import asyncio
from datetime import UTC, datetime

from app.domain.events import MarketTickEvent
from app.pipeline.event_bus import EventBus
from app.pipeline.market_pipeline import MarketPipeline


def test_event_bus_publish_subscribe() -> None:
    bus = EventBus()
    received: list[MarketTickEvent] = []

    async def on_tick(event: MarketTickEvent) -> None:
        received.append(event)

    bus.subscribe("market.tick", on_tick)
    event = MarketTickEvent(
        match_id="pm_football_001",
        ts_utc=datetime.now(UTC),
        outcome="home",
        bid=0.51,
        ask=0.53,
        volume=10000.0,
        source="pm",
    )
    asyncio.run(bus.publish("market.tick", event))
    assert len(received) == 1
    assert received[0].match_id == "pm_football_001"


def test_market_pipeline_step_generates_sampled_ticks() -> None:
    pipeline = MarketPipeline(sample_every=1)
    asyncio.run(pipeline.run_step())
    matches = pipeline.get_matches()
    assert len(matches) >= 1
    ticks = pipeline.get_sampled_ticks(match_id=matches[0].match_id, limit=5)
    assert len(ticks) >= 1
