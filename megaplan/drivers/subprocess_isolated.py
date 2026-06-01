"""Subprocess-isolated driver for pipeline steps.

``SubprocessIsolatedDriver`` spawns a child process (via ``spawn()``, which
sets ``start_new_session=True`` so the child is its own process-group leader)
and supervises it using the extracted ``_supervise_subprocess`` watcher from
``megaplan.auto``.  On timeout the whole process group is reaped via
``kill_group``.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from megaplan._pipeline.types import StepContext, StepResult
from megaplan.auto import _supervise_subprocess
from megaplan.runtime.process import spawn


@dataclass
class SubprocessIsolatedDriver:
    """Runs a pipeline step as an isolated subprocess.

    The child runs in its own session / process group (``start_new_session=True``
    via ``spawn()``), so ``kill_group`` can reap the entire tree on timeout.

    Attributes:
        name: Step identifier forwarded to the pipeline registry.
        kind: Step kind (default ``"produce"``).
        argv: Argument vector for the child process.
        idle_cap: Seconds without output before the child is killed (None = no cap).
        wall_cap: Hard wall-clock cap (None = no cap).
    """

    name: str = "subprocess_isolated"
    kind: Literal["produce", "judge", "decide", "subloop", "override"] = "produce"
    prompt_key: str | None = None
    slot: str | None = None
    produces: tuple[Any, ...] = ()
    consumes: tuple[Any, ...] = ()

    argv: list[str] = field(default_factory=list)
    idle_cap: float | None = None
    wall_cap: float | None = None

    def run_step(self, ctx: StepContext) -> StepResult:
        """Spawn *argv*, supervise, and return a ``StepResult``.

        On success (exit 0) the step patches ``state_patch`` with
        ``exit_code``, ``stdout``, and ``stderr``.  On timeout the exit
        code is 124 (``PHASE_TIMEOUT_EXIT_CODE``) and stderr carries a
        marker explaining the timeout reason.
        """
        proc = spawn(
            self.argv,
            cwd=ctx.plan_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=None,
        )
        exit_code, stdout, stderr, _state = _supervise_subprocess(
            proc,
            ctx.plan_dir,
            self.idle_cap,
            self.wall_cap,
            args=self.argv,
        )
        return StepResult(
            next="halt",
            state_patch={
                "exit_code": exit_code,
                "stdout": stdout,
                "stderr": stderr,
            },
        )
