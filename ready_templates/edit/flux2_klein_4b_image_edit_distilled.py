# vibecomfy: generated — converted by tools/convert_ready_templates.py
# Edits will be overwritten on regeneration. Add a `# vibecomfy: manual`
# marker on the first line if hand-editing is required.
"""Auto-generated ready_template — see tools/convert_ready_templates.py."""
from __future__ import annotations

from vibecomfy.workflow import VibeWorkflow, WorkflowSource
from vibecomfy.registry.ready_template import apply_ready_template_policy


READY_METADATA = {'model_assets': [{'name': 'flux-2-klein-4b-fp8.safetensors',
                   'url': 'https://huggingface.co/black-forest-labs/FLUX.2-klein-4b-fp8/resolve/main/flux-2-klein-4b-fp8.safetensors',
                   'subdir': 'diffusion_models'},
                  {'name': 'qwen_3_4b.safetensors',
                   'url': 'https://huggingface.co/Comfy-Org/z_image_turbo/resolve/main/split_files/text_encoders/qwen_3_4b.safetensors',
                   'subdir': 'text_encoders'},
                  {'name': 'flux2-vae.safetensors',
                   'url': 'https://huggingface.co/Comfy-Org/flux2-dev/resolve/main/split_files/vae/flux2-vae.safetensors',
                   'subdir': 'vae'}],
 'unbound_inputs': {'seed': 4548},
 'ready_template': 'edit/flux2_klein_4b_image_edit_distilled',
 'workflow_template': 'flux2_klein_4b_image_edit_distilled',
 'capability': 'image_edit',
 'source_role': 'materialized_ready_python_template',
 'source_workflow': 'workflow_corpus/official/edit/flux2_klein_4b_image_edit_distilled.json',
 'coverage_tier': 'required',
 'approach': None,
 'runtime_note': None,
 'discord_signal': None}

READY_REQUIREMENTS = {'models': [{'name': 'flux-2-klein-4b-fp8.safetensors',
             'url': 'https://huggingface.co/black-forest-labs/FLUX.2-klein-4b-fp8/resolve/main/flux-2-klein-4b-fp8.safetensors',
             'subdir': 'diffusion_models'},
            {'name': 'qwen_3_4b.safetensors',
             'url': 'https://huggingface.co/Comfy-Org/z_image_turbo/resolve/main/split_files/text_encoders/qwen_3_4b.safetensors',
             'subdir': 'text_encoders'},
            {'name': 'flux2-vae.safetensors',
             'url': 'https://huggingface.co/Comfy-Org/flux2-dev/resolve/main/split_files/vae/flux2-vae.safetensors',
             'subdir': 'vae'}],
 'custom_nodes': []}


def build() -> VibeWorkflow:
    """Build the workflow (auto-generated)."""
    wf = VibeWorkflow(
        READY_METADATA["ready_template"],
        WorkflowSource(
            id=READY_METADATA["ready_template"],
            path=__file__,
            source_type="ready_template",
        ),
    )

    ksamplerselect = _node(wf, 'KSamplerSelect', '75:61',
        sampler_name='euler',
    )
    unetloader = _node(wf, 'UNETLoader', '75:70',
        unet_name='flux-2-klein-4b-fp8.safetensors',
        weight_dtype='default',
    )
    cliploader = _node(wf, 'CLIPLoader', '75:71',
        clip_name='qwen_3_4b.safetensors',
        type='flux2',
        device='default',
    )
    vaeloader = _node(wf, 'VAELoader', '75:72',
        vae_name='flux2-vae.safetensors',
    )
    randomnoise = _node(wf, 'RandomNoise', '75:73',
        noise_seed=43301611940728,
    )
    loadimage = _node(wf, 'LoadImage', '76',
        image='handbag_white.png',
    )
    loadimage_2 = _node(wf, 'LoadImage', '81',
        image='comfy_logo_blue.png',
    )
    cliptextencode = _node(wf, 'CLIPTextEncode', '75:74',
        text='Change the bag color to blue.',
        clip=cliploader.out(0),
    )
    imagescaletototalpixels = _node(wf, 'ImageScaleToTotalPixels', '75:80',
        upscale_method='nearest-exact',
        megapixels=1,
        resolution_steps=1,
        image=loadimage.out(0),
    )
    conditioningzeroout = _node(wf, 'ConditioningZeroOut', '75:82',
        conditioning=cliptextencode.out(0),
    )
    getimagesize = _node(wf, 'GetImageSize', '75:99',
        image=imagescaletototalpixels.out(0),
    )
    vaeencode = _node(wf, 'VAEEncode', '75:122',
        pixels=imagescaletototalpixels.out(0),
        vae=vaeloader.out(0),
    )
    flux2scheduler = _node(wf, 'Flux2Scheduler', '75:62',
        steps=4,
        height=getimagesize.out(1),
        width=getimagesize.out(0),
    )
    emptyflux2latentimage = _node(wf, 'EmptyFlux2LatentImage', '75:66',
        batch_size=1,
        width=getimagesize.out(0),
        height=getimagesize.out(1),
    )
    referencelatent = _node(wf, 'ReferenceLatent', '75:121',
        conditioning=conditioningzeroout.out(0),
        latent=vaeencode.out(0),
    )
    referencelatent_2 = _node(wf, 'ReferenceLatent', '75:123',
        conditioning=cliptextencode.out(0),
        latent=vaeencode.out(0),
    )
    cfgguider = _node(wf, 'CFGGuider', '75:63',
        cfg=1,
        model=unetloader.out(0),
        negative=referencelatent.out(0),
        positive=referencelatent_2.out(0),
    )
    samplercustomadvanced = _node(wf, 'SamplerCustomAdvanced', '75:64',
        guider=cfgguider.out(0),
        latent_image=emptyflux2latentimage.out(0),
        noise=randomnoise.out(0),
        sampler=ksamplerselect.out(0),
        sigmas=flux2scheduler.out(0),
    )
    vaedecode = _node(wf, 'VAEDecode', '75:65',
        samples=samplercustomadvanced.out(0),
        vae=vaeloader.out(0),
    )
    saveimage = _node(wf, 'SaveImage', '9',
        filename_prefix='Flux2-Klein',
        images=vaedecode.out(0),
    )

    wf.finalize_metadata()
    apply_ready_template_policy(wf, READY_METADATA, source_path=__file__, requirements=READY_REQUIREMENTS)
    return wf


def _node(wf: VibeWorkflow, class_type: str, _id: str, _extras: dict | None = None, **kwargs):
    """Create a node, preserving the original node id from the source workflow.

    `_extras` carries kwargs whose names are not valid Python identifiers
    (e.g. "resize_type.multiple") which Python disallows as kwarg syntax.
    They are applied to the new node post-construction.
    """
    from vibecomfy.handles import Handle
    builder = wf.node(class_type, **kwargs)
    if _extras:
        for key, value in _extras.items():
            if isinstance(value, Handle):
                wf.connect(value, f"{builder.node.id}.{key}")
            else:
                builder.node.inputs[key] = value
    if builder.node.id != _id:
        old_id = builder.node.id
        node = wf.nodes.pop(old_id)
        node.id = _id
        wf.nodes[_id] = node
        for edge in wf.edges:
            if edge.to_node == old_id:
                edge.to_node = _id
            if edge.from_node == old_id:
                edge.from_node = _id
    return builder

