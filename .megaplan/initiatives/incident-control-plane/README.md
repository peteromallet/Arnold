---
superseded_by: custody-control-plane
---

# Incident Control Plane Initiative

Durable input material for implementing the Megaplan incident control plane.

Design inputs:

- `.megaplan/audits/incident-control-plane-plan-20260703.md`
- `.megaplan/audits/incident-control-plane-deepseek-review-20260703.md`
- `.megaplan/audits/incident-control-plane-codex-review-20260703.md`

Milestones:

- `m1-ledger-core-and-brief`: event schema, append helper, indexes, and read-only `megaplan incident brief`.
- `m2-repairer-integration`: watchdog, chain runner, immediate repairer, meta repairer, install sync, and prompts write/read incident events.
- `m3-auditor-github-and-hardening`: 6-hour auditor, GitHub sync, recurrence/problem index, redaction, and cloud rollout.

Prep recommendation:

- Overall plan difficulty: 5/5; selected profile: `partnered-5`; because bad decomposition or a weak control-plane contract can appear to work locally while preserving the exact class of autonomous-recovery failures this initiative is meant to eliminate.
- Robustness: `thorough`; because this touches the watchdog/repair/auditor loops and should get stronger critique before execution.
- Depth: `high`; because the planner must preserve a cross-actor state-machine invariant across wrappers, CLI, cloud runtime, and tests.
