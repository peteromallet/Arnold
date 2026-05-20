# vibecomfy: generated - converted by tools/convert_ready_templates.py
# Edits will be overwritten on regeneration. Put the manual opt-out
# marker on the first line if hand-editing is required.
"""Auto-generated ready_template - see tools/convert_ready_templates.py."""
from __future__ import annotations

from vibecomfy.templates import InputSpec, ModelAsset, ReadyMetadata, finalize, new_workflow, node as raw_call, ref
from vibecomfy.nodes.core import CLIPLoader, CLIPTextEncode, CLIPVisionLoader, LoadImage
from vibecomfy.nodes.kjnodes import ImageResizeKJv2
from vibecomfy.nodes.videohelpersuite import VHS_VideoCombine
from vibecomfy.nodes.wanvideowrapper import LoadWanVideoT5TextEncoder, WanVideoBlockSwap, WanVideoClipVisionEncode, WanVideoDecode, WanVideoImageToVideoEncode, WanVideoLoraSelect, WanVideoModelLoader, WanVideoSampler, WanVideoSetBlockSwap, WanVideoTextEmbedBridge, WanVideoTextEncode, WanVideoTorchCompileSettings, WanVideoVAELoader, WanVideoVRAMManagement


DEFAULT_FRAMES = 5
DEFAULT_NEGATIVE = '色调艳丽，过曝，静态，细节模糊不清，字幕，风格，作品，画作，画面，静止，整体发灰，最差质量，低质量，JPEG压缩残留，丑陋的，残缺的，多余的手指，画得不好的手部，画得不好的脸部，畸形的，毁容的，形态畸形的肢体，手指融合，静止不动的画面，杂乱的背景，三条腿，背景人很多，倒着走'
DEFAULT_PROMPT = "high quality nature video featuring a red panda balancing on a bamboo stem while a bird lands on it's head, on the background there is a waterfall"
DEFAULT_PROMPT_2 = '色调艳丽，过曝，静态，细节模糊不清，字幕，风格，作品，画作，画面，静止，整体发灰，最差质量，低质量，JPEG压缩残留，丑陋的，残缺的，多余的手指，画得不好的手部，画得不好的脸部，畸形的，毁容的，形态畸形的肢体，手指融合，静止不动的画面，杂乱的背景，三条腿，背景人很多，倒着走'
DEFAULT_PROMPT_3 = 'an old man is stroking his beard thoughtfully'
DEFAULT_SEED = 1057359483639287
GUIDE_STRENGTH = 1
MODEL_NAME = 'umt5-xxl-enc-bf16.safetensors'
MODEL_NAME_2 = 'wanvideo\\Wan2_1_VAE_bf16.safetensors'
MODEL_NAME_3 = 'umt5_xxl_fp16.safetensors'
MODEL_NAME_4 = 'clip_vision_h.safetensors'
MODEL_NAME_5 = 'WanVideo\\Lightx2v\\lightx2v_I2V_14B_480p_cfg_step_distill_rank64_bf16.safetensors'
MODEL_NAME_6 = 'WanVideo\\Wan2_1-I2V-14B-480P_fp8_e4m3fn.safetensors'


MODELS = {}

PUBLIC_INPUTS = {
    'model': InputSpec(node=ref('loadwanvideot5textencoder'), field='model_name', default=MODEL_NAME),
    'prompt': InputSpec(node=ref('cliptextencode'), field='text', default=DEFAULT_PROMPT),
    'seed': InputSpec(node=ref('wanvideosampler'), field='seed', default=DEFAULT_SEED),
    'image': InputSpec(node=ref('loadimage'), field='image', default='oldman_upscaled.png'),
    'input_image': InputSpec(node=ref('loadimage'), field='image', default='oldman_upscaled.png'),
    'width': InputSpec(node=ref('imageresizekjv2'), field='width', default=256),
    'height': InputSpec(node=ref('imageresizekjv2'), field='height', default=256),
}

READY_METADATA = ReadyMetadata.build(
    capability='image_to_video',
    inputs=PUBLIC_INPUTS,
    models=MODELS,
    requirements={'models': ['clip_vision_h.safetensors', 'umt5-xxl-enc-bf16.safetensors', 'umt5_xxl_fp16.safetensors', 'wanvideo\\Wan2_1_VAE_bf16.safetensors'], 'custom_nodes': ['ComfyUI-KJNodes', 'ComfyUI-VideoHelperSuite', 'ComfyUI-WanVideoWrapper']},
    custom_node_packs={'ComfyUI-KJNodes': {'commit': 'b7646ad70a7daa7aeb919ca542274758d26ba2df', 'url': 'https://github.com/kijai/ComfyUI-KJNodes.git', 'class_schema_sha256': '1beaf129c8fa26175d89a28f9ca10d08b5ac27c8fc9bff920263fcbba17cb691', 'classes_used': ['ImageResizeKJv2'], 'pip_packages': ['matplotlib'], 'status': 'pinned'}, 'ComfyUI-VideoHelperSuite': {'commit': '4ee72c065db22c9d96c2427954dc69e7b908444b', 'url': 'https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite.git', 'class_schema_sha256': '8391e679554eecd5d324a3e34a713ff240e619e3a07476587845ba18c9fae310', 'classes_used': ['VHS_VideoCombine'], 'pip_packages': [], 'status': 'pinned'}, 'ComfyUI-WanVideoWrapper': {'commit': 'df8f3e49daaad117cf3090cc916c83f3d001494c', 'url': 'https://github.com/kijai/ComfyUI-WanVideoWrapper.git', 'class_schema_sha256': '80187858cc6ec371c9860fd9ca5fcf5174324d75782046657e252492512d115f', 'classes_used': ['LoadWanVideoT5TextEncoder', 'WanVideoBlockSwap', 'WanVideoDecode', 'WanVideoImageToVideoEncode', 'WanVideoLoraSelect', 'WanVideoModelLoader', 'WanVideoSampler', 'WanVideoSetBlockSwap', 'WanVideoTextEmbedBridge', 'WanVideoTextEncode', 'WanVideoTorchCompileSettings', 'WanVideoVAELoader'], 'pip_packages': ['onnx', 'opencv-python-headless'], 'status': 'pinned'}},
    smoke_resolution='256x256x5_frames',
    approach='WanVideoWrapper 2.1 14B image-to-video',
    provenance={'source_workflow': 'workflow_corpus/custom_nodes/wanvideo_wrapper/kijai/wan21_14b_i2v.json'},
)

def build() -> VibeWorkflow:
    """Build the workflow (auto-generated)."""
    with new_workflow(READY_METADATA, source_path=__file__) as wf:

        loadwanvideot5textencoder = LoadWanVideoT5TextEncoder(
            _id='11',
            model_name=MODEL_NAME,
        )
        wf.metadata.setdefault('id_map', {})['loadwanvideot5textencoder'] = loadwanvideot5textencoder.node.id

        wanvideotorchcompilesettings = WanVideoTorchCompileSettings(_id='35')
        wf.metadata.setdefault('id_map', {})['wanvideotorchcompilesettings'] = wanvideotorchcompilesettings.node.id
        wanvideovaeloader = WanVideoVAELoader(_id='38', model_name=MODEL_NAME_2)
        wf.metadata.setdefault('id_map', {})['wanvideovaeloader'] = wanvideovaeloader.node.id
        wanvideoblockswap = WanVideoBlockSwap(
            _id='39',
            blocks_to_swap=10,
            use_non_blocking=True,
        )
        wf.metadata.setdefault('id_map', {})['wanvideoblockswap'] = wanvideoblockswap.node.id

        wanvideovrammanagement = WanVideoVRAMManagement(_id='45', widget_0=1)
        wf.metadata.setdefault('id_map', {})['wanvideovrammanagement'] = wanvideovrammanagement.node.id
        # Loaders
        cliploader = CLIPLoader(_id='48', clip_name=MODEL_NAME_3, type_='wan')
        wf.metadata.setdefault('id_map', {})['cliploader'] = cliploader.node.id
        # Inputs
        loadimage = LoadImage(
            _id='58',
            image='oldman_upscaled.png',
            _outputs=('IMAGE', 'MASK'),
        )
        wf.metadata.setdefault('id_map', {})['loadimage'] = loadimage.node.id

        # Loaders
        clipvisionloader = CLIPVisionLoader(_id='59', clip_name=MODEL_NAME_4)
        wf.metadata.setdefault('id_map', {})['clipvisionloader'] = clipvisionloader.node.id
        wanvideoloraselect = WanVideoLoraSelect(
            _id='69',
            lora=MODEL_NAME_5,
            merge_loras="<details><summary><b>Metadata</b></summary><table border='0' cellpadding='3'><tr><td colspan='2'><b>Metadata</b></td></tr><tr><td>No metadata found</td></tr></table></details>",
        )
        wf.metadata.setdefault('id_map', {})['wanvideoloraselect'] = wanvideoloraselect.node.id

        wanvideomodelloader = WanVideoModelLoader(
            _id='22',
            model=MODEL_NAME_6,
            base_precision='fp16',
            quantization='fp8_e4m3fn',
            lora=wanvideoloraselect,
        )
        wf.metadata.setdefault('id_map', {})['wanvideomodelloader'] = wanvideomodelloader.node.id

        # Conditioning
        cliptextencode = CLIPTextEncode(_id='49', text=DEFAULT_PROMPT, clip=cliploader)
        wf.metadata.setdefault('id_map', {})['cliptextencode'] = cliptextencode.node.id
        cliptextencode_2 = CLIPTextEncode(
            _id='50',
            text=DEFAULT_PROMPT_2,
            clip=cliploader,
        )
        wf.metadata.setdefault('id_map', {})['cliptextencode_2'] = cliptextencode_2.node.id

        imageresizekjv2 = ImageResizeKJv2(
            _id='68',
            width=256,
            height=256,
            upscale_method='lanczos',
            keep_proportion='crop',
            divisible_by=16,
            device='cpu',
            image=loadimage.out('IMAGE'),
            _outputs=('IMAGE', 'WIDTH', 'HEIGHT', 'MASK'),
        )
        wf.metadata.setdefault('id_map', {})['imageresizekjv2'] = imageresizekjv2.node.id

        wanvideotextencode = WanVideoTextEncode(
            _id='16',
            positive_prompt=DEFAULT_PROMPT_3,
            negative_prompt=DEFAULT_NEGATIVE,
            model_to_offload=wanvideomodelloader,
            t5=loadwanvideot5textencoder,
        )
        wf.metadata.setdefault('id_map', {})['wanvideotextencode'] = wanvideotextencode.node.id

        wanvideotextembedbridge = WanVideoTextEmbedBridge(
            _id='46',
            negative=cliptextencode_2,
            positive=cliptextencode,
        )
        wf.metadata.setdefault('id_map', {})['wanvideotextembedbridge'] = wanvideotextembedbridge.node.id

        wanvideoclipvisionencode = WanVideoClipVisionEncode(
            _id='65',
            ratio=0.2,
            clip_vision=clipvisionloader,
            image_1=imageresizekjv2.out('IMAGE'),
        )
        wf.metadata.setdefault('id_map', {})['wanvideoclipvisionencode'] = wanvideoclipvisionencode.node.id

        wanvideosetblockswap = WanVideoSetBlockSwap(
            _id='70',
            block_swap_args=wanvideoblockswap,
            model=wanvideomodelloader,
        )
        wf.metadata.setdefault('id_map', {})['wanvideosetblockswap'] = wanvideosetblockswap.node.id

        wanvideoimagetovideoencode = WanVideoImageToVideoEncode(
            _id='63',
            num_frames=DEFAULT_FRAMES,
            noise_aug_strength=0.03,
            fun_or_fl2v_model=False,
            width=imageresizekjv2.out('WIDTH'),
            height=imageresizekjv2.out('HEIGHT'),
            clip_embeds=wanvideoclipvisionencode,
            start_image=imageresizekjv2.out('IMAGE'),
            vae=wanvideovaeloader,
        )
        wf.metadata.setdefault('id_map', {})['wanvideoimagetovideoencode'] = wanvideoimagetovideoencode.node.id

        wanvideosampler = WanVideoSampler(
            _id='27',
            steps=1,
            cfg=GUIDE_STRENGTH,
            seed=DEFAULT_SEED,
            scheduler='dpm++_sde',
            batched_cfg='',
            image_embeds=wanvideoimagetovideoencode,
            model=wanvideosetblockswap,
            text_embeds=wanvideotextencode,
            _outputs=('SAMPLES', 'DENOISED_SAMPLES'),
        )
        wf.metadata.setdefault('id_map', {})['wanvideosampler'] = wanvideosampler.node.id

        wanvideodecode = WanVideoDecode(
            _id='28',
            normalization='default',
            samples=wanvideosampler.out('SAMPLES'),
            vae=wanvideovaeloader,
        )
        wf.metadata.setdefault('id_map', {})['wanvideodecode'] = wanvideodecode.node.id

        # Outputs
        vhs_videocombine = VHS_VideoCombine(_id='30', images=wanvideodecode)
        wf.metadata.setdefault('id_map', {})['vhs_videocombine'] = vhs_videocombine.node.id

        return wf.finalize(PUBLIC_INPUTS, output_type='VHS_VideoCombine', name='video', artifact_kind='video', mime_type='video/mp4', expected_cardinality='one')

