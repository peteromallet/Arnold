# vibecomfy: generated — converted by tools/convert_ready_templates.py
# Edits will be overwritten on regeneration. Add a `# vibecomfy: manual`
# marker on the first line if hand-editing is required.
"""Auto-generated ready_template — see tools/convert_ready_templates.py."""
from __future__ import annotations

from vibecomfy.workflow import VibeWorkflow, WorkflowSource
from vibecomfy.registry.ready_template import apply_ready_template_policy


READY_METADATA = {'model_assets': [],
 'unbound_inputs': {'seed': 3528},
 'ready_template': 'video/wanvideo_wrapper_13b_vace',
 'workflow_template': 'wanvideo_wrapper_13b_vace',
 'capability': 'vace_video_control',
 'source_role': 'materialized_ready_python_template',
 'source_workflow': 'workflow_corpus/custom_nodes/wanvideo_wrapper/kijai/wan13b_vace.json',
 'coverage_tier': 'supplemental',
 'approach': 'VACE control/edit workflow',
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
        widget_0=0,
        widget_1=False,
        widget_2=False,
        widget_3=True,
        widget_4=15,
    )
    wanvideoteacache = _node(wf, 'WanVideoTeaCache', '52',
        widget_0=0.10000000000000002,
        widget_1=0,
        widget_2=-1,
        widget_3='offload_device',
        widget_4='true',
        widget_5='e',
    )
    loadimage = _node(wf, 'LoadImage', '64',
        image='replicate-prediction-5cvynz9d91rgg0cfsvqschdpww-0.webp',
        widget_1='image',
    )
    wanvideoexperimentalargs = _node(wf, 'WanVideoExperimentalArgs', '71',
        widget_0='',
        widget_1=True,
        widget_2=False,
        widget_3=0,
        widget_4=False,
        widget_5=1,
        widget_6=1.25,
        widget_7=20,
    )
    wanvideoslg = _node(wf, 'WanVideoSLG', '72',
        widget_0='8',
        widget_1=0.30000000000000004,
        widget_2=0.7000000000000002,
    )
    loadimage_2 = _node(wf, 'LoadImage', '112',
        image='replicate-prediction-5cvynz9d91rgg0cfsvqschdpww-3.webp',
        widget_1='image',
    )
    getnode = _node(wf, 'GetNode', '123',
        widget_0='WanVAE',
    )
    getnode_2 = _node(wf, 'GetNode', '124',
        widget_0='WanVAE',
    )
    getnode_3 = _node(wf, 'GetNode', '126',
        widget_0='WanTextEncoder',
    )
    getnode_4 = _node(wf, 'GetNode', '127',
        widget_0='WanModel',
    )
    getnode_5 = _node(wf, 'GetNode', '128',
        widget_0='WanModel',
    )
    getnode_6 = _node(wf, 'GetNode', '130',
        widget_0='start_image',
    )
    getnode_7 = _node(wf, 'GetNode', '131',
        widget_0='end_image',
    )
    getnode_8 = _node(wf, 'GetNode', '142',
        widget_0='WanVAE',
    )
    getnode_9 = _node(wf, 'GetNode', '143',
        widget_0='WanTextEncoder',
    )
    wanvideoteacache_2 = _node(wf, 'WanVideoTeaCache', '147',
        widget_0=0.10000000000000002,
        widget_1=0,
        widget_2=-1,
        widget_3='offload_device',
        widget_4='true',
        widget_5='e',
    )
    wanvideoslg_2 = _node(wf, 'WanVideoSLG', '149',
        widget_0='8',
        widget_1=0.30000000000000004,
        widget_2=0.7100000000000002,
    )
    wanvideoexperimentalargs_2 = _node(wf, 'WanVideoExperimentalArgs', '150',
        widget_0='',
        widget_1=True,
        widget_2=False,
        widget_3=0,
        widget_4=False,
        widget_5=1,
        widget_6=1.25,
        widget_7=20,
    )
    getnode_10 = _node(wf, 'GetNode', '151',
        widget_0='WanModel',
    )
    getnode_11 = _node(wf, 'GetNode', '152',
        widget_0='WanModel',
    )
    getnode_12 = _node(wf, 'GetNode', '153',
        widget_0='reference_image',
    )
    getnode_13 = _node(wf, 'GetNode', '154',
        widget_0='control_video',
    )
    getnode_14 = _node(wf, 'GetNode', '166',
        widget_0='WanVAE',
    )
    loadimage_3 = _node(wf, 'LoadImage', '169',
        image='hunhyuanwolf.png',
        widget_1='image',
    )
    vhs_loadvideo = _node(wf, 'VHS_LoadVideo', '173',
        video='wolf_interpolated.mp4',
    )
    downloadandloaddepthanythingv2model = _node(wf, 'DownloadAndLoadDepthAnythingV2Model', '175',
        widget_0='depth_anything_v2_vitl_fp16.safetensors',
    )
    getnode_15 = _node(wf, 'GetNode', '185',
        widget_0='WanVAE',
    )
    getnode_16 = _node(wf, 'GetNode', '186',
        widget_0='WanTextEncoder',
    )
    wanvideoslg_3 = _node(wf, 'WanVideoSLG', '187',
        widget_0='8',
        widget_1=0.30000000000000004,
        widget_2=0.7000000000000002,
    )
    wanvideoexperimentalargs_3 = _node(wf, 'WanVideoExperimentalArgs', '188',
        widget_0='',
        widget_1=True,
        widget_2=False,
        widget_3=0,
        widget_4=False,
        widget_5=1,
        widget_6=1.25,
        widget_7=20,
    )
    getnode_17 = _node(wf, 'GetNode', '189',
        widget_0='WanModel',
    )
    getnode_18 = _node(wf, 'GetNode', '190',
        widget_0='WanModel',
    )
    getnode_19 = _node(wf, 'GetNode', '195',
        widget_0='WanVAE',
    )
    vhs_loadvideo_2 = _node(wf, 'VHS_LoadVideo', '199',
        video='wolf_interpolated.mp4',
    )
    getnode_20 = _node(wf, 'GetNode', '201',
        widget_0='InputVideo',
    )
    wanvideoteacache_3 = _node(wf, 'WanVideoTeaCache', '214',
        widget_0=0.10000000000000002,
        widget_1=0,
        widget_2=-1,
        widget_3='offload_device',
        widget_4='true',
        widget_5='e',
    )
    wanvideovacemodelselect = _node(wf, 'WanVideoVACEModelSelect', '224',
        widget_0='WanVideo\\Wan2_1-VACE_module_1_3B_bf16.safetensors',
    )
    wanvideotextencode = _node(wf, 'WanVideoTextEncode', '16',
        widget_0='black and white cartoon character',
        widget_1='colorful, bad quality, blurry, messy, chaotic',
        widget_2=True,
        model_to_offload=getnode_4.out(0),
        t5=getnode_3.out(0),
    )
    wanvideomodelloader = _node(wf, 'WanVideoModelLoader', '22',
        widget_0='WanVideo\\wan2.1_t2v_1.3B_fp16.safetensors',
        widget_1='fp16',
        widget_2='disabled',
        widget_3='offload_device',
        widget_4='sdpa',
        vace_model=wanvideovacemodelselect.out(0),
    )
    setnode_2 = _node(wf, 'SetNode', '122',
        widget_0='WanVAE',
        WANVAE=wanvideovaeloader.out(0),
    )
    setnode_3 = _node(wf, 'SetNode', '125',
        widget_0='WanTextEncoder',
        WANTEXTENCODER=loadwanvideot5textencoder.out(0),
    )
    addlabel = _node(wf, 'AddLabel', '133',
        widget_0=10,
        widget_1=2,
        widget_2=48,
        widget_3=32,
        widget_4='white',
        widget_5='black',
        widget_6='FreeMono.ttf',
        widget_7='start_frame',
        widget_8='up',
        image=getnode_6.out(0),
    )
    addlabel_2 = _node(wf, 'AddLabel', '134',
        widget_0=10,
        widget_1=2,
        widget_2=48,
        widget_3=32,
        widget_4='white',
        widget_5='black',
        widget_6='FreeMono.ttf',
        widget_7='end_frame',
        widget_8='up',
        image=getnode_7.out(0),
    )
    addlabel_3 = _node(wf, 'AddLabel', '156',
        widget_0=10,
        widget_1=2,
        widget_2=48,
        widget_3=32,
        widget_4='white',
        widget_5='black',
        widget_6='FreeMono.ttf',
        widget_7='reference image',
        widget_8='up',
        image=getnode_12.out(0),
    )
    addlabel_4 = _node(wf, 'AddLabel', '157',
        widget_0=10,
        widget_1=2,
        widget_2=48,
        widget_3=32,
        widget_4='white',
        widget_5='black',
        widget_6='FreeMono.ttf',
        widget_7='control_video',
        widget_8='up',
        image=getnode_13.out(0),
    )
    wanvideotextencode_2 = _node(wf, 'WanVideoTextEncode', '168',
        widget_0='robotic cybernetic wolf turning his head',
        widget_1='bad quality, blurry, messy, chaotic',
        widget_2=True,
        model_to_offload=getnode_10.out(0),
        t5=getnode_9.out(0),
    )
    imagepadkj = _node(wf, 'ImagePadKJ', '184',
        widget_0=0,
        widget_1=0,
        widget_2=0,
        widget_3=0,
        widget_4=128,
        widget_5='color',
        widget_6='255,255,255',
        image=loadimage_3.out(0),
    )
    addlabel_5 = _node(wf, 'AddLabel', '202',
        widget_0=10,
        widget_1=2,
        widget_2=48,
        widget_3=32,
        widget_4='white',
        widget_5='black',
        widget_6='FreeMono.ttf',
        widget_7='input',
        widget_8='up',
        image=getnode_20.out(0),
    )
    wanvideotextencode_3 = _node(wf, 'WanVideoTextEncode', '211',
        widget_0='robotic cybernetic wolf turning his head',
        widget_1='bad quality, blurry, messy, chaotic',
        widget_2=True,
        model_to_offload=getnode_17.out(0),
        t5=getnode_16.out(0),
    )
    imageresizekjv2 = _node(wf, 'ImageResizeKJv2', '226',
        height=256,
        widget_0=256,
        widget_1=256,
        widget_2='lanczos',
        widget_3='crop',
        widget_4='172,172,172',
        widget_5='center',
        widget_6=2,
        width=256,
        image=vhs_loadvideo_2.out(0),
    )
    imageresizekjv2_2 = _node(wf, 'ImageResizeKJv2', '227',
        height=256,
        widget_0=256,
        widget_1=256,
        widget_2='lanczos',
        widget_3='crop',
        widget_4='172,172,172',
        widget_5='center',
        widget_6=16,
        width=256,
        image=loadimage.out(0),
    )
    imageresizekjv2_4 = _node(wf, 'ImageResizeKJv2', '229',
        height=256,
        widget_0=256,
        widget_1=256,
        widget_2='lanczos',
        widget_3='crop',
        widget_4='172,172,172',
        widget_5='center',
        widget_6=16,
        width=256,
        image=vhs_loadvideo.out(0),
    )
    setnode = _node(wf, 'SetNode', '121',
        widget_0='WanModel',
        WANVIDEOMODEL=wanvideomodelloader.out(0),
    )
    imageconcatmulti_2 = _node(wf, 'ImageConcatMulti', '136',
        widget_0=2,
        widget_1='down',
        widget_2=True,
        widget_3=None,
        image_1=addlabel.out(0),
        image_2=addlabel_2.out(0),
    )
    setnode_4 = _node(wf, 'SetNode', '140',
        widget_0='start_image',
        IMAGE=imageresizekjv2_2.out(0),
    )
    imageconcatmulti_4 = _node(wf, 'ImageConcatMulti', '160',
        widget_0=2,
        widget_1='down',
        widget_2=True,
        widget_3=None,
        image_1=addlabel_3.out(0),
        image_2=addlabel_4.out(0),
    )
    depthanything_v2 = _node(wf, 'DepthAnything_V2', '174',
        da_model=downloadandloaddepthanythingv2model.out(0),
        images=imageresizekjv2_4.out(0),
    )
    imagepadkj_2 = _node(wf, 'ImagePadKJ', '216',
        widget_0=0,
        widget_1=0,
        widget_2=0,
        widget_3=0,
        widget_4=128,
        widget_5='color',
        widget_6='127,127,127',
        image=imageresizekjv2.out(0),
    )
    imageresizekjv2_3 = _node(wf, 'ImageResizeKJv2', '228',
        widget_0=256,
        widget_1=256,
        widget_2='lanczos',
        widget_3='crop',
        widget_4='172,172,172',
        widget_5='center',
        widget_6=16,
        height=imageresizekjv2_2.out(2),
        image=loadimage_2.out(0),
        width=imageresizekjv2_2.out(1),
    )
    imageresizekjv2_5 = _node(wf, 'ImageResizeKJv2', '230',
        widget_0=256,
        widget_1=256,
        widget_2='lanczos',
        widget_3='pad',
        widget_4='255,255,255',
        widget_5='center',
        widget_6=16,
        height=imageresizekjv2_4.out(2),
        image=imagepadkj.out(0),
        width=imageresizekjv2_4.out(1),
    )
    imageresizekjv2_6 = _node(wf, 'ImageResizeKJv2', '238',
        widget_0=256,
        widget_1=256,
        widget_2='lanczos',
        widget_3='pad',
        widget_4='255,255,255',
        widget_5='center',
        widget_6=16,
        height=imageresizekjv2_4.out(2),
        image=loadimage_3.out(0),
        width=imageresizekjv2_4.out(1),
    )
    setnode_5 = _node(wf, 'SetNode', '141',
        widget_0='end_image',
        IMAGE=imageresizekjv2_3.out(0),
    )
    setnode_6 = _node(wf, 'SetNode', '179',
        widget_0='reference_image',
        IMAGE=imageresizekjv2_5.out(0),
    )
    setnode_7 = _node(wf, 'SetNode', '180',
        widget_0='control_video',
        IMAGE=depthanything_v2.out(0),
    )
    getimagesizeandcount_6 = _node(wf, 'GetImageSizeAndCount', '205',
        image=imagepadkj_2.out(0),
    )
    getimagerangefrombatch = _node(wf, 'GetImageRangeFromBatch', '219',
        widget_0=0,
        widget_1=1,
        images=imagepadkj_2.out(0),
    )
    setnode_8 = _node(wf, 'SetNode', '221',
        widget_0='InputVideo',
        IMAGE=imagepadkj_2.out(0),
    )
    getimagerangefrombatch_2 = _node(wf, 'GetImageRangeFromBatch', '222',
        widget_0=0,
        widget_1=1,
        masks=imagepadkj_2.out(1),
    )
    previewimage_4 = _node(wf, 'PreviewImage', '237',
        images=imageresizekjv2_5.out(0),
    )
    wanvideovacestarttoendframe = _node(wf, 'WanVideoVACEStartToEndFrame', '111',
        widget_0=33,
        widget_1=0.5000000000000001,
        end_image=setnode_5.out(0),
        start_image=setnode_4.out(0),
    )
    vhs_videocombine_3 = _node(wf, 'VHS_VideoCombine', '177',
        save_output=True,
        images=setnode_7.out(0),
    )
    wanvideovaceencode_3 = _node(wf, 'WanVideoVACEEncode', '209',
        widget_0=480,
        widget_1=832,
        widget_2=29,
        widget_3=1.0000000000000002,
        widget_4=0,
        widget_5=1,
        widget_6=False,
        height=getimagesizeandcount_6.out(2),
        input_frames=getimagesizeandcount_6.out(0),
        input_masks=imagepadkj_2.out(1),
        num_frames=getimagesizeandcount_6.out(3),
        vae=getnode_15.out(0),
        width=getimagesizeandcount_6.out(1),
    )
    previewimage_2 = _node(wf, 'PreviewImage', '220',
        images=getimagerangefrombatch.out(0),
    )
    wanvideovacestarttoendframe_2 = _node(wf, 'WanVideoVACEStartToEndFrame', '231',
        widget_0=33,
        widget_1=0.5000000000000001,
        control_images=setnode_7.out(0),
        num_frames=vhs_loadvideo.out(1),
        start_image=imageresizekjv2_6.out(0),
    )
    maskpreview_3 = _node(wf, 'MaskPreview', '235',
        mask=getimagerangefrombatch_2.out(1),
    )
    getimagesizeandcount = _node(wf, 'GetImageSizeAndCount', '104',
        image=wanvideovacestarttoendframe.out(0),
    )
    getimagesizeandcount_3 = _node(wf, 'GetImageSizeAndCount', '145',
        image=wanvideovacestarttoendframe_2.out(0),
    )
    wanvideosampler_3 = _node(wf, 'WanVideoSampler', '197',
        steps=1,
        widget_0=1,
        widget_1=4.000000000000001,
        widget_10='comfy',
        widget_11='',
        widget_2=8.000000000000002,
        widget_3=18,
        widget_4='fixed',
        widget_5=True,
        widget_6='unipc',
        widget_7=0,
        widget_8=1,
        widget_9=False,
        cache_args=wanvideoteacache_3.out(0),
        experimental_args=wanvideoexperimentalargs_3.out(0),
        image_embeds=wanvideovaceencode_3.out(0),
        model=getnode_18.out(0),
        slg_args=wanvideoslg_3.out(0),
        text_embeds=wanvideotextencode_3.out(0),
    )
    previewimage_3 = _node(wf, 'PreviewImage', '232',
        images=wanvideovacestarttoendframe_2.out(0),
    )
    maskpreview = _node(wf, 'MaskPreview', '233',
        mask=wanvideovacestarttoendframe_2.out(1),
    )
    maskpreview_2 = _node(wf, 'MaskPreview', '234',
        mask=wanvideovacestarttoendframe.out(1),
    )
    wanvideovaceencode = _node(wf, 'WanVideoVACEEncode', '56',
        widget_0=480,
        widget_1=832,
        widget_2=29,
        widget_3=1.0000000000000002,
        widget_4=0,
        widget_5=1,
        widget_6=False,
        height=getimagesizeandcount.out(2),
        input_frames=getimagesizeandcount.out(0),
        input_masks=wanvideovacestarttoendframe.out(1),
        num_frames=getimagesizeandcount.out(3),
        ref_images=imageresizekjv2_2.out(0),
        vae=getnode_2.out(0),
        width=getimagesizeandcount.out(1),
    )
    previewimage = _node(wf, 'PreviewImage', '113',
        images=getimagesizeandcount.out(0),
    )
    wanvideovaceencode_2 = _node(wf, 'WanVideoVACEEncode', '148',
        widget_0=480,
        widget_1=832,
        widget_2=29,
        widget_3=1.0000000000000002,
        widget_4=0,
        widget_5=1,
        widget_6=False,
        height=getimagesizeandcount_3.out(2),
        input_frames=getimagesizeandcount_3.out(0),
        input_masks=wanvideovacestarttoendframe_2.out(1),
        num_frames=getimagesizeandcount_3.out(3),
        ref_images=setnode_6.out(0),
        vae=getnode_8.out(0),
        width=getimagesizeandcount_3.out(1),
    )
    wanvideodecode_3 = _node(wf, 'WanVideoDecode', '196',
        widget_0=False,
        widget_1=272,
        widget_2=272,
        widget_3=144,
        widget_4=128,
        samples=wanvideosampler_3.out(0),
        vae=getnode_19.out(0),
    )
    wanvideosampler = _node(wf, 'WanVideoSampler', '70',
        steps=1,
        widget_0=1,
        widget_1=4.000000000000001,
        widget_10='comfy',
        widget_11='',
        widget_2=8.000000000000002,
        widget_3=18,
        widget_4='fixed',
        widget_5=True,
        widget_6='unipc',
        widget_7=0,
        widget_8=1,
        widget_9=False,
        cache_args=wanvideoteacache.out(0),
        experimental_args=wanvideoexperimentalargs.out(0),
        image_embeds=wanvideovaceencode.out(0),
        model=getnode_5.out(0),
        slg_args=wanvideoslg.out(0),
        text_embeds=wanvideotextencode.out(0),
    )
    wanvideosampler_2 = _node(wf, 'WanVideoSampler', '172',
        steps=1,
        widget_0=1,
        widget_1=4.000000000000001,
        widget_10='comfy',
        widget_11='',
        widget_2=8.000000000000002,
        widget_3=0,
        widget_4='fixed',
        widget_5=True,
        widget_6='unipc',
        widget_7=0,
        widget_8=1,
        widget_9=False,
        cache_args=wanvideoteacache_2.out(0),
        experimental_args=wanvideoexperimentalargs_2.out(0),
        image_embeds=wanvideovaceencode_2.out(0),
        model=getnode_11.out(0),
        slg_args=wanvideoslg_2.out(0),
        text_embeds=wanvideotextencode_2.out(0),
    )
    getimagesizeandcount_5 = _node(wf, 'GetImageSizeAndCount', '193',
        image=wanvideodecode_3.out(0),
    )
    wanvideodecode = _node(wf, 'WanVideoDecode', '138',
        widget_0=False,
        widget_1=272,
        widget_2=272,
        widget_3=144,
        widget_4=128,
        samples=wanvideosampler.out(0),
        vae=getnode.out(0),
    )
    wanvideodecode_2 = _node(wf, 'WanVideoDecode', '167',
        widget_0=False,
        widget_1=272,
        widget_2=272,
        widget_3=144,
        widget_4=128,
        samples=wanvideosampler_2.out(0),
        vae=getnode_14.out(0),
    )
    emptyimage_3 = _node(wf, 'EmptyImage', '191',
        widget_0=8,
        widget_1=512,
        widget_2=1,
        widget_3=0,
        height=getimagesizeandcount_5.out(2),
    )
    getimagesizeandcount_2 = _node(wf, 'GetImageSizeAndCount', '137',
        image=wanvideodecode.out(0),
    )
    getimagesizeandcount_4 = _node(wf, 'GetImageSizeAndCount', '159',
        image=wanvideodecode_2.out(0),
    )
    imageconcatmulti_5 = _node(wf, 'ImageConcatMulti', '192',
        widget_0=3,
        widget_1='left',
        widget_2=True,
        widget_3=None,
        image_1=getimagesizeandcount_5.out(0),
        image_2=emptyimage_3.out(0),
        image_3=addlabel_5.out(0),
    )
    emptyimage = _node(wf, 'EmptyImage', '132',
        widget_0=8,
        widget_1=512,
        widget_2=1,
        widget_3=0,
        height=getimagesizeandcount_2.out(2),
    )
    emptyimage_2 = _node(wf, 'EmptyImage', '155',
        widget_0=8,
        widget_1=512,
        widget_2=1,
        widget_3=0,
        height=getimagesizeandcount_4.out(2),
    )
    vhs_videocombine_4 = _node(wf, 'VHS_VideoCombine', '213',
        save_output=True,
        images=imageconcatmulti_5.out(0),
    )
    imageconcatmulti = _node(wf, 'ImageConcatMulti', '135',
        widget_0=3,
        widget_1='left',
        widget_2=True,
        widget_3=None,
        image_1=getimagesizeandcount_2.out(0),
        image_2=emptyimage.out(0),
        image_3=imageconcatmulti_2.out(0),
    )
    imageconcatmulti_3 = _node(wf, 'ImageConcatMulti', '158',
        widget_0=3,
        widget_1='left',
        widget_2=True,
        widget_3=None,
        image_1=getimagesizeandcount_4.out(0),
        image_2=emptyimage_2.out(0),
        image_3=imageconcatmulti_4.out(0),
    )
    vhs_videocombine = _node(wf, 'VHS_VideoCombine', '139',
        save_output=True,
        images=imageconcatmulti.out(0),
    )
    vhs_videocombine_2 = _node(wf, 'VHS_VideoCombine', '165',
        save_output=True,
        images=imageconcatmulti_3.out(0),
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

