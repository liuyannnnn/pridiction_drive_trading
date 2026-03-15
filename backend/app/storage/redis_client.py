from redis.asyncio import Redis
from app.config import settings


redis_client = Redis.from_url(
    settings.redis_dsn,
    decode_responses=True,
)


async def ping_redis() -> bool:
    try:
        pong = await redis_client.ping()
        return bool(pong)
    except Exception:
        return False
