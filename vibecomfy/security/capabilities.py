"""
Capability taxonomy for the S4 capability fence.

Every node class in the VibeComfy IR carries a capability tag describing
the worst side-effect adding a node of that class could cause at *edit time*.

It is NOT a runtime sandbox classification — KSampler "executes code" at
inference time but is tagged ``passthrough`` because the gate fences additions
to the IR, not runtime execution of existing nodes.

See ``docs/security/capability_taxonomy.md`` for the full design.
"""

from __future__ import annotations

from typing import Literal

# ── Public capability type ───────────────────────────────────────────────────
Capability = Literal["filesystem_write", "network", "code_exec", "passthrough"]

# ── Internal imports from sibling seed module ────────────────────────────────
# These are in-package imports — no cross-layer dependency.
from vibecomfy.security._seed import (  # noqa: E402
    ALL_SEEDED,
    KNOWN_PASSTHROUGH,
    OUTPUT_NODE_NAMES,
    _OUTPUT_CLASSES_KEYS,
    _SIDE_EFFECTING_RE,
)


def _build_taxonomy() -> dict[str, frozenset[Capability]]:
    """Build the frozen capability taxonomy from seeded data.

    Classification rules (in priority order):

    1. **Output-class nodes** → ``filesystem_write``.
       ``_OUTPUT_CLASSES_KEYS`` nodes can write arbitrary paths on disk.

    2. **Keyword-tagged network** → ``network``.
       Nodes whose class name matches ``Download.*Load`` or ``VHS_LoadVideo.*``
       are network-facing (they download from remote URLs or load from FFmpeg sources).

    3. **Keyword-tagged code_exec** → ``code_exec``.
       Nodes whose class name matches ``.*Expression`` or ``.*Eval`` can
       evaluate or execute arbitrary code at add time.

    4. **Other keyword-tagged side-effecting** → ``filesystem_write``.
       Save*/Preview* nodes and VHS_VideoCombine write to disk.

    5. **Known passthrough** → ``passthrough``.
       Explicitly enumerated core ComfyUI nodes with no dangerous I/O at add time.

    6. **All other seeded entries** → ``passthrough``.
       Default for any class in ``ALL_SEEDED`` not matched above — these are
       pure graph nodes without dangerous add-time side effects.

    7. **Unknown classes (not in taxonomy)** → handled by ``unknown_class_policy()``,
       which returns ``code_exec`` (quarantine). The taxonomy does not pre-populate
       entries for unknown classes so the coverage test can detect gaps.
    """
    taxonomy: dict[str, frozenset[Capability]] = {}

    # Network-detection sub-patterns
    _NETWORK_RE = __import__("re").compile(r"^(Download.*Load|VHS_LoadVideo.*)$")
    # Code-exec-detection sub-patterns
    _CODE_EXEC_RE = __import__("re").compile(r"^.*Expression$|^.*Eval$")

    for class_type in sorted(ALL_SEEDED):
        # Rule 1: explicit output classes → filesystem_write
        if class_type in _OUTPUT_CLASSES_KEYS:
            taxonomy[class_type] = frozenset({"filesystem_write"})
            continue

        # Rule 2: side-effecting pattern match
        if _SIDE_EFFECTING_RE.match(class_type):
            # Sub-classify: network vs code_exec vs filesystem_write
            if _NETWORK_RE.match(class_type):
                taxonomy[class_type] = frozenset({"network"})
            elif _CODE_EXEC_RE.match(class_type):
                taxonomy[class_type] = frozenset({"code_exec"})
            else:
                # Save*/Preview*/VHS_VideoCombine → filesystem_write
                taxonomy[class_type] = frozenset({"filesystem_write"})
            continue

        # Rule 5: known passthrough → passthrough
        if class_type in KNOWN_PASSTHROUGH:
            taxonomy[class_type] = frozenset({"passthrough"})
            continue

        # Rule 6: all other seeded → passthrough
        taxonomy[class_type] = frozenset({"passthrough"})

    return taxonomy


# ── Frozen capability taxonomy ───────────────────────────────────────────────
CAPABILITY_TAXONOMY: dict[str, frozenset[Capability]] = _build_taxonomy()

# ── Public helpers ───────────────────────────────────────────────────────────


def capabilities_for(class_type: str) -> frozenset[Capability]:
    """Return the capability tag(s) for *class_type*.

    Returns a frozenset of one or more :data:`Capability` strings.
    Unknown classes receive the quarantine default from
    :func:`unknown_class_policy`.
    """
    if class_type in CAPABILITY_TAXONOMY:
        return CAPABILITY_TAXONOMY[class_type]
    # Also check KNOWN_PASSTHROUGH directly for classes not in ALL_SEEDED
    # but still explicitly listed as passthrough.
    if class_type in KNOWN_PASSTHROUGH:
        return frozenset({"passthrough"})
    return unknown_class_policy()


def is_side_effecting(class_type: str) -> bool:
    """Return True if *class_type* has any non-``passthrough`` capability.

    Unknown classes (quarantine) are considered side-effecting because
    they default to ``code_exec``.
    """
    caps = capabilities_for(class_type)
    return "passthrough" not in caps or len(caps) > 1


def unknown_class_policy() -> frozenset[Capability]:
    """Return the capability tag for unknown (unclassified) node classes.

    Unknown classes are treated as ``code_exec``-suspect (quarantine).
    This is the fail-closed default — a class we cannot prove is
    ``passthrough`` may be a wrapper that shells out, writes files,
    or calls ``eval()``.

    The policy is flippable to hard-deny later by changing this return
    value without altering the gate surface.
    """
    return frozenset({"code_exec"})
