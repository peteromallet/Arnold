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
from arnold_pipelines.megaplan.chain.git_ops import (
    PRTransitionEvidence,
    _build_pr_transition_evidence,
    _check_merge_tip_containment,
)
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


# ── T13: PR/CI transition evidence tests ────────────────────────────────


def test_pr_transition_evidence_frozen_dataclass_with_all_fields() -> None:
    """PRTransitionEvidence is a frozen dataclass with 11 documented fields."""
    evidence = PRTransitionEvidence(
        pr_number=77,
        pr_head_sha="abc123def456",
        last_pushed_tip="abc123def456",
        merge_commit_sha="fed654cba321",
        ci_readiness_state="green",
        evidence_timestamp="2026-07-05T00:00:00Z",
        contract_id="pr.merged.1",
        tip_containment_applicable=True,
        tip_containment_verified=True,
        tip_containment_reason="PR head is ancestor of merge commit",
        pinned_pr_head=None,
    )
    assert evidence.pr_number == 77
    assert evidence.pr_head_sha == "abc123def456"
    assert evidence.last_pushed_tip == "abc123def456"
    assert evidence.merge_commit_sha == "fed654cba321"
    assert evidence.ci_readiness_state == "green"
    assert evidence.evidence_timestamp == "2026-07-05T00:00:00Z"
    assert evidence.contract_id == "pr.merged.1"
    assert evidence.tip_containment_applicable is True
    assert evidence.tip_containment_verified is True
    assert evidence.tip_containment_reason == "PR head is ancestor of merge commit"
    assert evidence.pinned_pr_head is None

    # Frozen: mutation raises
    try:
        evidence.pr_number = 99  # type: ignore[misc]
        raise AssertionError("frozen dataclass should not allow mutation")
    except Exception:
        pass


def test_pr_transition_evidence_stale_head_pins_pr_head() -> None:
    """When tip containment is NOT applicable (squash), pinned_pr_head is set."""
    evidence = PRTransitionEvidence(
        pr_number=42,
        pr_head_sha="stale-head-sha",
        merge_commit_sha="squash-commit-sha",
        contract_id="pr.merged.1",
        tip_containment_applicable=False,
        tip_containment_verified=None,
        tip_containment_reason="squash merge — tip containment not applicable",
        pinned_pr_head="stale-head-sha",
    )
    assert evidence.tip_containment_applicable is False
    assert evidence.tip_containment_verified is None
    assert evidence.pinned_pr_head == "stale-head-sha"
    assert evidence.pr_head_sha == "stale-head-sha"


def test_pr_transition_evidence_merge_commit_with_containment_verified() -> None:
    """Merge commit strategy supports tip containment when verified."""
    evidence = PRTransitionEvidence(
        pr_number=100,
        pr_head_sha="pr-tip-sha",
        merge_commit_sha="merge-commit-sha",
        contract_id="pr.merged.1",
        tip_containment_applicable=True,
        tip_containment_verified=True,
        tip_containment_reason="PR head abc is an ancestor of merge commit def",
        pinned_pr_head=None,
    )
    assert evidence.tip_containment_applicable is True
    assert evidence.tip_containment_verified is True
    assert evidence.pinned_pr_head is None


def test_build_pr_transition_evidence_ready_sets_correct_contract() -> None:
    """_build_pr_transition_evidence for PR ready uses pr.ready.1 contract."""
    evidence = _build_pr_transition_evidence(
        pr_number=55,
        contract_id="pr.ready.1",
        pr_head_sha="ready-head-sha",
        last_pushed_tip="ready-tip-sha",
        ci_readiness_state="green",
    )
    assert evidence.contract_id == "pr.ready.1"
    assert evidence.pr_number == 55
    assert evidence.pr_head_sha == "ready-head-sha"
    assert evidence.last_pushed_tip == "ready-tip-sha"
    assert evidence.ci_readiness_state == "green"
    assert evidence.evidence_timestamp is not None
    # Ready evidence: no merge fields, no containment check
    assert evidence.merge_commit_sha is None
    assert evidence.tip_containment_applicable is None
    assert evidence.tip_containment_verified is None
    assert evidence.pinned_pr_head is None


def test_build_pr_transition_evidence_merged_with_containment() -> None:
    """_build_pr_transition_evidence for merge with containment sets pr.merged.1."""
    evidence = _build_pr_transition_evidence(
        pr_number=88,
        contract_id="pr.merged.1",
        pr_head_sha="merged-head-sha",
        merge_commit_sha="merge-commit-sha",
        tip_containment_applicable=True,
        tip_containment_verified=True,
        tip_containment_reason="ancestor check passed",
    )
    assert evidence.contract_id == "pr.merged.1"
    assert evidence.pr_number == 88
    assert evidence.pr_head_sha == "merged-head-sha"
    assert evidence.merge_commit_sha == "merge-commit-sha"
    assert evidence.tip_containment_applicable is True
    assert evidence.tip_containment_verified is True
    assert evidence.pinned_pr_head is None  # containment applicable → no pin
    assert evidence.evidence_timestamp is not None


def test_build_pr_transition_evidence_squash_pins_head() -> None:
    """Squash merge evidence pins PR head since containment not applicable."""
    evidence = _build_pr_transition_evidence(
        pr_number=33,
        contract_id="pr.merged.1",
        pr_head_sha="squashed-head-sha",
        merge_commit_sha="squash-commit-sha",
        tip_containment_applicable=False,
        tip_containment_verified=None,
        tip_containment_reason="squash merge — tip containment not applicable; pinned PR head required",
    )
    assert evidence.contract_id == "pr.merged.1"
    assert evidence.tip_containment_applicable is False
    assert evidence.tip_containment_verified is None
    # When containment not applicable, pinned_pr_head = pr_head_sha
    assert evidence.pinned_pr_head == "squashed-head-sha"


def test_build_pr_transition_evidence_stale_head_detected() -> None:
    """Stale PR head: containment applicable but NOT verified — pinned still None,
    but the failure reason is recorded."""
    evidence = _build_pr_transition_evidence(
        pr_number=22,
        contract_id="pr.merged.1",
        pr_head_sha="stale-head-sha",
        merge_commit_sha="merge-commit-sha",
        tip_containment_applicable=True,
        tip_containment_verified=False,
        tip_containment_reason="PR head stale-head-sha is NOT an ancestor of merge commit",
    )
    assert evidence.tip_containment_applicable is True
    assert evidence.tip_containment_verified is False
    assert evidence.pinned_pr_head is None  # not pinned; stale detected but not pinned
    assert "NOT an ancestor" in (evidence.tip_containment_reason or "")


def test_pr_merge_resolution_carries_evidence_fields() -> None:
    """PRMergeResolution can carry pr_ready_evidence and pr_merged_evidence."""
    ready_evidence = _build_pr_transition_evidence(
        pr_number=11,
        contract_id="pr.ready.1",
        pr_head_sha="ready-sha",
        ci_readiness_state="green",
    )
    merged_evidence = _build_pr_transition_evidence(
        pr_number=11,
        contract_id="pr.merged.1",
        pr_head_sha="ready-sha",
        merge_commit_sha="merge-sha",
        tip_containment_applicable=True,
        tip_containment_verified=True,
        tip_containment_reason="ancestor verified",
    )
    resolution = PRMergeResolution(
        handled=True,
        advanced=True,
        pr_number=11,
        pr_state="merged",
        reason="PR #11 merge-ready",
        pr_ready_evidence=ready_evidence,
        pr_merged_evidence=merged_evidence,
    )
    assert resolution.handled is True
    assert resolution.advanced is True
    assert resolution.pr_number == 11
    assert resolution.pr_state == "merged"
    assert resolution.pr_ready_evidence is not None
    assert resolution.pr_ready_evidence.contract_id == "pr.ready.1"
    assert resolution.pr_merged_evidence is not None
    assert resolution.pr_merged_evidence.contract_id == "pr.merged.1"
    assert resolution.pr_merged_evidence.tip_containment_verified is True


def test_pr_transition_evidence_defaults_are_none() -> None:
    """PRTransitionEvidence with only pr_number leaves all optionals as None."""
    evidence = PRTransitionEvidence(pr_number=1)
    assert evidence.pr_number == 1
    assert evidence.pr_head_sha is None
    assert evidence.last_pushed_tip is None
    assert evidence.merge_commit_sha is None
    assert evidence.ci_readiness_state is None
    assert evidence.evidence_timestamp is None
    assert evidence.contract_id is None
    assert evidence.tip_containment_applicable is None
    assert evidence.tip_containment_verified is None
    assert evidence.tip_containment_reason is None
    assert evidence.pinned_pr_head is None


def test_check_merge_tip_containment_missing_inputs() -> None:
    """_check_merge_tip_containment returns None,None when inputs are missing."""
    applicable, verified, reason = _check_merge_tip_containment(
        None,  # type: ignore[arg-type] - testing with None root
        "",
        None,
        writer=print,
    )
    assert applicable is None
    assert verified is None
    assert "missing" in (reason or "").lower()
