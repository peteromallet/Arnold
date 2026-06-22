"""First-class ``jokes`` pipeline.

This package is intentionally small but it is not a wrapper over ``creative``.
It declares a linear explicit-node workflow:

    draft -> tighten -> emit

The old step shells in :mod:`arnold_pipelines.megaplan.pipelines.jokes.steps`
remain available for M4 parity callers; the canonical ``build_pipeline()``
entrypoint now returns an :class:`arnold.workflow.dsl.Pipeline`.
"""

from __future__ import annotations

from arnold.workflow.dsl import Capability, Input, Output, Pipeline, Route, Step


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


def build_pipeline(topic: str = "software release notes") -> Pipeline:
    """Build the standalone jokes workflow as an explicit-node pipeline.

    *topic* is preserved as the first-class input to the pipeline and is
    threaded through to each stage via metadata so prompt renderers can use it.
    """

    draft = Step(
        id="draft",
        kind="agent",
        label="Draft a joke",
        inputs=(Input(name="topic"),),
        outputs=(Output(name="draft_artifact"), Output(name="draft_prompt")),
        capabilities=(Capability(id="creative", route="joke"),),
        metadata={
            "prompt_key": "draft_joke",
            "topic": topic,
            "stage": "draft",
        },
    )
    tighten = Step(
        id="tighten",
        kind="agent",
        label="Tighten the joke",
        inputs=(Input(name="draft_artifact", value_ref="draft.draft_artifact"),),
        outputs=(Output(name="tighten_artifact"), Output(name="tighten_prompt")),
        capabilities=(Capability(id="creative", route="joke"),),
        metadata={
            "prompt_key": "tighten_joke",
            "topic": topic,
            "stage": "tighten",
        },
    )
    emit = Step(
        id="emit",
        kind="emit",
        label="Emit final joke artifact",
        inputs=(Input(name="tighten_artifact", value_ref="tighten.tighten_artifact"),),
        outputs=(Output(name="joke_artifact"), Output(name="emit_prompt")),
        capabilities=(Capability(id="creative", route="joke"),),
        metadata={
            "prompt_key": "emit_joke",
            "topic": topic,
            "stage": "emit",
            "terminal": True,
        },
    )

    return Pipeline(
        id="jokes",
        version="m5-phase3",
        steps=(draft, tighten, emit),
        routes=(
            Route(id="draft:tighten", source="draft", target="tighten", label="tighten"),
            Route(id="tighten:emit", source="tighten", target="emit", label="emit"),
        ),
        capabilities=(Capability(id="creative", route="joke"),),
        metadata={
            "name": name,
            "description": description,
            "driver": driver,
            "entrypoint": entrypoint,
            "arnold_api_version": arnold_api_version,
            "capabilities": capabilities,
            "default_profile": default_profile,
            "supported_modes": supported_modes,
            "recommended_profiles": recommended_profiles,
            "resource_bundles": ("jokes",),
        },
    )


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
