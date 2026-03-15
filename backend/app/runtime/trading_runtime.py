import json
from typing import Any
from dataclasses import asdict
from datetime import UTC, datetime

from app.config import settings
from app.connectors.external_feed import ExternalFeedService
from app.domain.events import MarketTickEvent
from app.execution.simulator import SimulationExecutor
from app.models import MatchCard, MatchStatus, SportType
from app.pipeline.market_pipeline import MarketPipeline
from app.storage.cache_writer import CacheWriter
from app.storage.repository import Repository
from app.strategy.retracement import RetracementStrategy


class TradingRuntime:
    def __init__(
        self,
        cache_writer: Any | None = None,
        repository: Any | None = None,
    ) -> None:
        self._running = False
        self._pipeline = MarketPipeline(sample_every=1)
        self._strategy = RetracementStrategy(strategy_id="S001", retracement=0.05)
        self._simulator = SimulationExecutor(initial_balance=10000.0)
        self._cache_writer = cache_writer or CacheWriter()
        self._repository = repository or Repository()
        self._cache_errors = 0
        self._db_errors = 0
        self._event_logs: list[dict] = []
        self._external_ticks: list[dict] = []
        self._external_matches: dict[str, MatchCard] = {}
        self._goalserve_details: dict[str, dict] = {}
        self._external_service = ExternalFeedService(
            on_tick=self._on_external_tick,
            on_goalserve=self._on_goalserve_detail,
            on_log=self._on_external_log,
        )
        self._external_started = False
        self._collector_settings = {
            "collection_interval_minutes": 5,
            "football_volume_threshold_k": 50,
            "basketball_volume_threshold_k": 100,
        }

    async def start_simulation(self, initial_balance: float, retracement: float) -> dict:
        self._simulator = SimulationExecutor(initial_balance=initial_balance)
        self._strategy = RetracementStrategy(strategy_id="S001", retracement=retracement)
        self._running = True
        await self.step_once()
        return {"running": self._running}

    def stop_simulation(self) -> dict:
        self._running = False
        return {"running": self._running}

    async def step_once(self) -> None:
        await self._pipeline.run_step()
        for match in self._pipeline.get_matches():
            ticks = self._pipeline.get_sampled_ticks(match.match_id, limit=1)
            if not ticks:
                continue
            tick = ticks[-1]
            await self._persist_tick(match=match, tick=tick)
            if self._running:
                await self._handle_tick(tick)

    async def _handle_tick(self, tick: MarketTickEvent) -> None:
        signal = self._strategy.on_tick(tick)
        if signal is None:
            return
        result = self._simulator.execute(
            strategy_id=signal.strategy_id,
            action=signal.action,
            match_id=signal.match_id,
            price=signal.price,
            amount=signal.amount,
        )
        self._event_logs.append(
            {
                "ts_utc": signal.ts_utc.isoformat(),
                "level": "Order",
                "message": f"{signal.action.upper()} {signal.match_id} @ {signal.price:.4f}",
                "payload": result,
            }
        )

    def state(self) -> dict:
        return {
            "running": self._running,
            "balance": self._simulator.balance,
            "positions": len(self._simulator.positions),
            "logs": len(self._simulator.logs),
            "db_errors": self._db_errors,
            "cache_errors": self._cache_errors,
            "external_stream_enabled": settings.external_stream_enabled,
            "external_stream_started": self._external_started,
        }

    def get_matches(self):
        rows = self._pipeline.get_matches() + list(self._external_matches.values())
        football_min = float(self._collector_settings["football_volume_threshold_k"]) * 1000
        basketball_min = float(self._collector_settings["basketball_volume_threshold_k"]) * 1000
        filtered = []
        for row in rows:
            if row.sport.value.lower() == "football" and row.moneyline_volume < football_min:
                continue
            if row.sport.value.lower() == "basketball" and row.moneyline_volume < basketball_min:
                continue
            filtered.append(row)
        return filtered

    def get_ticks(self, match_id: str | None = None, limit: int = 50):
        external = list(self._external_ticks)
        if match_id:
            external = [row for row in external if row["match_id"] == match_id]
        if match_id:
            internal = [self._tick_to_dict(tick) for tick in self._pipeline.get_sampled_ticks(match_id, limit=limit)]
            return (internal + external)[-limit:]
        rows: list[dict] = list(external)
        for match in self._pipeline.get_matches():
            rows.extend(self._tick_to_dict(tick) for tick in self._pipeline.get_sampled_ticks(match.match_id, limit=limit))
        return rows[-limit:]

    def get_accounts(self) -> list[dict]:
        return [
            {
                "id": "S001",
                "mode": "simulation",
                "strategy_name": "首分买入，回撤卖出",
                "retracement": 0.05,
                "total_assets": self._simulator.balance + sum(p.amount for p in self._simulator.positions),
                "available_cash": self._simulator.balance,
                "position_count": len(self._simulator.positions),
                "is_running": self._running,
            }
        ]

    def get_positions(self) -> list[dict]:
        latest_ticks = {tick["match_id"]: tick for tick in self.get_ticks(limit=200)}
        matches = {m.match_id: m for m in self._pipeline.get_matches()}
        rows: list[dict] = []
        for index, position in enumerate(self._simulator.positions):
            latest = latest_ticks.get(position.match_id)
            current_price = float(latest["bid"]) if latest else position.entry_price
            pnl = (current_price - position.entry_price) * (position.amount / max(position.entry_price, 0.000001))
            match = matches.get(position.match_id)
            rows.append(
                {
                    "id": f"P{index + 1:03d}",
                    "strategy_id": position.strategy_id,
                    "match_id": position.match_id,
                    "match_name": f"{match.team_home} vs {match.team_away}" if match else position.match_id,
                    "entry_price": position.entry_price,
                    "current_price": current_price,
                    "amount": position.amount,
                    "pnl": pnl,
                }
            )
        return rows

    def get_trades(self) -> list[dict]:
        rows: list[dict] = []
        for index, item in enumerate(self._simulator.logs):
            if item.get("status") != "filled":
                continue
            rows.append(
                {
                    "id": f"T{index + 1:03d}",
                    "action": item.get("action"),
                    "price": item.get("price"),
                    "amount": item.get("amount"),
                    "profit": item.get("profit", 0.0),
                }
            )
        return rows

    def get_logs(self, limit: int = 200) -> list[dict]:
        return self._event_logs[-limit:]

    def get_collector_settings(self) -> dict:
        return dict(self._collector_settings)

    def update_collector_settings(self, payload: dict) -> dict:
        self._collector_settings.update(payload)
        return self.get_collector_settings()

    async def next_market_event(self) -> dict:
        if settings.external_stream_enabled and not self._external_started:
            await self.start_external_connectors()
        if self._external_ticks:
            return {"topic": "market.tick", "payload": self._external_ticks[-1]}
        await self.step_once()
        ticks = self.get_ticks(limit=1)
        if not ticks:
            return {"topic": "market.tick", "payload": {}}
        return {"topic": "market.tick", "payload": ticks[-1]}

    @staticmethod
    def _tick_to_dict(tick: MarketTickEvent) -> dict:
        row = asdict(tick)
        row["ts_utc"] = tick.ts_utc.isoformat()
        return row

    def get_goalserve_detail(self, match_id: str) -> dict:
        detail = self._goalserve_details.get(match_id)
        if detail is not None:
            return detail
        match = next((m for m in self._pipeline.get_matches() if m.match_id == match_id), None)
        if match is None:
            return {
                "match_id": match_id,
                "updated_at": "",
                "lineups": [],
                "recent_form": [],
                "odds": {},
            }
        return {
            "match_id": match.match_id,
            "updated_at": match.latest_ts_utc.isoformat(),
            "lineups": [
                {"team": match.team_home, "players": ["Player A", "Player B", "Player C"]},
                {"team": match.team_away, "players": ["Player D", "Player E", "Player F"]},
            ],
            "recent_form": [
                {"team": match.team_home, "wins": 3, "draws": 1, "losses": 1},
                {"team": match.team_away, "wins": 2, "draws": 2, "losses": 1},
            ],
            "odds": {
                "home": 1.92,
                "away": 2.10,
            },
        }

    async def start_external_connectors(self) -> None:
        if self._external_started:
            return
        await self._external_service.start()
        self._external_started = True

    async def stop_external_connectors(self) -> None:
        if not self._external_started:
            return
        await self._external_service.stop()
        self._external_started = False

    async def _persist_tick(self, match: Any, tick: MarketTickEvent) -> None:
        match_payload = {
            "match_id": match.match_id,
            "sport": match.sport.value.lower(),
            "league": match.league,
            "team_home": match.team_home,
            "team_away": match.team_away,
            "start_time_utc": match.start_time_utc,
            "status": match.status.value.lower(),
        }
        tick_payload = {
            "match_id": tick.match_id,
            "ts_utc": tick.ts_utc,
            "source": tick.source,
            "outcome": tick.outcome,
            "bid": tick.bid,
            "ask": tick.ask,
            "volume": tick.volume,
            "extra": json.dumps({}),
        }
        cache_payload = {
            "ts_utc": tick.ts_utc.isoformat(),
            "source": tick.source,
            "outcome": tick.outcome,
            "bid": tick.bid,
            "ask": tick.ask,
            "volume": tick.volume,
        }
        try:
            await self._cache_writer.write_live_tick(match.match_id, cache_payload)
        except Exception:
            self._cache_errors += 1
        try:
            await self._repository.ensure_match(match_payload)
            await self._repository.insert_tick(tick_payload)
        except Exception:
            self._db_errors += 1

    async def _on_external_tick(self, tick: dict) -> None:
        self._external_ticks.append(tick)
        self._external_ticks = self._external_ticks[-5000:]
        match_id = tick["match_id"]
        if match_id not in self._external_matches:
            now = datetime.now(UTC)
            self._external_matches[match_id] = MatchCard(
                match_id=match_id,
                sport=SportType.football,
                league="Polymarket Live",
                team_home=f"Token {match_id[:6]}",
                team_away="Opposite",
                start_time_utc=now,
                status=MatchStatus.live,
                moneyline_volume=0.0,
                total_volume=0.0,
                latest_ts_utc=now,
            )
        match = self._external_matches[match_id]
        match.latest_ts_utc = datetime.fromisoformat(str(tick["ts_utc"]).replace("Z", "+00:00"))
        match.moneyline_volume = match.moneyline_volume + float(tick.get("volume", 0.0))
        match.total_volume = match.total_volume + float(tick.get("volume", 0.0))
        await self._cache_writer.write_live_tick(match_id, tick)
        await self._repository.ensure_match(
            {
                "match_id": match.match_id,
                "sport": match.sport.value.lower(),
                "league": match.league,
                "team_home": match.team_home,
                "team_away": match.team_away,
                "start_time_utc": match.start_time_utc,
                "status": match.status.value.lower(),
            }
        )
        await self._repository.insert_tick(
            {
                "match_id": tick["match_id"],
                "ts_utc": datetime.fromisoformat(str(tick["ts_utc"]).replace("Z", "+00:00")),
                "source": tick.get("source", "external"),
                "outcome": tick.get("outcome", "home"),
                "bid": tick.get("bid"),
                "ask": tick.get("ask"),
                "volume": tick.get("volume", 0.0),
                "extra": json.dumps({}),
            }
        )

    async def _on_goalserve_detail(self, detail: dict) -> None:
        match_id = detail.get("match_id")
        if isinstance(match_id, str) and match_id:
            self._goalserve_details[match_id] = detail

    async def _on_external_log(self, message: str) -> None:
        self._event_logs.append(
            {
                "ts_utc": datetime.now(UTC).isoformat(),
                "level": "Info",
                "message": message,
                "payload": {},
            }
        )
        self._event_logs = self._event_logs[-2000:]
