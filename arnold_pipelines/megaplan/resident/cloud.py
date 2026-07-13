"""Constrained Megaplan cloud operation wrappers for resident tools."""

from __future__ import annotations

import argparse
import contextlib
from dataclasses import dataclass, field
from io import StringIO
import json
from pathlib import Path
from typing import Any, Literal, Mapping, Protocol

from arnold_pipelines.megaplan.cloud.cli import build_cloud_parser, run_cloud_cli
from .provenance import provenance_scope

CloudClassification = Literal["running", "blocked", "failed", "gate-needed", "completed", "unknown"]
CloudOperation = Literal[
    "cloud_status",
    "cloud_status_chain",
    "cloud_start_chain",
    "cloud_bootstrap",
    "cloud_resume",
    "cloud_logs",
]


@dataclass(frozen=True)
class CloudToolRequest:
    operation: CloudOperation
    target_id: str | None = None
    arguments: dict[str, str] = field(default_factory=dict)
    confirmed: bool = False
    launch_provenance: Mapping[str, Any] | None = None


@dataclass(frozen=True)
class CloudToolResult:
    classification: CloudClassification
    summary: str
    details: dict[str, object] = field(default_factory=dict)


class CloudToolBackend(Protocol):
    async def run(self, request: CloudToolRequest) -> CloudToolResult:
        """Execute one constrained cloud operation."""


class CloudCliBackend:
    """Default resident backend that dispatches through existing cloud CLI code."""

    async def run(self, request: CloudToolRequest) -> CloudToolResult:
        argv = _argv_for_request(request)
        root = Path(request.arguments.get("project_root") or ".").expanduser().resolve()
        parser = argparse.ArgumentParser()
        build_cloud_parser(parser.add_subparsers(dest="command", required=True))
        args = parser.parse_args(["cloud", *argv])
        stdout = StringIO()
        stderr = StringIO()
        with provenance_scope(request.launch_provenance), contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = run_cloud_cli(root, args)
        output = stdout.getvalue().strip()
        error_output = stderr.getvalue().strip()
        payload = _json_payload(output)
        classification = classify_cloud_payload(payload or {"returncode": code, "stderr": error_output})
        ok = code == 0
        summary = _summary_for_payload(request.operation, classification, payload, ok=ok)
        return CloudToolResult(
            classification=classification if ok else "failed",
            summary=summary,
            details={
                "returncode": code,
                "stdout": output,
                "stderr": error_output,
                "payload": payload,
                "argv": argv,
            },
        )


def classify_cloud_payload(payload: object) -> CloudClassification:
    """Classify status/chain payloads without depending on provider-specific text."""
    flat = " ".join(str(value).lower() for value in _walk_values(payload))
    if not flat.strip():
        return "unknown"
    if any(token in flat for token in ("gate-needed", "gate_needed", "gate pending", "gate_pending", "state_gated")):
        return "gate-needed"
    if any(token in flat for token in ("failed", "failure", "error", "state_failed", "traceback")):
        return "failed"
    if any(token in flat for token in ("blocked", "execution_blocked", "state_blocked")):
        return "blocked"
    if any(token in flat for token in ("completed", "complete", "done", "success", "state_done", "plan_done")):
        return "completed"
    if any(token in flat for token in ("running", "starting", "queued", "in_progress", "state_executing", "state_planning")):
        return "running"
    if isinstance(payload, dict) and payload.get("next_step"):
        return "running"
    return "unknown"


def progress_kind_for_classification(classification: CloudClassification) -> str:
    if classification == "completed":
        return "plan_done"
    if classification == "failed":
        return "plan_failed"
    if classification == "gate-needed":
        return "gate_pending"
    if classification == "blocked":
        return "execution_blocked"
    if classification == "running":
        return "phase_start"
    return "phase_end"


def cloud_run_status_for_classification(classification: CloudClassification) -> str:
    """Map resident cloud classifications onto CloudRun.status values."""
    if classification == "completed":
        return "completed"
    if classification == "failed":
        return "failed"
    if classification == "blocked":
        return "blocked"
    if classification == "gate-needed":
        return "gate-needed"
    if classification == "running":
        return "running"
    return "unknown"


def _argv_for_request(request: CloudToolRequest) -> list[str]:
    args = request.arguments
    cloud_yaml = args.get("cloud_yaml")
    argv: list[str] = []
    if request.operation == "cloud_status":
        argv = ["status"]
        if plan := args.get("plan"):
            argv.extend(["--plan", plan])
    elif request.operation == "cloud_status_chain":
        argv = ["status", "--chain"]
        if remote_spec := args.get("remote_spec"):
            argv.extend(["--remote-spec", remote_spec])
    elif request.operation == "cloud_start_chain":
        spec = args.get("spec")
        if not spec:
            raise ValueError("cloud_start_chain requires spec")
        argv = ["chain", spec]
        if idea_dir := args.get("idea_dir"):
            argv.extend(["--idea-dir", idea_dir])
        _append_repo_args(argv, args)
    elif request.operation == "cloud_bootstrap":
        idea_file = args.get("idea_file")
        if not idea_file:
            raise ValueError("cloud_bootstrap requires idea_file")
        argv = ["bootstrap", idea_file]
        if plan_name := args.get("plan_name"):
            argv.extend(["--plan-name", plan_name])
        if robustness := args.get("robustness"):
            argv.extend(["--robustness", robustness])
        _append_repo_args(argv, args)
    elif request.operation == "cloud_resume":
        argv = ["resume"]
        if plan := args.get("plan"):
            argv.extend(["--plan", plan])
    elif request.operation == "cloud_logs":
        argv = ["logs"]
        if args.get("no_follow") == "true":
            argv.append("--no-follow")
    else:
        raise ValueError(f"unsupported cloud operation: {request.operation}")
    if cloud_yaml:
        argv.extend(["--cloud-yaml", cloud_yaml])
    return argv


def _append_repo_args(argv: list[str], args: dict[str, str]) -> None:
    if repo_url := args.get("repo_url"):
        argv.extend(["--repo-url", repo_url])
    if repo_branch := args.get("repo_branch"):
        argv.extend(["--repo-branch", repo_branch])
    if repo_workspace := args.get("repo_workspace"):
        argv.extend(["--repo-workspace", repo_workspace])


def _summary_for_payload(
    operation: CloudOperation,
    classification: CloudClassification,
    payload: object,
    *,
    ok: bool,
) -> str:
    if not ok:
        return f"{operation} failed"
    if isinstance(payload, dict):
        next_step = payload.get("next_step")
        if isinstance(next_step, str) and next_step:
            return f"{operation}: next step {next_step}"
        summary = payload.get("summary")
        if isinstance(summary, dict):
            current = summary.get("current")
            if current:
                return f"{operation}: {current}"
    return f"{operation}: {classification}"


def _json_payload(text: str) -> object | None:
    if not text:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def _walk_values(value: object) -> list[object]:
    if isinstance(value, dict):
        values: list[object] = []
        for key, item in value.items():
            values.append(key)
            values.extend(_walk_values(item))
        return values
    if isinstance(value, list):
        values = []
        for item in value:
            values.extend(_walk_values(item))
        return values
    return [value]
