#!/usr/bin/env python3
"""Back-compat wrapper for the first-class `vibecomfy debug` command."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from vibecomfy.commands._agent_edit_debug import main


if __name__ == "__main__":
    raise SystemExit(main())
