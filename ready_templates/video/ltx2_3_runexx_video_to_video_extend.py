# vibecomfy: generated — converted by tools/convert_ready_templates.py
# Edits will be overwritten on regeneration. Add a `# vibecomfy: manual`
# marker on the first line if hand-editing is required.
"""Video To Video Extend with LTX 23 Video VAE Bf 16 VAE.

Public inputs:
    use_lora: Lightning LoRA branch toggle

Output: unknown.

Source:  workflow_corpus/custom_nodes/ltxvideo/runexx/LTX-2.3_V2V_Extend_Any_Video.json

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
def _get_node_ref_frames(wf, _id, **overrides):
    kwargs = dict(widget_0='ref_frames')
    kwargs.update(overrides)
    return node(wf, 'GetNode', _id, **kwargs)
def _get_node_ref_video(wf, _id, **overrides):
    kwargs = dict(widget_0='ref_video')
    kwargs.update(overrides)
    return node(wf, 'GetNode', _id, **kwargs)
def _get_node_overlap_seconds(wf, _id, **overrides):
    kwargs = dict(widget_0='overlap_seconds')
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
def _get_node_final_audio(wf, _id, **overrides):
    kwargs = dict(widget_0='final_audio')
    kwargs.update(overrides)
    return node(wf, 'GetNode', _id, **kwargs)
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
    'ltx_2_3_22b_distilled_transformer_only_fp8': ModelAsset(
        filename='ltx-2.3-22b-distilled_transformer_only_fp8_scaled.safetensors',
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
    'use_lora': InputSpec(node='594', field='value', default=True, type='BOOLEAN', description='Lightning LoRA branch toggle.'),
}

READY_METADATA = ReadyMetadata.build(
    template_id='ltx2_3_runexx_video_to_video_extend',
    capability='video_to_video_extend',
    inputs=PUBLIC_INPUTS,
    models=MODELS,
    output_prefix='',
    requirements={'custom_nodes': ['ComfyUI-GGUF', 'ComfyUI-KJNodes', 'ComfyUI-LTXVideo', 'ComfyUI-VideoHelperSuite', 'rgthree-comfy'], 'custom_node_refs': [{'slug': 'ComfyUI-GGUF', 'source': 'git',
                       'commit': '6ea2651e7df66d7585f6ffee804b20e92fb38b8a', 'url': 'https://github.com/city96/ComfyUI-GGUF.git'}, {'slug': 'ComfyUI-KJNodes', 'source': 'git', 'commit': 'b7646ad70a7daa7aeb919ca542274758d26ba2df', 'url': 'https://github.com/kijai/ComfyUI-KJNodes.git'}, {'slug': 'ComfyUI-LTXVideo', 'source': 'git',
                       'commit': '229437c6b65796d6a7a63ae34be2bd5ba31fa543', 'url': 'https://github.com/Lightricks/ComfyUI-LTXVideo.git'}, {'slug': 'ComfyUI-VideoHelperSuite', 'source': 'git',
                       'commit': '4ee72c065db22c9d96c2427954dc69e7b908444b', 'url': 'https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite.git'}, {'slug': 'rgthree-comfy', 'source': 'git',
                       'commit': '738105af5fb14e96fbecaf406dc356e284797e8c', 'url': 'https://github.com/rgthree/rgthree-comfy.git'}]},
    provenance={'approach': 'video-to-video extension', 'source_role': 'materialized_ready_python_template', 'source_workflow': 'workflow_corpus/custom_nodes/ltxvideo/runexx/LTX-2.3_V2V_Extend_Any_Video.json', 'smoke_resolution': '256x256x5_frames'},
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
        noise_seed=42,
        control_after_generate='fixed',
    )
    # ════ DECODE ════
    decoded_video = node(wf, 'VAEDecodeTiled', '127',
        tile_size=512,
        overlap=64,
        temporal_size=4096,
        temporal_overlap=8,
    )
    sampler_kind_137 = node(wf, 'KSamplerSelect', '137',
        sampler_name='euler_ancestral',
    )
    param_int_211 = node(wf, 'INTConstant', '211',
        value=10,
    )
    param_float = node(wf, 'PrimitiveFloat', '214', value=8)
    get_node_215 = _get_node_clip(wf, '215', )
    getnode_2 = _get_node_vae_audio(wf, '216', )
    getnode_3 = _get_node_vae(wf, '217', )
    getnode_4 = _get_node_vae_audio(wf, '219', )
    getnode_5 = _get_node_vae(wf, '220', )
    getnode_6 = _get_node_fps(wf, '221', )
    getnode_7 = _get_node_fps(wf, '222', )
    getnode_8 = _get_node_fps(wf, '223', )
    getnode_9 = node(wf, 'GetNode', '242',
        widget_0='upscale_model',
    )
    noise_2 = node(wf, 'RandomNoise', '243',
        noise_seed=432,
        control_after_generate='fixed',
    )
    getnode_10 = _get_node_vae(wf, '244', )
    sampler_kind_2 = node(wf, 'KSamplerSelect', '254',
        sampler_name='euler',
    )
    param_int_2 = node(wf, 'INTConstant', '305',
        value=3,
    )
    getnode_11 = _get_node_ref_frames(wf, '326', )
    getnode_12 = node(wf, 'GetNode', '356',
        widget_0='ext_seconds',
    )
    getnode_13 = _get_node_ref_video(wf, '363', )
    getnode_14 = node(wf, 'GetNode', '369',
        widget_0='model',
    )
    getnode_15 = _get_node_ref_frames(wf, '380', )
    getnode_16 = node(wf, 'GetNode', '392',
        widget_0='ref_audio',
    )
    getnode_17 = _get_node_overlap_seconds(wf, '398', )
    getnode_18 = node(wf, 'GetNode', '408',
        widget_0='vae_tiny',
    )
    getnode_19 = node(wf, 'GetNode', '439',
        widget_0='ref_image_overlap',
    )
    getnode_20 = _get_node_vae(wf, '442', )
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
        unet_name=MODELS['ltx_2_3_22b_distilled_transformer_only_fp8'].filename,
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
        value='The Joker looks at the camera and talks, he says "You know what clownheads. This scene is not from the movie. Its from LTX 2 point 3". \n\nThen the Joker stands up with an LTX soda can in his hand. \n\nHe drinks from the soda can, and then he says "Ahhh...  with a bit of LTX and Snickers, my mood changed. Lets all be friends." \n\nThen he laughs.\n',
    )
    reroute_496 = node(wf, 'Reroute', '496')
    param_INT = node(wf, 'INTConstant', '497',
        value=832,
    )
    getnode_21 = _get_node_max_size(wf, '502', )
    getnode_22 = _get_node_max_size(wf, '507', )
    getnode_23 = node(wf, 'GetNode', '508',
        widget_0='ref_image',
    )
    getnode_24 = _get_node_overlap_seconds(wf, '514', )
    reroute_2 = node(wf, 'Reroute', '528')
    getnode_25 = _get_node_ref_video(wf, '541', )
    getnode_26 = _get_node_ref_frames(wf, '542', )
    getnode_27 = _get_node_vae(wf, '555', )
    getnode_28 = _get_node_positive(wf, '572', )
    getnode_29 = _get_node_negative(wf, '573', )
    getnode_30 = _get_node_positive(wf, '576', )
    getnode_31 = _get_node_negative(wf, '577', )
    getnode_32 = _get_node_final_audio(wf, '579', )
    getnode_33 = _get_node_fps(wf, '580', )
    getnode_34 = node(wf, 'GetNode', '581',
        widget_0='final_video_blend',
    )
    # ════ INPUTS ════
    use_lora = node(wf, 'PrimitiveBoolean', '594', value=PUBLIC_INPUTS['use_lora'].default)
    getnode_35 = _get_node_clip(wf, '600', )
    getnode_36 = node(wf, 'GetNode', '602',
        widget_0='enable_promptenhance',
    )
    getnode_37 = _get_node_fps(wf, '606', )
    getnode_38 = node(wf, 'GetNode', '628',
        widget_0='final_video_cut',
    )
    getnode_39 = _get_node_ref_video(wf, '638', )
    getnode_40 = _get_node_final_audio(wf, '640', )
    getnode_41 = _get_node_fps(wf, '641', )
    load_audio_642 = node(wf, 'LoadAudio', '642',
        audio='speech_smoke.wav',
        widget_0='speech_smoke.wav',
    )
    # ════ TEXT CONDITIONING ════
    negative_prompt = node(wf, 'CLIPTextEncode', '110',
        text='text, subtitles, logo, low quality, distorted, bad anatomy, oversaturated, pixelated, low resolution, grainy, compression artifacts, jpeg artifacts, glitches, watermark, signature, copyright,  distortedsound, saturated sound, loud sound , deformed facial features, asymmetrical face, missing facial features, extra limbs, disfigured hands, blurry teeth, disfigured teeth',
        clip=get_node_215.out(0),
    )
    setnode_3 = node(wf, 'SetNode', '209',
        widget_0='ext_seconds',
        INT=param_int_211.out('VALUE'),
    )
    setnode_4 = node(wf, 'SetNode', '210',
        widget_0='fps',
        FLOAT=param_float.out('FLOAT'),
    )
    get_image_range_from_batch_306 = node(wf, 'GetImageRangeFromBatch', '306',
        widget_0=0,
        widget_1=4096,
        images=reroute_2.out(0),
        start_index=getnode_11.out(0),
    )
    vhs__load_video = node(wf, 'VHS_LoadVideo', '319',
        file='ltx_smoke_guide.mp4',
        video='ltx_smoke_guide.mp4',
        widget_0='ltx_smoke_guide.mp4',
        force_rate=getnode_6.out(0),
    )
    simple_calculator_k_j_352 = node(wf, 'SimpleCalculatorKJ', '352',
        expression='((round((a * b -1) / 8)) * 8) + 1 ',
        _extras={'variables.a': param_int_211.out('VALUE'), 'variables.b': param_float.out('FLOAT')},
    )
    simple_calculator_k_j_2 = node(wf, 'SimpleCalculatorKJ', '357',
        expression='a + b',
        _extras={'variables.a': getnode_12.out(0), 'variables.b': getnode_24.out(0)},
    )
    get_image_range_from_batch_2 = node(wf, 'GetImageRangeFromBatch', '379',
        widget_0=-1,
        widget_1=1,
        images=getnode_39.out(0),
        num_frames=getnode_15.out(0),
    )
    normalize_audio_loudness_443 = node(wf, 'NormalizeAudioLoudness', '443',
        widget_0=-16,
        audio=load_audio_642.out(0),
    )
    setnode_16 = node(wf, 'SetNode', '459',
        widget_0='upscale_model',
        LATENT_UPSCALE_MODEL=latent_upscale_model_loader_465.out(0),
    )
    setnode_17 = node(wf, 'SetNode', '460',
        widget_0='vae_audio',
        VAE=vaeloaderkj.out('AUDIO_VAE'),
    )
    setnode_18 = node(wf, 'SetNode', '461',
        widget_0='vae',
        VAE=vae_463.out('VAE'),
    )
    setnode_19 = node(wf, 'SetNode', '462',
        widget_0='clip',
        CLIP=text_encoder.out('CLIP'),
    )
    # ════ MODEL PATCH STACK ════
    lora = node(wf, 'LoraLoaderModelOnly', '464',
        lora_name='LTX\\LTX-2\\ltx-2.3-22b-distilled-lora-384.safetensors',
        strength_model=0.6,
        model=base_diffusion_model.out('MODEL'),
    )
    setnode_20 = node(wf, 'SetNode', '472',
        widget_0='vae_tiny',
        VAE=vae_2.out('VAE'),
    )
    setnode_22 = node(wf, 'SetNode', '498',
        widget_0='max_size',
        INT=param_INT.out('VALUE'),
    )
    # ════ IMAGE PREP ════
    resize_images_by_longer_edge_1 = node(wf, 'ResizeImagesByLongerEdge', '505',
        images=reroute_496.out(0),
        longer_edge=getnode_22.out(0),
    )
    image_batch_extend_with_overlap_536 = node(wf, 'ImageBatchExtendWithOverlap', '536',
        widget_0=1,
        widget_1='source',
        widget_2='perceptual_crossfade',
        new_images=reroute_2.out(0),
        overlap=getnode_26.out(0),
        source_images=getnode_25.out(0),
    )
    # ════ OUTPUT ════
    video_output_578 = node(wf, 'VHS_VideoCombine', '578',
        audio=getnode_32.out(0),
        frame_rate=getnode_33.out(0),
        images=getnode_34.out(0),
    )
    n_6002fb3c_ab34_4ad8_894e_fccaa60fd8c9 = node(wf, '6002fb3c-ab34-4ad8-894e-fccaa60fd8c9', '599',
        clip=getnode_35.out(0),
        image=getnode_23.out(0),
        string_b=primitive_string_multiline_487.out(0),
    )
    setnode_25 = node(wf, 'SetNode', '601',
        widget_0='enable_promptenhance',
        BOOLEAN=use_lora.out('BOOLEAN'),
    )
    simple_calculator_k_j_3 = node(wf, 'SimpleCalculatorKJ', '605',
        expression='((round((a * b -1) / 8)) * 8) + 1 ',
        _extras={'variables.a': param_int_2.out('VALUE'), 'variables.b': getnode_37.out(0)},
    )
    prompt_embedding_2 = node(wf, 'CLIPTextEncode', '626',
        text=' distorted sound, saturated sound, loud sound',
        clip=get_node_215.out(0),
    )
    vhs_videocombine_2 = node(wf, 'VHS_VideoCombine', '627',
        audio=getnode_40.out(0),
        frame_rate=getnode_41.out(0),
        images=getnode_38.out(0),
    )
    setnode_9 = node(wf, 'SetNode', '310',
        widget_0='ref_frames',
        INT=simple_calculator_k_j_3.out(1),
    )
    setnode_11 = node(wf, 'SetNode', '329',
        widget_0='ref_audio',
        AUDIO=normalize_audio_loudness_443.out(0),
    )
    setnode_12 = node(wf, 'SetNode', '349',
        widget_0='extended_frames',
        INT=simple_calculator_k_j_352.out(1),
    )
    vhs__video_info_1 = node(wf, 'VHS_VideoInfo', '382',
        video_info=vhs__load_video.out(3),
    )
    image_batch_multi_403 = node(wf, 'ImageBatchMulti', '403',
        widget_0=2,
        image_1=getnode_13.out(0),
        image_2=get_image_range_from_batch_306.out(0),
    )
    resize_image_mask_node_436 = node(wf, 'ResizeImageMaskNode', '436',
        resize_type='scale by multiplier',
scale_method='area',
        input=get_image_range_from_batch_2.out(0),
    )
    vhs_videoinfo_2 = node(wf, 'VHS_VideoInfo', '492',
        video_info=vhs__load_video.out(3),
    )
    # Upstream class is misspelled; do not rename.
    model_with_sage_attn = node(wf, 'PathchSageAttentionKJ', '520',
        sage_attention='disabled',
        allow_compile=False,
        model=lora.out('MODEL'),
    )
    model_sampling = node(wf, 'ModelSamplingSD3', '526',
        shift=13,
        model=getnode_14.out(0),
    )
    model_with_nag = node(wf, 'LTX2_NAG', '563',
        nag_scale=11,
        nag_alpha=0.25,
        nag_tau=2.5,
        inplace=True,
        model=getnode_14.out(0),
        nag_cond_audio=prompt_embedding_2.out('CONDITIONING'),
        nag_cond_video=negative_prompt.out('CONDITIONING'),
    )
    get_image_range_from_batch_3 = node(wf, 'GetImageRangeFromBatch', '566',
        widget_0=0,
        widget_1=1,
        images=get_image_range_from_batch_2.out(0),
    )
    setnode_24 = node(wf, 'SetNode', '574',
        widget_0='final_video_blend',
        IMAGE=image_batch_extend_with_overlap_536.out(2),
    )
    positive_prompt = node(wf, 'CLIPTextEncode', '592',
        text=n_6002fb3c_ab34_4ad8_894e_fccaa60fd8c9.out(0),
        clip=get_node_215.out(0),
    )
    basic_scheduler_164 = node(wf, 'BasicScheduler', '164',
        scheduler=1,
        steps=1,
        denoise=1,
        widget_1=8,
        model=model_sampling.out('MODEL'),
    )
    simple_calculator_k_j_4 = node(wf, 'SimpleCalculatorKJ', '384',
        expression='a / b',
        _extras={'variables.a': getnode_15.out(0), 'variables.b': vhs__video_info_1.out(5)},
    )
    setnode_14 = node(wf, 'SetNode', '451',
        widget_0='final_video_cut',
        IMAGE=image_batch_multi_403.out(0),
    )
    simple_calculator_k_j_5 = node(wf, 'SimpleCalculatorKJ', '500',
        expression='(a > c) or (b > c) ',
        _extras={'variables.a': vhs_videoinfo_2.out(8), 'variables.b': vhs_videoinfo_2.out(9), 'variables.c': getnode_21.out(0)},
    )
    get_image_range_from_batch_4 = node(wf, 'GetImageRangeFromBatch', '556',
        widget_0=-1,
        widget_1=1,
        images=resize_image_mask_node_436.out(0),
    )
    vaeencode_1 = node(wf, 'VAEEncode', '565',
        pixels=resize_image_mask_node_436.out(0),
        vae=getnode_3.out(0),
    )
    setnode_23 = node(wf, 'SetNode', '567',
        widget_0='ref_image_overlap',
        IMAGE=get_image_range_from_batch_3.out(0),
    )
    simple_calculator_k_j_6 = node(wf, 'SimpleCalculatorKJ', '386',
        expression='a - b',
        _extras={'variables.a': vhs__video_info_1.out(7), 'variables.b': simple_calculator_k_j_4.out(0)},
    )
    setnode_13 = node(wf, 'SetNode', '397',
        widget_0='overlap_seconds',
        FLOAT=simple_calculator_k_j_4.out(0),
    )
    lazy_switch_k_j_504 = node(wf, 'LazySwitchKJ', '504',
        widget_0=False,
        on_false=reroute_496.out(0),
        on_true=resize_images_by_longer_edge_1.out(0),
        switch=simple_calculator_k_j_5.out(2),
    )
    model_chunked_ffn = node(wf, 'LTXVChunkFeedForward', '522',
        chunks=2,
        dim_threshold=4096,
        model=model_with_sage_attn.out('MODEL'),
    )
    vaeencode_2_2 = node(wf, 'VAEEncode', '546',
        pixels=get_image_range_from_batch_4.out(0),
        vae=getnode_27.out(0),
    )
    trim_audio_duration_377 = node(wf, 'TrimAudioDuration', '377',
        widget_0=0,
        widget_1=60,
        audio=normalize_audio_loudness_443.out(0),
        duration=simple_calculator_k_j_4.out(0),
        start_index=simple_calculator_k_j_6.out(0),
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
    ltxvaudio_vaeencode = node(wf, 'LTXVAudioVAEEncode', '179',
        audio=trim_audio_duration_377.out(0),
        audio_vae=getnode_2.out(0),
    )
    setnode_21 = node(wf, 'SetNode', '481',
        widget_0='model',
        MODEL=model_attention_tuned.out('MODEL'),
    )
    resized_image = node(wf, 'ImageResizeKJv2', '512',
        
        upscale_method='lanczos',
        keep_proportion='crop',
        pad_color='0, 0, 0',
        crop_position='center',
        divisible_by=64,
        device='cpu',
        height=get_image_size_and_count_506.out(2),
        image=get_image_size_and_count_506.out(0),
        width=get_image_size_and_count_506.out(1),
    )
    ltxvaudio_video_mask = node(wf, 'LTXVAudioVideoMask', '178',
        widget_0=24,
        widget_1=0,
        widget_2=15,
        widget_3=0,
        widget_4=15,
        widget_5='pad',
        widget_6='add',
        audio_end_time=simple_calculator_k_j_2.out(0),
        audio_latent=ltxvaudio_vaeencode.out(0),
        audio_start_time=getnode_24.out(0),
        video_end_time=simple_calculator_k_j_2.out(0),
        video_fps=getnode_8.out(0),
        video_latent=vaeencode_1.out('LATENT'),
        video_start_time=getnode_24.out(0),
    )
    set_node_207 = node(wf, 'SetNode', '207',
        widget_0='width',
        INT=resized_image.out(1),
    )
    setnode_2 = node(wf, 'SetNode', '208',
        widget_0='height',
        INT=resized_image.out(2),
    )
    setnode_10 = node(wf, 'SetNode', '328',
        widget_0='ref_video',
        IMAGE=resized_image.out('IMAGE'),
    )
    get_image_range_from_batch_5 = node(wf, 'GetImageRangeFromBatch', '440',
        widget_0=0,
        widget_1=1,
        images=resized_image.out('IMAGE'),
    )
    resize_images_by_longer_edge_495 = node(wf, 'ResizeImagesByLongerEdge', '495',
        longer_edge=1536,
        images=get_image_range_from_batch_5.out(0),
    )
    ltxvadd_latent_guide = node(wf, 'LTXVAddLatentGuide', '545',
        widget_0=-1,
        widget_1=1,
        guiding_latent=vaeencode_2_2.out('LATENT'),
        latent=ltxvaudio_video_mask.out(0),
        negative=negative_prompt.out('CONDITIONING'),
        positive=positive_prompt.out('CONDITIONING'),
        vae=getnode_27.out(0),
    )
    conditioning = node(wf, 'LTXVConditioning', '107',
        frame_rate=getnode_7.out(0),
        negative=ltxvadd_latent_guide.out(1),
        positive=ltxvadd_latent_guide.out(0),
    )
    av_latent_109 = node(wf, 'LTXVConcatAVLatent', '109',
        audio_latent=ltxvaudio_video_mask.out(1),
        video_latent=ltxvadd_latent_guide.out(2),
    )
    setnode_8 = node(wf, 'SetNode', '294',
        widget_0='ref_image',
        IMAGE=resize_images_by_longer_edge_495.out(0),
    )
    preprocessed_image = node(wf, 'LTXVPreprocess', '299',
        img_compression=18,
        image=resize_images_by_longer_edge_495.out(0),
    )
    cfg_guider_129 = node(wf, 'CFGGuider', '129',
        cfg=2.5,
        model=model_with_nag.out('MODEL'),
        negative=conditioning.out('NEGATIVE'),
        positive=conditioning.out('POSITIVE'),
    )
    setnode_5 = node(wf, 'SetNode', '224',
        widget_0='positive',
        CONDITIONING=conditioning.out('POSITIVE'),
    )
    setnode_6 = node(wf, 'SetNode', '225',
        widget_0='negative',
        CONDITIONING=conditioning.out('NEGATIVE'),
    )
    setnode_7 = node(wf, 'SetNode', '285',
        widget_0='compress_image',
        IMAGE=preprocessed_image.out('OUTPUT_IMAGE'),
    )
    sampled_latent_113 = node(wf, 'SamplerCustomAdvanced', '113',
        guider=cfg_guider_129.out('GUIDER'),
        latent_image=av_latent_109.out('LATENT'),
        noise=noise_115.out('NOISE'),
        sampler=sampler_kind_137.out('SAMPLER'),
        sigmas=basic_scheduler_164.out(0),
    )
    av_latent_separated_1 = node(wf, 'LTXVSeparateAVLatent', '250',
        av_latent=sampled_latent_113.out('OUTPUT'),
    )
    cropped_latent_549 = node(wf, 'LTXVCropGuides', '549',
        latent=av_latent_separated_1.out('VIDEO_LATENT'),
        negative=getnode_29.out(0),
        positive=getnode_28.out(0),
    )
    cfg_guider_2 = node(wf, 'CFGGuider', '256',
        cfg=2.5,
        model=model_with_nag.out('MODEL'),
        negative=cropped_latent_549.out(1),
        positive=cropped_latent_549.out('LATENT'),
    )
    ltxvimg_to_video_inplace = node(wf, 'LTXVImgToVideoInplace', '438',
        widget_0=1,
        widget_1=False,
        image=getnode_19.out(0),
        latent=cropped_latent_549.out(2),
        vae=getnode_20.out(0),
    )
    av_latent_2 = node(wf, 'LTXVConcatAVLatent', '251',
        audio_latent=av_latent_separated_1.out('AUDIO_LATENT'),
        video_latent=ltxvimg_to_video_inplace.out(0),
    )
    sampled_latent_2 = node(wf, 'SamplerCustomAdvanced', '258',
        guider=cfg_guider_2.out('GUIDER'),
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
    cropped_latent_2 = node(wf, 'LTXVCropGuides', '569',
        latent=av_latent_separated_125.out('VIDEO_LATENT'),
        negative=getnode_31.out(0),
        positive=getnode_30.out(0),
    )
    trim_audio_duration_2 = node(wf, 'TrimAudioDuration', '394',
        widget_0=0,
        widget_1=2048,
        audio=decoded_audio.out(0),
        start_index=getnode_17.out(0),
    )
    decoded_image = node(wf, 'VAEDecode', '527',
        samples=cropped_latent_2.out(2),
        vae=getnode_5.out(0),
    )
    audio_concat_393 = node(wf, 'AudioConcat', '393',
        widget_0='after',
        audio1=getnode_16.out(0),
        audio2=trim_audio_duration_2.out(0),
    )
    setnode_15 = node(wf, 'SetNode', '453',
        widget_0='final_audio',
        AUDIO=audio_concat_393.out(0),
    )

    return finalize(
        wf,
        PUBLIC_INPUTS,
        READY_METADATA,
        output_node='',
        source_path=__file__,
    )

