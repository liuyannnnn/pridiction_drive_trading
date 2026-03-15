CREATE EXTENSION IF NOT EXISTS timescaledb;

SELECT create_hypertable(
  'polypdt.market_ticks',
  by_range('ts_utc'),
  if_not_exists => TRUE
);
