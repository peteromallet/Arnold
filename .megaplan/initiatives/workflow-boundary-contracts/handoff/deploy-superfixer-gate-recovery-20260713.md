# Deploy Superfixer Gate Recovery

## Objective

Diagnose, implement, test, and safely deploy the fix for the live Workflow Boundary Contracts corrective chain, which is stuck on S2 (`s2-contract-foundation-and-20260713-1544`) repeatedly failing the gate output structural audit because `north_star_actions` is missing. Restore the ordinary automatic repair chain of custody, retrigger it, and prove the original chain advances beyond the gate.

## Current evidence

- Cloud session: `workflow-boundary-contracts-corrective-20260710`.
- Canonical watchdog snapshot generated 2026-07-13T17:15:44Z reports the runner and heartbeat live, status `repairing`, overall 30% (1/4 milestones), S2 at 18% and `critiqued`.
- The gate repeatedly returns a prose recommendation while the structural audit requires a typed object including `north_star_actions`.
- The repair queue has an accepted request, but repair claim handoff has failed twice with `custody_missing`; repeated lifecycle requests are coalesced.
- The status projection says `repairing` because a repair sidecar/request exists, even though no effective repair claim is changing the failure mode.

## Required work

1. Follow the Superfixer chain of custody from watchdog detection through L1 repair, managed-agent launch/claim, L2/meta-repair, and the six-hour auditor. Identify the first layer that fails and the layer above it that should have caught the failure.
2. Diagnose the deterministic gate schema failure at its source. Inspect the gate prompt/schema/output adapter and determine why the worker emits prose without `north_star_actions`.
3. Implement the smallest robust correction. Preserve typed schema enforcement and safety guards; do not hand-advance the epic, edit runtime state to fake progress, or weaken structural validation.
4. Correct repair custody and escalation so `custody_missing` cannot leave a session indefinitely projected as effectively repairing. Deterministic repeated failures must change strategy or escalate through the proper managed repair layer rather than endlessly rerun the same phase.
5. Add focused regression tests covering the gate's required `north_star_actions`, deterministic structural-audit retries, repair claim/custody acquisition, and the upper-layer backstop/escalation behavior.
6. Deploy through the canonical on-box editable-install/wrapper mechanism. Do not use raw SSH or arbitrary remote shell commands. Do not restart the Discord resident unless the change genuinely requires it; if required, use only the canonical resident restart command and state that it can interrupt the current Discord turn.
7. Retrigger the ordinary repair path for `workflow-boundary-contracts-corrective-20260710`. Verify from durable evidence that the original S2 plan passes or advances beyond the gate and that watchdog/repair status reflects real custody and work.
8. Commit and publish the repair according to the repository's established deployment policy if tests pass and authority permits. Never bypass an approval gate, merge conflict, or failing required test.

## Deliverable

Return a concise verified summary with: root cause at each failed fixer layer, code/tests changed, test results, commit/deployment identity, retrigger evidence, the original chain's resulting state, and any remaining human action. If deployment or recovery cannot safely complete, report the exact blocker and durable evidence instead of claiming success.
