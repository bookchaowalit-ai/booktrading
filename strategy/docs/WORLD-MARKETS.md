# World Markets — read-only research lane

This lane adds a bounded World Markets adapter for market research. It is
explicitly **read-only**: it does not connect a wallet, sign Solana
transactions, place orders, reset the existing kill switch, or claim that a
displayed price gap is profitable.

## What it does

1. Fetches paginated event data from the configurable `/events` endpoint.
2. Normalizes nested event/market payloads into a stable `WorldMarket` model.
3. Optionally subscribes to the provider's `world_prices` WebSocket channel.
4. Writes exact response bytes to immutable landing storage and a Bronze
   Parquet row before exposing normalized results to the scanner.
5. Imports a permitted local JSON response when the provider read endpoint is
   unavailable, using the same landing and Bronze contract.
6. Produces paper-only watches for gross YES+NO complement gaps.

Quotes with impossible binary prices, inverted bid/ask, negative metrics, or
incomplete resolution context are retained for audit but excluded from paper
signals.  A market must expose a question/title, resolution source, and strike
or close time before the conservative scanner considers it a candidate.

Fees, slippage, partial fills, stale quotes, market rules, oracle resolution,
counterparty risk, and settlement timing are not solved by the live read path.
The offline replay below provides a deterministic starting point for a paper
ledger; it is not a profitability claim.

## Local usage

The normal run requires a lake root. Keep credentials out of shell history and
inject the optional API key through the environment or an approved secret
resolver:

```bash
export WORLD_MARKETS_LANDING_DIR=/tmp/world-markets-lake
export WORLD_MARKETS_API_KEY=  # optional; do not paste it into docs or chat
python strategy/scripts/world_market_research.py --category crypto --json
```

For an explicitly ephemeral smoke test:

```bash
python strategy/scripts/world_market_research.py --no-lake --category crypto
```

The command returns exit code `2` for a blocked API request such as `403`; it
does not fall back to webpage scraping or attempt to bypass Cloudflare.

When API access is unavailable, import a JSON response that you obtained from
an approved source or export process. The import is offline, requires a local
lake path, validates the JSON before writing, preserves the original bytes,
and derives an idempotent identity from the SHA-256 checksum:

```bash
python strategy/scripts/world_market_import.py \
  --payload /absolute/path/to/world-events.json \
  --landing-dir /absolute/path/to/world-markets-lake \
  --received-at 2026-09-12T10:00:00Z --json
```

The input must be a World event response in JSON object/array form. HTML pages,
browser cookies, authorization headers, and wallet data are not accepted as
market input. The output contains the manifest key and ranked paper watches;
use that manifest with the reviewed thesis flow below.

## Backend API for connected producers

The same import contract is available through the strategy FastAPI service so a
dashboard, scheduler, approved World-data producer, or future connector can
send one response over HTTP. Configure the service with a private backend
token and a lake root before exposing it:

```bash
export AUTH_TOKEN='use-a-secret-from-your-secret-manager'
export WORLD_MARKETS_LANDING_URI=/absolute/path/to/world-markets-lake
```

Check the integration without revealing provider credentials:

```bash
curl -H "Authorization: Bearer $AUTH_TOKEN" \
  http://localhost:8000/api/v1/world/status
```

Submit the exact JSON body received from an approved producer:

```bash
curl -X POST \
  "http://localhost:8000/api/v1/world/import?received_at=2026-09-12T10:00:00Z" \
  -H "Authorization: Bearer $AUTH_TOKEN" \
  -H "Content-Type: application/json" \
  --data-binary @/absolute/path/to/world-events.json
```

The API authenticates before reading or writing, validates the body, preserves
the exact bytes in the World landing/Bronze/manifest contract, and returns
normalized markets plus paper-only signals. It deliberately has no order,
wallet, claim, or execution endpoint; other services should consume this
contract and keep any later execution decision behind a separate reviewed
boundary.

Before collecting a longer sample, run the bounded live readiness check:

```bash
python strategy/scripts/world_market_readiness.py --category crypto --json
```

It checks API access, response normalization, quote/resolution quality, and
the configured lake path. A `403` means approved read access is still needed;
the check does not print response bodies or credential values. `--no-lake` can
probe access and parsing only, but it cannot report paper readiness.

## Offline replay / paper backtest

Use a checked-in or locally controlled JSONL fixture to replay observations and
settlements without contacting World or using a wallet:

```bash
python strategy/scripts/world_market_replay.py \
  strategy/tests/fixtures/world_markets/replay.jsonl --json
```

Each line contains an `observed_at` timestamp plus `markets` and/or
`settlements`. Settlement rows are processed chronologically, so a future
settlement cannot create a same-timestamp entry. The report models per-leg
fees, optional slippage, displayed ask sizes, partial fills, stale quote age,
and unresolved exposure. It labels all P&L as paper units. If ask sizes are
missing, the `unknown_size_fill_ratio` assumption is reported explicitly and
should be replaced with observed depth before relying on the result. Tune the
assumptions explicitly, for example:

```bash
python strategy/scripts/world_market_replay.py \
  strategy/tests/fixtures/world_markets/replay.jsonl \
  --fee-bps-per-leg 50 --slippage-bps-per-leg 10 \
  --max-quote-age-seconds 30 --unknown-size-fill-ratio 0.25
```

## Configuration

| Variable | Default | Purpose |
|---|---|---|
| `WORLD_MARKETS_API_BASE` | `https://markets-api-proxy.world-xyz.workers.dev/api/v1` | HTTP read endpoint |
| `WORLD_MARKETS_WS_URL` | `wss://markets-api-proxy.world-xyz.workers.dev/api/v1/ws` | Price stream endpoint |
| `WORLD_MARKETS_API_KEY` | unset | Optional provider credential, never logged |
| `WORLD_MARKETS_API_KEY_HEADER` | `Authorization` | Header name |
| `WORLD_MARKETS_API_KEY_SCHEME` | `Bearer` | Authorization scheme |
| `WORLD_MARKETS_LANDING_DIR` | unset | Local immutable lake root |
| `WORLD_MARKETS_LANDING_URI` | unset | `file://` or approved `s3://` lake URI |

Cloud landing remains fail-closed until the shared cloud-write gate and
attestations are explicitly enabled.

## Unified scanner integration

The World source is opt-in so an unavailable provider does not degrade the
existing default scanner:

```python
from app.market_intel.scanner import MarketScanner

scanner = MarketScanner(enabled_sources=["world"])
result = await scanner.scan_all()
```

`confidence` on the unified opportunity is labelled
`data_quality_not_probability`; it must never be interpreted as a probability
of winning.
