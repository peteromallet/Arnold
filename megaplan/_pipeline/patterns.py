"""Deprecated re-export bridge for megaplan._pipeline.patterns.

This module has been split:
* Neutral topology primitives → :mod:`arnold.pipeline.patterns`
* Megaplan policy topology functions → :mod:`megaplan.pipelines.megaplan.planning_topology`

This bridge re-exports from BOTH so existing consumers of
``megaplan._pipeline.patterns`` retain access to all symbols
(critique_revise_gate_loop, escalate_if, escalate_via_subpipeline,
phase_zero_gate, mode_prompts, etc.).

Import directly from the canonical sources for new code.
"""

from __future__ import annotations

import warnings

warnings.warn(
    "megaplan._pipeline.patterns is deprecated; "
    "import from arnold.pipeline.patterns (neutral) or "
    "megaplan.pipelines.megaplan.planning_topology (policy) instead.",
    DeprecationWarning,
    stacklevel=2,
)

# ── Neutral primitives from arnold ─────────────────────────────────────
from arnold.pipeline.patterns import *  # noqa: F403, E402

# ── Policy functions from megaplan planning_topology ───────────────────
from megaplan.pipelines.megaplan.planning_topology import (  # noqa: E402, F401
    critique_revise_gate_loop,
    escalate_if,
    escalate_via_subpipeline,
    mode_prompts,
    phase_zero_gate,
)

# Re-export the complete __all__ combining both sources
__all__ = [
    # Neutral topology (from arnold.pipeline.patterns / arnold.pipeline.pattern_topology)
    "PromoteFn",
    "JoinFn",
    "panel_parallel",
    "alternating_turns",
    "subpipeline_call",
    "iterate_until",
    "majority_vote",
    # Dynamic primitives
    "panel_from_artifact",
    "dynamic_fanout",
    "weighted_vote",
    "iterate_until_consensus",
    "paired_round",
    # M5a node-library metadata
    "arnold_api_version",
    "get_node_metadata",
    "iter_node_metadata",
    # Policy functions (from megaplan.pipelines.megaplan.planning_topology)
    "critique_revise_gate_loop",
    "escalate_if",
    "escalate_via_subpipeline",
    "mode_prompts",
    "phase_zero_gate",
]
