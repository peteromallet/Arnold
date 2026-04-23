# Auto-Improve Loop

Run SWE-bench Verified tasks. Score. Analyze failures. Fix the pipeline. Repeat.

## Prerequisites

- API keys in `auto_improve/api_keys.json` (see [API Keys](#api-keys) below)
- Additional provider keys in `~/.hermes/.env` (MiniMax, Google, OpenRouter)
- `megaplan` CLI installed and on PATH
- `pip install -e .` in both hermes-agent and megaplan repos
- Modal account configured (`modal token set`) — primary scoring method
- Docker Desktop (optional — fallback scoring if Modal fails)

---

## Configuration

### base_config.json

Controls model selection, robustness level, and run parameters:

```json
{
  "benchmark": "swe-bench",
  "models": {
    "prep": "zhipu:glm-5.1",
    "plan": "zhipu:glm-5.1",
    "critique": "minimax:MiniMax-M2.7-highspeed",
    "revise": "zhipu:glm-5.1",
    "gate": "zhipu:glm-5.1",
    "finalize": "zhipu:glm-5.1",
    "execute": "zhipu:glm-5.1",
    "review": "minimax:MiniMax-M2.7-highspeed"
  },
  "robustness": "heavy",
  "max_gate_iterations": 3,
  "eval_timeout_seconds": 1200,
  "workers": 3
}
```

Each phase can use a different model. You can mix providers freely.

### Provider Prefixes

Model strings use a `provider:model` format. The prefix determines API routing:

| Prefix | API Endpoint | Key env var | Fallback |
|--------|-------------|-------------|----------|
| `zhipu:` | Z.AI (`api.z.ai/api/coding/paas/v4`) | `ZHIPU_API_KEY` | None |
| `minimax:` | MiniMax direct (`api.minimax.io/v1`) | `MINIMAX_API_KEY` | OpenRouter (if MiniMax fails) |
| `google:` | Google Gemini (`generativelanguage.googleapis.com`) | `GEMINI_API_KEY` | None |
| No prefix | OpenRouter (`openrouter.ai/api/v1`) | `OPENROUTER_API_KEY` | None |

Keys are loaded from env vars first, then `~/.hermes/.env` as fallback. The MiniMax provider automatically falls back to OpenRouter on API errors (429s, timeouts).

### Robustness Levels

| Level | Critique checks | Gate iterations | Review | Use when |
|-------|----------------|-----------------|--------|----------|
| `light` | General review (0 structured checks) | Single pass (no gate loop) | Skipped | Quick fixes, fast iteration |
| `standard` | 4 core checks (issue_hints, correctness, scope, verification) | Up to 3 | Full | Most tasks |
| `heavy` | 8 checks (core + all_locations, callers, conventions, criteria_quality) | Up to 3 | Full | Complex bugs, unfamiliar codebases |

### API Keys

```json
// auto_improve/api_keys.json (gitignored)
[
  {"key": "abc123...", "base_url": "https://api.z.ai/api/coding/paas/v4"},
  {"key": "def456...", "base_url": "https://api.z.ai/api/coding/paas/v4"},
  {"key": "ghi789...", "base_url": "https://api.z.ai/api/coding/paas/v4"}
]
```

Keys are distributed round-robin across workers within each iteration. With 3 keys and 3 workers, each worker gets its own key. Running multiple iterations multiplies load per key (3 iterations × 1 worker = 3 workers per key).

Other provider keys go in `~/.hermes/.env`:
```bash
MINIMAX_API_KEY=sk-...
MINIMAX_BASE_URL=https://api.minimax.io/v1
OPENROUTER_API_KEY=sk-or-v1-...
GEMINI_API_KEY=AIza...
```

---

## CLI Commands

### Running iterations

```bash
# Start a new iteration (auto-increments iteration number):
python -m auto_improve.loop --workers 3

# Start with a specific iteration number:
python -m auto_improve.loop --workers 3 --iteration 025

# Force-restart a stale iteration (cleans old artifacts first):
python -m auto_improve.loop --workers 3 --iteration 025 --force

# Skip the run, just score existing results:
python -m auto_improve.loop --iteration 025 --skip-run

# Skip scoring:
python -m auto_improve.loop --iteration 025 --skip-score
```

### Monitoring

```bash
# Live dashboard (shows latest iteration):
python -m auto_improve.dashboard

# Inspect a specific task:
python -m auto_improve.dashboard --task django__django-12325

# Compare scores across iterations:
python -m auto_improve.check_scores iteration-021 iteration-022 iteration-023

# Auto-detect all active iterations:
python -m auto_improve.check_scores
```

### Scoring

The loop starts a watch scorer automatically. If you need to run scoring manually:

```bash
# Score via the unified watcher (watches all iterations):
python -m evals.watch_scoring_all --base-dir results/auto-improve

# Score a specific iteration's predictions:
python -m evals.watch_scoring results/auto-improve/iteration-021
```

Scoring uses Modal by default. Some repos (scikit-learn, some sympy) fail on Modal's sandbox build — these get marked as `SKIP` after 5 failed attempts.

To check scoring status:
```bash
cat results/auto-improve/iteration-021/_watch_scores.json | python -m json.tool
```

### Adding workers mid-run

```bash
python -m auto_improve.add_workers --iteration 025 --keys-file auto_improve/api_keys.json --start-id 3
```

### Cleaning up

```bash
# Remove old iteration workspaces (keeps results):
rm -rf evals/workspaces-auto-improve/iteration-NNN/

# Clean old scoring logs:
rm -rf logs/run_evaluation/hermes-watch-*

# Check disk usage:
du -sh evals/workspaces-auto-improve/*/
```

---

## The Process

Do these steps in order. Every time.

### Step 1: Run

Configure `base_config.json` with the desired model/robustness settings. Set tasks in `tasks.json` (default: all 500 SWE-bench Verified tasks). Launch:

```bash
python -m auto_improve.loop --workers 3 --iteration NNN
```

**Gate condition at 20 scored tasks:**
- Below 80% → kill the run, analyze failures, start improvement round
- 80%+ → continue (scale up if rate limits allow)

### Step 2: Review scores

```bash
python -m auto_improve.check_scores iteration-NNN
```

### Step 3: Analyze failures

For each failed task:
```bash
python -m auto_improve.dashboard --task <task_id>
```

This shows: phase trail, critique flags, gate decisions, patch summary, and score.

**Important:** Don't trust the pipeline's "all tests pass" claim. The executor runs tests in a warm environment. SWE-bench scores in a cold Docker/Modal container. Check the actual scoring output:
```bash
find logs/run_evaluation -path "*<task_id>*" -name "report.json" | sort | tail -1
find logs/run_evaluation -path "*<task_id>*" -name "test_output.txt" | sort | tail -1
```

Ask: **which phase went wrong?** Plan? Critique? Gate? Execute? Review? Environment?

### Step 4: Categorize

Group failures by structural cause:

| Pattern | Meaning |
|---------|---------|
| `narrow_fix` | Fixed symptom, not disease |
| `incomplete_scope` | Fix covers reported case but misses adjacent edge cases |
| `wrong_api` | Correct approach, wrong implementation detail |
| `test_contamination` | Executor modified test files despite constraint |
| `env_mismatch` | Tested against installed package instead of patched source |
| `insufficient_verification` | Cherry-picked tests, missed regressions in full suite |
| `critique_flagged_not_blocked` | Critique found the issue but gate let it through |
| `infra_error` | Worker/environment/scoring failure |

### Step 5: Implement improvements

Run a megaplan targeting the failure patterns. Constraints:
- Every change must help ANY coding task, not just these specific failures
- Prefer adding a sentence to a prompt over building a formal system
- Simple instructions change model behavior; labels and schemas usually don't

### Step 6: Start next iteration

Go back to Step 1 with the improvements active.

---

## Architecture

### Pipeline (megaplan)

```
prep → plan → critique → gate → [revise → critique → gate]* → finalize → execute → review
```

- **Critique**: Runs as parallel sub-agents (one per check) via `parallel_critique.py`. Each check gets its own template file (`critique_check_{id}.json`). Max 2 concurrent checks per worker to limit rate limiting.
- **Gate**: Enforces flag resolution. Flags can only be resolved via structured `flag_resolutions` (dispute with evidence, or accept_tradeoff). Max 3 resolutions per gate call. Bulk dismissal is blocked.
- **Execute**: Includes bug reproduction step — model writes a throwaway script verifying the reported bug is fixed, then deletes it.
- **Review**: Independent code review of the executed changes.

### Scoring

Predictions are scored via Modal (remote Docker containers) or local Docker. The scorer:
1. Watches for new prediction JSONL files in `_swebench_predictions/`
2. Submits each to `swebench.harness.run_evaluation` with `--modal true`
3. Parses `report.json` for pass/fail
4. Writes results to `_watch_scores.json`
5. Retries up to 5 times with exponential backoff (30s, 60s, 120s...)

Shared scoring utilities in `evals/watch_scoring.py`:
- `load_scores_data(path)` — read scores JSON
- `classify_task(entry)` — returns "pass", "fail", "pending", or "exhausted"
- `find_retryable_tasks(scores_data, predictions)` — identify tasks to retry

### Provider routing

Model resolution lives in `megaplan/parallel_critique.py` (`_resolve_model`) and `megaplan/hermes_worker.py`. Both use the same pattern:
1. Parse `provider:model` prefix
2. Load API key from env vars, falling back to `~/.hermes/.env`
3. Set `base_url` and `api_key` on the AIAgent
4. MiniMax has automatic OpenRouter fallback on API errors

## Rules

1. **No task-specific fixes.** If it only helps one task, don't do it.
2. **Simpler is better.** Prefer removing complexity over adding it.
3. **Record everything.** Every iteration should be traceable.
4. **Don't change prompts mid-iteration.** Run → score → analyze → THEN change.
5. **Don't optimize for the eval.** Would this help any coding task? If not, skip it.

## Files

```
auto_improve/
├── README.md                 ← you are here
├── tasks.json                ← current task list (500 SWE-bench Verified)
├── api_keys.json             ← Z.AI API keys (gitignored)
├── base_config.json          ← model + robustness config
├── loop.py                   ← orchestrator: run → score → scaffold docs
├── run_experiment.py         ← launches parallel workers, manages iterations
├── add_workers.py            ← add workers mid-run (multi-key support)
├── dashboard.py              ← live status + per-task inspector
├── check_scores.py           ← compare scores across iterations
├── score_experiment.py       ← post-run batch scoring
├── history.py                ← cross-iteration task performance
└── FAILURE_CATALOG.md        ← documented failure patterns from past iterations

evals/
├── parallel.py               ← worker orchestration, API key cycling
├── run_evals.py              ← single-worker eval runner (phase execution)
├── watch_scoring.py          ← scoring engine + shared utilities
├── watch_scoring_all.py      ← multi-iteration scoring watcher
├── config.py                 ← EvalConfig dataclass
├── manifest.py               ← task manifest (claim/done/error tracking)
└── benchmarks/swe_bench.py   ← SWE-bench task loading + workspace setup

results/auto-improve/iteration-NNN/
├── _run_config.json          ← materialized config for this run
├── _task_manifest.json       ← task status (pending/claimed/done/error)
├── _watch_scores.json        ← scoring results (pass/fail/pending/skip)
├── _swebench_predictions/    ← one JSONL per completed task
├── _worker_logs/             ← per-worker stdout/stderr logs
└── worker-N/<task_id>/       ← per-task phases, traces, audit trail
```
