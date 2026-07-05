# Progress Auditor / 6h Check Fix Decision - 2026-07-04

## Context

This decision record summarizes a direct `$megaplan-cloud` inspection plus a
five-agent DeepSeek fanout over the progress-auditor and superfixer evidence.

Subagent result files:

- `/tmp/auditor-fix-decision-results/01-wrapper-install-drift.txt`
- `/tmp/auditor-fix-decision-results/02-meta-repair-persistence.txt`
- `/tmp/auditor-fix-decision-results/03-watchdog-chain-health-disagreement.txt`
- `/tmp/auditor-fix-decision-results/04-auditor-gather-gaps.txt`
- `/tmp/auditor-fix-decision-results/05-stale-repair-custody.txt`

Direct cloud evidence came from `/workspace/watchdog-report.json`,
`/workspace/.megaplan/cloud-sessions/*.chain-health.progress.json`, and
`/workspace/.megaplan/meta-runs/*`.

## Decisions

### 1. Fix meta-repair persistence first

Decision: implemented locally.

Evidence:

- Latest Reigh meta-repair response began with `FIXED`.
- The same run log said `codex launch failed before producing a recordable
  meta-repair response; leaving recursion guard unpoisoned`.
- `arnold-meta-repair-loop` grepped both stdout and stderr for launch-failure
  text before accepting the parsed verdict. Stderr can contain old failure text
  from diagnostics, diffs, or test output even when stdout contains a valid
  verdict.

Fix:

- Parse `VERDICT` before the launch-failure grep.
- Only treat launch-failure text as fatal when stdout does not start with a
  recognized verdict: `FIXED`, `ESCALATE`, or `NO_FIX`.

Confidence: high. This explains the observed `FIXED` response being discarded.

### 2. Fix watchdog no-advance false positives during live work

Decision: implemented locally.

Evidence:

- `chain_health_status()` already avoids incrementing `no_advance_ticks` while
  `plan_has_live_activity` is true.
- The final `chain_no_advance` trigger did not re-check
  `plan_has_live_activity`, so a carried-over counter could fire after the plan
  became live again.
- Existing tests covered "live from the beginning" but not "counter already high,
  then plan becomes live."

Fix:

- Add `and not plan_has_live_activity` to the final `chain_no_advance` trigger.
- Add a regression test with a pre-existing high `no_advance_ticks` snapshot and
  a now-active plan step.

Confidence: high. This aligns the trigger with the counter logic and documented
intent.

### 3. Treat host progress-auditor drift as operational, not repair root cause

Decision: copy the current in-container `arnold-progress-auditor` to the host
before the next host timer run, but do not treat host wrapper drift as the cause
of repair/meta-repair behavior.

Evidence:

- The repair/watchdog/meta-repair processes run inside the cloud container.
- In-container wrappers matched the workspace wrappers during the subagent audit.
- The host `/usr/local/bin/arnold-progress-auditor` was stale and has degraded
  observability, but it does not dispatch repairs.

Recommended cloud command:

```bash
docker exec megaplan-cloud-agent cat /usr/local/bin/arnold-progress-auditor > /usr/local/bin/arnold-progress-auditor
chmod 755 /usr/local/bin/arnold-progress-auditor
```

Confidence: medium-high. It improves the 6h audit, but it is not the primary
cause of the observed self-healing loops.

### 4. Add auditor gather signals next

Decision: implemented locally and deployed to `$megaplan-cloud`.

Signals to add:

- `watchdog_chain_health_disagreement`: watchdog says `complete` or
  `awaiting_pr_merge`, but chain-health says `chain_complete=false`, PR is still
  open, or the chain is otherwise non-terminal.
- `repair_data_ghost_running`: repair-data says `running` with no current
  attempt/iterations while chain-health/watchdog evidence says terminal or absent.
- `green_with_recent_repair_churn`: backstop for sessions placed in
  `green_checks` despite recent repair/meta-repair churn or contradictory
  chain-health.

Evidence:

- `python-shaped-workflow-authoring`: chain-health had `chain_complete=true` and
  merged PR, while watchdog still reported `awaiting_pr_merge`.
- `native-composition-followup` and `code-smell-first-aid`: watchdog reported
  `complete` while chain-health reported incomplete/non-terminal state.
- Several sessions had `outcome=running` repair-data with no active attempt.

Confidence: high for the first two signals, medium for the green-check backstop.

Implementation notes:

- `arnold-progress-auditor` now records the matched watchdog item status/action
  in `prior_watchdog_report_refs`.
- `chain_state_summary.current` now carries `chain_complete`.
- `repair_data_summary` now carries `current_attempt_id`, `attempt_ids`, and
  `repair_run_count`.
- The gather reason pass now emits `watchdog_chain_health_disagreement`,
  `repair_data_ghost_running`, and `green_with_recent_repair_churn`.

Cloud verification:

- Deployed `arnold-progress-auditor` to the host, container `/usr/local/bin`, and
  `/workspace/arnold/.../wrappers`.
- Ran:

```bash
ARNOLD_AUDIT_AUTOFIX_ENABLED=0 ARNOLD_AUDIT_AUTOFIX_COMMIT_ENABLED=0 \
  /usr/local/bin/arnold-progress-auditor --once
```

- Report: `/workspace/audit-reports/20260704T110403Z-audit.json`.
- Result: 35 findings, 0 green checks.
- New deterministic reasons in that report:
  - `repair_data_ghost_running`: 17
  - `green_with_recent_repair_churn`: 18
  - `watchdog_chain_health_disagreement`: 0 in this latest snapshot.

While verifying this, a separate auditor safety bug surfaced and was fixed:

- Host-side report-only env vars were not forwarded into the container.
- An unquoted here-doc in the Codex prompt caused backtick text such as
  `FIXED`/`ESCALATE`/`NO_FIX` to execute as shell commands.
- The auditor now forwards report-only env vars through `docker exec`, quotes the
  static prompt here-doc, and skips Codex dispatch entirely when autofix is off.

### 5. Cleanup stale repair custody only after classification

Decision: do not manually purge ambiguous repair-data first.

Safe cleanup candidates exist, but deterministic classification should land
before touching ambiguous records. Otherwise the system can repeat the same
blind spot after the next run.

Confidence: medium-high.

## Verification Performed

Focused local tests:

```bash
PYTHONPATH=$PWD PYENV_VERSION=3.11.11 pytest -q \
  tests/cloud/test_watchdog_wrappers.py::test_arnold_meta_repair_loop_wrapper_bash_n_syntax \
  tests/cloud/test_watchdog_wrappers.py::test_meta_repair_wrapper_accepts_valid_verdict_before_launch_failure_grep \
  tests/cloud/test_watchdog_wrappers.py::test_chain_health_no_advance_ignores_existing_counter_after_plan_becomes_live \
  tests/cloud/test_watchdog_wrappers.py::test_chain_health_no_advance_ignores_active_plan_step \
  tests/cloud/test_watchdog_wrappers.py::test_chain_health_status_detects_busy_no_advance_across_ticks
```

Result: `5 passed`.

Note: the same test command without `PYTHONPATH=$PWD` fails because the extracted
wrapper Python cannot import `arnold_pipelines`; that is an invocation issue, not
a patch failure.
