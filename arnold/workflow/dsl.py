"""Explicit-node workflow authoring DSL.

Stability:
    public: ``Pipeline``, ``Step``, ``Route``, ``Input``, ``Output``, ``Capability``
    provisional: policy, source-span, subpipeline, and metadata fields carried by
        the public dataclasses
    internal: module-level normalization helpers

The DSL is intentionally pure data.  It provides no builder, fluent chaining,
decorator, ``Stage``, or public ``Edge`` authoring surface.

Ownership:
    This module owns only explicit authored node dataclasses.  Shared scalar ref
    validation lives in ``arnold.workflow.refs``; source parsing and diagnostics
    live in ``arnold.workflow.source_compiler``; manifest lowering lives in
    ``arnold.workflow.compiler``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Mapping

from arnold.manifest.manifests import SubpipelineRef, WorkflowPolicy
from arnold.workflow.refs import SourceSpan, canonical_alias, optional_ref, require_ref

PUBLIC_EXPORTS = ("Pipeline", "Step", "Route", "Input", "Output", "Capability")
PROVISIONAL_EXPORTS = ()
INTERNAL_EXPORTS = ()

__all__ = [
    "Capability",
    "INTERNAL_EXPORTS",
    "Input",
    "Output",
    "PUBLIC_EXPORTS",
    "PROVISIONAL_EXPORTS",
    "Pipeline",
    "Route",
    "Step",
]


def _freeze_metadata(value: Mapping[str, Any]) -> Mapping[str, Any]:
    return MappingProxyType({str(key): _freeze_value(subvalue) for key, subvalue in value.items()})


def _freeze_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return _freeze_metadata(value)
    if isinstance(value, list):
        return tuple(_freeze_value(item) for item in value)
    if isinstance(value, tuple):
        return tuple(_freeze_value(item) for item in value)
    return value


@dataclass(frozen=True)
class Input:
    """Public authored input binding for an explicit ``Step`` node."""

    name: str
    value_ref: str | None = None
    schema_hash: str | None = None
    source_span: SourceSpan | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "name", require_ref("input name", self.name))
        object.__setattr__(self, "value_ref", optional_ref("input value_ref", self.value_ref))
        object.__setattr__(self, "metadata", _freeze_metadata(self.metadata))


@dataclass(frozen=True)
class Output:
    """Public authored output declaration for an explicit ``Step`` node."""

    name: str
    schema_hash: str | None = None
    source_span: SourceSpan | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "name", require_ref("output name", self.name))
        object.__setattr__(self, "metadata", _freeze_metadata(self.metadata))


@dataclass(frozen=True)
class Capability:
    """Public authored capability requirement."""

    id: str
    route: str = "default"
    required: bool = True
    source_span: SourceSpan | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", require_ref("capability id", self.id))
        object.__setattr__(self, "route", require_ref("capability route", self.route))
        object.__setattr__(self, "metadata", _freeze_metadata(self.metadata))


@dataclass(frozen=True)
class Route:
    """Public authored control route between explicit ``Step`` nodes."""

    id: str
    source: str
    target: str
    label: str = "default"
    condition_ref: str | None = None
    source_span: SourceSpan | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", require_ref("route id", self.id))
        object.__setattr__(self, "source", require_ref("route source", self.source))
        object.__setattr__(self, "target", require_ref("route target", self.target))
        object.__setattr__(self, "label", require_ref("route label", self.label))
        object.__setattr__(
            self,
            "condition_ref",
            optional_ref("route condition_ref", self.condition_ref),
        )
        object.__setattr__(self, "metadata", _freeze_metadata(self.metadata))


@dataclass(frozen=True)
class Step:
    """Public authored workflow node with an explicit stable ``id``."""

    id: str
    kind: str
    label: str | None = None
    inputs: tuple[Input, ...] = ()
    outputs: tuple[Output, ...] = ()
    capabilities: tuple[Capability, ...] = ()
    policy: WorkflowPolicy | None = None
    source_span: SourceSpan | None = None
    subpipeline: SubpipelineRef | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", require_ref("step id", self.id))
        object.__setattr__(self, "kind", require_ref("step kind", self.kind))
        object.__setattr__(self, "inputs", tuple(self.inputs))
        object.__setattr__(self, "outputs", tuple(self.outputs))
        object.__setattr__(self, "capabilities", tuple(self.capabilities))
        object.__setattr__(self, "metadata", _freeze_metadata(self.metadata))


@dataclass(frozen=True)
class Pipeline:
    """Public explicit-node workflow authoring object."""

    id: str
    version: str
    steps: tuple[Step, ...]
    routes: tuple[Route, ...] = ()
    capabilities: tuple[Capability, ...] = ()
    policy: WorkflowPolicy | None = None
    source_span: SourceSpan | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", canonical_alias(self.id))
        object.__setattr__(self, "steps", tuple(self.steps))
        object.__setattr__(self, "routes", tuple(self.routes))
        object.__setattr__(self, "capabilities", tuple(self.capabilities))
        object.__setattr__(self, "metadata", _freeze_metadata(self.metadata))

    @property
    def entry(self) -> str:
        """Compatibility alias for graph-style callers."""
        return self.steps[0].id if self.steps else ""
