"""Scoring helpers for next-evals workspaces."""

from __future__ import annotations

import json
import subprocess
import time
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from utils import atomic_json_write


TOOL_BUCKETS = (
    "agent_task",
    "file_edit",
    "file_read",
    "file_write",
    "glob",
    "grep",
    "list_dir",
    "shell",
    "unknown",
    "web_fetch",
    "web_search",
)


@dataclass(slots=True)
class BuildResult:
    success: bool
    returncode: int
    stdout: str
    stderr: str
    command: list[str]
    duration_seconds: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class EvalRunResult:
    success: bool
    returncode: int
    stdout: str
    stderr: str
    command: list[str]
    duration_seconds: float
    reporter_json: dict[str, Any] | None
    results_path: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def check_build(workspace: str | Path, *, timeout_seconds: int = 600) -> BuildResult:
    command = ["npm", "run", "build"]
    started = time.monotonic()
    try:
        completed = subprocess.run(
            command,
            cwd=Path(workspace),
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
    except FileNotFoundError as exc:
        return BuildResult(
            success=False,
            returncode=-1,
            stdout="",
            stderr=str(exc),
            command=command,
            duration_seconds=time.monotonic() - started,
        )
    except subprocess.TimeoutExpired as exc:
        return BuildResult(
            success=False,
            returncode=-1,
            stdout=exc.stdout or "",
            stderr=(exc.stderr or "") + f"\nTimed out after {timeout_seconds}s",
            command=command,
            duration_seconds=time.monotonic() - started,
        )
    return BuildResult(
        success=completed.returncode == 0,
        returncode=completed.returncode,
        stdout=completed.stdout,
        stderr=completed.stderr,
        command=command,
        duration_seconds=time.monotonic() - started,
    )


def generate_results_json(
    trace: dict[str, Any] | list[dict[str, Any]] | str | None,
    workspace: str | Path,
    *,
    initial_commit_sha: str,
    status: str = "passed",
    duration_seconds: float = 0.0,
    model: str = "",
    error: str | None = None,
    transcript_path: str | None = None,
    transcript_raw_path: str | None = None,
    build_output_path: str | None = None,
    eval_output_path: str | None = None,
) -> dict[str, Any]:
    workspace_path = Path(workspace)
    messages = _extract_messages(trace)
    tool_results = _index_tool_results(messages)
    tool_call_counts = Counter({bucket: 0 for bucket in TOOL_BUCKETS})
    files_read: set[str] = set()
    shell_commands: list[dict[str, Any]] = []
    errors: list[str] = []
    web_fetches: list[Any] = []
    thinking_blocks = 0

    for message in messages:
        if message.get("role") == "assistant" and _message_has_reasoning(message):
            thinking_blocks += 1
        for tool_call in message.get("tool_calls") or []:
            tool_name = _extract_tool_name(tool_call)
            bucket = _tool_bucket(tool_name)
            tool_call_counts[bucket] += 1

            arguments = _parse_tool_arguments(tool_call)
            files_read.update(_extract_paths_for_bucket(bucket, arguments))

            if bucket == "shell":
                result_payload = tool_results.get(_extract_tool_call_id(tool_call), {})
                shell_entry = {"command": _shell_command_from_args(arguments)}
                exit_code = _extract_exit_code(result_payload)
                if exit_code is not None:
                    shell_entry["exitCode"] = exit_code
                    shell_entry["success"] = exit_code == 0
                elif isinstance(result_payload, dict) and "success" in result_payload:
                    shell_entry["success"] = bool(result_payload.get("success"))
                shell_commands.append(shell_entry)

            if bucket in {"web_fetch", "web_search"}:
                fetch_value = _extract_web_fetch(arguments)
                if fetch_value is not None:
                    web_fetches.append(fetch_value)

        if message.get("role") == "tool":
            result_payload = _parse_json_maybe(message.get("content"))
            error_text = _extract_error(result_payload)
            if error_text:
                errors.append(error_text)

    files_modified = _git_diff_name_only(workspace_path, initial_commit_sha)
    total_tool_calls = sum(tool_call_counts.values())

    result: dict[str, Any] = {
        "status": status,
        "duration": float(duration_seconds or 0.0),
        "model": model,
        "o11y": {
            "errors": errors,
            "filesModified": files_modified,
            "filesRead": sorted(files_read),
            "shellCommands": shell_commands,
            "thinkingBlocks": thinking_blocks,
            "toolCalls": dict(tool_call_counts),
            "totalToolCalls": total_tool_calls,
            "totalTurns": len(messages),
            "webFetches": web_fetches,
        },
    }
    if error:
        result["error"] = error
    if transcript_path:
        result["transcriptPath"] = transcript_path
    if transcript_raw_path:
        result["transcriptRawPath"] = transcript_raw_path
    if build_output_path and eval_output_path:
        result["outputPaths"] = {
            "eval": eval_output_path,
            "scripts": {"build": build_output_path},
        }
    return result


def run_eval_ts(
    workspace: str | Path,
    results_json: dict[str, Any],
    *,
    timeout_seconds: int = 600,
) -> EvalRunResult:
    workspace_path = Path(workspace)
    results_path = workspace_path / "__agent_eval__" / "results.json"
    atomic_json_write(results_path, results_json, default=str)

    # Restore EVAL.ts if the executor renamed it (e.g., to EVAL.test.ts)
    eval_ts = workspace_path / "EVAL.ts"
    if not eval_ts.exists():
        for renamed in [workspace_path / "EVAL.test.ts", workspace_path / "EVAL.spec.ts"]:
            if renamed.exists():
                renamed.rename(eval_ts)
                break

    # vitest's default include pattern only matches *.test.ts / *.spec.ts.
    # Write a minimal config that includes EVAL.ts.
    _ensure_vitest_config(workspace_path)
    command = ["npx", "vitest", "run", "--reporter=json"]
    started = time.monotonic()
    try:
        completed = subprocess.run(
            command,
            cwd=workspace_path,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
    except FileNotFoundError as exc:
        return EvalRunResult(
            success=False,
            returncode=-1,
            stdout="",
            stderr=str(exc),
            command=command,
            duration_seconds=time.monotonic() - started,
            reporter_json=None,
            results_path=str(results_path),
        )
    except subprocess.TimeoutExpired as exc:
        return EvalRunResult(
            success=False,
            returncode=-1,
            stdout=exc.stdout or "",
            stderr=(exc.stderr or "") + f"\nTimed out after {timeout_seconds}s",
            command=command,
            duration_seconds=time.monotonic() - started,
            reporter_json=None,
            results_path=str(results_path),
        )
    reporter_json = _extract_reporter_json(completed.stdout)
    success = completed.returncode == 0
    if reporter_json and "success" in reporter_json:
        success = bool(reporter_json.get("success")) and success

    return EvalRunResult(
        success=success,
        returncode=completed.returncode,
        stdout=completed.stdout,
        stderr=completed.stderr,
        command=command,
        duration_seconds=time.monotonic() - started,
        reporter_json=reporter_json,
        results_path=str(results_path),
    )


def _ensure_vitest_config(workspace: Path) -> None:
    """Write a vitest config that includes EVAL.ts, overwriting any existing one."""
    config_path = workspace / "vitest.config.ts"
    config_path.write_text(
        'import { defineConfig } from "vitest/config"\n'
        "export default defineConfig({\n"
        "  test: {\n"
        '    include: ["EVAL.ts"],\n'
        "  },\n"
        "})\n",
        encoding="utf-8",
    )


def _extract_messages(trace: dict[str, Any] | list[dict[str, Any]] | str | None) -> list[dict[str, Any]]:
    if trace is None:
        return []
    if isinstance(trace, list):
        return [msg for msg in trace if isinstance(msg, dict)]
    if isinstance(trace, dict):
        messages = trace.get("messages")
        if isinstance(messages, list):
            return [msg for msg in messages if isinstance(msg, dict)]
        return []
    if isinstance(trace, str):
        parsed = _parse_json_maybe(trace)
        if isinstance(parsed, dict):
            return _extract_messages(parsed)
        if isinstance(parsed, list):
            return _extract_messages(parsed)
    return []


def _index_tool_results(messages: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    indexed: dict[str, dict[str, Any]] = {}
    for message in messages:
        if message.get("role") != "tool":
            continue
        tool_call_id = message.get("tool_call_id")
        if not isinstance(tool_call_id, str) or not tool_call_id:
            continue
        payload = _parse_json_maybe(message.get("content"))
        indexed[tool_call_id] = payload if isinstance(payload, dict) else {}
    return indexed


def _message_has_reasoning(message: dict[str, Any]) -> bool:
    if message.get("reasoning"):
        return True
    details = message.get("reasoning_details")
    if isinstance(details, list) and details:
        return True
    codex_items = message.get("codex_reasoning_items")
    return isinstance(codex_items, list) and bool(codex_items)


def _extract_tool_name(tool_call: dict[str, Any]) -> str:
    function = tool_call.get("function")
    if isinstance(function, dict):
        name = function.get("name")
        if isinstance(name, str):
            return name
    name = tool_call.get("name")
    return name if isinstance(name, str) else ""


def _extract_tool_call_id(tool_call: dict[str, Any]) -> str | None:
    for key in ("call_id", "id"):
        value = tool_call.get(key)
        if isinstance(value, str) and value:
            return value
    return None


def _parse_tool_arguments(tool_call: dict[str, Any]) -> dict[str, Any]:
    function = tool_call.get("function")
    if not isinstance(function, dict):
        return {}
    arguments = function.get("arguments")
    parsed = _parse_json_maybe(arguments)
    return parsed if isinstance(parsed, dict) else {}


def _parse_json_maybe(value: Any) -> Any:
    if isinstance(value, (dict, list)):
        return value
    if not isinstance(value, str):
        return value
    text = value.strip()
    if not text:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def _tool_bucket(tool_name: str) -> str:
    lowered = tool_name.lower()
    if lowered in {"delegate_task", "agent_task"}:
        return "agent_task"
    if lowered in {"read_file", "read_files", "view_file"}:
        return "file_read"
    if lowered in {"write_file", "create_file", "append_file"}:
        return "file_write"
    if lowered in {"edit_file", "apply_patch", "replace_in_file"}:
        return "file_edit"
    if lowered in {"glob_search", "glob_files", "glob"}:
        return "glob"
    if lowered in {"search_files", "grep_search", "grep"}:
        return "grep"
    if lowered in {"list_dir", "list_files", "directory_tree"}:
        return "list_dir"
    if lowered in {"terminal", "shell"}:
        return "shell"
    if lowered in {"web_extract", "web_fetch", "browser_navigate"}:
        return "web_fetch"
    if lowered in {"web_search"}:
        return "web_search"
    if "read" in lowered and "file" in lowered:
        return "file_read"
    if any(token in lowered for token in ("write", "create", "append")) and "file" in lowered:
        return "file_write"
    if any(token in lowered for token in ("edit", "patch", "replace")):
        return "file_edit"
    if "grep" in lowered or "search" in lowered:
        return "grep"
    if "glob" in lowered:
        return "glob"
    if "list" in lowered or "dir" in lowered:
        return "list_dir"
    return "unknown"


def _extract_paths_for_bucket(bucket: str, arguments: dict[str, Any]) -> set[str]:
    if bucket != "file_read":
        return set()
    return set(_gather_path_values(arguments))


def _gather_path_values(value: Any) -> list[str]:
    found: list[str] = []
    if isinstance(value, dict):
        for key, nested in value.items():
            lowered = key.lower()
            if lowered in {"path", "paths", "file", "files", "filepath", "file_path"}:
                if isinstance(nested, str):
                    found.append(nested)
                elif isinstance(nested, list):
                    found.extend(item for item in nested if isinstance(item, str))
            else:
                found.extend(_gather_path_values(nested))
    elif isinstance(value, list):
        for item in value:
            found.extend(_gather_path_values(item))
    return found


def _shell_command_from_args(arguments: dict[str, Any]) -> str:
    command = arguments.get("command")
    if isinstance(command, str):
        return command
    cmd = arguments.get("cmd")
    return cmd if isinstance(cmd, str) else ""


def _extract_exit_code(result_payload: dict[str, Any]) -> int | None:
    if not isinstance(result_payload, dict):
        return None
    for key in ("exit_code", "exitCode", "returncode", "return_code"):
        value = result_payload.get(key)
        if isinstance(value, int):
            return value
    return None


def _extract_web_fetch(arguments: dict[str, Any]) -> Any:
    for key in ("url", "urls", "query"):
        value = arguments.get(key)
        if value:
            return value
    return None


def _extract_error(result_payload: Any) -> str | None:
    if not isinstance(result_payload, dict):
        return None
    for key in ("error", "stderr", "message"):
        value = result_payload.get(key)
        if isinstance(value, str) and value.strip():
            if key != "message" or result_payload.get("success") is False:
                return value.strip()
    return None


def _git_diff_name_only(workspace: Path, initial_commit_sha: str) -> list[str]:
    completed = subprocess.run(
        ["git", "diff", "--name-only", initial_commit_sha],
        cwd=workspace,
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        return []
    return [line for line in completed.stdout.splitlines() if line.strip()]


def _extract_reporter_json(stdout: str) -> dict[str, Any] | None:
    text = stdout.strip()
    if not text:
        return None
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        parsed = None
    if isinstance(parsed, dict):
        return parsed

    decoder = json.JSONDecoder()
    for index, char in enumerate(text):
        if char != "{":
            continue
        try:
            parsed, end = decoder.raw_decode(text[index:])
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict) and index + end <= len(text):
            return parsed
    return None
