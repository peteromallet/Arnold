# vibecomfy: manual
"""LTX 2.3 first/last-frame travel with a raw full-length video guide."""
from __future__ import annotations

from vibecomfy.handles import Handle
from vibecomfy.registry.ready import workflow_from_ready
from vibecomfy.registry.ready_template import apply_ready_template_policy
from vibecomfy.workflow import VibeWorkflow, WorkflowSource


LTX_RUNEXX_MODEL_ASSETS = [
    {
        "name": "ltx-2.3_text_projection_bf16.safetensors",
        "url": "https://huggingface.co/Kijai/LTX2.3_comfy/resolve/main/text_encoders/ltx-2.3_text_projection_bf16.safetensors",
        "subdir": "text_encoders",
    },
    {
        "name": "LTX23_video_vae_bf16.safetensors",
        "url": "https://huggingface.co/Kijai/LTX2.3_comfy/resolve/main/vae/LTX23_video_vae_bf16.safetensors",
        "subdir": "vae",
    },
    {
        "name": "LTX23_audio_vae_bf16.safetensors",
        "url": "https://huggingface.co/Kijai/LTX2.3_comfy/resolve/main/vae/LTX23_audio_vae_bf16.safetensors",
        "subdir": "checkpoints",
    },
    {
        "name": "taeltx2_3.safetensors",
        "url": "https://huggingface.co/Kijai/LTX2.3_comfy/resolve/main/vae/taeltx2_3.safetensors",
        "subdir": "vae",
    },
    {
        "name": "ltx-2.3-22b-distilled-1.1_transformer_only_fp8_scaled.safetensors",
        "url": "https://huggingface.co/Kijai/LTX2.3_comfy/resolve/main/diffusion_models/ltx-2.3-22b-distilled-1.1_transformer_only_fp8_scaled.safetensors",
        "subdir": "diffusion_models",
    },
    {
        "name": "LTX/v2/ltx-2.3-22b-distilled-1.1_lora-dynamic_fro09_avg_rank_111_bf16.safetensors",
        "url": "https://huggingface.co/Kijai/LTX2.3_comfy/resolve/main/loras/ltx-2.3-22b-distilled-1.1_lora-dynamic_fro09_avg_rank_111_bf16.safetensors",
        "subdir": "loras",
    },
]


READY_METADATA = {
    "model_assets": LTX_RUNEXX_MODEL_ASSETS,
    "unbound_inputs": {
        "seed": "14.noise_seed",
        "start_image": "45.image",
        "end_image": "47.image",
        "control_video": "5001.video",
        "prompt": "2103.value",
        "negative": "11.text",
        "frames": "2078.widget_0",
        "width": "2080.widget_0",
        "height": "2079.widget_0",
        "fps": "2076.value",
        "strength": "6102.value",
        "first_frame_strength": "2110.value",
        "last_frame_strength": "2108.value",
    },
    "ready_template": "video/ltx2_3_runexx_first_last_raw_video_guide",
    "workflow_template": "ltx2_3_runexx_first_last_raw_video_guide",
    "capability": "first_last_frame_raw_video_guide",
    "source_role": "manual_ready_python_template",
    "source_workflow": "manual composition of Runexx first/last frame and raw LTXVAddGuide video guidance",
    "coverage_tier": "required",
    "approach": "first/last-frame image anchors plus full-length raw video frames into LTXVAddGuide",
    "runtime_note": "Uses non-IC LTXVAddGuide; raw mode intentionally avoids LTXICLoRALoaderModelOnly and LTXAddVideoICLoRAGuide.",
    "discord_signal": "Matches Wan2GP LTX VG-style full-video guide without IC-LoRA.",
    "smoke_resolution": "256x256x9_frames",
    "ltx_best_practices": [
        "Use first/last anchors for travel endpoints.",
        "Use raw full-length guide frames for VG-style guidance.",
        "Keep IC-LoRA union-control modes on the separate IC-LoRA control template.",
    ],
    "comfy_configuration": {"reserve_vram": 12, "cache_none": True, "fp8_e4m3fn_text_enc": True},
}

READY_REQUIREMENTS = {
    "models": LTX_RUNEXX_MODEL_ASSETS,
    "custom_nodes": [
        "ComfyUI-GGUF",
        "ComfyUI-KJNodes",
        "ComfyUI-LTXVideo",
        "ComfyUI-VideoHelperSuite",
        "rgthree-comfy",
    ],
}


def build() -> VibeWorkflow:
    wf = workflow_from_ready("video/ltx2_3_runexx_first_last_frame")
    wf.id = READY_METADATA["ready_template"]
    wf.source = WorkflowSource(
        id=READY_METADATA["ready_template"],
        path=__file__,
        source_type="ready_template",
    )
    _use_ltx_audio_vae_loader(wf)

    control_video = _node(
        wf,
        "LoadVideo",
        "5001",
        file="ltx_smoke_guide.mp4",
        video="ltx_smoke_guide.mp4",
        widget_0="ltx_smoke_guide.mp4",
        widget_1="image",
    )
    components = _node(wf, "GetVideoComponents", "5000", video=control_video.out(0))
    guide_resized = _node(
        wf,
        "ImageResizeKJv2",
        "6101",
        width=Handle("2080", "0"),
        height=Handle("2079", "0"),
        upscale_method="lanczos",
        keep_proportion="stretch",
        pad_color="0, 0, 0",
        crop_position="center",
        divisible_by=32,
        device="cpu",
        image=components.out(0),
    )
    wf.replace_edge("2152.image", guide_resized.out(0))
    wf.nodes["2152"].inputs["frame_idx"] = 0
    guide_strength = _node(wf, "PrimitiveFloat", "6102", value=1)
    wf.replace_edge("2152.strength", guide_strength.out(0))
    _apply_runtime_schema_defaults(wf)

    wf.finalize_metadata()
    wf.register_input("start_image", "45", "image", "example.png")
    wf.register_input("end_image", "47", "image", "egyptian_queen.png")
    wf.register_input("control_video", "5001", "video", "ltx_smoke_guide.mp4")
    wf.register_input("prompt", "2103", "value", wf.nodes["2103"].inputs.get("value", ""))
    wf.register_input("negative", "11", "text", wf.nodes["11"].inputs.get("text", ""))
    wf.register_input("seed", "14", "noise_seed", 43)
    wf.register_input("frames", "2078", "widget_0", 9)
    wf.register_input("width", "2080", "widget_0", 256)
    wf.register_input("height", "2079", "widget_0", 256)
    wf.register_input("fps", "2076", "value", 8)
    wf.register_input("strength", "6102", "value", 1)
    wf.register_input("first_frame_strength", "2110", "value", 0.8)
    wf.register_input("last_frame_strength", "2108", "value", 0.8)

    apply_ready_template_policy(wf, READY_METADATA, source_path=__file__, requirements=READY_REQUIREMENTS)
    return wf


def _use_ltx_audio_vae_loader(wf: VibeWorkflow) -> None:
    if "175" in wf.nodes:
        wf.nodes["175"].class_type = "LTXVAudioVAELoader"
        wf.nodes["175"].inputs = {"ckpt_name": "LTX23_audio_vae_bf16.safetensors"}


def _apply_runtime_schema_defaults(wf: VibeWorkflow) -> None:
    if "43" in wf.nodes:
        wf.nodes["43"].inputs.update(
            {
                "filename_prefix": "reigh_vibecomfy_ltx_raw_guide",
                "format": "video/h264-mp4",
                "loop_count": 0,
                "pingpong": False,
                "save_output": True,
            }
        )


def _node(wf: VibeWorkflow, class_type: str, _id: str, _extras: dict | None = None, **kwargs):
    builder = wf.node(class_type, **kwargs)
    if _extras:
        for key, value in _extras.items():
            if isinstance(value, Handle):
                wf.connect(value, f"{builder.node.id}.{key}")
            else:
                builder.node.inputs[key] = value
    if builder.node.id != _id:
        old_id = builder.node.id
        node = wf.nodes.pop(old_id)
        node.id = _id
        wf.nodes[_id] = node
        for edge in wf.edges:
            if edge.to_node == old_id:
                edge.to_node = _id
            if edge.from_node == old_id:
                edge.from_node = _id
    return builder
