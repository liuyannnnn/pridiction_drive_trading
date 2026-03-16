from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field


class MatchStatus(str, Enum):
    live = "live"
    pre = "pre"
    finished = "finished"


class SportType(str, Enum):
    football = "football"
    basketball = "basketball"


class MatchCard(BaseModel):
    match_id: str = Field(..., description="系统内部比赛 ID")
    sport: SportType
    league: str
    team_home: str
    team_away: str
    start_time_utc: datetime
    status: MatchStatus
    moneyline_volume: float
    total_volume: float
    latest_ts_utc: datetime
    score_home: int | None = None
    score_away: int | None = None
    external_event_id: str = ""
    external_event_slug: str = ""
    external_market_id: str = ""
    external_market_slug: str = ""
