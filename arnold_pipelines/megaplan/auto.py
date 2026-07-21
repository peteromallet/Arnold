"""Auto-driver that advances a plan through its workflow-backed phases.

This loop is intentionally operational, not semantic: it reads status,
projects the next actionable target from the planning control surface, validates
that target against the canonical lowered workflow cursor when one is observed,
dispatches it, and repeats until terminal. If a run needs human judgment, the
driver records the lifecycle failure and stops instead of inventing a route.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import logging
import os
import re
import shlex
import signal
import socket
import subprocess
import sys
import tempfile
import threading
import time
import traceback
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Mapping

if TYPE_CHECKING:
    from arnold_pipelines.megaplan.drivers import Substrate

from arnold_pipelines.megaplan._core import (
    active_phase_name,
    find_plan_dir,
    list_batch_artifacts,
)
from arnold_pipelines.megaplan.fallback_chains import select_fallback_spec
from arnold.runtime.envelope import (
    _envelope_ctx,
    write_envelope_in,
)
from arnold_pipelines.megaplan._core.phase_runtime import _pid_alive
from arnold_pipelines.megaplan._core.state import write_plan_state
from arnold_pipelines.megaplan.handlers.shared import _warn_best_effort_emit_failure, _warn_read_fallback
from arnold_pipelines.megaplan.runtime.process import kill_group, spawn
from arnold_pipelines.megaplan.observability.events import (
    EventKind,
    emit as emit_event,
    read_events,
)
from arnold_pipelines.megaplan.orchestration.phase_result import (
    ExitKind,
    PhaseResult,
    read_phase_result,
)
from arnold_pipelines.megaplan.orchestration.authority_readers import (
    AuthorityDecision,
    effective_execute_completed_task_ids,
)
from arnold_pipelines.megaplan.orchestration.recovery_policy import RecoveryPolicy
from arnold_pipelines.megaplan.store import PlanRepository
from arnold_pipelines.megaplan.types import (
    CliError,
)
from arnold_pipelines.megaplan.control_interface import read_valid_targets
from arnold_pipelines.megaplan.custody.admission_control import (
    AUTO_ADMISSION_SURFACE,
    AUTO_ADMISSION_WRITER_ID,
    AdmissionFence,
    register_admission_writers,
    synthetic_text_source_record,
    validate_admission_mutation,
)
from arnold_pipelines.megaplan.workflows.events import (
    resolve_workflow_phase,
    workflow_cursor,
    workflow_dispatch_phase_names,
    workflow_phase_aliases,
)
from arnold.security.redaction import redact_text as redact_security_text
from arnold_pipelines.megaplan.planning.state import (
    AUTOMATION_TERMINAL_STATES,
    STATE_ABORTED,
    STATE_AWAITING_HUMAN,
    STATE_BLOCKED,
    STATE_CANCELLED,
    STATE_CRITIQUED,
    STATE_DONE,
    STATE_EXECUTED,
    STATE_FAILED,
    STATE_FINALIZED,
    STATE_GATED,
    STATE_PAUSED,
    STATE_PREPPED,
    STATE_TIEBREAKER_PENDING,
    STATE_TIEBREAKER_READY,
)


DEFAULT_STALL_THRESHOLD = 5
DEFAULT_MAX_ITERATIONS = 200
DEFAULT_POLL_SLEEP_SECONDS = 1.0
DEFAULT_PHASE_TIMEOUT_SECONDS = 3600
# Backstop for when liveness heartbeats fail to report (e.g. a non-streaming
# worker path, or an undiscovered heartbeat gap). Deliberately generous: a
# false kill of a healthy phase is catastrophic and currently recovers only by
# manual state surgery, whereas over-waiting on a genuinely-dead phase only
# costs wall-clock. Tighten once a stall becomes cheaply recoverable (resume
# the resume_cursor instead of terminal-failing). The accurate per-stream
# heartbeat (workers/hermes.py) is the primary signal; this is the net.
DEFAULT_PHASE_IDLE_TIMEOUT_SECONDS = 1800
DEFAULT_STATUS_TIMEOUT_SECONDS = 60
DEFAULT_MAX_CONTEXT_RETRIES = 2
CONTEXT_EXHAUSTION_FRAGMENT = "ran out of room in the model's context"
DEFAULT_MAX_EXTERNAL_RETRIES = 1
EXTERNAL_RETRYABLE_PHASES = frozenset(
    {"plan", "prep", "critique", "revise", "gate", "finalize", "review"}
)
EXTERNAL_PERMANENT_ERROR_KINDS = frozenset(
    {
        "auth",
        "balance",
        "quota",
        "billing",
        "config",
        "bad_request",
        "invalid_request",
        "unsupported_model",
        "context_exhausted",
        "context_length",
        "rate_limit",
    }
)
EXTERNAL_RETRYABLE_LAYERS = frozenset(
    {
        "stream_content_stall",
        "stream_first_content_timeout",
        "stream_read_timeout",
        "transport_timeout",
        "worker_stream_stall",
    }
)
STALL_PROGRESS_EVENT_KINDS = frozenset(
    {
        EventKind.LLM_CALL_START,
        EventKind.LLM_TOKEN_HEARTBEAT,
        EventKind.LLM_CALL_END,
        EventKind.LLM_CALL_ERROR,
        EventKind.ARTIFACT_WRITTEN,
        EventKind.COST_RECORDED,
        EventKind.TIER_ESCALATED,
    }
)
# When execute exits 0 but state.json's latest execute entry is `result=blocked`,
# the executor reported success-with-evidence-gaps (e.g. done tasks missing
# files_changed/commands_run). Retrying the same execute is structurally pointless
# — the model returned that shape — so we cap retries low and fail fast.
DEFAULT_MAX_BLOCKED_RETRIES = 1
# Cap on review→rework cycles before the driver bails. This mirrors the
# `execution.max_review_rework_cycles` config the review handler enforces
# internally (default 3); the auto-driver applies its own cap so that an
# unexpected-config or mis-routed rework loop cannot spin indefinitely.
DEFAULT_MAX_REVIEW_REWORK_CYCLES = 3
# How many consecutive `override add-note` failures the auto-driver will
# tolerate at a given critique fork before escalating to `override
# force-proceed`. The gate emits `override add-note` first in `valid_next`
# when a critique loop won't converge; without a human, the driver can
# only synthesize a stub note, and if even that fails twice the only
# remaining safe escape valve is force-proceed.
DEFAULT_MAX_ADD_NOTE_ATTEMPTS = 2
# Repeated semantic failure breaker. The normal stall detector intentionally
# treats fresh artifacts/events as progress, but some loops make expensive
# progress while preserving the exact same root failure (for example finalize
# rejecting the same selector contract after every revise). Cap those loops
# low so cloud repair receives a concrete failure instead of waiting for the
# broad max_iterations limit.
DEFAULT_MAX_REPEATED_FAILURE_SIGNATURES = 3
# Control actions that are invalid for the current state are deterministic:
# retrying the same binding cannot make progress and should not spend the
# global max_iterations budget.
DEFAULT_MAX_INVALID_TRANSITION_ATTEMPTS = 2
DEFAULT_MAX_DETERMINISTIC_PHASE_FAILURE_ATTEMPTS = 3
# Auto-ESCALATE-up: after this many consecutive execute failures with no
# forward progress, the driver pins execute to the next *more capable* tier
# model and retries with a fresh session. It keeps climbing on further
# failures until it reaches the ceiling (the most powerful distinct model in
# ``tier_models.execute``); once at the ceiling and still failing, control
# falls through to the existing state-stall ``manual_review`` halt — there is
# nothing stronger left to try. Deliberately small: a model that fails a task
# twice is unlikely to succeed a third time, and a stronger model is the
# cheapest high-leverage lever before giving up. Reaching for a bigger model
# also means a slower run, so the trigger is gated on *failure* (timeout,
# internal_error, blocked) — not on a pure latency stall, which is handled
# separately by stall detection and is not, on its own, evidence the model is
# too weak.
DEFAULT_ESCALATE_AFTER_FAILS = 2
DEFAULT_PHASE_HEARTBEAT_SECONDS = 60.0
ESCALATE_ACTIONS = ("force-proceed", "abort", "fail")
PHASE_TIMEOUT_EXIT_CODE = 124  # conventional; matches GNU `timeout`
PHASE_NAMES = workflow_dispatch_phase_names()
REQUIRES_STATE_RE = re.compile(
    r"requires state ['\"](?P<required>[^'\"]+)['\"], got ['\"](?P<got>[^'\"]+)['\"]"
)

_STABLE_ID_TO_PHASE: dict[str, str] = {
    alias: phase
    for alias, phase in workflow_phase_aliases().items()
    if alias.startswith("megaplan:")
}

_AUTO_CONTROL_TARGETS = frozenset(
    {
        "abort",
        "adopt-execution",
        "feedback",
        "force-proceed",
        "recover-blocked",
        "resume-clarify",
    }
)


def _resolve_phase_name(raw: str) -> str:
    """Return the dispatch phase for *raw* when workflow source defines one."""

    return resolve_workflow_phase(raw) or raw


def _normalize_auto_target_id(raw: str | None) -> str | None:
    if not isinstance(raw, str) or not raw.strip():
        return None
    parts = shlex.split(raw)
    if len(parts) >= 2 and parts[0] == "override":
        return parts[1]
    return _resolve_phase_name(raw.strip())


def _is_auto_supported_target(target_id: str | None) -> bool:
    if not isinstance(target_id, str) or not target_id:
        return False
    return target_id in PHASE_NAMES or target_id in _AUTO_CONTROL_TARGETS


@dataclass
class DriverOutcome:
    """Terminal outcome reported when the loop exits."""

    status: str  # "done" | "paused" | "stalled" | "escalated" | "failed" | "aborted" | "cancelled" | "cap" | "blocked" | "cost_cap_exceeded" | "context_retry_exhausted" | "worker_blocked" | "human_required"
    plan: str
    final_state: str
    iterations: int
    reason: str = ""
    last_phase: str | None = None
    events: list[dict[str, Any]] = field(default_factory=list)
    total_cost_usd: float | None = None
    cost_cap_usd: float | None = None
    context_retries_used: int = 0
    max_context_retries: int | None = None
    external_retries_used: int = 0
    max_external_retries: int | None = None
    blocked_retries_used: int = 0
    max_blocked_retries: int | None = None
    blocking_reasons: list[str] = field(default_factory=list)
    tier_escalations_used: int = 0
    escalation_tier_pin: int | None = None
    publish: dict[str, Any] | None = None

    def to_json(self) -> str:
        return json.dumps(
            {
                "status": self.status,
                "plan": self.plan,
                "final_state": self.final_state,
                "iterations": self.iterations,
                "reason": self.reason,
                "last_phase": self.last_phase,
                "events": self.events,
                "total_cost_usd": self.total_cost_usd,
                "cost_cap_usd": self.cost_cap_usd,
                "context_retries_used": self.context_retries_used,
                "max_context_retries": self.max_context_retries,
                "external_retries_used": self.external_retries_used,
                "max_external_retries": self.max_external_retries,
                "blocked_retries_used": self.blocked_retries_used,
                "max_blocked_retries": self.max_blocked_retries,
                "blocking_reasons": self.blocking_reasons,
                "tier_escalations_used": self.tier_escalations_used,
                "escalation_tier_pin": self.escalation_tier_pin,
                "publish": self.publish,
            },
            indent=2,
        )


NON_RETRYABLE_INFRASTRUCTURE_ERROR_CODES = frozenset(
    {
        "engine_write_isolation_unverified",
    }
)

NON_RETRYABLE_RECOVER_BLOCKED_ERROR_CODES = frozenset(
    {
        "blocked_recovery_not_resolved",
        "external_error_resume_required",
        "rerun_phase_required",
    }
)


def _extract_cli_error_payload(stdout: str, stderr: str) -> dict[str, Any] | None:
    """Return the structured CliError payload emitted by phase subprocesses.

    Handles three output shapes:
    1. Full-stream JSON (entire stdout/stderr is a single JSON object)
    2. Single-line JSON at end of stream (one JSON line per line)
    3. Multi-line pretty-printed JSON preceded by tool logs (e.g. ``[tool] …``,
       ``[done] …``, then a multi-line JSON object) — finds the last complete
       JSON object by scanning balanced ``{…}`` blocks from the end.
    """

    for stream in (stderr, stdout):
        text_stream = (stream or "").strip()
        if not text_stream:
            continue

        # Shape 1: full-stream JSON
        if text_stream.startswith("{"):
            try:
                payload = json.loads(text_stream)
            except json.JSONDecodeError:
                pass
            else:
                if _is_cli_error_payload(payload):
                    return payload

        # Shape 2: single-line JSON (scan lines in reverse)
        for line in reversed((stream or "").splitlines()):
            text = line.strip()
            if not text.startswith("{"):
                continue
            try:
                payload = json.loads(text)
            except json.JSONDecodeError:
                continue
            if _is_cli_error_payload(payload):
                return payload

        # Shape 3: pretty-printed multi-line JSON after tool logs.
        # Find the last balanced {…} block and try to parse it.
        payload = _extract_last_json_object(text_stream)
        if payload is not None and _is_cli_error_payload(payload):
            return payload

    return None


def _filtered_failure_stderr(stderr: str) -> str:
    """Drop non-fatal warning banners that should not mask the real failure."""

    lines = [line.rstrip() for line in (stderr or "").splitlines()]
    kept = [line for line in lines if not line.lstrip().startswith("M_WARN_")]
    return "\n".join(line for line in kept if line.strip()).strip()


def _is_cli_error_payload(payload: Any) -> bool:
    """Return True when *payload* looks like a structured CliError dict."""
    return (
        isinstance(payload, dict)
        and payload.get("success") is False
        and isinstance(payload.get("error"), str)
    )


def _extract_last_json_object(text: str) -> dict[str, Any] | None:
    """Find the last balanced JSON object (``{…}``) in *text*.

    Scans backwards to find a closing ``}``, then walks forward to find the
    matching opening ``{``, and attempts to parse the substring as JSON.
    Returns None when no balanced JSON object is found or parsing fails.
    """
    # Find the last '}' that is not inside a string.
    close = _find_last_unquoted_brace(text, "}")
    if close is None:
        return None
    # Walk backward from close to find the matching '{'.
    depth = 0
    for i in range(close, -1, -1):
        ch = text[i]
        if ch == "}" and not _inside_string(text, i):
            depth += 1
        elif ch == "{" and not _inside_string(text, i):
            depth -= 1
            if depth == 0:
                candidate = text[i:close + 1]
                try:
                    return json.loads(candidate)
                except json.JSONDecodeError:
                    return None
    return None


def _find_last_unquoted_brace(text: str, brace: str) -> int | None:
    """Return the index of the last *brace* that is not inside a JSON string."""
    for i in range(len(text) - 1, -1, -1):
        if text[i] == brace and not _inside_string(text, i):
            return i
    return None


def _inside_string(text: str, pos: int) -> bool:
    """Return True when *pos* is inside a JSON string literal.

    Uses a simple state-machine that counts unescaped ``\"`` characters
    scanning from position 0 up to *pos*.
    """
    in_string = False
    i = 0
    while i < pos:
        ch = text[i]
        if ch == "\\" and in_string:
            i += 2  # skip escaped char
            continue
        if ch == '"':
            in_string = not in_string
        i += 1
    return in_string


def _non_retryable_infrastructure_error_payload(
    stdout: str, stderr: str
) -> dict[str, Any] | None:
    payload = _extract_cli_error_payload(stdout, stderr)
    if payload is None:
        return None
    if payload.get("error") not in NON_RETRYABLE_INFRASTRUCTURE_ERROR_CODES:
        return None
    return payload


def _non_retryable_recover_blocked_error_payload(
    stdout: str, stderr: str
) -> dict[str, Any] | None:
    payload = _extract_cli_error_payload(stdout, stderr)
    if payload is None:
        return None
    if payload.get("error") not in NON_RETRYABLE_RECOVER_BLOCKED_ERROR_CODES:
        return None
    return payload


def _non_negative_int(value: str) -> int:
    try:
        parsed = int(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError(f"invalid non-negative integer: {value}") from error
    if parsed < 0:
        raise argparse.ArgumentTypeError("value must be non-negative")
    return parsed


def _non_negative_float(value: str) -> float:
    try:
        parsed = float(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError(f"invalid non-negative float: {value}") from error
    if parsed < 0:
        raise argparse.ArgumentTypeError("value must be non-negative")
    return parsed


def _is_retryable_external_error(phase: str, external_error: object | None) -> bool:
    """Return True for the narrow provider-failure class auto may retry.

    The policy deliberately targets stream stalls and timeout-shaped transport
    failures on non-execute phases. Auth, billing/quota, bad request, unsupported
    model, context-size, and rate-limit responses stay blocked/resumable because
    repeating them immediately is either unsafe or structurally pointless.
    """
    if phase not in EXTERNAL_RETRYABLE_PHASES:
        return False
    if external_error is None:
        return False

    error_kind = str(getattr(external_error, "error_kind", "") or "").lower()
    status_code = getattr(external_error, "status_code", None)
    retry_after_s = getattr(external_error, "retry_after_s", None)
    provider_error_code = str(
        getattr(external_error, "provider_error_code", "") or ""
    ).lower()
    error_layer = str(getattr(external_error, "error_layer", "") or "").lower()
    message = str(getattr(external_error, "message", "") or "").lower()

    if error_kind in EXTERNAL_PERMANENT_ERROR_KINDS:
        return False
    if retry_after_s is not None:
        return False
    if isinstance(status_code, int) and 400 <= status_code < 500 and status_code != 408:
        return False

    if error_layer in EXTERNAL_RETRYABLE_LAYERS:
        return True
    if error_kind in {"stream_content_stall", "stalled_stream"}:
        return True
    if (
        error_kind == "network"
        and (provider_error_code == "timeout" or "timeout" in message or "timed out" in message)
        and (status_code is None or status_code in {408, 500, 502, 503, 504})
    ):
        return True
    return False


def _apply_envelope_handshake(
    run_kwargs: dict[str, Any], plan_dir: Path | None
) -> None:
    """Symmetric subprocess handshake: write fresh ``.envelope-in.json`` per
    spawn and add a per-process ``MEGAPLAN_ENVELOPE_IN`` env var.

    The child consumes via :func:`consume_envelope_in` which pops the env var
    so grandchildren do not inherit it — every nested spawn must call this
    helper again to get its own fresh sidecar + env override.
    """
    envelope = _envelope_ctx.get()
    if envelope is None or plan_dir is None:
        return
    overrides = write_envelope_in(Path(plan_dir), envelope)
    existing = run_kwargs.get("progress_env") or {}
    merged = dict(existing)
    merged.update(overrides)
    run_kwargs["progress_env"] = merged


@dataclass
class WatcherState:
    """Explicit state for `_supervise_subprocess`, replacing nonlocal closures.

    Captures the timing/byte-buffer state the watcher loop mutates so the
    extracted helper does not need closure variables. Returned to the caller
    so tests can assert on watcher behavior beyond the (exit, out, err) tuple.
    """

    stdout_parts: list[bytes] = field(default_factory=list)
    stderr_parts: list[bytes] = field(default_factory=list)
    last_activity: float = 0.0
    last_hard_progress: float = 0.0
    last_liveness_mtime: float | None = None
    last_heartbeat: float = 0.0
    liveness_changed_since_heartbeat: bool = False
    started: float = 0.0
    timed_out_reason: str | None = None
    kill_monotonic: float | None = None


def _supervise_subprocess(
    proc: Any,
    plan_dir: Path | None,
    idle_cap: float | None,
    wall_cap: float | None,
    *,
    args: list[str] | None = None,
) -> tuple[int, str, str, WatcherState]:
    """Extracted watcher loop (verbatim semantics of auto.py L310-392).

    Drains ``proc.stdout``/``proc.stderr`` on background threads, monitors
    plan-artifact mtime for liveness, emits heartbeats, and applies wall +
    idle timeouts with ``kill_group`` reaping. Returns the final
    ``(exit_code, stdout, stderr, WatcherState)``.
    """

    args = args if args is not None else []
    state = WatcherState()
    state.last_activity = time.monotonic()
    state.last_hard_progress = state.last_activity
    state.last_liveness_mtime = _plan_liveness_mtime(plan_dir)
    heartbeat_interval = _phase_heartbeat_interval_seconds()
    state.last_heartbeat = state.last_activity

    def _reader(stream: Any, parts: list[bytes]) -> None:
        if stream is None:
            return
        while True:
            chunk = stream.read(4096)
            if not chunk:
                break
            parts.append(chunk)
            state.last_activity = time.monotonic()
            state.last_hard_progress = state.last_activity

    threads = [
        threading.Thread(target=_reader, args=(proc.stdout, state.stdout_parts), daemon=True),
        threading.Thread(target=_reader, args=(proc.stderr, state.stderr_parts), daemon=True),
    ]
    for thread in threads:
        thread.start()

    state.started = time.monotonic()
    while proc.poll() is None:
        now = time.monotonic()
        current_liveness_mtime = _plan_liveness_mtime(plan_dir)
        if (
            current_liveness_mtime is not None
            and (
                state.last_liveness_mtime is None
                or current_liveness_mtime > state.last_liveness_mtime
            )
        ):
            state.last_liveness_mtime = current_liveness_mtime
            state.last_activity = now
            state.last_hard_progress = now
            state.liveness_changed_since_heartbeat = True
        if heartbeat_interval is not None and now - state.last_heartbeat >= heartbeat_interval:
            logging.getLogger("megaplan").info(
                "%s",
                _format_phase_heartbeat(
                    args,
                    elapsed_s=now - state.started,
                    plan_dir=plan_dir,
                    progress_changed=state.liveness_changed_since_heartbeat,
                ),
            )
            state.last_heartbeat = now
            state.liveness_changed_since_heartbeat = False
        timeout_base = state.last_hard_progress if idle_cap is not None else state.started
        if wall_cap is not None and now - timeout_base >= wall_cap:
            state.timed_out_reason = f"subprocess timed out after {wall_cap}s"
            break
        if idle_cap is not None and now - state.last_activity >= idle_cap:
            state.timed_out_reason = (
                f"subprocess idle timed out after {idle_cap}s without output"
            )
            break
        time.sleep(0.2)

    if state.timed_out_reason is not None:
        state.kill_monotonic = time.monotonic()
        kill_group(proc, label="megaplan auto idle/timeout")
        for thread in threads:
            thread.join(timeout=1)
        stdout = b"".join(state.stdout_parts).decode("utf-8", errors="replace")
        stderr = b"".join(state.stderr_parts).decode("utf-8", errors="replace")
        marker = f"\n[megaplan auto] {state.timed_out_reason}"
        return PHASE_TIMEOUT_EXIT_CODE, stdout, (stderr + marker).strip(), state

    for thread in threads:
        thread.join(timeout=1)
    stdout = b"".join(state.stdout_parts).decode("utf-8", errors="replace")
    stderr = b"".join(state.stderr_parts).decode("utf-8", errors="replace")
    return int(proc.returncode or 0), stdout, stderr, state


def _run_planning_phase(
    args: list[str],
    *,
    cwd: Path | None = None,
    timeout: float | None = None,
    idle_timeout: float | None = None,
    progress_env: dict[str, str] | None = None,
    liveness_plan_dir: Path | None = None,
) -> tuple[int, str, str]:
    """Run one auto-dispatched command in-process.

    Kept as the test seam replacing the retired subprocess helper. The
    helper name stays legacy for test stability; dispatch now targets the
    canonical ``megaplan`` pipeline identity.
    """

    del timeout, idle_timeout
    if not args:
        return 1, "", "missing command"
    if args[0] == "override":
        return _run_override_command(args, cwd=cwd)
    plan = _plan_arg(args)
    if plan is None:
        return 1, "", "missing --plan"
    native_result = _run_native_planning_phase(
        args,
        plan=plan,
        cwd=cwd,
        progress_env=progress_env,
        liveness_plan_dir=liveness_plan_dir,
    )
    if native_result is not None:
        return native_result
    return _run_planning_phase_compatibility_fallback(
        args,
        plan=plan,
        cwd=cwd,
        progress_env=progress_env,
        liveness_plan_dir=liveness_plan_dir,
    )


class _PhaseDiagnosticText(str):
    """A phase stderr string carrying redacted in-process exception evidence."""

    diagnostic: dict[str, Any] | None

    def __new__(cls, value: str, diagnostic: dict[str, Any] | None = None) -> "_PhaseDiagnosticText":
        instance = super().__new__(cls, value)
        instance.diagnostic = diagnostic
        return instance


def _native_exception_diagnostic(error: Exception) -> dict[str, Any]:
    """Capture bounded, redacted exception evidence at the native phase boundary.

    This deliberately records a UTF-8 representation of the diagnostic, not
    purported provider bytes.  Native in-process exceptions do not expose the
    original stream bytes, and authoritative artifacts remain strictly decoded.
    """
    frames = traceback.extract_tb(error.__traceback__)
    callsite: dict[str, Any] | None = None
    if frames:
        frame = frames[-1]
        callsite = {
            "file": frame.filename,
            "line": frame.lineno,
            "function": frame.name,
        }
    rendered = redact_security_text("".join(traceback.format_exception(error)))
    # The bounded, redacted text is the only material encoded below; never
    # persist raw provider/request bytes from an exception object here.
    rendered = rendered[-16_384:]
    encoded = base64.b64encode(rendered.encode("utf-8", errors="backslashreplace")).decode("ascii")
    return {
        "source": "native_phase_exception",
        "exception_type": type(error).__name__,
        "exception_message": redact_security_text(str(error)),
        "exception_traceback": rendered,
        "exception_callsite": callsite,
        "diagnostic_bytes_b64": encoded,
        "diagnostic_bytes_encoding": "utf-8+base64",
    }


def _phase_diagnostic_metadata(stderr: str) -> dict[str, Any]:
    diagnostic = getattr(stderr, "diagnostic", None)
    return dict(diagnostic) if isinstance(diagnostic, dict) else {}


def _run_native_planning_phase(
    args: list[str],
    *,
    plan: str,
    cwd: Path | None,
    progress_env: dict[str, str] | None,
    liveness_plan_dir: Path | None,
) -> tuple[int, str, str] | None:
    """Run a canonical phase through the compiled shell's native program."""

    raw_phase = args[0] if args else ""
    phase = _resolve_phase_name(raw_phase)
    if phase not in PHASE_NAMES:
        return None
    try:
        from arnold.pipeline.native.ir import NativeProgram
        from arnold_pipelines.megaplan.pipeline import build_and_compile_pipeline

        pipeline = build_and_compile_pipeline()
        native_program = getattr(pipeline, "native_program", None)
        if not isinstance(native_program, NativeProgram):
            return None
        native_phase = next(
            (
                candidate
                for candidate in native_program.phases
                if getattr(candidate, "name", None) == phase
            ),
            None,
        )
        if native_phase is None or not callable(getattr(native_phase, "func", None)):
            return None
        payload = native_phase.func(
            {
                "__megaplan_auto_phase__": True,
                "phase": phase,
                "plan": plan,
                "cwd": cwd,
                "plan_dir": liveness_plan_dir,
                "argv": list(args),
                "progress_env": dict(progress_env or {}),
            }
        )
    except Exception as error:  # noqa: BLE001 - convert to tuple-shaped phase failure.
        diagnostic = _native_exception_diagnostic(error)
        return 1, "", _PhaseDiagnosticText(
            f"{diagnostic['exception_type']}: {diagnostic['exception_message']}",
            diagnostic,
        )

    if not isinstance(payload, dict):
        return 1, "", f"native phase {phase!r} returned {type(payload).__name__}"
    exit_code = payload.get("exit_code")
    stdout = payload.get("stdout")
    stderr = payload.get("stderr")
    if not isinstance(exit_code, int):
        return 1, "", f"native phase {phase!r} did not return exit_code"
    return (
        exit_code,
        stdout if isinstance(stdout, str) else "",
        stderr if isinstance(stderr, str) else "",
    )


def _run_planning_phase_compatibility_fallback(
    args: list[str],
    *,
    plan: str,
    cwd: Path | None,
    progress_env: dict[str, str] | None,
    liveness_plan_dir: Path | None,
) -> tuple[int, str, str]:
    """Explicit compatibility fallback for unsupported native phase dispatch."""

    from arnold.execution.operations import OperationKind, OperationRequest
    from arnold_pipelines.megaplan.registry import (
        dispatch_operation_for,
        phase_tuple_from_operation_result,
    )
    from arnold_pipelines.megaplan.runtime.discovery import CANONICAL_BUILTIN_PIPELINE

    result = dispatch_operation_for(
        CANONICAL_BUILTIN_PIPELINE,
        OperationRequest(
            kind=OperationKind.EXECUTE,
            payload={
                "phase": args[0],
                "plan": plan,
                "cwd": cwd,
                "plan_dir": liveness_plan_dir,
                "argv": list(args),
                "progress_env": dict(progress_env or {}),
            },
        ),
    )
    if not result.ok:
        payload = result.payload if isinstance(result.payload, dict) else {}
        exit_code = payload.get("exit_code")
        stdout = payload.get("stdout")
        stderr = payload.get("stderr")
        return (
            exit_code if isinstance(exit_code, int) and exit_code != 0 else 1,
            stdout if isinstance(stdout, str) else "",
            stderr if isinstance(stderr, str) and stderr else ", ".join(result.errors),
        )
    try:
        return phase_tuple_from_operation_result(result)
    except ValueError as exc:
        return 1, "", str(exc)


def _plan_arg(args: list[str]) -> str | None:
    try:
        index = args.index("--plan")
    except ValueError:
        return None
    if index + 1 >= len(args):
        return None
    return args[index + 1]


def _run_override_command(
    args: list[str],
    *,
    cwd: Path | None = None,
) -> tuple[int, str, str]:
    plan = _plan_arg(args)
    if plan is None:
        return 1, "", "missing --plan"
    action = args[1] if len(args) > 1 else ""
    root = Path(cwd or Path.cwd())
    try:
        from arnold_pipelines.megaplan.cli import load_plan
        from arnold_pipelines.megaplan._core.io import json_dump
        from arnold.execution.operations import OperationKind, OperationRequest
        from arnold_pipelines.megaplan.registry import dispatch_operation_for
        from arnold_pipelines.megaplan.runtime.discovery import CANONICAL_BUILTIN_PIPELINE

        plan_dir, state = load_plan(root, plan)
        namespace = _override_namespace(args, plan=plan)
        if action in {"", "list"}:
            result = dispatch_operation_for(
                CANONICAL_BUILTIN_PIPELINE,
                OperationRequest(
                    kind=OperationKind.OVERRIDE_LIST,
                    payload={"state": dict(state), "root": root, "plan": plan, "plan_dir": plan_dir},
                ),
            )
        else:
            result = dispatch_operation_for(
                CANONICAL_BUILTIN_PIPELINE,
                OperationRequest(
                    kind=OperationKind.OVERRIDE_APPLY,
                    payload={
                        "state": dict(state),
                        "root": root,
                        "plan": plan,
                        "plan_dir": plan_dir,
                        "action": action,
                        "reason": getattr(namespace, "reason", None),
                        "note": getattr(namespace, "note", None),
                        "source": getattr(namespace, "source", None),
                        "params": {
                            key: value
                            for key in (
                                "robustness",
                                "profile",
                                "phase",
                                "model",
                                "vendor",
                                "user_approved",
                                "strict_notes",
                            )
                            if (value := getattr(namespace, key, None)) is not None
                        },
                    },
                ),
            )
        if not result.ok:
            payload = dict(result.payload) if isinstance(result.payload, dict) else {}
            error = payload.get("error")
            message = payload.get("message")
            return (
                1,
                "",
                json.dumps(
                    {
                        "success": False,
                        "error": error if isinstance(error, str) else ",".join(result.errors),
                        "message": message if isinstance(message, str) else ",".join(result.errors),
                    }
                ),
            )
        response = result.payload.get("response") if isinstance(result.payload, dict) else None
        if response is None:
            response = result.payload
        return 0, json_dump(response), ""
    except CliError as error:
        payload: dict[str, Any] = {
            "success": False,
            "error": error.code,
            "message": error.message,
        }
        if error.extra:
            payload["details"] = dict(error.extra)
        return error.exit_code, "", json.dumps(payload)
    except Exception as error:  # noqa: BLE001 - match CLI failure surface.
        return 1, "", f"{type(error).__name__}: {error}"


def _override_namespace(args: list[str], *, plan: str) -> argparse.Namespace:
    action = args[1] if len(args) > 1 else ""
    values: dict[str, Any] = {
        "plan": plan,
        "override_action": action,
        "note": None,
        "reason": "",
        "source": "user",
        "user_approved": False,
        "robustness": None,
        "profile": None,
        "phase": None,
        "model": None,
        "vendor": None,
        "strict_notes": None,
    }
    index = 2
    while index < len(args):
        token = args[index]
        if token in {
            "--plan",
            "--note",
            "--reason",
            "--source",
            "--robustness",
            "--profile",
            "--phase",
            "--model",
            "--vendor",
        } and index + 1 < len(args):
            values[token[2:].replace("-", "_")] = args[index + 1]
            index += 1
        elif token == "--user-approved":
            values["user_approved"] = True
        index += 1
    return argparse.Namespace(**values)


def _override_force_proceed_in_process(
    *,
    root: Path,
    plan: str,
    reason: str,
    user_approved: bool = False,
) -> tuple[int, str, str]:
    args = ["override", "force-proceed", "--plan", plan, "--reason", reason]
    if user_approved:
        args.append("--user-approved")
    return _run_override_command(args, cwd=root)


def _override_abort_in_process(
    *,
    root: Path,
    plan: str,
    reason: str,
) -> tuple[int, str, str]:
    return _run_override_command(
        ["override", "abort", "--plan", plan, "--reason", reason],
        cwd=root,
    )


def _override_adopt_execution_in_process(
    *,
    root: Path,
    plan: str,
    reason: str,
) -> tuple[int, str, str]:
    try:
        from arnold_pipelines.megaplan._core.io import json_dump
        from arnold_pipelines.megaplan.handlers.override import handle_override

        response = handle_override(
            root,
            argparse.Namespace(
                override_action="adopt-execution",
                plan=plan,
                reason=reason,
            ),
        )
        return 0, json_dump(response), ""
    except CliError as error:
        payload: dict[str, Any] = {
            "success": False,
            "error": error.code,
            "message": error.message,
        }
        if error.extra:
            payload["details"] = dict(error.extra)
        return error.exit_code, "", json.dumps(payload)
    except Exception as error:  # noqa: BLE001 - match CLI failure surface.
        return 1, "", f"{type(error).__name__}: {error}"


def _with_project_dir_arg(args: list[str], project_dir: Path) -> list[str]:
    if "--project-dir" in args:
        return list(args)
    if not args:
        return ["--project-dir", str(project_dir)]
    return [args[0], "--project-dir", str(project_dir), *args[1:]]


def _plan_liveness_mtime(plan_dir: Path | None) -> float | None:
    """Return newest plan artifact mtime that proves a quiet phase is alive."""

    if plan_dir is None:
        return None
    # dormant-path: subprocess seam, retired at M6
    candidates = [plan_dir / "state.json"]
    try:
        candidates.extend(list_batch_artifacts(plan_dir))
    except OSError:
        pass
    newest: float | None = None
    for path in candidates:
        try:
            mtime = path.stat().st_mtime
        except OSError:
            continue
        if newest is None or mtime > newest:
            newest = mtime
    return newest


def _phase_heartbeat_interval_seconds() -> float | None:
    raw = os.getenv("MEGAPLAN_AUTO_HEARTBEAT_SECONDS")
    if raw is None:
        return DEFAULT_PHASE_HEARTBEAT_SECONDS
    try:
        value = float(raw)
    except ValueError:
        return DEFAULT_PHASE_HEARTBEAT_SECONDS
    if value <= 0:
        return None
    return value


def _format_phase_heartbeat(
    args: list[str],
    *,
    elapsed_s: float,
    plan_dir: Path | None,
    progress_changed: bool,
) -> str:
    command = "megaplan " + " ".join(args)
    bits = [
        f"[megaplan auto] heartbeat command={command!r}",
        f"elapsed={int(elapsed_s)}s",
        f"progress_mtime_changed={'yes' if progress_changed else 'no'}",
    ]
    # dormant-path: subprocess seam, retired at M6
    state_path = plan_dir / "state.json" if plan_dir is not None else None
    if state_path is not None:
        try:
            raw = json.loads(state_path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            raw = None
        except json.JSONDecodeError:
            _warn_read_fallback(
                "M3A_WARN_HEARTBEAT_STATE_READ",
                path=state_path,
                reason="corrupt_json",
            )
            raw = None
        except (OSError, UnicodeDecodeError):
            _warn_read_fallback(
                "M3A_WARN_HEARTBEAT_STATE_READ",
                path=state_path,
                reason="unreadable",
            )
            raw = None
        if isinstance(raw, dict):
            plan_name = raw.get("name")
            current_state = raw.get("current_state")
            active = raw.get("active_step")
            if isinstance(plan_name, str) and plan_name:
                bits.append(f"plan={plan_name}")
            if isinstance(current_state, str) and current_state:
                bits.append(f"state={current_state}")
            if isinstance(active, dict):
                step = active_phase_name(active)
                agent = active.get("agent")
                mode = active.get("mode")
                worker = "/".join(
                    part for part in (str(agent) if agent else "", str(mode) if mode else "") if part
                )
                if isinstance(step, str) and step:
                    bits.append(f"active_step={step}")
                if worker:
                    bits.append(f"worker={worker}")
    return " ".join(bits)


def _status(
    plan: str,
    cwd: Path | None = None,
    *,
    timeout: float = DEFAULT_STATUS_TIMEOUT_SECONDS,
    progress_env: dict[str, str] | None = None,
) -> dict[str, Any]:
    del timeout, progress_env
    from arnold_pipelines.megaplan.cli.status_view import handle_status

    root = Path(cwd or Path.cwd())
    response = handle_status(root, argparse.Namespace(plan=plan, pending_human=False))
    return dict(response)


def _control_action_label(next_step: str) -> str:
    return _normalize_auto_target_id(next_step) or next_step


def _required_state_for_control_action(next_step: str) -> str | None:
    action = _control_action_label(next_step)
    if action == "resume-clarify":
        return STATE_AWAITING_HUMAN
    if action == "recover-blocked":
        return STATE_BLOCKED
    return None


def _control_action_state_mismatch(
    next_step: str,
    state: str,
) -> dict[str, Any] | None:
    if next_step in PHASE_NAMES:
        return None
    required_state = _required_state_for_control_action(next_step)
    if required_state is None or state == required_state:
        return None
    action = _control_action_label(next_step)
    return {
        "action": action,
        "next_step": next_step,
        "required_state": required_state,
        "actual_state": state,
        "message": f"{action} requires state '{required_state}', got '{state}'",
        "signature": _invalid_transition_signature(
            action=action,
            state=state,
            error="invalid_transition",
            message=f"{action} requires state '{required_state}', got '{state}'",
        ),
    }


def _invalid_transition_signature(
    *,
    action: str,
    state: str,
    error: str,
    message: str,
) -> str:
    raw = json.dumps(
        {
            "action": action,
            "state": state,
            "error": error,
            "message": _normalize_failure_message(message),
        },
        sort_keys=True,
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _control_invalid_transition_failure(
    next_step: str,
    state: str,
    stdout: str,
    stderr: str,
) -> dict[str, Any] | None:
    if next_step in PHASE_NAMES:
        return None
    action = _control_action_label(next_step)
    payload = _extract_cli_error_payload(stdout, stderr)
    combined = f"{stderr}\n{stdout}".strip()
    error = (
        str(payload.get("error") or "")
        if isinstance(payload, dict)
        else ("invalid_transition" if "invalid_transition" in combined else "")
    )
    message = (
        str(payload.get("message") or "")
        if isinstance(payload, dict)
        else (_filtered_failure_stderr(stderr) or stdout.strip()[-400:])
    ).strip()
    requires_match = REQUIRES_STATE_RE.search(message)
    if error != "invalid_transition" and requires_match is None:
        return None
    required_state = requires_match.group("required") if requires_match else None
    actual_state = requires_match.group("got") if requires_match else state
    if not message:
        message = f"{action} returned invalid_transition"
    return {
        "action": action,
        "next_step": next_step,
        "error": error or "invalid_transition",
        "message": message,
        "required_state": required_state,
        "actual_state": actual_state,
        "requires_state_mismatch": bool(
            required_state is not None and actual_state != required_state
        ),
        "signature": _invalid_transition_signature(
            action=action,
            state=actual_state or state,
            error=error or "invalid_transition",
            message=message,
        ),
        "cli_error": payload if isinstance(payload, dict) else None,
    }


def _command_for_auto_target(next_step: str) -> list[str]:
    target = _control_action_label(next_step)
    if target == "execute":
        # --retry-blocked-tasks is safe to pass on every iteration. Within a
        # single auto session, tasks that report status=blocked terminate the
        # auto loop via STATE_AWAITING_HUMAN_VERIFY (see eb4ac447), so re-dispatch
        # only happens on a *fresh* `megaplan auto` invocation — which is the
        # user's signal that any external prereq has been resolved and stale
        # blocked statuses should be retried instead of short-circuiting.
        # If there are no blocked tasks, the flag is a no-op.
        return [
            "execute",
            "--confirm-destructive",
            "--user-approved",
            "--retry-blocked-tasks",
        ]
    if target == "feedback":
        # The auto driver must dispatch the *workflow* operation, not the
        # default "edit" operation — otherwise the handler would open $EDITOR
        # and block on human input.  "feedback workflow" scaffolds the file
        # non-interactively and transitions reviewed → done.
        return ["feedback", "workflow"]
    if target == "recover-blocked":
        return [
            "override",
            "recover-blocked",
            "--reason",
            "megaplan auto: recover blocked plan after blocker resolution",
        ]
    if target == "resume-clarify":
        return ["override", "resume-clarify"]
    if target == "force-proceed":
        return [
            "override",
            "force-proceed",
            "--reason",
            "megaplan auto: dispatch declared override target",
        ]
    if target == "abort":
        return [
            "override",
            "abort",
            "--reason",
            "megaplan auto: dispatch declared override target",
        ]
    if target == "adopt-execution":
        return [
            "override",
            "adopt-execution",
            "--reason",
            "megaplan auto: adopt complete execution artifact after worker failure",
        ]
    return [target]


def _phase_command(
    next_step: str,
    substrate: "Substrate" = "subprocess_isolated",
) -> list[str]:
    """Preserve the legacy phase-command contract for external callers.

    Command selection is owned by :func:`_command_for_auto_target`. Explicit
    multi-token override commands retain their historical argv shape so
    compatibility callers can continue to pass them through unchanged.
    ``substrate`` is accepted for forward compatibility; both supported
    substrates currently use the same command translation.
    """

    del substrate
    parts = shlex.split(next_step)
    if len(parts) >= 2 and parts[0] == "override":
        return parts
    return _command_for_auto_target(next_step)


def _failure_resume_cursor_for_step(
    next_step: str,
    *,
    plan_dir: Path | None,
) -> dict[str, str]:
    """Return the cursor to persist when an auto-dispatched command fails.

    Recovery helper commands are not resumable phases themselves. If
    ``recover-blocked`` fails, preserving the original blocked phase cursor lets
    the operator or a later auto iteration recover the work that actually
    blocked instead of wedging on ``phase='recover-blocked'``.
    """

    if next_step == "recover-blocked" and plan_dir is not None:
        try:
            # dormant-path: subprocess seam, retired at M6
            state_payload = json.loads((plan_dir / "state.json").read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, UnicodeDecodeError, ValueError):
            state_payload = {}
        if isinstance(state_payload, dict):
            cursor = state_payload.get("resume_cursor")
            if isinstance(cursor, dict):
                phase = cursor.get("phase")
                if isinstance(phase, str) and phase and phase != "recover-blocked":
                    return dict(cursor)
    return {"phase": next_step, "retry_strategy": "rerun_phase"}


def _resolve_plan_dir(plan: str, cwd: Path | None) -> Path | None:
    """Best-effort resolution of legacy or canonical orphan plan roots near ``cwd``."""
    return find_plan_dir(cwd or Path.cwd(), plan)





def _latest_versioned_artifact(plan_dir: Path | None, prefix: str) -> Path | None:
    """Return the highest-numbered versioned artifact (``<prefix>v<N>.json``)."""
    if plan_dir is None:
        return None
    try:
        candidates = [
            p for p in plan_dir.iterdir()
            if p.name.startswith(prefix) and p.suffix == ".json"
        ]
    except OSError:
        return None
    if not candidates:
        return None

    def _version(path: Path) -> int:
        stem = path.stem  # drop .json
        try:
            return int(stem.split("v")[-1])
        except (ValueError, IndexError):
            return -1

    candidates.sort(key=_version)
    return candidates[-1] if candidates else None


def _read_unresolved_flag_ids(plan_dir: Path | None) -> list[str]:
    """Best-effort list of unresolved flag IDs from the latest gate signals.

    Falls back to the latest critique artifact if no gate_signals_v*.json
    exists yet (e.g. ESCALATE arrived from a non-gate path). Returns ``[]``
    on any read/parse error — callers must treat that as "no flags known"
    and synthesize a generic note rather than crashing.
    """
    sources = [
        _latest_versioned_artifact(plan_dir, "gate_signals_v"),
        _latest_versioned_artifact(plan_dir, "critique_v"),
    ]
    for path in sources:
        if path is None:
            continue
        try:
            with path.open(encoding="utf-8") as handle:
                payload = json.load(handle)
        except FileNotFoundError:
            continue
        except json.JSONDecodeError:
            _warn_read_fallback(
                "M3A_WARN_AUTO_FLAGS_READ",
                path=path,
                reason="corrupt_json",
            )
            continue
        except (OSError, UnicodeDecodeError):
            _warn_read_fallback(
                "M3A_WARN_AUTO_FLAGS_READ",
                path=path,
                reason="unreadable",
            )
            continue
        if not isinstance(payload, dict):
            continue
        # gate_signals_v*.json uses key "unresolved_flags"; critique_v*.json
        # uses "flags". Either may be missing on truncated artifacts.
        for key in ("unresolved_flags", "flags"):
            flags = payload.get(key)
            if isinstance(flags, list) and flags:
                ids = [
                    str(f.get("id"))
                    for f in flags
                    if isinstance(f, dict) and isinstance(f.get("id"), str) and f.get("id")
                ]
                if ids:
                    return ids
    return []


def _synthesize_add_note_text(
    plan_dir: Path | None,
    *,
    iteration: int,
    attempt: int,
) -> str:
    """Build a non-empty `--note` string for an unattended add-note dispatch.

    The orchestrator only reaches `override add-note` when the
    critique→revise→gate loop has failed to converge and the gate has
    punted to a human. Without a human, the auto-driver records why it
    is advancing anyway: the unresolved flag IDs (if readable) and the
    iteration/attempt counters so audits can spot loops.
    """
    flag_ids = _read_unresolved_flag_ids(plan_dir)
    if flag_ids:
        # Cap the inline list — strict-notes mode rejects giant blobs.
        head = ", ".join(flag_ids[:10])
        suffix = f" (+{len(flag_ids) - 10} more)" if len(flag_ids) > 10 else ""
        flags_part = f"; unresolved=[{head}{suffix}]"
    else:
        flags_part = "; unresolved=[unknown]"
    return (
        f"auto: critique loop unresolved at iter {iteration} "
        f"(add-note attempt {attempt}){flags_part}; advancing without human"
    )


def _build_override_add_note_command(
    plan: str,
    plan_dir: Path | None,
    *,
    iteration: int,
    attempt: int,
) -> list[str]:
    """Construct the full argv for ``megaplan override add-note ...``.

    Matches the CLI contract enforced by ``cli.py::_validate_override_args``:
    requires both ``--plan`` and a non-empty ``--note``. Without ``--note``
    the subcommand fails with ``invalid_args`` and the auto-driver retries
    the same broken call until stall detection kills the run.
    """
    note = _synthesize_add_note_text(plan_dir, iteration=iteration, attempt=attempt)
    return ["override", "add-note", "--plan", plan, "--note", note]


def _sum_history_cost_usd(plan_dir: Path | None) -> float:
    if plan_dir is None:
        return 0.0

    try:
        # dormant-path: subprocess seam, retired at M6
        with (plan_dir / "state.json").open(encoding="utf-8") as handle:
            state_data = json.load(handle)
    except FileNotFoundError:
        return 0.0
    except json.JSONDecodeError:
        _warn_read_fallback(
            "M3A_WARN_HISTORY_COST_READ",
            path=plan_dir / "state.json",
            reason="corrupt_json",
        )
        return 0.0
    except (OSError, UnicodeDecodeError):
        _warn_read_fallback(
            "M3A_WARN_HISTORY_COST_READ",
            path=plan_dir / "state.json",
            reason="unreadable",
        )
        return 0.0

    if not isinstance(state_data, dict):
        return 0.0

    total = 0.0
    for entry in state_data.get("history") or []:
        if not isinstance(entry, dict):
            continue
        try:
            total += float(entry.get("cost_usd", 0.0) or 0.0)
        except (TypeError, ValueError):
            _warn_read_fallback(
                "M3A_WARN_COST_COERCION",
                path=plan_dir / "state.json",
                reason="invalid_cost",
                context={"entry": entry},
            )
            continue
    return round(total, 6)


def _read_state_data(plan_dir: Path | None) -> dict[str, Any] | None:
    """Best-effort read of ``state.json`` as a dict (None on any failure)."""
    if plan_dir is None:
        return None
    try:
        from arnold_pipelines.megaplan._core.state import load_plan_from_dir

        _, data = load_plan_from_dir(plan_dir)
    except FileNotFoundError:
        return None
    except (CliError, json.JSONDecodeError, OSError, UnicodeDecodeError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def _admit_auto_driver(plan_dir: Path | None, plan: str) -> dict[str, Any] | None:
    """Fail closed before auto mutates a stale or mismatched plan."""

    state_data = _read_state_data(plan_dir)
    if plan_dir is None or state_data is None:
        return None

    register_admission_writers()
    source_record = synthetic_text_source_record(
        selector=plan,
        label="auto-state",
        text=json.dumps(state_data, sort_keys=True, separators=(",", ":")),
    )
    fences = [
        AdmissionFence(
            identity="plan_name",
            expected=plan,
            observed=state_data.get("name"),
            satisfied=str(state_data.get("name") or "") == plan,
            detail="auto must mutate the exact requested plan",
        )
    ]

    binding = (state_data.get("meta") or {}).get("canonical_source_binding")
    if isinstance(binding, Mapping):
        from arnold_pipelines.megaplan.planning.source_binding import assert_canonical_source_current

        report = assert_canonical_source_current(plan_dir, state_data, operation="auto")
        current = report.get("current")
        bound = report.get("bound")
        if isinstance(current, Mapping):
            source_record = dict(current)
        elif isinstance(bound, Mapping):
            source_record = dict(bound)
        fences.append(
            AdmissionFence(
                identity="canonical_source_status",
                expected="match",
                observed=report.get("status"),
                satisfied=report.get("status") == "match",
                detail="auto requires the bound canonical source to remain current",
            )
        )

    return validate_admission_mutation(
        writer_id=AUTO_ADMISSION_WRITER_ID,
        surface_name=AUTO_ADMISSION_SURFACE,
        selector=plan,
        source_record=source_record,
        fences=tuple(fences),
        extra={"plan_dir": str(plan_dir)},
    )


def _normalize_failure_message(value: object) -> str:
    text = str(value or "").strip()
    text = re.sub(r"\s+", " ", text)
    return text[:500]


def _latest_meaningful_history_failure(
    state_data: dict[str, Any] | None,
) -> dict[str, Any] | None:
    if not isinstance(state_data, dict):
        return None
    history = state_data.get("history")
    if not isinstance(history, list):
        return None
    for entry in reversed(history):
        if not isinstance(entry, dict):
            continue
        result = str(entry.get("result") or "").strip().lower()
        message = _normalize_failure_message(entry.get("message"))
        if result in {"error", "failed", "failure", "blocked"} or message:
            return entry
    return None


def _repeated_failure_signature(
    plan_dir: Path | None,
    status: dict[str, Any],
) -> dict[str, Any] | None:
    """Return a semantic failure signature worth circuit-breaking.

    The breaker is intentionally narrow: it only watches loops that are about
    to spend another revise turn responding to the same latest failure. Normal
    execute/review progress and ordinary state repeats stay governed by the
    existing stall/rework detectors.
    """

    if status.get("next_step") != "revise":
        return None
    state_data = _read_state_data(plan_dir)
    failure = _latest_meaningful_history_failure(state_data)
    if not failure:
        return None
    step = str(failure.get("step") or "").strip()
    result = str(failure.get("result") or "").strip()
    message = _normalize_failure_message(failure.get("message"))
    if not message:
        return None
    raw = json.dumps(
        {
            "state": status.get("state"),
            "next_step": status.get("next_step"),
            "step": step,
            "result": result,
            "message": message,
        },
        sort_keys=True,
    )
    return {
        "hash": hashlib.sha256(raw.encode("utf-8")).hexdigest(),
        "step": step,
        "result": result,
        "message": message,
    }


def _auto_verify_deferred_must_criteria(plan_dir: Path | None, *, log) -> bool:
    """Auto-record pass verdicts for all deferred-must criteria on an
    auto-approve run, transitioning the plan to ``done``.

    Returns True when the plan was advanced (caller should ``continue`` the
    automation loop), False when it must fall through to the human halt
    (auto-approve not set, or anything unexpected — fail safe by stopping).

    Honesty contract: a plan only enters ``awaiting_human_verify`` after the
    review phase APPROVED, and review gates on the plan's own tests. So an
    auto-approve operator delegating sign-off to the harness is verified
    against that review, not rubber-stamped blind — if review had not approved,
    the plan would be in rework, not here.
    """
    if plan_dir is None:
        return False
    state_data = _read_state_data(plan_dir)
    if state_data is None:
        return False
    config = state_data.get("config")
    if not isinstance(config, dict) or not config.get("auto_approve"):
        return False
    try:
        from arnold_pipelines.megaplan._core.state import latest_plan_meta_path, save_state_merge_meta
        from arnold_pipelines.megaplan._core.io import atomic_write_json, read_json as _read_json
        from arnold_pipelines.megaplan.audits.capabilities import get_worker_capabilities
        from arnold_pipelines.megaplan.handlers.verifiability import get_human_verification_status
        from arnold_pipelines.megaplan.orchestration.verifiability import classify_criteria

        plan_meta = _read_json(latest_plan_meta_path(plan_dir, state_data))
        success_criteria = plan_meta.get("success_criteria", []) or []
        worker_caps = get_worker_capabilities(state_data)
        _, human_deferred = classify_criteria(success_criteria, worker_caps)
        # Under auto_approve the operator delegates sign-off to the harness for
        # ALL human-deferred criteria, not just must-priority ones. A plan that
        # entered ``awaiting_human_verify`` solely on deferred *should* criteria
        # (its must criteria all auto-verifiable) would otherwise halt forever:
        # auto-verify found no deferred-MUST, bailed, and the driver stopped for
        # a human who, under auto_approve, has already delegated sign-off. Record
        # verdicts for every deferred criterion (must + should) so should-only
        # plans advance too.
        deferred = [
            (i, sc) for i, sc in enumerate(success_criteria)
            if sc in human_deferred
        ]
        if not deferred:
            return False

        verifications_path = plan_dir / "human_verifications.json"
        verifications: list[dict[str, Any]] = []
        if verifications_path.exists():
            loaded = _read_json(verifications_path)
            if isinstance(loaded, list):
                verifications = loaded
        stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        for idx, sc in deferred:
            verifications.append({
                "criterion_idx": idx,
                "criterion": sc.get("criterion", ""),
                "verdict": "pass",
                "evidence": (
                    "auto-approved by chain driver: review phase approved "
                    "(review gates on the plan's tests) and auto_approve is set."
                ),
                "timestamp": stamp,
            })
        atomic_write_json(verifications_path, verifications)

        hv_status = get_human_verification_status(
            plan_dir, plan_meta, worker_caps=worker_caps
        )
        if not hv_status.get("all_deferred_must_verified"):
            log("auto-verify recorded verdicts but criteria still pending — stopping for human")
            return False
        state_data["current_state"] = STATE_DONE
        save_state_merge_meta(plan_dir, state_data)
        log(f"auto-verified {len(deferred)} deferred criteria (must+should) → done")
        return True
    except Exception as exc:  # fail safe: any error → human halt, never a false done
        log(f"auto-verify failed ({exc!r}) — falling through to human halt")
        return False


def _read_execute_tier_ladder(plan_dir: Path | None) -> dict[int, str]:
    """Return ``{tier_number: spec_string}`` for ``tier_models.execute``.

    Read from the plan's persisted ``state.json`` config (written by init when
    a tier-routed profile is active). Returns an empty dict when the run is not
    tier-routed (flat execute pin / no tiers) — the escalate path treats that
    as "nothing to escalate to" and no-ops gracefully.
    """
    state_data = _read_state_data(plan_dir)
    if state_data is None:
        return {}
    config = state_data.get("config")
    if not isinstance(config, dict):
        return {}
    tier_models = config.get("tier_models")
    if not isinstance(tier_models, dict):
        return {}
    execute_tiers = tier_models.get("execute")
    if not isinstance(execute_tiers, dict) or not execute_tiers:
        return {}
    max_execute_tier = config.get("max_execute_tier")
    if not isinstance(max_execute_tier, int) or not 1 <= max_execute_tier <= 10:
        max_execute_tier = None
    ladder: dict[int, str] = {}
    for raw_tier, spec in execute_tiers.items():
        try:
            tier_num = int(raw_tier)
        except (TypeError, ValueError):
            continue
        if max_execute_tier is not None and tier_num > max_execute_tier:
            continue
        if isinstance(spec, str) and spec.strip():
            ladder[tier_num] = spec
            continue
        if isinstance(spec, list):
            ladder[tier_num] = select_fallback_spec(
                spec,
                0,
                path=f"tier_models.execute.{tier_num}",
            )
    return ladder


def _latest_execute_max_tier(plan_dir: Path | None) -> int | None:
    """Highest ``batch_complexity`` tier the most recent execute phase routed.

    The execute aggregate history entry records ``batch_to_tier`` — one entry
    per batch with the complexity-derived tier. The highest such tier is the
    most capable model the failing execute actually used, and therefore the
    correct baseline to escalate *above*. Returns None when no tier-routed
    execute entry is found (caller falls back to climbing from the bottom).
    """
    state_data = _read_state_data(plan_dir)
    if state_data is None:
        return None
    history = state_data.get("history")
    if not isinstance(history, list):
        return None
    for entry in reversed(history):
        if not isinstance(entry, dict) or entry.get("step") != "execute":
            continue
        batch_to_tier = entry.get("batch_to_tier")
        if not isinstance(batch_to_tier, list) or not batch_to_tier:
            return None
        tiers = [
            int(b["batch_complexity"])
            for b in batch_to_tier
            if isinstance(b, dict)
            and isinstance(b.get("batch_complexity"), int)
        ]
        return max(tiers) if tiers else None
    return None


def _next_escalation_tier(
    ladder: dict[int, str],
    *,
    current_tier: int | None,
) -> tuple[int, str] | None:
    """Pick the next tier whose spec is a *distinct* model above ``current_tier``.

    "Escalate up" means moving toward the highest (most capable) tier number.
    Tiers whose spec string equals the current tier's spec are skipped — they
    are the *same* model (e.g. premium tiers 4 and 5 are both Opus), so
    escalating onto them would waste an escalation as a no-op. Returns
    ``(tier_number, spec)`` for the next distinct-model tier above
    ``current_tier``, or None when the ceiling is already reached / there is no
    more-capable distinct model left (caller then defers to manual_review).
    """
    if not ladder:
        return None
    sorted_tiers = sorted(ladder)
    ceiling = sorted_tiers[-1]
    # Baseline: the tier we are escalating *above*. When unknown, treat the
    # bottom of the ladder as the baseline so the first escalation climbs to
    # the next distinct model up from the weakest tier.
    if current_tier is None:
        current_tier = sorted_tiers[0]
    if current_tier >= ceiling:
        return None
    current_spec = ladder.get(current_tier)
    for tier in sorted_tiers:
        if tier <= current_tier:
            continue
        spec = ladder[tier]
        # Skip same-model steps (no-op escalation) — keep climbing until a
        # genuinely more capable distinct model appears.
        if current_spec is not None and spec == current_spec:
            continue
        return tier, spec
    return None


def _read_finalize_data(plan_dir: Path | None) -> dict[str, Any] | None:
    if plan_dir is None:
        return None
    try:
        with (plan_dir / "finalize.json").open(encoding="utf-8") as handle:
            data = json.load(handle)
    except (FileNotFoundError, OSError, json.JSONDecodeError, UnicodeDecodeError):
        return None
    return data if isinstance(data, dict) else None


def _write_json_atomic(path: Path, data: dict[str, Any]) -> None:
    tmp = path.with_name(f".{path.name}.tmp")
    tmp.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


def _pin_tasks_to_tier(
    plan_dir: Path | None,
    task_ids: list[str],
    new_tier: int,
) -> list[str]:
    """Pin every task in *task_ids* to at least *new_tier* in ``finalize.json``."""
    data = _read_finalize_data(plan_dir)
    if data is None:
        return []
    tasks = data.get("tasks")
    if not isinstance(tasks, list):
        return []
    wanted = set(task_ids)
    mutated: list[str] = []
    for task in tasks:
        if not isinstance(task, dict):
            continue
        task_id = task.get("id")
        if not isinstance(task_id, str) or task_id not in wanted:
            continue
        existing = task.get("tier_override")
        task["tier_override"] = max(existing, new_tier) if isinstance(existing, int) else new_tier
        mutated.append(task_id)
    if mutated and plan_dir is not None:
        try:
            _write_json_atomic(plan_dir / "finalize.json", data)
        except OSError:
            logging.getLogger("megaplan").warning(
                "_pin_tasks_to_tier: failed writing finalize.json", exc_info=True
            )
            return []
    return mutated


def _current_task_override(plan_dir: Path | None, task_id: str) -> int | None:
    data = _read_finalize_data(plan_dir)
    if data is None:
        return None
    tasks = data.get("tasks")
    if not isinstance(tasks, list):
        return None
    for task in tasks:
        if isinstance(task, dict) and task.get("id") == task_id:
            override = task.get("tier_override")
            if isinstance(override, int) and 1 <= override <= 10:
                return override
            return None
    return None


def _get_review_marker(plan_dir: Path | None) -> float | None:
    """Return a monotonically-advancing marker for the current review cycle.

    Uses ``review.json`` mtime — each completed review phase rewrites the
    file, so the mtime bumps once per review cycle. This is race-free
    enough for stall detection: the driver only checks the marker between
    iterations, and mtime granularity (~1s on APFS/ext4) is finer than the
    minimum review runtime.

    Returns ``None`` when no marker is available (plan dir missing, review
    not yet run, or stat failed) — the caller must treat ``None == None``
    as "no progress observed" and fall through to plain stall detection.
    """
    if plan_dir is None:
        return None
    review_path = plan_dir / "review.json"
    try:
        return review_path.stat().st_mtime
    except (OSError, FileNotFoundError):
        return None


def _issue_signature(item: dict[str, Any]) -> str:
    flag_id = item.get("flag_id")
    if isinstance(flag_id, str) and flag_id.strip():
        return f"flag:{flag_id.strip()}"
    issue = item.get("issue")
    text = re.sub(r"\s+", " ", (issue or "").strip().lower())
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]
    return f"issue:{digest}"


def _review_rework_signatures_by_task(review_data: dict[str, Any]) -> dict[str, set[str]]:
    if review_data.get("review_verdict") != "needs_rework":
        return {}
    result: dict[str, set[str]] = {}
    for item in review_data.get("rework_items", []) or []:
        if not isinstance(item, dict):
            continue
        task_id = item.get("task_id")
        if not isinstance(task_id, str) or not task_id or task_id.startswith("REVIEW"):
            continue
        result.setdefault(task_id, set()).add(_issue_signature(item))
    return result


def _load_review_rework_signatures(plan_dir: Path | None) -> dict[str, set[str]]:
    if plan_dir is None:
        return {}
    try:
        with (plan_dir / "review.json").open(encoding="utf-8") as handle:
            review_data = json.load(handle)
    except (FileNotFoundError, OSError, json.JSONDecodeError, UnicodeDecodeError):
        return {}
    if not isinstance(review_data, dict):
        return {}
    return _review_rework_signatures_by_task(review_data)


def _nonconverging_rework_tasks(
    *,
    previous: dict[str, set[str]],
    current: dict[str, set[str]],
    streaks: dict[str, int],
) -> list[str]:
    nonconverging: list[str] = []
    for task_id, current_signatures in current.items():
        prior_signatures = previous.get(task_id, set())
        if not prior_signatures:
            streaks[task_id] = 1
            continue
        if current_signatures < prior_signatures:
            streaks[task_id] = 1
            continue
        if prior_signatures & current_signatures:
            streaks[task_id] = streaks.get(task_id, 1) + 1
        else:
            streaks[task_id] = 1
        if streaks[task_id] >= 2:
            nonconverging.append(task_id)
    for task_id in set(streaks) - set(current):
        streaks.pop(task_id, None)
    return sorted(nonconverging)


def _task_complexity(plan_dir: Path | None, task_id: str) -> int | None:
    data = _read_finalize_data(plan_dir)
    if data is None:
        return None
    for task in data.get("tasks", []) or []:
        if not isinstance(task, dict) or task.get("id") != task_id:
            continue
        complexity = task.get("complexity")
        if isinstance(complexity, int) and 1 <= complexity <= 10:
            return complexity
    return None


def _review_nonconvergence_escalation_plan(
    *,
    plan_dir: Path | None,
    task_id: str,
    ladder: dict[int, str],
) -> tuple[int | None, tuple[int, str] | None]:
    baseline = _current_task_override(plan_dir, task_id)
    observed_tier = _latest_execute_max_tier(plan_dir)
    task_complexity = _task_complexity(plan_dir, task_id)
    for candidate in (observed_tier, task_complexity):
        if candidate is None:
            continue
        baseline = max(baseline, candidate) if baseline is not None else candidate
    return baseline, _next_escalation_tier(ladder, current_tier=baseline)


def _latest_artifact_name(plan_dir: Path | None) -> str | None:
    if plan_dir is None:
        return None
    try:
        artifact = PlanRepository.from_plan_dir(plan_dir).latest_execution_batch_artifact()
    except (OSError, RuntimeError, ValueError):
        return None
    if artifact is None:
        return None
    try:
        return artifact.relative_to(plan_dir).as_posix()
    except ValueError:
        return artifact.name


def _phase_result_signature(plan_dir: Path | None) -> tuple[int, int] | None:
    if plan_dir is None:
        return None
    try:
        stat = (plan_dir / "phase_result.json").stat()
    except OSError:
        return None
    return (stat.st_mtime_ns, stat.st_size)


def _record_lifecycle_failure(
    *,
    plan_dir: Path | None,
    kind: str,
    message: str,
    current_state: str | None = None,
    phase: str | None,
    resume_cursor: dict[str, Any] | None,
    last_artifact: str | None = None,
    suggested_action: str | None = None,
    metadata: dict[str, Any] | None = None,
    progress_emitter: Any | None = None,
) -> None:
    if plan_dir is None:
        return
    if current_state is None:
        # Driver-lifecycle exit (iteration cap, stall, cost cap, etc.): record
        # the failure event for audit + resume_cursor, but preserve the plan's
        # actual current_state — the driver giving up doesn't terminate the plan.
        try:
            # dormant-path: subprocess seam, retired at M6
            state_data = json.loads((plan_dir / "state.json").read_text(encoding="utf-8"))
            if isinstance(state_data, dict):
                current_state = state_data.get("current_state") or STATE_BLOCKED
            else:
                current_state = STATE_BLOCKED
        except FileNotFoundError:
            current_state = STATE_BLOCKED
        except json.JSONDecodeError:
            _warn_read_fallback(
                "M3A_WARN_LIFECYCLE_FAILURE_READ",
                path=plan_dir / "state.json",
                reason="corrupt_json",
            )
            current_state = STATE_BLOCKED
        except (OSError, UnicodeDecodeError, ValueError):
            _warn_read_fallback(
                "M3A_WARN_LIFECYCLE_FAILURE_READ",
                path=plan_dir / "state.json",
                reason="unreadable",
            )
            current_state = STATE_BLOCKED
    failure_details: dict[str, Any] | None = None
    try:
        failure_details = PlanRepository.from_plan_dir(plan_dir).record_lifecycle_failure(
            kind=kind,
            message=message,
            current_state=current_state,
            phase=phase,
            resume_cursor=resume_cursor,
            last_artifact=last_artifact,
            suggested_action=suggested_action,
            metadata=metadata,
        )
    except (OSError, RuntimeError, ValueError):
        return
    queue_root, marker_dir, repair_session, repair_run_kind = (
        _lifecycle_repair_request_route(plan_dir)
    )
    _enqueue_lifecycle_failure_request(
        plan_dir=plan_dir,
        queue_root=queue_root,
        marker_dir=marker_dir,
        session=repair_session,
        run_kind=repair_run_kind,
        kind=kind,
        message=message,
        current_state=current_state,
        phase=phase,
        suggested_action=suggested_action,
        metadata=metadata,
    )
    if progress_emitter is not None and failure_details is not None:
        if current_state == STATE_BLOCKED:
            progress_emitter.execution_blocked(summary=message, **failure_details)
        else:
            progress_emitter.plan_failed(summary=message, **failure_details)


def _enqueue_lifecycle_failure_request(
    *,
    plan_dir: Path,
    queue_root: Path,
    marker_dir: Path | None = None,
    session: str | None = None,
    run_kind: str = "plan",
    kind: str,
    message: str,
    current_state: str | None,
    phase: str | None,
    suggested_action: str | None,
    metadata: dict[str, Any] | None,
) -> None:
    try:
        from arnold_pipelines.megaplan.cloud.feature_flags import repair_request_queue_enabled
        from arnold_pipelines.megaplan.cloud.repair_requests import enqueue_repair_request

        if not repair_request_queue_enabled():
            return
        workspace_path = _workspace_path_for_plan_dir(plan_dir)
        enqueue_repair_request(
            queue_root=queue_root,
            marker_dir=marker_dir or plan_dir,
            session=session or plan_dir.name,
            source="lifecycle_failure",
            workspace=workspace_path,
            run_kind=run_kind,
            target={
                "plan_dir": str(plan_dir),
                "plan_name": plan_dir.name,
                "workspace_path": str(workspace_path),
            },
            problem_signature={
                "failure_kind": kind,
                "current_state": current_state or "",
                "phase_or_step": phase or "",
                "milestone_or_plan": plan_dir.name,
                "gate_recommendation": suggested_action or "",
                "blocked_task_id": _lifecycle_blocked_task_id(metadata),
            },
            root_cause_hint=message,
        )
    except Exception:
        _warn_best_effort_emit_failure(
            "M3A_WARN_REPAIR_REQUEST_ENQUEUE",
            action="enqueue_lifecycle_failure_request",
            plan_dir=plan_dir,
            phase=phase,
            context={"failure_kind": kind},
        )


def _enqueue_terminal_failure_request(plan_dir: Path) -> None:
    """Route a handler-recorded terminal failure to the managed repair queue.

    Some handlers, notably review, record ``latest_failure`` while transitioning
    the plan directly to ``blocked``.  The auto driver observes that terminal
    state without calling :func:`_record_lifecycle_failure`, so mirror the
    existing failure into repair custody without rewriting plan state.
    """

    try:
        state = json.loads((plan_dir / "state.json").read_text(encoding="utf-8"))
        failure = state.get("latest_failure") if isinstance(state, dict) else None
        if not isinstance(failure, dict):
            return
        queue_root, marker_dir, repair_session, repair_run_kind = (
            _lifecycle_repair_request_route(plan_dir)
        )
        metadata = failure.get("metadata")
        _enqueue_lifecycle_failure_request(
            plan_dir=plan_dir,
            queue_root=queue_root,
            marker_dir=marker_dir,
            session=repair_session,
            run_kind=repair_run_kind,
            kind=str(failure.get("kind") or "terminal_blocked"),
            message=str(failure.get("message") or "plan entered a blocked terminal state"),
            current_state=str(state.get("current_state") or STATE_BLOCKED),
            phase=str(failure.get("phase") or "") or None,
            suggested_action=str(failure.get("suggested_action") or "") or None,
            metadata=metadata if isinstance(metadata, dict) else None,
        )
    except Exception:
        _warn_best_effort_emit_failure(
            "M3A_WARN_REPAIR_REQUEST_ENQUEUE",
            action="enqueue_terminal_failure_request",
            plan_dir=plan_dir,
            phase="terminal_block",
        )


def _lifecycle_repair_request_route(
    plan_dir: Path,
) -> tuple[Path, Path, str, str]:
    """Resolve lifecycle failures onto the dispatcher-owned queue when set.

    Local runs retain their workspace queue. Managed cloud launchers inject the
    canonical queue, session, marker, and run-kind identity so plan-level
    failures cannot become accepted-but-unclaimed sidecars in a nested
    workspace queue.
    """

    workspace_path = _workspace_path_for_plan_dir(plan_dir)
    queue_root = Path(
        os.environ.get("ARNOLD_REPAIR_QUEUE_ROOT")
        or workspace_path / ".megaplan" / "repair-queue"
    )
    marker_dir = Path(os.environ.get("ARNOLD_REPAIR_MARKER_DIR") or plan_dir)
    session = os.environ.get("ARNOLD_REPAIR_SESSION") or plan_dir.name
    run_kind = os.environ.get("ARNOLD_REPAIR_RUN_KIND") or "plan"
    return queue_root, marker_dir, session, run_kind


def _workspace_path_for_plan_dir(plan_dir: Path) -> Path:
    if plan_dir.parent.name == "plans" and plan_dir.parent.parent.name == ".megaplan":
        return plan_dir.parent.parent.parent
    return plan_dir


def _lifecycle_blocked_task_id(metadata: dict[str, Any] | None) -> str:
    if not isinstance(metadata, dict):
        return ""
    for key in ("blocked_task_id", "task_id"):
        value = metadata.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    blocked = metadata.get("blocked_task_ids")
    if isinstance(blocked, list):
        for value in blocked:
            if isinstance(value, str) and value.strip():
                return value.strip()
    return ""


def _clear_latest_failure_for_success(plan_dir: Path | None) -> None:
    if plan_dir is None:
        return

    def _clear(current: dict[str, Any]) -> bool:
        changed = current.get("latest_failure") is not None
        current["latest_failure"] = None
        if "resume_cursor" in current:
            current.pop("resume_cursor", None)
            changed = True
        return changed

    try:
        write_plan_state(plan_dir, mode="patch-many", patch={}, mutation=_clear)
    except (CliError, OSError, RuntimeError, ValueError):
        return


def _clear_latest_failure_for_phase_dispatch(
    plan_dir: Path | None,
    phase: str | None,
) -> dict[str, Any] | None:
    if plan_dir is None or phase not in PHASE_NAMES:
        return None

    prior_failure: dict[str, Any] | None = None

    def _clear(current: dict[str, Any]) -> bool:
        nonlocal prior_failure
        failure = current.get("latest_failure")
        if isinstance(failure, dict):
            prior_failure = dict(failure)
        changed = current.get("latest_failure") is not None
        current["latest_failure"] = None
        if "resume_cursor" in current:
            current.pop("resume_cursor", None)
            changed = True
        return changed

    try:
        write_plan_state(plan_dir, mode="patch-many", patch={}, mutation=_clear)
    except (CliError, OSError, RuntimeError, ValueError):
        return prior_failure
    return prior_failure


_OBSOLETE_TERMINAL_BLOCK_FAILURE_KINDS = frozenset(
    {
        "blocked_recovery_not_resolved",
        "control_binding_mismatch",
        "invalid_transition_loop",
    }
)


def _failure_is_obsolete_after_terminal_block(failure: Any) -> bool:
    if not isinstance(failure, dict):
        return False
    kind = failure.get("kind")
    if kind in _OBSOLETE_TERMINAL_BLOCK_FAILURE_KINDS:
        return True
    if kind != "phase_failed":
        return False
    metadata = failure.get("metadata")
    stderr = metadata.get("stderr") if isinstance(metadata, dict) else ""
    message = failure.get("message")
    return "invalid_transition" in f"{message or ''}\n{stderr or ''}"


def _clear_obsolete_failure_for_terminal_block(
    plan_dir: Path | None,
    status: Mapping[str, Any],
) -> None:
    if plan_dir is None:
        return
    if status.get("state") != STATE_BLOCKED:
        return
    if status.get("next_step") or status.get("valid_next"):
        return
    blocker_recovery = status.get("blocker_recovery")
    if not isinstance(blocker_recovery, dict):
        return
    if blocker_recovery.get("has_terminal_blockers") is not True:
        return

    def _clear(current: dict[str, Any]) -> bool:
        if not _failure_is_obsolete_after_terminal_block(current.get("latest_failure")):
            return False
        current["latest_failure"] = None
        current.pop("resume_cursor", None)
        return True

    try:
        write_plan_state(plan_dir, mode="patch-many", patch={}, mutation=_clear)
    except (CliError, OSError, RuntimeError, ValueError):
        return


def _reconcile_latest_execution_batch(plan_dir: Path | None) -> dict[str, Any] | None:
    if plan_dir is None:
        return None
    try:
        # dormant-path: subprocess seam, retired at M6
        with (plan_dir / "state.json").open(encoding="utf-8") as handle:
            state_data = json.load(handle)
        if not isinstance(state_data, dict):
            return {"reconciled": False, "reason": "state payload was not an object"}
        from arnold_pipelines.megaplan.execute.merge import reconcile_latest_execution_batch

        return reconcile_latest_execution_batch(plan_dir, state_data)
    except Exception as error:
        return {"reconciled": False, "reason": str(error)}


def _shadow_completion_verdict(
    plan: str,
    plan_dir: Path | None,
    cwd: Path | None,
    *,
    log: Callable[..., None],
) -> str:
    """Compute + persist + log a completion verdict for a done plan.

    Returns ``done`` when the driver should proceed normally, ``routed`` when
    enforce mode patched state back to revise routing, and ``operator_required``
    when enforcement exhausted its retry cap.
    """
    if plan_dir is None:
        return "done"
    _log = logging.getLogger("arnold_pipelines.megaplan.auto")
    try:
        from arnold_pipelines.megaplan.orchestration.completion_contract import (
            CONTRACT_MODE_ENFORCE,
            CONTRACT_MODE_SHADOW,
            CONTRACT_MODE_WARN,
            CompletionSubject,
            compute_verdict,
            extract_green_suite_info,
            normalize_contract_mode,
        )
        from arnold_pipelines.megaplan.orchestration.completion_io import write_completion_verdict

        state: dict[str, Any] = {}
        try:
            # dormant-path: subprocess seam, retired at M6
            raw = json.loads((plan_dir / "state.json").read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                state = raw
        except Exception:
            state = {}

        config = state.get("config") if isinstance(state.get("config"), dict) else {}
        mode = normalize_contract_mode(config.get("completion_contract_mode"))

        project_dir_str = config.get("project_dir") if isinstance(config, dict) else None
        if isinstance(project_dir_str, str) and project_dir_str:
            project_dir = Path(project_dir_str)
        else:
            project_dir = cwd or Path.cwd()

        # Read milestone_base_sha from plan state chain_policy.
        # auto.py is single-plan — no ChainState fallback.
        milestone_base_sha: str | None = state.get("meta", {}).get("chain_policy", {}).get("milestone_base_sha")
        subject = CompletionSubject(
            kind="plan",
            name=plan,
            to_state="done",
            plan_name=plan,
        )
        verdict = compute_verdict(
            plan_dir=plan_dir,
            project_dir=project_dir,
            state=state,
            subject=subject,
            mode=mode,
            git_base_ref=milestone_base_sha,
        )
        try:
            write_completion_verdict(plan_dir, verdict)
        except Exception:
            pass  # persistence failure must never break the run

        log(verdict.one_line())

        if mode == CONTRACT_MODE_SHADOW:
            return "done"

        if mode == CONTRACT_MODE_WARN:
            if verdict.would_block:
                delta_dict, _ = extract_green_suite_info(verdict)
                newly_failing = (delta_dict or {}).get("newly_failing", []) if delta_dict else list(verdict.failures)
                _log.warning(
                    "completion_contract_mode=warn: advisory — verdict would block plan %r; "
                    "newly_failing=%r failures=%r",
                    plan,
                    newly_failing,
                    list(verdict.failures),
                )
            return "done"

        if mode == CONTRACT_MODE_ENFORCE:
            delta_dict, result_status = extract_green_suite_info(verdict)
            if result_status in {"runner_error", "timeout", "not_applicable"}:
                _log.warning(
                    "completion_contract_mode=enforce: verification run status=%r for plan %r — "
                    "not blocking (non-deterministic result); would_block=%r",
                    result_status,
                    plan,
                    verdict.would_block,
                )
                return "done"
            if delta_dict is None or not delta_dict.get("computable", False):
                _log.warning(
                    "completion_contract_mode=enforce: delta not computable for plan %r — "
                    "not blocking; would_block=%r",
                    plan,
                    verdict.would_block,
                )
                return "done"

            newly_failing = delta_dict.get("newly_failing") or []
            deleted_tests = delta_dict.get("deleted_tests") or []
            if not newly_failing and not deleted_tests:
                return "done"

            max_retries = int(config.get("enforce_revise_max_retries", 2))
            retry_count = int(state.get("enforce_revise_count", 0))
            if retry_count >= max_retries:
                _log.warning(
                    "completion_contract_mode=enforce: plan %r blocked; revise retry cap %d "
                    "exhausted — operator action required; newly_failing=%r deleted_tests=%r",
                    plan,
                    max_retries,
                    list(newly_failing),
                    list(deleted_tests),
                )
                try:
                    write_plan_state(
                        plan_dir,
                        mode="patch-many",
                        patch={"current_state": STATE_BLOCKED},
                    )
                except Exception:
                    pass
                return "operator_required"

            log(
                f"completion_contract_mode=enforce: blocking plan {plan!r} — "
                f"routing to revise (retry {retry_count + 1}/{max_retries}); "
                f"newly_failing={list(newly_failing)!r} deleted_tests={list(deleted_tests)!r}"
            )
            try:
                write_plan_state(
                    plan_dir,
                    mode="patch-many",
                    patch={
                        "current_state": STATE_CRITIQUED,
                        "last_gate": {"recommendation": "ITERATE"},
                        "enforce_revise_count": retry_count + 1,
                    },
                )
            except Exception as exc:
                _log.warning(
                    "completion_contract_mode=enforce: failed to patch state for plan %r — "
                    "failing open: %s",
                    plan,
                    exc,
                )
                return "done"
            return "routed"

        return "done"
    except Exception as exc:  # fail-open: a verdict bug must never break a run
        _log.debug("shadow completion verdict failed for plan %r: %s", plan, exc)
        return "done"


def _recover_execute_callback_failure_state(plan_dir: Path | None) -> bool:
    """Restore a successfully executed plan after an external callback failure."""
    if plan_dir is None:
        return False
    # dormant-path: subprocess seam, retired at M6
    state_path = plan_dir / "state.json"
    try:
        with state_path.open(encoding="utf-8") as handle:
            state_data = json.load(handle)
        if not isinstance(state_data, dict):
            return False
        if state_data.get("current_state") != STATE_FAILED:
            return False
        latest_failure = state_data.get("latest_failure")
        if not isinstance(latest_failure, dict):
            return False
        if latest_failure.get("kind") != "phase_callback_failed":
            return False
        if latest_failure.get("phase") != "execute":
            return False
        reconciliation = latest_failure.get("metadata", {}).get("checkpoint_reconciliation")
        if not isinstance(reconciliation, dict) or reconciliation.get("reconciled") is not True:
            return False
        history = state_data.get("history")
        if not isinstance(history, list):
            return False
        last_execute = next(
            (
                entry for entry in reversed(history)
                if isinstance(entry, dict) and entry.get("step") == "execute"
            ),
            None,
        )
        if not isinstance(last_execute, dict):
            return False
        execute_result = last_execute.get("result")
        if execute_result not in {"success", "blocked"}:
            return False
        if execute_result == "success":
            ok, reasons = _execute_completion_authority(plan_dir)
            if not ok:
                _record_lifecycle_failure(
                    plan_dir=plan_dir,
                    kind="authority_divergence",
                    message="execute callback recovery refused uncorroborated success",
                    current_state=STATE_BLOCKED,
                    phase="execute",
                    resume_cursor={"phase": "execute", "retry_strategy": "rerun_phase"},
                    suggested_action="Rerun execute so task completion can be corroborated.",
                    metadata={"reasons": reasons},
                    progress_emitter=None,
                )
                return False
        if not (plan_dir / "execution.json").exists():
            return False
        next_state = (
            STATE_EXECUTED if execute_result == "success" else STATE_FINALIZED
        )
        write_plan_state(
            plan_dir,
            mode="patch-many",
            patch={"current_state": next_state, "active_step": None},
            mutation=lambda current: (current.pop("active_step", None), True)[1],
        )
        return True
    except FileNotFoundError:
        return False
    except json.JSONDecodeError:
        _warn_read_fallback(
            "M3A_WARN_CALLBACK_RECOVERY_READ",
            path=state_path,
            reason="corrupt_json",
        )
        return False
    except (OSError, RuntimeError, UnicodeDecodeError, ValueError):
        _warn_read_fallback(
            "M3A_WARN_CALLBACK_RECOVERY_READ",
            path=state_path,
            reason="unreadable",
        )
        return False


def _recover_completed_execute_artifacts_after_failure(plan_dir: Path | None) -> bool:
    """Advance a finalized plan when execute artifacts are already complete.

    A streaming worker can fail after writing every ``execution_batch_N.json``
    and the aggregate ``execution.json`` but before clearing ``active_step`` or
    moving state from finalized -> executed. On resume, rerunning execute would
    redo completed work. Delegate the completeness decision to the same
    adopt-execution validator used by the explicit override path so auto does
    not grow a second, drifting definition of "complete".
    """

    if plan_dir is None:
        return False
    state_path = plan_dir / "state.json"
    try:
        state_data = json.loads(state_path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError, UnicodeDecodeError, ValueError):
        return False
    if not isinstance(state_data, dict):
        return False
    if state_data.get("current_state") != STATE_FINALIZED:
        return False
    active_step = state_data.get("active_step")
    if isinstance(active_step, dict):
        active_phase = active_phase_name(active_step)
        if active_phase and active_phase != "execute":
            return False
    if not (plan_dir / "execution.json").exists():
        return False
    if _latest_review_requires_rework_after_execution(plan_dir):
        return False
    try:
        root = plan_dir.parents[2]
    except IndexError:
        return False
    code, _out, _err = _override_adopt_execution_in_process(
        root=root,
        plan=plan_dir.name,
        reason="megaplan auto: adopted complete execution artifact after worker failure",
    )
    return code == 0


def _recover_completed_gate_artifact_after_failure(plan_dir: Path | None) -> bool:
    """Advance a critiqued plan when a passing gate artifact was already written.

    Gate can fail after writing the normalized ``gate.json`` but before
    ``_finish_step`` persists ``current_state=gated``. Rerunning gate in that
    shape burns model calls and can loop forever. Only adopt the artifact for
    the unambiguous proceed case; iterate/escalate/tiebreaker recommendations
    must continue through the normal handler because they carry routing side
    effects.
    """

    if plan_dir is None:
        return False
    try:
        state_data = json.loads((plan_dir / "state.json").read_text(encoding="utf-8"))
        gate_data = json.loads((plan_dir / "gate.json").read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError, UnicodeDecodeError, ValueError):
        return False
    if not isinstance(state_data, dict) or state_data.get("current_state") != STATE_CRITIQUED:
        return False
    active_step = state_data.get("active_step")
    if isinstance(active_step, dict):
        active_phase = active_phase_name(active_step)
        if active_phase and active_phase != "gate":
            return False
    if not isinstance(gate_data, dict):
        return False
    if gate_data.get("recommendation") != "PROCEED" or gate_data.get("passed") is not True:
        return False
    if gate_data.get("unresolved_flags"):
        return False

    def _patch(current: dict[str, Any]) -> bool:
        current["current_state"] = STATE_GATED
        current.pop("active_step", None)
        current.setdefault("meta", {})["gate_artifact_recovery"] = {
            "reason": "adopted passing gate.json after worker failure",
            "gate_recommendation": gate_data.get("recommendation"),
        }
        return True

    write_plan_state(
        plan_dir,
        mode="patch-many",
        patch={"current_state": STATE_GATED, "active_step": None},
        mutation=_patch,
    )
    return True


def _latest_review_requires_rework_after_execution(plan_dir: Path) -> bool:
    """Return true when old execution evidence is stale behind rework review."""

    review_path = plan_dir / "review.json"
    execution_path = plan_dir / "execution.json"
    try:
        review_data = json.loads(review_path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError, UnicodeDecodeError, ValueError):
        return False
    if not isinstance(review_data, dict):
        return False
    if review_data.get("review_verdict") != "needs_rework":
        return False
    try:
        return review_path.stat().st_mtime >= execution_path.stat().st_mtime
    except (OSError, FileNotFoundError):
        return False


def _finalize_tasks(plan_dir: Path | None) -> tuple[dict[str, Any], ...]:
    if plan_dir is None:
        return ()
    try:
        payload = json.loads((plan_dir / "finalize.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, ValueError):
        return ()
    if not isinstance(payload, dict):
        return ()
    tasks = payload.get("tasks")
    if not isinstance(tasks, list):
        return ()
    return tuple(dict(task) for task in tasks if isinstance(task, dict) and (task.get("id") or task.get("task_id")))


def _execution_batch_completed_task_ids(
    plan_dir: Path | None,
    *,
    project_dir: Path | None,
    state_data: dict[str, Any] | None,
    current_head: str | None = None,
) -> set[str]:
    if plan_dir is None:
        return set()
    completed: set[str] = set()
    for batch_path in list_batch_artifacts(plan_dir):
        try:
            payload = json.loads(batch_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, UnicodeDecodeError, ValueError):
            continue
        if not isinstance(payload, dict):
            continue
        records = [
            item
            for item in payload.get("task_updates", []) or []
            if isinstance(item, dict)
        ]
        if not records:
            continue
        completed.update(
            effective_execute_completed_task_ids(
                records,
                plan_dir=plan_dir,
                project_dir=project_dir,
                state=state_data,
                current_head=current_head,
            )
        )
    return completed


def _latest_recorded_execute_head(plan_dir: Path | None) -> str | None:
    if plan_dir is None:
        return None
    for batch_path in reversed(list_batch_artifacts(plan_dir)):
        try:
            payload = json.loads(batch_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, UnicodeDecodeError, ValueError):
            continue
        if not isinstance(payload, dict):
            continue
        task_updates = payload.get("task_updates")
        if not isinstance(task_updates, list):
            continue
        for record in reversed(task_updates):
            if not isinstance(record, dict):
                continue
            for key in ("head_sha", "head"):
                value = record.get(key)
                if isinstance(value, str) and value.strip():
                    return value.strip()
    return None


def _execute_completion_authority(plan_dir: Path | None) -> tuple[bool, list[str]]:
    """Return whether execute terminal success is corroborated by task evidence."""

    tasks = _finalize_tasks(plan_dir)
    if not tasks:
        return True, []
    state_data = _read_state_data(plan_dir)
    project_dir = None
    if isinstance(state_data, dict):
        config = state_data.get("config")
        raw_project_dir = config.get("project_dir") if isinstance(config, dict) else None
        if isinstance(raw_project_dir, str) and raw_project_dir:
            project_dir = Path(raw_project_dir)
    recorded_execute_head = _latest_recorded_execute_head(plan_dir)
    decisions: dict[str, AuthorityDecision] = {}
    completed = effective_execute_completed_task_ids(
        tasks,
        plan_dir=plan_dir,
        project_dir=project_dir,
        state=state_data,
        current_head=recorded_execute_head,
        decisions=decisions,
    )
    batch_completed = _execution_batch_completed_task_ids(
        plan_dir,
        project_dir=project_dir,
        state_data=state_data,
        current_head=recorded_execute_head,
    )
    missing: list[str] = []
    for task in tasks:
        task_id = str(task.get("id") or task.get("task_id") or "")
        raw_status = task.get("status")
        if raw_status in {None, "", "pending", "todo", "in_progress"}:
            if task_id in batch_completed:
                continue
            missing.append(
                f"{task_id or '<missing-task-id>'}:"
                f"not_executed:{raw_status or 'missing_status'}"
            )
            continue
        if raw_status in {"done", "completed", "skipped", "waived", "not_applicable"} and task_id not in completed:
            if (
                raw_status == "skipped"
                and task.get("reviewer_verdict") == "deferred_baseline_unavailable"
            ):
                continue
            decision = decisions.get(task_id)
            reason = "unknown"
            if decision is not None:
                reason = decision.status.value
                if decision.would_block_reasons:
                    reason = f"{reason}:{','.join(decision.would_block_reasons)}"
            missing.append(f"{task_id}:{reason}")
    return not missing, missing


def _block_for_execute_authority_divergence(
    *,
    plan_dir: Path | None,
    state: str,
    iteration: int,
    last_phase: str | None,
    reasons: list[str],
    log: Callable[..., None],
    outcome: Callable[..., DriverOutcome],
) -> DriverOutcome:
    preserved_active_step: Any = None
    if plan_dir is not None:
        try:
            state_payload = json.loads((plan_dir / "state.json").read_text(encoding="utf-8"))
            if isinstance(state_payload, dict):
                preserved_active_step = state_payload.get("active_step")
        except (OSError, json.JSONDecodeError, UnicodeDecodeError, ValueError):
            preserved_active_step = None
    log(
        "execute terminal success lacks corroborated task completion — blocking for recovery",
        authority_divergence=reasons,
    )
    _record_lifecycle_failure(
        plan_dir=plan_dir,
        kind="authority_divergence",
        message="execute terminal success lacks corroborated task completion",
        current_state=STATE_BLOCKED,
        phase="execute",
        resume_cursor={"phase": "execute", "retry_strategy": "rerun_phase"},
        suggested_action="Rerun execute so task completion can be corroborated.",
        metadata={"iteration": iteration, "reasons": reasons},
        progress_emitter=None,
    )
    if isinstance(preserved_active_step, dict) and plan_dir is not None:
        try:
            write_plan_state(
                plan_dir,
                mode="patch-many",
                patch={"active_step": preserved_active_step},
                validate_current_state=False,
            )
        except Exception:
            pass
    return outcome(
        "blocked",
        final_state=state,
        iterations=iteration,
        reason="execute terminal success lacks corroborated task completion",
        last_phase=last_phase,
        blocking_reasons=reasons,
    )


# Output artifacts written incrementally by long-running phase workers. When
# the worker dies mid-write these files survive on disk but lack the terminal
# fields the recovery paths look for. The next dispatch must start clean —
# otherwise critique's `_recover_valid_critique_output` (and friends) can
# treat the half-written file as authoritative and short-circuit the rerun.
_PHASE_OUTPUT_QUARANTINE: dict[str, tuple[str, ...]] = {
    "critique": ("critique_output.json",),
    "plan": ("plan_output.json",),
    "revise": ("revise_output.json",),
    "gate": ("gate_output.json",),
    "finalize": ("finalize_output.json",),
    "review": ("review_output.json",),
    "execute": ("execute_output.json", "execute_batch_*_output.json"),
}


def _quarantine_phase_outputs(plan_dir: Path, step: str) -> list[str]:
    """Rename half-written `<step>_output.json` files so a re-dispatched
    phase can't be fooled into "recovering" malformed worker output.

    Returns the list of artifact names quarantined (for logging).
    """
    quarantined: list[str] = []
    artifacts = _PHASE_OUTPUT_QUARANTINE.get(step)
    if not artifacts:
        return quarantined
    for name in artifacts:
        sources = (
            sorted(plan_dir.glob(name))
            if any(ch in name for ch in "*?[")
            else [plan_dir / name]
        )
        for source in sources:
            if not source.exists():
                continue
            artifact_name = source.name
            # Treat zero-byte AND structurally-empty payloads as corpses worth
            # quarantining. An output file that holds a complete payload is
            # rare in this orphan path, but we leave it alone — the handler's
            # own recover logic will accept or reject it normally.
            try:
                text = source.read_text(encoding="utf-8")
            except OSError:
                continue
            stripped = text.strip()
            if stripped not in ("", "{}", "[]"):
                try:
                    payload = json.loads(stripped)
                except (json.JSONDecodeError, ValueError):
                    _warn_read_fallback(
                        "M3A_WARN_QUARANTINE_READ",
                        path=source,
                        reason="corrupt_json",
                    )
                    payload = None
                # Non-empty parseable dicts/lists are left in place — only the
                # genuinely-empty corpses are quarantined.
                if isinstance(payload, dict) and payload:
                    continue
                if isinstance(payload, list) and payload:
                    continue
            target = plan_dir / f"{artifact_name}.orphaned"
            try:
                source.replace(target)
            except OSError:
                continue
            quarantined.append(artifact_name)
    return quarantined


def _active_phase_already_completed(
    plan_dir: Path | None,
    phase: str,
    current_state: str,
) -> bool:
    """True iff running ``phase`` is what produced ``current_state``."""
    if plan_dir is None or not phase or not current_state:
        return False
    try:
        from arnold_pipelines.megaplan._core.workflow import phase_produced_state

        state = PlanRepository.from_plan_dir(plan_dir).load_state()
        if not isinstance(state, dict):
            return False
        return phase_produced_state(state, phase, current_state)
    except Exception:
        return False


def _clear_orphaned_active_step(
    plan_dir: Path | None,
    expected_step: str,
    *,
    quarantine: bool = True,
) -> bool:
    """Strip an orphaned ``active_step`` from ``state.json`` in place.

    Returns True iff the cleanup actually wrote a change. The expected step
    name is used purely as a safety check — if state.json's ``active_step``
    no longer matches (because some other actor cleared it), we leave it
    alone rather than racing with a healthy phase.

    ``quarantine`` controls whether ``<step>_output.json`` is renamed aside.
    Dead-worker orphans still quarantine half-written outputs; completed
    in-process orphans keep their valid output for the successor phase.
    """
    if plan_dir is None:
        return False
    # dormant-path: subprocess seam, retired at M6
    state_path = plan_dir / "state.json"
    try:
        with state_path.open(encoding="utf-8") as handle:
            state_data = json.load(handle)
    except FileNotFoundError:
        return False
    except json.JSONDecodeError as exc:
        raise CliError(
            "orphan_clear_read",
            f"M3B_HALT_ORPHAN_CLEAR_READ: failed to parse {state_path}: {exc}",
            extra={"path": str(state_path), "expected_step": expected_step},
        ) from exc
    except (OSError, UnicodeDecodeError, ValueError) as exc:
        raise CliError(
            "orphan_clear_read",
            f"M3B_HALT_ORPHAN_CLEAR_READ: failed to read {state_path}: {exc}",
            extra={"path": str(state_path), "expected_step": expected_step},
        ) from exc
    if not isinstance(state_data, dict):
        raise CliError(
            "orphan_clear_read",
            "M3B_HALT_ORPHAN_CLEAR_READ: "
            f"{state_path} must contain a JSON object, got {type(state_data).__name__}",
            extra={
                "path": str(state_path),
                "expected_step": expected_step,
                "root_type": type(state_data).__name__,
            },
        )
    current_active = state_data.get("active_step")
    if not isinstance(current_active, dict):
        return False
    recorded_step = active_phase_name(current_active)
    if recorded_step != expected_step:
        return False
    quarantined = (
        _quarantine_phase_outputs(plan_dir, expected_step) if quarantine else []
    )

    def _patch_orphan_recovery(current: dict[str, Any]) -> bool:
        changed = current.pop("active_step", None) is not None
        if quarantined:
            meta = current.setdefault("meta", {})
            if isinstance(meta, dict):
                history = meta.setdefault("orphan_recoveries", [])
                if isinstance(history, list):
                    history.append({
                        "step": expected_step,
                        "quarantined": list(quarantined),
                    })
                    changed = True
        return changed

    try:
        write_plan_state(
            plan_dir,
            mode="patch-many",
            patch={},
            mutation=_patch_orphan_recovery,
            validate_current_state=False,
        )
    except Exception as exc:
        raise CliError(
            "orphan_clear_write",
            f"M3B_HALT_ORPHAN_CLEAR_WRITE: failed to clear orphaned active_step in {state_path}: {exc}",
            extra={"path": str(state_path), "expected_step": expected_step},
        ) from exc
    return True


@dataclass(frozen=True)
class _AutoDispatchProjection:
    next_step: str | None
    valid_next: tuple[str, ...]
    issue: str | None = None
    message: str = ""
    observed_phase: str | None = None
    observed_phase_source: str | None = None


def _projection_state_snapshot(
    plan: str,
    plan_dir: Path | None,
    status: Mapping[str, Any],
) -> dict[str, Any]:
    state = _read_state_data(plan_dir) or {}
    if not isinstance(state.get("name"), str) or not state.get("name"):
        state["name"] = plan
    current_state = status.get("state")
    if not isinstance(state.get("current_state"), str) and isinstance(current_state, str):
        state["current_state"] = current_state
    config = state.get("config")
    if not isinstance(config, dict):
        state["config"] = {}
    return state


def _projection_uses_recovery(state: Mapping[str, Any]) -> bool:
    current_state = state.get("current_state")
    return current_state in {
        STATE_AWAITING_HUMAN,
        STATE_BLOCKED,
        STATE_FAILED,
    }


def _projection_cursor_payload(
    status: Mapping[str, Any],
    observed_phase: str | None,
) -> dict[str, Any] | None:
    payload = status.get("workflow_cursor")
    if isinstance(payload, Mapping):
        return dict(payload)
    if observed_phase is None:
        return None
    cursor = workflow_cursor(observed_phase)
    if cursor is None:
        return None
    return cursor.to_dict()


def _observed_phase_context(
    state: Mapping[str, Any],
    status: Mapping[str, Any],
) -> tuple[str | None, str | None]:
    active_step = status.get("active_step")
    if isinstance(active_step, Mapping):
        active_phase = active_phase_name(active_step)
        if isinstance(active_phase, str) and active_phase:
            return active_phase, "active_step"
    state_active_step = state.get("active_step")
    if isinstance(state_active_step, Mapping):
        active_phase = active_phase_name(state_active_step)
        if isinstance(active_phase, str) and active_phase:
            return active_phase, "active_step"
    resume_cursor = state.get("resume_cursor")
    if isinstance(resume_cursor, Mapping):
        phase = resume_cursor.get("phase")
        if isinstance(phase, str) and phase:
            return phase, "resume_cursor"
    latest_failure = state.get("latest_failure")
    if isinstance(latest_failure, Mapping):
        phase = latest_failure.get("phase")
        if isinstance(phase, str) and phase:
            return phase, "latest_failure"
    # A history record is not automatically a completed transition.  In
    # particular execute emits ``partial``/``blocked`` while finalized keeps
    # projecting execute for the remaining work.  Letting those records
    # manufacture a review cursor turns a valid rework continuation into a
    # workflow_cursor_mismatch.
    last_step = status.get("last_step")
    if (
        isinstance(last_step, Mapping)
        and last_step.get("result") in {"success", "needs_rework", "force_proceeded"}
    ):
        phase = last_step.get("step")
        if isinstance(phase, str) and phase:
            return phase, "last_step"
    return None, None


def _gate_operator_issue(state: Mapping[str, Any]) -> tuple[str, str] | None:
    last_gate = state.get("last_gate")
    if not isinstance(last_gate, Mapping):
        return None
    recommendation = last_gate.get("recommendation")
    if recommendation == "ESCALATE":
        return (
            "gate_escalated",
            "gate escalated and requires an operator decision",
        )
    preflight = last_gate.get("preflight_results")
    failed = (
        {name for name, passed in preflight.items() if not passed}
        if isinstance(preflight, Mapping)
        else set()
    )
    if (
        state.get("current_state") == STATE_BLOCKED
        and recommendation == "PROCEED"
        and not last_gate.get("passed", False)
        and failed
        and failed <= {"claude_available", "codex_available"}
    ):
        return (
            "gate_force_proceed_required",
            "gate proceed is blocked by agent-availability preflight and requires an operator override",
        )
    return None


def _project_auto_dispatch(
    plan: str,
    *,
    plan_dir: Path | None,
    status: Mapping[str, Any],
) -> _AutoDispatchProjection:
    state = _projection_state_snapshot(plan, plan_dir, status)
    observed_phase, observed_phase_source = _observed_phase_context(state, status)
    cursor_payload = _projection_cursor_payload(status, observed_phase)
    cursor_dispatch_phase = (
        str(cursor_payload.get("dispatch_phase"))
        if isinstance(cursor_payload, Mapping) and isinstance(cursor_payload.get("dispatch_phase"), str)
        else _normalize_auto_target_id(observed_phase)
    )
    cursor_next_dispatches = tuple(
        str(item)
        for item in (cursor_payload.get("next_dispatch_phases") if isinstance(cursor_payload, Mapping) else ())
        if isinstance(item, str) and item
    )
    blocker_recovery = status.get("blocker_recovery")
    if (
        state.get("current_state") == STATE_BLOCKED
        and isinstance(blocker_recovery, Mapping)
        and blocker_recovery.get("has_terminal_blockers") is True
    ):
        return _AutoDispatchProjection(
            next_step=None,
            valid_next=(),
            observed_phase=cursor_dispatch_phase,
            observed_phase_source=observed_phase_source,
        )

    try:
        projection = read_valid_targets(
            state,
            plugin_id="megaplan",
            recovery=_projection_uses_recovery(state),
        )
    except Exception:
        projection = ()

    valid_targets: list[str] = []
    mismatches: list[str] = []
    for target in projection:
        target_id = _normalize_auto_target_id(getattr(target, "id", None))
        if not _is_auto_supported_target(target_id):
            continue
        metadata = getattr(target, "metadata", {})
        if not isinstance(metadata, Mapping):
            metadata = {}
        if metadata.get("actionable", True) is False:
            continue
        if _projection_uses_recovery(state):
            valid_targets.append(target_id)
            continue
        if metadata.get("dispatch_surface") == "workflow.native_policy":
            valid_targets.append(target_id)
            continue
        if not cursor_next_dispatches:
            valid_targets.append(target_id)
            continue
        if target_id in cursor_next_dispatches:
            valid_targets.append(target_id)
            continue
        if (
            observed_phase_source in {"active_step", "resume_cursor", "latest_failure"}
            and cursor_dispatch_phase is not None
            and target_id == cursor_dispatch_phase
        ):
            valid_targets.append(target_id)
            continue
        mismatches.append(target_id)

    unique_valid_targets = tuple(dict.fromkeys(valid_targets))
    if unique_valid_targets:
        return _AutoDispatchProjection(
            next_step=unique_valid_targets[0],
            valid_next=unique_valid_targets,
            observed_phase=cursor_dispatch_phase,
            observed_phase_source=observed_phase_source,
        )

    if (
        cursor_dispatch_phase is not None
        and _is_auto_supported_target(cursor_dispatch_phase)
        and observed_phase_source in {"active_step", "resume_cursor", "latest_failure"}
    ):
        return _AutoDispatchProjection(
            next_step=cursor_dispatch_phase,
            valid_next=(cursor_dispatch_phase,),
            observed_phase=cursor_dispatch_phase,
            observed_phase_source=observed_phase_source,
        )

    gate_issue = _gate_operator_issue(state)
    if gate_issue is not None:
        return _AutoDispatchProjection(
            next_step=None,
            valid_next=(),
            issue=gate_issue[0],
            message=gate_issue[1],
            observed_phase=cursor_dispatch_phase,
            observed_phase_source=observed_phase_source,
        )

    if mismatches and cursor_next_dispatches:
        expected = ", ".join(cursor_next_dispatches)
        actual = ", ".join(mismatches)
        source = observed_phase_source or "observed_phase"
        return _AutoDispatchProjection(
            next_step=None,
            valid_next=(),
            issue="workflow_cursor_mismatch",
            message=(
                f"workflow cursor from {source} expects one of [{expected}] "
                f"but control projection offered [{actual}]"
            ),
            observed_phase=cursor_dispatch_phase,
            observed_phase_source=observed_phase_source,
        )

    return _AutoDispatchProjection(
        next_step=None,
        valid_next=(),
        observed_phase=cursor_dispatch_phase,
        observed_phase_source=observed_phase_source,
    )


def _plan_clarification(plan_dir: Path | None) -> dict[str, Any] | None:
    """Read the ``clarification`` field from the plan state file, if any."""
    if plan_dir is None:
        return None
    try:
        # dormant-path: subprocess seam, retired at M6
        state_data = json.loads((plan_dir / "state.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, ValueError):
        return None
    if not isinstance(state_data, dict):
        return None
    return state_data.get("clarification")


def _auto_resume_prep_clarification(plan_dir: Path | None, *, log) -> bool:
    """In auto-approve runs, turn prep clarification halts into assumptions.

    Prep can surface "blocking" questions when a worker fails to gather enough
    evidence. In unattended cloud epics, ``auto_approve`` means the operator has
    delegated bounded judgment calls to the harness; otherwise the chain can park
    forever before planning even starts.
    """
    if plan_dir is None:
        return False
    state_data = _read_state_data(plan_dir)
    if state_data is None:
        return False
    config = state_data.get("config")
    if not isinstance(config, dict) or not config.get("auto_approve"):
        return False
    clarification = state_data.get("clarification")
    if not isinstance(clarification, dict) or clarification.get("source") != "prep":
        return False
    questions = clarification.get("questions") or []
    if not isinstance(questions, list):
        questions = []
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    def _resume(current: dict[str, Any]) -> bool:
        meta = current.get("meta")
        if not isinstance(meta, dict):
            meta = {}
            current["meta"] = meta
        notes = meta.get("notes")
        if not isinstance(notes, list):
            notes = []
            meta["notes"] = notes
        question_text = "\n".join(f"- {q}" for q in questions if isinstance(q, str))
        notes.append(
            {
                "source": "auto_approve_prep_clarification",
                "timestamp": stamp,
                "note": (
                    "Unattended auto-approve run: prep clarification halt was "
                    "converted into planner assumptions so the cloud chain can "
                    "continue. Questions:\n"
                    f"{question_text or '- <none recorded>'}\n"
                    "Planner/executor must make conservative repo-backed "
                    "assumptions, encode them in artifacts, and let normal "
                    "critique/gate/review phases reject unsafe choices."
                ),
            }
        )
        overrides = meta.get("overrides")
        if not isinstance(overrides, list):
            overrides = []
            meta["overrides"] = overrides
        overrides.append(
            {
                "action": "auto-resume-clarify",
                "timestamp": stamp,
                "reason": "auto_approve prep clarification",
                "question_count": len(questions),
            }
        )
        current["current_state"] = STATE_PREPPED
        current.pop("clarification", None)
        return True

    try:
        write_plan_state(
            plan_dir,
            mode="patch-many",
            patch={"current_state": STATE_PREPPED, "clarification": None},
            mutation=_resume,
        )
    except Exception:
        return False
    log(
        "auto-approved prep clarification assumptions — resuming from prepped",
        question_count=len(questions),
    )
    return True


def _parse_active_step_timestamp(value: object) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)
    except ValueError:
        return None


def _active_step_last_activity_stale(
    active_step: dict[str, Any],
    *,
    threshold_seconds: float,
) -> tuple[bool, int | None]:
    if threshold_seconds <= 0:
        return False, None
    last_activity_at = _parse_active_step_timestamp(active_step.get("last_activity_at"))
    if last_activity_at is None:
        return False, None
    idle_seconds = max(
        0,
        int((datetime.now(timezone.utc) - last_activity_at).total_seconds()),
    )
    return idle_seconds >= threshold_seconds, idle_seconds


def _active_step_progress_signature(
    active_step: object,
) -> tuple[str | None, str | None, str | None] | None:
    if not isinstance(active_step, dict):
        return None
    last_activity_at = active_step.get("last_activity_at")
    if not last_activity_at:
        return None
    return (
        str(active_step.get("run_id") or active_step.get("phase") or ""),
        str(last_activity_at),
        str(active_step.get("last_activity_kind") or ""),
    )


def _blocked_tasks_require_user_action(
    plan_dir: Path,
    blocked_tasks: tuple[Any, ...],
) -> bool:
    """Return whether blocked prerequisite tasks are tied to user actions."""

    if not blocked_tasks:
        return False
    finalize_path = plan_dir / "finalize.json"
    try:
        finalize_data = json.loads(finalize_path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError, UnicodeDecodeError):
        return False
    if not isinstance(finalize_data, dict):
        return False
    user_actions = finalize_data.get("user_actions")
    if not isinstance(user_actions, list) or not user_actions:
        return False

    blocked_ids = {
        task_id
        for blocked in blocked_tasks
        if isinstance((task_id := getattr(blocked, "task_id", None)), str) and task_id
    }
    if not blocked_ids:
        return False

    for action in user_actions:
        if not isinstance(action, dict):
            continue
        blocks_task_ids = action.get("blocks_task_ids")
        if isinstance(blocks_task_ids, list):
            scoped_ids = {
                task_id
                for task_id in blocks_task_ids
                if isinstance(task_id, str) and task_id
            }
            if blocked_ids & scoped_ids:
                return True
        if action.get("phase") == "before_execute" and (
            not isinstance(blocks_task_ids, list) or not blocks_task_ids
        ):
            return True
    return False


def _heartbeat_stream_counts(payload: Mapping[str, Any]) -> tuple[int, int] | None:
    token_value = payload.get("tokens_emitted_so_far", payload.get("tokens_emitted"))
    reasoning_value = payload.get(
        "reasoning_emitted_so_far",
        payload.get("reasoning_emitted"),
    )
    if token_value is None and reasoning_value is None:
        return None
    try:
        tokens = int(token_value or 0)
        reasoning = int(reasoning_value or 0)
    except (TypeError, ValueError):
        return None
    return max(tokens, 0), max(reasoning, 0)


def _stall_event_progress_snapshot(
    plan_dir: Path | None,
) -> tuple[int | None, bool, str | None]:
    """Return journal progress relevant to same-state stall detection."""

    if plan_dir is None:
        return None, False, None
    latest_progress_seq: int | None = None
    latest_progress_kind: str | None = None
    open_llm_calls: dict[str, dict[str, Any]] = {}
    anonymous_llm_starts: dict[str, dict[str, Any]] = {}
    # Running max stream counts seen across heartbeats this scan. A heartbeat
    # only counts as progress when it pushes one of these higher.
    max_tokens = -1
    max_reasoning = -1
    # Whether the most recent heartbeat showed growth — used to qualify the
    # in-flight flag so a wedged open call doesn't mask the stall.
    last_heartbeat_advanced = False
    saw_heartbeat = False
    try:
        for event in read_events(plan_dir):
            kind = event.get("kind")
            seq = event.get("seq")
            payload = event.get("payload") if isinstance(event.get("payload"), dict) else {}
            driver_lateral_defer = (
                kind == EventKind.TIER_ESCALATED
                and payload.get("scope") == "lateral_deferred"
            )
            counts_progress = True
            if kind == EventKind.LLM_TOKEN_HEARTBEAT:
                saw_heartbeat = True
                counts = _heartbeat_stream_counts(payload)
                if counts is None:
                    # Pre-count heartbeat shape — fail open (treat as progress).
                    last_heartbeat_advanced = True
                else:
                    tokens, reasoning = counts
                    counts_progress = tokens > max_tokens or reasoning > max_reasoning
                    if tokens > max_tokens:
                        max_tokens = tokens
                    if reasoning > max_reasoning:
                        max_reasoning = reasoning
                    last_heartbeat_advanced = counts_progress
            if (
                kind in STALL_PROGRESS_EVENT_KINDS
                and isinstance(seq, int)
                and not driver_lateral_defer
                and counts_progress
            ):
                latest_progress_seq = seq
                latest_progress_kind = str(kind)
            if kind == EventKind.LLM_CALL_START:
                request_id = payload.get("request_id")
                # A new call (re)starts the growth signal: until its first
                # heartbeat lands, an open call counts as in-flight progress so
                # a legitimately-slow first-token latency isn't false-stalled.
                last_heartbeat_advanced = True
                max_tokens = -1
                max_reasoning = -1
                if request_id:
                    open_llm_calls[str(request_id)] = event
                elif isinstance(seq, int):
                    anonymous_llm_starts[str(seq)] = event
            elif kind in {EventKind.LLM_CALL_END, EventKind.LLM_CALL_ERROR}:
                request_id = payload.get("request_id")
                if request_id:
                    open_llm_calls.pop(str(request_id), None)
                elif anonymous_llm_starts:
                    anonymous_llm_starts.clear()
    except Exception:
        return latest_progress_seq, False, latest_progress_kind
    # An open call only counts as "in flight" (a progress signal) while its
    # stream is still advancing. Once heartbeats flatline, the open call is a
    # wedge — drop the in-flight signal so same-state stall detection can fire.
    call_open = bool(open_llm_calls or anonymous_llm_starts)
    in_flight_progress = call_open and (last_heartbeat_advanced or not saw_heartbeat)
    return (
        latest_progress_seq,
        in_flight_progress,
        latest_progress_kind,
    )


def _auto_publish_branch_name(plan: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9._/-]+", "-", plan.strip()).strip("-./")
    slug = slug[:80] or "plan"
    return f"megaplan/{slug}"


def _git_text(root: Path, argv: list[str], *, timeout: int = 120) -> str:
    try:
        result = subprocess.run(
            argv,
            cwd=str(root),
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        raise CliError(
            "git_publish_timeout",
            f"{shlex.join(argv)} timed out after {timeout} seconds",
            extra={
                "argv": argv,
                "stdout": exc.stdout,
                "stderr": exc.stderr,
            },
        ) from exc
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip()
        raise CliError(
            "git_publish_failed",
            f"{shlex.join(argv)} failed with rc={result.returncode}"
            f"{(': ' + detail) if detail else ''}",
            extra={"argv": argv, "stdout": result.stdout, "stderr": result.stderr},
        )
    return result.stdout.strip()


def _git_has_changes(root: Path) -> bool:
    return bool(_git_text(root, ["git", "status", "--porcelain"]))


def _remote_branch_head(root: Path, branch: str) -> str | None:
    try:
        output = _git_text(root, ["git", "ls-remote", "--heads", "origin", branch], timeout=60)
    except CliError:
        return None
    for line in output.splitlines():
        parts = line.split()
        if parts:
            return parts[0].strip() or None
    return None


def _publish_done_plan(
    *,
    plan: str,
    plan_dir: Path | None,
    root: Path,
    branch: str | None,
    writer: Callable[[str], Any],
) -> dict[str, Any] | None:
    if plan_dir is None:
        return None
    if not _git_has_changes(root):
        payload = {
            "schema": "megaplan.auto_publish",
            "schema_version": 1,
            "status": "skipped",
            "reason": "clean_worktree",
            "plan": plan,
        }
        _atomic_write_text(plan_dir / "publish.json", json.dumps(payload, indent=2) + "\n")
        return payload

    target_branch = branch or _auto_publish_branch_name(plan)
    base_ref = _git_text(root, ["git", "rev-parse", "--abbrev-ref", "HEAD"])
    head_sha_before = _git_text(root, ["git", "rev-parse", "HEAD"])
    existing_branch = subprocess.run(
        ["git", "show-ref", "--verify", "--quiet", f"refs/heads/{target_branch}"],
        cwd=str(root),
        check=False,
        timeout=60,
    )
    if existing_branch.returncode == 0:
        _git_text(root, ["git", "switch", target_branch])
    else:
        _git_text(root, ["git", "switch", "-c", target_branch])

    _git_text(root, ["git", "add", "-A"])
    if not _git_has_changes(root):
        status = "skipped"
        reason = "nothing_staged_after_add"
    else:
        _git_text(
            root,
            [
                "git",
                "commit",
                "--no-verify",
                "-m",
                f"megaplan: {plan} auto publish",
            ],
        )
        status = "pushed"
        reason = ""

    commit_sha = _git_text(root, ["git", "rev-parse", "HEAD"])
    remote_url = ""
    push_result = None
    if status == "pushed":
        try:
            push_result = _git_text(
                root,
                ["git", "push", "--no-verify", "-u", "origin", f"HEAD:{target_branch}"],
                timeout=180,
            )
        except CliError as exc:
            remote_head = _remote_branch_head(root, target_branch)
            if remote_head == commit_sha:
                status = "pushed"
                reason = "remote_verified_after_push_error"
                push_result = exc.message
            else:
                status = "publish_failed"
                reason = exc.code
                push_result = exc.message
        try:
            remote_url = _git_text(root, ["git", "remote", "get-url", "origin"])
        except CliError:
            remote_url = ""
    payload = {
        "schema": "megaplan.auto_publish",
        "schema_version": 1,
        "status": status,
        "reason": reason,
        "plan": plan,
        "branch": target_branch,
        "base_branch": base_ref,
        "base_sha": head_sha_before,
        "commit_sha": commit_sha,
        "remote": "origin",
        "remote_url": remote_url,
        "push_output": push_result,
        "host": socket.gethostname(),
        "published_at": datetime.now(timezone.utc).isoformat(),
    }
    _atomic_write_text(plan_dir / "publish.json", json.dumps(payload, indent=2) + "\n")
    writer(
        f"[auto {plan}] publish {payload['status']}: "
        f"branch={target_branch} commit={commit_sha[:12]}\n"
    )
    return payload


def drive(
    plan: str,
    *,
    cwd: Path | None = None,
    stall_threshold: int = DEFAULT_STALL_THRESHOLD,
    max_iterations: int = DEFAULT_MAX_ITERATIONS,
    max_review_rework_cycles: int = DEFAULT_MAX_REVIEW_REWORK_CYCLES,
    max_cost_usd: float | None = None,
    max_context_retries: int = DEFAULT_MAX_CONTEXT_RETRIES,
    max_external_retries: int = DEFAULT_MAX_EXTERNAL_RETRIES,
    max_blocked_retries: int = DEFAULT_MAX_BLOCKED_RETRIES,
    max_add_note_attempts: int = DEFAULT_MAX_ADD_NOTE_ATTEMPTS,
    max_repeated_failure_signatures: int = DEFAULT_MAX_REPEATED_FAILURE_SIGNATURES,
    escalate_after_fails: int = DEFAULT_ESCALATE_AFTER_FAILS,
    on_escalate: str = "force-proceed",
    poll_sleep: float = DEFAULT_POLL_SLEEP_SECONDS,
    phase_timeout: float = DEFAULT_PHASE_TIMEOUT_SECONDS,
    phase_idle_timeout: float = DEFAULT_PHASE_IDLE_TIMEOUT_SECONDS,
    status_timeout: float = DEFAULT_STATUS_TIMEOUT_SECONDS,
    push: bool = True,
    publish_branch: str | None = None,
    phase_model: list[str] | None = None,
    on_phase_complete: Callable[[str, int, str, str], None] | None = None,
    progress_env: dict[str, str] | None = None,
    writer=sys.stdout.write,
) -> DriverOutcome:
    """Drive ``plan`` to completion.

    Returns a DriverOutcome with a terminal status. The writer is used for
    human-readable progress; structured events are collected on the outcome.
    """

    if on_escalate not in ESCALATE_ACTIONS:
        raise ValueError(f"on_escalate must be one of {ESCALATE_ACTIONS}")

    cwd = Path(cwd or Path.cwd())
    events: list[dict[str, Any]] = []
    last_state: str | None = None
    stall_count = 0
    last_progress_sig: int | None = None
    last_stall_progress_event_seq: int | None = None
    last_active_step_progress_sig: tuple[str | None, str | None, str | None] | None = None
    last_phase: str | None = None
    context_retry_count = 0
    external_retry_count = 0
    external_retry_counts_by_phase: dict[str, int] = {}
    blocked_retry_count = 0
    repeated_failure_signature: str | None = None
    repeated_failure_signature_count = 0
    invalid_transition_signature: str | None = None
    invalid_transition_signature_count = 0
    deterministic_phase_failure_signature: str | None = None
    deterministic_phase_failure_count = 0

    # ── Auto-ESCALATE-up state ─────────────────────────────────────────
    # Consecutive execute failures (timeout / internal_error / quality-block)
    # since the last forward progress. Per-execute and reset on progress or a
    # different next_step — never a global counter that accumulates across
    # unrelated phases/batches. When it reaches escalate_after_fails the driver
    # pins execute to the next more-capable distinct tier model.
    execute_fail_streak = 0
    # Forward-progress signature: (tasks_done + tasks_skipped). When it
    # advances the streak resets — a stronger model isn't warranted while the
    # current one is still making progress.
    last_execute_progress: int | None = None
    # The tier we have climbed the execute pin to (None = not yet escalated).
    escalation_tier_pin: int | None = None
    # The spec we are currently pinning execute to (None = configured routing).
    escalation_pin_spec: str | None = None
    # Total escalations performed, surfaced in the run summary.
    tier_escalations_used = 0

    # Rework-cycle tracking. When review returns `needs_rework`, the plan
    # ping-pongs `finalized ↔ executed ↔ finalized` while execute re-runs
    # batches. From the driver's naive view that looks like a stall, but
    # every completed review rewrites `review.json`, so its mtime is a
    # reliable "forward progress" marker — each advance means a real
    # review cycle finished since we last observed the state.
    plan_dir = _resolve_plan_dir(plan, cwd)
    if plan_dir is not None:
        _admit_auto_driver(plan_dir, plan)
        emit_event(EventKind.INIT, plan_dir=plan_dir, payload={"plan_name": plan})
    from arnold_pipelines.megaplan.orchestration.progress import ProgressEmitter
    progress_emitter = ProgressEmitter.from_env(progress_env)
    last_review_marker = _get_review_marker(plan_dir)
    rework_cycles_observed = 0
    review_rework_signatures = _load_review_rework_signatures(plan_dir)
    review_rework_streaks: dict[str, int] = {}
    review_rework_escalated_tasks: set[str] = set()

    def _record_failure(**kwargs: Any) -> None:
        _record_lifecycle_failure(**kwargs, progress_emitter=progress_emitter)

    def log(msg: str, **fields: Any) -> None:
        events.append({"msg": msg, **fields})
        writer(f"[auto {plan}] {msg}\n")

    live_phase_models = [
        item for item in (phase_model or []) if isinstance(item, str) and "=" in item
    ]

    def _append_live_phase_models(cmd: list[str], phase: str) -> list[str]:
        if not live_phase_models or phase not in PHASE_NAMES:
            return cmd
        next_cmd = list(cmd)
        for item in live_phase_models:
            item_phase = item.split("=", 1)[0]
            if item_phase == phase:
                next_cmd.extend(["--phase-model", item])
        return next_cmd

    def _phase_failure_detail(
        next_step: str,
        stdout: str,
        stderr: str,
        *,
        prior_failure: Mapping[str, Any] | None = None,
    ) -> str:
        state_data = _read_state_data(plan_dir)
        latest_failure = state_data.get("latest_failure") if isinstance(state_data, dict) else None
        if isinstance(latest_failure, dict) and latest_failure.get("phase") == next_step:
            message = latest_failure.get("message")
            if isinstance(message, str) and message.strip():
                return message.strip()
        if isinstance(prior_failure, Mapping) and prior_failure.get("phase") == next_step:
            message = prior_failure.get("message")
            if isinstance(message, str) and message.strip():
                return message.strip()
        return (_filtered_failure_stderr(stderr) or stdout.strip()[-400:]).strip()

    def _run_phase(cmd: list[str], next_step: str) -> tuple[int, str, str, object | None]:
        before_phase_result = _phase_result_signature(plan_dir)
        run_kwargs: dict[str, Any] = {
            "cwd": cwd,
            "timeout": phase_timeout,
            "idle_timeout": phase_idle_timeout,
            "liveness_plan_dir": plan_dir,
        }
        if progress_env:
            run_kwargs["progress_env"] = progress_env
        _apply_envelope_handshake(run_kwargs, plan_dir)
        try:
            code, out, err = _run_planning_phase(cmd, **run_kwargs)
        except TypeError as error:
            # Several unit tests monkeypatch _run_planning_phase with the pre-idle-timeout
            # signature. Keep that surface compatible without weakening the real path.
            if (
                "idle_timeout" not in str(error)
                and "liveness_plan_dir" not in str(error)
                and "progress_env" not in str(error)
            ):
                raise
            run_kwargs.pop("idle_timeout", None)
            run_kwargs.pop("liveness_plan_dir", None)
            run_kwargs.pop("progress_env", None)
            code, out, err = _run_planning_phase(cmd, **run_kwargs)

        # Read the structured phase_result.json only when this command actually
        # produced it. A stale result from the previous phase must not mask a
        # current phase failure or the driver can loop on the same state forever.
        result: object | None = None
        after_phase_result = _phase_result_signature(plan_dir)
        if after_phase_result is not None and after_phase_result != before_phase_result:
            candidate = read_phase_result(plan_dir)
            if candidate is not None and getattr(candidate, "phase", None) == next_step:
                result = candidate

        if result is not None:
            return code, out, err, result

        # Synthesize a PhaseResult when the file is missing
        if code == PHASE_TIMEOUT_EXIT_CODE:
            result = PhaseResult(
                phase=next_step,
                invocation_id="synthesized",
                exit_kind=ExitKind.timeout.value,
            )
        elif "idle timed out" in (err or ""):
            result = PhaseResult(
                phase=next_step,
                invocation_id="synthesized",
                exit_kind=ExitKind.timeout.value,
            )
        elif CONTEXT_EXHAUSTION_FRAGMENT.lower() in ((out or "") + (err or "")).lower():
            result = PhaseResult(
                phase=next_step,
                invocation_id="synthesized",
                exit_kind=ExitKind.context_exhausted.value,
            )
        elif _resolve_phase_name(next_step) not in PHASE_NAMES:
            # Non-phase commands (e.g. 'override add-note') — no synthesis
            result = None
        elif code == 0:
            # Subprocess exited cleanly but didn't write phase_result.json.
            # Synthesis as 'success' — in production all 8 handlers now emit,
            # so this branch only fires for legacy plans and test mocks.
            result = PhaseResult(
                phase=next_step,
                invocation_id="synthesized",
                exit_kind=ExitKind.success.value,
            )
        else:
            result = PhaseResult(
                phase=next_step,
                invocation_id="synthesized",
                exit_kind=ExitKind.internal_error.value,
            )

        return code, out, err, result

    def _clear_completed_phase_active_step(next_step: str, result: object | None) -> None:
        if plan_dir is None or result is None or getattr(result, "phase", None) != next_step:
            return
        try:
            write_plan_state(
                plan_dir,
                mode="patch-many",
                patch={"active_step": None},
                mutation=lambda current: (current.pop("active_step", None), True)[1],
            )
        except Exception:
            return

    def _outcome(
        status: str,
        *,
        final_state: str,
        iterations: int,
        reason: str = "",
        last_phase: str | None = None,
        blocking_reasons: list[str] | None = None,
        publish: dict[str, Any] | None = None,
    ) -> DriverOutcome:
        return DriverOutcome(
            status=status,
            plan=plan,
            final_state=final_state,
            iterations=iterations,
            reason=reason,
            last_phase=last_phase,
            events=events,
            total_cost_usd=_sum_history_cost_usd(plan_dir),
            cost_cap_usd=max_cost_usd,
            context_retries_used=context_retry_count,
            max_context_retries=max_context_retries,
            external_retries_used=external_retry_count,
            max_external_retries=max_external_retries,
            blocked_retries_used=blocked_retry_count,
            max_blocked_retries=max_blocked_retries,
            blocking_reasons=list(blocking_reasons or []),
            tier_escalations_used=tier_escalations_used,
            escalation_tier_pin=escalation_tier_pin,
            publish=publish,
        )

    iteration = 0
    while iteration < max_iterations:
        iteration += 1
        try:
            status_kwargs: dict[str, Any] = {"cwd": cwd, "timeout": status_timeout}
            if progress_env:
                status_kwargs["progress_env"] = progress_env
            status = _status(plan, **status_kwargs)
        except (RuntimeError, json.JSONDecodeError) as error:
            log(f"status lookup failed: {error}")
            _record_failure(
                plan_dir=plan_dir,
                kind="status_lookup_failed",
                message=str(error),
                current_state=None,
                phase=last_phase,
                resume_cursor={"phase": last_phase or "status", "retry_strategy": "rerun_status"},
                suggested_action="Inspect state.json and rerun status before resuming automation.",
                metadata={"iteration": iteration},
            )
            return _outcome(
                "failed",
                final_state=last_state or "unknown",
                iterations=iteration,
                reason=str(error),
                last_phase=last_phase,
            )

        state = status.get("state", "")

        if max_cost_usd is not None:
            cumulative = _sum_history_cost_usd(plan_dir)
            if cumulative > max_cost_usd:
                log(
                    f"cost cap exceeded after phase '{last_phase}': "
                    f"total_cost_usd={cumulative} > cost_cap_usd={max_cost_usd}",
                    total_cost_usd=cumulative,
                    cost_cap_usd=max_cost_usd,
                )
                _record_failure(
                    plan_dir=plan_dir,
                    kind="cost_cap_exceeded",
                    message=f"Cost cap exceeded: {cumulative} > {max_cost_usd}",
                    current_state=None,
                    phase=last_phase,
                    resume_cursor={"phase": last_phase or "status", "retry_strategy": "increase_cap_or_resume"},
                    suggested_action="Increase the cost cap or resume the plan after reviewing spend.",
                    metadata={"total_cost_usd": cumulative, "cost_cap_usd": max_cost_usd, "iteration": iteration},
                )
                return _outcome(
                    "cost_cap_exceeded",
                    final_state=state,
                    iterations=iteration,
                    reason=(
                        f"cost cap exceeded after phase '{last_phase}': "
                        f"{cumulative} > {max_cost_usd}"
                    ),
                    last_phase=last_phase,
                )

        legacy_next_step = status.get("next_step")
        legacy_valid_next = status.get("valid_next") or []
        # A worker can finish every execute artifact but die before its
        # finalized -> executed transition is persisted.  In that shape the
        # state control projection still offers ``execute`` while the last
        # completed workflow event correctly points at ``review``.  Reconcile
        # the artifact *before* comparing those two projections: otherwise
        # the comparison turns a recoverable state-write gap into a permanent
        # workflow_cursor_mismatch and the evidence-gated adoption path below
        # is never reached.
        status_active_step = status.get("active_step")
        status_active_phase = (
            active_phase_name(status_active_step)
            if isinstance(status_active_step, dict)
            else None
        )
        if (
            state == STATE_FINALIZED
            and (legacy_next_step == "execute" or status_active_phase == "execute")
            and _recover_completed_execute_artifacts_after_failure(plan_dir)
        ):
            message = "reconciled complete execution.json before workflow projection"
            log("recovered completed execute artifacts before workflow projection; resuming from executed")
            events.append({"msg": message, "phase": "execute", "plan": plan})
            continue
        projection = _project_auto_dispatch(plan, plan_dir=plan_dir, status=status)
        next_step = projection.next_step
        valid_next = list(projection.valid_next)
        status = dict(status)
        status["legacy_next_step"] = legacy_next_step
        status["legacy_valid_next"] = list(legacy_valid_next)
        status["next_step"] = next_step
        status["valid_next"] = valid_next

        log(
            f"iter {iteration} state={state} next={next_step} valid_next={valid_next} "
            f"legacy_next={legacy_next_step}",
            iteration=iteration,
            state=state,
            next_step=next_step,
            valid_next=valid_next,
            legacy_next_step=legacy_next_step,
            legacy_valid_next=legacy_valid_next,
        )

        repeat = _repeated_failure_signature(plan_dir, status)
        if repeat is None:
            pass
        elif repeat["hash"] == repeated_failure_signature:
            repeated_failure_signature_count += 1
        else:
            repeated_failure_signature = str(repeat["hash"])
            repeated_failure_signature_count = 1
        if (
            repeat is not None
            and max_repeated_failure_signatures > 0
            and repeated_failure_signature_count >= max_repeated_failure_signatures
        ):
            log(
                "repeated failure signature reached cap — bailing to repair",
                repeated_failure_signature=repeated_failure_signature,
                repeated_failure_signature_count=repeated_failure_signature_count,
                max_repeated_failure_signatures=max_repeated_failure_signatures,
                failure_step=repeat.get("step"),
            )
            _record_failure(
                plan_dir=plan_dir,
                kind="repeated_failure_signature",
                message=(
                    "same semantic failure repeated "
                    f"{repeated_failure_signature_count} times: "
                    f"{repeat.get('step')}: {repeat.get('message')}"
                ),
                current_state=STATE_BLOCKED,
                phase=str(repeat.get("step") or last_phase or next_step or "unknown"),
                resume_cursor={
                    "phase": str(repeat.get("step") or last_phase or next_step or "unknown"),
                    "retry_strategy": "repair_repeated_failure",
                },
                last_artifact=_latest_artifact_name(plan_dir),
                suggested_action=(
                    "Dispatch repair: repeated identical failure indicates a "
                    "system or plan-contract issue, not another revise turn."
                ),
                metadata={
                    "signature": repeated_failure_signature,
                    "count": repeated_failure_signature_count,
                    "max_repeated_failure_signatures": max_repeated_failure_signatures,
                    "failure_step": repeat.get("step"),
                    "failure_result": repeat.get("result"),
                    "failure_message": repeat.get("message"),
                    "iteration": iteration,
                },
            )
            return _outcome(
                "blocked",
                final_state=STATE_BLOCKED,
                iterations=iteration,
                reason=(
                    "same semantic failure repeated "
                    f"{repeated_failure_signature_count} times — repair required"
                ),
                last_phase=last_phase,
                blocking_reasons=["repeated_failure_signature"],
            )

        if state == STATE_FAILED and _recover_execute_callback_failure_state(plan_dir):
            log("recovered execute state after phase-complete callback failure; resuming")
            continue
        if (
            state == STATE_FINALIZED
            and (next_step == "execute" or status_active_phase == "execute")
        ):
            if _recover_completed_execute_artifacts_after_failure(plan_dir):
                message = "reconciled complete execution.json after worker failure"
                log("recovered completed execute artifacts after worker failure; resuming from executed")
                events.append({"msg": message, "phase": "execute", "plan": plan})
                continue
            events.append(
                {
                    "msg": "execute artifact reconciliation did not validate; rerunning execute",
                    "phase": "execute",
                    "plan": plan,
                }
            )
        if (
            state == STATE_CRITIQUED
            and (next_step == "gate" or status_active_phase == "gate")
            and _recover_completed_gate_artifact_after_failure(plan_dir)
        ):
            message = "reconciled passing gate.json after worker failure"
            log("recovered completed gate artifact after worker failure; resuming from gated")
            events.append({"msg": message, "phase": "gate", "plan": plan})
            continue

        # Terminal: plan reached a final state (or automation-terminal).
        if state in AUTOMATION_TERMINAL_STATES and not (
            state == STATE_BLOCKED
            and (
                valid_next
                or projection.issue in {"gate_escalated", "gate_force_proceed_required"}
            )
        ):
            if state == STATE_AWAITING_HUMAN:
                # Distinguish prep-sourced halts (blocking ambiguities) from
                # criteria-verification halts. Prep halts include the blocking
                # questions and the resume loop so the operator can act.
                clarification = _plan_clarification(plan_dir)
                if isinstance(clarification, dict) and clarification.get("source") == "prep":
                    if _auto_resume_prep_clarification(plan_dir, log=log):
                        continue
                    questions = clarification.get("questions") or []
                    question_list = "\n".join(f"  - {q}" for q in questions)
                    hint = (
                        "answer via `megaplan override add-note \"…\"` and resume via "
                        "`megaplan override resume-clarify`"
                    )
                    reason = (
                        f"prep surfaced {len(questions)} blocking "
                        f"ambiguities; a human may judge a flagged blocker a non-issue.\n"
                        f"blocking questions:\n{question_list}\n{hint}"
                    )
                    log(f"plan awaiting human clarification ({len(questions)} blocking questions) — automation stopping")
                else:
                    # Criteria-verification halt (NOT a prep clarification).
                    # On an auto-approve run the operator has already delegated
                    # sign-off to the harness: the plan only reaches this state
                    # AFTER the review phase approved (review itself gates on the
                    # plan's tests), so deferred-must criteria are auto-verified
                    # against that review rather than stalling for a human. This
                    # is what `auto_approve: true` means — "don't ask me".
                    if _auto_verify_deferred_must_criteria(plan_dir, log=log):
                        log("auto-verified deferred-must criteria (auto-approve run) — resuming to done")
                        continue
                    log("plan awaiting human verification — automation stopping")
                    reason = "plan has criteria requiring human verification"
                return _outcome(
                    "awaiting_human",
                    final_state=state,
                    iterations=iteration,
                    reason=reason,
                    last_phase=last_phase,
                )
            if state == STATE_TIEBREAKER_PENDING:
                log("tiebreaker pending — run 'megaplan tiebreaker-run --plan <name>' to execute")
                return _outcome(
                    "tiebreaker_pending",
                    final_state=state,
                    iterations=iteration,
                    reason="gate recommended tiebreaker — researcher/challenger run needed",
                    last_phase=last_phase,
                )
            if state == STATE_TIEBREAKER_READY:
                log("tiebreaker ready — run 'megaplan tiebreaker decide --plan <name>' to resolve")
                return _outcome(
                    "tiebreaker_ready",
                    final_state=state,
                    iterations=iteration,
                    reason="tiebreaker synthesis complete — awaiting human decision",
                    last_phase=last_phase,
                )
            if state == STATE_PAUSED:
                log("plan paused — automation stopping until resumed")
                return _outcome(
                    "paused",
                    final_state=state,
                    iterations=iteration,
                    reason="plan is paused and must be resumed by the user",
                    last_phase=last_phase,
                )
            terminal_status = {
                STATE_DONE: "done",
                STATE_ABORTED: "aborted",
                STATE_FAILED: "failed",
                STATE_BLOCKED: "blocked",
                STATE_CANCELLED: "cancelled",
            }.get(state, state)
            log(f"terminal state reached: {state}")
            publish_result: dict[str, Any] | None = None
            if terminal_status == "done":
                ok, reasons = _execute_completion_authority(plan_dir)
                if not ok:
                    return _block_for_execute_authority_divergence(
                        plan_dir=plan_dir,
                        state=state,
                        iteration=iteration,
                        last_phase=last_phase,
                        reasons=reasons,
                        log=log,
                        outcome=_outcome,
                    )
                enforce_result = _shadow_completion_verdict(plan, plan_dir, cwd, log=log)
                if enforce_result == "routed":
                    continue
                if enforce_result == "operator_required":
                    gate_details = ""
                    try:
                        verdict_data = json.loads(
                            (plan_dir / "completion_verdict.json").read_text(encoding="utf-8")
                        )
                        delta = (verdict_data.get("green_suite") or {}).get("delta") or {}
                        gate_details = (
                            f"; newly_failing={list(delta.get('newly_failing') or [])!r} "
                            f"deleted_tests={list(delta.get('deleted_tests') or [])!r}"
                        )
                    except Exception:
                        pass
                    log(
                        f"completion_contract_mode=enforce: plan {plan!r} halted — "
                        "revise retry cap exhausted; operator action required"
                    )
                    _record_failure(
                        plan_dir=plan_dir,
                        kind="enforce_block_cap_exhausted",
                        message="enforce block: revise retry cap exhausted — operator action required",
                        current_state=STATE_BLOCKED,
                        phase="completion_contract",
                        resume_cursor={"phase": "completion_contract", "retry_strategy": "human_approval"},
                        suggested_action="Address newly-failing tests and resume manually.",
                        metadata={"iteration": iteration},
                    )
                    return _outcome(
                        "blocked",
                        final_state=STATE_BLOCKED,
                        iterations=iteration,
                        reason=(
                            f"completion_contract_mode=enforce: revise retry cap exhausted "
                            f"for plan {plan!r} — operator action required{gate_details}"
                        ),
                        last_phase=last_phase,
                    )
                if push:
                    publish_result = _publish_done_plan(
                        plan=plan,
                        plan_dir=plan_dir,
                        root=cwd,
                        branch=publish_branch,
                        writer=writer,
                    )
            # Emit plan_finished or plan_aborted
            if plan_dir is not None:
                if terminal_status == "done":
                    _clear_latest_failure_for_success(plan_dir)
                elif terminal_status == "blocked":
                    _clear_obsolete_failure_for_terminal_block(plan_dir, status)
                    _enqueue_terminal_failure_request(plan_dir)
                try:
                    if terminal_status == "aborted":
                        emit_event(EventKind.PLAN_ABORTED, plan_dir=plan_dir, payload={"state": state})
                    elif terminal_status == "done":
                        emit_event(EventKind.PLAN_FINISHED, plan_dir=plan_dir, payload={"state": state})
                except Exception:
                    _warn_best_effort_emit_failure(
                        "M3A_WARN_EMIT_AUTO_TERMINAL",
                        action="auto-terminal",
                        plan_dir=plan_dir,
                        event_kind=(
                            "plan_aborted" if terminal_status == "aborted" else "plan_finished"
                        ),
                        context={"state": state},
                    )
            return _outcome(
                terminal_status,
                final_state=state,
                iterations=iteration,
                reason=f"plan entered terminal state '{state}'",
                last_phase=last_phase,
                publish=publish_result,
            )

        active_step = status.get("active_step")
        orphan_actions = {
            "resume_or_recover",
            "rerun_same_step",
            "rerun_execute",
            "terminate_idle_step",
        }
        # A cached "wait" verdict can mask a worker that has since died.
        # build_phase_observability probes pid liveness for the status view, but
        # this driver wait path historically did not. If the recorded worker is
        # no longer alive, reclassify to resume_or_recover so the orphan-recovery
        # block below clears and re-dispatches, instead of waiting forever on a
        # dead process (the dead-worker wedge).
        if isinstance(active_step, dict):
            _recorded_worker_pid = active_step.get("worker_pid")
            if _recorded_worker_pid is not None:
                try:
                    _worker_alive = _pid_alive(int(_recorded_worker_pid))
                except (TypeError, ValueError):
                    _worker_alive = True
                if not _worker_alive:
                    active_step["recommended_action"] = "resume_or_recover"
                    active_step.setdefault("health", "dead")
                    active_step["worker_pid_alive"] = False
                    active_step["recommended_action_reason"] = (
                        f"active step's recorded worker (pid={_recorded_worker_pid}) "
                        "is no longer alive; recovering instead of waiting"
                    )
        if (
            isinstance(active_step, dict)
            and active_step.get("recommended_action") not in orphan_actions
        ):
            is_stale, idle_seconds = _active_step_last_activity_stale(
                active_step,
                threshold_seconds=phase_idle_timeout,
            )
            if is_stale:
                threshold_display = int(phase_idle_timeout)
                active_step["recommended_action"] = "terminate_idle_step"
                active_step.setdefault("health", "stale")
                active_step["recommended_action_reason"] = (
                    "active_step.last_activity_at is stale "
                    f"({idle_seconds}s without activity >= {threshold_display}s threshold); "
                    "clearing before redispatch"
                )

        if (
            isinstance(active_step, dict)
            and active_step.get("recommended_action") == "wait"
        ):
            active_name = active_phase_name(active_step)
            if (
                active_name
                and active_name != next_step
                and isinstance(state, str)
                and _active_phase_already_completed(plan_dir, active_name, state)
            ):
                log(
                    f"active step '{active_name}' already completed "
                    f"(state={state}, next={next_step}) but was never cleared — "
                    "clearing in-process orphan so the driver advances",
                    orphan_step=active_name,
                    current_state=state,
                    next_step=next_step,
                )
                if active_name == "execute":
                    ok, reasons = _execute_completion_authority(plan_dir)
                    if not ok:
                        return _block_for_execute_authority_divergence(
                            plan_dir=plan_dir,
                            state=state,
                            iteration=iteration,
                            last_phase=last_phase,
                            reasons=reasons,
                            log=log,
                            outcome=_outcome,
                        )
                _clear_orphaned_active_step(
                    plan_dir, active_name, quarantine=False
                )
                active_step = None

        if (
            isinstance(active_step, dict)
            and active_step.get("recommended_action") == "wait"
        ):
            active_name = active_phase_name(active_step) or next_step or "unknown"
            reason = active_step.get("recommended_action_reason") or "active step is still healthy"
            log(f"active step '{active_name}' still running — waiting: {reason}")
            if poll_sleep > 0:
                time.sleep(poll_sleep)
            iteration -= 1  # healthy wait — don't consume iteration budget
            continue

        # Orphaned active_step: the recorded worker is dead (or stale and
        # unlocked) but state.json still claims a phase is running. Without
        # this guard the driver would either spin-poll a dead phase or
        # treat the corpse as authoritative on status / health. Clear it
        # before dispatching anything, and quarantine the half-written
        # output file from that phase so a fresh dispatch can't be fooled
        # into "recovering" malformed output.
        if (
            isinstance(active_step, dict)
            and active_step.get("recommended_action") in orphan_actions
        ):
            orphan_step = active_phase_name(active_step) or next_step or "unknown"
            reason = (
                active_step.get("recommended_action_reason")
                or "active step is orphaned (worker dead or stale and unlocked)"
            )
            log(
                f"active step '{orphan_step}' is orphaned — clearing before dispatch: {reason}",
                orphan_step=orphan_step,
                recommended_action=active_step.get("recommended_action"),
                health=active_step.get("health"),
            )
            _clear_orphaned_active_step(plan_dir, orphan_step)

        # Review-cycle progress: a fresh review.json means a real review
        # pass completed since the last iteration. This counts as forward
        # progress even when `state` looks unchanged (finalized→executed→
        # finalized during a needs_rework loop) — reset the stall counter
        # so execute has a full rework pass before tripping stall detection.
        current_review_marker = _get_review_marker(plan_dir)
        if (
            current_review_marker is not None
            and current_review_marker != last_review_marker
        ):
            if last_review_marker is not None:
                rework_cycles_observed += 1
                log(
                    f"review.json updated — rework cycle {rework_cycles_observed} "
                    f"observed, resetting stall counter",
                    rework_cycles_observed=rework_cycles_observed,
                )
                stall_count = 0
                current_signatures = _load_review_rework_signatures(plan_dir)
                nonconverging_tasks = _nonconverging_rework_tasks(
                    previous=review_rework_signatures,
                    current=current_signatures,
                    streaks=review_rework_streaks,
                )
                review_rework_signatures = current_signatures
                if nonconverging_tasks:
                    from arnold_pipelines.megaplan.auto_escalation import CATEGORY_POLICY, FailureCategory

                    policy = CATEGORY_POLICY[FailureCategory.review_non_convergence]
                    if policy.escalate:
                        ladder = _read_execute_tier_ladder(plan_dir)
                        for task_id in nonconverging_tasks:
                            if task_id in review_rework_escalated_tasks:
                                continue
                            baseline_tier, next_tier = _review_nonconvergence_escalation_plan(
                                plan_dir=plan_dir,
                                task_id=task_id,
                                ladder=ladder,
                            )
                            if next_tier is None:
                                log(
                                    "review non-convergence at escalation ceiling — "
                                    f"task {task_id} remains subject to review rework cap",
                                    task_id=task_id,
                                    baseline_tier=baseline_tier,
                                    category=FailureCategory.review_non_convergence.value,
                                )
                                continue
                            new_tier, new_spec = next_tier
                            pinned = _pin_tasks_to_tier(plan_dir, [task_id], new_tier)
                            if not pinned:
                                continue
                            review_rework_escalated_tasks.add(task_id)
                            tier_escalations_used += 1
                            log(
                                "review non-convergence — escalating task "
                                f"{task_id} to tier {new_tier}",
                                task_id=task_id,
                                from_tier=baseline_tier,
                                to_tier=new_tier,
                                to_spec=new_spec,
                                category=FailureCategory.review_non_convergence.value,
                            )
                            if plan_dir is not None:
                                try:
                                    emit_event(
                                        EventKind.TIER_ESCALATED,
                                        plan_dir=plan_dir,
                                        phase="execute",
                                        payload={
                                            "from_tier": baseline_tier,
                                            "to_tier": new_tier,
                                            "from_model": (
                                                ladder.get(baseline_tier)
                                                if baseline_tier is not None
                                                else None
                                            ),
                                            "to_model": new_spec,
                                            "failure_count": review_rework_streaks.get(task_id, 0),
                                            "escalations_used": tier_escalations_used,
                                            "scope": "review_non_convergence",
                                            "category": FailureCategory.review_non_convergence.value,
                                            "failing_task_ids": [task_id],
                                        },
                                    )
                                except Exception:
                                    _warn_best_effort_emit_failure(
                                        "M3A_WARN_EMIT_REVIEW_NONCONVERGENCE",
                                        action="auto-review-nonconvergence",
                                        plan_dir=plan_dir,
                                        phase="execute",
                                        event_kind="tier_escalated",
                                        context={"task_id": task_id},
                                    )
                                state_data = _read_state_data(plan_dir)
                                if isinstance(state_data, dict):
                                    state_data.setdefault("history", [])
                                    history = state_data.get("history")
                                    if isinstance(history, list):
                                        history.append(
                                            {
                                                "step": "escalation",
                                                "timestamp": datetime.now(timezone.utc).isoformat(),
                                                "duration_ms": 0,
                                                "cost_usd": 0.0,
                                                "result": FailureCategory.review_non_convergence.value,
                                                "category": FailureCategory.review_non_convergence.value,
                                                "scope": "review_non_convergence",
                                                "from_tier": baseline_tier,
                                                "to_tier": new_tier,
                                                "to_model": new_spec,
                                                "failing_task_ids": [task_id],
                                            }
                                        )
                                        try:
                                            _write_json_atomic(plan_dir / "state.json", state_data)
                                        except OSError:
                                            pass
            last_review_marker = current_review_marker

            if (
                rework_cycles_observed > max_review_rework_cycles + 1
                and state != "reviewed"
                and next_step != "feedback"
            ):
                # Review handler has its own internal cap (see
                # handlers.py::handle_review — force-proceeds to done when
                # prior_rework_count hits max_review_rework_cycles). This
                # driver cap is a belt-and-braces guard against config drift
                # or unexpected loops the handler didn't catch.
                log(
                    f"observed {rework_cycles_observed} rework cycles "
                    f"(cap={max_review_rework_cycles}) — bailing"
                )
                return _outcome(
                    "stalled",
                    final_state=state,
                    iterations=iteration,
                    reason=(
                        f"exceeded review rework cap "
                        f"({rework_cycles_observed} cycles > "
                        f"{max_review_rework_cycles}) — review keeps "
                        "returning needs_rework without resolving"
                    ),
                    last_phase=last_phase,
                )

        # Stall detection: same state for stall_threshold+ iterations with no
        # measurable progress. "Stalled" means "no progress", not merely
        # "same state name": large execute phases can drain tasks while state
        # is pinned, and critique/finalize/review can stream LLM or artifact
        # progress while their state is unchanged.
        progress_now = status.get("progress") or {}
        try:
            progress_sig_now = int(progress_now.get("tasks_done", 0) or 0) + int(
                progress_now.get("tasks_skipped", 0) or 0
            )
        except Exception:
            progress_sig_now = None
        made_task_progress = (
            progress_sig_now is not None
            and last_progress_sig is not None
            and progress_sig_now > last_progress_sig
        )
        (
            stall_progress_event_seq_now,
            has_in_flight_llm,
            stall_progress_event_kind_now,
        ) = _stall_event_progress_snapshot(plan_dir)
        made_event_progress = (
            stall_progress_event_seq_now is not None
            and (
                last_stall_progress_event_seq is None
                or stall_progress_event_seq_now > last_stall_progress_event_seq
            )
        )
        active_step_progress_sig_now = _active_step_progress_signature(active_step)
        made_active_step_progress = (
            active_step_progress_sig_now is not None
            and active_step_progress_sig_now != last_active_step_progress_sig
        )
        made_progress = (
            made_task_progress
            or made_event_progress
            or made_active_step_progress
            or has_in_flight_llm
        )
        if state == last_state and made_progress:
            if stall_count:
                if made_task_progress:
                    reason = f"task progress advanced ({last_progress_sig}->{progress_sig_now})"
                elif made_event_progress:
                    reason = (
                        f"event progress advanced to seq={stall_progress_event_seq_now} "
                        f"kind={stall_progress_event_kind_now}"
                    )
                elif made_active_step_progress:
                    reason = "active_step heartbeat advanced"
                else:
                    reason = "in-flight LLM call still open"
                log(
                    f"{reason} at state={state} — resetting stall counter",
                    stall_count=stall_count,
                    progress_sig=progress_sig_now,
                    progress_event_seq=stall_progress_event_seq_now,
                    in_flight_llm=has_in_flight_llm,
                    active_step_progress=active_step_progress_sig_now,
                )
            stall_count = 0
        elif state == last_state:
            stall_count += 1
            if stall_count >= stall_threshold:
                # Distinguish an all-blocked outcome from a generic stall.
                # When execute reports every pending task as `blocked`, the
                # problem is a poisoned session or genuinely broken env —
                # supervisors should react differently (e.g. retry with a
                # fresh session) rather than just restart and loop.
                progress = status.get("progress") or {}
                tasks_blocked = int(progress.get("tasks_blocked", 0) or 0)
                tasks_pending = int(progress.get("tasks_pending", 0) or 0)
                if tasks_blocked > 0 and tasks_pending == 0:
                    log(
                        f"all pending tasks reported status=blocked "
                        f"({tasks_blocked} blocked) — treating as poisoned outcome"
                    )
                    _record_failure(
                        plan_dir=plan_dir,
                        kind="tasks_blocked",
                        message="all pending tasks reported blocked",
                        current_state=STATE_BLOCKED,
                        phase=last_phase,
                        resume_cursor={"phase": last_phase or "execute", "retry_strategy": "fresh_session"},
                        last_artifact=_latest_artifact_name(plan_dir),
                        suggested_action="Resume with a fresh worker session after reviewing blocked task reasons.",
                        metadata={"tasks_blocked": tasks_blocked, "iteration": iteration},
                    )
                    return _outcome(
                        "blocked",
                        final_state=state,
                        iterations=iteration,
                        reason=(
                            "all tasks reported blocked — workers may be poisoned "
                            "or the environment may genuinely be broken"
                        ),
                        last_phase=last_phase,
                    )
                log(f"stalled at state={state} for {stall_count} iterations")
                _record_failure(
                    plan_dir=plan_dir,
                    kind="stalled",
                    message=f"stalled at '{state}' for {stall_count} iterations",
                    current_state=None,
                    phase=last_phase,
                    resume_cursor={"phase": last_phase or str(next_step or "status"), "retry_strategy": "manual_review"},
                    suggested_action="Review the plan state before resuming automation.",
                    metadata={
                        "stall_count": stall_count,
                        "iteration": iteration,
                        "manual_review_origin": "auto_stall",
                    },
                )
                return _outcome(
                    "stalled",
                    final_state=state,
                    iterations=iteration,
                    reason=(
                        f"stalled at '{state}' for {stall_count} iterations — "
                        "manual intervention required"
                    ),
                    last_phase=last_phase,
                )
        else:
            stall_count = 0
            # Emit state_transition on state change
            if plan_dir is not None and last_state is not None and state != last_state:
                try:
                    emit_event(
                        EventKind.STATE_TRANSITION,
                        plan_dir=plan_dir,
                        payload={"from": last_state, "to": state},
                    )
                except Exception:
                    _warn_best_effort_emit_failure(
                        "M3A_WARN_EMIT_AUTO_STATE_TRANSITION",
                        action="auto-state-transition",
                        plan_dir=plan_dir,
                        event_kind="state_transition",
                        context={"from_state": last_state, "to_state": state},
                    )
            last_state = state
        if progress_sig_now is not None:
            last_progress_sig = progress_sig_now
        last_stall_progress_event_seq = stall_progress_event_seq_now
        last_active_step_progress_sig = active_step_progress_sig_now

        if not next_step:
            if projection.issue in {"gate_escalated", "gate_force_proceed_required"}:
                log(projection.message)
                _record_failure(
                    plan_dir=plan_dir,
                    kind="gate_escalated",
                    message=projection.message,
                    current_state=STATE_BLOCKED,
                    phase="gate",
                    resume_cursor={
                        "phase": projection.observed_phase or "gate",
                        "retry_strategy": "human_decision",
                    },
                    suggested_action=(
                        "Resolve the gate decision explicitly; auto-drive no longer "
                        "chooses override routes on your behalf."
                    ),
                    metadata={
                        "iteration": iteration,
                        "issue": projection.issue,
                        "legacy_next_step": legacy_next_step,
                        "legacy_valid_next": legacy_valid_next,
                    },
                )
                return _outcome(
                    "human_required",
                    final_state=state,
                    iterations=iteration,
                    reason=projection.message,
                    last_phase=last_phase,
                )
            if projection.issue == "workflow_cursor_mismatch":
                log(projection.message)
                _record_failure(
                    plan_dir=plan_dir,
                    kind="workflow_cursor_mismatch",
                    message=projection.message,
                    current_state=STATE_BLOCKED,
                    phase=projection.observed_phase,
                    resume_cursor={
                        "phase": projection.observed_phase or "status",
                        "retry_strategy": "repair_workflow_projection",
                    },
                    suggested_action=(
                        "Repair the plan or workflow projection so the observed "
                        "workflow cursor and control targets agree."
                    ),
                    metadata={
                        "iteration": iteration,
                        "legacy_next_step": legacy_next_step,
                        "legacy_valid_next": legacy_valid_next,
                        "observed_phase_source": projection.observed_phase_source,
                    },
                )
                return _outcome(
                    "blocked",
                    final_state=STATE_BLOCKED,
                    iterations=iteration,
                    reason=projection.message,
                    last_phase=projection.observed_phase,
                    blocking_reasons=["workflow_cursor_mismatch"],
                )
            log(f"no actionable workflow target available (valid_next={valid_next})")
            _record_failure(
                plan_dir=plan_dir,
                kind="no_next_step",
                message="no actionable workflow target available",
                current_state=STATE_FAILED,
                phase=None,
                resume_cursor={"phase": "status", "retry_strategy": "repair_state"},
                suggested_action="Repair state.json or workflow/control mapping before resuming.",
                metadata={
                    "valid_next": valid_next,
                    "iteration": iteration,
                    "legacy_next_step": legacy_next_step,
                    "legacy_valid_next": legacy_valid_next,
                },
            )
            return _outcome(
                "failed",
                final_state=state,
                iterations=iteration,
                reason="no actionable workflow target available",
                last_phase=last_phase,
            )

        # Run the next phase.
        control_mismatch = _control_action_state_mismatch(str(next_step), str(state))
        if control_mismatch is not None:
            reason = str(control_mismatch["message"])
            log(
                "control action is not admissible from current state — bailing to repair",
                action=control_mismatch["action"],
                current_state=control_mismatch["actual_state"],
                required_state=control_mismatch["required_state"],
                next_step=next_step,
            )
            _record_failure(
                plan_dir=plan_dir,
                kind="control_binding_mismatch",
                message=reason,
                current_state=STATE_BLOCKED,
                phase=str(control_mismatch["action"]),
                resume_cursor={
                    "phase": str(control_mismatch["action"]),
                    "retry_strategy": "repair_control_binding",
                },
                last_artifact=_latest_artifact_name(plan_dir),
                suggested_action=(
                    "Repair the auto-driver/control binding: the selected control "
                    "action is not valid for the current plan state."
                ),
                metadata={
                    "action": control_mismatch["action"],
                    "next_step": next_step,
                    "required_state": control_mismatch["required_state"],
                    "actual_state": control_mismatch["actual_state"],
                    "iteration": iteration,
                    "signature": control_mismatch["signature"],
                },
            )
            return _outcome(
                "blocked",
                final_state=STATE_BLOCKED,
                iterations=iteration,
                reason=reason,
                last_phase=str(control_mismatch["action"]),
                blocking_reasons=["control_binding_mismatch"],
            )

        cmd = _command_for_auto_target(next_step) + ["--plan", plan]
        cmd = _append_live_phase_models(cmd, str(next_step))
        last_phase = next_step
        # Apply an active execute-tier escalation pin. The pin overrides
        # tier_models.execute via --phase-model and forces a *fresh*
        # session: the failed worker's session must not be resumed, or the
        # stronger model would never actually run (a tier change is a no-op
        # if the batch --resume's the old session on the old model).
        if next_step == "execute" and escalation_pin_spec is not None:
            cmd = [
                *cmd,
                "--phase-model",
                f"execute={escalation_pin_spec}",
                "--fresh",
            ]
        log(f"running: megaplan {' '.join(cmd)}", phase=next_step, timeout=phase_timeout)
        prior_phase_failure: dict[str, Any] | None = None
        if plan_dir is not None:
            prior_phase_failure = _clear_latest_failure_for_phase_dispatch(plan_dir, next_step)
            try:
                emit_event(EventKind.PHASE_START, plan_dir=plan_dir, phase=next_step, payload={"phase": next_step})
            except Exception:
                _warn_best_effort_emit_failure(
                    "M3A_WARN_EMIT_AUTO_PHASE_START",
                    action="auto-phase-start",
                    plan_dir=plan_dir,
                    phase=next_step,
                    event_kind="phase_start",
                )
        code, out, err, result = _run_phase(cmd, next_step)
        _clear_completed_phase_active_step(next_step, result)
        # Context-exhaustion retry loop: detect via PhaseResult.exit_kind,
        # not by string-matching captured stdout.
        #
        # M4 T17: classification is delegated to RecoveryPolicy.classify
        # (action ∈ {retry_fresh, halt}); auto.py retains every side
        # effect verbatim — counter bumps, log lines, _record_failure
        # call, and the returned _outcome.  Byte-stability of the trace
        # is guarded by tests/characterization/test_context_retry_byte_stability.py.
        if max_context_retries > 0:
            _ctx_policy = RecoveryPolicy(max_context_retries=max_context_retries)
            while (
                next_step == "execute"
                and result is not None
                and getattr(result, "exit_kind", None) == ExitKind.context_exhausted.value
            ):
                _ctx_decision = _ctx_policy.classify(
                    result,
                    layer="phase",
                    context_retries_used=context_retry_count,
                    phase=next_step,
                )
                if _ctx_decision.action == "halt":
                    log(
                        f"context exhaustion retry cap reached ({max_context_retries}) — bailing",
                        context_retries_used=context_retry_count,
                        max_context_retries=max_context_retries,
                    )
                    _record_failure(
                        plan_dir=plan_dir,
                        kind="context_retry_exhausted",
                        message=f"context exhaustion retry cap reached ({context_retry_count}/{max_context_retries})",
                        current_state=None,
                        phase=next_step,
                        resume_cursor={"phase": next_step, "retry_strategy": "fresh_session"},
                        last_artifact=_latest_artifact_name(plan_dir),
                        suggested_action="Resume execute with a fresh worker context.",
                        metadata={"context_retries_used": context_retry_count, "max_context_retries": max_context_retries},
                    )
                    return _outcome(
                        "context_retry_exhausted",
                        final_state=state,
                        iterations=iteration,
                        reason=(
                            f"context exhaustion retry cap reached "
                            f"({context_retry_count}/{max_context_retries})"
                        ),
                        last_phase=last_phase,
                    )
                log(
                    "context exhaustion detected — retrying execute with "
                    f"--fresh (retry {context_retry_count + 1}/{max_context_retries})",
                    context_retries_used=context_retry_count,
                    max_context_retries=max_context_retries,
                    next_context_retry=context_retry_count + 1,
                )
                context_retry_count += _ctx_decision.budget_delta
                if "--fresh" not in cmd:
                    cmd = [*cmd, "--fresh"]
                code, out, err, result = _run_phase(cmd, next_step)
                _clear_completed_phase_active_step(next_step, result)

        while (
            max_external_retries > 0
            and result is not None
            and getattr(result, "exit_kind", None) == ExitKind.external_error.value
        ):
            external_error = getattr(result, "external_error", None)
            phase_retry_count = external_retry_counts_by_phase.get(next_step, 0)
            # M4 T18: bind classification to RecoveryPolicy.classify while
            # preserving every side effect verbatim. classify returns a pure
            # decision; counter bumps + event emits stay below.
            _ext_decision = RecoveryPolicy(
                max_external_retries=max_external_retries
            ).classify(
                result,
                layer="phase",
                external_retries_used=phase_retry_count,
                phase=next_step,
            )
            if _ext_decision.action != "retry_transient":
                break
            # Retain the legacy retryability gate verbatim (identity guard).
            if not _is_retryable_external_error(next_step, external_error):
                break
            provider = getattr(external_error, "provider", "unknown")
            error_kind = getattr(external_error, "error_kind", "unknown")
            error_layer = getattr(external_error, "error_layer", None)
            provider_error_code = getattr(external_error, "provider_error_code", None)
            phase_retry_count += 1
            external_retry_counts_by_phase[next_step] = phase_retry_count
            external_retry_count += 1
            if "--fresh" not in cmd:
                cmd = [*cmd, "--fresh"]
            log(
                f"phase '{next_step}' retryable external_error [{provider}] "
                f"{error_kind} - retrying fresh "
                f"({phase_retry_count}/{max_external_retries})",
                phase=next_step,
                provider=provider,
                error_kind=error_kind,
                error_layer=error_layer,
                provider_error_code=provider_error_code,
                external_retries_used=external_retry_count,
                max_external_retries=max_external_retries,
            )
            if plan_dir is not None:
                try:
                    emit_event(
                        EventKind.PHASE_RETRY,
                        plan_dir=plan_dir,
                        phase=next_step,
                        payload={
                            "phase": next_step,
                            "provider": provider,
                            "error_kind": error_kind,
                            "error_layer": error_layer,
                            "provider_error_code": provider_error_code,
                            "retry": phase_retry_count,
                            "max_retries": max_external_retries,
                            "fresh": True,
                        },
                    )
                except Exception:
                    _warn_best_effort_emit_failure(
                        "M3A_WARN_EMIT_AUTO_PHASE_RETRY",
                        action="auto-phase-retry",
                        plan_dir=plan_dir,
                        phase=next_step,
                        event_kind="phase_retry",
                        context={
                            "provider": provider,
                            "error_kind": error_kind,
                            "error_layer": error_layer,
                            "retry": phase_retry_count,
                            "max_retries": max_external_retries,
                        },
                    )
            code, out, err, result = _run_phase(cmd, next_step)
            _clear_completed_phase_active_step(next_step, result)

        if result is None or getattr(result, "exit_kind", None) not in {
            ExitKind.internal_error.value,
            ExitKind.malformed_model_output.value,
        }:
            deterministic_phase_failure_signature = None
            deterministic_phase_failure_count = 0

        # Timeout detection: read from PhaseResult.exit_kind, not exit code.
        if result is not None and getattr(result, "exit_kind", None) == ExitKind.timeout.value:
            log(f"phase '{next_step}' timed out — stall detection will enforce the cap")
            # current_state=None (NOT STATE_FAILED): a phase timeout is a retryable
            # stall (a single worker turn hung — e.g. a Shannon TUI handshake stall),
            # not a terminal plan failure. Passing None preserves the plan's actual
            # pre-phase state so the next status() returns this same phase as next_step
            # and the driver RE-RUNS it (rerun_phase), bounded by stall detection — the
            # exact contract the log line above promises. This mirrors the sibling
            # internal_error/phase_failed path below (also current_state=None). Writing
            # STATE_FAILED here made the driver's terminal-state check give up on the
            # whole plan despite resume_cursor.retry_strategy=="rerun_phase", turning a
            # transient single-turn stall into a chain-killing failure.
            _record_failure(
                plan_dir=plan_dir,
                kind="phase_timeout",
                message=f"phase '{next_step}' timed out after {phase_timeout}s",
                current_state=None,
                phase=next_step,
                resume_cursor={"phase": next_step, "retry_strategy": "rerun_phase"},
                last_artifact=_latest_artifact_name(plan_dir),
                suggested_action="Investigate the timed-out phase and resume from the phase cursor.",
                metadata={"timeout_seconds": phase_timeout, "idle_timeout_seconds": phase_idle_timeout, "iteration": iteration},
            )
        elif result is not None and getattr(result, "exit_kind", None) == ExitKind.external_error.value:
            external_error = getattr(result, "external_error", None)
            provider = getattr(external_error, "provider", "unknown")
            error_kind = getattr(external_error, "error_kind", "unknown")
            message = getattr(external_error, "message", "")
            status_code = getattr(external_error, "status_code", None)
            retry_after_s = getattr(external_error, "retry_after_s", None)
            provider_error_code = getattr(external_error, "provider_error_code", None)
            error_layer = getattr(external_error, "error_layer", None)
            stall_timeout_s = getattr(external_error, "stall_timeout_s", None)
            elapsed_s = getattr(external_error, "elapsed_s", None)
            content_chunk_count = getattr(external_error, "content_chunk_count", None)
            reasoning_chunk_count = getattr(external_error, "reasoning_chunk_count", None)
            code_hint = f" HTTP {status_code}" if status_code is not None else ""
            retry_hint = (
                f" retry_after={retry_after_s}s"
                if retry_after_s is not None
                else ""
            )
            log(
                f"phase '{next_step}' external_error [{provider}] "
                f"{error_kind}{code_hint}{retry_hint}: {message[:200]}"
            )
            resume_command = f"python -m arnold_pipelines.megaplan resume --plan {plan}"
            _record_failure(
                plan_dir=plan_dir,
                kind="external_error",
                message=(
                    f"phase '{next_step}' external dependency failure: "
                    f"[{provider}] {error_kind}{code_hint}{retry_hint}"
                ),
                current_state=STATE_BLOCKED,
                phase=next_step,
                resume_cursor={
                    "phase": next_step,
                    "retry_strategy": (
                        "wait_and_retry"
                        if retry_after_s is not None and retry_after_s > 0
                        else "check_provider_and_retry"
                    ),
                },
                last_artifact=_latest_artifact_name(plan_dir),
                suggested_action=(
                    f"External provider '{provider}' returned {error_kind}. "
                    "Fix provider/profile settings if needed, then run "
                    f"`{resume_command}`."
                    + (
                        f" Wait {retry_after_s}s before retrying."
                        if retry_after_s is not None
                        else ""
                    )
                ),
                metadata={
                    "provider": provider,
                    "error_kind": error_kind,
                    "status_code": status_code,
                    "retry_after_s": retry_after_s,
                    "provider_error_code": provider_error_code,
                    "error_layer": error_layer,
                    "stall_timeout_s": stall_timeout_s,
                    "elapsed_s": elapsed_s,
                    "content_chunk_count": content_chunk_count,
                    "reasoning_chunk_count": reasoning_chunk_count,
                    "external_retries_used": external_retry_counts_by_phase.get(next_step, 0),
                    "max_external_retries": max_external_retries,
                    "exit_code": code,
                    "iteration": iteration,
                    "resume_command": resume_command,
                    "suggested_recovery_commands": [resume_command],
                },
            )
        infra_payload = _non_retryable_infrastructure_error_payload(out, err)
        if (
            result is not None
            and getattr(result, "exit_kind", None) == ExitKind.internal_error.value
            and infra_payload is not None
        ):
            error_code = str(infra_payload.get("error") or "infrastructure_error")
            message = str(infra_payload.get("message") or error_code)
            details = infra_payload.get("details")
            log(
                f"phase '{next_step}' refused by infrastructure preflight "
                f"{error_code}: {message}"
            )
            _record_failure(
                plan_dir=plan_dir,
                kind="infrastructure_error",
                message=message,
                current_state=None,
                phase=next_step,
                resume_cursor={"phase": next_step, "retry_strategy": "operator_action"},
                last_artifact=_latest_artifact_name(plan_dir),
                suggested_action=(
                    "Resolve the Megaplan engine isolation failure before resuming. "
                    "Use the recorded details to run with a verified isolation provider "
                    "or separate the engine and target writable roots."
                ),
                metadata={
                    "error": error_code,
                    "details": details if isinstance(details, dict) else {},
                    "exit_code": code,
                    "iteration": iteration,
                },
            )
            events.append(
                {
                    "msg": "infrastructure preflight refused phase",
                    "phase": next_step,
                    "error": error_code,
                    "message": message,
                    "details": details if isinstance(details, dict) else {},
                }
            )
            return _outcome(
                "infrastructure_error",
                final_state=state,
                iterations=iteration,
                reason=f"{error_code}: {message}",
                last_phase=next_step,
                blocking_reasons=[error_code],
            )
        elif result is not None and getattr(result, "exit_kind", None) in {
            ExitKind.internal_error.value,
            ExitKind.malformed_model_output.value,
        }:
            # Don't bail immediately — megaplan often records a partial failure
            # in state.json and the next status() reveals a recoverable valid_next.
            # Stall detection will still kill infinite loops.
            exit_kind = getattr(result, "exit_kind", None)
            failure_detail = _phase_failure_detail(
                next_step,
                out,
                err,
                prior_failure=prior_phase_failure,
            )
            filtered_stderr = _filtered_failure_stderr(err)
            diagnostic_metadata = _phase_diagnostic_metadata(err)
            redacted_stderr = redact_security_text(err.strip())[-16_384:]
            log(f"phase '{next_step}' exited with {exit_kind}: {failure_detail}")
            # plan_locked is transient contention from a concurrent auto/phase,
            # not a phase failure. Writing STATE_FAILED here turns a recoverable
            # lock-wait into a terminal state — the bug that surfaced when two
            # auto drivers raced into the same phase. Treat as a no-op; the next
            # iteration's status() will see the lock released.
            if "plan_locked" in ((err or "") + (out or "")):
                deterministic_phase_failure_signature = None
                deterministic_phase_failure_count = 0
                log(f"phase '{next_step}' hit plan_locked — transient contention, retrying next iteration")
            elif (
                next_step == "execute"
                and _recover_completed_execute_artifacts_after_failure(plan_dir)
            ):
                deterministic_phase_failure_signature = None
                deterministic_phase_failure_count = 0
                log("phase 'execute' failed after writing complete artifacts — recovered to executed")
                events.append(
                    {
                        "msg": "reconciled complete execution.json after worker failure",
                        "phase": "execute",
                        "plan": plan,
                    }
                )
            else:
                signature = json.dumps(
                    [next_step, exit_kind, failure_detail],
                    ensure_ascii=True,
                    separators=(",", ":"),
                )
                if signature == deterministic_phase_failure_signature:
                    deterministic_phase_failure_count += 1
                else:
                    deterministic_phase_failure_signature = signature
                    deterministic_phase_failure_count = 1
                if (
                    deterministic_phase_failure_count
                    >= DEFAULT_MAX_DETERMINISTIC_PHASE_FAILURE_ATTEMPTS
                ):
                    reason = (
                        f"phase '{next_step}' repeated the same {exit_kind} "
                        f"{deterministic_phase_failure_count} times: {failure_detail}"
                    )
                    _record_failure(
                        plan_dir=plan_dir,
                        kind="deterministic_phase_failure",
                        message=reason,
                        current_state=STATE_BLOCKED,
                        phase=next_step,
                        resume_cursor={
                            "phase": next_step,
                            "retry_strategy": "repair_phase_contract",
                        },
                        last_artifact=_latest_artifact_name(plan_dir),
                        suggested_action=(
                            "Repair or change the deterministic phase contract before resuming; "
                            "re-running the same phase output cannot make progress."
                        ),
                        metadata={
                            "signature": signature,
                            "count": deterministic_phase_failure_count,
                            "max_attempts": DEFAULT_MAX_DETERMINISTIC_PHASE_FAILURE_ATTEMPTS,
                            "exit_code": code,
                            "stderr": filtered_stderr,
                            "stderr_raw": redacted_stderr,
                            "stdout": out.strip()[-400:],
                            "iteration": iteration,
                            **diagnostic_metadata,
                        },
                    )
                    return _outcome(
                        "blocked",
                        final_state=STATE_BLOCKED,
                        iterations=iteration,
                        reason=reason,
                        last_phase=next_step,
                        blocking_reasons=["deterministic_phase_failure"],
                    )
                _record_failure(
                    plan_dir=plan_dir,
                    kind="phase_failed",
                    message=failure_detail or f"phase '{next_step}' {exit_kind}",
                    current_state=None,
                    phase=next_step,
                    resume_cursor={"phase": next_step, "retry_strategy": "rerun_phase"},
                    last_artifact=_latest_artifact_name(plan_dir),
                    suggested_action="Inspect phase output and resume from the failed phase.",
                    metadata={
                        "exit_code": code,
                        "stderr": filtered_stderr,
                        # Preserve redacted diagnostic stderr even when there
                        # were no warning lines to filter.  The old conditional
                        # erased the only evidence for in-process decoder
                        # failures such as UnicodeDecodeError.
                        "stderr_raw": redacted_stderr,
                        "stdout": out.strip()[-400:],
                        "iteration": iteration,
                        **diagnostic_metadata,
                    },
                )
        elif result is None and code != 0:
            # Non-phase commands (e.g. 'override add-note') that failed —
            # preserve existing exit-code-based handling.
            log(f"command '{next_step}' exited {code}: {err.strip() or out.strip()[-400:]}")
            invalid_transition = _control_invalid_transition_failure(
                next_step,
                str(state),
                out,
                err,
            )
            if invalid_transition is not None:
                signature = str(invalid_transition["signature"])
                if signature == invalid_transition_signature:
                    invalid_transition_signature_count += 1
                else:
                    invalid_transition_signature = signature
                    invalid_transition_signature_count = 1
                should_break = (
                    bool(invalid_transition.get("requires_state_mismatch"))
                    or invalid_transition_signature_count >= DEFAULT_MAX_INVALID_TRANSITION_ATTEMPTS
                )
                if should_break:
                    kind = (
                        "control_binding_mismatch"
                        if invalid_transition.get("requires_state_mismatch")
                        else "invalid_transition_loop"
                    )
                    action = str(invalid_transition.get("action") or next_step)
                    message = str(
                        invalid_transition.get("message")
                        or f"{action} returned invalid_transition"
                    )
                    reason = (
                        f"{action} invalid transition from state "
                        f"'{invalid_transition.get('actual_state') or state}': {message}"
                    )
                    log(
                        "invalid control transition is deterministic — bailing to repair",
                        action=action,
                        current_state=invalid_transition.get("actual_state") or state,
                        required_state=invalid_transition.get("required_state"),
                        invalid_transition_count=invalid_transition_signature_count,
                        max_invalid_transition_attempts=DEFAULT_MAX_INVALID_TRANSITION_ATTEMPTS,
                    )
                    _record_failure(
                        plan_dir=plan_dir,
                        kind=kind,
                        message=reason,
                        current_state=STATE_BLOCKED,
                        phase=action,
                        resume_cursor={
                            "phase": action,
                            "retry_strategy": "repair_control_binding",
                        },
                        last_artifact=_latest_artifact_name(plan_dir),
                        suggested_action=(
                            "Repair the auto-driver/control binding before resuming; "
                            "repeating the same control action in the same state "
                            "will keep returning invalid_transition."
                        ),
                        metadata={
                            "action": action,
                            "next_step": next_step,
                            "required_state": invalid_transition.get("required_state"),
                            "actual_state": invalid_transition.get("actual_state") or state,
                            "error": invalid_transition.get("error"),
                            "cli_error": invalid_transition.get("cli_error"),
                            "signature": signature,
                            "count": invalid_transition_signature_count,
                            "max_attempts": DEFAULT_MAX_INVALID_TRANSITION_ATTEMPTS,
                            "exit_code": code,
                            "stderr": err.strip(),
                            "stdout": out.strip()[-400:],
                            "iteration": iteration,
                        },
                    )
                    return _outcome(
                        "blocked",
                        final_state=STATE_BLOCKED,
                        iterations=iteration,
                        reason=reason,
                        last_phase=action,
                        blocking_reasons=[kind],
                    )
            else:
                invalid_transition_signature = None
                invalid_transition_signature_count = 0
            recover_blocked_payload = (
                _non_retryable_recover_blocked_error_payload(out, err)
                if next_step == "recover-blocked"
                else None
            )
            if recover_blocked_payload is not None:
                error_code = str(recover_blocked_payload.get("error") or "recover_blocked_failed")
                message = str(
                    recover_blocked_payload.get("message")
                    or f"command '{next_step}' exited {code}"
                )
                _record_failure(
                    plan_dir=plan_dir,
                    kind=error_code,
                    message=message,
                    current_state=STATE_BLOCKED,
                    phase=last_phase,
                    resume_cursor=_failure_resume_cursor_for_step(next_step, plan_dir=plan_dir),
                    last_artifact=_latest_artifact_name(plan_dir),
                    suggested_action="Resolve the blocker or use the suggested recovery command before resuming automation.",
                    metadata={
                        "exit_code": code,
                        "stderr": err.strip(),
                        "stdout": out.strip()[-400:],
                        "iteration": iteration,
                        "cli_error": recover_blocked_payload,
                    },
                )
                return _outcome(
                    "blocked",
                    final_state=STATE_BLOCKED,
                    iterations=iteration,
                    reason=message,
                    last_phase=last_phase,
                    blocking_reasons=[error_code],
                )
            _record_failure(
                plan_dir=plan_dir,
                kind="phase_failed",
                message=f"command '{next_step}' exited {code}",
                current_state=None,
                phase=next_step,
                resume_cursor=_failure_resume_cursor_for_step(next_step, plan_dir=plan_dir),
                last_artifact=_latest_artifact_name(plan_dir),
                suggested_action="Inspect command output and resume from the failed phase.",
                metadata={"exit_code": code, "stderr": err.strip(), "stdout": out.strip()[-400:], "iteration": iteration},
            )

        if (
            code in (0, None)
            and on_phase_complete
            and next_step in {"plan", "critique", "gate", "finalize", "execute", "review"}
        ):
            try:
                on_phase_complete(next_step, int(code or 0), out, err)
            except Exception as error:  # pragma: no cover - defensive callback boundary
                log(f"phase-complete callback failed after '{next_step}': {error}")
                reconciliation = (
                    _reconcile_latest_execution_batch(plan_dir)
                    if next_step == "execute"
                    else None
                )
                _record_failure(
                    plan_dir=plan_dir,
                    kind="phase_callback_failed",
                    message=f"phase-complete callback failed after '{next_step}': {error}",
                    current_state=STATE_FAILED,
                    phase=next_step,
                    resume_cursor={"phase": next_step, "retry_strategy": "rerun_phase"},
                    last_artifact=_latest_artifact_name(plan_dir),
                    suggested_action="Fix the phase-complete callback and resume this phase.",
                    metadata={"iteration": iteration, "checkpoint_reconciliation": reconciliation},
                )
                return _outcome(
                    "failed",
                    final_state=state,
                    iterations=iteration,
                    reason=f"phase-complete callback failed after '{next_step}': {error}",
                    last_phase=last_phase,
                )

        # Post-execute routing: consume PhaseResult.exit_kind exclusively.
        # Delete the old pathways that read state["history"], globbed
        # execution_batch_*.json, captured stdout tails, and deviation
        # prefix-matching tables. Those surfaces still exist for user-visible
        # logging, but the driver no longer consults them for decisions.
        if next_step == "execute" and result is not None and max_blocked_retries >= 0:
            ek = getattr(result, "exit_kind", None)
            if ek == ExitKind.success.value:
                ok, reasons = _execute_completion_authority(plan_dir)
                if not ok:
                    return _block_for_execute_authority_divergence(
                        plan_dir=plan_dir,
                        state=state,
                        iteration=iteration,
                        last_phase=last_phase,
                        reasons=reasons,
                        log=log,
                        outcome=_outcome,
                    )
                # Executor succeeded — continue to next phase without retry.
                pass
            elif ek == ExitKind.blocked_by_prereq.value:
                # Executor reported tasks blocked by prerequisites. Only
                # surface awaiting_human when finalize recorded matching user
                # actions; ordinary dependency blocks are not a human gate.
                blocked_tasks: tuple[Any, ...] = getattr(result, "blocked_tasks", ())
                if blocked_tasks:
                    blocked_summaries = [
                        (
                            f"{getattr(bt, 'task_id', '?')} "
                            f"(executor: {getattr(bt, 'notes', '')})"
                            if getattr(bt, "notes", "")
                            else getattr(bt, "task_id", "?")
                        )
                        for bt in blocked_tasks
                    ]
                    blocking_reasons = [
                        (
                            f"task {getattr(bt, 'task_id', '?')} reported "
                            f"status=blocked by executor: {getattr(bt, 'notes', '')}"
                            if getattr(bt, "notes", "")
                            else f"task {getattr(bt, 'task_id', '?')} reported status=blocked by executor"
                        )
                        for bt in blocked_tasks
                    ]
                    if _blocked_tasks_require_user_action(plan_dir, blocked_tasks):
                        reason = (
                            "execute reported blocked tasks awaiting user action: "
                            + "; ".join(blocked_summaries)
                        )
                        log(
                            "execute reported task(s) blocked awaiting user action — "
                            "exiting as awaiting_human without consuming a retry",
                            blocked_retries_used=blocked_retry_count,
                            max_blocked_retries=max_blocked_retries,
                            blocked_task_ids=[getattr(bt, "task_id", "?") for bt in blocked_tasks],
                        )
                        return _outcome(
                            "awaiting_human",
                            final_state=STATE_FINALIZED,
                            iterations=iteration,
                            reason=reason,
                            last_phase=last_phase,
                            blocking_reasons=blocking_reasons,
                        )
                    reason = "execute reported prerequisite-blocked tasks: " + "; ".join(
                        blocked_summaries
                    )
                    log(
                        "execute reported prerequisite-blocked task(s) without matching "
                        "user actions — surfacing as blocked",
                        blocked_retries_used=blocked_retry_count,
                        max_blocked_retries=max_blocked_retries,
                        blocked_task_ids=[getattr(bt, "task_id", "?") for bt in blocked_tasks],
                    )
                    _record_failure(
                        plan_dir=plan_dir,
                        kind="execution_blocked",
                        message=reason,
                        current_state=STATE_BLOCKED,
                        phase=next_step,
                        resume_cursor={
                            "phase": next_step,
                            "batch_index": None,
                            "retry_strategy": "manual_review",
                        },
                        last_artifact=_latest_artifact_name(plan_dir),
                        suggested_action=(
                            "Inspect the prerequisite evidence or resolve the blocked task "
                            "dependency before rerunning execute."
                        ),
                        metadata={
                            "blocked_retries_used": blocked_retry_count,
                            "max_blocked_retries": max_blocked_retries,
                            "blocking_reasons": blocking_reasons,
                        },
                    )
                    return _outcome(
                        "blocked",
                        final_state=STATE_FINALIZED,
                        iterations=iteration,
                        reason=reason,
                        last_phase=last_phase,
                        blocking_reasons=blocking_reasons,
                    )
                # No blocked tasks but still blocked_by_prereq — treat as
                # quality blocking via deviations.
                deviations_list: list[str] = [
                    getattr(dv, "message", str(dv))
                    for dv in getattr(result, "deviations", ())
                ]
                if blocked_retry_count >= max_blocked_retries:
                    log(
                        f"execute blocked by quality gates and retry cap reached "
                        f"({max_blocked_retries}) — bailing",
                        blocked_retries_used=blocked_retry_count,
                        max_blocked_retries=max_blocked_retries,
                        blocking_reasons=deviations_list,
                    )
                    _record_failure(
                        plan_dir=plan_dir,
                        kind="execution_blocked",
                        message="execute blocked_by_prereq with no blocked tasks — treating as quality block",
                        current_state=STATE_BLOCKED,
                        phase=next_step,
                        resume_cursor={
                            "phase": next_step,
                            "batch_index": None,
                            "retry_strategy": "fresh_session",
                        },
                        last_artifact=_latest_artifact_name(plan_dir),
                        suggested_action="Review blocking deviations and resume execute with a fresh session.",
                        metadata={
                            "blocked_retries_used": blocked_retry_count,
                            "max_blocked_retries": max_blocked_retries,
                            "blocking_reasons": deviations_list,
                        },
                    )
                    return _outcome(
                        "worker_blocked",
                        final_state=state,
                        iterations=iteration,
                        reason=(
                            "execute blocked by quality gates "
                            f"after {blocked_retry_count + 1} attempt(s); "
                            f"retry cap {max_blocked_retries} reached"
                        ),
                        last_phase=last_phase,
                        blocking_reasons=deviations_list,
                    )
                blocked_retry_count += 1
                log(
                    f"execute blocked by quality gates — retrying "
                    f"({blocked_retry_count}/{max_blocked_retries})",
                    blocked_retries_used=blocked_retry_count,
                    max_blocked_retries=max_blocked_retries,
                    blocking_reasons=deviations_list,
                )
            elif ek == ExitKind.blocked_by_quality.value:
                # Quality-gate block — retry with cap, using result.deviations
                # directly (no string prefix matching).
                deviations_list = [
                    getattr(dv, "message", str(dv))
                    for dv in getattr(result, "deviations", ())
                ]
                if blocked_retry_count >= max_blocked_retries:
                    log(
                        f"execute blocked by quality gates and retry cap reached "
                        f"({max_blocked_retries}) — bailing",
                        blocked_retries_used=blocked_retry_count,
                        max_blocked_retries=max_blocked_retries,
                        blocking_reasons=deviations_list,
                    )
                    _record_failure(
                        plan_dir=plan_dir,
                        kind="execution_blocked",
                        message="execute blocked by quality gates",
                        current_state=STATE_BLOCKED,
                        phase=next_step,
                        resume_cursor={
                            "phase": next_step,
                            "batch_index": None,
                            "retry_strategy": "fresh_session",
                        },
                        last_artifact=_latest_artifact_name(plan_dir),
                        suggested_action="Review blocking deviations and resume execute with a fresh session.",
                        metadata={
                            "blocked_retries_used": blocked_retry_count,
                            "max_blocked_retries": max_blocked_retries,
                            "blocking_reasons": deviations_list,
                        },
                    )
                    return _outcome(
                        "worker_blocked",
                        final_state=state,
                        iterations=iteration,
                        reason=(
                            "execute blocked by quality gates "
                            f"after {blocked_retry_count + 1} attempt(s); "
                            f"retry cap {max_blocked_retries} reached"
                        ),
                        last_phase=last_phase,
                        blocking_reasons=deviations_list,
                    )
                blocked_retry_count += 1
                log(
                    f"execute blocked by quality gates — retrying "
                    f"({blocked_retry_count}/{max_blocked_retries})",
                    blocked_retries_used=blocked_retry_count,
                    max_blocked_retries=max_blocked_retries,
                    blocking_reasons=deviations_list,
                )
            # timeout, context_exhausted, internal_error already handled above.

        # ── Auto-ESCALATE-up: respond to repeated execute failures ───────
        # Only execute is escalated (it is the phase routed by tier_models),
        # and only *failures* count — a pure latency stall is not, on its own,
        # evidence the model is too weak (and a bigger model is slower), so we
        # gate on hard failures: timeout, internal_error, and quality/prereq
        # blocks. Forward progress or moving off execute resets the streak so
        # the counter is per-execute, never a global accumulator.
        if next_step == "execute":
            progress = status.get("progress") or {}
            try:
                progress_sig = int(progress.get("tasks_done", 0) or 0) + int(
                    progress.get("tasks_skipped", 0) or 0
                )
            except (TypeError, ValueError):
                progress_sig = last_execute_progress or 0
            ek = getattr(result, "exit_kind", None) if result is not None else None
            execute_failed = (
                code not in (0, None)
                or ek
                in {
                    ExitKind.timeout.value,
                    ExitKind.internal_error.value,
                    ExitKind.malformed_model_output.value,
                    ExitKind.blocked_by_quality.value,
                    ExitKind.blocked_by_prereq.value,
                }
            )
            made_progress = (
                last_execute_progress is not None
                and progress_sig > last_execute_progress
            )
            if made_progress or not execute_failed:
                # Forward progress (or a clean execute) — the current model is
                # working; reset the streak so we don't escalate prematurely.
                if execute_fail_streak:
                    log(
                        "execute made progress — resetting escalate-up failure "
                        f"streak (was {execute_fail_streak})",
                        execute_fail_streak=execute_fail_streak,
                    )
                execute_fail_streak = 0
            else:
                execute_fail_streak += 1
                log(
                    f"execute failed — escalate-up streak {execute_fail_streak}"
                    f"/{escalate_after_fails}",
                    execute_fail_streak=execute_fail_streak,
                    escalate_after_fails=escalate_after_fails,
                )
                if (
                    escalate_after_fails > 0
                    and execute_fail_streak >= escalate_after_fails
                ):
                    ladder = _read_execute_tier_ladder(plan_dir)
                    # Baseline tier to escalate *above*: the highest tier the
                    # failing execute actually routed to, unless we have
                    # already climbed higher via a prior escalation.
                    observed_tier = _latest_execute_max_tier(plan_dir)
                    baseline_tier = escalation_tier_pin
                    if baseline_tier is None:
                        baseline_tier = observed_tier
                    elif observed_tier is not None:
                        baseline_tier = max(baseline_tier, observed_tier)
                    nxt = _next_escalation_tier(ladder, current_tier=baseline_tier)
                    if nxt is None:
                        # At the ceiling / no distinct stronger model / not
                        # tier-routed — nothing to escalate to. Leave the streak
                        # to feed the existing state-stall manual_review halt
                        # (the genuine last resort).
                        log(
                            "execute at escalation ceiling (no more-capable "
                            "distinct tier model) — deferring to state-stall "
                            "manual_review halt",
                            escalation_tier_pin=escalation_tier_pin,
                            baseline_tier=baseline_tier,
                        )
                    else:
                        new_tier, new_spec = nxt
                        from_spec = (
                            escalation_pin_spec
                            if escalation_pin_spec is not None
                            else (
                                ladder.get(baseline_tier)
                                if baseline_tier is not None
                                else None
                            )
                        )
                        tier_escalations_used += 1
                        log(
                            f"escalating execute UP: tier {baseline_tier}→{new_tier} "
                            f"({from_spec}→{new_spec}) after "
                            f"{execute_fail_streak} consecutive failures — "
                            "next execute will run fresh on the stronger model",
                            from_tier=baseline_tier,
                            to_tier=new_tier,
                            from_spec=from_spec,
                            to_spec=new_spec,
                            execute_fail_streak=execute_fail_streak,
                            tier_escalations_used=tier_escalations_used,
                        )
                        if plan_dir is not None:
                            try:
                                emit_event(
                                    EventKind.TIER_ESCALATED,
                                    plan_dir=plan_dir,
                                    phase="execute",
                                    payload={
                                        "from_tier": baseline_tier,
                                        "to_tier": new_tier,
                                        "from_model": from_spec,
                                        "to_model": new_spec,
                                        "failure_count": execute_fail_streak,
                                        "escalations_used": tier_escalations_used,
                                    },
                                )
                            except Exception:
                                _warn_best_effort_emit_failure(
                                    "M3A_WARN_EMIT_AUTO_TIER_ESCALATED",
                                    action="auto-tier-escalated",
                                    plan_dir=plan_dir,
                                    phase="execute",
                                    event_kind="tier_escalated",
                                    context={
                                        "from_tier": baseline_tier,
                                        "to_tier": new_tier,
                                    },
                                )
                        escalation_tier_pin = new_tier
                        escalation_pin_spec = new_spec
                        # Reset the streak: the next execute gets a fresh budget
                        # on the stronger model before we consider climbing more.
                        execute_fail_streak = 0
            last_execute_progress = progress_sig
        elif _resolve_phase_name(next_step) in PHASE_NAMES:
            # Moving off execute to another phase — the execute failure streak
            # is per-execute and must not leak across phases.
            execute_fail_streak = 0

        if poll_sleep > 0:
            time.sleep(poll_sleep)

        # Emit phase_end after phase completes
        if plan_dir is not None and last_phase:
            try:
                emit_event(EventKind.PHASE_END, plan_dir=plan_dir, phase=last_phase, payload={"phase": last_phase})
            except Exception:
                _warn_best_effort_emit_failure(
                    "M3A_WARN_EMIT_AUTO_PHASE_END",
                    action="auto-phase-end",
                    plan_dir=plan_dir,
                    phase=last_phase,
                    event_kind="phase_end",
                )

    # Hit iteration cap.
    log(f"hit max_iterations={max_iterations}")
    resume_cursor = _failure_resume_cursor_for_step(
        last_phase or "status",
        plan_dir=plan_dir,
    )
    _record_failure(
        plan_dir=plan_dir,
        kind="iteration_cap",
        message=f"exceeded max_iterations={max_iterations}",
        current_state=None,
        phase=last_phase,
        resume_cursor={**resume_cursor, "retry_strategy": "manual_review"},
        suggested_action="Review automation progress before resuming.",
        metadata={"max_iterations": max_iterations},
    )
    return _outcome(
        "cap",
        final_state=last_state or "unknown",
        iterations=max_iterations,
        reason=f"exceeded max_iterations={max_iterations}",
        last_phase=last_phase,
    )


def build_auto_parser(subparsers: Any) -> None:
    auto_parser = subparsers.add_parser(
        "auto",
        help="Drive a plan to completion without human intervention",
    )
    auto_parser.add_argument("--plan", required=True, help="Plan name")
    auto_parser.add_argument("--project-dir", default=None)
    auto_parser.add_argument(
        "--stall-threshold",
        type=int,
        default=DEFAULT_STALL_THRESHOLD,
        help=(
            f"Exit if the plan state doesn't change for this many iterations "
            f"AND no new review.json has been written (default "
            f"{DEFAULT_STALL_THRESHOLD}). Use --max-review-rework-cycles for "
            "the rework-loop limit — execute rework can span many iterations "
            "with state pinned at 'finalized', which is not a real stall."
        ),
    )
    auto_parser.add_argument(
        "--max-iterations",
        type=int,
        default=DEFAULT_MAX_ITERATIONS,
        help=f"Hard cap on loop iterations (default {DEFAULT_MAX_ITERATIONS})",
    )
    auto_parser.add_argument(
        "--max-review-rework-cycles",
        type=int,
        default=DEFAULT_MAX_REVIEW_REWORK_CYCLES,
        help=(
            f"Cap on observed review→rework cycles before the driver bails "
            f"(default {DEFAULT_MAX_REVIEW_REWORK_CYCLES}). A rework cycle is "
            "counted each time review.json is rewritten while state appears "
            "stuck at 'finalized'. Mirrors execution.max_review_rework_cycles."
        ),
    )
    auto_parser.add_argument(
        "--max-cost-usd",
        type=_non_negative_float,
        default=None,
        help=(
            "Abort automation after cumulative state history cost exceeds this "
            "USD cap. The check runs after each phase completes (default no cap)."
        ),
    )
    auto_parser.add_argument(
        "--max-context-retries",
        type=_non_negative_int,
        default=DEFAULT_MAX_CONTEXT_RETRIES,
        help=(
            f"Fresh execute retries to allow after Codex context-window "
            f"exhaustion (default {DEFAULT_MAX_CONTEXT_RETRIES}; 0 disables)."
        ),
    )
    auto_parser.add_argument(
        "--max-external-retries",
        type=_non_negative_int,
        default=DEFAULT_MAX_EXTERNAL_RETRIES,
        help=(
            f"Fresh non-execute phase retries to allow after retryable external "
            f"stream stalls or timeout-shaped network errors (default "
            f"{DEFAULT_MAX_EXTERNAL_RETRIES}; 0 disables)."
        ),
    )
    auto_parser.add_argument(
        "--phase-model",
        action="append",
        default=None,
        help=(
            "Live phase routing override forwarded to phase subprocesses, "
            "for example --phase-model execute=hermes:deepseek:deepseek-v4-pro."
        ),
    )
    auto_parser.add_argument(
        "--max-blocked-retries",
        type=_non_negative_int,
        default=DEFAULT_MAX_BLOCKED_RETRIES,
        help=(
            f"How many times to retry execute after the worker reports "
            f"result=blocked (e.g. done tasks missing files_changed) before "
            f"bailing with worker_blocked (default {DEFAULT_MAX_BLOCKED_RETRIES})."
        ),
    )
    auto_parser.add_argument(
        "--max-add-note-attempts",
        type=_non_negative_int,
        default=DEFAULT_MAX_ADD_NOTE_ATTEMPTS,
        help=(
            f"Consecutive `override add-note` failures to tolerate before "
            f"escalating to `override force-proceed` (default "
            f"{DEFAULT_MAX_ADD_NOTE_ATTEMPTS}). The driver synthesizes a "
            "note from the latest gate signals; the cap protects against "
            "loops where add-note itself keeps failing."
        ),
    )
    auto_parser.add_argument(
        "--max-repeated-failure-signatures",
        type=_non_negative_int,
        default=DEFAULT_MAX_REPEATED_FAILURE_SIGNATURES,
        help=(
            "Consecutive observations of the same semantic failure before "
            "bailing to repair instead of spending another revise loop "
            f"(default {DEFAULT_MAX_REPEATED_FAILURE_SIGNATURES}; 0 disables)."
        ),
    )
    auto_parser.add_argument(
        "--escalate-after-fails",
        type=_non_negative_int,
        default=DEFAULT_ESCALATE_AFTER_FAILS,
        help=(
            f"Consecutive execute failures (with no forward progress) before "
            f"the driver escalates UP to the next more-capable distinct model "
            f"in tier_models.execute and retries with a fresh session "
            f"(default {DEFAULT_ESCALATE_AFTER_FAILS}; 0 disables). It keeps "
            "climbing on further failures and caps at the most powerful "
            "distinct tier; once at that ceiling and still failing, control "
            "falls through to the state-stall manual_review halt. No-ops on "
            "runs without tier_models.execute."
        ),
    )
    auto_parser.add_argument(
        "--on-escalate",
        choices=ESCALATE_ACTIONS,
        default="force-proceed",
        help="What to do when the gate escalates (default force-proceed)",
    )
    auto_parser.add_argument(
        "--poll-sleep",
        type=float,
        default=DEFAULT_POLL_SLEEP_SECONDS,
        help=f"Seconds to sleep between phase transitions (default {DEFAULT_POLL_SLEEP_SECONDS})",
    )
    auto_parser.add_argument(
        "--phase-timeout",
        type=float,
        default=DEFAULT_PHASE_TIMEOUT_SECONDS,
        help=(
            f"Seconds before a single phase subprocess (plan/prep/critique/gate/finalize/execute/review) "
            f"is killed and treated as a failure (default {DEFAULT_PHASE_TIMEOUT_SECONDS}s). "
            "Stall detection still applies on top."
        ),
    )
    auto_parser.add_argument(
        "--phase-idle-timeout",
        type=float,
        default=DEFAULT_PHASE_IDLE_TIMEOUT_SECONDS,
        help=(
            f"Seconds without stdout/stderr from a phase subprocess before auto kills it "
            f"as idle (default {DEFAULT_PHASE_IDLE_TIMEOUT_SECONDS}s; set 0 to disable)."
        ),
    )
    auto_parser.add_argument(
        "--work-dir",
        default=None,
        help=(
            "Override the source-code working directory for subprocess workers "
            "(--add-dir / -C). Defaults to the current working directory."
        ),
    )
    auto_parser.add_argument(
        "--status-timeout",
        type=float,
        default=DEFAULT_STATUS_TIMEOUT_SECONDS,
        help=(
            f"Seconds before `megaplan status` / override subprocesses are killed "
            f"(default {DEFAULT_STATUS_TIMEOUT_SECONDS}s). These should always be quick; "
            "hitting this indicates serious trouble."
        ),
    )
    auto_parser.add_argument(
        "--outcome-file",
        default=None,
        help="Write the final DriverOutcome JSON to this path atomically before stdout.",
    )
    auto_parser.add_argument(
        "--no-push",
        action="store_true",
        help=(
            "Disable the default post-done branch commit/push publish step. "
            "Use for local/no-network runs."
        ),
    )
    auto_parser.add_argument(
        "--publish-branch",
        default=None,
        help=(
            "Branch name for the post-done publish step. Defaults to "
            "`megaplan/<plan>`."
        ),
    )


def _atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
        delete=False,
    ) as handle:
        tmp_path = Path(handle.name)
        handle.write(text)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(tmp_path, path)


def _apply_local_auto_engine_default(root: Path, plan: str) -> tuple[str | None, bool]:
    from arnold_pipelines.megaplan.runtime.engine_isolation import (
        default_provider_for_local_auto,
    )
    from arnold_pipelines.megaplan.runtime.execution_environment import (
        resolve_execution_environment,
    )

    plan_dir = _resolve_plan_dir(plan, root)
    if plan_dir is None:
        return None, False
    state_path = plan_dir / "state.json"
    try:
        state = json.loads(state_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None, False
    if not isinstance(state, dict):
        return None, False

    env = resolve_execution_environment(root=root, state=state)
    proof = default_provider_for_local_auto(env)
    if proof is None:
        return None, False

    meta = state.setdefault("meta", {})
    if not isinstance(meta, dict):
        meta = {}
        state["meta"] = meta
    meta["engine_isolation_auto_default"] = {
        "provider": proof.provider,
        "proof": proof.to_dict(),
    }
    write_plan_state(plan_dir, mode="replace", state=state)
    os.environ["MEGAPLAN_ENGINE_ISOLATION_PROVIDER"] = proof.provider
    return proof.provider, True


def run_auto(root: Path, args: argparse.Namespace) -> int:
    """CLI entry point. Returns a POSIX exit code suitable for ``sys.exit``."""
    from arnold_pipelines.megaplan.orchestration.progress import ProgressContext

    progress_context = ProgressContext.from_env()
    progress_env = progress_context.to_env() if progress_context is not None else None
    raw_phase_idle_timeout = getattr(
        args,
        "phase_idle_timeout",
        DEFAULT_PHASE_IDLE_TIMEOUT_SECONDS,
    )
    previous_provider = os.environ.get("MEGAPLAN_ENGINE_ISOLATION_PROVIDER")
    _provider, provider_was_set = _apply_local_auto_engine_default(root, args.plan)
    try:
        outcome = drive(
            args.plan,
            cwd=root,
            stall_threshold=args.stall_threshold,
            max_iterations=args.max_iterations,
            max_review_rework_cycles=args.max_review_rework_cycles,
            max_cost_usd=args.max_cost_usd,
            max_context_retries=args.max_context_retries,
            max_external_retries=getattr(
                args,
                "max_external_retries",
                DEFAULT_MAX_EXTERNAL_RETRIES,
            ),
            max_blocked_retries=args.max_blocked_retries,
            max_add_note_attempts=args.max_add_note_attempts,
            max_repeated_failure_signatures=getattr(
                args,
                "max_repeated_failure_signatures",
                DEFAULT_MAX_REPEATED_FAILURE_SIGNATURES,
            ),
            escalate_after_fails=getattr(
                args,
                "escalate_after_fails",
                DEFAULT_ESCALATE_AFTER_FAILS,
            ),
            on_escalate=args.on_escalate,
            poll_sleep=args.poll_sleep,
            phase_timeout=args.phase_timeout,
            phase_idle_timeout=(None if raw_phase_idle_timeout == 0 else raw_phase_idle_timeout),
            status_timeout=args.status_timeout,
            push=not getattr(args, "no_push", False),
            publish_branch=getattr(args, "publish_branch", None),
            phase_model=getattr(args, "phase_model", None),
            progress_env=progress_env,
        )
    finally:
        if provider_was_set:
            if previous_provider is None:
                os.environ.pop("MEGAPLAN_ENGINE_ISOLATION_PROVIDER", None)
            else:
                os.environ["MEGAPLAN_ENGINE_ISOLATION_PROVIDER"] = previous_provider
    outcome_json = outcome.to_json()
    if args.outcome_file:
        _atomic_write_text(Path(args.outcome_file), outcome_json)
    sys.stdout.write(outcome_json + "\n")
    # Exit codes: 0 done/aborted/cancelled/paused, 1 failed/unknown,
    # 2 stalled, 3 escalated, 4 iteration cap, 5 blocked, 6 cost cap exceeded,
    # 7 context retry exhausted, 8 worker_blocked, 9 infrastructure/preflight.
    if outcome.status == "done":
        return 0
    if outcome.status in {"aborted", "cancelled", "paused"}:
        return 0  # user-requested/non-running stops are not phase failures
    if outcome.status == "stalled":
        return 2
    if outcome.status == "escalated":
        return 3
    if outcome.status == "cap":
        return 4
    if outcome.status == "blocked":
        return 5
    if outcome.status == "cost_cap_exceeded":
        return 6
    if outcome.status == "context_retry_exhausted":
        return 7
    if outcome.status == "worker_blocked":
        return 8
    if outcome.status == "infrastructure_error":
        return 9
    return 1


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint for the auto driver."""

    parser = argparse.ArgumentParser(prog="megaplan auto")

    class _StandaloneSubparsers:
        def add_parser(self, *_args: Any, **_kwargs: Any) -> argparse.ArgumentParser:
            return parser

    build_auto_parser(_StandaloneSubparsers())
    args = parser.parse_args(argv)
    return run_auto(Path.cwd(), args)
