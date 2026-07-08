"""Stable fingerprints for canonical Megaplan workflow package resources."""

from __future__ import annotations

import ast
import hashlib
import json
from collections.abc import Mapping
from dataclasses import fields, is_dataclass
from enum import Enum
from pathlib import Path
from typing import Any

from arnold.workflow.compiler import compile_pipeline
from arnold.workflow.source_compiler import lower_workflow_file


CANONICAL_SOURCE_RESOURCE_PATH = "arnold_pipelines/megaplan/workflows/workflow.pypeline"
WORKFLOW_MODULE_RESOURCE_PATH = "arnold_pipelines/megaplan/workflows/workflow.py"
PROHIBITED_WRAPPER_TOKENS = (
    "SOURCE_",
    "handler_ref",
    "route_bindings",
    "manifest_hash",
    "build_manifest",
    "build_node",
    "node_builder",
    "generic dispatch",
)
WORKFLOW_SHIM_PROHIBITED_TOKENS = (
    "@workflow",
    "planning_workflow",
    "SOURCE_CRITIQUE",
    "SOURCE_EXECUTE",
    "handler_ref",
    "route_bindings",
)


def _stable_json_dump(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def _stable_payload_sha256(payload: Any) -> str:
    return f"sha256:{hashlib.sha256(_stable_json_dump(payload).encode('utf-8')).hexdigest()}"


def _sha256_text(text: str) -> str:
    return f"sha256:{hashlib.sha256(text.encode('utf-8')).hexdigest()}"


def _build_path_aliases(workflow_source_path: Path, workflow_module_path: Path) -> dict[str, str]:
    aliases: dict[str, str] = {}
    for actual_path, canonical_path in (
        (workflow_source_path, CANONICAL_SOURCE_RESOURCE_PATH),
        (workflow_module_path, WORKFLOW_MODULE_RESOURCE_PATH),
    ):
        aliases[actual_path.as_posix()] = canonical_path
        try:
            aliases[actual_path.resolve().as_posix()] = canonical_path
        except FileNotFoundError:
            pass
    return aliases


def _normalize_for_fingerprint(value: Any, *, path_aliases: dict[str, str]) -> Any:
    if is_dataclass(value):
        return {
            field.name: _normalize_for_fingerprint(
                getattr(value, field.name),
                path_aliases=path_aliases,
            )
            for field in fields(value)
        }
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Mapping):
        return {
            str(key): _normalize_for_fingerprint(item, path_aliases=path_aliases)
            for key, item in sorted(value.items(), key=lambda entry: str(entry[0]))
        }
    if isinstance(value, (tuple, list)):
        return [_normalize_for_fingerprint(item, path_aliases=path_aliases) for item in value]
    if isinstance(value, Path):
        raw = value.as_posix()
        return path_aliases.get(raw, raw)
    if isinstance(value, str):
        raw = value.replace("\\", "/")
        return path_aliases.get(raw, raw)
    return value


def canonical_workflow_fingerprints(
    *,
    workflow_source_path: Path,
    workflow_module_path: Path,
) -> dict[str, Any]:
    """Return stable source and lowered-semantic fingerprints for Megaplan resources."""

    resolved_source_path = workflow_source_path.resolve()
    resolved_module_path = workflow_module_path.resolve()
    workflow_source_text = resolved_source_path.read_text(encoding="utf-8")
    workflow_module_text = resolved_module_path.read_text(encoding="utf-8")

    lowered_pipeline = lower_workflow_file(resolved_source_path)
    manifest = compile_pipeline(lowered_pipeline)
    lowered_payload = _normalize_for_fingerprint(
        lowered_pipeline,
        path_aliases=_build_path_aliases(resolved_source_path, resolved_module_path),
    )

    workflow_tree = ast.parse(workflow_source_text)
    function = next(node for node in workflow_tree.body if isinstance(node, ast.FunctionDef))

    return {
        "canonical_source_path": CANONICAL_SOURCE_RESOURCE_PATH,
        "canonical_source_sha256": _sha256_text(workflow_source_text),
        "workflow_module_path": WORKFLOW_MODULE_RESOURCE_PATH,
        "workflow_module_sha256": _sha256_text(workflow_module_text),
        "lowered_semantics_sha256": _stable_payload_sha256(lowered_payload),
        "compiled_manifest_hash": manifest.manifest_hash,
        "compiled_topology_hash": manifest.topology_hash,
        "lowered_step_count": len(lowered_pipeline.steps),
        "lowered_route_count": len(lowered_pipeline.routes),
        "contains_while": any(isinstance(node, ast.While) for node in ast.walk(function)),
        "if_count": sum(isinstance(node, ast.If) for node in ast.walk(function)),
        "called_names": sorted(
            {
                node.func.id
                for node in ast.walk(function)
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
            }
        ),
        "branch_names": sorted(
            {
                node.left.id
                for node in ast.walk(function)
                if isinstance(node, ast.Compare) and isinstance(node.left, ast.Name)
            }
        ),
        "prohibited_hits": [
            token for token in PROHIBITED_WRAPPER_TOKENS if token in workflow_source_text
        ],
        "workflow_py_mentions_pypeline": "workflow.pypeline" in workflow_module_text,
        "workflow_py_prohibited_hits": [
            token for token in WORKFLOW_SHIM_PROHIBITED_TOKENS if token in workflow_module_text
        ],
    }
