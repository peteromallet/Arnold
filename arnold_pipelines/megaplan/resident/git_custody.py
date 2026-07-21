"""Deterministic git custody for resident-managed implementation agents.

The resident records the writable target before launch.  The worker still owns
the implementation, but a successful Codex exit is not accepted as completion
until a machine-readable receipt proves isolation, verification, and either
local integration or a launch-time ambiguity gate.
"""

from __future__ import annotations

from collections.abc import Mapping
import hashlib
import json
from pathlib import Path
import subprocess
from typing import Any


GIT_CUSTODY_SCHEMA = "arnold-resident-git-custody-v1"
GIT_CUSTODY_EVIDENCE_SCHEMA = "arnold-resident-git-custody-evidence-v1"
_GIT_POPEN = subprocess.Popen


class GitCustodyError(RuntimeError):
    """The launch target or completion evidence violates git custody."""


def _git(
    path: Path,
    *args: str,
    check: bool = True,
    text: bool = True,
) -> subprocess.CompletedProcess[Any]:
    process = _GIT_POPEN(
        ["git", "-C", str(path), *args],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=text,
    )
    stdout, stderr = process.communicate()
    result = subprocess.CompletedProcess(
        process.args,
        process.returncode,
        stdout=stdout,
        stderr=stderr,
    )
    if check and result.returncode != 0:
        stderr = (
            result.stderr.strip()
            if text
            else result.stderr.decode(errors="replace").strip()
        )
        raise GitCustodyError(f"git {' '.join(args)} failed in {path}: {stderr}")
    return result


def _resolved_git_path(path: Path, value: str) -> str:
    candidate = Path(value)
    if not candidate.is_absolute():
        candidate = path / candidate
    return str(candidate.resolve())


def snapshot_checkout(path: str | Path) -> dict[str, Any]:
    """Capture the bounded launch facts needed to resolve and verify custody."""

    root = Path(path).resolve()
    inside = _git(root, "rev-parse", "--is-inside-work-tree", check=False)
    if inside.returncode != 0 or inside.stdout.strip() != "true":
        return {"path": str(root), "git": False}
    top = Path(_git(root, "rev-parse", "--show-toplevel").stdout.strip()).resolve()
    common_raw = _git(top, "rev-parse", "--git-common-dir").stdout.strip()
    branch_result = _git(top, "symbolic-ref", "-q", "HEAD", check=False)
    upstream_result = _git(
        top,
        "rev-list",
        "--left-right",
        "--count",
        "HEAD...@{upstream}",
        check=False,
    )
    ahead = behind = None
    if upstream_result.returncode == 0:
        counts = upstream_result.stdout.strip().split()
        if len(counts) == 2:
            ahead, behind = (int(value) for value in counts)
    status = _git(
        top,
        "status",
        "--porcelain=v1",
        "-z",
        "--untracked-files=all",
        text=False,
    ).stdout
    return {
        "path": str(top),
        "git": True,
        "repository": _resolved_git_path(top, common_raw),
        "head_revision": _git(top, "rev-parse", "HEAD").stdout.strip(),
        "branch_ref": branch_result.stdout.strip() if branch_result.returncode == 0 else None,
        "dirty": bool(status),
        "status_sha256": hashlib.sha256(status).hexdigest(),
        "upstream_ahead": ahead,
        "upstream_behind": behind,
    }


def resolve_launch_git_custody(
    *,
    project_root: str | Path,
    runtime_root: str | Path,
    evidence_path: str | Path,
) -> dict[str, Any]:
    """Resolve the launch target without treating dirty/divergent state as ambiguity.

    A separate pinned resident worktree in the same repository is authoritative
    for resident-source changes.  Otherwise the attached project branch is the
    target.  Detached candidates have no writable ref and therefore fail closed.
    """

    project = snapshot_checkout(project_root)
    runtime = snapshot_checkout(runtime_root)
    candidates = [
        {
            "role": role,
            "path": item["path"],
            "branch_ref": item.get("branch_ref"),
            "head_revision": item.get("head_revision"),
        }
        for role, item in (("project", project), ("pinned_runtime", runtime))
        if item.get("git")
    ]
    selected: dict[str, Any] | None = None
    reason: str | None = None
    if (
        project.get("git")
        and runtime.get("git")
        and project.get("repository") == runtime.get("repository")
        and runtime.get("branch_ref")
        and runtime.get("path") != project.get("path")
    ):
        selected = runtime
        reason = "pinned_runtime_attached_branch_in_project_repository"
    elif project.get("git") and project.get("branch_ref"):
        selected = project
        reason = "attached_project_branch"

    custody: dict[str, Any] = {
        "schema_version": GIT_CUSTODY_SCHEMA,
        "evidence_path": str(Path(evidence_path).resolve()),
        "launch_checkouts": {"project": project, "pinned_runtime": runtime},
        "candidates": candidates,
    }
    if selected is None:
        refs = ", ".join(
            (
                f"{item['role']}={item.get('branch_ref') or 'detached'}"
                f"@{item.get('head_revision') or 'unknown'}"
            )
            for item in candidates
        ) or "no git checkout candidates"
        custody["target_resolution"] = {
            "status": "ambiguous",
            "gate": (
                "select one writable local target ref and relaunch; candidates: " + refs
            ),
        }
    else:
        custody["target_resolution"] = {
            "status": "resolved",
            "reason": reason,
            "target_path": selected["path"],
            "target_ref": selected["branch_ref"],
            "base_revision": selected["head_revision"],
        }
    return custody


def render_git_custody_contract(custody: Mapping[str, Any]) -> str:
    resolution = custody.get("target_resolution")
    resolution = resolution if isinstance(resolution, Mapping) else {}
    path = custody.get("evidence_path")
    if resolution.get("status") == "resolved":
        target = (
            f"target {resolution.get('target_ref')} at {resolution.get('base_revision')} "
            f"in {resolution.get('target_path')}"
        )
        integration = (
            "The target is unambiguous. Revalidate that ref immediately before integration, "
            "rebase the feature branch if it advanced, and integrate locally with fast-forward-only "
            "or the repository's documented non-destructive method. A dirty/divergent launch checkout "
            "is not an ambiguity and must remain untouched. Only a missing target ref or a target that "
            "moved off the recorded launch base may become blocked_ambiguity after launch. Use the exact "
            "gate template emitted by the contract validator: `recorded target <ref> no longer exists; "
            "retain <commit> and select the replacement writable local target ref` or `recorded target "
            "<ref> moved off launch base <base>; retain <commit> and select the history-reconciliation "
            "target`."
        )
    else:
        target = f"launch target unresolved: {resolution.get('gate')}"
        integration = (
            "Do not integrate. Record integration.status=blocked_ambiguity and copy the exact launch "
            "gate; do not invent a different candidate or infer main."
        )
    return (
        "[Git implementation custody contract — deterministic v1]\n"
        f"- launch resolution: {target}\n"
        f"- durable evidence path: {path}\n"
        "For authorized git-backed execution, create a new clean isolated git worktree and feature "
        "branch from the recorded base; never implement in either launch checkout. Preserve all dirty "
        "and concurrent work. "
        f"{integration} Before finishing, write JSON to the evidence path with schema_version "
        f"{GIT_CUSTODY_EVIDENCE_SCHEMA}; launch_target (target_ref, base_revision); implementation "
        "(worktree_path, branch_ref, base_revision, commit_revision); verification (diff_reviewed=true, "
        "git_diff_check=passed, tests=[{command,status=passed}, ...]); preservation "
        "(launch_checkout_untouched=true); revalidation (target_ref, observed_revision); and integration "
        "(status, target_ref, before_revision, after_revision, gate when blocked). The resident supervisor "
        "checks repository identity, isolation, clean state, ancestry, target containment, and this receipt. "
        "Missing or inconsistent evidence fails the delegated run even if the model process exits zero.\n"
    )


def git_custody_projection(custody: Mapping[str, Any] | None) -> dict[str, Any]:
    """Return the bounded custody facts copied into managed-child event trails."""

    if not isinstance(custody, Mapping):
        return {"available": False, "resolution_status": "missing"}
    resolution = custody.get("target_resolution")
    resolution = resolution if isinstance(resolution, Mapping) else {}
    return {
        "available": True,
        "schema_version": str(custody.get("schema_version") or ""),
        "evidence_path": str(custody.get("evidence_path") or "") or None,
        "resolution_status": str(resolution.get("status") or "unknown"),
        "resolution_reason": str(resolution.get("reason") or "") or None,
        "target_ref": str(resolution.get("target_ref") or "") or None,
        "target_path": str(resolution.get("target_path") or "") or None,
        "base_revision": str(resolution.get("base_revision") or "") or None,
        "gate": str(resolution.get("gate") or "") or None,
    }


def _mapping(value: object, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise GitCustodyError(f"git custody evidence missing object: {field}")
    return value


def _require_equal(actual: object, expected: object, field: str) -> None:
    if actual != expected:
        raise GitCustodyError(
            f"git custody evidence mismatch for {field}: expected {expected!r}, got {actual!r}"
        )


def validate_git_custody_evidence(custody: Mapping[str, Any]) -> dict[str, Any]:
    """Validate a worker receipt against live git state and launch facts."""

    resolution = _mapping(custody.get("target_resolution"), "target_resolution")
    evidence_path = Path(str(custody.get("evidence_path") or "")).resolve()
    try:
        evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError) as exc:
        raise GitCustodyError(f"missing or invalid git custody evidence: {evidence_path}") from exc
    if not isinstance(evidence, dict):
        raise GitCustodyError("git custody evidence must be a JSON object")
    _require_equal(
        evidence.get("schema_version"),
        GIT_CUSTODY_EVIDENCE_SCHEMA,
        "schema_version",
    )

    integration = _mapping(evidence.get("integration"), "integration")
    if resolution.get("status") == "ambiguous":
        _require_equal(integration.get("status"), "blocked_ambiguity", "integration.status")
        _require_equal(integration.get("gate"), resolution.get("gate"), "integration.gate")
        return {"status": "verified_ambiguity_gate", "evidence_path": str(evidence_path)}
    blocked_after_launch = integration.get("status") == "blocked_ambiguity"
    if integration.get("status") not in {"integrated", "blocked_ambiguity"}:
        raise GitCustodyError(
            "resolved launch target requires integration.status 'integrated' or "
            "a provable post-launch ambiguity gate"
        )
    if blocked_after_launch:
        resolved_target_path = Path(str(resolution.get("target_path") or "")).resolve()
        resolved_target_ref = str(resolution.get("target_ref") or "")
        resolved_base = str(resolution.get("base_revision") or "")
        if (
            _git(
                resolved_target_path,
                "merge-base",
                "--is-ancestor",
                resolved_base,
                resolved_target_ref,
                check=False,
            ).returncode
            == 0
        ):
            raise GitCustodyError(
                "launch target was resolved and remains on the recorded lineage; "
                "integration.status must be 'integrated', not an ambiguity gate"
            )

    launch_target = _mapping(evidence.get("launch_target"), "launch_target")
    implementation = _mapping(evidence.get("implementation"), "implementation")
    verification = _mapping(evidence.get("verification"), "verification")
    preservation = _mapping(evidence.get("preservation"), "preservation")
    revalidation = _mapping(evidence.get("revalidation"), "revalidation")
    target_ref = str(resolution.get("target_ref") or "")
    base_revision = str(resolution.get("base_revision") or "")
    target_path = Path(str(resolution.get("target_path") or "")).resolve()
    _require_equal(launch_target.get("target_ref"), target_ref, "launch_target.target_ref")
    _require_equal(launch_target.get("base_revision"), base_revision, "launch_target.base_revision")
    _require_equal(
        implementation.get("base_revision"),
        base_revision,
        "implementation.base_revision",
    )
    _require_equal(
        preservation.get("launch_checkout_untouched"),
        True,
        "preservation.launch_checkout_untouched",
    )
    _require_equal(verification.get("diff_reviewed"), True, "verification.diff_reviewed")
    _require_equal(verification.get("git_diff_check"), "passed", "verification.git_diff_check")
    tests = verification.get("tests")
    if not isinstance(tests, list) or not tests:
        raise GitCustodyError("git custody evidence requires at least one test command")
    for index, test in enumerate(tests):
        item = _mapping(test, f"verification.tests[{index}]")
        if not str(item.get("command") or "").strip() or item.get("status") != "passed":
            raise GitCustodyError(f"git custody test evidence is not passed at index {index}")

    worktree_path = Path(str(implementation.get("worktree_path") or "")).resolve()
    launch_paths = {
        Path(str(item.get("path"))).resolve()
        for item in _mapping(custody.get("launch_checkouts"), "launch_checkouts").values()
        if isinstance(item, Mapping) and item.get("path")
    }
    if worktree_path in launch_paths:
        raise GitCustodyError("implementation worktree is not isolated from launch checkouts")
    worktree = snapshot_checkout(worktree_path)
    target = snapshot_checkout(target_path)
    if not worktree.get("git") or worktree.get("repository") != target.get("repository"):
        raise GitCustodyError("implementation worktree is not registered in the target repository")
    if worktree.get("dirty"):
        raise GitCustodyError("implementation worktree is not clean")
    _require_equal(
        worktree.get("branch_ref"),
        implementation.get("branch_ref"),
        "implementation.branch_ref",
    )
    commit = str(implementation.get("commit_revision") or "")
    if not commit:
        raise GitCustodyError("implementation.commit_revision is required")
    if (
        _git(target_path, "cat-file", "-e", f"{commit}^{{commit}}", check=False).returncode
        != 0
    ):
        raise GitCustodyError("implementation commit does not exist in the target repository")
    if (
        _git(
            target_path,
            "merge-base",
            "--is-ancestor",
            base_revision,
            commit,
            check=False,
        ).returncode
        != 0
    ):
        raise GitCustodyError("launch base is not an ancestor of the implementation commit")
    if (
        _git(target_path, "diff", "--check", base_revision, commit, check=False).returncode
        != 0
    ):
        raise GitCustodyError("git diff --check failed for the implemented range")

    _require_equal(integration.get("target_ref"), target_ref, "integration.target_ref")
    _require_equal(revalidation.get("target_ref"), target_ref, "revalidation.target_ref")
    _require_equal(
        revalidation.get("observed_revision"),
        integration.get("before_revision"),
        "revalidation.observed_revision",
    )
    if blocked_after_launch:
        current = _git(target_path, "rev-parse", "--verify", target_ref, check=False)
        if current.returncode != 0:
            expected_gate = (
                f"recorded target {target_ref} no longer exists; retain {commit} and select "
                "the replacement writable local target ref"
            )
        elif (
            _git(
                target_path,
                "merge-base",
                "--is-ancestor",
                base_revision,
                target_ref,
                check=False,
            ).returncode
            != 0
        ):
            expected_gate = (
                f"recorded target {target_ref} moved off launch base {base_revision}; retain "
                f"{commit} and select the history-reconciliation target"
            )
        else:
            raise GitCustodyError(
                "launch target was resolved and remains on the recorded lineage; "
                "integration.status must be 'integrated', not an ambiguity gate"
            )
        _require_equal(integration.get("gate"), expected_gate, "integration.gate")
        return {
            "status": "verified_ambiguity_gate",
            "evidence_path": str(evidence_path),
            "target_ref": target_ref,
            "base_revision": base_revision,
            "commit_revision": commit,
            "gate": expected_gate,
            "worktree_path": str(worktree_path),
        }

    _require_equal(integration.get("status"), "integrated", "integration.status")
    after_revision = str(integration.get("after_revision") or "")
    if not after_revision:
        raise GitCustodyError("integration.after_revision is required")
    if (
        _git(
            target_path,
            "merge-base",
            "--is-ancestor",
            commit,
            target_ref,
            check=False,
        ).returncode
        != 0
    ):
        raise GitCustodyError("target ref does not contain the implementation commit")
    if (
        _git(
            target_path,
            "merge-base",
            "--is-ancestor",
            after_revision,
            target_ref,
            check=False,
        ).returncode
        != 0
    ):
        raise GitCustodyError("recorded integration result is not contained in the target ref")
    return {
        "status": "verified_integrated",
        "evidence_path": str(evidence_path),
        "target_ref": target_ref,
        "base_revision": base_revision,
        "commit_revision": commit,
        "target_revision": _git(target_path, "rev-parse", target_ref).stdout.strip(),
        "worktree_path": str(worktree_path),
    }


__all__ = [
    "GIT_CUSTODY_EVIDENCE_SCHEMA",
    "GIT_CUSTODY_SCHEMA",
    "GitCustodyError",
    "render_git_custody_contract",
    "resolve_launch_git_custody",
    "snapshot_checkout",
    "validate_git_custody_evidence",
]
