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
