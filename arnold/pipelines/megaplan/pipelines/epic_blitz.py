"""Python composition of the ``epic-blitz`` pipeline.

Three-round adversarial critique + revision of an epic draft:

* ``high_panel`` — five high-abstraction critics (existing_system_reuse,
  conceptual_fit, missing_abstraction, epic_decomposition, strategic_risk)
  running in parallel.
* ``high_revise`` — single agent fanning in high_panel.* and producing a
  revised epic.
* ``mid_panel`` — five mid-abstraction critics (codebase_convention_fit,
  data_artifact_model, orchestration_semantics, agent_model_assignment,
  blast_radius) running in parallel.
* ``mid_revise`` — single agent fanning in mid_panel.* and producing a
  further revised epic.
* ``low_panel`` — five low-abstraction critics (implementation_feasibility,
  testability, edge_cases, cli_ux_details, migration_backcompat) running
  in parallel.
* ``readiness`` — terminal agent fanning in low_panel.*, producing the
  final revised epic and assessing chain-readiness.
"""

from __future__ import annotations

from pathlib import Path

from arnold.pipelines.megaplan._pipeline.types import (
    Edge,
    ParallelStage,
    Pipeline,
    Stage,
)

_PIPELINE_DIR: Path = Path(__file__).parent / "epic-blitz"
_PROMPTS: Path = _PIPELINE_DIR / "prompts"

# ── Module-level metadata surfaced via PipelineRegistry (T9) ──────────

name: str = "epic-blitz"
description: str = (
    "Three-round adversarial critique of epic drafts (high / mid / low "
    "abstraction) with revision after each round. Produces a "
    "chain-ready revised epic."
)
default_profile: str = "@epic-blitz:standard"
supported_modes: tuple[str, ...] = ()
recommended_profiles: tuple[str, ...] = (
    "@epic-blitz:standard",
)
driver: tuple[str, str] = ("graph", "dispatch+emit")
entrypoint: str = "build_pipeline"
arnold_api_version: str = "1.0"
capabilities: tuple[str, ...] = ("epic", "critique", "revise")

# ── Prompt paths ──────────────────────────────────────────────────────

_HIGH_DIR = _PROMPTS / "high"
_MID_DIR = _PROMPTS / "mid"
_LOW_DIR = _PROMPTS / "low"
_REVISER_DIR = _PROMPTS / "reviser"

# High-abstraction critic prompts
_H_EXISTING_SYSTEM_REUSE = str(_HIGH_DIR / "existing_system_reuse.md")
_H_CONCEPTUAL_FIT = str(_HIGH_DIR / "conceptual_fit.md")
_H_MISSING_ABSTRACTION = str(_HIGH_DIR / "missing_abstraction.md")
_H_EPIC_DECOMPOSITION = str(_HIGH_DIR / "epic_decomposition.md")
_H_STRATEGIC_RISK = str(_HIGH_DIR / "strategic_risk.md")

# Mid-abstraction critic prompts
_M_CODEBASE_CONVENTION_FIT = str(_MID_DIR / "codebase_convention_fit.md")
_M_DATA_ARTIFACT_MODEL = str(_MID_DIR / "data_artifact_model.md")
_M_ORCHESTRATION_SEMANTICS = str(_MID_DIR / "orchestration_semantics.md")
_M_AGENT_MODEL_ASSIGNMENT = str(_MID_DIR / "agent_model_assignment.md")
_M_BLAST_RADIUS = str(_MID_DIR / "blast_radius.md")

# Low-abstraction critic prompts
_L_IMPLEMENTATION_FEASIBILITY = str(_LOW_DIR / "implementation_feasibility.md")
_L_TESTABILITY = str(_LOW_DIR / "testability.md")
_L_EDGE_CASES = str(_LOW_DIR / "edge_cases.md")
_L_CLI_UX_DETAILS = str(_LOW_DIR / "cli_ux_details.md")
_L_MIGRATION_BACKCOMPAT = str(_LOW_DIR / "migration_backcompat.md")

# Reviser / readiness prompts
_HIGH_REVISE_PROMPT = str(_REVISER_DIR / "high_revise.md")
_MID_REVISE_PROMPT = str(_REVISER_DIR / "mid_revise.md")
_READINESS_PROMPT = str(_REVISER_DIR / "readiness.md")


def build_pipeline() -> Pipeline:
    """Return the canonical ``epic-blitz`` :class:`Pipeline`.

    Six stages in insertion order: high_panel → high_revise → mid_panel
    → mid_revise → low_panel → readiness.  The builder auto-links
    panel→agent→panel via emit labels ``'next'`` (panel join) and
    ``'done'`` (agent).  The terminal readiness stage is manually
    patched with ``Edge('done', 'halt')`` so the executor terminates
    cleanly.
    """

    pipeline = (
        Pipeline.builder(
            "epic-blitz",
            description=description,
            default_profile=default_profile,
            supported_modes=supported_modes,
            pipeline_dir=_PIPELINE_DIR,
        )
        .input("draft", file=True)
        # ── Round 1: high abstraction ──────────────────────────────
        .panel(
            "high_panel",
            reviewers=[
                ("existing_system_reuse", _H_EXISTING_SYSTEM_REUSE),
                ("conceptual_fit", _H_CONCEPTUAL_FIT),
                ("missing_abstraction", _H_MISSING_ABSTRACTION),
                ("epic_decomposition", _H_EPIC_DECOMPOSITION),
                ("strategic_risk", _H_STRATEGIC_RISK),
            ],
            inputs=["draft"],
            merge="none",
        )
        .agent(
            "high_revise",
            prompt=_HIGH_REVISE_PROMPT,
            inputs=["draft", "high_panel.*"],
        )
        # ── Round 2: mid abstraction ───────────────────────────────
        .panel(
            "mid_panel",
            reviewers=[
                ("codebase_convention_fit", _M_CODEBASE_CONVENTION_FIT),
                ("data_artifact_model", _M_DATA_ARTIFACT_MODEL),
                ("orchestration_semantics", _M_ORCHESTRATION_SEMANTICS),
                ("agent_model_assignment", _M_AGENT_MODEL_ASSIGNMENT),
                ("blast_radius", _M_BLAST_RADIUS),
            ],
            inputs=["high_revise"],
            merge="none",
        )
        .agent(
            "mid_revise",
            prompt=_MID_REVISE_PROMPT,
            inputs=["high_revise", "mid_panel.*"],
        )
        # ── Round 3: low abstraction ───────────────────────────────
        .panel(
            "low_panel",
            reviewers=[
                ("implementation_feasibility", _L_IMPLEMENTATION_FEASIBILITY),
                ("testability", _L_TESTABILITY),
                ("edge_cases", _L_EDGE_CASES),
                ("cli_ux_details", _L_CLI_UX_DETAILS),
                ("migration_backcompat", _L_MIGRATION_BACKCOMPAT),
            ],
            inputs=["mid_revise"],
            merge="none",
        )
        .agent(
            "readiness",
            prompt=_READINESS_PROMPT,
            inputs=["mid_revise", "low_panel.*"],
        )
        .build()
    )

    # ── Patch the terminal readiness stage with Edge('done','halt') ──
    # Without this edge the executor raises LookupError at
    # executor.py:294 because AgentStep returns next='done' but the
    # terminal stage has no outgoing edges.
    readiness_stage = pipeline.stages["readiness"]
    if isinstance(readiness_stage, ParallelStage):
        fixed = ParallelStage(
            name=readiness_stage.name,
            steps=readiness_stage.steps,
            join=readiness_stage.join,
            edges=readiness_stage.edges + (Edge("done", "halt"),),
            max_workers=readiness_stage.max_workers,
        )
    else:
        fixed = Stage(
            name=readiness_stage.name,
            step=readiness_stage.step,
            edges=readiness_stage.edges + (Edge("done", "halt"),),
        )
    stages = dict(pipeline.stages)
    stages["readiness"] = fixed
    return Pipeline(
        stages=stages,
        entry=pipeline.entry,
        overlays=pipeline.overlays,
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
