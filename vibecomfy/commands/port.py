from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from vibecomfy.porting.convert import (
    ManualTemplateRefusal,
    ConversionWriteError,
    port_convert_and_write,
    port_convert_workflow,
)
from vibecomfy.porting.readability_inventory import build_readability_inventory
from vibecomfy.porting.widget_aliases import widget_alias_analysis
from vibecomfy.porting.workbench import analyze_source, load_port_source
from vibecomfy.schema import ConversionSchemaProvider, get_schema_provider
from vibecomfy.schema.cache import latest_object_info_cache_path


PORT_HELP = """Cheap preflight and Python materialization for ComfyUI workflow ports.

Use `port check` before manual template editing or expensive RunPod validation.
Use `port convert` to turn source workflows into Python scratchpads; pass
`--ready-id kind/name` only when intentionally producing a ready-template
candidate. Use `doctor`/`validate` after conversion, `nodes install-plan` for
custom node install planning, and `fetch` for URL-backed models. Use
`--head-check-models` only when you want network HEAD checks for model URLs.
"""


def _cmd_port_check(args: argparse.Namespace) -> int:
    schema_provider = _build_conversion_provider(args)
    port_mode: str = "strict_ready" if getattr(args, "strict_ready_template", False) else "auto"
    try:
        report = analyze_source(
            args.workflow,
            schema_provider=schema_provider,
            head_check_models=args.head_check_models,
            mode=port_mode,
        )
        if getattr(args, "strict_ready_template", False):
            _apply_strict_ready_template_gate(report)
    except Exception as exc:
        print(f"port check failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    _inject_schema_source_metadata(report, args)
    payload = report.to_json()
    _attach_contract_fields(payload)
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(_render_check(report))
    return 1 if report.has_errors else 0


def _cmd_port_convert(args: argparse.Namespace) -> int:
    schema_provider = _build_conversion_provider(args)
    port_mode: str = (
        "strict_ready"
        if getattr(args, "strict_ready_template", False) or args.ready_id
        else "auto"
    )
    try:
        report = analyze_source(
            args.workflow,
            schema_provider=schema_provider,
            head_check_models=args.head_check_models,
            mode=port_mode,
        )
        _inject_schema_source_metadata(report, args)
        if getattr(args, "strict_ready_template", False) or args.ready_id:
            _apply_strict_ready_template_gate(report)
        if report.has_errors:
            payload = {
                "status": "error",
                "report": report.to_json(),
                "message": "port convert stopped because port check found hard errors.",
            }
            _attach_contract_fields(payload["report"])
            _emit_convert_payload(payload, json_output=args.json)
            return 1

        loaded = load_port_source(args.workflow, schema_provider=schema_provider)
        result = port_convert_workflow(
            loaded.workflow,
            ready_id=args.ready_id,
            source_path=loaded.source_path,
            provenance=report.provenance,
            source_hash=report.source_hash,
            workflow_shape=report.workflow_shape,
            schema_provider=schema_provider,
        )
    except Exception as exc:
        print(f"port convert failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1

    out = Path(args.out)
    dry_run = getattr(args, "dry_run", False)
    diff_mode = getattr(args, "diff", False)

    try:
        write_result = port_convert_and_write(
            result,
            out,
            dry_run=dry_run,
            diff=diff_mode,
        )
    except ManualTemplateRefusal as exc:
        print(f"port convert refused: {exc}", file=sys.stderr)
        payload = {
            "status": "refused",
            "out": str(out),
            "message": str(exc),
            "conversion": result.to_json(),
            "report": report.to_json(),
        }
        _attach_contract_fields(payload["report"])
        _emit_convert_payload(payload, json_output=args.json)
        return 1
    except ConversionWriteError as exc:
        print(f"port convert failed: {exc}", file=sys.stderr)
        payload = {
            "status": "error",
            "out": str(out),
            "message": str(exc),
            "conversion": result.to_json(),
            "report": report.to_json(),
        }
        _attach_contract_fields(payload["report"])
        _emit_convert_payload(payload, json_output=args.json)
        return 1

    payload = {
        "status": "ok" if write_result["written"] or write_result["dry_run"] else "error",
        "out": str(out),
        "conversion": result.to_json(),
        "report": report.to_json(),
        "write": write_result,
    }
    _attach_contract_fields(payload["report"])
    _emit_convert_payload(payload, json_output=args.json)
    return 0


def _attach_contract_fields(payload: dict[str, Any]) -> None:
    metadata = payload.get("metadata")
    contract = metadata.get("contract") if isinstance(metadata, dict) else None
    if not isinstance(contract, dict):
        return
    payload["contract"] = contract
    payload["contract_shape"] = contract.get("contract_shape")
    payload["public_inputs"] = contract.get("public_inputs", [])
    payload["public_outputs"] = contract.get("public_outputs", [])
    payload["graph_contract"] = contract.get("graph_contract", {})


def _cmd_port_widgets(args: argparse.Namespace) -> int:
    schema_provider = get_schema_provider("local")
    try:
        loaded = load_port_source(
            args.workflow,
            schema_provider=schema_provider,
            use_comfy_converter=False,
        )
    except Exception as exc:
        print(f"port widgets failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    api_prompt = loaded.workflow.compile("api")
    widget_analysis = widget_alias_analysis(
        api_prompt,
        raw_workflow=loaded.raw_workflow,
        schema_provider=schema_provider,
    )
    payload = {
        "source": args.workflow,
        "source_hash": loaded.source_hash,
        **widget_analysis,
    }
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(_render_widgets(payload))
    return 0


def _cmd_port_inventory(args: argparse.Namespace) -> int:
    """Repo-only readability inventory for checked-in ready templates.

    ``port inventory --ready --json`` emits a deterministic, versioned JSON
    report built from the static ``ready_templates/**/*.py`` glob.  The report
    never consults plugin/cwd/user-global paths.
    """
    inventory = build_readability_inventory()
    if args.json:
        print(json.dumps(inventory.to_json(), indent=2, sort_keys=True))
    else:
        print(_render_inventory(inventory))
    return 0


def _render_inventory(inventory) -> str:
    entries = inventory.entries
    summary = inventory.summary
    flag_count = sum(1 for e in entries if e.missing_source_provenance)

    lines = [
        f"port inventory: {inventory.template_count} checked-in ready templates",
        f"missing source provenance: {flag_count}",
        f"markers: "
        + " ".join(
            f"{k.split('_', 1)[1]}={v}"
            for k, v in sorted(summary.items())
            if k.startswith("marker_")
        ),
    ]
    # Summary counts
    lines.append(
        f"issues: "
        + ", ".join(
            f"{key}={summary.get(key, 0)}"
            for key in [
                "positional_outs_total",
                "widget_n_fields_total",
                "uuid_class_types_total",
                "n_uuid_variables_total",
                "local_node_copies_total",
                "missing_output_contract",
            ]
        )
    )
    lines.append(f"app_active: {summary.get('app_active', 0)}")
    lines.append(f"templates_with_issues: {summary.get('templates_with_issues', 0)}")

    # Flagged entries
    flagged = [e for e in entries if e.missing_source_provenance]
    if flagged:
        lines.append("")
        lines.append("Flagged (no source provenance):")
        for e in flagged[:20]:
            lines.append(f"  {e.ready_id} ({e.marker})")
        if len(flagged) > 20:
            lines.append(f"  ... {len(flagged) - 20} more flagged entries; rerun with --json for full list")

    return "\n".join(lines)


def _apply_strict_ready_template_gate(report: Any) -> None:
    widget_analysis = (report.metadata or {}).get("widget_analysis") or {}
    unresolved = widget_analysis.get("unresolved_widget_aliases") or []
    schema_backed_classes = {
        str(group.get("class_type"))
        for group in widget_analysis.get("suggestions", [])
        if group.get("schema_source") != "unavailable" or group.get("suggested_schema_entry") is not None
    }
    blocked = [alias for alias in unresolved if str(alias.get("class_type")) in schema_backed_classes]
    if blocked:
        report.add_issue(
            "strict_ready_unresolved_widgets",
            (
                f"Strict ready-template gate found {len(blocked)} unresolved schema-backed positional widget alias"
                f"{'' if len(blocked) == 1 else 'es'}."
            ),
            severity="error",
            detail={
                "category": "strict_ready_template",
                "count": len(blocked),
                "examples": blocked[:20],
                "unresolved_total": len(unresolved),
            },
            recommendation=(
                "Run `vibecomfy port widgets <workflow> --json`, add schema aliases, or rewrite the template "
                "with named inputs before RunPod validation."
            ),
        )
    # Escalate any opaque_component_node_class diagnostics that are still warnings
    # (e.g. when analyze_source ran in scratchpad mode but the gate was invoked
    # separately).  Workbench strict_ready/app_active mode already emits these as
    # errors, so this is defense-in-depth.
    for issue in list(report.diagnostics):
        if issue.code != "opaque_component_node_class":
            continue
        if issue.severity == "warning":
            issue.severity = "error"
            issue.detail = dict(issue.detail or {})
            issue.detail["gate_escalation"] = "strict_ready"
            if "promotion" not in (issue.recommendation or ""):
                issue.recommendation = (
                    "Inline component/subgraph definitions with graphbuilder or ComfyUI's converter before "
                    "materializing a ready template. Do not wrap an opaque UUID runtime node in a Python "
                    "name; promotion requires real workflow-builder code with a known first-class replacement node."
                )
    if int((report.workflow_shape or {}).get("outputs") or 0) < 1:
        report.add_issue(
            "strict_ready_missing_output_contract",
            "Strict ready-template gate requires at least one public output contract.",
            severity="error",
            detail={"category": "strict_ready_template"},
            recommendation="Register the expected artifact with `bind_output(...)` so `public_outputs` describes the pre-run artifact contract before RunPod validation.",
        )


def _render_check(report: Any) -> str:
    counts = {"error": 0, "warning": 0, "info": 0}
    for issue in report.diagnostics:
        counts[issue.severity] = counts.get(issue.severity, 0) + 1
    lines = [
        f"port check: {'ok' if report.ok else 'errors found'}",
        f"source: {report.source}",
        f"nodes: {report.workflow_shape.get('runtime_nodes', 0)} runtime, {report.workflow_shape.get('helper_nodes', 0)} helper",
        f"diagnostics: {counts['error']} error, {counts['warning']} warning, {counts['info']} info",
    ]
    for issue in report.diagnostics[:12]:
        location = f" node {issue.node_id}" if issue.node_id else ""
        class_type = f" ({issue.class_type})" if issue.class_type else ""
        lines.append(f"- {issue.severity}: {issue.code}{location}{class_type}: {issue.message}")
    if len(report.diagnostics) > 12:
        lines.append(f"- ... {len(report.diagnostics) - 12} more diagnostics; rerun with --json for full details")
    if report.node_pack_suggestions:
        lines.append("Suggested custom node packs:")
        for pack in report.node_pack_suggestions:
            packages = f" (pip: {', '.join(pack.pip_packages)})" if pack.pip_packages else ""
            lines.append(f"- {pack.pack_name}: {pack.repo}{packages}")
    if report.asset_candidates:
        lines.append(f"Model asset candidates: {len(report.asset_candidates)}")
    if report.asset_checks:
        failed = sum(1 for check in report.asset_checks if not check.ok)
        lines.append(f"Model URL HEAD checks: {len(report.asset_checks) - failed} ok, {failed} failed")
    if report.recommendations:
        lines.append("Recommended next steps:")
        lines.extend(f"- {item}" for item in report.recommendations[:6])
    return "\n".join(lines)


def _build_conversion_provider(args: argparse.Namespace) -> ConversionSchemaProvider:
    runtime_enabled = getattr(args, "runtime_object_info", False)
    server_url: str | None = getattr(args, "server_url", None)
    object_info_cache = getattr(args, "object_info_cache", None)
    if object_info_cache is None and not getattr(args, "no_object_info_cache", False):
        latest = latest_object_info_cache_path()
        object_info_cache = str(latest) if latest is not None else None
    return ConversionSchemaProvider(
        object_info_cache_path=object_info_cache,
        enable_runtime=runtime_enabled,
        runtime_server_url=server_url,
    )


def _inject_schema_source_metadata(report: Any, args: argparse.Namespace) -> None:
    runtime_enabled = getattr(args, "runtime_object_info", False)
    server_url: str | None = getattr(args, "server_url", None)
    report.metadata["schema_source"] = {
        "provider": "ConversionSchemaProvider",
        "runtime_enabled": runtime_enabled,
        "server_url": server_url,
        "object_info_cache": getattr(args, "object_info_cache", None)
        or (
            None
            if getattr(args, "no_object_info_cache", False)
            else str(latest_object_info_cache_path() or "")
        ),
    }


def _emit_convert_payload(payload: dict[str, Any], *, json_output: bool) -> None:
    if json_output:
        print(json.dumps(payload, indent=2, sort_keys=True))
        return
    if payload["status"] == "ok":
        print(payload["out"])
        validation = payload["conversion"].get("validation")
        if validation:
            print(
                "validated emitted module: "
                f"import={validation['import_ok']} build={validation['build_ok']} "
                f"compile={validation['compile_ok']} schema={validation['schema_ok']}"
            )
        return
    print(payload.get("message", "port convert failed"), file=sys.stderr)
    report = payload.get("report") or {}
    for issue in (report.get("diagnostics") or [])[:12]:
        print(f"- {issue['severity']}: {issue['code']}: {issue['message']}", file=sys.stderr)


def _render_widgets(payload: dict[str, Any]) -> str:
    unresolved = payload.get("unresolved_widget_aliases") or []
    suggestions = payload.get("suggestions") or []
    lines = [
        f"port widgets: {len(unresolved)} unresolved positional widget alias"
        f"{'' if len(unresolved) == 1 else 'es'}",
        f"source: {payload.get('source')}",
    ]
    if not unresolved:
        return "\n".join(lines)
    for group in suggestions:
        lines.append(f"- {group['class_type']}: {len(group['nodes'])} node(s), source={group['schema_source']}")
        if group.get("python"):
            lines.append(f"  schema: {group['python']}")
        else:
            lines.append("  schema: unavailable from local object_info/node_index")
        for node in group["nodes"][:5]:
            inputs = ", ".join(node["unresolved_inputs"])
            lines.append(f"  node {node['node_id']}: {inputs}")
    return "\n".join(lines)


def register(subparsers) -> None:
    port = subparsers.add_parser(
        "port",
        description=PORT_HELP,
        epilog=PORT_HELP,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    port_subparsers = port.add_subparsers(dest="port_cmd", required=True)

    check = port_subparsers.add_parser(
        "check",
        help="Preflight a workflow before manual editing or RunPod validation.",
        description=PORT_HELP,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    check.add_argument("workflow")
    check.add_argument("--json", action="store_true")
    check.add_argument("--head-check-models", action="store_true", help="Opt in to non-downloading HEAD checks for model URLs.")
    check.add_argument(
        "--strict-ready-template",
        action="store_true",
        help="Escalate unresolved positional widget aliases to errors before promotion or RunPod validation.",
    )
    check.add_argument(
        "--runtime-object-info",
        action="store_true",
        help="Opt in to live /object_info schema evidence from a running ComfyUI server.",
    )
    check.add_argument(
        "--object-info-cache",
        help="Use a captured ComfyUI /object_info JSON file as offline schema evidence. Defaults to the newest out/cache/object_info*.json when present.",
    )
    check.add_argument(
        "--no-object-info-cache",
        action="store_true",
        help="Do not use cached /object_info schema evidence.",
    )
    check.add_argument(
        "--server-url",
        help="ComfyUI server URL for live /object_info (requires --runtime-object-info).",
    )
    check.set_defaults(func=_cmd_port_check)

    convert = port_subparsers.add_parser(
        "convert",
        help="Emit an importable Python scratchpad, or a ready-template candidate with --ready-id.",
        description=PORT_HELP,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    convert.add_argument("workflow")
    convert.add_argument("--out", required=True)
    convert.add_argument("--ready-id", help="Emit ready-template candidate mode; must have kind/name shape.")
    convert.add_argument("--json", action="store_true")
    convert.add_argument("--dry-run", action="store_true", help="Emit conversion payload and evidence without writing target file.")
    convert.add_argument("--diff", action="store_true", help="Produce unified diff + JSON diff metadata (implies dry-run).")
    convert.add_argument("--head-check-models", action="store_true", help="Opt in to non-downloading HEAD checks for model URLs.")
    convert.add_argument(
        "--strict-ready-template",
        action="store_true",
        help="Escalate unresolved positional widget aliases to errors. Ready-template conversion enables this by default.",
    )
    convert.add_argument(
        "--runtime-object-info",
        action="store_true",
        help="Opt in to live /object_info schema evidence from a running ComfyUI server.",
    )
    convert.add_argument(
        "--object-info-cache",
        help="Use a captured ComfyUI /object_info JSON file as offline schema evidence. Defaults to the newest out/cache/object_info*.json when present.",
    )
    convert.add_argument(
        "--no-object-info-cache",
        action="store_true",
        help="Do not use cached /object_info schema evidence.",
    )
    convert.add_argument(
        "--server-url",
        help="ComfyUI server URL for live /object_info (requires --runtime-object-info).",
    )
    convert.set_defaults(func=_cmd_port_convert)

    widgets = port_subparsers.add_parser(
        "widgets",
        help="Suggest widget-only schema entries for unresolved positional aliases.",
        description=(
            "Report widget_alias_unresolved diagnostics grouped by class and suggest "
            "widget-only schema entries from local node_index/object_info data when available."
        ),
    )
    widgets.add_argument("workflow")
    widgets.add_argument("--json", action="store_true")
    widgets.set_defaults(func=_cmd_port_widgets)

    inventory = port_subparsers.add_parser(
        "inventory",
        help="Repo-only readability inventory for checked-in ready templates.",
        description=(
            "Emit a deterministic, versioned JSON report built from the static "
            "ready_templates/**/*.py glob. Never consults plugin/cwd/user-global paths."
        ),
    )
    inventory.add_argument("--ready", action="store_true", default=True, help=argparse.SUPPRESS)
    inventory.add_argument("--json", action="store_true")
    inventory.set_defaults(func=_cmd_port_inventory)


__all__ = ["register", "_cmd_port_check", "_cmd_port_convert", "_cmd_port_inventory", "_cmd_port_widgets"]
