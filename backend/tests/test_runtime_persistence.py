import asyncio

from app.runtime.trading_runtime import TradingRuntime


class FakeCacheWriter:
    def __init__(self) -> None:
        self.writes: list[tuple[str, dict]] = []

    async def write_live_tick(self, match_id: str, payload: dict) -> None:
        self.writes.append((match_id, payload))


class FakeRepository:
    def __init__(self) -> None:
        self.match_writes = 0
        self.tick_writes = 0

    async def ensure_match(self, payload: dict) -> None:
        self.match_writes += 1

    async def insert_tick(self, payload: dict) -> None:
        self.tick_writes += 1


def test_runtime_step_persists_ticks_to_cache_and_repository() -> None:
    cache = FakeCacheWriter()
    repo = FakeRepository()
    runtime = TradingRuntime(cache_writer=cache, repository=repo)
    asyncio.run(runtime.start_simulation(initial_balance=1000.0, retracement=0.05))
    assert len(cache.writes) >= 1
    assert repo.match_writes >= 1
    assert repo.tick_writes >= 1
