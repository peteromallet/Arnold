---
superseded_by: custody-control-plane
---

# Repair Custody Core

## Outcome

Implement the core repair-custody contract so repairable blockers cannot fall between plan-local queueing and watchdog dispatch.

The sprint should produce a typed custody projection, durable request/attempt distinction, atomic claim semantics, a shared Python dispatch classifier, and regression coverage for the `agentic-replay-viewer` failure shape:

`current_state=blocked`, `resume_cursor.retry_strategy=manual_review`, `latest_failure.kind=blocked_recovery_not_resolved`.

## Context

The reviewed planning material for this sprint lives in:

- `.megaplan/initiatives/superfixer-repair-custody/repair-custody-sprint-plan.md`
- `.megaplan/initiatives/superfixer-repair-custody/load-bearing-questions.md`
- `.megaplan/initiatives/superfixer-repair-custody/megaplan-prep.md`

The prior incident showed that the repair queue and watchdog dispatch path can disagree. The plan-local repair queue accepted repair work, while watchdog looked directly at plan state, treated `manual_review` as human-only, and notified instead of dispatching repair. A narrow hotfix covers `blocked_recovery_not_resolved`, but the durable fix is a shared custody and dispatch contract.

## Scope

In scope:

- Add a canonical repair custody projection over existing plan state, repair queue/request/decision artifacts, and repair-data records.
- Keep current artifacts readable during migration; do not delete or replace them wholesale.
- Separate repair request identity from repair attempt evidence.
- Define stable blocker identity with `blocker_id` derived from a structured `blocker_fingerprint`.
- Add a typed Python dispatch classifier that maps repair state, typed blocker intent, process/lock evidence, and custody evidence to exactly one decision.
- Move repairability decisions for the known `manual_review` repairable/human-gated paths out of shell branching and into the classifier.
- Add a shared atomic claim operation for active repair requests, used before any repair actor launches.
- Expose minimal status buckets for `repairing`, `repairable_not_repairing`, and `broken_superfixer`.
- Preserve existing safety gates: `ARNOLD_AUTONOMY`, repair feature flags, budgets, command allowlists, recursion guards, push gates, redaction, and watchdog self-integrity.

Out of scope:

- Completing the `agentic-replay-viewer` product feature.
- Full L3 auditor redesign.
- Full watchdog lock-service extraction.
- Full deployment/CI hardening beyond proving installed/source drift does not hide this fix.
- Broad cleanup of the shell watchdog unrelated to dispatch/custody boundaries.

## Locked Decisions

- `manual_review` is a state/operator posture, not a dispatch policy.
- Dispatch policy belongs in typed Python, not new shell branches.
- The canonical custody layer starts as a projection over existing artifacts, not a destructive replacement.
- `dispatched`, `claimed`, and `running` are non-terminal without attempt heartbeat or terminal outcome evidence.
- Unknown or ambiguous blockers default to `human_required` or `broken_superfixer`, never aggressive auto-repair.
- M1 must stay scoped to custody core; richer observability and L3 work are follow-up milestones.

## Touchpoints

Likely areas to inspect and modify:

- `arnold_pipelines/megaplan/cloud/repair_requests.py`
- `arnold_pipelines/megaplan/cloud/repair_contract.py`
- `arnold_pipelines/megaplan/cloud/repair_lock.py`
- `arnold_pipelines/megaplan/cloud/current_target.py`
- `arnold_pipelines/megaplan/cloud/human_blockers.py`
- `arnold_pipelines/megaplan/cloud/cli.py`
- `arnold_pipelines/megaplan/cloud/wrappers/arnold-watchdog`
- `arnold_pipelines/megaplan/cloud/wrappers/arnold-repair-trigger`
- `arnold_pipelines/megaplan/cloud/wrappers/arnold-repair-loop`
- `tests/cloud/`

## Done Criteria

- A fixture reproducing the `agentic-replay-viewer` failure dispatches L1 repair and never emits DM-only `needs_human`.
- Plan state and repair queue artifacts are both consumed by the canonical custody projection.
- A plan-local accepted repair request is visible through the projection and consumed by watchdog/repair-trigger.
- Exactly one repair actor can claim a given active blocker; concurrent claim tests prove single-winner behavior.
- Request identity and repair attempts are separate in the data model and tests.
- `dispatched`, `claimed`, and `running` do not count as terminal without attempt outcome evidence.
- Unknown state/failure/retry combinations produce `broken_superfixer` or conservative human gating.
- Minimal `cloud status` output can distinguish `repairing`, `repairable_not_repairing`, and `broken_superfixer`.
- Existing safety gates are preserved and covered by focused tests where this sprint touches them.
- Focused tests pass, including relevant `tests/cloud` coverage.
