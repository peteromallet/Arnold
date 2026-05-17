# vibecomfy: manual
"""LTX 2.3 first/last two-stage low-VRAM parity candidate.

This keeps the Wan2GP-relevant two-stage shape while using the official
Lightricks low-VRAM loader family that fits 24GB GPUs.
"""
from __future__ import annotations

from vibecomfy.registry.ready_template import apply_ready_template_policy, bind_output
from vibecomfy.workflow import VibeWorkflow, WorkflowSource


LTX_FIRST_LAST_TWO_STAGE_ASSETS = [
    {
        "name": "ltx-2.3-22b-distilled-fp8.safetensors",
        "url": "https://huggingface.co/Lightricks/LTX-2.3-fp8/resolve/main/ltx-2.3-22b-distilled-fp8.safetensors",
        "subdir": "checkpoints",
    },
    {
        "name": "gemma_3_12B_it_fp4_mixed.safetensors",
        "url": "https://huggingface.co/Comfy-Org/ltx-2/resolve/main/split_files/text_encoders/gemma_3_12B_it_fp4_mixed.safetensors",
        "subdir": "text_encoders",
    },
    {
        "name": "ltx-2.3-spatial-upscaler-x2-1.1.safetensors",
        "url": "https://huggingface.co/Lightricks/LTX-2.3/resolve/main/ltx-2.3-spatial-upscaler-x2-1.1.safetensors",
        "subdir": "latent_upscale_models",
    },
]


READY_METADATA = {
    "model_assets": LTX_FIRST_LAST_TWO_STAGE_ASSETS,
    "unbound_inputs": {"seed": 3779},
    "ready_template": "video/ltx2_3_lightricks_first_last_two_stage_lowvram",
    "workflow_template": "ltx2_3_lightricks_first_last_two_stage_lowvram",
    "capability": "first_last_frame_video",
    "source_role": "manual_ready_python_template",
    "source_workflow": "manual composition of official Lightricks first/last and two-stage low-VRAM LTX 2.3 flows",
    "coverage_tier": "required",
    "approach": "two-stage first/last-frame route using LowVRAMCheckpointLoader",
    "runtime_note": (
        "Stage 1 uses Wan2GP's half-resolution long sigma schedule; the latent is "
        "spatially upsampled before stage 2 reapplies first/last guides and uses "
        "the Wan2GP refine sigma schedule."
    ),
    "discord_signal": "Use dedicated distilled fp8 + low-VRAM loaders on 24GB GPUs.",
    "smoke_resolution": "256x256x5_frames",
    "ltx_best_practices": [
        "Use LowVRAMCheckpointLoader for 4090 viability.",
        "Use the dedicated distilled fp8 checkpoint rather than the dev checkpoint plus LoRA when possible.",
        "Preserve Wan2GP's two-stage sigma structure for parity checks.",
    ],
    "runtime_packages": [
        {
            "name": "sageattention",
            "reason": "Required by LTX2MemoryEfficientSageAttentionPatch for the two-stage low-VRAM LTX route.",
            "source": "SageAttention-ada",
        }
    ],
    "comfy_configuration": {"memory_profile": 3, "fp8_e4m3fn_text_enc": True},
}

READY_REQUIREMENTS = {
    "models": LTX_FIRST_LAST_TWO_STAGE_ASSETS,
    "custom_nodes": ["ComfyUI-LTXVideo", "ComfyUI-KJNodes"],
}


VIDEO_OUTPUT_NODE = "4852"
VIDEO_OUTPUT_NAME = "video"
VIDEO_OUTPUT_PREFIX = "output"
VIDEO_OUTPUT_MIME = "video/mp4"


def build() -> VibeWorkflow:
    wf = VibeWorkflow(
        READY_METADATA["ready_template"],
        WorkflowSource(id=READY_METADATA["ready_template"], path=__file__, source_type="ready_template"),
    )

    first_image = _node(wf, "LoadImage", "31", _outputs=("image", "mask"), image="first.png")
    last_image = _node(wf, "LoadImage", "39", _outputs=("image", "mask"), image="last.png")
    seed_first = _node(wf, "RandomNoise", "100", _outputs=("noise",), noise_seed=315253765879496)
    seed_last = _node(wf, "RandomNoise", "101", _outputs=("noise",), noise_seed=315253765879496)
    frames = _node(wf, "PrimitiveInt", "102", _outputs=("value",), value=81)
    width = _node(wf, "PrimitiveInt", "113", _outputs=("value",), value=768)
    height = _node(wf, "PrimitiveInt", "98", _outputs=("value",), value=512)
    stage1_width = _node(wf, "PrimitiveInt", "1131", _outputs=("value",), value=384)
    stage1_height = _node(wf, "PrimitiveInt", "981", _outputs=("value",), value=256)
    fps_int = _node(wf, "PrimitiveInt", "114", _outputs=("value",), value=24)
    fps = _node(wf, "PrimitiveFloat", "123", _outputs=("value",), value=24)

    text_encoder = _node(
        wf,
        "LTXAVTextEncoderLoader",
        "103",
        _outputs=("clip",),
        ckpt_name="ltx-2.3-22b-distilled-fp8.safetensors",
        text_encoder="gemma_3_12B_it_fp4_mixed.safetensors",
        device="default",
    )
    audio_vae = _node(
        wf,
        "LTXVAudioVAELoader",
        "126",
        _outputs=("audio_vae",),
        ckpt_name="ltx-2.3-22b-distilled-fp8.safetensors",
    )
    checkpoint = _node(
        wf,
        "LowVRAMCheckpointLoader",
        "127",
        _outputs=("model", "clip", "vae"),
        ckpt_name="ltx-2.3-22b-distilled-fp8.safetensors",
    )
    patched_model = _node(
        wf,
        "LTX2MemoryEfficientSageAttentionPatch",
        "129",
        _outputs=("model",),
        model=checkpoint.out("model"),
        triton_kernels=True,
    )
    spatial_upscaler = _node(
        wf,
        "LatentUpscaleModelLoader",
        "182",
        _outputs=("latent_upscale_model",),
        model_name="ltx-2.3-spatial-upscaler-x2-1.1.safetensors",
    )

    resize_first = _node(
        wf,
        "ResizeImageMaskNode",
        "124",
        _outputs=("image",),
        _extras={
            "resize_type.width": width.out("value"),
            "resize_type.height": height.out("value"),
            "resize_type.crop": "center",
        },
        resize_type="scale dimensions",
        scale_method="nearest-exact",
        input=first_image.out("image"),
    )
    resize_last = _node(
        wf,
        "ResizeImageMaskNode",
        "125",
        _outputs=("image",),
        _extras={
            "resize_type.width": width.out("value"),
            "resize_type.height": height.out("value"),
            "resize_type.crop": "center",
        },
        resize_type="scale dimensions",
        scale_method="nearest-exact",
        input=last_image.out("image"),
    )
    resize_first_stage1 = _node(
        wf,
        "ResizeImageMaskNode",
        "1241",
        _outputs=("image",),
        _extras={
            "resize_type.width": stage1_width.out("value"),
            "resize_type.height": stage1_height.out("value"),
            "resize_type.crop": "center",
        },
        resize_type="scale dimensions",
        scale_method="nearest-exact",
        input=first_image.out("image"),
    )
    resize_last_stage1 = _node(
        wf,
        "ResizeImageMaskNode",
        "1251",
        _outputs=("image",),
        _extras={
            "resize_type.width": stage1_width.out("value"),
            "resize_type.height": stage1_height.out("value"),
            "resize_type.crop": "center",
        },
        resize_type="scale dimensions",
        scale_method="nearest-exact",
        input=last_image.out("image"),
    )
    preprocess_first = _node(
        wf,
        "LTXVPreprocess",
        "104",
        _outputs=("image",),
        img_compression=25,
        image=resize_first.out("image"),
    )
    preprocess_last = _node(
        wf,
        "LTXVPreprocess",
        "99",
        _outputs=("image",),
        img_compression=25,
        image=resize_last.out("image"),
    )
    preprocess_first_stage1 = _node(
        wf,
        "LTXVPreprocess",
        "1041",
        _outputs=("image",),
        img_compression=25,
        image=resize_first_stage1.out("image"),
    )
    preprocess_last_stage1 = _node(
        wf,
        "LTXVPreprocess",
        "991",
        _outputs=("image",),
        img_compression=25,
        image=resize_last_stage1.out("image"),
    )

    prompt = _node(
        wf,
        "CLIPTextEncode",
        "128",
        _outputs=("conditioning",),
        text="A smooth cinematic move between two anchor frames.",
        clip=text_encoder.out("clip"),
    )
    negative = _node(
        wf,
        "CLIPTextEncode",
        "112",
        _outputs=("conditioning",),
        text="blurry, oversaturated, pixelated, low resolution, grainy, distorted",
        clip=text_encoder.out("clip"),
    )
    conditioning = _node(
        wf,
        "LTXVConditioning",
        "109",
        _outputs=("positive", "negative"),
        frame_rate=fps.out("value"),
        negative=negative.out("conditioning"),
        positive=prompt.out("conditioning"),
    )

    stage1_image_size = _node(
        wf,
        "GetImageSize",
        "110",
        _outputs=("width", "height", "batch_size"),
        image=resize_first_stage1.out("image"),
    )
    empty_audio = _node(
        wf,
        "LTXVEmptyLatentAudio",
        "1010",
        _outputs=("audio_latent",),
        batch_size=1,
        frame_rate=fps_int.out("value"),
        frames_number=frames.out("value"),
        audio_vae=audio_vae.out("audio_vae"),
    )
    empty_video = _node(
        wf,
        "EmptyLTXVLatentVideo",
        "108",
        _outputs=("latent",),
        batch_size=1,
        width=stage1_image_size.out("width"),
        height=stage1_image_size.out("height"),
        length=frames.out("value"),
    )

    first_guide = _add_guide(wf, "115", preprocess_first_stage1, empty_video.out("latent"), conditioning, checkpoint, frame_idx=0)
    last_guide = _add_guide(wf, "111", preprocess_last_stage1, first_guide.out("latent"), first_guide, checkpoint, frame_idx=-1)
    stage1_concat = _node(
        wf,
        "LTXVConcatAVLatent",
        "119",
        _outputs=("latent",),
        audio_latent=empty_audio.out("audio_latent"),
        video_latent=last_guide.out("latent"),
    )
    stage1 = _sample(
        wf,
        "120",
        patched_model.out("model"),
        last_guide,
        stage1_concat.out("latent"),
        seed_first.out("noise"),
        sampler_name="euler_ancestral_cfg_pp",
        sigmas="1.0, 0.99375, 0.9875, 0.98125, 0.975, 0.909375, 0.725, 0.421875, 0.0",
    )
    separated_stage1 = _node(
        wf,
        "LTXVSeparateAVLatent",
        "121",
        _outputs=("video_latent", "audio_latent"),
        av_latent=stage1.out("denoised_output"),
    )
    upscaled_stage1 = _node(
        wf,
        "LTXVLatentUpsampler",
        "1845",
        _outputs=("latent",),
        samples=separated_stage1.out("video_latent"),
        upscale_model=spatial_upscaler.out("latent_upscale_model"),
        vae=checkpoint.out("vae"),
    )
    stage_boundary = _node(
        wf,
        "VRAM_Debug",
        "1846",
        _outputs=("any_output", "image_pass", "model_pass", "freemem_before", "freemem_after"),
        any_input=upscaled_stage1.out("latent"),
        empty_cache=True,
        gc_collect=True,
        unload_all_models=True,
    )
    cropped_stage1 = _node(
        wf,
        "LTXVCropGuides",
        "106",
        _outputs=("positive", "negative", "latent"),
        latent=stage_boundary.out("any_output"),
        negative=last_guide.out("negative"),
        positive=last_guide.out("positive"),
    )

    first_refine_guide = _add_guide(wf, "2150", preprocess_first, cropped_stage1.out("latent"), cropped_stage1, checkpoint, frame_idx=0)
    last_refine_guide = _add_guide(wf, "2152", preprocess_last, first_refine_guide.out("latent"), first_refine_guide, checkpoint, frame_idx=-1)
    stage2_concat = _node(
        wf,
        "LTXVConcatAVLatent",
        "4969",
        _outputs=("latent",),
        audio_latent=separated_stage1.out("audio_latent"),
        video_latent=last_refine_guide.out("latent"),
    )
    stage2 = _sample(
        wf,
        "4971",
        patched_model.out("model"),
        last_refine_guide,
        stage2_concat.out("latent"),
        seed_last.out("noise"),
        sampler_name="euler_cfg_pp",
        sigmas="0.909375, 0.725, 0.421875, 0.0",
    )
    separated_stage2 = _node(
        wf,
        "LTXVSeparateAVLatent",
        "4973",
        _outputs=("video_latent", "audio_latent"),
        av_latent=stage2.out("denoised_output"),
    )
    cropped_stage2 = _node(
        wf,
        "LTXVCropGuides",
        "4974",
        _outputs=("positive", "negative", "latent"),
        latent=separated_stage2.out("video_latent"),
        negative=last_refine_guide.out("negative"),
        positive=last_refine_guide.out("positive"),
    )
    decoded_audio = _node(
        wf,
        "LTXVAudioVAEDecode",
        "4848",
        _outputs=("audio",),
        audio_vae=audio_vae.out("audio_vae"),
        samples=separated_stage2.out("audio_latent"),
    )
    decoded_video = _node(
        wf,
        "LTXVTiledVAEDecode",
        "4995",
        _outputs=("images",),
        horizontal_tiles=2,
        vertical_tiles=2,
        overlap=6,
        last_frame_fix=False,
        working_device="auto",
        working_dtype="auto",
        latents=cropped_stage2.out("latent"),
        vae=checkpoint.out("vae"),
    )
    video = _node(
        wf,
        "CreateVideo",
        "4849",
        _outputs=("video",),
        fps=fps.out("value"),
        audio=decoded_audio.out("audio"),
        images=decoded_video.out("images"),
    )
    _node(wf, "SaveVideo", VIDEO_OUTPUT_NODE, filename_prefix=VIDEO_OUTPUT_PREFIX, format="auto", codec="auto", video=video.out("video"))

    wf.finalize_metadata()
    apply_ready_template_policy(wf, READY_METADATA, source_path=__file__, requirements=READY_REQUIREMENTS)
    wf.register_input("prompt", "128", "text", value=prompt.node.inputs.get("text"))
    wf.register_input("negative_prompt", "112", "text", value=negative.node.inputs.get("text"))
    wf.register_input("negative", "112", "text", value=negative.node.inputs.get("text"))
    wf.register_input("seed", "100", "noise_seed", value=315253765879496)
    wf.register_input("seed_first", "100", "noise_seed", value=315253765879496)
    wf.register_input("seed_last", "101", "noise_seed", value=315253765879496)
    wf.register_input("width", "113", "value", value=768)
    wf.register_input("height", "98", "value", value=512)
    wf.register_input("stage1_width", "1131", "value", value=384)
    wf.register_input("stage1_height", "981", "value", value=256)
    wf.register_input("frames", "102", "value", value=81)
    wf.register_input("fps", "123", "value", value=24)
    wf.register_input("fps_int", "114", "value", value=24)
    wf.register_input("first_strength", "115", "strength", value=1.0)
    wf.register_input("last_strength", "111", "strength", value=1.0)
    wf.register_input("first_frame_strength", "2150", "strength", value=1.0)
    wf.register_input("last_frame_strength", "2152", "strength", value=1.0)
    wf.register_input("first_image", "31", "image", value="first.png")
    wf.register_input("last_image", "39", "image", value="last.png")
    wf.register_input("start_image", "31", "image", value="first.png")
    wf.register_input("end_image", "39", "image", value="last.png")
    wf.register_input("model", "127", "ckpt_name", value="ltx-2.3-22b-distilled-fp8.safetensors")
    bind_output(
        wf,
        "4852",
        output_type="SaveVideo",
        name="video",
        artifact_kind="video",
        mime_type="video/mp4",
        filename_prefix="output",
        expected_cardinality="one",
    )
    return wf


def _add_guide(wf, node_id, image_node, latent, conditioning_node, checkpoint, *, frame_idx: int):
    return _node(
        wf,
        "LTXVAddGuide",
        node_id,
        _outputs=("positive", "negative", "latent"),
        frame_idx=frame_idx,
        strength=1.0,
        image=image_node.out("image"),
        latent=latent,
        negative=conditioning_node.out("negative"),
        positive=conditioning_node.out("positive"),
        vae=checkpoint.out("vae"),
    )


def _sample(wf, node_id, model, guides, latent, noise, *, sampler_name: str, sigmas: str):
    guider = _node(
        wf,
        "CFGGuider",
        f"{node_id}_guider",
        _outputs=("guider",),
        cfg=1,
        model=model,
        negative=guides.out("negative"),
        positive=guides.out("positive"),
    )
    sampler = _node(wf, "KSamplerSelect", f"{node_id}_sampler", _outputs=("sampler",), sampler_name=sampler_name)
    sigmas_node = _node(wf, "ManualSigmas", f"{node_id}_sigmas", _outputs=("sigmas",), sigmas=sigmas)
    return _node(
        wf,
        "SamplerCustomAdvanced",
        node_id,
        _outputs=("output", "denoised_output"),
        guider=guider.out("guider"),
        latent_image=latent,
        noise=noise,
        sampler=sampler.out("sampler"),
        sigmas=sigmas_node.out("sigmas"),
    )


def _node(
    wf: VibeWorkflow,
    class_type: str,
    _id: str,
    _extras: dict | None = None,
    _outputs: tuple[str, ...] | None = None,
    **kwargs,
):
    from vibecomfy.handles import Handle

    builder = wf.node(class_type, **kwargs)
    if _outputs is not None:
        builder.node.metadata["output_names"] = list(_outputs)
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
