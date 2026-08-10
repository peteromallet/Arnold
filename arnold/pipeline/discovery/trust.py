"""M1 compatibility shim — delegates to :mod:`arnold.workflow.discovery.trust`.

This module exists solely as a thin re-export surface so that callers
importing ``arnold.pipeline.discovery.trust`` receive the neutral
trust-classification primitives from the canonical workflow discovery
implementation.

.. attention::
   This is a temporary M1 compatibility shim.  It will be removed during
   M7 when implementation files are physically relocated into
   :mod:`arnold.pipeline.discovery`.
"""

from __future__ import annotations

from arnold.workflow.discovery.trust import (
    BLESSED_ALLOWLIST,
    TrustGrade,
    WorkflowTrustDecision,
    WorkflowTrustEvidenceKind,
    classify,
    classify_workflow_trust,
    derive_tenant_id,
    derive_workflow_tenant_id,
)

__all__ = [
    "BLESSED_ALLOWLIST",
    "TrustGrade",
    "WorkflowTrustDecision",
    "WorkflowTrustEvidenceKind",
    "classify",
    "classify_workflow_trust",
    "derive_tenant_id",
    "derive_workflow_tenant_id",
]
