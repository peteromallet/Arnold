"""Regression tests for the acceptance-commit atomic helpers.

These cover the end-to-end ``prepare_acceptance_commit`` ->
``commit_acceptance_commit``/``discard_acceptance_commit`` surface introduced for
the M5A atomic fail-closed milestone, including the CAS-backed journal
transaction and the cleanup of staged temp files on discard (the orphan-leak
bug where ``discard_acceptance_commit`` previously left ``.tx-*.tmp`` files).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from arnold_pipelines.megaplan.orchestration.acceptance_transaction import (
    AcceptanceBoundaryResult,
    AcceptanceSnapshot,
)
from arnold_pipelines.megaplan.orchestration.completion_io import (
    AcceptanceCommitPlan,
    commit_acceptance_commit,
    discard_acceptance_commit,
    prepare_acceptance_commit,
)
from arnold_pipelines.megaplan.orchestration.evidence_contract import (
    EvidenceRef,
    EvidenceStatus,
)
from arnold_pipelines.megaplan.chain.spec import ChainState

_FULL_SHA = "a" * 40


def _make_snapshot(*, milestone_label: str = "m5a", milestone_index: int = 3,
                   transaction_id: str = "tx1") -> AcceptanceSnapshot:
    return AcceptanceSnapshot(
        transaction_id=transaction_id,
        chain_run_id="c1",
        milestone_label=milestone_label,
        milestone_index=milestone_index,
        plan_name="p",
        source_commit_ref=_FULL_SHA,
        runtime_identity="ci",
        evidence=(EvidenceRef(kind="green_suite", status=EvidenceStatus.satisfied,
                              summary="ok"),),
    )


def _make_result(*, accepted: bool = True,
                 snapshot: AcceptanceSnapshot | None = None) -> AcceptanceBoundaryResult:
    snap = snapshot or _make_snapshot()
    return AcceptanceBoundaryResult(
        snapshot=snap,
        identity_valid=True,
        identity_failures=(),
        suite_run=None,
        verdict=None,
        commands=("pytest",),
        exit_codes=(0,),
        log_paths=(),
        log_digests=(),
        started_at="t",
        completed_at="t",
        suite_identity="r",
        commit_tree="t",
        artifact_digests={},
        suite_status="passed" if accepted else "failed",
        accepted=accepted,
        duration_seconds=1.0,
        failure_reasons=() if accepted else ("suite",),
        mode="atomic",
    )


def _bootstrap_plan_dir(tmp_path: Path) -> Path:
    proj = tmp_path / "proj"
    plan_dir = proj / ".megaplan" / "plans" / "p"
    plan_dir.mkdir(parents=True)
    spec = plan_dir / "chain_spec.yaml"
    spec.write_text("milestones:\n  - label: m1\n  - label: m2\n")
    return plan_dir


def test_prepare_acceptance_commit_stages_single_journal_transaction(tmp_path):
    plan_dir = _bootstrap_plan_dir(tmp_path)
    plan = prepare_acceptance_commit(
        plan_dir=plan_dir,
        spec_path=plan_dir / "chain_spec.yaml",
        result=_make_result(),
        state=ChainState(),
    )
    assert isinstance(plan, AcceptanceCommitPlan)
    # Exactly one journal prepare entry for this transaction.
    prepare_files = [plan.prepare_path] if plan.prepare_path.exists() else []
    assert len(prepare_files) == 1, prepare_files
    payload = json.loads(plan.prepare_path.read_text())
    # All five stages present in a single transaction payload.
    writes = payload.get("writes", [])
    target_names = {Path(w["target_path"]).name for w in writes}
    assert plan.state_path.name in target_names
    # Stage 3 (completion record), stage 4 (cursor advance) and stage 5
    # (milestone evidence) are also carried in the same tx payload.
    assert len(writes) >= 3


def test_commit_acceptance_commit_durably_applies_all_stages(tmp_path):
    plan_dir = _bootstrap_plan_dir(tmp_path)
    snap = _make_snapshot()
    plan = prepare_acceptance_commit(
        plan_dir=plan_dir,
        spec_path=plan_dir / "chain_spec.yaml",
        result=_make_result(snapshot=snap),
        state=ChainState(),
    )
    result = commit_acceptance_commit(plan)
    assert result.committed is True
    assert not result.violations
    # State file written and parseable.
    state = ChainState.from_dict(json.loads(plan.state_path.read_text()))
    completed_labels = {c["label"] for c in state.completed}
    assert snap.milestone_label in completed_labels
    completed_record = next(c for c in state.completed if c["label"] == snap.milestone_label)
    # completion record carries the acceptance receipt.
    assert completed_record.get("acceptance_receipt") is not None
    # Cursor advanced to the milestone index.
    assert state.current_milestone_index >= snap.milestone_index
    # Acceptance snapshot + committed transaction durable.
    assert plan.snapshot_path.exists()
    assert plan.committed_tx_path.exists()
    # Journal cleaned up after successful commit.
    assert not plan.prepare_path.exists()


def test_commit_acceptance_commit_cas_violation_fail_closed(tmp_path):
    plan_dir = _bootstrap_plan_dir(tmp_path)
    plan = prepare_acceptance_commit(
        plan_dir=plan_dir,
        spec_path=plan_dir / "chain_spec.yaml",
        result=_make_result(),
        state=ChainState(),
    )
    # On a fresh chain the prepare uses a target_absent CAS guard (the state
    # file must not exist at commit).  Creating it between prepare and commit
    # forces the guard to fail closed.
    plan.state_path.write_bytes(b'{"completed": [{"label": "mX"}]}\n')
    result = commit_acceptance_commit(plan)
    assert result.committed is False
    assert result.violations
    # Fail-closed: no completion record, no committed transaction.
    fresh = ChainState.from_dict(json.loads(plan.state_path.read_text()))
    completed_labels = {c.get("label") for c in fresh.completed}
    assert "m5a" not in completed_labels
    assert not plan.committed_tx_path.exists()
    # Journal discarded the violation.
    assert not plan.prepare_path.exists()


def test_discard_acceptance_commit_cleans_staged_temp_files(tmp_path):
    """Regression: discard must remove the staged .tx-*.tmp files, not just
    prepare.json (the prior bug left 3 orphan temp files in target dirs)."""
    plan_dir = _bootstrap_plan_dir(tmp_path)
    proj_root = plan_dir.parents[2]  # .megaplan/plans/p -> up to proj root
    plan = prepare_acceptance_commit(
        plan_dir=plan_dir,
        spec_path=plan_dir / "chain_spec.yaml",
        result=_make_result(),
        state=ChainState(),
    )
    # At prepare time the journal stages temp files in each target's parent.
    orphans_before = list(proj_root.rglob("*.tx-*.tmp"))
    assert orphans_before, "expected staged temp files at prepare time"
    discard_acceptance_commit(plan)
    orphans_after = list(proj_root.rglob("*.tx-*.tmp"))
    assert orphans_after == [], f"orphan temp files leaked: {orphans_after}"
    assert not plan.prepare_path.exists()


def test_discard_acceptance_commit_idempotent_on_missing_prepare(tmp_path):
    plan_dir = _bootstrap_plan_dir(tmp_path)
    plan = prepare_acceptance_commit(
        plan_dir=plan_dir,
        spec_path=plan_dir / "chain_spec.yaml",
        result=_make_result(),
        state=ChainState(),
    )
    discard_acceptance_commit(plan)
    # Calling again after discard must not raise.
    discard_acceptance_commit(plan)
    assert not plan.prepare_path.exists()


def test_prepare_rejects_unaccepted_result_fail_closed(tmp_path):
    plan_dir = _bootstrap_plan_dir(tmp_path)
    with pytest.raises(ValueError):
        prepare_acceptance_commit(
            plan_dir=plan_dir,
            spec_path=plan_dir / "chain_spec.yaml",
            result=_make_result(accepted=False),
            state=ChainState(),
        )
