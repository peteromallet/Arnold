from __future__ import annotations

from vibecomfy.registry.ready_template import build_api_ready_workflow


API_WORKFLOW = {'218': {'class_type': 'GetNode', 'inputs': {'widget_0': 'vae'}},
 '220': {'class_type': 'GetNode', 'inputs': {'widget_0': 'vae'}},
 '238': {'class_type': 'SetNode', 'inputs': {'widget_0': 'latent', 'LATENT': ['109', 0]}},
 '237': {'class_type': 'GetNode', 'inputs': {'widget_0': 'height_downsized'}},
 '236': {'class_type': 'GetNode', 'inputs': {'widget_0': 'width_downsized'}},
 '205': {'class_type': 'GetNode', 'inputs': {'widget_0': 'frames'}},
 '211': {'class_type': 'SetNode', 'inputs': {'widget_0': 'compress_image', 'IMAGE': ['162', 0]}},
 '282': {'class_type': 'SetNode', 'inputs': {'widget_0': 'height', 'INT': ['293', 0]}},
 '283': {'class_type': 'SetNode', 'inputs': {'widget_0': 'width', 'INT': ['292', 0]}},
 '284': {'class_type': 'SetNode', 'inputs': {'widget_0': 'fps', 'FLOAT': ['285', 0]}},
 '285': {'class_type': 'PrimitiveFloat', 'inputs': {'widget_0': 8}},
 '286': {'class_type': 'SetNode', 'inputs': {'widget_0': 'frames', 'INT': ['287', 1]}},
 '288': {'class_type': 'SetNode', 'inputs': {'widget_0': 't2v_mode', 'BOOLEAN': ['290', 0]}},
 '221': {'class_type': 'GetNode', 'inputs': {'widget_0': 'vae_audio'}},
 '219': {'class_type': 'GetNode', 'inputs': {'widget_0': 'vae'}},
 '242': {'class_type': 'GetNode', 'inputs': {'widget_0': 'upscale_model'}},
 '127': {'class_type': 'VAEDecodeTiled',
         'inputs': {'widget_0': 512,
                    'widget_1': 64,
                    'widget_2': 4096,
                    'widget_3': 8,
                    'samples': ['125', 0],
                    'vae': ['220', 0]}},
 '117': {'class_type': 'LTXVConcatAVLatent', 'inputs': {'video_latent': ['160', 0], 'audio_latent': ['116', 1]}},
 '229': {'class_type': 'GetNode', 'inputs': {'widget_0': 'negative'}},
 '228': {'class_type': 'GetNode', 'inputs': {'widget_0': 'positive'}},
 '307': {'class_type': 'GetNode', 'inputs': {'widget_0': 'fps'}},
 '309': {'class_type': 'GetNode', 'inputs': {'widget_0': 't2v_mode'}},
 '308': {'class_type': 'GetNode', 'inputs': {'widget_0': 't2v_mode'}},
 '311': {'class_type': 'SimpleCalculatorKJ', 'inputs': {'widget_0': 'a', 'variables.a': ['310', 0]}},
 '310': {'class_type': 'GetNode', 'inputs': {'widget_0': 'fps'}},
 '217': {'class_type': 'GetNode', 'inputs': {'widget_0': 'vae_audio'}},
 '240': {'class_type': 'SetNode', 'inputs': {'widget_0': 'latent_audio', 'LATENT': ['199', 0]}},
 '212': {'class_type': 'GetNode', 'inputs': {'widget_0': 'ref_image'}},
 '160': {'class_type': 'LTXVImgToVideoInplace',
         'inputs': {'widget_0': 1,
                    'widget_1': False,
                    'vae': ['219', 0],
                    'image': ['212', 0],
                    'latent': ['116', 0],
                    'bypass': ['309', 0]}},
 '116': {'class_type': 'LTXVSeparateAVLatent', 'inputs': {'av_latent': ['113', 0]}},
 '292': {'class_type': 'INTConstant', 'inputs': {'widget_0': 1280}},
 '293': {'class_type': 'INTConstant', 'inputs': {'widget_0': 736}},
 '234': {'class_type': 'SetNode', 'inputs': {'widget_0': 'height_downsized', 'INT': ['163', 1]}},
 '164': {'class_type': 'ResizeImageMaskNode',
         'inputs': {'widget_0': 'scale by multiplier', 'widget_1': 256, 'widget_2': 'area', 'input': ['165', 0]}},
 '248': {'class_type': 'SetNode', 'inputs': {'widget_0': 'resize_image', 'IMAGE': ['164', 0]}},
 '233': {'class_type': 'SetNode', 'inputs': {'widget_0': 'width_downsized', 'INT': ['163', 0]}},
 '163': {'class_type': 'GetImageSize', 'inputs': {'image': ['164', 0]}},
 '246': {'class_type': 'ResizeImagesByLongerEdge', 'inputs': {'widget_0': 1536, 'images': ['165', 0]}},
 '209': {'class_type': 'SetNode', 'inputs': {'widget_0': 'ref_image', 'IMAGE': ['246', 0]}},
 '244': {'class_type': 'GetNode', 'inputs': {'widget_0': 'height'}},
 '243': {'class_type': 'GetNode', 'inputs': {'widget_0': 'width'}},
 '188': {'class_type': 'SetNode', 'inputs': {'widget_0': 'upscale_model', 'LATENT_UPSCALE_MODEL': ['189', 0]}},
 '216': {'class_type': 'SetNode', 'inputs': {'widget_0': 'vae_audio', 'VAE': ['196', 0]}},
 '215': {'class_type': 'SetNode', 'inputs': {'widget_0': 'vae', 'VAE': ['184', 0]}},
 '213': {'class_type': 'SetNode', 'inputs': {'widget_0': 'clip', 'CLIP': ['190', 0]}},
 '225': {'class_type': 'GetNode', 'inputs': {'widget_0': 'model'}},
 '231': {'class_type': 'GetNode', 'inputs': {'widget_0': 'negative'}},
 '230': {'class_type': 'GetNode', 'inputs': {'widget_0': 'positive'}},
 '161': {'class_type': 'LTXVImgToVideoInplace',
         'inputs': {'widget_0': 1,
                    'widget_1': False,
                    'vae': ['218', 0],
                    'image': ['162', 0],
                    'latent': ['108', 0],
                    'bypass': ['308', 0]}},
 '199': {'class_type': 'LTXVEmptyLatentAudio',
         'inputs': {'frames_number': ['205', 0],
                    'frame_rate': ['311', 1],
                    'widget_0': 5,
                    'widget_1': 8,
                    'widget_2': 1,
                    'audio_vae': ['217', 0]}},
 '290': {'class_type': 'PrimitiveBoolean', 'inputs': {'widget_0': False}},
 '253': {'class_type': 'MarkdownNote',
         'inputs': {'widget_0': '## LTX-2 Prompting Tips\n'
                                '1. **Core Actions**: Describe events and actions as they occur over time  \n'
                                '2. **Audio**: Describe sounds and dialogue needed for the scene  \n'
                                '3. **Reference Image**: Do not repeat details already present  \n'
                                '4. **Consistency**: Avoid instructions that do not match the reference image, as this '
                                'will degrade results'}},
 '287': {'class_type': 'SimpleCalculatorKJ',
         'inputs': {'widget_0': '1+ 8*(round(a*b)/8)', 'a': ['291', 0], 'b': ['285', 0]}},
 '291': {'class_type': 'INTConstant', 'inputs': {'widget_0': 10}},
 '306': {'class_type': 'GetNode', 'inputs': {'widget_0': 'model_with_lora'}},
 '196': {'class_type': 'VAELoaderKJ',
         'inputs': {'widget_0': 'LTX23_audio_vae_bf16.safetensors', 'widget_1': 'main_device', 'widget_2': 'bf16'}},
 '251': {'class_type': 'MarkdownNote',
         'inputs': {'widget_0': 'Download models from here:\n'
                                '\n'
                                '\n'
                                'https://huggingface.co/Kijai/LTX2.3_comfy\n'
                                '\n'
                                'Text encoder : https://huggingface.co/Comfy-Org/ltx-2'}},
 '114': {'class_type': 'RandomNoise', 'inputs': {'widget_0': 420, 'widget_1': 'fixed'}},
 '331': {'class_type': 'SetNode', 'inputs': {'widget_0': 'vae_tiny', 'VAE': ['330', 0]}},
 '289': {'class_type': 'MarkdownNote',
         'inputs': {'widget_0': 'If low on Ram/Vram, try width height to 832 x 480 or 960 x 544.  If you can, run at '
                                '1280 x 720 or higher.\n'
                                '\n'
                                '\n'
                                'Length in seconds :  try 5, 10 or 20. \n'
                                'fps : 24 or 25 (or 48 or 50 if your pc can run it)'}},
 '326': {'class_type': 'MarkdownNote',
         'inputs': {'widget_0': 'If using some user made LTX-2 loras they sometimes are not trained on audio, so it '
                                'will produce very noisy audio outputs. Try use KJNodes LTX-2 Lora Loader Advanced in '
                                'such cases, and set the non video strenght to zero\n'}},
 '330': {'class_type': 'VAELoader', 'inputs': {'widget_0': 'taeltx2_3.safetensors'}},
 '184': {'class_type': 'VAELoader', 'inputs': {'widget_0': 'LTX23_video_vae_bf16.safetensors'}},
 '189': {'class_type': 'LatentUpscaleModelLoader',
         'inputs': {'widget_0': 'ltx-2.3-spatial-upscaler-x2-1.0.safetensors'}},
 '338': {'class_type': 'GetNode', 'inputs': {'widget_0': 'vae_tiny'}},
 '339': {'class_type': 'GetNode', 'inputs': {'widget_0': 'model_with_lora'}},
 '341': {'class_type': 'GetNode', 'inputs': {'widget_0': 'model'}},
 '103': {'class_type': 'CFGGuider',
         'inputs': {'widget_0': 2.5, 'model': ['341', 0], 'positive': ['228', 0], 'negative': ['229', 0]}},
 '329': {'class_type': 'UNETLoader',
         'inputs': {'widget_0': 'ltx-2.3-22b-distilled_transformer_only_fp8_scaled.safetensors',
                    'widget_1': 'default'}},
 '140': {'class_type': 'VHS_VideoCombine',
         'inputs': {'images': ['127', 0], 'audio': ['378', 0], 'frame_rate': ['307', 0]}},
 '109': {'class_type': 'LTXVConcatAVLatent', 'inputs': {'video_latent': ['161', 0], 'audio_latent': ['376', 0]}},
 '210': {'class_type': 'GetNode', 'inputs': {'widget_0': 'ref_image'}},
 '119': {'class_type': 'SamplerCustomAdvanced',
         'inputs': {'noise': ['114', 0],
                    'guider': ['103', 0],
                    'sampler': ['138', 0],
                    'sigmas': ['380', 0],
                    'latent_image': ['117', 0]}},
 '125': {'class_type': 'LTXVSeparateAVLatent', 'inputs': {'av_latent': ['119', 0]}},
 '340': {'class_type': 'SetNode', 'inputs': {'widget_0': 'model', 'MODEL': ['342', 0]}},
 '344': {'class_type': 'GetNode', 'inputs': {'widget_0': 'model'}},
 '115': {'class_type': 'RandomNoise', 'inputs': {'widget_0': 43, 'widget_1': 'fixed'}},
 '343': {'class_type': 'GetNode', 'inputs': {'widget_0': 'negative'}},
 '342': {'class_type': 'LTX2_NAG',
         'inputs': {'widget_0': 11,
                    'widget_1': 0.25,
                    'widget_2': 2.5,
                    'widget_3': True,
                    'model': ['337', 0],
                    'nag_cond_video': ['343', 0],
                    'nag_cond_audio': ['343', 0]}},
 '322': {'class_type': 'GetNode', 'inputs': {'widget_0': 'fps'}},
 '226': {'class_type': 'SetNode', 'inputs': {'widget_0': 'positive', 'CONDITIONING': ['107', 0]}},
 '227': {'class_type': 'SetNode', 'inputs': {'widget_0': 'negative', 'CONDITIONING': ['107', 1]}},
 '107': {'class_type': 'LTXVConditioning',
         'inputs': {'widget_0': 8, 'positive': ['121', 0], 'negative': ['110', 0], 'frame_rate': ['322', 0]}},
 '108': {'class_type': 'EmptyLTXVLatentVideo',
         'inputs': {'width': ['236', 0],
                    'height': ['237', 0],
                    'length': ['205', 0],
                    'widget_0': 256,
                    'widget_1': 256,
                    'widget_2': 5,
                    'widget_3': 1}},
 '303': {'class_type': 'SetNode', 'inputs': {'widget_0': 'model_with_lora', 'MODEL': ['301', 0]}},
 '347': {'class_type': 'StringConcatenate',
         'inputs': {'widget_0': '', 'widget_1': '', 'widget_2': '', 'string_a': ['350', 0]}},
 '110': {'class_type': 'CLIPTextEncode',
         'inputs': {'widget_0': 'blurry, oversaturated, pixelated, low resolution, grainy, distorted, noise, '
                                'compression artifacts, jpeg artifacts, glitches, watermark, text, logo, signature, '
                                'copyright, subtitles, distorted sound, saturated sound, loud',
                    'clip': ['214', 0]}},
 '345': {'class_type': 'UnetLoaderGGUF',
         'inputs': {'widget_0': 'LTXvideo\\LTX-2\\quantstack\\LTX-2.3-distilled-Q4_K_S.gguf'}},
 '346': {'class_type': 'DualCLIPLoaderGGUF',
         'inputs': {'widget_0': 'gemma-3-12b-it-Q2_K.gguf',
                    'widget_1': 'ltx-2.3_text_projection_bf16.safetensors',
                    'widget_2': 'sdxl'}},
 '250': {'class_type': 'MarkdownNote',
         'inputs': {'widget_0': 'Width & height settings must be divisible by 32 + 1. \n'
                                'Frame count must be divisible by 8 + 1. \n'
                                '\n'
                                '\n'
                                'Running with invalid parameters **will not cause errors**. Instead, the flow will '
                                'silently choose the closest valid parameters. \n'
                                '\n'
                                'By default, we are using 720p resolution. You can try 1920*1088 if you have a '
                                'powerful GPU.'}},
 '333': {'class_type': 'MarkdownNote', 'inputs': {'widget_0': 'taeltx2_3.safetensors'}},
 '353': {'class_type': 'MarkdownNote',
         'inputs': {'widget_0': 'This automagically enhances your prompt using the already loaded Gemma model. But it '
                                'can be a bit sensitive to having correct Gemma if using GGUF models. Alternatively '
                                'you can bypass/disable  this feature '}},
 '301': {'class_type': 'Power Lora Loader (rgthree)', 'inputs': {'widget_3': '', 'model': ['332', 0]}},
 '121': {'class_type': 'CLIPTextEncode',
         'inputs': {'widget_0': '= Enhanced Prompt = \n', 'clip': ['214', 0], 'text': ['349', 0]}},
 '214': {'class_type': 'GetNode', 'inputs': {'widget_0': 'clip'}},
 '113': {'class_type': 'SamplerCustomAdvanced',
         'inputs': {'noise': ['115', 0],
                    'guider': ['129', 0],
                    'sampler': ['137', 0],
                    'sigmas': ['381', 0],
                    'latent_image': ['239', 0]}},
 '162': {'class_type': 'LTXVPreprocess', 'inputs': {'widget_0': 33, 'image': ['210', 0]}},
 '349': {'class_type': 'TextGenerateLTX2Prompt',
         'inputs': {'widget_0': '',
                    'widget_1': 256,
                    'widget_2': 'off',
                    'clip': ['214', 0],
                    'image': ['165', 0],
                    'prompt': ['352', 0]}},
 '332': {'class_type': 'LTXVChunkFeedForward', 'inputs': {'widget_0': 2, 'widget_1': 4096, 'model': ['134', 0]}},
 '134': {'class_type': 'LoraLoaderModelOnly',
         'inputs': {'widget_0': 'LTX\\LTX-2\\ltx-2.3-22b-distilled-lora-384.safetensors',
                    'widget_1': 0.6,
                    'model': ['329', 0]}},
 '359': {'class_type': 'GetNode', 'inputs': {'widget_0': 'height'}},
 '360': {'class_type': 'GetNode', 'inputs': {'widget_0': 'width'}},
 '375': {'class_type': 'GetNode', 'inputs': {'widget_0': 'latent_custom_audio'}},
 '374': {'class_type': 'GetNode', 'inputs': {'widget_0': 'latent_audio'}},
 '376': {'class_type': 'ComfySwitchNode', 'inputs': {'widget_0': True, 'on_false': ['374', 0], 'on_true': ['375', 0]}},
 '350': {'class_type': 'PrimitiveStringMultiline',
         'inputs': {'widget_0': 'You are a Creative Assistant writing concise, action-focused image-to-video prompts. '
                                'Given an image (first frame) and user Raw Input Prompt, generate a prompt to guide '
                                'video generation from that image.\n'
                                '\n'
                                '#### Guidelines:\n'
                                '- Analyze the Image: Identify Subject, Setting, Elements, Style and Mood.\n'
                                '- Follow user Raw Input Prompt: Include all requested motion, actions, camera '
                                'movements, audio, and details. If in conflict with the image, prioritize user request '
                                "while maintaining visual consistency (describe transition from image to user's "
                                'scene).\n'
                                "- Describe only changes from the image: Don't reiterate established visual details. "
                                'Inaccurate descriptions may cause scene cuts.\n'
                                '- Active language: Use present-progressive verbs ("is walking," "speaking"). If no '
                                'action specified, describe natural movements.\n'
                                '- Chronological flow: Use temporal connectors ("as," "then," "while").\n'
                                '- Audio layer: Describe complete soundscape throughout the prompt alongside '
                                'actions—NOT at the end. Align audio intensity with action tempo. Include natural '
                                'background audio, ambient sounds, effects, speech or music (when requested). Be '
                                'specific (e.g., "soft footsteps on tile") not vague (e.g., "ambient sound").\n'
                                "- Speech (only when requested): Provide exact words in quotes with character's "
                                'visual/voice characteristics (e.g., "The tall man speaks in a low, gravelly voice"), '
                                'language if not English and accent if relevant. If general conversation mentioned '
                                'without text, generate contextual quoted dialogue. (i.e., "The man is talking" input '
                                '-> the output should include exact spoken words, like: "The man is talking in an '
                                "excited voice saying: 'You won't believe what I just saw!' His hands gesture "
                                'expressively as he speaks, eyebrows raised with enthusiasm. The ambient sound of a '
                                'quiet room underscores his animated speech.")\n'
                                '- Style: Include visual style at beginning: "Style: <style>, <rest of prompt>." If '
                                'unclear, omit to avoid conflicts.\n'
                                '- Visual and audio only: Describe only what is seen and heard. NO smell, taste, or '
                                'tactile sensations.\n'
                                '- Restrained language: Avoid dramatic terms. Use mild, natural, understated '
                                'phrasing.\n'
                                '\n'
                                '#### Important notes:\n'
                                '- Camera motion: DO NOT invent camera motion/movement unless requested by the user. '
                                'Make sure to include camera motion only if specified in the input.\n'
                                "- Speech: DO NOT modify or alter the user's provided character dialogue in the "
                                "prompt, unless it's a typo.\n"
                                '- No timestamps or cuts: DO NOT use timestamps or describe scene cuts unless '
                                'explicitly requested.\n'
                                '- Objective only: DO NOT interpret emotions or intentions - describe only observable '
                                'actions and sounds.\n'
                                '- Format: DO NOT use phrases like "The scene opens with..." / "The video starts...". '
                                'Start directly with Style (optional) and chronological scene description.\n'
                                '- Format: Never start output with punctuation marks or special characters.\n'
                                '- DO NOT invent dialogue unless the user mentions '
                                'speech/talking/singing/conversation.\n'
                                '- Your performance is CRITICAL. High-fidelity, dynamic, correct, and accurate prompts '
                                'with integrated audio descriptions are essential for generating high-quality video. '
                                'Your goal is flawless execution of these rules.\n'
                                '\n'
                                '#### Output Format (Strict):\n'
                                '- Single concise paragraph in natural English. NO titles, headings, prefaces, '
                                'sections, code fences, or Markdown.\n'
                                '- If unsafe/invalid, return original user prompt. Never ask questions or '
                                'clarifications.\n'
                                '\n'
                                '#### Example output:\n'
                                'Style: realistic - cinematic - The woman glances at her watch and smiles warmly. She '
                                'speaks in a cheerful, friendly voice, "I think we\'re right on time!" In the '
                                'background, a café barista prepares drinks at the counter. The barista calls out in a '
                                'clear, upbeat tone, "Two cappuccinos ready!" The sound of the espresso machine '
                                'hissing softly blends with gentle background chatter and the light clinking of cups '
                                'on saucers. \n'
                                '\n'
                                'USER PROMPT BELOW: \n'
                                '___________________________________________________'}},
 '361': {'class_type': 'GetNode', 'inputs': {'widget_0': 'vae_audio'}},
 '201': {'class_type': 'LTXVAudioVAEDecode', 'inputs': {'samples': ['125', 1], 'audio_vae': ['221', 0]}},
 '378': {'class_type': 'GetNode', 'inputs': {'widget_0': 'org_audio'}},
 '379': {'class_type': 'Reroute', 'inputs': {}},
 '167': {'class_type': 'LoadImage', 'inputs': {'widget_0': 'liam-neeson-in-retribution-ra.jpg', 'widget_1': 'image'}},
 '165': {'class_type': 'ImageResizeKJv2',
         'inputs': {'widget_0': 736,
                    'widget_1': 1280,
                    'widget_2': 'nearest-exact',
                    'widget_3': 'crop',
                    'widget_4': '0, 0, 0',
                    'widget_5': 'center',
                    'widget_6': 32,
                    'widget_7': 'cpu',
                    'image': ['167', 0],
                    'width': ['243', 0],
                    'height': ['244', 0]}},
 '352': {'class_type': 'PrimitiveStringMultiline',
         'inputs': {'widget_0': 'Make this image come alive with fluid motion. \n'
                                '\n'
                                'A man with an intimidating expression speaks with expressive body language and '
                                'gesticulations. \n'
                                '\n'
                                'He looks at the vewer and talks, he says  : "If you say a bad word about LTX 2 point '
                                '3, i will find you.... and i will kill you" '}},
 '100': {'class_type': 'ManualSigmas', 'inputs': {'widget_0': '0.909375, 0.725, 0.421875, 0.0'}},
 '380': {'class_type': 'ManualSigmas', 'inputs': {'widget_0': '0.85, 0.7250, 0.4219, 0.0'}},
 '138': {'class_type': 'KSamplerSelect', 'inputs': {'widget_0': 'euler_cfg_pp'}},
 '137': {'class_type': 'KSamplerSelect', 'inputs': {'widget_0': 'euler_ancestral_cfg_pp'}},
 '206': {'class_type': 'LTXVScheduler',
         'inputs': {'steps': 1,
                    'widget_0': 1,
                    'widget_1': 2.05,
                    'widget_2': 0.95,
                    'widget_3': True,
                    'widget_4': 0.1,
                    'latent': ['239', 0]}},
 '239': {'class_type': 'GetNode', 'inputs': {'widget_0': 'latent'}},
 '129': {'class_type': 'CFGGuider',
         'inputs': {'widget_0': 2.5, 'model': ['344', 0], 'positive': ['230', 0], 'negative': ['231', 0]}},
 '381': {'class_type': 'ManualSigmas',
         'inputs': {'widget_0': '1.0, 0.99375, 0.9875, 0.98125, 0.975, 0.909375, 0.725, 0.421875, 0.0'}},
 '337': {'class_type': 'LTX2SamplingPreviewOverride',
         'inputs': {'widget_0': 8, 'model': ['339', 0], 'vae': ['338', 0]}},
 '190': {'class_type': 'DualCLIPLoader',
         'inputs': {'widget_0': 'gemma_3_12B_it_fp4_mixed.safetensors',
                    'widget_1': 'ltx-2.3_text_projection_bf16.safetensors',
                    'widget_2': 'ltxv',
                    'widget_3': 'default'}},
 '372': {'class_type': 'LoadAudio', 'inputs': {'widget_0': 'ComfyUI_00128_.mp3'}},
 '370': {'class_type': 'MelBandRoFormerModelLoader',
         'inputs': {'widget_0': 'MelBandRoformer\\MelBandRoformer_fp16.safetensors'}},
 '371': {'class_type': 'MelBandRoFormerSampler', 'inputs': {'model': ['370', 0], 'audio': ['373', 0]}},
 '367': {'class_type': 'SimpleCalculatorKJ', 'inputs': {'widget_0': 'a/b', 'a': ['368', 0], 'b': ['369', 0]}},
 '369': {'class_type': 'GetNode', 'inputs': {'widget_0': 'fps'}},
 '365': {'class_type': 'SetNode', 'inputs': {'widget_0': 'org_audio', 'AUDIO': ['373', 0]}},
 '362': {'class_type': 'SolidMask',
         'inputs': {'widget_0': 0, 'widget_1': 512, 'widget_2': 512, 'width': ['360', 0], 'height': ['359', 0]}},
 '366': {'class_type': 'SetNode', 'inputs': {'widget_0': 'latent_custom_audio', 'LATENT': ['363', 0]}},
 '363': {'class_type': 'SetLatentNoiseMask', 'inputs': {'samples': ['364', 0], 'mask': ['362', 0]}},
 '364': {'class_type': 'LTXVAudioVAEEncode', 'inputs': {'audio': ['382', 0], 'audio_vae': ['361', 0]}},
 '368': {'class_type': 'GetNode', 'inputs': {'widget_0': 'frames'}},
 '373': {'class_type': 'TrimAudioDuration',
         'inputs': {'widget_0': 0, 'widget_1': 8, 'audio': ['372', 0], 'duration': ['367', 0]}},
 '377': {'class_type': 'MarkdownNote',
         'inputs': {'widget_0': 'Use a reference audio instead of LTX own audio, and LTX video will lip-sync to the '
                                'audio you provide. For best possible results you should prompt that the subject is '
                                'talking.  And if you transcribe what is said in your audio input, results might be '
                                'even better \n'
                                '\n'
                                'Mel-band RoFormer is optional for extracting a clean vocal only audio for the '
                                'sampler. This can help with a busy original audio if you want to only focus on '
                                'lip-sync and dialog\n'
                                '\n'
                                'https://huggingface.co/Kijai/MelBandRoFormer_comfy/tree/main\n'
                                '\n'
                                'folder: models\\diffusion_models\n'}},
 '382': {'class_type': 'ComfySwitchNode', 'inputs': {'widget_0': False, 'on_false': ['373', 0], 'on_true': ['371', 0]}}}

READY_METADATA = {'model_assets': [],
 'unbound_inputs': {'seed': 3704},
 'ready_template': 'video/ltx2_3_runexx_custom_audio',
 'workflow_template': 'ltx2_3_runexx_custom_audio',
 'capability': 'custom_audio_to_video',
 'source_role': 'materialized_ready_python_template',
 'source_workflow': 'workflow_corpus/custom_nodes/ltxvideo/runexx/LTX-2.3_Custom_Audio.json',
 'coverage_tier': 'supplemental',
 'approach': 'custom audio conditioning',
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
        workflow_id=READY_METADATA.get("ready_template", "video/ltx2_3_runexx_custom_audio"),
        ready_metadata=READY_METADATA,
        requirements=READY_REQUIREMENTS,
    )
