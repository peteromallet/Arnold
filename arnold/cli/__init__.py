"""Arnold CLI thin dispatch layer.

Routes:
* ``arnold workflow ...`` directly to ``arnold.cli.workflow`` without importing
  legacy Megaplan CLI modules.
* ``arnold status/trace/inspect/override`` to ``arnold.cli.operators``.
* All other commands lazily delegate to the legacy Megaplan CLI for the M5
  transition window.
"""

from __future__ import annotations

import sys
from typing import Sequence


# Commands that are implemented directly against the workflow/execution runtime.
_WORKFLOW_COMMAND = "workflow"
_OPERATOR_COMMANDS = frozenset({"status", "trace", "inspect", "override"})


def cli_entry() -> None:
    """Console-script entry point registered in pyproject.toml."""
    sys.exit(main())


def main(argv: Sequence[str] | None = None) -> int:
    """Lazy dispatch to the appropriate CLI implementation."""
    args = list(sys.argv[1:] if argv is None else argv)
    if not args:
        _print_usage()
        return 2

    command = args[0]
    rest = args[1:]

    if command == _WORKFLOW_COMMAND:
        from arnold.cli.workflow import main as _workflow_main

        return _workflow_main(rest)

    if command in _OPERATOR_COMMANDS:
        from arnold.cli.operators import main as _operators_main

        return _operators_main([command, *rest])

    # Legacy Megaplan CLI surface: imported lazily and only for commands that
    # have not yet been migrated to the workflow runtime.
    from arnold.pipelines.megaplan.cli.arnold import main as _arnold_main

    return _arnold_main(argv)


def _print_usage(*, file=None) -> None:  # type: ignore[no-untyped-def]
    target = file or sys.stdout
    print(
        "usage: arnold workflow {check,manifest,dot,dry-run,run,resume,describe} | "
        "arnold {status,trace,inspect,override} | "
        "arnold <legacy command> ...",
        file=target,
    )


__all__ = ["cli_entry", "main"]
