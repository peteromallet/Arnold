from __future__ import annotations

import json
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
RECORD = REPO / "docs/megaplan/post-m11-release-evidence-20260731.json"


def _record() -> dict:
    return json.loads(RECORD.read_text(encoding="utf-8"))


def _residuals() -> dict[str, dict]:
    return {item["id"]: item for item in _record()["residuals"]}


def test_release_transport_matches_authorized_direct_cas_path() -> None:
    data = _record()
    residuals = _residuals()

    assert data["record_status"] == "in_progress"
    assert "release-pr" not in residuals
    direct = residuals["direct-main-promotion"]
    assert direct["status"] == "pending"
    contract = direct["required_evidence"].lower()
    for phrase in (
        "non-force",
        "fast-forward",
        "compare-and-swap",
        "no pr",
        "force-with-lease",
    ):
        assert phrase in contract


def test_historical_packages_cannot_satisfy_final_packaging() -> None:
    data = _record()
    final_packaging = _residuals()["final-packaging-artifacts"]

    assert final_packaging["status"] == "pending"
    assert "historical packaging_artifacts cannot satisfy" in final_packaging[
        "required_evidence"
    ].lower()
    assert data["packaging_artifacts"]
    assert all(
        artifact["bound_commit"] != data["authority"]["evidence_cut_commit"]
        for artifact in data["packaging_artifacts"]
    )


def test_cutover_contract_uses_external_seed_snapshot_and_true_post_cutover_gates() -> None:
    residuals = _residuals()
    preflight = residuals["cutover-preflight"]
    promotion = residuals["runtime-selector-promotion"]

    assert preflight["status"] == "pending"
    preflight_contract = preflight["required_evidence"].lower()
    for phrase in (
        "release-specific cloud configuration",
        "external evidence snapshot",
        "outside immutable runtime_src",
        "canonical frozen seed document",
        "terminal-chain",
        "marker rebind",
    ):
        assert phrase in preflight_contract

    assert promotion["status"] == "pending"
    promotion_contract = promotion["required_evidence"].lower()
    for phrase in (
        "cutover lock",
        "guard-rebind",
        "launch seed",
        "atomically update",
        "rollback restores",
    ):
        assert phrase in promotion_contract

    assert residuals["acceptance-tag"]["status"] == "pending"
    assert "cleanup-deletions" not in residuals
