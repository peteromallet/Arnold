"""T6 — end-to-end tests for the ``doc`` pipeline (0.23, sprint) — M3a Arnold migration.

Exercises the new first-class ``doc`` pipeline.  The direct-executor test
uses the Arnold executor; the cli_run test still exercises the Megaplan
bridge path.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import pytest


def _make_run_args(
    *,
    pipeline_name: str,
    plan_dir: Path,
    state: dict[str, Any] | None = None,
    inputs: str | None = None,
) -> argparse.Namespace:
    """Build the full Namespace shape ``cli_run`` / ``_run_pipeline`` expects."""

    return argparse.Namespace(
        list_pipelines=False,
        pipeline_name=pipeline_name,
        input_file=None,
        plan_dir=str(plan_dir),
        inputs=inputs,
        state=json.dumps(state) if state is not None else None,
        mode=None,
        profile=None,
        describe=False,
        resume_choice=None,
        vendor=None,
    )


# ── (a) Stage-keys assertion — iterate ``.keys()`` (mapping), not ``.name`` ─

def test_doc_pipeline_stage_keys_in_canonical_order() -> None:
    from arnold.pipelines.megaplan.pipelines.doc import build_pipeline

    pipeline = build_pipeline()
    # ``pipeline.stages`` is Mapping[str, Stage|ParallelStage] — iterate keys.
    assert tuple(pipeline.stages.keys()) == (
        "outline",
        "section_drafts",
        "critique",
        "revise",
        "assembly",
    )
    # Belt-and-braces: ``.values()`` carries Stage objects with ``.name``.
    assert tuple(s.name for s in pipeline.stages.values()) == (
        "outline",
        "section_drafts",
        "critique",
        "revise",
        "assembly",
    )


# ── (b) supported_modes + description surface through PipelineRegistry ───

def test_doc_pipeline_metadata_surfaces_through_registry() -> None:
    from arnold.pipelines.megaplan._pipeline.registry import (
        pipeline_metadata,
        registered_pipelines,
    )

    assert "doc" in registered_pipelines()
    meta = pipeline_metadata("doc")
    assert tuple(meta.get("supported_modes", ()) or ()) == ("native",)
    description = meta.get("description") or ""
    assert isinstance(description, str) and description.strip(), description
    # Sanity: description mentions the pipeline shape.
    assert "outline" in description.lower()


# ── (c) section_drafts is a dynamic_fanout-produced SubloopStep ──────────

def test_doc_pipeline_section_drafts_is_subloopstep() -> None:
    from arnold.pipelines.megaplan._pipeline.subloop import SubloopStep
    from arnold.pipelines.megaplan.pipelines.doc import build_pipeline

    pipeline = build_pipeline()
    section_drafts_stage = pipeline.stages["section_drafts"]
    # The Stage holds a Step on ``.step``; dynamic_fanout returns a
    # SubloopStep (per the executor.py:171,179,295,298 rationale).
    assert isinstance(section_drafts_stage.step, SubloopStep), (
        "section_drafts.step must be a SubloopStep produced by "
        "dynamic_fanout — got " f"{type(section_drafts_stage.step).__name__}"
    )


# ── (d) Mocked outline with 3 specs → 3 fanout invocations of base_prompt ─

def test_doc_pipeline_fanout_invokes_base_prompt_per_section(
    tmp_path: Path,
) -> None:
    """Pre-seeding outline/sections.json with 3 specs makes the
    ``dynamic_fanout`` SubloopStep fire its ``base_prompt`` (the
    ``SectionDraftStep``) exactly 3 times, producing 3 section files.

    Uses the Arnold executor (M3a migration).
    """

    from arnold.pipelines.megaplan.pipelines.doc import build_pipeline
    from arnold.pipelines.megaplan.pipelines.doc.steps import SectionDraftStep
    from arnold.pipeline import run_pipeline
    from arnold.runtime.envelope import RuntimeEnvelope

    plan_dir = tmp_path / "doc-run"
    plan_dir.mkdir(parents=True, exist_ok=True)
    # Pre-seed the outline artifact so OutlineStep.run() does NOT
    # overwrite it (it only writes [] when the file is absent).
    outline_path = plan_dir / "outline" / "sections.json"
    outline_path.parent.mkdir(parents=True, exist_ok=True)
    specs = [
        {"section_id": "intro", "section_title": "Intro"},
        {"section_id": "body", "section_title": "Body"},
        {"section_id": "conclusion", "section_title": "Conclusion"},
    ]
    outline_path.write_text(json.dumps(specs))

    # Count base_prompt invocations by spying on SectionDraftStep.run.
    call_section_ids: list[str] = []
    original_run = SectionDraftStep.run

    def spy_run(self: SectionDraftStep, ctx: Any) -> Any:  # noqa: ANN401
        call_section_ids.append(self.section_id)
        return original_run(self, ctx)

    pipeline = build_pipeline()
    # Patch on the class so all specialised clones (via dataclasses.replace)
    # share the spied run().
    SectionDraftStep.run = spy_run  # type: ignore[assignment]
    try:
        envelope = RuntimeEnvelope(artifact_root=str(plan_dir))
        run_pipeline(pipeline, initial_state={}, envelope=envelope)
    finally:
        SectionDraftStep.run = original_run  # type: ignore[assignment]

    assert call_section_ids == ["intro", "body", "conclusion"], (
        f"Expected 3 fanout invocations with intro/body/conclusion ids; "
        f"got {call_section_ids!r}"
    )
    # Per-section artifacts landed on disk under section_drafts/.
    for sid in ("intro", "body", "conclusion"):
        assert (plan_dir / "section_drafts" / f"{sid}.md").exists()


# ── cli_run integration: drive the pipeline through the megaplan run path ─

def test_doc_pipeline_runs_through_cli_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Drive the doc pipeline through ``cli_run`` (the same code path
    Step 19's real-model smoke uses) and verify the pipeline reaches
    the terminal ``assembly`` stage.

    This test exercises the Megaplan bridge path — the doc pipeline's
    steps are dual-compatible (support both Arnold artifact_root and
    Megaplan plan_dir), and the pipeline graph uses Megaplan types,
    so cli_run continues to work.
    """

    from arnold.pipelines.megaplan._pipeline import preflight as preflight_module
    from arnold.pipelines.megaplan._pipeline.run_cli import cli_run

    # Neutralise the credential preflight — the doc pipeline's stage
    # shells write placeholders directly and never invoke a worker, so
    # the resolved profile is irrelevant to the topology assertion this
    # test cares about. ``_run_pipeline`` re-imports preflight_or_raise
    # at call time so we patch the source module.
    monkeypatch.setattr(
        preflight_module, "preflight_or_raise", lambda *a, **kw: None
    )

    plan_dir = tmp_path / "doc-cli-run"
    plan_dir.mkdir(parents=True, exist_ok=True)
    # Pre-seed outline so the fanout has work to do.
    outline_path = plan_dir / "outline" / "sections.json"
    outline_path.parent.mkdir(parents=True, exist_ok=True)
    outline_path.write_text(
        json.dumps(
            [
                {"section_id": "intro", "section_title": "Intro"},
                {"section_id": "body", "section_title": "Body"},
                {"section_id": "conclusion", "section_title": "End"},
            ]
        )
    )

    args = _make_run_args(pipeline_name="doc", plan_dir=plan_dir)
    rc = cli_run(args)
    assert rc == 0, f"cli_run('doc') returned non-zero exit code {rc}"

    # All three fanout outputs landed.
    for sid in ("intro", "body", "conclusion"):
        assert (plan_dir / "section_drafts" / f"{sid}.md").exists()
    # Terminal assembly artifact exists.
    assert (plan_dir / "assembly" / "final.md").exists()
