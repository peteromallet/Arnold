## Runtime & Execution Path Audit

---

### HIGH

1. **Three overlapping eval modules with zero integration** — `eval.py` (437 lines, used by CLI via `commands/runtime.py:12`), `eval_plan.py` (187 lines, new richer design), `eval_prompt.py` (145 lines, wraps `eval_plan`). The CLI path (`_cmd_runtime_eval_node` at `commands/runtime.py:53`) uses **only** `eval.compile_eval_subgraph` + its own inline `_queue_embedded`/`_queue_server` helpers. `eval_plan.py` and `eval_prompt.py` are completely unreachable from any production code path; only `test_agentic_affordances.py` imports them. Two competing output-type detection systems: `eval._detect_output_type` (eval.py:144) vs `eval_plan._classify_outputs` → `preview_plan_for_type` (eval_plan.py:129). No shared logic.

2. **Broken import in test suite** — `test_agentic_affordances.py:25`: `from vibecomfy.runtime.eval import plan_eval_node` — but `plan_eval_node` lives in `eval_plan.py`, not `eval.py`. This is a guaranteed `ImportError`. It appears no CI is actually running this test.

### MEDIUM

3. **`queue_eval_subgraph` is dead code raising `NotImplementedError`** — `eval.py:103-136`. Full docstring, parameter validation, but the body unconditionally raises `NotImplementedError`. The docstring on line 8 claims "Queueing is separated into `queue_eval_subgraph`" as an architectural decision, yet the CLI bypasses it entirely with its own inline helpers at `commands/runtime.py:140-155`.

4. **Queue/wait/outputs logic triplicated** — the sequence `queue_prompt → _wait_for_server_history → _outputs_from_server_history` appears identically in `run.py:84-92`, `session.py:505-530` (ServerSession._run_untracked), and `eval_prompt.py:55-58`. `run.py` and `ServerSession._run_untracked` are ~80% identical functions duplicating each other rather than one delegating to the other.

5. **`session.py` is a god-class at 1379 lines** — contains `EmbeddedSession`, `ServerSession`, `SessionConfig`, `RunResult`, config partitioning, server spawning (`_spawn_comfy_server`), prompt preparation, schema validation, history polling, output collection, metadata generation, model fingerprinting, watchdog lifecycle, session discovery (`active_session_metadata`, `find_active_session`), and memory-policy flushing. Session lifecycle, server management, and prompt orchestration belong in separate modules.

6. **`_on_schema_unavailable` duplicated verbatim** — identical 6-line method body in `EmbeddedSession` (session.py:205-210) and `ServerSession` (session.py:428-433). No shared base class or extracted function.

### LOW

7. **Inconsistent `ensure_packs` parameter** — `EmbeddedSession.run()` (session.py:220) and `run.run_embedded()` (run.py:141) both accept `ensure_packs`, but `run.run()` (run.py:38) and `ServerSession.run()` (session.py:446) silently lack it. The asymmetry is undocumented and would surprise anyone refactoring across paths.

8. **`watchdog.py:write_report` types `run_dir: Any`** (line 627) yet immediately coerces to `Path` on line 635 — signals the author didn't know what type callers pass; the only real caller (`_finalize_watchdog` at session.py:1353) passes a `Path`. The `Any` is a type-safety regression.

---

**Worst thing:** The three eval modules are a half-executed migration. `eval.py` is the live codepath; `eval_plan.py` + `eval_prompt.py` are a newer, richer design with no callers. The test that tries to bridge them (`test_agentic_affordances.py:25`) has a broken import that would fail on first execution. Any engineer touching eval-node will need to reverse-engineer which of three modules actually matters, and the broken test means no one will notice when they guess wrong.