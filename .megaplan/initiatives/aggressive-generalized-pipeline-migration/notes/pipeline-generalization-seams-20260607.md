# Pipeline Generalization Seams

Date: 2026-06-07

This note synthesizes a seven-agent DeepSeek audit of how Megaplan can move toward reusable, Python-first pipeline composition while preserving the current Evidence-First epic as the priority.

## Core Conclusion

The desired shape is real and already partially present: simple Python scripts should compose reusable pipeline steps, while Megaplan itself becomes one pipeline package built from those same primitives.

The right layering is:

1. `arnold.pipeline` generic runtime
2. reusable step contracts and model-boundary contracts
3. a small synchronous runner API
4. Megaplan-specific phase policy on top
5. chain/epic orchestration as the outer policy layer

The Evidence-First epic should still take precedence because it makes the state, evidence, transition, and engine/target boundaries trustworthy enough for these abstractions to be safe.

## Proposed Layers

### 1. Generic Runtime

Move or stabilize generic mechanisms under `arnold.pipeline` or `arnold.pipeline._runtime`:

- atomic JSON/text/bytes writes
- framed event logs
- append-only event writer
- state cache plus shadow-WAL authority fold
- lock helpers
- artifact repository base
- generic receipt base
- process/runtime utilities
- key pool, budget authority, governor
- sandbox context and write validation

Megaplan should continue to define policy-specific event kinds, state fields, artifact classifiers, and receipt extensions.

### 2. Step Contract

Create a single source of truth for phase/step metadata, replacing the current scatter across `workers/_impl.py`, `model_seam.py`, `schemas/runtime.py`, and recovery fallback tables.

Likely fields:

- `step`
- `schema_key`
- `capture_schema_key`
- `output_filename`
- `fallback_output_filename`
- `default_worker`
- `supports_persistent`
- `supports_read_only`
- `template_write_step`
- `timeout_seconds`
- `capture_normalizer`
- `auto_retryable`

Do not put runtime invocation state, prompt text, concrete provider flags, orchestration transitions, or state mutation policy inside `StepContract`.

### 3. Runner API

Expose a small Python API for scripts:

```python
from arnold.pipelines.megaplan.runner import run_step, next_steps, run_pipeline

run_step(plan, "plan", root=root)
run_step(plan, "critique", root=root)
run_step(plan, "gate", root=root)
```

The runner should:

- load plan state
- validate the requested transition
- dispatch the existing handler in-process
- return a structured `StepOutcome`
- avoid owning retry/stall/escalation policy

`auto.py` and chain/epic can keep the heavyweight unattended behavior.

### 4. Pipeline Composition

Python-first pipeline packages already have a partial surface:

```python
from arnold.pipelines.megaplan._pipeline.types import Pipeline

def build_pipeline() -> Pipeline:
    return (
        Pipeline.builder("my-pipeline")
        .input("draft", file=True)
        .agent("review", prompt="prompts/review.md", inputs=["draft"])
        .agent("revise", prompt="prompts/revise.md", inputs=["draft", "review"])
        .build()
    )
```

Keep YAML/declarative syntax postponed until the Python API is stable. If YAML returns, it should compile into the typed Python `Pipeline` graph, not bypass it.

### 5. Chain/Epic Layer

Chain/epic should remain policy, not base runtime:

- YAML milestone spec parsing
- Git/PR lifecycle
- merge policy
- clean-base requirements
- milestone retry/bump ladder
- completion contract checks
- hinge/dual-green/eval gates
- ladder-exhaustion ticketing

Generic pipeline responsibilities currently hidden in chain:

- ordered node iteration
- cursor/checkpoint persistence
- node dependency validation
- outcome normalization
- retry/terminal decision dispatch

The clean extraction seam is the existing `supervisor/chain_runner.py` loop: pull the generic loop into `supervisor/pipeline_runner.py`, leave chain-specific spec/Git/PR policy in chain bindings.

## Migration Sequence

1. Finish the active Evidence-First epic foundations; do not reorder this behind abstraction work.
2. Add characterization tests for existing workflow transitions and recovery maps.
3. Add `StepContract` as a checked mirror of existing dicts; no runtime behavior change.
4. Derive schema/capture/normalizer views from `StepContract`.
5. Add a minimal `runner.py` with `run_step`, `next_steps`, `run_pipeline`.
6. Extract generic state/artifact/event/runtime helpers behind re-export shims.
7. Pull generic chain loop behavior into a neutral pipeline runner.
8. Prove with a non-Megaplan pipeline that uses the same primitives without importing Megaplan state constants.

## No-Go Areas During Active Epic

- Do not change the `ContractResult` shared boundary.
- Do not change or delete `workflow_next`.
- Do not disturb `model_seam.py` capture/audit behavior during active evidence/Step-IO migrations.
- Do not relocate planning or delete compatibility paths until replay/dual-run characterization is green.
- Do not build YAML first.

## Readiness Tests

The abstraction is ready when:

- a non-planning pipeline runs on the same SDK pieces without Megaplan imports
- old and new planning paths match in replay/dual-run oracle tests
- `arnold.pipeline/**` has no Megaplan imports, `STATE_*`, or `GateRecommendation`
- planning reads as composition of generic primitives rather than defining the SDK itself
- resident/agent surfaces can bind to the same dispatch protocol without duplicating prompt assembly

