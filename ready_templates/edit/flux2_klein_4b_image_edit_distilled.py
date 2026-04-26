from __future__ import annotations

from vibecomfy.registry.ready_template import build_api_ready_workflow


API_WORKFLOW = {'9': {'class_type': 'SaveImage', 'inputs': {'widget_0': 'Flux2-Klein', 'images': ['75', 0]}},
 '97': {'class_type': 'MarkdownNote',
        'inputs': {'widget_0': 'Guide: [Subgraph](https://docs.comfy.org/interface/features/subgraph)\n'
                               '\n'
                               '## Model links (for local users)\n'
                               '\n'
                               '**text_encoders**\n'
                               '\n'
                               '- '
                               '[qwen_3_4b.safetensors](https://huggingface.co/Comfy-Org/z_image_turbo/resolve/main/split_files/text_encoders/qwen_3_4b.safetensors)\n'
                               '\n'
                               '**diffusion_models**\n'
                               '\n'
                               '- '
                               '[flux-2-klein-4b-fp8.safetensors](https://huggingface.co/black-forest-labs/FLUX.2-klein-4b-fp8/resolve/main/flux-2-klein-4b-fp8.safetensors)\n'
                               '\n'
                               '**vae**\n'
                               '\n'
                               '- '
                               '[flux2-vae.safetensors](https://huggingface.co/Comfy-Org/flux2-dev/resolve/main/split_files/vae/flux2-vae.safetensors)\n'
                               '\n'
                               '\n'
                               'Model Storage Location\n'
                               '\n'
                               '```\n'
                               '📂 ComfyUI/\n'
                               '├── 📂 models/\n'
                               '│   ├── 📂 text_encoders/\n'
                               '│   │      └── qwen_3_4b.safetensors\n'
                               '│   ├── 📂 diffusion_models/\n'
                               '│   │      └── flux-2-klein-4b-fp8.safetensors\n'
                               '│   └── 📂 vae/\n'
                               '│          └── flux2-vae.safetensors\n'
                               '```\n'
                               '\n'
                               '## Report issues\n'
                               '\n'
                               'Note: please update ComfyUI first '
                               '([guide](https://docs.comfy.org/installation/update_comfyui)) and prepare required '
                               'models. Desktop/Cloud will be updated after the stable release; nightly-supported '
                               'models may not be included yet, please wait for the next stable release.\n'
                               '\n'
                               '- Cannot run / runtime errors: '
                               '[ComfyUI/issues](https://github.com/Comfy-Org/ComfyUI/issues)\n'
                               '- UI / frontend issues: '
                               '[ComfyUI_frontend/issues](https://github.com/Comfy-Org/ComfyUI_frontend/issues)\n'
                               '- Workflow issues: '
                               '[workflow_templates/issues](https://github.com/Comfy-Org/workflow_templates/issues)\n'}},
 '81': {'class_type': 'LoadImage', 'inputs': {'widget_0': 'comfy_logo_blue.png', 'widget_1': 'image'}},
 '94': {'class_type': 'SaveImage', 'inputs': {'widget_0': 'Flux2-Klein', 'images': ['92', 0]}},
 '76': {'class_type': 'LoadImage', 'inputs': {'widget_0': 'handbag_white.png', 'widget_1': 'image'}},
 '98': {'class_type': 'MarkdownNote',
        'inputs': {'widget_0': 'This is a [Subgraph](https://docs.comfy.org/interface/features/subgraph). Enter for '
                               'advanced parameter editing, or right‑click → Unpack Subgraph to convert it into '
                               'regular nodes'}},
 '92': {'class_type': '65c22b29-59aa-496b-89c6-55a603658670', 'inputs': {'image': ['76', 0], 'image_1': ['81', 0]}},
 '75': {'class_type': '7b34ab90-36f9-45ba-a665-71d418f0df18', 'inputs': {'image': ['76', 0]}}}

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
    return build_api_ready_workflow(
        API_WORKFLOW,
        source_path=__file__,
        workflow_id=READY_METADATA.get("ready_template", "edit/flux2_klein_4b_image_edit_distilled"),
        ready_metadata=READY_METADATA,
        requirements=READY_REQUIREMENTS,
    )
