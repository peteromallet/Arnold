"""Git and GitHub MCP action classification for broker policy checks."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from arnold.security.broker_client import BrokerClient
from arnold.security.types import ActionRequest, ActionResult, ActionVerdict

_GIT_PROVIDER_NAMES = frozenset({"git", "github", "gitlab", "gitea", "bitbucket"})
_PUSH_CLASS_TOOL_MARKERS = (
    "push",
    "create_pull_request",
    "create_pr",
    "create_or_update_file",
    "update_file",
    "create_file",
    "delete_file",
    "commit",
    "delete_branch",
    "merge_pull_request",
    "merge_pr",
)
_BRANCH_KEYS = (
    "branch",
    "target_branch",
    "base_branch",
    "base",
    "ref",
)
_REPO_KEYS = (
    "repo",
    "repository",
    "repository_name",
    "repo_name",
    "full_name",
    "remote",
    "url",
)


@dataclass(frozen=True, slots=True)
class McpGitAuthorization:
    """Broker authorization outcome for an MCP git/GitHub mutation."""

    sensitive: bool
    request: ActionRequest | None = None
    result: ActionResult | None = None

    @property
    def allowed(self) -> bool:
        return self.result is None or self.result.verdict is ActionVerdict.ALLOW

    def broker_payload(self) -> dict[str, Any]:
        if self.result is None:
            return {}
        payload = self.result.to_json()
        return {
            "verdict": payload.get("verdict"),
            "summary": payload.get("summary"),
            "action_id": payload.get("action_id"),
            "effect_refs": payload.get("effect_refs", []),
            "metadata": payload.get("metadata", {}),
        }


def authorize_mcp_git_action(
    server_name: str,
    tool_name: str,
    args: dict[str, Any] | None,
    *,
    broker_client: BrokerClient | None = None,
) -> McpGitAuthorization:
    """Evaluate sensitive MCP git/GitHub mutations before handler execution."""

    action_request = build_mcp_git_action_request(server_name, tool_name, args or {})
    if action_request is None:
        return McpGitAuthorization(sensitive=False)

    client = broker_client or BrokerClient.from_environment()
    result = client.evaluate_action(action_request)
    return McpGitAuthorization(sensitive=True, request=action_request, result=result)


def build_mcp_git_action_request(
    server_name: str,
    tool_name: str,
    args: dict[str, Any],
) -> ActionRequest | None:
    """Return an ActionRequest for push-class MCP git operations, else None."""

    provider = _provider_name(server_name, tool_name, args)
    command = _extract_command(tool_name, args)
    if not _is_push_class_operation(provider, tool_name, command):
        return None

    force = _detect_force(tool_name, args, command)
    return ActionRequest(
        action_type=_action_type(tool_name, command, force),
        provider=provider,
        repo=_extract_repo(args),
        branch=_extract_branch(args, command),
        command=command,
        force=force,
        metadata={
            "mcp_server": server_name,
            "mcp_tool": tool_name,
            "effect": "git_remote_mutation",
        },
    )


def _provider_name(server_name: str, tool_name: str, args: dict[str, Any]) -> str | None:
    combined = f"{server_name} {tool_name}".lower()
    for provider in _GIT_PROVIDER_NAMES:
        if provider in combined:
            return provider
    repo = _extract_repo(args) or ""
    if "github.com" in repo.lower():
        return "github"
    command = " ".join(_extract_command(tool_name, args)).lower()
    if command.startswith("git ") or " git " in command:
        return "git"
    return None


def _is_push_class_operation(
    provider: str | None,
    tool_name: str,
    command: tuple[str, ...],
) -> bool:
    lowered_tool = tool_name.lower().replace("-", "_")
    if any(marker in lowered_tool for marker in _PUSH_CLASS_TOOL_MARKERS):
        return provider in _GIT_PROVIDER_NAMES or "github" in lowered_tool or "git" in lowered_tool

    lowered_command = [part.lower() for part in command]
    if len(lowered_command) >= 2 and lowered_command[0] == "git":
        return lowered_command[1] in {"push", "merge"}
    return False


def _action_type(tool_name: str, command: tuple[str, ...], force: bool) -> str:
    lowered_tool = tool_name.lower().replace("-", "_")
    lowered_command = [part.lower() for part in command]
    if "delete_branch" in lowered_tool:
        return "git_branch_delete"
    if "create_pull_request" in lowered_tool or "create_pr" in lowered_tool:
        return "git_pr_create"
    if "merge_pull_request" in lowered_tool or "merge_pr" in lowered_tool:
        return "git_pr_merge"
    if len(lowered_command) >= 2 and lowered_command[:2] == ["git", "push"] and _push_deletes_ref(command):
        return "git_branch_delete"
    if force:
        return "git_force_push"
    return "git_push"


def _extract_command(tool_name: str, args: dict[str, Any]) -> tuple[str, ...]:
    for key in ("command", "cmd", "argv"):
        value = args.get(key)
        if isinstance(value, str):
            return tuple(part for part in value.split() if part)
        if isinstance(value, (list, tuple)):
            return tuple(str(part) for part in value)
    return (tool_name,)


def _detect_force(tool_name: str, args: dict[str, Any], command: tuple[str, ...]) -> bool:
    if any(str(args.get(key, "")).lower() == "true" for key in ("force", "force_push", "force_with_lease")):
        return True
    lowered_tool = tool_name.lower().replace("-", "_")
    if "force_push" in lowered_tool:
        return True
    return any(part in {"--force", "-f", "--force-with-lease"} for part in command)


def _extract_repo(args: dict[str, Any]) -> str | None:
    owner = _optional_text(args.get("owner"))
    repo = _first_text(args, _REPO_KEYS)
    if owner and repo and "/" not in repo and not repo.startswith(("http://", "https://", "git@")):
        return f"{owner}/{repo}"
    return repo


def _extract_branch(args: dict[str, Any], command: tuple[str, ...]) -> str | None:
    branch = _first_text(args, _BRANCH_KEYS)
    if branch:
        return branch

    if len(command) >= 4 and command[0] == "git" and command[1] == "push":
        refspecs = [part for part in command[3:] if not part.startswith("-")]
        if refspecs:
            candidate = refspecs[-1]
            if ":" in candidate:
                candidate = candidate.rsplit(":", 1)[1]
            return candidate.removeprefix("refs/heads/")
    return None


def _push_deletes_ref(command: tuple[str, ...]) -> bool:
    return any(part.startswith(":") or part == "--delete" for part in command)


def _first_text(args: dict[str, Any], keys: tuple[str, ...]) -> str | None:
    for key in keys:
        value = _optional_text(args.get(key))
        if value:
            return value
    return None


def _optional_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


__all__ = [
    "McpGitAuthorization",
    "authorize_mcp_git_action",
    "build_mcp_git_action_request",
]
