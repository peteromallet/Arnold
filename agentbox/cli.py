"""Command line interface for AgentBox."""

from __future__ import annotations

import argparse
from dataclasses import asdict, is_dataclass
from datetime import datetime
import json
import subprocess
import sys
from collections.abc import Sequence
from enum import Enum
from pathlib import Path
from typing import Any
from uuid import uuid4

from arnold.runtime.durable_ops import ResourceType, TypedResource

from agentbox.adapters import get_operation_adapter, list_operation_adapters
from agentbox.config import AgentBoxConfigError, load_agentbox_config
from agentbox.operations import (
    AgentBoxOperationError,
    list_agentbox_operations,
    load_agentbox_operation,
    open_operation_store,
)
from agentbox.reconcile import reconcile
from agentbox.run_dirs import run_dir_paths
from agentbox.tmux import attach_argv, capture_pane, inspect_session


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="agentbox",
        description="AgentBox host provider CLI.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Write stable JSON output.",
    )
    subparsers = parser.add_subparsers(dest="command")

    run = subparsers.add_parser("run", help="Run a registered AgentBox operation adapter.")
    run.add_argument("--repo", required=True, help="Registered AgentBox repository name.")
    run.add_argument(
        "--kind",
        required=True,
        choices=[adapter.kind for adapter in list_operation_adapters()],
        help="Registered operation adapter kind.",
    )
    run.add_argument("--spec", required=True, help="Operation spec path.")
    run.add_argument("--operation-id")
    run.add_argument("--json", action="store_true", help="Write stable JSON output.")

    status = subparsers.add_parser("status", help="Show AgentBox host operation status.")
    status.add_argument("operation_id", nargs="?")
    status.add_argument("--json", action="store_true", help="Write stable JSON output.")

    logs = subparsers.add_parser("logs", help="Show bounded AgentBox host logs.")
    logs.add_argument("operation_id")
    logs.add_argument("--lines", type=_positive_int, default=100)
    logs.add_argument("--stream", choices=("stdout", "stderr", "all"), default="all")
    logs.add_argument("--json", action="store_true", help="Write stable JSON output.")

    attach = subparsers.add_parser("attach", help="Attach to a live AgentBox host session.")
    attach.add_argument("operation_id")

    reconcile_parser = subparsers.add_parser(
        "reconcile",
        help="Report AgentBox host-local state without mutating it.",
    )
    reconcile_parser.add_argument("--json", action="store_true", help="Write stable JSON output.")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return int(exc.code) if isinstance(exc.code, int) else 1
    if args.command is None:
        return 0

    json_output = bool(getattr(args, "json", False))
    try:
        config = load_agentbox_config()
        if args.command == "run":
            return _run(
                config,
                repo_name=args.repo,
                kind=args.kind,
                spec_path=args.spec,
                operation_id=args.operation_id,
                json_output=json_output,
            )
        if args.command == "status":
            return _status(config, args.operation_id, json_output=json_output)
        if args.command == "logs":
            return _logs(
                config,
                args.operation_id,
                lines=args.lines,
                stream=args.stream,
                json_output=json_output,
            )
        if args.command == "attach":
            return _attach(config, args.operation_id)
        if args.command == "reconcile":
            return _reconcile(config, json_output=json_output)
    except (AgentBoxConfigError, AgentBoxOperationError, FileNotFoundError, ValueError) as exc:
        return _diagnostic(str(exc), json_output=json_output)
    return _diagnostic(f"unknown command: {args.command}", json_output=json_output)


def _run(
    config: Any,
    *,
    repo_name: str,
    kind: str,
    spec_path: str,
    operation_id: str | None,
    json_output: bool,
) -> int:
    operation_id = operation_id or _new_operation_id(kind)
    try:
        registration = get_operation_adapter(kind)
    except KeyError as exc:
        return _diagnostic(str(exc), json_output=json_output)

    handler = registration.load()
    try:
        result = handler.launch(
            config,
            operation_id,
            repo_name=repo_name,
            spec_path=Path(spec_path),
        )
    except Exception as exc:
        payload = _run_error_payload(
            config,
            operation_id,
            kind=kind,
            operation_type=registration.operation_type,
            exc=exc,
        )
        _emit(payload, json_output=json_output)
        return 1

    payload = _run_result_payload(
        config,
        operation_id,
        kind=kind,
        operation_type=registration.operation_type,
        result=result,
        handler=handler,
    )
    _emit(payload, json_output=json_output)
    return 0


def _status(config: Any, operation_id: str | None, *, json_output: bool) -> int:
    if operation_id:
        run = load_agentbox_operation(config, operation_id)
        run = _tick_operation_for_status(config, run)
        payload: Any = _operation_status(config, run)
    else:
        payload = [
            _operation_status(config, _tick_operation_for_status(config, run))
            for run in list_agentbox_operations(config)
        ]
    _emit(payload, json_output=json_output)
    return 0


def _logs(
    config: Any,
    operation_id: str,
    *,
    lines: int,
    stream: str,
    json_output: bool,
) -> int:
    run = load_agentbox_operation(config, operation_id)
    resources = open_operation_store(config).list_typed_resources(operation_id)
    selected = ("stdout", "stderr") if stream == "all" else (stream,)
    entries = [_log_entry(config, operation_id, resources, name, lines=lines) for name in selected]

    if not any(entry["text"] for entry in entries):
        fallback = _tmux_capture_fallback(run, resources, lines=lines)
        if fallback is not None:
            entries = [fallback]

    payload = {"operation_id": operation_id, "lines": lines, "logs": entries}
    if json_output:
        _emit(payload, json_output=True)
    else:
        _print_log_entries(entries)
    return 0


def _attach(config: Any, operation_id: str) -> int:
    load_agentbox_operation(config, operation_id)
    session_resource = _single_process_session_resource(config, operation_id)
    if session_resource is None:
        return _diagnostic(
            f"operation {operation_id!r} has no recorded process-session resource; run `agentbox reconcile`",
            json_output=False,
        )

    session_name = _resource_session_name(session_resource)
    if not session_name:
        return _diagnostic(
            f"operation {operation_id!r} has a process-session resource without a session name",
            json_output=False,
        )

    status = inspect_session(session_name)
    if not status.exists:
        detail = f": {status.detail}" if status.detail else ""
        return _diagnostic(
            f"session {session_name!r} is {status.state}{detail}; run `agentbox reconcile`",
            json_output=False,
        )

    return subprocess.run(attach_argv(session_name), check=False).returncode


def _reconcile(config: Any, *, json_output: bool) -> int:
    report = reconcile(config).to_dict()
    _emit(report, json_output=json_output)
    return 0


def _operation_status(config: Any, run: Any) -> dict[str, Any]:
    resources = open_operation_store(config).list_typed_resources(run.id)
    session_resource = _process_session_resource(resources)
    session_status = None
    session_name = _resource_session_name(session_resource) if session_resource else run.metadata.get("session_name")
    if session_name:
        try:
            session_status = inspect_session(str(session_name))
        except FileNotFoundError as exc:
            session_status = {"session_name": str(session_name), "state": "tmux_unavailable", "exists": False, "detail": str(exc)}
        except Exception as exc:
            session_status = {"session_name": str(session_name), "state": "inspect_failed", "exists": False, "detail": str(exc)}
    paths = run_dir_paths(config, run.id)
    return {
        "operation_id": run.id,
        "operation_type": run.operation_type,
        "operation_state": run.state.value,
        "launch_state": run.metadata.get("launch_state"),
        "command": run.metadata.get("command"),
        "repo_names": run.metadata.get("repo_names", []),
        "run_dir": str(paths.root),
        "run_dir_exists": paths.root.exists(),
        "resource_count": len(resources),
        "session": _jsonable(session_status),
    }


def _tick_operation_for_status(config: Any, run: Any) -> Any:
    registration = _operation_adapter_for_type(run.operation_type)
    if registration is None:
        return run

    handler = registration.load()
    tick = getattr(handler, "tick", None)
    if not callable(tick):
        return run

    updated = tick(config, run.id)
    return updated if getattr(updated, "id", None) == run.id else load_agentbox_operation(
        config,
        run.id,
        operation_types=(registration.operation_type,),
    )


def _operation_adapter_for_type(operation_type: str) -> Any | None:
    for registration in list_operation_adapters():
        if registration.operation_type == operation_type:
            return registration
    return None


def _run_result_payload(
    config: Any,
    operation_id: str,
    *,
    kind: str,
    operation_type: str,
    result: Any,
    handler: Any,
) -> dict[str, Any]:
    run = load_agentbox_operation(config, operation_id, operation_types=(operation_type,))
    resources = open_operation_store(config).list_typed_resources(operation_id)
    paths = run_dir_paths(config, operation_id)
    diagnostics = _result_diagnostics(result)
    classification = _handler_classification(config, operation_id, handler, diagnostics)
    return {
        "operation_id": operation_id,
        "kind": kind,
        "operation_type": run.operation_type,
        "operation_state": run.state.value,
        "launch_state": run.metadata.get("launch_state"),
        "run_dir": str(paths.root),
        "resources": _resource_payloads(resources),
        "resolved_spec_path": _resolved_spec_path(result, run.metadata),
        "validation": run.metadata.get("validation"),
        "classification": classification,
        "diagnostics": diagnostics,
    }


def _run_error_payload(
    config: Any,
    operation_id: str,
    *,
    kind: str,
    operation_type: str,
    exc: Exception,
) -> dict[str, Any]:
    run = None
    resources: tuple[TypedResource, ...] = ()
    try:
        run = load_agentbox_operation(config, operation_id, operation_types=(operation_type,))
        resources = open_operation_store(config).list_typed_resources(operation_id)
    except Exception:
        pass

    paths = run_dir_paths(config, operation_id)
    diagnostics = _exception_diagnostics(exc)
    return {
        "operation_id": operation_id,
        "kind": kind,
        "operation_type": operation_type,
        "operation_state": run.state.value if run is not None else None,
        "launch_state": run.metadata.get("launch_state") if run is not None else None,
        "run_dir": str(paths.root),
        "resources": _resource_payloads(resources),
        "resolved_spec_path": (
            str(run.metadata.get("resolved_spec_path"))
            if run is not None and run.metadata.get("resolved_spec_path")
            else None
        ),
        "validation": run.metadata.get("validation") if run is not None else None,
        "classification": run.metadata.get("chain_status") if run is not None else None,
        "diagnostics": diagnostics,
        "error": str(exc),
    }


def _handler_classification(
    config: Any,
    operation_id: str,
    handler: Any,
    diagnostics: dict[str, Any] | None,
) -> dict[str, Any] | None:
    status = getattr(handler, "status", None)
    if not callable(status):
        return None
    try:
        snapshot = status(config, operation_id)
    except Exception as exc:
        if diagnostics is not None:
            diagnostics["classification"] = {
                "kind": type(exc).__name__,
                "message": str(exc),
            }
        return None
    classification = getattr(snapshot, "classification", None)
    to_dict = getattr(classification, "to_dict", None)
    if callable(to_dict):
        return to_dict()
    return _jsonable(classification) if classification is not None else None


def _result_diagnostics(result: Any) -> dict[str, Any] | None:
    host_result = getattr(result, "host_result", None)
    diagnostics = getattr(host_result, "diagnostics", None)
    return dict(diagnostics) if isinstance(diagnostics, dict) else _jsonable(diagnostics)


def _exception_diagnostics(exc: Exception) -> dict[str, Any]:
    diagnostics = getattr(exc, "diagnostics", None)
    if isinstance(diagnostics, dict):
        return dict(diagnostics)
    return {"kind": getattr(exc, "kind", type(exc).__name__), "message": str(exc)}


def _resolved_spec_path(result: Any, metadata: dict[str, Any]) -> str | None:
    value = getattr(result, "resolved_spec_path", None) or metadata.get("resolved_spec_path")
    return str(value) if value else None


def _resource_payloads(resources: Sequence[TypedResource]) -> list[dict[str, Any]]:
    return [
        {
            "id": resource.id,
            "type": resource.resource_type.value,
            "name": resource.name,
            "details": dict(resource.details),
        }
        for resource in resources
    ]


def _log_entry(
    config: Any,
    operation_id: str,
    resources: tuple[TypedResource, ...],
    stream: str,
    *,
    lines: int,
) -> dict[str, Any]:
    path = _log_path(config, operation_id, resources, stream)
    text = _tail_text(path, lines) if path is not None and path.exists() else ""
    return {
        "stream": stream,
        "path": str(path) if path is not None else None,
        "exists": bool(path is not None and path.exists()),
        "text": text,
    }


def _tmux_capture_fallback(
    run: Any,
    resources: tuple[TypedResource, ...],
    *,
    lines: int,
) -> dict[str, Any] | None:
    session_resource = _process_session_resource(resources)
    session_name = _resource_session_name(session_resource) if session_resource else None
    if not session_name:
        return None
    status = inspect_session(session_name)
    if not status.exists:
        return None
    return {
        "stream": "tmux",
        "path": None,
        "exists": True,
        "text": capture_pane(session_name, lines=lines),
        "session_name": session_name,
        "operation_id": run.id,
    }


def _log_path(
    config: Any,
    operation_id: str,
    resources: tuple[TypedResource, ...],
    stream: str,
) -> Path:
    for resource in resources:
        if resource.resource_type is ResourceType.LOG and resource.details.get("stream") == stream:
            path = resource.details.get("path")
            if path:
                return Path(str(path))
    paths = run_dir_paths(config, operation_id)
    return paths.stdout_path if stream == "stdout" else paths.stderr_path


def _single_process_session_resource(config: Any, operation_id: str) -> TypedResource | None:
    return _process_session_resource(open_operation_store(config).list_typed_resources(operation_id))


def _process_session_resource(resources: tuple[TypedResource, ...]) -> TypedResource | None:
    for resource in resources:
        if resource.resource_type is ResourceType.PROCESS_SESSION:
            return resource
    return None


def _resource_session_name(resource: TypedResource | None) -> str | None:
    if resource is None:
        return None
    value = resource.details.get("session_name") or resource.name
    return str(value) if value else None


def _tail_text(path: Path, lines: int) -> str:
    if lines <= 0:
        return ""
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        return "".join(handle.readlines()[-lines:])


def _print_log_entries(entries: list[dict[str, Any]]) -> None:
    for index, entry in enumerate(entries):
        if len(entries) > 1:
            if index:
                print()
            print(f"==> {entry['stream']} <==")
        print(entry["text"], end="" if str(entry["text"]).endswith("\n") else "\n")


def _emit(payload: Any, *, json_output: bool) -> None:
    if json_output:
        print(json.dumps(_jsonable(payload), indent=2, sort_keys=True))
    else:
        print(json.dumps(_jsonable(payload), indent=2, sort_keys=True))


def _diagnostic(message: str, *, json_output: bool) -> int:
    if json_output:
        _emit({"error": message}, json_output=True)
    else:
        print(f"agentbox: {message}", file=sys.stderr)
    return 1


def _jsonable(value: Any) -> Any:
    if is_dataclass(value) and not isinstance(value, type):
        return _jsonable(asdict(value))
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    return value


def _positive_int(value: str) -> int:
    parsed = int(value)
    if parsed < 0:
        raise argparse.ArgumentTypeError("value must be >= 0")
    return parsed


def _new_operation_id(kind: str) -> str:
    return f"{kind}-{uuid4().hex[:12]}"


__all__ = ["build_parser", "main"]
