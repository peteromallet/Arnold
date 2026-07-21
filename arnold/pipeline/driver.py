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
from arnold.workflow.native_wbc import begin_native_wbc_attempt


class StepwiseDriver:
    """Minimal concrete driver for neutral host-managed workflow starts."""

    isolation_mode = "in_process"

    def advance(self, envelope: RuntimeEnvelope) -> AdvanceOutcome:
        attempt = begin_native_wbc_attempt(
            envelope.artifact_root,
            producer_family="arnold_pipeline",
            surface="driver.advance",
            run_id=envelope.run_id,
            plugin_id=envelope.plugin_id,
            manifest_hash=envelope.manifest_hash,
            subject={"run_id": envelope.run_id},
            metadata={"isolation_mode": self.isolation_mode},
        )
        outcome = AdvanceOutcome(kind="advanced", payload={"run_id": envelope.run_id})
        attempt.effect("advance", {"run_id": envelope.run_id})
        attempt.terminal(status="completed", outcome=outcome.kind, payload=outcome.payload)
        return outcome

    def checkpoint(self, envelope: RuntimeEnvelope) -> CheckpointOutcome:
        attempt = begin_native_wbc_attempt(
            envelope.artifact_root,
            producer_family="arnold_pipeline",
            surface="driver.checkpoint",
            run_id=envelope.run_id,
            plugin_id=envelope.plugin_id,
            manifest_hash=envelope.manifest_hash,
            subject={"run_id": envelope.run_id},
            metadata={"isolation_mode": self.isolation_mode},
        )
        outcome = CheckpointOutcome(kind="advanced", payload={"run_id": envelope.run_id})
        attempt.effect("checkpoint", {"run_id": envelope.run_id})
        attempt.terminal(status="completed", outcome=outcome.kind, payload=outcome.payload)
        return outcome

    def resume(
        self,
        envelope: RuntimeEnvelope,
        cursor: ResumeCursorRef,
    ) -> RuntimeEnvelope:
        attempt = begin_native_wbc_attempt(
            envelope.artifact_root,
            producer_family="arnold_pipeline",
            surface="driver.resume",
            run_id=cursor.run_id or envelope.run_id,
            plugin_id=cursor.plugin_id or envelope.plugin_id,
            manifest_hash=envelope.manifest_hash,
            subject={"cursor_stage": cursor.cursor.get("stage"), "run_id": cursor.run_id},
            metadata={"isolation_mode": self.isolation_mode},
        )
        resumed = replace(envelope, resume_cursor=cursor)
        attempt.effect("resume", {"cursor_keys": sorted(cursor.cursor.keys())})
        attempt.terminal(
            status="completed",
            outcome="resumed",
            payload={"run_id": resumed.run_id, "resume_cursor": resumed.resume_cursor is not None},
        )
        return resumed


__all__ = ["StepwiseDriver"]
