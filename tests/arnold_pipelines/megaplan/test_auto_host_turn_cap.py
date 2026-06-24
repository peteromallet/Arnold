from __future__ import annotations

import importlib
import json
from pathlib import Path

import pytest

from arnold_pipelines.megaplan.orchestration.phase_result import atomic_write_phase_result


@pytest.mark.parametrize(
    "module_name",
    [
        "arnold.pipelines.megaplan.auto",
        "arnold_pipelines.megaplan.auto",
    ],
)
def test_host_turn_cap_cli_payload_becomes_retryable_external_error(module_name: str) -> None:
    auto = importlib.import_module(module_name)
    payload = {
        "success": False,
        "error": "rate_limit",
        "message": "Host premium-turn cap exhausted (3/3 slots active).",
        "details": {
            "source": "host_turn_cap",
            "retryable": True,
            "cap": 3,
        },
    }

    extracted = auto._extract_cli_error_payload(json.dumps(payload, indent=2), "")
    external_error = auto._external_error_from_cli_payload(extracted)

    assert external_error is not None
    assert external_error.provider == "host_turn_cap"
    assert external_error.error_kind == "rate_limit"
    assert external_error.source == "host_turn_cap"
    assert auto._is_retryable_external_error("plan", external_error) is True
    assert auto._is_host_turn_cap_external_error(external_error) is True


def test_non_host_rate_limit_cli_payload_is_not_auto_retryable() -> None:
    auto = importlib.import_module("arnold_pipelines.megaplan.auto")
    payload = {
        "success": False,
        "error": "rate_limit",
        "message": "Provider quota exhausted.",
        "details": {"source": "provider"},
    }

    extracted = auto._extract_cli_error_payload(json.dumps(payload), "")

    assert auto._external_error_from_cli_payload(extracted) is None


def test_drive_retries_host_turn_cap_when_stale_result_exists(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    auto = importlib.import_module("arnold_pipelines.megaplan.auto")
    plan = "host-cap-plan"
    plan_dir = tmp_path / ".megaplan" / "plans" / plan
    plan_dir.mkdir(parents=True)
    atomic_write_phase_result(
        plan_dir,
        auto.PhaseResult(
            phase="plan",
            invocation_id="previous",
            exit_kind=auto.ExitKind.external_error.value,
            external_error=auto.ExternalError(
                provider="host_turn_cap",
                error_kind="rate_limit",
                source="host_turn_cap",
            ),
        ),
    )
    (plan_dir / "state.json").write_text(
        json.dumps({"meta": {"current_invocation_id": "previous"}}),
        encoding="utf-8",
    )

    status_calls = iter(
        [
            {
                "state": "prepped",
                "next_step": "plan",
                "valid_next": ["plan"],
                "active_step": None,
            },
            {
                "state": auto.STATE_DONE,
                "next_step": None,
                "valid_next": [],
                "active_step": None,
            },
        ]
    )
    phase_calls: list[list[str]] = []
    host_cap_payload = {
        "success": False,
        "error": "rate_limit",
        "message": "Host premium-turn cap exhausted (3/3 slots active).",
        "details": {
            "source": "host_turn_cap",
            "retryable": True,
            "cap": 3,
        },
    }

    def fake_status(*_args: object, **_kwargs: object) -> dict[str, object]:
        return next(status_calls)

    def fake_run_planning_phase(cmd: list[str], **_kwargs: object) -> tuple[int, str, str]:
        phase_calls.append(cmd)
        if len(phase_calls) == 1:
            return 1, json.dumps(host_cap_payload, indent=2), ""
        return 0, "", ""

    log: list[str] = []
    monkeypatch.setattr(auto, "_status", fake_status)
    monkeypatch.setattr(auto, "_run_planning_phase", fake_run_planning_phase)
    monkeypatch.setattr(auto.time, "sleep", lambda _seconds: None)
    monkeypatch.setattr(auto, "_execute_completion_authority", lambda _plan_dir: (True, []))
    monkeypatch.setattr(auto, "_shadow_completion_verdict", lambda *_args, **_kwargs: None)

    outcome = auto.drive(
        plan,
        cwd=tmp_path,
        poll_sleep=0,
        max_iterations=3,
        writer=log.append,
    )

    assert outcome.status == "done"
    assert len(phase_calls) == 2
    assert any("waiting for host premium-turn capacity" in line for line in log)
    assert not any("internal_error" in line for line in log)
