CREATE EXTENSION IF NOT EXISTS timescaledb;

SELECT create_hypertable(
  'polypdt.market_snapshots',
  by_range('snapshot_ts_utc'),
  if_not_exists => TRUE
);
