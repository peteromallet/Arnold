---
type: brief
slug: m2-knowledge-use-governance
title: Knowledge Use, Correction, and Promotion Governance
epic: session-knowledge-compiler
created_at: '2026-07-16T12:30:00+00:00'
---

# M2 — Knowledge Use, Correction, and Promotion Governance

## Outcome

Turn M1 checkpoints into useful, correction-friendly session and project
knowledge through one append-only lifecycle and one scoped query path: rolling
and final synthesis, evidence-aware search, all five lightweight controls, and
reviewed repository/revision-aware promotion with contradiction preservation.

## In scope

- Produce versioned rolling synthesis from accepted checkpoints and one
  idempotent terminal synthesis only after the terminal range is accepted.
  Preserve exact record/checkpoint inputs, claim kinds, gaps, and older versions.
- Append claim/synthesis correction, supersession, rationale, actor, evidence,
  and deterministic active-view records; never mutate M1 evidence.
- Implement bounded, paginated Store-backed search over records, syntheses,
  corrections, and active/history views. Return evidence, claim kind,
  verification, applicability, scope, and lifecycle state with every result.
- Expose structured `record-learning`, `record-friction`, `correct-summary`,
  `search-session-knowledge`, and `propose-promotion` controls in the appropriate
  resident/managed-agent adapters. Automatic compilation remains the no-tool
  default; prompts do not bulk-inject the corpus.
- Define promotion candidate, repository/project identity, commit/branch/version/
  path/environment/time applicability, review decision, project knowledge,
  contradiction/adjudication, supersession, invalidation, and drift records.
- Require source/evidence/correction lineage and independent read/approve
  authorization. Narrow provisional claims may receive bounded automated aid;
  authoritative, broad, security, migration, public-contract, ambiguous, or
  contradictory claims require stronger declared/human authority.
- Detect bounded, explainable conflict candidates; preserve both sides and
  require recorded adjudication. Repository movement creates evidence-producing
  stale/drift signals, not automatic truth changes.
- Return accepted project knowledge as active only inside applicability;
  otherwise mark it stale/out-of-scope rather than current fact.

## Locked constraints

- A session summary is never inherently project-authoritative;
  `propose-promotion` stops at a candidate.
- Corrections and knowledge lifecycle are append-only; primary evidence and all
  historical versions remain resolvable.
- Unverified, inferred, proposed, contradicted, stale, and out-of-applicability
  material is never presented as confirmed current knowledge.
- No organization-wide ontology, separate promotion service, autonomous code
  change, hidden model adjudication, general vector platform, or weakened human/
  destructive-action authority.

## Acceptance evidence

- Multiple checkpoints yield linked rolling versions; terminal acceptance below
  or above threshold yields one final synthesis. Rebuild, duplicate terminal,
  concurrent correction, claim/synthesis correction, active-view, authorization,
  and full-history tests pass.
- Search enforces repository/session/revision/actor scope, authorization,
  pagination, bounded results, applicability, and active/superseded filters;
  leakage and decontextualized-result tests fail closed.
- All five named controls pass positive/negative schema, actor, authorization,
  idempotency, and lineage tests; a no-control session still compiles, and prompt
  tests prove the corpus is not injected wholesale.
- Promotion cannot be accepted without source evidence, deterministic identity,
  explicit applicability, and sufficient authority. Tests cover accept, reject,
  more evidence, narrow applicability, strong review, unauthorized review,
  corrected source, two-sided contradiction/adjudication, divergence/rebase,
  stale flag, supersession, invalidation, and applicable/out-of-scope retrieval.

## Dependencies and risks

Requires M1 accepted-checkpoint enumeration, record/evidence schemas, exact
route provenance, authorization, and atomicity tests. Reuse Store event/version
patterns, repository identity helpers, existing review authority, and one query
service with thin adapters. M2 is the densest sprint; if repository evidence
disproves the estimate, split its implementation without narrowing acceptance.

## Estimate and non-goals

Approximately two skilled-human weeks, including review and complete lifecycle
tests; estimate only, not a guarantee. Difficulty 5/5, profile `partnered-5`,
robustness `full`, depth `high`, directed prep enabled. Do not implement paper-
cut grouping/tickets, operational rollout, global RAG, automatic promotion or
conflict resolution, source deletion, or broad enablement.
