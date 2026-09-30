# Upgrade Plan

Living backlog for incremental hardening passes. Read `README.md` (capital
protection mode) first; nothing here authorizes real-money trading.

## Current state

**Score: 6.5 / 10** (was 5 before pass 1). The three suites (Go, Next.js,
strategy Python) are green, and CI now runs the full offline strategy suite.
Before this pass, the Go race detector flaked in CI, CI ran only 2 of the
~50 strategy test files, the paper grid sync crashed with a `NameError` it
then silently swallowed, the grid backtester had look-ahead bias, and anyone
could reset the kill switch without authentication.

## Backlog

### P0
- Go grid loop (`backend/internal/domain/service/implementation.go`,
  `executeGridTrading`) places an order on every 5s tick while price stays in
  the bottom/top band. It has no inventory or position cap and never
  de-duplicates per level. Add a per-level fill state and a max-position check
  before any real order.
- Upgrade `next` from 14.1.0 (npm flags a published security advisory) to the
  latest patched 14.2.x. Verify with `npm run lint && npx tsc --noEmit &&
  npm test && npm run build`.
- The Go `executeSignalTrade` / grid fallback reports a *failed real order*
  as a "PAPER" trade and counts it in `tradesCount`. Record it as a failed
  order instead, so evidence and PnL are not inflated.

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
