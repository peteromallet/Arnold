from __future__ import annotations

import json
from pathlib import Path

import pytest

from vibecomfy.cli_loader import load_workflow_any


def test_load_workflow_any_accepts_basename_ready_id() -> None:
    workflow = load_workflow_any("z_image")

    assert workflow.metadata["ready_template"] == "image/z_image"


def test_load_workflow_any_accepts_slash_ready_id() -> None:
    workflow = load_workflow_any("video/wan_t2v")

    assert workflow.metadata["ready_template"] == "video/wan_t2v"


def test_load_workflow_any_accepts_scratchpad_path(tmp_path: Path) -> None:
    scratchpad = tmp_path / "scratch.py"
    scratchpad.write_text(
        "from vibecomfy.workflow import VibeWorkflow, WorkflowSource\n\n"
        "def build():\n"
        "    wf = VibeWorkflow('scratch', WorkflowSource('scratch'))\n"
        "    wf.add_node('SaveImage', images='placeholder')\n"
        "    return wf.finalize_metadata()\n",
        encoding="utf-8",
    )

    workflow = load_workflow_any(str(scratchpad))

    assert workflow.id == "scratch"
    assert workflow.outputs[0].output_type == "SaveImage"


def test_load_workflow_any_accepts_json_path(tmp_path: Path) -> None:
    workflow_path = tmp_path / "workflow.json"
    workflow_path.write_text(
        json.dumps({"1": {"class_type": "SaveImage", "inputs": {"images": "placeholder"}}}),
        encoding="utf-8",
    )

    workflow = load_workflow_any(str(workflow_path))

    assert workflow.id == "workflow"
    assert workflow.outputs[0].node_id == "1"


def test_load_workflow_any_missing_id_raises_key_error() -> None:
    with pytest.raises(KeyError):
        load_workflow_any("not_a_real_workflow_id")


def test_load_workflow_any_missing_path_raises_file_not_found(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        load_workflow_any(str(tmp_path / "missing.json"))
