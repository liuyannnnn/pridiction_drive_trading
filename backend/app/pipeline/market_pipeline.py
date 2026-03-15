from datetime import UTC, datetime, timedelta

from app.domain.events import MarketTickEvent
from app.models import MatchCard, MatchStatus, SportType
from app.pipeline.event_bus import EventBus


class MarketPipeline:
    def __init__(self, sample_every: int = 3) -> None:
        self._bus = EventBus()
        self._sample_every = max(1, sample_every)
        self._step = 0
        self._matches = self._build_seed_matches()
        self._sampled_ticks: dict[str, list[MarketTickEvent]] = {match.match_id: [] for match in self._matches}

    def get_matches(self) -> list[MatchCard]:
        return self._matches

    def get_sampled_ticks(self, match_id: str, limit: int = 50) -> list[MarketTickEvent]:
        rows = self._sampled_ticks.get(match_id, [])
        return rows[-limit:]

    async def run_step(self) -> None:
        self._step += 1
        now = datetime.now(UTC)
        for index, match in enumerate(self._matches):
            if match.status != MatchStatus.live:
                continue
            drift = 0.003 if index % 2 == 0 else -0.003
            base = 0.5 + drift * self._step
            bid = min(0.95, max(0.05, base))
            ask = min(0.99, bid + 0.02)
            volume = match.moneyline_volume + self._step * 120
            tick = MarketTickEvent(
                match_id=match.match_id,
                ts_utc=now,
                outcome="home",
                bid=round(bid, 6),
                ask=round(ask, 6),
                volume=float(volume),
                source="pm",
            )
            if self._step % self._sample_every == 0:
                self._sampled_ticks[match.match_id].append(tick)
            await self._bus.publish("market.tick", tick)

    @staticmethod
    def _build_seed_matches() -> list[MatchCard]:
        now = datetime.now(UTC)
        return [
            MatchCard(
                match_id="pm_football_001",
                sport=SportType.football,
                league="Premier League",
                team_home="Arsenal",
                team_away="Chelsea",
                start_time_utc=now - timedelta(minutes=40),
                status=MatchStatus.live,
                moneyline_volume=78000.0,
                total_volume=201000.0,
                latest_ts_utc=now,
            ),
            MatchCard(
                match_id="pm_basketball_001",
                sport=SportType.basketball,
                league="NBA",
                team_home="Lakers",
                team_away="Warriors",
                start_time_utc=now + timedelta(hours=3),
                status=MatchStatus.pre,
                moneyline_volume=145000.0,
                total_volume=380000.0,
                latest_ts_utc=now,
            ),
        ]
