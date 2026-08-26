#!/usr/bin/env python3
"""Launch an omp-backed agentic subagent through omp (Oh My Pi).

This script is the omp-backed successor of the megaplan-AIAgent launcher:
the subagent runs as a one-off ``omp -p --model <model> "<prompt>"`` process,
so it gets omp's full toolset (Bash, Read, Edit, Glob, Grep, web search, …)
in the requested model's voice. It no longer imports the Arnold/megaplan
legacy agent runtime — the same migration `origin/omp-migration` performs for
megaplan workers.

Model specs use the familiar megaplan prefix convention and are translated
to omp model selectors (see ``_translate_model``): ``deepseek:``, ``kimi:``,
``zhipu:``, ``openrouter:``, ``codex:``, ``xai:``, plus shortcuts
``fast``/``flash``/``pro``/``grok``. Provider availability follows what omp
has configured (``~/.omp/agent/models.yml`` + stored credentials).

Usage:
    python launch_omp_agent.py \
        --model="deepseek:deepseek-v4-flash" \
        --toolsets="file,web" \
        --query-file=/tmp/brief.md

Final response goes to stdout. Everything else (warnings, timings, errors)
goes to stderr so callers can pipe the output cleanly.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Optional, Sequence


def _eprint(*args, **kwargs) -> None:
    kwargs.setdefault("file", sys.stderr)
    print(*args, **kwargs)
    sys.stderr.flush()


def _check_codex_network_sandbox() -> None:
    """Fail fast if launched from inside a `codex exec` sandbox without network.

    `codex exec --sandbox read-only|workspace-write` sets
    `CODEX_SANDBOX_NETWORK_DISABLED=1` and blocks outbound sockets. omp
    subagents need to reach provider APIs, so running from those modes always
    fails later with cryptic DNS/socket errors. The fix is to launch from a
    normal shell, or to run the Codex subagent with
    `--sandbox danger-full-access`.
    """
    disabled = os.environ.get("CODEX_SANDBOX_NETWORK_DISABLED")
    if disabled:
        _eprint(
            "[launch_omp_agent] FATAL: running inside a `codex exec` "
            "sandbox with network disabled (CODEX_SANDBOX_NETWORK_DISABLED="
            f"{disabled}). omp subagents cannot reach provider APIs.\n"
            "\n"
            "Fix one of:\n"
            "  1. Launch this subagent directly from a normal shell, or\n"
            "  2. Run the parent Codex subagent with "
            "`--sandbox danger-full-access`.\n"
            "\n"
            "See the subagent-launcher SKILL.md for details."
        )
        sys.exit(1)


_MODEL_SHORTCUTS = {
    "fast": "openrouter/xiaomi/mimo-v2-flash",
    "mimo": "openrouter/xiaomi/mimo-v2-flash",
    "mimo-fast": "openrouter/xiaomi/mimo-v2-flash",
    "flash": "deepseek/deepseek-v4-flash",
    "pro": "deepseek/deepseek-v4-pro",
    "grok": "grok/grok-4.6",
}

# megaplan key-pool prefixes → omp provider selectors. Values are either a
# fixed selector or a prefix to splice the model tail into.
_PREFIX_MAP: dict[str, str] = {
    "omp": "",                    # omp:provider/model → provider/model (megaplan profile-spec form)
    "deepseek": "deepseek/",       # deepseek:deepseek-v4-flash → deepseek/deepseek-v4-flash
    "kimi": "openrouter/moonshotai/kimi-latest",  # kimi:kimi-k2.7-code → nearest omp catalog row
    "zhipu": "openrouter/z-ai/glm-latest",        # zhipu:glm-5.2 → nearest omp catalog row
    "google": "openrouter/google/",
    "minimax": "openrouter/minimax/",
    "mimo": "openrouter/xiaomi/",
    "openrouter": "openrouter/",
    "codex": "openai-codex/",
    "xai": "grok/",                # xai:grok-4.6 → grok CLI-proxy provider (same x.ai token)
}

_OMP_THINKING_LEVELS = frozenset({"off", "minimal", "low", "medium", "high", "xhigh", "max"})


def _translate_model(model: str) -> tuple[str, Optional[str]]:
    """Translate a megaplan-style model spec to an omp selector.

    Returns ``(selector, thinking_level)``. ``thinking_level`` is set when the
    spec carries a trailing ``:low|medium|high|xhigh|max`` effort token, which
    maps to omp's ``--thinking``.
    """
    spec = str(model).strip()
    shortcut = _MODEL_SHORTCUTS.get(spec)
    if shortcut is not None:
        return shortcut, None

    thinking: Optional[str] = None
    candidate, sep, tail = spec.rpartition(":")
    if sep and tail in ("low", "medium", "high", "xhigh", "max"):
        spec, thinking = candidate, tail

    for prefix, mapped in _PREFIX_MAP.items():
        marker = f"{prefix}:"
        if spec.startswith(marker):
            tail = spec[len(marker):]
            if not mapped:
                return tail, thinking  # identity prefix: the tail is the selector
            if mapped.endswith("/"):
                return mapped + tail, thinking
            return mapped, thinking  # fixed catalog row; model tail is advisory
    return spec, thinking  # passthrough — omp fuzzy-matches or errors clearly


def read_query(query: Optional[str], query_file: Optional[str]) -> str:
    if query and query_file:
        raise ValueError("pass exactly one of --query or --query-file, not both")
    if not query and not query_file:
        raise ValueError("one of --query or --query-file is required")
    if query_file:
        qpath = Path(query_file).expanduser()
        if not qpath.exists():
            raise FileNotFoundError(f"query file not found: {qpath}")
        query = qpath.read_text(encoding="utf-8")
    assert query is not None
    if not query.strip():
        raise ValueError("query is empty")
    return query


def _normalize_toolsets(toolsets: Any) -> str:
    """fire passes `--toolsets=a,b` as a tuple — normalize to a CSV string."""
    if isinstance(toolsets, (tuple, list)):
        return ",".join(str(t) for t in toolsets)
    return str(toolsets)


def build_omp_command(
    *,
    omp_bin: str,
    model: str,
    thinking: Optional[str],
    toolsets: str,
) -> list[str]:
    cmd = [omp_bin, "-p", "--model", model]
    if thinking is not None and thinking in _OMP_THINKING_LEVELS:
        cmd += ["--thinking", thinking]
    if not toolsets or not [t for t in toolsets.split(",") if t.strip()]:
        cmd.append("--no-tools")
    cmd.append("--no-session")
    return cmd


def run(
    model: str = "deepseek:deepseek-v4-flash",
    query: Optional[str] = None,
    query_file: Optional[str] = None,
    toolsets: str = "file,web",
    max_tokens: int = 65536,
    context_budget_tokens: Optional[int] = None,
    session_id: Optional[str] = None,
    resume_session: bool = False,
    metadata_file: Optional[str] = None,
    project_dir: Optional[str] = None,
    # Long superfixer/babysitter turns legitimately run 30-60+ min; the old
    # hard 1800s default SIGTERMed them mid-work (rc=-15, no failure record).
    # Env-overridable so callers can tune without code edits.
    timeout: float = float(os.environ.get("MEGAPLAN_TURN_TIMEOUT_SECS", "7200")),
    omp_bin: str = "omp",
) -> int:
    """Dispatch a subagent through omp and print its final response to stdout."""
    start = time.monotonic()

    if resume_session:
        _eprint(
            "error: --resume-session is not supported in the omp-backed "
            "launcher. Run `omp --resume` directly to continue an omp session."
        )
        return 8

    try:
        prompt = read_query(query, query_file)
        selector, thinking = _translate_model(model)
        toolsets = _normalize_toolsets(toolsets)
        cmd = build_omp_command(
            omp_bin=omp_bin,
            model=selector,
            thinking=thinking,
            toolsets=toolsets,
        )
    except Exception as exc:
        _eprint(f"error: {exc}")
        return 2

    toolset_list = [t.strip() for t in toolsets.split(",") if t.strip()]
    _eprint(
        f"[launch_omp_agent] model={model} → resolved={selector} "
        f"toolsets={toolset_list or '(none)'} "
        f"max_tokens={max_tokens} context_budget_tokens={context_budget_tokens or '(auto)'}"
    )
    if thinking is not None:
        _eprint(f"[launch_omp_agent] thinking={thinking}")
    if toolset_list:
        _eprint(
            "[launch_omp_agent] NOTE: omp gives the full toolset (Bash, Read, "
            "Edit, web, …); the file/web/terminal subset is a superset here."
        )
    if max_tokens and max_tokens != 65536:
        _eprint(
            "[launch_omp_agent] NOTE: --max-tokens is informational; omp uses "
            "the model's native output ceiling."
        )
    if context_budget_tokens is not None:
        _eprint(
            "[launch_omp_agent] NOTE: --context-budget-tokens is not supported "
            "through omp (auto-compaction handles context)."
        )
    if session_id:
        _eprint(
            f"[launch_omp_agent] NOTE: --session-id={session_id!r} ignored — "
            "omp sessions are ephemeral here; use `omp --resume` for persistence."
        )

    cwd = None
    if project_dir:
        target = Path(project_dir).expanduser().resolve()
        if not target.is_dir():
            _eprint(f"error: --project-dir is not a directory: {target}")
            return 2
        cwd = str(target)

    if shutil.which(omp_bin) is None and not Path(omp_bin).exists():
        _eprint(f"error: omp CLI not found: {omp_bin!r}")
        return 3

    _eprint(f"[launch_omp_agent] cwd={cwd or Path.cwd()}")
    try:
        completed = subprocess.run(
            cmd + [prompt],
            text=True,
            cwd=cwd,
            check=False,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        _eprint(f"error: omp process exceeded --timeout={timeout}s")
        _write_metadata(metadata_file, start, model, selector, toolset_list, max_tokens, status="timeout", exit_code=124)
        return 124
    except KeyboardInterrupt:
        _eprint("[launch_omp_agent] interrupted")
        return 130

    elapsed = time.monotonic() - start
    status = "completed" if completed.returncode == 0 else "error"
    _write_metadata(
        metadata_file,
        start,
        model,
        selector,
        toolset_list,
        max_tokens,
        status=status,
        exit_code=completed.returncode,
    )
    _eprint(f"[launch_omp_agent] done in {elapsed:.1f}s (exit={completed.returncode})")
    return completed.returncode


def _write_metadata(
    metadata_file: Optional[str],
    start: float,
    model: str,
    resolved_model: str,
    toolset_list: list[str],
    max_tokens: int,
    *,
    status: str,
    exit_code: int,
) -> None:
    if not metadata_file:
        return
    receipt = {
        "schema_version": "arnold-omp-launcher-metadata-v1",
        "session_id": None,
        "resumed_session_id": None,
        "model": model,
        "resolved_model": resolved_model,
        "toolsets": toolset_list,
        "max_tokens": int(max_tokens),
        "status": status,
        "exit_code": exit_code,
        "elapsed_seconds": round(time.monotonic() - start, 3),
    }
    try:
        path = Path(metadata_file).expanduser()
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
        temporary.write_text(
            json.dumps(receipt, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        os.replace(temporary, path)
    except OSError as exc:
        _eprint(f"[launch_omp_agent] warning: could not write metadata: {exc}")


def main(argv: Optional[Sequence[str]] = None) -> None:
    # Legacy Arnold resident flows set ARNOLD_MANAGED_AGENT_* env vars and
    # expected the launcher to re-exec under a managed run. The omp-backed
    # launcher is a plain subprocess; managed-run wrapping is handled by the
    # caller — note it and continue.
    if (
        os.environ.get("ARNOLD_MANAGED_AGENT_RUN_ID")
        and os.environ.get("ARNOLD_MANAGED_AGENT_MANIFEST")
        and os.environ.get("ARNOLD_MANAGED_AGENT_ORIGIN")
    ):
        _eprint(
            "[launch_omp_agent] NOTE: managed-run env detected; the omp-backed "
            "launcher does not self-reexec (see SKILL.md)."
        )

    _check_codex_network_sandbox()
    try:
        import fire
    except ImportError:
        _eprint("error: this script requires `fire`. Install with `pip install fire`.")
        sys.exit(1)
    fire.Fire(run)


if __name__ == "__main__":
    main()
