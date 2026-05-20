# vibecomfy: generated — converted by tools/convert_ready_templates.py
# Edits will be overwritten on regeneration. Add a `# vibecomfy: manual`
# marker on the first line if hand-editing is required.
"""Auto-generated ready_template — see tools/convert_ready_templates.py."""
from __future__ import annotations

from vibecomfy.workflow import VibeWorkflow, WorkflowSource
from vibecomfy.registry.ready_template import apply_ready_template_policy


READY_METADATA = {'model_assets': [],
 'unbound_inputs': {'seed': 4971},
 'ready_template': 'video/wanvideo_wrapper_21_14b_v2v_infinitetalk',
 'workflow_template': 'wanvideo_wrapper_21_14b_v2v_infinitetalk',
 'capability': 'video_to_video_talking_avatar',
 'source_role': 'materialized_ready_python_template',
 'source_workflow': 'workflow_corpus/custom_nodes/wanvideo_wrapper/kijai/wan21_14b_v2v_infinitetalk.json',
 'coverage_tier': 'supplemental',
 'approach': 'InfiniteTalk video-to-video talking avatar',
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

    multitalkmodelloader = _node(wf, 'MultiTalkModelLoader', '120',
        widget_0='WanVideo\\InfiniteTalk\\InfiniteTalk\\Wan2_1-InfiniteTalk_Single_Q8.gguf',
    )
    loadaudio = _node(wf, 'LoadAudio', '125',
        audio='one-does-not-simply-walk-into-mordor-its-black-gates-are-guarded-by-more-than-just-orcs.mp3',
        widget_1=None,
        widget_2=None,
    )
    wanvideovaeloader = _node(wf, 'WanVideoVAELoader', '129',
        widget_0='wanvideo\\Wan2_1_VAE_bf16.safetensors',
        widget_1='bf16',
    )
    wanvideoblockswap = _node(wf, 'WanVideoBlockSwap', '134',
        widget_0=20,
        widget_1=False,
        widget_2=False,
        widget_3=True,
        widget_4=0,
        widget_5=1,
        widget_6=False,
    )
    downloadandloadwav2vecmodel = _node(wf, 'DownloadAndLoadWav2VecModel', '137',
        widget_0='TencentGameMate/chinese-wav2vec2-base',
        widget_1='fp16',
        widget_2='main_device',
    )
    wanvideoloraselect = _node(wf, 'WanVideoLoraSelect', '138',
        widget_0='WanVideo\\Lightx2v\\lightx2v_I2V_14B_480p_cfg_step_distill_rank64_bf16.safetensors',
        widget_1=1,
        widget_2=False,
        widget_3=False,
    )
    wanvideotorchcompilesettings = _node(wf, 'WanVideoTorchCompileSettings', '177',
        widget_0='inductor',
        widget_1=False,
        widget_2='default',
        widget_3=False,
        widget_4=64,
        widget_5=True,
        widget_6=128,
    )
    clipvisionloader = _node(wf, 'CLIPVisionLoader', '238',
        widget_0='clip_vision_h.safetensors',
    )
    wanvideotextencodecached = _node(wf, 'WanVideoTextEncodeCached', '241',
        widget_0='umt5-xxl-enc-bf16.safetensors',
        widget_1='bf16',
        widget_2='a woman is singing a lullaby',
        widget_3='bright tones, overexposed, static, blurred details, subtitles, style, works, paintings, images, static, overall gray, worst quality, low quality, JPEG compression residue, ugly, incomplete, extra fingers, poorly drawn hands, poorly drawn faces, deformed, disfigured, misshapen limbs, fused fingers, still picture, messy background, three legs, many people in the background, walking backwards',
        widget_4='disabled',
        widget_5=False,
        widget_6='gpu',
    )
    getnode = _node(wf, 'GetNode', '242',
        widget_0='VAE',
    )
    getnode_2 = _node(wf, 'GetNode', '243',
        widget_0='VAE',
    )
    getnode_3 = _node(wf, 'GetNode', '244',
        widget_0='VAE',
    )
    intconstant = _node(wf, 'INTConstant', '245',
        widget_0=640,
    )
    intconstant_2 = _node(wf, 'INTConstant', '246',
        widget_0=640,
    )
    getnode_4 = _node(wf, 'GetNode', '249',
        widget_0='height',
    )
    getnode_5 = _node(wf, 'GetNode', '250',
        widget_0='width',
    )
    getnode_6 = _node(wf, 'GetNode', '254',
        widget_0='input_audio',
    )
    getnode_7 = _node(wf, 'GetNode', '261',
        widget_0='wanmodel',
    )
    getnode_8 = _node(wf, 'GetNode', '265',
        widget_0='clip_vision_model',
    )
    intconstant_3 = _node(wf, 'INTConstant', '270',
        widget_0=1000,
    )
    getnode_9 = _node(wf, 'GetNode', '272',
        widget_0='max_frames',
    )
    melbandroformermodelloader = _node(wf, 'MelBandRoFormerModelLoader', '303',
        widget_0='MelBandRoFormer\\MelBandRoformer_fp16.safetensors',
    )
    wav2vecmodelloader = _node(wf, 'Wav2VecModelLoader', '306',
        widget_0='wav2vec2-chinese-base_fp16.safetensors',
        widget_1='fp16',
        widget_2='main_device',
    )
    wanvideomodelloader = _node(wf, 'WanVideoModelLoader', '122',
        widget_0='WanVideo\\wan2.1-i2v-14b-480p-Q8_0.gguf',
        widget_1='fp16',
        widget_2='disabled',
        widget_3='offload_device',
        widget_4='sdpa',
        block_swap_args=wanvideoblockswap.out(0),
        lora=wanvideoloraselect.out(0),
        multitalk_model=multitalkmodelloader.out(0),
    )
    vhs_loadvideo = _node(wf, 'VHS_LoadVideo', '228',
        video='wolf_interpolated.mp4',
        custom_height=getnode_4.out(0),
        custom_width=getnode_5.out(0),
    )
    setnode = _node(wf, 'SetNode', '240',
        widget_0='VAE',
        WANVAE=wanvideovaeloader.out(0),
    )
    setnode_2 = _node(wf, 'SetNode', '247',
        widget_0='width',
        INT=intconstant.out(0),
    )
    setnode_3 = _node(wf, 'SetNode', '248',
        widget_0='height',
        INT=intconstant_2.out(0),
    )
    setnode_4 = _node(wf, 'SetNode', '253',
        widget_0='input_audio',
        AUDIO=loadaudio.out(0),
    )
    setnode_6 = _node(wf, 'SetNode', '264',
        widget_0='clip_vision_model',
        CLIP_VISION=clipvisionloader.out(0),
    )
    setnode_7 = _node(wf, 'SetNode', '271',
        widget_0='max_frames',
        INT=intconstant_3.out(0),
    )
    imageresizekjv2 = _node(wf, 'ImageResizeKJv2', '230',
        widget_0=256,
        widget_1=256,
        widget_2='lanczos',
        widget_3='crop',
        widget_4='0, 0, 0',
        widget_5='center',
        widget_6=16,
        widget_7='cpu',
        height=getnode_4.out(0),
        image=vhs_loadvideo.out(0),
        width=getnode_5.out(0),
    )
    setnode_5 = _node(wf, 'SetNode', '260',
        widget_0='wanmodel',
        WANVIDEOMODEL=wanvideomodelloader.out(0),
    )
    melbandroformersampler = _node(wf, 'MelBandRoFormerSampler', '304',
        audio=setnode_4.out(0),
        model=melbandroformermodelloader.out(0),
    )
    multitalkwav2vecembeds = _node(wf, 'MultiTalkWav2VecEmbeds', '194',
        widget_0=True,
        widget_1=400,
        widget_2=25,
        widget_3=1.5,
        widget_4=1,
        widget_5='para',
        audio_1=melbandroformersampler.out(0),
        num_frames=getnode_9.out(0),
        wav2vec_model=downloadandloadwav2vecmodel.out(0),
    )
    wanvideoencode = _node(wf, 'WanVideoEncode', '229',
        widget_0=False,
        widget_1=272,
        widget_2=272,
        widget_3=144,
        widget_4=128,
        widget_5=0,
        widget_6=1,
        image=imageresizekjv2.out(0),
        vae=getnode_2.out(0),
    )
    getimagerangefrombatch = _node(wf, 'GetImageRangeFromBatch', '231',
        widget_0=0,
        widget_1=1,
        images=imageresizekjv2.out(0),
    )
    getimagesizeandcount = _node(wf, 'GetImageSizeAndCount', '291',
        image=getimagerangefrombatch.out(0),
    )
    setnode_8 = _node(wf, 'SetNode', '294',
        widget_0='actual_audio_frames',
        INT=multitalkwav2vecembeds.out(2),
    )
    wanvideoclipvisionencode = _node(wf, 'WanVideoClipVisionEncode', '237',
        widget_0=1,
        widget_1=1,
        widget_2='center',
        widget_3='average',
        widget_4=True,
        widget_5=0,
        widget_6=0.5,
        clip_vision=getnode_8.out(0),
        image_1=getimagesizeandcount.out(0),
    )
    previewany = _node(wf, 'PreviewAny', '293',
        source=setnode_8.out(0),
    )
    wanvideoimagetovideomultitalk = _node(wf, 'WanVideoImageToVideoMultiTalk', '192',
        widget_0=832,
        widget_1=480,
        widget_2=81,
        widget_3=9,
        widget_4=False,
        widget_5='disabled',
        widget_6=False,
        widget_7='infinitetalk',
        clip_embeds=wanvideoclipvisionencode.out(0),
        height=getimagesizeandcount.out(2),
        start_image=getimagesizeandcount.out(0),
        vae=getnode_3.out(0),
        width=getimagesizeandcount.out(1),
    )
    wanvideosampler = _node(wf, 'WanVideoSampler', '128',
        steps=1,
        widget_0=1,
        widget_1=1.0000000000000002,
        widget_10='comfy',
        widget_11=2,
        widget_12=-1,
        widget_13=True,
        widget_2=11.000000000000002,
        widget_3=2,
        widget_4='fixed',
        widget_5=True,
        widget_6='dpm++_sde',
        widget_7=0,
        widget_8=1,
        widget_9=False,
        image_embeds=wanvideoimagetovideomultitalk.out(0),
        model=getnode_7.out(0),
        multitalk_embeds=multitalkwav2vecembeds.out(0),
        samples=wanvideoencode.out(0),
        text_embeds=wanvideotextencodecached.out(0),
    )
    wanvideodecode = _node(wf, 'WanVideoDecode', '130',
        widget_0=False,
        widget_1=272,
        widget_2=272,
        widget_3=144,
        widget_4=128,
        widget_5='default',
        samples=wanvideosampler.out(0),
        vae=getnode.out(0),
    )
    getimagesizeandcount_2 = _node(wf, 'GetImageSizeAndCount', '300',
        image=wanvideodecode.out(0),
    )
    getimagerangefrombatch_2 = _node(wf, 'GetImageRangeFromBatch', '301',
        widget_0=0,
        widget_1=1,
        images=getimagesizeandcount_2.out(0),
        num_frames=getimagesizeandcount_2.out(3),
    )
    imageconcatmulti = _node(wf, 'ImageConcatMulti', '299',
        widget_0=2,
        widget_1='left',
        widget_2=False,
        widget_3=None,
        image_1=getimagerangefrombatch_2.out(0),
        image_2=imageresizekjv2.out(0),
    )
    vhs_videocombine = _node(wf, 'VHS_VideoCombine', '131',
        save_output=True,
        audio=getnode_6.out(0),
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

