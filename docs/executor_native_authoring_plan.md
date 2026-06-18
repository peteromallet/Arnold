# Execution plan: native authoring over Arnold's neutral graph executor

## Decision

Instead of building a brand-new generator-based native executor in Arnold, we will:

1. Let authors write pipelines as plain Python functions/classes.
2. Provide Arnold decorators/helpers that lower those functions into neutral `Stage`/`Step` objects and a `Pipeline` graph.
3. Run the resulting graph through Arnold's existing neutral executor (`arnold.pipeline.executor.run_pipeline`) or `PipelineStepwiseDriver`.
4. Implement the VibeComfy executor as the first consumer of this new authoring layer.

This reuses the runtime we already have and fills the real gap: **author experience and CLI dispatch**.

## Why this approach

- Arnold already has a working neutral executor (`arnold/pipeline/executor.py`), typed ports, `ExecutorHooks`, `PipelineBuilder`, and `PipelineStepwiseDriver`.
- The only bridged pipeline (`demo_judges`) proves neutral execution works; the limitation is the hard `_BRIDGED_PIPELINES` allowlist and lack of authoring support, not the executor.
- A generator-based executor introduces continuation serialization, exception/retry semantics, and typed-port parity problems that we do not need to solve now.

## Phase 0 — Arnold: make `driver` route to the neutral executor

### Goal

`arnold run vibecomfy-executor` should be able to bypass the legacy Megaplan executor and run through the neutral executor when the pipeline declares `driver = "in_process"` or `driver = "native"`.

### Changes

1. **Extend pipeline metadata vocabulary**

   Accept `driver = "in_process"` / `"native"` / `"graph"` in `arnold/pipelines/_authoring.py` and the manifest contract.

2. **Add a driver registry**

   ```python
   # arnold/pipeline/drivers.py
   DRIVER_RUNNERS: dict[str, Callable] = {
       "graph": run_megaplan_pipeline,       # existing legacy path
       "in_process": run_neutral_pipeline,   # new
       "native": run_neutral_pipeline,       # alias
   }
   ```

3. **Branch `arnold <module> run` on driver**

   In `arnold/pipelines/megaplan/cli/arnold.py`, `_handle_module_verb()` currently always calls `_megaplan_main(["run", module, ...])`. Change it to:

   ```python
   driver = pipeline_metadata(module).get("driver", "graph")
   if driver in ("in_process", "native"):
       return run_neutral_pipeline_module(module, argv)
   return _megaplan_main(["run", module, *argv])
   ```

4. **Add `run_neutral_pipeline_module()`**

   This helper:
   - imports the pipeline module,
   - calls `build_pipeline()`,
   - constructs a neutral `StepContext` with `artifact_root`, `inputs`, `profile`, `hook_extensions`,
   - invokes `arnold.pipeline.runner.run_pipeline()` with appropriate hooks.

5. **Update scaffolding**

   Allow `arnold pipelines new --driver in_process` to generate a module that uses the new authoring layer.

### Acceptance

```bash
arnold run vibecomfy-executor --inputs query="hello" --profile @vibecomfy-executor:default
```

executes through the neutral executor, not the legacy Megaplan executor.

## Phase 1 — Arnold: native authoring helpers

### Goal

Authors can write plain functions and get a neutral `Pipeline` graph back.

### Changes

1. **Add `arnold/pipeline/native/authoring.py`**

   ```python
   from dataclasses import dataclass
   from typing import Any, Callable
   from arnold.pipeline.types import Step, StepContext, StepResult

   @dataclass(frozen=True)
   class FunctionStep(Step):
       name: str
       kind: str
       fn: Callable[[StepContext], Any]

       def run(self, ctx: StepContext) -> StepResult:
           result = self.fn(ctx)
           if isinstance(result, StepResult):
               return result
           return StepResult(outputs=result if isinstance(result, dict) else {"result": result})

   def step_from_function(
       fn: Callable,
       *,
       name: str | None = None,
       kind: str = "produce",
       consumes: tuple[str, ...] = (),
       produces: tuple[str, ...] = (),
   ) -> Stage: ...
   ```

2. **Add `@step` and `@pipeline` decorators**

   ```python
   # arnold/pipeline/native/decorators.py
   def step(name=None, kind="produce", consumes=(), produces=()):
       def decorator(fn):
           return step_from_function(fn, name=name or fn.__name__, kind=kind, consumes=consumes, produces=produces)
       return decorator

   def pipeline(name=None, entry="run"):
       def decorator(fn):
           @functools.wraps(fn)
           def build_pipeline():
               return fn(PipelineBuilder(name=name or fn.__name__))
           build_pipeline.pipeline_name = name or fn.__name__
           return build_pipeline
       return decorator
   ```

3. **Add a neutral-hooks implementation for state/artifact persistence**

   ```python
   # arnold/pipeline/native/hooks.py
   class NativeExecutorHooks(NullExecutorHooks):
       def __init__(self, artifact_root: Path):
           self.artifact_root = Path(artifact_root)

       def on_stage_complete(self, stage, ctx, result, state, owned_keys):
           _write_state_json(self.artifact_root, state)
   ```

### Acceptance

A pipeline module can look like this:

```python
# arnold/pipelines/my_native/__init__.py
name = "my-native"
driver = "in_process"
default_profile = None

from arnold.pipeline.native.decorators import pipeline, step
from arnold.pipeline.builder import PipelineBuilder

@step(name="load", produces=("data",))
def load(ctx):
    return {"data": ctx.inputs["value"] * 2}

@step(name="reply", consumes=("data",), produces=("reply",))
def reply(ctx):
    return {"reply": f"got {ctx.state['data']}"}

@pipeline(name="my-native")
def build_pipeline(builder: PipelineBuilder):
    load_stage = load
    reply_stage = reply
    return (
        builder
        .add_stage(load_stage, emit_label="reply")
        .add_stage(reply_stage, emit_label="halt")
        .build(derive_bindings=True)
    )
```

## Phase 2 — VibeComfy: implement the executor as a native-authored pipeline

### Goal

Move VibeComfy executor logic into a native-authored pipeline that returns a neutral `Pipeline` graph.

### Changes

1. **Create `vibecomfy/executor/` package**

   ```text
   vibecomfy/executor/
     __init__.py
     pipeline.py          # build_pipeline() + @step-decorated phases
     phases.py            # classify, research, implement, reply functions
     models.py            # Plan, ExecutorResult
     profiles.py          # bundled default/openai/anthropic/opensource TOML
     integrations/
       edit.py            # headless handle_agent_edit wrapper
       hivemind.py        # corpus search
   ```

2. **Write phases as plain functions**

   ```python
   # vibecomfy/executor/phases.py
   from arnold.pipeline.native.decorators import step
   from arnold.pipeline.types import StepContext

   @step(name="classify", consumes=("query",), produces=("plan",))
   def classify(ctx: StepContext):
       query = ctx.inputs["query"]
       graph = ctx.inputs.get("graph")
       # ... existing heuristic + optional LLM call ...
       return {"plan": {"research": ..., "implement": ..., "reply": True}}
   ```

   `research`, `implement`, `reply` follow the same pattern.

3. **Build the pipeline**

   ```python
   # vibecomfy/executor/pipeline.py
   from arnold.pipeline.builder import PipelineBuilder
   from arnold.pipeline.native.decorators import pipeline
   from vibecomfy.executor.phases import classify, research, implement, reply

   @pipeline(name="vibecomfy-executor")
   def build_pipeline(builder: PipelineBuilder):
       return (
           builder
           .add_stage(classify, emit_label="research")
           .add_stage(research, emit_label="implement")
           .add_stage(implement, emit_label="reply")
           .add_stage(reply, emit_label="halt")
           .build(derive_bindings=True)
       )
   ```

   Short-circuit logic (skip research/implement when not needed) moves into the phase functions: they check `ctx.state["plan"]` and return empty outputs if disabled.

4. **Keep the Arnold registration shim**

   ```python
   # arnold/pipelines/vibecomfy_executor/__init__.py
   name = "vibecomfy-executor"
   driver = "in_process"
   default_profile = "@vibecomfy-executor:default"
   entrypoint = "vibecomfy.executor.pipeline:build_pipeline"
   ```

   The old `steps.py`, `_helpers.py`, and `pipelines.py` can be deleted once parity is proven, or kept as a fallback under a feature flag.

### Acceptance

```bash
arnold run vibecomfy-executor --inputs 'query=Set KSampler seed to 12345,graph=tests/fixtures/agent_edit/flat.json' --profile @vibecomfy-executor:default
```

produces the same `state.json` shape as the legacy path.

## Phase 3 — VibeComfy app integration

### Goal

The app can call the executor directly without going through `arnold run`.

### Changes

1. **Expose a Python entry point**

   ```python
   # vibecomfy/executor/__init__.py
   from vibecomfy.executor.pipeline import build_pipeline

   def run_executor(query, graph=None, profile="default", artifact_dir=None):
       from arnold.pipeline.runner import run_pipeline
       from arnold.pipeline.native.hooks import NativeExecutorHooks

       pipeline = build_pipeline()
       hooks = NativeExecutorHooks(artifact_dir) if artifact_dir else NullExecutorHooks()
       result = run_pipeline(
           pipeline,
           initial_state={"query": query, "graph": graph},
           hooks=hooks,
       )
       return result
   ```

2. **Wire into the app**

   - Add a new `POST /vibecomfy/agent-chat` route that calls `run_executor()`.
   - Or, if the existing `/vibecomfy/agent-edit/chat` route is the right semantic fit, refactor it to call `run_executor()` instead of the single-turn runtime.
   - Keep `/vibecomfy/agent-edit` as the direct graph-edit path.

3. **Preserve subprocess isolation**

   For ComfyUI environments with import collisions, keep the existing worker/subprocess path available. The authoring layer does not force in-process execution.

## Phase 4 — Tests and parity

1. **Unit tests** for each phase with injected LLM/edit/research stubs.
2. **CLI parity test**: run both legacy and new `arnold run vibecomfy-executor` against the same inputs and compare `state.json` keys and artifact existence.
3. **App smoke test**: one happy-path call through `/vibecomfy/agent-chat` or `/vibecomfy/agent-edit/chat`.

## Trade-offs

### Pros

- **Reuses proven runtime.** Typed ports, hooks, parallelism, step-at-a-time drivers, and checkpoint/resume already exist.
- **Smaller change surface.** We add authoring + dispatch; we do not rebuild execution.
- **No generator-serialization problems.** State is explicit and JSON-serializable; Python locals are never frozen.
- **Maintains feature parity.** Anything the neutral graph executor supports (parallel stages, typed IO, overrides, hooks) works for native-authored pipelines.
- **Easier rollback.** The legacy path stays intact until the new path proves parity.

### Cons

- **Still graph-shaped under the hood.** Arbitrary Python control flow (`while`, dynamic branching) must be expressed as graph loops/decision edges.
- **Decorators are a middle layer.** Authors do not write raw `if`/`while`; they write functions and let the builder wire edges.
- **Neutral types still leak into authoring.** `@step` consumes/produces string port names; full Python-native typing would need more work.
- **Loops require explicit graph constructs.** For the Megaplan planning loop (critique → gate → revise), we still need `loop_condition` + decision edges or a subloop stage.

### When to reconsider a true native executor

If VibeComfy (or another consumer) needs Python control flow that cannot be lowered to a graph — e.g. dynamic numbers of iterations depending on runtime data that changes the pipeline structure itself — then we revisit a generator-based native executor with evidence from the first port.

## First milestone

1. Arnold CLI routes `driver = "in_process"` to the neutral executor.
2. `@step` / `step_from_function` / `FunctionStep` exist.
3. `vibecomfy-executor` returns a neutral `Pipeline` built from decorated phases.
4. One end-to-end run passes: `arnold run vibecomfy-executor` through the neutral path produces a reply.
