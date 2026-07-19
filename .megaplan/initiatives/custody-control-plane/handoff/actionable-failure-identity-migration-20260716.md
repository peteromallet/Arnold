---
type: handoff
date: 2026-07-16
schema: custody-control-plane-actionable-identity-handoff-v1
status: ready-for-sequenced-implementation
source_research: ../research/actionable-failure-identity-custody-audit-20260716.md
source_decision: ../decisions/canonical-actionable-record-claimability-contract.md
raw_run: subagent-20260716-141251-24e3b08c
---

# Actionable identity migration order and conformance suite

## Implementation order

1. **Freeze inventory and vocabulary (M6).** Add every row in the research
   inventory to the canonical generated boundary inventory. Record exact
   source symbol, producer/consumer owner, current schema, runtime revision,
   and whether the row can emit actionable state. Do not change runtime yet.
2. **Land additive schema/store support (M6A).** Implement
   `ActionableRecordV2`, canonical constructors, hash verification, and a
   quarantine store. Add typed request/claim/attempt/decision records and a
   semantic idempotency index. Keep v1 readers read-only.
3. **Backfill without fabrication (M6A).** Migrate only v1 records whose
   identity and evidence are provable from write-time immutable artifacts.
   Quarantine the rest with reason codes. Never use current plan state to
   manufacture historical blocker identity.
4. **Repair intake and coalescing (concrete M6 owner, then M8).** Make queue
   acceptance require v2 claimability, persist coalesced occurrences, scope
   dedupe by occurrence/action target, and type verdict identity. Remove
   request identity dependence on root-cause prose.
5. **Migrate producers (M8).** In order: lifecycle failure, watchdog, manual
   retrigger, six-hour controller, supervisor exit, human gate, semantic
   findings, review aggregation/rework, then any remaining wrappers/native
   providers. Each producer must satisfy the conservation equation before the
   next cohort.
6. **Migrate consumers (M8/M9).** Claim/classifier/meta-repair/auditor/status
   consume v2 directly. Delete reconstruction from
   `project_repair_custody`; current-target checks become freshness-only.
7. **Resident/cloud convergence (M8/M9).** Join resident escalation and resume
   through occurrence/request/claim/attempt IDs while preserving immutable
   Discord provenance. Prove local, resident, cloud, and installed wrapper
   runtime revisions agree.
8. **Replay and restart proof (M10).** Add crash points around producer write,
   request accept, coalesce, claim, managed-run bind, attempt start/terminal,
   verdict, projection checkpoint, and telemetry emission. Rebuild from the
   immutable stream and compare exact hashes.
9. **Enforce and retire (M11).** Shadow -> quarantine -> enforce. Block old
   writers, retain expiring read-only adapters, and remove v1 reconstruction
   only after zero unknown producer coverage and a completed rollback drill.

## Required conformance/property tests

### Schema and identity

- Generate arbitrary valid records and prove canonical JSON ordering does not
  alter any ID.
- Removing/blanking any required identity, provenance, evidence, target, or
  retry field must make persistence return `quarantined`, never `accepted`.
- Unknown schema versions and additional authority-bearing fields fail closed.
- Mutating evidence digest, target snapshot, runtime revision, or causal parent
  changes occurrence/request identity or yields a hash mismatch.
- Duplicate `finding_id`, `occurrence_id`, request, claim, attempt, or decision
  with a different payload is `INCOHERENT`.

### Boundary conservation and aggregation

- For each critique/review/semantic/watchdog/auditor producer fixture, assert
  `produced == persisted_claimable + explicitly_quarantined`.
- Permute fanout completion order and producer-local IDs; canonical output and
  identity remain stable and no finding disappears.
- Inject a worker-returned review check ID that differs from the requested ID;
  reducer rejects it and persists a typed producer-contract failure.
- Any blocking rework/semantic error must have non-empty canonical identity and
  immutable evidence.

### Coalescing and claimability

- Same occurrence replay coalesces idempotently and persists a join decision.
- Same signature in two sessions never coalesces unless both name the same
  shared action target under an explicit policy; both session joins remain
  durable.
- Same target with different evidence snapshot is a new occurrence, not a
  silent coalesce.
- Every accepted request can be passed directly to claim without reading plan,
  current-target, status, filenames, or prose.
- Accepted-unclaimed age crossing the SLO deterministically creates one alert
  and cannot render as healthy/recovered.

### Claim, attempt, and terminal disposition

- Concurrent claimers produce exactly one fenced winner.
- PID reuse, stale owner metadata, transfer, retry, and custody-epoch changes
  cannot bind a managed run to the wrong request/target.
- Every attempt has exactly one terminal; duplicate same-payload terminal is
  idempotent and conflicting terminal is incoherent.
- Verdict records carry typed request/blocker/occurrence/attempt IDs; missing
  any join key cannot terminalize the request.

### Replay/restart and projections

- Property-test every prefix crash followed by duplicate/reordered replay of
  request, decision, claim, attempt, verdict, incident, and telemetry events.
  Final authoritative view and projection hash equal the uninterrupted run.
- Projection deletion/rebuild cannot create identity or action authority.
- Missing producer/runtime coverage, malformed records, or schema drift render
  `UNKNOWN/INCOHERENT`; counts never default to healthy zero.
- Restart with an accepted but malformed/unclaimable v1 request quarantines and
  alerts it; it cannot report successful recovery.

### Cross-runtime conformance

- Run the same fixtures through local Python, resident runtime, cloud wrapper,
  installed/editable package, and captured deployed wrapper revision.
- Assert identical canonical IDs, claimability decision, telemetry, and replay
  hash across variants.
- Static discovery must find every wrapper/native/provider call site; runtime
  traces must exercise every registered producer and consumer. Unmatched sets
  fail CI.

## Rollout and risk controls

- Additive v2 writes with v1 shadow comparison first; no dual authoritative
  writers.
- Quarantine instead of reconstructing missing identity. This may surface more
  blocked work initially; that is truthful and must be capacity-planned.
- Coalescing changes can temporarily increase queue volume. Rate-limit by
  action target after identity validation, not by signature prose.
- Preserve raw v1 bytes and migration receipts for rollback/audit. Rollback
  re-enables v1 read-only views, never v1 authority-increasing writes.
- Promotion gates require zero unexplained static/runtime rows, zero accepted
  unclaimable v2 records, conservation equations balanced per producer, and no
  `producer_coverage_unknown` in the canary window.

## Verification of this audit

The isolated audit worktree launched from
`056e8160e410007186e984459b005ef2fe080ef3` and was rebased onto observed target
`9ed382d09c98633663d9220a9891bf7b48c87e7c`. Focused current-contract tests ran:

`python -m pytest -q tests/orchestration/test_parallel_critique.py tests/orchestration/test_critique_custody.py tests/cloud/test_repair_requests.py tests/cloud/test_repair_custody.py tests/arnold_pipelines/run_authority/test_contracts.py tests/arnold_pipelines/run_authority/test_reducer.py tests/arnold/workflow/test_execution_attempt_ledger.py tests/resident/test_delegation_provenance.py`

Result: `390 passed`. This proves the named existing protections; it does not
erase the confirmed queue/review/semantic gaps above.

A direct temporary behavioral probe, rerun after that target rebase, enqueued the same signature for two
different sessions. It confirmed distinct computed request IDs, cross-session
coalescing to one persisted marker, and an accepted surviving projection with
an empty `blocker_id`.

Final-target caveat: the new phase-scope, phase-replay, and watchdog-fence
regressions pass (`3 passed`). Running the whole repair-dispatch classifier file
also exposed 12 pre-existing/stale fixtures that omit the now-required central
`queue_root`; those fail with `TypeError`. They remain an explicit conformance
gap and must not be counted as a runtime-fix regression or a green class-wide
gate.
