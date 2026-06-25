"""Native coverage for the split ``live-supervisor`` pipeline."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from arnold.pipeline import Pipeline, run_pipeline
from arnold.pipeline.native.ir import NativeProgram
from arnold.pipelines.megaplan.pipelines import live_supervisor as live_supervisor_mod
from arnold.pipelines.megaplan.pipelines.live_supervisor import build_pipeline
from arnold.pipelines.megaplan.pipelines.live_supervisor.model import (
    CheckFinding,
    HealthCategory,
    Incident,
    PlanEntry,
    SignalBundle,
    Snapshot,
    Triage,
)
from arnold.pipelines.megaplan.pipelines.live_supervisor.repair_agent import (
    HermesRepairAgent,
)
from arnold.runtime.envelope import RuntimeEnvelope


EXPECTED_STAGE_SEQUENCE = (
    "classify",
    "diagnose",
    "repair_decision",
    "recheck_emit",
)


def _incident(
    plan_id: str,
    *,
    state: dict[str, Any] | None = None,
    liveness: str = "stalled",
    triage: Triage = Triage.LIVE,
    block_details: dict[str, Any] | None = None,
    doctor_findings: tuple[CheckFinding, ...] = (),
    has_in_flight_llm: bool = False,
    last_event_age_seconds: float | None = None,
) -> Incident:
    entry = PlanEntry(
        plan_id=plan_id,
        plan_name=f"{plan_id}-plan",
        plan_dir=f"/tmp/{plan_id}-plan",
        repo_path="/tmp/repo",
        state=state or {"current_state": "planned"},
    )
    return Incident(
        plan_entry=entry,
        signals=SignalBundle(
            liveness=liveness,
            liveness_reason="test fixture",
            block_details=block_details or {},
            doctor_findings=doctor_findings,
            has_in_flight_llm=has_in_flight_llm,
            last_event_age_seconds=last_event_age_seconds,
        ),
        triage=triage,
    )


def _snapshot(*incidents: Incident) -> Snapshot:
    return Snapshot(
        scan_ts_utc="2026-06-20T00:00:00+00:00",
        plans=tuple(incident.plan_entry for incident in incidents),
        incidents=incidents,
    )


def _run_supervisor(
    tmp_path: Path,
    snapshot: Snapshot,
    *,
    repair_agent: Any | None = None,
) -> RuntimeEnvelope:
    envelope = RuntimeEnvelope(artifact_root=str(tmp_path))
    run_pipeline(
        build_pipeline(repair_agent=repair_agent, recheck_after_seconds=1.0),
        initial_state={"snapshot": snapshot.to_dict()},
        envelope=envelope,
    )
    return envelope


def _read_json(root: Path, stage: str, filename: str) -> Any:
    return json.loads((root / stage / filename).read_text(encoding="utf-8"))


class TestLiveSupervisorNative:
    def test_split_public_surface_and_native_program(self) -> None:
        import arnold.pipelines.megaplan.pipelines.live_supervisor as canonical
        import arnold.pipelines.megaplan.pipelines.live_supervisor.pipeline as canonical_pipeline
        import arnold.pipelines.megaplan.pipelines.live_supervisor.pipelines as compatibility
        import arnold_pipelines.megaplan.pipelines.live_supervisor as mirror
        import arnold_pipelines.megaplan.pipelines.live_supervisor.pipeline as mirror_pipeline
        import arnold_pipelines.megaplan.pipelines.live_supervisor.pipelines as mirror_compatibility

        pipeline = build_pipeline()

        assert live_supervisor_mod.driver == ("native", "linear")
        assert canonical.build_pipeline is canonical_pipeline.build_pipeline
        assert mirror.build_pipeline is canonical.build_pipeline
        assert mirror_pipeline.build_pipeline is canonical_pipeline.build_pipeline
        assert compatibility.build_pipeline is canonical_pipeline.build_pipeline
        assert mirror_compatibility.build_pipeline is canonical_pipeline.build_pipeline
        assert compatibility.__all__ == []
        assert mirror_compatibility.__all__ == []
        assert "live_supervisor_native" not in canonical.__all__
        assert not hasattr(canonical, "live_supervisor_native")
        assert not hasattr(canonical, "_build_graph_pipeline")

        assert isinstance(pipeline, Pipeline)
        assert isinstance(pipeline.native_program, NativeProgram)
        assert pipeline.native_program.name == "live-supervisor"
        assert tuple(pipeline.resource_bundles) == ()
        assert pipeline.entry == "classify"
        assert tuple(pipeline.stages) == EXPECTED_STAGE_SEQUENCE
        assert [phase.name for phase in pipeline.native_program.phases] == list(
            EXPECTED_STAGE_SEQUENCE
        )

    def test_native_execution_classifies_diagnoses_repairs_and_emits_artifacts(
        self,
        tmp_path: Path,
    ) -> None:
        false_stall = _incident(
            "false-stall",
            liveness="progressing",
            block_details={"recoverable_via": "resume"},
            has_in_flight_llm=True,
            last_event_age_seconds=450.0,
        )
        blocked_plan = _incident(
            "blocked",
            liveness="stalled",
            block_details={"is_blocked": True, "recoverable_via": "resume"},
        )
        harness_cleanup = _incident(
            "harness",
            state={"current_state": "completed"},
            doctor_findings=(
                CheckFinding(
                    scope="plan",
                    check="stale_lock",
                    status="warn",
                    message="stale lock remains",
                ),
            ),
        )

        _run_supervisor(
            tmp_path,
            _snapshot(false_stall, blocked_plan, harness_cleanup),
        )

        classifications = _read_json(tmp_path, "classify", "classifications.json")
        diagnoses = _read_json(tmp_path, "diagnose", "diagnoses.json")
        repairs = _read_json(
            tmp_path,
            "repair_decision",
            "repair_decisions.json",
        )
        recheck = _read_json(tmp_path, "recheck_emit", "recheck_emit.json")

        assert {item["plan_id"]: item["health_category"] for item in classifications} == {
            "false-stall": HealthCategory.FALSE_STALL.value,
            "blocked": HealthCategory.PLAN_ISSUE.value,
            "harness": HealthCategory.HARNESS_ISSUE.value,
        }
        assert {item["health_category"] for item in diagnoses} == {
            HealthCategory.FALSE_STALL.value,
            HealthCategory.PLAN_ISSUE.value,
            HealthCategory.HARNESS_ISSUE.value,
        }
        repair_by_plan = {item["plan_id"]: item for item in repairs}
        assert repair_by_plan["false-stall"]["recommended_command"] == "auto"
        assert repair_by_plan["false-stall"]["verdict"]["allowed"] is True
        assert repair_by_plan["blocked"]["recommended_command"] == "auto"
        assert repair_by_plan["blocked"]["verdict"]["allowed"] is True
        assert repair_by_plan["harness"]["recommended_command"].startswith("rm ")
        assert repair_by_plan["harness"]["verdict"]["allowed"] is True
        assert recheck["resumable"] is True
        assert recheck["decisions"] == repairs
        assert isinstance(recheck["recheck_after"], float)

    def test_native_repair_unavailable_falls_back_to_report_only(
        self,
        tmp_path: Path,
    ) -> None:
        incident = _incident(
            "blocked",
            liveness="stalled",
            block_details={"is_blocked": True, "recoverable_via": "resume"},
        )

        _run_supervisor(
            tmp_path,
            _snapshot(incident),
            repair_agent=HermesRepairAgent(None),
        )

        repairs = _read_json(
            tmp_path,
            "repair_decision",
            "repair_decisions.json",
        )

        assert repairs == [
            {
                "plan_id": "blocked",
                "health_category": HealthCategory.PLAN_ISSUE.value,
                "verdict": {
                    "allowed": False,
                    "reason": "no repair agent credentials or launcher available",
                },
            }
        ]
