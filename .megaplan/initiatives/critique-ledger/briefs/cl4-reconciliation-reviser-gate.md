# CL4 — Semantic reconciliation and truthful reviser/gate flow

## Outcome

Add mandatory history-aware reconciliation, explicit dispositions/reopen rules,
independent disposition audit, correctable decisions, bounded per-finding
revision actions, and truthful gate consumption. One semantic finding may have
many occurrences, and no known finding disappears by omission or official
misclassification.

## In scope

- Validate complete occurrence-to-finding reconciliation after all selected
  attempts terminate; support duplicate, refinement, regression, reopen, split,
  merge, new, unrelated, and uncertain judgments.
- Append corrections that supersede rather than rewrite earlier reconciliation
  decisions; preserve both decisions, rationales, inputs, and audit results.
- Apply deterministic region/evidence/near-match/audit-disagreement tripwires
  that mark `needs_reconciliation` without making semantic decisions.
- Independently audit mandatory risk classes plus a deterministic non-zero
  sample of remaining duplicate/resolved/rejected/accepted-risk dispositions.
- Append disposition events for acted-on, ignored/wont-fix, deferred, rejected,
  duplicate, accepted-risk/tradeoff, unknown, addressed-pending-verification,
  and resolved-verified meanings with evidence and reopen predicates.
- Give the reviser the complete actionable set plus relevant disposed history;
  require one structured action or explicit non-action per active requested
  finding, while closed historical findings remain context rather than work.
- Derive relevance/actionability from explicit disposition, severity, existing
  gate policy, scope anchors, and staleness. The evaluator may propose scope but
  may not silently remove a known finding from the active projection.
- Expose deterministic `must_act`, `must_revalidate`, and `context_only`
  projections. Only the first two create current reviser work.
- Permit batch action/non-action only with enumerated finding IDs and one shared
  evidence basis, action, and reopen rule. Validate structured non-action and
  audit its semantic adequacy instead of accepting free-form rhetoric.
- Append the reviser's response and a separate verifier's
  `dealt_with|partially_dealt_with|not_dealt_with|unknown` outcome to the same
  finding history, bound to exact plan-region and evidence revisions.
- Publish a rebuildable critique-round accountability receipt mapping every
  attempt and occurrence through reconciliation, response, verified outcome,
  remaining reason, and reopen condition.
- Give gate/finalize the accepted ledger revision, occurrence coverage,
  disposition/evidence/reopen state, revision actions, and independent
  verification; replace false semantic claims while retaining exact-text metric
  under an honest compatibility name.
- Bind role-flow transitions to WBC boundary receipts and current authority.

## Out of scope

Changing execution approval, severity thresholds, gate authority, automatic
repair, cutover execution, or treating the model's semantic judgment as a
deterministic truth or lifecycle mutation.

## Locked decisions

- Semantic deduplication is model judgment with append-only rationale and
  immutable occurrences; uncertainty is valid, and a later audited event may
  supersede an earlier judgment.
- Addressed is not resolved until independently verified against the exact plan
  revision and evidence.
- A round receipt is a complete projection over the finding history, not a
  second ledger or authority.
- Gate may rely only on current accepted reconciliation/disposition decisions;
  review-required, disputed, or superseded state stays visible and cannot
  support clean convergence.
- Closure/non-action must carry explicit reopen predicates and becomes stale on
  relevant input changes.
- Gate distinguishes no novelty, no blocker, no known finding, and no adjacent
  text match; old `recurring_critiques` cannot claim semantic recurrence.
- Missing mapping, disposition, evidence, freshness, or action coverage fails
  before revise/gate.
- The ledger grows monotonically; the active action projection is bounded and
  changes with explicit policy, scope, staleness, and disposition.

## Open questions

- What confidence/disagreement and risk classes require mandatory independent
  audit, and what deterministic non-zero sample floor covers the remainder?
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
- Wrong-duplicate, correction/supersession, independent-audit disagreement, and
  near-match tripwire fixtures retain complete replayable history.
- All required disposition meanings, rationales, evidence limits, remaining
  questions, and reopen rules validate and replay.
- Reviser action/non-action coverage over the active projection is exact;
  closed history remains visible without recurring work, batch membership is
  explicit, and boilerplate/unauditable non-action remains active.
- Region-scoped edits stale affected closures without requiring full-ledger
  re-adjudication; unknown/cross-cutting scope defaults to whole-plan freshness.
- Round-accountability fixtures prove every critique has an attributable
  response and independently verified result or an explicit unresolved reason.
- Gate/finalize fixtures prove honest zero/no-new claims, accepted tradeoffs,
  open minor findings, disputed merges, reopen, and unsupported closure failure.
- Existing flag/revise/gate/finalize/critique custody/WBC tests pass, plus
  negative-authority and fail-closed custody tests.

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
results, M6 semantic-loop replay, and backup/restore prerequisites. CL5 uses
this exact contract as the cutover candidate and rejects any stale handoff.
