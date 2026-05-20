# vibecomfy: generated — converted by tools/convert_ready_templates.py
# Edits will be overwritten on regeneration. Add a `# vibecomfy: manual`
# marker on the first line if hand-editing is required.
"""Control Lora Video.

Output: unknown.

Source:  workflow_corpus/custom_nodes/wanvideo_wrapper/kijai/wan13b_control_lora.json

Packs:   ComfyUI-VideoHelperSuite, ComfyUI-WanVideoWrapper
"""
from __future__ import annotations

from vibecomfy.workflow import VibeWorkflow
from vibecomfy.templates import InputSpec, ModelAsset, ReadyMetadata, finalize, new_workflow, node
MODELS = {}

PUBLIC_INPUTS = {}

READY_METADATA = ReadyMetadata.build(
    template_id='wanvideo_wrapper_13b_control_lora',
    capability='control_lora_video',
    inputs=PUBLIC_INPUTS,
    models=MODELS,
    output_prefix='',
    requirements={'custom_nodes': ['ComfyUI-VideoHelperSuite', 'ComfyUI-WanVideoWrapper'], 'custom_node_refs': [{'slug': 'ComfyUI-KJNodes', 'source': 'git', 'commit': 'b7646ad70a7daa7aeb919ca542274758d26ba2df', 'url': 'https://github.com/kijai/ComfyUI-KJNodes.git'}, {'slug': 'ComfyUI-VideoHelperSuite', 'source': 'git',
                       'commit': '4ee72c065db22c9d96c2427954dc69e7b908444b', 'url': 'https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite.git'}, {'slug': 'ComfyUI-WanVideoWrapper', 'source': 'git', 'commit': 'df8f3e49daaad117cf3090cc916c83f3d001494c', 'url': 'https://github.com/kijai/ComfyUI-WanVideoWrapper.git'}]},
    provenance={'smoke_resolution': '256x256x5_frames', 'source_role': 'materialized_ready_python_template', 'source_workflow': 'workflow_corpus/custom_nodes/wanvideo_wrapper/kijai/wan13b_control_lora.json', 'approach': 'WanVideoWrapper 1.3B control LoRA'},
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
    )
    # ════ LOADERS ════
    wan_video_vaeloader = node(wf, 'WanVideoVAELoader', '38',
        model_name='wanvideo\\Wan2_1_VAE_bf16.safetensors',
        precision='bf16',
    )
    wan_video_tea_cache_52 = node(wf, 'WanVideoTeaCache', '52',
        widget_0=0.1,
        widget_1=1,
        widget_2=-1,
        widget_3='offload_device',
        widget_4='true',
    )
    wan_video_torch_compile_settings_2 = node(wf, 'WanVideoTorchCompileSettings', '64',
        backend='inductor',
        fullgraph=False,
        mode='default',
        dynamic=False,
        dynamo_cache_size_limit=64,
        compile_transformer_blocks_only=True,
    )
    vhs__load_video = node(wf, 'VHS_LoadVideo', '97',
        video='wolf_interpolated.mp4',
    )
    wan_video_lora_select_98 = node(wf, 'WanVideoLoraSelect', '98',
        lora='WanVid\\wan2.1-1.3b-control-lora-tile-v1.1_comfy.safetensors',
        strength=1,
        low_mem_load=False,
    )
    wan_video_text_encode_16 = node(wf, 'WanVideoTextEncode', '16',
        positive_prompt='video of a wolf',
        negative_prompt='色调艳丽，过曝，静态，细节模糊不清，字幕，风格，作品，画作，画面，静止，整体发灰，最差质量，低质量，JPEG压缩残留，丑陋的，残缺的，多余的手指，画得不好的手部，画得不好的脸部，畸形的，毁容的，形态畸形的肢体，手指融合，静止不动的画面，杂乱的背景，三条腿，背景人很多，倒着走',
        force_offload=True,
        t5=load_wan_video_t5_text_encoder_11.out(0),
    )
    wan_video_model_loader_22 = node(wf, 'WanVideoModelLoader', '22',
        model='WanVideo\\wan2.1_t2v_1.3B_fp16.safetensors',
        base_precision='fp16',
        quantization='disabled',
        load_device='offload_device',
        attention_mode='sdpa',
        lora=wan_video_lora_select_98.out(0),
    )
    image_blur_104 = node(wf, 'ImageBlur', '104',
        widget_0=4,
        widget_1=1,
        image=vhs__load_video.out(0),
    )
    wan_video_encode_95 = node(wf, 'WanVideoEncode', '95',
        widget_0=False,
        widget_1=272,
        widget_2=272,
        widget_3=144,
        widget_4=128,
        widget_5=0,
        widget_6=1.0000000000000002,
        image=image_blur_104.out(0),
        vae=wan_video_vaeloader.out(0),
    )
    # ════ CONTROL ════
    wan_video_control_embeds_96 = node(wf, 'WanVideoControlEmbeds', '96',
        widget_0=0,
        widget_1=0.7,
        latents=wan_video_encode_95.out(0),
    )
    wan_video_sampler_27 = node(wf, 'WanVideoSampler', '27',
        steps=1,
        cfg=6,
        rope_function='comfy',
        shift=5,
        seed=0,
force_offload=True,
        scheduler='unipc',
        riflex_freq_index=0,
        denoise_strength=1,
        batched_cfg='',
        cache_args=wan_video_tea_cache_52.out(0),
        image_embeds=wan_video_control_embeds_96.out(0),
        model=wan_video_model_loader_22.out(0),
        text_embeds=wan_video_text_encode_16.out(0),
    )
    # ════ DECODE ════
    wan_video_decode_28 = node(wf, 'WanVideoDecode', '28',
        enable_vae_tiling=False,
        tile_x=272,
        tile_y=272,
        tile_stride_x=144,
        tile_stride_y=128,
        samples=wan_video_sampler_27.out(0),
        vae=wan_video_vaeloader.out(0),
    )
    image_concat_multi_103 = node(wf, 'ImageConcatMulti', '103',
        inputcount=2,
        direction='right',
        match_image_size=False,
        unused_3=None,
        image_1=image_blur_104.out(0),
        image_2=wan_video_decode_28.out(0),
    )
    # ════ OUTPUT ════
    video_output = node(wf, 'VHS_VideoCombine', '30',
        save_output=True,
        images=image_concat_multi_103.out(0),
    )

    return finalize(
        wf,
        PUBLIC_INPUTS,
        READY_METADATA,
        output_node='',
        source_path=__file__,
    )

