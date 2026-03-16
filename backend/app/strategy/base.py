from typing import Protocol

from app.domain.events import MarketTickEvent
from app.domain.signals import TradeSignal


class TradingStrategy(Protocol):
    @property
    def strategy_id(self) -> str: ...

    def on_tick(self, tick: MarketTickEvent) -> TradeSignal | None: ...
