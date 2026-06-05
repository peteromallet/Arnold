"""Worker-side prompt projection capability resolvers."""

from __future__ import annotations

from collections.abc import Sequence

from arnold.pipelines.megaplan.prompts._projection import PromptProjectionCapabilities

_READABLE_HERMES_TOOLSETS = {"file", "file-readonly", "terminal"}
_WRITABLE_HERMES_TOOLSETS = {"file", "terminal"}


def codex_projection_capabilities(
    *,
    resumed_session: bool,
    session_has_plan_dir_access: bool | None = None,
    checkpoint_write_access: bool = True,
) -> PromptProjectionCapabilities:
    """Resolve Codex prompt capabilities for fresh vs resumed sessions."""
    can_read_plan_dir = not resumed_session or bool(session_has_plan_dir_access)
    return PromptProjectionCapabilities(
        can_read_plan_dir=can_read_plan_dir,
        can_read_project_dir=True,
        has_file_tools=True,
        checkpoint_write_access=checkpoint_write_access,
    )


def hermes_projection_capabilities(toolsets: Sequence[str] | None) -> PromptProjectionCapabilities:
    """Resolve prompt capabilities from Hermes toolset selection."""
    selected = set(toolsets or [])
    can_read = bool(selected & _READABLE_HERMES_TOOLSETS)
    can_write = bool(selected & _WRITABLE_HERMES_TOOLSETS)
    return PromptProjectionCapabilities(
        can_read_plan_dir=can_read,
        can_read_project_dir=can_read,
        has_file_tools=can_read,
        checkpoint_write_access=can_write,
    )


def shannon_projection_capabilities(*, read_only: bool) -> PromptProjectionCapabilities:
    """Resolve prompt capabilities for Shannon read-only vs write modes."""
    return PromptProjectionCapabilities(
        can_read_plan_dir=True,
        can_read_project_dir=True,
        has_file_tools=True,
        checkpoint_write_access=not read_only,
    )


__all__ = [
    "codex_projection_capabilities",
    "hermes_projection_capabilities",
    "shannon_projection_capabilities",
]
