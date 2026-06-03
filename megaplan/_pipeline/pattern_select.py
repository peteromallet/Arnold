"""Selection primitives for tournament-style reduces.

Relocated to :mod:`arnold.pipeline.pattern_select` in M3a.
This module re-exports as a compatibility bridge.

M3a compatibility bridge; delete in M7.
"""

from __future__ import annotations

# M3a compatibility bridge; delete in M7
from arnold.pipeline.pattern_select import (  # noqa: F401  # re-export
    SelectionRule,
    _coerce,
    select,
    threshold,
    top_1,
    top_k,
)
