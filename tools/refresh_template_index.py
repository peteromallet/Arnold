"""Refresh the checked-in ready-template discovery index.

The index is a lightweight, static artifact for downstream tools that should
not import every ready template just to answer "does this template id exist?".
It is derived from the same runtime discovery path used by
``vibecomfy.registry.ready`` so checked-in metadata cannot drift from the
actual ready-template surface.
"""
from __future__ import annotations

import argparse
import ast
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

from vibecomfy.registry.ready import ready_template_ids
from vibecomfy.registry.static_contract import extract_ready_template_contract


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = REPO_ROOT / "template_index.json"
DEFAULT_COVERAGE = REPO_ROOT / "workflow_corpus" / "manifests" / "coverage.json"


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Refresh template_index.json from ready_templates discovery.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--check", action="store_true", help="Fail if the output file is stale.")
    args = parser.parse_args(argv)

    generated_at = _existing_generated_at(args.output)
    payload = build_template_index(generated_at=generated_at)
    rendered = json.dumps(payload, indent=2, sort_keys=False) + "\n"

    if args.check:
        current = args.output.read_text(encoding="utf-8") if args.output.exists() else None
        if current != rendered:
            print(f"{args.output} is stale; run `python -m tools.refresh_template_index`.", flush=True)
            return 1
        return 0

    args.output.write_text(rendered, encoding="utf-8")
    print(f"wrote {args.output} ({payload['template_count']} templates)")
    return 0


def build_template_index(*, generated_at: str | None = None) -> dict[str, Any]:
    generated_at = generated_at or _existing_generated_at(DEFAULT_OUTPUT)
    coverage = _load_coverage_by_template_id(DEFAULT_COVERAGE)
    templates: list[dict[str, Any]] = []
    for template_id in ready_template_ids():
        path = _ready_template_path(template_id)
        metadata, requirements = _ready_template_metadata(REPO_ROOT / path)
        static_contract = extract_ready_template_contract(REPO_ROOT / path)
        coverage_row = coverage.get(template_id, {})
        coverage_tier = metadata.get("coverage_tier") or coverage_row.get("coverage_tier", "")
        templates.append(
            {
                "id": template_id,
                "path": path,
                "capability": metadata.get("capability") or coverage_row.get("task", ""),
                "coverage_tier": coverage_tier,
                "custom_nodes": static_contract.get("custom_nodes")
                or sorted(_string_items(requirements.get("custom_nodes"))),
                "model_count": static_contract.get("model_count", len(_list_items(requirements.get("models")))),
                "public_inputs": static_contract["public_inputs"],
                "public_outputs": static_contract["public_outputs"],
                "artifact_expectations": static_contract["artifact_expectations"],
                "static_diagnostics": static_contract["diagnostics"],
                "public_input_status": _public_status(static_contract["public_inputs"], static_contract["diagnostics"]),
                "public_output_status": _public_status(static_contract["public_outputs"], static_contract["diagnostics"]),
                "readiness_class": static_contract["readiness_class"],
                "marker": static_contract["marker"],
                "app_active": static_contract["app_active"] or coverage_tier == "required",
                "blocked": static_contract["blocked"] or coverage_tier == "blocked",
                "reference": static_contract["reference"] or coverage_tier == "reference",
                "supplemental": static_contract["supplemental"] or coverage_tier == "supplemental",
            }
        )

    return {
        "generated_at": generated_at or datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "generated_from": "runtime ready template discovery",
        "include_rule": "find ready_templates -type f -name '*.py' ! -name '_*' | sort",
        "exclude_rule": "exclude __init__.py and files whose basename starts with '_' to match vibecomfy.registry.ready._template_paths",
        "template_count": len(templates),
        "templates": templates,
    }


def _ready_template_path(template_id: str) -> str:
    return (Path("ready_templates") / f"{template_id}.py").as_posix()


def _ready_template_metadata(path: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except (OSError, SyntaxError):
        return {}, {}
    assignments: dict[str, Any] = {}
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if not isinstance(target, ast.Name) or target.id not in {"READY_METADATA", "READY_REQUIREMENTS"}:
                continue
            assignments[target.id] = _literal_value(node.value, assignments)
    metadata = assignments.get("READY_METADATA")
    requirements = assignments.get("READY_REQUIREMENTS")
    return (
        metadata if isinstance(metadata, dict) else {},
        requirements if isinstance(requirements, dict) else {},
    )


def _literal_value(node: ast.AST, assignments: dict[str, Any]) -> Any:
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.List):
        return [_literal_value(item, assignments) for item in node.elts]
    if isinstance(node, ast.Tuple):
        return tuple(_literal_value(item, assignments) for item in node.elts)
    if isinstance(node, ast.Dict):
        return {
            _literal_value(key, assignments): _literal_value(value, assignments)
            for key, value in zip(node.keys, node.values)
            if key is not None
        }
    if isinstance(node, ast.Name):
        return assignments.get(node.id)
    if isinstance(node, ast.Subscript):
        value = _literal_value(node.value, assignments)
        key = _literal_value(node.slice, assignments)
        if isinstance(value, dict):
            return value.get(key)
    try:
        return ast.literal_eval(node)
    except (ValueError, TypeError):
        return None


def _list_items(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _string_items(value: Any) -> list[str]:
    return [item for item in _list_items(value) if isinstance(item, str)]


def _public_status(items: list[dict[str, Any]], diagnostics: list[dict[str, Any]]) -> str:
    if any(item.get("severity") == "error" for item in diagnostics):
        return "error"
    if items:
        return "declared"
    if diagnostics:
        return "partial"
    return "missing"


def _existing_generated_at(path: Path) -> str | None:
    if not path.exists():
        return None
    try:
        current = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    value = current.get("generated_at") if isinstance(current, dict) else None
    return value if isinstance(value, str) and value else None


def _load_coverage_by_template_id(path: Path) -> dict[str, dict[str, Any]]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    workflows = data.get("workflows", []) if isinstance(data, dict) else []
    result: dict[str, dict[str, Any]] = {}
    for item in workflows:
        if not isinstance(item, dict):
            continue
        keys: list[str] = []
        workflow_id = item.get("id")
        media = item.get("media")
        ready_template = item.get("ready_template")
        if isinstance(workflow_id, str):
            keys.append(workflow_id)
            if isinstance(media, str):
                keys.append(f"{media}/{workflow_id}")
        if isinstance(ready_template, str):
            keys.append(ready_template)
        for key in keys:
            result[key] = item
    return result


if __name__ == "__main__":
    raise SystemExit(main())
