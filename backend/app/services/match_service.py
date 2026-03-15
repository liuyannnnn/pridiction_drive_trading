from app.models import MatchCard, MatchStatus, SportType
from app.runtime.container import runtime


def list_matches(status: MatchStatus | None = None, sport: SportType | None = None) -> list[MatchCard]:
    rows = runtime.get_matches()
    if status is not None:
        rows = [row for row in rows if row.status == status]
    if sport is not None:
        rows = [row for row in rows if row.sport == sport]
    return rows
