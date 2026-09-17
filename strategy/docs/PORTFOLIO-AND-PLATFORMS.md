# Multi-platform portfolio and rewards lane

This lane is the common foundation for World Markets, Fomo, existing exchange
adapters, and future venues. It is intentionally paper-only: a registry entry
does not grant permission to trade, withdraw, or use a wallet.

## What was added

- `app/portfolio/registry.py` keeps one versioned capability record per
  platform. It records whether market data, paper trading, testnet execution,
  balance reads, and reward tracking are available.
- `app/portfolio/models.py` defines provider-neutral `PaperTrade`,
  `RewardEntry`, `PaperCapitalAccount`, and `PortfolioSnapshot` models. Each
  event carries an account alias, currency, and explicit paper mode.
- `app/portfolio/ledger.py` provides an in-memory, idempotent ledger with no
  network or broker side effects. Registered capital accounts calculate
  reserved risk, realized P&L, and available paper capital independently.
- `app/portfolio/finance.py` produces deterministic, non-cash finance
  projections. It is the hand-off contract to the central finance boundary;
  it never posts a real financial transaction.
- `app/portfolio/alpha.py` normalizes a settled selective-alpha journal row
  into one paper trade and one finance projection using the journal request ID
  as the stable source reference.
- `app/portfolio/integrations.py` converts World replay positions and reads
  legacy `AirdropTracker` rows into the common ledger. Invalid reward rows are
  returned as quarantine metadata without copying the raw task.
- `app/portfolio/replay.py` replays bounded versioned JSONL fixtures.
- `scripts/portfolio_registry.py` and `scripts/portfolio_replay.py` are
  read-only inspection tools.

The ledger keeps these numbers separate:

1. realized paper P&L after the trade's fee and slippage;
2. unrealized paper P&L only when an explicit mark is supplied;
3. realized reward value only after a reward is marked `claimed` and has a
   realized value;
4. pending reward estimates, which are never presented as cash; and
5. tracked costs.

Each trade and reward also keeps an explicit `account_scope`. A World paper
account, a Fomo paper account, and a reward/wallet alias therefore cannot be
silently combined. If a caller omits the alias, the model derives one from the
platform (`paper-world_xyz`, `rewards-airdrop_rewards`) rather than using a
single cross-platform default. `PaperCapitalAccount` calculates:

```text
available paper capital = starting capital + realized paper P&L - open reserved risk
```

Reward estimates and reward costs remain in the reward lane; they do not change
paper trading capital unless a future, separately reviewed cash-account
adapter explicitly models that transfer.

Money is grouped by `quote_currency`/`currency`. When more than one currency
is present, the aggregate money fields are left empty unless a reporting
currency is explicitly selected; the ledger never applies an unverified FX
rate.

World's two-leg `BUY_BOTH_REVIEW` position is represented as one synthetic
paper position whose entry price is the gross cost per filled unit. Its fees,
slippage, fill ratio, and source ticker remain in metadata, so the normalized
paper P&L reconciles to the World replay result without pretending that a live
order was placed.

The legacy airdrop tracker uses text such as `$500-5000` and statuses such as
`completed`. The converter records the lower bound as a pending estimate,
maps `completed` to `eligible`, and requires explicit realized value before a
reward can enter the claimed total. Textual cost estimates are retained as
notes; only a numeric `actual_cost` is counted as spent.

## Current capability map

| Platform | State | Current scope | Next gate |
| --- | --- | --- | --- |
| `world_xyz` | `blocked` | Existing read-only adapter and offline replay; the bounded live readiness probe returned HTTP 403 without approved access | Approved read access plus quote, size, and settlement validation |
| `fomo` | `planned` | Placeholder only; no API, order, wallet, or reward semantics are assumed | Official URL, API documentation, permission, and settlement model |
| `polymarket` | `paper` | Existing research/paper surfaces | Paper reconciliation and venue policy checks |
| `binance_global` | `testnet` | Research, paper, and testnet capability is represented; live is disabled | Independent testnet reconciliation and risk approval |
| `binance_th` | `paper` | Paper registry entry only | Venue-specific order, balance, and compliance contract |
| `bitkub` | `paper` | Paper registry entry only | Venue-specific order, balance, and compliance contract |
| `airdrop_rewards` | `read_only` | Candidate/eligible/claimed reward tracking | Source evidence and claim proof |

Fomo is deliberately not guessed from its name. Once the official endpoint is
known, add a separate adapter and update its capability record; do not turn the
placeholder into an execution path by changing a status flag alone.

## Data and control flow

```text
provider adapter
    -> exact landing / Bronze evidence
    -> normalized market or reward record
    -> strategy and risk evaluation
    -> paper portfolio or reward ledger
    -> reviewable snapshot
    -> non-cash finance projection for controlled central-finance import
    -> (future, separately gated) testnet/live executor
```

Finance projections are deliberately marked `activity_mode=paper`,
`cash_effect=false`, and `posting_status=separate_paper_lane`. A central
finance importer may reconcile these records to an explicit account alias, but
must not add them to cash income/expense totals automatically. This prevents a
paper win or a pending airdrop estimate from being counted as money twice.

For rewards, estimated values must retain their source and evidence reference.
Wallet scope is an alias only; private keys, seed phrases, cookies, and access
tokens must never enter events, fixtures, logs, or this registry.

## Commands

From `strategy/`:

```bash
python scripts/portfolio_registry.py --json
python scripts/portfolio_registry.py --platform fomo
python scripts/portfolio_replay.py tests/fixtures/portfolio/events.jsonl \
  --mark BTC-USDT=102 --json
python scripts/world_portfolio_replay.py tests/fixtures/world_markets/replay.jsonl \
  --reporting-currency USD --json
```

For a durable World alpha review, use `scripts/world_alpha_settle.py`; its
JSON result includes `paper_trade`, `finance_projection`, and the account
`capital` block. Use `scripts/world_alpha_reconcile.py` after a restart to
verify the same projection without creating a second event.

The fixture is illustrative and offline. It does not place an order or claim a
reward.

## When to split into separate projects

Keep the capability registry, common models, and accounting in this product
repository while they share the same release and risk boundary. Split a
platform adapter into its own project only when it has an independently
deployable runtime, provider-specific credentials, a separate test suite, or a
different data-retention/compliance boundary. Fomo should first pass the
contract and paper stages before it becomes an independently operated service.

## Promotion gates

1. **Research:** source payloads and parser errors are retained; no trade is
   implied.
2. **Paper:** deterministic replay, costs, quote age, available size, and
   settlement behavior are tested.
3. **Testnet:** venue-specific balances and fills reconcile against source
   evidence; kill switch and risk limits are independently verified.
4. **Live:** requires an explicit product/security/compliance decision and a
   separate credential boundary. This lane does not grant that approval.

The current milestone ends after the paper and rewards ledger. The next
provider-specific milestone is a read-only Fomo adapter after its official
endpoint and permitted contract are identified.
