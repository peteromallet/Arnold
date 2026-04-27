# vibecomfy: generated — converted by tools/convert_ready_templates.py
# Edits will be overwritten on regeneration. Add a `# vibecomfy: manual`
# marker on the first line if hand-editing is required.
"""Auto-generated ready_template — see tools/convert_ready_templates.py."""
from __future__ import annotations

from vibecomfy.workflow import VibeWorkflow, WorkflowSource
from vibecomfy.registry.ready_template import apply_ready_template_policy


READY_METADATA = {'model_assets': [{'name': 'flux-2-klein-base-9b-fp8.safetensors',
                   'url': 'https://huggingface.co/black-forest-labs/FLUX.2-klein-base-9b-fp8/resolve/main/flux-2-klein-base-9b-fp8.safetensors',
                   'subdir': 'diffusion_models'},
                  {'name': 'qwen_3_8b_fp8mixed.safetensors',
                   'url': 'https://huggingface.co/Comfy-Org/flux2-klein-9B/resolve/main/split_files/text_encoders/qwen_3_8b_fp8mixed.safetensors',
                   'subdir': 'text_encoders'},
                  {'name': 'full_encoder_small_decoder.safetensors',
                   'url': 'https://huggingface.co/black-forest-labs/FLUX.2-small-decoder/resolve/main/full_encoder_small_decoder.safetensors',
                   'subdir': 'vae'}],
 'unbound_inputs': {'seed': 2739},
 'ready_template': 'image/flux2_klein_9b_t2i',
 'workflow_template': 'flux2_klein_9b_t2i',
 'capability': 'text_to_image',
 'source_role': 'materialized_ready_python_template',
 'source_workflow': 'workflow_corpus/official/image/flux2_klein_9b_t2i.json',
 'coverage_tier': 'supplemental',
 'approach': 'official Flux.2 Klein 9B text-to-image safetensors workflow',
 'runtime_note': None,
 'discord_signal': None}

READY_REQUIREMENTS = {'models': [{'name': 'flux-2-klein-base-9b-fp8.safetensors',
             'url': 'https://huggingface.co/black-forest-labs/FLUX.2-klein-base-9b-fp8/resolve/main/flux-2-klein-base-9b-fp8.safetensors',
             'subdir': 'diffusion_models'},
            {'name': 'qwen_3_8b_fp8mixed.safetensors',
             'url': 'https://huggingface.co/Comfy-Org/flux2-klein-9B/resolve/main/split_files/text_encoders/qwen_3_8b_fp8mixed.safetensors',
             'subdir': 'text_encoders'},
            {'name': 'full_encoder_small_decoder.safetensors',
             'url': 'https://huggingface.co/black-forest-labs/FLUX.2-small-decoder/resolve/main/full_encoder_small_decoder.safetensors',
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

    n_7b34ab90_36f9_45ba_a665_71d418f0df18 = _node(wf, '7b34ab90-36f9-45ba-a665-71d418f0df18', '75')
    saveimage = _node(wf, 'SaveImage', '9',
        filename_prefix='Flux2-Klein',
        images=n_7b34ab90_36f9_45ba_a665_71d418f0df18.out(0),
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

