"""Arnold console entry point (restored for backward compatibility).

Arnold is the module-oriented namespace over the pipeline registry.
This module was consolidated into the CLI package; this shim preserves
import compatibility for existing tests.
"""

from __future__ import annotations

import sys
from typing import Sequence


UMBRELLA_OVERRIDE_ACTIONS: tuple[str, ...] = (
    "abort",
    "add-note",
    "set-robustness",
    "set-profile",
    "set-model",
    "set-vendor",
)

PLANNING_OVERRIDE_ACTIONS: tuple[str, ...] = (
    "force-proceed",
    "replan",
    "recover-blocked",
    "resume-clarify",
)

MODULE_VERBS: tuple[str, ...] = ("run", "check", "doctor", "describe", "auto")
PLANNING_MODULE_VERBS: tuple[str, ...] = (*MODULE_VERBS, "override")

PIPELINES_ACTIONS: tuple[str, ...] = ("list", "new", "check", "doctor", "describe")


def _discovered_module_names() -> set[str]:
    """Return discovered pipeline module CLI names."""
    try:
        from arnold_pipelines.megaplan._pipeline.registry import (
            discover_python_pipelines,
        )

        return {name for name, _builder, _meta, _path in discover_python_pipelines()}
    except Exception:
        # Fallback: common known modules
        return {
            "megaplan",
            "creative",
            "doc",
            "jokes",
            "epic-blitz",
            "evidence-pack",
            "live-supervisor",
            "select-tournament",
            "writing-panel-strict",
        }


def _megaplan_main(argv: list[str]) -> int:
    from arnold_pipelines.megaplan.cli import main as megaplan_main

    return megaplan_main(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if not args:
        return _print_usage_and_return()

    command = args[0]
    rest = args[1:]

    if command == "run":
        return _megaplan_main(["run", *rest])
    if command == "pipelines":
        return _handle_pipelines(rest)
    if command == "auto":
        return _handle_auto(rest)
    if command == "override":
        return _handle_umbrella_override(rest)

    modules = _discovered_module_names()
    if command in modules:
        return _handle_module_verb(command, rest)

    print(f"arnold: unknown command or module {command!r}", file=sys.stderr)
    return _print_usage_and_return(file=sys.stderr)


def _print_usage_and_return(file=None) -> int:
    from arnold_pipelines.megaplan.cli import build_parser

    if file is None:
        file = sys.stdout
    parser = build_parser()
    parser.print_usage(file)
    return 2


def _handle_pipelines(rest: list[str]) -> int:
    action = rest[0] if rest else "list"
    rest_args = rest[1:] if rest else []

    if action == "list":
        from arnold_pipelines.megaplan.cli import handle_list

        return handle_list(rest_args)
    elif action == "new":
        from arnold_pipelines.megaplan.cli import handle_initiative

        return handle_initiative(rest_args)
    elif action == "describe":
        from arnold_pipelines.megaplan.cli import handle_describe

        return handle_describe(rest_args)
    elif action in ("check", "doctor"):
        from arnold_pipelines.megaplan.cli import handle_doctor

        return handle_doctor(rest_args)
    else:
        print(f"arnold pipelines: unknown action {action!r}", file=sys.stderr)
        return 2


def _handle_auto(rest: list[str]) -> int:
    """auto command: delegates to megaplan auto."""
    cleaned = list(rest)
    # Strip 'planning' or 'megaplan' sub-command if present
    if cleaned and cleaned[0] in ("planning", "megaplan"):
        cleaned = cleaned[1:]
    return _megaplan_main(["auto", *cleaned])


def _handle_umbrella_override(rest: list[str]) -> int:
    """override command: delegates to megaplan override."""
    action = rest[0] if rest else ""
    rest_args = rest[1:] if rest else []

    if action in PLANNING_OVERRIDE_ACTIONS:
        return _megaplan_main(["override", action, *rest_args])
    elif action in UMBRELLA_OVERRIDE_ACTIONS:
        # Umbrella overrides go through megaplan
        return _megaplan_main(["override", action, *rest_args])
    else:
        if action:
            print(
                f"arnold override: unknown action {action!r}. "
                f"Use 'arnold megaplan override {action}' for megaplan-specific overrides.",
                file=sys.stderr,
            )
        return 2


def _handle_module_verb(module: str, rest: list[str]) -> int:
    """Handle a module verb command (e.g., 'megaplan run ...')."""
    verb = rest[0] if rest else "auto"
    rest_args = rest[1:] if rest else []

    if module == "megaplan":
        if verb == "override":
            return _megaplan_main(["override", *rest_args])
        return _megaplan_main([verb, *rest_args])
    else:
        # For non-megaplan modules, use the generic run path
        if verb == "run":
            return _megaplan_main(["run", module, *rest_args])
        print(f"arnold: unsupported verb {verb!r} for module {module!r}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
