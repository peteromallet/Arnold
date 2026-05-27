# vibecomfy: generated
# For hand-editing, run: python -m vibecomfy.cli copy-to-recipe <id>
"""Auto-generated ready_template — use python -m vibecomfy.cli copy-to-recipe <id> for hand-editing."""
from __future__ import annotations

from vibecomfy.templates import InputSpec, ReadyMetadata, new_workflow, node as raw_call
from vibecomfy.nodes.core import PreviewImage
from vibecomfy.nodes.kjnodes import GetImagesFromBatchIndexed, INTConstant, ImageResizeKJv2, PreviewAnimation
from vibecomfy.nodes.videohelpersuite import VHS_LoadVideo, VHS_VideoCombine
from vibecomfy.nodes.wanvideowrapper import LoadWanVideoT5TextEncoder, WanVideoControlnet, WanVideoControlnetLoader, WanVideoDecode, WanVideoEasyCache, WanVideoEmptyEmbeds, WanVideoEncode, WanVideoEnhanceAVideo, WanVideoExperimentalArgs, WanVideoModelLoader, WanVideoSLG, WanVideoSampler, WanVideoTextEncode, WanVideoTorchCompileSettings, WanVideoVAELoader


BF16 = 'bf16'
CENTER = 'center'
CPU = 'cpu'
DEFAULT_FPS = 24
DEFAULT_FRAMES = 121
DEFAULT_NEGATIVE = 'Bright tones, overexposed, static, blurred details, subtitles, style, works, paintings, images, static, overall gray, worst quality, low quality, JPEG compression residue, ugly, incomplete, extra fingers, poorly drawn hands, poorly drawn faces, deformed, disfigured, misshapen limbs, fused fingers, still picture, messy background, three legs, many people in the background, walking backwards"'
DEFAULT_PROMPT = "Close-up shot with soft lighting, focusing sharply on the lower half of a young woman's face. Her lips are slightly parted as she blows an enormous bubblegum bubble. The bubble is semi-transparent, shimmering gently under the light, and surprisingly contains a miniature aquarium inside, where two orange-and-white goldfish slowly swim, their fins delicately fluttering as if in an aquatic universe. The background is a pure light blue color."
DEFAULT_SEED = 47
DISABLED = 'disabled'
GUIDE_STRENGTH = 5
MODEL_NAME = 'Wan2_2-TI2V-5B-FastWanFullAttn_bf16.safetensors'
MODEL_NAME_2 = 'wan2.2-ti2v-5b-controlnet-depth-v1/diffusion_pytorch_model.safetensors'
MODEL_NAME_3 = 'umt5-xxl-enc-bf16.safetensors'
MODEL_NAME_4 = 'Wan2_2_VAE_bf16.safetensors'
NEAREST_EXACT = 'nearest-exact'
OFFLOAD_DEVICE = 'offload_device'
STRETCH = 'stretch'
V_0_0_0 = '0, 0, 0'


PUBLIC_INPUT_METADATA = {
    'seed': InputSpec(node='27', field='seed', default=DEFAULT_SEED, type='INT'),
    'fps': InputSpec(node='112', field='fps', default=DEFAULT_FPS, type='FLOAT'),
}

READY_METADATA = ReadyMetadata.build(
    capability='unknown',
    inputs=PUBLIC_INPUT_METADATA,
    requirements={'models': ['Wan2_2_VAE_bf16.safetensors', 'umt5-xxl-enc-bf16.safetensors']},
    custom_node_packs={'ComfyUI-KJNodes': {'commit': 'b7646ad70a7daa7aeb919ca542274758d26ba2df', 'url': 'https://github.com/kijai/ComfyUI-KJNodes.git', 'class_schema_sha256': '1beaf129c8fa26175d89a28f9ca10d08b5ac27c8fc9bff920263fcbba17cb691', 'classes_used': ['INTConstant', 'ImageResizeKJv2', 'PreviewAnimation'], 'pip_packages': ['matplotlib'], 'status': 'discovered'}, 'ComfyUI-VideoHelperSuite': {'commit': '4ee72c065db22c9d96c2427954dc69e7b908444b', 'url': 'https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite.git', 'class_schema_sha256': '8391e679554eecd5d324a3e34a713ff240e619e3a07476587845ba18c9fae310', 'classes_used': ['VHS_LoadVideo', 'VHS_VideoCombine'], 'pip_packages': [], 'status': 'discovered'}, 'ComfyUI-WanVideoWrapper': {'commit': 'df8f3e49daaad117cf3090cc916c83f3d001494c', 'url': 'https://github.com/kijai/ComfyUI-WanVideoWrapper.git', 'class_schema_sha256': '80187858cc6ec371c9860fd9ca5fcf5174324d75782046657e252492512d115f', 'classes_used': ['LoadWanVideoT5TextEncoder', 'WanVideoDecode', 'WanVideoEasyCache', 'WanVideoEmptyEmbeds', 'WanVideoEncode', 'WanVideoExperimentalArgs', 'WanVideoModelLoader', 'WanVideoSLG', 'WanVideoSampler', 'WanVideoTextEncode', 'WanVideoTorchCompileSettings', 'WanVideoVAELoader'], 'pip_packages': ['onnx', 'opencv-python-headless'], 'status': 'discovered'}},
    provenance={'source_path': '/Users/peteromalley/Documents/reigh-workspace/vibecomfy/workflow_corpus/custom_nodes/wanvideo_wrapper/kijai/wan22_5b_i2v_controlnet.json', 'source_id': 'wan22_5b_i2v_controlnet', 'source_type': 'api', 'source_workflow_path': '/Users/peteromalley/Documents/reigh-workspace/vibecomfy/workflow_corpus/custom_nodes/wanvideo_wrapper/kijai/wan22_5b_i2v_controlnet.json', 'output_mode': 'ready_template', 'ready_id': 'video/wanvideo_wrapper_22_5b_i2v_controlnet'},
)

def build() -> VibeWorkflow:
    """Build the workflow (auto-generated)."""
    wf = new_workflow(READY_METADATA, source_path=__file__)

    loadwanvideot5textencoder = LoadWanVideoT5TextEncoder(model_name=MODEL_NAME_3)
    wanvideotorchcompilesettings = WanVideoTorchCompileSettings()
    wanvideovaeloader = WanVideoVAELoader(model_name=MODEL_NAME_4)

    wanvideoexperimentalargs = WanVideoExperimentalArgs(
        cfg_zero_star=True,
        use_tcfg=True,
    )

    wanvideoslg = WanVideoSLG(blocks='7,8,9', end_percent=0.7)
    wanvideoeasycache = WanVideoEasyCache()
    wanvideocontrolnetloader = WanVideoControlnetLoader(model=MODEL_NAME_2)
    wanvideoenhanceavideo = WanVideoEnhanceAVideo()
    intconstant = INTConstant(value=121)
    intconstant_2 = INTConstant(value=1280)
    intconstant_3 = INTConstant(value=704)

    wanvideomodelloader = WanVideoModelLoader(
        model=MODEL_NAME,
        base_precision='fp16_fast',
        attention_mode='sageattn',
        compile_args=wanvideotorchcompilesettings,
    )

    image, frame_count, audio, video_info = VHS_LoadVideo(
        video='bubble.mp4',
        format='Wan',
        videopreview={'hidden': False, 'paused': False, 'params': {'frame_load_cap': 121, 'skip_first_frames': 0, 'force_rate': 0, 'filename': 'bubble.mp4', 'type': 'input', 'format': 'video/mp4', 'select_every_nth': 1}, 'muted': False},
        frame_load_cap=intconstant,
        **{'choose video to upload': 'image'},
    )

    image_image, width, height, mask = ImageResizeKJv2(
        upscale_method=NEAREST_EXACT,
        keep_proportion=STRETCH,
        device=CPU,
        width=intconstant_2,
        height=intconstant_3,
        image=image,
    )

    midas_depthmappreprocessor = raw_call('MiDaS-DepthMapPreprocessor', '104',
        a=6.283185307179586,
        bg_threshold=0.1,
        resolution=512,
        image=image_image,
    )

    getimagesfrombatchindexed = GetImagesFromBatchIndexed(
        indexes='0',
        images=image_image,
    )

    image_image_2, width_image, height_image, mask_image = ImageResizeKJv2(
        upscale_method=NEAREST_EXACT,
        keep_proportion=STRETCH,
        device=CPU,
        width=intconstant_2,
        height=intconstant_3,
        image=midas_depthmappreprocessor.out(0),
    )

    wanvideoencode = WanVideoEncode(
        enable_vae_tiling=272,
        tile_x=144,
        tile_y=128,
        tile_stride_x=0,
        tile_stride_y=1,
        image=getimagesfrombatchindexed,
        vae=wanvideovaeloader,
    )

    # Outputs
    previewimage = PreviewImage(images=getimagesfrombatchindexed)

    wanvideocontrolnet = WanVideoControlnet(
        control_images=image_image_2,
        controlnet=wanvideocontrolnetloader,
        model=wanvideomodelloader,
    )

    wanvideoemptyembeds = WanVideoEmptyEmbeds(
        num_frames=DEFAULT_FRAMES,
        width=intconstant_2,
        height=intconstant_3,
        extra_latents=wanvideoencode,
    )

    previewanimation = PreviewAnimation(fps=DEFAULT_FPS, images=image_image_2)

    wanvideotextencode = WanVideoTextEncode(
        positive_prompt=DEFAULT_PROMPT,
        negative_prompt=DEFAULT_NEGATIVE,
        model_to_offload=wanvideocontrolnet,
        t5=loadwanvideot5textencoder,
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
        feta_args=wanvideoenhanceavideo,
        image_embeds=wanvideoemptyembeds,
        model=wanvideocontrolnet,
        slg_args=wanvideoslg,
        text_embeds=wanvideotextencode,
    )

    wanvideodecode = WanVideoDecode(
        normalization='default',
        samples=samples,
        vae=wanvideovaeloader,
    )

    vhs_videocombine = VHS_VideoCombine(
        frame_rate=24,
        filename_prefix='WanVideoWrapper_5BI2V',
        format='video/h264-mp4',
        save_output=False,
        crf=19,
        pix_fmt='yuv420p',
        save_metadata=True,
        trim_to_audio=False,
        videopreview={'hidden': False, 'paused': False, 'params': {'filename': 'WanVideoWrapper_5BI2V_00007.mp4', 'subfolder': '', 'type': 'temp', 'format': 'video/h264-mp4', 'frame_rate': 24, 'workflow': 'WanVideoWrapper_5BI2V_00007.png', 'fullpath': '/home/user/Projects/ComfyUI/temp/WanVideoWrapper_5BI2V_00007.mp4'}},
        images=wanvideodecode,
    )

    return wf.finalize(PUBLIC_INPUT_METADATA, output_node=vhs_videocombine, output_type='VHS_VideoCombine', name='video', artifact_kind='video', mime_type='video/mp4', expected_cardinality='one', filename_prefix='WanVideoWrapper_5BI2V')

