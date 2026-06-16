"""Repair-runner adapter with broken-CLI resilience."""

from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence


@dataclass(frozen=True)
class RepairResult:
    status: str
    stdout: str
    stderr: str
    rc: int | None


_MEGAPLAN_SUBCOMMANDS: frozenset[str] = frozenset({
    "doctor",
    "auto",
    "resume",
    "chain",
})


class RepairRunner:
    """Run allowlisted repair commands via subprocess.

    Megaplan subcommands (``doctor``, ``auto``, ``resume``, ``chain``) are
    executed as ``python -m arnold.pipelines.megaplan <subcommand> ...`` inside
    the plan's project directory. System commands (``rm``, ``kill``) are run
    directly. If the executable is missing or the command cannot be run, returns
    a ``command_unavailable`` result instead of crashing.
    """

    def __init__(
        self,
        executable_search_path: Sequence[str] | None = None,
        python_bin: str | None = None,
    ) -> None:
        self._search_path = executable_search_path
        self._python_bin = python_bin or shutil.which("python3") or shutil.which("python") or "python"

    def _is_dry_run(self) -> bool:
        """An empty search path signals dry-run: do not execute anything."""
        return self._search_path is not None and len(self._search_path) == 0

    def _argv_for_command(self, command: str) -> tuple[list[str], str | None]:
        """Return (argv, cwd) for *command*.

        Megaplan subcommands are rewritten to ``python -m arnold.pipelines.megaplan``,
        or to a ``megaplan`` executable found on the search path if one exists.
        System commands are passed through. The returned cwd is the directory in
        which the command should run, or None for the current directory.
        """
        if self._is_dry_run():
            return [], None

        parts = command.split()
        if not parts:
            return [], None

        first = parts[0]
        # Detect an explicit project-dir marker injected by the CLI: "cd /path && cmd"
        if first == "cd" and len(parts) >= 4 and parts[2] == "&&":
            cwd = parts[1].strip("'\"")
            parts = parts[3:]
            first = parts[0] if parts else ""
        else:
            cwd = None

        if first in _MEGAPLAN_SUBCOMMANDS:
            # Prefer a real ``megaplan`` executable on PATH if available;
            # otherwise fall back to the module invocation.
            megaplan_exe = shutil.which("megaplan", path=self._search_path)
            if megaplan_exe is not None:
                return [megaplan_exe] + parts, cwd
            return [self._python_bin, "-m", "arnold.pipelines.megaplan"] + parts, cwd

        # Bare subcommands like "rm" or "kill" that are not standalone executables
        # but are safe shell builtins/utilities.
        if first in {"rm", "kill"}:
            return ["/bin/bash", "-c", " ".join(parts)], cwd

        executable = shutil.which(first, path=self._search_path)
        if executable is None:
            return [], cwd
        return [executable] + parts[1:], cwd

    def run(
        self,
        command: str,
        *,
        plan_dir: str | None = None,
        project_dir: str | None = None,
    ) -> RepairResult:
        """Execute *command* and return a structured result."""
        argv, argv_cwd = self._argv_for_command(command)
        if not argv:
            return RepairResult(
                status="command_unavailable",
                stdout="",
                stderr=f"executable not found or unsupported command: {command!r}",
                rc=None,
            )

        cwd = argv_cwd or project_dir
        if cwd is None and plan_dir is not None:
            # Fall back to the plan directory's repo root.
            try:
                cwd = str(Path(plan_dir).parents[2])
            except Exception:
                pass

        env = os.environ.copy()
        if cwd is not None:
            env["MEGAPLAN_PLAN_DIR"] = str(plan_dir) if plan_dir else cwd
            env["MEGAPLAN_PROJECT_DIR"] = cwd

        try:
            result = subprocess.run(
                argv,
                capture_output=True,
                text=True,
                timeout=300,
                check=False,
                cwd=cwd,
                env=env,
            )
            status = "success" if result.returncode == 0 else "failed"
            return RepairResult(
                status=status,
                stdout=result.stdout,
                stderr=result.stderr,
                rc=result.returncode,
            )
        except (FileNotFoundError, OSError) as exc:
            return RepairResult(
                status="command_unavailable",
                stdout="",
                stderr=f"could not execute {argv!r}: {exc}",
                rc=None,
            )
        except subprocess.TimeoutExpired:
            return RepairResult(
                status="timeout",
                stdout="",
                stderr="command timed out after 300s",
                rc=None,
            )


__all__ = [
    "RepairResult",
    "RepairRunner",
]
