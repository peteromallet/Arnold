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
from megaplan.observability.routing_ledger import (
    format_selected_spec,
    normalize_routing_phase,
    record_step_routing,
)
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


from megaplan.workers._mock_payloads import _EXECUTE_STEPS, _build_mock_payload

_CROSS_CALL_PERSISTENT_STEPS = _EXECUTE_STEPS
_CODEX_TEMPLATE_WRITE_STEPS = {"critique", "review"}

# Shared mapping from step name to schema filename, used by both
# run_claude_step and run_codex_step.
STEP_SCHEMA_FILENAMES: dict[str, str] = {
    "plan": "plan.json",
    "prep": "prep.json",
    "prep-triage": "prep_triage.json",
    "prep-research": "research.json",
    "prep-distill": "prep.json",
    "revise": "revise.json",
    "critique": "critique.json",
    "critique_evaluator": "critique_evaluator.json",
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
    step: SCHEMAS.get(filename, {}).get("required", [])
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


# Inter-event idle bound for the shannon worker (Claude via the shannon CLI).
#
# HISTORY (2026-05-24): shannon was launched with ``--output-format=json``, a
# FULLY BUFFERED format — shannon accumulated the whole turn (init + per-turn
# assistant/result) and wrote ONE ``JSON.stringify([...])`` array to stdout only
# at turn end. With no incremental stdout, the watchdog below (which resets
# ``last_output`` only on real stdout/stderr chunks, _impl.py:420) degenerated
# into a coarse total-turn DURATION cap: it effectively timed turn-start →
# turn-end. A legitimately long single Opus turn that ran silent past this bound
# was killed as a false ``worker_stall``.
#
# FIX (2026-05-28): shannon is now launched with ``--output-format=stream-json``
# (megaplan/workers/shannon.py), which emits one JSON event per line (NDJSON) AS
# work happens — ``system/init`` after session discovery, optional ``hook_*``
# rows, per-turn ``assistant`` + ``result``, and a trailing ``shannon_session``
# metadata row on cleanup. Each line flushes to stdout, so the watchdog resets
# ``last_output`` on real progress and this value once again behaves as a TRUE
# inter-event idle bound rather than a duration cap. A long legit turn keeps the
# timer reset via incremental events; only a genuinely hung turn (no event for
# the whole window) trips it.
#
# CAVEAT: the bound is only as fine-grained as shannon's event cadence. The
# heaviest gap is WITHIN a single ``waitForAssistantReply`` — shannon polls
# Claude's transcript .jsonl, which is written one row per COMPLETED content
# block, so a single very long thinking/answer block still emits no event until
# it finishes. Real transcripts show within-block gaps up to ~363s.
#
# TIGHTENED (2026-05-29): the shannon ``liveness_probe`` now treats Claude's
# transcript .jsonl mtime as the trusted progress signal (it advances as content
# blocks/tool events flush, INCLUDING mid-turn — finer-grained than the NDJSON
# events on stdout), and NO LONGER counts tmux pane churn as progress. Because a
# healthy slow turn keeps the idle clock reset via that transcript-mtime probe,
# the raw inter-event bound no longer needs ~2.5x headroom over the worst-case
# within-block gap. A WEDGED Claude (stalled SSE — sockets ESTABLISHED, 0% CPU)
# repaints its pane but writes NO transcript, so the probe correctly reads it as
# idle; lowering the bound from 900s to 300s makes such a wedge fail fast
# (~5 min) and retry instead of burning ~15 min per turn. 300s still sits below
# the 363s observed within-block gap only when the transcript is genuinely
# static for that long, which the probe distinguishes from a hang. Override via
# SHANNON_STREAM_READ_TIMEOUT.
# (The hermes path, which streams real SSE chunks, uses its own inter-chunk
# bound — HERMES_STREAM_READ_TIMEOUT — and is unaffected.)
DEFAULT_WORKER_STREAM_IDLE_TIMEOUT_SECONDS = 300.0

# Guaranteed backstop for the liveness-probe rescue path (_impl.py run_command).
# The probe's transcript-mtime "progress" signal can be wrong (e.g. it globs the
# wrong Claude project dir and falls into its no-signal branch that returns True
# forever — the exact bug that let a wedged turn keep its idle clock reset past
# the 300s bound). This caps how long a turn that has produced ZERO real
# stdout/stderr may be kept alive by probe rescues alone, INDEPENDENT of the
# probe. NDJSON events from a healthy shannon turn reset the real-output clock,
# so this only fires on a genuinely stdout-silent turn. Sits below the 2h
# wall-clock ``timeout`` so a wedge dies in minutes even if the probe lies; the
# slug-correct probe is the primary path and kills a wedge at ~the idle bound
# (~5 min). Override via SHANNON_PROBE_RESCUE_CAP_SECONDS.
DEFAULT_PROBE_RESCUE_CAP_SECONDS = 600.0
DEFAULT_CODEX_EXECUTOR_SESSION_HEADROOM_TOKENS = 80_000_000
CODEX_EXECUTOR_SESSION_HEADROOM_ENV = "MEGAPLAN_CODEX_EXECUTOR_SESSION_HEADROOM_TOKENS"


def _worker_stream_idle_timeout_seconds() -> float:
    """Inter-event idle bound (seconds) for the shannon worker.

    With shannon on ``--output-format=stream-json`` (see the constant comment
    above) this is a genuine inter-event idle bound: incremental NDJSON events
    reset the watchdog, so it only trips when shannon emits NO event for the
    whole window (a hung turn or a >window within-block gap). Configurable via
    ``SHANNON_STREAM_READ_TIMEOUT``. Defaults to 5 min — the transcript-mtime
    liveness probe keeps a healthy slow turn's idle clock reset mid-turn, so a
    wedged turn (no transcript growth) fails fast and retries instead of burning
    the old 15 min window. Clamped to a sane floor.
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


def _probe_rescue_cap_seconds() -> float:
    """Max wall-clock seconds a stdout-silent turn may be kept alive by probe
    rescues alone (see ``DEFAULT_PROBE_RESCUE_CAP_SECONDS``).

    Configurable via ``SHANNON_PROBE_RESCUE_CAP_SECONDS``. Clamped to a generous
    floor so it can never undercut a legitimately long probe-rescued turn (or the
    short silent workers the idle-timeout tests rely on) — its sole job is to kill
    a pathological wedge whose probe signal is unreadable, not to second-guess a
    working probe.
    """
    try:
        value = float(os.getenv(
            "SHANNON_PROBE_RESCUE_CAP_SECONDS",
            DEFAULT_PROBE_RESCUE_CAP_SECONDS,
        ))
    except (TypeError, ValueError):
        value = DEFAULT_PROBE_RESCUE_CAP_SECONDS
    return max(value, 120.0)


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
    # Populated by the Shannon worker so the receipt records the rolled
    # session plan (kind, session_id, voice, pre-turn kinds + pre_sleep_s).
    # ``None`` for non-Shannon workers.
    shannon_plan: dict[str, Any] | None = None

    @classmethod
    def from_agent_result(cls, agent_result: Any) -> WorkerResult:
        """Project a runtime ``AgentResult`` into the worker compatibility type."""
        return cls(
            payload=agent_result.payload,
            raw_output=agent_result.raw_output,
            duration_ms=agent_result.duration_ms,
            cost_usd=agent_result.cost_usd,
            session_id=agent_result.session_id,
            trace_output=agent_result.trace_output,
            rendered_prompt=agent_result.rendered_prompt,
            model_actual=agent_result.model_actual,
            prompt_tokens=agent_result.prompt_tokens,
            completion_tokens=agent_result.completion_tokens,
            total_tokens=agent_result.total_tokens,
            shannon_plan=agent_result.shannon_plan,
        )

    def to_agent_result(self) -> Any:
        """Project the worker compatibility type into the runtime ``AgentResult``."""
        from megaplan.agent_runtime import AgentResult

        return AgentResult(
            payload=self.payload,
            raw_output=self.raw_output,
            duration_ms=self.duration_ms,
            cost_usd=self.cost_usd,
            session_id=self.session_id,
            trace_output=self.trace_output,
            rendered_prompt=self.rendered_prompt,
            model_actual=self.model_actual,
            prompt_tokens=self.prompt_tokens,
            completion_tokens=self.completion_tokens,
            total_tokens=self.total_tokens,
            shannon_plan=self.shannon_plan,
        )


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
    pre_first_byte_timeout: float | None = None,
    liveness_probe: Callable[[], bool] | None = None,
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
            # Pre-first-byte watchdog state: distinct from idle_timeout. Set True
            # the moment any real stdout/stderr chunk arrives. The liveness
            # heartbeat does NOT flip this — that's the entire point: a wedged
            # codex subprocess produces zero output but keeps the heartbeat
            # ticking, which masks the stall. See diagnostic
            # /tmp/codex_wedge_diagnostic.md.
            first_byte_seen = [False]
            # Backstop tracker for the liveness-probe rescue path below. Unlike
            # ``last_output`` (which the probe resets when it believes the worker
            # is progressing), this is reset ONLY by real stdout/stderr bytes and
            # is NEVER touched by the probe. It bounds how long a stdout-SILENT
            # turn may be kept alive by probe rescues alone, so a wedge whose
            # transcript signal is unreadable for any reason (slug drift, probe
            # bug, exception) still dies within a hard multiple of the idle bound
            # instead of running to the 2h wall-clock ``timeout``.
            last_real_output = [time.monotonic()]

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
                    last_real_output[0] = time.monotonic()
                    first_byte_seen[0] = True
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
            # worker) OR the pre-first-byte watchdog (e.g. the codex worker), poll
            # process.wait() in short slices so we can also enforce those bounds
            # between slices. When both timeouts are None (no watchdog opt-in),
            # this collapses to the original single process.wait(timeout=timeout)
            # — no behavioral change for those callers.
            first_byte_deadline = (
                started + pre_first_byte_timeout
                if pre_first_byte_timeout is not None
                else None
            )
            if idle_timeout is not None or first_byte_deadline is not None:
                deadline = started + timeout
                try:
                    while True:
                        remaining = deadline - time.monotonic()
                        if remaining <= 0:
                            raise subprocess.TimeoutExpired(command, timeout)
                        # Poll on at most a 1s slice so both watchdogs fire promptly.
                        wait_slice = min(1.0, remaining)
                        try:
                            returncode = process.wait(timeout=wait_slice)
                            break
                        except subprocess.TimeoutExpired:
                            # Still running: check the pre-first-byte bound first.
                            # Only real stdout/stderr flips first_byte_seen; the
                            # heartbeat explicitly does not, so a wedged subprocess
                            # that produces zero bytes will trip this even while
                            # heartbeats keep ``state.json`` mtime fresh.
                            if (
                                first_byte_deadline is not None
                                and not first_byte_seen[0]
                                and time.monotonic() > first_byte_deadline
                            ):
                                kill_group(process)
                                returncode = process.poll() if process.poll() is not None else -1
                                heartbeat_stop.set()
                                for thread in threads:
                                    thread.join(timeout=1)
                                raise CliError(
                                    "codex_pre_first_byte_stall",
                                    (
                                        f"Worker produced no output before pre-first-byte "
                                        f"deadline ({pre_first_byte_timeout:.0f}s); "
                                        f"likely codex wedge at startup: "
                                        f"{' '.join(command[:3])}..."
                                    ),
                                    extra={
                                        "raw_output": _coerce_timeout_output(stdout_parts)
                                        + _coerce_timeout_output(stderr_parts)
                                    },
                                )
                            # Then the idle-output bound. Only real stdout/stderr
                            # resets last_output; the heartbeat does not.
                            if (
                                idle_timeout is not None
                                and time.monotonic() - last_output[0] > idle_timeout
                            ):
                                # Buffered-mode rescue: some workers (notably the
                                # shannon path, which drives Claude in a tmux pane
                                # under ``--output-format=json``) emit NOTHING on
                                # stdout/stderr for the entire turn — the CLI
                                # buffers its whole result. For those, an idle bound
                                # on stdout bytes alone degenerates into a hard
                                # total-turn wall-clock cap and KILLS healthy,
                                # actively-progressing turns (the original
                                # ``worker_stall`` with empty ``raw_output`` at
                                # exactly the idle bound). When a ``liveness_probe``
                                # is supplied, consult a REAL liveness signal (tmux
                                # pane content advancing, transcript .jsonl mtime
                                # moving) before killing: if the worker is alive and
                                # making progress, treat that as activity — reset the
                                # idle clock and keep waiting. Only a worker that is
                                # BOTH stdout-silent AND not progressing is killed,
                                # which still catches a genuinely hung/dead turn. The
                                # wall-clock ``timeout`` (worker_timeout_seconds)
                                # remains the hard upper bound.
                                if liveness_probe is not None:
                                    # Hard backstop: cap how long a stdout-SILENT
                                    # turn may be rescued by the probe alone. The
                                    # probe's "progress" signal (transcript mtime)
                                    # can be wrong — e.g. it globs the wrong
                                    # project dir and falls into its no-signal
                                    # branch that returns True forever — which is
                                    # exactly the failure that let a wedge keep its
                                    # idle clock reset past the bound. Once REAL
                                    # output (the only probe-independent signal) has
                                    # been absent longer than the rescue cap, stop
                                    # trusting the probe and kill. NDJSON events
                                    # from a healthy turn reset last_real_output, so
                                    # this never threatens a turn that is actually
                                    # emitting; the (now slug-correct) probe is the
                                    # primary path and kills a wedge at ~the idle
                                    # bound, so this only bites when the probe
                                    # signal is unreadable.
                                    probe_rescue_cap = _probe_rescue_cap_seconds()
                                    if (
                                        time.monotonic() - last_real_output[0]
                                        > probe_rescue_cap
                                    ):
                                        alive_and_progressing = False
                                    else:
                                        try:
                                            alive_and_progressing = bool(liveness_probe())
                                        except Exception:
                                            # A probe failure must never kill a
                                            # worker outright; fall back to the
                                            # conservative "treat as progress"
                                            # stance so a live turn is never
                                            # collateral. A truly dead turn is still
                                            # bounded by the probe_rescue_cap above
                                            # and the wall-clock timeout.
                                            alive_and_progressing = True
                                    if alive_and_progressing:
                                        if activity_callback is not None:
                                            try:
                                                activity_callback(
                                                    "liveness",
                                                    "buffered worker progressing "
                                                    "(probe); idle clock reset",
                                                )
                                            except Exception:
                                                pass
                                        last_output[0] = time.monotonic()
                                        continue
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


def _worker_isolated_env_vars() -> list[str]:
    """Return the list of env var names to per-worker filesystem-isolate.

    Driven by the config key ``execution.worker_isolated_env_vars`` (a list
    of env var names). Opt-in: an empty / unset list means no isolation and
    the worker env is built exactly as before. This is intentionally general
    — megaplan core knows nothing about any specific project's var names.

    A project whose CLI honours a "home"-style env var (e.g. Astrid's
    ``ASTRID_HOME`` / ``ASTRID_PROJECTS_ROOT``) can list those vars so each
    concurrent worker gets an isolated, throwaway state directory instead of
    sharing one global per-user dir — which otherwise lets one worker's stray
    session/state files spuriously fail another worker's test suite.
    """
    try:
        raw = get_effective("execution", "worker_isolated_env_vars")
    except KeyError:
        return []
    if not isinstance(raw, (list, tuple)):
        return []
    out: list[str] = []
    for name in raw:
        if isinstance(name, str) and name.strip():
            out.append(name.strip())
    return out


def _apply_worker_state_isolation(env: dict[str, str]) -> dict[str, str]:
    """Redirect configured env vars to fresh per-worker temp directories.

    For each var name in ``execution.worker_isolated_env_vars`` we mint a
    unique directory under the OS temp dir and point the var at it, mutating
    *env* in place. This isolates per-user filesystem state across concurrent
    workers. Directories are NOT eagerly deleted (a worker may spawn child
    processes that outlive this call); they are uniquely named under the
    system temp dir and left for the OS tmp reaper, which bounds leakage.

    No-ops when the config list is empty, so the existing env is untouched.
    Existing keys are overwritten only for the listed vars; every other key
    (API keys, codex/hermes/claude paths, MEGAPLAN_* ids) is preserved.
    """
    names = _worker_isolated_env_vars()
    if not names:
        return env
    base = Path(tempfile.gettempdir()) / "megaplan-worker-isolation"
    token = uuid.uuid4().hex[:12]
    for name in names:
        worker_dir = base / token / name
        try:
            worker_dir.mkdir(parents=True, exist_ok=True)
        except OSError:
            # If we cannot create the dir, leave the var as-is rather than
            # pointing the worker at a path that does not exist.
            continue
        env[name] = str(worker_dir)
    return env


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
    _apply_worker_state_isolation(env)
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
    _apply_worker_state_isolation(env)
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
    output_is_single_critique_check = (
        step == "critique"
        and output_path.name.startswith("critique_check_")
        and output_path.suffix == ".json"
    )
    if (
        prefer_output_file
        and file_payload is not None
        and (step != "critique" or output_is_template_file or output_is_single_critique_check)
    ):
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


# Steps the mock worker supports, in declaration order. The trace stub
# only fires for the two execute-shaped steps; everything else gets an
# empty trace. Update both sets to add a new step.
_MOCK_SUPPORTED_STEPS: tuple[str, ...] = (
    "plan", "prep", "prep-triage", "prep-research", "prep-distill", "loop_plan",
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


def _check_mock_safe() -> None:
    """Raise if MOCK_WORKERS is set but the process is not running under pytest.

    A stale ``MEGAPLAN_MOCK_WORKERS=1`` env var in a production context would
    silently produce synthetic output trusted as real.  This guard ensures the
    mock shortcut only engages inside a test run.
    """
    if "PYTEST_CURRENT_TEST" not in os.environ:
        raise CliError(
            "mock_worker_blocked",
            "MEGAPLAN_MOCK_WORKERS is set but the process is not running "
            "under pytest. Refusing to produce synthetic output in a "
            "non-test context. Unset MEGAPLAN_MOCK_WORKERS to run real "
            "workers.",
        )


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
_CODEX_EFFORT_ALIASES = {"xhigh": "high", "max": "high"}


def _normalize_codex_effort(effort: str | None) -> str | None:
    if effort is None:
        return None
    return _CODEX_EFFORT_ALIASES.get(effort, effort)


def _codex_model_flag(model: str | None) -> list[str]:
    """Build the ``-c model='...'`` codex flag, validating *model* first.

    Last-line-of-defense gate at the dispatch site: an upstream mis-parse
    (e.g. the historical ``codex:claude:sonnet`` bug, which yielded
    ``model='claude'``) must never be passed verbatim to the codex CLI as
    ``-c model='claude'``. ``parse_agent_spec`` now rejects such specs at the
    chokepoint, but this guard ensures the invariant holds even for callers
    that build a model string by another path. Returns an empty list when
    *model* is ``None`` (codex uses its configured default).
    """
    if model is None:
        return []
    from megaplan.types import _is_codex_model_name

    if not _is_codex_model_name(model):
        raise CliError(
            "invalid_codex_model",
            f"Refusing to launch codex with model={model!r}: not a recognised "
            f"codex/GPT-5.x model. This usually means a malformed agent spec "
            f"(e.g. 'codex:claude:sonnet') reached dispatch. Fix the phase_model "
            f"pin (e.g. via `megaplan override set-model` / `set-vendor`).",
        )
    return ["-c", f"model='{model}'"]


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
    output_path: Path | None = None,
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
        output_path=output_path,
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
    read_only: bool = False,
    output_path: Path | None = None,
) -> WorkerResult:
    if read_only and step not in {"prep-triage", "prep-distill", "critique", "review"}:
        raise CliError(
            "unsupported_step",
            f"Codex read-only runner does not support '{step}'",
        )
    effort = _normalize_codex_effort(effort)
    if effort is not None and effort not in _VALID_CODEX_EFFORTS:
        raise CliError("invalid_args", f"Unsupported codex effort level: {effort}")
    fresh = fresh or step not in _CROSS_CALL_PERSISTENT_STEPS
    if os.getenv(MOCK_ENV_VAR) == "1":
        _check_mock_safe()
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
    if output_path is None:
        out_handle = tempfile.NamedTemporaryFile("w+", encoding="utf-8", delete=False)
        out_handle.close()
        output_path = Path(out_handle.name)
    else:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
    prompt = prompt_override if prompt_override is not None else create_codex_prompt(
        step,
        state,
        plan_dir,
        root=root,
        **(prompt_kwargs or {}),
    )
    timeout_seconds = _codex_timeout_for_step("prep" if read_only else step)

    if read_only:
        command = [
            "codex",
            "exec",
            "--skip-git-repo-check",
            "--ephemeral",
            "-c",
            "sandbox_mode='read-only'",
            "-o",
            str(output_path),
        ]
        command.extend(_codex_model_flag(model))
        if effort is not None:
            command.extend(["-c", f"model_reasoning_effort={effort}"])
        command.extend(["--output-schema", str(schema_file), "-"])
    elif persistent and session.get("id") and not fresh:
        # codex exec resume does not support --output-schema; we rely on
        # validate_payload() after parsing the output file instead. It also
        # does not accept --add-dir; resumed sessions keep the workspace that
        # was granted when the session was created.
        command = ["codex", "exec", "resume"]
        if _trusted_container():
            command.append("--dangerously-bypass-approvals-and-sandbox")
        command.extend(_codex_model_flag(model))
        if effort is not None:
            command.extend(["-c", f"model_reasoning_effort={effort}"])
        command.extend(_codex_exec_mode_flags(step))
        # Cap tool-result output per message at 50k chars (defense-in-depth;
        # codex interprets this as tokens — 50k tokens ≈ 200k chars, generous
        # but bounded).  The hardcoded 10 KiB default is too small for test
        # output; 50k tokens is per-message only, no cross-message elision.
        command.extend(["-c", "tool_output_token_limit=50000"])
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
        command.extend(_codex_model_flag(model))
        if effort is not None:
            command.extend(["-c", f"model_reasoning_effort={effort}"])
        if not persistent:
            command.append("--ephemeral")
        command.extend(_codex_exec_mode_flags(step))
        # Cap tool-result output per message at 50k chars (defense-in-depth;
        # codex interprets this as tokens — 50k tokens ≈ 200k chars, generous
        # but bounded).  The hardcoded 10 KiB default is too small for test
        # output; 50k tokens is per-message only, no cross-message elision.
        command.extend(["-c", "tool_output_token_limit=50000"])
        if json_trace:
            command.append("--json")
        command.extend(["--output-schema", str(schema_file), "-"])

    try:
        # Pre-first-byte timeout: codex CLI can hang at startup (auth handshake,
        # default-endpoint connect, etc.) producing zero bytes while megaplan's
        # liveness heartbeat keeps the auto driver thinking everything is fine.
        # Bound the no-output startup phase to ~3min so wedges surface as a
        # retryable ``codex_pre_first_byte_stall`` instead of consuming the full
        # phase wall-clock. Env override:
        # MEGAPLAN_CODEX_PRE_FIRST_BYTE_TIMEOUT_S (default 180).
        try:
            pre_first_byte_s = float(
                os.getenv("MEGAPLAN_CODEX_PRE_FIRST_BYTE_TIMEOUT_S", "180")
            )
        except (TypeError, ValueError):
            pre_first_byte_s = 180.0
        result = run_command(
            command,
            cwd=Path.cwd(),
            stdin_text=prompt,
            env=_codex_child_env(turn_id=f'plan_worker_{state["name"]}'),
            timeout=timeout_seconds,
            activity_callback=_activity_callback_for_state(state, plan_dir),
            pre_first_byte_timeout=pre_first_byte_s if pre_first_byte_s > 0 else None,
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
                read_only=read_only,
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
                read_only=read_only,
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
                read_only=read_only,
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
            read_only=read_only,
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
            read_only=read_only,
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
            read_only=read_only,
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
        # install, and the downstream install guidance fired even when the
        # agent runtime was fully present.
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
                    "hermes backend requires the bundled runtime packages: pip install megaplan-harness (or pip install -e . in a source checkout; '[agent]' is only a no-op compatibility extra).",
                )
            if agent == "shannon":
                from megaplan._core.io import shannon_missing_deps
                missing = shannon_missing_deps()
                raise CliError(
                    "agent_deps_missing",
                    f"Shannon requires: {', '.join(missing)}. "
                    "Install bun (https://bun.sh) and ensure the vendored fork at megaplan/vendor/shannon/index.ts is present.",
                )
            if agent == "claude":
                from megaplan._core.io import shannon_missing_deps
                missing = shannon_missing_deps()
                raise CliError(
                    "agent_deps_missing",
                    f"Claude routes through Shannon and requires: {', '.join(missing)}. "
                    "Install bun (https://bun.sh) and ensure the vendored fork at megaplan/vendor/shannon/index.ts is present.",
                )
            raise CliError("agent_not_found", f"Agent '{agent}' not found on PATH")
        # For hermes via agent=="hermes" config default when not explicitly requested,
        # give a specific error
        if agent == "hermes":
            raise CliError(
                "agent_deps_missing",
                "hermes backend requires the bundled runtime packages: pip install megaplan-harness (or pip install -e . in a source checkout; '[agent]' is only a no-op compatibility extra).",
            )
        # Try fallback
        available = detect_available_agents()
        if not available:
            raise CliError(
                "agent_not_found",
                "No supported agents found. Install claude or codex, or install megaplan-harness (or pip install -e . in a source checkout) for hermes. The legacy '[agent]' extra is only a no-op compatibility alias.",
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
    read_only: bool = False,
    output_path: Path | None = None,
    worker_options: dict[str, Any] | None = None,
    record_routing: bool = True,
    ledger_phase: str | None = None,
    ledger_step_label: str | None = None,
    ledger_selected_spec: str | None = None,
    ledger_tier: int | None = None,
    ledger_complexity: int | None = None,
    ledger_tier_routing_active: bool = False,
) -> tuple[WorkerResult, str, str, bool]:
    am = resolved or resolve_agent_mode(step, args)
    agent = am.agent if isinstance(am, AgentMode) else am[0]
    mode = am.mode if isinstance(am, AgentMode) else am[1]
    refreshed = am.refreshed if isinstance(am, AgentMode) else am[2]
    model = am.model if isinstance(am, AgentMode) else am[3]
    effort = am.effort if isinstance(am, AgentMode) else None
    resolved_model = am.resolved_model if isinstance(am, AgentMode) else am[3]
    # Backstop: legacy callers (tests, older sites) still pass a 4-tuple
    # ``resolved=`` which drops ``resolved_model``. If we ended up with a
    # codex/claude agent but no resolved_model, auto-apply the pinned default
    # here so downstream dispatch is never invoked with model=None. The
    # diagnostic in /tmp/codex_wedge_diagnostic.md shows that this was the
    # silent path leading to the wedge.
    if resolved_model is None and agent in ("claude", "codex"):
        resolved_model = resolved_default_model_for_agent(agent)
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
                    output_path=output_path,
                    worker_options=worker_options,
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
                    read_only=read_only,
                    output_path=output_path,
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
                # Defensive guard: codex must receive an explicit model. The
                # diagnostic in /tmp/codex_wedge_diagnostic.md shows that when
                # ``resolved_model`` silently becomes ``None`` (e.g. via a
                # 4-tuple ``resolved=`` that drops the AgentMode's
                # ``resolved_model`` field), the codex CLI launches with no
                # ``-c model=...`` and hangs at startup. Fail loud instead.
                if os.getenv(MOCK_ENV_VAR) != "1":
                    assert resolved_model is not None and resolved_model != "", (
                        "run_step_with_worker about to invoke run_codex_step "
                        "with empty resolved_model. AgentMode.resolved_model "
                        "should hold e.g. 'gpt-5.5'. Upstream callers using a "
                        "4-tuple ``resolved=`` drop this field — pass the "
                        "AgentMode instance instead. See "
                        "/tmp/codex_wedge_diagnostic.md."
                    )
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
                            read_only=read_only,
                            output_path=output_path,
                        )
                        break
                    except CliError as error:
                        session_id = error.extra.get("session_id")
                        if (
                            attempted_retry
                            or step in _EXECUTE_STEPS
                            or error.code
                            not in {
                                "worker_timeout",
                                "connection_error",
                                "codex_pre_first_byte_stall",
                                "worker_error",
                            }
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
            if record_routing and (step != "execute" or ledger_step_label is not None):
                record_step_routing(
                    plan_dir,
                    phase=ledger_phase or normalize_routing_phase(step),
                    step_label=ledger_step_label or step,
                    agent=agent,
                    selected_spec=ledger_selected_spec
                    or format_selected_spec(agent, model, effort),
                    resolved_model=resolved_model,
                    actual_model=getattr(worker, "model_actual", None),
                    tier=ledger_tier,
                    complexity=ledger_complexity,
                    tier_routing_active=ledger_tier_routing_active,
                )
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
            effort = None
            # Re-resolve the default model for the new agent so codex/claude
            # fallback paths still get an explicit ``-c model=...`` and don't
            # hang on the CLI default. The original ``resolved_model`` belonged
            # to the previously-tried agent and is no longer valid here.
            resolved_model = (
                resolved_default_model_for_agent(fallback_agent)
                if fallback_agent in ("claude", "codex")
                else None
            )
            effective_refreshed = True
