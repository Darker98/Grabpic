import asyncio
import secrets
import logging
from uuid import UUID
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy import bindparam, literal, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.config import settings
from app.database import get_session
from app.face_engine import get_face_embeddings
from app.models.face import FaceEmbedding
from app.models.image import Image as ImageModel
import app.redis_client as redis_store
from app.schemas.auth import SelfieResponse
from fastapi import Request

logger = logging.getLogger(__name__)
router = APIRouter()
limiter = Limiter(key_func=get_remote_address)


@router.post("/selfie", response_model=SelfieResponse)
@limiter.limit("10/10minutes")
async def authenticate_selfie(
    request: Request,
    selfie: UploadFile = File(...),
    session: AsyncSession = Depends(get_session),
) -> SelfieResponse:
    selfie_bytes = await selfie.read()
    if not selfie_bytes:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail="No selfie image provided")

    try:
        faces = await asyncio.to_thread(get_face_embeddings, selfie_bytes)
    except ValueError:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail="No face detected in selfie")

    if len(faces) != 1:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Selfie must contain exactly one face")

    embedding, _, _ = faces[0]
    distance_expression = FaceEmbedding.embedding.op("<=>")(bindparam("query_vec", value=embedding))
    similarity_expression = literal(1) - distance_expression
    query = select(FaceEmbedding.grab_id, similarity_expression.label("similarity"))

    query = query.order_by(distance_expression).limit(1)
    result = await session.execute(query)
    row = result.first()

    if row is None or row.similarity < settings.FACE_SIMILARITY_THRESHOLD:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="No match found")

    token = "tok_" + secrets.token_urlsafe(24)
    if redis_store.redis_client is None:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Redis is not available")

    await redis_store.redis_client.set(f"grabpic:token:{token}", row.grab_id, ex=settings.TOKEN_TTL_SECONDS)

    return SelfieResponse(
        token=token,
        expires_in=settings.TOKEN_TTL_SECONDS,
        match_confidence=round(float(row.similarity), 4),
    )
