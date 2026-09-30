# Upgrade Plan

Living backlog for incremental hardening passes. Read `README.md` (capital
protection mode) first; nothing here authorizes real-money trading.

## Current state

**Score: 7 / 10** (6.5 after pass 1, 5 before). Pass 2 closed the Go grid P0s (position cap, per-level idempotency, failed orders no longer counted as paper trades) and moved Next to 14.2.35. The three suites (Go, Next.js,
strategy Python) are green, and CI now runs the full offline strategy suite.
Before this pass, the Go race detector flaked in CI, CI ran only 2 of the
~50 strategy test files, the paper grid sync crashed with a `NameError` it
then silently swallowed, the grid backtester had look-ahead bias, and anyone
could reset the kill switch without authentication.

## Backlog

### P0
- Next 14.2.35 is the last 14.x, but `npm audit` still lists Next advisories
  fixed only in 15.x/16.x (image optimizer, RSC DoS, middleware bypass).
  Plan a Next 15 migration (async request APIs, React 19) in its own pass.
- `executeSignalTrade` (SIGNAL/AUTO modes) still labels a failed real order
  as "PAPER" and counts it in `tradesCount`; apply the same fix as the grid
  (`gridStep`).
- Grid order placement is synchronous; an order that times out after the
  exchange accepted it is treated as failed. Reconcile open orders/fills from
  the exchange before re-arming a level.

### P1
- `require_auth` in `strategy/infrastructure/api/app.py` allows every caller
  when `AUTH_TOKEN` is unset (dev mode). Make it fail closed in production, for
  example by requiring `AUTH_TOKEN` whenever `ENVIRONMENT=production`.
- Backtester: ATR spacing and grid (re)anchoring still use bar *i*'s own
  close/high/low. Anchor on the bar open or the previous close, and resolve
  same-bar buy→sell round trips pessimistically.
- Money math uses `float` / `float64` everywhere (Go `model`, Python bots).
  Introduce `Decimal` (Python) or integer minor units at exchange boundaries,
  starting with order quantity/price rounding.
- `gofmt -l backend/internal` lists 11 files. Format them and add a
  `gofmt -l` check to CI.
- CI pins `GO_VERSION: '1.21'` and runs `go mod tidy` before testing. Drop
  the tidy step (it mutates `go.mod` in CI) and use `go mod verify` only.

### P2
- Strategy ruff debt: about 1,800 findings, most of them auto-fixable
  (imports, pyupgrade). Fix them per package and widen the CI ruff scope
  beyond `E9,F63,F7,F82`.
- Duplicate re-exports in `app/market_intel/sources/__init__.py` (F811).
- `frontend/package-lock.json` is gitignored, so installs are not
  reproducible; commit it and switch CI to `npm ci`.
- Go `adapter/exchange`, `adapter/repository` and `adapter/grpcserver` have
  no tests. Add table tests around order request construction, using fake
  HTTP servers only.

## Done in this pass (pass 1)
- Go: fixed a data race and a stale-goroutine bug in `BotServiceImpl`. Each
  run now gets its own context and config snapshot, so a Stop→Start can no
  longer leave the old loop trading. `Start` validates grid params: before
  this, `gridLevels=0` made the grid size +Inf and turned every tick into a
  BUY. `Start` also no longer reports "running" when persisting status fails.
  Zero or negative prices never produce orders, and no order is placed after
  Stop. Auto-mode keeps tracking a position whose exit order failed. Tests
  are in `bot_safety_test.go`.
- Strategy: fixed the `newly_fill_buys` NameError that disabled
  `GridBot._sync_state` fill reconciliation (`tests/test_grid_sync.py`).
- Strategy: kill-switch and circuit-breaker resets now fail closed (they need
  a configured token and a matching token). Arb paper reset requires auth.
  Token comparison uses `hmac.compare_digest`
  (`tests/test_safety_reset_auth.py`).
- Strategy: real/dca/trend bots default to safety mode unless
  `BINANCE_TH_USE_TESTNET=false` is set explicitly
  (`tests/test_mainnet_default.py`).
- Backtester: the entry gate uses only closed bars (i-1), and MTF confirmation
  uses only fully closed higher-TF candles. Buy fees are now charged, net and
  gross PnL are consistent, and FIFO cost basis is matched by quantity
  (`tests/test_grid_backtester.py`).
- CI: the strategy job runs the full offline pytest suite plus a ruff gate
  for undefined names and syntax errors.

## Done in this pass (pass 2)
- Go grid: new per-run `gridBook` (`implementation.go`). A BUY is placed at
  most once per grid level until a SELL releases it (idempotent, no more
  order-per-tick), base inventory is capped at `quantity * gridLevels`, the
  quote exposure is capped by `Investment` when set, SELL needs inventory
  (no naked sells), and a failed order is reported as `ORDER_FAILED` instead
  of a counted "PAPER" trade. Tests: `grid_position_test.go`; verified with
  `go vet` and `go test -race ./...`.
- Frontend: `next` and `eslint-config-next` 14.1.0 -> 14.2.35 (latest 14.x,
  no major bump). Verified `npm run lint`, `tsc --noEmit`, `npm test`
  (37 passed), `npm run build`.
