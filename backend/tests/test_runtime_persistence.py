import asyncio

from datetime import UTC, datetime

from app.models import MatchCard, MatchStatus, SportType
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
        self.last_match_payload: dict | None = None
        self.market_snapshots: list[dict] = []
        self.collector_settings: dict | None = None

    async def ensure_match(self, payload: dict) -> None:
        self.match_writes += 1
        self.last_match_payload = dict(payload)

    async def insert_tick(self, payload: dict) -> None:
        self.tick_writes += 1

    async def insert_market_snapshot(self, payload: dict) -> None:
        self.market_snapshots.append(dict(payload))

    async def get_collector_settings(self) -> dict | None:
        return self.collector_settings


def test_runtime_step_persists_ticks_to_cache_and_repository() -> None:
    cache = FakeCacheWriter()
    repo = FakeRepository()
    runtime = TradingRuntime(cache_writer=cache, repository=repo)
    asyncio.run(runtime.start_simulation(initial_balance=1000.0, retracement=0.05))
    assert len(cache.writes) >= 1
    assert repo.match_writes >= 1
    assert repo.tick_writes >= 1
    assert repo.last_match_payload is not None
    assert "moneyline_volume" in repo.last_match_payload
    assert "total_volume" in repo.last_match_payload
    assert "latest_ts_utc" in repo.last_match_payload


def test_runtime_market_universe_persists_total_and_moneyline_volume() -> None:
    repo = FakeRepository()
    runtime = TradingRuntime(cache_writer=FakeCacheWriter(), repository=repo)

    asyncio.run(
        runtime._on_market_universe(
            [
                {
                    "id": "mkt-1",
                    "slug": "sporting-cp-vs-fk-bodo-glimt-moneyline",
                    "question": "Sporting CP vs FK Bodo/Glimt",
                    "sport": "Football",
                    "startDate": "2026-03-17T16:45:00Z",
                    "volumeNum": 180000,
                    "outcomes": '["Sporting CP","Draw","FK Bodo/Glimt"]',
                    "outcomePrices": '["0.55","0.23","0.22"]',
                    "clobTokenIds": '["s1","s2","s3"]',
                    "events": [
                        {
                            "id": "evt-1",
                            "slug": "ucl-spo1-bog1-2026-03-17",
                            "title": "Sporting CP vs FK Bodo/Glimt",
                            "category": "Sports",
                            "volume": 520000,
                            "startDate": "2026-03-17T16:45:00Z",
                        }
                    ],
                }
            ]
        )
    )

    assert repo.last_match_payload is not None
    assert repo.last_match_payload["moneyline_volume"] == 180000
    assert repo.last_match_payload["total_volume"] == 520000
    assert "latest_ts_utc" in repo.last_match_payload
    matches = runtime.get_matches()
    target = next(match for match in matches if match.match_id == "evt-1")
    assert target.moneyline_volume == 180000
    assert target.total_volume == 520000


def test_runtime_get_matches_filters_by_total_volume_threshold() -> None:
    runtime = TradingRuntime(cache_writer=FakeCacheWriter(), repository=FakeRepository())
    runtime.update_collector_settings(
        {
            "football_volume_threshold_k": 500,
            "basketball_volume_threshold_k": 100,
        }
    )
    runtime._external_matches = {
        "evt-1": MatchCard(
            match_id="evt-1",
            sport=SportType.football,
            league="Champions League",
            team_home="Sporting CP",
            team_away="FK Bodo/Glimt",
            start_time_utc=datetime(2026, 3, 17, 16, 45, 0, tzinfo=UTC),
            status=MatchStatus.pre,
            moneyline_volume=180000,
            total_volume=520000,
            latest_ts_utc=datetime(2026, 3, 16, 12, 0, 0, tzinfo=UTC),
        )
    }

    matches = runtime.get_matches()

    assert any(match.match_id == "evt-1" for match in matches)


def test_next_market_event_skips_seed_pipeline_when_external_stream_enabled(monkeypatch) -> None:
    runtime = TradingRuntime(cache_writer=FakeCacheWriter(), repository=FakeRepository())
    runtime._external_ticks = []
    runtime._external_started = False
    called = {"start": 0, "step": 0}

    async def fake_start() -> None:
        called["start"] += 1
        runtime._external_started = True

    async def fake_step_once():
        called["step"] += 1
        return []

    monkeypatch.setattr("app.runtime.trading_runtime.settings.external_stream_enabled", True)
    monkeypatch.setattr(runtime, "start_external_connectors", fake_start)
    monkeypatch.setattr(runtime, "step_once", fake_step_once)

    payload = asyncio.run(runtime.next_market_event())

    assert payload == {"topic": "market.tick", "payload": {}}
    assert called["start"] == 1
    assert called["step"] == 0


def test_start_external_connectors_loads_persisted_collector_settings(monkeypatch) -> None:
    repo = FakeRepository()
    repo.collector_settings = {
        "collection_interval_minutes": 5,
        "football_volume_threshold_k": 500,
        "basketball_volume_threshold_k": 500,
    }
    runtime = TradingRuntime(cache_writer=FakeCacheWriter(), repository=repo)
    called = {"start": 0}

    async def fake_start() -> None:
        called["start"] += 1

    monkeypatch.setattr(runtime._external_service, "start", fake_start)

    asyncio.run(runtime.start_external_connectors())

    assert runtime.get_collector_settings()["football_volume_threshold_k"] == 500
    assert runtime.get_collector_settings()["basketball_volume_threshold_k"] == 500
    assert called["start"] == 1
