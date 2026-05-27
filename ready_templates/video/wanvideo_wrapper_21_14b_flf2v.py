# vibecomfy: generated
# For hand-editing, run: python -m vibecomfy.cli copy-to-recipe <id>
"""Auto-generated ready_template — use python -m vibecomfy.cli copy-to-recipe <id> for hand-editing."""
from __future__ import annotations

from vibecomfy.templates import InputSpec, ReadyMetadata, new_workflow
from vibecomfy.nodes.core import CLIPLoader, CLIPTextEncode, CLIPVisionLoader, EmptyImage, LoadImage
from vibecomfy.nodes.kjnodes import AddLabel, GetImageSizeAndCount, ImageConcatMulti, ImageResizeKJv2
from vibecomfy.nodes.videohelpersuite import VHS_VideoCombine
from vibecomfy.nodes.wanvideowrapper import LoadWanVideoClipTextEncoder, LoadWanVideoT5TextEncoder, WanVideoBlockSwap, WanVideoClipVisionEncode, WanVideoDecode, WanVideoImageToVideoEncode, WanVideoLoraSelect, WanVideoModelLoader, WanVideoSampler, WanVideoTextEmbedBridge, WanVideoTextEncode, WanVideoTorchCompileSettings, WanVideoVAELoader


BLACK = 'black'
CLIP_NAME = 'umt5_xxl_fp16.safetensors'
CLIP_NAME_2 = 'clip_vision_h.safetensors'
CPU = 'cpu'
CROP = 'crop'
DEFAULT_NEGATIVE = '色调艳丽，过曝，静态，细节模糊不清，字幕，风格，作品，画作，画面，静止，整体发灰，最差质量，低质量，JPEG压缩残留，丑陋的，残缺的，多余的手指，画得不好的手部，画得不好的脸部，畸形的，毁容的，形态畸形的肢体，手指融合，静止不动的画面，杂乱的背景，三条腿，背景人很多，倒着走'
DEFAULT_PROMPT = 'CG动画风格，一只蓝色的小鸟从地面起飞，煽动翅膀。小鸟羽毛细腻，胸前有独特的花纹，背景是蓝天白云，阳光明媚。镜跟随小鸟向上移动，展现出小鸟飞翔的姿态和天空的广阔。近景，仰视视角'
DEFAULT_PROMPT_2 = '色调艳丽，过曝，静态，细节模糊不清，字幕，风格，作品，画作，画面，静止，整体发灰，最差质量，低质量，JPEG压缩残留，丑陋的，残缺的，多余的手指，画得不好的手部，画得不好的脸部，畸形的，毁容的，形态畸形的肢体，手指融合，静止不动的画面，杂乱的背景，三条腿，背景人很多，倒着走'
DEFAULT_SEED = 43
FREEMONO_TTF = 'FreeMono.ttf'
GUIDE_STRENGTH = 1.0000000000000002
IMAGE = 'image'
LANCZOS = 'lanczos'
LORA_NAME = 'Wan21_T2V_14B_lightx2v_cfg_step_distill_lora_rank32.safetensors'
MODEL_NAME = 'umt5-xxl-enc-bf16.safetensors'
MODEL_NAME_2 = 'wanvideo\\Wan2_1_VAE_bf16.safetensors'
MODEL_NAME_3 = 'open-clip-xlm-roberta-large-vit-huge-14_visual_fp16.safetensors'
MODEL_NAME_4 = 'WanVideo\\Wan2_1-FLF2V-14B-720P_fp8_e4m3fn.safetensors'
TR_TD_OUTPUT_TD_TD_B_1_B_X_B_640_B_X_B_640_4_69MB_B_TD_TR = '<tr><td>Output: </td><td><b>1</b> x <b>640</b> x <b>640 | 4.69MB</b></td></tr>'
UP = 'up'
WHITE = 'white'


PUBLIC_INPUT_METADATA = {
    'model': InputSpec(node='1', field='model_name', default=MODEL_NAME),
    'prompt': InputSpec(node='12', field='text', default=DEFAULT_PROMPT),
    'seed': InputSpec(node='23', field='seed', default=DEFAULT_SEED),
    'image': InputSpec(node='7', field='image', default='pasted/image (853).png', aliases=('input_image',)),
    'height': InputSpec(node='17', field='height', default=32),
    'width': InputSpec(node='26', field='width', default=8),
}

READY_METADATA = ReadyMetadata.build(
    capability='unknown',
    inputs=PUBLIC_INPUT_METADATA,
    requirements={'models': ['clip_vision_h.safetensors', 'open-clip-xlm-roberta-large-vit-huge-14_visual_fp16.safetensors', 'umt5-xxl-enc-bf16.safetensors', 'umt5_xxl_fp16.safetensors', 'wanvideo\\Wan2_1_VAE_bf16.safetensors']},
    custom_node_packs={'ComfyUI-KJNodes': {'commit': 'b7646ad70a7daa7aeb919ca542274758d26ba2df', 'url': 'https://github.com/kijai/ComfyUI-KJNodes.git', 'class_schema_sha256': '1beaf129c8fa26175d89a28f9ca10d08b5ac27c8fc9bff920263fcbba17cb691', 'classes_used': ['GetImageSizeAndCount', 'ImageResizeKJv2'], 'pip_packages': ['matplotlib'], 'status': 'discovered'}, 'ComfyUI-VideoHelperSuite': {'commit': '4ee72c065db22c9d96c2427954dc69e7b908444b', 'url': 'https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite.git', 'class_schema_sha256': '8391e679554eecd5d324a3e34a713ff240e619e3a07476587845ba18c9fae310', 'classes_used': ['VHS_VideoCombine'], 'pip_packages': [], 'status': 'discovered'}, 'ComfyUI-WanVideoWrapper': {'commit': 'df8f3e49daaad117cf3090cc916c83f3d001494c', 'url': 'https://github.com/kijai/ComfyUI-WanVideoWrapper.git', 'class_schema_sha256': '80187858cc6ec371c9860fd9ca5fcf5174324d75782046657e252492512d115f', 'classes_used': ['LoadWanVideoT5TextEncoder', 'WanVideoBlockSwap', 'WanVideoDecode', 'WanVideoImageToVideoEncode', 'WanVideoLoraSelect', 'WanVideoModelLoader', 'WanVideoSampler', 'WanVideoTextEmbedBridge', 'WanVideoTextEncode', 'WanVideoTorchCompileSettings', 'WanVideoVAELoader'], 'pip_packages': ['onnx', 'opencv-python-headless'], 'status': 'discovered'}},
    source_path='workflow_corpus/custom_nodes/wanvideo_wrapper/kijai/wan21_14b_flf2v.json',
    source_id='wan21_14b_flf2v',
    source_type='api',
    source_workflow_path='workflow_corpus/custom_nodes/wanvideo_wrapper/kijai/wan21_14b_flf2v.json',
    source_hash='sha256:6a7b43e9091d9ba19b07f8e200d6d217d5b3ed8faa3353089d1ca4620fceff7d',
    output_mode='ready_template',
    ready_id='video/wanvideo_wrapper_21_14b_flf2v',
    provenance={'source_path': 'workflow_corpus/custom_nodes/wanvideo_wrapper/kijai/wan21_14b_flf2v.json', 'source_id': 'wan21_14b_flf2v', 'source_type': 'api', 'source_workflow_path': 'workflow_corpus/custom_nodes/wanvideo_wrapper/kijai/wan21_14b_flf2v.json', 'source_hash': 'sha256:6a7b43e9091d9ba19b07f8e200d6d217d5b3ed8faa3353089d1ca4620fceff7d', 'output_mode': 'ready_template', 'ready_id': 'video/wanvideo_wrapper_21_14b_flf2v', 'source_workflow': 'workflow_corpus/custom_nodes/wanvideo_wrapper/kijai/wan21_14b_flf2v.json'},
)

def build() -> VibeWorkflow:
    """Build the workflow (auto-generated)."""
    wf = new_workflow(READY_METADATA, source_path=__file__)

    loadwanvideot5textencoder = LoadWanVideoT5TextEncoder(model_name=MODEL_NAME)
    wanvideotorchcompilesettings = WanVideoTorchCompileSettings()
    wanvideovaeloader = WanVideoVAELoader(model_name=MODEL_NAME_2)
    wanvideoblockswap = WanVideoBlockSwap(use_non_blocking=True)

    # Loaders
    cliploader = CLIPLoader(clip_name=CLIP_NAME, type_='wan')
    loadwanvideocliptextencoder = LoadWanVideoClipTextEncoder(model_name=MODEL_NAME_3)

    # Inputs
    image, mask = LoadImage(image='pasted/image (853).png', unused_widget_1=IMAGE)
    clipvisionloader = CLIPVisionLoader(clip_name=CLIP_NAME_2)

    image_load, mask_load = LoadImage(
        image='pasted/image (852).png',
        unused_widget_1=IMAGE,
    )

    wanvideoloraselect = WanVideoLoraSelect(lora=LORA_NAME, strength=1.2000000000000002)

    wanvideomodelloader = WanVideoModelLoader(
        model=MODEL_NAME_4,
        base_precision='fp16_fast',
        quantization='fp8_e4m3fn',
        attention_mode='sageattn',
        block_swap_args=wanvideoblockswap,
        compile_args=wanvideotorchcompilesettings,
        lora=wanvideoloraselect,
    )

    # Conditioning
    cliptextencode = CLIPTextEncode(text=DEFAULT_PROMPT, clip=cliploader)
    cliptextencode_2 = CLIPTextEncode(text=DEFAULT_PROMPT_2, clip=cliploader)

    image_image, width, height, mask_image = ImageResizeKJv2(
        width=640,
        height=640,
        upscale_method=LANCZOS,
        keep_proportion=CROP,
        divisible_by=16,
        device=CPU,
        unused_widget_8=TR_TD_OUTPUT_TD_TD_B_1_B_X_B_640_B_X_B_640_4_69MB_B_TD_TR,
        image=image_load,
    )

    wanvideotextencode = WanVideoTextEncode(
        positive_prompt=DEFAULT_PROMPT,
        negative_prompt=DEFAULT_NEGATIVE,
        model_to_offload=wanvideomodelloader,
        t5=loadwanvideot5textencoder,
    )

    wanvideotextembedbridge = WanVideoTextEmbedBridge(
        negative=cliptextencode_2,
        positive=cliptextencode,
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
        image=image_image,
    )

    image_image_2, width_image, height_image, mask_image_2 = ImageResizeKJv2(
        upscale_method=LANCZOS,
        keep_proportion=CROP,
        divisible_by=16,
        device=CPU,
        unused_widget_8=TR_TD_OUTPUT_TD_TD_B_1_B_X_B_640_B_X_B_640_4_69MB_B_TD_TR,
        width=width,
        height=height,
        image=image,
    )

    wanvideoclipvisionencode = WanVideoClipVisionEncode(
        combine_embeds='concat',
        clip_vision=clipvisionloader,
        image_1=image_image,
        image_2=image_image_2,
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
        image=image_image_2,
    )

    imageconcatmulti = ImageConcatMulti(
        direction=True,
        match_image_size=None,
        unused_widget_1='down',
        image_1=addlabel,
        image_2=addlabel_2,
    )

    wanvideoimagetovideoencode = WanVideoImageToVideoEncode(
        tiled_vae=True,
        fun_or_fl2v_model=False,
        width=width_image,
        height=height_image,
        clip_embeds=wanvideoclipvisionencode,
        end_image=image_image_2,
        start_image=image_image,
        vae=wanvideovaeloader,
    )

    samples, denoised_samples = WanVideoSampler(
        steps=6,
        cfg=GUIDE_STRENGTH,
        shift=5.000000000000001,
        seed=DEFAULT_SEED,
        scheduler='dpm++_sde',
        batched_cfg='',
        unused_widget_4='fixed',
        image_embeds=wanvideoimagetovideoencode,
        model=wanvideomodelloader,
        text_embeds=wanvideotextencode,
    )

    wanvideodecode = WanVideoDecode(
        normalization='default',
        samples=samples,
        vae=wanvideovaeloader,
    )

    image_get, width_get, height_get, count = GetImageSizeAndCount(image=wanvideodecode)
    emptyimage = EmptyImage(width=8, height=height_get)

    imageconcatmulti_2 = ImageConcatMulti(
        inputcount=3,
        direction=True,
        match_image_size=None,
        unused_widget_1='left',
        image_1=image_get,
        image_2=emptyimage,
        image_3=imageconcatmulti,
    )

    # Outputs
    vhs_videocombine = VHS_VideoCombine(
        frame_rate=16,
        filename_prefix='WanVideoWrapper_I2V_endframe',
        format='video/h264-mp4',
        save_output=False,
        crf=19,
        pix_fmt='yuv420p',
        save_metadata=True,
        trim_to_audio=False,
        videopreview={'hidden': False, 'paused': False, 'params': {'filename': 'WanVideoWrapper_I2V_endframe_00008.mp4', 'subfolder': '', 'type': 'temp', 'format': 'video/h264-mp4', 'frame_rate': 16, 'workflow': 'WanVideoWrapper_I2V_endframe_00008.png', 'fullpath': 'N:\\AI\\ComfyUI\\temp\\WanVideoWrapper_I2V_endframe_00008.mp4'}},
        images=imageconcatmulti_2,
    )

    return wf.finalize(PUBLIC_INPUT_METADATA, output_node=vhs_videocombine, output_type='VHS_VideoCombine', name='video', artifact_kind='video', mime_type='video/mp4', expected_cardinality='one', filename_prefix='WanVideoWrapper_I2V_endframe')

