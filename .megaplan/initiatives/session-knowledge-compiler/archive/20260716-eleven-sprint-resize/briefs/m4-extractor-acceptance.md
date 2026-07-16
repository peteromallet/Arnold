---
type: brief
slug: m4-extractor-acceptance
title: Bounded Direct-Pro Extraction and Atomic Acceptance
epic: session-knowledge-compiler
created_at: '2026-07-16T00:00:00+00:00'
---

# M4 — Bounded Direct-Pro Extraction and Atomic Acceptance

## Outcome

Implement the bounded evidence compiler that invokes the exact direct DeepSeek
Pro route for an M2 source range, validates an M3 four-record result, and joins
atomic checkpoint acceptance without changing primary-session outcomes.

## In scope

- Serialize only the new persisted range plus bounded prior accepted context.
- Delimit evidence as untrusted data and resist transcript prompt injection.
- Invoke `hermes:deepseek:deepseek-v4-pro` through provider `direct` using the
  existing structured-worker seam.
- Enforce explicit input, output, attempt, duration, and cost bounds; represent
  chunking/truncation/unverified gaps without inventing coverage.
- Validate the M3 structured result and evidence links before persistence.
- Atomically persist all required records and complete the M2 checkpoint; leave
  malformed/partial/error results retryable with the cursor unchanged.
- Reuse worker error classification and suppress unsafe semantic/auth/schema/
  context fallback to another model or provider.
- Persist reproducibility metadata without credentials.
- Produce `docs/session-knowledge-compiler/handoffs/m4-accepted-checkpoints.md`.

## Out of scope

Rolling/final synthesis, corrections, search, promotion, paper-cut merging,
rollout policy, and generalized extraction infrastructure.

## Locked decisions

- Exact route is canonical direct Pro; Fireworks and silent substitution are not
  accepted routes.
- Transcript/tool content is evidence, never compiler instruction.
- All four records validate and commit together or the checkpoint does not
  advance.
- Extraction failure is visible/retryable and harmless to primary delivery.
- Evidence gaps remain explicit rather than being summarized away.

## Open questions

- What deterministic chunking strategy preserves claim/evidence locality?
- Which worker failures retry the same generation versus require a new one?
- How much prior accepted synthesis can safely contextualize an extraction?
- Which cost/size defaults are safe before M10 rollout measurement?

## Constraints

- Do not guess model/provider identity; durable evidence and tests prove it.
- Never send secrets or unrestricted environment data.
- Preserve M2 idempotency/atomicity and M3 schema validation under retries.
- No model call in unit tests; integration tests use bounded fakes or approved
  deterministic harness seams.

## Done criteria

- Representative extraction persists all four records with exact route metadata.
- Tests reject prompt injection, malformed/partial output, invalid evidence,
  unsafe fallback, over-budget input/output, and proposal-as-performed.
- Duplicate retry yields one accepted checkpoint; validation failure leaves the
  cursor and primary session result unchanged.
- Chunked fixtures prove complete range accounting and explicit gaps.
- M4 handoff defines accepted checkpoint enumeration and prior-context inputs.

## Touchpoints

M2/M3 APIs, Hermes/worker structured output and error classification, partnered
profiles/policy, serializer/redaction helpers, provider routing, and worker,
schema, store, and resident integration tests.

## Anti-scope

Do not build search, promotion, backlog ranking, a generic ETL framework,
provider fallback policy, or replace raw evidence with generated prose.

## Predecessor handoff

Require reviewed `docs/session-knowledge-compiler/handoffs/m3-record-schema.md`,
landed schema/storage APIs, and passing deterministic validation/transaction
tests. M4 consumes the schema; it does not redefine claim semantics.

## Plan sizing and rubric

Estimated duration: approximately two skilled-human weeks. Overall plan
difficulty: 4/5; profile `partnered-4`; robustness `full`; depth `high`;
directed prep enabled. Predecessor contracts constrain the design, but provider,
chunking, retry, and transaction topology still require substantial reasoning.
