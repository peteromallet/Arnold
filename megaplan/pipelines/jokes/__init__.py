"""First-class ``jokes`` pipeline.

This package is intentionally small but it is not a wrapper over ``creative``.
It declares: "I'm a graph driver, I need dispatch+emit"; the graph supplies
its own joke content stages and explicit stage wiring.
"""

from __future__ import annotations

from megaplan._pipeline.types import Edge, Pipeline, Stage
from megaplan.pipelines.jokes.steps import JokeStep


name: str = "jokes"
description: str = (
    "Joke pipeline: a graph driver that needs dispatch+emit, drafts a joke, "
    "tightens the beat, and emits the final artifact."
)
default_profile: str | None = None
supported_modes: tuple[str, ...] = ("joke",)
recommended_profiles: tuple[str, ...] = ()
driver: tuple[str, str] = ("graph", "dispatch+emit")
entrypoint: str = "build_pipeline"
arnold_api_version: str = "1.0"
capabilities: tuple[str, ...] = ("creative", "joke")


STAGE_SPECS: tuple[tuple[str, str, str], ...] = (
    ("draft", "draft_joke", "tighten"),
    ("tighten", "tighten_joke", "emit"),
    ("emit", "emit_joke", "halt"),
)


def build_pipeline(topic: str = "software release notes") -> Pipeline:
    """Build the standalone jokes graph.

    Each node dispatches one local joke step; the final node emits a
    durable artifact and halts.
    """

    stages: dict[str, Stage] = {}
    for stage_name, prompt_key, next_label in STAGE_SPECS:
        edges = () if next_label == "halt" else (
            Edge(label=next_label, target=next_label),
        )
        stages[stage_name] = Stage(
            name=stage_name,
            step=JokeStep(
                name=stage_name,
                prompt_key=prompt_key,
                topic=topic,
                next_label=next_label,
            ),
            edges=edges,
        )
    return Pipeline(stages=stages, entry="draft")


__all__ = [
    "build_pipeline",
    "name",
    "description",
    "default_profile",
    "supported_modes",
    "recommended_profiles",
    "driver",
    "entrypoint",
    "arnold_api_version",
    "capabilities",
]
