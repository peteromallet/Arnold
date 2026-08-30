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
            if name in FORBIDDEN_RAW:
                diagnostics.append({
                    "path": str(path),
                    "line": line,
                    "code": "raw_runtime_preflight" if name != "worker_launch_preflight" else "chain_local_preflight",
                    "symbol": name,
                })
        dispatch_calls = [
            node for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and ((isinstance(node.func, ast.Name) and node.func.id == "dispatch_with_admission")
                 or (isinstance(node.func, ast.Attribute) and node.func.attr == "dispatch_with_admission"))
        ]
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
