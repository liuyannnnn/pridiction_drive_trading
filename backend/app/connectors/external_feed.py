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
    def __init__(self, on_tick: TickHandler, on_log: LogHandler) -> None:
        self._on_tick = on_tick
        self._on_log = on_log

    async def run(self, stop_event: asyncio.Event) -> None:
        while not stop_event.is_set():
            try:
                assets = await self._fetch_asset_ids()
                if len(assets) == 0:
                    await self._on_log("polymarket: no assets found")
                    await asyncio.sleep(10)
                    continue
                async with websockets.connect(settings.polymarket_ws_url, ping_interval=10, ping_timeout=20) as ws:
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
                        raw = await asyncio.wait_for(ws.recv(), timeout=30)
                        message = json.loads(raw)
                        tick = parse_polymarket_message_to_tick(message)
                        if tick is not None:
                            await self._on_tick(tick)
            except Exception as exc:
                await self._on_log(f"polymarket: reconnect reason={exc}")
                await asyncio.sleep(3)

    async def _fetch_asset_ids(self) -> list[str]:
        url = f"{settings.polymarket_gamma_url}/markets"
        params = {"active": "true", "closed": "false", "limit": str(settings.polymarket_ws_max_assets)}
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            rows = response.json()
        ids: list[str] = []
        for row in rows:
            for token_id in _extract_market_token_ids(row):
                if token_id not in ids:
                    ids.append(token_id)
                if len(ids) >= settings.polymarket_ws_max_assets:
                    return ids
        return ids


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
                async with websockets.connect(ws_url, ping_interval=20, ping_timeout=20) as ws:
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
    def __init__(self, on_tick: TickHandler, on_goalserve: GoalserveHandler, on_log: LogHandler) -> None:
        self._on_tick = on_tick
        self._on_goalserve = on_goalserve
        self._on_log = on_log
        self._stop_event = asyncio.Event()
        self._tasks: list[asyncio.Task] = []

    async def start(self) -> None:
        if self._tasks:
            return
        self._stop_event = asyncio.Event()
        if settings.polymarket_ws_enabled:
            connector = PolymarketMarketWsConnector(on_tick=self._on_tick, on_log=self._on_log)
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


def _to_iso(value: object) -> str:
    if isinstance(value, str):
        if value.isdigit():
            return datetime.fromtimestamp(int(value) / 1000, tz=UTC).isoformat()
        return value
    if isinstance(value, int):
        return datetime.fromtimestamp(value / 1000, tz=UTC).isoformat()
    return datetime.now(UTC).isoformat()
