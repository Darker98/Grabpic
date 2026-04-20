import asyncio
import logging
from io import BytesIO
from uuid import UUID, uuid4
from PIL import Image
from fastapi import APIRouter, Depends, File, Form, HTTPException, Header, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession
from slowapi import Limiter
from slowapi.util import get_remote_address
from app.config import settings
from app.database import get_session
from app.models.image import Image as ImageModel
import app.redis_client as redis_store
from app.storage import upload_bytes
from app.schemas.upload import UploadResponse
from fastapi import Request

logger = logging.getLogger(__name__)
router = APIRouter()
limiter = Limiter(key_func=get_remote_address)


async def _validate_upload_file(file: UploadFile) -> tuple[bytes, str, str]:
    content = await file.read()
    if len(content) > 20 * 1024 * 1024:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="File exceeds 20MB limit")

    def _validate() -> str:
        with Image.open(BytesIO(content)) as image_obj:
            if image_obj.format not in {"JPEG", "PNG"}:
                raise ValueError("Unsupported image format")
            return image_obj.format.lower()

    try:
        format_name = await asyncio.to_thread(_validate)
    except ValueError:
        raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail="Invalid image format")

    extension = "jpg" if format_name == "jpeg" else "png"
    content_type = "image/jpeg" if extension == "jpg" else "image/png"
    return content, extension, content_type


@router.post("/upload", response_model=UploadResponse, status_code=status.HTTP_202_ACCEPTED)
@limiter.limit("10/10minutes")
async def upload_images(
    request: Request,
    images: list[UploadFile] = File(...),
    x_admin_key: str | None = Header(None, alias="X-Admin-Key"),
    session: AsyncSession = Depends(get_session),
) -> UploadResponse:
    if x_admin_key != settings.ADMIN_API_KEY:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")

    if not images:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="No images provided")

    if redis_store.redis_client is None:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Redis is not available")

    job_ids: list[str] = []
    accepted = 0

    async with session.begin():
        for uploaded_file in images:
            content, extension, content_type = await _validate_upload_file(uploaded_file)
            image_id = uuid4()
            bucket_key = f"{image_id}.{extension}"
            await upload_bytes(bucket_key, content, content_type)

            image_record = ImageModel(
                id=image_id,
                bucket_key=bucket_key,
            )
            session.add(image_record)
            accepted += 1

            entry_id = await redis_store.redis_client.xadd(
                "grabpic:ingest",
                {
                    "image_id": str(image_id),
                    "bucket_key": bucket_key,
                },
            )
            job_ids.append(entry_id)

    return UploadResponse(accepted=accepted, job_ids=job_ids)
