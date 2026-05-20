# vibecomfy: manual
# Edits will be overwritten on regeneration. Add a `# vibecomfy: manual`
# marker on the first line if hand-editing is required.
"""First Middle Last Frame Video with LTX 2.3 Text Projection.

Public inputs:
    use_lora: Lightning LoRA branch toggle

Output: unknown.

Source:  workflow_corpus/custom_nodes/ltxvideo/runexx/LTX-2.3_FML2V_First_Middle_Last_Frame_guider.json

Packs:   ComfyUI-GGUF, ComfyUI-KJNodes, ComfyUI-LTXVideo, ComfyUI-VideoHelperSuite, rgthree-comfy
"""
from __future__ import annotations

from vibecomfy.workflow import VibeWorkflow
from vibecomfy.templates import InputSpec, ModelAsset, ReadyMetadata, finalize, new_workflow, node

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
def _get_node_vae_audio(wf, _id, **overrides):
    kwargs = dict(widget_0='vae_audio')
    kwargs.update(overrides)
    return node(wf, 'GetNode', _id, **kwargs)
def _get_node_vae(wf, _id, **overrides):
    kwargs = dict(widget_0='vae')
    kwargs.update(overrides)
    return node(wf, 'GetNode', _id, **kwargs)
def _get_node_clip(wf, _id, **overrides):
    kwargs = dict(widget_0='clip')
    kwargs.update(overrides)
    return node(wf, 'GetNode', _id, **kwargs)
def _get_node_frames(wf, _id, **overrides):
    kwargs = dict(widget_0='frames')
    kwargs.update(overrides)
    return node(wf, 'GetNode', _id, **kwargs)
def _get_node_model_nag(wf, _id, **overrides):
    kwargs = dict(widget_0='model_nag')
    kwargs.update(overrides)
    return node(wf, 'GetNode', _id, **kwargs)
def _get_node_lastframe(wf, _id, **overrides):
    kwargs = dict(widget_0='lastframe')
    kwargs.update(overrides)
    return node(wf, 'GetNode', _id, **kwargs)
def _get_node_firstframe(wf, _id, **overrides):
    kwargs = dict(widget_0='firstframe')
    kwargs.update(overrides)
    return node(wf, 'GetNode', _id, **kwargs)
def _get_node_negative_guider(wf, _id, **overrides):
    kwargs = dict(widget_0='negative_guider')
    kwargs.update(overrides)
    return node(wf, 'GetNode', _id, **kwargs)
def _get_node_positive_guider(wf, _id, **overrides):
    kwargs = dict(widget_0='positive_guider')
    kwargs.update(overrides)
    return node(wf, 'GetNode', _id, **kwargs)
def _get_node_firstframe_strength(wf, _id, **overrides):
    kwargs = dict(widget_0='firstframe_strength')
    kwargs.update(overrides)
    return node(wf, 'GetNode', _id, **kwargs)
def _get_node_lastframe_strength(wf, _id, **overrides):
    kwargs = dict(widget_0='lastframe_strength')
    kwargs.update(overrides)
    return node(wf, 'GetNode', _id, **kwargs)
def _get_node_middleframe_strength(wf, _id, **overrides):
    kwargs = dict(widget_0='middleframe_strength')
    kwargs.update(overrides)
    return node(wf, 'GetNode', _id, **kwargs)
def _primitive_float(wf, _id, **overrides):
    kwargs = dict(value=8)
    kwargs.update(overrides)
    return node(wf, 'PrimitiveFloat', _id, **kwargs)
def _image_resize(wf, _id, height, image, width, **overrides):
    kwargs = dict(upscale_method='lanczos',
                  keep_proportion='crop',
                  pad_color='0, 0, 0',
                  crop_position='center',
                  divisible_by=32,
                  device='cpu',
                  height=height,
                  image=image,
                  width=width)
    kwargs.update(overrides)
    return node(wf, 'ImageResizeKJv2', _id, **kwargs)
def _l_t_x_v_preprocess(wf, _id, image, **overrides):
    kwargs = dict(img_compression=18,
                  image=image)
    kwargs.update(overrides)
    return node(wf, 'LTXVPreprocess', _id, **kwargs)
def _resize_images_by_longer_edge(wf, _id, images, **overrides):
    kwargs = dict(longer_edge=1536,
                  images=images)
    kwargs.update(overrides)
    return node(wf, 'ResizeImagesByLongerEdge', _id, **kwargs)
MODELS = {
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
    'gemma_clip': ModelAsset(
        filename='gemma-3-12b-it-Q2_K.gguf',
        url='',
        subdir='text_encoders',
    ),
    'gemma_clip_2': ModelAsset(
        filename='gemma_3_12B_it_fp4_mixed.safetensors',
        url='',
        subdir='text_encoders',
    ),
}

PUBLIC_INPUTS = {
    'use_lora': InputSpec(node='2082', field='value', default=True, type='BOOLEAN', description='Lightning LoRA branch toggle.'),
}

READY_METADATA = ReadyMetadata.build(
    template_id='ltx2_3_runexx_first_middle_last_frame',
    capability='first_middle_last_frame_video',
    inputs=PUBLIC_INPUTS,
    models=MODELS,
    output_prefix='',
    requirements={'custom_nodes': ['ComfyUI-GGUF', 'ComfyUI-KJNodes', 'ComfyUI-LTXVideo', 'ComfyUI-VideoHelperSuite', 'rgthree-comfy']},
    provenance={'smoke_resolution': '256x256x5_frames', 'approach': 'multi-anchor image-guided video', 'source_workflow': 'workflow_corpus/custom_nodes/ltxvideo/runexx/LTX-2.3_FML2V_First_Middle_Last_Frame_guider.json', 'source_role': 'materialized_ready_python_template'},
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
        noise_seed=43,
        control_after_generate='fixed',
    )
    noise_2 = node(wf, 'RandomNoise', '15',
        noise_seed=42,
        control_after_generate='fixed',
    )
    input_image_45 = node(wf, 'LoadImage', '45',
        image='sodacan_01.png',
)
    input_image_2 = node(wf, 'LoadImage', '47',
        image='image (11).png',
)
    get_node_70 = _get_node_width(wf, '70', )
    getnode_2 = _get_node_height(wf, '71', )
    getnode_3 = _get_node_fps(wf, '91', )
    getnode_4 = _get_node_fps(wf, '93', )
    getnode_5 = _get_node_vae_audio(wf, '117', )
    getnode_6 = _get_node_vae(wf, '120', )
    getnode_7 = node(wf, 'GetNode', '122',
        widget_0='model',
    )
    getnode_8 = _get_node_clip(wf, '124', )
    getnode_9 = _get_node_frames(wf, '127', )
    getnode_10 = _get_node_width(wf, '128', )
    getnode_11 = _get_node_height(wf, '129', )
    getnode_12 = node(wf, 'GetNode', '133',
        widget_0='upscale_model',
    )
    getnode_13 = _get_node_fps(wf, '137', )
    getnode_14 = _get_node_vae(wf, '147', )
    getnode_15 = _get_node_vae_audio(wf, '148', )
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
        model_name='ltx-2.3-spatial-upscaler-x2-1.1.safetensors',
    )
    base_diffusion_model = node(wf, 'UNETLoader', '187',
        unet_name=MODELS['ltx_2_3_22b_distilled_1_1_transformer_only'].filename,
        weight_dtype='default',
    )
    dual_cliploader_gguf = node(wf, 'DualCLIPLoaderGGUF', '189',
        clip_name1=MODELS['gemma_clip'].filename,
        clip_name2=MODELS['ltx_2_3_text_projection_bf16'].filename,
        type='ltxv',
    )
    text_encoder = node(wf, 'DualCLIPLoader', '190',
        clip_name1=MODELS['gemma_clip_2'].filename,
        clip_name2=MODELS['ltx_2_3_text_projection_bf16'].filename,
        type='ltxv',
        device='default',
    )
    unet_loader_gguf = node(wf, 'UnetLoaderGGUF', '191',
        unet_name='LTXvideo\\LTX-2\\quantstack\\LTX-2.3-distilled-Q4_K_S.gguf',
    )
    getnode_16 = node(wf, 'GetNode', '193',
        widget_0='vae_tiny',
    )
    getnode_17 = node(wf, 'GetNode', '196',
        widget_0='negative',
    )
    getnode_18 = _get_node_model_nag(wf, '200', )
    getnode_19 = _get_node_model_nag(wf, '201', )
    getnode_20 = node(wf, 'GetNode', '203',
        widget_0='final_video',
    )
    getnode_21 = node(wf, 'GetNode', '204',
        widget_0='final_audio',
    )
    sigmas_2 = node(wf, 'ManualSigmas', '215',
        sigmas='1.0, 0.99375, 0.9875, 0.98125, 0.975, 0.909375, 0.725, 0.421875, 0.0',
    )
    sigmas_3 = node(wf, 'ManualSigmas', '216',
        sigmas='0.85, 0.7250, 0.4219, 0.0',
    )
    getnode_22 = _get_node_height(wf, '219', )
    getnode_23 = _get_node_width(wf, '220', )
    getnode_24 = _get_node_lastframe(wf, '224', )
    getnode_25 = _get_node_firstframe(wf, '225', )
    getnode_26 = _get_node_clip(wf, '2067', )
    getnode_27 = node(wf, 'GetNode', '2068',
        widget_0='enhance_prompt',
    )
    param_float_2076 = _primitive_float(wf, '2076', )
    param_int_2078 = node(wf, 'INTConstant', '2078',
        value=15,
    )
    param_INT = node(wf, 'INTConstant', '2079',
        value=720,
    )
    param_INT_2 = node(wf, 'INTConstant', '2080',
        value=1280,
    )
    # ════ INPUTS ════
    use_lora = node(wf, 'PrimitiveBoolean', '2082', value=PUBLIC_INPUTS['use_lora'].default)
    n_19e3f7e8_881c_4a61_a360_1c463734043a = node(wf, '19e3f7e8-881c-4a61-a360-1c463734043a', '2102')
    primitive_string_multiline_2103 = node(wf, 'PrimitiveStringMultiline', '2103',
        value='Make this come alive with cinematic motion, smooth animation. \n\nThe scene starts with a close up of an LTX soda can with ic cubes around it. \n\nAll of a suddent an arm comes into frame and grabs the soda can, and lifts the soda can up. \n\nCamera pans up smoothly to show a woman holding the soda can. She talks with a soft British voice, and she says :" An LTX a day, keeps the doctor away". Then she laghts, and finally she drinks from the soda can. ',
    )
    getnode_28 = _get_node_lastframe(wf, '2106', )
    primitivefloat_2 = _primitive_float(wf, '2108', )
    primitivefloat_3 = _primitive_float(wf, '2110', )
    getnode_29 = _get_node_negative_guider(wf, '2154', )
    getnode_30 = _get_node_vae(wf, '2155', )
    getnode_31 = _get_node_positive_guider(wf, '2163', )
    getnode_32 = node(wf, 'GetNode', '2166',
        widget_0='negative_guider2',
    )
    getnode_33 = node(wf, 'GetNode', '2167',
        widget_0='positive_guider2',
    )
    input_image_3 = node(wf, 'LoadImage', '2172',
        image='image (12).png',
)
    getnode_34 = node(wf, 'GetNode', '2173',
        widget_0='middleframe',
    )
    getnode_35 = _get_node_frames(wf, '2175', )
    getnode_36 = _get_node_firstframe_strength(wf, '2187', )
    getnode_37 = _get_node_lastframe_strength(wf, '2188', )
    getnode_38 = _get_node_middleframe_strength(wf, '2189', )
    getnode_39 = node(wf, 'GetNode', '2214',
        widget_0='latent_audio',
    )
    getnode_40 = _get_node_firstframe(wf, '2220', )
    getnode_41 = _get_node_lastframe_strength(wf, '2226', )
    getnode_42 = _get_node_vae(wf, '2255', )
    getnode_43 = _get_node_negative_guider(wf, '2259', )
    getnode_44 = _get_node_positive_guider(wf, '2260', )
    getnode_45 = _get_node_firstframe_strength(wf, '2276', )
    primitivefloat_4 = _primitive_float(wf, '2278', )
    getnode_46 = _get_node_firstframe_strength(wf, '2279', )
    getnode_47 = _get_node_lastframe_strength(wf, '2280', )
    getnode_48 = _get_node_middleframe_strength(wf, '2281', )
    # ════ TEXT CONDITIONING ════
    negative_prompt = node(wf, 'CLIPTextEncode', '11',
        text='blurry, oversaturated, pixelated, low resolution, grainy, distorted, noise, compression artifacts, jpeg artifacts, glitches, watermark, text, logo, signature, copyright, subtitles, distorted sound, saturated sound, loud',
        clip=getnode_8.out(0),
    )
    # ════ OUTPUT ════
    video_output = node(wf, 'VHS_VideoCombine', '43',
        filename_prefix='reigh_vibecomfy_ltx_first_middle_last',
        format='video/h264-mp4',
        frame_rate=getnode_13.out(0),
        images=getnode_20.out(0),
        loop_count=0,
        pingpong=False,
        save_output=True,
    )
    resized_image_44 = _image_resize(wf, '44', getnode_2.out(0), input_image_45.out('IMAGE'), get_node_70.out(0))
    preprocessed_image_50 = _l_t_x_v_preprocess(wf, '50', getnode_24.out(0))
    simple_calculator_k_j_92 = node(wf, 'SimpleCalculatorKJ', '92',
        expression='a',
        a=getnode_3.out(0),
    )
    setnode_5 = node(wf, 'SetNode', '171',
        widget_0='upscale_model',
        LATENT_UPSCALE_MODEL=latent_upscale_model_loader_182.out(0),
    )
    setnode_6 = node(wf, 'SetNode', '172',
        widget_0='vae_audio',
        VAE=vaeloaderkj.out('AUDIO_VAE'),
    )
    setnode_7 = node(wf, 'SetNode', '173',
        widget_0='vae',
        VAE=vae_2.out('VAE'),
    )
    setnode_8 = node(wf, 'SetNode', '177',
        widget_0='vae_tiny',
        VAE=vae_180.out('VAE'),
    )
    # ════ MODEL PATCH STACK ════
    lora = node(wf, 'LoraLoaderModelOnly', '186',
        lora_name=MODELS['ltx_2_3_22b_distilled_1_1_lora_dynamic_fro'].filename,
        strength_model=0.6,
        model=base_diffusion_model.out('MODEL'),
    )
    setnode_9 = node(wf, 'SetNode', '188',
        widget_0='clip',
        CLIP=text_encoder.out('CLIP'),
    )
    n_8fa4f93a_67ee_463f_ba43_249580c0bfb1 = node(wf, '8fa4f93a-67ee-463f-ba43-249580c0bfb1', '2070',
        _1=primitive_string_multiline_2103.out(0),
        clip=getnode_26.out(0),
        image=n_19e3f7e8_881c_4a61_a360_1c463734043a.out(0),
    )
    setnode_13 = node(wf, 'SetNode', '2072',
        widget_0='height',
        INT=param_INT.out('VALUE'),
    )
    setnode_14 = node(wf, 'SetNode', '2073',
        widget_0='width',
        INT=param_INT_2.out('VALUE'),
    )
    setnode_15 = node(wf, 'SetNode', '2074',
        widget_0='fps',
        FLOAT=param_float_2076.out('FLOAT'),
    )
    simple_calculator_k_j_2 = node(wf, 'SimpleCalculatorKJ', '2077',
        expression='((round((a * b -1) / 8)) * 8) + 1 ',
        a=param_int_2078.out('VALUE'),
        b=param_float_2076.out('FLOAT'),
    )
    setnode_17 = node(wf, 'SetNode', '2081',
        widget_0='enhance_prompt',
        BOOLEAN=use_lora.out('BOOLEAN'),
    )
    ltxvpreprocess_2 = _l_t_x_v_preprocess(wf, '2084', getnode_25.out(0))
    setnode_18 = node(wf, 'SetNode', '2112',
        widget_0='firstframe_strength',
        FLOAT=primitivefloat_3.out('FLOAT'),
    )
    setnode_19 = node(wf, 'SetNode', '2113',
        widget_0='lastframe_strength',
        FLOAT=primitivefloat_2.out('FLOAT'),
    )
    ltxvpreprocess_3 = _l_t_x_v_preprocess(wf, '2174', getnode_34.out(0))
    comfy_math_expression_2191 = node(wf, 'ComfyMathExpression', '2191',
        widget_0='a/2',
        _extras={'values.a': getnode_23.out(0)},
    )
    comfy_math_expression_2 = node(wf, 'ComfyMathExpression', '2192',
        widget_0='a/2',
        _extras={'values.a': getnode_22.out(0)},
    )
    simple_calculator_k_j_3 = node(wf, 'SimpleCalculatorKJ', '2216',
        expression='a/2',
        _extras={'variables.a': getnode_35.out(0)},
    )
    setnode_31 = node(wf, 'SetNode', '2277',
        widget_0='middleframe_strength',
        FLOAT=primitivefloat_4.out('FLOAT'),
    )
    empty_audio_latent = node(wf, 'LTXVEmptyLatentAudio', '9',
        
        batch_size=1,
        audio_vae=getnode_5.out(0),
        frame_rate=simple_calculator_k_j_92.out(1),
        frames_number=getnode_9.out(0),
    )
    positive_prompt = node(wf, 'CLIPTextEncode', '16',
        text=n_8fa4f93a_67ee_463f_ba43_249580c0bfb1.out(0),
        clip=getnode_8.out(0),
    )
    wf.replace_edge('16.text', primitive_string_multiline_2103.out(0))
    wf.remove_node('2070')
    wf.remove_node('2102')
    empty_video_latent = node(wf, 'EmptyLTXVLatentVideo', '32',
        batch_size=1,
        
        
        width=comfy_math_expression_2191.out(1),
        height=comfy_math_expression_2.out(1),
        length=getnode_9.out(0),
    )
    imageresizekjv2_2 = _image_resize(wf, '48', resized_image_44.out(2), input_image_2.out('IMAGE'), resized_image_44.out(1))
    model_with_nag = node(wf, 'LTX2_NAG', '197',
        nag_scale=11,
        nag_alpha=0.25,
        nag_tau=2.5,
        inplace=True,
        model=getnode_7.out(0),
        nag_cond_audio=getnode_17.out(0),
        nag_cond_video=getnode_17.out(0),
    )
    # Upstream class is misspelled; do not rename.
    model_with_sage_attn = node(wf, 'PathchSageAttentionKJ', '226',
        sage_attention='disabled',
        allow_compile=False,
        model=lora.out('MODEL'),
    )
    setnode_16 = node(wf, 'SetNode', '2075',
        widget_0='frames',
        INT=simple_calculator_k_j_2.out(1),
    )
    resizeimagesbylongeredge_2 = _resize_images_by_longer_edge(wf, '2083', resized_image_44.out('IMAGE'))
    setnode_23 = node(wf, 'SetNode', '2185',
        widget_0='middleframe_count',
        INT=simple_calculator_k_j_3.out(1),
    )
    setnode_25 = node(wf, 'SetNode', '2217',
        widget_0='firstframe_resized',
        IMAGE=resized_image_44.out('IMAGE'),
    )
    setnode_30 = node(wf, 'SetNode', '2233',
        widget_0='negative',
        CONDITIONING=negative_prompt.out('CONDITIONING'),
    )
    conditioning = node(wf, 'LTXVConditioning', '10',
        frame_rate=getnode_4.out(0),
        negative=negative_prompt.out('CONDITIONING'),
        positive=positive_prompt.out('CONDITIONING'),
    )
    resize_images_by_longer_edge_49 = _resize_images_by_longer_edge(wf, '49', imageresizekjv2_2.out('IMAGE'))
    set_node_75 = node(wf, 'SetNode', '75',
        widget_0='firstframe',
        IMAGE=resizeimagesbylongeredge_2.out(0),
    )
    setnode_11 = node(wf, 'SetNode', '199',
        widget_0='model_nag',
        MODEL=model_with_nag.out('MODEL'),
    )
    imageresizekjv2_3 = _image_resize(wf, '2171', imageresizekjv2_2.out(2), input_image_3.out('IMAGE'), imageresizekjv2_2.out(1))
    setnode_24 = node(wf, 'SetNode', '2215',
        widget_0='latent_audio',
        LATENT=empty_audio_latent.out('LATENT'),
    )
    setnode_26 = node(wf, 'SetNode', '2218',
        widget_0='middleframe_resized',
        IMAGE=imageresizekjv2_2.out('IMAGE'),
    )
    setnode_2 = node(wf, 'SetNode', '78',
        widget_0='middleframe',
        IMAGE=resize_images_by_longer_edge_49.out(0),
    )
    model_chunked_ffn = node(wf, 'LTXVChunkFeedForward', '228',
        chunks=2,
        dim_threshold=4096,
        model=model_with_sage_attn.out('MODEL'),
    )
    resizeimagesbylongeredge_3 = _resize_images_by_longer_edge(wf, '2168', imageresizekjv2_3.out('IMAGE'))
    setnode_27 = node(wf, 'SetNode', '2219',
        widget_0='lastframe_resized',
        IMAGE=imageresizekjv2_3.out('IMAGE'),
    )
    ltxvadd_guide_multi_1 = node(wf, 'LTXVAddGuideMulti', '2221',
        latent=empty_video_latent.out('LATENT'),
        negative=conditioning.out('NEGATIVE'),
        num_guides='3',
        positive=conditioning.out('POSITIVE'),
        vae=getnode_42.out(0),
        _extras={'num_guides.frame_idx_1': 0, 'num_guides.frame_idx_2': simple_calculator_k_j_3.out(1), 'num_guides.frame_idx_3': -1, 'num_guides.image_1': ltxvpreprocess_2.out('OUTPUT_IMAGE'), 'num_guides.image_2': ltxvpreprocess_3.out('OUTPUT_IMAGE'), 'num_guides.image_3': preprocessed_image_50.out('OUTPUT_IMAGE'), 'num_guides.strength_1': getnode_46.out(0), 'num_guides.strength_2': getnode_48.out(0), 'num_guides.strength_3': getnode_47.out(0)},
    )
    av_latent_24 = node(wf, 'LTXVConcatAVLatent', '24',
        audio_latent=getnode_39.out(0),
        video_latent=ltxvadd_guide_multi_1.out(2),
    )
    # Stage 1 (REFINE): NAG model (bypasses patch stack) + base conditioning
    # Stage 2 (FINISH): IC-LoRA model (full patch chain)   + guided conditioning
    cfg_guider_1 = node(wf, 'CFGGuider', '36',
        cfg=2.5,
        model=getnode_18.out(0),
        negative=ltxvadd_guide_multi_1.out(1),
        positive=ltxvadd_guide_multi_1.out(0),
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
    setnode_22 = node(wf, 'SetNode', '2169',
        widget_0='lastframe',
        IMAGE=resizeimagesbylongeredge_3.out(0),
    )
    setnode_28 = node(wf, 'SetNode', '2223',
        widget_0='positive_guider',
        CONDITIONING=ltxvadd_guide_multi_1.out(0),
    )
    setnode_29 = node(wf, 'SetNode', '2224',
        widget_0='negative_guider',
        CONDITIONING=ltxvadd_guide_multi_1.out(1),
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
        guider=cfg_guider_1.out('GUIDER'),
        latent_image=av_latent_24.out('LATENT'),
        noise=noise_2.out('NOISE'),
        sampler=sampler_kind_1.out('SAMPLER'),
        sigmas=sigmas_2.out('SIGMAS'),
    )
    power_lora_loader__rgthree_ = node(wf, 'Power Lora Loader (rgthree)', '2107',
model=model_attention_tuned.out('MODEL'),
    )
    av_latent_separated_18 = node(wf, 'LTXVSeparateAVLatent', '18',
        av_latent=sampled_latent_13.out('OUTPUT'),
    )
    setnode_10 = node(wf, 'SetNode', '192',
        widget_0='model',
        MODEL=power_lora_loader__rgthree_.out(0),
    )
    setnode_12 = node(wf, 'SetNode', '230',
        widget_0='model_with_lora',
        MODEL=power_lora_loader__rgthree_.out(0),
    )
    cropped_latent_1 = node(wf, 'LTXVCropGuides', '2222',
        latent=av_latent_separated_18.out('VIDEO_LATENT'),
        negative=getnode_43.out(0),
        positive=getnode_44.out(0),
    )
    ltxvadd_guide_multi_2 = node(wf, 'LTXVAddGuideMulti', '2182',
        latent=cropped_latent_1.out(2),
        negative=cropped_latent_1.out(1),
        num_guides='2',
        positive=cropped_latent_1.out('LATENT'),
        vae=getnode_30.out(0),
        _extras={'num_guides.frame_idx_1': 0, 'num_guides.frame_idx_2': -1, 'num_guides.image_1': getnode_40.out(0), 'num_guides.image_2': getnode_28.out(0), 'num_guides.strength_1': getnode_45.out(0), 'num_guides.strength_2': getnode_41.out(0)},
    )
    cfg_guider_8 = node(wf, 'CFGGuider', '8',
        cfg=2.5,
        model=getnode_19.out(0),
        negative=ltxvadd_guide_multi_2.out(1),
        positive=ltxvadd_guide_multi_2.out(0),
    )
    av_latent_2 = node(wf, 'LTXVConcatAVLatent', '34',
        audio_latent=av_latent_separated_18.out('AUDIO_LATENT'),
        video_latent=ltxvadd_guide_multi_2.out(2),
    )
    setnode_20 = node(wf, 'SetNode', '2164',
        widget_0='positive_guider2',
        CONDITIONING=ltxvadd_guide_multi_2.out(0),
    )
    setnode_21 = node(wf, 'SetNode', '2165',
        widget_0='negative_guider2',
        CONDITIONING=ltxvadd_guide_multi_2.out(1),
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
        audio_vae=getnode_15.out(0),
        samples=av_latent_separated_2.out('AUDIO_LATENT'),
    )
    cropped_latent_2156 = node(wf, 'LTXVCropGuides', '2156',
        latent=av_latent_separated_2.out('VIDEO_LATENT'),
        negative=getnode_32.out(0),
        positive=getnode_33.out(0),
    )
    decoded_video = node(wf, 'VAEDecodeTiled', '149',
        tile_size=512,
        overlap=64,
        temporal_size=4096,
        temporal_overlap=8,
        samples=cropped_latent_2156.out(2),
        vae=getnode_14.out(0),
    )
    setnode_4 = node(wf, 'SetNode', '154',
        widget_0='final_audio',
        AUDIO=decoded_audio.out(0),
    )
    setnode_3 = node(wf, 'SetNode', '153',
        widget_0='final_video',
        IMAGE=decoded_video.out('IMAGE'),
    )

    return finalize(
        wf,
        PUBLIC_INPUTS,
        READY_METADATA,
        output_node='',
        source_path=__file__,
    )

