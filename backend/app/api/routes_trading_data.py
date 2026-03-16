from fastapi import APIRouter, Query

from app.config import settings
from app.runtime.container import runtime, trading_manager


router = APIRouter(prefix="/api/v1", tags=["trading-data"])


@router.get("/accounts")
async def list_accounts() -> list[dict]:
    rows = []
    for item in trading_manager.list_tradings():
        strategy_params = item.get("strategy_params", {}) if isinstance(item.get("strategy_params"), dict) else {}
        retracement = float(strategy_params.get("max_drawdown", strategy_params.get("retracement", 0.05)))
        rows.append(
            {
                "id": item.get("trading_id"),
                "mode": item.get("mode", "simulation"),
                "strategy_name": item.get("strategy_name", ""),
                "strategy_params": strategy_params,
                "retracement": retracement,
                "initial_balance": float(item.get("initial_balance", 0.0)),
                "affect_sports": item.get("affect_sports", []),
                "total_assets": float(item.get("equity", item.get("balance", 0.0))),
                "available_cash": float(item.get("balance", 0.0)),
                "position_count": int(item.get("positions", 0)),
                "win_rate": float(item.get("win_rate", 0.0)),
                "is_running": item.get("status") == "running",
                "trading_id": item.get("trading_id"),
                "status": item.get("status"),
            }
        )
    return rows


@router.get("/positions")
async def list_positions(trading_id: str | None = Query(default=None)) -> list[dict]:
    if trading_id:
        return trading_manager.get_trading_positions(trading_id)
    rows: list[dict] = []
    for item in trading_manager.list_tradings():
        rows.extend(trading_manager.get_trading_positions(item["trading_id"]))
    return rows


@router.get("/trades")
async def list_trades(
    trading_id: str | None = Query(default=None),
    match_id: str | None = Query(default=None),
    limit: int = Query(default=200, ge=1, le=1000),
) -> list[dict]:
    if trading_id:
        return trading_manager.get_trading_trades(trading_id, limit=limit, match_id=match_id)
    rows: list[dict] = []
    for item in trading_manager.list_tradings():
        rows.extend(trading_manager.get_trading_trades(item["trading_id"], limit=limit, match_id=match_id))
    return rows[-limit:]


@router.get("/logs")
async def list_logs(
    trading_id: str | None = Query(default=None),
    match_id: str | None = Query(default=None),
    limit: int = Query(default=200, ge=1, le=1000),
) -> list[dict]:
    if trading_id:
        return trading_manager.get_trading_logs(trading_id, limit=limit, match_id=match_id)
    rows: list[dict] = []
    for item in trading_manager.list_tradings():
        rows.extend(trading_manager.get_trading_logs(item["trading_id"], limit=limit, match_id=match_id))
    return rows[-limit:]


@router.get("/goalserve/match/{match_id}")
async def get_goalserve_match_detail(match_id: str) -> dict:
    return runtime.get_goalserve_detail(match_id=match_id)


@router.get("/collector/status")
async def collector_status() -> dict:
    state = runtime.state()
    ticks = runtime.get_ticks(limit=1)
    latest = ticks[-1] if ticks else {}
    return {
        "external_stream_enabled": bool(state.get("external_stream_enabled", False)),
        "external_stream_started": bool(state.get("external_stream_started", False)),
        "polymarket_ws_enabled": bool(settings.polymarket_ws_enabled),
        "goalserve_ws_enabled": bool(settings.goalserve_ws_enabled),
        "matches_count": len(runtime.get_matches()),
        "last_tick_source": latest.get("source"),
        "latest_tick_ts_utc": latest.get("ts_utc"),
    }
