from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from vibecomfy.schema.provider import SchemaProvider


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


@dataclass(slots=True)
class VibeOutput:
    node_id: str
    output_type: str
    name: str | None = None


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
        self.requirements = _infer_requirements(self)
        return self

    def set_input(self, name: str, value: Any) -> "VibeWorkflow":
        target = self.inputs.get(name)
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

    def add_node(self, class_type: str, **inputs: Any) -> VibeNode:
        node_id = self._next_node_id()
        node = VibeNode(id=node_id, class_type=class_type, inputs=dict(inputs))
        self.nodes[node_id] = node
        return node

    def connect(self, from_ref: str, to_ref: str) -> "VibeWorkflow":
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
        for edge in self.edges:
            if edge.from_node not in self.nodes:
                issues.append(ValidationIssue("missing_edge_source", f"Missing source node {edge.from_node}."))
            if edge.to_node not in self.nodes:
                issues.append(ValidationIssue("missing_edge_target", f"Missing target node {edge.to_node}."))
        if schema_provider is not None:
            from vibecomfy.schema.validate import validate_against_schema

            issues.extend(validate_against_schema(self, schema_provider))
        return ValidationReport(ok=not any(issue.severity == "error" for issue in issues), issues=issues)

    def compile(self, backend: str = "api") -> dict[str, Any]:
        if backend == "graphbuilder":
            return self._compile_graphbuilder()
        if backend != "api":
            raise ValueError(f"Unknown compile backend: {backend}")
        api: dict[str, Any] = {}
        for node_id, node in self.nodes.items():
            inputs = dict(node.inputs)
            inputs.update(node.widgets)
            api[str(node_id)] = {"class_type": node.class_type, "inputs": inputs}
        for edge in self.edges:
            api[str(edge.to_node)]["inputs"][edge.to_input] = [str(edge.from_node), int(edge.from_output)]
        return api

    def _compile_graphbuilder(self) -> dict[str, Any]:
        try:
            from comfy_execution.graph_utils import GraphBuilder
        except ImportError as exc:
            raise RuntimeError("GraphBuilder backend requires the installed HiddenSwitch ComfyUI runtime.") from exc

        edge_inputs: dict[str, dict[str, Any]] = {}
        for edge in self.edges:
            edge_inputs.setdefault(str(edge.to_node), {})[edge.to_input] = [str(edge.from_node), int(edge.from_output)]

        builder = GraphBuilder(prefix="")
        for node_id, node in self.nodes.items():
            inputs = dict(node.inputs)
            inputs.update(node.widgets)
            inputs.update(edge_inputs.get(str(node_id), {}))
            builder.node(node.class_type, id=str(node_id), **inputs)
        return builder.finalize()

    def _next_node_id(self) -> str:
        numeric = [int(node_id) for node_id in self.nodes if str(node_id).isdigit()]
        return str(max(numeric, default=0) + 1)
