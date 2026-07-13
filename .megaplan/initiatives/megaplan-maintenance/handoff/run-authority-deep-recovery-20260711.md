Diagnose the Run Authority cloud chain session `runauthority-epic-cloud` to the bottom and safely resume/advance it through the canonical Megaplan lifecycle.

Known canonical snapshot (2026-07-11T13:20:31Z): epic progress 100%, 2/3 sprints done, current plan `sprint-3-consumer-migration-20260711-0130` is `executed`, no live process, PR #212 open, automatic next action is review, and watchdog marks the session attention/stale. Workspace is `/workspace/runauthority-epic-cloud/Arnold`; chain spec is its initiative `runauthority-epic/chain.yaml`.

Requirements:
- Use Megaplan introspect, bounded trace, doctor, canonical chain state, watchdog evidence, and constrained/local operator surfaces. Do not run arbitrary remote shell commands.
- Establish the actual root cause, including why automatic executed→review progression did not happen and whether PR/review state, process custody, watchdog classification, editable-install drift, or transition authority is involved.
- Preserve existing work and avoid duplicate execution. Do not stash, checkout, reset, or discard changes.
- Apply the smallest safe one-time repair/resume action supported by the state machine and chain policy. The user explicitly authorized getting it resumed. Continue through review/next valid lifecycle transition where automatic policy permits.
- Verify live progress or a truthful terminal/gated state after intervention. If a genuine human approval or unsafe ambiguity blocks progress, stop and report the exact gate and evidence.
- Do not babysit or create recurring monitoring. Durable chain runners/watchdogs own continuation.
- Return a concise summary: root cause, action taken, resulting state, PR state, remaining blockers, and durable evidence.
