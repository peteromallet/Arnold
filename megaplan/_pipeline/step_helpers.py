"""Deprecated re-export bridge.

This module has moved to :mod:`arnold.pipeline.step_helpers`.
Import from there directly.  This stub exists only for backward
compatibility and will be removed in a future release.
"""

from __future__ import annotations

import warnings

warnings.warn(
    "megaplan._pipeline.step_helpers is deprecated; "
    "use arnold.pipeline.step_helpers instead.",
    DeprecationWarning,
    stacklevel=2,
)

from arnold.pipeline.step_helpers import *  # noqa: F403, E402
