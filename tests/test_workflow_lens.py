"""Lens integration tests covering generic graph behaviour and
first/last conditioning on the LTX parity template.

All intent assertions in this module operate through the
:mod:`vibecomfy.lens` layer without reaching for compiled Comfy API
JSON link checks.
"""

from __future__ import annotations

import pytest

from vibecomfy.lens import (
    diagnostics,
    edge_source,
    edge_targets,
    lens,
    node_value,
    nodes_by_class_type,
    outputs,
    registered_input_target,
    upstream,
    downstream,
)
from vibecomfy.registry.ready import workflow_from_ready
from vibecomfy.workflow import VibeWorkflow, WorkflowSource


# ── helpers ────────────────────────────────────────────────────────────────


def _tiny_first_last_workflow() -> VibeWorkflow:
    """Build a tiny (8-node) workflow that mimics a stripped-down first/last
    conditioning pattern so lens queries can be exercised on a predictable
    graph with known edge topology."""
    wf = VibeWorkflow(
        "tiny/first_last_smoke",
        WorkflowSource(id="tiny/first_last_smoke", source_type="fixture"),
    )

    # Use wf.node() for builder pattern (it supports Handle connections)
    start_img = wf.node("LoadImage", image="start.png")
    end_img = wf.node("LoadImage", image="end.png")

    resize = wf.node(
        "ResizeImageMaskNode",
        widget_0="scale longer dimension",
        widget_1=256,
        widget_2="lanczos",
        input=start_img.out(0),
    )
    condition = wf.node(
        "LTXVImgToVideoConditionOnly",
        widget_0=1.0,
        widget_1=False,
        image=resize.out(0),
    )

    resize2 = wf.node(
        "ResizeImageMaskNode",
        widget_0="scale longer dimension",
        widget_1=256,
        widget_2="lanczos",
        input=end_img.out(0),
    )
    condition2 = wf.node(
        "LTXVImgToVideoConditionOnly",
        widget_0=1.0,
        widget_1=False,
        image=resize2.out(0),
    )

    wf.finalize_metadata()
    wf.register_input("start_image", start_img.node.id, "image", "start.png")
    wf.register_input("end_image", end_img.node.id, "image", "end.png")
    wf.register_input("first_frame_strength", condition.node.id, "widget_0", 1.0)
    wf.register_input("last_frame_strength", condition2.node.id, "widget_0", 1.0)
    return wf


# ── generic lens behaviour ────────────────────────────────────────────────


def test_lens_edge_source_on_tiny_workflow() -> None:
    """edge_source resolves conditioning edges on a tiny authored graph."""
    wf = _tiny_first_last_workflow()
    l = lens(wf)

    # The first LTXVImgToVideoConditionOnly should have its .image input fed
    # by the ResizeImageMaskNode.
    cond_nodes = nodes_by_class_type(wf, "LTXVImgToVideoConditionOnly")
    assert len(cond_nodes) == 2

    # First condition node gets its image from a ResizeImageMaskNode
    src0 = l.edge_source(cond_nodes[0].id, "image")
    assert src0 is not None
    assert wf.nodes[src0.from_node].class_type == "ResizeImageMaskNode"

    # Second condition node also gets its image from a ResizeImageMaskNode
    src1 = l.edge_source(cond_nodes[1].id, "image")
    assert src1 is not None
    assert wf.nodes[src1.from_node].class_type == "ResizeImageMaskNode"

    # The two ResizeImageMaskNode sources should be distinct
    assert src0.from_node != src1.from_node


def test_lens_edge_source_returns_none_for_widget_input() -> None:
    """edge_source returns None when the input is widget-fed, not edge-fed."""
    wf = _tiny_first_last_workflow()

    # widget_0 on a condition node is a static value, not an edge
    cond_nodes = nodes_by_class_type(wf, "LTXVImgToVideoConditionOnly")
    assert lens(wf).edge_source(cond_nodes[0].id, "widget_0") is None


def test_lens_edge_targets_on_tiny_workflow() -> None:
    """edge_targets enumerates downstream sinks from a source node."""
    wf = _tiny_first_last_workflow()
    l = lens(wf)

    # Every ResizeImageMaskNode feeds exactly one LTXVImgToVideoConditionOnly
    resize_nodes = nodes_by_class_type(wf, "ResizeImageMaskNode")
    assert len(resize_nodes) == 2

    for rn in resize_nodes:
        targets = l.edge_targets(rn.id)
        assert len(targets) == 1
        assert wf.nodes[targets[0].to_node].class_type == "LTXVImgToVideoConditionOnly"


def test_lens_upstream_downstream_on_tiny_workflow() -> None:
    """upstream/downstream produce correct one-level traversal sets."""
    wf = _tiny_first_last_workflow()
    l = lens(wf)

    cond_nodes = nodes_by_class_type(wf, "LTXVImgToVideoConditionOnly")
    for cn in cond_nodes:
        up = l.upstream(cn.id)
        assert len(up) == 1
        up_node_id = next(iter(up))
        assert wf.nodes[up_node_id].class_type == "ResizeImageMaskNode"

    resize_nodes = nodes_by_class_type(wf, "ResizeImageMaskNode")
    for rn in resize_nodes:
        down = l.downstream(rn.id)
        assert len(down) == 1
        down_node_id = next(iter(down))
        assert wf.nodes[down_node_id].class_type == "LTXVImgToVideoConditionOnly"


def test_lens_registered_input_target_on_tiny_workflow() -> None:
    """registered_input_target finds inputs registered by name."""
    wf = _tiny_first_last_workflow()
    l = lens(wf)

    si = l.registered_input_target("start_image")
    assert si is not None
    assert si.node_id == "1"  # first node created in tiny workflow

    ei = l.registered_input_target("end_image")
    assert ei is not None

    # Missing input
    assert l.registered_input_target("nonexistent") is None


def test_lens_node_value_reads_widgets_and_inputs() -> None:
    """node_value reads from widgets (priority) then inputs."""
    wf = _tiny_first_last_workflow()
    l = lens(wf)

    cond_nodes = nodes_by_class_type(wf, "LTXVImgToVideoConditionOnly")
    assert len(cond_nodes) == 2
    for cn in cond_nodes:
        assert l.node_value(cn.id, "widget_0") == 1.0
        assert l.node_value(cn.id, "widget_1") is False


def test_lens_nodes_by_class_type_on_tiny_workflow() -> None:
    """nodes_by_class_type filters by exact class_type."""
    wf = _tiny_first_last_workflow()

    assert len(nodes_by_class_type(wf, "LoadImage")) == 2
    assert len(nodes_by_class_type(wf, "ResizeImageMaskNode")) == 2
    assert len(nodes_by_class_type(wf, "LTXVImgToVideoConditionOnly")) == 2
    assert len(nodes_by_class_type(wf, "SaveImage")) == 0


def test_lens_diagnostics_on_tiny_workflow() -> None:
    """diagnostics produces a readable multi-line summary."""
    wf = _tiny_first_last_workflow()
    diag = diagnostics(wf)

    assert "tiny/first_last_smoke" in diag
    assert "LTXVImgToVideoConditionOnly" in diag
    assert "ResizeImageMaskNode" in diag
    assert "LoadImage" in diag


def test_lens_outputs_on_tiny_workflow() -> None:
    """outputs() returns declared workflow outputs."""
    wf = _tiny_first_last_workflow()
    outs = outputs(wf)
    # No output node class types in this tiny fixture, so no outputs
    assert isinstance(outs, list)


# ── LTX parity template smoke through the lens ───────────────────────────


def test_lens_ltx_parity_registered_inputs_via_lens() -> None:
    """All 12 named LTX parity inputs are discoverable through the lens
    without reaching for compiled Comfy API JSON."""
    wf = workflow_from_ready("video/ltx2_3_lightricks_first_last_parity")
    l = lens(wf)

    required = {
        "first_image", "last_image", "prompt", "negative_prompt",
        "seed_first", "seed_last", "frames", "width", "height", "fps",
        "model", "vae",
    }
    for name in required:
        inp = l.registered_input_target(name)
        assert inp is not None, f"missing registered input: {name}"
        assert isinstance(inp.node_id, str) and len(inp.node_id) > 0


def test_lens_ltx_parity_first_last_conditioning_via_lens() -> None:
    """First and last-frame conditioning nodes exist and receive image feeds,
    verified entirely through the lens without compiled link assertions."""
    wf = workflow_from_ready("video/ltx2_3_lightricks_first_last_parity")
    l = lens(wf)

    # Find the two stage conditioning nodes
    cond_nodes = nodes_by_class_type(wf, "LTXVImgToVideoConditionOnly")
    cond_by_id = {n.id: n for n in cond_nodes}
    assert "3159" in cond_by_id, "stage-1 first-frame conditioning node missing"
    assert "4970" in cond_by_id, "stage-2 last-frame conditioning node missing"

    # Stage 1 (first frame): node 3159 receives image from upstream
    src_stage1 = l.edge_source("3159", "image")
    assert src_stage1 is not None, "stage-1 condition node has no image feed"
    upstream_stage1 = wf.nodes[src_stage1.from_node]
    assert upstream_stage1.class_type == "LTXVPreprocess", (
        f"stage-1 image should come from LTXVPreprocess, got {upstream_stage1.class_type}"
    )

    # Stage 2 (last frame): node 4970 receives image from upstream
    src_stage2 = l.edge_source("4970", "image")
    assert src_stage2 is not None, "stage-2 condition node has no image feed"
    upstream_stage2 = wf.nodes[src_stage2.from_node]
    assert upstream_stage2.class_type == "ResizeImageMaskNode", (
        f"stage-2 image should come from ResizeImageMaskNode, got {upstream_stage2.class_type}"
    )

    # Verify that stage 1's LTXVPreprocess is fed by a ResizeImageMaskNode (4990)
    preproc_src = l.edge_source("3336", "image")
    assert preproc_src is not None, "LTXVPreprocess has no image feed"
    assert preproc_src.from_node == "4990"

    # Verify the stage-2 ResizeImageMaskNode (4991) is fed by LoadImage (2005, last_image)
    resize_src = l.edge_source("4991", "input")
    assert resize_src is not None
    assert resize_src.from_node == "2005"


def test_lens_ltx_parity_prompt_negative_paths_via_lens() -> None:
    """Prompt and negative CLIPTextEncode nodes exist with correct text content,
    verified through the lens."""
    wf = workflow_from_ready("video/ltx2_3_lightricks_first_last_parity")
    l = lens(wf)

    # Prompt node 2483
    prompt_val = l.node_value("2483", "text")
    assert isinstance(prompt_val, str) and len(prompt_val) > 0

    # Negative node 2612
    neg_val = l.node_value("2612", "text")
    assert isinstance(neg_val, str) and len(neg_val) > 0

    # Both are fed by an LTXAVTextEncoderLoader (4982)
    for nid in ("2483", "2612"):
        src = l.edge_source(nid, "clip")
        assert src is not None, f"{nid} has no clip source"
        assert wf.nodes[src.from_node].class_type == "LTXAVTextEncoderLoader"


def test_lens_ltx_parity_seeds_via_lens() -> None:
    """Both seed nodes (4832, 4967) are RandomNoise with fixed control
    attributes, verified through the lens."""
    wf = workflow_from_ready("video/ltx2_3_lightricks_first_last_parity")
    l = lens(wf)

    for nid in ("4832", "4967"):
        noise_class = wf.nodes[nid].class_type
        assert noise_class == "RandomNoise", f"node {nid} is {noise_class}, expected RandomNoise"
        assert l.node_value(nid, "noise_seed") is not None
        cag = l.node_value(nid, "control_after_generate")
        assert cag == "fixed", f"node {nid} control_after_generate={cag}"


def test_lens_ltx_parity_dimensions_frames_fps_via_lens() -> None:
    """Dimensions (3059), frames (4988), and FPS (4989) are readable
    through the lens without compiled API checks."""
    wf = workflow_from_ready("video/ltx2_3_lightricks_first_last_parity")
    l = lens(wf)

    # EmptyLTXVLatentVideo 3059 carries width/height
    assert wf.nodes["3059"].class_type == "EmptyLTXVLatentVideo"
    width = l.node_value("3059", "width")
    height = l.node_value("3059", "height")
    assert isinstance(width, int) and width > 0
    assert isinstance(height, int) and height > 0

    # frames → PrimitiveInt 4988
    assert wf.nodes["4988"].class_type == "PrimitiveInt"
    frames = l.node_value("4988", "value")
    assert isinstance(frames, int) and frames > 0

    # fps → PrimitiveFloat 4989
    assert wf.nodes["4989"].class_type == "PrimitiveFloat"
    fps = l.node_value("4989", "value")
    assert isinstance(fps, (int, float)) and fps > 0


def test_lens_ltx_parity_stage2_sigmas_via_lens() -> None:
    """Stage-2 ManualSigmas (4985) carries the Wan2GP-parity sigma string,
    verified through the lens."""
    wf = workflow_from_ready("video/ltx2_3_lightricks_first_last_parity")
    l = lens(wf)

    assert wf.nodes["4985"].class_type == "ManualSigmas"
    sigmas = l.node_value("4985", "widget_0")
    assert sigmas == "0.909375, 0.725, 0.421875, 0.0", (
        f"stage-2 sigmas drifted: {sigmas!r}"
    )


def test_lens_ltx_parity_strength_defaults_via_lens() -> None:
    """First/last frame strength defaults are 1.0, verified through the lens."""
    wf = workflow_from_ready("video/ltx2_3_lightricks_first_last_parity")
    l = lens(wf)

    assert l.node_value("3159", "widget_0") == 1.0, "first_frame_strength default != 1.0"
    assert l.node_value("4970", "widget_0") == 1.0, "last_frame_strength default != 1.0"


def test_lens_ltx_parity_custom_nodes_via_lens() -> None:
    """Declared custom nodes match expectations, verified through requirements
    metadata (reachable through the workflow, not compiled JSON)."""
    wf = workflow_from_ready("video/ltx2_3_lightricks_first_last_parity")

    assert "ComfyUI-LTXVideo" in wf.requirements.custom_nodes
    assert "ComfyUI-KJNodes" in wf.requirements.custom_nodes
    assert "rgthree-comfy" not in wf.requirements.custom_nodes


def test_lens_ltx_parity_no_runexx_only_packs_via_lens() -> None:
    """Runexx-only node types are absent from the parity template,
    verified through the lens."""
    wf = workflow_from_ready("video/ltx2_3_lightricks_first_last_parity")

    forbidden = {
        "LTXVAddGuide",
        "LTXICLoRALoaderModelOnly",
        "LTXAddVideoICLoRAGuide",
        "LTX2MemoryEfficientSageAttentionPatch",
        "LTX2SamplingPreviewOverride",
    }
    found = forbidden & {n.class_type for n in wf.nodes.values()}
    assert found == set(), f"Runexx-only nodes leaked into parity template: {found}"


def test_lens_ltx_parity_video_output_via_lens() -> None:
    """SaveVideo output materialization is discoverable through the lens
    without compiled API output index checks."""
    wf = workflow_from_ready("video/ltx2_3_lightricks_first_last_parity")
    l = lens(wf)

    outs = l.outputs()
    save_video_outs = [o for o in outs if o.output_type == "SaveVideo"]
    assert len(save_video_outs) >= 1, "no SaveVideo output materialization found"

    # The SaveVideo node should be downstream of something
    for svo in save_video_outs:
        up = l.upstream(svo.node_id)
        assert len(up) > 0, f"SaveVideo {svo.node_id} is disconnected"


def test_lens_ltx_parity_source_is_pure_python() -> None:
    """The parity template is a manual ready Python template, not a JSON
    wrapper."""
    wf = workflow_from_ready("video/ltx2_3_lightricks_first_last_parity")

    assert wf.metadata["source_role"] == "manual_ready_python_template"
    assert wf.metadata["coverage_tier"] == "required"


def test_lens_ltx_parity_diagnostics_produces_readable_summary() -> None:
    """diagnostics on the real parity template produces a useful human-readable
    summary with node count, inputs, and outputs."""
    wf = workflow_from_ready("video/ltx2_3_lightricks_first_last_parity")
    diag = diagnostics(wf)

    assert "video/ltx2_3_lightricks_first_last_parity" in diag
    assert "LTXVImgToVideoConditionOnly" in diag
    assert "SaveVideo" in diag
    # Verify input count is reasonable
    assert "inputs (13)" in diag
