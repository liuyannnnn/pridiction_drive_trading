import asyncio
from pydantic import BaseModel, Field
from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

from app.runtime.container import runtime, trading_manager


router = APIRouter(prefix="/api/v1", tags=["simulation"])


class StartSimulationRequest(BaseModel):
    initial_balance: float = Field(default=10000.0, gt=0)
    retracement: float = Field(default=0.03, gt=0, lt=1)
    strategies: list[dict] | None = None
    affect_sports: list[str] = Field(default_factory=lambda: ["football", "basketball"])


class CreateTradingRequest(BaseModel):
    strategy_name: str
    strategy_params: dict = Field(default_factory=dict)
    affect_sports: list[str] = Field(default_factory=lambda: ["football", "basketball"])
    mode: str = "simulation"


class UpdateTradingRequest(BaseModel):
    strategy_params: dict | None = None
    affect_sports: list[str] | None = None


@router.post("/simulation/start")
async def start_simulation(body: StartSimulationRequest) -> dict:
    strategy_payloads = body.strategies or [
        {
            "name": "prematch_gap_retracement",
            "initial_balance": body.initial_balance,
            "entry_spread_threshold": 0.25,
            "max_drawdown": body.retracement,
        }
    ]
    started_rows: list[dict] = []
    for item in strategy_payloads:
        strategy_params = dict(item)
        strategy_params.setdefault("initial_balance", body.initial_balance)
        strategy_name = str(strategy_params.get("name", "prematch_gap_retracement"))
        created = trading_manager.create_trading(
            strategy_name=strategy_name,
            strategy_params=strategy_params,
            affect_sports=body.affect_sports,
            mode="simulation",
        )
        started_rows.append(trading_manager.start_trading(created["trading_id"]))
    running = len([item for item in started_rows if item["status"] == "running"])
    return {
        "running": running > 0,
        "running_count": running,
        "trading_ids": [item["trading_id"] for item in started_rows],
        "strategy_ids": [f'{item["trading_id"]}-S001' for item in started_rows],
        "tradings": started_rows,
    }


@router.post("/simulation/stop")
async def stop_simulation() -> dict:
    rows = []
    for item in trading_manager.list_tradings():
        if item["mode"] != "simulation":
            continue
        if item["status"] == "running":
            rows.append(trading_manager.stop_trading(item["trading_id"]))
    return {"stopped": len(rows), "running": False}


@router.get("/simulation/state")
async def simulation_state() -> dict:
    rows = [item for item in trading_manager.list_tradings() if item["mode"] == "simulation"]
    running = len([item for item in rows if item["status"] == "running"])
    return {"running": running > 0, "running_count": running, "tradings": rows}


@router.get("/strategies/catalog")
async def strategy_catalog() -> list[dict]:
    return trading_manager.strategy_catalog()


@router.post("/tradings")
async def create_trading(body: CreateTradingRequest) -> dict:
    return trading_manager.create_trading(
        strategy_name=body.strategy_name,
        strategy_params=body.strategy_params,
        affect_sports=body.affect_sports,
        mode=body.mode,
    )


@router.get("/tradings")
async def list_tradings() -> list[dict]:
    return trading_manager.list_tradings()


@router.get("/tradings/{trading_id}")
async def get_trading(trading_id: str) -> dict:
    return trading_manager.get_trading(trading_id)


@router.put("/tradings/{trading_id}")
async def update_trading(trading_id: str, body: UpdateTradingRequest) -> dict:
    return trading_manager.update_trading(
        trading_id,
        strategy_params=body.strategy_params,
        affect_sports=body.affect_sports,
    )


@router.post("/tradings/{trading_id}/start")
async def start_trading(trading_id: str) -> dict:
    return trading_manager.start_trading(trading_id)


@router.post("/tradings/{trading_id}/stop")
async def stop_trading(trading_id: str) -> dict:
    return trading_manager.stop_trading(trading_id)


@router.delete("/tradings/{trading_id}")
async def delete_trading(trading_id: str) -> dict:
    return trading_manager.delete_trading(trading_id)


@router.get("/ticks")
async def list_ticks(
    match_id: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
) -> list[dict]:
    return runtime.get_ticks(match_id=match_id, limit=limit)


@router.websocket("/ws/market")
async def market_ws(websocket: WebSocket) -> None:
    await websocket.accept()
    try:
        while True:
            event = await runtime.next_market_event()
            await websocket.send_json(event)
            await asyncio.sleep(1)
    except WebSocketDisconnect:
        return
