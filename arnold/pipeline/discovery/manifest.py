"""M1 compatibility shim — delegates to :mod:`arnold.workflow.discovery.manifest`.

This module exists solely as a thin re-export surface so that callers
importing ``arnold.pipeline.discovery.manifest`` receive the neutral
manifest-reader primitives from the canonical workflow discovery
implementation.

.. attention::
   This is a temporary M1 compatibility shim.  It will be removed during
   M7 when implementation files are physically relocated into
   :mod:`arnold.pipeline.discovery`.
"""

from __future__ import annotations

from arnold.workflow.discovery.manifest import (
    ARNOLD_IDENTITY_SCHEMA,
    CURRENT_MAJOR,
    REQUIRED_FIELDS,
    Manifest,
    ManifestError,
    derive_runtime_pipeline_id,
    read_manifest,
)

__all__ = [
    "ARNOLD_IDENTITY_SCHEMA",
    "CURRENT_MAJOR",
    "REQUIRED_FIELDS",
    "Manifest",
    "ManifestError",
    "derive_runtime_pipeline_id",
    "read_manifest",
]
