from __future__ import annotations

from vibecomfy.cli_loader import load_workflow_any
from vibecomfy.patches.resolution import resolution
from vibecomfy.runtime import run_embedded_sync


def build():
    workflow = load_workflow_any("video/wan_t2v")
    resolution(832, 480, 81).apply(workflow)
    workflow.set_seed(20260427)
    return workflow


if __name__ == "__main__":
    run_embedded_sync(build())
