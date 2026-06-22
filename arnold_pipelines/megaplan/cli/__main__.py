"""Allow running as `python -m arnold_pipelines.megaplan.cli` after the package split."""

from . import main

raise SystemExit(main())
