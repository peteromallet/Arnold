"""Thin module entrypoint for ``python -m arnold_pipelines.megaplan.cli.arnold``.

Delegates to the canonical CLI main path in
:mod:`arnold_pipelines.megaplan.cli` without duplicating any
implementation logic.  This exists solely so that
``python -m arnold_pipelines.megaplan.cli.arnold pipelines new ...``
reaches the same scaffold handler that ``megaplan pipelines new ...``
would invoke.
"""

from __future__ import annotations

from arnold_pipelines.megaplan.cli import main

if __name__ == "__main__":
    import sys

    sys.exit(main())
