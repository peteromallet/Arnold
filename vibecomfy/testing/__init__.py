"""Public testing helpers for downstream VibeComfy integrations.

Projects can opt into pytest fixtures with:

    pytest_plugins = ("vibecomfy.testing._pytest_plugin",)
"""

from .fixtures import (
    DryRuntime,
    dry_runtime,
    make_handle_factory,
    make_workflow_factory,
    vibecomfy_handle_factory,
    vibecomfy_workflow_factory,
)

__all__ = [
    "DryRuntime",
    "dry_runtime",
    "make_handle_factory",
    "make_workflow_factory",
    "vibecomfy_handle_factory",
    "vibecomfy_workflow_factory",
]
