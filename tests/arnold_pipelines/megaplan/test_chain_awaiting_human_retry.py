from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from arnold_pipelines.megaplan.auto import DriverOutcome
from arnold_pipelines.megaplan.chain import (
    _handle_outcome,
    _record_chain_last_state_after_plan_run,
    _reconcile_chain_from_ground_truth,
    _sync_chain_last_state_from_plan,
    run_chain,
    save_chain_state,
)
from arnold_pipelines.megaplan.chain.spec import ChainState, load_chain_state, load_spec
from arnold_pipelines.megaplan.planning.state import STATE_AWAITING_PR_MERGE


def _write_chain_spec(tmp_path: Path, *, merge_policy: str = "review") -> Path:
    spec_path = tmp_path / "chain.yaml"
    (tmp_path / "idea.md").write_text("ship m7\n", encoding="utf-8")
    spec_path.write_text(
        "\n".join(
            [
                "base_branch: main",
                f"merge_policy: {merge_policy}",
                "milestones:",
                "  - label: m7",
                "    idea: idea.md",
                "    branch: feature/m7",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return spec_path


def _write_plan_state(
    tmp_path: Path,
    *,
    plan_name: str = "m7-plan",
    current_state: str = "finalized",
) -> None:
    plan_dir = tmp_path / ".megaplan" / "plans" / plan_name
    plan_dir.mkdir(parents=True, exist_ok=True)
    (plan_dir / "state.json").write_text(
        (
            '{"name":"%s","current_state":"%s","latest_failure":null,'
            '"last_gate":{"recommendation":"PROCEED"},'
            '"active_step":{"phase":"execute"},'
            '"meta":{"chain_policy":{"milestone_label":"m7"}}}'
        )
        % (plan_name, current_state),
        encoding="utf-8",
    )


def test_handle_outcome_retries_stale_awaiting_human_with_satisfied_resolutions(
    tmp_path: Path,
) -> None:
    plan_dir = tmp_path / ".megaplan" / "plans" / "stale-plan"
    plan_dir.mkdir(parents=True)
    (plan_dir / "state.json").write_text(
        (
            '{"name":"stale-plan","current_state":"awaiting_human","meta":{},'
            '"resume_cursor":{"phase":"execute"}}'
        ),
        encoding="utf-8",
    )
    (plan_dir / "finalize.json").write_text(
        '{"user_actions":[{"id":"ua-1","phase":"before_execute"}]}',
        encoding="utf-8",
    )
    (plan_dir / "user_action_resolutions.json").write_text(
        '{"ua-1":{"action_id":"ua-1","state":"satisfied","created_at":"2026-06-28T00:00:00Z","created_by":"test"}}',
        encoding="utf-8",
    )

    spec = SimpleNamespace(
        on_failure_policy=SimpleNamespace(
            retry="retry_milestone",
            escalate="bump_profile",
            abort="stop_chain",
        ),
        on_escalate_policy=SimpleNamespace(
            retry="retry_milestone",
            escalate="bump_profile",
            abort="stop_chain",
        ),
        robustness="standard",
    )
    milestone = SimpleNamespace(label="m7", profile=None, robustness=None)
    state = ChainState()

    decision = _handle_outcome(
        DriverOutcome(
            status="awaiting_human",
            plan="stale-plan",
            final_state="awaiting_human",
            iterations=1,
            reason="stale blocked gate",
        ),
        spec=spec,
        writer=lambda _message: None,
        milestone=milestone,
        state=state,
        root=tmp_path,
    )

    assert decision == "retry"
    assert state.retry_counts == {"m7": 1}


def test_handle_outcome_retries_finalized_plan_when_execute_finds_satisfied_gate(
    tmp_path: Path,
) -> None:
    plan_dir = tmp_path / ".megaplan" / "plans" / "finalized-plan"
    plan_dir.mkdir(parents=True)
    (plan_dir / "state.json").write_text(
        (
            '{"name":"finalized-plan","current_state":"finalized","meta":{},'
            '"resume_cursor":{"phase":"execute"}}'
        ),
        encoding="utf-8",
    )
    (plan_dir / "finalize.json").write_text(
        '{"user_actions":[{"id":"ua-1","phase":"before_execute"}]}',
        encoding="utf-8",
    )
    (plan_dir / "user_action_resolutions.json").write_text(
        (
            '{"ua-1":{"action_id":"ua-1","state":"satisfied",'
            '"applies_to_task_ids":["m7-06-runtime-deletion-target-purge"],'
            '"created_at":"2026-06-28T00:00:00Z","created_by":"test"}}'
        ),
        encoding="utf-8",
    )

    spec = SimpleNamespace(
        on_failure_policy=SimpleNamespace(
            retry="retry_milestone",
            escalate="bump_profile",
            abort="stop_chain",
        ),
        on_escalate_policy=SimpleNamespace(
            retry="retry_milestone",
            escalate="bump_profile",
            abort="stop_chain",
        ),
        robustness="standard",
    )
    milestone = SimpleNamespace(label="m7", profile=None, robustness=None)
    state = ChainState()

    decision = _handle_outcome(
        DriverOutcome(
            status="awaiting_human",
            plan="finalized-plan",
            final_state="awaiting_human",
            iterations=1,
            reason="execute found a satisfied prerequisite gate",
        ),
        spec=spec,
        writer=lambda _message: None,
        milestone=milestone,
        state=state,
        root=tmp_path,
    )

    assert decision == "retry"
    assert state.retry_counts == {"m7": 1}


def test_handle_outcome_stops_finalized_plan_before_pr_progression(
    tmp_path: Path,
) -> None:
    spec = SimpleNamespace(
        on_failure_policy=SimpleNamespace(
            retry="retry_milestone",
            escalate="bump_profile",
            abort="stop_chain",
        ),
        on_escalate_policy=SimpleNamespace(
            retry="retry_milestone",
            escalate="bump_profile",
            abort="stop_chain",
        ),
        robustness="standard",
    )
    milestone = SimpleNamespace(label="m7", profile=None, robustness=None)
    state = ChainState()
    messages: list[str] = []

    decision = _handle_outcome(
        DriverOutcome(
            status="finalized",
            plan="finalized-plan",
            final_state="finalized",
            iterations=1,
            reason="stopped after finalize",
        ),
        spec=spec,
        writer=messages.append,
        milestone=milestone,
        state=state,
        root=tmp_path,
    )

    assert decision == "stop"
    assert state.retry_counts == {}
    assert any("finalized but not executed" in message for message in messages)


def test_sync_chain_last_state_refreshes_from_current_plan_state(tmp_path: Path) -> None:
    spec_path = tmp_path / "chain.yaml"
    spec_path.write_text("milestones: []\n", encoding="utf-8")
    plan_dir = tmp_path / ".megaplan" / "plans" / "m7-plan"
    plan_dir.mkdir(parents=True)
    (plan_dir / "state.json").write_text(
        '{"name":"m7-plan","current_state":"finalized","meta":{}}',
        encoding="utf-8",
    )
    messages: list[str] = []
    state = ChainState(
        current_milestone_index=6,
        current_plan_name="m7-plan",
        last_state="awaiting_human",
    )

    synced = _sync_chain_last_state_from_plan(
        tmp_path,
        spec_path,
        state,
        writer=messages.append,
    )

    assert synced.last_state == "finalized"
    assert load_chain_state(spec_path).last_state == "finalized"
    assert any("awaiting_human -> finalized" in message for message in messages)


def test_record_chain_last_state_after_plan_run_prefers_live_plan_state(
    tmp_path: Path,
) -> None:
    spec_path = tmp_path / "chain.yaml"
    spec_path.write_text("milestones: []\n", encoding="utf-8")
    plan_dir = tmp_path / ".megaplan" / "plans" / "m7-plan"
    plan_dir.mkdir(parents=True)
    (plan_dir / "state.json").write_text(
        '{"name":"m7-plan","current_state":"finalized","latest_failure":null}',
        encoding="utf-8",
    )
    messages: list[str] = []
    state = ChainState(
        current_milestone_index=6,
        current_plan_name="m7-plan",
        last_state="awaiting_human",
    )

    synced = _record_chain_last_state_after_plan_run(
        tmp_path,
        spec_path,
        state,
        DriverOutcome(
            status="awaiting_human",
            plan="m7-plan",
            final_state="awaiting_human",
            iterations=1,
            reason="stale chain halt",
        ),
        writer=messages.append,
    )

    assert synced.last_state == "finalized"
    assert load_chain_state(spec_path).last_state == "finalized"
    assert any("awaiting_human -> finalized" in message for message in messages)


def test_reconcile_leaves_finalized_open_pr_for_execute_resume(
    tmp_path: Path,
) -> None:
    spec_path = _write_chain_spec(tmp_path)
    spec = load_spec(spec_path)
    _write_plan_state(tmp_path, current_state="finalized")
    messages: list[str] = []
    state = ChainState(
        current_milestone_index=0,
        current_plan_name="m7-plan",
        last_state="awaiting_human",
        pr_number=122,
        pr_state="closed",
    )

    with patch("arnold_pipelines.megaplan.chain._pr_state", return_value="open"):
        reconciled = _reconcile_chain_from_ground_truth(
            tmp_path,
            spec_path,
            spec,
            state,
            writer=messages.append,
            push_enabled=True,
        )

    saved = load_chain_state(spec_path)
    assert reconciled.last_state == "finalized"
    assert reconciled.pr_state == "open"
    assert saved.last_state == "finalized"
    assert saved.pr_state == "open"
    audit = saved.metadata["ground_truth_reconciliation"]
    assert audit["current_state"] == "finalized"
    assert audit["pr_number"] == 122
    assert audit["pr_state"] == "open"
    assert not any("waiting for merge" in message for message in messages)


def test_reconcile_revalidates_completed_prs_from_live_github(
    tmp_path: Path,
) -> None:
    spec_path = _write_chain_spec(tmp_path)
    spec = load_spec(spec_path)
    _write_plan_state(tmp_path, current_state="done")
    state = ChainState(
        current_milestone_index=1,
        completed=[
            {
                "label": "m7",
                "plan": "m7-plan",
                "status": "done",
                "pr_number": 122,
                "pr_state": "open",
            }
        ],
    )

    with patch("arnold_pipelines.megaplan.chain._pr_state", return_value="merged"):
        reconciled = _reconcile_chain_from_ground_truth(
            tmp_path,
            spec_path,
            spec,
            state,
            writer=lambda _message: None,
            push_enabled=True,
        )

    assert reconciled.current_milestone_index == 1
    assert reconciled.completed[0]["pr_state"] == "merged"
    assert load_chain_state(spec_path).completed[0]["pr_state"] == "merged"


def test_run_chain_resumes_when_reconciled_finalized_pr_is_open(
    tmp_path: Path,
) -> None:
    spec_path = _write_chain_spec(tmp_path)
    _write_plan_state(tmp_path, current_state="finalized")
    save_chain_state(
        spec_path,
        ChainState(
            current_milestone_index=0,
            current_plan_name="m7-plan",
            last_state="finalized",
            pr_number=122,
            pr_state="open",
        ),
    )

    with (
        patch("arnold_pipelines.megaplan.chain._require_git_worktree_root"),
        patch("arnold_pipelines.megaplan.chain._dirty_worktree_paths", return_value=[]),
        patch(
            "arnold_pipelines.megaplan.chain._refresh_base_branch",
            lambda *args, **kwargs: None,
        ),
        patch(
            "arnold_pipelines.megaplan.chain._checkout_milestone_branch",
            lambda *args, **kwargs: None,
        ),
        patch("arnold_pipelines.megaplan.chain._capture_sync_state"),
        patch("arnold_pipelines.megaplan.chain._plan_state", return_value="finalized"),
        patch("arnold_pipelines.megaplan.chain._pr_state", return_value="open"),
        patch(
            "arnold_pipelines.megaplan.chain._drive_plan_with_blocked_execute_recovery",
            return_value=DriverOutcome(
                status="awaiting_human",
                plan="m7-plan",
                final_state="awaiting_human",
                iterations=1,
                reason="test stop after resume",
            ),
        ) as drive,
    ):
        result = run_chain(
            spec_path,
            tmp_path,
            writer=lambda _message: None,
            require_anchor_override=False,
            missing_anchor_ack_override="unit test uses a minimal chain spec",
        )

    drive.assert_called_once()
    assert result["status"] == "stopped"
    saved = load_chain_state(spec_path)
    assert saved.last_state == "finalized"
    assert saved.pr_state == "open"
