from datetime import UTC, datetime, timedelta

from app.connectors.external_feed import (
    PolymarketMarketWsConnector,
    build_sport_tag_ids,
    build_goalserve_token_attempts,
    compute_goalserve_refresh_deadline,
    extract_goalserve_token,
    extract_market_external_ids,
    extract_market_final_score,
    extract_market_league,
    extract_market_outcome_map,
    extract_market_outcome_prices,
    extract_market_teams,
    extract_polymarket_start_time,
    flatten_event_markets,
    parse_polymarket_message_to_tick,
    render_goalserve_subscribe_payload,
    select_polymarket_asset_ids,
    select_polymarket_markets,
)


def test_extract_goalserve_token_variants() -> None:
    assert extract_goalserve_token({"token": "abc"}) == "abc"
    assert extract_goalserve_token({"access_token": "def"}) == "def"
    assert extract_goalserve_token({"data": {"token": "ghi"}}) == "ghi"


def test_parse_polymarket_best_bid_ask_message() -> None:
    message = {
        "event_type": "best_bid_ask",
        "asset_id": "token_1",
        "best_bid": "0.73",
        "best_ask": "0.77",
        "timestamp": "1766789469958",
    }
    tick = parse_polymarket_message_to_tick(message)
    assert tick is not None
    assert tick["match_id"] == "token_1"
    assert tick["bid"] == 0.73
    assert tick["ask"] == 0.77


def test_parse_polymarket_price_change_message() -> None:
    message = {
        "event_type": "price_change",
        "price_changes": [
            {
                "asset_id": "token_2",
                "best_bid": "0.5",
                "best_ask": "0.52",
            }
        ],
        "timestamp": "1757908892351",
    }
    tick = parse_polymarket_message_to_tick(message)
    assert tick is not None
    assert tick["match_id"] == "token_2"
    assert tick["bid"] == 0.5
    assert tick["ask"] == 0.52


def test_build_goalserve_token_attempts_auto() -> None:
    attempts = build_goalserve_token_attempts(
        token_url="https://example.com/token",
        token_method="auto",
        api_key="k",
        username="u",
        password="p",
    )
    assert [item["method"] for item in attempts] == ["post_json", "post_form", "get_query"]
    assert attempts[0]["url"] == "https://example.com/token"
    assert attempts[0]["json"]["apiKey"] == "k"
    assert attempts[1]["data"]["apiKey"] == "k"
    assert attempts[2]["params"]["apiKey"] == "k"


def test_build_goalserve_token_attempts_template_url() -> None:
    attempts = build_goalserve_token_attempts(
        token_url="https://example.com/token?key={api_key}&u={username}&p={password}",
        token_method="auto",
        api_key="k",
        username="u",
        password="p",
    )
    assert attempts == [{"method": "get_template", "url": "https://example.com/token?key=k&u=u&p=p"}]


def test_render_goalserve_subscribe_payload() -> None:
    payload = render_goalserve_subscribe_payload('{"type":"subscribe","token":"{token}"}', token="abc")
    assert payload == '{"type":"subscribe","token":"abc"}'


def test_compute_goalserve_refresh_deadline() -> None:
    issued_at = datetime(2026, 1, 1, 0, 0, 0, tzinfo=UTC)
    deadline = compute_goalserve_refresh_deadline(issued_at, ttl_minutes=60, refresh_ahead_seconds=300)
    assert deadline == issued_at + timedelta(minutes=55)


def test_select_polymarket_markets_filter_24h_and_volume() -> None:
    now = datetime(2026, 3, 15, 12, 0, 0, tzinfo=UTC)
    rows = [
        {
            "question": "Arsenal vs Chelsea",
            "sport": "Football",
            "startDate": "2026-03-16T11:00:00Z",
            "volumeNum": 88000,
            "clobTokenIds": '["a1","a2"]',
        },
        {
            "question": "Lakers vs Warriors",
            "sport": "Basketball",
            "startDate": "2026-03-16T10:30:00Z",
            "volumeNum": 120000,
            "clobTokenIds": '["b1","b2"]',
        },
        {
            "question": "Past Match",
            "sport": "Football",
            "startDate": "2026-03-15T08:00:00Z",
            "volumeNum": 200000,
            "clobTokenIds": '["p1","p2"]',
        },
        {
            "question": "Future Too Far",
            "sport": "Basketball",
            "startDate": "2026-03-17T20:00:00Z",
            "volumeNum": 500000,
            "clobTokenIds": '["f1","f2"]',
        },
    ]
    selected = select_polymarket_markets(
        rows=rows,
        collector_settings={
            "football_volume_threshold_k": 50,
            "basketball_volume_threshold_k": 100,
        },
        now=now,
    )
    assert len(selected) == 2
    assert selected[0]["question"] == "Arsenal vs Chelsea"
    assert selected[1]["question"] == "Lakers vs Warriors"


def test_select_polymarket_markets_uses_event_total_volume_threshold() -> None:
    now = datetime(2026, 3, 16, 18, 0, 0, tzinfo=UTC)
    rows = [
        {
            "question": "Sporting CP vs FK Bodo/Glimt",
            "sport": "Football",
            "startDate": "2026-03-17T16:45:00Z",
            "volumeNum": 180000,
            "clobTokenIds": '["s1","s2","s3"]',
            "events": [
                {
                    "id": "evt-1",
                    "slug": "ucl-spo1-bog1-2026-03-17",
                    "title": "Sporting CP vs FK Bodo/Glimt",
                    "category": "Sports",
                    "volume": 520000,
                    "startDate": "2026-03-17T16:45:00Z",
                }
            ],
        }
    ]
    selected = select_polymarket_markets(
        rows=rows,
        collector_settings={
            "football_volume_threshold_k": 500,
            "basketball_volume_threshold_k": 100,
        },
        now=now,
    )
    assert len(selected) == 1
    assert selected[0]["events"][0]["slug"] == "ucl-spo1-bog1-2026-03-17"


def test_extract_polymarket_start_time_prefers_event_end_date_over_created_start_date() -> None:
    market = {
        "events": [
            {
                "slug": "ucl-spo1-bog1-2026-03-17",
                "title": "Sporting CP vs FK Bodo/Glimt",
                "startDate": "2026-03-04T19:05:33.226765Z",
                "endDate": "2026-03-17T17:45:00Z",
            }
        ]
    }
    start_time = extract_polymarket_start_time(market)
    assert start_time == datetime(2026, 3, 17, 17, 45, 0, tzinfo=UTC)


def test_polymarket_connector_disables_proxy_for_websocket(monkeypatch) -> None:
    called: dict[str, object] = {}

    class FakeWs:
        async def send(self, _payload: str) -> None:
            return None

        async def recv(self) -> str:
            stop_event.set()
            return "{}"

    class FakeWsContext:
        async def __aenter__(self) -> FakeWs:
            return FakeWs()

        async def __aexit__(self, exc_type, exc, tb) -> bool:
            return False

    async def on_tick(_tick: dict) -> None:
        return None

    async def on_log(_message: str) -> None:
        return None

    async def on_markets(_markets: list[dict]) -> None:
        return None

    def fake_connect(url: str, **kwargs):
        called["url"] = url
        called["kwargs"] = kwargs
        return FakeWsContext()

    stop_event = __import__("asyncio").Event()
    connector = PolymarketMarketWsConnector(
        on_tick=on_tick,
        on_log=on_log,
        on_markets=on_markets,
        get_collector_settings=lambda: {
            "collection_interval_minutes": 1,
            "football_volume_threshold_k": 50,
            "basketball_volume_threshold_k": 50,
        },
    )

    async def fake_fetch_asset_ids(_collector_settings: dict) -> tuple[list[str], list[dict]]:
        return (["asset-1"], [])

    monkeypatch.setattr(connector, "_fetch_asset_ids", fake_fetch_asset_ids)
    monkeypatch.setattr("app.connectors.external_feed.websockets.connect", fake_connect)

    __import__("asyncio").run(connector.run(stop_event))

    assert "proxy" in called["kwargs"]
    assert called["kwargs"]["proxy"] is None


def test_polymarket_connector_does_not_refetch_market_universe_before_refresh_deadline(monkeypatch) -> None:
    base_now = datetime(2026, 3, 16, 12, 0, 0, tzinfo=UTC)
    now = base_now
    fetch_calls = {"count": 0}
    market_calls = {"count": 0}

    class FakeDateTime:
        @staticmethod
        def now(_tz=None):
            return now

    async def on_tick(_tick: dict) -> None:
        return None

    async def on_log(_message: str) -> None:
        return None

    async def on_markets(_markets: list[dict]) -> None:
        market_calls["count"] += 1

    async def fake_fetch_asset_ids(_collector_settings: dict) -> tuple[list[str], list[dict]]:
        fetch_calls["count"] += 1
        return (["asset-1"], [{"id": "market-1"}])

    async def fake_sleep(seconds: float) -> None:
        nonlocal now
        now = now + timedelta(seconds=seconds)
        if (now - base_now).total_seconds() >= 12:
            stop_event.set()

    class FailingWsContext:
        async def __aenter__(self):
            raise TimeoutError("timed out during opening handshake")

        async def __aexit__(self, exc_type, exc, tb) -> bool:
            return False

    stop_event = __import__("asyncio").Event()
    connector = PolymarketMarketWsConnector(
        on_tick=on_tick,
        on_log=on_log,
        on_markets=on_markets,
        get_collector_settings=lambda: {
            "collection_interval_minutes": 1,
            "football_volume_threshold_k": 50,
            "basketball_volume_threshold_k": 50,
        },
    )

    monkeypatch.setattr(connector, "_fetch_asset_ids", fake_fetch_asset_ids)
    monkeypatch.setattr("app.connectors.external_feed.datetime", FakeDateTime)
    monkeypatch.setattr("app.connectors.external_feed.asyncio.sleep", fake_sleep)
    monkeypatch.setattr("app.connectors.external_feed.websockets.connect", lambda *_args, **_kwargs: FailingWsContext())

    __import__("asyncio").run(connector.run(stop_event))

    assert fetch_calls["count"] == 1
    assert market_calls["count"] == 1


def test_select_polymarket_asset_ids_respects_limit() -> None:
    rows = [
        {"clobTokenIds": '["a1","a2"]'},
        {"clobTokenIds": '["b1","b2"]'},
    ]
    ids = select_polymarket_asset_ids(rows, max_assets=3)
    assert ids == ["a1", "a2", "b1"]


def test_select_polymarket_markets_accepts_event_level_fields() -> None:
    now = datetime(2026, 3, 15, 12, 0, 0, tzinfo=UTC)
    rows = [
        {
            "question": "Lakers vs Warriors",
            "volumeNum": 210000,
            "clobTokenIds": '["e1","e2"]',
            "events": [
                {
                    "category": "Sports",
                    "subcategory": "Basketball",
                    "title": "Lakers vs Warriors",
                    "startDate": "2026-03-16T06:00:00Z",
                }
            ],
        }
    ]
    selected = select_polymarket_markets(
        rows=rows,
        collector_settings={
            "football_volume_threshold_k": 50,
            "basketball_volume_threshold_k": 100,
        },
        now=now,
    )
    assert len(selected) == 1


def test_flatten_event_markets_uses_parent_event_hints() -> None:
    events_rows = [
        {
            "id": "27830",
            "slug": "2026-nba-champion",
            "title": "Lakers vs Warriors",
            "category": "Sports",
            "markets": [
                {
                    "id": "m1",
                    "question": "Lakers vs Warriors",
                    "startDate": "2026-03-15T15:00:00Z",
                    "volumeNum": 250000,
                    "clobTokenIds": '["x1","x2"]',
                    "active": True,
                    "closed": False,
                }
            ],
        }
    ]
    rows = flatten_event_markets(events_rows)
    assert len(rows) == 1
    assert rows[0]["parentEventSlug"] == "2026-nba-champion"
    selected = select_polymarket_markets(
        rows=rows,
        collector_settings={"football_volume_threshold_k": 50, "basketball_volume_threshold_k": 100},
        now=datetime(2026, 3, 15, 12, 0, 0, tzinfo=UTC),
    )
    assert len(selected) == 1


def test_build_sport_tag_ids_extracts_football_and_basketball() -> None:
    rows = [
        {"sport": "nba", "tags": "1,745,100639"},
        {"sport": "soccer_epl", "tags": "1,2119,100640"},
        {"sport": "crypto", "tags": "1,99"},
    ]
    tag_ids = build_sport_tag_ids(rows)
    assert 745 in tag_ids
    assert 2119 in tag_ids
    assert 99 not in tag_ids


def test_extract_market_outcome_map_with_tokens_and_outcomes() -> None:
    market = {
        "outcomes": '["Home","Away","Draw"]',
        "tokens": [
            {"token_id": "t_home"},
            {"token_id": "t_away"},
            {"token_id": "t_draw"},
        ],
    }
    mapping = extract_market_outcome_map(market)
    assert mapping["t_home"] == "home"
    assert mapping["t_away"] == "away"
    assert mapping["t_draw"] == "draw"


def test_extract_market_outcome_prices_map() -> None:
    market = {
        "outcomes": '["Home","Away","Draw"]',
        "outcomePrices": '["0.41","0.34","0.25"]',
    }
    prices = extract_market_outcome_prices(market)
    assert prices["home"] == 0.41
    assert prices["away"] == 0.34
    assert prices["draw"] == 0.25


def test_extract_market_teams_from_event_title() -> None:
    market = {
        "events": [{"title": "Arsenal vs Chelsea"}],
        "question": "Will Arsenal win?",
    }
    teams = extract_market_teams(market)
    assert teams == ("Arsenal", "Chelsea")


def test_extract_market_external_ids() -> None:
    market = {
        "id": "1593514",
        "slug": "arsenal-chelsea-moneyline",
        "events": [{"id": "e123", "slug": "epl-arsenal-chelsea"}],
    }
    ids = extract_market_external_ids(market)
    assert ids["external_event_id"] == "e123"
    assert ids["external_event_slug"] == "epl-arsenal-chelsea"
    assert ids["external_market_id"] == "1593514"
    assert ids["external_market_slug"] == "arsenal-chelsea-moneyline"


def test_extract_market_league_prefers_slug_prefix() -> None:
    market = {"events": [{"slug": "epl-arsenal-chelsea"}]}
    assert extract_market_league(market, "football") == "Premier League"


def test_extract_market_final_score() -> None:
    market = {"events": [{"title": "Arsenal 2-1 Chelsea"}]}
    score = extract_market_final_score(market)
    assert score == (2, 1)


def test_extract_market_teams_from_rule_question() -> None:
    market = {
        "question": 'In the upcoming NBA game... If the Timberwolves win, the market resolves to "Timberwolves". If the Thunder win, the market resolves to "Thunder".'
    }
    teams = extract_market_teams(market)
    assert teams == ("Timberwolves", "Thunder")


def test_extract_market_teams_from_slug_fallback() -> None:
    market = {"events": [{"slug": "nba-min-okc-2026-03-15"}]}
    teams = extract_market_teams(market)
    assert teams == ("MIN", "OKC")
