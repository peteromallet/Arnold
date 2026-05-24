"""PhaseResult transport — explicit auto↔phase boundary.

Every phase handler writes ``phase_result.json`` atomically at exit;
the auto driver reads *only* that file to decide what to do next.
"""

from __future__ import annotations

import json
import re
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
    external_error = "external_error"


# ---------------------------------------------------------------------------
# Sub-dataclasses that appear inside PhaseResult
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class BlockedTask:
    """A task that could not be executed because its prerequisites are unmet."""

    task_id: str
    reason: str
    notes: str = ""
    blocking_action_ids: tuple[str, ...] = ()
    blocker_kind: str | None = None

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "task_id": self.task_id,
            "reason": self.reason,
            "notes": self.notes,
        }
        if self.blocking_action_ids:
            payload["blocking_action_ids"] = list(self.blocking_action_ids)
        if self.blocker_kind is not None:
            payload["blocker_kind"] = self.blocker_kind
        return payload

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> BlockedTask:
        raw_action_ids = d.get("blocking_action_ids", ())
        if not isinstance(raw_action_ids, (list, tuple)):
            raw_action_ids = ()
        return cls(
            task_id=str(d["task_id"]),
            reason=str(d.get("reason", "")),
            notes=str(d.get("notes", "")),
            blocking_action_ids=tuple(
                item for item in raw_action_ids if isinstance(item, str)
            ),
            blocker_kind=(
                str(d["blocker_kind"]) if d.get("blocker_kind") is not None else None
            ),
        )


@dataclass(frozen=True)
class Deviation:
    """A structured quality-gate deviation."""

    kind: str
    message: str
    task_id: str | None = None
    blocker_id: str | None = None
    phase: str | None = None

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"kind": self.kind, "message": self.message}
        if self.task_id is not None:
            d["task_id"] = self.task_id
        if self.blocker_id is not None:
            d["blocker_id"] = self.blocker_id
        if self.phase is not None:
            d["phase"] = self.phase
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Deviation:
        return cls(
            kind=str(d["kind"]),
            message=str(d["message"]),
            task_id=d.get("task_id"),
            blocker_id=d.get("blocker_id"),
            phase=d.get("phase"),
        )

    @classmethod
    def from_string(cls, raw: str) -> Deviation:
        """Convert a plain deviation string into a typed Deviation.

        The emission helper uses this when worker payloads carry string
        deviations rather than typed objects.
        """
        return cls(kind="quality_gate", message=raw, task_id=None)


@dataclass(frozen=True)
class ExternalError:
    """Structured external dependency failure surfaced at the phase boundary."""

    provider: str
    error_kind: str
    message: str = ""
    status_code: int | None = None
    retry_after_s: float | None = None
    request_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "provider": self.provider,
            "error_kind": self.error_kind,
            "message": self.message,
        }
        if self.status_code is not None:
            payload["status_code"] = self.status_code
        if self.retry_after_s is not None:
            payload["retry_after_s"] = self.retry_after_s
        if self.request_id is not None:
            payload["request_id"] = self.request_id
        return payload

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> ExternalError:
        return cls(
            provider=str(payload.get("provider") or "unknown"),
            error_kind=str(payload["error_kind"]),
            message=str(payload.get("message", "")),
            status_code=(
                int(payload["status_code"])
                if payload.get("status_code") is not None
                else None
            ),
            retry_after_s=(
                float(payload["retry_after_s"])
                if payload.get("retry_after_s") is not None
                else None
            ),
            request_id=(
                str(payload["request_id"])
                if payload.get("request_id") is not None
                else None
            ),
        )

    @classmethod
    def from_exception(
        cls,
        exc: Exception,
        *,
        provider: str = "unknown",
    ) -> ExternalError | None:
        """Classify known provider/API failures without masking internal bugs."""
        extra = getattr(exc, "extra", None)
        if isinstance(extra, dict):
            raw = extra.get("_external_error") or extra.get("external_error")
            if isinstance(raw, dict):
                return cls.from_dict(raw)

        exc_name = type(exc).__name__
        message = str(exc)
        combined = f"{exc_name} {message}".lower()

        status_code = _extract_status_code(exc, message)
        code = getattr(exc, "code", None)
        if code == "worker_stall" or "stalled stream" in combined:
            inferred_provider = provider
            if inferred_provider == "unknown":
                if "claude" in combined:
                    inferred_provider = "claude"
                elif "shannon" in combined:
                    inferred_provider = "shannon"
            return cls(
                provider=inferred_provider,
                error_kind="stalled_stream",
                message=message[:500],
                status_code=status_code,
            )
        error_kind: str | None = None
        if status_code == 429 or re.search(
            r"\b(rate[-_\s]?limit(?:ed)?|too many requests)\b", combined
        ):
            error_kind = "rate_limit"
        elif status_code == 402 or re.search(
            r"\b(payment required|insufficient (?:balance|credits?)|"
            r"balance|quota (?:exceeded|exhausted)|limit exhausted)\b",
            combined,
        ):
            error_kind = "balance"
        elif status_code in (401, 403) or re.search(
            r"\b(unauthori[sz]ed|forbidden|invalid api key|bad api key|"
            r"api key|authentication|permission denied)\b",
            combined,
        ):
            error_kind = "auth"
        elif status_code in (500, 502, 503, 504) or re.search(
            r"\b(server error|internal server|bad gateway|service unavailable|"
            r"gateway timeout)\b",
            combined,
        ):
            error_kind = "provider_failure"
        elif re.search(
            r"\b(timeout|timed out|connection (?:refused|reset|aborted)|"
            r"network|dns|resolve(?:d|r)?|unreachable)\b",
            combined,
        ):
            error_kind = "network"

        if error_kind is None:
            return None

        return cls(
            provider=provider,
            error_kind=error_kind,
            message=message[:500],
            status_code=status_code,
            retry_after_s=_extract_retry_after(combined),
            request_id=_extract_request_id(combined),
        )


def _extract_status_code(exc: Exception, message: str) -> int | None:
    for attr in ("status_code", "status"):
        value = getattr(exc, attr, None)
        if isinstance(value, int) and 100 <= value <= 599:
            return value
    for pattern in (
        r"\bstatus code[:\s]+(\d{3})\b",
        r"\bhttp[:\s]+(\d{3})\b",
        r"\berror code[:\s]+(\d{3})\b",
        r"\b(401|402|403|429|500|502|503|504)\b",
    ):
        match = re.search(pattern, message, re.IGNORECASE)
        if match:
            return int(match.group(1))
    return None


def _extract_retry_after(message: str) -> float | None:
    match = re.search(r"\bretry[-_\s]?after[:=\s]+(\d+(?:\.\d+)?)\b", message)
    if not match:
        return None
    try:
        return float(match.group(1))
    except ValueError:
        return None


def _extract_request_id(message: str) -> str | None:
    for pattern in (
        r"\brequest[-_ ]?id[:=\s]+([a-z0-9_-]+)\b",
        r"\bx-request-id[:=\s]+([a-z0-9_-]+)\b",
    ):
        match = re.search(pattern, message, re.IGNORECASE)
        if match:
            return match.group(1)
    return None


def _classify_external_error(exc: Exception) -> ExternalError | None:
    current: BaseException | None = exc
    seen: set[int] = set()
    while isinstance(current, Exception) and id(current) not in seen:
        seen.add(id(current))
        external_error = ExternalError.from_exception(current)
        if external_error is not None:
            return external_error
        current = current.__cause__ or current.__context__
    return None


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
    external_error: ExternalError | None = None

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
            "external_error": (
                self.external_error.to_dict()
                if self.external_error is not None
                else None
            ),
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
            external_error=(
                ExternalError.from_dict(raw)
                if isinstance((raw := d.get("external_error")), dict)
                else None
            ),
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
    - All required fields are present.
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

    external_error = payload.get("external_error")
    if external_error is not None:
        if not isinstance(external_error, dict):
            raise CliError(
                "parse_error",
                "phase_result.external_error must be an object or null",
            )
        for field_name in ("provider", "error_kind", "message"):
            if not isinstance(external_error.get(field_name), str):
                raise CliError(
                    "parse_error",
                    f"phase_result.external_error.{field_name} must be a string",
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
    external_error: ExternalError | None = None,
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
        log = logging.getLogger("megaplan.orchestration.phase_result")
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
        external_error=external_error,
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
        external_error = None
        if ek == ExitKind.internal_error.value:
            external_error = _classify_external_error(exc)
            if external_error is not None:
                ek = ExitKind.external_error.value

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
                        external_error=external_error,
                    )
                    atomic_write_phase_result(plan_dir, result)
        except Exception:
            # If we can't emit, that's fine — never swallow the original
            pass

        raise
