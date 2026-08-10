"""Branch protection and approval policy for brokered actions."""

from __future__ import annotations

from dataclasses import dataclass, field

from arnold.security.types import ActionRequest, ActionResult, ActionVerdict

DEFAULT_PROTECTED_BRANCHES: frozenset[str] = frozenset({"main", "master"})
DEFAULT_APPROVAL_REQUIRED_ACTIONS: frozenset[str] = frozenset(
    {"git_force_push", "git_branch_delete", "git_pr_merge", "credential_escalation"}
)


def normalize_branch_name(branch: str | None) -> str:
    """Normalize remote refs like refs/heads/main to their branch name."""

    if not branch:
        return ""
    normalized = branch.strip()
    for prefix in ("refs/heads/", "origin/"):
        if normalized.startswith(prefix):
            normalized = normalized[len(prefix) :]
    return normalized


@dataclass(frozen=True, slots=True)
class SecurityPolicy:
    """Deterministic policy for broker-covered actions."""

    protected_branches: frozenset[str] = field(default_factory=lambda: DEFAULT_PROTECTED_BRANCHES)
    approval_required_actions: frozenset[str] = field(
        default_factory=lambda: DEFAULT_APPROVAL_REQUIRED_ACTIONS
    )

    def is_protected_branch(self, branch: str | None) -> bool:
        normalized = normalize_branch_name(branch)
        return bool(normalized and normalized in self.protected_branches)

    def evaluate(self, request: ActionRequest) -> ActionResult:
        """Return the broker policy decision for an action request."""

        branch = normalize_branch_name(request.branch)

        if request.force:
            return ActionResult(
                verdict=ActionVerdict.APPROVAL_REQUIRED,
                summary=f"Force operation on {branch or 'unknown branch'} requires approval",
                metadata={
                    "action_type": request.action_type,
                    "branch": branch,
                    "repo": request.repo,
                    "force": True,
                },
            )

        if request.action_type in self.approval_required_actions:
            return ActionResult(
                verdict=ActionVerdict.APPROVAL_REQUIRED,
                summary=f"{request.action_type} requires approval",
                metadata={"action_type": request.action_type, "branch": branch, "repo": request.repo},
            )

        if request.action_type == "git_push" and self.is_protected_branch(branch):
            return ActionResult(
                verdict=ActionVerdict.DENY,
                summary=f"Push to protected branch {branch} is denied",
                metadata={"action_type": request.action_type, "branch": branch, "repo": request.repo},
            )

        return ActionResult(
            verdict=ActionVerdict.ALLOW,
            summary=f"{request.action_type} allowed",
            metadata={"action_type": request.action_type, "branch": branch, "repo": request.repo},
        )


__all__ = [
    "DEFAULT_APPROVAL_REQUIRED_ACTIONS",
    "DEFAULT_PROTECTED_BRANCHES",
    "SecurityPolicy",
    "normalize_branch_name",
]
