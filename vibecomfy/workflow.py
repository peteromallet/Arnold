from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import TYPE_CHECKING, Any

from vibecomfy.handles import Handle
from vibecomfy.porting import helpers as porting_helpers
from vibecomfy.porting.widget_aliases import apply_positional_widget_aliases

if TYPE_CHECKING:
    from vibecomfy.schema.provider import SchemaProvider


OPAQUE_COMPONENT_CLASS_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)


@dataclass(slots=True)
class WorkflowSource:
    id: str
    path: str | None = None
    source_type: str = "unknown"
    provenance: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class WorkflowRequirements:
    models: list[str] = field(default_factory=list)
    custom_nodes: list[str] = field(default_factory=list)
    missing_models: list[str] = field(default_factory=list)
    missing_nodes: list[str] = field(default_factory=list)
    unsupported: list[str] = field(default_factory=list)


@dataclass(slots=True)
class VibeNode:
    id: str
    class_type: str
    pack: str | None = None
    inputs: dict[str, Any] = field(default_factory=dict)
    widgets: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class VibeEdge:
    from_node: str
    from_output: str
    to_node: str
    to_input: str


@dataclass(slots=True)
class VibeInput:
    name: str
    node_id: str
    field: str
    value: Any = None
    type: str | None = None
    default: Any = None
    required: bool = False
    range: Any = None
    aliases: tuple[str, ...] = field(default_factory=tuple)
    media_semantics: str | None = None

    @property
    def media(self) -> str | None:
        return self.media_semantics

    @media.setter
    def media(self, value: str | None) -> None:
        self.media_semantics = value


@dataclass(slots=True)
class VibeOutput:
    node_id: str
    output_type: str
    name: str | None = None
    artifact_kind: str | None = None
    mime_type: str | None = None
    filename_prefix: str | None = None
    expected_cardinality: str | int | None = None


@dataclass(slots=True)
class ValidationIssue:
    code: str
    message: str
    severity: str = "error"
    detail: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ValidationReport:
    ok: bool
    issues: list[ValidationIssue] = field(default_factory=list)


@dataclass
class VibeWorkflow:
    id: str
    source: WorkflowSource
    nodes: dict[str, VibeNode] = field(default_factory=dict)
    edges: list[VibeEdge] = field(default_factory=list)
    inputs: dict[str, VibeInput] = field(default_factory=dict)
    outputs: list[VibeOutput] = field(default_factory=list)
    requirements: WorkflowRequirements = field(default_factory=WorkflowRequirements)
    metadata: dict[str, Any] = field(default_factory=dict)

    def set_prompt(self, value: str) -> "VibeWorkflow":
        return self.set_input("prompt", value)

    def set_seed(self, value: int) -> "VibeWorkflow":
        return self.set_input("seed", int(value))

    def set_steps(self, value: int) -> "VibeWorkflow":
        return self.set_input("steps", int(value))

    def set_model(self, value: str) -> "VibeWorkflow":
        return self.set_input("model", value)

    def finalize_metadata(self) -> "VibeWorkflow":
        from vibecomfy.metadata import OUTPUT_NODE_NAMES, _infer_requirements, _register_common_inputs

        self.inputs.clear()
        self.outputs.clear()
        for node_id, node in self.nodes.items():
            _register_common_inputs(self, node_id, node)
            if node.class_type in OUTPUT_NODE_NAMES:
                self.outputs.append(VibeOutput(node_id=node_id, output_type=node.class_type))
        self.outputs.sort(key=lambda o: (int(o.node_id) if o.node_id.isdigit() else (1 << 30), o.node_id))
        self.requirements = _infer_requirements(self)
        return self

    def finalize(
        self,
        public_inputs: dict[str, Any],
        *,
        metadata: dict[str, Any] | None = None,
        output_node: Any = None,
        output_kind: str | None = None,
        **bind_kwargs: Any,
    ) -> "VibeWorkflow":
        """Finalize ready-template public inputs and output binding.

        ``metadata`` is optional for the v2.5 method form; when omitted, the
        workflow's current metadata is used. The legacy free function remains
        available in ``vibecomfy.templates.finalize``.
        """
        from vibecomfy.templates import _finalize_impl

        return _finalize_impl(
            self,
            public_inputs,
            dict(self.metadata if metadata is None else metadata),
            output_node=output_node,
            output_kind=output_kind,
            **bind_kwargs,
        )

    def register_input(
        self,
        name: str,
        node_id: str,
        field: str,
        value: Any = None,
        *,
        type: str | None = None,
        default: Any = None,
        required: bool = False,
        range: Any = None,
        aliases: list[str] | tuple[str, ...] | None = None,
        media_semantics: str | None = None,
        media: str | None = None,
    ) -> "VibeWorkflow":
        if media_semantics is not None and media is not None and media_semantics != media:
            raise ValueError(
                f"register_input({name!r}): media_semantics and legacy media "
                "must match when both are provided"
            )
        resolved_media_semantics = media_semantics if media_semantics is not None else media
        alias_tuple = _normalize_input_aliases(aliases)
        self._validate_input_aliases(name, alias_tuple)
        self._validate_input_target(name, node_id, field)
        self.inputs[name] = VibeInput(
            name=name,
            node_id=str(node_id),
            field=field,
            value=value,
            type=type,
            default=value if default is None else default,
            required=required,
            range=range,
            aliases=alias_tuple,
            media_semantics=resolved_media_semantics,
        )
        return self

    def set_input(self, name: str, value: Any) -> "VibeWorkflow":
        target = self._resolve_input(name)
        if target and target.node_id in self.nodes:
            node = self.nodes[target.node_id]
            if target.field in node.inputs:
                node.inputs[target.field] = value
            else:
                node.widgets[target.field] = value
            target.value = value
            return self

        self.metadata.setdefault("unbound_inputs", {})[name] = value
        return self

    def _resolve_input(self, name: str) -> VibeInput | None:
        if name in self.inputs:
            return self.inputs[name]
        matches = [item for item in self.inputs.values() if name in item.aliases]
        if len(matches) > 1:
            raise ValueError(f"Input alias {name!r} is ambiguous in workflow {self.id!r}")
        return matches[0] if matches else None

    def _validate_input_aliases(self, name: str, aliases: tuple[str, ...]) -> None:
        if len(set(aliases)) != len(aliases):
            raise ValueError(f"register_input({name!r}): duplicate aliases are not allowed")
        if name in aliases:
            raise ValueError(f"register_input({name!r}): alias cannot equal its primary input name")
        existing_primary_names = {existing_name for existing_name in self.inputs if existing_name != name}
        if name in {
            alias
            for existing_name, item in self.inputs.items()
            if existing_name != name
            for alias in item.aliases
        }:
            raise ValueError(f"register_input({name!r}): primary input name conflicts with an existing alias")
        primary_conflicts = existing_primary_names.intersection(aliases)
        if primary_conflicts:
            conflict = sorted(primary_conflicts)[0]
            raise ValueError(f"register_input({name!r}): alias {conflict!r} conflicts with an existing primary input")
        existing_aliases = {
            alias
            for existing_name, item in self.inputs.items()
            if existing_name != name
            for alias in item.aliases
        }
        alias_conflicts = existing_aliases.intersection(aliases)
        if alias_conflicts:
            conflict = sorted(alias_conflicts)[0]
            raise ValueError(f"register_input({name!r}): alias {conflict!r} conflicts with an existing alias")

    def _validate_input_target(self, name: str, node_id: str, field: str) -> None:
        node_key = str(node_id)
        if node_key not in self.nodes:
            raise ValueError(
                f"register_input({name!r}): target node {node_key!r} does not exist "
                f"in workflow {self.id!r}"
            )
        node = self.nodes[node_key]
        if field not in node.inputs and field not in node.widgets:
            raise ValueError(
                f"register_input({name!r}): field {field!r} not found in "
                f"node {node_key!r} ({node.class_type}) inputs or widgets"
            )

    def add_node(self, class_type: str, **inputs: Any) -> VibeNode:
        node_id = self._next_node_id()
        node = VibeNode(id=node_id, class_type=class_type, inputs=dict(inputs))
        self.nodes[node_id] = node
        return node

    def node(self, class_type: str, **kwargs: Any) -> "_NodeBuilder":
        node = self.add_node(class_type)
        for key, value in kwargs.items():
            if isinstance(value, Handle):
                self.connect(value, f"{node.id}.{key}")
            else:
                node.inputs[key] = value
        return _NodeBuilder(workflow=self, node=node)

    def connect(self, from_ref: str | Handle, to_ref: str) -> "VibeWorkflow":
        if isinstance(from_ref, Handle):
            from_ref = str(from_ref)
        from_node, from_output = from_ref.split(".", 1)
        to_node, to_input = to_ref.split(".", 1)
        self.edges.append(VibeEdge(from_node, from_output, to_node, to_input))
        return self

    def disconnect(self, to_ref: str) -> bool:
        """Remove the edge whose target matches ``to_ref`` (``"node_id.input_name"``).

        Returns True if an edge was removed, False otherwise.
        """
        to_node, to_input = to_ref.split(".", 1)
        for index, edge in enumerate(self.edges):
            if edge.to_node == to_node and edge.to_input == to_input:
                del self.edges[index]
                return True
        return False

    def remove_node(self, node_id: str) -> "VibeWorkflow":
        """Remove a node and all edges attached to it."""
        node_id = str(node_id)
        self.nodes.pop(node_id, None)
        self.edges = [
            edge
            for edge in self.edges
            if str(edge.from_node) != node_id and str(edge.to_node) != node_id
        ]
        self.inputs = {
            name: target
            for name, target in self.inputs.items()
            if str(target.node_id) != node_id
        }
        self.outputs = [
            output
            for output in self.outputs
            if str(output.node_id) != node_id
        ]
        return self

    def replace_edge(self, to_ref: str, new_from_ref: str) -> "VibeWorkflow":
        """Redirect the edge feeding ``to_ref`` so it now originates from ``new_from_ref``.

        Disconnects the existing edge (if any) and connects the new source. Returns
        ``self`` for chaining.
        """
        self.disconnect(to_ref)
        return self.connect(new_from_ref, to_ref)

    def validate(self, schema_provider: SchemaProvider | None = None) -> ValidationReport:
        issues: list[ValidationIssue] = []
        if not self.nodes:
            issues.append(ValidationIssue("empty_workflow", "Workflow contains no nodes."))
        for node_id, node in self.nodes.items():
            if OPAQUE_COMPONENT_CLASS_RE.match(node.class_type):
                issues.append(
                    ValidationIssue(
                        "opaque_component_class_type",
                        (
                            f"Node {node_id} has opaque component class_type "
                            f"{node.class_type!r}; inline or replace the subgraph before runtime."
                        ),
                        severity="warning",
                        detail={"node_id": str(node_id), "class_type": node.class_type},
                    )
                )
            if node.class_type == "VAELoaderKJ":
                vae_name = node.inputs.get("vae_name") or node.inputs.get("widget_0")
                if isinstance(vae_name, str):
                    normalized_vae_name = vae_name.lower().replace("\\", "/")
                    if "ltx" in normalized_vae_name and "audio" in normalized_vae_name:
                        issues.append(
                            ValidationIssue(
                                "ltx_audio_vae_wrong_loader",
                                (
                                    f"Node {node_id} loads LTX audio VAE {vae_name!r} with VAELoaderKJ; "
                                    "use LTXVAudioVAELoader and stage the file under checkpoints."
                                ),
                                detail={"node_id": str(node_id), "class_type": node.class_type, "vae_name": vae_name},
                            )
                        )
        for edge in self.edges:
            if edge.from_node not in self.nodes:
                issues.append(ValidationIssue("missing_edge_source", f"Missing source node {edge.from_node}."))
            if edge.to_node not in self.nodes:
                issues.append(ValidationIssue("missing_edge_target", f"Missing target node {edge.to_node}."))
        if schema_provider is not None:
            from vibecomfy.schema.validate import validate_against_schema, validate_api_link_shapes

            issues.extend(validate_against_schema(self, schema_provider))
            try:
                api = self.compile(backend="api")
            except Exception as exc:
                issues.append(ValidationIssue("api_compile_failed", str(exc), severity="warning"))
            else:
                issues.extend(validate_api_link_shapes(api, schema_provider))
        return ValidationReport(ok=not any(issue.severity == "error" for issue in issues), issues=issues)

    def runtime_nodes(self) -> dict[str, VibeNode]:
        return porting_helpers.helper_stripped_nodes(self.nodes)

    def runtime_class_types(self) -> list[str]:
        return porting_helpers.helper_stripped_class_types(self.nodes)

    def helper_diagnostics(self) -> list[ValidationIssue]:
        return [
            ValidationIssue(
                diagnostic.code,
                diagnostic.message,
                severity=diagnostic.severity,
                detail={
                    **diagnostic.detail,
                    "node_id": diagnostic.node_id,
                    "class_type": diagnostic.class_type,
                },
            )
            for diagnostic in porting_helpers.collect_helper_diagnostics(self.nodes, self.edges)
        ]

    def compile(self, backend: str = "api") -> dict[str, Any]:
        if backend == "graphbuilder":
            return self._compile_graphbuilder()
        if backend != "api":
            raise ValueError(f"Unknown compile backend: {backend}")
        broadcast_sources = porting_helpers.collect_broadcast_sources(self.nodes, self.edges)
        api: dict[str, Any] = {}
        for node_id, node in self.nodes.items():
            if _is_ui_only_node(node):
                continue
            inputs = _rewrite_broadcast_links(_compile_node_inputs(node), self.nodes, broadcast_sources)
            api[str(node_id)] = {"class_type": node.class_type, "inputs": inputs}
        for edge in self.edges:
            if str(edge.to_node) not in api:
                continue
            edge_source = _resolve_edge_source(edge, self.nodes, broadcast_sources)
            if edge_source is None:
                continue
            if str(edge_source[0]) in self.nodes and str(edge_source[0]) not in api:
                continue
            api[str(edge.to_node)]["inputs"][edge.to_input] = edge_source
        return api

    def id_map(self) -> dict[str, str]:
        """Return debug mappings from source/symbolic ids to current node ids."""
        mapping: dict[str, str] = {}
        raw = self.metadata.get("id_map")
        if isinstance(raw, dict):
            mapping.update({str(key): str(value) for key, value in raw.items()})
        for node_id, node in self.nodes.items():
            source_id = node.metadata.get("source_id")
            if source_id is not None:
                mapping[str(source_id)] = str(node_id)
        return dict(sorted(mapping.items()))

    def _compile_graphbuilder(self) -> dict[str, Any]:
        try:
            from comfy_execution.graph_utils import GraphBuilder
        except ImportError as exc:
            raise RuntimeError("GraphBuilder backend requires the installed HiddenSwitch ComfyUI runtime.") from exc

        broadcast_sources = porting_helpers.collect_broadcast_sources(self.nodes, self.edges)
        edge_inputs: dict[str, dict[str, Any]] = {}
        for edge in self.edges:
            edge_source = _resolve_edge_source(edge, self.nodes, broadcast_sources)
            if edge_source is None:
                continue
            edge_inputs.setdefault(str(edge.to_node), {})[edge.to_input] = edge_source

        builder = GraphBuilder(prefix="")
        for node_id, node in self.nodes.items():
            if _is_ui_only_node(node):
                continue
            inputs = _rewrite_broadcast_links(_compile_node_inputs(node), self.nodes, broadcast_sources)
            inputs.update(edge_inputs.get(str(node_id), {}))
            builder.node(node.class_type, id=str(node_id), **inputs)
        return builder.finalize()

    def _next_node_id(self) -> str:
        numeric = [int(node_id) for node_id in self.nodes if str(node_id).isdigit()]
        return str(max(numeric, default=0) + 1)


@dataclass(frozen=True)
class _NodeBuilder:
    workflow: VibeWorkflow
    node: VibeNode

    @property
    def id(self) -> str:
        return self.node.id

    def out(self, slot: int | str) -> Handle:
        try:
            output_slot = int(str(slot))
        except ValueError as exc:
            output_names = self.node.metadata.get("output_names")
            if isinstance(output_names, (list, tuple)) and slot in output_names:
                return Handle(node_id=self.node.id, output_slot=output_names.index(slot), name=str(slot))
            if isinstance(output_names, (list, tuple)):
                normalized_slot = str(slot).upper()
                normalized_names = [str(name).upper() for name in output_names]
                if normalized_slot in normalized_names:
                    return Handle(
                        node_id=self.node.id,
                        output_slot=normalized_names.index(normalized_slot),
                        name=str(slot),
                    )
            raise NotImplementedError(
                f"Named output {slot!r} is not registered for {self.node.class_type} node {self.node.id}; "
                "register output_names metadata or pass an integer slot. "
                "Full named-output lookup awaits MP-6 schema integration."
            ) from exc
        return Handle(node_id=self.node.id, output_slot=output_slot)


def _compile_node_inputs(node: VibeNode) -> dict[str, Any]:
    inputs = dict(node.widgets)
    inputs.update(node.inputs)
    _apply_positional_widget_aliases(inputs, node.class_type)
    _drop_unused_positional_aliases(inputs)
    return {
        key: value
        for key, value in inputs.items()
        if not _is_ui_only_prompt_input(key, value)
    }


def _normalize_input_aliases(aliases: list[str] | tuple[str, ...] | None) -> tuple[str, ...]:
    if aliases is None:
        return ()
    return tuple(str(alias) for alias in aliases)


def _is_ui_only_prompt_input(key: str, value: Any) -> bool:
    if value is None:
        return True
    if key == "control_after_generate":
        return True
    if key == "add_noise_to_samples" and value == "":
        return True
    if key in {"videopreview", "preview", "preview_image"} and isinstance(value, dict):
        return True
    return False


def _is_ui_only_node(node: VibeNode) -> bool:
    return porting_helpers.is_helper_class_type(node.class_type)


def _broadcast_name(node: VibeNode) -> str | None:
    return porting_helpers.broadcast_name(node)


def _first_link_input(inputs: dict[str, Any]) -> list[Any] | None:
    return porting_helpers.first_link_input(inputs)


def _rewrite_broadcast_links(
    inputs: dict[str, Any],
    nodes: dict[str, VibeNode],
    broadcast_sources: dict[str, list[Any]],
) -> dict[str, Any]:
    return {
        key: _resolve_link_value(value, nodes, broadcast_sources)
        for key, value in inputs.items()
    }


def _resolve_edge_source(
    edge: VibeEdge,
    nodes: dict[str, VibeNode],
    broadcast_sources: dict[str, list[Any]],
) -> list[Any] | None:
    source_node = nodes.get(str(edge.from_node))
    if source_node is None:
        return [str(edge.from_node), int(edge.from_output)]
    if source_node.class_type == "GetNode":
        name = _broadcast_name(source_node)
        if name is None:
            return None
        return broadcast_sources.get(name)
    if source_node.class_type == "SetNode":
        name = _broadcast_name(source_node)
        if name is None:
            return None
        return broadcast_sources.get(name)
    if _is_ui_only_node(source_node):
        return None
    return [str(edge.from_node), int(edge.from_output)]


def _resolve_link_value(
    value: Any,
    nodes: dict[str, VibeNode],
    broadcast_sources: dict[str, list[Any]],
) -> Any:
    if not _is_api_link(value):
        return value
    source_node = nodes.get(str(value[0]))
    if source_node is None or source_node.class_type not in {"GetNode", "SetNode"}:
        return value
    name = _broadcast_name(source_node)
    if name is None:
        return value
    return broadcast_sources.get(name, value)


def _is_api_link(value: Any) -> bool:
    return porting_helpers.is_api_link(value)


def _apply_positional_widget_aliases(inputs: dict[str, Any], class_type: str) -> None:
    apply_positional_widget_aliases(inputs, class_type)


def _drop_unused_positional_aliases(inputs: dict[str, Any]) -> None:
    for key in list(inputs):
        if key.startswith("unused_"):
            inputs.pop(key, None)
