# Things to Refactor

Structural issues identified across the execution, scoring, and monitoring pipeline. Not bugs per se — more like places where the structure invites future bugs or confuses new contributors.

Ordered roughly by risk of causing problems.

---

## HIGH — Likely to bite on next iteration

### 1. Phase ordering hardcoded in 3 places

Adding or removing a phase requires edits in:
- `megaplan/_core/workflow.py` — the canonical state machine (WORKFLOW dict)
- `evals/run_evals.py:270-289` — `_phase_transitions()` duplicates transitions for eval routing
- `megaplan/types.py:257-269` — `DEFAULT_AGENT_ROUTING` maps phases to agents

**Fix:** The latter two should derive from `workflow.py`, not redefine transitions.

### 2. Two scoring codepaths that do the same thing differently

- `auto_improve/score.py` — single-threaded, used by cron
- `evals/watch_scoring.py` — ThreadPoolExecutor (2 threads), older code

They have different attempt-counting defaults (0 vs 1 for missing entries), different concurrency models, and different re-read logic. The threaded scorer has a lost-write race condition on `_watch_scores.json`.

**Fix:** Pick one, delete the other. Add file locking to the scores JSON (manifest already uses `fcntl.flock`).

### 3. Model resolution duplicated in hermes_worker and parallel_critique

Both call `key_pool.resolve_model()` independently. Both implement MiniMax→OpenRouter fallback with identical logic. Both report 429s to the key pool with the same cooldown values.

- `megaplan/hermes_worker.py:290` + fallback at ~line 320
- `megaplan/parallel_critique.py:56` + fallback at lines 132-146

**Fix:** Extract a `run_with_fallback(model, make_agent, run_fn)` helper. Call from both.

### 4. Escalation policy scattered across 4 call sites

When does a task escalate vs retry vs fail? Depends where you look:
- `run_evals.py:321-325` — gate says ESCALATE
- `run_evals.py:346-353` — phase max-retries exhausted
- `run_evals.py:791-792` — execute stuck >12 attempts
- `parallel_critique.py:150-163` — MiniMax+OpenRouter both fail → CliError (not escalate)

No single escalation decision tree.

**Fix:** Define escalation policy in one place. Each call site should ask the policy, not implement its own.

### 5. Manifest/scores/predictions: three files, one implicit state machine

A task's real state is the combination of its manifest status, whether a prediction file exists on disk, and its entry in `_watch_scores.json`. The valid transitions are spread across `find_scorable`, `find_retryable_tasks`, `check_limbo`, and the cron.

Notable gap: "done in manifest but no prediction file" is inferred by checking file existence, not explicitly modeled. This state caused the astropy-8707 stuck-scorer issue.

**Fix:** At minimum, document the state machine in one place. Ideally, add a `task_state()` function that returns the canonical state given all three sources.

### 6. Error categorisation drives retry policy but is fragile

`_categorize_scoring_error()` in `watch_scoring.py` is a chain of string-contains checks. Priority order matters — we already hit a bug where "timeout" matched before "modal_sandbox" because Modal errors contain "RetryError" in the traceback. Categories are plain strings, not an enum.

**Fix:** Use an enum. Check more-specific patterns before less-specific ones. Add a test with example error messages.

---

## MEDIUM — Won't break today but will confuse people

### 7. PlanState is an untyped dict

Handlers mutate `state["meta"]`, `state["iteration"]`, `state["plan_versions"]`, `state["sessions"]` directly. No TypedDict or dataclass defines which fields exist or who owns them. Easy to typo a key name or forget to update a field.

- `handlers.py:740` — `_append_to_meta(state, "significant_counts", ...)`
- `handlers.py:805-812` — directly mutates `state["iteration"]`, `state["plan_versions"]`, `state["meta"]`
- `handlers.py:858` — `_record_gate_debt_entries()` modifies root-level files, not state

**Fix:** Define `PlanState` as a TypedDict or dataclass with clear field ownership.

### 8. Gate outcome entangles decision and mutation

`_apply_gate_outcome()` in `handlers.py:476-555` checks conditions, mutates state, AND returns routing info, all in one function. The caller must then call `_store_last_gate()` afterward in the right order — there's a comment warning about this.

**Fix:** Split into `_compute_gate_outcome()` (pure, returns decision) and `_apply_gate_outcome()` (mutates state).

### 9. Sequential vs parallel critique have different error semantics

- Parallel critique: MiniMax→OpenRouter fallback, fresh UUID sessions per check
- Sequential critique: no fallback, continues existing session

Same operation, different reliability characteristics depending on which path runs.

**Fix:** Unify error/fallback handling. Both paths should use the same resilience policy.

### 10. Five levels of model config precedence

To determine which model runs a phase:
1. `--phase-model` flag
2. `--hermes` flag
3. `--agent` flag
4. Config file (`~/.megaplan/config.json`)
5. `DEFAULT_AGENT_ROUTING` hardcoded dict

Plus a silent fallback to first available agent stored as `args._agent_fallback`. Undocumented which wins. No validation that config keys match known phases.

**Fix:** Document precedence. Validate config at load time. Replace `args._agent_fallback` with explicit resolution.

### 11. Worker output parsing has recovery logic only for Hermes

`hermes_worker.parse_agent_output()` re-prompts if the template response is empty and the agent used tools. Claude/Codex workers just fail. Easy to add a new agent and miss this recovery path.

**Fix:** Extract `validate_worker_output(step, payload)` as single validation function; call for all agents.

### 12. Iteration hardcoded in multiple files

`ITERATION = "021"` appears in `cron.py`, `dashboard_web.py`, and various log paths. Starting iteration 022 means editing multiple files and hoping you got them all.

**Fix:** Single source of truth — env var, CLI arg, or a shared config file.

---

## LOW — Nice to fix but not urgent

### 13. Process management via pgrep pattern matching

The cron finds processes by `pgrep -f "run_evals"` etc. Fragile — a renamed script, extra argument, or unrelated process matching the pattern could cause false positives/negatives.

**Fix:** PID files written at startup, checked by cron.

### 14. Dashboard data.json does full filesystem walk per request

`_gather_data()` globs through `worker-*/task/run/phases/*.json` for every task on every request. This is why the dashboard is slow to load.

**Fix:** Cache the result with a short TTL (e.g. 30s), or compute incrementally from last-known state.

### 15. Key pool reload is TTL-based with no invalidation trigger

`key_pool.py` re-reads env/files every 60s. If you add a new API key, you wait up to 60s. File reads happen outside the lock, so a partial write could be seen.

**Fix:** Watch file mtime for invalidation. Move file I/O inside the critical section.

### 16. Verification task injection is regex-based

`_ensure_verification_task()` in `handlers.py:891-916` detects existing test tasks by regex on the description. Fragile if descriptions are reworded.

**Fix:** Add an explicit `task_type` field (e.g. `TaskType.VERIFICATION`) to the schema.

---

## Already fixed during this session

- **Error categorisation priority**: `modal_sandbox` now checked before `timeout` in `_categorize_scoring_error()`
- **Scorer stuck detection**: `last_score` now only counts successful scores (resolved != None), not error attempts
- **Cron state file**: Added `_cron_state.json` for deltas, throughput, stall detection, requeue loop detection
- **Atomic manifest writes**: `_atomic_json_write()` via tempfile + `os.replace()`
- **Git push error checking**: `push_to_github()` now checks return codes
- **Unreviewed infra failures**: Cron flags scoring-exhausted tasks with patches needing manual review
