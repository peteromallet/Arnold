# vibecomfy: generated — converted by tools/convert_ready_templates.py
# Edits will be overwritten on regeneration. Add a `# vibecomfy: manual`
# marker on the first line if hand-editing is required.
"""Fun Control Video with Umt 5 Xxl Fp 16 CLIP.

Output: unknown.

Source:  workflow_corpus/custom_nodes/wanvideo_wrapper/kijai/wan21_14b_fun_control.json

Packs:   ComfyUI-DepthAnythingV2, ComfyUI-KJNodes, ComfyUI-VideoHelperSuite, ComfyUI-WanVideoWrapper, rgthree-comfy
"""
from __future__ import annotations

from vibecomfy.workflow import VibeWorkflow
from vibecomfy.templates import InputSpec, ModelAsset, ReadyMetadata, finalize, new_workflow, node

def _getnode(wf, _id, **overrides):
    kwargs = dict(widget_0='VAE')
    kwargs.update(overrides)
    return node(wf, 'GetNode', _id, **kwargs)
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
    template_id='wanvideo_wrapper_21_14b_fun_control',
    capability='fun_control_video',
    inputs=PUBLIC_INPUTS,
    models=MODELS,
    output_prefix='',
    requirements={'custom_nodes': ['ComfyUI-DepthAnythingV2', 'ComfyUI-KJNodes', 'ComfyUI-VideoHelperSuite', 'ComfyUI-WanVideoWrapper', 'rgthree-comfy'], 'custom_node_refs': [{'slug': 'ComfyUI-DepthAnythingV2', 'source': 'git',
                       'commit': '553187872eeb1d52e50dc53209fa57e569609a72', 'url': 'https://github.com/kijai/ComfyUI-DepthAnythingV2.git'}, {'slug': 'ComfyUI-KJNodes', 'source': 'git', 'commit': 'b7646ad70a7daa7aeb919ca542274758d26ba2df', 'url': 'https://github.com/kijai/ComfyUI-KJNodes.git'}, {'slug': 'ComfyUI-VideoHelperSuite', 'source': 'git',
                       'commit': '4ee72c065db22c9d96c2427954dc69e7b908444b', 'url': 'https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite.git'}, {'slug': 'ComfyUI-WanVideoWrapper', 'source': 'git', 'commit': 'df8f3e49daaad117cf3090cc916c83f3d001494c', 'url': 'https://github.com/kijai/ComfyUI-WanVideoWrapper.git'}, {'slug': 'rgthree-comfy', 'source': 'git',
                       'commit': '738105af5fb14e96fbecaf406dc356e284797e8c', 'url': 'https://github.com/rgthree/rgthree-comfy.git'}]},
    provenance={'smoke_resolution': '256x256x5_frames', 'source_workflow': 'workflow_corpus/custom_nodes/wanvideo_wrapper/kijai/wan21_14b_fun_control.json', 'approach': 'WanVideoFun control workflow', 'source_role': 'materialized_ready_python_template'},
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
        model='WanVideo\\wan2.1_fun_control_1.3B_bf16.safetensors',
        base_precision='bf16',
        quantization='disabled',
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
    wan_video_vaeloader = node(wf, 'WanVideoVAELoader', '38',
        model_name='wanvideo\\Wan2_1_VAE_bf16.safetensors',
        precision='bf16',
    )
    wan_video_block_swap_39 = node(wf, 'WanVideoBlockSwap', '39',
        blocks_to_swap=10,
        offload_img_emb=False,
        offload_txt_emb=False,
        use_non_blocking=True,
        vace_blocks_to_swap=0,
    )
    wan_video_vrammanagement = node(wf, 'WanVideoVRAMManagement', '45',
        widget_0=1,
    )
    text_encoder = node(wf, 'CLIPLoader', '48',
        clip_name=MODELS['umt5_xxl_fp16_clip'].filename,
        type='wan',
        device='default',
    )
    wan_video_tea_cache_52 = node(wf, 'WanVideoTeaCache', '52',
        widget_0=0.08,
        widget_1=1,
        widget_2=-1,
        widget_3='offload_device',
        widget_4='true',
        widget_5='e',
    )
    input_image = node(wf, 'LoadImage', '58',
        image='pasted/image (758).png',
widget_2='',
    )
    clip_vision = node(wf, 'CLIPVisionLoader', '59',
        clip_name=MODELS['clip_vision_h_clip'].filename,
    )
    vhs__load_video = node(wf, 'VHS_LoadVideo', '71',
        video='wolf_interpolated.mp4',
    )
    # ════ CONTROL ════
    depth_model = node(wf, 'DownloadAndLoadDepthAnythingV2Model', '73',
        widget_0='depth_anything_v2_vitl_fp16.safetensors',
    )
    reroute_79 = node(wf, 'Reroute', '79')
    reroute_2 = node(wf, 'Reroute', '80')
    get_node_84 = _getnode(wf, '84', )
    getnode_2 = _getnode(wf, '85', )
    getnode_3 = _getnode(wf, '86', )
    getnode_4 = node(wf, 'GetNode', '89',
        widget_0='ControlSignal',
    )
    wan_video_experimental_args_90 = node(wf, 'WanVideoExperimentalArgs', '90',
        widget_0='',
        widget_1=True,
        widget_2=False,
        widget_3=0,
    )
    wan_video_text_encode_16 = node(wf, 'WanVideoTextEncode', '16',
        positive_prompt="high quality nature video of a red fox in an autumnal forest, there's a waterfall in the background",
        negative_prompt='色调艳丽，过曝，静态，细节模糊不清，字幕，风格，作品，画作，画面，静止，整体发灰，最差质量，低质量，JPEG压缩残留，丑陋的，残缺的，多余的手指，画得不好的手部，画得不好的脸部，畸形的，毁容的，形态畸形的肢体，手指融合，静止不动的画面，杂乱的背景，三条腿，背景人很多，倒着走',
        force_offload=True,
        model_to_offload=wan_video_model_loader_22.out(0),
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
    # ════ IMAGE PREP ════
    image_resize_k_j_1 = node(wf, 'ImageResizeKJ', '75',
        widget_0=640,
        widget_1=640,
        widget_2='lanczos',
        widget_3=False,
        widget_4=16,
        widget_5=0,
        widget_6=0,
        widget_7='disabled',
        image=vhs__load_video.out(0),
    )
    set_node_83 = node(wf, 'SetNode', '83',
        widget_0='VAE',
        WANVAE=wan_video_vaeloader.out(0),
    )
    wan_video_sampler_27 = node(wf, 'WanVideoSampler', '27',
        steps=1,
        cfg=6,
        rope_function='comfy',
        shift=5,
        seed=42,
force_offload=True,
        scheduler='unipc',
        riflex_freq_index=0,
        denoise_strength=1,
        batched_cfg='',
        cache_args=wan_video_tea_cache_52.out(0),
        experimental_args=wan_video_experimental_args_90.out(0),
        image_embeds=reroute_79.out(0),
        model=wan_video_model_loader_22.out(0),
        text_embeds=wan_video_text_encode_16.out(0),
    )
    wan_video_text_embed_bridge_46 = node(wf, 'WanVideoTextEmbedBridge', '46',
        negative=negative_prompt.out('CONDITIONING'),
        positive=positive_prompt.out('CONDITIONING'),
    )
    depth_map = node(wf, 'DepthAnything_V2', '72',
        da_model=depth_model.out('DA_V2_MODEL'),
        images=image_resize_k_j_1.out(0),
    )
    # ════ DECODE ════
    wan_video_decode_28 = node(wf, 'WanVideoDecode', '28',
        enable_vae_tiling=False,
        tile_x=272,
        tile_y=272,
        tile_stride_x=144,
        tile_stride_y=128,
        samples=wan_video_sampler_27.out(0),
        vae=getnode_3.out(0),
    )
    get_image_size_and_count_76 = node(wf, 'GetImageSizeAndCount', '76',
        image=depth_map.out('IMAGE'),
    )
    setnode_2 = node(wf, 'SetNode', '88',
        widget_0='ControlSignal',
        IMAGE=depth_map.out('IMAGE'),
    )
    image_resize_k_j_66 = node(wf, 'ImageResizeKJ', '66',
        widget_0=624,
        widget_1=624,
        widget_2='lanczos',
        widget_3=False,
        widget_4=16,
        widget_5=0,
        widget_6=0,
        widget_7='center',
        height=get_image_size_and_count_76.out(2),
        image=input_image.out('IMAGE'),
        width=get_image_size_and_count_76.out(1),
    )
    wan_video_encode_77 = node(wf, 'WanVideoEncode', '77',
        widget_0=False,
        widget_1=272,
        widget_2=272,
        widget_3=144,
        widget_4=128,
        widget_5=0,
        widget_6=1,
        image=get_image_size_and_count_76.out(0),
        vae=get_node_84.out(0),
    )
    # ════ OUTPUT ════
    vhs_videocombine_2 = node(wf, 'VHS_VideoCombine', '82',
        save_output=True,
        images=setnode_2.out(0),
    )
    image_concat_multi_87 = node(wf, 'ImageConcatMulti', '87',
        inputcount=2,
        direction='right',
        match_image_size=False,
        unused_3=None,
        image_1=getnode_4.out(0),
        image_2=wan_video_decode_28.out(0),
    )
    video_output_30 = node(wf, 'VHS_VideoCombine', '30',
        save_output=True,
        images=image_concat_multi_87.out(0),
    )
    wan_video_clip_vision_encode_65 = node(wf, 'WanVideoClipVisionEncode', '65',
        strength_1=1,
        strength_2=1,
        crop='center',
        combine_embeds='average',
        force_offload=True,
        tiles=0,
        ratio=0.2,
        clip_vision=clip_vision.out('CLIP_VISION'),
        image_1=image_resize_k_j_66.out(0),
    )
    wan_video_control_embeds_78 = node(wf, 'WanVideoControlEmbeds', '78',
        widget_0=0,
        widget_1=1,
        latents=wan_video_encode_77.out(0),
    )
    wan_video_image_to_video_encode_63 = node(wf, 'WanVideoImageToVideoEncode', '63',
        
        
        noise_aug_strength=0.03,
        start_latent_strength=1,
        end_latent_strength=1,
        force_offload=True,
        tiled_vae=True,
        clip_embeds=wan_video_clip_vision_encode_65.out(0),
        control_embeds=wan_video_control_embeds_78.out(0),
        height=image_resize_k_j_66.out(2),
        num_frames=get_image_size_and_count_76.out(3),
        start_image=image_resize_k_j_66.out(0),
        vae=getnode_2.out(0),
        width=image_resize_k_j_66.out(1),
    )
    wan_video_empty_embeds_69 = node(wf, 'WanVideoEmptyEmbeds', '69',
        widget_0=256,
        widget_1=256,
        widget_2=5,
        control_embeds=wan_video_control_embeds_78.out(0),
        height=get_image_size_and_count_76.out(2),
        num_frames=get_image_size_and_count_76.out(3),
        width=get_image_size_and_count_76.out(1),
    )

    return finalize(
        wf,
        PUBLIC_INPUTS,
        READY_METADATA,
        output_node='',
        source_path=__file__,
    )

