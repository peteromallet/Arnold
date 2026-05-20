# vibecomfy: generated — converted by tools/convert_ready_templates.py
# Edits will be overwritten on regeneration. Add a `# vibecomfy: manual`
# marker on the first line if hand-editing is required.
"""Auto-generated ready_template — see tools/convert_ready_templates.py."""
from __future__ import annotations

from vibecomfy.workflow import VibeWorkflow, WorkflowSource
from vibecomfy.registry.ready_template import apply_ready_template_policy


READY_METADATA = {'model_assets': [],
 'unbound_inputs': {'seed': 4736},
 'ready_template': 'video/wanvideo_wrapper_22_5b_t2v_controlnet',
 'workflow_template': 'wanvideo_wrapper_22_5b_t2v_controlnet',
 'capability': 'text_to_video_controlnet',
 'source_role': 'materialized_ready_python_template',
 'source_workflow': 'workflow_corpus/custom_nodes/wanvideo_wrapper/kijai/wan22_5b_t2v_controlnet.json',
 'coverage_tier': 'supplemental',
 'approach': 'WanVideoWrapper 2.2 5B text-to-video ControlNet',
 'runtime_note': None,
 'discord_signal': None,
 'smoke_resolution': '256x256x5_frames'}

READY_REQUIREMENTS = {'models': [],
 'custom_nodes': ['ComfyUI-KJNodes', 'ComfyUI-VideoHelperSuite', 'ComfyUI-WanVideoWrapper'],
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
                       'url': 'https://github.com/kijai/ComfyUI-WanVideoWrapper.git'}]}


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
        widget_0='Wan2_2_VAE_bf16.safetensors',
        widget_1='bf16',
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
        widget_9=0,
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
    wanvideocontrolnetloader = _node(wf, 'WanVideoControlnetLoader', '103',
        widget_0='wan2.2-ti2v-5b-controlnet-depth-v1/diffusion_pytorch_model.safetensors',
        widget_1='bf16',
        widget_2='disabled',
        widget_3='main_device',
    )
    wanvideoenhanceavideo = _node(wf, 'WanVideoEnhanceAVideo', '107',
        widget_0=2,
        widget_1=0,
        widget_2=1,
    )
    intconstant = _node(wf, 'INTConstant', '113',
        widget_0=121,
    )
    intconstant_2 = _node(wf, 'INTConstant', '114',
        widget_0=704,
    )
    intconstant_3 = _node(wf, 'INTConstant', '115',
        widget_0=1280,
    )
    wanvideomodelloader = _node(wf, 'WanVideoModelLoader', '22',
        widget_0='Wan2_2-TI2V-5B-FastWanFullAttn_bf16.safetensors',
        widget_1='fp16',
        widget_2='disabled',
        widget_3='offload_device',
        widget_4='sdpa',
        compile_args=wanvideotorchcompilesettings.out(0),
    )
    vhs_loadvideo = _node(wf, 'VHS_LoadVideo', '98',
        video='wolf_interpolated.mp4',
        frame_load_cap=intconstant.out(0),
    )
    wanvideoemptyembeds = _node(wf, 'WanVideoEmptyEmbeds', '106',
        num_frames=5,
        widget_0=256,
        widget_1=256,
        widget_2=5,
        height=intconstant_2.out(0),
        width=intconstant_3.out(0),
    )
    imageresizekjv2 = _node(wf, 'ImageResizeKJv2', '101',
        widget_0=256,
        widget_1=256,
        widget_2='nearest-exact',
        widget_3='stretch',
        widget_4='0, 0, 0',
        widget_5='center',
        widget_6=2,
        widget_7='cpu',
        height=intconstant_2.out(0),
        image=vhs_loadvideo.out(0),
        width=intconstant_3.out(0),
    )
    midas_depthmappreprocessor = _node(wf, 'MiDaS-DepthMapPreprocessor', '104',
        widget_0=6.283185307179586,
        widget_1=0.1,
        widget_2=512,
        image=imageresizekjv2.out(0),
    )
    imageresizekjv2_2 = _node(wf, 'ImageResizeKJv2', '109',
        widget_0=256,
        widget_1=256,
        widget_2='nearest-exact',
        widget_3='stretch',
        widget_4='0, 0, 0',
        widget_5='center',
        widget_6=2,
        widget_7='cpu',
        height=intconstant_2.out(0),
        image=midas_depthmappreprocessor.out(0),
        width=intconstant_3.out(0),
    )
    wanvideocontrolnet = _node(wf, 'WanVideoControlnet', '105',
        widget_0=1,
        widget_1=3,
        widget_2=0,
        widget_3=1,
        control_images=imageresizekjv2_2.out(0),
        controlnet=wanvideocontrolnetloader.out(0),
        model=wanvideomodelloader.out(0),
    )
    previewanimation = _node(wf, 'PreviewAnimation', '112',
        widget_0=24,
        images=imageresizekjv2_2.out(0),
    )
    wanvideotextencode = _node(wf, 'WanVideoTextEncode', '16',
        widget_0="Close-up shot with soft lighting, focusing sharply on the lower half of a young woman's face. Her lips are slightly parted as she blows an enormous bubblegum bubble. The bubble is semi-transparent, shimmering gently under the light, and surprisingly contains a miniature aquarium inside, where two orange-and-white goldfish slowly swim, their fins delicately fluttering as if in an aquatic universe. The background is a pure light blue color.",
        widget_1='Bright tones, overexposed, static, blurred details, subtitles, style, works, paintings, images, static, overall gray, worst quality, low quality, JPEG compression residue, ugly, incomplete, extra fingers, poorly drawn hands, poorly drawn faces, deformed, disfigured, misshapen limbs, fused fingers, still picture, messy background, three legs, many people in the background, walking backwards"',
        widget_2=True,
        widget_3=False,
        widget_4='gpu',
        model_to_offload=wanvideocontrolnet.out(0),
        t5=loadwanvideot5textencoder.out(0),
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
        feta_args=wanvideoenhanceavideo.out(0),
        image_embeds=wanvideoemptyembeds.out(0),
        model=wanvideocontrolnet.out(0),
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

