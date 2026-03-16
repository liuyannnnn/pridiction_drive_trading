import json
from typing import Any
from dataclasses import asdict
from datetime import UTC, datetime

from app.config import settings
from app.connectors.external_feed import (
    ExternalFeedService,
    _extract_market_token_ids,
    extract_market_external_ids,
    extract_market_final_score,
    extract_market_league,
    extract_market_outcome_map,
    extract_market_outcome_prices,
    extract_market_teams,
    extract_polymarket_total_volume,
    extract_polymarket_sport,
    extract_polymarket_start_time,
    extract_polymarket_volume,
    is_polymarket_moneyline_market,
)
from app.domain.events import MarketTickEvent
from app.execution.simulator import SimulationExecutor
from app.models import MatchCard, MatchStatus, SportType
from app.pipeline.market_pipeline import MarketPipeline
from app.storage.cache_writer import CacheWriter
from app.storage.repository import Repository
from app.strategy.registry import build_strategies


class TradingRuntime:
    def __init__(
        self,
        cache_writer: Any | None = None,
        repository: Any | None = None,
    ) -> None:
        self._running = False
        self._pipeline = MarketPipeline(sample_every=1)
        self._strategies = build_strategies(None)
        self._simulator = SimulationExecutor(initial_balance=10000.0)
        self._cache_writer = cache_writer or CacheWriter()
        self._repository = repository or Repository()
        self._cache_errors = 0
        self._db_errors = 0
        self._event_logs: list[dict] = []
        self._external_ticks: list[dict] = []
        self._external_matches: dict[str, MatchCard] = {}
        self._goalserve_details: dict[str, dict] = {}
        self._asset_market_map: dict[str, dict] = {}
        self._market_outcome_ticks: dict[str, dict[str, dict]] = {}
        self._last_live_snapshot_minute: dict[str, str] = {}
        self._external_service = ExternalFeedService(
            on_tick=self._on_external_tick,
            on_goalserve=self._on_goalserve_detail,
            on_log=self._on_external_log,
            on_markets=self._on_market_universe,
            get_collector_settings=self.get_collector_settings,
        )
        self._external_started = False
        self._collector_settings = {
            "collection_interval_minutes": 5,
            "football_volume_threshold_k": 50,
            "basketball_volume_threshold_k": 100,
        }

    @property
    def repository(self) -> Repository:
        return self._repository

    async def start_simulation(
        self,
        initial_balance: float,
        retracement: float,
        strategy_configs: list[dict] | None = None,
    ) -> dict:
        self._simulator = SimulationExecutor(initial_balance=initial_balance)
        if strategy_configs:
            self._strategies = build_strategies(strategy_configs)
        else:
            self._strategies = build_strategies(
                [
                    {
                        "name": "retracement",
                        "strategy_id": "S001",
                        "retracement": retracement,
                    }
                ]
            )
        self._running = True
        await self.step_once()
        return self.state()

    def stop_simulation(self) -> dict:
        self._running = False
        return {"running": self._running}

    async def step_once(self) -> list[tuple[MatchCard, MarketTickEvent]]:
        produced: list[tuple[MatchCard, MarketTickEvent]] = []
        await self._pipeline.run_step()
        for match in self._pipeline.get_matches():
            ticks = self._pipeline.get_sampled_ticks(match.match_id, limit=1)
            if not ticks:
                continue
            tick = ticks[-1]
            produced.append((match, tick))
            await self._persist_tick(match=match, tick=tick)
            if self._running:
                await self._handle_tick(tick)
        return produced

    async def _handle_tick(self, tick: MarketTickEvent) -> None:
        for strategy in self._strategies:
            signal = strategy.on_tick(tick)
            if signal is None:
                continue
            result = self._simulator.execute(
                strategy_id=signal.strategy_id,
                action=signal.action,
                match_id=signal.match_id,
                outcome=signal.outcome,
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
            "strategy_ids": [item.strategy_id for item in self._strategies],
        }

    def get_matches(self):
        if settings.external_stream_enabled:
            rows = list(self._external_matches.values())
        else:
            rows = self._pipeline.get_matches() + list(self._external_matches.values())
        football_min = float(self._collector_settings["football_volume_threshold_k"]) * 1000
        basketball_min = float(self._collector_settings["basketball_volume_threshold_k"]) * 1000
        filtered = []
        for row in rows:
            if row.sport.value.lower() == "football" and row.total_volume < football_min:
                continue
            if row.sport.value.lower() == "basketball" and row.total_volume < basketball_min:
                continue
            filtered.append(row)
        return filtered

    def get_ticks(self, match_id: str | None = None, limit: int = 50):
        external = list(self._external_ticks)
        if match_id:
            external = [row for row in external if row["match_id"] == match_id]
        if settings.external_stream_enabled:
            return external[-limit:]
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
        if settings.external_stream_enabled:
            if not self._external_started:
                await self.start_external_connectors()
            if self._external_ticks:
                return {"topic": "market.tick", "payload": self._external_ticks[-1]}
            return {"topic": "market.tick", "payload": {}}
        await self.step_once()
        ticks = self.get_ticks(limit=1)
        if not ticks:
            return {"topic": "market.tick", "payload": {}}
        return {"topic": "market.tick", "payload": ticks[-1]}

    @staticmethod
    def _tick_to_dict(tick: MarketTickEvent) -> dict:
        row = asdict(tick)
        row["ts_utc"] = tick.ts_utc.isoformat()
        if tick.start_time_utc is not None:
            row["start_time_utc"] = tick.start_time_utc.isoformat()
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
        try:
            stored = await self._repository.get_collector_settings()
        except Exception:
            stored = None
        if stored is not None:
            self.update_collector_settings(stored)
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
            "moneyline_volume": float(match.moneyline_volume),
            "total_volume": float(match.total_volume),
            "latest_ts_utc": match.latest_ts_utc,
            "external_event_id": match.external_event_id,
            "external_event_slug": match.external_event_slug,
            "external_market_id": match.external_market_id,
            "external_market_slug": match.external_market_slug,
            "score_home": match.score_home,
            "score_away": match.score_away,
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

    async def _on_market_universe(self, markets: list[dict]) -> None:
        now = datetime.now(UTC)
        latest: dict[str, MatchCard] = {}
        next_asset_map: dict[str, dict] = {}
        event_prices: dict[str, dict[str, float]] = {}
        max_market_volumes: dict[str, float] = {}
        moneyline_volumes: dict[str, float] = {}
        for market in markets:
            sport_name = extract_polymarket_sport(market)
            start_time = extract_polymarket_start_time(market)
            teams = extract_market_teams(market)
            if sport_name is None or start_time is None or teams is None:
                continue
            sport = SportType.football if sport_name == "football" else SportType.basketball
            home, away = teams
            status = MatchStatus.live if start_time <= now else MatchStatus.pre
            market_volume = extract_polymarket_volume(market)
            total_volume = extract_polymarket_total_volume(market)
            ids = extract_market_external_ids(market)
            event_id = ids["external_event_id"]
            market_id = ids["external_market_id"]
            if not event_id and not market_id:
                token_ids = _extract_market_token_ids(market)
                if not token_ids:
                    continue
                market_id = token_ids[0]
            match_id = event_id or market_id
            max_market_volumes[match_id] = max(max_market_volumes.get(match_id, 0.0), market_volume)
            if is_polymarket_moneyline_market(market):
                moneyline_volumes[match_id] = max(moneyline_volumes.get(match_id, 0.0), market_volume)
            score_home, score_away = extract_market_final_score(market)
            league = extract_market_league(market, sport_name)
            match = latest.get(match_id)
            if match is None:
                latest[match_id] = MatchCard(
                    match_id=match_id,
                    sport=sport,
                    league=league,
                    team_home=home,
                    team_away=away,
                    start_time_utc=start_time,
                    status=status,
                    moneyline_volume=0.0,
                    total_volume=total_volume,
                    latest_ts_utc=now,
                    score_home=score_home,
                    score_away=score_away,
                    external_event_id=ids["external_event_id"],
                    external_event_slug=ids["external_event_slug"],
                    external_market_id=ids["external_market_id"],
                    external_market_slug=ids["external_market_slug"],
                )
            else:
                match.start_time_utc = start_time
                match.status = status
                match.total_volume = max(match.total_volume, total_volume)
                match.latest_ts_utc = now
                if match.score_home is None and score_home is not None:
                    match.score_home = score_home
                if match.score_away is None and score_away is not None:
                    match.score_away = score_away
                if not match.external_market_id and ids["external_market_id"]:
                    match.external_market_id = ids["external_market_id"]
                if not match.external_market_slug and ids["external_market_slug"]:
                    match.external_market_slug = ids["external_market_slug"]
            target = latest[match_id]
            price_map = event_prices.setdefault(match_id, {})
            price_map.update(extract_market_outcome_prices(market))
            side = self._map_group_item_to_outcome(
                str(market.get("groupItemTitle") or ""),
                target.team_home,
                target.team_away,
            )
            yes_price = self._extract_yes_price(market)
            if side is not None and yes_price is not None:
                price_map[side] = yes_price
            outcome_map = extract_market_outcome_map(market)
            yes_token = self._extract_yes_token_id(market)
            for token_id, outcome in outcome_map.items():
                mapped_outcome = outcome
                if yes_token is not None and token_id == yes_token and side is not None:
                    mapped_outcome = side
                elif yes_token is not None and token_id != yes_token:
                    continue
                if mapped_outcome not in {"home", "away", "draw"}:
                    continue
                next_asset_map[token_id] = {
                    "match_id": match_id,
                    "outcome": mapped_outcome,
                    "outcome_prices": price_map,
                }
        for match_id, match in latest.items():
            fallback_moneyline = max_market_volumes.get(match_id, 0.0)
            match.moneyline_volume = moneyline_volumes.get(match_id, fallback_moneyline)
            match.total_volume = max(match.total_volume, fallback_moneyline, match.moneyline_volume)
        self._external_matches = latest
        self._asset_market_map = next_asset_map
        for match_id, match in latest.items():
            await self._repository.ensure_match(
                {
                    "match_id": match.match_id,
                    "sport": match.sport.value.lower(),
                    "league": match.league,
                    "team_home": match.team_home,
                    "team_away": match.team_away,
                    "start_time_utc": match.start_time_utc,
                    "status": match.status.value.lower(),
                    "moneyline_volume": match.moneyline_volume,
                    "total_volume": match.total_volume,
                    "latest_ts_utc": match.latest_ts_utc,
                    "external_event_id": match.external_event_id,
                    "external_event_slug": match.external_event_slug,
                    "external_market_id": match.external_market_id,
                    "external_market_slug": match.external_market_slug,
                    "score_home": match.score_home,
                    "score_away": match.score_away,
                }
            )
            if match.status == MatchStatus.pre:
                await self._repository.insert_market_snapshot(
                    self._build_snapshot_payload(
                        match=match,
                        snapshot_ts=now,
                        source="polymarket",
                        ingest_type="pre",
                        outcome_prices=event_prices.get(match_id, {}),
                        outcome_ticks=self._market_outcome_ticks.get(match_id, {}),
                    )
                )

    @staticmethod
    def _extract_yes_token_id(market: dict) -> str | None:
        outcomes_raw = market.get("outcomes")
        token_ids = _extract_market_token_ids(market)
        outcomes: list[str] = []
        if isinstance(outcomes_raw, str):
            try:
                parsed = json.loads(outcomes_raw)
                if isinstance(parsed, list):
                    outcomes = [str(item) for item in parsed]
            except Exception:
                return None
        elif isinstance(outcomes_raw, list):
            outcomes = [str(item) for item in outcomes_raw]
        for index, label in enumerate(outcomes):
            if index >= len(token_ids):
                break
            if label.strip().lower() == "yes":
                return token_ids[index]
        return None

    @staticmethod
    def _extract_yes_price(market: dict) -> float | None:
        outcomes_raw = market.get("outcomes")
        prices_raw = market.get("outcomePrices")
        outcomes: list[str] = []
        prices: list[float] = []
        if isinstance(outcomes_raw, str):
            try:
                parsed = json.loads(outcomes_raw)
                if isinstance(parsed, list):
                    outcomes = [str(item) for item in parsed]
            except Exception:
                outcomes = []
        elif isinstance(outcomes_raw, list):
            outcomes = [str(item) for item in outcomes_raw]
        if isinstance(prices_raw, str):
            try:
                parsed = json.loads(prices_raw)
                if isinstance(parsed, list):
                    prices = [float(item) for item in parsed]
            except Exception:
                prices = []
        elif isinstance(prices_raw, list):
            for item in prices_raw:
                try:
                    prices.append(float(item))
                except Exception:
                    prices.append(0.0)
        for index, label in enumerate(outcomes):
            if index >= len(prices):
                break
            if label.strip().lower() == "yes":
                return prices[index]
        return None

    @staticmethod
    def _map_group_item_to_outcome(group_item: str, home: str, away: str) -> str | None:
        text = group_item.strip().lower()
        if not text:
            return None
        if "draw" in text:
            return "draw"
        if home and home.lower() in text:
            return "home"
        if away and away.lower() in text:
            return "away"
        return None

    async def _on_external_tick(self, tick: dict) -> None:
        asset_id = str(tick["match_id"])
        meta = self._asset_market_map.get(asset_id)
        if meta is None:
            return
        match_id = str(meta["match_id"])
        outcome = str(meta["outcome"])
        match = self._external_matches.get(match_id)
        if match is None:
            return
        ts = datetime.fromisoformat(str(tick["ts_utc"]).replace("Z", "+00:00"))
        outcome_ticks = self._market_outcome_ticks.setdefault(match_id, {})
        outcome_ticks[outcome] = {
            "bid": tick.get("bid"),
            "ask": tick.get("ask"),
            "ts_utc": tick.get("ts_utc"),
        }
        cache_tick = {
            "match_id": match_id,
            "asset_id": asset_id,
            "outcome": outcome,
            "ts_utc": tick.get("ts_utc"),
            "source": tick.get("source", "external"),
            "bid": tick.get("bid"),
            "ask": tick.get("ask"),
            "volume": tick.get("volume", 0.0),
        }
        self._external_ticks.append(cache_tick)
        self._external_ticks = self._external_ticks[-5000:]
        match.latest_ts_utc = ts
        if match.status != MatchStatus.live:
            match.status = MatchStatus.live
        await self._cache_writer.write_live_tick(match_id, cache_tick)
        if match.status == MatchStatus.live:
            minute_bucket = ts.strftime("%Y-%m-%dT%H:%M")
            if self._last_live_snapshot_minute.get(match_id) != minute_bucket:
                self._last_live_snapshot_minute[match_id] = minute_bucket
                await self._repository.ensure_match(
                    {
                        "match_id": match.match_id,
                        "sport": match.sport.value.lower(),
                        "league": match.league,
                        "team_home": match.team_home,
                        "team_away": match.team_away,
                        "start_time_utc": match.start_time_utc,
                        "status": match.status.value.lower(),
                        "moneyline_volume": match.moneyline_volume,
                        "total_volume": match.total_volume,
                        "latest_ts_utc": match.latest_ts_utc,
                        "external_event_id": match.external_event_id,
                        "external_event_slug": match.external_event_slug,
                        "external_market_id": match.external_market_id,
                        "external_market_slug": match.external_market_slug,
                        "score_home": match.score_home,
                        "score_away": match.score_away,
                    }
                )
                await self._repository.insert_market_snapshot(
                    self._build_snapshot_payload(
                        match=match,
                        snapshot_ts=ts,
                        source="polymarket",
                        ingest_type="live_resampled",
                        outcome_prices=meta.get("outcome_prices", {}),
                        outcome_ticks=outcome_ticks,
                    )
                )

    @staticmethod
    def _build_snapshot_payload(
        match: MatchCard,
        snapshot_ts: datetime,
        source: str,
        ingest_type: str,
        outcome_prices: dict,
        outcome_ticks: dict,
    ) -> dict:
        home_tick = outcome_ticks.get("home", {})
        away_tick = outcome_ticks.get("away", {})
        draw_tick = outcome_ticks.get("draw", {})
        return {
            "match_id": match.match_id,
            "snapshot_ts_utc": snapshot_ts,
            "source": source,
            "sport": match.sport.value.lower(),
            "status": match.status.value.lower(),
            "start_time_utc": match.start_time_utc,
            "team_home": match.team_home,
            "team_away": match.team_away,
            "external_event_id": match.external_event_id,
            "external_event_slug": match.external_event_slug,
            "external_market_id": match.external_market_id,
            "external_market_slug": match.external_market_slug,
            "score_home": match.score_home,
            "score_away": match.score_away,
            "home_bid": home_tick.get("bid"),
            "home_ask": home_tick.get("ask"),
            "home_price": outcome_prices.get("home"),
            "away_bid": away_tick.get("bid"),
            "away_ask": away_tick.get("ask"),
            "away_price": outcome_prices.get("away"),
            "draw_bid": draw_tick.get("bid"),
            "draw_ask": draw_tick.get("ask"),
            "draw_price": outcome_prices.get("draw"),
            "moneyline_volume": match.moneyline_volume,
            "total_volume": match.total_volume,
            "ingest_type": ingest_type,
            "extra": {},
        }

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
