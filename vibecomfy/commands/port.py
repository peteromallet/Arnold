from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from vibecomfy.porting.convert import port_convert_workflow
from vibecomfy.porting.workbench import analyze_source, load_port_source
from vibecomfy.schema import get_schema_provider


PORT_HELP = """Cheap preflight and Python materialization for ComfyUI workflow ports.

Use `port check` before manual template editing or expensive RunPod validation.
Use `port convert` to turn source workflows into Python scratchpads; pass
`--ready-id kind/name` only when intentionally producing a ready-template
candidate. Use `doctor`/`validate` after conversion, `nodes install-plan` for
custom node install planning, and `fetch` for URL-backed models. Use
`--head-check-models` only when you want network HEAD checks for model URLs.
"""


def _cmd_port_check(args: argparse.Namespace) -> int:
    schema_provider = get_schema_provider("auto")
    try:
        report = analyze_source(
            args.workflow,
            schema_provider=schema_provider,
            head_check_models=args.head_check_models,
        )
        if getattr(args, "strict_ready_template", False):
            _apply_strict_ready_template_gate(report)
    except Exception as exc:
        print(f"port check failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    payload = report.to_json()
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(_render_check(report))
    return 1 if report.has_errors else 0


def _cmd_port_convert(args: argparse.Namespace) -> int:
    schema_provider = get_schema_provider("auto")
    try:
        report = analyze_source(
            args.workflow,
            schema_provider=schema_provider,
            head_check_models=args.head_check_models,
        )
        if getattr(args, "strict_ready_template", False) or args.ready_id:
            _apply_strict_ready_template_gate(report)
        if report.has_errors:
            payload = {
                "status": "error",
                "report": report.to_json(),
                "message": "port convert stopped because port check found hard errors.",
            }
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
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(result.text, encoding="utf-8")
    payload = {
        "status": "ok" if result.validation is None or result.validation.ok else "error",
        "out": str(out),
        "conversion": result.to_json(),
        "report": report.to_json(),
    }
    _emit_convert_payload(payload, json_output=args.json)
    return 0 if payload["status"] == "ok" else 1


def _cmd_port_widgets(args: argparse.Namespace) -> int:
    schema_provider = get_schema_provider("local")
    try:
        report = analyze_source(
            args.workflow,
            schema_provider=schema_provider,
            head_check_models=False,
        )
    except Exception as exc:
        print(f"port widgets failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    widget_analysis = report.metadata.get("widget_analysis", {})
    payload = {
        "source": report.source,
        "source_hash": report.source_hash,
        **widget_analysis,
    }
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(_render_widgets(payload))
    return 0


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
    if int((report.workflow_shape or {}).get("outputs") or 0) < 1:
        report.add_issue(
            "strict_ready_missing_output_contract",
            "Strict ready-template gate requires at least one declared workflow output.",
            severity="error",
            detail={"category": "strict_ready_template"},
            recommendation="Register the expected artifact with `workflow.register_output(...)` or equivalent ready-template policy before RunPod validation.",
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
    convert.add_argument("--head-check-models", action="store_true", help="Opt in to non-downloading HEAD checks for model URLs.")
    convert.add_argument(
        "--strict-ready-template",
        action="store_true",
        help="Escalate unresolved positional widget aliases to errors. Ready-template conversion enables this by default.",
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


__all__ = ["register", "_cmd_port_check", "_cmd_port_convert", "_cmd_port_widgets"]
