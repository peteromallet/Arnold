"""Deprecated re-export bridge for megaplan._pipeline.feature_flags.

The canonical unified-dispatch flag now lives in
:mod:`arnold.pipeline.feature_flags` as ``arnold_unified_dispatch_on()``
(controlled by ``ARNOLD_UNIFIED_DISPATCH``).

This bridge provides backward compatibility by also checking the legacy
``MEGAPLAN_UNIFIED_DISPATCH`` env var, so existing consumers that have
not yet migrated continue to work.
"""

from __future__ import annotations

import os
import warnings

warnings.warn(
    "megaplan._pipeline.feature_flags is deprecated; "
    "use arnold.pipeline.feature_flags instead.",
    DeprecationWarning,
    stacklevel=2,
)

# Re-export the canonical arnold function
from arnold.pipeline.feature_flags import arnold_unified_dispatch_on  # noqa: E402, F401

# Provide the legacy megaplan function that checks BOTH env vars
from arnold.pipeline.feature_flags import arnold_unified_dispatch_on as _arnold_fn  # noqa: E402


def megaplan_unified_dispatch_on() -> bool:
    """Return ``True`` when either ``ARNOLD_UNIFIED_DISPATCH`` or
    ``MEGAPLAN_UNIFIED_DISPATCH`` is ``'1'``.

    Defaults to ``False`` (per strangler discipline: old path default-ON,
    new path default-OFF).
    """
    return (
        os.environ.get("ARNOLD_UNIFIED_DISPATCH", "0") == "1"
        or os.environ.get("MEGAPLAN_UNIFIED_DISPATCH", "0") == "1"
    )
