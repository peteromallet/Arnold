from __future__ import annotations

from vibecomfy.ingest.normalize import convert_to_vibe_format
from vibecomfy.workflow import VibeOutput, VibeWorkflow, WorkflowSource


def test_finalize_metadata_matches_convert_to_vibe_format_for_equivalent_graph() -> None:
    workflow = VibeWorkflow("metadata", WorkflowSource("metadata"))
    text = workflow.add_node("CLIPTextEncode", text="hello")
    save = workflow.add_node("SaveVideo", video="placeholder")
    workflow.connect(f"{text.id}.0", f"{save.id}.video")
    workflow.finalize_metadata()

    converted = convert_to_vibe_format(
        {
            "1": {"class_type": "CLIPTextEncode", "inputs": {"text": "hello"}},
            "2": {"class_type": "SaveVideo", "inputs": {"video": ["1", 0]}},
        },
        workflow_id="metadata",
    )

    assert workflow.inputs == converted.inputs
    assert workflow.outputs == converted.outputs
    assert workflow.requirements == converted.requirements


def test_save_video_registers_output() -> None:
    workflow = VibeWorkflow("video-output", WorkflowSource("video-output"))
    workflow.add_node("SaveVideo", video="placeholder")
    workflow.finalize_metadata()

    assert workflow.outputs == [VibeOutput(node_id="1", output_type="SaveVideo")]


def test_finalize_metadata_orders_outputs_by_numeric_node_id() -> None:
    workflow = VibeWorkflow("ordered-output", WorkflowSource("ordered-output"))
    first = workflow.add_node("SaveVideo", video="placeholder")
    first.id = "12"
    workflow.nodes["12"] = workflow.nodes.pop("1")
    second = workflow.add_node("SaveVideo", video="placeholder")
    second.id = "5"
    workflow.nodes["5"] = workflow.nodes.pop("13")
    workflow.finalize_metadata()

    assert [output.node_id for output in workflow.outputs] == ["5", "12"]
