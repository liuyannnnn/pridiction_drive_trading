from app.strategy.base import TradingStrategy
from app.strategy.live_first_goal_retracement import LiveFirstGoalRetracementStrategy
from app.strategy.prematch_gap_retracement import PreMatchGapRetracementStrategy
from app.strategy.retracement import RetracementStrategy


def build_strategies(configs: list[dict] | None) -> list[TradingStrategy]:
    if not configs:
        return [
            PreMatchGapRetracementStrategy(
                strategy_id="S001",
                entry_spread_threshold=0.25,
                max_drawdown=0.05,
                trade_amount=100.0,
            )
        ]
    rows: list[TradingStrategy] = []
    for item in configs:
        rows.append(
            build_strategy(
                name=str(item.get("name", "")).strip().lower(),
                strategy_id=str(item.get("strategy_id", "")).strip() or f"S{len(rows) + 1:03d}",
                params=item,
            )
        )
    return rows


def build_strategy(name: str, strategy_id: str, params: dict) -> TradingStrategy:
    trade_amount = float(params.get("trade_amount", 100.0))
    if name == "prematch_gap_retracement":
        return PreMatchGapRetracementStrategy(
            strategy_id=strategy_id,
            entry_spread_threshold=float(params.get("entry_spread_threshold", 0.25)),
            max_drawdown=float(params.get("max_drawdown", 0.05)),
            trade_amount=trade_amount,
        )
    if name == "live_first_goal_retracement":
        return LiveFirstGoalRetracementStrategy(
            strategy_id=strategy_id,
            max_drawdown=float(params.get("max_drawdown", 0.05)),
            trade_amount=trade_amount,
        )
    if name == "retracement":
        return RetracementStrategy(
            strategy_id=strategy_id,
            retracement=float(params.get("retracement", 0.05)),
            trade_amount=trade_amount,
        )
    raise ValueError(f"unknown strategy: {name}")


def get_strategy_catalog() -> list[dict]:
    return [
        {
            "name": "prematch_gap_retracement",
            "display_name": "开赛前价差买入回撤卖出",
            "params": {
                "entry_spread_threshold": {"type": "number", "default": 0.25, "min": 0.01, "max": 0.99},
                "max_drawdown": {"type": "number", "default": 0.05, "min": 0.001, "max": 0.5},
                "trade_amount": {"type": "number", "default": 100.0, "min": 1, "max": 1000000},
            },
        },
        {
            "name": "live_first_goal_retracement",
            "display_name": "足球首进球买入回撤卖出",
            "params": {
                "max_drawdown": {"type": "number", "default": 0.05, "min": 0.001, "max": 0.5},
                "trade_amount": {"type": "number", "default": 100.0, "min": 1, "max": 1000000},
            },
        },
    ]
