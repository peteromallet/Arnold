# WBC attempt identity and replay incident — 2026-08-04

## Finding

The critique run did not fail because the ledger was unable to deduplicate a
normal retry. It failed because the execute producer reused one storage attempt
ID for two different immutable coordinator occurrences. The first durable
`started` event had `attempt_ordinal=5` and invocation `4cc63054-b198-424d-8181-1a650d05ee6e`.
The retry reused the same attempt ID and idempotency key but produced
`attempt_ordinal=6`, a new invocation UUID, later timestamps, and a new source
version. `DivergentDuplicateError` correctly quarantined the mutation.

The same error class appears in research/prep evidence, so this is a shared WBC
identity/replay defect, not an execute-only anomaly.

## Evidence

- Cloud plan: `cl2-wbc-backed-ledger-20260803-1357`.
- Durable key: `cl2-wbc-backed-ledger-20260803-1357:execute:batch:2:1f93603db53b:started`.
- Persisted attempt: `88c958d3-fc12-5198-830a-00bbd4fc9510`.
- Three diagnostic rows recorded retries with divergent payloads; the semantic
  batch/task scope remained unchanged.
- The exact differences were identity/fence/invocation/version and volatile
  observation timestamps—not a changed task request.

## Root cause

`execute/wbc.py` derived `_attempt_id` from only the logical `dispatch_id`,
while `LedgerEvent.identity` included the coordinator invocation and fence.
`worker_dispatch_wbc.py` had the same shape for its invocation field. Runtime
metadata was regenerated before every append, and the duplicate comparator
treated that timestamp as semantic data while ignoring the immutable identity.

## Landed repair

The repair commit makes the contract explicit:

1. Execute attempt IDs include run revision, dispatch ID, coordinator attempt,
   and fence. Worker-dispatch IDs additionally include the snapshotted current
   invocation. A new occurrence gets a new attempt stream and key.
2. A legacy attempt is reused only when its persisted identity exactly matches
   the current occurrence; a changed fence/invocation cannot be replayed into it.
3. Canonical duplicate comparison includes identity, event schema, provenance,
   adapter, versions, grant, status, outcome, and stable payload. It strips
   only top-level occurrence/observation timestamps and the WBC source-record
   observation timestamp. Semantic changes still raise and quarantine.
4. The SQLite ledger and transactional outbox share this comparison primitive.
5. Regression tests cover timestamp-only replay, identity divergence, outbox
   parity, execute fencing, and worker invocation fencing.

This preserves the old row byte-for-byte and makes the current blocked run
require explicit reconciliation before it can receive a fresh attempt. It does
not silently “repair” a partial external effect.

## Sol judgement and relaunch gate

GPT-5.6 Sol reviewed the exact row diff and agreed that ordinal 5→6 is a new
semantic attempt, not a replay. It rejected weakening `DivergentDuplicateError`
or minting a new key merely to evade a conflict. A new attempt is safe only
after the old attempt's task claims, partial batch effects, and checkpoint are
reconciled; a single runner/fence/home backend/current generation must be
authoritative. The semantic-mismatch canary must continue to raise.

Before cloud resume, take a read-only evidence backup, install the pinned commit
in the actual worker runtime, verify both ledger/outbox test paths, reconcile
the affected batch and checkpoint, and run one controlled recovery. If any
attempt/effect ownership is ambiguous, remain stopped and quarantine it.

## Follow-up (deeper platform work)

The durable platform fix is to centralize immutable attempt construction and
canonical event serialization in one WBC module, then require every research,
execute, phase, effect, and worker-dispatch producer to use it. Add a
generation-aware observation/notification facade and occurrence-deduped repair
claims so retries cannot create notification loops. Keep plan-local journals and
runtime metadata as projections/evidence, never as a second authority.
