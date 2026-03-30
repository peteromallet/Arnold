# Auto-Improve Loop

Run 20 tasks. Score. Analyze failures. Fix the pipeline. Repeat.

## Prerequisites

- `ZHIPU_API_KEY` and `ZHIPU_BASE_URL` set in `~/.hermes/.env`
- `megaplan` CLI installed and on PATH
- `pip install -e .` in both hermes-agent and megaplan repos
- Docker running (for scoring)

---

## The Process

Do these steps in order. Every time.

### Step 1: Run

```bash
python -m auto_improve.loop --workers 3
```

This launches 20 SWE-bench tasks, scores them, and writes `iterations/NNN/scores.json`. It also pre-fills `analysis.md` and scaffolds `changes.md`. Takes ~1-2 hours.

### Step 2: Review scores

Open `iterations/NNN/analysis.md`. Scores, task lists, and prior-iteration comparison are already filled in. Read them.

### Step 3: Analyze failures

For each failed task in `analysis.md`, read the audit trail:
- `iterations/NNN/consolidated/tasks/{task_id}/audit.json`
- `iterations/NNN/consolidated/tasks/{task_id}/patch.diff`

Ask: **which phase went wrong?** Plan? Critique? Gate? Execute? Fill in the "TODO: root cause" next to each failed task.

### Step 4: Categorize

Group failures by structural cause. Fill in "Failure Patterns" in `analysis.md`.

| Pattern | Meaning |
|---------|---------|
| `narrow_fix` | Fixed symptom, not disease |
| `over_defensive` | Added unnecessary fallbacks/wrappers |
| `wrong_approach` | Rejected correct approach for worse one |
| `under_scoped` | Limited scope to avoid breaking things |
| `unverified` | Couldn't verify, proceeded anyway |
| `infra_error` | Worker/environment/scoring failure |

### Step 5: One hypothesis

Pick the biggest pattern. Propose **one** general change. Write it in the "Hypothesis" section of `analysis.md`.

### Step 6: Implement the fix

Make the change. Usually a prompt edit in `/Documents/megaplan/megaplan/prompts.py` (separate repo). Then:
- Fill in `iterations/NNN/changes.md` (what, why, evidence)
- Add an entry to `FINDINGS.md`
- Commit the megaplan change: `cd /Documents/megaplan && git add -A && git commit -m "auto-improve NNN: <description>"`

### Step 7: Save iteration to GitHub

```bash
# In hermes-agent:
git switch -c auto-improve/iteration-NNN
git add auto_improve evals/
git commit -m "auto-improve: iteration NNN — <one-line summary>"
git push -u origin auto-improve/iteration-NNN
git switch main   # ← IMPORTANT: return to main before next run
```

### Step 8: Start the next iteration

Go back to Step 1. If pass rate hits **90%+ on the 20-task sample**, run the full 500-task SWE-bench Verified to get a real benchmark score.

---

## Rules

1. **Same model every iteration.** GLM-5.1 for all phases.
2. **Same 20 tasks every iteration.** `tasks.json` — 10 repos, fixed sample.
3. **No task-specific fixes.** If it only helps one task, don't do it.
4. **Simpler is better.** Prefer removing complexity over adding it.
5. **Record everything.** `analysis.md`, `changes.md`, `FINDINGS.md`. Every iteration.
6. **Branches are checkpoints.** `git checkout auto-improve/iteration-003` to jump back.
7. **One iteration at a time.** No parallel iterations.

## Principles for Changes

1. **Categorize before you fix.** Target a pattern, not an instance.
2. **One hypothesis per iteration.** Change one thing, measure the effect.
3. **Cheapest intervention first.** Prompt sentence > code change > architecture change.
4. **Don't optimize for the eval.** Would this help *any* coding task?
5. **Regressions are worse than no progress.** Fixes 3 but breaks 2 = roll back.
6. **Information flow is usually the bottleneck.** Right info exists, wrong phase gets it.
7. **Read the audit trail before theorizing.** Look at what actually happened.
8. **Record the learning even if the fix doesn't work.** FINDINGS.md is the real output.

## Files

```
auto_improve/
├── README.md                 ← you are here (the only process doc)
├── FINDINGS.md               ← cumulative learnings (append each iteration)
├── tasks.json                ← the 20 tasks (fixed, 10 repos)
├── base_config.json          ← model + robustness config (heavy = prep phase)
├── loop.py                   ← orchestrator: run → score → scaffold docs
├── dashboard.py              ← `python -m auto_improve.dashboard` for live status
├── run_experiment.py         ← launches parallel workers
├── score_experiment.py       ← scores predictions
├── utils.py                  ← compare_scores, load_scores helpers
└── iterations/NNN/
    ├── config.json           ← auto: materialized config for this run
    ├── scores.json           ← auto: pass/fail per task
    ├── analysis.md           ← auto-scaffolded → you fill TODOs (steps 2-5)
    ├── changes.md            ← auto-scaffolded → you fill details (step 6)
    └── consolidated/         ← auto: per-task patches + audit trails (step 3)
```
