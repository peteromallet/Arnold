# vibecomfy: generated — converted by tools/convert_ready_templates.py
# Edits will be overwritten on regeneration. Add a `# vibecomfy: manual`
# marker on the first line if hand-editing is required.
"""Auto-generated ready_template — see tools/convert_ready_templates.py."""
from __future__ import annotations

from vibecomfy.workflow import VibeWorkflow, WorkflowSource
from vibecomfy.registry.ready_template import apply_ready_template_policy


READY_METADATA = {'model_assets': [],
 'unbound_inputs': {'seed': 3581},
 'ready_template': 'video/wanvideo_wrapper_21_14b_i2v',
 'workflow_template': 'wanvideo_wrapper_21_14b_i2v',
 'capability': 'image_to_video',
 'source_role': 'materialized_ready_python_template',
 'source_workflow': 'workflow_corpus/custom_nodes/wanvideo_wrapper/kijai/wan21_14b_i2v.json',
 'coverage_tier': 'supplemental',
 'approach': 'WanVideoWrapper 2.1 14B image-to-video',
 'runtime_note': None,
 'discord_signal': None,
 'smoke_resolution': '256x256x5_frames'}

READY_REQUIREMENTS = {'models': [], 'custom_nodes': ['ComfyUI-KJNodes', 'ComfyUI-VideoHelperSuite', 'ComfyUI-WanVideoWrapper']}


def build() -> VibeWorkflow:
    """Build the workflow (auto-generated)."""
    wf = VibeWorkflow(
        READY_METADATA["ready_template"],
        WorkflowSource(
            id=READY_METADATA["ready_template"],
            path=__file__,
            source_type="ready_template",
        ),
    )

    loadwanvideot5textencoder = _node(wf, 'LoadWanVideoT5TextEncoder', '11',
        widget_0='umt5-xxl-enc-bf16.safetensors',
        widget_1='bf16',
        widget_2='offload_device',
        widget_3='disabled',
    )
    wanvideotorchcompilesettings = _node(wf, 'WanVideoTorchCompileSettings', '35',
        widget_0='inductor',
        widget_1=False,
        widget_2='default',
        widget_3=False,
        widget_4=64,
        widget_5=True,
        widget_6=128,
    )
    wanvideovaeloader = _node(wf, 'WanVideoVAELoader', '38',
        widget_0='wanvideo\\Wan2_1_VAE_bf16.safetensors',
        widget_1='bf16',
    )
    wanvideoblockswap = _node(wf, 'WanVideoBlockSwap', '39',
        widget_0=10,
        widget_1=False,
        widget_2=False,
        widget_3=True,
        widget_4=0,
    )
    wanvideovrammanagement = _node(wf, 'WanVideoVRAMManagement', '45',
        widget_0=1,
    )
    cliploader = _node(wf, 'CLIPLoader', '48',
        clip_name='umt5_xxl_fp16.safetensors',
        type='wan',
        device='default',
    )
    loadimage = _node(wf, 'LoadImage', '58',
        image='oldman_upscaled.png',
        widget_1='image',
    )
    clipvisionloader = _node(wf, 'CLIPVisionLoader', '59',
        widget_0='clip_vision_h.safetensors',
    )
    wanvideoloraselect = _node(wf, 'WanVideoLoraSelect', '69',
        widget_0='WanVideo\\Lightx2v\\lightx2v_I2V_14B_480p_cfg_step_distill_rank64_bf16.safetensors',
        widget_1=1,
        widget_2=False,
        widget_3="<details><summary><b>Metadata</b></summary><table border='0' cellpadding='3'><tr><td colspan='2'><b>Metadata</b></td></tr><tr><td>No metadata found</td></tr></table></details>",
    )
    wanvideomodelloader = _node(wf, 'WanVideoModelLoader', '22',
        widget_0='WanVideo\\Wan2_1-I2V-14B-480P_fp8_e4m3fn.safetensors',
        widget_1='fp16',
        widget_2='fp8_e4m3fn',
        widget_3='offload_device',
        widget_4='sdpa',
        lora=wanvideoloraselect.out(0),
    )
    cliptextencode = _node(wf, 'CLIPTextEncode', '49',
        text="high quality nature video featuring a red panda balancing on a bamboo stem while a bird lands on it's head, on the background there is a waterfall",
        clip=cliploader.out(0),
    )
    cliptextencode_2 = _node(wf, 'CLIPTextEncode', '50',
        text='色调艳丽，过曝，静态，细节模糊不清，字幕，风格，作品，画作，画面，静止，整体发灰，最差质量，低质量，JPEG压缩残留，丑陋的，残缺的，多余的手指，画得不好的手部，画得不好的脸部，畸形的，毁容的，形态畸形的肢体，手指融合，静止不动的画面，杂乱的背景，三条腿，背景人很多，倒着走',
        clip=cliploader.out(0),
    )
    imageresizekjv2 = _node(wf, 'ImageResizeKJv2', '68',
        height=256,
        widget_0=256,
        widget_1=256,
        widget_2='lanczos',
        widget_3='crop',
        widget_4='0, 0, 0',
        widget_5='center',
        widget_6=16,
        widget_7='cpu',
        width=256,
        image=loadimage.out(0),
    )
    wanvideotextencode = _node(wf, 'WanVideoTextEncode', '16',
        widget_0='an old man is stroking his beard thoughtfully',
        widget_1='色调艳丽，过曝，静态，细节模糊不清，字幕，风格，作品，画作，画面，静止，整体发灰，最差质量，低质量，JPEG压缩残留，丑陋的，残缺的，多余的手指，画得不好的手部，画得不好的脸部，畸形的，毁容的，形态畸形的肢体，手指融合，静止不动的画面，杂乱的背景，三条腿，背景人很多，倒着走',
        widget_2=True,
        widget_3=False,
        widget_4='gpu',
        model_to_offload=wanvideomodelloader.out(0),
        t5=loadwanvideot5textencoder.out(0),
    )
    wanvideotextembedbridge = _node(wf, 'WanVideoTextEmbedBridge', '46',
        negative=cliptextencode_2.out(0),
        positive=cliptextencode.out(0),
    )
    wanvideoclipvisionencode = _node(wf, 'WanVideoClipVisionEncode', '65',
        widget_0=1,
        widget_1=1,
        widget_2='center',
        widget_3='average',
        widget_4=True,
        widget_5=0,
        widget_6=0.20000000000000004,
        clip_vision=clipvisionloader.out(0),
        image_1=imageresizekjv2.out(0),
    )
    wanvideosetblockswap = _node(wf, 'WanVideoSetBlockSwap', '70',
        block_swap_args=wanvideoblockswap.out(0),
        model=wanvideomodelloader.out(0),
    )
    wanvideoimagetovideoencode = _node(wf, 'WanVideoImageToVideoEncode', '63',
        num_frames=5,
        widget_0=256,
        widget_1=256,
        widget_2=5,
        widget_3=0.030000000000000006,
        widget_4=1,
        widget_5=1,
        widget_6=True,
        widget_7=False,
        widget_8=False,
        clip_embeds=wanvideoclipvisionencode.out(0),
        height=imageresizekjv2.out(2),
        start_image=imageresizekjv2.out(0),
        vae=wanvideovaeloader.out(0),
        width=imageresizekjv2.out(1),
    )
    wanvideosampler = _node(wf, 'WanVideoSampler', '27',
        steps=1,
        widget_0=1,
        widget_1=1,
        widget_10='comfy',
        widget_11=0,
        widget_12=-1,
        widget_13=False,
        widget_2=5,
        widget_3=1057359483639287,
        widget_4='fixed',
        widget_5=True,
        widget_6='dpm++_sde',
        widget_7=0,
        widget_8=1,
        widget_9='',
        image_embeds=wanvideoimagetovideoencode.out(0),
        model=wanvideosetblockswap.out(0),
        text_embeds=wanvideotextencode.out(0),
    )
    wanvideodecode = _node(wf, 'WanVideoDecode', '28',
        widget_0=False,
        widget_1=272,
        widget_2=272,
        widget_3=144,
        widget_4=128,
        widget_5='default',
        samples=wanvideosampler.out(0),
        vae=wanvideovaeloader.out(0),
    )
    vhs_videocombine = _node(wf, 'VHS_VideoCombine', '30',
        save_output=True,
        images=wanvideodecode.out(0),
    )

    wf.finalize_metadata()
    apply_ready_template_policy(wf, READY_METADATA, source_path=__file__, requirements=READY_REQUIREMENTS)
    return wf


def _node(wf: VibeWorkflow, class_type: str, _id: str, _extras: dict | None = None, **kwargs):
    """Create a node, preserving the original node id from the source workflow.

    `_extras` carries kwargs whose names are not valid Python identifiers
    (e.g. "resize_type.multiple") which Python disallows as kwarg syntax.
    They are applied to the new node post-construction.
    """
    from vibecomfy.handles import Handle
    builder = wf.node(class_type, **kwargs)
    if _extras:
        for key, value in _extras.items():
            if isinstance(value, Handle):
                wf.connect(value, f"{builder.node.id}.{key}")
            else:
                builder.node.inputs[key] = value
    if builder.node.id != _id:
        old_id = builder.node.id
        node = wf.nodes.pop(old_id)
        node.id = _id
        wf.nodes[_id] = node
        for edge in wf.edges:
            if edge.to_node == old_id:
                edge.to_node = _id
            if edge.from_node == old_id:
                edge.from_node = _id
    return builder

