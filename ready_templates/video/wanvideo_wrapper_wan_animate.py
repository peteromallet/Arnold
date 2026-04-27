# vibecomfy: generated — converted by tools/convert_ready_templates.py
# Edits will be overwritten on regeneration. Add a `# vibecomfy: manual`
# marker on the first line if hand-editing is required.
"""Auto-generated ready_template — see tools/convert_ready_templates.py."""
from __future__ import annotations

from vibecomfy.workflow import VibeWorkflow, WorkflowSource
from vibecomfy.registry.ready_template import apply_ready_template_policy


READY_METADATA = {'model_assets': [],
 'unbound_inputs': {'seed': 3976},
 'ready_template': 'video/wanvideo_wrapper_wan_animate',
 'workflow_template': 'wanvideo_wrapper_wan_animate',
 'capability': 'animate_reference_video',
 'source_role': 'materialized_ready_python_template',
 'source_workflow': 'workflow_corpus/custom_nodes/wanvideo_wrapper/kijai/wan_animate.json',
 'coverage_tier': 'supplemental',
 'approach': 'WanAnimate reference animation',
 'runtime_note': None,
 'discord_signal': None,
 'smoke_resolution': '256x256x5_frames'}

READY_REQUIREMENTS = {'models': [],
 'custom_nodes': ['ComfyUI-KJNodes',
                  'ComfyUI-VideoHelperSuite',
                  'ComfyUI-WanVideoWrapper',
                  'comfyui_controlnet_aux']}


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
    wanvideoblockswap = _node(wf, 'WanVideoBlockSwap', '51',
        widget_0=25,
        widget_1=False,
        widget_2=False,
        widget_3=True,
        widget_4=0,
        widget_5=1,
        widget_6=False,
    )
    loadimage = _node(wf, 'LoadImage', '57',
        image='refer.jpeg',
        widget_1='image',
    )
    wanvideotextencodecached = _node(wf, 'WanVideoTextEncodeCached', '65',
        widget_0='umt5-xxl-enc-bf16.safetensors',
        widget_1='bf16',
        widget_2='man is walking, style is soft 3D render style, night time, moonlight',
        widget_3='色调艳丽，过曝，静态，细节模糊不清，字幕，风格，作品，画作，画面，静止，整体发灰，最差质量，低质量，JPEG压缩残留，丑陋的，残缺的，多余的手指，画得不好的手部，画得不好的脸部，畸形的，毁容的，形态畸形的肢体，手指融合，静止不动的画面，杂乱的背景，三条腿，背景人很多，倒着走',
        widget_4='disabled',
        widget_5=False,
        widget_6='gpu',
    )
    clipvisionloader = _node(wf, 'CLIPVisionLoader', '71',
        widget_0='clip_vision_h.safetensors',
    )
    downloadandloadsam2model = _node(wf, 'DownloadAndLoadSAM2Model', '102',
        widget_0='sam2_hiera_base_plus.safetensors',
        widget_1='video',
        widget_2='cuda',
        widget_3='fp16',
    )
    wanvideocontextoptions = _node(wf, 'WanVideoContextOptions', '110',
        widget_0='static_standard',
        widget_1=81,
        widget_2=4,
        widget_3=32,
        widget_4=True,
        widget_5=False,
        widget_6='linear',
    )
    getnode = _node(wf, 'GetNode', '131',
        widget_0='background_image',
    )
    getnode_2 = _node(wf, 'GetNode', '133',
        widget_0='reference_image',
    )
    getnode_3 = _node(wf, 'GetNode', '134',
        widget_0='reference_image',
    )
    getnode_4 = _node(wf, 'GetNode', '137',
        widget_0='face_images',
    )
    getnode_5 = _node(wf, 'GetNode', '138',
        widget_0='face_images',
    )
    getnode_6 = _node(wf, 'GetNode', '140',
        widget_0='pose_images',
    )
    getnode_7 = _node(wf, 'GetNode', '141',
        widget_0='pose_images',
    )
    getnode_8 = _node(wf, 'GetNode', '143',
        widget_0='mask',
    )
    getnode_9 = _node(wf, 'GetNode', '145',
        widget_0='input_video',
    )
    getnode_10 = _node(wf, 'GetNode', '146',
        widget_0='input_video',
    )
    reroute = _node(wf, 'Reroute', '147')
    getnode_11 = _node(wf, 'GetNode', '149',
        widget_0='input_audio',
    )
    intconstant = _node(wf, 'INTConstant', '150',
        widget_0=832,
    )
    intconstant_2 = _node(wf, 'INTConstant', '151',
        widget_0=480,
    )
    getnode_12 = _node(wf, 'GetNode', '155',
        widget_0='width',
    )
    getnode_13 = _node(wf, 'GetNode', '156',
        widget_0='height',
    )
    getnode_14 = _node(wf, 'GetNode', '158',
        widget_0='frame_count',
    )
    getnode_15 = _node(wf, 'GetNode', '162',
        widget_0='VAE',
    )
    getnode_16 = _node(wf, 'GetNode', '163',
        widget_0='VAE',
    )
    wanvideoloraselectmulti = _node(wf, 'WanVideoLoraSelectMulti', '171',
        widget_0='WanVideo\\WanAnimate_relight_lora_fp16.safetensors',
        widget_1=1,
        widget_10=False,
        widget_11=False,
        widget_2='WanVideo\\Lightx2v\\lightx2v_I2V_14B_480p_cfg_step_distill_rank64_bf16.safetensors',
        widget_3=1.2,
        widget_4='none',
        widget_5=1,
        widget_6='none',
        widget_7=1,
        widget_8='none',
        widget_9=1,
    )
    wanvideomodelloader = _node(wf, 'WanVideoModelLoader', '22',
        widget_0='WanVideo\\2_2\\Wan2_2-Animate-14B_fp8_e4m3fn_scaled_KJ.safetensors',
        widget_1='fp16',
        widget_2='disabled',
        widget_3='offload_device',
        widget_4='sdpa',
        compile_args=wanvideotorchcompilesettings.out(0),
    )
    vhs_loadvideo = _node(wf, 'VHS_LoadVideo', '63',
        video='wolf_interpolated.mp4',
        custom_height=intconstant_2.out(0),
        custom_width=intconstant.out(0),
    )
    imageresizekjv2 = _node(wf, 'ImageResizeKJv2', '64',
        widget_0=256,
        widget_1=256,
        widget_2='lanczos',
        widget_3='pad_edge_pixel',
        widget_4='0, 0, 0',
        widget_5='top',
        widget_6=16,
        widget_7='cpu',
        widget_8='<tr><td>Output: </td><td><b>1</b> x <b>832</b> x <b>480 | 4.57MB</b></td></tr>',
        height=intconstant_2.out(0),
        image=loadimage.out(0),
        width=intconstant.out(0),
    )
    wanvideoclipvisionencode = _node(wf, 'WanVideoClipVisionEncode', '70',
        widget_0=1,
        widget_1=1,
        widget_2='center',
        widget_3='average',
        widget_4=True,
        widget_5=0,
        widget_6=0.5,
        clip_vision=clipvisionloader.out(0),
        image_1=getnode_2.out(0),
    )
    imageconcatmulti_2 = _node(wf, 'ImageConcatMulti', '77',
        widget_0=4,
        widget_1='down',
        widget_2=True,
        widget_3=None,
        image_1=getnode_3.out(0),
        image_2=getnode_4.out(0),
        image_3=getnode_6.out(0),
        image_4=getnode_9.out(0),
    )
    pixelperfectresolution = _node(wf, 'PixelPerfectResolution', '152',
        widget_0=512,
        widget_1=512,
        widget_2='Just Resize',
        image_gen_height=intconstant_2.out(0),
        image_gen_width=intconstant.out(0),
        original_image=reroute.out(0),
    )
    setnode_8 = _node(wf, 'SetNode', '153',
        widget_0='width',
        INT=intconstant.out(0),
    )
    setnode_9 = _node(wf, 'SetNode', '154',
        widget_0='height',
        INT=intconstant_2.out(0),
    )
    setnode_11 = _node(wf, 'SetNode', '161',
        widget_0='VAE',
        WANVAE=wanvideovaeloader.out(0),
    )
    wanvideosetloras = _node(wf, 'WanVideoSetLoRAs', '48',
        lora=wanvideoloraselectmulti.out(0),
        model=wanvideomodelloader.out(0),
    )
    wanvideoanimateembeds = _node(wf, 'WanVideoAnimateEmbeds', '62',
        widget_0=832,
        widget_1=480,
        widget_2=501,
        widget_3=False,
        widget_4=77,
        widget_5='disabled',
        widget_6=1,
        widget_7=1,
        widget_8=False,
        bg_images=getnode.out(0),
        clip_embeds=wanvideoclipvisionencode.out(0),
        face_images=getnode_5.out(0),
        height=getnode_13.out(0),
        mask=getnode_8.out(0),
        num_frames=getnode_14.out(0),
        pose_images=getnode_7.out(0),
        ref_images=getnode_2.out(0),
        vae=getnode_16.out(0),
        width=getnode_12.out(0),
    )
    dwpreprocessor = _node(wf, 'DWPreprocessor', '73',
        widget_0='disable',
        widget_1='enable',
        widget_2='disable',
        widget_3=960,
        widget_4='yolox_l.torchscript.pt',
        widget_5='dw-ll_ucoco_384_bs5.torchscript.pt',
        widget_6='disable',
        image=reroute.out(0),
        resolution=pixelperfectresolution.out(0),
    )
    setnode = _node(wf, 'SetNode', '128',
        widget_0='reference_image',
        IMAGE=imageresizekjv2.out(0),
    )
    setnode_6 = _node(wf, 'SetNode', '144',
        widget_0='input_video',
        IMAGE=vhs_loadvideo.out(0),
    )
    setnode_7 = _node(wf, 'SetNode', '148',
        widget_0='input_audio',
        AUDIO=vhs_loadvideo.out(2),
    )
    setnode_10 = _node(wf, 'SetNode', '157',
        widget_0='frame_count',
        INT=vhs_loadvideo.out(1),
    )
    wanvideosetblockswap = _node(wf, 'WanVideoSetBlockSwap', '50',
        block_swap_args=wanvideoblockswap.out(0),
        model=wanvideosetloras.out(0),
    )
    pointseditor = _node(wf, 'PointsEditor', '107',
        widget_0='{"positive":[{"x":483.34844284815,"y":333.283583335728},{"x":479.85856239437277,"y":158.78956064686517}],"negative":[{"x":0,"y":0}]}',
        widget_1='[{"x":483.34844284815,"y":333.283583335728},{"x":479.85856239437277,"y":158.78956064686517}]',
        widget_10=None,
        widget_2='[{"x":0,"y":0}]',
        widget_3='[{}]',
        widget_4='[{}]',
        widget_5='xyxy',
        widget_6=832,
        widget_7=480,
        widget_8=False,
        widget_9='',
        bg_image=setnode_6.out(0),
    )
    facemaskfromposekeypoints = _node(wf, 'FaceMaskFromPoseKeypoints', '120',
        widget_0=0,
        pose_kps=dwpreprocessor.out(1),
    )
    setnode_4 = _node(wf, 'SetNode', '139',
        widget_0='pose_images',
        IMAGE=dwpreprocessor.out(0),
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
        widget_3=42,
        widget_4='fixed',
        widget_5=True,
        widget_6='dpm++_sde',
        widget_7=0,
        widget_8=1,
        widget_9='',
        image_embeds=wanvideoanimateembeds.out(0),
        model=wanvideosetblockswap.out(0),
        text_embeds=wanvideotextencodecached.out(0),
    )
    imagecropbymaskandresize = _node(wf, 'ImageCropByMaskAndResize', '96',
        widget_0=512,
        widget_1=0,
        widget_2=128,
        widget_3=512,
        image=reroute.out(0),
        mask=facemaskfromposekeypoints.out(0),
    )
    sam2segmentation = _node(wf, 'Sam2Segmentation', '104',
        widget_0=False,
        widget_1=False,
        coordinates_positive=pointseditor.out(0),
        image=setnode_6.out(0),
        sam2_model=downloadandloadsam2model.out(0),
    )
    wanvideodecode = _node(wf, 'WanVideoDecode', '28',
        widget_0=False,
        widget_1=272,
        widget_2=272,
        widget_3=144,
        widget_4=128,
        widget_5='default',
        samples=wanvideosampler.out(0),
        vae=getnode_15.out(0),
    )
    growmask = _node(wf, 'GrowMask', '100',
        widget_0=10,
        widget_1=True,
        mask=sam2segmentation.out(0),
    )
    setnode_3 = _node(wf, 'SetNode', '135',
        widget_0='face_images',
        IMAGE=imagecropbymaskandresize.out(0),
    )
    getimagesizeandcount = _node(wf, 'GetImageSizeAndCount', '42',
        image=wanvideodecode.out(0),
    )
    blockifymask = _node(wf, 'BlockifyMask', '108',
        widget_0=32,
        masks=growmask.out(0),
    )
    vhs_videocombine_3 = _node(wf, 'VHS_VideoCombine', '112',
        save_output=True,
        images=setnode_3.out(0),
    )
    imageconcatmulti = _node(wf, 'ImageConcatMulti', '66',
        widget_0=2,
        widget_1='left',
        widget_2=True,
        widget_3=None,
        image_1=getimagesizeandcount.out(0),
        image_2=imageconcatmulti_2.out(0),
    )
    setnode_5 = _node(wf, 'SetNode', '142',
        widget_0='mask',
        MASK=blockifymask.out(0),
    )
    vhs_videocombine = _node(wf, 'VHS_VideoCombine', '30',
        save_output=True,
        audio=getnode_11.out(0),
        images=imageconcatmulti.out(0),
    )
    drawmaskonimage = _node(wf, 'DrawMaskOnImage', '99',
        widget_0='0, 0, 0',
        image=getnode_10.out(0),
        mask=setnode_5.out(0),
    )
    setnode_2 = _node(wf, 'SetNode', '130',
        widget_0='background_image',
        IMAGE=drawmaskonimage.out(0),
    )
    vhs_videocombine_2 = _node(wf, 'VHS_VideoCombine', '75',
        save_output=True,
        images=setnode_2.out(0),
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

