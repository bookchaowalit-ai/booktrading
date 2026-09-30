# On-chain execution contract

`trade-intent.v1` is the strategy-side boundary between normalized market
evidence/risk and a future execution gateway. It is deliberately a proposal
contract, not a transaction API.

```text
signal/data → wallet intelligence → risk gate → TradeIntent
                                             ↓
                                  future Execution Gateway
                                  ├─ route/quote
                                  ├─ chain-specific adapter
                                  ├─ signer
                                  ├─ broadcast
                                  └─ receipt/reorg reconciliation
```

## What the strategy may emit

`app.trade_intent.TradeIntent` contains:

- supported chain identity: `solana`, `ethereum`, `bsc`, `base`, or `arbitrum`;
- `aggregator` or `direct_dex` route kind and a caller-selected venue label;
- input/output asset identifiers and integer base-unit input amount;
- maximum slippage in basis points;
- recipient wallet;
- the passed risk state, confidence, policy version, and evidence references;
- creation/expiry timestamps; and
- `paper` or `simulation` execution mode only.

The intent ID is deterministic over the normalized payload. Serialized intents
carry `execution_allowed=false` so downstream consumers cannot mistake this
phase for an approved live transaction.

## Offline paper/simulation consumer

`app.paper_execution.PaperExecutionGateway` is the first consumer of the
intent contract. A caller supplies a sanitized `PaperQuote` containing the
chain/route context, integer input/output amounts, quote timestamps, and a
simulated output amount. The gateway:

- rejects context mismatches, expired or future quotes, stale quotes, expired
  intents, and output below the intent's slippage bound;
- returns a versioned `PaperExecutionReceipt` with a deterministic
  `execution_id`;
- treats each `intent_id` as an idempotency key and rejects reuse with
  different quote data; and
- exports secret-free receipt events for a later lake writer.

The receipt records `signed=false`, `broadcasted=false`, `transaction_hash=null`,
and `reconciled=false`. It is execution evidence for paper/simulation only; it
does not create a `PaperTrade`, calculate P&L, reserve capital, or claim that a
swap occurred. A later portfolio adapter must consume an explicit simulated
fill policy rather than infer one from a transaction-like payload.

## What is intentionally absent

The contract does not contain:

- private keys, wallet exports, signatures, or seed phrases;
- RPC URLs, provider credentials, calldata, router/factory addresses, or gas
  transaction objects;
- a transaction hash or a claim that a swap happened;
- a production DEX registry or protocol-specific ABI;
- a cross-chain bridge instruction; or
- a direct call to the existing Go `DexService`.

The paper consumer also does not accept calldata, router addresses, RPC
configuration, transaction hashes, or arbitrary serialized fields.

The existing Go backend already has legacy EVM DEX providers and a `DexService`
with live-capable swap methods. This strategy contract does not wire to those
methods because the existing RPC boundary does not yet bind a normalized
`RiskDecision`, evidence freshness, intent expiry, execution mode, and
reconciliation record into one release-gated request. It remains a downstream
execution candidate, not a strategy dependency.

## Promotion gates

Before any live execution adapter is enabled, each chain/protocol needs:

1. a reviewed route/ABI/address registry and finality policy;
2. quote, allowance/permit, slippage, deadline, fee-on-transfer, and
   honeypot checks;
3. bounded signer custody and transaction policy outside the strategy process;
4. simulation/paper replay fixtures and idempotent intent handling;
5. receipt, reorg, balance-delta, and failure reconciliation; and
6. an explicit release approval that keeps live execution disabled by default.

Jupiter, 0x, LI.FI, Raydium, PumpSwap, Uniswap, Aerodrome, and PancakeSwap can
be future route/adapter implementations. Their presence in this document does
not register a production provider or claim that a live connector exists.
