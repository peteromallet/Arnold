"""Optional native trace emission — write state, events, artifact inventory,
stage sequence, and final checkpoint notification to a trace directory.

Implemented as a :class:`NativeTraceHooks` that wraps an inner
:class:`NativeRuntimeHooks` instance and emits trace data to a
``trace_dir`` when it is set.  When ``trace_dir`` is ``None`` (the
default), the wrapper passes through to the inner hooks with zero
overhead beyond a few attribute accesses — there are no allocations,
no file opens, and no event journal writes.

Trace directory layout::

    <trace_dir>/
        state.json          # snapshot after each stage + final
        events.ndjson       # NdjsonEventJournal-compatible event stream
        stages.json         # ordered stage sequence
        artifacts.json      # content-hash inventory of output files
        checkpoint.json     # final checkpoint notification

Example usage through :func:`run_native_pipeline`::

    result = run_native_pipeline(
        program,
        artifact_root="./run_01",
        trace_dir="./run_01/traces",
    )
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from arnold.pipeline.native.hooks import (
    NativeRuntimeHooks,
    NullNativeRuntimeHooks,
)
from arnold.pipeline.native.ir import NativeInstruction
from arnold.runtime.event_journal import NdjsonEventJournal


__all__ = [
    "NativeTraceHooks",
    "write_artifact_inventory",
]

# ── helpers ───────────────────────────────────────────────────────────


def _json_dumps(obj: Any) -> str:
    """Serialize *obj* to canonical JSON (sorted keys, compact)."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


def _sha256_hex(data: bytes) -> str:
    """Return ``sha256:<hex>`` string for *data*."""
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _ensure_dir(path: Path) -> None:
    """Create directory *path* if it does not exist."""
    path.mkdir(parents=True, exist_ok=True)


def write_artifact_inventory(root: str | Path) -> dict[str, str]:
    """Walk *root* and return a ``{relpath: sha256:<hex>}`` mapping.

    Directories and non-regular files are skipped.  Symlinks are
    followed.  Files larger than 10 MiB are hashed in 1 MiB chunks.
    """
    root_path = Path(root)
    if not root_path.is_dir():
        return {}
    inventory: dict[str, str] = {}
    for entry in sorted(root_path.rglob("*")):
        if not entry.is_file():
            continue
        rel = str(entry.relative_to(root_path))
        try:
            sha = hashlib.sha256()
            with open(entry, "rb") as fh:
                while True:
                    chunk = fh.read(1024 * 1024)
                    if not chunk:
                        break
                    sha.update(chunk)
            inventory[rel] = "sha256:" + sha.hexdigest()
        except (OSError, PermissionError):
            inventory[rel] = "error:unreadable"
    return inventory


# ── NativeTraceHooks ──────────────────────────────────────────────────


class NativeTraceHooks:
    """Native runtime hooks that emit native-trace artifacts when enabled.

    Wraps an inner :class:`NativeRuntimeHooks` (default
    :class:`NullNativeRuntimeHooks`) and delegates every callback to it.
    When *trace_dir* is set, additional trace data is written to the
    trace directory at the documented insertion points:

    * ``on_step_start`` — writes a ``phase.start`` event.
    * ``on_step_end`` — writes a ``phase.end`` event.
    * ``on_step_error`` — writes an ``error`` event.
    * ``on_stage_complete`` — snapshots ``state.json``.
    * ``on_checkpoint`` — writes ``stages.json``, ``artifacts.json``,
      and ``checkpoint.json``.

    When *trace_dir* is ``None`` every callback is a pure pass-through
    to the inner hooks — there are no file-system operations.
    """

    halt_reason: str | None

    def __init__(
        self,
        inner: NativeRuntimeHooks | None = None,
        *,
        trace_dir: str | Path | None = None,
        artifact_root: str | Path = ".",
    ) -> None:
        self._inner: NativeRuntimeHooks = (
            inner if inner is not None else NullNativeRuntimeHooks()
        )
        self._trace_dir: Path | None = (
            Path(trace_dir) if trace_dir is not None else None
        )
        self._artifact_root: Path = Path(artifact_root)
        self.halt_reason: str | None = None
        self._journal: NdjsonEventJournal | None = None
        self._stage_seq: list[str] = []

        if self._trace_dir is not None:
            _ensure_dir(self._trace_dir)
            self._journal = NdjsonEventJournal(self._trace_dir)
            self._journal.emit("pipeline.init", payload={"status": "started"})
            self._write_state_json({})

    # ── private helpers ─────────────────────────────────────────────

    def _write_state_json(self, state: dict[str, Any]) -> None:
        """Write *state* as ``state.json`` in the trace directory."""
        if self._trace_dir is None:
            return
        (self._trace_dir / "state.json").write_text(
            _json_dumps(state), encoding="utf-8"
        )

    def _write_stages_json(self) -> None:
        """Write the ordered stage sequence as ``stages.json``."""
        if self._trace_dir is None:
            return
        (self._trace_dir / "stages.json").write_text(
            _json_dumps(self._stage_seq), encoding="utf-8"
        )

    def _write_artifacts_json(self) -> None:
        """Write an artifact inventory as ``artifacts.json``."""
        if self._trace_dir is None:
            return
        inventory = write_artifact_inventory(self._artifact_root)
        (self._trace_dir / "artifacts.json").write_text(
            _json_dumps(inventory), encoding="utf-8"
        )

    def _write_checkpoint_json(self, cursor: dict[str, Any], final: bool) -> None:
        """Write the final checkpoint notification as ``checkpoint.json``."""
        if self._trace_dir is None:
            return
        payload: dict[str, Any] = {
            "final": final,
            "stage_sequence": list(self._stage_seq),
            "cursor_stage": cursor.get("stage", ""),
            "cursor_pc": (
                cursor.get("native", {}).get("pc")
                if isinstance(cursor.get("native"), dict)
                else None
            ),
        }
        (self._trace_dir / "checkpoint.json").write_text(
            _json_dumps(payload), encoding="utf-8"
        )

    # ── NativeRuntimeHooks callbacks ─────────────────────────────────

    def on_step_start(
        self,
        instr: NativeInstruction,
        ctx: dict[str, Any],
    ) -> dict[str, Any]:
        ctx = self._inner.on_step_start(instr, ctx)
        if self._journal is not None:
            self._journal.emit(
                "phase.start",
                payload={"phase": instr.name, "pc": instr.pc},
                phase=instr.name,
            )
        return ctx

    def on_step_end(
        self,
        instr: NativeInstruction,
        ctx: dict[str, Any],
        result: Any,
    ) -> Any:
        result = self._inner.on_step_end(instr, ctx, result)
        if self._journal is not None:
            self._journal.emit(
                "phase.end",
                payload={"phase": instr.name, "pc": instr.pc},
                phase=instr.name,
            )
        return result

    def on_step_error(
        self,
        instr: NativeInstruction,
        ctx: dict[str, Any],
        exc: BaseException,
    ) -> None:
        self._inner.on_step_error(instr, ctx, exc)
        if self._journal is not None:
            self._journal.emit(
                "error",
                payload={
                    "phase": instr.name,
                    "pc": instr.pc,
                    "error_type": type(exc).__name__,
                    "error_message": str(exc),
                },
                phase=instr.name,
            )

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
        self._inner.on_stage_complete(instr, ctx, result, state, owned_keys)
        # Build stage id the same way the runtime does
        stage_id = f"{instr.name}__pc{instr.pc}"
        self._stage_seq.append(stage_id)
        self._write_state_json(state)
        if self._journal is not None:
            self._journal.emit(
                "stage.complete",
                payload={"stage": stage_id, "pc": instr.pc},
                phase=instr.name,
            )

    def on_checkpoint(
        self,
        cursor: dict[str, Any],
        state: dict[str, Any],
    ) -> None:
        self._inner.on_checkpoint(cursor, state)
        final = bool(cursor.get("final", False))
        self._write_state_json(state)
        self._write_stages_json()
        self._write_artifacts_json()
        self._write_checkpoint_json(cursor, final=final)
        if self._journal is not None:
            self._journal.emit(
                "checkpoint",
                payload={
                    "final": final,
                    "stage_count": len(self._stage_seq),
                },
            )
