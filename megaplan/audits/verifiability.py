"""Compatibility facade for the canonical audit verifiability module.

.. deprecated::
    Use ``from arnold.pipelines.megaplan.audits.verifiability import ...`` instead.
    This module will be removed in a future milestone.
"""

from __future__ import annotations

import warnings

warnings.warn(
    "megaplan.audits.verifiability is deprecated; "
    "use arnold.pipelines.megaplan.audits.verifiability instead.",
    DeprecationWarning,
    stacklevel=2,
)

from arnold.pipelines.megaplan.audits.verifiability import *  # noqa: F401,F403,E402

__all__ = [
    "ALL_CAPABILITIES",
    "CriterionAudit",
    "HUMAN_CAPABILITIES",
    "audit_criteria",
    "classify_criteria",
    "validate_requires",
]
