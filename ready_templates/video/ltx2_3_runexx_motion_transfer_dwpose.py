from __future__ import annotations

from vibecomfy.registry.ready_template import build_api_ready_workflow


API_WORKFLOW = {'5121': {'class_type': 'SetNode', 'inputs': {'widget_0': 'upscale_model', 'LATENT_UPSCALE_MODEL': ['5132', 0]}},
 '5122': {'class_type': 'SetNode', 'inputs': {'widget_0': 'vae_audio', 'VAE': ['5127', 0]}},
 '5123': {'class_type': 'SetNode', 'inputs': {'widget_0': 'vae', 'VAE': ['5125', 0]}},
 '5124': {'class_type': 'SetNode', 'inputs': {'widget_0': 'clip', 'CLIP': ['5126', 0]}},
 '5125': {'class_type': 'VAELoader', 'inputs': {'widget_0': 'LTX23_video_vae_bf16.safetensors'}},
 '5126': {'class_type': 'DualCLIPLoader',
          'inputs': {'widget_0': 'gemma_3_12B_it_fp4_mixed.safetensors',
                     'widget_1': 'ltx-2.3_text_projection_bf16.safetensors',
                     'widget_2': 'ltxv',
                     'widget_3': 'default'}},
 '5128': {'class_type': 'SetNode', 'inputs': {'widget_0': 'vae_tiny', 'VAE': ['5129', 0]}},
 '5129': {'class_type': 'VAELoader', 'inputs': {'widget_0': 'taeltx2_3.safetensors'}},
 '5137': {'class_type': 'GetNode', 'inputs': {'widget_0': 'clip'}},
 '5141': {'class_type': 'GetNode', 'inputs': {'widget_0': 'vae'}},
 '5140': {'class_type': 'GetNode', 'inputs': {'widget_0': 'vae'}},
 '5161': {'class_type': 'SetNode', 'inputs': {'widget_0': 'positive', 'CONDITIONING': ['1241', 0]}},
 '5162': {'class_type': 'SetNode', 'inputs': {'widget_0': 'negative', 'CONDITIONING': ['1241', 1]}},
 '5176': {'class_type': 'GetNode', 'inputs': {'widget_0': 'ref_image'}},
 '5177': {'class_type': 'GetNode', 'inputs': {'widget_0': 'ref_image'}},
 '5181': {'class_type': 'GetNode', 'inputs': {'widget_0': 't2v_mode'}},
 '5139': {'class_type': 'GetNode', 'inputs': {'widget_0': 'vae'}},
 '5164': {'class_type': 'GetNode', 'inputs': {'widget_0': 'negative'}},
 '5146': {'class_type': 'GetNode', 'inputs': {'widget_0': 'vae'}},
 '5152': {'class_type': 'GetNode', 'inputs': {'widget_0': 'ref_video'}},
 '5165': {'class_type': 'SetNode', 'inputs': {'widget_0': 'positive_guider', 'CONDITIONING': ['5012', 0]}},
 '5184': {'class_type': 'GetNode', 'inputs': {'widget_0': 'latent_down_factor'}},
 '5025': {'class_type': 'ManualSigmas',
          'inputs': {'widget_0': '1.0, 0.99375, 0.9875, 0.98125, 0.975, 0.909375, 0.725, 0.421875, 0.0'}},
 '5149': {'class_type': 'GetNode', 'inputs': {'widget_0': 'model'}},
 '5191': {'class_type': 'GetNode', 'inputs': {'widget_0': 'upscale_model'}},
 '5180': {'class_type': 'GetNode', 'inputs': {'widget_0': 't2v_mode'}},
 '5169': {'class_type': 'GetNode', 'inputs': {'widget_0': 'positive_guider'}},
 '5170': {'class_type': 'GetNode', 'inputs': {'widget_0': 'negative_guider'}},
 '5172': {'class_type': 'GetNode', 'inputs': {'widget_0': 'negative'}},
 '5171': {'class_type': 'GetNode', 'inputs': {'widget_0': 'positive'}},
 '5070': {'class_type': 'KSamplerSelect', 'inputs': {'widget_0': 'euler_cfg_pp'}},
 '5071': {'class_type': 'ManualSigmas', 'inputs': {'widget_0': '0.85, 0.7250, 0.4219, 0.0'}},
 '5150': {'class_type': 'GetNode', 'inputs': {'widget_0': 'model'}},
 '5174': {'class_type': 'GetNode', 'inputs': {'widget_0': 'positive'}},
 '5173': {'class_type': 'GetNode', 'inputs': {'widget_0': 'negative'}},
 '5194': {'class_type': 'SetNode', 'inputs': {'widget_0': 'height', 'INT': ['5207', 0]}},
 '5195': {'class_type': 'SetNode', 'inputs': {'widget_0': 'width', 'INT': ['5206', 0]}},
 '5196': {'class_type': 'SetNode', 'inputs': {'widget_0': 'fps', 'FLOAT': ['5199', 0]}},
 '5199': {'class_type': 'PrimitiveFloat', 'inputs': {'widget_0': 8}},
 '5202': {'class_type': 'SimpleCalculatorKJ',
          'inputs': {'widget_0': '((round((a * b -1) / 8)) * 8) + 1 ',
                     'variables.a': ['5205', 0],
                     'variables.b': ['5203', 0]}},
 '5203': {'class_type': 'GetNode', 'inputs': {'widget_0': 'fps'}},
 '5204': {'class_type': 'SetNode', 'inputs': {'widget_0': 'frames', 'INT': ['5202', 1]}},
 '5205': {'class_type': 'INTConstant', 'inputs': {'widget_0': 10}},
 '5197': {'class_type': 'SetNode', 'inputs': {'widget_0': 't2v_mode', 'BOOLEAN': ['5198', 0]}},
 '5143': {'class_type': 'GetNode', 'inputs': {'widget_0': 'vae'}},
 '5216': {'class_type': 'GetNode', 'inputs': {'widget_0': 'fps'}},
 '3336': {'class_type': 'LTXVPreprocess', 'inputs': {'widget_0': 18, 'image': ['5177', 0]}},
 '5145': {'class_type': 'GetNode', 'inputs': {'widget_0': 'vae_audio'}},
 '5209': {'class_type': 'GetNode', 'inputs': {'widget_0': 'fps'}},
 '5158': {'class_type': 'GetNode', 'inputs': {'widget_0': 'ref_frames'}},
 '5213': {'class_type': 'GetNode', 'inputs': {'widget_0': 'height'}},
 '5212': {'class_type': 'GetNode', 'inputs': {'widget_0': 'width'}},
 '5218': {'class_type': 'GetNode', 'inputs': {'widget_0': 'fps'}},
 '5217': {'class_type': 'GetNode', 'inputs': {'widget_0': 'frames'}},
 '5214': {'class_type': 'ResizeImageMaskNode',
          'inputs': {'widget_0': 'scale by multiplier', 'widget_1': 256, 'widget_2': 'area', 'input': ['5211', 0]}},
 '5219': {'class_type': 'GetImageSize', 'inputs': {'image': ['5214', 0]}},
 '5151': {'class_type': 'SetNode', 'inputs': {'widget_0': 'ref_video', 'IMAGE': ['5221', 0]}},
 '5034': {'class_type': 'SimpleMath+', 'inputs': {'widget_0': 'a*32', 'a': ['5185', 0]}},
 '5185': {'class_type': 'GetNode', 'inputs': {'widget_0': 'latent_down_factor'}},
 '5153': {'class_type': 'SetNode', 'inputs': {'widget_0': 'ref_height', 'INT': ['5029', 1]}},
 '5154': {'class_type': 'SetNode', 'inputs': {'widget_0': 'ref_width', 'INT': ['5029', 0]}},
 '5155': {'class_type': 'SetNode', 'inputs': {'widget_0': 'ref_frames', 'INT': ['5029', 2]}},
 '5156': {'class_type': 'GetNode', 'inputs': {'widget_0': 'ref_height'}},
 '5157': {'class_type': 'GetNode', 'inputs': {'widget_0': 'ref_width'}},
 '5082': {'class_type': 'LTXVCropGuides',
          'inputs': {'positive': ['5174', 0], 'negative': ['5173', 0], 'latent': ['5074', 0]}},
 '5074': {'class_type': 'LTXVSeparateAVLatent', 'inputs': {'av_latent': ['5073', 0]}},
 '5222': {'class_type': 'MarkdownNote',
          'inputs': {'widget_0': 'This automagically enhances your prompt using the already loaded Gemma model. But it '
                                 'can be a bit sensitive to having correct Gemma if using GGUF models. Alternatively '
                                 'you can bypass/disable  this feature '}},
 '5223': {'class_type': 'MarkdownNote',
          'inputs': {'widget_0': '## LTX-2 Prompting Tips\n'
                                 '1. **Core Actions**: Describe events and actions as they occur over time  \n'
                                 '2. **Audio**: Describe sounds and dialogue needed for the scene  \n'
                                 '3. **Reference Image**: Do not repeat details already present  \n'
                                 '4. **Consistency**: Avoid instructions that do not match the reference image, as '
                                 'this will degrade results'}},
 '5225': {'class_type': 'MarkdownNote',
          'inputs': {'widget_0': 'If low on Ram/Vram, try  768x512, 832x480 or 960x544.  With higher Vram you can try '
                                 '1280x736 or 1920x1088\n'
                                 '\n'
                                 'Width & height settings must be divisible by 32 + 1. \n'
                                 'Frame count must be divisible by 8 + 1. \n'
                                 '\n'
                                 'Running with invalid parameters **will not cause errors**. Instead, the flow will '
                                 'silently choose the closest valid parameters. \n'
                                 '\n'
                                 '**Length in seconds:**  try 5, 10 or 20. \n'
                                 '\n'
                                 '**FPS:** 24 or 25 (or 48 if your pc can run it)\n'
                                 '\n'}},
 '5226': {'class_type': 'MarkdownNote',
          'inputs': {'widget_0': 'If using some user made LTX-2 loras they sometimes are not trained on audio, so it '
                                 'will produce very noisy audio outputs. Try use KJNodes LTX-2 Lora Loader Advanced in '
                                 'such cases, and set the non video strenght to zero\n'}},
 '5227': {'class_type': 'MarkdownNote', 'inputs': {'widget_0': 'taeltx2_3.safetensors'}},
 '5228': {'class_type': 'DualCLIPLoaderGGUF',
          'inputs': {'widget_0': 'gemma-3-12b-it-Q2_K.gguf',
                     'widget_1': 'ltx-2.3_text_projection_bf16.safetensors',
                     'widget_2': 'sdxl'}},
 '5229': {'class_type': 'UnetLoaderGGUF',
          'inputs': {'widget_0': 'LTXvideo\\LTX-2\\quantstack\\LTX-2.3-distilled-Q4_K_S.gguf'}},
 '5230': {'class_type': 'MarkdownNote',
          'inputs': {'widget_0': 'Input a  reference video that carries the desired camera motion\n'
                                 '\n'
                                 '\n'
                                 'The model transfers the camera behavior from the reference into the generated '
                                 'output. No trigger word is required.\n'
                                 '\n'
                                 'If the camera motion transfer feels too subtle, explicitly describe the desired '
                                 'movement in the prompt. This can strengthen the effect.\n'}},
 '5231': {'class_type': 'PathchSageAttentionKJ',
          'inputs': {'widget_0': 'auto', 'widget_1': False, 'model': ['5011', 0]}},
 '5232': {'class_type': 'LTXVChunkFeedForward', 'inputs': {'widget_0': 2, 'widget_1': 4096, 'model': ['5231', 0]}},
 '5234': {'class_type': 'SetNode', 'inputs': {'widget_0': 'model_with_lora', 'MODEL': ['5275', 0]}},
 '5236': {'class_type': 'GetNode', 'inputs': {'widget_0': 'enhance_prompt'}},
 '2483': {'class_type': 'CLIPTextEncode',
          'inputs': {'widget_0': '= enhanced prompt = ', 'clip': ['5137', 0], 'text': ['5237', 0]}},
 '5237': {'class_type': '94e8f3a0-557f-4580-93a0-f762c7b0d076',
          'inputs': {'clip': ['5235', 0], 'image': ['5241', 0], '_1': ['5242', 0]}},
 '5241': {'class_type': 'ResizeImageMaskNode',
          'inputs': {'widget_0': 'scale by multiplier', 'widget_1': 256, 'widget_2': 'area', 'input': ['5035', 0]}},
 '5235': {'class_type': 'GetNode', 'inputs': {'widget_0': 'clip'}},
 '5200': {'class_type': 'SetNode', 'inputs': {'widget_0': 'enhance_prompt', 'BOOLEAN': ['5201', 0]}},
 '5198': {'class_type': 'PrimitiveBoolean', 'inputs': {'widget_0': False}},
 '4832': {'class_type': 'RandomNoise', 'inputs': {'widget_0': 42, 'widget_1': 'fixed'}},
 '4831': {'class_type': 'KSamplerSelect', 'inputs': {'widget_0': 'euler_ancestral_cfg_pp'}},
 '4828': {'class_type': 'CFGGuider',
          'inputs': {'widget_0': 2.5, 'model': ['5149', 0], 'positive': ['5012', 0], 'negative': ['5012', 1]}},
 '5250': {'class_type': 'GetNode', 'inputs': {'widget_0': 'negative'}},
 '1241': {'class_type': 'LTXVConditioning',
          'inputs': {'widget_0': 8, 'positive': ['2483', 0], 'negative': ['2612', 0], 'frame_rate': ['5216', 0]}},
 '5166': {'class_type': 'SetNode', 'inputs': {'widget_0': 'negative_guider', 'CONDITIONING': ['5012', 1]}},
 '5163': {'class_type': 'GetNode', 'inputs': {'widget_0': 'positive'}},
 '5253': {'class_type': 'GetNode', 'inputs': {'widget_0': 'negative'}},
 '5251': {'class_type': 'LTX2_NAG',
          'inputs': {'widget_0': 11,
                     'widget_1': 0.25,
                     'widget_2': 2.5,
                     'widget_3': True,
                     'model': ['5187', 0],
                     'nag_cond_video': ['5253', 0],
                     'nag_cond_audio': ['5253', 0]}},
 '5068': {'class_type': 'RandomNoise', 'inputs': {'widget_0': 43, 'widget_1': 'fixed'}},
 '4845': {'class_type': 'LTXVSeparateAVLatent', 'inputs': {'av_latent': ['4829', 0]}},
 '5069': {'class_type': 'CFGGuider',
          'inputs': {'widget_0': 2.5, 'model': ['5150', 0], 'positive': ['5171', 0], 'negative': ['5172', 0]}},
 '5013': {'class_type': 'LTXVCropGuides',
          'inputs': {'positive': ['5169', 0], 'negative': ['5170', 0], 'latent': ['4845', 0]}},
 '5067': {'class_type': 'LTXVImgToVideoInplace',
          'inputs': {'widget_0': 0.7,
                     'widget_1': False,
                     'vae': ['5141', 0],
                     'image': ['5176', 0],
                     'latent': ['5013', 2],
                     'bypass': ['5180', 0]}},
 '5072': {'class_type': 'LTXVConcatAVLatent', 'inputs': {'video_latent': ['5067', 0], 'audio_latent': ['4845', 1]}},
 '4829': {'class_type': 'SamplerCustomAdvanced',
          'inputs': {'noise': ['4832', 0],
                     'guider': ['4828', 0],
                     'sampler': ['4831', 0],
                     'sigmas': ['5025', 0],
                     'latent_image': ['4528', 0]}},
 '5073': {'class_type': 'SamplerCustomAdvanced',
          'inputs': {'noise': ['5068', 0],
                     'guider': ['5069', 0],
                     'sampler': ['5070', 0],
                     'sigmas': ['5071', 0],
                     'latent_image': ['5072', 0]}},
 '5026': {'class_type': 'ResizeImageMaskNode',
          'inputs': {'widget_0': 'scale shorter dimension',
                     'widget_1': 256,
                     'widget_2': 'lanczos',
                     'input': ['5214', 0]}},
 '5029': {'class_type': 'GetImageSize', 'inputs': {'image': ['5221', 0]}},
 '2004': {'class_type': 'LoadImage',
          'inputs': {'widget_0': 'fjf1oxsjnnrgphxxrnzx6dh4k9-nano-banana-gemini-3-pro-image-ultra-realistic-black-and-white-cinematic-fullbody-portrait-of-muhammad-ali-standing-side-lighting-strong-contrast-intense-mysterious-expression-sharp.jpg',
                     'widget_1': 'image'}},
 '5035': {'class_type': 'ResizeImageMaskNode',
          'inputs': {'widget_0': 'scale longer dimension',
                     'widget_1': 256,
                     'widget_2': 'lanczos',
                     'input': ['2004', 0]}},
 '5175': {'class_type': 'SetNode', 'inputs': {'widget_0': 'ref_image', 'IMAGE': ['5035', 0]}},
 '5193': {'class_type': 'SetNode', 'inputs': {'widget_0': 'audio_original', 'AUDIO': ['5192', 2]}},
 '5160': {'class_type': 'GetNode', 'inputs': {'widget_0': 'ref_width'}},
 '5147': {'class_type': 'GetNode', 'inputs': {'widget_0': 'vae_audio'}},
 '5159': {'class_type': 'GetNode', 'inputs': {'widget_0': 'ref_height'}},
 '5260': {'class_type': 'SetNode', 'inputs': {'widget_0': 'latent_audio_custom', 'LATENT': ['5081', 0]}},
 '5080': {'class_type': 'SolidMask',
          'inputs': {'widget_0': 0, 'widget_1': 512, 'widget_2': 512, 'width': ['5160', 0], 'height': ['5159', 0]}},
 '5127': {'class_type': 'VAELoaderKJ',
          'inputs': {'widget_0': 'LTX23_audio_vae_bf16.safetensors', 'widget_1': 'main_device', 'widget_2': 'bf16'}},
 '5132': {'class_type': 'LatentUpscaleModelLoader',
          'inputs': {'widget_0': 'ltx-2.3-spatial-upscaler-x2-1.1.safetensors'}},
 '5130': {'class_type': 'UNETLoader',
          'inputs': {'widget_0': 'ltx-2.3-22b-distilled-1.1_transformer_only_fp8_scaled.safetensors',
                     'widget_1': 'default'}},
 '5148': {'class_type': 'SetNode', 'inputs': {'widget_0': 'model_iclora', 'MODEL': ['5011', 0]}},
 '5183': {'class_type': 'SetNode', 'inputs': {'widget_0': 'latent_down_factor', 'FLOAT': ['5011', 1]}},
 '5188': {'class_type': 'GetNode', 'inputs': {'widget_0': 'model_with_lora'}},
 '5190': {'class_type': 'GetNode', 'inputs': {'widget_0': 'vae_tiny'}},
 '5187': {'class_type': 'LTX2SamplingPreviewOverride',
          'inputs': {'widget_0': 8, 'model': ['5188', 0], 'vae': ['5190', 0]}},
 '5189': {'class_type': 'SetNode', 'inputs': {'widget_0': 'model', 'MODEL': ['5251', 0]}},
 '5076': {'class_type': 'LTXVAudioVAEDecode', 'inputs': {'samples': ['5074', 1], 'audio_vae': ['5145', 0]}},
 '5266': {'class_type': 'SetNode', 'inputs': {'widget_0': 'video_output', 'IMAGE': ['5075', 0]}},
 '5075': {'class_type': 'VAEDecodeTiled',
          'inputs': {'widget_0': 544,
                     'widget_1': 64,
                     'widget_2': 4096,
                     'widget_3': 4,
                     'samples': ['5082', 2],
                     'vae': ['5143', 0]}},
 '5268': {'class_type': 'VAEDecodeTiled', 'inputs': {'widget_0': 544, 'widget_1': 64, 'widget_2': 4096, 'widget_3': 4}},
 '5267': {'class_type': 'GetNode', 'inputs': {'widget_0': 'audio_output'}},
 '5269': {'class_type': 'GetNode', 'inputs': {'widget_0': 'video_output'}},
 '5208': {'class_type': 'VHS_VideoCombine',
          'inputs': {'images': ['5269', 0], 'audio': ['5267', 0], 'frame_rate': ['5209', 0]}},
 '5201': {'class_type': 'PrimitiveBoolean', 'inputs': {'widget_0': False}},
 '5233': {'class_type': 'LTX2AttentionTunerPatch',
          'inputs': {'widget_0': '',
                     'widget_1': 1,
                     'widget_2': 1,
                     'widget_3': 1,
                     'widget_4': 1,
                     'widget_5': True,
                     'model': ['5232', 0]}},
 '5131': {'class_type': 'LoraLoaderModelOnly',
          'inputs': {'widget_0': 'LTX\\LTX-2\\ltx-2.3-22b-distilled-lora-384.safetensors',
                     'widget_1': 0.6,
                     'model': ['5130', 0]}},
 '5224': {'class_type': 'MarkdownNote',
          'inputs': {'widget_0': 'Download models from here:\n'
                                 '\n'
                                 '\n'
                                 'https://huggingface.co/Kijai/LTX2.3_comfy\n'
                                 '\n'
                                 'Text encoder : https://huggingface.co/Comfy-Org/ltx-2 \n'
                                 '\n'
                                 'IC-Union Control lora:  '
                                 'https://huggingface.co/Lightricks/LTX-2.3-22b-IC-LoRA-Union-Control'}},
 '5275': {'class_type': 'Power Lora Loader (rgthree)', 'inputs': {'widget_3': '', 'model': ['5233', 0]}},
 '5011': {'class_type': 'LTXICLoRALoaderModelOnly',
          'inputs': {'widget_0': 'LTX\\LTX-2\\IC-Lora\\ltx-2.3-22b-v1.1-ic-lora-union-control-ref0.5.safetensors',
                     'widget_1': 0.71,
                     'model': ['5131', 0]}},
 '5276': {'class_type': 'SetNode', 'inputs': {'widget_0': 'ref_blended', 'IMAGE': ['5115', 0]}},
 '5277': {'class_type': 'SetNode', 'inputs': {'widget_0': 'ref_pose', 'IMAGE': ['4986', 0]}},
 '5280': {'class_type': 'SetNode', 'inputs': {'widget_0': 'ref_selected', 'IMAGE': ['5272', 0]}},
 '5278': {'class_type': 'GetNode', 'inputs': {'widget_0': 'ref_blended'}},
 '5279': {'class_type': 'GetNode', 'inputs': {'widget_0': 'ref_pose'}},
 '5281': {'class_type': 'GetNode', 'inputs': {'widget_0': 'ref_selected'}},
 '5221': {'class_type': 'ImageResizeKJv2',
          'inputs': {'widget_0': 512,
                     'widget_1': 512,
                     'widget_2': 'nearest-exact',
                     'widget_3': 'crop',
                     'widget_4': '0, 0, 0',
                     'widget_5': 'center',
                     'widget_6': 2,
                     'widget_7': 'cpu',
                     'image': ['5281', 0],
                     'width': ['5219', 0],
                     'height': ['5219', 1],
                     'divisible_by': ['5034', 0]}},
 '5284': {'class_type': 'SimpleCalculatorKJ',
          'inputs': {'widget_0': 'a / b ', 'variables.a': ['5285', 0], 'variables.b': ['5286', 0]}},
 '5285': {'class_type': 'GetNode', 'inputs': {'widget_0': 'ref_frames'}},
 '5286': {'class_type': 'GetNode', 'inputs': {'widget_0': 'fps'}},
 '5282': {'class_type': 'SetNode', 'inputs': {'widget_0': 'audio_custom', 'AUDIO': ['5283', 0]}},
 '5289': {'class_type': 'EmptyAudio',
          'inputs': {'widget_0': 60, 'widget_1': 44100, 'widget_2': 2, 'duration': ['5290', 0]}},
 '5290': {'class_type': 'SimpleCalculatorKJ',
          'inputs': {'widget_0': 'a / b', 'variables.a': ['5291', 0], 'variables.b': ['5292', 0]}},
 '5291': {'class_type': 'GetNode', 'inputs': {'widget_0': 'ref_frames'}},
 '5292': {'class_type': 'GetNode', 'inputs': {'widget_0': 'fps'}},
 '5288': {'class_type': 'GetNode', 'inputs': {'widget_0': 'audio_original'}},
 '5287': {'class_type': 'GetNode', 'inputs': {'widget_0': 'audio_custom'}},
 '5293': {'class_type': 'SetNode', 'inputs': {'widget_0': 'audio_selected', 'AUDIO': ['5274', 0]}},
 '2612': {'class_type': 'CLIPTextEncode',
          'inputs': {'widget_0': 'low contrast, washed out, text, subtitles, logo, still image, still video, blurry, '
                                 'low quality, distorted, bad anatomy, oversaturated, pixelated, low resolution, '
                                 'grainy, compression artifacts, jpeg artifacts, glitches, watermark, signature, '
                                 'copyright,  distortedsound, saturated sound, loud sound , deformed facial features, '
                                 'asymmetrical face, missing facial features, extra limbs, disfigured hands, blurry '
                                 'teeth, disfigured teeth',
                     'clip': ['5137', 0]}},
 '5081': {'class_type': 'SetLatentNoiseMask', 'inputs': {'samples': ['5079', 0], 'mask': ['5080', 0]}},
 '5296': {'class_type': 'GetNode', 'inputs': {'widget_0': 'audio_selected'}},
 '5283': {'class_type': 'TrimAudioDuration',
          'inputs': {'widget_0': 0, 'widget_1': 60, 'audio': ['5263', 0], 'duration': ['5284', 0]}},
 '5263': {'class_type': 'LoadAudio', 'inputs': {'widget_0': '(Verse).mp3'}},
 '5079': {'class_type': 'LTXVAudioVAEEncode', 'inputs': {'audio': ['5296', 0], 'audio_vae': ['5147', 0]}},
 '3059': {'class_type': 'EmptyLTXVLatentVideo',
          'inputs': {'width': ['5157', 0],
                     'height': ['5156', 0],
                     'length': ['5158', 0],
                     'widget_0': 256,
                     'widget_1': 256,
                     'widget_2': 5,
                     'widget_3': 1}},
 '3159': {'class_type': 'LTXVImgToVideoConditionOnly',
          'inputs': {'widget_0': 1,
                     'widget_1': False,
                     'vae': ['5139', 0],
                     'image': ['3336', 0],
                     'latent': ['3059', 0],
                     'bypass': ['5181', 0]}},
 '5247': {'class_type': 'SimpleCalculatorKJ', 'inputs': {'widget_0': 'a', 'variables.a': ['5245', 0]}},
 '5255': {'class_type': 'GetNode', 'inputs': {'widget_0': 'vae_audio'}},
 '5245': {'class_type': 'GetNode', 'inputs': {'widget_0': 'fps'}},
 '5248': {'class_type': 'GetNode', 'inputs': {'widget_0': 'ref_frames'}},
 '5258': {'class_type': 'SetNode', 'inputs': {'widget_0': 'latent_audio_selected', 'LATENT': ['5256', 0]}},
 '5294': {'class_type': 'SetNode', 'inputs': {'widget_0': 'latent_audio', 'LATENT': ['5243', 0]}},
 '5257': {'class_type': 'GetNode', 'inputs': {'widget_0': 'latent_audio_selected'}},
 '4528': {'class_type': 'LTXVConcatAVLatent', 'inputs': {'video_latent': ['5012', 2], 'audio_latent': ['5257', 0]}},
 '5243': {'class_type': 'LTXVEmptyLatentAudio',
          'inputs': {'frames_number': ['5248', 0],
                     'frame_rate': ['5247', 1],
                     'widget_0': 5,
                     'widget_1': 8,
                     'widget_2': 1,
                     'audio_vae': ['5255', 0]}},
 '5192': {'class_type': 'VHS_LoadVideoFFmpeg', 'inputs': {'force_rate': ['5218', 0], 'frame_load_cap': ['5217', 0]}},
 '5211': {'class_type': 'ImageResizeKJv2',
          'inputs': {'widget_0': 512,
                     'widget_1': 512,
                     'widget_2': 'nearest-exact',
                     'widget_3': 'crop',
                     'widget_4': '0, 0, 0',
                     'widget_5': 'center',
                     'widget_6': 2,
                     'widget_7': 'cpu',
                     'image': ['5192', 0],
                     'width': ['5212', 0],
                     'height': ['5213', 0]}},
 '5115': {'class_type': 'ImageBlend',
          'inputs': {'widget_0': 0.5, 'widget_1': 'multiply', 'image1': ['4986', 0], 'image2': ['5114', 0]}},
 '4986': {'class_type': 'DWPreprocessor',
          'inputs': {'widget_0': 'enable',
                     'widget_1': 'enable',
                     'widget_2': 'enable',
                     'widget_3': 256,
                     'widget_4': 'yolox_l.onnx',
                     'widget_5': 'dw-ll_ucoco_384_bs5.torchscript.pt',
                     'widget_6': 'disable',
                     'image': ['5026', 0]}},
 '5274': {'class_type': 'ComfySwitchNode',
          'inputs': {'widget_0': False, 'on_false': ['5273', 0], 'on_true': ['5287', 0]}},
 '5298': {'class_type': 'PrimitiveFloat', 'inputs': {'widget_0': 8}},
 '5300': {'class_type': 'SetNode', 'inputs': {'widget_0': 'ref_strength', 'FLOAT': ['5299', 0]}},
 '5299': {'class_type': 'PrimitiveFloat', 'inputs': {'widget_0': 8}},
 '5301': {'class_type': 'GetNode', 'inputs': {'widget_0': 'ref_strength'}},
 '5012': {'class_type': 'LTXAddVideoICLoRAGuide',
          'inputs': {'widget_0': 0,
                     'widget_1': 0.7,
                     'widget_2': 1,
                     'widget_3': 'disabled',
                     'widget_4': False,
                     'widget_5': 128,
                     'widget_6': 32,
                     'positive': ['5163', 0],
                     'negative': ['5164', 0],
                     'vae': ['5146', 0],
                     'latent': ['3159', 0],
                     'image': ['5152', 0],
                     'strength': ['5301', 0],
                     'latent_downscale_factor': ['5184', 0]}},
 '5242': {'class_type': 'PrimitiveStringMultiline',
          'inputs': {'widget_0': 'highly detailed, monochrime colors. Make this image come alive with fluid motion. \n'
                                 '\n'
                                 'A make boxer. \n'
                                 '\n'
                                 'He is dancing in sync to the music '}},
 '5207': {'class_type': 'INTConstant', 'inputs': {'widget_0': 1280}},
 '5206': {'class_type': 'INTConstant', 'inputs': {'widget_0': 736}},
 '5120': {'class_type': 'VHS_VideoCombine', 'inputs': {'images': ['5221', 0]}},
 '5114': {'class_type': 'DepthAnythingPreprocessor',
          'inputs': {'widget_0': 'depth_anything_vitl14.pth', 'widget_1': 512, 'image': ['5026', 0]}},
 '5272': {'class_type': 'ComfySwitchNode',
          'inputs': {'widget_0': False, 'on_false': ['5279', 0], 'on_true': ['5278', 0]}},
 '5265': {'class_type': 'SetNode', 'inputs': {'widget_0': 'audio_output', 'AUDIO': ['5264', 0]}},
 '5210': {'class_type': 'GetNode', 'inputs': {'widget_0': 'audio_selected'}},
 '5305': {'class_type': 'GetNode', 'inputs': {'widget_0': 'audio_custom_mode'}},
 '5264': {'class_type': 'ComfySwitchNode',
          'inputs': {'widget_0': True, 'on_false': ['5076', 0], 'on_true': ['5210', 0], 'switch': ['5305', 0]}},
 '5295': {'class_type': 'GetNode', 'inputs': {'widget_0': 'latent_audio'}},
 '5261': {'class_type': 'GetNode', 'inputs': {'widget_0': 'latent_audio_custom'}},
 '5306': {'class_type': 'GetNode', 'inputs': {'widget_0': 'audio_custom_mode'}},
 '5256': {'class_type': 'ComfySwitchNode',
          'inputs': {'widget_0': True, 'on_false': ['5295', 0], 'on_true': ['5261', 0], 'switch': ['5306', 0]}},
 '5304': {'class_type': 'SetNode', 'inputs': {'widget_0': 'audio_custom_mode', 'BOOLEAN': ['5303', 0]}},
 '5297': {'class_type': 'MarkdownNote',
          'inputs': {'widget_0': 'This workflow has 3 ways you can choose what audio to use. \n'
                                 '\n'
                                 '**AUDIO FROM INPUT VIDEO** \n'
                                 '\n'
                                 'Uses the audio from your input video and LTX hears this audio. Can be useful for '
                                 'dance, playing music instruments, talking etc. \n'
                                 '\n'
                                 '**CUSTOM AUDIO**\n'
                                 '\n'
                                 'Use your own audio file as input. \n'
                                 '\n'
                                 '**LTX NATIVE AUDIO** \n'
                                 '\n'
                                 'If you turn off *USE INPUT AUDIO* LTX will use its own audio  \n'}},
 '5303': {'class_type': 'PrimitiveBoolean', 'inputs': {'widget_0': True}},
 '5273': {'class_type': 'ComfySwitchNode',
          'inputs': {'widget_0': True, 'on_false': ['5289', 0], 'on_true': ['5288', 0]}},
 '5271': {'class_type': 'MarkdownNote',
          'inputs': {'widget_0': '**CONTROL VIDEO** \n'
                                 '\n'
                                 'This is the driving video that will influence LTX output in regards to pose and '
                                 'composition \n'
                                 '\n'
                                 '**OUTPUT LENGHT** \n'
                                 '\n'
                                 'The final output will be the length you set in seconds at "video settings" group. '
                                 'Unless the input video has shorter length. If the input video is shorter, this will '
                                 'be the length of the final LTX output also\n'
                                 '\n'
                                 '**INPUT AUDIO (OPTIONAL)**\n'
                                 ' \n'
                                 'You can also use the input audio from the input video and feed this to LTX. This can '
                                 'be useful for example if the video input has dialog or music etc that you want to '
                                 'use to influence dance or talk in LTX  \n'
                                 '\n'
                                 '**POSE - DEPTH **\n'
                                 '\n'
                                 'These are 2 different control signals LTX understands when using IC-Union-Control '
                                 'lora. You can try blend both pose and depth, or just use pose. \n'
                                 '\n'
                                 'You can play around with these to get different kinds of results\n'
                                 '\n'
                                 '\n'}}}

READY_METADATA = {'model_assets': [],
 'unbound_inputs': {'seed': 4791},
 'ready_template': 'video/ltx2_3_runexx_motion_transfer_dwpose',
 'workflow_template': 'ltx2_3_runexx_motion_transfer_dwpose',
 'capability': 'dwpose_motion_transfer',
 'source_role': 'materialized_ready_python_template',
 'source_workflow': 'workflow_corpus/custom_nodes/ltxvideo/runexx/LTX-2.3_Motion_Transfer_DWPose.json',
 'coverage_tier': 'supplemental',
 'approach': 'DWPose body motion transfer',
 'runtime_note': None,
 'discord_signal': None,
 'smoke_resolution': '256x256x5_frames',
 'ltx_best_practices': ['Use the official Lightricks workflows as runtime gates where possible.',
                        'Patch smoke runs to fp8/fp4 model assets, tiny frame counts, and low-VRAM loaders.',
                        'Bypass latent spatial upscalers in smoke runs until HiddenSwitch Comfy exposes '
                        'model_mmap_residency for LatentUpscaleModelManageable.',
                        'Keep community audio, lip-sync, and long-form workflows as ready templates until their custom '
                        'node packs and service credentials are declared.'],
 'comfy_configuration': {'reserve_vram': 12, 'cache_none': True, 'fp8_e4m3fn_text_enc': True}}

READY_REQUIREMENTS = {'models': [],
 'custom_nodes': ['ComfyUI-GGUF',
                  'ComfyUI-KJNodes',
                  'ComfyUI-LTXVideo',
                  'ComfyUI-VideoHelperSuite',
                  'comfyui_controlnet_aux']}


def build():
    return build_api_ready_workflow(
        API_WORKFLOW,
        source_path=__file__,
        workflow_id=READY_METADATA.get("ready_template", "video/ltx2_3_runexx_motion_transfer_dwpose"),
        ready_metadata=READY_METADATA,
        requirements=READY_REQUIREMENTS,
    )
