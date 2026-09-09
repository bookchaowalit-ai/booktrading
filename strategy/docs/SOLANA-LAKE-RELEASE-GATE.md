# Solana lake release gate

This is the release contract for the read-only Solana degen observation lake.
It applies to the `solana_rpc` source, `solana_onchain_events` dataset, and
the `file://` pilot or `s3://` production boundary described in
[`DEGEN-DISCOVERY.md`](DEGEN-DISCOVERY.md).

The gate keeps source evidence durable before a normalized event is consumed.
It does not authorize trading, order execution, or a public bucket.

## Required object-storage policy

The production bucket/R2 location must be private and have all of the following
recorded by the owner before `DATA_LAKE_CLOUD_WRITE_ENABLED=true` is used:

| Control | Required decision |
|---|---|
| Object ownership | Provider-enforced bucket ownership; ACL-based public writes are disabled. |
| Public access | Public listing and public reads are blocked. Access is limited to the ingestion role and the read-only restore/maintenance role. |
| Encryption | Provider server-side encryption is enabled; use a customer-managed key when the provider/account policy requires it. |
| Versioning | Object versioning is enabled so an accidental overwrite or delete can be recovered. The application still uses immutable keys and never overwrites. |
| Lifecycle | Raw, Bronze, compacted Bronze, and control manifests have explicit retention periods. Lifecycle expiration does not bypass a legal hold or incident preservation. |
| Transport | TLS is required for provider endpoints. Credentials never appear in a URI, object key, manifest, log, or status response. |
| Least privilege | The writer may create/read the scoped `landing/`, `bronze/`, `bronze_compacted/`, and `control/` prefixes. It has no delete permission in the pilot. |
| Recovery | A restore drill verifies raw bytes, Bronze checksum, manifest lineage, and compacted-part checksum from a clean destination. |

`SOLANA_DEGEN_S3_ENDPOINT` may select an S3-compatible endpoint such as R2.
Credentials come from boto3's standard provider chain or the runtime's secret
binding. Do not put access keys in `.env`, Docker Compose, or the endpoint URL.
The preflight only checks configuration and operator attestations; it does not
pretend to verify a remote bucket policy without a provider control-plane read.

## Release steps

1. Run the no-network preflight and local evidence drill:

   ```bash
   python strategy/scripts/solana_lake_preflight.py \
     --uri file:///tmp/booktrading-solana-lake \
     --drill --evidence-output /tmp/solana-restore-evidence.json --json
   ```

   The evidence file contains checksums and control metadata only; it does not
   copy raw payload bytes or credential values.

2. Review the bucket/R2 policy and bind credentials through the approved secret
   mechanism. Set the seven `SOLANA_DEGEN_*_ATTESTED` values only after the
   corresponding controls are evidenced. Keep `DATA_LAKE_CLOUD_WRITE_ENABLED`
   false until this review is complete.

   Before attesting, run the provider checker in offline mode to confirm the
   URI is redacted and the credential source is named without reading its
   value:

   ```bash
   python strategy/scripts/solana_lake_provider_check.py \
     --uri "$SOLANA_DEGEN_LANDING_URI" --json
   ```

   After the provider grants a read-only control-plane role, the same command
   can perform the policy calls explicitly with `--remote`. It checks bucket
   versioning, encryption, public-access blocking, ownership, lifecycle
   coverage, and public policy status; it never writes or deletes objects.

3. Run a dry-run compaction for a bounded UTC partition. It reads and validates
   source parts but writes nothing:

   ```bash
   python strategy/scripts/solana_bronze_compact.py \
     --uri "$SOLANA_DEGEN_LANDING_URI" \
     --event-date 2026-01-02 --json
   ```

4. Apply compaction only after the dry-run is reviewed. The command writes one
   new immutable part under `bronze_compacted/` and a control manifest under
   `control/compactions/`; it never deletes or edits the one-event source
   parts:

   ```bash
   python strategy/scripts/solana_bronze_compact.py \
     --uri "$SOLANA_DEGEN_LANDING_URI" \
     --event-date 2026-01-02 --apply --json
   ```

5. Verify the compaction manifest and run the single-event restore command from
   `DEGEN-DISCOVERY.md`. Record the output checksum and the clean-destination
   restore evidence in the release ticket. Production quota stays disabled if
   either verification fails.

6. Use `--require-production` as the final configuration gate. It returns a
   non-zero exit code until the S3 URI, cloud-write decision, bucket policy,
   versioning, encryption, lifecycle, secret binding, compaction approval, and
   restore approval are all explicitly attested:

   ```bash
   python strategy/scripts/solana_lake_preflight.py \
     --uri "$SOLANA_DEGEN_LANDING_URI" --require-production --json
   ```

## Compaction contract

Compaction is bounded by `SOLANA_DEGEN_COMPACTION_MAX_PARTS` and
`SOLANA_DEGEN_COMPACTION_MAX_INPUT_BYTES`. A compacted manifest lists every
source key, source checksum, source row count, output checksum, and output row
count. The commit order is output part first, manifest second. A retry with
the same source set is idempotent; a different source set or output bytes is a
conflict. Source parts remain the replay authority until a separate table
metadata/consumer migration is approved.

The current pilot does not delete source parts, expire objects, or register an
Iceberg table. Those actions require a separate change with consumer parity,
retention, rollback, and accountable owner evidence.

## Approval record

| Role | Name/date | Decision/evidence |
|---|---|---|
| Data product owner |  |  |
| Data engineering owner |  |  |
| Security/operations owner |  |  |
| Restore reviewer |  |  |
