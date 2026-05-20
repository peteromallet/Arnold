# vibecomfy: generated — converted by tools/convert_ready_templates.py
# Edits will be overwritten on regeneration. Add a `# vibecomfy: manual`
# marker on the first line if hand-editing is required.
"""Music Video Multiscene with LTX 23 Video VAE Bf 16 VAE.

Public inputs:
    use_lora: Lightning LoRA branch toggle

Output: unknown.

Source:  workflow_corpus/custom_nodes/ltxvideo/runexx/LTX-2.3_Music_Video_Creator_Low_RAM.json

Packs:   ComfyUI-GGUF, ComfyUI-KJNodes, ComfyUI-LTXVideo, ComfyUI-VideoHelperSuite, rgthree-comfy
"""
from __future__ import annotations

from vibecomfy.workflow import VibeWorkflow
from vibecomfy.templates import InputSpec, ModelAsset, ReadyMetadata, finalize, new_workflow, node

def _get_node_vae(wf, _id, **overrides):
    kwargs = dict(widget_0='vae')
    kwargs.update(overrides)
    return node(wf, 'GetNode', _id, **kwargs)
def _get_node_audio_original(wf, _id, **overrides):
    kwargs = dict(widget_0='audio_original')
    kwargs.update(overrides)
    return node(wf, 'GetNode', _id, **kwargs)
def _get_node_height(wf, _id, **overrides):
    kwargs = dict(widget_0='height')
    kwargs.update(overrides)
    return node(wf, 'GetNode', _id, **kwargs)
def _get_node_width(wf, _id, **overrides):
    kwargs = dict(widget_0='width')
    kwargs.update(overrides)
    return node(wf, 'GetNode', _id, **kwargs)
def _get_node_clip(wf, _id, **overrides):
    kwargs = dict(widget_0='clip')
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
def _get_node_negative_base(wf, _id, **overrides):
    kwargs = dict(widget_0='negative_base')
    kwargs.update(overrides)
    return node(wf, 'GetNode', _id, **kwargs)
def _get_node_positive_base(wf, _id, **overrides):
    kwargs = dict(widget_0='positive_base')
    kwargs.update(overrides)
    return node(wf, 'GetNode', _id, **kwargs)
def _get_node_model(wf, _id, **overrides):
    kwargs = dict(widget_0='model')
    kwargs.update(overrides)
    return node(wf, 'GetNode', _id, **kwargs)
def _get_node_initial_frames_count(wf, _id, **overrides):
    kwargs = dict(widget_0='initial_frames_count')
    kwargs.update(overrides)
    return node(wf, 'GetNode', _id, **kwargs)
def _get_node_foldername(wf, _id, **overrides):
    kwargs = dict(widget_0='foldername')
    kwargs.update(overrides)
    return node(wf, 'GetNode', _id, **kwargs)
def _primitive_float(wf, _id, **overrides):
    kwargs = dict(value=8)
    kwargs.update(overrides)
    return node(wf, 'PrimitiveFloat', _id, **kwargs)
def _primitive_boolean(wf, _id, **overrides):
    kwargs = dict(value=True)
    kwargs.update(overrides)
    return node(wf, 'PrimitiveBoolean', _id, **kwargs)
def _primitive_int(wf, _id, **overrides):
    kwargs = dict(value=5,
                  widget_1='fixed')
    kwargs.update(overrides)
    return node(wf, 'PrimitiveInt', _id, **kwargs)
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
    'use_lora': InputSpec(node='2116', field='value', default=False, type='BOOLEAN', description='Lightning LoRA branch toggle.'),
}

READY_METADATA = ReadyMetadata.build(
    template_id='ltx2_3_runexx_music_video_low_ram',
    capability='music_video_multiscene',
    inputs=PUBLIC_INPUTS,
    models=MODELS,
    output_prefix='',
    requirements={'custom_nodes': ['ComfyUI-GGUF', 'ComfyUI-KJNodes', 'ComfyUI-LTXVideo', 'ComfyUI-VideoHelperSuite', 'rgthree-comfy'], 'custom_node_refs': [{'slug': 'ComfyUI-GGUF', 'source': 'git',
                       'commit': '6ea2651e7df66d7585f6ffee804b20e92fb38b8a', 'url': 'https://github.com/city96/ComfyUI-GGUF.git'}, {'slug': 'ComfyUI-KJNodes', 'source': 'git', 'commit': 'b7646ad70a7daa7aeb919ca542274758d26ba2df', 'url': 'https://github.com/kijai/ComfyUI-KJNodes.git'}, {'slug': 'ComfyUI-LTXVideo', 'source': 'git',
                       'commit': '229437c6b65796d6a7a63ae34be2bd5ba31fa543', 'url': 'https://github.com/Lightricks/ComfyUI-LTXVideo.git'}, {'slug': 'ComfyUI-VideoHelperSuite', 'source': 'git',
                       'commit': '4ee72c065db22c9d96c2427954dc69e7b908444b', 'url': 'https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite.git'}, {'slug': 'rgthree-comfy', 'source': 'git',
                       'commit': '738105af5fb14e96fbecaf406dc356e284797e8c', 'url': 'https://github.com/rgthree/rgthree-comfy.git'}]},
    provenance={'approach': 'low-RAM multi-scene music video', 'source_role': 'materialized_ready_python_template', 'smoke_resolution': '256x256x5_frames', 'source_workflow': 'workflow_corpus/custom_nodes/ltxvideo/runexx/LTX-2.3_Music_Video_Creator_Low_RAM.json'},
    coverage_tier='supplemental',
    ltx_best_practices=['Use the official Lightricks workflows as runtime gates where possible.', 'Patch smoke runs to fp8/fp4 model assets, tiny frame counts, and low-VRAM loaders.', 'Bypass latent spatial upscalers in smoke runs until HiddenSwitch Comfy exposes model_mmap_residency for LatentUpscaleModelManageable.', 'Keep community audio, lip-sync, and long-form workflows as ready templates until their custom node packs and service credentials are declared.'],
    comfy_configuration={'reserve_vram': 12, 'cache_none': True, 'fp8_e4m3fn_text_enc': True},
    vibecomfy_version='0.1.0',
    comfy_core={'version': '0.18.2', 'tested_at': '2026-05-20T09:19:32.302139+00:00', 'commit': 'f7b38d2eb97207cd834bcc3eb2e8b1d447b96c68', 'status': 'discovered'},
)

def build() -> VibeWorkflow:
    """Build the workflow (auto-generated)."""
    wf = new_workflow(READY_METADATA, source_path=__file__)

    get_node_236 = _get_node_vae(wf, '236', )
    getnode_2 = _get_node_vae(wf, '413', )
    # ════ SAMPLING ════
    input_image_444 = node(wf, 'LoadImage', '444',
        image='download (8).png',
)
    getnode_3 = _get_node_audio_original(wf, '582', )
    param_int_1527 = node(wf, 'INTConstant', '1527',
        value=1000,
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
    param_float_1586 = _primitive_float(wf, '1586', )
    param_INT = node(wf, 'INTConstant', '1591',
        value=480,
    )
    load_audio_1594 = node(wf, 'LoadAudio', '1594',
        audio='ComfyUI_00152_.mp3',
    )
    getnode_4 = _get_node_height(wf, '1595', )
    getnode_5 = node(wf, 'GetNode', '1597',
        widget_0='vae_audio',
    )
    mel_band_ro_former_model_loader_1600 = node(wf, 'MelBandRoFormerModelLoader', '1600',
        widget_0='MelBandRoformer\\MelBandRoformer_fp16.safetensors',
    )
    getnode_6 = _get_node_width(wf, '1601', )
    param_INT_2 = node(wf, 'INTConstant', '1606',
        value=832,
    )
    getnode_7 = _get_node_clip(wf, '1622', )
    primitive_string_multiline_1624 = node(wf, 'PrimitiveStringMultiline', '1624',
        value='Make this image come alive with fluid motion. Cinematic music video shot of a red haired woman. \n\nShe sings with expressive motion and gesticulation. \nThe song she is singing is a sweet slow melancolic melody. Her lips moves in perfect lip-sync to the attached audio.  \n\nShe is walking through a mystical dreamy forrest, tracking camera as she walks towards the viewer. \nThe camera pulls away slowly keeping same distance to the woman. \n\nCinematic, volumetric lights, shadow play. \n\nIMPORTANT: The woman is singing, and her lips are moving with lip-sync to the lyrics of the song.',
    )
    getnode_8 = _get_node_width(wf, '1628', )
    getnode_9 = _get_node_height(wf, '1629', )
    getnode_10 = node(wf, 'GetNode', '1635',
        widget_0='frames',
    )
    getnode_11 = _get_node_fps(wf, '1636', )
    getnode_12 = node(wf, 'GetNode', '1654',
        widget_0='window_sec_01',
    )
    primitivefloat_2 = _primitive_float(wf, '1722', )
    primitive_string_multiline_2 = node(wf, 'PrimitiveStringMultiline', '1805',
        value='Make this image come alive with fluid motion. Cinematic music video shot of a red haired woman. \n\nShe sings with expressive motion and gesticulation. \nThe song she is singing is a sweet slow melancolic melody. Her lips moves in perfect lip-sync to the attached audio.  \n\nShe is walking through a romantic greenhouse with flowers and warm light, tracking camera as she walks towards the viewer.\n\nShe sings the lyrics: "I type a whisper, watch it bloom. In pixel fog and quiet rooms. A hundred frames begin to breathe. While melodies I couldn’t weave" \n\nCinematic, volumetric lights, shadow play.\n\nIMPORTANT: The woman is singing, and her lips are moving with lip-sync to the lyrics of the song.',
    )
    primitivefloat_3 = _primitive_float(wf, '1997', )
    primitivefloat_4 = _primitive_float(wf, '2012', )
    getnode_13 = _get_node_clip(wf, '2110', )
    getnode_14 = node(wf, 'GetNode', '2111',
        widget_0='enhance_prompt',
    )
    getnode_15 = _get_node_ref_image(wf, '2113', )
    # ════ INPUTS ════
    use_lora = node(wf, 'PrimitiveBoolean', '2116', value=PUBLIC_INPUTS['use_lora'].default)
    getnode_16 = _get_node_vae(wf, '2151', )
    getnode_17 = node(wf, 'GetNode', '2152',
        widget_0='upscale_model',
    )
    getnode_18 = _get_node_negative_base(wf, '2154', )
    getnode_19 = _get_node_positive_base(wf, '2155', )
    getnode_20 = _get_node_ref_image(wf, '2157', )
    getnode_21 = _get_node_positive_base(wf, '2161', )
    getnode_22 = _get_node_positive_base(wf, '2162', )
    getnode_23 = node(wf, 'GetNode', '2164',
        widget_0='vae_tiny',
    )
    getnode_24 = node(wf, 'GetNode', '2165',
        widget_0='model_with_lora',
    )
    getnode_25 = _get_node_model(wf, '2166', )
    getnode_26 = _get_node_negative_base(wf, '2167', )
    noise_2169 = node(wf, 'RandomNoise', '2169',
        noise_seed=420,
        control_after_generate='fixed',
    )
    getnode_27 = _get_node_model(wf, '2171', )
    getnode_28 = _get_node_model(wf, '2172', )
    sampler_kind_2174 = node(wf, 'KSamplerSelect', '2174',
        sampler_name='euler_cfg_pp',
    )
    sigmas_2176 = node(wf, 'ManualSigmas', '2176',
        sigmas='0.85, 0.7250, 0.4219, 0.0',
    )
    noise_2 = node(wf, 'RandomNoise', '2179',
        noise_seed=42,
        control_after_generate='fixed',
    )
    sampler_kind_2 = node(wf, 'KSamplerSelect', '2180',
        sampler_name='euler_ancestral_cfg_pp',
    )
    sigmas_2 = node(wf, 'ManualSigmas', '2187',
        sigmas='1.0, 0.99375, 0.9875, 0.98125, 0.975, 0.909375, 0.725, 0.421875, 0.0',
    )
    getnode_29 = _get_node_ref_image(wf, '2190', )
    getnode_30 = node(wf, 'GetNode', '2191',
        widget_0='width_downscaled',
    )
    getnode_31 = node(wf, 'GetNode', '2192',
        widget_0='height_downscaled',
    )
    getnode_32 = node(wf, 'GetNode', '2198',
        widget_0='image_strength',
    )
    param_int_2284 = _primitive_int(wf, '2284', )
    n_5e410bb1_405a_4d3d_808b_8f5f29426943 = node(wf, '5e410bb1-405a-4d3d-808b-8f5f29426943', '3877')
    param_string = node(wf, 'PrimitiveString', '4119', value='mynewvideo')
    getnode_33 = _get_node_initial_frames_count(wf, '4204', )
    getnode_34 = _get_node_fps(wf, '4710', )
    getnode_35 = _get_node_foldername(wf, '4711', )
    getnode_36 = node(wf, 'GetNode', '4724',
        widget_0='temp_name',
    )
    getnode_37 = _get_node_fps(wf, '4727', )
    getnode_38 = _get_node_foldername(wf, '4728', )
    getnode_39 = _get_node_fps(wf, '4729', )
    primitiveboolean_2 = _primitive_boolean(wf, '4736', )
    primitiveboolean_3 = _primitive_boolean(wf, '4740', )
    input_image_2 = node(wf, 'LoadImage', '4750',
        image='download (1).png',
)
    getnode_40 = _get_node_foldername(wf, '5065', )
    getnode_41 = _get_node_fps(wf, '5066', )
    primitiveboolean_4 = _primitive_boolean(wf, '5067', )
    primitive_string_multiline_3 = node(wf, 'PrimitiveStringMultiline', '5068',
        value='Make this image come alive with fluid motion. Cinematic music video shot of a red haired woman. \n\nShe sings with expressive motion and gesticulation. \nThe song she is singing is a sweet slow melancolic melody. Her lips moves in perfect lip-sync to the attached audio.  \n\nShe is sitting down at the stage at an abandoned teather.  The camera slowly orbits around the woman, the woman is always looking at the viewer.\n\nShe sings the lyrics: "Now rise from weights, unchained and free.\nLike open doors for you and me.\nAnd every node connects the light. To hands that build without a figh.  No locked gates, just open skies.Where anyone can close their eyes…".\n\n\nCinematic, volumetric lights, shadow play.\n\nIMPORTANT: The woman is singing, and her lips are moving with lip-sync to the lyrics of the song.',
    )
    getnode_42 = _get_node_initial_frames_count(wf, '5070', )
    primitivefloat_5 = _primitive_float(wf, '5071', )
    primitiveint_2 = _primitive_int(wf, '5072', )
    input_image_3 = node(wf, 'LoadImage', '5074',
        image='download (6).png',
)
    getnode_43 = _get_node_foldername(wf, '5140', )
    getnode_44 = _get_node_fps(wf, '5141', )
    primitiveboolean_5 = _primitive_boolean(wf, '5142', )
    primitive_string_multiline_4 = node(wf, 'PrimitiveStringMultiline', '5143',
        value='Make this image come alive with fluid motion. Cinematic music video shot of a red haired woman. \n\nShe sings with expressive motion and gesticulation. \nThe song she is singing is a sweet slow melancolic melody. Her lips moves in perfect lip-sync to the attached audio.  \n\nShe is sitting down at a piece of drift-wood at the beach, at dusk. Soft light from a cloudy sky. \n\n\nShe sings the lyrics: " … and dream. Oh, AceStep XL, you paint my dreams. ComfyUI, you stitch the seams. Of every film, each trembling tone. Where lonely sparks now feel at home".\n\nShe sings for a bit before she stands up and walks towards the viewer. \n\nThe camera slowly pulls in closer to the woman singing. \n\n\nCinematic, volumetric lights, shadow play.\n\nIMPORTANT: The woman is singing, and her lips are moving with lip-sync to the lyrics of the song.',
    )
    getnode_45 = _get_node_initial_frames_count(wf, '5145', )
    primitivefloat_6 = _primitive_float(wf, '5146', )
    primitiveint_3 = _primitive_int(wf, '5147', )
    input_image_4 = node(wf, 'LoadImage', '5149',
        image='download (2).png',
)
    getnode_46 = _get_node_foldername(wf, '5215', )
    getnode_47 = _get_node_fps(wf, '5216', )
    primitiveboolean_6 = _primitive_boolean(wf, '5217', )
    primitive_string_multiline_5 = node(wf, 'PrimitiveStringMultiline', '5218',
        value='Make this image come alive with fluid motion. Cinematic music video shot of a red haired woman. \n\nShe sings with expressive motion and gesticulation. \nThe song she is singing is a sweet slow melancolic melody. Her lips moves in perfect lip-sync to the attached audio.  \n\nShe is standing on a rooftop balcony with the city behind her, at night. Camera slowly orbits around her, with her always looking towards the viewer as she sings. \n\nShe sings the lyrics: "Thank you, Kijai, for the quiet grace. That smoothed the path through digital space. We dream in code, we dream in blue. And every open door leads through.......". \n\nThe camera slowly pulls in closer to the woman singing. \n\n\nCinematic, volumetric lights, shadow play.\n\nIMPORTANT: The woman is singing, and her lips are moving with lip-sync to the lyrics of the song.',
    )
    getnode_48 = _get_node_initial_frames_count(wf, '5220', )
    primitivefloat_7 = _primitive_float(wf, '5221', )
    primitiveint_4 = _primitive_int(wf, '5222', )
    input_image_5 = node(wf, 'LoadImage', '5224',
        image='download (12).png',
)
    getnode_49 = node(wf, 'GetNode', '5226',
        widget_0='final_frames',
    )
    getnode_50 = _get_node_audio_original(wf, '5227', )
    empty_video_latent = node(wf, 'EmptyLTXVLatentVideo', '344',
        batch_size=1,
        
        
        width=getnode_30.out(0),
        height=getnode_31.out(0),
        length=getnode_10.out(0),
    )
    # ════ IMAGE PREP ════
    resized_image = node(wf, 'ImageResizeKJv2', '445',
        
        upscale_method='lanczos',
        keep_proportion='crop',
        pad_color='0, 0, 0',
        crop_position='center',
        divisible_by=2,
        device='cpu',
        height=getnode_9.out(0),
        image=input_image_444.out('IMAGE'),
        width=getnode_8.out(0),
    )
    preprocessed_image = node(wf, 'LTXVPreprocess', '446',
        img_compression=18,
        image=getnode_29.out(0),
    )
    setnode_4 = node(wf, 'SetNode', '1528',
        widget_0='start_seed',
        INT=param_int_1527.out('VALUE'),
    )
    setnode_5 = node(wf, 'SetNode', '1555',
        widget_0='upscale_model',
        LATENT_UPSCALE_MODEL=latent_upscale_model_loader_1561.out(0),
    )
    setnode_6 = node(wf, 'SetNode', '1556',
        widget_0='vae_audio',
        VAE=vaeloaderkj.out('AUDIO_VAE'),
    )
    setnode_7 = node(wf, 'SetNode', '1557',
        widget_0='vae',
        VAE=vae_1559.out('VAE'),
    )
    setnode_8 = node(wf, 'SetNode', '1558',
        widget_0='clip',
        CLIP=text_encoder.out('CLIP'),
    )
    # ════ MODEL PATCH STACK ════
    lora = node(wf, 'LoraLoaderModelOnly', '1560',
        lora_name='LTX\\LTX-2\\ltx-2.3-22b-distilled-lora-384.safetensors',
        strength_model=0.6,
        model=base_diffusion_model.out('MODEL'),
    )
    setnode_9 = node(wf, 'SetNode', '1568',
        widget_0='vae_tiny',
        VAE=vae_2.out('VAE'),
    )
    setnode_10 = node(wf, 'SetNode', '1575',
        widget_0='height',
        INT=param_INT.out('VALUE'),
    )
    setnode_11 = node(wf, 'SetNode', '1576',
        widget_0='width',
        INT=param_INT_2.out('VALUE'),
    )
    setnode_12 = node(wf, 'SetNode', '1577',
        widget_0='fps',
        FLOAT=param_float_1586.out('FLOAT'),
    )
    trim_audio_duration_1598 = node(wf, 'TrimAudioDuration', '1598',
        widget_0=11,
        widget_1=40,
        audio=load_audio_1594.out(0),
        duration=n_5e410bb1_405a_4d3d_808b_8f5f29426943.out(0),
    )
    solid_mask_1604 = node(wf, 'SolidMask', '1604',
        widget_0=0,
        widget_1=512,
        widget_2=512,
        height=getnode_4.out(0),
        width=getnode_6.out(0),
    )
    # ════ TEXT CONDITIONING ════
    negative_prompt = node(wf, 'CLIPTextEncode', '1626',
        text='text, subtitles, logo, still image, still video, no motion, static, frozen, blurry, low quality, distorted, bad anatomy, oversaturated, pixelated, low resolution, grainy, compression artifacts, jpeg artifacts, glitches, watermark, signature, copyright,  distortedsound, saturated sound, loud sound , deformed facial features, asymmetrical face, missing facial features, extra limbs, disfigured hands, blurry teeth, disfigured teeth',
        clip=getnode_7.out(0),
    )
    simple_calculator_k_j_1651 = node(wf, 'SimpleCalculatorKJ', '1651',
        expression='((round((a * b -1) / 8)) * 8) + 1 ',
        _extras={'variables.a': primitivefloat_4.out('FLOAT'), 'variables.b': param_float_1586.out('FLOAT')},
    )
    setnode_22 = node(wf, 'SetNode', '1738',
        widget_0='image_strength',
        FLOAT=primitivefloat_2.out('FLOAT'),
    )
    n_3bd4eeb9_31fa_461a_8c04_2b24dd0aabaf = node(wf, '3bd4eeb9-31fa-461a-8c04-2b24dd0aabaf', '2109',
        _1=primitive_string_multiline_1624.out(0),
        clip=getnode_13.out(0),
        image=getnode_15.out(0),
    )
    setnode_25 = node(wf, 'SetNode', '2115',
        widget_0='enhance_prompt',
        BOOLEAN=use_lora.out('BOOLEAN'),
    )
    # Stage 1 (REFINE): NAG model (bypasses patch stack) + base conditioning
    # Stage 2 (FINISH): IC-LoRA model (full patch chain)   + guided conditioning
    cfg_guider_2170 = node(wf, 'CFGGuider', '2170',
        cfg=2.5,
        model=getnode_25.out(0),
        negative=getnode_21.out(0),
        positive=getnode_22.out(0),
    )
    model_sampling_2175 = node(wf, 'ModelSamplingSD3', '2175',
        shift=13,
        model=getnode_27.out(0),
    )
    cfg_guider_2 = node(wf, 'CFGGuider', '2177',
        cfg=2.5,
        model=getnode_27.out(0),
        negative=getnode_18.out(0),
        positive=getnode_19.out(0),
    )
    modelsamplingsd3_2 = node(wf, 'ModelSamplingSD3', '2185',
        shift=13,
        model=getnode_28.out(0),
    )
    setnode_28 = node(wf, 'SetNode', '2196',
        widget_0='sampler',
        SAMPLER=sampler_kind_2.out('SAMPLER'),
    )
    setnode_30 = node(wf, 'SetNode', '2314',
        widget_0='sigmas_2',
        SIGMAS=sigmas_2176.out('SIGMAS'),
    )
    setnode_31 = node(wf, 'SetNode', '2315',
        widget_0='sampler_2',
        SAMPLER=sampler_kind_2174.out('SAMPLER'),
    )
    setnode_32 = node(wf, 'SetNode', '2325',
        widget_0='window_sec_02',
        FLOAT=primitivefloat_3.out('FLOAT'),
    )
    c4106aee_ad7a_4925_972b_6f5b3d34db6e_2329 = node(wf, 'c4106aee-ad7a-4925-972b-6f5b3d34db6e', '2329',
        _1=primitive_string_multiline_2.out(0),
        _2=primitivefloat_3.out('FLOAT'),
        _4=getnode_33.out(0),
        images=input_image_2.out('IMAGE'),
        noise_seed=param_int_2284.out('INT'),
    )
    setnode_33 = node(wf, 'SetNode', '3722',
        widget_0='window_sec_01',
        FLOAT=primitivefloat_4.out('FLOAT'),
    )
    string_concatenate_4164 = node(wf, 'StringConcatenate', '4164',
        widget_0='MusicVideo',
        widget_1='',
        widget_2='\\',
        string_b=param_string.out(0),
    )
    string_concatenate_2 = node(wf, 'StringConcatenate', '4743',
        widget_0='output\\MusicVideo',
        widget_1='',
        widget_2='\\',
        string_b=getnode_36.out(0),
    )
    setnode_37 = node(wf, 'SetNode', '4995',
        widget_0='sigmas',
        SIGMAS=sigmas_2.out('SIGMAS'),
    )
    setnode_38 = node(wf, 'SetNode', '5064',
        widget_0='window_sec_03',
        FLOAT=primitivefloat_5.out('FLOAT'),
    )
    setnode_39 = node(wf, 'SetNode', '5139',
        widget_0='window_sec_04',
        FLOAT=primitivefloat_6.out('FLOAT'),
    )
    setnode_40 = node(wf, 'SetNode', '5214',
        widget_0='window_sec_05',
        FLOAT=primitivefloat_7.out('FLOAT'),
    )
    setnode_41 = node(wf, 'SetNode', '5225',
        widget_0='temp_name',
        STRING=param_string.out(0),
    )
    simple_calculator_k_j_2 = node(wf, 'SimpleCalculatorKJ', '5228',
        expression='a + 100',
        _extras={'variables.a': getnode_49.out(0)},
    )
    # Upstream class is misspelled; do not rename.
    model_with_sage_attn = node(wf, 'PathchSageAttentionKJ', '268',
        sage_attention='disabled',
        allow_compile=False,
        model=lora.out('MODEL'),
    )
    setnode_13 = node(wf, 'SetNode', '1578',
        widget_0='frames',
        INT=simple_calculator_k_j_1651.out(1),
    )
    setnode_14 = node(wf, 'SetNode', '1589',
        widget_0='audio_original',
        AUDIO=trim_audio_duration_1598.out(0),
    )
    mel_band_ro_former_sampler_1599 = node(wf, 'MelBandRoFormerSampler', '1599',
        audio=trim_audio_duration_1598.out(0),
        model=mel_band_ro_former_model_loader_1600.out(0),
    )
    positive_prompt = node(wf, 'CLIPTextEncode', '1621',
        text=n_3bd4eeb9_31fa_461a_8c04_2b24dd0aabaf.out(0),
        clip=getnode_7.out(0),
    )
    resize_image_mask_node_1630 = node(wf, 'ResizeImageMaskNode', '1630',
        resize_type='scale by multiplier',
scale_method='area',
        input=resized_image.out('IMAGE'),
    )
    basic_scheduler_2173 = node(wf, 'BasicScheduler', '2173',
        scheduler=1,
        steps=1,
        denoise=1,
        widget_1=4,
        model=model_sampling_2175.out('MODEL'),
    )
    model_with_nag = node(wf, 'LTX2_NAG', '2178',
        nag_scale=11,
        nag_alpha=0.25,
        nag_tau=2.5,
        inplace=True,
        model=getnode_24.out(0),
        nag_cond_audio=getnode_26.out(0),
        nag_cond_video=getnode_26.out(0),
    )
    basic_scheduler_2 = node(wf, 'BasicScheduler', '2186',
        scheduler=1,
        steps=1,
        denoise=1,
        widget_1=10,
        model=modelsamplingsd3_2.out('MODEL'),
    )
    resize_images_by_longer_edge_2189 = node(wf, 'ResizeImagesByLongerEdge', '2189',
        longer_edge=1536,
        images=resized_image.out('IMAGE'),
    )
    setnode_27 = node(wf, 'SetNode', '2195',
        widget_0='guider',
        GUIDER=cfg_guider_2170.out('GUIDER'),
    )
    setnode_29 = node(wf, 'SetNode', '2313',
        widget_0='guider_2',
        GUIDER=cfg_guider_2.out('GUIDER'),
    )
    ltxvimg_to_video_inplace_1 = node(wf, 'LTXVImgToVideoInplace', '4109',
        widget_0=1,
        widget_1=False,
        image=preprocessed_image.out('OUTPUT_IMAGE'),
        latent=empty_video_latent.out('LATENT'),
        vae=getnode_2.out(0),
    )
    load_videos_from_folder_4708 = node(wf, 'LoadVideosFromFolder', '4708',
        widget_0='output\\MusicVideo',
        widget_1=0,
        widget_2=0,
        widget_3=0,
        widget_4=0,
        widget_5=0,
        widget_6=1,
        widget_7='batch',
        widget_8=4,
        widget_9=False,
        frame_load_cap=simple_calculator_k_j_2.out(1),
        video=string_concatenate_2.out(0),
    )
    # ════ OUTPUT ════
    video_output_4709 = node(wf, 'VHS_VideoCombine', '4709',
        audio=c4106aee_ad7a_4925_972b_6f5b3d34db6e_2329.out(2),
        filename_prefix=getnode_35.out(0),
        frame_rate=getnode_34.out(0),
        images=c4106aee_ad7a_4925_972b_6f5b3d34db6e_2329.out(1),
        save_output=primitiveboolean_2.out('BOOLEAN'),
    )
    string_concatenate_3 = node(wf, 'StringConcatenate', '4735',
        widget_0='MusicVideo',
        widget_1='MusicVideo',
        widget_2='\\',
        string_a=string_concatenate_4164.out(0),
    )
    n_17238add_9973_482f_8fa3_248d4ed29886 = node(wf, '17238add-9973-482f-8fa3-248d4ed29886', '5073',
        _1=primitive_string_multiline_3.out(0),
        _2=primitivefloat_5.out('FLOAT'),
        _4=c4106aee_ad7a_4925_972b_6f5b3d34db6e_2329.out(0),
        images=input_image_3.out('IMAGE'),
        noise_seed=primitiveint_2.out('INT'),
    )
    conditioning = node(wf, 'LTXVConditioning', '164',
        frame_rate=getnode_11.out(0),
        negative=negative_prompt.out('CONDITIONING'),
        positive=positive_prompt.out('CONDITIONING'),
    )
    model_chunked_ffn = node(wf, 'LTXVChunkFeedForward', '504',
        chunks=2,
        dim_threshold=4096,
        model=model_with_sage_attn.out('MODEL'),
    )
    setnode_3 = node(wf, 'SetNode', '650',
        widget_0='ref_image',
        IMAGE=resize_images_by_longer_edge_2189.out(0),
    )
    setnode_15 = node(wf, 'SetNode', '1590',
        widget_0='audio_vocals',
        AUDIO=mel_band_ro_former_sampler_1599.out(0),
    )
    switch = node(wf, 'ComfySwitchNode', '1616',
        widget_0=True,
        on_false=trim_audio_duration_1598.out(0),
        on_true=mel_band_ro_former_sampler_1599.out(0),
    )
    get_image_size_1631 = node(wf, 'GetImageSize', '1631',
        image=resize_image_mask_node_1630.out(0),
    )
    setnode_26 = node(wf, 'SetNode', '2184',
        widget_0='model',
        MODEL=model_with_nag.out('MODEL'),
    )
    setnode_34 = node(wf, 'SetNode', '4121',
        widget_0='foldername',
        STRING=string_concatenate_3.out(0),
    )
    vhs_videocombine_2 = node(wf, 'VHS_VideoCombine', '4725',
        audio=getnode_50.out(0),
        frame_rate=getnode_37.out(0),
        images=load_videos_from_folder_4708.out(0),
    )
    vhs_videocombine_4 = node(wf, 'VHS_VideoCombine', '5069',
        audio=n_17238add_9973_482f_8fa3_248d4ed29886.out(2),
        filename_prefix=getnode_40.out(0),
        frame_rate=getnode_41.out(0),
        images=n_17238add_9973_482f_8fa3_248d4ed29886.out(1),
        save_output=primitiveboolean_4.out('BOOLEAN'),
    )
    a3fb563d_4711_4225_9210_fbe61b1bd79d_5148 = node(wf, 'a3fb563d-4711-4225-9210-fbe61b1bd79d', '5148',
        _1=primitive_string_multiline_4.out(0),
        _2=primitivefloat_6.out('FLOAT'),
        _4=n_17238add_9973_482f_8fa3_248d4ed29886.out(0),
        images=input_image_4.out('IMAGE'),
        noise_seed=primitiveint_3.out('INT'),
    )
    set_node_645 = node(wf, 'SetNode', '645',
        widget_0='positive_base',
        CONDITIONING=conditioning.out('POSITIVE'),
    )
    setnode_2 = node(wf, 'SetNode', '646',
        widget_0='negative_base',
        CONDITIONING=conditioning.out('NEGATIVE'),
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
    setnode_17 = node(wf, 'SetNode', '1615',
        widget_0='audio',
        AUDIO=switch.out('OUTPUT'),
    )
    setnode_19 = node(wf, 'SetNode', '1633',
        widget_0='width_downscaled',
        INT=get_image_size_1631.out(0),
    )
    setnode_20 = node(wf, 'SetNode', '1634',
        widget_0='height_downscaled',
        INT=get_image_size_1631.out(1),
    )
    trim_audio_duration_2 = node(wf, 'TrimAudioDuration', '1653',
        widget_0=0,
        widget_1=40,
        audio=switch.out('OUTPUT'),
        duration=getnode_12.out(0),
    )
    vhs_videocombine_5 = node(wf, 'VHS_VideoCombine', '5144',
        audio=a3fb563d_4711_4225_9210_fbe61b1bd79d_5148.out(2),
        filename_prefix=getnode_43.out(0),
        frame_rate=getnode_44.out(0),
        images=a3fb563d_4711_4225_9210_fbe61b1bd79d_5148.out(1),
        save_output=primitiveboolean_5.out('BOOLEAN'),
    )
    n_4acc9924_c0bd_470a_b000_46c75e61d004 = node(wf, '4acc9924-c0bd-470a-b000-46c75e61d004', '5223',
        _1=primitive_string_multiline_5.out(0),
        _2=primitivefloat_7.out('FLOAT'),
        _4=a3fb563d_4711_4225_9210_fbe61b1bd79d_5148.out(0),
        images=input_image_5.out('IMAGE'),
        noise_seed=primitiveint_4.out('INT'),
    )
    ltxvaudio_vaeencode = node(wf, 'LTXVAudioVAEEncode', '1605',
        audio=trim_audio_duration_2.out(0),
        audio_vae=getnode_5.out(0),
    )
    power_lora_loader__rgthree_ = node(wf, 'Power Lora Loader (rgthree)', '2150',
        widget_7='',
        model=model_attention_tuned.out('MODEL'),
    )
    setnode_36 = node(wf, 'SetNode', '4733',
        widget_0='final_frames',
        INT=n_4acc9924_c0bd_470a_b000_46c75e61d004.out(0),
    )
    vhs_videocombine_6 = node(wf, 'VHS_VideoCombine', '5219',
        audio=n_4acc9924_c0bd_470a_b000_46c75e61d004.out(2),
        filename_prefix=getnode_46.out(0),
        frame_rate=getnode_47.out(0),
        images=n_4acc9924_c0bd_470a_b000_46c75e61d004.out(1),
        save_output=primitiveboolean_6.out('BOOLEAN'),
    )
    set_latent_noise_mask_1603 = node(wf, 'SetLatentNoiseMask', '1603',
        mask=solid_mask_1604.out(0),
        samples=ltxvaudio_vaeencode.out(0),
    )
    setnode_18 = node(wf, 'SetNode', '1617',
        widget_0='model_with_lora',
        MODEL=power_lora_loader__rgthree_.out(0),
    )
    av_latent_350 = node(wf, 'LTXVConcatAVLatent', '350',
        audio_latent=set_latent_noise_mask_1603.out(0),
        video_latent=ltxvimg_to_video_inplace_1.out(0),
    )
    setnode_16 = node(wf, 'SetNode', '1602',
        widget_0='latent_custom_audio',
        LATENT=set_latent_noise_mask_1603.out(0),
    )
    sampled_latent_2181 = node(wf, 'SamplerCustomAdvanced', '2181',
        guider=cfg_guider_2170.out('GUIDER'),
        latent_image=av_latent_350.out('LATENT'),
        noise=noise_2.out('NOISE'),
        sampler=sampler_kind_2.out('SAMPLER'),
        sigmas=sigmas_2.out('SIGMAS'),
    )
    av_latent_separated_1 = node(wf, 'LTXVSeparateAVLatent', '2159',
        av_latent=sampled_latent_2181.out('OUTPUT'),
    )
    ltxvimg_to_video_inplace_2 = node(wf, 'LTXVImgToVideoInplace', '2183',
        widget_0=1,
        widget_1=False,
        image=getnode_20.out(0),
        latent=av_latent_separated_1.out('VIDEO_LATENT'),
        strength=getnode_32.out(0),
        vae=getnode_16.out(0),
    )
    av_latent_2 = node(wf, 'LTXVConcatAVLatent', '2153',
        audio_latent=av_latent_separated_1.out('AUDIO_LATENT'),
        video_latent=ltxvimg_to_video_inplace_2.out(0),
    )
    sampled_latent_2 = node(wf, 'SamplerCustomAdvanced', '2182',
        guider=cfg_guider_2.out('GUIDER'),
        latent_image=av_latent_2.out('LATENT'),
        noise=noise_2169.out('NOISE'),
        sampler=sampler_kind_2174.out('SAMPLER'),
        sigmas=sigmas_2176.out('SIGMAS'),
    )
    av_latent_separated_245 = node(wf, 'LTXVSeparateAVLatent', '245',
        av_latent=sampled_latent_2.out('OUTPUT'),
    )
    # ════ DECODE ════
    decoded_image = node(wf, 'VAEDecode', '1318',
        samples=av_latent_separated_245.out('VIDEO_LATENT'),
        vae=get_node_236.out(0),
    )
    get_image_size_and_count_2023 = node(wf, 'GetImageSizeAndCount', '2023',
        image=decoded_image.out('IMAGE'),
    )
    vram__debug = node(wf, 'VRAM_Debug', '4184',
        widget_0=True,
        widget_1=True,
        widget_2=False,
        image_pass=decoded_image.out('IMAGE'),
    )
    vhs_videocombine_3 = node(wf, 'VHS_VideoCombine', '4730',
        audio=getnode_3.out(0),
        filename_prefix=getnode_38.out(0),
        frame_rate=getnode_39.out(0),
        images=decoded_image.out('IMAGE'),
        save_output=primitiveboolean_3.out('BOOLEAN'),
    )
    setnode_23 = node(wf, 'SetNode', '1938',
        widget_0='height_generated',
        INT=get_image_size_and_count_2023.out(2),
    )
    setnode_24 = node(wf, 'SetNode', '1939',
        widget_0='width_generated',
        INT=get_image_size_and_count_2023.out(1),
    )
    get_image_size_and_count_2 = node(wf, 'GetImageSizeAndCount', '4199',
        image=vram__debug.out(1),
    )
    setnode_21 = node(wf, 'SetNode', '1716',
        widget_0='initial_frames',
        IMAGE=get_image_size_and_count_2.out(0),
    )
    setnode_35 = node(wf, 'SetNode', '4203',
        widget_0='initial_frames_count',
        INT=get_image_size_and_count_2.out(3),
    )

    return finalize(
        wf,
        PUBLIC_INPUTS,
        READY_METADATA,
        output_node='',
        source_path=__file__,
    )

