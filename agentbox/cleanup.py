"""Cleanup survey and executor for AgentBox operation resources."""

from __future__ import annotations

import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Literal

from arnold.runtime.durable_ops import OperationState, ResourceType, is_terminal_operation_state

from agentbox.config import AgentBoxConfig
from agentbox.git_worktree import git, git_operation_status, has_local_branch, list_worktrees
from agentbox.operations import (
    record_operation_cleanup_state,
    record_operation_pr,
)
from agentbox.repos import AgentBoxRepoNotFound, get_repo
from agentbox.run_dirs import append_event, run_dir_paths

CleanupRecommendation = Literal["land", "delete", "park"]


@dataclass(frozen=True)
class CleanupFinding:
    """One cleanup recommendation with supporting evidence."""

    finding_id: str
    operation_id: str | None
    repo_name: str | None
    branch: str | None
    worktree_path: str | None
    recommendation: CleanupRecommendation
    reason: str
    evidence: dict[str, Any]
    requires_confirmation: bool

    def to_dict(self) -> dict[str, Any]:
        return _jsonable(asdict(self))


@dataclass(frozen=True)
class CleanupSurveyReport:
    """Report-only cleanup survey result."""

    findings: tuple[CleanupFinding, ...]

    def to_dict(self) -> dict[str, Any]:
        return {"findings": [finding.to_dict() for finding in self.findings]}


def survey_cleanup(config: AgentBoxConfig) -> CleanupSurveyReport:
    """Survey AgentBox state and classify cleanup recommendations."""

    # Import here to avoid a circular import with agentbox.reconcile.
    from agentbox.reconcile import reconcile

    report = reconcile(config)
    findings: list[CleanupFinding] = []
    for operation in report.operations:
        terminal = is_terminal_operation_state(
            OperationState(operation.operation_state)
        )
        for worktree in operation.worktrees:
            evidence = _gather_worktree_evidence(
                config,
                operation_id=operation.operation_id,
                repo_name=worktree.repo_name,
                branch=worktree.branch,
                worktree_path=Path(worktree.worktree_path),
                checked_out_elsewhere=worktree.checked_out_elsewhere,
                terminal=terminal,
            )
            recommendation = _classify_cleanup_recommendation(evidence)
            finding_id = _finding_id(operation.operation_id, worktree.repo_name)
            findings.append(
                CleanupFinding(
                    finding_id=finding_id,
                    operation_id=operation.operation_id,
                    repo_name=worktree.repo_name,
                    branch=worktree.branch,
                    worktree_path=worktree.worktree_path,
                    recommendation=recommendation,
                    reason=evidence.get("reason", "surveyed"),
                    evidence=evidence,
                    requires_confirmation=recommendation in ("delete", "reset"),
                )
            )
    for orphan in report.orphan_run_dirs:
        findings.append(
            CleanupFinding(
                finding_id=f"orphan:{orphan.operation_id}",
                operation_id=orphan.operation_id,
                repo_name=None,
                branch=None,
                worktree_path=orphan.path,
                recommendation="park",
                reason="orphan_run_dir_requires_inspection",
                evidence={"orphan_run_dir": True},
                requires_confirmation=False,
            )
        )
    return CleanupSurveyReport(findings=tuple(findings))


def apply_cleanup(
    config: AgentBoxConfig,
    finding_id: str,
    action: str,
    *,
    confirmation_request_id: str | None = None,
    confirmation_phrase: str | None = None,
    confirmation_manager: Any | None = None,
    subject: Any | None = None,
) -> dict[str, Any]:
    """Apply one cleanup action to a surveyed finding.

    Destructive actions (``delete``, ``reset``, ``merge``) require confirmation
    through ``confirmation_manager`` when it is configured.
    """

    report = survey_cleanup(config)
    finding = next((f for f in report.findings if f.finding_id == finding_id), None)
    if finding is None:
        return {
            "ok": False,
            "action": action,
            "finding_id": finding_id,
            "error": "finding not found",
        }

    destructive_actions = {"delete", "reset", "merge"}
    if action in destructive_actions and confirmation_manager is not None:
        if not getattr(confirmation_manager, "required_for", lambda _: False)("reconcile_apply"):
            pass
        elif not confirmation_request_id or not confirmation_phrase:
            request = confirmation_manager.request_confirmation(
                subject=subject,
                action="reconcile_apply",
                target_summary=_cleanup_target_summary(finding),
                metadata={"tool": "cleanup_apply", "finding_id": finding.finding_id, "action": action},
            )
            return {
                "ok": False,
                "action": action,
                "finding_id": finding_id,
                "confirmation_required": True,
                "request_id": request.id,
                "exact_phrase": request.exact_phrase,
            }
        else:
            decision = confirmation_manager.confirm(
                request_id=confirmation_request_id,
                subject=subject,
                phrase=confirmation_phrase,
            )
            if not decision.allowed:
                return {
                    "ok": False,
                    "action": action,
                    "finding_id": finding_id,
                    "confirmation_required": True,
                    "request_id": confirmation_request_id,
                    "reason": decision.reason,
                }

    if action == "land":
        return _apply_land(config, finding)
    if action == "delete":
        return _apply_delete(config, finding)
    if action == "park":
        return _apply_park(config, finding)
    if action == "reset":
        return _apply_reset(config, finding)
    if action == "merge":
        return _apply_merge(config, finding)

    return {
        "ok": False,
        "action": action,
        "finding_id": finding_id,
        "error": f"unsupported cleanup action: {action}",
    }


def _apply_land(config: AgentBoxConfig, finding: CleanupFinding) -> dict[str, Any]:
    if not finding.operation_id or not finding.repo_name or not finding.branch:
        return {"ok": False, "action": "land", "finding_id": finding.finding_id, "error": "incomplete finding"}

    try:
        repo = get_repo(config, finding.repo_name)
    except AgentBoxRepoNotFound as exc:
        return {"ok": False, "action": "land", "finding_id": finding.finding_id, "error": str(exc)}

    from agentbox import github

    existing = github.pr_for_branch(repo.path, finding.branch)
    if existing.get("number") is not None:
        pr_number = existing["number"]
        pr_url = existing.get("url")
    else:
        base_ref = finding.evidence.get("base_ref") or repo.default_ref
        if base_ref == "HEAD":
            base_ref = _default_branch(repo.path) or "main"
        title = f"AgentBox cleanup: land {finding.branch}"
        body = f"Draft PR opened by AgentBox cleanup for operation {finding.operation_id}."
        result = github.create_draft_pr(
            repo.path,
            finding.branch,
            base=base_ref,
            title=title,
            body=body,
        )
        if not result.get("ok"):
            return {
                "ok": False,
                "action": "land",
                "finding_id": finding.finding_id,
                "error": result.get("error", "draft pr creation failed"),
                "fix_command": result.get("fix_command"),
            }
        pr_number = result["number"]
        pr_url = result.get("url")

    record_operation_pr(
        config,
        finding.operation_id,
        repo_name=finding.repo_name,
        branch=finding.branch,
        pr_number=pr_number,
        pr_url=pr_url,
    )
    record_operation_cleanup_state(
        config,
        finding.operation_id,
        repo_name=finding.repo_name,
        state="landed",
        reason="draft pr opened",
    )
    _append_cleanup_event(config, finding, "cleanup.land", {"pr_number": pr_number, "pr_url": pr_url})
    return {
        "ok": True,
        "action": "land",
        "finding_id": finding.finding_id,
        "pr_number": pr_number,
        "pr_url": pr_url,
    }


def _apply_delete(config: AgentBoxConfig, finding: CleanupFinding) -> dict[str, Any]:
    if not finding.operation_id:
        return {"ok": False, "action": "delete", "finding_id": finding.finding_id, "error": "incomplete finding"}

    branch = finding.branch
    repo_path: Path | None = None
    if finding.repo_name:
        try:
            repo_path = get_repo(config, finding.repo_name).path
        except AgentBoxRepoNotFound:
            pass

    worktree_path_value = finding.worktree_path
    if repo_path and branch:
        checked_out = _worktree_for_branch(repo_path, branch)
        if checked_out is None and has_local_branch(repo_path, branch):
            try:
                git(repo_path, "branch", "-D", branch, check=False)
            except Exception as exc:
                return {"ok": False, "action": "delete", "finding_id": finding.finding_id, "error": str(exc)}

    if worktree_path_value and repo_path:
        target = Path(worktree_path_value)
        if _is_registered_worktree(repo_path, target):
            try:
                git(repo_path, "worktree", "remove", str(target), check=False)
            except Exception as exc:
                return {"ok": False, "action": "delete", "finding_id": finding.finding_id, "error": str(exc)}

    if finding.repo_name:
        record_operation_cleanup_state(
            config,
            finding.operation_id,
            repo_name=finding.repo_name,
            state="deleted",
            reason="branch and worktree removed",
        )
    _append_cleanup_event(config, finding, "cleanup.delete", {})
    return {"ok": True, "action": "delete", "finding_id": finding.finding_id}


def _apply_park(config: AgentBoxConfig, finding: CleanupFinding) -> dict[str, Any]:
    if finding.operation_id and finding.repo_name:
        record_operation_cleanup_state(
            config,
            finding.operation_id,
            repo_name=finding.repo_name,
            state="parked",
            reason="manual inspection required",
        )
    _append_cleanup_event(config, finding, "cleanup.park", {})
    return {"ok": True, "action": "park", "finding_id": finding.finding_id}


def _apply_reset(config: AgentBoxConfig, finding: CleanupFinding) -> dict[str, Any]:
    if not finding.worktree_path:
        return {"ok": False, "action": "reset", "finding_id": finding.finding_id, "error": "no worktree path"}

    target = Path(finding.worktree_path)
    if not target.exists():
        return {"ok": False, "action": "reset", "finding_id": finding.finding_id, "error": "worktree path missing"}

    try:
        git(target, "reset", "--hard", "HEAD", check=False)
        git(target, "clean", "-fd", check=False)
    except Exception as exc:
        return {"ok": False, "action": "reset", "finding_id": finding.finding_id, "error": str(exc)}

    if finding.operation_id and finding.repo_name:
        record_operation_cleanup_state(
            config,
            finding.operation_id,
            repo_name=finding.repo_name,
            state="reset",
            reason="worktree reset to clean HEAD",
        )
    _append_cleanup_event(config, finding, "cleanup.reset", {})
    return {"ok": True, "action": "reset", "finding_id": finding.finding_id}


def _apply_merge(config: AgentBoxConfig, finding: CleanupFinding) -> dict[str, Any]:
    # Merge is gated by confirmation but not offered as a primary cleanup action.
    if finding.operation_id and finding.repo_name:
        record_operation_cleanup_state(
            config,
            finding.operation_id,
            repo_name=finding.repo_name,
            state="merge_requested",
            reason="merge action requires gh pr merge",
        )
    _append_cleanup_event(config, finding, "cleanup.merge", {})
    return {"ok": True, "action": "merge", "finding_id": finding.finding_id}


def _gather_worktree_evidence(
    config: AgentBoxConfig,
    *,
    operation_id: str,
    repo_name: str,
    branch: str,
    worktree_path: Path,
    checked_out_elsewhere: bool,
    terminal: bool,
) -> dict[str, Any]:
    evidence: dict[str, Any] = {
        "operation_id": operation_id,
        "repo_name": repo_name,
        "branch": branch,
        "worktree_path": str(worktree_path),
        "checked_out_elsewhere": checked_out_elsewhere,
        "terminal": terminal,
    }
    try:
        repo = get_repo(config, repo_name)
    except AgentBoxRepoNotFound:
        evidence["reason"] = "repo_not_registered"
        return evidence

    evidence["repo_path"] = str(repo.path)
    base_ref = repo.default_ref
    base_sha: str | None = None
    resource = _git_worktree_resource(config, operation_id, repo_name)
    if resource is not None:
        base_ref = resource.details.get("base_ref") or base_ref
        base_sha = resource.details.get("base_sha")
    evidence["base_ref"] = base_ref
    evidence["base_sha"] = base_sha

    if base_ref == "HEAD":
        base_ref = _default_branch(repo.path) or "main"

    status_path = worktree_path if worktree_path.exists() else repo.path
    try:
        dirty = bool(git(status_path, "status", "--porcelain", check=False).stdout.strip())
        evidence["dirty"] = dirty
    except Exception as exc:
        evidence["dirty"] = False
        evidence["status_error"] = str(exc)
        dirty = False

    try:
        op_status = git_operation_status(status_path)
        evidence["git_operation_in_progress"] = op_status.in_progress
        evidence["git_operation_markers"] = op_status.markers
    except Exception as exc:
        evidence["git_operation_in_progress"] = False
        evidence["git_operation_error"] = str(exc)
        op_status = None

    from agentbox import github

    if github.gh_installed():
        pr_info = github.pr_for_branch(repo.path, branch)
        evidence["auth_ok"] = pr_info.get("auth_ok")
        evidence["fix_command"] = pr_info.get("fix_command")
        evidence["pr_number"] = pr_info.get("number")
        evidence["pr_url"] = pr_info.get("url")
        evidence["pr_state"] = pr_info.get("state")
    else:
        evidence["auth_ok"] = None
        evidence["fix_command"] = None
        evidence["pr_number"] = None
        evidence["pr_url"] = None
        evidence["pr_state"] = None

    open_pr = evidence.get("pr_state") == "OPEN"
    evidence["open_pr"] = open_pr

    merged = False
    unique_commits = False
    if has_local_branch(repo.path, branch):
        try:
            base_sha = _resolve_ref(repo.path, base_ref)
            merged = _is_ancestor(repo.path, branch, base_ref)
            if not merged:
                unique_commits = _has_unique_commits(repo.path, branch, base_ref)
        except Exception as exc:
            evidence["merge_base_error"] = str(exc)
    evidence["merged"] = merged
    evidence["unique_commits"] = unique_commits

    if dirty or (op_status is not None and op_status.in_progress):
        evidence["reason"] = "dirty_or_in_progress_git_operation"
    elif checked_out_elsewhere:
        evidence["reason"] = "branch_checked_out_elsewhere"
    elif not terminal:
        evidence["reason"] = "operation_not_terminal"
    elif merged:
        evidence["reason"] = "branch_is_ancestor_of_base"
    elif unique_commits and not open_pr:
        evidence["reason"] = "unique_commits_no_open_pr_clean"
    else:
        evidence["reason"] = "default_park"

    return evidence


def _classify_cleanup_recommendation(evidence: dict[str, Any]) -> CleanupRecommendation:
    dirty = evidence.get("dirty", False)
    in_progress = evidence.get("git_operation_in_progress", False)
    checked_out_elsewhere = evidence.get("checked_out_elsewhere", False)
    terminal = evidence.get("terminal", False)
    merged = evidence.get("merged", False)
    unique_commits = evidence.get("unique_commits", False)
    open_pr = evidence.get("open_pr", False)

    if dirty or in_progress:
        return "park"
    if checked_out_elsewhere:
        return "park"
    if not terminal:
        return "park"
    if merged:
        return "delete"
    if unique_commits and not open_pr:
        return "land"
    return "park"


def _finding_id(operation_id: str, repo_name: str) -> str:
    return f"{operation_id}:{repo_name}"


def _cleanup_target_summary(finding: CleanupFinding) -> str:
    parts = ["cleanup"]
    if finding.operation_id:
        parts.append(finding.operation_id)
    if finding.repo_name:
        parts.append(finding.repo_name)
    if finding.branch:
        parts.append(finding.branch)
    return " ".join(parts)


def _git_worktree_resource(config: AgentBoxConfig, operation_id: str, repo_name: str) -> Any | None:
    from agentbox.operations import open_operation_store

    for resource in open_operation_store(config).list_typed_resources(operation_id):
        if (
            resource.resource_type is ResourceType.GIT_WORKTREE
            and resource.details.get("repo_name") == repo_name
        ):
            return resource
    return None


def _resolve_ref(repo_path: Path, ref: str) -> str:
    return git(repo_path, "rev-parse", "--verify", f"{ref}^{{commit}}", check=False).stdout.strip()


def _is_ancestor(repo_path: Path, descendant: str, ancestor: str) -> bool:
    result = subprocess.run(
        ("git", "merge-base", "--is-ancestor", descendant, ancestor),
        cwd=repo_path,
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return result.returncode == 0


def _has_unique_commits(repo_path: Path, branch: str, base: str) -> bool:
    result = git(repo_path, "log", f"{base}..{branch}", "--oneline", check=False)
    return bool(result.stdout.strip())


def _default_branch(repo_path: Path) -> str | None:
    result = git(repo_path, "rev-parse", "--abbrev-ref", "HEAD", check=False)
    return result.stdout.strip() or None


def _worktree_for_branch(repo_path: Path, branch: str) -> Any | None:
    for worktree in list_worktrees(repo_path):
        if worktree.branch_name == branch:
            return worktree
    return None


def _is_registered_worktree(repo_path: Path, target: Path) -> bool:
    resolved = target.resolve()
    return any(worktree.path.resolve() == resolved for worktree in list_worktrees(repo_path))


def _append_cleanup_event(
    config: AgentBoxConfig,
    finding: CleanupFinding,
    event_type: str,
    payload: dict[str, Any],
) -> None:
    if not finding.operation_id:
        return
    paths = run_dir_paths(config, finding.operation_id)
    append_event(
        paths,
        event_type,
        payload={
            "finding_id": finding.finding_id,
            "repo_name": finding.repo_name,
            "branch": finding.branch,
            **payload,
        },
    )


def _jsonable(value: object) -> Any:
    from enum import Enum

    if isinstance(value, Enum):
        return value.value
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    return value


__all__ = [
    "CleanupFinding",
    "CleanupSurveyReport",
    "apply_cleanup",
    "survey_cleanup",
]
