"""Allow running as `python -m arnold.pipelines.megaplan.cli` after the package split."""

from . import main

raise SystemExit(main())
