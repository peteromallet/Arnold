# Sprint 5 — Decompose god-modules (`directed//medium`)

Shared context: read `docs/structural_audit_2026-05.md` (first-sweep lenses 3/4/5, j6), `handoff-m4a.md`, and `handoff-m4b.md`. Sprint 5 of 10. This is a **behavior-preserving refactor** behind the differential harness + snapshots + consistency gates landed in earlier sprints — those are the acceptance net.

## Outcome
The god-modules are decomposed by concern into navigable modules with **zero semantic behavior change**, verified by the differential harness, snapshot assertions, and the current fast-suite command.

## Scope (IN)
1. **Split `porting/emitter.py`** (3,719 LOC) into focused modules following the existing plans in `docs/templates/decorator_template_emitter_completion.md` and `docs/templates/readable_ready_template_cleanup_plan.md`: e.g. `subgraph_emitter.py`, `naming.py` (merge with the post-sprint-4a version), all submodules use `vibecomfy/paths.py` from M4a for `REPO_ROOT`/`READY_ROOT` (no local recomputation), `wrapper_registry.py` (extracting the current wrapper-class heuristic with identical behavior; any generated `class_type → (module, symbol)` map starts as a parallel, gated path and cannot change committed output in this sprint), and a slim orchestrator that owns `_emit_build_function`.
2. **Decompose `runtime/session.py`** (1,379 LOC): de-dup the 6 functions/classes shared verbatim with `config.py` (import them); extract server-spawn into `server_process.py` and watchdog lifecycle into `watchdog_runtime.py`; **unify the two ~80%-identical `_run_untracked` implementations** (`EmbeddedSession` ~280-370, `ServerSession` ~472-556) into one private `vibecomfy/runtime/_execution.py::_execute_prompt()`. The signature should capture only the intersection of the current embedded/server needs; M6a owns finalizing `backend`, `strict_drift`, queue strategy, and the public `VibeSession.run(...)` protocol.
3. **Split `commands/port.py`** (1,347) and `commands/nodes.py` (919) into `_cmd_*` submodules under `commands/port/` and `commands/nodes/`, with `register()` delegating.
4. **Standardize existing CLI JSON output without public CLI breakage**: route existing `--json` paths through `commands/_output.py:emit()` where doing so is semantically equivalent after parsing. Do not add new `--json` flags to existing commands in this behavior-preserving sprint; new flags and broader JSON UX belong in M7 or follow-up release work.
5. **Create the decomposition handoff artifact** at `docs/megaplan_chains/excellence_epic/handoff-m5.md`, recording moved modules, public import compatibility, semantic-equivalence evidence, CLI smoke commands, and any places intentionally deferred to sprint 6a/6b.

## Locked decisions
- Behavior-preserving only — the differential harness, snapshot assertions, and current fast-suite command are the gate.
- Target <=800 LOC per decomposed module. Any touched module still above ~1,200 LOC requires explicit justification in `handoff-m5.md`.
- Extract the emitter's bytecode wrapper-class heuristics into a module with identical behavior; a generated registry can be added only as a gated, non-default path because this sprint is behavior-preserving.
- User-facing CLI syntax is not hard-renamed in this sprint. If naming cleanup is needed, add aliases/deprecation notes only, with existing documented invocations still working.
- CLI JSON standardization must be semantically equivalent for existing `--json` outputs (same parsed keys, values, and types) unless the changed command is explicitly new. `emit()`/`jsonable()` must reject non-JSON-serializable objects loudly instead of letting arbitrary objects crash later or stringify unpredictably.

## Prep deliverables
- Exact emitter submodule boundaries — the planner deliberates this, but must keep the public import surface stable and preserve semantic output.

## Constraints
- ZERO semantic behavior change: snapshot assertions and differential harness pass identically; any intentional snapshot delta is a bug unless justified in `handoff-m5.md` with evidence from prior correctness sprints.
- Narrow structural fixes are allowed when they eliminate shared mutable state, make implicit ordering explicit, or remove layering violations discovered during decomposition, provided the differential harness and snapshot assertions still prove semantic equivalence. Record before/after evidence in `handoff-m5.md`.
- Do not encode runtime-registry or RunPod assumptions into `_execution.py`; M6a owns the runtime registry and M6b owns RunPod semantics.
- Create `tests/test_api_surface.py` as the public import-surface contract test, then preserve it through decomposition.
- Existing documented CLI invocations remain accepted and produce the same output shape.
- Sprint-4a clone checks and sprint-4b classification-site checks must be rerun after decomposition to prove consolidated helpers were not re-forked and priority sites still route through `classify_node()`.

## Done criteria
- `emitter.py`, `session.py`, `port.py`, `nodes.py` decomposed; target module size is met or exceptions above ~1,200 LOC are justified in `handoff-m5.md`.
- Fast suite command, differential harness, and snapshot assertions green and unchanged. Fast suite command means the current `ci.yml` command unless earlier sprints replace it and record the replacement in their handoff.
- Public import surface test exists and passes for the package exports expected by users and recipes.
- Existing CLI `--json` output paths touched by the split flow through `emit()` and remain semantically equivalent with existing golden tests.
- Sprint-4a clone checks and sprint-4b classification checks rerun clean after the split.
- `handoff-m5.md` captures moved modules, compatibility checks, and semantic-equivalence evidence.

## Touchpoints
`vibecomfy/porting/emitter.py` (+ new submodules), `runtime/session.py` + `config.py` + new `server_process.py`/`watchdog_runtime.py`, `commands/port.py` + `nodes.py` (+ submodules), `commands/_output.py` + command modules.

## Anti-scope
Do NOT change runtime behavior or add the `VibeSession` factory (sprint 6a). Do NOT change emitter OUTPUT (sprint 1 owns correctness; here output must be identical).
