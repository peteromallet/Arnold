---
type: brief
slug: m9-paper-cut-backlog
title: Paper-Cut Consolidation, Ranking, and Ticket Adapter
epic: session-knowledge-compiler
created_at: '2026-07-16T00:00:00+00:00'
---

# M9 — Paper-Cut Consolidation, Ranking, and Ticket Adapter

## Outcome

Consolidate immutable paper-cut observations into explainable, reversible,
prioritized improvement backlog items and an idempotent existing-ticket adapter
without deleting, rewriting, or overstating any source observation.

## In scope

- Freeze a small grouping taxonomy with extensible tags, including
  discoverability, ambiguous contract, missing capability, reliability/
  correctness, performance/cost, and workaround/friction where evidenced.
- Define deterministic candidate keys using surface, category, symptom,
  applicability, and evidence; model suggestions may assist but never decide
  membership opaquely.
- Persist backlog items with every observation link, recurrence/distinct-session
  counts, impact, urgency, workaround cost, confidence, applicability, proposed
  outcome, status, scoring inputs, and history.
- Support merge, split, relate, reject, supersede, and reopen while preserving
  observations and prior memberships.
- Implement a documented deterministic priority policy without fake precision.
- Adapt to the existing ticket substrate with explicit mapping/idempotency keys;
  duplicate/retry processing creates no duplicate ticket.
- Expose bounded lineage from backlog item/ticket to every primary observation.
- Produce `docs/session-knowledge-compiler/handoffs/m9-backlog-lineage.md`.

## Out of scope

Automatically fixing items, organization-wide prioritization, deleting
observations, broad rollout, compiler budgets, and cross-project clustering.

## Locked decisions

- Paper cuts are evidence-preserving observations; backlog items are proposed
  consolidated work and are not the same record.
- Consolidation is explainable/reversible and never erases sources.
- Priority is reproducible; volume/confidence never turns proposed into done.
- Ticket integration is an adapter, not a replacement authority.
- Adapter failure is independent of compilation/session completion.

## Open questions

- What minimal scoring formula balances recurrence, impact, workaround, reach,
  confidence, and effort without pretending mathematical certainty?
- Which ticket fields hold lineage versus require an attached/indexed record?
- When may one observation relate to several candidates and which is primary?
- Which taxonomy labels must be stable versus extensible tags?

## Constraints

- Preserve M3 observation immutability and M8 applicability/authorization.
- Idempotent file/DB and ticket behavior; no remote effects in tests.
- Ranking inputs/decisions are inspectable and bounded.
- Metrics/records contain no transcript contents or credentials unnecessarily.

## Done criteria

- Equivalent observations consolidate once with all source links; a later split
  restores separate items without rewriting observations/history.
- Duplicate/retry processing creates no duplicate membership or ticket.
- Tests cover taxonomy, deterministic score inputs, merge/split/relate/reject/
  supersede/reopen, adapter failure, authorization, and lineage resolution.
- Proposed work never renders as performed or completed without ticket evidence.
- M9 handoff defines metrics and configuration surfaces M10 must operate.

## Touchpoints

M3 observations, M8 governed search/applicability, existing initiative/ticket
stores and CLI/domain APIs, Store backends, ranking/lineage records, and tests.

## Anti-scope

Do not auto-fix, delete observations, replace ticket authority, add global
clustering/vector infrastructure, or make ticket success gate compilation.

## Predecessor handoff

Require reviewed `docs/session-knowledge-compiler/handoffs/m8-governed-search.md`,
landed governed search/lifecycle APIs, and passing applicability/lineage tests.
M9 may group only immutable observations visible through those boundaries.

## Plan sizing and rubric

Estimated duration: approximately two skilled-human weeks. Overall plan
difficulty: 4/5; profile `partnered-4`; robustness `full`; depth `medium`;
directed prep enabled. Grouping/ranking needs judgment, but immutable source
lineage and governed search sharply constrain the acceptable design.
