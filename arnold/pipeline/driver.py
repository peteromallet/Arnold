"""Concrete default stepwise driver exported through ``arnold.pipeline``.

The runtime package owns the protocol and carrier dataclasses. This module
provides the no-argument concrete provider expected by external hosts that
launch Arnold workflows through the neutral ``arnold.pipeline`` surface.
"""

from __future__ import annotations

from dataclasses import replace

from arnold.execution.driver import AdvanceOutcome, CheckpointOutcome
from arnold.runtime.envelope import RuntimeEnvelope
from arnold.runtime.resume import ResumeCursorRef


class StepwiseDriver:
    """Minimal concrete driver for neutral host-managed workflow starts."""

    isolation_mode = "in_process"

    def advance(self, envelope: RuntimeEnvelope) -> AdvanceOutcome:
        return AdvanceOutcome(kind="advanced", payload={"run_id": envelope.run_id})

    def checkpoint(self, envelope: RuntimeEnvelope) -> CheckpointOutcome:
        return CheckpointOutcome(kind="advanced", payload={"run_id": envelope.run_id})

    def resume(
        self,
        envelope: RuntimeEnvelope,
        cursor: ResumeCursorRef,
    ) -> RuntimeEnvelope:
        return replace(envelope, resume_cursor=cursor)


__all__ = ["StepwiseDriver"]
