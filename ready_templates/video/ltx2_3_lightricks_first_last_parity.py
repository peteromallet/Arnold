# vibecomfy: manual
"""Lightricks LTX 2.3 distilled first/last parity template.

Pure-Python ready template based on the official ComfyUI LTX 2.3 FLF2V
workflow.  This route uses the dedicated distilled fp8 checkpoint rather than
the heavier dev checkpoint plus distilled LoRA spine.
"""
from __future__ import annotations

from vibecomfy.workflow import VibeWorkflow
from vibecomfy.templates import InputSpec, ModelAsset, ReadyMetadata, finalize, new_workflow, node


VIDEO_OUTPUT_NODE = "68"
VIDEO_OUTPUT_NAME = "video"
VIDEO_OUTPUT_PREFIX = "output"
VIDEO_OUTPUT_MIME = "video/mp4"
MODELS = {
    'ltx_2_3_22b_distilled_fp8': ModelAsset(
        filename='ltx-2.3-22b-distilled-fp8.safetensors',
        url='https://huggingface.co/Lightricks/LTX-2.3-fp8/resolve/main/ltx-2.3-22b-distilled-fp8.safetensors',
        subdir='checkpoints',
        sha256='d9646b6f2d5c42d337b23671634c43bfeece6989644f51b4a3aa088465ccd3b2',
        hf_revision='1d756cd27fa11c0896c4dfee093cd1bf36c7f7a1',
        size_bytes=29531884062,
    ),
    'gemma_3_12b_it_fp4_mixed': ModelAsset(
        filename='gemma_3_12B_it_fp4_mixed.safetensors',
        url='https://huggingface.co/Comfy-Org/ltx-2/resolve/main/split_files/text_encoders/gemma_3_12B_it_fp4_mixed.safetensors',
        subdir='text_encoders',
        sha256='aaca463d11e6d8d2a4bdb0d6299214c15ef78a3f73e0ef8113d5a9d0219b3f6d',
        hf_revision='bd5f9c87fcb0360ae7112f9784562670894d9492',
        size_bytes=9447702218,
    ),
}

PUBLIC_INPUTS = {
    'prompt': InputSpec(node='128', field='text', default='A cinematic first-last frame transition.', type='STRING', description='Text prompt.', media_semantics='text'),
    'negative_prompt': InputSpec(node='112', field='text', default='blurry, distorted, low quality', type='STRING', description='Negative text prompt.', media_semantics='text'),
    'seed': InputSpec(node='100', field='noise_seed', default=42, type='INT', description='Random seed.'),
    'seed_first': InputSpec(node='100', field='noise_seed', default=42, type='INT', description='Seed first.'),
    'seed_last': InputSpec(node='100', field='noise_seed', default=42, type='INT', description='Seed last.'),
    'width': InputSpec(node='113', field='value', default=832, type='INT', description='Output width.'),
    'height': InputSpec(node='98', field='value', default=480, type='INT', description='Output height.'),
    'output_fps': InputSpec(node='123', field='value', default=16, type='FLOAT', aliases=('fps',), description='Output playback frame rate.'),
    'fps_int': InputSpec(node='114', field='value', default=16, type='INT', description='Fps int.'),
    'first_strength': InputSpec(node='115', field='strength', default=1.0, type='FLOAT', description='First strength.'),
    'last_strength': InputSpec(node='111', field='strength', default=1.0, type='FLOAT', description='Last strength.'),
    'first_image': InputSpec(node='31', field='image', default='example_start.png', type='IMAGE', description='First image.'),
    'last_image': InputSpec(node='39', field='image', default='example_end.png', type='IMAGE', description='Last image.'),
    'start_image': InputSpec(node='31', field='image', default='example_start.png', type='IMAGE', description='Starting image.', media_semantics='image'),
    'end_image': InputSpec(node='39', field='image', default='example_end.png', type='IMAGE', description='Ending image.', media_semantics='image'),
    'model': InputSpec(node='127', field='ckpt_name', default=MODELS['ltx_2_3_22b_distilled_fp8'].filename, type='STRING', description='Model.'),
    'length': InputSpec(node='102', field='value', default=81, type='INT', aliases=('frames',), description='Number of output frames.'),
}

READY_METADATA = ReadyMetadata.build(
    template_id='ltx2_3_lightricks_first_last_parity',
    capability='first_last_frame_video',
    inputs=PUBLIC_INPUTS,
    models=MODELS,
    output_prefix='',
    requirements={'custom_nodes': ['ComfyUI-KJNodes', 'ComfyUI-LTXVideo'], 'custom_node_refs': [{'slug': 'ComfyUI-KJNodes', 'source': 'git', 'commit': 'b7646ad70a7daa7aeb919ca542274758d26ba2df', 'url': 'https://github.com/kijai/ComfyUI-KJNodes.git'}, {'slug': 'ComfyUI-LTXVideo', 'source': 'git',
                       'commit': '229437c6b65796d6a7a63ae34be2bd5ba31fa543', 'url': 'https://github.com/Lightricks/ComfyUI-LTXVideo.git'}]},
    provenance={'source_workflow': 'vendor/ComfyUI/tests/unit/playwright_cache/*/video_ltx2_3_flf2v.json', 'approach': 'Official Lightricks distilled fp8 first/last frame route', 'smoke_resolution': '256x256x5_frames', 'source_role': 'manual_ready_python_template'},
    coverage_tier='required',
    runtime_note='Patches named inputs for prompt, negative, seed, dimensions, frames, fps, first/last guide strengths, and first/last images.',
    discord_signal='Banodoco LTX notes point to the dedicated distilled fp8/quantized route for 4090 viability; dev+LoRA two-stage routes can OOM at 24GB.',
    ltx_best_practices=['Use the dedicated distilled fp8 checkpoint for first/last workflows on 24GB GPUs.', "Keep guide strengths in Wan2GP's 0..1 range.", 'Use tiled VAE decode for full-size app outputs.', 'Do not force the LTX2 memory-efficient Sage/Triton patch in the portable 4090 profile; LTX 2.3 guide masks must remain on the stable SDPA-compatible path unless a separate optimized profile proves the patch end-to-end.'],
    comfy_configuration={'memory_profile': 3, 'fp8_e4m3fn_text_enc': True},
    vibecomfy_version='0.1.0',
    comfy_core={'version': '0.18.2', 'tested_at': '2026-05-20T09:19:32.302139+00:00', 'commit': 'f7b38d2eb97207cd834bcc3eb2e8b1d447b96c68', 'status': 'discovered'},
)

READY_METADATA["unbound_inputs"].update({'end_image': '39.image', 'first_image': '31.image', 'first_strength': '115.strength', 'fps': '123.value', 'fps_int': '114.value', 'frames': '102.value', 'height': '98.value', 'last_image': '39.image', 'last_strength': '111.strength', 'model': '127.ckpt_name', 'negative_prompt': '112.text', 'prompt': '128.text', 'seed': '100.noise_seed', 'seed_first': '100.noise_seed', 'seed_last': '100.noise_seed', 'start_image': '31.image', 'width': '113.value'})

def build() -> VibeWorkflow:
    """Build the official distilled fp8 first/last workflow."""
    wf = new_workflow(READY_METADATA, source_path=__file__)

    # ════ INPUTS ════
    loadimage_first = node(wf, "LoadImage", "31", _outputs=("image", "mask"), image=PUBLIC_INPUTS['start_image'].default)
    loadimage_last = node(wf, "LoadImage", "39", _outputs=("image", "mask"), image=PUBLIC_INPUTS['end_image'].default)

    # ════ SAMPLING ════
    noise = node(wf, "RandomNoise", "100", _outputs=("noise",), noise_seed=PUBLIC_INPUTS['seed_last'].default)
    frames = node(wf, "PrimitiveInt", "102", _outputs=("value",), value=PUBLIC_INPUTS['length'].default)
    width = node(wf, "PrimitiveInt", "113", _outputs=("value",), value=PUBLIC_INPUTS['width'].default)
    height = node(wf, "PrimitiveInt", "98", _outputs=("value",), value=PUBLIC_INPUTS['height'].default)
    fps_int = node(wf, "PrimitiveInt", "114", _outputs=("value",), value=PUBLIC_INPUTS['fps_int'].default)
    fps = node(wf, "PrimitiveFloat", "123", _outputs=("value",), value=PUBLIC_INPUTS['output_fps'].default)

    # ════ TEXT CONDITIONING ════
    text_encoder = node(
        wf,
        "LTXAVTextEncoderLoader",
        "103",
        ckpt_name=MODELS['ltx_2_3_22b_distilled_fp8'].filename,
        text_encoder=MODELS['gemma_3_12b_it_fp4_mixed'].filename,
        device="default",
        _outputs=("clip",),
    )
    # ════ LOADERS ════
    audio_vae = node(
        wf,
        "LTXVAudioVAELoader",
        "126",
        _outputs=("audio_vae",),
        ckpt_name=MODELS['ltx_2_3_22b_distilled_fp8'].filename,
    )
    checkpoint = node(
        wf,
        "CheckpointLoaderSimple",
        "127",
        _outputs=("model", "clip", "vae"),
        ckpt_name=PUBLIC_INPUTS['model'].default,
    )

    # ════ IMAGE PREP ════
    resize_first = node(
        wf,
        "ResizeImageMaskNode",
        "124",
        _extras={
            "resize_type.width": width.out('VALUE'),
            "resize_type.height": height.out('VALUE'),
            "resize_type.crop": "center",
        },
        _outputs=("image",),
        resize_type="scale dimensions",
        scale_method="nearest-exact",
        input=loadimage_first.out('IMAGE'),
    )
    resize_last = node(
        wf,
        "ResizeImageMaskNode",
        "125",
        _extras={
            "resize_type.width": width.out('VALUE'),
            "resize_type.height": height.out('VALUE'),
            "resize_type.crop": "center",
        },
        _outputs=("image",),
        resize_type="scale dimensions",
        scale_method="nearest-exact",
        input=loadimage_last.out('IMAGE'),
    )
    preprocess_first = node(
        wf,
        "LTXVPreprocess",
        "104",
        _outputs=("image",),
        img_compression=25,
        image=resize_first.out('IMAGE'),
    )
    preprocess_last = node(
        wf,
        "LTXVPreprocess",
        "99",
        _outputs=("image",),
        img_compression=25,
        image=resize_last.out('IMAGE'),
    )

    positive_prompt = node(
        wf,
        "CLIPTextEncode",
        "128",
        _outputs=("conditioning",),
        text=PUBLIC_INPUTS['prompt'].default,
        clip=text_encoder.out('CLIP'),
    )
    negative_prompt = node(
        wf,
        "CLIPTextEncode",
        "112",
        _outputs=("conditioning",),
        text=PUBLIC_INPUTS['negative_prompt'].default,
        clip=text_encoder.out('CLIP'),
    )
    conditioning = node(
        wf,
        "LTXVConditioning",
        "109",
        _outputs=("positive", "negative"),
        frame_rate=fps.out('VALUE'),
        negative=negative_prompt.out('CONDITIONING'),
        positive=positive_prompt.out('CONDITIONING'),
    )

    image_size = node(wf, "GetImageSize", "110", _outputs=("width", "height", "batch_size"), image=resize_first.out('IMAGE'))
    # ════ LATENT ════
    empty_audio = node(
        wf,
        "LTXVEmptyLatentAudio",
        "101",
        _outputs=("audio_latent",),
        batch_size=1,
        frame_rate=fps_int.out('VALUE'),
        frames_number=frames.out('VALUE'),
        audio_vae=audio_vae.out('AUDIO_VAE'),
    )
    empty_video = node(
        wf,
        "EmptyLTXVLatentVideo",
        "108",
        _outputs=("latent",),
        batch_size=1,
        width=image_size.out('WIDTH'),
        height=image_size.out('HEIGHT'),
        length=frames.out('VALUE'),
    )

    first_guide = node(
        wf,
        "LTXVAddGuide",
        "115",
        _outputs=("positive", "negative", "latent"),
        frame_idx=0,
        strength=PUBLIC_INPUTS['first_strength'].default,
        image=preprocess_first.out('IMAGE'),
        latent=empty_video.out('LATENT'),
        negative=conditioning.out('NEGATIVE'),
        positive=conditioning.out('POSITIVE'),
        vae=checkpoint.out('VAE'),
    )
    last_guide = node(
        wf,
        "LTXVAddGuide",
        "111",
        _outputs=("positive", "negative", "latent"),
        frame_idx=-1,
        strength=PUBLIC_INPUTS['last_strength'].default,
        image=preprocess_last.out('IMAGE'),
        latent=first_guide.out('LATENT'),
        negative=first_guide.out('NEGATIVE'),
        positive=first_guide.out('POSITIVE'),
        vae=checkpoint.out('VAE'),
    )

    guider = node(
        wf,
        "CFGGuider",
        "116",
        _outputs=("guider",),
        cfg=1,
        model=checkpoint.out('MODEL'),
        negative=last_guide.out('NEGATIVE'),
        positive=last_guide.out('POSITIVE'),
    )
    sampler = node(wf, "SamplerEulerAncestral", "117", _outputs=("sampler",), eta=0, s_noise=1)
    sigmas = node(
        wf,
        "ManualSigmas",
        "118",
        _outputs=("sigmas",),
        sigmas="1., 0.99375, 0.9875, 0.98125, 0.975, 0.909375, 0.725, 0.421875, 0.0",
    )
    concat = node(
        wf,
        "LTXVConcatAVLatent",
        "119",
        _outputs=("latent",),
        audio_latent=empty_audio.out('AUDIO_LATENT'),
        video_latent=last_guide.out('LATENT'),
    )
    sampled = node(
        wf,
        "SamplerCustomAdvanced",
        "120",
        _outputs=("output", "denoised_output"),
        guider=guider.out('GUIDER'),
        latent_image=concat.out('LATENT'),
        noise=noise.out('NOISE'),
        sampler=sampler.out('SAMPLER'),
        sigmas=sigmas.out('SIGMAS'),
    )
    separated = node(
        wf,
        "LTXVSeparateAVLatent",
        "121",
        _outputs=("video_latent", "audio_latent"),
        av_latent=sampled.out('DENOISED_OUTPUT'),
    )
    cropped = node(
        wf,
        "LTXVCropGuides",
        "106",
        _outputs=("positive", "negative", "latent"),
        latent=separated.out('VIDEO_LATENT'),
        negative=last_guide.out('NEGATIVE'),
        positive=last_guide.out('POSITIVE'),
    )
    # ════ DECODE ════
    decoded_audio = node(
        wf,
        "LTXVAudioVAEDecode",
        "107",
        _outputs=("audio",),
        audio_vae=audio_vae.out('AUDIO_VAE'),
        samples=separated.out('AUDIO_LATENT'),
    )
    decoded_video = node(
        wf,
        "VAEDecodeTiled",
        "105",
        _outputs=("images",),
        tile_size=768,
        overlap=64,
        temporal_size=4096,
        temporal_overlap=64,
        samples=cropped.out('LATENT'),
        vae=checkpoint.out('VAE'),
    )
    # ════ OUTPUT ════
    video = node(
        wf,
        "CreateVideo",
        "122",
        _outputs=("video",),
        fps=fps.out('VALUE'),
        audio=decoded_audio.out('AUDIO'),
        images=decoded_video.out('IMAGES'),
    )
    node(wf, "SaveVideo", VIDEO_OUTPUT_NODE, filename_prefix=VIDEO_OUTPUT_PREFIX, format="auto", codec="auto", video=video.out('VIDEO'))

    return finalize(
        wf,
        PUBLIC_INPUTS,
        READY_METADATA,
        output_node='68',
        output_type='SaveVideo',
        name='video',
        mime_type='video/mp4',
        expected_cardinality='one',
        source_path=__file__,
    )

