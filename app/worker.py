import asyncio
import logging
from uuid import uuid4
from sqlalchemy import bindparam, text
from sqlalchemy.ext.asyncio import AsyncSession
from app.config import settings
from app.database import AsyncSessionLocal
from app.face_engine import get_face_embeddings
from app.models.face import FaceEmbedding
from app.models.image_face_mapping import ImageFaceMapping
import app.redis_client as redis_store
from app.redis_client import init_redis
from app.storage import download_bytes

logger = logging.getLogger(__name__)

STREAM_NAME = "grabpic:ingest"
GROUP_NAME = "grabpic-workers"


async def _find_matching_grab_id(session: AsyncSession, embedding: list[float]) -> str | None:
    query_vec_str = "[" + ",".join(map(str, embedding)) + "]"
    stmt = text("""
        SELECT grab_id, 1 - (embedding <=> CAST(:query_vec AS vector)) AS similarity
        FROM face_embeddings
        ORDER BY embedding <=> CAST(:query_vec AS vector)
        LIMIT 1
    """)

    result = await session.execute(stmt, {"query_vec": query_vec_str})
    row = result.first()
    if row is None:
        return None
    if float(row.similarity) >= settings.FACE_SIMILARITY_THRESHOLD:
        return row.grab_id
    return None


async def _process_entry(message_id: str, message: dict[str, str]) -> None:
    # ← reads live value through module reference, not stale import
    if redis_store.redis_client is None:
        raise RuntimeError("Redis client not initialized")

    image_id = message.get("image_id")
    bucket_key = message.get("bucket_key")
    if not image_id or not bucket_key:
        logger.warning("Skipping malformed ingest entry %s", message_id)
        await redis_store.redis_client.xack(STREAM_NAME, GROUP_NAME, message_id)
        return

    try:
        image_bytes = await download_bytes(bucket_key)
        faces = await asyncio.to_thread(get_face_embeddings, image_bytes)

        async with AsyncSessionLocal() as session:
            async with session.begin():
                for embedding, det_score, bbox in faces:
                    grab_id = await _find_matching_grab_id(session, embedding)
                    if grab_id is None:
                        grab_id = f"grb_{uuid4().hex[:12]}"

                    face_record = FaceEmbedding(
                        grab_id=grab_id,
                        embedding=embedding,
                        image_id=image_id,
                        bbox={"x1": bbox[0], "y1": bbox[1], "x2": bbox[2], "y2": bbox[3]} if len(bbox) >= 4 else {},
                        quality_score=det_score,
                    )
                    session.add(face_record)

                    mapping = ImageFaceMapping(image_id=image_id, grab_id=grab_id)
                    session.add(mapping)

    except Exception:
        logger.exception("Failed processing ingest entry %s", message_id)
    finally:
        # ← always ack, even on failure, to avoid poison pills
        await redis_store.redis_client.xack(STREAM_NAME, GROUP_NAME, message_id)


async def run() -> None:
    # ← init_redis sets the global, we read it via redis_store after
    await init_redis()

    try:
        await redis_store.redis_client.xgroup_create(
            STREAM_NAME, GROUP_NAME, id="0", mkstream=True  # ← "0" not "$" so pending msgs are reprocessed
        )
    except Exception as exc:
        if "BUSYGROUP" not in str(exc):
            raise

    logger.info("Worker started with consumer %s", settings.WORKER_NAME)

    while True:
        entries = await redis_store.redis_client.xreadgroup(
            GROUP_NAME,
            settings.WORKER_NAME,
            {STREAM_NAME: ">"},
            count=1,
            block=1000,
        )

        if not entries:
            await asyncio.sleep(1)
            continue

        for _, messages in entries:
            for message_id, message in messages:
                await _process_entry(message_id, message)


asyncio.run(run())  # ← runs whether invoked as -m app.worker or directly