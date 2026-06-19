"""Python composition of the ``writing-panel-strict`` pipeline.

Top-level package replacement for the legacy
``arnold/pipelines/megaplan/pipelines/writing-panel-strict/pipeline.yaml``.
Prompts / profiles / ``SKILL.md`` live inside this package; only the YAML
manifest is replaced.

Topology (identical to the legacy YAML — locks done-criterion #8):

* ``panel_review`` — three reviewers (pessimist, optimist,
  structuralist) running in parallel via the builder's
  :class:`ParallelStage` fan-out.
* ``synth`` — single agent fanning in the three reviewer artifacts
  via ``panel_review.*``.
* ``revise`` — single agent producing a revised draft from the
  original draft + the synthesised critique.
* ``human_decide`` — :class:`HumanDecisionStep` with ``options=['continue',
  'stop']``. ``continue`` loops back to ``panel_review`` (re-entry into
  the ParallelStage); ``stop`` exits via the executor's ``"halt"``
  terminator (the Python-composition equivalent of the YAML compiler's
  ``to: done`` → ``target="halt"`` translation at
  ``compiler.py:245``). The brief's ``['ship','continue','escalate']``
  sketch is rejected — done-criterion #8 requires identical behaviour
  to the YAML's ``choices: [continue, stop]``.
"""

from __future__ import annotations

from pathlib import Path

# M3a: Pipeline kept as megaplan bridge — build_pipeline() uses Pipeline.builder()
# which returns a megaplan PipelineBuilder with .panel()/.agent()/.human_gate()
# convenience methods not available on the Arnold PipelineBuilder.
from arnold.pipelines.megaplan._pipeline.types import Pipeline


_PIPELINE_DIR: Path = Path(__file__).parent
_PROMPTS: Path = _PIPELINE_DIR / "prompts"


# ── Module-level metadata surfaced via PipelineRegistry (T9) ──────────

name: str = "writing-panel-strict"
description: str = (
    "Adversarial review of prose drafts by N reviewers, then revise. "
    "Not for code."
)
default_profile: str = "@writing-panel-strict:standard"
supported_modes: tuple[str, ...] = ("polish", "restructure", "provoke")
recommended_profiles: tuple[str, ...] = (
    "@writing-panel-strict:premium",
    "@writing-panel-strict:standard",
    "@writing-panel-strict:cheap",
)
driver: tuple[str, str] = ("graph", "dispatch+emit")
entrypoint: str = "build_pipeline"
arnold_api_version: str = "1.0"
capabilities: tuple[str, ...] = ("writing", "critique", "revise")


def build_pipeline() -> Pipeline:
    """Return the canonical ``writing-panel-strict`` :class:`Pipeline`."""

    return (
        Pipeline.builder(
            "writing-panel-strict",
            description=description,
            default_profile=default_profile,
            supported_modes=supported_modes,
            pipeline_dir=_PIPELINE_DIR,
        )
        .input("draft", file=True)
        .panel(
            "panel_review",
            reviewers=[
                ("pessimist", str(_PROMPTS / "pessimist.md")),
                ("optimist", str(_PROMPTS / "optimist.md")),
                ("structuralist", str(_PROMPTS / "structuralist.md")),
            ],
            inputs=["draft"],
            merge="none",
        )
        .agent(
            "synth",
            prompt=str(_PROMPTS / "synth.md"),
            inputs=["panel_review.*"],
        )
        .agent(
            "revise",
            prompt=str(_PROMPTS / "revise.md"),
            inputs=["draft", "synth"],
        )
        .human_gate(
            "human_decide",
            artifact="revise",
            options=["continue", "stop"],
            edges={"continue": "panel_review", "stop": "halt"},
            loop_condition=lambda state: False,
        )
        .build()
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
