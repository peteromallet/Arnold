from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts import run_m11_lifecycle_correction as correction

COMMIT = "a" * 40
TREE = "b" * 40
RUNTIME = "sha256:" + "c" * 64


def _write(root: Path, relative: str, payload: dict) -> dict[str, str]:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, sort_keys=True) + "\n", encoding="utf-8")
    return {"path": relative, "sha256": correction._file_digest(path)}


def _candidate(root: Path) -> dict:
    forced = _write(root, "plan/operator_forced_chain_completion.json", {
        "schema": "arnold.megaplan.operator_forced_chain_completion.v1",
    })
    aggregate = _write(root, "evidence/aggregate.json", {
        "schema": correction.AGGREGATE_SCHEMA,
        "artifact_validation": {
            "runtime": {"passed": True},
            "audit": {"passed": True},
        },
        "debt_gate": {"passed": True},
        "summary": {
            "blockers": [{"expected_class": "forced_completion_guard"}],
        },
    })
    candidate = {
        "schema": correction.CANDIDATE_SCHEMA,
        "verifier_identity": "independent-oracle",
        "producer_identities": ["repair-agent", "implementation-agent"],
        "candidate_commit": COMMIT,
        "candidate_tree": TREE,
        "runtime_identity_sha256": RUNTIME,
        "forced_completion": forced,
        "aggregate": aggregate,
    }
    candidate["candidate_sha256"] = correction.candidate_digest(candidate)
    return candidate


def _git(_root: Path) -> tuple[str, str, bool]:
    return COMMIT, TREE, True


class FakeLifecycle:
    def __init__(self):
        self.subjects: set[str] = set()
        self.admissions: list[tuple[str, str]] = []
        self.transactions: list[dict] = []

    def subject_exists(self, subject_id: str) -> bool:
        return subject_id in self.subjects

    def admit_verification_subject(self, subject_id: str, idea: str):
        self.subjects.add(subject_id)
        self.admissions.append((subject_id, idea))
        return {"subject_id": subject_id, "api": "supported"}

    def committed_transactions(self, _subject_id: str):
        return list(self.transactions)


def _accepted_tx(candidate: dict) -> dict:
    return {
        "transaction_id": "tx-correction-1",
        "snapshot_hash": candidate["aggregate"]["sha256"],
        "accepted": True,
        "mode": "atomic",
        "tested_commit_ref": COMMIT,
        "tested_runtime_identity": RUNTIME,
        "verdict_ref": "verification-only",
    }


def test_dry_run_preflight_has_no_lifecycle_mutation(tmp_path: Path) -> None:
    lifecycle = FakeLifecycle()
    result = correction.admit(
        _candidate(tmp_path),
        repo_root=tmp_path,
        lifecycle=lifecycle,
        dry_run=True,
        git_state_reader=_git,
    )
    assert result["status"] == "preflight_passed"
    assert result["verification_only"] is True
    assert lifecycle.subjects == set()
    assert lifecycle.admissions == []


def test_admission_uses_supported_api_with_forced_binding(tmp_path: Path) -> None:
    lifecycle = FakeLifecycle()
    candidate = _candidate(tmp_path)
    result = correction.admit(
        candidate,
        repo_root=tmp_path,
        lifecycle=lifecycle,
        dry_run=False,
        git_state_reader=_git,
    )
    assert result["status"] == "admitted"
    assert len(lifecycle.admissions) == 1
    _subject, idea = lifecycle.admissions[0]
    assert "verification only" in idea
    assert candidate["forced_completion"]["sha256"] in idea
    assert "must not implement, repair, deploy, or directly edit" in idea


def test_receipt_requires_one_exact_authoritative_accepted_transaction(
    tmp_path: Path,
) -> None:
    lifecycle = FakeLifecycle()
    candidate = _candidate(tmp_path)
    admission = correction.admit(
        candidate,
        repo_root=tmp_path,
        lifecycle=lifecycle,
        dry_run=False,
        git_state_reader=_git,
    )
    lifecycle.transactions = [_accepted_tx(candidate)]
    first = correction.emit_receipt(
        candidate,
        repo_root=tmp_path,
        lifecycle=lifecycle,
        git_state_reader=_git,
    )
    second = correction.emit_receipt(
        candidate,
        repo_root=tmp_path,
        lifecycle=lifecycle,
        git_state_reader=_git,
    )
    assert first == second
    assert first["schema"] == "m11.lifecycle-correction-plan-receipt.v1"
    assert first["decision"] == "accepted"
    assert first["fresh"] is True
    assert first["verification_only"] is True
    assert first["subject_id"] == admission["subject_id"]
    assert first["forced_completion_sha256"] == candidate["forced_completion"]["sha256"]
    assert first["aggregate_sha256"] == candidate["aggregate"]["sha256"]


def test_rejects_nonindependent_verifier(tmp_path: Path) -> None:
    candidate = _candidate(tmp_path)
    candidate["producer_identities"].append("independent-oracle")
    candidate["candidate_sha256"] = correction.candidate_digest(candidate)
    with pytest.raises(
        correction.LifecycleCorrectionError, match="verifier_not_independent"
    ):
        correction.preflight(
            candidate,
            repo_root=tmp_path,
            lifecycle=FakeLifecycle(),
            git_state_reader=_git,
        )


def test_rejects_dirty_candidate(tmp_path: Path) -> None:
    with pytest.raises(
        correction.LifecycleCorrectionError, match="candidate_tree_dirty"
    ):
        correction.preflight(
            _candidate(tmp_path),
            repo_root=tmp_path,
            lifecycle=FakeLifecycle(),
            git_state_reader=lambda _root: (COMMIT, TREE, False),
        )


def test_rejects_incomplete_aggregate(tmp_path: Path) -> None:
    candidate = _candidate(tmp_path)
    path = tmp_path / candidate["aggregate"]["path"]
    payload = json.loads(path.read_text())
    payload["artifact_validation"]["audit"]["passed"] = False
    candidate["aggregate"] = _write(
        tmp_path, candidate["aggregate"]["path"], payload
    )
    candidate["candidate_sha256"] = correction.candidate_digest(candidate)
    with pytest.raises(
        correction.LifecycleCorrectionError, match="aggregate_incomplete"
    ):
        correction.preflight(
            candidate,
            repo_root=tmp_path,
            lifecycle=FakeLifecycle(),
            git_state_reader=_git,
        )


def test_rejects_existing_subject_on_fresh_admission(tmp_path: Path) -> None:
    candidate = _candidate(tmp_path)
    lifecycle = FakeLifecycle()
    first = correction.preflight(
        candidate,
        repo_root=tmp_path,
        lifecycle=lifecycle,
        git_state_reader=_git,
    )
    lifecycle.subjects.add(first["subject_id"])
    with pytest.raises(
        correction.LifecycleCorrectionError, match="correction_subject_not_fresh"
    ):
        correction.preflight(
            candidate,
            repo_root=tmp_path,
            lifecycle=lifecycle,
            git_state_reader=_git,
        )


@pytest.mark.parametrize("mutation", ["missing", "rejected", "wrong_snapshot", "ambiguous"])
def test_rejects_non_authoritative_transaction(
    tmp_path: Path, mutation: str
) -> None:
    candidate = _candidate(tmp_path)
    lifecycle = FakeLifecycle()
    admitted = correction.admit(
        candidate,
        repo_root=tmp_path,
        lifecycle=lifecycle,
        dry_run=False,
        git_state_reader=_git,
    )
    tx = _accepted_tx(candidate)
    if mutation == "missing":
        lifecycle.transactions = []
    elif mutation == "rejected":
        tx["accepted"] = False
        lifecycle.transactions = [tx]
    elif mutation == "wrong_snapshot":
        tx["snapshot_hash"] = "sha256:" + "0" * 64
        lifecycle.transactions = [tx]
    else:
        lifecycle.transactions = [tx, {**tx, "transaction_id": "tx-2"}]
    assert lifecycle.subject_exists(admitted["subject_id"])
    with pytest.raises(
        correction.LifecycleCorrectionError,
        match="authoritative_accepted_transaction_missing_or_ambiguous",
    ):
        correction.emit_receipt(
            candidate,
            repo_root=tmp_path,
            lifecycle=lifecycle,
            git_state_reader=_git,
        )
