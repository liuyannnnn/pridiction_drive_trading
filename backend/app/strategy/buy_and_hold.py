from datetime import UTC, datetime

from app.domain.events import MarketTickEvent
from app.domain.signals import TradeSignal


class BuyAndHoldStrategy:
    def __init__(self, strategy_id: str, trade_amount: float = 100.0) -> None:
        self._strategy_id = strategy_id
        self._trade_amount = trade_amount
        self._has_position: dict[str, bool] = {}

    @property
    def strategy_id(self) -> str:
        return self._strategy_id

    def on_tick(self, tick: MarketTickEvent) -> TradeSignal | None:
        if self._has_position.get(tick.match_id, False):
            return None
        self._has_position[tick.match_id] = True
        return TradeSignal(
            strategy_id=self._strategy_id,
            action="buy",
            match_id=tick.match_id,
            outcome=tick.outcome,
            price=tick.ask,
            amount=self._trade_amount,
            ts_utc=datetime.now(UTC),
        )
