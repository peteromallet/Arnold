"""Claude worker — native ``claude --print`` as the only Claude path.

Replaces the legacy tmux/stream shannon machinery entirely: this worker
launches the installed Claude Code CLI in print mode (one-shot, prompt via
argv — no stdin-wiring pitfalls), parses the phase JSON payload from the final
text, and returns the same WorkerResult contract as the omp/codex workers.

Signature mirrors the other workers so ``run_step_with_worker`` dispatches
``claude`` (and the deprecated ``shannon`` alias) here directly.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any, Mapping

from arnold_pipelines.megaplan.types import CliError

_CLAUDE_CHANNEL = "claude_cli"
# Phase wall-clock budgets, matching the codex/omp workers.
_CLAUDE_TIMEOUT_BY_STEP = {
    "execute": 7200,
    "plan": 1800,
    "revise": 1800,
    "review": 1800,
}
_CLAUDE_DEFAULT_TIMEOUT = 900
_VALID_CLAUDE_EFFORTS = frozenset({"minimal", "low", "medium", "high", "xhigh", "max"})


def _timeout_for_step(step: str) -> int:
    return _CLAUDE_TIMEOUT_BY_STEP.get(step, _CLAUDE_DEFAULT_TIMEOUT)


def _render_prompt(
    step: str,
    state: Any,
    plan_dir: Path,
    *,
    root: Path,
    prompt_override: str | None,
    prompt_kwargs: dict[str, Any] | None,
) -> str:
    from arnold_pipelines.megaplan.prompts import create_claude_prompt

    if prompt_override:
        return prompt_override
    return create_claude_prompt(step, state, plan_dir, root=root, **(prompt_kwargs or {}))


def _build_command(
    *,
    model: str,
    effort: str | None,
) -> list[str]:
    cmd = [
        "claude",
        "--print",
        "--input-format",
        "text",
        "--output-format",
        "text",
        "--model",
        model,
        "--permission-mode",
        "bypassPermissions",
    ]
    if effort is not None and effort in _VALID_CLAUDE_EFFORTS:
        cmd += ["--effort", effort]
    return cmd


def _parse_payload(raw: str, step: str) -> dict[str, Any]:
    """Extract the exact phase JSON object from the model's final text."""
    from arnold_pipelines.megaplan.workers._payload import (
        _deescape_double_encoded_json,
        _extract_json_from_mutating_tool_markup,
    )

    text = raw.strip()
    # Some models wrap the JSON in fenced blocks; strip a single fence layer.
    if text.startswith("```"):
        text = text.strip("`")
        text = text.strip()
        if text.startswith("json"):
            text = text[4:].strip()
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        deescaped = _deescape_double_encoded_json(text)
        if deescaped is not None:
            try:
                payload = json.loads(deescaped)
            except json.JSONDecodeError:
                payload = None
        else:
            payload = None
    if payload is None:
        recovered = _extract_json_from_mutating_tool_markup(text)
        if recovered is not None:
            try:
                payload = json.loads(recovered)
            except json.JSONDecodeError:
                payload = None
    if not isinstance(payload, Mapping):
        raise CliError(
            "parse_error",
            f"claude output for step '{step}' is not a single exact JSON "
            f"object (prose, markdown fences, or truncation)",
            extra={"raw_output": raw},
        )
    return dict(payload)


def run_claude_step(
    step: str,
    state: Any,
    plan_dir: Path,
    *,
    root: Path,
    fresh: bool = True,
    model: str | None = None,
    effort: str | None = None,
    prompt_override: str | None = None,
    prompt_kwargs: dict[str, Any] | None = None,
    read_only: bool = False,
    output_path: Path | None = None,
) -> Any:
    """Run one megaplan phase through native ``claude --print``."""
    from arnold_pipelines.megaplan.workers._impl import WorkerResult

    resolved_model = model or "claude-sonnet-4-6"
    if shutil.which("claude") is None:
        raise CliError(
            "launch_failure",
            "claude CLI not found on PATH; install Claude Code to use the "
            "claude worker",
        )

    prompt = _render_prompt(
        step, state, plan_dir, root=root,
        prompt_override=prompt_override, prompt_kwargs=prompt_kwargs,
    )
    if not prompt.strip():
        raise CliError("invalid_args", f"empty prompt for claude step '{step}'")

    timeout_seconds = _timeout_for_step(step)
    cmd = _build_command(model=resolved_model, effort=effort)
    started = time.monotonic()
    try:
        completed = subprocess.run(
            cmd + [prompt],
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired as exc:
        raise CliError(
            "worker_timeout",
            f"claude worker exceeded --timeout={timeout_seconds}s for step '{step}'",
        ) from exc
    duration_ms = int((time.monotonic() - started) * 1000)

    if completed.returncode != 0:
        raise CliError(
            "worker_error",
            f"claude --print exited {completed.returncode} for step '{step}': "
            f"{(completed.stderr or '').strip()[-500:] or 'no stderr'}",
        )

    raw = (completed.stdout or "").strip()
    if not raw:
        raise CliError(
            "worker_parse_error",
            f"claude worker produced no output for step '{step}'",
        )

    payload = _parse_payload(raw, step)
    return WorkerResult(
        payload=payload,
        raw_output=raw,
        duration_ms=duration_ms,
        cost_usd=0.0,
        model_actual=resolved_model,
        model_evidence=_CLAUDE_CHANNEL,
        worker_channel=_CLAUDE_CHANNEL,
        auth_channel="claude_cli",
        cost_pricing=None,
        session_id=None,
    )
