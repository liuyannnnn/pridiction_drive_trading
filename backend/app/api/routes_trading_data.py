from fastapi import APIRouter, Query

from app.runtime.container import runtime


router = APIRouter(prefix="/api/v1", tags=["trading-data"])


@router.get("/accounts")
async def list_accounts() -> list[dict]:
    return runtime.get_accounts()


@router.get("/positions")
async def list_positions() -> list[dict]:
    return runtime.get_positions()


@router.get("/trades")
async def list_trades() -> list[dict]:
    return runtime.get_trades()


@router.get("/logs")
async def list_logs(limit: int = Query(default=200, ge=1, le=1000)) -> list[dict]:
    return runtime.get_logs(limit=limit)


@router.get("/goalserve/match/{match_id}")
async def get_goalserve_match_detail(match_id: str) -> dict:
    return runtime.get_goalserve_detail(match_id=match_id)
