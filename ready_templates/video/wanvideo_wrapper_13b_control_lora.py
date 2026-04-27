# vibecomfy: generated — converted by tools/convert_ready_templates.py
# Edits will be overwritten on regeneration. Add a `# vibecomfy: manual`
# marker on the first line if hand-editing is required.
"""Auto-generated ready_template — see tools/convert_ready_templates.py."""
from __future__ import annotations

from vibecomfy.workflow import VibeWorkflow, WorkflowSource
from vibecomfy.registry.ready_template import apply_ready_template_policy


READY_METADATA = {'model_assets': [],
 'unbound_inputs': {'seed': 4407},
 'ready_template': 'video/wanvideo_wrapper_13b_control_lora',
 'workflow_template': 'wanvideo_wrapper_13b_control_lora',
 'capability': 'control_lora_video',
 'source_role': 'materialized_ready_python_template',
 'source_workflow': 'workflow_corpus/custom_nodes/wanvideo_wrapper/kijai/wan13b_control_lora.json',
 'coverage_tier': 'supplemental',
 'approach': 'WanVideoWrapper 1.3B control LoRA',
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
    )
    wanvideovaeloader = _node(wf, 'WanVideoVAELoader', '38',
        widget_0='wanvideo\\Wan2_1_VAE_bf16.safetensors',
        widget_1='bf16',
    )
    wanvideoteacache = _node(wf, 'WanVideoTeaCache', '52',
        widget_0=0.1,
        widget_1=1,
        widget_2=-1,
        widget_3='offload_device',
        widget_4='true',
    )
    wanvideotorchcompilesettings_2 = _node(wf, 'WanVideoTorchCompileSettings', '64',
        widget_0='inductor',
        widget_1=False,
        widget_2='default',
        widget_3=False,
        widget_4=64,
        widget_5=True,
    )
    vhs_loadvideo = _node(wf, 'VHS_LoadVideo', '97',
        video='wolf_interpolated.mp4',
    )
    wanvideoloraselect = _node(wf, 'WanVideoLoraSelect', '98',
        widget_0='WanVid\\wan2.1-1.3b-control-lora-tile-v1.1_comfy.safetensors',
        widget_1=1,
        widget_2=False,
    )
    wanvideotextencode = _node(wf, 'WanVideoTextEncode', '16',
        widget_0='video of a wolf',
        widget_1='色调艳丽，过曝，静态，细节模糊不清，字幕，风格，作品，画作，画面，静止，整体发灰，最差质量，低质量，JPEG压缩残留，丑陋的，残缺的，多余的手指，画得不好的手部，画得不好的脸部，畸形的，毁容的，形态畸形的肢体，手指融合，静止不动的画面，杂乱的背景，三条腿，背景人很多，倒着走',
        widget_2=True,
        t5=loadwanvideot5textencoder.out(0),
    )
    wanvideomodelloader = _node(wf, 'WanVideoModelLoader', '22',
        widget_0='WanVideo\\wan2.1_t2v_1.3B_fp16.safetensors',
        widget_1='fp16',
        widget_2='disabled',
        widget_3='offload_device',
        widget_4='sdpa',
        lora=wanvideoloraselect.out(0),
    )
    imageblur = _node(wf, 'ImageBlur', '104',
        widget_0=4,
        widget_1=1,
        image=vhs_loadvideo.out(0),
    )
    wanvideoencode = _node(wf, 'WanVideoEncode', '95',
        widget_0=False,
        widget_1=272,
        widget_2=272,
        widget_3=144,
        widget_4=128,
        widget_5=0,
        widget_6=1.0000000000000002,
        image=imageblur.out(0),
        vae=wanvideovaeloader.out(0),
    )
    wanvideocontrolembeds = _node(wf, 'WanVideoControlEmbeds', '96',
        widget_0=0,
        widget_1=0.7,
        latents=wanvideoencode.out(0),
    )
    wanvideosampler = _node(wf, 'WanVideoSampler', '27',
        steps=1,
        widget_0=1,
        widget_1=6,
        widget_10='comfy',
        widget_2=5,
        widget_3=0,
        widget_4='fixed',
        widget_5=True,
        widget_6='unipc',
        widget_7=0,
        widget_8=1,
        widget_9='',
        cache_args=wanvideoteacache.out(0),
        image_embeds=wanvideocontrolembeds.out(0),
        model=wanvideomodelloader.out(0),
        text_embeds=wanvideotextencode.out(0),
    )
    wanvideodecode = _node(wf, 'WanVideoDecode', '28',
        widget_0=False,
        widget_1=272,
        widget_2=272,
        widget_3=144,
        widget_4=128,
        samples=wanvideosampler.out(0),
        vae=wanvideovaeloader.out(0),
    )
    imageconcatmulti = _node(wf, 'ImageConcatMulti', '103',
        widget_0=2,
        widget_1='right',
        widget_2=False,
        widget_3=None,
        image_1=imageblur.out(0),
        image_2=wanvideodecode.out(0),
    )
    vhs_videocombine = _node(wf, 'VHS_VideoCombine', '30',
        save_output=True,
        images=imageconcatmulti.out(0),
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

