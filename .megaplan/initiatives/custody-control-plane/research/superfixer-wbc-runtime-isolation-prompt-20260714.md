You are the implementation agent for a live Hetzner/agentbox superfixer incident. Work independently and make a narrowly scoped source fix, tests, commit, and push. Do not restart or hand-advance any chain.

Read these completely before acting:
- /workspace/arnold/arnold_pipelines/megaplan/data/_codex_skills/megaplan-cloud/SKILL.md
- /workspace/arnold/arnold_pipelines/megaplan/data/_codex_skills/superfixer-debug/SKILL.md

Incident/session: workflow-boundary-contracts-corrective-20260710, current plan s3-megaplan-boundary-coverage-20260713-1934. The product chain is live and advancing. Preserve it.

Observed source-layer defect:
- Deployed clean supervisor source is /workspace/.megaplan/repository-strategy-roadmap-supervisor-source, revision 4847a74c67d02d714dd9399f9728f60b139cc28e on origin/editible-install.
- Commit d63a4de568b53a98697f2c3d5816ff6183896667 correctly reconciles newer terminal repair-data with an older immutable launched queue receipt. Direct snapshot construction from the deployed clean source reports running/no_action.
- The cached canonical snapshot still reports repairing. /usr/local/bin/arnold-watchdog write_status_snapshot invokes `python3 -` without safe-path isolation. The wrapper process cwd is /workspace/arnold. For stdin execution, cwd appears on sys.path and shadows the configured supervisor source. The watchdog log contains imports from /workspace/arnold even though CLOUD_WATCHDOG_ARNOLD_SRC and MEGAPLAN_SUPERVISOR_SOURCE_ROOT point at the clean source.
- arnold_supervisor_runtime_init validates the interpreter using PYTHONSAFEPATH=1 and -P, but later wrapper calls through python3 omit that protection.

Required implementation:
1. Create a fresh isolated worktree outside /workspace/arnold based on the latest fetched origin/editible-install. Do not edit the dirty resident checkout or the live target workspace.
2. Confirm the observation-path root cause, inspect current canonical resident safety policy/docs, and hunt every sibling Python invocation in watchdog, repair-loop, meta-repair, and progress-auditor wrappers.
3. Fix isolation at the common source layer so all supervisor Python subprocesses use the resolved dedicated interpreter with safe-path semantics and cannot import an arbitrary cwd checkout. Preserve explicit runtime controls and existing source-root behavior. Do not weaken guards.
4. Add focused regression coverage that actually exercises a conflicting cwd/import shadow case, not only a text assertion. Include sibling coverage sufficient for all four wrappers.
5. Run proportionate tests: new isolation tests, watchdog wrapper tests, repair custody tests, bash -n for affected wrappers, and any focused auditor/meta tests implicated by the common layer.
6. Re-fetch before publishing and reconcile with any concurrent origin/editible-install movement. Commit with a clear message and push to origin/editible-install only after tests pass. Do not deploy runtime files, restart supervisors, re-trigger repairs, or touch the live chain; report exact safe deployment/refresh guidance based on current policy.

Return concise durable evidence: root cause, files changed, commit and pushed ref, exact tests/results, sibling hunt, and canonical narrow refresh procedure. If evidence disproves the proposed defect, do not force a fix; report that instead.
