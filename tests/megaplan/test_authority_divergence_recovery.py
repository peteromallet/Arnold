from __future__ import annotations

import argparse
import dataclasses
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

import pytest

from arnold_pipelines.megaplan._core.io import plans_root
from arnold_pipelines.megaplan._core.state import write_plan_state
from arnold_pipelines.megaplan.cli.parser import build_parser
from arnold_pipelines.megaplan.cli.status_view import handle_progress, handle_status
from arnold_pipelines.megaplan.handlers import override as override_handler
from arnold_pipelines.megaplan.handlers.init import handle_init
from arnold_pipelines.megaplan.orchestration.phase_result import (
    Deviation,
    ExitKind,
    PhaseResult,
    atomic_write_phase_result,
)
from arnold_pipelines.megaplan.planning.state import STATE_AWAITING_HUMAN, STATE_BLOCKED
from arnold_pipelines.megaplan.quality_resolutions import build_quality_resolution_event
from arnold_pipelines.megaplan.types import CliError
from tests.conftest import load_state


@dataclasses.dataclass
class LocalPlanFixture:
    root: Path
    project_dir: Path
    plan_name: str
    plan_dir: Path
    make_args: Callable[..., argparse.Namespace]


@pytest.fixture
def local_plan_fixture(tmp_path: Path) -> LocalPlanFixture:
    root = tmp_path / "root"
    root.mkdir()
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    base = build_parser().parse_args(["init"])

    def make_args(**kwargs: object) -> argparse.Namespace:
        args = argparse.Namespace(**vars(base))
        args.project_dir = str(project_dir)
        for key, value in kwargs.items():
            setattr(args, key, value)
        return args

    response = handle_init(
        root,
        make_args(idea="fixture plan", name="fixture-plan", robustness="standard"),
    )
    plan_name = response["plan"]
    plan_dir = plans_root(root) / plan_name
    return LocalPlanFixture(root, project_dir, plan_name, plan_dir, make_args)


def _set_authority_divergence_blocked_state(fixture: LocalPlanFixture) -> None:
    state = load_state(fixture.plan_dir)
    state["current_state"] = STATE_BLOCKED
    state["resume_cursor"] = {"phase": "execute", "retry_strategy": "rerun_phase"}
    state["latest_failure"] = {
        "kind": "authority_divergence",
        "message": "execute terminal success lacks corroborated task completion",
        "phase": "execute",
        "state": STATE_BLOCKED,
    }
    write_plan_state(fixture.plan_dir, mode="replace", state=state)


def _seed_live_execute_with_stale_finalize_blockers(
    fixture: LocalPlanFixture,
) -> None:
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00", "Z"
    )
    state = load_state(fixture.plan_dir)
    state["current_state"] = "finalized"
    state["active_step"] = {
        "phase": "execute",
        "agent": "hermes",
        "worker_pid": os.getpid(),
        "started_at": now,
        "last_activity_at": now,
    }
    write_plan_state(fixture.plan_dir, mode="replace", state=state)
    (fixture.plan_dir / "finalize.json").write_text(
        json.dumps(
            {
                "tasks": [
                    {
                        "id": "T1",
                        "status": "done",
                        "commands_run": ["pytest tests/test_example.py -q"],
                    },
                    {
                        "id": "T2",
                        "status": "pending",
                    },
                ]
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (fixture.plan_dir / "execution_batch_1.json").write_text(
        json.dumps(
            {
                "task_updates": [
                    {
                        "task_id": "T1",
                        "status": "done",
                        "commands_run": ["pytest tests/test_example.py -q"],
                    }
                ]
            }
        )
        + "\n",
        encoding="utf-8",
    )
    atomic_write_phase_result(
        fixture.plan_dir,
        PhaseResult(
            phase="finalize",
            invocation_id="fixture-invocation",
            exit_kind=ExitKind.success.value,
            deviations=(
                Deviation(
                    kind="quality_gate",
                    message="Success criteria require human verification during execution.",
                ),
            ),
        ),
    )


def test_status_projects_execute_for_authority_divergence_block(
    local_plan_fixture: LocalPlanFixture,
) -> None:
    _set_authority_divergence_blocked_state(local_plan_fixture)

    response = handle_status(
        local_plan_fixture.root,
        argparse.Namespace(plan=local_plan_fixture.plan_name, pending_human=False),
    )

    assert response["state"] == STATE_BLOCKED
    assert response["next_step"] == "execute"
    assert response["valid_next"] == ["execute"]


def test_recover_blocked_rejects_authority_divergence(
    local_plan_fixture: LocalPlanFixture,
) -> None:
    _set_authority_divergence_blocked_state(local_plan_fixture)

    with pytest.raises(CliError) as exc_info:
        override_handler.handle_override(
            local_plan_fixture.root,
            local_plan_fixture.make_args(
                plan=local_plan_fixture.plan_name,
                override_action="recover-blocked",
                reason="retry automation",
            ),
        )

    assert exc_info.value.code == "rerun_phase_required"
    assert "fresh phase rerun" in exc_info.value.message
    assert exc_info.value.extra["rerun_command"] == (
        f"megaplan execute --plan {local_plan_fixture.plan_name} "
        "--confirm-destructive --user-approved"
    )


def test_status_projects_execute_for_stale_recover_blocked_iteration_cap(
    local_plan_fixture: LocalPlanFixture,
) -> None:
    state = load_state(local_plan_fixture.plan_dir)
    state["current_state"] = STATE_BLOCKED
    state["resume_cursor"] = {
        "phase": "recover-blocked",
        "retry_strategy": "manual_review",
    }
    state["latest_failure"] = {
        "kind": "iteration_cap",
        "message": "exceeded max_iterations=200",
        "phase": "recover-blocked",
        "state": STATE_BLOCKED,
    }
    write_plan_state(local_plan_fixture.plan_dir, mode="replace", state=state)
    atomic_write_phase_result(
        local_plan_fixture.plan_dir,
        PhaseResult(
            phase="execute",
            invocation_id="fixture-invocation",
            exit_kind=ExitKind.blocked_by_quality.value,
        ),
    )

    response = handle_status(
        local_plan_fixture.root,
        argparse.Namespace(plan=local_plan_fixture.plan_name, pending_human=False),
    )

    assert response["state"] == STATE_BLOCKED
    assert response["next_step"] == "execute"
    assert response["valid_next"] == ["execute"]


def test_status_projects_execute_for_stale_recover_blocked_failure(
    local_plan_fixture: LocalPlanFixture,
) -> None:
    state = load_state(local_plan_fixture.plan_dir)
    state["current_state"] = STATE_BLOCKED
    state["resume_cursor"] = {
        "phase": "execute",
        "retry_strategy": "fresh_session",
    }
    state["latest_failure"] = {
        "kind": "blocked_recovery_not_resolved",
        "message": "recover-blocked requires every current blocker to be explicitly resolved as non-terminal",
        "phase": "recover-blocked",
        "state": STATE_BLOCKED,
    }
    write_plan_state(local_plan_fixture.plan_dir, mode="replace", state=state)
    atomic_write_phase_result(
        local_plan_fixture.plan_dir,
        PhaseResult(
            phase="execute",
            invocation_id="fixture-invocation",
            exit_kind=ExitKind.blocked_by_quality.value,
        ),
    )

    response = handle_status(
        local_plan_fixture.root,
        argparse.Namespace(plan=local_plan_fixture.plan_name, pending_human=False),
    )

    assert response["state"] == STATE_BLOCKED
    assert response["next_step"] == "execute"
    assert response["valid_next"] == ["execute"]


def test_status_prefers_resume_clarify_for_blocked_prep_clarification(
    local_plan_fixture: LocalPlanFixture,
) -> None:
    state = load_state(local_plan_fixture.plan_dir)
    state["current_state"] = STATE_BLOCKED
    state["resume_cursor"] = {
        "phase": "execute",
        "retry_strategy": "fresh_session",
    }
    state["latest_failure"] = {
        "kind": "blocked_recovery_not_resolved",
        "message": "recover-blocked requires every current blocker to be explicitly resolved as non-terminal",
        "phase": "recover-blocked",
        "state": STATE_BLOCKED,
    }
    state["clarification"] = {
        "source": "prep",
        "intent_summary": "prep surfaced 1 blocking ambiguity",
        "questions": ["Question 1"],
    }
    write_plan_state(local_plan_fixture.plan_dir, mode="replace", state=state)

    response = handle_status(
        local_plan_fixture.root,
        argparse.Namespace(plan=local_plan_fixture.plan_name, pending_human=False),
    )

    assert response["state"] == STATE_BLOCKED
    assert response["next_step"] == "resume-clarify"
    assert response["valid_next"] == ["resume-clarify"]


def test_resume_clarify_allows_blocked_state_with_prep_clarification(
    local_plan_fixture: LocalPlanFixture,
) -> None:
    state = load_state(local_plan_fixture.plan_dir)
    state["current_state"] = STATE_BLOCKED
    state["clarification"] = {
        "source": "prep",
        "intent_summary": "prep surfaced 1 blocking ambiguity",
        "questions": ["Question 1"],
    }
    state.setdefault("meta", {})["notes"] = [
        {"source": "user", "note": "Answer recorded."}
    ]
    write_plan_state(local_plan_fixture.plan_dir, mode="replace", state=state)

    response = override_handler._override_resume_clarify(
        local_plan_fixture.root,
        local_plan_fixture.plan_dir,
        load_state(local_plan_fixture.plan_dir),
        argparse.Namespace(plan=local_plan_fixture.plan_name),
    )

    assert response["success"] is True
    next_state = load_state(local_plan_fixture.plan_dir)
    assert next_state["current_state"] == "prepped"
    assert "clarification" not in next_state


def test_recover_blocked_allows_fixed_quality_rerun(
    local_plan_fixture: LocalPlanFixture,
) -> None:
    state = load_state(local_plan_fixture.plan_dir)
    state["current_state"] = STATE_BLOCKED
    state["resume_cursor"] = {"phase": "execute", "retry_strategy": "fresh_session"}
    state.setdefault("meta", {})["quality_gate_resolutions"] = [
        build_quality_resolution_event(
            blocker_id="quality:global:pending-tasks",
            resolution="fixed",
            phase="execute",
        )
    ]
    write_plan_state(local_plan_fixture.plan_dir, mode="replace", state=state)
    (local_plan_fixture.plan_dir / "finalize.json").write_text(
        '{"tasks":[]}\n',
        encoding="utf-8",
    )
    atomic_write_phase_result(
        local_plan_fixture.plan_dir,
        PhaseResult(
            phase="execute",
            invocation_id="fixture-invocation",
            exit_kind=ExitKind.blocked_by_quality.value,
            deviations=(
                Deviation(
                    kind="quality_gate",
                    message=(
                        "Advisory audit finding: Tasks left pending after execute "
                        "(executor never started them): T12, T13, T14"
                    ),
                    blocker_id="quality:global:pending-tasks",
                ),
            ),
        ),
    )

    response = override_handler.handle_override(
        local_plan_fixture.root,
        local_plan_fixture.make_args(
            plan=local_plan_fixture.plan_name,
            override_action="recover-blocked",
            reason="rerun execute after resolving quality blockers as fixed",
        ),
    )

    updated = load_state(local_plan_fixture.plan_dir)
    assert response["success"] is True
    assert response["state"] == "finalized"
    assert response["archived_phase_result"].startswith("phase_result.recovered-")
    assert updated["current_state"] == "finalized"
    assert not (local_plan_fixture.plan_dir / "phase_result.json").exists()
    assert len(list(local_plan_fixture.plan_dir.glob("phase_result.recovered-*.json"))) == 1

    status = handle_status(
        local_plan_fixture.root,
        argparse.Namespace(plan=local_plan_fixture.plan_name, pending_human=False),
    )

    assert status["state"] == "finalized"
    assert status["next_step"] == "execute"
    assert "blocker_recovery" not in status
    assert "suggested_recovery_commands" not in status


def test_status_hides_recovery_blockers_while_execute_step_is_live(
    local_plan_fixture: LocalPlanFixture,
) -> None:
    _seed_live_execute_with_stale_finalize_blockers(local_plan_fixture)

    response = handle_status(
        local_plan_fixture.root,
        argparse.Namespace(plan=local_plan_fixture.plan_name, pending_human=False),
    )

    assert response["state"] == "finalized"
    assert response["active_step"]["recommended_action"] == "wait"
    assert "blocker_recovery" not in response
    assert "quality_blockers" not in response
    assert "suggested_recovery_commands" not in response


def test_status_ignores_non_blocking_gate_warnings_after_finalize(
    local_plan_fixture: LocalPlanFixture,
) -> None:
    warnings = [
        "The plan has one open question about Hetzner deployment/sync mechanics for cloud verification (Step 8). This is scoped as an integration check and does not block local implementation, but the implementation worker should resolve it before the cloud validation step.",
        "The `_normalize_stage_metric_phase` garbling concern is noted but deferred: Step 1 says to treat it as a real defect only if the working tree confirms it. The implementation worker should inspect this early to avoid downstream rework.",
    ]
    state = load_state(local_plan_fixture.plan_dir)
    state["current_state"] = "finalized"
    state["last_gate"] = {
        "warnings": warnings
    }
    write_plan_state(local_plan_fixture.plan_dir, mode="replace", state=state)
    (local_plan_fixture.plan_dir / "finalize.json").write_text(
        json.dumps({"tasks": [{"id": "T1", "status": "pending"}]}) + "\n",
        encoding="utf-8",
    )
    atomic_write_phase_result(
        local_plan_fixture.plan_dir,
        PhaseResult(
            phase="finalize",
            invocation_id="fixture-invocation",
            exit_kind=ExitKind.success.value,
            deviations=tuple(
                Deviation(kind="quality_gate", message=warning)
                for warning in warnings
            ),
        ),
    )

    response = handle_status(
        local_plan_fixture.root,
        argparse.Namespace(plan=local_plan_fixture.plan_name, pending_human=False),
    )

    assert response["state"] == "finalized"
    assert response["next_step"] == "execute"
    assert "execute" in response["valid_next"]
    assert "step" in response["valid_next"]
    assert response["progress"]["tasks_pending"] == 1
    assert "blocker_recovery" not in response


def test_status_ignores_successful_finalize_runtime_recheck_warnings(
    local_plan_fixture: LocalPlanFixture,
) -> None:
    state = load_state(local_plan_fixture.plan_dir)
    state["current_state"] = "finalized"
    state["last_gate"] = {
        "recommendation": "PROCEED",
        "passed": True,
        "warnings": [
            "Criteria 8 and 10 require runtime observation and subjective human judgment during deployment phases (Steps 9-11). These cannot be verified at gate time and must be rechecked after cloud deployment.",
            "Three open questions in the plan metadata remain unanswered: authoritative remote paths, SSH access fallback, and whether an additional incident projection is needed. The plan handles these as execution-time discoveries (Steps 9-10), which is acceptable but creates downstream uncertainty.",
        ],
    }
    write_plan_state(local_plan_fixture.plan_dir, mode="replace", state=state)
    (local_plan_fixture.plan_dir / "finalize.json").write_text(
        json.dumps({"tasks": [{"id": "T1", "status": "pending"}]}) + "\n",
        encoding="utf-8",
    )
    atomic_write_phase_result(
        local_plan_fixture.plan_dir,
        PhaseResult(
            phase="finalize",
            invocation_id="fixture-invocation",
            exit_kind=ExitKind.success.value,
            deviations=(
                Deviation(
                    kind="quality_gate",
                    message=(
                        "Criteria 8 and 10 require runtime observation and subjective "
                        "human judgment during deployment phases (Steps 9-11). These "
                        "cannot be verified at gate time and must be rechecked after "
                        "cloud deployment."
                    ),
                ),
                Deviation(
                    kind="quality_gate",
                    message=(
                        "Three open questions in the plan metadata remain unanswered: "
                        "authoritative remote paths, SSH access fallback, and whether "
                        "an additional incident projection is needed. The plan handles "
                        "these as execution-time discoveries (Steps 9-10), which is "
                        "acceptable but creates downstream uncertainty."
                    ),
                ),
            ),
        ),
    )

    response = handle_status(
        local_plan_fixture.root,
        argparse.Namespace(plan=local_plan_fixture.plan_name, pending_human=False),
    )

    assert response["state"] == "finalized"
    assert response["next_step"] == "execute"
    assert "execute" in response["valid_next"]
    assert "blocker_recovery" not in response


def test_progress_hides_recovery_blockers_while_execute_step_is_live(
    local_plan_fixture: LocalPlanFixture,
) -> None:
    _seed_live_execute_with_stale_finalize_blockers(local_plan_fixture)

    response = handle_progress(
        local_plan_fixture.root,
        argparse.Namespace(plan=local_plan_fixture.plan_name),
    )

    assert response["tasks_done"] == 1
    assert response["tasks_pending"] == 1
    assert "blocker_recovery" not in response
    assert "quality_blockers" not in response
    assert "suggested_recovery_commands" not in response
