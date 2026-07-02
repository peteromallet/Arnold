"""M1 compatibility shim — delegates to :mod:`arnold.workflow.validator`.

This module exists solely as a thin re-export surface so that callers
importing ``arnold.pipeline.validator`` receive the neutral graph-shape
and control-flow validation functions from the canonical workflow
implementation.

.. attention::
   This is a temporary M1 compatibility shim.  It will be removed during
   M7 when implementation files are physically relocated into
   :mod:`arnold.pipeline`.
"""

from __future__ import annotations

from arnold.workflow.validator import (
    validate,
    validate_control_flow,
    validate_dataflow_paths,
    validate_execution_resources,
    validate_invocation_requirements,
    validate_manifest_context,
    validate_resource_dependencies,
)

__all__ = [
    "validate",
    "validate_control_flow",
    "validate_dataflow_paths",
    "validate_execution_resources",
    "validate_invocation_requirements",
    "validate_manifest_context",
    "validate_resource_dependencies",
]
