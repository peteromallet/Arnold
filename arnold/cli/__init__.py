"""Arnold CLI thin dispatch layer.

Lazily delegates to the canonical CLI logic in
``arnold.pipelines.megaplan.cli.arnold`` so that ``arnold`` and
``python -m arnold`` work without eagerly importing the entire plugin tree.
"""

from __future__ import annotations

import sys
from typing import Sequence


def cli_entry() -> None:
    """Console-script entry point registered in pyproject.toml."""
    sys.exit(main())


def main(argv: Sequence[str] | None = None) -> int:
    """Lazy dispatch to the canonical Arnold CLI implementation."""
    from arnold.pipelines.megaplan.cli.arnold import main as _arnold_main

    return _arnold_main(argv)
