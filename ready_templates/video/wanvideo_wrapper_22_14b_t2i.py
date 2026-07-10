# vibecomfy: generated
# For hand-editing, run: python -m vibecomfy.cli copy-to-recipe <id>
"""Auto-generated ready_template — use python -m vibecomfy.cli copy-to-recipe <id> for hand-editing."""
from __future__ import annotations

from vibecomfy.templates import InputSpec, ModelAsset, ReadyMetadata, new_workflow
from vibecomfy.nodes.core import SaveImage
from vibecomfy.nodes.wanvideowrapper import WanVideoBlockSwap, WanVideoDecode, WanVideoEmptyEmbeds, WanVideoLoraSelectMulti, WanVideoModelLoader, WanVideoSampler, WanVideoSetBlockSwap, WanVideoSetLoRAs, WanVideoTextEncodeCached, WanVideoVAELoader


CLIP_NAME = 'umt5-xxl-enc-bf16.safetensors'
DEFAULT_FRAMES = 1
DEFAULT_NEGATIVE = 'fading, breaking, shot cuts, jumpcuts, blurry, noise, distorted'
DEFAULT_PROMPT = 'A compact cinematic still of a red cube on a clean white tabletop.'
DEFAULT_SEED = 12345
EULER = 'euler'
FP16 = 'fp16'
FP8_E4M3FN_SCALED = 'fp8_e4m3fn_scaled'
GUIDE_STRENGTH = 3.0
GUIDE_STRENGTH_2 = 1.0
LORA__NAME = 'WanVideo/Lightx2v/lightx2v_T2V_14B_cfg_step_distill_v2_lora_rank64_bf16.safetensors'
MODEL_NAME = 'WanVideo/2_2/Wan2_2-T2V-A14B-HIGH_fp8_e4m3fn_scaled_KJ.safetensors'
MODEL_NAME_2 = 'WanVideo/2_2/Wan2_2-T2V-A14B-LOW_fp8_e4m3fn_scaled_KJ.safetensors'
VAE_NAME = 'wanvideo/Wan2_1_VAE_bf16.safetensors'


MODELS = {
    'wan2_2_t2v_a14b_high_fp8_e4m3fn_scaled_kj': ModelAsset(filename='Wan2_2-T2V-A14B-HIGH_fp8_e4m3fn_scaled_KJ.safetensors', url='https://huggingface.co/Kijai/WanVideo_comfy_fp8_scaled/resolve/main/T2V/Wan2_2-T2V-A14B_HIGH_fp8_e4m3fn_scaled_KJ.safetensors', sha256='15384a1da9b5aa463464ba50a596b84f6c0929bfb72ec47df6bb48cb2e0b6f0c', hf_revision='5571ff9d81a631ee97946a703e94911d63214c44', size_bytes=15001361458, subdir='diffusion_models/WanVideo/2_2'),
    'wan2_2_t2v_a14b_low_fp8_e4m3fn_scaled_kj': ModelAsset(url='https://huggingface.co/Kijai/WanVideo_comfy_fp8_scaled/resolve/main/T2V/Wan2_2-T2V-A14B-LOW_fp8_e4m3fn_scaled_KJ.safetensors', sha256='ce74fff05e37f995a0ae845f53510e43f98b838f4e75d846eb3e2929e7f555cc', hf_revision='5571ff9d81a631ee97946a703e94911d63214c44', size_bytes=15001361458, subdir='diffusion_models/WanVideo/2_2'),
    'lightx2v_t2v_14b_cfg_step_distill_v2_lora_rank64_bf16': ModelAsset(url='https://huggingface.co/Kijai/WanVideo_comfy/resolve/main/Lightx2v/lightx2v_T2V_14B_cfg_step_distill_v2_lora_rank64_bf16.safetensors', sha256='37d49218544b9e0bfb8e831d1399f451fbc5068aff6474f42a90c928363c3573', hf_revision='87badb1f794c15daf51db60838a433ca08bb218f', size_bytes=630697104, subdir='loras/WanVideo/Lightx2v'),
    'vae': ModelAsset(url='https://huggingface.co/Kijai/WanVideo_comfy/resolve/main/Wan2_1_VAE_bf16.safetensors', sha256='1ab9a32cc2c740f6e39d80d367ce5dcc28db8c71b79b28670546b8973e9d75f9', hf_revision='87badb1f794c15daf51db60838a433ca08bb218f', size_bytes=253806278, subdir='vae'),
    'text_encoder': ModelAsset(url='https://huggingface.co/Kijai/WanVideo_comfy/resolve/main/umt5-xxl-enc-bf16.safetensors', sha256='4fa971faf306cad919033d5bbe192e571dc08452f800cbf2ec3c73977c01b2cc', hf_revision='87badb1f794c15daf51db60838a433ca08bb218f', size_bytes=11361845464, subdir='text_encoders'),
}


PUBLIC_INPUT_METADATA = {
    'width': InputSpec(node='5', field='width', default=832, type='INT'),
    'height': InputSpec(node='5', field='height', default=480, type='INT'),
    'seed': InputSpec(node='13', field='seed', default=DEFAULT_SEED, type='INT'),
}

READY_METADATA = ReadyMetadata.build(
    capability='text_to_image_single_frame',
    inputs=PUBLIC_INPUT_METADATA,
    models=MODELS,
    requirements={'custom_nodes': ['ComfyUI-WanVideoWrapper'], 'custom_node_refs': [{'slug': 'ComfyUI-WanVideoWrapper', 'source': 'git', 'version': 'unknown', 'commit': 'df8f3e49daaad117cf3090cc916c83f3d001494c', 'url': 'https://github.com/kijai/ComfyUI-WanVideoWrapper.git'}]},
    custom_node_packs={'ComfyUI-WanVideoWrapper': {'commit': 'df8f3e49daaad117cf3090cc916c83f3d001494c', 'url': 'https://github.com/kijai/ComfyUI-WanVideoWrapper.git', 'class_schema_sha256': '80187858cc6ec371c9860fd9ca5fcf5174324d75782046657e252492512d115f', 'classes_used': ['WanVideoBlockSwap', 'WanVideoDecode', 'WanVideoEmptyEmbeds', 'WanVideoLoraSelectMulti', 'WanVideoModelLoader', 'WanVideoSampler', 'WanVideoSetBlockSwap', 'WanVideoSetLoRAs', 'WanVideoTextEncodeCached', 'WanVideoVAELoader'], 'pip_packages': ['onnx', 'opencv-python-headless'], 'status': 'pinned'}},
    approach='Wan 2.2 14B high/low two-phase text-to-video graph decoded as one image frame',
    smoke_resolution='832x480x1_frame',
    runtime_note='Intended to match Reigh wan_2_2_t2i, which forces video_length=1 and returns PNG.',
    provenance={'source_workflow': 'ready_templates/video/wanvideo_wrapper_22_14b_t2i.py'},
)

def build() -> VibeWorkflow:
    """Build the workflow (auto-generated)."""
    wf = new_workflow(READY_METADATA, source_path=__file__)

    text_embeds, _, _ = WanVideoTextEncodeCached(
        _id='1',
        model_name=CLIP_NAME,
        positive_prompt=DEFAULT_PROMPT,
        negative_prompt=DEFAULT_NEGATIVE,
    )

    wanvideomodelloader = WanVideoModelLoader(
        _id='2',
        model=MODEL_NAME,
        base_precision=FP16,
        quantization=FP8_E4M3FN_SCALED,
        widget_1='fp16',
    )

    wanvideovaeloader = WanVideoVAELoader(_id='3', model_name=VAE_NAME)
    wanvideoblockswap = WanVideoBlockSwap(_id='4', blocks_to_swap=30)

    wanvideoemptyembeds = WanVideoEmptyEmbeds(
        _id='5',
        width=832,
        height=480,
        num_frames=DEFAULT_FRAMES,
        widget_2=1,
    )

    wanvideomodelloader_2 = WanVideoModelLoader(
        _id='6',
        model=MODEL_NAME_2,
        base_precision=FP16,
        quantization=FP8_E4M3FN_SCALED,
        widget_1='fp16',
    )

    wanvideoloraselectmulti = WanVideoLoraSelectMulti(
        _id='7',
        lora_0=LORA__NAME,
        merge_loras=False,
        widget_0='WanVideo/Lightx2v/lightx2v_T2V_14B_cfg_step_distill_v2_lora_rank64_bf16.safetensors',
    )

    wanvideoloraselectmulti_2 = WanVideoLoraSelectMulti(
        _id='8',
        lora_0=LORA__NAME,
        merge_loras=False,
        widget_0='WanVideo/Lightx2v/lightx2v_T2V_14B_cfg_step_distill_v2_lora_rank64_bf16.safetensors',
    )

    wanvideosetloras = WanVideoSetLoRAs(
        _id='9',
        lora=wanvideoloraselectmulti_2,
        model=wanvideomodelloader,
    )

    wanvideosetloras_2 = WanVideoSetLoRAs(
        _id='10',
        lora=wanvideoloraselectmulti,
        model=wanvideomodelloader_2,
    )

    wanvideosetblockswap = WanVideoSetBlockSwap(
        _id='11',
        block_swap_args=wanvideoblockswap,
        model=wanvideosetloras,
    )

    wanvideosetblockswap_2 = WanVideoSetBlockSwap(
        _id='12',
        block_swap_args=wanvideoblockswap,
        model=wanvideosetloras_2,
    )

    samples, _ = WanVideoSampler(
        _id='13',
        steps=6,
        cfg=GUIDE_STRENGTH,
        seed=DEFAULT_SEED,
        scheduler=EULER,
        batched_cfg='',
        end_step=2,
        image_embeds=wanvideoemptyembeds,
        model=wanvideosetblockswap,
        text_embeds=text_embeds,
    )

    samples_2, _ = WanVideoSampler(
        _id='14',
        steps=6,
        cfg=GUIDE_STRENGTH_2,
        seed=DEFAULT_SEED,
        scheduler=EULER,
        batched_cfg='',
        start_step=2,
        image_embeds=wanvideoemptyembeds,
        model=wanvideosetblockswap_2,
        samples=samples,
        text_embeds=text_embeds,
    )

    wanvideodecode = WanVideoDecode(
        _id='15',
        normalization='default',
        samples=samples_2,
        vae=wanvideovaeloader,
    )

    # Outputs
    saveimage = SaveImage(
        _id='16',
        filename_prefix='Wan-2-2-T2I',
        images=wanvideodecode,
    )

    return wf.finalize(PUBLIC_INPUT_METADATA, output_node=saveimage, output_type='SaveImage', name='image', artifact_kind='image', mime_type='image/png', expected_cardinality='one', filename_prefix='Wan-2-2-T2I')

