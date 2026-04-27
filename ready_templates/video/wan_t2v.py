from __future__ import annotations

from vibecomfy.registry.ready_template import build_authored_ready_workflow

NODES = (('3',
  'KSampler',
  {'latent_image': ['40', 0],
   'model': ['48', 0],
   'negative': ['7', 0],
   'positive': ['6', 0],
   'widget_0': 82628696717253,
   'widget_1': 'randomize',
   'widget_2': 30,
   'widget_3': 6,
   'widget_4': 'uni_pc',
   'widget_5': 'simple',
   'widget_6': 1}),
 ('37', 'UNETLoader', {'widget_0': 'wan2.1_t2v_1.3B_fp16.safetensors', 'widget_1': 'default'}),
 ('38', 'CLIPLoader', {'widget_0': 'umt5_xxl_fp8_e4m3fn_scaled.safetensors', 'widget_1': 'wan', 'widget_2': 'default'}),
 ('39', 'VAELoader', {'widget_0': 'wan_2.1_vae.safetensors'}),
 ('40', 'EmptyHunyuanLatentVideo', {'widget_0': 832, 'widget_1': 480, 'widget_2': 33, 'widget_3': 1}),
 ('48', 'ModelSamplingSD3', {'model': ['37', 0], 'widget_0': 8}),
 ('49', 'CreateVideo', {'images': ['8', 0], 'widget_0': 16}),
 ('50', 'SaveVideo', {'video': ['49', 0], 'widget_0': 'video/ComfyUI', 'widget_1': 'auto', 'widget_2': 'auto'}),
 ('6',
  'CLIPTextEncode',
  {'clip': ['38', 0],
   'widget_0': 'a fox moving quickly in a beautiful winter scenery nature trees mountains daytime tracking camera'}),
 ('7',
  'CLIPTextEncode',
  {'clip': ['38', 0],
   'widget_0': '色调艳丽，过曝，静态，细节模糊不清，字幕，风格，作品，画作，画面，静止，整体发灰，最差质量，低质量，JPEG压缩残留，丑陋的，残缺的，多余的手指，画得不好的手部，画得不好的脸部，畸形的，毁容的，形态畸形的肢体，手指融合，静止不动的画面，杂乱的背景，三条腿，背景人很多，倒着走'}),
 ('8', 'VAEDecode', {'samples': ['3', 0], 'vae': ['39', 0]}))

READY_METADATA = {'model_assets': [{'name': 'wan2.1_t2v_1.3B_fp16.safetensors',
                   'url': 'https://huggingface.co/Comfy-Org/Wan_2.1_ComfyUI_repackaged/resolve/main/split_files/diffusion_models/wan2.1_t2v_1.3B_fp16.safetensors',
                   'subdir': 'diffusion_models'},
                  {'name': 'umt5_xxl_fp8_e4m3fn_scaled.safetensors',
                   'url': 'https://huggingface.co/Comfy-Org/Wan_2.1_ComfyUI_repackaged/resolve/main/split_files/text_encoders/umt5_xxl_fp8_e4m3fn_scaled.safetensors',
                   'subdir': 'text_encoders'},
                  {'name': 'wan_2.1_vae.safetensors',
                   'url': 'https://huggingface.co/Comfy-Org/Wan_2.1_ComfyUI_repackaged/resolve/main/split_files/vae/wan_2.1_vae.safetensors',
                   'subdir': 'vae'}],
 'unbound_inputs': {'seed': 1705},
 'ready_template': 'video/wan_t2v',
 'workflow_template': 'wan_t2v',
 'capability': 'text_to_video',
 'source_role': 'materialized_ready_python_template',
 'source_workflow': 'workflow_corpus/official/video/wan_t2v.json',
 'coverage_tier': 'required',
 'approach': None,
 'runtime_note': None,
 'discord_signal': None}

READY_REQUIREMENTS = {'models': [{'name': 'wan2.1_t2v_1.3B_fp16.safetensors',
             'url': 'https://huggingface.co/Comfy-Org/Wan_2.1_ComfyUI_repackaged/resolve/main/split_files/diffusion_models/wan2.1_t2v_1.3B_fp16.safetensors',
             'subdir': 'diffusion_models'},
            {'name': 'umt5_xxl_fp8_e4m3fn_scaled.safetensors',
             'url': 'https://huggingface.co/Comfy-Org/Wan_2.1_ComfyUI_repackaged/resolve/main/split_files/text_encoders/umt5_xxl_fp8_e4m3fn_scaled.safetensors',
             'subdir': 'text_encoders'},
            {'name': 'wan_2.1_vae.safetensors',
             'url': 'https://huggingface.co/Comfy-Org/Wan_2.1_ComfyUI_repackaged/resolve/main/split_files/vae/wan_2.1_vae.safetensors',
             'subdir': 'vae'}],
 'custom_nodes': []}


def build():
    workflow = build_authored_ready_workflow(
        NODES,
        READY_METADATA,
        source_path=__file__,
        workflow_id=READY_METADATA.get("ready_template"),
        requirements=READY_REQUIREMENTS,
        registered_inputs={'prompt': ('6', 'widget_0')},
    )
    return workflow
