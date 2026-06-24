"""Python composition of the ``writing-panel-strict`` pipeline.

Normalized package replacement for the legacy
``megaplan/pipelines/writing-panel-strict/pipeline.yaml``. The implementation,
prompts, profiles, and ``SKILL.md`` now live together in this importable package.

Topology:

    panel_review (fanout: 3 reviewers) -> synth -> revise -> human_decide

``human_decide`` is a human-gate step. ``continue`` loops back to
``panel_review``; ``stop`` exits via a terminal halt route.
"""

from __future__ import annotations

from pathlib import Path

from arnold.manifest import ControlTransitionSlot, FanoutPolicy, LoopPolicy, SuspensionRoute, WorkflowPolicy
from arnold.workflow.dsl import Capability, Input, Output, Pipeline, Route, Step


_PIPELINE_DIR: Path = Path(__file__).parent
_PROMPTS: Path = _PIPELINE_DIR / "prompts"


name: str = "writing-panel-strict"
description: str = (
    "Adversarial review of prose drafts by N reviewers, then revise. "
    "Not for code."
)
default_profile: str = "@writing-panel-strict:standard"
supported_modes: tuple[str, ...] = ("graph", "polish", "restructure", "provoke")
recommended_profiles: tuple[str, ...] = (
    "@writing-panel-strict:premium",
    "@writing-panel-strict:standard",
    "@writing-panel-strict:cheap",
)
driver: tuple[str, str] = ("graph", "dispatch+emit")
entrypoint: str = "build_pipeline"
arnold_api_version: str = "1.0"
capabilities: tuple[str, ...] = ("writing", "critique", "revise")


REVIEWERS: tuple[tuple[str, str], ...] = (
    ("pessimist", str(_PROMPTS / "pessimist.md")),
    ("optimist", str(_PROMPTS / "optimist.md")),
    ("structuralist", str(_PROMPTS / "structuralist.md")),
)


def build_pipeline() -> Pipeline:
    """Return the canonical ``writing-panel-strict`` explicit-node pipeline."""

    panel_review = Step(
        id="panel_review",
        kind="fanout",
        label="Adversarial panel review",
        inputs=(Input(name="draft"),),
        outputs=(Output(name="review_batch"),),
        capabilities=(Capability(id="writing", route="critique"),),
        policy=WorkflowPolicy(
            fanout=FanoutPolicy(
                mode="static",
                width=len(REVIEWERS),
                reducer_ref="writing_panel_strict:merge_reviews",
            ),
        ),
        metadata={
            "reviewers": [
                {"name": name, "prompt_path": path}
                for name, path in REVIEWERS
            ],
            "merge": "none",
        },
    )
    synth = Step(
        id="synth",
        kind="agent",
        label="Synthesize panel critiques",
        inputs=(Input(name="review_batch", value_ref="panel_review.review_batch"),),
        outputs=(Output(name="synth_artifact"),),
        capabilities=(Capability(id="writing", route="critique"),),
        metadata={
            "prompt_path": str(_PROMPTS / "synth.md"),
        },
    )
    revise = Step(
        id="revise",
        kind="agent",
        label="Revise draft from synthesis",
        inputs=(
            Input(name="draft"),
            Input(name="synth_artifact", value_ref="synth.synth_artifact"),
        ),
        outputs=(Output(name="revised_draft"),),
        capabilities=(Capability(id="writing", route="revise"),),
        metadata={
            "prompt_path": str(_PROMPTS / "revise.md"),
        },
    )
    human_decide = Step(
        id="human_decide",
        kind="human_gate",
        label="Human decision: continue or stop",
        inputs=(Input(name="revised_draft", value_ref="revise.revised_draft"),),
        outputs=(Output(name="decision"),),
        capabilities=(Capability(id="human", route="decision"),),
        policy=WorkflowPolicy(
            loop=LoopPolicy(max_iterations=8, until_ref="human_decide:stop"),
            suspension_routes=(
                SuspensionRoute(route_id="human_decide:loop", reentry_id="continue"),
            ),
            control_transitions=(
                ControlTransitionSlot(
                    transition_id="human_decide:continue",
                    transition_type="override",
                    trigger_ref="human_decide.decision",
                    target_ref="panel_review",
                    policy_ref="writing_panel_strict:human_decide",
                ),
                ControlTransitionSlot(
                    transition_id="human_decide:stop",
                    transition_type="override",
                    trigger_ref="human_decide.decision",
                    target_ref="halt",
                    policy_ref="writing_panel_strict:human_decide",
                ),
            ),
        ),
        metadata={
            "options": ("continue", "stop"),
        },
    )
    halt = Step(
        id="halt",
        kind="halt",
        label="Terminal halt",
        outputs=(Output(name="status"),),
        metadata={"terminal": True},
    )

    return Pipeline(
        id="writing-panel-strict",
        version="m5-phase3",
        steps=(panel_review, synth, revise, human_decide, halt),
        routes=(
            Route(id="panel_review:synth", source="panel_review", target="synth", label="default"),
            Route(id="synth:revise", source="synth", target="revise", label="default"),
            Route(id="revise:human_decide", source="revise", target="human_decide", label="default"),
            Route(id="human_decide:panel_review", source="human_decide", target="panel_review", label="continue", condition_ref="continue"),
            Route(id="human_decide:halt", source="human_decide", target="halt", label="stop", condition_ref="stop"),
        ),
        capabilities=(
            Capability(id="writing", route="critique"),
            Capability(id="writing", route="revise"),
            Capability(id="human", route="decision", required=False),
        ),
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
            "pipeline_dir": str(_PIPELINE_DIR),
        },
    )


__all__ = [
    "build_pipeline",
    "description",
    "default_profile",
    "supported_modes",
    "recommended_profiles",
    "driver",
    "entrypoint",
    "arnold_api_version",
    "capabilities",
]
