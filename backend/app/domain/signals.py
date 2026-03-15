from dataclasses import dataclass
from datetime import datetime


@dataclass(slots=True)
class TradeSignal:
    strategy_id: str
    action: str
    match_id: str
    outcome: str
    price: float
    amount: float
    ts_utc: datetime
