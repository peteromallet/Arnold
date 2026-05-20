# vibecomfy: generated — converted by tools/convert_ready_templates.py
# Edits will be overwritten on regeneration. Add a `# vibecomfy: manual`
# marker on the first line if hand-editing is required.
"""Audio Image To Video.

Output: unknown.

Source:  workflow_corpus/custom_nodes/wanvideo_wrapper/kijai/wan22_5b_ovi_audio_i2v.json

Packs:   ComfyUI-KJNodes, ComfyUI-VideoHelperSuite, ComfyUI-WanVideoWrapper
"""
from __future__ import annotations

from vibecomfy.workflow import VibeWorkflow
from vibecomfy.templates import InputSpec, ModelAsset, ReadyMetadata, finalize, new_workflow, node
MODELS = {}

PUBLIC_INPUTS = {}

READY_METADATA = ReadyMetadata.build(
    template_id='wanvideo_wrapper_22_5b_ovi_audio_i2v',
    capability='audio_image_to_video',
    inputs=PUBLIC_INPUTS,
    models=MODELS,
    output_prefix='',
    requirements={'custom_nodes': ['ComfyUI-KJNodes', 'ComfyUI-VideoHelperSuite', 'ComfyUI-WanVideoWrapper'], 'custom_node_refs': [{'slug': 'ComfyUI-KJNodes', 'source': 'git', 'commit': 'b7646ad70a7daa7aeb919ca542274758d26ba2df', 'url': 'https://github.com/kijai/ComfyUI-KJNodes.git'}, {'slug': 'ComfyUI-VideoHelperSuite', 'source': 'git',
                       'commit': '4ee72c065db22c9d96c2427954dc69e7b908444b', 'url': 'https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite.git'}, {'slug': 'ComfyUI-WanVideoWrapper', 'source': 'git', 'commit': 'df8f3e49daaad117cf3090cc916c83f3d001494c', 'url': 'https://github.com/kijai/ComfyUI-WanVideoWrapper.git'}]},
    provenance={'source_role': 'materialized_ready_python_template', 'smoke_resolution': '256x256x5_frames', 'source_workflow': 'workflow_corpus/custom_nodes/wanvideo_wrapper/kijai/wan22_5b_ovi_audio_i2v.json', 'approach': 'Ovi image-to-video with audio'},
    coverage_tier='supplemental',
    vibecomfy_version='0.1.0',
    comfy_core={'version': '0.18.2', 'tested_at': '2026-05-20T09:19:32.302139+00:00', 'commit': 'f7b38d2eb97207cd834bcc3eb2e8b1d447b96c68', 'status': 'discovered'},
)

def build() -> VibeWorkflow:
    """Build the workflow (auto-generated)."""
    wf = new_workflow(READY_METADATA, source_path=__file__)

    # ════ SAMPLING ════
    wan_video_extra_model_select_78 = node(wf, 'WanVideoExtraModelSelect', '78',
        widget_0='WanVideo/Ovi/Wan_2_1_Ovi_audio_model_bf16.safetensors',
    )
    wan_video_block_swap_83 = node(wf, 'WanVideoBlockSwap', '83',
        blocks_to_swap=15,
        offload_img_emb=False,
        offload_txt_emb=False,
        use_non_blocking=True,
        vace_blocks_to_swap=0,
        prefetch_blocks=1,
        block_swap_debug=False,
    )
    # ════ TEXT CONDITIONING ════
    wan_video_text_encode_cached_85 = node(wf, 'WanVideoTextEncodeCached', '85',
        model_name='umt5-xxl-enc-bf16.safetensors',
        precision='bf16',
        positive_prompt='A tired old man is very sarcastically saying: <S>Oh great, they are making me talk now too.<E>. <AUDCAP>Clear older male voices speaking dialogue, subtle outdoor ambience.<ENDAUDCAP>',
        negative_prompt='色调艳丽，过曝，静态，细节模糊不清，字幕，风格，作品，画作，画面，静止，整体发灰，最差质量，低质量，JPEG压缩残留，丑陋的，残缺的，多余的手指，画得不好的手部，画得不好的脸部，畸形的，毁容的，形态畸形的肢体，手指融合，静止不动的画面，杂乱的背景，三条腿，背景人很多，倒着走',
        quantization='disabled',
        use_disk_cache=False,
        device='gpu',
    )
    # ════ LOADERS ════
    wan_video_vaeloader = node(wf, 'WanVideoVAELoader', '87',
        model_name='Wan2_2_VAE_bf16.safetensors',
        precision='bf16',
    )
    ovi_mmaudio_vaeloader = node(wf, 'OviMMAudioVAELoader', '89',
        widget_0='mmaudio_vae_16k_fp32.safetensors',
        widget_1='mmaudio_vocoder_bigvgan_best_netG_fp32.safetensors',
        widget_2='fp32',
    )
    wan_video_torch_compile_settings_91 = node(wf, 'WanVideoTorchCompileSettings', '91',
        backend='inductor',
        fullgraph=False,
        mode='default',
        dynamic=False,
        dynamo_cache_size_limit=64,
        compile_transformer_blocks_only=True,
        dynamo_recompile_limit=128,
    )
    wan_video_slg = node(wf, 'WanVideoSLG', '93',
        widget_0='11',
        widget_1=0,
        widget_2=1,
    )
    wan_video_text_encode_cached_2 = node(wf, 'WanVideoTextEncodeCached', '96',
        model_name='umt5-xxl-enc-bf16.safetensors',
        precision='bf16',
        positive_prompt='',
        negative_prompt='robotic, muffled, echo, distorted',
        quantization='disabled',
        use_disk_cache=True,
        device='gpu',
    )
    input_image = node(wf, 'LoadImage', '109',
        image='oldman_upscaled.png',
)
    wan_video_easy_cache_118 = node(wf, 'WanVideoEasyCache', '118',
        widget_0=0.015,
        widget_1=10,
        widget_2=-1,
        widget_3='offload_device',
    )
    # ════ LATENT ════
    wan_video_empty_m_m_audio_latents_125 = node(wf, 'WanVideoEmptyMMAudioLatents', '125',
        widget_0=157,
    )
    wan_video_model_loader_12 = node(wf, 'WanVideoModelLoader', '12',
        model='WanVideo/Ovi/Wan_2_1_Ovi_video_model_bf16.safetensors',
        base_precision='bf16',
        quantization='disabled',
        load_device='offload_device',
        attention_mode='sdpa',
        rms_norm_function='default',
        compile_args=wan_video_torch_compile_settings_91.out(0),
        extra_model=wan_video_extra_model_select_78.out(0),
    )
    wan_video_ovi_cfg = node(wf, 'WanVideoOviCFG', '94',
        widget_0=3,
        original_text_embeds=wan_video_text_encode_cached_85.out(0),
        ovi_negative_text_embeds=wan_video_text_encode_cached_2.out(1),
    )
    # ════ IMAGE PREP ════
    resized_image = node(wf, 'ImageResizeKJv2', '110',
        height=256,
        
        upscale_method='lanczos',
        keep_proportion='crop',
        pad_color='0, 0, 0',
        crop_position='center',
        divisible_by=32,
        device='cpu',
        width=256,
        image=input_image.out('IMAGE'),
    )
    wan_video_set_block_swap_84 = node(wf, 'WanVideoSetBlockSwap', '84',
        block_swap_args=wan_video_block_swap_83.out(0),
        model=wan_video_model_loader_12.out(0),
    )
    wan_video_encode_111 = node(wf, 'WanVideoEncode', '111',
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
    wan_video_empty_embeds_81 = node(wf, 'WanVideoEmptyEmbeds', '81',
        num_frames=5,
        widget_0=256,
        widget_1=256,
        widget_2=5,
        extra_latents=wan_video_encode_111.out(0),
        height=resized_image.out(2),
        width=resized_image.out(1),
    )
    wan_video_sampler_80 = node(wf, 'WanVideoSampler', '80',
        steps=1,
        cfg=4,
        rope_function='default',
        start_step=0,
        end_step=-1,
        add_noise_to_samples=False,
        shift=5,
        seed=42,
force_offload=True,
        scheduler='unipc',
        riflex_freq_index=0,
        denoise_strength=1,
        batched_cfg=False,
        cache_args=wan_video_easy_cache_118.out(0),
        image_embeds=wan_video_empty_embeds_81.out(0),
        model=wan_video_set_block_swap_84.out(0),
        samples=wan_video_empty_m_m_audio_latents_125.out(0),
        slg_args=wan_video_slg.out(0),
        text_embeds=wan_video_ovi_cfg.out(0),
    )
    # ════ DECODE ════
    wan_video_decode_86 = node(wf, 'WanVideoDecode', '86',
        enable_vae_tiling=False,
        tile_x=272,
        tile_y=272,
        tile_stride_x=144,
        tile_stride_y=128,
        normalization='default',
        samples=wan_video_sampler_80.out(0),
        vae=wan_video_vaeloader.out(0),
    )
    wan_video_decode_ovi_audio_90 = node(wf, 'WanVideoDecodeOviAudio', '90',
        mmaudio_vae=ovi_mmaudio_vaeloader.out(0),
        samples=wan_video_sampler_80.out(0),
    )
    # ════ OUTPUT ════
    video_output = node(wf, 'VHS_VideoCombine', '88',
        save_output=True,
        audio=wan_video_decode_ovi_audio_90.out(0),
        images=wan_video_decode_86.out(0),
    )
    preview_audio_108 = node(wf, 'PreviewAudio', '108',
        audio=wan_video_decode_ovi_audio_90.out(0),
    )

    return finalize(
        wf,
        PUBLIC_INPUTS,
        READY_METADATA,
        output_node='',
        source_path=__file__,
    )

