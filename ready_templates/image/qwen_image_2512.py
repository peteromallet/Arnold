from __future__ import annotations

from vibecomfy.registry.ready_template import build_api_ready_workflow


API_WORKFLOW = {'238:218': {'class_type': 'PrimitiveFloat', 'inputs': {'value': 1.0}},
 '238:219': {'class_type': 'CLIPLoader',
             'inputs': {'clip_name': 'qwen_2.5_vl_7b_fp8_scaled.safetensors',
                        'device': 'default',
                        'type': 'qwen_image'}},
 '238:220': {'class_type': 'VAELoader', 'inputs': {'vae_name': 'qwen_image_vae.safetensors'}},
 '238:221': {'class_type': 'LoraLoaderModelOnly',
             'inputs': {'lora_name': 'Qwen-Image-2512-Lightning-4steps-V1.0-fp32.safetensors',
                        'model': ['238:226', 0],
                        'strength_model': 1}},
 '238:222': {'class_type': 'ModelSamplingAuraFlow', 'inputs': {'model': ['238:233', 0], 'shift': 3.1000000000000005}},
 '238:223': {'class_type': 'PrimitiveFloat', 'inputs': {'value': 1}},
 '238:224': {'class_type': 'PrimitiveInt', 'inputs': {'value': 4}},
 '238:225': {'class_type': 'PrimitiveInt', 'inputs': {'value': 4}},
 '238:226': {'class_type': 'UNETLoader',
             'inputs': {'unet_name': 'qwen_image_2512_fp8_e4m3fn.safetensors', 'weight_dtype': 'default'}},
 '238:227': {'class_type': 'CLIPTextEncode',
             'inputs': {'clip': ['238:219', 0],
                        'text': 'Urban alleyway at dusk. Tall, statuesque high-fashion model striding elegantly, mid '
                                'distant full body shot from an angular perspective, cinematic/editorial with bold '
                                'contrasts and tactile materials. They wear a rose-gold metallic trench coat with '
                                'deconstructed elements over a black long-sleeved turtleneck with subtle texture; '
                                'paired with forest-green pleated pants with raw hems and a soft texture. Long braided '
                                'dark hair, medium complexion. They carry a vibrant yellow designer handbag with '
                                'geometric details and a structured silhouette. White architectural sneakers with bold '
                                'geometric cutouts. Bold, high-contrast, tactile, urban-grit meets high-fashion '
                                'impact, extreme clarity, extreme layering, post-processing with transparent '
                                'light-transmitting ultra-smooth high-definition film effect, removing all noise and '
                                'grain, removing all blur, removing all vintage feel, removing all roughness, drawn '
                                'with 32K pixel precision, unparalleled fine line drawing of every single detail, the '
                                'entire image like a brand new photograph, photorealistic\n'}},
 '238:228': {'class_type': 'CLIPTextEncode',
             'inputs': {'clip': ['238:219', 0],
                        'text': '低分辨率，低画质，肢体畸形，手指畸形，画面过饱和，蜡像感，人脸无细节，过度光滑，画面具有AI感。构图混乱。文字模糊，扭曲'}},
 '238:229': {'class_type': 'PrimitiveBoolean', 'inputs': {'value': True}},
 '238:230': {'class_type': 'KSampler',
             'inputs': {'cfg': ['238:243', 0],
                        'denoise': 1,
                        'latent_image': ['238:232', 0],
                        'model': ['238:222', 0],
                        'negative': ['238:228', 0],
                        'positive': ['238:227', 0],
                        'sampler_name': 'euler',
                        'scheduler': 'simple',
                        'seed': 1232512,
                        'steps': ['238:240', 0]}},
 '238:231': {'class_type': 'VAEDecode', 'inputs': {'samples': ['238:230', 0], 'vae': ['238:220', 0]}},
 '238:232': {'class_type': 'EmptySD3LatentImage', 'inputs': {'batch_size': 1, 'height': 768, 'width': 768}},
 '238:233': {'class_type': 'ComfySwitchNode',
             'inputs': {'on_false': ['238:226', 0], 'on_true': ['238:221', 0], 'switch': ['238:229', 0]}},
 '238:240': {'class_type': 'ComfySwitchNode',
             'inputs': {'on_false': ['238:224', 0], 'on_true': ['238:225', 0], 'switch': ['238:229', 0]}},
 '238:243': {'class_type': 'ComfySwitchNode',
             'inputs': {'on_false': ['238:223', 0], 'on_true': ['238:218', 0], 'switch': ['238:229', 0]}},
 '60': {'class_type': 'SaveImage', 'inputs': {'filename_prefix': 'Qwen-Image-2512', 'images': ['238:231', 0]}}}

READY_METADATA = {'model_assets': [{'name': 'qwen_image_2512_fp8_e4m3fn.safetensors',
                   'url': 'https://huggingface.co/Comfy-Org/Qwen-Image_ComfyUI/resolve/main/split_files/diffusion_models/qwen_image_2512_fp8_e4m3fn.safetensors',
                   'subdir': 'diffusion_models'},
                  {'name': 'qwen_2.5_vl_7b_fp8_scaled.safetensors',
                   'url': 'https://huggingface.co/Comfy-Org/Qwen-Image_ComfyUI/resolve/main/split_files/text_encoders/qwen_2.5_vl_7b_fp8_scaled.safetensors',
                   'subdir': 'text_encoders'},
                  {'name': 'qwen_image_vae.safetensors',
                   'url': 'https://huggingface.co/Comfy-Org/Qwen-Image_ComfyUI/resolve/main/split_files/vae/qwen_image_vae.safetensors',
                   'subdir': 'vae'},
                  {'name': 'Qwen-Image-2512-Lightning-4steps-V1.0-fp32.safetensors',
                   'url': 'https://huggingface.co/lightx2v/Qwen-Image-2512-Lightning/resolve/main/Qwen-Image-2512-Lightning-4steps-V1.0-fp32.safetensors',
                   'subdir': 'loras'}],
 'ready_template': 'image/qwen_image_2512',
 'workflow_template': 'qwen_image_2512',
 'capability': 'text_to_image',
 'source_role': 'materialized_ready_python_template',
 'source_workflow': 'workflow_corpus/official/image/qwen_image_2512.json',
 'coverage_tier': 'required',
 'approach': 'official Qwen-Image-2512 text-to-image workflow using the 4-step Lightning LoRA path for smoke/runtime '
             'validation',
 'runtime_note': None,
 'discord_signal': None,
 'runtime_variant': 'qwen-image-2512-lightning-4step-768px',
 'smoke_resolution': '768x768'}

READY_REQUIREMENTS = {'models': [{'name': 'qwen_image_2512_fp8_e4m3fn.safetensors',
             'url': 'https://huggingface.co/Comfy-Org/Qwen-Image_ComfyUI/resolve/main/split_files/diffusion_models/qwen_image_2512_fp8_e4m3fn.safetensors',
             'subdir': 'diffusion_models'},
            {'name': 'qwen_2.5_vl_7b_fp8_scaled.safetensors',
             'url': 'https://huggingface.co/Comfy-Org/Qwen-Image_ComfyUI/resolve/main/split_files/text_encoders/qwen_2.5_vl_7b_fp8_scaled.safetensors',
             'subdir': 'text_encoders'},
            {'name': 'qwen_image_vae.safetensors',
             'url': 'https://huggingface.co/Comfy-Org/Qwen-Image_ComfyUI/resolve/main/split_files/vae/qwen_image_vae.safetensors',
             'subdir': 'vae'},
            {'name': 'Qwen-Image-2512-Lightning-4steps-V1.0-fp32.safetensors',
             'url': 'https://huggingface.co/lightx2v/Qwen-Image-2512-Lightning/resolve/main/Qwen-Image-2512-Lightning-4steps-V1.0-fp32.safetensors',
             'subdir': 'loras'}],
 'custom_nodes': []}


def build():
    return build_api_ready_workflow(
        API_WORKFLOW,
        source_path=__file__,
        workflow_id=READY_METADATA.get("ready_template", "image/qwen_image_2512"),
        ready_metadata=READY_METADATA,
        requirements=READY_REQUIREMENTS,
    )
