"""Deprecated re-export bridge.

This module has moved to :mod:`arnold.pipeline.faults`.
Import from there directly.  This stub exists only for backward
compatibility and will be removed in a future release.
"""

from __future__ import annotations

import warnings

warnings.warn(
    "megaplan._pipeline.faults is deprecated; "
    "use arnold.pipeline.faults instead.",
    DeprecationWarning,
    stacklevel=2,
)

from arnold.pipeline.faults import *  # noqa: F403, E402
