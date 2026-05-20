# vibecomfy: generated — converted by tools/convert_ready_templates.py
# Edits will be overwritten on regeneration. Add a `# vibecomfy: manual`
# marker on the first line if hand-editing is required.
"""Video To Video Talking Avatar with CLIP Vision H CLIP.

Output: unknown.

Source:  workflow_corpus/custom_nodes/wanvideo_wrapper/kijai/wan21_14b_v2v_infinitetalk.json

Packs:   ComfyUI-KJNodes, ComfyUI-VideoHelperSuite, ComfyUI-WanVideoWrapper, rgthree-comfy
"""
from __future__ import annotations

from vibecomfy.workflow import VibeWorkflow
from vibecomfy.templates import InputSpec, ModelAsset, ReadyMetadata, finalize, new_workflow, node

def _getnode(wf, _id, **overrides):
    kwargs = dict(widget_0='VAE')
    kwargs.update(overrides)
    return node(wf, 'GetNode', _id, **kwargs)
MODELS = {
    'clip_vision_h_clip': ModelAsset(
        filename='clip_vision_h.safetensors',
        url='',
        subdir='text_encoders',
    ),
}

PUBLIC_INPUTS = {}

READY_METADATA = ReadyMetadata.build(
    template_id='wanvideo_wrapper_21_14b_v2v_infinitetalk',
    capability='video_to_video_talking_avatar',
    inputs=PUBLIC_INPUTS,
    models=MODELS,
    output_prefix='',
    requirements={'custom_nodes': ['ComfyUI-KJNodes', 'ComfyUI-VideoHelperSuite', 'ComfyUI-WanVideoWrapper', 'rgthree-comfy'], 'custom_node_refs': [{'slug': 'ComfyUI-KJNodes', 'source': 'git', 'commit': 'b7646ad70a7daa7aeb919ca542274758d26ba2df', 'url': 'https://github.com/kijai/ComfyUI-KJNodes.git'}, {'slug': 'ComfyUI-VideoHelperSuite', 'source': 'git',
                       'commit': '4ee72c065db22c9d96c2427954dc69e7b908444b', 'url': 'https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite.git'}, {'slug': 'ComfyUI-WanVideoWrapper', 'source': 'git', 'commit': 'df8f3e49daaad117cf3090cc916c83f3d001494c', 'url': 'https://github.com/kijai/ComfyUI-WanVideoWrapper.git'}, {'slug': 'rgthree-comfy', 'source': 'git',
                       'commit': '738105af5fb14e96fbecaf406dc356e284797e8c', 'url': 'https://github.com/rgthree/rgthree-comfy.git'}]},
    provenance={'approach': 'InfiniteTalk video-to-video talking avatar', 'source_workflow': 'workflow_corpus/custom_nodes/wanvideo_wrapper/kijai/wan21_14b_v2v_infinitetalk.json', 'smoke_resolution': '256x256x5_frames', 'source_role': 'materialized_ready_python_template'},
    coverage_tier='supplemental',
    vibecomfy_version='0.1.0',
    comfy_core={'version': '0.18.2', 'tested_at': '2026-05-20T09:19:32.302139+00:00', 'commit': 'f7b38d2eb97207cd834bcc3eb2e8b1d447b96c68', 'status': 'discovered'},
)

def build() -> VibeWorkflow:
    """Build the workflow (auto-generated)."""
    wf = new_workflow(READY_METADATA, source_path=__file__)

    # ════ LOADERS ════
    multi_talk_model_loader_120 = node(wf, 'MultiTalkModelLoader', '120',
        widget_0='WanVideo\\InfiniteTalk\\InfiniteTalk\\Wan2_1-InfiniteTalk_Single_Q8.gguf',
    )
    load_audio_125 = node(wf, 'LoadAudio', '125',
        audio='one-does-not-simply-walk-into-mordor-its-black-gates-are-guarded-by-more-than-just-orcs.mp3',
        widget_1=None,
        widget_2=None,
    )
    wan_video_vaeloader = node(wf, 'WanVideoVAELoader', '129',
        model_name='wanvideo\\Wan2_1_VAE_bf16.safetensors',
        precision='bf16',
    )
    # ════ SAMPLING ════
    wan_video_block_swap_134 = node(wf, 'WanVideoBlockSwap', '134',
        blocks_to_swap=20,
        offload_img_emb=False,
        offload_txt_emb=False,
        use_non_blocking=True,
        vace_blocks_to_swap=0,
        prefetch_blocks=1,
        block_swap_debug=False,
    )
    download_and_load_wav2_vec_model_137 = node(wf, 'DownloadAndLoadWav2VecModel', '137',
        widget_0='TencentGameMate/chinese-wav2vec2-base',
        widget_1='fp16',
        widget_2='main_device',
    )
    wan_video_lora_select_138 = node(wf, 'WanVideoLoraSelect', '138',
        lora='WanVideo\\Lightx2v\\lightx2v_I2V_14B_480p_cfg_step_distill_rank64_bf16.safetensors',
        strength=1,
        low_mem_load=False,
        merge_loras=False,
    )
    wan_video_torch_compile_settings_177 = node(wf, 'WanVideoTorchCompileSettings', '177',
        backend='inductor',
        fullgraph=False,
        mode='default',
        dynamic=False,
        dynamo_cache_size_limit=64,
        compile_transformer_blocks_only=True,
        dynamo_recompile_limit=128,
    )
    clip_vision = node(wf, 'CLIPVisionLoader', '238',
        clip_name=MODELS['clip_vision_h_clip'].filename,
    )
    # ════ TEXT CONDITIONING ════
    wan_video_text_encode_cached_241 = node(wf, 'WanVideoTextEncodeCached', '241',
        model_name='umt5-xxl-enc-bf16.safetensors',
        precision='bf16',
        positive_prompt='a woman is singing a lullaby',
        negative_prompt='bright tones, overexposed, static, blurred details, subtitles, style, works, paintings, images, static, overall gray, worst quality, low quality, JPEG compression residue, ugly, incomplete, extra fingers, poorly drawn hands, poorly drawn faces, deformed, disfigured, misshapen limbs, fused fingers, still picture, messy background, three legs, many people in the background, walking backwards',
        quantization='disabled',
        use_disk_cache=False,
        device='gpu',
    )
    get_node_242 = _getnode(wf, '242', )
    getnode_2 = _getnode(wf, '243', )
    getnode_3 = _getnode(wf, '244', )
    param_int_245 = node(wf, 'INTConstant', '245',
        value=640,
    )
    param_INT = node(wf, 'INTConstant', '246',
        value=640,
    )
    getnode_4 = node(wf, 'GetNode', '249',
        widget_0='height',
    )
    getnode_5 = node(wf, 'GetNode', '250',
        widget_0='width',
    )
    getnode_6 = node(wf, 'GetNode', '254',
        widget_0='input_audio',
    )
    getnode_7 = node(wf, 'GetNode', '261',
        widget_0='wanmodel',
    )
    getnode_8 = node(wf, 'GetNode', '265',
        widget_0='clip_vision_model',
    )
    param_INT_2 = node(wf, 'INTConstant', '270',
        value=1000,
    )
    getnode_9 = node(wf, 'GetNode', '272',
        widget_0='max_frames',
    )
    mel_band_ro_former_model_loader_303 = node(wf, 'MelBandRoFormerModelLoader', '303',
        widget_0='MelBandRoFormer\\MelBandRoformer_fp16.safetensors',
    )
    wav2_vec_model_loader_306 = node(wf, 'Wav2VecModelLoader', '306',
        widget_0='wav2vec2-chinese-base_fp16.safetensors',
        widget_1='fp16',
        widget_2='main_device',
    )
    wan_video_model_loader_122 = node(wf, 'WanVideoModelLoader', '122',
        model='WanVideo\\wan2.1-i2v-14b-480p-Q8_0.gguf',
        base_precision='fp16',
        quantization='disabled',
        load_device='offload_device',
        attention_mode='sdpa',
        block_swap_args=wan_video_block_swap_134.out(0),
        lora=wan_video_lora_select_138.out(0),
        multitalk_model=multi_talk_model_loader_120.out(0),
    )
    vhs__load_video = node(wf, 'VHS_LoadVideo', '228',
        video='wolf_interpolated.mp4',
        custom_height=getnode_4.out(0),
        custom_width=getnode_5.out(0),
    )
    set_node_240 = node(wf, 'SetNode', '240',
        widget_0='VAE',
        WANVAE=wan_video_vaeloader.out(0),
    )
    setnode_2 = node(wf, 'SetNode', '247',
        widget_0='width',
        INT=param_int_245.out('VALUE'),
    )
    setnode_3 = node(wf, 'SetNode', '248',
        widget_0='height',
        INT=param_INT.out('VALUE'),
    )
    setnode_4 = node(wf, 'SetNode', '253',
        widget_0='input_audio',
        AUDIO=load_audio_125.out(0),
    )
    setnode_6 = node(wf, 'SetNode', '264',
        widget_0='clip_vision_model',
        CLIP_VISION=clip_vision.out('CLIP_VISION'),
    )
    setnode_7 = node(wf, 'SetNode', '271',
        widget_0='max_frames',
        INT=param_INT_2.out('VALUE'),
    )
    # ════ IMAGE PREP ════
    resized_image = node(wf, 'ImageResizeKJv2', '230',
        
        upscale_method='lanczos',
        keep_proportion='crop',
        pad_color='0, 0, 0',
        crop_position='center',
        divisible_by=16,
        device='cpu',
        height=getnode_4.out(0),
        image=vhs__load_video.out(0),
        width=getnode_5.out(0),
    )
    setnode_5 = node(wf, 'SetNode', '260',
        widget_0='wanmodel',
        WANVIDEOMODEL=wan_video_model_loader_122.out(0),
    )
    mel_band_ro_former_sampler_304 = node(wf, 'MelBandRoFormerSampler', '304',
        audio=setnode_4.out(0),
        model=mel_band_ro_former_model_loader_303.out(0),
    )
    multi_talk_wav2_vec_embeds_194 = node(wf, 'MultiTalkWav2VecEmbeds', '194',
        widget_0=True,
        widget_1=400,
        widget_2=25,
        widget_3=1.5,
        widget_4=1,
        widget_5='para',
        audio_1=mel_band_ro_former_sampler_304.out(0),
        num_frames=getnode_9.out(0),
        wav2vec_model=download_and_load_wav2_vec_model_137.out(0),
    )
    wan_video_encode_229 = node(wf, 'WanVideoEncode', '229',
        widget_0=False,
        widget_1=272,
        widget_2=272,
        widget_3=144,
        widget_4=128,
        widget_5=0,
        widget_6=1,
        image=resized_image.out('IMAGE'),
        vae=getnode_2.out(0),
    )
    get_image_range_from_batch_231 = node(wf, 'GetImageRangeFromBatch', '231',
        widget_0=0,
        widget_1=1,
        images=resized_image.out('IMAGE'),
    )
    get_image_size_and_count_291 = node(wf, 'GetImageSizeAndCount', '291',
        image=get_image_range_from_batch_231.out(0),
    )
    setnode_8 = node(wf, 'SetNode', '294',
        widget_0='actual_audio_frames',
        INT=multi_talk_wav2_vec_embeds_194.out(2),
    )
    wan_video_clip_vision_encode_237 = node(wf, 'WanVideoClipVisionEncode', '237',
        strength_1=1,
        strength_2=1,
        crop='center',
        combine_embeds='average',
        force_offload=True,
        tiles=0,
        ratio=0.5,
        clip_vision=getnode_8.out(0),
        image_1=get_image_size_and_count_291.out(0),
    )
    # ════ OUTPUT ════
    preview_any_293 = node(wf, 'PreviewAny', '293',
        source=setnode_8.out(0),
    )
    wan_video_image_to_video_multi_talk_192 = node(wf, 'WanVideoImageToVideoMultiTalk', '192',
        widget_0=832,
        widget_1=480,
        widget_2=81,
        widget_3=9,
        widget_4=False,
        widget_5='disabled',
        widget_6=False,
        widget_7='infinitetalk',
        clip_embeds=wan_video_clip_vision_encode_237.out(0),
        height=get_image_size_and_count_291.out(2),
        start_image=get_image_size_and_count_291.out(0),
        vae=getnode_3.out(0),
        width=get_image_size_and_count_291.out(1),
    )
    wan_video_sampler_128 = node(wf, 'WanVideoSampler', '128',
        steps=1,
        cfg=1.0000000000000002,
        rope_function='comfy',
        start_step=2,
        end_step=-1,
        add_noise_to_samples=True,
        shift=11.000000000000002,
        seed=2,
force_offload=True,
        scheduler='dpm++_sde',
        riflex_freq_index=0,
        denoise_strength=1,
        batched_cfg=False,
        image_embeds=wan_video_image_to_video_multi_talk_192.out(0),
        model=getnode_7.out(0),
        multitalk_embeds=multi_talk_wav2_vec_embeds_194.out(0),
        samples=wan_video_encode_229.out(0),
        text_embeds=wan_video_text_encode_cached_241.out(0),
    )
    # ════ DECODE ════
    wan_video_decode_130 = node(wf, 'WanVideoDecode', '130',
        enable_vae_tiling=False,
        tile_x=272,
        tile_y=272,
        tile_stride_x=144,
        tile_stride_y=128,
        normalization='default',
        samples=wan_video_sampler_128.out(0),
        vae=get_node_242.out(0),
    )
    get_image_size_and_count_2 = node(wf, 'GetImageSizeAndCount', '300',
        image=wan_video_decode_130.out(0),
    )
    get_image_range_from_batch_2 = node(wf, 'GetImageRangeFromBatch', '301',
        widget_0=0,
        widget_1=1,
        images=get_image_size_and_count_2.out(0),
        num_frames=get_image_size_and_count_2.out(3),
    )
    image_concat_multi_299 = node(wf, 'ImageConcatMulti', '299',
        inputcount=2,
        direction='left',
        match_image_size=False,
        unused_3=None,
        image_1=get_image_range_from_batch_2.out(0),
        image_2=resized_image.out('IMAGE'),
    )
    video_output = node(wf, 'VHS_VideoCombine', '131',
        save_output=True,
        audio=getnode_6.out(0),
        images=image_concat_multi_299.out(0),
    )

    return finalize(
        wf,
        PUBLIC_INPUTS,
        READY_METADATA,
        output_node='',
        source_path=__file__,
    )

