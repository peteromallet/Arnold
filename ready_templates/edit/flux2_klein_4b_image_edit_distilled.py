from __future__ import annotations

from vibecomfy.registry.ready_template import build_authored_ready_workflow

NODES = (('75', '7b34ab90-36f9-45ba-a665-71d418f0df18', {'image': ['76', 0]}),
 ('76', 'LoadImage', {'widget_0': 'handbag_white.png', 'widget_1': 'image'}),
 ('81', 'LoadImage', {'widget_0': 'comfy_logo_blue.png', 'widget_1': 'image'}),
 ('9', 'SaveImage', {'images': ['75', 0], 'widget_0': 'Flux2-Klein'}),
 ('92', '65c22b29-59aa-496b-89c6-55a603658670', {'image': ['76', 0], 'image_1': ['81', 0]}),
 ('94', 'SaveImage', {'images': ['92', 0], 'widget_0': 'Flux2-Klein'}))

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


def build():
    workflow = build_authored_ready_workflow(
        NODES,
        READY_METADATA,
        source_path=__file__,
        workflow_id=READY_METADATA.get("ready_template"),
        requirements=READY_REQUIREMENTS,
    )
    return workflow
