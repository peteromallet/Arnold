# vibecomfy: generated — converted by tools/convert_ready_templates.py
# Edits will be overwritten on regeneration. Add a `# vibecomfy: manual`
# marker on the first line if hand-editing is required.
"""Speech To Video Pose Control.

Output: unknown.

Source:  workflow_corpus/custom_nodes/wanvideo_wrapper/kijai/wan22_s2v_framepack_pose.json

Packs:   ComfyUI-KJNodes, ComfyUI-VideoHelperSuite, ComfyUI-WanVideoWrapper, comfyui_controlnet_aux, rgthree-comfy
"""
from __future__ import annotations

from vibecomfy.workflow import VibeWorkflow
from vibecomfy.templates import InputSpec, ModelAsset, ReadyMetadata, finalize, new_workflow, node

def _get_node_VAE(wf, _id, **overrides):
    kwargs = dict(widget_0='VAE')
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
MODELS = {}

PUBLIC_INPUTS = {}

READY_METADATA = ReadyMetadata.build(
    template_id='wanvideo_wrapper_22_s2v_framepack_pose',
    capability='speech_to_video_pose_control',
    inputs=PUBLIC_INPUTS,
    models=MODELS,
    output_prefix='',
    requirements={'custom_nodes': ['ComfyUI-KJNodes', 'ComfyUI-VideoHelperSuite', 'ComfyUI-WanVideoWrapper', 'comfyui_controlnet_aux', 'rgthree-comfy'], 'custom_node_refs': [{'slug': 'ComfyUI-KJNodes', 'source': 'git', 'commit': 'b7646ad70a7daa7aeb919ca542274758d26ba2df', 'url': 'https://github.com/kijai/ComfyUI-KJNodes.git'}, {'slug': 'ComfyUI-VideoHelperSuite', 'source': 'git',
                       'commit': '4ee72c065db22c9d96c2427954dc69e7b908444b', 'url': 'https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite.git'}, {'slug': 'ComfyUI-WanVideoWrapper', 'source': 'git', 'commit': 'df8f3e49daaad117cf3090cc916c83f3d001494c', 'url': 'https://github.com/kijai/ComfyUI-WanVideoWrapper.git'}, {'slug': 'comfyui_controlnet_aux', 'source': 'git',
                       'commit': 'e8b689a513c3e6b63edc44066560ca5919c0576e', 'url': 'https://github.com/Fannovel16/comfyui_controlnet_aux.git'}, {'slug': 'rgthree-comfy', 'source': 'git',
                       'commit': '738105af5fb14e96fbecaf406dc356e284797e8c', 'url': 'https://github.com/rgthree/rgthree-comfy.git'}]},
    provenance={'source_role': 'materialized_ready_python_template', 'approach': 'S2V framepack pose workflow', 'smoke_resolution': '256x256x5_frames', 'source_workflow': 'workflow_corpus/custom_nodes/wanvideo_wrapper/kijai/wan22_s2v_framepack_pose.json'},
    coverage_tier='supplemental',
    vibecomfy_version='0.1.0',
    comfy_core={'version': '0.18.2', 'tested_at': '2026-05-20T09:19:32.302139+00:00', 'commit': 'f7b38d2eb97207cd834bcc3eb2e8b1d447b96c68', 'status': 'discovered'},
)

def build() -> VibeWorkflow:
    """Build the workflow (auto-generated)."""
    wf = new_workflow(READY_METADATA, source_path=__file__)

    # ════ SAMPLING ════
    wan_video_torch_compile_settings_35 = node(wf, 'WanVideoTorchCompileSettings', '35',
        backend='inductor',
        fullgraph=False,
        mode='default',
        dynamic=False,
        dynamo_cache_size_limit=64,
        compile_transformer_blocks_only=True,
        dynamo_recompile_limit=128,
    )
    # ════ LOADERS ════
    wan_video_vaeloader = node(wf, 'WanVideoVAELoader', '38',
        model_name='wanvideo\\Wan2_1_VAE_bf16.safetensors',
        precision='bf16',
    )
    wan_video_block_swap_39 = node(wf, 'WanVideoBlockSwap', '39',
        blocks_to_swap=32,
        offload_img_emb=False,
        offload_txt_emb=False,
        use_non_blocking=True,
        vace_blocks_to_swap=0,
        prefetch_blocks=1,
        block_swap_debug=False,
    )
    wan_video_lora_select_multi_60 = node(wf, 'WanVideoLoraSelectMulti', '60',
        lora_0='WanVideo\\Lightx2v\\lightx2v_T2V_14B_cfg_step_distill_v2_lora_rank64_bf16.safetensors',
        strength_0=1.2,
        low_mem_load=False,
        merge_loras=False,
        lora_1='none',
        strength_1=1,
        lora_2='none',
        strength_2=1,
        lora_3='none',
        strength_3=1,
        lora_4='none',
        strength_4=1,
    )
    audio_encoder_loader_65 = node(wf, 'AudioEncoderLoader', '65',
        widget_0='wav2vec_xlsr_53_english_fp32.safetensors',
    )
    load_audio_66 = node(wf, 'LoadAudio', '66',
        audio='0321. Alphaville - Big In Japan.mp3',
        widget_1=None,
        widget_2=None,
    )
    # ════ TEXT CONDITIONING ════
    wan_video_text_encode_cached_67 = node(wf, 'WanVideoTextEncodeCached', '67',
        model_name='umt5-xxl-enc-bf16.safetensors',
        precision='bf16',
        positive_prompt='3D animated scene of a young woman singing melancholically',
        negative_prompt='色调艳丽，过曝，静态，细节模糊不清，字幕，风格，作品，画作，画面，静止，整体发灰，最差质量，低质量，JPEG压缩残留，丑陋的，残缺的，多余的手指，画得不好的手部，画得不好的脸部，畸形的，毁容的，形态畸形的肢体，手指融合，静止不动的画面，杂乱的背景，三条腿，背景人很多，倒着走',
        quantization='disabled',
        use_disk_cache=True,
        device='gpu',
    )
    primitive_node_71 = node(wf, 'PrimitiveNode', '71',
        widget_0=501,
        widget_1='fixed',
    )
    input_image = node(wf, 'LoadImage', '73',
        image='2b.jpg',
)
    mel_band_ro_former_model_loader_81 = node(wf, 'MelBandRoFormerModelLoader', '81',
        widget_0='MelBandRoFormer\\MelBandRoformer_fp16.safetensors',
    )
    vhs__load_audio = node(wf, 'VHS_LoadAudio', '94')
    get_node_120 = _get_node_VAE(wf, '120', )
    getnode_2 = _get_node_VAE(wf, '121', )
    getnode_3 = _get_node_VAE(wf, '122', )
    getnode_4 = node(wf, 'GetNode', '126',
        widget_0='reference_image',
    )
    reroute_129 = node(wf, 'Reroute', '129')
    reroute_2 = node(wf, 'Reroute', '130')
    param_int_131 = node(wf, 'INTConstant', '131',
        value=640,
    )
    param_INT = node(wf, 'INTConstant', '132',
        value=640,
    )
    getnode_5 = _get_node_width(wf, '137', )
    getnode_6 = _get_node_height(wf, '138', )
    getnode_7 = _get_node_width(wf, '139', )
    getnode_8 = _get_node_height(wf, '140', )
    getnode_9 = _get_node_width(wf, '141', )
    getnode_10 = _get_node_height(wf, '142', )
    wan_video_model_loader_22 = node(wf, 'WanVideoModelLoader', '22',
        model='WanVideo\\S2V\\Wan2_2-S2V-14B_fp8_e4m3fn_scaled_KJ.safetensors',
        base_precision='fp16',
        quantization='fp8_e4m3fn_scaled',
        load_device='offload_device',
        attention_mode='sdpa',
        compile_args=wan_video_torch_compile_settings_35.out(0),
    )
    # ════ IMAGE PREP ════
    resized_image_74 = node(wf, 'ImageResizeKJv2', '74',
        
        upscale_method='lanczos',
        keep_proportion='crop',
        pad_color='0, 0, 0',
        crop_position='center',
        divisible_by=16,
        device='cpu',
height=getnode_6.out(0),
        image=input_image.out('IMAGE'),
        width=getnode_5.out(0),
    )
    vhs__load_video_1 = node(wf, 'VHS_LoadVideo', '106',
        video='wolf_interpolated.mp4',
        custom_height=getnode_10.out(0),
        custom_width=getnode_9.out(0),
        frame_load_cap=primitive_node_71.out(0),
    )
    vhs_loadvideo_2 = node(wf, 'VHS_LoadVideo', '116',
        video='wolf_interpolated.mp4',
        custom_height=getnode_8.out(0),
        custom_width=getnode_7.out(0),
        frame_load_cap=primitive_node_71.out(0),
    )
    set_node_119 = node(wf, 'SetNode', '119',
        widget_0='VAE',
        WANVAE=wan_video_vaeloader.out(0),
    )
    setnode_3 = node(wf, 'SetNode', '133',
        widget_0='width',
        INT=param_int_131.out('VALUE'),
    )
    setnode_4 = node(wf, 'SetNode', '134',
        widget_0='height',
        INT=param_INT.out('VALUE'),
    )
    wan_video_empty_embeds_37 = node(wf, 'WanVideoEmptyEmbeds', '37',
        widget_0=256,
        widget_1=256,
        widget_2=5,
        height=resized_image_74.out(2),
        num_frames=primitive_node_71.out(0),
        width=resized_image_74.out(1),
    )
    wan_video_set_lo_r_as_58 = node(wf, 'WanVideoSetLoRAs', '58',
        lora=wan_video_lora_select_multi_60.out(0),
        model=wan_video_model_loader_22.out(0),
    )
    mel_band_ro_former_sampler_82 = node(wf, 'MelBandRoFormerSampler', '82',
        audio=vhs__load_video_1.out(2),
        model=mel_band_ro_former_model_loader_81.out(0),
    )
    imageresizekjv2_2 = node(wf, 'ImageResizeKJv2', '110',
        
        upscale_method='bilinear',
        keep_proportion='crop',
        pad_color='0, 0, 0',
        crop_position='center',
        divisible_by=16,
        device='cpu',
        height=getnode_8.out(0),
        image=vhs_loadvideo_2.out(0),
        width=getnode_7.out(0),
    )
    setnode_2 = node(wf, 'SetNode', '125',
        widget_0='reference_image',
        IMAGE=resized_image_74.out('IMAGE'),
    )
    wan_video_set_block_swap_56 = node(wf, 'WanVideoSetBlockSwap', '56',
        block_swap_args=wan_video_block_swap_39.out(0),
        model=wan_video_set_lo_r_as_58.out(0),
    )
    wan_video_encode_72 = node(wf, 'WanVideoEncode', '72',
        widget_0=False,
        widget_1=272,
        widget_2=272,
        widget_3=144,
        widget_4=128,
        widget_5=0,
        widget_6=1,
        image=setnode_2.out(0),
        vae=getnode_2.out(0),
    )
    normalize_audio_loudness_98 = node(wf, 'NormalizeAudioLoudness', '98',
        widget_0=-23,
        audio=mel_band_ro_former_sampler_82.out(0),
    )
    # ════ CONTROL ════
    pose_estimated = node(wf, 'DWPreprocessor', '107',
        detect_hand='disable',
        detect_body='disable',
        detect_face='enable',
        resolution=640,
        bbox_detector='yolox_l.torchscript.pt',
        pose_estimator='dw-ll_ucoco_384_bs5.torchscript.pt',
        image=imageresizekjv2_2.out('IMAGE'),
    )
    audio_encoder_encode_64 = node(wf, 'AudioEncoderEncode', '64',
        audio=normalize_audio_loudness_98.out(0),
        audio_encoder=audio_encoder_loader_65.out(0),
    )
    imageresizekjv2_3 = node(wf, 'ImageResizeKJv2', '111',
        height=256,
        
        upscale_method='bilinear',
        keep_proportion='stretch',
        pad_color='0, 0, 0',
        crop_position='center',
        divisible_by=16,
        device='gpu',
        width=256,
        image=pose_estimated.out('IMAGE'),
    )
    wan_video_encode_2 = node(wf, 'WanVideoEncode', '109',
        widget_0=False,
        widget_1=272,
        widget_2=272,
        widget_3=144,
        widget_4=128,
        widget_5=0,
        widget_6=0.5,
        image=imageresizekjv2_3.out('IMAGE'),
        vae=getnode_3.out(0),
    )
    wan_video_add_s2_v_embeds_117 = node(wf, 'WanVideoAddS2VEmbeds', '117',
        widget_0=80,
        widget_1=1,
        widget_2=0,
        widget_3=1,
        widget_4=True,
        audio_encoder_output=audio_encoder_encode_64.out(0),
        embeds=wan_video_empty_embeds_37.out(0),
        pose_latent=wan_video_encode_2.out(0),
        ref_latent=wan_video_encode_72.out(0),
        vae=getnode_2.out(0),
    )
    wan_video_sampler_27 = node(wf, 'WanVideoSampler', '27',
        steps=1,
        cfg=1,
        rope_function='comfy',
        start_step=0,
        end_step=-1,
        add_noise_to_samples=False,
        shift=4,
        seed=45,
force_offload=True,
        scheduler='lcm',
        riflex_freq_index=0,
        denoise_strength=1,
        batched_cfg=False,
        image_embeds=wan_video_add_s2_v_embeds_117.out(0),
        model=wan_video_set_block_swap_56.out(0),
        text_embeds=wan_video_text_encode_cached_67.out(0),
    )
    # ════ OUTPUT ════
    preview_any_118 = node(wf, 'PreviewAny', '118',
        source=wan_video_add_s2_v_embeds_117.out(1),
    )
    # ════ DECODE ════
    wan_video_decode_28 = node(wf, 'WanVideoDecode', '28',
        enable_vae_tiling=False,
        tile_x=272,
        tile_y=272,
        tile_stride_x=144,
        tile_stride_y=128,
        normalization='default',
        samples=wan_video_sampler_27.out(0),
        vae=get_node_120.out(0),
    )
    get_image_size_and_count_70 = node(wf, 'GetImageSizeAndCount', '70',
        image=wan_video_decode_28.out(0),
    )
    get_image_range_from_batch_143 = node(wf, 'GetImageRangeFromBatch', '143',
        widget_0=0,
        widget_1=501,
        images=get_image_size_and_count_70.out(0),
        num_frames=primitive_node_71.out(0),
    )
    color_match_105 = node(wf, 'ColorMatch', '105',
        widget_0='mkl',
        widget_1=1,
        widget_2=True,
        image_ref=getnode_4.out(0),
        image_target=get_image_range_from_batch_143.out(0),
    )
    image_concat_multi_112 = node(wf, 'ImageConcatMulti', '112',
        inputcount=2,
        direction='right',
        match_image_size=False,
        unused_3=None,
        image_1=reroute_2.out(0),
        image_2=color_match_105.out(0),
    )
    lazy_switch_k_j_127 = node(wf, 'LazySwitchKJ', '127',
        widget_0=True,
        on_false=color_match_105.out(0),
        on_true=image_concat_multi_112.out(0),
    )
    video_output = node(wf, 'VHS_VideoCombine', '97',
        save_output=True,
        audio=reroute_129.out(0),
        images=lazy_switch_k_j_127.out(0),
    )

    return finalize(
        wf,
        PUBLIC_INPUTS,
        READY_METADATA,
        output_node='',
        source_path=__file__,
    )

