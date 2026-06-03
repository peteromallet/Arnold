"""Loop-stop predicates for pattern_dynamic and similar control loops.

Relocated to :mod:`arnold.pipeline.pattern_stops` in M3a.
This module re-exports as a compatibility bridge.

M3a compatibility bridge; delete in M7.
"""

from __future__ import annotations

# M3a compatibility bridge; delete in M7
from arnold.pipeline.pattern_stops import (  # noqa: F401  # re-export
    LoopState,
    _history,
    max_iters,
    no_improvement,
    plateau,
    threshold_reached,
)
