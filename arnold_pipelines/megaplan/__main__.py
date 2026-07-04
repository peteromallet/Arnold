"""Allow running as ``python -m arnold_pipelines.megaplan``."""

from arnold_pipelines.megaplan.cli import main
import sys

if __name__ == "__main__":
    sys.exit(main())
