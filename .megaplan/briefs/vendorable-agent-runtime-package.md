# Vendorable Agent Runtime Package — First Extraction Sprint

## Outcome
Create the first clean, vendorable agent-runtime package boundary inside this repo: a stable public contract for single-agent invocation across Codex, Claude/Shannon, and Hermes, plus a read-only fan-out contract that can dispatch mixed agent types and aggregate ordered results, costs, tokens, and failures.

This sprint should not try to finish the whole external product. It should make the extraction real enough that another repo could depend on the contracts without importing megaplan plan state, handlers, prompts, profiles, tickets, cloud, or pipeline internals.

## Context
The current repo already has most of the mechanics, but they are spread across megaplan-specific layers:

- `megaplan/types.py` owns `AgentSpec` / `AgentMode` parsing.
- `megaplan/workers/_impl.py` owns dispatch through Codex, Claude/Shannon, and Hermes.
- `megaplan/workers/shannon.py` owns the Shannon-backed Claude adapter and vendored Shannon path.
- `megaplan/workers/hermes.py` owns the Hermes/AIAgent adapter and vendored Hermes runtime import.
- `megaplan/_core/worker_fanout.py` owns `WorkerUnit` and worker fan-out through `run_step_with_worker`.
- `megaplan/_core/hermes_fanout.py` is misnamed: it now contains generic scatter/gather and process fan-out primitives, not Hermes-only logic.
- `megaplan/_pipeline/*` has cleaner `Step` / `StepContext` / `StepResult` / `ParallelStage` abstractions, but lacks production worker runtime semantics.
- `megaplan/bakeoff/*` has reusable worktree and merge ideas, but the bakeoff product lifecycle is not this sprint's target.

DeepSeek edge-fan results are stored at:
`.megaplan/research/vendorable-agent-runtime-edges/results/`

## Locked Decisions
1. **Do not invent `run_oneshot` as a separate keystone.** The existing `run_step_with_worker(read_only=True, output_path=...)` path already proved the one-shot dispatch shape. Generalize that boundary instead of adding another invocation contract.
2. **Split concerns.** Agent runtime, worker adapters, read fan-out, write-fanout policy, and pipeline orchestration are different layers. This sprint extracts contracts for the first three only.
3. **Read fan-out first.** Mixed-agent read-only fan-out is the immediate packageable primitive. Write fan-out is harder because merge semantics, semantic review, rollback, and worktree mutation are policy-heavy.
4. **The runtime package must import nothing from megaplan-specific plan state.** Megaplan should adapt into the package through narrow interfaces.
5. **Codex vendor for the run.** Use a Codex-backed premium profile for planning/critique/review because this is API extraction and structural reasoning work.

## Scope
IN:

1. Define a package-boundary module or internal package namespace for the future vendorable runtime. It may live under `megaplan/agent_runtime/` or another clearly named internal namespace for now.
2. Extract or mirror pure contract types:
   - `AgentSpec` / parser / formatter
   - `AgentRef` or equivalent public model identifier
   - `AgentRequest`
   - `AgentResult`
   - `WorkerResult` compatibility adapter
   - `FanoutUnit`
   - `FanoutResult`
   - cost/token summary with provenance
3. Introduce adapter protocols so the package does not depend on `PlanState`, `argparse.Namespace`, `.megaplan/` layout, prompts, schemas, observability, or config:
   - `PromptProvider`
   - `SessionStore`
   - `EventEmitter`
   - `LivenessTouch`
   - `KeySource`
   - `CommandRunner` or `ProcessRunner`
4. Rename or alias the generic fan-out core away from `hermes_fanout` terminology if feasible, or at least add the new package-facing name and keep old imports as internal compatibility.
5. Make `scatter_gather_processes` and read-only `scatter_worker_units` consumable through injected dispatch instead of importing `megaplan.workers.run_step_with_worker` directly.
6. Add contract tests using fake adapters:
   - mixed-agent fan-out preserves input order
   - per-unit model/spec variation works
   - read-only flag is forwarded and attested
   - timeout and hard-kill semantics are deterministic
   - tolerant `on_unit_error` produces ordered sentinels
   - costs/tokens aggregate with provenance
   - the old megaplan worker fan-out API still works through an adapter
7. Fix stale user-facing contradictions discovered during edge review:
   - remove or update `pip install '.[agent]'` guidance now that Hermes deps are core/no-op
   - clarify `claude` is Shannon-backed in this runtime
   - document that worker fan-out and pipeline fan-out are related but not the same contract

## Anti-Scope
Do NOT do these in this sprint:

- Do not extract or rewrite `megaplan/execute/batch.py`.
- Do not build generic write fan-out or `best_of_n` execute.
- Do not move bakeoff's full lifecycle into the package.
- Do not move cloud, resident, tickets, audits, editorial, skills distribution, or chain/epic logic.
- Do not publish a separate PyPI package yet.
- Do not rewrite the vendored Hermes runtime.
- Do not rewrite Shannon's tmux strategy, except where a narrow interface is needed for the contract.
- Do not require pipeline runtime migration. Additive bridge only.

## Open Questions For Prep
1. Should the first package namespace be `megaplan.agent_runtime`, `megaplan_agent_runtime`, or an internal `_agent_runtime` staging namespace?
2. Should `AgentResult` wrap `WorkerResult`, or should `WorkerResult` become a compatibility projection of `AgentResult`?
3. What is the minimum `SessionStore` interface that supports Codex session deltas, Shannon session IDs, and Hermes `SessionDB` without exposing `PlanState`?
4. How strict can read-only attestation be for Shannon today, given it is CLI/tool-list based rather than OS-sandbox enforced?
5. Should generic scatter/gather live beside the agent runtime package, or as a separate `agent_fanout` layer that depends on the runtime contracts?

## Constraints
- Preserve existing megaplan behavior and tests.
- Do not revert unrelated dirty work in this repo.
- Maintain backward-compatible imports where existing tests require them.
- Do not let the new package-facing surface import from `megaplan.handlers`, `megaplan.prompts`, `megaplan.schemas`, `megaplan.store`, `megaplan.observability`, or `megaplan.cli`.
- Keep the public names boring and adopter-oriented: avoid `hermes_fanout`, `WorkerUnit`, and `run_step_with_worker` as the final external vocabulary unless preserved only as compatibility aliases.

## Done Criteria
1. A documented package-facing API exists for single-agent calls and read fan-out.
2. Megaplan can still call the old worker/fan-out paths successfully through adapters.
3. Contract tests cover fake single-agent invocation and mixed-agent fan-out.
4. Existing focused tests pass:
   - `tests/test_worker_fanout.py`
   - `tests/test_hermes_fanout.py`
   - `tests/test_workers_agent_mode.py`
   - relevant worker contract tests for Codex/Shannon/Hermes touched by the sprint
5. Docs or brief updates settle the known contradictions:
   - no stale `[agent]` extra guidance
   - `hermes_fanout` name no longer presented as Hermes-only
   - `run_oneshot` no longer described as the necessary missing contract
6. A short follow-up plan exists for write fan-out, operator CLI/doctor, and external package publishing.

## Touchpoints
- `megaplan/types.py`
- `megaplan/workers/_impl.py`
- `megaplan/workers/__init__.py`
- `megaplan/workers/hermes.py`
- `megaplan/workers/shannon.py`
- `megaplan/_core/worker_fanout.py`
- `megaplan/_core/hermes_fanout.py`
- `megaplan/runtime/process.py`
- `megaplan/runtime/key_pool.py`
- `tests/test_worker_fanout.py`
- `tests/test_hermes_fanout.py`
- worker adapter tests
- `docs/hermes-vendoring.md`
- `.megaplan/briefs/multi-agent-fanout-primitive.md`

## Run Recommendation
Use:

`premium/thorough/high @codex +prep`

Rationale: this is structural API extraction across several coupled systems. It needs premium planning and review, explicit prep, and high author-side depth. `apex` would bring Claude into authoring and ignore the requested Codex vendor; `premium --vendor codex` matches the request while keeping all premium reasoning on Codex.
