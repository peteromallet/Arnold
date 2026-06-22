"""Discovery surface for pipeline packages.

M3a compatibility bridge; delete in M7.

Re-exports from the neutral Arnold discovery modules, injecting
Megaplan-specific defaults (``in_tree_path_fragment``, known
capabilities).
"""

# M3a compatibility bridge; delete in M7
from arnold.pipeline.discovery.manifest import (  # noqa: F401
    Manifest,
    ManifestError,
    read_manifest,
)
from arnold.pipeline.discovery.trust import (  # noqa: F401
    BLESSED_ALLOWLIST,
    TrustGrade,
    classify,
)

# Megaplan-specific constants (not in neutral Arnold)
KNOWN_CAPABILITIES: frozenset[str] = frozenset(
    {
        "plan",
        "execute",
        "review",
        "gate",
        "doc",
        "creative",
    }
)


def check_capabilities(capabilities: tuple[str, ...] | list[str]) -> list[str]:
    """Return a list of unrecognised capability kinds in *capabilities*."""
    return [c for c in capabilities if c not in KNOWN_CAPABILITIES]


__all__ = [
    "Manifest",
    "ManifestError",
    "read_manifest",
    "TrustGrade",
    "BLESSED_ALLOWLIST",
    "KNOWN_CAPABILITIES",
    "classify",
    "check_capabilities",
]
