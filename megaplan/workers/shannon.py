"""Shannon worker — opt-in Claude launcher via interactive tmux sessions.

Shannon (https://github.com/dexhorthy/shannon) runs real Claude Code in tmux,
sends prompts, and tails the Claude transcript JSONL instead of using
``claude -p``.  This module provides ``run_shannon_step``, a drop-in launcher
that preserves the same WorkerResult contract, schema validation, session
tracking, timeouts, error handling, and receipts as the native Claude path.

Env-var → ShannonConfig field mapping (all read by :meth:`ShannonConfig.load`):

  MEGAPLAN_SHANNON_READINESS_PROBE           → readiness_probe_raw / readiness_probe_forced
  MEGAPLAN_TRUSTED_CONTAINER                 → trusted_container
  MEGAPLAN_SHANNON_READINESS_TIMEOUT_SECONDS → readiness_timeout_seconds   (default 120)
  MEGAPLAN_SHANNON_EXECUTE_TIMEOUT_SECONDS   → execute_timeout_seconds     (default 7200)
  MEGAPLAN_SHANNON_CONTEXT_OP_TIMEOUT_SECONDS → context_op_timeout_seconds (default 180)
  MEGAPLAN_SHANNON_HANDSHAKE_PROBABILITY     → handshake_probability       (default 0.8)
  MEGAPLAN_SHANNON_HANDSHAKE_DELAY_MIN_SECONDS → handshake_delay_min_seconds (default 1.0)
  MEGAPLAN_SHANNON_HANDSHAKE_DELAY_MAX_SECONDS → handshake_delay_max_seconds (default 15.0)
  MEGAPLAN_SHANNON_SESSION_ROULETTE          → session_roulette_enabled    (default True)
  MEGAPLAN_SHANNON_SESSION_COMPACT_PROBABILITY → session_compact_probability (default 0.25)
  MEGAPLAN_SHANNON_CONTEXT_OP_DELAY_MIN_SECONDS → context_op_delay_min_seconds (default 1.0)
  MEGAPLAN_SHANNON_CONTEXT_OP_DELAY_MAX_SECONDS → context_op_delay_max_seconds (default 15.0)
  MEGAPLAN_SHANNON_PASTE_FIRST_TURN          → paste_first_turn            (default True)
  MEGAPLAN_SHANNON_MAX_OUTPUT_TOKENS         → max_output_tokens           (default 128000)
  MEGAPLAN_SHANNON_BASH_TIMEOUT_MS           → launched Claude Bash timeout (default 7200000)
  MEGAPLAN_SHANNON_DROP_ROOT                 → drop_root  (default: auto from root+trusted_container)
  MEGAPLAN_SHANNON_CHMOD_WORKSPACE           → chmod_workspace             (default True)
  MEGAPLAN_SHANNON_ENV_SCRUB                 → env_scrub                   (default True)
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import os
import random
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path
from typing import Any

# Absolute path to the megaplan-vendored Shannon fork. The runtime invokes
# ``bun <VENDORED_SHANNON_PATH>`` instead of relying on an ``@dexh/shannon``
# binary on PATH. ``_launch_command`` may wrap the argv in ``su -c <shell-join>``
# (drop-root path), so the absolute path is required for the shell join to
# resolve regardless of the child's cwd.
VENDORED_SHANNON_PATH = (
    Path(__file__).resolve().parents[1] / "vendor" / "shannon" / "index.ts"
).resolve()

from megaplan.runtime.process import OrphanDetectedError, TmuxSession, pane_pids
from megaplan.types import CliError, MOCK_ENV_VAR, PlanState
from megaplan._core import creative_form_id, read_json, schemas_root
from megaplan.prompts import create_claude_prompt
from megaplan.prompts._projection import check_prompt_size
from megaplan.prompts.review import compact_review_prompt
from megaplan.schemas import get_execution_schema_key
from megaplan.workers._impl import (
    STEP_SCHEMA_FILENAMES,
    WorkerResult,
    _activity_callback_for_state,
    _check_mock_safe,
    _extract_claude_usage,
    _external_worker_env,
    _normalize_worker_payload,
    _worker_stream_idle_timeout_seconds,
    mock_worker_output,
    resolve_work_dir,
    run_command,
    session_key_for,
    validate_payload,
)
from megaplan.workers._projection_caps import shannon_projection_capabilities


# Sentinel marker the vendored fork carries on line 2 of index.ts. Mirrors
# ``_SHANNON_VENDOR_SENTINEL`` in ``megaplan/_core/io.py``.
_SHANNON_VENDOR_SENTINEL = "MEGAPLAN_SHANNON_VENDORED v1"

# Module-level cache so _assert_vendored_shannon_sentinel() runs at most once
# per Python process even when called from every run_shannon_step invocation.
_shannon_vendor_sentinel_ok = False


def _assert_vendored_shannon_sentinel() -> None:
    """Fail fast if the vendored Shannon fork is missing or unrecognized.

    Replaces the prior auto-patcher's graceful-degradation net: if the
    sentinel comment isn't on the first few lines of megaplan/vendor/shannon/index.ts,
    the megaplan patches are not present and slash-completion / paste-first-turn
    / env-scrub silently break. Raise a ``CliError(code='shannon_vendor_missing')``
    so the operator sees the problem at the boundary.
    """
    global _shannon_vendor_sentinel_ok
    if _shannon_vendor_sentinel_ok:
        return
    try:
        with VENDORED_SHANNON_PATH.open("r", encoding="utf-8") as fh:
            head = "".join(next(fh, "") for _ in range(5))
    except OSError as exc:
        raise CliError(
            "shannon_vendor_missing",
            f"Vendored Shannon fork not readable at {VENDORED_SHANNON_PATH}: {exc}. "
            "Ensure megaplan/vendor/shannon/index.ts is present and run "
            "`bun install` inside megaplan/vendor/shannon/.",
        ) from exc
    if _SHANNON_VENDOR_SENTINEL not in head:
        raise CliError(
            "shannon_vendor_missing",
            f"Vendored Shannon fork at {VENDORED_SHANNON_PATH} is missing the "
            f"`{_SHANNON_VENDOR_SENTINEL}` sentinel — patches not applied. "
            "Re-stage the vendored fork (see megaplan/vendor/shannon/VENDOR.md).",
        )
    _shannon_vendor_sentinel_ok = True


def _raw_contains_success_result(raw: str) -> bool:
    """Return True when Shannon/Claude JSON output includes a success result."""
    if not raw.strip():
        return False

    candidates: list[Any] = []
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        parsed = None
    if isinstance(parsed, list):
        candidates.extend(parsed)
    elif isinstance(parsed, dict):
        candidates.append(parsed)

    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            parsed_line = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed_line, dict):
            candidates.append(parsed_line)

    for item in candidates:
        if not isinstance(item, dict):
            continue
        if item.get("type") == "result" and item.get("subtype") == "success":
            return True
        if item.get("terminal_reason") == "completed" and item.get("is_error") is False:
            return True
    return False


_TMUX_DIED_MARKERS = (
    "no server running",
    "no current client",
    "can't find session",
    "lost server",
)


def _raw_indicates_tmux_died(raw: str) -> bool:
    """Return True when Shannon's output reveals its tmux server/session died.

    The vendored Shannon launcher drives Claude inside a tmux session; when that
    server dies — e.g. during the ``waitForPrompt`` startup poll — it surfaces a
    line like ``tmux capture-pane -pt <id> -S -40 failed with 1: no server
    running``. That is a transient INFRASTRUCTURE stall (the Claude session
    crashed before producing a result), NOT a model/result error. It must be
    classified as a retryable ``worker_stall`` (which sheds the session and
    retries fresh), never misparsed as a bad result / ``internal_error`` because
    the only surviving stdout was Claude's ``system/init`` line.
    """
    if not raw:
        return False
    low = raw.lower()
    if "tmux" not in low and "capture-pane" not in low:
        return False
    return any(marker in low for marker in _TMUX_DIED_MARKERS)


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


@dataclasses.dataclass(frozen=True)
class ShannonConfig:
    """Every tunable Shannon knob in one place.

    Construct via :meth:`ShannonConfig.load` which reads ``env`` (defaulting
    to ``os.environ``) and falls back to safe defaults.  All existing env-var
    names are preserved for back-compat — see the module docstring for the
    full mapping table.
    """

    # ── readiness probe ───────────────────────────────────────────────────
    readiness_probe_raw: str     # lowercased MEGAPLAN_SHANNON_READINESS_PROBE
    readiness_probe_forced: bool # raw == "always"
    trusted_container: bool      # MEGAPLAN_TRUSTED_CONTAINER

    # ── timeouts ─────────────────────────────────────────────────────────
    readiness_timeout_seconds: int   # MEGAPLAN_SHANNON_READINESS_TIMEOUT_SECONDS
    execute_timeout_seconds: int     # MEGAPLAN_SHANNON_EXECUTE_TIMEOUT_SECONDS
    context_op_timeout_seconds: int  # MEGAPLAN_SHANNON_CONTEXT_OP_TIMEOUT_SECONDS

    # ── handshake ────────────────────────────────────────────────────────
    handshake_probability: float        # MEGAPLAN_SHANNON_HANDSHAKE_PROBABILITY
    handshake_delay_min_seconds: float  # MEGAPLAN_SHANNON_HANDSHAKE_DELAY_MIN_SECONDS
    handshake_delay_max_seconds: float  # MEGAPLAN_SHANNON_HANDSHAKE_DELAY_MAX_SECONDS

    # ── session strategy ─────────────────────────────────────────────────
    session_roulette_enabled: bool      # MEGAPLAN_SHANNON_SESSION_ROULETTE
    session_compact_probability: float  # MEGAPLAN_SHANNON_SESSION_COMPACT_PROBABILITY

    # ── context-op delays ────────────────────────────────────────────────
    context_op_delay_min_seconds: float  # MEGAPLAN_SHANNON_CONTEXT_OP_DELAY_MIN_SECONDS
    context_op_delay_max_seconds: float  # MEGAPLAN_SHANNON_CONTEXT_OP_DELAY_MAX_SECONDS

    # ── delivery ─────────────────────────────────────────────────────────
    paste_first_turn: bool  # MEGAPLAN_SHANNON_PASTE_FIRST_TURN; default native-style stdin handoff

    # ── output budget ────────────────────────────────────────────────────
    max_output_tokens: int  # MEGAPLAN_SHANNON_MAX_OUTPUT_TOKENS

    # ── root-drop / runtime env ──────────────────────────────────────────
    drop_root: bool        # MEGAPLAN_SHANNON_DROP_ROOT (or auto-detect)
    chmod_workspace: bool  # MEGAPLAN_SHANNON_CHMOD_WORKSPACE
    claude_config_mode: str  # MEGAPLAN_SHANNON_CLAUDE_CONFIG_MODE; isolated|native
    pin_claude: bool   # MEGAPLAN_SHANNON_PIN_CLAUDE; pin resolved claude bin per-run (default True)
    claude_bin: str    # MEGAPLAN_SHANNON_CLAUDE_BIN; explicit claude binary path override

    # ── structural tells (T9 targets; fields land here now) ──────────────
    voice: str       # prompt voice; no env-var yet; default "announced"
    env_scrub: bool  # MEGAPLAN_SHANNON_ENV_SCRUB; scrub MEGAPLAN_*/SHANNON_* from child

    def readiness_probe_enabled(self, session_agent: str) -> bool:
        """Resolve whether the readiness probe should run for this session_agent."""
        if self.readiness_probe_forced:
            return True
        raw = self.readiness_probe_raw
        if raw in {"1", "true", "yes", "on"}:
            return True
        if raw in {"0", "false", "no", "off"}:
            return False
        return session_agent == "claude" or self.trusted_container

    @classmethod
    def load(
        cls,
        profile: dict,
        env: dict[str, str] | None = None,
        state: object | None = None,
    ) -> "ShannonConfig":
        """Construct a ShannonConfig from environment variables.

        ``env`` defaults to ``os.environ`` when ``None``.  ``profile`` and
        ``state`` are reserved for future profile-level overrides; currently
        env-vars are the sole source.
        """
        if env is None:
            env = os.environ

        def _get(name: str) -> str:
            return env.get(name, "").strip()

        def _truthy(name: str) -> bool | None:
            raw = _get(name).lower()
            if raw in {"1", "true", "yes", "on"}:
                return True
            if raw in {"0", "false", "no", "off"}:
                return False
            return None

        def _int_pos(name: str, default: int) -> int:
            raw = _get(name)
            if not raw:
                return default
            try:
                return max(1, int(raw))
            except ValueError:
                return default

        def _float_unit(name: str, default: float) -> float:
            raw = _get(name)
            if not raw:
                return default
            try:
                return min(1.0, max(0.0, float(raw)))
            except ValueError:
                return default

        def _float_pos(name: str, default: float) -> float:
            raw = _get(name)
            if not raw:
                return default
            try:
                return max(0.0, float(raw))
            except ValueError:
                return default

        readiness_probe_raw = _get("MEGAPLAN_SHANNON_READINESS_PROBE").lower()
        trusted_container = _truthy("MEGAPLAN_TRUSTED_CONTAINER") is True
        drop_root_cfg = _truthy("MEGAPLAN_SHANNON_DROP_ROOT")
        if drop_root_cfg is not None:
            drop_root = drop_root_cfg
        else:
            drop_root = _running_as_root() and trusted_container
        _roulette = _truthy("MEGAPLAN_SHANNON_SESSION_ROULETTE")
        claude_config_mode = (
            _get("MEGAPLAN_SHANNON_CLAUDE_CONFIG_MODE").lower() or "isolated"
        )
        if claude_config_mode not in {"isolated", "native"}:
            raise CliError(
                "worker_error",
                "Invalid MEGAPLAN_SHANNON_CLAUDE_CONFIG_MODE "
                f"{claude_config_mode!r}; expected 'isolated' or 'native'.",
            )
        pin_claude = _truthy("MEGAPLAN_SHANNON_PIN_CLAUDE")
        claude_bin = _get("MEGAPLAN_SHANNON_CLAUDE_BIN")

        return cls(
            readiness_probe_raw=readiness_probe_raw,
            readiness_probe_forced=(readiness_probe_raw == "always"),
            trusted_container=trusted_container,
            readiness_timeout_seconds=_int_pos("MEGAPLAN_SHANNON_READINESS_TIMEOUT_SECONDS", 120),
            execute_timeout_seconds=_int_pos("MEGAPLAN_SHANNON_EXECUTE_TIMEOUT_SECONDS", 7200),
            context_op_timeout_seconds=_int_pos("MEGAPLAN_SHANNON_CONTEXT_OP_TIMEOUT_SECONDS", 180),
            handshake_probability=_float_unit("MEGAPLAN_SHANNON_HANDSHAKE_PROBABILITY", 0.8),
            handshake_delay_min_seconds=_float_pos("MEGAPLAN_SHANNON_HANDSHAKE_DELAY_MIN_SECONDS", 1.0),
            handshake_delay_max_seconds=_float_pos("MEGAPLAN_SHANNON_HANDSHAKE_DELAY_MAX_SECONDS", 15.0),
            session_roulette_enabled=(True if _roulette is None else bool(_roulette)),
            session_compact_probability=_float_unit("MEGAPLAN_SHANNON_SESSION_COMPACT_PROBABILITY", 0.25),
            context_op_delay_min_seconds=_float_pos("MEGAPLAN_SHANNON_CONTEXT_OP_DELAY_MIN_SECONDS", 1.0),
            context_op_delay_max_seconds=_float_pos("MEGAPLAN_SHANNON_CONTEXT_OP_DELAY_MAX_SECONDS", 15.0),
            paste_first_turn=(_truthy("MEGAPLAN_SHANNON_PASTE_FIRST_TURN") is not False),
            max_output_tokens=_int_pos("MEGAPLAN_SHANNON_MAX_OUTPUT_TOKENS", 128000),
            drop_root=drop_root,
            chmod_workspace=(_truthy("MEGAPLAN_SHANNON_CHMOD_WORKSPACE") is not False),
            claude_config_mode=claude_config_mode,
            pin_claude=(True if pin_claude is None else bool(pin_claude)),
            claude_bin=claude_bin,
            voice="announced",
            env_scrub=(_truthy("MEGAPLAN_SHANNON_ENV_SCRUB") is not False),
        )


# ---------------------------------------------------------------------------
# Readiness handshake
# ---------------------------------------------------------------------------


_SHANNON_READINESS_PROMPTS = (
    "Hey, I just opened this agent window. Say ready when you are good to go.",
    "Hi, checking that this new agent tab is awake. A quick ready is enough.",
    "Hello. I am about to send the actual brief. Tell me when you are ready.",
    "Hey there, this is just a quick warmup message. Say all set when you are.",
    "Hi, making sure this new session is live. Just say yep when you can take the brief.",
    "Hey, I am getting this agent window started. Let me know when you are ready.",
    "Hello, I will send the task in a moment. Say good to go when you are set.",
    "Hi, just checking that you are loaded in. Answer with ready when you are.",
    "Hey, new session check before I paste the work. Say send it when ready.",
    "Hello, this is a quick hello before the real request. Just confirm you are ready.",
    "Hey, can you confirm this window is ready? A short yes is fine.",
    "Hi, I am opening a fresh agent session. Say all good when you are set.",
    "Hello, I am going to hand you a brief next. Tell me when you are ready.",
    "Hey, quick startup check. Say ready when you can continue.",
    "Hi, making sure the agent is ready before the task. Give me a quick okay.",
    "Hey, I just spun up this session. Say ready whenever you are.",
    "Hello, checking in before I send the work. A quick all set is fine.",
    "Hi, this is the little pre-task ping. Just answer when you are ready.",
    "Hey, waiting for this new agent window to settle. Say settled when it has.",
    "Hello, I am about to send instructions. Confirm when you can receive them.",
    "Hi, quick check that you are here. Say here when you are ready.",
    "Hey, I opened this session for a task. Let me know when you are set.",
    "Hello, the actual brief is coming next. Say ready for it when you are.",
    "Hi, just making sure the session started cleanly. Send a quick okay.",
    "Hey, before I send the real prompt, tell me you are ready.",
    "Hello, new agent window is up. Say good to go when you are.",
    "Hi, I am checking this session before sending the brief. Confirm you are ready.",
    "Hey, this is just a starter message. Say all set when you are.",
    "Hello, can you let me know you are ready? Any short confirmation works.",
    "Hi, I will send the request after you answer. Say ready when ready.",
    "Hey, quick agent-window check. Tell me when you can start.",
    "Hello, I am waiting for the new session to be usable. Say usable when it is.",
    "Hi, this is just to wake up the session. Give me a quick yep.",
    "Hey, I am opening with a small check first. Let me know when you are ready.",
    "Hello, please confirm you are ready for the brief. Keep it short.",
    "Hi, new window looks open. Say ready when it is actually ready.",
    "Hey, I have a task to send after this. Say all set when you are.",
    "Hello, just testing the session before the brief. A quick ready is fine.",
    "Hi, I am here with the next task shortly. Tell me when you are ready.",
    "Hey, let me know this agent window is responsive. Say yep if it is.",
    "Hello, I am going to pass you the real request next. Say send it when ready.",
    "Hi, quick first message for the new session. Say ready when you are set.",
    "Hey, checking that this session can accept input. Confirm when it can.",
    "Hello, please answer with any short ready check once this window is ready.",
    "Hi, I just launched this agent. Say good when you are good.",
    "Hey, the task is coming in the next message. Tell me when you are ready.",
    "Hello, warmup first, brief second. Say all set when you are.",
    "Hi, making sure this fresh session is working. A quick okay works.",
    "Hey, I am about to give you work. Say ready when you are set.",
    "Hello, this is just a quick session check. Reply with a short confirmation.",
    "Hi, new agent session here. Say ready for the brief when you can take it.",
    "Hey, checking the room before I send the actual request. Say good when ready.",
    "Hello, I need this session ready before the brief. Confirm when it is.",
    "Hi, I am waiting on this agent window to be ready. Say ready when ready.",
    "Hey, simple startup ping. A quick yep is enough.",
    "Hello, I will paste the task after this. Say send it when ready.",
    "Hi, can you confirm the session is ready? Just say yes if it is.",
    "Hey, first message in a new agent window. Say all set when you are.",
    "Hello, the actual instructions will follow. Give me a short ready check.",
    "Hi, just making sure you are not still starting up. Say ready when you are done.",
    "Hey, I am checking that this new window is alive. Say alive when ready.",
    "Hello, please get ready for the brief. Tell me when you are ready.",
    "Hi, this is only the handshake message. Say all set when you are.",
    "Hey, quick check before I send the actual prompt. A short okay is fine.",
    "Hello, I opened a new session for the next task. Confirm when ready.",
    "Hi, I am going to send the brief once you answer. Say ready when ready.",
    "Hey, confirm you are ready and I will send the work. Any short yes works.",
    "Hello, just starting this agent window. Say good to go when you are good.",
    "Hi, I am giving the session a second before the task. Let me know when ready.",
    "Hey, this is a preflight hello. Say set when you are set.",
    "Hello, checking that you can respond before the real ask. Say yep if you can.",
    "Hi, I have the task queued up. Tell me when you are ready.",
    "Hey, new Claude window check. Say ready when you are ready.",
    "Hello, I am about to hand over the brief. Say send it when ready.",
    "Hi, please confirm this session is ready to work. A quick ready works.",
    "Hey, I am waiting for the agent to be ready. Say all good when it is.",
    "Hello, this is just the opener for a new session. Say ready when ready.",
    "Hi, I will send details once you confirm. Say set when you are set.",
    "Hey, making sure the window is responsive first. Give me a quick yep.",
    "Hello, the real message comes next. Tell me when you are ready.",
    "Hi, I am doing a quick startup check. A short ready is enough.",
    "Hey, I just opened this for a task. Say good to go when you are set.",
    "Hello, please answer with ready when this session can take the brief.",
    "Hi, quick handshake before the request. Say all set when ready.",
    "Hey, I need to know you are ready before I send the task. Just confirm.",
    "Hello, checking this new agent window before the brief. Say okay when ready.",
    "Hi, I am about to send the work over. Say good when you are good.",
    "Hey, just confirming this session is usable. Tell me when it is.",
    "Hello, I will send the main request after your reply. Say send it when ready.",
    "Hi, new session opened. Say ready for the brief when you are.",
    "Hey, small opening message before the task. A quick yep works.",
    "Hello, please confirm you are up and ready. Keep it short.",
    "Hi, I am checking that this agent has started. Say started when it has.",
    "Hey, the next message will have the actual brief. Say ready when ready.",
    "Hello, first I need a ready check. Say all set when you are set.",
    "Hi, just a quick new-window hello. Tell me when ready.",
    "Hey, I am about to send you the real prompt. Say send it when ready.",
    "Hello, making sure we are connected before the task. A short yes works.",
    "Hi, please let me know this session is ready. Say ready when ready.",
    "Hey, ready check before I pass over the brief. Say good to go when ready.",
)


def _env_truthy(name: str) -> bool | None:
    raw = os.getenv(name)
    if raw is None:
        return None
    normalized = raw.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    return None


_SHANNON_READ_ONLY_ALLOWED_TOOLS = (
    "Read",
    "Grep",
    "Glob",
    "WebFetch",
    "WebSearch",
)
_SHANNON_READ_ONLY_DISALLOWED_TOOLS = (
    "Bash",
    "Edit",
    "MultiEdit",
    "NotebookEdit",
    "TodoWrite",
    "Task",
    "Write",
)


def _shannon_bash_timeout_ms() -> int:
    """Per-command Bash-tool timeout for the Claude CLI that Shannon launches."""
    raw = os.getenv("MEGAPLAN_SHANNON_BASH_TIMEOUT_MS", "").strip()
    if not raw:
        return 7200000
    try:
        return max(1, int(raw))
    except ValueError:
        return 7200000


# ---------------------------------------------------------------------------
# Session-continuity strategy
# ---------------------------------------------------------------------------
#
# Shannon can reload a Claude conversation by uuid via the Claude CLI's on-disk
# session store: the deterministic per-(plan,step) tmux pane is torn down and
# recreated on every run (see run_shannon_step), so continuity rides on
# ``--resume <id>`` reloading the persisted session, not on pane liveness.
#
# Policy: NEVER plain-resume a session. Carrying the full prior conversation
# forward clouds the next turn's context (and megaplan re-sends everything a
# phase needs from disk on every call, so the old in-session history is dead
# weight). So whenever a session COULD be reused we shed its context instead:
#
#   clear    resume, inject ``/clear`` first — wipe context (Claude rotates to a
#            fresh session id, which the work turn then resumes). The common case.
#   compact  resume, inject ``/compact`` first — keep a trimmed summary instead
#            of a full wipe. The occasional case.
#   new      no prior session (first use) or an explicit --refresh → fresh session.
#
# ``resume`` survives only as the legacy path when the strategy is disabled.
# The clear/compact split is env-tunable; clear dominates by default.

_SESSION_STRATEGIES = ("resume", "compact", "clear", "new")


def _select_session_strategy(
    step: str,
    *,
    has_session: bool,
    explicit_fresh: bool,
    slash_supported: bool = True,
    cfg: "ShannonConfig | None" = None,
) -> str:
    """Pick a session strategy for this Shannon run.

    Returns one of :data:`_SESSION_STRATEGIES`. With the strategy enabled we
    never plain-``resume`` (full prior context clouds the turn): a reusable
    session is always shed — ``clear`` most of the time, ``compact`` occasionally
    (``MEGAPLAN_SHANNON_SESSION_COMPACT_PROBABILITY``, default 0.25). ``new`` is
    used only when there is no prior session or the caller forced a refresh.

    ``slash_supported`` reflects whether the installed shannon can actually
    complete a ``/clear``/``/compact`` turn (the patch is present). When it can't
    — a different shannon version, a read-only package dir, or auto-patch off on
    another user's machine — keep the SAME policy (never carry stale context) but
    switch the MECHANISM to a fresh ``new`` session: it sheds context just as
    cleanly, with no op turn that would otherwise burn the op timeout.

    ``cfg`` is optional for callers (unit tests) that invoke the function
    directly without a fully-loaded config; when absent it is auto-loaded from
    ``os.environ``.
    """
    if cfg is None:
        cfg = ShannonConfig.load({})
    if not has_session:
        return "new"
    if not cfg.session_roulette_enabled:
        # Legacy: only execute resumed, and only when not explicitly refreshed.
        return "resume" if (step == "execute" and not explicit_fresh) else "new"
    if explicit_fresh:
        # Honor an explicit refresh. Only execute carries a real refresh signal;
        # a non-execute phase's blanket fresh is policy, not user intent, so the
        # caller passes explicit_fresh=False for those and the roll proceeds.
        return "new"
    if not slash_supported:
        # No working /clear or /compact — shed context the safe way: fresh session.
        return "new"
    # Reuse path: shed context every time — clear most of the time, compact some.
    # NOTE (planned, T7/T8): this and the other ``random.*`` call sites in this
    # module will be re-seeded from a per-(plan_id, step_id, iteration) RNG so a
    # given turn's rolled strategy / handshake / jitter is reproducible across
    # reruns of the same step. The reproducibility trade is intentional —
    # randomness here is for human-likeness, not security; reproducible rolls
    # make stalls in CI debuggable without giving up the variance the policy needs.
    return "compact" if random.random() < cfg.session_compact_probability else "clear"


# ---------------------------------------------------------------------------
# Pure session plan (value types + planner)
# ---------------------------------------------------------------------------
#
# T6: ``plan_session`` is the pure, rng-seeded session planner. It owns every
# strategy/handshake/context-op decision and produces a fully-described
# :class:`SessionPlan`. Purity invariants (validated by tests):
#
#   * No I/O whatsoever — no subprocess, no time, no os.environ, no _impl
#     imports. Randomness comes from the injected ``rng`` only; the
#     module-global ``random`` is never touched inside ``plan_session``.
#   * Deterministic given ``rng``: same seed → identical SessionPlan.
#
# The bridge in ``run_shannon_step`` consumes ``plan.main`` through a thin
# adapter that maps Turn → (command, stdin, timeout, expect). Pre-turns are
# emitted as data only; later sprints (T6b) will route them through a single
# turn-runner. The vendored Shannon fork always supports slash-commands, so
# the prior ``slash_supported`` parameter is gone.


@dataclasses.dataclass(frozen=True)
class Turn:
    """A single Shannon invocation described as data (no commands yet).

    ``body`` is the user content for this turn (``/clear``, ``/compact``, a
    readiness prompt, or "" for the main turn whose body is the caller's
    real phase prompt). ``delivery`` is ``"argv"`` for ``-p`` launchers or
    ``"stdin"`` for the native-style stream-json prompt handoff. ``expect``
    annotates what the consumer should look for in the response — currently
    "envelope", "non_empty", "completion", or "rotation". ``pre_sleep_s`` is
    pre-computed by the injected rng (e.g. ``rng.uniform(lo, hi)``) so the
    consumer just calls ``time.sleep(turn.pre_sleep_s)`` — sampling stays out
    of the I/O path.
    """

    session_id: str
    resume: bool
    body: str
    delivery: str
    expect: str
    timeout: int
    pre_sleep_s: float


@dataclasses.dataclass(frozen=True)
class SessionPlan:
    """The full plan for one ``run_shannon_step`` invocation.

    ``kind`` is the chosen strategy (``"new"`` | ``"resume"`` | ``"clear"`` |
    ``"compact"``). ``session_id`` is the id the main turn will run under
    (the freshly generated id for ``new``, the stored id for everything
    else). ``pre_turns`` are the handshake / context-op turns in execution
    order. ``voice`` is a structural-tell knob (T9) carried for the bridge.
    """

    kind: str
    session_id: str
    pre_turns: tuple[Turn, ...]
    main: Turn
    voice: str


def _serialize_session_plan(plan: SessionPlan) -> dict[str, Any]:
    """Serialize ``plan`` into the ``shannon_plan`` receipt field.

    Records the rolled strategy kind, the chosen session id, the structural
    voice, and for every pre-turn the *kind* (handshake / context-op label
    derived from ``expect``) and the pre-rolled human-likeness delay so a
    forensic replay can verify exact reproducibility from the seed.
    """
    pre_turn_records: list[dict[str, Any]] = []
    for pt in plan.pre_turns:
        if pt.expect == "non_empty":
            pt_kind = "handshake"
        elif pt.body.startswith("/clear"):
            pt_kind = "clear"
        elif pt.body.startswith("/compact"):
            pt_kind = "compact"
        else:
            pt_kind = "context_op"
        pre_turn_records.append({
            "kind": pt_kind,
            "session_id": pt.session_id,
            "pre_sleep_s": pt.pre_sleep_s,
        })
    return {
        "kind": plan.kind,
        "session_id": plan.session_id,
        "voice": plan.voice,
        "pre_turns": pre_turn_records,
        "main": {
            "delivery": plan.main.delivery,
            "resume": plan.main.resume,
            "pre_sleep_s": plan.main.pre_sleep_s,
        },
    }


def _rng_session_id(rng: random.Random) -> str:
    """Build a deterministic UUIDv4 from the injected rng.

    ``uuid.uuid4()`` would pull entropy from ``os.urandom`` (I/O), which
    breaks ``plan_session`` purity and reproducibility. We instead reuse the
    rng's bytes and stamp the standard v4 version + variant nibbles so the
    Claude CLI and Shannon (which only care about UUID shape, not provenance)
    accept it as a session id.
    """
    b = bytearray(rng.randbytes(16))
    b[6] = (b[6] & 0x0F) | 0x40  # version 4
    b[8] = (b[8] & 0x3F) | 0x80  # variant 10xx
    return str(uuid.UUID(bytes=bytes(b)))


def _rng_uniform_or_zero(rng: random.Random, low: float, high: float) -> float:
    """``rng.uniform`` with the same guard rails as the prior delay samplers.

    Mirrors :func:`_sample_handshake_delay` / :func:`_sample_context_op_delay`:
    a non-positive upper bound yields 0; an inverted range collapses to the
    upper bound; otherwise sample uniformly. Pure (no time, no global random).
    """
    if high <= 0:
        return 0.0
    if low > high:
        low = high
    return rng.uniform(low, high)


def plan_session(
    step: str,
    *,
    stored_id: str | None,
    fresh: bool,
    cfg: ShannonConfig,
    rng: random.Random,
) -> SessionPlan:
    """Pure, rng-seeded planner for a Shannon run.

    Drops ``slash_supported`` (the vendored fork always supports
    ``/clear``/``/compact``). The legacy ``_select_session_strategy`` logic is
    preserved verbatim — only the mechanism changes:

    * randomness flows through the injected ``rng`` (never the module-global
      ``random``);
    * pre-turn delays are pre-sampled here, so the consumer just
      ``time.sleep(turn.pre_sleep_s)``;
    * new session ids are derived from the rng (never ``uuid.uuid4()``,
      which would call ``os.urandom`` and break purity).

    Determinism is the point: a given (rng-state) input produces an identical
    :class:`SessionPlan`. T7/T8 will seed the caller's rng from
    ``(plan_id, step, iteration)`` and persist that seed for forensic replay.
    """
    has_session = stored_id is not None
    explicit_fresh = fresh if step == "execute" else False

    # ── strategy selection (mirrors _select_session_strategy verbatim) ──
    if not has_session:
        kind = "new"
    elif not cfg.session_roulette_enabled:
        kind = "resume" if (step == "execute" and not explicit_fresh) else "new"
    elif explicit_fresh:
        kind = "new"
    else:
        kind = (
            "compact"
            if rng.random() < cfg.session_compact_probability
            else "clear"
        )

    # ── main turn session id (derive from rng for "new"; reuse otherwise) ──
    if kind == "new":
        main_session_id = _rng_session_id(rng)
        main_resume = False
    else:
        # ``has_session`` is True on every non-"new" branch, so stored_id is
        # guaranteed non-None here.
        assert stored_id is not None
        main_session_id = stored_id
        main_resume = True

    # ── pre-turns in execution order: handshake, then context-op ──
    pre_turns: list[Turn] = []
    # Pre-sample the main turn's pre-sleep so a handshake landing leaves a
    # human-like beat before the real work turn. Zero when no handshake fires.
    main_pre_sleep = 0.0

    if kind == "new":
        # Handshake roll. ``cfg.readiness_probe_enabled(session_agent)`` is a
        # deployment-time gate (not a roll) and lives at the consumption site
        # — plan_session has no ``session_agent`` input and doesn't gate on
        # it; it decides only whether the probability roll fires.
        handshake_roll = rng.random()
        if cfg.readiness_probe_forced or handshake_roll < cfg.handshake_probability:
            handshake_sleep = _rng_uniform_or_zero(
                rng,
                cfg.handshake_delay_min_seconds,
                cfg.handshake_delay_max_seconds,
            )
            readiness_prompt = rng.choice(_SHANNON_READINESS_PROMPTS)
            pre_turns.append(
                Turn(
                    session_id=main_session_id,
                    resume=False,
                    body=readiness_prompt,
                    delivery="argv",
                    expect="non_empty",
                    timeout=cfg.readiness_timeout_seconds,
                    pre_sleep_s=handshake_sleep,
                )
            )
            # The handshake turn creates the session via ``--session-id``; the
            # main work turn then resumes it.
            main_resume = True
            main_pre_sleep = _rng_uniform_or_zero(
                rng,
                cfg.handshake_delay_min_seconds,
                cfg.handshake_delay_max_seconds,
            )
    elif kind in ("clear", "compact"):
        op_sleep = _rng_uniform_or_zero(
            rng,
            cfg.context_op_delay_min_seconds,
            cfg.context_op_delay_max_seconds,
        )
        slash = "/clear" if kind == "clear" else "/compact"
        pre_turns.append(
            Turn(
                session_id=main_session_id,  # == stored_id on this branch
                resume=True,
                body=slash,
                delivery="argv",
                expect="rotation" if kind == "clear" else "completion",
                timeout=cfg.context_op_timeout_seconds,
                pre_sleep_s=op_sleep,
            )
        )

    main = Turn(
        session_id=main_session_id,
        resume=main_resume,
        body="",  # the caller substitutes the real phase prompt
        delivery="argv",  # caller overrides to "stdin" for the native-style main turn
        expect="envelope",
        timeout=cfg.execute_timeout_seconds,
        pre_sleep_s=main_pre_sleep,
    )

    return SessionPlan(
        kind=kind,
        session_id=main_session_id,
        pre_turns=tuple(pre_turns),
        main=main,
        voice=cfg.voice,
    )


def _shannon_run_nonce(state: PlanState, step: str) -> int:
    """Advance and return a per-state Shannon run nonce for retry-safe new sessions."""
    iteration = int(state.get("iteration", 0) or 0)
    meta = state.setdefault("meta", {})
    nonces = meta.setdefault("shannon_run_nonces", {})
    if not isinstance(nonces, dict):
        nonces = {}
        meta["shannon_run_nonces"] = nonces
    key = f"{step}:{iteration}"
    current = int(nonces.get(key, 0) or 0) + 1
    nonces[key] = current
    return current


def _seeded_rng_for_run(state: PlanState, step: str, *, nonce: int = 0) -> random.Random:
    """Per-(plan, step, iteration) seeded rng for ``plan_session``.

    Pinning randomness to (plan_id, step, iteration, nonce) keeps rolls
    inspectable while avoiding a poisonous collision after a failed "new"
    Shannon session. Without the nonce, retries reuse the same session id and
    can keep timing out against the previous transcript/session state.
    """
    plan_id = str(state.get("name", ""))
    iteration = int(state.get("iteration", 0) or 0)
    seed_bytes = hashlib.sha256(
        f"{plan_id}|{step}|{iteration}|{nonce}".encode("utf-8")
    ).digest()
    return random.Random(int.from_bytes(seed_bytes[:8], "big"))


# ---------------------------------------------------------------------------
# Unified turn executor (T7)
# ---------------------------------------------------------------------------
#
# ``run_turn`` is the single impure half of the planner/runner split. It maps
# one planned :class:`Turn` to one ``run_command`` invocation: it sleeps the
# pre-sampled human-like delay, builds the argv (``-p`` vs
# ``--input-format=stream-json``, ``--resume`` vs ``--session-id``), pipes
# stdin when the turn is a paste-first delivery, wraps the argv in the ctx
# nonroot prefix (no per-turn recomputation), threads the megaplan-owned
# liveness/idle/activity plumbing into ``run_command``, and consolidates the
# landed session id from any output shape. The CliError taxonomy
# (``worker_stall`` / ``worker_timeout`` / ``connection_error``) is preserved
# unchanged so the ``_impl.py`` retry loop at line ~2681 keeps working — we
# only decorate ``error.extra['session_id']`` with the turn's id to give the
# downstream cleanup the resume key it needs.
#
# This task (T7) adds ``run_turn`` and ``session_id_of`` AS NEW CODE next to
# the old per-mode execute paths in ``run_shannon_step`` — the orchestrator
# rewrite that switches every turn through this single executor (and deletes
# the old paths) is T6b / T8 work.


@dataclasses.dataclass(frozen=True)
class TurnContext:
    """Per-run ambient context built ONCE by the orchestrator.

    ``base_flags`` is the stable main-argv skeleton (``bun``, the vendored
    index path, ``--model``, ``--output-format=stream-json``, ``--bare``,
    ``--effort``, ``--permission-mode`` flags, etc.) WITHOUT the per-turn
    ``-p``/``--input-format=stream-json`` selector and WITHOUT the per-turn
    ``--resume``/``--session-id`` flag. ``shannon_prefix`` and ``env`` are
    the return value of a SINGLE :func:`_prepare_nonroot_shannon_runtime`
    call; ``run_turn`` MUST NOT recompute them per turn.
    """

    base_flags: list[str]
    shannon_prefix: list[str]
    env: dict[str, str]
    work_dir: Path
    plan_dir: Path
    run_dir: Path
    claude_config_dir: str | None
    tmux_session: TmuxSession
    state: PlanState


@dataclasses.dataclass(frozen=True)
class TurnResult:
    """What one ``run_turn`` invocation produced.

    ``raw`` is the concatenated stdout+stderr (the shape every downstream
    parser already expects). ``landed_session_id`` is extracted via
    :func:`session_id_of` so a ``/clear`` rotation is observable without the
    caller re-parsing.
    """

    raw: str
    returncode: int
    duration_ms: int
    landed_session_id: str | None


def session_id_of(raw: str | None) -> str | None:
    """Extract the landed Shannon/Claude session id from any output shape.

    Consolidates the three on-the-wire shapes the existing parsers each
    handle separately:

    * ``--output-format=stream-json`` (NDJSON, one JSON object per line) —
      previously :func:`_stream_session_id`.
    * Legacy ``--output-format=json`` buffered array of transcript messages —
      previously the list branch of :func:`_envelope_session_id`.
    * A single dict envelope (top-level ``{"session_id": ...}``) — previously
      the dict branch of :func:`_envelope_session_id`.

    Returns the LATEST session id seen so a ``/clear`` rotation (a fresh
    ``session_id`` emitted on the trailing ``result`` / ``shannon_session``
    row) is reflected. Returns ``None`` when nothing parseable carries an id.
    Best-effort throughout: any line that fails to parse is skipped rather
    than aborting the whole scan.
    """
    if not raw or not isinstance(raw, str):
        return None

    def _sid_from_dict(obj: dict[str, Any]) -> str | None:
        sid = obj.get("session_id")
        if not sid and isinstance(obj.get("message"), dict):
            inner = obj["message"]
            sid = inner.get("sessionId") or inner.get("session_id")
        return str(sid) if sid else None

    # ── NDJSON pass: scan line-by-line, return the latest sid seen ──
    # An NDJSON document has >1 line and decodes to at least one dict per
    # line. A single-line document is handled by the single-document path
    # below (it's either a buffered array, a single result line, or a dict).
    lines = [ln for ln in raw.splitlines() if ln.strip()]
    if len(lines) > 1:
        found: str | None = None
        for line in lines:
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                # Mixed prose, or a pretty-printed JSON document spread across
                # lines — skip and let the single-document path try.
                continue
            if isinstance(obj, dict):
                sid = _sid_from_dict(obj)
                if sid:
                    found = sid
        if found is not None:
            return found

    # ── Single-document pass: dict envelope or buffered array ──
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if isinstance(data, dict):
        return _sid_from_dict(data)
    if isinstance(data, list):
        for msg in reversed(data):
            if isinstance(msg, dict):
                sid = _sid_from_dict(msg)
                if sid:
                    return sid
    return None


def _typed_control_prompt_env(turn: Turn) -> dict[str, str] | None:
    """Return the per-turn env addition for short control-message typing."""
    if turn.delivery != "argv":
        return None
    if turn.body in {"/clear", "/compact"} and turn.expect in {"completion", "rotation"}:
        return {"SHANNON_TYPE_PROMPT_MAX_CHARS": "256"}
    if turn.expect == "non_empty" and turn.body == "Hello, say ready when you are.":
        return {"SHANNON_TYPE_PROMPT_MAX_CHARS": "256"}
    return None


def run_turn(turn: Turn, ctx: TurnContext) -> TurnResult:
    """Execute one planned :class:`Turn` as a single ``run_command`` call.

    The unified executor. Replaces the per-mode argv-builders / stdin-pipers /
    liveness wiring scattered across the readiness-probe block, the
    context-op helper, the repair helper, and the main work-turn site. Each
    of those still runs from ``run_shannon_step`` today (T7 is additive); the
    orchestrator rewrite that routes every turn through here is T6b / T8.

    Pre-conditions / contract:

    * The orchestrator built ``ctx`` ONCE: ``ctx.shannon_prefix`` and
      ``ctx.env`` come from a single :func:`_prepare_nonroot_shannon_runtime`
      call. ``run_turn`` MUST NOT recompute them per turn.
    * ``turn.pre_sleep_s`` was pre-sampled by the rng-seeded planner;
      ``run_turn`` performs the actual ``time.sleep`` here — this is the
      impure half of the Step 5 (T6) purity split.
    * ``turn.delivery`` selects ``-p <body>`` (argv) vs
      ``--input-format=stream-json`` + body-as-stdin-user-message.
    * ``turn.resume`` selects ``--resume <sid>`` (reuse) vs
      ``--session-id <sid>`` (fresh).
    * CliError codes ``worker_stall`` / ``worker_timeout`` /
      ``connection_error`` propagate UNCHANGED so the ``_impl.py`` retry
      loop at line ~2681 keeps working. We only decorate
      ``error.extra['session_id']`` with the turn's id to give the
      downstream session-cleanup the resume key it needs.
    """
    if turn.pre_sleep_s > 0:
        time.sleep(turn.pre_sleep_s)

    command: list[str] = list(ctx.base_flags)
    stdin_text: str | None = None
    if turn.delivery == "argv":
        command.extend(["-p", turn.body])
    elif turn.delivery == "stdin":
        command.append("--input-format=stream-json")
        stdin_text = json.dumps(
            {"type": "user", "message": {"role": "user", "content": turn.body}}
        )
    else:
        raise CliError(
            "worker_error",
            f"Unknown Turn.delivery {turn.delivery!r}; expected 'argv' or 'stdin'.",
        )

    if turn.resume:
        command.extend(["--resume", turn.session_id])
    else:
        command.extend(["--session-id", turn.session_id])

    if ctx.shannon_prefix:
        launch_command = [
            *ctx.shannon_prefix,
            _shell_join_command(command, ctx.work_dir),
        ]
    else:
        launch_command = command

    run_env = ctx.env
    typed_env = _typed_control_prompt_env(turn)
    if typed_env is not None:
        run_env = {**ctx.env, **typed_env}

    try:
        result = run_command(
            launch_command,
            cwd=ctx.work_dir,
            stdin_text=stdin_text,
            env=run_env,
            timeout=turn.timeout,
            activity_callback=_activity_callback_for_state(ctx.state, ctx.plan_dir),
            idle_timeout=_worker_stream_idle_timeout_seconds(),
            liveness_probe=_make_shannon_liveness_probe(
                ctx.tmux_session,
                turn.session_id,
                ctx.work_dir,
                claude_config_dir=ctx.claude_config_dir,
                home=ctx.env.get("HOME"),
            ),
            tmux_session=ctx.tmux_session,
        )
    except CliError as error:
        if error.code in {"worker_stall", "worker_timeout", "connection_error"}:
            error.extra["session_id"] = turn.session_id
        raise

    raw = (result.stdout or "") + (result.stderr or "")
    return TurnResult(
        raw=raw,
        returncode=result.returncode,
        duration_ms=result.duration_ms,
        landed_session_id=session_id_of(raw),
    )


# ---------------------------------------------------------------------------
# Prompt shaping
# ---------------------------------------------------------------------------


def _append_json_output_contract(prompt: str, *, step: str, schema_text: str) -> str:
    """Make Shannon's interactive Claude route emulate ``claude -p --json-schema``.

    Shannon forwards ``--json-schema`` to Claude, but because it starts an
    interactive Claude session rather than native print mode, Claude may still
    answer with prose. The compatibility layer therefore makes the structured
    output contract explicit in the user prompt.
    """
    extra_contract = ""
    if step == "execute":
        task_scope = _extract_bracketed_scope(
            prompt,
            r"Only produce `task_updates` for these tasks: \[([^\]]*)\]",
        )
        sense_scope = _extract_bracketed_scope(
            prompt,
            r"Only produce `sense_check_acknowledgments` for these sense checks: \[([^\]]*)\]",
        )
        if task_scope or sense_scope:
            extra_contract = (
                "\nEXECUTE BATCH OUTPUT SCOPE:\n"
                f"- `task_updates[].task_id` MUST be exactly these task IDs and no others: {task_scope or 'not specified'}.\n"
                f"- `sense_check_acknowledgments[].sense_check_id` MUST be exactly these sense check IDs and no others: {sense_scope or 'not specified'}.\n"
                "- Do not include completed dependency-context tasks in the final JSON.\n"
                "- Do not acknowledge sense checks outside the current batch.\n"
            )
    return (
        prompt.rstrip()
        + "\n\n"
        + "Output format:\n"
        + "- Your final answer must be exactly one valid JSON object and nothing else.\n"
        + "- Do not wrap the JSON in markdown fences. Do not include prose before or after it.\n"
        + "- The JSON object must conform to this schema. If a field is markdown, put the markdown as a JSON string value.\n"
        + schema_text
        + "\n"
        + extra_contract
    )


def _extract_bracketed_scope(prompt: str, pattern: str) -> str:
    match = re.search(pattern, prompt)
    if not match:
        return ""
    raw = match.group(1).strip()
    return raw or "none"


def _prompt_file_iteration(step: str, state: PlanState) -> int:
    current = int(state.get("iteration", 0) or 0)
    if step == "revise":
        return current + 1
    if step == "plan":
        return max(1, current)
    return current


def _write_prompt_file(run_dir: Path, step: str, prompt: str, *, iteration: int | None = None) -> Path:
    """Write the Shannon phase prompt to the per-run artifact directory.

    The prompt is written under *run_dir* (``.megaplan/runs/<plan>/<step>/shannon/``)
    so it stays scoped to the run and does not pollute the plan directory or cwd.
    """
    run_dir.mkdir(parents=True, exist_ok=True)
    if iteration is None:
        prompt_path = run_dir / f"{step}_shannon_prompt.txt"
    else:
        prompt_path = run_dir / f"{step}_v{iteration}_shannon_prompt.txt"
    prompt_path.write_text(prompt, encoding="utf-8")
    return prompt_path


def _running_as_root() -> bool:
    return hasattr(os, "geteuid") and os.geteuid() == 0


def _seed_nonroot_claude_home(home: Path) -> None:
    claude_dir = home / ".claude"
    claude_dir.mkdir(parents=True, exist_ok=True)
    state_path = home / ".claude.json"
    if not state_path.exists():
        state_path.write_text(
            json.dumps(
                {
                    "firstStartTime": "2026-01-01T00:00:00.000Z",
                    "hasCompletedOnboarding": True,
                    "lastOnboardingVersion": "2.1.49",
                    "hasAcknowledgedCostThreshold": True,
                    "migrationVersion": 13,
                    "opusProMigrationComplete": True,
                    "sonnet1m45MigrationComplete": True,
                    "seenNotifications": {},
                    "customApiKeyResponses": {"approved": [], "rejected": []},
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
    settings_path = claude_dir / "settings.json"
    if not settings_path.exists():
        settings_path.write_text(
            json.dumps(
                {
                    "skipDangerousModePermissionPrompt": True,
                    "env": {"MEGAPLAN_TRUSTED_CONTAINER": "1"},
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
    policy_source = Path("/root/.claude/policy-limits.json")
    policy_target = claude_dir / "policy-limits.json"
    if policy_source.exists() and not policy_target.exists():
        try:
            shutil.copy2(policy_source, policy_target)
        except OSError:
            pass


def _chmod_tree_for_nonroot(path: Path) -> None:
    try:
        subprocess.run(
            ["chmod", "-R", "a+rwX", str(path)],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except OSError:
        return


def _prepare_nonroot_shannon_runtime(
    work_dir: Path, env: dict[str, str], *, cfg: ShannonConfig
) -> tuple[list[str], dict[str, str]]:
    """Return a command prefix/env that lets Shannon launch interactive Claude.

    Claude refuses ``bypassPermissions`` when the process itself is root. In a
    trusted cloud container, Megaplan can stay root as the supervisor while the
    Shannon/Claude child runs as an unprivileged user. That preserves Shannon's
    interactive tmux behavior instead of falling back to ``claude -p``.
    """
    if not cfg.drop_root:
        return [], env

    user = os.getenv("MEGAPLAN_SHANNON_NONROOT_USER", "nobody")
    su_path = shutil.which("su")
    if not su_path:
        return [], env

    home = Path(os.getenv("MEGAPLAN_SHANNON_NONROOT_HOME", str(work_dir / ".megaplan" / "shannon-home")))
    home.mkdir(parents=True, exist_ok=True)
    _seed_nonroot_claude_home(home)

    try:
        os.chmod(home, 0o777)
        os.chmod(home / ".claude", 0o777)
        root_home = Path("/root")
        if root_home.exists():
            os.chmod(root_home, root_home.stat().st_mode | 0o011)
    except OSError:
        pass

    if cfg.chmod_workspace:
        _chmod_tree_for_nonroot(work_dir)

    child_env = dict(env)
    child_env["HOME"] = str(home)
    child_env.pop("TMUX", None)
    child_env.pop("TMUX_PANE", None)
    child_env["TMUX_TMPDIR"] = "/tmp"
    child_env.setdefault("MEGAPLAN_SHANNON_BOOTSTRAP_ENTER_COUNT", "4")
    child_env.setdefault("MEGAPLAN_SHANNON_BOOTSTRAP_ENTER_DELAY_MS", "1000")

    return [su_path, "-m", "-s", "/bin/bash", user, "-c"], child_env


def _shell_join_command(command: list[str], cwd: Path) -> str:
    return "cd " + shlex.quote(str(cwd)) + " && " + shlex.join(command)


# ---------------------------------------------------------------------------
# Shannon output parsing
# ---------------------------------------------------------------------------


def _extract_json_object(text: str) -> dict[str, Any] | None:
    """Best-effort recovery of a JSON object embedded in free-form text.

    Handles the common cases that bare ``json.loads`` rejects:

    * Claude responses wrapped in markdown code fences::

          ```json
          {"plan": "..."}
          ```

    * Prose preceding the JSON object (``Here is the plan: {...}``).
    * JSON followed by trailing prose (``{...}  Hope that helps!``).

    Returns the decoded dict on success, or ``None`` when no JSON object
    could be recovered. Non-object payloads (lists, scalars) also return
    ``None`` since callers expect a mapping.
    """

    if not isinstance(text, str):
        return None
    stripped = text.strip()
    if not stripped:
        return None
    # Already-valid JSON object.
    if stripped.startswith("{"):
        try:
            data = json.loads(stripped)
            if isinstance(data, dict):
                return data
        except json.JSONDecodeError:
            pass
    # Try raw_decode from each '{' in order to consume a leading object
    # even with trailing prose, and to skip past markdown fences or other
    # leading prose like "Producing the structured JSON output now: {...}".
    decoder = json.JSONDecoder()
    cursor = 0
    while True:
        idx = stripped.find("{", cursor)
        if idx < 0:
            break
        try:
            data, _end = decoder.raw_decode(stripped[idx:])
        except json.JSONDecodeError:
            cursor = idx + 1
            continue
        if isinstance(data, dict):
            return data
        cursor = idx + 1
    # Last-resort: trim to outermost braces.
    start = stripped.find("{")
    if start != -1:
        end = stripped.rfind("}")
        if end > start:
            try:
                data = json.loads(stripped[start : end + 1])
                if isinstance(data, dict):
                    return data
            except json.JSONDecodeError:
                return None
    return None


def _parse_shannon_ndjson_events(raw: str) -> list[Any] | None:
    """Parse Shannon ``--output-format=stream-json`` stdout into an event list.

    In ``stream-json`` mode Shannon emits one JSON object per line (NDJSON) as
    each event occurs — ``system/init``, per-turn ``assistant`` + ``result``,
    optional ``system/hook_*`` rows, and a trailing ``shannon_session``
    metadata row on cleanup — instead of buffering the whole turn into a single
    ``JSON.stringify([...])`` array (the ``--output-format=json`` shape). Each
    incremental line flushes to stdout, which lets the ``_impl.py`` idle-output
    watchdog reset ``last_output`` on real progress and gives Shannon genuine
    liveness for a long single turn.

    Returns the decoded list of events when *raw* is line-delimited JSON with at
    least one parseable object, otherwise ``None`` so the caller can fall back
    to the single-document (``--output-format=json``) parse path. The returned
    list is shaped exactly like the legacy buffered transcript array, so it is
    fed straight through the existing array-walking extraction below and yields
    an identical final structured-output payload for normal turns.
    """
    if not isinstance(raw, str):
        return None
    lines = [ln for ln in raw.splitlines() if ln.strip()]
    # A single JSON line that decodes to a list IS the legacy buffered array
    # (``--output-format=json``); leave it to the single-document path so its
    # behaviour is unchanged. NDJSON only ever has one JSON value per line.
    if len(lines) < 2:
        return None
    events: list[Any] = []
    saw_object = False
    for line in lines:
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            # Any non-JSON line means this is not clean NDJSON (e.g. a single
            # pretty-printed JSON document spread across lines, or interleaved
            # prose). Fall back to the single-document parser.
            return None
        if isinstance(value, dict):
            saw_object = True
        events.append(value)
    if not saw_object:
        return None
    return events


def _parse_shannon_output(raw: str) -> tuple[dict[str, Any], dict[str, Any]]:
    """Parse Shannon CLI output into ``(envelope, payload)``.

    Two on-the-wire shapes are supported:

    * ``--output-format=stream-json`` (the liveness path, current default): one
      JSON event per line (NDJSON). The events are collected, in order, into a
      list identical in shape to the legacy transcript array and then walked by
      the same reverse-scan logic below — so the trailing ``type=result`` event
      still wins and the extracted structured-output payload is identical to the
      buffered path for a normal turn.
    * ``--output-format=json`` (legacy buffered path): a single
      ``JSON.stringify([...])`` array of transcript messages, or a single error
      / structured-output object.

    We walk the array in reverse, preferring the trailing ``type=result`` event
    produced by ``@dexh/shannon`` and then falling back to assistant messages
    that carry ``structured_output`` or JSON text. If the top-level value is
    already a dict we hand it back directly (compatible with
    :func:`~megaplan.workers.parse_claude_envelope`'s expected input shape).
    """
    ndjson_events = _parse_shannon_ndjson_events(raw)
    if ndjson_events is not None:
        data: Any = ndjson_events
    else:
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise CliError(
                "parse_error",
                f"Shannon output was not valid JSON: {exc}",
                extra={"raw_output": raw},
            ) from exc

    # ── error envelope (single dict) ────────────────────────────────────
    if isinstance(data, dict):
        if data.get("is_error"):
            message = data.get("result") or data.get("message") or "Shannon returned an error"
            lower = str(message).lower()
            error_code: str = "worker_error"
            if any(
                pattern in lower
                for pattern in ("not logged in", "/login", "unauthorized", "authentication")
            ):
                error_code = "auth_error"
            raise CliError(
                error_code,
                f"Shannon step failed: {message}",
                extra={"raw_output": raw},
            )
        # structured_output / result at top level
        if "structured_output" in data and isinstance(data["structured_output"], dict):
            return data, data["structured_output"]
        if "result" in data:
            result_val = data["result"]
            if isinstance(result_val, str):
                if not result_val.strip():
                    raise CliError(
                        "parse_error",
                        "Shannon returned empty result (check structured_output field)",
                        extra={"raw_output": raw},
                    )
                try:
                    result_val = json.loads(result_val)
                except json.JSONDecodeError as exc:
                    extracted = _extract_json_object(result_val)
                    if extracted is None:
                        raise CliError(
                            "parse_error",
                            f"Shannon result payload was not valid JSON: {exc}",
                            extra={"raw_output": raw},
                        ) from exc
                    result_val = extracted
            if isinstance(result_val, dict):
                return data, result_val
        return data, data

    # ── JSON array of transcript messages ───────────────────────────────
    if isinstance(data, list):
        # Real Shannon JSON output ends with a result event carrying the final
        # text result plus session/cost/usage metadata.
        for msg in reversed(data):
            if not isinstance(msg, dict) or msg.get("type") != "result":
                continue
            result_val = msg.get("result")
            if isinstance(result_val, str):
                if not result_val.strip():
                    continue
                _text = result_val
                try:
                    result_val = json.loads(_text)
                except json.JSONDecodeError:
                    extracted = _extract_json_object(result_val)
                    if extracted is None:
                        continue
                    result_val = extracted
            if isinstance(result_val, dict):
                return msg, result_val

        # Walk in reverse to find the last assistant message with payload.
        for msg in reversed(data):
            if not isinstance(msg, dict):
                continue
            _type = msg.get("type") or msg.get("role", "")
            if _type not in ("assistant",):
                continue
            inner = msg.get("message", msg)
            if not isinstance(inner, dict):
                continue
            # structured_output (highest priority)
            if "structured_output" in inner and isinstance(inner["structured_output"], dict):
                return inner, inner["structured_output"]
            # result field
            if "result" in inner:
                result_val = inner["result"]
                if isinstance(result_val, str):
                    if not result_val.strip():
                        continue
                    try:
                        result_val = json.loads(result_val)
                    except json.JSONDecodeError:
                        extracted = _extract_json_object(result_val)
                        if extracted is None:
                            continue
                        result_val = extracted
                if isinstance(result_val, dict):
                    return inner, result_val
            # content blocks that might embed JSON
            content = inner.get("content")
            if isinstance(content, list):
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "text":
                        text = block.get("text", "")
                        try:
                            parsed = json.loads(text)
                            if isinstance(parsed, dict):
                                return inner, parsed
                        except json.JSONDecodeError:
                            extracted = _extract_json_object(text)
                            if isinstance(extracted, dict):
                                return inner, extracted
            elif isinstance(content, str):
                try:
                    parsed = json.loads(content)
                    if isinstance(parsed, dict):
                        return inner, parsed
                except json.JSONDecodeError:
                    extracted = _extract_json_object(content)
                    if isinstance(extracted, dict):
                        return inner, extracted

        # Fallback: return the last dict in the array
        if data and isinstance(data[-1], dict):
            last = data[-1]
            if "message" in last and isinstance(last["message"], dict):
                return last["message"], last["message"]
            return last, last

    raise CliError(
        "parse_error",
        f"Shannon output was not a JSON array or object: {type(data).__name__}",
        extra={"raw_output": raw},
    )


def _extract_actual_model_from_envelope(envelope: dict[str, Any]) -> str | None:
    model_actual = envelope.get("model")
    message = envelope.get("message")
    if not model_actual and isinstance(message, dict):
        model_actual = message.get("model")
    return str(model_actual) if model_actual else None


def _apply_file_fallback(
    step: str,
    payload: dict[str, Any],
    plan_dir: Path,
    *,
    output_path: Path | None = None,
) -> dict[str, Any]:
    """On-disk template fallback for steps that write their answer to a file.

    Claude sometimes emits a chatty summary instead of literal JSON in its final
    message; for ``critique``/``review`` the on-disk file is the source of
    truth. But prefer a transcript payload that carries populated findings over
    an unpopulated on-disk template, so work returned in the final message is
    not silently discarded.
    """
    file_fallback = {
        "critique": ("critique_output.json", "checks"),
        "review": ("review_output.json", "checks"),
    }
    if step not in file_fallback:
        return payload
    fallback_name, sentinel_key = file_fallback[step]
    fallback_path = Path(output_path) if output_path is not None else plan_dir / fallback_name
    if not fallback_path.exists():
        return payload
    try:
        file_payload = read_json(fallback_path)
    except Exception:
        return payload
    if not (isinstance(file_payload, dict) and sentinel_key in file_payload):
        return payload

    def _has_populated_findings(p: Any) -> bool:
        if not isinstance(p, dict):
            return False
        checks = p.get(sentinel_key)
        if not isinstance(checks, list) or not checks:
            return False
        for check in checks:
            if not isinstance(check, dict):
                continue
            findings = check.get("findings")
            if isinstance(findings, list) and findings:
                return True
        return False

    if _has_populated_findings(file_payload) or not _has_populated_findings(payload):
        return file_payload
    return payload


_EXECUTE_ENVELOPE_REPAIR_PROMPT = (
    "Your previous turn was cut off before you emitted the required structured "
    "result. Do NOT redo any work — the edits and commands you already ran in "
    "this session stand. Reply with ONLY one valid JSON object (no prose, no "
    "markdown fences) summarizing what you just did, conforming to the megaplan "
    "execute schema. It MUST include the keys: output, files_changed, "
    "commands_run, deviations, task_updates, and sense_check_acknowledgments. "
    "Keep prose fields concise so the whole object fits well within the output "
    "budget."
)


def _claude_transcript_paths(
    session_id: str | None,
    work_dir: Path,
    *,
    claude_config_dir: str | None = None,
    home: str | None = None,
) -> list[Path]:
    """Best-effort list of candidate Claude transcript .jsonl files for a turn.

    Shannon drives a real Claude Code session and Claude appends to a
    per-session transcript under ``~/.claude/projects/<slug>/<session>.jsonl``.
    That file's mtime advances as the turn produces content blocks (even though
    shannon emits nothing on stdout under ``--output-format=json``), so a moving
    mtime is a reliable "the turn is still doing work" signal. The project slug
    encoding is Claude-internal, so we glob defensively by session id and fall
    back to a directory-wide scan keyed on the work_dir slug. Returns ``[]`` when
    nothing is found (the probe then leans on the tmux-pane signal instead).

    When *claude_config_dir* is set (``CLAUDE_CONFIG_DIR`` env-var), the
    projects root is ``<claude_config_dir>/projects`` instead of
    ``~/.claude/projects``, keeping per-run transcript globs scoped to the
    artifact dir.
    """
    paths: list[Path] = []
    try:
        if claude_config_dir:
            projects_root = Path(claude_config_dir) / "projects"
        elif home:
            projects_root = Path(home) / ".claude" / "projects"
        else:
            projects_root = Path.home() / ".claude" / "projects"
    except Exception:
        return paths
    if not projects_root.is_dir():
        return paths
    try:
        if session_id:
            paths.extend(projects_root.glob(f"*/{session_id}.jsonl"))
        if not paths:
            # Fall back to the work_dir-derived project slug. This MUST match
            # shannon's ``projectKeyForCwd`` byte-for-byte, otherwise we glob a
            # directory that does not exist, find no transcript, and the probe
            # degenerates to its "no signal" branch (returns True forever) — the
            # exact bug that let a wedged turn keep its idle clock reset past the
            # 300s bound. shannon (index.ts ``projectKeyForCwd``) computes the
            # Claude project slug as ``resolve(cwd).replace(/[^a-zA-Z0-9_-]/g,
            # '-')`` — it replaces EVERY non-alphanumeric character (``/`` AND
            # ``.``, spaces, etc.) with ``-``. The previous code replaced only
            # ``/``, so a worktree path like ``.../Documents/.megaplan-worktrees/
            # ...`` produced ``...Documents-.megaplan-worktrees...`` while shannon
            # (and Claude itself) wrote to ``...Documents--megaplan-worktrees...``.
            slug = re.sub(r"[^a-zA-Z0-9_-]", "-", str(work_dir.resolve()))
            candidate_dir = projects_root / slug
            if candidate_dir.is_dir():
                paths.extend(candidate_dir.glob("*.jsonl"))
    except Exception:
        return paths
    return paths


def _make_shannon_liveness_probe(
    tmux_session: TmuxSession,
    session_id: str | None,
    work_dir: Path,
    *,
    claude_config_dir: str | None = None,
    home: str | None = None,
):
    """Build a liveness probe for the buffered shannon worker.

    The shannon worker runs Claude under ``--output-format=json``: the CLI
    buffers its ENTIRE response and writes nothing to the host stdout/stderr
    pipe until the turn completes. The ``run_command`` idle-output watchdog
    therefore sees zero bytes for the whole turn and, on a long-but-healthy
    turn, would kill it at the idle bound with a misleading ``worker_stall``.

    This probe gives ``run_command`` a REAL liveness signal so it only kills a
    worker that is genuinely stuck. It reports progress (``True``) ONLY when:

    * a candidate Claude transcript ``.jsonl`` mtime has advanced — the turn is
      flushing completed content blocks / tool events to disk. This is the only
      TRUSTWORTHY signal of genuine work.

    Crucially, tmux pane-content churn is NOT treated as progress on its own.
    A wedged Claude (HTTP/SSE stream stalled — sockets ESTABLISHED, 0% CPU, no
    tokens) still repaints its interactive pane (cursor redraws, spinner
    animations, status-line refreshes) while writing NOTHING to its transcript.
    Counting that pane churn as "progress" reset the idle clock forever, so a
    wedged turn never tripped the inter-event ``stalled_stream`` bound and burned
    the full window before retrying — and re-wedging. Requiring transcript growth
    makes a wedged turn correctly read as idle so the bound bites within its
    intended window.

    It reports ``False`` (no progress) when the session is alive but the
    transcript mtime is static across the idle window — i.e. a genuinely hung
    turn — or when the tmux session has vanished entirely. Every tmux/FS call
    degrades gracefully; a probe that cannot read ANY signal at all (no
    transcript found AND pane unreadable) returns ``True`` so the conservative
    wall-clock ``timeout`` stays the sole bound rather than risking a false kill.
    """
    # Captured-snapshot state across probe calls.
    last_pane = [""]
    last_mtime = [0.0]
    primed = [False]

    def _capture_pane() -> str | None:
        try:
            result = subprocess.run(
                ["tmux", "capture-pane", "-p", "-t", tmux_session.name],
                check=False,
                capture_output=True,
                text=True,
            )
        except FileNotFoundError:
            return None
        if result.returncode != 0:
            return None
        return result.stdout

    def _max_transcript_mtime() -> float:
        newest = 0.0
        for path in _claude_transcript_paths(
            session_id, work_dir, claude_config_dir=claude_config_dir, home=home
        ):
            try:
                m = path.stat().st_mtime
            except OSError:
                continue
            if m > newest:
                newest = m
        return newest

    def _probe() -> bool:
        # If the tmux session is gone, the worker can no longer be progressing
        # in a pane we can observe — defer to the stdout/wall-clock bounds (do
        # NOT claim progress).
        try:
            session_alive = tmux_session.exists()
        except Exception:
            session_alive = True  # cannot tell — do not kill on this alone

        pane = _capture_pane()
        mtime = _max_transcript_mtime()

        if not primed[0]:
            # First probe establishes the baseline; treat as progress so the
            # very first idle expiry never kills before we have a comparison.
            last_pane[0] = pane or ""
            last_mtime[0] = mtime
            primed[0] = True
            return True

        # Transcript mtime advancing is the ONLY trusted progress signal: it
        # means completed content blocks / tool events are being flushed to
        # disk. Pane churn is deliberately ignored as a standalone signal — a
        # wedged Claude repaints its pane without writing any transcript, and
        # counting that as progress reset the idle clock forever (the root-cause
        # bug). We still refresh the pane baseline for diagnostics/parity.
        progressing = mtime > last_mtime[0]

        # Refresh baselines for the next comparison.
        if pane is not None:
            last_pane[0] = pane
        if mtime > last_mtime[0]:
            last_mtime[0] = mtime

        if progressing:
            return True

        # No transcript movement. If we have NO observable transcript signal at
        # all (no transcript file found yet) and the session still exists, stay
        # conservative (return True) and let the wall-clock cap govern — we
        # cannot distinguish a hang from a turn that simply has not opened its
        # transcript. Only declare "not progressing" when we genuinely observed
        # a static-but-alive transcript.
        have_signal = mtime > 0.0
        if not have_signal and session_alive:
            return True
        return False

    return _probe


# ---------------------------------------------------------------------------
# Public worker entry-point
# ---------------------------------------------------------------------------


def _tmux_slug(text: str) -> str:
    """Sanitize *text* to tmux-safe characters (no ``.``, ``:``, whitespace)."""
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug or "plan"


def _shannon_run_dir(plan_dir: Path, *, plan_id: str, step: str) -> Path:
    """Per-run artifact directory: ``.megaplan/runs/<plan_id>/<step>/shannon/``.

    All Shannon run artifacts (prompt file, Claude config, transcripts) are
    scoped under this directory so they do not pollute cwd or ~/.claude. The
    path is derived from (plan_id, step) — the same inputs the orchestrator
    already has — and threaded through :class:`TurnContext` so downstream
    helpers can resolve artifact paths without recomputing.
    """
    return plan_dir / ".megaplan" / "runs" / plan_id / step / "shannon"


def _write_tmux_session_ledger(
    run_dir: Path,
    *,
    plan_id: str,
    step: str,
    iteration: int,
    tmux_session_name: str,
) -> Path:
    """Record the opaque tmux session's operator mapping under *run_dir*."""
    run_dir.mkdir(parents=True, exist_ok=True)
    ledger_path = run_dir / "tmux_session.json"
    payload = {
        "version": 1,
        "plan_id": plan_id,
        "step": step,
        "iteration": iteration,
        "tmux_session_name": tmux_session_name,
        "tmux_session_name_derivation": "sha256(plan_id|step|iteration)[:12]",
        "run_dir": str(run_dir),
    }
    fd, tmp = tempfile.mkstemp(dir=str(run_dir), prefix=".tmux_session.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as fh:
            json.dump(payload, fh, indent=2, sort_keys=True)
            fh.write("\n")
        os.replace(tmp, ledger_path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
    return ledger_path


def _ensure_workspace_trusted(
    work_dir: Path, *, claude_config_dir: str | None = None, home: str | None = None
) -> None:
    """Pre-accept Claude Code's folder-trust dialog for *work_dir* before launch.

    Shannon launches the real ``claude`` CLI in an *interactive* tmux session,
    which prompts "Is this a project you trust?" for any directory that has not
    already been accepted. That dialog is NOT suppressed by
    ``--dangerously-skip-permissions`` / ``--permission-mode bypassPermissions``;
    in a fresh dir (a ``/tmp`` worktree, a pinned-engine clone, a cloud checkout)
    it blocks on stdin and the readiness probe times out, stalling the phase.

    There is no global "trust all folders" switch in Claude Code (verified: only
    the per-directory ``~/.claude.json`` → ``projects[path]`` acceptance persists).
    So we write that acceptance ourselves, for every folder Shannon runs in —
    effectively auto-trusting everything the app touches.

    Trust is keyed on the RESOLVED real path: ``claude`` resolves the workspace
    via realpath, so on macOS ``/tmp/x`` is checked as ``/private/tmp/x``. We
    write both the given and resolved paths to be safe. Best-effort: any failure
    is logged and ignored (a missing entry only re-surfaces the dialog).

    When *claude_config_dir* is set (``CLAUDE_CONFIG_DIR`` env-var), the trust
    file is ``<claude_config_dir>/.claude.json`` instead of ``~/.claude.json``.
    This keeps per-run trust entries scoped to the run artifact dir.

    When native config mode is selected and the worker drops root, *home* must
    be the effective child ``HOME`` so pre-trust writes land where Claude will
    actually read them.
    """
    try:
        if claude_config_dir:
            cfg_path = Path(claude_config_dir) / ".claude.json"
        elif home:
            cfg_path = Path(home) / ".claude.json"
        else:
            cfg_path = Path(os.path.expanduser("~/.claude.json"))
        candidates = {str(work_dir)}
        try:
            candidates.add(str(work_dir.resolve()))
        except OSError:
            pass
        data: dict[str, Any] = {}
        if cfg_path.exists():
            try:
                data = json.loads(cfg_path.read_text())
            except (ValueError, OSError):
                data = {}
        if not isinstance(data, dict):
            return
        projects = data.setdefault("projects", {})
        if not isinstance(projects, dict):
            return
        changed = False
        # Global first-run onboarding (theme picker) blocks the composer just
        # like the trust dialog does. An isolated CLAUDE_CONFIG_DIR starts
        # empty, so claude treats it as a fresh install and the readiness
        # probe times out staring at the theme wizard. Pre-complete it.
        if not data.get("hasCompletedOnboarding"):
            data["hasCompletedOnboarding"] = True
            data.setdefault("theme", "dark")
            changed = True
        # Fresh isolated Claude config dirs also show the one-time
        # bypass-permissions responsibility dialog before Shannon can paste the
        # prompt. Pre-accept it for unattended Megaplan workers; the caller has
        # already opted into bypass mode by selecting Shannon's write-capable
        # execution path.
        if not data.get("bypassPermissionsModeAccepted"):
            data["bypassPermissionsModeAccepted"] = True
            changed = True
        for path in candidates:
            entry = projects.get(path)
            if not isinstance(entry, dict):
                entry = {}
            if not (
                entry.get("hasTrustDialogAccepted")
                and entry.get("hasCompletedProjectOnboarding")
            ):
                entry["hasTrustDialogAccepted"] = True
                entry["hasCompletedProjectOnboarding"] = True
                entry.setdefault("projectOnboardingSeenCount", 1)
                projects[path] = entry
                changed = True
        if not changed:
            return  # already trusted — avoid clobbering a concurrent claude write
        fd, tmp = tempfile.mkstemp(dir=str(cfg_path.parent), prefix=".claude.json.")
        try:
            with os.fdopen(fd, "w") as fh:
                json.dump(data, fh, indent=2)
            os.replace(tmp, cfg_path)
        except BaseException:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise
    except Exception as exc:  # best-effort: never let trust-prep crash the worker
        print(
            f"[megaplan] could not pre-trust workspace {work_dir} for Shannon: {exc}",
            file=sys.stderr,
            flush=True,
        )


def _resolve_pinned_claude(cfg: ShannonConfig) -> str | None:
    """Resolve the claude binary to pin for this run, or None to leave PATH alone.

    Precedence: the explicit ``MEGAPLAN_SHANNON_CLAUDE_BIN`` override, else (when
    ``pin_claude`` — the default) the *real* absolute path of the ``claude``
    currently on PATH. We resolve the symlink to its target so a mid-run symlink
    flip — e.g. the Claude CLI auto-updater repointing ``~/.local/bin/claude`` to
    a newer, headless-broken build — cannot switch the version under a running
    step. Returns None when pinning is disabled or no ``claude`` is found
    (preserves the legacy PATH-resolution behavior).
    """
    if cfg.claude_bin:
        resolved = os.path.realpath(os.path.expanduser(cfg.claude_bin))
        if not os.path.isfile(resolved):
            raise CliError(
                "worker_error",
                f"MEGAPLAN_SHANNON_CLAUDE_BIN={cfg.claude_bin!r} is not a file "
                f"(resolved {resolved}).",
            )
        return resolved
    if not cfg.pin_claude:
        return None
    found = shutil.which("claude")
    if not found:
        return None
    return os.path.realpath(found)


def _install_claude_pin(
    env: dict[str, str], run_dir: Path, pinned: str
) -> dict[str, str]:
    """Prepend a per-run shim dir to ``PATH`` so the vendored launcher's
    ``which claude`` resolves to *pinned* (an absolute binary path), immune to
    any ``~/.local/bin/claude`` symlink churn during the run. Returns a new env
    dict; does not mutate the input.
    """
    shim_dir = run_dir / "claude_pin"
    shim_dir.mkdir(parents=True, exist_ok=True)
    shim = shim_dir / "claude"
    try:
        if shim.exists() or shim.is_symlink():
            shim.unlink()
        os.symlink(pinned, shim)
    except OSError:
        # Symlink not permitted on this mount — fall back to an exec wrapper.
        shim.write_text(
            f'#!/bin/bash\nexec {shlex.quote(pinned)} "$@"\n', encoding="utf-8"
        )
        shim.chmod(0o755)
    new_env = dict(env)
    new_env["PATH"] = f"{shim_dir}{os.pathsep}{new_env.get('PATH', '')}"
    return new_env


def run_shannon_step(
    step: str,
    state: PlanState,
    plan_dir: Path,
    *,
    root: Path,
    fresh: bool,
    prompt_override: str | None = None,
    prompt_kwargs: dict[str, Any] | None = None,
    effort: str | None = None,
    session_agent: str = "shannon",
    model: str | None = None,
    read_only: bool = False,
    output_path: Path | None = None,
) -> WorkerResult:
    """Run a megaplan phase via Shannon (Claude in an interactive tmux session).

    Reads top-to-bottom: load config → seed rng → build prompt + ctx → plan
    the session → run each pre-turn → run the main turn → parse / repair /
    build :class:`WorkerResult`. Every turn — readiness handshake, ``/compact``
    or ``/clear`` context op, the main work turn, and an execute-envelope
    repair turn — goes through the single :func:`run_turn` executor against
    the per-run :class:`TurnContext`.

    Parameters match :func:`~megaplan.workers.run_claude_step` so the
    ``run_step_with_worker`` dispatch can call them interchangeably.
    """
    # ── (a) mock worker shortcut ────────────────────────────────────────
    if os.getenv(MOCK_ENV_VAR) == "1":
        _check_mock_safe()
        return mock_worker_output(
            step, state, plan_dir,
            prompt_override=prompt_override,
            prompt_kwargs=prompt_kwargs,
        )
    fresh = fresh or step != "execute"

    # ── (b) config + sentinel + workspace ───────────────────────────────
    cfg = ShannonConfig.load(state.get("config", {}), state=state)
    _assert_vendored_shannon_sentinel()
    work_dir = resolve_work_dir(state)

    # Per-run artifact directory so prompt files, Claude config, and
    # transcripts stay scoped to this invocation and don't pollute cwd or
    # ~/.claude. Left on disk after the step for post-hoc inspection.
    plan_id = str(state.get("name", ""))
    run_dir = _shannon_run_dir(plan_dir, plan_id=plan_id, step=step)
    run_dir.mkdir(parents=True, exist_ok=True)
    empty_mcp_config_path = run_dir / "empty_mcp_config.json"
    empty_mcp_config_path.write_text('{"mcpServers":{}}\n', encoding="utf-8")

    claude_config_dir = (
        run_dir / "claude_config" if cfg.claude_config_mode == "isolated" else None
    )
    if claude_config_dir is not None:
        claude_config_dir.mkdir(parents=True, exist_ok=True)
    _ensure_workspace_trusted(
        work_dir,
        claude_config_dir=str(claude_config_dir) if claude_config_dir is not None else None,
    )

    # Tmux session name is a truncated sha256 of (plan_id, step, iteration)
    # so it's recoverable for reaping but carries no lexical advertisement
    # like "megaplan-" or "step". Still passed via SHANNON_TMUX_SESSION_NAME
    # (honored by the vendored fork's P14 patch).
    iteration = int(state.get("iteration", 0) or 0)
    session_name = hashlib.sha256(
        f"{plan_id}|{step}|{iteration}".encode("utf-8")
    ).hexdigest()[:12]
    tmux_session = TmuxSession(session_name)
    _write_tmux_session_ledger(
        run_dir,
        plan_id=plan_id,
        step=step,
        iteration=iteration,
        tmux_session_name=session_name,
    )

    # Reap any residual same-(plan,step) tmux pane from a prior attempt; if
    # the session survives teardown it is genuinely unkillable and must fail
    # the step. Wrap in CliError so the execute loop's CliError-only handlers
    # produce a clean failed-state write instead of a raw traceback.
    try:
        pids = pane_pids(session_name)
        tmux_session.teardown()
        if tmux_session.exists():
            raise OrphanDetectedError(
                sessions=[session_name],
                pids=pids,
                remediation=f"tmux kill-session -t {session_name}",
            )
    except OrphanDetectedError as e:
        raise CliError(
            "worker_error",
            f"Orphan tmux session survived teardown: {session_name}. "
            f"Manual remediation: {e.remediation}",
            extra={"sessions": e.sessions, "pids": e.pids},
        ) from e

    session_key = session_key_for(step, session_agent, model=model)
    session = state["sessions"].get(session_key, {})
    stored_session_id: str | None = session.get("id")
    # The id currently persisted in state["sessions"]. A /clear op rotates the
    # live id mid-run, so the stall/timeout handler must clear the entry whose
    # id is EITHER the original (persisted) id OR the rotated one.
    persisted_session_id = stored_session_id

    # ── (c) build the real phase prompt (file + launcher pointer) ───────
    projection_capabilities = shannon_projection_capabilities(read_only=read_only)
    base_prompt = (
        prompt_override
        if prompt_override is not None
        else create_claude_prompt(
            step,
            state,
            plan_dir,
            root=root,
            projection_capabilities=projection_capabilities,
            **(prompt_kwargs or {}),
        )
    )
    if output_path is not None:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
    plan_mode = state["config"].get("mode", "code")
    schema_name = (
        get_execution_schema_key(plan_mode, form=creative_form_id(state))
        if step == "execute"
        else STEP_SCHEMA_FILENAMES[step]
    )
    schema_text = json.dumps(read_json(schemas_root(root) / schema_name))
    prompt = _append_json_output_contract(base_prompt, step=step, schema_text=schema_text)
    try:
        check_prompt_size(prompt, phase=step)
    except CliError as error:
        if step != "review" or error.code != "prompt_oversized":
            raise
        base_prompt = compact_review_prompt(
            state,
            plan_dir,
            root,
            prompt_size_error=error.extra,
            pre_check_flags=(prompt_kwargs or {}).get("pre_check_flags"),
            projection_capabilities=projection_capabilities,
        )
        prompt = _append_json_output_contract(base_prompt, step=step, schema_text=schema_text)
        check_prompt_size(prompt, phase=step)

    prompt_iteration = _prompt_file_iteration(step, state) if fresh and step != "execute" else None
    prompt_path = _write_prompt_file(run_dir, step, prompt, iteration=prompt_iteration)
    launcher_prompt = (
        "Read the full megaplan phase prompt from this file and follow it exactly: "
        f"{prompt_path}. Your final response must satisfy the structured output "
        "contract in that file. Do not summarize the file; execute its instructions."
    )

    # ── (d) Shannon argv skeleton (everything except per-turn -p/--resume) ─
    # Real megaplan prompts can exceed argv limits, so the main turn rides a
    # short launcher prompt that points Claude at the on-disk prompt file.
    # stream-json gives incremental NDJSON liveness for the parent watchdog.
    # The vendored fork's absolute path is required because the drop-root path
    # may shell-join the argv under ``su -c``.
    base_flags: list[str] = ["bun", str(VENDORED_SHANNON_PATH)]
    # Unattended Megaplan phases must not depend on operator/account MCP health.
    # Claude Code can surface unauthenticated or broken MCPs as startup banners,
    # which makes Shannon's interactive readiness gate environment-sensitive.
    base_flags.extend(["--strict-mcp-config", "--mcp-config", str(empty_mcp_config_path)])
    if model is not None:
        base_flags.extend(["--model", model])
    base_flags.append("--output-format=stream-json")
    if cfg.drop_root:
        # Claude's interactive non-print mode only honors ANTHROPIC_API_KEY
        # reliably in bare mode for the cloud-root → non-root handoff. Still
        # interactive tmux, not ``claude -p``.
        base_flags.append("--bare")
    if effort is not None:
        base_flags.extend(["--effort", effort])
    if read_only:
        base_flags.extend(
            [
                "--allowedTools",
                *_SHANNON_READ_ONLY_ALLOWED_TOOLS,
                "--disallowedTools",
                *_SHANNON_READ_ONLY_DISALLOWED_TOOLS,
            ]
        )
    else:
        base_flags.extend(
            [
                "--permission-mode",
                "bypassPermissions",
                "--dangerously-skip-permissions",
                "--allow-dangerously-skip-permissions",
            ]
        )

    # ── (e) env, ONCE: timeouts, output ceiling, native prompt handoff, nonroot prefix ─
    _is_root = hasattr(os, "geteuid") and os.geteuid() == 0
    paste_mode = cfg.paste_first_turn
    env = _external_worker_env(turn_id=f'plan_worker_{state["name"]}')
    env["SHANNON_TMUX_SESSION_NAME"] = session_name
    # Route Claude's ~/.claude/ writes to the per-run artifact dir so
    # /clear session-file churn does not pile up in the user's home dir.
    # The vendored fork's P15 patch strips MEGAPLAN_*/SHANNON_* from the
    # grandchild env but CLAUDE_CONFIG_DIR passes through to Claude.
    if claude_config_dir is not None:
        env["CLAUDE_CONFIG_DIR"] = str(claude_config_dir)
    else:
        env.pop("CLAUDE_CONFIG_DIR", None)
    if paste_mode:
        # Keep the historical env flag for older vendored launchers and for
        # operator diagnostics. The current vendored launcher always starts
        # native interactive Claude in tmux, waits for a ready prompt, then
        # sends every turn through tmux paste-buffer with a small random delay.
        env["MEGAPLAN_SHANNON_PASTE_FIRST_TURN"] = "1"
        # Startup race: Claude's welcome banner can paint "❯" before the input
        # box is genuinely live. Nudge delayed Enters past the banner; the
        # TypeScript wrapper still waits for prompt readiness before sending.
        if not cfg.drop_root:
            env.setdefault("MEGAPLAN_SHANNON_BOOTSTRAP_ENTER_COUNT", "2")
            env.setdefault("MEGAPLAN_SHANNON_BOOTSTRAP_ENTER_DELAY_MS", "2500")
    if not _is_root:
        # Setting to empty (not popping) defeats Bun's dotenv auto-load in
        # shannon's launcher: Bun skips vars already set, so an empty value
        # blocks .env injection. Claude Code treats empty as no key and falls
        # back to OAuth. (megaplan ticket 01KRXNZZGRV17PHZRJ2Q56SPS3.)
        env["ANTHROPIC_API_KEY"] = ""
    # Megaplan owns phase timeouts; keep Shannon's internal watchdog above the
    # worker budget so the parent decides when to stop waiting. The default
    # 180s is too short for normal critique/finalize/execute phases.
    env.setdefault("SHANNON_TURN_TIMEOUT_MS", "7200000")
    # Raise the Claude CLI output ceiling above the inherited ~64k default so
    # opus-class models aren't cut off mid-run before emitting the envelope.
    env.setdefault("CLAUDE_CODE_MAX_OUTPUT_TOKENS", str(cfg.max_output_tokens))
    # Raise Claude Code's per-command Bash timeout above its built-in 120s cap.
    bash_timeout_ms = str(_shannon_bash_timeout_ms())
    env.setdefault("BASH_DEFAULT_TIMEOUT_MS", bash_timeout_ms)
    env.setdefault("BASH_MAX_TIMEOUT_MS", bash_timeout_ms)
    # Compute the nonroot shannon prefix + child env EXACTLY ONCE per run and
    # thread the result through ctx — :func:`run_turn` MUST NOT recompute it.
    shannon_prefix, env = _prepare_nonroot_shannon_runtime(work_dir, env, cfg=cfg)
    # Pin the claude binary for this run (default on): resolve it once to an
    # absolute path and put it first on the child PATH so the vendored launcher's
    # `which claude` cannot be hijacked mid-run by the Claude CLI auto-updater
    # repointing the ~/.local/bin/claude symlink to a headless-broken build.
    pinned_claude = _resolve_pinned_claude(cfg)
    if pinned_claude:
        env = _install_claude_pin(env, run_dir, pinned_claude)
    _ensure_workspace_trusted(
        work_dir,
        claude_config_dir=str(claude_config_dir) if claude_config_dir is not None else None,
        home=env.get("HOME"),
    )

    ctx = TurnContext(
        base_flags=base_flags,
        shannon_prefix=shannon_prefix,
        env=env,
        work_dir=work_dir,
        plan_dir=plan_dir,
        run_dir=run_dir,
        claude_config_dir=str(claude_config_dir) if claude_config_dir is not None else None,
        tmux_session=tmux_session,
        state=state,
    )

    # ── (f) plan the session ────────────────────────────────────────────
    # plan_session owns every roll (strategy, handshake, context-op delays,
    # new-session id) under a seeded RNG so a run is replayable for forensics.
    session_nonce = _shannon_run_nonce(state, step)
    session_rng = _seeded_rng_for_run(state, step, nonce=session_nonce)
    plan = plan_session(
        step,
        stored_id=stored_session_id,
        fresh=fresh,
        cfg=cfg,
        rng=session_rng,
    )
    session_id = plan.main.session_id
    main_turn = dataclasses.replace(
        plan.main,
        body=(prompt if paste_mode else launcher_prompt),
        delivery=("stdin" if paste_mode else "argv"),
    )
    print(
        f"[megaplan] shannon session strategy for {step}: {plan.kind} "
        f"(session {session_id}).",
        file=sys.stderr,
        flush=True,
    )

    # ── (g) pre-turns: handshake (fails the phase) and/or context-op
    # (best-effort; on failure we shed context the safe way — fresh session).
    for pre_turn in plan.pre_turns:
        if pre_turn.expect == "non_empty":
            # Readiness handshake: only run when the deployment gate is open
            # for this session_agent. Failure (CliError, non-zero exit, or
            # empty output) fails the phase.
            if not cfg.readiness_probe_enabled(session_agent):
                # plan_session optimistically set main.resume=True (because a
                # successful handshake would have created the session). When
                # the gate skips the handshake the session is not created, so
                # the main turn must spawn it via --session-id instead.
                main_turn = dataclasses.replace(main_turn, resume=False)
                continue
            try:
                pre_result = run_turn(pre_turn, ctx)
            except CliError as error:
                if error.code == "worker_timeout":
                    error.extra["session_id"] = pre_turn.session_id
                raise
            if pre_result.returncode != 0:
                if _raw_contains_success_result(pre_result.raw):
                    print(
                        "[megaplan] WARNING: Shannon readiness probe returned "
                        f"exit code {pre_result.returncode} after a successful "
                        "result envelope; accepting readiness output.",
                        file=sys.stderr,
                        flush=True,
                    )
                    continue
                raise CliError(
                    "worker_error",
                    f"Shannon readiness probe failed with exit code {pre_result.returncode}",
                    extra={"raw_output": pre_result.raw, "session_id": pre_turn.session_id},
                )
            if not pre_result.raw.strip():
                raise CliError(
                    "worker_error",
                    "Shannon readiness probe returned no output",
                    extra={"raw_output": "", "session_id": pre_turn.session_id},
                )
        else:
            # Context op (/compact or /clear). Best-effort: on stall/timeout/
            # non-zero exit, never plain-resume the un-shed session — shed it
            # the safe way with a fresh new session id.
            print(
                f"[megaplan] shannon session strategy: injecting {pre_turn.body} "
                f"into resumed session {pre_turn.session_id} before the main turn.",
                file=sys.stderr,
                flush=True,
            )
            try:
                pre_result = run_turn(pre_turn, ctx)
            except CliError as error:
                print(
                    f"[megaplan] shannon {pre_turn.body} turn did not complete "
                    f"cleanly ({error.code}); starting a fresh session instead.",
                    file=sys.stderr,
                    flush=True,
                )
                session_id = str(uuid.uuid4())
                main_turn = dataclasses.replace(
                    main_turn, session_id=session_id, resume=False
                )
                continue
            if pre_result.returncode != 0:
                print(
                    f"[megaplan] shannon {pre_turn.body} did not complete; "
                    f"starting a fresh session instead of resuming stale context.",
                    file=sys.stderr,
                    flush=True,
                )
                session_id = str(uuid.uuid4())
                main_turn = dataclasses.replace(
                    main_turn, session_id=session_id, resume=False
                )
                continue
            # ``landed_session_id`` is None when the op's output isn't parseable
            # JSON — treat that as "no rotation, same id" (compact's normal case).
            # /clear emits an NDJSON ``result`` row carrying the rotated id, so a
            # successful clear's landed id differs from the resumed id.
            landed = pre_result.landed_session_id or pre_turn.session_id
            if landed != pre_turn.session_id:
                # ``/clear`` rotates the session id; resume the new one.
                print(
                    f"[megaplan] shannon {pre_turn.body} rotated session "
                    f"{pre_turn.session_id} -> {landed}; work turn will resume "
                    "the new session.",
                    file=sys.stderr,
                    flush=True,
                )
                session_id = landed
                main_turn = dataclasses.replace(main_turn, session_id=landed)

    # ── (h) main work turn ──────────────────────────────────────────────
    try:
        main_result = run_turn(main_turn, ctx)
    except CliError as error:
        # On stall/timeout, drop any persisted session id that matches the
        # leased one (original OR rotated) so the next attempt spawns fresh
        # instead of racing an orphan on --resume <sid>.
        if error.code in ("worker_timeout", "worker_stall"):
            try:
                sessions = state.get("sessions")
                if isinstance(sessions, dict):
                    entry = sessions.get(session_key)
                    entry_id = entry.get("id") if isinstance(entry, dict) else None
                    if entry_id is not None and entry_id in {
                        main_turn.session_id, persisted_session_id,
                    }:
                        sessions.pop(session_key, None)
                        print(
                            f"[megaplan] Cleared persisted shannon session "
                            f"{session_key}={entry_id} after {error.code}; "
                            "next attempt will start a fresh session.",
                            file=sys.stderr,
                            flush=True,
                        )
            except Exception:
                # Best-effort cleanup; never mask the original CliError.
                pass
        raise

    raw = main_result.raw

    # A dead tmux server during the turn (the vendored launcher surfaces
    # ``tmux capture-pane ... no server running``) means the Claude session
    # crashed before emitting a result — a transient infra stall, not a bad
    # result. Without this guard the tmux-error text falls through to
    # ``_parse_shannon_output``, which finds no result envelope and the only
    # surviving line is Claude's ``system/init`` message — so the crash is
    # misparsed and surfaces as a non-retryable ``internal_error`` that loops.
    # Classify it as a retryable ``worker_stall`` instead: shed the persisted
    # session id (matching the run_turn stall handler above) and re-raise so the
    # next attempt spawns a fresh session.
    if not _raw_contains_success_result(raw) and _raw_indicates_tmux_died(raw):
        try:
            sessions = state.get("sessions")
            if isinstance(sessions, dict):
                entry = sessions.get(session_key)
                entry_id = entry.get("id") if isinstance(entry, dict) else None
                if entry_id is not None and entry_id in {
                    main_turn.session_id, persisted_session_id,
                }:
                    sessions.pop(session_key, None)
        except Exception:
            pass
        raise CliError(
            "worker_stall",
            "Shannon tmux server died during the turn (no server running); the "
            "Claude session crashed before producing a result — retrying on a "
            "fresh session.",
            extra={"raw_output": raw, "session_id": main_turn.session_id},
        )

    # ── (i) parse + (execute-only) repair the structured envelope ───────
    # A heavy execute batch can exhaust max_tokens on reasoning before emitting
    # the envelope. The work itself stands — a resume turn that asks for ONLY
    # the envelope is far cheaper than redoing the whole batch, and the
    # surrounding execute loop deliberately does not retry execute.
    def _parse_and_validate(raw_text: str) -> tuple[dict[str, Any], dict[str, Any]]:
        env_, pay_ = _parse_shannon_output(raw_text)
        pay_ = _apply_file_fallback(step, pay_, plan_dir, output_path=output_path)
        pay_ = _normalize_worker_payload(step, pay_)
        validate_payload(step, pay_)
        return env_, pay_

    try:
        envelope, payload = _parse_and_validate(raw)
    except CliError as error:
        repaired_raw: str | None = None
        if step == "execute" and error.code in {"parse_error", "schema_error"}:
            repair_sid = session_id_of(raw) or main_turn.session_id
            repair_turn = Turn(
                session_id=repair_sid,
                resume=True,
                body=_EXECUTE_ENVELOPE_REPAIR_PROMPT,
                delivery="argv",
                expect="envelope",
                timeout=cfg.execute_timeout_seconds,
                pre_sleep_s=0.0,
            )
            print(
                "[megaplan] execute output was truncated/invalid; resuming "
                f"session {repair_sid} to re-request only the structured envelope.",
                file=sys.stderr,
                flush=True,
            )
            try:
                repair_result = run_turn(repair_turn, ctx)
                repaired_raw = repair_result.raw or None
            except CliError:
                repaired_raw = None
        if repaired_raw is None:
            raise CliError(error.code, error.message, extra={"raw_output": raw}) from error
        try:
            envelope, payload = _parse_and_validate(repaired_raw)
        except CliError as repair_error:
            raise CliError(
                repair_error.code,
                f"{repair_error.message} (after structured-envelope repair attempt)",
                extra={"raw_output": repaired_raw, "original_raw_output": raw},
            ) from repair_error
        raw = repaired_raw

    return WorkerResult(
        payload=payload,
        raw_output=raw,
        duration_ms=main_result.duration_ms,
        cost_usd=float(envelope.get("total_cost_usd", 0.0) or 0.0),
        session_id=str(envelope.get("session_id") or session_id),
        rendered_prompt=prompt,
        model_actual=_extract_actual_model_from_envelope(envelope),
        prompt_tokens=_extract_claude_usage(envelope)[0],
        completion_tokens=_extract_claude_usage(envelope)[1],
        total_tokens=sum(_extract_claude_usage(envelope)),
        shannon_plan=_serialize_session_plan(plan),
    )
