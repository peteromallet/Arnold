"""Append-only ndjson event journal per plan.

Every plan gets one ``events.ndjson`` file in its plan directory.
The writer uses a sidecar ``.events.seq`` counter protected by ``fcntl.flock``
to guarantee monotonic sequence numbers across concurrent writers (parent
driver + child workers).

Usage::

    from megaplan.observability.events import emit, EventKind

    emit(EventKind.INIT, plan_dir=plan_dir, payload={"plan_name": "my-plan"})
"""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import threading
import time
import warnings
from contextvars import ContextVar
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, Generator, Iterator, Optional, Sequence, Set

if TYPE_CHECKING:
    from megaplan._pipeline.envelope import RunEnvelope


# ---------------------------------------------------------------------------
# M4 T9 — observability-side envelope ContextVar (run_id carrier).
#
# install_runtime_governor seats the active RunEnvelope here on enter and
# clears it on exit (via the token returned by ContextVar.set).  Event emits
# read this ContextVar to resolve the current run_id; when the ContextVar is
# unset, the emit proceeds WITHOUT a run_id and WARN_ONCE is fired exactly
# once for the lifetime of the process so the missing-carrier case is loud
# without spamming the log on every emit.
#
# EventWriter.emit's signature is intentionally unchanged at this step — the
# run_id is injected into the emitted event dict as a sibling key when an
# envelope is in scope.
# ---------------------------------------------------------------------------

_envelope_ctx: ContextVar[Optional["RunEnvelope"]] = ContextVar(
    "_envelope_ctx_events", default=None
)

_missing_envelope_ctx_warned: bool = False
_missing_envelope_ctx_warn_lock = threading.Lock()


def _warn_missing_envelope_ctx_once() -> None:
    global _missing_envelope_ctx_warned
    with _missing_envelope_ctx_warn_lock:
        if _missing_envelope_ctx_warned:
            return
        _missing_envelope_ctx_warned = True
    warnings.warn(
        "observability.events: emit() invoked with no RunEnvelope in "
        "_envelope_ctx; emitting without run_id (M4 T9 WARN_ONCE).",
        RuntimeWarning,
        stacklevel=3,
    )


def _reset_missing_envelope_ctx_warned_for_tests() -> None:
    """Test hook — re-arms the WARN_ONCE latch."""
    global _missing_envelope_ctx_warned
    with _missing_envelope_ctx_warn_lock:
        _missing_envelope_ctx_warned = False


def _resolve_run_id() -> Optional[str]:
    """Return the run_id derived from the active RunEnvelope, or None.

    When the ContextVar is unset, fires WARN_ONCE and returns None so the
    caller emits the envelope WITHOUT a run_id field.
    """
    env = _envelope_ctx.get()
    if env is None:
        _warn_missing_envelope_ctx_once()
        return None
    rid = getattr(env, "run_id", None)
    if rid:
        return str(rid)
    lineage = getattr(env, "lineage", ()) or ()
    if lineage:
        return str(lineage[0])
    return None


# ---------------------------------------------------------------------------
# Event-kind enumeration (string-literal aliases)
# ---------------------------------------------------------------------------

class EventKind:
    """String-literal constants for all 27 event kinds.

    Use these instead of bare strings so typos are caught at import time.
    """

    # ── Lifecycle (9) ──────────────────────────────────────────────────
    INIT: str = "init"
    PHASE_START: str = "phase_start"
    PHASE_END: str = "phase_end"
    PHASE_RETRY: str = "phase_retry"
    STATE_TRANSITION: str = "state_transition"
    STATE_WRITTEN: str = "state_written"
    LOCK_ACQUIRED: str = "lock_acquired"
    LOCK_RELEASED: str = "lock_released"
    PLAN_ABORTED: str = "plan_aborted"
    PLAN_FINISHED: str = "plan_finished"

    # ── Subprocess (3) ─────────────────────────────────────────────────
    SUBPROCESS_SPAWNED: str = "subprocess_spawned"
    SUBPROCESS_EXITED: str = "subprocess_exited"
    SUBPROCESS_SIGNALED: str = "subprocess_signaled"

    # ── LLM (4) ────────────────────────────────────────────────────────
    LLM_CALL_START: str = "llm_call_start"
    LLM_TOKEN_HEARTBEAT: str = "llm_token_heartbeat"
    LLM_CALL_END: str = "llm_call_end"
    LLM_CALL_ERROR: str = "llm_call_error"

    # ── Artifacts (2) ──────────────────────────────────────────────────
    ARTIFACT_WRITTEN: str = "artifact_written"
    ARTIFACT_INVALIDATED: str = "artifact_invalidated"

    # ── Decisions (4) ──────────────────────────────────────────────────
    OVERRIDE_APPLIED: str = "override_applied"
    FLAG_RAISED: str = "flag_raised"
    FLAG_RESOLVED: str = "flag_resolved"
    NOTE_ADDED: str = "note_added"
    # Auto-driver escalated execute to a more capable tier model after
    # repeated failures (payload: model/tier from→to, task/batch, fail count).
    TIER_ESCALATED: str = "tier_escalated"

    # ── Cost (1) ───────────────────────────────────────────────────────
    COST_RECORDED: str = "cost_recorded"

    # ── Diagnostics (2) ────────────────────────────────────────────────
    HEALTH_CHECK_FAILED: str = "health_check_failed"
    DRIFT_DETECTED: str = "drift_detected"

    # ── Activation (1) ─────────────────────────────────────────────────
    ACTIVATION_TRANSITIONED: str = "activation_transitioned"

    # ── R1 authority (1) ───────────────────────────────────────────────
    # WAL-fold rebuild disagreed with on-disk state.json cache; cache was
    # rewritten with the WAL-derived truth.
    STATE_CACHE_DRIFT: str = "state_cache_drift"


# Convenience set for fast membership checks.
_ALL_EVENT_KINDS: Set[str] = frozenset(
    {
        EventKind.INIT,
        EventKind.PHASE_START,
        EventKind.PHASE_END,
        EventKind.PHASE_RETRY,
        EventKind.STATE_TRANSITION,
        EventKind.STATE_WRITTEN,
        EventKind.LOCK_ACQUIRED,
        EventKind.LOCK_RELEASED,
        EventKind.PLAN_ABORTED,
        EventKind.PLAN_FINISHED,
        EventKind.SUBPROCESS_SPAWNED,
        EventKind.SUBPROCESS_EXITED,
        EventKind.SUBPROCESS_SIGNALED,
        EventKind.LLM_CALL_START,
        EventKind.LLM_TOKEN_HEARTBEAT,
        EventKind.LLM_CALL_END,
        EventKind.LLM_CALL_ERROR,
        EventKind.ARTIFACT_WRITTEN,
        EventKind.ARTIFACT_INVALIDATED,
        EventKind.OVERRIDE_APPLIED,
        EventKind.FLAG_RAISED,
        EventKind.FLAG_RESOLVED,
        EventKind.NOTE_ADDED,
        EventKind.TIER_ESCALATED,
        EventKind.COST_RECORDED,
        EventKind.HEALTH_CHECK_FAILED,
        EventKind.DRIFT_DETECTED,
        EventKind.ACTIVATION_TRANSITIONED,
        EventKind.STATE_CACHE_DRIFT,
    }
)


# ---------------------------------------------------------------------------
# Sidecar file names
# ---------------------------------------------------------------------------

_SEQ_FILE = ".events.seq"
_INIT_TS_FILE = ".events.init_ts"
_NDJSON_FILE = "events.ndjson"


# ---------------------------------------------------------------------------
# EventWriter
# ---------------------------------------------------------------------------

class EventWriter:
    """Appends one JSON event per line to ``plan_dir/events.ndjson``.

    Thread-safe and process-safe for concurrent writers that share the same
    plan directory: the full critical section (read seq → increment → write
    counter → append event → release lock) is guarded by ``fcntl.flock`` on
    the sidecar ``.events.seq`` file.

    Typical usage (module-level singleton per plan_dir)::

        from megaplan.observability.events import EventWriter

        writer = EventWriter(plan_dir)
        writer.emit("init", payload={"plan_name": "my-plan"})
    """

    def __init__(self, plan_dir: Path) -> None:
        self._plan_dir = Path(plan_dir)
        self._plan_dir.mkdir(parents=True, exist_ok=True)
        self._ndjson_path = self._plan_dir / _NDJSON_FILE
        self._seq_path = self._plan_dir / _SEQ_FILE
        self._init_ts_path = self._plan_dir / _INIT_TS_FILE

        # Per-instance lock for thread safety within the same process.
        self._thread_lock = threading.Lock()

    # ── public API ─────────────────────────────────────────────────────

    def emit(
        self,
        kind: str,
        *,
        phase: Optional[str] = None,
        payload: Optional[Dict[str, Any]] = None,
    ) -> dict:
        """Write one event to the journal and return it as a dict.

        Returns the full event dict (including the assigned ``seq``) so
        callers can inspect or further process it.

        The entire critical section (seq read → increment → counter write →
        event append → flock release) is guarded by fcntl.flock on the
        sidecar ``.events.seq`` file, guaranteeing monotonic seq *and*
        strict file order even across multiple OS processes.
        """
        ts_utc = datetime.now(timezone.utc)

        with self._thread_lock:
            init_ts = self._load_init_ts()

            # Build the event dict first so we know the line to write.
            # M4 T10: schema_version=1 pinned in the NDJSON envelope; run_id
            # added below from the active _envelope_ctx.
            event: dict = {
                "seq": -1,  # placeholder — assigned under flock
                "schema_version": 1,
                "ts_utc": ts_utc.isoformat(),
                "ts_rel_init_s": None,
                "kind": kind,
                "phase": phase,
                "payload": payload if payload is not None else {},
            }
            # M4 T9: inject run_id resolved from the active RunEnvelope when
            # one is in scope.  Missing context omits the field and fires
            # WARN_ONCE on the first miss (no signature change to emit()).
            _rid = _resolve_run_id()
            if _rid is not None:
                event["run_id"] = _rid
            if init_ts is not None:
                event["ts_rel_init_s"] = (ts_utc - init_ts).total_seconds()
            if kind == EventKind.INIT and init_ts is None:
                event["ts_rel_init_s"] = 0.0

            line = json.dumps(event, ensure_ascii=False, separators=(",", ":"))

            # ── FULL critical section under flock ─────────────────────
            # Open or create both the seq counter and the ndjson file.
            seq_fd = os.open(str(self._seq_path), os.O_RDWR | os.O_CREAT, 0o644)
            ndjson_fd = os.open(
                str(self._ndjson_path),
                os.O_WRONLY | os.O_APPEND | os.O_CREAT,
                0o644,
            )
            try:
                fcntl.flock(seq_fd, fcntl.LOCK_EX)

                # (1) Read → increment → write seq counter.
                try:
                    raw = os.read(seq_fd, 128)
                    current = int(raw.strip()) if raw.strip() else -1
                except (ValueError, FileNotFoundError):
                    current = -1
                new_seq = current + 1
                os.lseek(seq_fd, 0, os.SEEK_SET)
                os.write(seq_fd, str(new_seq).encode("ascii"))
                os.ftruncate(seq_fd, os.lseek(seq_fd, 0, os.SEEK_CUR))
                os.fsync(seq_fd)

                # (2) Patch the real seq into the event line and append.
                event["seq"] = new_seq
                final_line = json.dumps(event, ensure_ascii=False, separators=(",", ":"))
                os.write(ndjson_fd, (final_line + "\n").encode("utf-8"))
                os.fsync(ndjson_fd)

                # (3) Release flock AFTER both writes are complete.
                fcntl.flock(seq_fd, fcntl.LOCK_UN)
            finally:
                # Close regardless of lock state (already unlocked if we
                # reached the explicit unlock above; still safe to call).
                try:
                    os.close(seq_fd)
                except OSError:
                    pass
                try:
                    os.close(ndjson_fd)
                except OSError:
                    pass

            # Persist init timestamp outside the critical section (it's
            # only written once and races on it are benign — the first
            # writer wins and the value is immutable).
            if kind == EventKind.INIT and init_ts is None:
                self._write_init_ts(ts_utc)

        return event

    def _load_init_ts(self) -> Optional[datetime]:
        """Return the init timestamp cached in .events.init_ts, or None."""
        if not self._init_ts_path.exists():
            return None
        try:
            raw = self._init_ts_path.read_text(encoding="utf-8").strip()
            return datetime.fromisoformat(raw)
        except (ValueError, OSError):
            return None

    def _write_init_ts(self, ts: datetime) -> None:
        """Persist the init timestamp to .events.init_ts."""
        self._init_ts_path.write_text(ts.isoformat(), encoding="utf-8")


# ---------------------------------------------------------------------------
# Module-level emit helper (convenience)
# ---------------------------------------------------------------------------

_WRITERS: Dict[str, EventWriter] = {}
_WRITERS_LOCK = threading.Lock()


def _writer_key(plan_dir: Path) -> str:
    return str(plan_dir.resolve())


def _get_writer(plan_dir: Path) -> EventWriter:
    key = _writer_key(plan_dir)
    with _WRITERS_LOCK:
        writer = _WRITERS.get(key)
        if writer is None:
            writer = EventWriter(plan_dir)
            _WRITERS[key] = writer
        return writer


def emit(
    kind: str,
    plan_dir: Path,
    *,
    phase: Optional[str] = None,
    payload: Optional[Dict[str, Any]] = None,
) -> dict:
    """Module-level convenience: write one event to *plan_dir*/events.ndjson.

    Returns the full event dict.
    """
    return _get_writer(plan_dir).emit(kind, phase=phase, payload=payload)


def compute_model_identity(
    model_name: str | None, reported_version: str | None = None
) -> str:
    """Return a deterministic sha256 hex digest identifying a model.

    The digest is built from ``f"{model_name}\\x00{reported_version}".encode()``.
    Uses ``hashlib.sha256`` (NOT Python's salted ``hash()``) so the value is
    stable across processes and runs — required for R7 monoculture telemetry.
    """
    name = model_name or ""
    version = reported_version or ""
    return hashlib.sha256(f"{name}\x00{version}".encode("utf-8")).hexdigest()


def emit_state_wal(
    plan_dir: Path,
    snapshot: Dict[str, Any],
    *,
    taint: str = "trusted",
    schema_version: Optional[int] = None,
    effect: Optional[Any] = None,
) -> dict:
    """Emit a STATE_WRITTEN shadow-WAL event carrying the full post-validation state.

    The full snapshot is recorded under ``state``; ``effect_class`` is the coarse
    literal ``"state_write"``; ``taint`` defaults to ``"trusted"``; ``schema_version``
    is pulled from the snapshot when not explicitly provided.

    ``effect`` is an optional :class:`megaplan.observability.effect_ledger.Effect`
    instance (W11a typed Effect skeleton).  It is stored in the payload under the
    key ``"effect"`` but is NEVER read for control flow in M1 — enforcement is M4.
    """
    if schema_version is None:
        sv = snapshot.get("schema_version", 0) if isinstance(snapshot, dict) else 0
        try:
            schema_version = int(sv)
        except (TypeError, ValueError):
            schema_version = 0
    payload: Dict[str, Any] = {
        "state": snapshot,
        "effect_class": "state_write",
        "taint": taint,
        "schema_version": schema_version,
        "effect": None,
    }
    if effect is not None:
        from megaplan.observability.effect_ledger import Effect
        if isinstance(effect, Effect):
            payload["effect"] = {
                "replay_class": effect.replay_class.value,
                "idempotency_key": effect.idempotency_key,
                "compensation": effect.compensation,
                "provenance": dict(effect.provenance),
                "effect_taint": effect.effect_taint,
            }
    return _get_writer(Path(plan_dir)).emit(EventKind.STATE_WRITTEN, payload=payload)


# ---------------------------------------------------------------------------
# Reader: generator over events.ndjson
# ---------------------------------------------------------------------------

def read_events(
    plan_dir: Path,
    *,
    since_seq: Optional[int] = None,
    kinds: Optional[Sequence[str]] = None,
) -> Generator[dict, None, None]:
    """Yield each event dict from ``plan_dir/events.ndjson``.

    Args:
        plan_dir: Path to the plan directory.
        since_seq: If set, only yield events with ``seq > since_seq``.
        kinds: If set, only yield events whose ``kind`` is in this iterable.

    Yields:
        Parsed event dicts in file order.
    """
    ndjson_path = Path(plan_dir) / _NDJSON_FILE
    if not ndjson_path.exists():
        return

    kind_set: Optional[Set[str]] = set(kinds) if kinds else None

    with open(ndjson_path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError as exc:
                # M4 T10: under UNIFIED_EMIT=1 (or master flag), a journal
                # decode error is a LOUD catalogued failure — silent
                # continue used to swallow corruption.  Flag-off path
                # remains byte-identical (silent skip).
                try:
                    from megaplan._pipeline.flags import unified_emit_on
                    if unified_emit_on():
                        raise RuntimeError(
                            "EVENTS_NDJSON_DECODE_ERROR: "
                            f"plan_dir={plan_dir} line={line!r} err={exc}"
                        ) from exc
                except ImportError:
                    pass
                continue

            # seq filter
            if since_seq is not None:
                seq = event.get("seq")
                if isinstance(seq, int) and seq <= since_seq:
                    continue

            # kind filter
            if kind_set is not None and event.get("kind") not in kind_set:
                continue

            yield event


# ---------------------------------------------------------------------------
# Utility: stream-follow helper
# ---------------------------------------------------------------------------

def _stat_size(path: Path) -> int:
    try:
        return path.stat().st_size
    except FileNotFoundError:
        return 0


def iter_events(
    plan_dir: Path,
    *,
    since_seq: Optional[int] = None,
    kinds: Optional[Sequence[str]] = None,
) -> Iterator[dict]:
    """Iterator (non-generator) wrapper — needed for some consumer patterns."""
    yield from read_events(plan_dir, since_seq=since_seq, kinds=kinds)


# ---------------------------------------------------------------------------
# Subprocess instrumentation context manager
# ---------------------------------------------------------------------------

import contextlib
import os as _os


@contextlib.contextmanager
def spawned(
    plan_dir: Path,
    *,
    role: str = "worker",
    argv_redacted: Optional[list[str]] = None,
    phase: Optional[str] = None,
):
    """Context manager that emits subprocess_spawned / subprocess_exited events.

    Usage::

        with spawned(plan_dir, role="critique_worker", argv_redacted=cmd) as ctx:
            ctx.pid = os.getpid()
            # ... do work ...
    """
    import time as _time

    pid = _os.getpid()
    started = _time.monotonic()
    try:
        emit(
            EventKind.SUBPROCESS_SPAWNED,
            plan_dir=plan_dir,
            phase=phase,
            payload={
                "pid": pid,
                "role": role,
                "argv_redacted": argv_redacted or [],
            },
        )
    except Exception:
        pass

    ctx_obj = type("_SpawnedCtx", (), {"pid": pid})()
    try:
        yield ctx_obj
    finally:
        elapsed = _time.monotonic() - started
        try:
            emit(
                EventKind.SUBPROCESS_EXITED,
                plan_dir=plan_dir,
                phase=phase,
                payload={"pid": pid, "role": role, "returncode": None, "duration_s": elapsed},
            )
        except Exception:
            pass


def live_log_tee(
    plan_dir: Path,
    phase_name: str,
    *,
    stream: str = "stdout",
    text: str = "",
) -> None:
    """Append a line to ``<plan_dir>/<phase>.live.log`` for diagnostic surfaces."""
    if not text:
        return
    try:
        log_path = plan_dir / f"{phase_name}.live.log"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write(f"[{stream}] {text.rstrip()}\n")
    except Exception:
        pass
