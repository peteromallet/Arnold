"""Python composition of the first-class ``doc`` pipeline.

Linear topology with NO gate stage — single-pass critique + revise,
then assembly:

    outline → section_drafts → critique → revise → assembly

* ``outline`` emits a ``sections`` JSON artifact (a list of section
  specs the per-section drafts stage will fan out over).
* ``section_drafts`` is the in-tree consumer of the new dynamic
  primitives: a :func:`dynamic_fanout` SubloopStep whose generator
  reads the outline-emitted artifact and whose ``base_prompt`` is a
  per-section execute step. The join concatenates the per-section
  outputs into a single mapping that downstream stages consume.
* ``critique`` and ``revise`` are direct ``Step``s (not
  ``critique_revise_gate_loop``) — there is no third ``gate`` stage in
  ``pipeline.stages``. The doc pipeline is deliberately single-pass.
* ``assembly`` concatenates the section drafts + revisions into the
  final document. Its ``run()`` returns ``next='halt'`` directly per
  ``executor.py:218-220`` (a ``halt``-labelled edge would be
  unreachable; the assembly Stage carries no halt edge).

Per-stage prompt files are bundled under
``megaplan/pipelines/doc/prompts/``. The public Step shells in
``megaplan.pipelines.doc.steps`` carry the canonical ``prompt_key`` slots
(``outline_doc`` / ``execute_doc`` / ``critique_doc`` / ``revise_doc``
/ ``assemble_doc``).
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Any, Mapping

from arnold.pipeline.native import (
    compile_pipeline,
    phase,
    pipeline,
)
from arnold.pipeline import Edge, Pipeline, Stage
from arnold.pipeline.pattern_dynamic import run_fanout
from arnold_pipelines.megaplan.step_types import StepContext, StepResult
from arnold_pipelines.megaplan.pipelines.doc.steps import (
    AssemblyStep,
    CritiqueStep,
    OutlineArtifactReader,
    OutlineStep,
    ReviseStep,
    SectionDraftStep,
    concat_sections_join,
)

# ── Module-level metadata surfaced via PipelineRegistry ────────────────

name: str = "doc"
description: str = (
    "Linear doc pipeline: outline → per-section drafts (dynamic fanout) "
    "→ critique → revise → assembly. Single-pass; no gate."
)
default_profile: str | None = None
supported_modes: tuple[str, ...] = ("native",)
recommended_profiles: tuple[str, ...] = ()
driver: tuple[str, str] = ("native", "dynamic-fanout")
entrypoint: str = "build_pipeline"
arnold_api_version: str = "1.0"
capabilities: tuple[str, ...] = ("doc",)


# ── Native helpers ─────────────────────────────────────────────────────


def _ctx_from_native(raw_ctx: object) -> StepContext:
    """Adapt the native runtime's dict context to a Megaplan StepContext."""
    if isinstance(raw_ctx, dict):
        raw_inputs = raw_ctx.get("inputs") or {}
        inputs = (
            {str(key): value for key, value in raw_inputs.items()}
            if isinstance(raw_inputs, Mapping)
            else {}
        )
        return StepContext(
            plan_dir=Path(
                raw_ctx.get("plan_dir") or raw_ctx.get("artifact_root") or "."
            ),
            state=raw_ctx.get("state", {}),
            profile=raw_ctx.get("profile"),
            mode=str(raw_ctx.get("mode") or "doc"),
            inputs=inputs,
            envelope=raw_ctx.get("envelope"),
        )
    plan_dir = getattr(raw_ctx, "plan_dir", None) or getattr(
        raw_ctx,
        "artifact_root",
        ".",
    )
    raw_inputs = getattr(raw_ctx, "inputs", {}) or {}
    inputs = (
        {str(key): value for key, value in raw_inputs.items()}
        if isinstance(raw_inputs, Mapping)
        else {}
    )
    return StepContext(
        plan_dir=Path(plan_dir),
        state=getattr(raw_ctx, "state", {}) or {},
        profile=getattr(raw_ctx, "profile", None),
        mode=str(getattr(raw_ctx, "mode", None) or "doc"),
        inputs=inputs,
        envelope=getattr(raw_ctx, "envelope", None),
    )


def _json_safe_step_result(result: StepResult) -> StepResult:
    """Keep native state and resume cursors JSON-serializable."""
    return replace(
        result,
        outputs={key: str(value) for key, value in result.outputs.items()},
    )


class _SectionDraftsFanoutStep:
    name = "section_drafts"
    kind = "fanout"
    prompt_key = None
    slot = None

    def run(self, ctx: StepContext) -> StepResult:
        return run_fanout(
            OutlineArtifactReader(artifact_label="sections"),
            SectionDraftStep(),
            concat_sections_join,
            ctx,
            typed_ports=False,
        )


def _section_drafts_step() -> Any:
    return _SectionDraftsFanoutStep()


# ── Native phase wrappers ───────────────────────────────────────────────


@phase(name="outline")
def _native_outline(ctx: object) -> StepResult:
    return _json_safe_step_result(OutlineStep().run(_ctx_from_native(ctx)))


@phase(name="section_drafts")
def _native_section_drafts(ctx: object) -> StepResult:
    return _json_safe_step_result(_section_drafts_step().run(_ctx_from_native(ctx)))


@phase(name="critique")
def _native_critique(ctx: object) -> StepResult:
    return _json_safe_step_result(CritiqueStep().run(_ctx_from_native(ctx)))


@phase(name="revise")
def _native_revise(ctx: object) -> StepResult:
    return _json_safe_step_result(ReviseStep().run(_ctx_from_native(ctx)))


@phase(name="assembly")
def _native_assembly(ctx: object) -> StepResult:
    return _json_safe_step_result(AssemblyStep().run(_ctx_from_native(ctx)))


# ── Native pipeline bundle ───────────────────────────────────────────────


@pipeline("doc")
def doc_native(ctx: object) -> Any:
    state = yield _native_outline(ctx)
    state = yield _native_section_drafts(ctx)
    state = yield _native_critique(ctx)
    state = yield _native_revise(ctx)
    state = yield _native_assembly(ctx)
    return state


def _native_bundle() -> Any:
    return compile_pipeline(doc_native)


# ── Pipeline assembly ──────────────────────────────────────────────────


def _build_graph_pipeline() -> Pipeline:
    """Return the canonical ``doc`` :class:`Pipeline`.

    Stage order (insertion-order preserved via plain ``dict``):

    1. ``outline`` — emits ``sections`` JSON artifact.
    2. ``section_drafts`` — :func:`dynamic_fanout` SubloopStep wrapping
       the outline reader + per-section base_prompt.
    3. ``critique`` — direct Step (no gate loop).
    4. ``revise`` — direct Step (no gate loop).
    5. ``assembly`` — terminal Step (returns ``next='halt'``).
    """

    stages: dict[str, Stage] = {
        "outline": Stage(
            name="outline",
            step=OutlineStep(),
            edges=(Edge(label="section_drafts", target="section_drafts"),),
        ),
        "section_drafts": Stage(
            name="section_drafts",
            step=_section_drafts_step(),
            edges=(Edge(label="critique", target="critique"),),
        ),
        "critique": Stage(
            name="critique",
            step=CritiqueStep(),
            edges=(Edge(label="revise", target="revise"),),
        ),
        "revise": Stage(
            name="revise",
            step=ReviseStep(),
            edges=(Edge(label="assembly", target="assembly"),),
        ),
        "assembly": Stage(
            name="assembly",
            step=AssemblyStep(),
            edges=(),
        ),
    }

    pipeline = Pipeline(stages=stages, entry="outline", resource_bundles=())
    return pipeline


def build_pipeline() -> Pipeline:
    """Return the native-backed ``doc`` :class:`Pipeline`.

    The graph shell remains available for explicit legacy execution; the
    canonical runtime dispatches through the attached ``native_program``.
    """
    graph = _build_graph_pipeline()
    return replace(
        graph,
        native_program=_native_bundle(),
        resource_bundles=(),
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
    "doc_native",
]
