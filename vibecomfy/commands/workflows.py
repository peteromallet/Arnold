from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import vibecomfy.fetch as fetch_assets
from vibecomfy.commands._output import emit
from vibecomfy.commands.index_files import IndexReadError, print_index_error
from vibecomfy.commands._workflow_path import load_workflow_index_rows
from vibecomfy.registry.ready import (
    _resolve_ready_path,
    ready_template_ids,
    ready_template_source_info,
    workflow_from_ready,
)
from vibecomfy.runtime.session import _model_assets_from_workflow


def _cmd_workflows_list(args: argparse.Namespace) -> int:
    rows = []
    if args.ready:
        rows = [
            {"id": template_id, "media_type": "ready", "path": str(_resolve_ready_path(template_id))}
            for template_id in ready_template_ids()[: args.limit]
        ]
        return emit(rows, json=args.json, text_renderer=_render_workflow_rows)
    try:
        rows.extend(load_workflow_index_rows())
    except IndexReadError as exc:
        print_index_error(exc)
        return 1
    return emit(rows[: args.limit], json=args.json, text_renderer=_render_workflow_rows)


def _cmd_workflows_source_info(args: argparse.Namespace) -> int:
    info = ready_template_source_info(args.template_id).to_dict()
    return emit(info, json=args.json, text_renderer=lambda row: json.dumps(row, indent=2, sort_keys=True))


def _cmd_workflows_enrich_targets(args: argparse.Namespace) -> int:
    manifest = json.loads(Path(args.targets_json).read_text(encoding="utf-8"))
    enriched = enrich_target_manifest(manifest, models_root=args.models_root)
    payload = json.dumps(enriched, indent=2, sort_keys=True) + "\n"
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(payload, encoding="utf-8")
    else:
        print(payload, end="")
    return 0


def enrich_target_manifest(
    manifest: dict[str, Any],
    *,
    models_root: str | Path | None = None,
) -> dict[str, Any]:
    """Enrich a Reigh target manifest with VibeComfy source/schema/asset data."""
    root = Path(models_root) if models_root is not None else fetch_assets.models_root()
    targets = manifest.get("targets", [])
    if not isinstance(targets, list):
        raise ValueError("target manifest field `targets` must be a list")
    enriched_targets: list[dict[str, Any]] = []
    seen_template_ids: set[str] = set()
    selected_template_ids: list[str] = []
    for target in targets:
        if not isinstance(target, dict):
            continue
        template_id = target.get("template_id") or target.get("selected_template_id")
        if not isinstance(template_id, str) or not template_id:
            enriched_targets.append(
                {
                    **target,
                    "enrichment_status": "skipped",
                    "issues": [
                        {
                            "group": "workflow_source",
                            "code": "missing_template_id",
                            "severity": "error",
                            "message": "Target has no VibeComfy template_id.",
                        }
                    ],
                }
            )
            continue
        if template_id not in seen_template_ids:
            seen_template_ids.add(template_id)
            selected_template_ids.append(template_id)
        enriched_targets.append(_enrich_target(target, template_id=template_id, models_root=root))
    return {
        "schema_version": 1,
        "source_manifest_schema_version": manifest.get("schema_version"),
        "producer": "vibecomfy.workflows.enrich-targets",
        "models_root": str(root),
        "selector": manifest.get("selector", {}),
        "selection": manifest.get("selection", {}),
        "templates": selected_template_ids,
        "targets": enriched_targets,
    }


def _enrich_target(
    target: dict[str, Any],
    *,
    template_id: str,
    models_root: Path,
) -> dict[str, Any]:
    issues: list[dict[str, Any]] = []
    try:
        source_info = ready_template_source_info(template_id).to_dict()
        workflow = workflow_from_ready(template_id)
        validation_report = workflow.validate()
        try:
            api = workflow.compile("api")
            schema_summary = {
                "node_count": len(api),
                "class_types": sorted(
                    {
                        node.get("class_type")
                        for node in api.values()
                        if isinstance(node, dict) and isinstance(node.get("class_type"), str)
                    }
                ),
            }
        except Exception as exc:  # noqa: BLE001 - diagnostic payload
            schema_summary = {"compile_error": str(exc)}
            issues.append(
                {
                    "group": "schema",
                    "code": "api_compile_failed",
                    "severity": "error",
                    "message": str(exc),
                }
            )
        assets = [_asset_metadata(entry, models_root=models_root) for entry in _model_assets_from_workflow(workflow)]
        for diagnostic in source_info.get("diagnostics", []):
            issues.append({"group": "workflow_source", **diagnostic})
        for issue in validation_report.issues:
            issues.append(
                {
                    "group": "schema",
                    "code": issue.code,
                    "severity": issue.severity,
                    "message": issue.message,
                    "detail": issue.detail,
                }
            )
        for asset in assets:
            if not asset["present"]:
                issues.append(
                    {
                        "group": "assets",
                        "code": "missing_model_asset",
                        "severity": "error",
                        "message": (
                            f"Missing {asset['name']} in {asset['category']}; "
                            f"looked at {', '.join(asset['paths_checked'])}"
                        ),
                        "detail": {
                            "name": asset["name"],
                            "category": asset["category"],
                            "expected_path": asset["expected_path"],
                            "paths_checked": asset["paths_checked"],
                            "url": asset.get("url"),
                            "remediation": asset.get("remediation"),
                        },
                    }
                )
        return {
            **target,
            "template_id": template_id,
            "enrichment_status": "ok" if not any(i.get("severity") == "error" for i in issues) else "issues",
            "source": source_info,
            "schema": schema_summary,
            "assets": assets,
            "issues": issues,
        }
    except Exception as exc:  # noqa: BLE001 - target-level diagnostics must survive
        return {
            **target,
            "template_id": template_id,
            "enrichment_status": "failed",
            "issues": [
                {
                    "group": "workflow_source",
                    "code": "enrichment_failed",
                    "severity": "error",
                    "message": str(exc),
                }
            ],
        }


def _asset_metadata(entry: dict[str, str], *, models_root: Path) -> dict[str, Any]:
    name = entry["name"]
    subdir = entry.get("subdir") or entry.get("directory") or "checkpoints"
    target_path = entry.get("target_path")
    relative = Path(target_path) if target_path else Path(subdir) / name
    expected = models_root / relative
    paths_checked = [str(expected)]
    present = expected.exists()
    remediation = None
    url = entry.get("url")
    if url:
        remediation = f"mkdir -p {expected.parent} && curl -L {url} -o {expected}"
    return {
        "name": name,
        "category": subdir,
        "subdir": subdir,
        "url": url,
        "target_path": str(relative).replace("\\", "/"),
        "expected_path": str(expected),
        "paths_checked": paths_checked,
        "present": present,
        "remediation": remediation,
    }


def _render_workflow_rows(rows: list[dict]) -> str:
    return "\n".join(f"{row.get('id')}\t{row.get('media_type', '-')}\t{row.get('path')}" for row in rows)


def register(subparsers) -> None:
    workflows = subparsers.add_parser("workflows")
    workflows_sub = workflows.add_subparsers(dest="subcmd", required=True)
    workflows_list = workflows_sub.add_parser("list")
    workflows_list.add_argument("--limit", type=int, default=200)
    workflows_list.add_argument("--ready", action="store_true")
    workflows_list.add_argument("--json", action="store_true")
    workflows_list.set_defaults(func=_cmd_workflows_list)
    source_info = workflows_sub.add_parser("source-info")
    source_info.add_argument("template_id")
    source_info.add_argument("--json", action="store_true")
    source_info.set_defaults(func=_cmd_workflows_source_info)
    enrich = workflows_sub.add_parser("enrich-targets")
    enrich.add_argument("--targets-json", required=True)
    enrich.add_argument("--output")
    enrich.add_argument("--models-root", type=Path)
    enrich.set_defaults(func=_cmd_workflows_enrich_targets)


__all__ = ["enrich_target_manifest", "register"]
