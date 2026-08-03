from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

import pytest

from arnold_pipelines.megaplan import auto
from arnold_pipelines.megaplan.blocker_recovery import (
    compact_failure_identity,
    validated_deterministic_phase_repair,
)
from arnold_pipelines.megaplan.fallback_chains import classify_retryability
from arnold_pipelines.megaplan.handlers.override import (
    _external_error_requires_resume,
    _override_recover_blocked,
)
from arnold_pipelines.megaplan.observability.events import EventKind
from arnold_pipelines.megaplan.orchestration.phase_result import (
    ExitKind,
    ExternalError,
    PhaseResult,
    atomic_write_phase_result,
    phase_result_guard,
    read_phase_result,
)
from arnold_pipelines.megaplan.orchestration.recovery_policy import RecoveryPolicy
from arnold_pipelines.megaplan.types import CliError


FINGERPRINT = "a" * 64


def _contract_error() -> ExternalError:
    return ExternalError(
        provider="codex",
        error_kind="provider_contract",
        message="strict response schema rejected before model launch",
        status_code=400,
        error_layer="schema_error",
        deterministic=True,
        nonretryable=True,
        failure_fingerprint=FINGERPRINT,
    )


class _TypedProviderContractError(RuntimeError):
    error_kind = "provider_contract"
    error_layer = "schema_error"
    deterministic = True
    nonretryable = True
    failure_fingerprint = FINGERPRINT


def _write_state(plan_dir: Path, *, repaired: bool = False) -> None:
    state: dict[str, object] = {
        "name": "demo",
        "current_state": "gated",
    }
    if repaired:
        state["meta"] = {
            "provider_contract_repair_retry": {
                "status": "available",
                "failure_kind": "provider_contract_failure",
                "phase": "finalize",
                "repair_commit": "b" * 40,
            },
            "overrides": [
                {
                    "action": "recover-blocked",
                    "phase_contract_repair": {
                        "failure_kind": "provider_contract_failure",
                        "phase": "finalize",
                        "repair_commit": "b" * 40,
                    },
                }
            ]
        }
    (plan_dir / "state.json").write_text(json.dumps(state), encoding="utf-8")


def test_phase_guard_preserves_typed_provider_contract_failure(tmp_path: Path) -> None:
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    (plan_dir / "state.json").write_text(
        json.dumps(
            {
                "name": "demo",
                "current_state": "gated",
                "active_step": {"phase": "finalize", "agent": "codex"},
                "meta": {"current_invocation_id": "inv-provider-contract"},
            }
        ),
        encoding="utf-8",
    )
    error_payload = _contract_error().to_dict()

    with pytest.raises(CliError, match="response contract"):
        with phase_result_guard(plan_dir):
            raise CliError(
                "provider_contract",
                "response contract cannot be compiled",
                extra={"_external_error": error_payload},
            )

    result = read_phase_result(plan_dir)
    assert result is not None
    assert result.exit_kind == ExitKind.external_error.value
    assert result.external_error is not None
    assert result.external_error.to_dict() == error_payload


def test_attribute_typed_compiler_error_is_not_degraded_to_internal_error() -> None:
    error = ExternalError.from_exception(
        _TypedProviderContractError("response schema compiler invariant failed"),
        provider="codex",
    )

    assert error is not None
    assert error.to_dict() == {
        "provider": "codex",
        "error_kind": "provider_contract",
        "message": "response schema compiler invariant failed",
        "error_layer": "schema_error",
        "deterministic": True,
        "nonretryable": True,
        "failure_fingerprint": FINGERPRINT,
    }


def test_provider_contract_failure_is_permanent_for_all_fallback_policies() -> None:
    error = _contract_error()

    assert classify_retryability(error) == "permanent"
    decision = RecoveryPolicy(max_external_retries=99).classify(
        PhaseResult(
            phase="finalize",
            invocation_id="inv",
            exit_kind=ExitKind.external_error.value,
            external_error=error,
        ),
        layer="phase",
        phase="finalize",
    )
    assert decision.action == "halt"
    assert decision.halt_kind == "permanent_external"


@pytest.mark.parametrize(
    ("repaired", "expected_kind", "expected_strategy"),
    [
        (False, "provider_contract_failure", "repair_provider_contract"),
        (True, "provider_contract_repair_failed", "manual_review"),
    ],
)
def test_auto_calls_provider_once_and_routes_to_bounded_repair(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    repaired: bool,
    expected_kind: str,
    expected_strategy: str,
) -> None:
    plan_dir = tmp_path / "demo"
    plan_dir.mkdir()
    _write_state(plan_dir, repaired=repaired)
    calls = 0
    failures: list[dict[str, object]] = []

    monkeypatch.setattr(auto, "_resolve_plan_dir", lambda plan, cwd: plan_dir)
    monkeypatch.setattr(
        auto,
        "_status",
        lambda plan, **kwargs: {
            "state": "gated",
            "next_step": "finalize",
            "valid_next": ["finalize"],
            "progress": {},
        },
    )

    def fail_finalize(args, **kwargs):
        nonlocal calls
        calls += 1
        atomic_write_phase_result(
            plan_dir,
            PhaseResult(
                phase="finalize",
                invocation_id=f"inv-{calls}",
                exit_kind=ExitKind.external_error.value,
                external_error=_contract_error(),
            ),
        )
        return 1, "", "provider contract rejected"

    monkeypatch.setattr(auto, "_run_planning_phase", fail_finalize)
    monkeypatch.setattr(
        auto,
        "_record_lifecycle_failure",
        lambda **kwargs: failures.append(kwargs),
    )
    monkeypatch.setattr(auto, "emit_event", lambda *args, **kwargs: None)

    outcome = auto.drive(
        "demo",
        cwd=tmp_path,
        max_iterations=20,
        max_external_retries=20,
        poll_sleep=0,
    )

    assert outcome.status == "blocked"
    assert calls == 1
    assert failures[-1]["kind"] == expected_kind
    assert failures[-1]["resume_cursor"] == {
        "phase": "finalize",
        "retry_strategy": expected_strategy,
        "provider_failure_fingerprint": FINGERPRINT,
    }
    assert failures[-1]["metadata"]["failure_fingerprint"] == FINGERPRINT


def test_provider_failure_event_does_not_reset_stall_progress(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(
        auto,
        "read_events",
        lambda plan_dir: [
            {
                "seq": 7,
                "kind": EventKind.LLM_CALL_ERROR,
                "payload": {
                    "request_id": "req-1",
                    "error_kind": "provider_contract",
                },
            }
        ],
    )

    latest_seq, in_flight, latest_kind = auto._stall_event_progress_snapshot(tmp_path)

    assert latest_seq is None
    assert in_flight is False
    assert latest_kind is None


def test_recover_provider_contract_requires_commit_bound_receipt(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    plan_dir = tmp_path / ".megaplan" / "plans" / "demo"
    plan_dir.mkdir(parents=True)
    state = {
        "name": "demo",
        "current_state": "blocked",
        "meta": {},
        "resume_cursor": {
            "phase": "finalize",
            "retry_strategy": "repair_provider_contract",
            "provider_failure_fingerprint": FINGERPRINT,
        },
        "latest_failure": {
            "kind": "provider_contract_failure",
            "phase": "finalize",
            "message": "provider response contract rejected before launch",
            "metadata": {"failure_fingerprint": FINGERPRINT},
        },
    }
    failure_fingerprint = compact_failure_identity(state["latest_failure"])[
        "fingerprint"
    ]
    (plan_dir / "state.json").write_text(json.dumps(state), encoding="utf-8")
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(
        ["git", "config", "user.email", "test@example.invalid"],
        cwd=tmp_path,
        check=True,
    )
    subprocess.run(["git", "config", "user.name", "Test"], cwd=tmp_path, check=True)
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-qm", "provider contract repair"], cwd=tmp_path, check=True)
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    monkeypatch.setattr(
        "arnold_pipelines.megaplan.runtime.process.megaplan_engine_root",
        lambda: tmp_path,
    )

    with pytest.raises(CliError, match="exact current failure fingerprint"):
        validated_deterministic_phase_repair(
            tmp_path,
            state,
            state["resume_cursor"],
            head,
            "c" * 64,
        )

    evidence = validated_deterministic_phase_repair(
        tmp_path,
        state,
        state["resume_cursor"],
        head,
        failure_fingerprint,
    )
    assert evidence is not None
    assert evidence["failure_kind"] == "provider_contract_failure"
    assert evidence["repair_commit"] == head
    assert evidence["failure_fingerprint"] == failure_fingerprint
    assert evidence["repair_scope"] == "engine_runtime"
    assert evidence["engine_head"] == head
    assert "workspace_head" not in evidence

    atomic_write_phase_result(
        plan_dir,
        PhaseResult(
            phase="finalize",
            invocation_id="failed-inv",
            exit_kind=ExitKind.external_error.value,
            external_error=_contract_error(),
        ),
    )
    response = _override_recover_blocked(
        tmp_path,
        plan_dir,
        state,
        argparse.Namespace(
            plan="demo",
            reason="validated provider response-contract repair",
            repair_commit=head,
            failure_fingerprint=failure_fingerprint,
        ),
    )
    assert response["success"] is True
    persisted = json.loads((plan_dir / "state.json").read_text(encoding="utf-8"))
    allowance = persisted["meta"]["provider_contract_repair_retry"]
    assert allowance["status"] == "available"
    assert allowance["failure_kind"] == "provider_contract_failure"
    assert allowance["repair_commit"] == head


def test_provider_contract_repair_cannot_bypass_receipt_via_generic_resume() -> None:
    state = {
        "latest_failure": {
            "kind": "provider_contract_failure",
            "phase": "finalize",
        }
    }
    cursor = {
        "phase": "finalize",
        "retry_strategy": "repair_provider_contract",
    }
    phase_result = PhaseResult(
        phase="finalize",
        invocation_id="inv",
        exit_kind=ExitKind.external_error.value,
        external_error=_contract_error(),
    )

    assert _external_error_requires_resume(state, cursor, phase_result) is False


def test_success_retires_one_shot_provider_contract_repair_allowance(
    tmp_path: Path,
) -> None:
    plan_dir = tmp_path / "demo"
    plan_dir.mkdir()
    _write_state(plan_dir, repaired=True)

    auto._clear_latest_failure_for_success(plan_dir)

    state = json.loads((plan_dir / "state.json").read_text(encoding="utf-8"))
    assert "provider_contract_repair_retry" not in state["meta"]
    assert auto._provider_contract_repair_already_used(plan_dir, "finalize") is False
