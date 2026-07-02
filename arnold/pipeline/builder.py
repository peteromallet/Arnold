"""M1 compatibility shim — delegates to :mod:`arnold.workflow.builder`.

This module exists solely as a thin re-export surface so that callers
importing ``arnold.pipeline.builder`` receive the neutral
:class:`PipelineBuilder` from the canonical workflow implementation.

.. attention::
   This is a temporary M1 compatibility shim.  It will be removed during
   M7 when implementation files are physically relocated into
   :mod:`arnold.pipeline`.
"""

from __future__ import annotations

from arnold.workflow.builder import PipelineBuilder

__all__ = ["PipelineBuilder"]
