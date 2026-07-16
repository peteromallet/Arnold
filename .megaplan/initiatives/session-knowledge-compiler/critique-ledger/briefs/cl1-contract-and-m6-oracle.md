# CL1 — Contract, ownership, and M6 oracle freeze

## Outcome

Freeze the minimum versioned critique-ledger contract, its exact WBC/Megaplan
ownership boundaries, and a content-addressed read-only M6 corpus/oracle. Leave
CL2 an accepted schema/compatibility bundle with no unknown writer or corpus row.

## In scope

- Inventory current evaluator verdict, producer artifacts, critique custody,
  flag/revision/gate/finalize records, WBC attempt/evidence/payload contracts,
  schemas, readers, writers, and tests.
- Decide stored events versus rebuildable projections; freeze occurrence,
  reconciliation, disposition, domain-briefing, and ledger-manifest schemas.
- Map explicit dispositions for acted-on, ignored/wont-fix, deferred, rejected,
  duplicate, accepted-risk, unknown, and resolved semantics; keep severity
  orthogonal and require reopen conditions.
- Freeze historical/mixed-version unknown behavior, privacy/retention classes,
  failure/atomicity table, and evaluator-versus-curator authority.
- Copy/redact/content-address the preserved M6 inputs without mutating their
  source and encode the required oracle facts in the validation plan.

## Out of scope

Persistence implementation, prompt/routing changes, live model calls, runtime
behavior, historical semantic backfill, shadow/canary enablement, or WBC edits
outside additive declarations/fixtures needed to freeze the contract.

## Locked decisions

- One logical cumulative finding set with immutable occurrences and bounded
  domain projections; semantic merges are append-only model judgments.
- Deterministic code owns custody/completeness/freshness, not semantic sameness.
- Optional blind discovery must be reconciled before revise/gate consumption.
- `no_additional_findings` is a first-class success, distinct from no blocker or
  no known finding.
- WBC remains attempt/effect/evidence owner; the critique ledger grants no
  execution, transition, repair, or gate authority.

## Open questions

- Does the evaluator curate directly or accept a curator proposal while keeping
  final disposition authority?
- Which current flag/gate states are stored inputs versus compatibility
  projections, and what is the minimal stable semantic finding ID contract?
- Which evidence classes require governed durable references and what retention
  applies to prompts, completions, and private repository evidence?
- What exact domain floors and briefing budgets are approved per robustness?

## Constraints

Use the exact target/WBC ancestry and M6 source revision recorded in the annex.
Inspection and corpus capture must be read-only. Unknown legacy semantics remain
unknown. A hash without retained retrievable bytes is not evidence preservation.
This sprint must fit roughly two weeks including review.

## Done criteria

- Source-to-owner and contract-to-producer matrices assign one writer and all
  compatibility readers; no row is unknown or competing.
- Versioned schemas/goldens cover all dispositions, relationships, modes,
  no-additional outcomes, evidence availability, tombstones, and future/unknown
  versions.
- Atomicity/failure and privacy/retention tables are reviewed against landed
  WBC policy and negative-authority tests are specified.
- M6 manifest hashes every required input; replay twice produces identical
  inventory/oracle hashes; the five-occurrence family and accepted replay
  limitation are mechanically asserted.
- Current versus proposed behavior and all unresolved product/authority gates
  are explicit; no implementation is falsely marked landed.

## Touchpoints

`arnold/workflow/{execution_attempt_ledger,payload_policy,boundary_evidence,boundary_compatibility,boundary_conformance}.py`;
`arnold_pipelines/megaplan/{audits,prompts,orchestration,handlers,schemas}`
critique/evaluator/gate surfaces; WBC support/owner matrices; M6 corpus; related
WBC, critique custody, evaluator, and parallel critique tests.

## Anti-scope

Do not create a new authority ledger, semantic database, embeddings, similarity
threshold, transition writer, repair queue, or broad Session Knowledge Compiler
feature. Do not edit or resume M6.

## Written handoff to CL2

Write and review `docs/critique-ledger/handoffs/cl1-contract-oracle.json` with
schema/version hashes, owner and compatibility matrices, WBC revision/receipt
refs, M6 corpus/oracle hashes, privacy/retention and atomicity decisions, open
gates, implementation touchpoints, and `accepted_for_cl2: true`. CL2 must reject
a missing, stale, unreviewed, or blocker-bearing handoff.
