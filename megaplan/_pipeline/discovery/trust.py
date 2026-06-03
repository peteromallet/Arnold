"""Deprecated re-export bridge.

This module has moved to :mod:`arnold.pipeline.discovery.trust`.
Import from there directly.  This stub exists only for backward
compatibility and will be removed in a future release.
"""

from __future__ import annotations

import warnings

warnings.warn(
    "megaplan._pipeline.discovery.trust is deprecated; "
    "use arnold.pipeline.discovery.trust instead.",
    DeprecationWarning,
    stacklevel=2,
)

from arnold.pipeline.discovery.trust import *  # noqa: F403, E402
