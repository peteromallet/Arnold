"""Megaplan chain/PR platform conformance with faked git and remote edges."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from types import SimpleNamespace

from arnold.control.interface import RunStateView
from arnold.runtime.outcome import RunOutcome
from arnold_pipelines.megaplan.chain import (
    ChainState,
    MilestoneSpec,
    load_chain_state,
    save_chain_state,
)
import arnold_pipelines.megaplan.chain as chain_pkg
from arnold_pipelines.megaplan.chain import git_ops
from arnold_pipelines.megaplan.supervisor.model import RunNode, SupervisorState, SupervisorVariantKind
from arnold_pipelines.megaplan.supervisor.pr_merge import (
    PRMergeResolution,
    maybe_resolve_pr_merge_wait,
)
from arnold_pipelines.megaplan.supervisor.ladder import SupervisorLadderPolicy


def _write_chain_spec(path: Path) -> None:
    path.write_text(
        "\n".join(
            [
                "base_branch: main",
                "milestones:",
                "  - label: m6",
                "    idea: idea.md",
                "    branch: m6-native-platform",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    path.with_name("idea.md").write_text("ship native platform\n", encoding="utf-8")


def test_chain_pr_handoff_sync_and_restart_state_use_faked_boundaries(
    tmp_path: Path,
    monkeypatch,
) -> None:
    commands: list[tuple[str, ...]] = []
    writer_messages: list[str] = []
    spec_path = tmp_path / "chain.yaml"
    _write_chain_spec(spec_path)
    milestone = MilestoneSpec(
        label="m6",
        idea="idea.md",
        branch="m6-native-platform",
    )

    def writer(message: str) -> None:
        writer_messages.append(message)

    def fake_run_command(root, cmd, *, writer, timeout=120, error_code):
        commands.append(tuple(cmd))
        if cmd[:3] == ["gh", "pr", "list"]:
            return subprocess.CompletedProcess(cmd, 0, stdout="[]", stderr="")
        if cmd[:3] == ["gh", "pr", "create"]:
            return subprocess.CompletedProcess(
                cmd,
                0,
                stdout="https://github.example/repo/pull/77\n",
                stderr="",
            )
        if cmd[:3] == ["gh", "pr", "ready"]:
            return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")
        if cmd[:3] == ["gh", "pr", "merge"]:
            return subprocess.CompletedProcess(cmd, 0, stdout="merge queued\n", stderr="")
        if cmd[:3] == ["gh", "pr", "view"]:
            return subprocess.CompletedProcess(
                cmd,
                0,
                stdout=json.dumps({"state": "MERGED", "mergedAt": "2026-07-05T00:00:00Z"}),
                stderr="",
            )
        raise AssertionError(f"unexpected command: {cmd}")

    monkeypatch.setattr(git_ops.shutil, "which", lambda name: "/usr/bin/gh")
    monkeypatch.setattr(chain_pkg, "_run_command", fake_run_command)
    monkeypatch.setattr(chain_pkg, "_list_open_pr_for_branch", lambda root, branch, *, writer: None)
    monkeypatch.setattr(chain_pkg, "_parse_pr_number_from_url", lambda output: 77)

    pr_number = git_ops._ensure_milestone_pr(
        tmp_path,
        milestone,
        base_branch="main",
        writer=writer,
    )
    assert pr_number == 77
    assert any(
        command[:3] == ("gh", "pr", "create")
        and "--head" in command
        and "m6-native-platform" in command
        for command in commands
    )

    state = ChainState(
        current_milestone_index=0,
        current_plan_name="plan-m6",
        pr_number=77,
        pr_state="open",
    )
    save_chain_state(spec_path, state)
    monkeypatch.setattr(chain_pkg, "_branch_head", lambda root: "local-sha")
    monkeypatch.setattr(chain_pkg, "_remote_branch_head", lambda root, branch: "local-sha")
    monkeypatch.setattr(chain_pkg, "_is_worktree_dirty", lambda root: False)

    git_ops._capture_sync_state(
        tmp_path,
        spec_path,
        branch="m6-native-platform",
        pr_number=77,
        extra_repos=[str(tmp_path / "missing-repo")],
    )
    synced = load_chain_state(spec_path)
    assert synced.branch_head == "local-sha"
    assert synced.pr_head == "local-sha"
    assert synced.sync_state == "synced"
    assert synced.extra_repo_sync == [{"path": str(tmp_path / "missing-repo"), "status": "missing"}]

    round_tripped = load_chain_state(spec_path)
    round_tripped.completed.append(
        {
            "label": "m6",
            "status": "done",
            "plan": "plan-m6",
            "commit_sha": "local-sha",
            "pushed": True,
            "pr_number": 77,
            "pr_state": "open",
        }
    )
    save_chain_state(spec_path, round_tripped)
    restarted = load_chain_state(spec_path)
    assert restarted.completed[0]["pr_number"] == 77
    assert restarted.completed[0]["commit_sha"] == "local-sha"
    assert restarted.current_plan_name == "plan-m6"

    monkeypatch.setattr("arnold_pipelines.megaplan.supervisor.pr_merge.git_ops._pr_state", lambda root, pr_number, *, writer: "open")
    monkeypatch.setattr("arnold_pipelines.megaplan.supervisor.pr_merge._pr_merge_readiness", lambda root, pr_number, *, writer: "green")
    monkeypatch.setattr("arnold_pipelines.megaplan.supervisor.pr_merge.git_ops._mark_pr_ready", lambda root, pr_number, *, writer: commands.append(("gh", "pr", "ready", str(pr_number))))
    monkeypatch.setattr("arnold_pipelines.megaplan.supervisor.pr_merge.git_ops._enable_auto_merge", lambda root, pr_number, *, writer: "open")

    resolution = maybe_resolve_pr_merge_wait(
        root=tmp_path,
        state_id="supervisor-run",
        state=SupervisorState(
            variant=SupervisorVariantKind.CHAIN,
            run_nodes=[RunNode(node_id="node-1", spec_ref="m6")],
        ),
        node=RunNode(node_id="node-1", spec_ref="m6"),
        run_state=RunStateView(
            run_id="run-001",
            outcome=RunOutcome.AWAITING_HUMAN,
            cursor="awaiting_pr_merge",
            raw_state={"current_state": "awaiting_pr_merge", "resume_cursor": {"kind": "pr_merge", "pr_number": 77}},
            metadata={"pr_number": 77},
        ),
        plan_dir=tmp_path / ".megaplan" / "plans" / "plan-m6",
        binding="megaplan",
        policy=SupervisorLadderPolicy(),
        writer=writer,
    )
    assert isinstance(resolution, PRMergeResolution)
    assert resolution.handled is True
    assert resolution.advanced is True
    assert resolution.pr_state == "open"
    assert ("gh", "pr", "ready", "77") in commands

    product_routing_markers = {
        "product_routing_owner": "arnold_pipelines.megaplan.workflows.workflow.pypeline",
        "substrate_does_not_own": [
            "loop exits",
            "execute/review decisions",
            "model routing",
            "task satisfaction",
        ],
    }
    synced.metadata["platform_conformance"] = product_routing_markers
    save_chain_state(spec_path, synced)
    loaded = load_chain_state(spec_path)
    assert loaded.metadata["platform_conformance"] == product_routing_markers
    assert not any("megaplan route" in " ".join(command).lower() for command in commands)


def test_compatibility_pr_actor_preserves_manual_review_policy(tmp_path: Path) -> None:
    node = RunNode(node_id="node-1", spec_ref="m6")
    resolution = maybe_resolve_pr_merge_wait(
        root=tmp_path,
        state_id="supervisor-run",
        state=SupervisorState(
            variant=SupervisorVariantKind.CHAIN,
            run_nodes=[node],
        ),
        node=node,
        run_state=RunStateView(
            run_id="run-001",
            outcome=RunOutcome.AWAITING_HUMAN,
            cursor="awaiting_pr_merge",
            raw_state={
                "current_state": "awaiting_pr_merge",
                "resume_cursor": {"kind": "pr_merge", "pr_number": 77},
            },
            metadata={"pr_number": 77},
        ),
        plan_dir=tmp_path / ".megaplan" / "plans" / "plan-m6",
        binding="megaplan",
        policy=SupervisorLadderPolicy(),
        writer=lambda _message: None,
        automatic_pr_progression=False,
    )

    assert resolution.handled is False
    assert resolution.advanced is False
    assert resolution.pr_number == 77
    assert "human PR review" in (resolution.reason or "")
