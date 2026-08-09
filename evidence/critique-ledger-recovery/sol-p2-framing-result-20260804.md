# Sol P2 framing result — 2026-08-04

## Diagnosis

The deepest failure is **distributed authority without transactional custody**.
Runtime commands, source trees, plan state, `latest_failure`, phase results,
repair receipts, provider metadata, leases, PIDs, markers, batch receipts, and
observer snapshots can describe different executions, yet transitions accept
them without proving they belong to the same attempt and evidence generation.
That permits stale projections to outrank newer failures, entry points to run
different code, provider routes to drift, and `executing` to be published
before ownership and process identity are proven. VJ9 is the validation-side
form: the test and implementation contract crossed a revision boundary without
authoritative source/runtime custody.

Retries and extra telemetry do not solve this. Every Megaplan entry point needs
one admission and commit protocol.

## P2 north star

Build and adopt a versioned **ExecutionAttempt ledger** and admission
controller used by wrappers, resident mode, chain templates, supervisor, cloud
resume, recovery, watchdog, status, and future pipelines.

Each attempt carries:

- immutable prepared envelope: session, plan, phase/job, entry point, failure
  occurrence/fingerprint, worktree/source revision, runtime hash and absolute
  module command, validation command, and role-scoped provider routes;
- append-only attestations: provider preflight, lease/fence generation,
  container, PID/start identity, exact command, batch-receipt hashes,
  heartbeats, and terminal result;
- monotonic transitions:
  `prepared -> admitted -> leased -> launched -> verified/executing ->
  terminal|blocked`;
- compare-and-swap generations, with only the admission controller allowed to
  publish `executing` and only an occurrence-bound recovery receipt allowed to
  clear a failure.

Markers, tmux, phase results, snapshots, and observer output become
non-authoritative projections. Batch receipts remain authoritative for actual
task models, but their identities and hashes attach to the attempt.

## Non-goals

Do not redesign ledger business semantics, automatically resolve U1/quality
judgements, silently migrate ambiguous legacy sessions, or promise recovery
from host loss/network partitions in this P2. Those remain later or human-gated
work.

## Proposed milestones

**M0 — Authority definition:** approve the attempt schema, transition table,
evidence precedence, and complete entry-point/mutation inventory. No unknown
mutation path may remain.

**M1 — Reference kernel:** implement the ledger transition API, admission
controller, fencing rules, and conformance harness.

**M2 — Parallel adapters:** after M1, runtime/source custody,
evidence/recovery, lease/liveness, provider authority, and observer projection
work proceed in parallel. Provider resolution precedes leasing; process
attestation precedes `executing`.

**M3 — Entry-point adoption:** route every entry point through admission. Shadow
comparison is acceptable during rollout, but only one writer is authoritative.

**M4 — Migration/certification:** classify legacy sessions and run the complete
failure-injection matrix against every pipeline entry point.

Human gates remain for schema/migration policy, ambiguous takeover, changing a
session's pinned source/runtime/provider identity, and U1/quality acceptance.

## Current run boundary

Do now: preserve VJ9, prove source/runtime/worktree identity, repair the
adapter contract test, verify canonical store/outbox behavior, run the bounded
validation suites, and recover only with an occurrence-bound typed receipt.

P2: ExecutionAttempt ledger, admission, custody envelope, provider registry,
fenced liveness, evidence ordering, bounded projections, and cross-entry-point
conformance.

Later: post-dispatch retry policy, host/network-loss recovery, stronger artifact
signing, replacement infrastructure, and operational SLOs.
