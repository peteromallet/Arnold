"""File-backed audit hook support for the native pipeline runtime.

Implemented as a :class:`AuditHooks` that wraps an inner
:class:`NativeRuntimeHooks` instance and delegates every callback to it.
When *audit_dir* is set, audit records are appended to an ``audit.ndjson``
file (one JSON record per line) at the documented insertion points.

Each audit record captures:

* ``run_id`` — stable identifier for the run
* ``step_path`` — the stable tree-shaped path of the step
* ``attempt`` — attempt number (defaults to 1, incremented by retry wiring)
* ``input_keys`` — sorted list of input context dict keys
* ``output_keys`` — sorted list of output/result dict keys (success only)
* ``started_at`` / ``ended_at`` — ISO-8601 timestamps
* ``status`` — ``"success"`` or ``"failure"``
* ``error_type`` / ``error_message`` — exception details (failure only)

The audit file is written separately from ``resume_cursor.json`` and
checkpoints, providing an append-only audit trail that survives
suspension/resume cycles.

Example usage through :func:`run_native_pipeline`::

    result = run_native_pipeline(
        program,
        artifact_root="./run_01",
        audit_dir="./run_01/audit",
    )

Boundary discipline
-------------------
No ``megaplan`` imports.  No forbidden vocabulary literals.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping
from uuid import uuid4

from arnold.pipeline.native.hooks import (
    NativeRuntimeHooks,
    NullNativeRuntimeHooks,
)
from arnold.pipeline.native.ir import NativeInstruction


__all__ = [
    "AuditHooks",
    "AuditRecord",
]

# ── helpers ───────────────────────────────────────────────────────────


def _json_dumps(obj: Any) -> str:
    """Serialize *obj* to canonical JSON (sorted keys, compact)."""
    return json.dumps(
        obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str
    )


def _ensure_dir(path: Path) -> None:
    """Create directory *path* if it does not exist."""
    path.mkdir(parents=True, exist_ok=True)


def _utcnow_iso() -> str:
    """Return current UTC timestamp as ISO-8601 string."""
    return datetime.now(timezone.utc).isoformat()


def _dict_keys_summary(d: Any) -> list[str] | None:
    """Return sorted top-level keys of a dict-like, or None if not applicable."""
    if isinstance(d, Mapping):
        return sorted(str(k) for k in d.keys())
    return None


# ── AuditRecord ───────────────────────────────────────────────────────


class AuditRecord:
    """A single audit record representing one step attempt.

    This is a simple mutable bag used internally by :class:`AuditHooks`
    to accumulate per-step data before flushing to ``audit.ndjson``.
    It is not intended for direct construction by callers.
    """

    __slots__ = (
        "run_id",
        "step_path",
        "attempt",
        "input_keys",
        "output_keys",
        "started_at",
        "ended_at",
        "status",
        "error_type",
        "error_message",
    )

    def __init__(
        self,
        *,
        run_id: str,
        step_path: str,
        attempt: int = 1,
        input_keys: list[str] | None = None,
    ) -> None:
        self.run_id = run_id
        self.step_path = step_path
        self.attempt = attempt
        self.input_keys = input_keys
        self.output_keys: list[str] | None = None
        self.started_at: str = _utcnow_iso()
        self.ended_at: str | None = None
        self.status: str = "started"
        self.error_type: str | None = None
        self.error_message: str | None = None

    def mark_success(self, result: Any) -> None:
        """Finalize the record with a success outcome."""
        self.ended_at = _utcnow_iso()
        self.status = "success"
        self.output_keys = _dict_keys_summary(result)

    def mark_failure(self, exc: BaseException) -> None:
        """Finalize the record with a failure outcome."""
        self.ended_at = _utcnow_iso()
        self.status = "failure"
        self.error_type = type(exc).__name__
        self.error_message = str(exc)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a dictionary for NDJSON writing."""
        return {
            "run_id": self.run_id,
            "step_path": self.step_path,
            "attempt": self.attempt,
            "input_keys": self.input_keys,
            "output_keys": self.output_keys,
            "started_at": self.started_at,
            "ended_at": self.ended_at,
            "status": self.status,
            "error_type": self.error_type,
            "error_message": self.error_message,
        }


# ── AuditHooks ────────────────────────────────────────────────────────


class AuditHooks:
    """Native runtime hooks that emit file-backed audit records when enabled.

    Wraps an inner :class:`NativeRuntimeHooks` (default
    :class:`NullNativeRuntimeHooks`) and delegates every callback to it.
    When *audit_dir* is set, audit records are written to ``audit.ndjson``
    at the documented insertion points:

    * ``on_step_start`` — creates an in-progress :class:`AuditRecord`.
    * ``on_step_end`` — finalizes the record as ``"success"`` and flushes.
    * ``on_step_error`` — finalizes the record as ``"failure"`` and flushes.

    When *audit_dir* is ``None`` every callback is a pure pass-through
    to the inner hooks — there are no file-system operations.

    The audit file is append-only NDJSON (one JSON record per line),
    written separately from ``resume_cursor.json`` and checkpoints.
    """

    halt_reason: str | None

    def __init__(
        self,
        inner: NativeRuntimeHooks | None = None,
        *,
        audit_dir: str | Path | None = None,
    ) -> None:
        self._inner: NativeRuntimeHooks = (
            inner if inner is not None else NullNativeRuntimeHooks()
        )
        self._audit_dir: Path | None = (
            Path(audit_dir) if audit_dir is not None else None
        )
        self.halt_reason: str | None = None
        self._run_id: str = uuid4().hex
        self._attempts: dict[str, int] = {}
        self._active_record: AuditRecord | None = None

        if self._audit_dir is not None:
            _ensure_dir(self._audit_dir)
            # Write a run.init marker so tooling can discover runs
            self._append_record({
                "event": "run.init",
                "run_id": self._run_id,
                "started_at": _utcnow_iso(),
            })

    # ── private helpers ─────────────────────────────────────────────

    def _audit_path(self) -> Path | None:
        """Return the path to ``audit.ndjson``, or ``None`` if disabled."""
        if self._audit_dir is None:
            return None
        return self._audit_dir / "audit.ndjson"

    def _append_record(self, record: dict[str, Any]) -> None:
        """Append a JSON line to ``audit.ndjson``."""
        audit_file = self._audit_path()
        if audit_file is None:
            return
        line = _json_dumps(record)
        with open(audit_file, "a", encoding="utf-8") as fh:
            fh.write(line + "\n")

    def _flush_active(self) -> None:
        """Flush the active audit record to disk if one exists."""
        if self._active_record is not None:
            self._append_record(self._active_record.to_dict())
            self._active_record = None

    def _step_key(self, instr: NativeInstruction) -> str:
        """Return a stable key for a step (used for attempt counting)."""
        # Use name+pc as the step identity; this is stable across
        # suspension/resume because pc is deterministic.
        return f"{instr.name or instr.op}__pc{instr.pc}"

    def _resolve_step_path(self, ctx: dict[str, Any]) -> str:
        """Extract the stable step_path from context."""
        step_path = ctx.get("step_path")
        if isinstance(step_path, str) and step_path:
            return step_path
        run_path = ctx.get("run_path")
        if isinstance(run_path, str) and run_path:
            return run_path
        return "root"

    def _next_attempt(self, step_key: str) -> int:
        """Return the next attempt number for *step_key*."""
        current = self._attempts.get(step_key, 0)
        attempt = current + 1
        self._attempts[step_key] = attempt
        return attempt

    # ── NativeRuntimeHooks callbacks ─────────────────────────────────

    def on_step_start(
        self,
        instr: NativeInstruction,
        ctx: dict[str, Any],
    ) -> dict[str, Any]:
        ctx = self._inner.on_step_start(instr, ctx)
        if self._audit_dir is not None:
            step_key = self._step_key(instr)
            self._active_record = AuditRecord(
                run_id=self._run_id,
                step_path=self._resolve_step_path(ctx),
                attempt=self._next_attempt(step_key),
                input_keys=_dict_keys_summary(ctx),
            )
        return ctx

    def on_step_end(
        self,
        instr: NativeInstruction,
        ctx: dict[str, Any],
        result: Any,
    ) -> Any:
        result = self._inner.on_step_end(instr, ctx, result)
        if self._audit_dir is not None and self._active_record is not None:
            self._active_record.mark_success(result)
            self._flush_active()
        return result

    def on_step_error(
        self,
        instr: NativeInstruction,
        ctx: dict[str, Any],
        exc: BaseException,
    ) -> None:
        self._inner.on_step_error(instr, ctx, exc)
        if self._audit_dir is not None and self._active_record is not None:
            self._active_record.mark_failure(exc)
            self._flush_active()

    def merge_state(
        self,
        instr: NativeInstruction,
        state: dict[str, Any],
        outputs: dict[str, Any],
        owned_keys: frozenset[str],
    ) -> tuple[dict[str, Any], frozenset[str]]:
        return self._inner.merge_state(instr, state, outputs, owned_keys)

    def join_envelope(
        self,
        instr: NativeInstruction,
        current_envelope: Any,
        step_envelope: Any,
    ) -> Any:
        return self._inner.join_envelope(instr, current_envelope, step_envelope)

    def should_suspend(
        self,
        instr: NativeInstruction,
        state: dict[str, Any],
        result: Any,
    ) -> tuple[bool, str | None]:
        return self._inner.should_suspend(instr, state, result)

    def should_halt_loop(
        self,
        instr: NativeInstruction,
        state: dict[str, Any],
        iteration: int,
    ) -> tuple[bool, str | None]:
        return self._inner.should_halt_loop(instr, state, iteration)

    def on_stage_complete(
        self,
        instr: NativeInstruction,
        ctx: dict[str, Any],
        result: Any,
        state: dict[str, Any],
        owned_keys: frozenset[str],
    ) -> None:
        return self._inner.on_stage_complete(instr, ctx, result, state, owned_keys)

    def on_checkpoint(
        self,
        cursor: dict[str, Any],
        state: dict[str, Any],
    ) -> None:
        return self._inner.on_checkpoint(cursor, state)
