import logging
from datetime import datetime, timezone, timedelta
from uuid import UUID
from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from slowapi import Limiter
from slowapi.util import get_remote_address
from app.config import settings
from app.database import get_session
from app.models.image import Image as ImageModel
from app.models.image_face_mapping import ImageFaceMapping
import app.redis_client as redis_store
from app.schemas.images import ImageItem, ImageListResponse
from app import storage
from fastapi import Request

logger = logging.getLogger(__name__)
router = APIRouter()
limiter = Limiter(key_func=get_remote_address)


@router.get("", response_model=ImageListResponse)
@limiter.limit("10/10minutes")
async def list_images(
    request: Request,
    authorization: str | None = Header(None),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
) -> ImageListResponse:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Token missing or expired")

    token = authorization.removeprefix("Bearer ").strip()
    if not token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Token missing or expired")

    if redis_store.redis_client is None:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Redis is not available")

    grab_id = await redis_store.redis_client.get(f"grabpic:token:{token}")
    if not grab_id:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Token missing or expired")

    count_query = select(func.count()).select_from(ImageFaceMapping).join(ImageModel, ImageFaceMapping.image_id == ImageModel.id)
    count_query = count_query.where(ImageFaceMapping.grab_id == grab_id)

    total = await session.scalar(count_query) or 0
    offset = (page - 1) * limit

    query = select(ImageModel.id, ImageModel.bucket_key, ImageModel.taken_at).join(ImageFaceMapping, ImageFaceMapping.image_id == ImageModel.id)
    query = query.where(ImageFaceMapping.grab_id == grab_id)
    query = query.offset(offset).limit(limit)

    rows = await session.execute(query)
    images: list[ImageItem] = []
    expires_at = datetime.now(timezone.utc) + timedelta(seconds=settings.TOKEN_TTL_SECONDS)

    for image_id, bucket_key, taken_at in rows.fetchall():
        url = await storage.generate_presigned_url(bucket_key, expires_in=settings.TOKEN_TTL_SECONDS)
        images.append(
            ImageItem(
                image_id=str(image_id),
                url=url,
                expires_at=expires_at,
                taken_at=taken_at,
            )
        )

    return ImageListResponse(grab_id=grab_id, total=total, page=page, images=images)
