# vibecomfy: generated - converted by tools/convert_ready_templates.py
# Edits will be overwritten on regeneration. Put the manual opt-out
# marker on the first line if hand-editing is required.
"""Auto-generated ready_template - see tools/convert_ready_templates.py."""
from __future__ import annotations

from vibecomfy.templates import InputSpec, ModelAsset, ReadyMetadata, finalize, new_workflow, node as raw_call, ref
from vibecomfy.nodes.core import CLIPLoader, CLIPTextEncode, LoadImage
from vibecomfy.nodes.kjnodes import ImageResizeKJv2
from vibecomfy.nodes.videohelpersuite import VHS_VideoCombine
from vibecomfy.nodes.wanvideowrapper import LoadWanVideoT5TextEncoder, WanVideoDecode, WanVideoEasyCache, WanVideoEmptyEmbeds, WanVideoEncode, WanVideoExperimentalArgs, WanVideoModelLoader, WanVideoSLG, WanVideoSampler, WanVideoTextEmbedBridge, WanVideoTextEncode, WanVideoTorchCompileSettings, WanVideoVAELoader


DEFAULT_FRAMES = 5
DEFAULT_NEGATIVE = 'Bright tones, overexposed, static, blurred details, subtitles, style, works, paintings, images, static, overall gray, worst quality, low quality, JPEG compression residue, ugly, incomplete, extra fingers, poorly drawn hands, poorly drawn faces, deformed, disfigured, misshapen limbs, fused fingers, still picture, messy background, three legs, many people in the background, walking backwards"'
DEFAULT_PROMPT = "high quality nature video featuring a red panda balancing on a bamboo stem while a bird lands on it's head, on the background there is a waterfall"
DEFAULT_PROMPT_2 = '色调艳丽，过曝，静态，细节模糊不清，字幕，风格，作品，画作，画面，静止，整体发灰，最差质量，低质量，JPEG压缩残留，丑陋的，残缺的，多余的手指，画得不好的手部，画得不好的脸部，畸形的，毁容的，形态畸形的肢体，手指融合，静止不动的画面，杂乱的背景，三条腿，背景人很多，倒着走'
DEFAULT_PROMPT_3 = 'the woman starts to play a violin'
DEFAULT_SEED = 47
GUIDE_STRENGTH = 5
MODEL_NAME = 'umt5-xxl-enc-bf16.safetensors'
MODEL_NAME_2 = 'wanvideo\\Wan2_2_VAE_bf16.safetensors'
MODEL_NAME_3 = 'umt5_xxl_fp16.safetensors'
MODEL_NAME_4 = 'WanVideo\\2_2\\wan2.2_ti2v_5B_fp16.safetensors'


MODELS = {}

PUBLIC_INPUTS = {
    'model': InputSpec(node=ref('loadwanvideot5textencoder'), field='model_name', default=MODEL_NAME),
    'prompt': InputSpec(node=ref('cliptextencode'), field='text', default=DEFAULT_PROMPT),
    'seed': InputSpec(node=ref('samples'), field='seed', default=DEFAULT_SEED),
    'image': InputSpec(node=ref('image'), field='image', default='image (658).png'),
    'input_image': InputSpec(node=ref('image'), field='image', default='image (658).png'),
    'width': InputSpec(node=ref('image_image'), field='width', default=256),
    'height': InputSpec(node=ref('image_image'), field='height', default=256),
}

READY_METADATA = ReadyMetadata.build(
    capability='image_to_video',
    inputs=PUBLIC_INPUTS,
    models=MODELS,
    requirements={'models': ['umt5-xxl-enc-bf16.safetensors', 'umt5_xxl_fp16.safetensors', 'wanvideo\\Wan2_2_VAE_bf16.safetensors'], 'custom_nodes': ['ComfyUI-KJNodes', 'ComfyUI-VideoHelperSuite', 'ComfyUI-WanVideoWrapper']},
    custom_node_packs={'ComfyUI-KJNodes': {'commit': 'b7646ad70a7daa7aeb919ca542274758d26ba2df', 'url': 'https://github.com/kijai/ComfyUI-KJNodes.git', 'class_schema_sha256': '1beaf129c8fa26175d89a28f9ca10d08b5ac27c8fc9bff920263fcbba17cb691', 'classes_used': ['ImageResizeKJv2'], 'pip_packages': ['matplotlib'], 'status': 'pinned'}, 'ComfyUI-VideoHelperSuite': {'commit': '4ee72c065db22c9d96c2427954dc69e7b908444b', 'url': 'https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite.git', 'class_schema_sha256': '8391e679554eecd5d324a3e34a713ff240e619e3a07476587845ba18c9fae310', 'classes_used': ['VHS_VideoCombine'], 'pip_packages': [], 'status': 'pinned'}, 'ComfyUI-WanVideoWrapper': {'commit': 'df8f3e49daaad117cf3090cc916c83f3d001494c', 'url': 'https://github.com/kijai/ComfyUI-WanVideoWrapper.git', 'class_schema_sha256': '80187858cc6ec371c9860fd9ca5fcf5174324d75782046657e252492512d115f', 'classes_used': ['LoadWanVideoT5TextEncoder', 'WanVideoDecode', 'WanVideoEasyCache', 'WanVideoEmptyEmbeds', 'WanVideoEncode', 'WanVideoExperimentalArgs', 'WanVideoModelLoader', 'WanVideoSLG', 'WanVideoSampler', 'WanVideoTextEmbedBridge', 'WanVideoTextEncode', 'WanVideoTorchCompileSettings', 'WanVideoVAELoader'], 'pip_packages': ['onnx', 'opencv-python-headless'], 'status': 'pinned'}},
    approach='WanVideoWrapper 2.2 5B image-to-video',
    smoke_resolution='256x256x5_frames',
    provenance={'source_workflow': 'workflow_corpus/custom_nodes/wanvideo_wrapper/kijai/wan22_5b_i2v.json'},
)

def build() -> VibeWorkflow:
    """Build the workflow (auto-generated)."""
    with new_workflow(READY_METADATA, source_path=__file__) as wf:

        loadwanvideot5textencoder = LoadWanVideoT5TextEncoder(model_name=MODEL_NAME)
        wanvideotorchcompilesettings = WanVideoTorchCompileSettings()
        wanvideovaeloader = WanVideoVAELoader(model_name=MODEL_NAME_2)

        # Loaders
        cliploader = CLIPLoader(clip_name=MODEL_NAME_3, type_='wan')

        # Inputs
        image, mask = LoadImage(image='image (658).png')

        wanvideoexperimentalargs = WanVideoExperimentalArgs(
            widget_0='',
            widget_1=True,
            widget_2=False,
            widget_3=0,
            widget_4=False,
            widget_5=1,
            widget_6=1.25,
            widget_7=20,
            widget_8=True,
        )

        wanvideoslg = WanVideoSLG(widget_0='7,8,9', widget_1=0.1, widget_2=0.7)

        wanvideoeasycache = WanVideoEasyCache(
            widget_0=0.015,
            widget_1=10,
            widget_2=-1,
            widget_3='offload_device',
        )

        wanvideomodelloader = WanVideoModelLoader(
            model=MODEL_NAME_4,
            base_precision='fp16',
            compile_args=wanvideotorchcompilesettings,
        )

        # Conditioning
        cliptextencode = CLIPTextEncode(text=DEFAULT_PROMPT, clip=cliploader)
        cliptextencode_2 = CLIPTextEncode(text=DEFAULT_PROMPT_2, clip=cliploader)

        image_image, width, height, mask_image = ImageResizeKJv2(
            width=256,
            height=256,
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
            widget_0=False,
            widget_1=272,
            widget_2=272,
            widget_3=144,
            widget_4=128,
            widget_5=0,
            widget_6=1,
            image=image_image,
            vae=wanvideovaeloader,
        )

        wanvideoemptyembeds = WanVideoEmptyEmbeds(
            num_frames=DEFAULT_FRAMES,
            widget_0=256,
            widget_1=256,
            widget_2=5,
            extra_latents=wanvideoencode,
            height=height,
            width=width,
        )

        samples, denoised_samples = WanVideoSampler(
            steps=1,
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
        vhs_videocombine = VHS_VideoCombine(images=wanvideodecode)

        return wf.finalize(PUBLIC_INPUTS, output_type='VHS_VideoCombine', name='video', artifact_kind='video', mime_type='video/mp4', expected_cardinality='one')

