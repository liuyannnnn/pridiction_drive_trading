from datetime import UTC, datetime

from app.domain.events import MarketTickEvent
from app.domain.signals import TradeSignal


class RetracementStrategy:
    def __init__(self, strategy_id: str, retracement: float, trade_amount: float = 100.0) -> None:
        self._strategy_id = strategy_id
        self._retracement = retracement
        self._trade_amount = trade_amount
        self._peak_bid: dict[str, float] = {}
        self._has_position: dict[str, bool] = {}

    def on_tick(self, tick: MarketTickEvent) -> TradeSignal | None:
        match_id = tick.match_id
        peak = self._peak_bid.get(match_id, tick.bid)
        if tick.bid > peak:
            peak = tick.bid
        self._peak_bid[match_id] = peak
        holding = self._has_position.get(match_id, False)
        if not holding:
            self._has_position[match_id] = True
            return TradeSignal(
                strategy_id=self._strategy_id,
                action="buy",
                match_id=match_id,
                outcome=tick.outcome,
                price=tick.ask,
                amount=self._trade_amount,
                ts_utc=datetime.now(UTC),
            )
        drawdown = 0.0 if peak <= 0 else (peak - tick.bid) / peak
        if drawdown >= self._retracement:
            self._has_position[match_id] = False
            self._peak_bid[match_id] = tick.bid
            return TradeSignal(
                strategy_id=self._strategy_id,
                action="sell",
                match_id=match_id,
                outcome=tick.outcome,
                price=tick.bid,
                amount=self._trade_amount,
                ts_utc=datetime.now(UTC),
            )
        return None
