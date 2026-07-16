# CL4 — Semantic reconciliation and truthful reviser/gate flow

## Outcome

Add mandatory history-aware reconciliation, explicit dispositions/reopen rules,
per-finding revision actions, and truthful gate consumption. One semantic
finding may have many occurrences, and no known finding disappears by omission.

## In scope

- Validate complete occurrence-to-finding reconciliation after all selected
  attempts terminate; support duplicate, refinement, regression, reopen, split,
  merge, new, unrelated, and uncertain judgments.
- Append disposition events for acted-on, ignored/wont-fix, deferred, rejected,
  duplicate, accepted-risk/tradeoff, unknown, addressed-pending-verification,
  and resolved-verified meanings with evidence and reopen predicates.
- Give the reviser the complete actionable set plus relevant disposed history;
  require one structured action or explicit non-action per requested finding.
- Give gate/finalize the accepted ledger revision, occurrence coverage,
  disposition/evidence/reopen state, revision actions, and independent
  verification; replace false semantic claims while retaining exact-text metric
  under an honest compatibility name.
- Bind role-flow transitions to WBC boundary receipts and current authority.

## Out of scope

Changing execution approval, severity thresholds, gate authority, automatic
repair, shadow/canary enablement, or treating the model's semantic judgment as a
deterministic truth or lifecycle mutation.

## Locked decisions

- Semantic deduplication is model judgment with append-only rationale and
  immutable occurrences; uncertainty is valid.
- Addressed is not resolved until independently verified against the exact plan
  revision and evidence.
- Closure/non-action must carry explicit reopen predicates and becomes stale on
  relevant input changes.
- Gate distinguishes no novelty, no blocker, no known finding, and no adjacent
  text match; old `recurring_critiques` cannot claim semantic recurrence.
- Missing mapping, disposition, evidence, freshness, or action coverage fails
  before revise/gate.

## Open questions

- What confidence/disagreement requires a second evaluator or tiebreaker?
- Which non-blocking open dispositions gate may accept under existing policy?
- What compatibility field/name exposes exact-text adjacency during migration?
- Which reopen predicates can be mechanically triggered versus model-evaluated?

## Constraints

Consume accepted CL1–CL3 handoffs. Preserve current flag/gate/finalize positive
authority and WBC attempt/evidence ownership. A model event cannot directly
write plan/chain lifecycle state. This sprint must remain independently
reviewable within roughly two weeks.

## Done criteria

- Reconciliation accounts for 100% of parseable occurrences and every attempt
  outcome; dropped/unmapped/duplicate/stale rows block.
- All required disposition meanings, rationales, evidence limits, remaining
  questions, and reopen rules validate and replay.
- Reviser action/non-action coverage is exact; unchanged findings remain visible.
- Gate/finalize fixtures prove honest zero/no-new claims, accepted tradeoffs,
  open minor findings, disputed merges, reopen, and unsupported closure failure.
- Existing flag/revise/gate/finalize/critique custody/WBC tests pass, plus
  negative authority and rollback compatibility tests.

## Touchpoints

Evaluator verdict validation; critique custody/ledger projections; flag lifecycle;
`prompts/critique.py`, revise metadata/prompt; `prompts/gate.py`,
`orchestration/gate_signals.py`, `handlers/gate.py`; finalize custody; boundary
contracts/receipts and focused tests.

## Anti-scope

No automatic semantic closure, exact-text/embedding similarity as authority,
severity-disposition collapse, execution approval change, repair dispatch, or
silent compatibility deletion.

## Written handoff to CL5

Write and review `docs/critique-ledger/handoffs/cl4-role-flow.json` with accepted
role-flow/schema hashes, disposition/reopen matrix, reconciliation and action-
coverage proofs, gate-claim compatibility map, WBC receipts, negative-authority
results, M6 dry replay, and rollback instructions. CL5 uses this exact contract
as the candidate implementation under test.
