from __future__ import annotations

from vibecomfy.registry.ready_template import build_authored_ready_workflow

NODES = (('75', '7b34ab90-36f9-45ba-a665-71d418f0df18', {}),
 ('9', 'SaveImage', {'images': ['75', 0], 'widget_0': 'Flux2-Klein'}))

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


def build():
    workflow = build_authored_ready_workflow(
        NODES,
        READY_METADATA,
        source_path=__file__,
        workflow_id=READY_METADATA.get("ready_template"),
        requirements=READY_REQUIREMENTS,
    )
    return workflow
