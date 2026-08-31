"""Tests for megaplan adapter: CompletionSubject, SubjectInventory, S2FShadowRunner.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from arnold.workflow.completion.spec import SubjectKind
from arnold.workflow.completion.source_declaration import SourceDeclaration
from arnold.workflow.completion.shadow import S2FTemplatesUnavailable
from arnold_pipelines.megaplan.completion.adapter import (
    MEGAPLAN_KIND_MAPPING,
    CompletionSubject,
    SubjectInventory,
    S2FShadowRunner,
    megaplan_subject_inventory,
    shadow_runner,
)


# ---------------------------------------------------------------------------
# MEGAPLAN_KIND_MAPPING — each kind coverage
# ---------------------------------------------------------------------------


class TestMegaplanKindMapping:
    """MEGAPLAN_KIND_MAPPING covers all expected artifact types."""

    def test_plan_maps_to_workflow(self) -> None:
        assert MEGAPLAN_KIND_MAPPING["plan"] == SubjectKind.WORKFLOW

    def test_milestone_maps_to_workflow(self) -> None:
        assert MEGAPLAN_KIND_MAPPING["milestone"] == SubjectKind.WORKFLOW

    def test_phase_maps_to_step(self) -> None:
        assert MEGAPLAN_KIND_MAPPING["phase"] == SubjectKind.STEP

    def test_step_maps_to_step(self) -> None:
        assert MEGAPLAN_KIND_MAPPING["step"] == SubjectKind.STEP

    def test_stage_maps_to_step(self) -> None:
        assert MEGAPLAN_KIND_MAPPING["stage"] == SubjectKind.STEP

    def test_task_maps_to_dynamic_task(self) -> None:
        assert MEGAPLAN_KIND_MAPPING["task"] == SubjectKind.DYNAMIC_TASK

    def test_effect_maps_to_effect(self) -> None:
        assert MEGAPLAN_KIND_MAPPING["effect"] == SubjectKind.EFFECT

    def test_review_maps_to_human_boundary(self) -> None:
        assert MEGAPLAN_KIND_MAPPING["review"] == SubjectKind.HUMAN_BOUNDARY

    def test_every_subject_kind_is_mapped(self) -> None:
        """Every non-PURE SubjectKind has at least one mapping."""
        mapped_kinds = set(MEGAPLAN_KIND_MAPPING.values())
        for kind in SubjectKind:
            assert kind in mapped_kinds, f"{kind.value} has no mapping"


# ---------------------------------------------------------------------------
# CompletionSubject — construction and kind derivation
# ---------------------------------------------------------------------------


class TestCompletionSubject:
    """CompletionSubject dataclass contract."""

    def test_kind_auto_derived(self) -> None:
        subj = CompletionSubject(
            artifact_type="plan",
            identifier="plan-001",
            name="My Plan",
        )
        assert subj.kind == SubjectKind.WORKFLOW

    def test_explicit_kind(self) -> None:
        subj = CompletionSubject(
            artifact_type="plan",
            identifier="plan-001",
            kind=SubjectKind.WORKFLOW,
        )
        assert subj.kind == SubjectKind.WORKFLOW

    def test_unknown_artifact_type_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="Unsupported"):
            CompletionSubject(artifact_type="unknown_type", identifier="unknown-001")

    def test_empty_artifact_type_raises(self) -> None:
        with pytest.raises(ValueError, match="artifact_type"):
            CompletionSubject(artifact_type="", identifier="test")

    def test_empty_identifier_raises(self) -> None:
        with pytest.raises(ValueError, match="identifier"):
            CompletionSubject(artifact_type="step", identifier="")

    def test_to_source_declaration(self) -> None:
        subj = CompletionSubject(
            artifact_type="step",
            identifier="step-001",
            name="My Step",
        )
        src = subj.to_source_declaration()
        assert isinstance(src, SourceDeclaration)
        assert src.kind == SubjectKind.STEP
        assert src.canonical_name == "My Step"
        assert "megaplan:step:step-001" in src.source_id

    def test_to_subject_declaration(self) -> None:
        subj = CompletionSubject(
            artifact_type="plan",
            identifier="plan-001",
            name="Test Plan",
        )
        sd = subj.to_subject_declaration()
        assert sd.subject_kind == SubjectKind.WORKFLOW
        assert sd.source.canonical_name == "Test Plan"
        assert sd.subject_instance_id.startswith("megaplan:")
        assert sd.declaration_id.startswith("megaplan:")

    def test_to_subject_declaration_with_explicit_ids(self) -> None:
        subj = CompletionSubject(
            artifact_type="step",
            identifier="step-001",
        )
        sd = subj.to_subject_declaration(
            declaration_id="explicit-decl",
            subject_instance_id="explicit-inst",
        )
        assert sd.declaration_id == "explicit-decl"
        assert sd.subject_instance_id == "explicit-inst"

    def test_frozen(self) -> None:
        subj = CompletionSubject(
            artifact_type="step",
            identifier="step-001",
        )
        with pytest.raises(AttributeError):
            subj.identifier = "new-id"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# SubjectInventory
# ---------------------------------------------------------------------------


class TestSubjectInventory:
    """SubjectInventory dataclass contract."""

    def test_empty(self) -> None:
        inv = SubjectInventory()
        assert len(inv) == 0

    def test_with_subjects(self) -> None:
        subj = CompletionSubject(
            artifact_type="plan", identifier="p1",
        )
        inv = SubjectInventory(subjects=(subj,))
        assert len(inv) == 1

    def test_to_declarations(self) -> None:
        subj = CompletionSubject(
            artifact_type="step", identifier="s1", name="Step1",
        )
        inv = SubjectInventory(subjects=(subj,))
        decls = inv.to_declarations()
        assert len(decls) == 1
        assert decls[0].subject_kind == SubjectKind.STEP
        assert decls[0].source.canonical_name == "Step1"


# ---------------------------------------------------------------------------
# megaplan_subject_inventory
# ---------------------------------------------------------------------------


class TestMegaplanSubjectInventory:
    """megaplan_subject_inventory creates SubjectInventory from artifact dicts."""

    def test_single_artifact(self) -> None:
        artifacts = (
            {"artifact_type": "plan", "identifier": "p1", "name": "Plan1"},
        )
        declarations = megaplan_subject_inventory(artifacts)
        assert len(declarations) == 1
        assert declarations[0].subject_kind == SubjectKind.WORKFLOW

    def test_multiple_artifacts(self) -> None:
        artifacts = (
            {"artifact_type": "plan", "identifier": "p1"},
            {"artifact_type": "step", "identifier": "s1"},
            {"artifact_type": "review", "identifier": "r1"},
        )
        inv = megaplan_subject_inventory(artifacts)
        assert len(inv) == 3

    def test_skips_artifacts_with_missing_fields(self) -> None:
        artifacts = (
            {"artifact_type": "plan", "identifier": "p1"},
            {"artifact_type": "", "identifier": "bad"},
            {"identifier": "no-type"},
            {},
        )
        inv = megaplan_subject_inventory(artifacts)
        assert len(inv) == 1

    def test_all_artifact_types(self) -> None:
        artifacts = tuple(
            {"artifact_type": at, "identifier": f"{at}-001"}
            for at in MEGAPLAN_KIND_MAPPING
        )
        inv = megaplan_subject_inventory(artifacts)
        assert len(inv) == len(MEGAPLAN_KIND_MAPPING)


# ---------------------------------------------------------------------------
# S2FShadowRunner — shadow runner integration
# ---------------------------------------------------------------------------


class TestS2FShadowRunner:
    """S2FShadowRunner wraps shadow evaluation."""

    def test_create_runner(self) -> None:
        runner = S2FShadowRunner()
        assert any(".megaplan/plans" in p for p in runner.scan_dirs)
        assert any("GO-FORMAT" in p for p in runner.schema_markers)

    def test_runner_no_files(self) -> None:
        runner = S2FShadowRunner(
            scan_dirs=("/nonexistent",),
        )
        with pytest.raises(S2FTemplatesUnavailable):
            runner.run_shadow()

    def test_runner_with_inventory(self) -> None:
        subj = CompletionSubject(
            artifact_type="step",
            identifier="runner-step",
            name="RunnerStep",
        )
        inv = SubjectInventory(subjects=(subj,))
        runner = S2FShadowRunner()
        result = runner.run_shadow_with_inventory(inv)
        assert len(result.specs) == 1
        assert len(result.verdicts) == 1
        assert result.specs[0].subject_kind == SubjectKind.STEP

    def test_discovery_gap_report_nonexistent(self) -> None:
        runner = S2FShadowRunner(
            scan_dirs=("/nonexistent",),
        )
        report = runner.discovery_gap_report()
        assert len(report.discovered_files) == 0
        assert report.has_gaps is True

    def test_runner_with_s2f_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpl = {
                "schema_version": "arnold.workflow.s2f_template.v1",
                "declarations": [
                    {
                        "kind": "workflow",
                        "canonical_name": "s2f_wf",
                        "source_id": "s2f-wf-001",
                    },
                ],
            }
            tmpl_path = Path(tmpdir) / "s2f_template.json"
            tmpl_path.write_text(json.dumps(tmpl))
            runner = S2FShadowRunner(
                scan_dirs=(tmpdir,),
                schema_markers=("arnold.workflow.s2f_template.v1",),
            )
            result = runner.run_shadow()
            assert len(result.specs) == 1
            assert result.specs[0].subject_kind == SubjectKind.WORKFLOW


# ---------------------------------------------------------------------------
# shadow_runner factory
# ---------------------------------------------------------------------------


class TestShadowRunnerFactory:
    """shadow_runner convenience factory."""

    def test_default(self) -> None:
        runner = shadow_runner()
        assert isinstance(runner, S2FShadowRunner)

    def test_with_scan_dirs(self) -> None:
        runner = shadow_runner(scan_dirs=("/custom",))
        assert runner.scan_dirs == ("/custom",)
