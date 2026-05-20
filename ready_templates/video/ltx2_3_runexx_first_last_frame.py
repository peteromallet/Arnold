# vibecomfy: manual
# Edits will be overwritten on regeneration. Add a `# vibecomfy: manual`
# marker on the first line if hand-editing is required.
"""Auto-generated ready_template — see tools/convert_ready_templates.py."""
from __future__ import annotations

from vibecomfy.workflow import VibeWorkflow
from vibecomfy.templates import InputSpec, ModelAsset, ReadyMetadata, finalize, new_workflow, node

OUTPUT_PREFIX = "reigh_vibecomfy_ltx_first_last"


def _get_node_width(wf, _id, **overrides):
    kwargs = dict(widget_0='width')
    kwargs.update(overrides)
    return node(wf, 'GetNode', _id, **kwargs)
def _get_node_height(wf, _id, **overrides):
    kwargs = dict(widget_0='height')
    kwargs.update(overrides)
    return node(wf, 'GetNode', _id, **kwargs)
def _get_node_fps(wf, _id, **overrides):
    kwargs = dict(widget_0='fps')
    kwargs.update(overrides)
    return node(wf, 'GetNode', _id, **kwargs)
def _get_node_vae(wf, _id, **overrides):
    kwargs = dict(widget_0='vae')
    kwargs.update(overrides)
    return node(wf, 'GetNode', _id, **kwargs)
def _get_node_vae_audio(wf, _id, **overrides):
    kwargs = dict(widget_0='vae_audio')
    kwargs.update(overrides)
    return node(wf, 'GetNode', _id, **kwargs)
def _get_node_clip(wf, _id, **overrides):
    kwargs = dict(widget_0='clip')
    kwargs.update(overrides)
    return node(wf, 'GetNode', _id, **kwargs)
def _get_node_firstframe(wf, _id, **overrides):
    kwargs = dict(widget_0='firstframe')
    kwargs.update(overrides)
    return node(wf, 'GetNode', _id, **kwargs)
def _get_node_negative(wf, _id, **overrides):
    kwargs = dict(widget_0='negative')
    kwargs.update(overrides)
    return node(wf, 'GetNode', _id, **kwargs)
def _get_node_model_nag(wf, _id, **overrides):
    kwargs = dict(widget_0='model_nag')
    kwargs.update(overrides)
    return node(wf, 'GetNode', _id, **kwargs)
def _get_node_positive(wf, _id, **overrides):
    kwargs = dict(widget_0='positive')
    kwargs.update(overrides)
    return node(wf, 'GetNode', _id, **kwargs)
MODELS = {
    'gemma_3_12b_it_fp4_mixed': ModelAsset(
        filename='gemma_3_12B_it_fp4_mixed.safetensors',
        url='https://huggingface.co/Comfy-Org/ltx-2/resolve/main/split_files/text_encoders/gemma_3_12B_it_fp4_mixed.safetensors',
        subdir='text_encoders',
        sha256='aaca463d11e6d8d2a4bdb0d6299214c15ef78a3f73e0ef8113d5a9d0219b3f6d',
        hf_revision='bd5f9c87fcb0360ae7112f9784562670894d9492',
        size_bytes=9447702218,
    ),
    'ltx_2_3_text_projection_bf16': ModelAsset(
        filename='ltx-2.3_text_projection_bf16.safetensors',
        url='https://huggingface.co/Kijai/LTX2.3_comfy/resolve/main/text_encoders/ltx-2.3_text_projection_bf16.safetensors',
        subdir='text_encoders',
        hf_revision='main',
    ),
    'ltx23_video_vae_bf16': ModelAsset(
        filename='LTX23_video_vae_bf16.safetensors',
        url='https://huggingface.co/Kijai/LTX2.3_comfy/resolve/main/vae/LTX23_video_vae_bf16.safetensors',
        subdir='vae',
        hf_revision='main',
    ),
    'ltx23_audio_vae_bf16': ModelAsset(
        filename='LTX23_audio_vae_bf16.safetensors',
        url='https://huggingface.co/Kijai/LTX2.3_comfy/resolve/main/vae/LTX23_audio_vae_bf16.safetensors',
        subdir='checkpoints',
        hf_revision='main',
    ),
    'taeltx2_3': ModelAsset(
        filename='taeltx2_3.safetensors',
        url='https://huggingface.co/Kijai/LTX2.3_comfy/resolve/main/vae/taeltx2_3.safetensors',
        subdir='vae',
        hf_revision='main',
    ),
    'ltx_2_3_22b_distilled_1_1_transformer_only': ModelAsset(
        filename='ltx-2.3-22b-distilled-1.1_transformer_only_fp8_scaled.safetensors',
        url='https://huggingface.co/Kijai/LTX2.3_comfy/resolve/main/diffusion_models/ltx-2.3-22b-distilled-1.1_transformer_only_fp8_scaled.safetensors',
        subdir='diffusion_models',
        hf_revision='main',
    ),
    'ltx_2_3_22b_distilled_1_1_lora_dynamic_fro': ModelAsset(
        filename='LTX\\v2\\ltx-2.3-22b-distilled-1.1_lora-dynamic_fro09_avg_rank_111_bf16.safetensors',
        url='https://huggingface.co/Kijai/LTX2.3_comfy/resolve/main/loras/ltx-2.3-22b-distilled-1.1_lora-dynamic_fro09_avg_rank_111_bf16.safetensors',
        subdir='loras',
        hf_revision='main',
    ),
    'ltx_2_3_spatial_upscaler_x2_1_1': ModelAsset(
        filename='ltx-2.3-spatial-upscaler-x2-1.1.safetensors',
        url='https://huggingface.co/Lightricks/LTX-2.3/resolve/main/ltx-2.3-spatial-upscaler-x2-1.1.safetensors',
        subdir='latent_upscale_models',
        sha256='5f416311fa8172b65af67530758964708d29a317b830d689a51143b7f91913ed',
        hf_revision='76730e634e70a28f4e8d51f5e29c08e40e2d8e74',
        size_bytes=995743560,
    ),
}

PUBLIC_INPUTS = {
    'start_image': InputSpec(node='45', field='image', default='image (6).png', type='STRING', description='Starting image.', media_semantics='image'),
    'end_image': InputSpec(node='47', field='image', default='0 (13).webp', type='STRING', description='Ending image.', media_semantics='image'),
    'first_image': InputSpec(node='45', field='image', default='image (6).png', type='STRING', description='First image.'),
    'last_image': InputSpec(node='47', field='image', default='0 (13).webp', type='STRING', description='Last image.'),
    'prompt': InputSpec(node='2103', field='value', default="wf.nodes['2103'].inputs.get('value', '')", type='STRING', description='Text prompt.', media_semantics='text'),
    'negative_prompt': InputSpec(node='11', field='text', default="wf.nodes['11'].inputs.get('text', '')", type='STRING', description='Negative text prompt.', media_semantics='text'),
    'seed': InputSpec(node='15', field='noise_seed', default=42, type='STRING', description='Random seed.'),
    'seed_first': InputSpec(node='15', field='noise_seed', default=42, type='STRING', description='Seed first.'),
    'seed_last': InputSpec(node='14', field='noise_seed', default=43, type='STRING', description='Seed last.'),
    'width': InputSpec(node='2080', field='value', default=1280, type='STRING', description='Output width.'),
    'height': InputSpec(node='2079', field='value', default=720, type='STRING', description='Output height.'),
    'output_fps': InputSpec(node='2076', field='value', default=24, type='STRING', aliases=('fps',), description='Output playback frame rate.'),
    'fps_int': InputSpec(node='2076', field='value', default=24, type='STRING', description='Fps int.'),
    'first_frame_strength': InputSpec(node='2110', field='value', default=1.0, type='STRING', description='First frame strength.'),
    'last_frame_strength': InputSpec(node='2108', field='value', default=1.0, type='STRING', description='Last frame strength.'),
    'first_strength': InputSpec(node='2110', field='value', default=1.0, type='STRING', description='First strength.'),
    'last_strength': InputSpec(node='2108', field='value', default=1.0, type='STRING', description='Last strength.'),
    'use_lora': InputSpec(node='2082', field='value', default=True, type='BOOLEAN', description='Lightning LoRA branch toggle.'),
    'length': InputSpec(node='2078', field='value', default=81, type='STRING', aliases=('frames',), description='Number of output frames.'),
}

READY_METADATA = ReadyMetadata.build(
    template_id='ltx2_3_runexx_first_last_frame',
    capability='first_last_frame_video',
    inputs=PUBLIC_INPUTS,
    models=MODELS,
    output_prefix='',
    requirements={'custom_nodes': ['ComfyUI-KJNodes', 'ComfyUI-LTXVideo', 'ComfyUI-VideoHelperSuite', 'rgthree-comfy'], 'custom_node_refs': [{'slug': 'ComfyUI-KJNodes', 'source': 'git', 'commit': 'b7646ad70a7daa7aeb919ca542274758d26ba2df', 'url': 'https://github.com/kijai/ComfyUI-KJNodes.git'}, {'slug': 'ComfyUI-LTXVideo', 'source': 'git',
                       'commit': '229437c6b65796d6a7a63ae34be2bd5ba31fa543', 'url': 'https://github.com/Lightricks/ComfyUI-LTXVideo.git'}, {'slug': 'ComfyUI-VideoHelperSuite', 'source': 'git',
                       'commit': '4ee72c065db22c9d96c2427954dc69e7b908444b', 'url': 'https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite.git'}, {'slug': 'rgthree-comfy', 'source': 'git',
                       'commit': '738105af5fb14e96fbecaf406dc356e284797e8c', 'url': 'https://github.com/rgthree/rgthree-comfy.git'}]},
    provenance={'approach': 'first/last-frame image anchors', 'source_role': 'manual_ready_python_template', 'source_workflow': 'workflow_corpus/custom_nodes/ltxvideo/runexx/LTX-2.3_FLF2V_First_Last_Frame.json', 'smoke_resolution': '256x256x5_frames'},
    coverage_tier='required',
    runtime_packages=[{'name': 'sageattention', 'reason': 'Required by PathchSageAttentionKJ auto mode for 4090-speed LTX Runexx validation.', 'source': 'SageAttention-ada'}],
    ltx_best_practices=['Use the official Lightricks workflows as runtime gates where possible.', 'Patch smoke runs to fp8/fp4 model assets, tiny frame counts, and low-VRAM loaders.', 'Bypass latent spatial upscalers in smoke runs until HiddenSwitch Comfy exposes model_mmap_residency for LatentUpscaleModelManageable.', 'Keep community audio, lip-sync, and long-form workflows as ready templates until their custom node packs and service credentials are declared.'],
    comfy_configuration={'memory_profile': 3, 'fp8_e4m3fn_text_enc': True},
    vibecomfy_version='0.1.0',
    comfy_core={'version': '0.18.2', 'tested_at': '2026-05-20T09:19:32.302139+00:00', 'commit': 'f7b38d2eb97207cd834bcc3eb2e8b1d447b96c68', 'status': 'discovered'},
)

READY_METADATA["unbound_inputs"].update({'end_image': '47.image', 'first_frame_strength': '2110.value', 'first_image': '45.image', 'first_strength': '2110.value', 'fps': '2076.value', 'fps_int': '2076.value', 'frames': '2078.value', 'height': '2079.value', 'last_frame_strength': '2108.value', 'last_image': '47.image', 'last_strength': '2108.value', 'negative': '11.text', 'negative_prompt': '11.text', 'prompt': '2103.value', 'seed': '15.noise_seed', 'seed_first': '15.noise_seed', 'seed_last': '14.noise_seed', 'start_image': '45.image', 'width': '2080.value'})

def build() -> VibeWorkflow:
    """Build the workflow (auto-generated)."""
    wf = new_workflow(READY_METADATA, source_path=__file__)

    # ════ SAMPLING ════
    sampler_kind_1 = node(wf, 'KSamplerSelect', '1',
        sampler_name='euler_ancestral_cfg_pp',
    )
    sampler_kind_2 = node(wf, 'KSamplerSelect', '4',
        sampler_name='euler_cfg_pp',
    )
    sigmas_5 = node(wf, 'ManualSigmas', '5',
        sigmas='0.909375, 0.725, 0.421875, 0.0',
    )
    noise_14 = node(wf, 'RandomNoise', '14',
        noise_seed=PUBLIC_INPUTS['seed_last'].default,
        control_after_generate='fixed',
    )
    noise_2 = node(wf, 'RandomNoise', '15',
        noise_seed=PUBLIC_INPUTS['seed_first'].default,
        control_after_generate='fixed',
    )
    # ════ INPUTS ════
    input_image_45 = node(wf, 'LoadImage', '45',
        image=PUBLIC_INPUTS['first_image'].default,
)
    input_image_2 = node(wf, 'LoadImage', '47',
        image=PUBLIC_INPUTS['last_image'].default,
)
    get_node_70 = _get_node_width(wf, '70', )
    getnode_2 = _get_node_height(wf, '71', )
    getnode_3 = _get_node_fps(wf, '91', )
    getnode_4 = _get_node_fps(wf, '93', )
    getnode_5 = _get_node_vae(wf, '111', )
    getnode_6 = _get_node_vae_audio(wf, '117', )
    getnode_7 = _get_node_vae(wf, '120', )
    getnode_8 = node(wf, 'GetNode', '122',
        widget_0='model',
    )
    getnode_9 = _get_node_clip(wf, '124', )
    getnode_10 = node(wf, 'GetNode', '127',
        widget_0='frames',
    )
    getnode_11 = _get_node_width(wf, '128', )
    getnode_12 = _get_node_height(wf, '129', )
    getnode_13 = _get_node_firstframe(wf, '132', )
    getnode_14 = node(wf, 'GetNode', '133',
        widget_0='upscale_model',
    )
    getnode_15 = _get_node_fps(wf, '137', )
    getnode_16 = _get_node_vae(wf, '147', )
    getnode_17 = _get_node_vae_audio(wf, '148', )
    # ════ LOADERS ════
    vaeloaderkj = node(wf, 'LTXVAudioVAELoader', '175',
        ckpt_name=MODELS['ltx23_audio_vae_bf16'].filename,
    )
    vae_180 = node(wf, 'VAELoader', '180',
        vae_name=MODELS['taeltx2_3'].filename,
    )
    vae_2 = node(wf, 'VAELoader', '181',
        vae_name=MODELS['ltx23_video_vae_bf16'].filename,
    )
    # ════ LATENT ════
    latent_upscale_model_loader_182 = node(wf, 'LatentUpscaleModelLoader', '182',
        model_name=MODELS['ltx_2_3_spatial_upscaler_x2_1_1'].filename,
    )
    base_diffusion_model = node(wf, 'UNETLoader', '187',
        unet_name=MODELS['ltx_2_3_22b_distilled_1_1_transformer_only'].filename,
        weight_dtype='default',
    )
    text_encoder = node(wf, 'DualCLIPLoader', '190',
        clip_name1=MODELS['gemma_3_12b_it_fp4_mixed'].filename,
        clip_name2=MODELS['ltx_2_3_text_projection_bf16'].filename,
        type='ltxv',
        device='default',
    )
    getnode_18 = node(wf, 'GetNode', '193',
        widget_0='vae_tiny',
    )
    getnode_19 = _get_node_negative(wf, '196', )
    getnode_20 = _get_node_model_nag(wf, '200', )
    getnode_21 = _get_node_model_nag(wf, '201', )
    getnode_22 = node(wf, 'GetNode', '203',
        widget_0='final_video',
    )
    getnode_23 = node(wf, 'GetNode', '204',
        widget_0='final_audio',
    )
    getnode_24 = _get_node_positive(wf, '205', )
    getnode_25 = _get_node_negative(wf, '206', )
    getnode_26 = _get_node_negative(wf, '207', )
    getnode_27 = _get_node_positive(wf, '208', )
    sigmas_2 = node(wf, 'ManualSigmas', '215',
        sigmas='1.0, 0.99375, 0.9875, 0.98125, 0.975, 0.909375, 0.725, 0.421875, 0.0',
    )
    sigmas_3 = node(wf, 'ManualSigmas', '216',
        sigmas='0.909375, 0.725, 0.421875, 0.0',
    )
    getnode_28 = node(wf, 'GetNode', '219',
        widget_0='height_downscaled',
    )
    getnode_29 = node(wf, 'GetNode', '220',
        widget_0='width_downscaled',
    )
    getnode_30 = node(wf, 'GetNode', '224',
        widget_0='lastframe_resized',
    )
    getnode_31 = _get_node_firstframe(wf, '225', )
    getnode_32 = _get_node_clip(wf, '2067', )
    getnode_33 = node(wf, 'GetNode', '2068',
        widget_0='enhance_prompt',
    )
    param_float_2076 = node(wf, 'PrimitiveFloat', '2076', value=PUBLIC_INPUTS['fps_int'].default)
    param_int_2078 = node(wf, 'INTConstant', '2078',
        value=PUBLIC_INPUTS['length'].default,
    )
    param_height = node(wf, 'INTConstant', '2079',
        value=PUBLIC_INPUTS['height'].default,
    )
    param_width = node(wf, 'INTConstant', '2080',
        value=PUBLIC_INPUTS['width'].default,
    )
    use_lora = node(wf, 'PrimitiveBoolean', '2082', value=PUBLIC_INPUTS['use_lora'].default)
    primitive_string_multiline_2103 = node(wf, 'PrimitiveStringMultiline', '2103',
        value=PUBLIC_INPUTS['prompt'].default,
    )
    getnode_34 = node(wf, 'GetNode', '2106',
        widget_0='lastframe',
    )
    param_last_frame_strength = node(wf, 'PrimitiveFloat', '2108', value=PUBLIC_INPUTS['last_strength'].default)
    param_first_frame_strength = node(wf, 'PrimitiveFloat', '2110', value=PUBLIC_INPUTS['first_strength'].default)
    getnode_35 = node(wf, 'GetNode', '2114',
        widget_0='firstframe_strength',
    )
    getnode_36 = node(wf, 'GetNode', '2115',
        widget_0='lastframe_strength',
    )
    getnode_37 = _get_node_negative(wf, '2154', )
    getnode_38 = _get_node_vae(wf, '2155', )
    getnode_39 = _get_node_vae(wf, '2162', )
    getnode_40 = _get_node_positive(wf, '2163', )
    getnode_41 = node(wf, 'GetNode', '2166',
        widget_0='negative_guider',
    )
    getnode_42 = node(wf, 'GetNode', '2167',
        widget_0='positive_guider',
    )
    # Stage 1 (REFINE): NAG model (bypasses patch stack) + base conditioning
    # Stage 2 (FINISH): IC-LoRA model (full patch chain)   + guided conditioning
    cfg_guider_8 = node(wf, 'CFGGuider', '8',
        cfg=2.5,
        model=getnode_21.out(0),
        negative=getnode_25.out(0),
        positive=getnode_24.out(0),
    )
    # ════ TEXT CONDITIONING ════
    negative_prompt = node(wf, 'CLIPTextEncode', '11',
        text=PUBLIC_INPUTS['negative_prompt'].default,
        clip=getnode_9.out(0),
    )
    empty_video_latent = node(wf, 'EmptyLTXVLatentVideo', '32',
        batch_size=1,
        
        
        width=getnode_29.out(0),
        height=getnode_28.out(0),
        length=getnode_10.out(0),
    )
    cfg_guider_2 = node(wf, 'CFGGuider', '36',
        cfg=2.5,
        model=getnode_20.out(0),
        negative=getnode_26.out(0),
        positive=getnode_27.out(0),
    )
    # ════ OUTPUT ════
    video_output = node(wf, 'VHS_VideoCombine', '43',
        filename_prefix='reigh_vibecomfy_ltx_first_last',
        format='video/h264-mp4',
        frame_rate=getnode_15.out(0),
        images=getnode_22.out(0),
        loop_count=0,
        pingpong=False,
        save_output=True,
    )
    # ════ IMAGE PREP ════
    resized_image_44 = node(wf, 'ImageResizeKJv2', '44',
        
        upscale_method='nearest-exact',
        keep_proportion='crop',
        pad_color='0, 0, 0',
        crop_position='center',
        divisible_by=32,
        device='cpu',
        height=getnode_2.out(0),
        image=input_image_45.out('IMAGE'),
        width=get_node_70.out(0),
    )
    preprocessed_image_50 = node(wf, 'LTXVPreprocess', '50',
        img_compression=18,
        image=getnode_30.out(0),
    )
    simple_calculator_k_j_92 = node(wf, 'SimpleCalculatorKJ', '92',
        expression='a',
        a=getnode_3.out(0),
    )
    setnode_7 = node(wf, 'SetNode', '171',
        widget_0='upscale_model',
        LATENT_UPSCALE_MODEL=latent_upscale_model_loader_182.out(0),
    )
    setnode_8 = node(wf, 'SetNode', '172',
        widget_0='vae_audio',
        VAE=vaeloaderkj.out('AUDIO_VAE'),
    )
    setnode_9 = node(wf, 'SetNode', '173',
        widget_0='vae',
        VAE=vae_2.out('VAE'),
    )
    setnode_10 = node(wf, 'SetNode', '177',
        widget_0='vae_tiny',
        VAE=vae_180.out('VAE'),
    )
    # ════ MODEL PATCH STACK ════
    lora = node(wf, 'LoraLoaderModelOnly', '186',
        lora_name=MODELS['ltx_2_3_22b_distilled_1_1_lora_dynamic_fro'].filename,
        strength_model=0.6,
        model=base_diffusion_model.out('MODEL'),
    )
    setnode_11 = node(wf, 'SetNode', '188',
        widget_0='clip',
        CLIP=text_encoder.out('CLIP'),
    )
    setnode_17 = node(wf, 'SetNode', '2072',
        widget_0='height',
        INT=param_height.out('VALUE'),
    )
    setnode_18 = node(wf, 'SetNode', '2073',
        widget_0='width',
        INT=param_width.out('VALUE'),
    )
    setnode_19 = node(wf, 'SetNode', '2074',
        widget_0='fps',
        FLOAT=param_float_2076.out('FLOAT'),
    )
    simple_calculator_k_j_2 = node(wf, 'SimpleCalculatorKJ', '2077',
        expression='a',
        a=param_int_2078.out('VALUE'),
        b=param_float_2076.out('FLOAT'),
    )
    setnode_21 = node(wf, 'SetNode', '2081',
        widget_0='enhance_prompt',
        BOOLEAN=use_lora.out('BOOLEAN'),
    )
    preprocessed_image_2 = node(wf, 'LTXVPreprocess', '2084',
        img_compression=18,
        image=getnode_31.out(0),
    )
    setnode_22 = node(wf, 'SetNode', '2112',
        widget_0='firstframe_strength',
        FLOAT=param_first_frame_strength.out('FLOAT'),
    )
    setnode_23 = node(wf, 'SetNode', '2113',
        widget_0='lastframe_strength',
        FLOAT=param_last_frame_strength.out('FLOAT'),
    )
    empty_audio_latent = node(wf, 'LTXVEmptyLatentAudio', '9',
        
        batch_size=1,
        audio_vae=getnode_6.out(0),
        frame_rate=simple_calculator_k_j_92.out(1),
        frames_number=getnode_10.out(0),
    )
    positive_prompt = node(wf, 'CLIPTextEncode', '16',
        text=primitive_string_multiline_2103.out(0),
        clip=getnode_9.out(0),
    )
    wf.replace_edge('16.text', primitive_string_multiline_2103.out(0))
    wf.remove_node('2070')
    wf.remove_node('2102')
    image_scale_by_26 = node(wf, 'ImageScaleBy', '26',
        upscale_method='lanczos',
        scale_by=0.5,
        image=resized_image_44.out('IMAGE'),
    )
    imageresizekjv2_2 = node(wf, 'ImageResizeKJv2', '48',
        
        upscale_method='nearest-exact',
        keep_proportion='crop',
        pad_color='0, 0, 0',
        crop_position='center',
        divisible_by=32,
        device='cpu',
        height=resized_image_44.out(2),
        image=input_image_2.out('IMAGE'),
        width=resized_image_44.out(1),
    )
    model_with_nag = node(wf, 'LTX2_NAG', '197',
        nag_scale=11,
        nag_alpha=0.25,
        nag_tau=2.5,
        inplace=True,
        model=getnode_8.out(0),
        nag_cond_audio=getnode_19.out(0),
        nag_cond_video=getnode_19.out(0),
    )
    anchored_latent_210 = node(wf, 'LTXVImgToVideoInplaceKJ', '210',
        latent=empty_video_latent.out('LATENT'),
        num_images='2',
        vae=getnode_5.out(0),
        _extras={
            'num_images.image_1': preprocessed_image_2.out('OUTPUT_IMAGE'),
            'num_images.image_2': preprocessed_image_50.out('OUTPUT_IMAGE'),
            'num_images.index_1': 0,
            'num_images.index_2': -1,
            'num_images.strength_1': getnode_35.out(0),
            'num_images.strength_2': getnode_36.out(0),
        },
    )
    # Upstream class is misspelled; do not rename.
    model_with_sage_attn = node(wf, 'PathchSageAttentionKJ', '226',
        sage_attention='auto',
        allow_compile=False,
        model=lora.out('MODEL'),
    )
    setnode_20 = node(wf, 'SetNode', '2075',
        widget_0='frames',
        INT=simple_calculator_k_j_2.out(1),
    )
    resize_images_by_longer_edge_1 = node(wf, 'ResizeImagesByLongerEdge', '2083',
        longer_edge=1536,
        images=resized_image_44.out('IMAGE'),
    )
    conditioning = node(wf, 'LTXVConditioning', '10',
        frame_rate=getnode_4.out(0),
        negative=negative_prompt.out('CONDITIONING'),
        positive=positive_prompt.out('CONDITIONING'),
    )
    av_latent_24 = node(wf, 'LTXVConcatAVLatent', '24',
        audio_latent=empty_audio_latent.out('LATENT'),
        video_latent=anchored_latent_210.out('LATENT'),
    )
    get_image_size_28 = node(wf, 'GetImageSize', '28',
        image=image_scale_by_26.out(0),
    )
    resize_images_by_longer_edge_49 = node(wf, 'ResizeImagesByLongerEdge', '49',
        longer_edge=1536,
        images=imageresizekjv2_2.out('IMAGE'),
    )
    set_node_75 = node(wf, 'SetNode', '75',
        widget_0='firstframe',
        IMAGE=resize_images_by_longer_edge_1.out(0),
    )
    setnode_13 = node(wf, 'SetNode', '199',
        widget_0='model_nag',
        MODEL=model_with_nag.out('MODEL'),
    )
    setnode_24 = node(wf, 'SetNode', '2129',
        widget_0='lastframe_resized',
        IMAGE=imageresizekjv2_2.out('IMAGE'),
    )
    ltxvscheduler = node(wf, 'LTXVScheduler', '2',
        steps=1,
        max_shift=2.05,
        base_shift=0.95,
        stretch=True,
        terminal=0.1,
        latent=av_latent_24.out('LATENT'),
    )
    sampled_latent_13 = node(wf, 'SamplerCustomAdvanced', '13',
        guider=cfg_guider_2.out('GUIDER'),
        latent_image=av_latent_24.out('LATENT'),
        noise=noise_2.out('NOISE'),
        sampler=sampler_kind_1.out('SAMPLER'),
        sigmas=sigmas_2.out('SIGMAS'),
    )
    setnode_2 = node(wf, 'SetNode', '78',
        widget_0='lastframe',
        IMAGE=resize_images_by_longer_edge_49.out(0),
    )
    setnode_3 = node(wf, 'SetNode', '125',
        widget_0='positive',
        CONDITIONING=conditioning.out('POSITIVE'),
    )
    setnode_4 = node(wf, 'SetNode', '126',
        widget_0='negative',
        CONDITIONING=conditioning.out('NEGATIVE'),
    )
    setnode_14 = node(wf, 'SetNode', '217',
        widget_0='width_downscaled',
        INT=get_image_size_28.out(0),
    )
    setnode_15 = node(wf, 'SetNode', '218',
        widget_0='height_downscaled',
        INT=get_image_size_28.out(1),
    )
    model_chunked_ffn = node(wf, 'LTXVChunkFeedForward', '228',
        chunks=2,
        dim_threshold=4096,
        model=model_with_sage_attn.out('MODEL'),
    )
    av_latent_separated_18 = node(wf, 'LTXVSeparateAVLatent', '18',
        av_latent=sampled_latent_13.out('OUTPUT'),
    )
    ltxvlatent_upsampler = node(wf, 'LTXVLatentUpsampler', '25',
        _outputs=("latent",),
        samples=av_latent_separated_18.out('VIDEO_LATENT'),
        upscale_model=getnode_14.out(0),
        vae=getnode_7.out(0),
    )
    stage_boundary = node(wf, 'VRAM_Debug', '1846',
        _outputs=("any_output", "image_pass", "model_pass", "freemem_before", "freemem_after"),
        any_input=ltxvlatent_upsampler.out('LATENT'),
        empty_cache=True,
        gc_collect=True,
        unload_all_models=True,
    )
    model_attention_tuned = node(wf, 'LTX2AttentionTunerPatch', '229',
        blocks='',
        video_scale=1,
        audio_scale=1,
        video_to_audio_scale=1,
        audio_to_video_scale=1,
        triton_kernels=False,
        model=model_chunked_ffn.out('MODEL'),
    )
    l_t_x2_memory_efficient_sage_attention_patch_2291 = node(wf, 'LTX2MemoryEfficientSageAttentionPatch', '2291',
        triton_kernels=True,
        model=model_attention_tuned.out('MODEL'),
    )
    anchored_latent_2 = node(wf, 'LTXVImgToVideoInplaceKJ', '2105',
        latent=stage_boundary.out('ANY_OUTPUT'),
        num_images='1',
        vae=getnode_39.out(0),
        _extras={
            'num_images.image_1': getnode_13.out(0),
            'num_images.index_1': 0,
            'num_images.strength_1': getnode_35.out(0),
        },
    )
    power_lora_loader__rgthree_ = node(wf, 'Power Lora Loader (rgthree)', '2107',
model=l_t_x2_memory_efficient_sage_attention_patch_2291.out(0),
    )
    setnode_12 = node(wf, 'SetNode', '192',
        widget_0='model',
        MODEL=power_lora_loader__rgthree_.out(0),
    )
    setnode_16 = node(wf, 'SetNode', '230',
        widget_0='model_with_lora',
        MODEL=power_lora_loader__rgthree_.out(0),
    )
    ltxvadd_guide = node(wf, 'LTXVAddGuide', '2152',
        frame_idx=-1,
        image=getnode_34.out(0),
        latent=anchored_latent_2.out('LATENT'),
        negative=getnode_37.out(0),
        positive=getnode_40.out(0),
        strength=getnode_36.out(0),
        vae=getnode_38.out(0),
    )
    av_latent_2 = node(wf, 'LTXVConcatAVLatent', '34',
        audio_latent=av_latent_separated_18.out('AUDIO_LATENT'),
        video_latent=ltxvadd_guide.out(2),
    )
    setnode_25 = node(wf, 'SetNode', '2164',
        widget_0='positive_guider',
        CONDITIONING=ltxvadd_guide.out(0),
    )
    setnode_26 = node(wf, 'SetNode', '2165',
        widget_0='negative_guider',
        CONDITIONING=ltxvadd_guide.out(1),
    )
    sampled_latent_2 = node(wf, 'SamplerCustomAdvanced', '21',
        guider=cfg_guider_8.out('GUIDER'),
        latent_image=av_latent_2.out('LATENT'),
        noise=noise_14.out('NOISE'),
        sampler=sampler_kind_2.out('SAMPLER'),
        sigmas=sigmas_3.out('SIGMAS'),
    )
    av_latent_separated_2 = node(wf, 'LTXVSeparateAVLatent', '146',
        av_latent=sampled_latent_2.out('OUTPUT'),
    )
    # ════ DECODE ════
    decoded_audio = node(wf, 'LTXVAudioVAEDecode', '150',
        audio_vae=getnode_17.out(0),
        samples=av_latent_separated_2.out('AUDIO_LATENT'),
    )
    cropped_latent = node(wf, 'LTXVCropGuides', '2156',
        latent=av_latent_separated_2.out('VIDEO_LATENT'),
        negative=getnode_41.out(0),
        positive=getnode_42.out(0),
    )
    decoded_video = node(wf, 'VAEDecodeTiled', '149',
        tile_size=512,
        overlap=64,
        temporal_size=4096,
        temporal_overlap=8,
        samples=cropped_latent.out(2),
        vae=getnode_16.out(0),
    )
    setnode_6 = node(wf, 'SetNode', '154',
        widget_0='final_audio',
        AUDIO=decoded_audio.out(0),
    )
    setnode_5 = node(wf, 'SetNode', '153',
        widget_0='final_video',
        IMAGE=decoded_video.out('IMAGE'),
    )

    _apply_runtime_schema_defaults(wf)
    return finalize(
        wf,
        PUBLIC_INPUTS,
        READY_METADATA,
        output_node='43',
        output_type='VHS_VideoCombine',
        name='video',
        mime_type='video/mp4',
        expected_cardinality='one',
        source_path=__file__,
    )

def _apply_runtime_schema_defaults(wf: VibeWorkflow) -> None:
    """Fill schema-required inputs that older exported widget JSON omitted."""
    if "92" in wf.nodes:
        wf.nodes["92"].inputs.setdefault("variables", "a")
    if "2077" in wf.nodes:
        wf.nodes["2077"].inputs.setdefault("variables", "a,b")
        wf.nodes["2077"].inputs["widget_0"] = "a"
    if "43" in wf.nodes:
        wf.nodes["43"].inputs.update(
            {
                "filename_prefix": OUTPUT_PREFIX,
                "format": "video/h264-mp4",
                "loop_count": 0,
                "pingpong": False,
                "save_output": True,
            }
        )

