CREATE SCHEMA IF NOT EXISTS polypdt;

CREATE TABLE IF NOT EXISTS polypdt.matches (
  match_id TEXT PRIMARY KEY,
  sport TEXT NOT NULL,
  league TEXT NOT NULL,
  team_home TEXT NOT NULL,
  team_away TEXT NOT NULL,
  start_time_utc TIMESTAMPTZ NOT NULL,
  status TEXT NOT NULL,
  source_pm_event_id TEXT,
  source_goalserve_event_id TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS polypdt.match_mapping (
  mapping_id BIGSERIAL PRIMARY KEY,
  match_id TEXT NOT NULL REFERENCES polypdt.matches(match_id),
  pm_event_id TEXT NOT NULL,
  goalserve_event_id TEXT NOT NULL,
  score NUMERIC(6,5) NOT NULL,
  decision TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS polypdt.orders (
  order_id TEXT PRIMARY KEY,
  match_id TEXT NOT NULL REFERENCES polypdt.matches(match_id),
  strategy_id TEXT NOT NULL,
  mode TEXT NOT NULL,
  side TEXT NOT NULL,
  price NUMERIC(10,6) NOT NULL,
  size NUMERIC(18,6) NOT NULL,
  status TEXT NOT NULL,
  external_order_id TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS polypdt.positions (
  position_id BIGSERIAL PRIMARY KEY,
  match_id TEXT NOT NULL REFERENCES polypdt.matches(match_id),
  strategy_id TEXT NOT NULL,
  outcome TEXT NOT NULL,
  size NUMERIC(18,6) NOT NULL,
  avg_price NUMERIC(10,6) NOT NULL,
  realized_pnl NUMERIC(18,6) NOT NULL DEFAULT 0,
  unrealized_pnl NUMERIC(18,6) NOT NULL DEFAULT 0,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS polypdt.strategy_runs (
  run_id BIGSERIAL PRIMARY KEY,
  strategy_id TEXT NOT NULL,
  mode TEXT NOT NULL,
  status TEXT NOT NULL,
  config JSONB NOT NULL,
  started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  ended_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS polypdt.trade_logs (
  log_id BIGSERIAL PRIMARY KEY,
  run_id BIGINT REFERENCES polypdt.strategy_runs(run_id),
  match_id TEXT,
  level TEXT NOT NULL,
  message TEXT NOT NULL,
  payload JSONB,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

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
);

CREATE INDEX IF NOT EXISTS idx_market_ticks_match_time
  ON polypdt.market_ticks (match_id, ts_utc DESC);

CREATE INDEX IF NOT EXISTS idx_matches_status_sport
  ON polypdt.matches (status, sport);

CREATE INDEX IF NOT EXISTS idx_orders_strategy_status
  ON polypdt.orders (strategy_id, status);
