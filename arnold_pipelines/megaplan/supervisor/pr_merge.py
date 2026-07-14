"""Supervisor PR-merge actor for awaiting-human cursor states.

This actor bridges the neutral supervisor outcome vocabulary back to the
existing chain git/gh helpers when a planning run parks in an awaiting-human
state that is actually "wait for PR merge". The supervisor should not leave
that case parked for manual handling on the new path:

* already-merged PRs advance immediately;
* green PRs are marked ready and auto-merge is armed, then the node advances;
* red, blocked, missing-check, or merge-command failures enter the ladder.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from arnold_pipelines.megaplan.chain import git_ops
from arnold.control.interface import ControlBinding, RunStateView
from arnold.runtime.outcome import RunOutcome
from arnold_pipelines.megaplan.supervisor.ladder import (
    LadderAction,
    LadderDecision,
    SupervisorLadderPolicy,
    apply_ladder,
)
from arnold_pipelines.megaplan.supervisor.model import RunNode, SupervisorState
from arnold_pipelines.megaplan.types import CliError


_AWAITING_PR_MERGE = "awaiting_pr_merge"
_PR_WAIT_CURSOR_KINDS = frozenset(
    {
        "pr_merge",
        "awaiting_pr_merge",
    }
)

_GREEN_MERGE_STATE_STATUSES = frozenset({"clean", "has_hooks"})


@dataclass(frozen=True)
class PRMergeCursor:
    """Parsed PR-merge cursor metadata from a supervisor run-state view."""

    kind: str
    pr_number: int | None
    current_state: str | None
    resume_cursor: dict[str, Any] | None


@dataclass(frozen=True)
class PRMergeResolution:
    # Outcome of the supervisor PR-merge actor.

    handled: bool
    advanced: bool = False
    decision: LadderDecision | None = None
    pr_number: int | None = None
    pr_state: str | None = None
    reason: str | None = None
    # PR transition evidence captured at ready/merge points.
    pr_ready_evidence: Any | None = None
    pr_merged_evidence: Any | None = None


def maybe_resolve_pr_merge_wait(
    *,
    root: Path,
    state_id: str,
    state: SupervisorState,
    node: RunNode,
    run_state: RunStateView,
    plan_dir: Path,
    binding: ControlBinding | str,
    policy: SupervisorLadderPolicy,
    writer,
) -> PRMergeResolution:
    """Handle awaiting-human PR merge waits or return ``handled=False``.

    Cursor detection is intentionally metadata-driven so the actor only fires
    for explicit PR-wait states instead of every ``RunOutcome.AWAITING_HUMAN``.
    """

    cursor = parse_pr_merge_cursor(run_state)
    if cursor is None:
        return PRMergeResolution(handled=False)

    pr_number = cursor.pr_number
    if pr_number is None:
        return _ladder_failure(
            root=root,
            state_id=state_id,
            state=state,
            node=node,
            run_state=run_state,
            plan_dir=plan_dir,
            binding=binding,
            policy=policy,
            reason="awaiting_pr_merge cursor is missing pr_number",
        )

    try:
        pr_state = git_ops._pr_state(root, pr_number, writer=writer)
    except CliError as exc:
        return _ladder_failure(
            root=root,
            state_id=state_id,
            state=state,
            node=node,
            run_state=run_state,
            plan_dir=plan_dir,
            binding=binding,
            policy=policy,
            reason=f"PR #{pr_number} state probe failed: {exc.message}",
        )

    if pr_state == "merged":
        # Capture merged PR evidence: merge commit and tip containment check.
        merged_evidence = git_ops._capture_pr_merged_evidence(
            root, pr_number, writer=writer
        )
        return PRMergeResolution(
            handled=True,
            advanced=True,
            pr_number=pr_number,
            pr_state="merged",
            reason=f"PR #{pr_number} is already merged",
            pr_merged_evidence=merged_evidence,
        )

    try:
        readiness = _pr_merge_readiness(root, pr_number, writer=writer)
    except CliError as exc:
        return _ladder_failure(
            root=root,
            state_id=state_id,
            state=state,
            node=node,
            run_state=run_state,
            plan_dir=plan_dir,
            binding=binding,
            policy=policy,
            reason=f"PR #{pr_number} readiness probe failed: {exc.message}",
        )
    if readiness != "green":
        return _ladder_failure(
            root=root,
            state_id=state_id,
            state=state,
            node=node,
            run_state=run_state,
            plan_dir=plan_dir,
            binding=binding,
            policy=policy,
            reason=f"PR #{pr_number} is not merge-ready ({readiness})",
        )

    # Capture PR-ready evidence before marking ready.
    pr_ready_evidence = git_ops._capture_pr_ready_evidence(
        root, pr_number, writer=writer, ci_readiness_state=readiness,
    )
    # Capture PR head before merge so merged evidence can reference it.
    pr_head_sha, _last_pushed = git_ops._capture_pr_head_evidence(
        root, pr_number, writer=writer,
    )

    try:
        git_ops._mark_pr_ready(root, pr_number, writer=writer)
        merged_state = git_ops._enable_auto_merge(root, pr_number, writer=writer)
    except CliError as exc:
        return _ladder_failure(
            root=root,
            state_id=state_id,
            state=state,
            node=node,
            run_state=run_state,
            plan_dir=plan_dir,
            binding=binding,
            policy=policy,
            reason=f"PR #{pr_number} merge handling failed: {exc.message}",
        )

    # Capture merged evidence with tip containment after merge succeeds.
    merged_evidence = git_ops._capture_pr_merged_evidence(
        root, pr_number, writer=writer, pr_head_sha=pr_head_sha,
    )

    return PRMergeResolution(
        handled=True,
        advanced=True,
        pr_number=pr_number,
        pr_state=merged_state,
        reason=f"PR #{pr_number} is merge-ready ({merged_state})",
        pr_ready_evidence=pr_ready_evidence,
        pr_merged_evidence=merged_evidence,
    )


def parse_pr_merge_cursor(run_state: RunStateView) -> PRMergeCursor | None:
    """Return PR cursor metadata when the run is explicitly awaiting PR merge."""

    if run_state.outcome != RunOutcome.AWAITING_HUMAN:
        return None

    raw_state = run_state.raw_state if isinstance(run_state.raw_state, Mapping) else {}
    resume_cursor = raw_state.get("resume_cursor")
    if not isinstance(resume_cursor, dict):
        resume_cursor = None
    metadata = run_state.metadata if isinstance(run_state.metadata, Mapping) else {}

    current_state = _optional_str(raw_state.get("current_state")) or run_state.cursor
    cursor_kind = _optional_str(metadata.get("cursor_kind"))
    if cursor_kind is None and resume_cursor is not None:
        cursor_kind = (
            _optional_str(resume_cursor.get("kind"))
            or _optional_str(resume_cursor.get("wait_kind"))
            or _optional_str(resume_cursor.get("state"))
        )
    if cursor_kind is None and current_state == _AWAITING_PR_MERGE:
        cursor_kind = _AWAITING_PR_MERGE
    if cursor_kind not in _PR_WAIT_CURSOR_KINDS:
        return None

    pr_number = _optional_int(metadata.get("pr_number"))
    if pr_number is None and resume_cursor is not None:
        pr_number = _optional_int(resume_cursor.get("pr_number"))
    if pr_number is None:
        pr_number = _optional_int(raw_state.get("pr_number"))

    return PRMergeCursor(
        kind=cursor_kind,
        pr_number=pr_number,
        current_state=current_state,
        resume_cursor=dict(resume_cursor) if resume_cursor is not None else None,
    )


def _pr_merge_readiness(root: Path, pr_number: int, *, writer) -> str:
    """Classify whether a PR is merge-ready, blocked, or missing checks."""

    proc = git_ops._run_command(
        root,
        [
            "gh",
            "pr",
            "view",
            str(pr_number),
            "--json",
            "state,mergeStateStatus,isDraft",
        ],
        writer=writer,
        timeout=120,
        error_code="gh_pr_view_failed",
    )
    try:
        payload = json.loads(proc.stdout or "{}")
    except json.JSONDecodeError as exc:
        raise CliError("gh_pr_view_failed", f"gh pr view produced non-JSON output: {exc}") from exc

    state = _optional_str(payload.get("state"))
    if state == "merged":
        return "merged"
    if payload.get("isDraft") is True:
        return "draft"

    merge_state = _optional_str(payload.get("mergeStateStatus"))
    if merge_state in _GREEN_MERGE_STATE_STATUSES:
        return "green"
    if merge_state is None:
        return "missing_checks"
    return merge_state


def _ladder_failure(
    *,
    root: Path,
    state_id: str,
    state: SupervisorState,
    node: RunNode,
    run_state: RunStateView,
    plan_dir: Path,
    binding: ControlBinding | str,
    policy: SupervisorLadderPolicy,
    reason: str,
) -> PRMergeResolution:
    decision = apply_ladder(
        root=root,
        state_id=state_id,
        state=state,
        node=node,
        run_state=run_state,
        outcome=RunOutcome.FAILED,
        plan_dir=plan_dir,
        binding=binding,
        policy=policy,
    )
    return PRMergeResolution(
        handled=True,
        advanced=decision.action == LadderAction.ADVANCE,
        decision=decision,
        reason=reason,
    )


def _optional_int(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            return None
    return None


def _optional_str(value: object) -> str | None:
    return value.lower() if isinstance(value, str) and value else None


__all__ = [
    "PRMergeCursor",
    "PRMergeResolution",
    "maybe_resolve_pr_merge_wait",
    "parse_pr_merge_cursor",
]
