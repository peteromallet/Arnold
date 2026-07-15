"""Tests for T16: atomic/enforce-mode behavior of ``_append_completed_with_guard``.

In atomic (fail-closed) mode the completion cursor must ONLY advance through the
CAS-backed acceptance commit helper.  On any predicate failure, CAS violation,
prepare rejection, or missing acceptance evidence the prior chain state is left
completely unchanged and a typed repair target is recorded.  Shadow mode
preserves the original legacy behavior exactly.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import arnold_pipelines.megaplan.chain as chain_module
from arnold_pipelines.megaplan._core.io import JournalCASResult, JournalCASViolation
from arnold_pipelines.megaplan.chain import (
    _append_completed_with_guard,
    load_chain_state,
    save_chain_state,
)
from arnold_pipelines.megaplan.chain.spec import ChainState
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


_FULL_SHA = "a" * 40


def _record() -> dict[str, object]:
    return {"label": "m1", "plan": "plan-m1", "status": "done"}


def _atomic_state() -> ChainState:
    state = ChainState()
    state.completion_contract_mode = "atomic"
    return state


def _accepted_result(*, milestone_index: int = 0) -> AcceptanceBoundaryResult:
    snapshot = AcceptanceSnapshot(
        transaction_id="tx-001",
        chain_run_id="run-1",
        milestone_label="m1",
        milestone_index=milestone_index,
        plan_name="plan-m1",
        source_commit_ref=_FULL_SHA,
        runtime_identity="ci-runner-7",
    )
    return AcceptanceBoundaryResult(
        snapshot=snapshot,
        identity_valid=True,
        identity_failures=(),
        suite_run=None,
        verdict=None,
        commands=(),
        exit_codes=(),
        log_paths=(),
        log_digests=(),
        started_at="2026-07-15T00:00:00Z",
        completed_at="2026-07-15T00:01:00Z",
        suite_identity="suite-run-1",
        commit_tree=_FULL_SHA,
        artifact_digests={},
        suite_status="passed",
        accepted=True,
        duration_seconds=60.0,
        failure_reasons=(),
        mode="atomic",
    )


def _write_chain_spec(root: Path) -> Path:
    idea = root / "idea.md"
    idea.write_text("ship milestone\n", encoding="utf-8")
    spec_path = root / "chain.yaml"
    spec_path.write_text(
        "base_branch: main\n"
        "anchors:\n"
        "  north_star: NORTHSTAR.md\n"
        "milestones:\n"
        "  - label: m1\n"
        f"    idea: {idea}\n"
        "    branch: test/m1\n",
        encoding="utf-8",
    )
    return spec_path


# ---------------------------------------------------------------------------
# Shadow mode (must be byte-for-byte unchanged legacy behavior)
# ---------------------------------------------------------------------------


def test_shadow_mode_predicate_failure_uses_legacy_behavior() -> None:
    """Shadow mode: predicate failure sets authority_divergence, no repair target."""
    state = ChainState()  # default mode == shadow
    messages: list[str] = []

    with patch.object(
        chain_module,
        "_chain_completion_guard",
        return_value=(False, "blocked: predicate failed"),
    ):
        appended, reason = _append_completed_with_guard(
            Path("/tmp/fake-root"),
            state,
            _record(),
            implementation_milestone=True,
            writer=messages.append,
        )

    assert appended is False
    assert reason == "blocked: predicate failed"
    assert state.completed == []
    assert state.last_state == "authority_divergence"
    # No typed repair targets in shadow mode.
    assert state.metadata.get("completion_guard_repair_targets") in (None, [])
    assert any("completion guard blocked" in m for m in messages)


def test_shadow_mode_success_appends_record_directly() -> None:
    """Shadow mode: predicate pass appends record directly (no acceptance commit)."""
    state = ChainState()

    with patch.object(
        chain_module,
        "_chain_completion_guard",
        return_value=(True, "non-implementation completion guard passed"),
    ):
        appended, reason = _append_completed_with_guard(
            Path("/tmp/fake-root"),
            state,
            _record(),
            implementation_milestone=False,
            writer=lambda _m: None,
        )

    assert appended is True
    assert state.completed == [_record()]
    assert state.metadata.get("completion_guard_repair_targets") in (None, [])


# ---------------------------------------------------------------------------
# Atomic mode: predicate failure -> fail closed, prior state unchanged
# ---------------------------------------------------------------------------


def test_atomic_predicate_failure_leaves_state_unchanged_and_emits_repair_target() -> None:
    """Atomic predicate failure does NOT mutate completed/cursor and emits a
    typed unknown_acceptance_failure repair target (legacy fallback)."""
    state = _atomic_state()
    prior_completed = list(state.completed)
    prior_index = state.current_milestone_index

    with patch.object(
        chain_module,
        "_chain_completion_guard",
        return_value=(False, "blocked: stale evidence"),
    ):
        appended, reason = _append_completed_with_guard(
            Path("/tmp/fake-root"),
            state,
            _record(),
            implementation_milestone=True,
            writer=lambda _m: None,
        )

    assert appended is False
    assert reason == "blocked: stale evidence"
    # Prior state unchanged on failure.
    assert state.completed == prior_completed
    assert state.current_milestone_index == prior_index
    assert state.last_state != "authority_divergence"  # atomic does not set this
    # Typed repair target emitted.
    targets = state.metadata.get("completion_guard_repair_targets")
    assert isinstance(targets, list) and len(targets) == 1
    assert targets[0]["kind"] == "unknown_acceptance_failure"
    assert targets[0]["summary"] == "blocked: stale evidence"
    assert targets[0]["details"]["legacy"] is True
    assert targets[0]["details"]["plan_name"] == "plan-m1"
    assert targets[0]["details"]["milestone_label"] == "m1"


def test_atomic_predicate_failure_with_typed_predicate_failures_passes_them_through() -> None:
    """When a V2 caller supplies typed predicate_failures, each is recorded with
    its own kind/summary/details."""
    state = _atomic_state()
    pfs = [
        {
            "kind": "stale",
            "summary": "receipt is stale",
            "details": {"age_hours": 72},
            "evidence_kind": "acceptance_receipt",
        },
        {
            "kind": "divergent",
            "summary": "artifact hash mismatch",
            "details": {"expected": "aaa", "actual": "bbb"},
            "evidence_kind": "artifact_digest",
        },
    ]

    with patch.object(
        chain_module,
        "_chain_completion_guard",
        return_value=(False, "blocked: multiple"),
    ):
        appended, reason = _append_completed_with_guard(
            Path("/tmp/fake-root"),
            state,
            _record(),
            implementation_milestone=True,
            writer=lambda _m: None,
            predicate_failures=pfs,
        )

    assert appended is False
    targets = state.metadata.get("completion_guard_repair_targets")
    assert isinstance(targets, list) and len(targets) == 2
    assert targets[0]["kind"] == "stale"
    assert targets[0]["evidence_kind"] == "acceptance_receipt"
    assert targets[1]["kind"] == "divergent"
    assert targets[1]["evidence_kind"] == "artifact_digest"
    assert state.completed == []


def test_atomic_no_acceptance_evidence_fails_closed() -> None:
    """Atomic mode with predicate pass but no acceptance_result must never
    advance the cursor and must emit a missing_acceptance_evidence target."""
    state = _atomic_state()
    prior_completed = list(state.completed)

    with patch.object(
        chain_module,
        "_chain_completion_guard",
        return_value=(True, "non-implementation completion guard passed"),
    ):
        appended, reason = _append_completed_with_guard(
            Path("/tmp/fake-root"),
            state,
            _record(),
            implementation_milestone=False,
            writer=lambda _m: None,
            # No acceptance_result / spec_path / plan_dir provided.
        )

    assert appended is False
    assert "fail-closed" in reason
    assert "accepted acceptance boundary" in reason
    # Prior state unchanged.
    assert state.completed == prior_completed
    targets = state.metadata.get("completion_guard_repair_targets")
    assert isinstance(targets, list) and len(targets) == 1
    assert targets[0]["kind"] == "unknown_acceptance_failure"
    assert targets[0]["details"]["missing_acceptance_evidence"] is True


# ---------------------------------------------------------------------------
# Atomic mode: success via acceptance commit helper
# ---------------------------------------------------------------------------


def test_atomic_commit_success_advances_state_through_acceptance_helper(
    tmp_path: Path,
) -> None:
    """Atomic mode: predicate pass + accepted boundary commits via the CAS helper
    and mirrors the committed completion record + cursor into the in-memory state."""
    spec_path = _write_chain_spec(tmp_path)
    plan_dir = tmp_path / ".megaplan" / "plans" / "plan-m1"
    plan_dir.mkdir(parents=True, exist_ok=True)
    state = _atomic_state()
    save_chain_state(spec_path, state)

    result = _accepted_result()

    with patch.object(
        chain_module,
        "_chain_completion_guard",
        return_value=(True, "non-implementation completion guard passed"),
    ):
        appended, reason = _append_completed_with_guard(
            tmp_path,
            state,
            _record(),
            implementation_milestone=False,
            writer=lambda _m: None,
            acceptance_result=result,
            spec_path=spec_path,
            plan_dir=plan_dir,
            milestone_index=0,
        )

    assert appended is True
    # In-memory state mirrors the committed new_state.
    assert len(state.completed) == 1
    rec = state.completed[0]
    assert rec["label"] == "m1"
    assert rec["snapshot_hash"] == result.snapshot.content_hash
    assert "acceptance_receipt" in rec
    assert state.current_milestone_index == 0
    assert "m1" in state.milestone_boundary_evidence
    # Durable state on disk also has the completed record.
    disk = load_chain_state(spec_path)
    assert len(disk.completed) == 1
    assert disk.completed[0]["label"] == "m1"
    assert disk.current_milestone_index == 0
    # No repair targets on success.
    assert state.metadata.get("completion_guard_repair_targets") in (None, [])


# ---------------------------------------------------------------------------
# Atomic mode: CAS violation -> prior durable state unchanged
# ---------------------------------------------------------------------------


def test_atomic_cas_violation_leaves_state_unchanged_and_emits_divergent_target(
    tmp_path: Path,
) -> None:
    """CAS violation on commit leaves prior durable state unchanged, discards the
    staged transaction, and emits a divergent repair target."""
    spec_path = _write_chain_spec(tmp_path)
    plan_dir = tmp_path / ".megaplan" / "plans" / "plan-m1"
    plan_dir.mkdir(parents=True, exist_ok=True)
    state = _atomic_state()
    state.completed.append(
        {
            "label": "m0",
            "plan": "plan-m0",
            "milestone_index": -1,
            "status": "done",
            "acceptance_receipt": {
                "snapshot_hash": "old",
                "milestone_label": "m0",
                "plan_name": "plan-m0",
                "milestone_index": -1,
            },
        }
    )
    prior_completed = [dict(r) for r in state.completed]
    save_chain_state(spec_path, state)

    result = _accepted_result()

    fake_plan = AcceptanceCommitPlan(
        tx_id="tx-001-commit",
        journal_root=tmp_path / ".megaplan" / "plans" / ".chains",
        prepare_path=tmp_path / "prepare.json",
        state_path=tmp_path / "state.json",
        prior_state_sha256="oldhash",
        new_state={"completed": [{"label": "m1"}], "current_milestone_index": 0},
        transaction_payload={},
        snapshot_payload={},
        snapshot_path=tmp_path / "snap.json",
        committed_tx_path=tmp_path / "tx.json",
        writes=(),
        milestone_label="m1",
        milestone_index=0,
        receipt_payload={},
    )
    fake_violation = JournalCASViolation(
        section="writes",
        entry_index=0,
        target_path=str(tmp_path / "state.json"),
        guard="expected_prior_sha256",
        expected="oldhash",
        actual="newhash",
    )
    fake_cas = JournalCASResult(tx_id="tx-001-commit", committed=False, violations=(fake_violation,))

    with (
        patch.object(
            chain_module,
            "_chain_completion_guard",
            return_value=(True, "non-implementation completion guard passed"),
        ),
        patch(
            "arnold_pipelines.megaplan.orchestration.completion_io.prepare_acceptance_commit",
            return_value=fake_plan,
        ),
        patch(
            "arnold_pipelines.megaplan.orchestration.completion_io.commit_acceptance_commit",
            return_value=fake_cas,
        ),
        patch(
            "arnold_pipelines.megaplan.orchestration.completion_io.discard_acceptance_commit"
        ) as mock_discard,
    ):
        appended, reason = _append_completed_with_guard(
            tmp_path,
            state,
            _record(),
            implementation_milestone=False,
            writer=lambda _m: None,
            acceptance_result=result,
            spec_path=spec_path,
            plan_dir=plan_dir,
            milestone_index=0,
        )

    assert appended is False
    assert "CAS violation" in reason
    # Prior in-memory state unchanged.
    assert [c["label"] for c in state.completed] == ["m0"]
    # Durable state unchanged.
    disk = load_chain_state(spec_path)
    assert [c["label"] for c in disk.completed] == ["m0"]
    # Staged transaction was discarded.
    mock_discard.assert_called_once_with(fake_plan)
    # Divergent repair target emitted.
    targets = state.metadata.get("completion_guard_repair_targets")
    assert isinstance(targets, list) and len(targets) == 1
    assert targets[0]["kind"] == "divergent"
    assert targets[0]["evidence_kind"] == "acceptance_commit"
    assert targets[0]["details"]["cas_violations"][0]["guard"] == "expected_prior_sha256"


# ---------------------------------------------------------------------------
# Atomic mode: prepare rejection (unaccepted boundary) -> fail closed
# ---------------------------------------------------------------------------


def test_atomic_prepare_rejection_for_unaccepted_boundary_fails_closed(
    tmp_path: Path,
) -> None:
    """If prepare_acceptance_commit rejects the boundary (e.g. accepted=False),
    the cursor must not advance and a repair target is emitted."""
    spec_path = _write_chain_spec(tmp_path)
    plan_dir = tmp_path / ".megaplan" / "plans" / "plan-m1"
    plan_dir.mkdir(parents=True, exist_ok=True)
    state = _atomic_state()
    prior_completed = list(state.completed)
    save_chain_state(spec_path, state)

    result = _accepted_result()

    with (
        patch.object(
            chain_module,
            "_chain_completion_guard",
            return_value=(True, "non-implementation completion guard passed"),
        ),
        patch(
            "arnold_pipelines.megaplan.orchestration.completion_io.prepare_acceptance_commit",
            side_effect=ValueError("boundary result was not accepted"),
        ),
    ):
        appended, reason = _append_completed_with_guard(
            tmp_path,
            state,
            _record(),
            implementation_milestone=False,
            writer=lambda _m: None,
            acceptance_result=result,
            spec_path=spec_path,
            plan_dir=plan_dir,
            milestone_index=0,
        )

    assert appended is False
    assert "prepare rejected" in reason
    # Prior state unchanged.
    assert state.completed == prior_completed
    targets = state.metadata.get("completion_guard_repair_targets")
    assert isinstance(targets, list) and len(targets) == 1
    assert targets[0]["kind"] == "unknown_acceptance_failure"
    assert "prepare_error" in targets[0]["details"]


def test_atomic_enforce_mode_synonym_works_like_atomic(tmp_path: Path) -> None:
    """``enforce`` is a synonym for ``atomic`` — both trigger fail-closed path."""
    spec_path = _write_chain_spec(tmp_path)
    plan_dir = tmp_path / ".megaplan" / "plans" / "plan-m1"
    plan_dir.mkdir(parents=True, exist_ok=True)
    state = ChainState()
    state.completion_contract_mode = "enforce"
    save_chain_state(spec_path, state)

    result = _accepted_result()

    with patch.object(
        chain_module,
        "_chain_completion_guard",
        return_value=(True, "non-implementation completion guard passed"),
    ):
        appended, reason = _append_completed_with_guard(
            tmp_path,
            state,
            _record(),
            implementation_milestone=False,
            writer=lambda _m: None,
            acceptance_result=result,
            spec_path=spec_path,
            plan_dir=plan_dir,
            milestone_index=0,
        )

    assert appended is True
    assert len(state.completed) == 1
    assert state.completed[0]["label"] == "m1"
