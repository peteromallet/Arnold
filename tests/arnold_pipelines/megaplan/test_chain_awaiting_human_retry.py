from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from arnold_pipelines.megaplan.auto import DriverOutcome
from arnold_pipelines.megaplan.chain import (
    _handle_outcome,
    _record_chain_last_state_after_plan_run,
    _reconcile_chain_from_ground_truth,
    _recover_stale_prerequisite_block,
    _sync_chain_last_state_from_plan,
    run_chain,
    save_chain_state,
)
from arnold_pipelines.megaplan.chain.spec import ChainSpec, ChainState, load_chain_state, load_spec
from arnold_pipelines.megaplan.planning.state import STATE_AWAITING_PR_MERGE

_DEFAULT_ACTIVE_STEP = object()


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
    active_step: object = _DEFAULT_ACTIVE_STEP,
) -> None:
    plan_dir = tmp_path / ".megaplan" / "plans" / plan_name
    plan_dir.mkdir(parents=True, exist_ok=True)
    serialized_active_step = json.dumps(
        {"phase": "execute"} if active_step is _DEFAULT_ACTIVE_STEP else active_step
    )
    (plan_dir / "state.json").write_text(
        (
            '{"name":"%s","current_state":"%s","latest_failure":null,'
            '"last_gate":{"recommendation":"PROCEED"},'
            '"active_step":%s,'
            '"meta":{"chain_policy":{"milestone_label":"m7"}}}'
        )
        % (plan_name, current_state, serialized_active_step),
        encoding="utf-8",
    )


def _sha256(path: Path) -> str:
    import hashlib

    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_completed_prerequisite_chain(tmp_path: Path) -> Path:
    prereq_path = tmp_path / "prereq.yaml"
    brief_path = tmp_path / "m1.md"
    proof_path = tmp_path / "proof.md"
    prereq_path.write_text(
        "milestones:\n  - label: m1\n    idea: m1.md\n",
        encoding="utf-8",
    )
    brief_path.write_text("# M1\n", encoding="utf-8")
    proof_path.write_text("# Proof\n", encoding="utf-8")
    save_chain_state(
        prereq_path,
        ChainState(
            current_milestone_index=1,
            completed=[{"label": "m1", "status": "done", "plan": "plan-m1"}],
            metadata={
                "chain_spec_path": str(prereq_path.resolve(strict=False)),
                "chain_spec_sha256": _sha256(prereq_path),
            },
        ),
    )
    prereq_path.with_name("completion-manifest.json").write_text(
        (
            "{\n"
            '  "schema": "arnold.megaplan.chain_completion_manifest.v1",\n'
            f'  "chain": {{"path": "prereq.yaml", "sha256": "{_sha256(prereq_path)}"}},\n'
            '  "milestones": [\n'
            "    {\n"
            '      "label": "m1",\n'
            f'      "brief_path": "m1.md", "brief_sha256": "{_sha256(brief_path)}",\n'
            '      "status": "done", "plan": "plan-m1",\n'
            f'      "proof_artifacts": [{{"path": "proof.md", "sha256": "{_sha256(proof_path)}"}}]\n'
            "    }\n"
            "  ]\n"
            "}\n"
        ),
        encoding="utf-8",
    )
    return prereq_path


def test_stale_prerequisite_block_revalidates_chain_preconditions_and_retries(
    tmp_path: Path,
) -> None:
    prereq_path = _write_completed_prerequisite_chain(tmp_path)
    spec_path = tmp_path / "dependent.yaml"
    spec_path.write_text("milestones: []\n", encoding="utf-8")
    spec = ChainSpec.from_dict(
        {
            "launch_preconditions": [
                {
                    "name": "prereq complete",
                    "kind": "chain_completed",
                    "chain": str(prereq_path.relative_to(tmp_path)),
                    "require_manifest": True,
                }
            ],
            "milestones": [],
        }
    )
    plan_dir = tmp_path / ".megaplan" / "plans" / "blocked-plan"
    plan_dir.mkdir(parents=True)
    (plan_dir / "finalize.json").write_text(
        (
            '{"tasks":[{"id":"T12","status":"blocked",'
            '"description":"conditional prerequisite task",'
            '"executor_notes":"Blocked by stale prerequisite completion manifest",'
            '"files_changed":["stale.py"],"commands_run":["pytest"],'
            '"evidence_files":["old.json"],"reviewer_verdict":"blocked"}]}'
        ),
        encoding="utf-8",
    )
    (plan_dir / "state.json").write_text(
        (
            '{"name":"blocked-plan","current_state":"blocked",'
            '"latest_failure":{"kind":"execution_blocked",'
            '"message":"execute reported prerequisite-blocked tasks: T12",'
            '"metadata":{"blocking_reasons":["T12 blocked by completion manifest"]}},'
            '"resume_cursor":{"phase":"execute"},'
            '"active_step":{"phase":"execute"},"meta":{}}'
        ),
        encoding="utf-8",
    )
    messages: list[str] = []

    recovered = _recover_stale_prerequisite_block(
        tmp_path,
        spec_path,
        spec,
        DriverOutcome(
            status="blocked",
            plan="blocked-plan",
            final_state="blocked",
            iterations=1,
            reason="recover-blocked requires every current blocker to be explicitly resolved",
        ),
        plan_dir=plan_dir,
        reason="execution_batch_11.json has no completed tasks",
        writer=messages.append,
    )

    assert recovered is True
    finalize = json.loads((plan_dir / "finalize.json").read_text(encoding="utf-8"))
    task = finalize["tasks"][0]
    assert task["status"] == "pending"
    assert task["executor_notes"] == ""
    assert task["files_changed"] == []
    state = json.loads((plan_dir / "state.json").read_text(encoding="utf-8"))
    assert state["current_state"] == "finalized"
    assert "latest_failure" not in state
    assert "resume_cursor" not in state
    assert "active_step" not in state
    assert state["meta"]["chain_precondition_revalidations"][0]["reset_task_ids"] == ["T12"]
    assert (plan_dir / "chain_precondition_revalidation.json").is_file()
    assert any("current launch preconditions now pass" in message for message in messages)


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


def test_handle_outcome_stops_unresolved_prerequisite_block_without_retry(
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
        robustness="extreme",
    )
    milestone = SimpleNamespace(label="m1", profile=None, robustness="extreme")
    state = ChainState()
    messages: list[str] = []

    decision = _handle_outcome(
        DriverOutcome(
            status="blocked",
            plan="m1-plan",
            final_state="blocked",
            iterations=1,
            reason=(
                "execute reported prerequisite-blocked tasks: T11 "
                "(M7 prerequisite is not satisfied)"
            ),
        ),
        spec=spec,
        writer=messages.append,
        milestone=milestone,
        state=state,
        root=tmp_path,
    )

    assert decision == "stop"
    assert state.retry_counts == {}
    assert any("unresolved explicit blocker" in message for message in messages)


def test_handle_outcome_stops_settled_prerequisite_gate_without_retry(
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
        robustness="extreme",
    )
    milestone = SimpleNamespace(label="m1", profile=None, robustness="extreme")
    state = ChainState()
    messages: list[str] = []

    decision = _handle_outcome(
        DriverOutcome(
            status="blocked",
            plan="m1-plan",
            final_state="blocked",
            iterations=1,
            reason=(
                "execute reported prerequisite-blocked tasks: T12 "
                "(Blocked by the settled SD2 launch gate)"
            ),
        ),
        spec=spec,
        writer=messages.append,
        milestone=milestone,
        state=state,
        root=tmp_path,
    )

    assert decision == "stop"
    assert state.retry_counts == {}
    assert any("unresolved explicit blocker" in message for message in messages)


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


def test_sync_chain_last_state_prefers_active_step_phase_over_terminal_projection(
    tmp_path: Path,
) -> None:
    spec_path = tmp_path / "chain.yaml"
    spec_path.write_text("milestones: []\n", encoding="utf-8")
    plan_dir = tmp_path / ".megaplan" / "plans" / "m7-plan"
    plan_dir.mkdir(parents=True)
    (plan_dir / "state.json").write_text(
        '{"name":"m7-plan","current_state":"finalized","active_step":{"phase":"execute"},"meta":{}}',
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

    assert synced.last_state == "execute"
    assert load_chain_state(spec_path).last_state == "execute"
    assert any("awaiting_human -> execute" in message for message in messages)


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


def test_record_chain_last_state_after_plan_run_keeps_execute_phase_visible(
    tmp_path: Path,
) -> None:
    spec_path = tmp_path / "chain.yaml"
    spec_path.write_text("milestones: []\n", encoding="utf-8")
    plan_dir = tmp_path / ".megaplan" / "plans" / "m7-plan"
    plan_dir.mkdir(parents=True)
    (plan_dir / "state.json").write_text(
        '{"name":"m7-plan","current_state":"finalized","latest_failure":null,'
        '"active_step":{"phase":"execute"}}',
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
            status="blocked",
            plan="m7-plan",
            final_state="blocked",
            iterations=1,
            reason="execute worker stopped",
        ),
        writer=messages.append,
    )

    assert synced.last_state == "execute"
    assert load_chain_state(spec_path).last_state == "execute"
    assert any("blocked -> execute" in message for message in messages)


def test_run_chain_syncs_last_state_after_each_child_phase(tmp_path: Path) -> None:
    spec_path = _write_chain_spec(tmp_path)
    _write_plan_state(tmp_path, current_state="initialized", active_step=None)
    messages: list[str] = []

    def fake_drive(
        root: Path,
        spec_path_arg: Path,
        plan_name: str,
        spec: ChainSpec,
        *,
        on_phase_complete,
        writer,
    ) -> DriverOutcome:
        assert spec_path_arg == spec_path
        _write_plan_state(
            root,
            plan_name=plan_name,
            current_state="planned",
            active_step=None,
        )
        on_phase_complete("plan", 0, "", "")
        return DriverOutcome(
            status="stalled",
            plan=plan_name,
            final_state="stalled",
            iterations=1,
            reason="stop after phase callback",
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
        patch("arnold_pipelines.megaplan.chain._pr_state", return_value="open"),
        patch("arnold_pipelines.megaplan.chain._ensure_milestone_pr", return_value=122),
        patch("arnold_pipelines.megaplan.chain._commit_and_push_phase"),
        patch("arnold_pipelines.megaplan.chain._init_plan", return_value="m7-plan"),
        patch("arnold_pipelines.megaplan.chain._write_chain_policy_into_plan_meta"),
        patch("arnold_pipelines.megaplan.chain._attach_chain_anchors_to_plan"),
        patch(
            "arnold_pipelines.megaplan.chain._drive_plan_with_blocked_execute_recovery",
            fake_drive,
        ),
    ):
        result = run_chain(
            spec_path,
            tmp_path,
            writer=messages.append,
            require_anchor_override=False,
            missing_anchor_ack_override="unit test uses a minimal chain spec",
        )

    assert result["status"] == "stopped"
    saved = load_chain_state(spec_path)
    assert saved.last_state == "planned"


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


def test_reconcile_reviewed_finalized_plan_waits_for_open_pr_merge(
    tmp_path: Path,
) -> None:
    spec_path = _write_chain_spec(tmp_path)
    spec = load_spec(spec_path)
    plan_dir = tmp_path / ".megaplan" / "plans" / "m7-plan"
    plan_dir.mkdir(parents=True, exist_ok=True)
    (plan_dir / "state.json").write_text(
        json.dumps(
            {
                "name": "m7-plan",
                "current_state": "finalized",
                "latest_failure": None,
                "active_step": None,
                "meta": {"chain_policy": {"milestone_label": "m7"}},
                "history": [
                    {"step": "execute", "result": "blocked"},
                    {"step": "review", "result": "success"},
                ],
            }
        ),
        encoding="utf-8",
    )
    state = ChainState(
        current_milestone_index=0,
        current_plan_name="m7-plan",
        last_state="finalized",
        pr_number=122,
        pr_state="open",
    )

    with patch("arnold_pipelines.megaplan.chain._pr_state", return_value="open"):
        reconciled = _reconcile_chain_from_ground_truth(
            tmp_path,
            spec_path,
            spec,
            state,
            writer=lambda _message: None,
            push_enabled=True,
        )

    saved = load_chain_state(spec_path)
    assert reconciled.current_plan_name == "m7-plan"
    assert reconciled.current_milestone_index == 0
    assert reconciled.completed == []
    assert reconciled.last_state == STATE_AWAITING_PR_MERGE
    assert saved.last_state == STATE_AWAITING_PR_MERGE


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


def test_reconcile_clears_stale_active_state_when_completed_milestone_is_terminal(
    tmp_path: Path,
) -> None:
    spec_path = _write_chain_spec(tmp_path)
    spec = load_spec(spec_path)
    _write_plan_state(tmp_path, current_state="blocked")
    state = ChainState(
        current_milestone_index=0,
        current_plan_name="m7-plan",
        last_state="blocked",
        pr_number=122,
        pr_state="merged",
        completed=[
            {
                "label": "m7",
                "plan": "m7-plan",
                "status": "done",
                "pr_number": 122,
                "pr_state": "merged",
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

    saved = load_chain_state(spec_path)
    assert reconciled.current_milestone_index == 1
    assert reconciled.current_plan_name is None
    assert reconciled.pr_number is None
    assert reconciled.pr_state is None
    assert reconciled.last_state == "done"
    assert saved.current_milestone_index == 1
    assert saved.current_plan_name is None
    assert saved.pr_number is None
    assert saved.pr_state is None
    assert saved.last_state == "done"


def test_reconcile_rejects_terminal_merged_pr_plan_without_completion_evidence(
    tmp_path: Path,
) -> None:
    spec_path = _write_chain_spec(tmp_path)
    spec = load_spec(spec_path)
    _write_plan_state(tmp_path, current_state="done")
    state = ChainState(
        current_milestone_index=0,
        current_plan_name="m7-plan",
        last_state="initialized",
        pr_number=122,
        pr_state="open",
        completed=[],
    )

    messages: list[str] = []
    with patch("arnold_pipelines.megaplan.chain._pr_state", return_value="merged"):
        reconciled = _reconcile_chain_from_ground_truth(
            tmp_path,
            spec_path,
            spec,
            state,
            writer=messages.append,
            push_enabled=True,
        )

    saved = load_chain_state(spec_path)
    assert reconciled.current_milestone_index == 0
    assert reconciled.current_plan_name == "m7-plan"
    assert reconciled.last_state == "authority_divergence"
    assert reconciled.completed == []
    assert saved.current_milestone_index == 0
    assert saved.current_plan_name == "m7-plan"
    assert saved.last_state == "authority_divergence"
    assert saved.completed == reconciled.completed
    assert any("reconciliation completion guard blocked m7" in msg for msg in messages)
    assert not saved.has_milestone_evidence("m7")


def test_reconcile_rejects_terminal_local_plan_without_completion_evidence(
    tmp_path: Path,
) -> None:
    spec_path = _write_chain_spec(tmp_path)
    spec = load_spec(spec_path)
    _write_plan_state(tmp_path, current_state="done")
    state = ChainState(
        current_milestone_index=0,
        current_plan_name="m7-plan",
        last_state="initialized",
        completed=[],
    )

    messages: list[str] = []
    reconciled = _reconcile_chain_from_ground_truth(
        tmp_path,
        spec_path,
        spec,
        state,
        writer=messages.append,
        push_enabled=False,
    )

    saved = load_chain_state(spec_path)
    assert reconciled.current_milestone_index == 0
    assert reconciled.current_plan_name == "m7-plan"
    assert reconciled.last_state == "authority_divergence"
    assert reconciled.completed == []
    assert saved.current_milestone_index == 0
    assert saved.current_plan_name == "m7-plan"
    assert saved.last_state == "authority_divergence"
    assert saved.completed == reconciled.completed
    assert any("reconciliation completion guard blocked m7" in msg for msg in messages)
    assert not saved.has_milestone_evidence("m7")


def test_reconcile_rewinds_branch_completion_missing_pr_context(
    tmp_path: Path,
) -> None:
    spec_path = _write_chain_spec(tmp_path)
    spec = load_spec(spec_path)
    _write_plan_state(tmp_path, current_state="done")
    state = ChainState(
        current_milestone_index=1,
        last_state="done",
        completed=[
            {
                "label": "m7",
                "plan": "m7-plan",
                "status": "done",
                "pr_number": None,
                "pr_state": None,
            }
        ],
    )

    messages: list[str] = []
    reconciled = _reconcile_chain_from_ground_truth(
        tmp_path,
        spec_path,
        spec,
        state,
        writer=messages.append,
        push_enabled=True,
    )

    saved = load_chain_state(spec_path)
    assert reconciled.current_milestone_index == 0
    assert reconciled.current_plan_name == "m7-plan"
    assert reconciled.pr_number is None
    assert reconciled.pr_state is None
    assert reconciled.last_state == "authority_divergence"
    assert reconciled.completed == []
    assert saved.current_milestone_index == 0
    assert saved.current_plan_name == "m7-plan"
    assert saved.last_state == "authority_divergence"
    assert saved.completed == []
    assert any("missing PR context" in message for message in messages)


def test_reconcile_clears_terminal_last_state_when_active_plan_state_is_unavailable(
    tmp_path: Path,
) -> None:
    spec_path = _write_chain_spec(tmp_path)
    spec = load_spec(spec_path)
    state = ChainState(
        current_milestone_index=0,
        current_plan_name="m7-plan",
        last_state="done",
        completed=[],
    )

    messages: list[str] = []
    reconciled = _reconcile_chain_from_ground_truth(
        tmp_path,
        spec_path,
        spec,
        state,
        writer=messages.append,
        push_enabled=False,
    )

    saved = load_chain_state(spec_path)
    assert reconciled.current_plan_name == "m7-plan"
    assert reconciled.current_milestone_index == 0
    assert reconciled.last_state == "unknown"
    assert saved.last_state == "unknown"
    assert saved.metadata["ground_truth_reconciliation"]["current_state"] is None
    assert any("cleared stale terminal last_state" in message for message in messages)


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
    assert saved.last_state == "execute"
    assert saved.pr_state == "open"


def test_run_chain_does_not_replay_durably_blocked_plan_on_restart(
    tmp_path: Path,
) -> None:
    spec_path = _write_chain_spec(tmp_path)
    _write_plan_state(tmp_path, current_state="blocked", active_step=None)
    save_chain_state(
        spec_path,
        ChainState(
            current_milestone_index=0,
            current_plan_name="m7-plan",
            last_state="blocked",
            pr_number=122,
            pr_state="open",
        ),
    )

    messages: list[str] = []
    with (
        patch("arnold_pipelines.megaplan.chain._require_git_worktree_root"),
        patch("arnold_pipelines.megaplan.chain._pr_state", return_value="open"),
        patch("arnold_pipelines.megaplan.chain._plan_state", return_value="blocked"),
        patch(
            "arnold_pipelines.megaplan.chain._drive_plan_with_blocked_execute_recovery"
        ) as drive,
    ):
        result = run_chain(
            spec_path,
            tmp_path,
            writer=messages.append,
            require_anchor_override=False,
            missing_anchor_ack_override="unit test uses a minimal chain spec",
        )

    drive.assert_not_called()
    assert result["status"] == "stopped"
    assert result["reason"] == "milestone m7 remains blocked"
    assert any("already durably blocked" in message for message in messages)


def test_no_push_reconciliation_never_fabricates_open_pr_as_merged(
    tmp_path: Path,
) -> None:
    spec_path = _write_chain_spec(tmp_path)
    _write_plan_state(tmp_path, current_state="done", active_step=None)
    state = ChainState(
        current_milestone_index=0,
        current_plan_name="m7-plan",
        last_state=STATE_AWAITING_PR_MERGE,
        pr_number=255,
        pr_state="open",
    )
    save_chain_state(spec_path, state)

    captured: list[dict[str, object]] = []

    def append_completed(_root, chain_state, record, **_kwargs):
        captured.append(record)
        chain_state.completed.append(record)
        return True, "verified local publication"

    with (
        patch("arnold_pipelines.megaplan.chain._require_git_worktree_root"),
        patch(
            "arnold_pipelines.megaplan.chain._reconcile_chain_from_ground_truth",
            return_value=state,
        ),
        patch("arnold_pipelines.megaplan.chain._current_git_head", return_value="a" * 40),
        patch(
            "arnold_pipelines.megaplan.chain._run_milestone_validations_blocking",
            return_value=None,
        ),
        patch(
            "arnold_pipelines.megaplan.chain._append_completed_with_guard",
            side_effect=append_completed,
        ),
        patch("arnold_pipelines.megaplan.chain._mark_plan_completed_by_chain"),
        patch("arnold_pipelines.megaplan.chain._emit_milestone_completion_evidence"),
        patch("arnold_pipelines.megaplan.chain._emit_chain_complete_evidence"),
        patch(
            "arnold_pipelines.megaplan.chain._finalize_validation_artifacts_after_done_append",
            return_value=None,
        ),
    ):
        result = run_chain(
            spec_path,
            tmp_path,
            no_push=True,
            no_git_refresh=True,
            one=True,
            require_anchor_override=False,
            missing_anchor_ack_override="unit test uses a minimal chain spec",
        )

    assert result["status"] == "done"
    assert captured == [
        {
            "label": "m7",
            "plan": "m7-plan",
            "status": "done",
            "pr_number": None,
            "pr_state": None,
            "local_commit_sha": "a" * 40,
            "publication_evidence": "local_no_push_reconciliation",
        }
    ]
    saved = load_chain_state(spec_path)
    assert saved.metadata["local_pr_reconciliation"] == {
        "milestone": "m7",
        "pr_number": 255,
        "observed_pr_state": "open",
        "local_commit_sha": "a" * 40,
    }


def test_one_stops_after_ground_truth_reconciles_local_milestone(
    tmp_path: Path,
) -> None:
    spec_path = _write_chain_spec(tmp_path)
    state = ChainState(current_milestone_index=0, completed=[])
    state_after = ChainState(
        current_milestone_index=1,
        completed=[
            {
                "label": "m7",
                "plan": "m7-plan",
                "status": "done",
                "pr_number": None,
                "pr_state": None,
                "local_commit_sha": "b" * 40,
            }
        ],
    )
    save_chain_state(spec_path, state)

    with (
        patch("arnold_pipelines.megaplan.chain._require_git_worktree_root"),
        patch(
            "arnold_pipelines.megaplan.chain._reconcile_chain_from_ground_truth",
            return_value=state_after,
        ),
        patch("arnold_pipelines.megaplan.chain._drive_plan_with_blocked_execute_recovery") as drive,
    ):
        result = run_chain(
            spec_path,
            tmp_path,
            no_push=True,
            no_git_refresh=True,
            one=True,
            require_anchor_override=False,
            missing_anchor_ack_override="unit test uses a minimal chain spec",
        )

    drive.assert_not_called()
    assert result["status"] == "done"
    assert result["reason"] == "one-milestone limit reached during ground-truth reconciliation"


def test_run_chain_rearms_fresh_session_execute_block_on_restart(
    tmp_path: Path,
) -> None:
    spec_path = _write_chain_spec(tmp_path)
    _write_plan_state(
        tmp_path,
        current_state="blocked",
        active_step=None,
    )
    plan_dir = tmp_path / ".megaplan" / "plans" / "m7-plan"
    state_payload = json.loads((plan_dir / "state.json").read_text(encoding="utf-8"))
    state_payload["latest_failure"] = {
        "kind": "execution_blocked",
        "message": "execute blocked by quality gates",
        "phase": "execute",
        "state": "blocked",
    }
    state_payload["resume_cursor"] = {
        "phase": "execute",
        "retry_strategy": "fresh_session",
    }
    (plan_dir / "state.json").write_text(
        json.dumps(state_payload) + "\n",
        encoding="utf-8",
    )
    save_chain_state(
        spec_path,
        ChainState(
            current_milestone_index=0,
            current_plan_name="m7-plan",
            last_state="blocked",
            pr_number=122,
            pr_state="open",
        ),
    )

    messages: list[str] = []
    with (
        patch("arnold_pipelines.megaplan.chain._require_git_worktree_root"),
        patch("arnold_pipelines.megaplan.chain._pr_state", return_value="open"),
        patch("arnold_pipelines.megaplan.chain._plan_state", return_value="blocked"),
        patch(
            "arnold_pipelines.megaplan.chain._checkout_milestone_branch",
            return_value="origin/main",
        ),
        patch("arnold_pipelines.megaplan.chain._capture_sync_state"),
        patch(
            "arnold_pipelines.megaplan.chain._drive_plan_with_blocked_execute_recovery",
            return_value=DriverOutcome(
                status="done",
                plan="m7-plan",
                final_state="done",
                iterations=1,
                reason="execute reran after fresh-session reset",
            ),
        ) as drive,
    ):
        result = run_chain(
            spec_path,
            tmp_path,
            writer=messages.append,
            require_anchor_override=False,
            missing_anchor_ack_override="unit test uses a minimal chain spec",
        )

    drive.assert_called_once()
    updated = json.loads((plan_dir / "state.json").read_text(encoding="utf-8"))
    assert updated["current_state"] == "finalized"
    assert "latest_failure" not in updated
    assert "resume_cursor" not in updated
    assert result["status"] != "stopped"
    assert any("fresh-session retry" in message for message in messages)


def test_run_chain_rearms_stale_incomplete_execute_cursor_mismatch_on_restart(
    tmp_path: Path,
) -> None:
    """Chain admission must not stop before the corrected auto driver runs."""

    spec_path = _write_chain_spec(tmp_path)
    _write_plan_state(tmp_path, current_state="blocked", active_step=None)
    plan_dir = tmp_path / ".megaplan" / "plans" / "m7-plan"
    state_payload = json.loads((plan_dir / "state.json").read_text(encoding="utf-8"))
    state_payload["history"] = [
        {"step": "execute", "result": "blocked", "message": "T8 and T11 pending"}
    ]
    state_payload["latest_failure"] = {
        "kind": "workflow_cursor_mismatch",
        "message": "workflow cursor from last_step expects one of [review] but control projection offered [execute]",
        "phase": "execute",
        "state": "blocked",
        "metadata": {"observed_phase_source": "last_step"},
    }
    state_payload["resume_cursor"] = {
        "phase": "execute",
        "retry_strategy": "repair_workflow_projection",
    }
    (plan_dir / "state.json").write_text(json.dumps(state_payload) + "\n", encoding="utf-8")
    save_chain_state(
        spec_path,
        ChainState(
            current_milestone_index=0,
            current_plan_name="m7-plan",
            last_state="blocked",
            pr_number=122,
            pr_state="open",
        ),
    )

    messages: list[str] = []
    with (
        patch("arnold_pipelines.megaplan.chain._require_git_worktree_root"),
        patch("arnold_pipelines.megaplan.chain._pr_state", return_value="open"),
        patch("arnold_pipelines.megaplan.chain._plan_state", return_value="blocked"),
        patch(
            "arnold_pipelines.megaplan.chain._checkout_milestone_branch",
            return_value="origin/main",
        ),
        patch("arnold_pipelines.megaplan.chain._capture_sync_state"),
        patch(
            "arnold_pipelines.megaplan.chain._drive_plan_with_blocked_execute_recovery",
            return_value=DriverOutcome(
                status="done",
                plan="m7-plan",
                final_state="done",
                iterations=1,
                reason="pending execute work resumed",
            ),
        ) as drive,
    ):
        result = run_chain(
            spec_path,
            tmp_path,
            writer=messages.append,
            require_anchor_override=False,
            missing_anchor_ack_override="unit test uses a minimal chain spec",
        )

    drive.assert_called_once()
    updated = json.loads((plan_dir / "state.json").read_text(encoding="utf-8"))
    assert updated["current_state"] == "finalized"
    assert "latest_failure" not in updated
    assert "resume_cursor" not in updated
    assert updated["meta"]["workflow_cursor_recoveries"][-1]["history_result"] == "blocked"
    assert result["status"] != "stopped"
    assert any("stale incomplete-execute workflow cursor mismatch" in message for message in messages)


def test_chain_preserves_genuine_workflow_cursor_mismatch(
    tmp_path: Path,
) -> None:
    """Only the invalidated incomplete-history shape is reopened."""

    from arnold_pipelines.megaplan.chain import _rearm_stale_incomplete_execute_cursor_mismatch

    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    payload = {
        "current_state": "blocked",
        "history": [{"step": "execute", "result": "blocked"}],
        "latest_failure": {
            "kind": "workflow_cursor_mismatch",
            "message": "workflow cursor from active_step expects one of [review] but control projection offered [execute]",
            "phase": "execute",
            "metadata": {"observed_phase_source": "active_step"},
        },
        "resume_cursor": {"phase": "execute", "retry_strategy": "repair_workflow_projection"},
    }
    (plan_dir / "state.json").write_text(json.dumps(payload), encoding="utf-8")

    assert _rearm_stale_incomplete_execute_cursor_mismatch(plan_dir, writer=lambda _message: None) is False
    assert json.loads((plan_dir / "state.json").read_text(encoding="utf-8")) == payload
