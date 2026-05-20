# vibecomfy: generated — converted by tools/convert_ready_templates.py
# Edits will be overwritten on regeneration. Add a `# vibecomfy: manual`
# marker on the first line if hand-editing is required.
"""First Last Frame Video with Umt 5 Xxl Fp 16 CLIP.

Output: unknown.

Source:  workflow_corpus/custom_nodes/wanvideo_wrapper/kijai/wan21_14b_flf2v.json

Packs:   ComfyUI-KJNodes, ComfyUI-VideoHelperSuite, ComfyUI-WanVideoWrapper, rgthree-comfy
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
    'clip_vision_h_clip': ModelAsset(
        filename='clip_vision_h.safetensors',
        url='',
        subdir='text_encoders',
    ),
}

PUBLIC_INPUTS = {}

READY_METADATA = ReadyMetadata.build(
    template_id='wanvideo_wrapper_21_14b_flf2v',
    capability='first_last_frame_video',
    inputs=PUBLIC_INPUTS,
    models=MODELS,
    output_prefix='',
    requirements={'custom_nodes': ['ComfyUI-KJNodes', 'ComfyUI-VideoHelperSuite', 'ComfyUI-WanVideoWrapper', 'rgthree-comfy'], 'custom_node_refs': [{'slug': 'ComfyUI-KJNodes', 'source': 'git', 'commit': 'b7646ad70a7daa7aeb919ca542274758d26ba2df', 'url': 'https://github.com/kijai/ComfyUI-KJNodes.git'}, {'slug': 'ComfyUI-VideoHelperSuite', 'source': 'git',
                       'commit': '4ee72c065db22c9d96c2427954dc69e7b908444b', 'url': 'https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite.git'}, {'slug': 'ComfyUI-WanVideoWrapper', 'source': 'git', 'commit': 'df8f3e49daaad117cf3090cc916c83f3d001494c', 'url': 'https://github.com/kijai/ComfyUI-WanVideoWrapper.git'}, {'slug': 'rgthree-comfy', 'source': 'git',
                       'commit': '738105af5fb14e96fbecaf406dc356e284797e8c', 'url': 'https://github.com/rgthree/rgthree-comfy.git'}]},
    provenance={'source_workflow': 'workflow_corpus/custom_nodes/wanvideo_wrapper/kijai/wan21_14b_flf2v.json', 'smoke_resolution': '256x256x5_frames', 'source_role': 'materialized_ready_python_template', 'approach': 'WanVideoWrapper first/last-frame video'},
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
        model_name='wanvideo\\Wan2_1_VAE_bf16.safetensors',
        precision='bf16',
    )
    wan_video_block_swap_39 = node(wf, 'WanVideoBlockSwap', '39',
        blocks_to_swap=20,
        offload_img_emb=False,
        offload_txt_emb=False,
        use_non_blocking=True,
        vace_blocks_to_swap=0,
        prefetch_blocks=0,
        block_swap_debug=False,
    )
    text_encoder = node(wf, 'CLIPLoader', '48',
        clip_name=MODELS['umt5_xxl_fp16_clip'].filename,
        type='wan',
        device='default',
    )
    load_wan_video_clip_text_encoder_56 = node(wf, 'LoadWanVideoClipTextEncoder', '56',
        widget_0='open-clip-xlm-roberta-large-vit-huge-14_visual_fp16.safetensors',
        widget_1='fp16',
        widget_2='offload_device',
    )
    input_image_58 = node(wf, 'LoadImage', '58',
        image='pasted/image (853).png',
)
    clip_vision = node(wf, 'CLIPVisionLoader', '59',
        clip_name=MODELS['clip_vision_h_clip'].filename,
    )
    input_image_2 = node(wf, 'LoadImage', '63',
        image='pasted/image (852).png',
)
    get_node_93 = node(wf, 'GetNode', '93',
        widget_0='start_image',
    )
    getnode_2 = node(wf, 'GetNode', '94',
        widget_0='end_image',
    )
    wan_video_lora_select_106 = node(wf, 'WanVideoLoraSelect', '106',
        lora='Wan21_T2V_14B_lightx2v_cfg_step_distill_lora_rank32.safetensors',
        strength=1.2,
        low_mem_load=False,
        merge_loras=True,
    )
    wan_video_model_loader_22 = node(wf, 'WanVideoModelLoader', '22',
        model='WanVideo\\Wan2_1-FLF2V-14B-720P_fp8_e4m3fn.safetensors',
        base_precision='fp16',
        quantization='fp8_e4m3fn',
        load_device='offload_device',
        attention_mode='sdpa',
        block_swap_args=wan_video_block_swap_39.out(0),
        compile_args=wan_video_torch_compile_settings_35.out(0),
        lora=wan_video_lora_select_106.out(0),
    )
    positive_prompt = node(wf, 'CLIPTextEncode', '49',
        text='CG动画风格，一只蓝色的小鸟从地面起飞，煽动翅膀。小鸟羽毛细腻，胸前有独特的花纹，背景是蓝天白云，阳光明媚。镜跟随小鸟向上移动，展现出小鸟飞翔的姿态和天空的广阔。近景，仰视视角',
        clip=text_encoder.out('CLIP'),
    )
    negative_prompt = node(wf, 'CLIPTextEncode', '50',
        text='色调艳丽，过曝，静态，细节模糊不清，字幕，风格，作品，画作，画面，静止，整体发灰，最差质量，低质量，JPEG压缩残留，丑陋的，残缺的，多余的手指，画得不好的手部，画得不好的脸部，畸形的，毁容的，形态畸形的肢体，手指融合，静止不动的画面，杂乱的背景，三条腿，背景人很多，倒着走',
        clip=text_encoder.out('CLIP'),
    )
    add_label_95 = node(wf, 'AddLabel', '95',
        widget_0=10,
        widget_1=2,
        widget_2=48,
        widget_3=32,
        widget_4='white',
        widget_5='black',
        widget_6='FreeMono.ttf',
        widget_7='start_frame',
        widget_8='up',
        image=get_node_93.out(0),
    )
    add_label_2 = node(wf, 'AddLabel', '96',
        widget_0=10,
        widget_1=2,
        widget_2=48,
        widget_3=32,
        widget_4='white',
        widget_5='black',
        widget_6='FreeMono.ttf',
        widget_7='end_frame',
        widget_8='up',
        image=getnode_2.out(0),
    )
    # ════ IMAGE PREP ════
    resized_image_107 = node(wf, 'ImageResizeKJv2', '107',
        height=256,
        
        upscale_method='lanczos',
        keep_proportion='crop',
        pad_color='0, 0, 0',
        crop_position='center',
        divisible_by=16,
        device='cpu',
width=256,
        image=input_image_2.out('IMAGE'),
    )
    wan_video_text_encode_16 = node(wf, 'WanVideoTextEncode', '16',
        positive_prompt='CG动画风格，一只蓝色的小鸟从地面起飞，煽动翅膀。小鸟羽毛细腻，胸前有独特的花纹，背景是蓝天白云，阳光明媚。镜跟随小鸟向上移动，展现出小鸟飞翔的姿态和天空的广阔。近景，仰视视角',
        negative_prompt='色调艳丽，过曝，静态，细节模糊不清，字幕，风格，作品，画作，画面，静止，整体发灰，最差质量，低质量，JPEG压缩残留，丑陋的，残缺的，多余的手指，画得不好的手部，画得不好的脸部，畸形的，毁容的，形态畸形的肢体，手指融合，静止不动的画面，杂乱的背景，三条腿，背景人很多，倒着走',
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
    image_concat_multi_70 = node(wf, 'ImageConcatMulti', '70',
        inputcount=2,
        direction='down',
        match_image_size=True,
        unused_3=None,
        image_1=add_label_95.out(0),
        image_2=add_label_2.out(0),
    )
    set_node_91 = node(wf, 'SetNode', '91',
        widget_0='start_image',
        IMAGE=resized_image_107.out('IMAGE'),
    )
    imageresizekjv2_2 = node(wf, 'ImageResizeKJv2', '108',
        
        upscale_method='lanczos',
        keep_proportion='crop',
        pad_color='0, 0, 0',
        crop_position='center',
        divisible_by=16,
        device='cpu',
height=resized_image_107.out(2),
        image=input_image_58.out('IMAGE'),
        width=resized_image_107.out(1),
    )
    setnode_2 = node(wf, 'SetNode', '92',
        widget_0='end_image',
        IMAGE=imageresizekjv2_2.out('IMAGE'),
    )
    wan_video_clip_vision_encode_88 = node(wf, 'WanVideoClipVisionEncode', '88',
        strength_1=1,
        strength_2=1,
        crop='center',
        combine_embeds='concat',
        force_offload=True,
        tiles=0,
        ratio=0.5,
        clip_vision=clip_vision.out('CLIP_VISION'),
        image_1=set_node_91.out(0),
        image_2=setnode_2.out(0),
    )
    wan_video_image_to_video_encode_89 = node(wf, 'WanVideoImageToVideoEncode', '89',
        num_frames=5,
        
        
        noise_aug_strength=0,
        start_latent_strength=1,
        end_latent_strength=True,
        force_offload=True,
        tiled_vae=True,
        fun_or_fl2v_model=False,
        clip_embeds=wan_video_clip_vision_encode_88.out(0),
        end_image=setnode_2.out(0),
        height=imageresizekjv2_2.out(2),
        start_image=set_node_91.out(0),
        vae=wan_video_vaeloader.out(0),
        width=imageresizekjv2_2.out(1),
    )
    wan_video_sampler_27 = node(wf, 'WanVideoSampler', '27',
        steps=1,
        cfg=1.0000000000000002,
        rope_function='comfy',
        start_step=0,
        end_step=-1,
        add_noise_to_samples=False,
        shift=5.000000000000001,
        seed=43,
force_offload=True,
        scheduler='dpm++_sde',
        riflex_freq_index=0,
        denoise_strength=1,
        batched_cfg='',
        image_embeds=wan_video_image_to_video_encode_89.out(0),
        model=wan_video_model_loader_22.out(0),
        text_embeds=wan_video_text_encode_16.out(0),
    )
    # ════ DECODE ════
    wan_video_decode_101 = node(wf, 'WanVideoDecode', '101',
        enable_vae_tiling=False,
        tile_x=272,
        tile_y=272,
        tile_stride_x=144,
        tile_stride_y=128,
        normalization='default',
        samples=wan_video_sampler_27.out(0),
        vae=wan_video_vaeloader.out(0),
    )
    get_image_size_and_count_68 = node(wf, 'GetImageSizeAndCount', '68',
        image=wan_video_decode_101.out(0),
    )
    empty_image_97 = node(wf, 'EmptyImage', '97',
        widget_0=8,
        widget_1=512,
        widget_2=1,
        widget_3=0,
        height=get_image_size_and_count_68.out(2),
    )
    image_concat_multi_2 = node(wf, 'ImageConcatMulti', '71',
        inputcount=3,
        direction='left',
        match_image_size=True,
        unused_3=None,
        image_1=get_image_size_and_count_68.out(0),
        image_2=empty_image_97.out(0),
        image_3=image_concat_multi_70.out(0),
    )
    # ════ OUTPUT ════
    video_output = node(wf, 'VHS_VideoCombine', '30',
        save_output=True,
        images=image_concat_multi_2.out(0),
    )

    return finalize(
        wf,
        PUBLIC_INPUTS,
        READY_METADATA,
        output_node='',
        source_path=__file__,
    )

