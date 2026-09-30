# Wallet Intelligence Contract

`wallet-intelligence.v1` is a read-only producer-side contract for normalized
on-chain wallet evidence. The current implementation lives in
`app.market_intel.wallet_intelligence` as an extraction pilot inside the
strategy repository. It is not a wallet custody, signing, swap, or order API.

## Inputs

- `WalletTransfer` identifies one normalized token transfer with
  `chain + token_address + tx_hash + log_index`, block position, amount,
  observation time, and source provenance.
- `WalletRelation` identifies a graph edge with a chain-scoped wallet pair,
  relation type, confidence, observation time, and source.
- `ClusterSellObservation` identifies one normalized sell observation with
  chain/token/cluster identity, wallet, amount, quote value, transaction
  position, observation time, source, and the cluster balance used as its
  denominator.

Upstream RPC/indexer collectors own extraction, finality, reorg handling, and
landing/Bronze durability. This module accepts normalized records and performs
no network calls.

## Merge policy

Only `same_owner` and `shared_control` relations whose confidence meets the
configured threshold may merge wallets. The following relations remain
retained graph evidence and never merge ownership by default:

- `funded_by`
- `common_funder`
- exchange/CEX funding or custody labels

The resulting cluster IDs are deterministic and chain-scoped. A cluster is an
ownership hypothesis for risk analysis, not a legal ownership assertion.

## Outputs

`calculate_concentration` emits:

- raw top-five share,
- cluster-adjusted/effective top-five share,
- observed supply and coverage,
- explicit excluded supply/wallets,
- cluster HHI, and
- chain-scoped cluster balances.

Pool, vault, bridge, burn, and CEX addresses must be supplied as explicit
exclusions by a trusted upstream labeler. The module does not guess them.
When effective concentration is present, `risk_gate.py` uses it before the
legacy raw top-five fallback.

`ClusterSellMonitor` maintains a bounded event-time window per
`chain/token/cluster`, deduplicates by transaction position, and emits
`cluster-sell-monitor.v1` alerts with sell share, unique sellers, event count,
severity, and reasons. Alerts are risk evidence only. A high/critical alert
vetoes the risk gate; a stale or conflicting watch alert causes abstention.

For the additive Solana sell-event input, see
[`SOLANA-SELL-EVENT-CONTRACT.md`](SOLANA-SELL-EVENT-CONTRACT.md). The adapter
passes only finalized/canonical normalized events, requires an explicit
chain-scoped resolver and positive pre-sell balance, and does not infer
ownership from funding or common-funder evidence.

For the parallel EVM sell-event input, see
[`EVM-SELL-EVENT-CONTRACT.md`](EVM-SELL-EVENT-CONTRACT.md). Its EVM-specific
adapter maps only verified/finalized/canonical events and requires the same
explicit resolver, positive balance, and external USD evidence. It does not
widen or alter the Solana adapter.

## Consumer boundary

Allowed consumers are replay, research/backtest, paper signal generation,
monitoring, and the deterministic risk gate. Execution Gateway code may
consume an approved risk decision, but must not call this module to sign or
submit transactions.

Promotion to a standalone `book-wallet-intelligence` product requires a
chain-scoped upstream owner, durable lake schema, finality/reorg policy,
label provenance, contract compatibility tests, a read-only API/CLI, and a
release gate. Until those exist, this pilot remains inside strategy and must
not be treated as a live trading dependency.
