# Auto-Improve Loop

Run 20 tasks. Score. Analyze failures. Fix the pipeline. Repeat.

## Prerequisites

- `ZHIPU_API_KEY` and `ZHIPU_BASE_URL` set in `~/.hermes/.env`
- `megaplan` CLI installed and on PATH
- `pip install -e .` in both hermes-agent and megaplan repos
- Docker running (for local scoring)
- Modal account configured (`modal token set`) — required for scoring non-Django repos

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

Ask: **which phase went wrong?** Plan? Critique? Gate? Execute? Fill in the blanks next to each failed task (Phase, Pattern, Why).

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

### Step 5: Hypothesize

What general changes would address the top patterns? Write them in the "Hypothesis" section of `analysis.md`. Fix everything obvious — don't artificially limit to one.

### Step 6: Implement improvements via megaplan

Run a megaplan to implement improvements. The megaplan idea text MUST include:

1. **Prior iteration context** — read `iterations/*/analysis.md` and `iterations/*/changes.md` for the last 2-3 iterations. What patterns keep recurring? What was tried and didn't work? What did work?
2. **FINDINGS.md meta-learnings** — the accumulated wisdom about how to do this work
3. **This iteration's failure patterns** from your analysis (Step 4)
4. **Specific evidence** — which tasks failed, which phase went wrong, what the audit trail showed
5. **Explicit constraints** — include these in the idea text so the executor follows them:
   - "Every change must help ANY coding task, not just these specific failures"
   - "Prefer adding a sentence to a prompt over building a formal system"
   - "Simple instructions change model behavior; labels, schemas, and classification taxonomies usually don't"
   - "Don't add new fields to schemas unless the downstream consumer actually uses them"
   - "Read the existing prompts before proposing changes — don't duplicate what's already there"
6. **Infra fixes** — scoring reliability, process improvements. Always fair game.

After the megaplan executes, review the changes critically:
- Did it build unnecessary scaffolding? Strip it back.
- Did it add formal categories where a sentence would do? Simplify.
- Would a new developer understand the prompt changes without context? If not, rewrite.

Then:
- Fill in `iterations/NNN/changes.md` (what, why, evidence)
- Update `FINDINGS.md` if you learned something cross-cutting (not per-iteration details — those go in analysis.md)
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

### Step 8: Rotate tasks and start next iteration

Before going back to Step 1, update `tasks.json`:
- Keep ~10 tasks that passed (anchors — detect regressions)
- Keep ~5 tasks that failed (retries — test if your fix helped)
- Add ~5 new tasks from SWE-bench Verified (generalization — does it work on unseen tasks?)
- Maintain repo diversity (don't let it drift to all-django)

Then go back to Step 1. If pass rate hits **90%+ on the 20-task sample**, run the full 500-task SWE-bench Verified to get a real benchmark score.

---

## Rules

1. **Same model every iteration.** GLM-5.1 for all phases.
2. **20 tasks per iteration, rotating mix.** Each batch should be:
   - ~10 **anchors** — tasks that passed before (regression detection)
   - ~5 **retries** — tasks that failed before (did the fix help?)
   - ~5 **new** — unseen tasks (generalization signal)
   Update `tasks.json` each iteration based on prior results. Keep repo diversity.
3. **No task-specific fixes.** If it only helps one task, don't do it.
4. **Simpler is better.** Prefer removing complexity over adding it.
5. **Record everything.** `analysis.md`, `changes.md`, `FINDINGS.md`. Every iteration.
6. **Branches are checkpoints.** `git checkout auto-improve/iteration-003` to jump back.
7. **One iteration at a time.** No parallel iterations.

## Principles for Changes

1. **Categorize before you fix.** Target a pattern, not an instance.
2. **Fix everything obvious.** If the analysis reveals multiple independent improvements, make them all.
3. **Cheapest intervention first.** Prompt sentence > code change > architecture change.
4. **Don't optimize for the eval.** Would this help *any* coding task? If not, don't do it.
5. **Regressions are worse than no progress.** Fixes 3 but breaks 2 = roll back.
6. **Information flow is usually the bottleneck.** Right info exists, wrong phase gets it.
7. **Read the audit trail before theorizing.** Look at what actually happened.
8. **Record the learning even if the fix doesn't work.** FINDINGS.md is the real output.
9. **Simple instructions > formal systems.** "Estimate the scope" beats a classification taxonomy. "Read the traceback" beats a structured diagnosis framework. Direct instructions change model behavior; labels and schemas often don't.
10. **Don't change prompts mid-iteration.** Run → score → analyze → THEN change. Mixing invalidates the experiment.

## Files

```
auto_improve/
├── README.md                 ← you are here (the only process doc)
├── FINDINGS.md               ← cross-cutting meta-learnings (not per-iteration details)
├── tasks.json                ← current 20 tasks (rotated each iteration)
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
