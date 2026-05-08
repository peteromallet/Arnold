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
    convert.set_defaults(func=_cmd_port_convert)


__all__ = ["register", "_cmd_port_check", "_cmd_port_convert"]
