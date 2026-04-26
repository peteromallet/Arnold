from __future__ import annotations

from vibecomfy.registry.ready_template import build_api_ready_workflow


API_WORKFLOW = {'37': {'class_type': 'UNETLoader',
        'inputs': {'widget_0': 'wan2.1_i2v_480p_14B_fp16.safetensors', 'widget_1': 'default'}},
 '38': {'class_type': 'CLIPLoader',
        'inputs': {'widget_0': 'umt5_xxl_fp8_e4m3fn_scaled.safetensors', 'widget_1': 'wan', 'widget_2': 'default'}},
 '39': {'class_type': 'VAELoader', 'inputs': {'widget_0': 'wan_2.1_vae.safetensors'}},
 '49': {'class_type': 'CLIPVisionLoader', 'inputs': {'widget_0': 'clip_vision_h.safetensors'}},
 '6': {'class_type': 'CLIPTextEncode',
       'inputs': {'widget_0': 'a cute anime girl with massive fennec ears and a big fluffy tail wearing a maid outfit '
                              'turning around',
                  'clip': ['38', 0]}},
 '54': {'class_type': 'ModelSamplingSD3', 'inputs': {'widget_0': 8, 'model': ['37', 0]}},
 '55': {'class_type': 'CreateVideo', 'inputs': {'widget_0': 16, 'images': ['8', 0]}},
 '3': {'class_type': 'KSampler',
       'inputs': {'widget_0': 987948718394761,
                  'widget_1': 'randomize',
                  'widget_2': 20,
                  'widget_3': 6,
                  'widget_4': 'uni_pc',
                  'widget_5': 'simple',
                  'widget_6': 1,
                  'model': ['54', 0],
                  'positive': ['50', 0],
                  'negative': ['50', 1],
                  'latent_image': ['50', 2]}},
 '8': {'class_type': 'VAEDecode', 'inputs': {'samples': ['3', 0], 'vae': ['39', 0]}},
 '56': {'class_type': 'SaveVideo',
        'inputs': {'widget_0': 'video/ComfyUI', 'widget_1': 'auto', 'widget_2': 'auto', 'video': ['55', 0]}},
 '50': {'class_type': 'WanImageToVideo',
        'inputs': {'widget_0': 512,
                   'widget_1': 512,
                   'widget_2': 33,
                   'widget_3': 1,
                   'positive': ['6', 0],
                   'negative': ['7', 0],
                   'vae': ['39', 0],
                   'clip_vision_output': ['51', 0],
                   'start_image': ['52', 0]}},
 '51': {'class_type': 'CLIPVisionEncode', 'inputs': {'widget_0': 'none', 'clip_vision': ['49', 0], 'image': ['52', 0]}},
 '7': {'class_type': 'CLIPTextEncode',
       'inputs': {'widget_0': '色调艳丽，过曝，静态，细节模糊不清，字幕，风格，作品，画作，画面，静止，整体发灰，最差质量，低质量，JPEG压缩残留，丑陋的，残缺的，多余的手指，画得不好的手部，画得不好的脸部，畸形的，毁容的，形态畸形的肢体，手指融合，静止不动的画面，杂乱的背景，三条腿，背景人很多，倒着走',
                  'clip': ['38', 0]}},
 '57': {'class_type': 'MarkdownNote',
        'inputs': {'widget_0': '[Tutorial](https://docs.comfy.org/tutorials/video/wan/wan-video)\n'
                               '\n'
                               '\n'
                               '## Model links\n'
                               '\n'
                               '**text_encoders**\n'
                               '\n'
                               '- '
                               '[umt5_xxl_fp8_e4m3fn_scaled.safetensors](https://huggingface.co/Comfy-Org/Wan_2.1_ComfyUI_repackaged/resolve/main/split_files/text_encoders/umt5_xxl_fp8_e4m3fn_scaled.safetensors)\n'
                               '\n'
                               '**clip_vision**\n'
                               '\n'
                               '- '
                               '[clip_vision_h.safetensors](https://huggingface.co/Comfy-Org/Wan_2.1_ComfyUI_repackaged/resolve/main/split_files/clip_vision/clip_vision_h.safetensors)\n'
                               '\n'
                               '**diffusion_models**\n'
                               '\n'
                               '- '
                               '[wan2.1_i2v_480p_14B_fp16.safetensors](https://huggingface.co/Comfy-Org/Wan_2.1_ComfyUI_repackaged/resolve/main/split_files/diffusion_models/wan2.1_i2v_480p_14B_fp16.safetensors)\n'
                               '\n'
                               '**vae**\n'
                               '\n'
                               '- '
                               '[wan_2.1_vae.safetensors](https://huggingface.co/Comfy-Org/Wan_2.1_ComfyUI_repackaged/resolve/main/split_files/vae/wan_2.1_vae.safetensors)\n'
                               '\n'
                               '\n'
                               'Model Storage Location\n'
                               '\n'
                               '```\n'
                               '📂 ComfyUI/\n'
                               '├── 📂 models/\n'
                               '│   ├── 📂 text_encoders/\n'
                               '│   │      └── umt5_xxl_fp8_e4m3fn_scaled.safetensors\n'
                               '│   ├── 📂 clip_vision/\n'
                               '│   │      └── clip_vision_h.safetensors\n'
                               '│   ├── 📂 diffusion_models/\n'
                               '│   │      └── wan2.1_i2v_480p_14B_fp16.safetensors\n'
                               '│   └── 📂 vae/\n'
                               '│          └── wan_2.1_vae.safetensors\n'
                               '```\n'}},
 '52': {'class_type': 'LoadImage', 'inputs': {'widget_0': 'image_to_video_wan_start_image.png', 'widget_1': 'image'}}}

READY_METADATA = {'model_assets': [{'name': 'wan2.1_i2v_480p_14B_fp16.safetensors',
                   'url': 'https://huggingface.co/Comfy-Org/Wan_2.1_ComfyUI_repackaged/resolve/main/split_files/diffusion_models/wan2.1_i2v_480p_14B_fp16.safetensors',
                   'subdir': 'diffusion_models'},
                  {'name': 'umt5_xxl_fp8_e4m3fn_scaled.safetensors',
                   'url': 'https://huggingface.co/Comfy-Org/Wan_2.1_ComfyUI_repackaged/resolve/main/split_files/text_encoders/umt5_xxl_fp8_e4m3fn_scaled.safetensors',
                   'subdir': 'text_encoders'},
                  {'name': 'wan_2.1_vae.safetensors',
                   'url': 'https://huggingface.co/Comfy-Org/Wan_2.1_ComfyUI_repackaged/resolve/main/split_files/vae/wan_2.1_vae.safetensors',
                   'subdir': 'vae'},
                  {'name': 'clip_vision_h.safetensors',
                   'url': 'https://huggingface.co/Comfy-Org/Wan_2.1_ComfyUI_repackaged/resolve/main/split_files/clip_vision/clip_vision_h.safetensors',
                   'subdir': 'clip_vision'}],
 'unbound_inputs': {'seed': 1694},
 'ready_template': 'video/wan_i2v',
 'workflow_template': 'wan_i2v',
 'capability': 'image_to_video',
 'source_role': 'materialized_ready_python_template',
 'source_workflow': 'workflow_corpus/official/video/wan_i2v.json',
 'coverage_tier': 'required',
 'approach': None,
 'runtime_note': None,
 'discord_signal': None}

READY_REQUIREMENTS = {'models': [{'name': 'wan2.1_i2v_480p_14B_fp16.safetensors',
             'url': 'https://huggingface.co/Comfy-Org/Wan_2.1_ComfyUI_repackaged/resolve/main/split_files/diffusion_models/wan2.1_i2v_480p_14B_fp16.safetensors',
             'subdir': 'diffusion_models'},
            {'name': 'umt5_xxl_fp8_e4m3fn_scaled.safetensors',
             'url': 'https://huggingface.co/Comfy-Org/Wan_2.1_ComfyUI_repackaged/resolve/main/split_files/text_encoders/umt5_xxl_fp8_e4m3fn_scaled.safetensors',
             'subdir': 'text_encoders'},
            {'name': 'wan_2.1_vae.safetensors',
             'url': 'https://huggingface.co/Comfy-Org/Wan_2.1_ComfyUI_repackaged/resolve/main/split_files/vae/wan_2.1_vae.safetensors',
             'subdir': 'vae'},
            {'name': 'clip_vision_h.safetensors',
             'url': 'https://huggingface.co/Comfy-Org/Wan_2.1_ComfyUI_repackaged/resolve/main/split_files/clip_vision/clip_vision_h.safetensors',
             'subdir': 'clip_vision'}],
 'custom_nodes': []}


def build():
    return build_api_ready_workflow(
        API_WORKFLOW,
        source_path=__file__,
        workflow_id=READY_METADATA.get("ready_template", "video/wan_i2v"),
        ready_metadata=READY_METADATA,
        requirements=READY_REQUIREMENTS,
    )
