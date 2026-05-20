# vibecomfy: generated — converted by tools/convert_ready_templates.py
# Edits will be overwritten on regeneration. Add a `# vibecomfy: manual`
# marker on the first line if hand-editing is required.
"""Custom Audio To Video with LTX 23 Video VAE Bf 16 VAE.

Public inputs:
    use_lora: Lightning LoRA branch toggle

Output: unknown.

Source:  workflow_corpus/custom_nodes/ltxvideo/runexx/LTX-2.3_Custom_Audio.json

Packs:   ComfyUI-GGUF, ComfyUI-KJNodes, ComfyUI-LTXVideo, ComfyUI-VideoHelperSuite, rgthree-comfy
"""
from __future__ import annotations

from vibecomfy.workflow import VibeWorkflow
from vibecomfy.templates import InputSpec, ModelAsset, ReadyMetadata, finalize, new_workflow, node

def _get_node_frames(wf, _id, **overrides):
    kwargs = dict(widget_0='frames')
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
def _get_node_vae(wf, _id, **overrides):
    kwargs = dict(widget_0='vae')
    kwargs.update(overrides)
    return node(wf, 'GetNode', _id, **kwargs)
def _get_node_model(wf, _id, **overrides):
    kwargs = dict(widget_0='model')
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
def _get_node_width(wf, _id, **overrides):
    kwargs = dict(widget_0='width')
    kwargs.update(overrides)
    return node(wf, 'GetNode', _id, **kwargs)
def _get_node_height(wf, _id, **overrides):
    kwargs = dict(widget_0='height')
    kwargs.update(overrides)
    return node(wf, 'GetNode', _id, **kwargs)
def _get_node_model_with_lora(wf, _id, **overrides):
    kwargs = dict(widget_0='model_with_lora')
    kwargs.update(overrides)
    return node(wf, 'GetNode', _id, **kwargs)
def _get_node_fps(wf, _id, **overrides):
    kwargs = dict(widget_0='fps')
    kwargs.update(overrides)
    return node(wf, 'GetNode', _id, **kwargs)
def _get_node_t2v_mode(wf, _id, **overrides):
    kwargs = dict(widget_0='t2v_mode')
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
    'ltx_2_3_22b_distilled_transformer_only_fp8': ModelAsset(
        filename='ltx-2.3-22b-distilled_transformer_only_fp8_scaled.safetensors',
        url='',
        subdir='diffusion_models',
    ),
    'taeltx2_3_vae': ModelAsset(
        filename='taeltx2_3.safetensors',
        url='',
        subdir='vae',
    ),
    'gemma_clip_2': ModelAsset(
        filename='gemma-3-12b-it-Q2_K.gguf',
        url='',
        subdir='text_encoders',
    ),
}

PUBLIC_INPUTS = {
    'use_lora': InputSpec(node='290', field='value', default=False, type='BOOLEAN', description='Lightning LoRA branch toggle.'),
}

READY_METADATA = ReadyMetadata.build(
    template_id='ltx2_3_runexx_custom_audio',
    capability='custom_audio_to_video',
    inputs=PUBLIC_INPUTS,
    models=MODELS,
    output_prefix='',
    requirements={'custom_nodes': ['ComfyUI-GGUF', 'ComfyUI-KJNodes', 'ComfyUI-LTXVideo', 'ComfyUI-VideoHelperSuite', 'rgthree-comfy'], 'custom_node_refs': [{'slug': 'ComfyUI-GGUF', 'source': 'git',
                       'commit': '6ea2651e7df66d7585f6ffee804b20e92fb38b8a', 'url': 'https://github.com/city96/ComfyUI-GGUF.git'}, {'slug': 'ComfyUI-KJNodes', 'source': 'git', 'commit': 'b7646ad70a7daa7aeb919ca542274758d26ba2df', 'url': 'https://github.com/kijai/ComfyUI-KJNodes.git'}, {'slug': 'ComfyUI-LTXVideo', 'source': 'git',
                       'commit': '229437c6b65796d6a7a63ae34be2bd5ba31fa543', 'url': 'https://github.com/Lightricks/ComfyUI-LTXVideo.git'}, {'slug': 'ComfyUI-VideoHelperSuite', 'source': 'git',
                       'commit': '4ee72c065db22c9d96c2427954dc69e7b908444b', 'url': 'https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite.git'}, {'slug': 'rgthree-comfy', 'source': 'git',
                       'commit': '738105af5fb14e96fbecaf406dc356e284797e8c', 'url': 'https://github.com/rgthree/rgthree-comfy.git'}]},
    provenance={'approach': 'custom audio conditioning', 'smoke_resolution': '256x256x5_frames', 'source_workflow': 'workflow_corpus/custom_nodes/ltxvideo/runexx/LTX-2.3_Custom_Audio.json', 'source_role': 'materialized_ready_python_template'},
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
    sigmas_100 = node(wf, 'ManualSigmas', '100',
        sigmas='0.909375, 0.725, 0.421875, 0.0',
    )
    noise_114 = node(wf, 'RandomNoise', '114',
        noise_seed=420,
        control_after_generate='fixed',
    )
    noise_2 = node(wf, 'RandomNoise', '115',
        noise_seed=43,
        control_after_generate='fixed',
    )
    sampler_kind_137 = node(wf, 'KSamplerSelect', '137',
        sampler_name='euler_ancestral_cfg_pp',
    )
    sampler_kind_2 = node(wf, 'KSamplerSelect', '138',
        sampler_name='euler_cfg_pp',
    )
    input_image = node(wf, 'LoadImage', '167',
        image='liam-neeson-in-retribution-ra.jpg',
)
    # ════ LOADERS ════
    vae_184 = node(wf, 'VAELoader', '184',
        vae_name=MODELS['ltx23_video_vae_bf16_vae'].filename,
    )
    # ════ LATENT ════
    latent_upscale_model_loader_189 = node(wf, 'LatentUpscaleModelLoader', '189',
        model_name='ltx-2.3-spatial-upscaler-x2-1.0.safetensors',
    )
    text_encoder = node(wf, 'DualCLIPLoader', '190',
        clip_name1=MODELS['gemma_clip'].filename,
        clip_name2=MODELS['ltx_2_3_text_projection_bf16_clip'].filename,
        type='ltxv',
        device='default',
    )
    vaeloaderkj = node(wf, 'LTXVAudioVAELoader', '196',
        ckpt_name='LTX23_audio_vae_bf16.safetensors',
    )
    get_node_205 = _get_node_frames(wf, '205', )
    getnode_2 = _get_node_ref_image(wf, '210', )
    getnode_3 = _get_node_ref_image(wf, '212', )
    getnode_4 = node(wf, 'GetNode', '214',
        widget_0='clip',
    )
    getnode_5 = _get_node_vae_audio(wf, '217', )
    getnode_6 = _get_node_vae(wf, '218', )
    getnode_7 = _get_node_vae(wf, '219', )
    getnode_8 = _get_node_vae(wf, '220', )
    getnode_9 = _get_node_vae_audio(wf, '221', )
    getnode_10 = _get_node_model(wf, '225', )
    getnode_11 = _get_node_positive(wf, '228', )
    getnode_12 = _get_node_negative(wf, '229', )
    getnode_13 = _get_node_positive(wf, '230', )
    getnode_14 = _get_node_negative(wf, '231', )
    getnode_15 = node(wf, 'GetNode', '236',
        widget_0='width_downsized',
    )
    getnode_16 = node(wf, 'GetNode', '237',
        widget_0='height_downsized',
    )
    getnode_17 = node(wf, 'GetNode', '239',
        widget_0='latent',
    )
    getnode_18 = node(wf, 'GetNode', '242',
        widget_0='upscale_model',
    )
    getnode_19 = _get_node_width(wf, '243', )
    getnode_20 = _get_node_height(wf, '244', )
    param_float = node(wf, 'PrimitiveFloat', '285', value=8)
    # ════ INPUTS ════
    use_lora = node(wf, 'PrimitiveBoolean', '290', value=PUBLIC_INPUTS['use_lora'].default)
    param_int_291 = node(wf, 'INTConstant', '291',
        value=10,
    )
    param_INT = node(wf, 'INTConstant', '292',
        value=1280,
    )
    param_INT_2 = node(wf, 'INTConstant', '293',
        value=736,
    )
    getnode_21 = _get_node_model_with_lora(wf, '306', )
    getnode_22 = _get_node_fps(wf, '307', )
    getnode_23 = _get_node_t2v_mode(wf, '308', )
    getnode_24 = _get_node_t2v_mode(wf, '309', )
    getnode_25 = _get_node_fps(wf, '310', )
    getnode_26 = _get_node_fps(wf, '322', )
    base_diffusion_model = node(wf, 'UNETLoader', '329',
        unet_name=MODELS['ltx_2_3_22b_distilled_transformer_only_fp8'].filename,
        weight_dtype='default',
    )
    vae_2 = node(wf, 'VAELoader', '330',
        vae_name=MODELS['taeltx2_3_vae'].filename,
    )
    getnode_27 = node(wf, 'GetNode', '338',
        widget_0='vae_tiny',
    )
    getnode_28 = _get_node_model_with_lora(wf, '339', )
    getnode_29 = _get_node_model(wf, '341', )
    getnode_30 = _get_node_negative(wf, '343', )
    getnode_31 = _get_node_model(wf, '344', )
    unet_loader_gguf = node(wf, 'UnetLoaderGGUF', '345',
        unet_name='LTXvideo\\LTX-2\\quantstack\\LTX-2.3-distilled-Q4_K_S.gguf',
    )
    dual_cliploader_gguf = node(wf, 'DualCLIPLoaderGGUF', '346',
        clip_name1=MODELS['gemma_clip_2'].filename,
        clip_name2=MODELS['ltx_2_3_text_projection_bf16_clip'].filename,
        type='sdxl',
    )
    primitive_string_multiline_350 = node(wf, 'PrimitiveStringMultiline', '350',
        value='You are a Creative Assistant writing concise, action-focused image-to-video prompts. Given an image (first frame) and user Raw Input Prompt, generate a prompt to guide video generation from that image.\n\n#### Guidelines:\n- Analyze the Image: Identify Subject, Setting, Elements, Style and Mood.\n- Follow user Raw Input Prompt: Include all requested motion, actions, camera movements, audio, and details. If in conflict with the image, prioritize user request while maintaining visual consistency (describe transition from image to user\'s scene).\n- Describe only changes from the image: Don\'t reiterate established visual details. Inaccurate descriptions may cause scene cuts.\n- Active language: Use present-progressive verbs ("is walking," "speaking"). If no action specified, describe natural movements.\n- Chronological flow: Use temporal connectors ("as," "then," "while").\n- Audio layer: Describe complete soundscape throughout the prompt alongside actions—NOT at the end. Align audio intensity with action tempo. Include natural background audio, ambient sounds, effects, speech or music (when requested). Be specific (e.g., "soft footsteps on tile") not vague (e.g., "ambient sound").\n- Speech (only when requested): Provide exact words in quotes with character\'s visual/voice characteristics (e.g., "The tall man speaks in a low, gravelly voice"), language if not English and accent if relevant. If general conversation mentioned without text, generate contextual quoted dialogue. (i.e., "The man is talking" input -> the output should include exact spoken words, like: "The man is talking in an excited voice saying: \'You won\'t believe what I just saw!\' His hands gesture expressively as he speaks, eyebrows raised with enthusiasm. The ambient sound of a quiet room underscores his animated speech.")\n- Style: Include visual style at beginning: "Style: <style>, <rest of prompt>." If unclear, omit to avoid conflicts.\n- Visual and audio only: Describe only what is seen and heard. NO smell, taste, or tactile sensations.\n- Restrained language: Avoid dramatic terms. Use mild, natural, understated phrasing.\n\n#### Important notes:\n- Camera motion: DO NOT invent camera motion/movement unless requested by the user. Make sure to include camera motion only if specified in the input.\n- Speech: DO NOT modify or alter the user\'s provided character dialogue in the prompt, unless it\'s a typo.\n- No timestamps or cuts: DO NOT use timestamps or describe scene cuts unless explicitly requested.\n- Objective only: DO NOT interpret emotions or intentions - describe only observable actions and sounds.\n- Format: DO NOT use phrases like "The scene opens with..." / "The video starts...". Start directly with Style (optional) and chronological scene description.\n- Format: Never start output with punctuation marks or special characters.\n- DO NOT invent dialogue unless the user mentions speech/talking/singing/conversation.\n- Your performance is CRITICAL. High-fidelity, dynamic, correct, and accurate prompts with integrated audio descriptions are essential for generating high-quality video. Your goal is flawless execution of these rules.\n\n#### Output Format (Strict):\n- Single concise paragraph in natural English. NO titles, headings, prefaces, sections, code fences, or Markdown.\n- If unsafe/invalid, return original user prompt. Never ask questions or clarifications.\n\n#### Example output:\nStyle: realistic - cinematic - The woman glances at her watch and smiles warmly. She speaks in a cheerful, friendly voice, "I think we\'re right on time!" In the background, a café barista prepares drinks at the counter. The barista calls out in a clear, upbeat tone, "Two cappuccinos ready!" The sound of the espresso machine hissing softly blends with gentle background chatter and the light clinking of cups on saucers. \n\nUSER PROMPT BELOW: \n___________________________________________________',
    )
    primitive_string_multiline_2 = node(wf, 'PrimitiveStringMultiline', '352',
        value='Make this image come alive with fluid motion. \n\nA man with an intimidating expression speaks with expressive body language and gesticulations. \n\nHe looks at the vewer and talks, he says  : "If you say a bad word about LTX 2 point 3, i will find you.... and i will kill you" ',
    )
    getnode_32 = _get_node_height(wf, '359', )
    getnode_33 = _get_node_width(wf, '360', )
    getnode_34 = _get_node_vae_audio(wf, '361', )
    getnode_35 = _get_node_frames(wf, '368', )
    getnode_36 = _get_node_fps(wf, '369', )
    mel_band_ro_former_model_loader_370 = node(wf, 'MelBandRoFormerModelLoader', '370',
        widget_0='MelBandRoformer\\MelBandRoformer_fp16.safetensors',
    )
    load_audio_372 = node(wf, 'LoadAudio', '372',
        audio='ComfyUI_00128_.mp3',
    )
    getnode_37 = node(wf, 'GetNode', '374',
        widget_0='latent_audio',
    )
    getnode_38 = node(wf, 'GetNode', '375',
        widget_0='latent_custom_audio',
    )
    getnode_39 = node(wf, 'GetNode', '378',
        widget_0='org_audio',
    )
    reroute_379 = node(wf, 'Reroute', '379')
    sigmas_2 = node(wf, 'ManualSigmas', '380',
        sigmas='0.85, 0.7250, 0.4219, 0.0',
    )
    sigmas_3 = node(wf, 'ManualSigmas', '381',
        sigmas='1.0, 0.99375, 0.9875, 0.98125, 0.975, 0.909375, 0.725, 0.421875, 0.0',
    )
    # Stage 1 (REFINE): NAG model (bypasses patch stack) + base conditioning
    # Stage 2 (FINISH): IC-LoRA model (full patch chain)   + guided conditioning
    cfg_guider_103 = node(wf, 'CFGGuider', '103',
        cfg=2.5,
        model=getnode_29.out(0),
        negative=getnode_12.out(0),
        positive=getnode_11.out(0),
    )
    empty_video_latent = node(wf, 'EmptyLTXVLatentVideo', '108',
        batch_size=1,
        
        
        width=getnode_15.out(0),
        height=getnode_16.out(0),
        length=get_node_205.out(0),
    )
    # ════ TEXT CONDITIONING ════
    negative_prompt = node(wf, 'CLIPTextEncode', '110',
        text='blurry, oversaturated, pixelated, low resolution, grainy, distorted, noise, compression artifacts, jpeg artifacts, glitches, watermark, text, logo, signature, copyright, subtitles, distorted sound, saturated sound, loud',
        clip=getnode_4.out(0),
    )
    cfg_guider_2 = node(wf, 'CFGGuider', '129',
        cfg=2.5,
        model=getnode_31.out(0),
        negative=getnode_14.out(0),
        positive=getnode_13.out(0),
    )
    # ════ MODEL PATCH STACK ════
    lora = node(wf, 'LoraLoaderModelOnly', '134',
        lora_name='LTX\\LTX-2\\ltx-2.3-22b-distilled-lora-384.safetensors',
        strength_model=0.6,
        model=base_diffusion_model.out('MODEL'),
    )
    # ════ IMAGE PREP ════
    preprocessed_image = node(wf, 'LTXVPreprocess', '162',
        img_compression=33,
        image=getnode_2.out(0),
    )
    resized_image = node(wf, 'ImageResizeKJv2', '165',
        
        upscale_method='nearest-exact',
        keep_proportion='crop',
        pad_color='0, 0, 0',
        crop_position='center',
        divisible_by=32,
        device='cpu',
        height=getnode_20.out(0),
        image=input_image.out('IMAGE'),
        width=getnode_19.out(0),
    )
    set_node_188 = node(wf, 'SetNode', '188',
        widget_0='upscale_model',
        LATENT_UPSCALE_MODEL=latent_upscale_model_loader_189.out(0),
    )
    ltxvscheduler = node(wf, 'LTXVScheduler', '206',
        steps=1,
        max_shift=2.05,
        base_shift=0.95,
        stretch=True,
        terminal=0.1,
        latent=getnode_17.out(0),
    )
    setnode_4 = node(wf, 'SetNode', '213',
        widget_0='clip',
        CLIP=text_encoder.out('CLIP'),
    )
    setnode_5 = node(wf, 'SetNode', '215',
        widget_0='vae',
        VAE=vae_184.out('VAE'),
    )
    setnode_6 = node(wf, 'SetNode', '216',
        widget_0='vae_audio',
        VAE=vaeloaderkj.out('AUDIO_VAE'),
    )
    setnode_14 = node(wf, 'SetNode', '282',
        widget_0='height',
        INT=param_INT_2.out('VALUE'),
    )
    setnode_15 = node(wf, 'SetNode', '283',
        widget_0='width',
        INT=param_INT.out('VALUE'),
    )
    setnode_16 = node(wf, 'SetNode', '284',
        widget_0='fps',
        FLOAT=param_float.out('FLOAT'),
    )
    simple_calculator_k_j_287 = node(wf, 'SimpleCalculatorKJ', '287',
        expression='1+ 8*(round(a*b)/8)',
        a=param_int_291.out('VALUE'),
        b=param_float.out('FLOAT'),
    )
    setnode_18 = node(wf, 'SetNode', '288',
        widget_0='t2v_mode',
        BOOLEAN=use_lora.out('BOOLEAN'),
    )
    simple_calculator_k_j_2 = node(wf, 'SimpleCalculatorKJ', '311',
        expression='a',
        _extras={'variables.a': getnode_25.out(0)},
    )
    setnode_20 = node(wf, 'SetNode', '331',
        widget_0='vae_tiny',
        VAE=vae_2.out('VAE'),
    )
    string_concatenate_347 = node(wf, 'StringConcatenate', '347',
        widget_0='',
        widget_1='',
        widget_2='',
        string_a=primitive_string_multiline_350.out(0),
    )
    solid_mask_362 = node(wf, 'SolidMask', '362',
        widget_0=0,
        widget_1=512,
        widget_2=512,
        height=getnode_32.out(0),
        width=getnode_33.out(0),
    )
    simple_calculator_k_j_3 = node(wf, 'SimpleCalculatorKJ', '367',
        expression='a/b',
        a=getnode_35.out(0),
        b=getnode_36.out(0),
    )
    switch_376 = node(wf, 'ComfySwitchNode', '376',
        widget_0=True,
        on_false=getnode_37.out(0),
        on_true=getnode_38.out(0),
    )
    sampled_latent_113 = node(wf, 'SamplerCustomAdvanced', '113',
        guider=cfg_guider_2.out('GUIDER'),
        latent_image=getnode_17.out(0),
        noise=noise_2.out('NOISE'),
        sampler=sampler_kind_137.out('SAMPLER'),
        sigmas=sigmas_3.out('SIGMAS'),
    )
    ltxvimg_to_video_inplace_1 = node(wf, 'LTXVImgToVideoInplace', '161',
        widget_0=1,
        widget_1=False,
        bypass=getnode_23.out(0),
        image=preprocessed_image.out('OUTPUT_IMAGE'),
        latent=empty_video_latent.out('LATENT'),
        vae=getnode_6.out(0),
    )
    resize_image_mask_node_164 = node(wf, 'ResizeImageMaskNode', '164',
        resize_type='scale by multiplier',
scale_method='area',
        input=resized_image.out('IMAGE'),
    )
    empty_audio_latent = node(wf, 'LTXVEmptyLatentAudio', '199',
        
        batch_size=1,
        audio_vae=getnode_5.out(0),
        frame_rate=simple_calculator_k_j_2.out(1),
        frames_number=get_node_205.out(0),
    )
    setnode_3 = node(wf, 'SetNode', '211',
        widget_0='compress_image',
        IMAGE=preprocessed_image.out('OUTPUT_IMAGE'),
    )
    resize_images_by_longer_edge_246 = node(wf, 'ResizeImagesByLongerEdge', '246',
        longer_edge=1536,
        images=resized_image.out('IMAGE'),
    )
    setnode_17 = node(wf, 'SetNode', '286',
        widget_0='frames',
        INT=simple_calculator_k_j_287.out(1),
    )
    model_chunked_ffn = node(wf, 'LTXVChunkFeedForward', '332',
        chunks=2,
        dim_threshold=4096,
        model=lora.out('MODEL'),
    )
    model_with_nag = node(wf, 'LTX2_NAG', '342',
        nag_scale=11,
        nag_alpha=0.25,
        nag_tau=2.5,
        inplace=True,
        model=getnode_28.out(0),
        nag_cond_audio=getnode_30.out(0),
        nag_cond_video=getnode_30.out(0),
    )
    text_generate_l_t_x2_prompt_349 = node(wf, 'TextGenerateLTX2Prompt', '349',
        widget_0='',
        widget_1=256,
        widget_2='off',
        clip=getnode_4.out(0),
        image=resized_image.out('IMAGE'),
        prompt=primitive_string_multiline_2.out(0),
    )
    trim_audio_duration_373 = node(wf, 'TrimAudioDuration', '373',
        widget_0=0,
        widget_1=8,
        audio=load_audio_372.out(0),
        duration=simple_calculator_k_j_3.out(0),
    )
    av_latent_109 = node(wf, 'LTXVConcatAVLatent', '109',
        audio_latent=switch_376.out('OUTPUT'),
        video_latent=ltxvimg_to_video_inplace_1.out(0),
    )
    av_latent_separated_116 = node(wf, 'LTXVSeparateAVLatent', '116',
        av_latent=sampled_latent_113.out('OUTPUT'),
    )
    positive_prompt = node(wf, 'CLIPTextEncode', '121',
        text=text_generate_l_t_x2_prompt_349.out(0),
        clip=getnode_4.out(0),
    )
    get_image_size_163 = node(wf, 'GetImageSize', '163',
        image=resize_image_mask_node_164.out(0),
    )
    setnode_2 = node(wf, 'SetNode', '209',
        widget_0='ref_image',
        IMAGE=resize_images_by_longer_edge_246.out(0),
    )
    setnode_12 = node(wf, 'SetNode', '240',
        widget_0='latent_audio',
        LATENT=empty_audio_latent.out('LATENT'),
    )
    setnode_13 = node(wf, 'SetNode', '248',
        widget_0='resize_image',
        IMAGE=resize_image_mask_node_164.out(0),
    )
    power_lora_loader__rgthree_ = node(wf, 'Power Lora Loader (rgthree)', '301',
model=model_chunked_ffn.out('MODEL'),
    )
    setnode_21 = node(wf, 'SetNode', '340',
        widget_0='model',
        MODEL=model_with_nag.out('MODEL'),
    )
    setnode_22 = node(wf, 'SetNode', '365',
        widget_0='org_audio',
        AUDIO=trim_audio_duration_373.out(0),
    )
    mel_band_ro_former_sampler_371 = node(wf, 'MelBandRoFormerSampler', '371',
        audio=trim_audio_duration_373.out(0),
        model=mel_band_ro_former_model_loader_370.out(0),
    )
    conditioning = node(wf, 'LTXVConditioning', '107',
        frame_rate=getnode_26.out(0),
        negative=negative_prompt.out('CONDITIONING'),
        positive=positive_prompt.out('CONDITIONING'),
    )
    ltxvimg_to_video_inplace_2 = node(wf, 'LTXVImgToVideoInplace', '160',
        widget_0=1,
        widget_1=False,
        bypass=getnode_24.out(0),
        image=getnode_3.out(0),
        latent=av_latent_separated_116.out('VIDEO_LATENT'),
        vae=getnode_7.out(0),
    )
    setnode_9 = node(wf, 'SetNode', '233',
        widget_0='width_downsized',
        INT=get_image_size_163.out(0),
    )
    setnode_10 = node(wf, 'SetNode', '234',
        widget_0='height_downsized',
        INT=get_image_size_163.out(1),
    )
    setnode_11 = node(wf, 'SetNode', '238',
        widget_0='latent',
        LATENT=av_latent_109.out('LATENT'),
    )
    setnode_19 = node(wf, 'SetNode', '303',
        widget_0='model_with_lora',
        MODEL=power_lora_loader__rgthree_.out(0),
    )
    switch_audio = node(wf, 'ComfySwitchNode', '382',
        widget_0=False,
        on_false=trim_audio_duration_373.out(0),
        on_true=mel_band_ro_former_sampler_371.out(0),
    )
    av_latent_2 = node(wf, 'LTXVConcatAVLatent', '117',
        audio_latent=av_latent_separated_116.out('AUDIO_LATENT'),
        video_latent=ltxvimg_to_video_inplace_2.out(0),
    )
    setnode_7 = node(wf, 'SetNode', '226',
        widget_0='positive',
        CONDITIONING=conditioning.out('POSITIVE'),
    )
    setnode_8 = node(wf, 'SetNode', '227',
        widget_0='negative',
        CONDITIONING=conditioning.out('NEGATIVE'),
    )
    ltxvaudio_vaeencode = node(wf, 'LTXVAudioVAEEncode', '364',
        audio=switch_audio.out('OUTPUT'),
        audio_vae=getnode_34.out(0),
    )
    sampled_latent_2 = node(wf, 'SamplerCustomAdvanced', '119',
        guider=cfg_guider_103.out('GUIDER'),
        latent_image=av_latent_2.out('LATENT'),
        noise=noise_114.out('NOISE'),
        sampler=sampler_kind_2.out('SAMPLER'),
        sigmas=sigmas_2.out('SIGMAS'),
    )
    set_latent_noise_mask_363 = node(wf, 'SetLatentNoiseMask', '363',
        mask=solid_mask_362.out(0),
        samples=ltxvaudio_vaeencode.out(0),
    )
    av_latent_separated_2 = node(wf, 'LTXVSeparateAVLatent', '125',
        av_latent=sampled_latent_2.out('OUTPUT'),
    )
    setnode_23 = node(wf, 'SetNode', '366',
        widget_0='latent_custom_audio',
        LATENT=set_latent_noise_mask_363.out(0),
    )
    # ════ DECODE ════
    decoded_video = node(wf, 'VAEDecodeTiled', '127',
        tile_size=512,
        overlap=64,
        temporal_size=4096,
        temporal_overlap=8,
        samples=av_latent_separated_2.out('VIDEO_LATENT'),
        vae=getnode_8.out(0),
    )
    decoded_audio = node(wf, 'LTXVAudioVAEDecode', '201',
        audio_vae=getnode_9.out(0),
        samples=av_latent_separated_2.out('AUDIO_LATENT'),
    )
    # ════ OUTPUT ════
    video_output = node(wf, 'VHS_VideoCombine', '140',
        audio=getnode_39.out(0),
        frame_rate=getnode_22.out(0),
        images=decoded_video.out('IMAGE'),
    )

    return finalize(
        wf,
        PUBLIC_INPUTS,
        READY_METADATA,
        output_node='',
        source_path=__file__,
    )

