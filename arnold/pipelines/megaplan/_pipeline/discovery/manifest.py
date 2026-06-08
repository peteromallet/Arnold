"""Manifest reader: extract pipeline metadata without importing the module.

M3a compatibility bridge; delete in M7.

Delegates to the neutral Arnold manifest reader with the legacy
``"megaplan.pipeline-manifest.v1"`` identity schema.
"""

from __future__ import annotations

# M3a compatibility bridge; delete in M7
from arnold.pipeline.discovery.manifest import (  # noqa: F401
    CURRENT_MAJOR,
    REQUIRED_FIELDS,
    Manifest,
    ManifestError,
)
from arnold.pipeline.discovery.manifest import read_manifest as _arnold_read_manifest
from pathlib import Path
from typing import Union

# Legacy identity schema for Megaplan compatibility.
MEGAPLAN_IDENTITY_SCHEMA: str = "megaplan.pipeline-manifest.v1"


def read_manifest(module_file: Path) -> Union[Manifest, ManifestError]:
    """Read and validate a pipeline manifest from *module_file*.

    Megaplan bridge: delegates to the neutral Arnold reader with the
    legacy ``"megaplan.pipeline-manifest.v1"`` identity schema.

    M3a compatibility bridge; delete in M7.
    """
    return _arnold_read_manifest(
        module_file,
        identity_schema=MEGAPLAN_IDENTITY_SCHEMA,
    )
