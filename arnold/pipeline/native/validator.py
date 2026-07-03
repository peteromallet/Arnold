"""Routing-purity validation for native pipeline decision bodies.

This validator is intentionally conservative: it inspects only native
decision callables plus static ``NativeProgram.routing_topology`` metadata.
Phase bodies remain unconstrained so live work can be moved into steps while
decisions route on recorded outputs.
"""

from __future__ import annotations

import ast
import inspect
import textwrap
from dataclasses import dataclass, field
from types import ModuleType
from typing import Any, Callable, Mapping

from arnold.pipeline.native.ir import NativeProgram

MOVE_WORK_RECOMMENDATION = (
    "Move live work into a step and route on recorded outputs."
)

_ROUTING_TOPOLOGY_COLLECTION_KEYS = ("routes", "edges", "bindings")
_ROUTING_TOPOLOGY_NODE_KEYS = ("nodes", "stages", "steps")
_TERMINAL_TARGETS = frozenset({"halt"})
_ROUTING_OWNED_STATE_KEYS = frozenset(
    {
        "__control_override__",
        "__override_route__",
        "branch",
        "branches",
        "current_state",
        "decision",
        "next_stage",
        "next_step",
        "override_action",
        "override_route",
        "route",
        "routes",
        "workflow_transition",
    }
)
_MUTATING_METHODS = frozenset(
    {
        "__setitem__",
        "clear",
        "pop",
        "popitem",
        "setdefault",
        "update",
    }
)

_NONDETERMINISTIC_PREFIXES = (
    "datetime.date.today",
    "datetime.datetime.now",
    "datetime.datetime.utcnow",
    "os.urandom",
    "random.",
    "secrets.",
    "time.monotonic",
    "time.perf_counter",
    "time.time",
    "uuid.uuid1",
    "uuid.uuid4",
)
_IO_PREFIXES = (
    "builtins.open",
    "io.open",
    "os.listdir",
    "os.makedirs",
    "os.mkdir",
    "os.remove",
    "os.rename",
    "os.replace",
    "os.rmdir",
    "os.unlink",
    "pathlib.Path.mkdir",
    "pathlib.Path.open",
    "pathlib.Path.read_bytes",
    "pathlib.Path.read_text",
    "pathlib.Path.rename",
    "pathlib.Path.replace",
    "pathlib.Path.rmdir",
    "pathlib.Path.touch",
    "pathlib.Path.unlink",
    "pathlib.Path.write_bytes",
    "pathlib.Path.write_text",
    "shutil.",
)
_NETWORK_PREFIXES = (
    "aiohttp.",
    "http.client.",
    "httpx.",
    "requests.",
    "socket.",
    "urllib.request.",
    "urllib3.",
)
_SUBPROCESS_PREFIXES = (
    "os.popen",
    "os.system",
    "subprocess.",
)
_DYNAMIC_PREFIXES = (
    "__import__",
    "builtins.__import__",
    "builtins.compile",
    "builtins.eval",
    "builtins.exec",
    "getattr",
    "globals",
    "importlib.",
    "locals",
    "setattr",
    "vars",
)


@dataclass(frozen=True)
class RoutingPurityDiagnostic:
    """Structured routing-purity defect."""

    code: str
    message: str
    program: str | None = None
    decision: str | None = None
    source_file: str | None = None
    line: int | None = None
    column: int | None = None
    topology_path: str | None = None
    recommendation: str = MOVE_WORK_RECOMMENDATION


@dataclass
class RoutingPurityReport:
    """Validation result for routing purity."""

    diagnostics: list[RoutingPurityDiagnostic] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.diagnostics

    def add(self, diagnostic: RoutingPurityDiagnostic) -> None:
        self.diagnostics.append(diagnostic)

    def extend(self, diagnostics: list[RoutingPurityDiagnostic]) -> None:
        self.diagnostics.extend(diagnostics)


def validate_decision_body(
    fn: Callable[..., Any],
    *,
    program_name: str | None = None,
    decision_name: str | None = None,
) -> list[RoutingPurityDiagnostic]:
    """Return routing-purity diagnostics for a single decision callable."""
    decision_label = decision_name or getattr(fn, "__decision_name__", fn.__name__)
    source_file = getattr(fn, "__decision_source_file__", None) or inspect.getsourcefile(fn)
    first_lineno = getattr(fn, "__decision_first_lineno__", None)

    try:
        source = inspect.getsource(fn)
    except (OSError, TypeError) as exc:
        return [
            RoutingPurityDiagnostic(
                code="routing.source_unavailable",
                message=(
                    f"Decision '{decision_label}' cannot be statically inspected: "
                    f"{type(exc).__name__}: {exc}"
                ),
                program=program_name,
                decision=decision_label,
                source_file=str(source_file) if source_file else None,
                line=first_lineno,
                recommendation=MOVE_WORK_RECOMMENDATION,
            )
        ]

    tree = ast.parse(textwrap.dedent(source))
    func_def = _find_function_def(tree, fn.__name__)
    if func_def is None:
        return [
            RoutingPurityDiagnostic(
                code="routing.source_missing_function",
                message=(
                    f"Decision '{decision_label}' source could not be matched to a "
                    "function definition."
                ),
                program=program_name,
                decision=decision_label,
                source_file=str(source_file) if source_file else None,
                line=first_lineno,
            )
        ]

    visitor = _DecisionPurityVisitor(
        fn=fn,
        program_name=program_name,
        decision_name=decision_label,
        source_file=str(source_file) if source_file else None,
        base_lineno=first_lineno or 1,
    )
    visitor.visit(func_def)
    return visitor.diagnostics


def validate_pipeline_purity(program: NativeProgram) -> RoutingPurityReport:
    """Validate a native program tree for routing purity."""
    report = RoutingPurityReport()
    _validate_pipeline_purity(program, report, seen=set())
    return report


def _validate_pipeline_purity(
    program: NativeProgram,
    report: RoutingPurityReport,
    *,
    seen: set[int],
) -> None:
    marker = id(program)
    if marker in seen:
        return
    seen.add(marker)

    seen_decisions: set[int] = set()
    for instr in program.instructions:
        if instr.op == "decision" and instr.func is not None:
            fn_marker = id(instr.func)
            if fn_marker not in seen_decisions:
                report.extend(
                    validate_decision_body(
                        instr.func,
                        program_name=program.name,
                        decision_name=instr.name or getattr(instr.func, "__name__", "decision"),
                    )
                )
                seen_decisions.add(fn_marker)
        if instr.op == "subpipeline" and isinstance(instr.subprogram, NativeProgram):
            _validate_pipeline_purity(instr.subprogram, report, seen=seen)

    report.extend(_validate_routing_topology(program))


def _validate_routing_topology(program: NativeProgram) -> list[RoutingPurityDiagnostic]:
    topology = program.routing_topology
    if not topology:
        return []
    if not isinstance(topology, dict):
        return [
            RoutingPurityDiagnostic(
                code="routing.topology_invalid_type",
                message="routing_topology must be a dict of static routing metadata.",
                program=program.name,
                topology_path="routing_topology",
                recommendation="Record static route metadata as a plain dict of labels and targets.",
            )
        ]

    known_nodes = {instr.name for instr in program.instructions if instr.name}
    known_nodes.update(_extract_topology_nodes(topology))
    diagnostics: list[RoutingPurityDiagnostic] = []

    for collection_key in _ROUTING_TOPOLOGY_COLLECTION_KEYS:
        collection = topology.get(collection_key)
        if collection is None:
            continue
        path = f"routing_topology.{collection_key}"
        if not isinstance(collection, list):
            diagnostics.append(
                RoutingPurityDiagnostic(
                    code="routing.topology_invalid_collection",
                    message=f"{path} must be a list of static route records.",
                    program=program.name,
                    topology_path=path,
                    recommendation="Store static route records in a list of plain dicts.",
                )
            )
            continue

        for index, record in enumerate(collection):
            record_path = f"{path}[{index}]"
            if not isinstance(record, Mapping):
                diagnostics.append(
                    RoutingPurityDiagnostic(
                        code="routing.topology_invalid_record",
                        message=f"{record_path} must be a dict.",
                        program=program.name,
                        topology_path=record_path,
                    )
                )
                continue

            source = _record_value(record, "source", "source_step", "from")
            label = _record_value(record, "label", "route", "edge")
            target = _record_value(record, "target", "target_step", "to")
            condition_ref = _record_value(record, "condition_ref", "condition")

            if not isinstance(source, str) or not source:
                diagnostics.append(
                    RoutingPurityDiagnostic(
                        code="routing.topology_invalid_source",
                        message=f"{record_path}.source must be a non-empty string.",
                        program=program.name,
                        topology_path=f"{record_path}.source",
                        recommendation="Use a static source stage name.",
                    )
                )
            elif source not in known_nodes:
                diagnostics.append(
                    RoutingPurityDiagnostic(
                        code="routing.topology_unknown_source",
                        message=f"{record_path}.source '{source}' does not match a known stage.",
                        program=program.name,
                        topology_path=f"{record_path}.source",
                        recommendation="Point static routes at declared stages in the same program.",
                    )
                )

            if not isinstance(label, str) or not label:
                diagnostics.append(
                    RoutingPurityDiagnostic(
                        code="routing.topology_invalid_label",
                        message=f"{record_path}.label must be a non-empty string.",
                        program=program.name,
                        topology_path=f"{record_path}.label",
                        recommendation="Use a static route label.",
                    )
                )

            if target is not None and not isinstance(target, str):
                diagnostics.append(
                    RoutingPurityDiagnostic(
                        code="routing.topology_invalid_target",
                        message=f"{record_path}.target must be a string or null.",
                        program=program.name,
                        topology_path=f"{record_path}.target",
                        recommendation="Use a static target stage name or null for terminal routes.",
                    )
                )
            elif isinstance(target, str) and target not in known_nodes and target not in _TERMINAL_TARGETS:
                diagnostics.append(
                    RoutingPurityDiagnostic(
                        code="routing.topology_unknown_target",
                        message=f"{record_path}.target '{target}' does not match a known stage.",
                        program=program.name,
                        topology_path=f"{record_path}.target",
                        recommendation="Point static routes at declared stages in the same program.",
                    )
                )

            if condition_ref is not None and not isinstance(condition_ref, str):
                diagnostics.append(
                    RoutingPurityDiagnostic(
                        code="routing.topology_invalid_condition_ref",
                        message=f"{record_path}.condition_ref must be a string when present.",
                        program=program.name,
                        topology_path=f"{record_path}.condition_ref",
                        recommendation="Reference a static condition name or omit condition_ref.",
                    )
                )

    return diagnostics


def _extract_topology_nodes(topology: Mapping[str, Any]) -> set[str]:
    nodes: set[str] = set()
    for key in _ROUTING_TOPOLOGY_NODE_KEYS:
        collection = topology.get(key)
        if not isinstance(collection, list):
            continue
        for entry in collection:
            if isinstance(entry, str) and entry:
                nodes.add(entry)
            elif isinstance(entry, Mapping):
                name = _record_value(entry, "name", "stage", "step", "id")
                if isinstance(name, str) and name:
                    nodes.add(name)
    return nodes


def _record_value(record: Mapping[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in record:
            return record[key]
    return None


def _find_function_def(tree: ast.AST, fn_name: str) -> ast.FunctionDef | ast.AsyncFunctionDef | None:
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == fn_name:
            return node
    return None


class _DecisionPurityVisitor(ast.NodeVisitor):
    def __init__(
        self,
        *,
        fn: Callable[..., Any],
        program_name: str | None,
        decision_name: str,
        source_file: str | None,
        base_lineno: int,
    ) -> None:
        self.fn = fn
        self.program_name = program_name
        self.decision_name = decision_name
        self.source_file = source_file
        self.base_lineno = base_lineno
        self.diagnostics: list[RoutingPurityDiagnostic] = []

    def visit_Import(self, node: ast.Import) -> None:
        self._add(
            node,
            code="routing.dynamic_import",
            message="Decision bodies must not import modules dynamically.",
        )

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        self._add(
            node,
            code="routing.dynamic_import",
            message="Decision bodies must not import modules dynamically.",
        )

    def visit_Call(self, node: ast.Call) -> None:
        dotted = _dotted_name(node.func)
        resolved = _resolve_reference_name(self.fn, node.func)
        resolved_call = _resolve_call_target_name(self.fn, node.func)
        candidate_names = tuple(name for name in (dotted, resolved, resolved_call) if name)

        if _is_dynamic_dispatch(node.func):
            self._add(
                node,
                code="routing.dynamic_dispatch",
                message="Decision bodies must not use dynamic dispatch.",
            )
        elif _matches_prefix(candidate_names, _NONDETERMINISTIC_PREFIXES):
            self._add(
                node,
                code="routing.nondeterministic_call",
                message="Decision bodies must not call nondeterministic APIs.",
            )
        elif _matches_prefix(candidate_names, _IO_PREFIXES):
            self._add(
                node,
                code="routing.io_call",
                message="Decision bodies must not perform filesystem I/O.",
            )
        elif _matches_prefix(candidate_names, _NETWORK_PREFIXES):
            self._add(
                node,
                code="routing.network_call",
                message="Decision bodies must not perform network I/O.",
            )
        elif _matches_prefix(candidate_names, _SUBPROCESS_PREFIXES):
            self._add(
                node,
                code="routing.subprocess_call",
                message="Decision bodies must not spawn subprocesses or shell commands.",
            )
        elif _matches_prefix(candidate_names, _DYNAMIC_PREFIXES):
            self._add(
                node,
                code="routing.dynamic_dispatch",
                message="Decision bodies must not use dynamic imports or reflective dispatch.",
            )

        if _mutates_state_by_method(node):
            key_name = _mutated_state_key_name(node)
            if key_name is not None:
                self._add(
                    node,
                    code="routing.state_mutation",
                    message=(
                        f"Decision bodies must not mutate routing-owned state key '{key_name}'."
                    ),
                )

        self.generic_visit(node)

    def visit_Assign(self, node: ast.Assign) -> None:
        for target in node.targets:
            key_name = _mutated_state_key_name(target)
            if key_name is not None:
                self._add(
                    target,
                    code="routing.state_mutation",
                    message=(
                        f"Decision bodies must not mutate routing-owned state key '{key_name}'."
                    ),
                )
        self.generic_visit(node)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        key_name = _mutated_state_key_name(node.target)
        if key_name is not None:
            self._add(
                node.target,
                code="routing.state_mutation",
                message=(
                    f"Decision bodies must not mutate routing-owned state key '{key_name}'."
                ),
            )
        self.generic_visit(node)

    def visit_AugAssign(self, node: ast.AugAssign) -> None:
        key_name = _mutated_state_key_name(node.target)
        if key_name is not None:
            self._add(
                node.target,
                code="routing.state_mutation",
                message=(
                    f"Decision bodies must not mutate routing-owned state key '{key_name}'."
                ),
            )
        self.generic_visit(node)

    def _add(self, node: ast.AST, *, code: str, message: str) -> None:
        self.diagnostics.append(
            RoutingPurityDiagnostic(
                code=code,
                message=message,
                program=self.program_name,
                decision=self.decision_name,
                source_file=self.source_file,
                line=self.base_lineno + getattr(node, "lineno", 1) - 1,
                column=getattr(node, "col_offset", None),
            )
        )


def _matches_prefix(names: tuple[str, ...], prefixes: tuple[str, ...]) -> bool:
    for name in names:
        for prefix in prefixes:
            if name == prefix or name.startswith(prefix):
                return True
    return False


def _dotted_name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        base = _dotted_name(node.value)
        if base is None:
            return None
        return f"{base}.{node.attr}"
    return None


def _resolve_reference_name(fn: Callable[..., Any], node: ast.AST) -> str | None:
    dotted = _dotted_name(node)
    if dotted is None:
        return None
    root, _, remainder = dotted.partition(".")
    candidate = fn.__globals__.get(root)
    if candidate is None:
        return None

    current = candidate
    resolved_parts: list[str] = [_object_name(current)]
    if not resolved_parts[0]:
        return None

    if remainder:
        for piece in remainder.split("."):
            try:
                current = getattr(current, piece)
            except Exception:
                resolved_parts.append(piece)
                break
            resolved_parts.append(piece)

    return ".".join(part for part in resolved_parts if part)


def _resolve_call_target_name(fn: Callable[..., Any], node: ast.AST) -> str | None:
    if not isinstance(node, ast.Attribute):
        return None
    if not isinstance(node.value, ast.Call):
        return None
    callee_name = _resolve_reference_name(fn, node.value.func) or _dotted_name(node.value.func)
    if callee_name is None:
        return None
    return f"{callee_name}.{node.attr}"


def _object_name(obj: Any) -> str:
    if isinstance(obj, ModuleType):
        return obj.__name__
    module = getattr(obj, "__module__", None)
    qualname = getattr(obj, "__qualname__", None) or getattr(obj, "__name__", None)
    if module and qualname:
        return f"{module}.{qualname}"
    if qualname:
        return qualname
    if module:
        return module
    return ""


def _is_dynamic_dispatch(node: ast.AST) -> bool:
    if isinstance(node, (ast.Call, ast.Subscript, ast.Lambda)):
        return True
    if isinstance(node, ast.Attribute) and node.attr in {"__call__", "__getattribute__", "__getattr__"}:
        return True
    return False


def _mutates_state_by_method(node: ast.Call) -> bool:
    if not isinstance(node.func, ast.Attribute):
        return False
    if node.func.attr not in _MUTATING_METHODS:
        return False
    return _state_key_from_expr(node.func.value) is not None


def _mutated_state_key_name(node: ast.AST) -> str | None:
    state_key = _state_key_from_expr(node)
    if state_key in _ROUTING_OWNED_STATE_KEYS:
        return state_key
    return None


def _state_key_from_expr(node: ast.AST) -> str | None:
    path = _subscript_path(node)
    if len(path) >= 2 and path[0] == "state" and isinstance(path[1], str):
        return path[1]
    if len(path) >= 3 and path[0] in {"ctx", "context"} and path[1] == "state" and isinstance(path[2], str):
        return path[2]
    return None


def _subscript_path(node: ast.AST) -> tuple[str, ...]:
    if isinstance(node, ast.Name):
        return (node.id,)
    if isinstance(node, ast.Subscript):
        base = _subscript_path(node.value)
        key = _literal_subscript_key(node.slice)
        if base and key is not None:
            return base + (key,)
    return ()


def _literal_subscript_key(node: ast.AST) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.Index):  # pragma: no cover - py<3.9 compat
        return _literal_subscript_key(node.value)
    return None
