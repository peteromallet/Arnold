from __future__ import annotations

from vibecomfy.registry.ready_template import build_api_ready_workflow


API_WORKFLOW = {'35': {'class_type': 'MarkdownNote',
        'inputs': {'widget_0': '## Model links\n'
                               '\n'
                               '**text_encoders**\n'
                               '\n'
                               '- '
                               '[qwen_3_4b.safetensors](https://huggingface.co/Comfy-Org/z_image_turbo/resolve/main/split_files/text_encoders/qwen_3_4b.safetensors)\n'
                               '\n'
                               '**diffusion_models**\n'
                               '\n'
                               '- '
                               '[z_image_bf16.safetensors](https://huggingface.co/Comfy-Org/z_image/resolve/main/split_files/diffusion_models/z_image_bf16.safetensors)\n'
                               '\n'
                               '**vae**\n'
                               '\n'
                               '- '
                               '[ae.safetensors](https://huggingface.co/Comfy-Org/z_image_turbo/resolve/main/split_files/vae/ae.safetensors)\n'
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
                               '│   │      └── z_image_bf16.safetensors\n'
                               '│   └── 📂 vae/\n'
                               '│          └── ae.safetensors\n'
                               '```\n'}},
 '84': {'class_type': 'MarkdownNote',
        'inputs': {'widget_0': 'The node below is a subgraph. Learn more at [Subgraph '
                               'docs](https://docs.comfy.org/interface/features/subgraph)'}},
 '9': {'class_type': 'SaveImage', 'inputs': {'widget_0': 'z-image', 'images': ['76', 0]}},
 '76': {'class_type': '9b9009e4-2d3d-445f-9be5-6063f465757e',
        'inputs': {'widget_0': 'A fashion photography work full of surreal romanticism, using a low-angle upward '
                               'shooting composition, with a clear light blue sky as the background, and the visual '
                               'focus concentrated on the fantasy blue vegetation and the model walking through it.\n'
                               '\n'
                               'The vegetation in the picture is processed into varying shades of blue, from light ice '
                               'blue to deep cobalt blue. The textures of the leaves and branches are delicate and '
                               'realistic. The warm brown tree trunks form a sharp contrast with the cool blue leaves, '
                               'resembling a dreamy forest from another world. An African-American model wearing a '
                               'yellow and white vertical striped long dress walks slowly on the sand. The warm tones '
                               'of the dress echo with the surrounding cool blue vegetation. The noon sun casts clear '
                               'shadows on the sand, enhancing the sense of space and reality in the picture.\n'
                               '\n'
                               'The entire scene, with its clean and transparent colors and fantasy settings, not only '
                               'exudes the vastness of the natural wilderness but also presents a quiet and poetic '
                               'high-fashion sense due to the surreal vegetation.',
                   'widget_1': 1024,
                   'widget_2': 1024,
                   'widget_3': 25,
                   'widget_4': 4,
                   'widget_5': None,
                   'widget_6': None,
                   'widget_7': 'z_image_bf16.safetensors',
                   'widget_8': 'qwen_3_4b.safetensors',
                   'widget_9': 'ae.safetensors'}},
 '86': {'class_type': 'MarkdownNote', 'inputs': {'widget_0': '- Steps: 30～50\n- cfg:  3～5'}}}

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
 'source_role': 'materialized_ready_python_template',
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


def build():
    return build_api_ready_workflow(
        API_WORKFLOW,
        source_path=__file__,
        workflow_id=READY_METADATA.get("ready_template", "image/z_image"),
        ready_metadata=READY_METADATA,
        requirements=READY_REQUIREMENTS,
    )
