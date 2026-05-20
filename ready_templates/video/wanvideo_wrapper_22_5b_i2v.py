# vibecomfy: generated — converted by tools/convert_ready_templates.py
# Edits will be overwritten on regeneration. Add a `# vibecomfy: manual`
# marker on the first line if hand-editing is required.
"""Image-to-video generation with Umt 5 Xxl Fp 16 CLIP.

Output: unknown.

Source:  workflow_corpus/custom_nodes/wanvideo_wrapper/kijai/wan22_5b_i2v.json

Packs:   ComfyUI-KJNodes, ComfyUI-VideoHelperSuite, ComfyUI-WanVideoWrapper
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
    template_id='wanvideo_wrapper_22_5b_i2v',
    capability='image_to_video',
    inputs=PUBLIC_INPUTS,
    models=MODELS,
    output_prefix='',
    requirements={'custom_nodes': ['ComfyUI-KJNodes', 'ComfyUI-VideoHelperSuite', 'ComfyUI-WanVideoWrapper'], 'custom_node_refs': [{'slug': 'ComfyUI-KJNodes', 'source': 'git', 'commit': 'b7646ad70a7daa7aeb919ca542274758d26ba2df', 'url': 'https://github.com/kijai/ComfyUI-KJNodes.git'}, {'slug': 'ComfyUI-VideoHelperSuite', 'source': 'git',
                       'commit': '4ee72c065db22c9d96c2427954dc69e7b908444b', 'url': 'https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite.git'}, {'slug': 'ComfyUI-WanVideoWrapper', 'source': 'git', 'commit': 'df8f3e49daaad117cf3090cc916c83f3d001494c', 'url': 'https://github.com/kijai/ComfyUI-WanVideoWrapper.git'}]},
    provenance={'approach': 'WanVideoWrapper 2.2 5B image-to-video', 'source_role': 'materialized_ready_python_template', 'source_workflow': 'workflow_corpus/custom_nodes/wanvideo_wrapper/kijai/wan22_5b_i2v.json', 'smoke_resolution': '256x256x5_frames'},
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
        model_name='wanvideo\\Wan2_2_VAE_bf16.safetensors',
        precision='bf16',
    )
    text_encoder = node(wf, 'CLIPLoader', '48',
        clip_name=MODELS['umt5_xxl_fp16_clip'].filename,
        type='wan',
        device='default',
    )
    input_image = node(wf, 'LoadImage', '58',
        image='image (658).png',
)
    wan_video_experimental_args_90 = node(wf, 'WanVideoExperimentalArgs', '90',
        widget_0='',
        widget_1=True,
        widget_2=False,
        widget_3=0,
        widget_4=False,
        widget_5=1,
        widget_6=1.25,
        widget_7=20,
        widget_8=True,
    )
    wan_video_slg = node(wf, 'WanVideoSLG', '91',
        widget_0='7,8,9',
        widget_1=0.1,
        widget_2=0.7,
    )
    wan_video_easy_cache_94 = node(wf, 'WanVideoEasyCache', '94',
        widget_0=0.015,
        widget_1=10,
        widget_2=-1,
        widget_3='offload_device',
    )
    wan_video_model_loader_22 = node(wf, 'WanVideoModelLoader', '22',
        model='WanVideo\\2_2\\wan2.2_ti2v_5B_fp16.safetensors',
        base_precision='fp16',
        quantization='disabled',
        load_device='offload_device',
        attention_mode='sdpa',
        compile_args=wan_video_torch_compile_settings_35.out(0),
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
    resized_image = node(wf, 'ImageResizeKJv2', '71',
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
    wan_video_text_encode_16 = node(wf, 'WanVideoTextEncode', '16',
        positive_prompt='the woman starts to play a violin',
        negative_prompt='Bright tones, overexposed, static, blurred details, subtitles, style, works, paintings, images, static, overall gray, worst quality, low quality, JPEG compression residue, ugly, incomplete, extra fingers, poorly drawn hands, poorly drawn faces, deformed, disfigured, misshapen limbs, fused fingers, still picture, messy background, three legs, many people in the background, walking backwards"',
        force_offload=True,
        use_disk_cache=False,
        device='gpu',
        model_to_offload=wan_video_model_loader_22.out(0),
        t5=load_wan_video_t5_text_encoder_11.out(0),
    )
    wan_video_text_embed_bridge_46 = node(wf, 'WanVideoTextEmbedBridge', '46',
        negative=negative_prompt.out('CONDITIONING'),
        positive=positive_prompt.out('CONDITIONING'),
    )
    wan_video_encode_70 = node(wf, 'WanVideoEncode', '70',
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
    wan_video_empty_embeds_78 = node(wf, 'WanVideoEmptyEmbeds', '78',
        num_frames=5,
        widget_0=256,
        widget_1=256,
        widget_2=5,
        extra_latents=wan_video_encode_70.out(0),
        height=resized_image.out(2),
        width=resized_image.out(1),
    )
    wan_video_sampler_27 = node(wf, 'WanVideoSampler', '27',
        steps=1,
        cfg=5,
        rope_function='comfy',
        start_step=0,
        end_step=-1,
        add_noise_to_samples='',
        shift=8,
        seed=47,
force_offload=True,
        scheduler='flowmatch_pusa',
        riflex_freq_index=0,
        denoise_strength=1,
        batched_cfg='',
        cache_args=wan_video_easy_cache_94.out(0),
        experimental_args=wan_video_experimental_args_90.out(0),
        image_embeds=wan_video_empty_embeds_78.out(0),
        model=wan_video_model_loader_22.out(0),
        slg_args=wan_video_slg.out(0),
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
    video_output = node(wf, 'VHS_VideoCombine', '92',
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

