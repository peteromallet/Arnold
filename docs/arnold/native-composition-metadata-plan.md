# Native Composition Metadata Rollout Plan

This document describes the additive decorator and IR metadata rollout for the
M0 bridge milestone.  It names the new stable fields, specifies the additive
invocable metadata shape that both `NativePhase` and `NativePipeline` must
satisfy, and defines the rollout order so that later milestones have a wired
surface to target without breaking existing behaviour.

## Scope

- **M0 is additive only.**  No existing dunder attribute, decorator parameter,
  IR field, or introspection helper is removed.
- The new metadata is *declared* on decorators and *carried forward* into the
  native IR so that composition, trace, replay, and conformance tooling can
  read it without executing decorated bodies.
- `NativePhase` and `NativePipeline` remain concrete frozen dataclasses.
  The new fields are added to their existing field sets; no abstract base class,
  protocol, or mixin replaces them.  They satisfy the invocable metadata shape
  by *having* the named fields, not by inheritance.

## Current Decorator Metadata Surface

Before M0 the decorators in `arnold/pipeline/native/decorators.py` attach these
dunder attributes to decorated functions:

### `@phase`

| Dunder attribute               | Type                      | Default                  |
|--------------------------------|---------------------------|--------------------------|
| `__phase__`                    | `bool`                    | `True`                   |
| `__phase_name__`               | `str`                     | function `__name__`      |
| `__phase_description__`        | `str \| None`             | `None`                   |
| `__phase_produces__`           | `tuple`                   | `()`                     |
| `__phase_consumes__`           | `tuple`                   | `()`                     |

### `@pipeline`

| Dunder attribute               | Type                      | Default                  |
|--------------------------------|---------------------------|--------------------------|
| `__pipeline__`                 | `bool`                    | `True`                   |
| `__pipeline_name__`            | `str`                     | function `__name__`      |
| `__pipeline_description__`     | `str \| None`             | `None`                   |

The introspection helpers `is_phase`, `get_phase_meta`, `is_pipeline`,
`get_pipeline_meta`, `is_decision`, and `get_decision_meta` read only these
attributes.  They return hand-built `dict` values rather than IR dataclass
instances.

## Current IR Metadata Surface

Before M0 the native IR dataclasses in `arnold/pipeline/native/ir.py` carry
these fields:

### `NativePhase`

| Field        | Type                    | Default |
|--------------|-------------------------|---------|
| `name`       | `str`                   | *(required)* |
| `func`       | `Callable[..., Any]`    | *(required, compare=False, hash=False)* |
| `produces`   | `tuple`                 | `()`    |
| `consumes`   | `tuple`                 | `()`    |

### `NativePipeline`

| Field         | Type                        | Default |
|---------------|-----------------------------|---------|
| `name`        | `str`                       | *(required)* |
| `func`        | `Callable[..., Any]`        | *(required, compare=False, hash=False)* |
| `phases`      | `tuple[NativePhase, ...]`   | `()`    |
| `decisions`   | `tuple[NativeDecision, ...]`| `()`    |
| `loop_guards` | `tuple[NativeLoopGuard, ...]`| `()`   |
| `description` | `str`                       | `""`    |

## Additive Decorator Fields (M0)

### `@step` / `@phase`

The `@step` decorator is the preferred authoring name.  `@phase` is the
compatibility alias.  Both carry the same new dunder attributes **in addition
to** the existing `__phase__` and `__phase_*` attributes.

New dunder attributes:

| Dunder attribute       | Type                      | Default                          |
|------------------------|---------------------------|----------------------------------|
| `__step_id__`          | `str \| None`             | `None` (compiler derives from canonical callable identity) |
| `__step_inputs__`      | `dict[str, Any] \| None`  | `None`                           |
| `__step_outputs__`     | `dict[str, Any] \| None`  | `None`                           |

Decorator signature (additive parameters shown with defaults):

```python
def step(
    name: str | None = None,
    *,
    id: str | None = None,              # NEW — stable semantic identity
    description: str | None = None,
    inputs: dict[str, Any] | None = None,  # NEW — declared input schema
    outputs: dict[str, Any] | None = None, # NEW — declared output schema
    produces: tuple = (),                  # existing — port metadata (compatibility)
    consumes: tuple = (),                  # existing — port metadata (compatibility)
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    ...
```

The decorator implementation must:

1. Attach `__step_id__`, `__step_inputs__`, and `__step_outputs__` as function
   attributes (in addition to all existing `__phase_*` attributes).
2. When `id` is `None`, set `__step_id__ = None` and let the compiler derive a
   default from the canonical callable identity at compile time.
3. When `id` is provided, treat it as the durable semantic identity.  It is
   stable across compilation, projection, trace emission, and replay.
4. Keep `produces` / `consumes` as the compatibility port-metadata substrate
   used by current projection and runtime layers.

### `@workflow` / `@pipeline`

The `@workflow` decorator is the preferred authoring name.  `@pipeline` is the
compatibility alias.  Both carry the same new dunder attributes **in addition
to** the existing `__pipeline__` and `__pipeline_*` attributes.

New dunder attributes:

| Dunder attribute          | Type                      | Default                          |
|---------------------------|---------------------------|----------------------------------|
| `__workflow_id__`         | `str \| None`             | `None` (compiler derives from canonical callable identity) |
| `__workflow_inputs__`     | `dict[str, Any] \| None`  | `None`                           |
| `__workflow_outputs__`    | `dict[str, Any] \| None`  | `None`                           |

Decorator signature (additive parameters shown with defaults):

```python
def workflow(
    name: str | None = None,
    *,
    id: str | None = None,              # NEW — stable workflow identity
    description: str | None = None,
    inputs: dict[str, Any] | None = None,  # NEW — declared workflow input schema
    outputs: dict[str, Any] | None = None, # NEW — declared workflow output schema
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    ...
```

The decorator implementation must:

1. Attach `__workflow_id__`, `__workflow_inputs__`, and `__workflow_outputs__`
   as function attributes (in addition to all existing `__pipeline_*` attributes).
2. When `id` is `None`, set `__workflow_id__ = None` and let the compiler derive
   a default.
3. When `id` is provided, treat it as the durable workflow identity.

### `@decision`

`@decision` is unchanged in M0.  It does not become `@step` and does not
receive `inputs`/`outputs` fields.  Decision vocabulary, human-gate metadata,
resume schema, and override routes remain explicit and are validated separately
from step/workflow IO contracts.

## Additive IR Fields (M0)

### `NativePhase` — Additive Fields

The following fields are added to `NativePhase` with defaults that preserve
backward compatibility.  Every existing constructor call site that does not
pass the new fields continues to compile and behave identically.

| Field            | Type                      | Default    | Notes |
|------------------|---------------------------|------------|-------|
| `id`             | `str \| None`             | `None`     | Stable semantic identity.  `None` means identity is derived from `name` by the compiler; an explicit value is the durability contract. |
| `inputs_schema`  | `dict[str, Any] \| None`  | `None`     | Declared input schema metadata.  Must be serializable and comparable without executing the callable body. |
| `outputs_schema` | `dict[str, Any] \| None`  | `None`     | Declared output schema metadata.  Same serializability contract. |

The existing fields `name`, `func`, `produces`, and `consumes` are retained
unchanged.  `NativePhase` remains a concrete frozen dataclass.

### `NativePipeline` — Additive Fields

| Field            | Type                      | Default    | Notes |
|------------------|---------------------------|------------|-------|
| `id`             | `str \| None`             | `None`     | Stable workflow identity. |
| `inputs_schema`  | `dict[str, Any] \| None`  | `None`     | Declared workflow input schema metadata. |
| `outputs_schema` | `dict[str, Any] \| None`  | `None`     | Declared workflow output schema metadata. |

The existing fields `name`, `func`, `phases`, `decisions`, `loop_guards`, and
`description` are retained unchanged.  `NativePipeline` remains a concrete
frozen dataclass.

### Other IR Types

`NativeDecision`, `NativeLoopGuard`, `ParallelInstruction`, `NativeInstruction`,
and `NativeProgram` do not receive new fields in M0.  `NativeInstruction` and
`NativeProgram` already carry `produces`/`consumes` metadata and decision
vocabulary sufficient for the current compiler.

### Invocable Metadata Shape

Both `NativePhase` and `NativePipeline` satisfy the same additive invocable
metadata shape by possessing these named fields:

- `name: str`
- `id: str | None`
- `inputs_schema: dict[str, Any] | None`
- `outputs_schema: dict[str, Any] | None`

This shape is structural, not inherited.  There is no `Invocable` protocol or
abstract base class.  Conformance is checked by the compiler reading the named
fields from the concrete dataclass instances.  Later milestones may add a
shared helper that reads these fields generically, but that helper operates
over the existing concrete types.

## Introspection Helper Updates (M0)

The existing introspection helpers in `arnold/pipeline/native/decorators.py`
are extended additively.  No existing helper is removed or changes its return
type.

### New Helpers

```python
def is_step(fn: Any) -> bool:
    """Return True if *fn* is a @step- or @phase-decorated callable."""

def get_step_meta(fn: Any) -> dict[str, Any] | None:
    """Return step metadata dict including id, inputs, outputs."""

def is_workflow(fn: Any) -> bool:
    """Return True if *fn* is a @workflow- or @pipeline-decorated callable."""

def get_workflow_meta(fn: Any) -> dict[str, Any] | None:
    """Return workflow metadata dict including id, inputs, outputs."""
```

### Expanded Existing Helpers

`get_phase_meta` and `get_pipeline_meta` are extended to also include the new
`id`, `inputs`, and `outputs` keys when the corresponding dunder attributes are
present.  When the new dunder attributes are `None`, the keys are present with
`None` values so that callers do not need to guard against missing keys.

```python
def get_phase_meta(fn: Any) -> dict[str, Any] | None:
    """Return phase metadata dict including id, inputs, outputs."""
    if not is_phase(fn):
        return None
    return {
        "name": getattr(fn, "__phase_name__", fn.__name__),
        "description": getattr(fn, "__phase_description__", None),
        "produces": getattr(fn, "__phase_produces__", ()),
        "consumes": getattr(fn, "__phase_consumes__", ()),
        "id": getattr(fn, "__step_id__", None),
        "inputs": getattr(fn, "__step_inputs__", None),
        "outputs": getattr(fn, "__step_outputs__", None),
    }

def get_pipeline_meta(fn: Any) -> dict[str, Any] | None:
    """Return pipeline metadata dict including id, inputs, outputs."""
    if not is_pipeline(fn):
        return None
    return {
        "name": getattr(fn, "__pipeline_name__", fn.__name__),
        "description": getattr(fn, "__pipeline_description__", None) or "",
        "phases": [],
        "decisions": [],
        "id": getattr(fn, "__workflow_id__", None),
        "inputs": getattr(fn, "__workflow_inputs__", None),
        "outputs": getattr(fn, "__workflow_outputs__", None),
    }
```

## Compiler Integration (M0)

The compiler in `arnold/pipeline/native/compiler.py` is updated to:

1. Read `__step_id__` / `__step_inputs__` / `__step_outputs__` from decorated
   phase callables and propagate them into the `NativePhase` constructor.
2. Read `__workflow_id__` / `__workflow_inputs__` / `__workflow_outputs__` from
   the decorated pipeline callable and propagate them into the `NativePipeline`
   that `emit()` returns (via `NativeProgram`).
3. Derive a default stable ID from the canonical callable identity when the
   authored `id` is `None`.  The default derivation is a function of the
   callable's fully-qualified name; it is deterministic and stable across
   compilations of the same source.

The compiler's `emit()` method already constructs `NativePhase` and
`NativeProgram` instances.  The new fields are passed as additional keyword
arguments; existing call sites that use positional or keyword-only construction
are updated to include the new fields with `None` defaults.

## Rollout Order

### Phase 0 — Documentation (this document)
- This document is the canonical reference for the metadata rollout.
- All subsequent phases must preserve the naming and shape specified here.

### Phase 1 — Decorator Field Wiring
- Add `id`, `inputs`, `outputs` parameters to `@step`/`@workflow` decorators.
- Attach `__step_id__`, `__step_inputs__`, `__step_outputs__` (and
  `__workflow_*` equivalents) as function attributes.
- `@phase` and `@pipeline` aliases are updated to carry the same new dunder
  attributes alongside their existing ones.
- All existing tests continue to pass because the new parameters are optional
  and the old dunder attributes are preserved.

### Phase 2 — IR Field Addition
- Add `id`, `inputs_schema`, `outputs_schema` to `NativePhase` and
  `NativePipeline` dataclasses with `None` defaults.
- No existing constructor call site is broken because the new fields have
  defaults.

### Phase 3 — Introspection Helper Update
- Add `is_step`, `get_step_meta`, `is_workflow`, `get_workflow_meta`.
- Extend `get_phase_meta` and `get_pipeline_meta` to include the new keys.
- Existing helpers return supersets of their previous dicts; no caller sees
  fewer keys.

### Phase 4 — Compiler Integration
- Update the compiler to read decorator metadata and propagate it into IR
  instances.
- Update `emit()` to pass the new fields to `NativeProgram` and `NativePhase`
  constructors.
- Default ID derivation is deterministic and stable.

### Phases 5+ — Migration and Conformance (M1-M6)
- Megaplan migration from compatibility shells to source-owned composition uses
  the new metadata fields.
- Conformance tooling reads `id`, `inputs_schema`, `outputs_schema` from
  compiled IR.
- The invocable metadata shape enables generic composition validation without
  inspecting function bodies.

## Backward Compatibility Guarantees

1. **All existing `@phase` and `@pipeline` usage continues to work.**  The new
   `id`, `inputs`, and `outputs` parameters are keyword-only and optional.

2. **All existing dunder attributes remain.**  `__phase__`, `__phase_name__`,
   `__phase_description__`, `__phase_produces__`, `__phase_consumes__`,
   `__pipeline__`, `__pipeline_name__`, and `__pipeline_description__` are not
   removed or renamed.

3. **All existing introspection helpers continue to work.**  `is_phase`,
   `get_phase_meta`, `is_pipeline`, `get_pipeline_meta`, `is_decision`, and
   `get_decision_meta` are unchanged in their core logic.  `get_phase_meta` and
   `get_pipeline_meta` gain new keys but do not lose existing ones.

4. **All existing IR constructors continue to work.**  `NativePhase(name=...,
   func=...)` and `NativePipeline(name=..., func=...)` still compile because
   the new fields have `None` defaults.

5. **All existing compiler behaviour is preserved.**  The compiler still lowers
   `@pipeline`-decorated generators into `NativeProgram` instances.  The new
   metadata is propagated alongside existing `produces`/`consumes` metadata;
   nothing is removed.

6. **`@decision` is unchanged.**  It does not receive `id`, `inputs`, or
   `outputs` fields.  Decision vocabulary and human-gate metadata remain on
   their existing attributes and IR fields.

## Non-Conformant Patterns (Documented, Not Fixed In M0)

The following patterns are known to exist in the codebase and are documented as
non-conformant migration targets for M1-M6.  M0 does not fix them unless they
block the contract fixtures.

- Direct `NativePhase(...)` and `NativePipeline(...)` construction in
  `arnold_pipelines/megaplan/_compatibility.py` and
  `arnold_pipelines/megaplan/select_tournament/pipeline.py` that does not pass
  the new `id`, `inputs_schema`, or `outputs_schema` fields.  These sites
  continue to work because the new fields have `None` defaults, but they do not
  declare composition metadata and are therefore not conformant with the M0
  contract.

- Hand-built dict returns from `get_phase_meta` and `get_pipeline_meta` that
  are consumed by code expecting only the pre-M0 keys.  The new keys are
  additive and backward-compatible, but callers should migrate to read the new
  keys when they need composition metadata.

## Acceptance Criteria

An implementation satisfies this rollout plan when:

1. `@step` and `@workflow` decorators exist and accept `id`, `inputs`, and
   `outputs` parameters.
2. `@phase` and `@pipeline` aliases carry the same new dunder attributes
   alongside their existing ones.
3. `NativePhase` has `id`, `inputs_schema`, and `outputs_schema` fields with
   `None` defaults.
4. `NativePipeline` has `id`, `inputs_schema`, and `outputs_schema` fields with
   `None` defaults.
5. The compiler propagates decorator metadata into IR instances.
6. All existing native pipeline tests pass.
7. All existing `@phase` / `@pipeline` authoring patterns continue to work
   without modification.
