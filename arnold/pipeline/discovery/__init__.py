"""Arnold pipeline discovery — neutral, opinion-free.

This package owns the neutral discovery contract (manifest-first,
non-executing path enumeration).  The core primitives are:

* :class:`Manifest` — static metadata extracted from a pipeline module
  without importing.
* :class:`ManifestError` — loud rejection when manifest reading fails.
* :func:`read_manifest` — parse a pipeline module's source to extract
  metadata constants.
* :class:`TrustGrade` — path-derived trust classification.
* :func:`classify` — derive trust tier from a module file path.

Every Megaplan opinion (scan roots, known capabilities, blessed
allowlist defaults, budget authority) is injected by the consumer
rather than baked in.
"""

from arnold.pipeline.discovery.manifest import (
    CURRENT_MAJOR,
    REQUIRED_FIELDS,
    Manifest,
    ManifestError,
    read_manifest,
)
from arnold.pipeline.discovery.trust import (
    TrustGrade,
    classify,
    derive_tenant_id,
)

__all__ = [
    "CURRENT_MAJOR",
    "REQUIRED_FIELDS",
    "Manifest",
    "ManifestError",
    "read_manifest",
    "TrustGrade",
    "classify",
    "derive_tenant_id",
]
