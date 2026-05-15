# vibecomfy: manual
"""Lightricks LTX 2.3 distilled first/last parity template.

Pure-Python ready template based on the official ComfyUI LTX 2.3 FLF2V
workflow.  This route uses the dedicated distilled fp8 checkpoint rather than
the heavier dev checkpoint plus distilled LoRA spine.
"""
from __future__ import annotations

from vibecomfy.workflow import VibeWorkflow, WorkflowSource
from vibecomfy.registry.ready_template import apply_ready_template_policy


LTX_FIRST_LAST_MODEL_ASSETS = [
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
]


READY_METADATA = {
    "model_assets": LTX_FIRST_LAST_MODEL_ASSETS,
    "unbound_inputs": {"seed": 3779},
    "ready_template": "video/ltx2_3_lightricks_first_last_parity",
    "workflow_template": "ltx2_3_lightricks_first_last_parity",
    "capability": "first_last_frame_video",
    "source_role": "manual_ready_python_template",
    "source_workflow": "vendor/ComfyUI/tests/unit/playwright_cache/*/video_ltx2_3_flf2v.json",
    "coverage_tier": "required",
    "approach": "Official Lightricks distilled fp8 first/last frame route",
    "runtime_note": (
        "Patches named inputs for prompt, negative, seed, dimensions, frames, fps, "
        "first/last guide strengths, and first/last images."
    ),
    "discord_signal": (
        "Banodoco LTX notes point to the dedicated distilled fp8/quantized route for "
        "4090 viability; dev+LoRA two-stage routes can OOM at 24GB."
    ),
    "smoke_resolution": "256x256x5_frames",
    "ltx_best_practices": [
        "Use the dedicated distilled fp8 checkpoint for first/last workflows on 24GB GPUs.",
        "Keep guide strengths in Wan2GP's 0..1 range.",
        "Use tiled VAE decode for full-size app outputs.",
        "Do not force the LTX2 memory-efficient Sage/Triton patch in the portable 4090 profile; LTX 2.3 guide masks must remain on the stable SDPA-compatible path unless a separate optimized profile proves the patch end-to-end.",
    ],
    "comfy_configuration": {"memory_profile": 1, "fp8_e4m3fn_text_enc": True},
}

READY_REQUIREMENTS = {
    "models": [],
    "custom_nodes": ["ComfyUI-LTXVideo"],
}


def build() -> VibeWorkflow:
    """Build the official distilled fp8 first/last workflow."""
    wf = VibeWorkflow(
        READY_METADATA["ready_template"],
        WorkflowSource(
            id=READY_METADATA["ready_template"],
            path=__file__,
            source_type="ready_template",
        ),
    )

    loadimage_first = _node(wf, "LoadImage", "31", _outputs=("image", "mask"), image="first.png")
    loadimage_last = _node(wf, "LoadImage", "39", _outputs=("image", "mask"), image="last.png")

    randomnoise = _node(wf, "RandomNoise", "100", _outputs=("noise",), noise_seed=315253765879496)
    frames = _node(wf, "PrimitiveInt", "102", _outputs=("value",), value=121)
    width = _node(wf, "PrimitiveInt", "113", _outputs=("value",), value=1280)
    height = _node(wf, "PrimitiveInt", "98", _outputs=("value",), value=720)
    fps_int = _node(wf, "PrimitiveInt", "114", _outputs=("value",), value=24)
    fps = _node(wf, "PrimitiveFloat", "123", _outputs=("value",), value=24)

    text_encoder = _node(
        wf,
        "LTXAVTextEncoderLoader",
        "103",
        ckpt_name="ltx-2.3-22b-distilled-fp8.safetensors",
        text_encoder="gemma_3_12B_it_fp4_mixed.safetensors",
        device="default",
        _outputs=("clip",),
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
        "CheckpointLoaderSimple",
        "127",
        _outputs=("model", "clip", "vae"),
        ckpt_name="ltx-2.3-22b-distilled-fp8.safetensors",
    )

    resize_first = _node(
        wf,
        "ResizeImageMaskNode",
        "124",
        _extras={
            "resize_type.width": width.out("value"),
            "resize_type.height": height.out("value"),
            "resize_type.crop": "center",
        },
        _outputs=("image",),
        resize_type="scale dimensions",
        scale_method="nearest-exact",
        input=loadimage_first.out("image"),
    )
    resize_last = _node(
        wf,
        "ResizeImageMaskNode",
        "125",
        _extras={
            "resize_type.width": width.out("value"),
            "resize_type.height": height.out("value"),
            "resize_type.crop": "center",
        },
        _outputs=("image",),
        resize_type="scale dimensions",
        scale_method="nearest-exact",
        input=loadimage_last.out("image"),
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

    prompt = _node(
        wf,
        "CLIPTextEncode",
        "128",
        _outputs=("conditioning",),
        text="The camera moves from a high position to a low position, keeping the subject centered.",
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

    image_size = _node(wf, "GetImageSize", "110", _outputs=("width", "height", "batch_size"), image=resize_first.out("image"))
    empty_audio = _node(
        wf,
        "LTXVEmptyLatentAudio",
        "101",
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
        width=image_size.out("width"),
        height=image_size.out("height"),
        length=frames.out("value"),
    )

    first_guide = _node(
        wf,
        "LTXVAddGuide",
        "115",
        _outputs=("positive", "negative", "latent"),
        frame_idx=0,
        strength=1.0,
        image=preprocess_first.out("image"),
        latent=empty_video.out("latent"),
        negative=conditioning.out("negative"),
        positive=conditioning.out("positive"),
        vae=checkpoint.out("vae"),
    )
    last_guide = _node(
        wf,
        "LTXVAddGuide",
        "111",
        _outputs=("positive", "negative", "latent"),
        frame_idx=-1,
        strength=1.0,
        image=preprocess_last.out("image"),
        latent=first_guide.out("latent"),
        negative=first_guide.out("negative"),
        positive=first_guide.out("positive"),
        vae=checkpoint.out("vae"),
    )

    guider = _node(
        wf,
        "CFGGuider",
        "116",
        _outputs=("guider",),
        cfg=1,
        model=checkpoint.out("model"),
        negative=last_guide.out("negative"),
        positive=last_guide.out("positive"),
    )
    sampler = _node(wf, "SamplerEulerAncestral", "117", _outputs=("sampler",), eta=0, s_noise=1)
    sigmas = _node(
        wf,
        "ManualSigmas",
        "118",
        _outputs=("sigmas",),
        sigmas="1., 0.99375, 0.9875, 0.98125, 0.975, 0.909375, 0.725, 0.421875, 0.0",
        widget_0="1., 0.99375, 0.9875, 0.98125, 0.975, 0.909375, 0.725, 0.421875, 0.0",
    )
    concat = _node(
        wf,
        "LTXVConcatAVLatent",
        "119",
        _outputs=("latent",),
        audio_latent=empty_audio.out("audio_latent"),
        video_latent=last_guide.out("latent"),
    )
    sampled = _node(
        wf,
        "SamplerCustomAdvanced",
        "120",
        _outputs=("output", "denoised_output"),
        guider=guider.out("guider"),
        latent_image=concat.out("latent"),
        noise=randomnoise.out("noise"),
        sampler=sampler.out("sampler"),
        sigmas=sigmas.out("sigmas"),
    )
    separated = _node(
        wf,
        "LTXVSeparateAVLatent",
        "121",
        _outputs=("video_latent", "audio_latent"),
        av_latent=sampled.out("denoised_output"),
    )
    cropped = _node(
        wf,
        "LTXVCropGuides",
        "106",
        _outputs=("positive", "negative", "latent"),
        latent=separated.out("video_latent"),
        negative=last_guide.out("negative"),
        positive=last_guide.out("positive"),
    )
    decoded_audio = _node(
        wf,
        "LTXVAudioVAEDecode",
        "107",
        _outputs=("audio",),
        audio_vae=audio_vae.out("audio_vae"),
        samples=separated.out("audio_latent"),
    )
    decoded_video = _node(
        wf,
        "VAEDecodeTiled",
        "105",
        _outputs=("images",),
        tile_size=768,
        overlap=64,
        temporal_size=4096,
        temporal_overlap=64,
        samples=cropped.out("latent"),
        vae=checkpoint.out("vae"),
    )
    video = _node(
        wf,
        "CreateVideo",
        "122",
        _outputs=("video",),
        fps=fps.out("value"),
        audio=decoded_audio.out("audio"),
        images=decoded_video.out("images"),
    )
    _node(wf, "SaveVideo", "68", filename_prefix="output", format="auto", codec="auto", video=video.out("video"))

    wf.finalize_metadata()
    apply_ready_template_policy(wf, READY_METADATA, source_path=__file__, requirements=READY_REQUIREMENTS)

    wf.register_input("prompt", "128", "text", value=prompt.node.inputs.get("text"))
    wf.register_input("negative_prompt", "112", "text", value=negative.node.inputs.get("text"))
    wf.register_input("seed", "100", "noise_seed", value=315253765879496)
    wf.register_input("seed_first", "100", "noise_seed", value=315253765879496)
    wf.register_input("seed_last", "100", "noise_seed", value=315253765879496)
    wf.register_input("width", "113", "value", value=1280)
    wf.register_input("height", "98", "value", value=720)
    wf.register_input("frames", "102", "value", value=121)
    wf.register_input("fps", "123", "value", value=24)
    wf.register_input("fps_int", "114", "value", value=24)
    wf.register_input("first_strength", "115", "strength", value=1.0)
    wf.register_input("last_strength", "111", "strength", value=1.0)
    wf.register_input("first_image", "31", "image", value="first.png")
    wf.register_input("last_image", "39", "image", value="last.png")
    wf.register_input("model", "127", "ckpt_name", value="ltx-2.3-22b-distilled-fp8.safetensors")

    return wf


def _node(
    wf: VibeWorkflow,
    class_type: str,
    _id: str,
    _extras: dict | None = None,
    _outputs: tuple[str, ...] | None = None,
    **kwargs,
):
    """Create a node while preserving the original source workflow id."""
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
