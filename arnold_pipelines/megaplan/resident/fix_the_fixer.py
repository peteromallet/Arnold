"""Discord command boundary for the resident fix-the-fixer capability."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import runpy
import shlex


FIX_THE_FIXER_COMMAND = "/fix-the-fixer"
FIX_THE_FIXER_APPLICATION_COMMAND = "fix-the-fixer"
FIX_THE_FIXER_TOOL = "fix_the_fixer"
FIX_THE_FIXER_USAGE = '/fix-the-fixer --target "EPIC_OR_SESSION_TEXT"'
FIX_THE_FIXER_DESCRIPTION = (
    "Launch one durable high-risk meta-fixer for an epic or session target."
)
_RENDERER = (
    Path(__file__).resolve().parents[1]
    / "skills/fix-the-fixer/scripts/render_goal.py"
)


def validate_fix_the_fixer_target(value: str) -> str:
    if not value.strip():
        raise ValueError("--target must contain epic or session text")
    if "\x00" in value:
        raise ValueError("--target must not contain NUL")
    return value


def render_fix_the_fixer_goal(target: str) -> str:
    """Load the skill's standalone renderer so its goal contract stays canonical."""

    namespace = runpy.run_path(str(_RENDERER))
    renderer = namespace.get("render_goal")
    if not callable(renderer):
        raise RuntimeError("fix-the-fixer goal renderer is unavailable")
    return str(renderer(validate_fix_the_fixer_target(target)))


@dataclass(frozen=True)
class FixTheFixerCommand:
    target: str | None = None
    error: str | None = None

    def resident_payload(self) -> dict[str, object]:
        payload: dict[str, object] = {"name": FIX_THE_FIXER_TOOL}
        if self.target is not None:
            payload["arguments"] = {"target": self.target}
        if self.error is not None:
            payload["error"] = self.error
        return payload


def resident_command_catalog() -> tuple[dict[str, str], ...]:
    """Return the discoverable direct Discord command catalog."""

    return (
        {
            "name": FIX_THE_FIXER_COMMAND,
            "usage": FIX_THE_FIXER_USAGE,
            "resident_tool": FIX_THE_FIXER_TOOL,
            "description": (
                "Launch exactly one durable, mutation-authorized high-risk meta-fixer "
                "for the identified epic or session."
            ),
        },
    )


def parse_fix_the_fixer_command(content: str) -> FixTheFixerCommand | None:
    """Parse one strict command while retaining the decoded target byte-for-byte."""

    try:
        arguments = shlex.split(content, posix=True)
    except ValueError as exc:
        if content.lstrip().startswith(FIX_THE_FIXER_COMMAND):
            return FixTheFixerCommand(error=f"invalid quoting: {exc}; usage: {FIX_THE_FIXER_USAGE}")
        return None
    if not arguments or arguments[0] != FIX_THE_FIXER_COMMAND:
        return None

    target: str | None = None
    if len(arguments) == 3 and arguments[1] == "--target":
        target = arguments[2]
    elif len(arguments) == 2 and arguments[1].startswith("--target="):
        target = arguments[1].partition("=")[2]
    else:
        return FixTheFixerCommand(
            error=f"exactly one non-empty --target text flag is required; usage: {FIX_THE_FIXER_USAGE}"
        )
    try:
        validate_fix_the_fixer_target(target)
    except ValueError as exc:
        return FixTheFixerCommand(error=f"{exc}; usage: {FIX_THE_FIXER_USAGE}")
    return FixTheFixerCommand(target=target)
