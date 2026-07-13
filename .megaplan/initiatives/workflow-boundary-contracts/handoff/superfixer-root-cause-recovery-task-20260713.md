# Superfixer root-cause and recovery task

Act as the deployment/root-repair operator for the existing Workflow Boundary Contracts corrective cloud session.

You must use and follow the `superfixer-debug` skill at `/workspace/arnold/arnold_pipelines/megaplan/data/_codex_skills/superfixer-debug/SKILL.md`. If that skill cannot be read, stop immediately without mutating anything and report exactly why.

## Target

- Existing session: `workflow-boundary-contracts-corrective-20260710`
- Existing plan: `c1-contract-reality-20260711-1433`
- Existing initiative: `workflow-boundary-contracts`
- Known repair request: `7473fa422fea89a936d0be64f25468524f0d7d0e1c8632478f5dcfc6ec37860e`

Do not create a replacement session, duplicate chain, or hand-advance plan/chain state. Do not weaken gates, fabricate success, or mark the incident resolved merely because code or tests pass.

## Required investigation

Trace the full chain of custody using the skill's four questions at every layer—TRACKED, FIXED, INTENT, CONTEXT—across:

1. watchdog and canonical status projection;
2. L1 repair-loop / request-claim-attempt lifecycle;
3. L2 meta-repair / broken-superfixer handling;
4. L3 six-hour progress auditor and its escalation/catch behavior.

Establish evidence-backed answers to all of these:

- Why the original WBC C1 failure happened.
- Why the first fixer did not fix it.
- Why request `7473fa...` was accepted/dispatched but remained at zero claims and zero attempts.
- Why the layer above did not detect and correct that failure.
- Whether stale process, sidecar, marker, installed-runtime, wrapper, custody, retry-budget, or projection disagreement contributed.
- The first broken custody layer and the first higher layer that should have caught it.

Ground truth must include the existing session's live process observation, cloud marker, chain state, plan state/events/logs, repair request/claim/attempt/custody records, meta-repair evidence, auditor evidence, installed runtime identity, and relevant external publication state where available.

## Required action

Once root cause is proven:

1. Fix the fixer/control-plane defect at the correct layer, including deterministic regression tests. Preserve genuine human gates and fail closed on unknown evidence.
2. Ensure a recurrence is automatically claimed/retried/repaired or escalated as broken automation with actionable evidence; it must not be falsely labeled human-required.
3. Ensure L2 can repair an L1 implementation/launch/custody defect and L3 deterministically catches a failed or stale L1/L2 cycle.
4. Re-trigger the canonical bounded repair path for the original `workflow-boundary-contracts-corrective-20260710` session.
5. Verify the original session—not a substitute—actually advances beyond the current C1 blockage and remains healthy long enough to establish recovery. Code changes, passing tests, a queued request, or a running repair process alone are insufficient.

If a genuine approval/credential/destructive-action/product-decision gate is reached, stop and report the exact typed gate and evidence instead of bypassing it.

## Operational constraints

- This agent is already on the AgentBox. Do not run arbitrary remote shell commands or raw SSH.
- Do not use `pkill`, `killall`, cgroup-wide/systemd-wide kills, or tmux cleanup.
- Use canonical Megaplan/on-box control paths and constrained cloud/status mechanisms.
- Preserve unrelated dirty work and existing sessions.
- Durable project findings belong only under `.megaplan/initiatives/workflow-boundary-contracts/` in the appropriate `research/`, `decisions/`, `notes/`, or `handoff/` folder. Runtime state remains under `plans/`.

## Completion report

Return a concise evidence-backed report containing:

- original failure root cause;
- first broken fixer layer;
- higher layer that failed to catch it;
- exact permanent prevention implemented and tests;
- retrigger evidence;
- original-session advancement evidence;
- remaining risks or exact human gate, if any;
- commits created, and whether anything was pushed.
