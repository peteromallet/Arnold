from __future__ import annotations

import argparse
from pathlib import Path
from types import SimpleNamespace

import pytest
from arnold.control.interface import ControlTransitionRequest

from arnold_pipelines.megaplan.control import (
    ControlTarget,
    approve_gate_control_handler,
    reject_gate_control_handler,
)
from arnold_pipelines.megaplan.handlers.override import (
    _normalize_override_response,
    _routed_override_response,
)
from arnold_pipelines.megaplan.planning.state import (
    STATE_ABORTED,
    STATE_DONE,
    STATE_GATED,
    STATE_PLANNED,
)


@pytest.mark.parametrize(
    ("action", "state", "artifacts"),
    [
        (
            "abort",
            {"config": {}, "current_state": STATE_ABORTED, "meta": {}},
            None,
        ),
        (
            "force-proceed",
            {
                "config": {},
                "current_state": STATE_GATED,
                "meta": {"overrides": [{"action": "force-proceed", "debt_entries_added": 2}]},
            },
            {"orchestrator_guidance": "Proceed natively.", "debt_entries_added": 3},
        ),
        (
            "replan",
            {"config": {}, "current_state": STATE_PLANNED, "iteration": 3, "meta": {}},
            {"plan_file": "plan_v3.md"},
        ),
    ],
)
def test_routed_override_responses_drop_next_step_authority(
    tmp_path: Path,
    action: str,
    state: dict[str, object],
    artifacts: dict[str, object] | None,
) -> None:
    response = _routed_override_response(
        action,
        plan_dir=tmp_path,
        state=state,
        args=argparse.Namespace(reason="operator override", note=None),
        artifacts=artifacts,
    )

    assert "next_step" not in response
    assert "next_step_runtime" not in response
    assert response["override_action"] == action
    assert "route_signal" in response


@pytest.mark.parametrize(
    "action",
    [
        "abort",
        "adopt-execution",
        "force-proceed",
        "recover-blocked",
        "replan",
        "resume-clarify",
    ],
)
def test_legacy_override_normalization_strips_next_step_for_routed_actions(action: str) -> None:
    response = _normalize_override_response(
        action,
        {
            "success": True,
            "step": "override",
            "next_step": "legacy-target",
            "next_step_runtime": {"timeout_seconds": 1},
        },
    )

    assert "next_step" not in response
    assert "next_step_runtime" not in response
    assert response["override_action"] == action
    assert "route_signal" in response


@pytest.mark.parametrize(
    ("handler", "intent", "payload", "expected_action"),
    [
        (approve_gate_control_handler, "approve_gate", {"reason": "ship it"}, "force-proceed"),
        (
            reject_gate_control_handler,
            "reject_gate",
            {"reason": "needs work", "note": "revise this"},
            "add-note",
        ),
    ],
)
def test_gate_control_handlers_drop_next_step_authority(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    handler,
    intent: str,
    payload: dict[str, str],
    expected_action: str,
) -> None:
    import arnold_pipelines.megaplan.control as control_module

    captured: dict[str, object] = {}

    monkeypatch.setattr(
        control_module,
        "_gate_resolved",
        lambda *args, **kwargs: SimpleNamespace(id="progress-1"),
    )

    def fake_apply_gate_control_request(*args, **kwargs):
        captured["action"] = kwargs["action"]
        return {
            "summary": "ok",
            "next_step": "legacy-target",
            "next_step_runtime": {"timeout_seconds": 1},
            "route_signal": "force_proceed" if kwargs["action"] == "force-proceed" else "add_note",
        }

    monkeypatch.setattr(control_module, "_apply_gate_control_request", fake_apply_gate_control_request)

    target = ControlTarget(
        intent=intent,
        target_id="gate-1",
        project_root=tmp_path,
        plan="demo",
        plan_dir=tmp_path / ".megaplan" / "plans" / "demo",
        gate_id="gate-1",
        payload=payload,
    )

    result = handler(target, SimpleNamespace(id="message-1"), store=SimpleNamespace())

    gate_response = result["gate"]
    assert captured["action"] == expected_action
    assert gate_response["summary"] == "ok"
    assert gate_response["route_signal"] in {"force_proceed", "add_note"}
    assert "next_step" not in gate_response
    assert "next_step_runtime" not in gate_response
    assert result["progress_event_id"] == "progress-1"


@pytest.mark.parametrize(
    ("intent", "action", "payload"),
    [
        ("approve_gate", "force-proceed", {"reason": "ship it", "user_approved": True}),
        ("reject_gate", "add-note", {"reason": "needs work", "note": "revise this"}),
    ],
)
def test_gate_control_adapter_builds_transition_request(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    intent: str,
    action: str,
    payload: dict[str, object],
) -> None:
    import arnold_pipelines.megaplan.control as control_module

    plan_dir = tmp_path / ".megaplan" / "plans" / "demo"
    plan_dir.mkdir(parents=True)
    (plan_dir / "state.json").write_text('{"name":"demo","current_state":"gated","config":{},"meta":{}}')

    captured: dict[str, object] = {}

    def fake_apply_transition(run_state, transition, binding, *, plan_dir=None):
        captured["run_state"] = run_state
        captured["transition"] = transition
        captured["binding"] = binding
        captured["plan_dir"] = plan_dir
        return SimpleNamespace(
            accepted=True,
            mutated=True,
            reason=None,
            artifacts={},
            state_deltas=(),
            events=(),
        )

    monkeypatch.setattr(control_module, "apply_transition", fake_apply_transition)
    monkeypatch.setattr(
        "arnold_pipelines.megaplan.handlers.override._emit_routed_override_events",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(
        "arnold_pipelines.megaplan.handlers.override._routed_override_response",
        lambda *args, **kwargs: {
            "summary": "ok",
            "route_signal": "force_proceed" if action == "force-proceed" else "add_note",
            "next_step": "legacy-target",
            "next_step_runtime": {"timeout_seconds": 1},
        },
    )

    target = ControlTarget(
        intent=intent,
        target_id="gate-1",
        project_root=tmp_path,
        plan="demo",
        plan_dir=plan_dir,
        gate_id="gate-1",
        payload={k: v for k, v in payload.items() if isinstance(v, str)},
    )
    message = SimpleNamespace(id="message-1", actor_id="operator-1")

    result = control_module._apply_gate_control_request(
        target,
        message,
        action=action,
        payload={k: v for k, v in payload.items() if k == "user_approved"},
        reason=str(payload["reason"]),
        note=payload.get("note") if isinstance(payload.get("note"), str) else None,
        source="user" if action == "add-note" else "control_message",
    )

    transition = captured["transition"]
    assert isinstance(transition, ControlTransitionRequest)
    assert transition.action == action
    assert transition.target_id == action
    assert transition.actor == "operator-1"
    assert transition.reason == payload["reason"]
    assert transition.note == payload.get("note")
    assert transition.metadata["control_intent"] == intent
    assert transition.metadata["control_message_id"] == "message-1"
    assert result["route_signal"] in {"force_proceed", "add_note"}
    assert "next_step" not in result
    assert "next_step_runtime" not in result
