"""Megaplan-owned adapters for bridging neutral artifact roots to plan dirs."""

from __future__ import annotations

from arnold.pipeline.types import StepContext


def artifact_root_as_plan_dir(ctx: StepContext) -> str:
    """Return ``ctx.artifact_root`` as a legacy ``plan_dir`` string."""

    return ctx.artifact_root
