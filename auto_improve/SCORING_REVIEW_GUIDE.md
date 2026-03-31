# Scoring Review Guide

When a task scores `resolved: false`, review it before accepting the result or excluding it from pass rate.

## Principle

The raw SWE-bench score (`resolved: true/false`) is the ground truth. Exclusions are exceptions that must be justified with evidence. When in doubt, keep the failure.

## When to Exclude

Only exclude when ALL of these are true:

1. **The source code fix is correct** — verified by reading the patch against the issue
2. **The failure is not caused by our code** — it's an environment, Docker, or SWE-bench harness issue
3. **The same fix would pass in a different scoring environment** — or the upstream/gold patch has the same behavior

## When NOT to Exclude

- "The fix is close but one test case fails" → NOT excludable. The fix is wrong.
- "The fix passes locally but fails in Docker" → Investigate first. Usually means the fix has an env-dependent bug (circular import, Python version difference). That's a real bug.
- "The SWE-bench test expects different behavior" → NOT excludable. Our fix doesn't match what's expected.
- "The executor modified test files" → NOT excludable. That's our pipeline's fault.

## How to Investigate Before Deciding

1. **Check the scoring report** (not just pipeline artifacts):
   ```bash
   # Find the test report
   find logs/run_evaluation -path "*<task_id>*" -name "report.json" | sort | tail -1

   # Read FAIL_TO_PASS and PASS_TO_PASS results
   python3 -c "import json; r=json.load(open('<path>')); ..."
   ```

2. **Check the test output**:
   ```bash
   find logs/run_evaluation -path "*<task_id>*" -name "test_output.txt" | sort | tail -1
   ```

3. **Compare with SWE-bench gold patch**:
   ```python
   from datasets import load_dataset
   ds = load_dataset('princeton-nlp/SWE-bench_Verified', split='test')
   for row in ds:
       if row['instance_id'] == '<task_id>':
           print(row['patch'])  # the known-correct fix
   ```

4. **Ask**: Would the gold patch also fail in this environment? If yes → env issue. If no → our fix is wrong.

## How to Write the Review

Edit `_watch_scores.json`, add a `review` field to the task entry:

```json
{
  "resolved": false,
  "review": {
    "category": "<category>",
    "explanation": "<detailed explanation with evidence>",
    "excluded_from_pass_rate": true,
    "reviewed_by": "<who>",
    "reviewed_at": "<ISO timestamp>"
  }
}
```

### Categories

| Category | Meaning | Excludable? |
|----------|---------|-------------|
| `env_regression` | Fix is correct but an unrelated test regresses due to Docker/Python version difference | YES — if gold patch has same behavior |
| `env_missing_dep` | Docker environment missing a package (e.g., `roman`) | YES — not our bug |
| `harness_error` | SWE-bench harness can't find prediction ID or crashes | YES — infra, not code |
| `partial_fix` | Fix covers most cases but misses one test | NO — fix is incomplete |
| `test_contamination` | Executor modified test files, conflicting with SWE-bench test patch | NO — pipeline fault |
| `wrong_detail` | Right approach but wrong implementation detail | NO — code is wrong |
| `circular_import` | Works locally but circular import in Docker | NO — real bug |
| `scoring_exhausted` | Scoring failed 3 times (auto-tagged) | INVESTIGATE — could be either |

### Example: Legitimate Exclusion

```json
"review": {
    "category": "env_missing_dep",
    "explanation": "All tests fail with 'No module named roman'. Docker env missing the roman package. Every test in test_build_linkcheck.py fails identically. Our patch (2-line fix adding TooManyRedirects to except clause) is correct — verified against upstream PR #8476. Gold patch would also fail in this env.",
    "excluded_from_pass_rate": true,
    "reviewed_by": "human",
    "reviewed_at": "2026-04-01T10:00:00Z"
}
```

### Example: NOT Excludable

```json
"review": {
    "category": "circular_import",
    "explanation": "Patch adds itrs_observed_transforms.py and imports it in __init__.py. Works locally but creates circular import in SWE-bench Docker (Python 3.9). This is a real bug in our patch — the import ordering is wrong. 68 PASS_TO_PASS tests also fail.",
    "excluded_from_pass_rate": false,
    "reviewed_by": "human",
    "reviewed_at": "2026-04-01T10:00:00Z"
}
```

## Dashboard Display

- Raw score always shown: `Scored: 10/13 = 77%`
- If exclusions exist: `| Adjusted: 11/12 = 92% (1 excluded)`
- Per-task: `→ FAIL [EXCLUDED: env_missing_dep]`
- Exclusions section at top with reasons

Both numbers are always public. The raw result is never modified.
