from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.routes_health import router as health_router
from app.api.routes_matches import router as matches_router
from app.api.routes_simulation import router as simulation_router
from app.api.routes_settings import router as settings_router
from app.api.routes_trading_data import router as trading_data_router
from app.config import settings
from app.runtime.container import runtime, trading_manager


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in settings.cors_allowed_origins.split(",") if origin.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def on_startup() -> None:
    try:
        await runtime.repository.ensure_schema()
    except Exception:
        pass
    if settings.external_stream_enabled:
        await runtime.start_external_connectors()


@app.on_event("shutdown")
async def on_shutdown() -> None:
    await trading_manager.stop_dispatcher()
    await runtime.stop_external_connectors()

app.include_router(health_router)
app.include_router(matches_router)
app.include_router(simulation_router)
app.include_router(settings_router)
app.include_router(trading_data_router)
