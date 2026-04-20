import logging
import redis.asyncio as redis
from app.config import settings

logger = logging.getLogger(__name__)
redis_client: redis.Redis | None = None


async def init_redis() -> redis.Redis:
    global redis_client
    if redis_client is None:
        logger.info("Connecting to Redis")
        redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)
        await redis_client.ping()
    return redis_client


async def close_redis() -> None:
    global redis_client
    if redis_client is not None:
        await redis_client.close()
        redis_client = None
