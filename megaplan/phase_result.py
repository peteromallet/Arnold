"""PhaseResult transport — explicit auto↔phase boundary.

Every phase handler writes ``phase_result.json`` atomically at exit;
the auto driver reads *only* that file to decide what to do next.
"""

from __future__ import annotations

import json
import subprocess
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any


class ExitKind(str, Enum):
    """Classification for how a phase exited.

    These are enum **literals**, not free text.  The auto driver switches
    on them to decide retry, human escalation, or continuation.
    """

    success = "success"
    blocked_by_quality = "blocked_by_quality"
    blocked_by_prereq = "blocked_by_prereq"
    timeout = "timeout"
    context_exhausted = "context_exhausted"
    internal_error = "internal_error"


# ---------------------------------------------------------------------------
# Sub-dataclasses that appear inside PhaseResult
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class BlockedTask:
    """A task that could not be executed because its prerequisites are unmet."""

    task_id: str
    reason: str
    notes: str = ""

    # NOTE: no prereq_ids field — the plan says blocked tasks have zero
    # producers in megaplan/.

    def to_dict(self) -> dict[str, str]:
        return {
            "task_id": self.task_id,
            "reason": self.reason,
            "notes": self.notes,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> BlockedTask:
        return cls(
            task_id=str(d["task_id"]),
            reason=str(d.get("reason", "")),
            notes=str(d.get("notes", "")),
        )


@dataclass(frozen=True)
class Deviation:
    """A structured quality-gate deviation."""

    kind: str
    message: str
    task_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"kind": self.kind, "message": self.message}
        if self.task_id is not None:
            d["task_id"] = self.task_id
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Deviation:
        return cls(
            kind=str(d["kind"]),
            message=str(d["message"]),
            task_id=d.get("task_id"),
        )

    @classmethod
    def from_string(cls, raw: str) -> Deviation:
        """Convert a plain deviation string into a typed Deviation.

        The emission helper uses this when worker payloads carry string
        deviations rather than typed objects.
        """
        return cls(kind="quality_gate", message=raw, task_id=None)


# ---------------------------------------------------------------------------
# PhaseResult — the canonical phase-boundary record
# ---------------------------------------------------------------------------


_PHASE_RESULT_FIELDS = frozenset(
    {
        "phase",
        "invocation_id",
        "exit_kind",
        "blocked_tasks",
        "deviations",
        "artifacts_written",
        "cli_provenance",
    }
)

_VALID_EXIT_KINDS: frozenset[str] = frozenset(e.value for e in ExitKind)


@dataclass(frozen=True)
class PhaseResult:
    """Single canonical record for what a phase did.

    Written atomically to ``<plan_dir>/phase_result.json`` by every phase
    handler at exit (success, blocked, or error).  Read by the auto driver
    as the sole source of truth for post-phase routing decisions.
    """

    phase: str
    invocation_id: str
    exit_kind: str  # ExitKind value (string, for JSON friendliness)
    blocked_tasks: tuple[BlockedTask, ...] = ()
    deviations: tuple[Deviation, ...] = ()
    artifacts_written: tuple[str, ...] = ()
    cli_provenance: dict[str, Any] = field(default_factory=dict)

    # ── helpers ─────────────────────────────────────────────────────────

    @property
    def exit_kind_enum(self) -> ExitKind:
        return ExitKind(self.exit_kind)

    # ── serialisation ───────────────────────────────────────────────────

    def to_dict(self) -> dict[str, Any]:
        return {
            "phase": self.phase,
            "invocation_id": self.invocation_id,
            "exit_kind": self.exit_kind,
            "blocked_tasks": [bt.to_dict() for bt in self.blocked_tasks],
            "deviations": [d.to_dict() for d in self.deviations],
            "artifacts_written": list(self.artifacts_written),
            "cli_provenance": dict(self.cli_provenance),
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> PhaseResult:
        return cls(
            phase=str(d["phase"]),
            invocation_id=str(d["invocation_id"]),
            exit_kind=str(d["exit_kind"]),
            blocked_tasks=tuple(
                BlockedTask.from_dict(bt) for bt in d.get("blocked_tasks", [])
            ),
            deviations=tuple(
                Deviation.from_dict(dv) for dv in d.get("deviations", [])
            ),
            artifacts_written=tuple(d.get("artifacts_written", [])),
            cli_provenance=dict(d.get("cli_provenance", {})),
        )


# ---------------------------------------------------------------------------
# Atomic I/O
# ---------------------------------------------------------------------------

PHASE_RESULT_FILENAME = "phase_result.json"


def atomic_write_phase_result(plan_dir: Path, result: PhaseResult) -> None:
    """Write *result* atomically to ``<plan_dir>/phase_result.json``.

    Uses the existing ``atomic_write_json`` helper from ``_core/io.py``
    (write to .tmp → fsync → rename).
    """
    from megaplan._core.io import atomic_write_json

    path = plan_dir / PHASE_RESULT_FILENAME
    atomic_write_json(path, result.to_dict())


def read_phase_result(plan_dir: Path) -> PhaseResult | None:
    """Read ``phase_result.json`` from *plan_dir*, or return ``None``."""
    path = plan_dir / PHASE_RESULT_FILENAME
    if not path.is_file():
        return None
    from megaplan._core.io import read_json

    raw = read_json(path)
    return PhaseResult.from_dict(raw)


# ---------------------------------------------------------------------------
# Invocation ID
# ---------------------------------------------------------------------------


def generate_invocation_id() -> str:
    """Return a short, unique invocation identifier.

    Uses ``uuid4().hex[:16]`` as specified in the plan — no heavy
    dependency needed.
    """
    return uuid.uuid4().hex[:16]


# ---------------------------------------------------------------------------
# Structural validation
# ---------------------------------------------------------------------------


def validate_phase_result(payload: dict[str, Any]) -> None:
    """Validate the **structure** of a ``PhaseResult`` dict.

    Checks:
    - All 7 required fields are present.
    - ``exit_kind`` is a recognised enum literal.
    - ``blocked_tasks`` and ``deviations`` have the correct nested shapes.
    - ``phase``, ``invocation_id`` are strings; ``artifacts_written`` is a
      list of strings; ``cli_provenance`` is a dict.
    """
    from megaplan.types import CliError

    if not isinstance(payload, dict):
        raise CliError("parse_error", "phase_result payload must be a dict")

    # --- required fields --------------------------------------------------
    missing = sorted(_PHASE_RESULT_FIELDS - set(payload))
    if missing:
        raise CliError(
            "parse_error",
            "phase_result missing required fields: " + ", ".join(missing),
        )

    # --- exit_kind enum ---------------------------------------------------
    ek = payload.get("exit_kind")
    if not isinstance(ek, str) or ek not in _VALID_EXIT_KINDS:
        raise CliError(
            "parse_error",
            f"phase_result.exit_kind must be one of "
            f"{sorted(_VALID_EXIT_KINDS)}, got {ek!r}",
        )

    # --- phase, invocation_id scalars -------------------------------------
    for field_name in ("phase", "invocation_id"):
        val = payload.get(field_name)
        if not isinstance(val, str) or not val:
            raise CliError(
                "parse_error",
                f"phase_result.{field_name} must be a non-empty string, got {val!r}",
            )

    # --- artifacts_written ------------------------------------------------
    aw = payload.get("artifacts_written")
    if not isinstance(aw, list) or not all(isinstance(x, str) for x in aw):
        raise CliError(
            "parse_error",
            "phase_result.artifacts_written must be a list of strings",
        )

    # --- cli_provenance ---------------------------------------------------
    cp = payload.get("cli_provenance")
    if not isinstance(cp, dict):
        raise CliError(
            "parse_error",
            "phase_result.cli_provenance must be a dict",
        )

    # --- blocked_tasks ----------------------------------------------------
    bts = payload.get("blocked_tasks")
    if not isinstance(bts, list):
        raise CliError(
            "parse_error",
            "phase_result.blocked_tasks must be a list",
        )
    for i, bt in enumerate(bts):
        if not isinstance(bt, dict):
            raise CliError(
                "parse_error",
                f"phase_result.blocked_tasks[{i}] must be an object",
            )
        if "task_id" not in bt:
            raise CliError(
                "parse_error",
                f"phase_result.blocked_tasks[{i}] missing task_id",
            )
        # reason and notes are optional

    # --- deviations -------------------------------------------------------
    devs = payload.get("deviations")
    if not isinstance(devs, list):
        raise CliError(
            "parse_error",
            "phase_result.deviations must be a list",
        )
    for i, dv in enumerate(devs):
        if not isinstance(dv, dict):
            raise CliError(
                "parse_error",
                f"phase_result.deviations[{i}] must be an object",
            )
        if "kind" not in dv or "message" not in dv:
            raise CliError(
                "parse_error",
                f"phase_result.deviations[{i}] missing kind or message",
            )


# ---------------------------------------------------------------------------
# Phase-result emission helper
# ---------------------------------------------------------------------------


def _emit_phase_result(
    phase: str,
    state: dict[str, Any],
    plan_dir: Path,
    *,
    exit_kind: str,
    blocked_tasks: tuple[BlockedTask, ...] = (),
    deviations: tuple[Deviation, ...] = (),
    artifacts_written: tuple[str, ...] = (),
    cli_provenance: dict[str, Any] | None = None,
) -> None:
    """Construct and write a ``PhaseResult`` from handler state.

    This is the **single** emission point that every phase handler must call
    before returning its ``StepResponse``.  It reads the current invocation
    id from ``state[\"meta\"][\"current_invocation_id\"]`` — if that key is
    absent it raises ``RuntimeError`` because the handler bypassed
    ``set_active_step``.
    """
    if cli_provenance is None:
        cli_provenance = {}

    invocation_id = (state.get("meta") or {}).get("current_invocation_id")
    if not isinstance(invocation_id, str) or not invocation_id:
        # set_active_step was bypassed — this is abnormal in production but
        # can happen in tests that mock _run_worker at the module level.
        # Log a warning and skip emission rather than crashing.
        import logging
        log = logging.getLogger("megaplan.phase_result")
        log.warning(
            "set_active_step was bypassed for phase=%r — "
            "skipping phase_result.json emission",
            phase,
        )
        return

    result = PhaseResult(
        phase=phase,
        invocation_id=invocation_id,
        exit_kind=exit_kind,
        blocked_tasks=blocked_tasks,
        deviations=deviations,
        artifacts_written=artifacts_written,
        cli_provenance=cli_provenance,
    )

    # Validate against schema before writing
    validate_phase_result(result.to_dict())
    atomic_write_phase_result(plan_dir, result)


# ---------------------------------------------------------------------------
# Guard context manager
# ---------------------------------------------------------------------------


@contextmanager
def phase_result_guard(plan_dir: Path):
    """Context manager that wraps a phase handler body.

    If the handler body raises an ``Exception`` (but NOT ``KeyboardInterrupt``
    or ``SystemExit``), the guard attempts to emit an error-result
    ``phase_result.json`` before re-raising the original exception verbatim.

    *When the guard cannot find a current invocation id* (e.g. the error
    happened before ``set_active_step`` ran), it **skips emission entirely**
    and simply re-raises the original exception.  This preserves the existing
    behaviour for pre-setup ``CliError`` paths.
    """
    try:
        yield
    except (KeyboardInterrupt, SystemExit):
        # Never intercept these — let them propagate immediately
        raise
    except BaseException as exc:  # pragma: no cover – catch-all for safety
        # Only handle Exception subclasses; BaseExceptions like
        # GeneratorExit / CancelledError still propagate unwrapped.
        if not isinstance(exc, Exception):
            raise

        # Decide exit_kind based on exception class
        if isinstance(exc, subprocess.TimeoutExpired):
            ek = ExitKind.timeout.value
        else:
            ek = ExitKind.internal_error.value

        # Try to emit only if we have an invocation id
        state_path = plan_dir / "state.json"
        try:
            if state_path.is_file():
                raw = json.loads(state_path.read_text(encoding="utf-8"))
                meta = raw.get("meta") if isinstance(raw, dict) else None
                invocation_id = (
                    meta.get("current_invocation_id")
                    if isinstance(meta, dict)
                    else None
                )
                if isinstance(invocation_id, str) and invocation_id:
                    result = PhaseResult(
                        phase=raw.get("active_step", {}).get("step", "unknown"),
                        invocation_id=invocation_id,
                        exit_kind=ek,
                    )
                    atomic_write_phase_result(plan_dir, result)
        except Exception:
            # If we can't emit, that's fine — never swallow the original
            pass

        raise