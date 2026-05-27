# vibecomfy: generated
# For hand-editing, run: python -m vibecomfy.cli copy-to-recipe <id>
"""Auto-generated ready_template — use python -m vibecomfy.cli copy-to-recipe <id> for hand-editing."""
from __future__ import annotations

from vibecomfy.templates import InputSpec, ReadyMetadata, new_workflow
from vibecomfy.nodes.core import EmptyImage, GetImageRangeFromBatch, LoadImage, MaskPreview, PreviewImage
from vibecomfy.nodes.depthanythingv2 import DepthAnything_V2, DownloadAndLoadDepthAnythingV2Model
from vibecomfy.nodes.kjnodes import AddLabel, GetImageSizeAndCount, ImageConcatMulti, ImagePadKJ, ImageResizeKJv2
from vibecomfy.nodes.videohelpersuite import VHS_LoadVideo, VHS_VideoCombine
from vibecomfy.nodes.wanvideowrapper import LoadWanVideoT5TextEncoder, WanVideoBlockSwap, WanVideoDecode, WanVideoExperimentalArgs, WanVideoModelLoader, WanVideoSLG, WanVideoSampler, WanVideoTeaCache, WanVideoTextEncode, WanVideoTorchCompileSettings, WanVideoVACEEncode, WanVideoVACEModelSelect, WanVideoVACEStartToEndFrame, WanVideoVAELoader


BLACK = 'black'
COLOR = 'color'
CROP = 'crop'
DEFAULT_FRAMES = 33
DEFAULT_NEGATIVE = 'colorful, bad quality, blurry, messy, chaotic'
DEFAULT_NEGATIVE_2 = 'bad quality, blurry, messy, chaotic'
DEFAULT_PROMPT = 'black and white cartoon character'
DEFAULT_PROMPT_2 = 'robotic cybernetic wolf turning his head'
DEFAULT_SEED = 18
DOWN = 'down'
FIXED = 'fixed'
FREEMONO_TTF = 'FreeMono.ttf'
GUIDE_STRENGTH = 4.000000000000001
IMAGE = 'image'
LANCZOS = 'lanczos'
LEFT = 'left'
MODEL_NAME = 'umt5-xxl-enc-bf16.safetensors'
MODEL_NAME_2 = 'wanvideo\\Wan2_1_VAE_bf16.safetensors'
MODEL_NAME_3 = 'depth_anything_v2_vitl_fp16.safetensors'
MODEL_NAME_4 = 'WanVideo\\wan2.1_t2v_1.3B_fp16.safetensors'
PAD = 'pad'
TRUE = 'true'
UP = 'up'
VACE_MODEL_NAME = 'WanVideo\\Wan2_1-VACE_module_1_3B_bf16.safetensors'
VALUE = ''
VIDEO_H264_MP4 = 'video/h264-mp4'
V_172_172_172 = '172,172,172'
V_255_255_255 = '255,255,255'
V_8 = '8'
WHITE = 'white'
WOLF_INTERPOLATED_MP4 = 'wolf_interpolated.mp4'
YUV420P = 'yuv420p'


PUBLIC_INPUT_METADATA = {
    'model': InputSpec(node='1', field='model_name', default=MODEL_NAME),
    'seed': InputSpec(node='60', field='seed', default=DEFAULT_SEED),
    'image': InputSpec(node='6', field='image', default='replicate-prediction-5cvynz9d91rgg0cfsvqschdpww-0.webp', aliases=('input_image',)),
    'width': InputSpec(node='69', field='width', default=8),
    'height': InputSpec(node='27', field='height', default=32),
}

READY_METADATA = ReadyMetadata.build(
    capability='unknown',
    inputs=PUBLIC_INPUT_METADATA,
    requirements={'models': ['umt5-xxl-enc-bf16.safetensors', 'wanvideo\\Wan2_1_VAE_bf16.safetensors']},
    custom_node_packs={'ComfyUI-DepthAnythingV2': {'commit': '553187872eeb1d52e50dc53209fa57e569609a72', 'url': 'https://github.com/kijai/ComfyUI-DepthAnythingV2.git', 'class_schema_sha256': 'f4e181ab42ca179eda161acba5121e999cb54b1dbee0dc087a22bd42af7241ae', 'classes_used': ['DepthAnything_V2', 'DownloadAndLoadDepthAnythingV2Model'], 'pip_packages': ['opencv-python-headless', 'transformers'], 'status': 'discovered'}, 'ComfyUI-KJNodes': {'commit': 'b7646ad70a7daa7aeb919ca542274758d26ba2df', 'url': 'https://github.com/kijai/ComfyUI-KJNodes.git', 'class_schema_sha256': '1beaf129c8fa26175d89a28f9ca10d08b5ac27c8fc9bff920263fcbba17cb691', 'classes_used': ['GetImageRangeFromBatch', 'GetImageSizeAndCount', 'ImageResizeKJv2'], 'pip_packages': ['matplotlib'], 'status': 'discovered'}, 'ComfyUI-VideoHelperSuite': {'commit': '4ee72c065db22c9d96c2427954dc69e7b908444b', 'url': 'https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite.git', 'class_schema_sha256': '8391e679554eecd5d324a3e34a713ff240e619e3a07476587845ba18c9fae310', 'classes_used': ['VHS_LoadVideo', 'VHS_VideoCombine'], 'pip_packages': [], 'status': 'discovered'}, 'ComfyUI-WanVideoWrapper': {'commit': 'df8f3e49daaad117cf3090cc916c83f3d001494c', 'url': 'https://github.com/kijai/ComfyUI-WanVideoWrapper.git', 'class_schema_sha256': '80187858cc6ec371c9860fd9ca5fcf5174324d75782046657e252492512d115f', 'classes_used': ['LoadWanVideoT5TextEncoder', 'WanVideoBlockSwap', 'WanVideoDecode', 'WanVideoExperimentalArgs', 'WanVideoModelLoader', 'WanVideoSLG', 'WanVideoSampler', 'WanVideoTextEncode', 'WanVideoTorchCompileSettings', 'WanVideoVACEEncode', 'WanVideoVACEModelSelect', 'WanVideoVACEStartToEndFrame', 'WanVideoVAELoader'], 'pip_packages': ['onnx', 'opencv-python-headless'], 'status': 'discovered'}},
    source_path='workflow_corpus/custom_nodes/wanvideo_wrapper/kijai/wan13b_vace.json',
    source_id='wan13b_vace',
    source_type='api',
    source_workflow_path='workflow_corpus/custom_nodes/wanvideo_wrapper/kijai/wan13b_vace.json',
    source_hash='sha256:06cf3b68602617d785d1ae094ac8e978d0c75fcd3e437f8fd8dd677d6c3f2074',
    output_mode='ready_template',
    ready_id='video/wanvideo_wrapper_13b_vace',
    provenance={'source_path': 'workflow_corpus/custom_nodes/wanvideo_wrapper/kijai/wan13b_vace.json', 'source_id': 'wan13b_vace', 'source_type': 'api', 'source_workflow_path': 'workflow_corpus/custom_nodes/wanvideo_wrapper/kijai/wan13b_vace.json', 'source_hash': 'sha256:06cf3b68602617d785d1ae094ac8e978d0c75fcd3e437f8fd8dd677d6c3f2074', 'output_mode': 'ready_template', 'ready_id': 'video/wanvideo_wrapper_13b_vace', 'source_workflow': 'workflow_corpus/custom_nodes/wanvideo_wrapper/kijai/wan13b_vace.json'},
)

def build() -> VibeWorkflow:
    """Build the workflow (auto-generated)."""
    wf = new_workflow(READY_METADATA, source_path=__file__)

    loadwanvideot5textencoder = LoadWanVideoT5TextEncoder(model_name=MODEL_NAME)
    wanvideotorchcompilesettings = WanVideoTorchCompileSettings()
    wanvideovaeloader = WanVideoVAELoader(model_name=MODEL_NAME_2)

    wanvideoblockswap = WanVideoBlockSwap(
        blocks_to_swap=0,
        use_non_blocking=True,
        vace_blocks_to_swap=15,
    )

    wanvideoteacache = WanVideoTeaCache(
        rel_l1_thresh=0.10000000000000002,
        start_step=0,
        use_coefficients=TRUE,
    )

    # Inputs
    image, mask = LoadImage(
        image='replicate-prediction-5cvynz9d91rgg0cfsvqschdpww-0.webp',
        unused_widget_1=IMAGE,
    )

    wanvideoexperimentalargs = WanVideoExperimentalArgs(cfg_zero_star=True)

    wanvideoslg = WanVideoSLG(
        blocks=V_8,
        start_percent=0.30000000000000004,
        end_percent=0.7000000000000002,
    )

    image_load, mask_load = LoadImage(
        image='replicate-prediction-5cvynz9d91rgg0cfsvqschdpww-3.webp',
        unused_widget_1=IMAGE,
    )

    wanvideoteacache_2 = WanVideoTeaCache(
        rel_l1_thresh=0.10000000000000002,
        start_step=0,
        use_coefficients=TRUE,
    )

    wanvideoslg_2 = WanVideoSLG(
        blocks=V_8,
        start_percent=0.30000000000000004,
        end_percent=0.7100000000000002,
    )

    wanvideoexperimentalargs_2 = WanVideoExperimentalArgs(cfg_zero_star=True)

    image_load_2, mask_load_2 = LoadImage(
        image='hunhyuanwolf.png',
        unused_widget_1=IMAGE,
    )

    image_load_3, frame_count, audio, video_info = VHS_LoadVideo(
        video=WOLF_INTERPOLATED_MP4,
        videopreview={'hidden': False, 'paused': False, 'params': {'filename': 'wolf_interpolated.mp4', 'type': 'input', 'format': 'video/mp4', 'force_rate': 0, 'custom_width': 0, 'custom_height': 0, 'frame_load_cap': 0, 'skip_first_frames': 0, 'select_every_nth': 1}},
        **{'choose video to upload': 'image'},
    )

    downloadandloaddepthanythingv2model = DownloadAndLoadDepthAnythingV2Model(
        model=MODEL_NAME_3,
    )

    wanvideoslg_3 = WanVideoSLG(
        blocks=V_8,
        start_percent=0.30000000000000004,
        end_percent=0.7000000000000002,
    )

    wanvideoexperimentalargs_3 = WanVideoExperimentalArgs(cfg_zero_star=True)

    image_load_4, frame_count_load, audio_load, video_info_load = VHS_LoadVideo(
        video=WOLF_INTERPOLATED_MP4,
        videopreview={'hidden': False, 'paused': False, 'params': {'filename': 'wolf_interpolated.mp4', 'type': 'input', 'format': 'video/mp4', 'force_rate': 0, 'custom_width': 0, 'custom_height': 0, 'frame_load_cap': 0, 'skip_first_frames': 0, 'select_every_nth': 1}},
        **{'choose video to upload': 'image'},
    )

    wanvideoteacache_3 = WanVideoTeaCache(
        rel_l1_thresh=0.10000000000000002,
        start_step=0,
        use_coefficients=TRUE,
    )

    wanvideovacemodelselect = WanVideoVACEModelSelect(vace_model=VACE_MODEL_NAME)

    wanvideomodelloader = WanVideoModelLoader(
        model=MODEL_NAME_4,
        base_precision='fp16',
        vace_model=wanvideovacemodelselect,
    )

    images, masks = ImagePadKJ(
        bottom=128,
        extra_padding=COLOR,
        pad_mode='255,255,255',
        unused_widget_0=0,
        image=image_load_2,
    )

    image_image, width, height, mask_image = ImageResizeKJv2(
        upscale_method=LANCZOS,
        keep_proportion=CROP,
        pad_color=V_172_172_172,
        image=image_load_4,
    )

    image_image_2, width_image, height_image, mask_image_2 = ImageResizeKJv2(
        width=640,
        height=640,
        upscale_method=LANCZOS,
        keep_proportion=CROP,
        pad_color=V_172_172_172,
        divisible_by=16,
        image=image,
    )

    image_image_3, width_image_2, height_image_2, mask_image_3 = ImageResizeKJv2(
        upscale_method=LANCZOS,
        keep_proportion=CROP,
        pad_color=V_172_172_172,
        divisible_by=16,
        image=image_load_3,
    )

    wanvideotextencode = WanVideoTextEncode(
        positive_prompt=DEFAULT_PROMPT,
        negative_prompt=DEFAULT_NEGATIVE,
        model_to_offload=wanvideomodelloader,
        t5=loadwanvideot5textencoder,
    )

    addlabel = AddLabel(
        text_x=2,
        text_y=48,
        height=32,
        font_size=WHITE,
        font_color=BLACK,
        label_color=FREEMONO_TTF,
        font='start_frame',
        text=UP,
        unused_widget_0=10,
        image=image_image_2,
    )

    wanvideotextencode_2 = WanVideoTextEncode(
        positive_prompt=DEFAULT_PROMPT_2,
        negative_prompt=DEFAULT_NEGATIVE_2,
        model_to_offload=wanvideomodelloader,
        t5=loadwanvideot5textencoder,
    )

    depthanything_v2 = DepthAnything_V2(
        da_model=downloadandloaddepthanythingv2model,
        images=image_image_3,
    )

    wanvideotextencode_3 = WanVideoTextEncode(
        positive_prompt=DEFAULT_PROMPT_2,
        negative_prompt=DEFAULT_NEGATIVE_2,
        model_to_offload=wanvideomodelloader,
        t5=loadwanvideot5textencoder,
    )

    images_image, masks_image = ImagePadKJ(
        bottom=128,
        extra_padding=COLOR,
        pad_mode='127,127,127',
        unused_widget_0=0,
        image=image_image,
    )

    image_image_4, width_image_3, height_image_3, mask_image_4 = ImageResizeKJv2(
        upscale_method=LANCZOS,
        keep_proportion=CROP,
        pad_color=V_172_172_172,
        divisible_by=16,
        width=width_image,
        height=height_image,
        image=image_load,
    )

    image_image_5, width_image_4, height_image_4, mask_image_5 = ImageResizeKJv2(
        upscale_method=LANCZOS,
        keep_proportion=PAD,
        pad_color=V_255_255_255,
        divisible_by=16,
        width=width_image_2,
        height=height_image_2,
        image=images,
    )

    image_image_6, width_image_5, height_image_5, mask_image_6 = ImageResizeKJv2(
        upscale_method=LANCZOS,
        keep_proportion=PAD,
        pad_color=V_255_255_255,
        divisible_by=16,
        width=width_image_2,
        height=height_image_2,
        image=image_load_2,
    )

    images_wan, masks_wan = WanVideoVACEStartToEndFrame(
        num_frames=DEFAULT_FRAMES,
        empty_frame_level=0.5000000000000001,
        end_image=image_image_4,
        start_image=image_image_2,
    )

    addlabel_2 = AddLabel(
        text_x=2,
        text_y=48,
        height=32,
        font_size=WHITE,
        font_color=BLACK,
        label_color=FREEMONO_TTF,
        font='end_frame',
        text=UP,
        unused_widget_0=10,
        image=image_image_4,
    )

    addlabel_3 = AddLabel(
        text_x=2,
        text_y=48,
        height=32,
        font_size=WHITE,
        font_color=BLACK,
        label_color=FREEMONO_TTF,
        font='reference image',
        text=UP,
        unused_widget_0=10,
        image=image_image_5,
    )

    addlabel_4 = AddLabel(
        text_x=2,
        text_y=48,
        height=32,
        font_size=WHITE,
        font_color=BLACK,
        label_color=FREEMONO_TTF,
        font='control_video',
        text=UP,
        unused_widget_0=10,
        image=depthanything_v2,
    )

    # Outputs
    vhs_videocombine = VHS_VideoCombine(
        frame_rate=16,
        filename_prefix='WanVideoWrapper_VACE_startendframe',
        format=VIDEO_H264_MP4,
        save_output=False,
        crf=19,
        pix_fmt=YUV420P,
        save_metadata=True,
        trim_to_audio=False,
        videopreview={'hidden': False, 'paused': False, 'params': {'filename': 'WanVideoWrapper_VACE_startendframe_00001.mp4', 'subfolder': '', 'type': 'temp', 'format': 'video/h264-mp4', 'frame_rate': 16, 'workflow': 'WanVideoWrapper_VACE_startendframe_00001.png', 'fullpath': 'N:\\AI\\ComfyUI\\temp\\WanVideoWrapper_VACE_startendframe_00001.mp4'}},
        images=depthanything_v2,
    )

    addlabel_5 = AddLabel(
        text_x=2,
        text_y=48,
        height=32,
        font_size=WHITE,
        font_color=BLACK,
        label_color=FREEMONO_TTF,
        font='input',
        text=UP,
        unused_widget_0=10,
        image=images_image,
    )

    image_get, width_get, height_get, count = GetImageSizeAndCount(image=images_image)
    image_get_2, mask_get = GetImageRangeFromBatch(images=images_image)
    image_get_3, mask_get_2 = GetImageRangeFromBatch(masks=masks_image)

    images_wan_2, masks_wan_2 = WanVideoVACEStartToEndFrame(
        empty_frame_level=0.5000000000000001,
        num_frames=frame_count,
        control_images=depthanything_v2,
        start_image=image_image_6,
    )

    previewimage = PreviewImage(images=image_image_5)

    image_get_4, width_get_2, height_get_2, count_get = GetImageSizeAndCount(
        image=images_wan,
    )

    imageconcatmulti = ImageConcatMulti(
        direction=True,
        match_image_size=None,
        unused_widget_1=DOWN,
        image_1=addlabel,
        image_2=addlabel_2,
    )

    image_get_5, width_get_3, height_get_3, count_get_2 = GetImageSizeAndCount(
        image=images_wan_2,
    )

    imageconcatmulti_2 = ImageConcatMulti(
        direction=True,
        match_image_size=None,
        unused_widget_1=DOWN,
        image_1=addlabel_3,
        image_2=addlabel_4,
    )

    wanvideovaceencode = WanVideoVACEEncode(
        strength=0,
        vace_start_percent=1,
        vace_end_percent=False,
        unused_widget_0=480,
        width=width_get,
        height=height_get,
        num_frames=count,
        input_frames=image_get,
        input_masks=masks_image,
        vae=wanvideovaeloader,
    )

    previewimage_2 = PreviewImage(images=image_get_2)
    previewimage_3 = PreviewImage(images=images_wan_2)
    maskpreview = MaskPreview(mask=masks_wan_2)
    maskpreview_2 = MaskPreview(mask=masks_wan)
    maskpreview_3 = MaskPreview(mask=mask_get_2)

    wanvideovaceencode_2 = WanVideoVACEEncode(
        strength=0,
        vace_start_percent=1,
        vace_end_percent=False,
        unused_widget_0=480,
        width=width_get_2,
        height=height_get_2,
        num_frames=count_get,
        input_frames=image_get_4,
        input_masks=masks_wan,
        ref_images=image_image_2,
        vae=wanvideovaeloader,
    )

    previewimage_4 = PreviewImage(images=image_get_4)

    wanvideovaceencode_3 = WanVideoVACEEncode(
        strength=0,
        vace_start_percent=1,
        vace_end_percent=False,
        unused_widget_0=480,
        width=width_get_3,
        height=height_get_3,
        num_frames=count_get_2,
        input_frames=image_get_5,
        input_masks=masks_wan_2,
        ref_images=image_image_5,
        vae=wanvideovaeloader,
    )

    samples, denoised_samples = WanVideoSampler(
        steps=20,
        cfg=GUIDE_STRENGTH,
        shift=8.000000000000002,
        seed=DEFAULT_SEED,
        start_step=VALUE,
        unused_widget_4=FIXED,
        cache_args=wanvideoteacache_3,
        experimental_args=wanvideoexperimentalargs_3,
        image_embeds=wanvideovaceencode,
        model=wanvideomodelloader,
        slg_args=wanvideoslg_3,
        text_embeds=wanvideotextencode_3,
    )

    samples_wan, denoised_samples_wan = WanVideoSampler(
        steps=20,
        cfg=GUIDE_STRENGTH,
        shift=8.000000000000002,
        seed=DEFAULT_SEED,
        start_step=VALUE,
        unused_widget_4=FIXED,
        cache_args=wanvideoteacache,
        experimental_args=wanvideoexperimentalargs,
        image_embeds=wanvideovaceencode_2,
        model=wanvideomodelloader,
        slg_args=wanvideoslg,
        text_embeds=wanvideotextencode,
    )

    samples_wan_2, denoised_samples_wan_2 = WanVideoSampler(
        steps=20,
        cfg=GUIDE_STRENGTH,
        shift=8.000000000000002,
        start_step=VALUE,
        unused_widget_4=FIXED,
        cache_args=wanvideoteacache_2,
        experimental_args=wanvideoexperimentalargs_2,
        image_embeds=wanvideovaceencode_3,
        model=wanvideomodelloader,
        slg_args=wanvideoslg_2,
        text_embeds=wanvideotextencode_2,
    )

    wanvideodecode = WanVideoDecode(samples=samples, vae=wanvideovaeloader)
    wanvideodecode_2 = WanVideoDecode(samples=samples_wan, vae=wanvideovaeloader)
    wanvideodecode_3 = WanVideoDecode(samples=samples_wan_2, vae=wanvideovaeloader)

    image_get_6, width_get_4, height_get_4, count_get_3 = GetImageSizeAndCount(
        image=wanvideodecode,
    )

    image_get_7, width_get_5, height_get_5, count_get_4 = GetImageSizeAndCount(
        image=wanvideodecode_2,
    )

    image_get_8, width_get_6, height_get_6, count_get_5 = GetImageSizeAndCount(
        image=wanvideodecode_3,
    )

    emptyimage = EmptyImage(width=8, height=height_get_4)
    emptyimage_2 = EmptyImage(width=8, height=height_get_5)
    emptyimage_3 = EmptyImage(width=8, height=height_get_6)

    imageconcatmulti_3 = ImageConcatMulti(
        inputcount=3,
        direction=True,
        match_image_size=None,
        unused_widget_1=LEFT,
        image_1=image_get_6,
        image_2=emptyimage,
        image_3=addlabel_5,
    )

    imageconcatmulti_4 = ImageConcatMulti(
        inputcount=3,
        direction=True,
        match_image_size=None,
        unused_widget_1=LEFT,
        image_1=image_get_7,
        image_2=emptyimage_2,
        image_3=imageconcatmulti,
    )

    imageconcatmulti_5 = ImageConcatMulti(
        inputcount=3,
        direction=True,
        match_image_size=None,
        unused_widget_1=LEFT,
        image_1=image_get_8,
        image_2=emptyimage_3,
        image_3=imageconcatmulti_2,
    )

    vhs_videocombine_2 = VHS_VideoCombine(
        frame_rate=16,
        filename_prefix='WanVideoWrapper_VACE_outpaint',
        format=VIDEO_H264_MP4,
        save_output=False,
        crf=19,
        pix_fmt=YUV420P,
        save_metadata=True,
        trim_to_audio=False,
        videopreview={'hidden': False, 'paused': False, 'params': {'filename': 'WanVideoWrapper_VACE_outpaint_00002.mp4', 'subfolder': '', 'type': 'temp', 'format': 'video/h264-mp4', 'frame_rate': 16, 'workflow': 'WanVideoWrapper_VACE_outpaint_00002.png', 'fullpath': 'N:\\AI\\ComfyUI\\temp\\WanVideoWrapper_VACE_outpaint_00002.mp4'}},
        images=imageconcatmulti_3,
    )

    vhs_videocombine_3 = VHS_VideoCombine(
        frame_rate=16,
        filename_prefix='WanVideoWrapper_VACE_startendframe',
        format=VIDEO_H264_MP4,
        save_output=False,
        crf=19,
        pix_fmt=YUV420P,
        save_metadata=True,
        trim_to_audio=False,
        videopreview={'hidden': False, 'paused': False, 'params': {'filename': 'WanVideoWrapper_VACE_startendframe_00005.mp4', 'subfolder': '', 'type': 'temp', 'format': 'video/h264-mp4', 'frame_rate': 16, 'workflow': 'WanVideoWrapper_VACE_startendframe_00005.png', 'fullpath': 'N:\\AI\\ComfyUI\\temp\\WanVideoWrapper_VACE_startendframe_00005.mp4'}},
        images=imageconcatmulti_4,
    )

    vhs_videocombine_4 = VHS_VideoCombine(
        frame_rate=16,
        filename_prefix='WanVideoWrapper_VACE_startendframe',
        format=VIDEO_H264_MP4,
        save_output=False,
        crf=19,
        pix_fmt=YUV420P,
        save_metadata=True,
        trim_to_audio=False,
        videopreview={'hidden': False, 'paused': False, 'params': {'filename': 'WanVideoWrapper_VACE_startendframe_00011.mp4', 'subfolder': '', 'type': 'temp', 'format': 'video/h264-mp4', 'frame_rate': 16, 'workflow': 'WanVideoWrapper_VACE_startendframe_00011.png', 'fullpath': 'N:\\AI\\ComfyUI\\temp\\WanVideoWrapper_VACE_startendframe_00011.mp4'}},
        images=imageconcatmulti_5,
    )

    return wf.finalize(PUBLIC_INPUT_METADATA, output_node=vhs_videocombine, output_type='VHS_VideoCombine', name='video', artifact_kind='video', mime_type='video/mp4', expected_cardinality='one', filename_prefix='WanVideoWrapper_VACE_startendframe')

