from __future__ import annotations

from vibecomfy.registry.ready_template import build_api_ready_workflow


API_WORKFLOW = {'1555': {'class_type': 'SetNode', 'inputs': {'widget_0': 'upscale_model', 'LATENT_UPSCALE_MODEL': ['1561', 0]}},
 '1556': {'class_type': 'SetNode', 'inputs': {'widget_0': 'vae_audio', 'VAE': ['1567', 0]}},
 '1557': {'class_type': 'SetNode', 'inputs': {'widget_0': 'vae', 'VAE': ['1559', 0]}},
 '1558': {'class_type': 'SetNode', 'inputs': {'widget_0': 'clip', 'CLIP': ['1562', 0]}},
 '1559': {'class_type': 'VAELoader', 'inputs': {'widget_0': 'LTX23_video_vae_bf16.safetensors'}},
 '1562': {'class_type': 'DualCLIPLoader',
          'inputs': {'widget_0': 'gemma_3_12B_it_fp4_mixed.safetensors',
                     'widget_1': 'ltx-2.3_text_projection_bf16.safetensors',
                     'widget_2': 'ltxv',
                     'widget_3': 'default'}},
 '1567': {'class_type': 'VAELoaderKJ',
          'inputs': {'widget_0': 'LTX23_audio_vae_bf16.safetensors', 'widget_1': 'main_device', 'widget_2': 'bf16'}},
 '1568': {'class_type': 'SetNode', 'inputs': {'widget_0': 'vae_tiny', 'VAE': ['1569', 0]}},
 '1569': {'class_type': 'VAELoader', 'inputs': {'widget_0': 'taeltx2_3.safetensors'}},
 '1572': {'class_type': 'MarkdownNote',
          'inputs': {'widget_0': 'Download models from here:\n'
                                 '\n'
                                 '\n'
                                 'https://huggingface.co/Kijai/LTX2.3_comfy\n'
                                 '\n'
                                 'Text encoder : https://huggingface.co/Comfy-Org/ltx-2'}},
 '1575': {'class_type': 'SetNode', 'inputs': {'widget_0': 'height', 'INT': ['1591', 0]}},
 '1576': {'class_type': 'SetNode', 'inputs': {'widget_0': 'width', 'INT': ['1606', 0]}},
 '1577': {'class_type': 'SetNode', 'inputs': {'widget_0': 'fps', 'FLOAT': ['1586', 0]}},
 '1617': {'class_type': 'SetNode', 'inputs': {'widget_0': 'model_with_lora', 'MODEL': ['1627', 0]}},
 '1622': {'class_type': 'GetNode', 'inputs': {'widget_0': 'clip'}},
 '413': {'class_type': 'GetNode', 'inputs': {'widget_0': 'vae'}},
 '1635': {'class_type': 'GetNode', 'inputs': {'widget_0': 'frames'}},
 '1621': {'class_type': 'CLIPTextEncode',
          'inputs': {'widget_0': '= Enhanced Prompt = \n', 'clip': ['1622', 0], 'text': ['1926', 0]}},
 '1570': {'class_type': 'UNETLoader',
          'inputs': {'widget_0': 'ltx-2.3-22b-distilled_transformer_only_fp8_scaled.safetensors',
                     'widget_1': 'default'}},
 '1560': {'class_type': 'LoraLoaderModelOnly',
          'inputs': {'widget_0': 'LTX\\LTX-2\\ltx-2.3-22b-distilled-lora-384.safetensors',
                     'widget_1': 0.6,
                     'model': ['1570', 0]}},
 '268': {'class_type': 'PathchSageAttentionKJ',
         'inputs': {'widget_0': 'auto', 'widget_1': False, 'model': ['1560', 0]}},
 '1634': {'class_type': 'SetNode', 'inputs': {'widget_0': 'height_downscaled', 'INT': ['1631', 1]}},
 '1629': {'class_type': 'GetNode', 'inputs': {'widget_0': 'height'}},
 '1628': {'class_type': 'GetNode', 'inputs': {'widget_0': 'width'}},
 '1561': {'class_type': 'LatentUpscaleModelLoader',
          'inputs': {'widget_0': 'ltx-2.3-spatial-upscaler-x2-1.1.safetensors'}},
 '646': {'class_type': 'SetNode', 'inputs': {'widget_0': 'negative', 'CONDITIONING': ['164', 1]}},
 '645': {'class_type': 'SetNode', 'inputs': {'widget_0': 'positive', 'CONDITIONING': ['164', 0]}},
 '1633': {'class_type': 'SetNode', 'inputs': {'widget_0': 'width_downscaled', 'INT': ['1631', 0]}},
 '1808': {'class_type': 'GetNode', 'inputs': {'widget_0': 'width_downscaled'}},
 '1807': {'class_type': 'GetNode', 'inputs': {'widget_0': 'height_downscaled'}},
 '1809': {'class_type': 'GetNode', 'inputs': {'widget_0': 'ref_image'}},
 '1814': {'class_type': 'GetNode', 'inputs': {'widget_0': 'vae'}},
 '1815': {'class_type': 'GetNode', 'inputs': {'widget_0': 'vae_audio'}},
 '1816': {'class_type': 'GetNode', 'inputs': {'widget_0': 'vae'}},
 '1817': {'class_type': 'GetNode', 'inputs': {'widget_0': 'upscale_model'}},
 '1819': {'class_type': 'LTXVConcatAVLatent', 'inputs': {'video_latent': ['1825', 0], 'audio_latent': ['1827', 1]}},
 '1820': {'class_type': 'GetNode', 'inputs': {'widget_0': 'negative'}},
 '1821': {'class_type': 'GetNode', 'inputs': {'widget_0': 'positive'}},
 '1823': {'class_type': 'GetNode', 'inputs': {'widget_0': 't2v_mode'}},
 '1824': {'class_type': 'GetNode', 'inputs': {'widget_0': 'ref_image'}},
 '1827': {'class_type': 'LTXVSeparateAVLatent', 'inputs': {'av_latent': ['1845', 0]}},
 '1828': {'class_type': 'GetNode', 'inputs': {'widget_0': 'model'}},
 '1829': {'class_type': 'GetNode', 'inputs': {'widget_0': 'negative'}},
 '1830': {'class_type': 'GetNode', 'inputs': {'widget_0': 'positive'}},
 '1831': {'class_type': 'GetNode', 'inputs': {'widget_0': 'model_with_lora'}},
 '1833': {'class_type': 'GetNode', 'inputs': {'widget_0': 'vae_tiny'}},
 '1834': {'class_type': 'GetNode', 'inputs': {'widget_0': 'model_with_lora'}},
 '1839': {'class_type': 'LTXVSeparateAVLatent', 'inputs': {'av_latent': ['1838', 0]}},
 '1841': {'class_type': 'GetNode', 'inputs': {'widget_0': 'model'}},
 '1843': {'class_type': 'GetNode', 'inputs': {'widget_0': 'negative'}},
 '1855': {'class_type': 'GetNode', 'inputs': {'widget_0': 'latent'}},
 '1861': {'class_type': 'SetNode', 'inputs': {'widget_0': 't2v_mode', 'BOOLEAN': ['1862', 0]}},
 '1862': {'class_type': 'PrimitiveBoolean', 'inputs': {'widget_0': False}},
 '1586': {'class_type': 'PrimitiveFloat', 'inputs': {'widget_0': 8}},
 '1832': {'class_type': 'RandomNoise', 'inputs': {'widget_0': 420, 'widget_1': 'fixed'}},
 '504': {'class_type': 'LTXVChunkFeedForward', 'inputs': {'widget_0': 2, 'widget_1': 4096, 'model': ['268', 0]}},
 '1523': {'class_type': 'LTX2AttentionTunerPatch',
          'inputs': {'widget_0': '',
                     'widget_1': 1,
                     'widget_2': 1,
                     'widget_3': 1,
                     'widget_4': 1,
                     'widget_5': True,
                     'model': ['504', 0]}},
 '1563': {'class_type': 'MarkdownNote',
          'inputs': {'widget_0': '## LTX-2 Prompting Tips\n'
                                 '1. **Core Actions**: Describe events and actions as they occur over time  \n'
                                 '2. **Audio**: Describe sounds and dialogue needed for the scene  \n'
                                 '3. **Reference Image**: Do not repeat details already present  \n'
                                 '4. **Consistency**: Avoid instructions that do not match the reference image, as '
                                 'this will degrade results'}},
 '1856': {'class_type': 'CFGGuider',
          'inputs': {'widget_0': 2.5, 'model': ['1841', 0], 'positive': ['1830', 0], 'negative': ['1829', 0]}},
 '1887': {'class_type': 'GetNode', 'inputs': {'widget_0': 'height'}},
 '1889': {'class_type': 'GetNode', 'inputs': {'widget_0': 'vae_audio'}},
 '1891': {'class_type': 'SetNode', 'inputs': {'widget_0': 'latent_custom_audio', 'LATENT': ['1892', 0]}},
 '1835': {'class_type': 'GetNode', 'inputs': {'widget_0': 'model'}},
 '650': {'class_type': 'SetNode', 'inputs': {'widget_0': 'ref_image', 'IMAGE': ['445', 0]}},
 '1631': {'class_type': 'GetImageSize', 'inputs': {'image': ['1630', 0]}},
 '1630': {'class_type': 'ResizeImageMaskNode',
          'inputs': {'widget_0': 'scale by multiplier', 'widget_1': 256, 'widget_2': 'area', 'input': ['445', 0]}},
 '1878': {'class_type': 'GetNode', 'inputs': {'widget_0': 'model'}},
 '1911': {'class_type': 'BasicScheduler',
          'inputs': {'steps': 1, 'widget_0': 1, 'widget_1': 4, 'widget_2': 1, 'model': ['1912', 0]}},
 '1818': {'class_type': 'VAEDecodeTiled',
          'inputs': {'widget_0': 512,
                     'widget_1': 64,
                     'widget_2': 4096,
                     'widget_3': 8,
                     'samples': ['1839', 0],
                     'vae': ['1814', 0]}},
 '1636': {'class_type': 'GetNode', 'inputs': {'widget_0': 'fps'}},
 '1898': {'class_type': 'GetNode', 'inputs': {'widget_0': 'fps'}},
 '1897': {'class_type': 'SimpleCalculatorKJ',
          'inputs': {'widget_0': '((round((a * b -1) / 8)) * 8) + 1 ',
                     'variables.a': ['1583', 0],
                     'variables.b': ['1898', 0]}},
 '1918': {'class_type': 'SetNode', 'inputs': {'widget_0': 'frames_seconds', 'INT': ['1897', 1]}},
 '1583': {'class_type': 'INTConstant', 'inputs': {'widget_0': 10}},
 '344': {'class_type': 'EmptyLTXVLatentVideo',
         'inputs': {'width': ['1808', 0],
                    'height': ['1807', 0],
                    'length': ['1635', 0],
                    'widget_0': 256,
                    'widget_1': 256,
                    'widget_2': 5,
                    'widget_3': 1}},
 '1860': {'class_type': 'SetNode', 'inputs': {'widget_0': 'latent', 'LATENT': ['350', 0]}},
 '1894': {'class_type': 'GetNode', 'inputs': {'widget_0': 'latent_custom_audio'}},
 '350': {'class_type': 'LTXVConcatAVLatent', 'inputs': {'video_latent': ['1934', 0], 'audio_latent': ['1894', 0]}},
 '1578': {'class_type': 'SetNode', 'inputs': {'widget_0': 'frames', '*': ['1920', 0]}},
 '1892': {'class_type': 'SetLatentNoiseMask', 'inputs': {'samples': ['1893', 0], 'mask': ['1890', 0]}},
 '1888': {'class_type': 'GetNode', 'inputs': {'widget_0': 'width'}},
 '1890': {'class_type': 'SolidMask',
          'inputs': {'widget_0': 0, 'widget_1': 512, 'widget_2': 512, 'width': ['1888', 0], 'height': ['1887', 0]}},
 '1822': {'class_type': 'GetNode', 'inputs': {'widget_0': 'fps'}},
 '1852': {'class_type': 'KSamplerSelect', 'inputs': {'widget_0': 'euler_cfg_pp'}},
 '1912': {'class_type': 'ModelSamplingSD3', 'inputs': {'widget_0': 13, 'model': ['1835', 0]}},
 '1851': {'class_type': 'ManualSigmas', 'inputs': {'widget_0': '0.85, 0.7250, 0.4219, 0.0'}},
 '1836': {'class_type': 'CFGGuider',
          'inputs': {'widget_0': 2.5, 'model': ['1835', 0], 'positive': ['1821', 0], 'negative': ['1820', 0]}},
 '1844': {'class_type': 'LTX2_NAG',
          'inputs': {'widget_0': 11,
                     'widget_1': 0.25,
                     'widget_2': 2.5,
                     'widget_3': True,
                     'model': ['1858', 0],
                     'nag_cond_video': ['1843', 0],
                     'nag_cond_audio': ['1843', 0]}},
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
 '1627': {'class_type': 'Power Lora Loader (rgthree)', 'inputs': {'widget_4': '', 'model': ['1523', 0]}},
 '1626': {'class_type': 'CLIPTextEncode',
          'inputs': {'widget_0': 'text, subtitles, logo, still image, still video, no motion, static, frozen, blurry, '
                                 'low quality, distorted, bad anatomy, oversaturated, pixelated, low resolution, '
                                 'grainy, compression artifacts, jpeg artifacts, glitches, watermark, signature, '
                                 'copyright,  distortedsound, saturated sound, loud sound , deformed facial features, '
                                 'asymmetrical face, missing facial features, extra limbs, disfigured hands, blurry '
                                 'teeth, disfigured teeth',
                     'clip': ['1622', 0]}},
 '1842': {'class_type': 'RandomNoise', 'inputs': {'widget_0': 42, 'widget_1': 'fixed'}},
 '1853': {'class_type': 'KSamplerSelect', 'inputs': {'widget_0': 'euler_ancestral_cfg_pp'}},
 '1847': {'class_type': 'LTXVAudioVAEDecode', 'inputs': {'samples': ['1839', 1], 'audio_vae': ['1815', 0]}},
 '1915': {'class_type': 'VRAM_Debug',
          'inputs': {'widget_0': True, 'widget_1': True, 'widget_2': True, 'image_pass': ['1818', 0]}},
 '1837': {'class_type': 'VHS_VideoCombine',
          'inputs': {'images': ['1915', 1], 'audio': ['1847', 0], 'frame_rate': ['1822', 0]}},
 '1608': {'class_type': 'MarkdownNote',
          'inputs': {'widget_0': 'Use a reference audio instead of LTX own audio, and LTX video will lip-sync to the '
                                 'audio you provide. For best possible results you should prompt that the subject is '
                                 'talking.  And if you transcribe what is said in your audio input, results might be '
                                 'even better \n'
                                 '\n'
                                 'Mel-band RoFormer is optional for extracting a clean vocal only audio for the '
                                 'sampler\n'
                                 '\n'
                                 'https://huggingface.co/Kijai/MelBandRoFormer_comfy/tree/main\n'
                                 '\n'
                                 'folder: models\\diffusion_models\n'}},
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
 '1566': {'class_type': 'MarkdownNote',
          'inputs': {'widget_0': 'This automagically enhances your prompt using the already loaded Gemma model. But it '
                                 'can be a bit sensitive to having correct Gemma if using GGUF models. Alternatively '
                                 'you can bypass/disable  this feature '}},
 '1564': {'class_type': 'MarkdownNote',
          'inputs': {'widget_0': 'If using some user made LTX-2 loras they sometimes are not trained on audio, so it '
                                 'will produce very noisy audio outputs. Try use KJNodes LTX-2 Lora Loader Advanced in '
                                 'such cases, and set the non video strenght to zero\n'}},
 '1565': {'class_type': 'MarkdownNote', 'inputs': {'widget_0': 'taeltx2_3.safetensors'}},
 '1573': {'class_type': 'DualCLIPLoaderGGUF',
          'inputs': {'widget_0': 'gemma-3-12b-it-Q2_K.gguf',
                     'widget_1': 'ltx-2.3_text_projection_bf16.safetensors',
                     'widget_2': 'sdxl'}},
 '1571': {'class_type': 'UnetLoaderGGUF',
          'inputs': {'widget_0': 'LTXvideo\\LTX-2\\quantstack\\LTX-2.3-distilled-Q4_K_S.gguf'}},
 '1845': {'class_type': 'SamplerCustomAdvanced',
          'inputs': {'noise': ['1842', 0],
                     'guider': ['1856', 0],
                     'sampler': ['1853', 0],
                     'sigmas': ['1857', 0],
                     'latent_image': ['1855', 0]}},
 '1838': {'class_type': 'SamplerCustomAdvanced',
          'inputs': {'noise': ['1832', 0],
                     'guider': ['1836', 0],
                     'sampler': ['1852', 0],
                     'sigmas': ['1851', 0],
                     'latent_image': ['1819', 0]}},
 '1930': {'class_type': 'SetNode', 'inputs': {'widget_0': 'enhance_prompt', 'BOOLEAN': ['1929', 0]}},
 '1926': {'class_type': 'a8d7fd9f-52aa-447a-9766-53cb91c0ef18',
          'inputs': {'clip': ['1619', 0], 'image': ['1630', 0], '_1': ['1624', 0]}},
 '1619': {'class_type': 'GetNode', 'inputs': {'widget_0': 'clip'}},
 '1931': {'class_type': 'GetNode', 'inputs': {'widget_0': 'enhance_prompt'}},
 '1929': {'class_type': 'PrimitiveBoolean', 'inputs': {'widget_0': True}},
 '1825': {'class_type': 'LTXVImgToVideoInplace',
          'inputs': {'widget_0': 1,
                     'widget_1': False,
                     'vae': ['1816', 0],
                     'image': ['1824', 0],
                     'latent': ['1827', 0],
                     'bypass': ['1823', 0]}},
 '1935': {'class_type': 'GetNode', 'inputs': {'widget_0': 't2v_mode'}},
 '1934': {'class_type': 'LTXVImgToVideoInplace',
          'inputs': {'widget_0': 0.7,
                     'widget_1': False,
                     'vae': ['413', 0],
                     'image': ['446', 0],
                     'latent': ['344', 0],
                     'bypass': ['1935', 0]}},
 '164': {'class_type': 'LTXVConditioning',
         'inputs': {'widget_0': 8, 'positive': ['1621', 0], 'negative': ['1626', 0], 'frame_rate': ['1636', 0]}},
 '446': {'class_type': 'LTXVPreprocess', 'inputs': {'widget_0': 18, 'image': ['1809', 0]}},
 '1840': {'class_type': 'SetNode', 'inputs': {'widget_0': 'model', 'MODEL': ['1844', 0]}},
 '1876': {'class_type': 'ModelSamplingSD3', 'inputs': {'widget_0': 13, 'model': ['1878', 0]}},
 '1877': {'class_type': 'BasicScheduler',
          'inputs': {'steps': 1, 'widget_0': 1, 'widget_1': 8, 'widget_2': 1, 'model': ['1876', 0]}},
 '1857': {'class_type': 'ManualSigmas',
          'inputs': {'widget_0': '1.0, 0.99375, 0.9875, 0.98125, 0.975, 0.909375, 0.725, 0.421875, 0.0'}},
 '1858': {'class_type': 'LTX2SamplingPreviewOverride',
          'inputs': {'widget_0': 8, 'model': ['1834', 0], 'vae': ['1833', 0]}},
 '1624': {'class_type': 'PrimitiveStringMultiline',
          'inputs': {'widget_0': 'A video from a TV broadcast with a male and a female news achor. They both stay in '
                                 'frame all the time.\n'
                                 '\n'
                                 'The dialog from the male and female is as follows:\n'
                                 '\n'
                                 'Spaker_1 is the woman, and Speaker_2 is the man.\n'
                                 '\n'
                                 '[speaker_1][confused]: This is awkward! I guess the prompter ran out of ideas, and '
                                 'put us in this odd situation.\n'
                                 '[speaker_2][embarrassed] : But hey,  just because we are here, in a new video, '
                                 "doesn't mean our voices change. \n"
                                 '[speaker_1][excited]: Aber ich möchte mit dir schlafen.\n'
                                 '[speaker_2][happy]: I still have no idea what she said! Might be for the best '
                                 '[laughing]\n'
                                 '\n'
                                 'The dialog with perfect lip-sync to the audio\n'
                                 '\n'
                                 '\n'
                                 'They both smile at the end.\n'
                                 '\n'
                                 '\n'}},
 '1936': {'class_type': 'MelBandRoFormerSampler', 'inputs': {'model': ['1937', 0], 'audio': ['1939', 0]}},
 '1937': {'class_type': 'MelBandRoFormerModelLoader',
          'inputs': {'widget_0': 'MelBandRoformer\\MelBandRoformer_fp16.safetensors'}},
 '1938': {'class_type': 'PrimitiveStringMultiline', 'inputs': {'widget_0': ''}},
 '1939': {'class_type': 'TrimAudioDuration', 'inputs': {'widget_0': 0, 'widget_1': 15, 'audio': ['1941', 0]}},
 '1940': {'class_type': 'MarkdownNote',
          'inputs': {'widget_0': 'Refference text (transcribe what is said in your refference audio) \n'
                                 '\n'
                                 '(optional - turn off x_vector_only to use)'}},
 '1942': {'class_type': 'PrimitiveStringMultiline',
          'inputs': {'widget_0': 'So what if you just want to prompt. Text to video works fine as well. Go generate '
                                 'some while I enjoy my coffee. '}},
 '1944': {'class_type': 'AILab_Qwen3TTSVoiceClone',
          'inputs': {'widget_0': 'Hello, this is a cloned voice.',
                     'widget_1': '1.7B',
                     'widget_2': 'Auto',
                     'widget_3': '',
                     'widget_4': True,
                     'widget_5': 986337553816914,
                     'widget_6': 116899311982882,
                     'widget_7': 'randomize',
                     'reference_audio': ['1936', 0],
                     'target_text': ['1942', 0],
                     'reference_text': ['1938', 0]}},
 '1943': {'class_type': 'PreviewAudio', 'inputs': {'audio': ['1904', 0]}},
 '1904': {'class_type': 'AudioEnhancementNode',
          'inputs': {'widget_0': 'manual',
                     'widget_1': 0.7,
                     'widget_2': 0.6,
                     'widget_3': 1.3,
                     'widget_4': 1.2,
                     'widget_5': 1,
                     'widget_6': 1,
                     'widget_7': 0.5,
                     'widget_8': 'keep_original',
                     'widget_9': False,
                     'widget_10': 5,
                     'widget_11': 0,
                     'widget_12': 0,
                     'widget_13': 'full_track',
                     'audio': ['1916', 0]}},
 '1916': {'class_type': 'AudioNormalizeLUFS',
          'inputs': {'widget_0': -20, 'widget_1': 0, 'widget_2': 0, 'widget_3': 'full_track', 'audio': ['1944', 0]}},
 '1758': {'class_type': 'SetNode', 'inputs': {'widget_0': 'audio_tts', 'AUDIO': ['1904', 0]}},
 '1865': {'class_type': 'Reroute', 'inputs': {}},
 '1784': {'class_type': 'GetNode', 'inputs': {'widget_0': 'audio_tts'}},
 '1893': {'class_type': 'LTXVAudioVAEEncode', 'inputs': {'audio': ['1865', 0], 'audio_vae': ['1889', 0]}},
 '1920': {'class_type': '63e8c999-0a69-4f62-af3f-8b77f0095971', 'inputs': {'audio': ['1865', 0]}},
 '1941': {'class_type': 'LoadAudio', 'inputs': {'widget_0': 'd1b26d5a32db420183fa17af9c699278.mp3'}},
 '444': {'class_type': 'LoadImage', 'inputs': {'widget_0': '17745317855d08.png', 'widget_1': 'image'}},
 '1591': {'class_type': 'INTConstant', 'inputs': {'widget_0': 960}},
 '1606': {'class_type': 'INTConstant', 'inputs': {'widget_0': 544}}}

READY_METADATA = {'model_assets': [],
 'unbound_inputs': {'seed': 4872},
 'ready_template': 'video/ltx2_3_runexx_talking_avatar_qwen_tts',
 'workflow_template': 'ltx2_3_runexx_talking_avatar_qwen_tts',
 'capability': 'tts_talking_avatar',
 'source_role': 'materialized_ready_python_template',
 'source_workflow': 'workflow_corpus/custom_nodes/ltxvideo/runexx/LTX-2.3_Talking_Avatar_Qwen_TTS.json',
 'coverage_tier': 'supplemental',
 'approach': 'Qwen TTS talking avatar',
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
 'custom_nodes': ['ComfyUI-GGUF', 'ComfyUI-KJNodes', 'ComfyUI-LTXVideo', 'ComfyUI-QwenTTS', 'ComfyUI-VideoHelperSuite']}


def build():
    return build_api_ready_workflow(
        API_WORKFLOW,
        source_path=__file__,
        workflow_id=READY_METADATA.get("ready_template", "video/ltx2_3_runexx_talking_avatar_qwen_tts"),
        ready_metadata=READY_METADATA,
        requirements=READY_REQUIREMENTS,
    )
