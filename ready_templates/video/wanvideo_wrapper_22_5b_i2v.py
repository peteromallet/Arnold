# vibecomfy: generated — converted by tools/convert_ready_templates.py
# Edits will be overwritten on regeneration. Add a `# vibecomfy: manual`
# marker on the first line if hand-editing is required.
"""Auto-generated ready_template — see tools/convert_ready_templates.py."""
from __future__ import annotations

from vibecomfy.workflow import VibeWorkflow, WorkflowSource
from vibecomfy.registry.ready_template import apply_ready_template_policy


READY_METADATA = {'model_assets': [],
 'unbound_inputs': {'seed': 3534},
 'ready_template': 'video/wanvideo_wrapper_22_5b_i2v',
 'workflow_template': 'wanvideo_wrapper_22_5b_i2v',
 'capability': 'image_to_video',
 'source_role': 'materialized_ready_python_template',
 'source_workflow': 'workflow_corpus/custom_nodes/wanvideo_wrapper/kijai/wan22_5b_i2v.json',
 'coverage_tier': 'supplemental',
 'approach': 'WanVideoWrapper 2.2 5B image-to-video',
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
        widget_0='wanvideo\\Wan2_2_VAE_bf16.safetensors',
        widget_1='bf16',
    )
    cliploader = _node(wf, 'CLIPLoader', '48',
        clip_name='umt5_xxl_fp16.safetensors',
        type='wan',
        device='default',
    )
    loadimage = _node(wf, 'LoadImage', '58',
        image='image (658).png',
        widget_1='image',
    )
    wanvideoexperimentalargs = _node(wf, 'WanVideoExperimentalArgs', '90',
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
    wanvideoslg = _node(wf, 'WanVideoSLG', '91',
        widget_0='7,8,9',
        widget_1=0.1,
        widget_2=0.7,
    )
    wanvideoeasycache = _node(wf, 'WanVideoEasyCache', '94',
        widget_0=0.015,
        widget_1=10,
        widget_2=-1,
        widget_3='offload_device',
    )
    wanvideomodelloader = _node(wf, 'WanVideoModelLoader', '22',
        widget_0='WanVideo\\2_2\\wan2.2_ti2v_5B_fp16.safetensors',
        widget_1='fp16',
        widget_2='disabled',
        widget_3='offload_device',
        widget_4='sdpa',
        compile_args=wanvideotorchcompilesettings.out(0),
    )
    cliptextencode = _node(wf, 'CLIPTextEncode', '49',
        text="high quality nature video featuring a red panda balancing on a bamboo stem while a bird lands on it's head, on the background there is a waterfall",
        clip=cliploader.out(0),
    )
    cliptextencode_2 = _node(wf, 'CLIPTextEncode', '50',
        text='色调艳丽，过曝，静态，细节模糊不清，字幕，风格，作品，画作，画面，静止，整体发灰，最差质量，低质量，JPEG压缩残留，丑陋的，残缺的，多余的手指，画得不好的手部，画得不好的脸部，畸形的，毁容的，形态畸形的肢体，手指融合，静止不动的画面，杂乱的背景，三条腿，背景人很多，倒着走',
        clip=cliploader.out(0),
    )
    imageresizekjv2 = _node(wf, 'ImageResizeKJv2', '71',
        height=256,
        widget_0=256,
        widget_1=256,
        widget_2='lanczos',
        widget_3='crop',
        widget_4='0, 0, 0',
        widget_5='center',
        widget_6=32,
        widget_7='cpu',
        widget_8='<tr><td>Output: </td><td><b>1</b> x <b>1024</b> x <b>1024 | 12.00MB</b></td></tr>',
        width=256,
        image=loadimage.out(0),
    )
    wanvideotextencode = _node(wf, 'WanVideoTextEncode', '16',
        widget_0='the woman starts to play a violin',
        widget_1='Bright tones, overexposed, static, blurred details, subtitles, style, works, paintings, images, static, overall gray, worst quality, low quality, JPEG compression residue, ugly, incomplete, extra fingers, poorly drawn hands, poorly drawn faces, deformed, disfigured, misshapen limbs, fused fingers, still picture, messy background, three legs, many people in the background, walking backwards"',
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
    wanvideoencode = _node(wf, 'WanVideoEncode', '70',
        widget_0=False,
        widget_1=272,
        widget_2=272,
        widget_3=144,
        widget_4=128,
        widget_5=0,
        widget_6=1,
        image=imageresizekjv2.out(0),
        vae=wanvideovaeloader.out(0),
    )
    wanvideoemptyembeds = _node(wf, 'WanVideoEmptyEmbeds', '78',
        num_frames=5,
        widget_0=256,
        widget_1=256,
        widget_2=5,
        extra_latents=wanvideoencode.out(0),
        height=imageresizekjv2.out(2),
        width=imageresizekjv2.out(1),
    )
    wanvideosampler = _node(wf, 'WanVideoSampler', '27',
        steps=1,
        widget_0=1,
        widget_1=5,
        widget_10='comfy',
        widget_11=0,
        widget_12=-1,
        widget_13='',
        widget_2=8,
        widget_3=47,
        widget_4='fixed',
        widget_5=True,
        widget_6='flowmatch_pusa',
        widget_7=0,
        widget_8=1,
        widget_9='',
        cache_args=wanvideoeasycache.out(0),
        experimental_args=wanvideoexperimentalargs.out(0),
        image_embeds=wanvideoemptyembeds.out(0),
        model=wanvideomodelloader.out(0),
        slg_args=wanvideoslg.out(0),
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
    vhs_videocombine = _node(wf, 'VHS_VideoCombine', '92',
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

