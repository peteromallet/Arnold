"""Completion DM formatter for AgentBox operations."""

from __future__ import annotations

from typing import Any


def format_completion_dm(
    operation_status: dict[str, Any],
    *,
    validation: dict[str, Any] | None = None,
    branch_status: dict[str, Any] | None = None,
    next_action: str | None = None,
) -> str:
    """Return a concise plain-text completion DM for an operation."""

    operation_id = operation_status.get("operation_id", "<unknown>")
    state = operation_status.get("operation_state", "<unknown>")
    lines = [f"Operation {operation_id} completed with state {state}."]

    validation = validation or operation_status.get("validation") or {}
    if validation:
        status = validation.get("status", "unknown")
        lines.append(f"Validation: {status}.")

    branch_status = branch_status or {}
    branch = branch_status.get("branch") or operation_status.get("branch")
    pr_number = branch_status.get("pr_number") or operation_status.get("pr_number")
    pr_url = branch_status.get("pr_url") or operation_status.get("pr_url")
    ci_status = branch_status.get("ci_status") or operation_status.get("ci_status")

    parts: list[str] = []
    if branch:
        parts.append(f"branch={branch}")
    if pr_number is not None:
        parts.append(f"pr_number={pr_number}")
    if pr_url:
        parts.append(f"pr_url={pr_url}")
    if ci_status:
        parts.append(f"ci_status={ci_status}")
    if parts:
        lines.append(f"Branch/PR status: {', '.join(parts)}.")

    cleanup_state = operation_status.get("cleanup_state")
    if cleanup_state:
        lines.append(f"Cleanup state: {cleanup_state}.")

    if next_action:
        lines.append(f"Next action: {next_action}")
    else:
        lines.append("Next action: review the operation status and choose land, park, or delete.")

    return "\n".join(lines)


__all__ = ["format_completion_dm"]
