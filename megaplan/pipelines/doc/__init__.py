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

Per-stage prompt files are registered under
``megaplan/pipelines/doc/prompts/``. The public Step shells in
``megaplan.pipelines.doc.steps`` carry the canonical ``prompt_key`` slots
(``outline_doc`` / ``execute_doc`` / ``critique_doc`` / ``revise_doc``
/ ``assemble_doc``).
"""

from __future__ import annotations

from megaplan._pipeline.patterns import dynamic_fanout
from megaplan._pipeline.types import (
    Edge,
    Pipeline,
    Stage,
)
from megaplan.pipelines.doc.steps import (
    AssemblyStep,
    CritiqueStep,
    OutlineArtifactReader,
    OutlineStep,
    ReviseStep,
    SectionDraftStep,
    concat_sections_join,
)

# Import the prompts sub-package for its register_pipeline_prompt side-effects.
from megaplan.pipelines.doc import prompts as _prompts  # noqa: F401


# ── Module-level metadata surfaced via PipelineRegistry ────────────────

description: str = (
    "Linear doc pipeline: outline → per-section drafts (dynamic fanout) "
    "→ critique → revise → assembly. Single-pass; no gate."
)
default_profile: str | None = None
supported_modes: tuple[str, ...] = ()
recommended_profiles: tuple[str, ...] = ()


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
        generator=OutlineArtifactReader(artifact_label="sections"),
        base_prompt=SectionDraftStep(),
        join=concat_sections_join,
        name="section_drafts",
    )

    stages: dict[str, Stage] = {
        "outline": Stage(
            name="outline",
            step=OutlineStep(),
            edges=(Edge(label="section_drafts", target="section_drafts"),),
        ),
        "section_drafts": Stage(
            name="section_drafts",
            step=fanout,
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

    return Pipeline(stages=stages, entry="outline")


__all__ = [
    "build_pipeline",
    "description",
    "default_profile",
    "supported_modes",
    "recommended_profiles",
]
