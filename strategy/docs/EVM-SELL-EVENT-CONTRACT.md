# EVM sell event contract

`evm-event.v1` is a bounded, additive contract for read-only normalized EVM
sell evidence. It is implemented in `app.market_intel.evm_event_schema` and
is deliberately separate from the existing latest-head
`evm-onchain-events.v1` factory/pool discovery path.

The supported chain names are exactly:

- `ethereum`
- `bsc`
- `base`
- `arbitrum`

This phase does **not** enable execution, orders, wallet custody, signing,
`sendTransaction`, a real RPC, an indexer, a price lookup, or a lake writer.
All included fixtures use fake addresses, hashes, topics, and protocol
registrations.

## Normalized event

`EVMSellEvent` requires:

| Field | Meaning |
| --- | --- |
| `event_id` | SHA-256 identity over the canonical pipe-delimited event position |
| `event_schema_version` | Exactly `evm-event.v1` |
| `chain`, `protocol`, `contract_address`, `event_topic` | Explicit normalized source identity |
| `event_type` | Exactly `sell` |
| `transaction_hash`, `block_hash`, `block_number`, `log_index`, `event_index` | Explicit transaction/block position |
| `token_address`, `pool_address`, `seller_wallet` | Decoder-proven sell roles |
| `token_amount_raw`, `quote_amount_raw` | Non-negative integer base units |
| `quote_asset` | Raw quote asset identifier; no price is derived |
| `observed_at`, `source` | Observation time and provenance |
| `decoder_version`, `decoder_status` | Decoder evidence |
| `finality_status` | `observed`, `safe`, `finalized`, or `unknown` |
| `reorg_status` | `pending`, `canonical`, `orphaned`, or `unknown` |

`quote_value_usd` and `finality_reference` are optional external evidence.
Raw amounts are never converted through `float`; decimal or EVM hexadecimal
integer text is normalized directly to Python integers. The USD field is
accepted only as supplied evidence and is not calculated from quote units.

The identity material is:

```text
chain|protocol|contract_address|event_topic|block_hash|transaction_hash|log_index|event_index
```

Chains, protocols, addresses, topics, and hashes are normalized before
hashing. EVM addresses are lower-case 20-byte hex values and topics/hashes are
lower-case 32-byte hex values. A block hash is mandatory: a canonical
replacement on another fork therefore receives a different `event_id`, even
when its transaction, log, and event positions are otherwise equal.

`make_status_revision` and `append_status_revision` create a new immutable
status view while retaining the same event identity and all event evidence.
Only `verified` + `finalized` + `canonical` events are monitor-eligible.
Observed/safe, pending, unknown, or orphaned evidence remains available for
replay but cannot enter the cluster-sell monitor. An orphan revision
invalidates monitoring eligibility without deleting the original evidence.

## Decoder registry and fixture boundary

`app.market_intel.sources.evm_sell_events` accepts only an already-sanitized
transaction mapping with sanitized log mappings. It performs no RPC, indexer,
price, wallet, or order lookup. The registry key is the explicit tuple:

```text
(chain, normalized_contract_address, normalized_topic0)
```

Each `EVMProtocolDecoder` entry carries a caller-supplied `protocol`,
`decoder`, and `decoder_version`. The default registry is empty. There are no
production DEX ABI definitions, contract addresses, event topics, or protocol
entries in this repository.

The `make_fixture_decoder` helper is intentionally generic and test-only in
scope. The caller must provide the sell discriminator, `token_to_quote`
orientation, required account roles, and (when desired) a fixture protocol.
The helper requires explicit `event_type=sell`, `side=sell`, token/quote
objects, seller/pool roles, non-negative raw amounts, and `event_index`. It is
not a Raydium, Uniswap, PancakeSwap, Aerodrome, or other real DEX decoder.

The normalizer ignores failed transactions, removed logs, unsupported
registrations, unverified decoder output, missing block hashes, incomplete
positions, non-sell events, ambiguous orientations, and duplicate or
ambiguous log/event positions. It preserves raw quote units and the quote
asset. A caller may pass external USD evidence, but the normalizer never
fetches or infers it.

## Registry separation

The sell decoder registry is not `EVMProviderRegistry`:

- the sell decoder registry maps a caller-reviewed
  `chain + contract_address + topic0` to a pure sanitized-mapping decoder;
  it is empty by default and owns no credentials or network configuration;
  and
- `EVMProviderRegistry` remains the disabled-by-default, release-gated
  security-evidence boundary for already-fetched GoPlus, Honeypot,
  simulation, LP-custody, or related observations.

`EVMOnchainSource` remains unchanged: it is still
`evm-onchain-events.v1` latest-head factory/pool discovery with zero-price
quotes. This normalized sell contract is not wired into `DegenSource`,
`MarketQuote`, `MarketScanner`, the legacy discovery source, or the EVM
provider path.

## Cluster-sell adapter

`app.market_intel.evm_cluster_sell_adapter` is a parallel EVM-specific,
read-only adapter. It requires:

1. a verified, finalized, canonical `EVMSellEvent`;
2. an injected chain-scoped resolver for `(chain, seller_wallet)`;
3. a positive pre-sell cluster balance; and
4. external `quote_value_usd` evidence, either on the normalized event or
   supplied to the adapter.

Missing context returns an `ignored` route. The adapter never treats funding,
common-funder evidence, transaction proximity, or shared accounts as
ownership. Accepted fields map mechanically into the existing
`ClusterSellObservation`:

| EVM event | Observation |
| --- | --- |
| `transaction_hash` | `tx_hash` |
| `log_index` | `log_index` |
| `block_number` | `block_number` |
| `observed_at`, `source` | same fields |
| `seller_wallet` | `wallet` |
| `token_amount_raw` | `amount_token` |
| external `quote_value_usd` | `quote_value_usd` |

The adapter deduplicates `event_id`, rejects conflicting
`chain/transaction/log/event` positions, and always returns
`trade_instruction: false`. It emits no order, opportunity, execution, or
signing field.

## Lake and promotion boundary

There is no EVM lake writer in phase one. Existing discovery rows, manifests,
Bronze schemas, and source defaults are not reinterpreted as
`evm-event.v1`. A future landing/Bronze integration must use a separately
versioned dataset, manifest, replay rule, and release decision.

Promotion beyond fixtures requires, at minimum:

- protocol-specific decoder specifications and reviewed production registry
  entries for each enabled chain;
- sanitized replay fixtures covering success, failure, removed logs, duplicate
  positions, decoder mismatches, finality transitions, and fork replacement;
- an owned chain/provider finality and reorg policy with durable evidence;
- explicit cluster-label provenance and balance snapshot semantics;
- external valuation provenance and freshness limits;
- a read-only lake contract, lineage/retention policy, and replay/restore
  evidence;
- security review confirming no credentials, RPC writes, signing, or
  execution dependency; and
- a separate release approval before any runtime wiring into discovery,
  risk, or opportunity paths.

Until those gates are complete, no production decoder entries are enabled and
this contract remains a pure fixture-bound evidence slice.
