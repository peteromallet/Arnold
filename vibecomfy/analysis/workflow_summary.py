"""Deterministic analysis helpers for deriving workflow summary fields.

These functions compute ``task_type``, ``media_type``, ``flags``, and
``complexity`` from a ``VibeWorkflow``'s structural properties (node class
names, output types, edge count, etc.).  They are designed to be stable
across the full corpus — no randomness, no LLM dependency.

SD2 compliance: ``task_type``, ``media_type``, ``flags``, and ``complexity``
are derived deterministically; only ``title``, ``description``, and ``tags``
come from the LLM.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from vibecomfy.workflow import VibeWorkflow


# ── Core ComfyUI node class names ──────────────────────────────────────
# Nodes in this set are considered "built-in" / "core" and are excluded
# from custom-node detection.  This list is deliberately broad to avoid
# false positives on common nodes that ship with ComfyUI itself.
_CORE_CLASS_NAMES: frozenset[str] = frozenset({
    # Loaders
    "CheckpointLoader",
    "CheckpointLoaderSimple",
    "CLIPLoader",
    "ControlNetLoader",
    "DualCLIPLoader",
    "GLIGENLoader",
    "HypernetworkLoader",
    "LoraLoader",
    "LoraLoaderModelOnly",
    "StyleModelLoader",
    "UNETLoader",
    "UpscaleModelLoader",
    "VAELoader",
    # Encoders
    "CLIPTextEncode",
    "CLIPTextEncodeSDXL",
    "CLIPTextEncodeSDXLRefiner",
    "CLIPVisionEncode",
    "VAEEncode",
    "VAEEncodeForInpaint",
    # Samplers
    "KSampler",
    "KSamplerAdvanced",
    "KSamplerSelect",
    # Decoders
    "VAEDecode",
    "VAEDecodeTiled",
    # Latent
    "EmptyLatentImage",
    "LatentBlend",
    "LatentComposite",
    "LatentCompositeMasked",
    "LatentCrop",
    "LatentFlip",
    "LatentRotate",
    "LatentUpscale",
    # Image I/O
    "LoadImage",
    "LoadImageMask",
    "PreviewImage",
    "SaveImage",
    "SaveImageWebsocket",
    # Conditioning
    "ConditioningAverage",
    "ConditioningCombine",
    "ConditioningConcat",
    "ConditioningSetArea",
    "ConditioningSetAreaPercentage",
    "ConditioningSetMask",
    "ConditioningSetTimestepRange",
    "ConditioningZeroOut",
    # Model patches
    "ModelSamplingDiscrete",
    "ModelSamplingStableCascade",
    "ModelSamplingSD3",
    # Misc utilities
    "ImageScale",
    "ImageScaleBy",
    "ImageUpscaleWithModel",
    "PadImageForOutpaint",
    "SetLatentNoiseMask",
    # ControlNet
    "ControlNetApply",
    "ControlNetApplyAdvanced",
    # Inpaint
    "VAEEncodeForInpaint",
})


# ── Node-class → task_type keyword mapping ─────────────────────────────
# Ordered by priority: earlier matches win when multiple keywords are found.
_TASK_KEYWORD_MAP: tuple[tuple[str, frozenset[str]], ...] = (
    ("inpainting", frozenset({"inpaint", "Inpaint"})),
    ("outpainting", frozenset({"outpaint", "Outpaint"})),
    ("controlnet", frozenset({"ControlNet", "controlnet"})),
    ("lora_training", frozenset({"LoRATrain", "lora_train", "LoraTrain"})),
    (
        "image_to_video",
        frozenset({
            "WanVideo", "wan_video", "WANVideo",
            "AnimateDiff", "animatediff",
            "VideoCombine", "VHS_VideoCombine", "VHS_LoadVideo",
            "ToVideo", "to_video",
            "Mochi", "mochi",
            "LTXV", "ltxv",
        }),
    ),
    (
        "video_to_video",
        frozenset({
            "VideoToVideo", "video_to_video",
        }),
    ),
    (
        "animation",
        frozenset({
            "Animate", "animate", "Animation",
            "SaveAnimated", "SaveWEBM", "SaveGIF",
        }),
    ),
    (
        "upscaling",
        frozenset({
            "Upscale", "upscale", "ImageResize",
            "SuperResolution", "super_resolution",
        }),
    ),
    (
        "compositing",
        frozenset({
            "Composite", "composite", "ImageBlend",
            "MaskComposite", "ImageCompositeMasked",
        }),
    ),
    (
        "image_to_image",
        frozenset({
            "Img2Img", "img2img", "ImageToImage", "image_to_image",
        }),
    ),
)


# ── Output-type → media_type mapping ───────────────────────────────────
_VIDEO_OUTPUT_TYPES: frozenset[str] = frozenset({
    "VHS_VideoCombine", "SaveVideo", "SaveAnimatedWEBP",
    "SaveAnimatedPNG", "SaveAnimatedGIF", "SaveWEBM",
    "VideoCombine", "WanVideoDecode", "WanVideoSampler",
})

_AUDIO_OUTPUT_TYPES: frozenset[str] = frozenset({
    "SaveAudio", "SaveAudioMP3", "VHS_LoadAudio",
})

_IMAGE_OUTPUT_TYPES: frozenset[str] = frozenset({
    "SaveImage", "PreviewImage", "SaveImageWebsocket",
})

_3D_OUTPUT_TYPES: frozenset[str] = frozenset({
    "CreateCameraInfo", "EmptyLatentHunyuan3Dv2", "File3DToSplat",
    "GetSplatCount", "Hunyuan3Dv2Conditioning",
    "Hunyuan3Dv2ConditioningMultiView", "Load3D", "MergeSplat",
    "MeshyAnimateModelNode", "MeshyImageToModelNode",
    "MeshyMultiImageToModelNode", "MeshyRefineNode",
    "MeshyRigModelNode", "MeshyTextToModelNode", "MeshyTextureNode",
    "Preview3D", "Preview3DAdvanced", "RenderSplat", "Rodin3D_Detail",
    "Rodin3D_Gen2", "Rodin3D_Gen25_Image", "Rodin3D_Gen25_Text",
    "Rodin3D_Regular", "Rodin3D_Sketch", "Rodin3D_Smooth",
    "SV3D_Conditioning", "Save3D", "SaveGLB", "SaveOBJ",
    "SplatToFile3D", "SplatToMesh", "StableZero123",
    "StableZero123_Conditioning", "StableZero123_Conditioning_Batched",
    "Tencent3DPartNode", "Tencent3DTextureEditNode",
    "TencentImageToModelNode", "TencentModelTo3DUVNode",
    "TencentSmartTopologyNode", "TencentTextToModelNode",
    "TransformSplat", "TripoConversionNode", "TripoImageToModelNode",
    "TripoMultiviewToModelNode", "TripoP1ImageToModelNode",
    "TripoP1MultiviewToModelNode", "TripoP1TextToModelNode",
    "TripoRefineNode", "TripoRetargetNode", "TripoRigNode",
    "TripoSR", "TripoSplatConditioning", "TripoSplatPreprocessImage",
    "TripoSplatSamplingPreview", "TripoTextToModelNode",
    "TripoTextureNode", "VAEDecodeHunyuan3D", "VAEDecodeTripoSplat",
    "VoxelToMesh", "VoxelToMeshBasic",
})


def infer_task_type(workflow: "VibeWorkflow") -> str:
    """Derive the high-level task category from node class names.

    Returns one of:
    ``text_to_image``, ``image_to_image``, ``image_to_video``,
    ``video_to_video``, ``inpainting``, ``outpainting``, ``upscaling``,
    ``animation``, ``lora_training``, ``controlnet``, ``compositing``,
    ``other``.
    """
    # Collect all class names (case-sensitive preserved).
    class_names: list[str] = [
        node.class_type for node in workflow.nodes.values()
    ]

    # Check for text-to-image indicators: presence of CLIPTextEncode (text
    # prompt encoding) + KSampler implies generation from text.
    has_text_encode = any(
        "TextEncode" in cn or "CLIPTextEncode" in cn for cn in class_names
    )
    has_sampler = any(
        "Sampler" in cn and "Select" not in cn for cn in class_names
    )

    # Build a combined string for keyword scanning.
    combined = " ".join(class_names)

    # Scan ordered keyword map; first match wins.
    for task_type, keywords in _TASK_KEYWORD_MAP:
        for kw in keywords:
            if kw in combined:
                # Special case: "animation" overrides only if we have video
                # outputs, otherwise fall through.
                if task_type == "animation":
                    return "animation"
                if task_type == "compositing":
                    return "compositing"
                return task_type

    # Heuristic: image_to_video when VHS nodes are present.
    if any("VHS_VideoCombine" in cn or "VHS_LoadVideo" in cn for cn in class_names):
        return "image_to_video"

    # Heuristic: text_to_image when text encoding + sampler present
    if has_text_encode and has_sampler:
        return "text_to_image"

    # Heuristic: image_to_image when LoadImage + sampler present (no text)
    has_load_image = any("LoadImage" in cn for cn in class_names)
    if has_load_image and has_sampler:
        return "image_to_image"

    # Default
    return "other"


def infer_media_type(workflow: "VibeWorkflow") -> str:
    """Derive the dominant media type from output node types.

    Returns one of: ``image``, ``video``, ``audio``, ``3d``, ``multi``.
    """
    output_types: set[str] = set()
    for output in workflow.outputs:
        output_types.add(output.output_type)

    # Also inspect node class types for media indicators.
    node_class_types: set[str] = {
        node.class_type for node in workflow.nodes.values()
    }

    # Determine which media categories are present.
    has_video = bool(
        output_types & _VIDEO_OUTPUT_TYPES
        or node_class_types & _VIDEO_OUTPUT_TYPES
        or any("Video" in ct for ct in node_class_types)
    )
    has_audio = bool(
        output_types & _AUDIO_OUTPUT_TYPES
        or node_class_types & _AUDIO_OUTPUT_TYPES
    )
    has_image = bool(
        output_types & _IMAGE_OUTPUT_TYPES
        or node_class_types & _IMAGE_OUTPUT_TYPES
    )
    has_3d = bool(
        output_types & _3D_OUTPUT_TYPES
        or node_class_types & _3D_OUTPUT_TYPES
    )

    categories = sum([has_video, has_audio, has_image, has_3d])
    if categories > 1:
        return "multi"
    if has_video:
        return "video"
    if has_audio:
        return "audio"
    if has_3d:
        return "3d"
    # Default to image (most common ComfyUI output).
    return "image"


def detect_custom_nodes(workflow: "VibeWorkflow") -> list[str]:
    """Return a deduplicated, sorted list of non-core node class names.

    A node is considered "custom" if its ``class_type`` is not in the
    built-in core ComfyUI set and is not a known utility/flow-control node.
    """
    # Known flow-control / utility class names that are neither core nor
    # interesting "custom" nodes.
    _UTILITY_CLASS_NAMES: frozenset[str] = frozenset({
        "Note", "MarkdownNote", "Reroute", "PrimitiveNode",
        "GetNode", "SetNode", "INTConstant", "FLOATConstant",
        "STRINGConstant", "BOOLConstant",
        "Fast Groups Bypasser (rgthree)", "Fast Groups Muter (rgthree)",
        "Mute / Bypass Repeater (rgthree)",
    })

    custom: set[str] = set()
    for node in workflow.nodes.values():
        ct = node.class_type
        if ct in _CORE_CLASS_NAMES:
            continue
        if ct in _UTILITY_CLASS_NAMES:
            continue
        # Skip empty/unknown
        if not ct or ct == "Unknown":
            continue
        custom.add(ct)

    return sorted(custom)


def compute_complexity_score(workflow: "VibeWorkflow") -> int:
    """Compute a complexity score (1-5) from structural metrics.

    Factors:
    - Node count (weighted)
    - Edge count (weighted)
    - Presence of custom nodes
    - Graph depth / branching

    Returns an integer in [1, 5].
    """
    node_count = len(workflow.nodes)
    edge_count = len(workflow.edges)
    custom_count = len(detect_custom_nodes(workflow))

    # Base score from node count.
    if node_count <= 5:
        score = 1
    elif node_count <= 15:
        score = 2
    elif node_count <= 40:
        score = 3
    elif node_count <= 80:
        score = 4
    else:
        score = 5

    # Edge density bonus: high edge-to-node ratio suggests complex wiring.
    if node_count > 0:
        edge_ratio = edge_count / node_count
        if edge_ratio > 2.0:
            score = min(5, score + 1)
        elif edge_ratio > 1.5:
            score = min(5, score + 1)

    # Custom node bonus.
    if custom_count > 10:
        score = min(5, score + 1)
    elif custom_count > 5:
        score = min(5, score + 1)

    return score


def derive_flags(workflow: "VibeWorkflow") -> dict[str, bool]:
    """Derive boolean flags from workflow structure.

    Returns a dict with keys like ``requires_custom_nodes``,
    ``is_animated``, ``has_controlnet``, ``has_ipadapter``, etc.
    """
    class_names: set[str] = {
        node.class_type for node in workflow.nodes.values()
    }
    combined = " ".join(class_names)

    flags: dict[str, bool] = {
        "requires_custom_nodes": len(detect_custom_nodes(workflow)) > 0,
        "is_animated": any(
            kw in combined
            for kw in ("Animate", "animate", "Video", "video",
                        "VHS_VideoCombine", "SaveAnimated")
        ),
        "has_controlnet": any(
            kw in combined for kw in ("ControlNet", "controlnet", "Control")
        ),
        "has_ipadapter": any(
            kw in combined for kw in ("IPAdapter", "ipadapter", "IP-Adapter")
        ),
        "has_lora": any(
            kw in combined for kw in ("Lora", "lora", "LoRA")
        ),
        "has_video_output": any(
            ct in _VIDEO_OUTPUT_TYPES or "Video" in ct
            for ct in class_names
        ),
    }

    return flags
