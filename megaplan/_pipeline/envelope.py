"""Deprecated re-export bridge.

This module has moved to :mod:`arnold.pipeline.envelope`.
Import from there directly.  This stub exists only for backward
compatibility and will be removed in a future release.
"""

from __future__ import annotations

import warnings

warnings.warn(
    "megaplan._pipeline.envelope is deprecated; "
    "use arnold.pipeline.envelope instead.",
    DeprecationWarning,
    stacklevel=2,
)

from arnold.pipeline.envelope import *  # noqa: F403, E402
from arnold.pipeline.envelope import _envelope_ctx, _fanout_active_ctx  # noqa: E402
