"""Path-derived trust-tier evaluator for pipeline discovery.

M3a compatibility bridge; delete in M7.

Delegates to the neutral Arnold trust evaluator with Megaplan-specific
in-tree path fragments (``"arnold/pipelines"`` scanned first,
``"megaplan/pipelines"`` second).
"""

from __future__ import annotations

from pathlib import Path

# M3a compatibility bridge; delete in M7
from arnold.pipeline.discovery.trust import (  # noqa: F401
    BLESSED_ALLOWLIST,
    TrustTier,
    derive_tenant_id,
)
from arnold.pipeline.discovery.trust import classify as _arnold_classify

# Megaplan-specific in-tree path fragments.  ``arnold/pipelines`` is the new
# plugin root (scanned first); ``megaplan/pipelines`` is the legacy root.
_IN_TREE_PATH_FRAGMENTS: tuple[str, ...] = ("arnold/pipelines", "megaplan/pipelines")

# Re-export capability constants from the parent __init__ so that
# legacy imports (``from megaplan._pipeline.discovery.trust import
# KNOWN_CAPABILITIES``) continue to work.
from megaplan._pipeline.discovery import (  # noqa: E402, F401
    KNOWN_CAPABILITIES,
    check_capabilities,
)


def classify(
    module_path: Path,
    *,
    blessed_allowlist: tuple[str, ...] = BLESSED_ALLOWLIST,
) -> TrustTier:
    """Return the trust tier for *module_path*.

    Megaplan bridge: delegates to the neutral Arnold classifier with
    each in-tree path fragment.  The first matching fragment wins.

    M3a compatibility bridge; delete in M7.
    """
    for fragment in _IN_TREE_PATH_FRAGMENTS:
        tier = _arnold_classify(
            module_path,
            blessed_allowlist=blessed_allowlist,
            in_tree_path_fragment=fragment,
        )
        if tier != TrustTier.QUARANTINED:
            return tier
    return _arnold_classify(
        module_path,
        blessed_allowlist=blessed_allowlist,
        in_tree_path_fragment=None,
    )
