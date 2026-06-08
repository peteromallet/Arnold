from __future__ import annotations

import argparse
import json
from pathlib import Path

import pytest

from arnold.pipelines.megaplan.handlers import verifiability as verifiability_module
from arnold.pipelines.megaplan.handlers.verifiability import get_human_verification_status, handle_verify_human
from arnold.pipelines.megaplan.run_outcome import RunOutcome
from arnold.pipelines.megaplan.types import CliError
from arnold.pipelines.megaplan.planning.state import (
    STATE_AWAITING_HUMAN,
    STATE_AWAITING_HUMAN_VERIFY,
    STATE_DONE,
    STATE_INITIALIZED,
)


# ---------------------------------------------------------------------------
# Existing get_human_verification_status tests (unchanged)
# ---------------------------------------------------------------------------


def test_get_human_verification_status_latest_verdict_controls_pending(tmp_path: Path) -> None:
    plan_meta = {
        "success_criteria": [
            {"criterion": "browser proof", "priority": "must", "requires": ["drive_browser"]},
            {"criterion": "logs attached", "priority": "should", "requires": ["drive_browser"]},
        ]
    }
    (tmp_path / "human_verifications.json").write_text(
        json.dumps(
            [
                {"criterion_idx": 0, "timestamp": "2026-05-25T10:00:00Z", "verdict": "pass"},
                {"criterion_idx": 0, "timestamp": "2026-05-25T11:00:00Z", "verdict": "fail"},
                {"criterion_idx": 1, "timestamp": "2026-05-25T12:00:00Z", "verdict": "pass"},
            ]
        ),
        encoding="utf-8",
    )

    status = get_human_verification_status(
        tmp_path,
        plan_meta,
        worker_caps={"codex": {"run_tests"}},
    )

    assert status["verified"] == 1
    assert status["pending"] == 1
    assert status["all_deferred_must_verified"] is False
    assert status["rows"][0]["latest_verdict"] == "fail"
    assert status["rows"][0]["verified"] is False
    assert status["rows"][1]["latest_verdict"] == "pass"
    assert status["rows"][1]["verified"] is True


def test_get_human_verification_status_same_timestamp_uses_last_file_entry(tmp_path: Path) -> None:
    plan_meta = {
        "success_criteria": [
            {"criterion": "browser proof", "priority": "must", "requires": ["drive_browser"]},
        ]
    }
    verifications_path = tmp_path / "human_verifications.json"
    verifications_path.write_text(
        json.dumps(
            [
                {"criterion_idx": 0, "timestamp": "2026-05-25T10:00:00Z", "verdict": "fail"},
                {"criterion_idx": 0, "timestamp": "2026-05-25T10:00:00Z", "verdict": "pass"},
            ]
        ),
        encoding="utf-8",
    )

    status = get_human_verification_status(
        tmp_path,
        plan_meta,
        worker_caps={"codex": {"run_tests"}},
    )

    assert status["pending"] == 0
    assert status["verified"] == 1
    assert status["all_deferred_must_verified"] is True
    assert status["rows"][0]["latest_verdict"] == "pass"
    assert status["rows"][0]["latest_timestamp"] == "2026-05-25T10:00:00Z"


def test_verify_human_list_uses_worker_capabilities_for_pending_count(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    plan_meta = {
        "success_criteria": [
            {
                "criterion": "unit tests pass",
                "priority": "must",
                "requires": ["run_tests"],
            },
            {
                "criterion": "browser inspected",
                "priority": "must",
                "requires": ["drive_browser"],
            },
        ]
    }
    meta_path = tmp_path / "plan-v1.meta.json"
    meta_path.write_text(json.dumps(plan_meta), encoding="utf-8")
    (tmp_path / "human_verifications.json").write_text(
        json.dumps(
            [
                {
                    "criterion_idx": 1,
                    "timestamp": "2026-05-25T10:00:00Z",
                    "verdict": "pass",
                }
            ]
        ),
        encoding="utf-8",
    )
    state = _make_plan_state(current_state=STATE_DONE)

    monkeypatch.setattr(
        verifiability_module,
        "load_plan",
        lambda _root, _plan: (tmp_path, state),
    )
    monkeypatch.setattr(
        verifiability_module,
        "latest_plan_meta_path",
        lambda _plan_dir, _state: meta_path,
    )

    result = verifiability_module.handle_verify_human(
        tmp_path,
        argparse.Namespace(plan="test-plan", list_flag=True, json_flag=True),
    )

    assert result["pending"] == 0
    assert result["all_deferred_must_verified"] is True
    assert result["rows"][0]["deferred_must"] is False
    assert result["rows"][1]["deferred_must"] is True


# ---------------------------------------------------------------------------
# F6 verify-human characterization: handle_verify_human behaviour
# ---------------------------------------------------------------------------


def _make_plan_state(
    *,
    current_state: str = STATE_AWAITING_HUMAN_VERIFY,
    name: str = "test-plan",
) -> dict:
    """Minimal plan state dict suitable for ``handle_verify_human``."""
    return {
        "name": name,
        "idea": "test idea",
        "current_state": current_state,
        "iteration": 1,
        "created_at": "2026-01-01T00:00:00Z",
        "config": {
            "project_dir": "/tmp/project",
            "workers": {
                "codex": {"verifies": ["run_tests", "read_files"]},
            },
        },
        "sessions": {},
        "plan_versions": [{"file": "plan-v1.md", "version": 1}],
        "history": [],
        "meta": {},
    }


def _make_plan_meta(success_criteria: list[dict] | None = None) -> dict:
    """Minimal plan meta suitable for ``handle_verify_human``."""
    if success_criteria is None:
        success_criteria = [
            {
                "criterion": "All tests pass",
                "priority": "must",
                "requires": ["run_tests"],
            },
        ]
    return {"success_criteria": success_criteria}


def _verdict_args(
    criterion: str = "0",
    pass_flag: bool = True,
    evidence: str = "manual check",
) -> argparse.Namespace:
    """Build an argparse.Namespace for verdict-recording mode."""
    return argparse.Namespace(
        plan="test-plan",
        list_flag=False,
        json_flag=False,
        criterion=criterion,
        pass_flag=pass_flag,
        fail_flag=not pass_flag,
        evidence=evidence,
    )


# ── state gate ─────────────────────────────────────────────────────────


def test_handle_verify_human_requires_awaiting_human_verify_state(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``verify-human`` in verdict mode must reject non-awaiting states."""
    state = _make_plan_state(current_state=STATE_INITIALIZED)
    monkeypatch.setattr(
        "arnold.pipelines.megaplan.handlers.verifiability.load_plan",
        lambda root, name: (tmp_path, state),
    )

    with pytest.raises(CliError) as exc_info:
        handle_verify_human(tmp_path, _verdict_args())

    assert exc_info.value.code == "wrong_state"
    assert "awaiting_human_verify" in exc_info.value.message
    assert state["current_state"] == STATE_INITIALIZED  # unchanged


def test_handle_verify_human_accepts_awaiting_human_verify_state(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``verify-human`` in verdict mode accepts STATE_AWAITING_HUMAN_VERIFY."""
    state = _make_plan_state(current_state=STATE_AWAITING_HUMAN_VERIFY)
    meta = _make_plan_meta()

    # Write plan meta so read_json succeeds
    meta_path = tmp_path / "plan-v1.meta.json"
    meta_path.write_text(json.dumps(meta), encoding="utf-8")

    monkeypatch.setattr(
        "arnold.pipelines.megaplan.handlers.verifiability.load_plan",
        lambda root, name: (tmp_path, state),
    )
    monkeypatch.setattr(
        "arnold.pipelines.megaplan.handlers.verifiability.now_utc",
        lambda: "2026-05-31T12:00:00Z",
    )
    # Capture state transition
    monkeypatch.setattr(
        "arnold.pipelines.megaplan.handlers.verifiability.save_state_merge_meta",
        lambda plan_dir, st: st.update({"current_state": STATE_DONE}),
    )

    result = handle_verify_human(tmp_path, _verdict_args())

    assert result["success"] is True
    assert result["step"] == "verify-human"
    assert result["state"] == STATE_DONE
    assert result["verdict"] == "pass"


# ── state transition ───────────────────────────────────────────────────


def test_handle_verify_human_transitions_to_done_when_all_verified(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """When all deferred-must criteria are verified the plan moves to DONE."""
    state = _make_plan_state(current_state=STATE_AWAITING_HUMAN_VERIFY)
    meta = _make_plan_meta(
        success_criteria=[
            {
                "criterion": "Tests pass",
                "priority": "must",
                "requires": ["run_tests"],
            },
        ]
    )

    meta_path = tmp_path / "plan-v1.meta.json"
    meta_path.write_text(json.dumps(meta), encoding="utf-8")

    monkeypatch.setattr(
        "arnold.pipelines.megaplan.handlers.verifiability.load_plan",
        lambda root, name: (tmp_path, state),
    )
    monkeypatch.setattr(
        "arnold.pipelines.megaplan.handlers.verifiability.now_utc",
        lambda: "2026-05-31T12:00:00Z",
    )
    monkeypatch.setattr(
        "arnold.pipelines.megaplan.handlers.verifiability.save_state_merge_meta",
        lambda plan_dir, st: st.update({"current_state": STATE_DONE}),
    )

    result = handle_verify_human(tmp_path, _verdict_args())

    assert result["success"] is True
    assert result["state"] == STATE_DONE
    assert "transitioned to done" in result["summary"].lower()


def test_handle_verify_human_stays_awaiting_when_pending_remain(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """State stays awaiting_human_verify when not all must-criteria pass."""
    state = _make_plan_state(current_state=STATE_AWAITING_HUMAN_VERIFY)
    meta = _make_plan_meta(
        success_criteria=[
            {
                "criterion": "Tests pass",
                "priority": "must",
                "requires": ["run_tests"],
            },
            {
                "criterion": "UI check",
                "priority": "must",
                "requires": ["drive_browser"],
            },
        ]
    )

    meta_path = tmp_path / "plan-v1.meta.json"
    meta_path.write_text(json.dumps(meta), encoding="utf-8")

    monkeypatch.setattr(
        "arnold.pipelines.megaplan.handlers.verifiability.load_plan",
        lambda root, name: (tmp_path, state),
    )
    monkeypatch.setattr(
        "arnold.pipelines.megaplan.handlers.verifiability.now_utc",
        lambda: "2026-05-31T12:00:00Z",
    )
    monkeypatch.setattr(
        "arnold.pipelines.megaplan.handlers.verifiability.save_state_merge_meta",
        lambda plan_dir, st: None,  # should NOT be called
    )

    result = handle_verify_human(tmp_path, _verdict_args())

    assert result["success"] is True
    assert result["state"] == STATE_AWAITING_HUMAN_VERIFY  # still awaiting


# ── projection ─────────────────────────────────────────────────────────


def test_verify_human_pause_point_projects_to_run_outcome_awaiting_human() -> None:
    """STATE_AWAITING_HUMAN_VERIFY maps to RunOutcome.awaiting_human."""
    assert STATE_AWAITING_HUMAN_VERIFY == "awaiting_human_verify"
    assert STATE_AWAITING_HUMAN is STATE_AWAITING_HUMAN_VERIFY

    projection = {
        STATE_AWAITING_HUMAN_VERIFY: RunOutcome.AWAITING_HUMAN,
    }
    assert projection[STATE_AWAITING_HUMAN_VERIFY] == RunOutcome.AWAITING_HUMAN
    assert projection[STATE_AWAITING_HUMAN_VERIFY].value == "awaiting_human"


def test_handle_verify_human_result_state_projects_to_awaiting_human(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The handler result's ``state`` field is STATE_AWAITING_HUMAN_VERIFY
    (which equals ``awaiting_human_verify``) and projects to
    RunOutcome.awaiting_human."""
    state = _make_plan_state(current_state=STATE_AWAITING_HUMAN_VERIFY)
    meta = _make_plan_meta(
        success_criteria=[
            {
                "criterion": "Tests pass",
                "priority": "must",
                "requires": ["run_tests"],
            },
            {
                "criterion": "UI check",
                "priority": "must",
                "requires": ["drive_browser"],
            },
        ]
    )

    meta_path = tmp_path / "plan-v1.meta.json"
    meta_path.write_text(json.dumps(meta), encoding="utf-8")

    monkeypatch.setattr(
        "arnold.pipelines.megaplan.handlers.verifiability.load_plan",
        lambda root, name: (tmp_path, state),
    )
    monkeypatch.setattr(
        "arnold.pipelines.megaplan.handlers.verifiability.now_utc",
        lambda: "2026-05-31T12:00:00Z",
    )
    monkeypatch.setattr(
        "arnold.pipelines.megaplan.handlers.verifiability.save_state_merge_meta",
        lambda plan_dir, st: None,
    )

    result = handle_verify_human(tmp_path, _verdict_args())

    # The result state is still awaiting (not all verified)
    assert result["state"] == STATE_AWAITING_HUMAN_VERIFY

    # And that state conceptually projects to awaiting_human
    # (the planning state name "awaiting_human_verify" maps to the
    # domain-neutral RunOutcome.AWAITING_HUMAN whose value is "awaiting_human")
    projection = {STATE_AWAITING_HUMAN_VERIFY: RunOutcome.AWAITING_HUMAN}
    assert projection[result["state"]] == RunOutcome.AWAITING_HUMAN
    assert projection[result["state"]].value == "awaiting_human"


# ── preservation of human-pause artifacts ──────────────────────────────


def test_handle_verify_human_does_not_create_awaiting_user_json(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``handle_verify_human`` must never create ``awaiting_user.json``."""
    state = _make_plan_state(current_state=STATE_AWAITING_HUMAN_VERIFY)
    meta = _make_plan_meta()

    meta_path = tmp_path / "plan-v1.meta.json"
    meta_path.write_text(json.dumps(meta), encoding="utf-8")

    awaiting_path = tmp_path / "awaiting_user.json"
    assert not awaiting_path.exists(), "precondition: no awaiting_user.json"

    monkeypatch.setattr(
        "arnold.pipelines.megaplan.handlers.verifiability.load_plan",
        lambda root, name: (tmp_path, state),
    )
    monkeypatch.setattr(
        "arnold.pipelines.megaplan.handlers.verifiability.now_utc",
        lambda: "2026-05-31T12:00:00Z",
    )
    monkeypatch.setattr(
        "arnold.pipelines.megaplan.handlers.verifiability.save_state_merge_meta",
        lambda plan_dir, st: st.update({"current_state": STATE_DONE}),
    )

    handle_verify_human(tmp_path, _verdict_args())

    assert not awaiting_path.exists(), (
        "handle_verify_human must not create awaiting_user.json"
    )


def test_handle_verify_human_does_not_alter_existing_awaiting_user_json(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``handle_verify_human`` must not modify a pre-existing
    ``awaiting_user.json``."""
    state = _make_plan_state(current_state=STATE_AWAITING_HUMAN_VERIFY)
    meta = _make_plan_meta()

    meta_path = tmp_path / "plan-v1.meta.json"
    meta_path.write_text(json.dumps(meta), encoding="utf-8")

    # Pre-populate awaiting_user.json (simulating pipeline pause)
    awaiting_path = tmp_path / "awaiting_user.json"
    original_content = json.dumps({
        "pipeline": "default",
        "stage": "planning",
        "questions": [{"id": "q1", "text": "What now?"}],
    })
    awaiting_path.write_text(original_content, encoding="utf-8")

    monkeypatch.setattr(
        "arnold.pipelines.megaplan.handlers.verifiability.load_plan",
        lambda root, name: (tmp_path, state),
    )
    monkeypatch.setattr(
        "arnold.pipelines.megaplan.handlers.verifiability.now_utc",
        lambda: "2026-05-31T12:00:00Z",
    )
    monkeypatch.setattr(
        "arnold.pipelines.megaplan.handlers.verifiability.save_state_merge_meta",
        lambda plan_dir, st: st.update({"current_state": STATE_DONE}),
    )

    handle_verify_human(tmp_path, _verdict_args())

    # Content must be unchanged
    assert awaiting_path.read_text(encoding="utf-8") == original_content


def test_handle_verify_human_preserves_pipeline_paused_stage(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``handle_verify_human`` must not clear ``_pipeline_paused_stage``
    from plan state."""
    state = _make_plan_state(current_state=STATE_AWAITING_HUMAN_VERIFY)
    state["_pipeline_paused_stage"] = "human_gate"
    meta = _make_plan_meta()

    meta_path = tmp_path / "plan-v1.meta.json"
    meta_path.write_text(json.dumps(meta), encoding="utf-8")

    monkeypatch.setattr(
        "arnold.pipelines.megaplan.handlers.verifiability.load_plan",
        lambda root, name: (tmp_path, state),
    )
    monkeypatch.setattr(
        "arnold.pipelines.megaplan.handlers.verifiability.now_utc",
        lambda: "2026-05-31T12:00:00Z",
    )
    monkeypatch.setattr(
        "arnold.pipelines.megaplan.handlers.verifiability.save_state_merge_meta",
        lambda plan_dir, st: st.update({"current_state": STATE_DONE}),
    )

    handle_verify_human(tmp_path, _verdict_args())

    assert state.get("_pipeline_paused_stage") == "human_gate", (
        "handle_verify_human must not clear _pipeline_paused_stage"
    )


def test_handle_verify_human_does_not_create_pipeline_paused_stage(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``handle_verify_human`` must not inject ``_pipeline_paused_stage``
    when it was absent."""
    state = _make_plan_state(current_state=STATE_AWAITING_HUMAN_VERIFY)
    # Explicitly remove any potential default
    state.pop("_pipeline_paused_stage", None)
    assert "_pipeline_paused_stage" not in state

    meta = _make_plan_meta()
    meta_path = tmp_path / "plan-v1.meta.json"
    meta_path.write_text(json.dumps(meta), encoding="utf-8")

    monkeypatch.setattr(
        "arnold.pipelines.megaplan.handlers.verifiability.load_plan",
        lambda root, name: (tmp_path, state),
    )
    monkeypatch.setattr(
        "arnold.pipelines.megaplan.handlers.verifiability.now_utc",
        lambda: "2026-05-31T12:00:00Z",
    )
    monkeypatch.setattr(
        "arnold.pipelines.megaplan.handlers.verifiability.save_state_merge_meta",
        lambda plan_dir, st: st.update({"current_state": STATE_DONE}),
    )

    handle_verify_human(tmp_path, _verdict_args())

    assert "_pipeline_paused_stage" not in state, (
        "handle_verify_human must not inject _pipeline_paused_stage"
    )
