# Scoring Review Guide

When a task scores `resolved: false` or `resolved: null` (SKIP), review it before accepting the result.

## CLI Tool

```bash
# Review a failed task — adds a review entry to _watch_scores.json:
python -m auto_improve.review --iteration 021 --task django__django-14011 \
    --category partial_fix \
    --explanation "Fix covers 3/4 test cases but misses samesite+secure interaction" \
    --exclude false

# Review a SKIP task as a virtual pass (patch matches golden):
python -m auto_improve.review --iteration 021 --task sympy__sympy-20590 \
    --category golden_match \
    --explanation "Our patch is identical to golden — adds __slots__ = () to Printable" \
    --exclude true

# View all reviews for an iteration:
python -m auto_improve.review --iteration 021 --list
```

## Principle

The raw SWE-bench score (`resolved: true/false/null`) is the ground truth. Reviews add context but never silently change the raw result. Exclusions adjust the pass rate denominator and must be justified with evidence. When in doubt, keep the failure.

## Decision Framework

For every failed or skipped task, answer these questions in order:

### Question 1: Did we produce a patch?
- **No patch (escalated)** → Category: `escalated`. Not excludable. This is a pipeline failure.
- **Yes** → Continue to Q2.

### Question 2: Was the patch applied successfully?
- **No (patch doesn't apply)** → Category: `bad_patch`. Not excludable.
- **Yes** → Continue to Q3.

### Question 3: Did the tests actually run?
- **No (Modal sandbox failure, missing dep, harness crash)** → Compare against golden patch (Q3a).
  - **Q3a: Is our patch essentially the same as golden?** → Category: `golden_match`. Excludable (virtual pass).
  - **Q3a: Different from golden** → Category: `scoring_infra`. Excludable only if golden would also fail in this env.
- **Yes, tests ran** → Continue to Q4.

### Question 4: Which tests failed?
- **FAIL_TO_PASS tests failed (our fix didn't work)** → Continue to Q5.
- **Only PASS_TO_PASS regressions (our fix broke existing tests)** → Category: `regression`. Not excludable.
- **Both** → Category: `partial_fix` or `regression`. Not excludable.

### Question 5: Compare our patch to golden patch.
- **Same files, same approach, minor difference** → Category: `close_miss`. Not excludable, but note for improvement.
- **Same files, different approach, ours is plausibly correct** → Category: `alternative_approach`. Investigate deeper — the SWE-bench test may be too narrow.
- **Wrong files or wrong approach** → Category: `wrong_approach`. Not excludable.
- **Right approach but wrong implementation detail** → Category: `wrong_detail`. Not excludable.

### Question 6: Could the pipeline have caught this?
Always answer this regardless of excludability:
- **Critique flagged it but gate let through** → Note: gate enforcement issue.
- **Critique missed it** → Note: critique prompt gap.
- **Execute didn't test the bug scenario** → Note: bug reproduction step missed.
- **Review rubber-stamped** → Note: review quality issue.

## Categories

| Category | Meaning | Excludable? | Required Evidence |
|----------|---------|-------------|-------------------|
| `golden_match` | Our patch matches the golden patch but scoring infra failed | YES | Show patch comparison |
| `env_regression` | Fix correct, unrelated test regresses in Docker | YES | Show golden has same behavior |
| `env_missing_dep` | Docker env missing a package | YES | Show the import error, verify golden would also fail |
| `harness_error` | SWE-bench harness crash (not our code) | YES | Show harness error log |
| `scoring_infra` | Modal/Docker couldn't run tests, patch differs from golden | MAYBE | Compare patches, explain why ours might work |
| `partial_fix` | Fix covers most cases but misses one test | NO | Show which test failed and why |
| `close_miss` | Same approach as golden, minor detail wrong | NO | Show the diff between our patch and golden |
| `wrong_detail` | Right approach, wrong implementation | NO | Explain the implementation error |
| `wrong_approach` | Fundamentally different from golden | NO | Explain why our approach fails |
| `regression` | Fix works but breaks existing tests | NO | Show PASS_TO_PASS failures |
| `test_contamination` | Executor modified test files | NO | Show test file modifications |
| `escalated` | Pipeline gave up, no patch produced | NO | Note which phase failed |
| `scoring_exhausted` | Scoring failed N times (auto-tagged) | INVESTIGATE | Check stderr for root cause |

## Review Entry Format

Each review is stored in `_watch_scores.json` on the task entry:

```json
{
  "resolved": false,
  "review": {
    "category": "<category from table above>",
    "explanation": "<detailed explanation — MUST include evidence, not just a claim>",
    "excluded_from_pass_rate": true,
    "golden_comparison": "<same/similar/different/not_checked>",
    "pipeline_gap": "<critique_missed/gate_bypass/execute_no_test/review_rubber_stamp/none>",
    "reviewed_by": "<human or auto>",
    "reviewed_at": "<ISO timestamp>"
  }
}
```

### Required fields for every review:
- **category**: From the table above.
- **explanation**: What happened and why. Must cite specific evidence (file names, test names, error messages). "Fix is wrong" is not enough — say WHY it's wrong.
- **excluded_from_pass_rate**: true/false. Only true for categories marked YES above.
- **golden_comparison**: Did you compare against the golden patch? What did you find?
- **pipeline_gap**: Which pipeline phase could have prevented this? This is the most important field for improvement — it feeds back into the next iteration's changes.

### Example: SKIP task that matches golden (virtual pass)

```json
"review": {
    "category": "golden_match",
    "explanation": "Our patch adds __slots__ = () to Printable class in sympy/core/_print_helpers.py — identical to golden patch. Modal sandbox build fails on sympy (setup_repo.sh exit 2). Cannot score but fix is correct.",
    "excluded_from_pass_rate": true,
    "golden_comparison": "same",
    "pipeline_gap": "none",
    "reviewed_by": "human",
    "reviewed_at": "2026-04-03T01:00:00Z"
}
```

### Example: Real failure, critique should have caught it

```json
"review": {
    "category": "partial_fix",
    "explanation": "Fix handles lazy+string concatenation but not lazy+lazy. test_lazy_add fails with TypeError. Golden patch uses a different approach (force_str on both operands). Critique flagged 'overly broad TypeError catch' but gate resolved it as accept_tradeoff.",
    "excluded_from_pass_rate": false,
    "golden_comparison": "different",
    "pipeline_gap": "gate_bypass",
    "reviewed_by": "human",
    "reviewed_at": "2026-04-03T01:00:00Z"
}
```

### Example: Real failure, not excludable

```json
"review": {
    "category": "wrong_detail",
    "explanation": "Patch quotes table_name with quote_name() but not column_name. SQL keyword 'order' causes syntax error in SELECT. Golden patch quotes all 3 identifiers. Critique should have verified ALL identifiers are quoted.",
    "excluded_from_pass_rate": false,
    "golden_comparison": "similar",
    "pipeline_gap": "critique_missed",
    "reviewed_by": "human",
    "reviewed_at": "2026-04-03T01:00:00Z"
}
```

## Dashboard Display

- Raw score always shown: `Scored: 10/13 = 77%`
- If exclusions exist: `| Adjusted: 11/12 = 92% (1 excluded)`
- Per-task: `→ FAIL [EXCLUDED: golden_match]` or `→ SKIP [EXCLUDED: golden_match]`
- Exclusions section at top with reasons

Both numbers are always public. The raw result is never modified.

## Integration with Cron Runbook

The hourly cron job (see `CRON_RUNBOOK.md`) includes failure analysis at step 5. When new FAILs appear:

1. Compare against golden patch
2. Classify using the decision framework above
3. Write a review entry (via CLI or manual JSON edit)
4. Note the `pipeline_gap` — this feeds into the next improvement round

When SKIP tasks appear:
1. Compare our patch against golden
2. If identical/essentially same → review as `golden_match`, exclude from pass rate
3. If different → review as `scoring_infra`, investigate further
