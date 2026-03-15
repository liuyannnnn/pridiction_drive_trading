import asyncio
from pydantic import BaseModel, Field
from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

from app.runtime.container import runtime


router = APIRouter(prefix="/api/v1", tags=["simulation"])


class StartSimulationRequest(BaseModel):
    initial_balance: float = Field(default=10000.0, gt=0)
    retracement: float = Field(default=0.03, gt=0, lt=1)


@router.post("/simulation/start")
async def start_simulation(body: StartSimulationRequest) -> dict:
    return await runtime.start_simulation(
        initial_balance=body.initial_balance,
        retracement=body.retracement,
    )


@router.post("/simulation/stop")
async def stop_simulation() -> dict:
    return runtime.stop_simulation()


@router.get("/simulation/state")
async def simulation_state() -> dict:
    return runtime.state()


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
