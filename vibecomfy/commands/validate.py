from __future__ import annotations

import argparse
import sys
import traceback
from typing import Any

from vibecomfy.cli_loader import load_workflow_any
from vibecomfy.commands._output import emit
from vibecomfy.schema import get_schema_provider
from vibecomfy.schema.format import format_issue
from vibecomfy.workflow import ValidationIssue, ValidationReport, VibeWorkflow


def _cmd_validate(args: argparse.Namespace) -> int:
    try:
        schema_provider = None if args.no_schema else get_schema_provider("auto")
        workflow = load_workflow_any(args.path)
        report = workflow.validate(schema_provider=schema_provider)
    except Exception as exc:
        if args.json:
            emit(_exception_payload(args.path, exc), json=True, text_renderer=_render_exception_payload)
            return 1
        traceback.print_exc(file=sys.stderr)
        print(f"python_build_error: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1

    payload = _report_payload(workflow, report)
    if not report.ok:
        if args.json:
            emit(payload, json=True, text_renderer=_render_report_payload)
            return 1
        for issue in report.issues:
            print(f"{issue.severity}: {format_issue(issue)}", file=sys.stderr)
        return 1
    if args.json:
        return emit(payload, json=True, text_renderer=_render_report_payload)
    print("ok")
    return 0


def _report_payload(workflow: VibeWorkflow, report: ValidationReport) -> dict[str, Any]:
    return {
        "workflow_id": workflow.id,
        "ok": report.ok,
        "status": "ok" if report.ok else "error",
        "issues": [_issue_payload(issue) for issue in report.issues],
    }


def _issue_payload(issue: ValidationIssue) -> dict[str, Any]:
    return {
        "code": issue.code,
        "message": issue.message,
        "severity": issue.severity,
        "detail": issue.detail or {},
    }


def _exception_payload(path: str, exc: Exception) -> dict[str, Any]:
    return {
        "path": path,
        "ok": False,
        "status": "error",
        "errors": [
            {
                "code": "workflow_load_error",
                "type": type(exc).__name__,
                "message": str(exc),
            }
        ],
    }


def _render_report_payload(payload: dict[str, Any]) -> str:
    if payload["ok"]:
        return "ok"
    return "\n".join(format_issue(_issue_from_payload(issue)) for issue in payload["issues"])


def _render_exception_payload(payload: dict[str, Any]) -> str:
    return "\n".join(f"{error['type']}: {error['message']}" for error in payload["errors"])


def _issue_from_payload(payload: dict[str, Any]) -> ValidationIssue:
    return ValidationIssue(
        code=payload["code"],
        message=payload["message"],
        severity=payload.get("severity", "error"),
        detail=payload.get("detail") or {},
    )


def register(subparsers) -> None:
    validate = subparsers.add_parser("validate")
    validate.add_argument("path")
    validate.add_argument("--json", action="store_true")
    validate.add_argument("--no-schema", action="store_true", help="Skip schema validation; run structural-only.")
    validate.set_defaults(func=_cmd_validate)
