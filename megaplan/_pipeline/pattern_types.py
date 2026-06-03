"""Deprecated re-export bridge.

This module has moved to :mod:`arnold.pipeline.pattern_types`.
Import from there directly.  This stub exists only for backward
compatibility and will be removed in a future release.
"""

from __future__ import annotations

import warnings

warnings.warn(
    "megaplan._pipeline.pattern_types is deprecated; "
    "use arnold.pipeline.pattern_types instead.",
    DeprecationWarning,
    stacklevel=2,
)

from arnold.pipeline.pattern_types import *  # noqa: F403, E402
