"""Python composition of the first-class ``megaplan`` pipeline.

The planning pipeline is the megaplan plan-production substrate:

    prep → plan → critique ↔ gate ↔ revise (loop) → finalize
                                ↓ tiebreaker (on tie)
                                ↓ execute (optional, on proceed)
                                ↓ review  (optional, after execute)

Gate verdicts route the loop:

* ``proceed``    — gate approved; continue to finalize (or execute).
* ``iterate``    — gate rejected; re-enter critique → revise loop.
* ``tiebreaker`` — evaluators split; hand off to tiebreaker stage.
* ``escalate``   — escalate to a higher-complexity model tier.

Robustness levels control the depth of the critique/gate loop:

* ``bare``     — single-pass, no gate loop.
* ``light``    — one critique+revise round, minimal gate.
* ``full``     — standard gate loop (default).
* ``thorough`` — extended gate loop with stricter criteria.
* ``extreme``  — maximum depth, all evaluators enabled.

Driver substrate: ``subprocess_isolated`` for execute/review stages;
``graph+loop-node`` for the critique→gate→revise subloop.

This package is the canonical discovered ``megaplan`` pipeline.
Its physical package path remains ``megaplan.pipelines.planning`` so the
legacy ``planning`` import path keeps working while registry discovery
publishes the canonical ``megaplan`` identity.

As of M4, this module is a thin compatibility facade — the canonical
implementation lives in ``arnold.pipelines.megaplan``.
"""

from __future__ import annotations

# ── Re-export the canonical implementation from the Arnold plugin ──────
from arnold.pipelines.megaplan import (  # noqa: E402, F401
    build_pipeline,
    compile_planning_pipeline,
    operation_registry,
    override_catalog,
)

# ── Module-level metadata surfaced via PipelineRegistry ────────────────

name: str = "megaplan"
description: str = (
    "Built-in megaplan pipeline: prep → plan → critique/gate/revise loop "
    "→ finalize → execute → review. Gate verdicts: proceed / iterate / "
    "tiebreaker / escalate. Robustness levels: bare / light / full / "
    "thorough / extreme."
)
default_profile: str | None = None
supported_modes: tuple[str, ...] = ("plan",)
driver: tuple[str, str] = ("subprocess_isolated", "graph+loop-node")
entrypoint: str = "build_pipeline"
arnold_api_version: str = "1.0"
capabilities: tuple[str, ...] = ("plan", "execute", "review")


__all__ = [
    "build_pipeline",
    "compile_planning_pipeline",
    "operation_registry",
    "override_catalog",
    "description",
    "default_profile",
    "supported_modes",
    "driver",
    "arnold_api_version",
    "capabilities",
]
