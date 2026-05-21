from __future__ import annotations

import argparse
import ast
import json
import re
import sys
import traceback
from pathlib import Path

from vibecomfy.cli_loader import load_workflow_any
from vibecomfy.porting.emitter import _build_subgraph_def, _disambiguated_subgraph_slugs
from vibecomfy.schema import get_schema_provider
from vibecomfy.schema.format import format_issue


def _cmd_validate(args: argparse.Namespace) -> int:
    schema_provider = None if args.no_schema else get_schema_provider("auto")
    try:
        workflow = load_workflow_any(args.path)
        report = workflow.validate(schema_provider=schema_provider)
    except Exception as exc:
        traceback.print_exc(file=sys.stderr)
        print(f"python_build_error: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    if not report.ok:
        for issue in report.issues:
            print(f"{issue.severity}: {format_issue(issue)}", file=sys.stderr)
        return 1
    if getattr(args, "check_freshness", False):
        drift = _subgraph_freshness_diagnostics(Path(args.path))
        if drift:
            for item in drift:
                print(f"error: {item}", file=sys.stderr)
            return 1
    print("ok")
    return 0


def register(subparsers) -> None:
    validate = subparsers.add_parser("validate")
    validate.add_argument("path")
    validate.add_argument("--backend", default="api")
    validate.add_argument("--no-schema", action="store_true", help="Skip schema validation; run structural-only.")
    validate.add_argument("--check-freshness", action="store_true", help="Check materialized subgraph source hashes against source workflow JSON.")
    validate.set_defaults(func=_cmd_validate)


def _subgraph_freshness_diagnostics(template_path: Path) -> list[str]:
    if not template_path.exists() or template_path.suffix != ".py":
        return []
    source = template_path.read_text(encoding="utf-8")
    expected = dict(re.findall(r"subgraph ([0-9a-fA-F-]{36}).*?\n\s*# vibecomfy source hash: sha256:([0-9a-f]{64})", source))
    if not expected:
        return []
    source_workflow = _source_workflow_from_template(source)
    if source_workflow is None:
        return [f"{template_path}: materialized subgraph hashes present but no source_workflow metadata was found"]
    source_path = (Path.cwd() / source_workflow).resolve()
    if not source_path.exists():
        return [f"{template_path}: source workflow not found: {source_workflow}"]
    raw = json.loads(source_path.read_text(encoding="utf-8"))
    definitions = raw.get("definitions") if isinstance(raw, dict) else None
    subgraphs = definitions.get("subgraphs") if isinstance(definitions, dict) else None
    if isinstance(subgraphs, dict):
        raw_by_id = {str(item.get("id")): item for item in subgraphs.values() if isinstance(item, dict) and item.get("id")}
    elif isinstance(subgraphs, list):
        raw_by_id = {str(item.get("id")): item for item in subgraphs if isinstance(item, dict) and item.get("id")}
    else:
        return [f"{template_path}: source workflow has no subgraph definitions"]
    slugs = _disambiguated_subgraph_slugs(raw_by_id)
    diagnostics: list[str] = []
    for subgraph_id, expected_hash in sorted(expected.items()):
        raw_subgraph = raw_by_id.get(subgraph_id)
        if raw_subgraph is None:
            diagnostics.append(f"{template_path}: source subgraph missing: {subgraph_id}")
            continue
        actual = _build_subgraph_def(raw_subgraph, slug=slugs.get(subgraph_id, f"subgraph_{subgraph_id[:8]}"), source_path=source_workflow).source_hash
        if actual != expected_hash:
            diagnostics.append(f"{template_path}: subgraph {subgraph_id} source hash changed: {expected_hash} -> {actual}")
    return diagnostics


def _source_workflow_from_template(source: str) -> str | None:
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if not isinstance(node.func, ast.Attribute) or node.func.attr != "build":
            continue
        for kw in node.keywords:
            if kw.arg in {"source_workflow", "provenance"}:
                try:
                    value = ast.literal_eval(kw.value)
                except Exception:
                    continue
                if isinstance(value, str):
                    return value
                if isinstance(value, dict) and isinstance(value.get("source_workflow"), str):
                    return value["source_workflow"]
    return None
