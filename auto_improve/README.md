# Auto-Improve Loop

Run SWE-bench Verified tasks. Score. Analyze failures. Fix the pipeline. Repeat.

## Prerequisites

- API keys in `auto_improve/api_keys.json` (see format below)
- `megaplan` CLI installed and on PATH
- `pip install -e .` in both hermes-agent and megaplan repos
- Docker running (for local scoring fallback)
- Modal account configured (`modal token set`) — primary scoring method

---

## The Process

Do these steps in order. Every time.

### Step 1: Run

```bash
# Small iteration (20 tasks, 3 workers, single key):
python -m auto_improve.loop --workers 3

# Full 500-task run with multiple keys (3 workers per key):
python -m auto_improve.loop --workers 3   # starts first 3 workers
python -m auto_improve.add_workers --iteration NNN --keys-file auto_improve/api_keys.json --start-id 3
```

Monitor with:
```bash
python -m auto_improve.dashboard          # overview
python -m auto_improve.dashboard --task django__django-12325   # inspect one task
```

The watch scorer runs automatically with auto-restart. If it dies, the dashboard shows `Scorer: NOT RUNNING ⚠` or `Scorer: DEAD ⛔`.

**Gate condition at 20 scored tasks:**
- Below 80% → kill the run, analyze failures, start improvement round
- 80%+ → continue (scale up if rate limits allow)

To add more API keys mid-run:
```bash
# Edit api_keys.json, then:
python -m auto_improve.add_workers --iteration NNN --keys-file auto_improve/api_keys.json --start-id 9
```

### Step 2: Review scores

Open `iterations/NNN/analysis.md`. Scores, task lists, and prior-iteration comparison are already filled in. Read them.

### Step 3: Analyze failures

For each failed task, use the dashboard inspector:
```bash
python -m auto_improve.dashboard --task <task_id>
```

This shows: phase trail, critique flags, gate decisions, patch summary, and score. For deeper investigation, read the artifacts under the worker's result directory.

**Important:** Don't trust the pipeline's "all tests pass" claim. Always check the actual SWE-bench scoring output:
```bash
# Find the real test results (not the executor's local run)
find logs/run_evaluation -path "*<task_id>*" -name "report.json" | sort | tail -1
find logs/run_evaluation -path "*<task_id>*" -name "test_output.txt" | sort | tail -1
```

The executor runs tests in a warm, partially-initialized environment. SWE-bench scores in a cold Docker. Things that pass locally can fail in Docker (circular imports, missing deps, Python version differences).

For each failure, decide: is it a real code bug or an environment issue? Follow `SCORING_REVIEW_GUIDE.md` to categorize and optionally exclude environmental failures from the adjusted pass rate.

Ask: **which phase went wrong?** Plan? Critique? Gate? Execute? Environment?

### Step 4: Categorize

Group failures by structural cause. Fill in "Failure Patterns" in `analysis.md`.

| Pattern | Meaning |
|---------|---------|
| `narrow_fix` | Fixed symptom, not disease |
| `incomplete_scope` | Fix covers reported case but misses adjacent edge cases |
| `wrong_api` | Correct approach, wrong implementation detail |
| `test_contamination` | Executor modified test files despite constraint |
| `env_mismatch` | Tested against installed package instead of patched source |
| `insufficient_verification` | Cherry-picked tests, missed regressions in full suite |
| `infra_error` | Worker/environment/scoring failure |

### Step 5: Hypothesize

What general changes would address the top patterns? Write them in the "Hypothesis" section of `analysis.md`. Fix everything obvious — don't artificially limit to one.

### Step 6: Implement improvements via megaplan

Run a megaplan to implement improvements. The megaplan idea text MUST include:

1. **Prior iteration context** — read `iterations/*/analysis.md` and `iterations/*/changes.md` for the last 2-3 iterations
2. **FINDINGS.md meta-learnings** — the accumulated wisdom
3. **This iteration's failure patterns** from your analysis (Step 4)
4. **Specific evidence** — which tasks failed, which phase went wrong
5. **Explicit constraints:**
   - "Every change must help ANY coding task, not just these specific failures"
   - "Prefer adding a sentence to a prompt over building a formal system"
   - "Simple instructions change model behavior; labels, schemas, and classification taxonomies usually don't"
   - "Read the existing prompts before proposing changes — don't duplicate what's already there"
6. **Infra fixes** — scoring reliability, process improvements. Always fair game.

After the megaplan executes, review critically:
- Did it build unnecessary scaffolding? Strip it back.
- Would a new developer understand the prompt changes without context? If not, rewrite.

Then:
- Fill in `iterations/NNN/changes.md` (what, why, evidence)
- Update `FINDINGS.md` if you learned something cross-cutting
- Commit megaplan changes: `cd /Documents/megaplan && git add -A && git commit -m "auto-improve NNN: <description>"`

### Step 7: Save iteration to GitHub

```bash
# In hermes-agent:
git switch -c auto-improve/iteration-NNN
git add auto_improve evals/
git commit -m "auto-improve: iteration NNN — <one-line summary>"
git push -u origin auto-improve/iteration-NNN
git switch main   # ← IMPORTANT: return to main before next run
```

### Step 8: Start next iteration

Go back to Step 1 with the improvements active.

---

## Rules

1. **Same model every iteration.** GLM-5.1 for all phases.
2. **No task-specific fixes.** If it only helps one task, don't do it.
3. **Simpler is better.** Prefer removing complexity over adding it.
4. **Record everything.** `analysis.md`, `changes.md`, `FINDINGS.md`. Every iteration.
5. **Branches are checkpoints.** `git checkout auto-improve/iteration-003` to jump back.
6. **One iteration at a time.** No parallel iterations.
7. **Don't change prompts mid-iteration.** Run → score → analyze → THEN change.

## Principles for Changes

1. **Categorize before you fix.** Target a pattern, not an instance.
2. **Fix everything obvious.** Multiple independent improvements = make them all.
3. **Cheapest intervention first.** Prompt sentence > code change > architecture change.
4. **Don't optimize for the eval.** Would this help *any* coding task? If not, don't do it.
5. **Regressions are worse than no progress.** Fixes 3 but breaks 2 = roll back.
6. **Information flow is usually the bottleneck.** Right info exists, wrong phase gets it.
7. **Read the audit trail before theorizing.** Look at what actually happened.
8. **Record the learning even if the fix doesn't work.** FINDINGS.md is the real output.
9. **Simple instructions > formal systems.** Direct instructions change model behavior; labels and schemas often don't.

## API Keys

```json
// auto_improve/api_keys.json (gitignored)
[
  {"key": "abc123...", "base_url": "https://api.z.ai/api/coding/paas/v4"},
  {"key": "def456...", "base_url": "https://api.z.ai/api/coding/paas/v4"}
]
```

Each key gets 3 workers. More keys = more parallelism without rate limiting.

## Files

```
auto_improve/
├── README.md                 ← you are here (the process doc)
├── SCORING_REVIEW_GUIDE.md   ← when/how to review and exclude scoring failures
├── FINDINGS.md               ← cross-cutting meta-learnings
├── tasks.json                ← current task list
├── api_keys.json             ← API keys (gitignored)
├── base_config.json          ← model + robustness config
├── loop.py                   ← orchestrator: run → score → scaffold docs
├── add_workers.py            ← add workers mid-run (multi-key support)
├── dashboard.py              ← live status + per-task inspector
├── run_experiment.py         ← launches parallel workers
├── score_experiment.py       ← scores predictions
├── history.py                ← cross-iteration task performance
├── utils.py                  ← compare_scores, load_scores helpers
└── iterations/NNN/
    ├── config.json           ← auto: materialized config for this run
    ├── scores.json           ← auto: pass/fail per task
    ├── analysis.md           ← auto-scaffolded → you fill TODOs (steps 2-5)
    ├── changes.md            ← auto-scaffolded → you fill details (step 6)
    └── consolidated/         ← auto: per-task patches + audit trails
```
