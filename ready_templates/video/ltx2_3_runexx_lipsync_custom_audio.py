# vibecomfy: generated — converted by tools/convert_ready_templates.py
# Edits will be overwritten on regeneration. Add a `# vibecomfy: manual`
# marker on the first line if hand-editing is required.
"""Voice To Lipsync Video with LTX 23 Video VAE Bf 16 VAE.

Public inputs:
    use_lora: Lightning LoRA branch toggle

Output: unknown.

Source:  workflow_corpus/custom_nodes/ltxvideo/runexx/LTX-2.3_V2V_Just_Talk_custom_audio_lipsync.json

Packs:   ComfyUI-GGUF, ComfyUI-KJNodes, ComfyUI-LTXVideo, ComfyUI-VideoHelperSuite, rgthree-comfy
"""
from __future__ import annotations

from vibecomfy.workflow import VibeWorkflow
from vibecomfy.templates import InputSpec, ModelAsset, ReadyMetadata, finalize, new_workflow, node

def _get_node_clip(wf, _id, **overrides):
    kwargs = dict(widget_0='clip')
    kwargs.update(overrides)
    return node(wf, 'GetNode', _id, **kwargs)
def _get_node_vae_audio(wf, _id, **overrides):
    kwargs = dict(widget_0='vae_audio')
    kwargs.update(overrides)
    return node(wf, 'GetNode', _id, **kwargs)
def _get_node_vae(wf, _id, **overrides):
    kwargs = dict(widget_0='vae')
    kwargs.update(overrides)
    return node(wf, 'GetNode', _id, **kwargs)
def _get_node_fps(wf, _id, **overrides):
    kwargs = dict(widget_0='fps')
    kwargs.update(overrides)
    return node(wf, 'GetNode', _id, **kwargs)
def _get_node_ext_seconds(wf, _id, **overrides):
    kwargs = dict(widget_0='ext_seconds')
    kwargs.update(overrides)
    return node(wf, 'GetNode', _id, **kwargs)
def _get_node_ref_image(wf, _id, **overrides):
    kwargs = dict(widget_0='ref_image')
    kwargs.update(overrides)
    return node(wf, 'GetNode', _id, **kwargs)
def _get_node_max_size(wf, _id, **overrides):
    kwargs = dict(widget_0='max_size')
    kwargs.update(overrides)
    return node(wf, 'GetNode', _id, **kwargs)
def _get_node_positive(wf, _id, **overrides):
    kwargs = dict(widget_0='positive')
    kwargs.update(overrides)
    return node(wf, 'GetNode', _id, **kwargs)
def _get_node_negative(wf, _id, **overrides):
    kwargs = dict(widget_0='negative')
    kwargs.update(overrides)
    return node(wf, 'GetNode', _id, **kwargs)
def _get_node_ref_video(wf, _id, **overrides):
    kwargs = dict(widget_0='ref_video')
    kwargs.update(overrides)
    return node(wf, 'GetNode', _id, **kwargs)
def _get_node_model_n_nag(wf, _id, **overrides):
    kwargs = dict(widget_0='model_n_nag')
    kwargs.update(overrides)
    return node(wf, 'GetNode', _id, **kwargs)
def _get_node_positive_to_crop(wf, _id, **overrides):
    kwargs = dict(widget_0='positive_to_crop')
    kwargs.update(overrides)
    return node(wf, 'GetNode', _id, **kwargs)
def _get_node_negative_to_crop(wf, _id, **overrides):
    kwargs = dict(widget_0='negative_to_crop')
    kwargs.update(overrides)
    return node(wf, 'GetNode', _id, **kwargs)
def _get_node_latent_audio_selecte(wf, _id, **overrides):
    kwargs = dict(widget_0='latent_audio_selected')
    kwargs.update(overrides)
    return node(wf, 'GetNode', _id, **kwargs)
def _get_image_range_from_batch(wf, _id, images, **overrides):
    kwargs = dict(widget_0=0,
                  widget_1=1,
                  images=images)
    kwargs.update(overrides)
    return node(wf, 'GetImageRangeFromBatch', _id, **kwargs)
MODELS = {
    'ltx23_video_vae_bf16_vae': ModelAsset(
        filename='LTX23_video_vae_bf16.safetensors',
        url='',
        subdir='vae',
    ),
    'gemma_clip': ModelAsset(
        filename='gemma_3_12B_it_fp4_mixed.safetensors',
        url='',
        subdir='text_encoders',
    ),
    'ltx_2_3_text_projection_bf16_clip': ModelAsset(
        filename='ltx-2.3_text_projection_bf16.safetensors',
        url='',
        subdir='text_encoders',
    ),
    'taeltx2_3_vae': ModelAsset(
        filename='taeltx2_3.safetensors',
        url='',
        subdir='vae',
    ),
    'ltx_2_3_22b_distilled_1_1_transformer_only': ModelAsset(
        filename='ltx-2.3-22b-distilled-1.1_transformer_only_fp8_scaled.safetensors',
        url='',
        subdir='diffusion_models',
    ),
    'gemma_clip_2': ModelAsset(
        filename='gemma-3-12b-it-Q2_K.gguf',
        url='',
        subdir='text_encoders',
    ),
}

PUBLIC_INPUTS = {
    'use_lora': InputSpec(node='594', field='value', default=False, type='BOOLEAN', description='Lightning LoRA branch toggle.'),
}

READY_METADATA = ReadyMetadata.build(
    template_id='ltx2_3_runexx_lipsync_custom_audio',
    capability='voice_to_lipsync_video',
    inputs=PUBLIC_INPUTS,
    models=MODELS,
    output_prefix='',
    requirements={'custom_nodes': ['ComfyUI-GGUF', 'ComfyUI-KJNodes', 'ComfyUI-LTXVideo', 'ComfyUI-VideoHelperSuite', 'rgthree-comfy'], 'custom_node_refs': [{'slug': 'ComfyUI-GGUF', 'source': 'git',
                       'commit': '6ea2651e7df66d7585f6ffee804b20e92fb38b8a', 'url': 'https://github.com/city96/ComfyUI-GGUF.git'}, {'slug': 'ComfyUI-KJNodes', 'source': 'git', 'commit': 'b7646ad70a7daa7aeb919ca542274758d26ba2df', 'url': 'https://github.com/kijai/ComfyUI-KJNodes.git'}, {'slug': 'ComfyUI-LTXVideo', 'source': 'git',
                       'commit': '229437c6b65796d6a7a63ae34be2bd5ba31fa543', 'url': 'https://github.com/Lightricks/ComfyUI-LTXVideo.git'}, {'slug': 'ComfyUI-VideoHelperSuite', 'source': 'git',
                       'commit': '4ee72c065db22c9d96c2427954dc69e7b908444b', 'url': 'https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite.git'}, {'slug': 'rgthree-comfy', 'source': 'git',
                       'commit': '738105af5fb14e96fbecaf406dc356e284797e8c', 'url': 'https://github.com/rgthree/rgthree-comfy.git'}]},
    provenance={'source_role': 'materialized_ready_python_template', 'approach': 'custom-audio lip-sync / voice-to-video', 'source_workflow': 'workflow_corpus/custom_nodes/ltxvideo/runexx/LTX-2.3_V2V_Just_Talk_custom_audio_lipsync.json', 'smoke_resolution': '256x256x5_frames'},
    coverage_tier='supplemental',
    ltx_best_practices=['Use the official Lightricks workflows as runtime gates where possible.', 'Patch smoke runs to fp8/fp4 model assets, tiny frame counts, and low-VRAM loaders.', 'Bypass latent spatial upscalers in smoke runs until HiddenSwitch Comfy exposes model_mmap_residency for LatentUpscaleModelManageable.', 'Keep community audio, lip-sync, and long-form workflows as ready templates until their custom node packs and service credentials are declared.'],
    comfy_configuration={'reserve_vram': 12, 'cache_none': True, 'fp8_e4m3fn_text_enc': True},
    vibecomfy_version='0.1.0',
    comfy_core={'version': '0.18.2', 'tested_at': '2026-05-20T09:19:32.302139+00:00', 'commit': 'f7b38d2eb97207cd834bcc3eb2e8b1d447b96c68', 'status': 'discovered'},
)

def build() -> VibeWorkflow:
    """Build the workflow (auto-generated)."""
    wf = new_workflow(READY_METADATA, source_path=__file__)

    # ════ SAMPLING ════
    noise_115 = node(wf, 'RandomNoise', '115',
        noise_seed=790774741312584,
        control_after_generate='randomize',
    )
    # ════ DECODE ════
    decoded_video = node(wf, 'VAEDecodeTiled', '127',
        tile_size=512,
        overlap=64,
        temporal_size=4096,
        temporal_overlap=8,
    )
    sampler_kind_137 = node(wf, 'KSamplerSelect', '137',
        sampler_name='euler_ancestral_cfg_pp',
    )
    param_int_211 = node(wf, 'INTConstant', '211',
        value=3,
    )
    param_float_214 = node(wf, 'PrimitiveFloat', '214', value=8)
    get_node_215 = _get_node_clip(wf, '215', )
    getnode_2 = _get_node_vae_audio(wf, '216', )
    getnode_3 = _get_node_vae(wf, '217', )
    getnode_4 = _get_node_vae_audio(wf, '219', )
    getnode_5 = _get_node_vae(wf, '220', )
    getnode_6 = _get_node_fps(wf, '221', )
    getnode_7 = _get_node_fps(wf, '222', )
    getnode_8 = node(wf, 'GetNode', '242',
        widget_0='upscale_model',
    )
    noise_2 = node(wf, 'RandomNoise', '243',
        noise_seed=43,
        control_after_generate='fixed',
    )
    getnode_9 = _get_node_vae(wf, '244', )
    sampler_kind_2 = node(wf, 'KSamplerSelect', '254',
        sampler_name='euler_cfg_pp',
    )
    getnode_10 = _get_node_ext_seconds(wf, '356', )
    getnode_11 = node(wf, 'GetNode', '369',
        widget_0='model',
    )
    getnode_12 = node(wf, 'GetNode', '408',
        widget_0='vae_tiny',
    )
    getnode_13 = _get_node_ref_image(wf, '439', )
    getnode_14 = _get_node_vae(wf, '442', )
    # ════ LOADERS ════
    vae_463 = node(wf, 'VAELoader', '463',
        vae_name=MODELS['ltx23_video_vae_bf16_vae'].filename,
    )
    # ════ LATENT ════
    latent_upscale_model_loader_465 = node(wf, 'LatentUpscaleModelLoader', '465',
        model_name='ltx-2.3-spatial-upscaler-x2-1.1.safetensors',
    )
    text_encoder = node(wf, 'DualCLIPLoader', '466',
        clip_name1=MODELS['gemma_clip'].filename,
        clip_name2=MODELS['ltx_2_3_text_projection_bf16_clip'].filename,
        type='ltxv',
        device='default',
    )
    vaeloaderkj = node(wf, 'LTXVAudioVAELoader', '471',
        ckpt_name='LTX23_audio_vae_bf16.safetensors',
    )
    vae_2 = node(wf, 'VAELoader', '473',
        vae_name=MODELS['taeltx2_3_vae'].filename,
    )
    base_diffusion_model = node(wf, 'UNETLoader', '474',
        unet_name=MODELS['ltx_2_3_22b_distilled_1_1_transformer_only'].filename,
        weight_dtype='default',
    )
    unet_loader_gguf = node(wf, 'UnetLoaderGGUF', '475',
        unet_name='LTXvideo\\LTX-2\\quantstack\\LTX-2.3-distilled-Q4_K_S.gguf',
    )
    dual_cliploader_gguf = node(wf, 'DualCLIPLoaderGGUF', '477',
        clip_name1=MODELS['gemma_clip_2'].filename,
        clip_name2=MODELS['ltx_2_3_text_projection_bf16_clip'].filename,
        type='sdxl',
    )
    sigmas_479 = node(wf, 'ManualSigmas', '479',
        sigmas='0.85, 0.7250, 0.4219, 0.0',
    )
    sigmas_2 = node(wf, 'ManualSigmas', '480',
        sigmas='1.0, 0.99375, 0.9875, 0.98125, 0.975, 0.909375, 0.725, 0.421875, 0.0',
    )
    primitive_string_multiline_487 = node(wf, 'PrimitiveStringMultiline', '487',
        value='Cinematic video woman wearing colorful make-up, with colorful  light creating a creative scene. \n\nShe talks with perfect lip-sync movements to the attached audio. Her mouth and lips moves as she talks. \n \nThe camera slowly moves away from the woman, showing her full body. She is standing at a  colorful theatre scene doing a victorian era play. ',
    )
    reroute_496 = node(wf, 'Reroute', '496')
    param_INT = node(wf, 'INTConstant', '497',
        value=650,
    )
    getnode_15 = _get_node_max_size(wf, '502', )
    getnode_16 = _get_node_max_size(wf, '507', )
    getnode_17 = _get_node_ref_image(wf, '508', )
    getnode_18 = _get_node_positive(wf, '572', )
    getnode_19 = _get_node_negative(wf, '573', )
    getnode_20 = _get_node_fps(wf, '580', )
    getnode_21 = node(wf, 'GetNode', '581',
        widget_0='final_video',
    )
    # ════ INPUTS ════
    use_lora = node(wf, 'PrimitiveBoolean', '594', value=PUBLIC_INPUTS['use_lora'].default)
    getnode_22 = _get_node_clip(wf, '600', )
    getnode_23 = node(wf, 'GetNode', '602',
        widget_0='enable_promptenhance',
    )
    getnode_24 = _get_node_ref_video(wf, '638', )
    getnode_25 = _get_node_fps(wf, '643', )
    getnode_26 = node(wf, 'GetNode', '649',
        widget_0='final_audio',
    )
    getnode_27 = _get_node_model_n_nag(wf, '652', )
    getnode_28 = _get_node_model_n_nag(wf, '654', )
    getnode_29 = _get_node_vae(wf, '719', )
    getnode_30 = _get_node_ref_video(wf, '724', )
    getnode_31 = _get_node_vae(wf, '731', )
    getnode_32 = _get_node_ref_image(wf, '732', )
    getnode_33 = _get_node_positive(wf, '739', )
    getnode_34 = _get_node_negative(wf, '740', )
    # ════ TEXT CONDITIONING ════
    ltxavtext_encoder_loader = node(wf, 'LTXAVTextEncoderLoader', '742',
        ckpt_name='ltx-2.3-22b-dev-fp8.safetensors',
        text_encoder=MODELS['gemma_clip'].filename,
        
        device='default',
    )
    getnode_35 = _get_node_vae(wf, '804', )
    param_FLOAT = node(wf, 'PrimitiveFloat', '814', value=8)
    getnode_36 = node(wf, 'GetNode', '816',
        widget_0='last_latent_strength',
    )
    getnode_37 = _get_node_positive_to_crop(wf, '822', )
    getnode_38 = _get_node_negative_to_crop(wf, '823', )
    getnode_39 = _get_node_negative_to_crop(wf, '825', )
    getnode_40 = _get_node_positive_to_crop(wf, '826', )
    getnode_41 = node(wf, 'GetNode', '845',
        widget_0='latent_custom_audio',
    )
    getnode_42 = node(wf, 'GetNode', '846',
        widget_0='latent_audio',
    )
    load_audio_855 = node(wf, 'LoadAudio', '855',
        audio='e9318ca1-5e2b-47aa-8397-f4538b0151b0.wav',
    )
    getnode_43 = node(wf, 'GetNode', '856',
        widget_0='height_generated',
    )
    getnode_44 = _get_node_vae_audio(wf, '858', )
    mel_band_ro_former_model_loader_861 = node(wf, 'MelBandRoFormerModelLoader', '861',
        widget_0='MelBandRoformer\\MelBandRoformer_fp16.safetensors',
    )
    getnode_45 = node(wf, 'GetNode', '862',
        widget_0='width_generated',
    )
    getnode_46 = node(wf, 'GetNode', '872',
        widget_0='frames_loaded',
    )
    getnode_47 = _get_node_fps(wf, '873', )
    getnode_48 = _get_node_ext_seconds(wf, '874', )
    getnode_49 = _get_node_latent_audio_selecte(wf, '879', )
    getnode_50 = _get_node_latent_audio_selecte(wf, '887', )
    conditioning = node(wf, 'LTXVConditioning', '107',
        frame_rate=getnode_7.out(0),
        negative=getnode_34.out(0),
        positive=getnode_33.out(0),
    )
    prompt_embedding_110 = node(wf, 'CLIPTextEncode', '110',
        text='text, subtitles, logo, low quality, distorted, bad anatomy, oversaturated, pixelated, low resolution, grainy, compression artifacts, jpeg artifacts, glitches, watermark, signature, copyright,  distortedsound, saturated sound, loud sound , deformed facial features, asymmetrical face, missing facial features, extra limbs, disfigured hands, blurry teeth, disfigured teeth',
        clip=get_node_215.out(0),
    )
    setnode_3 = node(wf, 'SetNode', '209',
        widget_0='ext_seconds',
        INT=param_int_211.out('VALUE'),
    )
    setnode_4 = node(wf, 'SetNode', '210',
        widget_0='fps',
        FLOAT=param_float_214.out('FLOAT'),
    )
    # Stage 1 (REFINE): NAG model (bypasses patch stack) + base conditioning
    # Stage 2 (FINISH): IC-LoRA model (full patch chain)   + guided conditioning
    cfg_guider_1 = node(wf, 'CFGGuider', '256',
        cfg=2.5,
        model=getnode_27.out(0),
        negative=getnode_19.out(0),
        positive=getnode_18.out(0),
    )
    # ════ IMAGE PREP ════
    resize_image_mask_node_436 = node(wf, 'ResizeImageMaskNode', '436',
        resize_type='scale by multiplier',
scale_method='area',
        input=getnode_24.out(0),
    )
    setnode_9 = node(wf, 'SetNode', '459',
        widget_0='upscale_model',
        LATENT_UPSCALE_MODEL=latent_upscale_model_loader_465.out(0),
    )
    setnode_10 = node(wf, 'SetNode', '460',
        widget_0='vae_audio',
        VAE=vaeloaderkj.out('AUDIO_VAE'),
    )
    setnode_11 = node(wf, 'SetNode', '461',
        widget_0='vae',
        VAE=vae_463.out('VAE'),
    )
    setnode_12 = node(wf, 'SetNode', '462',
        widget_0='clip',
        CLIP=ltxavtext_encoder_loader.out(0),
    )
    # ════ MODEL PATCH STACK ════
    lora = node(wf, 'LoraLoaderModelOnly', '464',
        lora_name='LTX\\LTX-2\\ltx-2.3-22b-distilled-lora-384.safetensors',
        strength_model=0.6,
        model=base_diffusion_model.out('MODEL'),
    )
    setnode_13 = node(wf, 'SetNode', '472',
        widget_0='vae_tiny',
        VAE=vae_2.out('VAE'),
    )
    setnode_15 = node(wf, 'SetNode', '498',
        widget_0='max_size',
        INT=param_INT.out('VALUE'),
    )
    resize_images_by_longer_edge_1 = node(wf, 'ResizeImagesByLongerEdge', '505',
        images=reroute_496.out(0),
        longer_edge=getnode_16.out(0),
    )
    # ════ OUTPUT ════
    video_output = node(wf, 'VHS_VideoCombine', '578',
        audio=getnode_26.out(0),
        frame_rate=getnode_20.out(0),
        images=getnode_21.out(0),
    )
    setnode_16 = node(wf, 'SetNode', '601',
        widget_0='enable_promptenhance',
        BOOLEAN=use_lora.out('BOOLEAN'),
    )
    prompt_embedding_2 = node(wf, 'CLIPTextEncode', '626',
        text=' distorted sound, saturated sound, loud sound',
        clip=get_node_215.out(0),
    )
    get_image_size_and_count_1 = node(wf, 'GetImageSizeAndCount', '698',
        image=getnode_24.out(0),
    )
    comfy_math_expression_699 = node(wf, 'ComfyMathExpression', '699',
        widget_0='a',
        _extras={'values.a': getnode_25.out(0)},
    )
    resize_image_mask_node_2 = node(wf, 'ResizeImageMaskNode', '726',
        resize_type='scale by multiplier',
scale_method='nearest-exact',
        input=getnode_30.out(0),
    )
    vhs__load_video_f_fmpeg = node(wf, 'VHS_LoadVideoFFmpeg', '774',
        force_rate=getnode_6.out(0),
    )
    e428c881_c48b_4849_9158_8311b4df27c7_784 = node(wf, 'e428c881-c48b-4849-9158-8311b4df27c7', '784',
        clip=getnode_22.out(0),
        image=getnode_17.out(0),
        switch=getnode_23.out(0),
    )
    setnode_21 = node(wf, 'SetNode', '815',
        widget_0='last_latent_strength',
        FLOAT=param_FLOAT.out('FLOAT'),
    )
    switch_847 = node(wf, 'ComfySwitchNode', '847',
        widget_0=True,
        on_false=getnode_42.out(0),
        on_true=getnode_41.out(0),
    )
    simple_calculator_k_j_1 = node(wf, 'SimpleCalculatorKJ', '854',
        expression='(a/b)+c',
        _extras={'variables.a': getnode_46.out(0), 'variables.b': getnode_47.out(0), 'variables.c': getnode_48.out(0)},
    )
    solid_mask_865 = node(wf, 'SolidMask', '865',
        widget_0=0,
        widget_1=512,
        widget_2=512,
        height=getnode_43.out(0),
        width=getnode_45.out(0),
    )
    vhs__video_info = node(wf, 'VHS_VideoInfo', '492',
        video_info=vhs__load_video_f_fmpeg.out(3),
    )
    # Upstream class is misspelled; do not rename.
    model_with_sage_attn = node(wf, 'PathchSageAttentionKJ', '520',
        sage_attention='disabled',
        allow_compile=False,
        model=lora.out('MODEL'),
    )
    model_sampling = node(wf, 'ModelSamplingSD3', '526',
        shift=13,
        model=getnode_11.out(0),
    )
    model_with_nag = node(wf, 'LTX2_NAG', '563',
        nag_scale=11,
        nag_alpha=0.25,
        nag_tau=2.5,
        inplace=True,
        model=getnode_11.out(0),
        nag_cond_audio=prompt_embedding_2.out('CONDITIONING'),
        nag_cond_video=prompt_embedding_110.out('CONDITIONING'),
    )
    vaeencode_1 = node(wf, 'VAEEncode', '565',
        pixels=resize_image_mask_node_436.out(0),
        vae=getnode_3.out(0),
    )
    prompt_embedding_3 = node(wf, 'CLIPTextEncode', '592',
        text=e428c881_c48b_4849_9158_8311b4df27c7_784.out(0),
        clip=get_node_215.out(0),
    )
    empty_audio_latent = node(wf, 'LTXVEmptyLatentAudio', '642',
        
        batch_size=1,
        audio_vae=getnode_2.out(0),
        frame_rate=comfy_math_expression_699.out(1),
        frames_number=get_image_size_and_count_1.out(3),
    )
    setnode_20 = node(wf, 'SetNode', '656',
        widget_0='negative',
        CONDITIONING=prompt_embedding_110.out('CONDITIONING'),
    )
    comfy_math_expression_2 = node(wf, 'ComfyMathExpression', '700',
        widget_0='a/b',
        _extras={'values.a': get_image_size_and_count_1.out(3), 'values.b': getnode_25.out(0)},
    )
    getimagerangefrombatch_2 = _get_image_range_from_batch(wf, '714', resize_image_mask_node_2.out(0))
    face_segment_761 = node(wf, 'FaceSegment', '761',
        widget_0=True,
        widget_1=True,
        widget_10=True,
        widget_11=True,
        widget_12=False,
        widget_13=False,
        widget_14=False,
        widget_15=512,
        widget_16=0,
        widget_17=10,
        widget_18=False,
        widget_19='Alpha',
        widget_2=False,
        widget_20='#222222',
        widget_3=True,
        widget_4=True,
        widget_5=False,
        widget_6=True,
        widget_7=True,
        widget_8=True,
        widget_9=True,
        images=resize_image_mask_node_2.out(0),
    )
    get_image_range_from_batch = node(wf, 'GetImageRangeFromBatch', '806',
        widget_0=-1,
        widget_1=1,
        images=resize_image_mask_node_436.out(0),
    )
    setnode_24 = node(wf, 'SetNode', '849',
        widget_0='latent_audio_selected',
        LATENT=switch_847.out('OUTPUT'),
    )
    trim_audio_duration_859 = node(wf, 'TrimAudioDuration', '859',
        widget_0=0,
        widget_1=40,
        audio=load_audio_855.out(0),
        duration=simple_calculator_k_j_1.out(0),
    )
    setnode_31 = node(wf, 'SetNode', '883',
        widget_0='width_generated',
        INT=get_image_size_and_count_1.out(1),
    )
    setnode_32 = node(wf, 'SetNode', '884',
        widget_0='height_generated',
        INT=get_image_size_and_count_1.out(2),
    )
    basic_scheduler_164 = node(wf, 'BasicScheduler', '164',
        scheduler=1,
        steps=1,
        denoise=1,
        widget_1=15,
        model=model_sampling.out('MODEL'),
    )
    simple_calculator_k_j_500 = node(wf, 'SimpleCalculatorKJ', '500',
        expression='(a > c) or (b > c) ',
        _extras={'variables.a': vhs__video_info.out(8), 'variables.b': vhs__video_info.out(9), 'variables.c': getnode_15.out(0)},
    )
    setnode_18 = node(wf, 'SetNode', '651',
        widget_0='model_n_nag',
        MODEL=model_with_nag.out('MODEL'),
    )
    setnode_19 = node(wf, 'SetNode', '655',
        widget_0='positive',
        CONDITIONING=prompt_embedding_3.out('CONDITIONING'),
    )
    comfy_math_expression_3 = node(wf, 'ComfyMathExpression', '701',
        widget_0='a+b',
        _extras={'values.a': comfy_math_expression_2.out(0), 'values.b': getnode_10.out(0)},
    )
    blockify_mask_790 = node(wf, 'BlockifyMask', '790',
        block_size=12,
        widget_1='cpu',
        masks=face_segment_761.out(1),
    )
    vaeencode_2_2 = node(wf, 'VAEEncode', '809',
        pixels=get_image_range_from_batch.out(0),
        vae=getnode_35.out(0),
    )
    setnode_25 = node(wf, 'SetNode', '852',
        widget_0='audio_original',
        AUDIO=trim_audio_duration_859.out(0),
    )
    mel_band_ro_former_sampler_860 = node(wf, 'MelBandRoFormerSampler', '860',
        audio=trim_audio_duration_859.out(0),
        model=mel_band_ro_former_model_loader_861.out(0),
    )
    setnode_29 = node(wf, 'SetNode', '871',
        widget_0='frames_loaded',
        INT=vhs__video_info.out(6),
    )
    lazy_switch_k_j_504 = node(wf, 'LazySwitchKJ', '504',
        widget_0=False,
        on_false=reroute_496.out(0),
        on_true=resize_images_by_longer_edge_1.out(0),
        switch=simple_calculator_k_j_500.out(2),
    )
    model_chunked_ffn = node(wf, 'LTXVChunkFeedForward', '522',
        chunks=2,
        dim_threshold=4096,
        model=model_with_sage_attn.out('MODEL'),
    )
    resize_image_mask_node_3 = node(wf, 'ResizeImageMaskNode', '717',
        resize_type='match size',
scale_method='nearest-exact',
        input=blockify_mask_790.out(0),
        _extras={'resize_type.match': getimagerangefrombatch_2.out(0)},
    )
    mask_to_image_791 = node(wf, 'MaskToImage', '791',
        mask=blockify_mask_790.out(0),
    )
    setnode_26 = node(wf, 'SetNode', '853',
        widget_0='audio_vocals',
        AUDIO=mel_band_ro_former_sampler_860.out(0),
    )
    switch_audio = node(wf, 'ComfySwitchNode', '868',
        widget_0=True,
        on_false=trim_audio_duration_859.out(0),
        on_true=mel_band_ro_former_sampler_860.out(0),
    )
    get_image_size_and_count_506 = node(wf, 'GetImageSizeAndCount', '506',
        image=lazy_switch_k_j_504.out(0),
    )
    model_attention_tuned = node(wf, 'LTX2AttentionTunerPatch', '523',
        blocks='',
        video_scale=1,
        audio_scale=1,
        video_to_audio_scale=1,
        audio_to_video_scale=1,
        triton_kernels=False,
        model=model_chunked_ffn.out('MODEL'),
    )
    ltxvpreprocess_masks = node(wf, 'LTXVPreprocessMasks', '720',
        widget_0=False,
        widget_1=False,
        widget_2='max',
        widget_3=0,
        widget_4=True,
        widget_5=0.5,
        widget_6=1,
        masks=resize_image_mask_node_3.out(0),
        vae=getnode_29.out(0),
    )
    getimagerangefrombatch_3 = _get_image_range_from_batch(wf, '775', mask_to_image_791.out(0))
    ltxvaudio_vaeencode = node(wf, 'LTXVAudioVAEEncode', '866',
        audio=switch_audio.out('OUTPUT'),
        audio_vae=getnode_44.out(0),
    )
    setnode_28 = node(wf, 'SetNode', '867',
        widget_0='audio',
        AUDIO=switch_audio.out('OUTPUT'),
    )
    resized_image = node(wf, 'ImageResizeKJv2', '512',
        
        upscale_method='nearest-exact',
        keep_proportion='crop',
        pad_color='0, 0, 0',
        crop_position='center',
        divisible_by=64,
        device='cpu',
        height=get_image_size_and_count_506.out(2),
        image=get_image_size_and_count_506.out(0),
        width=get_image_size_and_count_506.out(1),
    )
    power_lora_loader__rgthree_ = node(wf, 'Power Lora Loader (rgthree)', '660',
model=model_attention_tuned.out('MODEL'),
    )
    preview_image_763 = node(wf, 'PreviewImage', '763',
        images=getimagerangefrombatch_3.out(0),
    )
    ltxvset_video_latent_noise_masks = node(wf, 'LTXVSetVideoLatentNoiseMasks', '794',
        masks=ltxvpreprocess_masks.out(0),
        samples=vaeencode_1.out('LATENT'),
    )
    set_latent_noise_mask_864 = node(wf, 'SetLatentNoiseMask', '864',
        mask=solid_mask_865.out(0),
        samples=ltxvaudio_vaeencode.out(0),
    )
    ltxvaudio_video_mask = node(wf, 'LTXVAudioVideoMask', '178',
        widget_0=24,
        widget_1=0,
        widget_2=15,
        widget_3=0,
        widget_4=10000,
        widget_5='pad',
        widget_6='add',
        audio_end_time=comfy_math_expression_3.out(0),
        audio_latent=empty_audio_latent.out('LATENT'),
        video_end_time=comfy_math_expression_3.out(0),
        video_fps=getnode_25.out(0),
        video_latent=ltxvset_video_latent_noise_masks.out(0),
        video_start_time=comfy_math_expression_2.out(0),
    )
    set_node_207 = node(wf, 'SetNode', '207',
        widget_0='width',
        INT=resized_image.out(1),
    )
    setnode_2 = node(wf, 'SetNode', '208',
        widget_0='height',
        INT=resized_image.out(2),
    )
    setnode_7 = node(wf, 'SetNode', '328',
        widget_0='ref_video',
        IMAGE=resized_image.out('IMAGE'),
    )
    get_image_range_from_batch_440 = _get_image_range_from_batch(wf, '440', resized_image.out('IMAGE'))
    setnode_14 = node(wf, 'SetNode', '481',
        widget_0='model',
        MODEL=power_lora_loader__rgthree_.out(0),
    )
    setnode_27 = node(wf, 'SetNode', '863',
        widget_0='latent_custom_audio',
        LATENT=set_latent_noise_mask_864.out(0),
    )
    resize_images_by_longer_edge_495 = node(wf, 'ResizeImagesByLongerEdge', '495',
        longer_edge=1536,
        images=get_image_range_from_batch_440.out(0),
    )
    ltxvadd_latent_guide = node(wf, 'LTXVAddLatentGuide', '799',
        widget_0=-1,
        widget_1=0.7,
        guiding_latent=vaeencode_2_2.out('LATENT'),
        latent=ltxvaudio_video_mask.out(0),
        latent_idx=get_image_size_and_count_1.out(3),
        negative=conditioning.out('NEGATIVE'),
        positive=conditioning.out('POSITIVE'),
        strength=getnode_36.out(0),
        vae=getnode_35.out(0),
    )
    setnode_30 = node(wf, 'SetNode', '876',
        widget_0='latent_audio',
        LATENT=ltxvaudio_video_mask.out(1),
    )
    cfg_guider_129 = node(wf, 'CFGGuider', '129',
        cfg=2.5,
        model=getnode_28.out(0),
        negative=ltxvadd_latent_guide.out(1),
        positive=ltxvadd_latent_guide.out(0),
    )
    setnode_6 = node(wf, 'SetNode', '294',
        widget_0='ref_image',
        IMAGE=resize_images_by_longer_edge_495.out(0),
    )
    preprocessed_image = node(wf, 'LTXVPreprocess', '299',
        img_compression=18,
        image=resize_images_by_longer_edge_495.out(0),
    )
    ltxvimg_to_video_inplace_1 = node(wf, 'LTXVImgToVideoInplace', '730',
        widget_0=0.7,
        widget_1=False,
        image=getnode_32.out(0),
        latent=ltxvadd_latent_guide.out(2),
        vae=getnode_31.out(0),
    )
    setnode_22 = node(wf, 'SetNode', '820',
        widget_0='positive_to_crop',
        CONDITIONING=ltxvadd_latent_guide.out(0),
    )
    setnode_23 = node(wf, 'SetNode', '821',
        widget_0='negative_to_crop',
        CONDITIONING=ltxvadd_latent_guide.out(1),
    )
    av_latent_109 = node(wf, 'LTXVConcatAVLatent', '109',
        audio_latent=getnode_50.out(0),
        video_latent=ltxvimg_to_video_inplace_1.out(0),
    )
    setnode_5 = node(wf, 'SetNode', '285',
        widget_0='compress_image',
        IMAGE=preprocessed_image.out('OUTPUT_IMAGE'),
    )
    sampled_latent_113 = node(wf, 'SamplerCustomAdvanced', '113',
        guider=cfg_guider_129.out('GUIDER'),
        latent_image=av_latent_109.out('LATENT'),
        noise=noise_115.out('NOISE'),
        sampler=sampler_kind_137.out('SAMPLER'),
        sigmas=sigmas_2.out('SIGMAS'),
    )
    av_latent_separated_1 = node(wf, 'LTXVSeparateAVLatent', '250',
        av_latent=sampled_latent_113.out('OUTPUT'),
    )
    cropped_latent_810 = node(wf, 'LTXVCropGuides', '810',
        latent=av_latent_separated_1.out('VIDEO_LATENT'),
        negative=getnode_38.out(0),
        positive=getnode_37.out(0),
    )
    ltxvimg_to_video_inplace_2 = node(wf, 'LTXVImgToVideoInplace', '438',
        widget_0=1,
        widget_1=False,
        image=getnode_13.out(0),
        latent=cropped_latent_810.out(2),
        vae=getnode_14.out(0),
    )
    av_latent_2 = node(wf, 'LTXVConcatAVLatent', '251',
        audio_latent=av_latent_separated_1.out('AUDIO_LATENT'),
        video_latent=ltxvimg_to_video_inplace_2.out(0),
    )
    sampled_latent_2 = node(wf, 'SamplerCustomAdvanced', '258',
        guider=cfg_guider_1.out('GUIDER'),
        latent_image=av_latent_2.out('LATENT'),
        noise=noise_2.out('NOISE'),
        sampler=sampler_kind_2.out('SAMPLER'),
        sigmas=sigmas_479.out('SIGMAS'),
    )
    av_latent_separated_125 = node(wf, 'LTXVSeparateAVLatent', '125',
        av_latent=sampled_latent_2.out('OUTPUT'),
    )
    decoded_audio = node(wf, 'LTXVAudioVAEDecode', '425',
        audio_vae=getnode_4.out(0),
        samples=av_latent_separated_125.out('AUDIO_LATENT'),
    )
    cropped_latent_2 = node(wf, 'LTXVCropGuides', '824',
        latent=av_latent_separated_125.out('VIDEO_LATENT'),
        negative=getnode_39.out(0),
        positive=getnode_40.out(0),
    )
    decoded_image = node(wf, 'VAEDecode', '527',
        samples=cropped_latent_2.out(2),
        vae=getnode_5.out(0),
    )
    setnode_17 = node(wf, 'SetNode', '648',
        widget_0='final_audio',
        AUDIO=decoded_audio.out(0),
    )
    setnode_8 = node(wf, 'SetNode', '451',
        widget_0='final_video',
        IMAGE=decoded_image.out('IMAGE'),
    )

    return finalize(
        wf,
        PUBLIC_INPUTS,
        READY_METADATA,
        output_node='',
        source_path=__file__,
    )

