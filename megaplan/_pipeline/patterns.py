"""Compatibility facade for reusable pipeline pattern functions.

Public imports continue to come from :mod:`megaplan._pipeline.patterns`,
while the implementations now live in concern-specific sibling modules.
Underscore-prefixed dynamic helpers and classes remain reachable as
attributes on this facade for de-facto compatibility with tests and
callers that introspect them.
"""

from __future__ import annotations

from megaplan._pipeline.pattern_dynamic import (
    _agreement_ratio,
    _ConsensusStep,
    _DynamicFanoutStep,
    _extract_specs_from_result,
    _PanelFromArtifactStep,
    _PairedRoundStep,
    _read_specs_from_path,
    _specialize_step,
    dynamic_fanout,
    iterate_until_consensus,
    paired_round,
    panel_from_artifact,
)
from megaplan._pipeline.pattern_joins import majority_vote, weighted_vote
from megaplan._pipeline.pattern_topology import (
    alternating_turns,
    critique_revise_gate_loop,
    escalate_if,
    iterate_until,
    mode_prompts,
    panel_parallel,
    phase_zero_gate,
    subpipeline_call,
)
from megaplan._pipeline.pattern_types import JoinFn, PromoteFn  # noqa: F401


__all__ = [
    "PromoteFn",
    "JoinFn",
    "critique_revise_gate_loop",
    "panel_parallel",
    "alternating_turns",
    "subpipeline_call",
    "mode_prompts",
    "iterate_until",
    "escalate_if",
    "majority_vote",
    "phase_zero_gate",
    # Dynamic primitives (0.23 — pipeline-rationalization sprint, T2).
    "panel_from_artifact",
    "dynamic_fanout",
    "weighted_vote",
    "iterate_until_consensus",
    "paired_round",
]
