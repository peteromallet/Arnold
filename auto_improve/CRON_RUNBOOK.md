# Cron Runbook

This runbook is **iteration-agnostic**: it describes how to operate and diagnose `auto_improve/cron.py` regardless of which iteration is currently active. The cron's target iteration is set by the `ITERATION` constant at the top of `auto_improve/cron.py` — update that one value to point the cron at a different run.

> Paths and log filenames below use `<ITER>` as shorthand for the active iteration (e.g. `021`, `022-robust`, `023-baseline`). Replace with the current value from `auto_improve/cron.py::ITERATION` when running commands by hand.

## Automated checks

```bash
python -m auto_improve.cron --fix --push
```

This handles: score check, process health, scorer stuck detection, quota spinners, review bug, worker staleness, limbo tasks, requeue loop detection, false negatives, stall detection, dashboard export, and git push.

The script maintains a **state file** (`_cron_state.json`) inside the iteration directory, between runs. This enables:
- **Delta reporting** — what changed since last run (preds, scored, passed)
- **Throughput** — tasks/hour since last run
- **Stall detection** — alerts after 2+ consecutive runs with zero progress
- **Requeue loop detection** — flags tasks that cycle through requeue 3+ times

The cron reads its liveness signals from the iteration's `_pidfile.json` (worker PIDs + scorer PID), **not** from `pgrep`. That means running multiple iterations side by side (e.g. the main run plus an experiment) will not cause cross-talk in the counts — the cron only reports on whichever iteration it's pointed at.

The script outputs three types of lines:
- `✓ FIXED: ...` — handled automatically, just report to user
- `⚠ ...` — needs manual investigation, use the sections below to diagnose and fix
- `⚠ ALERT: ...` — urgent, fix immediately

**Act on every `⚠` line.** Don't just report it — investigate using the sections below and fix it before reporting to the user.

## Pointing the cron at a different iteration

1. Edit `auto_improve/cron.py` and set `ITERATION` to the target iteration suffix — either pure digits (`"021"`) or a qualifier-bearing name (`"022-robust"`, `"023-baseline"`).
2. `ITER_DIR` will become `results/auto-improve/iteration-<ITERATION>` automatically.
3. The script normalizes the iteration name for `auto_improve.score` invocations, so both styles work.
4. Run `python -m auto_improve.cron` (no `--fix`) once to confirm the new iteration header and sensible counts before turning fixes back on.

## When the script can't fix it

### Mass escalation (>5 consecutive)

```bash
grep -a 'ESCALATED\|PASSED\|FAILED' results/auto-improve/iteration-<ITER>/_worker_logs/worker-*.stderr.log | tail -20
```

Check which phase they're dying at:
- All at review → review template bug returned
- All at gate → gate override bug returned
- All at prep → API down / all keys exhausted

Fix the root cause, requeue escalated tasks, restart workers.

### Systemic scoring failures

If the scorer keeps erroring on the same task, that task may have a Modal sandbox issue. Check `tail -20 /tmp/scorer-<ITER>.log`. Kill the scorer and restart — the stuck task gets exponential backoff. Modal-sandbox errors get capped at 2 retries before the task is marked exhausted; persistent failures on the same task should be flagged for manual review (compare the patch to golden).

### Dashboard repo wiped

OS cleans `/tmp` periodically. If the dashboard 404s:
```bash
cd /tmp && git clone https://github.com/peteromallet/swe-bench-challenge.git
```

### Requeue loop (same tasks cycling)

If the script reports tasks in a requeue loop:
1. Check `_cron_state.json` → `requeue_cycle_counts` for the task IDs
2. Read the task's history in `_task_manifest.json` to see error patterns
3. These tasks likely have a systemic issue (bad repo, unsupported test framework, dependency incompatibility)
4. Either fix the root cause or mark them as permanently failed via a human review entry

### Zero-progress stall

If the script reports zero progress for 2+ runs:
1. Check if workers are alive via the pidfile: `cat results/auto-improve/iteration-<ITER>/_pidfile.json`
2. Check whether all API keys are exhausted: look for 429s and quota-reset dates in recent worker logs
3. Check whether all remaining tasks are stuck in claimed-but-idle state in the manifest
4. If quota is the bottleneck and reset is hours away, **don't restart workers** — they'll just spin on the same exhausted keys

### Scoring-exhausted tasks need manual review

Tasks where scoring infrastructure failed but a patch exists get flagged by the cron for manual review. Compare the patch to the golden reference:
- **≥90% similarity** → resolve as PASS, mark with `reviewed_by: human` and `category: false_negative`
- **<90% similarity** → resolve as FAIL with `category: scoring_exhausted`

Use the helpers in `auto_improve/check_false_negatives.py` for similarity scoring.

### Review timeouts

The heavy-mode review runs multiple parallel LLM checks. If it exceeds the per-phase timeout (default 1200s):
1. Check `megaplan/parallel_review.py` concurrency setting
2. Check MiniMax key health — slow or flaky responses stretch review time
3. Phase retry can fail if the workspace directory has been cleaned up between attempts; investigate the workspace dir before restarting

## Known issues

| Issue | Symptom | Fix |
|-------|---------|-----|
| Review template bug | "incomplete review coverage" | Fixed in megaplan — restart workers |
| Gate override bug | Infinite critique→revise loops | Fixed in megaplan — restart workers |
| Z.AI quota exhaustion | 429 "Weekly/Monthly Limit Exhausted" | Key pool cools key 1h; other keys used |
| MiniMax 429 | Rate limit on critique/review | Key pool cools key 60s; OpenRouter fallback |
| MiniMax bad content | Worker falls back to OpenRouter mid-phase | Automatic; expect occasional slow phases |
| Scorer stuck | Same ERROR repeating in log | Kill and restart scorer |
| /tmp wiped | Dashboard 404 | Re-clone swe-bench-challenge repo |
| Mass escalation | >5 consecutive escalations | Diagnose phase — usually systemic bug |
| Worker stale | Alive but log not updating for 30m+ | Kill and restart the stale worker |
| Requeue loop | Same task IDs cycling 3+ times | Check task history, fix root cause or mark failed |
| Heavy review timeout | Review phase hits 1200s cap | Check MiniMax health; may need phase_timeout bump |
| Modal sandbox failure | "Error creating sandbox" in scorer log | Categorized as `modal_sandbox`, capped at 2 retries, flagged for manual review |

## Retry policy

Data shows ~60% of high-retry tasks eventually pass. Most failures are infrastructure, not model quality. Don't cap retries — keep requeuing. The cron script handles this automatically, and will alert if the same tasks cycle 3+ times.
