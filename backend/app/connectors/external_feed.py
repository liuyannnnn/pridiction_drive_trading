import asyncio
import json
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta

import httpx
import websockets

from app.config import settings


TickHandler = Callable[[dict], Awaitable[None]]
LogHandler = Callable[[str], Awaitable[None]]
GoalserveHandler = Callable[[dict], Awaitable[None]]
CollectorSettingsProvider = Callable[[], dict]
MarketUniverseHandler = Callable[[list[dict]], Awaitable[None]]


def extract_goalserve_token(payload: dict) -> str | None:
    if "token" in payload and isinstance(payload["token"], str):
        return payload["token"]
    if "access_token" in payload and isinstance(payload["access_token"], str):
        return payload["access_token"]
    data = payload.get("data")
    if isinstance(data, dict) and isinstance(data.get("token"), str):
        return data["token"]
    return None


def build_goalserve_token_attempts(
    token_url: str,
    token_method: str,
    api_key: str,
    username: str,
    password: str,
) -> list[dict]:
    body = {
        "apiKey": api_key,
        "api_key": api_key,
        "username": username,
        "password": password,
    }
    if "{" in token_url:
        return [
            {
                "method": "get_template",
                "url": token_url.format(
                    api_key=api_key,
                    username=username,
                    password=password,
                ),
            }
        ]
    method = token_method.strip().lower()
    if method == "post_json":
        return [{"method": "post_json", "url": token_url, "json": body}]
    if method == "post_form":
        return [{"method": "post_form", "url": token_url, "data": body}]
    if method == "get_query":
        return [{"method": "get_query", "url": token_url, "params": body}]
    return [
        {"method": "post_json", "url": token_url, "json": body},
        {"method": "post_form", "url": token_url, "data": body},
        {"method": "get_query", "url": token_url, "params": body},
    ]


def render_goalserve_subscribe_payload(template: str, token: str) -> str:
    return template.replace("{token}", token)


def compute_goalserve_refresh_deadline(
    issued_at: datetime,
    ttl_minutes: int,
    refresh_ahead_seconds: int,
) -> datetime:
    safe_ttl = max(1, ttl_minutes)
    safe_ahead = max(0, refresh_ahead_seconds)
    return issued_at + timedelta(minutes=safe_ttl, seconds=-safe_ahead)


def parse_polymarket_message_to_tick(message: dict) -> dict | None:
    event_type = message.get("event_type")
    if event_type == "best_bid_ask":
        asset_id = message.get("asset_id")
        best_bid = message.get("best_bid")
        best_ask = message.get("best_ask")
        if asset_id is None or best_bid is None or best_ask is None:
            return None
        ts = _to_iso(message.get("timestamp"))
        return {
            "match_id": str(asset_id),
            "ts_utc": ts,
            "source": "polymarket",
            "outcome": "home",
            "bid": float(best_bid),
            "ask": float(best_ask),
            "volume": 0.0,
        }
    if event_type == "price_change":
        rows = message.get("price_changes")
        if not isinstance(rows, list) or len(rows) == 0:
            return None
        row = rows[0]
        asset_id = row.get("asset_id")
        best_bid = row.get("best_bid")
        best_ask = row.get("best_ask")
        if asset_id is None or best_bid is None or best_ask is None:
            return None
        ts = _to_iso(message.get("timestamp"))
        return {
            "match_id": str(asset_id),
            "ts_utc": ts,
            "source": "polymarket",
            "outcome": "home",
            "bid": float(best_bid),
            "ask": float(best_ask),
            "volume": 0.0,
        }
    return None


def parse_goalserve_message_to_detail(payload: dict) -> dict | None:
    events = payload.get("events")
    if not isinstance(events, dict):
        return None
    first = next(iter(events.values()), None)
    if not isinstance(first, dict):
        return None
    info = first.get("info", {})
    if not isinstance(info, dict):
        return None
    name = str(info.get("name", ""))
    teams = name.split(" vs ")
    home = teams[0] if len(teams) > 0 else "Home"
    away = teams[1] if len(teams) > 1 else "Away"
    return {
        "match_id": str(info.get("id", "")),
        "updated_at": _to_iso(payload.get("updated_ts")),
        "lineups": [
            {"team": home, "players": []},
            {"team": away, "players": []},
        ],
        "recent_form": [],
        "odds": {},
    }


class PolymarketMarketWsConnector:
    def __init__(
        self,
        on_tick: TickHandler,
        on_log: LogHandler,
        on_markets: MarketUniverseHandler | None = None,
        get_collector_settings: CollectorSettingsProvider | None = None,
    ) -> None:
        self._on_tick = on_tick
        self._on_log = on_log
        self._on_markets = on_markets
        self._get_collector_settings = get_collector_settings

    async def run(self, stop_event: asyncio.Event) -> None:
        assets: list[str] = []
        markets: list[dict] = []
        refresh_deadline: datetime | None = None
        while not stop_event.is_set():
            collector_settings = self._get_collector_settings() if self._get_collector_settings else {}
            refresh_minutes = max(1, int(collector_settings.get("collection_interval_minutes", 5)))
            now = datetime.now(UTC)
            should_refresh = refresh_deadline is None or now >= refresh_deadline or len(assets) == 0
            try:
                if should_refresh:
                    assets, markets = await self._fetch_asset_ids(collector_settings)
                    refresh_deadline = datetime.now(UTC) + timedelta(minutes=refresh_minutes)
                    if len(assets) == 0:
                        await self._on_log("polymarket: no assets found")
                        await asyncio.sleep(self._seconds_until_deadline(refresh_deadline, fallback=10))
                        continue
                    if self._on_markets is not None:
                        await self._on_markets(markets)
                async with websockets.connect(
                    settings.polymarket_ws_url,
                    ping_interval=10,
                    ping_timeout=20,
                    proxy=None,
                ) as ws:
                    await ws.send(
                        json.dumps(
                            {
                                "assets_ids": assets,
                                "type": "market",
                                "custom_feature_enabled": settings.polymarket_ws_custom_feature_enabled,
                            }
                        )
                    )
                    await self._on_log(f"polymarket: subscribed assets={len(assets)}")
                    while not stop_event.is_set():
                        if refresh_deadline is not None and datetime.now(UTC) >= refresh_deadline:
                            await self._on_log("polymarket: refresh market universe")
                            break
                        raw = await asyncio.wait_for(ws.recv(), timeout=30)
                        message = json.loads(raw)
                        tick = parse_polymarket_message_to_tick(message)
                        if tick is not None:
                            await self._on_tick(tick)
            except Exception as exc:
                await self._on_log(f"polymarket: reconnect reason={exc}")
                await asyncio.sleep(self._seconds_until_deadline(refresh_deadline, fallback=3, maximum=3))

    @staticmethod
    def _seconds_until_deadline(
        refresh_deadline: datetime | None,
        fallback: int,
        maximum: int | None = None,
    ) -> float:
        if refresh_deadline is None:
            return float(fallback)
        remaining = max(0.0, (refresh_deadline - datetime.now(UTC)).total_seconds())
        if remaining == 0:
            return 0.0
        if maximum is not None:
            return min(float(maximum), remaining)
        return remaining

    async def _fetch_asset_ids(self, collector_settings: dict) -> tuple[list[str], list[dict]]:
        sports_url = f"{settings.polymarket_gamma_url}/sports"
        events_url = f"{settings.polymarket_gamma_url}/events"
        markets_url = f"{settings.polymarket_gamma_url}/markets"
        markets_params = {"active": "true", "closed": "false", "limit": "1000"}
        async with httpx.AsyncClient(timeout=20) as client:
            sports_response = await client.get(sports_url)
            sports_response.raise_for_status()
            sports_rows = sports_response.json()
            tag_ids = build_sport_tag_ids(sports_rows if isinstance(sports_rows, list) else [])
            events_acc: list[dict] = []
            seen_ids: set[str] = set()
            tasks = [
                client.get(
                    events_url,
                    params={"tag_id": str(tag_id), "active": "true", "closed": "false", "limit": "200"},
                )
                for tag_id in tag_ids[:16]
            ]
            responses = await asyncio.gather(*tasks, return_exceptions=True)
            for response in responses:
                if isinstance(response, Exception):
                    continue
                if response.status_code >= 400:
                    continue
                batch = response.json()
                if not isinstance(batch, list):
                    continue
                for event in batch:
                    if not isinstance(event, dict):
                        continue
                    event_id = str(event.get("id", ""))
                    if not event_id or event_id in seen_ids:
                        continue
                    seen_ids.add(event_id)
                    events_acc.append(event)
            rows = flatten_event_markets(events_acc)
            if not rows:
                markets_response = await client.get(markets_url, params=markets_params)
                markets_response.raise_for_status()
                market_rows = markets_response.json()
                rows = market_rows if isinstance(market_rows, list) else []
        selected_rows = select_polymarket_markets(
            rows=rows,
            collector_settings=collector_settings,
            now=datetime.now(UTC),
        )
        return (
            select_polymarket_asset_ids(
                rows=selected_rows,
                max_assets=settings.polymarket_ws_max_assets,
            ),
            selected_rows,
        )


class GoalserveWsConnector:
    def __init__(self, on_goalserve: GoalserveHandler, on_log: LogHandler) -> None:
        self._on_goalserve = on_goalserve
        self._on_log = on_log

    async def run(self, stop_event: asyncio.Event) -> None:
        while not stop_event.is_set():
            try:
                token, refresh_deadline = await self._fetch_token()
                if token is None:
                    await self._on_log("goalserve: token missing")
                    await asyncio.sleep(10)
                    continue
                ws_url = settings.goalserve_ws_url.format(token=token)
                async with websockets.connect(
                    ws_url,
                    ping_interval=20,
                    ping_timeout=20,
                    proxy=None,
                ) as ws:
                    if settings.goalserve_subscribe_payload.strip():
                        payload = render_goalserve_subscribe_payload(
                            settings.goalserve_subscribe_payload.strip(),
                            token=token,
                        )
                        await ws.send(payload)
                    await self._on_log("goalserve: subscribed")
                    while not stop_event.is_set():
                        if datetime.now(UTC) >= refresh_deadline:
                            await self._on_log("goalserve: token nearing expiry, reconnect for refresh")
                            break
                        wait_seconds = max(1.0, min(30.0, (refresh_deadline - datetime.now(UTC)).total_seconds()))
                        try:
                            raw = await asyncio.wait_for(ws.recv(), timeout=wait_seconds)
                        except asyncio.TimeoutError:
                            continue
                        payload = json.loads(raw)
                        detail = parse_goalserve_message_to_detail(payload)
                        if detail is not None:
                            await self._on_goalserve(detail)
            except Exception as exc:
                await self._on_log(f"goalserve: reconnect reason={exc}")
                await asyncio.sleep(3)

    async def _fetch_token(self) -> tuple[str | None, datetime]:
        if not settings.goalserve_token_url:
            return None, datetime.now(UTC)
        attempts = build_goalserve_token_attempts(
            token_url=settings.goalserve_token_url,
            token_method=settings.goalserve_token_method,
            api_key=settings.goalserve_api_key,
            username=settings.goalserve_username,
            password=settings.goalserve_password,
        )
        async with httpx.AsyncClient(timeout=20) as client:
            for index, attempt in enumerate(attempts):
                try:
                    if attempt["method"] in {"get_template", "get_query"}:
                        response = await client.get(
                            attempt["url"],
                            params=attempt.get("params"),
                        )
                    elif attempt["method"] == "post_form":
                        response = await client.post(
                            attempt["url"],
                            data=attempt.get("data"),
                        )
                    else:
                        response = await client.post(
                            attempt["url"],
                            json=attempt.get("json"),
                        )
                    response.raise_for_status()
                    payload = response.json()
                    token = extract_goalserve_token(payload)
                    if token:
                        ttl_minutes = settings.goalserve_token_ttl_minutes
                        deadline = compute_goalserve_refresh_deadline(
                            issued_at=datetime.now(UTC),
                            ttl_minutes=ttl_minutes,
                            refresh_ahead_seconds=settings.goalserve_token_refresh_ahead_seconds,
                        )
                        return token, deadline
                    await self._on_log(f"goalserve: token field missing on attempt={index + 1}")
                except Exception as exc:
                    await self._on_log(f"goalserve: token request failed attempt={index + 1} reason={exc}")
        return None, datetime.now(UTC)


class ExternalFeedService:
    def __init__(
        self,
        on_tick: TickHandler,
        on_goalserve: GoalserveHandler,
        on_log: LogHandler,
        on_markets: MarketUniverseHandler | None = None,
        get_collector_settings: CollectorSettingsProvider | None = None,
    ) -> None:
        self._on_tick = on_tick
        self._on_goalserve = on_goalserve
        self._on_log = on_log
        self._on_markets = on_markets
        self._get_collector_settings = get_collector_settings
        self._stop_event = asyncio.Event()
        self._tasks: list[asyncio.Task] = []

    async def start(self) -> None:
        if self._tasks:
            return
        self._stop_event = asyncio.Event()
        if settings.polymarket_ws_enabled:
            connector = PolymarketMarketWsConnector(
                on_tick=self._on_tick,
                on_log=self._on_log,
                on_markets=self._on_markets,
                get_collector_settings=self._get_collector_settings,
            )
            self._tasks.append(asyncio.create_task(connector.run(self._stop_event)))
        if settings.goalserve_ws_enabled:
            connector = GoalserveWsConnector(on_goalserve=self._on_goalserve, on_log=self._on_log)
            self._tasks.append(asyncio.create_task(connector.run(self._stop_event)))

    async def stop(self) -> None:
        if not self._tasks:
            return
        self._stop_event.set()
        for task in self._tasks:
            task.cancel()
        self._tasks = []


def _extract_market_token_ids(row: dict) -> list[str]:
    ids: list[str] = []
    clob_token_ids = row.get("clobTokenIds")
    if isinstance(clob_token_ids, str):
        try:
            parsed = json.loads(clob_token_ids)
            if isinstance(parsed, list):
                ids.extend(str(item) for item in parsed if item is not None)
        except Exception:
            pass
    tokens = row.get("tokens")
    if isinstance(tokens, list):
        for item in tokens:
            if isinstance(item, dict):
                token_id = item.get("token_id") or item.get("tokenId")
                if token_id is not None:
                    ids.append(str(token_id))
    return ids


def extract_market_outcome_map(row: dict) -> dict[str, str]:
    token_ids = _extract_market_token_ids(row)
    outcomes = _extract_market_outcomes(row)
    mapped: dict[str, str] = {}
    for index, token_id in enumerate(token_ids):
        label = outcomes[index] if index < len(outcomes) else ""
        text = label.lower()
        if "draw" in text or "tie" in text:
            mapped[token_id] = "draw"
        elif any(key in text for key in ("away", "visitor", "team b", "no")):
            mapped[token_id] = "away"
        else:
            mapped[token_id] = "home"
    return mapped


def extract_market_outcome_prices(row: dict) -> dict[str, float]:
    prices_raw = row.get("outcomePrices")
    outcomes = _extract_market_outcomes(row)
    prices: list[float] = []
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
    mapped: dict[str, float] = {}
    for index, label in enumerate(outcomes):
        if index >= len(prices):
            continue
        text = label.lower()
        if "draw" in text or "tie" in text:
            mapped["draw"] = prices[index]
        elif any(key in text for key in ("away", "visitor", "team b", "no")):
            mapped["away"] = prices[index]
        else:
            mapped["home"] = prices[index]
    return mapped


def _extract_market_outcomes(row: dict) -> list[str]:
    outcomes_raw = row.get("outcomes")
    if isinstance(outcomes_raw, str):
        try:
            parsed = json.loads(outcomes_raw)
            if isinstance(parsed, list):
                return [str(item) for item in parsed]
        except Exception:
            return []
    if isinstance(outcomes_raw, list):
        return [str(item) for item in outcomes_raw]
    return []


def extract_market_external_ids(row: dict) -> dict[str, str]:
    event = _extract_first_event(row)
    return {
        "external_event_id": str(event.get("id") or ""),
        "external_event_slug": str(event.get("slug") or row.get("parentEventSlug") or ""),
        "external_market_id": str(row.get("id") or ""),
        "external_market_slug": str(row.get("slug") or ""),
    }


def extract_market_teams(row: dict) -> tuple[str, str] | None:
    event = _extract_first_event(row)
    event_title = str(event.get("title") or row.get("parentEventTitle") or "").strip()
    parsed = _split_teams_from_text(event_title)
    if parsed is not None:
        return parsed
    question = str(row.get("question") or "")
    parsed = _extract_teams_from_question_rules(question)
    if parsed is not None:
        return parsed
    for text in (question, str(row.get("title") or ""), str(row.get("description") or "")):
        parsed = _split_teams_from_text(text)
        if parsed is not None:
            return parsed
    slug = str(event.get("slug") or row.get("parentEventSlug") or "").strip()
    parsed = _extract_teams_from_slug(slug)
    if parsed is not None:
        return parsed
    return None


def extract_market_league(row: dict, sport: str) -> str:
    event = _extract_first_event(row)
    slug = str(event.get("slug") or row.get("parentEventSlug") or "").lower()
    map_items = [
        ("epl", "Premier League"),
        ("lal", "La Liga"),
        ("bun", "Bundesliga"),
        ("fl1", "Ligue 1"),
        ("itc", "Serie A"),
        ("mls", "MLS"),
        ("nba", "NBA"),
        ("wnba", "WNBA"),
        ("ncaab", "NCAA"),
        ("ncaaw", "NCAA"),
    ]
    for key, league in map_items:
        if slug.startswith(f"{key}-") or f"-{key}-" in slug:
            return league
    category = str(event.get("category") or row.get("parentEventCategory") or "").strip()
    if category:
        return category
    return "Football" if sport == "football" else "Basketball"


def extract_market_final_score(row: dict) -> tuple[int | None, int | None]:
    event = _extract_first_event(row)
    for text in (
        str(event.get("title") or ""),
        str(row.get("question") or ""),
        str(row.get("description") or ""),
    ):
        score = _extract_score_from_text(text)
        if score is not None:
            return score
    return (None, None)


def extract_polymarket_sport(row: dict) -> str | None:
    candidates: list[str] = []
    for key in (
        "sport",
        "sports",
        "category",
        "groupItemTitle",
        "subTitle",
        "title",
        "question",
        "parentEventSlug",
        "parentEventTitle",
        "parentEventCategory",
    ):
        value = row.get(key)
        if isinstance(value, str):
            candidates.append(value.lower())
        if isinstance(value, list):
            for item in value:
                if isinstance(item, str):
                    candidates.append(item.lower())
                if isinstance(item, dict):
                    for sub_key in ("label", "slug", "name"):
                        sub_val = item.get(sub_key)
                        if isinstance(sub_val, str):
                            candidates.append(sub_val.lower())
    events = row.get("events")
    if isinstance(events, list):
        for event in events[:3]:
            if isinstance(event, dict):
                for key in ("category", "subcategory", "title", "slug"):
                    value = event.get(key)
                    if isinstance(value, str):
                        candidates.append(value.lower())
    text = " ".join(candidates)
    if any(token in text for token in ("football", "soccer", "premier league", "la liga", "champions league")):
        return "football"
    if any(token in text for token in ("basketball", "nba", "wnba", "ncaa")):
        return "basketball"
    return None


def extract_polymarket_start_time(row: dict) -> datetime | None:
    # Sports events often use endDate as the market close / game start,
    # while startDate may reflect event creation time.
    for key in ("gameStartTime", "startTime", "endDate", "endDateIso", "startDateIso", "startDate"):
        value = row.get(key)
        ts = _parse_datetime(value)
        if ts is not None:
            return ts
    events = row.get("events")
    if isinstance(events, list):
        for event in events[:3]:
            if not isinstance(event, dict):
                continue
            for key in ("gameStartTime", "startTime", "endDate", "endDateIso", "startDateIso", "startDate"):
                value = event.get(key)
                ts = _parse_datetime(value)
                if ts is not None:
                    return ts
    return None


def extract_polymarket_volume(row: dict) -> float:
    for key in ("volumeNum", "volume", "volumeClob", "liquidityNum", "liquidity"):
        value = row.get(key)
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            try:
                return float(value)
            except Exception:
                continue
    return 0.0


def extract_polymarket_total_volume(row: dict) -> float:
    event = _extract_first_event(row)
    for key in ("volume", "volumeNum", "volumeClob", "liquidityNum", "liquidity"):
        value = event.get(key)
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            try:
                return float(value)
            except Exception:
                continue
    return extract_polymarket_volume(row)


def is_polymarket_moneyline_market(row: dict) -> bool:
    for key in ("groupItemTitle", "title", "question", "slug"):
        value = row.get(key)
        if isinstance(value, str) and "moneyline" in value.lower():
            return True
    outcomes = [item.strip().lower() for item in _extract_market_outcomes(row)]
    if not outcomes:
        return False
    if any(item in {"yes", "no"} for item in outcomes):
        return False
    teams = extract_market_teams(row)
    if teams is None:
        return False
    home, away = teams
    home_low = home.lower()
    away_low = away.lower()
    has_home = any(home_low in item or item in {"home", "team a"} for item in outcomes)
    has_away = any(away_low in item or item in {"away", "visitor", "team b"} for item in outcomes)
    has_draw = any("draw" in item or "tie" in item for item in outcomes)
    return has_home and has_away and (has_draw or len(outcomes) == 2)


def select_polymarket_markets(
    rows: list[dict],
    collector_settings: dict,
    now: datetime,
) -> list[dict]:
    football_min = float(collector_settings.get("football_volume_threshold_k", 50)) * 1000
    basketball_min = float(collector_settings.get("basketball_volume_threshold_k", 100)) * 1000
    horizon = now + timedelta(hours=24)
    selected: list[dict] = []
    for row in rows:
        sport = extract_polymarket_sport(row)
        if sport not in {"football", "basketball"}:
            continue
        start_time = extract_polymarket_start_time(row)
        if start_time is None or start_time.tzinfo is None:
            continue
        if not (now <= start_time <= horizon):
            continue
        total_volume = extract_polymarket_total_volume(row)
        if sport == "football" and total_volume < football_min:
            continue
        if sport == "basketball" and total_volume < basketball_min:
            continue
        if extract_market_teams(row) is None:
            continue
        selected.append(row)
    return selected


def select_polymarket_asset_ids(
    rows: list[dict],
    max_assets: int,
) -> list[str]:
    ids: list[str] = []
    for row in rows:
        for token_id in _extract_market_token_ids(row):
            if token_id not in ids:
                ids.append(token_id)
            if len(ids) >= max_assets:
                return ids
    return ids


def flatten_event_markets(events_rows: list[dict]) -> list[dict]:
    rows: list[dict] = []
    for event in events_rows:
        if not isinstance(event, dict):
            continue
        markets = event.get("markets")
        if not isinstance(markets, list):
            continue
        for market in markets:
            if not isinstance(market, dict):
                continue
            if market.get("active") is False or market.get("closed") is True:
                continue
            row = dict(market)
            row["parentEventSlug"] = str(event.get("slug", ""))
            row["parentEventTitle"] = str(event.get("title", ""))
            row["parentEventCategory"] = str(event.get("category", ""))
            row["events"] = [event]
            rows.append(row)
    return rows


def build_sport_tag_ids(sports_rows: list[dict]) -> list[int]:
    allowed_prefixes = (
        "football",
        "soccer",
        "basketball",
        "nba",
        "wnba",
        "ncaab",
        "ncaaw",
        "epl",
        "lal",
        "bun",
        "fl1",
        "itc",
        "mls",
    )
    tag_ids: list[int] = []
    for row in sports_rows:
        if not isinstance(row, dict):
            continue
        sport_name = str(row.get("sport", "")).lower().strip()
        if not sport_name.startswith(allowed_prefixes):
            continue
        tags_text = str(row.get("tags", ""))
        for item in tags_text.split(","):
            item = item.strip()
            if not item.isdigit():
                continue
            tag_id = int(item)
            if tag_id not in tag_ids:
                tag_ids.append(tag_id)
    return tag_ids[:40]


def _extract_first_event(row: dict) -> dict:
    events = row.get("events")
    if isinstance(events, list) and events and isinstance(events[0], dict):
        return events[0]
    return {}


def _split_teams_from_text(text: str) -> tuple[str, str] | None:
    clean = text.strip()
    if not clean:
        return None
    for sep in (" vs ", " v ", " @ "):
        if sep in clean.lower():
            parts = clean.split(sep, 1) if sep in clean else _split_case_insensitive(clean, sep)
            if parts is None:
                continue
            home = parts[0].strip(" ?:-")
            away = parts[1].strip(" ?:-")
            if home and away:
                return (home, away)
    return None


def _extract_teams_from_question_rules(text: str) -> tuple[str, str] | None:
    clean = text.replace("\n", " ")
    marker = "If the "
    idx1 = clean.find(marker)
    if idx1 < 0:
        return None
    rest = clean[idx1 + len(marker) :]
    idx_win1 = rest.find(" win")
    if idx_win1 < 0:
        return None
    team1 = rest[:idx_win1].strip(" \"'")
    idx2 = rest.find(marker, idx_win1)
    if idx2 < 0:
        return None
    rest2 = rest[idx2 + len(marker) :]
    idx_win2 = rest2.find(" win")
    if idx_win2 < 0:
        return None
    team2 = rest2[:idx_win2].strip(" \"'")
    if team1 and team2 and team1.lower() != team2.lower():
        return (team1, team2)
    return None


def _split_case_insensitive(text: str, sep: str) -> tuple[str, str] | None:
    low = text.lower()
    idx = low.find(sep)
    if idx < 0:
        return None
    return (text[:idx], text[idx + len(sep) :])


def _extract_score_from_text(text: str) -> tuple[int, int] | None:
    clean = text.strip()
    for token in clean.replace("–", "-").split():
        if "-" not in token:
            continue
        parts = token.split("-")
        if len(parts) != 2:
            continue
        if parts[0].isdigit() and parts[1].isdigit():
            return (int(parts[0]), int(parts[1]))
    return None


def _extract_teams_from_slug(slug: str) -> tuple[str, str] | None:
    if not slug:
        return None
    parts = [item for item in slug.lower().split("-") if item]
    clean = [item for item in parts if not item.isdigit() and item not in {"nba", "wnba", "epl", "lal", "bun", "fl1", "itc", "mls"}]
    if len(clean) < 2:
        return None
    left = clean[0].upper()
    right = clean[1].upper()
    if left == right:
        return None
    return (left, right)


def _parse_datetime(value: object) -> datetime | None:
    if isinstance(value, (int, float)):
        base = int(value)
        if base > 1_000_000_000_000:
            base = int(base / 1000)
        return datetime.fromtimestamp(base, tz=UTC)
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        if text.isdigit():
            base = int(text)
            if base > 1_000_000_000_000:
                base = int(base / 1000)
            return datetime.fromtimestamp(base, tz=UTC)
        try:
            parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                return parsed.replace(tzinfo=UTC)
            return parsed.astimezone(UTC)
        except Exception:
            return None
    return None


def _to_iso(value: object) -> str:
    if isinstance(value, str):
        if value.isdigit():
            return datetime.fromtimestamp(int(value) / 1000, tz=UTC).isoformat()
        return value
    if isinstance(value, int):
        return datetime.fromtimestamp(value / 1000, tz=UTC).isoformat()
    return datetime.now(UTC).isoformat()
