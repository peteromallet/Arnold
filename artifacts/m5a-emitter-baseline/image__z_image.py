# vibecomfy: generated — converted by tools/convert_ready_templates.py
# Edits will be overwritten on regeneration. Add a `# vibecomfy: manual`
# marker on the first line if hand-editing is required.
"""Auto-generated ready_template — see tools/convert_ready_templates.py."""
from __future__ import annotations

from vibecomfy.workflow import VibeWorkflow, WorkflowSource
from vibecomfy.registry.ready_template import apply_ready_template_policy


READY_METADATA = {'model_assets': [{'name': 'qwen_3_4b.safetensors',
                   'url': 'https://huggingface.co/Comfy-Org/z_image_turbo/resolve/main/split_files/text_encoders/qwen_3_4b.safetensors',
                   'subdir': 'text_encoders'},
                  {'name': 'ae.safetensors',
                   'url': 'https://huggingface.co/Comfy-Org/z_image_turbo/resolve/main/split_files/vae/ae.safetensors',
                   'subdir': 'vae'},
                  {'name': 'z_image_bf16.safetensors',
                   'url': 'https://huggingface.co/Comfy-Org/z_image/resolve/main/split_files/diffusion_models/z_image_bf16.safetensors',
                   'subdir': 'diffusion_models'}],
 'unbound_inputs': {'seed': 1732},
 'ready_template': 'image/z_image',
 'workflow_template': 'z_image',
 'capability': 'text_to_image',
 'source_role': 'authored_ready_python_template',
 'source_workflow': 'workflow_corpus/official/image/z_image.json',
 'coverage_tier': 'required',
 'approach': None,
 'runtime_note': None,
 'discord_signal': None}

READY_REQUIREMENTS = {'models': [{'name': 'qwen_3_4b.safetensors',
             'url': 'https://huggingface.co/Comfy-Org/z_image_turbo/resolve/main/split_files/text_encoders/qwen_3_4b.safetensors',
             'subdir': 'text_encoders'},
            {'name': 'ae.safetensors',
             'url': 'https://huggingface.co/Comfy-Org/z_image_turbo/resolve/main/split_files/vae/ae.safetensors',
             'subdir': 'vae'},
            {'name': 'z_image_bf16.safetensors',
             'url': 'https://huggingface.co/Comfy-Org/z_image/resolve/main/split_files/diffusion_models/z_image_bf16.safetensors',
             'subdir': 'diffusion_models'}],
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

    unetloader = _node(wf, 'UNETLoader', '1',
        unet_name='z_image_bf16.safetensors',
        weight_dtype='default',
    )
    cliploader = _node(wf, 'CLIPLoader', '2',
        clip_name='qwen_3_4b.safetensors',
        type='lumina2',
        device='default',
    )
    vaeloader = _node(wf, 'VAELoader', '3',
        vae_name='ae.safetensors',
    )
    emptysd3latentimage = _node(wf, 'EmptySD3LatentImage', '7',
        width=1024,
        height=1024,
        batch_size=1,
    )
    modelsamplingauraflow = _node(wf, 'ModelSamplingAuraFlow', '4',
        shift=3,
        model=unetloader.out(0),
    )
    positive = _node(wf, 'CLIPTextEncode', '5',
        text='A fashion photography work full of surreal romanticism, using a low-angle upward shooting composition, with a clear light blue sky as the background, and the visual focus concentrated on the fantasy blue vegetation and the model walking through it.\n\nThe vegetation in the picture is processed into varying shades of blue, from light ice blue to deep cobalt blue. The textures of the leaves and branches are delicate and realistic. The warm brown tree trunks form a sharp contrast with the cool blue leaves, resembling a dreamy forest from another world. An African-American model wearing a yellow and white vertical striped long dress walks slowly on the sand. The warm tones of the dress echo with the surrounding cool blue vegetation. The noon sun casts clear shadows on the sand, enhancing the sense of space and reality in the picture.\n\nThe entire scene, with its clean and transparent colors and fantasy settings, not only exudes the vastness of the natural wilderness but also presents a quiet and poetic high-fashion sense due to the surreal vegetation.',
        clip=cliploader.out(0),
    )
    negative = _node(wf, 'CLIPTextEncode', '6',
        text='',
        clip=cliploader.out(0),
    )
    ksampler = _node(wf, 'KSampler', '8',
        seed=770044821593082,
        steps=25,
        cfg=4.0,
        sampler_name='res_multistep',
        scheduler='simple',
        denoise=1.0,
        latent_image=emptysd3latentimage.out(0),
        model=modelsamplingauraflow.out(0),
        negative=negative.out(0),
        positive=positive.out(0),
    )
    vaedecode = _node(wf, 'VAEDecode', '9',
        samples=ksampler.out(0),
        vae=vaeloader.out(0),
    )
    saveimage = _node(wf, 'SaveImage', '10',
        filename_prefix='z-image',
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
