"""Repair-runner adapter with broken-CLI resilience."""

from __future__ import annotations

import os
import shlex
import shutil
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence

from arnold_pipelines.megaplan.cloud.repair_contract import append_attempt_record


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
    executed as ``python -m arnold_pipelines.megaplan <subcommand> ...`` inside
    the plan's project directory. System commands (``rm``, ``kill``) are run
    directly. If the executable is missing or the command cannot be run, returns
    a ``command_unavailable`` result instead of crashing.
    """

    def __init__(
        self,
        executable_search_path: Sequence[str] | None = None,
        python_bin: str | None = None,
        evidence_sidecar_dir: str | None = None,
        evidence_session: str = "",
    ) -> None:
        self._search_path = executable_search_path
        self._python_bin = python_bin or shutil.which("python3") or shutil.which("python") or "python"
        self._evidence_sidecar_dir = evidence_sidecar_dir or os.environ.get(
            "CLOUD_WATCHDOG_REPAIR_SIDECAR_DIR",
            "",
        )
        self._evidence_session = evidence_session or os.environ.get("SESSION", "")

    def _is_dry_run(self) -> bool:
        """An empty search path signals dry-run: do not execute anything."""
        return self._search_path is not None and len(self._search_path) == 0

    @staticmethod
    def _with_default_profile(parts: list[str]) -> list[str]:
        """Inject ``--profile partnered-5`` for allowlisted repair subcommands.

        Megaplan repair commands (``doctor``/``auto``/``resume``/``chain``) inherit
        the engine default profile when none is given. The meta-loop repair layer
        runs under the partnered-5 profile (validated at
        ``arnold_pipelines/megaplan/profiles/partnered-5.toml``); route repairs
        through it unless the caller already pinned a ``--profile``.
        """
        if any(p == "--profile" or p.startswith("--profile=") for p in parts):
            return parts
        return parts + ["--profile", "partnered-5"]

    def _argv_for_command(self, command: str) -> tuple[list[str], str | None, bool]:
        """Return (argv, cwd, is_megaplan_subcommand) for *command*.

        Megaplan subcommands are always rewritten to
        ``python -P -m arnold_pipelines.megaplan`` so the subprocess cannot
        import stale checkout-local packages from the active workflow cwd.
        System commands are passed through. The returned cwd is the directory in
        which the command should run, or None for the current directory.
        """
        if self._is_dry_run():
            return [], None, False

        parts = shlex.split(command)
        if not parts:
            return [], None, False

        first = parts[0]
        # Detect an explicit project-dir marker injected by the CLI: "cd /path && cmd"
        if first == "cd" and len(parts) >= 4 and parts[2] == "&&":
            cwd = parts[1].strip("'\"")
            parts = parts[3:]
            first = parts[0] if parts else ""
        else:
            cwd = None

        if first in _MEGAPLAN_SUBCOMMANDS:
            return [self._python_bin, "-P", "-m", "arnold_pipelines.megaplan"] + parts, cwd, True

        # Bare subcommands like "rm" or "kill" that are not standalone executables
        # but are safe shell builtins/utilities.
        if first in {"rm", "kill"}:
            return ["/bin/bash", "-c", " ".join(parts)], cwd, False

        executable = shutil.which(first, path=self._search_path)
        if executable is None:
            return [], cwd, False
        return [executable] + parts[1:], cwd, False

    def _megaplan_subcommand_env(self, base: dict[str, str] | None = None) -> dict[str, str]:
        """Anchor Megaplan subprocesses to the editable install engine checkout."""

        from arnold_pipelines.megaplan.runtime.process import (
            megaplan_engine_env,
            megaplan_engine_root,
        )

        env = megaplan_engine_env(base)
        env.setdefault("MEGAPLAN_ENGINE_ROOT", str(megaplan_engine_root()))
        env["PYTHONSAFEPATH"] = "1"
        # Meta-loop repairs default to the validated partnered-5 profile
        # (arnold_pipelines/megaplan/profiles/partnered-5.toml). Plan configs that
        # pin an explicit profile still win; this only fills the gap when a
        # repair context would otherwise inherit the engine default "partnered".
        env.setdefault("MEGAPLAN_DEFAULT_PROFILE", "partnered-5")
        env.setdefault("MEGAPLAN_REPAIR_PROFILE", "partnered-5")
        return env

    def run(
        self,
        command: str,
        *,
        plan_dir: str | None = None,
        project_dir: str | None = None,
    ) -> RepairResult:
        """Execute *command* and return a structured result."""
        argv, argv_cwd, is_megaplan_subcommand = self._argv_for_command(command)
        if not argv:
            result = RepairResult(
                status="command_unavailable",
                stdout="",
                stderr=f"executable not found or unsupported command: {command!r}",
                rc=None,
            )
            self._append_evidence(command, result, project_dir=project_dir, plan_dir=plan_dir)
            return result

        cwd = argv_cwd or project_dir
        if cwd is None and plan_dir is not None:
            # Fall back to the plan directory's repo root.
            try:
                cwd = str(Path(plan_dir).parents[2])
            except Exception:
                pass

        env = (
            self._megaplan_subcommand_env(os.environ.copy())
            if is_megaplan_subcommand
            else os.environ.copy()
        )
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
            repair_result = RepairResult(
                status=status,
                stdout=result.stdout,
                stderr=result.stderr,
                rc=result.returncode,
            )
            self._append_evidence(command, repair_result, project_dir=cwd, plan_dir=plan_dir)
            return repair_result
        except (FileNotFoundError, OSError) as exc:
            result = RepairResult(
                status="command_unavailable",
                stdout="",
                stderr=f"could not execute {argv!r}: {exc}",
                rc=None,
            )
            self._append_evidence(command, result, project_dir=cwd, plan_dir=plan_dir)
            return result
        except subprocess.TimeoutExpired:
            result = RepairResult(
                status="timeout",
                stdout="",
                stderr="command timed out after 300s",
                rc=None,
            )
            self._append_evidence(command, result, project_dir=cwd, plan_dir=plan_dir)
            return result

    def _append_evidence(
        self,
        command: str,
        result: RepairResult,
        *,
        project_dir: str | None,
        plan_dir: str | None,
    ) -> None:
        if not self._evidence_sidecar_dir:
            return
        recorded_at = datetime.now(timezone.utc).isoformat()
        append_attempt_record(
            self._evidence_sidecar_dir,
            {
                "session_id": self._evidence_session,
                "attempt_id": f"repair-runner:{recorded_at}",
                "actor": "watchdog.repair_runner",
                "command": command,
                "state": self._result_state(result.status),
                "outcome": result.status,
                "returncode": result.rc,
                "project_dir": project_dir or "",
                "plan_dir": plan_dir or "",
                "recorded_at": recorded_at,
            },
        )

    @staticmethod
    def _result_state(status: str) -> str:
        if status == "success":
            return "succeeded"
        if status == "timeout":
            return "running"
        return "failed"


__all__ = [
    "RepairResult",
    "RepairRunner",
]
