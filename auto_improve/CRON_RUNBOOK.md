# Cron Runbook

**Active iteration: 021** (GLM-5.1 + MiniMax-M2.7, heavy robustness, 500 tasks)

## Automated checks

```bash
python -m auto_improve.cron --fix --push
```

This handles: score check, process health, scorer stuck detection, quota spinners, review bug, worker staleness, limbo tasks, requeue loop detection, false negatives, stall detection, dashboard export, and git push.

The script maintains a **state file** (`_cron_state.json`) between runs. This enables:
- **Delta reporting**: what changed since last run (preds, scored, passed)
- **Throughput**: tasks/hour since last run
- **Stall detection**: alerts after 2+ consecutive runs with zero progress
- **Requeue loop detection**: flags tasks that cycle through requeue 3+ times

The script outputs three types of lines:
- `✓ FIXED: ...` — handled automatically, just report to user
- `⚠ ...` — needs manual investigation, use the sections below to diagnose and fix
- `⚠ ALERT: ...` — urgent, fix immediately

**Act on every `⚠` line.** Don't just report it — investigate using the sections below and fix it before reporting to the user.

## When the script can't fix it

### Mass escalation (>5 consecutive)

```bash
grep -a 'ESCALATED\|PASSED\|FAILED' results/auto-improve/iteration-021/_worker_logs/worker-*.stderr.log | tail -20
```

Check which phase they're dying at:
- All at review → review template bug returned
- All at gate → gate override bug returned
- All at prep → API down / all keys exhausted

Fix the root cause, requeue escalated tasks, restart workers.

### Systemic scoring failures

If scorer keeps erroring on the same task, that task may have a Modal sandbox issue. Check `tail -20 /tmp/scorer-021.log`. Kill scorer, restart — the stuck task gets exponential backoff.

### Dashboard repo wiped

OS cleans `/tmp` periodically. If dashboard 404s:
```bash
cd /tmp && git clone https://github.com/peteromallet/swe-bench-challenge.git
```

### Requeue loop (same tasks cycling)

If the script reports tasks in a requeue loop:
1. Check `_cron_state.json` → `requeue_cycle_counts` for the task IDs
2. Read the task's history in `_task_manifest.json` to see error patterns
3. These tasks likely have a systemic issue (bad repo, unsupported test framework)
4. Either fix the root cause or mark them as permanently failed

### Zero-progress stall

If the script reports zero progress for 2+ runs:
1. Check if workers are alive: `pgrep -f run_evals`
2. Check if all API keys are exhausted: look for 429s in recent worker logs
3. Check if all remaining tasks are in a stuck state in the manifest

## Known issues

| Issue | Symptom | Fix |
|-------|---------|-----|
| Review template bug | "incomplete review coverage" | Fixed in megaplan — restart workers |
| Gate override bug | Infinite critique→revise loops | Fixed in megaplan — restart workers |
| Z.AI quota exhaustion | 429 "Weekly/Monthly Limit Exhausted" | Key pool cools key 1h; other keys used |
| MiniMax 429 | Rate limit on critique/review | Key pool cools key 60s; OpenRouter fallback |
| Scorer stuck | Same ERROR repeating in log | Kill and restart scorer |
| /tmp wiped | Dashboard 404 | Re-clone swe-bench-challenge repo |
| Mass escalation | >5 consecutive escalations | Diagnose phase — usually systemic bug |
| Worker stale | Alive but log not updating | Kill and restart the stale worker |
| Requeue loop | Same task IDs cycling 3+ times | Check task history, fix root cause or mark failed |

## Retry policy

Data shows ~60% of high-retry tasks eventually pass. Most failures are infrastructure, not model quality. Don't cap retries — keep requeuing. The cron script handles this automatically, and will alert if the same tasks cycle 3+ times.
