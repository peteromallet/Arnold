# vibecomfy: generated - converted by tools/convert_ready_templates.py
# Edits will be overwritten on regeneration. Put the manual opt-out
# marker on the first line if hand-editing is required.
"""Auto-generated ready_template - see tools/convert_ready_templates.py."""
from __future__ import annotations

from vibecomfy.templates import InputSpec, ModelAsset, ReadyMetadata, finalize, new_workflow, node as raw_call, ref
from vibecomfy.nodes.core import CLIPLoader, CLIPTextEncode
from vibecomfy.nodes.videohelpersuite import VHS_VideoCombine
from vibecomfy.nodes.wanvideowrapper import LoadWanVideoT5TextEncoder, WanVideoBlockSwap, WanVideoDecode, WanVideoEmptyEmbeds, WanVideoEnhanceAVideo, WanVideoLoraSelectMulti, WanVideoModelLoader, WanVideoSampler, WanVideoSetBlockSwap, WanVideoSetLoRAs, WanVideoTextEmbedBridge, WanVideoTextEncode, WanVideoTorchCompileSettings, WanVideoVAELoader


DEFAULT_FRAMES = 5
DEFAULT_NEGATIVE = '色调艳丽，过曝，静态，细节模糊不清，字幕，风格，作品，画作，画面，静止，整体发灰，最差质量，低质量，JPEG压缩残留，丑陋的，残缺的，多余的手指，画得不好的手部，画得不好的脸部，畸形的，毁容的，形态畸形的肢体，手指融合，静止不动的画面，杂乱的背景，三条腿，背景人很多，倒着走'
DEFAULT_PROMPT = "high quality nature video featuring a red panda balancing on a bamboo stem while a bird lands on it's head, on the background there is a waterfall"
DEFAULT_PROMPT_2 = '色调艳丽，过曝，静态，细节模糊不清，字幕，风格，作品，画作，画面，静止，整体发灰，最差质量，低质量，JPEG压缩残留，丑陋的，残缺的，多余的手指，画得不好的手部，画得不好的脸部，畸形的，毁容的，形态畸形的肢体，手指融合，静止不动的画面，杂乱的背景，三条腿，背景人很多，倒着走'
DEFAULT_SEED = 42
GUIDE_STRENGTH = 1
MODEL_NAME = 'umt5-xxl-enc-bf16.safetensors'
MODEL_NAME_2 = 'WanVideo\\fp8_scaled_kj\\T2V\\Wan2_1-T2V-14B_fp8_e4m3fn_scaled_KJ.safetensors'
MODEL_NAME_3 = 'wanvideo\\Wan2_1_VAE_bf16.safetensors'
MODEL_NAME_4 = 'umt5_xxl_fp16.safetensors'
MODEL_NAME_5 = 'WanVideo\\Lightx2v\\lightx2v_T2V_14B_cfg_step_distill_v2_lora_rank64_bf16.safetensors'


MODELS = {}

PUBLIC_INPUTS = {
    'model': InputSpec(node=ref('loadwanvideot5textencoder'), field='model_name', default=MODEL_NAME),
    'prompt': InputSpec(node=ref('cliptextencode'), field='text', default=DEFAULT_PROMPT),
    'seed': InputSpec(node=ref('wanvideosampler'), field='seed', default=DEFAULT_SEED),
    'width': InputSpec(node=ref('wanvideoemptyembeds'), field='width', default=256),
    'height': InputSpec(node=ref('wanvideoemptyembeds'), field='height', default=256),
}

READY_METADATA = ReadyMetadata.build(
    capability='text_to_video',
    inputs=PUBLIC_INPUTS,
    models=MODELS,
    requirements={'models': ['umt5-xxl-enc-bf16.safetensors', 'umt5_xxl_fp16.safetensors', 'wanvideo\\Wan2_1_VAE_bf16.safetensors'], 'custom_nodes': ['ComfyUI-VideoHelperSuite', 'ComfyUI-WanVideoWrapper']},
    custom_node_packs={'ComfyUI-VideoHelperSuite': {'commit': '4ee72c065db22c9d96c2427954dc69e7b908444b', 'url': 'https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite.git', 'class_schema_sha256': '8391e679554eecd5d324a3e34a713ff240e619e3a07476587845ba18c9fae310', 'classes_used': ['VHS_VideoCombine'], 'pip_packages': [], 'status': 'pinned'}, 'ComfyUI-WanVideoWrapper': {'commit': 'df8f3e49daaad117cf3090cc916c83f3d001494c', 'url': 'https://github.com/kijai/ComfyUI-WanVideoWrapper.git', 'class_schema_sha256': '80187858cc6ec371c9860fd9ca5fcf5174324d75782046657e252492512d115f', 'classes_used': ['LoadWanVideoT5TextEncoder', 'WanVideoBlockSwap', 'WanVideoDecode', 'WanVideoEmptyEmbeds', 'WanVideoLoraSelectMulti', 'WanVideoModelLoader', 'WanVideoSampler', 'WanVideoSetBlockSwap', 'WanVideoSetLoRAs', 'WanVideoTextEmbedBridge', 'WanVideoTextEncode', 'WanVideoTorchCompileSettings', 'WanVideoVAELoader'], 'pip_packages': ['onnx', 'opencv-python-headless'], 'status': 'pinned'}},
    smoke_resolution='256x256x5_frames',
    approach='WanVideoWrapper 2.1 14B text-to-video',
    provenance={'source_workflow': 'workflow_corpus/custom_nodes/wanvideo_wrapper/kijai/wan21_14b_t2v.json'},
)

def build() -> VibeWorkflow:
    """Build the workflow (auto-generated)."""
    with new_workflow(READY_METADATA, source_path=__file__) as wf:

        loadwanvideot5textencoder = LoadWanVideoT5TextEncoder(
            _id='11',
            model_name=MODEL_NAME,
        )
        wf.metadata.setdefault('id_map', {})['loadwanvideot5textencoder'] = loadwanvideot5textencoder.node.id

        wanvideomodelloader = WanVideoModelLoader(
            _id='22',
            model=MODEL_NAME_2,
            base_precision='fp16',
            quantization='fp8_e4m3fn_scaled',
        )
        wf.metadata.setdefault('id_map', {})['wanvideomodelloader'] = wanvideomodelloader.node.id

        wanvideotorchcompilesettings = WanVideoTorchCompileSettings(_id='35')
        wf.metadata.setdefault('id_map', {})['wanvideotorchcompilesettings'] = wanvideotorchcompilesettings.node.id
        wanvideoemptyembeds = WanVideoEmptyEmbeds(
            _id='37',
            height=256,
            num_frames=DEFAULT_FRAMES,
            widget_0=256,
            widget_1=256,
            widget_2=5,
            width=256,
        )
        wf.metadata.setdefault('id_map', {})['wanvideoemptyembeds'] = wanvideoemptyembeds.node.id

        wanvideovaeloader = WanVideoVAELoader(_id='38', model_name=MODEL_NAME_3)
        wf.metadata.setdefault('id_map', {})['wanvideovaeloader'] = wanvideovaeloader.node.id
        wanvideoblockswap = WanVideoBlockSwap(_id='39')
        wf.metadata.setdefault('id_map', {})['wanvideoblockswap'] = wanvideoblockswap.node.id
        # Loaders
        cliploader = CLIPLoader(_id='48', clip_name=MODEL_NAME_4, type_='wan')
        wf.metadata.setdefault('id_map', {})['cliploader'] = cliploader.node.id
        wanvideoenhanceavideo = WanVideoEnhanceAVideo(
            _id='55',
            widget_0=2,
            widget_1=0,
            widget_2=1,
        )
        wf.metadata.setdefault('id_map', {})['wanvideoenhanceavideo'] = wanvideoenhanceavideo.node.id

        wanvideoloraselectmulti = WanVideoLoraSelectMulti(
            _id='60',
            lora_0=MODEL_NAME_5,
            merge_loras=False,
        )
        wf.metadata.setdefault('id_map', {})['wanvideoloraselectmulti'] = wanvideoloraselectmulti.node.id

        wanvideotextencode = WanVideoTextEncode(
            _id='16',
            positive_prompt=DEFAULT_PROMPT,
            negative_prompt=DEFAULT_NEGATIVE,
            t5=loadwanvideot5textencoder,
        )
        wf.metadata.setdefault('id_map', {})['wanvideotextencode'] = wanvideotextencode.node.id

        # Conditioning
        cliptextencode = CLIPTextEncode(_id='49', text=DEFAULT_PROMPT, clip=cliploader)
        wf.metadata.setdefault('id_map', {})['cliptextencode'] = cliptextencode.node.id
        cliptextencode_2 = CLIPTextEncode(
            _id='50',
            text=DEFAULT_PROMPT_2,
            clip=cliploader,
        )
        wf.metadata.setdefault('id_map', {})['cliptextencode_2'] = cliptextencode_2.node.id

        wanvideosetloras = WanVideoSetLoRAs(
            _id='58',
            lora=wanvideoloraselectmulti,
            model=wanvideomodelloader,
        )
        wf.metadata.setdefault('id_map', {})['wanvideosetloras'] = wanvideosetloras.node.id

        wanvideotextembedbridge = WanVideoTextEmbedBridge(
            _id='46',
            negative=cliptextencode_2,
            positive=cliptextencode,
        )
        wf.metadata.setdefault('id_map', {})['wanvideotextembedbridge'] = wanvideotextembedbridge.node.id

        wanvideosetblockswap = WanVideoSetBlockSwap(
            _id='56',
            block_swap_args=wanvideoblockswap,
            model=wanvideosetloras,
        )
        wf.metadata.setdefault('id_map', {})['wanvideosetblockswap'] = wanvideosetblockswap.node.id

        wanvideosampler = WanVideoSampler(
            _id='27',
            steps=1,
            cfg=GUIDE_STRENGTH,
            seed=DEFAULT_SEED,
            scheduler='dpm++_sde',
            widget_14='',
            feta_args=wanvideoenhanceavideo,
            image_embeds=wanvideoemptyembeds,
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

