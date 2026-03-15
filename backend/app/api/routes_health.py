from fastapi import APIRouter
from app.storage.postgres import ping_postgres
from app.storage.redis_client import ping_redis


router = APIRouter(prefix="/api/v1", tags=["health"])


@router.get("/health")
async def get_health() -> dict:
    postgres_ok = await ping_postgres()
    redis_ok = await ping_redis()
    status = "ok" if postgres_ok and redis_ok else "degraded"
    return {
        "status": status,
        "postgres": postgres_ok,
        "redis": redis_ok,
    }
