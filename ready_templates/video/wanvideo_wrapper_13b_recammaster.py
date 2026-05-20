# vibecomfy: generated — converted by tools/convert_ready_templates.py
# Edits will be overwritten on regeneration. Add a `# vibecomfy: manual`
# marker on the first line if hand-editing is required.
"""Auto-generated ready_template — see tools/convert_ready_templates.py."""
from __future__ import annotations

from vibecomfy.workflow import VibeWorkflow, WorkflowSource
from vibecomfy.registry.ready_template import apply_ready_template_policy


READY_METADATA = {'model_assets': [],
 'unbound_inputs': {'seed': 4285},
 'ready_template': 'video/wanvideo_wrapper_13b_recammaster',
 'workflow_template': 'wanvideo_wrapper_13b_recammaster',
 'capability': 'camera_control_video',
 'source_role': 'materialized_ready_python_template',
 'source_workflow': 'workflow_corpus/custom_nodes/wanvideo_wrapper/kijai/wan13b_recammaster.json',
 'coverage_tier': 'supplemental',
 'approach': 'ReCamMaster camera-control workflow',
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
    wanvideomodelloader = _node(wf, 'WanVideoModelLoader', '22',
        widget_0='WanVideo\\Wan2_1_kwai_recammaster_1_3B_step20000_bf16.safetensors',
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
        widget_0=20,
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
        widget_0=0.10000000000000002,
        widget_1=6,
        widget_2=-1,
        widget_3='offload_device',
        widget_4='true',
        widget_5='e0',
    )
    downloadandloadflorence2model = _node(wf, 'DownloadAndLoadFlorence2Model', '124',
        widget_0='MiaoshouAI/Florence-2-base-PromptGen-v2.0',
        widget_1='fp16',
        widget_2='sdpa',
    )
    wanvideoexperimentalargs = _node(wf, 'WanVideoExperimentalArgs', '127',
        widget_0='',
        widget_1=True,
        widget_2=False,
        widget_3=0,
    )
    vhs_loadvideo = _node(wf, 'VHS_LoadVideo', '128',
        video='wolf_interpolated.mp4',
    )
    getnode = _node(wf, 'GetNode', '141',
        widget_0='WanModel',
    )
    getnode_2 = _node(wf, 'GetNode', '143',
        widget_0='TextEmbeds',
    )
    getnode_3 = _node(wf, 'GetNode', '145',
        widget_0='WanVAE',
    )
    getnode_4 = _node(wf, 'GetNode', '146',
        widget_0='WanVAE',
    )
    getnode_5 = _node(wf, 'GetNode', '157',
        widget_0='InputLatents',
    )
    wanvideorecammastergenerateorbitcamera = _node(wf, 'WanVideoReCamMasterGenerateOrbitCamera', '206',
        widget_0=81,
        widget_1=90,
    )
    cliptextencode = _node(wf, 'CLIPTextEncode', '49',
        text="high quality nature video featuring a red panda balancing on a bamboo stem while a bird lands on it's head, on the background there is a waterfall",
        clip=cliploader.out(0),
    )
    cliptextencode_2 = _node(wf, 'CLIPTextEncode', '50',
        text='色调艳丽，过曝，静态，细节模糊不清，字幕，风格，作品，画作，画面，静止，整体发灰，最差质量，低质量，JPEG压缩残留，丑陋的，残缺的，多余的手指，画得不好的手部，画得不好的脸部，畸形的，毁容的，形态畸形的肢体，手指融合，静止不动的画面，杂乱的背景，三条腿，背景人很多，倒着走',
        clip=cliploader.out(0),
    )
    getimagesizeandcount = _node(wf, 'GetImageSizeAndCount', '129',
        image=vhs_loadvideo.out(0),
    )
    setnode = _node(wf, 'SetNode', '140',
        widget_0='WanModel',
        WANVIDEOMODEL=wanvideomodelloader.out(0),
    )
    setnode_3 = _node(wf, 'SetNode', '144',
        widget_0='WanVAE',
        WANVAE=wanvideovaeloader.out(0),
    )
    wanvideorecammasterdefaultcamera = _node(wf, 'WanVideoReCamMasterDefaultCamera', '205',
        widget_0='pan_right',
        latents=getnode_5.out(0),
    )
    wanvideotextembedbridge = _node(wf, 'WanVideoTextEmbedBridge', '46',
        negative=cliptextencode_2.out(0),
        positive=cliptextencode.out(0),
    )
    wanvideorecammastercameraembed = _node(wf, 'WanVideoReCamMasterCameraEmbed', '56',
        camera_poses=wanvideorecammasterdefaultcamera.out(0),
        latents=getnode_5.out(0),
    )
    imageresizekj = _node(wf, 'ImageResizeKJ', '59',
        widget_0=832,
        widget_1=480,
        widget_2='lanczos',
        widget_3=False,
        widget_4=16,
        widget_5='center',
        image=getimagesizeandcount.out(0),
    )
    widgettostring = _node(wf, 'WidgetToString', '74',
        widget_0=0,
        widget_1='camera_type',
        widget_2=False,
        widget_3='',
        widget_4=2,
        any_input=wanvideorecammasterdefaultcamera.out(0),
    )
    getimagerangefrombatch = _node(wf, 'GetImageRangeFromBatch', '130',
        widget_0=0,
        widget_1=1,
        images=imageresizekj.out(0),
    )
    recammasterposevisualizer = _node(wf, 'ReCamMasterPoseVisualizer', '138',
        widget_0=0.10000000000000002,
        widget_1=0.20000000000000004,
        widget_2=0.4000000000000001,
        widget_3=0.5000000000000001,
        camera_poses=wanvideorecammastercameraembed.out(1),
    )
    setnode_4 = _node(wf, 'SetNode', '147',
        widget_0='InputVideo',
        IMAGE=imageresizekj.out(0),
    )
    wanvideosampler = _node(wf, 'WanVideoSampler', '155',
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
        widget_9=False,
        cache_args=wanvideoteacache.out(0),
        experimental_args=wanvideoexperimentalargs.out(0),
        image_embeds=wanvideorecammastercameraembed.out(0),
        model=getnode.out(0),
        text_embeds=getnode_2.out(0),
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
    wanvideoencode = _node(wf, 'WanVideoEncode', '58',
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
    florence2run = _node(wf, 'Florence2Run', '123',
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
        florence2_model=downloadandloadflorence2model.out(0),
        image=getimagerangefrombatch.out(0),
    )
    previewimage = _node(wf, 'PreviewImage', '131',
        images=getimagerangefrombatch.out(0),
    )
    previewimage_2 = _node(wf, 'PreviewImage', '139',
        images=recammasterposevisualizer.out(0),
    )
    wanvideotextencode = _node(wf, 'WanVideoTextEncode', '16',
        widget_0='video of an autumnal forest scene',
        widget_1='色调艳丽，过曝，静态，细节模糊不清，字幕，风格，作品，画作，画面，静止，整体发灰，最差质量，低质量，JPEG压缩残留，丑陋的，残缺的，多余的手指，画得不好的手部，画得不好的脸部，畸形的，毁容的，形态畸形的肢体，手指融合，静止不动的画面，杂乱的背景，三条腿，背景人很多，倒着走',
        widget_2=True,
        positive_prompt=florence2run.out(2),
        t5=loadwanvideot5textencoder.out(0),
    )
    addlabel = _node(wf, 'AddLabel', '122',
        widget_0=10,
        widget_1=2,
        widget_2=48,
        widget_3=32,
        widget_4='white',
        widget_5='black',
        widget_6='FreeMonoBoldOblique.otf',
        widget_7='input',
        widget_8='up',
        image=wanvideodecode.out(0),
        text=widgettostring.out(0),
    )
    showtext_pysssss = _node(wf, 'ShowText|pysssss', '125',
        widget_0='A man in a suit and tie walking down a hallway. He has a friendly expression and is looking directly at the camera. The hallway has beige walls adorned with framed black and white photographs. There is a door on the left side of the hallway and a poster on the wall. The lighting is soft and natural. The image is high quality and has a watermark in the bottom right corner.',
        widget_1='A man in a suit and tie walking down a hallway. He has a friendly expression and is looking directly at the camera. The hallway has beige walls adorned with framed black and white photographs. There is a door on the left side of the hallway and a poster on the wall. The lighting is soft and natural. The image is high quality and has a watermark in the bottom right corner.',
        text=florence2run.out(2),
    )
    setnode_5 = _node(wf, 'SetNode', '156',
        widget_0='InputLatents',
        LATENT=wanvideoencode.out(0),
    )
    vhs_videocombine = _node(wf, 'VHS_VideoCombine', '30',
        save_output=True,
        images=addlabel.out(0),
    )
    setnode_2 = _node(wf, 'SetNode', '142',
        widget_0='TextEmbeds',
        WANVIDEOTEXTEMBEDS=wanvideotextencode.out(0),
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

