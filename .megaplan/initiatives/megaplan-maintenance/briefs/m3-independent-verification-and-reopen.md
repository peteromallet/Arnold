# M3 — Independent verification and reopen

## Outcome

Separate repair attempt, provisional handoff, independent verification, closure, and reopen. A fix is successful only when later coherent observations prove the original blocker remains cleared.

## In scope

- Audit backlog rank 11 and the proposed `RepairAttempt.v1` and `VerificationEvent.v1` contracts.
- Independent checkpoints at immediate, 5 minutes, 1 hour, and 6 hours, with blocker-specific negative controls.
- Install identity, retrigger receipt, test evidence, cost, diff scope, canary install, rollback, regression linking, and reopen behavior.
- Preserve the `gpt-5.6-sol` pin and resolved-model receipts.

## Locked decisions

- The repair actor cannot write its own terminal verification.
- Process/tmux health can only produce provisional liveness.
- Unknown or contradictory evidence keeps custody open.
- A recurrence after verified closure creates a new occurrence and fresh bounded budget.

## Out of scope

- Broad production autonomy rollout.
- The six-hour aggregation/report redesign, except emitting the typed evidence it requires.

## Done criteria

- The full custody fault matrix covers alive-but-blocked, stale terminal state, failed install, wrong installed hash, recurrence, and human gates.
- Only blocker-cleared cases close; regressions reopen and link causally.
- One controlled canary proves install → retrigger → 5m/1h/6h verification, and a forced failure proves rollback.
- All model-backed repair receipts identify `gpt-5.6-sol`.

