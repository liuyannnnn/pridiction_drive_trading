from datetime import UTC, datetime, timedelta
from pathlib import Path
import asyncio

from app.domain.events import MarketTickEvent
from app.runtime.trading_manager import TradingInstance, TradingManager
from app.strategy.registry import get_strategy_catalog


def test_strategy_catalog_contains_two_test_strategies() -> None:
    catalog = get_strategy_catalog()
    names = [item["name"] for item in catalog]
    assert "prematch_gap_retracement" in names
    assert "live_first_goal_retracement" in names


def test_trading_instance_isolated_by_parameters() -> None:
    now = datetime.now(UTC)
    trading_a = TradingInstance(
        trading_id="T001",
        strategy_name="prematch_gap_retracement",
        strategy_params={"entry_spread_threshold": 0.25, "max_drawdown": 0.05, "trade_amount": 100},
        affect_sports=["football"],
        mode="simulation",
        created_at=now,
    )
    trading_b = TradingInstance(
        trading_id="T002",
        strategy_name="prematch_gap_retracement",
        strategy_params={"entry_spread_threshold": 0.10, "max_drawdown": 0.05, "trade_amount": 200},
        affect_sports=["football"],
        mode="simulation",
        created_at=now,
    )
    tick = MarketTickEvent(
        match_id="m1",
        ts_utc=now,
        outcome="home",
        bid=0.56,
        ask=0.58,
        volume=1000.0,
        source="pm",
        sport="football",
        status="pre",
        start_time_utc=now + timedelta(minutes=8),
        score_home=0,
        score_away=0,
    )
    trading_a.process_tick(tick)
    trading_b.process_tick(tick)
    assert len(trading_a.executor.logs) == 0
    assert len(trading_b.executor.logs) == 1
    assert trading_b.executor.logs[0]["amount"] == 200


def test_trading_manager_create_and_start() -> None:
    manager = TradingManager()
    created = manager.create_trading(
        strategy_name="prematch_gap_retracement",
        strategy_params={"entry_spread_threshold": 0.25, "max_drawdown": 0.05, "initial_balance": 2500.0},
        affect_sports=["football"],
        mode="simulation",
    )
    trading_id = created["trading_id"]
    assert created["initial_balance"] == 2500.0
    started = manager.start_trading(trading_id)
    assert started["status"] == "running"
    assert started["trading_id"] == trading_id
    assert started["initial_balance"] == 2500.0


def test_trading_instance_writes_separate_log_file(tmp_path: Path) -> None:
    now = datetime.now(UTC)
    trading = TradingInstance(
        trading_id="TLOG001",
        strategy_name="prematch_gap_retracement",
        strategy_params={"entry_spread_threshold": 0.10, "max_drawdown": 0.05, "trade_amount": 120},
        affect_sports=["football"],
        mode="simulation",
        created_at=now,
        log_dir=tmp_path,
    )
    tick = MarketTickEvent(
        match_id="m1",
        ts_utc=now,
        outcome="home",
        bid=0.56,
        ask=0.58,
        volume=1000.0,
        source="pm",
        sport="football",
        status="pre",
        start_time_utc=now + timedelta(minutes=8),
        score_home=0,
        score_away=0,
    )
    trading.process_tick(tick)
    log_path = tmp_path / "TLOG001.log"
    assert log_path.exists()
    content = log_path.read_text(encoding="utf-8")
    assert '"trading_id": "TLOG001"' in content
    assert '"action": "buy"' in content


def test_dispatcher_stays_idle_without_running_tradings() -> None:
    class FakeRuntime:
        def __init__(self) -> None:
            self.calls = 0

        async def step_once(self):
            self.calls += 1
            return []

    async def case() -> None:
        runtime = FakeRuntime()
        manager = TradingManager(market_runtime=runtime)
        await manager.start_dispatcher()
        await asyncio.sleep(0.05)
        assert runtime.calls == 0
        await manager.stop_dispatcher()

    asyncio.run(case())


def test_start_trading_bootstraps_dispatcher() -> None:
    class FakeRuntime:
        def __init__(self) -> None:
            self.calls = 0

        async def step_once(self):
            self.calls += 1
            return []

    async def case() -> None:
        runtime = FakeRuntime()
        manager = TradingManager(market_runtime=runtime)
        created = manager.create_trading(
            strategy_name="prematch_gap_retracement",
            strategy_params={"entry_spread_threshold": 0.25, "max_drawdown": 0.05},
            affect_sports=["football"],
            mode="simulation",
        )
        manager.start_trading(created["trading_id"])
        await asyncio.sleep(0.05)
        assert runtime.calls > 0
        manager.stop_trading(created["trading_id"])
        await asyncio.sleep(0.01)
        await manager.stop_dispatcher()

    asyncio.run(case())
