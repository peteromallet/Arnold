# Hourly Cron Runbook

This is the checklist that runs every hour. Go top to bottom, every time.

## 1. Scores

```bash
python -m auto_improve.check_scores iteration-021 iteration-022
```

Record: pass rate for each iteration, any new scores since last check.

## 2. Health Check

```bash
python -m auto_improve.healthcheck iteration-021 iteration-022
```

Fix anything it flags:
- **Scorer dead** → `nohup python -m auto_improve.score --watch --iterations 021 022 2>/tmp/scorer.log &`
- **Worker stalled >20 min** → check if rate limited or actually stuck. If stuck, kill and let manifest requeue.
- **Disk <10GB** → `rm -rf evals/workspaces-auto-improve/iteration-0{old iterations}/`

## 3. Rate Limit Tuning

Check 429 counts per worker. The goal: **some 429s but not excessive**.

| 429s/worker | Action |
|-------------|--------|
| 0 | We're under-utilizing — could add workers |
| 1-50 | Healthy — API is being used efficiently |
| 50-200 | Moderate — acceptable, monitor |
| 200+ | Too much — kill a worker or an iteration |

If all workers are >200 429s, consider killing one iteration to free up API capacity for the other.

## 4. Reaching 20 Scored Tasks

Both iterations must reach **20 scored tasks** before any decision is made. No exceptions.

### What counts as "scored"?
- PASS (resolved: true) ✓
- FAIL (resolved: false) ✓
- Reviewed and resolved via `python -m auto_improve.review --resolve pass/fail` ✓
- Unresolved SKIP ✗ — these must be reviewed first (see step 6)

### If tasks can't be scored (Modal failures, escalations):
Replace them with new random tasks so the iteration reaches 20 scored:
```bash
# Add replacement tasks to an iteration's manifest:
python -m auto_improve.add_tasks --iteration 021 --count 5 --seed 9999
```
The new tasks will be picked up by running workers automatically.

### If all 20 tasks are done but some are SKIP/unresolved:
Review every SKIP (step 6). Resolve each as PASS or FAIL with justification. If a SKIP can't be resolved (e.g., Modal failure + different approach from golden), resolve as FAIL and add a replacement task.

The goal: **20 tasks with a definitive PASS or FAIL verdict each. No limbo.**

## 5. Decision Gate (BOTH iterations at 20 scored)

**Wait for BOTH iterations to reach 20 scored before deciding.** Do not proceed early.

### Compare the two iterations:

| Scenario | Action |
|----------|--------|
| Both ≥ 80% | Pick the higher score. If tied, pick **standard** (faster, cheaper). Kill the other. Launch 500-task run. |
| One ≥ 80%, other < 80% | Pick the ≥ 80% one. Kill the other. Launch 500-task run. |
| Both < 80% | Kill both. Analyze failures (step 6). Implement improvements. Relaunch. |

### Launching the 500-task run:
1. Kill the losing iteration: `python -m auto_improve.kill --iteration XXX`
2. Update `base_config.json` with the winning config (robustness level, models)
3. Restore `tasks.json` to the full 500: `cp auto_improve/tasks.json.bak auto_improve/tasks.json`
4. Launch: `python -m auto_improve.loop --workers 3 --iteration NNN`
5. Start scorer: `nohup python -m auto_improve.score --watch --iterations NNN 2>/tmp/scorer.log &`

## 5. Failure Analysis (when pass rate < 80%)

For each FAIL task:

```bash
python -m auto_improve.dashboard --task <task_id>
```

Then compare against golden patch:
```python
# In Python:
from datasets import load_dataset
ds = load_dataset('princeton-nlp/SWE-bench_Verified', split='test')
golden = {inst['instance_id']: inst for inst in ds}
# Compare golden[task_id]['patch'] vs our prediction
```

Classify each failure:
- **Same approach as golden, minor difference** → close miss, model nearly got it
- **Different approach, ours is wrong** → model misunderstood the problem
- **Different approach, ours might work** → scoring environment issue
- **Critique flagged it but gate let through** → gate enforcement issue
- **Critique missed it** → critique prompt issue
- **Execute didn't test properly** → execute prompt issue

## 6. False Negative Check

```bash
python -m auto_improve.check_false_negatives
```

Compares failed patches against golden reference. If a failed task has >90% identical changes to golden, it's likely a scoring infrastructure failure, not a real failure.

- **100% match** → resolve as PASS via `python -m auto_improve.review --iteration 021 --task TASK_ID --resolve pass --category scoring_infra --golden identical`
- **>90% match** → inspect manually, resolve if functionally equivalent
- **<90%** → real failure, leave as is

All manual reviews must be documented with reasoning and are visible on the dashboard via the "Manually reviewed" filter.

## 7. SKIP Task Check

For SKIP tasks (Modal sandbox failures), compare our patch to golden:
- If patches are essentially identical → count as virtual PASS
- If different → note but don't count either way

## 8. Export & Push

```bash
python -m auto_improve.dashboard_export 021 --push
```

Updates the GitHub Pages dashboard with latest scores, traces, and probability estimates.

## 9. Report

Summarize for the user:
- Pass rates for each iteration
- New scores since last check
- Any issues found and fixed
- Rate limit status (healthy/moderate/excessive)
- Whether decision gate threshold has been reached
- Any SKIP tasks that match golden (virtual passes)
