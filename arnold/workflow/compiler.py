"""Compiler from the M2 explicit-node DSL to the v1 manifest contract.

Stability:
    public: ``compile_pipeline``
    internal: helpers that lower DSL carriers to manifest fields

The compiler never executes workflow topology code, prompt builders, hooks, or
reducers.  It lowers pure authoring data into deterministic manifest nodes and
edges and validates the result before returning it.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Iterable, Mapping

from arnold.manifest.refs import SourceSpan
from arnold.workflow.dsl import Capability, Input, Output, Pipeline, Route, Step
from arnold.manifest.manifests import (
    CapabilityRequirement,
    WorkflowEdge,
    WorkflowManifest,
    WorkflowNode,
)
from arnold.workflow.validation import validate_manifest


class CompileDiagnosticError(ValueError):
    """Raised when a pipeline cannot be lowered to a valid manifest."""

    def __init__(
        self,
        message: str,
        *,
        node_id: str | None = None,
        field: str | None = None,
    ) -> None:
        self.node_id = node_id
        self.field = field
        parts: list[str] = []
        if node_id is not None:
            parts.append(f"node {node_id!r}")
        if field is not None:
            parts.append(f"field {field!r}")
        prefix = " ".join(parts)
        if prefix:
            message = f"{prefix}: {message}"
        super().__init__(message)


def _diagnostic(
    message: str,
    *,
    node_id: str | None = None,
    field: str | None = None,
) -> CompileDiagnosticError:
    return CompileDiagnosticError(message, node_id=node_id, field=field)


def _freeze_metadata(value: Mapping[str, Any]) -> Mapping[str, Any]:
    """Return a JSON-serializable, hash-stable metadata mapping.

    Lists and tuples become JSON arrays so manifest validation accepts them.
    """

    frozen: dict[str, Any] = {}
    for key, subvalue in value.items():
        if isinstance(subvalue, Mapping):
            frozen[key] = dict(_freeze_metadata(subvalue))
        elif isinstance(subvalue, (list, tuple)):
            frozen[key] = [_freeze_value(item) for item in subvalue]
        else:
            frozen[key] = subvalue
    return frozen


def _freeze_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return _freeze_metadata(value)
    if isinstance(value, (list, tuple)):
        return [_freeze_value(item) for item in value]
    return value


def _pattern_block_type() -> type[Any]:
    from arnold.patterns._core import PatternBlock

    return PatternBlock


# The compiler is used in long-lived test processes that may reload
# ``arnold.workflow.dsl`` (e.g. import-boundary tests delete workflow
# submodules from ``sys.modules``).  Class-identity ``isinstance`` checks
# then fail because the reloaded module exposes a fresh ``Step``/``Route``
# class.  We accept carriers from any freshly-loaded workflow DSL module by
# checking their runtime module/name, while still using the module-level
# imports for type hints and internal construction.


def _is_step_instance(value: Any) -> bool:
    return type(value).__module__ == "arnold.workflow.dsl" and type(value).__name__ == "Step"


def _is_route_instance(value: Any) -> bool:
    return type(value).__module__ == "arnold.workflow.dsl" and type(value).__name__ == "Route"


def _validate_metadata_value(
    value: Any,
    *,
    node_id: str | None = None,
    field: str,
) -> None:
    if isinstance(value, Mapping):
        for key, subvalue in value.items():
            if not isinstance(key, str) or not key:
                raise _diagnostic(
                    "metadata keys must be non-empty strings",
                    node_id=node_id,
                    field=field,
                )
            _validate_metadata_value(subvalue, node_id=node_id, field=f"{field}.{key}")
        return
    if isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            _validate_metadata_value(item, node_id=node_id, field=f"{field}[{index}]")
        return
    if value is None or isinstance(value, (str, bool, int)):
        return
    if isinstance(value, float) and math.isfinite(value):
        return
    raise _diagnostic(
        (
            f"metadata values must be JSON primitives, arrays, or objects; "
            f"got {type(value).__name__}"
        ),
        node_id=node_id,
        field=field,
    )


def _validate_step(step: Step) -> None:
    _validate_metadata_value(step.metadata, node_id=step.id, field="metadata")
    for input_binding in step.inputs:
        _validate_metadata_value(
            input_binding.metadata,
            node_id=step.id,
            field=f"inputs.{input_binding.name}.metadata",
        )
    for output in step.outputs:
        _validate_metadata_value(
            output.metadata,
            node_id=step.id,
            field=f"outputs.{output.name}.metadata",
        )
    for capability in step.capabilities:
        _validate_metadata_value(
            capability.metadata,
            node_id=step.id,
            field=f"capabilities.{capability.id}.metadata",
        )


def _validate_route(route: Route) -> None:
    _validate_metadata_value(route.metadata, node_id=route.source, field=f"routes.{route.id}.metadata")


def _normalize_pipeline_inputs(
    pipeline: Pipeline,
    *,
    patterns: Any | Iterable[Any] = (),
) -> tuple[tuple[Step, ...], tuple[Route, ...]]:
    pattern_block_type = _pattern_block_type()
    if isinstance(patterns, pattern_block_type):
        patterns = (patterns,)
    steps: list[Step] = []
    routes: list[Route] = list(pipeline.routes)

    for index, step in enumerate(pipeline.steps):
        if isinstance(step, pattern_block_type):
            raise _diagnostic(
                "PatternBlock values are not allowed in Pipeline.steps; "
                "pass them via compile_pipeline(..., patterns=(block,))",
                field=f"steps[{index}]",
            )
        if not _is_step_instance(step):
            raise _diagnostic(
                f"Pipeline.steps values must be Step instances, got {type(step).__name__}",
                field=f"steps[{index}]",
            )
        steps.append(step)

    for index, pattern in enumerate(patterns):
        if not isinstance(pattern, pattern_block_type):
            raise _diagnostic(
                f"patterns values must be PatternBlock instances, got {type(pattern).__name__}",
                field=f"patterns[{index}]",
            )
        for step in pattern.steps:
            if not _is_step_instance(step):
                raise _diagnostic(
                    f"PatternBlock.steps values must be Step instances, got {type(step).__name__}",
                    field=f"patterns[{index}].steps",
                )
            steps.append(step)
        for route in pattern.routes:
            if not _is_route_instance(route):
                raise _diagnostic(
                    f"PatternBlock.routes values must be Route instances, got {type(route).__name__}",
                    field=f"patterns[{index}].routes",
                )
            routes.append(route)

    step_tuple = tuple(steps)
    route_tuple = tuple(routes)
    for step in step_tuple:
        _validate_step(step)
    for route in route_tuple:
        _validate_route(route)
    _validate_metadata_value(pipeline.metadata, field="metadata")
    return step_tuple, route_tuple


def _compile_capability(capability: Capability) -> CapabilityRequirement:
    return CapabilityRequirement(
        capability_id=capability.id,
        route=capability.route,
        required=capability.required,
    )


def _compile_input(input_binding: Input) -> dict[str, Any]:
    meta: dict[str, Any] = {}
    if input_binding.value_ref is not None:
        meta["value_ref"] = input_binding.value_ref
    if input_binding.schema_hash is not None:
        meta["schema_hash"] = input_binding.schema_hash
    return meta


def _compile_output(output: Output) -> dict[str, Any]:
    meta: dict[str, Any] = {}
    if output.schema_hash is not None:
        meta["schema_hash"] = output.schema_hash
    return meta


def _compile_step(step: Step) -> WorkflowNode:
    metadata = _freeze_metadata(step.metadata)
    if step.inputs:
        metadata["input_bindings"] = {
            input_binding.name: _compile_input(input_binding)
            for input_binding in step.inputs
        }
    if step.outputs:
        metadata["output_bindings"] = {
            output.name: _compile_output(output)
            for output in step.outputs
        }
    return WorkflowNode(
        id=step.id,
        kind=step.kind,
        label=step.label,
        inputs=tuple(input_binding.name for input_binding in step.inputs),
        outputs=tuple(output.name for output in step.outputs),
        capabilities=tuple(_compile_capability(capability) for capability in step.capabilities),
        policy=step.policy,
        source_span=step.source_span,
        subpipeline=step.subpipeline,
        metadata=metadata,
    )


def _compile_route(route: Route) -> WorkflowEdge:
    return WorkflowEdge(
        id=route.id,
        source=route.source,
        target=route.target,
        label=route.label,
        condition_ref=route.condition_ref,
        metadata=_freeze_metadata(route.metadata),
    )


def compile_pipeline(
    pipeline: Pipeline,
    *,
    patterns: Iterable[Any] = (),
) -> WorkflowManifest:
    """Lower an explicit-node pipeline to a validated ``WorkflowManifest``.

    Authored step IDs are preserved exactly.  Duplicate IDs are rejected rather
    than renamed.  Edge IDs are deterministic and derived from authored route
    data.  The manifest is validated before it is returned, and both topology
    and manifest hashes are computed from canonical inputs.
    """

    steps, routes = _normalize_pipeline_inputs(pipeline, patterns=patterns)

    known_ids: set[str] = set()
    duplicate_ids: set[str] = set()
    for step in steps:
        if step.id in known_ids:
            duplicate_ids.add(step.id)
        known_ids.add(step.id)
    if duplicate_ids:
        raise _diagnostic(
            f"duplicate step ids are not allowed: {sorted(duplicate_ids)!r}",
            field="steps",
        )

    edge_ids: set[str] = set()
    for route in routes:
        if route.id in edge_ids:
            raise _diagnostic(
                f"duplicate route id {route.id!r}",
                node_id=route.source,
                field="routes",
            )
        edge_ids.add(route.id)
        if route.source not in known_ids:
            raise _diagnostic(
                f"route source {route.source!r} is not a declared step",
                node_id=route.source,
                field="routes",
            )
        if route.target not in known_ids:
            raise _diagnostic(
                f"route target {route.target!r} is not a declared step",
                node_id=route.target,
                field="routes",
            )

    nodes = tuple(_compile_step(step) for step in steps)
    edges = tuple(_compile_route(route) for route in routes)

    manifest = WorkflowManifest(
        id=pipeline.id,
        nodes=nodes,
        edges=edges,
        version=pipeline.version,
        capabilities=tuple(_compile_capability(capability) for capability in pipeline.capabilities),
        policy=pipeline.policy,
        source_span=pipeline.source_span,
        metadata=_freeze_metadata(pipeline.metadata),
    )
    validate_manifest(manifest)
    return manifest


def compile_pattern_block(
    pattern_block: Any,
    *,
    id: str = "pattern",
    version: str = "1.0",
    source_span: SourceSpan | None = None,
    metadata: Mapping[str, Any] | None = None,
) -> WorkflowManifest:
    """Compile a single ``PatternBlock`` to a validated ``WorkflowManifest``.

    This is sugar for ``compile_pipeline(Pipeline(..., steps=(), routes=()),
    patterns=pattern_block)``.  Pattern blocks are first-class compiler inputs,
    but they remain outside ``Pipeline.steps`` to preserve the explicit-node
    invariant.
    """

    pipeline = Pipeline(
        id=id,
        version=version,
        steps=(),
        routes=(),
        source_span=source_span,
        metadata=metadata or {},
    )
    return compile_pipeline(pipeline, patterns=pattern_block)


@dataclass(frozen=True)
class CompileResult:
    """Internal carrier for the compiled manifest plus diagnostic helpers."""

    manifest: WorkflowManifest
