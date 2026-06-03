"""Deprecated re-export bridge.

This module has moved to :mod:`arnold.pipeline.subloop`.
Import from there directly.  This stub exists only for backward
compatibility and will be removed in a future release.
"""

from __future__ import annotations

import warnings

warnings.warn(
    "megaplan._pipeline.subloop is deprecated; "
    "use arnold.pipeline.subloop instead.",
    DeprecationWarning,
    stacklevel=2,
)

from arnold.pipeline.subloop import *  # noqa: F403, E402
