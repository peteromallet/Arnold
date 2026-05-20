# vibecomfy: generated — converted by tools/convert_ready_templates.py
# Edits will be overwritten on regeneration. Add a `# vibecomfy: manual`
# marker on the first line if hand-editing is required.
"""Text To Video with Umt 5 Xxl Fp 16 CLIP.

Output: unknown.

Source:  workflow_corpus/custom_nodes/wanvideo_wrapper/kijai/wan21_14b_t2v.json

Packs:   ComfyUI-VideoHelperSuite, ComfyUI-WanVideoWrapper
"""
from __future__ import annotations

from vibecomfy.workflow import VibeWorkflow
from vibecomfy.templates import InputSpec, ModelAsset, ReadyMetadata, finalize, new_workflow, node
MODELS = {
    'umt5_xxl_fp16_clip': ModelAsset(
        filename='umt5_xxl_fp16.safetensors',
        url='',
        subdir='text_encoders',
    ),
}

PUBLIC_INPUTS = {}

READY_METADATA = ReadyMetadata.build(
    template_id='wanvideo_wrapper_21_14b_t2v',
    capability='text_to_video',
    inputs=PUBLIC_INPUTS,
    models=MODELS,
    output_prefix='',
    requirements={'custom_nodes': ['ComfyUI-VideoHelperSuite', 'ComfyUI-WanVideoWrapper'], 'custom_node_refs': [{'slug': 'ComfyUI-KJNodes', 'source': 'git', 'commit': 'b7646ad70a7daa7aeb919ca542274758d26ba2df', 'url': 'https://github.com/kijai/ComfyUI-KJNodes.git'}, {'slug': 'ComfyUI-VideoHelperSuite', 'source': 'git',
                       'commit': '4ee72c065db22c9d96c2427954dc69e7b908444b', 'url': 'https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite.git'}, {'slug': 'ComfyUI-WanVideoWrapper', 'source': 'git', 'commit': 'df8f3e49daaad117cf3090cc916c83f3d001494c', 'url': 'https://github.com/kijai/ComfyUI-WanVideoWrapper.git'}]},
    provenance={'smoke_resolution': '256x256x5_frames', 'source_role': 'materialized_ready_python_template', 'source_workflow': 'workflow_corpus/custom_nodes/wanvideo_wrapper/kijai/wan21_14b_t2v.json', 'approach': 'WanVideoWrapper 2.1 14B text-to-video'},
    coverage_tier='supplemental',
    vibecomfy_version='0.1.0',
    comfy_core={'version': '0.18.2', 'tested_at': '2026-05-20T09:19:32.302139+00:00', 'commit': 'f7b38d2eb97207cd834bcc3eb2e8b1d447b96c68', 'status': 'discovered'},
)

def build() -> VibeWorkflow:
    """Build the workflow (auto-generated)."""
    wf = new_workflow(READY_METADATA, source_path=__file__)

    # ════ TEXT CONDITIONING ════
    load_wan_video_t5_text_encoder_11 = node(wf, 'LoadWanVideoT5TextEncoder', '11',
        model_name='umt5-xxl-enc-bf16.safetensors',
        precision='bf16',
        load_device='offload_device',
        quantization='disabled',
    )
    # ════ LOADERS ════
    wan_video_model_loader_22 = node(wf, 'WanVideoModelLoader', '22',
        model='WanVideo\\fp8_scaled_kj\\T2V\\Wan2_1-T2V-14B_fp8_e4m3fn_scaled_KJ.safetensors',
        base_precision='fp16',
        quantization='fp8_e4m3fn_scaled',
        load_device='offload_device',
        attention_mode='sdpa',
    )
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
    wan_video_empty_embeds_37 = node(wf, 'WanVideoEmptyEmbeds', '37',
        height=256,
        num_frames=5,
        widget_0=256,
        widget_1=256,
        widget_2=5,
        width=256,
    )
    wan_video_vaeloader = node(wf, 'WanVideoVAELoader', '38',
        model_name='wanvideo\\Wan2_1_VAE_bf16.safetensors',
        precision='bf16',
    )
    wan_video_block_swap_39 = node(wf, 'WanVideoBlockSwap', '39',
        blocks_to_swap=20,
        offload_img_emb=False,
        offload_txt_emb=False,
        use_non_blocking=False,
        vace_blocks_to_swap=0,
    )
    text_encoder = node(wf, 'CLIPLoader', '48',
        clip_name=MODELS['umt5_xxl_fp16_clip'].filename,
        type='wan',
        device='default',
    )
    wan_video_enhance_a_video_55 = node(wf, 'WanVideoEnhanceAVideo', '55',
        widget_0=2,
        widget_1=0,
        widget_2=1,
    )
    wan_video_lora_select_multi_60 = node(wf, 'WanVideoLoraSelectMulti', '60',
        lora_0='WanVideo\\Lightx2v\\lightx2v_T2V_14B_cfg_step_distill_v2_lora_rank64_bf16.safetensors',
        strength_0=1,
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
    wan_video_text_encode_16 = node(wf, 'WanVideoTextEncode', '16',
        positive_prompt="high quality nature video featuring a red panda balancing on a bamboo stem while a bird lands on it's head, on the background there is a waterfall",
        negative_prompt='色调艳丽，过曝，静态，细节模糊不清，字幕，风格，作品，画作，画面，静止，整体发灰，最差质量，低质量，JPEG压缩残留，丑陋的，残缺的，多余的手指，画得不好的手部，画得不好的脸部，畸形的，毁容的，形态畸形的肢体，手指融合，静止不动的画面，杂乱的背景，三条腿，背景人很多，倒着走',
        force_offload=True,
        use_disk_cache=False,
        device='gpu',
        t5=load_wan_video_t5_text_encoder_11.out(0),
    )
    positive_prompt = node(wf, 'CLIPTextEncode', '49',
        text="high quality nature video featuring a red panda balancing on a bamboo stem while a bird lands on it's head, on the background there is a waterfall",
        clip=text_encoder.out('CLIP'),
    )
    negative_prompt = node(wf, 'CLIPTextEncode', '50',
        text='色调艳丽，过曝，静态，细节模糊不清，字幕，风格，作品，画作，画面，静止，整体发灰，最差质量，低质量，JPEG压缩残留，丑陋的，残缺的，多余的手指，画得不好的手部，画得不好的脸部，畸形的，毁容的，形态畸形的肢体，手指融合，静止不动的画面，杂乱的背景，三条腿，背景人很多，倒着走',
        clip=text_encoder.out('CLIP'),
    )
    wan_video_set_lo_r_as_58 = node(wf, 'WanVideoSetLoRAs', '58',
        lora=wan_video_lora_select_multi_60.out(0),
        model=wan_video_model_loader_22.out(0),
    )
    wan_video_text_embed_bridge_46 = node(wf, 'WanVideoTextEmbedBridge', '46',
        negative=negative_prompt.out('CONDITIONING'),
        positive=positive_prompt.out('CONDITIONING'),
    )
    wan_video_set_block_swap_56 = node(wf, 'WanVideoSetBlockSwap', '56',
        block_swap_args=wan_video_block_swap_39.out(0),
        model=wan_video_set_lo_r_as_58.out(0),
    )
    wan_video_sampler_27 = node(wf, 'WanVideoSampler', '27',
        steps=1,
        cfg=1,
        rope_function='comfy',
        start_step=0,
        end_step=-1,
        add_noise_to_samples=False,
        widget_14='',
        shift=5,
        seed=42,
force_offload=True,
        scheduler='dpm++_sde',
        riflex_freq_index=0,
        denoise_strength=1,
        batched_cfg=False,
        feta_args=wan_video_enhance_a_video_55.out(0),
        image_embeds=wan_video_empty_embeds_37.out(0),
        model=wan_video_set_block_swap_56.out(0),
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
        samples=wan_video_sampler_27.out(0),
        vae=wan_video_vaeloader.out(0),
    )
    # ════ OUTPUT ════
    video_output = node(wf, 'VHS_VideoCombine', '30',
        save_output=True,
        images=wan_video_decode_28.out(0),
    )

    return finalize(
        wf,
        PUBLIC_INPUTS,
        READY_METADATA,
        output_node='',
        source_path=__file__,
    )

