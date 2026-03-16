from fastapi.testclient import TestClient
from app.config import settings
from app.main import app
from app.runtime.container import runtime, trading_manager


client = TestClient(app)


def _clear_tradings() -> None:
    for trading_id in list(trading_manager._tradings.keys()):
        trading_manager.delete_trading(trading_id)


def test_health_endpoint_shape() -> None:
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    payload = response.json()
    assert "status" in payload
    assert "postgres" in payload
    assert "redis" in payload


def test_matches_endpoint(monkeypatch) -> None:
    monkeypatch.setattr(settings, "external_stream_enabled", False)
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
    _clear_tradings()
    start = client.post("/api/v1/simulation/start", json={"initial_balance": 2000.0, "retracement": 0.05})
    assert start.status_code == 200
    assert start.json()["running"] is True

    state = client.get("/api/v1/simulation/state")
    assert state.status_code == 200
    assert "running" in state.json()
    assert "running_count" in state.json()

    stop = client.post("/api/v1/simulation/stop")
    assert stop.status_code == 200
    assert stop.json()["running"] is False


def test_simulation_start_with_multiple_strategies() -> None:
    _clear_tradings()
    start = client.post(
        "/api/v1/simulation/start",
        json={
            "initial_balance": 2000.0,
            "retracement": 0.05,
            "strategies": [
                {"name": "prematch_gap_retracement", "strategy_id": "S001", "entry_spread_threshold": 0.25, "max_drawdown": 0.05, "trade_amount": 100},
                {"name": "live_first_goal_retracement", "strategy_id": "S002", "max_drawdown": 0.05, "trade_amount": 80},
            ],
        },
    )
    assert start.status_code == 200
    payload = start.json()
    assert payload["running"] is True
    assert len(payload["strategy_ids"]) == 2
    assert len(payload["trading_ids"]) == 2
    listed = client.get("/api/v1/tradings")
    assert listed.status_code == 200
    created_ids = {item["trading_id"] for item in listed.json() if item["mode"] == "simulation"}
    assert set(payload["trading_ids"]).issubset(created_ids)


def test_simulation_endpoints_only_control_simulation_tradings() -> None:
    _clear_tradings()
    created_real = client.post(
        "/api/v1/tradings",
        json={
            "strategy_name": "prematch_gap_retracement",
            "strategy_params": {"entry_spread_threshold": 0.25, "max_drawdown": 0.05, "trade_amount": 100},
            "affect_sports": ["football"],
            "mode": "real",
        },
    )
    assert created_real.status_code == 200
    real_id = created_real.json()["trading_id"]
    started_real = client.post(f"/api/v1/tradings/{real_id}/start")
    assert started_real.status_code == 200
    assert started_real.json()["status"] == "running"

    created_sim = client.post(
        "/api/v1/tradings",
        json={
            "strategy_name": "prematch_gap_retracement",
            "strategy_params": {"entry_spread_threshold": 0.25, "max_drawdown": 0.05, "trade_amount": 100},
            "affect_sports": ["football"],
            "mode": "simulation",
        },
    )
    assert created_sim.status_code == 200
    sim_id = created_sim.json()["trading_id"]
    started_sim = client.post(f"/api/v1/tradings/{sim_id}/start")
    assert started_sim.status_code == 200

    state = client.get("/api/v1/simulation/state")
    assert state.status_code == 200
    payload = state.json()
    assert payload["running"] is True
    assert payload["running_count"] == 1
    assert {item["trading_id"] for item in payload["tradings"]} == {sim_id}

    stopped = client.post("/api/v1/simulation/stop")
    assert stopped.status_code == 200
    assert stopped.json()["stopped"] == 1

    real_snapshot = client.get(f"/api/v1/tradings/{real_id}")
    assert real_snapshot.status_code == 200
    assert real_snapshot.json()["status"] == "running"

    sim_snapshot = client.get(f"/api/v1/tradings/{sim_id}")
    assert sim_snapshot.status_code == 200
    assert sim_snapshot.json()["status"] == "stopped"


def test_trading_data_endpoints() -> None:
    _clear_tradings()
    client.post("/api/v1/simulation/start", json={"initial_balance": 3000.0, "retracement": 0.05})

    accounts = client.get("/api/v1/accounts")
    assert accounts.status_code == 200
    assert isinstance(accounts.json(), list)
    assert len(accounts.json()) >= 1
    account = accounts.json()[0]
    assert "id" in account
    assert "mode" in account
    assert "strategy_name" in account
    assert "retracement" in account
    assert "total_assets" in account
    assert "available_cash" in account
    assert "position_count" in account
    assert "is_running" in account
    assert "initial_balance" in account
    assert "affect_sports" in account
    assert "win_rate" in account

    positions = client.get("/api/v1/positions")
    assert positions.status_code == 200
    assert isinstance(positions.json(), list)

    trades = client.get("/api/v1/trades")
    assert trades.status_code == 200
    assert isinstance(trades.json(), list)

    logs = client.get("/api/v1/logs")
    assert logs.status_code == 200
    assert isinstance(logs.json(), list)


def test_update_trading_endpoint_merges_strategy_params_and_updates_account_projection() -> None:
    _clear_tradings()
    created = client.post(
        "/api/v1/tradings",
        json={
            "strategy_name": "prematch_gap_retracement",
            "strategy_params": {
                "initial_balance": 5000.0,
                "entry_spread_threshold": 0.35,
                "max_drawdown": 0.05,
                "trade_amount": 120.0,
            },
            "affect_sports": ["football"],
            "mode": "simulation",
        },
    )
    assert created.status_code == 200
    trading_id = created.json()["trading_id"]

    started = client.post(f"/api/v1/tradings/{trading_id}/start")
    assert started.status_code == 200
    assert started.json()["status"] == "running"

    updated = client.put(
        f"/api/v1/tradings/{trading_id}",
        json={
            "strategy_params": {
                "max_drawdown": 0.07,
                "trade_amount": 150.0,
            },
            "affect_sports": ["basketball"],
        },
    )
    assert updated.status_code == 200
    payload = updated.json()
    assert payload["status"] == "running"
    assert payload["affect_sports"] == ["basketball"]
    assert payload["strategy_params"]["initial_balance"] == 5000.0
    assert payload["strategy_params"]["entry_spread_threshold"] == 0.35
    assert payload["strategy_params"]["max_drawdown"] == 0.07
    assert payload["strategy_params"]["trade_amount"] == 150.0

    stored = client.get(f"/api/v1/tradings/{trading_id}")
    assert stored.status_code == 200
    assert stored.json()["strategy_params"]["entry_spread_threshold"] == 0.35
    assert stored.json()["strategy_params"]["max_drawdown"] == 0.07

    accounts = client.get("/api/v1/accounts")
    assert accounts.status_code == 200
    account = next(item for item in accounts.json() if item["id"] == trading_id)
    assert account["retracement"] == 0.07
    assert account["affect_sports"] == ["basketball"]
    assert account["strategy_params"]["trade_amount"] == 150.0
    assert account["strategy_params"]["entry_spread_threshold"] == 0.35


def test_trades_and_logs_can_be_scoped_by_match_id() -> None:
    _clear_tradings()
    created_one = client.post(
        "/api/v1/tradings",
        json={
            "strategy_name": "prematch_gap_retracement",
            "strategy_params": {"initial_balance": 3000.0, "entry_spread_threshold": 0.25, "max_drawdown": 0.05, "trade_amount": 100},
            "affect_sports": ["football"],
            "mode": "simulation",
        },
    )
    created_two = client.post(
        "/api/v1/tradings",
        json={
            "strategy_name": "live_first_goal_retracement",
            "strategy_params": {"initial_balance": 3000.0, "max_drawdown": 0.05, "trade_amount": 80},
            "affect_sports": ["football"],
            "mode": "simulation",
        },
    )
    assert created_one.status_code == 200
    assert created_two.status_code == 200
    trading_one = trading_manager._tradings[created_one.json()["trading_id"]]
    trading_two = trading_manager._tradings[created_two.json()["trading_id"]]

    trading_one.executor.logs = [
        {"trade_id": "T-A1", "match_id": "match-a", "action": "buy", "price": 0.61, "amount": 100.0, "profit": 0.0},
        {"trade_id": "T-B1", "match_id": "match-b", "action": "sell", "price": 0.58, "amount": 100.0, "profit": -5.0},
    ]
    trading_two.executor.logs = [
        {"trade_id": "T-A2", "match_id": "match-a", "action": "buy", "price": 0.49, "amount": 80.0, "profit": 0.0},
    ]
    trading_one.logs = [
        {"ts_utc": "2026-03-16T08:00:00+00:00", "match_id": "match-a", "level": "trade", "message": "match-a buy"},
        {"ts_utc": "2026-03-16T08:01:00+00:00", "match_id": "match-b", "level": "warn", "message": "match-b stop"},
    ]
    trading_two.logs = [
        {"ts_utc": "2026-03-16T08:02:00+00:00", "match_id": "match-a", "level": "trade", "message": "match-a confirm"},
    ]

    trades = client.get("/api/v1/trades?match_id=match-a")
    assert trades.status_code == 200
    assert [item["trade_id"] for item in trades.json()] == ["T-A1", "T-A2"]
    assert {item["match_id"] for item in trades.json()} == {"match-a"}

    logs = client.get("/api/v1/logs?match_id=match-a&limit=10")
    assert logs.status_code == 200
    assert [item["message"] for item in logs.json()] == ["match-a buy", "match-a confirm"]
    assert {item["match_id"] for item in logs.json()} == {"match-a"}


def test_collector_status_endpoint() -> None:
    response = client.get("/api/v1/collector/status")
    assert response.status_code == 200
    payload = response.json()
    assert "external_stream_enabled" in payload
    assert "external_stream_started" in payload
    assert "polymarket_ws_enabled" in payload
    assert "goalserve_ws_enabled" in payload
    assert "matches_count" in payload
    assert "last_tick_source" in payload
    assert "latest_tick_ts_utc" in payload


def test_matches_endpoint_triggers_external_start_when_enabled(monkeypatch) -> None:
    started = {"called": False}
    original_enabled = settings.external_stream_enabled
    original_started = runtime._external_started

    async def fake_start() -> None:
        started["called"] = True
        runtime._external_started = True

    monkeypatch.setattr(settings, "external_stream_enabled", True)
    monkeypatch.setattr(runtime, "start_external_connectors", fake_start)
    runtime._external_started = False

    response = client.get("/api/v1/matches")
    assert response.status_code == 200
    assert started["called"] is True

    runtime._external_started = original_started
    monkeypatch.setattr(settings, "external_stream_enabled", original_enabled)


def test_goalserve_detail_endpoint(monkeypatch) -> None:
    monkeypatch.setattr(settings, "external_stream_enabled", False)
    matches = client.get("/api/v1/matches").json()
    match_id = matches[0]["match_id"]
    detail = client.get(f"/api/v1/goalserve/match/{match_id}")
    assert detail.status_code == 200
    payload = detail.json()
    assert payload["match_id"] == match_id
    assert "lineups" in payload
    assert "odds" in payload


def test_collector_settings_endpoints() -> None:
    _clear_tradings()
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
    stored = client.get("/api/v1/settings/collector")
    assert stored.status_code == 200
    assert stored.json()["collection_interval_minutes"] == 9


def test_collector_settings_survive_runtime_reset(monkeypatch) -> None:
    _clear_tradings()
    stored_payload: dict | None = None

    async def fake_upsert(payload: dict) -> None:
        nonlocal stored_payload
        stored_payload = dict(payload)

    async def fake_get() -> dict | None:
        return dict(stored_payload) if stored_payload is not None else None

    monkeypatch.setattr(runtime.repository, "upsert_collector_settings", fake_upsert)
    monkeypatch.setattr(runtime.repository, "get_collector_settings", fake_get)
    payload = {
        "collection_interval_minutes": 12,
        "football_volume_threshold_k": 88,
        "basketball_volume_threshold_k": 166,
    }
    updated = client.put("/api/v1/settings/collector", json=payload)
    assert updated.status_code == 200
    runtime.update_collector_settings(
        {
            "collection_interval_minutes": 1,
            "football_volume_threshold_k": 1,
            "basketball_volume_threshold_k": 1,
        }
    )
    loaded = client.get("/api/v1/settings/collector")
    assert loaded.status_code == 200
    assert loaded.json()["collection_interval_minutes"] == 12
    assert loaded.json()["football_volume_threshold_k"] == 88
    assert loaded.json()["basketball_volume_threshold_k"] == 166


def test_collector_settings_update_triggers_immediate_refresh(monkeypatch) -> None:
    _clear_tradings()
    called = {"stop": 0, "start": 0}
    original_enabled = settings.external_stream_enabled
    original_started = runtime._external_started

    async def fake_stop() -> None:
        called["stop"] += 1
        runtime._external_started = False

    async def fake_start() -> None:
        called["start"] += 1
        runtime._external_started = True

    monkeypatch.setattr(settings, "external_stream_enabled", True)
    runtime._external_started = True
    monkeypatch.setattr(runtime, "stop_external_connectors", fake_stop)
    monkeypatch.setattr(runtime, "start_external_connectors", fake_start)

    response = client.put(
        "/api/v1/settings/collector",
        json={
            "collection_interval_minutes": 7,
            "football_volume_threshold_k": 66,
            "basketball_volume_threshold_k": 99,
        },
    )
    assert response.status_code == 200
    assert called["stop"] == 1
    assert called["start"] == 1

    runtime._external_started = original_started
    monkeypatch.setattr(settings, "external_stream_enabled", original_enabled)


def test_collector_settings_falls_back_to_runtime_when_repository_read_fails(monkeypatch) -> None:
    async def fake_get() -> dict | None:
        raise RuntimeError("db unavailable")

    monkeypatch.setattr(runtime.repository, "get_collector_settings", fake_get)
    runtime.update_collector_settings(
        {
            "collection_interval_minutes": 15,
            "football_volume_threshold_k": 77,
            "basketball_volume_threshold_k": 155,
        }
    )
    response = client.get("/api/v1/settings/collector")
    assert response.status_code == 200
    assert response.json()["collection_interval_minutes"] == 15


def test_collector_settings_falls_back_to_runtime_when_repository_write_fails(monkeypatch) -> None:
    async def fake_upsert(payload: dict) -> None:
        raise RuntimeError("db unavailable")

    monkeypatch.setattr(runtime.repository, "upsert_collector_settings", fake_upsert)
    response = client.put(
        "/api/v1/settings/collector",
        json={
            "collection_interval_minutes": 11,
            "football_volume_threshold_k": 81,
            "basketball_volume_threshold_k": 141,
        },
    )
    assert response.status_code == 200
    assert response.json()["collection_interval_minutes"] == 11


def test_market_ws_stream_endpoint() -> None:
    with client.websocket_connect("/api/v1/ws/market") as websocket:
        message = websocket.receive_json()
        assert "topic" in message
        assert "payload" in message
        assert message["topic"] == "market.tick"


def test_cors_preflight_from_frontend_origin() -> None:
    response = client.options(
        "/api/v1/health",
        headers={
            "Origin": "http://127.0.0.1:5173",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "http://127.0.0.1:5173"


def test_tradings_endpoints() -> None:
    _clear_tradings()
    created = client.post(
        "/api/v1/tradings",
        json={
            "strategy_name": "prematch_gap_retracement",
            "strategy_params": {"entry_spread_threshold": 0.25, "max_drawdown": 0.05, "trade_amount": 100},
            "affect_sports": ["football"],
            "mode": "simulation",
        },
    )
    assert created.status_code == 200
    trading_id = created.json()["trading_id"]
    started = client.post(f"/api/v1/tradings/{trading_id}/start")
    assert started.status_code == 200
    assert started.json()["status"] == "running"
    listed = client.get("/api/v1/tradings")
    assert listed.status_code == 200
    assert any(item["trading_id"] == trading_id for item in listed.json())
    removed = client.delete(f"/api/v1/tradings/{trading_id}")
    assert removed.status_code == 200
    assert removed.json()["deleted"] is True
