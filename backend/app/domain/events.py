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
    sport: str | None = None
    status: str | None = None
    start_time_utc: datetime | None = None
    score_home: int | None = None
    score_away: int | None = None
