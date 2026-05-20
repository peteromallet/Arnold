# vibecomfy: manual
# Promoted during sprint 7 to preserve snapshot parity while curating public output contracts.
"""Image editing with Flux 2 Klein 4B.

Public inputs:
    image (required): Image
    prompt (required): Text prompt
    seed: Random seed

Output: SaveImage (node 9).

Source:  workflow_corpus/official/edit/flux2_klein_4b_image_edit_distilled.json

Packs:   ComfyUI-KJNodes
"""
from __future__ import annotations

from vibecomfy.workflow import VibeWorkflow
from vibecomfy.templates import InputSpec, ModelAsset, ReadyMetadata, finalize, new_workflow, node

MODELS = {
    'flux_2_klein_4b_fp8': ModelAsset(
        filename='flux-2-klein-4b-fp8.safetensors',
        url='https://huggingface.co/black-forest-labs/FLUX.2-klein-4b-fp8/resolve/main/flux-2-klein-4b-fp8.safetensors',
        subdir='diffusion_models',
    ),
    'qwen_3_4b': ModelAsset(
        filename='qwen_3_4b.safetensors',
        url='https://huggingface.co/Comfy-Org/z_image_turbo/resolve/main/split_files/text_encoders/qwen_3_4b.safetensors',
        subdir='text_encoders',
    ),
    'flux2_vae': ModelAsset(
        filename='flux2-vae.safetensors',
        url='https://huggingface.co/Comfy-Org/flux2-dev/resolve/main/split_files/vae/flux2-vae.safetensors',
        subdir='vae',
    ),
}

PUBLIC_INPUTS = {
    'image': InputSpec(node='76', field='image', default='handbag_white.png', type='IMAGE', required=True, aliases=('input_image',), description='Image.'),
    'prompt': InputSpec(node='75:74', field='text', default='Change the bag color to blue.', type='STRING', required=True, description='Text prompt.', media_semantics='text'),
    'seed': InputSpec(node='75:73', field='noise_seed', default=43301611940728, type='INT', description='Random seed.'),
}

# ported from workflow_corpus/official/edit/flux2_klein_4b_image_edit_distilled.json (sha256: 0f80c2530a50fad061dea855c55c50f586a331c5f2d3f37efe7fea59b4ab9610)
READY_METADATA = ReadyMetadata.build(
    template_id='flux2_klein_4b_image_edit_distilled',
    capability='image_edit',
    inputs=PUBLIC_INPUTS,
    models=MODELS,
    output_prefix='Flux2-Klein',
    requirements={'custom_nodes': ['ComfyUI-KJNodes'], 'custom_node_refs': [{'slug': 'ComfyUI-KJNodes', 'source': 'git', 'commit': 'b7646ad70a7daa7aeb919ca542274758d26ba2df', 'url': 'https://github.com/kijai/ComfyUI-KJNodes.git'}]},
    provenance={'source_role': 'materialized_ready_python_template', 'source_workflow': 'workflow_corpus/official/edit/flux2_klein_4b_image_edit_distilled.json'},
    coverage_tier='required',
    vibecomfy_version='0.1.0',
    comfy_core={'version': '0.18.2', 'tested_at': '2026-05-20T09:19:32.302139+00:00', 'commit': 'f7b38d2eb97207cd834bcc3eb2e8b1d447b96c68', 'status': 'discovered'},
)

READY_METADATA["unbound_inputs"].update({'image': '76.image', 'prompt': '75:74.text', 'seed': '75:73.noise_seed'})

def build() -> VibeWorkflow:
    """Build the workflow (auto-generated)."""
    wf = new_workflow(READY_METADATA, source_path=__file__)

    # ════ SAMPLING ════
    sampler_kind = node(wf, 'KSamplerSelect', '75:61',
        sampler_name='euler',
    )
    # ════ LOADERS ════
    base_diffusion_model = node(wf, 'UNETLoader', '75:70',
        unet_name=MODELS['flux_2_klein_4b_fp8'].filename,
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
    # ════ INPUTS ════
    input_image_76 = node(wf, 'LoadImage', '76',
        image=PUBLIC_INPUTS['image'].default,
    )
    input_image_2 = node(wf, 'LoadImage', '81',
        image='comfy_logo_blue.png',
    )
    # ════ TEXT CONDITIONING ════
    prompt_embedding = node(wf, 'CLIPTextEncode', '75:74',
        text=PUBLIC_INPUTS['prompt'].default,
        clip=text_encoder.out('CLIP'),
    )
    # ════ IMAGE PREP ════
    image_scale_to_total_pixels = node(wf, 'ImageScaleToTotalPixels', '75:80',
        upscale_method='nearest-exact',
        megapixels=1,
        resolution_steps=1,
        image=input_image_76.out('IMAGE'),
    )
    conditioning_zero_out = node(wf, 'ConditioningZeroOut', '75:82',
        conditioning=prompt_embedding.out('CONDITIONING'),
    )
    get_image_size = node(wf, 'GetImageSize', '75:99',
        image=image_scale_to_total_pixels.out('IMAGE'),
    )
    vaeencode = node(wf, 'VAEEncode', '75:122',
        pixels=image_scale_to_total_pixels.out('IMAGE'),
        vae=vae.out('VAE'),
    )
    flux2_scheduler = node(wf, 'Flux2Scheduler', '75:62',
        steps=4,
        height=get_image_size.out(1),
        width=get_image_size.out(0),
    )
    # ════ LATENT ════
    empty_flux2_latent_image = node(wf, 'EmptyFlux2LatentImage', '75:66',
        batch_size=1,
        width=get_image_size.out(0),
        height=get_image_size.out(1),
    )
    reference_latent_1 = node(wf, 'ReferenceLatent', '75:121',
        conditioning=conditioning_zero_out.out('CONDITIONING'),
        latent=vaeencode.out('LATENT'),
    )
    reference_latent_2 = node(wf, 'ReferenceLatent', '75:123',
        conditioning=prompt_embedding.out('CONDITIONING'),
        latent=vaeencode.out('LATENT'),
    )
    cfg_guider = node(wf, 'CFGGuider', '75:63',
        cfg=1,
        model=base_diffusion_model.out('MODEL'),
        negative=reference_latent_1.out(0),
        positive=reference_latent_2.out(0),
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

