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
_PATH_FALLBACK_BLOCKLIST: tuple[str, ...] = (".grok",)


# Flags that ask for the usage text instead of an agent run.
_HELP_FLAGS = frozenset({"-h", "--help"})
_USAGE = """\
usage: arnold [flags] [message...]

Run an omp named agent. Bare = interactive session; a message = one-shot
(printed answer). Leading flags pass through to omp.

  --agent NAME     talk to a different installed agent (default: arnold)
  -c               continue the most recent conversation
  --resume ID      resume a specific session
  -h, --help       show this help

Launcher: ARNOLD_AGENT_LAUNCHER env var, else ~/.bun/bin/agent.
"""


def _find_launcher() -> Path | None:
    override = os.environ.get("ARNOLD_AGENT_LAUNCHER")
    if override:
        candidate = Path(override).expanduser()
        return candidate if candidate.is_file() else None
    for candidate in _LAUNCHER_CANDIDATES:
        if candidate.is_file():
            return candidate
    on_path = shutil.which("agent")
    if on_path and not any(marker in on_path for marker in _PATH_FALLBACK_BLOCKLIST):
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
            print(
                'arnold: --agent requires a value (e.g. arnold --agent scout "hi")',
                file=sys.stderr,
            )
            return 1
        agent = rest.pop(index)
    # Leading omp flags (continue/resume/session-dir/profile) pass through.
    # A trailing message implies one-shot mode (--print); flags alone keep the
    # interactive TUI/picker.
    flags, message = _split_flags(rest)

    if not message and _HELP_FLAGS.intersection(flags):
        print(_USAGE, end="")
        return 0

    if any(token.startswith("-") for token in message):
        print(
            'arnold: flags must precede the message, e.g. arnold -c "follow-up"',
            file=sys.stderr,
        )
        return 1

    launcher = _find_launcher()
    if launcher is None:
        print(
            "arnold: could not locate the omp agent launcher. Install oh-my-pi "
            "(~/.bun/bin/agent) or point ARNOLD_AGENT_LAUNCHER at its 'agent' script.",
            file=sys.stderr,
        )
        return 1

    exec_argv = [str(launcher), "run", agent, *flags]
    if message:
        # One-shot: answer printed to stdout, then exit.
        exec_argv += ["--print", *message]
    # Hand the terminal over wholesale either way.
    os.execvp(str(launcher), exec_argv)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
