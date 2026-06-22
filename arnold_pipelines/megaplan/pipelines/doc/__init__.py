"""Python composition of the first-class ``doc`` pipeline.

Linear explicit-node workflow with a dynamic fanout stage:

    outline -> section_drafts (fanout+reducer) -> critique -> revise -> assembly

The ``section_drafts`` step consumes the ``sections`` artifact emitted by
``outline`` and fans out per-section draft nodes. The reducer concatenates the
per-section outputs into a single mapping for downstream stages.
"""

from __future__ import annotations

from arnold.manifest import FanoutPolicy, ReducerRef, WorkflowPolicy
from arnold.workflow.dsl import Capability, Input, Output, Pipeline, Route, Step


name: str = "doc"
description: str = (
    "Linear doc pipeline: outline → per-section drafts (dynamic fanout) "
    "→ critique → revise → assembly. Single-pass; no gate."
)
default_profile: str | None = None
supported_modes: tuple[str, ...] = ()
recommended_profiles: tuple[str, ...] = ()
driver: tuple[str, str] = ("subprocess_isolated", "dynamic-fanout")
entrypoint: str = "build_pipeline"
arnold_api_version: str = "1.0"
capabilities: tuple[str, ...] = ("doc",)


def build_pipeline() -> Pipeline:
    """Return the canonical ``doc`` explicit-node pipeline."""

    outline = Step(
        id="outline",
        kind="agent",
        label="Outline document sections",
        inputs=(Input(name="brief"),),
        outputs=(Output(name="sections"), Output(name="outline_prompt")),
        capabilities=(Capability(id="doc", route="outline"),),
        metadata={"prompt_key": "outline_doc", "stage": "outline"},
    )
    section_drafts = Step(
        id="section_drafts",
        kind="fanout",
        label="Draft each section in parallel",
        inputs=(Input(name="sections", value_ref="outline.sections"),),
        outputs=(Output(name="draft_chunks"),),
        capabilities=(Capability(id="doc", route="execute"),),
        policy=WorkflowPolicy(
            fanout=FanoutPolicy(mode="dynamic", reducer_ref="doc:concat_sections"),
            reducers=(ReducerRef(reducer_id="doc:concat_sections"),),
        ),
        metadata={
            "prompt_key": "execute_doc",
            "generator_ref": "doc:outline_artifact_reader",
            "stage": "section_drafts",
        },
    )
    critique = Step(
        id="critique",
        kind="agent",
        label="Critique the assembled draft",
        inputs=(Input(name="draft_chunks", value_ref="section_drafts.draft_chunks"),),
        outputs=(Output(name="critique_artifact"), Output(name="critique_prompt")),
        capabilities=(Capability(id="doc", route="critique"),),
        metadata={"prompt_key": "critique_doc", "stage": "critique"},
    )
    revise = Step(
        id="revise",
        kind="agent",
        label="Revise from critique",
        inputs=(
            Input(name="draft_chunks", value_ref="section_drafts.draft_chunks"),
            Input(name="critique_artifact", value_ref="critique.critique_artifact"),
        ),
        outputs=(Output(name="revised_draft"), Output(name="revise_prompt")),
        capabilities=(Capability(id="doc", route="revise"),),
        metadata={"prompt_key": "revise_doc", "stage": "revise"},
    )
    assembly = Step(
        id="assembly",
        kind="emit",
        label="Assemble final document",
        inputs=(Input(name="revised_draft", value_ref="revise.revised_draft"),),
        outputs=(Output(name="document"), Output(name="assembly_prompt")),
        capabilities=(Capability(id="doc", route="assemble"),),
        metadata={"prompt_key": "assemble_doc", "stage": "assembly", "terminal": True},
    )

    return Pipeline(
        id="doc",
        version="m5-phase3",
        steps=(outline, section_drafts, critique, revise, assembly),
        routes=(
            Route(id="outline:section_drafts", source="outline", target="section_drafts", label="section_drafts"),
            Route(id="section_drafts:critique", source="section_drafts", target="critique", label="critique"),
            Route(id="critique:revise", source="critique", target="revise", label="revise"),
            Route(id="revise:assembly", source="revise", target="assembly", label="assembly"),
        ),
        capabilities=(Capability(id="doc", route="default"),),
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
            "resource_bundles": ("doc",),
        },
    )


__all__ = [
    "build_pipeline",
    "description",
    "default_profile",
    "supported_modes",
    "recommended_profiles",
    "driver",
    "arnold_api_version",
    "capabilities",
]
