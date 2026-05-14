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
    command = [
        "shannon",
        "-p",
        launcher_prompt,
        "--output-format=json",
    ]
    if effort is not None:
        command.extend(["--effort", effort])
    command.extend([
        "--permission-mode",
        "bypassPermissions",
        "--dangerously-skip-permissions",
        "--allow-dangerously-skip-permissions",
    ])

    if session_id and not fresh:
        # Shannon sessions are tmux-scoped; we pass the session_id so the
        # downstream CLI can resume the tmux pane if supported.
        command.extend(["--resume", session_id])
    else:
        session_id = str(uuid.uuid4())
        command.extend(["--session-id", session_id])

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
