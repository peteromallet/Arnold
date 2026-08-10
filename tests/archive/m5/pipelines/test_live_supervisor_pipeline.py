"""Integration test for the live-supervisor pipeline."""

from __future__ import annotations

import json
from pathlib import Path

from arnold.pipeline import Pipeline
from arnold.pipeline.executor import run_pipeline
from arnold.pipeline.discovery.manifest import Manifest, read_manifest
from arnold.pipeline.native import NativeProgram
from arnold.pipelines.megaplan.pipelines.live_supervisor import build_pipeline
from arnold.pipelines.megaplan.pipelines.live_supervisor.model import (
    HealthCategory,
    Incident,
    PlanEntry,
    SignalBundle,
    Snapshot,
    Triage,
)
from arnold.runtime.envelope import RuntimeEnvelope


def _snapshot_with_false_stall() -> Snapshot:
    entry = PlanEntry(
        plan_id="p1",
        plan_name="my-plan",
        plan_dir="/tmp/my-plan",
        repo_path="/tmp/repo",
        state={"current_state": "planned"},
    )
    incident = Incident(
        plan_entry=entry,
        signals=SignalBundle(
            liveness="progressing",
            liveness_reason="llm in flight",
            block_details={},
            doctor_findings=(),
            has_in_flight_llm=True,
            last_event_age_seconds=350.0,
        ),
        triage=Triage.LIVE,
    )
    return Snapshot.now(plans=(entry,), incidents=(incident,))


def test_live_supervisor_manifest_is_static_and_discoverable():
    pipeline_init = (
        Path(__file__).resolve().parents[4]
        / "arnold"
        / "pipelines"
        / "megaplan"
        / "pipelines"
        / "live_supervisor"
        / "__init__.py"
    )

    result = read_manifest(pipeline_init)

    assert isinstance(result, Manifest)
    assert result.name == "live-supervisor"
    assert result.driver == ("native", "linear")
    assert result.entrypoint == "build_pipeline"


def test_pipeline_accepts_snapshot_and_produces_action_report(tmp_path):
    snapshot = _snapshot_with_false_stall()
    envelope = RuntimeEnvelope(artifact_root=str(tmp_path))
    pipeline = build_pipeline()

    assert isinstance(pipeline, Pipeline)
    assert isinstance(pipeline.native_program, NativeProgram)
    assert tuple(pipeline.resource_bundles) == ()
    result_envelope = run_pipeline(
        pipeline,
        initial_state={"snapshot": snapshot.to_dict()},
        envelope=envelope,
    )

    assert result_envelope is envelope

    classify = json.loads((tmp_path / "classify" / "classifications.json").read_text())
    diagnose = json.loads((tmp_path / "diagnose" / "diagnoses.json").read_text())
    repair = json.loads((tmp_path / "repair_decision" / "repair_decisions.json").read_text())
    recheck = json.loads((tmp_path / "recheck_emit" / "recheck_emit.json").read_text())

    assert classify[0]["health_category"] == HealthCategory.FALSE_STALL.value
    assert diagnose[0]["health_category"] == HealthCategory.FALSE_STALL.value
    assert "plan_id" in repair[0]
    assert "verdict" in repair[0]
    assert recheck["resumable"] is True
    assert recheck["decisions"] == repair
