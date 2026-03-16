# PM Requirement Gap Analysis

Reference: `需求.md`
Date: 2026-03-16
Scope: simulation-only alignment round

## Summary

This round brings the codebase into a more consistent simulation-phase state:
- collector settings are resilient when the database is unavailable and refresh immediately when streaming is active
- simulation APIs now model multiple trading instances instead of silently dropping all but the first strategy
- the right-side trading panel create/start/stop/delete actions now use backend tradings APIs instead of local fake state
- existing simulation tradings can now update strategy parameters through backend partial-update APIs
- match detail trade/log panes now request backend data scoped to the selected match
- runtime schema bootstrap and `infra/sql/init_polypdt.sql` now describe the same core simulation entities

The project is still short of the original end-state in `需求.md`, mainly around real trading, Goalserve server-side verification/history backfill, PM-vs-Goalserve matching workflow, and startup recovery of persisted trading instances.

## Database Fitness

### Reasonable / aligned now
- `matches`
  - fits left rail and match header requirements with sport/league/teams/start/status/score/volume/latest refresh time plus PM external IDs
- `market_ticks`
  - supports short-term tick reads and debugging
- `market_snapshots`
  - fits minute-level sampled chart/history storage and Timescale hypertable use
- `tradings`
  - now represents trading instances rather than strategy source, including mode, status, JSON params, sports scope, initial balance, and future account alias slot
- `trading_accounts`, `trading_positions`, `trading_trades`, `trading_logs`
  - match the right panel and detail pane needs for simulation state
- `collector_settings`
  - supports threshold and interval persistence
- `match_mapping`
  - reserved for PM/Goalserve linkage results and confidence scoring

### Still missing or partial
- no durable restore path from database back into in-memory trading instances on startup
- no historical Goalserve tables/job bookkeeping yet
- no explicit real-trading account credential tables because this round intentionally excludes real trading
- no dedicated sampled orderbook/outcome price history beyond current snapshot model

## Requirement-by-Requirement Status

### 1. Basic environment
- Frontend under `front/`: Implemented baseline, now more tightly bound to backend simulation data
- `polyapi/` and `gsapi/` docs mirror: Present
- PostgreSQL/Timescale schema under `polypdt`: Implemented for simulation-phase entities
- Redis for high-frequency caching: Present in runtime design, partially used for live tick caching

### 2. System overview
- Multi-strategy simulation framework: Partially implemented
- Real trading framework: Deferred this round by request
- Sports limited to football/basketball: Implemented in backend/runtime scope, frontend trading creation now restricted accordingly

### 3. Left match rail
- Live/pre grouping: Implemented
- Threshold-based collection interval: Implemented
- Future match horizon 24h: Partially implemented in current market selection logic; should be re-verified against live data on server
- PM websocket live updates: Implemented skeleton
- Card bottom fields for moneyline volume/total volume/latest refresh: Backing fields implemented in schema and APIs

### 4. Middle match detail
- Match metadata/time/teams/volume/outcome prices: Implemented baseline
- ECharts moneyline chart: Implemented
- Goalserve detail block: Implemented skeleton/fallback, real server validation still deferred
- Trade records area for current match: Implemented for backend-backed current-match filtering.
- Log area for current match: Implemented for backend-backed current-match filtering.

### 5. Right trading panel
- Create simulation trading with strategy and params: Implemented via backend tradings APIs
- Create real trading with PM account alias: Deferred this round
- Display account funds/positions/trades: Implemented for simulation instances
- Start/stop/delete bound to backend: Implemented
- Edit existing strategy parameters: Implemented for simulation tradings through backend partial-update semantics

### 6. External data source: Goalserve
- Websocket connector skeleton with token refresh handling: Implemented in code structure
- HTTP history download and database storage: Deferred
- Local testing: Blocked by IP whitelist, still requires server-side validation

### 7. Strategy architecture requirements
- Strategy files isolated: Implemented
- Trading vs strategy separation: Implemented more clearly this round
- Strategy receives normalized market data and emits signals: Implemented for current simulation flow
- JSON-configured per-trading strategy params: Implemented
- Multiple trading instances may use same strategy class: Implemented
- Independent strategy execution isolation: Partial. Instances have isolated queues/state, but there is not yet a dedicated thread/process isolation model.

### 8. Performance and async requirements
- Async database/cache path: Implemented baseline
- Redis-first high-frequency write and sampled DB persistence: Partial. Cache write exists; broader resampling and replay strategy still needs hardening.
- Event broadcast to strategies immediately: Implemented via dispatcher loop and per-instance queues
- Independent thread/process strategy workers: Deferred. Current isolation is coroutine/task-based.

### 9. Match mapping requirement
- Rule-based PM/Goalserve mapping persistence point: Implemented as schema slot
- Actual matching workflow with confidence tiers/manual review: Deferred
- AI-assisted mapping: Deferred by design

### 10. Initial test strategies from `需求.md`
- Pre-match spread/retracement strategy: Implemented
- Football first-goal/retracement strategy: Implemented
- Settlement at match end: Implemented in simulator
- Win rate definition as positive-profit trades / total closed trades: Implemented in trading snapshots

## Highest-Priority Remaining Gaps

1. Add repository-backed recovery of persisted trading metadata on startup.
2. Validate PM live market selection rules, especially the 24-hour future filter, against real upstream data.
3. Implement Goalserve historical HTTP ingestion and server-side live validation.
4. Add real-trading account configuration and execution path in a separate phase.
