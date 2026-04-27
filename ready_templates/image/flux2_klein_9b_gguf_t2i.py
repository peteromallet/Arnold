# vibecomfy: generated — converted by tools/convert_ready_templates.py
# Edits will be overwritten on regeneration. Add a `# vibecomfy: manual`
# marker on the first line if hand-editing is required.
"""Auto-generated ready_template — see tools/convert_ready_templates.py."""
from __future__ import annotations

from vibecomfy.workflow import VibeWorkflow, WorkflowSource
from vibecomfy.registry.ready_template import apply_ready_template_policy


READY_METADATA = {'model_assets': [{'name': 'qwen_3_8b_fp8mixed.safetensors',
                   'url': 'https://huggingface.co/Comfy-Org/flux2-klein-9B/resolve/main/split_files/text_encoders/qwen_3_8b_fp8mixed.safetensors',
                   'subdir': 'text_encoders'}],
 'unbound_inputs': {'seed': 3259},
 'ready_template': 'image/flux2_klein_9b_gguf_t2i',
 'workflow_template': 'flux2_klein_9b_gguf_t2i',
 'capability': 'text_to_image',
 'source_role': 'materialized_ready_python_template',
 'source_workflow': 'workflow_corpus/custom_nodes/flux2/flux2_klein_9b_gguf_t2i.json',
 'coverage_tier': 'required',
 'approach': None,
 'runtime_note': None,
 'discord_signal': None}

READY_REQUIREMENTS = {'models': [{'name': 'qwen_3_8b_fp8mixed.safetensors',
             'url': 'https://huggingface.co/Comfy-Org/flux2-klein-9B/resolve/main/split_files/text_encoders/qwen_3_8b_fp8mixed.safetensors',
             'subdir': 'text_encoders'}],
 'custom_nodes': ['ComfyUI-GGUF']}


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
    primitiveint = _node(wf, 'PrimitiveInt', '75:68',
        value=1024,
    )
    primitiveint_2 = _node(wf, 'PrimitiveInt', '75:69',
        value=1024,
    )
    unetloader = _node(wf, 'UNETLoader', '75:70',
        unet_name='flux-2-klein-base-9b-fp8.safetensors',
        weight_dtype='default',
    )
    cliploader = _node(wf, 'CLIPLoader', '75:71',
        clip_name='qwen_3_8b_fp8mixed.safetensors',
        type='flux2',
        device='default',
    )
    vaeloader = _node(wf, 'VAELoader', '75:72',
        vae_name='full_encoder_small_decoder.safetensors',
    )
    randomnoise = _node(wf, 'RandomNoise', '75:73',
        noise_seed=653844576367526,
    )
    flux2scheduler = _node(wf, 'Flux2Scheduler', '75:62',
        steps=20,
        height=primitiveint_2.out(0),
        width=primitiveint.out(0),
    )
    emptyflux2latentimage = _node(wf, 'EmptyFlux2LatentImage', '75:66',
        batch_size=1,
        width=primitiveint.out(0),
        height=primitiveint_2.out(0),
    )
    negative = _node(wf, 'CLIPTextEncode', '75:67',
        text='',
        clip=cliploader.out(0),
    )
    positive = _node(wf, 'CLIPTextEncode', '75:74',
        text='',
        clip=cliploader.out(0),
    )
    cfgguider = _node(wf, 'CFGGuider', '75:63',
        cfg=5,
        model=unetloader.out(0),
        negative=negative.out(0),
        positive=positive.out(0),
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

