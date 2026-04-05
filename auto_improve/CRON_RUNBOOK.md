# Hourly Cron Runbook

This is the checklist that runs every hour. Go top to bottom, every time.

**Active iteration: 021** (GLM-5.1 + MiniMax-M2.7, heavy robustness, 500 tasks)

## 1. Scores

```bash
python -m auto_improve.check_scores iteration-021
```

Record: pass rate, new scores since last check, predictions pending scoring.

## 2. Health Check

```bash
python -m auto_improve.healthcheck
```

Fix anything it flags:
- **Scorer dead** → `nohup python -m auto_improve.score --watch --iterations 021 > /tmp/scorer-021.log 2>&1 &`
- **Dashboard dead** → `nohup python -m auto_improve.dashboard_web 021 --port 8080 > /dev/null 2>&1 &`
- **Worker stalled >20 min** → check if rate limited or actually stuck. If stuck, kill and let manifest requeue.
- **Worker quota spinning** (Z.AI weekly limit) → kill that worker, it'll restart with a different key.
- **Disk <10GB** → `rm -rf evals/workspaces-auto-improve/iteration-0{old iterations}/`

## 3. Rate Limits

Check 429 counts per worker. Goal: **some 429s but not excessive**.

| 429s/worker | Action |
|-------------|--------|
| 0 | Healthy |
| 1-50 | Healthy |
| 50-200 | Moderate — monitor |
| 200+ | Kill that worker or check key pool |

Also check for Z.AI quota errors (`Weekly/Monthly Limit Exhausted`). These need the worker killed — retrying is futile until quota resets.

## 4. Review Bug Check

```bash
grep -ac 'incomplete review coverage' results/auto-improve/iteration-021/_worker_logs/worker-*.stderr.log
```

If any recent review failures, the review template bug may have regressed. Alert immediately.

## 5. False Negative Check

```bash
python -m auto_improve.check_false_negatives
```

Compares failed patches against golden reference. If a failed task has >90% identical changes to golden, it's likely a scoring infrastructure failure.

- **100% match** → resolve as PASS via review CLI with `category=scoring_infra, golden=identical`
- **>90% match** → inspect manually, resolve if functionally equivalent
- **<90%** → real failure, leave as is

All manual reviews must be documented with reasoning and visible on the dashboard via the "Manually reviewed" filter.

## 6. Failure Analysis

For new FAIL tasks, compare against golden patch:

```python
from datasets import load_dataset
ds = load_dataset('princeton-nlp/SWE-bench_Verified', split='test')
golden = {inst['instance_id']: inst for inst in ds}
```

Classify each failure:
- **Same approach as golden, minor difference** → close miss
- **Different approach, ours is wrong** → model misunderstood
- **Incomplete** → right approach, missed a file or change
- **Scoring infra** → correct patch, scoring failed

## 7. Export & Push

```bash
python -m auto_improve.dashboard_export 021 --push
```

Updates GitHub Pages dashboard with latest scores, traces, probability estimates, and full trace uploads to the GitHub Release.

Also push code changes:
```bash
cd /path/to/hermes-agent && git add -A auto_improve/ evals/ tests/ && git diff --cached --quiet || git commit -m "auto: update from cron" && git push fork main
```

## 8. Report

Summarize:
- Pass rate and change since last check
- Worker status (phases, any stuck/dead)
- Any issues found and fixed
- Any false negatives found and resolved
- Rate limit / quota status
