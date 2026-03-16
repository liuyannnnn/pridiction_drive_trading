from pydantic import BaseModel, Field
from fastapi import APIRouter

from app.config import settings
from app.runtime.container import runtime


router = APIRouter(prefix="/api/v1", tags=["settings"])


class CollectorSettingsRequest(BaseModel):
    collection_interval_minutes: int = Field(default=5, ge=1, le=120)
    football_volume_threshold_k: int = Field(default=50, ge=0, le=100000)
    basketball_volume_threshold_k: int = Field(default=100, ge=0, le=100000)


@router.get("/settings/collector")
async def get_collector_settings() -> dict:
    try:
        stored = await runtime.repository.get_collector_settings()
    except Exception:
        stored = None
    if stored is not None:
        runtime.update_collector_settings(stored)
    return runtime.get_collector_settings()


@router.put("/settings/collector")
async def put_collector_settings(body: CollectorSettingsRequest) -> dict:
    updated = runtime.update_collector_settings(body.model_dump())
    try:
        await runtime.repository.upsert_collector_settings(updated)
    except Exception:
        pass
    if settings.external_stream_enabled and runtime._external_started:
        try:
            await runtime.stop_external_connectors()
            await runtime.start_external_connectors()
        except Exception:
            pass
    return updated
