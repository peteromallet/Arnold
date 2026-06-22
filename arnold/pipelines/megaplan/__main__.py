"""Allow running as ``python -m arnold.pipelines.megaplan`` (M4 parity shim)."""

import sys

from arnold_pipelines.megaplan.cli import main

sys.exit(main())
