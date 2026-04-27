# vibecomfy: generated — converted by tools/convert_ready_templates.py
# Edits will be overwritten on regeneration. Add a `# vibecomfy: manual`
# marker on the first line if hand-editing is required.
"""Auto-generated ready_template — see tools/convert_ready_templates.py."""
from __future__ import annotations

from vibecomfy.workflow import VibeWorkflow, WorkflowSource
from vibecomfy.registry.ready_template import apply_ready_template_policy


READY_METADATA = {'model_assets': [],
 'unbound_inputs': {'seed': 4501},
 'ready_template': 'video/wanvideo_wrapper_21_14b_fun_control',
 'workflow_template': 'wanvideo_wrapper_21_14b_fun_control',
 'capability': 'fun_control_video',
 'source_role': 'materialized_ready_python_template',
 'source_workflow': 'workflow_corpus/custom_nodes/wanvideo_wrapper/kijai/wan21_14b_fun_control.json',
 'coverage_tier': 'supplemental',
 'approach': 'WanVideoFun control workflow',
 'runtime_note': None,
 'discord_signal': None,
 'smoke_resolution': '256x256x5_frames'}

READY_REQUIREMENTS = {'models': [],
 'custom_nodes': ['ComfyUI-DepthAnythingV2',
                  'ComfyUI-KJNodes',
                  'ComfyUI-VideoHelperSuite',
                  'ComfyUI-WanVideoWrapper']}


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
    wanvideomodelloader = _node(wf, 'WanVideoModelLoader', '22',
        widget_0='WanVideo\\wan2.1_fun_control_1.3B_bf16.safetensors',
        widget_1='bf16',
        widget_2='disabled',
        widget_3='offload_device',
        widget_4='sdpa',
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
    wanvideoteacache = _node(wf, 'WanVideoTeaCache', '52',
        widget_0=0.08000000000000002,
        widget_1=1,
        widget_2=-1,
        widget_3='offload_device',
        widget_4='true',
        widget_5='e',
    )
    loadimage = _node(wf, 'LoadImage', '58',
        image='pasted/image (758).png',
        widget_1='image',
        widget_2='',
    )
    clipvisionloader = _node(wf, 'CLIPVisionLoader', '59',
        widget_0='clip_vision_h.safetensors',
    )
    vhs_loadvideo = _node(wf, 'VHS_LoadVideo', '71',
        video='wolf_interpolated.mp4',
    )
    downloadandloaddepthanythingv2model = _node(wf, 'DownloadAndLoadDepthAnythingV2Model', '73',
        widget_0='depth_anything_v2_vitl_fp16.safetensors',
    )
    reroute = _node(wf, 'Reroute', '79')
    reroute_2 = _node(wf, 'Reroute', '80')
    getnode = _node(wf, 'GetNode', '84',
        widget_0='VAE',
    )
    getnode_2 = _node(wf, 'GetNode', '85',
        widget_0='VAE',
    )
    getnode_3 = _node(wf, 'GetNode', '86',
        widget_0='VAE',
    )
    getnode_4 = _node(wf, 'GetNode', '89',
        widget_0='ControlSignal',
    )
    wanvideoexperimentalargs = _node(wf, 'WanVideoExperimentalArgs', '90',
        widget_0='',
        widget_1=True,
        widget_2=False,
        widget_3=0,
    )
    wanvideotextencode = _node(wf, 'WanVideoTextEncode', '16',
        widget_0="high quality nature video of a red fox in an autumnal forest, there's a waterfall in the background",
        widget_1='色调艳丽，过曝，静态，细节模糊不清，字幕，风格，作品，画作，画面，静止，整体发灰，最差质量，低质量，JPEG压缩残留，丑陋的，残缺的，多余的手指，画得不好的手部，画得不好的脸部，畸形的，毁容的，形态畸形的肢体，手指融合，静止不动的画面，杂乱的背景，三条腿，背景人很多，倒着走',
        widget_2=True,
        model_to_offload=wanvideomodelloader.out(0),
        t5=loadwanvideot5textencoder.out(0),
    )
    cliptextencode = _node(wf, 'CLIPTextEncode', '49',
        text="high quality nature video featuring a red panda balancing on a bamboo stem while a bird lands on it's head, on the background there is a waterfall",
        clip=cliploader.out(0),
    )
    cliptextencode_2 = _node(wf, 'CLIPTextEncode', '50',
        text='色调艳丽，过曝，静态，细节模糊不清，字幕，风格，作品，画作，画面，静止，整体发灰，最差质量，低质量，JPEG压缩残留，丑陋的，残缺的，多余的手指，画得不好的手部，画得不好的脸部，畸形的，毁容的，形态畸形的肢体，手指融合，静止不动的画面，杂乱的背景，三条腿，背景人很多，倒着走',
        clip=cliploader.out(0),
    )
    imageresizekj_2 = _node(wf, 'ImageResizeKJ', '75',
        widget_0=640,
        widget_1=640,
        widget_2='lanczos',
        widget_3=False,
        widget_4=16,
        widget_5=0,
        widget_6=0,
        widget_7='disabled',
        image=vhs_loadvideo.out(0),
    )
    setnode = _node(wf, 'SetNode', '83',
        widget_0='VAE',
        WANVAE=wanvideovaeloader.out(0),
    )
    wanvideosampler = _node(wf, 'WanVideoSampler', '27',
        steps=1,
        widget_0=1,
        widget_1=6,
        widget_10='comfy',
        widget_2=5,
        widget_3=42,
        widget_4='fixed',
        widget_5=True,
        widget_6='unipc',
        widget_7=0,
        widget_8=1,
        widget_9='',
        cache_args=wanvideoteacache.out(0),
        experimental_args=wanvideoexperimentalargs.out(0),
        image_embeds=reroute.out(0),
        model=wanvideomodelloader.out(0),
        text_embeds=wanvideotextencode.out(0),
    )
    wanvideotextembedbridge = _node(wf, 'WanVideoTextEmbedBridge', '46',
        negative=cliptextencode_2.out(0),
        positive=cliptextencode.out(0),
    )
    depthanything_v2 = _node(wf, 'DepthAnything_V2', '72',
        da_model=downloadandloaddepthanythingv2model.out(0),
        images=imageresizekj_2.out(0),
    )
    wanvideodecode = _node(wf, 'WanVideoDecode', '28',
        widget_0=False,
        widget_1=272,
        widget_2=272,
        widget_3=144,
        widget_4=128,
        samples=wanvideosampler.out(0),
        vae=getnode_3.out(0),
    )
    getimagesizeandcount = _node(wf, 'GetImageSizeAndCount', '76',
        image=depthanything_v2.out(0),
    )
    setnode_2 = _node(wf, 'SetNode', '88',
        widget_0='ControlSignal',
        IMAGE=depthanything_v2.out(0),
    )
    imageresizekj = _node(wf, 'ImageResizeKJ', '66',
        widget_0=624,
        widget_1=624,
        widget_2='lanczos',
        widget_3=False,
        widget_4=16,
        widget_5=0,
        widget_6=0,
        widget_7='center',
        height=getimagesizeandcount.out(2),
        image=loadimage.out(0),
        width=getimagesizeandcount.out(1),
    )
    wanvideoencode = _node(wf, 'WanVideoEncode', '77',
        widget_0=False,
        widget_1=272,
        widget_2=272,
        widget_3=144,
        widget_4=128,
        widget_5=0,
        widget_6=1,
        image=getimagesizeandcount.out(0),
        vae=getnode.out(0),
    )
    vhs_videocombine_2 = _node(wf, 'VHS_VideoCombine', '82',
        save_output=True,
        images=setnode_2.out(0),
    )
    imageconcatmulti = _node(wf, 'ImageConcatMulti', '87',
        widget_0=2,
        widget_1='right',
        widget_2=False,
        widget_3=None,
        image_1=getnode_4.out(0),
        image_2=wanvideodecode.out(0),
    )
    vhs_videocombine = _node(wf, 'VHS_VideoCombine', '30',
        save_output=True,
        images=imageconcatmulti.out(0),
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
        image_1=imageresizekj.out(0),
    )
    wanvideocontrolembeds = _node(wf, 'WanVideoControlEmbeds', '78',
        widget_0=0,
        widget_1=1,
        latents=wanvideoencode.out(0),
    )
    wanvideoimagetovideoencode = _node(wf, 'WanVideoImageToVideoEncode', '63',
        widget_0=256,
        widget_1=256,
        widget_2=5,
        widget_3=0.030000000000000006,
        widget_4=1,
        widget_5=1,
        widget_6=True,
        widget_7=True,
        clip_embeds=wanvideoclipvisionencode.out(0),
        control_embeds=wanvideocontrolembeds.out(0),
        height=imageresizekj.out(2),
        num_frames=getimagesizeandcount.out(3),
        start_image=imageresizekj.out(0),
        vae=getnode_2.out(0),
        width=imageresizekj.out(1),
    )
    wanvideoemptyembeds = _node(wf, 'WanVideoEmptyEmbeds', '69',
        widget_0=256,
        widget_1=256,
        widget_2=5,
        control_embeds=wanvideocontrolembeds.out(0),
        height=getimagesizeandcount.out(2),
        num_frames=getimagesizeandcount.out(3),
        width=getimagesizeandcount.out(1),
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

