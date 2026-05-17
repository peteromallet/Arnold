# vibecomfy: manual
"""Wan 2.2 14B VACE cocktail template for Reigh travel/join parity."""
from __future__ import annotations

from vibecomfy.registry.ready_template import apply_ready_template_policy
from vibecomfy.workflow import VibeWorkflow, WorkflowSource


DEFAULT_PROMPT = "A smooth cinematic transition with consistent identity, lighting, and camera motion."
DEFAULT_NEGATIVE = "fading, breaking, shot cuts, jumpcuts, blurry, noise, distorted"

READY_METADATA = {
    "model_assets": [
        {
            "name": "Wan2_2-T2V-A14B-HIGH_fp8_e4m3fn_scaled_KJ.safetensors",
            "url": "https://huggingface.co/Kijai/WanVideo_comfy_fp8_scaled/resolve/main/T2V/Wan2_2-T2V-A14B_HIGH_fp8_e4m3fn_scaled_KJ.safetensors",
            "directory": "diffusion_models/WanVideo/2_2",
        },
        {
            "name": "Wan2_2-T2V-A14B-LOW_fp8_e4m3fn_scaled_KJ.safetensors",
            "url": "https://huggingface.co/Kijai/WanVideo_comfy_fp8_scaled/resolve/main/T2V/Wan2_2-T2V-A14B-LOW_fp8_e4m3fn_scaled_KJ.safetensors",
            "directory": "diffusion_models/WanVideo/2_2",
        },
        {
            "name": "Wan2_1-VACE_module_14B_fp8_e4m3fn.safetensors",
            "url": "https://huggingface.co/Kijai/WanVideo_comfy/resolve/main/Wan2_1-VACE_module_14B_fp8_e4m3fn.safetensors",
            "directory": "diffusion_models/WanVideo",
        },
        {
            "name": "lightx2v_T2V_14B_cfg_step_distill_v2_lora_rank64_bf16.safetensors",
            "url": "https://huggingface.co/Kijai/WanVideo_comfy/resolve/main/Lightx2v/lightx2v_T2V_14B_cfg_step_distill_v2_lora_rank64_bf16.safetensors",
            "directory": "loras/WanVideo/Lightx2v",
        },
        {
            "name": "Wan2_1_VAE_bf16.safetensors",
            "url": "https://huggingface.co/Kijai/WanVideo_comfy/resolve/main/Wan2_1_VAE_bf16.safetensors",
            "directory": "vae/wanvideo",
        },
        {
            "name": "umt5-xxl-enc-bf16.safetensors",
            "url": "https://huggingface.co/Kijai/WanVideo_comfy/resolve/main/umt5-xxl-enc-bf16.safetensors",
            "directory": "text_encoders",
        },
    ],
    "ready_template": "video/wanvideo_wrapper_22_14b_vace_cocktail",
    "workflow_template": "wanvideo_wrapper_22_14b_vace_cocktail",
    "capability": "video_vace_travel_join",
    "source_role": "reigh_parity_manual_template",
    "source_workflow": "ComfyUI-WanVideoWrapper VACE + Wan2GP/defaults/wan_2_2_vace_lightning_baseline_2_2_2.json",
    "coverage_tier": "production_parity_candidate",
    "approach": "Wan 2.2 14B VACE high/high/low cocktail with first/last frame and optional control-video conditioning",
    "runtime_note": "Matches Reigh Wan2GP VACE baseline shape: 81 frames, 6 Euler steps, CFG 3/1/1, flow shift 5.",
    "smoke_resolution": "832x480x81_frames",
}

READY_REQUIREMENTS = {
    "models": READY_METADATA["model_assets"],
    "custom_nodes": ["ComfyUI-KJNodes", "ComfyUI-VideoHelperSuite", "ComfyUI-WanVideoWrapper"],
}


def build() -> VibeWorkflow:
    wf = VibeWorkflow(
        READY_METADATA["ready_template"],
        WorkflowSource(id=READY_METADATA["ready_template"], path=__file__, source_type="ready_template"),
    )

    start_image = _node(wf, "LoadImage", "64", image="vace_start.png")
    end_image = _node(wf, "LoadImage", "112", image="vace_end.png")
    control_video = _node(
        wf,
        "VHS_LoadVideo",
        "199",
        _extras={
            "video": "vace_control.mp4",
            "force_rate": 16,
            "custom_width": 832,
            "custom_height": 480,
            "frame_load_cap": 81,
            "skip_first_frames": 0,
            "select_every_nth": 1,
            "format": "AnimateDiff",
            "choose video to upload": "image",
        },
    )

    vae = _node(wf, "WanVideoVAELoader", "38", model_name="wanvideo/Wan2_1_VAE_bf16.safetensors", precision="bf16")
    vace_model = _node(wf, "WanVideoVACEModelSelect", "224", vace_model="WanVideo/Wan2_1-VACE_module_14B_fp8_e4m3fn.safetensors")
    block_swap = _node(wf, "WanVideoBlockSwap", "39", blocks_to_swap=30, offload_img_emb=True, offload_txt_emb=True, use_non_blocking=True, vace_blocks_to_swap=8, prefetch_blocks=0)
    high_lora = _node(wf, "WanVideoLoraSelectMulti", "98", lora_0="WanVideo/Lightx2v/lightx2v_T2V_14B_cfg_step_distill_v2_lora_rank64_bf16.safetensors", strength_0=1.0, lora_1="none", strength_1=1, lora_2="none", strength_2=1, lora_3="none", strength_3=1, lora_4="none", strength_4=1, low_mem_load=False, merge_loras=False)
    low_lora = _node(wf, "WanVideoLoraSelectMulti", "93", lora_0="WanVideo/Lightx2v/lightx2v_T2V_14B_cfg_step_distill_v2_lora_rank64_bf16.safetensors", strength_0=1.0, lora_1="none", strength_1=1, lora_2="none", strength_2=1, lora_3="none", strength_3=1, lora_4="none", strength_4=1, low_mem_load=False, merge_loras=False)
    high_model_raw = _node(wf, "WanVideoModelLoader", "22", model="WanVideo/2_2/Wan2_2-T2V-A14B-HIGH_fp8_e4m3fn_scaled_KJ.safetensors", base_precision="fp16", quantization="fp8_e4m3fn_scaled", load_device="offload_device", attention_mode="sdpa", extra_model=vace_model.out(0))
    low_model_raw = _node(wf, "WanVideoModelLoader", "92", model="WanVideo/2_2/Wan2_2-T2V-A14B-LOW_fp8_e4m3fn_scaled_KJ.safetensors", base_precision="fp16", quantization="fp8_e4m3fn_scaled", load_device="offload_device", attention_mode="sdpa", extra_model=vace_model.out(0))
    high_model_lora = _node(wf, "WanVideoSetLoRAs", "79", model=high_model_raw.out(0), lora=high_lora.out(0))
    low_model_lora = _node(wf, "WanVideoSetLoRAs", "80", model=low_model_raw.out(0), lora=low_lora.out(0))
    high_model = _node(wf, "WanVideoSetBlockSwap", "86", model=high_model_lora.out(0), block_swap_args=block_swap.out(0))
    low_model = _node(wf, "WanVideoSetBlockSwap", "91", model=low_model_lora.out(0), block_swap_args=block_swap.out(0))

    first_last = _node(
        wf,
        "WanVideoVACEStartToEndFrame",
        "111",
        num_frames=81,
        empty_frame_level=0.5,
        start_image=start_image.out(0),
        end_image=end_image.out(0),
        control_images=control_video.out(0),
    )
    vace_embeds = _node(
        wf,
        "WanVideoVACEEncode",
        "56",
        vae=vae.out(0),
        input_frames=first_last.out(0),
        input_masks=first_last.out(1),
        ref_images=start_image.out(0),
        width=832,
        height=480,
        num_frames=81,
        strength=1.0,
        vace_start_percent=0.0,
        vace_end_percent=1.0,
    )
    text = _node(wf, "WanVideoTextEncodeCached", "16", model_name="umt5-xxl-enc-bf16.safetensors", precision="bf16", positive_prompt=DEFAULT_PROMPT, negative_prompt=DEFAULT_NEGATIVE, quantization="disabled", use_disk_cache=True, device="gpu")
    phase_1 = _node(wf, "WanVideoSampler", "27", steps=6, cfg=3.0, shift=5, seed=12345, force_offload=True, scheduler="euler", riflex_freq_index=0, rope_function="comfy", start_step=0, end_step=2, add_noise_to_samples=False, model=high_model.out(0), image_embeds=vace_embeds.out(0), text_embeds=text.out(0))
    phase_2 = _node(wf, "WanVideoSampler", "87", steps=6, cfg=1.0, shift=5, seed=12345, force_offload=True, scheduler="euler", riflex_freq_index=0, rope_function="comfy", start_step=2, end_step=4, add_noise_to_samples=False, model=high_model.out(0), image_embeds=vace_embeds.out(0), text_embeds=text.out(0), samples=phase_1.out(0))
    phase_3 = _node(wf, "WanVideoSampler", "197", steps=6, cfg=1.0, shift=5, seed=12345, force_offload=True, scheduler="euler", riflex_freq_index=0, rope_function="comfy", start_step=4, end_step=-1, add_noise_to_samples=False, model=low_model.out(0), image_embeds=vace_embeds.out(0), text_embeds=text.out(0), samples=phase_2.out(0))
    decoded = _node(wf, "WanVideoDecode", "28", enable_vae_tiling=False, tile_x=272, tile_y=272, tile_stride_x=144, tile_stride_y=128, normalization="default", samples=phase_3.out(0), vae=vae.out(0))
    _node(
        wf,
        "VHS_VideoCombine",
        "139",
        _extras={
            "frame_rate": 16,
            "loop_count": 0,
            "filename_prefix": "Wan-2-2-VACE",
            "format": "video/h264-mp4",
            "pix_fmt": "yuv420p",
            "crf": 19,
            "save_metadata": True,
            "trim_to_audio": False,
            "pingpong": False,
            "save_output": True,
        },
        images=decoded.out(0),
    )

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
