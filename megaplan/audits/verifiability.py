"""Deprecated compatibility shim — canonical implementation in :mod:`megaplan.orchestration.verifiability`.

.. deprecated::
    Use ``from megaplan.orchestration.verifiability import ...`` instead.
    This module will be removed in a future milestone.

This module used to hold a near-duplicate of the verifiability audit code that
differed by exactly one import line (it pulled ``ALL_CAPABILITIES`` /
``HUMAN_CAPABILITIES`` from :mod:`megaplan.audits.capabilities` instead of the
canonical capability registry). Now that :mod:`megaplan.audits.capabilities` is
itself a shim over :mod:`megaplan.runtime.capabilities`, both copies resolve to
the same source and the divergence is collapsed. The file is kept as a thin
re-export so external callers like
``from megaplan.audits.verifiability import X`` keep working.
"""

from __future__ import annotations

import warnings

warnings.warn(
    "megaplan.audits.verifiability is deprecated; "
    "use megaplan.orchestration.verifiability instead.",
    DeprecationWarning,
    stacklevel=2,
)

from megaplan.orchestration.verifiability import *  # noqa: F401,F403,E402

__all__ = [
    "ALL_CAPABILITIES",
    "CriterionAudit",
    "HUMAN_CAPABILITIES",
    "audit_criteria",
    "classify_criteria",
    "validate_requires",
]
