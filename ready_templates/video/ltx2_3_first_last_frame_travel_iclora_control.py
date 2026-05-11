# vibecomfy: manual
"""LTX 2.3 first/last-frame travel with full-length IC-LoRA control guide."""
from __future__ import annotations

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
        "subdir": "vae",
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
        "control_mode": "6000.value",
        "prompt": "16.text",
        "negative": "11.text",
        "frames": "2078.widget_0",
        "width": "2080.widget_0",
        "height": "2079.widget_0",
        "fps": "2076.value",
        "strength": "5012.widget_1",
        "ic_lora_filename": "5011.lora_name",
        "ic_lora_strength": "5011.widget_1",
    },
    "ready_template": "video/ltx2_3_first_last_frame_travel_iclora_control",
    "workflow_template": "ltx2_3_first_last_frame_travel_iclora_control",
    "capability": "first_last_frame_control_video",
    "source_role": "manual_ready_python_template",
    "source_workflow": "manual composition of Runexx first/last frame and Lightricks IC-LoRA union control",
    "coverage_tier": "required",
    "approach": "first/last-frame image anchors plus full-length raw/pose/depth/canny IC-LoRA guide branches",
    "runtime_note": "Default guide branch is Canny. Patch node 5012 input image to select raw, pose, or depth branches.",
    "discord_signal": "Combines recurring LTX first/last travel and full-length control-guide workflows.",
    "smoke_resolution": "256x256x9_frames",
    "ltx_best_practices": [
        "Use first/last anchors for travel endpoints.",
        "Use a full-length guide video with IC-LoRA union-control conditioning.",
        "Patch smoke runs to fp8/fp4 model assets, tiny frame counts, and low-VRAM loader settings.",
    ],
    "comfy_configuration": {"reserve_vram": 12, "cache_none": True, "fp8_e4m3fn_text_enc": True},
}

READY_REQUIREMENTS = {
    "models": [],
    "custom_nodes": [
        "ComfyUI-DepthAnythingV2",
        "ComfyUI-GGUF",
        "ComfyUI-KJNodes",
        "ComfyUI-LTXVideo",
        "ComfyUI-VideoHelperSuite",
        "comfyui_controlnet_aux",
    ],
}


def build() -> VibeWorkflow:
    wf = VibeWorkflow(
        READY_METADATA["ready_template"],
        WorkflowSource(
            id=READY_METADATA["ready_template"],
            path=__file__,
            source_type="ready_template",
        ),
    )

    sampler_refine = _node(wf, "KSamplerSelect", "1", sampler_name="euler_ancestral_cfg_pp")
    sampler_finish = _node(wf, "KSamplerSelect", "4", sampler_name="euler_cfg_pp")
    randomnoise_finish = _node(wf, "RandomNoise", "14", noise_seed=43, control_after_generate="fixed")
    randomnoise_refine = _node(wf, "RandomNoise", "15", noise_seed=42, control_after_generate="fixed")

    start_image = _node(wf, "LoadImage", "45", image="example.png", widget_1="image")
    end_image = _node(wf, "LoadImage", "47", image="egyptian_queen.png", widget_1="image")
    control_video = _node(
        wf,
        "LoadVideo",
        "5001",
        file="ltx_smoke_guide.mp4",
        video="ltx_smoke_guide.mp4",
        widget_0="ltx_smoke_guide.mp4",
        widget_1="image",
    )
    control_mode = _node(wf, "PrimitiveString", "6000", value="canny")

    fps = _node(wf, "PrimitiveFloat", "2076", value=8)
    frames = _node(wf, "INTConstant", "2078", widget_0=9)
    height = _node(wf, "INTConstant", "2079", widget_0=256)
    width = _node(wf, "INTConstant", "2080", widget_0=256)
    first_strength = _node(wf, "PrimitiveFloat", "2110", value=0.8)
    last_strength = _node(wf, "PrimitiveFloat", "2108", value=0.8)

    video_vae = _node(wf, "VAELoader", "181", vae_name="LTX23_video_vae_bf16.safetensors")
    tiny_vae = _node(wf, "VAELoader", "180", vae_name="taeltx2_3.safetensors")
    audio_vae = _node(
        wf,
        "VAELoaderKJ",
        "175",
        widget_0="LTX23_audio_vae_bf16.safetensors",
        widget_1="main_device",
        widget_2="bf16",
    )
    unet = _node(
        wf,
        "UNETLoader",
        "187",
        unet_name="ltx-2.3-22b-distilled-1.1_transformer_only_fp8_scaled.safetensors",
        weight_dtype="default",
    )
    clip = _node(
        wf,
        "DualCLIPLoader",
        "190",
        clip_name1="gemma_3_12B_it_fp4_mixed.safetensors",
        clip_name2="ltx-2.3_text_projection_bf16.safetensors",
        type="ltxv",
        device="default",
    )
    distilled_lora = _node(
        wf,
        "LoraLoaderModelOnly",
        "186",
        lora_name="LTX\\v2\\ltx-2.3-22b-distilled-1.1_lora-dynamic_fro09_avg_rank_111_bf16.safetensors",
        strength_model=0.6,
        model=unet.out(0),
    )
    preview_model = _node(wf, "LTX2SamplingPreviewOverride", "198", widget_0=8, model=unet.out(0), vae=tiny_vae.out(0))
    nag_model = _node(
        wf,
        "LTX2_NAG",
        "197",
        widget_0=11,
        widget_1=0.25,
        widget_2=2.5,
        widget_3=True,
        model=preview_model.out(0),
    )
    sage = _node(wf, "PathchSageAttentionKJ", "226", widget_0="disabled", widget_1=False, model=distilled_lora.out(0))
    memory = _node(wf, "LTX2MemoryEfficientSageAttentionPatch", "227", widget_0=True, model=sage.out(0))
    chunked = _node(wf, "LTXVChunkFeedForward", "228", widget_0=2, widget_1=4096, model=memory.out(0))
    tuned = _node(
        wf,
        "LTX2AttentionTunerPatch",
        "229",
        widget_0="",
        widget_1=1,
        widget_2=1,
        widget_3=1,
        widget_4=1,
        widget_5=True,
        model=chunked.out(0),
    )
    ic_lora = _node(
        wf,
        "LTXICLoRALoaderModelOnly",
        "5011",
        lora_name="ltx-2.3-22b-ic-lora-union-control-ref0.5.safetensors",
        widget_0="ltx-2.3-22b-ic-lora-union-control-ref0.5.safetensors",
        widget_1=1,
        model=tuned.out(0),
    )

    negative = _node(
        wf,
        "CLIPTextEncode",
        "11",
        text="blurry, oversaturated, pixelated, low resolution, grainy, distorted, noise, compression artifacts, jpeg artifacts, glitches, watermark, text, logo, signature, copyright, subtitles",
        clip=clip.out(0),
    )
    positive = _node(
        wf,
        "CLIPTextEncode",
        "16",
        text="A cinematic first-to-last-frame travel shot with smooth continuous camera motion, coherent subject motion, realistic lighting, and natural temporal consistency.",
        clip=clip.out(0),
    )
    conditioning = _node(
        wf,
        "LTXVConditioning",
        "10",
        widget_0=8,
        frame_rate=fps.out(0),
        negative=negative.out(0),
        positive=positive.out(0),
    )

    start_resized = _node(
        wf,
        "ImageResizeKJv2",
        "44",
        widget_0=256,
        widget_1=256,
        widget_2="nearest-exact",
        widget_3="crop",
        widget_4="0, 0, 0",
        widget_5="center",
        widget_6=32,
        widget_7="cpu",
        height=height.out(0),
        image=start_image.out(0),
        width=width.out(0),
    )
    end_resized = _node(
        wf,
        "ImageResizeKJv2",
        "48",
        widget_0=256,
        widget_1=256,
        widget_2="nearest-exact",
        widget_3="crop",
        widget_4="0, 0, 0",
        widget_5="center",
        widget_6=32,
        widget_7="cpu",
        height=height.out(0),
        image=end_image.out(0),
        width=width.out(0),
    )
    first_preprocessed = _node(wf, "LTXVPreprocess", "2084", widget_0=18, image=start_resized.out(0))
    last_preprocessed = _node(wf, "LTXVPreprocess", "50", widget_0=18, image=end_resized.out(0))

    components = _node(wf, "GetVideoComponents", "5000", video=control_video.out(0))
    guide_resized = _node(
        wf,
        "ResizeImageMaskNode",
        "5026",
        widget_0="scale to multiple",
        widget_1=256,
        widget_2="lanczos",
        input=components.out(0),
        _extras={"resize_type.multiple": ic_lora.out(1)},
    )
    guide_raw = _node(
        wf,
        "ResizeImageMaskNode",
        "6101",
        widget_0="scale to multiple",
        widget_1=256,
        widget_2="lanczos",
        input=guide_resized.out(0),
        _extras={"resize_type.multiple": ic_lora.out(1)},
    )
    guide_pose = _node(
        wf,
        "DWPreprocessor",
        "4986",
        widget_0="enable",
        widget_1="enable",
        widget_2="enable",
        widget_3=256,
        widget_4="yolox_l.onnx",
        widget_5="dw-ll_ucoco_384_bs5.torchscript.pt",
        widget_6="disable",
        image=guide_resized.out(0),
    )
    guide_canny_edges = _node(
        wf,
        "CannyEdgePreprocessor",
        "4991",
        widget_0=92,
        widget_1=200,
        widget_2=256,
        image=guide_resized.out(0),
    )
    depth_model = _node(wf, "DownloadAndLoadDepthAnythingV2Model", "5060", model="depth_anything_v2_vits_fp32.safetensors", precision="fp32")
    guide_depth = _node(wf, "DepthAnything_V2", "5061", da_model=depth_model.out(0), images=guide_resized.out(0))
    guide_canny = _node(
        wf,
        "ResizeImageMaskNode",
        "5028",
        widget_0="scale to multiple",
        widget_1=256,
        widget_2="lanczos",
        input=guide_canny_edges.out(0),
        _extras={"resize_type.multiple": ic_lora.out(1)},
    )
    guide_pose_sized = _node(
        wf,
        "ResizeImageMaskNode",
        "6102",
        widget_0="scale to multiple",
        widget_1=256,
        widget_2="lanczos",
        input=guide_pose.out(0),
        _extras={"resize_type.multiple": ic_lora.out(1)},
    )
    guide_depth_sized = _node(
        wf,
        "ResizeImageMaskNode",
        "6103",
        widget_0="scale to multiple",
        widget_1=256,
        widget_2="lanczos",
        input=guide_depth.out(0),
        _extras={"resize_type.multiple": ic_lora.out(1)},
    )

    latent = _node(
        wf,
        "EmptyLTXVLatentVideo",
        "32",
        batch_size=1,
        widget_0=256,
        widget_1=256,
        widget_2=9,
        width=width.out(0),
        height=height.out(0),
        length=frames.out(0),
    )
    fps_int = _node(wf, "LTXFloatToInt", "5066", widget_0=0, a=fps.out(0))
    audio_latent = _node(
        wf,
        "LTXVEmptyLatentAudio",
        "9",
        widget_0=9,
        widget_1=8,
        widget_2=1,
        audio_vae=audio_vae.out(0),
        frame_rate=fps_int.out(0),
        frames_number=frames.out(0),
    )
    anchored_latent = _node(
        wf,
        "LTXVImgToVideoInplaceKJ",
        "210",
        latent=latent.out(0),
        num_images="2",
        vae=video_vae.out(0),
        _extras={
            "num_images.image_1": first_preprocessed.out(0),
            "num_images.image_2": last_preprocessed.out(0),
            "num_images.index_1": 0,
            "num_images.index_2": -1,
            "num_images.strength_1": first_strength.out(0),
            "num_images.strength_2": last_strength.out(0),
        },
    )
    guided = _node(
        wf,
        "LTXAddVideoICLoRAGuide",
        "5012",
        widget_0=0,
        widget_1=1,
        widget_2=1,
        widget_3="disabled",
        widget_4=False,
        widget_5=128,
        widget_6=32,
        image=guide_canny.out(0),
        latent=anchored_latent.out(0),
        latent_downscale_factor=ic_lora.out(1),
        negative=conditioning.out(1),
        positive=conditioning.out(0),
        vae=video_vae.out(0),
    )
    av_latent = _node(wf, "LTXVConcatAVLatent", "24", audio_latent=audio_latent.out(0), video_latent=guided.out(2))
    cfg_refine = _node(wf, "CFGGuider", "36", cfg=2.5, model=nag_model.out(0), negative=conditioning.out(1), positive=conditioning.out(0))
    sigmas_refine = _node(wf, "ManualSigmas", "215", widget_0="1.0, 0.99375, 0.9875, 0.98125, 0.975, 0.909375, 0.725, 0.421875, 0.0")
    refined = _node(
        wf,
        "SamplerCustomAdvanced",
        "13",
        guider=cfg_refine.out(0),
        latent_image=av_latent.out(0),
        noise=randomnoise_refine.out(0),
        sampler=sampler_refine.out(0),
        sigmas=sigmas_refine.out(0),
    )
    separated_refined = _node(wf, "LTXVSeparateAVLatent", "18", av_latent=refined.out(0))
    av_latent_finish = _node(wf, "LTXVConcatAVLatent", "34", audio_latent=separated_refined.out(1), video_latent=separated_refined.out(0))
    cfg_finish = _node(wf, "CFGGuider", "8", cfg=2.5, model=ic_lora.out(0), negative=guided.out(1), positive=guided.out(0))
    sigmas_finish = _node(wf, "ManualSigmas", "216", widget_0="0.85, 0.7250, 0.4219, 0.0")
    finished = _node(
        wf,
        "SamplerCustomAdvanced",
        "21",
        guider=cfg_finish.out(0),
        latent_image=av_latent_finish.out(0),
        noise=randomnoise_finish.out(0),
        sampler=sampler_finish.out(0),
        sigmas=sigmas_finish.out(0),
    )
    separated_finished = _node(wf, "LTXVSeparateAVLatent", "146", av_latent=finished.out(0))
    cropped = _node(wf, "LTXVCropGuides", "2156", latent=separated_finished.out(0), negative=guided.out(1), positive=guided.out(0))
    decoded_audio = _node(wf, "LTXVAudioVAEDecode", "150", audio_vae=audio_vae.out(0), samples=separated_finished.out(1))
    decoded_video = _node(
        wf,
        "VAEDecodeTiled",
        "149",
        tile_size=512,
        overlap=64,
        temporal_size=4096,
        temporal_overlap=8,
        samples=cropped.out(2),
        vae=video_vae.out(0),
    )
    output = _node(
        wf,
        "VHS_VideoCombine",
        "43",
        audio=decoded_audio.out(0),
        filename_prefix="reigh_vibecomfy_ltx_control_first_last",
        format="video/h264-mp4",
        frame_rate=fps.out(0),
        images=decoded_video.out(0),
        loop_count=0,
        pingpong=False,
        save_output=True,
    )

    wf.finalize_metadata()
    wf.register_input("start_image", "45", "image", "example.png")
    wf.register_input("end_image", "47", "image", "egyptian_queen.png")
    wf.register_input("control_video", "5001", "video", "ltx_smoke_guide.mp4")
    wf.register_input("control_mode", "6000", "value", "canny")
    wf.register_input("prompt", "16", "text", positive.node.inputs["text"])
    wf.register_input("negative", "11", "text", negative.node.inputs["text"])
    wf.register_input("seed", "14", "noise_seed", 43)
    wf.register_input("frames", "2078", "widget_0", 9)
    wf.register_input("width", "2080", "widget_0", 256)
    wf.register_input("height", "2079", "widget_0", 256)
    wf.register_input("fps", "2076", "value", 8)
    wf.register_input("strength", "5012", "widget_1", 1)
    wf.register_input("ic_lora_filename", "5011", "lora_name", "ltx-2.3-22b-ic-lora-union-control-ref0.5.safetensors")
    wf.register_input("ic_lora_strength", "5011", "widget_1", 1)
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
