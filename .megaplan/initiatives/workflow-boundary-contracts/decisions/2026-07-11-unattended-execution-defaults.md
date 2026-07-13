# Decision: Freeze Unattended Execution Defaults

Date: 2026-07-11

## Decision

Once the two declared upstream chains are complete on combined `main`, their
content-addressed manifests validate, and the queued editable-install identity
check passes, C1-C6 runs without milestone approval, clarification, merge, or
design-selection pauses. The chain uses `merge_policy: auto`,
`driver.auto_approve: true`, and `prep_clarify: false`.

Acceptance and stop criteria are executable gates. A failing criterion records
the evidence and aborts through `stop_chain`; it never asks an operator to waive,
interpret, or approve the failure. Rerun follows correction on `main` using the
same pinned inputs.

## Ledger And Object Storage Default

The implementation extends the existing neutral
`arnold.pipeline.native.persistence.NativePersistenceBackend` seam and the
kernel event-journal mechanism; it does not introduce a Megaplan-only store.
The default reference backend is run/artifact-root scoped file persistence:

- ordered events use the existing fcntl-locked, fsync-backed append-only NDJSON
  journal semantics with monotonic sequence and idempotency enforcement;
- referenced bytes use a tenant/workflow/run-scoped content-addressed object
  tree with SHA-256 identity, atomic temporary-file promotion, fsync, and
  immutable-by-digest reads;
- result/state/terminal publication uses a durable outbox/prepare-commit record
  and deterministic reconciliation unless the pinned prerequisite backend
  exposes one transaction spanning those writes;
- backend selection is automatic: use the prerequisite-owned transactional
  backend when it satisfies the frozen protocol and fault suite; otherwise use
  the file backend above. More than one passing backend does not trigger a
  prompt—the transactional backend wins, then the file reference backend.

Missing locking, fsync/durability, idempotency, atomic promotion, tenant scope,
or reconciliation capability fails C1/C2 validation. An in-memory backend is
test-only and cannot satisfy conformance.

## Inline Payload Default

Inline payload policy version `wbc.inline.v1` allows only canonical UTF-8 JSON
whose serialized size is at most 16 KiB and whose privacy class is `public` or
`internal`. Binary data, secrets, credentials, free-form prompts/completions,
personal/restricted data, and payloads above 16 KiB always use a governed
durable reference. Secret detection rejects the write; it never stores a
redacted secret as if it were the original result. Inline and referenced modes
both carry digest, schema/media type, byte size, privacy class, and retention
class so policy changes are mechanically visible.

Serialization failure, unknown classification, missing governance metadata, or
threshold ambiguity selects reference mode when safe; if safe reference
storage is unavailable, dispatch/completion fails closed.

## Retention And Redaction Default

Policy version `wbc.retention.v1` follows the repository's current repair-data
windows and default-on redaction posture:

- transient debug/attempt payload: 14 days;
- standard inputs, results, artifacts, and audit payload: 30 days;
- authority, escalation, causal ledger metadata, redaction records, and
  tombstones: 90 days;
- unresolved, quarantined, `persistence_failed`, or `indeterminate` records are
  retained until resolution plus their class window;
- legal hold overrides disposal; expiry never overrides an active hold.

Redaction is on by default. It requires an accepted authority record, preserves
non-secret causal metadata and an audit-visible tombstone, and never rewrites
the append-only event. Secrets are excluded at ingestion. Unknown privacy or
retention class fails closed to referenced restricted data with no automatic
expiry; if access isolation cannot be proven, the write is rejected. Production
operators may later lengthen retention, but shortening these defaults is a
separate policy change and is not decided during C1-C6.

## Native Adapter And Version Selection

C6's required non-Megaplan adopter is the canonical
`arnold.pipeline.native.runtime.run_native_pipeline` path through
`NativePersistenceBackend`, exercised by
`arnold.pipelines.evidence_pack.pipeline:build_pipeline`. It is already a
native-only, API `1.0` graph with fan-out/reduction and a human-review boundary,
so no adapter choice remains for the milestone.

The adapter/runtime version vector is the combined-main source SHA, compiled
workflow manifest hash, `arnold_api_version`, persistence protocol/schema hash,
and template schema hashes. C1 records that vector; C2-C6 reject drift. A newer
compatible implementation is not selected mid-chain. If the pinned source no
longer exposes these symbols or evidence shapes, validation fails and the chain
aborts rather than substituting another adapter.

The conformance run injects a signed fixture decision at the human-review
boundary and uses fake/fenced external witnesses. It tests suspension/resume
semantics without waiting for a person or issuing a production effect.

## External Authorization Boundary

The following remain genuine external gates because the epic cannot safely
manufacture their authority: both upstream completion manifests on combined
`main`, a clean launch checkout, and equality of the launch base and synced
editable-install source revision. They are pre-launch machine checks, not
mid-chain prompts.

Production-wide dispatch/autonomy, destructive provider operations,
force-proceed, waivers, and real end-user approvals remain outside this epic.
C1-C6 implements and tests their contracts in observe-only, fake, fenced, or
already-authorized modes; production enablement is not required for chain
completion.
