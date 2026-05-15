from __future__ import annotations

from vibecomfy.ingest.normalize import convert_to_vibe_format
from vibecomfy.registry.ready_template import bind_input
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


def test_finalize_metadata_clears_bind_input_registered_inputs() -> None:
    """Regression: finalize_metadata() clears ALL registered inputs including
    those added by bind_input().  This is why bind_input must be called AFTER
    finalize_metadata/finalize_ready_template in generated code."""
    workflow = VibeWorkflow("regression", WorkflowSource("regression"))
    workflow.add_node("LoadImage", image="placeholder")
    workflow.add_node("SaveImage", filename_prefix="out/regression")
    workflow.connect("1.0", "2.images")

    # Simulate the wrong order: bind_input before finalize_metadata
    bind_input(workflow, "prefix", "2", "filename_prefix")
    assert "prefix" in workflow.inputs  # Present now

    workflow.finalize_metadata()

    # The registered input must be gone
    assert "prefix" not in workflow.inputs, (
        "finalize_metadata() must clear all registered inputs, "
        "including those from bind_input()"
    )
