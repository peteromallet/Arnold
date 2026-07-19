#!/usr/bin/env python3
"""Launch a Claude Code subagent process with an explicit model selector.

This is intentionally script-level. The Codex ``multi_agent_v1.spawn_agent``
tool exposed to this environment has no ``model`` field, so this repo cannot
force that external tool to run Opus. The robust local path is to launch a
separate Claude Code process and pass ``--model`` directly.

Final response goes to stdout. Diagnostics go to stderr.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Optional, Sequence


MODEL_ALIASES = {
    "opus": "opus",
    "claude-opus": "opus",
    "sonnet": "sonnet",
    "claude-sonnet": "sonnet",
    "haiku": "haiku",
    "claude-haiku": "haiku",
}


def _eprint(*args, **kwargs) -> None:
    kwargs.setdefault("file", sys.stderr)
    print(*args, **kwargs)
    sys.stderr.flush()


def resolve_model_selector(model: str) -> str:
    """Return the Claude CLI model selector for *model*.

    Known short aliases are normalized. Full Claude model ids are passed
    through unchanged so this script does not need constant churn when Claude
    Code adds a new model.
    """
    normalized = str(model).strip()
    if not normalized:
        raise ValueError("--model must not be empty")
    return MODEL_ALIASES.get(normalized.lower(), normalized)


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


def build_claude_command(
    *,
    claude_bin: str,
    model: str,
    agent: Optional[str] = None,
    effort: Optional[str] = None,
    permission_mode: Optional[str] = None,
    tools: Optional[str] = None,
    allowed_tools: Optional[str] = None,
    disallowed_tools: Optional[str] = None,
    add_dir: Optional[Sequence[str]] = None,
    mcp_config: Optional[Sequence[str]] = None,
    plugin_dir: Optional[Sequence[str]] = None,
    setting_sources: Optional[str] = None,
    settings: Optional[str] = None,
    fallback_model: Optional[str] = None,
    output_format: str = "text",
    verbose: bool = False,
    session_id: Optional[str] = None,
    resume: Optional[str] = None,
    bare: bool = False,
    dangerously_skip_permissions: bool = False,
    no_session_persistence: bool = False,
) -> list[str]:
    if session_id and resume:
        raise ValueError("--session-id and --resume are mutually exclusive")
    cmd = [
        claude_bin,
        "--print",
        "--input-format",
        "text",
        "--output-format",
        output_format,
        "--model",
        resolve_model_selector(model),
    ]
    if agent:
        cmd += ["--agent", agent]
    if effort:
        cmd += ["--effort", effort]
    if permission_mode:
        cmd += ["--permission-mode", permission_mode]
    if tools is not None:
        cmd += ["--tools", tools]
    if allowed_tools:
        cmd += ["--allowedTools", allowed_tools]
    if disallowed_tools:
        cmd += ["--disallowedTools", disallowed_tools]
    for value in add_dir or ():
        cmd += ["--add-dir", value]
    for value in mcp_config or ():
        cmd += ["--mcp-config", value]
    for value in plugin_dir or ():
        cmd += ["--plugin-dir", value]
    if setting_sources:
        cmd += ["--setting-sources", setting_sources]
    if settings:
        cmd += ["--settings", settings]
    if fallback_model:
        cmd += ["--fallback-model", fallback_model]
    if verbose:
        cmd.append("--verbose")
    if session_id:
        cmd += ["--session-id", session_id]
    if resume:
        cmd += ["--resume", resume]
    if no_session_persistence:
        cmd.append("--no-session-persistence")
    if bare:
        cmd.append("--bare")
    if dangerously_skip_permissions:
        cmd.append("--dangerously-skip-permissions")
    return cmd


def run(
    *,
    model: str,
    query: Optional[str],
    query_file: Optional[str],
    project_dir: Optional[str],
    claude_bin: str,
    timeout: Optional[float],
    dry_run: bool,
    **command_options,
) -> int:
    try:
        prompt = read_query(query, query_file)
        cmd = build_claude_command(
            claude_bin=claude_bin,
            model=model,
            **command_options,
        )
    except Exception as exc:
        _eprint(f"error: {exc}")
        return 2

    cwd = None
    if project_dir:
        target = Path(project_dir).expanduser().resolve()
        if not target.is_dir():
            _eprint(f"error: --project-dir is not a directory: {target}")
            return 2
        cwd = str(target)

    if dry_run:
        print(json.dumps({"cmd": cmd, "cwd": cwd, "stdin": prompt}, indent=2))
        return 0

    if shutil.which(claude_bin) is None and not Path(claude_bin).exists():
        _eprint(f"error: Claude CLI not found: {claude_bin!r}")
        return 3

    _eprint(
        "[launch_claude_agent] "
        f"model={resolve_model_selector(model)} cwd={cwd or Path.cwd()}"
    )
    try:
        completed = subprocess.run(
            cmd,
            input=prompt,
            text=True,
            cwd=cwd,
            check=False,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        _eprint(f"error: Claude process exceeded --timeout={timeout}s")
        return 124
    except KeyboardInterrupt:
        _eprint("[launch_claude_agent] interrupted")
        return 130
    return completed.returncode


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", default="opus", help="Claude model alias/id; default: opus")
    prompt = parser.add_mutually_exclusive_group(required=True)
    prompt.add_argument("--query", help="Inline prompt")
    prompt.add_argument("--query-file", help="Path to prompt file")
    parser.add_argument("--project-dir", help="Working directory for the Claude process")
    parser.add_argument("--claude-bin", default="claude", help="Claude CLI path/name")
    parser.add_argument("--timeout", type=float, default=1800, help="Optional process timeout in seconds")
    parser.add_argument("--dry-run", action="store_true", help="Print command JSON instead of launching")

    parser.add_argument("--agent", help="Claude Code agent name for this session")
    parser.add_argument("--effort", choices=["low", "medium", "high", "xhigh", "max"])
    parser.add_argument("--permission-mode", choices=["acceptEdits", "auto", "bypassPermissions", "default", "dontAsk", "plan"])
    parser.add_argument("--tools", help='Claude built-in tools list, e.g. "default" or "Bash,Edit,Read"')
    parser.add_argument("--allowed-tools", dest="allowed_tools", help="Allowed tool patterns")
    parser.add_argument("--disallowed-tools", dest="disallowed_tools", help="Disallowed tool patterns")
    parser.add_argument("--add-dir", action="append", default=[], help="Additional allowed directory; repeatable")
    parser.add_argument("--mcp-config", action="append", default=[], help="MCP config path/json; repeatable")
    parser.add_argument("--plugin-dir", action="append", default=[], help="Plugin directory; repeatable")
    parser.add_argument("--setting-sources", help="Comma-separated Claude setting sources")
    parser.add_argument("--settings", help="Settings file path or JSON")
    parser.add_argument("--fallback-model", help="Optional Claude CLI fallback model list")
    session = parser.add_mutually_exclusive_group()
    session.add_argument("--session-id", help="Persistent UUID for a new Claude session")
    session.add_argument("--resume", help="Resume an existing persistent Claude session UUID")
    parser.add_argument("--output-format", default="text", choices=["text", "json", "stream-json"])
    parser.add_argument("--verbose", action="store_true", help="Request full Claude event output")
    parser.add_argument(
        "--no-session-persistence",
        action="store_true",
        help="Disable persistence explicitly; managed launches do not use this",
    )
    parser.add_argument("--bare", action="store_true")
    parser.add_argument("--dangerously-skip-permissions", action="store_true")
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = _parser().parse_args(argv)
    return run(**vars(args))


if __name__ == "__main__":
    sys.exit(main())
