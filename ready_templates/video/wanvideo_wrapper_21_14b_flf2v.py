# vibecomfy: generated — converted by tools/convert_ready_templates.py
# Edits will be overwritten on regeneration. Add a `# vibecomfy: manual`
# marker on the first line if hand-editing is required.
"""Auto-generated ready_template — see tools/convert_ready_templates.py."""
from __future__ import annotations

from vibecomfy.workflow import VibeWorkflow, WorkflowSource
from vibecomfy.registry.ready_template import apply_ready_template_policy


READY_METADATA = {'model_assets': [],
 'unbound_inputs': {'seed': 3788},
 'ready_template': 'video/wanvideo_wrapper_21_14b_flf2v',
 'workflow_template': 'wanvideo_wrapper_21_14b_flf2v',
 'capability': 'first_last_frame_video',
 'source_role': 'materialized_ready_python_template',
 'source_workflow': 'workflow_corpus/custom_nodes/wanvideo_wrapper/kijai/wan21_14b_flf2v.json',
 'coverage_tier': 'supplemental',
 'approach': 'WanVideoWrapper first/last-frame video',
 'runtime_note': None,
 'discord_signal': None,
 'smoke_resolution': '256x256x5_frames'}

READY_REQUIREMENTS = {'models': [],
 'custom_nodes': ['ComfyUI-KJNodes',
                  'ComfyUI-VideoHelperSuite',
                  'ComfyUI-WanVideoWrapper',
                  'rgthree-comfy'],
 'custom_node_refs': [{'slug': 'ComfyUI-KJNodes',
                       'source': 'git',
                       'commit': 'b7646ad70a7daa7aeb919ca542274758d26ba2df',
                       'url': 'https://github.com/kijai/ComfyUI-KJNodes.git'},
                      {'slug': 'ComfyUI-VideoHelperSuite',
                       'source': 'git',
                       'url': 'https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite.git'},
                      {'slug': 'ComfyUI-WanVideoWrapper',
                       'source': 'git',
                       'commit': 'df8f3e49daaad117cf3090cc916c83f3d001494c',
                       'url': 'https://github.com/kijai/ComfyUI-WanVideoWrapper.git'},
                      {'slug': 'rgthree-comfy',
                       'source': 'git',
                       'url': 'https://github.com/rgthree/rgthree-comfy.git'}]}


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
        widget_0=20,
        widget_1=False,
        widget_2=False,
        widget_3=True,
        widget_4=0,
        widget_5=0,
        widget_6=False,
    )
    cliploader = _node(wf, 'CLIPLoader', '48',
        clip_name='umt5_xxl_fp16.safetensors',
        type='wan',
        device='default',
    )
    loadwanvideocliptextencoder = _node(wf, 'LoadWanVideoClipTextEncoder', '56',
        widget_0='open-clip-xlm-roberta-large-vit-huge-14_visual_fp16.safetensors',
        widget_1='fp16',
        widget_2='offload_device',
    )
    loadimage = _node(wf, 'LoadImage', '58',
        image='pasted/image (853).png',
        widget_1='image',
    )
    clipvisionloader = _node(wf, 'CLIPVisionLoader', '59',
        widget_0='clip_vision_h.safetensors',
    )
    loadimage_2 = _node(wf, 'LoadImage', '63',
        image='pasted/image (852).png',
        widget_1='image',
    )
    getnode = _node(wf, 'GetNode', '93',
        widget_0='start_image',
    )
    getnode_2 = _node(wf, 'GetNode', '94',
        widget_0='end_image',
    )
    wanvideoloraselect = _node(wf, 'WanVideoLoraSelect', '106',
        widget_0='Wan21_T2V_14B_lightx2v_cfg_step_distill_lora_rank32.safetensors',
        widget_1=1.2000000000000002,
        widget_2=False,
        widget_3=True,
    )
    wanvideomodelloader = _node(wf, 'WanVideoModelLoader', '22',
        widget_0='WanVideo\\Wan2_1-FLF2V-14B-720P_fp8_e4m3fn.safetensors',
        widget_1='fp16',
        widget_2='fp8_e4m3fn',
        widget_3='offload_device',
        widget_4='sdpa',
        block_swap_args=wanvideoblockswap.out(0),
        compile_args=wanvideotorchcompilesettings.out(0),
        lora=wanvideoloraselect.out(0),
    )
    cliptextencode = _node(wf, 'CLIPTextEncode', '49',
        text='CG动画风格，一只蓝色的小鸟从地面起飞，煽动翅膀。小鸟羽毛细腻，胸前有独特的花纹，背景是蓝天白云，阳光明媚。镜跟随小鸟向上移动，展现出小鸟飞翔的姿态和天空的广阔。近景，仰视视角',
        clip=cliploader.out(0),
    )
    cliptextencode_2 = _node(wf, 'CLIPTextEncode', '50',
        text='色调艳丽，过曝，静态，细节模糊不清，字幕，风格，作品，画作，画面，静止，整体发灰，最差质量，低质量，JPEG压缩残留，丑陋的，残缺的，多余的手指，画得不好的手部，画得不好的脸部，畸形的，毁容的，形态畸形的肢体，手指融合，静止不动的画面，杂乱的背景，三条腿，背景人很多，倒着走',
        clip=cliploader.out(0),
    )
    addlabel = _node(wf, 'AddLabel', '95',
        widget_0=10,
        widget_1=2,
        widget_2=48,
        widget_3=32,
        widget_4='white',
        widget_5='black',
        widget_6='FreeMono.ttf',
        widget_7='start_frame',
        widget_8='up',
        image=getnode.out(0),
    )
    addlabel_2 = _node(wf, 'AddLabel', '96',
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
    imageresizekjv2 = _node(wf, 'ImageResizeKJv2', '107',
        height=256,
        widget_0=256,
        widget_1=256,
        widget_2='lanczos',
        widget_3='crop',
        widget_4='0, 0, 0',
        widget_5='center',
        widget_6=16,
        widget_7='cpu',
        widget_8='<tr><td>Output: </td><td><b>1</b> x <b>640</b> x <b>640 | 4.69MB</b></td></tr>',
        width=256,
        image=loadimage_2.out(0),
    )
    wanvideotextencode = _node(wf, 'WanVideoTextEncode', '16',
        widget_0='CG动画风格，一只蓝色的小鸟从地面起飞，煽动翅膀。小鸟羽毛细腻，胸前有独特的花纹，背景是蓝天白云，阳光明媚。镜跟随小鸟向上移动，展现出小鸟飞翔的姿态和天空的广阔。近景，仰视视角',
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
    imageconcatmulti = _node(wf, 'ImageConcatMulti', '70',
        widget_0=2,
        widget_1='down',
        widget_2=True,
        widget_3=None,
        image_1=addlabel.out(0),
        image_2=addlabel_2.out(0),
    )
    setnode = _node(wf, 'SetNode', '91',
        widget_0='start_image',
        IMAGE=imageresizekjv2.out(0),
    )
    imageresizekjv2_2 = _node(wf, 'ImageResizeKJv2', '108',
        widget_0=256,
        widget_1=256,
        widget_2='lanczos',
        widget_3='crop',
        widget_4='0, 0, 0',
        widget_5='center',
        widget_6=16,
        widget_7='cpu',
        widget_8='<tr><td>Output: </td><td><b>1</b> x <b>640</b> x <b>640 | 4.69MB</b></td></tr>',
        height=imageresizekjv2.out(2),
        image=loadimage.out(0),
        width=imageresizekjv2.out(1),
    )
    setnode_2 = _node(wf, 'SetNode', '92',
        widget_0='end_image',
        IMAGE=imageresizekjv2_2.out(0),
    )
    wanvideoclipvisionencode = _node(wf, 'WanVideoClipVisionEncode', '88',
        widget_0=1,
        widget_1=1,
        widget_2='center',
        widget_3='concat',
        widget_4=True,
        widget_5=0,
        widget_6=0.5,
        clip_vision=clipvisionloader.out(0),
        image_1=setnode.out(0),
        image_2=setnode_2.out(0),
    )
    wanvideoimagetovideoencode = _node(wf, 'WanVideoImageToVideoEncode', '89',
        num_frames=5,
        widget_0=256,
        widget_1=256,
        widget_2=5,
        widget_3=0,
        widget_4=1,
        widget_5=True,
        widget_6=True,
        widget_7=True,
        widget_8=False,
        clip_embeds=wanvideoclipvisionencode.out(0),
        end_image=setnode_2.out(0),
        height=imageresizekjv2_2.out(2),
        start_image=setnode.out(0),
        vae=wanvideovaeloader.out(0),
        width=imageresizekjv2_2.out(1),
    )
    wanvideosampler = _node(wf, 'WanVideoSampler', '27',
        steps=1,
        widget_0=1,
        widget_1=1.0000000000000002,
        widget_10='comfy',
        widget_11=0,
        widget_12=-1,
        widget_13=False,
        widget_2=5.000000000000001,
        widget_3=43,
        widget_4='fixed',
        widget_5=True,
        widget_6='dpm++_sde',
        widget_7=0,
        widget_8=1,
        widget_9='',
        image_embeds=wanvideoimagetovideoencode.out(0),
        model=wanvideomodelloader.out(0),
        text_embeds=wanvideotextencode.out(0),
    )
    wanvideodecode = _node(wf, 'WanVideoDecode', '101',
        widget_0=False,
        widget_1=272,
        widget_2=272,
        widget_3=144,
        widget_4=128,
        widget_5='default',
        samples=wanvideosampler.out(0),
        vae=wanvideovaeloader.out(0),
    )
    getimagesizeandcount = _node(wf, 'GetImageSizeAndCount', '68',
        image=wanvideodecode.out(0),
    )
    emptyimage = _node(wf, 'EmptyImage', '97',
        widget_0=8,
        widget_1=512,
        widget_2=1,
        widget_3=0,
        height=getimagesizeandcount.out(2),
    )
    imageconcatmulti_2 = _node(wf, 'ImageConcatMulti', '71',
        widget_0=3,
        widget_1='left',
        widget_2=True,
        widget_3=None,
        image_1=getimagesizeandcount.out(0),
        image_2=emptyimage.out(0),
        image_3=imageconcatmulti.out(0),
    )
    vhs_videocombine = _node(wf, 'VHS_VideoCombine', '30',
        save_output=True,
        images=imageconcatmulti_2.out(0),
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

