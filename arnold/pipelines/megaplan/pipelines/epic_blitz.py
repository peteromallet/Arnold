"""Native composition of the ``epic-blitz`` pipeline.

Three-round adversarial critique + revision of an epic draft:

* ``high_panel`` - five high-abstraction critics.
* ``high_revise`` - single agent fanning in ``high_panel.*``.
* ``mid_panel`` - five mid-abstraction critics.
* ``mid_revise`` - single agent fanning in ``mid_panel.*``.
* ``low_panel`` - five low-abstraction critics.
* ``readiness`` - terminal agent fanning in ``low_panel.*``.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from arnold.pipeline.native import (
    compile_pipeline,
    native_panel,
    phase,
    pipeline,
    project_graph,
)
from arnold.pipelines.megaplan._pipeline.envelope import EMPTY_ENVELOPE
from arnold.pipelines.megaplan._pipeline.pattern_topology import panel_parallel
from arnold.pipelines.megaplan._pipeline.steps.agent import AgentStep
from arnold.pipelines.megaplan._pipeline.steps.panel import PanelReviewerStep
from arnold.pipelines.megaplan._pipeline.types import (
    Edge,
    ParallelStage,
    Pipeline,
    Stage,
    Step,
    StepContext,
)

_PIPELINE_DIR: Path = Path(__file__).parent / "epic-blitz"
_PROMPTS: Path = _PIPELINE_DIR / "prompts"

# Module-level metadata surfaced via PipelineRegistry.

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

# Prompt paths.

_HIGH_DIR = _PROMPTS / "high"
_MID_DIR = _PROMPTS / "mid"
_LOW_DIR = _PROMPTS / "low"
_REVISER_DIR = _PROMPTS / "reviser"

_H_EXISTING_SYSTEM_REUSE = str(_HIGH_DIR / "existing_system_reuse.md")
_H_CONCEPTUAL_FIT = str(_HIGH_DIR / "conceptual_fit.md")
_H_MISSING_ABSTRACTION = str(_HIGH_DIR / "missing_abstraction.md")
_H_EPIC_DECOMPOSITION = str(_HIGH_DIR / "epic_decomposition.md")
_H_STRATEGIC_RISK = str(_HIGH_DIR / "strategic_risk.md")

_M_CODEBASE_CONVENTION_FIT = str(_MID_DIR / "codebase_convention_fit.md")
_M_DATA_ARTIFACT_MODEL = str(_MID_DIR / "data_artifact_model.md")
_M_ORCHESTRATION_SEMANTICS = str(_MID_DIR / "orchestration_semantics.md")
_M_AGENT_MODEL_ASSIGNMENT = str(_MID_DIR / "agent_model_assignment.md")
_M_BLAST_RADIUS = str(_MID_DIR / "blast_radius.md")

_L_IMPLEMENTATION_FEASIBILITY = str(_LOW_DIR / "implementation_feasibility.md")
_L_TESTABILITY = str(_LOW_DIR / "testability.md")
_L_EDGE_CASES = str(_LOW_DIR / "edge_cases.md")
_L_CLI_UX_DETAILS = str(_LOW_DIR / "cli_ux_details.md")
_L_MIGRATION_BACKCOMPAT = str(_LOW_DIR / "migration_backcompat.md")

_HIGH_REVISE_PROMPT = str(_REVISER_DIR / "high_revise.md")
_MID_REVISE_PROMPT = str(_REVISER_DIR / "mid_revise.md")
_READINESS_PROMPT = str(_REVISER_DIR / "readiness.md")

_HIGH_REVIEWERS: tuple[tuple[str, str], ...] = (
    ("existing_system_reuse", _H_EXISTING_SYSTEM_REUSE),
    ("conceptual_fit", _H_CONCEPTUAL_FIT),
    ("missing_abstraction", _H_MISSING_ABSTRACTION),
    ("epic_decomposition", _H_EPIC_DECOMPOSITION),
    ("strategic_risk", _H_STRATEGIC_RISK),
)
_MID_REVIEWERS: tuple[tuple[str, str], ...] = (
    ("codebase_convention_fit", _M_CODEBASE_CONVENTION_FIT),
    ("data_artifact_model", _M_DATA_ARTIFACT_MODEL),
    ("orchestration_semantics", _M_ORCHESTRATION_SEMANTICS),
    ("agent_model_assignment", _M_AGENT_MODEL_ASSIGNMENT),
    ("blast_radius", _M_BLAST_RADIUS),
)
_LOW_REVIEWERS: tuple[tuple[str, str], ...] = (
    ("implementation_feasibility", _L_IMPLEMENTATION_FEASIBILITY),
    ("testability", _L_TESTABILITY),
    ("edge_cases", _L_EDGE_CASES),
    ("cli_ux_details", _L_CLI_UX_DETAILS),
    ("migration_backcompat", _L_MIGRATION_BACKCOMPAT),
)

_HIGH_REVIEWER_IDS = tuple(reviewer_id for reviewer_id, _ in _HIGH_REVIEWERS)
_MID_REVIEWER_IDS = tuple(reviewer_id for reviewer_id, _ in _MID_REVIEWERS)
_LOW_REVIEWER_IDS = tuple(reviewer_id for reviewer_id, _ in _LOW_REVIEWERS)

_EMPTY_PANEL_ORDER: dict[str, tuple[str, ...]] = {}
_HIGH_PANEL_ORDER: dict[str, tuple[str, ...]] = {
    "high_panel": _HIGH_REVIEWER_IDS,
}
_MID_PANEL_ORDER: dict[str, tuple[str, ...]] = {
    "high_panel": _HIGH_REVIEWER_IDS,
    "mid_panel": _MID_REVIEWER_IDS,
}
_LOW_PANEL_ORDER: dict[str, tuple[str, ...]] = {
    "high_panel": _HIGH_REVIEWER_IDS,
    "mid_panel": _MID_REVIEWER_IDS,
    "low_panel": _LOW_REVIEWER_IDS,
}

_EPIC_BLITZ_STAGE_ORDER: tuple[str, ...] = (
    "high_panel",
    "high_revise",
    "mid_panel",
    "mid_revise",
    "low_panel",
    "readiness",
)


def _copy_panel_order(
    order: Mapping[str, Sequence[str]],
) -> dict[str, list[str]]:
    return {panel: list(reviewers) for panel, reviewers in order.items()}


def _dict_to_step_context(ctx: object) -> StepContext:
    """Adapt native-runtime contexts to Megaplan's StepContext."""

    if isinstance(ctx, StepContext):
        return ctx
    if hasattr(ctx, "plan_dir") and hasattr(ctx, "state") and hasattr(ctx, "profile"):
        return ctx  # type: ignore[return-value]

    if isinstance(ctx, dict):
        raw_state = ctx.get("state") or {}
        raw_inputs = ctx.get("inputs") or {}
        root = ctx.get("artifact_root") or ctx.get("plan_dir") or "."
        envelope = ctx.get("envelope") or EMPTY_ENVELOPE
        mode = str(ctx.get("mode") or "code")
        profile = ctx.get("profile") or {}
    else:
        raw_state = getattr(ctx, "state", {}) or {}
        raw_inputs = getattr(ctx, "inputs", {}) or {}
        root = getattr(ctx, "artifact_root", None) or getattr(ctx, "plan_dir", ".")
        envelope = getattr(ctx, "envelope", None) or EMPTY_ENVELOPE
        mode = str(getattr(ctx, "mode", "code") or "code")
        profile = getattr(ctx, "profile", {}) or {}

    inputs = {
        str(key): Path(value) if isinstance(value, str) else value
        for key, value in dict(raw_inputs).items()
    }
    return StepContext(
        plan_dir=Path(root),
        state=dict(raw_state) if isinstance(raw_state, dict) else raw_state,
        profile=profile,
        mode=mode,
        inputs=inputs,
        envelope=envelope,
    )


def _make_panel_reviewer_step(
    stage_name: str,
    reviewer_id: str,
    prompt_ref: str,
    inputs: Sequence[str],
    panel_reviewer_order: Mapping[str, Sequence[str]],
) -> PanelReviewerStep:
    return PanelReviewerStep(
        name=f"{stage_name}.{reviewer_id}",
        kind="produce",
        prompt_key=None,
        slot=None,
        _prompt_ref=prompt_ref,
        _pipeline_dir=_PIPELINE_DIR,
        _pipeline_name=name,
        _input_refs=list(inputs),
        _reviewer_id=reviewer_id,
        _panel_reviewer_order=_copy_panel_order(panel_reviewer_order),
        _mode="",
    )


def _make_agent_step(
    stage_name: str,
    prompt_ref: str,
    inputs: Sequence[str],
    panel_reviewer_order: Mapping[str, Sequence[str]],
) -> AgentStep:
    return AgentStep(
        name=stage_name,
        kind="produce",
        prompt_key=None,
        slot=None,
        _prompt_ref=prompt_ref,
        _pipeline_dir=_PIPELINE_DIR,
        _pipeline_name=name,
        _input_refs=list(inputs),
        _produces="markdown",
        _panel_reviewer_order=_copy_panel_order(panel_reviewer_order),
        _mode="",
    )


def _run_panel_reviewer(
    ctx: object,
    *,
    stage_name: str,
    reviewer_id: str,
    prompt_ref: str,
    inputs: Sequence[str],
    panel_reviewer_order: Mapping[str, Sequence[str]],
) -> Any:
    step = _make_panel_reviewer_step(
        stage_name,
        reviewer_id,
        prompt_ref,
        inputs,
        panel_reviewer_order,
    )
    return step.run(_dict_to_step_context(ctx))


def _run_agent(
    ctx: object,
    *,
    stage_name: str,
    prompt_ref: str,
    inputs: Sequence[str],
    panel_reviewer_order: Mapping[str, Sequence[str]],
) -> Any:
    step = _make_agent_step(stage_name, prompt_ref, inputs, panel_reviewer_order)
    return step.run(_dict_to_step_context(ctx))


@phase(name="high_panel.existing_system_reuse")
def _native_high_existing_system_reuse(ctx: object) -> Any:
    return _run_panel_reviewer(
        ctx,
        stage_name="high_panel",
        reviewer_id="existing_system_reuse",
        prompt_ref=_H_EXISTING_SYSTEM_REUSE,
        inputs=("draft",),
        panel_reviewer_order=_EMPTY_PANEL_ORDER,
    )


@phase(name="high_panel.conceptual_fit")
def _native_high_conceptual_fit(ctx: object) -> Any:
    return _run_panel_reviewer(
        ctx,
        stage_name="high_panel",
        reviewer_id="conceptual_fit",
        prompt_ref=_H_CONCEPTUAL_FIT,
        inputs=("draft",),
        panel_reviewer_order=_EMPTY_PANEL_ORDER,
    )


@phase(name="high_panel.missing_abstraction")
def _native_high_missing_abstraction(ctx: object) -> Any:
    return _run_panel_reviewer(
        ctx,
        stage_name="high_panel",
        reviewer_id="missing_abstraction",
        prompt_ref=_H_MISSING_ABSTRACTION,
        inputs=("draft",),
        panel_reviewer_order=_EMPTY_PANEL_ORDER,
    )


@phase(name="high_panel.epic_decomposition")
def _native_high_epic_decomposition(ctx: object) -> Any:
    return _run_panel_reviewer(
        ctx,
        stage_name="high_panel",
        reviewer_id="epic_decomposition",
        prompt_ref=_H_EPIC_DECOMPOSITION,
        inputs=("draft",),
        panel_reviewer_order=_EMPTY_PANEL_ORDER,
    )


@phase(name="high_panel.strategic_risk")
def _native_high_strategic_risk(ctx: object) -> Any:
    return _run_panel_reviewer(
        ctx,
        stage_name="high_panel",
        reviewer_id="strategic_risk",
        prompt_ref=_H_STRATEGIC_RISK,
        inputs=("draft",),
        panel_reviewer_order=_EMPTY_PANEL_ORDER,
    )


@phase(name="high_revise")
def _native_high_revise(ctx: object) -> Any:
    return _run_agent(
        ctx,
        stage_name="high_revise",
        prompt_ref=_HIGH_REVISE_PROMPT,
        inputs=("draft", "high_panel.*"),
        panel_reviewer_order=_HIGH_PANEL_ORDER,
    )


@phase(name="mid_panel.codebase_convention_fit")
def _native_mid_codebase_convention_fit(ctx: object) -> Any:
    return _run_panel_reviewer(
        ctx,
        stage_name="mid_panel",
        reviewer_id="codebase_convention_fit",
        prompt_ref=_M_CODEBASE_CONVENTION_FIT,
        inputs=("high_revise",),
        panel_reviewer_order=_HIGH_PANEL_ORDER,
    )


@phase(name="mid_panel.data_artifact_model")
def _native_mid_data_artifact_model(ctx: object) -> Any:
    return _run_panel_reviewer(
        ctx,
        stage_name="mid_panel",
        reviewer_id="data_artifact_model",
        prompt_ref=_M_DATA_ARTIFACT_MODEL,
        inputs=("high_revise",),
        panel_reviewer_order=_HIGH_PANEL_ORDER,
    )


@phase(name="mid_panel.orchestration_semantics")
def _native_mid_orchestration_semantics(ctx: object) -> Any:
    return _run_panel_reviewer(
        ctx,
        stage_name="mid_panel",
        reviewer_id="orchestration_semantics",
        prompt_ref=_M_ORCHESTRATION_SEMANTICS,
        inputs=("high_revise",),
        panel_reviewer_order=_HIGH_PANEL_ORDER,
    )


@phase(name="mid_panel.agent_model_assignment")
def _native_mid_agent_model_assignment(ctx: object) -> Any:
    return _run_panel_reviewer(
        ctx,
        stage_name="mid_panel",
        reviewer_id="agent_model_assignment",
        prompt_ref=_M_AGENT_MODEL_ASSIGNMENT,
        inputs=("high_revise",),
        panel_reviewer_order=_HIGH_PANEL_ORDER,
    )


@phase(name="mid_panel.blast_radius")
def _native_mid_blast_radius(ctx: object) -> Any:
    return _run_panel_reviewer(
        ctx,
        stage_name="mid_panel",
        reviewer_id="blast_radius",
        prompt_ref=_M_BLAST_RADIUS,
        inputs=("high_revise",),
        panel_reviewer_order=_HIGH_PANEL_ORDER,
    )


@phase(name="mid_revise")
def _native_mid_revise(ctx: object) -> Any:
    return _run_agent(
        ctx,
        stage_name="mid_revise",
        prompt_ref=_MID_REVISE_PROMPT,
        inputs=("high_revise", "mid_panel.*"),
        panel_reviewer_order=_MID_PANEL_ORDER,
    )


@phase(name="low_panel.implementation_feasibility")
def _native_low_implementation_feasibility(ctx: object) -> Any:
    return _run_panel_reviewer(
        ctx,
        stage_name="low_panel",
        reviewer_id="implementation_feasibility",
        prompt_ref=_L_IMPLEMENTATION_FEASIBILITY,
        inputs=("mid_revise",),
        panel_reviewer_order=_MID_PANEL_ORDER,
    )


@phase(name="low_panel.testability")
def _native_low_testability(ctx: object) -> Any:
    return _run_panel_reviewer(
        ctx,
        stage_name="low_panel",
        reviewer_id="testability",
        prompt_ref=_L_TESTABILITY,
        inputs=("mid_revise",),
        panel_reviewer_order=_MID_PANEL_ORDER,
    )


@phase(name="low_panel.edge_cases")
def _native_low_edge_cases(ctx: object) -> Any:
    return _run_panel_reviewer(
        ctx,
        stage_name="low_panel",
        reviewer_id="edge_cases",
        prompt_ref=_L_EDGE_CASES,
        inputs=("mid_revise",),
        panel_reviewer_order=_MID_PANEL_ORDER,
    )


@phase(name="low_panel.cli_ux_details")
def _native_low_cli_ux_details(ctx: object) -> Any:
    return _run_panel_reviewer(
        ctx,
        stage_name="low_panel",
        reviewer_id="cli_ux_details",
        prompt_ref=_L_CLI_UX_DETAILS,
        inputs=("mid_revise",),
        panel_reviewer_order=_MID_PANEL_ORDER,
    )


@phase(name="low_panel.migration_backcompat")
def _native_low_migration_backcompat(ctx: object) -> Any:
    return _run_panel_reviewer(
        ctx,
        stage_name="low_panel",
        reviewer_id="migration_backcompat",
        prompt_ref=_L_MIGRATION_BACKCOMPAT,
        inputs=("mid_revise",),
        panel_reviewer_order=_MID_PANEL_ORDER,
    )


@phase(name="readiness")
def _native_readiness(ctx: object) -> Any:
    return _run_agent(
        ctx,
        stage_name="readiness",
        prompt_ref=_READINESS_PROMPT,
        inputs=("mid_revise", "low_panel.*"),
        panel_reviewer_order=_LOW_PANEL_ORDER,
    )


@pipeline("epic-blitz")
def epic_blitz(ctx: object) -> Any:
    """Native declaration for the epic-blitz graph."""

    for branch in native_panel(
        "high_panel",
        (
            ("existing_system_reuse", _native_high_existing_system_reuse),
            ("conceptual_fit", _native_high_conceptual_fit),
            ("missing_abstraction", _native_high_missing_abstraction),
            ("epic_decomposition", _native_high_epic_decomposition),
            ("strategic_risk", _native_high_strategic_risk),
        ),
    ):
        state = yield branch(ctx)
    state = yield _native_high_revise(ctx)

    for branch in native_panel(
        "mid_panel",
        (
            ("codebase_convention_fit", _native_mid_codebase_convention_fit),
            ("data_artifact_model", _native_mid_data_artifact_model),
            ("orchestration_semantics", _native_mid_orchestration_semantics),
            ("agent_model_assignment", _native_mid_agent_model_assignment),
            ("blast_radius", _native_mid_blast_radius),
        ),
    ):
        state = yield branch(ctx)
    state = yield _native_mid_revise(ctx)

    for branch in native_panel(
        "low_panel",
        (
            ("implementation_feasibility", _native_low_implementation_feasibility),
            ("testability", _native_low_testability),
            ("edge_cases", _native_low_edge_cases),
            ("cli_ux_details", _native_low_cli_ux_details),
            ("migration_backcompat", _native_low_migration_backcompat),
        ),
    ):
        state = yield branch(ctx)
    state = yield _native_readiness(ctx)
    return state


def _make_panel_stage(
    stage_name: str,
    reviewers: Sequence[tuple[str, str]],
    *,
    inputs: Sequence[str],
    panel_reviewer_order: Mapping[str, Sequence[str]],
    edge: Edge,
) -> ParallelStage:
    reviewer_pairs: list[tuple[str, Step]] = []
    for reviewer_id, prompt_ref in reviewers:
        reviewer_pairs.append(
            (
                reviewer_id,
                _make_panel_reviewer_step(
                    stage_name,
                    reviewer_id,
                    prompt_ref,
                    inputs,
                    panel_reviewer_order,
                ),
            )
        )
    return panel_parallel(
        stage_name,
        tuple(reviewer_pairs),
        edges=(edge,),
        merge_strategy="none",
        max_workers=None,
        next_label="next",
    )


def _make_agent_stage(
    stage_name: str,
    prompt_ref: str,
    *,
    inputs: Sequence[str],
    panel_reviewer_order: Mapping[str, Sequence[str]],
    edges: tuple[Edge, ...],
) -> Stage:
    return Stage(
        name=stage_name,
        step=_make_agent_step(stage_name, prompt_ref, inputs, panel_reviewer_order),
        edges=edges,
    )


def _project_native_pipeline() -> Pipeline:
    """Compile/project the native declaration, then specialize Megaplan steps."""

    projected = project_graph(compile_pipeline(epic_blitz), key_mode="phase")
    actual_order = tuple(projected.stages.keys())
    if actual_order != _EPIC_BLITZ_STAGE_ORDER:
        raise RuntimeError(
            "epic-blitz native projection stage order mismatch: "
            f"expected {_EPIC_BLITZ_STAGE_ORDER!r}, got {actual_order!r}"
        )
    if projected.entry != "high_panel":
        raise RuntimeError(
            "epic-blitz native projection entry mismatch: "
            f"expected 'high_panel', got {projected.entry!r}"
        )

    stages: dict[str, Stage | ParallelStage] = {
        "high_panel": _make_panel_stage(
            "high_panel",
            _HIGH_REVIEWERS,
            inputs=("draft",),
            panel_reviewer_order=_EMPTY_PANEL_ORDER,
            edge=Edge("next", "high_revise"),
        ),
        "high_revise": _make_agent_stage(
            "high_revise",
            _HIGH_REVISE_PROMPT,
            inputs=("draft", "high_panel.*"),
            panel_reviewer_order=_HIGH_PANEL_ORDER,
            edges=(Edge("done", "mid_panel"),),
        ),
        "mid_panel": _make_panel_stage(
            "mid_panel",
            _MID_REVIEWERS,
            inputs=("high_revise",),
            panel_reviewer_order=_HIGH_PANEL_ORDER,
            edge=Edge("next", "mid_revise"),
        ),
        "mid_revise": _make_agent_stage(
            "mid_revise",
            _MID_REVISE_PROMPT,
            inputs=("high_revise", "mid_panel.*"),
            panel_reviewer_order=_MID_PANEL_ORDER,
            edges=(Edge("done", "low_panel"),),
        ),
        "low_panel": _make_panel_stage(
            "low_panel",
            _LOW_REVIEWERS,
            inputs=("mid_revise",),
            panel_reviewer_order=_MID_PANEL_ORDER,
            edge=Edge("next", "readiness"),
        ),
        "readiness": _make_agent_stage(
            "readiness",
            _READINESS_PROMPT,
            inputs=("mid_revise", "low_panel.*"),
            panel_reviewer_order=_LOW_PANEL_ORDER,
            edges=(Edge("done", "halt"),),
        ),
    }
    return Pipeline(stages=stages, entry=projected.entry)


def _build_legacy_graph_pipeline() -> Pipeline:
    """Return the pre-native hand-built graph for parity baselines."""

    pipeline = (
        Pipeline.builder(
            "epic-blitz",
            description=description,
            default_profile=default_profile,
            supported_modes=supported_modes,
            pipeline_dir=_PIPELINE_DIR,
        )
        .input("draft", file=True)
        .panel(
            "high_panel",
            reviewers=_HIGH_REVIEWERS,
            inputs=["draft"],
            merge="none",
        )
        .agent(
            "high_revise",
            prompt=_HIGH_REVISE_PROMPT,
            inputs=["draft", "high_panel.*"],
        )
        .panel(
            "mid_panel",
            reviewers=_MID_REVIEWERS,
            inputs=["high_revise"],
            merge="none",
        )
        .agent(
            "mid_revise",
            prompt=_MID_REVISE_PROMPT,
            inputs=["high_revise", "mid_panel.*"],
        )
        .panel(
            "low_panel",
            reviewers=_LOW_REVIEWERS,
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


def build_pipeline() -> Pipeline:
    """Return the canonical native-projected ``epic-blitz`` Pipeline."""

    return _project_native_pipeline()


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
