#!/usr/bin/env python3
"""Final Batch 3 attempt-5 framing entry point.

The byte framing implementation is the already-sealed NBF-BATCH3-DIFF-V1
primitive from attempt 4; this immutable entry point gives the attempt-5 seal
its own explicit, reproducible command identity without changing semantics.
"""
from __future__ import annotations

from nbf_batch3_attempt4_diff_v1 import main


if __name__ == "__main__":
    raise SystemExit(main())
