"""VibeComfy executor pipeline for Arnold.

Classify a user query, conditionally research via the Hivemind/Banodoco
knowledge corpus, conditionally implement, and always emit a final reply.

Typical usage::

    python -m arnold run vibecomfy-executor --inputs query="How do I set WAN cfg?"
"""

from __future__ import annotations

from arnold.pipelines.vibecomfy_executor.pipelines import build_pipeline
from arnold.pipeline.types import Pipeline

# ── Required contract fields ──────────────────────────────────────────────

name: str = "vibecomfy-executor"
description: str = (
    "Classify a query, optionally research via Hivemind, "
    "optionally implement, and always emit a final reply."
)
default_profile: str | None = "@vibecomfy-executor:default"
recommended_profiles: tuple[str, ...] = (
    "@vibecomfy-executor:default",
    "@vibecomfy-executor:openai",
    "@vibecomfy-executor:anthropic",
    "@vibecomfy-executor:opensource",
)
supported_modes: tuple[str, ...] = ()
driver: str = "in_process"
entrypoint: str = "build_pipeline"
arnold_api_version: str = "1.0"
capabilities: tuple[str, ...] = ("orchestration", "research", "hivemind")

# ── Entrypoint ────────────────────────────────────────────────────────────


def build_pipeline(
    name: str = "vibecomfy-executor", description: str = ""
) -> Pipeline:
    """Build the VibeComfy executor pipeline."""
    from arnold.pipelines.vibecomfy_executor.pipelines import (
        build_pipeline as _build_pipeline,
    )

    return _build_pipeline(name=name, description=description)


__all__ = [
    "arnold_api_version",
    "build_pipeline",
    "capabilities",
    "default_profile",
    "description",
    "driver",
    "entrypoint",
    "name",
    "recommended_profiles",
    "supported_modes",
]
