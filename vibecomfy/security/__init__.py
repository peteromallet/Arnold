"""VibeComfy security package.

Combines the static capability taxonomy with the S4 capability fence:
provenance tags, untrusted-source scoping, confirmation gates, and graph-text
taint helpers. This package must stay isolated from analysis, runtime, porting,
and registry layers.
"""

from vibecomfy.security.capabilities import (
    CAPABILITY_TAXONOMY,
    Capability,
    capabilities_for,
    is_side_effecting,
    unknown_class_policy,
)
from vibecomfy.security import provenance
from vibecomfy.security.gate import (
    CapabilityFenceError,
    GateContext,
    current_gate_context,
    require_confirmation,
    requesting_provenance,
    set_gate_context,
    untrusted_scope,
)
from vibecomfy.security.provenance import PROVENANCE_KEY, Provenance

__all__ = [
    "CAPABILITY_TAXONOMY",
    "Capability",
    "CapabilityFenceError",
    "GateContext",
    "PROVENANCE_KEY",
    "Provenance",
    "capabilities_for",
    "current_gate_context",
    "is_side_effecting",
    "provenance",
    "require_confirmation",
    "requesting_provenance",
    "set_gate_context",
    "unknown_class_policy",
    "untrusted_scope",
]
