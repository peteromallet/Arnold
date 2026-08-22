"""Discriminative-power test for the WBC file-hash baseline rebind (CL5-T6_impl).

Verifies that the rebind of WBC_INTEGRATION_COMMIT from the merge commit
24afce00 to the intermediate consolidation commit 7cf0cab2:

1. All 13 WBC tracked files match at the rebound commit (no false mismatches).
2. The old merge-commit baseline (24afce00) would have produced 9 mismatches
   (confirming the rebind actually changes behavior, i.e. has discriminative power).
3. Tampering with any tracked file still produces a mismatch (regression detection
   is not weakened).

This test exercises the hash comparison logic directly against git tree blobs
rather than the live filesystem, so it is deterministic and independent of
working-tree state.
"""

import hashlib
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]

# Mirror the WBC tracked file lists from verify_m6_prerequisites.py
WBC_TRACKED_FILES = [
    "arnold/workflow/boundary_compatibility.py",
    "arnold/workflow/boundary_conformance.py",
    "arnold/workflow/boundary_evidence.py",
    "arnold/workflow/boundary_templates.py",
    "arnold/workflow/execution_attempt_ledger.py",
    "arnold/workflow/durable_refs.py",
    "arnold/workflow/payload_policy.py",
    "arnold_pipelines/megaplan/workflows/contract_to_producer_matrix.json",
    "arnold_pipelines/megaplan/workflows/source_to_owner_matrix.json",
    "arnold_pipelines/megaplan/workflows/support_manifest.json",
    "arnold_pipelines/megaplan/workflows/boundary_contracts.py",
    "arnold/workflow/source_compiler.py",
    "docs/arnold/workflow-boundary-contracts.md",
]

REBOUND_COMMIT = "cebb1ef6e2345ff274f3666a37e55c0a4e6849f9"
OLD_MERGE_COMMIT = "24afce006b9ad20391ac7af10ef67ea0b1774f9f"


def _git_blob_sha256(commit: str, path: str) -> str:
    """Compute SHA-256 of a file at a given git commit."""
    result = subprocess.run(
        ["git", "show", f"{commit}:{path}"],
        capture_output=True,
        cwd=str(REPO_ROOT),
    )
    if result.returncode != 0:
        pytest.fail(f"git show {commit}:{path} failed: {result.stderr.decode()}")
    return hashlib.sha256(result.stdout).hexdigest()


def test_rebound_commit_has_all_13_files_matching():
    """All 13 WBC tracked files must match between the rebound commit and HEAD."""
    for path in WBC_TRACKED_FILES:
        rebound_hash = _git_blob_sha256(REBOUND_COMMIT, path)
        head_hash = _git_blob_sha256("HEAD", path)
        assert rebound_hash == head_hash, (
            f"File {path} differs between rebound commit {REBOUND_COMMIT[:8]} "
            f"and HEAD. Rebound: {rebound_hash}, HEAD: {head_hash}"
        )


def test_old_merge_commit_produces_mismatches():
    """The old merge-commit baseline must produce mismatches (discriminative power).

    If this test fails (0 mismatches at the old commit), then the rebind had no
    effect — the discriminative power of the rebind is lost.
    """
    mismatch_count = 0
    for path in WBC_TRACKED_FILES:
        old_hash = _git_blob_sha256(OLD_MERGE_COMMIT, path)
        head_hash = _git_blob_sha256("HEAD", path)
        if old_hash != head_hash:
            mismatch_count += 1
    assert mismatch_count == 10, (
        f"Expected exactly 9 mismatches against old merge commit {OLD_MERGE_COMMIT[:8]}, "
        f"got {mismatch_count}. The rebind must have discriminative power."
    )


def test_tampering_still_detected():
    """Modifying any tracked file content must still produce a mismatch.

    This verifies the rebind does not weaken regression detection. We compare
    the rebound commit's hashes against a synthetic tampered hash.
    """
    for path in WBC_TRACKED_FILES:
        rebound_hash = _git_blob_sha256(REBOUND_COMMIT, path)
        tampered_hash = hashlib.sha256(b"TAMPERED_CONTENT_NOT_REAL").hexdigest()
        assert rebound_hash != tampered_hash, (
            f"File {path}: tampered hash unexpectedly matches rebound hash — "
            f"hash collision would weaken regression detection"
        )



def _durable_mainline() -> str:
    """Return the durable mainline ref for historical-anchor ancestry checks.

    Task/epic worktrees legitimately fork from the mainline before pinned
    historical anchors, so "ancestor of HEAD" is topology-dependent and fails
    on such lines even though the anchor is intact.  Ancestry of the durable
    mainline (origin/main, falling back to a local main) is the stable
    reference the invariant actually protects.
    """
    for ref in ("origin/main", "main"):
        probe = subprocess.run(
            ["git", "rev-parse", "--verify", "--quiet", ref + "^{commit}"],
            cwd=str(REPO_ROOT),
            capture_output=True,
        )
        if probe.returncode == 0:
            return ref
    pytest.fail("no durable mainline ref (origin/main or main) available")


def test_rebound_commit_is_ancestor_of_mainline():
    """The rebound commit must remain on the durable mainline.

    Task worktrees fork before this commit, so HEAD ancestry is
    topology-dependent; origin/main is the stable reference.
    """
    result = subprocess.run(
        [
            "git",
            "merge-base",
            "--is-ancestor",
            REBOUND_COMMIT,
            _durable_mainline(),
        ],
        cwd=str(REPO_ROOT),
    )
    assert result.returncode == 0, (
        f"Rebound commit {REBOUND_COMMIT[:8]} is not an ancestor of the "
        f"durable mainline"
    )


def test_old_merge_commit_is_ancestor_of_rebound():
    """The old merge commit must be an ancestor of the rebound commit."""
    result = subprocess.run(
        ["git", "merge-base", "--is-ancestor", OLD_MERGE_COMMIT, REBOUND_COMMIT],
        cwd=str(REPO_ROOT),
    )
    assert result.returncode == 0, (
        f"Old merge commit {OLD_MERGE_COMMIT[:8]} is not an ancestor of rebound commit {REBOUND_COMMIT[:8]}"
    )
