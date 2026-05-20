# vibecomfy: generated — converted by tools/convert_ready_templates.py
# Edits will be overwritten on regeneration. Add a `# vibecomfy: manual`
# marker on the first line if hand-editing is required.
"""Camera Control Video with Umt 5 Xxl Fp 16 CLIP.

Output: unknown.

Source:  workflow_corpus/custom_nodes/wanvideo_wrapper/kijai/wan13b_recammaster.json

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
}

PUBLIC_INPUTS = {}

READY_METADATA = ReadyMetadata.build(
    template_id='wanvideo_wrapper_13b_recammaster',
    capability='camera_control_video',
    inputs=PUBLIC_INPUTS,
    models=MODELS,
    output_prefix='',
    requirements={'custom_nodes': ['ComfyUI-KJNodes', 'ComfyUI-VideoHelperSuite', 'ComfyUI-WanVideoWrapper', 'rgthree-comfy'], 'custom_node_refs': [{'slug': 'ComfyUI-KJNodes', 'source': 'git', 'commit': 'b7646ad70a7daa7aeb919ca542274758d26ba2df', 'url': 'https://github.com/kijai/ComfyUI-KJNodes.git'}, {'slug': 'ComfyUI-VideoHelperSuite', 'source': 'git',
                       'commit': '4ee72c065db22c9d96c2427954dc69e7b908444b', 'url': 'https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite.git'}, {'slug': 'ComfyUI-WanVideoWrapper', 'source': 'git', 'commit': 'df8f3e49daaad117cf3090cc916c83f3d001494c', 'url': 'https://github.com/kijai/ComfyUI-WanVideoWrapper.git'}, {'slug': 'rgthree-comfy', 'source': 'git',
                       'commit': '738105af5fb14e96fbecaf406dc356e284797e8c', 'url': 'https://github.com/rgthree/rgthree-comfy.git'}]},
    provenance={'source_workflow': 'workflow_corpus/custom_nodes/wanvideo_wrapper/kijai/wan13b_recammaster.json', 'smoke_resolution': '256x256x5_frames', 'source_role': 'materialized_ready_python_template', 'approach': 'ReCamMaster camera-control workflow'},
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
        model='WanVideo\\Wan2_1_kwai_recammaster_1_3B_step20000_bf16.safetensors',
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
        blocks_to_swap=20,
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
        widget_0=0.1,
        widget_1=6,
        widget_2=-1,
        widget_3='offload_device',
        widget_4='true',
        widget_5='e0',
    )
    download_and_load_florence2_model_124 = node(wf, 'DownloadAndLoadFlorence2Model', '124',
        widget_0='MiaoshouAI/Florence-2-base-PromptGen-v2.0',
        widget_1='fp16',
        widget_2='sdpa',
    )
    wan_video_experimental_args_127 = node(wf, 'WanVideoExperimentalArgs', '127',
        widget_0='',
        widget_1=True,
        widget_2=False,
        widget_3=0,
    )
    vhs__load_video = node(wf, 'VHS_LoadVideo', '128',
        video='wolf_interpolated.mp4',
    )
    get_node_141 = node(wf, 'GetNode', '141',
        widget_0='WanModel',
    )
    getnode_2 = node(wf, 'GetNode', '143',
        widget_0='TextEmbeds',
    )
    getnode_3 = node(wf, 'GetNode', '145',
        widget_0='WanVAE',
    )
    getnode_4 = node(wf, 'GetNode', '146',
        widget_0='WanVAE',
    )
    getnode_5 = node(wf, 'GetNode', '157',
        widget_0='InputLatents',
    )
    wan_video_re_cam_master_generate_orbit_camera_206 = node(wf, 'WanVideoReCamMasterGenerateOrbitCamera', '206',
        widget_0=81,
        widget_1=90,
    )
    positive_prompt = node(wf, 'CLIPTextEncode', '49',
        text="high quality nature video featuring a red panda balancing on a bamboo stem while a bird lands on it's head, on the background there is a waterfall",
        clip=text_encoder.out('CLIP'),
    )
    negative_prompt = node(wf, 'CLIPTextEncode', '50',
        text='色调艳丽，过曝，静态，细节模糊不清，字幕，风格，作品，画作，画面，静止，整体发灰，最差质量，低质量，JPEG压缩残留，丑陋的，残缺的，多余的手指，画得不好的手部，画得不好的脸部，畸形的，毁容的，形态畸形的肢体，手指融合，静止不动的画面，杂乱的背景，三条腿，背景人很多，倒着走',
        clip=text_encoder.out('CLIP'),
    )
    get_image_size_and_count_129 = node(wf, 'GetImageSizeAndCount', '129',
        image=vhs__load_video.out(0),
    )
    set_node_140 = node(wf, 'SetNode', '140',
        widget_0='WanModel',
        WANVIDEOMODEL=wan_video_model_loader_22.out(0),
    )
    setnode_3 = node(wf, 'SetNode', '144',
        widget_0='WanVAE',
        WANVAE=wan_video_vaeloader.out(0),
    )
    wan_video_re_cam_master_default_camera_205 = node(wf, 'WanVideoReCamMasterDefaultCamera', '205',
        widget_0='pan_right',
        latents=getnode_5.out(0),
    )
    wan_video_text_embed_bridge_46 = node(wf, 'WanVideoTextEmbedBridge', '46',
        negative=negative_prompt.out('CONDITIONING'),
        positive=positive_prompt.out('CONDITIONING'),
    )
    wan_video_re_cam_master_camera_embed_56 = node(wf, 'WanVideoReCamMasterCameraEmbed', '56',
        camera_poses=wan_video_re_cam_master_default_camera_205.out(0),
        latents=getnode_5.out(0),
    )
    # ════ IMAGE PREP ════
    image_resize_k_j_59 = node(wf, 'ImageResizeKJ', '59',
        widget_0=832,
        widget_1=480,
        widget_2='lanczos',
        widget_3=False,
        widget_4=16,
        widget_5='center',
        image=get_image_size_and_count_129.out(0),
    )
    widget_to_string_74 = node(wf, 'WidgetToString', '74',
        widget_0=0,
        widget_1='camera_type',
        widget_2=False,
        widget_3='',
        widget_4=2,
        any_input=wan_video_re_cam_master_default_camera_205.out(0),
    )
    get_image_range_from_batch_130 = node(wf, 'GetImageRangeFromBatch', '130',
        widget_0=0,
        widget_1=1,
        images=image_resize_k_j_59.out(0),
    )
    re_cam_master_pose_visualizer_138 = node(wf, 'ReCamMasterPoseVisualizer', '138',
        widget_0=0.1,
        widget_1=0.2,
        widget_2=0.4,
        widget_3=0.5,
        camera_poses=wan_video_re_cam_master_camera_embed_56.out(1),
    )
    setnode_4 = node(wf, 'SetNode', '147',
        widget_0='InputVideo',
        IMAGE=image_resize_k_j_59.out(0),
    )
    wan_video_sampler_155 = node(wf, 'WanVideoSampler', '155',
        steps=1,
        cfg=6,
        rope_function='comfy',
        shift=5,
        seed=42,
force_offload=True,
        scheduler='unipc',
        riflex_freq_index=0,
        denoise_strength=1,
        batched_cfg=False,
        cache_args=wan_video_tea_cache_52.out(0),
        experimental_args=wan_video_experimental_args_127.out(0),
        image_embeds=wan_video_re_cam_master_camera_embed_56.out(0),
        model=get_node_141.out(0),
        text_embeds=getnode_2.out(0),
    )
    # ════ DECODE ════
    wan_video_decode_28 = node(wf, 'WanVideoDecode', '28',
        enable_vae_tiling=False,
        tile_x=272,
        tile_y=272,
        tile_stride_x=144,
        tile_stride_y=128,
        samples=wan_video_sampler_155.out(0),
        vae=getnode_3.out(0),
    )
    wan_video_encode_58 = node(wf, 'WanVideoEncode', '58',
        widget_0=False,
        widget_1=272,
        widget_2=272,
        widget_3=144,
        widget_4=128,
        widget_5=0,
        widget_6=1,
        image=setnode_4.out(0),
        vae=getnode_4.out(0),
    )
    florence2_run_123 = node(wf, 'Florence2Run', '123',
        widget_0='',
        widget_1='detailed_caption',
        widget_2=True,
        widget_3=False,
        widget_4=1024,
        widget_5=3,
        widget_6=True,
        widget_7='',
        widget_8=1,
        widget_9='fixed',
        florence2_model=download_and_load_florence2_model_124.out(0),
        image=get_image_range_from_batch_130.out(0),
    )
    # ════ OUTPUT ════
    preview_image_131 = node(wf, 'PreviewImage', '131',
        images=get_image_range_from_batch_130.out(0),
    )
    preview_image_2 = node(wf, 'PreviewImage', '139',
        images=re_cam_master_pose_visualizer_138.out(0),
    )
    wan_video_text_encode_16 = node(wf, 'WanVideoTextEncode', '16',
        negative_prompt='色调艳丽，过曝，静态，细节模糊不清，字幕，风格，作品，画作，画面，静止，整体发灰，最差质量，低质量，JPEG压缩残留，丑陋的，残缺的，多余的手指，画得不好的手部，画得不好的脸部，畸形的，毁容的，形态畸形的肢体，手指融合，静止不动的画面，杂乱的背景，三条腿，背景人很多，倒着走',
        force_offload=True,
        positive_prompt=florence2_run_123.out(2),
        t5=load_wan_video_t5_text_encoder_11.out(0),
    )
    add_label_122 = node(wf, 'AddLabel', '122',
        widget_0=10,
        widget_1=2,
        widget_2=48,
        widget_3=32,
        widget_4='white',
        widget_5='black',
        widget_6='FreeMonoBoldOblique.otf',
        widget_7='input',
        widget_8='up',
        image=wan_video_decode_28.out(0),
        text=widget_to_string_74.out(0),
    )
    showtext_pysssss = node(wf, 'ShowText|pysssss', '125',
        widget_0='A man in a suit and tie walking down a hallway. He has a friendly expression and is looking directly at the camera. The hallway has beige walls adorned with framed black and white photographs. There is a door on the left side of the hallway and a poster on the wall. The lighting is soft and natural. The image is high quality and has a watermark in the bottom right corner.',
        widget_1='A man in a suit and tie walking down a hallway. He has a friendly expression and is looking directly at the camera. The hallway has beige walls adorned with framed black and white photographs. There is a door on the left side of the hallway and a poster on the wall. The lighting is soft and natural. The image is high quality and has a watermark in the bottom right corner.',
        text=florence2_run_123.out(2),
    )
    setnode_5 = node(wf, 'SetNode', '156',
        widget_0='InputLatents',
        LATENT=wan_video_encode_58.out(0),
    )
    video_output = node(wf, 'VHS_VideoCombine', '30',
        save_output=True,
        images=add_label_122.out(0),
    )
    setnode_2 = node(wf, 'SetNode', '142',
        widget_0='TextEmbeds',
        WANVIDEOTEXTEMBEDS=wan_video_text_encode_16.out(0),
    )

    return finalize(
        wf,
        PUBLIC_INPUTS,
        READY_METADATA,
        output_node='',
        source_path=__file__,
    )

