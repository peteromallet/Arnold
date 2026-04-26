from __future__ import annotations

from vibecomfy.registry.ready_template import build_api_ready_workflow


API_WORKFLOW = {'9': {'class_type': 'SaveImage', 'inputs': {'widget_0': 'Flux2-Klein', 'images': ['75', 0]}},
 '78': {'class_type': 'SaveImage', 'inputs': {'widget_0': 'Flux2-Klein', 'images': ['77', 0]}},
 '79': {'class_type': 'MarkdownNote',
        'inputs': {'widget_0': 'Guide: [Subgraph](https://docs.comfy.org/interface/features/subgraph)\n'
                               '\n'
                               '## Model links (for local users)\n'
                               '\n'
                               '**text_encoders**\n'
                               '\n'
                               '- '
                               '[qwen_3_4b.safetensors](https://huggingface.co/Comfy-Org/flux2-klein/resolve/main/split_files/text_encoders/qwen_3_4b.safetensors)\n'
                               '\n'
                               '**diffusion_models**\n'
                               '\n'
                               '- '
                               '[flux-2-klein-base-4b.safetensors](https://huggingface.co/Comfy-Org/flux2-klein/resolve/main/split_files/diffusion_models/flux-2-klein-base-4b.safetensors)\n'
                               '- '
                               '[flux-2-klein-4b.safetensors](https://huggingface.co/Comfy-Org/flux2-klein/resolve/main/split_files/diffusion_models/flux-2-klein-4b.safetensors)\n'
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
                               '│   │      ├── flux-2-klein-base-4b.safetensors\n'
                               '│   │      └── flux-2-klein-4b.safetensors\n'
                               '│   └── 📂 vae/\n'
                               '│          └── flux2-vae.safetensors\n'
                               '```\n'
                               '\n'
                               '## Report issue\n'
                               '\n'
                               'Note: please update ComfyUI first '
                               '([guide](https://docs.comfy.org/installation/update_comfyui)) and prepare the required '
                               'models. Desktop/Cloud will be updated after the stable release; nightly-supported '
                               'models may not be included yet, please wait for the next stable release.\n'
                               '\n'
                               '- Cannot run / runtime errors: '
                               '[ComfyUI/issues](https://github.com/Comfy-Org/ComfyUI/issues)\n'
                               '- UI / frontend issues: '
                               '[ComfyUI_frontend/issues](https://github.com/Comfy-Org/ComfyUI_frontend/issues)\n'
                               '- Workflow issues: '
                               '[workflow_templates/issues](https://github.com/Comfy-Org/workflow_templates/issues)\n'
                               '\n'}},
 '76': {'class_type': 'PrimitiveStringMultiline',
        'inputs': {'widget_0': 'A hedgehog wearing a tiny party hat surrounded by confetti, early digital camera '
                               'style, slight noise, flash photography, candid moment, 2000s digicam aesthetic, '
                               'festive birthday celebration atmosphere\n'}},
 '75': {'class_type': '7b34ab90-36f9-45ba-a665-71d418f0df18',
        'inputs': {'widget_0': '',
                   'widget_1': 1024,
                   'widget_2': 1024,
                   'widget_3': 'flux-2-klein-base-4b.safetensors',
                   'widget_4': 'qwen_3_4b.safetensors',
                   'widget_5': 'flux2-vae.safetensors',
                   'text': ['76', 0]}},
 '77': {'class_type': 'a67caa28-5f85-4917-8396-36004960dd30',
        'inputs': {'widget_0': '',
                   'widget_1': 1024,
                   'widget_2': 1024,
                   'widget_3': 'flux-2-klein-4b.safetensors',
                   'widget_4': 'qwen_3_4b.safetensors',
                   'widget_5': 'flux2-vae.safetensors',
                   'text': ['76', 0]}}}

READY_METADATA = {'model_assets': [{'name': 'flux-2-klein-base-4b.safetensors',
                   'url': 'https://huggingface.co/Comfy-Org/flux2-klein/resolve/main/split_files/diffusion_models/flux-2-klein-base-4b.safetensors',
                   'subdir': 'diffusion_models'},
                  {'name': 'qwen_3_4b.safetensors',
                   'url': 'https://huggingface.co/Comfy-Org/flux2-klein/resolve/main/split_files/text_encoders/qwen_3_4b.safetensors',
                   'subdir': 'text_encoders'},
                  {'name': 'flux2-vae.safetensors',
                   'url': 'https://huggingface.co/Comfy-Org/flux2-dev/resolve/main/split_files/vae/flux2-vae.safetensors',
                   'subdir': 'vae'},
                  {'name': 'flux-2-klein-4b.safetensors',
                   'url': 'https://huggingface.co/Comfy-Org/flux2-klein/resolve/main/split_files/diffusion_models/flux-2-klein-4b.safetensors',
                   'subdir': 'diffusion_models'}],
 'unbound_inputs': {'seed': 2734},
 'ready_template': 'image/flux2_klein_4b_t2i',
 'workflow_template': 'flux2_klein_4b_t2i',
 'capability': 'text_to_image',
 'source_role': 'materialized_ready_python_template',
 'source_workflow': 'workflow_corpus/official/image/flux2_klein_4b_t2i.json',
 'coverage_tier': 'required',
 'approach': None,
 'runtime_note': None,
 'discord_signal': None}

READY_REQUIREMENTS = {'models': [{'name': 'flux-2-klein-base-4b.safetensors',
             'url': 'https://huggingface.co/Comfy-Org/flux2-klein/resolve/main/split_files/diffusion_models/flux-2-klein-base-4b.safetensors',
             'subdir': 'diffusion_models'},
            {'name': 'qwen_3_4b.safetensors',
             'url': 'https://huggingface.co/Comfy-Org/flux2-klein/resolve/main/split_files/text_encoders/qwen_3_4b.safetensors',
             'subdir': 'text_encoders'},
            {'name': 'flux2-vae.safetensors',
             'url': 'https://huggingface.co/Comfy-Org/flux2-dev/resolve/main/split_files/vae/flux2-vae.safetensors',
             'subdir': 'vae'},
            {'name': 'flux-2-klein-4b.safetensors',
             'url': 'https://huggingface.co/Comfy-Org/flux2-klein/resolve/main/split_files/diffusion_models/flux-2-klein-4b.safetensors',
             'subdir': 'diffusion_models'}],
 'custom_nodes': []}


def build():
    return build_api_ready_workflow(
        API_WORKFLOW,
        source_path=__file__,
        workflow_id=READY_METADATA.get("ready_template", "image/flux2_klein_4b_t2i"),
        ready_metadata=READY_METADATA,
        requirements=READY_REQUIREMENTS,
    )
