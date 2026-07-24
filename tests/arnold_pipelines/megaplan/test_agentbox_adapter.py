from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Callable

import pytest

from arnold.runtime.durable_ops import OperationState, ResourceType

from agentbox.config import AgentBoxConfig
from agentbox.operations import create_agentbox_operation, load_agentbox_operation, open_operation_store, update_agentbox_operation
from agentbox.repos import register_repo
from agentbox.run_dirs import read_metadata, run_dir_paths
from agentbox.tmux import SessionStatus

from arnold_pipelines.megaplan.agentbox_adapter import (
    MEGAPLAN_CHAIN_OPERATION_TYPE,
    MegaplanChainHandler,
    MegaplanChainLaunchError,
    _record_completion_dm,
)
from arnold_pipelines.megaplan.chain.spec import ChainState, load_chain_state, save_chain_state


def test_megaplan_chain_launch_validates_relative_spec_before_tmux(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = _config_with_repo(tmp_path, "app")
    repo = config.repos_root / "app"
    _write_valid_chain(repo)
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "add chain spec")
    calls: list[dict[str, object]] = []

    def fake_start_session(operation_id, command, *, cwd=None, run_paths=None):
        calls.append(
            {
                "operation_id": operation_id,
                "command": command,
                "cwd": cwd,
                "stdout": run_paths.stdout_path,
            }
        )
        return "agentbox-chain-1"

    monkeypatch.setattr("agentbox.host.start_session", fake_start_session)
    monkeypatch.setattr(
        "agentbox.host.inspect_session",
        lambda name: SessionStatus(name, "running", True),
    )
    monkeypatch.setattr(
        "arnold_pipelines.megaplan.agentbox_adapter.inspect_session",
        lambda name: SessionStatus(name, "running", True),
    )

    result = MegaplanChainHandler().launch(
        config,
        "chain-1",
        repo_name="app",
        spec_path=".megaplan/initiatives/epic/chain.yaml",
    )

    run = load_agentbox_operation(config, "chain-1")
    resources = open_operation_store(config).list_typed_resources("chain-1")
    metadata = read_metadata(result.host_result.run_paths)
    events = _events(result.host_result.run_paths.events_path)

    assert run.operation_type == MEGAPLAN_CHAIN_OPERATION_TYPE
    assert run.state is OperationState.RUNNING
    assert run.metadata["launch_intent"] == "megaplan_chain"
    assert run.metadata["validation"]["status"] == "passed"
    assert result.resolved_spec_path == result.project_root / ".megaplan/initiatives/epic/chain.yaml"
    assert result.resolved_spec_path.is_absolute()
    assert calls == [
        {
            "operation_id": "chain-1",
            "command": (
                "python",
                "-m",
                "arnold_pipelines.megaplan",
                "chain",
                "start",
                "--spec",
                str(result.resolved_spec_path),
                "--project-dir",
                str(result.project_root),
            ),
            "cwd": result.project_root,
            "stdout": result.host_result.run_paths.stdout_path,
        }
    ]
    assert metadata["resolved_spec_path"] == str(result.resolved_spec_path)
    assert "megaplan_chain.validation_passed" in [event["event_type"] for event in events]
    assert {resource.resource_type for resource in resources} == {
        ResourceType.GIT_WORKTREE,
        ResourceType.LOG,
        ResourceType.PROCESS_SESSION,
    }
    assert sum(resource.resource_type is ResourceType.PROCESS_SESSION for resource in resources) == 1


@pytest.mark.parametrize(
    ("case_name", "arrange", "spec_path", "expected_kind"),
    [
        (
            "missing_spec",
            lambda repo: None,
            ".megaplan/initiatives/epic/missing.yaml",
            "invalid_spec",
        ),
        (
            "invalid_yaml",
            lambda repo: _write_raw_chain(repo, "milestones: [\n"),
            ".megaplan/initiatives/epic/chain.yaml",
            "invalid_spec",
        ),
        (
            "missing_idea",
            lambda repo: _write_chain(repo, idea_path="missing.md"),
            ".megaplan/initiatives/epic/chain.yaml",
            "missing_idea_file",
        ),
        (
            "missing_seed_plan",
            lambda repo: (_write_valid_chain(repo, seed_plan="missing-seed")),
            ".megaplan/initiatives/epic/chain.yaml",
            "missing_seed_plan",
        ),
    ],
)
def test_megaplan_chain_validation_failures_persist_diagnostics_without_tmux(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    case_name: str,
    arrange: Callable[[Path], None],
    spec_path: str,
    expected_kind: str,
) -> None:
    config = _config_with_repo(tmp_path, "app")
    repo = config.repos_root / "app"
    arrange(repo)
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", f"add invalid chain spec for {case_name}", allow_empty=True)

    def fail_if_called(*args, **kwargs):
        raise AssertionError("tmux must not start before chain spec validation succeeds")

    monkeypatch.setattr("agentbox.host.start_session", fail_if_called)

    with pytest.raises(MegaplanChainLaunchError) as exc_info:
        MegaplanChainHandler().launch(
            config,
            "chain-1",
            repo_name="app",
            spec_path=spec_path,
        )

    run = load_agentbox_operation(config, "chain-1")
    resources = open_operation_store(config).list_typed_resources("chain-1")
    metadata = read_metadata(run_dir_paths(config, "chain-1"))
    events = _events(config.runs_root / "chain-1" / "events.ndjson")
    diagnostics = run.metadata["launch_diagnostics"]

    assert exc_info.value.kind == expected_kind
    assert run.operation_type == MEGAPLAN_CHAIN_OPERATION_TYPE
    assert run.state is OperationState.PENDING
    assert run.metadata["launch_state"] == "failed_before_running"
    assert diagnostics["phase"] == "validation"
    assert diagnostics["kind"] == expected_kind
    assert Path(diagnostics["spec_path"]).is_absolute()
    assert Path(diagnostics["project_root"]).is_absolute()
    assert metadata["validation"]["status"] == "failed"
    assert metadata["validation"]["kind"] == expected_kind
    assert events[-1]["event_type"] == "megaplan_chain.validation_failed"
    assert sum(resource.resource_type is ResourceType.PROCESS_SESSION for resource in resources) == 0
    assert {resource.resource_type for resource in resources} == {
        ResourceType.GIT_WORKTREE,
        ResourceType.LOG,
    }


def test_megaplan_chain_retry_after_validation_failure_reuses_resources_and_reruns_validation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = _config_with_repo(tmp_path, "app")
    repo = config.repos_root / "app"
    _write_chain(repo, idea_path=".megaplan/initiatives/epic/briefs/idea.md")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "add chain spec without idea")

    def fail_if_called(*args, **kwargs):
        raise AssertionError("tmux must not start before validation succeeds")

    monkeypatch.setattr("agentbox.host.start_session", fail_if_called)

    with pytest.raises(MegaplanChainLaunchError) as exc_info:
        MegaplanChainHandler().launch(
            config,
            "chain-1",
            repo_name="app",
            spec_path=".megaplan/initiatives/epic/chain.yaml",
        )

    failed_resources = open_operation_store(config).list_typed_resources("chain-1")
    failed_worktree = next(
        resource for resource in failed_resources if resource.resource_type is ResourceType.GIT_WORKTREE
    )
    failed_run_paths = run_dir_paths(config, "chain-1")
    worktree_path = Path(str(failed_worktree.details["worktree_path"]))
    retry_idea_path = worktree_path / ".megaplan" / "initiatives" / "epic" / "briefs" / "idea.md"
    retry_idea_path.parent.mkdir(parents=True, exist_ok=True)
    retry_idea_path.write_text(
        "Retry with the missing idea now present.\n",
        encoding="utf-8",
    )
    calls: list[dict[str, object]] = []

    def fake_start_session(operation_id, command, *, cwd=None, run_paths=None):
        calls.append({"operation_id": operation_id, "cwd": cwd, "run_paths": run_paths})
        return "agentbox-chain-1"

    monkeypatch.setattr("agentbox.host.start_session", fake_start_session)
    monkeypatch.setattr(
        "agentbox.host.inspect_session",
        lambda name: SessionStatus(name, "running", True),
    )

    result = MegaplanChainHandler().launch(
        config,
        "chain-1",
        repo_name="app",
        spec_path=".megaplan/initiatives/epic/chain.yaml",
    )

    resources = open_operation_store(config).list_typed_resources("chain-1")
    events = _events(result.host_result.run_paths.events_path)

    assert exc_info.value.kind == "missing_idea_file"
    assert result.host_result.run_paths == failed_run_paths
    assert result.project_root == worktree_path
    assert calls == [
        {
            "operation_id": "chain-1",
            "cwd": worktree_path,
            "run_paths": failed_run_paths,
        }
    ]
    assert load_agentbox_operation(config, "chain-1").state is OperationState.RUNNING
    assert sum(resource.resource_type is ResourceType.GIT_WORKTREE for resource in resources) == 1
    assert sum(resource.resource_type is ResourceType.PROCESS_SESSION for resource in resources) == 1
    assert "megaplan_chain.validation_failed" in [event["event_type"] for event in events]
    assert events[-1]["event_type"] == "host_launch.running"


def test_megaplan_chain_retry_after_tmux_start_failure_reuses_prepared_resources(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = _config_with_repo(tmp_path, "app")
    repo = config.repos_root / "app"
    _write_valid_chain(repo)
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "add chain spec")
    start_attempts = 0

    def flaky_start_session(operation_id, command, *, cwd=None, run_paths=None):
        nonlocal start_attempts
        start_attempts += 1
        if start_attempts == 1:
            raise RuntimeError("tmux unavailable")
        return "agentbox-chain-1"

    monkeypatch.setattr("agentbox.host.start_session", flaky_start_session)
    monkeypatch.setattr(
        "agentbox.host.inspect_session",
        lambda name: SessionStatus(name, "running", True),
    )

    with pytest.raises(MegaplanChainLaunchError) as exc_info:
        MegaplanChainHandler().launch(
            config,
            "chain-1",
            repo_name="app",
            spec_path=".megaplan/initiatives/epic/chain.yaml",
        )

    failed_resources = open_operation_store(config).list_typed_resources("chain-1")
    failed_worktree = next(
        resource for resource in failed_resources if resource.resource_type is ResourceType.GIT_WORKTREE
    )
    failed_run_paths = run_dir_paths(config, "chain-1")

    result = MegaplanChainHandler().launch(
        config,
        "chain-1",
        repo_name="app",
        spec_path=".megaplan/initiatives/epic/chain.yaml",
    )
    resources = open_operation_store(config).list_typed_resources("chain-1")

    assert exc_info.value.kind == "tmux_launch_failed"
    assert start_attempts == 2
    assert result.host_result.run_paths == failed_run_paths
    assert result.project_root == Path(str(failed_worktree.details["worktree_path"]))
    assert load_agentbox_operation(config, "chain-1").state is OperationState.RUNNING
    assert sum(resource.resource_type is ResourceType.GIT_WORKTREE for resource in resources) == 1
    assert sum(resource.resource_type is ResourceType.PROCESS_SESSION for resource in resources) == 1


def test_megaplan_chain_duplicate_running_launch_summarizes_live_session_without_restart(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = _config_with_repo(tmp_path, "app")
    repo = config.repos_root / "app"
    _write_valid_chain(repo)
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "add chain spec")
    starts = 0

    def fake_start_session(operation_id, command, *, cwd=None, run_paths=None):
        nonlocal starts
        starts += 1
        return "agentbox-chain-1"

    monkeypatch.setattr("agentbox.host.start_session", fake_start_session)
    monkeypatch.setattr(
        "agentbox.host.inspect_session",
        lambda name: SessionStatus(name, "running", True),
    )
    monkeypatch.setattr(
        "arnold_pipelines.megaplan.agentbox_adapter.inspect_session",
        lambda name: SessionStatus(name, "running", True),
    )

    first = MegaplanChainHandler().launch(
        config,
        "chain-1",
        repo_name="app",
        spec_path=".megaplan/initiatives/epic/chain.yaml",
    )
    second = MegaplanChainHandler().launch(
        config,
        "chain-1",
        repo_name="app",
        spec_path=".megaplan/initiatives/epic/chain.yaml",
    )
    resources = open_operation_store(config).list_typed_resources("chain-1")
    events = _events(second.host_result.run_paths.events_path)

    assert starts == 1
    assert second.host_result.run_paths == first.host_result.run_paths
    assert second.host_result.session_name == "agentbox-chain-1"
    assert second.host_result.diagnostics["kind"] == "already_running"
    assert sum(resource.resource_type is ResourceType.PROCESS_SESSION for resource in resources) == 1
    assert events[-1]["event_type"] == "megaplan_chain.running_reused"


def test_megaplan_chain_refuses_terminal_operation_retry_without_resetting_state(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = _config_with_repo(tmp_path, "app")
    repo = config.repos_root / "app"
    _write_valid_chain(repo)
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "add chain spec")

    monkeypatch.setattr(
        "agentbox.host.start_session",
        lambda *args, **kwargs: "agentbox-chain-1",
    )
    monkeypatch.setattr(
        "agentbox.host.inspect_session",
        lambda name: SessionStatus(name, "running", True),
    )
    MegaplanChainHandler().launch(
        config,
        "chain-1",
        repo_name="app",
        spec_path=".megaplan/initiatives/epic/chain.yaml",
    )
    update_agentbox_operation(config, "chain-1", state=OperationState.SUCCEEDED)

    def fail_if_called(*args, **kwargs):
        raise AssertionError("terminal operation retries must not start tmux")

    monkeypatch.setattr("agentbox.host.start_session", fail_if_called)

    with pytest.raises(MegaplanChainLaunchError) as exc_info:
        MegaplanChainHandler().launch(
            config,
            "chain-1",
            repo_name="app",
            spec_path=".megaplan/initiatives/epic/chain.yaml",
        )

    run = load_agentbox_operation(config, "chain-1")
    events = _events(run_dir_paths(config, "chain-1").events_path)

    assert exc_info.value.kind == "terminal_operation"
    assert run.state is OperationState.SUCCEEDED
    assert run.metadata["launch_state"] == "running"
    assert events[-1]["event_type"] == "megaplan_chain.retry_refused"


def test_megaplan_chain_status_snapshot_classifies_complete_over_live_runner(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = _config_with_repo(tmp_path, "app")
    repo = config.repos_root / "app"
    _write_valid_chain(repo)
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "add chain spec")
    monkeypatch.setattr("agentbox.host.start_session", lambda *args, **kwargs: "agentbox-chain-1")
    monkeypatch.setattr(
        "agentbox.host.inspect_session",
        lambda name: SessionStatus(name, "running", True),
    )
    monkeypatch.setattr(
        "arnold_pipelines.megaplan.agentbox_adapter.inspect_session",
        lambda name: SessionStatus(name, "running", True),
    )

    result = MegaplanChainHandler().launch(
        config,
        "chain-1",
        repo_name="app",
        spec_path=".megaplan/initiatives/epic/chain.yaml",
    )
    save_chain_state(
        result.resolved_spec_path,
        ChainState(
            current_milestone_index=1,
            current_plan_name="m1",
            last_state="done",
            pr_number=42,
            pr_state="merged",
            branch_head="abc",
            pr_head="abc",
            last_pushed_commit="abc",
            sync_state="synced",
            completed=[{"label": "first"}],
        ),
    )
    _write_plan_state(result.project_root, "m1", "done")

    snapshot = MegaplanChainHandler().status(config, "chain-1")
    payload = snapshot.to_dict()

    assert snapshot.classification.operation_state is OperationState.SUCCEEDED
    assert snapshot.classification.effective_status == "complete"
    assert snapshot.classification.reason == "all_milestones_completed"
    assert payload["spec"]["milestone_count"] == 1
    assert payload["policy"]["validation_policy"] == "none"
    assert payload["runner"]["status"] == "alive"
    assert payload["pr"] == {
        "status": "available",
        "pr_number": 42,
        "pr_state": "merged",
        "pr_head": "abc",
    }
    assert payload["sync"]["sync_state"] == "synced"


def test_megaplan_chain_status_snapshot_uses_latest_verdict_human_verification(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = _config_with_repo(tmp_path, "app")
    repo = config.repos_root / "app"
    _write_valid_chain(repo)
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "add chain spec")
    monkeypatch.setattr("agentbox.host.start_session", lambda *args, **kwargs: "agentbox-chain-1")
    monkeypatch.setattr(
        "agentbox.host.inspect_session",
        lambda name: SessionStatus(name, "running", True),
    )
    monkeypatch.setattr(
        "arnold_pipelines.megaplan.agentbox_adapter.inspect_session",
        lambda name: SessionStatus(name, "running", True),
    )

    result = MegaplanChainHandler().launch(
        config,
        "chain-1",
        repo_name="app",
        spec_path=".megaplan/initiatives/epic/chain.yaml",
    )
    save_chain_state(
        result.resolved_spec_path,
        ChainState(current_milestone_index=0, current_plan_name="m1", last_state="awaiting_human_verify"),
    )
    plan_dir = _write_plan_state(result.project_root, "m1", "awaiting_human_verify")
    (plan_dir / "human_verifications.json").write_text(
        json.dumps(
            [
                {"criterion_idx": 0, "timestamp": "2026-01-01T00:00:00Z", "verdict": "pass"},
                {"criterion_idx": 0, "timestamp": "2026-01-02T00:00:00Z", "verdict": "fail"},
            ]
        ),
        encoding="utf-8",
    )

    snapshot = MegaplanChainHandler().status(config, "chain-1")

    assert snapshot.human_verification["status"] == "available"
    assert snapshot.human_verification["semantics"] == "latest_verdict"
    assert snapshot.human_verification["pending"] == 1
    assert snapshot.human_verification["rows"][0]["latest_verdict"] == "fail"
    assert snapshot.classification.operation_state is OperationState.AWAITING_APPROVAL
    assert snapshot.classification.effective_status == "awaiting_human_verify"
    assert snapshot.classification.reason == "latest_verdict_human_verification_pending"


def test_megaplan_chain_status_snapshot_classifies_active_plan_without_runner_as_suspended(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = _config_with_repo(tmp_path, "app")
    repo = config.repos_root / "app"
    _write_valid_chain(repo)
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "add chain spec")
    monkeypatch.setattr("agentbox.host.start_session", lambda *args, **kwargs: "agentbox-chain-1")
    monkeypatch.setattr(
        "agentbox.host.inspect_session",
        lambda name: SessionStatus(name, "running", True),
    )

    result = MegaplanChainHandler().launch(
        config,
        "chain-1",
        repo_name="app",
        spec_path=".megaplan/initiatives/epic/chain.yaml",
    )
    save_chain_state(
        result.resolved_spec_path,
        ChainState(current_milestone_index=0, current_plan_name="m1", last_state="planned"),
    )
    _write_plan_state(result.project_root, "m1", "planned")
    monkeypatch.setattr(
        "arnold_pipelines.megaplan.agentbox_adapter.inspect_session",
        lambda name: SessionStatus(name, "dead", False),
    )

    snapshot = MegaplanChainHandler().status(config, "chain-1")

    assert snapshot.runner["status"] == "dead"
    assert snapshot.plan_status["status"] == "planned"
    assert snapshot.classification.operation_state is OperationState.SUSPENDED
    assert snapshot.classification.effective_status == "stale_bookkeeping"
    assert snapshot.classification.reason == "active_plan_without_live_runner"


def test_megaplan_chain_status_ignores_stale_completed_current_plan(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = _config_with_repo(tmp_path, "app")
    repo = config.repos_root / "app"
    idea_dir = repo / ".megaplan" / "initiatives" / "epic" / "briefs"
    idea_dir.mkdir(parents=True, exist_ok=True)
    (idea_dir / "m1.md").write_text("Implement the first milestone.\n", encoding="utf-8")
    (idea_dir / "m2.md").write_text("Implement the second milestone.\n", encoding="utf-8")
    _write_raw_chain(
        repo,
        "\n".join(
            [
                "base_branch: main",
                "milestones:",
                "  - label: m1",
                "    idea: .megaplan/initiatives/epic/briefs/m1.md",
                "  - label: m2",
                "    idea: .megaplan/initiatives/epic/briefs/m2.md",
                "",
            ]
        ),
    )
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "add chain spec")
    monkeypatch.setattr("agentbox.host.start_session", lambda *args, **kwargs: "agentbox-chain-1")
    monkeypatch.setattr(
        "agentbox.host.inspect_session",
        lambda name: SessionStatus(name, "running", True),
    )

    result = MegaplanChainHandler().launch(
        config,
        "chain-1",
        repo_name="app",
        spec_path=".megaplan/initiatives/epic/chain.yaml",
    )
    save_chain_state(
        result.resolved_spec_path,
        ChainState(
            current_milestone_index=1,
            current_plan_name="m1",
            last_state="blocked",
            completed=[{"label": "m1", "plan": "m1", "status": "done"}],
        ),
    )
    _write_plan_state(result.project_root, "m1", "blocked")
    monkeypatch.setattr(
        "arnold_pipelines.megaplan.agentbox_adapter.inspect_session",
        lambda name: SessionStatus(name, "dead", False),
    )

    snapshot = MegaplanChainHandler().status(config, "chain-1")

    assert snapshot.plan_status == {"status": "missing", "reason": "no current plan"}
    assert snapshot.classification.operation_state is OperationState.SUSPENDED
    assert snapshot.classification.effective_status == "stale_bookkeeping"
    assert snapshot.classification.reason == "running_operation_without_live_runner"


def test_megaplan_chain_status_clears_stale_completed_current_plan_raw_state(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = _config_with_repo(tmp_path, "app")
    repo = config.repos_root / "app"
    idea_dir = repo / ".megaplan" / "initiatives" / "epic" / "briefs"
    idea_dir.mkdir(parents=True, exist_ok=True)
    (idea_dir / "m1.md").write_text("Implement the first milestone.\n", encoding="utf-8")
    (idea_dir / "m2.md").write_text("Implement the second milestone.\n", encoding="utf-8")
    _write_raw_chain(
        repo,
        "\n".join(
            [
                "base_branch: main",
                "milestones:",
                "  - label: m1",
                "    idea: .megaplan/initiatives/epic/briefs/m1.md",
                "  - label: m2",
                "    idea: .megaplan/initiatives/epic/briefs/m2.md",
                "",
            ]
        ),
    )
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "add chain spec")
    monkeypatch.setattr("agentbox.host.start_session", lambda *args, **kwargs: "agentbox-chain-1")
    monkeypatch.setattr(
        "agentbox.host.inspect_session",
        lambda name: SessionStatus(name, "running", True),
    )

    result = MegaplanChainHandler().launch(
        config,
        "chain-1",
        repo_name="app",
        spec_path=".megaplan/initiatives/epic/chain.yaml",
    )
    save_chain_state(
        result.resolved_spec_path,
        ChainState(
            current_milestone_index=1,
            current_plan_name="m1",
            last_state="blocked",
            pr_number=42,
            pr_state="merged",
            completed=[{"label": "m1", "plan": "m1", "status": "done"}],
        ),
    )

    normalized = load_chain_state(result.resolved_spec_path)

    assert normalized.current_plan_name is None
    assert normalized.pr_number is None
    assert normalized.pr_state is None
    assert normalized.last_state == "done"


def test_megaplan_chain_status_clears_inherited_blocked_state_after_cursor_advances(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = _config_with_repo(tmp_path, "app")
    repo = config.repos_root / "app"
    idea_dir = repo / ".megaplan" / "initiatives" / "epic" / "briefs"
    idea_dir.mkdir(parents=True, exist_ok=True)
    (idea_dir / "m1.md").write_text("Implement the first milestone.\n", encoding="utf-8")
    (idea_dir / "m2.md").write_text("Implement the second milestone.\n", encoding="utf-8")
    _write_raw_chain(
        repo,
        "\n".join(
            [
                "base_branch: main",
                "milestones:",
                "  - label: m1",
                "    idea: .megaplan/initiatives/epic/briefs/m1.md",
                "  - label: m2",
                "    idea: .megaplan/initiatives/epic/briefs/m2.md",
                "",
            ]
        ),
    )
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "add chain spec")
    monkeypatch.setattr("agentbox.host.start_session", lambda *args, **kwargs: "agentbox-chain-1")
    monkeypatch.setattr(
        "agentbox.host.inspect_session",
        lambda name: SessionStatus(name, "running", True),
    )

    result = MegaplanChainHandler().launch(
        config,
        "chain-1",
        repo_name="app",
        spec_path=".megaplan/initiatives/epic/chain.yaml",
    )
    save_chain_state(
        result.resolved_spec_path,
        ChainState(
            current_milestone_index=1,
            current_plan_name=None,
            last_state="blocked",
            completed=[{"label": "m1", "plan": "m1", "status": "done"}],
        ),
    )

    normalized = load_chain_state(result.resolved_spec_path)

    assert normalized.current_milestone_index == 1
    assert normalized.current_plan_name is None
    assert normalized.last_state == "done"


def test_megaplan_chain_status_ignores_stale_completed_current_plan_by_milestone_label(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = _config_with_repo(tmp_path, "app")
    repo = config.repos_root / "app"
    idea_dir = repo / ".megaplan" / "initiatives" / "epic" / "briefs"
    idea_dir.mkdir(parents=True, exist_ok=True)
    (idea_dir / "m1.md").write_text("Implement the first milestone.\n", encoding="utf-8")
    (idea_dir / "m2.md").write_text("Implement the second milestone.\n", encoding="utf-8")
    _write_raw_chain(
        repo,
        "\n".join(
            [
                "base_branch: main",
                "milestones:",
                "  - label: m1",
                "    idea: .megaplan/initiatives/epic/briefs/m1.md",
                "  - label: m2",
                "    idea: .megaplan/initiatives/epic/briefs/m2.md",
                "",
            ]
        ),
    )
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "add chain spec")
    monkeypatch.setattr("agentbox.host.start_session", lambda *args, **kwargs: "agentbox-chain-1")
    monkeypatch.setattr(
        "agentbox.host.inspect_session",
        lambda name: SessionStatus(name, "running", True),
    )

    result = MegaplanChainHandler().launch(
        config,
        "chain-1",
        repo_name="app",
        spec_path=".megaplan/initiatives/epic/chain.yaml",
    )
    save_chain_state(
        result.resolved_spec_path,
        ChainState(
            current_milestone_index=1,
            current_plan_name="milestone-m1",
            last_state="blocked",
            completed=[{"label": "m1", "status": "done"}],
        ),
    )
    plan_dir = _write_plan_state(result.project_root, "milestone-m1", "blocked")
    state = json.loads((plan_dir / "state.json").read_text(encoding="utf-8"))
    state["meta"] = {"chain_policy": {"milestone_label": "m1"}}
    (plan_dir / "state.json").write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
    monkeypatch.setattr(
        "arnold_pipelines.megaplan.agentbox_adapter.inspect_session",
        lambda name: SessionStatus(name, "dead", False),
    )

    snapshot = MegaplanChainHandler().status(config, "chain-1")

    assert snapshot.plan_status == {"status": "missing", "reason": "no current plan"}
    assert snapshot.classification.operation_state is OperationState.SUSPENDED
    assert snapshot.classification.effective_status == "stale_bookkeeping"
    assert snapshot.classification.reason == "running_operation_without_live_runner"


def test_megaplan_chain_status_does_not_complete_from_terminal_cursor_without_full_completed_set(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = _config_with_repo(tmp_path, "app")
    repo = config.repos_root / "app"
    idea_dir = repo / ".megaplan" / "initiatives" / "epic" / "briefs"
    idea_dir.mkdir(parents=True, exist_ok=True)
    (idea_dir / "m1.md").write_text("Implement the first milestone.\n", encoding="utf-8")
    (idea_dir / "m2.md").write_text("Implement the second milestone.\n", encoding="utf-8")
    _write_raw_chain(
        repo,
        "\n".join(
            [
                "base_branch: main",
                "milestones:",
                "  - label: m1",
                "    idea: .megaplan/initiatives/epic/briefs/m1.md",
                "  - label: m2",
                "    idea: .megaplan/initiatives/epic/briefs/m2.md",
                "",
            ]
        ),
    )
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "add chain spec")
    monkeypatch.setattr("agentbox.host.start_session", lambda *args, **kwargs: "agentbox-chain-1")
    monkeypatch.setattr(
        "agentbox.host.inspect_session",
        lambda name: SessionStatus(name, "running", True),
    )

    result = MegaplanChainHandler().launch(
        config,
        "chain-1",
        repo_name="app",
        spec_path=".megaplan/initiatives/epic/chain.yaml",
    )
    save_chain_state(
        result.resolved_spec_path,
        ChainState(
            current_milestone_index=2,
            current_plan_name=None,
            last_state="done",
            completed=[{"label": "m1", "plan": "m1", "status": "done"}],
        ),
    )
    monkeypatch.setattr(
        "arnold_pipelines.megaplan.agentbox_adapter.inspect_session",
        lambda name: SessionStatus(name, "dead", False),
    )

    snapshot = MegaplanChainHandler().status(config, "chain-1")

    assert snapshot.classification.operation_state is OperationState.SUSPENDED
    assert snapshot.classification.effective_status == "stale_bookkeeping"
    assert snapshot.classification.reason == "running_operation_without_live_runner"


@pytest.mark.parametrize(
    (
        "spec_policy",
        "chain_state",
        "plan_state",
        "runner_status",
        "expected_state",
        "expected_status",
        "expected_reason",
    ),
    [
        (
            {},
            ChainState(current_milestone_index=0, current_plan_name="m1", last_state="planned"),
            "planned",
            SessionStatus("agentbox-chain-1", "running", True),
            OperationState.RUNNING,
            "running",
            "runner_alive",
        ),
        (
            {},
            ChainState(current_milestone_index=0, current_plan_name="m1", last_state="failed"),
            "failed",
            SessionStatus("agentbox-chain-1", "running", True),
            OperationState.FAILED,
            "failed",
            "plan_failed",
        ),
        (
            {},
            ChainState(
                current_milestone_index=0,
                current_plan_name="m1",
                last_state="awaiting_pr_merge",
                pr_number=77,
                pr_state="open",
                branch_head="abc",
                pr_head="def",
                last_pushed_commit="def",
                sync_state="behind_pr",
            ),
            "awaiting_pr_merge",
            SessionStatus("agentbox-chain-1", "dead", False),
            OperationState.AWAITING_APPROVAL,
            "awaiting_pr_merge",
            "chain_waiting_for_pr_merge",
        ),
        (
            {"prerequisite_policy": "required"},
            ChainState(),
            None,
            SessionStatus("agentbox-chain-1", "dead", False),
            OperationState.AWAITING_APPROVAL,
            "human_prerequisite",
            "required_prerequisite_policy",
        ),
        (
            {"validation_policy": "required"},
            ChainState(),
            None,
            SessionStatus("agentbox-chain-1", "dead", False),
            OperationState.AWAITING_APPROVAL,
            "quality_gate",
            "required_validation_policy",
        ),
    ],
)
def test_megaplan_chain_status_snapshot_classifies_cross_file_states(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    spec_policy: dict[str, str],
    chain_state: ChainState,
    plan_state: str | None,
    runner_status: SessionStatus,
    expected_state: OperationState,
    expected_status: str,
    expected_reason: str,
) -> None:
    config = _config_with_repo(tmp_path, "app")
    repo = config.repos_root / "app"
    _write_valid_chain(repo, **spec_policy)
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "add chain spec")
    monkeypatch.setattr("agentbox.host.start_session", lambda *args, **kwargs: "agentbox-chain-1")
    monkeypatch.setattr(
        "agentbox.host.inspect_session",
        lambda name: SessionStatus(name, "running", True),
    )

    result = MegaplanChainHandler().launch(
        config,
        "chain-1",
        repo_name="app",
        spec_path=".megaplan/initiatives/epic/chain.yaml",
    )
    save_chain_state(result.resolved_spec_path, chain_state)
    if plan_state is not None:
        _write_plan_state(result.project_root, "m1", plan_state)
    monkeypatch.setattr(
        "arnold_pipelines.megaplan.agentbox_adapter.inspect_session",
        lambda name: runner_status,
    )

    snapshot = MegaplanChainHandler().status(config, "chain-1")

    assert snapshot.classification.operation_state is expected_state
    assert snapshot.classification.effective_status == expected_status
    assert snapshot.classification.reason == expected_reason
    assert snapshot.policy["prerequisite_policy"] == spec_policy.get("prerequisite_policy", "none")
    assert snapshot.policy["validation_policy"] == spec_policy.get("validation_policy", "none")
    assert snapshot.runner["status"] == ("alive" if runner_status.exists else "dead")
    if chain_state.pr_number is not None:
        assert snapshot.pr["pr_number"] == chain_state.pr_number
        assert snapshot.sync["sync_state"] == chain_state.sync_state


def test_megaplan_chain_tick_persists_classification_and_status_change_event(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = _config_with_repo(tmp_path, "app")
    repo = config.repos_root / "app"
    _write_valid_chain(repo)
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "add chain spec")
    monkeypatch.setattr("agentbox.host.start_session", lambda *args, **kwargs: "agentbox-chain-1")
    monkeypatch.setattr(
        "agentbox.host.inspect_session",
        lambda name: SessionStatus(name, "running", True),
    )

    result = MegaplanChainHandler().launch(
        config,
        "chain-1",
        repo_name="app",
        spec_path=".megaplan/initiatives/epic/chain.yaml",
    )
    save_chain_state(
        result.resolved_spec_path,
        ChainState(current_milestone_index=0, current_plan_name="m1", last_state="planned"),
    )
    _write_plan_state(result.project_root, "m1", "planned")
    monkeypatch.setattr(
        "arnold_pipelines.megaplan.agentbox_adapter.inspect_session",
        lambda name: SessionStatus(name, "dead", False),
    )

    updated = MegaplanChainHandler().tick(config, "chain-1")
    events = _events(run_dir_paths(config, "chain-1").events_path)

    assert updated.state is OperationState.SUSPENDED
    assert updated.metadata["chain_status"]["operation_state"] == "suspended"
    assert updated.metadata["chain_status"]["effective_status"] == "stale_bookkeeping"
    assert updated.metadata["chain_status"]["reason"] == "active_plan_without_live_runner"
    assert events[-1]["event_type"] == "megaplan_chain.status_changed"
    assert events[-1]["payload"]["current"]["operation_state"] == "suspended"


def test_megaplan_chain_resume_restarts_stored_command_only_for_stale_dead_runner(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = _config_with_repo(tmp_path, "app")
    repo = config.repos_root / "app"
    _write_valid_chain(repo)
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "add chain spec")
    starts: list[dict[str, object]] = []

    def fake_start_session(operation_id, command, *, cwd=None, run_paths=None):
        starts.append({"operation_id": operation_id, "command": command, "cwd": cwd})
        return "agentbox-chain-1"

    monkeypatch.setattr("agentbox.host.start_session", fake_start_session)
    monkeypatch.setattr(
        "agentbox.host.inspect_session",
        lambda name: SessionStatus(name, "running", True),
    )
    monkeypatch.setattr(
        "arnold_pipelines.megaplan.agentbox_adapter.inspect_session",
        lambda name: SessionStatus(name, "running", True),
    )
    result = MegaplanChainHandler().launch(
        config,
        "chain-1",
        repo_name="app",
        spec_path=".megaplan/initiatives/epic/chain.yaml",
    )
    save_chain_state(
        result.resolved_spec_path,
        ChainState(current_milestone_index=0, current_plan_name="m1", last_state="planned"),
    )
    _write_plan_state(result.project_root, "m1", "planned")
    monkeypatch.setattr(
        "arnold_pipelines.megaplan.agentbox_adapter.inspect_session",
        lambda name: SessionStatus(name, "dead", False),
    )
    MegaplanChainHandler().tick(config, "chain-1")

    resumed = MegaplanChainHandler().resume(config, "chain-1")
    events = _events(run_dir_paths(config, "chain-1").events_path)

    assert resumed.state is OperationState.RUNNING
    assert len(starts) == 2
    assert starts[-1]["command"] == tuple(load_agentbox_operation(config, "chain-1").metadata["command"])
    assert starts[-1]["cwd"] == result.project_root
    assert events[-1]["event_type"] == "megaplan_chain.resumed"


def test_megaplan_chain_resume_directs_pre_running_failures_to_retry_launch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = _config_with_repo(tmp_path, "app")
    repo = config.repos_root / "app"
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "empty repo for missing spec", allow_empty=True)

    monkeypatch.setattr(
        "agentbox.host.start_session",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("tmux must not start")),
    )
    with pytest.raises(MegaplanChainLaunchError):
        MegaplanChainHandler().launch(
            config,
            "chain-1",
            repo_name="app",
            spec_path=".megaplan/initiatives/epic/missing.yaml",
        )

    with pytest.raises(MegaplanChainLaunchError) as exc_info:
        MegaplanChainHandler().resume(config, "chain-1")

    events = _events(run_dir_paths(config, "chain-1").events_path)

    assert exc_info.value.kind == "pre_running_retry_required"
    assert "agentbox run --operation-id" in str(exc_info.value)
    assert events[-1]["event_type"] == "megaplan_chain.resume_refused"


def test_megaplan_chain_summarize_and_cleanup_descriptor_are_compact_and_non_destructive(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = _config_with_repo(tmp_path, "app")
    repo = config.repos_root / "app"
    _write_valid_chain(repo)
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "add chain spec")
    monkeypatch.setattr("agentbox.host.start_session", lambda *args, **kwargs: "agentbox-chain-1")
    monkeypatch.setattr(
        "agentbox.host.inspect_session",
        lambda name: SessionStatus(name, "running", True),
    )
    monkeypatch.setattr(
        "arnold_pipelines.megaplan.agentbox_adapter.inspect_session",
        lambda name: SessionStatus(name, "running", True),
    )
    result = MegaplanChainHandler().launch(
        config,
        "chain-1",
        repo_name="app",
        spec_path=".megaplan/initiatives/epic/chain.yaml",
    )
    save_chain_state(
        result.resolved_spec_path,
        ChainState(current_milestone_index=0, current_plan_name="m1", last_state="planned"),
    )
    _write_plan_state(result.project_root, "m1", "planned")

    summary = MegaplanChainHandler().summarize(config, "chain-1")
    descriptor = MegaplanChainHandler().cleanup_descriptor(config, "chain-1")

    assert summary.startswith("chain-1: running state=running reason=runner_alive")
    assert "plan=m1" in summary
    assert "runner=alive" in summary
    assert descriptor["non_destructive"] is True
    assert descriptor["run_dir"] == str(run_dir_paths(config, "chain-1").root)
    assert {resource["type"] for resource in descriptor["resources"]} == {
        "git_worktree",
        "log",
        "process_session",
    }
    assert Path(descriptor["paths"]["stdout"]).exists()


def test_record_completion_dm_emits_event_and_sends_discord_dm(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = _config_with_repo(tmp_path, "app")
    create_agentbox_operation(
        config,
        "chain-1",
        command="echo hi",
        operation_type=MEGAPLAN_CHAIN_OPERATION_TYPE,
        repo_names=["app"],
    )
    update_agentbox_operation(config, "chain-1", state=OperationState.RUNNING)
    update_agentbox_operation(
        config,
        "chain-1",
        state=OperationState.SUCCEEDED,
        metadata={
            "repo_names": ["app"],
            "validation": {"status": "passed"},
            "pr_info": {"app": {"number": 42, "url": "https://github.com/example/repo/pull/42"}},
            "ci_status": {"app": "passed"},
        },
    )

    payloads: list[dict[str, object]] = []
    monkeypatch.setattr(
        "arnold_pipelines.megaplan.agentbox_adapter.send_discord_dm",
        lambda payload: payloads.append(dict(payload)) or {"ok": True, "message_count": 1},
    )

    run = load_agentbox_operation(config, "chain-1")
    _record_completion_dm(config, "chain-1", run)

    updated = load_agentbox_operation(config, "chain-1")
    events = _events(run_dir_paths(config, "chain-1").events_path)

    assert "Operation chain-1 completed with state succeeded." in updated.metadata["completion_dm"]
    assert events[-1]["event_type"] == "megaplan_chain.completion_dm_ready"
    assert payloads[0]["title"] == "Megaplan chain complete - chain-1"
    assert payloads[0]["links"] == [{"label": "PR", "url": "https://github.com/example/repo/pull/42"}]
    assert any(field["label"] == "CI" and field["value"] == "passed" for field in payloads[0]["fields"])


def test_record_completion_dm_never_raises_when_discord_send_crashes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = _config_with_repo(tmp_path, "app")
    create_agentbox_operation(
        config,
        "chain-1",
        command="echo hi",
        operation_type=MEGAPLAN_CHAIN_OPERATION_TYPE,
        repo_names=["app"],
    )
    update_agentbox_operation(config, "chain-1", state=OperationState.RUNNING)
    update_agentbox_operation(
        config,
        "chain-1",
        state=OperationState.SUCCEEDED,
        metadata={"repo_names": ["app"]},
    )

    monkeypatch.setattr(
        "arnold_pipelines.megaplan.agentbox_adapter.send_discord_dm",
        lambda payload: (_ for _ in ()).throw(RuntimeError("boom")),
    )

    run = load_agentbox_operation(config, "chain-1")
    _record_completion_dm(config, "chain-1", run)

    events = _events(run_dir_paths(config, "chain-1").events_path)
    assert events[-1]["event_type"] == "megaplan_chain.completion_dm_ready"


def _config_with_repo(tmp_path: Path, repo_name: str) -> AgentBoxConfig:
    config = AgentBoxConfig(workspace_root=tmp_path / "workspace")
    repo = _init_repo(config.repos_root / repo_name)
    register_repo(config, repo_name, path=repo)
    return config


def _init_repo(path: Path) -> Path:
    path.mkdir(parents=True)
    _git(path, "init", "-b", "main")
    _git(path, "config", "user.email", "agentbox@example.test")
    _git(path, "config", "user.name", "AgentBox Tests")
    (path / "README.md").write_text("# test\n", encoding="utf-8")
    _git(path, "add", "README.md")
    _git(path, "commit", "-m", "initial")
    return path


def _write_valid_chain(
    repo: Path,
    *,
    seed_plan: str | None = None,
    prerequisite_policy: str | None = None,
    validation_policy: str | None = None,
) -> None:
    idea = repo / ".megaplan" / "initiatives" / "epic" / "briefs" / "idea.md"
    idea.parent.mkdir(parents=True, exist_ok=True)
    idea.write_text("Implement the first milestone.\n", encoding="utf-8")
    _write_chain(
        repo,
        idea_path=".megaplan/initiatives/epic/briefs/idea.md",
        seed_plan=seed_plan,
        prerequisite_policy=prerequisite_policy,
        validation_policy=validation_policy,
    )


def _write_chain(
    repo: Path,
    *,
    idea_path: str,
    seed_plan: str | None = None,
    prerequisite_policy: str | None = None,
    validation_policy: str | None = None,
) -> None:
    lines = [
        "base_branch: main",
    ]
    if prerequisite_policy:
        lines.append(f"prerequisite_policy: {prerequisite_policy}")
    if validation_policy:
        lines.append(f"validation_policy: {validation_policy}")
    if seed_plan:
        lines.extend(
            [
                "seed:",
                f"  plan: {seed_plan}",
            ]
        )
    lines.extend(
        [
            "milestones:",
            "  - label: first",
            f"    idea: {idea_path}",
            "",
        ]
    )
    _write_raw_chain(repo, "\n".join(lines))


def _write_raw_chain(repo: Path, content: str) -> None:
    spec = repo / ".megaplan" / "initiatives" / "epic" / "chain.yaml"
    spec.parent.mkdir(parents=True, exist_ok=True)
    spec.write_text(content, encoding="utf-8")


def _write_plan_state(project_root: Path, plan_name: str, current_state: str) -> Path:
    plan_dir = project_root / ".megaplan" / "plans" / plan_name
    plan_dir.mkdir(parents=True, exist_ok=True)
    (plan_dir / "plan_v1.md").write_text("# plan\n", encoding="utf-8")
    state = {
        "name": plan_name,
        "current_state": current_state,
        "config": {},
        "plan_versions": [{"file": "plan_v1.md"}],
        "meta": {},
    }
    (plan_dir / "state.json").write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
    meta = {
        "success_criteria": [
            {"criterion": "Human confirms the milestone works", "priority": "must"}
        ]
    }
    (plan_dir / "plan_v1.meta.json").write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    return plan_dir


def _git(cwd: Path, *args: str, allow_empty: bool = False) -> str:
    command = ("git", *args)
    if allow_empty and args and args[0] == "commit":
        command = ("git", "commit", "--allow-empty", *args[1:])
    return subprocess.run(
        command,
        cwd=cwd,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    ).stdout.strip()


def _events(path: Path) -> list[dict[str, object]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
    ]
