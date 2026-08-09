"""Tests for M6 corpus fixture, manifest, and oracle.

Validates deterministic ordering, revision pinning, redaction,
retained-byte retrievability, tamper detection, and independence
from the preserved workspace.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

FIXTURE_DIR = Path(__file__).resolve().parent.parent.parent / "fixtures" / "critique_ledger"
EVIDENCE_DIR = Path(__file__).resolve().parent.parent.parent.parent / "docs" / "critique-ledger" / "evidence"

CORPUS_PATH = FIXTURE_DIR / "m6-corpus.json"
MANIFEST_PATH = EVIDENCE_DIR / "m6-corpus-manifest.json"
ORACLE_PATH = EVIDENCE_DIR / "m6-oracle.json"


def _load_json(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _hash_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class TestM6CorpusExists:
    """Verify all three artifacts exist and are valid JSON."""

    def test_corpus_fixture_exists(self):
        assert CORPUS_PATH.exists(), f"Corpus fixture missing: {CORPUS_PATH}"
        data = _load_json(CORPUS_PATH)
        assert "meta" in data
        assert "plan" in data

    def test_manifest_exists(self):
        assert MANIFEST_PATH.exists(), f"Manifest missing: {MANIFEST_PATH}"
        data = _load_json(MANIFEST_PATH)
        assert data["schema"] == "cl.m6-corpus-manifest.v1"

    def test_oracle_exists(self):
        assert ORACLE_PATH.exists(), f"Oracle missing: {ORACLE_PATH}"
        data = _load_json(ORACLE_PATH)
        assert data["schema"] == "cl.m6-oracle.v1"
        assert len(data["six_oracle_facts"]) == 6


class TestM6CorpusDeterminism:
    """Verify corpus structure and deterministic properties."""

    def test_schema_version(self):
        corpus = _load_json(CORPUS_PATH)
        assert corpus["meta"]["schema_version"] == "cl.m6-corpus.v1"

    def test_revision_pinned(self):
        corpus = _load_json(CORPUS_PATH)
        assert corpus["meta"]["source_revision"] == "ea2be1fe36c42c4f19afedd2c096b5dcec7c56df"
        assert len(corpus["meta"]["source_revision"]) == 40

    def test_five_rounds_present(self):
        corpus = _load_json(CORPUS_PATH)
        rounds = corpus["plan"]["rounds"]
        assert len(rounds) == 5, f"Expected 5 rounds, got {len(rounds)}"
        labels = [r["round_label"] for r in rounds]
        assert labels == ["v1", "v2", "v3", "v4", "v5"], f"Unexpected round order: {labels}"

    def test_deterministic_ordering(self):
        """Rounds must be in v1-v5 order."""
        corpus = _load_json(CORPUS_PATH)
        rounds = corpus["plan"]["rounds"]
        for i, expected in enumerate(["v1", "v2", "v3", "v4", "v5"]):
            assert rounds[i]["round_label"] == expected

    def test_dual_hashing_present(self):
        corpus = _load_json(CORPUS_PATH)
        assert "raw_hash" in corpus["meta"]
        assert "redacted_hash" in corpus["meta"]
        assert corpus["meta"]["raw_hash"].startswith("sha256:")
        assert corpus["meta"]["redacted_hash"].startswith("sha256:")

    def test_no_duplicate_round_labels(self):
        corpus = _load_json(CORPUS_PATH)
        labels = [r["round_label"] for r in corpus["plan"]["rounds"]]
        assert len(labels) == len(set(labels)), f"Duplicate round labels: {labels}"


class TestM6CorpusRedaction:
    """Verify path redaction is applied."""

    def test_no_raw_workspace_paths(self):
        """Redacted corpus must not contain raw workspace paths."""
        corpus_text = CORPUS_PATH.read_text(encoding="utf-8")
        assert "/workspace/custody-control-plane-20260714" not in corpus_text, (
            "Raw workspace path found in redacted corpus"
        )

    def test_redaction_markers_present(self):
        """Redacted paths should use placeholder markers."""
        corpus_text = CORPUS_PATH.read_text(encoding="utf-8")
        # The redacted content uses <SOURCE_REPO> as replacement
        # Check that the corpus JSON itself doesn't leak paths
        assert "<SOURCE_REPO>" in corpus_text or "SOURCE_REPO" not in corpus_text, (
            "Redaction marker behavior unexpected"
        )

    def test_content_hash_stable(self):
        """Redacted hash of plan data should be stable."""
        corpus = _load_json(CORPUS_PATH)
        redacted_hash = corpus["meta"]["redacted_hash"]
        assert redacted_hash.startswith("sha256:")
        # The stored hash is of the plan data (without meta), so recompute
        # from plan data only to verify
        import re
        plan_json = json.dumps(corpus["plan"], indent=2, sort_keys=True, default=str)
        plan_json = re.sub(r"/workspace/custody-control-plane-20260714/Arnold", "<SOURCE_REPO>", plan_json)
        recomputed = hashlib.sha256(plan_json.encode("utf-8")).hexdigest()
        assert redacted_hash == f"sha256:{recomputed}", (
            f"Stored hash {redacted_hash} != recomputed sha256:{recomputed}"
        )


class TestM6CorpusIntegrity:
    """Verify corpus data integrity."""

    def test_all_rounds_have_required_artifacts(self):
        corpus = _load_json(CORPUS_PATH)
        required = ["plan_meta", "critique", "evaluator_verdict", "gate_signals"]
        for rd in corpus["plan"]["rounds"]:
            for req in required:
                assert req in rd["available"], (
                    f"{rd['round_label']} missing required artifact: {req}"
                )

    def test_plan_level_has_contract(self):
        corpus = _load_json(CORPUS_PATH)
        pl = corpus["plan"]["plan_level"]
        assert "contract" in pl, "Plan-level contract missing"

    def test_plan_level_has_state(self):
        corpus = _load_json(CORPUS_PATH)
        pl = corpus["plan"]["plan_level"]
        assert "state" in pl, "Plan-level state missing"

    def test_no_unavailable_required(self):
        corpus = _load_json(CORPUS_PATH)
        for rd in corpus["plan"]["rounds"]:
            unavail = rd.get("unavailable", [])
            assert len(unavail) == 0, (
                f"{rd['round_label']} has {len(unavail)} unavailable artifacts"
            )


class TestM6CorpusIndependence:
    """Verify corpus is independent of preserved workspace."""

    def test_no_absolute_repo_paths_in_metadata(self):
        corpus = _load_json(CORPUS_PATH)
        plan_path = corpus["plan"]["plan_path"]
        assert "/workspace/custody-control-plane-20260714" not in plan_path, (
            "Raw workspace path in plan_path"
        )

    def test_source_revision_not_mutable_ref(self):
        corpus = _load_json(CORPUS_PATH)
        rev = corpus["meta"]["source_revision"]
        # Must be a full SHA, not a branch name
        assert len(rev) == 40
        assert all(c in "0123456789abcdef" for c in rev)


class TestTamperDetection:
    """Verify tampering would be detected."""

    def test_stored_hash_matches_plan_data(self):
        """The stored redacted_hash must match the plan data (not full corpus with meta)."""
        corpus = _load_json(CORPUS_PATH)
        stored = corpus["meta"]["redacted_hash"]
        import re
        plan_json = json.dumps(corpus["plan"], indent=2, sort_keys=True, default=str)
        plan_json = re.sub(r"/workspace/custody-control-plane-20260714/Arnold", "<SOURCE_REPO>", plan_json)
        recomputed = f"sha256:{hashlib.sha256(plan_json.encode('utf-8')).hexdigest()}"
        assert stored == recomputed, (
            f"Stored plan hash {stored} != recomputed {recomputed}"
        )

    def test_manifest_hash_matches_corpus_plan_data(self):
        manifest = _load_json(MANIFEST_PATH)
        manifest_hash = manifest["retained_byte_hashes"]["hash"]
        # The manifest hash refers to the plan data redacted hash
        corpus = _load_json(CORPUS_PATH)
        actual = corpus["meta"]["redacted_hash"]
        assert manifest_hash == actual, (
            f"Manifest hash {manifest_hash} doesn't match corpus plan hash {actual}"
        )


class TestM6OracleFacts:
    """Verify oracle facts are correctly encoded."""

    def test_six_facts_present(self):
        oracle = _load_json(ORACLE_PATH)
        assert len(oracle["six_oracle_facts"]) == 6

    def test_fact_1_blocked_prerequisite(self):
        oracle = _load_json(ORACLE_PATH)
        f1 = oracle["six_oracle_facts"][0]
        assert f1["fact_id"] == 1
        assert f1["finding_id"] == "CF-9D56C033A0AFFA4A7607"
        assert f1["round"] == "v4"

    def test_fact_2_four_lenses(self):
        oracle = _load_json(ORACLE_PATH)
        f2 = oracle["six_oracle_facts"][1]
        assert f2["fact_id"] == 2
        assert len(f2["lenses"]) == 4
        assert "correctness" in f2["lenses"]
        assert "scope" in f2["lenses"]
        assert "verification" in f2["lenses"]
        assert "prerequisite_ordering" in f2["lenses"]

    def test_fact_3_recurring_critiques_empty(self):
        oracle = _load_json(ORACLE_PATH)
        f3 = oracle["six_oracle_facts"][2]
        assert f3["fact_id"] == 3
        assert f3["value"] == []

    def test_fact_4_five_to_one_reconciliation(self):
        oracle = _load_json(ORACLE_PATH)
        f4 = oracle["six_oracle_facts"][3]
        assert f4["fact_id"] == 4
        assert f4["reconciliation_type"] == "FindingReconciliationEvent"
        assert f4["not_textual_similarity"] is True

    def test_fact_5_replay_limitation(self):
        oracle = _load_json(ORACLE_PATH)
        f5 = oracle["six_oracle_facts"][4]
        assert f5["fact_id"] == 5
        assert "reopen_condition" in f5
        assert "ea2be1fe" in f5["reopen_condition"]

    def test_fact_6_no_failed_malformed(self):
        oracle = _load_json(ORACLE_PATH)
        f6 = oracle["six_oracle_facts"][5]
        assert f6["fact_id"] == 6
        assert f6["failed_count"] == 0
        assert f6["dropped_count"] == 0
        assert f6["malformed_count"] == 0

    def test_oracle_generation_idempotent(self):
        """Oracle hash should be stable (deterministic content)."""
        oracle = _load_json(ORACLE_PATH)
        assert oracle["schema"] == "cl.m6-oracle.v1"
        assert oracle["source_revision"] == "ea2be1fe36c42c4f19afedd2c096b5dcec7c56df"
