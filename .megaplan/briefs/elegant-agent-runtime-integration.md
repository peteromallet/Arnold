# Elegant Agent Runtime Integration

## Outcome

Make internal agent dispatch and fanout consumption elegant and coherent. A Megaplan internal caller should have one obvious way to dispatch one agent request, one obvious way to fan out worker-backed agent requests, and a clearly separated public/vendorable runtime contract. The finished work should reduce the current split-brain surface without regressing the completed vendorable-agent-runtime-package sprint.

## Context

The prior sprint `vendorable-agent-runtime-package` completed and review passed. It introduced:

- `megaplan.agent_runtime` with `AgentRequest`, `AgentResult`, `FanoutUnit`, `FanoutResult`, `scatter_agent_units`, `AgentDispatcher`, and related contracts.
- `megaplan._core.worker_fanout` with `WorkerUnit` and `scatter_worker_units`.
- `megaplan.agent_runtime.process_fanout` and `megaplan._core.process_fanout` aliases over generic process fanout.
- Parallel critique migration to `WorkerUnit` / `scatter_worker_units`.
- Gate/execution blocker fixes so quality decisions are durable.

DeepSeek fanout exploration of the current surface area produced six independent reports under `/tmp/megaplan-deepseek-surface-results/`. Treat the following synthesis as settled input:

1. The current implementation is internally usable, but not elegant: single-agent calls use `run_step_with_worker`, critique uses `scatter_worker_units`, prep research uses direct `scatter_gather_processes`, review uses `scatter_gather_checks` and raw Hermes, and the runtime contracts are not yet the internal currency everywhere.
2. Remaining fanout migration targets are:
   - `megaplan/orchestration/prep_research.py`: direct `scatter_gather_processes` with ad hoc dict units.
   - `megaplan/review/parallel.py`: `scatter_gather_checks` and raw Hermes-specific review fanout.
3. Direct `run_step_with_worker` remains valid for single-agent dispatch in:
   - `megaplan/loop/engine.py`
   - `megaplan/handlers/shared.py`
   - `megaplan/execute/batch.py`
   - sequential tiebreaker orchestration
   - `_core/worker_fanout.py` as the adapter implementation.
4. The vendorable package still leaks Megaplan internals:
   - `AgentResult.from_worker_result()` / `to_worker_result()` couple `agent_runtime` to `megaplan.workers`.
   - `AgentSpec` / `AgentMode` are imported from `megaplan.types`.
   - `agent_runtime.process_fanout` re-exports from `_core.hermes_fanout`.
   Decide whether to fully decouple now or explicitly split public core vs Megaplan adapter.
5. Worker fanout currently collapses rich `AgentResult`/`WorkerResult` provenance into payload + cost/tokens. It risks dropping `session_id`, `shannon_plan`, `rendered_prompt`, `model_actual`, `trace_output`, and output path provenance.
6. Missing guardrails:
   - no characterization/lint test forbids new raw concurrency or bespoke fanout in orchestration paths.
   - no import-surface test covers `megaplan.agent_runtime.process_fanout.__all__`.
   - no fresh install/wheel smoke test for external importability.
7. Packaging/docs gaps:
   - no external agent runtime integration doc.
   - no `py.typed`.
   - cloud template defaults may need `[db]` if cloud DB mode is intended.

## Locked Decisions

- Keep `run_step_with_worker` as the internal single-agent compatibility primitive. Do not force every single-agent caller through fanout.
- Make `AgentRequest` / `AgentResult` the conceptual currency at the adapter boundary.
- Make fanout callers phase-specific only in prompt building, parse hooks, reduce hooks, side-task definitions, and error sentinels. They should not choose raw Hermes/thread/process mechanisms directly unless implementing the runtime layer.
- Prefer migration over a large rewrite. Preserve existing behavior and pass current tests.
- Review-specific semantics must not be lost: prior flag filtering, criteria verdict side task, verified/disputed flag merge behavior, payload cleanup, cost/token aggregation, and deterministic output artifacts.
- Prep research semantics must not be lost: ordered area results, `read_only=True`, timeout/error sentinels, cost/token aggregation, and normalized finding payloads.
- Preserve the critique == review invariant unless a test or existing config explicitly documents a different path.
- Do not hide legitimate quality gates. If scope/audit blockers appear, make them visible and resolvable through the quality ledger rather than bypassing them.

## Scope In

1. Add or refine the internal dispatch/fanout abstraction so internal callers can use a simple, coherent interface:
   - single agent dispatch remains `run_step_with_worker` or a thin `AgentDispatcher` wrapper around it.
   - worker fanout should preserve richer provenance, preferably by carrying `AgentResult` objects or an explicit per-unit result structure instead of only payload tuples.
2. Migrate prep research fanout to the sanctioned worker fanout path or add a clearly documented adapter if a process-only path is retained.
3. Migrate review parallel fanout away from raw Hermes / `scatter_gather_checks` to the worker fanout path, including any needed side-task support.
4. Decide and implement the clean split between:
   - vendorable runtime core (`megaplan.agent_runtime`)
   - Megaplan adapter layer (`megaplan._core.worker_fanout`, workers compatibility).
5. Add guardrail tests that prevent future bespoke fanout/concurrency in orchestration code.
6. Add external-facing docs for internal consumers and eventual vendors:
   - how to dispatch one request
   - how to fan out worker-backed requests
   - when to use `agent_runtime.process_fanout`
   - what is intentionally internal.
7. Add package-readiness improvements if small and clear (`py.typed`, process-fanout import-surface test, fresh import smoke if practical).

## Scope Out

- Do not redesign the full worker stack or replace `run_step_with_worker`.
- Do not rewrite all phase handlers.
- Do not remove Hermes vendoring.
- Do not delete legacy functions unless all production call sites and tests are migrated safely.
- Do not introduce a new third-party concurrency library.
- Do not change model routing policy or profile semantics except where needed for tests.
- Do not create a separate PyPI package in this sprint; make the code packageable and document the remaining extraction boundary.

## Touchpoints

- `megaplan/agent_runtime/`
- `megaplan/_core/worker_fanout.py`
- `megaplan/_core/process_fanout.py`
- `megaplan/_core/hermes_fanout.py`
- `megaplan/orchestration/parallel_critique.py`
- `megaplan/orchestration/prep_research.py`
- `megaplan/review/parallel.py`
- `megaplan/workers/_impl.py`
- `megaplan/workers/hermes.py`
- `megaplan/prompts/tiebreaker_orchestrator.py`
- `megaplan/orchestration/tiebreaker.py`
- `tests/test_worker_fanout.py`
- `tests/test_agent_runtime_contracts.py`
- `tests/test_agent_runtime_fanout.py`
- `tests/test_prep_research.py`
- `tests/test_review.py`
- `tests/test_hermes_fanout.py`
- `tests/characterization/test_import_surface.py`
- new docs under `docs/` if useful.

## Done Criteria

Must:

- Internal fanout architecture is explainable in one short doc section and reflected in code.
- Remaining production fanout call sites are either migrated to the common worker/runtime path or explicitly classified as runtime implementation internals with tests enforcing that boundary.
- Review and prep research pass their focused tests after any migration.
- Worker fanout preserves or intentionally exposes enough per-unit provenance for `session_id`, `shannon_plan`, `model_actual`, `rendered_prompt`, `trace_output`, output path, tokens, and cost.
- `megaplan.agent_runtime` public import surface remains exact and characterized.
- Add guardrail tests for prohibited bespoke fanout/concurrency imports in orchestration code, with explicit allowlists.
- Existing focused suite from the prior sprint still passes, plus any new tests for this sprint.

Should:

- Add `docs/agent-runtime-integration.md` or equivalent.
- Add `megaplan/py.typed` if packaging includes it without extra build changes.
- Add `megaplan.agent_runtime.process_fanout` import-surface characterization.
- Add at least one fresh import smoke test if it is cheap and stable.

Info:

- The prior run ended with 425 focused tests passing and the plan state `done`.
- Worktree is intentionally dirty with the prior sprint's completed changes. Compose with them; do not revert them.

## Anti-Scope

- Do not collapse every single-agent call into fanout.
- Do not let review migration drop criteria verdicts or prior-flag behavior.
- Do not let prep migration drop timeout sentinels or normalized findings.
- Do not make the external runtime more confusing by promoting every internal helper to public API.
- Do not solve packaging by hiding imports with broad try/except blocks.

