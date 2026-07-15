#!/usr/bin/env python3
"""Launch a hermes-backed agentic subagent (DeepSeek / Kimi / Zhipu / etc.).

This script exposes the megaplan AIAgent primitive — the same one the hermes
worker uses for plan phases — as a standalone CLI. Unlike a plain `curl` chat
call, the resulting agent can actually call tools (read files, fetch URLs,
optionally run a shell), so it is a *real* agentic subagent rather than a
one-shot opinion.

Usage:
    PYENV_VERSION=3.11.11 python launch_hermes_agent.py \
        --model="deepseek:deepseek-v4-pro" \
        --toolsets="file,web" \
        --query-file=/tmp/brief.md

Security note: the agent inherits the current process's filesystem access.
The megaplan sandbox (`megaplan.runtime.sandbox`) is NOT installed here — the
wiring requires a plan workspace and is non-trivial to bootstrap standalone.
Treat the agent's reach as equivalent to the invoking user's shell.

Final response goes to stdout. Everything else (warnings, timings, errors)
goes to stderr so callers can pipe the output cleanly.
"""

from __future__ import annotations

import os
import hashlib
import subprocess
import sys
import time
import traceback
import math
import json
from pathlib import Path
from typing import Optional
from urllib.parse import unquote, urlparse


def _eprint(*args, **kwargs) -> None:
    kwargs.setdefault("file", sys.stderr)
    print(*args, **kwargs)
    sys.stderr.flush()


def _load_hermes_env() -> None:
    """Replicate `hermes_cli.env_loader.load_hermes_dotenv` minimally.

    `resolve_model` reads from `os.environ` directly via its key pool; if the
    caller didn't `source ~/.hermes/.env` we have to do it ourselves so
    DEEPSEEK_API_KEY / FIREWORKS_API_KEY / etc. land in the environment.

    We intentionally avoid `python-dotenv` (extra dep) and do a small parser
    that matches the format hermes uses (KEY=value, optional quotes, comments).
    """
    env_path = Path.home() / ".hermes" / ".env"
    if not env_path.exists():
        return
    try:
        for raw in env_path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip("'").strip('"')
            # Override stale shell values — the user-level hermes env is canonical.
            os.environ[key] = value
    except OSError as exc:
        _eprint(f"[launch_hermes_agent] warning: could not read {env_path}: {exc}")


def _check_codex_network_sandbox() -> None:
    """Fail fast if launched from inside a `codex exec` sandbox without network.

    `codex exec --sandbox read-only|workspace-write` sets
    `CODEX_SANDBOX_NETWORK_DISABLED=1` and blocks outbound sockets. Hermes
    agents need to reach provider APIs, so running from those modes always
    fails later with cryptic DNS/socket errors. The fix is to launch from a
    normal shell, or to run the Codex subagent with
    `--sandbox danger-full-access`.
    """
    disabled = os.environ.get("CODEX_SANDBOX_NETWORK_DISABLED")
    if disabled:
        _eprint(
            "[launch_hermes_agent] FATAL: running inside a `codex exec` "
            "sandbox with network disabled (CODEX_SANDBOX_NETWORK_DISABLED="
            f"{disabled}). Hermes agents cannot reach provider APIs.\n"
            "\n"
            "Fix one of:\n"
            "  1. Launch this hermes subagent directly from a normal shell, or\n"
            "  2. Run the parent Codex subagent with "
            "`--sandbox danger-full-access`.\n"
            "\n"
            "See the subagent-launcher SKILL.md for details."
        )
        sys.exit(1)


def _prefer_legacy_megaplan_distribution() -> None:
    """Put the legacy ``megaplan`` editable checkout before Arnold guard paths.

    Arnold clean-break worktrees intentionally contain a top-level
    ``megaplan.py`` guard that raises ``ModuleNotFoundError``. That is correct
    for product code, but this launcher still depends on the legacy
    ``megaplan.agent`` runtime. Editable Arnold installs can appear earlier on
    ``sys.path`` than the legacy checkout, so resolve the installed
    ``megaplan`` distribution and put its source root first.
    """

    try:
        from importlib.metadata import distribution

        dist = distribution("megaplan")
        direct_url = dist.read_text("direct_url.json")
        if not direct_url:
            return
        url = json.loads(direct_url).get("url", "")
        parsed = urlparse(url)
        if parsed.scheme != "file":
            return
        root = Path(unquote(parsed.path))
        if not (root / "megaplan" / "agent" / "__init__.py").exists():
            return
        root_str = str(root)
        sys.path[:] = [p for p in sys.path if p != root_str]
        sys.path.insert(0, root_str)
    except Exception as exc:
        if "No package metadata was found for megaplan" in str(exc):
            return
        _eprint(
            "[launch_hermes_agent] warning: could not prefer legacy "
            f"megaplan distribution: {exc}"
        )


def _add_fallback_megaplan_paths() -> None:
    """If the editable ``megaplan`` distribution isn't installed, add known source roots.

    Codex and other clean shells often don't have the editable install metadata,
    but the source checkout still exists on disk. This fallback lets the launcher
    work without a manual ``PYTHONPATH``.
    """
    try:
        import megaplan.agent  # noqa: F401 — probe only
        return
    except ModuleNotFoundError:
        pass

    candidates = []
    for env_name in ("MEGPLAN_PATH", "MEGPLAN_ENGINE", "ARNOLD_PATH"):
        env_path = os.environ.get(env_name)
        if env_path:
            candidates.append(Path(env_path))

    home = Path.home()
    cwd = Path.cwd()
    candidates.extend(
        [
            home / "Documents" / "megaplan",
            home / "Documents" / "megaplan-engine",
            home / "Documents" / "megaplan-engine-main",
            home / "Documents" / "Arnold",
            home / "src" / "megaplan",
            home / "megaplan",
            home / "workspace" / "megaplan",
            cwd.parent / "megaplan",
            cwd.parent / "megaplan-engine",
            cwd.parent / "megaplan-engine-main",
            cwd.parent / "Arnold",
        ]
    )

    for root in candidates:
        if not root.exists():
            continue
        if (
            (root / "megaplan" / "agent" / "__init__.py").exists()
            or (root / "arnold" / "pipelines" / "megaplan" / "agent" / "__init__.py").exists()
            or (root / "arnold" / "agent" / "run_agent.py").exists()
        ):
            root_str = str(root)
            if root_str not in sys.path:
                sys.path.insert(0, root_str)
            return


def _import_runtime():
    """Import Hermes runtime from legacy megaplan or current Arnold checkout."""
    # Try 1: legacy top-level megaplan package
    try:
        import megaplan.agent  # noqa: F401 — installs hermes sys.path
        from run_agent import AIAgent
        from hermes_state import SessionDB
        from megaplan.runtime.key_pool import resolve_model
        return AIAgent, SessionDB, resolve_model
    except ModuleNotFoundError as legacy_exc:
        if legacy_exc.name not in {"megaplan", "megaplan.agent", "run_agent", "hermes_state"}:
            raise
    # Try 2: current Arnold editable-install layout.
    try:
        from arnold.agent.run_agent import AIAgent
        from arnold.agent.hermes_state import SessionDB
        from arnold_pipelines.megaplan.runtime.key_pool import resolve_model
        return AIAgent, SessionDB, resolve_model
    except ModuleNotFoundError as current_exc:
        if current_exc.name not in {"arnold", "arnold.agent", "arnold.agent.run_agent", "arnold.agent.hermes_state"}:
            raise
        pass
    # Try 3: current Arnold checkout with legacy vendored-agent path on sys.path.
    try:
        vendored_agent = Path.cwd() / "arnold" / "pipelines" / "megaplan" / "agent"
        if vendored_agent.exists():
            vendored_agent_str = str(vendored_agent)
            if vendored_agent_str not in sys.path:
                sys.path.insert(0, vendored_agent_str)
        from arnold.agent.run_agent import AIAgent
        from arnold.agent.hermes_state import SessionDB
        from arnold_pipelines.megaplan.runtime.key_pool import resolve_model
        return AIAgent, SessionDB, resolve_model
    except ModuleNotFoundError as vendored_exc:
        if vendored_exc.name not in {"arnold", "arnold.agent", "arnold.agent.run_agent", "arnold.agent.hermes_state"}:
            raise
        pass
    # Try 4: historical product-local layout.
    from arnold_pipelines.megaplan.agent.run_agent import AIAgent
    from arnold_pipelines.megaplan.agent.hermes_state import SessionDB
    from arnold_pipelines.megaplan.runtime.key_pool import resolve_model
    return AIAgent, SessionDB, resolve_model


def _no_op_stream(_text: str) -> None:
    """Sentinel callback that forces AIAgent's streaming path.

    Copied verbatim from megaplan/workers/hermes.py:50.  AIAgent decides
    streaming vs non-streaming based on whether `stream_callback` is set;
    Fireworks rejects `max_tokens > 4096` without `stream=true`, and the
    direct DeepSeek route is kept on the same path for parity.
    """
    return None


# Same flag the hermes worker tags the callback with — harmless if AIAgent
# does not check it, but matches the upstream pattern exactly.
_no_op_stream._megaplan_force_stream = True  # type: ignore[attr-defined]


_MODEL_SHORTCUTS = {
    "fast": "mimo:mimo-v2.5-pro-ultraspeed",
    "mimo": "mimo:mimo-v2.5-pro-ultraspeed",
    "mimo-fast": "mimo:mimo-v2.5-pro-ultraspeed",
    "flash": "deepseek:deepseek-v4-flash",
    "pro": "deepseek:deepseek-v4-pro",
}

_HIGH_TOKEN_STREAM_PROVIDERS = ("fireworks:", "deepseek:", "mimo:")
_HIGH_TOKEN_STREAM_MAX_TOKENS = 4096
_NESTED_WORKER_ENV = "ARNOLD_NESTED_MANAGED_AGENT_WORKER"


def _resolve_model_shortcut(model: str) -> str:
    return _MODEL_SHORTCUTS.get(str(model).strip(), model)


def _automatic_managed_reexec() -> int | None:
    """Put nested automatic Hermes/DeepSeek work under its own durable run."""

    parent_run_id = str(os.environ.get("ARNOLD_MANAGED_AGENT_RUN_ID") or "").strip()
    parent_manifest = str(os.environ.get("ARNOLD_MANAGED_AGENT_MANIFEST") or "").strip()
    machine_origin = str(os.environ.get("ARNOLD_MANAGED_AGENT_ORIGIN") or "").strip()
    if not parent_run_id or not parent_manifest or not machine_origin:
        return None
    if os.environ.get(_NESTED_WORKER_ENV) == "1":
        return None
    try:
        from arnold_pipelines.megaplan.managed_agent import (
            normalize_machine_origin_provenance,
            validate_automatic_managed_manifest,
        )

        parent_manifest_path = Path(parent_manifest).resolve()
        parent_payload = json.loads(parent_manifest_path.read_text(encoding="utf-8"))
        validate_automatic_managed_manifest(
            parent_payload,
            manifest_path=parent_manifest_path,
        )
        inherited_origin = normalize_machine_origin_provenance(json.loads(machine_origin))
        if parent_payload.get("run_id") != parent_run_id:
            raise ValueError("parent run id disagrees with manifest")
        if inherited_origin != parent_payload.get("launch_provenance"):
            raise ValueError("parent machine origin disagrees with manifest")
        if not any(
            item.get("status") == "running"
            for item in parent_payload.get("status_history") or []
            if isinstance(item, dict)
        ):
            raise ValueError("parent managed run never reached running")
    except (OSError, TypeError, ValueError) as exc:
        raise RuntimeError("automatic nested launcher inherited invalid managed custody") from exc

    model = "deepseek:deepseek-v4-pro"
    project_dir = str(Path.cwd())
    query_file = ""
    child_args: list[str] = []
    for argument in sys.argv[1:]:
        if argument.startswith(("--model=",)):
            model = argument.split("=", 1)[1]
        elif argument.startswith(("--project_dir=", "--project-dir=")):
            project_dir = argument.split("=", 1)[1]
        elif argument.startswith(("--query_file=", "--query-file=")):
            query_file = argument.split("=", 1)[1]
            option = argument.split("=", 1)[0]
            child_args.append(f"{option}=@managed-stdin@")
            continue
        elif argument.startswith("--query="):
            raise RuntimeError("automatic nested agent requires sealed --query-file input")
        child_args.append(argument)
    if not query_file:
        raise RuntimeError("automatic nested agent requires --query-file")
    query_path = Path(query_file).expanduser().resolve()
    identity_material = json.dumps(
        [parent_run_id, model, child_args, hashlib.sha256(query_path.read_bytes()).hexdigest()],
        separators=(",", ":"),
    )
    identity_digest = hashlib.sha256(identity_material.encode("utf-8")).hexdigest()[:24]
    identity = f"nested-research:{parent_run_id}:{identity_digest}"
    command = [
        sys.executable,
        "-m",
        "arnold_pipelines.megaplan.managed_agent",
        "run",
        "--run-kind",
        "automatic_research_subagent",
        "--identity-key",
        identity,
        "--project-dir",
        str(Path(project_dir).expanduser().resolve()),
        "--task-kind",
        "research",
        "--difficulty",
        "8",
        "--model",
        model,
        "--reasoning-effort",
        "high",
        "--route-class",
        "managed_parent_research",
        "--backend",
        "hermes",
        "--command-display",
        f"nested managed research subagent model={model}",
        "--origin-kind",
        "managed_parent_agent",
        "--origin-id",
        parent_run_id,
        "--origin-component",
        "launch_hermes_agent",
        "--trigger-id",
        identity_digest,
        "--parent-run-id",
        parent_run_id,
        "--lineage-key",
        f"nested-research:{parent_run_id}",
        "--stdin-file",
        str(query_path),
        "--require-output",
        "--link",
        f"parent_manifest={parent_manifest}",
        "--link",
        "phase=nested_research",
        "--",
        sys.executable,
        str(Path(__file__).resolve()),
        *child_args,
    ]
    env = dict(os.environ)
    env[_NESTED_WORKER_ENV] = "1"
    return subprocess.run(command, env=env, check=False).returncode


def _requires_streaming(model: str, max_tokens: int) -> bool:
    if not model.startswith(_HIGH_TOKEN_STREAM_PROVIDERS):
        return False
    return max_tokens > _HIGH_TOKEN_STREAM_MAX_TOKENS


def _apply_context_budget(agent, budget_tokens: Optional[int]) -> Optional[dict[str, int]]:
    """Raise AIAgent's auto-compaction threshold for this process only.

    The underlying hermes runtime derives ``threshold_tokens`` from a detected
    model context length and the user's compression.threshold setting.  Some
    provider routes can have stale/probed-low cache entries, so the standalone
    launcher exposes a local escape hatch without changing global config.
    """
    if budget_tokens is None:
        return None
    if budget_tokens <= 0:
        raise ValueError("--context-budget-tokens must be a positive integer")

    compressor = getattr(agent, "context_compressor", None)
    if compressor is None:
        raise RuntimeError("AIAgent has no context_compressor to configure")

    old_threshold = int(getattr(compressor, "threshold_tokens", 0) or 0)
    old_context = int(getattr(compressor, "context_length", 0) or 0)
    if old_threshold >= budget_tokens:
        return {
            "old_threshold": old_threshold,
            "new_threshold": old_threshold,
            "old_context": old_context,
            "new_context": old_context,
        }

    threshold_percent = float(getattr(compressor, "threshold_percent", 0) or 0)
    if threshold_percent <= 0:
        threshold_percent = 1.0
    new_context = max(old_context, math.ceil(budget_tokens / threshold_percent))
    compressor.context_length = new_context
    compressor.threshold_tokens = budget_tokens
    return {
        "old_threshold": old_threshold,
        "new_threshold": budget_tokens,
        "old_context": old_context,
        "new_context": new_context,
    }


def run(
    model: str = "deepseek:deepseek-v4-pro",
    query: Optional[str] = None,
    query_file: Optional[str] = None,
    toolsets: str = "file,web",
    max_tokens: int = 65536,
    context_budget_tokens: Optional[int] = None,
    session_id: Optional[str] = None,
    project_dir: Optional[str] = None,
) -> None:
    """Dispatch a hermes-backed agent and print its final response to stdout.

    Args:
        model: Provider-prefixed model spec, e.g. ``deepseek:deepseek-v4-pro``
            (default), ``deepseek:deepseek-v4-flash`` (faster, no reasoning),
            ``mimo:mimo-v2.5-pro-ultraspeed`` (very fast), 
            ``fireworks:accounts/fireworks/models/kimi-k2p5``, ``zhipu:glm-5.1``.
            Shortcuts: ``fast``/``mimo``/``mimo-fast`` → MiMo ultraspeed,
            ``flash`` → DeepSeek flash, ``pro`` → DeepSeek pro.
            Bare model names route through OpenRouter (legacy path).
        query: Inline prompt. Mutually exclusive with ``query_file``.
        query_file: Path to a file containing the prompt. Use this for any
            non-trivial prompt; argv is brittle for multi-line content.
        toolsets: Comma-separated subset of {file, web, terminal}. Empty
            string disables tools entirely (pure chat through the hermes
            transport — useful for direct comparisons with the curl path).
        max_tokens: Hard cap on response tokens. ≥ 4097 forces streaming
            on deepseek:/fireworks: providers — the script handles that
            automatically.
        context_budget_tokens: Optional minimum prompt-token budget before
            auto-compaction triggers. This raises the per-run compressor cap
            without changing Hermes config or context-length cache. Useful
            when provider metadata/cache underestimates a long-context model.
        session_id: Reuse a prior hermes session id (optional).
        project_dir: Working directory the agent should treat as cwd.
            Defaults to the script's invoking cwd. Note: this does NOT install
            the megaplan sandbox — see security note in module docstring.
    """
    start = time.monotonic()

    if query and query_file:
        _eprint("error: pass exactly one of --query or --query-file, not both")
        sys.exit(2)
    if not query and not query_file:
        _eprint("error: one of --query or --query-file is required")
        sys.exit(2)
    if context_budget_tokens is not None and int(context_budget_tokens) <= 0:
        _eprint("error: --context-budget-tokens must be a positive integer")
        sys.exit(2)

    if query_file:
        qpath = Path(query_file).expanduser()
        if not qpath.exists():
            _eprint(f"error: query file not found: {qpath}")
            sys.exit(2)
        query = qpath.read_text(encoding="utf-8")

    _load_hermes_env()

    # Optional cwd change so file tools resolve relative paths the caller expects.
    if project_dir:
        target = Path(project_dir).expanduser().resolve()
        if not target.is_dir():
            _eprint(f"error: --project-dir is not a directory: {target}")
            sys.exit(2)
        os.chdir(target)
        target_str = str(target)
        if target_str not in sys.path:
            sys.path.insert(0, target_str)

    # Imports happen after env load so any module-level credential lookups see
    # the freshly populated environment.
    try:
        _prefer_legacy_megaplan_distribution()
        _add_fallback_megaplan_paths()
        AIAgent, SessionDB, resolve_model = _import_runtime()
    except Exception as exc:
        _eprint("error: could not import megaplan/hermes runtime:")
        _eprint(traceback.format_exc())
        sys.exit(3)

    model = _resolve_model_shortcut(model)
    resolved_model, agent_kwargs = resolve_model(model)
    if "api_key" not in agent_kwargs or not agent_kwargs.get("api_key"):
        # OpenRouter fallback is okay (no prefix), but for explicit prefixed
        # providers a missing key means the .env load found nothing useful.
        if ":" in model:
            _eprint(
                f"error: no API key resolved for provider prefix in {model!r}. "
                f"Check ~/.hermes/.env for the matching *_API_KEY variable."
            )
            sys.exit(4)

    # `python-fire` helpfully parses `--toolsets="file,web"` as a tuple
    # `('file', 'web')`. Accept both string and tuple/list forms.
    if isinstance(toolsets, (tuple, list)):
        toolset_list = [str(t).strip() for t in toolsets if str(t).strip()]
    else:
        toolset_list = [t.strip() for t in str(toolsets).split(",") if t.strip()]

    _eprint(
        f"[launch_hermes_agent] model={model} → resolved={resolved_model} "
        f"toolsets={toolset_list or '(none)'} max_tokens={max_tokens} "
        f"context_budget_tokens={context_budget_tokens or '(auto)'}"
    )
    if toolset_list and "terminal" in toolset_list:
        _eprint(
            "[launch_hermes_agent] WARNING: 'terminal' toolset is enabled but the "
            "megaplan sandbox is NOT installed in this entrypoint. Shell commands "
            "will run with the invoking user's privileges."
        )

    try:
        agent = AIAgent(
            model=resolved_model,
            # [] is an explicit no-tools capability set.  None means "use the
            # runtime default" and silently grants file/web tools.
            enabled_toolsets=toolset_list,
            session_id=session_id,
            session_db=SessionDB(),
            max_tokens=max_tokens,
            skip_context_files=True,
            skip_memory=True,
            quiet_mode=True,
            **agent_kwargs,
        )
    except Exception:
        _eprint("error: AIAgent construction failed:")
        _eprint(traceback.format_exc())
        sys.exit(5)

    try:
        budget_result = _apply_context_budget(agent, context_budget_tokens)
    except Exception:
        _eprint("error: could not apply --context-budget-tokens:")
        _eprint(traceback.format_exc())
        sys.exit(5)
    if budget_result and budget_result["new_threshold"] != budget_result["old_threshold"]:
        _eprint(
            "[launch_hermes_agent] context budget override: "
            f"compaction threshold {budget_result['old_threshold']:,} → "
            f"{budget_result['new_threshold']:,} tokens "
            f"(context length {budget_result['old_context']:,} → "
            f"{budget_result['new_context']:,})"
        )

    # Route agent's own diagnostic prints to stderr so stdout stays clean.
    agent._print_fn = lambda *a, **kw: print(*a, **kw, file=sys.stderr)

    run_kwargs: dict = {}
    if _requires_streaming(model, max_tokens):
        run_kwargs["stream_callback"] = _no_op_stream
        _eprint("[launch_hermes_agent] streaming forced (provider + max_tokens > 4096)")

    # Keep a handle on the real stdout, then swap stdout → stderr while the
    # agent runs. The KawaiiSpinner and other agent-internal prints capture
    # `sys.stdout` at construction time, so anything that escapes our
    # `_print_fn` override (spinner thread, tool progress prefixes) will land
    # on stderr instead of polluting the final-response channel.
    real_stdout = sys.stdout
    sys.stdout = sys.stderr
    try:
        result = agent.run_conversation(user_message=query, **run_kwargs)
    except KeyboardInterrupt:
        sys.stdout = real_stdout
        _eprint("[launch_hermes_agent] interrupted")
        sys.exit(130)
    except Exception:
        sys.stdout = real_stdout
        _eprint("error: run_conversation raised:")
        _eprint(traceback.format_exc())
        sys.exit(6)
    finally:
        sys.stdout = real_stdout

    elapsed = time.monotonic() - start

    final = result.get("final_response") if isinstance(result, dict) else None
    if final is None:
        _eprint(
            f"[launch_hermes_agent] WARNING: agent returned no final_response. "
            f"finish_reason={result.get('finish_reason') if isinstance(result, dict) else 'n/a'!r}"
        )
        _eprint(f"[launch_hermes_agent] elapsed={elapsed:.1f}s")
        sys.exit(7)

    print(final)
    _eprint(f"[launch_hermes_agent] done in {elapsed:.1f}s")


def main() -> None:
    nested_returncode = _automatic_managed_reexec()
    if nested_returncode is not None:
        raise SystemExit(nested_returncode)
    _check_codex_network_sandbox()
    try:
        import fire
    except ImportError:
        _eprint("error: this script requires `fire`. Install with `pip install fire`.")
        sys.exit(1)
    fire.Fire(run)


if __name__ == "__main__":
    main()
