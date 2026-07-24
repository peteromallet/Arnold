from __future__ import annotations

from arnold.pipeline.declaration_lowering import lower_stage_declarations
from arnold.pipeline.types import Port, PortRef, ReadRef, Stage, StepContext, StepResult, WriteRef


class _Step:
    def run(self, ctx: StepContext) -> StepResult:  # pragma: no cover
        return StepResult()


def test_lowering_derives_effective_typed_ports_from_reads_and_writes() -> None:
    stage = Stage(
        name="author",
        step=_Step(),
        reads=(PortRef(port_name="brief", content_type="text/markdown"),),
        writes=(Port(name="draft", content_type="text/markdown"),),
    )

    lowered = lower_stage_declarations(stage)

    assert lowered.typed_reads == (
        PortRef(port_name="brief", content_type="text/markdown"),
    )
    assert lowered.typed_writes == (
        Port(name="draft", content_type="text/markdown"),
    )
    assert lowered.effective_consumes == lowered.typed_reads
    assert lowered.effective_produces == lowered.typed_writes
    assert lowered.clean_binding is True


def test_lowering_preserves_legacy_read_write_refs_as_untyped() -> None:
    stage = Stage(
        name="legacy",
        step=_Step(),
        reads=(ReadRef(name="brief.md"),),
        writes=(WriteRef(name="draft.md"),),
    )

    lowered = lower_stage_declarations(stage)

    assert lowered.legacy_reads == (ReadRef(name="brief.md"),)
    assert lowered.legacy_writes == (WriteRef(name="draft.md"),)
    assert lowered.typed_reads == ()
    assert lowered.typed_writes == ()
    assert lowered.effective_consumes == ()
    assert lowered.effective_produces == ()
    assert lowered.clean_binding is True


def test_lowering_accepts_matching_explicit_and_typed_declarations() -> None:
    stage = Stage(
        name="agreed",
        step=_Step(),
        reads=(PortRef(port_name="brief", content_type="text/markdown"),),
        writes=(Port(name="draft", content_type="text/markdown"),),
        consumes=(PortRef(port_name="brief", content_type="text/markdown"),),
        produces=(Port(name="draft", content_type="text/markdown"),),
    )

    lowered = lower_stage_declarations(stage)

    assert lowered.declared_consumes == lowered.effective_consumes
    assert lowered.declared_produces == lowered.effective_produces
    assert lowered.drift_defects == ()
    assert lowered.clean_binding is True


def test_lowering_reports_drift_when_explicit_and_typed_declarations_disagree() -> None:
    stage = Stage(
        name="drifted",
        step=_Step(),
        reads=(PortRef(port_name="brief", content_type="text/plain"),),
        writes=(Port(name="draft", content_type="text/plain"),),
        consumes=(PortRef(port_name="brief", content_type="text/markdown"),),
        produces=(Port(name="draft", content_type="text/markdown"),),
    )

    lowered = lower_stage_declarations(stage)

    assert {(defect.direction, defect.name) for defect in lowered.drift_defects} == {
        ("consumes", "brief"),
        ("produces", "draft"),
    }
    assert all(defect.code == "declaration_drift" for defect in lowered.drift_defects)
    assert lowered.clean_binding is False
