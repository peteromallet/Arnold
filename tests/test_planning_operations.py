from __future__ import annotations

from pathlib import Path
from typing import Any

from arnold.runtime.operations import OperationKind, OperationRequest
from arnold.pipelines.megaplan.control_interface import ControlTransitionRequest, RunStateView
from arnold.pipelines.megaplan.planning.operations import profile_validate_operation, resume_phase_args
from arnold.pipelines.megaplan.pipelines.planning import operation_registry, override_catalog


def test_planning_operation_registry_supports_all_six_operation_kinds() -> None:
    registry = operation_registry()

    assert registry.supported_operations() == frozenset(
        {
            OperationKind.RUN_PHASE,
            OperationKind.STATUS_PROJECTION,
            OperationKind.RESUME,
            OperationKind.OVERRIDE_LIST,
            OperationKind.OVERRIDE_APPLY,
            OperationKind.PROFILE_VALIDATE,
        }
    )


def test_resume_phase_args_preserves_execute_resume_flags() -> None:
    assert resume_phase_args({"phase": "execute", "batch_index": 3}, "plan-1") == [
        "execute",
        "--plan",
        "plan-1",
        "--confirm-destructive",
        "--user-approved",
        "--batch",
        "3",
    ]
    assert resume_phase_args({"phase": "review"}, "plan-1") == [
        "review",
        "--plan",
        "plan-1",
    ]


def test_run_phase_dispatch_returns_exit_code_stdout_and_stderr(monkeypatch) -> None:
    registry = operation_registry()

    def fake_run_phase(phase, *, plan, cwd=None, plan_dir=None, argv=None, progress_env=None):  # noqa: ANN001
        assert phase == "plan"
        assert plan == "demo-plan"
        assert cwd == Path("/tmp/root")
        assert plan_dir == Path("/tmp/plan")
        assert argv == ["--flag"]
        assert progress_env == {"MODE": "test"}
        return 0, "phase stdout", "phase stderr"

    monkeypatch.setattr(
        "arnold.pipelines.megaplan.planning.operations._pipeline",
        lambda: type("P", (), {"run_phase": staticmethod(fake_run_phase)})(),
    )

    result = registry.dispatch(
        OperationRequest(
            kind=OperationKind.RUN_PHASE,
            payload={
                "phase": "plan",
                "plan": "demo-plan",
                "cwd": "/tmp/root",
                "plan_dir": "/tmp/plan",
                "argv": ["--flag"],
                "progress_env": {"MODE": "test"},
            },
        )
    )

    assert result.ok is True
    assert result.payload == {
        "exit_code": 0,
        "stdout": "phase stdout",
        "stderr": "phase stderr",
    }
    assert set(result.payload) == {"exit_code", "stdout", "stderr"}


def test_run_phase_dispatch_ignores_unknown_carrier_keys(monkeypatch) -> None:
    registry = operation_registry()
    captured: dict[str, Any] = {}

    def fake_run_phase(phase, *, plan, cwd=None, plan_dir=None, argv=None, progress_env=None):  # noqa: ANN001
        captured["phase"] = phase
        captured["plan"] = plan
        captured["cwd"] = cwd
        captured["plan_dir"] = plan_dir
        captured["argv"] = argv
        captured["progress_env"] = progress_env
        return 0, "", ""

    monkeypatch.setattr(
        "arnold.pipelines.megaplan.planning.operations._pipeline",
        lambda: type("P", (), {"run_phase": staticmethod(fake_run_phase)})(),
    )

    result = registry.dispatch(
        OperationRequest(
            kind=OperationKind.RUN_PHASE,
            payload={
                "phase": "review",
                "plan": "demo-plan",
                "cwd": "/tmp/root",
                "plan_dir": "/tmp/plan",
                "argv": ["--flag"],
                "progress_env": {"MODE": "test"},
                "runtime_envelope": {"opaque": True},
                "unknown_sentinel": "still-opaque",
            },
        )
    )

    assert result.ok is True
    assert captured == {
        "phase": "review",
        "plan": "demo-plan",
        "cwd": Path("/tmp/root"),
        "plan_dir": Path("/tmp/plan"),
        "argv": ["--flag"],
        "progress_env": {"MODE": "test"},
    }


def test_status_projection_dispatch_uses_planning_binding() -> None:
    registry = operation_registry()
    state = {
        "name": "p1",
        "current_state": "critiqued",
        "config": {"project_dir": "/tmp/project"},
    }

    result = registry.dispatch(
        OperationRequest(
            kind=OperationKind.STATUS_PROJECTION,
            payload={"state": state, "mode": "valid_targets"},
        )
    )

    assert result.ok is True
    assert isinstance(result.payload["state_view"], RunStateView)
    assert tuple(target.id for target in result.payload["valid_targets"]) == (
        "gate",
        "step",
    )


def test_override_list_returns_plugin_owned_catalog() -> None:
    registry = operation_registry()

    result = registry.dispatch(
        OperationRequest(kind=OperationKind.OVERRIDE_LIST, payload={})
    )

    assert result.ok is True
    assert result.payload["catalog"] == override_catalog()
    assert "force-proceed" in result.payload["catalog"]
    assert "set-profile" in result.payload["catalog"]


def test_override_apply_routes_through_planning_control_binding() -> None:
    registry = operation_registry()
    state = {
        "name": "p1",
        "current_state": "gated",
        "config": {"project_dir": "/tmp/project"},
        "meta": {},
        "last_gate": {},
        "plan_versions": [{"file": "plan.md"}],
    }

    result = registry.dispatch(
        OperationRequest(
            kind=OperationKind.OVERRIDE_APPLY,
            payload={
                "state": state,
                "request": ControlTransitionRequest(
                    action="replan",
                    reason="operator reroute",
                ),
            },
        )
    )

    assert result.ok is True
    assert result.payload["accepted"] is True
    assert result.payload["mutated"] is True
    assert result.payload["reason"] == "replan"


def test_override_apply_builds_transition_request_from_flat_payload(monkeypatch) -> None:
    registry = operation_registry()
    state = {
        "name": "p1",
        "current_state": "gated",
        "config": {"project_dir": "/tmp/project"},
        "meta": {},
        "last_gate": {},
        "plan_versions": [{"file": "plan.md"}],
    }
    captured: dict[str, Any] = {}

    class _FakeResult:
        accepted = True
        mutated = True
        reason = "replan"
        artifacts = {}
        state_deltas = ()
        events = ()

    class _FakeBinding:
        def apply_transition(self, run_state, transition):  # noqa: ANN001
            captured["run_state"] = run_state
            captured["transition"] = transition
            return _FakeResult()

    monkeypatch.setattr(
        "arnold.pipelines.megaplan.planning.operations.planning_control_binding",
        lambda: _FakeBinding(),
    )

    result = registry.dispatch(
        OperationRequest(
            kind=OperationKind.OVERRIDE_APPLY,
            payload={
                "state": state,
                "action": "set-model",
                "target_id": "execute",
                "params": {"model": "gpt-5.5", "phase": "execute"},
                "actor": "operator",
                "source": "cli",
                "reason": "reroute",
                "note": "carry forward",
                "metadata": {"robustness": "full"},
                "expected_versions": {"resume_cursor": 3},
                "idempotency_key": "abc123",
                "unknown_sentinel": {"opaque": True},
            },
        )
    )

    assert result.ok is True
    transition = captured["transition"]
    assert isinstance(transition, ControlTransitionRequest)
    assert transition.action == "set-model"
    assert transition.target_id == "execute"
    assert transition.params == {"model": "gpt-5.5", "phase": "execute"}
    assert transition.actor == "operator"
    assert transition.source == "cli"
    assert transition.reason == "reroute"
    assert transition.note == "carry forward"
    assert transition.metadata == {"robustness": "full"}
    assert transition.expected_versions == {"resume_cursor": 3}
    assert transition.idempotency_key == "abc123"


def test_profile_validate_reuses_existing_preflight_inputs(monkeypatch) -> None:
    registry = operation_registry()
    captured: dict[str, object] = {}

    def fake_preflight(profile, *, pipeline_name="", profile_name=""):  # noqa: ANN001
        captured["profile"] = dict(profile)
        captured["pipeline_name"] = pipeline_name
        captured["profile_name"] = profile_name

    monkeypatch.setattr(
        "arnold.pipelines.megaplan.planning.validation.preflight_or_raise",
        fake_preflight,
    )

    result = registry.dispatch(
        OperationRequest(
            kind=OperationKind.PROFILE_VALIDATE,
            payload={
                "profile": {"plan": "claude:gpt-5"},
                "pipeline_name": "megaplan",
                "profile_name": "default",
            },
        )
    )

    assert result.ok is True
    assert result.payload == {"validated": True}
    assert captured == {
        "profile": {"plan": "claude:gpt-5"},
        "pipeline_name": "megaplan",
        "profile_name": "default",
    }


def test_profile_validate_operation_calls_observed_megaplan_preflight(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_preflight(profile, *, pipeline_name="", profile_name=""):  # noqa: ANN001
        captured["profile"] = dict(profile)
        captured["pipeline_name"] = pipeline_name
        captured["profile_name"] = profile_name

    monkeypatch.setattr(
        "arnold.pipelines.megaplan._pipeline.preflight.preflight_or_raise",
        fake_preflight,
    )

    result = profile_validate_operation(
        {
            "profile": {"plan": "claude:gpt-5"},
            "pipeline_name": "megaplan",
            "profile_name": "default",
        }
    )

    assert result.ok is True
    assert captured == {
        "profile": {"plan": "claude:gpt-5"},
        "pipeline_name": "megaplan",
        "profile_name": "default",
    }


def test_resume_dispatch_uses_plugin_owned_argument_translation() -> None:
    registry = operation_registry()
    captured: dict[str, object] = {}

    def fake_runner(phase, *, plan, cwd=None, plan_dir=None, argv=None):  # noqa: ANN001
        captured["phase"] = phase
        captured["plan"] = plan
        captured["cwd"] = cwd
        captured["plan_dir"] = plan_dir
        captured["argv"] = list(argv or [])
        return 0, "resume ok", ""

    result = registry.dispatch(
        OperationRequest(
            kind=OperationKind.RESUME,
            payload={
                "cursor": {"phase": "execute", "batch_index": 2},
                "plan": "demo-plan",
                "root": "/tmp/root",
                "plan_dir": "/tmp/plan",
                "runner": fake_runner,
            },
        )
    )

    assert result.ok is True
    assert captured == {
        "phase": "execute",
        "plan": "demo-plan",
        "cwd": Path("/tmp/root"),
        "plan_dir": Path("/tmp/plan"),
        "argv": [
            "execute",
            "--plan",
            "demo-plan",
            "--confirm-destructive",
            "--user-approved",
            "--batch",
            "2",
        ],
    }
    assert result.payload["args"] == captured["argv"]
    assert set(result.payload) == {"args", "exit_code", "stdout", "stderr"}
