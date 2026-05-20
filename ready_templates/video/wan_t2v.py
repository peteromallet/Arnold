# vibecomfy: manual
# Promoted during sprint 7 to preserve snapshot parity while curating public output contracts.
"""Text To Video with Wan 2.1 T2V 1.3B.

Public inputs:
    prompt (required): Text prompt
    negative_prompt: Negative text prompt
    seed: Random seed
    steps: Sampling steps
    width: Output width
    height: Output height
    output_fps: Output playback frame rate
    cfg: Classifier-free guidance scale
    sampler_name: Sampler algorithm
    length: Number of output frames

Output: SaveVideo (node 50).

Source:  workflow_corpus/official/video/wan_t2v.json
"""
from __future__ import annotations

from vibecomfy.workflow import VibeWorkflow
from vibecomfy.templates import InputSpec, ModelAsset, ReadyMetadata, finalize, new_workflow, node

_NEGATIVE_PROMPT_DEFAULT = """色调艳丽，过曝，静态，细节模糊不清，字幕，风格，作品，画作，画面，静止，整体发灰，最差质量，低质量，JPEG压缩残留，丑陋的，残缺的，多余的手指，画得不好的手部，画得不好的脸部，畸形的，毁容的，形态畸形的肢体，手指融合，静止不动的画面，杂乱的背景，三条腿，背景人很多，倒着走"""

MODELS = {
    'wan2_1_t2v_1_3b_fp16': ModelAsset(
        filename='wan2.1_t2v_1.3B_fp16.safetensors',
        url='https://huggingface.co/Comfy-Org/Wan_2.1_ComfyUI_repackaged/resolve/main/split_files/diffusion_models/wan2.1_t2v_1.3B_fp16.safetensors',
        subdir='diffusion_models',
    ),
    'umt5_xxl_fp8_e4m3fn_scaled': ModelAsset(
        filename='umt5_xxl_fp8_e4m3fn_scaled.safetensors',
        url='https://huggingface.co/Comfy-Org/Wan_2.1_ComfyUI_repackaged/resolve/main/split_files/text_encoders/umt5_xxl_fp8_e4m3fn_scaled.safetensors',
        subdir='text_encoders',
        hf_revision='main',
    ),
    'wan_2_1_vae': ModelAsset(
        filename='wan_2.1_vae.safetensors',
        url='https://huggingface.co/Comfy-Org/Wan_2.1_ComfyUI_repackaged/resolve/main/split_files/vae/wan_2.1_vae.safetensors',
        subdir='vae',
        hf_revision='main',
    ),
}

PUBLIC_INPUTS = {
    'prompt': InputSpec(node='6', field='text', default='a fox moving quickly in a beautiful winter scenery nature trees mountains daytime tracking camera', type='STRING', required=True, description='Text prompt.', media_semantics='text'),
    'negative_prompt': InputSpec(node='7', field='text', default=_NEGATIVE_PROMPT_DEFAULT, type='STRING', aliases=('negative',), description='Negative text prompt.', media_semantics='text'),
    'seed': InputSpec(node='3', field='seed', default=82628696717253, type='INT', description='Random seed.'),
    'steps': InputSpec(node='3', field='steps', default=30, type='INT', description='Sampling steps.'),
    'width': InputSpec(node='40', field='width', default=832, type='INT', description='Output width.'),
    'height': InputSpec(node='40', field='height', default=480, type='INT', description='Output height.'),
    'output_fps': InputSpec(node='49', field='fps', default=16, type='FLOAT', aliases=('fps',), description='Output playback frame rate.'),
    'cfg': InputSpec(node='3', field='cfg', default=6, type='INT', description='Classifier-free guidance scale.'),
    'sampler_name': InputSpec(node='3', field='sampler_name', default='uni_pc', type='STRING', description='Sampler algorithm.'),
    'length': InputSpec(node='40', field='length', default=33, type='INT', aliases=('frames',), description='Number of output frames.'),
}

# ported from workflow_corpus/official/video/wan_t2v.json (sha256: 6cfcb2bcc842926d462667f1858651a7a73d698591013e4d0370bdc2984a6fea)
READY_METADATA = ReadyMetadata.build(
    template_id='wan_t2v',
    capability='text_to_video',
    inputs=PUBLIC_INPUTS,
    models=MODELS,
    output_prefix='video/ComfyUI',
    provenance={'source_role': 'materialized_ready_python_template', 'source_workflow': 'workflow_corpus/official/video/wan_t2v.json'},
    coverage_tier='required',
    vibecomfy_version='0.1.0',
    comfy_core={'version': '0.18.2', 'tested_at': '2026-05-20T09:19:32.302139+00:00', 'commit': 'f7b38d2eb97207cd834bcc3eb2e8b1d447b96c68', 'status': 'discovered'},
)

READY_METADATA["unbound_inputs"].update({'fps': '49.fps', 'frames': '40.length', 'height': '40.height', 'negative_prompt': '7.text', 'prompt': '6.text', 'seed': '3.seed', 'steps': '3.steps', 'width': '40.width'})

def build() -> VibeWorkflow:
    """Build the workflow (auto-generated)."""
    wf = new_workflow(READY_METADATA, source_path=__file__)

    # ════ LOADERS ════
    base_diffusion_model = node(wf, 'UNETLoader', '37',
        unet_name=MODELS['wan2_1_t2v_1_3b_fp16'].filename,
        weight_dtype='default',
    )
    text_encoder = node(wf, 'CLIPLoader', '38',
        clip_name=MODELS['umt5_xxl_fp8_e4m3fn_scaled'].filename,
        type='wan',
        device='default',
    )
    vae = node(wf, 'VAELoader', '39',
        vae_name=MODELS['wan_2_1_vae'].filename,
    )
    # ════ LATENT ════
    latent = node(wf, 'EmptyHunyuanLatentVideo', '40',
        width=PUBLIC_INPUTS['width'].default,
        height=PUBLIC_INPUTS['height'].default,
        length=PUBLIC_INPUTS['length'].default,
        batch_size=1,
    )
    # ════ TEXT CONDITIONING ════
    positive_prompt = node(wf, 'CLIPTextEncode', '6',
        text=PUBLIC_INPUTS['prompt'].default,
        clip=text_encoder.out('CLIP'),
    )
    negative_prompt = node(wf, 'CLIPTextEncode', '7',
        text=PUBLIC_INPUTS['negative_prompt'].default,
        clip=text_encoder.out('CLIP'),
    )
    # ════ SAMPLING ════
    model_sampling = node(wf, 'ModelSamplingSD3', '48',
        shift=8,
        model=base_diffusion_model.out('MODEL'),
    )
    sampler = node(wf, 'KSampler', '3',
        seed=PUBLIC_INPUTS['seed'].default,
        steps=PUBLIC_INPUTS['steps'].default,
        cfg=PUBLIC_INPUTS['cfg'].default,
        sampler_name=PUBLIC_INPUTS['sampler_name'].default,
        scheduler='simple',
        denoise=1,
        latent_image=latent.out(0),
        model=model_sampling.out('MODEL'),
        negative=negative_prompt.out('CONDITIONING'),
        positive=positive_prompt.out('CONDITIONING'),
    )
    # ════ DECODE ════
    decoded_image = node(wf, 'VAEDecode', '8',
        samples=sampler.out('LATENT'),
        vae=vae.out('VAE'),
    )
    # ════ OUTPUT ════
    video = node(wf, 'CreateVideo', '49',
        fps=PUBLIC_INPUTS['output_fps'].default,
        images=decoded_image.out('IMAGE'),
    )
    saved_video = node(wf, 'SaveVideo', '50',
        filename_prefix='video/ComfyUI',
        format='auto',
        codec='auto',
        video=video.out('VIDEO'),
    )

    return finalize(
        wf,
        PUBLIC_INPUTS,
        READY_METADATA,
        output_node='50',
        output_type='SaveVideo',
        name='video',
        mime_type='video/mp4',
        expected_cardinality='one',
        filename_prefix='video/ComfyUI',
        source_path=__file__,
    )

