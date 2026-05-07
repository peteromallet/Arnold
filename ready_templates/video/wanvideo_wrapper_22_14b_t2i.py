# vibecomfy: manual
"""Wan 2.2 14B single-frame T2I template for Reigh parity."""
from __future__ import annotations

from vibecomfy.registry.ready_template import apply_ready_template_policy
from vibecomfy.workflow import VibeWorkflow, WorkflowSource


DEFAULT_PROMPT = "A compact cinematic still of a red cube on a clean white tabletop."
DEFAULT_NEGATIVE = "fading, breaking, shot cuts, jumpcuts, blurry, noise, distorted"

READY_METADATA = {
    "model_assets": [
        {
            "name": "Wan2_2-T2V-A14B-HIGH_fp8_e4m3fn_scaled_KJ.safetensors",
            "url": "https://huggingface.co/Kijai/WanVideo_comfy/resolve/main/WanVideo/2_2/Wan2_2-T2V-A14B-HIGH_fp8_e4m3fn_scaled_KJ.safetensors",
            "directory": "diffusion_models/WanVideo/2_2",
        },
        {
            "name": "Wan2_2-T2V-A14B-LOW_fp8_e4m3fn_scaled_KJ.safetensors",
            "url": "https://huggingface.co/Kijai/WanVideo_comfy/resolve/main/WanVideo/2_2/Wan2_2-T2V-A14B-LOW_fp8_e4m3fn_scaled_KJ.safetensors",
            "directory": "diffusion_models/WanVideo/2_2",
        },
        {
            "name": "lightx2v_T2V_14B_cfg_step_distill_v2_lora_rank64_bf16.safetensors",
            "url": "https://huggingface.co/Kijai/WanVideo_comfy/resolve/main/WanVideo/Lightx2v/lightx2v_T2V_14B_cfg_step_distill_v2_lora_rank64_bf16.safetensors",
            "directory": "loras/WanVideo/Lightx2v",
        },
        {
            "name": "Wan2_1_VAE_bf16.safetensors",
            "url": "https://huggingface.co/Kijai/WanVideo_comfy/resolve/main/WanVideo/Wan2_1_VAE_bf16.safetensors",
            "directory": "vae/wanvideo",
        },
        {
            "name": "umt5-xxl-enc-bf16.safetensors",
            "url": "https://huggingface.co/Kijai/WanVideo_comfy/resolve/main/WanVideo/umt5-xxl-enc-bf16.safetensors",
            "directory": "text_encoders",
        },
    ],
    "ready_template": "video/wanvideo_wrapper_22_14b_t2i",
    "workflow_template": "wanvideo_wrapper_22_14b_t2i",
    "capability": "text_to_image_single_frame",
    "source_role": "reigh_parity_manual_template",
    "source_workflow": "ComfyUI-WanVideoWrapper/example_workflows/wanvideo_2_2_14B_Pusa_extension_example_01.json",
    "coverage_tier": "production_parity_candidate",
    "approach": "Wan 2.2 14B high/low two-phase text-to-video graph decoded as one image frame",
    "runtime_note": "Intended to match Reigh wan_2_2_t2i, which forces video_length=1 and returns PNG.",
    "smoke_resolution": "832x480x1_frame",
}

READY_REQUIREMENTS = {
    "models": READY_METADATA["model_assets"],
    "custom_nodes": ["ComfyUI-KJNodes", "ComfyUI-WanVideoWrapper"],
}


def build() -> VibeWorkflow:
    wf = VibeWorkflow(
        READY_METADATA["ready_template"],
        WorkflowSource(id=READY_METADATA["ready_template"], path=__file__, source_type="ready_template"),
    )

    vae = _node(wf, "WanVideoVAELoader", "38", widget_0="wanvideo\\Wan2_1_VAE_bf16.safetensors", widget_1="bf16")
    block_swap = _node(wf, "WanVideoBlockSwap", "39", widget_0=30, widget_1=False, widget_2=False, widget_3=False, widget_4=0, widget_5=0, widget_6=False)
    high_lora = _node(wf, "WanVideoLoraSelectMulti", "98", widget_0="WanVideo\\Lightx2v\\lightx2v_T2V_14B_cfg_step_distill_v2_lora_rank64_bf16.safetensors", widget_1=1.0, widget_2="none", widget_3=1, widget_4="none", widget_5=1, widget_6="none", widget_7=1, widget_8="none", widget_9=1, widget_10=False, widget_11=False)
    low_lora = _node(wf, "WanVideoLoraSelectMulti", "93", widget_0="WanVideo\\Lightx2v\\lightx2v_T2V_14B_cfg_step_distill_v2_lora_rank64_bf16.safetensors", widget_1=1.0, widget_2="none", widget_3=1, widget_4="none", widget_5=1, widget_6="none", widget_7=1, widget_8="none", widget_9=1, widget_10=False, widget_11=False)
    high_model_raw = _node(wf, "WanVideoModelLoader", "22", widget_0="WanVideo\\2_2\\Wan2_2-T2V-A14B-HIGH_fp8_e4m3fn_scaled_KJ.safetensors", widget_1="fp16", widget_2="fp8_e4m3fn_scaled", widget_3="offload_device", widget_4="sdpa")
    low_model_raw = _node(wf, "WanVideoModelLoader", "92", widget_0="WanVideo\\2_2\\Wan2_2-T2V-A14B-LOW_fp8_e4m3fn_scaled_KJ.safetensors", widget_1="fp16", widget_2="fp8_e4m3fn_scaled", widget_3="offload_device", widget_4="sdpa")
    high_model_lora = _node(wf, "WanVideoSetLoRAs", "79", model=high_model_raw.out(0), lora=high_lora.out(0))
    low_model_lora = _node(wf, "WanVideoSetLoRAs", "80", model=low_model_raw.out(0), lora=low_lora.out(0))
    high_model = _node(wf, "WanVideoSetBlockSwap", "86", model=high_model_lora.out(0), block_swap_args=block_swap.out(0))
    low_model = _node(wf, "WanVideoSetBlockSwap", "91", model=low_model_lora.out(0), block_swap_args=block_swap.out(0))
    embeds = _node(wf, "WanVideoEmptyEmbeds", "78", widget_0=832, widget_1=480, widget_2=1, width=832, height=480, num_frames=1)
    text = _node(wf, "WanVideoTextEncodeCached", "16", widget_0="umt5-xxl-enc-bf16.safetensors", widget_1="bf16", widget_2=DEFAULT_PROMPT, widget_3=DEFAULT_NEGATIVE, widget_4="disabled", widget_5=True, widget_6="gpu")
    high_samples = _node(wf, "WanVideoSampler", "27", steps=6, widget_0=6, widget_1=3.0, widget_2=5, widget_3=12345, widget_4="fixed", widget_5=True, widget_6="euler", widget_7=0, widget_8=1, widget_9="", widget_10="comfy", widget_11=0, widget_12=2, widget_13=False, model=high_model.out(0), image_embeds=embeds.out(0), text_embeds=text.out(0), end_step=2)
    low_samples = _node(wf, "WanVideoSampler", "87", steps=6, widget_0=6, widget_1=1.0, widget_2=5, widget_3=12345, widget_4="fixed", widget_5=True, widget_6="euler", widget_7=0, widget_8=1, widget_9="", widget_10="comfy", widget_11=2, widget_12=-1, widget_13=False, model=low_model.out(0), image_embeds=embeds.out(0), text_embeds=text.out(0), samples=high_samples.out(0), start_step=2)
    decoded = _node(wf, "WanVideoDecode", "28", widget_0=False, widget_1=272, widget_2=272, widget_3=144, widget_4=128, widget_5="default", samples=low_samples.out(0), vae=vae.out(0))
    _node(wf, "SaveImage", "60", filename_prefix="Wan-2-2-T2I", images=decoded.out(0))

    wf.finalize_metadata()
    apply_ready_template_policy(wf, READY_METADATA, source_path=__file__, requirements=READY_REQUIREMENTS)
    return wf


def _node(wf: VibeWorkflow, class_type: str, _id: str, _extras: dict | None = None, **kwargs):
    from vibecomfy.handles import Handle

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
