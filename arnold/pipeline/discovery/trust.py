"""Path-derived trust-tier evaluator for pipeline discovery.

Trust tiers are computed from the filesystem origin of a pipeline module —
never from module-level constants or user-supplied metadata. The three tiers:

- ``AUTO_EXEC``   — in-tree package under any of the ``_SCAN_ROOTS``; auto-executes
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

# Scan roots for in-tree pipeline discovery. Each entry is a dotted Python
# package name (e.g. 'arnold.pipelines', 'megaplan.pipelines'). The classify()
# function checks whether a resolved module path falls inside any of these
# subtrees by converting dots to path separators.
# Default includes both arnold and megaplan roots for backward compatibility.
_SCAN_ROOTS: tuple[str, ...] = ("arnold.pipelines", "megaplan.pipelines")


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
    2. If *module_path* is inside any of the in-tree ``_SCAN_ROOTS``
       subtrees → ``AUTO_EXEC``.
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
    for scan_root in _SCAN_ROOTS:
        path_fragment = "/" + scan_root.replace(".", "/") + "/"
        if path_fragment in normalised or normalised.endswith("/" + scan_root.replace(".", "/")):
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

# KNOWN_CAPABILITIES is a frozenset of structural capability kind identifiers.
# These are NOT Megaplan planning-phase literals — they are SDK-level capability
# kinds that describe what a pipeline module can structurally do (plan, execute,
# review, gate, produce documentation, or perform creative work). The names
# overlap with Megaplan phase names by historical convention, not by identity.
# ---------------------------------------------------------------------------
# GREP-GATE-EXEMPTION: The strings 'plan', 'execute', 'review', and 'gate'
# inside this frozenset are structural capability kind identifiers, NOT
# planning-phase literals or gate-recommendation strings. The grep gate that
# scans for forbidden Megaplan coupling must exempt this module-level constant.
# ---------------------------------------------------------------------------
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

# Configurable override for capability kinds. When set to a non-None frozenset,
# it replaces KNOWN_CAPABILITIES in check_capabilities() lookups. This allows
# embedders to extend or restrict the recognised capability surface without
# monkeypatching the module-level constant.
_CUSTOM_CAPABILITIES: frozenset[str] | None = None


def _effective_capabilities() -> frozenset[str]:
    """Return the active capability set, respecting the configurable override."""
    if _CUSTOM_CAPABILITIES is not None:
        return _CUSTOM_CAPABILITIES
    return KNOWN_CAPABILITIES


def check_capabilities(capabilities: tuple[str, ...] | list[str]) -> list[str]:
    """Return a list of unrecognised capability kinds in *capabilities*.

    An empty return value means every declared capability is known.
    Callers should surface unknown capabilities as a loud ``ManifestError``
    rather than silently ignoring them.
    """
    effective = _effective_capabilities()
    return [c for c in capabilities if c not in effective]

__all__ = [
    "TrustTier",
    "BLESSED_ALLOWLIST",
    "KNOWN_CAPABILITIES",
    "classify",
    "check_capabilities",
    "derive_tenant_id",
]

