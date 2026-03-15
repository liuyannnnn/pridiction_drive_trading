import json
from app.storage.redis_client import redis_client


class CacheWriter:
    async def write_live_tick(self, match_id: str, payload: dict) -> None:
        key = f"pm:live:{match_id}:latest"
        await redis_client.set(key, json.dumps(payload, ensure_ascii=False))
        await redis_client.xadd("events:market", {"match_id": match_id, "payload": json.dumps(payload, ensure_ascii=False)}, maxlen=5000)
