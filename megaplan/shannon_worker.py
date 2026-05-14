"""Shannon worker — opt-in Claude launcher via interactive tmux sessions.

Shannon (https://github.com/dexhorthy/shannon) runs real Claude Code in tmux,
sends prompts, and tails the Claude transcript JSONL instead of using
``claude -p``.  This module provides ``run_shannon_step``, a drop-in launcher
that preserves the same WorkerResult contract, schema validation, session
tracking, timeouts, error handling, and receipts as the native Claude path.
"""

from __future__ import annotations

import json
import os
import random
import re
import shutil
import time
import uuid
from pathlib import Path
from typing import Any

from megaplan.types import CliError, MOCK_ENV_VAR, PlanState
from megaplan._core import creative_form_id, json_dump, read_json, schemas_root
from megaplan.prompts import create_claude_prompt
from megaplan.schemas import get_execution_schema_key
from megaplan.workers import (
    STEP_SCHEMA_FILENAMES,
    WorkerResult,
    _activity_callback_for_state,
    _extract_claude_usage,
    _external_worker_env,
    _normalize_worker_payload,
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
    configured = _env_truthy("MEGAPLAN_SHANNON_READINESS_PROBE")
    if configured is not None:
        return configured
    if session_agent == "claude":
        return True
    # Cloud workers set trusted-container mode. Keep local Shannon runs as a
    # single turn unless explicitly opted in, because the probe adds latency.
    return _env_truthy("MEGAPLAN_TRUSTED_CONTAINER") is True


def _shannon_readiness_timeout_seconds() -> int:
    raw = os.getenv("MEGAPLAN_SHANNON_READINESS_TIMEOUT_SECONDS", "").strip()
    if not raw:
        return 120
    try:
        return max(1, int(raw))
    except ValueError:
        return 120


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
        + "SHANNON STRUCTURED OUTPUT CONTRACT:\n"
        + f"- This megaplan phase is `{step}`.\n"
        + "- Your final answer MUST be exactly one valid JSON object and nothing else.\n"
        + "- Do not wrap the JSON in markdown fences. Do not include prose before or after it.\n"
        + "- The JSON object MUST conform to this schema. If a field is markdown, put the markdown as a JSON string value.\n"
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


def _write_prompt_file(plan_dir: Path, step: str, prompt: str) -> Path:
    prompt_path = plan_dir / f"{step}_shannon_prompt.txt"
    prompt_path.write_text(prompt, encoding="utf-8")
    return prompt_path


def _shannon_package_entrypoint() -> Path | None:
    executable = shutil.which("shannon")
    if not executable:
        return None
    bin_path = Path(executable).resolve()
    candidate = bin_path.parent.parent / "index.ts"
    return candidate if candidate.is_file() else None


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

    if patched == original:
        return

    backup = entrypoint.with_suffix(entrypoint.suffix + ".bak.megaplan-shannon")
    try:
        if not backup.exists():
            backup.write_text(original, encoding="utf-8")
        entrypoint.write_text(patched, encoding="utf-8")
    except OSError:
        return


# ---------------------------------------------------------------------------
# Shannon output parsing
# ---------------------------------------------------------------------------


def _parse_shannon_output(raw: str) -> tuple[dict[str, Any], dict[str, Any]]:
    """Parse Shannon CLI JSON output into ``(envelope, payload)``.

    Shannon with ``--output-format=json`` emits a JSON array of transcript
    messages. We walk the array in reverse, preferring the trailing
    ``type=result`` event produced by ``@dexh/shannon@0.0.2`` and then falling
    back to assistant messages that carry ``structured_output`` or JSON text.
    If the top-level value is already a dict we hand it back directly
    (compatible with :func:`~megaplan.workers.parse_claude_envelope`'s expected
    input shape).
    """
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
                    raise CliError(
                        "parse_error",
                        f"Shannon result payload was not valid JSON: {exc}",
                        extra={"raw_output": raw},
                    ) from exc
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
                try:
                    result_val = json.loads(result_val)
                except json.JSONDecodeError:
                    continue
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
                        continue
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
                            pass
            elif isinstance(content, str):
                try:
                    parsed = json.loads(content)
                    if isinstance(parsed, dict):
                        return inner, parsed
                except json.JSONDecodeError:
                    pass

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


# ---------------------------------------------------------------------------
# Public worker entry-point
# ---------------------------------------------------------------------------


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
) -> WorkerResult:
    """Run a megaplan phase via Shannon (Claude in an interactive tmux session).

    Parameters match :func:`~megaplan.workers.run_claude_step` so the
    ``run_step_with_worker`` dispatch can call them interchangeably.
    """
    # ── (a) mock worker shortcut ────────────────────────────────────────
    if os.getenv(MOCK_ENV_VAR) == "1":
        return mock_worker_output(
            step, state, plan_dir,
            prompt_override=prompt_override,
            prompt_kwargs=prompt_kwargs,
        )

    # ── (b) resolve working directory and session ───────────────────────
    _ensure_shannon_parent_timeout_control()
    work_dir = resolve_work_dir(state)
    session_key = session_key_for(step, session_agent)
    session = state["sessions"].get(session_key, {})
    session_id: str | None = session.get("id")

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

    prompt_path = _write_prompt_file(plan_dir, step, prompt)
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
        "-p",
        launcher_prompt,
        "--output-format=json",
    ]
    if effort is not None:
        base_command.extend(["--effort", effort])
    base_command.extend([
        "--permission-mode",
        "bypassPermissions",
        "--dangerously-skip-permissions",
        "--allow-dangerously-skip-permissions",
    ])

    new_session = not (session_id and not fresh)
    if session_id and not fresh:
        # Shannon sessions are tmux-scoped; pass the session_id so the
        # downstream CLI can resume the tmux pane if supported.
        command = [*base_command, "--resume", session_id]
    else:
        session_id = str(uuid.uuid4())
        command = [*base_command, "--session-id", session_id]

    # ── (e) execute with timeout / activity callback ────────────────────
    started = time.monotonic()
    env = _external_worker_env(turn_id=f'plan_worker_{state["name"]}')
    # Shannon intentionally drives an interactive Claude Code session. Do not
    # let an inherited API key force Claude Code into its first-run "use this
    # key?" prompt; megaplan's Claude route should use the user's Claude Code
    # login/session state instead.
    env.pop("ANTHROPIC_API_KEY", None)
    # Megaplan owns phase timeout/staleness policy. Shannon's packaged
    # 180s turn timeout is too short for normal critique/finalize/execute
    # phases, so keep Shannon's internal watchdog above megaplan's worker
    # budget and let the parent process decide when to stop waiting.
    env.setdefault("SHANNON_TURN_TIMEOUT_MS", "7200000")
    if (
        new_session
        and _shannon_readiness_probe_enabled(session_agent)
        and _shannon_should_send_handshake()
    ):
        readiness_prompt = _shannon_random_handshake_prompt()
        readiness_command = [
            "shannon",
            "-p",
            readiness_prompt,
            "--output-format=json",
        ]
        if effort is not None:
            readiness_command.extend(["--effort", effort])
        readiness_command.extend(
            [
                "--permission-mode",
                "bypassPermissions",
                "--dangerously-skip-permissions",
                "--allow-dangerously-skip-permissions",
                "--session-id",
                session_id,
            ]
        )
        time.sleep(_shannon_random_handshake_delay_seconds())
        try:
            readiness = run_command(
                readiness_command,
                cwd=work_dir,
                stdin_text=None,
                env=env,
                timeout=_shannon_readiness_timeout_seconds(),
                activity_callback=_activity_callback_for_state(state, plan_dir),
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
        command = [*base_command, "--resume", session_id]
    try:
        result = run_command(
            command,
            cwd=work_dir,
            stdin_text=None,
            env=env,
            activity_callback=_activity_callback_for_state(state, plan_dir),
        )
    except CliError as error:
        # (j) timeout → enrich with session_id
        if error.code == "worker_timeout":
            error.extra["session_id"] = session_id
        raise

    raw = result.stdout or result.stderr
    elapsed_ms = int((time.monotonic() - started) * 1000)

    # ── (f) parse Shannon output ────────────────────────────────────────
    envelope, payload = _parse_shannon_output(raw)

    # ── (g) normalize + validate ────────────────────────────────────────
    payload = _normalize_worker_payload(step, payload)
    try:
        validate_payload(step, payload)
    except CliError as error:
        raise CliError(
            error.code, error.message, extra={"raw_output": raw}
        ) from error

    # ── (h) extract token usage ─────────────────────────────────────────
    prompt_tokens, completion_tokens = _extract_claude_usage(envelope)

    # ── (i) construct WorkerResult ──────────────────────────────────────
    return WorkerResult(
        payload=payload,
        raw_output=raw,
        duration_ms=result.duration_ms,
        cost_usd=float(envelope.get("total_cost_usd", 0.0) or 0.0),
        session_id=str(envelope.get("session_id") or session_id),
        rendered_prompt=prompt,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=prompt_tokens + completion_tokens,
    )
