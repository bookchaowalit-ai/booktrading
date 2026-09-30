# Upgrade Plan

Living backlog for incremental hardening passes. Read `README.md` (capital
protection mode) first; nothing here authorizes real-money trading.

## Current state

**Score: 7.5 / 10** (7 after pass 2, 6.5 after pass 1, 5 before). Pass 3 fixed failed signal orders being counted as paper trades, made strategy auth fail closed in production, and enforced gofmt/tidy in CI. Pass 2 closed the Go grid P0s (position cap, per-level idempotency, failed orders no longer counted as paper trades) and moved Next to 14.2.35. The three suites (Go, Next.js,
strategy Python) are green, and CI now runs the full offline strategy suite.
Before this pass, the Go race detector flaked in CI, CI ran only 2 of the
~50 strategy test files, the paper grid sync crashed with a `NameError` it
then silently swallowed, the grid backtester had look-ahead bias, and anyone
could reset the kill switch without authentication.

## Backlog

### P0
- Grid order placement is synchronous; an order that times out after the
  exchange accepted it is treated as failed. Reconcile open orders/fills from
  the exchange before re-arming a level.

### P1
- Backtester: ATR spacing and grid (re)anchoring still use bar *i*'s own
  close/high/low. Anchor on the bar open or the previous close, and resolve
  same-bar buy→sell round trips pessimistically.
- Money math uses `float` / `float64` everywhere (Go `model`, Python bots).
  Introduce `Decimal` (Python) or integer minor units at exchange boundaries,
  starting with order quantity/price rounding.
- CI pins `GO_VERSION: '1.21'` (EOL). Move to a supported Go and bump the
  `go` directive in `go.mod` together.
- Signal/auto order placement shares the grid's timeout problem (see P0);
  reconcile before re-sending an exit order.

### P2
- Strategy ruff debt: about 1,800 findings, most of them auto-fixable
  (imports, pyupgrade). Fix them per package and widen the CI ruff scope
  beyond `E9,F63,F7,F82`.
- Duplicate re-exports in `app/market_intel/sources/__init__.py` (F811).
- Frontend residual `npm audit` findings: `postcss` bundled inside `next`
  (build-time only) and `esbuild` under vitest 1.x (dev server only). Move
  vitest to 3.x; the postcss one clears when Next ships a newer bundle.
- `next lint` is deprecated in Next 15.5 and removed in 16. Migrate to the
  ESLint CLI with a flat `eslint.config.mjs` before any Next 16 move.
- Go `adapter/exchange`, `adapter/repository` and `adapter/grpcserver` have
  no tests. Add table tests around order request construction, using fake
  HTTP servers only.

## Done in this pass (pass 4)
- Frontend: Next 14.2.35 -> 15.5.27 (latest 15.x), React 18 -> 19,
  `@types/react*` 19, `eslint-config-next` 15.5.27, `@testing-library/react`
  16 (+ `@testing-library/dom`), and `lucide-react` 0.469 (first release with
  a React 19 peer). The only async request API use (`headers()` in
  `src/app/page.tsx`) is now awaited; `[lang]` params were already awaited.
  `npm audit` no longer lists Next advisories.
- Frontend installs are reproducible: `package-lock.json` is tracked, and CI
  and the Dockerfile use `npm ci`. CI also runs `next build` now.
- Verified: `npm run lint`, `tsc --noEmit`, `npm test` (37 passed), `npm run
  build`.

## Done in pass 3
- Go signal/auto: `executeSignalTrade` now delegates to `signalTradeStep`.
  A failed order is reported as `ORDER_FAILED` activity, is not counted in
  `tradesCount`/`TotalTrades`, is never relabelled `PAPER_SIGNAL_*`, and
  never opens an auto-mode position. Tests: `signal_trade_test.go`.
- Strategy: `require_auth` fails closed when `AUTH_TOKEN` is empty and
  `ENVIRONMENT=production` (set in `docker-compose.prod.yml`); startup logs
  an error. Tests: `tests/test_require_auth_production.py`.
- CI: `go mod tidy` no longer mutates go.mod silently (tidy + `git diff
  --exit-code`), and a `gofmt -l` gate was added; all 42 unformatted backend
  files were formatted.
- Verified: `go vet`, `go test -race ./...`, strategy `pytest -q` (491
  passed) and the CI ruff gate.

## Done in pass 1
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

## Done in pass 2
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
