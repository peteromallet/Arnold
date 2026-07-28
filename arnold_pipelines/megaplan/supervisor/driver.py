"""Supervisor run-driver seam over the existing auto-driver loop.

M5d keeps the current M3-compatible subprocess-backed run behavior by
wrapping ``megaplan.auto.drive`` behind a small protocol.  The protocol is
fake-friendly for upcoming chain/bakeoff supervisor tests, while the
``PackRunner`` protocol deliberately stays narrow until the M6 discovered-pack
execution API stabilizes.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Protocol, runtime_checkable

from arnold_pipelines.megaplan.auto import (
    DEFAULT_MAX_ITERATIONS,
    DEFAULT_PHASE_TIMEOUT_SECONDS,
    DEFAULT_POLL_SLEEP_SECONDS,
    DEFAULT_STALL_THRESHOLD,
    DEFAULT_STATUS_TIMEOUT_SECONDS,
    ESCALATE_ACTIONS as AUTO_ESCALATE_ACTIONS,
    DriverOutcome,
    drive as auto_drive,
)
from arnold_pipelines.megaplan.custody.admission_control import (
    AdmissionFence,
    SUPERVISOR_ADMISSION_SURFACE,
    SUPERVISOR_ADMISSION_WRITER_ID,
    register_admission_writers,
    synthetic_text_source_record,
    validate_admission_mutation,
)
from arnold_pipelines.megaplan.supervisor.model import RunNode

RunWriter = Callable[[str], object]
PhaseCompleteHook = Callable[[str, int, str, str], None]
DEFAULT_ESCALATE_ACTION = AUTO_ESCALATE_ACTIONS[0]


@dataclass(frozen=True)
class RunRequest:
    """Stable supervisor request for one plan-driving invocation."""

    root: Path
    plan: str
    stall_threshold: int = DEFAULT_STALL_THRESHOLD
    max_iterations: int = DEFAULT_MAX_ITERATIONS
    poll_sleep: float = DEFAULT_POLL_SLEEP_SECONDS
    phase_timeout: float = DEFAULT_PHASE_TIMEOUT_SECONDS
    status_timeout: float = DEFAULT_STATUS_TIMEOUT_SECONDS
    escalate_action: str = DEFAULT_ESCALATE_ACTION
    on_phase_complete: PhaseCompleteHook | None = None
    writer: RunWriter = sys.stdout.write


@runtime_checkable
class RunDriver(Protocol):
    """Minimal supervisor contract for driving one initialized run."""

    def drive(self, request: RunRequest) -> DriverOutcome:
        """Drive ``request.plan`` and return the raw auto-driver outcome."""
        ...


class DefaultRunDriver:
    """Adapter that preserves the existing subprocess-loop auto-driver path."""

    def drive(self, request: RunRequest) -> DriverOutcome:
        register_admission_writers()
        validate_admission_mutation(
            writer_id=SUPERVISOR_ADMISSION_WRITER_ID,
            surface_name=SUPERVISOR_ADMISSION_SURFACE,
            selector=request.plan,
            source_record=synthetic_text_source_record(
                selector=request.plan,
                label="supervisor-run-request",
                text="\n".join((str(request.root), request.plan)),
            ),
            fences=(
                AdmissionFence(
                    identity="request_root_exists",
                    expected=True,
                    observed=request.root.exists(),
                    satisfied=request.root.exists(),
                    detail="supervisor dispatch requires an existing project root",
                ),
            ),
            extra={"root": str(request.root)},
        )
        return auto_drive(
            request.plan,
            cwd=request.root,
            stall_threshold=request.stall_threshold,
            max_iterations=request.max_iterations,
            on_escalate=request.escalate_action,
            poll_sleep=request.poll_sleep,
            phase_timeout=request.phase_timeout,
            status_timeout=request.status_timeout,
            on_phase_complete=request.on_phase_complete,
            writer=request.writer,
        )


@runtime_checkable
class PackRunner(Protocol):
    """Temporary seam for pack-backed run initialization.

    M5d does not assume any stable M6 discovered-pack execution API yet.
    The only documented contract is: given a supervisor run node, produce the
    plan name that a ``RunDriver`` should execute. Unit tests should inject
    fakes instead of invoking live pack discovery or pack execution.
    """

    def prepare_plan(self, *, root: Path, node: RunNode) -> str:
        """Return the initialized plan name for ``node``."""
        ...


__all__ = [
    "DEFAULT_ESCALATE_ACTION",
    "DefaultRunDriver",
    "PackRunner",
    "PhaseCompleteHook",
    "RunDriver",
    "RunRequest",
    "RunWriter",
]
