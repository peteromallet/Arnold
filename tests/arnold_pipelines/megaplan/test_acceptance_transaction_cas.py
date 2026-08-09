"""CAS and crash-recovery tests for the atomic acceptance-commit boundary.

These tests prove that no crash stage, duplicate driver, stale worker, retry,
or out-of-order event can expose early-completed, merge-ready, or
successor-ready chain state, and that the completion record + cursor advance
are exactly-once.

Scope (high-level acceptance-commit surface):
  * :func:`prepare_acceptance_commit` stages one CAS-backed journal tx.
  * :func:`commit_acceptance_commit` runs ``commit_journal_transaction_cas``.
  * :func:`discard_acceptance_commit` removes a staged candidate.
  * :func:`replay_acceptance_commit_journal` recovers committed-only state.

The underlying journal-level mechanics (crash injection at each commit stage,
duplicate/stale CAS contention, exactly-once replay) are covered by the
companion extension to ``tests/arnold/kernel/test_journal.py``.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from arnold_pipelines.megaplan._core import io as journal_io
from arnold_pipelines.megaplan.chain import spec as chain_spec
from arnold_pipelines.megaplan.chain.spec import ChainState
from arnold_pipelines.megaplan.orchestration.acceptance_transaction import (
    AcceptanceBoundaryResult,
    AcceptanceSnapshot,
)
from arnold_pipelines.megaplan.orchestration.completion_io import (
    commit_acceptance_commit,
    discard_acceptance_commit,
    prepare_acceptance_commit,
    replay_acceptance_commit_journal,
)
from arnold_pipelines.megaplan.orchestration.evidence_contract import (
    EvidenceRef,
    EvidenceStatus,
)

_FULL_SHA = "a" * 40
_ALT_FULL_SHA = "b" * 40


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_snapshot(
    *,
    milestone_label: str = "m5a",
    milestone_index: int = 3,
    transaction_id: str = "tx1",
    source_commit_ref: str = _FULL_SHA,
) -> AcceptanceSnapshot:
    return AcceptanceSnapshot(
        transaction_id=transaction_id,
        chain_run_id="c1",
        milestone_label=milestone_label,
        milestone_index=milestone_index,
        plan_name="p",
        source_commit_ref=source_commit_ref,
        runtime_identity="ci",
        evidence=(
            EvidenceRef(
                kind="green_suite",
                status=EvidenceStatus.satisfied,
                summary="ok",
            ),
        ),
    )


def _make_result(
    *,
    accepted: bool = True,
    snapshot: AcceptanceSnapshot | None = None,
) -> AcceptanceBoundaryResult:
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


def _load_ondisk_state(state_path: Path) -> ChainState:
    """Load the current on-disk chain state, or a fresh ChainState if absent.

    ``prepare_acceptance_commit`` builds ``new_state`` from the in-memory
    ``state`` parameter (it never reads the state file for content), so the
    caller MUST pass the current on-disk state to avoid clobbering prior
    completions when committing a later milestone.
    """
    if state_path.exists():
        return ChainState.from_dict(json.loads(state_path.read_text()))
    return ChainState()


def _prepare_commit(
    plan_dir: Path,
    snapshot: AcceptanceSnapshot,
    *,
    milestone_index: int | None = None,
    state: ChainState | None = None,
    expected_prior_state_sha256: str | None = None,
    tx_id: str | None = None,
):
    spec_path = plan_dir / "chain_spec.yaml"
    state_path = chain_spec._state_path_for(spec_path)
    if state is None:
        state = _load_ondisk_state(state_path)
    return prepare_acceptance_commit(
        plan_dir=plan_dir,
        spec_path=spec_path,
        result=_make_result(snapshot=snapshot),
        state=state,
        milestone_index=milestone_index,
        expected_prior_state_sha256=expected_prior_state_sha256,
        tx_id=tx_id,
    )


def _state_dict(plan_dir, state_path: Path) -> dict:
    return json.loads(state_path.read_text())


def _completed_labels(state_path: Path) -> set[str]:
    if not state_path.exists():
        return set()
    return {c["label"] for c in _state_dict(None, state_path).get("completed", [])}


def _cursor(state_path: Path) -> int:
    if not state_path.exists():
        return -1
    return int(_state_dict(None, state_path).get("current_milestone_index", -1))


def _state_sha(path: Path) -> str | None:
    import hashlib

    try:
        raw = path.read_bytes()
    except OSError:
        return None
    return "sha256:" + hashlib.sha256(raw).hexdigest()


# ===========================================================================
# 1. Crash stages — no torn state leaks after recovery at any commit stage
# ===========================================================================


class TestAcceptanceCommitCrashStages:
    """A crash at *any* stage of the acceptance commit must never expose a
    partially-applied transaction; recovery either completes it or discards
    it entirely."""

    def test_crash_after_prepare_before_commit_discards_state(self, tmp_path):
        """Driver prepares but crashes before writing the commit marker.
        Recovery must discard the uncommitted candidate so NO state file,
        completion record, or cursor advance is visible."""
        plan_dir = _bootstrap_plan_dir(tmp_path)
        plan = _prepare_commit(plan_dir, _make_snapshot())

        # Crash: nothing committed. Recovery should discard the candidate.
        rec = replay_acceptance_commit_journal(plan.journal_root)
        assert plan.tx_id in rec["discarded"]
        assert plan.tx_id not in rec["replayed"]
        # No state file materialised.
        assert not plan.state_path.exists()
        # No committed transaction file.
        assert not plan.committed_tx_path.exists()
        # Prepare entry cleaned up.
        assert not plan.prepare_path.exists()

    def test_crash_after_commit_marker_before_apply_completes_durable(self, tmp_path):
        """Crash *after* the commit marker is written but *before* the writes
        are applied. Recovery sees (prepare + marker) and replays to
        completion: state, receipt, completed record, and cursor are ALL
        durably applied and consistent."""
        plan_dir = _bootstrap_plan_dir(tmp_path)
        plan = _prepare_commit(plan_dir, _make_snapshot())

        # Simulate crash right after the commit marker.
        journal_io.write_journal_commit_marker(plan.journal_root, plan.tx_id)
        assert not plan.state_path.exists()  # not yet applied

        rec = replay_acceptance_commit_journal(plan.journal_root)
        assert plan.tx_id in rec["replayed"]

        # Full, consistent state now on disk.
        state = ChainState.from_dict(json.loads(plan.state_path.read_text()))
        assert "m5a" in {c["label"] for c in state.completed}
        rec_m5a = next(c for c in state.completed if c["label"] == "m5a")
        assert rec_m5a.get("acceptance_receipt") is not None
        assert state.current_milestone_index >= 3
        assert plan.snapshot_path.exists()
        assert plan.committed_tx_path.exists()
        # Prepare + marker cleaned up after replay.
        assert not plan.prepare_path.exists()

    def test_crash_after_apply_before_cleanup_is_idempotent(self, tmp_path):
        """Crash *after* the writes are applied but *before* cleanup. Recovery
        re-applies idempotently and cleans up; the final state is identical to
        a clean commit."""
        plan_dir = _bootstrap_plan_dir(tmp_path)
        plan = _prepare_commit(plan_dir, _make_snapshot())

        # Simulate crash after marker + apply, before cleanup.
        journal_io.write_journal_commit_marker(plan.journal_root, plan.tx_id)
        payload = journal_io.read_json(plan.prepare_path)
        payload["journal_root"] = str(plan.journal_root)
        journal_io._apply_prepared_writes(payload)
        assert plan.state_path.exists()  # applied

        snapshot_before = plan.state_path.read_bytes()
        rec = replay_acceptance_commit_journal(plan.journal_root)
        assert plan.tx_id in rec["replayed"]
        # State bytes unchanged by idempotent re-apply.
        assert plan.state_path.read_bytes() == snapshot_before
        # Cleanup completed.
        assert not plan.prepare_path.exists()

    def test_crash_after_cleanup_is_clean_final_state(self, tmp_path):
        """Crash *after* full cleanup. Recovery is a no-op; the final state
        is exactly the committed state."""
        plan_dir = _bootstrap_plan_dir(tmp_path)
        plan = _prepare_commit(plan_dir, _make_snapshot())
        res = commit_acceptance_commit(plan)
        assert res.committed is True
        # Transaction is fully cleaned up (no prepare/marker remain).
        assert not plan.prepare_path.exists()

        snapshot = plan.state_path.read_bytes()
        rec = replay_acceptance_commit_journal(plan.journal_root)
        assert rec["replayed"] == []
        assert rec["discarded"] == []
        assert plan.state_path.read_bytes() == snapshot

    def test_repeated_recovery_does_not_duplicate_completion(self, tmp_path):
        """Running recovery multiple times (e.g. restart loops) must never
        add a second completion record or move the cursor again."""
        plan_dir = _bootstrap_plan_dir(tmp_path)
        plan = _prepare_commit(plan_dir, _make_snapshot())
        journal_io.write_journal_commit_marker(plan.journal_root, plan.tx_id)

        for _ in range(4):
            replay_acceptance_commit_journal(plan.journal_root)

        state = ChainState.from_dict(json.loads(plan.state_path.read_text()))
        m5a_recs = [c for c in state.completed if c["label"] == "m5a"]
        assert len(m5a_recs) == 1
        assert state.current_milestone_index == 3


# ===========================================================================
# 2. Duplicate drivers — concurrent writers cannot both complete
# ===========================================================================


class TestDuplicateDrivers:
    """Two drivers racing to commit the same milestone cannot both succeed."""

    def test_target_absent_loses_after_first_commit(self, tmp_path):
        """Both drivers target a fresh (absent) state. Driver A commits
        first; driver B's ``target_absent`` CAS guard fails closed — its
        commit is discarded and the state is exactly driver A's."""
        plan_dir = _bootstrap_plan_dir(tmp_path)

        plan_a = _prepare_commit(
            plan_dir, _make_snapshot(transaction_id="driverA"),
            tx_id="driverA-commit",
        )
        plan_b = _prepare_commit(
            plan_dir, _make_snapshot(transaction_id="driverB"),
            tx_id="driverB-commit",
        )

        res_a = commit_acceptance_commit(plan_a)
        assert res_a.committed is True

        res_b = commit_acceptance_commit(plan_b)
        assert res_b.committed is False
        assert res_b.violations  # CAS violation reported

        # State reflects exactly one completion (driver A's).
        labels = _completed_labels(plan_a.state_path)
        assert labels == {"m5a"}
        state = ChainState.from_dict(json.loads(plan_a.state_path.read_text()))
        rec = next(c for c in state.completed if c["label"] == "m5a")
        assert rec["transaction_id"] == "driverA"

    def test_duplicate_stale_prior_hash_second_driver_fails_closed(self, tmp_path):
        """Both drivers capture the same prior state hash from an existing
        state. Driver A commits (state changes); driver B's
        ``expected_prior_sha256`` no longer matches — fail-closed."""
        plan_dir = _bootstrap_plan_dir(tmp_path)
        # Seed an existing state with one completion.
        seed_plan = _prepare_commit(
            plan_dir, _make_snapshot(milestone_label="m0", milestone_index=0),
            tx_id="seed-commit",
        )
        commit_acceptance_commit(seed_plan)
        prior = _state_sha(seed_plan.state_path)

        plan_a = _prepare_commit(
            plan_dir,
            _make_snapshot(transaction_id="dupA", milestone_index=1),
            expected_prior_state_sha256=prior,
            tx_id="dupA-commit",
        )
        plan_b = _prepare_commit(
            plan_dir,
            _make_snapshot(transaction_id="dupB", milestone_index=1),
            expected_prior_state_sha256=prior,
            tx_id="dupB-commit",
        )
        res_a = commit_acceptance_commit(plan_a)
        assert res_a.committed is True

        res_b = commit_acceptance_commit(plan_b)
        assert res_b.committed is False
        assert res_b.violations

        state = ChainState.from_dict(json.loads(plan_a.state_path.read_text()))
        idx1 = [c for c in state.completed if c.get("milestone_index") == 1]
        assert len(idx1) == 1
        assert idx1[0]["transaction_id"] == "dupA"


# ===========================================================================
# 3. Stale workers — a worker with an outdated state hash cannot commit
# ===========================================================================


class TestStaleWorkers:
    """A worker that captured a state hash before another commit landed must
    fail closed and leave the landed state untouched."""

    def test_stale_state_hash_blocks_commit(self, tmp_path):
        plan_dir = _bootstrap_plan_dir(tmp_path)
        # Land m0 to create initial state.
        first = _prepare_commit(
            plan_dir, _make_snapshot(milestone_label="m0", milestone_index=0),
            tx_id="first-commit",
        )
        commit_acceptance_commit(first)
        stale_hash = _state_sha(first.state_path)

        # Stale worker prepares m1 against the OLD hash.
        stale_plan = _prepare_commit(
            plan_dir,
            _make_snapshot(milestone_label="m1", milestone_index=1,
                           transaction_id="stale"),
            expected_prior_state_sha256=stale_hash,
            tx_id="stale-commit",
        )
        # A *different* commit lands first, changing the state.
        interloper = _prepare_commit(
            plan_dir,
            _make_snapshot(milestone_label="m2", milestone_index=2,
                           transaction_id="inter"),
            tx_id="inter-commit",
        )
        res_inter = commit_acceptance_commit(interloper)
        assert res_inter.committed is True

        # Now the stale worker commits — CAS fails.
        res_stale = commit_acceptance_commit(stale_plan)
        assert res_stale.committed is False
        assert res_stale.violations

        state = ChainState.from_dict(json.loads(first.state_path.read_text()))
        labels = {c["label"] for c in state.completed}
        assert labels == {"m0", "m2"}  # stale m1 NOT landed
        assert "m1" not in labels

    def test_stale_worker_recovers_by_refreshing_hash(self, tmp_path):
        """After a stale-worker CAS failure, re-preparing against the current
        on-disk hash lets the worker commit successfully (retry semantics)."""
        plan_dir = _bootstrap_plan_dir(tmp_path)
        first = _prepare_commit(
            plan_dir, _make_snapshot(milestone_label="m0", milestone_index=0),
            tx_id="first-commit",
        )
        commit_acceptance_commit(first)

        stale_hash = _state_sha(first.state_path)
        stale_plan = _prepare_commit(
            plan_dir,
            _make_snapshot(milestone_label="m1", milestone_index=1,
                           transaction_id="stale"),
            expected_prior_state_sha256=stale_hash,
            tx_id="stale-commit",
        )
        inter = _prepare_commit(
            plan_dir,
            _make_snapshot(milestone_label="m2", milestone_index=2,
                           transaction_id="inter"),
            tx_id="inter-commit",
        )
        commit_acceptance_commit(inter)

        res = commit_acceptance_commit(stale_plan)
        assert res.committed is False

        # Refresh: re-prepare against the now-current hash.
        fresh_hash = _state_sha(first.state_path)
        retry = _prepare_commit(
            plan_dir,
            _make_snapshot(milestone_label="m1", milestone_index=1,
                           transaction_id="stale"),
            expected_prior_state_sha256=fresh_hash,
            tx_id="stale-retry-commit",
        )
        res2 = commit_acceptance_commit(retry)
        assert res2.committed is True

        state = ChainState.from_dict(json.loads(first.state_path.read_text()))
        labels = {c["label"] for c in state.completed}
        assert labels == {"m0", "m1", "m2"}


# ===========================================================================
# 4. Crash / restart — full crash then recovery then re-commit
# ===========================================================================


class TestCrashRestart:
    """A full crash at the prepare stage, followed by restart + re-prepare +
    commit, must produce a consistent committed state."""

    def test_crash_then_restart_reprepare_then_commit(self, tmp_path):
        plan_dir = _bootstrap_plan_dir(tmp_path)
        plan = _prepare_commit(plan_dir, _make_snapshot())
        # Crash: no commit marker. Recovery discards the candidate.
        rec = replay_acceptance_commit_journal(plan.journal_root)
        assert plan.tx_id in rec["discarded"]
        assert not plan.state_path.exists()

        # Restart: a fresh driver re-prepares and commits successfully.
        plan2 = _prepare_commit(plan_dir, _make_snapshot())
        res = commit_acceptance_commit(plan2)
        assert res.committed is True

        state = ChainState.from_dict(json.loads(plan2.state_path.read_text()))
        m5a = [c for c in state.completed if c["label"] == "m5a"]
        assert len(m5a) == 1
        assert state.current_milestone_index >= 3

    def test_crash_after_marker_then_restart_completes(self, tmp_path):
        """Crash after the marker but before apply; restart recovery completes
        the transaction so a subsequent driver sees the landed state."""
        plan_dir = _bootstrap_plan_dir(tmp_path)
        plan = _prepare_commit(plan_dir, _make_snapshot())
        journal_io.write_journal_commit_marker(plan.journal_root, plan.tx_id)

        replay_acceptance_commit_journal(plan.journal_root)
        landed_hash = _state_sha(plan.state_path)
        assert landed_hash is not None

        # A new driver now prepares against the landed state and commits.
        plan2 = _prepare_commit(
            plan_dir,
            _make_snapshot(milestone_label="m6", milestone_index=4,
                           transaction_id="tx2"),
        )
        res = commit_acceptance_commit(plan2)
        assert res.committed is True

        state = ChainState.from_dict(json.loads(plan.state_path.read_text()))
        assert {"m5a", "m6"} <= {c["label"] for c in state.completed}
        assert state.current_milestone_index >= 4


# ===========================================================================
# 5. Retry — discard then re-prepare succeeds
# ===========================================================================


class TestRetryAfterFailure:
    """After a CAS failure the candidate is discarded; a fresh prepare+commit
    with the correct prior hash succeeds."""

    def test_discard_then_reprepare_commits(self, tmp_path):
        plan_dir = _bootstrap_plan_dir(tmp_path)
        plan = _prepare_commit(plan_dir, _make_snapshot())
        # Explicitly discard (e.g. predicate failed before commit).
        discard_acceptance_commit(plan)
        assert not plan.prepare_path.exists()
        assert not plan.state_path.exists()

        plan2 = _prepare_commit(plan_dir, _make_snapshot())
        res = commit_acceptance_commit(plan2)
        assert res.committed is True
        assert plan2.state_path.exists()

    def test_cas_failure_discards_then_retry_commits(self, tmp_path):
        plan_dir = _bootstrap_plan_dir(tmp_path)
        # Land an initial state.
        seed = _prepare_commit(
            plan_dir, _make_snapshot(milestone_label="m0", milestone_index=0),
            tx_id="seed-commit",
        )
        commit_acceptance_commit(seed)
        old_hash = _state_sha(seed.state_path)

        # Prepare with a STALE (wrong) hash to force a CAS failure.
        bad = _prepare_commit(
            plan_dir,
            _make_snapshot(transaction_id="bad", milestone_index=1),
            expected_prior_state_sha256="sha256:" + "0" * 64,
            tx_id="bad-commit",
        )
        res = commit_acceptance_commit(bad)
        assert res.committed is False
        assert res.violations
        # Journal already discarded the failed candidate.
        assert not bad.prepare_path.exists()

        # Retry with the correct hash.
        retry = _prepare_commit(
            plan_dir,
            _make_snapshot(transaction_id="bad", milestone_index=1),
            tx_id="retry-commit",
        )
        res2 = commit_acceptance_commit(retry)
        assert res2.committed is True


# ===========================================================================
# 6. Out-of-order events — cursor never moves backward
# ===========================================================================


class TestOutOfOrderEvents:
    """Committing milestones out of index order must not move the cursor
    backward, and each milestone gets exactly one completion record."""

    def test_higher_index_then_lower_keeps_cursor_at_max(self, tmp_path):
        plan_dir = _bootstrap_plan_dir(tmp_path)
        # Commit index 2 first (out of order).
        p_hi = _prepare_commit(
            plan_dir,
            _make_snapshot(milestone_label="m2", milestone_index=2,
                           transaction_id="hi"),
            tx_id="hi-commit",
        )
        commit_acceptance_commit(p_hi)
        assert _cursor(p_hi.state_path) == 2

        # Now commit index 0 — cursor must NOT drop to 0.
        p_lo = _prepare_commit(
            plan_dir,
            _make_snapshot(milestone_label="m0", milestone_index=0,
                           transaction_id="lo"),
            tx_id="lo-commit",
        )
        commit_acceptance_commit(p_lo)
        assert _cursor(p_lo.state_path) == 2

        labels = _completed_labels(p_hi.state_path)
        assert labels == {"m2", "m0"}

    def test_replay_then_lower_index_does_not_move_cursor_backward(self, tmp_path):
        """A committed higher-index milestone recovered via replay (cursor=3),
        followed by a normal commit of a lower-index milestone (loaded from
        the recovered on-disk state), must keep the cursor at 3 — not regress
        to the lower index."""
        plan_dir = _bootstrap_plan_dir(tmp_path)
        # Crash after marker for index 3.
        p3 = _prepare_commit(
            plan_dir,
            _make_snapshot(milestone_label="m3", milestone_index=3,
                           transaction_id="t3"),
            tx_id="t3-commit",
        )
        journal_io.write_journal_commit_marker(p3.journal_root, p3.tx_id)
        replay_acceptance_commit_journal(p3.journal_root)
        assert _cursor(p3.state_path) == 3

        # Normal commit of a lower-index milestone (state loaded from disk).
        p1 = _prepare_commit(
            plan_dir,
            _make_snapshot(milestone_label="m1", milestone_index=1,
                           transaction_id="t1"),
            tx_id="t1-commit",
        )
        res = commit_acceptance_commit(p1)
        assert res.committed is True
        assert _cursor(p3.state_path) == 3  # cursor did NOT regress to 1

        state = ChainState.from_dict(json.loads(p3.state_path.read_text()))
        assert {"m3", "m1"} <= {c["label"] for c in state.completed}


# ===========================================================================
# 7. Exactly-once completion records + cursor advancement
# ===========================================================================


class TestExactlyOnceCompletion:
    """Re-committing (retry / replay) the same milestone must yield exactly
    one completion record and advance the cursor exactly once."""

    def test_recommit_same_milestone_single_completion_record(self, tmp_path):
        plan_dir = _bootstrap_plan_dir(tmp_path)
        plan = _prepare_commit(plan_dir, _make_snapshot())
        commit_acceptance_commit(plan)

        state_path = plan.state_path
        first_bytes = state_path.read_bytes()
        first_rec = [
            c for c in json.loads(first_bytes).get("completed", [])
            if c["label"] == "m5a"
        ]
        assert len(first_rec) == 1

        # Re-stage the SAME milestone (fresh boundary run, same snapshot).
        plan2 = _prepare_commit(plan_dir, _make_snapshot())
        res = commit_acceptance_commit(plan2)
        assert res.committed is True

        recs = [
            c for c in json.loads(state_path.read_text()).get("completed", [])
            if c["label"] == "m5a"
        ]
        assert len(recs) == 1  # exactly one, replaced not duplicated

    def test_recommit_same_milestone_cursor_advances_once(self, tmp_path):
        plan_dir = _bootstrap_plan_dir(tmp_path)
        plan = _prepare_commit(plan_dir, _make_snapshot())
        commit_acceptance_commit(plan)
        assert _cursor(plan.state_path) == 3

        for _ in range(3):
            plan_retry = _prepare_commit(plan_dir, _make_snapshot())
            commit_acceptance_commit(plan_retry)

        assert _cursor(plan.state_path) == 3  # never above

    def test_replay_committed_tx_does_not_duplicate_record(self, tmp_path):
        """After a clean commit, calling recovery (which finds no pending
        transactions) must leave the single completion record intact."""
        plan_dir = _bootstrap_plan_dir(tmp_path)
        plan = _prepare_commit(plan_dir, _make_snapshot())
        commit_acceptance_commit(plan)

        before = json.loads(plan.state_path.read_text())
        for _ in range(5):
            replay_acceptance_commit_journal(plan.journal_root)
        after = json.loads(plan.state_path.read_text())

        m5a_before = [c for c in before["completed"] if c["label"] == "m5a"]
        m5a_after = [c for c in after["completed"] if c["label"] == "m5a"]
        assert len(m5a_after) == 1
        assert len(m5a_before) == 1
        assert before["current_milestone_index"] == after["current_milestone_index"]

    def test_duplicate_completion_blocked_by_completed_cursor_cas(self, tmp_path):
        """A second driver attempting the same milestone after the first
        committed must fail the CAS guard — no duplicate completion record."""
        plan_dir = _bootstrap_plan_dir(tmp_path)
        plan_a = _prepare_commit(
            plan_dir, _make_snapshot(transaction_id="a"), tx_id="a-commit",
        )
        plan_b = _prepare_commit(
            plan_dir, _make_snapshot(transaction_id="b"), tx_id="b-commit",
        )
        commit_acceptance_commit(plan_a)
        res_b = commit_acceptance_commit(plan_b)
        assert res_b.committed is False

        recs = [
            c for c in json.loads(plan_a.state_path.read_text()).get("completed", [])
            if c["label"] == "m5a"
        ]
        assert len(recs) == 1


# ===========================================================================
# 8. Fail-closed invariants — no early executed/completed/merge-ready state
# ===========================================================================


class TestFailClosedInvariants:
    """Invariant: prior state is byte-identical after a failed commit, and no
    completion evidence leaks for a non-accepted boundary."""

    def test_cas_failure_leaves_prior_state_byte_identical(self, tmp_path):
        plan_dir = _bootstrap_plan_dir(tmp_path)
        seed = _prepare_commit(
            plan_dir, _make_snapshot(milestone_label="m0", milestone_index=0),
            tx_id="seed-commit",
        )
        commit_acceptance_commit(seed)
        prior_bytes = seed.state_path.read_bytes()

        # Attempt a commit with a deliberately wrong prior hash.
        bad = _prepare_commit(
            plan_dir,
            _make_snapshot(transaction_id="bad", milestone_index=1),
            expected_prior_state_sha256="sha256:" + "9" * 64,
            tx_id="bad-commit",
        )
        res = commit_acceptance_commit(bad)
        assert res.committed is False
        # Prior state untouched.
        assert seed.state_path.read_bytes() == prior_bytes

    def test_non_accepted_boundary_does_not_stage(self, tmp_path):
        """A boundary result with accepted=False must never prepare a commit
        (fail-closed precondition gate)."""
        plan_dir = _bootstrap_plan_dir(tmp_path)
        from arnold_pipelines.megaplan.orchestration.completion_io import (
            prepare_acceptance_commit,
        )

        with pytest.raises(ValueError):
            prepare_acceptance_commit(
                plan_dir=plan_dir,
                spec_path=plan_dir / "chain_spec.yaml",
                result=_make_result(accepted=False),
                state=ChainState(),
            )
        # Nothing on disk.
        assert not any((plan_dir).rglob("*.prepare.json"))

    def test_target_absent_on_existing_state_blocks(self, tmp_path):
        """If the state already exists, a ``target_absent`` guard (fresh-chain
        assumption) must block — proving the guard reflects reality."""
        plan_dir = _bootstrap_plan_dir(tmp_path)
        seed = _prepare_commit(
            plan_dir, _make_snapshot(milestone_label="m0", milestone_index=0),
            tx_id="seed-commit",
        )
        commit_acceptance_commit(seed)

        # Force target_absent by passing a stale snapshot that would re-create.
        plan = _prepare_commit(
            plan_dir,
            _make_snapshot(transaction_id="fresh", milestone_label="m1",
                           milestone_index=1),
            tx_id="fresh-commit",
        )
        # After seed, the on-disk hash is used; manually corrupt the guard.
        payload = journal_io.read_json(plan.prepare_path)
        for w in payload.get("writes", []):
            if plan.state_path.name in w.get("target_path", ""):
                w.pop("expected_prior_sha256", None)
                w["target_absent"] = True
        journal_io.atomic_write_json(plan.prepare_path, payload)

        res = commit_acceptance_commit(plan)
        assert res.committed is False
        assert res.violations
