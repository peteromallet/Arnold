"""Unit tests for deterministic analysis helpers in vibecomfy.analysis.workflow_summary.

Covers: empty graph, single node, large graph, and unknown node types
for infer_task_type, infer_media_type, detect_custom_nodes,
compute_complexity_score, and derive_flags.
"""

from __future__ import annotations

import pytest

from vibecomfy.analysis.workflow_summary import (
    compute_complexity_score,
    derive_flags,
    detect_custom_nodes,
    infer_media_type,
    infer_task_type,
)
from vibecomfy.workflow import (
    VibeEdge,
    VibeNode,
    VibeOutput,
    VibeWorkflow,
    WorkflowSource,
)


def _make_workflow(
    workflow_id: str = "test",
    nodes: dict[str, VibeNode] | None = None,
    edges: list[VibeEdge] | None = None,
    outputs: list[VibeOutput] | None = None,
) -> VibeWorkflow:
    """Build a minimal VibeWorkflow for testing analysis helpers."""
    wf = VibeWorkflow(workflow_id, WorkflowSource(workflow_id))
    if nodes:
        wf.nodes = nodes
    if edges:
        wf.edges = edges
    if outputs:
        wf.outputs = outputs
    return wf


# ── Empty graph ──────────────────────────────────────────────────────────


def test_empty_graph_infer_task_type_returns_other() -> None:
    """Empty workflow with no nodes should return 'other'."""
    wf = _make_workflow()
    assert infer_task_type(wf) == "other"


def test_empty_graph_infer_media_type_defaults_to_image() -> None:
    """Empty workflow should default to 'image' media type."""
    wf = _make_workflow()
    assert infer_media_type(wf) == "image"


def test_empty_graph_detect_custom_nodes_returns_empty() -> None:
    wf = _make_workflow()
    assert detect_custom_nodes(wf) == []


def test_empty_graph_compute_complexity_score_is_1() -> None:
    wf = _make_workflow()
    assert compute_complexity_score(wf) == 1


def test_empty_graph_derive_flags_all_false() -> None:
    wf = _make_workflow()
    flags = derive_flags(wf)
    assert flags == {
        "requires_custom_nodes": False,
        "is_animated": False,
        "has_controlnet": False,
        "has_ipadapter": False,
        "has_lora": False,
        "has_video_output": False,
    }


# ── Single node ──────────────────────────────────────────────────────────


def test_single_clip_text_encode_node_returns_other() -> None:
    """A single CLIPTextEncode node alone cannot be classified."""
    wf = _make_workflow(
        nodes={"1": VibeNode("1", "CLIPTextEncode")},
    )
    assert infer_task_type(wf) == "other"


def test_single_ksampler_node_returns_other() -> None:
    """A single KSampler without text encode or load image is 'other'."""
    wf = _make_workflow(
        nodes={"1": VibeNode("1", "KSampler")},
    )
    assert infer_task_type(wf) == "other"


def test_single_save_image_node_returns_other() -> None:
    wf = _make_workflow(
        nodes={"1": VibeNode("1", "SaveImage")},
    )
    assert infer_task_type(wf) == "other"


def test_single_node_media_type_from_output() -> None:
    """A single SaveImage node with an IMAGE output is 'image'."""
    wf = _make_workflow(
        nodes={"1": VibeNode("1", "SaveImage")},
        outputs=[VibeOutput(node_id="1", output_type="SaveImage")],
    )
    assert infer_media_type(wf) == "image"


def test_single_node_video_output_infers_video() -> None:
    wf = _make_workflow(
        nodes={"1": VibeNode("1", "VHS_VideoCombine")},
        outputs=[VibeOutput(node_id="1", output_type="VHS_VideoCombine")],
    )
    assert infer_media_type(wf) == "video"


def test_single_node_audio_output_infers_audio() -> None:
    wf = _make_workflow(
        nodes={"1": VibeNode("1", "SaveAudio")},
        outputs=[VibeOutput(node_id="1", output_type="SaveAudio")],
    )
    assert infer_media_type(wf) == "audio"


def test_single_node_3d_output_infers_3d() -> None:
    wf = _make_workflow(
        nodes={"1": VibeNode("1", "TripoSR")},
        outputs=[VibeOutput(node_id="1", output_type="TripoSR")],
    )
    assert infer_media_type(wf) == "3d"


def test_single_node_detect_custom_nodes_unknown_is_excluded() -> None:
    """A node with 'Unknown' class_type should not appear as custom."""
    wf = _make_workflow(
        nodes={"1": VibeNode("1", "Unknown")},
    )
    assert detect_custom_nodes(wf) == []


def test_single_node_detect_custom_nodes_empty_class_type_excluded() -> None:
    wf = _make_workflow(
        nodes={"1": VibeNode("1", "")},
    )
    assert detect_custom_nodes(wf) == []


def test_single_node_detect_custom_nodes_true_custom() -> None:
    """A non-core, non-utility node should be detected as custom."""
    wf = _make_workflow(
        nodes={"1": VibeNode("1", "MyCustomAmazingNode")},
    )
    assert detect_custom_nodes(wf) == ["MyCustomAmazingNode"]


def test_single_node_core_node_not_custom() -> None:
    """Core nodes (e.g., KSampler) should not be detected as custom."""
    wf = _make_workflow(
        nodes={"1": VibeNode("1", "KSampler")},
    )
    assert detect_custom_nodes(wf) == []


def test_single_node_utility_node_not_custom() -> None:
    """Utility nodes (e.g., Note) should not be detected as custom."""
    wf = _make_workflow(
        nodes={"1": VibeNode("1", "Note")},
    )
    assert detect_custom_nodes(wf) == []


def test_single_node_complexity_score_is_1() -> None:
    wf = _make_workflow(
        nodes={"1": VibeNode("1", "KSampler")},
    )
    assert compute_complexity_score(wf) == 1


def test_single_node_derive_flags() -> None:
    wf = _make_workflow(
        nodes={"1": VibeNode("1", "KSampler")},
    )
    flags = derive_flags(wf)
    assert flags["requires_custom_nodes"] is False
    assert flags["has_controlnet"] is False
    assert flags["has_lora"] is False


# ── Task type inference ──────────────────────────────────────────────────


def test_text_to_image_detected_with_clip_and_sampler() -> None:
    """CLIPTextEncode + KSampler → text_to_image."""
    wf = _make_workflow(
        nodes={
            "1": VibeNode("1", "CLIPTextEncode"),
            "2": VibeNode("2", "KSampler"),
        },
    )
    assert infer_task_type(wf) == "text_to_image"


def test_image_to_image_detected_with_load_image_and_sampler() -> None:
    """LoadImage + KSampler (no text encode) → image_to_image."""
    wf = _make_workflow(
        nodes={
            "1": VibeNode("1", "LoadImage"),
            "2": VibeNode("2", "KSampler"),
        },
    )
    assert infer_task_type(wf) == "image_to_image"


def test_inpainting_detected() -> None:
    wf = _make_workflow(
        nodes={"1": VibeNode("1", "VAEEncodeForInpaint")},
    )
    assert infer_task_type(wf) == "inpainting"


def test_controlnet_detected() -> None:
    wf = _make_workflow(
        nodes={"1": VibeNode("1", "ControlNetApply")},
    )
    assert infer_task_type(wf) == "controlnet"


def test_upscaling_detected() -> None:
    wf = _make_workflow(
        nodes={"1": VibeNode("1", "ImageUpscaleWithModel")},
    )
    assert infer_task_type(wf) == "upscaling"


def test_video_to_video_detected() -> None:
    """Keyword priority: ``video_to_video`` keywords are checked after
    ``image_to_video``, and some substrings overlap.  ``VideoToVideo``
    contains ``ToVideo`` (an image_to_video keyword) so it's classified
    as image_to_video by the current keyword ordering."""
    wf = _make_workflow(
        nodes={"1": VibeNode("1", "VideoToVideo")},
    )
    assert infer_task_type(wf) == "image_to_video"


def test_video_to_video_detected_via_exact_keyword() -> None:
    """``video_to_video`` keyword survives when not shadowed by earlier
    image_to_video keywords."""
    wf = _make_workflow(
        nodes={"1": VibeNode("1", "SomeVid2VidNode")},
    )
    # No keyword matches → falls through to text/image heuristics,
    # but no text encode or sampler → 'other'
    assert infer_task_type(wf) == "other"


def test_animation_detected() -> None:
    wf = _make_workflow(
        nodes={"1": VibeNode("1", "SaveAnimated")},
    )
    assert infer_task_type(wf) == "animation"


def test_compositing_detected() -> None:
    wf = _make_workflow(
        nodes={"1": VibeNode("1", "ImageCompositeMasked")},
    )
    assert infer_task_type(wf) == "compositing"


def test_lora_training_detected() -> None:
    wf = _make_workflow(
        nodes={"1": VibeNode("1", "LoRATrain")},
    )
    assert infer_task_type(wf) == "lora_training"


def test_image_to_video_detected_via_vhs() -> None:
    wf = _make_workflow(
        nodes={"1": VibeNode("1", "VHS_VideoCombine")},
    )
    assert infer_task_type(wf) == "image_to_video"


def test_image_to_video_detected_via_wan() -> None:
    wf = _make_workflow(
        nodes={"1": VibeNode("1", "WanVideoSampler")},
    )
    assert infer_task_type(wf) == "image_to_video"


def test_image_to_video_detected_via_animatediff() -> None:
    wf = _make_workflow(
        nodes={"1": VibeNode("1", "AnimateDiff")},
    )
    assert infer_task_type(wf) == "image_to_video"


def test_image_to_video_detected_via_mochi() -> None:
    wf = _make_workflow(
        nodes={"1": VibeNode("1", "Mochi")},
    )
    assert infer_task_type(wf) == "image_to_video"


def test_image_to_video_detected_via_ltxv() -> None:
    wf = _make_workflow(
        nodes={"1": VibeNode("1", "LTXV")},
    )
    assert infer_task_type(wf) == "image_to_video"


def test_task_type_priority_inpainting_over_other_keywords() -> None:
    """inpainting is checked first, so VAEEncodeForInpaint wins."""
    wf = _make_workflow(
        nodes={
            "1": VibeNode("1", "VAEEncodeForInpaint"),
            "2": VibeNode("2", "ImageUpscaleWithModel"),  # also matches upscaling
        },
    )
    assert infer_task_type(wf) == "inpainting"


# ── Media type inference ─────────────────────────────────────────────────


def test_media_type_image_from_save_image_output() -> None:
    wf = _make_workflow(
        nodes={"1": VibeNode("1", "SaveImage")},
        outputs=[VibeOutput(node_id="1", output_type="SaveImage")],
    )
    assert infer_media_type(wf) == "image"


def test_media_type_video_from_vhs_output() -> None:
    wf = _make_workflow(
        nodes={"1": VibeNode("1", "VHS_VideoCombine")},
        outputs=[VibeOutput(node_id="1", output_type="VHS_VideoCombine")],
    )
    assert infer_media_type(wf) == "video"


def test_media_type_video_from_save_animated_gif() -> None:
    wf = _make_workflow(
        nodes={"1": VibeNode("1", "SaveAnimatedGIF")},
        outputs=[VibeOutput(node_id="1", output_type="SaveAnimatedGIF")],
    )
    assert infer_media_type(wf) == "video"


def test_media_type_video_from_node_class_name() -> None:
    """Video is detected from node class_type even without explicit output."""
    wf = _make_workflow(
        nodes={"1": VibeNode("1", "SomeVideoProcessor")},
    )
    assert infer_media_type(wf) == "video"


def test_media_type_multi_when_image_and_video_outputs() -> None:
    wf = _make_workflow(
        nodes={
            "1": VibeNode("1", "SaveImage"),
            "2": VibeNode("2", "VHS_VideoCombine"),
        },
        outputs=[
            VibeOutput(node_id="1", output_type="SaveImage"),
            VibeOutput(node_id="2", output_type="VHS_VideoCombine"),
        ],
    )
    assert infer_media_type(wf) == "multi"


def test_media_type_audio_from_save_audio_mp3() -> None:
    wf = _make_workflow(
        nodes={"1": VibeNode("1", "SaveAudioMP3")},
        outputs=[VibeOutput(node_id="1", output_type="SaveAudioMP3")],
    )
    assert infer_media_type(wf) == "audio"


def test_media_type_3d_from_triposr() -> None:
    wf = _make_workflow(
        nodes={"1": VibeNode("1", "TripoSR")},
        outputs=[VibeOutput(node_id="1", output_type="TripoSR")],
    )
    assert infer_media_type(wf) == "3d"


def test_media_type_3d_from_save_glb() -> None:
    wf = _make_workflow(
        nodes={"1": VibeNode("1", "SaveGLB")},
        outputs=[VibeOutput(node_id="1", output_type="SaveGLB")],
    )
    assert infer_media_type(wf) == "3d"


def test_media_type_defaults_to_image_for_unknown_output() -> None:
    wf = _make_workflow(
        nodes={"1": VibeNode("1", "SomeUnknownNode")},
        outputs=[VibeOutput(node_id="1", output_type="SomeUnknownOutput")],
    )
    assert infer_media_type(wf) == "image"


# ── Custom node detection ────────────────────────────────────────────────


def test_detect_custom_nodes_all_core_nodes() -> None:
    """A workflow with only core nodes should return an empty list."""
    wf = _make_workflow(
        nodes={
            "1": VibeNode("1", "CheckpointLoaderSimple"),
            "2": VibeNode("2", "CLIPTextEncode"),
            "3": VibeNode("3", "KSampler"),
            "4": VibeNode("4", "VAEDecode"),
            "5": VibeNode("5", "SaveImage"),
        },
    )
    assert detect_custom_nodes(wf) == []


def test_detect_custom_nodes_mixed() -> None:
    wf = _make_workflow(
        nodes={
            "1": VibeNode("1", "CheckpointLoaderSimple"),
            "2": VibeNode("2", "CLIPTextEncode"),
            "3": VibeNode("3", "KSampler"),
            "4": VibeNode("4", "MyCustomNode"),
            "5": VibeNode("5", "AnotherCustom"),
            "6": VibeNode("6", "VAEDecode"),
            "7": VibeNode("7", "SaveImage"),
        },
    )
    result = detect_custom_nodes(wf)
    assert result == ["AnotherCustom", "MyCustomNode"]  # sorted


def test_detect_custom_nodes_utility_nodes_excluded() -> None:
    wf = _make_workflow(
        nodes={
            "1": VibeNode("1", "Note"),
            "2": VibeNode("2", "Reroute"),
            "3": VibeNode("3", "PrimitiveNode"),
            "4": VibeNode("4", "Fast Groups Bypasser (rgthree)"),
        },
    )
    assert detect_custom_nodes(wf) == []


def test_detect_custom_nodes_deduplicates() -> None:
    wf = _make_workflow(
        nodes={
            "1": VibeNode("1", "RepeatedNode"),
            "2": VibeNode("2", "RepeatedNode"),
            "3": VibeNode("3", "RepeatedNode"),
        },
    )
    assert detect_custom_nodes(wf) == ["RepeatedNode"]


# ── Complexity score ─────────────────────────────────────────────────────


def test_complexity_score_empty_workflow() -> None:
    wf = _make_workflow()
    assert compute_complexity_score(wf) == 1


def test_complexity_score_small_workflow() -> None:
    """≤5 nodes → score 1."""
    wf = _make_workflow(
        nodes={
            str(i): VibeNode(str(i), "CLIPTextEncode") for i in range(1, 6)
        },
    )
    assert compute_complexity_score(wf) == 1


def test_complexity_score_medium_workflow() -> None:
    """6-15 nodes → base score 2."""
    wf = _make_workflow(
        nodes={
            str(i): VibeNode(str(i), "CLIPTextEncode") for i in range(1, 11)
        },
    )
    assert compute_complexity_score(wf) == 2


def test_complexity_score_medium_large_workflow() -> None:
    """16-40 nodes → base score 3."""
    wf = _make_workflow(
        nodes={
            str(i): VibeNode(str(i), "CLIPTextEncode") for i in range(1, 21)
        },
    )
    assert compute_complexity_score(wf) == 3


def test_complexity_score_large_workflow() -> None:
    """41-80 nodes → base score 4."""
    wf = _make_workflow(
        nodes={
            str(i): VibeNode(str(i), "CLIPTextEncode") for i in range(1, 51)
        },
    )
    assert compute_complexity_score(wf) == 4


def test_complexity_score_very_large_workflow() -> None:
    """81+ nodes → base score 5."""
    wf = _make_workflow(
        nodes={
            str(i): VibeNode(str(i), "CLIPTextEncode") for i in range(1, 91)
        },
    )
    assert compute_complexity_score(wf) == 5


def test_complexity_score_edge_density_bonus() -> None:
    """High edge-to-node ratio bumps score up."""
    nodes = {str(i): VibeNode(str(i), "KSampler") for i in range(1, 4)}  # 3 nodes
    # 7 edges → ratio > 2.0 → bump from 1 to at least 2
    edges = [
        VibeEdge("1", "0", "2", "latent"),
        VibeEdge("1", "0", "3", "latent"),
        VibeEdge("2", "0", "1", "positive"),
        VibeEdge("2", "0", "3", "positive"),
        VibeEdge("3", "0", "1", "negative"),
        VibeEdge("3", "0", "2", "negative"),
        VibeEdge("1", "0", "2", "model"),
    ]
    wf = _make_workflow(nodes=nodes, edges=edges)
    # base=1, edge_ratio=7/3≈2.33 > 2.0 → +1 → still ≤5
    score = compute_complexity_score(wf)
    assert score == 2


def test_complexity_score_custom_nodes_bonus() -> None:
    """Many custom nodes bump score up."""
    # 6 nodes → base score 2
    nodes = {
        str(i): VibeNode(str(i), f"CustomNode{i}") for i in range(1, 7)
    }
    wf = _make_workflow(nodes=nodes)
    # custom_count=6 > 5 → +1 → 3
    assert compute_complexity_score(wf) == 3


def test_complexity_score_capped_at_5() -> None:
    """Score must never exceed 5."""
    # 100 nodes → base 5, plus many edges and custom nodes → still 5
    nodes = {
        str(i): VibeNode(str(i), f"Custom{i}") for i in range(1, 101)
    }
    edges = []
    for i in range(1, 100):
        edges.append(VibeEdge(str(i), "0", str(i + 1), "input"))
        edges.append(VibeEdge(str(i + 1), "0", str(i), "input"))
    wf = _make_workflow(nodes=nodes, edges=edges)
    assert compute_complexity_score(wf) == 5


# ── Flags derivation ─────────────────────────────────────────────────────


def test_derive_flags_requires_custom_nodes_when_custom_present() -> None:
    wf = _make_workflow(
        nodes={
            "1": VibeNode("1", "KSampler"),
            "2": VibeNode("2", "CustomNode"),
        },
    )
    flags = derive_flags(wf)
    assert flags["requires_custom_nodes"] is True


def test_derive_flags_requires_custom_nodes_false_when_only_core() -> None:
    wf = _make_workflow(
        nodes={
            "1": VibeNode("1", "KSampler"),
            "2": VibeNode("2", "CLIPTextEncode"),
        },
    )
    flags = derive_flags(wf)
    assert flags["requires_custom_nodes"] is False


def test_derive_flags_is_animated_true() -> None:
    wf = _make_workflow(
        nodes={"1": VibeNode("1", "SaveAnimatedWEBP")},
    )
    flags = derive_flags(wf)
    assert flags["is_animated"] is True


def test_derive_flags_is_animated_true_for_video() -> None:
    wf = _make_workflow(
        nodes={"1": VibeNode("1", "VHS_VideoCombine")},
    )
    flags = derive_flags(wf)
    assert flags["is_animated"] is True


def test_derive_flags_has_controlnet_true() -> None:
    wf = _make_workflow(
        nodes={"1": VibeNode("1", "ControlNetApply")},
    )
    flags = derive_flags(wf)
    assert flags["has_controlnet"] is True


def test_derive_flags_has_ipadapter_true() -> None:
    wf = _make_workflow(
        nodes={"1": VibeNode("1", "IPAdapter")},
    )
    flags = derive_flags(wf)
    assert flags["has_ipadapter"] is True


def test_derive_flags_has_lora_true() -> None:
    wf = _make_workflow(
        nodes={"1": VibeNode("1", "LoraLoader")},
    )
    flags = derive_flags(wf)
    assert flags["has_lora"] is True


def test_derive_flags_has_video_output_true() -> None:
    wf = _make_workflow(
        nodes={"1": VibeNode("1", "VHS_VideoCombine")},
        outputs=[VibeOutput(node_id="1", output_type="VHS_VideoCombine")],
    )
    flags = derive_flags(wf)
    assert flags["has_video_output"] is True


def test_derive_flags_all_false_for_simple_image_workflow() -> None:
    wf = _make_workflow(
        nodes={
            "1": VibeNode("1", "CheckpointLoaderSimple"),
            "2": VibeNode("2", "CLIPTextEncode"),
            "3": VibeNode("3", "KSampler"),
            "4": VibeNode("4", "VAEDecode"),
            "5": VibeNode("5", "SaveImage"),
        },
    )
    flags = derive_flags(wf)
    assert flags == {
        "requires_custom_nodes": False,
        "is_animated": False,
        "has_controlnet": False,
        "has_ipadapter": False,
        "has_lora": False,
        "has_video_output": False,
    }


# ── Large graph / integration-style scenarios ────────────────────────────


def test_large_graph_all_functions_handle_100_nodes() -> None:
    """Smoke test: all functions should handle a 100-node workflow without error."""
    nodes = {}
    for i in range(1, 101):
        # Mix of core, custom, and video nodes
        if i % 4 == 0:
            ct = "CLIPTextEncode"
        elif i % 4 == 1:
            ct = "KSampler"
        elif i % 4 == 2:
            ct = f"CustomNode{i}"
        else:
            ct = "VHS_VideoCombine"
        nodes[str(i)] = VibeNode(str(i), ct)

    edges = []
    for i in range(1, 100):
        edges.append(VibeEdge(str(i), "0", str(i + 1), "input"))

    outputs = [VibeOutput(node_id="1", output_type="VHS_VideoCombine")]

    wf = _make_workflow(nodes=nodes, edges=edges, outputs=outputs)

    # All functions should return without error
    task_type = infer_task_type(wf)
    media_type = infer_media_type(wf)
    custom_nodes = detect_custom_nodes(wf)
    complexity = compute_complexity_score(wf)
    flags = derive_flags(wf)

    # Basic sanity
    assert isinstance(task_type, str)
    assert media_type == "video"  # VHS_VideoCombine nodes present, output type matches
    # 25 unique CustomNode{i} class types + 1 VHS_VideoCombine = 26
    assert len(custom_nodes) == 26
    assert 1 <= complexity <= 5
    assert isinstance(flags, dict)
    assert flags["has_video_output"] is True
    assert flags["requires_custom_nodes"] is True


def test_large_graph_task_type_is_stable() -> None:
    """Very large graph with many nodes but clear inpainting signal."""
    nodes = {}
    for i in range(1, 201):
        ct = "KSampler" if i != 100 else "VAEEncodeForInpaint"
        nodes[str(i)] = VibeNode(str(i), ct)
    wf = _make_workflow(nodes=nodes)
    assert infer_task_type(wf) == "inpainting"


# ── Unknown node types ───────────────────────────────────────────────────


def test_unknown_node_type_infer_task_type_returns_other() -> None:
    """Completely unknown node class names should yield 'other'."""
    wf = _make_workflow(
        nodes={
            "1": VibeNode("1", "FlarbGarbNode"),
            "2": VibeNode("2", "ZargBlargProcessor"),
        },
    )
    assert infer_task_type(wf) == "other"


def test_unknown_node_type_media_type_defaults_to_image() -> None:
    wf = _make_workflow(
        nodes={
            "1": VibeNode("1", "FlarbGarbNode"),
        },
    )
    assert infer_media_type(wf) == "image"


def test_unknown_node_type_detected_as_custom() -> None:
    """Nodes not in core or utility sets are custom nodes."""
    wf = _make_workflow(
        nodes={
            "1": VibeNode("1", "FlarbGarbNode"),
            "2": VibeNode("2", "ZargBlargProcessor"),
        },
    )
    assert detect_custom_nodes(wf) == ["FlarbGarbNode", "ZargBlargProcessor"]


def test_unknown_node_type_complexity_is_proportional_to_count() -> None:
    """Even unknown nodes contribute to complexity."""
    wf_small = _make_workflow(
        nodes={str(i): VibeNode(str(i), "UnknownNode") for i in range(1, 4)},
    )
    wf_large = _make_workflow(
        nodes={str(i): VibeNode(str(i), "UnknownNode") for i in range(1, 51)},
    )
    assert compute_complexity_score(wf_small) == 1
    assert compute_complexity_score(wf_large) == 4


def test_unknown_node_type_flags() -> None:
    wf = _make_workflow(
        nodes={
            "1": VibeNode("1", "FlarbGarbNode"),
        },
    )
    flags = derive_flags(wf)
    # The single unknown node IS a custom node
    assert flags["requires_custom_nodes"] is True
    assert flags["is_animated"] is False
    assert flags["has_controlnet"] is False
    assert flags["has_ipadapter"] is False
    assert flags["has_lora"] is False
    assert flags["has_video_output"] is False


def test_mixed_known_and_unknown_nodes() -> None:
    """Workflow with a mix of core and completely unknown nodes."""
    wf = _make_workflow(
        nodes={
            "1": VibeNode("1", "CLIPTextEncode"),
            "2": VibeNode("2", "KSampler"),
            "3": VibeNode("3", "VAEDecode"),
            "4": VibeNode("4", "CompletelyUnknown"),
            "5": VibeNode("5", "AnotherUnknown"),
        },
    )
    assert infer_task_type(wf) == "text_to_image"
    assert detect_custom_nodes(wf) == ["AnotherUnknown", "CompletelyUnknown"]
    # 5 nodes ≤ 5 → base score 1; 2 custom nodes (≤5) → no bonus
    assert compute_complexity_score(wf) == 1
    flags = derive_flags(wf)
    assert flags["requires_custom_nodes"] is True


def test_node_with_xl_text_encode_detects_text_to_image() -> None:
    """SDXL CLIPTextEncode variant still detects text_to_image."""
    wf = _make_workflow(
        nodes={
            "1": VibeNode("1", "CLIPTextEncodeSDXL"),
            "2": VibeNode("2", "KSampler"),
        },
    )
    assert infer_task_type(wf) == "text_to_image"


def test_node_with_ipadapter_advanced() -> None:
    """IPAdapter-Advanced should be detected in flags."""
    wf = _make_workflow(
        nodes={"1": VibeNode("1", "IPAdapter-Advanced")},
    )
    flags = derive_flags(wf)
    assert flags["has_ipadapter"] is True
