---
type: brief
slug: c1-compiler-capture-cursors
title: Durable Capture, Cursors, and Trigger Lifecycle
epic: session-knowledge-compiler
created_at: '2026-07-13T20:36:41.553511+00:00'
---

# C1 — Durable Capture, Cursors, and Trigger Lifecycle

## Outcome

Implement the durable, provider-neutral substrate that makes every managed
agent/session eligible for incremental knowledge compilation. Persist canonical
source ranges, token progress, immutable checkpoint/job state, idempotency, and
terminal-trigger behavior without coupling compiler health to the managed
session's result or delivery.

## Source and prerequisite

Require reviewed `docs/managed-agents/handoffs/l3-megaplan-cutover.json`, the
complete launch-seam registry, and compiler ownership matrix from L3. Resolve G6
compilation grouping before accepting eligibility behavior. Use the North Star,
the neutral-lifecycle decision, the primary research from durable run
`subagent-20260716-155100-6d5344d7`, and the original conversation audit.
Historical chain `chain-c256f171485f` initialized planning only; it is not a
predecessor or implementation input.

## In scope

- Consume committed v3 journal streams and immutable evidence refs for every
  L3-classified eligible managed run. Preserve explicit v1/v2 compatibility
  gaps; do not re-normalize duplicate manifest/log/receipt/projection views.
- Implement deterministic `include|exclude|defer_to_owner` selection from
  origin/role, `projection_of`, evidence authorization, canonical evidence owner,
  `compilation_unit_id`, and policy version. Exclude resident root conversation,
  compiler, observer/auditor/controller, projection, and delivery-verifier prose.
- Define a canonical session identity and append-only source-position/range
  contract. A checkpoint must identify exactly which persisted evidence it
  covers without treating byte, event, and token offsets as interchangeable.
- Persist exact token usage when available and a clearly tagged fallback rule
  when it is not. Counter resets, cache tokens, retries, and multiple providers
  must not silently create negative or duplicate progress.
- Schedule compilation when newly persisted tokens since the last successful
  checkpoint reach approximately 100,000 and whenever the session newly enters
  completed, failed, cancelled, or superseded state.
- Represent an optional idle trigger as explicit disabled-by-default policy;
  implement it only if it can share the same durable eligibility/idempotency
  path without adding a second scheduler truth.
- Add durable job/lease/attempt state and a deterministic idempotency key based
  on session identity, source range, compiler/schema generation, and trigger
  kind. Concurrent sweeps and restart replay must converge on one checkpoint.
- Advance the last-successful cursor atomically only after a complete checkpoint
  is committed. Preserve failed attempts and retry evidence without advancing.
- Expose status/diagnostic information sufficient to tell eligible, queued,
  compiling, failed/retryable, and successfully checkpointed states apart.
- Add storage migrations/compatibility and focused file/DB backend tests as
  required by existing Store contracts.

## Out of scope

- LLM extraction prompts or four semantic output schemas (C2).
- Rolling/final synthesis, correction, or search (C3).
- Project promotion (C4) and backlog consolidation (C5).
- Replacing authoritative session logs or changing managed-agent terminal
  delivery semantics.

## Locked decisions

- Threshold is roughly 100,000 **newly persisted** tokens, not total lifetime
  tokens checked repeatedly and not a 10,000-token default.
- Terminal states trigger even when the threshold has not been reached.
- Checkpoints are immutable. Derived rolling views may change later, but source
  range coverage may not.
- Compiler work is asynchronous. Its failure must never turn a completed session
  into failed, delay terminal delivery, or be reported as primary-session work.
- Offset advancement and successful checkpoint persistence are one atomic
  logical commit; partial output never consumes the source range.
- Transcripts/tool evidence remain primary and must not be compacted away.

## Open questions for the planner

- **G6, compiler product owner:** approve when contributors have independent
  compilation units versus `defer_to_owner`, using nested/retry/rework/synthesis
  fixtures. Missing approval blocks eligibility acceptance.
- Which L3 source stream/range is canonical for each producer and which legacy
  sources remain explicit corroboration or gaps?
- What exact fallback token accounting is least misleading when a provider does
  not persist usage for every event?
- Which existing scheduler/Store claim primitive supports compiler eligibility
  without creating a second queue, lease authority, or lifecycle writer?
- Which retention/redaction controls must be inherited rather than duplicated?
- Is idle eligibility worth implementing now, or should only its policy/schema
  be reserved and tested as disabled?

## Constraints

- Implement only on the execution-time isolated target and preserve unrelated
  concurrent work according to repository custody policy.
- Use existing Store/file/DB transaction and migration patterns; no second
  unmanaged database or sidecar ledger.
- Fail closed on cursor ambiguity and fail open with respect to primary session
  completion.
- No hidden network dependency in trigger/cursor tests.
- Preserve backward compatibility for existing managed-agent manifests and
  resident stores that have no knowledge-compiler fields.

## Touchpoints

L3 lifecycle journal/projection and compiler policy APIs; Store file/DB and
migration modules; scheduler/claim primitives; authorization/redaction helpers;
structured direct-Hermes routing; and compiler eligibility, native-range,
atomicity, terminal, concurrency, anti-recursion, Store, and isolation tests.

## Measurable done criteria

- A persisted source-range/checkpoint contract exists with schema/version and
  deterministic idempotency keys.
- Tests prove one threshold trigger for 100k new persisted tokens, no trigger
  below threshold, and terminal triggering below threshold for every locked
  terminal state.
- Restart, concurrent sweeps, duplicate delivery, counter reset, out-of-order
  persistence, partial-write, and retry tests prove no skipped or double-counted
  source range.
- A forced compiler-job failure leaves the managed session state and terminal
  delivery unchanged; failure remains visible and retryable and cursor stays put.
- Existing stores/manifests migrate or load compatibly.
- Coverage tests prove exactly one compilation unit/range across retries,
  continuations, nested contributors, synthesis owners, repair workers,
  observers, compiler workers, delivery projections, and duplicate source views.
- `docs/session-knowledge-compiler/handoffs/c1-accepted-checkpoints.json`
  satisfies the epic handoff schema and is reviewed for C2.

## Anti-scope

Do not add product search, auto-promotion, generalized RAG, transcript deletion,
or paper-cut ranking. Do not refactor lifecycle, scheduling, WBC, Run Authority,
Custody, delivery, or ticket ownership merely because they are adjacent.

## Estimate and run shape

Approximately two skilled-human weeks. Overall plan difficulty 5/5; profile
`partnered-5`; robustness `full`; depth `high`; directed prep. Wrong evidence
ownership, native positions, eligibility, or commit boundaries can silently skip
or duplicate durable knowledge while focused tests pass.
