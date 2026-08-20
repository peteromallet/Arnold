#!/usr/bin/env python3
"""Launch a Grok subagent through omp (Oh My Pi).

Runs `omp -p --model <model> "<prompt>"` as a one-off process so the
subagent gets omp's full toolset (Bash, Read, Edit, Glob, Grep, web, …)
against a Grok model. The grok provider is defined in omp's
`~/.omp/agent/models.yml`: it talks to the same `cli-chat-proxy.grok.com`
endpoint the `grok` CLI uses, authenticated with the same x.ai OIDC token
(rotated by `~/.omp/agent/grok-token.py` — no API key, billed to your grok
account).

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


def _eprint(*args, **kwargs) -> None:
    kwargs.setdefault("file", sys.stderr)
    print(*args, **kwargs)
    sys.stderr.flush()


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


def build_omp_command(
    *,
    omp_bin: str,
    model: str,
    auto_approve: bool,
    no_session: bool,
) -> list[str]:
    cmd = [omp_bin, "-p", "--model", model]
    if auto_approve:
        cmd.append("--auto-approve")
    if no_session:
        cmd.append("--no-session")
    return cmd


def run(
    *,
    model: str,
    query: Optional[str],
    query_file: Optional[str],
    project_dir: Optional[str],
    omp_bin: str,
    timeout: Optional[float],
    dry_run: bool,
    auto_approve: bool,
    no_session: bool,
) -> int:
    try:
        prompt = read_query(query, query_file)
        cmd = build_omp_command(
            omp_bin=omp_bin,
            model=model,
            auto_approve=auto_approve,
            no_session=no_session,
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
        print(json.dumps({"cmd": cmd + [prompt], "cwd": cwd}, indent=2))
        return 0

    if shutil.which(omp_bin) is None and not Path(omp_bin).exists():
        _eprint(f"error: omp CLI not found: {omp_bin!r}")
        return 3

    _eprint(f"[launch_omp_agent] model={model} cwd={cwd or Path.cwd()}")
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
        return 124
    except KeyboardInterrupt:
        _eprint("[launch_omp_agent] interrupted")
        return 130
    return completed.returncode


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--model",
        default="grok/grok-4.6",
        help="omp model (provider/model or fuzzy match, e.g. grok-4.6); default: grok/grok-4.6",
    )
    prompt = parser.add_mutually_exclusive_group(required=True)
    prompt.add_argument("--query", help="Inline prompt")
    prompt.add_argument("--query-file", help="Path to prompt file")
    parser.add_argument("--project-dir", help="Working directory for the omp process")
    parser.add_argument("--omp-bin", default="omp", help="omp CLI path/name")
    parser.add_argument("--timeout", type=float, default=1800, help="Optional process timeout in seconds")
    parser.add_argument("--auto-approve", action="store_true", help="Pass --auto-approve to omp")
    parser.add_argument(
        "--no-session",
        action="store_true",
        default=True,
        help="Run ephemeral (no saved session); default on for one-off subagents",
    )
    parser.add_argument("--dry-run", action="store_true", help="Print command JSON instead of launching")
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = _parser().parse_args(argv)
    return run(**vars(args))


if __name__ == "__main__":
    sys.exit(main())
