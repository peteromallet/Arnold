# M1: Prep Semantic Health Guard

> Superseded as an executable milestone by C1-C6. Preserved only as historical
> checklist material; it cannot add a prompt, gate, or policy choice to the
> corrective chain.

## Outcome

Protect current cloud runs from the observed prep artifact/state divergence
class without waiting for the full boundary-contract architecture.

The watchdog can detect a high-confidence prep boundary divergence:

- prep artifacts or receipts exist;
- durable state remains `initialized`;
- history lacks prep success;
- `phase_result.json` is missing, stale, or not for prep;
- active work is not fresh enough to explain the gap;
- the current chain/session still points at this plan.

## Scope

IN:

- Add a pure, read-only prep contract evaluator.
- Add a watchdog alive-session fallback that calls the evaluator before generic
  stall heuristics.
- Return a structured compact status for dispatch and a JSON finding for
  evidence.
- Add observe-only and dispatch flags.
- Add focused tests for the exact incident shape and false-positive controls.

OUT:

- Broad phase coverage.
- Producer-side immediate enqueue.
- Chain/PR/cloud boundary coverage.
- Permanent bespoke prep-only registry.

## Locked Decisions

- M1 is intentionally narrow.
- Activity/liveness alone never marks a boundary healthy.
- Artifact existence alone never marks a boundary broken.
- Fresh `active_step`, in-flight LLM, or fresh events can suppress the finding
  when the artifact may still be in-progress.
- Old artifacts from noncurrent/abandoned plans are ignored.
- This is a bridge toward `BoundaryContract`, not the final abstraction.

## Done Criteria

1. A synthetic plan with `prep.json` / `prep_metrics.json` /
   `step_receipt_prep_v*.json`, `state.current_state=initialized`, no prep
   success history, and missing/stale `phase_result.json` produces a
   `phase_artifact_state_divergence` finding.
2. A healthy prepped plan produces no finding.
3. Fresh active prep produces no `repair_now` finding.
4. Stale abandoned/noncurrent plan artifacts are ignored.
5. Watchdog dispatches repair on the same scan when dispatch is enabled.
6. Watchdog reports observe-only findings without dispatch when observe-only is
   enabled.
7. Tests cover stable signature behavior and no duplicate dispatch when an
   identical repair is already active.

## Touchpoints

- `arnold_pipelines/megaplan/cloud/wrappers/arnold-watchdog`
- new semantic health module under `arnold_pipelines/megaplan/cloud/`
- `tests/cloud/test_watchdog_wrappers.py`
- new focused semantic-health tests under `tests/cloud/`
