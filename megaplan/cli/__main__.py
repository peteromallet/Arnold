"""Allow running as `python -m megaplan.cli` after the package split."""

from . import main

raise SystemExit(main())
