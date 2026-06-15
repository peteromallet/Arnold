from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from arnold.pipeline.executor import run_pipeline
from arnold.pipeline.types import (
    ContractResult,
    ContractStatus,
    Edge,
    Pipeline,
    Stage,
    StepContext,
    StepResult,
    Suspension,
)
from arnold.pipelines.evidence_pack import EvidencePackHooks, build_initial_pipeline
from arnold.pipelines.evidence_pack.verifier import make_evidence_pack_payload
from arnold.runtime.envelope import RuntimeEnvelope
from arnold.runtime.event_journal import read_event_journal


class _PatchStep:
    name = "patch"
    kind = "compute"

    def run(self, ctx: StepContext) -> StepResult:
        return StepResult(
            outputs={"from_output": "yes"},
            state_patch={"from_patch": "yes"},
            next="halt",
        )


class _SuspendStep:
    name = "suspend"
    kind = "compute"

    def run(self, ctx: StepContext) -> StepResult:
        return StepResult(
            next="halt",
            contract_result=ContractResult(
                status=ContractStatus.SUSPENDED,
                suspension=Suspension(
                    kind="human",
                    awaitable="approval/1",
                    resume_cursor="cursor-1",
                ),
            ),
        )


def _single(step: Any) -> Pipeline:
    return Pipeline(stages={"s": Stage(name="s", step=step)}, entry="s")


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def test_hooks_persist_events_and_state(tmp_path: Path) -> None:
    hooks = EvidencePackHooks(tmp_path)

    run_pipeline(
        _single(_PatchStep()),
        {"seed": True},
        RuntimeEnvelope(plugin_id="evidence", run_id="r-1", artifact_root=str(tmp_path)),
        hooks=hooks,
    )

    events = read_event_journal(tmp_path)
    assert [event["kind"] for event in events] == [
        "phase_start",
        "phase_end",
        "state_written",
    ]
    assert events[0]["payload"] == {"stage": "s"}
    assert events[1]["payload"] == {"next": "halt", "stage": "s"}
    state = _read_json(tmp_path / "state.json")
    assert state["seed"] is True
    assert state["from_output"] == "yes"
    assert state["from_patch"] == "yes"


def test_hooks_persist_resume_cursor_on_suspension(tmp_path: Path) -> None:
    hooks = EvidencePackHooks(tmp_path)

    run_pipeline(
        _single(_SuspendStep()),
        {},
        RuntimeEnvelope(plugin_id="evidence", run_id="r-1", artifact_root=str(tmp_path)),
        hooks=hooks,
    )

    cursor = _read_json(tmp_path / "resume_cursor.json")
    assert cursor == {"stage": "s", "resume_cursor": "cursor-1"}


def test_real_evidence_pack_pipeline_writes_hook_artifacts(tmp_path: Path) -> None:
    pack_path = tmp_path / "input_pack.json"
    pack_path.write_text(
        json.dumps(
            make_evidence_pack_payload(
                evidence_pack_id="pack-hooks",
                source_ticket="ticket-1",
                checkpoints=[
                    {
                        "checkpoint_id": "pack-hooks.structural_audit",
                        "status": "passed",
                        "artifact_refs": [],
                    }
                ],
            )
        ),
        encoding="utf-8",
    )

    run_pipeline(
        build_initial_pipeline(),
        {"evidence_pack_path": str(pack_path)},
        RuntimeEnvelope(
            plugin_id="evidence_pack_verifier",
            run_id="r-hooks",
            artifact_root=str(tmp_path),
        ),
        hooks=EvidencePackHooks(tmp_path),
    )

    assert (tmp_path / "events.ndjson").exists()
    assert (tmp_path / "state.json").exists()
    assert _read_json(tmp_path / "resume_cursor.json") == {
        "stage": "human_review",
        "resume_cursor": "pack-hooks.human_review_gate",
    }
    kinds = [event["kind"] for event in read_event_journal(tmp_path)]
    assert "phase_start" in kinds
    assert "phase_end" in kinds
    assert "state_written" in kinds
