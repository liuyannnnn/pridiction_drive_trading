CREATE SCHEMA IF NOT EXISTS polypdt;

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
);

CREATE INDEX IF NOT EXISTS idx_market_snapshots_match_time
  ON polypdt.market_snapshots (match_id, snapshot_ts_utc DESC);

CREATE INDEX IF NOT EXISTS idx_matches_status_sport
  ON polypdt.matches (status, sport);

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
);

CREATE INDEX IF NOT EXISTS idx_tradings_mode_status
  ON polypdt.tradings (mode, status);

CREATE TABLE IF NOT EXISTS polypdt.trading_accounts (
  trading_id TEXT PRIMARY KEY,
  balance NUMERIC(18,6) NOT NULL,
  equity NUMERIC(18,6) NOT NULL,
  available_cash NUMERIC(18,6) NOT NULL,
  position_count INTEGER NOT NULL,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS polypdt.trading_positions (
  trading_id TEXT NOT NULL,
  strategy_id TEXT NOT NULL,
  match_id TEXT NOT NULL,
  outcome TEXT NOT NULL,
  entry_price NUMERIC(10,6) NOT NULL,
  amount NUMERIC(18,6) NOT NULL,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  PRIMARY KEY (trading_id, strategy_id, match_id, outcome)
);

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
);

CREATE TABLE IF NOT EXISTS polypdt.trading_logs (
  log_id BIGSERIAL PRIMARY KEY,
  trading_id TEXT NOT NULL,
  ts_utc TIMESTAMPTZ NOT NULL,
  level TEXT NOT NULL,
  message TEXT NOT NULL,
  payload JSONB
);

CREATE TABLE IF NOT EXISTS polypdt.collector_settings (
  id SMALLINT PRIMARY KEY,
  collection_interval_minutes INTEGER NOT NULL,
  football_volume_threshold_k INTEGER NOT NULL,
  basketball_volume_threshold_k INTEGER NOT NULL,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
