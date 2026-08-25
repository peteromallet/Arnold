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
import subprocess
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
  --onboard        run provider setup, then exit (also works when already set up)
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


# Branded omp build: the local oh-my-pi fork compiled as a standalone binary.
# Preferred over stock `omp` so the CLI surface (version string, terminal tab
# title, status line) carries Arnold branding. OMP_BIN set in the environment
# always wins; ARNOLD_STOCK_OMP=1 opts out entirely.
_BRANDED_OMP = Path.home() / "Documents" / "oh-my-pi" / "packages" / "coding-agent" / "dist" / "omp"


def _resolve_omp_bin(env=None) -> str | None:
    """Resolve which ``omp`` binary a launch would use.

    Preference mirrors _select_omp_bin: an explicit OMP_BIN override wins,
    then the branded build (unless ARNOLD_STOCK_OMP=1), then PATH. Returns
    None when nothing resolves; callers decide what that means for them.
    """
    target = os.environ if env is None else env
    override = target.get("OMP_BIN")
    if override:
        return override
    if target.get("ARNOLD_STOCK_OMP") != "1" and _BRANDED_OMP.is_file():
        return str(_BRANDED_OMP)
    return shutil.which("omp")


def _omp_supports_onboard(omp_bin: str) -> bool:
    """Probe whether this omp build ships the ``onboard`` subcommand.

    Exit 0/2 from ``omp onboard --help`` counts as supported (argparse uses 2
    for unknown commands, so anything else — or any spawn failure/timeouts —
    means the build predates onboarding and the caller should fall back).
    """
    try:
        proc = subprocess.run(
            [omp_bin, "onboard", "--help"],
            capture_output=True,
            timeout=15,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return proc.returncode in (0, 2)


def _select_omp_bin(env=None) -> None:
    """Point the agent launcher at the branded build when it exists."""
    target = os.environ if env is None else env
    resolved = _resolve_omp_bin(target)
    if resolved and target.get("ARNOLD_STOCK_OMP") != "1":
        target.setdefault("OMP_BIN", resolved)

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


def _identity_label(agent: str) -> str:
    """Short role label for the header line: default persona vs custom agent."""
    return "AgentBox Operator" if agent == DEFAULT_AGENT else f"agent · {agent}"


def _one_shot_header(agent: str) -> str:
    """Branded identity line shown at the top of a one-shot run."""
    return f"arnold · {_identity_label(agent)}"


def _print_one_shot_header(agent: str, stream=None) -> None:
    """Brand the top of a one-shot run before omp takes over the terminal.

    omp's print mode owns stdout and writes its own status to stderr, so the
    identity line goes to stderr too, landing above 'Working...'. The terminal
    tab title gets the same brand via OSC 0. The interactive TUI clears the
    screen and sets its own title, so this only runs for one-shot messages.
    Skipped entirely when stderr is not a terminal so piped output stays clean.
    Flushed explicitly: os.execvp replaces the process without flushing.
    """
    stream = sys.stderr if stream is None else stream
    if not stream.isatty():
        return
    print(f"\x1b]0;{_one_shot_header(agent)}\x07", end="", file=stream, flush=True)
    print(f"\x1b[1m{_one_shot_header(agent)}\x1b[0m", file=stream, flush=True)


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
    # --onboard: run the provider-onboarding flow on demand and exit. Works
    # regardless of what is already configured so it doubles as a test entry.
    if "--onboard" in rest:
        rest.remove("--onboard")
        if rest:
            print(
                "arnold: --onboard takes no other arguments",
                file=sys.stderr,
            )
            return 1
        # Prefer the native `omp onboard` experience when an omp binary
        # resolves (same preference as _select_omp_bin) and this build ships
        # the subcommand. Hand the terminal over wholesale via execvp; if the
        # exec itself fails, drop to the Python flow rather than dying.
        omp_bin = _resolve_omp_bin()
        if omp_bin is not None and _omp_supports_onboard(omp_bin):
            try:
                os.execvp(omp_bin, [omp_bin, "onboard"])
            except OSError:
                pass  # fall through to the Python flow below
        from agentbox.onboarding.flow import run_flow

        return run_flow().exit_code

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

    # First-run provider onboarding: strictly an interactive-terminal offer,
    # gated on zero ready routes so configured machines are never nagged.
    # Onboarding must NEVER break a launch — any failure proceeds silently.
    try:
        # guards.py is stdlib-only: evaluating the gate must not pay the
        # onboarding import cost on any launch that can never offer.
        from agentbox.onboarding.guards import should_offer

        stdin_tty, stderr_tty = sys.stdin.isatty(), sys.stderr.isatty()
        guards = dict(
            stdin_tty=stdin_tty,
            stderr_tty=stderr_tty,
            message=bool(message),
            flags=flags,
        )
        if should_offer(**guards):
            from agentbox.onboarding.detect import READY, scan_providers

            def _route_ready() -> bool:
                return any(p.status == READY for p in scan_providers().providers)

            if not _route_ready():
                from agentbox.onboarding.flow import offer_and_repreflight

                offer_and_repreflight(**guards, repreflight=_route_ready)
    except Exception:
        pass

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
        _print_one_shot_header(agent)
    _select_omp_bin()
    # Hand the terminal over wholesale either way.
    os.execvp(str(launcher), exec_argv)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
