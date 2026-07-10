# Decision: native VibeComfy executor — what changes in Arnold vs. VibeComfy

## Context

We are going all-in on expressing the VibeComfy executor as native Python instead of as an Arnold/Megaplan graph pipeline. We can change code on **both** the Arnold side and the VibeComfy side. The goal is not just a one-off migration: Arnold should end up able to support many workflows that follow the same native-Python shape.

## What the DeepSeek survey found in Arnold

### Already exists (solid foundation)

- **Neutral pipeline types and executor** (`arnold/pipeline/types.py`, `arnold/pipeline/executor.py`). `Pipeline`, `Stage`, `Step`, `StepContext`, `StepResult`, `Port`, `PortRef`, and a walk-loop executor that operates on neutral types, not Megaplan types.
- **A 12-callback `ExecutorHooks` protocol** (`arnold/pipeline/hooks.py`) plus `NullExecutorHooks`. Used today by the bridge and usable by a native runtime.
- **`PipelineBuilder`** (`arnold/pipeline/builder.py`) for assembling neutral `Pipeline` objects.
- **`PipelineStepwiseDriver`** (`arnold/runtime/driver.py`) — a complete in-process driver that takes a `Pipeline`, tracks state/iteration, and exposes `advance()` / `checkpoint()` / `resume()`. It is **not wired into the CLI** today.
- **`driver` metadata field** on pipeline packages (`arnold/pipelines/_template/__init__.py`, `_authoring.py`). It is collected and stored, but **not used for runtime routing**.
- **Manifest-first discovery** (`arnold/pipeline/discovery/manifest.py`) that can extract metadata without importing modules.
- **Profile loading infrastructure** (`run_cli.py:_resolve_profile_for_run`) already handles `@pipeline:profile` syntax and TOML profiles.
- **Loop primitives**: `Stage.loop_condition`, `LoopNode`, `pattern_topology`, `resolve_edge` with decision/override routing. The neutral executor delegates loop halting to hooks, not to inline graph semantics.

### Missing (the gaps)

- **No native-function pipeline driver.** Every execution path today assumes a `Pipeline` graph of `Stage`/`ParallelStage` objects connected by `Edge`. There is no concept of a plain Python function/coroutine as a pipeline.
- **No decorator or function-to-stage lowering.** No `@pipeline`, `@phase`, or `step_from_function`. Authors must hand-build `Stage` dataclasses.
- **`driver` is metadata-only.** The CLI always routes `arnold <pipeline> run` through the Megaplan executor path. There is no `if driver == "native": ...` branch.
- **`_BRIDGED_PIPELINES` is a hard-coded allowlist** with only `demo_judges`. The bridge proves neutral execution works but is not general.
- **No runtime resolver that materializes typed-port bindings into `StepContext.inputs`.** The binding map exists at build time; the executor does not automatically populate inputs from it.
- **`PipelineStepwiseDriver` is graph-only.** It cannot execute arbitrary Python control flow (`while`, dynamic branches) without translating it into graph loops first.
- **No reusable neutral hooks implementation for state/artifact persistence.** `MegaplanExecutorHooks` is tied to Megaplan state files and CAS semantics.

## Decision

Build a **native-pipeline runtime inside Arnold** and implement the VibeComfy executor as the first consumer of that runtime.

### Arnold changes

Add a new `arnold.pipeline.native` subsystem that makes plain Python a first-class pipeline authoring model.

#### 1. Native pipeline abstraction

```python
# arnold/pipeline/native/types.py
@dataclass
class NativePhase:
    name: str
    fn: Callable[[PhaseContext], Any]
    produces: tuple[str, ...]
    consumes: tuple[str, ...]
    kind: Literal["produce", "decide"] = "produce"

@dataclass
class NativePipeline:
    name: str
    fn: Callable[..., Any]           # the native Python orchestration function
    phases: dict[str, NativePhase]   # metadata derived from decorators
    entry_inputs: tuple[str, ...]
```

The native function is a normal Python function/coroutine that receives a `PhaseContext` and yields at phase boundaries so the runtime can checkpoint:

```python
# vibecomfy/executor/pipeline.py
from arnold.pipeline.native import pipeline, phase, PhaseContext

@phase(name="classify", consumes=("query",), produces=("plan",))
def classify(ctx: PhaseContext) -> Plan:
    ...

@pipeline(name="vibecomfy-executor")
def run_executor(ctx: PhaseContext):
    plan = yield classify(ctx)
    if plan.research:
        summary = yield research(ctx, plan)
    ...
    return ExecutorResult(...)
```

#### 2. Native executor

`arnold.pipeline.native.executor` runs the native function:

- Catches `yield` to create a checkpoint.
- Serializes state to `plan_dir/state.json` after every checkpoint.
- Resumes by restoring state and re-entering the generator at the last checkpoint.
- Applies overrides before `@decision` phases.
- Writes artifacts via a reusable `StateStore` abstraction.
- Implements an `ExecutorHooks`-style protocol so observability, cost tracking, and policy checks plug in uniformly.

This is **not** a graph executor. It runs Python control flow directly.

#### 3. Driver registry and CLI dispatch

Make `driver` affect routing:

```python
# arnold/pipeline/native/registry.py
NATIVE_DRIVERS = {
    "native": NativeExecutor,
    "in_process": NativeExecutor,  # alias
}
```

In `arnold/pipelines/megaplan/cli/arnold.py`, branch module `run` on `pipeline_metadata(name).get("driver")`:

```python
if driver in NATIVE_DRIVERS:
    return NATIVE_DRIVERS[driver].run(module, ctx, plan_dir)
else:
    return _megaplan_main(["run", module, ...])
```

#### 4. Reusable native building blocks

Move generic concerns into Arnold so every native pipeline gets them:

- `arnold.pipeline.native.profiles` — load/merge TOML profiles, resolve stage specs.
- `arnold.pipeline.native.backends` — `AgentBackend` protocol + Arnold dispatch backend.
- `arnold.pipeline.native.state` — checkpoint serialization, resume cursor handling.
- `arnold.pipeline.native.introspection` — derive a neutral `Pipeline`/graph view from decorators for UI/tracing.

#### 5. Keep the graph executor

The existing neutral graph executor and `PipelineBuilder` stay for workflows that are naturally graph-shaped. Native and graph pipelines coexist. Over time, native can become the default authoring style.

### VibeComfy changes

#### 1. Implement the executor as a native pipeline

Create `vibecomfy/executor/`:

```text
vibecomfy/executor/
  __init__.py              # exports run_executor
  pipeline.py              # @pipeline + @phase definitions
  models.py                # Plan, ExecutorResult
  profiles.py              # bundled TOML loader
  backends/arnold.py       # ArnoldAgentBackend (optional, injected by Arnold runtime)
  integrations/
    edit.py                # headless handle_agent_edit wrapper
    hivemind.py            # corpus search
```

`pipeline.py` contains only VibeComfy-specific logic: prompts, classification heuristics, edit integration. It does **not** implement pause/resume, state serialization, or profile resolution — those come from Arnold.

#### 2. Register with Arnold

The existing `arnold/pipelines/vibecomfy_executor/` module becomes a tiny registration shim:

```python
# arnold/pipelines/vibecomfy_executor/__init__.py
name = "vibecomfy-executor"
driver = "native"
entrypoint = "vibecomfy.executor.pipeline:run_executor"
default_profile = "@vibecomfy-executor:default"
```

No graph builder, no Megaplan conversion.

#### 3. App integration

Add a new endpoint `POST /vibecomfy/agent-chat` that calls `run_executor` directly (or through the Arnold native runtime if the app wants pause/resume). The existing `/vibecomfy/agent-edit` endpoint stays unchanged.

### Boundary summary

| Concern | Arnold owns | VibeComfy owns |
|---|---|---|
| Pipeline execution engine | ✅ native executor, checkpointing, resume |
| Driver registry / CLI dispatch | ✅ |
| Generic hooks, state store, profiles | ✅ |
| Agent backend abstraction | ✅ `AgentBackend` protocol + Arnold backend |
| VibeComfy-specific phases | ✅ `vibecomfy.executor.pipeline` |
| Edit integration | ✅ `vibecomfy.executor.integrations.edit` |
| App endpoint / UX | ✅ `/vibecomfy/agent-chat` |
| TOML profile files | co-owned; bundled defaults live in VibeComfy, loaded by Arnold |

## Risks

- **Dual runtime complexity.** Arnold will have both graph and native executors. They must share state/artifact contracts so tools can inspect either.
- **Feature parity.** The native executor must catch up to graph executor features: `ParallelStage` equivalents, typed-port validation, subloops, suspension contracts. We should port features incrementally.
- **ComfyUI import collisions.** Even with a clean Arnold runtime, importing Arnold agent backends inside ComfyUI can clash with custom nodes. The native core should allow direct-provider backends (OpenAI/Anthropic HTTP) so the app can avoid heavy Arnold imports if desired.

## Recommended first milestone

1. Implement `arnold.pipeline.native` with just enough to run a linear `@pipeline` of `@phase` functions, with state serialization and resume.
2. Port `vibecomfy-executor` to native first; keep the old graph path as fallback.
3. Run `run_matrix.py` parity on the native path.
4. Only then generalize patterns (loops, fanout, decisions) for other workflows.
