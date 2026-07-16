---
type: brief
slug: m3-record-contracts
title: Four-Record Schemas, Evidence References, and Persistence
epic: session-knowledge-compiler
created_at: '2026-07-16T00:00:00+00:00'
---

# M3 — Four-Record Schemas, Evidence References, and Persistence

## Outcome

Freeze and implement the durable semantic contract for activity, reusable
knowledge, paper-cut observations, and improvement candidates, including claim
kinds, evidence references, applicability, provenance, and atomic persistence
hooks into M2's checkpoint lifecycle.

## In scope

- Define separate versioned schemas/storage/query primitives for the four
  canonical record types.
- Require `observed`, `performed`, `inferred`, `proposed`, or `unverified` claim
  kind on every substantive claim.
- Define evidence references into the exact M1/M2 range and relevant transcript,
  tool, log, manifest, file, commit, command, and test artifacts.
- Validate missing, structurally invalid, unauthorized, and out-of-range links.
- Keep activity distinct from reusable knowledge; keep immutable observations
  distinct from mutable-status improvement proposals.
- Record source range, actor, confidence/verification, applicability, compiler,
  model/provider, prompt/schema generation, and supersession capability without
  storing credentials.
- Provide one all-or-nothing persistence interface that M4 can call before M2
  marks a checkpoint successful.
- Produce `docs/session-knowledge-compiler/handoffs/m3-record-schema.md`.

## Out of scope

Model prompts/invocation, acceptance retry orchestration, synthesis, correction
UX, search indexing, promotion decisions, consolidation, and rollout.

## Locked decisions

- Four outputs remain distinct even when one event supports multiple records.
- Performed needs action evidence; proposed never reads as done; inferred and
  unverified never masquerade as observed fact.
- Primary evidence outranks all derived records and is never rewritten.
- Paper-cut observations remain source-preserving; candidates may link but not
  overwrite them.
- Partial record sets cannot commit a successful checkpoint.

## Open questions

- Which fields are stable enums versus versioned extensible tags?
- What evidence-reference granularity balances resolvability and storage cost?
- Which applicability fields belong on all records versus reusable knowledge?
- How should schema generations coexist during rolling upgrades?

## Constraints

- File/DB parity, schema-versioned compatibility, bounded record sizes, and no
  secret material in provenance.
- Authorization to a record cannot exceed authorization to its evidence.
- Reuse M2 idempotency and transaction boundaries; no second cursor.
- Validation is deterministic and does not require a model/network call.

## Done criteria

- Schemas enforce record type, claim kind, evidence, source range, and provenance.
- Tests reject proposal-as-performed, missing kind, invalid/out-of-range evidence,
  duplicate identity, unauthorized references, and partial record sets.
- Fixtures demonstrate activity/knowledge and observation/candidate differences.
- File/DB round trips and old/new schema compatibility pass.
- M3 handoff specifies the structured result M4 must produce and accept.

## Touchpoints

M1/M2 schemas, Store interfaces/backends/migrations, structured serialization,
authorization helpers, query primitives, and schema/store tests.

## Anti-scope

Do not implement LLM extraction, search UI, promotion approval, backlog ranking,
general document extraction, vector infrastructure, or source deletion.

## Predecessor handoff

Require reviewed `docs/session-knowledge-compiler/handoffs/m2-checkpoint-commit.md`,
the landed lifecycle API, and passing atomicity/restart tests. M3 must join that
transaction contract rather than weakening it.

## Plan sizing and rubric

Estimated duration: approximately two skilled-human weeks. Overall plan
difficulty: 5/5; profile `partnered-5`; robustness `thorough`; depth `high`;
directed prep enabled. These public schemas encode truth and lineage; subtle
classification or compatibility mistakes can outlive their producing session.
