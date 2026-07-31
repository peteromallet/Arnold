"""Deterministic A7 legacy-reader inventory and runtime trace capture."""

from __future__ import annotations

import ast
import hashlib
import importlib
import inspect
import json
import sys
import tempfile
import textwrap
from pathlib import Path
from typing import Any, Callable


A7_INVENTORY_SCHEMA = "m11.a7-legacy-bypass-inventory.v1"

SOURCE_SPECS: dict[str, tuple[Path, str]] = {
    "readers": (
        Path("evidence/authority-reader-registry.json"),
        "m6.authority-reader-registry.v1",
    ),
    "writers": (
        Path("evidence/controlled-writer-registry.json"),
        "m6.controlled-writer-registry.v1",
    ),
    "deletion": (
        Path("evidence/rollout-deletion-register.json"),
        "m6.rollout-deletion-register.v1",
    ),
    "historical_adapters": (
        Path("evidence/wbc-historical-adapters.json"),
        "m6.wbc-historical-adapters.v1",
    ),
    "migration": (
        Path("evidence/migration-matrix-reconciled.json"),
        "m6.migration-matrix-reconciled.v1",
    ),
}

_LEGACY_TERMS = (
    "legacy", "raw_state", "raw state", "status", "process", "marker",
    "sidecar", "wrapper", "compatib", "filename", "mutable_receipt",
    "raw_json",
)


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def _sha256(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _load_sources(repo_root: Path) -> tuple[
    dict[str, dict[str, Any]], dict[str, dict[str, Any]], list[dict[str, Any]]
]:
    documents: dict[str, dict[str, Any]] = {}
    bindings: dict[str, dict[str, Any]] = {}
    failures: list[dict[str, Any]] = []
    for name, (relative_path, expected_schema) in SOURCE_SPECS.items():
        path = repo_root / relative_path
        try:
            raw = path.read_bytes()
            value = json.loads(raw)
        except (OSError, json.JSONDecodeError) as exc:
            failures.append({
                "kind": "source_unreadable",
                "source": name,
                "path": relative_path.as_posix(),
                "detail": str(exc),
            })
            value, raw = {}, b""
        if not isinstance(value, dict):
            failures.append({
                "kind": "source_not_object",
                "source": name,
                "path": relative_path.as_posix(),
            })
            value = {}
        actual_schema = (
            value.get("meta", {}).get("schema")
            if name == "historical_adapters"
            else value.get("schema")
        )
        if actual_schema != expected_schema:
            failures.append({
                "kind": "source_schema_mismatch",
                "source": name,
                "expected": expected_schema,
                "actual": actual_schema,
            })
        documents[name] = value
        bindings[name] = {
            "path": relative_path.as_posix(),
            "sha256": _sha256(raw),
            "schema": actual_schema,
        }
    return documents, bindings, failures


def _module_name(path: str) -> str | None:
    if not path.endswith(".py"):
        return None
    return path[:-3].replace("/", ".")


def _discover_adapter_calls(
    repo_root: Path,
    adapters: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Callable[..., Any]]]:
    failures: list[dict[str, Any]] = []
    imported_modules: dict[str, Any] = {}
    for adapter in adapters:
        for path in adapter.get("path_symbols", []):
            module_name = _module_name(str(path))
            if module_name and module_name not in imported_modules:
                try:
                    imported_modules[module_name] = importlib.import_module(module_name)
                except Exception as exc:
                    failures.append({
                        "kind": "adapter_module_import_failed",
                        "adapter_id": adapter.get("adapter_id"),
                        "module": module_name,
                        "detail": repr(exc),
                    })

    rows: dict[str, dict[str, Any]] = {}
    callables: dict[str, Callable[..., Any]] = {}
    for adapter in adapters:
        adapter_id = str(adapter.get("adapter_id", ""))
        for operation in adapter.get("observed_read_operations", []):
            matches: list[Callable[..., Any]] = []
            for module in imported_modules.values():
                candidate = getattr(module, operation, None)
                if callable(candidate):
                    matches.append(candidate)
            unique = {
                f"{candidate.__module__}.{candidate.__qualname__}": candidate
                for candidate in matches
            }
            if not unique:
                failures.append({
                    "kind": "adapter_operation_resolution_failed",
                    "adapter_id": adapter_id,
                    "operation": operation,
                    "matches": sorted(unique),
                })
                continue
            # One operation name may intentionally exist in multiple declared
            # modules (for example Claude and Codex pricing readers).  Each
            # resolved implementation is a distinct static callsite and must
            # be exercised at runtime.
            for call_id, function in sorted(unique.items()):
                source_path = inspect.getsourcefile(function)
                try:
                    source_lines, line = inspect.getsourcelines(function)
                    source_tree = ast.parse(textwrap.dedent("".join(source_lines)))
                    ast_definitions = [
                        node.name
                        for node in ast.walk(source_tree)
                        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                    ]
                except (OSError, TypeError, SyntaxError) as exc:
                    line = 0
                    ast_definitions = []
                    failures.append({
                        "kind": "static_ast_parse_failed",
                        "callsite_id": call_id,
                        "detail": repr(exc),
                    })
                if function.__name__ not in ast_definitions:
                    failures.append({
                        "kind": "static_ast_definition_missing",
                        "callsite_id": call_id,
                        "expected_function": function.__name__,
                    })
                relative_source = Path(*function.__module__.split(".")).with_suffix(".py")
                bound_source = repo_root / relative_source
                if not bound_source.is_file():
                    failures.append({
                        "kind": "static_source_binding_missing",
                        "callsite_id": call_id,
                        "path": relative_source.as_posix(),
                    })
                    bound_digest = ""
                else:
                    bound_digest = _sha256(bound_source.read_bytes())
                    if source_path and _sha256(Path(source_path).read_bytes()) != bound_digest:
                        failures.append({
                            "kind": "loaded_source_binding_mismatch",
                            "callsite_id": call_id,
                            "path": relative_source.as_posix(),
                        })
                existing = rows.setdefault(call_id, {
                    "callsite_id": call_id,
                    "module": function.__module__,
                    "qualname": function.__qualname__,
                    "source_path": relative_source.as_posix(),
                    "line": line,
                    "discovery": "ast_function_definition",
                    "adapter_ids": [],
                    "operations": [],
                })
                existing["adapter_ids"].append(adapter_id)
                existing["operations"].append(operation)
                callables[call_id] = function

    for row in rows.values():
        row["adapter_ids"] = sorted(set(row["adapter_ids"]))
        row["operations"] = sorted(set(row["operations"]))
        row["source_sha256"] = _sha256(
            (repo_root / row["source_path"]).read_bytes()
        ) if (repo_root / row["source_path"]).is_file() else ""
    return sorted(rows.values(), key=lambda row: row["callsite_id"]), failures, callables


def _invoke(function: Callable[..., Any], scratch: Path) -> Any:
    name = function.__name__
    if name == "next_plan_artifact_name":
        return function(scratch, 1)
    if name == "load_cloud_status_snapshot":
        return function(scratch / "missing-status.json")
    if name == "load_megaplan_step_io_policy":
        return function(scratch / ".megaplan" / "plans" / "a7")
    if name == "_collect_receipts":
        return function(scratch)
    if name == "_safe_read_json":
        return function(scratch / "missing.json")
    if name == "load_and_extract":
        (scratch / "execution.json").write_text("{}\n", encoding="utf-8")
        return function(scratch, "execute", 1)
    if name == "build_snapshot":
        return function(roots=(str(scratch),), process_scanner=lambda: ())
    if name == "correlate_processes_to_plans":
        return function((), ())
    if name == "scan_processes":
        return function(())
    if name in {"is_creative_mode", "is_prose_mode"}:
        return function({})
    if name == "read_json":
        path = scratch / "payload.json"
        path.write_text("{}\n", encoding="utf-8")
        return function(path)
    if name == "cost_from_usage":
        return function(10, 5, "test-model")
    if name == "estimate_tokens_from_cost":
        return function(0.01)
    raise ValueError(f"no deterministic A7 trace invocation for {function.__module__}.{name}")


def _capture_runtime_calls(
    callables: dict[str, Callable[..., Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    observed: set[str] = set()
    rows: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    target_codes = {
        function.__code__: call_id
        for call_id, function in callables.items()
        if hasattr(function, "__code__")
    }

    def profiler(frame: Any, event: str, arg: Any) -> None:
        del arg
        if event == "call" and frame.f_code in target_codes:
            observed.add(target_codes[frame.f_code])

    with tempfile.TemporaryDirectory(prefix="m11-a7-trace-") as tmp:
        scratch = Path(tmp)
        previous = sys.getprofile()
        sys.setprofile(profiler)
        try:
            for call_id, function in sorted(callables.items()):
                try:
                    result = _invoke(function, scratch)
                    outcome = type(result).__name__
                    error = ""
                except Exception as exc:
                    outcome = "error"
                    error = repr(exc)
                    failures.append({
                        "kind": "runtime_trace_invocation_failed",
                        "callsite_id": call_id,
                        "detail": error,
                    })
                rows.append({
                    "callsite_id": call_id,
                    "captured": call_id in observed,
                    "outcome_type": outcome,
                    "error": error,
                })
        finally:
            sys.setprofile(previous)
    for call_id in sorted(set(callables) - observed):
        failures.append({
            "kind": "runtime_trace_missing",
            "callsite_id": call_id,
        })
    return rows, failures


def _registry_rows(documents: dict[str, dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    return {
        "readers": [
            {"id": row.get("reader_id"), "row_hash": row.get("row_hash")}
            for row in documents["readers"].get("rows", [])
        ],
        "writers": [
            {"id": row.get("writer_id"), "row_hash": row.get("row_hash")}
            for row in documents["writers"].get("rows", [])
        ],
        "deletion": [
            {"id": row.get("entry_id"), "row_hash": row.get("row_hash")}
            for row in documents["deletion"].get("rows", [])
        ],
        "historical_adapters": [
            {"id": row.get("adapter_id")}
            for row in documents["historical_adapters"].get("adapters", [])
        ],
        "migration": [
            {"id": row.get("row_index"), "row_hash": row.get("row_hash")}
            for row in documents["migration"].get("rows", [])
        ],
    }


def _legacy_candidates(documents: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    row_sources = {
        "reader": documents["readers"].get("rows", []),
        "writer": documents["writers"].get("rows", []),
        "deletion": documents["deletion"].get("rows", []),
        "migration": documents["migration"].get("rows", []),
    }
    for source, rows in row_sources.items():
        for row in rows:
            text = json.dumps(row, sort_keys=True).lower()
            if any(term in text for term in _LEGACY_TERMS):
                candidates.append({
                    "source": source,
                    "id": (
                        row.get("reader_id") or row.get("writer_id")
                        or row.get("entry_id") or row.get("row_index")
                    ),
                    "row_hash": row.get("row_hash"),
                    "disposition": (
                        row.get("retirement_gate") or row.get("deletion_gate")
                        or "M11 evidence closure required"
                    ),
                })
    return sorted(candidates, key=lambda row: (row["source"], str(row["id"])))


def generate_a7_inventory(repo_root: Path) -> dict[str, Any]:
    documents, bindings, failures = _load_sources(repo_root)
    adapters = documents.get("historical_adapters", {}).get("adapters", [])
    static_rows, static_failures, callables = _discover_adapter_calls(
        repo_root, adapters
    )
    trace_rows, trace_failures = _capture_runtime_calls(callables)
    failures.extend(static_failures)
    failures.extend(trace_failures)

    declared = sorted(row["callsite_id"] for row in static_rows)
    runtime = sorted(
        row["callsite_id"] for row in trace_rows if row["captured"] and not row["error"]
    )
    exact = bool(declared) and declared == runtime
    if not exact:
        failures.append({
            "kind": "static_runtime_set_mismatch",
            "missing_runtime": sorted(set(declared) - set(runtime)),
            "unexpected_runtime": sorted(set(runtime) - set(declared)),
        })
    registry_rows = _registry_rows(documents)
    if any(not rows for rows in registry_rows.values()):
        failures.append({
            "kind": "empty_registry_join",
            "empty": sorted(name for name, rows in registry_rows.items() if not rows),
        })

    inventory: dict[str, Any] = {
        "schema": A7_INVENTORY_SCHEMA,
        "status": "satisfied" if not failures else "blocked",
        "source_bindings": bindings,
        "registry_rows": registry_rows,
        "legacy_candidates": _legacy_candidates(documents),
        "historical_adapter_rows": adapters,
        "static_call_sites": static_rows,
        "runtime_trace_coverage": trace_rows,
        "static_call_site_set_equality": exact,
        "declared_callsite_ids": declared,
        "runtime_callsite_ids": runtime,
        "failures": failures,
    }
    inventory["content_sha256"] = _sha256(_canonical_bytes(inventory))
    return inventory


def write_a7_inventory(repo_root: Path, output: Path) -> dict[str, Any]:
    inventory = generate_a7_inventory(repo_root)
    output_path = output if output.is_absolute() else repo_root / output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(inventory, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return inventory


__all__ = [
    "A7_INVENTORY_SCHEMA",
    "SOURCE_SPECS",
    "generate_a7_inventory",
    "write_a7_inventory",
]
