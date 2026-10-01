# Trading — Phase 4 Walk-Forward Strategy Validation

Read-only research tooling that answers one question: **is the EMA/ADX
futures strategy consistent out-of-sample**, before leverage or real money
is ever considered.

## Safety statement

- **Read-only.** No exchange credentials, no API keys, no env vars, no auth
  headers anywhere in this directory.
- **No order placement, no mainnet execution.** The only network code is
  `data.py --fetch`, which downloads *public* Binance market data (klines
  and funding rates) from unauthenticated endpoints. The lake-first path
  (`lake_source.py`, `signal_report.py`) reads local Silver Parquet only.
- **Research only. Nothing here is investment advice.**

## Layout

| File | Purpose |
|---|---|
| `futures_backtest.py` | Core EMA/ADX backtest engine (importable + CLI) |
| `data.py` | CSV cache + public Binance fetch (the only network code) |
| `walk_forward.py` | Phase 4 walk-forward validator (importable + CLI) |
| `fixtures.py` | Deterministic synthetic data generator (seed 42) |
| `fixtures/sample_1h.csv` | Committed 9000-bar 1h fixture (3 regimes + crash) |
| `fixtures/sample_funding.csv` | Committed 8h funding-rate fixture |
| `tests/` | Stdlib `unittest` suites, no network, no pytest |

Python 3 standard library only — CI needs no pip installs. The lake bridge
(`lake_source.py`, `signal_report.py`) also needs the Solo Empire
`infra/scripts/data_lake` runtime; it is found by walking up from this folder
(the normal nested checkout) or through `SOLO_EMPIRE_ROOT`. Reports default to
`$SOLO_EMPIRE_ROOT/data/generated/reports/trading`.

This folder moved here from Solo Empire
`projects/money/finance/book-finance/trading/` on 2026-10-01. It is research
tooling only: it is excluded from the strategy Docker image
(`strategy/.dockerignore`) and from the strategy pytest run (`testpaths`).

## Quickstart

```bash
cd strategy/research

# (optional) download real public data — no credentials needed
python3 data.py --fetch --symbol BTCUSDT --interval 1h --market futures \
  --start 2025-01-01 --end 2025-07-01 --out /tmp/btc_1h.csv \
  --funding-out /tmp/btc_funding.csv

# run the walk-forward validator (fixed grid and train-selected modes)
python3 walk_forward.py --csv /tmp/btc_1h.csv --funding-csv /tmp/btc_funding.csv \
  --mode fixed  --out /tmp/report_fixed.md  --json /tmp/report_fixed.json
python3 walk_forward.py --csv /tmp/btc_1h.csv --funding-csv /tmp/btc_funding.csv \
  --mode select --out /tmp/report_select.md --json /tmp/report_select.json

# or use the committed synthetic fixture (no network)
python3 walk_forward.py --csv fixtures/sample_1h.csv \
  --funding-csv fixtures/sample_funding.csv --mode select \
  --out /tmp/report.md --json /tmp/report.json
```

The CLI always exits 0 — it is research tooling. PASS/FAIL lives in the
report's **Gate** column and the JSON `gate.verdict` fields, with explicit
failure reasons per variant.

## Lake-first daily paper signal

The production path reads market data from the Data Lakehouse instead of
calling an exchange from this directory:

```text
Binance public klines / fundingRate (keyless)
  -> book-crypto-data  (python -m book_crypto.ohlcv)   Bronze crypto_ohlcv / crypto_funding
  -> infra/scripts/data_lake/silver.py                 Silver, deduplicated + OHLC quality gate
  -> lake_source.py                                    closed bars, gap/staleness checks
  -> walk_forward.py / signal_report.py                gate + PAPER decision + journal
```

```bash
task trading:daily            # capture (incremental) -> Silver -> paper signal
task trading:lake:status      # coverage, gaps, funding points per symbol
task trading:walk-forward -- --lake-symbol BTCUSDT --mode select --out /tmp/wf.md
task test:trading
```

| File | Purpose |
|---|---|
| `lake_source.py` | Load Silver bars/funding, dedupe overlapping parts, report gaps (needs DuckDB/PyArrow runtime) |
| `signal_report.py` | Daily PAPER decision per symbol, Markdown/JSON report, idempotent paper journal, track-record scoring |

Decision rules:

- `NO_TRADE` when history is shorter than train+test, the last closed bar is
  more than two bars old, a gap falls inside the latest train window, gaps
  exceed 0.5% of history, or the walk-forward risk gate fails.
- Otherwise `PAPER_LONG` / `PAPER_SHORT` / `PAPER_FLAT` from the variant
  selected on the most recent train window only, read at the last closed bar.
- The paper track record scores consecutive journal entries at 1x notional
  with costs. It is met only after 90+ days with a positive return that beats
  buy-and-hold over the same span. Meeting it is evidence for review, not
  permission to trade real money.

Reports and the journal are written to `data/generated/reports/trading/`
(ignored by Git).

## Methodology

- **Walk-forward scheme.** Rolling `[train][test]` windows sliding by
  `step` (defaults: train 2160 bars ≈ 90d, test 720 ≈ 30d, step 720). In
  `fixed` mode every grid variant is scored on every test window. In
  `select` mode the best variant is chosen **on the train slice only** (by
  Sharpe; ties broken by lower max drawdown, then grid order) and that
  frozen variant is evaluated on the test slice — the selection function
  receives only the train slice, so the test slice cannot leak into
  parameter choice.
- **Execution at next open.** A signal observed at the close of bar *i* is
  executed at the open of bar *i+1*. Indicator values at bar *i* use bars
  `0..i` only (EMA seeded by SMA of the first N closes; ADX by Wilder's
  smoothing). One position at a time.
- **Cost model.** Every fill pays `notional * taker_fee_bps`; slippage is
  baked into the fill price (`price * (1 ± slippage_bps)`). Futures funding
  is charged at each 8h boundary crossed while a position is open
  (`notional * rate`, positive rate costs longs and pays shorts), from the
  funding series or the constant `funding_rate_bps_per_8h` fallback.
- **Sizing.** Futures notional = `equity * leverage` (recomputed at entry);
  spot notional = `equity` (no borrowing, long only regardless of mode;
  spot ignores leverage).
- **Liquidation approximation.** Checked once per bar at the close: if the
  mark-to-market loss reaches `posted_margin - maintenance_margin_rate *
  notional`, the position is force-closed at that bar's close (not the
  exact liquidation price) and the loss is capped at the posted margin.
  Deliberately simple and documented; real venues liquidate intra-bar.
- **Risk gate.** A variant PASSes only if its median OOS window return
  beats the spot buy-and-hold-after-costs baseline median **and** max
  drawdown ≤ 25% **and** stitched-OOS Sharpe ≥ 0 **and** profitable windows
  ≥ 40% (all configurable via `--gate-*` flags). Every variant row carries
  explicit failure reasons.

## Tests

```bash
python3 tests/futures_backtest_test.py
python3 tests/walk_forward_test.py
python3 tests/data_test.py
```

Coverage includes: hand-computed indicator values, entry at next-bar open,
exact fee/slippage accounting, funding sign for long and short, liquidation
loss capping, spot ignoring leverage, determinism, truncation no-look-ahead
proof, test-slice-invisibility proof for `select` mode, risk-gate reasons
and overrides, and byte-exact fixture reproducibility (tests never
regenerate data at runtime).

---

*Research tooling only — not investment advice. Read-only: no exchange
credentials, no order placement, no mainnet execution anywhere in this
code.*

## Local documents

- [performance-log-template](performance-log-template.md)
