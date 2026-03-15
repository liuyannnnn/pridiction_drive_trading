from fastapi.testclient import TestClient
from app.main import app


client = TestClient(app)


def test_health_endpoint_shape() -> None:
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    payload = response.json()
    assert "status" in payload
    assert "postgres" in payload
    assert "redis" in payload


def test_matches_endpoint() -> None:
    response = client.get("/api/v1/matches")
    assert response.status_code == 200
    payload = response.json()
    assert isinstance(payload, list)
    assert len(payload) >= 1
    row = payload[0]
    assert "match_id" in row
    assert "sport" in row
    assert "status" in row


def test_ticks_endpoint() -> None:
    response = client.get("/api/v1/ticks")
    assert response.status_code == 200
    payload = response.json()
    assert isinstance(payload, list)


def test_simulation_control_endpoints() -> None:
    start = client.post("/api/v1/simulation/start", json={"initial_balance": 2000.0, "retracement": 0.05})
    assert start.status_code == 200
    assert start.json()["running"] is True

    state = client.get("/api/v1/simulation/state")
    assert state.status_code == 200
    assert "balance" in state.json()
    assert "running" in state.json()

    stop = client.post("/api/v1/simulation/stop")
    assert stop.status_code == 200
    assert stop.json()["running"] is False


def test_trading_data_endpoints() -> None:
    client.post("/api/v1/simulation/start", json={"initial_balance": 3000.0, "retracement": 0.05})

    accounts = client.get("/api/v1/accounts")
    assert accounts.status_code == 200
    assert isinstance(accounts.json(), list)
    assert len(accounts.json()) >= 1

    positions = client.get("/api/v1/positions")
    assert positions.status_code == 200
    assert isinstance(positions.json(), list)

    trades = client.get("/api/v1/trades")
    assert trades.status_code == 200
    assert isinstance(trades.json(), list)

    logs = client.get("/api/v1/logs")
    assert logs.status_code == 200
    assert isinstance(logs.json(), list)


def test_goalserve_detail_endpoint() -> None:
    matches = client.get("/api/v1/matches").json()
    match_id = matches[0]["match_id"]
    detail = client.get(f"/api/v1/goalserve/match/{match_id}")
    assert detail.status_code == 200
    payload = detail.json()
    assert payload["match_id"] == match_id
    assert "lineups" in payload
    assert "odds" in payload


def test_collector_settings_endpoints() -> None:
    current = client.get("/api/v1/settings/collector")
    assert current.status_code == 200
    payload = current.json()
    assert "collection_interval_minutes" in payload
    assert "football_volume_threshold_k" in payload

    updated = client.put(
        "/api/v1/settings/collector",
        json={
            "collection_interval_minutes": 9,
            "football_volume_threshold_k": 70,
            "basketball_volume_threshold_k": 130,
        },
    )
    assert updated.status_code == 200
    assert updated.json()["collection_interval_minutes"] == 9


def test_market_ws_stream_endpoint() -> None:
    with client.websocket_connect("/api/v1/ws/market") as websocket:
        message = websocket.receive_json()
        assert "topic" in message
        assert "payload" in message
        assert message["topic"] == "market.tick"
