"""Python composition of the ``doc`` pipeline (0.23, T4).

First-class doc pipeline replacing the legacy ``--mode doc`` overlay on
``planning``. Linear topology with NO gate stage — single-pass critique
+ revise, then assembly:

    outline → section_drafts → critique → revise → assembly

* ``outline`` emits a ``sections`` JSON artifact (a list of section
  specs the per-section drafts stage will fan out over).
* ``section_drafts`` is the in-tree consumer of the new dynamic
  primitives: a :func:`dynamic_fanout` SubloopStep whose generator
  reads the outline-emitted artifact and whose ``base_prompt`` is a
  per-section execute step. The join concatenates the per-section
  outputs into a single mapping that downstream stages consume.
* ``critique`` and ``revise`` are direct ``Step``s (NOT
  ``critique_revise_gate_loop``) — there is no third ``gate`` stage in
  ``pipeline.stages``. The doc pipeline drops the legacy
  iterate/proceed/tiebreaker/escalate gate semantics doc-mode under
  planning had; this is a deliberate behaviour delta documented in
  the 0.23.0 changelog (single-pass topology).
* ``assembly`` concatenates the section drafts + revisions into the
  final document. Its ``run()`` returns ``next='halt'`` directly per
  ``executor.py:218-220`` (a ``halt``-labelled edge would be
  unreachable; the assembly Stage carries no halt edge).

Per-stage prompt files are relocated and registered under
``megaplan/pipelines/doc/prompts/`` in T5 (next batches). The Stage
shells defined here carry the canonical ``prompt_key`` slots
(``outline_doc`` / ``execute_doc`` / ``critique_doc`` / ``revise_doc``
/ ``assemble_doc``) so T5's ``register_pipeline_prompt`` calls land in
the expected slots.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

from megaplan._pipeline.patterns import dynamic_fanout
from megaplan._pipeline.types import (
    Edge,
    Pipeline,
    Stage,
    StepContext,
    StepResult,
)

# Import the prompts sub-package for its register_pipeline_prompt side-effects.
from megaplan.pipelines.doc import prompts as _prompts  # noqa: F401


_PIPELINE_DIR: Path = Path(__file__).parent / "doc"


# ── Module-level metadata surfaced via PipelineRegistry ────────────────

description: str = (
    "Linear doc pipeline: outline → per-section drafts (dynamic fanout) "
    "→ critique → revise → assembly. Single-pass; no gate."
)
default_profile: str | None = None
supported_modes: tuple[str, ...] = ()
recommended_profiles: tuple[str, ...] = ()


# ── Stage step shells ─────────────────────────────────────────────────


@dataclass(frozen=True)
class _OutlineStep:
    """Emits a ``sections`` JSON artifact.

    The actual prompt rendering + worker invocation is wired in T5 via
    pipeline-scoped prompt registration (``register_pipeline_prompt``
    against the ``outline_doc`` key). The shell here ensures the
    artifact contract — a JSON list at ``<plan_dir>/outline/sections.json``
    — is honoured even when the worker has not run yet.
    """

    name: str = "outline"
    kind: str = "produce"
    prompt_key: str | None = "outline_doc"
    slot: str | None = None

    def run(self, ctx: StepContext) -> StepResult:
        out = Path(ctx.plan_dir) / "outline" / "sections.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        if not out.exists():
            out.write_text(json.dumps([]))
        return StepResult(outputs={"sections": out}, next="section_drafts")


@dataclass(frozen=True)
class _OutlineArtifactReader:
    """Generator for the section_drafts ``dynamic_fanout`` SubloopStep.

    Reads the ``sections`` artifact emitted by the outline stage and
    surfaces it as ``state_patch['specs']`` — the in-memory list path
    of :func:`dynamic_fanout`'s spec resolution.
    """

    name: str = "outline_artifact_reader"
    kind: str = "produce"
    prompt_key: str | None = None
    slot: str | None = None
    artifact_label: str = "sections"

    def run(self, ctx: StepContext) -> StepResult:
        path: Path | None = None
        if isinstance(ctx.inputs, Mapping):
            raw = ctx.inputs.get(self.artifact_label)
            if raw is not None:
                path = Path(raw)
        if path is None:
            path = Path(ctx.plan_dir) / "outline" / "sections.json"
        if not path.exists():
            return StepResult(state_patch={"specs": []}, next="done")
        try:
            data = json.loads(path.read_text())
        except (json.JSONDecodeError, OSError):
            data = []
        if not isinstance(data, list):
            data = []
        return StepResult(state_patch={"specs": list(data)}, next="done")


@dataclass(frozen=True)
class _SectionDraftStep:
    """Per-section ``base_prompt`` template — specialised per spec via
    :func:`dataclasses.replace`. The spec keys (``section_id`` /
    ``section_title``) are dataclass field names so they survive the
    intersection check in ``_specialize_step``."""

    name: str = "section_draft"
    kind: str = "produce"
    prompt_key: str | None = "execute_doc"
    slot: str | None = None
    section_id: str = ""
    section_title: str = ""

    def run(self, ctx: StepContext) -> StepResult:
        sid = self.section_id or "section"
        out = Path(ctx.plan_dir) / "section_drafts" / f"{sid}.md"
        out.parent.mkdir(parents=True, exist_ok=True)
        if not out.exists():
            out.write_text(f"# {self.section_title or sid}\n")
        return StepResult(outputs={sid: out}, next="done")


def _concat_sections_join(
    results: list[StepResult], ctx: StepContext
) -> StepResult:
    """Concatenate per-section outputs under their section_id keys and
    advance to the ``critique`` stage."""

    del ctx
    merged: dict[str, Path] = {}
    for r in results:
        if isinstance(r.outputs, Mapping):
            for k, v in r.outputs.items():
                merged[k] = Path(v)
    return StepResult(outputs=merged, next="critique")


@dataclass(frozen=True)
class _CritiqueStep:
    name: str = "critique"
    kind: str = "produce"
    prompt_key: str | None = "critique_doc"
    slot: str | None = None

    def run(self, ctx: StepContext) -> StepResult:
        out = Path(ctx.plan_dir) / "critique" / "v1.md"
        out.parent.mkdir(parents=True, exist_ok=True)
        if not out.exists():
            out.write_text("")
        return StepResult(outputs={"critique": out}, next="revise")


@dataclass(frozen=True)
class _ReviseStep:
    name: str = "revise"
    kind: str = "produce"
    prompt_key: str | None = "revise_doc"
    slot: str | None = None

    def run(self, ctx: StepContext) -> StepResult:
        out = Path(ctx.plan_dir) / "revise" / "v1.md"
        out.parent.mkdir(parents=True, exist_ok=True)
        if not out.exists():
            out.write_text("")
        return StepResult(outputs={"revise": out}, next="assembly")


@dataclass(frozen=True)
class _AssemblyStep:
    """Terminal stage: returns ``next='halt'`` directly.

    Per ``executor.py:218-220`` the executor returns before normal edge
    dispatch when ``result.next == 'halt'`` — a ``halt``-labelled edge
    on the enclosing Stage is unreachable. The assembly Stage carries
    no outgoing edges; termination comes from this Step's ``next``.
    """

    name: str = "assembly"
    kind: str = "produce"
    prompt_key: str | None = "assemble_doc"
    slot: str | None = None

    def run(self, ctx: StepContext) -> StepResult:
        out = Path(ctx.plan_dir) / "assembly" / "final.md"
        out.parent.mkdir(parents=True, exist_ok=True)
        if not out.exists():
            out.write_text("")
        return StepResult(outputs={"final": out}, next="halt")


# ── Pipeline assembly ──────────────────────────────────────────────────


def build_pipeline() -> Pipeline:
    """Return the canonical ``doc`` :class:`Pipeline`.

    Stage order (insertion-order preserved via plain ``dict``):

    1. ``outline`` — emits ``sections`` JSON artifact.
    2. ``section_drafts`` — :func:`dynamic_fanout` SubloopStep wrapping
       the outline reader + per-section base_prompt.
    3. ``critique`` — direct Step (no gate loop).
    4. ``revise`` — direct Step (no gate loop).
    5. ``assembly`` — terminal Step (returns ``next='halt'``).
    """

    fanout = dynamic_fanout(
        generator=_OutlineArtifactReader(artifact_label="sections"),
        base_prompt=_SectionDraftStep(),
        join=_concat_sections_join,
        name="section_drafts",
    )

    stages: dict[str, Stage] = {
        "outline": Stage(
            name="outline",
            step=_OutlineStep(),
            edges=(Edge(label="section_drafts", target="section_drafts"),),
        ),
        "section_drafts": Stage(
            name="section_drafts",
            step=fanout,
            edges=(Edge(label="critique", target="critique"),),
        ),
        "critique": Stage(
            name="critique",
            step=_CritiqueStep(),
            edges=(Edge(label="revise", target="revise"),),
        ),
        "revise": Stage(
            name="revise",
            step=_ReviseStep(),
            edges=(Edge(label="assembly", target="assembly"),),
        ),
        "assembly": Stage(
            name="assembly",
            step=_AssemblyStep(),
            edges=(),
        ),
    }

    return Pipeline(stages=stages, entry="outline")


__all__ = [
    "build_pipeline",
    "description",
    "default_profile",
    "supported_modes",
    "recommended_profiles",
]
