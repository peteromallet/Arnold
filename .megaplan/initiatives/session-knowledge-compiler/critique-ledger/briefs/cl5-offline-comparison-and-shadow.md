# CL5 — M6 offline comparison and report-only live shadow

## Outcome

Prove whether the context-first ledger reduces duplicate revision work without
suppressing novel findings. Reconstruct M6, run controlled comparison arms, and
operate report-only shadow with durable, attributable metrics and zero authority.

## In scope

- Execute the frozen offline reconstruction and deterministic replay twice.
- Run control, history-preload, blind-then-reconcile, and recommended hybrid
  arms under original mixed and fixed homogeneous model conditions.
- Blind-adjudicate semantic families, evidence quality, false merge/closure,
  novelty, duplicate actions, dispositions, token/latency, and gate deltas.
- Add default-off report-only shadow sidecars, observation artifacts, dashboards,
  sampling/review workflow, and zero-mutation/WBC receipt checks.
- Exercise all named relationship/disposition/failure/overflow/rollback and
  no-additional cases across representative robustness/profile routes.

## Out of scope

Changing live critic selection or prompts, revise/gate consumption, canary or
broad rollout, production backfill, deployment/restart, or acceptance based on
unblinded prose alone.

## Locked decisions

- M6 corpus and oracle are fixed inputs; mutation invalidates the experiment.
- Context treatment is the independent variable; other prompt/model/evidence/
  budget variables are held constant and versioned.
- Shadow is report-only and cannot influence plan, gate, chain, repair, or
  delivery behavior.
- Failing any significant-suppression, occurrence-loss, unsupported-closure,
  stale-briefing, novelty-loss, or authority-leak condition blocks canary.

## Open questions

- What sample size/observation window gives adequate confidence per route?
- Who performs blind adjudication and resolves evaluator disagreement?
- What approved token/latency budget is materially acceptable?
- Which false-merge/closure rates are acceptable beyond the hard failure cases?

## Constraints

Consume accepted CL1–CL4 handoffs and exact hashes. Preserve original outputs
and candidate outputs. Report missing evidence as unknown, not zero. Keep all
shadow writes isolated from authoritative plan/run stores except declared
append-only observation evidence. Bound the corpus, comparison arms, shadow
sample, review, and handoff to roughly two weeks.

## Done criteria

- Offline replay is deterministic and matches every M6 oracle fact.
- Controlled reports include exact input/model/profile/prompt/budget hashes and
  blind judge evidence; improvement direction persists across model conditions.
- Acceptance thresholds in `validation/m6-end-to-end.md` pass with confidence
  bounds and no hard failure.
- Shadow covers the required route/failure matrix and proves zero authoritative
  behavior change through negative tests and WBC receipts.
- A reviewed candidate canary cohort, promotion/rollback owners, and automatic
  stop triggers are recorded; otherwise CL6 remains blocked.

## Touchpoints

Frozen M6 fixtures/oracle; replay/experiment harness; feature flags; metrics/
reports; critique/evaluator/ledger adapters in report-only mode; WBC evidence and
negative mutation tests; CI artifacts.

## Anti-scope

No prompt or gate behavior change in shadow, cherry-picked runs, mutable corpus,
unversioned model comparisons, silent missing metrics, production enablement,
deployment, or restart.

## Written handoff to CL6

Write and review `docs/critique-ledger/handoffs/cl5-shadow-acceptance.json` with
all corpus/implementation hashes, comparison and adjudication reports, metrics
and confidence bounds, shadow route coverage, WBC zero-authority proof, approved
cohort, promotion owners, stop thresholds, rollback rehearsal plan, and
`accepted_for_canary: true`. Any unmet threshold or open hard failure blocks CL6.
