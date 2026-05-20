# vibecomfy: generated — converted by tools/convert_ready_templates.py
# Edits will be overwritten on regeneration. Add a `# vibecomfy: manual`
# marker on the first line if hand-editing is required.
"""Tts Talking Avatar with LTX 23 Video VAE Bf 16 VAE.

Public inputs:
    use_lora: Lightning LoRA branch toggle

Output: unknown.

Source:  workflow_corpus/custom_nodes/ltxvideo/runexx/LTX-2.3_Talking_Avatar_Qwen_TTS.json

Packs:   ComfyUI-GGUF, ComfyUI-KJNodes, ComfyUI-LTXVideo, ComfyUI-QwenTTS, ComfyUI-VideoHelperSuite, rgthree-comfy
"""
from __future__ import annotations

from vibecomfy.workflow import VibeWorkflow
from vibecomfy.templates import InputSpec, ModelAsset, ReadyMetadata, finalize, new_workflow, node

def _get_node_vae(wf, _id, **overrides):
    kwargs = dict(widget_0='vae')
    kwargs.update(overrides)
    return node(wf, 'GetNode', _id, **kwargs)
def _get_node_clip(wf, _id, **overrides):
    kwargs = dict(widget_0='clip')
    kwargs.update(overrides)
    return node(wf, 'GetNode', _id, **kwargs)
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
def _get_node_ref_image(wf, _id, **overrides):
    kwargs = dict(widget_0='ref_image')
    kwargs.update(overrides)
    return node(wf, 'GetNode', _id, **kwargs)
def _get_node_vae_audio(wf, _id, **overrides):
    kwargs = dict(widget_0='vae_audio')
    kwargs.update(overrides)
    return node(wf, 'GetNode', _id, **kwargs)
def _get_node_negative(wf, _id, **overrides):
    kwargs = dict(widget_0='negative')
    kwargs.update(overrides)
    return node(wf, 'GetNode', _id, **kwargs)
def _get_node_positive(wf, _id, **overrides):
    kwargs = dict(widget_0='positive')
    kwargs.update(overrides)
    return node(wf, 'GetNode', _id, **kwargs)
def _get_node_t2v_mode(wf, _id, **overrides):
    kwargs = dict(widget_0='t2v_mode')
    kwargs.update(overrides)
    return node(wf, 'GetNode', _id, **kwargs)
def _get_node_model(wf, _id, **overrides):
    kwargs = dict(widget_0='model')
    kwargs.update(overrides)
    return node(wf, 'GetNode', _id, **kwargs)
def _get_node_model_with_lora(wf, _id, **overrides):
    kwargs = dict(widget_0='model_with_lora')
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
    'use_lora': InputSpec(node='1862', field='value', default=False, type='BOOLEAN', description='Lightning LoRA branch toggle.'),
}

READY_METADATA = ReadyMetadata.build(
    template_id='ltx2_3_runexx_talking_avatar_qwen_tts',
    capability='tts_talking_avatar',
    inputs=PUBLIC_INPUTS,
    models=MODELS,
    output_prefix='',
    requirements={'custom_nodes': ['ComfyUI-GGUF', 'ComfyUI-KJNodes', 'ComfyUI-LTXVideo', 'ComfyUI-QwenTTS', 'ComfyUI-VideoHelperSuite', 'rgthree-comfy'], 'custom_node_refs': [{'slug': 'ComfyUI-GGUF', 'source': 'git',
                       'commit': '6ea2651e7df66d7585f6ffee804b20e92fb38b8a', 'url': 'https://github.com/city96/ComfyUI-GGUF.git'}, {'slug': 'ComfyUI-KJNodes', 'source': 'git', 'commit': 'b7646ad70a7daa7aeb919ca542274758d26ba2df', 'url': 'https://github.com/kijai/ComfyUI-KJNodes.git'}, {'slug': 'ComfyUI-LTXVideo', 'source': 'git',
                       'commit': '229437c6b65796d6a7a63ae34be2bd5ba31fa543', 'url': 'https://github.com/Lightricks/ComfyUI-LTXVideo.git'}, {'slug': 'ComfyUI-QwenTTS', 'source': 'git', 'commit': 'd8122a8ba835b65fd65c113d2b273b1ad1579293', 'url': 'https://github.com/1038lab/ComfyUI-QwenTTS.git'}, {'slug': 'ComfyUI-VideoHelperSuite', 'source': 'git',
                       'commit': '4ee72c065db22c9d96c2427954dc69e7b908444b', 'url': 'https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite.git'}, {'slug': 'rgthree-comfy', 'source': 'git',
                       'commit': '738105af5fb14e96fbecaf406dc356e284797e8c', 'url': 'https://github.com/rgthree/rgthree-comfy.git'}]},
    provenance={'source_role': 'materialized_ready_python_template', 'source_workflow': 'workflow_corpus/custom_nodes/ltxvideo/runexx/LTX-2.3_Talking_Avatar_Qwen_TTS.json', 'smoke_resolution': '256x256x5_frames', 'approach': 'Qwen TTS talking avatar'},
    coverage_tier='supplemental',
    ltx_best_practices=['Use the official Lightricks workflows as runtime gates where possible.', 'Patch smoke runs to fp8/fp4 model assets, tiny frame counts, and low-VRAM loaders.', 'Bypass latent spatial upscalers in smoke runs until HiddenSwitch Comfy exposes model_mmap_residency for LatentUpscaleModelManageable.', 'Keep community audio, lip-sync, and long-form workflows as ready templates until their custom node packs and service credentials are declared.'],
    comfy_configuration={'reserve_vram': 12, 'cache_none': True, 'fp8_e4m3fn_text_enc': True},
    vibecomfy_version='0.1.0',
    comfy_core={'version': '0.18.2', 'tested_at': '2026-05-20T09:19:32.302139+00:00', 'commit': 'f7b38d2eb97207cd834bcc3eb2e8b1d447b96c68', 'status': 'discovered'},
)

def build() -> VibeWorkflow:
    """Build the workflow (auto-generated)."""
    wf = new_workflow(READY_METADATA, source_path=__file__)

    get_node_413 = _get_node_vae(wf, '413', )
    # ════ SAMPLING ════
    input_image = node(wf, 'LoadImage', '444',
        image='17745317855d08.png',
)
    # ════ LOADERS ════
    vae_1559 = node(wf, 'VAELoader', '1559',
        vae_name=MODELS['ltx23_video_vae_bf16_vae'].filename,
    )
    # ════ LATENT ════
    latent_upscale_model_loader_1561 = node(wf, 'LatentUpscaleModelLoader', '1561',
        model_name='ltx-2.3-spatial-upscaler-x2-1.1.safetensors',
    )
    text_encoder = node(wf, 'DualCLIPLoader', '1562',
        clip_name1=MODELS['gemma_clip'].filename,
        clip_name2=MODELS['ltx_2_3_text_projection_bf16_clip'].filename,
        type='ltxv',
        device='default',
    )
    vaeloaderkj = node(wf, 'LTXVAudioVAELoader', '1567',
        ckpt_name='LTX23_audio_vae_bf16.safetensors',
    )
    vae_2 = node(wf, 'VAELoader', '1569',
        vae_name=MODELS['taeltx2_3_vae'].filename,
    )
    base_diffusion_model = node(wf, 'UNETLoader', '1570',
        unet_name=MODELS['ltx_2_3_22b_distilled_transformer_only_fp8'].filename,
        weight_dtype='default',
    )
    unet_loader_gguf = node(wf, 'UnetLoaderGGUF', '1571',
        unet_name='LTXvideo\\LTX-2\\quantstack\\LTX-2.3-distilled-Q4_K_S.gguf',
    )
    dual_cliploader_gguf = node(wf, 'DualCLIPLoaderGGUF', '1573',
        clip_name1=MODELS['gemma_clip_2'].filename,
        clip_name2=MODELS['ltx_2_3_text_projection_bf16_clip'].filename,
        type='sdxl',
    )
    param_int_1583 = node(wf, 'INTConstant', '1583',
        value=10,
    )
    param_float = node(wf, 'PrimitiveFloat', '1586', value=8)
    param_INT = node(wf, 'INTConstant', '1591',
        value=960,
    )
    param_INT_2 = node(wf, 'INTConstant', '1606',
        value=544,
    )
    getnode_2 = _get_node_clip(wf, '1619', )
    getnode_3 = _get_node_clip(wf, '1622', )
    primitive_string_multiline_1624 = node(wf, 'PrimitiveStringMultiline', '1624',
        value="A video from a TV broadcast with a male and a female news achor. They both stay in frame all the time.\n\nThe dialog from the male and female is as follows:\n\nSpaker_1 is the woman, and Speaker_2 is the man.\n\n[speaker_1][confused]: This is awkward! I guess the prompter ran out of ideas, and put us in this odd situation.\n[speaker_2][embarrassed] : But hey,  just because we are here, in a new video, doesn't mean our voices change. \n[speaker_1][excited]: Aber ich möchte mit dir schlafen.\n[speaker_2][happy]: I still have no idea what she said! Might be for the best [laughing]\n\nThe dialog with perfect lip-sync to the audio\n\n\nThey both smile at the end.\n\n\n",
    )
    getnode_4 = _get_node_width(wf, '1628', )
    getnode_5 = _get_node_height(wf, '1629', )
    getnode_6 = node(wf, 'GetNode', '1635',
        widget_0='frames',
    )
    getnode_7 = _get_node_fps(wf, '1636', )
    getnode_8 = node(wf, 'GetNode', '1784',
        widget_0='audio_tts',
    )
    getnode_9 = node(wf, 'GetNode', '1807',
        widget_0='height_downscaled',
    )
    getnode_10 = node(wf, 'GetNode', '1808',
        widget_0='width_downscaled',
    )
    getnode_11 = _get_node_ref_image(wf, '1809', )
    getnode_12 = _get_node_vae(wf, '1814', )
    getnode_13 = _get_node_vae_audio(wf, '1815', )
    getnode_14 = _get_node_vae(wf, '1816', )
    getnode_15 = node(wf, 'GetNode', '1817',
        widget_0='upscale_model',
    )
    getnode_16 = _get_node_negative(wf, '1820', )
    getnode_17 = _get_node_positive(wf, '1821', )
    getnode_18 = _get_node_fps(wf, '1822', )
    getnode_19 = _get_node_t2v_mode(wf, '1823', )
    getnode_20 = _get_node_ref_image(wf, '1824', )
    getnode_21 = _get_node_model(wf, '1828', )
    getnode_22 = _get_node_negative(wf, '1829', )
    getnode_23 = _get_node_positive(wf, '1830', )
    getnode_24 = _get_node_model_with_lora(wf, '1831', )
    noise_1832 = node(wf, 'RandomNoise', '1832',
        noise_seed=420,
        control_after_generate='fixed',
    )
    getnode_25 = node(wf, 'GetNode', '1833',
        widget_0='vae_tiny',
    )
    getnode_26 = _get_node_model_with_lora(wf, '1834', )
    getnode_27 = _get_node_model(wf, '1835', )
    getnode_28 = _get_node_model(wf, '1841', )
    noise_2 = node(wf, 'RandomNoise', '1842',
        noise_seed=42,
        control_after_generate='fixed',
    )
    getnode_29 = _get_node_negative(wf, '1843', )
    sigmas_1851 = node(wf, 'ManualSigmas', '1851',
        sigmas='0.85, 0.7250, 0.4219, 0.0',
    )
    sampler_kind_1852 = node(wf, 'KSamplerSelect', '1852',
        sampler_name='euler_cfg_pp',
    )
    sampler_kind_2 = node(wf, 'KSamplerSelect', '1853',
        sampler_name='euler_ancestral_cfg_pp',
    )
    getnode_30 = node(wf, 'GetNode', '1855',
        widget_0='latent',
    )
    sigmas_2 = node(wf, 'ManualSigmas', '1857',
        sigmas='1.0, 0.99375, 0.9875, 0.98125, 0.975, 0.909375, 0.725, 0.421875, 0.0',
    )
    # ════ INPUTS ════
    use_lora = node(wf, 'PrimitiveBoolean', '1862', value=PUBLIC_INPUTS['use_lora'].default)
    reroute_1865 = node(wf, 'Reroute', '1865')
    getnode_31 = _get_node_model(wf, '1878', )
    getnode_32 = _get_node_height(wf, '1887', )
    getnode_33 = _get_node_width(wf, '1888', )
    getnode_34 = _get_node_vae_audio(wf, '1889', )
    getnode_35 = node(wf, 'GetNode', '1894',
        widget_0='latent_custom_audio',
    )
    getnode_36 = _get_node_fps(wf, '1898', )
    use_BOOLEAN = node(wf, 'PrimitiveBoolean', '1929', value=True)
    getnode_37 = node(wf, 'GetNode', '1931',
        widget_0='enhance_prompt',
    )
    getnode_38 = _get_node_t2v_mode(wf, '1935', )
    mel_band_ro_former_model_loader_1937 = node(wf, 'MelBandRoFormerModelLoader', '1937',
        widget_0='MelBandRoformer\\MelBandRoformer_fp16.safetensors',
    )
    primitive_string_multiline_2 = node(wf, 'PrimitiveStringMultiline', '1938',
        value='',
    )
    load_audio_1941 = node(wf, 'LoadAudio', '1941',
        audio='d1b26d5a32db420183fa17af9c699278.mp3',
    )
    primitive_string_multiline_3 = node(wf, 'PrimitiveStringMultiline', '1942',
        value='So what if you just want to prompt. Text to video works fine as well. Go generate some while I enjoy my coffee. ',
    )
    empty_video_latent = node(wf, 'EmptyLTXVLatentVideo', '344',
        batch_size=1,
        
        
        width=getnode_10.out(0),
        height=getnode_9.out(0),
        length=getnode_6.out(0),
    )
    # ════ IMAGE PREP ════
    resized_image = node(wf, 'ImageResizeKJv2', '445',
        
        upscale_method='lanczos',
        keep_proportion='crop',
        pad_color='0, 0, 0',
        crop_position='center',
        divisible_by=2,
        device='cpu',
        height=getnode_5.out(0),
        image=input_image.out('IMAGE'),
        width=getnode_4.out(0),
    )
    preprocessed_image = node(wf, 'LTXVPreprocess', '446',
        img_compression=18,
        image=getnode_11.out(0),
    )
    setnode_4 = node(wf, 'SetNode', '1555',
        widget_0='upscale_model',
        LATENT_UPSCALE_MODEL=latent_upscale_model_loader_1561.out(0),
    )
    setnode_5 = node(wf, 'SetNode', '1556',
        widget_0='vae_audio',
        VAE=vaeloaderkj.out('AUDIO_VAE'),
    )
    setnode_6 = node(wf, 'SetNode', '1557',
        widget_0='vae',
        VAE=vae_1559.out('VAE'),
    )
    setnode_7 = node(wf, 'SetNode', '1558',
        widget_0='clip',
        CLIP=text_encoder.out('CLIP'),
    )
    # ════ MODEL PATCH STACK ════
    lora = node(wf, 'LoraLoaderModelOnly', '1560',
        lora_name='LTX\\LTX-2\\ltx-2.3-22b-distilled-lora-384.safetensors',
        strength_model=0.6,
        model=base_diffusion_model.out('MODEL'),
    )
    setnode_8 = node(wf, 'SetNode', '1568',
        widget_0='vae_tiny',
        VAE=vae_2.out('VAE'),
    )
    setnode_9 = node(wf, 'SetNode', '1575',
        widget_0='height',
        INT=param_INT.out('VALUE'),
    )
    setnode_10 = node(wf, 'SetNode', '1576',
        widget_0='width',
        INT=param_INT_2.out('VALUE'),
    )
    setnode_11 = node(wf, 'SetNode', '1577',
        widget_0='fps',
        FLOAT=param_float.out('FLOAT'),
    )
    # ════ TEXT CONDITIONING ════
    negative_prompt = node(wf, 'CLIPTextEncode', '1626',
        text='text, subtitles, logo, still image, still video, no motion, static, frozen, blurry, low quality, distorted, bad anatomy, oversaturated, pixelated, low resolution, grainy, compression artifacts, jpeg artifacts, glitches, watermark, signature, copyright,  distortedsound, saturated sound, loud sound , deformed facial features, asymmetrical face, missing facial features, extra limbs, disfigured hands, blurry teeth, disfigured teeth',
        clip=getnode_3.out(0),
    )
    # Stage 1 (REFINE): NAG model (bypasses patch stack) + base conditioning
    # Stage 2 (FINISH): IC-LoRA model (full patch chain)   + guided conditioning
    cfg_guider_1836 = node(wf, 'CFGGuider', '1836',
        cfg=2.5,
        model=getnode_27.out(0),
        negative=getnode_16.out(0),
        positive=getnode_17.out(0),
    )
    cfg_guider_2 = node(wf, 'CFGGuider', '1856',
        cfg=2.5,
        model=getnode_28.out(0),
        negative=getnode_22.out(0),
        positive=getnode_23.out(0),
    )
    setnode_19 = node(wf, 'SetNode', '1861',
        widget_0='t2v_mode',
        BOOLEAN=use_lora.out('BOOLEAN'),
    )
    model_sampling_1876 = node(wf, 'ModelSamplingSD3', '1876',
        shift=13,
        model=getnode_31.out(0),
    )
    solid_mask_1890 = node(wf, 'SolidMask', '1890',
        widget_0=0,
        widget_1=512,
        widget_2=512,
        height=getnode_32.out(0),
        width=getnode_33.out(0),
    )
    ltxvaudio_vaeencode = node(wf, 'LTXVAudioVAEEncode', '1893',
        audio=reroute_1865.out(0),
        audio_vae=getnode_34.out(0),
    )
    simple_calculator_k_j_1897 = node(wf, 'SimpleCalculatorKJ', '1897',
        expression='((round((a * b -1) / 8)) * 8) + 1 ',
        _extras={'variables.a': param_int_1583.out('VALUE'), 'variables.b': getnode_36.out(0)},
    )
    modelsamplingsd3_2 = node(wf, 'ModelSamplingSD3', '1912',
        shift=13,
        model=getnode_27.out(0),
    )
    n_63e8c999_0a69_4f62_af3f_8b77f0095971 = node(wf, '63e8c999-0a69-4f62-af3f-8b77f0095971', '1920',
        audio=reroute_1865.out(0),
    )
    setnode_22 = node(wf, 'SetNode', '1930',
        widget_0='enhance_prompt',
        BOOLEAN=use_BOOLEAN.out('BOOLEAN'),
    )
    trim_audio_duration_1939 = node(wf, 'TrimAudioDuration', '1939',
        widget_0=0,
        widget_1=15,
        audio=load_audio_1941.out(0),
    )
    # Upstream class is misspelled; do not rename.
    model_with_sage_attn = node(wf, 'PathchSageAttentionKJ', '268',
        sage_attention='disabled',
        allow_compile=False,
        model=lora.out('MODEL'),
    )
    setnode_3 = node(wf, 'SetNode', '650',
        widget_0='ref_image',
        IMAGE=resized_image.out('IMAGE'),
    )
    setnode_12 = node(wf, 'SetNode', '1578',
        widget_0='frames',
        _extras={'*': n_63e8c999_0a69_4f62_af3f_8b77f0095971.out(0)},
    )
    resize_image_mask_node_1630 = node(wf, 'ResizeImageMaskNode', '1630',
        resize_type='scale by multiplier',
scale_method='area',
        input=resized_image.out('IMAGE'),
    )
    model_with_nag = node(wf, 'LTX2_NAG', '1844',
        nag_scale=11,
        nag_alpha=0.25,
        nag_tau=2.5,
        inplace=True,
        model=getnode_26.out(0),
        nag_cond_audio=getnode_29.out(0),
        nag_cond_video=getnode_29.out(0),
    )
    sampled_latent_1 = node(wf, 'SamplerCustomAdvanced', '1845',
        guider=cfg_guider_2.out('GUIDER'),
        latent_image=getnode_30.out(0),
        noise=noise_2.out('NOISE'),
        sampler=sampler_kind_2.out('SAMPLER'),
        sigmas=sigmas_2.out('SIGMAS'),
    )
    basic_scheduler_1877 = node(wf, 'BasicScheduler', '1877',
        scheduler=1,
        steps=1,
        denoise=1,
        widget_1=8,
        model=model_sampling_1876.out('MODEL'),
    )
    set_latent_noise_mask_1892 = node(wf, 'SetLatentNoiseMask', '1892',
        mask=solid_mask_1890.out(0),
        samples=ltxvaudio_vaeencode.out(0),
    )
    basic_scheduler_2 = node(wf, 'BasicScheduler', '1911',
        scheduler=1,
        steps=1,
        denoise=1,
        widget_1=4,
        model=modelsamplingsd3_2.out('MODEL'),
    )
    setnode_21 = node(wf, 'SetNode', '1918',
        widget_0='frames_seconds',
        INT=simple_calculator_k_j_1897.out(1),
    )
    ltxvimg_to_video_inplace_1 = node(wf, 'LTXVImgToVideoInplace', '1934',
        widget_0=0.7,
        widget_1=False,
        bypass=getnode_38.out(0),
        image=preprocessed_image.out('OUTPUT_IMAGE'),
        latent=empty_video_latent.out('LATENT'),
        vae=get_node_413.out(0),
    )
    mel_band_ro_former_sampler_1936 = node(wf, 'MelBandRoFormerSampler', '1936',
        audio=trim_audio_duration_1939.out(0),
        model=mel_band_ro_former_model_loader_1937.out(0),
    )
    av_latent_350 = node(wf, 'LTXVConcatAVLatent', '350',
        audio_latent=getnode_35.out(0),
        video_latent=ltxvimg_to_video_inplace_1.out(0),
    )
    model_chunked_ffn = node(wf, 'LTXVChunkFeedForward', '504',
        chunks=2,
        dim_threshold=4096,
        model=model_with_sage_attn.out('MODEL'),
    )
    get_image_size_1631 = node(wf, 'GetImageSize', '1631',
        image=resize_image_mask_node_1630.out(0),
    )
    av_latent_separated_1827 = node(wf, 'LTXVSeparateAVLatent', '1827',
        av_latent=sampled_latent_1.out('OUTPUT'),
    )
    setnode_17 = node(wf, 'SetNode', '1840',
        widget_0='model',
        MODEL=model_with_nag.out('MODEL'),
    )
    setnode_20 = node(wf, 'SetNode', '1891',
        widget_0='latent_custom_audio',
        LATENT=set_latent_noise_mask_1892.out(0),
    )
    a8d7fd9f_52aa_447a_9766_53cb91c0ef18_1926 = node(wf, 'a8d7fd9f-52aa-447a-9766-53cb91c0ef18', '1926',
        _1=primitive_string_multiline_1624.out(0),
        clip=getnode_2.out(0),
        image=resize_image_mask_node_1630.out(0),
    )
    ailab__qwen3_ttsvoice_clone = node(wf, 'AILab_Qwen3TTSVoiceClone', '1944',
        widget_0='Hello, this is a cloned voice.',
        widget_1='1.7B',
        widget_2='Auto',
        widget_3='',
        widget_4=True,
        widget_5=986337553816914,
        widget_6=116899311982882,
        widget_7='randomize',
        reference_audio=mel_band_ro_former_sampler_1936.out(0),
        reference_text=primitive_string_multiline_2.out(0),
        target_text=primitive_string_multiline_3.out(0),
    )
    model_attention_tuned = node(wf, 'LTX2AttentionTunerPatch', '1523',
        blocks='',
        video_scale=1,
        audio_scale=1,
        video_to_audio_scale=1,
        audio_to_video_scale=1,
        triton_kernels=False,
        model=model_chunked_ffn.out('MODEL'),
    )
    positive_prompt = node(wf, 'CLIPTextEncode', '1621',
        text=a8d7fd9f_52aa_447a_9766_53cb91c0ef18_1926.out(0),
        clip=getnode_3.out(0),
    )
    setnode_14 = node(wf, 'SetNode', '1633',
        widget_0='width_downscaled',
        INT=get_image_size_1631.out(0),
    )
    setnode_15 = node(wf, 'SetNode', '1634',
        widget_0='height_downscaled',
        INT=get_image_size_1631.out(1),
    )
    ltxvimg_to_video_inplace_2 = node(wf, 'LTXVImgToVideoInplace', '1825',
        widget_0=1,
        widget_1=False,
        bypass=getnode_19.out(0),
        image=getnode_20.out(0),
        latent=av_latent_separated_1827.out('VIDEO_LATENT'),
        vae=getnode_14.out(0),
    )
    setnode_18 = node(wf, 'SetNode', '1860',
        widget_0='latent',
        LATENT=av_latent_350.out('LATENT'),
    )
    audio_normalize_lufs = node(wf, 'AudioNormalizeLUFS', '1916',
        widget_0=-20,
        widget_1=0,
        widget_2=0,
        widget_3='full_track',
        audio=ailab__qwen3_ttsvoice_clone.out(0),
    )
    conditioning = node(wf, 'LTXVConditioning', '164',
        frame_rate=getnode_7.out(0),
        negative=negative_prompt.out('CONDITIONING'),
        positive=positive_prompt.out('CONDITIONING'),
    )
    power_lora_loader__rgthree_ = node(wf, 'Power Lora Loader (rgthree)', '1627',
        widget_4='',
        model=model_attention_tuned.out('MODEL'),
    )
    av_latent_2 = node(wf, 'LTXVConcatAVLatent', '1819',
        audio_latent=av_latent_separated_1827.out('AUDIO_LATENT'),
        video_latent=ltxvimg_to_video_inplace_2.out(0),
    )
    audio_enhancement_node_1904 = node(wf, 'AudioEnhancementNode', '1904',
        widget_0='manual',
        widget_1=0.7,
        widget_10=5,
        widget_11=0,
        widget_12=0,
        widget_13='full_track',
        widget_2=0.6,
        widget_3=1.3,
        widget_4=1.2,
        widget_5=1,
        widget_6=1,
        widget_7=0.5,
        widget_8='keep_original',
        widget_9=False,
        audio=audio_normalize_lufs.out(0),
    )
    set_node_645 = node(wf, 'SetNode', '645',
        widget_0='positive',
        CONDITIONING=conditioning.out('POSITIVE'),
    )
    setnode_2 = node(wf, 'SetNode', '646',
        widget_0='negative',
        CONDITIONING=conditioning.out('NEGATIVE'),
    )
    setnode_13 = node(wf, 'SetNode', '1617',
        widget_0='model_with_lora',
        MODEL=power_lora_loader__rgthree_.out(0),
    )
    setnode_16 = node(wf, 'SetNode', '1758',
        widget_0='audio_tts',
        AUDIO=audio_enhancement_node_1904.out(0),
    )
    sampled_latent_1838 = node(wf, 'SamplerCustomAdvanced', '1838',
        guider=cfg_guider_1836.out('GUIDER'),
        latent_image=av_latent_2.out('LATENT'),
        noise=noise_1832.out('NOISE'),
        sampler=sampler_kind_1852.out('SAMPLER'),
        sigmas=sigmas_1851.out('SIGMAS'),
    )
    # ════ OUTPUT ════
    preview_audio_1943 = node(wf, 'PreviewAudio', '1943',
        audio=audio_enhancement_node_1904.out(0),
    )
    av_latent_separated_2 = node(wf, 'LTXVSeparateAVLatent', '1839',
        av_latent=sampled_latent_1838.out('OUTPUT'),
    )
    # ════ DECODE ════
    decoded_video = node(wf, 'VAEDecodeTiled', '1818',
        tile_size=512,
        overlap=64,
        temporal_size=4096,
        temporal_overlap=8,
        samples=av_latent_separated_2.out('VIDEO_LATENT'),
        vae=getnode_12.out(0),
    )
    decoded_audio = node(wf, 'LTXVAudioVAEDecode', '1847',
        audio_vae=getnode_13.out(0),
        samples=av_latent_separated_2.out('AUDIO_LATENT'),
    )
    vram__debug = node(wf, 'VRAM_Debug', '1915',
        widget_0=True,
        widget_1=True,
        widget_2=True,
        image_pass=decoded_video.out('IMAGE'),
    )
    video_output = node(wf, 'VHS_VideoCombine', '1837',
        audio=decoded_audio.out(0),
        frame_rate=getnode_18.out(0),
        images=vram__debug.out(1),
    )

    return finalize(
        wf,
        PUBLIC_INPUTS,
        READY_METADATA,
        output_node='',
        source_path=__file__,
    )

