# Hourly Cron Runbook

**Active iteration: 021** (GLM-5.1 + MiniMax-M2.7, heavy robustness, 500 tasks)

Be proactive — fix problems immediately, don't just report them.

## 1. Scores & Health

```bash
python -m auto_improve.check_scores iteration-021
```

Then check everything is alive:
- Workers: `ps aux | grep run_evals | grep -v grep | wc -l` (expect 6-7)
- Scorer: `ps aux | grep 'auto_improve.score' | grep -v grep` (expect 1)
- Dashboard: `ps aux | grep dashboard_web | grep -v grep` (expect 1)
- Disk: `df -h /` (alert if < 5GB)

Check worker phases are progressing (not stuck on same task for 30+ min).

**If anything is dead, restart it immediately** — see [Restart Commands](#restart-commands) below.

## 2. Diagnose Issues

Check for known failure patterns:
- **Review bug**: `grep -ac 'incomplete review coverage' results/auto-improve/iteration-021/_worker_logs/worker-*.stderr.log` — should be 0
- **Quota spinners**: check for `Weekly.*Limit` in recent worker logs — kill the worker if spinning
- **High-retry tasks** (5+ requeues, still unresolved): `python -m auto_improve.resolve_stuck` — check if infra or model quality
- **Limbo tasks** (escalated/errored, not retried): requeue as pending
- **Scorer stuck** on one task: `tail -10 /tmp/scorer-021.log` — if same error looping, kill and restart

## 3. Failures & Reviews

```bash
python -m auto_improve.check_false_negatives
```

If any >90% match to golden: verify and resolve as PASS with documented reasoning.

For new FAILs: compare against golden to classify (close miss, wrong approach, incomplete, infra failure).

## 4. Push & Report

```bash
python -m auto_improve.dashboard_export 021 --push
cd /Users/peteromalley/Documents/hermes-agent && git add -A auto_improve/ evals/ tests/ && git diff --cached --quiet || git commit -m "auto: update from cron" && git push fork main
```

Report concisely: scores, what changed, what you fixed, anything needing user attention.

---

## Restart Commands

```bash
# Scorer
nohup python -m auto_improve.score --watch --iterations 021 > /tmp/scorer-021.log 2>&1 &

# Dashboard
nohup python -m auto_improve.dashboard_web 021 --port 8080 > /dev/null 2>&1 &

# Workers (kills all and relaunches)
ps aux | grep 'run_evals' | grep -v grep | awk '{print $2}' | xargs kill 2>/dev/null
sleep 2
nohup python -m evals.run_evals --config results/auto-improve/iteration-021/_run_config.json -v > /dev/null 2>&1 &

# Dashboard repo wiped (/tmp cleaned by OS)
cd /tmp && git clone https://github.com/peteromallet/swe-bench-challenge.git
```

## Known Issues We've Hit

| Issue | Symptom | Fix |
|-------|---------|-----|
| Review template bug | "incomplete review coverage" on all tasks | Fixed in megaplan — restart workers |
| Gate override bug | Infinite critique→revise loops, PROCEED overridden | Fixed in megaplan — restart workers |
| Z.AI quota exhaustion | 429 "Weekly/Monthly Limit Exhausted" | Key pool now cools down key for 1h; other keys used |
| MiniMax 429 | Rate limit on critique/review | Key pool cools down key 60s; OpenRouter fallback |
| Scorer stuck on one task | Same ERROR repeating in scorer log | Kill scorer, restart — stuck task retries with backoff |
| /tmp wiped by OS | Dashboard 404, data.json missing | Re-clone swe-bench-challenge repo |
| Mass escalation | >5 consecutive escalations | Check which phase — usually a systemic bug |
