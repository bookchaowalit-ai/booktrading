# Degen discovery (read-only)

The degen scanner has three separate paths:

1. `DegenSource` uses DexScreener for priced pairs and can optionally enrich
   Solana tokens with Birdeye. Token address plus chain is the identity; a
   ticker is display text only.
2. `SolanaOnchainStream` subscribes to Solana program logs, fetches the
   confirmed transaction, and emits a launch/pool/migration event before an
   indexer has necessarily produced a price. It reconnects with bounded
   backoff and can persist a replay checkpoint.
3. `EVMOnchainSource` optionally polls `eth_blockNumber` and `eth_getLogs` for
   approved factory addresses and pair-creation topics on Ethereum, BSC, Base,
   and Arbitrum. It emits zero-price discovery events; missing token/pair ABI
   fields stay `unverified` and cannot pass the risk gate.

The stream is observation-only. It never signs or submits a transaction and
does not enable order execution.

## Configuration

Set these variables in the strategy service environment when the stream is
ready to be exercised:

```text
MARKET_INTEL_ONCHAIN_STREAM_ENABLED=true
MARKET_INTEL_RISK_GATE_ENABLED=true
MARKET_INTEL_RISK_MAX_AGE_SECONDS=900
SOLANA_WS_URL=wss://api.mainnet-beta.solana.com
SOLANA_RPC_URL=https://api.mainnet-beta.solana.com
SOLANA_ONCHAIN_PROGRAM_IDS=6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P
SOLANA_DEGEN_CHECKPOINT=/var/lib/booktrading/solana-degen-checkpoint.json
SOLANA_DEGEN_LANDING_URI=s3://booktrading-onchain/market-intelligence
SOLANA_DEGEN_LANDING_DATASET=solana_onchain_events
SOLANA_DEGEN_S3_ENDPOINT=
DATA_LAKE_CLOUD_WRITE_ENABLED=false
MARKET_INTEL_EVM_PROVIDER_MAX_TOKENS=20
MARKET_INTEL_EVM_PROVIDER_REGISTRY_JSON=
EVM_ONCHAIN_RPC_URLS_JSON=
EVM_ONCHAIN_FACTORY_ADDRESSES_JSON=
EVM_ONCHAIN_EVENT_TOPICS_JSON=
```

`SOLANA_WS_URL` and `SOLANA_RPC_URL` may point at a managed provider. Never put
provider keys in the URL, logs, or checkpoint. Use the provider's normal
secret mechanism for authenticated endpoints.

`BIRDEYE_API_KEY` is optional. When present, the scanner attaches a bounded
Birdeye observation to records that already have a Solana token address. A
missing or stale provider is surfaced in metadata; it never turns into a
synthetic price.

When `SOLANA_DEGEN_LANDING_URI` is set, every live websocket notification is
written as exact source bytes under `landing/`, then a versioned Bronze Parquet
row under `bronze/`, before a normalized event is dispatched. The immutable
`control/manifests/` record stores the event identity, raw/Bronze object keys,
byte counts, and SHA-256 checksums. A control checkpoint makes a retry safe if
the process stops between those writes. Retries with the same bytes are
idempotent; a different payload for the same event identity is rejected and
the normalized event is held until the stream reconnects.

`file://` (or the legacy `SOLANA_DEGEN_LANDING_DIR`) is for local drills.
`s3://` uses boto3's normal AWS/R2 credential chain; set
`DATA_LAKE_CLOUD_WRITE_ENABLED=true` only for an intentional provider run and
keep the endpoint/credentials in the secret mechanism. The stream never puts
credentials in lake objects or status responses. The current Bronze pilot
writes one immutable Parquet part per event. Use
[`SOLANA-LAKE-RELEASE-GATE.md`](SOLANA-LAKE-RELEASE-GATE.md) for the bounded
compaction, bucket-policy, secret-binding, and restore approval gates before
high-volume quota is enabled.

Plan or apply a UTC Bronze compaction without deleting source parts with:

```bash
python strategy/scripts/solana_bronze_compact.py \
  --uri "$SOLANA_DEGEN_LANDING_URI" --event-date 2026-01-02 --json
```

Restore one manifest and verify both checksums with:

```bash
python strategy/scripts/solana_landing_restore.py \
  --uri "$SOLANA_DEGEN_LANDING_URI" \
  --manifest-key 'control/manifests/source=solana_rpc/dataset=solana_onchain_events/schema_version=2/event_id=<event-key>.json' \
  --output /tmp/solana-restore
```

The service endpoint is `GET /api/market-intel/onchain/status`. It reports
connection state, checkpoint state, last slot, and a bounded recent-event
buffer. The event buffer is evidence for monitoring, not a trading ledger.

## Event and risk semantics

`token_created`, `pool_created`, and `liquidity_migrated` are discovery events,
not buy signals. They carry `data_complete`, signature, slot, program id, and
explicit `risk_flags` when price or transaction details are unavailable.
Downstream enrichment should verify mint/freeze authorities, Token-2022
extensions, holder concentration, liquidity depth, LP custody, and sellability
before any strategy is allowed to consider an asset. `risk_gate.py` writes a
typed `risk_decision` with one of `detected`, `unsupported`,
`insufficient_evidence`, `high_risk`, `watchlist`, `paper_candidate`, or
`invalidated`. Only `watchlist` and `paper_candidate` can reach degen
opportunity ranking; a missing, stale, conflicting, or provider-only check is
an abstention. A `watchlist` result is a bounded research state, not a claim
that the token is safe or will not rug. The current concentration value is
the raw share of the five largest token accounts; pool/vault exclusion and
wallet-level clustering are still pending, so it is evidence rather than a
final holder score.

DexScreener boosts are retained as `paid_promotion` discovery metadata only.
They never satisfy an authority, LP custody, or sell simulation requirement.
The current gate also rejects unsupported chains and unverified Solana log
events before momentum or buy-pressure signals are ranked.

For EVM evidence, `app.market_intel.evm_security` accepts already-fetched
GoPlus/Honeypot/simulation/LP-custody payloads and emits the
`evm-security.v1` schema. It is intentionally schema-only: it does not call
providers or submit transactions. Missing sell success, unverified LP custody,
partial/expiring locks, proxy/admin controls, or conflicting observations stay
in `insufficient_evidence`/`high_risk` until an outer provider boundary records
fresh, reconcilable evidence. Raw provider payloads and credentials remain
outside this adapter contract.

`app.market_intel.evm_provider.EVMProviderIngestor` is the bounded outer
boundary for an explicitly configured endpoint list. It retries only
`408/425/429/5xx` responses and transport timeouts with capped exponential
backoff, stores only endpoint host/path, status, attempt count, fetch time and
response SHA-256 in provenance, and carries required-provider failures into
the risk gate as `provider_availability` evidence. API keys belong in
secret-managed headers; credential-like query parameters are rejected. An
empty endpoint list makes no network request and cannot satisfy the gate.

`EVMProviderRegistry.from_env()` accepts this variable as secret-free JSON. The
registry must set `enabled=true` and `release_gate_approved=true` before it can
build an ingestor. When `degen` is enabled and the variable is non-empty,
`MarketScanner` loads the registry and fails fast if approval or secret binding
is missing. Each endpoint may name a `secret_ref` and `secret_header`, but the
JSON must never contain the secret value. The scanner's environment fallback
maps a reference ending in `/goplus` to `MARKET_INTEL_EVM_SECRET_GOPLUS`; a
production deployment should pass `evm_secret_resolver` backed by its secret
manager instead. The registry can also be passed to
`MarketScanner(evm_provider_registry=registry, evm_secret_resolver=...)` (or an
already-built `evm_provider_ingestor`). Passing both forms is rejected to keep
the provider path unambiguous. Leaving the variable blank keeps the scanner in
its no-EVM-provider mode.

`coverage_status` จะแยก `present_adapters` และ `missing_required_adapters` ต่อ
chain; ชุดหลักสำหรับการประเมิน EVM คือ `goplus`, `honeypot`, `simulation` และ
`lp_custody`. การมีแค่หนึ่ง adapter ยังไม่ถือว่า coverage ครบ.

สำหรับ EVM event discovery ให้ส่ง `EVMOnchainSource` เข้า
`MarketScanner(evm_onchain_source=...)` หรือกำหนด JSON ทั้งสามตัวแปรด้านบน
ซึ่ง scanner จะโหลด source ให้อัตโนมัติเมื่อมีค่าใดค่าหนึ่งถูกตั้งไว้
โดยต้องระบุ RPC, factory และ topic ที่ผ่านการตรวจ ABI แล้วครบชุดต่อ chain.
การ polling เป็น bounded block lookback ต่อรอบ scan ไม่ใช่ websocket และไม่
แทนการตรวจ security/exit ของ token. RPC timeout/transport error จะ retry แบบ
จำกัดและแสดงเฉพาะ error class ใน `coverage_status`; ไม่มี URL, header หรือ
payload ดิบในสถานะระบบ.

ก่อนผูก resolver กับ runtime ให้ใช้
[`EVM-PROVIDER-RELEASE-GATE.md`](EVM-PROVIDER-RELEASE-GATE.md) และรัน
`scripts/evm_provider_preflight.py`; dry-run นี้เป็น MockTransport แบบ
paper-only จึงไม่ยืนยันว่า upstream จริงพร้อมใช้งานและไม่สร้าง transaction

The stream uses `processed` logs for latency and fetches the transaction at
`confirmed` commitment. Consumers should treat a later failed or rolled-back
observation as invalid and use the checkpoint to replay the gap.
