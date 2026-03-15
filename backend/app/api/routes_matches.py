from fastapi import APIRouter, Query
from app.models import MatchStatus, SportType
from app.services.match_service import list_matches


router = APIRouter(prefix="/api/v1", tags=["matches"])


@router.get("/matches")
async def get_matches(
    status: MatchStatus | None = Query(default=None),
    sport: SportType | None = Query(default=None),
) -> list[dict]:
    rows = list_matches(status=status, sport=sport)
    return [row.model_dump(mode="json") for row in rows]
