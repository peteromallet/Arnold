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
from typing import Any, Mapping

PHASE_RESULT_SCHEMA = "megaplan.phase_result"
PHASE_RESULT_SCHEMA_VERSION = 1
PHASE_RESULT_CONTRACT_VERSION = 1


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
    malformed_model_output = "malformed_model_output"
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
    provider_error_code: str | None = None
    error_layer: str | None = None
    source: str | None = None
    stall_timeout_s: float | None = None
    elapsed_s: float | None = None
    content_chunk_count: int | None = None
    reasoning_chunk_count: int | None = None

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
        if self.provider_error_code is not None:
            payload["provider_error_code"] = self.provider_error_code
        if self.error_layer is not None:
            payload["error_layer"] = self.error_layer
        if self.source is not None:
            payload["source"] = self.source
        if self.stall_timeout_s is not None:
            payload["stall_timeout_s"] = self.stall_timeout_s
        if self.elapsed_s is not None:
            payload["elapsed_s"] = self.elapsed_s
        if self.content_chunk_count is not None:
            payload["content_chunk_count"] = self.content_chunk_count
        if self.reasoning_chunk_count is not None:
            payload["reasoning_chunk_count"] = self.reasoning_chunk_count
        return payload

    @classmethod
    def from_dict(cls, payload: dict[str, Any], *, provider: str | None = None) -> ExternalError:
        raw_provider = str(payload.get("provider") or "unknown")
        if raw_provider == "unknown" and provider:
            raw_provider = provider
        return cls(
            provider=raw_provider,
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
            provider_error_code=(
                str(payload["provider_error_code"])
                if payload.get("provider_error_code") is not None
                else None
            ),
            error_layer=(
                str(payload["error_layer"])
                if payload.get("error_layer") is not None
                else None
            ),
            source=(
                str(payload["source"]) if payload.get("source") is not None else None
            ),
            stall_timeout_s=(
                float(payload["stall_timeout_s"])
                if payload.get("stall_timeout_s") is not None
                else None
            ),
            elapsed_s=(
                float(payload["elapsed_s"])
                if payload.get("elapsed_s") is not None
                else None
            ),
            content_chunk_count=(
                int(payload["content_chunk_count"])
                if payload.get("content_chunk_count") is not None
                else None
            ),
            reasoning_chunk_count=(
                int(payload["reasoning_chunk_count"])
                if payload.get("reasoning_chunk_count") is not None
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
        from arnold_pipelines.megaplan.orchestration.phase_result_classify import (
            classify_external_error_payload,
        )

        payload = classify_external_error_payload(exc, provider=provider)
        if payload is None:
            return None
        return cls.from_dict(payload, provider=provider)


def _classify_external_error(exc: Exception) -> ExternalError | None:
    from arnold_pipelines.megaplan.orchestration.phase_result_classify import (
        classify_external_error_chain,
    )

    payload = classify_external_error_chain(exc)
    if payload is None:
        return None
    return ExternalError.from_dict(payload)


def _is_malformed_model_output_error(exc: Exception) -> bool:
    from arnold_pipelines.megaplan.types import CliError

    if not isinstance(exc, CliError):
        return False
    if exc.code not in {"parse_error", "worker_parse_error"}:
        return False
    if exc.extra.get("model_output_parse_error") is not None:
        return bool(exc.extra.get("model_output_parse_error"))
    return "raw_output" in exc.extra


# ---------------------------------------------------------------------------
# PhaseResult — the canonical phase-boundary record
# ---------------------------------------------------------------------------


_PHASE_RESULT_FIELDS = frozenset(
    {
        "schema",
        "schema_version",
        "phase_result_contract_version",
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


def _optional_int(value: Any) -> int:
    if value is None:
        return 0
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


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
    schema: str = PHASE_RESULT_SCHEMA
    schema_version: int = PHASE_RESULT_SCHEMA_VERSION
    phase_result_contract_version: int = PHASE_RESULT_CONTRACT_VERSION

    # ── helpers ─────────────────────────────────────────────────────────

    @property
    def exit_kind_enum(self) -> ExitKind:
        return ExitKind(self.exit_kind)

    # ── serialisation ───────────────────────────────────────────────────

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": PHASE_RESULT_SCHEMA,
            "schema_version": PHASE_RESULT_SCHEMA_VERSION,
            "phase_result_contract_version": PHASE_RESULT_CONTRACT_VERSION,
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
            schema=str(d.get("schema", PHASE_RESULT_SCHEMA)),
            schema_version=_optional_int(d.get("schema_version")),
            phase_result_contract_version=_optional_int(
                d.get("phase_result_contract_version")
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
    from arnold_pipelines.megaplan._core.io import atomic_write_json

    path = plan_dir / PHASE_RESULT_FILENAME
    payload = result.to_dict()
    validate_phase_result_current(payload)
    atomic_write_json(path, payload)


def read_phase_result(plan_dir: Path) -> PhaseResult | None:
    """Read ``phase_result.json`` from *plan_dir*, or return ``None``."""
    path = plan_dir / PHASE_RESULT_FILENAME
    if not path.is_file():
        return None
    from arnold_pipelines.megaplan._core.io import read_json

    raw = read_json(path)
    validate_phase_result(raw)
    return PhaseResult.from_dict(raw)


def is_superseded_recovered_phase_result(
    *,
    phase: str,
    exit_kind: str,
    state: Mapping[str, Any] | None,
) -> bool:
    """Return True when a recover-blocked override supersedes a phase_result.

    Older ``recover-blocked`` recoveries moved ``state.current_state`` back to
    the predecessor phase but left the terminal ``phase_result.json`` in place.
    Reader paths must treat that artifact as historical context once the same
    phase is being resumed.
    """

    if exit_kind == ExitKind.success.value:
        return False
    if not isinstance(state, Mapping):
        return False

    current_state = state.get("current_state")
    if not isinstance(current_state, str) or not current_state:
        return False

    resume_cursor = state.get("resume_cursor")
    if not isinstance(resume_cursor, Mapping):
        return False
    resume_phase = resume_cursor.get("phase")
    if not isinstance(resume_phase, str) or resume_phase != phase:
        return False

    meta = state.get("meta")
    overrides = meta.get("overrides") if isinstance(meta, Mapping) else None
    if not isinstance(overrides, list):
        return False

    for entry in reversed(overrides):
        if not isinstance(entry, Mapping) or entry.get("action") != "recover-blocked":
            continue
        entry_resume = entry.get("resume_cursor")
        if not isinstance(entry_resume, Mapping):
            continue
        entry_phase = entry_resume.get("phase")
        if not isinstance(entry_phase, str) or entry_phase != phase:
            continue
        entry_to_state = entry.get("to_state")
        if isinstance(entry_to_state, str) and entry_to_state and entry_to_state != current_state:
            continue
        return True
    return False


# ---------------------------------------------------------------------------
# Invocation ID
# ---------------------------------------------------------------------------


def generate_invocation_id() -> str:
    """Return a short, unique invocation identifier.

    Uses ``uuid4().hex[:16]`` as specified in the plan — no heavy
    dependency needed.
    """
    return uuid.uuid4().hex[:16]


def _active_phase_name(active: Any) -> str:
    if not isinstance(active, dict):
        return "unknown"
    phase = active.get("phase") or active.get("step")
    return phase if isinstance(phase, str) and phase else "unknown"


# ---------------------------------------------------------------------------
# Structural validation
# ---------------------------------------------------------------------------


def _validate_phase_result_structure(
    payload: dict[str, Any],
    *,
    require_current_schema: bool,
) -> None:
    """Validate the **structure** of a ``PhaseResult`` dict.

    Checks:
    - All required fields are present.
    - Current writes include current schema/version fields.
    - ``exit_kind`` is a recognised enum literal.
    - ``blocked_tasks`` and ``deviations`` have the correct nested shapes.
    - ``phase``, ``invocation_id`` are strings; ``artifacts_written`` is a
      list of strings; ``cli_provenance`` is a dict.
    """
    from arnold_pipelines.megaplan.types import CliError

    if not isinstance(payload, dict):
        raise CliError("parse_error", "phase_result payload must be a dict")

    # --- required fields --------------------------------------------------
    required_fields = set(_PHASE_RESULT_FIELDS)
    if not require_current_schema:
        required_fields -= {"schema", "schema_version", "phase_result_contract_version"}
    missing = sorted(required_fields - set(payload))
    if missing:
        raise CliError(
            "parse_error",
            "phase_result missing required fields: " + ", ".join(missing),
        )

    if require_current_schema:
        if payload.get("schema") != PHASE_RESULT_SCHEMA:
            raise CliError(
                "parse_error",
                f"phase_result.schema must be {PHASE_RESULT_SCHEMA!r}",
            )
        if payload.get("schema_version") != PHASE_RESULT_SCHEMA_VERSION:
            raise CliError(
                "parse_error",
                f"phase_result.schema_version must be {PHASE_RESULT_SCHEMA_VERSION}",
            )
        if payload.get("phase_result_contract_version") != PHASE_RESULT_CONTRACT_VERSION:
            raise CliError(
                "parse_error",
                "phase_result.phase_result_contract_version must be "
                f"{PHASE_RESULT_CONTRACT_VERSION}",
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


def validate_phase_result(payload: dict[str, Any]) -> None:
    """Validate a legacy-readable ``PhaseResult`` dict.

    This read-side validator accepts artifacts emitted before schema/version
    fields existed. Use :func:`validate_phase_result_current` before writing
    current emissions.
    """
    _validate_phase_result_structure(payload, require_current_schema=False)


def validate_phase_result_current(payload: dict[str, Any]) -> None:
    """Validate a current write-side ``PhaseResult`` dict."""
    _validate_phase_result_structure(payload, require_current_schema=True)


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
        log = logging.getLogger("arnold_pipelines.megaplan.orchestration.phase_result")
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

    # Validate against the current schema before writing.
    validate_phase_result_current(result.to_dict())
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

        from arnold_pipelines.megaplan.types import CliError

        # Decide exit_kind based on exception class
        if isinstance(exc, subprocess.TimeoutExpired):
            ek = ExitKind.timeout.value
        elif isinstance(exc, CliError) and exc.extra.get("model_output_parse_error") is True:
            ek = ExitKind.malformed_model_output.value
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
                phase = _active_phase_name(raw.get("active_step"))
                if isinstance(invocation_id, str) and invocation_id and phase != "unknown":
                    result = PhaseResult(
                        phase=phase,
                        invocation_id=invocation_id,
                        exit_kind=ek,
                        external_error=external_error,
                    )
                    validate_phase_result_current(result.to_dict())
                    atomic_write_phase_result(plan_dir, result)
        except Exception:
            # If we can't emit, that's fine — never swallow the original
            pass

        raise


__all__ = [
    "PHASE_RESULT_SCHEMA",
    "PHASE_RESULT_SCHEMA_VERSION",
    "PHASE_RESULT_CONTRACT_VERSION",
    "ExitKind",
    "BlockedTask",
    "Deviation",
    "ExternalError",
    "PhaseResult",
    "PHASE_RESULT_FILENAME",
    "atomic_write_phase_result",
    "read_phase_result",
    "generate_invocation_id",
    "validate_phase_result",
    "validate_phase_result_current",
    "_emit_phase_result",
    "phase_result_guard",
]
