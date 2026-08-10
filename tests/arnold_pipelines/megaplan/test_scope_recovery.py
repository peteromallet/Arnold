from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from arnold_pipelines.megaplan.authority.scope_recovery import (
    ScopeRecoveryConflict,
    ScopeRecoveryRequest,
    claim_successor_generation,
    normalize_recovery_path,
    request_from_receipt,
)


def _request(*, paths: tuple[str, ...] = ("src/a.py",), receipt: str = "receipt-1"):
    return ScopeRecoveryRequest(
        task_id="T7",
        batch_id="B3",
        rejected_attempt_id="attempt-66",
        current_generation=4,
        run_revision="rev-current",
        authority_digest="authority-current",
        pre_attempt_baseline="base-commit",
        landed_tree="landed-commit",
        write_set_version="write-set-v2",
        admitted_paths=paths,
        verification_commands=("pytest tests/test_a.py",),
        receipt_digest=receipt,
    )


def test_scope_amendment_claims_one_verification_only_successor(tmp_path: Path) -> None:
    claim = claim_successor_generation(tmp_path, _request())
    again = claim_successor_generation(tmp_path, _request())

    assert again == claim
    assert claim["generation"] == 5
    assert claim["rejected_attempt_id"] == "attempt-66"
    assert claim["body_execution_allowed"] is False
    assert claim["verification_only"] is True
    journal = json.loads((tmp_path / "task_scope_recovery.json").read_text())
    assert journal["claims"] == [claim]


def test_competing_scope_amendments_have_one_cas_winner(tmp_path: Path) -> None:
    requests = [_request(receipt="receipt-a"), _request(receipt="receipt-b")]

    def claim(request):
        try:
            return ("won", claim_successor_generation(tmp_path, request)["receipt_digest"])
        except ScopeRecoveryConflict:
            return ("lost", request.receipt_digest)

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(claim, requests))

    assert sorted(result[0] for result in results) == ["lost", "won"]
    journal = json.loads((tmp_path / "task_scope_recovery.json").read_text())
    assert len(journal["claims"]) == 1


@pytest.mark.parametrize(
    "path",
    ["/etc/passwd", "../escape.py", "src/../../escape.py", "", ".", "a\x00b"],
)
def test_scope_recovery_rejects_hostile_paths(path: str) -> None:
    with pytest.raises(ValueError):
        normalize_recovery_path(path)


def test_request_binds_baseline_landed_tree_and_current_authority() -> None:
    receipt = {
        "subject_attempt": "attempt-66",
        "plan_revision": "rev-current",
        "tree_commit": "landed-commit",
        "receipt_digest": "receipt-66",
        "test_results": {
            "scope_amendment": {
                "pre_attempt_baseline": "base-commit",
                "write_set_version": "write-set-v2",
                "admitted_paths": ["generated/output.py"],
                "verification_commands": ["pytest tests/test_generated.py"],
            }
        },
    }

    request = request_from_receipt(
        receipt,
        task_id="T30",
        batch_id="B8",
        current_generation=2,
        authority_digest="authority-now",
    )

    assert request is not None
    assert request.pre_attempt_baseline == "base-commit"
    assert request.landed_tree == "landed-commit"
    assert request.authority_digest == "authority-now"
    assert request.admitted_paths == ("generated/output.py",)
