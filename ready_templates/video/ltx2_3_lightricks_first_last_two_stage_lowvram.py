# vibecomfy: generated
# For hand-editing, run: python -m vibecomfy.cli copy-to-recipe <id>
"""Auto-generated ready_template — use python -m vibecomfy.cli copy-to-recipe <id> for hand-editing."""
from __future__ import annotations

from vibecomfy.templates import InputSpec, ModelAsset, ReadyMetadata, new_workflow
from vibecomfy.nodes.core import CFGGuider, CLIPTextEncode, CreateVideo, EmptyLTXVLatentVideo, GetImageSize, KSamplerSelect, LTXAVTextEncoderLoader, LTXVAddGuide, LTXVAudioVAEDecode, LTXVAudioVAELoader, LTXVConcatAVLatent, LTXVConditioning, LTXVCropGuides, LTXVLatentUpsampler, LTXVPreprocess, LTXVSeparateAVLatent, LatentUpscaleModelLoader, LoadImage, ManualSigmas, RandomNoise, ResizeImageMaskNode, SamplerCustomAdvanced, SaveVideo
from vibecomfy.nodes.kjnodes import LTX2MemoryEfficientSageAttentionPatch, VRAM_Debug
from vibecomfy.nodes.ltxvideo import LTXVTiledVAEDecode, LowVRAMCheckpointLoader


CENTER = 'center'
CKPT_NAME = 'ltx-2.3-22b-distilled-fp8.safetensors'
DEFAULT_FPS = 16.0
DEFAULT_FRAMES = 81
DEFAULT_PROMPT = 'A cinematic first-last frame transition.'
DEFAULT_SEED = 42
GUIDE_STRENGTH = 1
NEAREST_EXACT = 'nearest-exact'
SCALE_DIMENSIONS = 'scale dimensions'
SPATIAL_UPSCALER_NAME = 'ltx-2.3-spatial-upscaler-x2-1.1.safetensors'
TEXT_ENCODER_NAME = 'gemma_3_12B_it_fp4_mixed.safetensors'


MODELS = {
    'checkpoint': ModelAsset(url='https://huggingface.co/Lightricks/LTX-2.3-fp8/resolve/main/ltx-2.3-22b-distilled-fp8.safetensors', sha256='d9646b6f2d5c42d337b23671634c43bfeece6989644f51b4a3aa088465ccd3b2', hf_revision='1d756cd27fa11c0896c4dfee093cd1bf36c7f7a1', size_bytes=29531884062, subdir='checkpoints'),
    'text_encoder': ModelAsset(url='https://huggingface.co/Comfy-Org/ltx-2/resolve/main/split_files/text_encoders/gemma_3_12B_it_fp4_mixed.safetensors', sha256='aaca463d11e6d8d2a4bdb0d6299214c15ef78a3f73e0ef8113d5a9d0219b3f6d', hf_revision='bd5f9c87fcb0360ae7112f9784562670894d9492', size_bytes=9447702218, subdir='text_encoders'),
    'upscale_model': ModelAsset(url='https://huggingface.co/Lightricks/LTX-2.3/resolve/main/ltx-2.3-spatial-upscaler-x2-1.1.safetensors', sha256='5f416311fa8172b65af67530758964708d29a317b830d689a51143b7f91913ed', hf_revision='76730e634e70a28f4e8d51f5e29c08e40e2d8e74', size_bytes=995743560, subdir='latent_upscale_models'),
}


PUBLIC_INPUT_METADATA = {
    'image': InputSpec(node='1', field='image', default='', type='IMAGE', required=True, aliases=('input_image',), media_semantics='image'),
    'seed': InputSpec(node='3', field='noise_seed', default=DEFAULT_SEED, type='INT'),
    'frames': InputSpec(node='27', field='length', default=DEFAULT_FRAMES, type='INT'),
    'fps': InputSpec(node='46', field='fps', default=DEFAULT_FPS, type='FLOAT'),
    'prompt': InputSpec(node='13', field='text', default='blurry, distorted, low quality', type='STRING', required=True, media_semantics='text'),
}

READY_METADATA = ReadyMetadata.build(
    capability='first_last_frame_video',
    inputs=PUBLIC_INPUT_METADATA,
    models=MODELS,
    requirements={'custom_nodes': ['ComfyUI-KJNodes', 'ComfyUI-LTXVideo'], 'custom_node_refs': [{'slug': 'ComfyUI-KJNodes', 'source': 'git', 'version': 'unknown', 'commit': 'b7646ad70a7daa7aeb919ca542274758d26ba2df', 'url': 'https://github.com/kijai/ComfyUI-KJNodes.git'}, {'slug': 'ComfyUI-LTXVideo', 'source': 'git', 'version': 'unknown', 'commit': '229437c6b65796d6a7a63ae34be2bd5ba31fa543', 'url': 'https://github.com/Lightricks/ComfyUI-LTXVideo.git'}]},
    custom_node_packs={'ComfyUI-KJNodes': {'commit': 'b7646ad70a7daa7aeb919ca542274758d26ba2df', 'url': 'https://github.com/kijai/ComfyUI-KJNodes.git', 'class_schema_sha256': '1beaf129c8fa26175d89a28f9ca10d08b5ac27c8fc9bff920263fcbba17cb691', 'classes_used': ['GetImageSize', 'LTXVAddGuide'], 'pip_packages': ['matplotlib'], 'status': 'pinned'}, 'ComfyUI-LTXVideo': {'commit': '229437c6b65796d6a7a63ae34be2bd5ba31fa543', 'url': 'https://github.com/Lightricks/ComfyUI-LTXVideo.git', 'class_schema_sha256': '82e0b1f31509a969cf441c45e2517d0cd93f31b5390cc16f4a0ffa244421f39e', 'classes_used': ['EmptyLTXVLatentVideo', 'LTXAVTextEncoderLoader', 'LTXVAudioVAEDecode', 'LTXVAudioVAELoader', 'LTXVConcatAVLatent', 'LTXVConditioning', 'LTXVCropGuides', 'LTXVEmptyLatentAudio', 'LTXVPreprocess', 'LTXVSeparateAVLatent', 'LatentUpscaleModelLoader'], 'pip_packages': [], 'status': 'pinned'}},
    source_path='ready_templates/video/ltx2_3_lightricks_first_last_two_stage_lowvram.py',
    source_id='video/ltx2_3_lightricks_first_last_two_stage_lowvram',
    source_type='ready_template',
    source_workflow_path='ready_templates/video/ltx2_3_lightricks_first_last_two_stage_lowvram.py',
    output_mode='ready_template',
    ready_id='video/ltx2_3_lightricks_first_last_two_stage_lowvram',
    smoke_resolution='256x256x5_frames',
    approach='two-stage first/last-frame route using LowVRAMCheckpointLoader',
    runtime_note="Stage 1 uses Wan2GP's half-resolution long sigma schedule; the latent is spatially upsampled before stage 2 reapplies first/last guides and uses the Wan2GP refine sigma schedule.",
    discord_signal='Use dedicated distilled fp8 + low-VRAM loaders on 24GB GPUs.',
    runtime_packages=[{'name': 'sageattention', 'reason': 'Required by LTX2MemoryEfficientSageAttentionPatch for the two-stage low-VRAM LTX route.', 'source': 'SageAttention-ada'}],
    ltx_best_practices=['Use LowVRAMCheckpointLoader for 4090 viability.', 'Use the dedicated distilled fp8 checkpoint rather than the dev checkpoint plus LoRA when possible.', "Preserve Wan2GP's two-stage sigma structure for parity checks."],
    comfy_configuration={'memory_profile': 3, 'fp8_e4m3fn_text_enc': True},
    provenance={'source_path': 'ready_templates/video/ltx2_3_lightricks_first_last_two_stage_lowvram.py', 'source_id': 'video/ltx2_3_lightricks_first_last_two_stage_lowvram', 'source_type': 'ready_template', 'source_workflow_path': 'ready_templates/video/ltx2_3_lightricks_first_last_two_stage_lowvram.py', 'output_mode': 'ready_template', 'ready_id': 'video/ltx2_3_lightricks_first_last_two_stage_lowvram'},
)

def build() -> VibeWorkflow:
    """Build the workflow (auto-generated)."""
    wf = new_workflow(READY_METADATA, source_path=__file__)

    # Inputs
    image, _ = LoadImage(_id='1', image='example_start.png')
    image_2, _ = LoadImage(_id='2', image='example_end.png')
    randomnoise = RandomNoise(_id='3', noise_seed=DEFAULT_SEED)
    randomnoise_2 = RandomNoise(_id='4', noise_seed=DEFAULT_SEED)

    ltxavtextencoderloader = LTXAVTextEncoderLoader(
        _id='5',
        text_encoder=TEXT_ENCODER_NAME,
        ckpt_name=CKPT_NAME,
        device='default',
    )

    ltxvaudiovaeloader = LTXVAudioVAELoader(_id='6', ckpt_name=CKPT_NAME)
    model, _, vae = LowVRAMCheckpointLoader(_id='7', ckpt_name=CKPT_NAME)

    latentupscalemodelloader = LatentUpscaleModelLoader(
        _id='8',
        model_name=SPATIAL_UPSCALER_NAME,
    )

    # Sampling
    ksamplerselect = KSamplerSelect(_id='9', sampler_name='euler_ancestral_cfg_pp')

    manualsigmas = ManualSigmas(
        _id='10',
        sigmas='1.0, 0.99375, 0.9875, 0.98125, 0.975, 0.909375, 0.725, 0.421875, 0.0',
    )

    ksamplerselect_2 = KSamplerSelect(_id='11', sampler_name='euler_cfg_pp')
    manualsigmas_2 = ManualSigmas(_id='12', sigmas='0.909375, 0.725, 0.421875, 0.0')

    # Conditioning
    cliptextencode = CLIPTextEncode(
        _id='13',
        text='blurry, distorted, low quality',
        clip=ltxavtextencoderloader,
    )

    resizeimagemasknode = ResizeImageMaskNode(
        _id='14',
        resize_type=SCALE_DIMENSIONS,
        scale_method=NEAREST_EXACT,
        input=image,
        **{'resize_type.crop': CENTER, 'resize_type.height': 480, 'resize_type.width': 832},
    )

    resizeimagemasknode_2 = ResizeImageMaskNode(
        _id='15',
        resize_type=SCALE_DIMENSIONS,
        scale_method=NEAREST_EXACT,
        input=image_2,
        **{'resize_type.crop': CENTER, 'resize_type.height': 480, 'resize_type.width': 832},
    )

    cliptextencode_2 = CLIPTextEncode(
        _id='16',
        text=DEFAULT_PROMPT,
        clip=ltxavtextencoderloader,
    )

    ltx2memoryefficientsageattentionpatch = LTX2MemoryEfficientSageAttentionPatch(
        _id='17',
        model=model,
    )

    resizeimagemasknode_3 = ResizeImageMaskNode(
        _id='19',
        resize_type=SCALE_DIMENSIONS,
        scale_method=NEAREST_EXACT,
        input=image,
        **{'resize_type.crop': CENTER, 'resize_type.height': 480, 'resize_type.width': 832},
    )

    resizeimagemasknode_4 = ResizeImageMaskNode(
        _id='20',
        resize_type=SCALE_DIMENSIONS,
        scale_method=NEAREST_EXACT,
        input=image_2,
        **{'resize_type.crop': CENTER, 'resize_type.height': 480, 'resize_type.width': 832},
    )

    ltxvpreprocess = LTXVPreprocess(
        _id='21',
        img_compression=25,
        image=resizeimagemasknode_2,
    )

    ltxvpreprocess_2 = LTXVPreprocess(
        _id='22',
        img_compression=25,
        image=resizeimagemasknode,
    )

    positive, negative = LTXVConditioning(
        _id='23',
        frame_rate=16.0,
        negative=cliptextencode,
        positive=cliptextencode_2,
    )

    width, height, _ = GetImageSize(_id='24', image=resizeimagemasknode_3)

    ltxvpreprocess_3 = LTXVPreprocess(
        _id='25',
        img_compression=25,
        image=resizeimagemasknode_4,
    )

    ltxvpreprocess_4 = LTXVPreprocess(
        _id='26',
        img_compression=25,
        image=resizeimagemasknode_3,
    )

    emptyltxvlatentvideo = EmptyLTXVLatentVideo(
        _id='27',
        length=DEFAULT_FRAMES,
        width=width,
        height=height,
    )

    positive_2, negative_2, latent = LTXVAddGuide(
        _id='28',
        image=ltxvpreprocess_4,
        latent=emptyltxvlatentvideo,
        negative=negative,
        positive=positive,
        vae=vae,
    )

    positive_3, negative_3, latent_2 = LTXVAddGuide(
        _id='29',
        frame_idx=-1,
        image=ltxvpreprocess_3,
        latent=latent,
        negative=negative_2,
        positive=positive_2,
        vae=vae,
    )

    ltxvconcatavlatent = LTXVConcatAVLatent(_id='30', video_latent=latent_2)

    cfgguider = CFGGuider(
        _id='31',
        cfg=GUIDE_STRENGTH,
        model=ltx2memoryefficientsageattentionpatch,
        negative=negative_3,
        positive=positive_3,
    )

    _, denoised_output = SamplerCustomAdvanced(
        _id='32',
        guider=cfgguider,
        latent_image=ltxvconcatavlatent,
        noise=randomnoise,
        sampler=ksamplerselect,
        sigmas=manualsigmas,
    )

    video_latent, _ = LTXVSeparateAVLatent(_id='33', av_latent=denoised_output)

    ltxvlatentupsampler = LTXVLatentUpsampler(
        _id='34',
        samples=video_latent,
        upscale_model=latentupscalemodelloader,
        vae=vae,
    )

    any_output, _, _, _, _ = VRAM_Debug(
        _id='35',
        unload_all_models=True,
        any_input=ltxvlatentupsampler,
    )

    positive_4, negative_4, latent_3 = LTXVCropGuides(
        _id='36',
        latent=any_output,
        negative=negative_3,
        positive=positive_3,
    )

    positive_5, negative_5, latent_4 = LTXVAddGuide(
        _id='37',
        image=ltxvpreprocess_2,
        latent=latent_3,
        negative=negative_4,
        positive=positive_4,
        vae=vae,
    )

    positive_6, negative_6, latent_5 = LTXVAddGuide(
        _id='38',
        frame_idx=-1,
        image=ltxvpreprocess,
        latent=latent_4,
        negative=negative_5,
        positive=positive_5,
        vae=vae,
    )

    ltxvconcatavlatent_2 = LTXVConcatAVLatent(_id='39', video_latent=latent_5)

    cfgguider_2 = CFGGuider(
        _id='40',
        cfg=GUIDE_STRENGTH,
        model=ltx2memoryefficientsageattentionpatch,
        negative=negative_6,
        positive=positive_6,
    )

    _, denoised_output_2 = SamplerCustomAdvanced(
        _id='41',
        guider=cfgguider_2,
        latent_image=ltxvconcatavlatent_2,
        noise=randomnoise_2,
        sampler=ksamplerselect_2,
        sigmas=manualsigmas_2,
    )

    video_latent_2, audio_latent_2 = LTXVSeparateAVLatent(
        _id='42',
        av_latent=denoised_output_2,
    )

    ltxvaudiovaedecode = LTXVAudioVAEDecode(
        _id='43',
        audio_vae=ltxvaudiovaeloader,
        samples=audio_latent_2,
    )

    _, _, latent_6 = LTXVCropGuides(
        _id='44',
        latent=video_latent_2,
        negative=negative_6,
        positive=positive_6,
    )

    ltxvtiledvaedecode = LTXVTiledVAEDecode(
        _id='45',
        horizontal_tiles=2,
        vertical_tiles=2,
        overlap=6,
        latents=latent_6,
        vae=vae,
    )

    createvideo = CreateVideo(
        _id='46',
        fps=DEFAULT_FPS,
        audio=ltxvaudiovaedecode,
        images=ltxvtiledvaedecode,
    )

    # Outputs
    savevideo = SaveVideo(_id='47', filename_prefix='output', video=createvideo)

    return wf.finalize(PUBLIC_INPUT_METADATA, output_node=savevideo, output_type='SaveVideo', name='video', artifact_kind='video', mime_type='video/mp4', expected_cardinality='one', filename_prefix='output')

