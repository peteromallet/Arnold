"""Arnold CLI dispatch layer.

Routes:
* ``arnold workflow ...`` directly to ``arnold.cli.workflow``.
* ``arnold status/trace/inspect/override`` to ``arnold.cli.operators``.
* ``arnold approve/deny/cancel/resume`` to ``arnold.cli.execution``.

Legacy Megaplan subcommands are removed in M6; the only supported top-level
verbs are the workflow runtime and the operator projection commands.
"""

from __future__ import annotations

import sys
from typing import Sequence


# Commands that are implemented directly against the workflow/execution runtime.
_WORKFLOW_COMMAND = "workflow"
_OPERATOR_COMMANDS = frozenset({"status", "trace", "inspect", "override"})
_EXECUTION_COMMANDS = frozenset({"approve", "deny", "cancel", "resume"})


def cli_entry() -> None:
    """Console-script entry point registered in pyproject.toml."""
    sys.exit(main())


def main(argv: Sequence[str] | None = None) -> int:
    """Dispatch to the workflow CLI or operator commands."""
    args = list(sys.argv[1:] if argv is None else argv)
    if not args:
        _print_usage()
        return 2
    if args[0] in {"-h", "--help"}:
        _print_usage()
        return 0

    command = args[0]
    rest = args[1:]

    if command == _WORKFLOW_COMMAND:
        from arnold.cli.workflow import main as _workflow_main

        return _workflow_main(rest)

    if command in _OPERATOR_COMMANDS:
        from arnold.cli.operators import main as _operators_main

        return _operators_main([command, *rest])

    if command in _EXECUTION_COMMANDS:
        from arnold.cli.execution import main as _execution_main

        return _execution_main([command, *rest], prog="arnold")

    print(f"arnold: unknown command {command!r}", file=sys.stderr)
    _print_usage(file=sys.stderr)
    return 2


def _print_usage(*, file=None) -> None:  # type: ignore[no-untyped-def]
    target = file or sys.stdout
    print(
        "usage: arnold workflow {check,manifest,dot,dry-run,run,resume,describe} | "
        "arnold {status,trace,inspect,override,approve,deny,cancel,resume}",
        file=target,
    )


__all__ = ["cli_entry", "main"]
