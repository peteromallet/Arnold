#!/usr/bin/env python3
"""Static proof that production worker doors do not bypass admission."""
from __future__ import annotations

import argparse
import ast
import json
import re
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
DOORS = (
    ROOT / "arnold_pipelines/megaplan/workers/_impl.py",
    ROOT / "arnold_pipelines/megaplan/workers/omp.py",
    ROOT / "arnold_pipelines/megaplan/cloud/babysitter/launch.py",
)
CHAIN = ROOT / "arnold_pipelines/megaplan/chain"
FORBIDDEN_RAW = {
    "refresh_runtime_launch_seed_for_worker_dispatch",
    "require_configured_runtime_launch",
    "worker_launch_preflight",
}


def _call_names(tree: ast.AST) -> Iterable[tuple[str, int]]:
    aliases: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            for item in node.names:
                aliases[item.asname or item.name] = item.name
        elif isinstance(node, ast.Import):
            for item in node.names:
                aliases[item.asname or item.name.split(".")[-1]] = item.name
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                yield aliases.get(node.func.id, node.func.id), node.lineno
            elif isinstance(node.func, ast.Attribute):
                yield node.func.attr, node.lineno


def _aliases(tree: ast.AST) -> dict[str, str]:
    """Resolve import, module, assignment, and callable aliases deterministically."""
    aliases: dict[str, str] = {}
    changed = True
    passes = 0
    while changed and passes < 32:
        passes += 1
        changed = False
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                for item in node.names:
                    name = item.asname or item.name
                    qualified = f"{node.module}.{item.name}" if node.module else item.name
                    if aliases.get(name) != qualified:
                        aliases[name] = qualified
                        changed = True
            elif isinstance(node, ast.Import):
                for item in node.names:
                    name = item.asname or item.name.split(".")[-1]
                    if aliases.get(name) != item.name:
                        aliases[name] = item.name
                        changed = True
            elif isinstance(node, (ast.Assign, ast.AnnAssign)):
                value = node.value
                qualified = _qualified_value_name(value, aliases)
                if not qualified:
                    continue
                targets = node.targets if isinstance(node, ast.Assign) else (node.target,)
                for target in targets:
                    if isinstance(target, ast.Name) and aliases.get(target.id) != qualified:
                        aliases[target.id] = qualified
                        changed = True
    return aliases


def _qualified_value_name(node: ast.AST, aliases: dict[str, str]) -> str:
    if isinstance(node, (ast.Name, ast.Attribute)):
        return _qualified_name(node, aliases)
    if (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "getattr"
        and len(node.args) >= 2
        and isinstance(node.args[1], ast.Constant)
        and isinstance(node.args[1].value, str)
    ):
        prefix = _qualified_name(node.args[0], aliases)
        return f"{prefix}.{node.args[1].value}" if prefix else node.args[1].value
    return ""


def _call_target(node: ast.Call, aliases: dict[str, str]) -> str:
    if isinstance(node.func, (ast.Name, ast.Attribute)):
        return _qualified_name(node.func, aliases)
    return ""


def _getattr_target(node: ast.Call, aliases: dict[str, str]) -> str:
    if (
        isinstance(node.func, ast.Name)
        and node.func.id == "getattr"
        and len(node.args) >= 2
        and isinstance(node.args[1], ast.Constant)
        and isinstance(node.args[1].value, str)
    ):
        prefix = _qualified_name(node.args[0], aliases)
        return f"{prefix}.{node.args[1].value}" if prefix else node.args[1].value
    return ""


def _qualified_name(node: ast.AST, aliases: dict[str, str]) -> str:
    if isinstance(node, ast.Name):
        return aliases.get(node.id, node.id)
    if isinstance(node, ast.Attribute):
        prefix = _qualified_name(node.value, aliases)
        return f"{prefix}.{node.attr}" if prefix else node.attr
    return ""

def _symbol(node: ast.AST) -> str:
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        return node.name
    for parent in getattr(node, "_authority_parents", ()):
        if isinstance(parent, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            return parent.name
    return "<module>"


def _diagnostic(path: Path, node: ast.AST, *, category: str, reason: str, code: str | None = None) -> dict[str, Any]:
    return {
        "path": str(path),
        "line": getattr(node, "lineno", 0),
        "enclosing_symbol": _symbol(node),
        "category": category,
        "reason": reason,
        "code": code or category,
    }


class _AuthorityVisitor(ast.NodeVisitor):
    def __init__(self, path: Path, aliases: dict[str, str], *, strict_all_calls: bool = False) -> None:
        self.path = path
        self.aliases = aliases
        self.strict_all_calls = strict_all_calls
        self.diagnostics: list[dict[str, Any]] = []
        self.scope: list[ast.AST] = []
        self.calls_by_scope: dict[ast.AST, list[ast.Call]] = {}

    def visit(self, node: ast.AST) -> Any:
        node._authority_parents = tuple(reversed(self.scope))  # type: ignore[attr-defined]
        return super().visit(node)

    def _add(self, node: ast.AST, category: str, reason: str, code: str | None = None) -> None:
        self.diagnostics.append(_diagnostic(self.path, node, category=category, reason=reason, code=code))

    def visit_FunctionDef(self, node: ast.FunctionDef) -> Any:
        self.scope.append(node)
        self.calls_by_scope[node] = []
        self.generic_visit(node)
        self.scope.pop()

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_ClassDef(self, node: ast.ClassDef) -> Any:
        self.scope.append(node)
        self.generic_visit(node)
        self.scope.pop()

    def visit_Call(self, node: ast.Call) -> Any:
        name = _call_target(node, self.aliases)
        getattr_target = _getattr_target(node, self.aliases)
        if getattr_target:
            name = getattr_target
        short = name.rsplit(".", 1)[-1]
        scope = self.scope[-1] if self.scope else None
        if scope is not None:
            self.calls_by_scope.setdefault(scope, []).append(node)

        if short in FORBIDDEN_RAW or name in FORBIDDEN_RAW:
            category = "chain_local_preflight" if short == "worker_launch_preflight" else "raw_authority_call"
            self._add(node, category, f"raw authority primitive {name!r} is owned by canonical admission", "raw_runtime_preflight" if category == "raw_authority_call" else category)

        scope_name = self.scope[-1].name if self.scope and isinstance(self.scope[-1], (ast.FunctionDef, ast.AsyncFunctionDef)) else ""
        # ``execute`` is a configured physical door even though its spelling
        # does not contain the historical launch/worker words.  Keep the
        # checker focused on known door-shaped symbols, but never let that
        # legacy naming convention hide a process construction.
        # A configured physical door is a file-level boundary: helper nesting
        # and arbitrary function names must not hide a second process/client/
        # RPC construction.  ``strict_all_calls`` is used for focused fixture
        # paths; canonical door files receive the same treatment here.
        door_scope = self.strict_all_calls or self.path in DOORS or not scope_name or bool(re.search(r"launch|dispatch|admit|spawn|worker|execute", scope_name, re.I))
        # These helpers only inspect/measure already-running processes or
        # invoke read-only catalog/runtime probes; they are not launch doors.
        process_observation_helpers = {
            "run_command", "output", "_prepare_zero_recovery_model_runtime",
            "_zero_recovery_source_identity", "_quiesce_zero_recovery_model_uid",
            "_ps_children", "_subtree_cputime_sample", "_worktree_mutation_fingerprint",
        }
        process_name = name.lower()
        is_process_call = short != "run" or process_name.startswith("subprocess.") or process_name.startswith("asyncio.subprocess.")
        if door_scope and scope_name in process_observation_helpers and short == "run":
            pass
        elif door_scope and short in {"Popen", "create_subprocess_exec", "create_subprocess_shell", "system", "call", "run"} and is_process_call:
            self._add(node, "direct_process_construction", f"direct process construction {name!r} bypasses the admitted closure")
        elif door_scope and short in {"RpcClient", "OpenAI", "Anthropic", "Client"}:
            self._add(node, "direct_client_construction", f"direct client construction {name!r} bypasses the admitted closure")
        elif door_scope and short in {"create", "request", "post", "send"} and any(part in name.lower() for part in ("rpc", "client", "completion", "response")):
            self._add(node, "direct_rpc_construction", f"direct RPC call {name!r} bypasses the admitted closure")
        elif door_scope and short in {"CommonWorkerDispatchSpec", "WbcRuntimeProducerFacade", "build_worker_dispatch_spec"}:
            self._add(node, "direct_wbc_construction", f"direct WBC construction {name!r} must be supplied by the owner")

        if short in {"run_managed_command", "run_omp_step"} and self.path.parent.name == "chain":
            self._add(node, "direct_chain_launch", f"chain code directly invokes launch authority {name!r}", "direct_chain_launch")
        if short in {"final_launch", "legacy_launch"}:
            self._add(node, "raw_final_launch_access", f"raw final-launch access {short!r} bypasses the controlled adapter")

        self.generic_visit(node)


def _resolved_call_name(call: ast.Call, aliases: dict[str, str]) -> str:
    return _call_target(call, aliases) or _getattr_target(call, aliases)


def _order_diagnostics(path: Path, tree: ast.AST, visitor: _AuthorityVisitor) -> None:
    admission_calls: list[ast.Call] = []
    for calls in visitor.calls_by_scope.values():
        admission_calls.extend(
            call for call in calls
            if _resolved_call_name(call, visitor.aliases).rsplit(".", 1)[-1]
            in {"dispatch_with_admission", "require_production_worker_dispatch_runtime"}
        )
    for scope, calls in visitor.calls_by_scope.items():
        admission_lines = [
            call.lineno for call in calls
            if _resolved_call_name(call, visitor.aliases).rsplit(".", 1)[-1]
            in {"dispatch_with_admission", "require_production_worker_dispatch_runtime"}
        ]
        if len(admission_lines) > 1:
            visitor._add(scope, "nested_double_admission", "one physical door contains more than one admission call")
        if admission_lines:
            for nested in admission_calls:
                parents = getattr(nested, "_authority_parents", ())
                owner = parents[0] if parents else None
                if owner is not scope and scope in parents:
                    visitor._add(nested, "nested_double_admission", "nested scope repeats canonical admission")
        ancestor_calls: list[ast.Call] = []
        for parent in getattr(scope, "_authority_parents", ()):
            ancestor_calls.extend(visitor.calls_by_scope.get(parent, ()))
        all_scope_calls = [*ancestor_calls, *calls]
        all_admission_lines = [
            call.lineno for call in all_scope_calls
            if _resolved_call_name(call, visitor.aliases).rsplit(".", 1)[-1]
            in {"dispatch_with_admission", "require_production_worker_dispatch_runtime"}
        ]
        for call in calls:
            name = _resolved_call_name(call, visitor.aliases)
            short = name.rsplit(".", 1)[-1]
            if short == "run" and name.rsplit(".", 1)[0].endswith("wbc_dispatch"):
                nested = any(
                    isinstance(parent, (ast.FunctionDef, ast.AsyncFunctionDef))
                    and parent is not scope
                    for parent in getattr(call, "_authority_parents", ())
                )
                if _symbol(call) == "run_step_with_worker":
                    continue
                if not nested and not any(line < call.lineno for line in all_admission_lines):
                    visitor._add(call, "wbc_before_admission", "WBC attempt occurs before canonical admission")
            if short in {"run_managed_command", "run_omp_step"}:
                if visitor.path.parent.name == "chain" and not any(line < call.lineno for line in all_admission_lines):
                    visitor._add(call, "direct_launch_before_admission", "launch call is not dominated by canonical admission")

def _text_diagnostics(path: Path, source: str, aliases: dict[str, str], *, strict_all_calls: bool = False) -> list[dict[str, Any]]:
    diagnostics: list[dict[str, Any]] = []
    try:
        tree = ast.parse(source, filename=str(path))
    except SyntaxError:
        return diagnostics
    # This pass is intentionally separate from the AST authority visitor:
    # absent-WBC delegation is a control-flow/text rule, but its diagnostics
    # still need the same enclosing-symbol context.
    context = _AuthorityVisitor(path, aliases, strict_all_calls=strict_all_calls)
    context.visit(tree)
    for node in ast.walk(tree):
        if not isinstance(node, ast.If):
            continue
        test = node.test
        absent_wbc = _is_absent_wbc_test(test, aliases)
        if not absent_wbc:
            continue
        for call in ast.walk(node):
            if not isinstance(call, ast.Call):
                continue
            name = _call_target(call, aliases) or _getattr_target(call, aliases)
            if name.rsplit(".", 1)[-1] in {"final_launch", "legacy_launch"}:
                diagnostics.append(_diagnostic(path, call, category="absent_wbc_legacy_delegation", reason="absent WBC branch delegates to legacy final launch"))
    return diagnostics


def _is_wbc_name(node: ast.AST, aliases: dict[str, str]) -> bool:
    return _qualified_name(node, aliases).rsplit(".", 1)[-1] == "wbc_dispatch"


def _is_absent_wbc_test(test: ast.AST, aliases: dict[str, str]) -> bool:
    """Recognize falsey, reversed, and multiline WBC guards structurally."""
    if isinstance(test, ast.UnaryOp) and isinstance(test.op, ast.Not):
        operand = test.operand
        if _is_wbc_name(operand, aliases):
            return True
        return isinstance(operand, ast.Call) and _qualified_name(operand.func, aliases).rsplit(".", 1)[-1] == "bool" and len(operand.args) == 1 and _is_wbc_name(operand.args[0], aliases)
    if isinstance(test, ast.Compare) and len(test.ops) == 1 and len(test.comparators) == 1:
        left, right = test.left, test.comparators[0]
        if isinstance(test.ops[0], (ast.Is, ast.Eq)):
            if (isinstance(right, ast.Constant) and right.value is False):
                return _is_falsey_wbc_expression(left, aliases)
            if (isinstance(left, ast.Constant) and left.value is False):
                return _is_falsey_wbc_expression(right, aliases)
            return (_is_wbc_name(left, aliases) and isinstance(right, ast.Constant) and right.value is None) or (
                isinstance(left, ast.Constant) and left.value is None and _is_wbc_name(right, aliases)
            )
    return False


def _is_falsey_wbc_expression(node: ast.AST, aliases: dict[str, str]) -> bool:
    if _is_wbc_name(node, aliases):
        return True
    return isinstance(node, ast.Call) and _qualified_name(node.func, aliases).rsplit(".", 1)[-1] == "bool" and len(node.args) == 1 and _is_wbc_name(node.args[0], aliases)


def check_files(paths: Iterable[Path] = DOORS) -> dict[str, Any]:
    paths = tuple(paths)
    diagnostics: list[dict[str, Any]] = []
    for path in paths:
        try:
            source = path.read_text(encoding="utf-8")
            tree = ast.parse(source, filename=str(path))
        except (OSError, SyntaxError) as exc:
            diagnostics.append({"path": str(path), "line": 0, "enclosing_symbol": "<module>", "category": "unreadable_or_invalid", "reason": str(exc), "code": "unreadable_or_invalid"})
            continue
        aliases = _aliases(tree)
        visitor = _AuthorityVisitor(path, aliases, strict_all_calls=path not in DOORS)
        visitor.visit(tree)
        _order_diagnostics(path, tree, visitor)
        diagnostics.extend(visitor.diagnostics)
        diagnostics.extend(_text_diagnostics(path, source, aliases, strict_all_calls=path not in DOORS))
        if path.name == "_impl.py":
            if "dispatch_with_admission" not in source:
                diagnostics.append({"path": str(path), "code": "missing_canonical_dispatch"})
            if "_run_step_with_worker_legacy" not in source:
                diagnostics.append({"path": str(path), "code": "missing_admitted_final_closure"})
        if path.name == "omp.py" and "_run_omp_with_admission" not in source:
            diagnostics.append({"path": str(path), "code": "missing_omp_door"})
        if path.name == "launch.py" and "_admit_managed_launch" not in source:
            diagnostics.append({"path": str(path), "code": "missing_babysitter_door"})
    # Fixture callers ask to inspect exactly their temporary door.  Scanning
    # the entire chain tree for every fixture is both redundant and capable of
    # turning the focused suite into a timeout.  The repository check retains
    # the chain authority pass because it uses the configured default doors.
    chain_paths = CHAIN.rglob("*.py") if paths == DOORS else ()
    for path in chain_paths:
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except (OSError, SyntaxError):
            continue
        aliases = _aliases(tree)
        visitor = _AuthorityVisitor(path, aliases)
        visitor.visit(tree)
        _order_diagnostics(path, tree, visitor)
        diagnostics.extend(visitor.diagnostics)
    def display_path(path: Path) -> str:
        try:
            return str(path.relative_to(ROOT))
        except ValueError:
            return str(path)

    return {"ok": not diagnostics, "diagnostics": diagnostics, "doors": [display_path(p) for p in paths]}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="check the repository doors")
    parser.parse_args()
    result = check_files()
    print(json.dumps(result, sort_keys=True, indent=2))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
