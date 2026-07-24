"""Subprocess-isolated driver for pipeline steps.

``SubprocessIsolatedDriver`` spawns a child process (via ``spawn()``, which
sets ``start_new_session=True`` so the child is its own process-group leader)
and supervises it using the extracted ``_supervise_subprocess`` watcher from
``megaplan.auto``.  On timeout the whole process group is reaped via
``kill_group``.

M3d enhancement: accepts optional ``BatchRuntimeSettings`` scalars and
computes an effective wall cap as ``min(wall_cap | wall_timeout_s,
deadline_remaining_s)`` at ``run_step`` time.  An already-expired deadline
returns a neutral ``StepResult`` rather than raising.
"""

from __future__ import annotations

import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal, TYPE_CHECKING

from arnold_pipelines.megaplan.step_types import StepContext, StepResult
from arnold_pipelines.megaplan.auto import _supervise_subprocess
from arnold_pipelines.megaplan.runtime.process import spawn

if TYPE_CHECKING:
    from arnold_pipelines.megaplan.runtime.batch import BatchRuntimeSettings


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
        batch_settings: Optional neutral batch runtime settings carrying
            deadline and timeout scalars.  When provided, the effective wall
            cap is clamped to ``min(wall_cap | wall_timeout_s,
            deadline_remaining_s)`` at ``run_step`` time.
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
    batch_settings: Any = None  # BatchRuntimeSettings | None — typed as Any to avoid arnold import at module level

    def run_step(self, ctx: StepContext) -> StepResult:
        """Spawn *argv*, supervise, and return a ``StepResult``.

        On success (exit 0) the step patches ``state_patch`` with
        ``exit_code``, ``stdout``, and ``stderr``.  On timeout the exit
        code is 124 (``PHASE_TIMEOUT_EXIT_CODE``) and stderr carries a
        marker explaining the timeout reason.

        When ``batch_settings`` is provided, the effective wall cap is
        computed at invocation time as ``min(explicit_wall_cap,
        deadline_remaining_s)``.  If the deadline has already expired,
        a neutral ``StepResult`` is returned immediately.
        """
        effective_wall_cap = self.wall_cap

        # --- M3d: deadline-aware wall cap from BatchRuntimeSettings ---
        bs = self.batch_settings
        if bs is not None:
            wall_timeout_s: float | None = getattr(bs, "wall_timeout_s", None)
            deadline_epoch_s: float | None = getattr(bs, "deadline_epoch_s", None)

            # Incorporate wall_timeout_s as a candidate wall cap
            if wall_timeout_s is not None:
                if effective_wall_cap is None or wall_timeout_s < effective_wall_cap:
                    effective_wall_cap = wall_timeout_s

            # Clamp to remaining deadline
            if deadline_epoch_s is not None:
                remaining = deadline_epoch_s - time.time()
                if remaining <= 0:
                    # Deadline already expired — return neutral outcome
                    return StepResult(
                        next="halt",
                        state_patch={
                            "exit_code": None,
                            "stdout": "",
                            "stderr": "deadline expired before step started",
                        },
                    )
                if effective_wall_cap is None or remaining < effective_wall_cap:
                    effective_wall_cap = remaining

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
            effective_wall_cap,
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
