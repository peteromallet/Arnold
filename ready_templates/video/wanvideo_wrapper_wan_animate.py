# vibecomfy: generated - converted by tools/convert_ready_templates.py
# Edits will be overwritten on regeneration. Put the manual opt-out
# marker on the first line if hand-editing is required.
"""Auto-generated ready_template - see tools/convert_ready_templates.py."""
from __future__ import annotations

from vibecomfy.templates import InputSpec, ModelAsset, ReadyMetadata, finalize, new_workflow, node as raw_call, ref
from vibecomfy.nodes.core import CLIPVisionLoader, GrowMask, LoadImage, PixelPerfectResolution
from vibecomfy.nodes.kjnodes import BlockifyMask, DrawMaskOnImage, GetImageSizeAndCount, INTConstant, ImageConcatMulti, ImageResizeKJv2, PointsEditor
from vibecomfy.nodes.sam2 import DownloadAndLoadSAM2Model, Sam2Segmentation
from vibecomfy.nodes.videohelpersuite import VHS_LoadVideo, VHS_VideoCombine
from vibecomfy.nodes.wanvideowrapper import WanVideoBlockSwap, WanVideoClipVisionEncode, WanVideoContextOptions, WanVideoDecode, WanVideoLoraSelectMulti, WanVideoModelLoader, WanVideoSampler, WanVideoSetBlockSwap, WanVideoSetLoRAs, WanVideoTextEncodeCached, WanVideoTorchCompileSettings, WanVideoVAELoader


DEFAULT_FRAMES = 501
DEFAULT_NEGATIVE = '色调艳丽，过曝，静态，细节模糊不清，字幕，风格，作品，画作，画面，静止，整体发灰，最差质量，低质量，JPEG压缩残留，丑陋的，残缺的，多余的手指，画得不好的手部，画得不好的脸部，畸形的，毁容的，形态畸形的肢体，手指融合，静止不动的画面，杂乱的背景，三条腿，背景人很多，倒着走'
DEFAULT_PROMPT = 'man is walking, style is soft 3D render style, night time, moonlight'
DEFAULT_SEED = 42
GUIDE_STRENGTH = 1
MODEL_NAME = 'wanvideo\\Wan2_1_VAE_bf16.safetensors'
MODEL_NAME_2 = 'umt5-xxl-enc-bf16.safetensors'
MODEL_NAME_3 = 'clip_vision_h.safetensors'
MODEL_NAME_4 = 'sam2_hiera_base_plus.safetensors'
MODEL_NAME_5 = 'WanVideo\\WanAnimate_relight_lora_fp16.safetensors'
MODEL_NAME_6 = 'WanVideo\\Lightx2v\\lightx2v_I2V_14B_480p_cfg_step_distill_rank64_bf16.safetensors'
MODEL_NAME_7 = 'WanVideo\\2_2\\Wan2_2-Animate-14B_fp8_e4m3fn_scaled_KJ.safetensors'
MODEL_NAME_8 = 'yolox_l.torchscript.pt'
MODEL_NAME_9 = 'dw-ll_ucoco_384_bs5.torchscript.pt'
WIDGET_0 = 'background_image'
WIDGET_0_10 = 'frame_count'
WIDGET_0_11 = 'VAE'
WIDGET_0_2 = 'reference_image'
WIDGET_0_3 = 'face_images'
WIDGET_0_4 = 'pose_images'
WIDGET_0_5 = 'mask'
WIDGET_0_6 = 'input_video'
WIDGET_0_7 = 'input_audio'
WIDGET_0_8 = 'width'
WIDGET_0_9 = 'height'


MODELS = {}

PUBLIC_INPUTS = {
    'model': InputSpec(node=ref('wanvideovaeloader'), field='model_name', default=MODEL_NAME),
    'seed': InputSpec(node=ref('wanvideosampler'), field='seed', default=DEFAULT_SEED),
    'image': InputSpec(node=ref('loadimage'), field='image', default='refer.jpeg'),
    'input_image': InputSpec(node=ref('loadimage'), field='image', default='refer.jpeg'),
    'width': InputSpec(node=ref('pointseditor'), field='width', default=832),
    'height': InputSpec(node=ref('pointseditor'), field='height', default=480),
}

READY_METADATA = ReadyMetadata.build(
    capability='animate_reference_video',
    inputs=PUBLIC_INPUTS,
    models=MODELS,
    requirements={'models': ['clip_vision_h.safetensors', 'umt5-xxl-enc-bf16.safetensors', 'wanvideo\\Wan2_1_VAE_bf16.safetensors'], 'custom_nodes': ['ComfyUI-KJNodes', 'ComfyUI-VideoHelperSuite', 'ComfyUI-WanVideoWrapper', 'ComfyUI-segment-anything-2', 'comfyui_controlnet_aux', 'rgthree-comfy']},
    custom_node_packs={'ComfyUI-KJNodes': {'commit': 'b7646ad70a7daa7aeb919ca542274758d26ba2df', 'url': 'https://github.com/kijai/ComfyUI-KJNodes.git', 'class_schema_sha256': '1beaf129c8fa26175d89a28f9ca10d08b5ac27c8fc9bff920263fcbba17cb691', 'classes_used': ['BlockifyMask', 'DrawMaskOnImage', 'GetImageSizeAndCount', 'INTConstant', 'ImageResizeKJv2', 'PointsEditor'], 'pip_packages': ['matplotlib'], 'status': 'pinned'}, 'ComfyUI-segment-anything-2': {'commit': '0c35fff5f382803e2310103357b5e985f5437f32', 'url': 'https://github.com/kijai/ComfyUI-segment-anything-2.git', 'class_schema_sha256': 'e3640990ce145928d9404234721b4f23fd02717c7f07af03b3d0be0f8a150e9c', 'classes_used': ['DownloadAndLoadSAM2Model', 'Sam2Segmentation'], 'pip_packages': ['opencv-python-headless'], 'status': 'pinned'}, 'ComfyUI-VideoHelperSuite': {'commit': '4ee72c065db22c9d96c2427954dc69e7b908444b', 'url': 'https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite.git', 'class_schema_sha256': '8391e679554eecd5d324a3e34a713ff240e619e3a07476587845ba18c9fae310', 'classes_used': ['VHS_LoadVideo', 'VHS_VideoCombine'], 'pip_packages': [], 'status': 'pinned'}, 'ComfyUI-WanVideoWrapper': {'commit': 'df8f3e49daaad117cf3090cc916c83f3d001494c', 'url': 'https://github.com/kijai/ComfyUI-WanVideoWrapper.git', 'class_schema_sha256': '80187858cc6ec371c9860fd9ca5fcf5174324d75782046657e252492512d115f', 'classes_used': ['WanVideoBlockSwap', 'WanVideoDecode', 'WanVideoLoraSelectMulti', 'WanVideoModelLoader', 'WanVideoSampler', 'WanVideoSetBlockSwap', 'WanVideoSetLoRAs', 'WanVideoTextEncodeCached', 'WanVideoTorchCompileSettings', 'WanVideoVAELoader'], 'pip_packages': ['onnx', 'opencv-python-headless'], 'status': 'pinned'}, 'comfyui_controlnet_aux': {'commit': 'e8b689a513c3e6b63edc44066560ca5919c0576e', 'url': 'https://github.com/Fannovel16/comfyui_controlnet_aux.git', 'class_schema_sha256': 'e485b148824d72ef7af7e90f711eefb511ffe73b25cd1c6053e1e5c7bd3bbd62', 'classes_used': ['DWPreprocessor'], 'pip_packages': ['onnxruntime', 'opencv-python-headless'], 'status': 'pinned'}, 'rgthree-comfy': {'commit': '738105af5fb14e96fbecaf406dc356e284797e8c', 'url': 'https://github.com/rgthree/rgthree-comfy.git', 'class_schema_sha256': '2b52072e02c59cb05ce83e5c45e1c7fd5b1273fee9b62eaaa0e66a81a4c07872', 'classes_used': ['GetNode', 'SetNode'], 'pip_packages': [], 'status': 'pinned'}},
    approach='WanAnimate reference animation',
    smoke_resolution='256x256x5_frames',
    provenance={'source_workflow': 'workflow_corpus/custom_nodes/wanvideo_wrapper/kijai/wan_animate.json'},
)

def build() -> VibeWorkflow:
    """Build the workflow (auto-generated)."""
    with new_workflow(READY_METADATA, source_path=__file__) as wf:

        wanvideotorchcompilesettings = WanVideoTorchCompileSettings()
        wanvideovaeloader = WanVideoVAELoader(model_name=MODEL_NAME)
        wanvideoblockswap = WanVideoBlockSwap(
            blocks_to_swap=25,
            use_non_blocking=True,
            prefetch_blocks=1,
        )

        # Inputs
        loadimage = LoadImage(image='refer.jpeg', _outputs=('IMAGE', 'MASK'))
        wanvideotextencodecached = WanVideoTextEncodeCached(
            model_name=MODEL_NAME_2,
            positive_prompt=DEFAULT_PROMPT,
            negative_prompt=DEFAULT_NEGATIVE,
            use_disk_cache=False,
            _outputs=('TEXT_EMBEDS', 'NEGATIVE_TEXT_EMBEDS', 'POSITIVE_PROMPT'),
        )

        # Loaders
        clipvisionloader = CLIPVisionLoader(clip_name=MODEL_NAME_3)
        downloadandloadsam2model = DownloadAndLoadSAM2Model(
            model=MODEL_NAME_4,
            segmentor='video',
            device='cuda',
        )

        wanvideocontextoptions = WanVideoContextOptions(
            context_schedule='static_standard',
            context_overlap=32,
        )

        getnode = raw_call(wf, 'GetNode', '131', widget_0=WIDGET_0)
        getnode_2 = raw_call(wf, 'GetNode', '133', widget_0=WIDGET_0_2)
        getnode_3 = raw_call(wf, 'GetNode', '134', widget_0=WIDGET_0_2)
        getnode_4 = raw_call(wf, 'GetNode', '137', widget_0=WIDGET_0_3)
        getnode_5 = raw_call(wf, 'GetNode', '138', widget_0=WIDGET_0_3)
        getnode_6 = raw_call(wf, 'GetNode', '140', widget_0=WIDGET_0_4)
        getnode_7 = raw_call(wf, 'GetNode', '141', widget_0=WIDGET_0_4)
        getnode_8 = raw_call(wf, 'GetNode', '143', widget_0=WIDGET_0_5)
        getnode_9 = raw_call(wf, 'GetNode', '145', widget_0=WIDGET_0_6)
        getnode_10 = raw_call(wf, 'GetNode', '146', widget_0=WIDGET_0_6)
        reroute = raw_call(wf, 'Reroute', '147')
        getnode_11 = raw_call(wf, 'GetNode', '149', widget_0=WIDGET_0_7)
        intconstant = INTConstant(value=832)
        intconstant_2 = INTConstant(value=480)
        getnode_12 = raw_call(wf, 'GetNode', '155', widget_0=WIDGET_0_8)
        getnode_13 = raw_call(wf, 'GetNode', '156', widget_0=WIDGET_0_9)
        getnode_14 = raw_call(wf, 'GetNode', '158', widget_0=WIDGET_0_10)
        getnode_15 = raw_call(wf, 'GetNode', '162', widget_0=WIDGET_0_11)
        getnode_16 = raw_call(wf, 'GetNode', '163', widget_0=WIDGET_0_11)
        wanvideoloraselectmulti = WanVideoLoraSelectMulti(
            lora_0=MODEL_NAME_5,
            lora_1=MODEL_NAME_6,
            strength_1=1.2,
            merge_loras=False,
        )

        setnode_8 = raw_call(wf, 'SetNode', '153', widget_0=WIDGET_0_8, INT=intconstant)
        setnode_9 = raw_call(wf, 'SetNode', '154',
            widget_0=WIDGET_0_9,
            INT=intconstant_2,
        )

        setnode_11 = raw_call(wf, 'SetNode', '161',
            widget_0=WIDGET_0_11,
            WANVAE=wanvideovaeloader,
        )

        wanvideomodelloader = WanVideoModelLoader(
            model=MODEL_NAME_7,
            base_precision='fp16',
            compile_args=wanvideotorchcompilesettings,
        )

        vhs_loadvideo = VHS_LoadVideo(
            video='wolf_interpolated.mp4',
            custom_height=intconstant_2,
            custom_width=intconstant,
            _outputs=('IMAGE', 'FRAME_COUNT', 'AUDIO', 'VIDEO_INFO'),
        )

        imageresizekjv2 = ImageResizeKJv2(
            upscale_method='lanczos',
            keep_proportion='pad_edge_pixel',
            crop_position='top',
            divisible_by=16,
            device='cpu',
            widget_0=256,
            widget_1=256,
            width=intconstant,
            height=intconstant_2,
            image=loadimage.out('IMAGE'),
            _outputs=('IMAGE', 'WIDTH', 'HEIGHT', 'MASK'),
        )

        wanvideoclipvisionencode = WanVideoClipVisionEncode(
            clip_vision=clipvisionloader,
            image_1=getnode_2.out(0),
        )

        imageconcatmulti = ImageConcatMulti(
            inputcount=4,
            direction='down',
            match_image_size=True,
            unused_3=None,
            image_1=getnode_3.out(0),
            image_2=getnode_4.out(0),
            image_3=getnode_6.out(0),
            image_4=getnode_9.out(0),
        )

        pixelperfectresolution = PixelPerfectResolution(
            resize_mode=512,
            widget_1=512,
            widget_2='Just Resize',
            image_gen_height=intconstant_2,
            image_gen_width=intconstant,
            original_image=reroute.out(0),
        )

        wanvideoanimateembeds = raw_call(wf, 'WanVideoAnimateEmbeds', '62',
            force_offload=False,
            unused_8=False,
            widget_0=832,
            widget_1=480,
            widget_2=501,
            width=getnode_12.out(0),
            height=getnode_13.out(0),
            num_frames=getnode_14.out(0),
            bg_images=getnode.out(0),
            clip_embeds=wanvideoclipvisionencode,
            face_images=getnode_5.out(0),
            mask=getnode_8.out(0),
            pose_images=getnode_7.out(0),
            ref_images=getnode_2.out(0),
            vae=getnode_16.out(0),
        )

        dwpreprocessor = raw_call(wf, 'DWPreprocessor', '73',
            detect_hand='disable',
            detect_body='enable',
            detect_face='disable',
            bbox_detector=MODEL_NAME_8,
            pose_estimator=MODEL_NAME_9,
            scale_stick_for_xinsr_cn='disable',
            widget_3=960,
            resolution=pixelperfectresolution,
            image=reroute.out(0),
        )

        setnode = raw_call(wf, 'SetNode', '128',
            widget_0=WIDGET_0_2,
            IMAGE=imageresizekjv2.out('IMAGE'),
        )

        setnode_6 = raw_call(wf, 'SetNode', '144',
            widget_0=WIDGET_0_6,
            IMAGE=vhs_loadvideo.out('IMAGE'),
        )

        setnode_7 = raw_call(wf, 'SetNode', '148',
            widget_0=WIDGET_0_7,
            AUDIO=vhs_loadvideo.out('AUDIO'),
        )

        setnode_10 = raw_call(wf, 'SetNode', '157',
            widget_0=WIDGET_0_10,
            INT=vhs_loadvideo.out('FRAME_COUNT'),
        )

        wanvideosetloras = WanVideoSetLoRAs(
            lora=wanvideoloraselectmulti,
            model=wanvideomodelloader,
        )

        facemaskfromposekeypoints = raw_call(wf, 'FaceMaskFromPoseKeypoints', '120',
            widget_0=0,
            pose_kps=dwpreprocessor.out(1),
        )

        setnode_4 = raw_call(wf, 'SetNode', '139',
            widget_0=WIDGET_0_4,
            IMAGE=dwpreprocessor,
        )

        wanvideosetblockswap = WanVideoSetBlockSwap(
            block_swap_args=wanvideoblockswap,
            model=wanvideosetloras,
        )

        pointseditor = PointsEditor(
            points_store='{"positive":[{"x":483.34844284815,"y":333.283583335728},{"x":479.85856239437277,"y":158.78956064686517}],"negative":[{"x":0,"y":0}]}',
            coordinates='[{"x":483.34844284815,"y":333.283583335728},{"x":479.85856239437277,"y":158.78956064686517}]',
            neg_coordinates='[{"x":0,"y":0}]',
            bbox_store='[{}]',
            bboxes='[{}]',
            bbox_format='xyxy',
            width=832,
            height=480,
            widget_10=None,
            widget_9='',
            bg_image=setnode_6.out(0),
            _outputs=('POSITIVE_COORDS', 'NEGATIVE_COORDS', 'BBOX', 'BBOX_MASK', 'CROPPED_IMAGE'),
        )

        imagecropbymaskandresize = raw_call(wf, 'ImageCropByMaskAndResize', '96',
            _outputs=('IMAGES', 'MASKS', 'BBOX'),
            widget_0=512,
            widget_1=0,
            widget_2=128,
            widget_3=512,
            image=reroute.out(0),
            mask=facemaskfromposekeypoints,
        )

        wanvideosampler = WanVideoSampler(
            steps=1,
            cfg=GUIDE_STRENGTH,
            seed=DEFAULT_SEED,
            scheduler='dpm++_sde',
            batched_cfg='',
            widget_0=1,
            image_embeds=wanvideoanimateembeds,
            model=wanvideosetblockswap,
            text_embeds=wanvideotextencodecached.out('TEXT_EMBEDS'),
            _outputs=('SAMPLES', 'DENOISED_SAMPLES'),
        )

        sam2segmentation = Sam2Segmentation(
            coordinates_positive=pointseditor.out('POSITIVE_COORDS'),
            image=setnode_6.out(0),
            sam2_model=downloadandloadsam2model,
        )

        setnode_3 = raw_call(wf, 'SetNode', '135',
            widget_0=WIDGET_0_3,
            IMAGE=imagecropbymaskandresize.out('IMAGES'),
        )

        wanvideodecode = WanVideoDecode(
            normalization='default',
            samples=wanvideosampler.out('SAMPLES'),
            vae=getnode_15.out(0),
        )

        growmask = GrowMask(expand=10, mask=sam2segmentation)
        getimagesizeandcount = GetImageSizeAndCount(
            image=wanvideodecode,
            _outputs=('IMAGE', 'WIDTH', 'HEIGHT', 'COUNT'),
        )

        blockifymask = BlockifyMask(masks=growmask)

        # Outputs
        vhs_videocombine = VHS_VideoCombine(images=setnode_3.out(0))
        setnode_5 = raw_call(wf, 'SetNode', '142',
            widget_0=WIDGET_0_5,
            MASK=blockifymask,
        )

        imageconcatmulti_2 = ImageConcatMulti(
            direction='left',
            match_image_size=True,
            unused_3=None,
            image_1=getimagesizeandcount.out('IMAGE'),
            image_2=imageconcatmulti,
        )

        vhs_videocombine_2 = VHS_VideoCombine(
            audio=getnode_11.out(0),
            images=imageconcatmulti_2,
        )

        drawmaskonimage = DrawMaskOnImage(
            image=getnode_10.out(0),
            mask=setnode_5.out(0),
        )

        setnode_2 = raw_call(wf, 'SetNode', '130',
            widget_0=WIDGET_0,
            IMAGE=drawmaskonimage,
        )

        vhs_videocombine_3 = VHS_VideoCombine(images=setnode_2.out(0))

        wf._set_id_map({name: node.node.id for name, node in (('wanvideotorchcompilesettings', wanvideotorchcompilesettings), ('wanvideovaeloader', wanvideovaeloader), ('wanvideoblockswap', wanvideoblockswap), ('loadimage', loadimage), ('wanvideotextencodecached', wanvideotextencodecached), ('clipvisionloader', clipvisionloader), ('downloadandloadsam2model', downloadandloadsam2model), ('wanvideocontextoptions', wanvideocontextoptions), ('wanvideoanimateembeds', wanvideoanimateembeds), ('dwpreprocessor', dwpreprocessor), ('imagecropbymaskandresize', imagecropbymaskandresize), ('facemaskfromposekeypoints', facemaskfromposekeypoints), ('setnode', setnode), ('setnode_2', setnode_2), ('getnode', getnode), ('getnode_2', getnode_2), ('getnode_3', getnode_3), ('setnode_3', setnode_3), ('getnode_4', getnode_4), ('getnode_5', getnode_5), ('setnode_4', setnode_4), ('getnode_6', getnode_6), ('getnode_7', getnode_7), ('setnode_5', setnode_5), ('getnode_8', getnode_8), ('setnode_6', setnode_6), ('getnode_9', getnode_9), ('getnode_10', getnode_10), ('reroute', reroute), ('setnode_7', setnode_7), ('getnode_11', getnode_11), ('intconstant', intconstant), ('intconstant_2', intconstant_2), ('setnode_8', setnode_8), ('setnode_9', setnode_9), ('getnode_12', getnode_12), ('getnode_13', getnode_13), ('setnode_10', setnode_10), ('getnode_14', getnode_14), ('setnode_11', setnode_11), ('getnode_15', getnode_15), ('getnode_16', getnode_16), ('wanvideoloraselectmulti', wanvideoloraselectmulti), ('wanvideomodelloader', wanvideomodelloader), ('vhs_loadvideo', vhs_loadvideo), ('imageresizekjv2', imageresizekjv2), ('wanvideoclipvisionencode', wanvideoclipvisionencode), ('imageconcatmulti', imageconcatmulti), ('pixelperfectresolution', pixelperfectresolution), ('wanvideosetloras', wanvideosetloras), ('wanvideosetblockswap', wanvideosetblockswap), ('pointseditor', pointseditor), ('wanvideosampler', wanvideosampler), ('sam2segmentation', sam2segmentation), ('wanvideodecode', wanvideodecode), ('growmask', growmask), ('getimagesizeandcount', getimagesizeandcount), ('blockifymask', blockifymask), ('vhs_videocombine', vhs_videocombine), ('imageconcatmulti_2', imageconcatmulti_2), ('vhs_videocombine_2', vhs_videocombine_2), ('drawmaskonimage', drawmaskonimage), ('vhs_videocombine_3', vhs_videocombine_3))})

        return wf.finalize(PUBLIC_INPUTS, output_node=vhs_videocombine, output_type='VHS_VideoCombine', name='video', artifact_kind='video', mime_type='video/mp4', expected_cardinality='one')

