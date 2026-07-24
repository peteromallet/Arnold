"""Focused prerequisite tests for M6 verify_m6_prerequisites tool.

Covers:
- Stale M5 bound head (bound head exists but is not current HEAD)
- WBC ancestry failure (parent not ancestor of HEAD)
- WBC parent mismatch (evidence parents don't match git merge commit)
- Missing attestation (M5 final attestation file missing)
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path
from unittest import mock

import pytest

# Module under test
from tools.verify_m6_prerequisites import (
    ACTIVATION_EVIDENCE_PATH,
    ALL_WBC_FILES,
    check_activation_receipt_evidence,
    check_current_head,
    check_m5_bound_head_vs_current_head,
    check_m5_final_attestation,
    check_m5_milestone_attestation,
    check_m5_reconciliation_artifacts,
    check_wbc_ancestry,
    check_wbc_file_hashes,
    check_wbc_merge_evidence,
    check_wbc_package_metadata,
    commit_exists,
    current_head,
    is_ancestor,
    merge_parents,
    run_all_checks,
    WBC_INTEGRATION_COMMIT,
    M5_FINAL_ATTESTATION,
    M5_ATTESTATION,
    M5_HANDOFF_DIR,
    WBC_MERGE_EVIDENCE,
    REPO_ROOT,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_final_attestation_dict(
    bound_head: str = "8bb779dcaa08edcc92736eb265689ad894d8d839",
    retirement_status: str = "completed",
    bound_artifacts: dict | None = None,
) -> dict:
    """Build a minimal but well-formed M5 final attestation dict."""
    return {
        "schema": "m5.final-attestation.v2",
        "generated_at": "2026-07-14T20:27:36.310029Z",
        "canonical_initiative": "runauthority-epic",
        "canonical_session": "runauthority-epic-cloud",
        "superseded_by": "custody-control-plane",
        "repository_subject_head": bound_head,
        "retirement_status": retirement_status,
        "gates": {
            "accepted_receipts": 3,
            "verified_milestones": 3,
            "divergence_count": 0,
            "canonical_manifest_sha256": (
                "d1c5e318a15a5d8bc28d9bcf24fe593d"
                "9fbf9b0ddfd43c0ccb81126834210e55"
            ),
            "retired_marker_sha256": (
                "b3b082eb91c578c569a7c6f2237c7da6"
                "84a0a43a92b7589e23869d17d4bcb1d8"
            ),
            "review_gate": "owned_by_current_megaplan_review_evidence",
            "full_suite_collection_errors": 0,
        },
        "bound_artifacts": bound_artifacts or {},
        "unresolved_evidence": [],
        "notes": [],
    }


# ---------------------------------------------------------------------------
# Stale M5 bound head
# ---------------------------------------------------------------------------


class TestStaleM5BoundHead:
    """M5 bound head exists but is not current HEAD (SD1: mismatch → INCOHERENT)."""

    def test_mismatch_but_ancestor_yields_incoherent(self, tmp_path: Path) -> None:
        """When bound head != HEAD but bound head is ancestor → INCOHERENT."""
        attestation = _make_final_attestation_dict(
            bound_head="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        )

        with mock.patch(
            "tools.verify_m6_prerequisites._read_json",
            return_value=attestation,
        ), mock.patch(
            "tools.verify_m6_prerequisites.current_head",
            return_value="bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
        ), mock.patch(
            "tools.verify_m6_prerequisites.commit_exists",
            return_value=True,
        ), mock.patch(
            "tools.verify_m6_prerequisites.is_ancestor",
            return_value=True,
        ):
            result = check_m5_bound_head_vs_current_head()
            assert result["status"] == "INCOHERENT"
            assert result["m5_is_ancestor_of_head"] is True
            assert result["exact_match"] is False

    def test_mismatch_and_not_ancestor_yields_blocked(self) -> None:
        """When bound head != HEAD and NOT ancestor → BLOCKED."""
        attestation = _make_final_attestation_dict(
            bound_head="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        )

        with mock.patch(
            "tools.verify_m6_prerequisites._read_json",
            return_value=attestation,
        ), mock.patch(
            "tools.verify_m6_prerequisites.current_head",
            return_value="bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
        ), mock.patch(
            "tools.verify_m6_prerequisites.commit_exists",
            return_value=True,
        ), mock.patch(
            "tools.verify_m6_prerequisites.is_ancestor",
            return_value=False,
        ):
            result = check_m5_bound_head_vs_current_head()
            assert result["status"] == "BLOCKED"
            assert result["m5_is_ancestor_of_head"] is False

    def test_stale_bound_head_not_in_repo(self) -> None:
        """When bound head doesn't exist in repo → INCOHERENT."""
        attestation = _make_final_attestation_dict(
            bound_head="deadbeefdeadbeefdeadbeefdeadbeefdeadbeef",
        )

        with mock.patch(
            "tools.verify_m6_prerequisites._read_json",
            return_value=attestation,
        ), mock.patch(
            "tools.verify_m6_prerequisites.current_head",
            return_value="bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
        ), mock.patch(
            "tools.verify_m6_prerequisites.commit_exists",
            return_value=False,
        ):
            result = check_m5_bound_head_vs_current_head()
            assert result["status"] == "INCOHERENT"
            assert "does not exist" in result.get("detail", "")


# ---------------------------------------------------------------------------
# WBC ancestry failure
# ---------------------------------------------------------------------------


class TestWBCAncestryFailure:
    """WBC merge parents are not ancestors of current HEAD."""

    @staticmethod
    def _make_evidence_file(tmp_path: Path, content: str) -> Path:
        """Create a temporary WBC merge evidence file with given content."""
        f = tmp_path / "wbc-merge-evidence.md"
        f.write_text(content, encoding="utf-8")
        return f

    def test_first_parent_not_ancestor(self, tmp_path: Path) -> None:
        """When first parent is not an ancestor of HEAD → INCOHERENT."""
        evidence_content = (
            "# WBC merge evidence\n\n"
            "- Integration commit: `1111111111111111111111111111111111111111`\n"
            "- First parent: `2222222222222222222222222222222222222222`\n"
            "- Second parent: `3333333333333333333333333333333333333333`\n"
        )
        evidence_file = self._make_evidence_file(tmp_path, evidence_content)

        with mock.patch(
            "tools.verify_m6_prerequisites.WBC_MERGE_EVIDENCE", evidence_file
        ), mock.patch(
            "tools.verify_m6_prerequisites.current_head",
            return_value="bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
        ), mock.patch(
            "tools.verify_m6_prerequisites.commit_exists",
            return_value=True,
        ), mock.patch(
            "tools.verify_m6_prerequisites.is_ancestor",
            side_effect=lambda maybe, desc: maybe != "2222222222222222222222222222222222222222",
        ):
            result = check_wbc_ancestry()
            assert result["status"] == "INCOHERENT"
            assert "ancestry_issues" in result
            assert any(
                "first_parent" in issue
                for issue in result.get("ancestry_issues", [])
            )

    def test_both_parents_not_ancestors(self, tmp_path: Path) -> None:
        """When both parents are not ancestors → INCOHERENT."""
        evidence_content = (
            "# WBC merge evidence\n\n"
            "- Integration commit: `1111111111111111111111111111111111111111`\n"
            "- First parent: `2222222222222222222222222222222222222222`\n"
            "- Second parent: `3333333333333333333333333333333333333333`\n"
        )
        evidence_file = self._make_evidence_file(tmp_path, evidence_content)

        with mock.patch(
            "tools.verify_m6_prerequisites.WBC_MERGE_EVIDENCE", evidence_file
        ), mock.patch(
            "tools.verify_m6_prerequisites.current_head",
            return_value="bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
        ), mock.patch(
            "tools.verify_m6_prerequisites.commit_exists",
            return_value=True,
        ), mock.patch(
            "tools.verify_m6_prerequisites.is_ancestor",
            return_value=False,
        ):
            result = check_wbc_ancestry()
            assert result["status"] == "INCOHERENT"
            assert len(result.get("ancestry_issues", [])) >= 2

    def test_missing_evidence_file_blocks_ancestry_check(self, tmp_path: Path) -> None:
        """When WBC merge evidence file is missing → BLOCKED."""
        missing = tmp_path / "nonexistent.md"
        with mock.patch(
            "tools.verify_m6_prerequisites.WBC_MERGE_EVIDENCE", missing
        ):
            result = check_wbc_ancestry()
            assert result["status"] == "BLOCKED"


# ---------------------------------------------------------------------------
# WBC parent mismatch
# ---------------------------------------------------------------------------


class TestWBCParentMismatch:
    """WBC merge evidence parents don't match git merge commit actual parents."""

    @staticmethod
    def _make_evidence_file(tmp_path: Path, content: str) -> Path:
        f = tmp_path / "wbc-merge-evidence.md"
        f.write_text(content, encoding="utf-8")
        return f

    def test_first_parent_not_in_actual_parents(self, tmp_path: Path) -> None:
        """When first parent from evidence is not in git actual parents → INCOHERENT."""
        evidence_content = (
            "# WBC merge evidence\n\n"
            "- Integration commit: `1111111111111111111111111111111111111111`\n"
            "- First parent: `9999999999999999999999999999999999999999`\n"
            "- Second parent: `3333333333333333333333333333333333333333`\n"
        )
        evidence_file = self._make_evidence_file(tmp_path, evidence_content)

        real_parents = [
            "2222222222222222222222222222222222222222",
            "3333333333333333333333333333333333333333",
        ]

        with mock.patch(
            "tools.verify_m6_prerequisites.WBC_MERGE_EVIDENCE", evidence_file
        ), mock.patch(
            "tools.verify_m6_prerequisites.commit_exists",
            return_value=True,
        ), mock.patch(
            "tools.verify_m6_prerequisites.merge_parents",
            return_value=real_parents,
        ):
            result = check_wbc_merge_evidence()
            assert result["status"] == "INCOHERENT"
            assert "parent_mismatches" in result
            assert any(
                "9999999999999999999999999999999999999999" in m
                for m in result.get("parent_mismatches", [])
            )

    def test_both_parents_mismatch(self, tmp_path: Path) -> None:
        """When neither parent from evidence matches git → INCOHERENT."""
        evidence_content = (
            "# WBC merge evidence\n\n"
            "- Integration commit: `1111111111111111111111111111111111111111`\n"
            "- First parent: `9999999999999999999999999999999999999999`\n"
            "- Second parent: `8888888888888888888888888888888888888888`\n"
        )
        evidence_file = self._make_evidence_file(tmp_path, evidence_content)

        real_parents = [
            "2222222222222222222222222222222222222222",
            "3333333333333333333333333333333333333333",
        ]

        with mock.patch(
            "tools.verify_m6_prerequisites.WBC_MERGE_EVIDENCE", evidence_file
        ), mock.patch(
            "tools.verify_m6_prerequisites.commit_exists",
            return_value=True,
        ), mock.patch(
            "tools.verify_m6_prerequisites.merge_parents",
            return_value=real_parents,
        ):
            result = check_wbc_merge_evidence()
            assert result["status"] == "INCOHERENT"
            assert len(result.get("parent_mismatches", [])) == 2

    def test_not_a_merge_commit(self, tmp_path: Path) -> None:
        """When integration commit is not a merge commit → INCOHERENT."""
        evidence_content = (
            "# WBC merge evidence\n\n"
            "- Integration commit: `1111111111111111111111111111111111111111`\n"
            "- First parent: `2222222222222222222222222222222222222222`\n"
            "- Second parent: `3333333333333333333333333333333333333333`\n"
        )
        evidence_file = self._make_evidence_file(tmp_path, evidence_content)

        with mock.patch(
            "tools.verify_m6_prerequisites.WBC_MERGE_EVIDENCE", evidence_file
        ), mock.patch(
            "tools.verify_m6_prerequisites.commit_exists",
            return_value=True,
        ), mock.patch(
            "tools.verify_m6_prerequisites.merge_parents",
            return_value=["2222222222222222222222222222222222222222"],  # only 1 parent
        ):
            result = check_wbc_merge_evidence()
            assert result["status"] == "INCOHERENT"
            assert "not a merge commit" in result.get("detail", "")


# ---------------------------------------------------------------------------
# Missing attestation
# ---------------------------------------------------------------------------


class TestMissingAttestation:
    """M5 final attestation file is missing or missing critical fields."""

    def test_final_attestation_file_missing(self) -> None:
        """When final-attestation.json is missing → BLOCKED."""
        with mock.patch(
            "tools.verify_m6_prerequisites._read_json",
            return_value=None,
        ):
            result = check_m5_final_attestation()
            assert result["status"] == "BLOCKED"
            assert "missing" in result.get("detail", "").lower()

    def test_final_attestation_missing_bound_head(self) -> None:
        """When attestation lacks repository_subject_head → INCOHERENT."""
        bad_attestation = _make_final_attestation_dict()
        del bad_attestation["repository_subject_head"]

        with mock.patch(
            "tools.verify_m6_prerequisites._read_json",
            return_value=bad_attestation,
        ):
            result = check_m5_final_attestation()
            assert result["status"] == "INCOHERENT"
            assert "repository_subject_head" in result.get("detail", "")

    def test_milestone_attestation_file_missing(self) -> None:
        """When attestation.json is missing → BLOCKED."""
        with mock.patch(
            "tools.verify_m6_prerequisites._read_json",
            return_value=None,
        ):
            result = check_m5_milestone_attestation()
            assert result["status"] == "BLOCKED"
            assert "missing" in result.get("detail", "").lower()

    def test_bound_head_vs_current_head_with_missing_attestation(self) -> None:
        """When final attestation is missing, bound head check → BLOCKED."""
        with mock.patch(
            "tools.verify_m6_prerequisites._read_json",
            return_value=None,
        ):
            result = check_m5_bound_head_vs_current_head()
            assert result["status"] == "BLOCKED"
            assert "unavailable" in result.get("detail", "").lower()


# ---------------------------------------------------------------------------
# EXPLAINED_BENIGN edge cases (T2b)
# ---------------------------------------------------------------------------


class TestExplainedBenignM5Head:
    """Tests for EXPLAINED_BENIGN resolution of M5-to-HEAD advancement."""

    def test_exact_ancestry_match_yields_pass_with_explained_benign(self) -> None:
        """When resolution evidence matches exact bound_head and ancestry → PASS with EXPLAINED_BENIGN."""
        attestation = _make_final_attestation_dict(
            bound_head="8bb779dcaa08edcc92736eb265689ad894d8d839",
        )

        with mock.patch(
            "tools.verify_m6_prerequisites._read_json",
            return_value=attestation,
        ), mock.patch(
            "tools.verify_m6_prerequisites.current_head",
            return_value="904560e44aaa0f6ae59f0834ad062b017666adaa",
        ), mock.patch(
            "tools.verify_m6_prerequisites.commit_exists",
            return_value=True,
        ), mock.patch(
            "tools.verify_m6_prerequisites.is_ancestor",
            return_value=True,
        ), mock.patch(
            "tools.verify_m6_prerequisites._load_resolution",
            return_value={
                "m5_bound_head_relationship": {
                    "m5_bound_head": "8bb779dcaa08edcc92736eb265689ad894d8d839",
                    "m5_is_ancestor_of_head": True,
                    "m6_landed_squash_merge": "3fb5cac558499eba56ec54eeb4e10a96900d362a",
                    "verdict": "Legitimate post-M5 evolution",
                }
            },
        ):
            result = check_m5_bound_head_vs_current_head()
            assert result["status"] == "PASS"
            assert result.get("resolution_class") == "EXPLAINED_BENIGN"
            assert result["exact_match"] is False
            assert result["m5_is_ancestor_of_head"] is True

    def test_stale_resolution_bound_head_mismatch_yields_incoherent(self) -> None:
        """When resolution refers to a different bound_head → INCOHERENT (stale evidence)."""
        attestation = _make_final_attestation_dict(
            bound_head="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        )

        with mock.patch(
            "tools.verify_m6_prerequisites._read_json",
            return_value=attestation,
        ), mock.patch(
            "tools.verify_m6_prerequisites.current_head",
            return_value="bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
        ), mock.patch(
            "tools.verify_m6_prerequisites.commit_exists",
            return_value=True,
        ), mock.patch(
            "tools.verify_m6_prerequisites.is_ancestor",
            return_value=True,
        ), mock.patch(
            "tools.verify_m6_prerequisites._load_resolution",
            return_value={
                "m5_bound_head_relationship": {
                    "m5_bound_head": "cccccccccccccccccccccccccccccccccccccccc",
                    "m5_is_ancestor_of_head": True,
                    "m6_landed_squash_merge": "3fb5cac558499eba56ec54eeb4e10a96900d362a",
                    "verdict": "Stale resolution for a different bound_head",
                }
            },
        ):
            result = check_m5_bound_head_vs_current_head()
            assert result["status"] == "INCOHERENT"
            assert "resolution_class" not in result

    def test_divergent_history_landed_merge_not_ancestor_yields_incoherent(self) -> None:
        """When landed squash merge is no longer ancestor → INCOHERENT (divergent history)."""
        attestation = _make_final_attestation_dict(
            bound_head="8bb779dcaa08edcc92736eb265689ad894d8d839",
        )

        def _is_ancestor_side_effect(maybe_ancestor, descendant):
            # M5 is ancestor of HEAD, but landed merge is NOT
            if maybe_ancestor == "8bb779dcaa08edcc92736eb265689ad894d8d839":
                return True
            if maybe_ancestor == "3fb5cac558499eba56ec54eeb4e10a96900d362a":
                return False
            return True

        with mock.patch(
            "tools.verify_m6_prerequisites._read_json",
            return_value=attestation,
        ), mock.patch(
            "tools.verify_m6_prerequisites.current_head",
            return_value="904560e44aaa0f6ae59f0834ad062b017666adaa",
        ), mock.patch(
            "tools.verify_m6_prerequisites.commit_exists",
            return_value=True,
        ), mock.patch(
            "tools.verify_m6_prerequisites.is_ancestor",
            side_effect=_is_ancestor_side_effect,
        ), mock.patch(
            "tools.verify_m6_prerequisites._load_resolution",
            return_value={
                "m5_bound_head_relationship": {
                    "m5_bound_head": "8bb779dcaa08edcc92736eb265689ad894d8d839",
                    "m5_is_ancestor_of_head": True,
                    "m6_landed_squash_merge": "3fb5cac558499eba56ec54eeb4e10a96900d362a",
                    "verdict": "Legitimate post-M5 evolution",
                }
            },
        ):
            result = check_m5_bound_head_vs_current_head()
            assert result["status"] == "INCOHERENT"
            assert "resolution_class" not in result

    def test_missing_resolution_ancestor_mismatch_yields_incoherent(self) -> None:
        """When bound_head is ancestor but no resolution → INCOHERENT."""
        attestation = _make_final_attestation_dict(
            bound_head="8bb779dcaa08edcc92736eb265689ad894d8d839",
        )

        with mock.patch(
            "tools.verify_m6_prerequisites._read_json",
            return_value=attestation,
        ), mock.patch(
            "tools.verify_m6_prerequisites.current_head",
            return_value="bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
        ), mock.patch(
            "tools.verify_m6_prerequisites.commit_exists",
            return_value=True,
        ), mock.patch(
            "tools.verify_m6_prerequisites.is_ancestor",
            return_value=True,
        ), mock.patch(
            "tools.verify_m6_prerequisites._load_resolution",
            return_value=None,  # No resolution available
        ):
            result = check_m5_bound_head_vs_current_head()
            assert result["status"] == "INCOHERENT"
            assert "resolution_class" not in result


class TestExplainedBenignSourceCompiler:
    """Tests for EXPLAINED_BENIGN resolution of source_compiler.py mismatch."""

    def test_source_compiler_exact_hashes_yield_explained_benign(self) -> None:
        """When resolution hashes match current/merge exactly → EXPLAINED_BENIGN."""
        current_hash = "5e1f56262810790966696a7720e93fa0bccaabfe4085e70fa76bb0fd64eb7186"
        merge_hash = "0f41737c72b6f798f929623c2d650723166f45fc1c683082ea173e83f2aa16d5"
        modifying_sha = "4d1f22dbbd20efb9c246ed461f65b3cd57d91090"

        resolution = {
            "source_compiler_mismatch_investigation": {
                "status": "explained_and_benign",
                "current_sha256": current_hash,
                "merge_sha256": merge_hash,
                "modifying_commit": {
                    "sha": modifying_sha,
                    "subject": "fix(workflow): retain missing boundary contract diagnostics",
                    "is_ancestor_of_head": True,
                },
                "change_analysis": {
                    "wbc_owner_aligned": True,
                },
                "verdict": "Legitimate WBC-owned post-merge evolution",
            }
        }

        from tools.verify_m6_prerequisites import _check_source_compiler_explained

        with mock.patch(
            "tools.verify_m6_prerequisites.commit_exists",
            return_value=True,
        ), mock.patch(
            "tools.verify_m6_prerequisites.is_ancestor",
            return_value=True,
        ), mock.patch(
            "tools.verify_m6_prerequisites.current_head",
            return_value="904560e44aaa0f6ae59f0834ad062b017666adaa",
        ):
            result = _check_source_compiler_explained(current_hash, merge_hash, resolution)
            assert result is not None
            assert result["resolution_class"] == "EXPLAINED_BENIGN"
            assert result["modifying_commit"] == modifying_sha

    def test_altered_source_bytes_different_current_hash_yields_none(self) -> None:
        """When current_hash in resolution doesn't match actual → None (no resolution)."""
        current_hash_actual = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
        merge_hash_actual = "0f41737c72b6f798f929623c2d650723166f45fc1c683082ea173e83f2aa16d5"
        modifying_sha = "4d1f22dbbd20efb9c246ed461f65b3cd57d91090"

        resolution = {
            "source_compiler_mismatch_investigation": {
                "status": "explained_and_benign",
                "current_sha256": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
                "merge_sha256": merge_hash_actual,
                "modifying_commit": {
                    "sha": modifying_sha,
                    "subject": "fix",
                    "is_ancestor_of_head": True,
                },
                "change_analysis": {"wbc_owner_aligned": True},
                "verdict": "something",
            }
        }

        from tools.verify_m6_prerequisites import _check_source_compiler_explained

        with mock.patch(
            "tools.verify_m6_prerequisites.commit_exists",
            return_value=True,
        ), mock.patch(
            "tools.verify_m6_prerequisites.is_ancestor",
            return_value=True,
        ), mock.patch(
            "tools.verify_m6_prerequisites.current_head",
            return_value="904560e44aaa0f6ae59f0834ad062b017666adaa",
        ):
            result = _check_source_compiler_explained(current_hash_actual, merge_hash_actual, resolution)
            assert result is None

    def test_modified_by_non_ancestor_yields_none(self) -> None:
        """When modifying commit is not ancestor of HEAD → None."""
        current_hash = "5e1f56262810790966696a7720e93fa0bccaabfe4085e70fa76bb0fd64eb7186"
        merge_hash = "0f41737c72b6f798f929623c2d650723166f45fc1c683082ea173e83f2aa16d5"
        modifying_sha = "4d1f22dbbd20efb9c246ed461f65b3cd57d91090"

        resolution = {
            "source_compiler_mismatch_investigation": {
                "status": "explained_and_benign",
                "current_sha256": current_hash,
                "merge_sha256": merge_hash,
                "modifying_commit": {
                    "sha": modifying_sha,
                    "subject": "fix",
                    "is_ancestor_of_head": True,
                },
                "change_analysis": {"wbc_owner_aligned": True},
                "verdict": "something",
            }
        }

        from tools.verify_m6_prerequisites import _check_source_compiler_explained

        with mock.patch(
            "tools.verify_m6_prerequisites.commit_exists",
            return_value=True,
        ), mock.patch(
            "tools.verify_m6_prerequisites.is_ancestor",
            return_value=False,  # modifying commit NOT ancestor
        ), mock.patch(
            "tools.verify_m6_prerequisites.current_head",
            return_value="904560e44aaa0f6ae59f0834ad062b017666adaa",
        ):
            result = _check_source_compiler_explained(current_hash, merge_hash, resolution)
            assert result is None

    def test_wbc_owner_not_aligned_yields_none(self) -> None:
        """When change_analysis.wbc_owner_aligned is False → None."""
        current_hash = "5e1f56262810790966696a7720e93fa0bccaabfe4085e70fa76bb0fd64eb7186"
        merge_hash = "0f41737c72b6f798f929623c2d650723166f45fc1c683082ea173e83f2aa16d5"
        modifying_sha = "4d1f22dbbd20efb9c246ed461f65b3cd57d91090"

        resolution = {
            "source_compiler_mismatch_investigation": {
                "status": "explained_and_benign",
                "current_sha256": current_hash,
                "merge_sha256": merge_hash,
                "modifying_commit": {
                    "sha": modifying_sha,
                    "subject": "fix",
                    "is_ancestor_of_head": True,
                },
                "change_analysis": {"wbc_owner_aligned": False},
                "verdict": "something",
            }
        }

        from tools.verify_m6_prerequisites import _check_source_compiler_explained

        with mock.patch(
            "tools.verify_m6_prerequisites.commit_exists",
            return_value=True,
        ), mock.patch(
            "tools.verify_m6_prerequisites.is_ancestor",
            return_value=True,
        ), mock.patch(
            "tools.verify_m6_prerequisites.current_head",
            return_value="904560e44aaa0f6ae59f0834ad062b017666adaa",
        ):
            result = _check_source_compiler_explained(current_hash, merge_hash, resolution)
            assert result is None


class TestExplainedBenignV2Matrices:
    """Tests for V2 matrix delta EXPLAINED_BENIGN classification."""

    def test_known_v2_matrix_with_v2_schema_yields_explained_benign(self, tmp_path: Path) -> None:
        """When a file is in V2_MATRIX_FILES and has v2 schema → EXPLAINED_BENIGN."""
        matrix_file = tmp_path / "source_to_owner_matrix.json"
        matrix_file.parent.mkdir(parents=True, exist_ok=True)
        matrix_file.write_text(json.dumps({
            "meta": {"schema_version": "v2"},
            "data": {"rows": []},
        }))

        from tools.verify_m6_prerequisites import _check_v2_matrix_delta, V2_MATRIX_FILES

        with mock.patch(
            "tools.verify_m6_prerequisites.REPO_ROOT", tmp_path
        ), mock.patch(
            "tools.verify_m6_prerequisites.V2_MATRIX_FILES",
            {"source_to_owner_matrix.json"},
        ):
            result = _check_v2_matrix_delta("source_to_owner_matrix.json")
            assert result is not None
            assert result["resolution_class"] == "EXPLAINED_BENIGN"
            assert "v2" in result["resolution_source"] or "cl1" in result["resolution_source"].lower()

    def test_unrecognized_matrix_not_in_v2_set_yields_none(self, tmp_path: Path) -> None:
        """When a file is NOT in V2_MATRIX_FILES → None (unrecognized change)."""
        unknown_file = tmp_path / "unknown_matrix.json"
        unknown_file.parent.mkdir(parents=True, exist_ok=True)
        unknown_file.write_text(json.dumps({
            "meta": {"schema_version": "v2"},
        }))

        from tools.verify_m6_prerequisites import _check_v2_matrix_delta

        with mock.patch(
            "tools.verify_m6_prerequisites.REPO_ROOT", tmp_path
        ), mock.patch(
            "tools.verify_m6_prerequisites.V2_MATRIX_FILES",
            {"source_to_owner_matrix.json"},  # different set
        ):
            result = _check_v2_matrix_delta("unknown_matrix.json")
            assert result is None

    def test_v2_matrix_without_v2_schema_yields_none(self, tmp_path: Path) -> None:
        """When a V2_MATRIX_FILES entry has v1 schema → None (content doesn't match)."""
        matrix_file = tmp_path / "contract_to_producer_matrix.json"
        matrix_file.parent.mkdir(parents=True, exist_ok=True)
        matrix_file.write_text(json.dumps({
            "meta": {"schema_version": "v1"},
            "data": {"rows": []},
        }))

        from tools.verify_m6_prerequisites import _check_v2_matrix_delta

        with mock.patch(
            "tools.verify_m6_prerequisites.REPO_ROOT", tmp_path
        ), mock.patch(
            "tools.verify_m6_prerequisites.V2_MATRIX_FILES",
            {"contract_to_producer_matrix.json"},
        ):
            result = _check_v2_matrix_delta("contract_to_producer_matrix.json")
            assert result is None

    def test_v2_matrix_file_missing_on_disk_yields_none(self, tmp_path: Path) -> None:
        """When a V2_MATRIX_FILES entry doesn't exist on disk → None."""
        from tools.verify_m6_prerequisites import _check_v2_matrix_delta

        with mock.patch(
            "tools.verify_m6_prerequisites.REPO_ROOT", tmp_path
        ), mock.patch(
            "tools.verify_m6_prerequisites.V2_MATRIX_FILES",
            {"nonexistent_matrix.json"},
        ):
            result = _check_v2_matrix_delta("nonexistent_matrix.json")
            assert result is None


class TestExplainedBenignWbcFileHashes:
    """Integration tests: check_wbc_file_hashes with EXPLAINED_BENIGN path."""

    def test_v2_matrix_mismatch_resolved_as_explained_benign(self, tmp_path: Path) -> None:
        """When a v2 matrix file mismatches, it should be classified EXPLAINED_BENIGN."""
        current_content = json.dumps({
            "meta": {"schema_version": "v2"},
            "data": {"rows": [{"test": "row"}]},
        }).encode("utf-8")
        merge_content = json.dumps({
            "meta": {"schema_version": "v1"},
            "data": {"rows": []},
        }).encode("utf-8")
        current_hash = hashlib.sha256(current_content).hexdigest()
        merge_hash = hashlib.sha256(merge_content).hexdigest()

        # Create the v2 matrix file on disk
        matrix_path = tmp_path / "arnold_pipelines" / "megaplan" / "workflows" / "source_to_owner_matrix.json"
        matrix_path.parent.mkdir(parents=True, exist_ok=True)
        matrix_path.write_bytes(current_content)

        with mock.patch(
            "tools.verify_m6_prerequisites.commit_exists",
            return_value=True,
        ), mock.patch(
            "tools.verify_m6_prerequisites.ALL_WBC_FILES",
            ["arnold_pipelines/megaplan/workflows/source_to_owner_matrix.json"],
        ), mock.patch(
            "tools.verify_m6_prerequisites.WBC_BOUNDARY_FILES", []
        ), mock.patch(
            "tools.verify_m6_prerequisites.WBC_RUNTIME_FILES", []
        ), mock.patch(
            "tools.verify_m6_prerequisites.WBC_SCHEMA_FILES",
            ["arnold_pipelines/megaplan/workflows/source_to_owner_matrix.json"],
        ), mock.patch(
            "tools.verify_m6_prerequisites.WBC_SUPPORT_FILES", []
        ), mock.patch(
            "tools.verify_m6_prerequisites._sha256_file",
            return_value=current_hash,
        ), mock.patch(
            "tools.verify_m6_prerequisites.file_content_at_commit",
            return_value=merge_content,
        ), mock.patch(
            "tools.verify_m6_prerequisites._check_v2_matrix_delta",
            return_value={
                "resolution_class": "EXPLAINED_BENIGN",
                "resolution_source": "cl1.v2-matrix-addition",
                "resolution_detail": "CL1 additive declaration: v2",
            },
        ), mock.patch(
            "tools.verify_m6_prerequisites.REPO_ROOT", tmp_path
        ):
            result = check_wbc_file_hashes()
            assert result["status"] == "PASS"
            assert result["summary"]["explained_benign"] == 1
            assert result["summary"]["mismatched"] == 0

    def test_unrecognized_file_mismatch_yields_incoherent(self, tmp_path: Path) -> None:
        """When a non-v2, non-source_compiler file mismatches → INCOHERENT."""
        current_content = b"new content\n"
        merge_content = b"old content\n"
        current_hash = hashlib.sha256(current_content).hexdigest()

        unknown_file = tmp_path / "arnold" / "workflow" / "unknown.py"
        unknown_file.parent.mkdir(parents=True, exist_ok=True)
        unknown_file.write_bytes(current_content)

        with mock.patch(
            "tools.verify_m6_prerequisites.commit_exists",
            return_value=True,
        ), mock.patch(
            "tools.verify_m6_prerequisites.ALL_WBC_FILES",
            ["arnold/workflow/unknown.py"],
        ), mock.patch(
            "tools.verify_m6_prerequisites.WBC_BOUNDARY_FILES",
            ["arnold/workflow/unknown.py"],
        ), mock.patch(
            "tools.verify_m6_prerequisites.WBC_RUNTIME_FILES", []
        ), mock.patch(
            "tools.verify_m6_prerequisites.WBC_SCHEMA_FILES", []
        ), mock.patch(
            "tools.verify_m6_prerequisites.WBC_SUPPORT_FILES", []
        ), mock.patch(
            "tools.verify_m6_prerequisites._sha256_file",
            return_value=current_hash,
        ), mock.patch(
            "tools.verify_m6_prerequisites.file_content_at_commit",
            return_value=merge_content,
        ), mock.patch(
            "tools.verify_m6_prerequisites._check_explained_benign_file",
            return_value=None,  # no resolution
        ), mock.patch(
            "tools.verify_m6_prerequisites.REPO_ROOT", tmp_path
        ):
            result = check_wbc_file_hashes()
            assert result["status"] == "INCOHERENT"
            assert result["summary"]["mismatched"] == 1


# ---------------------------------------------------------------------------
# Integration / aggregate
# ---------------------------------------------------------------------------


class TestRunAllChecks:
    """End-to-end aggregate check produces correct overall status."""

    @staticmethod
    def _make_evidence_file(tmp_path: Path, content: str) -> Path:
        f = tmp_path / "wbc-merge-evidence.md"
        f.write_text(content, encoding="utf-8")
        return f

    def test_all_pass_yields_pass(self, tmp_path: Path) -> None:
        """When all checks pass, overall status is PASS.

        Note: check_wbc_package_metadata and check_activation_receipt_evidence
        always return UNKNOWN per design (editable install / file presence are
        not proofs), so we mock them out to PASS for this aggregate test.
        """
        attestation = _make_final_attestation_dict()

        evidence_content = (
            "# WBC merge evidence\n\n"
            "- Integration commit: `1111111111111111111111111111111111111111`\n"
            "- First parent: `2222222222222222222222222222222222222222`\n"
            "- Second parent: `3333333333333333333333333333333333333333`\n"
        )
        evidence_file = self._make_evidence_file(tmp_path, evidence_content)

        # Create a temp file for each WBC file so hash comparison passes
        wbc_files_dir = tmp_path / "wbc_files"
        wbc_files_dir.mkdir()

        with mock.patch(
            "tools.verify_m6_prerequisites.current_head",
            return_value="8bb779dcaa08edcc92736eb265689ad894d8d839",
        ), mock.patch(
            "tools.verify_m6_prerequisites.commit_exists",
            return_value=True,
        ), mock.patch(
            "tools.verify_m6_prerequisites.is_ancestor",
            return_value=True,
        ), mock.patch(
            "tools.verify_m6_prerequisites.merge_parents",
            return_value=[
                "2222222222222222222222222222222222222222",
                "3333333333333333333333333333333333333333",
            ],
        ), mock.patch(
            "tools.verify_m6_prerequisites._read_json",
            return_value=attestation,
        ), mock.patch(
            "tools.verify_m6_prerequisites.WBC_MERGE_EVIDENCE", evidence_file
        ), mock.patch(
            "tools.verify_m6_prerequisites.check_wbc_package_metadata",
            return_value={"check": "wbc_package_metadata", "status": "PASS"},
        ), mock.patch(
            "tools.verify_m6_prerequisites.check_wbc_file_hashes",
            return_value={"check": "wbc_file_hashes", "status": "PASS"},
        ), mock.patch(
            "tools.verify_m6_prerequisites.check_activation_receipt_evidence",
            return_value={"check": "activation_receipt_evidence", "status": "PASS"},
        ):
            overall, checks = run_all_checks()
            assert overall == "PASS"
            assert len(checks) == 10  # all checks present (7 original + 3 new)

    def test_one_blocked_yields_blocked(self, tmp_path: Path) -> None:
        """When any single check is BLOCKED, overall is BLOCKED."""
        # Make M5 attestation missing (BLOCKED), others PASS
        evidence_content = (
            "# WBC merge evidence\n\n"
            "- Integration commit: `1111111111111111111111111111111111111111`\n"
            "- First parent: `2222222222222222222222222222222222222222`\n"
            "- Second parent: `3333333333333333333333333333333333333333`\n"
        )
        evidence_file = self._make_evidence_file(tmp_path, evidence_content)

        def _read_json_side_effect(path):
            if path == M5_FINAL_ATTESTATION:
                return None  # BLOCKED
            if path == M5_ATTESTATION:
                return {"schema": "m5.milestone-range-attestation.v1", "milestones": []}
            return None

        with mock.patch(
            "tools.verify_m6_prerequisites.current_head",
            return_value="bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
        ), mock.patch(
            "tools.verify_m6_prerequisites.commit_exists",
            return_value=True,
        ), mock.patch(
            "tools.verify_m6_prerequisites.is_ancestor",
            return_value=True,
        ), mock.patch(
            "tools.verify_m6_prerequisites.merge_parents",
            return_value=[
                "2222222222222222222222222222222222222222",
                "3333333333333333333333333333333333333333",
            ],
        ), mock.patch(
            "tools.verify_m6_prerequisites._read_json",
            side_effect=_read_json_side_effect,
        ), mock.patch(
            "tools.verify_m6_prerequisites.WBC_MERGE_EVIDENCE", evidence_file
        ), mock.patch(
            "tools.verify_m6_prerequisites.check_wbc_package_metadata",
            return_value={"check": "wbc_package_metadata", "status": "PASS"},
        ), mock.patch(
            "tools.verify_m6_prerequisites.check_wbc_file_hashes",
            return_value={"check": "wbc_file_hashes", "status": "PASS"},
        ), mock.patch(
            "tools.verify_m6_prerequisites.check_activation_receipt_evidence",
            return_value={"check": "activation_receipt_evidence", "status": "PASS"},
        ):
            overall, checks = run_all_checks()
            assert overall == "BLOCKED"

    def test_one_incoherent_yields_incoherent_when_no_blocked(self, tmp_path: Path) -> None:
        """When INCOHERENT exists but no BLOCKED → overall INCOHERENT."""
        attestation = _make_final_attestation_dict(
            bound_head="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        )

        evidence_content = (
            "# WBC merge evidence\n\n"
            "- Integration commit: `1111111111111111111111111111111111111111`\n"
            "- First parent: `2222222222222222222222222222222222222222`\n"
            "- Second parent: `3333333333333333333333333333333333333333`\n"
        )
        evidence_file = self._make_evidence_file(tmp_path, evidence_content)

        with mock.patch(
            "tools.verify_m6_prerequisites.current_head",
            return_value="bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
        ), mock.patch(
            "tools.verify_m6_prerequisites.commit_exists",
            return_value=True,
        ), mock.patch(
            "tools.verify_m6_prerequisites.is_ancestor",
            return_value=True,  # ancestor but mismatch → INCOHERENT
        ), mock.patch(
            "tools.verify_m6_prerequisites.merge_parents",
            return_value=[
                "2222222222222222222222222222222222222222",
                "3333333333333333333333333333333333333333",
            ],
        ), mock.patch(
            "tools.verify_m6_prerequisites._read_json",
            return_value=attestation,
        ), mock.patch(
            "tools.verify_m6_prerequisites.WBC_MERGE_EVIDENCE", evidence_file
        ), mock.patch(
            "tools.verify_m6_prerequisites.check_wbc_package_metadata",
            return_value={"check": "wbc_package_metadata", "status": "PASS"},
        ), mock.patch(
            "tools.verify_m6_prerequisites.check_wbc_file_hashes",
            return_value={"check": "wbc_file_hashes", "status": "PASS"},
        ), mock.patch(
            "tools.verify_m6_prerequisites.check_activation_receipt_evidence",
            return_value={"check": "activation_receipt_evidence", "status": "PASS"},
        ):
            overall, checks = run_all_checks()
            assert overall == "INCOHERENT"


# ---------------------------------------------------------------------------
# WBC package metadata
# ---------------------------------------------------------------------------


class TestWBCPackageMetadata:
    """Installed/editable package metadata recording."""

    def test_pip_show_parses_correctly(self) -> None:
        """When pip show succeeds, metadata is recorded and status is UNKNOWN."""
        pip_output = (
            "Name: arnold\n"
            "Version: 0.23.0\n"
            "Location: /root/.pyenv/versions/3.11.11/lib/python3.11/site-packages\n"
            "Editable project location: /workspace/custody-control-plane-20260714/Arnold\n"
        )
        with mock.patch(
            "subprocess.run",
            return_value=mock.Mock(
                returncode=0,
                stdout=pip_output,
                stderr="",
            ),
        ), mock.patch(
            "tools.verify_m6_prerequisites.REPO_ROOT",
            Path("/workspace/custody-control-plane-20260714/Arnold"),
        ):
            result = check_wbc_package_metadata()
            assert result["status"] == "UNKNOWN"
            assert result["package_name"] == "arnold"
            assert result["version"] == "0.23.0"
            assert result["is_editable"] is True
            assert result["editable_project_location"] is not None

    def test_pip_unavailable_yields_unknown(self) -> None:
        """When pip is not available, status is UNKNOWN."""
        with mock.patch(
            "subprocess.run",
            side_effect=FileNotFoundError,
        ):
            result = check_wbc_package_metadata()
            assert result["status"] == "UNKNOWN"
            assert "pip not available" in result.get("detail", "")

    def test_pip_show_fails_yields_unknown(self) -> None:
        """When pip show returns non-zero, status is UNKNOWN."""
        with mock.patch(
            "subprocess.run",
            return_value=mock.Mock(
                returncode=1,
                stdout="",
                stderr="Package not found",
            ),
        ):
            result = check_wbc_package_metadata()
            assert result["status"] == "UNKNOWN"
            assert "failed" in result.get("detail", "")


# ---------------------------------------------------------------------------
# WBC file hashes
# ---------------------------------------------------------------------------


class TestWBCFileHashes:
    """WBC file hash comparison against merge tree."""

    def test_all_files_match_yields_pass(self, tmp_path: Path) -> None:
        """When all WBC files match between current and merge tree → PASS."""
        test_content = b"test file content\n"
        test_hash = hashlib.sha256(test_content).hexdigest()

        # Mock all WBC files to exist with matching content
        with mock.patch(
            "tools.verify_m6_prerequisites.commit_exists",
            return_value=True,
        ), mock.patch(
            "tools.verify_m6_prerequisites.ALL_WBC_FILES",
            ["test_file.py"],  # single test file
        ), mock.patch(
            "tools.verify_m6_prerequisites.WBC_BOUNDARY_FILES",
            ["test_file.py"],
        ), mock.patch(
            "tools.verify_m6_prerequisites.WBC_RUNTIME_FILES",
            [],
        ), mock.patch(
            "tools.verify_m6_prerequisites.WBC_SCHEMA_FILES",
            [],
        ), mock.patch(
            "tools.verify_m6_prerequisites.WBC_SUPPORT_FILES",
            [],
        ), mock.patch(
            "tools.verify_m6_prerequisites._sha256_file",
            return_value=test_hash,
        ), mock.patch(
            "tools.verify_m6_prerequisites.file_content_at_commit",
            return_value=test_content,
        ), mock.patch(
            "tools.verify_m6_prerequisites.REPO_ROOT",
            tmp_path,
        ):
            # Create the test file on disk so Path.exists() passes
            (tmp_path / "test_file.py").write_bytes(test_content)
            result = check_wbc_file_hashes()
            assert result["status"] == "PASS"
            assert result["summary"]["matched"] == 1
            assert result["summary"]["mismatched"] == 0

    def test_mismatched_files_yields_incoherent(self, tmp_path: Path) -> None:
        """When files differ between current and merge → INCOHERENT."""
        current_content = b"current content\n"
        merge_content = b"merge content\n"
        current_hash = hashlib.sha256(current_content).hexdigest()

        with mock.patch(
            "tools.verify_m6_prerequisites.commit_exists",
            return_value=True,
        ), mock.patch(
            "tools.verify_m6_prerequisites.ALL_WBC_FILES",
            ["test_file.py"],
        ), mock.patch(
            "tools.verify_m6_prerequisites.WBC_BOUNDARY_FILES",
            ["test_file.py"],
        ), mock.patch(
            "tools.verify_m6_prerequisites.WBC_RUNTIME_FILES",
            [],
        ), mock.patch(
            "tools.verify_m6_prerequisites.WBC_SCHEMA_FILES",
            [],
        ), mock.patch(
            "tools.verify_m6_prerequisites.WBC_SUPPORT_FILES",
            [],
        ), mock.patch(
            "tools.verify_m6_prerequisites._sha256_file",
            return_value=current_hash,
        ), mock.patch(
            "tools.verify_m6_prerequisites.file_content_at_commit",
            return_value=merge_content,
        ), mock.patch(
            "tools.verify_m6_prerequisites.REPO_ROOT",
            tmp_path,
        ):
            (tmp_path / "test_file.py").write_bytes(current_content)
            result = check_wbc_file_hashes()
            assert result["status"] == "INCOHERENT"
            assert result["summary"]["mismatched"] == 1

    def test_missing_current_file_yields_unknown(self, tmp_path: Path) -> None:
        """When file is missing from current tree → UNKNOWN."""
        merge_content = b"merge content\n"

        with mock.patch(
            "tools.verify_m6_prerequisites.commit_exists",
            return_value=True,
        ), mock.patch(
            "tools.verify_m6_prerequisites.ALL_WBC_FILES",
            ["nonexistent.py"],
        ), mock.patch(
            "tools.verify_m6_prerequisites.WBC_BOUNDARY_FILES",
            ["nonexistent.py"],
        ), mock.patch(
            "tools.verify_m6_prerequisites.WBC_RUNTIME_FILES",
            [],
        ), mock.patch(
            "tools.verify_m6_prerequisites.WBC_SCHEMA_FILES",
            [],
        ), mock.patch(
            "tools.verify_m6_prerequisites.WBC_SUPPORT_FILES",
            [],
        ), mock.patch(
            "tools.verify_m6_prerequisites._sha256_file",
            return_value=None,
        ), mock.patch(
            "tools.verify_m6_prerequisites.file_content_at_commit",
            return_value=merge_content,
        ), mock.patch(
            "tools.verify_m6_prerequisites.REPO_ROOT",
            tmp_path,
        ):
            result = check_wbc_file_hashes()
            assert result["status"] == "UNKNOWN"
            assert result["summary"]["missing_current"] == 1

    def test_integration_commit_missing_yields_blocked(self) -> None:
        """When WBC integration commit doesn't exist → BLOCKED."""
        with mock.patch(
            "tools.verify_m6_prerequisites.commit_exists",
            return_value=False,
        ):
            result = check_wbc_file_hashes()
            assert result["status"] == "BLOCKED"


# ---------------------------------------------------------------------------
# Activation receipt evidence
# ---------------------------------------------------------------------------


class TestActivationReceiptEvidence:
    """Activation receipt evidence check — always UNKNOWN."""

    def test_evidence_file_present_yields_unknown(self, tmp_path: Path) -> None:
        """When activation evidence exists → UNKNOWN (not proof)."""
        evidence = tmp_path / "activation-evidence.md"
        evidence.write_text(
            "# Activation evidence\n\n"
            "- landed main: `1fc545cc0c95c933a88fbf5b2556b479d76a31bd`\n"
            "- WBC no-ff merge: `24afce006b9ad20391ac7af10ef67ea0b1774f9f`\n"
            "- pip install -e .\n"
            "- runtime-provenance verifier: ok=true\n"
            "- restart receipt: preserved\n"
        )

        with mock.patch(
            "tools.verify_m6_prerequisites.ACTIVATION_EVIDENCE_PATH", evidence
        ):
            result = check_activation_receipt_evidence()
            assert result["status"] == "UNKNOWN"
            assert result["receipt_present"] is True
            assert "landed_main_sha" in result
            assert result["landed_main_sha"] == (
                "1fc545cc0c95c933a88fbf5b2556b479d76a31bd"
            )
            assert result["mentions_editable_install"] is True
            assert result["mentions_runtime_provenance"] is True
            assert result["mentions_restart_receipt"] is True

    def test_evidence_file_missing_yields_unknown(self) -> None:
        """When activation evidence is missing → UNKNOWN."""
        missing = Path("/tmp/nonexistent-activation-evidence.md")
        with mock.patch(
            "tools.verify_m6_prerequisites.ACTIVATION_EVIDENCE_PATH", missing
        ):
            result = check_activation_receipt_evidence()
            assert result["status"] == "UNKNOWN"
            assert result["receipt_present"] is False
            assert "not found" in result.get("detail", "")

    def test_evidence_file_unreadable_yields_unknown(self, tmp_path: Path) -> None:
        """When activation evidence is unreadable → UNKNOWN."""
        evidence = tmp_path / "activation-evidence.md"
        evidence.write_text("content")
        # Make it unreadable by mocking read_text to raise OSError
        with mock.patch(
            "tools.verify_m6_prerequisites.ACTIVATION_EVIDENCE_PATH", evidence
        ), mock.patch.object(
            Path, "read_text", side_effect=OSError("Permission denied")
        ):
            result = check_activation_receipt_evidence()
            assert result["status"] == "UNKNOWN"
            assert "Cannot read" in result.get("detail", "")
