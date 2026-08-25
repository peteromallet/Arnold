"""Interactive first-run onboarding flow (Batch 3).

Composes :mod:`agentbox.onboarding.detect` (what already exists) with
:mod:`agentbox.onboarding.wire` (persist + verify). North Star rules baked
in here:

- Detect before asking: the menu is bucketed ready / found / missing and
  ranked by the catalog order from the scan.
- One verified route is success: the loop only exits 0 when at least one
  route passed ``wire.verify_route``; a half-wired state never exits 0.
- Never re-prompt: accepted credentials land in omp's own stores via the
  wire helpers; provenance is recorded for every acceptance.
- Secrets are masked: pasted keys are read through a stdin-based hidden
  read (plain line for testability) and NEVER echoed to any output sink;
  every failure string printed comes from wire's redacted detail fields.
- Headless stays fail-closed: non-TTY prints one hint line and exits 2
  without touching anything.

All screen output goes through the injectable ``stdout`` callable and all
input through the injectable ``stdin`` callable — no bare ``input()`` /
``print()`` inside :func:`run_flow`, so tests script whole sessions.
"""

from __future__ import annotations

import os
import sys
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from agentbox.onboarding import detect
from agentbox.onboarding.catalog import PROVIDERS
from agentbox.onboarding.guards import should_offer
from agentbox.onboarding.detect import CANDIDATE, MISSING, READY, ScanReport
from agentbox.onboarding.wire import (
    WireResult,
    record_provenance,
    verify_route,
    wire_api_key,
    wire_cli_proxy,
    wire_oauth,
)

__all__ = ["FlowResult", "offer_and_repreflight", "run_flow", "should_offer"]

_NON_INTERACTIVE_HINT = (
    "Non-interactive shell; run `arnold` in a terminal to set up providers."
)
_MAX_VERIFY_ATTEMPTS = 3


@dataclass(frozen=True)
class FlowResult:
    """Outcome of one interactive flow run."""

    exit_code: int  # 0 >=1 verified route | 1 cancelled | 2 non-TTY
    wired_provider: str | None = None
    route: str | None = None
    verified: bool = False


# ---------------------------------------------------------------------------
# Guard: should the interactive offer happen at all?
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Injectable I/O
# ---------------------------------------------------------------------------

class _IO:
    """Thin stdin/stdout shim; EOF surfaces as ``None``, never an exception."""

    def __init__(
        self,
        stdin: Callable[[], str],
        stdout: Callable[[str], None],
    ) -> None:
        self._stdin = stdin
        self._stdout = stdout

    def say(self, text: str = "") -> None:
        self._stdout(text)

    def ask(self, prompt: str) -> str | None:
        self.say(prompt)
        try:
            return self._stdin()
        except EOFError:
            return None

    def ask_secret(self, prompt: str) -> str | None:
        """Read a secret with terminal echo suppressed on a real TTY.

        Falls back to the injectable plain-line path when stdin is not a TTY
        (piped/scripted sessions), so tests stay deterministic while interactive
        pastes are never echoed.
        """
        self.say(prompt)
        if sys.stdin.isatty():
            secret = _read_hidden()
            if secret is None:
                return None
            self.say("")  # newline consumed invisibly by the hidden read
            return secret
        try:
            return self._stdin()
        except EOFError:
            return None


def _read_hidden() -> str | None:
    """Read one line with echo disabled; None means cancelled.

    Uses termios directly so the characters never reach the screen. Raises
    nothing: KeyboardInterrupt is converted to cancellation like EOF.
    """
    import os as _os
    import termios
    import tty

    fd = 0  # stdin; callers may dup2 a pty slave onto it
    saved = termios.tcgetattr(fd)
    buf = bytearray()
    try:
        tty.setcbreak(fd)
        while True:
            raw = _os.read(fd, 1)
            if not raw:  # EOF -> cancellation, never a busy loop
                return None
            ch = raw.decode("utf-8", errors="replace") if raw[0] < 0x80 else None
            if ch is not None and ch in ("\n", "\r"):
                return buf.decode("utf-8", errors="replace")
            if ch == "\x7f" or ch == "\x08":  # DEL/Backspace
                if buf:
                    del buf[-1:]  # drop one BYTE; multi-byte tail re-decodes on submit
                continue
            if ch == "\x03":  # ETX == Ctrl-C in cbreak mode
                return None
            buf += raw  # bytes buffered whole so multi-byte UTF-8 survives
    except KeyboardInterrupt:
        return None
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, saved)


def _declined(answer: str | None) -> bool:
    """n/no/q or EOF count as decline everywhere."""
    if answer is None:
        return True
    return answer.strip().lower() in ("n", "no", "q")


def _confirmed(answer: str | None) -> bool:
    """Empty input counts as Yes where the prompt says [Y/n]."""
    if answer is None:
        return False
    return answer.strip().lower() in ("", "y", "yes")


def _default_agent_dir(environ: Mapping[str, str] = os.environ) -> Path:
    override = environ.get("PI_CODING_AGENT_DIR")
    if override:
        return Path(override)
    home = environ.get("HOME") or str(Path.home())
    return Path(home) / ".omp" / "agent"


class _Cancelled(Exception):
    """User declined/cancelled at a prompt."""


# Outcome sentinels of one S2->S4 configure round for a single provider.
_OK = "ok"  # payload carries (pid, verified route)
_MENU = "menu"  # go back to the provider menu
_STOP = "stop"  # user declined / gave up entirely


# ---------------------------------------------------------------------------
# Screens
# ---------------------------------------------------------------------------

def _menu_entries(
    report: ScanReport,
    configured: set[str],
    show_all: bool,
) -> list[detect.ProviderScan]:
    entries = [
        p
        for p in report.providers
        if p.id not in configured and p.status in (READY, CANDIDATE)
    ]
    if show_all:
        entries += [
            p
            for p in report.providers
            if p.id not in configured and p.status == MISSING
        ]
    return entries


def _render_menu(
    io_: _IO,
    report: ScanReport,
    configured: set[str],
    show_all: bool,
) -> list[detect.ProviderScan]:
    """S0 header + S1 bucketed menu. Returns the currently listed entries."""
    io_.say("Welcome to Arnold! Let's find a working model route for you.")
    ready = [p for p in report.providers if p.status == READY]
    found = [p for p in report.providers if p.status == CANDIDATE]
    missing_n = sum(1 for p in report.providers if p.status == MISSING)
    io_.say(
        f"Scanned this machine: {len(ready)} ready, "
        f"{len(found)} found-but-unwired, {missing_n} missing."
    )
    io_.say("Pick what to set up (found/ready first):")

    entries = _menu_entries(report, configured, show_all)
    last_status: str | None = None
    for idx, entry in enumerate(entries, start=1):
        if entry.status != last_status:
            last_status = entry.status
            if entry.status == READY:
                io_.say("Ready now:")
            elif entry.status == CANDIDATE:
                io_.say("Found (needs a step to wire):")
            else:
                io_.say("Missing (nothing detected):")
        origin = (
            f" ({entry.origin.kind}: {entry.origin.detail})"
            if entry.origin
            else ""
        )
        marker = "  <- recommended" if idx == 1 else ""
        io_.say(f"  {idx}. {entry.id} [{entry.status}]{origin}{marker}")
    if not entries:
        io_.say("  (nothing detected yet)")
    if not show_all and missing_n:
        io_.say(f"  s. show everything ({missing_n} more hidden)")
    elif show_all:
        io_.say("  s. hide missing providers")
    if (
        "openrouter" not in configured
        and "openrouter" not in {e.id for e in entries}
        and "openrouter" in PROVIDERS
    ):
        io_.say(
            "  o. Set up OpenRouter (one key, hundreds of models — openrouter.ai)"
        )
    return entries


def _pick_provider(io_: _IO, report: ScanReport, configured: set[str]) -> str | None:
    """S1 prompt loop. Returns provider id, 'openrouter', or None on decline."""
    show_all = False
    while True:
        entries = _render_menu(io_, report, configured, show_all)
        raw = io_.ask("Number, 's' to toggle hidden, or 'n' to skip setup: ")
        if raw is None or _declined(raw):
            return None
        text = raw.strip().lower()
        if text == "s":
            show_all = not show_all
            continue
        if text == "o" and "openrouter" not in {e.id for e in entries}:
            return "openrouter"
        if text.isdigit():
            idx = int(text)
            if 1 <= idx <= len(entries):
                return entries[idx - 1].id
        io_.say("Pick a number from the list, 's' to toggle, or 'n' to skip.")


def _wire_once(pid: str, *, io_: _IO, agent_dir: Path) -> tuple[WireResult, str]:
    """S2: wire according to the catalog auth_kinds (api_key > oauth > cli_proxy).

    Returns ``(result, api_key)``; ``api_key`` is the pasted key (only for the
    api_key route) so the caller can thread it into verification redaction.
    """
    spec = PROVIDERS[pid]
    kinds = spec.auth_kinds
    env_label = "/".join(spec.env_keys) or f"{pid} API key"
    if "api_key" in kinds:
        key = io_.ask_secret(
            f"Paste your {env_label} key (input hidden; Enter=cancel): "
        )
        if key is None or not key.strip():
            raise _Cancelled()
        return wire_api_key(
            pid,
            key.strip(),
            agent_dir=agent_dir,
            origin_kind="manual-entry",
            origin_detail=f"interactive onboarding ({env_label})",
        ), key.strip()
    if "oauth" in kinds:
        return wire_oauth(pid, agent_dir=agent_dir), ""
    if "cli_proxy" in kinds:
        return wire_cli_proxy(
            pid, source=f"foreign CLI store ({pid})", agent_dir=agent_dir
        ), ""
    return WireResult(
        ok=False,
        provider=pid,
        mechanism="none",
        detail=f"no supported wiring kind for {pid!r}",
        provenance={},
    ), ""


def _configure_provider(
    pid: str,
    *,
    io_: _IO,
    agent_dir: Path,
) -> tuple[str, tuple[str, str]]:
    """S2->S4 loop for one provider (max 3 verify attempts).

    Returns ``(_OK, (pid, verified_route))``, or ``(_MENU, ...)`` to pick a
    different provider, or ``(_STOP, ...)`` when the user declines/gives up.
    Never reports success without a passing verification.
    """
    default_route = PROVIDERS[pid].default_route
    for _attempt in range(1, _MAX_VERIFY_ATTEMPTS + 1):
        try:
            result, api_key = _wire_once(pid, io_=io_, agent_dir=agent_dir)
        except _Cancelled:
            return (_STOP, ("", ""))
        if not result.ok:
            io_.say(f"Wiring failed: {result.detail}")
            if not _confirmed(io_.ask("Try again? [Y/n] ")):
                return (_STOP, ("", ""))
            continue
        # S3 model pick — default preselected.
        raw = io_.ask(f"Model [{default_route}] (Enter=keep): ")
        if raw is None:
            return (_STOP, ("", ""))
        route = raw.strip() or default_route
        verdict = verify_route(route, agent_dir=agent_dir, secrets=(api_key,) if api_key else ())
        if verdict.ok:
            record_provenance(agent_dir, [dict(result.provenance, route=route)])
            return (_OK, (pid, route))
        io_.say(f"Verification failed for {route}: {verdict.output}")
        ans = io_.ask("[Enter=try again] d=different provider, n=give up: ")
        if ans is None or _declined(ans):
            return (_STOP, ("", ""))
        if ans.strip().lower() == "d":
            return (_MENU, ("", ""))
    io_.say(
        f"Giving up on {pid} after {_MAX_VERIFY_ATTEMPTS} attempts "
        "(nothing marked verified)."
    )
    return (_STOP, ("", ""))


def _run_flow(
    *,
    scan: ScanReport | None,
    io_: _IO,
    agent_dir: Path,
) -> FlowResult:
    # S0 header + detection scan (reuse detect.scan_providers unless injected).
    report = scan if scan is not None else detect.scan_providers()

    configured: dict[str, str] = {}  # pid -> verified route
    last: tuple[str, str] | None = None
    while True:
        picked = _pick_provider(io_, report, set(configured))
        if picked is None:
            break
        outcome, payload = _configure_provider(
            picked, io_=io_, agent_dir=agent_dir
        )
        if outcome == _MENU:
            continue
        if outcome == _STOP:
            break
        pid, route = payload
        configured[pid] = route
        last = (pid, route)
        # S5 success screen.
        io_.say(f"Verified route: {route}")
        io_.say(
            f"Saved into omp's own store under {agent_dir} — future launches "
            "reuse it silently, you will never be asked again."
        )
        io_.say(
            "Provenance recorded in "
            f"{Path(agent_dir) / '.arnold_onboarding_provenance.jsonl'} "
            "(origin: onboarding)."
        )
        again = io_.ask("Add another provider now? [y/N] ")
        if again is None or again.strip().lower() not in ("y", "yes"):
            break
    if last is not None:
        return FlowResult(0, last[0], last[1], True)
    return FlowResult(1)


def run_flow(
    *,
    scan: ScanReport | None = None,
    stdin: Callable[[], str] = input,
    stdout: Callable[[str], None] = print,
    agent_dir=None,
    stdin_tty: bool | None = None,
    stderr_tty: bool | None = None,
) -> FlowResult:
    """Run the interactive screens S0-S5.

    Exit contract: 0 >= 1 verified route; 1 cancelled; 2 non-TTY (prints
    one hint line). All omp subprocess traffic goes through the pinned
    seams in :mod:`agentbox.onboarding.wire`.
    """
    if stdin_tty is None:
        stdin_tty = sys.stdin.isatty()
    if stderr_tty is None:
        stderr_tty = sys.stderr.isatty()
    resolved_dir = Path(agent_dir) if agent_dir is not None else _default_agent_dir()
    io_ = _IO(stdin, stdout)
    try:
        if not (stdin_tty and stderr_tty):
            stdout(_NON_INTERACTIVE_HINT)
            return FlowResult(2)
        return _run_flow(scan=scan, io_=io_, agent_dir=resolved_dir)
    except (EOFError, KeyboardInterrupt):
        # Decline semantics anywhere in the flow; never half-wired success.
        return FlowResult(1)


# ---------------------------------------------------------------------------
# Post-failure offer + re-preflight
# ---------------------------------------------------------------------------

def offer_and_repreflight(
    *,
    stdin_tty: bool,
    stderr_tty: bool,
    message: bool,
    flags: Sequence[str],
    repreflight: Callable[[], bool],
    environ: Mapping[str, str] = os.environ,
    agent_dir=None,
    summary_lines: Sequence[str] = (),
) -> bool | None:
    """Offer the flow after a credential preflight failure.

    Returns:
      None          -- guards failed, user declined, the flow didn't verify,
                       or invoking the omp binary raised FileNotFoundError /
                       OSError (old-pin fallback: print nothing extra; the
                       caller falls through to its original failure path)
      True / False  -- repreflight() verdict after a verified flow (exit 0)

    paths keep failing closed byte-for-byte (North Star).
    """
    if not should_offer(
        stdin_tty=stdin_tty,
        stderr_tty=stderr_tty,
        message=message,
        flags=flags,
        environ=environ,
    ):
        return None
    for line in summary_lines:
        print(line)
    try:
        answer = input("Set up providers now? [Y/n] ")
    except (EOFError, KeyboardInterrupt, OSError):
        # OSError covers closed/captured stdin (pytest capture) — decline.
        return None
    if answer.strip().lower() in ("n", "no", "q"):
        return None
    try:
        result = run_flow(agent_dir=agent_dir)
    except OSError:
        # OLD-PIN FALLBACK: omp binary absent/broken during flow startup.
        return None
    if result.exit_code != 0:
        return None
    return bool(repreflight())
