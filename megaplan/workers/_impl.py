"""Worker orchestration: running Claude and Codex steps."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import textwrap
import threading
import time
import uuid
from contextvars import ContextVar
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from megaplan.audits.robustness import build_empty_template
from megaplan.forms.provocations import select_active_checks
from megaplan.schemas import SCHEMAS, get_execution_schema_key
from megaplan.orchestration.progress import strip_progress_env
from megaplan.types import (
    AgentMode,
    CliError,
    DEFAULT_AGENT_ROUTING,
    MOCK_ENV_VAR,
    PlanState,
    SessionInfo,
    parse_agent_spec,
    resolved_default_model_for_agent,
)
from megaplan._core import (
    apply_session_update,
    configured_robustness,
    creative_form_id,
    detect_available_agents,
    phase_timeout_seconds,
    get_effective,
    json_dump,
    latest_plan_meta_path,
    load_config,
    now_utc,
    read_json,
    schemas_root,
    touch_active_step,
)
from megaplan.prompts import (
    create_claude_prompt,
    create_codex_prompt,
    create_hermes_prompt,
    _resolve_prompt_root,
)
from megaplan.runtime.process import TmuxSession, kill_group, spawn


_EXECUTE_STEPS = {"execute", "loop_execute"}
_CROSS_CALL_PERSISTENT_STEPS = _EXECUTE_STEPS
_CODEX_TEMPLATE_WRITE_STEPS = {"critique", "review"}

# Shared mapping from step name to schema filename, used by both
# run_claude_step and run_codex_step.
STEP_SCHEMA_FILENAMES: dict[str, str] = {
    "plan": "plan.json",
    "prep": "prep.json",
    "revise": "revise.json",
    "critique": "critique.json",
    "feedback": "feedback.json",
    "gate": "gate.json",
    "finalize": "finalize.json",
    "execute": "execution.json",
    "loop_plan": "loop_plan.json",
    "loop_execute": "loop_execute.json",
    "review": "review.json",
    "tiebreaker_researcher": "tiebreaker_researcher.json",
    "tiebreaker_challenger": "tiebreaker_challenger.json",
}

# Derive required keys per step from SCHEMAS so they aren't duplicated.
_STEP_REQUIRED_KEYS: dict[str, list[str]] = {
    step: SCHEMAS[filename].get("required", [])
    for step, filename in STEP_SCHEMA_FILENAMES.items()
}


@dataclass
class CommandResult:
    command: list[str]
    cwd: Path
    returncode: int
    stdout: str
    stderr: str
    duration_ms: int


# Per-turn duration cap for the shannon worker (Claude via the shannon CLI).
#
# IMPORTANT — why this is a coarse DURATION cap, not a true inter-chunk idle
# bound (empirically established 2026-05-24): shannon does NOT passthrough
# Claude's token stream. It drives Claude in a tmux session and reconstructs
# output by polling Claude's transcript .jsonl, emitting to its OWN stdout only
# at turn start (init) and turn end (result). And the transcript file itself is
# written one row per COMPLETED content block — it stays byte-static for the
# entire duration of a single long thinking/answer block. So during a long
# single-block Opus turn there is NO incremental signal on stdout OR the
# transcript (the only token-by-token signal is the live tmux pane). An
# "inter-chunk inactivity" bound therefore degenerates into a total-turn
# duration cap for shannon: the timer effectively counts turn-start → turn-end.
#
# Consequence: this value must exceed the longest LEGITIMATE single turn (real
# transcripts show within-turn gaps up to ~363s) while still catching the
# original failure mode (a genuinely hung turn that would otherwise run until the
# ~30m+ phase wall-clock and fail the whole plan). 900s gives ~2.5x headroom over
# observed legit turns and still kills an infinite hang at 15 min, well inside
# the phase cap. Override via SHANNON_STREAM_READ_TIMEOUT.
# (A true fine-grained liveness signal would require scraping the tmux pane —
# deliberately NOT done; a duration cap is the honest mechanism for a worker with
# no incremental output. The hermes path, which DOES stream real SSE chunks, uses
# a genuine inter-chunk bound — HERMES_STREAM_READ_TIMEOUT — and is unaffected.)
DEFAULT_WORKER_STREAM_IDLE_TIMEOUT_SECONDS = 900.0
DEFAULT_CODEX_EXECUTOR_SESSION_HEADROOM_TOKENS = 80_000_000
CODEX_EXECUTOR_SESSION_HEADROOM_ENV = "MEGAPLAN_CODEX_EXECUTOR_SESSION_HEADROOM_TOKENS"


def _worker_stream_idle_timeout_seconds() -> float:
    """Per-turn duration cap (seconds) for the shannon worker.

    Because shannon emits no incremental stdout/transcript signal within a
    content block (see the module comment above), this bound functions as a
    total-turn duration cap, not a true inter-chunk idle bound. Configurable via
    ``SHANNON_STREAM_READ_TIMEOUT``. Defaults to 15 min — generous for the
    longest legitimate Opus turn (~363s observed) while still catching a hung
    turn well before the coarse phase wall-clock. Clamped to a sane floor.
    """
    try:
        value = float(os.getenv(
            "SHANNON_STREAM_READ_TIMEOUT",
            DEFAULT_WORKER_STREAM_IDLE_TIMEOUT_SECONDS,
        ))
    except (TypeError, ValueError):
        value = DEFAULT_WORKER_STREAM_IDLE_TIMEOUT_SECONDS
    # Never allow a sub-30s idle bound that could abort a healthy slow tool turn.
    return max(value, 30.0)


def _codex_executor_session_headroom_tokens() -> int:
    raw = os.getenv(CODEX_EXECUTOR_SESSION_HEADROOM_ENV)
    if raw is None:
        return DEFAULT_CODEX_EXECUTOR_SESSION_HEADROOM_TOKENS
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return DEFAULT_CODEX_EXECUTOR_SESSION_HEADROOM_TOKENS
    return max(value, 0)


def _codex_total_tokens_from_session(session: dict[str, Any]) -> int | None:
    usage = session.get("last_total_tokens")
    if not isinstance(usage, dict):
        return None
    total = usage.get("total_tokens")
    if total is None:
        total = sum(
            int(usage.get(key, 0) or 0)
            for key in (
                "input_tokens",
                "output_tokens",
                "reasoning_output_tokens",
            )
        )
    try:
        return int(total)
    except (TypeError, ValueError):
        return None


@dataclass
class WorkerResult:
    payload: dict[str, Any]
    raw_output: str
    duration_ms: int
    cost_usd: float
    session_id: str | None = None
    trace_output: str | None = None
    rendered_prompt: str | None = None
    model_actual: str | None = None
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


# ---------------------------------------------------------------------------
# Worker working directory resolution (git-worktree isolation)
#
# When megaplan is invoked from a git worktree, the plan's stored project_dir
# may point at a *different* checkout (usually the main repo). To avoid
# subprocess workers writing source code into the wrong working tree, resolve
# the "working directory" at CLI entry (CWD, or an explicit --work-dir
# override) and pass *that* through to the worker's --add-dir / -C flags.
#
# Plan state files (.megaplan/plans/...) still live under project_dir; only
# the source-code working tree tracked by the subprocess changes.
# ---------------------------------------------------------------------------

_WORK_DIR_OVERRIDE: ContextVar[Path | None] = ContextVar(
    "megaplan_work_dir_override", default=None
)
_WORK_DIR_WARNED: set[Path] = set()
_WORK_DIR_WARNED_LOCK = threading.Lock()


def set_work_dir_override(path: Path | str | None) -> None:
    """Set an explicit working directory for subprocess workers.

    Typically called once from the CLI entry point with either an explicit
    --work-dir value or ``Path.cwd()``. Pass ``None`` to clear the override
    (primarily useful in tests).

    Sets the ContextVar for the current context.
    """
    _WORK_DIR_OVERRIDE.set(Path(path) if path is not None else None)


def resolve_work_dir(state: PlanState) -> Path:
    """Return the source-code working directory for worker subprocesses.

    Precedence:
    1. Explicit override set via :func:`set_work_dir_override` (e.g. from the
       CLI ``--work-dir`` flag).
    2. The plan's stored ``project_dir`` (persisted at ``megaplan init``).
    3. Current working directory (``Path.cwd()``) as a last-resort fallback
       when the plan has no ``project_dir`` recorded.

    If the resolved path differs from the plan's stored ``project_dir``, a
    one-time informational line is printed so operators notice worktree
    divergence. (Callers that want a visually-loud operator warning should
    invoke :func:`warn_if_work_dir_differs_from_project_dir` from the phase
    entry point — this function keeps the log terse because it fires on every
    worker invocation.)
    """
    try:
        project_dir = Path(state["config"]["project_dir"]).resolve()
    except Exception:
        project_dir = None
    override = _WORK_DIR_OVERRIDE.get()
    if override is not None:
        work_dir = override
    elif project_dir is not None:
        work_dir = project_dir
    else:
        work_dir = Path.cwd()
    try:
        resolved_work = work_dir.resolve()
    except Exception:
        resolved_work = work_dir
    if project_dir is not None and resolved_work != project_dir:
        with _WORK_DIR_WARNED_LOCK:
            if resolved_work not in _WORK_DIR_WARNED:
                _WORK_DIR_WARNED.add(resolved_work)
                print(
                    f"[megaplan] Using plan's project_dir ({project_dir}) for "
                    f"subprocess --add-dir. Override with --work-dir if needed.",
                    flush=True,
                )
    return work_dir


def warn_if_work_dir_differs_from_project_dir(state: PlanState) -> None:
    """Emit a visible WARNING if the resolved work_dir is narrower than the
    plan's stored ``project_dir``.

    Intended to be called at the top of any phase that spawns sandboxed
    subprocess workers (execute, review, etc.). The warning alerts the
    operator that codex will be sandboxed to a subset of the project tree,
    which silently breaks writes to sibling subrepos.
    """
    try:
        project_dir = Path(state["config"]["project_dir"]).resolve()
    except Exception:
        return
    work_dir = resolve_work_dir(state)
    try:
        resolved_work = work_dir.resolve()
    except Exception:
        resolved_work = work_dir
    if resolved_work == project_dir:
        return
    try:
        cwd = Path.cwd().resolve()
    except Exception:
        cwd = Path.cwd()
    # ANSI bold yellow + warning emoji for visual distinction. Printed to
    # stderr so it is not swallowed by output redirection of the primary
    # response payload.
    prefix = "\033[1;33m" if sys.stderr.isatty() else ""
    suffix = "\033[0m" if sys.stderr.isatty() else ""
    message = (
        f"{prefix}⚠️  WARNING: codex will be sandboxed to {resolved_work}, "
        f"but the plan's project_dir is {project_dir}. File writes outside "
        f"{resolved_work} will fail. Pass --work-dir {project_dir} or cd to "
        f"{project_dir} to match the plan.{suffix}"
    )
    # CWD context helps the operator see *why* work_dir ended up narrower.
    if cwd != project_dir and cwd != resolved_work:
        message += f"\n[megaplan] (current shell cwd: {cwd})"
    print(message, file=sys.stderr, flush=True)





def run_command(
    command: list[str],
    *,
    cwd: Path,
    stdin_text: str | None = None,
    env: dict[str, str] | None = None,
    timeout: int | None = None,
    activity_callback: Callable[[str, str], None] | None = None,
    idle_timeout: float | None = None,
    tmux_session: TmuxSession | None = None,
) -> CommandResult:
    try:
        started = time.monotonic()
        timeout = timeout or get_effective("execution", "worker_timeout_seconds")
        if activity_callback is None:
            try:
                process = subprocess.run(
                    command,
                    input=stdin_text,
                    text=True,
                    cwd=str(cwd),
                    capture_output=True,
                    timeout=timeout,
                    env=env,
                )
            except subprocess.TimeoutExpired as exc:
                def _coerce_timeout_output(value: str | bytes | None) -> str:
                    if value is None:
                        return ""
                    if isinstance(value, bytes):
                        return value.decode("utf-8", errors="replace")
                    return value

                raise CliError(
                    "worker_timeout",
                    f"Command timed out after {timeout}s: {' '.join(command[:3])}...",
                    extra={
                        "raw_output": _coerce_timeout_output(exc.output)
                        + _coerce_timeout_output(exc.stderr)
                    },
                ) from exc
            except FileNotFoundError as exc:
                raise CliError(
                    "agent_not_found",
                    f"Command not found: {command[0]}",
                ) from exc
            return CommandResult(
                command=command,
                cwd=cwd,
                returncode=process.returncode,
                stdout=process.stdout or "",
                stderr=process.stderr or "",
                duration_ms=int((time.monotonic() - started) * 1000),
            )

        try:
            process = spawn(
                command,
                cwd=str(cwd),
                stdin=subprocess.PIPE if stdin_text is not None else None,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=env,
            )
            stdout_parts: list[bytes] = []
            stderr_parts: list[bytes] = []

            # Idle-output watchdog state. Updated ONLY on real stdout/stderr chunks
            # (never by the liveness heartbeat) so a stalled-but-alive subprocess is
            # detected while a healthy, actively-streaming call keeps resetting it.
            # ``last_output`` is a single-element list so the reader closures can
            # mutate it without a nonlocal declaration.
            last_output = [time.monotonic()]

            def _reader(stream: Any, parts: list[bytes], kind: str) -> None:
                if stream is None:
                    return
                # Use read1() so we deliver bytes as soon as the OS makes them
                # available (one underlying read) rather than blocking until a full
                # 4096-byte buffer fills. The plain read(4096) would not return until
                # the pipe accumulated 4096 bytes OR closed, so a worker streaming
                # small frames (e.g. shannon JSON deltas) would surface NO activity
                # mid-stream — both starving the liveness/activity callback and
                # hiding genuine progress from the idle-output watchdog below.
                # read1() falls back to read() for any stream lacking it.
                reader = getattr(stream, "read1", None) or stream.read
                while True:
                    chunk = reader(4096)
                    if not chunk:
                        break
                    last_output[0] = time.monotonic()
                    parts.append(chunk)
                    if activity_callback is not None:
                        activity_callback(kind, chunk.decode("utf-8", errors="replace"))

            threads = [
                threading.Thread(target=_reader, args=(process.stdout, stdout_parts, "stdout"), daemon=True),
                threading.Thread(target=_reader, args=(process.stderr, stderr_parts, "stderr"), daemon=True),
            ]
            # Liveness heartbeat: some subprocess workers (notably ``codex exec``)
            # can run a single long task while emitting nothing on stdout/stderr for
            # many minutes — a tool turn or a stalled-then-resuming network call.
            # The reader-driven ``activity_callback`` only fires on output, so a
            # provably-alive worker would otherwise look idle and trip the outer
            # `megaplan auto` idle-timeout, killing the whole phase. Emit a periodic
            # liveness signal while the process is alive so that watchdog sees a
            # heartbeat. The callback is rate-limited and routes to
            # ``touch_active_step`` (bumping state.json mtime, which the auto driver
            # recognizes as activity); this is a no-op for the in-process hermes path
            # and for any worker whose activity_callback is None.
            heartbeat_stop = threading.Event()

            def _heartbeat() -> None:
                while not heartbeat_stop.wait(5.0):
                    if process.poll() is not None:
                        return
                    try:
                        activity_callback("liveness", "worker subprocess alive")
                    except Exception:
                        pass

            threads.append(threading.Thread(target=_heartbeat, daemon=True))
            for thread in threads:
                thread.start()
            if process.stdin is not None and stdin_text is not None:
                process.stdin.write(stdin_text.encode("utf-8"))
                process.stdin.close()

            def _coerce_timeout_output(parts: list[bytes]) -> str:
                return b"".join(parts).decode("utf-8", errors="replace")

            # When the caller opts in to the idle-output watchdog (e.g. the shannon
            # worker), poll process.wait() in short slices so we can also enforce the
            # inter-chunk inactivity bound between slices. When idle_timeout is None
            # (codex/claude paths), this collapses to the original single
            # process.wait(timeout=timeout) — no behavioral change for those callers.
            if idle_timeout is not None:
                deadline = started + timeout
                try:
                    while True:
                        remaining = deadline - time.monotonic()
                        if remaining <= 0:
                            raise subprocess.TimeoutExpired(command, timeout)
                        try:
                            returncode = process.wait(timeout=min(1.0, remaining))
                            break
                        except subprocess.TimeoutExpired:
                            # Still running: check the idle-output bound. Only real
                            # stdout/stderr resets last_output; the heartbeat does not.
                            if time.monotonic() - last_output[0] > idle_timeout:
                                kill_group(process)
                                returncode = process.poll() if process.poll() is not None else -1
                                heartbeat_stop.set()
                                for thread in threads:
                                    thread.join(timeout=1)
                                raise CliError(
                                    "worker_stall",
                                    (
                                        f"Worker produced no output for {idle_timeout:.0f}s "
                                        f"(stalled stream): {' '.join(command[:3])}..."
                                    ),
                                    extra={
                                        "raw_output": _coerce_timeout_output(stdout_parts)
                                        + _coerce_timeout_output(stderr_parts)
                                    },
                                )
                            continue
                except subprocess.TimeoutExpired as exc:
                    kill_group(process)
                    returncode = process.poll() if process.poll() is not None else -1
                    heartbeat_stop.set()
                    for thread in threads:
                        thread.join(timeout=1)
                    raise CliError(
                        "worker_timeout",
                        f"Command timed out after {timeout}s: {' '.join(command[:3])}...",
                        extra={"raw_output": _coerce_timeout_output(stdout_parts) + _coerce_timeout_output(stderr_parts)},
                    ) from exc
            else:
                try:
                    returncode = process.wait(timeout=timeout)
                except subprocess.TimeoutExpired as exc:
                    kill_group(process)
                    returncode = process.poll() if process.poll() is not None else -1
                    heartbeat_stop.set()
                    for thread in threads:
                        thread.join(timeout=1)
                    raise CliError(
                        "worker_timeout",
                        f"Command timed out after {timeout}s: {' '.join(command[:3])}...",
                        extra={"raw_output": _coerce_timeout_output(stdout_parts) + _coerce_timeout_output(stderr_parts)},
                    ) from exc
            heartbeat_stop.set()
            for thread in threads:
                thread.join(timeout=1)
        except FileNotFoundError as exc:
            raise CliError(
                "agent_not_found",
                f"Command not found: {command[0]}",
            ) from exc
        return CommandResult(
            command=command,
            cwd=cwd,
            returncode=returncode,
            stdout=b"".join(stdout_parts).decode("utf-8", errors="replace"),
            stderr=b"".join(stderr_parts).decode("utf-8", errors="replace"),
            duration_ms=int((time.monotonic() - started) * 1000),
        )
    finally:
        if tmux_session:
            tmux_session.teardown()


def _activity_callback_for_state(state: PlanState, plan_dir: Path) -> Callable[[str, str], None] | None:
    active_step = state.get("active_step")
    if not isinstance(active_step, dict):
        return None
    run_id = active_step.get("run_id")
    if not isinstance(run_id, str) or not run_id:
        return None
    last_touch = 0.0

    def _callback(kind: str, detail: str) -> None:
        nonlocal last_touch
        now = time.monotonic()
        if now - last_touch < 2.0:
            return
        last_touch = now
        touch_active_step(plan_dir, run_id=run_id, kind=kind, detail=detail.strip())

    return _callback


_CODEX_ERROR_PATTERNS: list[tuple[str, str, str]] = [
    # (pattern_substring, error_code, human_message)
    # Keep transport failures ahead of generic HTTP/status matches so
    # thread IDs or unrelated numbers do not get misclassified as 429s.
    ("failed to lookup address information", "connection_error", "Codex could not resolve the backend host"),
    ("failed to connect to websocket", "connection_error", "Codex could not connect to the realtime backend"),
    ("stream disconnected before completion", "connection_error", "Codex connection dropped before completion"),
    ("error sending request for url", "connection_error", "Codex could not send the backend request"),
    ("nodename nor servname provided", "connection_error", "Codex could not resolve the backend host"),
    ("connection error", "connection_error", "Codex could not connect to the API"),
    ("connection refused", "connection_error", "Codex could not connect to the API"),
    ("usage limit", "quota_exceeded", "Codex usage limit reached"),
    ("try again at", "quota_exceeded", "Codex usage limit reached"),
    ("rate limit", "rate_limit", "Codex hit a rate limit"),
    ("rate_limit", "rate_limit", "Codex hit a rate limit"),
    ("quota", "quota_exceeded", "Codex quota exceeded"),
    ("context length", "context_overflow", "Prompt exceeded Codex context length"),
    ("context_length", "context_overflow", "Prompt exceeded Codex context length"),
    ("maximum context", "context_overflow", "Prompt exceeded Codex context length"),
    ("too many tokens", "context_overflow", "Prompt exceeded Codex context length"),
    ("timed out", "worker_timeout", "Codex request timed out"),
    ("timeout", "worker_timeout", "Codex request timed out"),
    ("invalid_json_schema", "schema_error", "Codex request rejected: invalid JSON schema"),
    ("invalid_request_error", "schema_error", "Codex request rejected: invalid request"),
    ("internal server error", "api_error", "Codex API returned an internal error"),
    ("model not found", "model_error", "Codex model not found or unavailable"),
    ("permission denied", "permission_error", "Codex permission denied"),
    ("authentication", "auth_error", "Codex authentication failed"),
    ("unauthorized", "auth_error", "Codex authentication failed"),
]


def _codex_retry_guidance(step: str | None = None) -> str:
    if step in _EXECUTE_STEPS:
        return (
            "Re-run the same execute step on Codex once before changing agent; "
            "preserve the existing session path unless a fresh retry is explicitly needed."
        )
    return "Re-run the same step on Codex once before changing agent."


def _diagnose_codex_failure(raw: str, returncode: int) -> tuple[str, str]:
    """Parse Codex stderr/stdout for known error patterns. Returns (error_code, message)."""
    lower = raw.lower()
    for pattern, code, message in _CODEX_ERROR_PATTERNS:
        if pattern in lower:
            return code, f"{message}. {_codex_retry_guidance()}"
    if re.search(r"\bhttp\s*429\b", lower) or re.search(r"\b429\b", lower):
        return "rate_limit", f"Codex hit a rate limit (HTTP 429). {_codex_retry_guidance()}"
    if re.search(r"\bhttp\s*400\b", lower) or re.search(r"\b400\b", lower):
        return "schema_error", f"Codex API rejected request (HTTP 400). {_codex_retry_guidance()}"
    if re.search(r"\bhttp\s*500\b", lower) or re.search(r"\b500\b", lower):
        return "api_error", f"Codex API returned an internal error (HTTP 500). {_codex_retry_guidance()}"
    if re.search(r"\bhttp\s*502\b", lower) or re.search(r"\b502\b", lower):
        return "api_error", f"Codex API returned a gateway error (HTTP 502). {_codex_retry_guidance()}"
    if re.search(r"\bhttp\s*503\b", lower) or re.search(r"\b503\b", lower):
        return "api_error", f"Codex API service unavailable (HTTP 503). {_codex_retry_guidance()}"
    return "worker_error", (
        f"Codex step failed with exit code {returncode} (no recognized error pattern in output). "
        + _codex_retry_guidance()
    )


def _codex_timeout_for_step(step: str) -> int:
    configured_timeout = int(get_effective("execution", "worker_timeout_seconds"))
    return phase_timeout_seconds(step, configured_timeout_seconds=configured_timeout)


def _codex_exec_mode_flags(step: str) -> list[str]:
    if _trusted_container():
        return []
    # All non-execute phases (plan, prep, critique, revise, gate, finalize,
    # review) need to write template artifacts (plan markdown, metadata JSON,
    # critique/review JSON, finalize.json). Without --full-auto codex defaults
    # to on-request approval, which fails silently when stdin is the prompt
    # (no tty). Default everything to --full-auto and let the workspace-write
    # sandbox plus writable_roots configuration constrain actual writes.
    return ["--full-auto"]


_ROLLOUT_MISSING_PATTERNS = (
    "no rollout found for thread id",
    "thread/resume failed",
)


# Patterns that indicate the worker's *session history* has absorbed an
# obsolete environmental failure (e.g. from an earlier invocation before the
# container was configured for trusted-mode). On a later invocation the model
# reads this history, believes the environment is still broken, and returns
# "blocked" without attempting commands — causing infinite retry loops.
# Detecting these in the raw output and invalidating the session forces a
# fresh start so the belief can't survive.
_POISONED_SESSION_PATTERNS: tuple[tuple[str, ...], ...] = (
    # Single-substring match (any one of these is enough).
    ("bwrap: creating new namespace failed",),
    # Multi-substring match (all substrings must be present).
    ("permission denied", "cannot start sandbox"),
    ("repository command execution", "unavailable", "sandbox"),
    ("permissions profile", "does not define any recognized filesystem entries"),
)


def _is_rollout_missing(raw: str) -> bool:
    """Detect Codex's signal that a session/thread id has no rollout.

    Happens when: container was restarted between phases and codex's session
    store (usually ``$HOME/.codex/sessions``) was wiped, but megaplan's plan
    state still has the session id and tries to ``codex exec resume <id>``.

    Match is case-insensitive on known substrings so minor wording changes
    upstream don't break recovery. Fall back to failing loudly if Codex
    introduces a new error string — false positives here would mask real
    session crashes.
    """
    if not raw:
        return False
    lowered = raw.lower()
    return any(pat in lowered for pat in _ROLLOUT_MISSING_PATTERNS)


def _is_poisoned_environmental_failure(raw: str) -> bool:
    """Detect obsolete sandbox/environment failure beliefs in worker output.

    Returns True when the raw output contains known-stale environment errors
    that a persistent session may have absorbed from a prior invocation
    (before trusted-container mode was enabled). See the comment on
    ``_POISONED_SESSION_PATTERNS`` above for motivation.

    The check is intentionally conservative: every pattern is a conjunction
    of substrings all of which must be present (case-insensitive). A single
    sandbox error combined with a generic "Permission denied" elsewhere in a
    long trace should not trigger unless the full phrase appears.
    """
    if not raw:
        return False
    lowered = raw.lower()
    for group in _POISONED_SESSION_PATTERNS:
        if all(sub in lowered for sub in group):
            return True
    return False


def _is_session_too_large_for_compact(raw: str) -> bool:
    """Detect a Codex session that has grown too large to remote-compact.

    Codex auto-triggers OpenAI's remote-compaction API when the session
    approaches the model's context window. If that compaction call hits a
    rate limit and exhausts its retry budget, codex emits a
    ``remote compact task ... 429 Too Many Requests`` error and exits
    non-zero. ``codex exec resume <session-id>`` will keep replaying the
    same oversized session and hit the same wall — invalidating the
    session and retrying with ``--fresh`` is the only escape.
    """
    if not raw:
        return False
    lowered = raw.lower()
    return "remote compact task" in lowered and "429" in lowered


# System directories that should never be auto-promoted to a writable
# sandbox root. Used by :func:`_auto_writable_roots`. The check below
# matches the resolved path against these roots exactly *and* against
# direct children (e.g. /usr) — we never want to widen the sandbox to
# anything that broad even if the user happens to have project_dir at
# /usr/local/foo.
_AUTO_ROOT_FORBIDDEN: tuple[Path, ...] = (
    Path("/"),
    Path("/usr"),
    Path("/etc"),
    Path("/var"),
    Path("/private"),
    Path("/System"),
    Path("/Library"),
    Path("/bin"),
    Path("/sbin"),
    Path("/opt"),
    Path("/tmp"),
    Path.home(),
)


def _is_safe_auto_root(candidate: Path) -> bool:
    """Return True iff *candidate* is safe to auto-promote to a writable root.

    Excludes (a) system directories, (b) the user's home directory itself
    (granting write to ~ would defeat the sandbox), and (c) any path
    shallower than two levels below root (e.g. ``/Users``, ``/home``).
    """
    try:
        resolved = candidate.resolve()
    except Exception:
        return False
    # Reject filesystem root and very shallow paths.
    if len(resolved.parts) < 3:
        return False
    for forbidden in _AUTO_ROOT_FORBIDDEN:
        try:
            forbidden_resolved = forbidden.resolve()
        except Exception:
            continue
        if resolved == forbidden_resolved:
            return False
    return True


def _auto_writable_roots(work_dir: Path) -> list[str]:
    """Auto-detect additional writable roots that surround *work_dir*.

    Strategy: walk up from *work_dir* looking for a workspace marker — the
    nearest ancestor containing a ``.git`` directory or a sibling
    ``.megaplan/`` directory. If that ancestor is a strict parent of
    *work_dir* and passes :func:`_is_safe_auto_root`, return it as an
    additional writable root.

    This handles the common monorepo / multi-package workspace case where
    ``project_dir`` is a subdirectory (e.g. ``tools/``) but legitimate plan
    output writes to sibling directories (``effects/``, ``themes/``,
    ``animations/``). Without this, codex's ``workspace-write`` sandbox
    blocks those writes with ``sandbox denied creating '../foo' outside the
    writable root``.

    Disable with ``MEGAPLAN_NARROW_SANDBOX=1`` (e.g. for CI runs of
    untrusted plans where the narrow default is the safer choice).
    """
    if os.environ.get("MEGAPLAN_NARROW_SANDBOX", "").strip().lower() in {
        "1", "true", "yes", "on",
    }:
        return []
    try:
        start = Path(work_dir).resolve()
    except Exception:
        return []
    current = start.parent
    seen_root: Path | None = None
    while True:
        if seen_root is None:
            if (current / ".git").exists() or (current / ".megaplan").is_dir():
                seen_root = current
                break
        parent = current.parent
        if parent == current:
            break
        current = parent
    if seen_root is None or seen_root == start:
        return []
    if not _is_safe_auto_root(seen_root):
        return []
    return [str(seen_root)]


def _trusted_container() -> bool:
    """Return True when MEGAPLAN_TRUSTED_CONTAINER is set to a truthy value.

    In a locked-down container (Docker/Railway/Kubernetes without
    user-namespace capabilities), bubblewrap's default sandbox fails with
    ``bwrap: Creating new namespace failed: Permission denied`` because
    ``kernel.unprivileged_userns_clone`` is not settable by an unprivileged
    user. Per the official guidance at
    https://docs.docker.com/ai/sandboxes/agents/codex/ the operator is
    expected to rely on container-level isolation and bypass the Codex
    sandbox entirely. Setting ``MEGAPLAN_TRUSTED_CONTAINER=1`` on the
    worker environment activates that path.
    """
    return os.environ.get("MEGAPLAN_TRUSTED_CONTAINER", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def _sandbox_fingerprint(work_dir: Path | str) -> str:
    """Return a stable hash of the sandbox-affecting inputs for codex.

    Captures every input that would change codex's effective sandbox
    between invocations:

    - ``MEGAPLAN_TRUSTED_CONTAINER`` (toggles ``--dangerously-bypass-...``)
    - ``work_dir`` (appears in ``-C`` and in
      ``sandbox_workspace_write.writable_roots``)

    The hash is stored on each session entry when it is created; at resume
    time we refuse to reuse a session whose fingerprint no longer matches.
    This prevents the silent drift where an operator sets
    ``MEGAPLAN_TRUSTED_CONTAINER=1`` *after* a session was created and
    codex keeps using the locked-in (broken) sandbox forever.
    """
    trusted = "1" if _trusted_container() else "0"
    try:
        work_resolved = str(Path(work_dir).resolve())
    except Exception:
        work_resolved = str(work_dir)
    payload = f"trusted={trusted}\nwork_dir={work_resolved}\n"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def _codex_child_env(
    turn_id: str | None = None,
    actor_id: str | None = None,
) -> dict[str, str]:
    env = strip_progress_env(os.environ.copy())
    # Nested Codex workers should not inherit the parent Codex session state.
    # Those variables can cause the child to attach to the outer thread/CI
    # context instead of behaving like an isolated worker invocation.
    env.pop("CODEX_THREAD_ID", None)
    env.pop("CODEX_CI", None)
    if turn_id is not None:
        env["MEGAPLAN_TURN_ID"] = turn_id
    if actor_id is not None:
        env["MEGAPLAN_ACTOR_ID"] = actor_id
    return env


def _external_worker_env(
    turn_id: str | None = None,
    actor_id: str | None = None,
) -> dict[str, str]:
    env = strip_progress_env(os.environ.copy())
    if turn_id is not None:
        env["MEGAPLAN_TURN_ID"] = turn_id
    if actor_id is not None:
        env["MEGAPLAN_ACTOR_ID"] = actor_id
    return env


def _merge_partial_output(raw_output: str, output_path: Path) -> str:
    merged = raw_output or ""
    try:
        partial = output_path.read_text(encoding="utf-8").strip()
    except (FileNotFoundError, OSError, UnicodeDecodeError):
        partial = ""
    if partial and partial not in merged:
        if merged and not merged.endswith("\n"):
            merged += "\n"
        merged += "[partial_output_file]\n" + partial
    return merged


def _codex_session_jsonl_path(session_id: str) -> Path | None:
    """Locate the rollout JSONL for a given codex session_id.

    Codex stores rollouts at
    ``$CODEX_HOME/sessions/<YYYY>/<MM>/<DD>/rollout-<timestamp>-<session-id>.jsonl``.
    The directory date may not match the call date if a session was created
    earlier and resumed. We glob across all date dirs and return the most
    recently modified match (or ``None`` if none).
    """
    if not session_id:
        return None
    codex_home_str = os.getenv("CODEX_HOME", "").strip() or str(Path.home() / ".codex")
    sessions_root = Path(codex_home_str).expanduser() / "sessions"
    if not sessions_root.is_dir():
        return None
    try:
        matches = list(sessions_root.glob(f"*/*/*/rollout-*-{session_id}.jsonl"))
    except OSError:
        return None
    if not matches:
        return None
    try:
        matches.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    except OSError:
        pass
    return matches[0]


def _read_codex_total_token_usage(jsonl_path: Path) -> dict[str, Any] | None:
    """Read a codex rollout JSONL and return the latest ``total_token_usage``.

    Scans for ``event_msg`` events of type ``token_count`` and returns the
    ``info.total_token_usage`` blob from the last one with non-null ``info``.
    Returns ``None`` if no usable event is found or the file is unreadable.
    Tolerates malformed/non-JSON lines.
    """
    try:
        text = jsonl_path.read_text(encoding="utf-8")
    except (FileNotFoundError, OSError, UnicodeDecodeError):
        return None
    last_usage: dict[str, Any] | None = None
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except (json.JSONDecodeError, ValueError):
            continue
        if not isinstance(obj, dict) or obj.get("type") != "event_msg":
            continue
        payload = obj.get("payload")
        if not isinstance(payload, dict) or payload.get("type") != "token_count":
            continue
        info = payload.get("info")
        if not isinstance(info, dict):
            continue
        usage = info.get("total_token_usage")
        if isinstance(usage, dict):
            last_usage = usage
    return last_usage


def _read_codex_default_model() -> str | None:
    """Best-effort read of the codex CLI default model from ``config.toml``.

    Returns ``None`` if the config is missing or the model field is absent;
    callers should fall back to :data:`codex_pricing.DEFAULT_MODEL` in that
    case. We do a permissive line-based parse to avoid taking a hard
    dependency on a TOML library just for one key.
    """
    codex_home_str = os.getenv("CODEX_HOME", "").strip() or str(Path.home() / ".codex")
    config_path = Path(codex_home_str).expanduser() / "config.toml"
    try:
        text = config_path.read_text(encoding="utf-8")
    except (FileNotFoundError, OSError, UnicodeDecodeError):
        return None
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        # Stop at first table header so we only read top-level model =
        if stripped.startswith("["):
            break
        if "=" not in stripped:
            continue
        key, _, value = stripped.partition("=")
        if key.strip() == "model":
            value = value.strip().split("#", 1)[0].strip()
            return value.strip().strip('"').strip("'") or None
    return None


def _codex_step_cost(
    session_id: str | None,
    session_entry: dict[str, Any],
) -> tuple[float, int, int, str | None, dict[str, Any] | None]:
    """Compute incremental cost (USD) and token deltas for one codex step.

    Looks up the rollout JSONL for ``session_id``, reads the cumulative
    ``total_token_usage``, and subtracts the ``last_total_tokens`` snapshot
    stored on ``session_entry`` (mutated in place to record the new totals).

    Returns ``(cost_usd, prompt_tokens_delta, completion_tokens_delta,
    model, current_total_usage)``. Any failure to read the JSONL or compute
    the delta returns zeros and a ``None`` usage blob — never raises.
    """
    from megaplan.pricing.codex import cost_from_codex_usage_dict

    if not session_id:
        return 0.0, 0, 0, None, None
    path = _codex_session_jsonl_path(session_id)
    if path is None:
        return 0.0, 0, 0, None, None
    current = _read_codex_total_token_usage(path)
    if current is None:
        return 0.0, 0, 0, None, None
    prev = session_entry.get("last_total_tokens") if isinstance(session_entry, dict) else None
    if not isinstance(prev, dict):
        prev = {}

    def _delta(key: str) -> int:
        try:
            cur = int(current.get(key, 0) or 0)
            old = int(prev.get(key, 0) or 0)
        except (TypeError, ValueError):
            return 0
        return max(cur - old, 0)

    delta_usage = {
        "input_tokens": _delta("input_tokens"),
        "cached_input_tokens": _delta("cached_input_tokens"),
        "output_tokens": _delta("output_tokens"),
        "reasoning_output_tokens": _delta("reasoning_output_tokens"),
    }
    model = _read_codex_default_model()
    cost = cost_from_codex_usage_dict(delta_usage, model)
    prompt_tokens = delta_usage["input_tokens"]  # already includes cached
    completion_tokens = (
        delta_usage["output_tokens"] + delta_usage["reasoning_output_tokens"]
    )
    return cost, prompt_tokens, completion_tokens, model, current


def extract_session_id(raw: str) -> str | None:
    # Try structured JSONL first (codex --json emits {"type":"thread.started","thread_id":"..."})
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
            if isinstance(obj, dict) and obj.get("thread_id"):
                return str(obj["thread_id"])
        except (json.JSONDecodeError, ValueError):
            continue
    # Fallback: unstructured text pattern
    match = re.search(r"\bsession[_ ]id[: ]+([0-9a-fA-F-]{8,})", raw)
    return match.group(1) if match else None


def _extract_claude_usage(envelope: dict[str, Any] | None) -> tuple[int, int]:
    """Return ``(prompt_tokens, completion_tokens)`` from a Claude envelope.

    The Claude CLI emits a ``usage`` dict like::

        {
            "input_tokens": 123,
            "cache_read_input_tokens": 456,
            "cache_creation_input_tokens": 78,
            "output_tokens": 90,
        }

    Cached and uncached input are summed into ``prompt_tokens``. Missing or
    non-numeric fields default to ``0``. Returns ``(0, 0)`` if ``envelope``
    is missing or lacks a ``usage`` dict.
    """
    if not isinstance(envelope, dict):
        return 0, 0
    usage = envelope.get("usage")
    if not isinstance(usage, dict):
        return 0, 0

    def _safe_int(value: Any) -> int:
        try:
            return int(value or 0)
        except (TypeError, ValueError):
            return 0

    prompt_tokens = (
        _safe_int(usage.get("input_tokens"))
        + _safe_int(usage.get("cache_read_input_tokens"))
        + _safe_int(usage.get("cache_creation_input_tokens"))
    )
    completion_tokens = _safe_int(usage.get("output_tokens"))
    return prompt_tokens, completion_tokens


def parse_claude_envelope(raw: str) -> tuple[dict[str, Any], dict[str, Any]]:
    try:
        envelope = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise CliError("parse_error", f"Claude output was not valid JSON: {exc}", extra={"raw_output": raw}) from exc
    if isinstance(envelope, dict) and envelope.get("is_error"):
        message = envelope.get("result") or envelope.get("message") or "Claude returned an error"
        lower = str(message).lower()
        error_code = "worker_error"
        if any(pattern in lower for pattern in ("not logged in", "/login", "unauthorized", "authentication")):
            error_code = "auth_error"
        raise CliError(error_code, f"Claude step failed: {message}", extra={"raw_output": raw})
    # When using --json-schema, structured output lives in "structured_output"
    # rather than "result" (which may be empty).
    payload: Any = envelope
    if isinstance(envelope, dict):
        if "structured_output" in envelope and isinstance(envelope["structured_output"], dict):
            payload = envelope["structured_output"]
        elif "result" in envelope:
            payload = envelope["result"]
    if isinstance(payload, str):
        if not payload.strip():
            raise CliError("parse_error", "Claude returned empty result (check structured_output field)", extra={"raw_output": raw})
        try:
            payload = json.loads(payload)
        except json.JSONDecodeError as exc:
            raise CliError("parse_error", f"Claude result payload was not valid JSON: {exc}", extra={"raw_output": raw}) from exc
    if not isinstance(payload, dict):
        raise CliError("parse_error", "Claude result payload was not an object", extra={"raw_output": raw})
    return envelope, payload


def _extract_json_candidates_from_raw(raw: str) -> list[dict[str, Any]]:
    """Extract plausible JSON payload objects from raw agent output."""

    def _iter_nested_json_dicts(value: Any) -> list[dict[str, Any]]:
        candidates: list[dict[str, Any]] = []
        if isinstance(value, dict):
            candidates.append(value)
            prioritized_keys = (
                "structured_output",
                "result",
                "payload",
                "text",
                "message",
            )
            for key in prioritized_keys:
                if key not in value:
                    continue
                nested = value.get(key)
                candidates.extend(_iter_nested_json_dicts(nested))
            for nested in value.values():
                candidates.extend(_iter_nested_json_dicts(nested))
            return candidates
        if isinstance(value, list):
            for item in value:
                candidates.extend(_iter_nested_json_dicts(item))
            return candidates
        if isinstance(value, str):
            text = value.strip()
            if text.startswith("{") or text.startswith("["):
                try:
                    parsed = json.loads(text)
                except json.JSONDecodeError:
                    return []
                return _iter_nested_json_dicts(parsed)
            # Prose-wrapped JSON inside a string field — scan for embedded
            # JSON objects (e.g. assistant message text that prefaces the
            # structured output with a sentence or two). Mirrors strategy 3
            # below but scoped to the string content.
            embedded: list[dict[str, Any]] = []
            decoder = json.JSONDecoder()
            cursor = 0
            while True:
                brace = text.find("{", cursor)
                if brace < 0:
                    break
                try:
                    parsed, _end = decoder.raw_decode(text[brace:])
                except json.JSONDecodeError:
                    cursor = brace + 1
                    continue
                embedded.extend(_iter_nested_json_dicts(parsed))
                cursor = brace + 1
            return embedded
        return []

    candidates: list[dict[str, Any]] = []

    # Strategy 1: look for ```json ... ``` fenced blocks
    fenced = re.findall(r"```json\s*\n(.*?)```", raw, re.DOTALL)
    for block in fenced:
        try:
            obj = json.loads(block.strip())
            candidates.extend(_iter_nested_json_dicts(obj))
        except json.JSONDecodeError:
            continue
    # Strategy 2: parse JSONL/event-stream lines and inspect nested message fields.
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        candidates.extend(_iter_nested_json_dicts(obj))
    # Strategy 3: scan for the first decodable JSON object, even when
    # additional logs/traces are appended after it.
    decoder = json.JSONDecoder()
    search_start = 0
    while True:
        brace_start = raw.find("{", search_start)
        if brace_start < 0:
            break
        try:
            obj, _end = decoder.raw_decode(raw[brace_start:])
        except json.JSONDecodeError:
            search_start = brace_start + 1
            continue
        candidates.extend(_iter_nested_json_dicts(obj))
        search_start = brace_start + 1
    deduped: list[dict[str, Any]] = []
    seen: set[str] = set()
    for candidate in candidates:
        try:
            marker = json_dump(candidate)
        except Exception:
            marker = repr(candidate)
        if marker in seen:
            continue
        seen.add(marker)
        deduped.append(candidate)
    return deduped


def _extract_json_from_raw(raw: str) -> dict[str, Any] | None:
    """Return the first plausible JSON object extracted from raw agent output."""
    candidates = _extract_json_candidates_from_raw(raw)
    if candidates:
        return candidates[0]
    return None


def _normalize_worker_payload(step: str, payload: dict[str, Any]) -> dict[str, Any]:
    if step == "execute":
        normalized = dict(payload)
        task_updates = normalized.get("task_updates")
        if isinstance(task_updates, list):
            normalized_updates: list[Any] = []
            for update in task_updates:
                if not isinstance(update, dict):
                    normalized_updates.append(update)
                    continue
                item = dict(update)
                if "task_id" not in item and isinstance(item.get("id"), str):
                    item["task_id"] = item["id"]
                if item.get("status") == "completed":
                    item["status"] = "done"
                normalized_updates.append(item)
            normalized["task_updates"] = normalized_updates
        acknowledgments = normalized.get("sense_check_acknowledgments")
        if isinstance(acknowledgments, list):
            normalized_acknowledgments: list[Any] = []
            for acknowledgment in acknowledgments:
                if not isinstance(acknowledgment, dict):
                    normalized_acknowledgments.append(acknowledgment)
                    continue
                item = dict(acknowledgment)
                if "sense_check_id" not in item and isinstance(item.get("id"), str):
                    item["sense_check_id"] = item["id"]
                normalized_acknowledgments.append(item)
            normalized["sense_check_acknowledgments"] = normalized_acknowledgments
        return normalized
    if step == "revise" and "changes_summary" not in payload:
        normalized = dict(payload)
        flags_addressed = normalized.get("flags_addressed", [])
        if isinstance(flags_addressed, list) and flags_addressed:
            normalized["changes_summary"] = "Updated the plan to address the critique and gate feedback."
        else:
            normalized["changes_summary"] = "No critique flags were raised; refined the plan for execution."
        return normalized
    if step == "review":
        normalized = dict(payload)
        for key in ("checks", "pre_check_flags", "verified_flag_ids", "disputed_flag_ids"):
            if normalized.get(key) is None:
                normalized[key] = []
            else:
                normalized.setdefault(key, [])
        return normalized
    # Defensive defaults: Opus occasionally drops top-level array keys even when
    # the prompt schema lists them as required. Default them to [] so the chain
    # can proceed; missing string-typed required keys still fail validation.
    _STEP_OPTIONAL_ARRAY_DEFAULTS: dict[str, tuple[str, ...]] = {
        "plan": ("questions", "success_criteria", "assumptions"),
        "critique": ("flags", "verified_flag_ids", "disputed_flag_ids"),
        "revise": ("flags_addressed", "assumptions", "success_criteria", "questions"),
        "gate": ("warnings", "settled_decisions", "flag_resolutions", "accepted_tradeoffs"),
        "finalize": ("watch_items", "sense_checks", "user_actions"),
        "prep": ("relevant_code", "test_expectations", "constraints"),
        "loop_plan": ("spec_updates",),
        "loop_execute": ("files_to_change",),
        "tiebreaker_challenger": ("missing_options", "hard_cases", "reframings"),
        "feedback": ("stages",),
    }
    if step in _STEP_OPTIONAL_ARRAY_DEFAULTS:
        normalized = dict(payload)
        for key in _STEP_OPTIONAL_ARRAY_DEFAULTS[step]:
            if key not in normalized or normalized.get(key) is None:
                normalized[key] = []
        return normalized
    return payload


def _looks_like_step_payload(step: str, payload: dict[str, Any]) -> bool:
    required = set(_STEP_REQUIRED_KEYS.get(step, []))
    if required.intersection(payload):
        return True
    if step == "execute" and {"task_updates", "sense_check_acknowledgments"}.intersection(payload):
        return True
    return False


def parse_json_file(path: Path) -> dict[str, Any]:
    try:
        payload = read_json(path)
    except FileNotFoundError as exc:
        raise CliError("parse_error", f"Output file {path.name} was not created") from exc
    except json.JSONDecodeError as exc:
        raise CliError("parse_error", f"Output file {path.name} was not valid JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise CliError("parse_error", f"Output file {path.name} did not contain a JSON object")
    return payload


def _recover_codex_payload(
    step: str,
    *,
    plan_dir: Path,
    output_path: Path,
    raw: str,
    prefer_output_file: bool = True,
) -> dict[str, Any] | None:
    file_payload = None
    template_payload = None
    file_recovered_candidates: list[dict[str, Any]] = []
    try:
        file_payload = parse_json_file(output_path)
    except CliError:
        try:
            file_raw = output_path.read_text(encoding="utf-8", errors="replace")
            file_recovered_candidates.extend(_extract_json_candidates_from_raw(file_raw))
        except OSError:
            pass
    fallback_names = {
        "critique": "critique_output.json",
        "review": "review_output.json",
    }
    fallback_name = fallback_names.get(step, f"{step}_output.json")
    fallback_path = plan_dir / fallback_name
    if fallback_path != output_path and fallback_path.exists():
        try:
            template_payload = parse_json_file(fallback_path)
        except CliError:
            try:
                fallback_raw = fallback_path.read_text(encoding="utf-8", errors="replace")
                file_recovered_candidates.extend(_extract_json_candidates_from_raw(fallback_raw))
            except OSError:
                pass
    if file_payload is None and template_payload is not None:
        file_payload = template_payload
        template_payload = None
    output_is_template_file = output_path == fallback_path
    if prefer_output_file and file_payload is not None and (step != "critique" or output_is_template_file):
        normalized_file_payload = _normalize_worker_payload(step, file_payload)
        try:
            validate_payload(step, normalized_file_payload)
        except CliError as error:
            if _looks_like_step_payload(step, normalized_file_payload):
                raise CliError(
                    "parse_error",
                    f"Recovered JSON object for {step} failed validation: {error.message}",
                    extra={"raw_output": raw},
                ) from error
        else:
            return normalized_file_payload
    raw_candidates = _extract_json_candidates_from_raw(raw)
    candidate_payloads: list[dict[str, Any]] = []
    if file_payload is not None:
        candidate_payloads.append(file_payload)
    if template_payload is not None:
        candidate_payloads.append(template_payload)
    candidate_payloads.extend(file_recovered_candidates)
    candidate_payloads.extend(raw_candidates)
    valid_payloads: list[dict[str, Any]] = []
    validation_errors: list[str] = []
    for candidate in candidate_payloads:
        normalized = _normalize_worker_payload(step, candidate)
        try:
            validate_payload(step, normalized)
        except CliError as error:
            if _looks_like_step_payload(step, normalized):
                validation_errors.append(error.message)
            continue
        valid_payloads.append(normalized)
    if not valid_payloads:
        if validation_errors:
            unique_errors = list(dict.fromkeys(validation_errors))
            raise CliError(
                "parse_error",
                f"Recovered JSON object for {step} failed validation: "
                + " | ".join(unique_errors),
                extra={"raw_output": raw},
            )
        return None
    if step == "critique" and len(valid_payloads) > 1:
        def _critique_completeness_score(item: dict[str, Any]) -> tuple[int, int]:
            checks = item.get("checks", [])
            if not isinstance(checks, list):
                return (0, 0)
            completed_checks = 0
            total_findings = 0
            for check in checks:
                if not isinstance(check, dict):
                    continue
                findings = check.get("findings", [])
                if not isinstance(findings, list) or not findings:
                    continue
                completed_checks += 1
                total_findings += len(findings)
            return (completed_checks, total_findings)

        return max(valid_payloads, key=_critique_completeness_score)
    return valid_payloads[0]


def validate_payload(step: str, payload: dict[str, Any]) -> None:
    if step == "phase_result":
        from megaplan.orchestration.phase_result import validate_phase_result
        validate_phase_result(payload)
        return
    if step == "execute":
        full_required = _STEP_REQUIRED_KEYS.get(step, [])
        missing_full = [key for key in full_required if key not in payload]
        if not missing_full:
            return
        batch_required = ["task_updates", "sense_check_acknowledgments"]
        missing_batch = [key for key in batch_required if key not in payload]
        if not missing_batch:
            return
        raise CliError(
            "parse_error",
            (
                "execute output missing required keys: "
                + ", ".join(missing_full)
                + ". Batch execute payloads may omit aggregate fields, "
                + "but must include task_updates and sense_check_acknowledgments."
            ),
        )
    required = _STEP_REQUIRED_KEYS.get(step)
    if required is None:
        return
    missing = [key for key in required if key not in payload]
    if missing:
        raise CliError("parse_error", f"{step} output missing required keys: {', '.join(missing)}")


def _mock_result(
    payload: dict[str, Any],
    *,
    trace_output: str | None = None,
) -> WorkerResult:
    return WorkerResult(
        payload=payload,
        raw_output=json_dump(payload),
        duration_ms=10,
        cost_usd=0.0,
        session_id=str(uuid.uuid4()),
        trace_output=trace_output,
    )


def _deep_merge(base: dict[str, Any], overrides: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in overrides.items():
        base_value = merged.get(key)
        if isinstance(base_value, dict) and isinstance(value, dict):
            merged[key] = _deep_merge(base_value, value)
            continue
        merged[key] = value
    return merged


def _default_mock_plan_payload(state: PlanState, plan_dir: Path) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "plan": textwrap.dedent(
            f"""
            # Implementation Plan: Mock Planning Pass

            ## Overview
            Produce a concrete plan for: {state['idea']}. Keep the scope grounded in the repository and define validation before execution.

            ## Step 1: Inspect the current flow (`megaplan/workers.py`)
            **Scope:** Small
            1. **Inspect** the planner and prompt touch points before editing (`megaplan/workers.py:199`, `megaplan/prompts.py:29`).

            ## Step 2: Implement the smallest viable change (`megaplan/handlers.py`)
            **Scope:** Medium
            1. **Update** the narrowest set of files required to implement the idea (`megaplan/handlers.py:400`).
            2. **Capture** any non-obvious behavior with a short example.
               ```python
               result = "keep the plan structure consistent"
               ```

            ## Step 3: Verify the behavior (`tests/test_megaplan.py`)
            **Scope:** Small
            1. **Run** focused checks that prove the change works (`tests/test_megaplan.py:1`).

            ## Execution Order
            1. Inspect before editing so the plan stays repo-specific.
            2. Implement before expanding verification.

            ## Validation Order
            1. Run targeted tests first.
            2. Run broader checks after the core change lands.
            """
        ).strip(),
        "questions": ["Are there existing patterns in the repo that should be preserved?"],
        "success_criteria": [
            {"criterion": "A concrete implementation path exists.", "priority": "must"},
            {"criterion": "Verification is defined before execution.", "priority": "should"},
        ],
        "assumptions": ["The project directory is writable."],
    }
    return payload


def _default_mock_prep_payload(state: PlanState, plan_dir: Path) -> dict[str, Any]:
    del plan_dir
    return {
        "task_summary": str(state.get("idea", "")).strip() or "Prepare a concise engineering brief for the requested task.",
        "key_evidence": [],
        "relevant_code": [],
        "test_expectations": [],
        "constraints": [],
        "suggested_approach": "Inspect the code paths named in the task, read nearby tests first when they exist, then carry the distilled brief into planning.",
    }


def _loop_goal(state: dict[str, Any]) -> str:
    return str(state.get("idea", state.get("spec", {}).get("goal", "")))


def _default_mock_loop_plan_payload(state: dict[str, Any], plan_dir: Path) -> dict[str, Any]:
    spec = state.get("spec", {})
    goal = _loop_goal(state)
    return {
        "spec_updates": {
            "known_issues": spec.get("known_issues", []),
            "tried_and_failed": spec.get("tried_and_failed", []),
            "best_result_summary": f"Most recent mock planning pass for: {goal}",
        },
        "next_action": "Run the project command, inspect the failures, and prepare the next minimal fix.",
        "reasoning": "The loop spec is initialized and ready for an execution pass based on the current goal and retained context.",
    }


def _default_mock_loop_execute_payload(
    state: dict[str, Any],
    plan_dir: Path,
    *,
    prompt_override: str | None = None,
) -> dict[str, Any]:
    spec = state.get("spec", {})
    goal = _loop_goal(state)
    return {
        "diagnosis": f"Mock execution diagnosis for goal: {goal}",
        "fix_description": "Inspect the command failure, update the smallest relevant file, and rerun the command.",
        "files_to_change": list(spec.get("allowed_changes", []))[:3],
        "confidence": "medium",
        "outcome": "continue",
        "should_pause": False,
    }


def _default_mock_critique_payload(state: PlanState, plan_dir: Path) -> dict[str, Any]:
    iteration = state["iteration"] or 1
    robustness = configured_robustness(state)
    active_checks = select_active_checks(state, robustness, plan_dir=plan_dir)
    checks = build_empty_template(active_checks)
    if iteration == 1:
        return {
            "checks": [
                {
                    **check,
                    "findings": [
                        {
                            "detail": "Mock critique found a concrete repository issue that should be addressed before proceeding.",
                            "flagged": True,
                        }
                    ],
                }
                for check in checks
            ],
            "flags": [
                {
                    "id": "FLAG-001",
                    "concern": "The plan does not name the files or modules it expects to touch.",
                    "category": "completeness",
                    "severity_hint": "likely-significant",
                    "evidence": "Execution could drift because there is no repo-specific scope.",
                },
                {
                    "id": "FLAG-002",
                    "concern": "The plan does not define an observable verification command.",
                    "category": "correctness",
                    "severity_hint": "likely-significant",
                    "evidence": "Success cannot be demonstrated without a concrete check.",
                },
            ],
            "verified_flag_ids": [],
            "disputed_flag_ids": [],
        }
    return {
        "checks": [
            {
                **check,
                "findings": [
                    {
                        "detail": "Mock critique verified the revised plan against the repository context and found no remaining issue.",
                        "flagged": False,
                    }
                ],
            }
            for check in checks
        ],
        "flags": [],
        "verified_flag_ids": [*(check["id"] for check in checks), "FLAG-001", "FLAG-002"],
        "disputed_flag_ids": [],
    }



def _default_mock_revise_payload(state: PlanState, plan_dir: Path) -> dict[str, Any]:
    return {
        "plan": textwrap.dedent(
            f"""
            # Implementation Plan: Mock Revision Pass

            ## Overview
            Refine the plan for: {state['idea']}. Tighten file-level scope and keep validation explicit.

            ## Step 1: Reconfirm file scope (`megaplan/handlers.py`)
            **Scope:** Small
            1. **Inspect** the exact edit points before changing the plan (`megaplan/handlers.py:540`).

            ## Step 2: Tighten the implementation slice (`megaplan/workers.py`)
            **Scope:** Medium
            1. **Limit** the plan to the smallest coherent change set (`megaplan/workers.py:256`).
            2. **Illustrate** the intended shape when it helps reviewers.
               ```python
               changes_summary = "Added explicit scope and verification details."
               ```

            ## Step 3: Reconfirm verification (`tests/test_workers.py`)
            **Scope:** Small
            1. **Run** a concrete verification command and record the expected proof point (`tests/test_workers.py:251`).

            ## Execution Order
            1. Re-scope the plan before adjusting implementation details.
            2. Re-run validation after the plan is tightened.

            ## Validation Order
            1. Start with the focused worker and handler tests.
            2. End with the broader suite if the focused checks pass.
            """
        ).strip(),
        "changes_summary": "Added explicit repo-scoping and verification steps.",
        "flags_addressed": ["FLAG-001", "FLAG-002"],
        "assumptions": ["The repository contains enough context for implementation."],
        "success_criteria": [
            {"criterion": "The plan identifies exact touch points before editing.", "priority": "must"},
            {"criterion": "A concrete verification command is defined.", "priority": "should"},
        ],
        "questions": [],
    }


def _default_mock_gate_payload(state: PlanState, plan_dir: Path) -> dict[str, Any]:
    recommendation = "ITERATE" if state["iteration"] == 1 else "PROCEED"
    return {
        "recommendation": recommendation,
        "rationale": (
            "First critique cycle still needs another pass."
            if recommendation == "ITERATE"
            else "Signals are strong enough to move into execution."
        ),
        "signals_assessment": (
            "Iteration 1 still carries unresolved significant flags and should revise."
            if recommendation == "ITERATE"
            else "Weighted score and loop trajectory support proceeding."
        ),
        "warnings": [],
        "settled_decisions": [],
        "flag_resolutions": [],
        "accepted_tradeoffs": [],
    }


def _default_mock_finalize_payload(state: PlanState, plan_dir: Path) -> dict[str, Any]:
    return {
        "tasks": [
            {
                "id": "T1",
                "description": f"Implement: {state['idea']}",
                "depends_on": [],
                "status": "pending",
                "complexity": 3,
                "complexity_justification": "Mock implementation task; assumes multi-file non-trivial logic → tier 3.",
                "executor_notes": "",
                "files_changed": [],
                "commands_run": [],
                "evidence_files": [],
                "reviewer_verdict": "",
            },
            {
                "id": "T2",
                "description": "Verify success criteria",
                "depends_on": [],
                "status": "pending",
                "complexity": 2,
                "complexity_justification": "Mock verification task; running and reading tests → tier 2.",
                "executor_notes": "",
                "files_changed": [],
                "commands_run": [],
                "evidence_files": [],
                "reviewer_verdict": "",
            },
        ],
        "watch_items": ["Ensure repository state matches plan assumptions"],
        "sense_checks": [
            {
                "id": "SC1",
                "task_id": "T1",
                "question": "Verify implementation matches the stated idea.",
                "executor_note": "",
                "verdict": "",
            },
            {
                "id": "SC2",
                "task_id": "T2",
                "question": "Verify success criteria were actually checked.",
                "executor_note": "",
                "verdict": "",
            },
        ],
        "user_actions": [],
        "meta_commentary": "This is a mock finalize output.",
        "validation": {
            "plan_steps_covered": [
                {"plan_step_summary": f"Implement: {state['idea']}", "finalize_item_ids": ["T1"]},
                {"plan_step_summary": "Verify success criteria", "finalize_item_ids": ["T2"]},
            ],
            "orphan_tasks": [],
            "completeness_notes": "All plan steps mapped to tasks.",
            "coverage_complete": True,
        },
    }


def _task_ids_from_prompt_override(prompt_override: str | None) -> set[str] | None:
    if prompt_override is None:
        return None
    match = re.search(r"Only produce `?task_updates`? for these tasks:\s*\[([^\]]*)\]", prompt_override)
    if match is None:
        return None
    task_ids = {item.strip() for item in match.group(1).split(",") if item.strip()}
    return task_ids


def _default_mock_execute_payload(
    state: PlanState,
    plan_dir: Path,
    *,
    prompt_override: str | None = None,
) -> dict[str, Any]:
    target = Path(state["config"]["project_dir"]) / "IMPLEMENTED_BY_MEGAPLAN.txt"
    relative_target = str(target.relative_to(Path(state["config"]["project_dir"])))
    payload = {
        "output": "Mock execution completed successfully.",
        "files_changed": [relative_target],
        "commands_run": ["mock-write IMPLEMENTED_BY_MEGAPLAN.txt"],
        "deviations": [],
        "task_updates": [
            {
                "task_id": "T1",
                "status": "done",
                "executor_notes": "Implemented via mock worker output and wrote IMPLEMENTED_BY_MEGAPLAN.txt.",
                "files_changed": [relative_target],
                "commands_run": ["mock-write IMPLEMENTED_BY_MEGAPLAN.txt"],
            },
            {
                "task_id": "T2",
                "status": "done",
                "executor_notes": "Verified success criteria via mock worker output and command checks.",
                "files_changed": [],
                "commands_run": ["mock-verify success criteria"],
            },
        ],
        "sense_check_acknowledgments": [
            {
                "sense_check_id": "SC1",
                "executor_note": "Confirmed the implementation artifact was written for the main task.",
            },
            {
                "sense_check_id": "SC2",
                "executor_note": "Confirmed the verification-only task is backed by command evidence.",
            },
        ],
    }
    batch_task_ids = _task_ids_from_prompt_override(prompt_override)
    if batch_task_ids is None:
        return payload
    payload["task_updates"] = [
        task_update
        for task_update in payload["task_updates"]
        if task_update["task_id"] in batch_task_ids
    ]
    payload["sense_check_acknowledgments"] = [
        acknowledgment
        for acknowledgment in payload["sense_check_acknowledgments"]
        if acknowledgment["sense_check_id"] in {
            f"SC{task_id[1:]}"
            for task_id in batch_task_ids
            if task_id.startswith("T")
        }
    ]
    return payload


def _default_mock_review_payload(state: PlanState, plan_dir: Path) -> dict[str, Any]:
    meta = read_json(latest_plan_meta_path(plan_dir, state))
    criteria = []
    for entry in meta.get("success_criteria", []):
        if isinstance(entry, dict):
            name = entry.get("criterion", str(entry))
            priority = entry.get("priority", "must")
        else:
            name = str(entry)
            priority = "must"
        criteria.append({"name": name, "priority": priority, "pass": "pass", "evidence": "Mock execution and artifacts satisfy the criterion."})
    return {
        "review_verdict": "approved",
        "checks": [],
        "pre_check_flags": [],
        "verified_flag_ids": [],
        "disputed_flag_ids": [],
        "criteria": criteria,
        "issues": [],
        "rework_items": [],
        "summary": "Mock review passed.",
        "task_verdicts": [
            {
                "task_id": "T1",
                "reviewer_verdict": "Pass - mock verified with file-backed implementation evidence.",
                "evidence_files": [str((Path(state["config"]["project_dir"]) / "IMPLEMENTED_BY_MEGAPLAN.txt").relative_to(Path(state["config"]["project_dir"])))],
            },
            {
                "task_id": "T2",
                "reviewer_verdict": "Pass - verification task was reviewed via command evidence and executor notes rather than a changed file.",
                "evidence_files": [],
            },
        ],
        "sense_check_verdicts": [
            {"sense_check_id": "SC1", "verdict": "Confirmed."},
            {"sense_check_id": "SC2", "verdict": "Confirmed."},
        ],
    }


_MockPayloadBuilder = Callable[[dict[str, Any], Path], dict[str, Any]]

_MOCK_DEFAULTS: dict[str, _MockPayloadBuilder] = {
    "plan": _default_mock_plan_payload,
    "prep": _default_mock_prep_payload,
    "loop_plan": _default_mock_loop_plan_payload,
    "critique": _default_mock_critique_payload,
    "revise": _default_mock_revise_payload,
    "gate": _default_mock_gate_payload,
    "finalize": _default_mock_finalize_payload,
    "execute": _default_mock_execute_payload,
    "loop_execute": _default_mock_loop_execute_payload,
    "review": _default_mock_review_payload,
}


def _build_mock_payload(step: str, state: dict[str, Any], plan_dir: Path, **overrides: Any) -> dict[str, Any]:
    builder = _MOCK_DEFAULTS.get(step)
    if builder is None:
        raise CliError("unsupported_step", f"Mock worker does not support '{step}'")
    prompt_override = overrides.pop("prompt_override", None)
    if step in _EXECUTE_STEPS:
        if step == "loop_execute":
            return _deep_merge(_default_mock_loop_execute_payload(state, plan_dir, prompt_override=prompt_override), overrides)
        return _deep_merge(_default_mock_execute_payload(state, plan_dir, prompt_override=prompt_override), overrides)
    return _deep_merge(builder(state, plan_dir), overrides)


# Steps the mock worker supports, in declaration order. The trace stub
# only fires for the two execute-shaped steps; everything else gets an
# empty trace. Update both sets to add a new step.
_MOCK_SUPPORTED_STEPS: tuple[str, ...] = (
    "plan", "prep", "loop_plan",
    "critique", "revise", "gate", "finalize",
    "execute", "loop_execute", "review",
)
_MOCK_TRACE_OUTPUTS: dict[str, str] = {
    "execute": '{"event":"mock-execute"}\n',
    "loop_execute": '{"event":"mock-loop-execute"}\n',
}


def _mock_step(
    step: str,
    state: PlanState,
    plan_dir: Path,
    *,
    prompt_override: str | None = None,
) -> WorkerResult:
    """Build the canonical mock WorkerResult for ``step``.

    ``step == "execute"`` writes the IMPLEMENTED_BY_MEGAPLAN.txt sentinel
    into the project directory — the only side effect any of the mock
    handlers performed. Execute-shaped steps thread ``prompt_override``
    through; the rest ignore it.
    """
    if step not in _MOCK_SUPPORTED_STEPS:
        raise CliError("unsupported_step", f"Mock worker does not support '{step}'")
    if step == "execute":
        target = Path(state["config"]["project_dir"]) / "IMPLEMENTED_BY_MEGAPLAN.txt"
        target.write_text("mock execution completed\n", encoding="utf-8")
    if step in _EXECUTE_STEPS:
        payload = _build_mock_payload(step, state, plan_dir, prompt_override=prompt_override)
    else:
        payload = _build_mock_payload(step, state, plan_dir)
    return _mock_result(payload, trace_output=_MOCK_TRACE_OUTPUTS.get(step))


def mock_worker_output(
    step: str,
    state: PlanState,
    plan_dir: Path,
    *,
    prompt_override: str | None = None,
    prompt_kwargs: dict[str, Any] | None = None,
) -> WorkerResult:
    del prompt_kwargs
    result = _mock_step(step, state, plan_dir, prompt_override=prompt_override)
    try:
        root = _resolve_prompt_root(plan_dir, None)
        side_effect_paths = (
            plan_dir / "critique_output.json",
            plan_dir / "review_output.json",
        )
        preexisting_paths = {path for path in side_effect_paths if path.exists()}
        result.rendered_prompt = create_hermes_prompt(step, state, plan_dir, root=root)
        for path in side_effect_paths:
            if path.exists() and path not in preexisting_paths:
                path.unlink()
    except Exception:
        result.rendered_prompt = prompt_override
    return result


def session_key_for(step: str, agent: str, model: str | None = None) -> str:
    if step in {"plan", "revise"}:
        key = f"{agent}_planner"
    elif step == "critique":
        key = f"{agent}_critic"
    elif step == "gate":
        key = f"{agent}_gatekeeper"
    elif step == "finalize":
        key = f"{agent}_finalizer"
    elif step == "execute":
        key = f"{agent}_executor"
    elif step == "review":
        key = f"{agent}_reviewer"
    else:
        key = f"{agent}_{step}"
    if model:
        key += f"_{hashlib.sha256(model.encode()).hexdigest()[:8]}"
    return key


def update_session_state(step: str, agent: str, session_id: str | None, *, mode: str, refreshed: bool, model: str | None = None, existing_sessions: dict[str, Any] | None = None) -> tuple[str, SessionInfo] | None:
    """Build a session entry for the given step.

    Returns ``(key, entry)`` so the caller can store it on the state dict,
    or ``None`` when there is no session_id to record.
    """
    if not session_id:
        return None
    key = session_key_for(step, agent, model=model)
    if existing_sessions is None:
        existing_sessions = {}
    entry = {
        "id": session_id,
        "mode": mode,
        "created_at": existing_sessions.get(key, {}).get("created_at", now_utc()),
        "last_used_at": now_utc(),
        "refreshed": refreshed,
    }
    existing_entry = existing_sessions.get(key, {})
    if (
        isinstance(existing_entry, dict)
        and existing_entry.get("id") == session_id
        and isinstance(existing_entry.get("last_total_tokens"), dict)
    ):
        entry["last_total_tokens"] = dict(existing_entry["last_total_tokens"])
    return key, entry


_VALID_CLAUDE_EFFORTS = {"low", "medium", "high", "xhigh", "max"}
_VALID_CODEX_EFFORTS = ("minimal", "low", "medium", "high")


def run_claude_step(
    step: str,
    state: PlanState,
    plan_dir: Path,
    *,
    root: Path,
    fresh: bool,
    prompt_override: str | None = None,
    prompt_kwargs: dict[str, Any] | None = None,
    effort: str | None = None,
    model: str | None = None,
) -> WorkerResult:
    """Compatibility wrapper: the public ``claude`` route runs via Shannon."""
    if effort is not None and effort not in _VALID_CLAUDE_EFFORTS:
        raise CliError("invalid_args", f"Unsupported claude effort level: {effort}")
    from megaplan.workers.shannon import run_shannon_step

    return run_shannon_step(
        step,
        state,
        plan_dir,
        root=root,
        fresh=fresh,
        prompt_override=prompt_override,
        prompt_kwargs=prompt_kwargs,
        effort=effort,
        session_agent="claude",
        model=model,
    )


def run_codex_step(
    step: str,
    state: PlanState,
    plan_dir: Path,
    *,
    root: Path,
    persistent: bool,
    fresh: bool = False,
    json_trace: bool = False,
    prompt_override: str | None = None,
    prompt_kwargs: dict[str, Any] | None = None,
    effort: str | None = None,
    model: str | None = None,
) -> WorkerResult:
    if effort is not None and effort not in _VALID_CODEX_EFFORTS:
        raise CliError("invalid_args", f"Unsupported codex effort level: {effort}")
    fresh = fresh or step not in _CROSS_CALL_PERSISTENT_STEPS
    if os.getenv(MOCK_ENV_VAR) == "1":
        return mock_worker_output(step, state, plan_dir, prompt_override=prompt_override, prompt_kwargs=prompt_kwargs)
    project_dir = Path(state["config"]["project_dir"])
    work_dir = resolve_work_dir(state)
    plan_mode = state["config"].get("mode", "code")
    codex_schema_name = (
        get_execution_schema_key(plan_mode, form=creative_form_id(state))
        if step == "execute"
        else STEP_SCHEMA_FILENAMES[step]
    )
    schema_file = schemas_root(root) / codex_schema_name
    session_key = session_key_for(step, "codex", model=model)
    session = state["sessions"].get(session_key, {})
    if fresh and persistent and step == "execute" and session.get("id"):
        print(
            f"[megaplan] Fresh codex execute requested; invalidating prior "
            f"{session_key} session {session['id']}",
            flush=True,
        )
        state["sessions"].pop(session_key, None)
        session = {}
    if persistent and step == "execute" and session.get("id") and not fresh:
        threshold = _codex_executor_session_headroom_tokens()
        total_tokens = _codex_total_tokens_from_session(session)
        if total_tokens is not None and total_tokens >= threshold:
            print(
                f"[megaplan] Codex executor session {session['id']} has "
                f"{total_tokens:,} total tokens, exceeding headroom threshold "
                f"{threshold:,}; starting execute with a fresh session",
                flush=True,
            )
            state["sessions"].pop(session_key, None)
            session = {}
            fresh = True
    out_handle = tempfile.NamedTemporaryFile("w+", encoding="utf-8", delete=False)
    out_handle.close()
    output_path = Path(out_handle.name)
    prompt = prompt_override if prompt_override is not None else create_codex_prompt(
        step,
        state,
        plan_dir,
        root=root,
        **(prompt_kwargs or {}),
    )
    timeout_seconds = _codex_timeout_for_step(step)

    if persistent and session.get("id") and not fresh:
        # codex exec resume does not support --output-schema; we rely on
        # validate_payload() after parsing the output file instead. It also
        # does not accept --add-dir; resumed sessions keep the workspace that
        # was granted when the session was created.
        command = ["codex", "exec", "resume"]
        if _trusted_container():
            command.append("--dangerously-bypass-approvals-and-sandbox")
        if model is not None:
            command.extend(["-c", f"model='{model}'"])
        if effort is not None:
            command.extend(["-c", f"model_reasoning_effort={effort}"])
        command.extend(_codex_exec_mode_flags(step))
        if json_trace:
            command.append("--json")
        command.extend([
            "--skip-git-repo-check",
            "-o", str(output_path),
            str(session["id"]), "-",
        ])
    else:
        command = [
            "codex",
            "exec",
            "--skip-git-repo-check",
            "-C",
            str(work_dir),
            "--add-dir",
            str(plan_dir),
        ]
        if _trusted_container():
            # In a trusted container the surrounding runtime is the sandbox.
            # Skip the workspace-write sandbox (which requires user namespaces
            # that most container runtimes don't grant) and let Codex run
            # unsandboxed. The outer container boundary still contains writes.
            command.append("--dangerously-bypass-approvals-and-sandbox")
        else:
            # Allow projects to declare extra writable roots via state.config.
            # Useful when the project_dir is a subdirectory of a multi-package
            # workspace and tasks legitimately create files in sibling dirs
            # (e.g. tools/ as project_dir but plan creates animations/ at the
            # workspace root). Roots are passed verbatim to codex; relative
            # paths are resolved against work_dir.
            extra_roots: list[str] = []
            # Auto-widen the sandbox to the enclosing workspace root when
            # work_dir is a subdirectory of a larger checkout. Without this,
            # plans whose project_dir is e.g. ``tools/`` get blocked from
            # writing siblings like ``effects/`` even though they're part of
            # the same repo. Set MEGAPLAN_NARROW_SANDBOX=1 to opt out.
            extra_roots.extend(_auto_writable_roots(Path(work_dir)))
            try:
                state_path = plan_dir / "state.json"
                if state_path.is_file():
                    state_data = json.loads(state_path.read_text(encoding="utf-8"))
                    raw_extra = state_data.get("config", {}).get("extra_writable_roots", []) or []
                    if isinstance(raw_extra, list):
                        for root in raw_extra:
                            if not isinstance(root, str):
                                continue
                            resolved = (Path(work_dir) / root).resolve() if not Path(root).is_absolute() else Path(root).resolve()
                            extra_roots.append(str(resolved))
            except Exception:
                pass
            # Deduplicate while preserving order; ensures work_dir is first
            # (codex treats the first entry as the primary workspace).
            seen: set[str] = set()
            roots: list[str] = []
            for r in [str(work_dir), *extra_roots]:
                if r not in seen:
                    seen.add(r)
                    roots.append(r)
            roots_literal = ", ".join(f"\"{r}\"" for r in roots)
            command.extend([
                "-c",
                f"sandbox_workspace_write.writable_roots=[{roots_literal}]",
            ])
        command.extend([
            "-o",
            str(output_path),
        ])
        if model is not None:
            command.extend(["-c", f"model='{model}'"])
        if effort is not None:
            command.extend(["-c", f"model_reasoning_effort={effort}"])
        if not persistent:
            command.append("--ephemeral")
        command.extend(_codex_exec_mode_flags(step))
        if json_trace:
            command.append("--json")
        command.extend(["--output-schema", str(schema_file), "-"])

    try:
        result = run_command(
            command,
            cwd=Path.cwd(),
            stdin_text=prompt,
            env=_codex_child_env(turn_id=f'plan_worker_{state["name"]}'),
            timeout=timeout_seconds,
            activity_callback=_activity_callback_for_state(state, plan_dir),
        )
    except CliError as error:
        error.extra["raw_output"] = _merge_partial_output(
            str(error.extra.get("raw_output", "")),
            output_path,
        )
        # Recover from a lost session: container restarted since the session was
        # created, codex's rollout store is gone, but megaplan still has the id.
        # Clear the stale session and retry once with fresh=True.
        if not fresh and persistent and session.get("id") and _is_rollout_missing(
            str(error.extra.get("raw_output", ""))
        ):
            print(
                f"[megaplan] Codex session {session['id']} has no rollout "
                f"(container restart or session wipe); retrying {step} with a fresh session",
                flush=True,
            )
            # Drop the stale session id so later phases don't also try to resume it.
            state["sessions"].pop(session_key, None)
            return run_codex_step(
                step,
                state,
                plan_dir,
                root=root,
                persistent=persistent,
                fresh=True,
                json_trace=json_trace,
                prompt_override=prompt_override,
                prompt_kwargs=prompt_kwargs,
                effort=effort,
                model=model,
            )
        # Recover from a poisoned session: the history carries an obsolete
        # "sandbox is broken" belief from a pre-trusted-container run. Only
        # act when we're in trusted-container mode (so we know the belief is
        # stale) and we were resuming a session (fresh sessions can't carry
        # the poisoned history). See _is_poisoned_environmental_failure.
        if (
            not fresh
            and persistent
            and session.get("id")
            and _trusted_container()
            and _is_poisoned_environmental_failure(
                str(error.extra.get("raw_output", ""))
            )
        ):
            print(
                "[megaplan] Detected poisoned session (obsolete sandbox failure belief); "
                "invalidating session and retrying with --fresh",
                flush=True,
            )
            state["sessions"].pop(session_key, None)
            return run_codex_step(
                step,
                state,
                plan_dir,
                root=root,
                persistent=persistent,
                fresh=True,
                json_trace=json_trace,
                prompt_override=prompt_override,
                prompt_kwargs=prompt_kwargs,
                effort=effort,
                model=model,
            )
        # Recover from a session that grew too large to remote-compact:
        # OpenAI 429s the compaction call, codex gives up and exits. Same
        # session id will keep failing — start fresh.
        if (
            not fresh
            and persistent
            and session.get("id")
            and _is_session_too_large_for_compact(
                str(error.extra.get("raw_output", ""))
            )
        ):
            print(
                "[megaplan] Detected oversized codex session (remote compact 429); "
                "invalidating session and retrying with --fresh",
                flush=True,
            )
            state["sessions"].pop(session_key, None)
            return run_codex_step(
                step,
                state,
                plan_dir,
                root=root,
                persistent=persistent,
                fresh=True,
                json_trace=json_trace,
                prompt_override=prompt_override,
                prompt_kwargs=prompt_kwargs,
                effort=effort,
                model=model,
            )
        if error.code == "worker_timeout":
            recovered_payload = _recover_codex_payload(
                step,
                plan_dir=plan_dir,
                output_path=output_path,
                raw=str(error.extra.get("raw_output", "")),
                prefer_output_file=False,
            )
            if recovered_payload is not None:
                timeout_session_id = session.get("id") if persistent else None
                if timeout_session_id is None:
                    timeout_session_id = extract_session_id(str(error.extra.get("raw_output", "")))
                return WorkerResult(
                    payload=recovered_payload,
                    raw_output=str(error.extra.get("raw_output", "")),
                    duration_ms=0,
                    cost_usd=0.0,
                    session_id=timeout_session_id,
                    trace_output=str(error.extra.get("raw_output", "")) if json_trace else None,
                    rendered_prompt=prompt,
                )
            timeout_session_id = session.get("id") if persistent else None
            if timeout_session_id is None:
                timeout_session_id = extract_session_id(error.extra.get("raw_output", ""))
            if timeout_session_id is not None:
                error.extra["session_id"] = timeout_session_id
            diagnosed_code, diagnosed_message = _diagnose_codex_failure(
                str(error.extra.get("raw_output", "")),
                124,
            )
            if diagnosed_code == "connection_error":
                raise CliError(
                    diagnosed_code,
                    diagnosed_message,
                    extra=error.extra,
                    valid_next=error.valid_next,
                    exit_code=error.exit_code,
                ) from error
            raise CliError(
                "worker_timeout",
                (
                    f"Codex {step} step timed out after {timeout_seconds}s before producing structured output. "
                    + _codex_retry_guidance(step)
                ),
                extra=error.extra,
                valid_next=error.valid_next,
                exit_code=error.exit_code,
            ) from error
        raise
    raw = result.stdout + result.stderr
    # Same rollout-missing recovery for the non-exception path (non-zero exit
    # without CliError being raised). See _is_rollout_missing for context.
    if (
        not fresh
        and persistent
        and session.get("id")
        and result.returncode != 0
        and _is_rollout_missing(raw)
    ):
        print(
            f"[megaplan] Codex session {session['id']} has no rollout "
            f"(container restart or session wipe); retrying {step} with a fresh session",
            flush=True,
        )
        state["sessions"].pop(session_key, None)
        return run_codex_step(
            step,
            state,
            plan_dir,
            root=root,
            persistent=persistent,
            fresh=True,
            json_trace=json_trace,
            prompt_override=prompt_override,
            prompt_kwargs=prompt_kwargs,
            effort=effort,
            model=model,
        )
    # Poisoned-session recovery on non-exception path: the worker exited 0 or
    # non-zero but produced output that still echoes an obsolete sandbox
    # failure belief. Same guard conditions as the CliError branch above.
    if (
        not fresh
        and persistent
        and session.get("id")
        and _trusted_container()
        and _is_poisoned_environmental_failure(raw)
    ):
        print(
            "[megaplan] Detected poisoned session (obsolete sandbox failure belief); "
            "invalidating session and retrying with --fresh",
            flush=True,
        )
        state["sessions"].pop(session_key, None)
        return run_codex_step(
            step,
            state,
            plan_dir,
            root=root,
            persistent=persistent,
            fresh=True,
            json_trace=json_trace,
            prompt_override=prompt_override,
            prompt_kwargs=prompt_kwargs,
            effort=effort,
            model=model,
        )
    # Oversized-session recovery on non-exception path. See the matching
    # branch in the CliError handler above for context.
    if (
        not fresh
        and persistent
        and session.get("id")
        and result.returncode != 0
        and _is_session_too_large_for_compact(raw)
    ):
        print(
            "[megaplan] Detected oversized codex session (remote compact 429); "
            "invalidating session and retrying with --fresh",
            flush=True,
        )
        state["sessions"].pop(session_key, None)
        return run_codex_step(
            step,
            state,
            plan_dir,
            root=root,
            persistent=persistent,
            fresh=True,
            json_trace=json_trace,
            prompt_override=prompt_override,
            prompt_kwargs=prompt_kwargs,
            effort=effort,
            model=model,
        )
    if result.returncode != 0 and (not output_path.exists() or not output_path.read_text(encoding="utf-8").strip()):
        error_code, error_message = _diagnose_codex_failure(raw, result.returncode)
        raise CliError(error_code, error_message, extra={"raw_output": raw})
    if result.returncode != 0:
        error_code, error_message = _diagnose_codex_failure(raw, result.returncode)
        if error_code != "worker_error":
            raise CliError(error_code, error_message, extra={"raw_output": raw})
    payload = _recover_codex_payload(
        step,
        plan_dir=plan_dir,
        output_path=output_path,
        raw=raw,
    )
    if payload is None:
        raise CliError("parse_error", f"Output file {output_path.name} was not valid JSON and no fallback found", extra={"raw_output": raw})
    raw_session_id = extract_session_id(raw)
    session_id = session.get("id") if persistent and not fresh else None
    if persistent and not session_id:
        session_id = raw_session_id or session.get("id")
        if not session_id:
            raise CliError(
                "worker_error",
                f"Could not determine Codex session id for persistent {step} step",
                extra={"raw_output": raw},
            )
    trace_output = raw if json_trace else None
    # Capture real codex token usage / USD cost from the rollout JSONL.
    # session_id may be None for ephemeral runs; in that case try to recover
    # the auto-assigned id from the run output so we can still bill the step.
    cost_session_id = raw_session_id if fresh else (session_id or raw_session_id)
    session_entry = {}
    if isinstance(state.get("sessions"), dict):
        candidate_entry = state["sessions"].get(session_key, {})
        if isinstance(candidate_entry, dict) and candidate_entry.get("id") == cost_session_id:
            session_entry = candidate_entry
    cost_usd, prompt_tokens, completion_tokens, model_actual, current_totals = _codex_step_cost(
        cost_session_id, session_entry
    )
    if current_totals is not None:
        # Persist the running totals so the next step in the same session
        # only bills its own delta. We mutate the existing session entry
        # when present; otherwise stash a minimal record under session_key.
        if isinstance(state.get("sessions"), dict):
            entry = state["sessions"].setdefault(session_key, {})
            if isinstance(entry, dict):
                if cost_session_id:
                    entry["id"] = cost_session_id
                entry["last_total_tokens"] = dict(current_totals)
    if cost_usd == 0.0 and cost_session_id and current_totals is None:
        # Don't crash; just leave a breadcrumb so operators can investigate
        # missing rollouts (codex stored elsewhere, permission issue, etc.).
        print(
            f"[megaplan] Could not locate codex rollout for session "
            f"{cost_session_id}; step cost will be recorded as $0.00",
            flush=True,
        )
    return WorkerResult(
        payload=payload,
        raw_output=raw,
        duration_ms=result.duration_ms,
        cost_usd=cost_usd,
        session_id=session_id,
        trace_output=trace_output,
        rendered_prompt=prompt,
        model_actual=model_actual,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=prompt_tokens + completion_tokens,
    )


def _is_agent_available(agent: str) -> bool:
    """Check if an agent is available (CLI binary or vendored for hermes)."""
    if agent == "hermes":
        # The legacy filesystem probe pointed at megaplan/workers/agent/, which
        # has never existed — run_agent.py lives one directory up at
        # megaplan/agent/. The probe therefore always returned False on every
        # install, and the downstream "pip install 'megaplan-harness[agent]'"
        # error message fired even when the agent runtime was fully present.
        # Importing megaplan.agent triggers the sys.path side effect at
        # megaplan/agent/__init__.py that makes run_agent / hermes_state
        # resolvable; we probe both so a partial install also fails closed.
        try:
            import megaplan.agent
            import importlib
            import sys
            from pathlib import Path

            agent_dir = str(Path(megaplan.agent.__file__).resolve().parent)
            if agent_dir not in sys.path:
                sys.path.insert(0, agent_dir)

            for module_name in ("run_agent", "hermes_state", "tools", "tools.registry"):
                module = sys.modules.get(module_name)
                module_file = getattr(module, "__file__", None)
                if (
                    module is not None
                    and (
                        not module_file
                        or not str(Path(module_file).resolve()).startswith(agent_dir)
                    )
                ):
                    sys.modules.pop(module_name, None)
            importlib.invalidate_caches()
            from run_agent import AIAgent  # noqa: F401
            from hermes_state import SessionDB  # noqa: F401
        except ImportError:
            return False
        return True
    if agent in {"claude", "shannon"}:
        from megaplan._core.io import is_shannon_available
        return is_shannon_available()
    return bool(shutil.which(agent))


def _agent_requested_explicitly(step: str, args: argparse.Namespace) -> bool:
    if getattr(args, "hermes", None) is not None:
        return True
    if getattr(args, "agent", None):
        return True
    for phase_model in getattr(args, "phase_model", None) or []:
        if "=" not in phase_model:
            continue
        phase_step, _phase_spec = phase_model.split("=", 1)
        if phase_step == step:
            return True
    return False


def _runtime_fallback_candidates(current_agent: str) -> list[str]:
    return [agent for agent in detect_available_agents() if agent != current_agent]


def resolve_agent_mode(step: str, args: argparse.Namespace, *, home: Path | None = None) -> AgentMode:
    """Returns an :class:`AgentMode` with agent, mode, refreshed, model, effort, resolved_model.

    Both agents default to persistent sessions.  Use --fresh to start a new
    persistent session (break continuity) or --ephemeral for a truly one-off
    call with no session saved.

    The model is extracted from compound agent specs (e.g. 'hermes:openai/gpt-5')
    or from --phase-model / --hermes CLI flags.  For bare ``claude`` /
    ``codex`` specs (no explicit model), the pinned default model is resolved
    and stored in ``resolved_model``.
    """
    model: str | None = None
    effort: str | None = None

    explicit_agent_spec = getattr(args, "agent", None)
    explicit_hermes_flag = getattr(args, "hermes", None)
    explicit_agent_override = bool(explicit_agent_spec) or explicit_hermes_flag is not None
    live_phase_model_steps = getattr(args, "_live_phase_model_steps", None)
    live_phase_model_steps_known = live_phase_model_steps is not None
    if live_phase_model_steps is None:
        live_phase_model_steps = {
            pm.split("=", 1)[0]
            for pm in (getattr(args, "phase_model", None) or [])
            if "=" in pm
        }

    # Check --phase-model overrides first when they came from the current CLI.
    # Persisted phase_model entries are merged into args by profile expansion,
    # but an explicit recovery flag like `execute --agent codex` must be able
    # to override those stale persisted routes. If callers have not supplied
    # provenance, preserve the historical phase_model-first behavior.
    phase_models = getattr(args, "phase_model", None) or []
    phase_model_matches = (
        not explicit_agent_override
        or not live_phase_model_steps_known
        or step in live_phase_model_steps
    )
    if phase_model_matches:
        for pm in phase_models:
            if "=" in pm:
                pm_step, pm_spec = pm.split("=", 1)
                if pm_step == step:
                    pm_parsed = parse_agent_spec(pm_spec)
                    agent = pm_parsed.agent
                    model = pm_parsed.model
                    effort = pm_parsed.effort
                    break
        else:
            phase_model_matches = False

    if not phase_model_matches:
        # Check --hermes flag
        hermes_flag = explicit_hermes_flag
        if hermes_flag is not None:
            agent = "hermes"
            if isinstance(hermes_flag, str) and hermes_flag:
                model = hermes_flag
        else:
            # Check explicit --agent flag
            explicit = explicit_agent_spec
            if explicit:
                explicit_parsed = parse_agent_spec(explicit)
                agent = explicit_parsed.agent
                model = explicit_parsed.model
                effort = explicit_parsed.effort
            else:
                # Fall back to config / defaults
                config = load_config(home)
                spec = config.get("agents", {}).get(step) or DEFAULT_AGENT_ROUTING[step]
                spec_parsed = parse_agent_spec(spec)
                agent = spec_parsed.agent
                model = spec_parsed.model
                effort = spec_parsed.effort

    # Validate agent availability
    # MEGAPLAN_MOCK_WORKERS=1 bypasses availability for explicit Shannon
    if os.environ.get("MEGAPLAN_MOCK_WORKERS") == "1" and agent == "shannon":
        pass  # Skip availability check; worker handles mock mode
    elif not _is_agent_available(agent):
        is_explicit = _agent_requested_explicitly(step, args)
        if is_explicit:
            if agent == "hermes":
                raise CliError(
                    "agent_deps_missing",
                    "hermes backend requires: pip install 'megaplan-harness[agent]'",
                )
            if agent == "shannon":
                from megaplan._core.io import shannon_missing_deps
                missing = shannon_missing_deps()
                raise CliError(
                    "agent_deps_missing",
                    f"Shannon requires: {', '.join(missing)}. "
                    "Install with: npm install -g @dexh/shannon@0.0.2",
                )
            if agent == "claude":
                from megaplan._core.io import shannon_missing_deps
                missing = shannon_missing_deps()
                raise CliError(
                    "agent_deps_missing",
                    f"Claude routes through Shannon and requires: {', '.join(missing)}. "
                    "Install with: npm install -g @dexh/shannon@0.0.2",
                )
            raise CliError("agent_not_found", f"Agent '{agent}' not found on PATH")
        # For hermes via agent=="hermes" config default when not explicitly requested,
        # give a specific error
        if agent == "hermes":
            raise CliError(
                "agent_deps_missing",
                "hermes backend requires: pip install 'megaplan-harness[agent]'",
            )
        # Try fallback
        available = detect_available_agents()
        if not available:
            raise CliError(
                "agent_not_found",
                "No supported agents found. Install claude or codex, or pip install 'megaplan-harness[agent]' for hermes.",
            )
        fallback = available[0]
        args._agent_fallback = {
            "requested": agent,
            "resolved": fallback,
            "reason": f"{agent} not available",
        }
        agent = fallback
        model = None  # Reset model when falling back
        effort = None

    ephemeral = getattr(args, "ephemeral", False)
    fresh = getattr(args, "fresh", False)
    persist = getattr(args, "persist", False)
    conflicting = sum([fresh, persist, ephemeral])
    if conflicting > 1:
        raise CliError("invalid_args", "Cannot combine --fresh, --persist, and --ephemeral")
    # Resolve default model for bare premium agent specs.
    resolved_model: str | None = model
    if resolved_model is None and agent in ("claude", "codex"):
        resolved_model = resolved_default_model_for_agent(agent)

    if ephemeral:
        return AgentMode(
            agent=agent,
            mode="ephemeral",
            refreshed=True,
            model=model,
            effort=effort,
            resolved_model=resolved_model,
        )
    refreshed = fresh
    # Review with Claude: default to fresh to avoid self-bias (principle #5)
    if step == "review" and agent == "claude":
        if persist and not getattr(args, "confirm_self_review", False):
            raise CliError("invalid_args", "Claude review requires --confirm-self-review when using --persist")
        if not persist:
            refreshed = True
    return AgentMode(
        agent=agent,
        mode="persistent",
        refreshed=refreshed,
        model=model,
        effort=effort,
        resolved_model=resolved_model,
    )


def run_step_with_worker(
    step: str,
    state: PlanState,
    plan_dir: Path,
    args: argparse.Namespace,
    *,
    root: Path,
    resolved: tuple[str, str, bool, str | None] | AgentMode | None = None,
    prompt_override: str | None = None,
    prompt_kwargs: dict[str, Any] | None = None,
) -> tuple[WorkerResult, str, str, bool]:
    am = resolved or resolve_agent_mode(step, args)
    agent = am.agent if isinstance(am, AgentMode) else am[0]
    mode = am.mode if isinstance(am, AgentMode) else am[1]
    refreshed = am.refreshed if isinstance(am, AgentMode) else am[2]
    model = am.model if isinstance(am, AgentMode) else am[3]
    effort = am.effort if isinstance(am, AgentMode) else None
    resolved_model = am.resolved_model if isinstance(am, AgentMode) else am[3]
    # Cross-call persistence is only valid for execute-shaped phases. Every
    # other phase receives all needed context in its prompt, so resuming prior
    # planner/critic/reviewer sessions risks cache-replay no-ops.
    effective_refreshed = refreshed or step not in _CROSS_CALL_PERSISTENT_STEPS
    explicit_agent = _agent_requested_explicitly(step, args)
    attempted_agents: set[str] = set()
    while True:
        attempted_agents.add(agent)
        try:
            if agent == "hermes":
                # Deferred import to avoid circular import (hermes_worker imports from workers)
                from megaplan.workers.hermes import run_hermes_step
                worker = run_hermes_step(
                    step,
                    state,
                    plan_dir,
                    root=root,
                    fresh=effective_refreshed,
                    model=model,
                    effort=effort,
                    prompt_override=prompt_override,
                )
            elif agent in ("claude", "shannon"):
                # Both the ``claude`` agent (Claude via the shannon CLI, e.g.
                # the ``partnered`` profile) and the explicit ``shannon`` agent
                # run through run_shannon_step. A stalled SSE stream now surfaces
                # promptly as a retryable ``worker_stall`` (idle-output watchdog
                # in run_command) instead of hanging until the coarse phase
                # wall-clock ``worker_timeout``. Give it the same bounded one-shot
                # retry the codex branch grants transient failures so a single
                # stall retries (fresh session) rather than failing the plan.
                from megaplan.workers.shannon import run_shannon_step
                shannon_kwargs: dict[str, Any] = dict(
                    root=root,
                    prompt_override=prompt_override,
                    prompt_kwargs=prompt_kwargs,
                    effort=effort,
                    model=resolved_model,
                )
                if agent == "claude":
                    shannon_kwargs["session_agent"] = "claude"
                attempted_retry = False
                while True:
                    try:
                        worker = run_shannon_step(
                            step,
                            state,
                            plan_dir,
                            fresh=effective_refreshed,
                            **shannon_kwargs,
                        )
                        break
                    except CliError as error:
                        if (
                            attempted_retry
                            or step in _EXECUTE_STEPS
                            or error.code not in {"worker_stall", "worker_timeout", "connection_error"}
                        ):
                            raise
                        attempted_retry = True
                        # Retry on a fresh session so a wedged stream is not
                        # resumed back into the same stall.
                        effective_refreshed = True
                        continue
            else:
                attempted_retry = False
                while True:
                    try:
                        worker = run_codex_step(
                            step,
                            state,
                            plan_dir,
                            root=root,
                            persistent=(mode == "persistent"),
                            fresh=effective_refreshed,
                            json_trace=(step == "execute"),
                            prompt_override=prompt_override,
                            prompt_kwargs=prompt_kwargs,
                            effort=effort,
                            model=resolved_model,
                        )
                        break
                    except CliError as error:
                        session_id = error.extra.get("session_id")
                        if (
                            attempted_retry
                            or step in _EXECUTE_STEPS
                            or error.code not in {"worker_timeout", "connection_error"}
                        ):
                            raise
                        attempted_retry = True
                        if mode == "persistent" and isinstance(session_id, str) and session_id:
                            apply_session_update(
                                state,
                                step,
                                agent,
                                session_id,
                                mode=mode,
                                refreshed=effective_refreshed,
                                model=resolved_model,
                            )
                            effective_refreshed = step not in _CROSS_CALL_PERSISTENT_STEPS
                        continue
            return worker, agent, mode, effective_refreshed
        except CliError as error:
            if explicit_agent or error.code not in {"auth_error", "connection_error"}:
                raise
            fallback_candidates = [
                candidate
                for candidate in _runtime_fallback_candidates(agent)
                if candidate not in attempted_agents
            ]
            if not fallback_candidates:
                raise
            fallback_agent = fallback_candidates[0]
            args._agent_fallback = {
                "requested": agent,
                "resolved": fallback_agent,
                "reason": f"{agent} runtime unhealthy: {error.code}",
            }
            agent = fallback_agent
            model = None
            effective_refreshed = True
