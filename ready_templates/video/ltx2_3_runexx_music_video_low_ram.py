from __future__ import annotations

from vibecomfy.registry.ready_template import build_api_ready_workflow


API_WORKFLOW = {'1555': {'class_type': 'SetNode', 'inputs': {'widget_0': 'upscale_model', 'LATENT_UPSCALE_MODEL': ['1561', 0]}},
 '1556': {'class_type': 'SetNode', 'inputs': {'widget_0': 'vae_audio', 'VAE': ['1567', 0]}},
 '1557': {'class_type': 'SetNode', 'inputs': {'widget_0': 'vae', 'VAE': ['1559', 0]}},
 '1563': {'class_type': 'MarkdownNote',
          'inputs': {'widget_0': '## LTX-2 Prompting Tips\n'
                                 '1. **Core Actions**: Describe events and actions as they occur over time  \n'
                                 '2. **Audio**: Describe sounds and dialogue needed for the scene  \n'
                                 '3. **Reference Image**: Do not repeat details already present  \n'
                                 '4. **Consistency**: Avoid instructions that do not match the reference image, as '
                                 'this will degrade results'}},
 '1568': {'class_type': 'SetNode', 'inputs': {'widget_0': 'vae_tiny', 'VAE': ['1569', 0]}},
 '1569': {'class_type': 'VAELoader', 'inputs': {'widget_0': 'taeltx2_3.safetensors'}},
 '1575': {'class_type': 'SetNode', 'inputs': {'widget_0': 'height', 'INT': ['1591', 0]}},
 '1576': {'class_type': 'SetNode', 'inputs': {'widget_0': 'width', 'INT': ['1606', 0]}},
 '1577': {'class_type': 'SetNode', 'inputs': {'widget_0': 'fps', 'FLOAT': ['1586', 0]}},
 '1597': {'class_type': 'GetNode', 'inputs': {'widget_0': 'vae_audio'}},
 '1601': {'class_type': 'GetNode', 'inputs': {'widget_0': 'width'}},
 '1617': {'class_type': 'SetNode', 'inputs': {'widget_0': 'model_with_lora', 'MODEL': ['2150', 0]}},
 '1622': {'class_type': 'GetNode', 'inputs': {'widget_0': 'clip'}},
 '1604': {'class_type': 'SolidMask',
          'inputs': {'widget_0': 0, 'widget_1': 512, 'widget_2': 512, 'width': ['1601', 0], 'height': ['1595', 0]}},
 '1595': {'class_type': 'GetNode', 'inputs': {'widget_0': 'height'}},
 '413': {'class_type': 'GetNode', 'inputs': {'widget_0': 'vae'}},
 '1635': {'class_type': 'GetNode', 'inputs': {'widget_0': 'frames'}},
 '1636': {'class_type': 'GetNode', 'inputs': {'widget_0': 'fps'}},
 '645': {'class_type': 'SetNode', 'inputs': {'widget_0': 'positive_base', 'CONDITIONING': ['164', 0]}},
 '646': {'class_type': 'SetNode', 'inputs': {'widget_0': 'negative_base', 'CONDITIONING': ['164', 1]}},
 '1570': {'class_type': 'UNETLoader',
          'inputs': {'widget_0': 'ltx-2.3-22b-distilled_transformer_only_fp8_scaled.safetensors',
                     'widget_1': 'default'}},
 '236': {'class_type': 'GetNode', 'inputs': {'widget_0': 'vae'}},
 '1528': {'class_type': 'SetNode', 'inputs': {'widget_0': 'start_seed', 'INT': ['1527', 0]}},
 '1560': {'class_type': 'LoraLoaderModelOnly',
          'inputs': {'widget_0': 'LTX\\LTX-2\\ltx-2.3-22b-distilled-lora-384.safetensors',
                     'widget_1': 0.6,
                     'model': ['1570', 0]}},
 '1605': {'class_type': 'LTXVAudioVAEEncode', 'inputs': {'audio': ['1653', 0], 'audio_vae': ['1597', 0]}},
 '1590': {'class_type': 'SetNode', 'inputs': {'widget_0': 'audio_vocals', 'AUDIO': ['1599', 0]}},
 '245': {'class_type': 'LTXVSeparateAVLatent', 'inputs': {'av_latent': ['2182', 0]}},
 '1738': {'class_type': 'SetNode', 'inputs': {'widget_0': 'image_strength', 'FLOAT': ['1722', 0]}},
 '2023': {'class_type': 'GetImageSizeAndCount', 'inputs': {'image': ['1318', 0]}},
 '1938': {'class_type': 'SetNode', 'inputs': {'widget_0': 'height_generated', 'INT': ['2023', 2]}},
 '1939': {'class_type': 'SetNode', 'inputs': {'widget_0': 'width_generated', 'INT': ['2023', 1]}},
 '1626': {'class_type': 'CLIPTextEncode',
          'inputs': {'widget_0': 'text, subtitles, logo, still image, still video, no motion, static, frozen, blurry, '
                                 'low quality, distorted, bad anatomy, oversaturated, pixelated, low resolution, '
                                 'grainy, compression artifacts, jpeg artifacts, glitches, watermark, signature, '
                                 'copyright,  distortedsound, saturated sound, loud sound , deformed facial features, '
                                 'asymmetrical face, missing facial features, extra limbs, disfigured hands, blurry '
                                 'teeth, disfigured teeth',
                     'clip': ['1622', 0]}},
 '1600': {'class_type': 'MelBandRoFormerModelLoader',
          'inputs': {'widget_0': 'MelBandRoformer\\MelBandRoformer_fp16.safetensors'}},
 '1599': {'class_type': 'MelBandRoFormerSampler', 'inputs': {'model': ['1600', 0], 'audio': ['1598', 0]}},
 '1602': {'class_type': 'SetNode', 'inputs': {'widget_0': 'latent_custom_audio', 'LATENT': ['1603', 0]}},
 '2113': {'class_type': 'GetNode', 'inputs': {'widget_0': 'ref_image'}},
 '2110': {'class_type': 'GetNode', 'inputs': {'widget_0': 'clip'}},
 '2111': {'class_type': 'GetNode', 'inputs': {'widget_0': 'enhance_prompt'}},
 '1621': {'class_type': 'CLIPTextEncode',
          'inputs': {'widget_0': '= Enhanced Prompt = \n', 'clip': ['1622', 0], 'text': ['2109', 0]}},
 '2115': {'class_type': 'SetNode', 'inputs': {'widget_0': 'enhance_prompt', 'BOOLEAN': ['2116', 0]}},
 '2109': {'class_type': '3bd4eeb9-31fa-461a-8c04-2b24dd0aabaf',
          'inputs': {'clip': ['2110', 0], 'image': ['2113', 0], '_1': ['1624', 0]}},
 '1567': {'class_type': 'VAELoaderKJ',
          'inputs': {'widget_0': 'LTX23_audio_vae_bf16.safetensors', 'widget_1': 'main_device', 'widget_2': 'bf16'}},
 '1559': {'class_type': 'VAELoader', 'inputs': {'widget_0': 'LTX23_video_vae_bf16.safetensors'}},
 '1558': {'class_type': 'SetNode', 'inputs': {'widget_0': 'clip', 'CLIP': ['1562', 0]}},
 '1572': {'class_type': 'MarkdownNote',
          'inputs': {'widget_0': 'Download models from here:\n'
                                 '\n'
                                 '\n'
                                 'https://huggingface.co/Kijai/LTX2.3_comfy\n'
                                 '\n'
                                 'Text encoder : https://huggingface.co/Comfy-Org/ltx-2'}},
 '2151': {'class_type': 'GetNode', 'inputs': {'widget_0': 'vae'}},
 '2153': {'class_type': 'LTXVConcatAVLatent', 'inputs': {'video_latent': ['2183', 0], 'audio_latent': ['2159', 1]}},
 '2159': {'class_type': 'LTXVSeparateAVLatent', 'inputs': {'av_latent': ['2181', 0]}},
 '2164': {'class_type': 'GetNode', 'inputs': {'widget_0': 'vae_tiny'}},
 '2169': {'class_type': 'RandomNoise', 'inputs': {'widget_0': 420, 'widget_1': 'fixed'}},
 '2171': {'class_type': 'GetNode', 'inputs': {'widget_0': 'model'}},
 '2173': {'class_type': 'BasicScheduler',
          'inputs': {'steps': 1, 'widget_0': 1, 'widget_1': 4, 'widget_2': 1, 'model': ['2175', 0]}},
 '2175': {'class_type': 'ModelSamplingSD3', 'inputs': {'widget_0': 13, 'model': ['2171', 0]}},
 '2179': {'class_type': 'RandomNoise', 'inputs': {'widget_0': 42, 'widget_1': 'fixed'}},
 '164': {'class_type': 'LTXVConditioning',
         'inputs': {'widget_0': 8, 'positive': ['1621', 0], 'negative': ['1626', 0], 'frame_rate': ['1636', 0]}},
 '2184': {'class_type': 'SetNode', 'inputs': {'widget_0': 'model', 'MODEL': ['2178', 0]}},
 '2165': {'class_type': 'GetNode', 'inputs': {'widget_0': 'model_with_lora'}},
 '1562': {'class_type': 'DualCLIPLoader',
          'inputs': {'widget_0': 'gemma_3_12B_it_fp4_mixed.safetensors',
                     'widget_1': 'ltx-2.3_text_projection_bf16.safetensors',
                     'widget_2': 'ltxv',
                     'widget_3': 'default'}},
 '1630': {'class_type': 'ResizeImageMaskNode',
          'inputs': {'widget_0': 'scale by multiplier', 'widget_1': 256, 'widget_2': 'area', 'input': ['445', 0]}},
 '1631': {'class_type': 'GetImageSize', 'inputs': {'image': ['1630', 0]}},
 '2190': {'class_type': 'GetNode', 'inputs': {'widget_0': 'ref_image'}},
 '446': {'class_type': 'LTXVPreprocess', 'inputs': {'widget_0': 18, 'image': ['2190', 0]}},
 '2191': {'class_type': 'GetNode', 'inputs': {'widget_0': 'width_downscaled'}},
 '2192': {'class_type': 'GetNode', 'inputs': {'widget_0': 'height_downscaled'}},
 '2162': {'class_type': 'GetNode', 'inputs': {'widget_0': 'positive_base'}},
 '2155': {'class_type': 'GetNode', 'inputs': {'widget_0': 'positive_base'}},
 '2154': {'class_type': 'GetNode', 'inputs': {'widget_0': 'negative_base'}},
 '2167': {'class_type': 'GetNode', 'inputs': {'widget_0': 'negative_base'}},
 '2178': {'class_type': 'LTX2_NAG',
          'inputs': {'widget_0': 11,
                     'widget_1': 0.25,
                     'widget_2': 2.5,
                     'widget_3': True,
                     'model': ['2188', 0],
                     'nag_cond_video': ['2167', 0],
                     'nag_cond_audio': ['2167', 0]}},
 '2198': {'class_type': 'GetNode', 'inputs': {'widget_0': 'image_strength'}},
 '2157': {'class_type': 'GetNode', 'inputs': {'widget_0': 'ref_image'}},
 '2152': {'class_type': 'GetNode', 'inputs': {'widget_0': 'upscale_model'}},
 '2166': {'class_type': 'GetNode', 'inputs': {'widget_0': 'model'}},
 '350': {'class_type': 'LTXVConcatAVLatent', 'inputs': {'video_latent': ['4109', 0], 'audio_latent': ['1603', 0]}},
 '2161': {'class_type': 'GetNode', 'inputs': {'widget_0': 'positive_base'}},
 '2195': {'class_type': 'SetNode', 'inputs': {'widget_0': 'guider', 'GUIDER': ['2170', 0]}},
 '1603': {'class_type': 'SetLatentNoiseMask', 'inputs': {'samples': ['1605', 0], 'mask': ['1604', 0]}},
 '650': {'class_type': 'SetNode', 'inputs': {'widget_0': 'ref_image', 'IMAGE': ['2189', 0]}},
 '344': {'class_type': 'EmptyLTXVLatentVideo',
         'inputs': {'width': ['2191', 0],
                    'height': ['2192', 0],
                    'length': ['1635', 0],
                    'widget_0': 256,
                    'widget_1': 256,
                    'widget_2': 5,
                    'widget_3': 1}},
 '2313': {'class_type': 'SetNode', 'inputs': {'widget_0': 'guider_2', 'GUIDER': ['2177', 0]}},
 '2314': {'class_type': 'SetNode', 'inputs': {'widget_0': 'sigmas_2', 'SIGMAS': ['2176', 0]}},
 '2315': {'class_type': 'SetNode', 'inputs': {'widget_0': 'sampler_2', 'SAMPLER': ['2174', 0]}},
 '2176': {'class_type': 'ManualSigmas', 'inputs': {'widget_0': '0.85, 0.7250, 0.4219, 0.0'}},
 '2177': {'class_type': 'CFGGuider',
          'inputs': {'widget_0': 2.5, 'model': ['2171', 0], 'positive': ['2155', 0], 'negative': ['2154', 0]}},
 '2170': {'class_type': 'CFGGuider',
          'inputs': {'widget_0': 2.5, 'model': ['2166', 0], 'positive': ['2162', 0], 'negative': ['2161', 0]}},
 '1624': {'class_type': 'PrimitiveStringMultiline',
          'inputs': {'widget_0': 'Make this image come alive with fluid motion. Cinematic music video shot of a red '
                                 'haired woman. \n'
                                 '\n'
                                 'She sings with expressive motion and gesticulation. \n'
                                 'The song she is singing is a sweet slow melancolic melody. Her lips moves in perfect '
                                 'lip-sync to the attached audio.  \n'
                                 '\n'
                                 'She is walking through a mystical dreamy forrest, tracking camera as she walks '
                                 'towards the viewer. \n'
                                 'The camera pulls away slowly keeping same distance to the woman. \n'
                                 '\n'
                                 'Cinematic, volumetric lights, shadow play. \n'
                                 '\n'
                                 'IMPORTANT: The woman is singing, and her lips are moving with lip-sync to the lyrics '
                                 'of the song.'}},
 '1651': {'class_type': 'SimpleCalculatorKJ',
          'inputs': {'widget_0': '((round((a * b -1) / 8)) * 8) + 1 ',
                     'variables.a': ['2012', 0],
                     'variables.b': ['1586', 0]}},
 '1578': {'class_type': 'SetNode', 'inputs': {'widget_0': 'frames', 'INT': ['1651', 1]}},
 '3722': {'class_type': 'SetNode', 'inputs': {'widget_0': 'window_sec_01', 'FLOAT': ['2012', 0]}},
 '2012': {'class_type': 'PrimitiveFloat', 'inputs': {'widget_0': 8}},
 '1589': {'class_type': 'SetNode', 'inputs': {'widget_0': 'audio_original', 'AUDIO': ['1598', 0]}},
 '1594': {'class_type': 'LoadAudio', 'inputs': {'widget_0': 'ComfyUI_00152_.mp3'}},
 '3877': {'class_type': '5e410bb1-405a-4d3d-808b-8f5f29426943', 'inputs': {}},
 '1598': {'class_type': 'TrimAudioDuration',
          'inputs': {'widget_0': 11, 'widget_1': 40, 'audio': ['1594', 0], 'duration': ['3877', 0]}},
 '3878': {'class_type': 'MarkdownNote',
          'inputs': {'widget_0': 'It can greatly improve the results if you transcribe the lyrics for each segment in '
                                 'the prompt \n'
                                 '\n'
                                 'For example: \n'
                                 '\n'
                                 'And she sings: "...... " '}},
 '1564': {'class_type': 'MarkdownNote',
          'inputs': {'widget_0': 'If using some user made LTX-2 loras they sometimes are not trained on audio, so it '
                                 'will produce very noisy audio outputs. Try use KJNodes LTX-2 Lora Loader Advanced in '
                                 'such cases, and set the non video strenght to zero\n'}},
 '1565': {'class_type': 'MarkdownNote', 'inputs': {'widget_0': 'taeltx2_3.safetensors'}},
 '1566': {'class_type': 'MarkdownNote',
          'inputs': {'widget_0': 'This automagically enhances your prompt using the already loaded Gemma model. But it '
                                 'can be a bit sensitive to having correct Gemma if using GGUF models. Alternatively '
                                 'you can bypass/disable  this feature '}},
 '1573': {'class_type': 'DualCLIPLoaderGGUF',
          'inputs': {'widget_0': 'gemma-3-12b-it-Q2_K.gguf',
                     'widget_1': 'ltx-2.3_text_projection_bf16.safetensors',
                     'widget_2': 'sdxl'}},
 '3879': {'class_type': 'MarkdownNote',
          'inputs': {'widget_0': 'Use something like Qwen Image Edit or Flux Klein to create new scenes with same '
                                 'consistent characters. \n'
                                 '\n'
                                 'Qwen Image even has a "Next Scene" lora made for this purpose. As well as a '
                                 '"Different Angle" lora.  \n'
                                 '\n'
                                 'The above models works great in ComfyUI.\n'
                                 '\n'
                                 'Loras: \n'
                                 '\n'
                                 'https://huggingface.co/lovis93/next-scene-qwen-image-lora-2509\n'
                                 '\n'
                                 'https://huggingface.co/lovis93/Flux-2-Multi-Angles-LoRA-v2  \n'
                                 '\n'
                                 'https://huggingface.co/fal/Qwen-Image-Edit-2511-Multiple-Angles-LoRA\n'
                                 '\n'
                                 '\n'
                                 '\n'
                                 '\n'
                                 '---\n'
                                 '\n'
                                 'Outside of ComfyUI tools like Nano Banana, ChatGPT and Qwen LLM can also do this. '}},
 '1607': {'class_type': 'MarkdownNote',
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
 '1571': {'class_type': 'UnetLoaderGGUF',
          'inputs': {'widget_0': 'LTXvideo\\LTX-2\\quantstack\\LTX-2.3-distilled-Q4_K_S.gguf'}},
 '2325': {'class_type': 'SetNode', 'inputs': {'widget_0': 'window_sec_02', 'FLOAT': ['1997', 0]}},
 '1527': {'class_type': 'INTConstant', 'inputs': {'widget_0': 1000}},
 '2183': {'class_type': 'LTXVImgToVideoInplace',
          'inputs': {'widget_0': 1,
                     'widget_1': False,
                     'vae': ['2151', 0],
                     'image': ['2157', 0],
                     'latent': ['2159', 0],
                     'strength': ['2198', 0]}},
 '4109': {'class_type': 'LTXVImgToVideoInplace',
          'inputs': {'widget_0': 1, 'widget_1': False, 'vae': ['413', 0], 'image': ['446', 0], 'latent': ['344', 0]}},
 '2150': {'class_type': 'Power Lora Loader (rgthree)', 'inputs': {'widget_7': '', 'model': ['1523', 0]}},
 '2172': {'class_type': 'GetNode', 'inputs': {'widget_0': 'model'}},
 '1654': {'class_type': 'GetNode', 'inputs': {'widget_0': 'window_sec_01'}},
 '2181': {'class_type': 'SamplerCustomAdvanced',
          'inputs': {'noise': ['2179', 0],
                     'guider': ['2170', 0],
                     'sampler': ['2180', 0],
                     'sigmas': ['2187', 0],
                     'latent_image': ['350', 0]}},
 '2116': {'class_type': 'PrimitiveBoolean', 'inputs': {'widget_0': False}},
 '1628': {'class_type': 'GetNode', 'inputs': {'widget_0': 'width'}},
 '1629': {'class_type': 'GetNode', 'inputs': {'widget_0': 'height'}},
 '1561': {'class_type': 'LatentUpscaleModelLoader',
          'inputs': {'widget_0': 'ltx-2.3-spatial-upscaler-x2-1.1.safetensors'}},
 '1586': {'class_type': 'PrimitiveFloat', 'inputs': {'widget_0': 8}},
 '2174': {'class_type': 'KSamplerSelect', 'inputs': {'widget_0': 'euler_cfg_pp'}},
 '2188': {'class_type': 'LTX2SamplingPreviewOverride',
          'inputs': {'widget_0': 8, 'model': ['2165', 0], 'vae': ['2164', 0]}},
 '2185': {'class_type': 'ModelSamplingSD3', 'inputs': {'widget_0': 13, 'model': ['2172', 0]}},
 '2186': {'class_type': 'BasicScheduler',
          'inputs': {'steps': 1, 'widget_0': 1, 'widget_1': 10, 'widget_2': 1, 'model': ['2185', 0]}},
 '1653': {'class_type': 'TrimAudioDuration',
          'inputs': {'widget_0': 0, 'widget_1': 40, 'audio': ['1616', 0], 'duration': ['1654', 0]}},
 '1615': {'class_type': 'SetNode', 'inputs': {'widget_0': 'audio', 'AUDIO': ['1616', 0]}},
 '1616': {'class_type': 'ComfySwitchNode',
          'inputs': {'widget_0': True, 'on_false': ['1598', 0], 'on_true': ['1599', 0]}},
 '1608': {'class_type': 'MarkdownNote',
          'inputs': {'widget_0': '**AUDIO START FROM:** \n'
                                 ' For a longer music video, you can create multiple renders in a row. And use the '
                                 '"Trim Audio" node **start index** to set where you want to continue from. For '
                                 'example if the first render was 50 seconds, you can set start index to 50 seconds, '
                                 'and continue render the song from there\n'
                                 '\n'
                                 '----\n'
                                 '\n'
                                 'Mel-band RoFormer is optional for extracting a clean vocal only audio for the '
                                 'sampler. This can be useful for example if its a close up of a singer. For other '
                                 'music where you want instrument and dance to follow the beat, use full music track '
                                 'and not vocals only\n'
                                 '\n'
                                 'https://huggingface.co/Kijai/MelBandRoFormer_comfy/tree/main\n'
                                 '\n'
                                 'folder: models\\diffusion_models\n'}},
 '1606': {'class_type': 'INTConstant', 'inputs': {'widget_0': 832}},
 '1591': {'class_type': 'INTConstant', 'inputs': {'widget_0': 480}},
 '268': {'class_type': 'PathchSageAttentionKJ',
         'inputs': {'widget_0': 'auto', 'widget_1': False, 'model': ['1560', 0]}},
 '504': {'class_type': 'LTXVChunkFeedForward', 'inputs': {'widget_0': 2, 'widget_1': 4096, 'model': ['268', 0]}},
 '1523': {'class_type': 'LTX2AttentionTunerPatch',
          'inputs': {'widget_0': '',
                     'widget_1': 1,
                     'widget_2': 1,
                     'widget_3': 1,
                     'widget_4': 1,
                     'widget_5': True,
                     'model': ['504', 0]}},
 '4120': {'class_type': 'MarkdownNote',
          'inputs': {'widget_0': '**SET UNIQUE FOLDER NAME PER RUN:**  \n'
                                 '\n'
                                 'This **must** be set to a unique name (string with no spaces and with standard '
                                 'characters). \n'
                                 '\n'
                                 'This will be a temporary save directory for the frames generated.  \n'
                                 '\n'
                                 '**Alternatively you can delete the content of the folder, before running next run**\n'
                                 '\n'
                                 'Located in **comfyui/outout/MusicVideo**\n'}},
 '2182': {'class_type': 'SamplerCustomAdvanced',
          'inputs': {'noise': ['2169', 0],
                     'guider': ['2177', 0],
                     'sampler': ['2174', 0],
                     'sigmas': ['2176', 0],
                     'latent_image': ['2153', 0]}},
 '4711': {'class_type': 'GetNode', 'inputs': {'widget_0': 'foldername'}},
 '4710': {'class_type': 'GetNode', 'inputs': {'widget_0': 'fps'}},
 '1318': {'class_type': 'VAEDecode', 'inputs': {'samples': ['245', 0], 'vae': ['236', 0]}},
 '4728': {'class_type': 'GetNode', 'inputs': {'widget_0': 'foldername'}},
 '4729': {'class_type': 'GetNode', 'inputs': {'widget_0': 'fps'}},
 '582': {'class_type': 'GetNode', 'inputs': {'widget_0': 'audio_original'}},
 '4736': {'class_type': 'PrimitiveBoolean', 'inputs': {'widget_0': True}},
 '4740': {'class_type': 'PrimitiveBoolean', 'inputs': {'widget_0': True}},
 '4730': {'class_type': 'VHS_VideoCombine',
          'inputs': {'images': ['1318', 0],
                     'audio': ['582', 0],
                     'frame_rate': ['4729', 0],
                     'filename_prefix': ['4728', 0],
                     'save_output': ['4740', 0]}},
 '1805': {'class_type': 'PrimitiveStringMultiline',
          'inputs': {'widget_0': 'Make this image come alive with fluid motion. Cinematic music video shot of a red '
                                 'haired woman. \n'
                                 '\n'
                                 'She sings with expressive motion and gesticulation. \n'
                                 'The song she is singing is a sweet slow melancolic melody. Her lips moves in perfect '
                                 'lip-sync to the attached audio.  \n'
                                 '\n'
                                 'She is walking through a romantic greenhouse with flowers and warm light, tracking '
                                 'camera as she walks towards the viewer.\n'
                                 '\n'
                                 'She sings the lyrics: "I type a whisper, watch it bloom. In pixel fog and quiet '
                                 'rooms. A hundred frames begin to breathe. While melodies I couldn’t weave" \n'
                                 '\n'
                                 'Cinematic, volumetric lights, shadow play.\n'
                                 '\n'
                                 'IMPORTANT: The woman is singing, and her lips are moving with lip-sync to the lyrics '
                                 'of the song.'}},
 '1722': {'class_type': 'PrimitiveFloat', 'inputs': {'widget_0': 8}},
 '4709': {'class_type': 'VHS_VideoCombine',
          'inputs': {'images': ['2329', 1],
                     'audio': ['2329', 2],
                     'frame_rate': ['4710', 0],
                     'filename_prefix': ['4711', 0],
                     'save_output': ['4736', 0]}},
 '4204': {'class_type': 'GetNode', 'inputs': {'widget_0': 'initial_frames_count'}},
 '4199': {'class_type': 'GetImageSizeAndCount', 'inputs': {'image': ['4184', 1]}},
 '4184': {'class_type': 'VRAM_Debug',
          'inputs': {'widget_0': True, 'widget_1': True, 'widget_2': False, 'image_pass': ['1318', 0]}},
 '1716': {'class_type': 'SetNode', 'inputs': {'widget_0': 'initial_frames', 'IMAGE': ['4199', 0]}},
 '4203': {'class_type': 'SetNode', 'inputs': {'widget_0': 'initial_frames_count', 'INT': ['4199', 3]}},
 '4995': {'class_type': 'SetNode', 'inputs': {'widget_0': 'sigmas', 'SIGMAS': ['2187', 0]}},
 '2196': {'class_type': 'SetNode', 'inputs': {'widget_0': 'sampler', 'SAMPLER': ['2180', 0]}},
 '2180': {'class_type': 'KSamplerSelect', 'inputs': {'widget_0': 'euler_ancestral_cfg_pp'}},
 '2187': {'class_type': 'ManualSigmas',
          'inputs': {'widget_0': '1.0, 0.99375, 0.9875, 0.98125, 0.975, 0.909375, 0.725, 0.421875, 0.0'}},
 '4727': {'class_type': 'GetNode', 'inputs': {'widget_0': 'fps'}},
 '4121': {'class_type': 'SetNode', 'inputs': {'widget_0': 'foldername', 'STRING': ['4735', 0]}},
 '4735': {'class_type': 'StringConcatenate',
          'inputs': {'widget_0': 'MusicVideo', 'widget_1': 'MusicVideo', 'widget_2': '\\', 'string_a': ['4164', 0]}},
 '444': {'class_type': 'LoadImage', 'inputs': {'widget_0': 'download (8).png', 'widget_1': 'image'}},
 '2189': {'class_type': 'ResizeImagesByLongerEdge', 'inputs': {'widget_0': 1536, 'images': ['445', 0]}},
 '1634': {'class_type': 'SetNode', 'inputs': {'widget_0': 'height_downscaled', 'INT': ['1631', 1]}},
 '1633': {'class_type': 'SetNode', 'inputs': {'widget_0': 'width_downscaled', 'INT': ['1631', 0]}},
 '445': {'class_type': 'ImageResizeKJv2',
         'inputs': {'widget_0': 960,
                    'widget_1': 544,
                    'widget_2': 'lanczos',
                    'widget_3': 'crop',
                    'widget_4': '0, 0, 0',
                    'widget_5': 'center',
                    'widget_6': 2,
                    'widget_7': 'cpu',
                    'image': ['444', 0],
                    'width': ['1628', 0],
                    'height': ['1629', 0]}},
 '2284': {'class_type': 'PrimitiveInt', 'inputs': {'widget_0': 5, 'widget_1': 'fixed'}},
 '5065': {'class_type': 'GetNode', 'inputs': {'widget_0': 'foldername'}},
 '5066': {'class_type': 'GetNode', 'inputs': {'widget_0': 'fps'}},
 '5067': {'class_type': 'PrimitiveBoolean', 'inputs': {'widget_0': True}},
 '5070': {'class_type': 'GetNode', 'inputs': {'widget_0': 'initial_frames_count'}},
 '5068': {'class_type': 'PrimitiveStringMultiline',
          'inputs': {'widget_0': 'Make this image come alive with fluid motion. Cinematic music video shot of a red '
                                 'haired woman. \n'
                                 '\n'
                                 'She sings with expressive motion and gesticulation. \n'
                                 'The song she is singing is a sweet slow melancolic melody. Her lips moves in perfect '
                                 'lip-sync to the attached audio.  \n'
                                 '\n'
                                 'She is sitting down at the stage at an abandoned teather.  The camera slowly orbits '
                                 'around the woman, the woman is always looking at the viewer.\n'
                                 '\n'
                                 'She sings the lyrics: "Now rise from weights, unchained and free.\n'
                                 'Like open doors for you and me.\n'
                                 'And every node connects the light. To hands that build without a figh.  No locked '
                                 'gates, just open skies.Where anyone can close their eyes…".\n'
                                 '\n'
                                 '\n'
                                 'Cinematic, volumetric lights, shadow play.\n'
                                 '\n'
                                 'IMPORTANT: The woman is singing, and her lips are moving with lip-sync to the lyrics '
                                 'of the song.'}},
 '5072': {'class_type': 'PrimitiveInt', 'inputs': {'widget_0': 5, 'widget_1': 'fixed'}},
 '5074': {'class_type': 'LoadImage', 'inputs': {'widget_0': 'download (6).png', 'widget_1': 'image'}},
 '4750': {'class_type': 'LoadImage', 'inputs': {'widget_0': 'download (1).png', 'widget_1': 'image'}},
 '5064': {'class_type': 'SetNode', 'inputs': {'widget_0': 'window_sec_03', 'FLOAT': ['5071', 0]}},
 '5140': {'class_type': 'GetNode', 'inputs': {'widget_0': 'foldername'}},
 '5141': {'class_type': 'GetNode', 'inputs': {'widget_0': 'fps'}},
 '5142': {'class_type': 'PrimitiveBoolean', 'inputs': {'widget_0': True}},
 '5145': {'class_type': 'GetNode', 'inputs': {'widget_0': 'initial_frames_count'}},
 '5147': {'class_type': 'PrimitiveInt', 'inputs': {'widget_0': 5, 'widget_1': 'fixed'}},
 '5139': {'class_type': 'SetNode', 'inputs': {'widget_0': 'window_sec_04', 'FLOAT': ['5146', 0]}},
 '1997': {'class_type': 'PrimitiveFloat', 'inputs': {'widget_0': 8}},
 '5143': {'class_type': 'PrimitiveStringMultiline',
          'inputs': {'widget_0': 'Make this image come alive with fluid motion. Cinematic music video shot of a red '
                                 'haired woman. \n'
                                 '\n'
                                 'She sings with expressive motion and gesticulation. \n'
                                 'The song she is singing is a sweet slow melancolic melody. Her lips moves in perfect '
                                 'lip-sync to the attached audio.  \n'
                                 '\n'
                                 'She is sitting down at a piece of drift-wood at the beach, at dusk. Soft light from '
                                 'a cloudy sky. \n'
                                 '\n'
                                 '\n'
                                 'She sings the lyrics: " … and dream. Oh, AceStep XL, you paint my dreams. ComfyUI, '
                                 'you stitch the seams. Of every film, each trembling tone. Where lonely sparks now '
                                 'feel at home".\n'
                                 '\n'
                                 'She sings for a bit before she stands up and walks towards the viewer. \n'
                                 '\n'
                                 'The camera slowly pulls in closer to the woman singing. \n'
                                 '\n'
                                 '\n'
                                 'Cinematic, volumetric lights, shadow play.\n'
                                 '\n'
                                 'IMPORTANT: The woman is singing, and her lips are moving with lip-sync to the lyrics '
                                 'of the song.'}},
 '5149': {'class_type': 'LoadImage', 'inputs': {'widget_0': 'download (2).png', 'widget_1': 'image'}},
 '5215': {'class_type': 'GetNode', 'inputs': {'widget_0': 'foldername'}},
 '5216': {'class_type': 'GetNode', 'inputs': {'widget_0': 'fps'}},
 '5217': {'class_type': 'PrimitiveBoolean', 'inputs': {'widget_0': True}},
 '5220': {'class_type': 'GetNode', 'inputs': {'widget_0': 'initial_frames_count'}},
 '5222': {'class_type': 'PrimitiveInt', 'inputs': {'widget_0': 5, 'widget_1': 'fixed'}},
 '5224': {'class_type': 'LoadImage', 'inputs': {'widget_0': 'download (12).png', 'widget_1': 'image'}},
 '5214': {'class_type': 'SetNode', 'inputs': {'widget_0': 'window_sec_05', 'FLOAT': ['5221', 0]}},
 '5221': {'class_type': 'PrimitiveFloat', 'inputs': {'widget_0': 8}},
 '5146': {'class_type': 'PrimitiveFloat', 'inputs': {'widget_0': 8}},
 '5071': {'class_type': 'PrimitiveFloat', 'inputs': {'widget_0': 8}},
 '5069': {'class_type': 'VHS_VideoCombine',
          'inputs': {'images': ['5073', 1],
                     'audio': ['5073', 2],
                     'frame_rate': ['5066', 0],
                     'filename_prefix': ['5065', 0],
                     'save_output': ['5067', 0]}},
 '5218': {'class_type': 'PrimitiveStringMultiline',
          'inputs': {'widget_0': 'Make this image come alive with fluid motion. Cinematic music video shot of a red '
                                 'haired woman. \n'
                                 '\n'
                                 'She sings with expressive motion and gesticulation. \n'
                                 'The song she is singing is a sweet slow melancolic melody. Her lips moves in perfect '
                                 'lip-sync to the attached audio.  \n'
                                 '\n'
                                 'She is standing on a rooftop balcony with the city behind her, at night. Camera '
                                 'slowly orbits around her, with her always looking towards the viewer as she sings. \n'
                                 '\n'
                                 'She sings the lyrics: "Thank you, Kijai, for the quiet grace. That smoothed the path '
                                 'through digital space. We dream in code, we dream in blue. And every open door leads '
                                 'through.......". \n'
                                 '\n'
                                 'The camera slowly pulls in closer to the woman singing. \n'
                                 '\n'
                                 '\n'
                                 'Cinematic, volumetric lights, shadow play.\n'
                                 '\n'
                                 'IMPORTANT: The woman is singing, and her lips are moving with lip-sync to the lyrics '
                                 'of the song.'}},
 '5144': {'class_type': 'VHS_VideoCombine',
          'inputs': {'images': ['5148', 1],
                     'audio': ['5148', 2],
                     'frame_rate': ['5141', 0],
                     'filename_prefix': ['5140', 0],
                     'save_output': ['5142', 0]}},
 '5219': {'class_type': 'VHS_VideoCombine',
          'inputs': {'images': ['5223', 1],
                     'audio': ['5223', 2],
                     'frame_rate': ['5216', 0],
                     'filename_prefix': ['5215', 0],
                     'save_output': ['5217', 0]}},
 '5073': {'class_type': '17238add-9973-482f-8fa3-248d4ed29886',
          'inputs': {'noise_seed': ['5072', 0],
                     '_1': ['5068', 0],
                     '_2': ['5071', 0],
                     '_4': ['2329', 0],
                     'images': ['5074', 0]}},
 '2329': {'class_type': 'c4106aee-ad7a-4925-972b-6f5b3d34db6e',
          'inputs': {'noise_seed': ['2284', 0],
                     '_1': ['1805', 0],
                     '_2': ['1997', 0],
                     '_4': ['4204', 0],
                     'images': ['4750', 0]}},
 '5148': {'class_type': 'a3fb563d-4711-4225-9210-fbe61b1bd79d',
          'inputs': {'noise_seed': ['5147', 0],
                     '_1': ['5143', 0],
                     '_2': ['5146', 0],
                     '_4': ['5073', 0],
                     'images': ['5149', 0]}},
 '5223': {'class_type': '4acc9924-c0bd-470a-b000-46c75e61d004',
          'inputs': {'noise_seed': ['5222', 0],
                     '_1': ['5218', 0],
                     '_2': ['5221', 0],
                     '_4': ['5148', 0],
                     'images': ['5224', 0]}},
 '4733': {'class_type': 'SetNode', 'inputs': {'widget_0': 'final_frames', 'INT': ['5223', 0]}},
 '4164': {'class_type': 'StringConcatenate',
          'inputs': {'widget_0': 'MusicVideo', 'widget_1': '', 'widget_2': '\\', 'string_b': ['4119', 0]}},
 '5225': {'class_type': 'SetNode', 'inputs': {'widget_0': 'temp_name', 'STRING': ['4119', 0]}},
 '4119': {'class_type': 'PrimitiveString', 'inputs': {'widget_0': 'mynewvideo'}},
 '4743': {'class_type': 'StringConcatenate',
          'inputs': {'widget_0': 'output\\MusicVideo', 'widget_1': '', 'widget_2': '\\', 'string_b': ['4724', 0]}},
 '4724': {'class_type': 'GetNode', 'inputs': {'widget_0': 'temp_name'}},
 '5227': {'class_type': 'GetNode', 'inputs': {'widget_0': 'audio_original'}},
 '4725': {'class_type': 'VHS_VideoCombine',
          'inputs': {'images': ['4708', 0], 'audio': ['5227', 0], 'frame_rate': ['4727', 0]}},
 '5228': {'class_type': 'SimpleCalculatorKJ', 'inputs': {'widget_0': 'a + 100', 'variables.a': ['5226', 0]}},
 '5226': {'class_type': 'GetNode', 'inputs': {'widget_0': 'final_frames'}},
 '4708': {'class_type': 'LoadVideosFromFolder',
          'inputs': {'widget_0': 'output\\MusicVideo',
                     'widget_1': 0,
                     'widget_2': 0,
                     'widget_3': 0,
                     'widget_4': 0,
                     'widget_5': 0,
                     'widget_6': 1,
                     'widget_7': 'batch',
                     'widget_8': 4,
                     'widget_9': False,
                     'video': ['4743', 0],
                     'frame_load_cap': ['5228', 1]}}}

READY_METADATA = {'model_assets': [],
 'unbound_inputs': {'seed': 4435},
 'ready_template': 'video/ltx2_3_runexx_music_video_low_ram',
 'workflow_template': 'ltx2_3_runexx_music_video_low_ram',
 'capability': 'music_video_multiscene',
 'source_role': 'materialized_ready_python_template',
 'source_workflow': 'workflow_corpus/custom_nodes/ltxvideo/runexx/LTX-2.3_Music_Video_Creator_Low_RAM.json',
 'coverage_tier': 'supplemental',
 'approach': 'low-RAM multi-scene music video',
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

READY_REQUIREMENTS = {'models': [], 'custom_nodes': ['ComfyUI-GGUF', 'ComfyUI-KJNodes', 'ComfyUI-LTXVideo', 'ComfyUI-VideoHelperSuite']}


def build():
    return build_api_ready_workflow(
        API_WORKFLOW,
        source_path=__file__,
        workflow_id=READY_METADATA.get("ready_template", "video/ltx2_3_runexx_music_video_low_ram"),
        ready_metadata=READY_METADATA,
        requirements=READY_REQUIREMENTS,
    )
