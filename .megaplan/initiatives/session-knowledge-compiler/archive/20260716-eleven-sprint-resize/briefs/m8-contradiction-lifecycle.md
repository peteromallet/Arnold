---
type: brief
slug: m8-contradiction-lifecycle
title: Contradiction, Supersession, Invalidation, and Revision-Aware Search
epic: session-knowledge-compiler
created_at: '2026-07-16T00:00:00+00:00'
---

# M8 — Contradiction, Supersession, Invalidation, and Revision-Aware Search

## Outcome

Complete project-knowledge lifecycle safety: detect and preserve potential
contradictions, adjudicate rather than auto-merge them, append supersession and
invalidation, flag drift, and return knowledge as active only when the caller's
repository/revision satisfies applicability.

## In scope

- Define contradiction candidate, adjudication, supersession, invalidation,
  stale/drift signal, and lifecycle records linked to M7 decisions/evidence.
- Detect bounded, explainable potential conflicts against active knowledge and
  pending relevant candidates; never auto-merge incompatible claims.
- Support recorded adjudication, accept-one, narrow-both, request evidence,
  supersede, and invalidate outcomes while preserving every historical version.
- Resolve active knowledge at repository/worktree/cloud revision and mark
  out-of-applicability or possibly stale content without presenting it as fact.
- Treat rebase/divergence/code-test change as evidence-producing drift signals,
  not automatic proof of contradiction.
- Enforce review authority and correction lineage during every lifecycle action.
- Integrate governed project knowledge into M6 bounded search semantics.
- Produce `docs/session-knowledge-compiler/handoffs/m8-governed-search.md`.

## Out of scope

Organization/global ontology, paper-cut grouping, ticket creation, code changes,
rollout controls, and unrelated vector/retrieval infrastructure.

## Locked decisions

- Contradictions are preserved and adjudicated, never newest-wins overwritten.
- Corrections, supersessions, and invalidations are append-only.
- Search outside applicability marks stale/out-of-scope and not current truth.
- Primary evidence remains resolvable after every lifecycle transition.
- Drift hints do not silently invalidate or contradict knowledge.

## Open questions

- Which deterministic candidate-generation rules keep checks bounded/explainable?
- How should rebases map old commit applicability without false certainty?
- Which file/test changes should flag knowledge for review?
- What precedence applies to overlapping narrow active claims after adjudication?

## Constraints

- Authorization and review tiers from M7 remain mandatory.
- File/DB parity, bounded checks, explainable evidence, and no hidden model
  decision as final authority.
- Historical accepted versions remain searchable/auditable.
- No execution behavior changes based solely on promoted knowledge.

## Done criteria

- Contradictory candidates remain traceable and require recorded adjudication.
- Tests cover same-revision conflict, narrowed coexistence, supersession,
  invalidation, corrected source, branch divergence, rebase, stale flag, and
  applicable/out-of-scope search.
- Search at an applicable revision returns active knowledge with provenance;
  other revisions never receive it as current fact.
- All lifecycle history and primary evidence resolve after transitions.
- M8 handoff defines governed search/observation inputs M9 can trust.

## Touchpoints

M7 records/review policy, M6 search, repository identity and diff helpers, Store
indexes/backends, authorization, and contradiction/revision/lifecycle tests.

## Anti-scope

Do not auto-edit code, auto-merge conflicts, build global knowledge, delete old
records, or weaken human/destructive-action authority.

## Predecessor handoff

Require reviewed `docs/session-knowledge-compiler/handoffs/m7-promotion-governance.md`,
landed applicability/review records, and passing fail-closed identity/authority
tests. M8 extends lifecycle; it does not reopen promotion authority design.

## Plan sizing and rubric

Estimated duration: approximately two skilled-human weeks. Overall plan
difficulty: 5/5; profile `partnered-5`; robustness `thorough`; depth `high`;
directed prep enabled. History-sensitive contradiction and applicability errors
can pass focused tests while misleading future work non-locally.
