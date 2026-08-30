#!/usr/bin/env python3
"""Static proof that production worker doors do not bypass admission."""
from __future__ import annotations

import argparse
import ast
import json
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
DOORS = (
    ROOT / "arnold_pipelines/megaplan/workers/_impl.py",
    ROOT / "arnold_pipelines/megaplan/workers/omp.py",
    ROOT / "arnold_pipelines/megaplan/cloud/babysitter/launch.py",
)
CANONICAL_DOORS = frozenset(DOORS)
CHAIN = ROOT / "arnold_pipelines/megaplan/chain"
FORBIDDEN_RAW = {
    "refresh_runtime_launch_seed_for_worker_dispatch",
    "require_configured_runtime_launch",
    "worker_launch_preflight",
}


def _constant_string(node: ast.AST) -> str:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        left = _constant_string(node.left)
        right = _constant_string(node.right)
        return left + right if left and right else ""
    return ""


def _resolve_expr(node: ast.AST, aliases: dict[str, str]) -> str:
    if isinstance(node, ast.Name):
        return aliases.get(node.id, node.id)
    if isinstance(node, ast.Attribute):
        base = _resolve_expr(node.value, aliases)
        name = f"{base}.{node.attr}" if base else node.attr
        return aliases.get(name, name)
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "getattr":
        if len(node.args) >= 2:
            base = _resolve_expr(node.args[0], aliases)
            attr = _constant_string(node.args[1])
            if base and attr:
                name = f"{base}.{attr}"
                return aliases.get(name, name)
    return ""


def _aliases(tree: ast.AST) -> dict[str, str]:
    aliases: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            for item in node.names:
                module = node.module or ""
                aliases[item.asname or item.name] = f"{module}.{item.name}".strip(".")
        elif isinstance(node, ast.Import):
            for item in node.names:
                aliases[item.asname or item.name.split(".")[-1]] = item.name
    for _ in range(16):
        changed = False
        for node in ast.walk(tree):
            if not isinstance(node, (ast.Assign, ast.AnnAssign, ast.NamedExpr)):
                continue
            resolved = _resolve_expr(node.value, aliases)
            if not resolved:
                continue
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for target in targets:
                if isinstance(target, ast.Name):
                    key = target.id
                elif isinstance(target, ast.Attribute):
                    key = _resolve_expr(target, aliases)
                else:
                    continue
                if key and aliases.get(key) != resolved:
                    aliases[key] = resolved
                    changed = True
        if not changed:
            break
    return aliases


def _call_names(tree: ast.AST) -> Iterable[tuple[str, int]]:
    aliases = _aliases(tree)
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            yield _resolve_expr(node.func, aliases), node.lineno


def _enclosing_functions(tree: ast.AST) -> dict[int, str]:
    """Map call line numbers to the innermost function that owns them."""
    owners: dict[int, str] = {}

    class Visitor(ast.NodeVisitor):
        def __init__(self) -> None:
            self.stack: list[str] = []

        def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
            self.stack.append(node.name)
            self.generic_visit(node)
            self.stack.pop()

        def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
            self.stack.append(node.name)
            self.generic_visit(node)
            self.stack.pop()

        def visit_Call(self, node: ast.Call) -> None:
            if self.stack:
                owners[node.lineno] = self.stack[-1]
            self.generic_visit(node)

    Visitor().visit(tree)
    return owners

def check_files(paths: Iterable[Path] = DOORS) -> dict[str, Any]:
    diagnostics: list[dict[str, Any]] = []
    for path in paths:
        try:
            source = path.read_text(encoding="utf-8")
            tree = ast.parse(source, filename=str(path))
        except (OSError, SyntaxError) as exc:
            diagnostics.append({"path": str(path), "code": "unreadable_or_invalid", "detail": str(exc)})
            continue
        for name, line in _call_names(tree):
            if name in FORBIDDEN_RAW or name.rsplit(".", 1)[-1] in FORBIDDEN_RAW:
                diagnostics.append({
                    "path": str(path),
                    "line": line,
                    "code": "raw_runtime_preflight" if name != "worker_launch_preflight" else "chain_local_preflight",
                    "symbol": name,
                })
        aliases = _aliases(tree)
        dispatch_calls = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and (
                _resolve_expr(node.func, aliases) == "dispatch_with_admission"
                or _resolve_expr(node.func, aliases).endswith(".dispatch_with_admission")
            )
        ]
        owners = _enclosing_functions(tree)
        raw_process_calls = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and _resolve_expr(node.func, aliases) in {
                "subprocess.Popen",
                "subprocess.run",
                "subprocess.call",
                "subprocess.check_call",
                "subprocess.check_output",
            }
        ]
        allowed_canonical_subprocess_owners = {
            "run_command",
            "output",
            "_prepare_zero_recovery_model_runtime",
            "_zero_recovery_source_identity",
            "_quiesce_zero_recovery_model_uid",
            "_ps_children",
            "_subtree_cputime_sample",
            "_worktree_mutation_fingerprint",
        }
        for node in raw_process_calls:
            name = _resolve_expr(node.func, aliases)
            owner = owners.get(node.lineno)
            if (
                path in CANONICAL_DOORS
                and name != "subprocess.Popen"
                and owner in allowed_canonical_subprocess_owners
            ):
                continue
            diagnostics.append({
                "path": str(path),
                "line": node.lineno,
                "code": "raw_launch_access",
                "symbol": name or "dynamic subprocess launch",
            })
        if path not in CANONICAL_DOORS:
            direct_launches = [
                (name, line) for name, line in _call_names(tree)
                if name in {"run_managed_command", "run_omp_step", "worker_launch_preflight"}
            ]
            for name, line in direct_launches:
                diagnostics.append({"path": str(path), "line": line, "code": "no_wbc_bypass", "symbol": name})
            wbc_calls = [
                node
                for node in ast.walk(tree)
                if isinstance(node, ast.Call)
                and _resolve_expr(node.func, aliases).split(".")[-1] in {"run", "dispatch"}
                and not _resolve_expr(node.func, aliases).startswith("subprocess.")
            ]
            if wbc_calls:
                dispatch_lines = [node.lineno for node in dispatch_calls]
                if not dispatch_lines or any(node.lineno < min(dispatch_lines) for node in wbc_calls):
                    diagnostics.extend(
                        {"path": str(path), "line": node.lineno, "code": "wbc_before_admission"}
                        for node in wbc_calls
                    )
        # The shared dispatcher owns admission.  A door may invoke it once,
        # but may not supply a replacement gate capable of minting a receipt or
        # bypassing source/runtime/liveness checks.  Resolver/readers belong on
        # the typed request instead.
        for node in dispatch_calls:
            if any(keyword.arg == "gate" for keyword in node.keywords):
                diagnostics.append({
                    "path": str(path),
                    "line": node.lineno,
                    "code": "caller_trusted_admission_gate",
                    "detail": "dispatch_with_admission must use the canonical authority",
                })
        if path.name in {"_impl.py", "omp.py", "launch.py"} and len(dispatch_calls) > 1:
            diagnostics.append({
                "path": str(path),
                "code": "duplicate_admission_door",
                "detail": f"found {len(dispatch_calls)} dispatch_with_admission calls; each physical door must have one",
            })
        for node in dispatch_calls:
            owner = owners.get(node.lineno, "")
            expected = {
                "_impl.py": "_production_worker_dispatch",
                "omp.py": "_run_omp_with_admission",
                "launch.py": "_admit_managed_launch",
            }.get(path.name)
            if expected and owner != expected:
                diagnostics.append({
                    "path": str(path),
                    "line": node.lineno,
                    "code": "dispatch_outside_authorized_door",
                    "detail": f"canonical dispatch must be owned by {expected}, got {owner or 'module'}",
                })
            typed_return = any(
                keyword.arg == "return_worker"
                and getattr(keyword.value, "value", None) in {True, False}
                for keyword in node.keywords
            )
            if not typed_return:
                diagnostics.append({
                    "path": str(path),
                    "line": node.lineno,
                    "code": "dispatch_without_typed_worker_return",
                    "detail": "production doors must retain the typed worker result for terminal normalization",
                })
        if path.name == "_impl.py":
            if "dispatch_with_admission" not in source:
                diagnostics.append({"path": str(path), "code": "missing_canonical_dispatch"})
            if "_run_step_with_worker_legacy" not in source:
                diagnostics.append({"path": str(path), "code": "missing_admitted_final_closure"})
        if path.name == "omp.py" and "_run_omp_with_admission" not in source:
            diagnostics.append({"path": str(path), "code": "missing_omp_door"})
        if path.name == "launch.py" and "_admit_managed_launch" not in source:
            diagnostics.append({"path": str(path), "code": "missing_babysitter_door"})
    for path in CHAIN.rglob("*.py"):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except (OSError, SyntaxError):
            continue
        for name, line in _call_names(tree):
            if name in {"run_managed_command", "run_omp_step", "worker_launch_preflight"}:
                diagnostics.append({"path": str(path), "line": line, "code": "direct_chain_launch", "symbol": name})
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
