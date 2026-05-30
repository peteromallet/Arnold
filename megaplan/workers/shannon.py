"""Shannon worker — opt-in Claude launcher via interactive tmux sessions.

Shannon (https://github.com/dexhorthy/shannon) runs real Claude Code in tmux,
sends prompts, and tails the Claude transcript JSONL instead of using
``claude -p``.  This module provides ``run_shannon_step``, a drop-in launcher
that preserves the same WorkerResult contract, schema validation, session
tracking, timeouts, error handling, and receipts as the native Claude path.
"""

from __future__ import annotations

import json
import logging
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

from megaplan.runtime.process import OrphanDetectedError, TmuxSession, pane_pids
from megaplan.types import CliError, MOCK_ENV_VAR, PlanState
from megaplan._core import creative_form_id, json_dump, read_json, schemas_root
from megaplan.prompts import create_claude_prompt
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


def _shannon_readiness_probe_enabled(session_agent: str) -> bool:
    raw = os.getenv("MEGAPLAN_SHANNON_READINESS_PROBE", "").strip().lower()
    if raw == "always":
        return True
    configured = _env_truthy("MEGAPLAN_SHANNON_READINESS_PROBE")
    if configured is not None:
        return configured
    if session_agent == "claude":
        return True
    # Cloud workers set trusted-container mode. Keep local Shannon runs as a
    # single turn unless explicitly opted in, because the probe adds latency.
    return _env_truthy("MEGAPLAN_TRUSTED_CONTAINER") is True


def _shannon_readiness_probe_forced() -> bool:
    return os.getenv("MEGAPLAN_SHANNON_READINESS_PROBE", "").strip().lower() == "always"


def _shannon_readiness_timeout_seconds() -> int:
    raw = os.getenv("MEGAPLAN_SHANNON_READINESS_TIMEOUT_SECONDS", "").strip()
    if not raw:
        return 120
    try:
        return max(1, int(raw))
    except ValueError:
        return 120


def _shannon_execute_timeout_seconds() -> int:
    raw = os.getenv("MEGAPLAN_SHANNON_EXECUTE_TIMEOUT_SECONDS", "").strip()
    if not raw:
        return 7200
    try:
        return max(1, int(raw))
    except ValueError:
        return 7200


def _shannon_max_output_tokens() -> int:
    """Output-token budget for the Claude CLI that Shannon launches.

    Shannon forwards ``--effort`` to ``claude`` but never sets an explicit
    output-token ceiling, so the launched Claude Code inherits its built-in
    default (~64k combined thinking+text for opus). On a heavy ``execute``
    batch, opus can spend that entire budget on one reasoning/content block and
    get cut off at ``max_tokens`` *before* it emits the required structured
    result envelope (``task_updates`` / ``sense_check_acknowledgments``), so the
    batch fails with no forward progress.

    megaplan owns the phase budget, so raise the Claude output ceiling well
    above that default via ``CLAUDE_CODE_MAX_OUTPUT_TOKENS`` (the env var Claude
    Code reads). opus-4-x supports far larger output budgets; 128k leaves ample
    headroom for a long reasoning prelude *and* the final JSON envelope.
    Overridable via ``MEGAPLAN_SHANNON_MAX_OUTPUT_TOKENS``.
    """
    raw = os.getenv("MEGAPLAN_SHANNON_MAX_OUTPUT_TOKENS", "").strip()
    if not raw:
        return 128000
    try:
        return max(1, int(raw))
    except ValueError:
        return 128000


def _shannon_bash_timeout_ms() -> int:
    """Per-command Bash-tool timeout for the Claude CLI that Shannon launches.

    Claude Code's built-in Bash tool kills any single *foreground* command at
    ``BASH_DEFAULT_TIMEOUT_MS`` (default 120000ms = 120s) with a SIGKILL and the
    message ``Command timed out after 120s``. That default is per-command, not
    per-turn, so it is invisible on light batches but lethal on a legitimate
    long-running command inside an ``execute`` turn — e.g. ``python -m pytest
    tests/`` on a full suite, a build, or an integration run. A forensic
    analysis of a failed run found exactly this: the final worker attempt was
    SIGKILLed (exit 137) mid-``pytest`` at 120s while earlier batches that never
    ran a single >2min command completed fine in 5-10 minutes.

    megaplan — not the spawned Claude Code's per-command default — owns the
    stop-policy here: the worker has a 7200s execute cap (``run_command``
    ``timeout``) and a 900s idle-output stall watchdog (``idle_timeout``). So
    raise the launched CLI's Bash ceiling well above that 120s default and let
    megaplan's phase budget + stall watchdog decide when to stop waiting,
    matching how we already override ``SHANNON_TURN_TIMEOUT_MS`` and
    ``CLAUDE_CODE_MAX_OUTPUT_TOKENS``. Overridable via
    ``MEGAPLAN_SHANNON_BASH_TIMEOUT_MS``.
    """
    raw = os.getenv("MEGAPLAN_SHANNON_BASH_TIMEOUT_MS", "").strip()
    if not raw:
        return 7200000
    try:
        return max(1, int(raw))
    except ValueError:
        return 7200000


def _shannon_handshake_probability() -> float:
    raw = os.getenv("MEGAPLAN_SHANNON_HANDSHAKE_PROBABILITY", "").strip()
    if not raw:
        return 0.8
    try:
        return min(1.0, max(0.0, float(raw)))
    except ValueError:
        return 0.8


def _shannon_should_send_handshake() -> bool:
    return random.random() < _shannon_handshake_probability()


def _shannon_random_handshake_prompt() -> str:
    return random.choice(_SHANNON_READINESS_PROMPTS)


def _shannon_random_handshake_delay_seconds() -> float:
    return random.randrange(10, 151) / 10


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


def _shannon_session_roulette_enabled() -> bool:
    """Whether to apply the shed-context session strategy (clear/compact on reuse).

    Default on. Set ``MEGAPLAN_SHANNON_SESSION_ROULETTE=0`` to restore the legacy
    deterministic behavior (execute plain-resumes when it can; every other phase
    always starts fresh).
    """
    configured = _env_truthy("MEGAPLAN_SHANNON_SESSION_ROULETTE")
    return True if configured is None else configured


def _session_strategy_probability(env_name: str, default: float) -> float:
    raw = os.getenv(env_name, "").strip()
    if not raw:
        return default
    try:
        return min(1.0, max(0.0, float(raw)))
    except ValueError:
        return default


def _select_session_strategy(
    step: str, *, has_session: bool, explicit_fresh: bool, slash_supported: bool = True
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
    """
    if not has_session:
        return "new"
    if not _shannon_session_roulette_enabled():
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
    compact_p = _session_strategy_probability(
        "MEGAPLAN_SHANNON_SESSION_COMPACT_PROBABILITY", 0.25
    )
    return "compact" if random.random() < compact_p else "clear"


def _shannon_context_op_timeout_seconds() -> int:
    """Bounded timeout for an injected ``/compact`` or ``/clear`` turn.

    Compaction/clear turns may not emit a normal assistant reply, so they run
    under a short cap (best-effort) rather than the full execute budget; on
    timeout the run silently proceeds with a plain resume. Override via
    ``MEGAPLAN_SHANNON_CONTEXT_OP_TIMEOUT_SECONDS``.
    """
    raw = os.getenv("MEGAPLAN_SHANNON_CONTEXT_OP_TIMEOUT_SECONDS", "").strip()
    if not raw:
        return 180
    try:
        return max(1, int(raw))
    except ValueError:
        return 180


def _shannon_context_op_delay_seconds() -> float:
    """Randomized human-like pause before a ``/compact`` or ``/clear`` turn fires.

    A context op shouldn't trigger the instant the strategy is rolled — a short
    random jitter makes the pacing less mechanical (so a resumed session isn't
    cleared the moment it's picked up). Range is tunable via
    ``MEGAPLAN_SHANNON_CONTEXT_OP_DELAY_MIN_SECONDS`` /
    ``MEGAPLAN_SHANNON_CONTEXT_OP_DELAY_MAX_SECONDS`` (defaults 1.0..15.0,
    matching the readiness-handshake jitter). Set MAX to 0 to disable.
    """
    def _read(name: str, default: float) -> float:
        raw = os.getenv(name, "").strip()
        if not raw:
            return default
        try:
            return max(0.0, float(raw))
        except ValueError:
            return default

    low = _read("MEGAPLAN_SHANNON_CONTEXT_OP_DELAY_MIN_SECONDS", 1.0)
    high = _read("MEGAPLAN_SHANNON_CONTEXT_OP_DELAY_MAX_SECONDS", 15.0)
    if high <= 0:
        return 0.0
    if low > high:
        low = high
    # Tenth-second granularity, mirroring _shannon_random_handshake_delay_seconds.
    return random.randrange(int(low * 10), int(high * 10) + 1) / 10


def _shannon_paste_first_turn_enabled() -> bool:
    """Deliver the real phase prompt as a pasted first turn, not an argv launcher.

    When on (and the Shannon paste-first-turn patch is present), the main turn's
    full prompt is sent over stdin (stream-json) and Shannon launches Claude bare
    then pastes it as turn 1 — so Claude receives the actual task instead of a
    "read this file and follow it" pointer, with no argv size limit. Non-root
    interactive path only.

    EXPERIMENTAL, default OFF. The bare-launch path is timing-sensitive: Shannon's
    waitForPrompt can fire on Claude's welcome banner before the input box is
    ready, racing the turn-1 paste (mitigated here by a bootstrap-enter nudge, but
    not yet bulletproof across machine speeds). Keep opt-in until waitForPrompt is
    hardened. The caller additionally gates on the patch being present
    (``_shannon_supports_paste_first_turn``) so enabling it on an unpatched
    shannon safely falls back to the argv launcher. Set
    ``MEGAPLAN_SHANNON_PASTE_FIRST_TURN=1`` to enable.
    """
    return _env_truthy("MEGAPLAN_SHANNON_PASTE_FIRST_TURN") is True


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


def _write_prompt_file(plan_dir: Path, step: str, prompt: str, *, iteration: int | None = None) -> Path:
    if iteration is None:
        prompt_path = plan_dir / f"{step}_shannon_prompt.txt"
    else:
        prompt_path = plan_dir / f"{step}_v{iteration}_shannon_prompt.txt"
    prompt_path.write_text(prompt, encoding="utf-8")
    return prompt_path


def _shannon_package_entrypoint() -> Path | None:
    executable = shutil.which("shannon")
    if not executable:
        return None
    bin_path = Path(executable).resolve()
    candidate = bin_path.parent.parent / "index.ts"
    return candidate if candidate.is_file() else None


def _shannon_entrypoint_contains(marker: str) -> bool:
    """Whether the installed shannon entrypoint carries a given megaplan patch.

    The megaplan Shannon patches are applied in-place to whatever ``@dexh/shannon``
    is on PATH. On another user's machine that copy may be a different version
    (anchors miss), live in a read-only/system dir (cannot be written), or have
    auto-patch disabled — in any of which the patch is simply absent. Features
    that REQUIRE a patch must detect this and degrade safely rather than assume
    the patch landed. Best-effort: any read failure reports "not present".
    """
    entrypoint = _shannon_package_entrypoint()
    if entrypoint is None:
        return False
    try:
        return marker in entrypoint.read_text(encoding="utf-8")
    except OSError:
        return False


def _shannon_supports_paste_first_turn() -> bool:
    # Marker spliced by the paste-first-turn patch (see
    # _ensure_shannon_parent_timeout_control). Without it, sending the prompt via
    # stdin/no-``-p`` would make an unpatched shannon argv-launch turn 1 and hit
    # ARG_MAX, so callers fall back to the argv launcher.
    return _shannon_entrypoint_contains("let launchedWithPrompt = !(")


def _shannon_supports_slash_completion() -> bool:
    # Marker spliced by the slash-command completion patch. Without it, a
    # ``/compact``/``/clear`` turn cannot be detected as complete and burns the op
    # timeout, so callers shed context via a fresh session ("new") instead.
    return _shannon_entrypoint_contains("function megaplanSlashCompletionRow(")


# Version of the megaplan helper block. Bump when any helper body changes so an
# already-patched install replaces the stale block (see the sentinel-replace
# logic in _ensure_shannon_parent_timeout_control) instead of keeping the old one.
_SHANNON_HELPERS_VERSION = "v2"


def _ensure_shannon_parent_timeout_control() -> None:
    """Patch known npm @dexh/shannon 0.0.2 defects in-place when needed.

    The published package has a lower, hardcoded 180s turn timeout than
    megaplan's worker timeout and can return on an intermediate tool-use
    assistant row. Until Shannon publishes those fixes, keep this compatibility
    patch local and targeted so the public ``claude`` route remains reliable.
    """
    if os.getenv("MEGAPLAN_SHANNON_AUTO_PATCH", "1").lower() in {"0", "false", "no"}:
        return

    entrypoint = _shannon_package_entrypoint()
    if entrypoint is None:
        return

    try:
        original = entrypoint.read_text(encoding="utf-8")
    except OSError:
        return

    patched = original.replace(
        "const TURN_TIMEOUT_MS = 180_000;",
        "const TURN_TIMEOUT_MS = Number(Bun.env.SHANNON_TURN_TIMEOUT_MS ?? 900_000);",
    )
    tool_use_guard = '    if (row.message?.stop_reason === "tool_use") continue;\n'
    target = "    if (textFromContent(row.message.content)) return row;\n"
    if tool_use_guard not in patched and target in patched:
        patched = patched.replace(target, tool_use_guard + target, 1)

    # Each helper function is inserted independently in front of
    # ``buildClaudeArgs`` and gated on its own unique signature substring.
    # The previous implementation bundled all three into one blob gated on
    # ``rootSafeClaudeArgs``; if a prior megaplan version had patched the
    # entrypoint with just ``isRootProcess``/``rootSafeClaudeArgs`` (older
    # blob), the next patch saw the gate satisfied and skipped the entire
    # blob — leaving ``maybeSendStartupEnterKeys`` undefined while its call
    # site was still spliced in below.  Splitting the gates lets a
    # partially-patched entrypoint heal on the next pass.
    build_anchor = "export function buildClaudeArgs(parsed: Record<string, unknown>): string[] {\n"

    def _insert_before_build_args(source: str, helper: str) -> str:
        if build_anchor in source:
            return source.replace(build_anchor, helper + "\n" + build_anchor, 1)
        match = re.search(
            r"(?m)^export function buildClaudeArgs\(parsed: Record<string, unknown>\): string\[\] \{",
            source,
        )
        if not match:
            return source
        return source[: match.start()] + helper + "\n" + source[match.start() :]

    is_root_helper = r'''
function isRootProcess() {
  return typeof process.getuid === "function" && process.getuid() === 0;
}
'''.lstrip()

    root_safe_args_helper = r'''
function rootSafeClaudeArgs(args: string[]): string[] {
  if (!isRootProcess()) return args;

  const filtered: string[] = [];
  for (let index = 0; index < args.length; index += 1) {
    const arg = args[index];
    if (arg === "--dangerously-skip-permissions" || arg === "--allow-dangerously-skip-permissions") {
      continue;
    }
    if (arg === "--permission-mode" && args[index + 1] === "bypassPermissions") {
      filtered.push("--permission-mode", "auto");
      index += 1;
      continue;
    }
    if (arg === "--session-id" || arg === "--resume") {
      index += 1;
      continue;
    }
    if (arg === "--continue") {
      continue;
    }
    filtered.push(arg);
  }
  return filtered;
}
'''.lstrip()

    startup_enter_helper = r'''
async function maybeSendStartupEnterKeys(tmuxSession: string) {
  const count = Number(Bun.env.MEGAPLAN_SHANNON_BOOTSTRAP_ENTER_COUNT ?? 0);
  if (!Number.isFinite(count) || count <= 0) return;
  const delayMs = Number(Bun.env.MEGAPLAN_SHANNON_BOOTSTRAP_ENTER_DELAY_MS ?? 1000);
  for (let index = 0; index < count; index += 1) {
    await sleep(Math.max(100, delayMs));
    await runCommand(["tmux", "send-keys", "-t", tmuxSession, "C-m"], false);
  }
}
'''.lstrip()

    # Insertion order is preserved by inserting each in front of the same
    # anchor in reverse declaration order: maybeSendStartupEnterKeys first,
    # then rootSafeClaudeArgs, then isRootProcess, so the resulting file
    # ordering reads isRootProcess -> rootSafeClaudeArgs ->
    # maybeSendStartupEnterKeys -> buildClaudeArgs.
    if (
        "async function maybeSendStartupEnterKeys(tmuxSession: string)" not in patched
    ):
        patched = _insert_before_build_args(patched, startup_enter_helper)
    if (
        "function rootSafeClaudeArgs(args: string[]): string[]" not in patched
    ):
        patched = _insert_before_build_args(patched, root_safe_args_helper)
    if (
        "function isRootProcess()" not in patched
    ):
        patched = _insert_before_build_args(patched, is_root_helper)
    patched = patched.replace(
        '''    if (arg === "--permission-mode" && args[index + 1] === "bypassPermissions") {
      index += 1;
      continue;
    }
''',
        '''    if (arg === "--permission-mode" && args[index + 1] === "bypassPermissions") {
      filtered.push("--permission-mode", "auto");
      index += 1;
      continue;
    }
''',
    )

    launch_target = '''    await runCommand([
      "tmux",
      "new-session",
      "-d",
      "-s",
      tmuxSession,
      "-c",
      options.cwd,
      "claude",
      ...options.claudeArgs,
      prompt,
    ]);
'''
    launch_replacement = '''    const claudeLaunchArgs = isRootProcess()
      ? ["claude", "-p", ...rootSafeClaudeArgs(options.claudeArgs), prompt]
      : ["claude", ...options.claudeArgs, prompt];
    await runCommand([
      "tmux",
      "new-session",
      "-d",
      "-s",
      tmuxSession,
      "-c",
      options.cwd,
      ...claudeLaunchArgs,
    ]);
'''
    if launch_target in patched and launch_replacement not in patched:
        patched = patched.replace(launch_target, launch_replacement, 1)
    elif (
        "const claudeLaunchArgs = isRootProcess()" not in patched
        and re.search(r'(?m)^\s+"claude",\n\s+\.\.\.options\.claudeArgs,\n\s+prompt,\n', patched)
    ):
        patched = re.sub(
            r"(?m)^(\s*)await runCommand\(\[\n",
            '\\1const claudeLaunchArgs = isRootProcess()\n'
            '\\1  ? ["claude", "-p", ...rootSafeClaudeArgs(options.claudeArgs), prompt]\n'
            '\\1  : ["claude", ...options.claudeArgs, prompt];\n'
            "\\1await runCommand([\n",
            patched,
            count=1,
        )
        patched = re.sub(
            r'(?m)^\s+"claude",\n\s+\.\.\.options\.claudeArgs,\n\s+prompt,\n',
            "      ...claudeLaunchArgs,\n",
            patched,
            count=1,
        )

    startup_target = "    let launchedWithPrompt = true;\n"
    startup_replacement = "    void maybeSendStartupEnterKeys(tmuxSession);\n\n    let launchedWithPrompt = true;\n"
    if startup_replacement not in patched and startup_target in patched:
        patched = patched.replace(startup_target, startup_replacement, 1)
    elif (
        "void maybeSendStartupEnterKeys(tmuxSession);" not in patched
        and re.search(r"(?m)^(\s*)let launchedWithPrompt = true;\s*$", patched)
    ):
        patched = re.sub(
            r"(?m)^(\s*)let launchedWithPrompt = true;\s*$",
            r"\1void maybeSendStartupEnterKeys(tmuxSession);\n\n\1let launchedWithPrompt = true;",
            patched,
            count=1,
        )

    # Patch megaplanTmuxSessionName to honour SHANNON_TMUX_SESSION_NAME so
    # megaplan can supply a deterministic tmux session name for lifecycle
    # ownership (cross-process orphan prevention).
    _tmux_name_anchor = (
        "return sessionId ? `shannon-${sessionId}` : `shannon-${randomUUID()}`;"
    )
    _tmux_name_replacement = (
        "return Bun.env.SHANNON_TMUX_SESSION_NAME ?? "
        "(sessionId ? `shannon-${sessionId}` : `shannon-${randomUUID()}`);"
    )
    if _tmux_name_anchor in patched and _tmux_name_replacement not in patched:
        patched = patched.replace(_tmux_name_anchor, _tmux_name_replacement, 1)
    elif _tmux_name_anchor not in patched and "Bun.env.SHANNON_TMUX_SESSION_NAME" not in patched:
        logging.getLogger(__name__).warning(
            "Shannon megaplanTmuxSessionName anchor not found in %s — "
            "skipping patch; deterministic tmux session naming will not be "
            "available.",
            entrypoint,
        )

    # --- megaplan: slash-command turn completion (/compact, /clear) ---------
    # Stock Shannon both discovers a session (rowContainsPromptAfter) and
    # detects a turn's completion (assistantReplyFromRows) by an EXACT
    # prompt-echo match: row.message.content === prompt. A slash command is
    # recorded in the transcript as "<command-name>/compact</command-name>…",
    # never the bare "/compact", so both gates miss it and the turn burns the
    # full turn timeout before exiting non-zero — even though the command ran.
    # Teach both gates to recognise a slash-command turn, and complete it on the
    # real on-disk markers (verified against Claude Code v2.1.x transcripts):
    #   /compact done -> a row with subtype "compact_boundary" (or isCompactSummary
    #                    true, or a <local-command-stdout>/"Compacted"/"Not enough
    #                    messages to compact" line for the no-op case).
    #   /clear  done -> the "<command-name>/clear" row, which Claude writes into a
    #                    freshly-ROTATED session file; discovery lands on that new
    #                    file so Shannon emits the new session_id (the work turn
    #                    must resume THAT, not the cleared id).
    slash_helpers = (
        f"// >>> megaplan-shannon-helpers {_SHANNON_HELPERS_VERSION} >>>\n"
    ) + r'''
function megaplanSlashCommand(prompt) {
  if (typeof prompt !== "string") return undefined;
  const trimmed = prompt.trimStart();
  if (!trimmed.startsWith("/")) return undefined;
  return trimmed.trim().split(/\s+/)[0];
}

function megaplanSlashPromptMatches(prompt, content) {
  const cmd = megaplanSlashCommand(prompt);
  if (!cmd || typeof content !== "string") return false;
  return content.includes("<command-name>" + cmd);
}

function megaplanRowText(row) {
  const top = typeof row.content === "string" ? row.content : "";
  const msg = typeof row.message?.content === "string" ? row.message.content : "";
  return top + "\n" + msg;
}

function megaplanSlashSynthReply(cmd, sessionId, row) {
  const sid = (row && (row.sessionId ?? row.session_id)) ?? sessionId;
  return {
    type: "assistant",
    message: {
      role: "assistant",
      content: [{ type: "text", text: "[megaplan] slash command " + cmd + " completed" }],
      stop_reason: "end_turn",
      usage: {},
      model: "unknown",
    },
    sessionId: sid,
    session_id: sid,
    uuid: (row && row.uuid) ?? randomUUID(),
  };
}

function megaplanSlashCompletionRow(prompt, rows) {
  const cmd = megaplanSlashCommand(prompt);
  if (!cmd) return undefined;
  // Anchor on the LAST freshly-submitted command row: a resumed session may
  // already contain earlier /compact|/clear command rows, prior
  // <local-command-stdout> rows, or content that merely mentions the markers,
  // and scanning from the first match would falsely complete on stale rows.
  let cmdIdx = -1;
  for (let i = 0; i < rows.length; i += 1) {
    if (megaplanRowText(rows[i]).includes("<command-name>" + cmd)) cmdIdx = i;
  }
  if (cmdIdx < 0) return undefined;
  let sessionId = rows[cmdIdx].sessionId ?? rows[cmdIdx].session_id;
  // /clear is instantaneous and rotates the session; the command row in the new
  // transcript IS the completion.
  if (cmd === "/clear") return megaplanSlashSynthReply(cmd, sessionId, rows[cmdIdx]);
  // Only markers AFTER the freshly-submitted command row count as completion.
  for (let i = cmdIdx + 1; i < rows.length; i += 1) {
    const row = rows[i];
    sessionId = row.sessionId ?? row.session_id ?? sessionId;
    const text = megaplanRowText(row);
    if (row.subtype === "compact_boundary" || row.isCompactSummary === true) {
      return megaplanSlashSynthReply(cmd, sessionId, row);
    }
    if (text.includes("<local-command-stdout>") || text.includes("Compacted") || text.includes("Not enough messages to compact")) {
      return megaplanSlashSynthReply(cmd, sessionId, row);
    }
    if (row.type === "assistant" && row.message?.role === "assistant" && row.message?.stop_reason !== "tool_use" && textFromContent(row.message?.content)) {
      return megaplanSlashSynthReply(cmd, sessionId, row);
    }
  }
  return undefined;
}
// <<< megaplan-shannon-helpers <<<
'''.lstrip()

    # Sentinel-delimited so a helper body change actually propagates: if the
    # CURRENT version block isn't present, strip any older megaplan helper block
    # and (re)insert the current one. (String-anchored insertion alone can't
    # update an already-inserted helper — it would keep the stale version.)
    _helpers_begin = "// >>> megaplan-shannon-helpers"
    _helpers_current = f"{_helpers_begin} {_SHANNON_HELPERS_VERSION} >>>"
    if _helpers_current not in patched:
        patched = re.sub(
            re.escape(_helpers_begin) + r".*?// <<< megaplan-shannon-helpers <<<\n",
            "",
            patched,
            flags=re.DOTALL,
        )
        patched = _insert_before_build_args(patched, slash_helpers)

    # Discovery gate: accept the wrapped slash-command row.
    discovery_target = (
        '  if (row.type !== "user" || row.message?.content !== prompt) return false;\n'
    )
    discovery_replacement = (
        '  if (row.type !== "user") return false;\n'
        "  if (row.message?.content !== prompt && "
        "!megaplanSlashPromptMatches(prompt, row.message?.content)) return false;\n"
    )
    if discovery_target in patched and discovery_replacement not in patched:
        patched = patched.replace(discovery_target, discovery_replacement, 1)

    # Completion gate: short-circuit assistantReplyFromRows for slash commands.
    completion_target = (
        "export function assistantReplyFromRows(prompt: string, rows: TranscriptRow[]): TranscriptRow | undefined {\n"
        "  let sawPrompt = false;\n"
    )
    completion_replacement = (
        "export function assistantReplyFromRows(prompt: string, rows: TranscriptRow[]): TranscriptRow | undefined {\n"
        "  const megaplanSlashReply = megaplanSlashCompletionRow(prompt, rows);\n"
        "  if (megaplanSlashReply) return megaplanSlashReply;\n"
        "  let sawPrompt = false;\n"
    )
    if completion_target in patched and completion_replacement not in patched:
        patched = patched.replace(completion_target, completion_replacement, 1)

    # --- megaplan: paste the first turn instead of cramming it into argv ----
    # Stock Shannon launches ``claude … <prompt>`` with the FIRST prompt in argv,
    # which (a) caps prompt size at ARG_MAX and (b) forces megaplan to send a
    # "read this file and follow it" launcher pointer rather than the real task —
    # an in-session tell and an extra layer of indirection. When
    # MEGAPLAN_SHANNON_PASTE_FIRST_TURN is set (non-root interactive path only),
    # launch claude with NO prompt and deliver turn 1 through the same
    # waitForPrompt→sendPrompt paste path used for every later turn, so the real
    # phase prompt (fed via --input-format=stream-json on stdin) arrives as a
    # normal pasted first message with no argv limit.
    paste_args_target = "      : [\"claude\", ...options.claudeArgs, prompt];\n"
    paste_args_replacement = (
        "      : (Bun.env.MEGAPLAN_SHANNON_PASTE_FIRST_TURN\n"
        "          ? [\"claude\", ...options.claudeArgs]\n"
        "          : [\"claude\", ...options.claudeArgs, prompt]);\n"
    )
    if paste_args_target in patched and paste_args_replacement not in patched:
        patched = patched.replace(paste_args_target, paste_args_replacement, 1)

    paste_flag_target = "    let launchedWithPrompt = true;\n"
    paste_flag_replacement = (
        "    let launchedWithPrompt = !(Bun.env.MEGAPLAN_SHANNON_PASTE_FIRST_TURN && !isRootProcess());\n"
    )
    if paste_flag_target in patched and "let launchedWithPrompt = !(" not in patched:
        patched = patched.replace(paste_flag_target, paste_flag_replacement, 1)

    # --- megaplan: feed the tmux buffer via stdin, not argv -----------------
    # Stock sendPrompt does `tmux set-buffer -b <name> <prompt>` — the prompt is
    # an ARGV argument to tmux, whose command parser caps at ~16KB, far below
    # ARG_MAX. Real megaplan prompts are 70-128KB, so set-buffer truncates/fails
    # and the turn dies. Feed the buffer over stdin (`load-buffer -b <name> -`)
    # instead — no size cap — and paste with `-p` (bracketed paste) so a
    # multi-line prompt isn't submitted line-by-line.
    send_prompt_target = (
        '  await runCommand(["tmux", "set-buffer", "-b", `shannon-${tmuxSession}`, prompt]);\n'
        '  await runCommand(["tmux", "paste-buffer", "-b", `shannon-${tmuxSession}`, "-t", tmuxSession]);\n'
    )
    send_prompt_replacement = (
        "  const _mpBuf = `shannon-${tmuxSession}`;\n"
        '  const _mpLoad = Bun.spawn(["tmux", "load-buffer", "-b", _mpBuf, "-"], '
        '{ stdin: "pipe", stdout: "pipe", stderr: "pipe" });\n'
        "  _mpLoad.stdin.write(prompt);\n"
        "  await _mpLoad.stdin.end();\n"
        "  if ((await _mpLoad.exited) !== 0) {\n"
        "    throw new Error(`tmux load-buffer failed: ${await new Response(_mpLoad.stderr).text()}`);\n"
        "  }\n"
        '  await runCommand(["tmux", "paste-buffer", "-p", "-b", _mpBuf, "-t", tmuxSession]);\n'
    )
    if send_prompt_target in patched and "tmux load-buffer" not in patched:
        patched = patched.replace(send_prompt_target, send_prompt_replacement, 1)

    # --- megaplan: match Claude Code's project-folder slug for dotted paths ---
    # Shannon derives the ~/.claude/projects/<slug> folder by replacing non
    # [A-Za-z0-9._-] with "-", which KEEPS ".". Claude Code replaces "." too, so
    # for a cwd under ".megaplan-worktrees" Shannon searches
    # "…-.megaplan-worktrees-…" while Claude wrote "…--megaplan-worktrees-…" →
    # the transcript is never found and EVERY claude phase times out
    # ("Timed out waiting for Claude transcript…"). Drop "." from the kept set so
    # the slug matches. Fixes all worktree-based runs.
    slug_target = 'return resolve(cwd).normalize("NFC").replace(/[^a-zA-Z0-9._-]/g, "-");'
    slug_replacement = 'return resolve(cwd).normalize("NFC").replace(/[^a-zA-Z0-9_-]/g, "-");'
    if slug_target in patched:
        patched = patched.replace(slug_target, slug_replacement, 1)

    if patched == original:
        return

    backup = entrypoint.with_suffix(entrypoint.suffix + ".bak.megaplan-shannon")
    tmp = entrypoint.with_name(f"{entrypoint.name}.megaplan.tmp.{os.getpid()}")
    try:
        if not backup.exists():
            backup.write_text(original, encoding="utf-8")
        # Atomic publish: write a temp file in the same dir, then os.replace it
        # into place. megaplan launches `bun index.ts` constantly and runs many
        # Shannon processes concurrently (epics, bakeoffs, `megaplan cloud`
        # multi-tenancy); a non-atomic write_text would let a bun launch — or
        # another patcher's read — observe a half-written file (truncated TS →
        # syntax error → the whole turn crashes; partial read → duplicate helper
        # inserts). os.replace is atomic on POSIX, so every reader/launcher sees
        # either the old or the fully-patched file, never a torn one. Combined
        # with the idempotent anchor gates, concurrent writers converge on the
        # same content (last-writer-wins is harmless).
        tmp.write_text(patched, encoding="utf-8")
        os.replace(tmp, entrypoint)
    except OSError:
        try:
            tmp.unlink()
        except OSError:
            pass
        return


def _running_as_root() -> bool:
    return hasattr(os, "geteuid") and os.geteuid() == 0


def _shannon_drop_root_enabled() -> bool:
    configured = _env_truthy("MEGAPLAN_SHANNON_DROP_ROOT")
    if configured is not None:
        return configured
    return _running_as_root() and _env_truthy("MEGAPLAN_TRUSTED_CONTAINER") is True


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


def _prepare_nonroot_shannon_runtime(work_dir: Path, env: dict[str, str]) -> tuple[list[str], dict[str, str]]:
    """Return a command prefix/env that lets Shannon launch interactive Claude.

    Claude refuses ``bypassPermissions`` when the process itself is root. In a
    trusted cloud container, Megaplan can stay root as the supervisor while the
    Shannon/Claude child runs as an unprivileged user. That preserves Shannon's
    interactive tmux behavior instead of falling back to ``claude -p``.
    """
    if not _shannon_drop_root_enabled():
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

    if _env_truthy("MEGAPLAN_SHANNON_CHMOD_WORKSPACE") is not False:
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


def _envelope_session_id(raw: str) -> str | None:
    """Best-effort extraction of the Shannon/Claude session id from raw output.

    Used to resume the same session for an envelope-repair turn even when the
    payload itself failed to parse/validate.
    """
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if isinstance(data, dict):
        sid = data.get("session_id")
        return str(sid) if sid else None
    if isinstance(data, list):
        for msg in reversed(data):
            if isinstance(msg, dict):
                sid = msg.get("session_id") or (
                    msg.get("message", {}).get("sessionId")
                    if isinstance(msg.get("message"), dict)
                    else None
                )
                if sid:
                    return str(sid)
    return None


def _apply_file_fallback(step: str, payload: dict[str, Any], plan_dir: Path) -> dict[str, Any]:
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
    fallback_path = plan_dir / fallback_name
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


def _claude_transcript_paths(session_id: str | None, work_dir: Path) -> list[Path]:
    """Best-effort list of candidate Claude transcript .jsonl files for a turn.

    Shannon drives a real Claude Code session and Claude appends to a
    per-session transcript under ``~/.claude/projects/<slug>/<session>.jsonl``.
    That file's mtime advances as the turn produces content blocks (even though
    shannon emits nothing on stdout under ``--output-format=json``), so a moving
    mtime is a reliable "the turn is still doing work" signal. The project slug
    encoding is Claude-internal, so we glob defensively by session id and fall
    back to a directory-wide scan keyed on the work_dir slug. Returns ``[]`` when
    nothing is found (the probe then leans on the tmux-pane signal instead).
    """
    paths: list[Path] = []
    try:
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
        for path in _claude_transcript_paths(session_id, work_dir):
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


def _repair_execute_envelope(
    *,
    base_command: list[str],
    session_id: str,
    launch_command,
    work_dir: Path,
    env: dict[str, str],
    state: PlanState,
    plan_dir: Path,
    tmux_session: TmuxSession,
) -> str | None:
    """Resume the just-run execute session and ask only for the JSON envelope.

    Returns the raw Shannon output of the repair turn, or ``None`` if the repair
    could not even be launched. Best-effort: any failure returns ``None`` so the
    caller falls back to raising the original parse/validation error.
    """
    # Rebuild the argv so the resume turn's ``-p`` prompt is the repair prompt,
    # not the original "read the prompt file" launcher prompt.
    repair_command: list[str] = []
    index = 0
    while index < len(base_command):
        token = base_command[index]
        if token == "-p" and index + 1 < len(base_command):
            repair_command.extend(["-p", _EXECUTE_ENVELOPE_REPAIR_PROMPT])
            index += 2
            continue
        repair_command.append(token)
        index += 1
    repair_command.extend(["--resume", session_id])
    print(
        "[megaplan] execute output was truncated/invalid; resuming session "
        f"{session_id} to re-request only the structured envelope.",
        file=sys.stderr,
        flush=True,
    )
    try:
        repair = run_command(
            launch_command(repair_command),
            cwd=work_dir,
            stdin_text=None,
            env=env,
            timeout=_shannon_execute_timeout_seconds(),
            activity_callback=_activity_callback_for_state(state, plan_dir),
            idle_timeout=_worker_stream_idle_timeout_seconds(),
            liveness_probe=_make_shannon_liveness_probe(
                tmux_session, session_id, work_dir
            ),
            tmux_session=tmux_session,
        )
    except CliError:
        return None
    repaired_raw = repair.stdout or repair.stderr
    return repaired_raw or None


def _stream_session_id(raw: str) -> str | None:
    """Extract the session id Shannon landed on from its NDJSON stream output.

    The op turn (/compact, /clear) emits ``--output-format=stream-json`` — one
    JSON object per line, not a single array — so ``_envelope_session_id`` (which
    ``json.loads`` the whole blob) can't read it. ``/clear`` in particular ROTATES
    to a new session id, which Shannon reports in its ``result`` / ``shannon_session``
    rows. Return the last session id seen across the stream.
    """
    found: str | None = None
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(obj, dict):
            continue
        sid = obj.get("session_id")
        if not sid and isinstance(obj.get("message"), dict):
            sid = obj["message"].get("sessionId") or obj["message"].get("session_id")
        if sid:
            found = str(sid)
    return found


def _run_shannon_context_op(
    *,
    base_command: list[str],
    slash_command: str,
    session_id: str,
    launch_command,
    work_dir: Path,
    env: dict[str, str],
    state: PlanState,
    plan_dir: Path,
    tmux_session: TmuxSession,
) -> str | None:
    """Inject a Claude slash command (``/compact`` / ``/clear``) into a resumed session.

    Shannon pastes the ``-p`` prompt straight into Claude's interactive input and
    presses Enter (``tmux set-buffer`` → ``paste-buffer`` → ``send-keys C-m``), so
    a prompt that is exactly a slash command fires that command as if typed by a
    human. The op runs as its own turn against ``--resume <session_id>`` before the
    real work turn.

    ``/compact`` summarises in place and keeps the same session id; ``/clear``
    ROTATES to a fresh session id (and a new transcript file). The megaplan
    Shannon patch (see ``_ensure_shannon_parent_timeout_control``) teaches Shannon
    to complete the slash-command turn on the real on-disk markers instead of the
    exact prompt-echo it can never match, and to report the landed session id.

    Returns the session id the work turn should resume (the same id for compact,
    the rotated id for clear), or ``None`` if the op did not complete. Best-effort:
    any failure (timeout, non-zero exit) is logged and swallowed so the caller
    falls back to a plain resume of the original session — context hygiene must
    never fail the phase.
    """
    # Rebuild argv so the turn's ``-p`` prompt is the slash command, not the
    # original "read the prompt file" launcher prompt.
    op_command: list[str] = []
    index = 0
    while index < len(base_command):
        token = base_command[index]
        if token == "-p" and index + 1 < len(base_command):
            op_command.extend(["-p", slash_command])
            index += 2
            continue
        op_command.append(token)
        index += 1
    op_command.extend(["--resume", session_id])
    print(
        f"[megaplan] shannon session strategy: injecting {slash_command} into "
        f"resumed session {session_id} before the main turn.",
        file=sys.stderr,
        flush=True,
    )
    try:
        op_result = run_command(
            launch_command(op_command),
            cwd=work_dir,
            stdin_text=None,
            env=env,
            timeout=_shannon_context_op_timeout_seconds(),
            activity_callback=_activity_callback_for_state(state, plan_dir),
            idle_timeout=_worker_stream_idle_timeout_seconds(),
            liveness_probe=_make_shannon_liveness_probe(
                tmux_session, session_id, work_dir
            ),
            tmux_session=tmux_session,
        )
    except CliError as error:
        print(
            f"[megaplan] shannon {slash_command} turn did not complete cleanly "
            f"({error.code}); proceeding with a plain resume.",
            file=sys.stderr,
            flush=True,
        )
        return None
    landed = _stream_session_id((op_result.stdout or "") + (op_result.stderr or ""))
    if landed and landed != session_id:
        print(
            f"[megaplan] shannon {slash_command} rotated session "
            f"{session_id} -> {landed}; work turn will resume the new session.",
            file=sys.stderr,
            flush=True,
        )
    return landed or session_id


# ---------------------------------------------------------------------------
# Public worker entry-point
# ---------------------------------------------------------------------------


def _tmux_slug(text: str) -> str:
    """Sanitize *text* to tmux-safe characters (no ``.``, ``:``, whitespace)."""
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug or "plan"


def _ensure_workspace_trusted(work_dir: Path) -> None:
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
    """
    try:
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
) -> WorkerResult:
    """Run a megaplan phase via Shannon (Claude in an interactive tmux session).

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

    # Derive a deterministic, plan+step-scoped tmux session name once and
    # reuse it for env injection, TmuxSession construction, and eventual
    # reconciliation (no attempt suffix; sanitized to tmux-safe chars).
    session_name = f"megaplan-{_tmux_slug(state['name'])}-{_tmux_slug(step)}"
    tmux_session = TmuxSession(session_name)

    # ── reconcile-then-backstop ─────────────────────────────────────────
    # Reap any residual same-(plan,step) tmux session left by a prior
    # attempt (recovery path; subsumes the old dispatcher-side reap — no
    # handle threading needed). If the plan's own session survives teardown,
    # it is genuinely unkillable and must fail the step. Wrap in CliError
    # so the execute loop's CliError-only handlers produce a clean
    # failed-state write instead of a raw traceback (gate warning).
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

    # ── (b) resolve working directory and session ───────────────────────
    _ensure_shannon_parent_timeout_control()
    work_dir = resolve_work_dir(state)
    _ensure_workspace_trusted(work_dir)
    session_key = session_key_for(step, session_agent, model=model)
    session = state["sessions"].get(session_key, {})
    session_id: str | None = session.get("id")
    # The id actually persisted in state["sessions"] right now. A /clear op
    # rotates ``session_id`` to a new value mid-run, so the stall/timeout handler
    # must clear the entry whose id is EITHER the original (persisted) id OR the
    # current one — otherwise the stale leased id is never dropped.
    persisted_session_id = session_id

    # ── (c) build prompt ────────────────────────────────────────────────
    base_prompt = (
        prompt_override
        if prompt_override is not None
        else create_claude_prompt(
            step, state, plan_dir, root=root, **(prompt_kwargs or {})
        )
    )

    # ── (d) construct Shannon CLI command ───────────────────────────────
    plan_mode = state["config"].get("mode", "code")
    schema_name = (
        get_execution_schema_key(plan_mode, form=creative_form_id(state))
        if step == "execute"
        else STEP_SCHEMA_FILENAMES[step]
    )
    schema_text = json.dumps(read_json(schemas_root(root) / schema_name))
    prompt = _append_json_output_contract(
        base_prompt,
        step=step,
        schema_text=schema_text,
    )

    prompt_iteration = _prompt_file_iteration(step, state) if fresh and step != "execute" else None
    prompt_path = _write_prompt_file(plan_dir, step, prompt, iteration=prompt_iteration)
    launcher_prompt = (
        "Read the full megaplan phase prompt from this file and follow it exactly: "
        f"{prompt_path}. Your final response must satisfy the structured output "
        "contract in that file. Do not summarize the file; execute its instructions."
    )

    # Per https://github.com/dexhorthy/shannon and @dexh/shannon@0.0.2,
    # ``-p`` is the reliable path. Real megaplan prompts can exceed argv
    # limits, so the full prompt is written to a plan-local file and the
    # command-line prompt only points Claude at that file.
    base_command = [
        "shannon",
    ]
    if model is not None:
        base_command.extend(["--model", model])
    base_command.extend([
        "-p",
        launcher_prompt,
        # stream-json makes Shannon emit one JSON event per line (NDJSON) as
        # work happens (init, per-turn assistant/result, trailing metadata)
        # instead of buffering the entire turn into a single JSON array that
        # only flushes at turn end. The incremental lines reset the _impl.py
        # idle-output watchdog (last_output, _impl.py:420), giving Shannon
        # genuine liveness so a long legitimate Opus turn no longer trips the
        # SHANNON_STREAM_READ_TIMEOUT idle bound as a false worker_stall.
        # _parse_shannon_output handles both NDJSON and the legacy json array.
        "--output-format=stream-json",
    ])
    drop_root_requested = _shannon_drop_root_enabled()
    if drop_root_requested:
        # Claude's non-print interactive mode only consumes ANTHROPIC_API_KEY
        # reliably in bare mode for this cloud-root → non-root handoff. This is
        # still Shannon driving an interactive Claude tmux session, not
        # ``claude -p``.
        base_command.append("--bare")
    if effort is not None:
        base_command.extend(["--effort", effort])
    if read_only:
        base_command.extend(
            [
                "--allowedTools",
                *_SHANNON_READ_ONLY_ALLOWED_TOOLS,
                "--disallowedTools",
                *_SHANNON_READ_ONLY_DISALLOWED_TOOLS,
            ]
        )
    else:
        base_command.extend([
            "--permission-mode",
            "bypassPermissions",
            "--dangerously-skip-permissions",
            "--allow-dangerously-skip-permissions",
        ])

    # Prompt delivery. Default: the launcher prompt rides in argv (``-p``) and
    # points Claude at the on-disk prompt file. Paste-first-turn (non-root only,
    # requires the Shannon patch): deliver the REAL phase prompt over stdin as a
    # stream-json user message; Shannon launches Claude bare and pastes it as
    # turn 1, so Claude works the actual task with no argv limit and no
    # "read this file" pointer. ``main_flags`` is the main turn's argv minus the
    # ``-p`` launcher; op/repair turns keep their own small ``-p`` prompts.
    # Gate paste-first-turn on the Shannon patch actually being present: on
    # another user's machine the patch may be absent (different version,
    # read-only package dir, auto-patch off), and feeding a stdin/no-``-p`` prompt
    # to an unpatched shannon would argv-launch turn 1 and hit ARG_MAX. When the
    # patch is missing we fall back to the argv launcher.
    _is_root = hasattr(os, "geteuid") and os.geteuid() == 0
    paste_mode = (
        _shannon_paste_first_turn_enabled()
        and not _is_root
        and _shannon_supports_paste_first_turn()
    )
    if (
        _shannon_paste_first_turn_enabled()
        and not _is_root
        and not _shannon_supports_paste_first_turn()
    ):
        # Operator asked for paste-first-turn but the installed shannon lacks the
        # patch (different version / read-only package dir / auto-patch off).
        # Surface it once rather than silently using the argv launcher.
        print(
            "[megaplan] MEGAPLAN_SHANNON_PASTE_FIRST_TURN is set but the shannon "
            "paste-first-turn patch is not present; using the argv launcher. "
            "Ensure MEGAPLAN_SHANNON_AUTO_PATCH is on and the @dexh/shannon "
            "package dir is writable.",
            file=sys.stderr,
            flush=True,
        )
    main_stdin: str | None = None
    if paste_mode:
        main_flags: list[str] = []
        _i = 0
        while _i < len(base_command):
            if base_command[_i] == "-p" and _i + 1 < len(base_command):
                _i += 2
                continue
            main_flags.append(base_command[_i])
            _i += 1
        main_flags.append("--input-format=stream-json")
        main_stdin = json.dumps(
            {"type": "user", "message": {"role": "user", "content": prompt}}
        )
    else:
        main_flags = list(base_command)

    # Roll a session-continuity strategy (resume / compact / clear / new). Only
    # execute carries a genuine refresh signal in ``fresh``; for every other
    # phase ``fresh`` is the blanket force-fresh policy (set above), not user
    # intent, so we pass explicit_fresh=False there and let the roll decide.
    strategy = _select_session_strategy(
        step,
        has_session=bool(session_id),
        explicit_fresh=fresh if step == "execute" else False,
        slash_supported=_shannon_supports_slash_completion(),
    )
    new_session = strategy == "new"
    if new_session:
        session_id = str(uuid.uuid4())
        command = [*main_flags, "--session-id", session_id]
    else:
        # Resume the stored session by id. The downstream Claude CLI reloads the
        # persisted conversation in a fresh tmux pane (the prior pane was already
        # torn down above), so resume rides on the session id, not pane liveness.
        command = [*main_flags, "--resume", session_id]
    print(
        f"[megaplan] shannon session strategy for {step}: {strategy} "
        f"(session {session_id}).",
        file=sys.stderr,
        flush=True,
    )

    # ── (e) execute with timeout / activity callback ────────────────────
    started = time.monotonic()
    env = _external_worker_env(turn_id=f'plan_worker_{state["name"]}')
    env["SHANNON_TMUX_SESSION_NAME"] = session_name
    if paste_mode:
        # Activate the Shannon paste-first-turn patch for these invocations so the
        # bare-launched Claude receives the prompt as a pasted turn 1 (the main
        # turn over stdin; readiness/op turns paste their small ``-p`` prompts).
        env["MEGAPLAN_SHANNON_PASTE_FIRST_TURN"] = "1"
        # Bare launch has a startup race: Shannon's waitForPrompt returns as soon
        # as the pane shows "❯"/">", which Claude's welcome banner prints BEFORE
        # the input box is ready, so the turn-1 paste can land before Claude
        # accepts input and get dropped (observed: empty output, op times out).
        # Nudge a couple of delayed Enters during startup to settle past the
        # banner. Tunable; overridable by the operator's own values.
        env.setdefault("MEGAPLAN_SHANNON_BOOTSTRAP_ENTER_COUNT", "2")
        env.setdefault("MEGAPLAN_SHANNON_BOOTSTRAP_ENTER_DELAY_MS", "2500")
    # Shannon normally drives an interactive Claude Code session. Do not let an
    # inherited API key force local interactive Claude into its first-run "use
    # this key?" prompt. Root cloud workers are different: the Shannon package
    # is auto-patched to launch Claude in print mode under root, and that path
    # needs ANTHROPIC_API_KEY for non-interactive auth.
    if not (hasattr(os, "geteuid") and os.geteuid() == 0):
        # Setting to empty (rather than popping) defeats Bun's dotenv auto-load
        # in shannon's launcher: Bun's loader skips vars that are already set,
        # so an empty value blocks re-injection from a project-local .env file.
        # Claude Code treats empty as no key and falls back to OAuth credentials.
        # See megaplan ticket 01KRXNZZGRV17PHZRJ2Q56SPS3.
        env["ANTHROPIC_API_KEY"] = ""
    # Megaplan owns phase timeout/staleness policy. Shannon's packaged
    # 180s turn timeout is too short for normal critique/finalize/execute
    # phases, so keep Shannon's internal watchdog above megaplan's worker
    # budget and let the parent process decide when to stop waiting.
    env.setdefault("SHANNON_TURN_TIMEOUT_MS", "7200000")
    # Raise the Claude CLI output-token ceiling so opus-class models are not cut
    # off at the inherited ~64k default mid-run, before emitting the structured
    # result envelope. megaplan, not the model default, owns this budget.
    env.setdefault("CLAUDE_CODE_MAX_OUTPUT_TOKENS", str(_shannon_max_output_tokens()))
    # Raise the Claude CLI's per-command Bash-tool timeout. Its built-in 120s
    # default (BASH_DEFAULT_TIMEOUT_MS) SIGKILLs legitimate long-running execute
    # commands (full test suites, builds) mid-run; megaplan's 7200s execute cap +
    # 900s stall watchdog already own the stop-policy. Set both the default and
    # the max so the model cannot be capped below this even if it requests more.
    bash_timeout_ms = str(_shannon_bash_timeout_ms())
    env.setdefault("BASH_DEFAULT_TIMEOUT_MS", bash_timeout_ms)
    env.setdefault("BASH_MAX_TIMEOUT_MS", bash_timeout_ms)
    shannon_prefix, env = _prepare_nonroot_shannon_runtime(work_dir, env)

    def _launch_command(shannon_command: list[str]) -> list[str]:
        if not shannon_prefix:
            return shannon_command
        return [*shannon_prefix, _shell_join_command(shannon_command, work_dir)]

    if (
        new_session
        and _shannon_readiness_probe_enabled(session_agent)
        and (_shannon_readiness_probe_forced() or _shannon_should_send_handshake())
    ):
        readiness_prompt = _shannon_random_handshake_prompt()
        readiness_command = [
            "shannon",
        ]
        if model is not None:
            readiness_command.extend(["--model", model])
        readiness_command.extend([
            "-p",
            readiness_prompt,
            # Match the main run: stream-json gives the readiness probe the same
            # incremental-liveness behaviour. Its output is only checked for
            # non-emptiness (not parsed for a structured payload), so the shape
            # change is inert here beyond liveness.
            "--output-format=stream-json",
        ])
        if effort is not None:
            readiness_command.extend(["--effort", effort])
        if drop_root_requested:
            readiness_command.append("--bare")
        if read_only:
            readiness_command.extend(
                [
                    "--allowedTools",
                    *_SHANNON_READ_ONLY_ALLOWED_TOOLS,
                    "--disallowedTools",
                    *_SHANNON_READ_ONLY_DISALLOWED_TOOLS,
                ]
            )
        else:
            readiness_command.extend(
                [
                    "--permission-mode",
                    "bypassPermissions",
                    "--dangerously-skip-permissions",
                    "--allow-dangerously-skip-permissions",
                ]
            )
        readiness_command.extend(["--session-id", session_id])
        # Both the readiness-probe and the main run_command below share the
        # same tmux_session (deterministic session_name from above). They are
        # serialized by run_command's finally block (probe returns →
        # teardown → main launches), so they must not be parallelized (gate
        # warning). The shared env/SHANNON_TMUX_SESSION_NAME ensures both
        # resolve to the same tmux session.
        time.sleep(_shannon_random_handshake_delay_seconds())
        try:
            readiness = run_command(
                _launch_command(readiness_command),
                cwd=work_dir,
                stdin_text=None,
                env=env,
                timeout=_shannon_readiness_timeout_seconds(),
                activity_callback=_activity_callback_for_state(state, plan_dir),
                idle_timeout=_worker_stream_idle_timeout_seconds(),
                liveness_probe=_make_shannon_liveness_probe(
                    tmux_session, session_id, work_dir
                ),
                tmux_session=tmux_session,
            )
        except CliError as error:
            if error.code == "worker_timeout":
                error.extra["session_id"] = session_id
            raise
        if readiness.returncode != 0:
            raise CliError(
                "worker_error",
                f"Shannon readiness probe failed with exit code {readiness.returncode}",
                extra={
                    "raw_output": (readiness.stdout or "") + (readiness.stderr or ""),
                    "session_id": session_id,
                },
            )
        if not ((readiness.stdout or "") + (readiness.stderr or "")).strip():
            raise CliError(
                "worker_error",
                "Shannon readiness probe returned no output",
                extra={"raw_output": "", "session_id": session_id},
            )
        time.sleep(_shannon_random_handshake_delay_seconds())
        command = [*main_flags, "--resume", session_id]
    if strategy in ("compact", "clear") and not new_session:
        # Human-like pacing: pause a randomized beat before touching the session
        # so it isn't compacted/cleared the instant it's picked up.
        time.sleep(_shannon_context_op_delay_seconds())
        # Trim the resumed context before the real work turn. Best-effort: on any
        # failure we keep ``command`` as the plain resume and carry on. ``/clear``
        # rotates to a new session id, so resume whatever the op landed on.
        op_session_id = _run_shannon_context_op(
            base_command=base_command,
            slash_command="/compact" if strategy == "compact" else "/clear",
            session_id=session_id,
            launch_command=_launch_command,
            work_dir=work_dir,
            env=env,
            state=state,
            plan_dir=plan_dir,
            tmux_session=tmux_session,
        )
        if op_session_id:
            # op completed (compact: same id; clear: rotated id) — resume it.
            if op_session_id != session_id:
                session_id = op_session_id
                command = [*main_flags, "--resume", session_id]
        else:
            # op FAILED (timeout / non-zero). The policy is "never carry stale
            # context", so do NOT fall back to plain-resuming the original
            # (un-shed) session — shed it the safe way with a fresh session.
            new_session = True
            session_id = str(uuid.uuid4())
            command = [*main_flags, "--session-id", session_id]
            print(
                f"[megaplan] shannon context-op did not complete; starting a "
                f"fresh session {session_id} instead of resuming stale context.",
                file=sys.stderr,
                flush=True,
            )
    try:
        result = run_command(
            _launch_command(command),
            cwd=work_dir,
            stdin_text=main_stdin,
            env=env,
            timeout=_shannon_execute_timeout_seconds(),
            activity_callback=_activity_callback_for_state(state, plan_dir),
            idle_timeout=_worker_stream_idle_timeout_seconds(),
            liveness_probe=_make_shannon_liveness_probe(
                tmux_session, session_id, work_dir
            ),
            tmux_session=tmux_session,
        )
    except CliError as error:
        # (j) timeout / idle-output stall → enrich with session_id so the
        # downstream CLI can resume the tmux pane / retry the session.
        if error.code in ("worker_timeout", "worker_stall"):
            error.extra["session_id"] = session_id
            # Invalidate the persisted shannon session-id on a stall/timeout.
            # The worker subprocess has just been killed (group SIGTERM/KILL in
            # run_command) but a setsid-on-its-own grandchild — or one that
            # escaped the kill window — may still be holding this session_id
            # via the persistent ``--resume <sid>`` lease in the Claude CLI /
            # tmux pane. If we leave the id in state, the NEXT megaplan
            # executor cycle will read state.json and pass ``--resume <sid>``
            # again, racing the orphan for the same session. Drop the persisted
            # id here so the next attempt spawns with a fresh ``--session-id``.
            try:
                sessions = state.get("sessions")
                if isinstance(sessions, dict):
                    entry = sessions.get(session_key)
                    # Dual-compare: a /clear op rotates ``session_id`` mid-run, so
                    # the persisted entry still holds the ORIGINAL id. Drop it if
                    # it matches either, else the stale leased id is never cleared
                    # and the next cycle races an orphan on ``--resume``.
                    entry_id = entry.get("id") if isinstance(entry, dict) else None
                    if entry_id is not None and entry_id in {session_id, persisted_session_id}:
                        sessions.pop(session_key, None)
                        print(
                            f"[megaplan] Cleared persisted shannon session "
                            f"{session_key}={entry_id} after {error.code}; "
                            "next attempt will start a fresh session.",
                            file=sys.stderr,
                            flush=True,
                        )
            except Exception:
                # Best-effort cleanup; never let it mask the original CliError.
                pass
        raise

    raw = result.stdout or result.stderr
    elapsed_ms = int((time.monotonic() - started) * 1000)

    # ── (f) parse Shannon output ────────────────────────────────────────
    # On a heavy ``execute`` batch the model can still exhaust its output
    # budget on reasoning/content before emitting the structured envelope and
    # get cut off at ``max_tokens`` (empty/invalid JSON or missing required
    # keys). The work itself (edits, commands) has already happened in the
    # session, so a single resume turn that asks for *only* the envelope is far
    # cheaper than re-running the whole batch — and the surrounding execute loop
    # deliberately does not retry execute. Attempt that repair in-place once.
    def _parse_and_validate(raw_text: str) -> tuple[dict[str, Any], dict[str, Any]]:
        env_, pay_ = _parse_shannon_output(raw_text)
        pay_ = _apply_file_fallback(step, pay_, plan_dir)
        pay_ = _normalize_worker_payload(step, pay_)
        validate_payload(step, pay_)
        return env_, pay_

    try:
        envelope, payload = _parse_and_validate(raw)
    except CliError as error:
        repaired = None
        if step == "execute" and error.code in {"parse_error", "schema_error"}:
            repaired = _repair_execute_envelope(
                base_command=base_command,
                # The work turn runs under --output-format=stream-json (NDJSON),
                # which _envelope_session_id (single json.loads) can't parse — try
                # the NDJSON-aware extractor first, then the legacy-array one, then
                # the (possibly rotated) session_id the work turn actually ran under.
                session_id=str(
                    _stream_session_id(raw)
                    or _envelope_session_id(raw)
                    or session_id
                ),
                launch_command=_launch_command,
                work_dir=work_dir,
                env=env,
                state=state,
                plan_dir=plan_dir,
                tmux_session=tmux_session,
            )
        if repaired is None:
            raise CliError(error.code, error.message, extra={"raw_output": raw}) from error
        try:
            envelope, payload = _parse_and_validate(repaired)
        except CliError as repair_error:
            raise CliError(
                repair_error.code,
                f"{repair_error.message} (after structured-envelope repair attempt)",
                extra={"raw_output": repaired, "original_raw_output": raw},
            ) from repair_error
        raw = repaired

    return WorkerResult(
        payload=payload,
        raw_output=raw,
        duration_ms=result.duration_ms,
        cost_usd=float(envelope.get("total_cost_usd", 0.0) or 0.0),
        session_id=str(envelope.get("session_id") or session_id),
        rendered_prompt=prompt,
        prompt_tokens=_extract_claude_usage(envelope)[0],
        completion_tokens=_extract_claude_usage(envelope)[1],
        total_tokens=sum(_extract_claude_usage(envelope)),
    )
