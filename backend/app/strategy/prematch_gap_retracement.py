from datetime import UTC, datetime, timedelta

from app.domain.events import MarketTickEvent
from app.domain.signals import TradeSignal


class PreMatchGapRetracementStrategy:
    def __init__(
        self,
        strategy_id: str,
        entry_spread_threshold: float,
        max_drawdown: float,
        trade_amount: float = 100.0,
    ) -> None:
        self._strategy_id = strategy_id
        self._entry_spread_threshold = entry_spread_threshold
        self._max_drawdown = max_drawdown
        self._trade_amount = trade_amount
        self._holding_outcome: dict[str, str] = {}
        self._peak_price: dict[str, float] = {}

    @property
    def strategy_id(self) -> str:
        return self._strategy_id

    def on_tick(self, tick: MarketTickEvent) -> TradeSignal | None:
        if tick.status != "pre":
            return None
        if tick.start_time_utc is None:
            return None
        if tick.start_time_utc - tick.ts_utc > timedelta(minutes=10):
            return None
        match_id = tick.match_id
        home_ask = tick.ask
        away_ask = max(0.0, 1 - tick.bid)
        spread = abs(home_ask - away_ask)
        holding = self._holding_outcome.get(match_id)
        if holding is None:
            if spread < self._entry_spread_threshold:
                return None
            selected = "home" if home_ask >= away_ask else "away"
            self._holding_outcome[match_id] = selected
            mark = tick.bid if selected == "home" else max(0.0, 1 - tick.ask)
            self._peak_price[match_id] = mark
            entry_price = tick.ask if selected == "home" else away_ask
            return TradeSignal(
                strategy_id=self._strategy_id,
                action="buy",
                match_id=match_id,
                outcome=selected,
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
