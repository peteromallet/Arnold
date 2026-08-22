"""Console entry point: run an omp named agent (default: ``arnold``).

Installed as the ``arnold`` console script. Bare invocation opens the
agent's interactive session; positional words become a one-shot message:

    arnold                      # interactive AgentBox Operator session
    arnold "What is running?"   # one-shot question, printed answer
    arnold --agent scout "…"    # talk to a different installed agent

The workflow/operator tooling lives on the ``megaplan`` console script.
"""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

DEFAULT_AGENT = "arnold"

# Known good homes for omp's ``agent`` launcher script. A bare ``agent`` on
# PATH may be a different vendor's binary (e.g. grok ships one too), so the
# PATH fallback is only trusted outside those installs.
_LAUNCHER_CANDIDATES: tuple[Path, ...] = (
    Path.home() / ".bun" / "bin" / "agent",
)
_UNTRUSTED_PATH_MARKERS: tuple[str, ...] = (".grok",)


def _find_launcher() -> Path | None:
    override = os.environ.get("ARNOLD_AGENT_LAUNCHER")
    if override:
        candidate = Path(override).expanduser()
        return candidate if candidate.is_file() else None
    for candidate in _LAUNCHER_CANDIDATES:
        if candidate.is_file():
            return candidate
    on_path = shutil.which("agent")
    if on_path and not any(marker in on_path for marker in _UNTRUSTED_PATH_MARKERS):
        return Path(on_path)
    return None


# omp flags that consume a following value token.
_VALUE_FLAGS = frozenset({"-r", "--resume", "--session-dir", "--profile"})


def _split_flags(rest: list[str]) -> tuple[list[str], list[str]]:
    """Partition leading omp flags from the remaining message words."""
    flags: list[str] = []
    index = 0
    while index < len(rest) and rest[index].startswith("-"):
        token = rest[index]
        flags.append(token)
        index += 1
        if token in _VALUE_FLAGS and index < len(rest):
            flags.append(rest[index])
            index += 1
    return flags, rest[index:]


def main(argv: list[str] | None = None) -> int:
    rest = list(sys.argv[1:] if argv is None else argv)
    agent = DEFAULT_AGENT
    while "--agent" in rest:
        index = rest.index("--agent")
        rest.pop(index)
        if index >= len(rest):
            print("arnold: --agent requires a value", file=sys.stderr)
            return 1
        agent = rest.pop(index)

    launcher = _find_launcher()
    if launcher is None:
        print(
            "arnold: could not locate the omp agent launcher. Install oh-my-pi "
            "(~/.bun/bin/agent) or point ARNOLD_AGENT_LAUNCHER at its 'agent' script.",
            file=sys.stderr,
        )
        return 1

    # Leading omp flags (continue/resume/session-dir/profile) pass through.
    # A trailing message implies one-shot mode (--print); flags alone keep the
    # interactive TUI/picker. Hand the terminal over wholesale either way.
    flags, message = _split_flags(rest)
    if message:
        # One-shot: answer printed to stdout, then exit.
        os.execvp(
            str(launcher),
            [str(launcher), "run", agent, *flags, "--print", *message],
        )
    else:
        # Flags alone: interactive TUI / session picker owns the terminal.
        os.execvp(str(launcher), [str(launcher), "run", agent, *flags])


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
