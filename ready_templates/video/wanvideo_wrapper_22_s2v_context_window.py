# vibecomfy: generated — converted by tools/convert_ready_templates.py
# Edits will be overwritten on regeneration. Add a `# vibecomfy: manual`
# marker on the first line if hand-editing is required.
"""Speech To Video Context Window.

Output: unknown.

Source:  workflow_corpus/custom_nodes/wanvideo_wrapper/kijai/wan22_s2v_context_window.json

Packs:   ComfyUI-KJNodes, ComfyUI-VideoHelperSuite, ComfyUI-WanVideoWrapper
"""
from __future__ import annotations

from vibecomfy.workflow import VibeWorkflow
from vibecomfy.templates import InputSpec, ModelAsset, ReadyMetadata, finalize, new_workflow, node
MODELS = {}

PUBLIC_INPUTS = {}

READY_METADATA = ReadyMetadata.build(
    template_id='wanvideo_wrapper_22_s2v_context_window',
    capability='speech_to_video_context_window',
    inputs=PUBLIC_INPUTS,
    models=MODELS,
    output_prefix='',
    requirements={'custom_nodes': ['ComfyUI-KJNodes', 'ComfyUI-VideoHelperSuite', 'ComfyUI-WanVideoWrapper'], 'custom_node_refs': [{'slug': 'ComfyUI-KJNodes', 'source': 'git', 'commit': 'b7646ad70a7daa7aeb919ca542274758d26ba2df', 'url': 'https://github.com/kijai/ComfyUI-KJNodes.git'}, {'slug': 'ComfyUI-VideoHelperSuite', 'source': 'git',
                       'commit': '4ee72c065db22c9d96c2427954dc69e7b908444b', 'url': 'https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite.git'}, {'slug': 'ComfyUI-WanVideoWrapper', 'source': 'git', 'commit': 'df8f3e49daaad117cf3090cc916c83f3d001494c', 'url': 'https://github.com/kijai/ComfyUI-WanVideoWrapper.git'}]},
    provenance={'smoke_resolution': '256x256x5_frames', 'source_workflow': 'workflow_corpus/custom_nodes/wanvideo_wrapper/kijai/wan22_s2v_context_window.json', 'approach': 'S2V context-window workflow', 'source_role': 'materialized_ready_python_template'},
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
        blocks_to_swap=25,
        offload_img_emb=False,
        offload_txt_emb=False,
        use_non_blocking=True,
        vace_blocks_to_swap=0,
        prefetch_blocks=1,
        block_swap_debug=False,
    )
    wan_video_lora_select_multi_60 = node(wf, 'WanVideoLoraSelectMulti', '60',
        lora_0='WanVideo\\Lightx2v\\lightx2v_T2V_14B_cfg_step_distill_v2_lora_rank64_bf16.safetensors',
        strength_0=1.5,
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
        audio='NieR_ Automata - _Weight of the World_ ENG VER. by Lizz Robinett [CyOSTbel3AM].mp3',
        widget_1=None,
        widget_2=None,
    )
    # ════ TEXT CONDITIONING ════
    wan_video_text_encode_cached_67 = node(wf, 'WanVideoTextEncodeCached', '67',
        model_name='umt5-xxl-enc-bf16.safetensors',
        precision='bf16',
        positive_prompt='a woman is singing passionately',
        negative_prompt='色调艳丽，过曝，静态，细节模糊不清，字幕，风格，作品，画作，画面，静止，整体发灰，最差质量，低质量，JPEG压缩残留，丑陋的，残缺的，多余的手指，画得不好的手部，画得不好的脸部，畸形的，毁容的，形态畸形的肢体，手指融合，静止不动的画面，杂乱的背景，三条腿，背景人很多，倒着走',
        quantization='disabled',
        use_disk_cache=True,
        device='gpu',
    )
    primitive_node_71 = node(wf, 'PrimitiveNode', '71',
        widget_0=201,
        widget_1='fixed',
    )
    input_image = node(wf, 'LoadImage', '73',
        image='2b.jpg',
)
    mel_band_ro_former_model_loader_81 = node(wf, 'MelBandRoFormerModelLoader', '81',
        widget_0='MelBandRoFormer\\MelBandRoformer_fp16.safetensors',
    )
    wan_video_context_options_83 = node(wf, 'WanVideoContextOptions', '83',
        widget_0='uniform_standard',
        widget_1=81,
        widget_2=4,
        widget_3=16,
        widget_4=True,
        widget_5=False,
        widget_6='linear',
    )
    vhs__load_audio = node(wf, 'VHS_LoadAudio', '94')
    download_and_load_gimmvfimodel = node(wf, 'DownloadAndLoadGIMMVFIModel', '95',
        widget_0='gimmvfi_r_arb_lpips_fp32.safetensors',
        widget_1='fp16',
        widget_2=False,
    )
    wan_video_model_loader_22 = node(wf, 'WanVideoModelLoader', '22',
        model='WanVideo\\S2V\\Wan2_2-S2V-14B_fp8_e4m3fn_scaled_KJ.safetensors',
        base_precision='fp16',
        quantization='fp8_e4m3fn_scaled',
        load_device='offload_device',
        attention_mode='sdpa',
        compile_args=wan_video_torch_compile_settings_35.out(0),
    )
    # ════ IMAGE PREP ════
    resized_image = node(wf, 'ImageResizeKJv2', '74',
        height=256,
        
        upscale_method='lanczos',
        keep_proportion='crop',
        pad_color='0, 0, 0',
        crop_position='center',
        divisible_by=2,
        device='cpu',
width=256,
        image=input_image.out('IMAGE'),
    )
    mel_band_ro_former_sampler_82 = node(wf, 'MelBandRoFormerSampler', '82',
        audio=vhs__load_audio.out(0),
        model=mel_band_ro_former_model_loader_81.out(0),
    )
    wan_video_empty_embeds_37 = node(wf, 'WanVideoEmptyEmbeds', '37',
        widget_0=256,
        widget_1=256,
        widget_2=5,
        height=resized_image.out(2),
        num_frames=primitive_node_71.out(0),
        width=resized_image.out(1),
    )
    wan_video_set_lo_r_as_58 = node(wf, 'WanVideoSetLoRAs', '58',
        lora=wan_video_lora_select_multi_60.out(0),
        model=wan_video_model_loader_22.out(0),
    )
    # ════ OUTPUT ════
    preview_any_62 = node(wf, 'PreviewAny', '62',
        source=wan_video_model_loader_22.out(0),
    )
    wan_video_encode_72 = node(wf, 'WanVideoEncode', '72',
        widget_0=False,
        widget_1=272,
        widget_2=272,
        widget_3=144,
        widget_4=128,
        widget_5=0,
        widget_6=1,
        image=resized_image.out('IMAGE'),
        vae=wan_video_vaeloader.out(0),
    )
    normalize_audio_loudness_98 = node(wf, 'NormalizeAudioLoudness', '98',
        widget_0=-23,
        audio=mel_band_ro_former_sampler_82.out(0),
    )
    wan_video_set_block_swap_56 = node(wf, 'WanVideoSetBlockSwap', '56',
        block_swap_args=wan_video_block_swap_39.out(0),
        model=wan_video_set_lo_r_as_58.out(0),
    )
    audio_encoder_encode_64 = node(wf, 'AudioEncoderEncode', '64',
        audio=normalize_audio_loudness_98.out(0),
        audio_encoder=audio_encoder_loader_65.out(0),
    )
    wan_video_add_s2_v_embeds_101 = node(wf, 'WanVideoAddS2VEmbeds', '101',
        widget_0=201,
        widget_1=1,
        widget_2=0,
        widget_3=1,
        widget_4=False,
        audio_encoder_output=audio_encoder_encode_64.out(0),
        embeds=wan_video_empty_embeds_37.out(0),
        frame_window_size=primitive_node_71.out(0),
        ref_latent=wan_video_encode_72.out(0),
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
        scheduler='dpm++_sde',
        riflex_freq_index=0,
        denoise_strength=1,
        batched_cfg=False,
        context_options=wan_video_context_options_83.out(0),
        image_embeds=wan_video_add_s2_v_embeds_101.out(0),
        model=wan_video_set_block_swap_56.out(0),
        text_embeds=wan_video_text_encode_cached_67.out(0),
    )
    preview_any_2 = node(wf, 'PreviewAny', '69',
        source=wan_video_add_s2_v_embeds_101.out(1),
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
        vae=wan_video_vaeloader.out(0),
    )
    # ════ LATENT ════
    insert_latent_to_indexed_77 = node(wf, 'InsertLatentToIndexed', '77',
        widget_0=0,
        destination=wan_video_sampler_27.out(0),
        source=wan_video_encode_72.out(0),
    )
    get_image_size_and_count_70 = node(wf, 'GetImageSizeAndCount', '70',
        image=wan_video_decode_28.out(0),
    )
    vhs__split_images = node(wf, 'VHS_SplitImages', '80',
        images=get_image_size_and_count_70.out(0),
    )
    gimmvfiinterpolate = node(wf, 'GIMMVFI_interpolate', '96',
        widget_0=1,
        widget_1=3,
        widget_2=0,
        widget_3='fixed',
        widget_4=False,
        gimmvfi_model=download_and_load_gimmvfimodel.out(0),
        images=vhs__split_images.out(2),
    )
    vhs_videocombine_2 = node(wf, 'VHS_VideoCombine', '97',
        save_output=True,
        audio=vhs__load_audio.out(0),
        images=vhs__split_images.out(2),
    )
    vhs__select_every_nth_image = node(wf, 'VHS_SelectEveryNthImage', '102',
        images=gimmvfiinterpolate.out(0),
    )
    video_output_30 = node(wf, 'VHS_VideoCombine', '30',
        save_output=True,
        audio=vhs__load_audio.out(0),
        images=vhs__select_every_nth_image.out(0),
    )

    return finalize(
        wf,
        PUBLIC_INPUTS,
        READY_METADATA,
        output_node='',
        source_path=__file__,
    )

