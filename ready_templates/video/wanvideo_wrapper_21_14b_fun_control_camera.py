# vibecomfy: generated — converted by tools/convert_ready_templates.py
# Edits will be overwritten on regeneration. Add a `# vibecomfy: manual`
# marker on the first line if hand-editing is required.
"""Camera Control Video with Umt 5 Xxl Fp 8 E4m3fn Scaled CLIP.

Output: unknown.

Source:  workflow_corpus/custom_nodes/wanvideo_wrapper/kijai/wan21_14b_fun_control_camera.json

Packs:   ComfyUI-KJNodes, ComfyUI-VideoHelperSuite, ComfyUI-WanVideoWrapper, rgthree-comfy
"""
from __future__ import annotations

from vibecomfy.workflow import VibeWorkflow
from vibecomfy.templates import InputSpec, ModelAsset, ReadyMetadata, finalize, new_workflow, node
MODELS = {
    'umt5_xxl_fp8_e4m3fn_scaled_clip': ModelAsset(
        filename='umt5_xxl_fp8_e4m3fn_scaled.safetensors',
        url='',
        subdir='text_encoders',
    ),
}

PUBLIC_INPUTS = {}

READY_METADATA = ReadyMetadata.build(
    template_id='wanvideo_wrapper_21_14b_fun_control_camera',
    capability='camera_control_video',
    inputs=PUBLIC_INPUTS,
    models=MODELS,
    output_prefix='',
    requirements={'custom_nodes': ['ComfyUI-KJNodes', 'ComfyUI-VideoHelperSuite', 'ComfyUI-WanVideoWrapper', 'rgthree-comfy'], 'custom_node_refs': [{'slug': 'ComfyUI-KJNodes', 'source': 'git', 'commit': 'b7646ad70a7daa7aeb919ca542274758d26ba2df', 'url': 'https://github.com/kijai/ComfyUI-KJNodes.git'}, {'slug': 'ComfyUI-VideoHelperSuite', 'source': 'git',
                       'commit': '4ee72c065db22c9d96c2427954dc69e7b908444b', 'url': 'https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite.git'}, {'slug': 'ComfyUI-WanVideoWrapper', 'source': 'git', 'commit': 'df8f3e49daaad117cf3090cc916c83f3d001494c', 'url': 'https://github.com/kijai/ComfyUI-WanVideoWrapper.git'}, {'slug': 'rgthree-comfy', 'source': 'git',
                       'commit': '738105af5fb14e96fbecaf406dc356e284797e8c', 'url': 'https://github.com/rgthree/rgthree-comfy.git'}]},
    provenance={'approach': 'WanVideoFun camera-control workflow', 'source_workflow': 'workflow_corpus/custom_nodes/wanvideo_wrapper/kijai/wan21_14b_fun_control_camera.json', 'source_role': 'materialized_ready_python_template', 'smoke_resolution': '256x256x5_frames'},
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
        model='WanVideo\\Wan2.1-Fun-V1.1-1.3B-Control-Camera.safetensors',
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
        blocks_to_swap=15,
        offload_img_emb=False,
        offload_txt_emb=False,
        use_non_blocking=True,
        vace_blocks_to_swap=0,
    )
    text_encoder = node(wf, 'CLIPLoader', '48',
        clip_name=MODELS['umt5_xxl_fp8_e4m3fn_scaled_clip'].filename,
        type='wan',
        device='default',
    )
    wan_video_tea_cache_52 = node(wf, 'WanVideoTeaCache', '52',
        widget_0=0.08,
        widget_1=6,
        widget_2=-1,
        widget_3='offload_device',
        widget_4='true',
        widget_5='e0',
    )
    input_image = node(wf, 'LoadImage', '58',
        image='oldman_upscaled.png',
)
    reroute_80 = node(wf, 'Reroute', '80')
    get_node_85 = node(wf, 'GetNode', '85',
        widget_0='VAE',
    )
    getnode_2 = node(wf, 'GetNode', '86',
        widget_0='VAE',
    )
    getnode_3 = node(wf, 'GetNode', '89',
        widget_0='InputImage',
    )
    wan_video_experimental_args_90 = node(wf, 'WanVideoExperimentalArgs', '90',
        widget_0='',
        widget_1=True,
        widget_2=False,
        widget_3=0,
        widget_4=True,
        widget_5=1,
        widget_6=1.25,
        widget_7=20,
    )
    param_int = node(wf, 'INTConstant', '105',
        value=81,
    )
    wan_video_text_encode_16 = node(wf, 'WanVideoTextEncode', '16',
        positive_prompt='high quality video of an old man',
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
    set_node_83 = node(wf, 'SetNode', '83',
        widget_0='VAE',
        WANVAE=wan_video_vaeloader.out(0),
    )
    # ════ IMAGE PREP ════
    resized_image = node(wf, 'ImageResizeKJv2', '97',
        height=256,
        
        upscale_method='lanczos',
        keep_proportion='crop',
        pad_color='0, 0, 0',
        crop_position='center',
        divisible_by=16,
        width=256,
        image=input_image.out('IMAGE'),
    )
    ade__camera_pose_basic = node(wf, 'ADE_CameraPoseBasic', '99',
        widget_0='Zoom Out',
        widget_1=0.1,
        widget_2=40,
        frame_length=param_int.out('VALUE'),
    )
    wan_video_sampler_27 = node(wf, 'WanVideoSampler', '27',
        steps=1,
        cfg=6,
        rope_function='comfy',
        start_step='',
        shift=5,
        seed=43,
force_offload=True,
        scheduler='unipc',
        riflex_freq_index=0,
        denoise_strength=1,
        batched_cfg='',
        cache_args=wan_video_tea_cache_52.out(0),
        experimental_args=wan_video_experimental_args_90.out(0),
        image_embeds=reroute_80.out(0),
        model=wan_video_model_loader_22.out(0),
        text_embeds=wan_video_text_encode_16.out(0),
    )
    wan_video_text_embed_bridge_46 = node(wf, 'WanVideoTextEmbedBridge', '46',
        negative=negative_prompt.out('CONDITIONING'),
        positive=positive_prompt.out('CONDITIONING'),
    )
    setnode_2 = node(wf, 'SetNode', '98',
        widget_0='InputImage',
        IMAGE=resized_image.out('IMAGE'),
    )
    camera_pose_visualizer_102 = node(wf, 'CameraPoseVisualizer', '102',
        widget_0='',
        widget_1=0.2,
        widget_2=0.3,
        widget_3=1,
        widget_4=False,
        widget_5=True,
        widget_6=False,
        cameractrl_poses=ade__camera_pose_basic.out(0),
    )
    wan_video_fun_camera_embeds_104 = node(wf, 'WanVideoFunCameraEmbeds', '104',
        widget_0=832,
        widget_1=480,
        widget_2=1,
        widget_3=0,
        widget_4=1,
        height=resized_image.out(2),
        poses=ade__camera_pose_basic.out(0),
        width=resized_image.out(1),
    )
    # ════ DECODE ════
    wan_video_decode_28 = node(wf, 'WanVideoDecode', '28',
        enable_vae_tiling=False,
        tile_x=272,
        tile_y=272,
        tile_stride_x=144,
        tile_stride_y=128,
        samples=wan_video_sampler_27.out(0),
        vae=getnode_2.out(0),
    )
    wan_video_image_to_video_encode_63 = node(wf, 'WanVideoImageToVideoEncode', '63',
        
        
        noise_aug_strength=0.03,
        start_latent_strength=1,
        end_latent_strength=1,
        force_offload=True,
        tiled_vae=True,
        control_embeds=wan_video_fun_camera_embeds_104.out(0),
        height=resized_image.out(2),
        num_frames=param_int.out('VALUE'),
        start_image=setnode_2.out(0),
        vae=get_node_85.out(0),
        width=resized_image.out(1),
    )
    # ════ OUTPUT ════
    preview_image_103 = node(wf, 'PreviewImage', '103',
        images=camera_pose_visualizer_102.out(0),
    )
    image_concat_multi_87 = node(wf, 'ImageConcatMulti', '87',
        inputcount=3,
        direction='left',
        match_image_size=True,
        unused_3=None,
        image_1=wan_video_decode_28.out(0),
        image_2=getnode_3.out(0),
        image_3=camera_pose_visualizer_102.out(0),
    )
    video_output = node(wf, 'VHS_VideoCombine', '30',
        save_output=True,
        images=image_concat_multi_87.out(0),
    )

    return finalize(
        wf,
        PUBLIC_INPUTS,
        READY_METADATA,
        output_node='',
        source_path=__file__,
    )

