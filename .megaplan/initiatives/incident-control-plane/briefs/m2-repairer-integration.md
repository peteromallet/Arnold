---
superseded_by: custody-control-plane
---

# M2: Repairer Integration

## Outcome

Watchdog, chain runner, immediate repairer, meta repairer, and install sync use the incident control plane for recovery handoffs. A repair-system fix is not considered shipped until the ledger proves commit, install, retrigger, and original-condition verification.

## Design Inputs

- M1 ledger helper and `megaplan incident brief`.
- `.megaplan/audits/incident-control-plane-plan-20260703.md`

## Scope

In:

- Patch watchdog wrapper/prompt paths to create or update incident events for detections, live process evidence, stale report age, and next expected repair events.
- Patch chain runner paths to dispatch expired expected events and record chain lifecycle/stale-state findings.
- Patch immediate repairer prompts/wrappers to start from `megaplan incident brief`, claim expected events, record attempts, emit structured failures, and verify original failure signals.
- Patch meta repairer prompts/wrappers to diagnose immediate-repair failures, distinguish project blockers from repair-system failures, commit repair-system fixes when needed, call install sync, retrigger immediate repair, and verify recovery.
- Add install-sync event writing for commit SHA, target runtime id/path, sync command, before/after runtime identity, and verification command.
- Enforce the shipped-fix chain: `source_fix_committed -> install_sync_applied -> repair_retriggered/relaunch -> verified_recovered`.
- Add loop-breaking rules: no repeated immediate/meta attempt without new evidence, changed code, changed state, or changed hypothesis.
- Add tests around missing meta repair, stale immediate repair, source fix without install, install without retrigger, and retrigger without original-condition recovery.

Out:

- Do not make the six-hour auditor the main fixer yet.
- Do not add broad GitHub issue/comment publication yet.
- Do not solve every legacy watchdog edge case unrelated to incident handoff.

## Locked Decisions

- Immediate repair default timebox is 15 minutes or two attempts without new evidence.
- Meta repair treats the immediate repairer as the patient. It must record when the repairer is not the problem.
- Install sync is a first-class actor with its own evidence, not a hidden shell step.
- Subagents receive frozen briefs by default and cannot mutate ledger or commit unless explicitly delegated.

## Open Questions For Planner

- Exact dispatch command plumbing for cloud wrappers.
- How to identify the active cloud runtime robustly enough for install-sync verification.
- How much existing repair-loop JSON can be wrapped versus migrated.
- Which tests can run locally without real cloud processes.

## Done Criteria

- A watchdog-detected stalled incident leads to an immediate repair event or a clear expired expectation.
- Immediate repair failures reliably trigger meta-repair expectation/dispatch evidence.
- Meta repair source fixes require install-sync and retrigger evidence before they are considered shipped.
- `megaplan incident brief` can explain the full repairer chain for fixture incidents.
- Regression tests cover the known failure classes that motivated this initiative.
