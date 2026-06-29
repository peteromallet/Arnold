"""Path-derived trust-grade evaluator for pipeline discovery.

Trust grades are computed from the filesystem origin of a pipeline module —
never from module-level constants or user-supplied metadata.  The three
grades:

- ``AUTO_EXEC``   — in-tree package under a recognised prefix subtree;
                    auto-executes on selection.
- ``QUARANTINED`` — out-of-tree / user-home module; manifest-only at
                    discovery; execution requires explicit promotion to
                    ``BLESSED``.
- ``BLESSED``     — either origin, explicitly listed in the blessed
                    allowlist; auto-executes on selection like
                    ``AUTO_EXEC``.

The neutral Arnold version accepts an *in_tree_path_fragment* parameter
so that consumers can define their own "in-tree" prefix.  Megaplan
passes ``"megaplan/pipelines"`` through the bridge.
"""

from __future__ import annotations

import enum
import hashlib
from pathlib import Path

# ---------------------------------------------------------------------------
# Public constants
# ---------------------------------------------------------------------------

# Allowlist of blessed pipeline install-path strings.  Default empty — no
# out-of-tree modules are promoted automatically.  To promote a user module,
# add its absolute path string (resolved) to this tuple.
BLESSED_ALLOWLIST: tuple[str, ...] = ()


# ---------------------------------------------------------------------------
# TrustGrade
# ---------------------------------------------------------------------------


class TrustGrade(enum.Enum):
    """Trust classification for a discovered pipeline module."""

    AUTO_EXEC = "auto_exec"
    QUARANTINED = "quarantined"
    BLESSED = "blessed"


# ---------------------------------------------------------------------------
# Core evaluator
# ---------------------------------------------------------------------------


def classify(
    module_path: Path,
    *,
    blessed_allowlist: tuple[str, ...] = BLESSED_ALLOWLIST,
    in_tree_path_fragment: str | None = None,
) -> TrustGrade:
    """Return the trust grade for *module_path*.

    Classification order:

    1. If ``str(module_path.resolve())`` is in *blessed_allowlist* → ``BLESSED``.
    2. If *in_tree_path_fragment* is set and *module_path* is inside that
       subtree → ``AUTO_EXEC``.
    3. Otherwise → ``QUARANTINED``.

    The *blessed_allowlist* and *in_tree_path_fragment* parameters exist so
    callers can inject their own definitions without mutating module-level
    constants (useful in tests and for non-Megaplan consumers).
    """
    resolved = str(module_path.resolve())

    if resolved in blessed_allowlist:
        return TrustGrade.BLESSED

    if in_tree_path_fragment is not None:
        normalised = resolved.replace("\\", "/")
        fragment_with_sep = "/" + in_tree_path_fragment + "/"
        if fragment_with_sep in normalised or normalised.endswith(
            "/" + in_tree_path_fragment
        ):
            return TrustGrade.AUTO_EXEC

    return TrustGrade.QUARANTINED


def derive_tenant_id(cli_name: str, module_path: Path) -> str:
    """Return the SDK-derived tenant id for an out-of-tree pipeline.

    The id is stable for the same CLI name and resolved install path, and is
    never read from user manifest metadata.
    """

    raw = f"{cli_name}\0{module_path.resolve()}".encode("utf-8")
    return "pipeline_" + hashlib.sha256(raw).hexdigest()[:24]
