from dataclasses import dataclass
from datetime import datetime


@dataclass(slots=True)
class MarketTickEvent:
    match_id: str
    ts_utc: datetime
    outcome: str
    bid: float
    ask: float
    volume: float
    source: str
