---
type: brief
slug: m1-compiler-core
title: End-to-End Capture and Evidence Compiler
epic: session-knowledge-compiler
created_at: '2026-07-16T12:30:00+00:00'
---

# M1 — End-to-End Capture and Evidence Compiler

## Outcome

Deliver one production-shaped vertical slice: a managed session becomes
eligible, an exact new persisted evidence range is claimed, bounded direct-Pro
extraction emits four validated record types, and the range is accepted exactly
once without affecting primary-session completion or delivery.

## In scope

- Inventory resident and automatic-repair managed-session sources; define
  versioned session/source identity, native position, half-open range, terminal
  observation, exact/tagged-fallback token observation, and capability fields.
- Add backward-compatible file/DB persistence using existing Store patterns.
- Trigger after roughly 100,000 newly persisted tokens and on completed,
  failed, cancelled, and superseded transitions below threshold. Reserve one
  disabled idle-policy field; do not add a second scheduling path.
- Use existing scheduler/store claim patterns for durable eligibility, attempt,
  retry, last-successful cursor, deterministic idempotency, and atomic logical
  acceptance. Preserve late/out-of-order/failed evidence and diagnostics.
- Define separate versioned activity, reusable-knowledge, paper-cut observation,
  and improvement-candidate records with claim kind, evidence, applicability,
  actor, confidence/verification, and compiler provenance.
- Serialize only the new range plus bounded prior accepted context; frame source
  content as untrusted evidence; represent truncation and unverified gaps.
- Invoke only `hermes:deepseek:deepseek-v4-pro` via provider `direct` through the
  existing structured-worker seam. Bound input/output/attempt/duration/cost and
  reject silent provider/model fallback.
- Validate and persist the complete four-record set before advancing the cursor.
  Model/schema/store/auth failure remains visible and retryable.

## Locked constraints

- Primary evidence is never replaced, compacted, or rewritten.
- Native byte/event/sequence/token positions are not interchangeable; ambiguity
  fails closed for compilation and remains fail-open for primary delivery.
- `observed`, `performed`, `inferred`, `proposed`, and `unverified` remain
  explicit. Proposed work never renders as performed.
- Authorization to a derived record cannot exceed its evidence authorization.
- No sidecar database, generic event bus, standalone queue, credentials in
  provenance, hidden network dependency in unit tests, or unrelated refactor.

## Acceptance evidence

- Representative resident and repair fixtures resolve exact evidence ranges;
  legacy stores/manifests load and migrate additively.
- Tests cover threshold/no-threshold, every terminal state below threshold,
  missing usage, counter reset/cache/retry, late/out-of-order events, ambiguous
  positions, duplicate delivery, concurrent claims, restart, expiry, and partial
  write with no skipped/double-counted range.
- Schemas and round trips prove all four records remain distinct and reject
  missing kind, proposal-as-performed, unauthorized/missing/out-of-range
  evidence, duplicate identity, partial results, prompt injection, explicit
  budget overflow, and unsafe fallback.
- A bounded fake integration durably records the exact direct-Pro route and
  accepts the range once; every forced failure leaves the successful cursor and
  managed-session result/delivery unchanged.
- The landed APIs expose accepted checkpoints and bounded prior-context inputs
  for M2 without introducing another cursor or truth store.

## Dependencies and risks

Use current Store transactions/migrations, scheduler claims, managed-session
events, worker result/error classification, Hermes structured output,
authorization/redaction helpers, and provider policy. The largest risk is
backend position/transaction mismatch; retain capability flags and fail closed
rather than inventing false cross-backend precision.

## Estimate and non-goals

Approximately two skilled-human weeks, including design, implementation, tests,
review, and a usable M2 handoff; estimate only, not a guarantee. Difficulty 5/5,
profile `partnered-5`, robustness `full`, depth `high`, directed prep enabled.
Do not build synthesis/search, promotion, backlog ranking, generalized ETL/RAG,
idle enablement, product deployment, or a scheduler/storage replacement.
