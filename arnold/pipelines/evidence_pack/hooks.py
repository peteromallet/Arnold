"""Evidence-pack lifecycle hooks for the Arnold canonical executor.

``EvidencePackHooks`` wires the three runtime primitives — NDJSON event sink,
state persistence under lock, and resume-cursor persistence — into a single
``NullExecutorHooks`` subclass that evidence-pack pipelines inject at
executor bootstrap time.

Boundary discipline
-------------------

Zero megaplan imports.  No forbidden vocabulary literals.
All imports come from ``arnold.pipeline`` and ``arnold.runtime`` only.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from arnold.pipeline import (
    ContractStatus,
    NullExecutorHooks,
    ParallelStage,
    Stage,
    StepContext,
    StepResult,
    persist_resume_cursor,
)
from arnold.runtime.event_journal import NdjsonEventSink
from arnold.runtime.state_persistence import atomic_write_json, plan_state_lock

__all__ = ["EvidencePackHooks"]


class EvidencePackHooks(NullExecutorHooks):
    """Store-less lifecycle hooks for evidence-pack pipelines.

    Does NOT require a database, a Megaplan store, or a ``plan_dir``
    convention.  All state is persisted directly under *artifact_root*:

    * Events → ``<artifact_root>/events.ndjson`` (via ``NdjsonEventSink``).
    * State  → ``<artifact_root>/state.json`` (under ``.state.lock``).
    * Resume cursor → ``<artifact_root>/resume_cursor.json`` (when a step
      suspends with ``ContractStatus.SUSPENDED``).

    Parameters
    ----------
    artifact_root:
        Directory under which all artifacts are written.  Created if missing.
    """

    def __init__(self, artifact_root: str | Path) -> None:
        super().__init__()
        self._artifact_root = Path(artifact_root)
        self._artifact_root.mkdir(parents=True, exist_ok=True)
        self._sink = NdjsonEventSink(self._artifact_root)

    # ------------------------------------------------------------------
    # on_step_start
    # ------------------------------------------------------------------

    def on_step_start(
        self,
        stage: Stage | ParallelStage,
        ctx: StepContext,
    ) -> StepContext:
        """Emit ``phase_start`` event with the stage name."""
        self._sink.emit(
            "phase_start",
            payload={"stage": stage.name},
        )
        return ctx

    # ------------------------------------------------------------------
    # on_step_end
    # ------------------------------------------------------------------

    def on_step_end(
        self,
        stage: Stage | ParallelStage,
        ctx: StepContext,
        result: StepResult,
    ) -> StepResult:
        """Emit ``phase_end`` event and persist resume cursor on suspension."""
        self._sink.emit(
            "phase_end",
            payload={"stage": stage.name, "next": result.next},
        )

        # ── Suspension routing ──────────────────────────────────────
        contract = result.contract_result
        if contract is not None and contract.status == ContractStatus.SUSPENDED:
            suspension = contract.suspension
            resume_cursor_val = suspension.resume_cursor if suspension is not None else None
            persist_resume_cursor(
                self._artifact_root,
                stage=stage.name,
                resume_cursor=resume_cursor_val,
            )

        return result

    # ------------------------------------------------------------------
    # on_stage_complete
    # ------------------------------------------------------------------

    def on_stage_complete(
        self,
        stage: Stage | ParallelStage,
        ctx: StepContext,
        result: StepResult,
        state: Any,
        owned_keys: frozenset[str],
    ) -> None:
        """Write ``state.json`` under ``.state.lock`` and emit ``state_written``."""
        del ctx, result, owned_keys  # unused in this hook

        lock_path = self._artifact_root / ".state.lock"
        state_path = self._artifact_root / "state.json"

        with plan_state_lock(lock_path):
            atomic_write_json(state_path, state)

        # Emit after the write succeeds so the journal is a faithful
        # record of what was actually persisted.
        self._sink.emit(
            "state_written",
            payload={"stage": stage.name},
        )
