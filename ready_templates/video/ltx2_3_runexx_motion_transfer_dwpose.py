# vibecomfy: generated — converted by tools/convert_ready_templates.py
# Edits will be overwritten on regeneration. Add a `# vibecomfy: manual`
# marker on the first line if hand-editing is required.
"""Dwpose Motion Transfer with LTX 23 Video VAE Bf 16 VAE.

Public inputs:
    use_lora: Lightning LoRA branch toggle

Output: unknown.

Source:  workflow_corpus/custom_nodes/ltxvideo/runexx/LTX-2.3_Motion_Transfer_DWPose.json

Packs:   ComfyUI-GGUF, ComfyUI-KJNodes, ComfyUI-LTXVideo, ComfyUI-VideoHelperSuite, comfyui_controlnet_aux, rgthree-comfy
"""
from __future__ import annotations

from vibecomfy.workflow import VibeWorkflow
from vibecomfy.templates import InputSpec, ModelAsset, ReadyMetadata, finalize, new_workflow, node

def _get_node_clip(wf, _id, **overrides):
    kwargs = dict(widget_0='clip')
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
def _get_node_model(wf, _id, **overrides):
    kwargs = dict(widget_0='model')
    kwargs.update(overrides)
    return node(wf, 'GetNode', _id, **kwargs)
def _get_node_ref_height(wf, _id, **overrides):
    kwargs = dict(widget_0='ref_height')
    kwargs.update(overrides)
    return node(wf, 'GetNode', _id, **kwargs)
def _get_node_ref_width(wf, _id, **overrides):
    kwargs = dict(widget_0='ref_width')
    kwargs.update(overrides)
    return node(wf, 'GetNode', _id, **kwargs)
def _get_node_ref_frames(wf, _id, **overrides):
    kwargs = dict(widget_0='ref_frames')
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
def _get_node_ref_image(wf, _id, **overrides):
    kwargs = dict(widget_0='ref_image')
    kwargs.update(overrides)
    return node(wf, 'GetNode', _id, **kwargs)
def _get_node_t2v_mode(wf, _id, **overrides):
    kwargs = dict(widget_0='t2v_mode')
    kwargs.update(overrides)
    return node(wf, 'GetNode', _id, **kwargs)
def _get_node_latent_down_factor(wf, _id, **overrides):
    kwargs = dict(widget_0='latent_down_factor')
    kwargs.update(overrides)
    return node(wf, 'GetNode', _id, **kwargs)
def _get_node_fps(wf, _id, **overrides):
    kwargs = dict(widget_0='fps')
    kwargs.update(overrides)
    return node(wf, 'GetNode', _id, **kwargs)
def _get_node_audio_selected(wf, _id, **overrides):
    kwargs = dict(widget_0='audio_selected')
    kwargs.update(overrides)
    return node(wf, 'GetNode', _id, **kwargs)
def _get_node_audio_custom_mode(wf, _id, **overrides):
    kwargs = dict(widget_0='audio_custom_mode')
    kwargs.update(overrides)
    return node(wf, 'GetNode', _id, **kwargs)
def _primitive_float(wf, _id, **overrides):
    kwargs = dict(value=8)
    kwargs.update(overrides)
    return node(wf, 'PrimitiveFloat', _id, **kwargs)
def _comfy_switchnode(wf, _id, on_false, on_true, switch, **overrides):
    kwargs = dict(widget_0=True,
                  on_false=on_false,
                  on_true=on_true,
                  switch=switch)
    kwargs.update(overrides)
    return node(wf, 'ComfySwitchNode', _id, **kwargs)
def _comfy_switch_node_variant(wf, _id, on_false, on_true, **overrides):
    kwargs = dict(widget_0=False,
                  on_false=on_false,
                  on_true=on_true)
    kwargs.update(overrides)
    return node(wf, 'ComfySwitchNode', _id, **kwargs)
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
    'use_lora': InputSpec(node='5198', field='value', default=False, type='BOOLEAN', description='Lightning LoRA branch toggle.'),
}

READY_METADATA = ReadyMetadata.build(
    template_id='ltx2_3_runexx_motion_transfer_dwpose',
    capability='dwpose_motion_transfer',
    inputs=PUBLIC_INPUTS,
    models=MODELS,
    output_prefix='',
    requirements={'custom_nodes': ['ComfyUI-GGUF', 'ComfyUI-KJNodes', 'ComfyUI-LTXVideo', 'ComfyUI-VideoHelperSuite', 'comfyui_controlnet_aux', 'rgthree-comfy'], 'custom_node_refs': [{'slug': 'ComfyUI-GGUF', 'source': 'git',
                       'commit': '6ea2651e7df66d7585f6ffee804b20e92fb38b8a', 'url': 'https://github.com/city96/ComfyUI-GGUF.git'}, {'slug': 'ComfyUI-KJNodes', 'source': 'git', 'commit': 'b7646ad70a7daa7aeb919ca542274758d26ba2df', 'url': 'https://github.com/kijai/ComfyUI-KJNodes.git'}, {'slug': 'ComfyUI-LTXVideo', 'source': 'git',
                       'commit': '229437c6b65796d6a7a63ae34be2bd5ba31fa543', 'url': 'https://github.com/Lightricks/ComfyUI-LTXVideo.git'}, {'slug': 'ComfyUI-VideoHelperSuite', 'source': 'git',
                       'commit': '4ee72c065db22c9d96c2427954dc69e7b908444b', 'url': 'https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite.git'}, {'slug': 'comfyui_controlnet_aux', 'source': 'git',
                       'commit': 'e8b689a513c3e6b63edc44066560ca5919c0576e', 'url': 'https://github.com/Fannovel16/comfyui_controlnet_aux.git'}, {'slug': 'rgthree-comfy', 'source': 'git',
                       'commit': '738105af5fb14e96fbecaf406dc356e284797e8c', 'url': 'https://github.com/rgthree/rgthree-comfy.git'}]},
    provenance={'source_role': 'materialized_ready_python_template', 'approach': 'DWPose body motion transfer', 'source_workflow': 'workflow_corpus/custom_nodes/ltxvideo/runexx/LTX-2.3_Motion_Transfer_DWPose.json', 'smoke_resolution': '256x256x5_frames'},
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
    input_image = node(wf, 'LoadImage', '2004',
        image='fjf1oxsjnnrgphxxrnzx6dh4k9-nano-banana-gemini-3-pro-image-ultra-realistic-black-and-white-cinematic-fullbody-portrait-of-muhammad-ali-standing-side-lighting-strong-contrast-intense-mysterious-expression-sharp.jpg',
)
    sampler_kind_4831 = node(wf, 'KSamplerSelect', '4831',
        sampler_name='euler_ancestral_cfg_pp',
    )
    noise_4832 = node(wf, 'RandomNoise', '4832',
        noise_seed=42,
        control_after_generate='fixed',
    )
    sigmas_5025 = node(wf, 'ManualSigmas', '5025',
        sigmas='1.0, 0.99375, 0.9875, 0.98125, 0.975, 0.909375, 0.725, 0.421875, 0.0',
    )
    noise_2 = node(wf, 'RandomNoise', '5068',
        noise_seed=43,
        control_after_generate='fixed',
    )
    sampler_kind_2 = node(wf, 'KSamplerSelect', '5070',
        sampler_name='euler_cfg_pp',
    )
    sigmas_2 = node(wf, 'ManualSigmas', '5071',
        sigmas='0.85, 0.7250, 0.4219, 0.0',
    )
    # ════ LOADERS ════
    vae_5125 = node(wf, 'VAELoader', '5125',
        vae_name=MODELS['ltx23_video_vae_bf16_vae'].filename,
    )
    text_encoder = node(wf, 'DualCLIPLoader', '5126',
        clip_name1=MODELS['gemma_clip'].filename,
        clip_name2=MODELS['ltx_2_3_text_projection_bf16_clip'].filename,
        type='ltxv',
        device='default',
    )
    vaeloaderkj = node(wf, 'LTXVAudioVAELoader', '5127',
        ckpt_name='LTX23_audio_vae_bf16.safetensors',
    )
    vae_2 = node(wf, 'VAELoader', '5129',
        vae_name=MODELS['taeltx2_3_vae'].filename,
    )
    base_diffusion_model = node(wf, 'UNETLoader', '5130',
        unet_name=MODELS['ltx_2_3_22b_distilled_1_1_transformer_only'].filename,
        weight_dtype='default',
    )
    # ════ LATENT ════
    latent_upscale_model_loader_5132 = node(wf, 'LatentUpscaleModelLoader', '5132',
        model_name='ltx-2.3-spatial-upscaler-x2-1.1.safetensors',
    )
    get_node_5137 = _get_node_clip(wf, '5137', )
    getnode_2 = _get_node_vae(wf, '5139', )
    getnode_3 = _get_node_vae(wf, '5140', )
    getnode_4 = _get_node_vae(wf, '5141', )
    getnode_5 = _get_node_vae(wf, '5143', )
    getnode_6 = _get_node_vae_audio(wf, '5145', )
    getnode_7 = _get_node_vae(wf, '5146', )
    getnode_8 = _get_node_vae_audio(wf, '5147', )
    getnode_9 = _get_node_model(wf, '5149', )
    getnode_10 = _get_node_model(wf, '5150', )
    getnode_11 = node(wf, 'GetNode', '5152',
        widget_0='ref_video',
    )
    getnode_12 = _get_node_ref_height(wf, '5156', )
    getnode_13 = _get_node_ref_width(wf, '5157', )
    getnode_14 = _get_node_ref_frames(wf, '5158', )
    getnode_15 = _get_node_ref_height(wf, '5159', )
    getnode_16 = _get_node_ref_width(wf, '5160', )
    getnode_17 = _get_node_positive(wf, '5163', )
    getnode_18 = _get_node_negative(wf, '5164', )
    getnode_19 = node(wf, 'GetNode', '5169',
        widget_0='positive_guider',
    )
    getnode_20 = node(wf, 'GetNode', '5170',
        widget_0='negative_guider',
    )
    getnode_21 = _get_node_positive(wf, '5171', )
    getnode_22 = _get_node_negative(wf, '5172', )
    getnode_23 = _get_node_negative(wf, '5173', )
    getnode_24 = _get_node_positive(wf, '5174', )
    getnode_25 = _get_node_ref_image(wf, '5176', )
    getnode_26 = _get_node_ref_image(wf, '5177', )
    getnode_27 = _get_node_t2v_mode(wf, '5180', )
    getnode_28 = _get_node_t2v_mode(wf, '5181', )
    getnode_29 = _get_node_latent_down_factor(wf, '5184', )
    getnode_30 = _get_node_latent_down_factor(wf, '5185', )
    getnode_31 = node(wf, 'GetNode', '5188',
        widget_0='model_with_lora',
    )
    getnode_32 = node(wf, 'GetNode', '5190',
        widget_0='vae_tiny',
    )
    getnode_33 = node(wf, 'GetNode', '5191',
        widget_0='upscale_model',
    )
    # ════ INPUTS ════
    use_lora = node(wf, 'PrimitiveBoolean', '5198', value=PUBLIC_INPUTS['use_lora'].default)
    param_float_5199 = _primitive_float(wf, '5199', )
    use_BOOLEAN = node(wf, 'PrimitiveBoolean', '5201', value=False)
    getnode_34 = _get_node_fps(wf, '5203', )
    param_int_5205 = node(wf, 'INTConstant', '5205',
        value=10,
    )
    param_INT = node(wf, 'INTConstant', '5206',
        value=736,
    )
    param_INT_2 = node(wf, 'INTConstant', '5207',
        value=1280,
    )
    getnode_35 = _get_node_fps(wf, '5209', )
    getnode_36 = _get_node_audio_selected(wf, '5210', )
    getnode_37 = node(wf, 'GetNode', '5212',
        widget_0='width',
    )
    getnode_38 = node(wf, 'GetNode', '5213',
        widget_0='height',
    )
    getnode_39 = _get_node_fps(wf, '5216', )
    getnode_40 = node(wf, 'GetNode', '5217',
        widget_0='frames',
    )
    getnode_41 = _get_node_fps(wf, '5218', )
    dual_cliploader_gguf = node(wf, 'DualCLIPLoaderGGUF', '5228',
        clip_name1=MODELS['gemma_clip_2'].filename,
        clip_name2=MODELS['ltx_2_3_text_projection_bf16_clip'].filename,
        type='sdxl',
    )
    unet_loader_gguf = node(wf, 'UnetLoaderGGUF', '5229',
        unet_name='LTXvideo\\LTX-2\\quantstack\\LTX-2.3-distilled-Q4_K_S.gguf',
    )
    getnode_42 = _get_node_clip(wf, '5235', )
    getnode_43 = node(wf, 'GetNode', '5236',
        widget_0='enhance_prompt',
    )
    primitive_string_multiline_5242 = node(wf, 'PrimitiveStringMultiline', '5242',
        value='highly detailed, monochrime colors. Make this image come alive with fluid motion. \n\nA make boxer. \n\nHe is dancing in sync to the music ',
    )
    getnode_44 = _get_node_fps(wf, '5245', )
    getnode_45 = _get_node_ref_frames(wf, '5248', )
    getnode_46 = _get_node_negative(wf, '5250', )
    getnode_47 = _get_node_negative(wf, '5253', )
    getnode_48 = _get_node_vae_audio(wf, '5255', )
    getnode_49 = node(wf, 'GetNode', '5257',
        widget_0='latent_audio_selected',
    )
    getnode_50 = node(wf, 'GetNode', '5261',
        widget_0='latent_audio_custom',
    )
    load_audio_5263 = node(wf, 'LoadAudio', '5263',
        audio='(Verse).mp3',
    )
    getnode_51 = node(wf, 'GetNode', '5267',
        widget_0='audio_output',
    )
    # ════ DECODE ════
    decoded_video_1 = node(wf, 'VAEDecodeTiled', '5268',
        tile_size=544,
        overlap=64,
        temporal_size=4096,
        temporal_overlap=4,
    )
    getnode_52 = node(wf, 'GetNode', '5269',
        widget_0='video_output',
    )
    getnode_53 = node(wf, 'GetNode', '5278',
        widget_0='ref_blended',
    )
    getnode_54 = node(wf, 'GetNode', '5279',
        widget_0='ref_pose',
    )
    getnode_55 = node(wf, 'GetNode', '5281',
        widget_0='ref_selected',
    )
    getnode_56 = _get_node_ref_frames(wf, '5285', )
    getnode_57 = _get_node_fps(wf, '5286', )
    getnode_58 = node(wf, 'GetNode', '5287',
        widget_0='audio_custom',
    )
    getnode_59 = node(wf, 'GetNode', '5288',
        widget_0='audio_original',
    )
    getnode_60 = _get_node_ref_frames(wf, '5291', )
    getnode_61 = _get_node_fps(wf, '5292', )
    getnode_62 = node(wf, 'GetNode', '5295',
        widget_0='latent_audio',
    )
    getnode_63 = _get_node_audio_selected(wf, '5296', )
    primitivefloat_2 = _primitive_float(wf, '5298', )
    primitivefloat_3 = _primitive_float(wf, '5299', )
    getnode_64 = node(wf, 'GetNode', '5301',
        widget_0='ref_strength',
    )
    use_BOOLEAN_2 = node(wf, 'PrimitiveBoolean', '5303', value=True)
    getnode_65 = _get_node_audio_custom_mode(wf, '5305', )
    getnode_66 = _get_node_audio_custom_mode(wf, '5306', )
    # ════ TEXT CONDITIONING ════
    negative_prompt = node(wf, 'CLIPTextEncode', '2612',
        text='low contrast, washed out, text, subtitles, logo, still image, still video, blurry, low quality, distorted, bad anatomy, oversaturated, pixelated, low resolution, grainy, compression artifacts, jpeg artifacts, glitches, watermark, signature, copyright,  distortedsound, saturated sound, loud sound , deformed facial features, asymmetrical face, missing facial features, extra limbs, disfigured hands, blurry teeth, disfigured teeth',
        clip=get_node_5137.out(0),
    )
    empty_video_latent = node(wf, 'EmptyLTXVLatentVideo', '3059',
        batch_size=1,
        
        
        width=getnode_13.out(0),
        height=getnode_12.out(0),
        length=getnode_14.out(0),
    )
    # ════ IMAGE PREP ════
    preprocessed_image = node(wf, 'LTXVPreprocess', '3336',
        img_compression=18,
        image=getnode_26.out(0),
    )
    simplemath_ = node(wf, 'SimpleMath+', '5034',
        widget_0='a*32',
        a=getnode_30.out(0),
    )
    resize_image_mask_node_1 = node(wf, 'ResizeImageMaskNode', '5035',
        resize_type='scale longer dimension',
scale_method='lanczos',
        input=input_image.out('IMAGE'),
    )
    # Stage 1 (REFINE): NAG model (bypasses patch stack) + base conditioning
    # Stage 2 (FINISH): IC-LoRA model (full patch chain)   + guided conditioning
    cfg_guider_1 = node(wf, 'CFGGuider', '5069',
        cfg=2.5,
        model=getnode_10.out(0),
        negative=getnode_22.out(0),
        positive=getnode_21.out(0),
    )
    ltxvaudio_vaeencode = node(wf, 'LTXVAudioVAEEncode', '5079',
        audio=getnode_63.out(0),
        audio_vae=getnode_8.out(0),
    )
    solid_mask_5080 = node(wf, 'SolidMask', '5080',
        widget_0=0,
        widget_1=512,
        widget_2=512,
        height=getnode_15.out(0),
        width=getnode_16.out(0),
    )
    set_node_5121 = node(wf, 'SetNode', '5121',
        widget_0='upscale_model',
        LATENT_UPSCALE_MODEL=latent_upscale_model_loader_5132.out(0),
    )
    setnode_2 = node(wf, 'SetNode', '5122',
        widget_0='vae_audio',
        VAE=vaeloaderkj.out('AUDIO_VAE'),
    )
    setnode_3 = node(wf, 'SetNode', '5123',
        widget_0='vae',
        VAE=vae_5125.out('VAE'),
    )
    setnode_4 = node(wf, 'SetNode', '5124',
        widget_0='clip',
        CLIP=text_encoder.out('CLIP'),
    )
    setnode_5 = node(wf, 'SetNode', '5128',
        widget_0='vae_tiny',
        VAE=vae_2.out('VAE'),
    )
    # ════ MODEL PATCH STACK ════
    lora = node(wf, 'LoraLoaderModelOnly', '5131',
        lora_name='LTX\\LTX-2\\ltx-2.3-22b-distilled-lora-384.safetensors',
        strength_model=0.6,
        model=base_diffusion_model.out('MODEL'),
    )
    vhs__load_video_f_fmpeg = node(wf, 'VHS_LoadVideoFFmpeg', '5192',
        force_rate=getnode_41.out(0),
        frame_load_cap=getnode_40.out(0),
    )
    setnode_19 = node(wf, 'SetNode', '5194',
        widget_0='height',
        INT=param_INT_2.out('VALUE'),
    )
    setnode_20 = node(wf, 'SetNode', '5195',
        widget_0='width',
        INT=param_INT.out('VALUE'),
    )
    setnode_21 = node(wf, 'SetNode', '5196',
        widget_0='fps',
        FLOAT=param_float_5199.out('FLOAT'),
    )
    setnode_22 = node(wf, 'SetNode', '5197',
        widget_0='t2v_mode',
        BOOLEAN=use_lora.out('BOOLEAN'),
    )
    setnode_23 = node(wf, 'SetNode', '5200',
        widget_0='enhance_prompt',
        BOOLEAN=use_BOOLEAN.out('BOOLEAN'),
    )
    simple_calculator_k_j_5202 = node(wf, 'SimpleCalculatorKJ', '5202',
        expression='((round((a * b -1) / 8)) * 8) + 1 ',
        _extras={'variables.a': param_int_5205.out('VALUE'), 'variables.b': getnode_34.out(0)},
    )
    # ════ OUTPUT ════
    vhs_videocombine_2 = node(wf, 'VHS_VideoCombine', '5208',
        audio=getnode_51.out(0),
        frame_rate=getnode_35.out(0),
        images=getnode_52.out(0),
    )
    simple_calculator_k_j_2 = node(wf, 'SimpleCalculatorKJ', '5247',
        expression='a',
        _extras={'variables.a': getnode_44.out(0)},
    )
    switch_5256 = _comfy_switchnode(wf, '5256', getnode_62.out(0), getnode_50.out(0), getnode_66.out(0))
    comfyswitchnode_3 = _comfy_switch_node_variant(wf, '5272', getnode_54.out(0), getnode_53.out(0))
    simple_calculator_k_j_3 = node(wf, 'SimpleCalculatorKJ', '5284',
        expression='a / b ',
        _extras={'variables.a': getnode_56.out(0), 'variables.b': getnode_57.out(0)},
    )
    simple_calculator_k_j_4 = node(wf, 'SimpleCalculatorKJ', '5290',
        expression='a / b',
        _extras={'variables.a': getnode_60.out(0), 'variables.b': getnode_61.out(0)},
    )
    setnode_36 = node(wf, 'SetNode', '5300',
        widget_0='ref_strength',
        FLOAT=primitivefloat_3.out('FLOAT'),
    )
    setnode_37 = node(wf, 'SetNode', '5304',
        widget_0='audio_custom_mode',
        BOOLEAN=use_BOOLEAN_2.out('BOOLEAN'),
    )
    ltxvimg_to_video_condition_only = node(wf, 'LTXVImgToVideoConditionOnly', '3159',
        strength=1,
        bypass=getnode_28.out(0),
        image=preprocessed_image.out('OUTPUT_IMAGE'),
        latent=empty_video_latent.out('LATENT'),
        vae=getnode_2.out(0),
    )
    final_model_with_ic_lora = node(wf, 'LTXICLoRALoaderModelOnly', '5011',
        lora_name='LTX\\LTX-2\\IC-Lora\\ltx-2.3-22b-v1.1-ic-lora-union-control-ref0.5.safetensors',
        strength_model=0.71,
        model=lora.out('MODEL'),
    )
    set_latent_noise_mask_5081 = node(wf, 'SetLatentNoiseMask', '5081',
        mask=solid_mask_5080.out(0),
        samples=ltxvaudio_vaeencode.out(0),
    )
    setnode_15 = node(wf, 'SetNode', '5175',
        widget_0='ref_image',
        IMAGE=resize_image_mask_node_1.out(0),
    )
    setnode_18 = node(wf, 'SetNode', '5193',
        widget_0='audio_original',
        AUDIO=vhs__load_video_f_fmpeg.out(2),
    )
    setnode_24 = node(wf, 'SetNode', '5204',
        widget_0='frames',
        INT=simple_calculator_k_j_5202.out(1),
    )
    resized_image_5211 = node(wf, 'ImageResizeKJv2', '5211',
        
        upscale_method='nearest-exact',
        keep_proportion='crop',
        pad_color='0, 0, 0',
        crop_position='center',
        divisible_by=2,
        device='cpu',
        height=getnode_38.out(0),
        image=vhs__load_video_f_fmpeg.out(0),
        width=getnode_37.out(0),
    )
    resize_image_mask_node_2 = node(wf, 'ResizeImageMaskNode', '5241',
        resize_type='scale by multiplier',
scale_method='area',
        input=resize_image_mask_node_1.out(0),
    )
    empty_audio_latent = node(wf, 'LTXVEmptyLatentAudio', '5243',
        
        batch_size=1,
        audio_vae=getnode_48.out(0),
        frame_rate=simple_calculator_k_j_2.out(1),
        frames_number=getnode_45.out(0),
    )
    model_with_nag = node(wf, 'LTX2_NAG', '5251',
        nag_scale=11,
        nag_alpha=0.25,
        nag_tau=2.5,
        inplace=True,
        model=getnode_31.out(0),
        nag_cond_audio=getnode_47.out(0),
        nag_cond_video=getnode_47.out(0),
    )
    setnode_26 = node(wf, 'SetNode', '5258',
        widget_0='latent_audio_selected',
        LATENT=switch_5256.out('OUTPUT'),
    )
    setnode_32 = node(wf, 'SetNode', '5280',
        widget_0='ref_selected',
        IMAGE=comfyswitchnode_3.out('OUTPUT'),
    )
    trim_audio_duration_5283 = node(wf, 'TrimAudioDuration', '5283',
        widget_0=0,
        widget_1=60,
        audio=load_audio_5263.out(0),
        duration=simple_calculator_k_j_3.out(0),
    )
    empty_audio_5289 = node(wf, 'EmptyAudio', '5289',
        widget_0=60,
        widget_1=44100,
        widget_2=2,
        duration=simple_calculator_k_j_4.out(0),
    )
    guided_latent = node(wf, 'LTXAddVideoICLoRAGuide', '5012',
        frame_idx=0,
        crop=1,
        use_tiled_encode='disabled',
tile_size=128,
        tile_overlap=32,
        image=getnode_11.out(0),
        latent=ltxvimg_to_video_condition_only.out(0),
        latent_downscale_factor=getnode_29.out(0),
        negative=getnode_18.out(0),
        positive=getnode_17.out(0),
        strength=getnode_64.out(0),
        vae=getnode_7.out(0),
    )
    setnode_6 = node(wf, 'SetNode', '5148',
    # POSSIBLE CHAIN BYPASS: takes LTXICLoRALoaderModelOnly directly; does NOT inherit the PathchSageAttentionKJ/LTXVChunkFeedForward/LTX2AttentionTunerPatch patches.
        widget_0='model_iclora',
        MODEL=final_model_with_ic_lora.out('MODEL'),
    )
    setnode_16 = node(wf, 'SetNode', '5183',
        widget_0='latent_down_factor',
        FLOAT=final_model_with_ic_lora.out('LATENT_DOWNSCALE_FACTOR'),
    )
    setnode_17 = node(wf, 'SetNode', '5189',
        widget_0='model',
        MODEL=model_with_nag.out('MODEL'),
    )
    resize_image_mask_node_3 = node(wf, 'ResizeImageMaskNode', '5214',
        resize_type='scale by multiplier',
scale_method='area',
        input=resized_image_5211.out('IMAGE'),
    )
    # Upstream class is misspelled; do not rename.
    model_with_sage_attn = node(wf, 'PathchSageAttentionKJ', '5231',
        sage_attention='disabled',
        allow_compile=False,
        model=final_model_with_ic_lora.out('MODEL'),
    )
    n_94e8f3a0_557f_4580_93a0_f762c7b0d076 = node(wf, '94e8f3a0-557f-4580-93a0-f762c7b0d076', '5237',
        _1=primitive_string_multiline_5242.out(0),
        clip=getnode_42.out(0),
        image=resize_image_mask_node_2.out(0),
    )
    setnode_27 = node(wf, 'SetNode', '5260',
        widget_0='latent_audio_custom',
        LATENT=set_latent_noise_mask_5081.out(0),
    )
    comfyswitchnode_4 = _comfy_switchnode(wf, '5273', empty_audio_5289.out(0), getnode_59.out(0), None)
    setnode_33 = node(wf, 'SetNode', '5282',
        widget_0='audio_custom',
        AUDIO=trim_audio_duration_5283.out(0),
    )
    setnode_35 = node(wf, 'SetNode', '5294',
        widget_0='latent_audio',
        LATENT=empty_audio_latent.out('LATENT'),
    )
    positive_prompt = node(wf, 'CLIPTextEncode', '2483',
        text=n_94e8f3a0_557f_4580_93a0_f762c7b0d076.out(0),
        clip=get_node_5137.out(0),
    )
    av_latent_4528 = node(wf, 'LTXVConcatAVLatent', '4528',
        audio_latent=getnode_49.out(0),
        video_latent=guided_latent.out('LATENT'),
    )
    cfg_guider_4828 = node(wf, 'CFGGuider', '4828',
        cfg=2.5,
        model=getnode_9.out(0),
        negative=guided_latent.out('NEGATIVE'),
        positive=guided_latent.out('POSITIVE'),
    )
    resize_image_mask_node_5026 = node(wf, 'ResizeImageMaskNode', '5026',
        resize_type='scale shorter dimension',
scale_method='lanczos',
        input=resize_image_mask_node_3.out(0),
    )
    setnode_13 = node(wf, 'SetNode', '5165',
        widget_0='positive_guider',
        CONDITIONING=guided_latent.out('POSITIVE'),
    )
    setnode_14 = node(wf, 'SetNode', '5166',
        widget_0='negative_guider',
        CONDITIONING=guided_latent.out('NEGATIVE'),
    )
    get_image_size_1 = node(wf, 'GetImageSize', '5219',
        image=resize_image_mask_node_3.out(0),
    )
    model_chunked_ffn = node(wf, 'LTXVChunkFeedForward', '5232',
        chunks=2,
        dim_threshold=4096,
        model=model_with_sage_attn.out('MODEL'),
    )
    comfyswitchnode_5 = _comfy_switch_node_variant(wf, '5274', comfyswitchnode_4.out('OUTPUT'), getnode_58.out(0))
    conditioning = node(wf, 'LTXVConditioning', '1241',
        frame_rate=getnode_39.out(0),
        negative=negative_prompt.out('CONDITIONING'),
        positive=positive_prompt.out('CONDITIONING'),
    )
    sampled_latent_4829 = node(wf, 'SamplerCustomAdvanced', '4829',
        guider=cfg_guider_4828.out('GUIDER'),
        latent_image=av_latent_4528.out('LATENT'),
        noise=noise_4832.out('NOISE'),
        sampler=sampler_kind_4831.out('SAMPLER'),
        sigmas=sigmas_5025.out('SIGMAS'),
    )
    # ════ CONTROL ════
    pose_estimated = node(wf, 'DWPreprocessor', '4986',
        detect_hand='enable',
        detect_body='enable',
        detect_face='enable',
        resolution=512,
        bbox_detector='yolox_l.onnx',
        pose_estimator='dw-ll_ucoco_384_bs5.torchscript.pt',
        scale_stick_for_xinsr_cn='disable',
        image=resize_image_mask_node_5026.out(0),
    )
    depth_anything_preprocessor_5114 = node(wf, 'DepthAnythingPreprocessor', '5114',
        widget_0='depth_anything_vitl14.pth',
        widget_1=512,
        image=resize_image_mask_node_5026.out(0),
    )
    imageresizekjv2_2 = node(wf, 'ImageResizeKJv2', '5221',
        
        upscale_method='nearest-exact',
        keep_proportion='crop',
        pad_color='0, 0, 0',
        crop_position='center',
        device='cpu',
        divisible_by=simplemath_.out(0),
        height=get_image_size_1.out(1),
        image=getnode_55.out(0),
        width=get_image_size_1.out(0),
    )
    model_attention_tuned = node(wf, 'LTX2AttentionTunerPatch', '5233',
        blocks='',
        video_scale=1,
        audio_scale=1,
        video_to_audio_scale=1,
        audio_to_video_scale=1,
        triton_kernels=False,
        model=model_chunked_ffn.out('MODEL'),
    )
    setnode_34 = node(wf, 'SetNode', '5293',
        widget_0='audio_selected',
        AUDIO=comfyswitchnode_5.out('OUTPUT'),
    )
    av_latent_separated_4845 = node(wf, 'LTXVSeparateAVLatent', '4845',
        av_latent=sampled_latent_4829.out('OUTPUT'),
    )
    get_image_size_5029 = node(wf, 'GetImageSize', '5029',
        image=imageresizekjv2_2.out('IMAGE'),
    )
    image_blend_5115 = node(wf, 'ImageBlend', '5115',
        widget_0=0.5,
        widget_1='multiply',
        image1=pose_estimated.out('IMAGE'),
        image2=depth_anything_preprocessor_5114.out(0),
    )
    video_output_5120 = node(wf, 'VHS_VideoCombine', '5120',
        images=imageresizekjv2_2.out('IMAGE'),
    )
    setnode_7 = node(wf, 'SetNode', '5151',
        widget_0='ref_video',
        IMAGE=imageresizekjv2_2.out('IMAGE'),
    )
    setnode_11 = node(wf, 'SetNode', '5161',
        widget_0='positive',
        CONDITIONING=conditioning.out('POSITIVE'),
    )
    setnode_12 = node(wf, 'SetNode', '5162',
        widget_0='negative',
        CONDITIONING=conditioning.out('NEGATIVE'),
    )
    power_lora_loader__rgthree_ = node(wf, 'Power Lora Loader (rgthree)', '5275',
model=model_attention_tuned.out('MODEL'),
    )
    setnode_31 = node(wf, 'SetNode', '5277',
        widget_0='ref_pose',
        IMAGE=pose_estimated.out('IMAGE'),
    )
    cropped_latent_5013 = node(wf, 'LTXVCropGuides', '5013',
        latent=av_latent_separated_4845.out('VIDEO_LATENT'),
        negative=getnode_20.out(0),
        positive=getnode_19.out(0),
    )
    setnode_8 = node(wf, 'SetNode', '5153',
        widget_0='ref_height',
        INT=get_image_size_5029.out(1),
    )
    setnode_9 = node(wf, 'SetNode', '5154',
        widget_0='ref_width',
        INT=get_image_size_5029.out(0),
    )
    setnode_10 = node(wf, 'SetNode', '5155',
        widget_0='ref_frames',
        INT=get_image_size_5029.out(2),
    )
    setnode_25 = node(wf, 'SetNode', '5234',
        widget_0='model_with_lora',
        MODEL=power_lora_loader__rgthree_.out(0),
    )
    setnode_30 = node(wf, 'SetNode', '5276',
        widget_0='ref_blended',
        IMAGE=image_blend_5115.out(0),
    )
    ltxvimg_to_video_inplace = node(wf, 'LTXVImgToVideoInplace', '5067',
        widget_0=0.7,
        widget_1=False,
        bypass=getnode_27.out(0),
        image=getnode_25.out(0),
        latent=cropped_latent_5013.out(2),
        vae=getnode_4.out(0),
    )
    av_latent_2 = node(wf, 'LTXVConcatAVLatent', '5072',
        audio_latent=av_latent_separated_4845.out('AUDIO_LATENT'),
        video_latent=ltxvimg_to_video_inplace.out(0),
    )
    sampled_latent_2 = node(wf, 'SamplerCustomAdvanced', '5073',
        guider=cfg_guider_1.out('GUIDER'),
        latent_image=av_latent_2.out('LATENT'),
        noise=noise_2.out('NOISE'),
        sampler=sampler_kind_2.out('SAMPLER'),
        sigmas=sigmas_2.out('SIGMAS'),
    )
    av_latent_separated_2 = node(wf, 'LTXVSeparateAVLatent', '5074',
        av_latent=sampled_latent_2.out('OUTPUT'),
    )
    decoded_audio = node(wf, 'LTXVAudioVAEDecode', '5076',
        audio_vae=getnode_6.out(0),
        samples=av_latent_separated_2.out('AUDIO_LATENT'),
    )
    cropped_latent_2 = node(wf, 'LTXVCropGuides', '5082',
        latent=av_latent_separated_2.out('VIDEO_LATENT'),
        negative=getnode_23.out(0),
        positive=getnode_24.out(0),
    )
    decoded_video_5075 = node(wf, 'VAEDecodeTiled', '5075',
        tile_size=544,
        overlap=64,
        temporal_size=4096,
        temporal_overlap=4,
        samples=cropped_latent_2.out(2),
        vae=getnode_5.out(0),
    )
    comfyswitchnode_2 = _comfy_switchnode(wf, '5264', decoded_audio.out(0), getnode_36.out(0), getnode_65.out(0))
    setnode_28 = node(wf, 'SetNode', '5265',
        widget_0='audio_output',
        AUDIO=comfyswitchnode_2.out('OUTPUT'),
    )
    setnode_29 = node(wf, 'SetNode', '5266',
        widget_0='video_output',
        IMAGE=decoded_video_5075.out('IMAGE'),
    )

    return finalize(
        wf,
        PUBLIC_INPUTS,
        READY_METADATA,
        output_node='',
        source_path=__file__,
    )

