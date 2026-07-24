---
superseded_by: custody-control-plane
---

# M2 - One-Hour Repair Correctness

## Objective

Make the existing one-hour repair loop bounded and independently verifiable. Repair success must mean complete, progressed, live with fresh activity, or true human blocker with a durable escalation record. Process/tmux liveness alone must become `partial_liveness`, not success.

## Files And Areas To Change

- `arnold_pipelines/megaplan/cloud/wrappers/arnold-repair-loop`
  - Add `CLOUD_WATCHDOG_REPAIR_BUDGET_SECS` with default 3600.
  - Preserve `CLOUD_WATCHDOG_REPAIR_ITERATION_MAX=3` as compatibility while enforcing the wall-clock budget.
  - Track deadline and remaining budget before model dispatch, Kimi launch, mechanical relaunch, state inspection, and Discord escalation.
  - Record `repair_timeout` as a terminal outcome when the envelope expires.
  - Enforce the shared repair lock before stale-state clearing, gate answering, relaunch, marker mutation, and needs-human pointer writes.
  - Add `verify_repair_effect()` or extend `verify_started_and_holding()`.
- `arnold_pipelines/megaplan/cloud/repair_contract.py`
  - Finalize verification record helpers and status/outcome mapping.
- `arnold_pipelines/megaplan/cloud/current_target.py`
  - Use resolver snapshots for pre/post verification.
- `arnold_pipelines/megaplan/cloud/human_blockers.py`
  - Prove true-human blockers are classified separately from mechanical gates/stale markers.
- `tests/cloud/test_watchdog_wrappers.py`
  - Add adapter/scenario coverage, but do not put all semantics here.
- New or expanded pure Python tests:
  - verification status transitions;
  - budget/deadline helpers;
  - true-human-blocker classification;
  - no liveness-only terminal success.

## Verifiable Completion Criterion

- Fixture where tmux stays alive but no state/event progress occurs produces `partial_liveness`, not success.
- Fixture where event seq/active-step heartbeat/chain log mtime advances produces `live_with_fresh_activity`.
- Fixture where plan iteration, state, milestone index, completed count, or git HEAD advances produces `progressed`.
- Fixture where current target is truly human-blocked writes/updates escalation ledger and pointer and reports `true_human_blocker`.
- Very small budget tests produce `repair_timeout` without fake human escalation.
- Existing three-iteration behavior remains when budget permits.
- Focused tests and wrapper characterization pass.

## Guardrails

- Do not add failure-triggered repair yet except for no-op compatibility scaffolding.
- Do not count model summaries, "agent launched," or "tmux held" as success proof.
- Do not let Discord delivery failure masquerade as a delivered human escalation.
