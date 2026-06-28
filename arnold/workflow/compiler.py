"""Compiler from the M2 explicit-node DSL to the v1 manifest contract.

Stability:
    public: ``compile_pipeline``
    internal: helpers that lower DSL carriers to manifest fields

The compiler never executes workflow topology code, prompt builders, hooks, or
reducers.  It lowers pure authoring data into deterministic manifest nodes and
edges and validates the result before returning it.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

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
        source_span=route.source_span,
        metadata=_freeze_metadata(route.metadata),
    )


def compile_pipeline(pipeline: Pipeline) -> WorkflowManifest:
    """Lower an explicit-node pipeline to a validated ``WorkflowManifest``.

    Authored step IDs are preserved exactly.  Duplicate IDs are rejected rather
    than renamed.  Edge IDs are deterministic and derived from authored route
    data.  The manifest is validated before it is returned, and both topology
    and manifest hashes are computed from canonical inputs.
    """

    known_ids: set[str] = set()
    duplicate_ids: set[str] = set()
    for step in pipeline.steps:
        if step.id in known_ids:
            duplicate_ids.add(step.id)
        known_ids.add(step.id)
    if duplicate_ids:
        raise _diagnostic(
            f"duplicate step ids are not allowed: {sorted(duplicate_ids)!r}",
            field="steps",
        )

    edge_ids: set[str] = set()
    for route in pipeline.routes:
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

    nodes = tuple(_compile_step(step) for step in pipeline.steps)
    edges = tuple(_compile_route(route) for route in pipeline.routes)

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


@dataclass(frozen=True)
class CompileResult:
    """Internal carrier for the compiled manifest plus diagnostic helpers."""

    manifest: WorkflowManifest
