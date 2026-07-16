---
type: brief
slug: m1-compiler-core
title: End-to-End Capture and Evidence Compiler
epic: session-knowledge-compiler
created_at: '2026-07-16T12:30:00+00:00'
---

# M1 — End-to-End Capture and Evidence Compiler

## Outcome

Deliver one production-shaped vertical slice: any managed execution maps to a
versioned observation envelope with exact lineage and evidence, becomes
eligible, claims an exact new persisted range, emits four validated records via
bounded direct-Pro extraction, and accepts the range exactly once without
affecting primary execution, acceptance, custody, completion, or delivery.

## In scope

- Re-inventory current authoritative and corroborating seams for resident roots/
  descendants, Megaplan prep/plan/critique/gate/revise/finalize/execute/review
  phases and implementation/review workers, neutral and repair/meta-repair/
  watchdog/auditor managed runs, plan/milestone/chain/child-epic transitions,
  higher-level workflows, and Hermes/Codex/Claude/future execution backends.
- Define one versioned `KnowledgeObservationEnvelope` and stable workflow ->
  epic/chain -> sprint/milestone -> plan -> phase/step -> attempt -> agent-run
  lineage. Preserve root/parent, retry/rework/supersession, task/goal revision,
  authority/custody/acceptance/delivery refs, native position and exact half-open
  range, gaps, capabilities, and backend/model/route provenance.
- Distinguish occurrence, source persistence, adapter capture/observation,
  compiler ingestion, decision, and terminal times in UTC. Order within a
  stream by native sequence/position and across streams only by causal refs.
- Add backward-compatible file/DB persistence using existing Store patterns.
- Trigger after roughly 100,000 newly persisted tokens and on completed,
  failed, cancelled, and superseded transitions below threshold. Reserve one
  disabled idle-policy field; do not add a second scheduling path.
- Add generic Store append and versioned, idempotent adapters at already-
  persisted source seams. Use existing scheduler/store claim patterns for
  eligibility, attempt, retry, last-successful cursor, and atomic logical
  acceptance. Preserve late/out-of-order/concurrent/failed evidence and gaps.
- Define separate versioned activity, reusable-knowledge, paper-cut observation,
  and improvement-candidate records with claim kind, evidence, applicability,
  actor, confidence/verification, and compiler provenance.
- Serialize only the new range plus bounded prior accepted context; frame source
  content as untrusted evidence; represent truncation and unverified gaps.
- Invoke only `hermes:deepseek:deepseek-v4-pro` via provider `direct` through the
  existing structured-worker seam. Bound input/output/attempt/duration/cost and
  reject silent provider/model fallback. This compiler extraction route is
  independent of the Hermes, Codex, Claude, or future backend that produced the
  source execution evidence.
- Validate and persist the complete four-record set before advancing the cursor.
  Model/schema/store/auth failure remains visible and retryable.

## Locked constraints

- Primary evidence is never replaced, compacted, or rewritten.
- Native byte/event/sequence/token positions are not interchangeable; ambiguity
  fails closed for compilation and remains fail-open for primary delivery.
- `observed`, `performed`, `inferred`, `proposed`, and `unverified` remain
  explicit. Proposed work never renders as performed.
- Authorization to a derived record cannot exceed its evidence authorization.
- Run Authority, WBC, workflow/Megaplan scheduling and acceptance, Custody,
  repair dispatch, and delivery remain owned outside the compiler. Their
  records are referenced; the compiler cannot grant, fence, schedule, accept,
  retry, transfer custody, deliver, or reinterpret their decisions.
- Logs, PIDs, mutable state/status projections, transcripts, tool output, and
  agent/model prose remain evidence rather than authority. Unknown and
  not-applicable fields stay explicit; adapters never guess from clocks/names.
- No sidecar database, generic event bus, standalone queue, credentials in
  provenance, hidden network dependency in unit tests, or unrelated refactor.

## Acceptance evidence

- A generated coverage matrix binds every required execution kind, role,
  transition, and backend to a real durable source seam, source-priority label,
  adapter, fixture, and test. Representative resident, phase/worker, chain, and
  repair fixtures resolve exact evidence ranges; legacy stores/manifests load
  and migrate additively.
- Envelope tests cover complete hierarchy and optional levels, parent/root/
  causal/retry/rework/supersession links, separate lifecycle/acceptance state,
  distinct time semantics, native ordering, orphans/cycles, cross-run binding
  drift, custody epoch/fence mismatch, and duplicate launch conflicts.
- Tests cover threshold/no-threshold, every terminal state below threshold,
  missing usage, counter reset/cache/retry, late/out-of-order events, ambiguous
  positions, duplicate delivery, concurrent claims/children, restart, expiry,
  crash and partial write with no skipped/double-counted range or silent child.
- Schemas and round trips prove all four records remain distinct and reject
  missing kind, proposal-as-performed, unauthorized/missing/out-of-range
  evidence, duplicate identity, partial results, prompt injection, explicit
  budget overflow, and unsafe fallback.
- A bounded fake integration durably records the exact direct-Pro route and
  accepts the range once; every forced failure leaves the successful cursor and
  managed-session result/delivery unchanged.
- The landed APIs expose accepted checkpoints and bounded prior-context inputs
  for M2 without introducing another cursor, authority ledger, or truth store.
- Negative tests prove capture is append-only and cannot mutate execution,
  acceptance, custody, repair, scheduling, or delivery state.

## Dependencies and risks

Use current Store/native journals and migrations, WBC where operationally
authoritative, scheduler claims, managed manifests, typed phase/worker results,
chain/acceptance receipts, authoritative custody/repair records, Hermes
structured output, authorization/redaction helpers, and provider policy. The
largest risks are incomplete chain/parent identity, uneven WBC adoption, and
backend position/transaction mismatch; retain capability/source-priority flags
and explicit gaps and fail closed rather than inventing precision or authority.

## Estimate and non-goals

Approximately two skilled-human weeks, including design, implementation, tests,
review, and a usable M2 handoff; estimate only, not a guarantee. Difficulty 5/5,
profile `partnered-5`, robustness `full`, depth `high`, directed prep enabled.
Do not build synthesis/search, promotion, backlog ranking, generalized ETL/RAG,
idle enablement, product deployment, or a scheduler/storage replacement.
