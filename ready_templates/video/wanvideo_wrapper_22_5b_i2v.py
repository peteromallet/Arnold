# vibecomfy: generated
# For hand-editing, run: python -m vibecomfy.cli copy-to-recipe <id>
"""Auto-generated ready_template — use python -m vibecomfy.cli copy-to-recipe <id> for hand-editing."""
from __future__ import annotations

from vibecomfy.templates import InputSpec, ReadyMetadata, new_workflow
from vibecomfy.nodes.core import CLIPLoader, CLIPTextEncode, LoadImage
from vibecomfy.nodes.kjnodes import ImageResizeKJv2
from vibecomfy.nodes.videohelpersuite import VHS_VideoCombine
from vibecomfy.nodes.wanvideowrapper import LoadWanVideoT5TextEncoder, WanVideoDecode, WanVideoEasyCache, WanVideoEmptyEmbeds, WanVideoEncode, WanVideoExperimentalArgs, WanVideoModelLoader, WanVideoSLG, WanVideoSampler, WanVideoTextEmbedBridge, WanVideoTextEncode, WanVideoTorchCompileSettings, WanVideoVAELoader


BF16 = 'bf16'
CLIP_NAME = 'umt5_xxl_fp16.safetensors'
DEFAULT_FRAMES = 121
DEFAULT_NEGATIVE = 'Bright tones, overexposed, static, blurred details, subtitles, style, works, paintings, images, static, overall gray, worst quality, low quality, JPEG compression residue, ugly, incomplete, extra fingers, poorly drawn hands, poorly drawn faces, deformed, disfigured, misshapen limbs, fused fingers, still picture, messy background, three legs, many people in the background, walking backwards"'
DEFAULT_PROMPT = '色调艳丽，过曝，静态，细节模糊不清，字幕，风格，作品，画作，画面，静止，整体发灰，最差质量，低质量，JPEG压缩残留，丑陋的，残缺的，多余的手指，画得不好的手部，画得不好的脸部，畸形的，毁容的，形态畸形的肢体，手指融合，静止不动的画面，杂乱的背景，三条腿，背景人很多，倒着走'
DEFAULT_PROMPT_2 = "high quality nature video featuring a red panda balancing on a bamboo stem while a bird lands on it's head, on the background there is a waterfall"
DEFAULT_PROMPT_3 = 'the woman starts to play a violin'
DEFAULT_SEED = 47
DISABLED = 'disabled'
GUIDE_STRENGTH = 5
MODEL_NAME = 'umt5-xxl-enc-bf16.safetensors'
MODEL_NAME_2 = 'wanvideo\\Wan2_2_VAE_bf16.safetensors'
MODEL_NAME_3 = 'WanVideo\\2_2\\wan2.2_ti2v_5B_fp16.safetensors'
OFFLOAD_DEVICE = 'offload_device'


PUBLIC_INPUT_METADATA = {
    'seed': InputSpec(node='27', field='seed', default=DEFAULT_SEED, type='INT'),
    'image': InputSpec(node='58', field='image', default='image (658).png', type='IMAGE', required=True, aliases=('input_image',), media_semantics='image'),
    'width': InputSpec(node='71', field='width', default=1024, type='INT'),
    'height': InputSpec(node='71', field='height', default=1024, type='INT'),
    'prompt': InputSpec(node='49', field='text', default=DEFAULT_PROMPT_2, type='STRING', required=True, media_semantics='text'),
}

READY_METADATA = ReadyMetadata.build(
    capability='unknown',
    inputs=PUBLIC_INPUT_METADATA,
    requirements={'models': ['umt5-xxl-enc-bf16.safetensors', 'umt5_xxl_fp16.safetensors', 'wanvideo\\Wan2_2_VAE_bf16.safetensors']},
    custom_node_packs={'ComfyUI-KJNodes': {'commit': 'b7646ad70a7daa7aeb919ca542274758d26ba2df', 'url': 'https://github.com/kijai/ComfyUI-KJNodes.git', 'class_schema_sha256': '1beaf129c8fa26175d89a28f9ca10d08b5ac27c8fc9bff920263fcbba17cb691', 'classes_used': ['ImageResizeKJv2'], 'pip_packages': ['matplotlib'], 'status': 'discovered'}, 'ComfyUI-VideoHelperSuite': {'commit': '4ee72c065db22c9d96c2427954dc69e7b908444b', 'url': 'https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite.git', 'class_schema_sha256': '8391e679554eecd5d324a3e34a713ff240e619e3a07476587845ba18c9fae310', 'classes_used': ['VHS_VideoCombine'], 'pip_packages': [], 'status': 'discovered'}, 'ComfyUI-WanVideoWrapper': {'commit': 'df8f3e49daaad117cf3090cc916c83f3d001494c', 'url': 'https://github.com/kijai/ComfyUI-WanVideoWrapper.git', 'class_schema_sha256': '80187858cc6ec371c9860fd9ca5fcf5174324d75782046657e252492512d115f', 'classes_used': ['LoadWanVideoT5TextEncoder', 'WanVideoDecode', 'WanVideoEasyCache', 'WanVideoEmptyEmbeds', 'WanVideoEncode', 'WanVideoExperimentalArgs', 'WanVideoModelLoader', 'WanVideoSLG', 'WanVideoSampler', 'WanVideoTextEmbedBridge', 'WanVideoTextEncode', 'WanVideoTorchCompileSettings', 'WanVideoVAELoader'], 'pip_packages': ['onnx', 'opencv-python-headless'], 'status': 'discovered'}},
    provenance={'source_path': '/Users/peteromalley/Documents/reigh-workspace/vibecomfy/workflow_corpus/custom_nodes/wanvideo_wrapper/kijai/wan22_5b_i2v.json', 'source_id': 'wan22_5b_i2v', 'source_type': 'api', 'source_workflow_path': '/Users/peteromalley/Documents/reigh-workspace/vibecomfy/workflow_corpus/custom_nodes/wanvideo_wrapper/kijai/wan22_5b_i2v.json', 'output_mode': 'ready_template', 'ready_id': 'video/wanvideo_wrapper_22_5b_i2v'},
)

def build() -> VibeWorkflow:
    """Build the workflow (auto-generated)."""
    wf = new_workflow(READY_METADATA, source_path=__file__)

    loadwanvideot5textencoder = LoadWanVideoT5TextEncoder(model_name=MODEL_NAME)
    wanvideotorchcompilesettings = WanVideoTorchCompileSettings()
    wanvideovaeloader = WanVideoVAELoader(model_name=MODEL_NAME_2)

    # Loaders
    cliploader = CLIPLoader(clip_name=CLIP_NAME, type_='wan')

    # Inputs
    image, mask = LoadImage(image='image (658).png')

    wanvideoexperimentalargs = WanVideoExperimentalArgs(
        cfg_zero_star=True,
        use_tcfg=True,
    )

    wanvideoslg = WanVideoSLG(blocks='7,8,9', end_percent=0.7)
    wanvideoeasycache = WanVideoEasyCache()

    wanvideomodelloader = WanVideoModelLoader(
        model=MODEL_NAME_3,
        base_precision='fp16_fast',
        attention_mode='sageattn',
        compile_args=wanvideotorchcompilesettings,
    )

    # Conditioning
    cliptextencode = CLIPTextEncode(text=DEFAULT_PROMPT_2, clip=cliploader)
    cliptextencode_2 = CLIPTextEncode(text=DEFAULT_PROMPT, clip=cliploader)

    image_image, width, height, mask_image = ImageResizeKJv2(
        width=1024,
        height=1024,
        upscale_method='lanczos',
        keep_proportion='crop',
        divisible_by=32,
        device='cpu',
        image=image,
    )

    wanvideotextencode = WanVideoTextEncode(
        positive_prompt=DEFAULT_PROMPT_3,
        negative_prompt=DEFAULT_NEGATIVE,
        model_to_offload=wanvideomodelloader,
        t5=loadwanvideot5textencoder,
    )

    wanvideotextembedbridge = WanVideoTextEmbedBridge(
        negative=cliptextencode_2,
        positive=cliptextencode,
    )

    wanvideoencode = WanVideoEncode(
        enable_vae_tiling=272,
        tile_x=144,
        tile_y=128,
        tile_stride_x=0,
        tile_stride_y=1,
        image=image_image,
        vae=wanvideovaeloader,
    )

    wanvideoemptyembeds = WanVideoEmptyEmbeds(
        num_frames=DEFAULT_FRAMES,
        width=width,
        height=height,
        extra_latents=wanvideoencode,
    )

    samples, denoised_samples = WanVideoSampler(
        cfg=GUIDE_STRENGTH,
        shift=8,
        seed=DEFAULT_SEED,
        scheduler='flowmatch_pusa',
        batched_cfg='',
        add_noise_to_samples='',
        cache_args=wanvideoeasycache,
        experimental_args=wanvideoexperimentalargs,
        image_embeds=wanvideoemptyembeds,
        model=wanvideomodelloader,
        slg_args=wanvideoslg,
        text_embeds=wanvideotextencode,
    )

    wanvideodecode = WanVideoDecode(
        normalization='default',
        samples=samples,
        vae=wanvideovaeloader,
    )

    # Outputs
    vhs_videocombine = VHS_VideoCombine(
        frame_rate=24,
        filename_prefix='WanVideoWrapper_5BI2V',
        format='video/h264-mp4',
        save_output=False,
        crf=19,
        pix_fmt='yuv420p',
        save_metadata=True,
        trim_to_audio=False,
        videopreview={'hidden': False, 'paused': False, 'params': {'filename': 'WanVideoWrapper_5BI2V_00004.mp4', 'subfolder': '', 'type': 'temp', 'format': 'video/h264-mp4', 'frame_rate': 24, 'workflow': 'WanVideoWrapper_5BI2V_00004.png', 'fullpath': 'N:\\AI\\ComfyUI\\temp\\WanVideoWrapper_5BI2V_00004.mp4'}},
        images=wanvideodecode,
    )

    return wf.finalize(PUBLIC_INPUT_METADATA, output_node=vhs_videocombine, output_type='VHS_VideoCombine', name='video', artifact_kind='video', mime_type='video/mp4', expected_cardinality='one', filename_prefix='WanVideoWrapper_5BI2V')

