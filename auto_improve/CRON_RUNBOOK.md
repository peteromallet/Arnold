# Hourly Cron Runbook

**Active iteration: 021** (GLM-5.1 + MiniMax-M2.7, heavy robustness, 500 tasks)

## 1. Scores

```bash
python -m auto_improve.check_scores iteration-021
```

Note pass rate, new scores since last check, predictions pending scoring.

**If no new scores in 2+ hours**: something is wrong. Check scorer logs (`tail -20 /tmp/scorer-021.log`), check if predictions exist but aren't being scored (`ls -lt results/auto-improve/iteration-021/_swebench_predictions/ | head -5`). Restart scorer if needed.

## 2. Health

Check everything is alive and progressing. Fix anything broken immediately.

```bash
# Workers alive?
ps aux | grep run_evals | grep -v grep | wc -l

# Scorer alive?
ps aux | grep 'auto_improve.score' | grep -v grep

# Dashboard alive?
ps aux | grep dashboard_web | grep -v grep

# Worker phases — are they progressing?
for w in 0 1 2 3 4 5; do
  grep -a '\] [A-Z].*running\|ESCALATED\|PASSED\|FAILED' results/auto-improve/iteration-021/_worker_logs/worker-$w.stderr.log 2>/dev/null | grep -v resource_tracker | tail -1
done

# Review bug?
grep -ac 'incomplete review coverage' results/auto-improve/iteration-021/_worker_logs/worker-*.stderr.log

# Quota spinners?
for w in 0 1 2 3 4 5; do
  tail -50 results/auto-improve/iteration-021/_worker_logs/worker-$w.stderr.log 2>/dev/null | grep -c 'Weekly.*Limit'
done

# Disk
df -h /
```

**Restart commands:**
- Scorer: `nohup python -m auto_improve.score --watch --iterations 021 > /tmp/scorer-021.log 2>&1 &`
- Dashboard: `nohup python -m auto_improve.dashboard_web 021 --port 8080 > /dev/null 2>&1 &`
- Workers: `nohup python -m evals.run_evals --config results/auto-improve/iteration-021/_run_config.json -v > /dev/null 2>&1 &`
- Kill quota spinner: find worker-N PID and `kill` it (main loop restarts it)

**If no new predictions in 2+ hours**: check worker logs for what phase they're stuck on. Common causes:
- All workers in CRITIQUE loops (MiniMax slow) — wait, they'll resolve
- Workers hitting quota errors — kill the spinner, check key pool
- Review bug returned — alert immediately
- All workers escalating — check if it's a systemic issue vs hard tasks

**Scorer alive but stuck**: check if last few scorer log lines are the same error repeating (e.g. `tail -10 /tmp/scorer-021.log`). If the same task is erroring in a loop, kill the scorer, then restart. The stuck task will be retried with exponential backoff on the next cycle.

**Workers alive but all escalating**: check the last 10 completed tasks in worker logs — if >5 consecutive escalations, it's likely systemic, not just hard tasks. Diagnose:
```bash
# Count recent escalations vs completions
grep -a 'ESCALATED\|PASSED\|FAILED' results/auto-improve/iteration-021/_worker_logs/worker-*.stderr.log | tail -20
```
Common systemic causes we've hit:
- Review template bug (all escalate at review phase) → check for "incomplete review coverage"
- Gate override bug (all escalate at gate phase, PROCEED overridden) → check for "Overriding to ITERATE"
- API down (all fail at prep) → check for 429/5xx errors
If systemic: fix the root cause, requeue the escalated tasks, restart workers.

**Limbo tasks**: Check for tasks stuck in non-terminal states that aren't being retried:
```bash
python3 -c "
import json
from pathlib import Path
m = json.load(open('results/auto-improve/iteration-021/_task_manifest.json'))
s = json.load(open('results/auto-improve/iteration-021/_watch_scores.json'))
preds = set(p.stem for p in Path('results/auto-improve/iteration-021/_swebench_predictions').glob('*.jsonl'))
escalated = sum(1 for tid, t in m['tasks'].items() if t.get('status') == 'done' and tid not in preds)
errors = sum(1 for t in m['tasks'].values() if t.get('status') == 'error')
exhausted = sum(1 for t in s['tasks'].values() if isinstance(t.get('review',{}), dict) and t.get('review',{}).get('category') == 'scoring_exhausted')
print(f'Escalated (no patch): {escalated}, Errors: {errors}, Scoring exhausted: {exhausted}')
if escalated + errors + exhausted > 0: print('ACTION: requeue these tasks')
"
```
- **Escalated**: done but no prediction → requeue as pending
- **Errors**: failed with < 5 errors → requeue as pending
- **Scoring exhausted**: has prediction but scorer gave up → reset scoring attempts to 0

## 3. Failures

```bash
python -m auto_improve.check_false_negatives
```

If any >90% match to golden found: these are likely correct patches failed by scoring infra. Verify and resolve as PASS with documented reasoning.

For new FAILs: compare against golden patch to classify (close miss, wrong approach, incomplete, infra failure).

## 4. Push

```bash
python -m auto_improve.dashboard_export 021 --push
cd /path/to/hermes-agent && git add -A auto_improve/ evals/ tests/ && git diff --cached --quiet || git commit -m "auto: update from cron" && git push fork main
```

## 5. Report

Concise summary: scores, worker status, any issues found and fixed.
