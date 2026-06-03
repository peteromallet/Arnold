"""Type aliases used as contracts by the pipeline pattern library.

Relocated to :mod:`arnold.pipeline.pattern_types` in M3a.
This module re-exports as a compatibility bridge.

M3a compatibility bridge; delete in M7.
"""

from __future__ import annotations

# M3a compatibility bridge; delete in M7
from arnold.pipeline.pattern_types import (  # noqa: F401  # re-export
    JoinFn,
    PromoteFn,
)
