from __future__ import annotations

import argparse
import json
from typing import Any

from vibecomfy.cli_loader import load_workflow_any
from vibecomfy.commands._output import emit
from vibecomfy.diagnostics import DiagnosticFinding
from vibecomfy.schema import get_schema_provider, schema_provider_from_object_info_file
from vibecomfy.schema.format import format_issue
from vibecomfy.workflow import ValidationIssue, VibeNode, VibeWorkflow, WorkflowSource


def _cmd_validate_call(args: argparse.Namespace) -> int:
    try:
        kwargs = json.loads(args.kwargs)
    except json.JSONDecodeError:
        return _emit_parse_error(
            "invalid_kwargs_json",
            "--kwargs must be valid JSON.",
            json_output=args.json,
        )
    if not isinstance(kwargs, dict):
        return _emit_parse_error(
            "kwargs_not_object",
            "--kwargs JSON must decode to an object.",
            json_output=args.json,
        )

    schema_provider, provider_payload = _provider_from_args(args)
    workflow = VibeWorkflow(
        id=f"port-validate-call-{args.class_type}",
        source=WorkflowSource(id="port validate-call", source_type="cli"),
    )
    workflow.nodes["1"] = VibeNode(id="1", class_type=args.class_type, inputs=kwargs)
    report = workflow.validate(schema_provider=schema_provider)
    payload = {
        "class_type": args.class_type,
        "ok": report.ok,
        "issues": [_issue_payload(issue) for issue in report.issues],
        "status": "ok" if report.ok else "error",
        "provider": provider_payload,
    }
    emit(payload, json=args.json, text_renderer=_render_report_payload)
    return 0 if report.ok else 1


def _cmd_check(args: argparse.Namespace) -> int:
    schema_provider, provider_payload = _provider_from_args(args)
    workflow = load_workflow_any(args.path)
    report = workflow.validate(schema_provider=schema_provider)
    payload = {
        "workflow_id": workflow.id,
        "ok": report.ok,
        "issues": [_issue_payload(issue) for issue in report.issues],
        "status": "ok" if report.ok else "error",
        "provider": provider_payload,
    }
    emit(payload, json=args.json, text_renderer=_render_report_payload)
    return 0 if report.ok else 1


def _provider_from_args(args: argparse.Namespace) -> tuple[Any, dict[str, str | None]]:
    if args.object_info_cache:
        provider = schema_provider_from_object_info_file(args.object_info_cache)
        return provider, {"kind": "object_info_file", "path": str(args.object_info_cache)}
    provider = get_schema_provider("auto")
    return provider, {"kind": provider.__class__.__name__}


def _emit_parse_error(code: str, message: str, *, json_output: bool) -> int:
    finding = DiagnosticFinding(code=code, message=message, severity="error")
    payload = {"status": "error", "errors": [_parse_error_payload(finding)]}
    emit(payload, json=json_output, text_renderer=_render_parse_error)
    return 2


def _render_parse_error(payload: dict[str, Any]) -> str:
    return "\n".join(error["message"] for error in payload["errors"])


def _render_report_payload(payload: dict[str, Any]) -> str:
    if payload["ok"]:
        return "ok"
    return "\n".join(format_issue(_issue_from_payload(issue)) for issue in payload["issues"])


def _issue_payload(issue: ValidationIssue) -> dict[str, Any]:
    detail = issue.detail or {}
    finding = DiagnosticFinding(
        code=issue.code,
        message=issue.message,
        severity=issue.severity,
        node_id=str(detail["node_id"]) if "node_id" in detail else None,
        class_type=str(detail["class_type"]) if "class_type" in detail else None,
        detail=detail,
    )
    return _port_issue_payload(finding)


def _port_issue_payload(finding: DiagnosticFinding) -> dict[str, Any]:
    return {
        "code": finding.code,
        "message": finding.message,
        "severity": finding.severity,
        "detail": finding.detail or {},
    }


def _parse_error_payload(finding: DiagnosticFinding) -> dict[str, str]:
    return {"code": finding.code, "message": finding.message}


def _issue_from_payload(payload: dict[str, Any]) -> ValidationIssue:
    return ValidationIssue(
        code=payload["code"],
        message=payload["message"],
        severity=payload.get("severity", "error"),
        detail=payload.get("detail") or {},
    )


def register(subparsers) -> None:
    port = subparsers.add_parser("port")
    port_subparsers = port.add_subparsers(dest="port_cmd", required=True)

    validate_call = port_subparsers.add_parser("validate-call")
    validate_call.add_argument("class_type")
    validate_call.add_argument("--kwargs", required=True, help="JSON object of node input values.")
    validate_call.add_argument("--json", action="store_true")
    validate_call.add_argument("--object-info-cache", help="Path to a ComfyUI object_info JSON cache.")
    validate_call.set_defaults(func=_cmd_validate_call)

    check = port_subparsers.add_parser("check")
    check.add_argument("path")
    check.add_argument("--json", action="store_true")
    check.add_argument("--object-info-cache", help="Path to a ComfyUI object_info JSON cache.")
    check.set_defaults(func=_cmd_check)
