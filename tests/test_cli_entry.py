from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pytest

from arnold.pipelines.megaplan.cli import (
    COMMAND_HANDLERS,
    _build_status_payload,
    cli_entry,
    handle_quality_gate,
    handle_user_action,
)
from arnold.pipelines.megaplan.cloud.cli import _register_cloud_subcommands, build_cloud_parser
from arnold.pipelines.megaplan.handlers import handle_override
from arnold.pipelines.megaplan.handlers.override import _OVERRIDE_ACTIONS
from arnold.pipelines.megaplan.orchestration.phase_result import BlockedTask, Deviation, ExternalError
from arnold.pipelines.megaplan.user_actions import (
    VALID_RESOLUTIONS,
    build_resolution_event,
    effective_resolutions,
)


def _invoke_cli_entry() -> None:
    cli_entry()


def _subcommands(parser: argparse.ArgumentParser) -> set[str]:
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            return set(action.choices)
    raise AssertionError("parser did not register any subcommands")


def _subparser(parser: argparse.ArgumentParser, name: str) -> argparse.ArgumentParser:
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            return action.choices[name]
    raise AssertionError(f"parser did not register subcommand {name!r}")


def test_build_cloud_parser_matches_register_cloud_subcommands() -> None:
    top_level = argparse.ArgumentParser()
    top_level_subparsers = top_level.add_subparsers(dest="command", required=True)
    build_cloud_parser(top_level_subparsers)

    standalone = argparse.ArgumentParser(prog="megaplan cloud")
    _register_cloud_subcommands(standalone)

    cloud_parser = _subparser(top_level, "cloud")
    assert _subcommands(cloud_parser) == _subcommands(standalone)


def test_cli_entry_lazy_cloud_help(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(sys, "argv", ["megaplan", "cloud", "status", "--help"])

    with pytest.raises(SystemExit) as info:
        _invoke_cli_entry()

    assert info.value.code == 0
    output = capsys.readouterr().out
    assert "usage: megaplan cloud status" in output
    assert "--plan" in output


def test_cli_entry_lazy_cloud_supervise_help(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """``megaplan cloud supervise --help`` shows --chain, --cloud-yaml, and --remote-spec."""
    monkeypatch.setattr(sys, "argv", ["megaplan", "cloud", "supervise", "--help"])

    with pytest.raises(SystemExit) as info:
        _invoke_cli_entry()

    assert info.value.code == 0
    output = capsys.readouterr().out
    assert "--chain" in output
    assert "--cloud-yaml" in output
    assert "--remote-spec" in output


# ---------------------------------------------------------------------------
# user-action resolve CLI tests
# ---------------------------------------------------------------------------


def _setup_resolution_plan_dir(tmp_path: Path) -> tuple[Path, Path, dict[str, object]]:
    """Create a minimal plan directory with finalize.json for CLI testing."""
    root = tmp_path / "root"
    plan_dir = root / ".megaplan" / "plans" / "test-plan"
    plan_dir.mkdir(parents=True)

    state = {
        "name": "test-plan",
        "idea": "test",
        "current_state": "planned",
        "iteration": 1,
        "created_at": "2026-05-20T00:00:00Z",
        "config": {"project_dir": str(root)},
        "sessions": {},
        "plan_versions": [],
        "history": [],
        "meta": {
            "notes": [],
            "overrides": [],
            "user_action_resolutions": [],
        },
        "last_gate": {},
    }
    state_path = plan_dir / "state.json"
    state_path.write_text(json.dumps(state), encoding="utf-8")
    return root, plan_dir, state


def _write_minimal_status_plan(root: Path, plan: str, state: str) -> None:
    plan_dir = root / ".megaplan" / "plans" / plan
    plan_dir.mkdir(parents=True)
    payload = {
        "name": plan,
        "idea": "test",
        "current_state": state,
        "iteration": 1,
        "created_at": "2026-06-03T00:00:00Z",
        "config": {"project_dir": str(root)},
        "sessions": {},
        "plan_versions": [],
        "history": [],
        "meta": {"notes": []},
        "last_gate": {},
    }
    (plan_dir / "state.json").write_text(json.dumps(payload), encoding="utf-8")


def test_status_project_dir_resolves_plan_from_target_not_cwd(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    from arnold.pipelines.megaplan import cli as cli_mod

    engine_root = tmp_path / "engine"
    target_root = tmp_path / "target"
    engine_root.mkdir()
    target_root.mkdir()
    _write_minimal_status_plan(engine_root, "demo-plan", "planned")
    _write_minimal_status_plan(target_root, "demo-plan", "executed")

    monkeypatch.chdir(engine_root)
    monkeypatch.setattr(cli_mod, "_auto_sync_installed_skills", lambda: None)

    code = cli_mod.main(
        ["status", "--project-dir", str(target_root), "--plan", "demo-plan"]
    )

    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["plan"] == "demo-plan"
    assert payload["state"] == "executed"


def _write_finalize_with_actions(
    plan_dir: Path,
    *,
    user_actions: list[dict[str, object]] | None = None,
    tasks: list[dict[str, object]] | None = None,
) -> None:
    finalize_path = plan_dir / "finalize.json"
    data: dict[str, object] = {
        "tasks": tasks
        or [
            {
                "id": "T1",
                "description": "Task 1",
                "depends_on": [],
                "status": "pending",
            },
        ],
    }
    if user_actions:
        data["user_actions"] = user_actions
    finalize_path.write_text(json.dumps(data), encoding="utf-8")


def _write_minimal_status_plan(root: Path, plan: str, state: str) -> None:
    plan_dir = root / ".megaplan" / "plans" / plan
    plan_dir.mkdir(parents=True)
    payload = {
        "name": plan,
        "idea": "test",
        "current_state": state,
        "iteration": 1,
        "created_at": "2026-06-03T00:00:00Z",
        "config": {"project_dir": str(root)},
        "sessions": {},
        "plan_versions": [],
        "history": [],
        "meta": {"notes": []},
        "last_gate": {},
    }
    (plan_dir / "state.json").write_text(json.dumps(payload), encoding="utf-8")


def test_status_project_dir_resolves_plan_from_target_not_cwd(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    from arnold.pipelines.megaplan import cli as cli_mod

    engine_root = tmp_path / "engine"
    target_root = tmp_path / "target"
    engine_root.mkdir()
    target_root.mkdir()
    _write_minimal_status_plan(engine_root, "demo-plan", "planned")
    _write_minimal_status_plan(target_root, "demo-plan", "executed")

    monkeypatch.chdir(engine_root)
    monkeypatch.setattr(cli_mod, "_auto_sync_installed_skills", lambda: None)

    code = cli_mod.main(
        ["status", "--project-dir", str(target_root), "--plan", "demo-plan"]
    )

    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["plan"] == "demo-plan"
    assert payload["state"] == "executed"


def test_user_action_resolve_valid_write(tmp_path: Path) -> None:
    """End-to-end: write a resolution via the CLI handler, verify persistence."""
    root, plan_dir, state = _setup_resolution_plan_dir(tmp_path)
    _write_finalize_with_actions(
        plan_dir,
        user_actions=[
            {
                "id": "ua1",
                "description": "Approve deployment",
                "phase": "before_execute",
                "blocks_task_ids": ["T1"],
            }
        ],
    )

    args = argparse.Namespace(
        plan="test-plan",
        user_action_action="resolve",
        action_id="ua1",
        resolution="satisfied",
        fallback_mode=None,
        tasks=None,
        instructions=None,
        reason="All checks passed",
    )
    result = handle_user_action(root, args)

    assert result["success"] is True
    assert "ua1" in str(result.get("summary", ""))
    assert "satisfied" in str(result.get("summary", ""))

    # Verify persistence
    state_data = json.loads((plan_dir / "state.json").read_text(encoding="utf-8"))
    resolutions = state_data["meta"].get("user_action_resolutions", [])
    assert len(resolutions) == 1
    assert resolutions[0]["action_id"] == "ua1"
    assert resolutions[0]["resolution"] == "satisfied"
    assert resolutions[0]["reason"] == "All checks passed"
    assert "timestamp" in resolutions[0]
    assert "created_at" in resolutions[0]
    assert resolutions[0]["created_at"] == resolutions[0]["timestamp"]
    assert "created_by" in resolutions[0]


def test_user_action_resolve_accepted_blocked_with_fallback(tmp_path: Path) -> None:
    """Write an accepted_blocked resolution with all fallback fields."""
    root, plan_dir, state = _setup_resolution_plan_dir(tmp_path)
    _write_finalize_with_actions(
        plan_dir,
        user_actions=[
            {
                "id": "ua2",
                "description": "Run manual migration",
                "phase": "before_execute",
                "blocks_task_ids": ["T1"],
            }
        ],
    )

    args = argparse.Namespace(
        plan="test-plan",
        user_action_action="resolve",
        action_id="ua2",
        resolution="accepted_blocked",
        fallback_mode="skip_migration",
        tasks="T1",
        instructions="Proceed without migration; validate schema after",
        reason="Migration not needed in dev",
    )
    result = handle_user_action(root, args)

    assert result["success"] is True
    state_data = json.loads((plan_dir / "state.json").read_text(encoding="utf-8"))
    resolutions = state_data["meta"].get("user_action_resolutions", [])
    assert len(resolutions) == 1
    ev = resolutions[0]
    assert ev["action_id"] == "ua2"
    assert ev["resolution"] == "accepted_blocked"
    assert ev["fallback_mode"] == "skip_migration"
    assert ev["applies_to_tasks"] == ["T1"]
    assert ev["instructions"] == "Proceed without migration; validate schema after"
    assert ev["reason"] == "Migration not needed in dev"


def test_user_action_resolve_all_five_states_persist(tmp_path: Path) -> None:
    """All five resolution constants are accepted and persisted."""
    root, plan_dir, state = _setup_resolution_plan_dir(tmp_path)
    _write_finalize_with_actions(
        plan_dir,
        user_actions=[
            {
                "id": f"ua{i}",
                "description": f"Action {i}",
                "phase": "before_execute",
                "blocks_task_ids": ["T1"],
            }
            for i in range(5)
        ],
    )

    for i, resolution in enumerate(VALID_RESOLUTIONS):
        args = argparse.Namespace(
            plan="test-plan",
            user_action_action="resolve",
            action_id=f"ua{i}",
            resolution=resolution,
            fallback_mode=None,
            tasks=None,
            instructions=None,
            reason=f"Test {resolution}",
        )
        result = handle_user_action(root, args)
        assert result["success"] is True, f"Failed for resolution {resolution}"

    # Verify all five persisted
    state_data = json.loads((plan_dir / "state.json").read_text(encoding="utf-8"))
    resolutions = state_data["meta"].get("user_action_resolutions", [])
    assert len(resolutions) == 5
    persisted = {ev["resolution"] for ev in resolutions}
    assert persisted == set(VALID_RESOLUTIONS)


def test_user_action_resolve_invalid_resolution_choice(tmp_path: Path) -> None:
    """Invalid resolution choice is rejected by argparse before handler."""
    _setup_resolution_plan_dir(tmp_path)

    parser = _build_parser_for_test()
    with pytest.raises(SystemExit):
        parser.parse_args(
            ["user-action", "resolve", "--action-id", "ua1", "--resolution", "bogus"]
        )


def test_user_action_resolve_unknown_action_id(tmp_path: Path) -> None:
    """Unknown action_id is rejected with a clear error message."""
    root, plan_dir, state = _setup_resolution_plan_dir(tmp_path)
    _write_finalize_with_actions(
        plan_dir,
        user_actions=[
            {
                "id": "ua1",
                "description": "Known action",
                "phase": "before_execute",
                "blocks_task_ids": ["T1"],
            }
        ],
    )

    args = argparse.Namespace(
        plan="test-plan",
        user_action_action="resolve",
        action_id="ua_nonexistent",
        resolution="satisfied",
        fallback_mode=None,
        tasks=None,
        instructions=None,
        reason=None,
    )
    from arnold.pipelines.megaplan.types import CliError

    with pytest.raises(CliError) as exc_info:
        handle_user_action(root, args)

    msg = str(exc_info.value)
    assert "ua_nonexistent" in msg


def test_user_action_resolve_bad_task_scope(tmp_path: Path) -> None:
    """Typoed --tasks value fails with clear error referencing valid task IDs."""
    root, plan_dir, state = _setup_resolution_plan_dir(tmp_path)
    _write_finalize_with_actions(
        plan_dir,
        user_actions=[
            {
                "id": "ua1",
                "description": "Action",
                "phase": "before_execute",
                "blocks_task_ids": ["T1"],
            }
        ],
        tasks=[
            {
                "id": "T1",
                "description": "Task 1",
                "depends_on": [],
                "status": "pending",
            },
        ],
    )

    args = argparse.Namespace(
        plan="test-plan",
        user_action_action="resolve",
        action_id="ua1",
        resolution="satisfied",
        fallback_mode=None,
        tasks="T_nonexistent",
        instructions=None,
        reason=None,
    )
    from arnold.pipelines.megaplan.types import CliError

    with pytest.raises(CliError) as exc_info:
        handle_user_action(root, args)

    msg = str(exc_info.value)
    assert "T_nonexistent" in msg


def test_user_action_resolve_persists_metadata_fields(tmp_path: Path) -> None:
    """All metadata fields (timestamp, created_at, created_by) are persisted."""
    root, plan_dir, state = _setup_resolution_plan_dir(tmp_path)
    _write_finalize_with_actions(
        plan_dir,
        user_actions=[
            {
                "id": "ua1",
                "description": "Action",
                "phase": "before_execute",
                "blocks_task_ids": ["T1"],
            }
        ],
    )

    args = argparse.Namespace(
        plan="test-plan",
        user_action_action="resolve",
        action_id="ua1",
        resolution="waived",
        fallback_mode=None,
        tasks=None,
        instructions=None,
        reason=None,
    )
    result = handle_user_action(root, args)
    assert result["success"] is True

    state_data = json.loads((plan_dir / "state.json").read_text(encoding="utf-8"))
    ev = state_data["meta"]["user_action_resolutions"][0]

    # Verify metadata
    assert "timestamp" in ev
    assert "created_at" in ev
    assert ev["timestamp"] == ev["created_at"]
    assert "created_by" in ev
    assert isinstance(ev["created_by"], str) and len(ev["created_by"]) > 0


def test_user_action_resolve_multiple_events_latest_wins(tmp_path: Path) -> None:
    """Two resolution events for the same action: effective_resolutions returns latest."""
    root, plan_dir, state = _setup_resolution_plan_dir(tmp_path)
    _write_finalize_with_actions(
        plan_dir,
        user_actions=[
            {
                "id": "ua1",
                "description": "Action",
                "phase": "before_execute",
                "blocks_task_ids": ["T1"],
            }
        ],
    )

    # First resolution
    args1 = argparse.Namespace(
        plan="test-plan",
        user_action_action="resolve",
        action_id="ua1",
        resolution="manual_required",
        fallback_mode=None,
        tasks=None,
        instructions=None,
        reason="first pass",
    )
    handle_user_action(root, args1)

    # Second resolution (overrides first)
    args2 = argparse.Namespace(
        plan="test-plan",
        user_action_action="resolve",
        action_id="ua1",
        resolution="satisfied",
        fallback_mode=None,
        tasks=None,
        instructions=None,
        reason="updated",
    )
    handle_user_action(root, args2)

    state_data = json.loads((plan_dir / "state.json").read_text(encoding="utf-8"))
    events = state_data["meta"]["user_action_resolutions"]
    assert len(events) == 2

    effective = effective_resolutions(events)
    assert effective["ua1"]["resolution"] == "satisfied"
    assert effective["ua1"]["reason"] == "updated"


def test_user_action_resolve_task_out_of_action_scope(tmp_path: Path) -> None:
    """--tasks with a valid task ID that is NOT in the action's blocks_task_ids fails."""
    root, plan_dir, state = _setup_resolution_plan_dir(tmp_path)
    _write_finalize_with_actions(
        plan_dir,
        user_actions=[
            {
                "id": "ua1",
                "description": "Action",
                "phase": "before_execute",
                "blocks_task_ids": ["T1"],
            }
        ],
        tasks=[
            {
                "id": "T1",
                "description": "Task 1",
                "depends_on": [],
                "status": "pending",
            },
            {
                "id": "T2",
                "description": "Task 2",
                "depends_on": [],
                "status": "pending",
            },
        ],
    )

    # T2 exists in finalize.json but is NOT blocked by ua1
    args = argparse.Namespace(
        plan="test-plan",
        user_action_action="resolve",
        action_id="ua1",
        resolution="satisfied",
        fallback_mode=None,
        tasks="T2",
        instructions=None,
        reason=None,
    )
    from arnold.pipelines.megaplan.types import CliError

    with pytest.raises(CliError) as exc_info:
        handle_user_action(root, args)

    msg = str(exc_info.value)
    assert "T2" in msg
    assert "not in action" in msg.lower() or "blocked task scope" in msg.lower()
    assert exc_info.value.extra["requested_task_ids"] == ["T2"]
    assert exc_info.value.extra["allowed_task_ids"] == ["T1"]
    assert exc_info.value.extra["invalid_task_ids"] == ["T2"]


def test_user_action_resolve_unknown_task_returns_actionable_extra(
    tmp_path: Path,
) -> None:
    root, plan_dir, state = _setup_resolution_plan_dir(tmp_path)
    _write_finalize_with_actions(
        plan_dir,
        user_actions=[
            {
                "id": "ua1",
                "description": "Action",
                "phase": "before_execute",
                "blocks_task_ids": ["T1"],
            }
        ],
        tasks=[
            {
                "id": "T1",
                "description": "Task 1",
                "depends_on": [],
                "status": "pending",
            },
        ],
    )

    args = argparse.Namespace(
        plan="test-plan",
        user_action_action="resolve",
        action_id="ua1",
        resolution="satisfied",
        fallback_mode=None,
        tasks="T_missing",
        instructions=None,
        reason=None,
    )
    from arnold.pipelines.megaplan.types import CliError

    with pytest.raises(CliError) as exc_info:
        handle_user_action(root, args)

    assert exc_info.value.extra["requested_task_ids"] == ["T_missing"]
    assert exc_info.value.extra["unknown_task_ids"] == ["T_missing"]
    assert exc_info.value.extra["known_task_ids"] == ["T1"]


def test_user_action_resolve_allows_derived_synthetic_gate_scope(
    tmp_path: Path,
) -> None:
    root, plan_dir, state = _setup_resolution_plan_dir(tmp_path)
    _write_finalize_with_actions(
        plan_dir,
        user_actions=[
            {
                "id": "ua_legacy",
                "description": "Legacy prerequisite",
                "phase": "before_execute",
            }
        ],
        tasks=[
            {
                "id": "T0",
                "description": "gate",
                "depends_on": [],
                "status": "pending",
            },
            {
                "id": "T1",
                "description": "Task 1",
                "depends_on": ["T0"],
                "status": "pending",
            },
            {
                "id": "T2",
                "description": "Task 2",
                "depends_on": ["T0"],
                "status": "pending",
            },
        ],
    )

    args = argparse.Namespace(
        plan="test-plan",
        user_action_action="resolve",
        action_id="ua_legacy",
        resolution="satisfied",
        fallback_mode=None,
        tasks="T2",
        instructions=None,
        reason="covered by operator",
        phase="execute",
        evidence=["operator note", "audit log"],
        debt_note="temporary dependency",
    )
    result = handle_user_action(root, args)

    assert result["success"] is True
    assert result["phase"] == "execute"
    assert result["evidence"] == ["operator note", "audit log"]
    assert result["debt_note"] == "temporary dependency"
    state_data = json.loads((plan_dir / "state.json").read_text(encoding="utf-8"))
    event = state_data["meta"]["user_action_resolutions"][0]
    assert event["applies_to_tasks"] == ["T2"]
    assert event["phase"] == "execute"
    assert event["evidence"] == ["operator note", "audit log"]
    assert event["debt_note"] == "temporary dependency"


def test_quality_gate_resolve_persists_resolution_event(tmp_path: Path) -> None:
    root, plan_dir, state = _setup_resolution_plan_dir(tmp_path)
    blocker_id = "quality:T1:missing-evidence"
    _write_finalize_with_actions(plan_dir)

    from tests.conftest import make_fake_phase_result

    make_fake_phase_result(
        plan_dir,
        exit_kind="blocked_by_quality",
        deviations=(
            Deviation(
                kind="quality_gate",
                message="missing execution evidence",
                task_id="T1",
                blocker_id=blocker_id,
            ),
        ),
    )

    args = argparse.Namespace(
        plan="test-plan",
        quality_gate_action="resolve",
        blocker_id=blocker_id,
        resolution="accepted_with_debt",
        phase="execute",
        evidence=["execution_batch_1.json", "operator note"],
        debt_note="evidence will be backfilled in follow-up",
        fallback_mode="degraded-validation",
    )
    result = handle_quality_gate(root, args)

    assert result["success"] is True
    assert result["blocker_id"] == blocker_id
    assert result["resolution"] == "accepted_with_debt"
    assert result["phase"] == "execute"
    assert result["evidence"] == ["execution_batch_1.json", "operator note"]
    assert result["debt_note"] == "evidence will be backfilled in follow-up"
    assert result["fallback_mode"] == "degraded-validation"
    assert result["blocker"]["blocker_id"] == blocker_id

    state_data = json.loads((plan_dir / "state.json").read_text(encoding="utf-8"))
    events = state_data["meta"]["quality_gate_resolutions"]
    assert len(events) == 1
    assert events[0]["blocker_id"] == blocker_id
    assert events[0]["resolution"] == "accepted_with_debt"
    assert events[0]["phase"] == "execute"
    assert events[0]["fallback_mode"] == "degraded-validation"


def test_quality_gate_resolve_updates_status_recovery_payload(
    tmp_path: Path,
) -> None:
    root, plan_dir, state = _setup_resolution_plan_dir(tmp_path)
    blocker_id = "quality:T1:missing-evidence"
    _write_finalize_with_actions(plan_dir)

    from tests.conftest import make_fake_phase_result

    make_fake_phase_result(
        plan_dir,
        exit_kind="blocked_by_quality",
        deviations=(
            Deviation(
                kind="quality_gate",
                message="missing execution evidence",
                task_id="T1",
                blocker_id=blocker_id,
            ),
        ),
    )

    before = _build_status_payload(plan_dir, state)
    assert before["quality_blockers"][0]["resolution_state"] == "unresolved"
    assert before["quality_blockers"][0]["resolution_behavior"] == "hard_block"
    assert (
        f"quality-gate resolve --blocker-id {blocker_id}"
        in before["suggested_recovery_commands"]
    )

    args = argparse.Namespace(
        plan="test-plan",
        quality_gate_action="resolve",
        blocker_id=blocker_id,
        resolution="fixed",
        phase="execute",
        evidence=None,
        debt_note=None,
    )
    handle_quality_gate(root, args)

    state_after = json.loads((plan_dir / "state.json").read_text(encoding="utf-8"))
    after = _build_status_payload(plan_dir, state_after)
    blocker = after["quality_blockers"][0]

    assert blocker["blocker_id"] == blocker_id
    assert blocker["resolution_state"] == "fixed"
    assert blocker["resolution_behavior"] == "rerun_required"
    assert blocker["requires_rerun"] is True
    assert blocker["suggested_commands"] == ["execute --retry-blocked-tasks"]
    assert "execute --retry-blocked-tasks" in after["suggested_recovery_commands"]


def test_quality_gate_resolve_rejects_unknown_current_blocker(
    tmp_path: Path,
) -> None:
    root, plan_dir, state = _setup_resolution_plan_dir(tmp_path)
    _write_finalize_with_actions(plan_dir)

    from tests.conftest import make_fake_phase_result

    make_fake_phase_result(
        plan_dir,
        exit_kind="blocked_by_quality",
        deviations=(
            Deviation(
                kind="quality_gate",
                message="missing execution evidence",
                task_id="T1",
                blocker_id="quality:T1:known",
            ),
        ),
    )

    args = argparse.Namespace(
        plan="test-plan",
        quality_gate_action="resolve",
        blocker_id="quality:T1:missing",
        resolution="fixed",
        phase="execute",
        evidence=None,
        debt_note=None,
    )

    from arnold.pipelines.megaplan.types import CliError

    with pytest.raises(CliError) as exc_info:
        handle_quality_gate(root, args)

    assert exc_info.value.extra["requested_blocker_id"] == "quality:T1:missing"
    assert exc_info.value.extra["known_blocker_ids"] == ["quality:T1:known"]


def test_quality_gate_and_recover_blocked_are_registered() -> None:
    parser = _build_parser_for_test()

    quality_args = parser.parse_args(
        [
            "quality-gate",
            "resolve",
            "--blocker-id",
            "quality:T1:abc",
            "--resolution",
            "fixed",
            "--fallback-mode",
            "rerun",
        ]
    )
    assert quality_args.command == "quality-gate"
    assert quality_args.quality_gate_action == "resolve"
    assert quality_args.fallback_mode == "rerun"
    assert COMMAND_HANDLERS["quality-gate"] is handle_quality_gate

    override_args = parser.parse_args(
        [
            "override",
            "recover-blocked",
            "--plan",
            "test-plan",
            "--reason",
            "operator resolved blocker",
        ]
    )
    assert override_args.command == "override"
    assert override_args.override_action == "recover-blocked"
    assert COMMAND_HANDLERS["override"] is handle_override
    assert "recover-blocked" in _OVERRIDE_ACTIONS


def test_override_recover_blocked_restores_resume_state(tmp_path: Path) -> None:
    root, plan_dir, state = _setup_resolution_plan_dir(tmp_path)
    state["current_state"] = "blocked"
    state["resume_cursor"] = {"phase": "execute", "retry_strategy": "fresh_session"}
    state["latest_failure"] = {"kind": "execution_blocked"}
    state["meta"]["user_action_resolutions"] = [
        build_resolution_event(
            action_id="ua_legacy",
            resolution="satisfied",
            tasks=["gate"],
            reason="operator completed legacy gate",
        )
    ]
    (plan_dir / "state.json").write_text(json.dumps(state), encoding="utf-8")
    _write_finalize_with_actions(
        plan_dir,
        tasks=[
            {
                "id": "gate",
                "description": "Verify before_execute prerequisites",
                "depends_on": [],
                "status": "pending",
            },
            {
                "id": "T1",
                "description": "Task 1",
                "depends_on": ["gate"],
                "status": "pending",
            },
        ],
        user_actions=[
            {
                "id": "ua_legacy",
                "description": "Approve deployment",
                "phase": "before_execute",
            }
        ],
    )

    from tests.conftest import make_fake_phase_result

    make_fake_phase_result(
        plan_dir,
        exit_kind="blocked_by_prereq",
        blocked_tasks=(
            BlockedTask(
                task_id="gate",
                reason="before_execute action is unresolved",
            ),
        ),
    )

    args = argparse.Namespace(
        plan="test-plan",
        override_action="recover-blocked",
        reason="operator resolved external blocker",
    )
    result = handle_override(root, args)

    assert result["success"] is True
    assert result["state"] == "finalized"
    assert result["next_step"] == "execute"
    state_data = json.loads((plan_dir / "state.json").read_text(encoding="utf-8"))
    assert state_data["current_state"] == "finalized"
    assert "latest_failure" not in state_data
    override = state_data["meta"]["overrides"][-1]
    assert override["action"] == "recover-blocked"
    assert override["reason"] == "operator resolved external blocker"
    assert override["blocker_ids"] == ["prereq:ua_legacy:gate"]


def test_override_recover_blocked_refuses_unresolved_prereq(
    tmp_path: Path,
) -> None:
    root, plan_dir, state = _setup_resolution_plan_dir(tmp_path)
    state["current_state"] = "blocked"
    state["resume_cursor"] = {"phase": "execute", "retry_strategy": "fresh_session"}
    state["latest_failure"] = {"kind": "execution_blocked"}
    (plan_dir / "state.json").write_text(json.dumps(state), encoding="utf-8")
    _write_finalize_with_actions(
        plan_dir,
        user_actions=[
            {
                "id": "ua1",
                "description": "Approve deployment",
                "phase": "before_execute",
                "blocks_task_ids": ["T1"],
            }
        ],
    )

    from tests.conftest import make_fake_phase_result

    make_fake_phase_result(
        plan_dir,
        exit_kind="blocked_by_prereq",
        blocked_tasks=(
            BlockedTask(
                task_id="T1",
                reason="prerequisite unresolved",
                blocking_action_ids=("ua1",),
            ),
        ),
    )

    args = argparse.Namespace(
        plan="test-plan",
        override_action="recover-blocked",
        reason="operator tried too early",
    )

    from arnold.pipelines.megaplan.types import CliError

    with pytest.raises(CliError) as exc_info:
        handle_override(root, args)

    assert exc_info.value.code == "blocked_recovery_not_resolved"
    assert exc_info.value.extra["blocker_ids"] == ["prereq:ua1:T1"]
    blocker = exc_info.value.extra["unresolved_blockers"][0]
    assert blocker["resolution_state"] == "unresolved"
    assert blocker["suggested_commands"] == [
        "user-action resolve --action-id ua1 --tasks T1"
    ]
    state_data = json.loads((plan_dir / "state.json").read_text(encoding="utf-8"))
    assert state_data["current_state"] == "blocked"
    assert state_data["latest_failure"] == {"kind": "execution_blocked"}


def test_override_recover_blocked_refuses_active_fixed_quality_blocker(
    tmp_path: Path,
) -> None:
    root, plan_dir, state = _setup_resolution_plan_dir(tmp_path)
    blocker_id = "quality:T1:missing-evidence"
    state["current_state"] = "blocked"
    state["resume_cursor"] = {"phase": "review", "retry_strategy": "fresh_session"}
    state["latest_failure"] = {"kind": "quality_blocked"}

    from arnold.pipelines.megaplan.quality_resolutions import build_quality_resolution_event

    state["meta"]["quality_gate_resolutions"] = [
        build_quality_resolution_event(
            blocker_id=blocker_id,
            resolution="fixed",
            phase="execute",
            evidence=["operator says fixed"],
        )
    ]
    (plan_dir / "state.json").write_text(json.dumps(state), encoding="utf-8")
    _write_finalize_with_actions(plan_dir)

    from tests.conftest import make_fake_phase_result

    make_fake_phase_result(
        plan_dir,
        exit_kind="blocked_by_quality",
        deviations=(
            Deviation(
                kind="quality_gate",
                message="missing execution evidence",
                task_id="T1",
                blocker_id=blocker_id,
            ),
        ),
    )

    args = argparse.Namespace(
        plan="test-plan",
        override_action="recover-blocked",
        reason="operator marked finding fixed",
    )

    from arnold.pipelines.megaplan.types import CliError

    with pytest.raises(CliError) as exc_info:
        handle_override(root, args)

    assert exc_info.value.code == "blocked_recovery_not_resolved"
    assert exc_info.value.extra["blocker_ids"] == [blocker_id]
    assert exc_info.value.extra["requires_rerun"] is True
    blocker = exc_info.value.extra["unresolved_blockers"][0]
    assert blocker["resolution_state"] == "fixed"
    assert blocker["resolution_behavior"] == "rerun_required"
    assert blocker["suggested_commands"] == ["execute --retry-blocked-tasks"]
    state_data = json.loads((plan_dir / "state.json").read_text(encoding="utf-8"))
    assert state_data["current_state"] == "blocked"


def test_blocked_external_error_status_suggests_resume_not_blocker_recovery(
    tmp_path: Path,
) -> None:
    root, plan_dir, state = _setup_resolution_plan_dir(tmp_path)
    state["current_state"] = "blocked"
    state["resume_cursor"] = {"phase": "execute", "retry_strategy": "wait_and_retry"}
    state["latest_failure"] = {
        "kind": "external_error",
        "phase": "execute",
        "message": "phase 'execute' external dependency failure: [deepseek] rate_limit",
    }
    (plan_dir / "state.json").write_text(json.dumps(state), encoding="utf-8")
    _write_finalize_with_actions(plan_dir)

    from tests.conftest import make_fake_phase_result

    make_fake_phase_result(
        plan_dir,
        exit_kind="external_error",
        external_error=ExternalError(
            provider="deepseek",
            error_kind="rate_limit",
            message="429 Too Many Requests",
            status_code=429,
            retry_after_s=60.0,
        ),
    )

    payload = _build_status_payload(plan_dir, state)

    assert payload["suggested_recovery_commands"] == ["resume --plan test-plan"]
    assert "blocker_recovery" not in payload
    assert "quality_blockers" not in payload
    assert payload["external_error_recovery"]["recommended_action"] == "resume"


def test_override_recover_blocked_external_error_requires_resume(
    tmp_path: Path,
) -> None:
    root, plan_dir, state = _setup_resolution_plan_dir(tmp_path)
    state["current_state"] = "blocked"
    state["resume_cursor"] = {"phase": "execute", "retry_strategy": "wait_and_retry"}
    state["latest_failure"] = {"kind": "external_error", "phase": "execute"}
    (plan_dir / "state.json").write_text(json.dumps(state), encoding="utf-8")
    _write_finalize_with_actions(plan_dir)

    from tests.conftest import make_fake_phase_result

    make_fake_phase_result(
        plan_dir,
        exit_kind="external_error",
        external_error=ExternalError(
            provider="deepseek",
            error_kind="rate_limit",
            message="429 Too Many Requests",
        ),
    )

    args = argparse.Namespace(
        plan="test-plan",
        override_action="recover-blocked",
        reason="operator tried blocker recovery",
    )

    from arnold.pipelines.megaplan.types import CliError

    with pytest.raises(CliError) as exc_info:
        handle_override(root, args)

    assert exc_info.value.code == "external_error_resume_required"
    assert exc_info.value.extra["resume_command"] == "megaplan resume --plan test-plan"
    assert exc_info.value.extra["suggested_recovery_commands"] == [
        "megaplan resume --plan test-plan"
    ]
    assert exc_info.value.extra["phase_result_exit_kind"] == "external_error"
    state_data = json.loads((plan_dir / "state.json").read_text(encoding="utf-8"))
    assert state_data["current_state"] == "blocked"
    assert state_data["resume_cursor"] == state["resume_cursor"]
    assert state_data["latest_failure"] == state["latest_failure"]


def test_set_profile_preserves_external_error_resume_guidance_while_blocked(
    tmp_path: Path,
) -> None:
    root, plan_dir, state = _setup_resolution_plan_dir(tmp_path)
    state["current_state"] = "blocked"
    state["resume_cursor"] = {"phase": "execute", "retry_strategy": "wait_and_retry"}
    state["latest_failure"] = {"kind": "external_error", "phase": "execute"}
    (plan_dir / "state.json").write_text(json.dumps(state), encoding="utf-8")
    _write_finalize_with_actions(plan_dir)

    args = argparse.Namespace(
        plan="test-plan",
        override_action="set-profile",
        profile="all-codex",
        reason="switch provider before retry",
    )
    result = handle_override(root, args)

    assert result["success"] is True
    assert result["state"] == "blocked"

    state_data = json.loads((plan_dir / "state.json").read_text(encoding="utf-8"))
    assert state_data["resume_cursor"] == state["resume_cursor"]
    assert state_data["latest_failure"] == state["latest_failure"]
    assert state_data["config"]["profile"] == "all-codex"

    payload = _build_status_payload(plan_dir, state_data)
    assert payload["suggested_recovery_commands"] == ["resume --plan test-plan"]


def test_override_recover_blocked_requires_reason_in_main(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    root, plan_dir, state = _setup_resolution_plan_dir(tmp_path)
    monkeypatch.chdir(root)

    from arnold.pipelines.megaplan.cli import main

    code = main(["override", "recover-blocked", "--plan", "test-plan"])

    assert code != 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["error"] == "invalid_args"
    assert "recover-blocked requires --reason" in payload["message"]


def _build_parser_for_test() -> argparse.ArgumentParser:
    """Build a minimal parser for testing argument validation."""
    from arnold.pipelines.megaplan.cli import build_parser

    return build_parser()
