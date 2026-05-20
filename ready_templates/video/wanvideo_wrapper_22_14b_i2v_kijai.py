# vibecomfy: manual
# Converted by tools/convert_ready_templates.py, then hand-edited for the
# production parity runtime path.
"""Image-to-video generation with Wan 2.2 I2V A14b High Fp 8 E4m3fn Scaled Kj.

Output: unknown.

Source:  workflow_corpus/custom_nodes/wanvideo_wrapper/kijai/wanvideo_2_2_I2V_A14B_example_WIP.json

Packs:   ComfyUI-KJNodes, ComfyUI-VideoHelperSuite, ComfyUI-WanVideoWrapper
"""
from __future__ import annotations

from vibecomfy.workflow import VibeWorkflow
from vibecomfy.templates import InputSpec, ModelAsset, ReadyMetadata, finalize, new_workflow, node
MODELS = {
    'wan2_2_i2v_a14b_high_fp8_e4m3fn_scaled_kj': ModelAsset(
        filename='Wan2_2-I2V-A14B-HIGH_fp8_e4m3fn_scaled_KJ.safetensors',
        url='https://huggingface.co/Kijai/WanVideo_comfy_fp8_scaled/resolve/main/I2V/Wan2_2-I2V-A14B-HIGH_fp8_e4m3fn_scaled_KJ.safetensors',
        subdir='',
    ),
    'wan2_2_i2v_a14b_low_fp8_e4m3fn_scaled_kj': ModelAsset(
        filename='Wan2_2-I2V-A14B-LOW_fp8_e4m3fn_scaled_KJ.safetensors',
        url='https://huggingface.co/Kijai/WanVideo_comfy_fp8_scaled/resolve/main/I2V/Wan2_2-I2V-A14B-LOW_fp8_e4m3fn_scaled_KJ.safetensors',
        subdir='',
    ),
    'wan2_1_vae_bf16': ModelAsset(
        filename='Wan2_1_VAE_bf16.safetensors',
        url='https://huggingface.co/Kijai/WanVideo_comfy/resolve/main/Wan2_1_VAE_bf16.safetensors',
        subdir='',
    ),
    'umt5_xxl_enc_bf16': ModelAsset(
        filename='umt5-xxl-enc-bf16.safetensors',
        url='https://huggingface.co/Kijai/WanVideo_comfy/resolve/main/umt5-xxl-enc-bf16.safetensors',
        subdir='',
    ),
    'umt5_xxl_fp16': ModelAsset(
        filename='umt5_xxl_fp16.safetensors',
        url='https://huggingface.co/Comfy-Org/Wan_2.1_ComfyUI_repackaged/resolve/main/split_files/text_encoders/umt5_xxl_fp16.safetensors',
        subdir='',
    ),
    'lightx2v_i2v_14b_480p_cfg_step_distill_ran': ModelAsset(
        filename='lightx2v_I2V_14B_480p_cfg_step_distill_rank64_bf16.safetensors',
        url='https://huggingface.co/Kijai/WanVideo_comfy/resolve/main/Lightx2v/lightx2v_I2V_14B_480p_cfg_step_distill_rank64_bf16.safetensors',
        subdir='',
    ),
}

PUBLIC_INPUTS = {}

READY_METADATA = ReadyMetadata.build(
    template_id='wanvideo_wrapper_22_14b_i2v_kijai',
    capability='image_to_video',
    inputs=PUBLIC_INPUTS,
    models=MODELS,
    output_prefix='',
    requirements={'custom_nodes': ['ComfyUI-KJNodes', 'ComfyUI-VideoHelperSuite', 'ComfyUI-WanVideoWrapper']},
    provenance={'approach': 'Kijai WanVideoWrapper Wan 2.2 A14B I2V high/low two-phase workflow with Lightx2v LoRA', 'source_workflow': 'workflow_corpus/custom_nodes/wanvideo_wrapper/kijai/wanvideo_2_2_I2V_A14B_example_WIP.json', 'source_role': 'materialized_kijai_reference_workflow', 'smoke_resolution': '832x480x81_frames'},
    coverage_tier='production_parity_candidate',
    runtime_note='Worker scratchpads patch image, prompt, seed, resolution, frame count, and force VHS output saving.',
    source_url='https://raw.githubusercontent.com/kijai/ComfyUI-WanVideoWrapper/main/example_workflows/wanvideo_2_2_I2V_A14B_example_WIP.json',
    vibecomfy_version='0.1.0',
    comfy_core={'version': '0.18.2', 'tested_at': '2026-05-20T09:19:32.302139+00:00', 'commit': 'f7b38d2eb97207cd834bcc3eb2e8b1d447b96c68', 'status': 'discovered'},
)

def build() -> VibeWorkflow:
    """Build the workflow (auto-generated)."""
    wf = new_workflow(READY_METADATA, source_path=__file__)

    # ════ TEXT CONDITIONING ════
    load_wan_video_t5_text_encoder_11 = node(wf, 'LoadWanVideoT5TextEncoder', '11',
        model_name=MODELS['umt5_xxl_enc_bf16'].filename,
        precision='bf16',
        load_device='offload_device',
        quantization='disabled',
    )
    # ════ LOADERS ════
    wan_video_vaeloader = node(wf, 'WanVideoVAELoader', '38',
        model_name='wanvideo\\Wan2_1_VAE_bf16.safetensors',
        precision='bf16',
    )
    # ════ SAMPLING ════
    wan_video_block_swap_39 = node(wf, 'WanVideoBlockSwap', '39',
        blocks_to_swap=20,
        offload_img_emb=False,
        offload_txt_emb=False,
        use_non_blocking=False,
        vace_blocks_to_swap=1,
    )
    text_encoder = node(wf, 'CLIPLoader', '48',
        clip_name=MODELS['umt5_xxl_fp16'].filename,
        type='wan',
        device='default',
    )
    wan_video_lora_select_56 = node(wf, 'WanVideoLoraSelect', '56',
        lora='WanVideo\\Lightx2v\\lightx2v_I2V_14B_480p_cfg_step_distill_rank64_bf16.safetensors',
        strength=3,
        low_mem_load=False,
        merge_loras=False,
    )
    input_image = node(wf, 'LoadImage', '67',
        image='oldman_upscaled.png',
    )
    param_int_91 = node(wf, 'INTConstant', '91',
        value=3,
    )
    param_steps = node(wf, 'INTConstant', '94',
        value=6,
    )
    wan_video_lora_select_2 = node(wf, 'WanVideoLoraSelect', '97',
        lora='WanVideo\\Lightx2v\\lightx2v_I2V_14B_480p_cfg_step_distill_rank64_bf16.safetensors',
        strength=1,
        low_mem_load=False,
        merge_loras=False,
    )
    wan_video_text_encode_16 = node(wf, 'WanVideoTextEncode', '16',
        positive_prompt='old man gets up and jumps into the lake',
        negative_prompt='色调艳丽，过曝，静态，细节模糊不清，字幕，风格，作品，画作，画面，静止，整体发灰，最差质量，低质量，JPEG压缩残留，丑陋的，残缺的，多余的手指，画得不好的手部，画得不好的脸部，畸形的，毁容的，形态畸形的肢体，手指融合，静止不动的画面，杂乱的背景，三条腿，背景人很多，倒着走',
        force_offload=True,
        use_disk_cache=False,
        device='gpu',
        t5=load_wan_video_t5_text_encoder_11.out(0),
    )
    wan_video_model_loader_22 = node(wf, 'WanVideoModelLoader', '22',
        model='WanVideo\\2_2\\Wan2_2-I2V-A14B-HIGH_fp8_e4m3fn_scaled_KJ.safetensors',
        base_precision='fp16',
        quantization='fp8_e4m3fn_scaled',
        load_device='offload_device',
        attention_mode='sdpa',
    )
    positive_prompt = node(wf, 'CLIPTextEncode', '49',
        text="high quality nature video featuring a red panda balancing on a bamboo stem while a bird lands on it's head, on the background there is a waterfall",
        clip=text_encoder.out('CLIP'),
    )
    negative_prompt = node(wf, 'CLIPTextEncode', '50',
        text='色调艳丽，过曝，静态，细节模糊不清，字幕，风格，作品，画作，画面，静止，整体发灰，最差质量，低质量，JPEG压缩残留，丑陋的，残缺的，多余的手指，画得不好的手部，画得不好的脸部，畸形的，毁容的，形态畸形的肢体，手指融合，静止不动的画面，杂乱的背景，三条腿，背景人很多，倒着走',
        clip=text_encoder.out('CLIP'),
    )
    # ════ IMAGE PREP ════
    resized_image = node(wf, 'ImageResizeKJv2', '68',
        width=720,
        height=720,
        upscale_method='lanczos',
        keep_proportion='crop',
        pad_color='0, 0, 0',
        crop_position='center',
        divisible_by=32,
        device='cpu',
        image=input_image.out('IMAGE'),
    )
    wan_video_model_loader_2 = node(wf, 'WanVideoModelLoader', '71',
        model='WanVideo\\2_2\\Wan2_2-I2V-A14B-LOW_fp8_e4m3fn_scaled_KJ.safetensors',
        base_precision='fp16',
        quantization='fp8_e4m3fn_scaled',
        load_device='offload_device',
        attention_mode='sdpa',
    )
    create_cfgschedule_float_list = node(wf, 'CreateCFGScheduleFloatList', '95',
        cfg_scale_start=2,
        cfg_scale_end=2,
        interpolation='linear',
        start_percent=0,
        end_percent=0.01,
        steps=param_steps.out('VALUE'),
    )
    wan_video_text_embed_bridge_46 = node(wf, 'WanVideoTextEmbedBridge', '46',
        negative=negative_prompt.out('CONDITIONING'),
        positive=positive_prompt.out('CONDITIONING'),
    )
    wan_video_image_to_video_encode_89 = node(wf, 'WanVideoImageToVideoEncode', '89',
        num_frames=81,
        noise_aug_strength=0,
        start_latent_strength=1,
        end_latent_strength=1,
        force_offload=True,
        tiled_vae=False,
        fun_or_fl2v_model=False,
        
        width=resized_image.out(1),
        height=resized_image.out(2),
        start_image=resized_image.out('IMAGE'),
        vae=wan_video_vaeloader.out(0),
    )
    wan_video_set_block_swap_92 = node(wf, 'WanVideoSetBlockSwap', '92',
        block_swap_args=wan_video_block_swap_39.out(0),
        model=wan_video_model_loader_22.out(0),
    )
    wan_video_set_block_swap_2 = node(wf, 'WanVideoSetBlockSwap', '93',
        block_swap_args=wan_video_block_swap_39.out(0),
        model=wan_video_model_loader_2.out(0),
    )
    wan_video_set_lo_r_as_79 = node(wf, 'WanVideoSetLoRAs', '79',
        lora=wan_video_lora_select_2.out(0),
        model=wan_video_set_block_swap_2.out(0),
    )
    wan_video_set_lo_r_as_2 = node(wf, 'WanVideoSetLoRAs', '80',
        lora=wan_video_lora_select_56.out(0),
        model=wan_video_set_block_swap_92.out(0),
    )
    wan_video_sampler_27 = node(wf, 'WanVideoSampler', '27',
        shift=8,
        seed=43,
        force_offload=True,
        scheduler='dpm++_sde',
        riflex_freq_index=0,
        denoise_strength=1,
        batched_cfg=False,
        rope_function='comfy',
        start_step=0,
        add_noise_to_samples='',
        
        
        steps=param_steps.out('VALUE'),
        cfg=create_cfgschedule_float_list.out(0),
        end_step=param_int_91.out('VALUE'),
        image_embeds=wan_video_image_to_video_encode_89.out(0),
        model=wan_video_set_lo_r_as_2.out(0),
        text_embeds=wan_video_text_encode_16.out(0),
    )
    wan_video_sampler_2 = node(wf, 'WanVideoSampler', '90',
        cfg=1,
        shift=8,
        seed=43,
        force_offload=True,
        scheduler='dpm++_sde',
        riflex_freq_index=0,
        denoise_strength=1,
        batched_cfg=False,
        rope_function='comfy',
        end_step=-1,
        add_noise_to_samples='',
        
        steps=param_steps.out('VALUE'),
        start_step=param_int_91.out('VALUE'),
        image_embeds=wan_video_image_to_video_encode_89.out(0),
        model=wan_video_set_lo_r_as_79.out(0),
        samples=wan_video_sampler_27.out(0),
        text_embeds=wan_video_text_encode_16.out(0),
    )
    # ════ DECODE ════
    wan_video_decode_28 = node(wf, 'WanVideoDecode', '28',
        enable_vae_tiling=False,
        tile_x=272,
        tile_y=272,
        tile_stride_x=144,
        tile_stride_y=128,
        normalization='default',
        samples=wan_video_sampler_2.out(0),
        vae=wan_video_vaeloader.out(0),
    )
    get_image_size_and_count_69 = node(wf, 'GetImageSizeAndCount', '69',
        image=wan_video_decode_28.out(0),
    )
    # ════ OUTPUT ════
    video_output = node(wf, 'VHS_VideoCombine', '60',
        crf=19,
        filename_prefix='WanVideo2_2_I2V',
        format='video/h264-mp4',
        frame_rate=16,
        loop_count=0,
        pingpong=False,
        pix_fmt='yuv420p',
        save_metadata=True,
        save_output=False,
        trim_to_audio=False,
        videopreview={'hidden': False, 'params': {'filename': 'WanVideo2_2_I2V_00006.mp4', 'format': 'video/h264-mp4', 'frame_rate': 16, 'fullpath': 'N:\\AI\\ComfyUI\\temp\\WanVideo2_2_I2V_00006.mp4', 'subfolder': '', 'type': 'temp', 'workflow': 'WanVideo2_2_I2V_00006.png'}, 'paused': False},
        images=get_image_size_and_count_69.out(0),
    )

    return finalize(
        wf,
        PUBLIC_INPUTS,
        READY_METADATA,
        output_node='',
        source_path=__file__,
    )

