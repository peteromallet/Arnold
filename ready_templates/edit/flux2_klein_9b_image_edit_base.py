from __future__ import annotations

from vibecomfy.registry.ready_template import build_api_ready_workflow


API_WORKFLOW = {'9': {'class_type': 'SaveImage', 'inputs': {'widget_0': 'Flux2-Klein-4b-base', 'images': ['75', 0]}},
 '94': {'class_type': 'SaveImage', 'inputs': {'widget_0': 'Flux2-Klein-4b-base', 'images': ['92', 0]}},
 '81': {'class_type': 'LoadImage', 'inputs': {'widget_0': 'comfy_logo_blue.png', 'widget_1': 'image'}},
 '76': {'class_type': 'LoadImage', 'inputs': {'widget_0': 'car_interior_white.jpeg', 'widget_1': 'image'}},
 '97': {'class_type': 'MarkdownNote',
        'inputs': {'widget_0': '## Model Links (for Local Users)\n'
                               '\n'
                               '**diffusion_models**\n'
                               '\n'
                               '- '
                               '[flux-2-klein-base-9b-fp8.safetensors](https://huggingface.co/black-forest-labs/FLUX.2-klein-base-9b-fp8)\n'
                               '\n'
                               "> Please visit BFL's repo, accept the agreement in the repo, and then download the fp8 "
                               'model.\n'
                               '\n'
                               '**text_encoders**\n'
                               '\n'
                               '- '
                               '[qwen_3_8b_fp8mixed.safetensors](https://huggingface.co/Comfy-Org/flux2-klein-9B/resolve/main/split_files/text_encoders/qwen_3_8b_fp8mixed.safetensors)\n'
                               '\n'
                               '**vae**\n'
                               '\n'
                               '- '
                               '[full_encoder_small_decoder.safetensors](https://huggingface.co/black-forest-labs/FLUX.2-small-decoder/resolve/main/full_encoder_small_decoder.safetensors)\n'
                               '\n'
                               '\n'
                               '## Model Storage Location\n'
                               '\n'
                               '```\n'
                               '📂 ComfyUI/\n'
                               '├── 📂 models/\n'
                               '│   ├── 📂 diffusion_models/\n'
                               '│   │   └── flux-2-klein-base-9b-fp8.safetensors\n'
                               '│   ├── 📂 text_encoders/\n'
                               '│   │   └── qwen_3_8b_fp8mixed.safetensors\n'
                               '│   └── 📂 vae/\n'
                               '│       └── full_encoder_small_decoder.safetensors\n'
                               '```\n'
                               '\n'
                               '## Report Issue\n'
                               '\n'
                               'Note: Please update ComfyUI first '
                               '([guide](https://docs.comfy.org/installation/update_comfyui)) and prepare required '
                               'models. Desktop/Cloud updates follow stable releases, so some nightly-supported models '
                               'may not be available yet.\n'
                               '\n'
                               '- Cannot run / runtime errors: '
                               '[ComfyUI/issues](https://github.com/comfyanonymous/ComfyUI/issues)\n'
                               '- UI / frontend issues: '
                               '[ComfyUI_frontend/issues](https://github.com/Comfy-Org/ComfyUI_frontend/issues)\n'
                               '- Workflow issues: '
                               '[workflow_templates/issues](https://github.com/Comfy-Org/workflow_templates/issues)\n'}},
 '99': {'class_type': 'MarkdownNote',
        'inputs': {'widget_0': 'The node below is a subgraph. Learn more at [Subgraph '
                               'docs](https://docs.comfy.org/interface/features/subgraph)'}},
 '92': {'class_type': '65c22b29-59aa-496b-89c6-55a603658670', 'inputs': {'image': ['76', 0], 'image_1': ['81', 0]}},
 '75': {'class_type': '7b34ab90-36f9-45ba-a665-71d418f0df18', 'inputs': {'image': ['76', 0]}}}

READY_METADATA = {'model_assets': [{'name': 'flux-2-klein-base-9b-fp8.safetensors',
                   'url': 'https://huggingface.co/black-forest-labs/FLUX.2-klein-base-9b-fp8/resolve/main/flux-2-klein-base-9b-fp8.safetensors',
                   'subdir': 'diffusion_models'},
                  {'name': 'qwen_3_8b_fp8mixed.safetensors',
                   'url': 'https://huggingface.co/Comfy-Org/flux2-klein-9B/resolve/main/split_files/text_encoders/qwen_3_8b_fp8mixed.safetensors',
                   'subdir': 'text_encoders'},
                  {'name': 'full_encoder_small_decoder.safetensors',
                   'url': 'https://huggingface.co/black-forest-labs/FLUX.2-small-decoder/resolve/main/full_encoder_small_decoder.safetensors',
                   'subdir': 'vae'}],
 'unbound_inputs': {'seed': 4006},
 'ready_template': 'edit/flux2_klein_9b_image_edit_base',
 'workflow_template': 'flux2_klein_9b_image_edit_base',
 'capability': 'image_edit',
 'source_role': 'materialized_ready_python_template',
 'source_workflow': 'workflow_corpus/official/edit/flux2_klein_9b_image_edit_base.json',
 'coverage_tier': 'supplemental',
 'approach': 'official Flux.2 Klein 9B base image-edit workflow',
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


def build():
    return build_api_ready_workflow(
        API_WORKFLOW,
        source_path=__file__,
        workflow_id=READY_METADATA.get("ready_template", "edit/flux2_klein_9b_image_edit_base"),
        ready_metadata=READY_METADATA,
        requirements=READY_REQUIREMENTS,
    )
