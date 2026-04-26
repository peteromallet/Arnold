from __future__ import annotations

from pathlib import Path

from vibecomfy.scratchpad_loader import load_scratchpad


def test_load_scratchpad_returns_workflow(tmp_path: Path) -> None:
    scratchpad = tmp_path / "scratch.py"
    scratchpad.write_text(
        """
from vibecomfy.workflow import VibeWorkflow, WorkflowSource, VibeNode

def build():
    workflow = VibeWorkflow(id="x", source=WorkflowSource(id="x"))
    workflow.nodes["1"] = VibeNode(id="1", class_type="SaveImage")
    return workflow
""",
        encoding="utf-8",
    )

    workflow = load_scratchpad(scratchpad)
    assert workflow.id == "x"
    assert workflow.validate().ok
