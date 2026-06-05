"""Deprecation forwarder: ``megaplan`` console script → ``arnold``.

Keeps the legacy ``megaplan`` console-script entry point alive while
printing a deprecation warning to stderr and delegating to ``arnold``.
"""

from __future__ import annotations

import sys

_DEPRECATION_MESSAGE = "megaplan: this command is deprecated, use arnold instead."


def megaplan_entry() -> None:
    """Console-script entry point registered in pyproject.toml.

    Prints a deprecation warning to stderr, then delegates to
    ``arnold.cli.main()`` and exits with the returned exit code.
    """
    print(_DEPRECATION_MESSAGE, file=sys.stderr)
    from arnold.cli import main as _arnold_main

    sys.exit(_arnold_main())
