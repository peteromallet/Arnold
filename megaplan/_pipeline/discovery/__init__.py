"""Deprecated re-export bridge for megaplan._pipeline.discovery.

This package has moved to :mod:`arnold.pipeline.discovery`.
Import from there directly.  This stub exists only for backward
compatibility and will be removed in a future release.
"""

from __future__ import annotations

import warnings

warnings.warn(
    "megaplan._pipeline.discovery is deprecated; "
    "use arnold.pipeline.discovery instead.",
    DeprecationWarning,
    stacklevel=2,
)

from arnold.pipeline.discovery import *  # noqa: F403, E402, F401
