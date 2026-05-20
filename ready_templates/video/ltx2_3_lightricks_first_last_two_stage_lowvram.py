# vibecomfy: manual
"""LTX 2.3 first/last two-stage low-VRAM parity candidate.

This keeps the Wan2GP-relevant two-stage shape while using the official
Lightricks low-VRAM loader family that fits 24GB GPUs.
"""
from __future__ import annotations

from vibecomfy.workflow import VibeWorkflow
from vibecomfy.templates import InputSpec, ModelAsset, ReadyMetadata, finalize, new_workflow, node

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


VIDEO_OUTPUT_NODE = "4852"
VIDEO_OUTPUT_NAME = "video"
VIDEO_OUTPUT_PREFIX = "output"
VIDEO_OUTPUT_MIME = "video/mp4"

def _resize_image_masknode(wf, _id, _outputs, _extras, input, **overrides):
    kwargs = dict(resize_type='scale dimensions',
                  scale_method='nearest-exact',
                  _outputs=_outputs,
                  _extras=_extras,
                  input=input)
    kwargs.update(overrides)
    return node(wf, 'ResizeImageMaskNode', _id, **kwargs)
def _l_t_x_v_preprocess(wf, _id, _outputs, image, **overrides):
    kwargs = dict(img_compression=25,
                  _outputs=_outputs,
                  image=image)
    kwargs.update(overrides)
    return node(wf, 'LTXVPreprocess', _id, **kwargs)
MODELS = {
    'ltx_2_3_22b_distilled_fp8': ModelAsset(
        filename='ltx-2.3-22b-distilled-fp8.safetensors',
        url='https://huggingface.co/Lightricks/LTX-2.3-fp8/resolve/main/ltx-2.3-22b-distilled-fp8.safetensors',
        subdir='checkpoints',
    ),
    'gemma_3_12b_it_fp4_mixed': ModelAsset(
        filename='gemma_3_12B_it_fp4_mixed.safetensors',
        url='https://huggingface.co/Comfy-Org/ltx-2/resolve/main/split_files/text_encoders/gemma_3_12B_it_fp4_mixed.safetensors',
        subdir='text_encoders',
    ),
    'ltx_2_3_spatial_upscaler_x2_1_1': ModelAsset(
        filename='ltx-2.3-spatial-upscaler-x2-1.1.safetensors',
        url='https://huggingface.co/Lightricks/LTX-2.3/resolve/main/ltx-2.3-spatial-upscaler-x2-1.1.safetensors',
        subdir='latent_upscale_models',
    ),
}

PUBLIC_INPUTS = {
    'prompt': InputSpec(node='128', field='text', default='A cinematic first-last frame transition.', type='STRING', description='Text prompt.', media_semantics='text'),
    'negative_prompt': InputSpec(node='112', field='text', default='blurry, distorted, low quality', type='STRING', aliases=('negative',), description='Negative text prompt.', media_semantics='text'),
    'seed': InputSpec(node='100', field='noise_seed', default=42, type='INT', description='Random seed.'),
    'seed_first': InputSpec(node='100', field='noise_seed', default=42, type='INT', description='Seed first.'),
    'seed_last': InputSpec(node='101', field='noise_seed', default=42, type='INT', description='Seed last.'),
    'width': InputSpec(node='113', field='value', default=832, type='INT', description='Output width.'),
    'height': InputSpec(node='98', field='value', default=480, type='INT', description='Output height.'),
    'stage1_width': InputSpec(node='1131', field='value', default=832, type='INT', description='Stage1 width.'),
    'stage1_height': InputSpec(node='981', field='value', default=480, type='INT', description='Stage1 height.'),
    'output_fps': InputSpec(node='123', field='value', default=16, type='FLOAT', aliases=('fps',), description='Output playback frame rate.'),
    'fps_int': InputSpec(node='114', field='value', default=16, type='INT', description='Fps int.'),
    'first_strength': InputSpec(node='115', field='strength', default=None, type='STRING', description='First strength.'),
    'last_strength': InputSpec(node='111', field='strength', default=None, type='STRING', description='Last strength.'),
    'first_frame_strength': InputSpec(node='2150', field='strength', default=None, type='STRING', description='First frame strength.'),
    'last_frame_strength': InputSpec(node='2152', field='strength', default=None, type='STRING', description='Last frame strength.'),
    'first_image': InputSpec(node='31', field='image', default='example_start.png', type='IMAGE', description='First image.'),
    'last_image': InputSpec(node='39', field='image', default='example_end.png', type='IMAGE', description='Last image.'),
    'start_image': InputSpec(node='31', field='image', default='example_start.png', type='IMAGE', description='Starting image.', media_semantics='image'),
    'end_image': InputSpec(node='39', field='image', default='example_end.png', type='IMAGE', description='Ending image.', media_semantics='image'),
    'model': InputSpec(node='127', field='ckpt_name', default=MODELS['ltx_2_3_22b_distilled_fp8'].filename, type='STRING', description='Model.'),
    'length': InputSpec(node='102', field='value', default=81, type='INT', aliases=('frames',), description='Number of output frames.'),
}

READY_METADATA = ReadyMetadata.build(
    template_id='ltx2_3_lightricks_first_last_two_stage_lowvram',
    capability='first_last_frame_video',
    inputs=PUBLIC_INPUTS,
    models=MODELS,
    output_prefix='',
    requirements={'custom_nodes': ['ComfyUI-KJNodes', 'ComfyUI-LTXVideo'], 'custom_node_refs': [{'slug': 'ComfyUI-KJNodes', 'source': 'git', 'commit': 'b7646ad70a7daa7aeb919ca542274758d26ba2df', 'url': 'https://github.com/kijai/ComfyUI-KJNodes.git'}, {'slug': 'ComfyUI-LTXVideo', 'source': 'git',
                       'commit': '229437c6b65796d6a7a63ae34be2bd5ba31fa543', 'url': 'https://github.com/Lightricks/ComfyUI-LTXVideo.git'}]},
    provenance={'source_workflow': 'manual composition of official Lightricks first/last and two-stage low-VRAM LTX 2.3 flows', 'smoke_resolution': '256x256x5_frames', 'approach': 'two-stage first/last-frame route using LowVRAMCheckpointLoader', 'source_role': 'manual_ready_python_template'},
    coverage_tier='required',
    runtime_note="Stage 1 uses Wan2GP's half-resolution long sigma schedule; the latent is spatially upsampled before stage 2 reapplies first/last guides and uses the Wan2GP refine sigma schedule.",
    discord_signal='Use dedicated distilled fp8 + low-VRAM loaders on 24GB GPUs.',
    runtime_packages=[{'name': 'sageattention', 'reason': 'Required by LTX2MemoryEfficientSageAttentionPatch for the two-stage low-VRAM LTX route.', 'source': 'SageAttention-ada'}],
    ltx_best_practices=['Use LowVRAMCheckpointLoader for 4090 viability.', 'Use the dedicated distilled fp8 checkpoint rather than the dev checkpoint plus LoRA when possible.', "Preserve Wan2GP's two-stage sigma structure for parity checks."],
    comfy_configuration={'memory_profile': 3, 'fp8_e4m3fn_text_enc': True},
    vibecomfy_version='0.1.0',
    comfy_core={'version': '0.18.2', 'tested_at': '2026-05-20T09:19:32.302139+00:00', 'commit': 'f7b38d2eb97207cd834bcc3eb2e8b1d447b96c68', 'status': 'discovered'},
)

READY_METADATA["unbound_inputs"].update({'end_image': '39.image', 'first_frame_strength': '2150.strength', 'first_image': '31.image', 'first_strength': '115.strength', 'fps': '123.value', 'fps_int': '114.value', 'frames': '102.value', 'height': '98.value', 'last_frame_strength': '2152.strength', 'last_image': '39.image', 'last_strength': '111.strength', 'model': '127.ckpt_name', 'negative': '112.text', 'negative_prompt': '112.text', 'prompt': '128.text', 'seed': '100.noise_seed', 'seed_first': '100.noise_seed', 'seed_last': '101.noise_seed', 'stage1_height': '981.value', 'stage1_width': '1131.value', 'start_image': '31.image', 'width': '113.value'})

def build() -> VibeWorkflow:
    wf = new_workflow(READY_METADATA, source_path=__file__)

    # ════ INPUTS ════
    first_image = node(wf, "LoadImage", "31", _outputs=("image", "mask"), image=PUBLIC_INPUTS['start_image'].default)
    last_image = node(wf, "LoadImage", "39", _outputs=("image", "mask"), image=PUBLIC_INPUTS['end_image'].default)
    # ════ SAMPLING ════
    seed_first = node(wf, "RandomNoise", "100", _outputs=("noise",), noise_seed=PUBLIC_INPUTS['seed_first'].default)
    seed_last = node(wf, "RandomNoise", "101", _outputs=("noise",), noise_seed=PUBLIC_INPUTS['seed_last'].default)
    frames = node(wf, "PrimitiveInt", "102", _outputs=("value",), value=PUBLIC_INPUTS['length'].default)
    width = node(wf, "PrimitiveInt", "113", _outputs=("value",), value=PUBLIC_INPUTS['width'].default)
    height = node(wf, "PrimitiveInt", "98", _outputs=("value",), value=PUBLIC_INPUTS['height'].default)
    stage1_width = node(wf, "PrimitiveInt", "1131", _outputs=("value",), value=PUBLIC_INPUTS['stage1_width'].default)
    stage1_height = node(wf, "PrimitiveInt", "981", _outputs=("value",), value=PUBLIC_INPUTS['stage1_height'].default)
    fps_int = node(wf, "PrimitiveInt", "114", _outputs=("value",), value=PUBLIC_INPUTS['fps_int'].default)
    fps = node(wf, "PrimitiveFloat", "123", _outputs=("value",), value=PUBLIC_INPUTS['output_fps'].default)

    # ════ TEXT CONDITIONING ════
    text_encoder = node(
        wf,
        "LTXAVTextEncoderLoader",
        "103",
        _outputs=("clip",),
        ckpt_name=MODELS['ltx_2_3_22b_distilled_fp8'].filename,
        text_encoder=MODELS['gemma_3_12b_it_fp4_mixed'].filename,
        device="default",
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
        "LowVRAMCheckpointLoader",
        "127",
        _outputs=("model", "clip", "vae"),
        ckpt_name=PUBLIC_INPUTS['model'].default,
    )
    patched_model = node(
        wf,
        "LTX2MemoryEfficientSageAttentionPatch",
        "129",
        _outputs=("model",),
        model=checkpoint.out('MODEL'),
        triton_kernels=True,
    )
    # ════ LATENT ════
    spatial_upscaler = node(
        wf,
        "LatentUpscaleModelLoader",
        "182",
        _outputs=("latent_upscale_model",),
        model_name=MODELS['ltx_2_3_spatial_upscaler_x2_1_1'].filename,
    )

    resize_first = _resize_image_masknode(wf, '124', ('image',), {'resize_type.width': width.out('VALUE'), 'resize_type.height': height.out('VALUE'), 'resize_type.crop': 'center'}, first_image.out('IMAGE'))
    resize_last = _resize_image_masknode(wf, '125', ('image',), {'resize_type.width': width.out('VALUE'), 'resize_type.height': height.out('VALUE'), 'resize_type.crop': 'center'}, last_image.out('IMAGE'))
    resize_first_stage1 = _resize_image_masknode(wf, '1241', ('image',), {'resize_type.width': stage1_width.out('VALUE'), 'resize_type.height': stage1_height.out('VALUE'), 'resize_type.crop': 'center'}, first_image.out('IMAGE'))
    resize_last_stage1 = _resize_image_masknode(wf, '1251', ('image',), {'resize_type.width': stage1_width.out('VALUE'), 'resize_type.height': stage1_height.out('VALUE'), 'resize_type.crop': 'center'}, last_image.out('IMAGE'))
    preprocess_first = _l_t_x_v_preprocess(wf, '104', ('image',), resize_first.out('IMAGE'))
    preprocess_last = _l_t_x_v_preprocess(wf, '99', ('image',), resize_last.out('IMAGE'))
    preprocess_first_stage1 = _l_t_x_v_preprocess(wf, '1041', ('image',), resize_first_stage1.out('IMAGE'))
    preprocess_last_stage1 = _l_t_x_v_preprocess(wf, '991', ('image',), resize_last_stage1.out('IMAGE'))

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

    stage1_image_size = node(
        wf,
        "GetImageSize",
        "110",
        _outputs=("width", "height", "batch_size"),
        image=resize_first_stage1.out('IMAGE'),
    )
    empty_audio = node(
        wf,
        "LTXVEmptyLatentAudio",
        "1010",
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
        width=stage1_image_size.out('WIDTH'),
        height=stage1_image_size.out('HEIGHT'),
        length=frames.out('VALUE'),
    )

    first_guide = _add_guide(wf, "115", preprocess_first_stage1, empty_video.out('LATENT'), conditioning, checkpoint, frame_idx=0)
    last_guide = _add_guide(wf, "111", preprocess_last_stage1, first_guide.out('LATENT'), first_guide, checkpoint, frame_idx=-1)
    stage1_concat = node(
        wf,
        "LTXVConcatAVLatent",
        "119",
        _outputs=("latent",),
        audio_latent=empty_audio.out('AUDIO_LATENT'),
        video_latent=last_guide.out('LATENT'),
    )
    stage1 = _sample(
        wf,
        "120",
        patched_model.out('MODEL'),
        last_guide,
        stage1_concat.out('LATENT'),
        seed_first.out('NOISE'),
        sampler_name="euler_ancestral_cfg_pp",
        sigmas="1.0, 0.99375, 0.9875, 0.98125, 0.975, 0.909375, 0.725, 0.421875, 0.0",
    )
    separated_stage1 = node(
        wf,
        "LTXVSeparateAVLatent",
        "121",
        _outputs=("video_latent", "audio_latent"),
        av_latent=stage1.out('DENOISED_OUTPUT'),
    )
    upscaled_stage1 = node(
        wf,
        "LTXVLatentUpsampler",
        "1845",
        _outputs=("latent",),
        samples=separated_stage1.out('VIDEO_LATENT'),
        upscale_model=spatial_upscaler.out('LATENT_UPSCALE_MODEL'),
        vae=checkpoint.out('VAE'),
    )
    stage_boundary = node(
        wf,
        "VRAM_Debug",
        "1846",
        _outputs=("any_output", "image_pass", "model_pass", "freemem_before", "freemem_after"),
        any_input=upscaled_stage1.out('LATENT'),
        empty_cache=True,
        gc_collect=True,
        unload_all_models=True,
    )
    cropped_stage1 = node(
        wf,
        "LTXVCropGuides",
        "106",
        _outputs=("positive", "negative", "latent"),
        latent=stage_boundary.out('ANY_OUTPUT'),
        negative=last_guide.out('NEGATIVE'),
        positive=last_guide.out('POSITIVE'),
    )

    first_refine_guide = _add_guide(wf, "2150", preprocess_first, cropped_stage1.out('LATENT'), cropped_stage1, checkpoint, frame_idx=0)
    last_refine_guide = _add_guide(wf, "2152", preprocess_last, first_refine_guide.out('LATENT'), first_refine_guide, checkpoint, frame_idx=-1)
    stage2_concat = node(
        wf,
        "LTXVConcatAVLatent",
        "4969",
        _outputs=("latent",),
        audio_latent=separated_stage1.out('AUDIO_LATENT'),
        video_latent=last_refine_guide.out('LATENT'),
    )
    stage2 = _sample(
        wf,
        "4971",
        patched_model.out('MODEL'),
        last_refine_guide,
        stage2_concat.out('LATENT'),
        seed_last.out('NOISE'),
        sampler_name="euler_cfg_pp",
        sigmas="0.909375, 0.725, 0.421875, 0.0",
    )
    separated_stage2 = node(
        wf,
        "LTXVSeparateAVLatent",
        "4973",
        _outputs=("video_latent", "audio_latent"),
        av_latent=stage2.out('DENOISED_OUTPUT'),
    )
    cropped_stage2 = node(
        wf,
        "LTXVCropGuides",
        "4974",
        _outputs=("positive", "negative", "latent"),
        latent=separated_stage2.out('VIDEO_LATENT'),
        negative=last_refine_guide.out('NEGATIVE'),
        positive=last_refine_guide.out('POSITIVE'),
    )
    # ════ DECODE ════
    decoded_audio = node(
        wf,
        "LTXVAudioVAEDecode",
        "4848",
        _outputs=("audio",),
        audio_vae=audio_vae.out('AUDIO_VAE'),
        samples=separated_stage2.out('AUDIO_LATENT'),
    )
    decoded_video = node(
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
        latents=cropped_stage2.out('LATENT'),
        vae=checkpoint.out('VAE'),
    )
    # ════ OUTPUT ════
    video = node(
        wf,
        "CreateVideo",
        "4849",
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
        output_node='4852',
        output_type='SaveVideo',
        name='video',
        mime_type='video/mp4',
        expected_cardinality='one',
        source_path=__file__,
    )

def _add_guide(wf, node_id, image_node, latent, conditioning_node, checkpoint, *, frame_idx: int):
    return node(
        wf,
        "LTXVAddGuide",
        node_id,
        _outputs=("positive", "negative", "latent"),
        frame_idx=frame_idx,
        strength=1.0,
        image=image_node.out('IMAGE'),
        latent=latent,
        negative=conditioning_node.out('NEGATIVE'),
        positive=conditioning_node.out('POSITIVE'),
        vae=checkpoint.out('VAE'),
    )

def _sample(wf, node_id, model, guides, latent, noise, *, sampler_name: str, sigmas: str):
    guider = node(
        wf,
        "CFGGuider",
        f"{node_id}_guider",
        _outputs=("guider",),
        cfg=1,
        model=model,
        negative=guides.out('NEGATIVE'),
        positive=guides.out('POSITIVE'),
    )
    sampler = node(wf, "KSamplerSelect", f"{node_id}_sampler", _outputs=("sampler",), sampler_name=sampler_name)
    sigmas_node = node(wf, "ManualSigmas", f"{node_id}_sigmas", _outputs=("sigmas",), sigmas=sigmas)
    return node(
        wf,
        "SamplerCustomAdvanced",
        node_id,
        _outputs=("output", "denoised_output"),
        guider=guider.out('GUIDER'),
        latent_image=latent,
        noise=noise,
        sampler=sampler.out('SAMPLER'),
        sigmas=sigmas_node.out('SIGMAS'),
    )
