from datetime import UTC, datetime

from app.domain.events import MarketTickEvent
from app.execution.simulator import SimulationExecutor
from app.strategy.registry import build_strategies
from app.strategy.retracement import RetracementStrategy


def test_retracement_strategy_generates_buy_then_sell() -> None:
    strategy = RetracementStrategy(strategy_id="S001", retracement=0.05)
    match_id = "pm_football_001"
    first = MarketTickEvent(
        match_id=match_id,
        ts_utc=datetime.now(UTC),
        outcome="home",
        bid=0.50,
        ask=0.52,
        volume=10000.0,
        source="pm",
    )
    buy_signal = strategy.on_tick(first)
    assert buy_signal is not None
    assert buy_signal.action == "buy"

    second = MarketTickEvent(
        match_id=match_id,
        ts_utc=datetime.now(UTC),
        outcome="home",
        bid=0.60,
        ask=0.62,
        volume=10500.0,
        source="pm",
    )
    assert strategy.on_tick(second) is None

    third = MarketTickEvent(
        match_id=match_id,
        ts_utc=datetime.now(UTC),
        outcome="home",
        bid=0.54,
        ask=0.56,
        volume=11000.0,
        source="pm",
    )
    sell_signal = strategy.on_tick(third)
    assert sell_signal is not None
    assert sell_signal.action == "sell"


def test_simulation_executor_updates_balance_and_positions() -> None:
    simulator = SimulationExecutor(initial_balance=1000.0)
    buy = simulator.execute(
        strategy_id="S001",
        action="buy",
        match_id="pm_football_001",
        outcome="home",
        price=0.5,
        amount=100.0,
    )
    assert buy["status"] == "filled"
    assert simulator.balance == 900.0
    assert len(simulator.positions) == 1

    sell = simulator.execute(
        strategy_id="S001",
        action="sell",
        match_id="pm_football_001",
        outcome="home",
        price=0.55,
        amount=100.0,
    )
    assert sell["status"] == "filled"
    assert simulator.balance > 1000.0
    assert len(simulator.positions) == 0


def test_strategy_registry_builds_multiple_strategies() -> None:
    strategies = build_strategies(
        [
            {"name": "prematch_gap_retracement", "strategy_id": "S001", "entry_spread_threshold": 0.25, "max_drawdown": 0.05, "trade_amount": 100},
            {"name": "live_first_goal_retracement", "strategy_id": "S002", "max_drawdown": 0.05, "trade_amount": 80},
        ]
    )
    assert len(strategies) == 2
    assert [item.strategy_id for item in strategies] == ["S001", "S002"]
