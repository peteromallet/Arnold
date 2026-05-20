# vibecomfy: generated — converted by tools/convert_ready_templates.py
# Edits will be overwritten on regeneration. Add a `# vibecomfy: manual`
# marker on the first line if hand-editing is required.
"""Text To Video Controlnet.

Output: unknown.

Source:  workflow_corpus/custom_nodes/wanvideo_wrapper/kijai/wan22_5b_t2v_controlnet.json

Packs:   ComfyUI-KJNodes, ComfyUI-VideoHelperSuite, ComfyUI-WanVideoWrapper
"""
from __future__ import annotations

from vibecomfy.workflow import VibeWorkflow
from vibecomfy.templates import InputSpec, ModelAsset, ReadyMetadata, finalize, new_workflow, node
MODELS = {}

PUBLIC_INPUTS = {}

READY_METADATA = ReadyMetadata.build(
    template_id='wanvideo_wrapper_22_5b_t2v_controlnet',
    capability='text_to_video_controlnet',
    inputs=PUBLIC_INPUTS,
    models=MODELS,
    output_prefix='',
    requirements={'custom_nodes': ['ComfyUI-KJNodes', 'ComfyUI-VideoHelperSuite', 'ComfyUI-WanVideoWrapper'], 'custom_node_refs': [{'slug': 'ComfyUI-KJNodes', 'source': 'git', 'commit': 'b7646ad70a7daa7aeb919ca542274758d26ba2df', 'url': 'https://github.com/kijai/ComfyUI-KJNodes.git'}, {'slug': 'ComfyUI-VideoHelperSuite', 'source': 'git',
                       'commit': '4ee72c065db22c9d96c2427954dc69e7b908444b', 'url': 'https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite.git'}, {'slug': 'ComfyUI-WanVideoWrapper', 'source': 'git', 'commit': 'df8f3e49daaad117cf3090cc916c83f3d001494c', 'url': 'https://github.com/kijai/ComfyUI-WanVideoWrapper.git'}]},
    provenance={'source_workflow': 'workflow_corpus/custom_nodes/wanvideo_wrapper/kijai/wan22_5b_t2v_controlnet.json', 'approach': 'WanVideoWrapper 2.2 5B text-to-video ControlNet', 'smoke_resolution': '256x256x5_frames', 'source_role': 'materialized_ready_python_template'},
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
        model_name='Wan2_2_VAE_bf16.safetensors',
        precision='bf16',
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
        widget_9=0,
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
    # ════ CONTROL ════
    wan_video_controlnet_loader_103 = node(wf, 'WanVideoControlnetLoader', '103',
        widget_0='wan2.2-ti2v-5b-controlnet-depth-v1/diffusion_pytorch_model.safetensors',
        widget_1='bf16',
        widget_2='disabled',
        widget_3='main_device',
    )
    wan_video_enhance_a_video_107 = node(wf, 'WanVideoEnhanceAVideo', '107',
        widget_0=2,
        widget_1=0,
        widget_2=1,
    )
    param_int_113 = node(wf, 'INTConstant', '113',
        value=121,
    )
    param_height = node(wf, 'INTConstant', '114',
        value=704,
    )
    param_width = node(wf, 'INTConstant', '115',
        value=1280,
    )
    wan_video_model_loader_22 = node(wf, 'WanVideoModelLoader', '22',
        model='Wan2_2-TI2V-5B-FastWanFullAttn_bf16.safetensors',
        base_precision='fp16',
        quantization='disabled',
        load_device='offload_device',
        attention_mode='sdpa',
        compile_args=wan_video_torch_compile_settings_35.out(0),
    )
    vhs__load_video = node(wf, 'VHS_LoadVideo', '98',
        video='wolf_interpolated.mp4',
        frame_load_cap=param_int_113.out('VALUE'),
    )
    wan_video_empty_embeds_106 = node(wf, 'WanVideoEmptyEmbeds', '106',
        num_frames=5,
        widget_0=256,
        widget_1=256,
        widget_2=5,
        height=param_height.out('VALUE'),
        width=param_width.out('VALUE'),
    )
    # ════ IMAGE PREP ════
    resized_image_101 = node(wf, 'ImageResizeKJv2', '101',
        
        upscale_method='nearest-exact',
        keep_proportion='stretch',
        pad_color='0, 0, 0',
        crop_position='center',
        divisible_by=2,
        device='cpu',
        height=param_height.out('VALUE'),
        image=vhs__load_video.out(0),
        width=param_width.out('VALUE'),
    )
    midas_depthmappreprocessor = node(wf, 'MiDaS-DepthMapPreprocessor', '104',
        widget_0=6.28318530718,
        widget_1=0.1,
        widget_2=512,
        image=resized_image_101.out('IMAGE'),
    )
    imageresizekjv2_2 = node(wf, 'ImageResizeKJv2', '109',
        
        upscale_method='nearest-exact',
        keep_proportion='stretch',
        pad_color='0, 0, 0',
        crop_position='center',
        divisible_by=2,
        device='cpu',
        height=param_height.out('VALUE'),
        image=midas_depthmappreprocessor.out(0),
        width=param_width.out('VALUE'),
    )
    wan_video_controlnet_105 = node(wf, 'WanVideoControlnet', '105',
        widget_0=1,
        widget_1=3,
        widget_2=0,
        widget_3=1,
        control_images=imageresizekjv2_2.out('IMAGE'),
        controlnet=wan_video_controlnet_loader_103.out(0),
        model=wan_video_model_loader_22.out(0),
    )
    # ════ OUTPUT ════
    preview_animation_112 = node(wf, 'PreviewAnimation', '112',
        widget_0=24,
        images=imageresizekjv2_2.out('IMAGE'),
    )
    wan_video_text_encode_16 = node(wf, 'WanVideoTextEncode', '16',
        positive_prompt="Close-up shot with soft lighting, focusing sharply on the lower half of a young woman's face. Her lips are slightly parted as she blows an enormous bubblegum bubble. The bubble is semi-transparent, shimmering gently under the light, and surprisingly contains a miniature aquarium inside, where two orange-and-white goldfish slowly swim, their fins delicately fluttering as if in an aquatic universe. The background is a pure light blue color.",
        negative_prompt='Bright tones, overexposed, static, blurred details, subtitles, style, works, paintings, images, static, overall gray, worst quality, low quality, JPEG compression residue, ugly, incomplete, extra fingers, poorly drawn hands, poorly drawn faces, deformed, disfigured, misshapen limbs, fused fingers, still picture, messy background, three legs, many people in the background, walking backwards"',
        force_offload=True,
        use_disk_cache=False,
        device='gpu',
        model_to_offload=wan_video_controlnet_105.out(0),
        t5=load_wan_video_t5_text_encoder_11.out(0),
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
        feta_args=wan_video_enhance_a_video_107.out(0),
        image_embeds=wan_video_empty_embeds_106.out(0),
        model=wan_video_controlnet_105.out(0),
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

