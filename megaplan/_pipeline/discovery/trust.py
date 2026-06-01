"""Path-derived trust-tier evaluator for pipeline discovery.

Trust tiers are computed from the filesystem origin of a pipeline module —
never from module-level constants or user-supplied metadata. The three tiers:

- ``AUTO_EXEC``   — in-tree package under ``megaplan/pipelines/``; auto-executes
                    on selection (trusted, same package tree as the SDK).
- ``QUARANTINED`` — out-of-tree / user-home module; manifest-only at discovery;
                    execution requires explicit promotion to ``BLESSED``.
- ``BLESSED``     — either origin, explicitly listed in ``BLESSED_ALLOWLIST``;
                    auto-executes on selection like ``AUTO_EXEC``.

See ``briefs/m6/manifest-contract.md`` §2.6 for the full spec.
"""

from __future__ import annotations

import enum
import hashlib
from pathlib import Path

# ---------------------------------------------------------------------------
# Public constants
# ---------------------------------------------------------------------------

# Allowlist of blessed pipeline install-path strings. Default empty — no
# out-of-tree modules are promoted automatically. To promote a user module,
# add its absolute path string (resolved) to this tuple.
BLESSED_ALLOWLIST: tuple[str, ...] = ()

# The canonical in-tree pipelines root, relative to the repo root. We derive
# trust by checking whether the resolved module path is inside this subtree.
_IN_TREE_PACKAGE: str = "megaplan.pipelines"
_IN_TREE_PATH_FRAGMENT: str = "megaplan/pipelines"


# ---------------------------------------------------------------------------
# TrustTier
# ---------------------------------------------------------------------------


class TrustTier(enum.Enum):
    """Trust classification for a discovered pipeline module."""

    AUTO_EXEC = "auto_exec"
    QUARANTINED = "quarantined"
    BLESSED = "blessed"


# ---------------------------------------------------------------------------
# Core evaluator
# ---------------------------------------------------------------------------


def classify(module_path: Path, *, blessed_allowlist: tuple[str, ...] = BLESSED_ALLOWLIST) -> TrustTier:
    """Return the trust tier for *module_path*.

    Classification order:
    1. If ``str(module_path.resolve())`` is in *blessed_allowlist* → ``BLESSED``.
    2. If *module_path* is inside the in-tree ``megaplan/pipelines/`` subtree → ``AUTO_EXEC``.
    3. Otherwise → ``QUARANTINED``.

    The *blessed_allowlist* parameter exists so callers can pass a non-default
    allowlist without mutating the module-level constant (useful in tests).
    """
    resolved = str(module_path.resolve())

    if resolved in blessed_allowlist:
        return TrustTier.BLESSED

    # Normalise path separators for cross-platform safety.
    # Use leading slash anchor to avoid matching ".megaplan/pipelines/" etc.
    normalised = resolved.replace("\\", "/")
    fragment_with_sep = "/" + _IN_TREE_PATH_FRAGMENT + "/"
    if fragment_with_sep in normalised or normalised.endswith("/" + _IN_TREE_PATH_FRAGMENT):
        return TrustTier.AUTO_EXEC

    return TrustTier.QUARANTINED


def derive_tenant_id(cli_name: str, module_path: Path) -> str:
    """Return the SDK-derived tenant id for an out-of-tree pipeline.

    The id is stable for the same CLI name and resolved install path, and is
    never read from user manifest metadata.
    """

    raw = f"{cli_name}\0{module_path.resolve()}".encode("utf-8")
    return "pipeline_" + hashlib.sha256(raw).hexdigest()[:24]


# ---------------------------------------------------------------------------
# Capability allowlist helper
# ---------------------------------------------------------------------------

# The set of capability kinds that the SDK recognises. Anything outside this
# set is denied at discovery time regardless of trust tier. Future capability
# kinds are introduced here explicitly rather than discovered from manifests.
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
    """Return a list of unrecognised capability kinds in *capabilities*.

    An empty return value means every declared capability is known.
    Callers should surface unknown capabilities as a loud ``ManifestError``
    rather than silently ignoring them.
    """
    return [c for c in capabilities if c not in KNOWN_CAPABILITIES]
