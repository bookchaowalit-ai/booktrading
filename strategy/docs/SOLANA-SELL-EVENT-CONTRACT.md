# Solana sell event contract

`solana-event.v1` is a bounded, additive contract for read-only normalized
Solana sell evidence. It is implemented in
`app.market_intel.solana_event_schema` and is deliberately separate from the
existing launch/pool discovery event path.

This MVP does **not** enable execution, orders, wallet custody, signing,
`sendTransaction`, or a network client. The fixtures and tests use fake
program IDs. No production Raydium, PumpSwap, or launchpad program ID is
enabled by this contract.

## Normalized event

`SolanaSellEvent` requires:

| Field | Meaning |
| --- | --- |
| `event_id` | SHA-256 identity of `chain\|protocol\|program_id\|signature\|instruction_index\|event_index` |
| `event_schema_version` | Exactly `solana-event.v1` |
| `chain`, `protocol`, `program_id` | Explicit normalized source identity |
| `event_type` | Exactly `sell` |
| `signature`, `slot` | Transaction identity and Solana slot |
| `instruction_index`, `event_index` | Explicit transaction position; neither is inferred |
| `token_address`, `pool_address`, `seller_wallet` | Decoder-proven sell roles |
| `token_amount_raw`, `quote_amount_raw` | Non-negative integer base units |
| `quote_mint` | Quote asset mint |
| `observed_at`, `source` | Observation time and provenance |
| `decoder_version`, `decoder_status` | Decoder evidence |
| `finality_status` | `processed`, `confirmed`, `finalized`, or `unknown` |
| `reorg_status` | `pending`, `canonical`, `orphaned`, or `unknown` |

Raw amounts are never converted through `float`. JSON decimal strings are
accepted and normalized to Python integers. `quote_value_usd` is optional
external evidence. The schema does not derive it from quote units, fetch a
price, or insert zero as a substitute for missing valuation.

`compute_event_id`/`deterministic_event_id` is the only event identity helper.
The dataclass validates that the supplied ID matches the canonical material.
`make_status_revision` and `append_status_revision` create a new immutable
status view while reusing the same `event_id`. A revision that changes any
event identity or evidence field is rejected. An orphan revision remains in
the append-only evidence history and is not eligible for monitoring.

## Decoder boundary and registry

`app.market_intel.sources.solana_sell_events` accepts only an already-fetched,
sanitized transaction dictionary. It performs no RPC or websocket call. The
caller must supply a program-ID registry, for example:

```python
registry = make_decoder_registry(
    raydium_program_id="FakeRaydiumProgram",
    pumpswap_program_id="FakePumpSwapProgram",
)
```

The example IDs are placeholders; callers must choose and review their own
registry entries. There is no module-level production registry. In
particular, a Pump launchpad `PUMP_PROGRAM_ID` is not treated as a PumpSwap
AMM ID.

The fixture boundary requires protocol-specific evidence, not just a log
string:

- the Raydium decoder requires `raydium.swap.sell.v1`, explicit `sell` fields,
  `token_to_quote` orientation, and `pool`, `seller`, `token_source`, and
  `quote_destination` account roles;
- the PumpSwap decoder requires `pumpswap.swap.sell.v1`, the same explicit
  orientation, and `pool`, `user`, `base_vault`, `quote_vault`,
  `user_base_source`, and `user_quote_destination` roles.

Failed transactions, unsupported registry IDs, missing seller/pool/index,
ambiguous token/quote orientation, and non-sell instructions are ignored.
The decoder preserves raw quote units and mint; a USD valuation may be passed
separately by a trusted outer evidence producer.

## Finality and reorg policy

The existing stream may observe `processed` logs and fetch `confirmed`
transactions for latency. That behavior and its defaults are unchanged.
This sell-event consumer is stricter because the existing
`ClusterSellMonitor` has no retraction API:

1. `processed` and `confirmed` events are retained as evidence but are not
   monitor-eligible;
2. `finalized` with `pending`, `unknown`, or `orphaned` reorg status is not
   monitor-eligible;
3. only `finalized` + `canonical` may reach the monitor; and
4. a later orphan revision invalidates the event for monitoring without
   deleting the original event or pretending that an alert can be retracted.

## Monitor adapter

`app.market_intel.cluster_sell_adapter` requires a chain-scoped resolver and a
positive pre-sell cluster balance supplied by the caller. The resolver receives
`(chain, seller_wallet)` and must return an explicitly established cluster.
The adapter never infers ownership from funding, common funders, transfer
proximity, or shared transaction accounts. Missing cluster context or missing
external `quote_value_usd` evidence produces no monitor observation.

The mapping is intentionally mechanical:

- `token_amount_raw` -> `ClusterSellObservation.amount_token`
- `signature` -> `tx_hash`
- `slot` -> `block_number`
- `event_index` -> `log_index`
- `observed_at`, `source`, seller wallet, token, cluster, and supplied USD
  evidence are preserved.

Event IDs are deduplicated and an event index must be unique per chain and
transaction. Route results attach `alert.as_dict()` when an alert is emitted
and always carry `trade_instruction: false`. There is no opportunity, order,
or execution route.

## Lake compatibility

This is an additive producer contract. The existing discovery/lake path is
unchanged:

- `LANDING_SCHEMA_VERSION=2` remains unchanged;
- `BRONZE_SCHEMA_VERSION=1` and `BRONZE_COLUMNS` remain unchanged;
- existing keys, manifests, discovery event semantics, stream defaults, and
  v1 compaction remain unchanged; and
- a future lake integration must use a new dataset and schema/version, with a
  separate manifest and release decision. It must not reinterpret old
  `solana_onchain_events` rows as `solana-event.v1` rows.

See [`DEGEN-DISCOVERY.md`](DEGEN-DISCOVERY.md) for the existing stream and
[`SOLANA-LAKE-RELEASE-GATE.md`](SOLANA-LAKE-RELEASE-GATE.md) for the current
landing/Bronze release gate.
