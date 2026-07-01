"""Sub-agent dispatch for the resident VP to-do sweep.

The resident main agent calls ``launch_subagent`` to delegate execution of a
to-do item to a separate hermes-backed agent (by default the configured
``subagent_model_name``). We invoke the proven ``launch_hermes_agent.py`` CLI as
a subprocess: it keeps stdout as the clean final response (agent diagnostics are
rerouted to stderr) and already wires general-purpose ``file,web,terminal``
toolsets. The blocking ``subprocess.run`` runs in a worker thread via
``asyncio.to_thread`` so the resident event loop stays responsive.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
import logging
import subprocess
import sys
import tempfile
from pathlib import Path

from .config import ResidentConfig

LOGGER = logging.getLogger(__name__)

# resident/ -> megaplan/ -> skills/subagent-launcher/launch_hermes_agent.py
LAUNCHER_PATH = (
    Path(__file__).resolve().parent.parent / "skills" / "subagent-launcher" / "launch_hermes_agent.py"
)


@dataclass(frozen=True)
class SubagentResult:
    ok: bool
    final_text: str
    stderr: str
    returncode: int
    error: str | None = None


async def launch_subagent_task(
    config: ResidentConfig,
    *,
    task: str,
    toolsets: str | None = None,
    project_dir: str | None = None,
) -> SubagentResult:
    """Dispatch ``task`` to a hermes sub-agent and return its final response.

    ``stdout`` carries only the sub-agent's final response (the launcher swaps
    agent diagnostics to stderr); on non-zero exit or empty stdout ``ok`` is
    False and ``error`` carries a short diagnostic from stderr.
    """
    if not LAUNCHER_PATH.exists():
        raise FileNotFoundError(f"hermes launcher not found: {LAUNCHER_PATH}")

    argv: list[str] = [
        sys.executable,
        str(LAUNCHER_PATH),
        "--model",
        config.subagent_model_name,
        "--toolsets",
        toolsets or config.special_requests_subagent_toolsets,
        "--max-tokens",
        str(config.special_requests_subagent_max_tokens),
    ]
    if project_dir:
        argv += ["--project-dir", str(project_dir)]

    # Multi-line prompts are brittle on argv — write to a query file instead.
    with tempfile.NamedTemporaryFile(
        "w", suffix=".md", delete=False, encoding="utf-8"
    ) as handle:
        handle.write(task)
        query_path = handle.name
    argv += ["--query-file", query_path]

    timeout_s = float(config.special_requests_subagent_timeout_s)
    try:
        completed = await asyncio.to_thread(_run_subprocess, argv, timeout_s)
    finally:
        try:
            Path(query_path).unlink(missing_ok=True)
        except OSError:
            LOGGER.debug("could not remove subagent query file %s", query_path, exc_info=True)

    return completed


def _run_subprocess(argv: list[str], timeout_s: float) -> SubagentResult:
    try:
        completed = subprocess.run(
            argv,
            capture_output=True,
            text=True,
            timeout=timeout_s,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        return SubagentResult(
            ok=False,
            final_text="",
            stderr=str(exc),
            returncode=-1,
            error=f"subagent timed out after {timeout_s:.0f}s",
        )
    final_text = (completed.stdout or "").strip()
    stderr = completed.stderr or ""
    returncode = completed.returncode
    ok = returncode == 0 and bool(final_text)
    error: str | None = None
    if not ok:
        tail = stderr.strip()[:500]
        error = f"subagent exit {returncode}" + (f": {tail}" if tail else " (no stdout)")
    return SubagentResult(
        ok=ok,
        final_text=final_text,
        stderr=stderr,
        returncode=returncode,
        error=error,
    )
