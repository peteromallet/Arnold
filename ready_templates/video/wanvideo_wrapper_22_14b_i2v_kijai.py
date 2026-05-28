# vibecomfy: generated
# For hand-editing, run: python -m vibecomfy.cli copy-to-recipe <id>
"""Auto-generated ready_template — use python -m vibecomfy.cli copy-to-recipe <id> for hand-editing."""
from __future__ import annotations

from vibecomfy.templates import InputSpec, ModelAsset, ReadyMetadata, new_workflow
from vibecomfy.nodes.core import LoadImage
from vibecomfy.nodes.kjnodes import GetImageSizeAndCount, INTConstant, ImageResizeKJv2
from vibecomfy.nodes.videohelpersuite import VHS_VideoCombine
from vibecomfy.nodes.wanvideowrapper import CreateCFGScheduleFloatList, LoadWanVideoT5TextEncoder, WanVideoBlockSwap, WanVideoDecode, WanVideoImageToVideoEncode, WanVideoLoraSelect, WanVideoModelLoader, WanVideoSampler, WanVideoSetBlockSwap, WanVideoSetLoRAs, WanVideoTextEncode, WanVideoVAELoader


CLIP_NAME = 'umt5-xxl-enc-bf16.safetensors'
DEFAULT_NEGATIVE = '色调艳丽，过曝，静态，细节模糊不清，字幕，风格，作品，画作，画面，静止，整体发灰，最差质量，低质量，JPEG压缩残留，丑陋的，残缺的，多余的手指，画得不好的手部，画得不好的脸部，畸形的，毁容的，形态畸形的肢体，手指融合，静止不动的画面，杂乱的背景，三条腿，背景人很多，倒着走'
DEFAULT_PROMPT = 'old man gets up and jumps into the lake'
DEFAULT_SEED = 43
DPM_SDE = 'dpm++_sde'
FP16 = 'fp16'
FP8_E4M3FN_SCALED = 'fp8_e4m3fn_scaled'
GUIDE_STRENGTH = 1
LORA_NAME = 'WanVideo/Lightx2v/lightx2v_I2V_14B_480p_cfg_step_distill_rank64_bf16.safetensors'
MODEL_NAME = 'WanVideo/2_2/Wan2_2-I2V-A14B-HIGH_fp8_e4m3fn_scaled_KJ.safetensors'
MODEL_NAME_2 = 'WanVideo/2_2/Wan2_2-I2V-A14B-LOW_fp8_e4m3fn_scaled_KJ.safetensors'
VAE_NAME = 'wanvideo/Wan2_1_VAE_bf16.safetensors'


MODELS = {
    'checkpoint': ModelAsset(url='https://huggingface.co/Kijai/WanVideo_comfy_fp8_scaled/resolve/main/I2V/Wan2_2-I2V-A14B-HIGH_fp8_e4m3fn_scaled_KJ.safetensors', subdir='checkpoints'),
    'checkpoint_2': ModelAsset(url='https://huggingface.co/Kijai/WanVideo_comfy_fp8_scaled/resolve/main/I2V/Wan2_2-I2V-A14B-LOW_fp8_e4m3fn_scaled_KJ.safetensors', subdir='checkpoints'),
    'checkpoint_3': ModelAsset(url='https://huggingface.co/Kijai/WanVideo_comfy/resolve/main/Wan2_1_VAE_bf16.safetensors', subdir='checkpoints'),
    'checkpoint_4': ModelAsset(url='https://huggingface.co/Kijai/WanVideo_comfy/resolve/main/umt5-xxl-enc-bf16.safetensors', subdir='checkpoints'),
    'checkpoint_5': ModelAsset(url='https://huggingface.co/Comfy-Org/Wan_2.1_ComfyUI_repackaged/resolve/main/split_files/text_encoders/umt5_xxl_fp16.safetensors', subdir='checkpoints'),
    'checkpoint_6': ModelAsset(url='https://huggingface.co/Kijai/WanVideo_comfy/resolve/main/Lightx2v/lightx2v_I2V_14B_480p_cfg_step_distill_rank64_bf16.safetensors', subdir='checkpoints'),
}


PUBLIC_INPUT_METADATA = {
    'image': InputSpec(node='7', field='image', default='', type='IMAGE', required=True, aliases=('input_image',), media_semantics='image'),
    'width': InputSpec(node='15', field='width', default=720, type='INT'),
    'height': InputSpec(node='15', field='height', default=720, type='INT'),
    'seed': InputSpec(node='23', field='seed', default=DEFAULT_SEED, type='INT'),
}

READY_METADATA = ReadyMetadata.build(
    capability='image_to_video',
    inputs=PUBLIC_INPUT_METADATA,
    models=MODELS,
    requirements={'custom_nodes': ['ComfyUI-KJNodes', 'ComfyUI-VideoHelperSuite', 'ComfyUI-WanVideoWrapper'], 'custom_node_refs': [{'slug': 'ComfyUI-KJNodes', 'source': 'git', 'version': 'unknown', 'commit': 'b7646ad70a7daa7aeb919ca542274758d26ba2df', 'url': 'https://github.com/kijai/ComfyUI-KJNodes.git'}, {'slug': 'ComfyUI-VideoHelperSuite', 'source': 'git', 'version': 'unknown', 'commit': '4ee72c065db22c9d96c2427954dc69e7b908444b', 'url': 'https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite.git'}, {'slug': 'ComfyUI-WanVideoWrapper', 'source': 'git', 'version': 'unknown', 'commit': 'df8f3e49daaad117cf3090cc916c83f3d001494c', 'url': 'https://github.com/kijai/ComfyUI-WanVideoWrapper.git'}]},
    custom_node_packs={'ComfyUI-KJNodes': {'commit': 'b7646ad70a7daa7aeb919ca542274758d26ba2df', 'url': 'https://github.com/kijai/ComfyUI-KJNodes.git', 'class_schema_sha256': '1beaf129c8fa26175d89a28f9ca10d08b5ac27c8fc9bff920263fcbba17cb691', 'classes_used': ['GetImageSizeAndCount', 'INTConstant', 'ImageResizeKJv2'], 'pip_packages': ['matplotlib'], 'status': 'pinned'}, 'ComfyUI-VideoHelperSuite': {'commit': '4ee72c065db22c9d96c2427954dc69e7b908444b', 'url': 'https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite.git', 'class_schema_sha256': '8391e679554eecd5d324a3e34a713ff240e619e3a07476587845ba18c9fae310', 'classes_used': ['VHS_VideoCombine'], 'pip_packages': [], 'status': 'pinned'}, 'ComfyUI-WanVideoWrapper': {'commit': 'df8f3e49daaad117cf3090cc916c83f3d001494c', 'url': 'https://github.com/kijai/ComfyUI-WanVideoWrapper.git', 'class_schema_sha256': '80187858cc6ec371c9860fd9ca5fcf5174324d75782046657e252492512d115f', 'classes_used': ['CreateCFGScheduleFloatList', 'LoadWanVideoT5TextEncoder', 'WanVideoBlockSwap', 'WanVideoDecode', 'WanVideoImageToVideoEncode', 'WanVideoLoraSelect', 'WanVideoModelLoader', 'WanVideoSampler', 'WanVideoSetBlockSwap', 'WanVideoSetLoRAs', 'WanVideoTextEmbedBridge', 'WanVideoTextEncode', 'WanVideoVAELoader'], 'pip_packages': ['onnx', 'opencv-python-headless'], 'status': 'pinned'}},
    approach='Kijai WanVideoWrapper Wan 2.2 A14B I2V high/low two-phase workflow with Lightx2v LoRA',
    smoke_resolution='832x480x81_frames',
    runtime_note='Worker scratchpads patch image, prompt, seed, resolution, frame count, and force VHS output saving.',
    source_url='https://raw.githubusercontent.com/kijai/ComfyUI-WanVideoWrapper/main/example_workflows/wanvideo_2_2_I2V_A14B_example_WIP.json',
    provenance={'source_workflow': 'ready_templates/video/wanvideo_wrapper_22_14b_i2v_kijai.py'},
)

def build() -> VibeWorkflow:
    """Build the workflow (auto-generated)."""
    wf = new_workflow(READY_METADATA, source_path=__file__)

    loadwanvideot5textencoder = LoadWanVideoT5TextEncoder(_id='1', model_name=CLIP_NAME)

    wanvideomodelloader = WanVideoModelLoader(
        _id='2',
        model=MODEL_NAME,
        base_precision=FP16,
        quantization=FP8_E4M3FN_SCALED,
    )

    wanvideovaeloader = WanVideoVAELoader(_id='3', model_name=VAE_NAME)
    wanvideoblockswap = WanVideoBlockSwap(_id='4', vace_blocks_to_swap=1)

    wanvideoloraselect = WanVideoLoraSelect(
        _id='6',
        lora=LORA_NAME,
        strength=3,
        merge_loras=False,
    )

    # Inputs
    image, _ = LoadImage(_id='7', image='oldman_upscaled.png')

    wanvideomodelloader_2 = WanVideoModelLoader(
        _id='8',
        model=MODEL_NAME_2,
        base_precision=FP16,
        quantization=FP8_E4M3FN_SCALED,
    )

    intconstant = INTConstant(_id='9', value=3)
    intconstant_2 = INTConstant(_id='10', value=6)

    wanvideoloraselect_2 = WanVideoLoraSelect(
        _id='11',
        lora=LORA_NAME,
        merge_loras=False,
    )

    wanvideotextencode = WanVideoTextEncode(
        _id='12',
        positive_prompt=DEFAULT_PROMPT,
        negative_prompt=DEFAULT_NEGATIVE,
        t5=loadwanvideot5textencoder,
    )

    image_2, width, height, _ = ImageResizeKJv2(
        _id='15',
        width=720,
        height=720,
        upscale_method='lanczos',
        keep_proportion='crop',
        divisible_by=32,
        device='cpu',
        image=image,
    )

    wanvideosetblockswap = WanVideoSetBlockSwap(
        _id='16',
        block_swap_args=wanvideoblockswap,
        model=wanvideomodelloader,
    )

    wanvideosetblockswap_2 = WanVideoSetBlockSwap(
        _id='17',
        block_swap_args=wanvideoblockswap,
        model=wanvideomodelloader_2,
    )

    createcfgschedulefloatlist = CreateCFGScheduleFloatList(
        _id='18',
        cfg_scale_start=2,
        cfg_scale_end=2,
        end_percent=0.01,
        steps=intconstant_2,
    )

    wanvideosetloras = WanVideoSetLoRAs(
        _id='20',
        lora=wanvideoloraselect_2,
        model=wanvideosetblockswap_2,
    )

    wanvideosetloras_2 = WanVideoSetLoRAs(
        _id='21',
        lora=wanvideoloraselect,
        model=wanvideosetblockswap,
    )

    wanvideoimagetovideoencode = WanVideoImageToVideoEncode(
        _id='22',
        fun_or_fl2v_model=False,
        width=width,
        height=height,
        start_image=image_2,
        vae=wanvideovaeloader,
    )

    samples, _ = WanVideoSampler(
        _id='23',
        shift=8,
        seed=DEFAULT_SEED,
        scheduler=DPM_SDE,
        add_noise_to_samples='',
        steps=intconstant_2,
        cfg=createcfgschedulefloatlist,
        end_step=intconstant,
        image_embeds=wanvideoimagetovideoencode,
        model=wanvideosetloras_2,
        text_embeds=wanvideotextencode,
    )

    samples_2, _ = WanVideoSampler(
        _id='24',
        cfg=GUIDE_STRENGTH,
        shift=8,
        seed=DEFAULT_SEED,
        scheduler=DPM_SDE,
        add_noise_to_samples='',
        steps=intconstant_2,
        start_step=intconstant,
        image_embeds=wanvideoimagetovideoencode,
        model=wanvideosetloras,
        samples=samples,
        text_embeds=wanvideotextencode,
    )

    wanvideodecode = WanVideoDecode(
        _id='25',
        normalization='default',
        samples=samples_2,
        vae=wanvideovaeloader,
    )

    image_3, _, _, _ = GetImageSizeAndCount(_id='26', image=wanvideodecode)

    # Outputs
    vhs_videocombine = VHS_VideoCombine(
        _id='27',
        frame_rate=16,
        filename_prefix='WanVideo2_2_I2V',
        format='video/h264-mp4',
        save_output=False,
        crf=19,
        pix_fmt='yuv420p',
        save_metadata=True,
        trim_to_audio=False,
        videopreview={'hidden': False, 'params': {'filename': 'WanVideo2_2_I2V_00006.mp4', 'format': 'video/h264-mp4', 'frame_rate': 16, 'fullpath': 'N:\\AI\\ComfyUI\\temp\\WanVideo2_2_I2V_00006.mp4', 'subfolder': '', 'type': 'temp', 'workflow': 'WanVideo2_2_I2V_00006.png'}, 'paused': False},
        images=image_3,
    )

    return wf.finalize(PUBLIC_INPUT_METADATA, output_node=vhs_videocombine, output_type='VHS_VideoCombine', name='video', artifact_kind='video', mime_type='video/mp4', expected_cardinality='one', filename_prefix='WanVideo2_2_I2V')

