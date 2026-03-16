from datetime import UTC, datetime

from app.domain.events import MarketTickEvent
from app.domain.signals import TradeSignal


class LiveFirstGoalRetracementStrategy:
    def __init__(
        self,
        strategy_id: str,
        max_drawdown: float,
        trade_amount: float = 100.0,
    ) -> None:
        self._strategy_id = strategy_id
        self._max_drawdown = max_drawdown
        self._trade_amount = trade_amount
        self._holding_outcome: dict[str, str] = {}
        self._peak_price: dict[str, float] = {}
        self._last_score: dict[str, tuple[int, int]] = {}

    @property
    def strategy_id(self) -> str:
        return self._strategy_id

    def on_tick(self, tick: MarketTickEvent) -> TradeSignal | None:
        if tick.sport != "football" or tick.status != "live":
            return None
        if tick.score_home is None or tick.score_away is None:
            return None
        match_id = tick.match_id
        prev_home, prev_away = self._last_score.get(match_id, (tick.score_home, tick.score_away))
        self._last_score[match_id] = (tick.score_home, tick.score_away)
        holding = self._holding_outcome.get(match_id)
        if holding is None:
            first_goal_side = None
            if prev_home == 0 and prev_away == 0 and tick.score_home > prev_home:
                first_goal_side = "home"
            if prev_home == 0 and prev_away == 0 and tick.score_away > prev_away:
                first_goal_side = "away"
            if first_goal_side is None:
                return None
            self._holding_outcome[match_id] = first_goal_side
            mark = tick.bid if first_goal_side == "home" else max(0.0, 1 - tick.ask)
            self._peak_price[match_id] = mark
            entry_price = tick.ask if first_goal_side == "home" else max(0.0, 1 - tick.bid)
            return TradeSignal(
                strategy_id=self._strategy_id,
                action="buy",
                match_id=match_id,
                outcome=first_goal_side,
                price=entry_price,
                amount=self._trade_amount,
                ts_utc=datetime.now(UTC),
            )
        mark_price = tick.bid if holding == "home" else max(0.0, 1 - tick.ask)
        peak = max(self._peak_price.get(match_id, mark_price), mark_price)
        self._peak_price[match_id] = peak
        drawdown = 0.0 if peak <= 0 else (peak - mark_price) / peak
        if drawdown < self._max_drawdown:
            return None
        self._holding_outcome.pop(match_id, None)
        self._peak_price.pop(match_id, None)
        return TradeSignal(
            strategy_id=self._strategy_id,
            action="sell",
            match_id=match_id,
            outcome=holding,
            price=mark_price,
            amount=self._trade_amount,
            ts_utc=datetime.now(UTC),
        )
