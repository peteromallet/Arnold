from __future__ import annotations

from vibecomfy.registry.ready_template import build_api_ready_workflow


API_WORKFLOW = {'93': {'class_type': 'ImageScaleToTotalPixels',
        'inputs': {'widget_0': 'lanczos', 'widget_1': 1.5, 'widget_2': 1, 'image': ['78', 0]}},
 '99': {'class_type': 'MarkdownNote',
        'inputs': {'widget_0': '[Tutorial](https://docs.comfy.org/tutorials/image/qwen/qwen-image-edit)\n'
                               '\n'
                               '\n'
                               '## Model links\n'
                               '\n'
                               '**text_encoders**\n'
                               '\n'
                               '- '
                               '[qwen_2.5_vl_7b_fp8_scaled.safetensors](https://huggingface.co/Comfy-Org/Qwen-Image_ComfyUI/resolve/main/split_files/text_encoders/qwen_2.5_vl_7b_fp8_scaled.safetensors)\n'
                               '\n'
                               '**loras**\n'
                               '\n'
                               '- '
                               '[Qwen-Image-Edit-Lightning-4steps-V1.0-bf16.safetensors](https://huggingface.co/lightx2v/Qwen-Image-Lightning/resolve/main/Qwen-Image-Edit-Lightning-4steps-V1.0-bf16.safetensors)\n'
                               '\n'
                               '**diffusion_models**\n'
                               '\n'
                               '- '
                               '[qwen_image_edit_fp8_e4m3fn.safetensors](https://huggingface.co/Comfy-Org/Qwen-Image-Edit_ComfyUI/resolve/main/split_files/diffusion_models/qwen_image_edit_fp8_e4m3fn.safetensors)\n'
                               '\n'
                               '**vae**\n'
                               '\n'
                               '- '
                               '[qwen_image_vae.safetensors](https://huggingface.co/Comfy-Org/Qwen-Image_ComfyUI/resolve/main/split_files/vae/qwen_image_vae.safetensors)\n'
                               '\n'
                               '\n'
                               'Model Storage Location\n'
                               '\n'
                               '```\n'
                               '📂 ComfyUI/\n'
                               '├── 📂 models/\n'
                               '│   ├── 📂 text_encoders/\n'
                               '│   │      └── qwen_2.5_vl_7b_fp8_scaled.safetensors\n'
                               '│   ├── 📂 loras/\n'
                               '│   │      └── Qwen-Image-Edit-Lightning-4steps-V1.0-bf16.safetensors\n'
                               '│   ├── 📂 diffusion_models/\n'
                               '│   │      └── qwen_image_edit_fp8_e4m3fn.safetensors\n'
                               '│   └── 📂 vae/\n'
                               '│          └── qwen_image_vae.safetensors\n'
                               '```\n'
                               '\n'
                               '## Report issue\n'
                               '\n'
                               'If you have any problems running this workflow, please report template-related issues '
                               'via this link: [report the template issue '
                               'here](https://github.com/Comfy-Org/workflow_templates/issues)\n'}},
 '78': {'class_type': 'LoadImage',
        'inputs': {'widget_0': 'image_qwen_image_edit_input_image.png', 'widget_1': 'image'}},
 '60': {'class_type': 'SaveImage', 'inputs': {'widget_0': 'ComfyUI', 'images': ['102', 0]}},
 '96': {'class_type': 'MarkdownNote',
        'inputs': {'widget_0': 'This node is to avoid poor output results caused by excessively large input image '
                               'sizes.'}},
 '102': {'class_type': '74a8e1e2-9cb8-4112-978e-06ce1b5793f1', 'inputs': {'image': ['78', 0]}}}

READY_METADATA = {'model_assets': [{'name': 'qwen_image_edit_fp8_e4m3fn.safetensors',
                   'url': 'https://huggingface.co/Comfy-Org/Qwen-Image-Edit_ComfyUI/resolve/main/split_files/diffusion_models/qwen_image_edit_fp8_e4m3fn.safetensors',
                   'subdir': 'diffusion_models'},
                  {'name': 'qwen_2.5_vl_7b_fp8_scaled.safetensors',
                   'url': 'https://huggingface.co/Comfy-Org/Qwen-Image_ComfyUI/resolve/main/split_files/text_encoders/qwen_2.5_vl_7b_fp8_scaled.safetensors',
                   'subdir': 'text_encoders'},
                  {'name': 'qwen_image_vae.safetensors',
                   'url': 'https://huggingface.co/Comfy-Org/Qwen-Image_ComfyUI/resolve/main/split_files/vae/qwen_image_vae.safetensors',
                   'subdir': 'vae'},
                  {'name': 'Qwen-Image-Edit-Lightning-4steps-V1.0-bf16.safetensors',
                   'url': 'https://huggingface.co/lightx2v/Qwen-Image-Lightning/resolve/main/Qwen-Image-Edit-Lightning-4steps-V1.0-bf16.safetensors',
                   'subdir': 'loras'}],
 'unbound_inputs': {'seed': 2570},
 'ready_template': 'edit/qwen_image_edit',
 'workflow_template': 'qwen_image_edit',
 'capability': 'image_edit',
 'source_role': 'materialized_ready_python_template',
 'source_workflow': 'workflow_corpus/official/edit/qwen_image_edit.json',
 'coverage_tier': 'required',
 'approach': None,
 'runtime_note': None,
 'discord_signal': None}

READY_REQUIREMENTS = {'models': [{'name': 'qwen_image_edit_fp8_e4m3fn.safetensors',
             'url': 'https://huggingface.co/Comfy-Org/Qwen-Image-Edit_ComfyUI/resolve/main/split_files/diffusion_models/qwen_image_edit_fp8_e4m3fn.safetensors',
             'subdir': 'diffusion_models'},
            {'name': 'qwen_2.5_vl_7b_fp8_scaled.safetensors',
             'url': 'https://huggingface.co/Comfy-Org/Qwen-Image_ComfyUI/resolve/main/split_files/text_encoders/qwen_2.5_vl_7b_fp8_scaled.safetensors',
             'subdir': 'text_encoders'},
            {'name': 'qwen_image_vae.safetensors',
             'url': 'https://huggingface.co/Comfy-Org/Qwen-Image_ComfyUI/resolve/main/split_files/vae/qwen_image_vae.safetensors',
             'subdir': 'vae'},
            {'name': 'Qwen-Image-Edit-Lightning-4steps-V1.0-bf16.safetensors',
             'url': 'https://huggingface.co/lightx2v/Qwen-Image-Lightning/resolve/main/Qwen-Image-Edit-Lightning-4steps-V1.0-bf16.safetensors',
             'subdir': 'loras'}],
 'custom_nodes': []}


def build():
    return build_api_ready_workflow(
        API_WORKFLOW,
        source_path=__file__,
        workflow_id=READY_METADATA.get("ready_template", "edit/qwen_image_edit"),
        ready_metadata=READY_METADATA,
        requirements=READY_REQUIREMENTS,
    )
