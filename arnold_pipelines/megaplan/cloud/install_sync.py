from __future__ import annotations

import shlex
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable

from arnold_pipelines.megaplan.cloud.incident_bridge import (
    append_install_sync_applied,
    append_install_sync_failed,
)
from arnold_pipelines.megaplan.cloud.redact import redact_text


Runner = Callable[..., subprocess.CompletedProcess[str]]

_IDENTITY_PROBE = (
    "import json, pathlib, sys; "
    "import arnold_pipelines; "
    "package_file = pathlib.Path(arnold_pipelines.__file__).resolve(); "
    "print(json.dumps({"
    "'python_executable': sys.executable, "
    "'package_file': str(package_file), "
    "'package_root': str(package_file.parent.parent)"
    "}, sort_keys=True))"
)


def _run(
    command: list[str],
    *,
    cwd: Path,
    runner: Runner,
) -> subprocess.CompletedProcess[str]:
    return runner(
        command,
        cwd=str(cwd),
        capture_output=True,
        text=True,
        check=False,
    )


def _tail(text: str, *, max_lines: int = 20) -> str:
    lines = text.splitlines()
    if len(lines) <= max_lines:
        return text.strip()
    return "\n".join(lines[-max_lines:]).strip()


def _redacted_tail(text: str) -> str:
    return redact_text(_tail(text or ""))


def _command_text(command: list[str]) -> str:
    return " ".join(shlex.quote(part) for part in command)


def capture_runtime_identity(
    source_root: Path | str,
    *,
    python_executable: str | None = None,
    runner: Runner = subprocess.run,
) -> dict[str, Any]:
    root = Path(source_root).expanduser().resolve()
    python_bin = python_executable or sys.executable

    git_head_proc = _run(["git", "rev-parse", "HEAD"], cwd=root, runner=runner)
    git_branch_proc = _run(["git", "branch", "--show-current"], cwd=root, runner=runner)
    probe_proc = _run([python_bin, "-c", _IDENTITY_PROBE], cwd=root, runner=runner)

    package_identity: dict[str, Any] = {}
    if probe_proc.returncode == 0:
        try:
            import json

            loaded = json.loads(probe_proc.stdout or "{}")
        except Exception:
            loaded = {}
        if isinstance(loaded, dict):
            package_identity = loaded

    return {
        "source_root": str(root),
        "python_executable": package_identity.get("python_executable") or python_bin,
        "git_head": (git_head_proc.stdout or "").strip() or None,
        "git_branch": (git_branch_proc.stdout or "").strip() or None,
        "package_file": package_identity.get("package_file"),
        "package_root": package_identity.get("package_root"),
    }


def apply_install_sync(
    *,
    source_root: Path | str,
    incident_id: str,
    session_id: str | None = None,
    problem_id: str | None = None,
    root: Path | str | None = None,
    python_executable: str | None = None,
    runner: Runner = subprocess.run,
) -> dict[str, Any]:
    source = Path(source_root).expanduser().resolve()
    python_bin = python_executable or sys.executable
    command = [python_bin, "-m", "pip", "install", "-e", str(source)]
    before_identity = capture_runtime_identity(
        source,
        python_executable=python_bin,
        runner=runner,
    )
    install_proc = _run(command, cwd=source, runner=runner)
    after_identity = capture_runtime_identity(
        source,
        python_executable=python_bin,
        runner=runner,
    )

    command_text = _command_text(command)
    verification = {
        "kind": "install_sync_verification",
        "expected_git_head": before_identity.get("git_head"),
        "observed_git_head": after_identity.get("git_head"),
        "runtime_changed": before_identity != after_identity,
        "returncode": install_proc.returncode,
        "success": install_proc.returncode == 0,
    }
    evidence = [
        {
            "kind": "runtime_identity",
            "before": before_identity,
            "after": after_identity,
            "command": command_text,
            "returncode": install_proc.returncode,
        },
        {
            "kind": "command_result",
            "command": command_text,
            "returncode": install_proc.returncode,
            "stdout_tail": _redacted_tail(install_proc.stdout or ""),
            "stderr_tail": _redacted_tail(install_proc.stderr or ""),
        },
        verification,
    ]
    summary = (
        f"Editable install synced with {command_text}"
        if install_proc.returncode == 0
        else f"Editable install sync failed with {command_text}"
    )
    if install_proc.returncode == 0:
        event = append_install_sync_applied(
            incident_id=incident_id,
            summary=summary,
            evidence=evidence,
            session_id=session_id,
            problem_id=problem_id,
            root=root or source,
        )
        status = "applied"
    else:
        event = append_install_sync_failed(
            incident_id=incident_id,
            summary=summary,
            evidence=evidence,
            session_id=session_id,
            problem_id=problem_id,
            root=root or source,
        )
        status = "failed"

    return {
        "status": status,
        "command": command,
        "command_text": command_text,
        "returncode": install_proc.returncode,
        "before_identity": before_identity,
        "after_identity": after_identity,
        "stdout_tail": evidence[1]["stdout_tail"],
        "stderr_tail": evidence[1]["stderr_tail"],
        "verification": verification,
        "event": event,
    }


__all__ = [
    "apply_install_sync",
    "capture_runtime_identity",
]
