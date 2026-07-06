"""Compile-time contract objects for Python-shaped workflow authoring.

This module declares the neutral data shapes consumed by the future
Python-shaped source compiler. It is intentionally not a runtime, registry,
discovery system, or graph builder: workflow source is parsed statically and
these objects describe imports the compiler may resolve.

Ownership:
    This module owns resolver-facing component and call contract objects.  It
    does not parse source or lower manifests.  Shared scalar ref validation is
    delegated to ``arnold.workflow.refs`` so explicit DSL objects and source
    compiler validation accept and reject the same ref alphabet.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from types import MappingProxyType
from typing import Any, Mapping

from arnold.workflow.refs import require_ref

GRAMMAR_VERSION = "arnold.workflow.authoring.v2"


class ComponentKind(StrEnum):
    """Typed component kinds recognized by the V2 authoring grammar."""

    STEP = "step"
    PROMPT = "prompt"
    POLICY = "policy"
    SCHEMA = "schema"
    SUBFLOW = "subflow"
    WORKFLOW = "workflow"


@dataclass(frozen=True)
class ComponentProvenance:
    """Stable source identity for an imported authoring component."""

    module: str
    qualname: str
    export_name: str | None = None
    call_site_path: str | None = None
    parent_path: str | None = None
    iteration_coordinate: str | None = None
    policy_references: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "module", _require_identifier_path("module", self.module))
        object.__setattr__(self, "qualname", _require_qualname("qualname", self.qualname))
        if self.export_name is not None:
            object.__setattr__(
                self,
                "export_name",
                _require_identifier("export_name", self.export_name),
            )
        if self.call_site_path is not None:
            object.__setattr__(
                self,
                "call_site_path",
                _require_provenance_path("call_site_path", self.call_site_path),
            )
        if self.parent_path is not None:
            object.__setattr__(
                self,
                "parent_path",
                _require_provenance_path("parent_path", self.parent_path),
            )
        if self.iteration_coordinate is not None:
            object.__setattr__(
                self,
                "iteration_coordinate",
                _require_iteration_coordinate("iteration_coordinate", self.iteration_coordinate),
            )
        object.__setattr__(
            self,
            "policy_references",
            tuple(_require_ref("policy_references", value) for value in self.policy_references),
        )

    @property
    def ref(self) -> str:
        """Return the canonical ``module:qualname`` component reference."""

        return f"{self.module}:{self.qualname}"


@dataclass(frozen=True)
class ComponentContract:
    """Base contract for a statically resolvable workflow component export."""

    id: str
    kind: ComponentKind
    provenance: ComponentProvenance
    label: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", _require_ref("id", self.id))
        object.__setattr__(self, "kind", ComponentKind(self.kind))
        object.__setattr__(self, "metadata", _freeze_mapping(self.metadata))


@dataclass(frozen=True, init=False)
class PromptComponent(ComponentContract):
    """Prompt metadata referenced by a statically authored step."""

    template: str | None = None
    parameters: tuple[str, ...] = ()

    def __init__(
        self,
        id: str,
        provenance: ComponentProvenance,
        *,
        label: str | None = None,
        template: str | None = None,
        parameters: tuple[str, ...] = (),
        metadata: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(
            id=id,
            kind=ComponentKind.PROMPT,
            provenance=provenance,
            label=label,
            metadata={} if metadata is None else metadata,
        )
        object.__setattr__(self, "template", template)
        object.__setattr__(self, "parameters", tuple(parameters))


@dataclass(frozen=True, init=False)
class PolicyComponent(ComponentContract):
    """Bounded control, budget, authority, or effect policy metadata."""

    policy_type: str
    config: Mapping[str, Any] = field(default_factory=dict)

    def __init__(
        self,
        id: str,
        provenance: ComponentProvenance,
        *,
        policy_type: str,
        label: str | None = None,
        config: Mapping[str, Any] | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(
            id=id,
            kind=ComponentKind.POLICY,
            provenance=provenance,
            label=label,
            metadata={} if metadata is None else metadata,
        )
        object.__setattr__(self, "policy_type", _require_ref("policy_type", policy_type))
        object.__setattr__(self, "config", _freeze_mapping({} if config is None else config))


@dataclass(frozen=True, init=False)
class SchemaComponent(ComponentContract):
    """Input, output, payload, or resume schema metadata."""

    schema_type: str | None = None
    schema: Mapping[str, Any] = field(default_factory=dict)

    def __init__(
        self,
        id: str,
        provenance: ComponentProvenance,
        *,
        label: str | None = None,
        schema_type: str | None = None,
        schema: Mapping[str, Any] | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(
            id=id,
            kind=ComponentKind.SCHEMA,
            provenance=provenance,
            label=label,
            metadata={} if metadata is None else metadata,
        )
        object.__setattr__(self, "schema_type", schema_type)
        object.__setattr__(self, "schema", _freeze_mapping({} if schema is None else schema))


@dataclass(frozen=True, init=False)
class SubflowComponent(ComponentContract):
    """Nested workflow component metadata for a manifest subpipeline ref."""

    workflow_id: str
    version: str | None = None

    def __init__(
        self,
        id: str,
        provenance: ComponentProvenance,
        *,
        workflow_id: str,
        version: str | None = None,
        label: str | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(
            id=id,
            kind=ComponentKind.SUBFLOW,
            provenance=provenance,
            label=label,
            metadata={} if metadata is None else metadata,
        )
        object.__setattr__(self, "workflow_id", _require_ref("workflow_id", workflow_id))
        object.__setattr__(self, "version", version)

    def __call__(
        self,
        *,
        id: str,
        manifest_hash: str,
        alias: str | None = None,
        metadata: Mapping[str, Any] | None = None,
        **_inputs: Any,
    ) -> "AuthoredSubflow":
        """Return compile-time subflow-call data; this does not execute a workflow."""

        return AuthoredSubflow(
            id=id,
            component=self,
            manifest_hash=manifest_hash,
            alias=alias,
            metadata={} if metadata is None else metadata,
        )


@dataclass(frozen=True)
class AuthoredStep:
    """Compile-time step call captured from a Python-shaped workflow body."""

    id: str
    component: "StepComponent"
    prompt: PromptComponent | None = None
    policy: PolicyComponent | None = None
    input_schema: SchemaComponent | None = None
    output_schema: SchemaComponent | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", _require_ref("id", self.id))
        object.__setattr__(self, "metadata", _freeze_mapping(self.metadata))


@dataclass(frozen=True)
class AuthoredSubflow:
    """Compile-time subflow call captured from a Python-shaped workflow body."""

    id: str
    component: "SubflowComponent"
    manifest_hash: str
    alias: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", _require_ref("id", self.id))
        object.__setattr__(self, "manifest_hash", _require_ref("manifest_hash", self.manifest_hash))
        object.__setattr__(self, "alias", None if self.alias is None else _require_ref("alias", self.alias))
        object.__setattr__(self, "metadata", _freeze_mapping(self.metadata))


@dataclass(frozen=True, init=False)
class StepComponent(ComponentContract):
    """Callable-shaped component that lowers to one workflow step."""

    step_type: str = "agent"
    prompt: PromptComponent | None = None
    policy: PolicyComponent | None = None
    input_schema: SchemaComponent | None = None
    output_schema: SchemaComponent | None = None

    def __init__(
        self,
        id: str,
        provenance: ComponentProvenance,
        *,
        label: str | None = None,
        step_type: str = "agent",
        prompt: PromptComponent | None = None,
        policy: PolicyComponent | None = None,
        input_schema: SchemaComponent | None = None,
        output_schema: SchemaComponent | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(
            id=id,
            kind=ComponentKind.STEP,
            provenance=provenance,
            label=label,
            metadata={} if metadata is None else metadata,
        )
        object.__setattr__(self, "step_type", _require_ref("step_type", step_type))
        object.__setattr__(self, "prompt", prompt)
        object.__setattr__(self, "policy", policy)
        object.__setattr__(self, "input_schema", input_schema)
        object.__setattr__(self, "output_schema", output_schema)

    def __call__(
        self,
        *,
        id: str,
        prompt: PromptComponent | None = None,
        policy: PolicyComponent | None = None,
        input_schema: SchemaComponent | None = None,
        output_schema: SchemaComponent | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> AuthoredStep:
        """Return compile-time step-call data; this does not execute a step."""

        return AuthoredStep(
            id=id,
            component=self,
            prompt=self.prompt if prompt is None else prompt,
            policy=self.policy if policy is None else policy,
            input_schema=self.input_schema if input_schema is None else input_schema,
            output_schema=self.output_schema if output_schema is None else output_schema,
            metadata={} if metadata is None else metadata,
        )


@dataclass(frozen=True)
class IntrinsicDeclaration:
    """Reserved compiler intrinsic name imported by workflow source."""

    name: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "name", _require_identifier("name", self.name))

    def __call__(self, *_args: Any, **_kwargs: Any) -> None:
        raise RuntimeError(
            f"{self.name!r} is a compile-time workflow intrinsic and cannot be executed"
        )


def _freeze_mapping(value: Mapping[str, Any]) -> Mapping[str, Any]:
    return MappingProxyType({str(key): _freeze_value(subvalue) for key, subvalue in value.items()})


def _freeze_value(value: Any) -> Any:
    if getattr(value, "__arnold_preserve_mapping__", False):
        return value
    if isinstance(value, Mapping):
        return _freeze_mapping(value)
    if isinstance(value, list):
        return tuple(_freeze_value(item) for item in value)
    if isinstance(value, tuple):
        return tuple(_freeze_value(item) for item in value)
    return value


def _require_identifier(name: str, value: str) -> str:
    if not isinstance(value, str) or not value.isidentifier():
        raise ValueError(f"{name} must be a Python identifier")
    return value


def _require_identifier_path(name: str, value: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{name} must be a non-empty dotted path")
    for segment in value.split("."):
        _require_identifier(name, segment)
    return value


def _require_qualname(name: str, value: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{name} must be a non-empty qualname")
    for segment in value.split("."):
        _require_identifier(name, segment)
    return value


def _require_ref(name: str, value: str) -> str:
    return require_ref(name, value)


def _require_provenance_path(name: str, value: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{name} must be a non-empty authored path")
    for segment in value.split("/"):
        if not segment:
            raise ValueError(f"{name} must not contain empty path segments")
        base = segment.split("[", 1)[0]
        _require_ref(name, base)
    return value


def _require_iteration_coordinate(name: str, value: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{name} must be a non-empty iteration coordinate")
    if not (value.startswith("[") and value.endswith("]")):
        raise ValueError(f"{name} must use bracket notation")
    return value


workflow = IntrinsicDeclaration("workflow")
loop = IntrinsicDeclaration("loop")
halt = IntrinsicDeclaration("halt")
suspend = IntrinsicDeclaration("suspend")
transition = IntrinsicDeclaration("transition")

RESERVED_INTRINSIC_NAMES = (
    workflow.name,
    loop.name,
    halt.name,
    suspend.name,
    transition.name,
)
RESERVED_STEP_CALL_KEYWORDS = ("id", "policy", "policies", "schema")
RESERVED_SUBFLOW_CALL_KEYWORDS = ("id", "manifest_hash", "alias")
RESERVED_INTRINSIC_CALL_KEYWORDS = MappingProxyType(
    {
        "loop": ("policy", "reentry_id"),
        "halt": ("id", "trigger_ref", "target_ref", "payload_schema_hash", "policy_ref"),
        "suspend": (
            "route_id",
            "capability_id",
            "reentry_id",
            "payload_schema_hash",
            "resume_schema_hash",
            "resume_schema_ref",
            "resume_payload_ref",
        ),
        "transition": ("id", "type", "trigger_ref", "target_ref", "payload_schema_hash", "policy_ref"),
    }
)

__all__ = [
    "AuthoredSubflow",
    "AuthoredStep",
    "ComponentContract",
    "ComponentKind",
    "ComponentProvenance",
    "GRAMMAR_VERSION",
    "IntrinsicDeclaration",
    "PolicyComponent",
    "PromptComponent",
    "RESERVED_INTRINSIC_CALL_KEYWORDS",
    "RESERVED_INTRINSIC_NAMES",
    "RESERVED_SUBFLOW_CALL_KEYWORDS",
    "RESERVED_STEP_CALL_KEYWORDS",
    "SchemaComponent",
    "StepComponent",
    "SubflowComponent",
    "halt",
    "loop",
    "suspend",
    "transition",
    "workflow",
]
