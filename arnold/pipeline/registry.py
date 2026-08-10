"""M1 compatibility shim — delegates to :mod:`arnold.workflow.registry`.

This module exists solely as a thin re-export surface so that callers
importing ``arnold.pipeline.registry`` receive the neutral
:class:`PipelineRegistry` and associated protocol types from the
canonical workflow implementation.

.. attention::
   This is a temporary M1 compatibility shim.  It will be removed during
   M7 when implementation files are physically relocated into
   :mod:`arnold.pipeline`.
"""

from __future__ import annotations

from arnold.workflow.registry import (
    DiscoveryHook,
    PipelineBuilder,
    PipelineRegistry,
    RegistrationKind,
    ResourcePathPolicy,
    TrustPolicy,
)

__all__ = [
    "DiscoveryHook",
    "PipelineBuilder",
    "PipelineRegistry",
    "RegistrationKind",
    "ResourcePathPolicy",
    "TrustPolicy",
]
