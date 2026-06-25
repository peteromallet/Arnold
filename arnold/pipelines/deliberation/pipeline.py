"""Deliberation pipeline construction — 10-stage DAG assembler.

Builds the full question-gen → human-gate → draft-plan → layered
critique-panel → skeptical-synthesis → final-report chain and attaches
a native program so the package satisfies the native-first contract.
The graph structure is preserved for topology hashing and baseline
parity; execution is delegated to the native runtime.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Any

from arnold.pipeline.builder import PipelineBuilder
from arnold.pipeline.native.compiler import compile_pipeline
from arnold.pipeline.native.ir import NativeProgram
from arnold.pipeline.resources import PromptSource
from arnold.pipeline.steps.agent import AgentStep, WorkerFn
from arnold.pipeline.types import Edge, Pipeline, Stage

from arnold.pipelines.deliberation import native as _native_module
from arnold.pipelines.deliberation.steps import (
    build_critique_panel_stage,
    build_draft_plan_stage,
    build_final_report_stage,
    build_human_gate_stage,
    build_question_gen_stage,
    build_skeptical_synthesis_stage,
)

# ---------------------------------------------------------------------------
# Layer ordering — descriptive name → zero-based index
# ---------------------------------------------------------------------------

_LAYER_ORDER: tuple[tuple[str, int], ...] = (
    ("high", 0),
    ("mid", 1),
    ("low", 2),
)

# Number of layers in the deliberation pipeline.
_LAYER_COUNT: int = len(_LAYER_ORDER)


# ---------------------------------------------------------------------------
# No-op event sink (used when no journal is wired at construction time)
# ---------------------------------------------------------------------------


class _NoopEventSink:
    """An :class:`EventSink` that silently discards every event.

    Used as a fallback when :func:`build_skeptical_synthesis_stage`
    requires a ``journal`` but the initial pipeline construction has
    not yet been given an :class:`~arnold.runtime.event_journal.EventSink`.
    """

    def emit(self, kind: str, *, payload=None, scope=None, phase=None, idempotency_key=None) -> None:  # type: ignore[no-untyped-def]
        pass


_NOOP_SINK = _NoopEventSink()


# ---------------------------------------------------------------------------
# Native bundle defaults (for manifest-introspection builds without profile)
# ---------------------------------------------------------------------------


def _noop_worker(**kwargs: Any) -> str:
    """Placeholder worker used when compiling a manifest-only native program."""
    return ""


def _default_profile() -> dict[str, Any]:
    return {
        "question_gen": "default",
        "draft_plan": "default",
        "layer_high_panel": "high",
        "layer_high_synth": "default",
        "layer_mid_panel": "mid",
        "layer_mid_synth": "default",
        "layer_low_panel": "low",
        "layer_low_synth": "default",
        "final_report": "default",
    }


def _default_workers() -> dict[str, WorkerFn]:
    return {"default": _noop_worker}


def _default_prompts() -> PromptSource:
    return ""


def _native_bundle(
    profile: dict[str, Any],
    workers: dict[str, WorkerFn],
    prompts: PromptSource | None = None,
) -> NativeProgram:
    """Compile the deliberation native program for *profile*/*workers*/*prompts*.

    The returned :class:`~arnold.pipeline.native.ir.NativeProgram` is also
    stored in the native module's runtime configuration so the phase functions
    can resolve workers and prompts when the program runs.
    """
    _native_module._set_bundle_config(  # type: ignore[attr-defined]
        profile=profile,
        workers=workers,
        prompts=prompts if prompts is not None else _default_prompts(),
    )
    return compile_pipeline(_native_module.deliberation_native)  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# Worker resolution
# ---------------------------------------------------------------------------


def _resolve_panel_worker(
    profile: dict[str, Any],
    workers: dict[str, WorkerFn],
    panel_key: str,
) -> WorkerFn:
    """Resolve the worker for a critique-panel stage.

    Resolution rules (first match wins):

    1. *profile*[*panel_key*] is a string that matches a key in
       *workers* → return that worker.
    2. *profile*[*panel_key*] is a string that does NOT match any
       worker → treat it as an abstraction-level shorthand and
       fall through to the default (first available worker).
    3. *profile*[*panel_key*] is a dict (structured panel config) →
       use the first available worker as fallback.

    Raises :exc:`ValueError` when no workers are registered at all.
    """
    entry = profile.get(panel_key)
    if isinstance(entry, str):
        worker = workers.get(entry)
        if worker is not None:
            return worker
        # String doesn't match a worker — treat as abstraction-level
        # shorthand (e.g. 'high', 'mid', 'low') and fall through.
    # Dict entry or unrecognized string — use any available worker.
    if workers:
        return next(iter(workers.values()))
    raise ValueError(
        f"Panel stage {panel_key!r}: no workers registered — "
        f"cannot resolve a worker for the critique panel"
    )


def _resolve_agent_worker(
    profile: dict[str, Any],
    workers: dict[str, WorkerFn],
    stage_key: str,
) -> WorkerFn:
    """Resolve the worker for a single-agent stage.

    Reads *profile*[*stage_key*] as an agent name and looks it up in
    *workers*.

    Raises :exc:`ValueError` when the profile entry is missing or the
    agent name is unknown.
    """
    agent = profile.get(stage_key)
    if not isinstance(agent, str):
        raise ValueError(
            f"Stage {stage_key!r} expects a string agent name in the "
            f"profile, got {type(agent).__name__}"
        )
    worker = workers.get(agent)
    if worker is None:
        raise ValueError(
            f"Stage {stage_key!r} references agent {agent!r} but no "
            f"such worker is registered"
        )
    return worker


# ---------------------------------------------------------------------------
# build_initial_pipeline
# ---------------------------------------------------------------------------


def build_initial_pipeline(
    *,
    profile: dict[str, Any],
    workers: dict[str, WorkerFn],
    prompts: PromptSource | None = None,
) -> Pipeline:
    """Build the full 10-stage deliberation :class:`Pipeline`.

    The DAG (with edge labels in parentheses)::

        question_gen (done) → human_gate (answers_collected) →
        draft_plan (done) → layer_high_panel (panel_done) →
        layer_high_synth (done) → layer_mid_panel (panel_done) →
        layer_mid_synth (done) → layer_low_panel (panel_done) →
        layer_low_synth (done) → final_report (done) → halt

    Parameters
    ----------
    profile:
        Mapping of stage names → agent-spec strings (or dicts for
        critique-panel configuration).  Expected keys:

        * ``question_gen`` — agent name
        * ``draft_plan`` — agent name
        * ``layer_high_panel`` — agent name or ``{abstraction_level,
          ...}`` dict
        * ``layer_high_synth`` — agent name
        * ``layer_mid_panel`` — agent name or dict
        * ``layer_mid_synth`` — agent name
        * ``layer_low_panel`` — agent name or dict
        * ``layer_low_synth`` — agent name
        * ``final_report`` — agent name
    workers:
        Mapping of agent names → :data:`WorkerFn` callables.
    prompts:
        Optional :class:`PromptSource` used by every stage.  When
        ``None``, each stage falls back to its built-in prompt text.
    """
    prompt_source = prompts

    builder = PipelineBuilder(
        name="deliberation",
        description="Deliberation pipeline — layered idea refinement",
    )

    # -- stage 1: question_gen -------------------------------------------
    qg_worker = _resolve_agent_worker(profile, workers, "question_gen")
    qg_stage = build_question_gen_stage(prompt_source, qg_worker)
    # Edge already: done → human_gate
    builder.add_stage(qg_stage, emit_label="done")

    # -- stage 2: human_gate ---------------------------------------------
    hg_stage = build_human_gate_stage()
    # Edge already: answers_collected → draft_plan
    builder.add_stage(hg_stage, emit_label="answers_collected")

    # -- stage 3: draft_plan ---------------------------------------------
    dp_worker = _resolve_agent_worker(profile, workers, "draft_plan")
    dp_stage = build_draft_plan_stage(prompt_source, dp_worker)
    # Override the hard-coded edge target (layer_0_synth → layer_high_panel).
    dp_stage = replace(
        dp_stage,
        edges=(Edge(label="done", target="layer_high_panel"),),
    )
    builder.add_stage(dp_stage, emit_label="done")

    # -- stages 4–9: layered critique panels + skeptical synthesis -------
    for i, (layer_name, layer_idx) in enumerate(_LAYER_ORDER):
        panel_key = f"layer_{layer_name}_panel"
        synth_key = f"layer_{layer_name}_synth"

        # Determine the downstream target for this layer's synthesis.
        if i < _LAYER_COUNT - 1:
            next_layer_name = _LAYER_ORDER[i + 1][0]
            synth_next_target = f"layer_{next_layer_name}_panel"
        else:
            synth_next_target = "final_report"

        # --- Panel stage ---
        panel_config = profile.get(panel_key, layer_name)
        panel_worker = _resolve_panel_worker(profile, workers, panel_key)
        panel_stage = build_critique_panel_stage(
            layer=layer_idx,
            profile_layer_config=panel_config,
            prompt_source=prompt_source,
            worker=panel_worker,
        )
        # Rename stage and internal steps from numeric → descriptive.
        _rename_parallel_stage(panel_stage, layer_idx, layer_name, panel_key)
        # Override edge target (layer_{idx}_synth → descriptive synth name).
        panel_stage = replace(
            panel_stage,
            edges=(Edge(label="panel_done", target=synth_key),),
        )
        builder.add_parallel_stage(panel_stage, emit_label="panel_done")

        # --- Synthesis stage ---
        synth_worker = _resolve_agent_worker(profile, workers, synth_key)
        synth_stage = build_skeptical_synthesis_stage(
            layer=layer_idx,
            next_target=synth_next_target,
            prompt_source=prompt_source,
            worker=synth_worker,
            journal=_NOOP_SINK,
        )
        # Rename stage and internal step from numeric → descriptive.
        _rename_synth_stage(synth_stage, layer_idx, layer_name, synth_key)
        builder.add_stage(synth_stage, emit_label="done")

    # -- stage 10: final_report ------------------------------------------
    fr_worker = _resolve_agent_worker(profile, workers, "final_report")
    fr_stage = build_final_report_stage(prompt_source, fr_worker)
    # Edge already: done → halt
    builder.add_stage(fr_stage, emit_label="done")

    pipeline = builder.build()
    program = _native_bundle(profile, workers, prompt_source)
    return replace(pipeline, resource_bundles=(), native_program=program)


# ---------------------------------------------------------------------------
# build_pipeline  (manifest entrypoint)
# ---------------------------------------------------------------------------


def build_pipeline(name: str = "deliberation", **kwargs: Any) -> Pipeline:
    """Manifest entrypoint — delegates to :func:`build_initial_pipeline`.

    Accepts ``name`` and any keyword arguments that
    :func:`build_initial_pipeline` expects.  When *profile* and
    *workers* are not provided, returns an empty pipeline shell with
    a compiled native program attached for manifest-introspection tests.
    """
    profile = kwargs.pop("profile", None)
    workers = kwargs.pop("workers", None)
    prompts = kwargs.pop("prompts", None)

    program = _native_bundle(
        _default_profile(),
        _default_workers(),
        prompts if prompts is not None else _default_prompts(),
    )

    if profile is None or workers is None:
        # Manifest-introspection shell: no graph stages, but a compiled native
        # program is attached so the package satisfies the native-first contract.
        shell_stage = Stage(
            name="manifest_introspection",
            step=AgentStep(name="manifest_introspection"),
        )
        return Pipeline(
            stages={"manifest_introspection": shell_stage},
            entry="manifest_introspection",
            resource_bundles=(),
            native_program=program,
        )

    return build_initial_pipeline(profile=profile, workers=workers, prompts=prompts)


# ---------------------------------------------------------------------------
# Internal helpers — stage renaming
# ---------------------------------------------------------------------------


def _rename_parallel_stage(
    stage: Any,
    layer_idx: int,
    layer_name: str,
    new_name: str,
) -> None:
    """Mutate *stage* (a ParallelStage) so its name and internal step
    names use *layer_name* instead of the numeric *layer_idx* prefix.
    """
    old_prefix = f"layer_{layer_idx}_panel"
    object.__setattr__(stage, "name", new_name)

    renamed_steps: list[Any] = []
    for step in stage.steps:
        step.name = step.name.replace(old_prefix, new_name, 1)
        renamed_steps.append(step)
    object.__setattr__(stage, "steps", tuple(renamed_steps))


def _rename_synth_stage(
    stage: Any,
    layer_idx: int,
    layer_name: str,
    new_name: str,
) -> None:
    """Mutate *stage* (a Stage) so its name and internal AgentStep name
    use *layer_name* instead of the numeric *layer_idx* prefix.
    """
    object.__setattr__(stage, "name", new_name)
    stage.step.name = new_name  # AgentStep.name is mutable
