"""Docker helpers shared by benchmark backends."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Callable


CommandRunner = Callable[[list[str], Path, int | None], subprocess.CompletedProcess[str]]


def pull_image(
    image: str,
    runner: CommandRunner | None = None,
    timeout: int | None = None,
) -> subprocess.CompletedProcess[str]:
    return (runner or _run_command)(["docker", "pull", image], Path.cwd(), timeout)


def build_image(
    tag: str,
    context_dir: str | Path,
    dockerfile: str | Path | None = None,
    runner: CommandRunner | None = None,
    timeout: int | None = None,
) -> subprocess.CompletedProcess[str]:
    """Build a Docker image from a Dockerfile."""
    context = Path(context_dir).expanduser().resolve()
    command = ["docker", "build", "-t", tag]
    if dockerfile:
        command.extend(["-f", str(dockerfile)])
    command.append(str(context))
    return (runner or _run_command)(command, context, timeout)


def run_with_mount(
    image: str,
    workspace_path: str | Path,
    cmd: list[str],
    timeout: int | None = None,
    runner: CommandRunner | None = None,
) -> subprocess.CompletedProcess[str]:
    workspace = Path(workspace_path).expanduser().resolve()
    command = [
        "docker",
        "run",
        "--rm",
        "-v",
        f"{workspace}:/workspace",
        "-w",
        "/workspace",
        image,
        *cmd,
    ]
    return (runner or _run_command)(command, workspace, timeout)


def docker_version(
    runner: CommandRunner | None = None,
    timeout: int | None = None,
) -> str:
    completed = (runner or _run_command)(
        ["docker", "version", "--format", "{{.Server.Version}}"],
        Path.cwd(),
        timeout,
    )
    return completed.stdout.strip()


def _run_command(
    command: list[str],
    cwd: Path,
    timeout: int | None,
) -> subprocess.CompletedProcess[str]:
    try:
        completed = subprocess.run(
            command,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except FileNotFoundError as exc:
        raise RuntimeError(f"Command not found: {' '.join(command)}") from exc
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(
            f"Command timed out after {timeout}s: {' '.join(command)}\n"
            f"{(exc.stdout or '')}{(exc.stderr or '')}"
        ) from exc

    if completed.returncode != 0:
        raise RuntimeError(
            f"Command failed ({completed.returncode}): {' '.join(command)}\n"
            f"{completed.stdout}{completed.stderr}"
        )
    return completed
