from fastapi import APIRouter, Query
from app.config import settings
from app.models import MatchStatus, SportType
from app.runtime.container import runtime
from app.services.match_service import list_matches


router = APIRouter(prefix="/api/v1", tags=["matches"])


@router.get("/matches")
async def get_matches(
    status: MatchStatus | None = Query(default=None),
    sport: SportType | None = Query(default=None),
) -> list[dict]:
    if settings.external_stream_enabled and not runtime._external_started:
        await runtime.start_external_connectors()
    rows = list_matches(status=status, sport=sport)
    return [row.model_dump(mode="json") for row in rows]
