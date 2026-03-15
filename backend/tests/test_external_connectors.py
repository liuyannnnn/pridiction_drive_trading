from datetime import UTC, datetime, timedelta

from app.connectors.external_feed import (
    build_goalserve_token_attempts,
    compute_goalserve_refresh_deadline,
    extract_goalserve_token,
    parse_polymarket_message_to_tick,
    render_goalserve_subscribe_payload,
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
