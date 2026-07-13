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
from typing import Any, Callable, Literal

from arnold_pipelines.megaplan.audits.robustness import build_empty_template
from arnold_pipelines.megaplan.forms.provocations import select_active_checks
from arnold_pipelines.megaplan.fallback_chains import (
    classify_retryability,
    configured_fallback_chain_for_phase,
    decode_phase_model_value,
    fallback_observability_fields,
    is_same_family_operational_classification,
    provider_family,
)
from arnold_pipelines.megaplan.profiles import DEFAULT_AGENT_ROUTING, effective_premium_vendor
from arnold_pipelines.megaplan.schemas import SCHEMAS, get_execution_schema_key
from arnold_pipelines.megaplan.orchestration.progress import strip_progress_env
from arnold_pipelines.megaplan.observability.routing_ledger import (
    format_selected_spec,
    normalize_routing_phase,
    record_step_routing,
)
from arnold_pipelines.megaplan.types import (
    AgentMode,
    CliError,
    MOCK_ENV_VAR,
    PlanState,
    SessionInfo,
    format_agent_spec,
    is_premium_placeholder_agent,
    parse_agent_spec,
    resolved_default_model_for_agent,
    resolve_premium_placeholder_spec,
)
from arnold_pipelines.megaplan._core import (
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
from arnold_pipelines.megaplan._core.state import write_plan_state
from arnold_pipelines.megaplan.prompts import (
    _resolve_prompt_root,
    create_codex_prompt,
)
from arnold.execution.step_invocation import StepInvocation
from arnold_pipelines.megaplan.model_seam import (
    ModelBudgetError,
    ModelTier,
    ModelStructuralAuditError,
    audit_step_payload,
    capture_step_output,
    render_prompt_for_dispatch,
    render_step_message,
    schema_audits_step_payload,
)
from arnold_pipelines.megaplan.runtime.process import TmuxSession, kill_group, spawn
from arnold_pipelines.megaplan.runtime.engine_isolation import engine_write_barrier
from arnold_pipelines.megaplan.runtime.execution_environment import resolve_execution_environment
from arnold_pipelines.megaplan.runtime.execution_environment import (
    ExecutionEnvironment,
    classify_path_overlap,
    isolation_cli_error,
)


from arnold_pipelines.megaplan.workers._mock_payloads import _EXECUTE_STEPS, _build_mock_payload

_CROSS_CALL_PERSISTENT_STEPS = _EXECUTE_STEPS
_CODEX_WORKER_CHANNEL = "codex_cli"
_MUTATING_WORKER_STEPS = {"execute", "revise", "loop_execute"}

# Shared mapping from step name to schema filename, used by both
# run_claude_step and run_codex_step.
# Built from the authoritative StepContract registry.
from arnold_pipelines.megaplan.step_contracts import build_step_schema_filenames

STEP_SCHEMA_FILENAMES: dict[str, str] = build_step_schema_filenames()

# Derive required keys per step from SCHEMAS so they aren't duplicated.
_STEP_REQUIRED_KEYS: dict[str, list[str]] = {
    step: SCHEMAS.get(filename, {}).get("required", [])
    for step, filename in STEP_SCHEMA_FILENAMES.items()
}
_RETIRED_VALIDATE_PAYLOAD_STEPS = frozenset({
    "finalize", "critique", "review", "gate",
    "plan", "prep", "prep-triage", "prep-research", "prep-distill",
    "feedback", "critique_evaluator", "revise",
    "loop_plan", "loop_execute", "tiebreaker_researcher", "tiebreaker_challenger",
    "execute",
})


def _project_local_tmp_dir(base: Path) -> Path:
    """Return a writable temp directory inside the project tree.

    Codex's read-only sandbox is scoped to the repo root, so prompt and output
    temp files passed via ``@/path`` must live under ``base`` (typically the
    project root or the plan directory) rather than the system temp directory.
    """
    tmp = base / ".megaplan" / "worker_tmp"
    tmp.mkdir(parents=True, exist_ok=True)
    return tmp


def _normalize_stdin_text(stdin_text: str | None) -> str | None:
    """Read prompt-file contents when a worker is handed a file path.

    The codex path accepts prompt text via stdin. Some callers hand that seam a
    temp-file path containing the real prompt; if the path string reaches the
    model verbatim, the worker sees only a filename. When *stdin_text* names an
    existing file, read and return its contents instead.
    """
    if stdin_text is None:
        return None
    candidate = stdin_text.strip()
    if not candidate or "\n" in candidate or "\r" in candidate:
        return stdin_text
    try:
        path = Path(candidate).expanduser()
    except (TypeError, ValueError):
        return stdin_text
    if not path.is_file():
        return stdin_text
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return stdin_text


@dataclass
class CommandResult:
    command: list[str]
    cwd: Path
    returncode: int
    stdout: str
    stderr: str
    duration_ms: int

ProgressLivenessState = Literal["progressing", "alive_only", "stalled", "unknown"]
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
#
# THREE-CHANNEL LIVENESS MODEL (2026-06-10). The shannon ``liveness_probe`` no
# longer treats "silence == death". Silence is ambiguous: a healthy turn is
# legitimately silent while (a) running a long synchronous tool call (a 10-20 min
# ``pytest``) — Claude emits nothing and the transcript does not grow; or (b)
# thinking server-side for minutes — no tokens surfaced yet. A genuine wedge
# (stalled SSE: sockets ESTABLISHED, 0% CPU, receiving nothing) ALSO looks
# silent. Conflating these false-killed healthy turns. The probe now samples
# THREE independent channels and treats the turn as ALIVE if ANY advanced since
# the last sample, WEDGED only if ALL THREE are flat continuously for the idle
# window K (``SHANNON_STREAM_READ_TIMEOUT``, default 300s):
#   1. transcript .jsonl mtime/size advanced  (catches normal token streaming);
#   2. process-subtree CPU-time advanced       (catches the silent tool call);
#   3. API socket recv-bytes advanced          (catches the silent thinking).
# See ``build_three_channel_liveness_probe`` below and
# ``shannon._make_shannon_liveness_probe`` for the concrete samplers. Silence on
# its own NEVER kills; only all-three-flat-for-K does.
#
# Two distinct backstops still exist BELOW the three channels:
#
# ``DEFAULT_PROBE_RESCUE_CAP_SECONDS`` / ``SHANNON_PROBE_RESCUE_CAP_SECONDS`` —
# caps how long a turn that has produced ZERO real stdout/stderr may be kept
# alive by probe rescues alone, INDEPENDENT of the probe, in case the probe's
# signals are all unreadable (e.g. it globs the wrong project dir, or ps/nettop
# are missing). NDJSON events from a healthy shannon turn reset the real-output
# clock, so this only fires on a genuinely stdout-silent turn. It is RESET by
# real output, so it is NOT an absolute cap — see the next one.
DEFAULT_PROBE_RESCUE_CAP_SECONDS = 600.0

# Hard absolute per-turn backstop. This is intentionally much larger than the
# idle/probe rescue caps: it only bounds a genuinely runaway turn that keeps at
# least one liveness channel hot forever.
DEFAULT_TURN_HARD_CAP_SECONDS = 5400.0

DEFAULT_CODEX_EXECUTOR_SESSION_HEADROOM_TOKENS = 1_000_000
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


def _turn_hard_cap_seconds() -> float:
    """Hard ABSOLUTE per-turn wall-clock cap (see ``DEFAULT_TURN_HARD_CAP_SECONDS``).

    INDEPENDENT of the three-channel probe and the rescue cap; never reset by any
    signal. Stops an INFINITE run (e.g. a ``pytest`` stuck in an infinite loop
    keeping the CPU channel hot forever) even when the channels correctly report
    the turn as "alive". Configurable via ``SHANNON_TURN_HARD_CAP_SECONDS``.
    Clamped to a generous floor so it can never undercut a legitimately long
    test-plus-thinking turn — its sole job is to bound a genuine runaway.
    """
    try:
        value = float(os.getenv(
            "SHANNON_TURN_HARD_CAP_SECONDS",
            DEFAULT_TURN_HARD_CAP_SECONDS,
        ))
    except (TypeError, ValueError):
        value = DEFAULT_TURN_HARD_CAP_SECONDS
    # Floor: comfortably above the test_baseline_timeout default (3600s) so a
    # legitimate large test run plus thinking is never cut short.
    return max(value, 3600.0)


def build_three_channel_liveness_probe(
    *,
    transcript_sample: Callable[[], float | int | None],
    cpu_sample: Callable[[], float | int | None],
    socket_sample: Callable[[], float | int | None],
) -> Callable[[], bool]:
    """Compose three independent activity samplers into one liveness probe.

    This is the COMBINING / DECISION half of the three-channel liveness model —
    deliberately separated from the concrete samplers so it is unit-testable
    WITHOUT a live ``claude`` process, live sockets, or ``ps``/``nettop``. Each
    sampler returns a monotone-comparable token (a counter / mtime / byte total)
    or ``None`` when that channel is unreadable RIGHT NOW.

    Returned probe semantics (matches ``run_command``'s ``liveness_probe``
    contract: ``True`` == "alive, reset the idle clock", ``False`` == "wedged,
    proceed to kill"):

    * First call primes the baselines and returns ``True`` (no comparison yet).
    * On each later call a channel is "active" iff its token is readable now AND
      STRICTLY GREATER than its last readable value. The turn is ALIVE if ANY of
      the three channels is active.
    * The turn is WEDGED (``False``) only when ALL THREE channels are FLAT — i.e.
      every readable channel's token is unchanged. Because ``run_command`` only
      consults the probe after the idle window K has elapsed with no real output,
      a ``False`` here means all three were flat continuously across K → kill.
    * GRACEFUL DEGRADATION: a channel that returns ``None`` (tool unavailable,
      e.g. ``nettop`` missing, or no transcript yet) is "unknown", NOT "flat". A
      sample that raises is also treated as unknown. If EVERY channel is unknown
      we cannot prove a wedge, so we return ``True`` (defer to the rescue cap /
      hard cap / wall-clock ``timeout``) — a missing tool can never cause a false
      kill. Once a channel becomes readable its baseline is (re)established so the
      first readable sample is not mistaken for "advanced".
    """
    last: dict[str, float] = {}
    primed = [False]

    def _sample(name: str, fn: Callable[[], float | int | None]) -> float | None:
        try:
            value = fn()
        except Exception:
            return None
        if value is None:
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    def _probe() -> bool:
        samples = {
            "transcript": _sample("transcript", transcript_sample),
            "cpu": _sample("cpu", cpu_sample),
            "socket": _sample("socket", socket_sample),
        }

        if not primed[0]:
            for name, value in samples.items():
                if value is not None:
                    last[name] = value
            primed[0] = True
            return True

        any_active = False
        any_readable = False
        for name, value in samples.items():
            if value is None:
                # Unknown right now — neither active nor flat. Do not update the
                # baseline so a transient read failure can't swallow real growth.
                continue
            any_readable = True
            prev = last.get(name)
            if prev is None:
                # Channel just became readable; establish its baseline. Not
                # counted as activity (no prior value to advance from).
                last[name] = value
                continue
            if value > prev:
                any_active = True
            # Advance the high-water mark monotonically (never regress on a
            # transient lower read, e.g. a transcript rotation).
            if value > prev:
                last[name] = value

        if any_active:
            return True
        if not any_readable:
            # No channel could be read at all — cannot prove a wedge. Stay
            # conservative; the rescue cap / hard cap / wall-clock timeout bound
            # a genuinely dead turn so this never hangs forever.
            return True
        # At least one channel readable and ALL readable channels flat → wedged.
        return False

    return _probe


def _ps_children(pid: str) -> list[str]:
    """Return the direct child PIDs of *pid* via ``ps`` (portable; macOS+Linux)."""
    try:
        result = subprocess.run(
            ["ps", "-o", "pid=,ppid="],
            check=False,
            capture_output=True,
            text=True,
        )
    except (FileNotFoundError, OSError):
        return []
    if result.returncode != 0:
        return []
    children: list[str] = []
    for line in result.stdout.splitlines():
        parts = line.split()
        if len(parts) != 2:
            continue
        child, parent = parts
        if parent == pid:
            children.append(child)
    return children


def _process_tree_pids(roots: list[str], *, max_pids: int = 256) -> list[str]:
    """BFS the process subtree rooted at each pid in *roots* (descendants too)."""
    seen: list[str] = []
    seen_set: set[str] = set()
    frontier = [pid for pid in roots if pid]
    while frontier and len(seen) < max_pids:
        pid = frontier.pop()
        if pid in seen_set:
            continue
        seen_set.add(pid)
        seen.append(pid)
        frontier.extend(_ps_children(pid))
    return seen


def _cputime_to_seconds(raw: str) -> float | None:
    """Parse a ``ps`` ``cputime`` field (``[[DD-]HH:]MM:SS[.ss]``) to seconds."""
    raw = raw.strip()
    if not raw or raw == "-":
        return None
    days = 0
    if "-" in raw:
        day_str, _, raw = raw.partition("-")
        try:
            days = int(day_str)
        except ValueError:
            days = 0
    parts = raw.split(":")
    try:
        nums = [float(part) for part in parts]
    except ValueError:
        return None
    seconds = 0.0
    for value in nums:
        seconds = seconds * 60 + value
    return seconds + days * 86400.0


def _subtree_cputime_sample(roots: list[str]) -> float | None:
    """Return cumulative CPU time (seconds) consumed by the subtree of *roots*."""
    pids = _process_tree_pids(roots)
    if not pids:
        return None
    try:
        result = subprocess.run(
            ["ps", "-o", "pid=,cputime="],
            check=False,
            capture_output=True,
            text=True,
        )
    except (FileNotFoundError, OSError):
        return None
    if result.returncode != 0:
        return None
    pid_set = set(pids)
    total = 0.0
    saw_any = False
    for line in result.stdout.splitlines():
        parts = line.split(None, 1)
        if len(parts) != 2:
            continue
        pid, cputime = parts
        if pid not in pid_set:
            continue
        seconds = _cputime_to_seconds(cputime)
        if seconds is None:
            continue
        saw_any = True
        total += seconds
    return total if saw_any else None


def _path_progress_signal(path: Path | None) -> tuple[int, int] | None:
    """Return a monotone-comparable progress signal for *path* when readable."""
    if path is None:
        return None
    try:
        stat = path.stat()
    except OSError:
        return None
    return (max(int(stat.st_mtime_ns), 0), int(stat.st_size))


@dataclass
class CodexProgressLiveness:
    """Progress classifier for Codex turns that go silent during tool work.

    Execute turns often enter a long foreground tool call (`pytest`, build,
    shell script) after Codex has already emitted the JSON trace row that
    started the tool. During that window the Codex parent process can remain
    stdout-silent for many minutes even though the subprocess tree is actively
    working. Without a secondary progress signal the idle-output watchdog turns
    into a false total-turn cap.

    We treat the turn as `progressing` when any of these cheap local signals
    advances since the last probe:

    - the structured output file grows;
    - the Codex rollout JSONL grows (after `thread.started` reveals the session);
    - the Codex subprocess tree accumulates CPU time.

    A live child with readable but flat signals is only `alive_only` so
    `run_command` applies its grace cap. A dead child is `stalled`.
    """

    output_path: Path
    # Review is read-only and normally short.  Unlike execute, a review must
    # not let a spinning Codex/node process masquerade as useful work forever:
    # its JSON trace/rollout/output file are the authoritative evidence that
    # the model is actually advancing.  Execute keeps CPU sampling because a
    # legitimate long-running tool can be stdout-silent for minutes.
    include_cpu_signal: bool = True

    session_id: str | None = None
    _stdout_buffer: str = ""
    _child_pid: str | None = None
    _child_alive: Callable[[], bool] | None = None
    _last_output_signal: tuple[int, int] | None = None
    _last_rollout_signal: tuple[int, int] | None = None
    _last_cpu_signal: float | None = None

    def bind_process(self, process: Any) -> Callable[[], ProgressLivenessState]:
        try:
            pid = getattr(process, "pid", None)
        except Exception:
            pid = None
        self._child_pid = str(pid) if pid is not None else None
        self._child_alive = lambda: process.poll() is None
        return self.probe

    def activity_guard(self, kind: str, text: str) -> None:
        """Observe stdout JSONL so the probe can discover the Codex session id."""
        if kind != "stdout" or not text:
            return
        self._stdout_buffer += text
        lines = self._stdout_buffer.splitlines(keepends=True)
        if lines and not lines[-1].endswith(("\n", "\r")):
            self._stdout_buffer = lines.pop()
        else:
            self._stdout_buffer = ""
        for line in lines:
            stripped = line.strip()
            if not stripped.startswith("{"):
                continue
            try:
                payload = json.loads(stripped)
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict) and payload.get("thread_id"):
                self.session_id = str(payload["thread_id"])

    def _sample_rollout_signal(self) -> tuple[int, int] | None:
        if not self.session_id:
            return None
        return _path_progress_signal(_codex_session_jsonl_path(self.session_id))

    def _sample_cpu_signal(self) -> float | None:
        if not self._child_pid:
            return None
        return _subtree_cputime_sample([self._child_pid])

    def _observe(
        self,
        current: Any | None,
        attr_name: str,
    ) -> tuple[bool, bool]:
        if current is None:
            return False, False
        previous = getattr(self, attr_name)
        if previous is None:
            setattr(self, attr_name, current)
            return True, False
        if current > previous:
            setattr(self, attr_name, current)
            return True, True
        return True, False

    def probe(self) -> ProgressLivenessState:
        readable = False
        progressing = False

        signals: list[tuple[Any | None, str]] = [
            (_path_progress_signal(self.output_path), "_last_output_signal"),
            (self._sample_rollout_signal(), "_last_rollout_signal"),
        ]
        if self.include_cpu_signal:
            signals.append((self._sample_cpu_signal(), "_last_cpu_signal"))
        for current, attr_name in signals:
            signal_readable, signal_progressing = self._observe(current, attr_name)
            readable = readable or signal_readable
            progressing = progressing or signal_progressing

        if progressing:
            return "progressing"

        if self._child_alive is not None:
            try:
                if not bool(self._child_alive()):
                    return "stalled"
            except Exception:
                return "unknown"

        if readable:
            return "alive_only"
        return "unknown"


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
    # ``unpriced`` means usage was observed but no canonical model rate exists;
    # cost_usd remains 0.0 for backward-compatible numeric aggregation.
    cost_pricing: str | None = None
    # Populated by the Shannon worker so the receipt records the rolled
    # session plan (kind, session_id, voice, pre-turn kinds + pre_sleep_s).
    # ``None`` for non-Shannon workers.
    shannon_plan: dict[str, Any] | None = None
    rate_limit: dict[str, Any] | None = None
    worker_channel: str | None = None
    auth_channel: str | None = None
    auth_metadata: dict[str, Any] | None = None
    configured_specs: tuple[str, ...] = ()
    attempt_index: int = 0
    attempted_specs: tuple[str, ...] = ()
    failed_attempt_reasons: tuple[str, ...] = ()
    fallback_trigger: str | None = None

    @classmethod
    def from_agent_result(cls, agent_result: Any) -> WorkerResult:
        """Project a runtime ``AgentResult`` into the worker compatibility type."""
        metadata = getattr(agent_result, "metadata", {}) or {}
        rate_limit = getattr(agent_result, "rate_limit", None)
        if rate_limit is None:
            rate_limit = metadata.get("rate_limit")
            if not isinstance(rate_limit, dict):
                rate_limit = None
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
            cost_pricing=metadata.get("cost_pricing"),
            shannon_plan=agent_result.shannon_plan,
            rate_limit=rate_limit,
            worker_channel=metadata.get("worker_channel"),
            auth_channel=metadata.get("auth_channel"),
            auth_metadata=metadata.get("auth_metadata"),
            configured_specs=tuple(metadata.get("configured_specs", ())),
            attempt_index=int(metadata.get("attempt_index", 0) or 0),
            attempted_specs=tuple(metadata.get("attempted_specs", ())),
            failed_attempt_reasons=tuple(metadata.get("failed_attempt_reasons", ())),
            fallback_trigger=metadata.get("fallback_trigger"),
        )

    def to_agent_result(self) -> Any:
        """Project the worker compatibility type into the runtime ``AgentResult``."""
        from arnold_pipelines.megaplan.agent_runtime import AgentResult

        metadata = {
            key: value
            for key, value in {
                "rate_limit": self.rate_limit,
                "worker_channel": self.worker_channel,
                "auth_channel": self.auth_channel,
                "auth_metadata": self.auth_metadata,
                "cost_pricing": self.cost_pricing,
                "configured_specs": list(self.configured_specs),
                "attempt_index": self.attempt_index,
                "attempted_specs": list(self.attempted_specs),
                "failed_attempt_reasons": list(self.failed_attempt_reasons),
                "fallback_trigger": self.fallback_trigger,
            }.items()
            if value is not None
        }
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
            rate_limit=self.rate_limit,
            metadata=metadata,
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
    Missing or stale ``project_dir`` fails closed unless an explicit override
    was supplied.

    If the resolved path differs from the plan's stored ``project_dir``, a
    one-time informational line is printed so operators notice worktree
    divergence. (Callers that want a visually-loud operator warning should
    invoke :func:`warn_if_work_dir_differs_from_project_dir` from the phase
    entry point — this function keeps the log terse because it fires on every
    worker invocation.)
    """
    override = _WORK_DIR_OVERRIDE.get()
    if override is not None:
        resolved_override = Path(override).expanduser().resolve()
        if not resolved_override.is_dir():
            raise CliError(
                "invalid_work_dir",
                f"worker work-dir override does not exist or is not a directory: {resolved_override}",
            )
        return resolved_override
    try:
        raw_project_dir = state["config"]["project_dir"]
    except Exception as exc:
        raise CliError(
            "missing_project_dir",
            "plan state is missing config.project_dir; refusing to use process cwd for worker execution",
        ) from exc
    project_dir = Path(str(raw_project_dir)).expanduser().resolve()
    if not project_dir.is_dir():
        raise CliError(
            "stale_project_dir",
            f"plan config.project_dir does not exist or is not a directory: {project_dir}",
        )
    work_dir = project_dir
    resolved_work = work_dir.resolve()
    if project_dir is not None and resolved_work != project_dir:
        with _WORK_DIR_WARNED_LOCK:
            if resolved_work not in _WORK_DIR_WARNED:
                _WORK_DIR_WARNED.add(resolved_work)
                print(
                    f"[megaplan] Using plan's project_dir ({project_dir}) for "
                    f"subprocess --add-dir. Override with --work-dir if needed.",
                    flush=True,
                )
    return resolved_work


def _guard_mutating_worker_launch(step: str, state: PlanState, root: Path) -> None:
    if step not in _MUTATING_WORKER_STEPS:
        return
    env = resolve_execution_environment(root=root, state=state)
    proof = engine_write_barrier(env, step)
    _record_engine_verification(
        state,
        step=step,
        timing="before_worker",
        env=env,
        proof=(
            proof
            if isinstance(proof, dict)
            else proof.to_dict()
            if hasattr(proof, "to_dict")
            else {"provider": type(proof).__name__}
        ),
    )


def _record_engine_verification(
    state: PlanState,
    *,
    step: str,
    timing: str,
    env: ExecutionEnvironment,
    proof: dict[str, Any] | None = None,
) -> dict[str, Any]:
    meta = state.setdefault("meta", {})
    if not isinstance(meta, dict):
        meta = {}
        state["meta"] = meta
    verifications = meta.setdefault("engine_isolation_verifications", [])
    if not isinstance(verifications, list):
        verifications = []
        meta["engine_isolation_verifications"] = verifications
    record: dict[str, Any] = {
        "phase": step,
        "timing": timing,
        "engine_root": str(env.engine_root),
    }
    if proof is not None:
        record["proof"] = proof
    verifications.append(record)
    return record


def _verify_engine_after_mutating_worker(
    step: str,
    state: PlanState,
    root: Path,
    before_env: ExecutionEnvironment,
) -> None:
    del before_env
    if step not in _MUTATING_WORKER_STEPS:
        return
    after_env = resolve_execution_environment(root=root, state=state)
    _record_engine_verification(
        state,
        step=step,
        timing="after_worker",
        env=after_env,
    )


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
    activity_guard: Callable[[str, str], None] | None = None,
    idle_timeout: float | None = None,
    pre_first_byte_timeout: float | None = None,
    liveness_probe: Callable[[], bool] | None = None,
    progress_liveness_probe: Callable[[], ProgressLivenessState] | None = None,
    progress_liveness_factory: Callable[[Any], Callable[[], ProgressLivenessState] | None]
    | None = None,
    progress_liveness_grace_timeout: float | None = None,
    tmux_session: TmuxSession | None = None,
) -> CommandResult:
    stdin_text = _normalize_stdin_text(stdin_text)
    # Codex CLI (v0.137+) interprets a trailing "-" as "read the prompt from
    # stdin".  Older versions wedged on piped stdin, so the code previously wrote
    # the prompt to a temp file and passed "@/path/to/file".  Modern Codex treats
    # "@file" as a reference/attachment rather than the prompt itself, causing the
    # worker to hang waiting for instructions.  We now write the prompt to a temp
    # file and feed that file as stdin while keeping the trailing "-".
    stdin_path: Path | None = None
    if stdin_text is not None and command and command[-1] == "-":
        stdin_handle = tempfile.NamedTemporaryFile(
            "w+", encoding="utf-8", delete=False, dir=str(_project_local_tmp_dir(cwd))
        )
        stdin_handle.write(stdin_text)
        stdin_handle.flush()
        stdin_handle.close()
        stdin_path = Path(stdin_handle.name)
        # Keep the trailing "-" so codex reads the prompt from stdin.

    try:
        started = time.monotonic()
        timeout = timeout or get_effective("execution", "worker_timeout_seconds")
        if activity_callback is None and activity_guard is None:
            stdin_file: Any | None = None
            try:
                if stdin_path is not None:
                    stdin_file = open(stdin_path, "rb")
                process = subprocess.run(
                    command,
                    stdin=stdin_file if stdin_file is not None else subprocess.DEVNULL,
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
            finally:
                if stdin_file is not None:
                    stdin_file.close()
                if stdin_path is not None:
                    stdin_path.unlink(missing_ok=True)
            return CommandResult(
                command=command,
                cwd=cwd,
                returncode=process.returncode,
                stdout=process.stdout or "",
                stderr=process.stderr or "",
                duration_ms=int((time.monotonic() - started) * 1000),
            )

        stdin_path = None
        stdin_file = None
        try:
            if stdin_text is not None:
                # Large prompts written to a PIPE can deadlock: the producer
                # blocks when the pipe buffer fills before the consumer has
                # started draining stdin. Writing the prompt to a temp file and
                # letting the child read that file via stdin avoids the race.
                stdin_handle = tempfile.NamedTemporaryFile(
                    "w+", encoding="utf-8", delete=False, dir=str(_project_local_tmp_dir(cwd))
                )
                stdin_handle.write(stdin_text)
                stdin_handle.flush()
                stdin_handle.close()
                stdin_path = Path(stdin_handle.name)
                stdin_file = open(stdin_path, "rb")

            process = spawn(
                command,
                cwd=str(cwd),
                stdin=stdin_file if stdin_file is not None else subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=env,
            )
            if progress_liveness_probe is None and progress_liveness_factory is not None:
                try:
                    progress_liveness_probe = progress_liveness_factory(process)
                except Exception:
                    progress_liveness_probe = None
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
            last_progress_signal = [last_real_output[0]]
            guard_triggered = threading.Event()
            guard_error: list[CliError] = []

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
                    last_progress_signal[0] = time.monotonic()
                    first_byte_seen[0] = True
                    parts.append(chunk)
                    text = chunk.decode("utf-8", errors="replace")
                    if activity_guard is not None:
                        try:
                            activity_guard(kind, text)
                        except CliError as exc:
                            guard_error.append(exc)
                            guard_triggered.set()
                            return
                        except Exception as exc:
                            guard_error.append(
                                CliError(
                                    "activity_guard_error",
                                    f"Worker activity guard failed: {exc}",
                                )
                            )
                            guard_triggered.set()
                            return
                    if activity_callback is not None:
                        activity_callback(kind, text)

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
                    if activity_callback is None:
                        continue
                    try:
                        activity_callback("liveness", "worker subprocess alive")
                    except Exception:
                        pass

            threads.append(threading.Thread(target=_heartbeat, daemon=True))
            for thread in threads:
                thread.start()

            def _coerce_timeout_output(parts: list[bytes]) -> str:
                return b"".join(parts).decode("utf-8", errors="replace")

            def _combined_raw_output() -> str:
                return _coerce_timeout_output(stdout_parts) + _coerce_timeout_output(stderr_parts)

            def _raise_guard_error() -> None:
                error = guard_error[0] if guard_error else CliError(
                    "activity_guard_error",
                    "Worker activity guard stopped the subprocess.",
                )
                raw = _combined_raw_output()
                if raw:
                    existing = str(error.extra.get("raw_output", ""))
                    error.extra["raw_output"] = existing + raw if existing else raw
                raise error

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
            if (
                idle_timeout is not None
                or first_byte_deadline is not None
                or activity_guard is not None
                or progress_liveness_probe is not None
            ):
                deadline = started + timeout
                # Hard ABSOLUTE per-turn cap (three-channel liveness backstop).
                # Independent of the probe and never reset by any signal: it
                # bounds an INFINITE run that keeps a liveness channel hot forever
                # (e.g. a pytest stuck in an infinite loop spinning CPU). Only
                # armed on the shannon liveness path (a probe was supplied); other
                # callers keep their exact prior behaviour. Clamped at/below the
                # wall-clock ``timeout`` so it can only ever tighten, never loosen.
                hard_cap_deadline = (
                    started + min(_turn_hard_cap_seconds(), float(timeout))
                    if liveness_probe is not None
                    else None
                )
                try:
                    while True:
                        if guard_triggered.is_set():
                            kill_group(process)
                            heartbeat_stop.set()
                            for thread in threads:
                                thread.join(timeout=1)
                            _raise_guard_error()
                        remaining = deadline - time.monotonic()
                        if remaining <= 0:
                            raise subprocess.TimeoutExpired(command, timeout)
                        # Poll on short slices so watchdogs and guard failures
                        # fire promptly while reader threads keep collecting output.
                        wait_slice = min(0.1 if activity_guard is not None else 1.0, remaining)
                        try:
                            returncode = process.wait(timeout=wait_slice)
                            break
                        except subprocess.TimeoutExpired:
                            # Hard absolute cap first: fires regardless of probe
                            # channels or real output. A runaway that keeps a
                            # channel hot forever (infinite-loop pytest, a forever
                            # pinging socket) is killed here even though the probe
                            # would correctly call it "alive".
                            if (
                                hard_cap_deadline is not None
                                and time.monotonic() > hard_cap_deadline
                            ):
                                kill_group(process)
                                returncode = process.poll() if process.poll() is not None else -1
                                heartbeat_stop.set()
                                for thread in threads:
                                    thread.join(timeout=1)
                                cap = min(_turn_hard_cap_seconds(), float(timeout))
                                raise CliError(
                                    "worker_timeout",
                                    (
                                        f"Worker exceeded the hard per-turn cap "
                                        f"({cap:.0f}s; SHANNON_TURN_HARD_CAP_SECONDS); "
                                        f"runaway turn killed: {' '.join(command[:3])}..."
                                    ),
                                    extra={
                                        "raw_output": _coerce_timeout_output(stdout_parts)
                                        + _coerce_timeout_output(stderr_parts)
                                    },
                                )
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
                                if progress_liveness_probe is not None:
                                    try:
                                        liveness_state = progress_liveness_probe()
                                    except Exception:
                                        liveness_state = "unknown"
                                    if liveness_state == "progressing":
                                        if activity_callback is not None:
                                            try:
                                                activity_callback(
                                                    "liveness",
                                                    "worker progressing (probe); idle clock reset",
                                                )
                                            except Exception:
                                                pass
                                        now = time.monotonic()
                                        last_output[0] = now
                                        last_progress_signal[0] = now
                                        continue
                                    if liveness_state in {"alive_only", "unknown"}:
                                        grace = (
                                            progress_liveness_grace_timeout
                                            if progress_liveness_grace_timeout is not None
                                            else _probe_rescue_cap_seconds()
                                        )
                                        if time.monotonic() - last_progress_signal[0] <= grace:
                                            if activity_callback is not None:
                                                try:
                                                    activity_callback(
                                                        "liveness",
                                                        f"worker {liveness_state} (probe); "
                                                        "idle clock reset within grace",
                                                    )
                                                except Exception:
                                                    pass
                                            last_output[0] = time.monotonic()
                                            continue
                                    # "stalled" or expired alive_only/unknown
                                    # grace falls through to the centralized
                                    # worker_stall kill path below.
                                elif liveness_probe is not None:
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
            if guard_triggered.is_set():
                kill_group(process)
                heartbeat_stop.set()
                for thread in threads:
                    thread.join(timeout=1)
                _raise_guard_error()
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
        # Guard against UnboundLocalError when an early exception prevents
        # the stdin temp-file variables from being bound.
        stdin_file_local = locals().get("stdin_file")
        if stdin_file_local is not None:
            try:
                stdin_file_local.close()
            except Exception:
                pass
        stdin_path_local = locals().get("stdin_path")
        if stdin_path_local is not None:
            try:
                stdin_path_local.unlink(missing_ok=True)
            except Exception:
                pass
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
    # critique/review JSON, finalize.json). Without an explicit sandbox codex
    # defaults to on-request approval, which fails silently when stdin is the
    # prompt (no tty). Default everything to workspace-write sandbox mode so
    # codex auto-approves writes within configured writable_roots.
    return ["--sandbox", "workspace-write"]


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


def _codex_writable_roots(
    work_dir: Path | str,
    state: PlanState,
    env: ExecutionEnvironment,
    *,
    phase: str | None = None,
) -> list[str]:
    """Return Codex writable roots after engine root filtering.

    The target work dir is always present. Auto/configured extra roots are
    accepted only when they are disjoint from the engine root.
    """

    roots: list[tuple[Path, str]] = [(Path(work_dir).resolve(), "target_work_dir")]
    roots.extend((Path(root).resolve(), "auto") for root in _auto_writable_roots(Path(work_dir)))
    try:
        raw_extra = state.get("config", {}).get("extra_writable_roots", []) or []
        if isinstance(raw_extra, list):
            for root in raw_extra:
                if not isinstance(root, str):
                    continue
                path = Path(root)
                roots.append(
                    (
                        (Path(work_dir) / path).resolve() if not path.is_absolute() else path.resolve(),
                        "configured",
                    )
                )
    except Exception:
        pass

    seen: set[str] = set()
    filtered: list[str] = []
    trusted = _trusted_container()
    for root, source in roots:
        root_str = str(root)
        if root_str in seen:
            continue
        seen.add(root_str)
        overlap = classify_path_overlap(root, env.engine_root)
        if overlap != "disjoint" and not trusted:
            if _is_self_hosted_engine_target_root(root, source, state, env):
                filtered.append(root_str)
                continue
            if source == "auto" and not (root / ".git").exists():
                continue
            raise isolation_cli_error(
                "codex_writable_root_overlaps_engine",
                "Codex writable root overlaps the engine root; refusing engine-writable sandbox",
                env=env,
                extra={
                    "writable_root": root_str,
                    "writable_root_source": source,
                    "overlap": overlap,
                },
            )
        filtered.append(root_str)
    work_str = str(Path(work_dir).resolve())
    if work_str not in filtered:
        filtered.insert(0, work_str)
    return filtered


def _is_self_hosted_engine_target_root(
    root: Path,
    source: str,
    state: PlanState,
    env: ExecutionEnvironment,
) -> bool:
    """Allow only intentional self-hosted engine development writes.

    A normal target project must not receive writable access to a separate
    Megaplan engine checkout.  When the target, work, and engine roots are the
    same repository, however, the plan is explicitly operating on Megaplan
    itself; refusing the target root would make editable engine work
    impossible.  Keep the exception exact so parent/auto/configured roots that
    merely contain the engine stay blocked.
    """

    if source != "target_work_dir":
        return False
    configured_mode = ""
    try:
        configured_mode = str(
            state.get("config", {}).get("engine_isolation_mode", "")
            or state.get("config", {}).get("engine_isolation_provider", "")
        ).strip()
    except Exception:
        configured_mode = ""
    provider = (
        os.environ.get("MEGAPLAN_ENGINE_ISOLATION_PROVIDER", "")
        or os.environ.get("MEGPLAN_ENGINE_ISOLATION_PROVIDER", "")
        or configured_mode
    ).strip()
    if provider != "self_hosted_editable":
        return False
    return (
        root == env.engine_root
        and root == env.target_root
        and root == env.work_dir
    )


def _codex_sandbox_fingerprint(work_dir: Path | str, state: PlanState, env: ExecutionEnvironment) -> str:
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
    payload = {
        "trusted_container": _trusted_container(),
        "work_dir": str(Path(work_dir).resolve()),
        "writable_roots": [] if _trusted_container() else _codex_writable_roots(work_dir, state, env),
        "engine_root": str(env.engine_root),
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()[:16]


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
    requested_model: str | None = None,
) -> tuple[float, int, int, str | None, dict[str, Any] | None]:
    """Compute incremental cost (USD) and token deltas for one codex step.

    Looks up the rollout JSONL for ``session_id``, reads the cumulative
    ``total_token_usage``, and subtracts the ``last_total_tokens`` snapshot
    stored on ``session_entry`` (mutated in place to record the new totals).

    Returns ``(cost_usd, prompt_tokens_delta, completion_tokens_delta,
    model, current_total_usage)``. Unknown model rates produce numeric 0.0 for
    existing aggregation code; the caller records the explicit ``unpriced``
    status on the worker result. Missing usage never raises.
    """
    from arnold_pipelines.megaplan.pricing.codex import cost_from_codex_usage_dict

    if not session_id:
        return 0.0, 0, 0, requested_model, None
    path = _codex_session_jsonl_path(session_id)
    if path is None:
        return 0.0, 0, 0, requested_model, None
    current = _read_codex_total_token_usage(path)
    if current is None:
        return 0.0, 0, 0, requested_model, None
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
    model = requested_model or _read_codex_default_model()
    priced_cost = cost_from_codex_usage_dict(delta_usage, model)
    cost = priced_cost if priced_cost is not None else 0.0
    prompt_tokens = delta_usage["input_tokens"]  # already includes cached
    completion_tokens = (
        delta_usage["output_tokens"] + delta_usage["reasoning_output_tokens"]
    )
    return cost, prompt_tokens, completion_tokens, model, current


def _emit_codex_execute_llm_start(
    plan_dir: Path,
    *,
    model: str | None,
    prompt: str,
    json_trace: bool,
) -> None:
    try:
        from arnold_pipelines.megaplan.observability.events import EventKind, emit

        prompt_hash = (
            hashlib.sha256(prompt.encode("utf-8")).hexdigest()[:16]
            if prompt
            else None
        )
        emit(
            EventKind.LLM_CALL_START,
            plan_dir=plan_dir,
            phase="execute",
            payload={
                "provider": "codex",
                "model": model,
                "prompt_hash": prompt_hash,
                "streaming": bool(json_trace),
                "request_id": None,
            },
        )
    except Exception:
        pass


def _emit_codex_execute_llm_end(
    plan_dir: Path,
    *,
    request_id: str | None,
    model: str | None,
    tokens_in: int,
    tokens_out: int,
) -> None:
    try:
        from arnold_pipelines.megaplan.observability.events import EventKind, emit

        emit(
            EventKind.LLM_CALL_END,
            plan_dir=plan_dir,
            phase="execute",
            payload={
                "tokens_in": tokens_in,
                "tokens_out": tokens_out,
                "request_id": request_id,
                "model": model,
            },
        )
    except Exception:
        pass


def _emit_codex_execute_cost_recorded(
    plan_dir: Path,
    *,
    request_id: str | None,
    model: str | None,
    cost_usd: float,
) -> None:
    try:
        from arnold_pipelines.megaplan.observability.events import EventKind, emit

        emit(
            EventKind.COST_RECORDED,
            plan_dir=plan_dir,
            phase="execute",
            payload={
                "request_id": request_id,
                "cost_usd": float(cost_usd),
                "provider": "codex",
                "model": model,
            },
        )
    except Exception:
        pass


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


# DeepSeek and Kimi sometimes emit tool markup using ASCII XML tags and
# sometimes using DSML-style tags such as ``<｜DSML｜invoke name="write_file">``.
# Detect both forms so the recovery path can extract the payload instead of
# failing the whole worker turn.
_DSML_PREFIX = "\uff5cDSML\uff5c"
_DEEPSEEK_TOOL_TAG_RE = re.compile(
    rf"<(?P<name>(?:\{_DSML_PREFIX})?(?:read_file|file_read|read|search_files|file_search|search|"
    rf"web_extract|fetch_url|web_search|write_file|file_write|write|edit_file|"
    rf"patch|apply_patch|delete_file|run_command|bash|terminal|invoke|tool_call|"
    rf"tool_calls|tool_result))\b(?P<attrs>[^<>]*)>",
    re.IGNORECASE,
)
_DEEPSEEK_INVOKE_NAME_RE = re.compile(
    r"\bname=[\"'](?P<name>[^\"']+)[\"']",
    re.IGNORECASE,
)
_DEEPSEEK_MUTATING_TOOL_NAMES = frozenset(
    {
        "write_file",
        "file_write",
        "write",
        "edit_file",
        "patch",
        "apply_patch",
        "delete_file",
        "run_command",
        "bash",
        "terminal",
    }
)


def _deepseek_tool_markup_names(raw: str) -> set[str]:
    """Return tool-like XML tag names emitted in assistant text."""
    names: set[str] = set()
    if not raw or "<" not in raw:
        return names
    for match in _DEEPSEEK_TOOL_TAG_RE.finditer(raw):
        name = match.group("name")
        if name.startswith(_DSML_PREFIX):
            name = name[len(_DSML_PREFIX):]
        name = name.lower()
        if name == "invoke":
            invoked = _DEEPSEEK_INVOKE_NAME_RE.search(match.group("attrs") or "")
            if invoked:
                names.add(invoked.group("name").strip().lower())
            else:
                names.add(name)
            continue
        names.add(name)
    return names


def _looks_like_deepseek_tool_markup(raw: str) -> bool:
    return bool(_deepseek_tool_markup_names(raw))


def _contains_mutating_deepseek_tool_markup(raw: str) -> bool:
    return bool(_deepseek_tool_markup_names(raw).intersection(_DEEPSEEK_MUTATING_TOOL_NAMES))


def _critique_repair_context(
    *,
    check_id: str | None = None,
    question: str | None = None,
) -> str:
    bits: list[str] = []
    if check_id:
        bits.append(f"check {check_id!r}")
    if question:
        cleaned = " ".join(str(question).split())
        if cleaned:
            bits.append(f"question {cleaned[:180]!r}")
    return f" ({'; '.join(bits)})" if bits else ""


def _extract_json_candidates_from_raw(raw: str) -> list[dict[str, Any]]:
    """Extract plausible JSON payload objects from raw agent output."""
    # Some models (DeepSeek/Kimi) answer with write-style tool markup containing
    # the JSON payload. Recover that first so downstream extraction sees JSON.
    from arnold_pipelines.megaplan.workers.hermes import _extract_json_from_mutating_tool_markup

    recovered = _extract_json_from_mutating_tool_markup(raw)
    if recovered is not None:
        raw = recovered

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


def _looks_like_plan_markdown(text: str) -> bool:
    stripped = text.lstrip()
    if not stripped:
        return False
    if stripped.startswith("# "):
        return True
    if "## Overview" in text:
        return True
    return bool(re.search(r"(?m)^#{2,3}\s+Step\s+\d+:\s+.+$", text))


def _extract_plan_capture_input(raw_text: str) -> str | dict[str, Any]:
    candidate = _extract_json_from_raw(raw_text)
    if isinstance(candidate, dict):
        if isinstance(candidate.get("plan"), str):
            return candidate
        if isinstance(candidate.get("steps"), list):
            return candidate
        if isinstance(candidate.get("title"), str) and isinstance(candidate.get("overview"), str):
            return candidate
    if _looks_like_plan_markdown(raw_text):
        from arnold_pipelines.megaplan.model_seam import coerce_plan_markdown_payload

        return coerce_plan_markdown_payload(raw_text)
    return raw_text


def _json_decode_error_for_raw(raw: str) -> json.JSONDecodeError | None:
    """Return a representative JSON decode error for malformed model output."""
    text = raw.strip()
    if not text:
        return None
    candidates = [text]
    fenced = re.findall(r"```json\s*\n(.*?)```", raw, re.DOTALL)
    candidates.extend(block.strip() for block in fenced if block.strip())
    brace = raw.find("{")
    if brace >= 0:
        candidates.append(raw[brace:].strip())
    for line in raw.splitlines():
        stripped = line.strip()
        if stripped.startswith("{") or stripped.startswith("["):
            candidates.append(stripped)
    for candidate in candidates:
        try:
            json.loads(candidate)
        except json.JSONDecodeError as exc:
            return exc
        except (TypeError, ValueError):
            continue
    return None


def _build_json_repair_prompt(error: json.JSONDecodeError, raw: str) -> str:
    prompt = (
        f"Your previous output was not valid JSON (error at line {error.lineno} "
        f"col {error.colno}). Re-emit ONLY a single JSON object matching the "
        "required schema. Escape every backslash as `\\\\` (e.g. write a regex "
        "as `clarify\\\\s*\\\\(`). No prose, no code fences."
    )
    raw = raw.strip()
    if raw:
        prompt += "\n\nPrevious output to repair:\n" + raw[-20000:]
    return prompt


def _recover_payload_from_candidates(
    step: str,
    candidates: list[dict[str, Any]],
    *,
    raw: str,
    validate: bool,
) -> dict[str, Any] | None:
    validation_errors: list[str] = []
    for candidate in candidates:
        if not validate:
            return dict(candidate)
        payload = _normalize_step_payload_for_audit(step, dict(candidate))
        try:
            audit_step_payload(step, payload)
        except ModelStructuralAuditError as error:
            if _looks_like_step_payload(step, payload):
                validation_errors.append(error.details)
            continue
        return payload
    if validation_errors:
        unique_errors = list(dict.fromkeys(validation_errors))
        raise CliError(
            "parse_error",
            f"Repaired JSON object for {step} failed validation: "
            + " | ".join(unique_errors),
            extra={"raw_output": raw, "model_output_parse_error": True},
        )
    return None


def _repair_worker_json_once(
    step: str,
    raw: str,
    repair_call: Callable[[str], str],
    *,
    parse_error: json.JSONDecodeError | None = None,
    validate: bool = True,
    output_path: Path | None = None,
    template_unchanged: bool = False,
    check_id: str | None = None,
    question: str | None = None,
) -> tuple[dict[str, Any], str] | None:
    error = parse_error or _json_decode_error_for_raw(raw)
    if error is None:
        return None
    repaired_raw = repair_call(_build_json_repair_prompt(error, raw))
    repaired_candidates = _extract_json_candidates_from_raw(repaired_raw)
    if (
        step == "critique"
        and _looks_like_deepseek_tool_markup(repaired_raw)
        and repaired_candidates
        and not any(_looks_like_step_payload(step, candidate) for candidate in repaired_candidates)
    ):
        context = _critique_repair_context(check_id=check_id, question=question)
        raise CliError(
            "parse_error",
            "Repair retry for critique did not return a critique JSON object"
            f"{context}: model emitted unsupported tool-call markup; critique template unchanged",
            extra={
                "raw_output": repaired_raw,
                "model_output_parse_error": True,
                "unsupported_tool_call_markup": True,
                "critique_template_unchanged": True,
                **({"check_id": check_id} if check_id else {}),
                **({"question": question} if question else {}),
            },
        )
    payload = _recover_payload_from_candidates(
        step,
        repaired_candidates,
        raw=repaired_raw,
        validate=validate,
    )
    if payload is None:
        repaired_error = _json_decode_error_for_raw(repaired_raw)
        location = (
            f" at line {repaired_error.lineno} col {repaired_error.colno}"
            if repaired_error is not None
            else ""
        )
        if step == "critique" and (
            _looks_like_deepseek_tool_markup(raw)
            or _looks_like_deepseek_tool_markup(repaired_raw)
            or template_unchanged
        ):
            context = _critique_repair_context(check_id=check_id, question=question)
            template_detail = (
                f"; critique template unchanged at {output_path.name}"
                if template_unchanged and output_path is not None
                else "; critique template unchanged"
                if template_unchanged
                else ""
            )
            mutating_detail = (
                "; unsupported write operation rejected"
                if _contains_mutating_deepseek_tool_markup(raw)
                or _contains_mutating_deepseek_tool_markup(repaired_raw)
                else ""
            )
            raise CliError(
                "parse_error",
                "Repair retry for critique did not return valid JSON"
                f"{location}{context}: model emitted unsupported tool-call markup"
                f"{template_detail}{mutating_detail}",
                extra={
                    "raw_output": repaired_raw,
                    "model_output_parse_error": True,
                    "unsupported_tool_call_markup": True,
                    "critique_template_unchanged": template_unchanged,
                    **({"check_id": check_id} if check_id else {}),
                    **({"question": question} if question else {}),
                },
            )
        raise CliError(
            "parse_error",
            f"Repair retry for {step} did not return valid JSON{location}",
            extra={"raw_output": repaired_raw, "model_output_parse_error": True},
        )
    return payload, repaired_raw


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


def _normalize_step_payload_for_audit(step: str, payload: dict[str, Any]) -> dict[str, Any]:
    if step != "critique":
        return payload
    checks = payload.get("checks")
    if not isinstance(checks, list):
        return payload
    changed = False
    clean_checks: list[Any] = []
    for check in checks:
        if not isinstance(check, dict):
            clean_checks.append(check)
            continue
        findings = check.get("findings")
        if not isinstance(findings, list):
            clean_checks.append(check)
            continue
        clean_findings: list[Any] = []
        check_changed = False
        for finding in findings:
            if not isinstance(finding, dict):
                clean_findings.append(finding)
                continue
            extra_keys = set(finding) - {"detail", "flagged"}
            if extra_keys:
                finding = {k: v for k, v in finding.items() if k in {"detail", "flagged"}}
                check_changed = True
            clean_findings.append(finding)
        if check_changed:
            check = dict(check)
            check["findings"] = clean_findings
            changed = True
        clean_checks.append(check)
    if not changed:
        return payload
    clean_payload = dict(payload)
    clean_payload["checks"] = clean_checks
    return clean_payload


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
        schema_path = schemas_root(root) / STEP_SCHEMA_FILENAMES[step]
        schema = read_json(schema_path) if schema_path.exists() else None
        side_effect_paths = (
            plan_dir / "critique_output.json",
            plan_dir / "review_output.json",
        )
        preexisting_paths = {path for path in side_effect_paths if path.exists()}
        result.rendered_prompt = render_prompt_for_dispatch(
            "hermes",
            step,
            state,
            plan_dir,
            root=root,
            schema=schema,
            prompt_override=prompt_override,
        ).prompt
        for path in side_effect_paths:
            if path.exists() and path not in preexisting_paths:
                path.unlink()
    except Exception:
        result.rendered_prompt = prompt_override
    return result


def _normalize_shannon_session_channel(worker_channel: str | None) -> str | None:
    if worker_channel in {None, ""}:
        return None
    normalized = str(worker_channel).strip().lower().replace("-", "_")
    if normalized in {"shannon_stream", "stream", "stream_json", "native_stream"}:
        return "stream_json"
    if normalized in {"shannon", "tmux", "interactive_tmux"}:
        return "tmux"
    return normalized


def _shannon_session_identity_suffix(
    *,
    worker_channel: str | None,
    auth_channel: str | None,
    auth_metadata: dict[str, Any] | None,
) -> str | None:
    channel = _normalize_shannon_session_channel(worker_channel)
    if channel is None:
        return None
    metadata = auth_metadata if isinstance(auth_metadata, dict) else {}
    auth = str(auth_channel or metadata.get("auth_channel") or "subscription")
    auth = auth.strip().lower().replace("-", "_")
    if auth in {"", "oauth"}:
        auth = "subscription"

    # Historical Shannon session keys were tmux/subscription keys. Keep that
    # exact spelling as the compatibility/migration path; all other Shannon
    # channel identities get an explicit suffix so stream/tmux cannot cross-resume.
    if channel == "tmux" and auth == "subscription":
        return None

    parts = [channel, auth]
    if auth == "api_key":
        dry_run = bool(metadata.get("dry_run"))
        source = metadata.get("api_key_source")
        parts.append("dry_run" if dry_run else "live")
        if source:
            digest = hashlib.sha256(str(source).encode("utf-8")).hexdigest()[:8]
            parts.append(digest)
    return "_".join(parts)


def session_key_for(
    step: str,
    agent: str,
    model: str | None = None,
    *,
    worker_channel: str | None = None,
    auth_channel: str | None = None,
    auth_metadata: dict[str, Any] | None = None,
) -> str:
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
    if agent in {"shannon", "claude"}:
        channel_suffix = _shannon_session_identity_suffix(
            worker_channel=worker_channel,
            auth_channel=auth_channel,
            auth_metadata=auth_metadata,
        )
        if channel_suffix:
            key += f"_{channel_suffix}"
    if model:
        key += f"_{hashlib.sha256(model.encode()).hexdigest()[:8]}"
    return key


def update_session_state(
    step: str,
    agent: str,
    session_id: str | None,
    *,
    mode: str,
    refreshed: bool,
    model: str | None = None,
    existing_sessions: dict[str, Any] | None = None,
    worker_channel: str | None = None,
    auth_channel: str | None = None,
    auth_metadata: dict[str, Any] | None = None,
) -> tuple[str, SessionInfo] | None:
    """Build a session entry for the given step.

    Returns ``(key, entry)`` so the caller can store it on the state dict,
    or ``None`` when there is no session_id to record.
    """
    if not session_id:
        return None
    key = session_key_for(
        step,
        agent,
        model=model,
        worker_channel=worker_channel,
        auth_channel=auth_channel,
        auth_metadata=auth_metadata,
    )
    if existing_sessions is None:
        existing_sessions = {}
    entry = {
        "id": session_id,
        "mode": mode,
        "created_at": existing_sessions.get(key, {}).get("created_at", now_utc()),
        "last_used_at": now_utc(),
        "refreshed": refreshed,
    }
    if worker_channel is not None:
        entry["worker_channel"] = _normalize_shannon_session_channel(worker_channel) or worker_channel
    if auth_channel is not None:
        entry["auth_channel"] = str(auth_channel).strip().lower().replace("-", "_")
    if auth_metadata is not None:
        entry["auth_metadata"] = dict(auth_metadata)
    existing_entry = existing_sessions.get(key, {})
    if (
        isinstance(existing_entry, dict)
        and existing_entry.get("id") == session_id
        and isinstance(existing_entry.get("last_total_tokens"), dict)
    ):
        entry["last_total_tokens"] = dict(existing_entry["last_total_tokens"])
    return key, entry


_VALID_CLAUDE_EFFORTS = {"low", "medium", "high", "xhigh", "max"}
_VALID_CODEX_EFFORTS = ("minimal", "low", "medium", "high", "xhigh", "max")


def _normalize_codex_effort(effort: str | None) -> str | None:
    """Preserve an explicitly requested Codex effort without silent clamping."""

    return effort


def _codex_effort_flag(effort: str | None) -> list[str]:
    """Build the exact Codex CLI effort flag, preserving xhigh/max."""

    effort = _normalize_codex_effort(effort)
    if effort is None:
        return []
    if effort not in _VALID_CODEX_EFFORTS:
        raise CliError("invalid_args", f"Unsupported codex effort level: {effort}")
    return ["-c", f"model_reasoning_effort={effort}"]


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
    from arnold_pipelines.megaplan.types import _is_codex_model_name

    if not _is_codex_model_name(model):
        raise CliError(
            "invalid_codex_model",
            f"Refusing to launch codex with model={model!r}: not a recognised "
            f"codex/GPT-5.x model. This usually means a malformed agent spec "
            f"(e.g. 'codex:claude:sonnet') reached dispatch. Fix the phase_model "
            f"pin (e.g. via `megaplan override set-model` / `set-vendor`).",
        )
    return ["-c", f"model='{model}'"]


def _run_claude_step_uncapped(
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
    from arnold_pipelines.megaplan.workers.shannon import run_shannon_step

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
    return _run_claude_step_uncapped(
        step,
        state,
        plan_dir,
        root=root,
        fresh=fresh,
        prompt_override=prompt_override,
        prompt_kwargs=prompt_kwargs,
        effort=effort,
        model=model,
        output_path=output_path,
    )


def _run_codex_step_uncapped(
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
    repair_attempted: bool = False,
    free_text: bool = False,
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
    if step == "execute" and os.getenv("MEGAPLAN_CODEX_EXECUTE_PERSIST_SESSION") != "1":
        fresh = True
    if os.getenv(MOCK_ENV_VAR) == "1":
        _check_mock_safe()
        return mock_worker_output(step, state, plan_dir, prompt_override=prompt_override, prompt_kwargs=prompt_kwargs)
    work_dir = resolve_work_dir(state)
    execution_env = resolve_execution_environment(root=root, state=state)
    sandbox_fingerprint = (
        "read-only"
        if read_only
        else _codex_sandbox_fingerprint(work_dir, state, execution_env)
    )
    if not read_only:
        _guard_mutating_worker_launch(step, state, root)
    plan_mode = state["config"].get("mode", "code")
    codex_schema_name = (
        get_execution_schema_key(plan_mode, form=creative_form_id(state))
        if step == "execute"
        else STEP_SCHEMA_FILENAMES[step]
    )
    schema_file = schemas_root(root) / codex_schema_name
    session_key = session_key_for(step, "codex", model=model)
    session = state["sessions"].get(session_key, {})
    if persistent and step == "execute" and session.get("id") and not fresh:
        prior_fingerprint = session.get("sandbox_fingerprint")
        if prior_fingerprint and prior_fingerprint != sandbox_fingerprint:
            print(
                f"[megaplan] Codex executor session {session['id']} sandbox "
                "fingerprint changed; starting execute with a fresh session",
                flush=True,
            )
            state["sessions"].pop(session_key, None)
            session = {}
            fresh = True
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
        out_handle = tempfile.NamedTemporaryFile(
            "w+", encoding="utf-8", delete=False, dir=str(_project_local_tmp_dir(plan_dir))
        )
        out_handle.close()
        output_path = Path(out_handle.name)
    else:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
    seam_tier = (
        ModelTier.NON_ENFORCED
        if persistent and session.get("id") and not fresh and not read_only
        else ModelTier.ENFORCED
    )
    schema = read_json(schema_file)
    capture_schema = SCHEMAS.get(codex_schema_name, schema)
    rendered_prompt = render_prompt_for_dispatch(
        "codex",
        step,
        state,
        plan_dir,
        root=root,
        model=model,
        normalized_model=model,
        tier=seam_tier,
        schema=schema,
        prompt_override=prompt_override,
        **(prompt_kwargs or {}),
    )
    prompt = _normalize_stdin_text(rendered_prompt.prompt) or ""
    timeout_seconds = _codex_timeout_for_step("prep" if read_only else step)

    if read_only:
        command = [
            "codex",
            "exec",
            "--skip-git-repo-check",
            "--ephemeral",
            "-o",
            str(output_path),
        ]
        if _trusted_container():
            # Trusted containers are the outer sandbox. On hosts without
            # unprivileged user namespaces, Codex's read-only bubblewrap
            # sandbox fails before the worker can inspect local files.
            command.append("--dangerously-bypass-approvals-and-sandbox")
        else:
            command.extend([
                "-c",
                "sandbox_mode='read-only'",
            ])
        command.extend(_codex_model_flag(model))
        command.extend(_codex_effort_flag(effort))
        if json_trace:
            command.append("--json")
        if free_text:
            command.append("-")
        else:
            command.extend(["--output-schema", str(schema_file), "-"])
    elif persistent and session.get("id") and not fresh:
        # codex exec resume does not support --output-schema; capture_step_output
        # handles the output file validation after parsing instead. It also
        # does not accept --add-dir; resumed sessions keep the workspace that
        # was granted when the session was created.
        command = ["codex", "exec", "resume"]
        if _trusted_container():
            command.append("--dangerously-bypass-approvals-and-sandbox")
        command.extend(_codex_model_flag(model))
        command.extend(_codex_effort_flag(effort))
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
            roots = _codex_writable_roots(work_dir, state, execution_env, phase=step)
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
        command.extend(_codex_effort_flag(effort))
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
        try:
            codex_idle_s = float(os.getenv("MEGAPLAN_CODEX_IDLE_TIMEOUT_S", "600"))
        except (TypeError, ValueError):
            codex_idle_s = 600.0
        if step == "execute":
            _emit_codex_execute_llm_start(
                plan_dir,
                model=model,
                prompt=prompt,
                json_trace=json_trace,
            )
        # Non-execute phases have no long mutating tool turn to protect.  They
        # must show a structured Codex event, rollout token, or output artifact
        # to extend their idle window; a live-but-silent node process is a
        # transport/CLI wedge, not progress.  Execute deliberately retains
        # CPU-based liveness because pytest/build subprocesses can be
        # legitimately quiet for minutes.
        strict_structured_liveness = step not in _EXECUTE_STEPS
        liveness = CodexProgressLiveness(
            output_path=output_path,
            include_cpu_signal=not strict_structured_liveness,
        )
        result = run_command(
            command,
            cwd=work_dir,
            stdin_text=prompt,
            env=_codex_child_env(turn_id=f'plan_worker_{state["name"]}'),
            timeout=timeout_seconds,
            activity_callback=_activity_callback_for_state(state, plan_dir),
            activity_guard=liveness.activity_guard,
            pre_first_byte_timeout=pre_first_byte_s if pre_first_byte_s > 0 else None,
            idle_timeout=codex_idle_s if codex_idle_s > 0 else None,
            progress_liveness_factory=liveness.bind_process,
            # Structured non-execute liveness has no grace: a process that is
            # merely alive but has no token/event/artifact evidence must
            # surface as a retryable worker_stall at the configured bounded
            # idle timeout.
            progress_liveness_grace_timeout=(
                0.0 if strict_structured_liveness else (codex_idle_s if codex_idle_s > 0 else None)
            ),
        )
        if not read_only:
            _verify_engine_after_mutating_worker(step, state, root, execution_env)
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
        if error.code in {"worker_timeout", "worker_stall"}:
            try:
                capture_outcome = capture_step_output(
                    StepInvocation(
                        kind="model",
                        metadata={
                            "tier": seam_tier.value,
                            "worker": "codex",
                            "model": model,
                            "normalized_model": model,
                            "validation_step": step,
                            "compatibility_validation_step": step,
                            "schema": schema,
                            "capture_schema": capture_schema,
                            "capture_recovery": {
                                "step": step,
                                "plan_dir": str(plan_dir),
                                "output_path": str(output_path),
                                "prefer_output_file": False,
                            },
                        },
                    ),
                    str(error.extra.get("raw_output", "")),
                )
                recovered_payload = _normalize_step_payload_for_audit(
                    step,
                    dict(capture_outcome.legacy_payload),
                )
            except (json.JSONDecodeError, ModelStructuralAuditError):
                recovered_payload = None
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
                    worker_channel=_CODEX_WORKER_CHANNEL,
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
                error.code,
                (
                    (
                        f"Codex {step} worker became silent before producing structured output. "
                        if error.code == "worker_stall"
                        else f"Codex {step} step timed out after {timeout_seconds}s before producing structured output. "
                    )
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
    try:
        output_raw = output_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        output_raw = ""
    if free_text:
        text = output_raw or raw
        payload: dict[str, Any] = {}
        if step == "plan":
            extracted = _extract_plan_capture_input(text)
            if isinstance(extracted, dict):
                payload = extracted
        return WorkerResult(
            payload=payload,
            raw_output=text,
            duration_ms=result.duration_ms,
            cost_usd=0.0,
            session_id=extract_session_id(raw),
            trace_output=raw if json_trace else None,
            rendered_prompt=prompt,
            worker_channel=_CODEX_WORKER_CHANNEL,
        )
    capture_input: str | dict[str, Any] = raw
    plan_text = output_raw or raw
    if step == "plan":
        capture_input = _extract_plan_capture_input(plan_text)
    try:
        capture_outcome = capture_step_output(
            StepInvocation(
                kind="model",
                metadata={
                    "tier": seam_tier.value,
                    "worker": "codex",
                    "model": model,
                    "normalized_model": model,
                    "validation_step": step,
                    "compatibility_validation_step": step,
                    "schema": schema,
                    "capture_schema": capture_schema,
                    "capture_recovery": {
                        "step": step,
                        "plan_dir": str(plan_dir),
                        "output_path": str(output_path),
                        "prefer_output_file": True,
                    },
                },
            ),
            capture_input,
        )
        payload = _normalize_step_payload_for_audit(
            step,
            dict(capture_outcome.legacy_payload),
        )
    except json.JSONDecodeError:
        payload = None
    except ModelStructuralAuditError as error:
        raise CliError("parse_error", str(error), extra={"raw_output": raw}) from error
    if payload is None:
        parse_error = _json_decode_error_for_raw(raw)
        try:
            output_raw = output_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            output_raw = ""
        if parse_error is None:
            parse_error = _json_decode_error_for_raw(output_raw)
        repair_raw = output_raw or raw
        if parse_error is not None and not repair_attempted:
            repair_prompt = _build_json_repair_prompt(parse_error, repair_raw)
            # _pre_dispatch_budget_check sentinel: budget guard for dispatch
            try:
                render_step_message(StepInvocation(kind="model", metadata={
                    "prompt": repair_prompt,
                    "model": model,
                    "normalized_model": model,
                    "validation_step": step,
                    "tier": (seam_tier.value if isinstance(seam_tier, ModelTier) else ModelTier.NON_ENFORCED.value),
                    "worker": "codex",
                }))
            except ModelBudgetError:
                raise
            return run_codex_step(
                step,
                state,
                plan_dir,
                root=root,
                persistent=persistent,
                fresh=True,
                json_trace=json_trace,
                prompt_override=repair_prompt,
                prompt_kwargs=prompt_kwargs,
                effort=effort,
                model=model,
                read_only=read_only,
                output_path=output_path,
                repair_attempted=True,
            )
        raise CliError(
            "parse_error",
            f"Output file {output_path.name} was not valid JSON and no fallback found",
            extra={
                "raw_output": repair_raw or raw,
                "model_output_parse_error": parse_error is not None,
            },
        )
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
        cost_session_id, session_entry, model
    )
    observed_model = model_actual or model
    from arnold_pipelines.megaplan.pricing.codex import is_model_priced

    cost_pricing = (
        "unavailable"
        if current_totals is None
        else "priced"
        if is_model_priced(observed_model)
        else "unpriced"
    )
    if step == "execute":
        _emit_codex_execute_llm_end(
            plan_dir,
            request_id=cost_session_id,
            model=observed_model,
            tokens_in=prompt_tokens,
            tokens_out=completion_tokens,
        )
        if current_totals is not None and cost_pricing == "priced":
            _emit_codex_execute_cost_recorded(
                plan_dir,
                request_id=cost_session_id,
                model=observed_model,
                cost_usd=cost_usd,
            )
    should_record_session = persistent and not (
        step == "execute" and os.getenv("MEGAPLAN_CODEX_EXECUTE_PERSIST_SESSION") != "1"
    )
    if should_record_session and isinstance(state.get("sessions"), dict):
        entry = state["sessions"].setdefault(session_key, {})
        if isinstance(entry, dict):
            if session_id:
                entry["id"] = session_id
            entry["sandbox_fingerprint"] = sandbox_fingerprint
    if current_totals is not None:
        # Persist the running totals so the next step in the same session
        # only bills its own delta. We mutate the existing session entry
        # when present; otherwise stash a minimal record under session_key.
        if isinstance(state.get("sessions"), dict):
            entry = state["sessions"].setdefault(session_key, {})
            if isinstance(entry, dict):
                if cost_session_id:
                    entry["id"] = cost_session_id
                entry["sandbox_fingerprint"] = sandbox_fingerprint
                entry["last_total_tokens"] = dict(current_totals)
    if cost_usd == 0.0 and cost_session_id and current_totals is None:
        # Don't crash; just leave a breadcrumb so operators can investigate
        # missing rollouts (codex stored elsewhere, permission issue, etc.).
        print(
            f"[megaplan] Could not locate codex rollout for session "
            f"{cost_session_id}; step cost will be recorded as $0.00",
            flush=True,
        )
    elif cost_pricing == "unpriced":
        print(
            f"[megaplan] No canonical pricing for Codex model {observed_model!r}; "
            "step cost is explicitly unpriced (numeric compatibility value $0.00)",
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
        model_actual=observed_model,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=prompt_tokens + completion_tokens,
        cost_pricing=cost_pricing,
        worker_channel=_CODEX_WORKER_CHANNEL,
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
    free_text: bool = False,
    repair_attempted: bool = False,
) -> WorkerResult:
    # Non-execute supervision relies on stream-json to observe rollout/token
    # cadence.  Enforce it here as well as at dispatcher call sites so direct
    # handler callers cannot silently disable the watchdog's evidence channel.
    json_trace = json_trace or step not in _EXECUTE_STEPS
    return _run_codex_step_uncapped(
        step,
        state,
        plan_dir,
        root=root,
        persistent=persistent,
        fresh=fresh,
        json_trace=json_trace,
        prompt_override=prompt_override,
        prompt_kwargs=prompt_kwargs,
        effort=effort,
        model=model,
        read_only=read_only,
        output_path=output_path,
        free_text=free_text,
        repair_attempted=repair_attempted,
    )


def run_codex_prep_step(
    step: str,
    state: PlanState,
    plan_dir: Path,
    *,
    root: Path,
    prompt_override: str | None = None,
    prompt_kwargs: dict[str, Any] | None = None,
    effort: str | None = None,
    model: str | None = None,
) -> WorkerResult:
    """Run prep triage/distill through Codex without writable grants."""

    if step not in {"prep-triage", "prep-distill"}:
        raise CliError("unsupported_step", f"Codex prep runner does not support '{step}'")
    effort = _normalize_codex_effort(effort)
    if effort is not None and effort not in _VALID_CODEX_EFFORTS:
        raise CliError("invalid_args", f"Unsupported codex effort level: {effort}")
    if os.getenv(MOCK_ENV_VAR) == "1":
        _check_mock_safe()
        return mock_worker_output(
            step,
            state,
            plan_dir,
            prompt_override=prompt_override,
            prompt_kwargs=prompt_kwargs,
        )

    out_handle = tempfile.NamedTemporaryFile(
        "w+", encoding="utf-8", delete=False, dir=str(_project_local_tmp_dir(plan_dir))
    )
    out_handle.close()
    output_path = Path(out_handle.name)
    schema_file = schemas_root(root) / STEP_SCHEMA_FILENAMES[step]
    schema = read_json(schema_file)
    capture_schema = SCHEMAS.get(STEP_SCHEMA_FILENAMES[step], schema)
    rendered_prompt = render_prompt_for_dispatch(
        "codex",
        step,
        state,
        plan_dir,
        root=root,
        model=model,
        normalized_model=model,
        tier=ModelTier.ENFORCED,
        schema=schema,
        prompt_override=prompt_override,
        **(prompt_kwargs or {}),
    )
    prompt = rendered_prompt.prompt
    command = [
        "codex",
        "exec",
        "--skip-git-repo-check",
        "--ephemeral",
        "-o",
        str(output_path),
    ]
    if _trusted_container():
        command.append("--dangerously-bypass-approvals-and-sandbox")
    else:
        command.extend([
            "-c",
            "sandbox_mode='read-only'",
        ])
    command.extend(_codex_model_flag(model))
    command.extend(_codex_effort_flag(effort))
    command.extend(["--output-schema", str(schema_file), "-"])

    result = run_command(
        command,
        cwd=resolve_work_dir(state),
        stdin_text=prompt,
        env=_codex_child_env(turn_id=f'prep_worker_{state["name"]}'),
        timeout=_codex_timeout_for_step("prep"),
        activity_callback=_activity_callback_for_state(state, plan_dir),
    )
    raw = result.stdout + result.stderr
    if result.returncode != 0 and (
        not output_path.exists() or not output_path.read_text(encoding="utf-8").strip()
    ):
        error_code, error_message = _diagnose_codex_failure(raw, result.returncode)
        raise CliError(error_code, error_message, extra={"raw_output": raw})
    try:
        capture_outcome = capture_step_output(
            StepInvocation(
                kind="model",
                metadata={
                    "tier": ModelTier.ENFORCED.value,
                    "worker": "codex",
                    "model": model,
                    "normalized_model": model,
                    "validation_step": step,
                    "compatibility_validation_step": step,
                    "schema": schema,
                    "capture_schema": capture_schema,
                    "capture_recovery": {
                        "step": step,
                        "plan_dir": str(plan_dir),
                        "output_path": str(output_path),
                        "prefer_output_file": True,
                    },
                },
            ),
            raw,
        )
        payload = _normalize_step_payload_for_audit(
            step,
            dict(capture_outcome.legacy_payload),
        )
    except json.JSONDecodeError:
        payload = None
    except ModelStructuralAuditError as error:
        raise CliError("parse_error", str(error), extra={"raw_output": raw}) from error
    if payload is None:
        raise CliError(
            "parse_error",
            f"Output file {output_path.name} was not valid JSON and no fallback found",
            extra={"raw_output": raw},
        )
    return WorkerResult(
        payload=payload,
        raw_output=raw,
        duration_ms=result.duration_ms,
        cost_usd=0.0,
        session_id=extract_session_id(raw),
        rendered_prompt=prompt,
        model_actual=model,
        worker_channel=_CODEX_WORKER_CHANNEL,
    )


def _is_agent_available(agent: str) -> bool:
    """Check if an agent is available (CLI binary or vendored for hermes)."""
    if agent == "hermes":
        # The vendored run_agent.py and hermes_state.py now live under
        # ``arnold/agent/``. Import ``arnold.agent`` to locate the directory,
        # place it on ``sys.path`` so the legacy absolute imports resolve, then
        # probe the two required modules so a partial install fails closed.
        try:
            import importlib
            import sys
            from pathlib import Path

            import arnold.agent as _agent_pkg

            agent_dir = str(Path(_agent_pkg.__file__).resolve().parent)
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
        from arnold_pipelines.megaplan._core.io import (
            _shannon_stream_worker_enabled,
            is_claude_stream_available,
            is_shannon_available,
        )
        if _shannon_stream_worker_enabled():
            return is_claude_stream_available()
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


_VENDOR_AWARE_DEFAULT_STEPS = frozenset({"critique_evaluator", "feedback"})


def _effective_premium_vendor(args: argparse.Namespace) -> str | None:
    vendor = getattr(args, "_effective_vendor", None) or getattr(args, "vendor", None)
    return vendor if vendor in {"claude", "codex"} else None


def _vendor_adjusted_default_spec(step: str, spec: str, args: argparse.Namespace) -> str:
    vendor = _effective_premium_vendor(args)
    if step not in _VENDOR_AWARE_DEFAULT_STEPS or vendor is None:
        return spec
    parsed = parse_agent_spec(spec)
    if parsed.agent not in {"claude", "codex"} or parsed.agent == vendor:
        return spec
    if parsed.model is None and parsed.effort is None:
        return vendor
    if parsed.model is None and parsed.effort is not None:
        return f"{vendor}:{parsed.effort}"
    return spec


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
                pm_step, chain = decode_phase_model_value(pm)
                if pm_step == step:
                    pm_parsed = parse_agent_spec(chain.selected())
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
                configured_spec = config.get("agents", {}).get(step)
                spec = configured_spec or DEFAULT_AGENT_ROUTING[step]
                spec = _vendor_adjusted_default_spec(step, spec, args)
                if is_premium_placeholder_agent(parse_agent_spec(spec).agent):
                    vendor = effective_premium_vendor(args, config)
                    spec = format_agent_spec(resolve_premium_placeholder_spec(spec, vendor))
                spec_parsed = parse_agent_spec(spec)
                agent = spec_parsed.agent
                model = spec_parsed.model
                effort = spec_parsed.effort

    if is_premium_placeholder_agent(agent):
        raise CliError(
            "invalid_agent_spec",
            f"Unresolved premium placeholder reached worker dispatch for step {step!r}. "
            "Resolve it to 'claude' or 'codex' before dispatch.",
        )

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
                    "hermes backend requires the bundled runtime packages: pip install arnold (or pip install -e . in a source checkout; '[agent]' is only a no-op compatibility extra).",
                )
            if agent == "shannon":
                from arnold_pipelines.megaplan._core.io import shannon_missing_deps
                missing = shannon_missing_deps()
                raise CliError(
                    "agent_deps_missing",
                    f"Shannon requires: {', '.join(missing)}. "
                    "Install bun (https://bun.sh) and ensure the vendored fork at megaplan/vendor/shannon/index.ts is present.",
                )
            if agent == "claude":
                from arnold_pipelines.megaplan._core.io import shannon_missing_deps
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
                "hermes backend requires the bundled runtime packages: pip install arnold (or pip install -e . in a source checkout; '[agent]' is only a no-op compatibility extra).",
            )
        # Try fallback
        available = detect_available_agents()
        if not available:
            raise CliError(
                "agent_not_found",
                "No supported agents found. Install claude or codex, or install arnold (or pip install -e . in a source checkout) for hermes. The legacy '[agent]' extra is only a no-op compatibility alias.",
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


# ---------------------------------------------------------------------------
# ArnoldDispatcher helper closures (flag-ON path, Step 5b)
#
# These functions are injected as per-call closure adapters inside the
# MEGAPLAN_USE_AGENT_DISPATCHER=1 branch of run_step_with_worker.  They
# replicate the inner one-shot retry semantics from the flag-OFF codex and
# shannon branches so CliError propagates unchanged to the outer
# auth/connection fallback loop.
# ---------------------------------------------------------------------------


def _codex_to_agent_result(
    req: Any,
    *,
    step: str,
    state: PlanState,
    plan_dir: Path,
    root: Path,
    args: argparse.Namespace,
    worker_options: dict[str, Any] | None,
    prompt_override: str | None,
    prompt_kwargs: dict[str, Any] | None,
    output_path: Path | None,
    effective_refreshed: bool,
) -> Any:
    """Call run_codex_step and project WorkerResult → AgentResult."""
    mode = req.mode
    resolved_model = req.resolved_model
    effort = req.effort
    read_only = req.read_only
    if os.getenv(MOCK_ENV_VAR) != "1":
        assert resolved_model is not None and resolved_model != "", (
            "run_step_with_worker about to invoke run_codex_step via "
            "ArnoldDispatcher with empty resolved_model. "
            "AgentMode.resolved_model should hold e.g. 'gpt-5.5'. "
            "See /tmp/codex_wedge_diagnostic.md."
        )
    attempted_retry = False
    eff_fresh = effective_refreshed
    while True:
        try:
            _w = run_codex_step(
                step,
                state,
                plan_dir,
                root=root,
                persistent=(mode == "persistent"),
                fresh=eff_fresh,
                # Every non-execute phase needs stream-json too: it supplies
                # the token/tool evidence used to distinguish a live phase
                # from a silent transport wedge.  The final schema payload
                # still comes from the output file.
                json_trace=True,
                prompt_override=prompt_override,
                prompt_kwargs=prompt_kwargs,
                effort=effort,
                model=resolved_model,
                read_only=read_only,
                output_path=output_path,
            )
            return _w.to_agent_result()
        except CliError as error:
            session_id = error.extra.get("session_id")
            if (
                attempted_retry
                or step in _EXECUTE_STEPS
                or error.code
                not in {
                    "worker_timeout",
                    "worker_stall",
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
                    req.agent,
                    session_id,
                    mode=mode,
                    refreshed=eff_fresh,
                    model=resolved_model,
                )
                eff_fresh = step not in _CROSS_CALL_PERSISTENT_STEPS
            continue


def _shannon_to_agent_result(
    req: Any,
    *,
    step: str,
    state: PlanState,
    plan_dir: Path,
    root: Path,
    args: argparse.Namespace,
    worker_options: dict[str, Any] | None,
    prompt_override: str | None,
    prompt_kwargs: dict[str, Any] | None,
    output_path: Path | None,
    effective_refreshed: bool,
) -> Any:
    """Call run_shannon_step and project WorkerResult → AgentResult."""
    from arnold_pipelines.megaplan._core.io import _shannon_stream_worker_enabled

    if _shannon_stream_worker_enabled(root=root, plan_id=str(state.get("name") or "")):
        from arnold_pipelines.megaplan.workers.shannon_stream import (
            run_shannon_stream_step as run_shannon_worker_step,
        )
    else:
        from arnold_pipelines.megaplan.workers.shannon import (
            run_shannon_step as run_shannon_worker_step,
        )

    mode = req.mode
    resolved_model = req.resolved_model
    effort = req.effort
    read_only = req.read_only
    shannon_kwargs: dict[str, Any] = dict(
        root=root,
        prompt_override=prompt_override,
        prompt_kwargs=prompt_kwargs,
        effort=effort,
        model=resolved_model,
        read_only=read_only,
        output_path=output_path,
    )
    if req.agent == "claude":
        shannon_kwargs["session_agent"] = "claude"
    attempted_retry = False
    eff_fresh = effective_refreshed
    while True:
        try:
            _w = run_shannon_worker_step(
                step,
                state,
                plan_dir,
                fresh=eff_fresh,
                **shannon_kwargs,
            )
            return _w.to_agent_result()
        except CliError as error:
            if (
                attempted_retry
                or step in _EXECUTE_STEPS
                or error.code not in {"worker_stall", "worker_timeout", "connection_error"}
            ):
                raise
            attempted_retry = True
            eff_fresh = True
            continue


def _selected_step_spec(agent: str, model: str | None, effort: str | None) -> str:
    return format_selected_spec(agent, model, effort) or agent


def _initial_fallback_metadata(
    step: str,
    args: argparse.Namespace,
    *,
    agent: str,
    model: str | None,
    effort: str | None,
    configured_specs: tuple[str, ...] | list[str] | str | None = None,
) -> dict[str, Any]:
    if configured_specs is not None:
        ledger_fields = fallback_observability_fields(configured_specs)
        normalized_specs = tuple(ledger_fields["configured_specs"])
    else:
        configured = configured_fallback_chain_for_phase(getattr(args, "phase_model", None), step)
        normalized_specs = configured.specs if configured is not None else (_selected_step_spec(agent, model, effort),)
    return {
        "configured_specs": normalized_specs,
        "attempt_index": 0,
        "attempted_specs": (normalized_specs[0],),
        "failed_attempt_reasons": (),
        "fallback_trigger": None,
    }


def _assign_worker_fallback_metadata(worker: WorkerResult, metadata: dict[str, Any]) -> None:
    worker.configured_specs = tuple(metadata["configured_specs"])
    worker.attempt_index = int(metadata["attempt_index"])
    worker.attempted_specs = tuple(metadata["attempted_specs"])
    worker.failed_attempt_reasons = tuple(metadata["failed_attempt_reasons"])
    worker.fallback_trigger = metadata["fallback_trigger"]


_CONFIGURED_SPEC_FALLBACK_CLASSES = frozenset(
    {
        "availability",
        "infrastructure",
        "auth",
        "quota",
        "rate_limit",
        "unsupported_model",
        "context_window",
    }
)


def _configured_spec_failure_class(error: CliError) -> str:
    external = error.extra.get("_external_error")
    if external is not None:
        return classify_retryability(external)
    return classify_retryability(
        {
            "code": error.code,
            "message": str(error),
            "status_code": error.extra.get("status_code"),
            "retryable": error.extra.get("retryable"),
        }
    )


def _agent_mode_from_configured_spec(
    spec: str,
    *,
    mode: str,
    refreshed: bool,
) -> AgentMode:
    parsed = parse_agent_spec(spec)
    resolved_model = parsed.model
    if parsed.agent in ("claude", "codex") and not resolved_model:
        resolved_model = resolved_default_model_for_agent(parsed.agent)
    return AgentMode(
        agent=parsed.agent,
        mode=mode,
        refreshed=refreshed,
        model=parsed.model,
        effort=parsed.effort,
        resolved_model=resolved_model,
    )


def _configured_spec_worker_failure_class(worker: WorkerResult) -> str | None:
    payload = worker.payload
    if not isinstance(payload, dict) or payload.get("success") is not False:
        return None
    details = payload.get("details")
    external = details.get("_external_error") if isinstance(details, dict) else None
    if external is not None:
        return classify_retryability(external)
    return classify_retryability(
        {
            "code": payload.get("error"),
            "message": payload.get("message"),
        }
    )


def _advance_configured_spec_fallback(
    fallback_metadata: dict[str, Any],
    failure_class: str | None,
    *,
    mode: str,
    step: str,
    read_only: bool,
) -> tuple[AgentMode, dict[str, Any]] | None:
    # Never redispatch after a worker may have mutated the checkout. This is
    # stricter than the provider/model relationship and keeps mid-write
    # failures fail-closed for both explicit and profile-provided chains.
    if not read_only or step in _EXECUTE_STEPS:
        return None
    if failure_class not in _CONFIGURED_SPEC_FALLBACK_CLASSES:
        return None
    configured_specs = tuple(fallback_metadata["configured_specs"])
    attempt_index = int(fallback_metadata["attempt_index"])
    next_index = attempt_index + 1
    if next_index >= len(configured_specs):
        return None
    next_spec = configured_specs[next_index]
    current_spec = configured_specs[attempt_index]
    if provider_family(next_spec) == provider_family(current_spec):
        if not is_same_family_operational_classification(failure_class):  # type: ignore[arg-type]
            return None
    next_mode = _agent_mode_from_configured_spec(
        next_spec,
        mode=mode,
        refreshed=True,
    )
    next_metadata = {
        "configured_specs": configured_specs,
        "attempt_index": next_index,
        "attempted_specs": (
            *fallback_metadata["attempted_specs"],
            next_spec,
        ),
        "failed_attempt_reasons": (
            *fallback_metadata["failed_attempt_reasons"],
            failure_class,
        ),
        "fallback_trigger": failure_class,
    }
    return next_mode, next_metadata


def _patch_active_step_fallback_metadata(
    plan_dir: Path,
    state: PlanState,
    metadata: dict[str, Any],
    *,
    agent: str,
    mode: str,
    model: str | None,
) -> None:
    active = state.get("active_step")
    run_id = active.get("run_id") if isinstance(active, dict) else None
    if not isinstance(run_id, str) or not run_id:
        return
    fields = fallback_observability_fields(
        metadata["configured_specs"],
        attempt_index=int(metadata["attempt_index"]),
        attempted_specs=metadata["attempted_specs"],
        failed_attempt_reasons=metadata["failed_attempt_reasons"],
        fallback_trigger=metadata["fallback_trigger"],
    )

    def _mutate(current: dict[str, Any]) -> bool:
        current_active = current.get("active_step")
        if not isinstance(current_active, dict) or current_active.get("run_id") != run_id:
            return False
        current_active["agent"] = agent
        current_active["mode"] = mode
        if model:
            current_active["model"] = model
        current_active.update(fields)
        current_active["last_activity_at"] = now_utc()
        current_active["last_activity_kind"] = "fallback"
        current_active["last_activity_detail"] = f"advanced to {fields['selected_spec']}"
        return True

    try:
        write_plan_state(plan_dir, mode="patch-many", mutation=_mutate)
    except Exception:
        return


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
    ledger_configured_specs: tuple[str, ...] | list[str] | str | None = None,
    ledger_attempt_index: int | None = None,
    ledger_attempted_specs: tuple[str, ...] | list[str] | str | None = None,
    ledger_failed_attempt_reasons: tuple[str, ...] | list[str] | None = None,
    ledger_fallback_trigger: str | None = None,
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
    if ledger_configured_specs is not None:
        ledger_fields = fallback_observability_fields(
            ledger_configured_specs,
            attempt_index=int(ledger_attempt_index or 0),
            attempted_specs=ledger_attempted_specs,
            failed_attempt_reasons=ledger_failed_attempt_reasons,
            fallback_trigger=ledger_fallback_trigger,
        )
        fallback_metadata = {
            "configured_specs": tuple(ledger_fields["configured_specs"]),
            "attempt_index": ledger_fields["selected_spec_index"],
            "attempted_specs": tuple(ledger_fields["attempted_specs"]),
            "failed_attempt_reasons": tuple(ledger_fields["failed_attempt_reasons"]),
            "fallback_trigger": ledger_fields["fallback_trigger"],
        }
    else:
        fallback_metadata = _initial_fallback_metadata(
            step,
            args,
            agent=agent,
            model=model,
            effort=effort,
        )
    while True:
        attempted_agents.add(agent)
        try:
            if os.getenv("MEGAPLAN_USE_AGENT_DISPATCHER") != "1":
                if agent == "hermes":
                    # Deferred import to avoid circular import (hermes_worker imports from workers)
                    from arnold_pipelines.megaplan.workers.hermes import run_hermes_step
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
                    from arnold_pipelines.megaplan._core.io import _shannon_stream_worker_enabled

                    if _shannon_stream_worker_enabled(root=root, plan_id=str(state.get("name") or "")):
                        from arnold_pipelines.megaplan.workers.shannon_stream import (
                            run_shannon_stream_step as run_shannon_worker_step,
                        )
                    else:
                        from arnold_pipelines.megaplan.workers.shannon import (
                            run_shannon_step as run_shannon_worker_step,
                        )

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
                            worker = run_shannon_worker_step(
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
                                json_trace=True,
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
                                    "worker_stall",
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
            else:
                # Flag-ON path: route all agents through ArnoldDispatcher via
                # per-call closure registrations.  The outer auth/connection
                # fallback (except CliError below) still wraps everything; the
                # inner per-backend one-shot retry lives inside the closures.
                from arnold.agent import ArnoldDispatcher
                from arnold.agent.adapters.deepseek import DeepSeekAdapter as _DeepSeekAdapter
                from arnold.agent.contracts import AgentRequest as _AgentRequest
                _dispatcher = ArnoldDispatcher()
                _dispatcher.register("hermes", _DeepSeekAdapter())
                _dispatcher.register(
                    "codex",
                    lambda req: _codex_to_agent_result(
                        req,
                        step=step,
                        state=state,
                        plan_dir=plan_dir,
                        root=root,
                        args=args,
                        worker_options=worker_options,
                        prompt_override=prompt_override,
                        prompt_kwargs=prompt_kwargs,
                        output_path=output_path,
                        effective_refreshed=effective_refreshed,
                    ),
                )
                _shannon_closure = lambda req: _shannon_to_agent_result(
                    req,
                    step=step,
                    state=state,
                    plan_dir=plan_dir,
                    root=root,
                    args=args,
                    worker_options=worker_options,
                    prompt_override=prompt_override,
                    prompt_kwargs=prompt_kwargs,
                    output_path=output_path,
                    effective_refreshed=effective_refreshed,
                )
                _dispatcher.register("claude", _shannon_closure)
                _dispatcher.register("shannon", _shannon_closure)
                if agent == "hermes":
                    _rendered = render_prompt_for_dispatch(
                        "hermes",
                        step,
                        state,
                        plan_dir,
                        root=root,
                        model=model,
                        prompt_override=prompt_override,
                        **(prompt_kwargs or {}),
                    )
                    _prompt = _rendered.prompt
                else:
                    _prompt = None
                _request = _AgentRequest(
                    agent=agent,
                    mode=mode,
                    model=model,
                    resolved_model=resolved_model,
                    effort=effort,
                    read_only=read_only,
                    prompt=_prompt,
                    system_prompt=None,
                    metadata={
                        "step": step,
                        "plan_dir": str(plan_dir),
                        **(worker_options or {}),
                    },
                )
                worker = WorkerResult.from_agent_result(_dispatcher.dispatch(_request))
            fallback_attempt = _advance_configured_spec_fallback(
                fallback_metadata,
                _configured_spec_worker_failure_class(worker),
                mode=mode,
                step=step,
                read_only=read_only,
            )
            if fallback_attempt is not None:
                next_mode, fallback_metadata = fallback_attempt
                agent = next_mode.agent
                mode = next_mode.mode
                refreshed = next_mode.refreshed
                model = next_mode.model
                effort = next_mode.effort
                resolved_model = next_mode.resolved_model
                effective_refreshed = True
                _patch_active_step_fallback_metadata(
                    plan_dir,
                    state,
                    fallback_metadata,
                    agent=agent,
                    mode=mode,
                    model=model,
                )
                continue
            _assign_worker_fallback_metadata(worker, fallback_metadata)
            if record_routing and (step != "execute" or ledger_step_label is not None):
                actual_model = getattr(worker, "model_actual", None)
                if actual_model is None and agent == "codex":
                    actual_model = resolved_model
                record_step_routing(
                    plan_dir,
                    phase=ledger_phase or normalize_routing_phase(step),
                    step_label=ledger_step_label or step,
                    agent=agent,
                    selected_spec=ledger_selected_spec
                    or format_selected_spec(agent, model, effort),
                    resolved_model=resolved_model,
                    actual_model=actual_model,
                    tier=ledger_tier,
                    complexity=ledger_complexity,
                    tier_routing_active=ledger_tier_routing_active,
                    configured_specs=worker.configured_specs,
                    attempt_index=worker.attempt_index,
                    attempted_specs=worker.attempted_specs,
                    failed_attempt_reasons=worker.failed_attempt_reasons,
                    fallback_trigger=worker.fallback_trigger,
            )
            return worker, agent, mode, effective_refreshed
        except CliError as error:
            fallback_attempt = _advance_configured_spec_fallback(
                fallback_metadata,
                _configured_spec_failure_class(error),
                mode=mode,
                step=step,
                read_only=read_only,
            )
            if fallback_attempt is not None:
                next_mode, fallback_metadata = fallback_attempt
                agent = next_mode.agent
                mode = next_mode.mode
                refreshed = next_mode.refreshed
                model = next_mode.model
                effort = next_mode.effort
                resolved_model = next_mode.resolved_model
                effective_refreshed = True
                _patch_active_step_fallback_metadata(
                    plan_dir,
                    state,
                    fallback_metadata,
                    agent=agent,
                    mode=mode,
                    model=model,
                )
                continue
            suppress_ambient_fallback = bool(
                (worker_options or {}).get("_suppress_ambient_agent_fallback")
            )
            if (
                explicit_agent
                or suppress_ambient_fallback
                or error.code not in {"auth_error", "connection_error"}
            ):
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
            failed_spec = _selected_step_spec(agent, model, effort)
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
            selected_fallback_spec = _selected_step_spec(agent, model, effort)
            configured_specs = list(fallback_metadata["configured_specs"])
            if failed_spec not in configured_specs:
                configured_specs.append(failed_spec)
            if selected_fallback_spec not in configured_specs:
                configured_specs.append(selected_fallback_spec)
            fallback_metadata = {
                "configured_specs": tuple(configured_specs),
                "attempt_index": configured_specs.index(selected_fallback_spec),
                "attempted_specs": (
                    *fallback_metadata["attempted_specs"],
                    selected_fallback_spec,
                ),
                "failed_attempt_reasons": (
                    *fallback_metadata["failed_attempt_reasons"],
                    error.code,
                ),
                "fallback_trigger": error.code,
            }
            effective_refreshed = True
