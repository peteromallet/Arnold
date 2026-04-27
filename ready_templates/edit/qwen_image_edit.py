from __future__ import annotations

from vibecomfy.registry.ready_template import build_authored_ready_workflow

NODES = (('102', '74a8e1e2-9cb8-4112-978e-06ce1b5793f1', {'image': ['78', 0]}),
 ('60', 'SaveImage', {'images': ['102', 0], 'widget_0': 'ComfyUI'}),
 ('78', 'LoadImage', {'widget_0': 'image_qwen_image_edit_input_image.png', 'widget_1': 'image'}),
 ('93', 'ImageScaleToTotalPixels', {'image': ['78', 0], 'widget_0': 'lanczos', 'widget_1': 1.5, 'widget_2': 1}))

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
    workflow = build_authored_ready_workflow(
        NODES,
        READY_METADATA,
        source_path=__file__,
        workflow_id=READY_METADATA.get("ready_template"),
        requirements=READY_REQUIREMENTS,
    )
    return workflow
