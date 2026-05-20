# vibecomfy: manual
# Promoted during sprint 7 to preserve snapshot parity while curating public output contracts.
"""Text-to-image generation with Flux 2 Klein Base 4B.

Public inputs:
    prompt (required): Text prompt
    negative_prompt: Negative text prompt
    seed: Random seed
    width: Output width
    height: Output height

Output: SaveImage (node 9).

Source:  workflow_corpus/official/image/flux2_klein_4b_t2i.json
"""
from __future__ import annotations

from vibecomfy.workflow import VibeWorkflow
from vibecomfy.templates import InputSpec, ModelAsset, ReadyMetadata, finalize, new_workflow, node

_PROMPT_DEFAULT = """A hedgehog wearing a tiny party hat surrounded by confetti, early digital camera style, slight noise, flash photography, candid moment, 2000s digicam aesthetic, festive birthday celebration atmosphere
"""

MODELS = {
    'flux_2_klein_base_4b': ModelAsset(
        filename='flux-2-klein-base-4b.safetensors',
        url='https://huggingface.co/Comfy-Org/flux2-klein/resolve/main/split_files/diffusion_models/flux-2-klein-base-4b.safetensors',
        subdir='diffusion_models',
        sha256='9c5fed22b76baea749d88fc2abe3ad53245e7b21a0d353a762665eea00043b92',
        hf_revision='a9e4ca87c16db4c4e1a16406a9ddb300ab0ae246',
        size_bytes=7751105712,
    ),
    'qwen_3_4b': ModelAsset(
        filename='qwen_3_4b.safetensors',
        url='https://huggingface.co/Comfy-Org/flux2-klein/resolve/main/split_files/text_encoders/qwen_3_4b.safetensors',
        subdir='text_encoders',
        sha256='6c671498573ac2f7a5501502ccce8d2b08ea6ca2f661c458e708f36b36edfc5a',
        hf_revision='a9e4ca87c16db4c4e1a16406a9ddb300ab0ae246',
        size_bytes=8044982048,
    ),
    'flux2_vae': ModelAsset(
        filename='flux2-vae.safetensors',
        url='https://huggingface.co/Comfy-Org/flux2-dev/resolve/main/split_files/vae/flux2-vae.safetensors',
        subdir='vae',
        sha256='d64f3a68e1cc4f9f4e29b6e0da38a0204fe9a49f2d4053f0ec1fa1ca02f9c4b5',
        hf_revision='03d6521e6f6a47396b3f951cbea50f7e6c2f482e',
        size_bytes=336213556,
    ),
    'flux_2_klein_4b': ModelAsset(
        filename='flux-2-klein-4b.safetensors',
        url='https://huggingface.co/Comfy-Org/flux2-klein/resolve/main/split_files/diffusion_models/flux-2-klein-4b.safetensors',
        subdir='diffusion_models',
        sha256='ec3d4e733a771f61c052fb4856c48b336c55eaf2c65487c2a1faeb9bbda7a343',
        hf_revision='a9e4ca87c16db4c4e1a16406a9ddb300ab0ae246',
        size_bytes=7751105712,
    ),
}

PUBLIC_INPUTS = {
    'prompt': InputSpec(node='76', field='value', default=_PROMPT_DEFAULT, type='STRING', required=True, description='Text prompt.', media_semantics='text'),
    'negative_prompt': InputSpec(node='75:67', field='text', default='', type='STRING', aliases=('negative',), description='Negative text prompt.', media_semantics='text'),
    'seed': InputSpec(node='75:73', field='noise_seed', default=0, type='INT', description='Random seed.'),
    'width': InputSpec(node='75:68', field='value', default=1024, type='INT', description='Output width.'),
    'height': InputSpec(node='75:69', field='value', default=1024, type='INT', description='Output height.'),
}

# ported from workflow_corpus/official/image/flux2_klein_4b_t2i.json (sha256: 237b436e577cdd2a97527766637e87af162b4c14fb293c9c269b470b7a2d0166)
READY_METADATA = ReadyMetadata.build(
    template_id='flux2_klein_4b_t2i',
    capability='text_to_image',
    inputs=PUBLIC_INPUTS,
    models=MODELS,
    output_prefix='Flux2-Klein',
    provenance={'source_workflow': 'workflow_corpus/official/image/flux2_klein_4b_t2i.json', 'source_role': 'materialized_ready_python_template'},
    coverage_tier='required',
    vibecomfy_version='0.1.0',
    comfy_core={'version': '0.18.2', 'tested_at': '2026-05-20T09:19:32.302139+00:00', 'commit': 'f7b38d2eb97207cd834bcc3eb2e8b1d447b96c68', 'status': 'discovered'},
)

READY_METADATA["unbound_inputs"].update({'height': '75:69.value', 'negative_prompt': '75:67.text', 'prompt': '76.value', 'seed': '75:73.noise_seed', 'width': '75:68.value'})

def build() -> VibeWorkflow:
    """Build the workflow (auto-generated)."""
    wf = new_workflow(READY_METADATA, source_path=__file__)

    # ════ SAMPLING ════
    sampler_kind = node(wf, 'KSamplerSelect', '75:61',
        sampler_name='euler',
    )
    # ════ INPUTS ════
    param_width = node(wf, 'PrimitiveInt', '75:68', value=PUBLIC_INPUTS['width'].default)
    param_height = node(wf, 'PrimitiveInt', '75:69', value=PUBLIC_INPUTS['height'].default)
    # ════ LOADERS ════
    base_diffusion_model = node(wf, 'UNETLoader', '75:70',
        unet_name=MODELS['flux_2_klein_base_4b'].filename,
        weight_dtype='default',
    )
    text_encoder = node(wf, 'CLIPLoader', '75:71',
        clip_name=MODELS['qwen_3_4b'].filename,
        type='flux2',
        device='default',
    )
    vae = node(wf, 'VAELoader', '75:72',
        vae_name=MODELS['flux2_vae'].filename,
    )
    noise = node(wf, 'RandomNoise', '75:73',
        noise_seed=PUBLIC_INPUTS['seed'].default,
    )
    primitive_string_multiline_76 = node(wf, 'PrimitiveStringMultiline', '76',
        value=PUBLIC_INPUTS['prompt'].default,
    )
    flux2_scheduler = node(wf, 'Flux2Scheduler', '75:62',
        steps=20,
        height=param_height.out('INT'),
        width=param_width.out('INT'),
    )
    # ════ LATENT ════
    empty_flux2_latent_image = node(wf, 'EmptyFlux2LatentImage', '75:66',
        batch_size=1,
        width=param_width.out('INT'),
        height=param_height.out('INT'),
    )
    # ════ TEXT CONDITIONING ════
    negative_prompt = node(wf, 'CLIPTextEncode', '75:67',
        text=PUBLIC_INPUTS['negative_prompt'].default,
        clip=text_encoder.out('CLIP'),
    )
    positive_prompt = node(wf, 'CLIPTextEncode', '75:74',
        text=primitive_string_multiline_76.out(0),
        clip=text_encoder.out('CLIP'),
    )
    cfg_guider = node(wf, 'CFGGuider', '75:63',
        cfg=5,
        model=base_diffusion_model.out('MODEL'),
        negative=negative_prompt.out('CONDITIONING'),
        positive=positive_prompt.out('CONDITIONING'),
    )
    sampled_latent = node(wf, 'SamplerCustomAdvanced', '75:64',
        guider=cfg_guider.out('GUIDER'),
        latent_image=empty_flux2_latent_image.out(0),
        noise=noise.out('NOISE'),
        sampler=sampler_kind.out('SAMPLER'),
        sigmas=flux2_scheduler.out(0),
    )
    # ════ DECODE ════
    decoded_image = node(wf, 'VAEDecode', '75:65',
        samples=sampled_latent.out('OUTPUT'),
        vae=vae.out('VAE'),
    )
    # ════ OUTPUT ════
    image_output = node(wf, 'SaveImage', '9',
        filename_prefix='Flux2-Klein',
        images=decoded_image.out('IMAGE'),
    )

    return finalize(
        wf,
        PUBLIC_INPUTS,
        READY_METADATA,
        output_node='9',
        output_type='SaveImage',
        name='image',
        mime_type='image/png',
        expected_cardinality='one',
        filename_prefix='Flux2-Klein',
        source_path=__file__,
    )

