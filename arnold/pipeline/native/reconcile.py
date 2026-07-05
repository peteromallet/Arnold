"""Fail-closed reconcile policy for native side-effect resume."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from agentbox.git_worktree import (
    commit_exists,
    git_dirty_status,
    git_operation_status,
    has_local_branch,
    resolve_ref,
)
from agentbox.reconcile import parse_porcelain_paths, probe_file


ReconcileAction = str
ReconcileState = str


@dataclass(frozen=True)
class ReconcileMetadata:
    """Checkpoint/effect metadata used to authorize resume decisions."""

    operation: str
    target: str | None = None
    owned_paths: frozenset[str] = frozenset()
    expected_ref: str | None = None
    expected_commit: str | None = None
    expected_content: str | None = None
    expected_sha256: str | None = None


@dataclass(frozen=True)
class ReconcileActionTableEntry:
    """Declarative policy row for one reconcile state."""

    state: ReconcileState
    detection: str
    allowed_action: ReconcileAction
    required_metadata: tuple[str, ...]
    blocked_diagnostic: str | None = None


@dataclass(frozen=True)
class ReconcileDecision:
    """Concrete reconcile outcome for one step resume attempt."""

    state: ReconcileState
    action: ReconcileAction
    continue_execution: bool
    skip_execution: bool
    detail: str | None
    required_metadata: tuple[str, ...]

    @property
    def blocked(self) -> bool:
        return self.action == "block"


ACTION_TABLE: tuple[ReconcileActionTableEntry, ...] = (
    ReconcileActionTableEntry(
        state="clean",
        detection="No git dirty entries and no in-progress git operation markers.",
        allowed_action="execute",
        required_metadata=(),
    ),
    ReconcileActionTableEntry(
        state="dirty_owned_changes",
        detection="Dirty git paths exist and every path is covered by owned_paths.",
        allowed_action="continue_owned",
        required_metadata=("owned_paths",),
    ),
    ReconcileActionTableEntry(
        state="dirty_unknown_changes",
        detection="Dirty git paths exist outside owned_paths or ownership metadata is absent.",
        allowed_action="block",
        required_metadata=("owned_paths",),
        blocked_diagnostic="Worktree has unowned dirty changes; refusing to mutate or guess.",
    ),
    ReconcileActionTableEntry(
        state="in_progress_git_operation",
        detection="git_operation_status() reports merge/rebase/cherry-pick/revert/bisect markers.",
        allowed_action="block",
        required_metadata=(),
        blocked_diagnostic="Git operation is still in progress; refusing cleanup without explicit ownership recovery.",
    ),
    ReconcileActionTableEntry(
        state="branch_already_exists",
        detection="Target branch exists and resolves to the expected ref when provided.",
        allowed_action="skip",
        required_metadata=("target", "expected_ref"),
        blocked_diagnostic="Branch already exists but could not be proven to match the expected ref.",
    ),
    ReconcileActionTableEntry(
        state="commit_already_exists",
        detection="Expected commit resolves to an existing commit object.",
        allowed_action="skip",
        required_metadata=("expected_commit",),
        blocked_diagnostic="Commit existence could not be proven from checkpoint metadata.",
    ),
    ReconcileActionTableEntry(
        state="expected_file_write_already_applied",
        detection="Target file exists and matches expected content or expected sha256.",
        allowed_action="skip",
        required_metadata=("target", "expected_content|expected_sha256"),
        blocked_diagnostic="File write target exists but the expected contents were not proven.",
    ),
    ReconcileActionTableEntry(
        state="unknown",
        detection="Any state not covered by known file/git probes.",
        allowed_action="block",
        required_metadata=(),
        blocked_diagnostic="Encountered unknown reconcile state; refusing to mutate or guess.",
    ),
)

ACTION_BY_STATE = {entry.state: entry for entry in ACTION_TABLE}


def action_entry(state: ReconcileState) -> ReconcileActionTableEntry:
    return ACTION_BY_STATE.get(state, ACTION_BY_STATE["unknown"])


def reconcile_file_write(
    path: Path | str,
    metadata: ReconcileMetadata,
) -> ReconcileDecision:
    probe = probe_file(
        path,
        expected_content=metadata.expected_content,
        expected_sha256=metadata.expected_sha256,
    )
    if probe.exists and (
        probe.content_matches is True or probe.sha256_matches is True
    ):
        return _decision(
            "expected_file_write_already_applied",
            detail=f"target already matches expected file contents: {probe.path}",
        )
    if probe.exists:
        target = _normalize_repo_path(metadata.target or Path(path).name)
        if target in metadata.owned_paths:
            return _decision(
                "dirty_owned_changes",
                detail=f"target exists with owned changes: {probe.path}",
            )
        return _decision(
            "dirty_unknown_changes",
            detail=f"target exists but does not match expected contents: {probe.path}",
        )
    return _decision("clean", detail=f"target file does not exist yet: {probe.path}")


def reconcile_git_branch_create(
    repo_path: Path | str,
    metadata: ReconcileMetadata,
    *,
    status_path: Path | str | None = None,
) -> ReconcileDecision:
    op_state = git_operation_status(status_path or repo_path)
    if op_state.in_progress:
        return _decision(
            "in_progress_git_operation",
            detail=f"git markers present: {', '.join(op_state.markers)}",
        )
    branch = metadata.target
    if branch and has_local_branch(repo_path, branch):
        expected_ref = metadata.expected_ref
        if expected_ref is not None and _ref_matches(repo_path, branch, expected_ref):
            return _decision(
                "branch_already_exists",
                detail=f"branch {branch!r} already points at {resolve_ref(repo_path, branch)}",
            )
        return _decision(
            "unknown",
            detail=f"branch {branch!r} exists but expected_ref did not match",
        )
    return _dirty_or_clean_decision(status_path or repo_path, metadata)


def reconcile_git_commit(
    repo_path: Path | str,
    metadata: ReconcileMetadata,
    *,
    status_path: Path | str | None = None,
) -> ReconcileDecision:
    op_state = git_operation_status(status_path or repo_path)
    if op_state.in_progress:
        return _decision(
            "in_progress_git_operation",
            detail=f"git markers present: {', '.join(op_state.markers)}",
        )
    if metadata.expected_commit and commit_exists(repo_path, metadata.expected_commit):
        return _decision(
            "commit_already_exists",
            detail=f"commit already exists: {metadata.expected_commit}",
        )
    return _dirty_or_clean_decision(status_path or repo_path, metadata)


def reconcile_git_worktree(
    repo_path: Path | str,
    metadata: ReconcileMetadata,
    *,
    status_path: Path | str | None = None,
) -> ReconcileDecision:
    op_state = git_operation_status(status_path or repo_path)
    if op_state.in_progress:
        return _decision(
            "in_progress_git_operation",
            detail=f"git markers present: {', '.join(op_state.markers)}",
        )
    return _dirty_or_clean_decision(status_path or repo_path, metadata)


def reconcile_decision_allows_takeover(decision: ReconcileDecision) -> bool:
    """Return whether a native reconcile decision can authorize takeover."""

    return not decision.blocked and (decision.continue_execution or decision.skip_execution)


def _dirty_or_clean_decision(
    repo_path: Path | str,
    metadata: ReconcileMetadata,
) -> ReconcileDecision:
    status = git_dirty_status(repo_path)
    if not status.is_dirty:
        return _decision("clean", detail="worktree is clean")
    dirty_paths = frozenset(_normalize_repo_path(path) for path in parse_porcelain_paths(status.entries))
    if metadata.owned_paths and dirty_paths.issubset(metadata.owned_paths):
        return _decision(
            "dirty_owned_changes",
            detail=f"owned dirty paths: {', '.join(sorted(dirty_paths))}",
        )
    return _decision(
        "dirty_unknown_changes",
        detail=f"unowned dirty paths: {', '.join(sorted(dirty_paths))}",
    )


def _decision(state: ReconcileState, *, detail: str | None) -> ReconcileDecision:
    entry = action_entry(state)
    return ReconcileDecision(
        state=entry.state,
        action=entry.allowed_action,
        continue_execution=entry.allowed_action in {"execute", "continue_owned"},
        skip_execution=entry.allowed_action == "skip",
        detail=detail or entry.blocked_diagnostic,
        required_metadata=entry.required_metadata,
    )


def _ref_matches(repo_path: Path | str, left: str, right: str) -> bool:
    try:
        return resolve_ref(repo_path, left) == resolve_ref(repo_path, right)
    except Exception:
        return False


def _normalize_repo_path(path: Path | str) -> str:
    return Path(path).as_posix().lstrip("./")


__all__ = [
    "ACTION_TABLE",
    "ReconcileActionTableEntry",
    "ReconcileDecision",
    "ReconcileMetadata",
    "action_entry",
    "reconcile_file_write",
    "reconcile_decision_allows_takeover",
    "reconcile_git_branch_create",
    "reconcile_git_commit",
    "reconcile_git_worktree",
]
