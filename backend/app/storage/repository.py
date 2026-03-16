import json
from sqlalchemy import text
from app.storage.postgres import engine


class Repository:
    def __init__(self) -> None:
        self._schema_ready = False

    async def ensure_schema(self) -> None:
        if self._schema_ready:
            return
        async with engine.begin() as conn:
            await conn.execute(text("CREATE SCHEMA IF NOT EXISTS polypdt"))
            await conn.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS polypdt.matches (
                      match_id TEXT PRIMARY KEY,
                      sport TEXT NOT NULL,
                      league TEXT NOT NULL,
                      team_home TEXT NOT NULL,
                      team_away TEXT NOT NULL,
                      start_time_utc TIMESTAMPTZ NOT NULL,
                      status TEXT NOT NULL,
                      moneyline_volume NUMERIC(18,6) NOT NULL DEFAULT 0,
                      total_volume NUMERIC(18,6) NOT NULL DEFAULT 0,
                      latest_ts_utc TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                      external_event_id TEXT NOT NULL DEFAULT '',
                      external_event_slug TEXT NOT NULL DEFAULT '',
                      external_market_id TEXT NOT NULL DEFAULT '',
                      external_market_slug TEXT NOT NULL DEFAULT '',
                      score_home INTEGER,
                      score_away INTEGER,
                      created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                      updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    )
                    """
                )
            )
            await conn.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS polypdt.match_mapping (
                      mapping_id BIGSERIAL PRIMARY KEY,
                      match_id TEXT NOT NULL,
                      pm_event_id TEXT NOT NULL,
                      goalserve_event_id TEXT NOT NULL,
                      score NUMERIC(6,5) NOT NULL,
                      decision TEXT NOT NULL,
                      created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    )
                    """
                )
            )
            await conn.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS polypdt.market_ticks (
                      tick_id BIGSERIAL PRIMARY KEY,
                      match_id TEXT NOT NULL,
                      ts_utc TIMESTAMPTZ NOT NULL,
                      source TEXT NOT NULL,
                      outcome TEXT NOT NULL,
                      bid NUMERIC(10,6),
                      ask NUMERIC(10,6),
                      volume NUMERIC(18,6),
                      extra JSONB
                    )
                    """
                )
            )
            await conn.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS polypdt.market_snapshots (
                      snapshot_id BIGSERIAL PRIMARY KEY,
                      match_id TEXT NOT NULL,
                      snapshot_ts_utc TIMESTAMPTZ NOT NULL,
                      source TEXT NOT NULL,
                      sport TEXT NOT NULL,
                      status TEXT NOT NULL,
                      start_time_utc TIMESTAMPTZ NOT NULL,
                      team_home TEXT NOT NULL,
                      team_away TEXT NOT NULL,
                      external_event_id TEXT NOT NULL DEFAULT '',
                      external_event_slug TEXT NOT NULL DEFAULT '',
                      external_market_id TEXT NOT NULL DEFAULT '',
                      external_market_slug TEXT NOT NULL DEFAULT '',
                      score_home INTEGER,
                      score_away INTEGER,
                      home_bid NUMERIC(10,6),
                      home_ask NUMERIC(10,6),
                      home_price NUMERIC(10,6),
                      away_bid NUMERIC(10,6),
                      away_ask NUMERIC(10,6),
                      away_price NUMERIC(10,6),
                      draw_bid NUMERIC(10,6),
                      draw_ask NUMERIC(10,6),
                      draw_price NUMERIC(10,6),
                      moneyline_volume NUMERIC(18,6),
                      total_volume NUMERIC(18,6),
                      ingest_type TEXT NOT NULL,
                      extra JSONB
                    )
                    """
                )
            )
            await conn.execute(
                text(
                    """
                    CREATE INDEX IF NOT EXISTS idx_market_ticks_match_time
                    ON polypdt.market_ticks (match_id, ts_utc DESC)
                    """
                )
            )
            await conn.execute(
                text(
                    """
                    CREATE INDEX IF NOT EXISTS idx_market_snapshots_match_time
                    ON polypdt.market_snapshots (match_id, snapshot_ts_utc DESC)
                    """
                )
            )
            await conn.execute(
                text(
                    """
                    CREATE INDEX IF NOT EXISTS idx_matches_status_sport
                    ON polypdt.matches (status, sport)
                    """
                )
            )
            await conn.execute(text("ALTER TABLE polypdt.matches ADD COLUMN IF NOT EXISTS external_event_id TEXT NOT NULL DEFAULT ''"))
            await conn.execute(text("ALTER TABLE polypdt.matches ADD COLUMN IF NOT EXISTS external_event_slug TEXT NOT NULL DEFAULT ''"))
            await conn.execute(text("ALTER TABLE polypdt.matches ADD COLUMN IF NOT EXISTS external_market_id TEXT NOT NULL DEFAULT ''"))
            await conn.execute(text("ALTER TABLE polypdt.matches ADD COLUMN IF NOT EXISTS external_market_slug TEXT NOT NULL DEFAULT ''"))
            await conn.execute(text("ALTER TABLE polypdt.matches ADD COLUMN IF NOT EXISTS moneyline_volume NUMERIC(18,6) NOT NULL DEFAULT 0"))
            await conn.execute(text("ALTER TABLE polypdt.matches ADD COLUMN IF NOT EXISTS total_volume NUMERIC(18,6) NOT NULL DEFAULT 0"))
            await conn.execute(text("ALTER TABLE polypdt.matches ADD COLUMN IF NOT EXISTS latest_ts_utc TIMESTAMPTZ NOT NULL DEFAULT NOW()"))
            await conn.execute(text("ALTER TABLE polypdt.matches ADD COLUMN IF NOT EXISTS score_home INTEGER"))
            await conn.execute(text("ALTER TABLE polypdt.matches ADD COLUMN IF NOT EXISTS score_away INTEGER"))
            await conn.execute(text("ALTER TABLE polypdt.market_snapshots ADD COLUMN IF NOT EXISTS external_event_id TEXT NOT NULL DEFAULT ''"))
            await conn.execute(text("ALTER TABLE polypdt.market_snapshots ADD COLUMN IF NOT EXISTS external_event_slug TEXT NOT NULL DEFAULT ''"))
            await conn.execute(text("ALTER TABLE polypdt.market_snapshots ADD COLUMN IF NOT EXISTS external_market_id TEXT NOT NULL DEFAULT ''"))
            await conn.execute(text("ALTER TABLE polypdt.market_snapshots ADD COLUMN IF NOT EXISTS external_market_slug TEXT NOT NULL DEFAULT ''"))
            await conn.execute(text("ALTER TABLE polypdt.market_snapshots ADD COLUMN IF NOT EXISTS score_home INTEGER"))
            await conn.execute(text("ALTER TABLE polypdt.market_snapshots ADD COLUMN IF NOT EXISTS score_away INTEGER"))
            await conn.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS polypdt.tradings (
                      trading_id TEXT PRIMARY KEY,
                      strategy_name TEXT NOT NULL,
                      strategy_params JSONB NOT NULL,
                      affect_sports JSONB NOT NULL,
                      mode TEXT NOT NULL,
                      status TEXT NOT NULL,
                      initial_balance NUMERIC(18,6) NOT NULL DEFAULT 0,
                      account_alias TEXT,
                      created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                      updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    )
                    """
                )
            )
            await conn.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS polypdt.trading_accounts (
                      trading_id TEXT PRIMARY KEY,
                      balance NUMERIC(18,6) NOT NULL,
                      equity NUMERIC(18,6) NOT NULL,
                      available_cash NUMERIC(18,6) NOT NULL,
                      position_count INTEGER NOT NULL,
                      updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    )
                    """
                )
            )
            await conn.execute(text("ALTER TABLE polypdt.tradings ADD COLUMN IF NOT EXISTS initial_balance NUMERIC(18,6) NOT NULL DEFAULT 0"))
            await conn.execute(text("ALTER TABLE polypdt.tradings ADD COLUMN IF NOT EXISTS account_alias TEXT"))
            await conn.execute(
                text(
                    """
                    CREATE INDEX IF NOT EXISTS idx_tradings_mode_status
                    ON polypdt.tradings (mode, status)
                    """
                )
            )
            await conn.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS polypdt.trading_positions (
                      trading_id TEXT NOT NULL,
                      strategy_id TEXT NOT NULL,
                      match_id TEXT NOT NULL,
                      outcome TEXT NOT NULL,
                      entry_price NUMERIC(10,6) NOT NULL,
                      amount NUMERIC(18,6) NOT NULL,
                      updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                      PRIMARY KEY (trading_id, strategy_id, match_id, outcome)
                    )
                    """
                )
            )
            await conn.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS polypdt.trading_trades (
                      trade_id BIGSERIAL PRIMARY KEY,
                      trading_id TEXT NOT NULL,
                      strategy_id TEXT NOT NULL,
                      action TEXT NOT NULL,
                      match_id TEXT NOT NULL,
                      outcome TEXT NOT NULL,
                      price NUMERIC(10,6) NOT NULL,
                      amount NUMERIC(18,6) NOT NULL,
                      profit NUMERIC(18,6) NOT NULL DEFAULT 0,
                      status TEXT NOT NULL,
                      ts_utc TIMESTAMPTZ NOT NULL,
                      payload JSONB
                    )
                    """
                )
            )
            await conn.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS polypdt.trading_logs (
                      log_id BIGSERIAL PRIMARY KEY,
                      trading_id TEXT NOT NULL,
                      ts_utc TIMESTAMPTZ NOT NULL,
                      level TEXT NOT NULL,
                      message TEXT NOT NULL,
                      payload JSONB
                    )
                    """
                )
            )
            await conn.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS polypdt.collector_settings (
                      id SMALLINT PRIMARY KEY,
                      collection_interval_minutes INTEGER NOT NULL,
                      football_volume_threshold_k INTEGER NOT NULL,
                      basketball_volume_threshold_k INTEGER NOT NULL,
                      updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    )
                    """
                )
            )
        try:
            async with engine.begin() as conn:
                await conn.execute(text("CREATE EXTENSION IF NOT EXISTS timescaledb"))
                await conn.execute(
                    text(
                        """
                        SELECT create_hypertable(
                          'polypdt.market_snapshots',
                          by_range('snapshot_ts_utc'),
                          if_not_exists => TRUE
                        )
                        """
                    )
                )
        except Exception:
            pass
        self._schema_ready = True

    async def ensure_match(self, payload: dict) -> None:
        await self.ensure_schema()
        sql = text(
            """
            INSERT INTO polypdt.matches (
              match_id, sport, league, team_home, team_away, start_time_utc, status,
              moneyline_volume, total_volume, latest_ts_utc,
              external_event_id, external_event_slug, external_market_id, external_market_slug, score_home, score_away, updated_at
            )
            VALUES (
              :match_id, :sport, :league, :team_home, :team_away, :start_time_utc, :status,
              :moneyline_volume, :total_volume, :latest_ts_utc,
              :external_event_id, :external_event_slug, :external_market_id, :external_market_slug, :score_home, :score_away, NOW()
            )
            ON CONFLICT (match_id) DO UPDATE SET
              sport = EXCLUDED.sport,
              league = EXCLUDED.league,
              team_home = EXCLUDED.team_home,
              team_away = EXCLUDED.team_away,
              start_time_utc = EXCLUDED.start_time_utc,
              status = EXCLUDED.status,
              moneyline_volume = EXCLUDED.moneyline_volume,
              total_volume = EXCLUDED.total_volume,
              latest_ts_utc = EXCLUDED.latest_ts_utc,
              external_event_id = EXCLUDED.external_event_id,
              external_event_slug = EXCLUDED.external_event_slug,
              external_market_id = EXCLUDED.external_market_id,
              external_market_slug = EXCLUDED.external_market_slug,
              score_home = EXCLUDED.score_home,
              score_away = EXCLUDED.score_away,
              updated_at = NOW()
            """
        )
        data = dict(payload)
        data.setdefault("external_event_id", "")
        data.setdefault("external_event_slug", "")
        data.setdefault("external_market_id", "")
        data.setdefault("external_market_slug", "")
        data.setdefault("moneyline_volume", 0.0)
        data.setdefault("total_volume", 0.0)
        data.setdefault("latest_ts_utc", data["start_time_utc"])
        data.setdefault("score_home", None)
        data.setdefault("score_away", None)
        async with engine.begin() as conn:
            await conn.execute(sql, data)

    async def insert_tick(self, payload: dict) -> None:
        await self.ensure_schema()
        sql = text(
            """
            INSERT INTO polypdt.market_ticks (match_id, ts_utc, source, outcome, bid, ask, volume, extra)
            VALUES (:match_id, :ts_utc, :source, :outcome, :bid, :ask, :volume, CAST(:extra AS JSONB))
            """
        )
        async with engine.begin() as conn:
            await conn.execute(sql, payload)

    async def insert_market_snapshot(self, payload: dict) -> None:
        await self.ensure_schema()
        sql = text(
            """
            INSERT INTO polypdt.market_snapshots (
              match_id, snapshot_ts_utc, source, sport, status, start_time_utc, team_home, team_away,
              external_event_id, external_event_slug, external_market_id, external_market_slug, score_home, score_away,
              home_bid, home_ask, home_price, away_bid, away_ask, away_price, draw_bid, draw_ask, draw_price,
              moneyline_volume, total_volume, ingest_type, extra
            )
            VALUES (
              :match_id, :snapshot_ts_utc, :source, :sport, :status, :start_time_utc, :team_home, :team_away,
              :external_event_id, :external_event_slug, :external_market_id, :external_market_slug, :score_home, :score_away,
              :home_bid, :home_ask, :home_price, :away_bid, :away_ask, :away_price, :draw_bid, :draw_ask, :draw_price,
              :moneyline_volume, :total_volume, :ingest_type, CAST(:extra AS JSONB)
            )
            """
        )
        data = dict(payload)
        data.setdefault("external_event_id", "")
        data.setdefault("external_event_slug", "")
        data.setdefault("external_market_id", "")
        data.setdefault("external_market_slug", "")
        data.setdefault("score_home", None)
        data.setdefault("score_away", None)
        data["extra"] = json.dumps(payload.get("extra", {}))
        async with engine.begin() as conn:
            await conn.execute(sql, data)

    async def save_trading(self, payload: dict) -> None:
        await self.ensure_schema()
        sql = text(
            """
            INSERT INTO polypdt.tradings (
              trading_id, strategy_name, strategy_params, affect_sports, mode, status, initial_balance, account_alias, updated_at
            )
            VALUES (
              :trading_id, :strategy_name, CAST(:strategy_params AS JSONB), CAST(:affect_sports AS JSONB), :mode, :status, :initial_balance, :account_alias, NOW()
            )
            ON CONFLICT (trading_id) DO UPDATE SET
              strategy_name = EXCLUDED.strategy_name,
              strategy_params = EXCLUDED.strategy_params,
              affect_sports = EXCLUDED.affect_sports,
              mode = EXCLUDED.mode,
              status = EXCLUDED.status,
              initial_balance = EXCLUDED.initial_balance,
              account_alias = EXCLUDED.account_alias,
              updated_at = NOW()
            """
        )
        data = dict(payload)
        data["strategy_params"] = json.dumps(payload["strategy_params"])
        data["affect_sports"] = json.dumps(payload["affect_sports"])
        data.setdefault("initial_balance", 0.0)
        data.setdefault("account_alias", None)
        async with engine.begin() as conn:
            await conn.execute(sql, data)

    async def update_trading_status(self, payload: dict) -> None:
        await self.ensure_schema()
        sql = text(
            """
            UPDATE polypdt.tradings
            SET status = :status, updated_at = NOW()
            WHERE trading_id = :trading_id
            """
        )
        async with engine.begin() as conn:
            await conn.execute(sql, payload)

    async def delete_trading(self, trading_id: str) -> None:
        await self.ensure_schema()
        statements = [
            text("DELETE FROM polypdt.trading_positions WHERE trading_id = :trading_id"),
            text("DELETE FROM polypdt.trading_trades WHERE trading_id = :trading_id"),
            text("DELETE FROM polypdt.trading_logs WHERE trading_id = :trading_id"),
            text("DELETE FROM polypdt.trading_accounts WHERE trading_id = :trading_id"),
            text("DELETE FROM polypdt.tradings WHERE trading_id = :trading_id"),
        ]
        async with engine.begin() as conn:
            for statement in statements:
                await conn.execute(statement, {"trading_id": trading_id})

    async def upsert_trading_account(self, payload: dict) -> None:
        await self.ensure_schema()
        sql = text(
            """
            INSERT INTO polypdt.trading_accounts (trading_id, balance, equity, available_cash, position_count, updated_at)
            VALUES (:trading_id, :balance, :equity, :available_cash, :position_count, NOW())
            ON CONFLICT (trading_id) DO UPDATE SET
              balance = EXCLUDED.balance,
              equity = EXCLUDED.equity,
              available_cash = EXCLUDED.available_cash,
              position_count = EXCLUDED.position_count,
              updated_at = NOW()
            """
        )
        async with engine.begin() as conn:
            await conn.execute(sql, payload)

    async def replace_trading_positions(self, trading_id: str, positions: list[dict]) -> None:
        await self.ensure_schema()
        delete_sql = text("DELETE FROM polypdt.trading_positions WHERE trading_id = :trading_id")
        insert_sql = text(
            """
            INSERT INTO polypdt.trading_positions
              (trading_id, strategy_id, match_id, outcome, entry_price, amount, updated_at)
            VALUES
              (:trading_id, :strategy_id, :match_id, :outcome, :entry_price, :amount, NOW())
            """
        )
        async with engine.begin() as conn:
            await conn.execute(delete_sql, {"trading_id": trading_id})
            for row in positions:
                await conn.execute(insert_sql, row)

    async def insert_trading_trade(self, payload: dict) -> None:
        await self.ensure_schema()
        sql = text(
            """
            INSERT INTO polypdt.trading_trades
              (trading_id, strategy_id, action, match_id, outcome, price, amount, profit, status, ts_utc, payload)
            VALUES
              (:trading_id, :strategy_id, :action, :match_id, :outcome, :price, :amount, :profit, :status, :ts_utc, CAST(:payload AS JSONB))
            """
        )
        data = dict(payload)
        data["payload"] = json.dumps(payload.get("payload", {}))
        async with engine.begin() as conn:
            await conn.execute(sql, data)

    async def insert_trading_log(self, payload: dict) -> None:
        await self.ensure_schema()
        sql = text(
            """
            INSERT INTO polypdt.trading_logs
              (trading_id, ts_utc, level, message, payload)
            VALUES
              (:trading_id, :ts_utc, :level, :message, CAST(:payload AS JSONB))
            """
        )
        data = dict(payload)
        data["payload"] = json.dumps(payload.get("payload", {}))
        async with engine.begin() as conn:
            await conn.execute(sql, data)

    async def get_collector_settings(self) -> dict | None:
        await self.ensure_schema()
        sql = text(
            """
            SELECT collection_interval_minutes, football_volume_threshold_k, basketball_volume_threshold_k
            FROM polypdt.collector_settings
            WHERE id = 1
            """
        )
        async with engine.connect() as conn:
            row = (await conn.execute(sql)).mappings().first()
            if row is None:
                return None
            return {
                "collection_interval_minutes": int(row["collection_interval_minutes"]),
                "football_volume_threshold_k": int(row["football_volume_threshold_k"]),
                "basketball_volume_threshold_k": int(row["basketball_volume_threshold_k"]),
            }

    async def upsert_collector_settings(self, payload: dict) -> None:
        await self.ensure_schema()
        sql = text(
            """
            INSERT INTO polypdt.collector_settings
              (id, collection_interval_minutes, football_volume_threshold_k, basketball_volume_threshold_k, updated_at)
            VALUES
              (1, :collection_interval_minutes, :football_volume_threshold_k, :basketball_volume_threshold_k, NOW())
            ON CONFLICT (id) DO UPDATE SET
              collection_interval_minutes = EXCLUDED.collection_interval_minutes,
              football_volume_threshold_k = EXCLUDED.football_volume_threshold_k,
              basketball_volume_threshold_k = EXCLUDED.basketball_volume_threshold_k,
              updated_at = NOW()
            """
        )
        async with engine.begin() as conn:
            await conn.execute(sql, payload)
