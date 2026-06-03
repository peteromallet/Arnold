"""Discovery surface for pipeline packages.

This package owns the manifest-first, non-executing discovery contract.
See ``briefs/m6/manifest-contract.md`` for the full specification.
"""

from arnold.pipeline.discovery.manifest import (
    Manifest,
    ManifestError,
    read_manifest,
)
from arnold.pipeline.discovery.trust import (
    BLESSED_ALLOWLIST,
    KNOWN_CAPABILITIES,
    TrustTier,
    check_capabilities,
    classify,
)

__all__ = [
    "Manifest",
    "ManifestError",
    "read_manifest",
    "TrustTier",
    "BLESSED_ALLOWLIST",
    "KNOWN_CAPABILITIES",
    "classify",
    "check_capabilities",
]
