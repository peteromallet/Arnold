from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts import generate_m11_acceptance_receipt as acceptance


COMMIT = "a" * 40
TREE = "b" * 40


def _write(root: Path, relative: str, payload: dict) -> dict[str, str]:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, sort_keys=True) + "\n", encoding="utf-8")
    return {"path": relative, "sha256": acceptance._file_digest(path)}


def _candidate(root: Path) -> dict:
    forced = _write(root, "plan/operator_forced_chain_completion.json", {
        "schema": "arnold.megaplan.operator_forced_chain_completion.v1",
        "reason": "historical forced completion requiring correction",
    })
    aggregate = _write(root, "evidence/aggregate.json", {
        "schema": "m11.cross_contract_acceptance.v1",
        "artifact_validation": {
            name: {"passed": True}
            for name in acceptance.EVIDENCE_NAMES
        },
        "debt_gate": {"passed": True},
        "summary": {
            "blockers": [{"expected_class": "forced_completion_guard"}],
        },
    })
    evidence = {
        name: _write(root, f"evidence/{name}.json", {
            "schema": f"test.{name}.v1",
            "passed": True,
        })
        for name in acceptance.EVIDENCE_NAMES
    }
    proof_map = _write(root, "proof-map.json", {
        "schema": acceptance.PROOF_MAP_SCHEMA,
        "m11": ["evidence/aggregate.json"],
    })
    correction = _write(root, "evidence/correction.json", {
        "schema": acceptance.CORRECTION_SCHEMA,
        "decision": "accepted",
        "fresh": True,
        "forced_completion_sha256": forced["sha256"],
        "aggregate_sha256": aggregate["sha256"],
        "candidate_commit": COMMIT,
        "candidate_tree": TREE,
        "accepted_by": "independent-oracle",
    })
    candidate = {
        "schema": acceptance.CANDIDATE_SCHEMA,
        "decision": "accepted",
        "verifier_identity": "independent-oracle",
        "producer_identities": {
            "repair": ["simple-fixer"],
            "implementation": ["m11-implementation-agent"],
        },
        "candidate_commit": COMMIT,
        "candidate_tree": TREE,
        "forced_completion": forced,
        "aggregate": aggregate,
        "evidence": evidence,
        "proof_map": proof_map,
        "correction_plan_receipt": correction,
    }
    candidate["candidate_sha256"] = acceptance.candidate_digest(candidate)
    return candidate


def _git(_root: Path) -> tuple[str, str, bool]:
    return COMMIT, TREE, True


def test_emits_deterministic_fully_bound_independent_receipt(
    tmp_path: Path,
) -> None:
    candidate = _candidate(tmp_path)
    first = acceptance.build_acceptance_receipt(
        candidate, repo_root=tmp_path, git_state_reader=_git
    )
    second = acceptance.build_acceptance_receipt(
        candidate, repo_root=tmp_path, git_state_reader=_git
    )
    assert first == second
    assert first["schema"] == "m11.acceptance-receipt.v1"
    assert first["decision"] == "accepted"
    assert first["independent_verifier"] is True
    assert first["verifier_identity"] == "independent-oracle"
    assert first["candidate_clean"] is True
    assert set(first["evidence"]) == set(acceptance.EVIDENCE_NAMES)
    assert first["content_sha256"].startswith("sha256:")


def test_rejects_verifier_who_produced_repair(tmp_path: Path) -> None:
    candidate = _candidate(tmp_path)
    candidate["producer_identities"]["repair"].append("independent-oracle")
    candidate["candidate_sha256"] = acceptance.candidate_digest(candidate)
    with pytest.raises(
        acceptance.AcceptanceReceiptError, match="verifier_not_independent"
    ):
        acceptance.build_acceptance_receipt(
            candidate, repo_root=tmp_path, git_state_reader=_git
        )


@pytest.mark.parametrize(
    "state,error",
    [
        ((COMMIT, TREE, False), "candidate_tree_dirty"),
        (("c" * 40, TREE, True), "candidate_commit_mismatch"),
        ((COMMIT, "d" * 40, True), "candidate_tree_mismatch"),
    ],
)
def test_rejects_bad_candidate_git_state(
    tmp_path: Path, state: tuple[str, str, bool], error: str
) -> None:
    candidate = _candidate(tmp_path)
    with pytest.raises(acceptance.AcceptanceReceiptError, match=error):
        acceptance.build_acceptance_receipt(
            candidate,
            repo_root=tmp_path,
            git_state_reader=lambda _root: state,
        )


def test_rejects_any_evidence_digest_mismatch(tmp_path: Path) -> None:
    candidate = _candidate(tmp_path)
    candidate["evidence"]["runtime"]["sha256"] = "sha256:" + "0" * 64
    candidate["candidate_sha256"] = acceptance.candidate_digest(candidate)
    with pytest.raises(
        acceptance.AcceptanceReceiptError,
        match="evidence_runtime_digest_mismatch",
    ):
        acceptance.build_acceptance_receipt(
            candidate, repo_root=tmp_path, git_state_reader=_git
        )


def test_rejects_incomplete_aggregate(tmp_path: Path) -> None:
    candidate = _candidate(tmp_path)
    path = tmp_path / candidate["aggregate"]["path"]
    payload = json.loads(path.read_text())
    payload["artifact_validation"]["audit"]["passed"] = False
    candidate["aggregate"] = _write(
        tmp_path, candidate["aggregate"]["path"], payload
    )
    correction_path = tmp_path / candidate["correction_plan_receipt"]["path"]
    correction = json.loads(correction_path.read_text())
    correction["aggregate_sha256"] = candidate["aggregate"]["sha256"]
    candidate["correction_plan_receipt"] = _write(
        tmp_path, "evidence/correction.json", correction
    )
    candidate["candidate_sha256"] = acceptance.candidate_digest(candidate)
    with pytest.raises(
        acceptance.AcceptanceReceiptError, match="aggregate_incomplete"
    ):
        acceptance.build_acceptance_receipt(
            candidate, repo_root=tmp_path, git_state_reader=_git
        )


def test_forced_state_requires_fresh_accepted_correction(tmp_path: Path) -> None:
    candidate = _candidate(tmp_path)
    path = tmp_path / candidate["correction_plan_receipt"]["path"]
    correction = json.loads(path.read_text())
    correction["fresh"] = False
    candidate["correction_plan_receipt"] = _write(
        tmp_path, "evidence/correction.json", correction
    )
    candidate["candidate_sha256"] = acceptance.candidate_digest(candidate)
    with pytest.raises(
        acceptance.AcceptanceReceiptError,
        match="correction_plan_not_fresh_or_accepted",
    ):
        acceptance.build_acceptance_receipt(
            candidate, repo_root=tmp_path, git_state_reader=_git
        )


def test_rejects_incomplete_proof_map(tmp_path: Path) -> None:
    candidate = _candidate(tmp_path)
    candidate["proof_map"] = _write(tmp_path, "proof-map.json", {
        "schema": acceptance.PROOF_MAP_SCHEMA,
        "m11": [],
    })
    candidate["candidate_sha256"] = acceptance.candidate_digest(candidate)
    with pytest.raises(
        acceptance.AcceptanceReceiptError, match="proof_map_incomplete"
    ):
        acceptance.build_acceptance_receipt(
            candidate, repo_root=tmp_path, git_state_reader=_git
        )


def test_candidate_mismatch_and_nonaccepted_decision_fail_closed(
    tmp_path: Path,
) -> None:
    candidate = _candidate(tmp_path)
    candidate["decision"] = "blocked"
    with pytest.raises(
        acceptance.AcceptanceReceiptError, match="candidate_digest_mismatch"
    ):
        acceptance.build_acceptance_receipt(
            candidate, repo_root=tmp_path, git_state_reader=_git
        )
    candidate["candidate_sha256"] = acceptance.candidate_digest(candidate)
    with pytest.raises(
        acceptance.AcceptanceReceiptError, match="decision_not_accepted"
    ):
        acceptance.build_acceptance_receipt(
            candidate, repo_root=tmp_path, git_state_reader=_git
        )
