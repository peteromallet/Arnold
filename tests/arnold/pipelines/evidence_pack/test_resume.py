"""Resume tests for the native-first evidence-pack pipeline."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from arnold.pipeline import RESUME_REVERIFY_EXTENSION_KEY, Suspension, persist_resume_cursor
from arnold.pipeline.native.runtime import run_native_pipeline
from arnold.pipelines.evidence_pack.pipeline import build_pipeline
from arnold.pipelines.evidence_pack import resume as resume_module
from arnold.pipelines.evidence_pack.resume import (
    EvidencePackResumeError,
    resume_evidence_pack,
)
from arnold.pipelines.evidence_pack.verifier import make_evidence_pack_payload
from arnold.runtime.envelope import RuntimeEnvelope


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, sort_keys=True, indent=2), encoding="utf-8")


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _failing_evidence_pack(evidence_pack_id: str = "pack-001") -> dict[str, Any]:
    return make_evidence_pack_payload(
        evidence_pack_id=evidence_pack_id,
        source_ticket="",
        checkpoints=[
            {
                "checkpoint_id": f"{evidence_pack_id}.structural_audit",
                "status": "passed",
                "artifact_refs": [],
            },
        ],
    )


def _run_fail_to_suspension(tmp_path: Path, pack_id: str = "pack-001") -> RuntimeEnvelope:
    pack_path = tmp_path / "input_pack.json"
    _write_json(pack_path, _failing_evidence_pack(pack_id))
    envelope = RuntimeEnvelope(
        plugin_id="evidence_pack_verifier",
        run_id="r-1",
        artifact_root=str(tmp_path),
    )
    result = run_native_pipeline(
        build_pipeline().native_program,
        artifact_root=tmp_path,
        initial_state={"evidence_pack_path": str(pack_path)},
        initial_envelope=envelope,
    )
    assert result.suspended is True
    return envelope


def test_resume_evidence_pack_approval_runs_native_resume(tmp_path: Path) -> None:
    envelope = _run_fail_to_suspension(tmp_path, "pack-resume")
    assert (tmp_path / "evidence_pack.json").exists()
    assert (tmp_path / "verdict.json").exists()
    assert (tmp_path / "resume_cursor.json").exists()
    assert (tmp_path / "awaiting_user.json").exists()
    checkpoint = _read_json(tmp_path / "checkpoint_pack-resume.human_review_gate.json")
    assert checkpoint["status"] == "suspended"

    result = resume_evidence_pack(
        tmp_path,
        envelope=envelope,
        human_input={"approved": True, "comment": "approved"},
    )

    assert result.resumed is True
    assert result.envelope is not None
    assert result.envelope.run_id == envelope.run_id
    assert "human_review" in str(result.cursor.get("stage", ""))
    assert not (tmp_path / "resume_cursor.json").exists()
    assert not (tmp_path / "awaiting_user.json").exists()
    verdict = _read_json(tmp_path / "verdict.json")
    attestation = _read_json(tmp_path / "attestation.json")
    assert verdict["verdict"] == "FAIL"
    assert attestation["evidence_pack_id"] == "pack-resume"
    assert attestation["verdict"] == "FAIL"


def test_resume_evidence_pack_rejection_clears_cursor_without_attestation(
    tmp_path: Path,
) -> None:
    _run_fail_to_suspension(tmp_path, "pack-reject")

    result = resume_evidence_pack(
        tmp_path,
        human_input={"approved": False, "comment": "needs revision"},
    )

    assert result.resumed is True
    assert not (tmp_path / "resume_cursor.json").exists()
    assert not (tmp_path / "awaiting_user.json").exists()
    assert not (tmp_path / "attestation.json").exists()
    verdict = _read_json(tmp_path / "verdict.json")
    checkpoint = _read_json(tmp_path / "checkpoint_pack-reject.human_review_gate.json")
    assert verdict["verdict"] == "FAIL"
    assert checkpoint["status"] == "suspended"


def test_resume_evidence_pack_rejects_unknown_native_cursor_stage(tmp_path: Path) -> None:
    _run_fail_to_suspension(tmp_path)
    cursor_path = tmp_path / "resume_cursor.json"
    cursor = _read_json(cursor_path)
    cursor["stage"] = "evidence_pack__reduce__pc7"
    cursor["artifact_stage"] = "reduce"
    _write_json(cursor_path, cursor)

    with pytest.raises(EvidencePackResumeError, match="human_review"):
        resume_evidence_pack(tmp_path, human_input={"approved": True})


def test_resume_evidence_pack_rejects_graph_cursor_without_native_payload(
    tmp_path: Path,
) -> None:
    _run_fail_to_suspension(tmp_path)
    persist_resume_cursor(tmp_path, stage="human_review", resume_cursor="legacy")

    with pytest.raises(EvidencePackResumeError, match="graph-born"):
        resume_evidence_pack(tmp_path, human_input={"approved": True})


def test_resume_evidence_pack_rejects_non_mapping_supplied_cursor(
    tmp_path: Path,
) -> None:
    _run_fail_to_suspension(tmp_path)

    with pytest.raises(EvidencePackResumeError, match="native cursor mapping"):
        resume_evidence_pack(
            tmp_path,
            human_input={"approved": True},
            resume_cursor="human_review",  # type: ignore[arg-type]
        )


def test_resume_evidence_pack_rejects_mismatched_supplied_cursor(
    tmp_path: Path,
) -> None:
    _run_fail_to_suspension(tmp_path)
    supplied = _read_json(tmp_path / "resume_cursor.json")
    supplied["stage"] = "evidence_pack__reduce__pc7"

    with pytest.raises(EvidencePackResumeError, match="does not match"):
        resume_evidence_pack(
            tmp_path,
            human_input={"approved": True},
            resume_cursor=supplied,
        )


def test_resume_evidence_pack_corrupt_cursor_fails_closed(tmp_path: Path) -> None:
    _run_fail_to_suspension(tmp_path)
    (tmp_path / "resume_cursor.json").write_text("{", encoding="utf-8")

    with pytest.raises(EvidencePackResumeError, match="could not be decoded"):
        resume_evidence_pack(tmp_path, human_input={"approved": True})


def test_resume_evidence_pack_missing_cursor_fails_closed(tmp_path: Path) -> None:
    with pytest.raises(EvidencePackResumeError, match="missing native resume cursor"):
        resume_evidence_pack(tmp_path, human_input={"approved": True})


def test_resume_evidence_pack_rejects_non_mapping_human_input(tmp_path: Path) -> None:
    _run_fail_to_suspension(tmp_path)

    with pytest.raises(EvidencePackResumeError, match="human_input must be a mapping"):
        resume_evidence_pack(
            tmp_path,
            human_input=["approved"],  # type: ignore[arg-type]
        )


def test_resume_human_input_overrides_extra_state(tmp_path: Path) -> None:
    envelope = _run_fail_to_suspension(tmp_path, "pack-extra-state")

    result = resume_evidence_pack(
        tmp_path,
        envelope=envelope,
        human_input={"approved": True, "comment": "approved"},
        extra_state={"human_input": {"choice": "failed", "comment": "stale"}},
    )

    assert result.resumed is True
    assert (tmp_path / "attestation.json").exists()


def test_resume_extra_state_merges_into_native_initial_state(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    envelope = _run_fail_to_suspension(tmp_path, "pack-extra-state-merge")
    captured: dict[str, Any] = {}

    def fake_run_native_pipeline(*args: Any, **kwargs: Any) -> Any:
        captured["initial_state"] = kwargs["initial_state"]
        captured["human_input"] = kwargs["human_input"]
        captured["resume"] = kwargs["resume"]
        return SimpleNamespace(envelope=envelope, suspended=False)

    monkeypatch.setattr(resume_module, "run_native_pipeline", fake_run_native_pipeline)

    result = resume_evidence_pack(
        tmp_path,
        envelope=envelope,
        human_input={"approved": True, "comment": "fresh"},
        extra_state={
            "operator": "reviewer-1",
            "human_input": {"choice": "failed", "comment": "stale"},
        },
    )

    assert result.resumed is True
    assert captured["resume"] is True
    assert captured["human_input"] == {
        "approved": True,
        "comment": "fresh",
        "choice": "emit",
    }
    assert captured["initial_state"] == {
        "operator": "reviewer-1",
        "human_input": {
            "approved": True,
            "comment": "fresh",
            "choice": "emit",
        },
    }


def test_resume_reverify_invalid_resuspends_without_native_resume(tmp_path: Path) -> None:
    _run_fail_to_suspension(tmp_path, "pack-invalid")
    suspension = Suspension(
        kind="human",
        awaitable="approval/pack-invalid",
        resume_input_schema={
            RESUME_REVERIFY_EXTENSION_KEY: {
                "artifact_path": "missing.json",
                "invalid_policy": "resuspend",
            }
        },
        resume_cursor="pack-invalid.human_review_gate",
    )

    result = resume_evidence_pack(
        tmp_path,
        human_input={"approved": True},
        suspension=suspension,
    )

    assert result.resumed is False
    assert result.reverify is not None
    assert result.reverify.outcome == "invalid"
    assert not (tmp_path / "attestation.json").exists()
