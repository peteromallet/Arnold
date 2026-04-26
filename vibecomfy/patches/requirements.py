from __future__ import annotations

from collections.abc import Iterable

from vibecomfy.workflow import VibeWorkflow


def ensure_custom_nodes(workflow: VibeWorkflow, names: Iterable[str]) -> None:
    for name in names:
        if name not in workflow.requirements.custom_nodes:
            workflow.requirements.custom_nodes.append(name)
