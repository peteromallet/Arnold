# Sol review brief — critique recovery control-plane category

## Decision requested

Review the current recovery direction and identify the broader category of failure underneath the VJ8 incident. Take a firm position on: (1) whether the current fixes are root-level or only local mitigation, (2) every additional surface Luna should audit, and (3) the shortest safe plan to make the current critique session resume without hiding legitimate U1/quality gates.

## Target and evidence

- Cloud session: `critique-ledger-accountability-v3-r5-20260803`
- Workspace: `/workspace/critique-ledger-accountability-v3-r5-20260803/Arnold`
- Plan: `cl2-wbc-backed-ledger-20260803-1357`
- State after occurrence-scoped repair: `finalized`, execution entry `execute`, `next_step=execute`.
- Original VJ8 failure: `pre_dispatch_validation_failed`, phase `execute`, `worker_dispatched=false`, exit code 1, occurrence `validation-8a0d0d672f63643cc82e`, signature `sha256:8a0d0d672f63643cc82ef81841ab9493b87bfe69671c5da9d961dc60c878c4d3`.
- Exact validation rerun after source/test repair: 130 passed, 0 failed.
- Occurrence receipt: `.megaplan/plans/cl2-wbc-backed-ledger-20260803-1357/validation_repairs/VJ8-validation-8a0d0d672f63643cc82e.json`.
- Existing prior review: `evidence/critique-ledger-recovery/sol-review-r5-20260804.md`.

## Repairs already applied in the target worktree

- Ledger exact-retry canonicalization preserves omitted optional VersionSet fields as `None`; divergent same-key events raise typed `IdempotencyConflictError`; tests now cover exact retry, conflict, and transaction atomicity.
- Outbox and ledger use a shared canonical event representation.
- `pre_dispatch_validation_failed` and `validation_job_failed` are machine-repairable only through an occurrence-bound receipt that binds failure signature, job, source revision, test result, and runtime hash.
- Recovery refuses stale/mismatched phase evidence and refuses to bypass genuine blockers.
- Status exposes `latest_failure`; finalized projects to `execute` because finalized is an execute-entry state, not terminal.

## New evidence: cloud wrapper regression

The canonical local `cloud resume` wrapper did not reach the plan. Its SSH provider issued:

```text
cd /workspace/critique-ledger-accountability-v3-r5-20260803/Arnold && arnold status --plan cl2-wbc-backed-ledger-20260803-1357
```

On the cloud container, `arnold` resolves to `/root/.pyenv/shims/arnold`, whose installed CLI exposes a different interface and rejects the request:

```text
usage: arnold status [-h] --artifact-root ARTIFACT_ROOT
arnold status: error: the following arguments are required: --artifact-root
```

The canonical runtime venv (`/workspace/runtime-venvs/arnold-wbc-full-20260804`) can execute the intended megaplan CLI and returns the correct payload (`state=finalized`, `execution_state=ready`, `next_step=execute`, while preserving unresolved U1/quality blockers). Thus the immediate blocker is a runtime/entrypoint identity mismatch in the cloud control plane, not a new plan failure.

## Constraints

- Do not fabricate CL1/U1 handoffs or resolve quality blockers just to make the run advance.
- Do not force-proceed, create a new chain, or declare liveness from tmux/state-only evidence.
- The durable fix must apply to all cloud megaplan sessions, not only this critique plan.

## Ask Sol to return

Return a ranked root-cause tree; a bounded Luna audit matrix (one task per independent surface); the minimum safe cloud-entrypoint/lease repair; and a two-stage rollout: get this exact session moving now, then harden the shared system. Flag any judgement call that must remain human-gated.
