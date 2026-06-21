from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol, Sequence

from vibecomfy.commands._diagnostics import Diagnostic


class GitRunner(Protocol):
    def __call__(
        self,
        args: Sequence[str],
        *,
        check: bool,
        capture_output: bool,
        text: bool,
    ) -> subprocess.CompletedProcess[str]:
        ...


@dataclass(frozen=True)
class GitStdoutResult:
    stdout: str | None
    diagnostic: Diagnostic | None = None

    @property
    def ok(self) -> bool:
        return self.diagnostic is None


def git_stdout_result(
    pack_dir: Path,
    args: Sequence[str],
    *,
    runner: GitRunner | None = None,
) -> GitStdoutResult:
    """Run ``git -C pack_dir ...`` and return stdout plus failure diagnostics."""

    command = ["git", "-C", str(pack_dir), *args]
    run = subprocess.run if runner is None else runner
    try:
        completed = run(command, check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as exc:
        return GitStdoutResult(
            stdout=None,
            diagnostic=Diagnostic(
                code="git_command_failed",
                message=f"git command failed with exit code {exc.returncode}",
                severity="error",
                recoverable=True,
                details={
                    "command": _stringify_command(_exception_command(exc.cmd, command)),
                    "returncode": exc.returncode,
                    "stderr": _stringify_output(exc.stderr),
                },
            ),
        )
    except OSError as exc:
        return GitStdoutResult(
            stdout=None,
            diagnostic=Diagnostic(
                code="git_command_os_error",
                message=str(exc),
                severity="error",
                recoverable=True,
                details={
                    "command": _stringify_command(command),
                    "error": type(exc).__name__,
                    "errno": exc.errno,
                },
            ),
        )

    returncode = getattr(completed, "returncode", 0)
    if returncode != 0:
        return GitStdoutResult(
            stdout=None,
            diagnostic=Diagnostic(
                code="git_command_failed",
                message=f"git command failed with exit code {returncode}",
                severity="error",
                recoverable=True,
                details={
                    "command": _stringify_command(command),
                    "returncode": returncode,
                    "stderr": _stringify_output(getattr(completed, "stderr", None)),
                },
            ),
        )
    return GitStdoutResult(stdout=getattr(completed, "stdout", ""))


def git_stdout(pack_dir: Path, args: Sequence[str], *, runner: GitRunner | None = None) -> str | None:
    """Run ``git -C pack_dir ...`` and return stdout, or ``None`` on failure."""

    return git_stdout_result(pack_dir, args, runner=runner).stdout


def git_head(pack_dir: Path, *, runner: GitRunner | None = None) -> str | None:
    stdout = git_stdout(pack_dir, ["rev-parse", "HEAD"], runner=runner)
    return (stdout or "").strip() or None


def _exception_command(value: Any, fallback: Sequence[str]) -> Sequence[Any]:
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return value
    if value:
        return [value]
    return fallback


def _stringify_command(command: Sequence[Any]) -> list[str]:
    return [str(item) for item in command]


def _stringify_output(output: object) -> str:
    if output is None:
        return ""
    if isinstance(output, bytes):
        return output.decode(errors="replace")
    return str(output)


__all__ = ["GitRunner", "GitStdoutResult", "git_head", "git_stdout", "git_stdout_result"]
