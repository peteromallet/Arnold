"""Allow running as ``python -m arnold.pipelines.megaplan``."""

from arnold.pipelines.megaplan.cli import main
import sys

sys.exit(main())
