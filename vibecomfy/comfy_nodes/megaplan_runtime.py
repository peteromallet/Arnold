"""Megaplan/Arnold runtime adapter for the VibeComfy agent-edit loop.

VibeComfy's ``agent_provider._load_arnold_runtime`` discovers a runtime module
that exposes ``run_agent_turn(...)`` and (optionally) ``get_agent_status(...)``.
The shipped megaplan/arnold harness (``pip install`` of
https://github.com/peteromallet/arnold, importable as the ``megaplan`` package)
does not expose those exact entry points -- its agent backend is the
``megaplan.agent.run_agent.AIAgent`` class. This module is the small adapter the
runbook calls for: it drives ``AIAgent`` for a single, tool-free completion and
returns VibeComfy's agent-edit contracts.

Wire it up by pointing the discovery env var at this module::

    export VIBECOMFY_ARNOLD_RUNTIME_MODULE="vibecomfy.comfy_nodes.megaplan_runtime"

Routes
------
* ``deepseek``  -> DeepSeek direct (``https://api.deepseek.com``), key resolved
  from ``DEEPSEEK_API_KEY`` or ``~/.hermes/.env`` (where the browser
  credential route writes it). This is the canonical browser-key route.
* ``arnold`` (also ``auto`` / ``anthropic`` / ``openai-codex`` after VibeComfy
  normalises them) -> AIAgent's own provider resolution (Claude via OpenRouter
  or local OAuth). Honest about availability: status reports ``ok`` only when a
  usable credential resolves.

Everything heavy (provider routing, retries, OAuth resolution) is handled by the
real ``AIAgent`` backend; this file is intentionally thin.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Mapping, Sequence

# How long to wait for a single agent turn (subprocess) before giving up.
_TURN_TIMEOUT_SECONDS = float(os.getenv("VIBECOMFY_AGENT_TURN_TIMEOUT", "180"))
_WORKER_PATH = str(Path(__file__).with_name("megaplan_worker.py"))

# DeepSeek direct endpoint defaults (OpenAI-compatible chat-completions).
_DEEPSEEK_BASE_URL = os.getenv("VIBECOMFY_DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")
_DEEPSEEK_MODEL = os.getenv("VIBECOMFY_DEEPSEEK_MODEL", "deepseek-chat")

# Arnold/Hermes (Claude etc.) default model when a non-DeepSeek route is used.
_ARNOLD_MODEL = os.getenv("VIBECOMFY_ARNOLD_MODEL", "anthropic/claude-opus-4.6")
_ARNOLD_BASE_URL = os.getenv("VIBECOMFY_ARNOLD_BASE_URL") or None

_HERMES_ENV_PATH = Path("~/.hermes/.env").expanduser()


def _load_env_file_into_environ(path: Path = _HERMES_ENV_PATH) -> None:
    """Best-effort: hydrate os.environ from ~/.hermes/.env without overwriting.

    The browser credential route writes ``DEEPSEEK_API_KEY=...`` here, so a
    ComfyUI process started without the key in its environment still picks it up.
    """
    try:
        text = path.read_text(encoding="utf-8")
    except (FileNotFoundError, OSError):
        return
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


# Hydrate on import so credential presence + provider calls see the stored key.
_load_env_file_into_environ()


def _resolve_deepseek_key() -> str | None:
    # Re-read the env file each call so a freshly browser-submitted key is seen
    # without restarting the server.
    if not os.getenv("DEEPSEEK_API_KEY"):
        _load_env_file_into_environ()
    return os.getenv("DEEPSEEK_API_KEY")


def _split_messages(messages: Sequence[Mapping[str, Any]] | None) -> tuple[str | None, str | None]:
    """Return (system_message, user_message) from VibeComfy's built messages."""
    system_msg: str | None = None
    user_msg: str | None = None
    for entry in messages or []:
        role = entry.get("role")
        content = entry.get("content")
        if not isinstance(content, str):
            continue
        if role == "system" and system_msg is None:
            system_msg = content
        elif role == "user":
            user_msg = content
    return system_msg, user_msg


def _build_agent_kwargs(route: str) -> dict[str, Any]:
    """AIAgent constructor kwargs for a single, tool-free completion."""
    common: dict[str, Any] = dict(
        max_iterations=1,
        enabled_toolsets=[],          # no tools: one-shot completion
        save_trajectories=False,      # no trajectory files on disk
        skip_context_files=True,      # don't load SOUL.md / AGENTS.md
        skip_memory=True,             # don't load/write the memory store
        quiet_mode=True,
    )
    if route == "deepseek":
        return dict(
            model=_DEEPSEEK_MODEL,
            api_key=_resolve_deepseek_key(),
            base_url=_DEEPSEEK_BASE_URL,
            provider="deepseek",
            **common,
        )
    # arnold / auto / anthropic / openai-codex -> let AIAgent resolve creds.
    return dict(model=_ARNOLD_MODEL, base_url=_ARNOLD_BASE_URL, **common)


def _run_worker(
    agent_kwargs: dict[str, Any],
    system_msg: str | None,
    user_msg: str,
    *,
    response_contract: str = "python",
) -> dict[str, Any]:
    """Run one AIAgent turn in an isolated subprocess; return its result dict.

    Isolation avoids the top-level module-name collision between megaplan's
    agent (bare ``import utils`` / ``model_tools``) and ComfyUI's own ``utils``
    package, and keeps the agent's asyncio/HTTP state out of ComfyUI's loop.
    """
    with tempfile.TemporaryDirectory(prefix="vibecomfy-agent-") as tmp:
        req_path = os.path.join(tmp, "request.json")
        res_path = os.path.join(tmp, "result.json")
        with open(req_path, "w", encoding="utf-8") as fh:
            json.dump(
                {
                    "agent_kwargs": agent_kwargs,
                    "system_message": system_msg,
                    "user_message": user_msg,
                    "response_contract": response_contract,
                },
                fh,
            )
        env = dict(os.environ)
        # Ensure the child can see the DeepSeek key even if only ~/.hermes/.env had it.
        key = _resolve_deepseek_key()
        if key:
            env["DEEPSEEK_API_KEY"] = key
        # Don't leak ComfyUI's cwd/path into the child (it is what causes the
        # `utils` collision); run from a neutral directory.
        proc = subprocess.run(
            [sys.executable, _WORKER_PATH, req_path, res_path],
            cwd=tmp,
            env=env,
            capture_output=True,
            text=True,
            timeout=_TURN_TIMEOUT_SECONDS,
        )
        try:
            with open(res_path, encoding="utf-8") as fh:
                return json.load(fh)
        except (FileNotFoundError, json.JSONDecodeError) as exc:
            tail = (proc.stderr or proc.stdout or "")[-800:]
            raise RuntimeError(
                f"Agent worker produced no result (exit {proc.returncode}). {exc}. "
                f"Worker output tail:\n{tail}"
            ) from exc


def run_agent_turn(
    *,
    task: str,
    python_source: str,
    route: str,
    model: str | None = None,
    messages: Sequence[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Run one agent-edit turn through the megaplan AIAgent backend.

    Returns ``{"python": <str>, "message": <str>}`` as VibeComfy expects.
    """
    normalized = (route or "arnold").strip().lower()
    system_msg, user_msg = _split_messages(messages)
    if user_msg is None:
        # Fall back to reconstructing the user message from the raw inputs.
        user_msg = (
            f"User request:\n{task}\n\n"
            "Current scratchpad Python:\n```python\n" + (python_source or "") + "\n```"
        )

    if normalized == "deepseek" and not _resolve_deepseek_key():
        raise PermissionError(
            "DeepSeek route selected but no DEEPSEEK_API_KEY is available "
            "(checked environment and ~/.hermes/.env). Submit a key via the "
            "VibeComfy panel or export DEEPSEEK_API_KEY."
        )

    agent_kwargs = _build_agent_kwargs(normalized)
    result = _run_worker(agent_kwargs, system_msg, user_msg, response_contract="python")
    if "error" in result:
        # Surface auth-style failures as PermissionError so VibeComfy classifies
        # them as auth errors; everything else stays a provider error.
        err = result.get("error", "agent worker failed")
        if result.get("error_type") in {"AuthError", "AuthenticationError", "PermissionError"}:
            raise PermissionError(err)
        raise RuntimeError(err)
    return {"python": result["python"], "message": result["message"]}


def run_agent_turn_delta(
    *,
    task: str,
    projection: str,
    op_schema: Mapping[str, Any],
    route: str,
    model: str | None = None,
    messages: Sequence[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Run one v2 agent-edit turn and return ``{"delta": [...], "message": str}``."""
    normalized = (route or "arnold").strip().lower()
    system_msg, user_msg = _split_messages(messages)
    if user_msg is None:
        user_msg = (
            f"User request:\n{task}\n\n"
            "Address-preserving UI projection:\n"
            f"{projection}"
        )

    if normalized == "deepseek" and not _resolve_deepseek_key():
        raise PermissionError(
            "DeepSeek route selected but no DEEPSEEK_API_KEY is available "
            "(checked environment and ~/.hermes/.env). Submit a key via the "
            "VibeComfy panel or export DEEPSEEK_API_KEY."
        )

    agent_kwargs = _build_agent_kwargs(normalized)
    result = _run_worker(agent_kwargs, system_msg, user_msg, response_contract="delta")
    if "error" in result:
        err = result.get("error", "agent worker failed")
        if result.get("error_type") in {"AuthError", "AuthenticationError", "PermissionError"}:
            raise PermissionError(err)
        raise RuntimeError(err)
    return {"delta": result["delta"], "message": result["message"]}


def run_agent_turn_batch(
    *,
    task: str,
    route: str,
    model: str | None = None,
    messages: Sequence[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Run one batch-REPL agent-edit turn and return raw model content."""
    normalized = (route or "arnold").strip().lower()
    system_msg, user_msg = _split_messages(messages)
    if user_msg is None:
        user_msg = f"User request:\n{task}"

    if normalized == "deepseek" and not _resolve_deepseek_key():
        raise PermissionError(
            "DeepSeek route selected but no DEEPSEEK_API_KEY is available "
            "(checked environment and ~/.hermes/.env). Submit a key via the "
            "VibeComfy panel or export DEEPSEEK_API_KEY."
        )

    agent_kwargs = _build_agent_kwargs(normalized)
    result = _run_worker(agent_kwargs, system_msg, user_msg, response_contract="batch_repl")
    if "error" in result:
        err = result.get("error", "agent worker failed")
        if result.get("error_type") in {"AuthError", "AuthenticationError", "PermissionError"}:
            raise PermissionError(err)
        if result.get("error_type") in {"JSONDecodeError", "ValueError"}:
            return {"content": ""}
        raise RuntimeError(err)
    return {"content": result["content"]}


def get_agent_status(*, route: str, model: str | None = None) -> dict[str, Any]:
    """Report whether the selected route can actually run a turn.

    VibeComfy's wrapper forces ``provider_available=True`` once this module
    imports; the ``ok`` flag below is the real readiness gate.
    """
    normalized = (route or "arnold").strip().lower()
    backend = "megaplan.agent.run_agent.AIAgent"
    if normalized == "deepseek":
        key = _resolve_deepseek_key()
        return {
            "ok": bool(key),
            "backend": backend,
            "model": model or _DEEPSEEK_MODEL,
            "base_url": _DEEPSEEK_BASE_URL,
            "deepseek_key_present": bool(key),
            "detail": (
                "DeepSeek key resolved; ready to run agent-edit turns."
                if key
                else "No DEEPSEEK_API_KEY in environment or ~/.hermes/.env."
            ),
        }
    # arnold / auto / anthropic / openai-codex
    has_anthropic = bool(
        os.getenv("ANTHROPIC_API_KEY")
        or os.getenv("ANTHROPIC_TOKEN")
        or os.getenv("OPENROUTER_API_KEY")
        or os.getenv("CLAUDE_CODE_OAUTH_TOKEN")
        or (Path("~/.claude/.credentials.json").expanduser().exists())
        or (Path("~/.hermes/.anthropic_oauth.json").expanduser().exists())
    )
    return {
        "ok": has_anthropic,
        "backend": backend,
        "model": model or _ARNOLD_MODEL,
        "detail": (
            "Arnold/Hermes (Claude) credential resolved via local OAuth/API key."
            if has_anthropic
            else "No Anthropic/OpenRouter credential found for the Arnold route."
        ),
    }


__all__ = ["run_agent_turn", "run_agent_turn_delta", "run_agent_turn_batch", "get_agent_status"]
