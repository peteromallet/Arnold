"""Deprecated re-export bridge.

This module has moved to :mod:`arnold.pipeline.pattern_dynamic`.
Import from there directly.  This stub exists only for backward
compatibility and will be removed in a future release.

Note: Policy functions (critique_revise_gate_loop, escalate_if,
escalate_via_subpipeline, phase_zero_gate, mode_prompts) that were
removed from the neutral arnold topology now live in
:mod:`megaplan.pipelines.megaplan.planning_topology`.
Import from there if you need those.
"""

from __future__ import annotations

import warnings

warnings.warn(
    "megaplan._pipeline.pattern_dynamic is deprecated; "
    "use arnold.pipeline.pattern_dynamic instead.",
    DeprecationWarning,
    stacklevel=2,
)

from arnold.pipeline.pattern_dynamic import *  # noqa: F403, E402
