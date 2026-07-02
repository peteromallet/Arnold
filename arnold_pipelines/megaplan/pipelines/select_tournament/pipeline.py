"""Native declaration and builder for the ``select-tournament`` pipeline.

Topology:

    score_candidates (fanout) -> pairwise_bracket -> winner

The boundary between every stage is a declared typed Port:
``candidate_scores`` feeds the bracket reducer, and ``bracket_result`` feeds
the winner stage. The terminal winner artifact is also declared as a Port so
consumers can bind to it later without scraping state.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import replace
from pathlib import Path
from typing import Any

from arnold.pipeline.declaration_lowering import bind_with_lowered_declarations
from arnold.pipeline.native import NativeProgram, phase, project_graph
from arnold.pipeline.native.ir import NativeInstruction, NativePhase, ParallelInstruction
from arnold.pipeline.contracts import (
    BindResult,
    PortBindError,
    RepairGradient,
    bind,
)
from arnold.runtime.envelope import EMPTY_ENVELOPE
from arnold_pipelines.megaplan.feature_flags import typed_ports_on
from arnold.pipeline.types import (
    Edge,
    ParallelStage,
    Port,
    PortRef,
    Pipeline,
    Stage,
    StepContext as _CanonicalStepContext,
    StepResult,
)
from arnold_pipelines.megaplan.step_types import StepContext as _StepContext
from .steps import (
    BRACKET_RESULT_PORT,
    CANDIDATE_SCORES_PORT,
    WINNER_PORT,
    CandidateScoreStep,
    PairwiseBracketStep,
    WinnerStep,
    join_candidate_scores,
)


DEFAULT_CANDIDATES: tuple[str, ...] = (
    "alpha",
    "beta",
    "gamma",
    "delta",
)
_CANDIDATE_SCORE_STATE_PREFIX = "__select_tournament_candidate_score_"

name: str = "select-tournament"
description: str = (
    "Selection tournament pipeline: fan out per-candidate scoring, reduce "
    "scores through a pairwise bracket, then emit a winner artifact."
)
default_profile: str | None = None
supported_modes: tuple[str, ...] = ("native",)
recommended_profiles: tuple[str, ...] = ()
driver: tuple[str, str] = ("native", "fanout+pairwise-reduce")
entrypoint: str = "build_pipeline"
arnold_api_version: str = "1.0"
capabilities: tuple[str, ...] = ("review",)


def _candidate_score_state_key(seed: int) -> str:
    return f"{_CANDIDATE_SCORE_STATE_PREFIX}{seed}"


def _candidate_score_steps(candidates: Sequence[str]) -> tuple[CandidateScoreStep, ...]:
    """Return deterministic per-candidate scoring steps in seed order."""

    total = max(1, len(candidates))
    return tuple(
        CandidateScoreStep(
            candidate=str(candidate),
            seed=index,
            score=float(index + 1) / float(total),
        )
        for index, candidate in enumerate(candidates)
    )


def _dict_to_step_context(ctx: object) -> _StepContext:
    """Adapt native-runtime contexts to the Megaplan StepContext expected here."""

    if isinstance(ctx, _StepContext):
        return ctx
    if isinstance(ctx, _CanonicalStepContext):
        return _StepContext(
            plan_dir=Path(ctx.artifact_root),
            state=dict(ctx.state) if isinstance(ctx.state, dict) else {},
            profile={},
            mode=ctx.mode,
            inputs=dict(ctx.inputs),
            envelope=ctx.envelope or EMPTY_ENVELOPE,
        )
    if hasattr(ctx, "plan_dir") and hasattr(ctx, "state") and hasattr(ctx, "profile"):
        return ctx  # type: ignore[return-value]

    if isinstance(ctx, dict):
        raw_state = ctx.get("state") or {}
        raw_inputs = ctx.get("inputs") or {}
        root = ctx.get("artifact_root") or ctx.get("plan_dir") or "."
        envelope = ctx.get("envelope") or EMPTY_ENVELOPE
        mode = str(ctx.get("mode") or "select")
        profile = ctx.get("profile") or {}
    else:
        raw_state = getattr(ctx, "state", {}) or {}
        raw_inputs = getattr(ctx, "inputs", {}) or {}
        root = getattr(ctx, "artifact_root", None) or getattr(ctx, "plan_dir", ".")
        envelope = getattr(ctx, "envelope", None) or EMPTY_ENVELOPE
        mode = str(getattr(ctx, "mode", "select") or "select")
        profile = getattr(ctx, "profile", {}) or {}

    inputs = {
        str(key): Path(value) if isinstance(value, str) else value
        for key, value in dict(raw_inputs).items()
    }
    if isinstance(raw_state, dict):
        for port_name in (CANDIDATE_SCORES_PORT.name, BRACKET_RESULT_PORT.name):
            value = raw_state.get(port_name)
            if value is not None:
                inputs.setdefault(
                    port_name,
                    Path(value) if isinstance(value, str) else value,
                )
    return _StepContext(
        plan_dir=Path(root),
        state=dict(raw_state) if isinstance(raw_state, dict) else raw_state,
        profile=profile,
        mode=mode,
        inputs=inputs,
        envelope=envelope,
    )


def _candidate_score_phase(step: CandidateScoreStep):
    """Return a candidate-specific native phase for the attached program."""

    def _native_candidate_score(ctx: object) -> Any:
        result = step.run(_dict_to_step_context(ctx))
        outputs = dict(result.outputs)
        score_path = outputs.get("candidate_score")
        if score_path is not None:
            outputs[_candidate_score_state_key(step.seed)] = score_path
        return replace(result, outputs=outputs)

    _native_candidate_score.__name__ = f"_native_candidate_score_{step.seed}"
    return phase(
        name=f"candidate_score_{step.seed}",
        produces=(CANDIDATE_SCORES_PORT,),
    )(_native_candidate_score)


def _materialize_candidate_scores(ctx: object) -> _StepContext:
    step_ctx = _dict_to_step_context(ctx)
    if CANDIDATE_SCORES_PORT.name in step_ctx.inputs:
        return step_ctx

    raw_state = step_ctx.state if isinstance(step_ctx.state, dict) else {}
    score_paths: list[tuple[int, Path]] = []
    for key, value in raw_state.items():
        if not str(key).startswith(_CANDIDATE_SCORE_STATE_PREFIX):
            continue
        seed = int(str(key).removeprefix(_CANDIDATE_SCORE_STATE_PREFIX))
        score_paths.append((seed, Path(value)))
    if not score_paths:
        return step_ctx

    score_paths.sort(key=lambda item: item[0])
    joined = join_candidate_scores(
        [
            StepResult(outputs={"candidate_score": score_path})
            for _, score_path in score_paths
        ],
        step_ctx,
    )
    candidate_scores_path = Path(joined.outputs[CANDIDATE_SCORES_PORT.name])
    inputs = dict(step_ctx.inputs)
    inputs[CANDIDATE_SCORES_PORT.name] = candidate_scores_path
    state = dict(raw_state)
    state[CANDIDATE_SCORES_PORT.name] = candidate_scores_path
    return replace(step_ctx, inputs=inputs, state=state)


@phase(
    name="pairwise_bracket",
    consumes=(PortRef(CANDIDATE_SCORES_PORT.name, CANDIDATE_SCORES_PORT.content_type),),
    produces=(BRACKET_RESULT_PORT,),
)
def _native_pairwise_bracket(ctx: object) -> Any:
    return PairwiseBracketStep().run(_materialize_candidate_scores(ctx))


@phase(
    name="winner",
    consumes=(PortRef(BRACKET_RESULT_PORT.name, BRACKET_RESULT_PORT.content_type),),
    produces=(WINNER_PORT,),
)
def _native_winner(ctx: object) -> Any:
    return WinnerStep().run(_dict_to_step_context(ctx))


def _native_program(candidate_list: tuple[str, ...]) -> NativeProgram:
    """Build a native declaration whose fanout branches match candidates."""

    branch_funcs = tuple(
        _candidate_score_phase(step)
        for step in _candidate_score_steps(candidate_list)
    )
    branch_names = tuple(
        getattr(func, "__phase_name__", func.__name__)
        for func in branch_funcs
    )
    merge_pc = 1 + len(branch_funcs)
    parallel_block = ParallelInstruction(
        name="score_candidates",
        branches=branch_names,
        branch_funcs=branch_funcs,
        reducer=join_candidate_scores,
        merge_pc=merge_pc,
    )

    instructions: list[NativeInstruction] = [
        NativeInstruction(
            pc=0,
            op="parallel",
            name="score_candidates",
            next_pc=1,
            subprogram=parallel_block,
            parallel_index=0,
        )
    ]
    phases: list[NativePhase] = []
    for offset, func in enumerate(branch_funcs, start=1):
        produces = tuple(getattr(func, "__phase_produces__", ()) or ())
        phase_ir = NativePhase(
            name=getattr(func, "__phase_name__", func.__name__),
            func=func,
            produces=produces,
        )
        phases.append(phase_ir)
        instructions.append(
            NativeInstruction(
                pc=offset,
                op="phase",
                name=phase_ir.name,
                func=func,
                next_pc=offset + 1,
                produces=produces,
            )
        )

    tail_specs = (
        ("pairwise_bracket", _native_pairwise_bracket),
        ("winner", _native_winner),
    )
    for index, (stage_name, func) in enumerate(tail_specs, start=merge_pc):
        produces = tuple(getattr(func, "__phase_produces__", ()) or ())
        consumes = tuple(getattr(func, "__phase_consumes__", ()) or ())
        phases.append(
            NativePhase(
                name=stage_name,
                func=func,
                produces=produces,
                consumes=consumes,
            )
        )
        instructions.append(
            NativeInstruction(
                pc=index,
                op="phase",
                name=stage_name,
                func=func,
                next_pc=index + 1,
                produces=produces,
                consumes=consumes,
            )
        )

    instructions.append(NativeInstruction(pc=merge_pc + len(tail_specs), op="halt"))
    return NativeProgram(
        name="select-tournament",
        instructions=tuple(instructions),
        phases=tuple(phases),
        parallel_blocks=(parallel_block,),
    )


def _bind_or_raise(pipeline: Pipeline) -> Pipeline:
    edges = {
        stage_name: tuple(
            edge.target
            for edge in stage.edges
            if edge.target != "halt" and edge.target in pipeline.stages
        )
        for stage_name, stage in pipeline.stages.items()
    }
    result = bind_with_lowered_declarations(pipeline.stages, edges)
    if result is None:
        result = bind(pipeline.stages, edges)
    if isinstance(result, RepairGradient):
        wanted = getattr(result.wanted, "port_name", result.wanted)
        raise PortBindError(
            "select-tournament",
            str(wanted),
            f"bind failed: {result.error_kind}",
        )
    assert isinstance(result, BindResult)
    return replace(pipeline, binding_map=result.binding_map)


def _project_native_pipeline(candidate_list: tuple[str, ...]) -> Pipeline:
    """Compile/project the native declaration and specialize candidate scoring."""

    program = _native_program(candidate_list)
    projected = project_graph(program, key_mode="phase")
    projected_stages = projected.stages
    for stage_name in ("score_candidates", "pairwise_bracket", "winner"):
        if stage_name not in projected_stages:
            raise RuntimeError(
                f"select-tournament native projection missing stage {stage_name!r}"
            )

    score_projected = projected_stages["score_candidates"]
    pairwise_projected = projected_stages["pairwise_bracket"]

    stages = {
        "score_candidates": ParallelStage(
            name="score_candidates",
            steps=_candidate_score_steps(candidate_list),
            join=join_candidate_scores,
            edges=tuple(score_projected.edges),
            max_workers=len(candidate_list),
            produces=(CANDIDATE_SCORES_PORT,),
        ),
        "pairwise_bracket": Stage(
            name="pairwise_bracket",
            step=PairwiseBracketStep(),
            edges=tuple(pairwise_projected.edges),
            consumes=(PortRef(CANDIDATE_SCORES_PORT.name, CANDIDATE_SCORES_PORT.content_type),),
            produces=(BRACKET_RESULT_PORT,),
        ),
        "winner": Stage(
            name="winner",
            step=WinnerStep(),
            edges=(),
            consumes=(PortRef(BRACKET_RESULT_PORT.name, BRACKET_RESULT_PORT.content_type),),
            produces=(WINNER_PORT,),
        ),
    }
    return Pipeline(
        stages=stages,
        entry=projected.entry,
        resource_bundles=(),
        native_program=program,
    )


def build_pipeline(
    candidates: Sequence[str] = DEFAULT_CANDIDATES,
) -> Pipeline:
    """Return the canonical native-projected ``select-tournament`` pipeline."""

    candidate_list = tuple(str(candidate) for candidate in candidates)
    if not candidate_list:
        raise ValueError("select-tournament requires at least one candidate")

    pipeline = _project_native_pipeline(candidate_list)
    if typed_ports_on():
        return _bind_or_raise(pipeline)
    return replace(pipeline, binding_map=None)


def _build_legacy_graph_pipeline(
    candidates: Sequence[str] = DEFAULT_CANDIDATES,
) -> Pipeline:
    """Return the graph-shell baseline for parity tests.

    The native declaration is the source of truth; this builder exposes the
    same projected shell without the attached ``native_program`` so legacy
    graph-executor parity coverage can compare the two runtime paths.
    """

    candidate_list = tuple(str(candidate) for candidate in candidates)
    if not candidate_list:
        raise ValueError("select-tournament requires at least one candidate")

    pipeline = _project_native_pipeline(candidate_list)
    return replace(pipeline, native_program=None)


__all__ = [
    "DEFAULT_CANDIDATES",
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
