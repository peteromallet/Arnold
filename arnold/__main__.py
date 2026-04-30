"""Package entry point for ``python -m arnold``."""

from __future__ import annotations

from arnold.cli import main


if __name__ == "__main__":
    raise SystemExit(main())
