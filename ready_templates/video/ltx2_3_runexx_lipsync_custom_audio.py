from __future__ import annotations

from vibecomfy.registry.ready_template import build_api_ready_workflow


API_WORKFLOW = {'244': {'class_type': 'GetNode', 'inputs': {'widget_0': 'vae'}},
 '459': {'class_type': 'SetNode', 'inputs': {'widget_0': 'upscale_model', 'LATENT_UPSCALE_MODEL': ['465', 0]}},
 '460': {'class_type': 'SetNode', 'inputs': {'widget_0': 'vae_audio', 'VAE': ['471', 0]}},
 '461': {'class_type': 'SetNode', 'inputs': {'widget_0': 'vae', 'VAE': ['463', 0]}},
 '467': {'class_type': 'MarkdownNote',
         'inputs': {'widget_0': '## LTX-2 Prompting Tips\n'
                                '1. **Core Actions**: Describe events and actions as they occur over time  \n'
                                '2. **Audio**: Describe sounds and dialogue needed for the scene  \n'
                                '3. **Reference Image**: Do not repeat details already present  \n'
                                '4. **Consistency**: Avoid instructions that do not match the reference image, as this '
                                'will degrade results'}},
 '472': {'class_type': 'SetNode', 'inputs': {'widget_0': 'vae_tiny', 'VAE': ['473', 0]}},
 '473': {'class_type': 'VAELoader', 'inputs': {'widget_0': 'taeltx2_3.safetensors'}},
 '477': {'class_type': 'DualCLIPLoaderGGUF',
         'inputs': {'widget_0': 'gemma-3-12b-it-Q2_K.gguf',
                    'widget_1': 'ltx-2.3_text_projection_bf16.safetensors',
                    'widget_2': 'sdxl'}},
 '476': {'class_type': 'MarkdownNote',
         'inputs': {'widget_0': 'Download models from here:\n'
                                '\n'
                                '\n'
                                'https://huggingface.co/Kijai/LTX2.3_comfy\n'
                                '\n'
                                'Text encoder : https://huggingface.co/Comfy-Org/ltx-2'}},
 '498': {'class_type': 'SetNode', 'inputs': {'widget_0': 'max_size', 'INT': ['497', 0]}},
 '502': {'class_type': 'GetNode', 'inputs': {'widget_0': 'max_size'}},
 '507': {'class_type': 'GetNode', 'inputs': {'widget_0': 'max_size'}},
 '496': {'class_type': 'Reroute', 'inputs': {}},
 '505': {'class_type': 'ResizeImagesByLongerEdge',
         'inputs': {'widget_0': 1536, 'images': ['496', 0], 'longer_edge': ['507', 0]}},
 '470': {'class_type': 'MarkdownNote',
         'inputs': {'widget_0': 'This automagically enhances your prompt using the already loaded Gemma model. But it '
                                'can be a bit sensitive to having correct Gemma if using GGUF models. Alternatively '
                                'you can bypass/disable  this feature '}},
 '471': {'class_type': 'VAELoaderKJ',
         'inputs': {'widget_0': 'LTX23_audio_vae_bf16.safetensors', 'widget_1': 'main_device', 'widget_2': 'bf16'}},
 '475': {'class_type': 'UnetLoaderGGUF',
         'inputs': {'widget_0': 'LTXvideo\\LTX-2\\quantstack\\LTX-2.3-distilled-Q4_K_S.gguf'}},
 '601': {'class_type': 'SetNode', 'inputs': {'widget_0': 'enable_promptenhance', 'BOOLEAN': ['594', 0]}},
 '580': {'class_type': 'GetNode', 'inputs': {'widget_0': 'fps'}},
 '469': {'class_type': 'MarkdownNote', 'inputs': {'widget_0': 'taeltx2_3.safetensors'}},
 '219': {'class_type': 'GetNode', 'inputs': {'widget_0': 'vae_audio'}},
 '464': {'class_type': 'LoraLoaderModelOnly',
         'inputs': {'widget_0': 'LTX\\LTX-2\\ltx-2.3-22b-distilled-lora-384.safetensors',
                    'widget_1': 0.6,
                    'model': ['474', 0]}},
 '299': {'class_type': 'LTXVPreprocess', 'inputs': {'widget_0': 18, 'image': ['495', 0]}},
 '285': {'class_type': 'SetNode', 'inputs': {'widget_0': 'compress_image', 'IMAGE': ['299', 0]}},
 '648': {'class_type': 'SetNode', 'inputs': {'widget_0': 'final_audio', 'AUDIO': ['425', 0]}},
 '652': {'class_type': 'GetNode', 'inputs': {'widget_0': 'model_n_nag'}},
 '654': {'class_type': 'GetNode', 'inputs': {'widget_0': 'model_n_nag'}},
 '651': {'class_type': 'SetNode', 'inputs': {'widget_0': 'model_n_nag', 'MODEL': ['563', 0]}},
 '465': {'class_type': 'LatentUpscaleModelLoader',
         'inputs': {'widget_0': 'ltx-2.3-spatial-upscaler-x2-1.1.safetensors'}},
 '500': {'class_type': 'SimpleCalculatorKJ',
         'inputs': {'widget_0': '(a > c) or (b > c) ',
                    'variables.a': ['492', 8],
                    'variables.b': ['492', 9],
                    'variables.c': ['502', 0]}},
 '294': {'class_type': 'SetNode', 'inputs': {'widget_0': 'ref_image', 'IMAGE': ['495', 0]}},
 '504': {'class_type': 'LazySwitchKJ',
         'inputs': {'widget_0': False, 'on_false': ['496', 0], 'on_true': ['505', 0], 'switch': ['500', 2]}},
 '481': {'class_type': 'SetNode', 'inputs': {'widget_0': 'model', 'MODEL': ['660', 0]}},
 '506': {'class_type': 'GetImageSizeAndCount', 'inputs': {'image': ['504', 0]}},
 '495': {'class_type': 'ResizeImagesByLongerEdge', 'inputs': {'widget_0': 1536, 'images': ['440', 0]}},
 '208': {'class_type': 'SetNode', 'inputs': {'widget_0': 'height', 'INT': ['512', 2]}},
 '581': {'class_type': 'GetNode', 'inputs': {'widget_0': 'final_video'}},
 '209': {'class_type': 'SetNode', 'inputs': {'widget_0': 'ext_seconds', 'INT': ['211', 0]}},
 '210': {'class_type': 'SetNode', 'inputs': {'widget_0': 'fps', 'FLOAT': ['214', 0]}},
 '214': {'class_type': 'PrimitiveFloat', 'inputs': {'widget_0': 8}},
 '442': {'class_type': 'GetNode', 'inputs': {'widget_0': 'vae'}},
 '408': {'class_type': 'GetNode', 'inputs': {'widget_0': 'vae_tiny'}},
 '242': {'class_type': 'GetNode', 'inputs': {'widget_0': 'upscale_model'}},
 '251': {'class_type': 'LTXVConcatAVLatent', 'inputs': {'video_latent': ['438', 0], 'audio_latent': ['250', 1]}},
 '439': {'class_type': 'GetNode', 'inputs': {'widget_0': 'ref_image'}},
 '438': {'class_type': 'LTXVImgToVideoInplace',
         'inputs': {'widget_0': 1, 'widget_1': False, 'vae': ['442', 0], 'image': ['439', 0], 'latent': ['810', 2]}},
 '479': {'class_type': 'ManualSigmas', 'inputs': {'widget_0': '0.85, 0.7250, 0.4219, 0.0'}},
 '222': {'class_type': 'GetNode', 'inputs': {'widget_0': 'fps'}},
 '215': {'class_type': 'GetNode', 'inputs': {'widget_0': 'clip'}},
 '626': {'class_type': 'CLIPTextEncode',
         'inputs': {'widget_0': ' distorted sound, saturated sound, loud sound', 'clip': ['215', 0]}},
 '592': {'class_type': 'CLIPTextEncode',
         'inputs': {'widget_0': '= from prompt enhancer = ', 'clip': ['215', 0], 'text': ['784', 0]}},
 '655': {'class_type': 'SetNode', 'inputs': {'widget_0': 'positive', 'CONDITIONING': ['592', 0]}},
 '656': {'class_type': 'SetNode', 'inputs': {'widget_0': 'negative', 'CONDITIONING': ['110', 0]}},
 '739': {'class_type': 'GetNode', 'inputs': {'widget_0': 'positive'}},
 '220': {'class_type': 'GetNode', 'inputs': {'widget_0': 'vae'}},
 '451': {'class_type': 'SetNode', 'inputs': {'widget_0': 'final_video', 'IMAGE': ['527', 0]}},
 '462': {'class_type': 'SetNode', 'inputs': {'widget_0': 'clip', 'CLIP': ['742', 0]}},
 '701': {'class_type': 'ComfyMathExpression',
         'inputs': {'widget_0': 'a+b', 'values.a': ['700', 0], 'values.b': ['356', 0]}},
 '643': {'class_type': 'GetNode', 'inputs': {'widget_0': 'fps'}},
 '699': {'class_type': 'ComfyMathExpression', 'inputs': {'widget_0': 'a', 'values.a': ['643', 0]}},
 '724': {'class_type': 'GetNode', 'inputs': {'widget_0': 'ref_video'}},
 '468': {'class_type': 'MarkdownNote',
         'inputs': {'widget_0': 'If using some user made LTX-2 loras they sometimes are not trained on audio, so it '
                                'will produce very noisy audio outputs. Try use KJNodes LTX-2 Lora Loader Advanced in '
                                'such cases, and set the non video strenght to zero\n'}},
 '440': {'class_type': 'GetImageRangeFromBatch', 'inputs': {'widget_0': 0, 'widget_1': 1, 'images': ['512', 0]}},
 '207': {'class_type': 'SetNode', 'inputs': {'widget_0': 'width', 'INT': ['512', 1]}},
 '328': {'class_type': 'SetNode', 'inputs': {'widget_0': 'ref_video', 'IMAGE': ['512', 0]}},
 '221': {'class_type': 'GetNode', 'inputs': {'widget_0': 'fps'}},
 '508': {'class_type': 'GetNode', 'inputs': {'widget_0': 'ref_image'}},
 '600': {'class_type': 'GetNode', 'inputs': {'widget_0': 'clip'}},
 '602': {'class_type': 'GetNode', 'inputs': {'widget_0': 'enable_promptenhance'}},
 '742': {'class_type': 'LTXAVTextEncoderLoader',
         'inputs': {'text_encoder': 'gemma_3_12B_it_fp4_mixed.safetensors',
                    'ckpt_name': 'ltx-2.3-22b-dev-fp8.safetensors',
                    'widget_0': 'gemma_3_12B_it_fp4_mixed.safetensors',
                    'widget_1': 'VIDEO\\LTX\\LTX-2\\ltx-2.3_text_projection_bf16.safetensors',
                    'widget_2': 'default'}},
 '463': {'class_type': 'VAELoader', 'inputs': {'widget_0': 'LTX23_video_vae_bf16.safetensors'}},
 '127': {'class_type': 'VAEDecodeTiled', 'inputs': {'widget_0': 512, 'widget_1': 64, 'widget_2': 4096, 'widget_3': 8}},
 '466': {'class_type': 'DualCLIPLoader',
         'inputs': {'widget_0': 'gemma_3_12B_it_fp4_mixed.safetensors',
                    'widget_1': 'ltx-2.3_text_projection_bf16.safetensors',
                    'widget_2': 'ltxv',
                    'widget_3': 'default'}},
 '524': {'class_type': 'MarkdownNote',
         'inputs': {'widget_0': '**MAX SIZE**:  Max pixels of the output video (longest side). If lower ram/vram try '
                                'reasonable sizes such as 768,  832 or 960. And if the original video is lower than '
                                'that, set same as original video \n'
                                '\n'
                                '\n'
                                '**EXTEND in seconds** : How much to add to your video. LTX works best with 5s, 10s or '
                                '15s.\n'
                                '\n'
                                '**FPS**  You can either set the fps same as the input video, or set it to 24 as is '
                                'most common with LTX \n'
                                '\n'
                                '\n'}},
 '633': {'class_type': 'MarkdownNote',
         'inputs': {'widget_0': 'With this workflow you can run both as a single-pass and 2-pass mode.\n'
                                '\n'
                                '2-pass workflow is usually a faster and easier on ram/vram. Feel free to try both '
                                'modes with the toggles (**Toggle both to change mode**)\n'}},
 '719': {'class_type': 'GetNode', 'inputs': {'widget_0': 'vae'}},
 '714': {'class_type': 'GetImageRangeFromBatch', 'inputs': {'widget_0': 0, 'widget_1': 1, 'images': ['726', 0]}},
 '726': {'class_type': 'ResizeImageMaskNode',
         'inputs': {'widget_0': 'scale by multiplier',
                    'widget_1': 256,
                    'widget_2': 'nearest-exact',
                    'input': ['724', 0]}},
 '775': {'class_type': 'GetImageRangeFromBatch', 'inputs': {'widget_0': 0, 'widget_1': 1, 'images': ['791', 0]}},
 '791': {'class_type': 'MaskToImage', 'inputs': {'mask': ['790', 0]}},
 '717': {'class_type': 'ResizeImageMaskNode',
         'inputs': {'widget_0': 'match size',
                    'widget_1': 256,
                    'widget_2': 'nearest-exact',
                    'input': ['790', 0],
                    'resize_type.match': ['714', 0]}},
 '763': {'class_type': 'PreviewImage', 'inputs': {'images': ['775', 0]}},
 '129': {'class_type': 'CFGGuider',
         'inputs': {'widget_0': 2.5, 'model': ['654', 0], 'positive': ['799', 0], 'negative': ['799', 1]}},
 '113': {'class_type': 'SamplerCustomAdvanced',
         'inputs': {'noise': ['115', 0],
                    'guider': ['129', 0],
                    'sampler': ['137', 0],
                    'sigmas': ['480', 0],
                    'latent_image': ['109', 0]}},
 '258': {'class_type': 'SamplerCustomAdvanced',
         'inputs': {'noise': ['243', 0],
                    'guider': ['256', 0],
                    'sampler': ['254', 0],
                    'sigmas': ['479', 0],
                    'latent_image': ['251', 0]}},
 '740': {'class_type': 'GetNode', 'inputs': {'widget_0': 'negative'}},
 '369': {'class_type': 'GetNode', 'inputs': {'widget_0': 'model'}},
 '737': {'class_type': 'MarkdownNote',
         'inputs': {'widget_0': '**Face selection:** \n'
                                '\n'
                                'Mouth, upper and lower lips for most faithful re-creation of the input video. But '
                                'masking more might look more natural (masking all of face)\n'
                                '\n'
                                '**Limitation**: Made for human like input videos. For non human creatures, it might '
                                'fail to detect. Try the other "Point Editor" workflow variant for this (with a '
                                'sidenote, LTX will still try make lipsync even if the mask fails)'}},
 '521': {'class_type': 'LTX2MemoryEfficientSageAttentionPatch', 'inputs': {'widget_0': True, 'model': ['520', 0]}},
 '243': {'class_type': 'RandomNoise', 'inputs': {'widget_0': 43, 'widget_1': 'fixed'}},
 '250': {'class_type': 'LTXVSeparateAVLatent', 'inputs': {'av_latent': ['113', 0]}},
 '573': {'class_type': 'GetNode', 'inputs': {'widget_0': 'negative'}},
 '572': {'class_type': 'GetNode', 'inputs': {'widget_0': 'positive'}},
 '256': {'class_type': 'CFGGuider',
         'inputs': {'widget_0': 2.5, 'model': ['652', 0], 'positive': ['572', 0], 'negative': ['573', 0]}},
 '356': {'class_type': 'GetNode', 'inputs': {'widget_0': 'ext_seconds'}},
 '815': {'class_type': 'SetNode', 'inputs': {'widget_0': 'last_latent_strength', 'FLOAT': ['814', 0]}},
 '809': {'class_type': 'VAEEncode', 'inputs': {'pixels': ['806', 0], 'vae': ['804', 0]}},
 '700': {'class_type': 'ComfyMathExpression',
         'inputs': {'widget_0': 'a/b', 'values.a': ['698', 3], 'values.b': ['643', 0]}},
 '425': {'class_type': 'LTXVAudioVAEDecode', 'inputs': {'samples': ['125', 1], 'audio_vae': ['219', 0]}},
 '110': {'class_type': 'CLIPTextEncode',
         'inputs': {'widget_0': 'text, subtitles, logo, low quality, distorted, bad anatomy, oversaturated, pixelated, '
                                'low resolution, grainy, compression artifacts, jpeg artifacts, glitches, watermark, '
                                'signature, copyright,  distortedsound, saturated sound, loud sound , deformed facial '
                                'features, asymmetrical face, missing facial features, extra limbs, disfigured hands, '
                                'blurry teeth, disfigured teeth',
                    'clip': ['215', 0]}},
 '563': {'class_type': 'LTX2_NAG',
         'inputs': {'widget_0': 11,
                    'widget_1': 0.25,
                    'widget_2': 2.5,
                    'widget_3': True,
                    'model': ['368', 0],
                    'nag_cond_video': ['110', 0],
                    'nag_cond_audio': ['626', 0]}},
 '520': {'class_type': 'PathchSageAttentionKJ', 'inputs': {'widget_0': 'auto', 'widget_1': False, 'model': ['464', 0]}},
 '761': {'class_type': 'FaceSegment',
         'inputs': {'widget_0': True,
                    'widget_1': True,
                    'widget_2': False,
                    'widget_3': True,
                    'widget_4': True,
                    'widget_5': True,
                    'widget_6': True,
                    'widget_7': True,
                    'widget_8': True,
                    'widget_9': True,
                    'widget_10': True,
                    'widget_11': True,
                    'widget_12': False,
                    'widget_13': False,
                    'widget_14': False,
                    'widget_15': 512,
                    'widget_16': 0,
                    'widget_17': 10,
                    'widget_18': False,
                    'widget_19': 'Alpha',
                    'widget_20': '#222222',
                    'images': ['726', 0]}},
 '790': {'class_type': 'BlockifyMask', 'inputs': {'widget_0': 12, 'widget_1': 'cpu', 'masks': ['761', 1]}},
 '804': {'class_type': 'GetNode', 'inputs': {'widget_0': 'vae'}},
 '806': {'class_type': 'GetImageRangeFromBatch', 'inputs': {'widget_0': -1, 'widget_1': 1, 'images': ['436', 0]}},
 '816': {'class_type': 'GetNode', 'inputs': {'widget_0': 'last_latent_strength'}},
 '730': {'class_type': 'LTXVImgToVideoInplace',
         'inputs': {'widget_0': 0.7, 'widget_1': False, 'vae': ['731', 0], 'image': ['732', 0], 'latent': ['799', 2]}},
 '720': {'class_type': 'LTXVPreprocessMasks',
         'inputs': {'widget_0': False,
                    'widget_1': False,
                    'widget_2': 'max',
                    'widget_3': 0,
                    'widget_4': True,
                    'widget_5': 0.5,
                    'widget_6': 1,
                    'masks': ['717', 0],
                    'vae': ['719', 0]}},
 '107': {'class_type': 'LTXVConditioning',
         'inputs': {'widget_0': 8, 'positive': ['739', 0], 'negative': ['740', 0], 'frame_rate': ['222', 0]}},
 '732': {'class_type': 'GetNode', 'inputs': {'widget_0': 'ref_image'}},
 '731': {'class_type': 'GetNode', 'inputs': {'widget_0': 'vae'}},
 '519': {'class_type': 'MarkdownNote',
         'inputs': {'widget_0': '**A LITTLE USAGE TIP** \n'
                                '\n'
                                'If you want to start extending earlier (aka cut some from end of input video) you can '
                                'use **frame_load_cap** in the video loader node and set max frames to use. And vice '
                                'verse if you want to cut off some of the start of your input video you can use  '
                                '**skip_first_frames** \n'}},
 '794': {'class_type': 'LTXVSetVideoLatentNoiseMasks', 'inputs': {'samples': ['565', 0], 'masks': ['720', 0]}},
 '649': {'class_type': 'GetNode', 'inputs': {'widget_0': 'final_audio'}},
 '578': {'class_type': 'VHS_VideoCombine',
         'inputs': {'images': ['581', 0], 'audio': ['649', 0], 'frame_rate': ['580', 0]}},
 '821': {'class_type': 'SetNode', 'inputs': {'widget_0': 'negative_to_crop', 'CONDITIONING': ['799', 1]}},
 '820': {'class_type': 'SetNode', 'inputs': {'widget_0': 'positive_to_crop', 'CONDITIONING': ['799', 0]}},
 '799': {'class_type': 'LTXVAddLatentGuide',
         'inputs': {'widget_0': -1,
                    'widget_1': 0.7,
                    'vae': ['804', 0],
                    'positive': ['107', 0],
                    'negative': ['107', 1],
                    'latent': ['178', 0],
                    'guiding_latent': ['809', 0],
                    'latent_idx': ['698', 3],
                    'strength': ['816', 0]}},
 '822': {'class_type': 'GetNode', 'inputs': {'widget_0': 'positive_to_crop'}},
 '823': {'class_type': 'GetNode', 'inputs': {'widget_0': 'negative_to_crop'}},
 '125': {'class_type': 'LTXVSeparateAVLatent', 'inputs': {'av_latent': ['258', 0]}},
 '824': {'class_type': 'LTXVCropGuides',
         'inputs': {'positive': ['826', 0], 'negative': ['825', 0], 'latent': ['125', 0]}},
 '826': {'class_type': 'GetNode', 'inputs': {'widget_0': 'positive_to_crop'}},
 '825': {'class_type': 'GetNode', 'inputs': {'widget_0': 'negative_to_crop'}},
 '527': {'class_type': 'VAEDecode', 'inputs': {'samples': ['824', 2], 'vae': ['220', 0]}},
 '789': {'class_type': 'MarkdownNote',
         'inputs': {'widget_0': 'For lip-sync **only prompt** for the dialog. The more other things you prompt, the '
                                'more might change in the final output.  Typical prompt could be something like:  \n'
                                '\n'
                                '_She talks with a soft British accent, and she says: "Oh hello there, I can talk, '
                                'thanks to LTX". She talks with perfect lip-sync movements. Her mouth and lips moves '
                                'as she talks. _'}},
 '796': {'class_type': 'MarkdownNote',
         'inputs': {'widget_0': '**FACE MASK***\n'
                                'If you want more strict follow the input video you can use the masking. If the '
                                'masking end up with lack of lip-sync try **mask more of face** to give the model more '
                                'freedom of expression. \n'
                                '\n'
                                '**Re-Imagine***\n'
                                'And as a last resort you can toggle on the **Re-Imagine** option that will '
                                're-generate a "new" video based on your input. You can also try the mask offset to '
                                'increase the masked area\n'
                                '\n'}},
 '810': {'class_type': 'LTXVCropGuides',
         'inputs': {'positive': ['822', 0], 'negative': ['823', 0], 'latent': ['250', 0]}},
 '526': {'class_type': 'ModelSamplingSD3', 'inputs': {'widget_0': 13, 'model': ['368', 0]}},
 '164': {'class_type': 'BasicScheduler',
         'inputs': {'steps': 1, 'widget_0': 1, 'widget_1': 15, 'widget_2': 1, 'model': ['526', 0]}},
 '480': {'class_type': 'ManualSigmas',
         'inputs': {'widget_0': '1.0, 0.99375, 0.9875, 0.98125, 0.975, 0.909375, 0.725, 0.421875, 0.0'}},
 '137': {'class_type': 'KSamplerSelect', 'inputs': {'widget_0': 'euler_ancestral_cfg_pp'}},
 '254': {'class_type': 'KSamplerSelect', 'inputs': {'widget_0': 'euler_cfg_pp'}},
 '853': {'class_type': 'SetNode', 'inputs': {'widget_0': 'audio_vocals', 'AUDIO': ['860', 0]}},
 '858': {'class_type': 'GetNode', 'inputs': {'widget_0': 'vae_audio'}},
 '860': {'class_type': 'MelBandRoFormerSampler', 'inputs': {'model': ['861', 0], 'audio': ['859', 0]}},
 '861': {'class_type': 'MelBandRoFormerModelLoader',
         'inputs': {'widget_0': 'MelBandRoformer\\MelBandRoformer_fp16.safetensors'}},
 '866': {'class_type': 'LTXVAudioVAEEncode', 'inputs': {'audio': ['868', 0], 'audio_vae': ['858', 0]}},
 '867': {'class_type': 'SetNode', 'inputs': {'widget_0': 'audio', 'AUDIO': ['868', 0]}},
 '868': {'class_type': 'ComfySwitchNode', 'inputs': {'widget_0': True, 'on_false': ['859', 0], 'on_true': ['860', 0]}},
 '115': {'class_type': 'RandomNoise', 'inputs': {'widget_0': 790774741312584, 'widget_1': 'randomize'}},
 '871': {'class_type': 'SetNode', 'inputs': {'widget_0': 'frames_loaded', 'INT': ['492', 6]}},
 '492': {'class_type': 'VHS_VideoInfo', 'inputs': {'video_info': ['774', 3]}},
 '660': {'class_type': 'Power Lora Loader (rgthree)', 'inputs': {'widget_3': '', 'model': ['523', 0]}},
 '814': {'class_type': 'PrimitiveFloat', 'inputs': {'widget_0': 8}},
 '818': {'class_type': 'MarkdownNote',
         'inputs': {'widget_0': 'Strength of end frame from input video (before extend). Not having it too strong '
                                'gives the model more freedom for natural movements, but might be less true to the '
                                'input video\n'}},
 '474': {'class_type': 'UNETLoader',
         'inputs': {'widget_0': 'ltx-2.3-22b-distilled-1.1_transformer_only_fp8_scaled.safetensors',
                    'widget_1': 'default'}},
 '594': {'class_type': 'PrimitiveBoolean', 'inputs': {'widget_0': False}},
 '784': {'class_type': 'e428c881-c48b-4849-9158-8311b4df27c7',
         'inputs': {'clip': ['600', 0], 'image': ['508', 0], 'switch': ['602', 0]}},
 '774': {'class_type': 'VHS_LoadVideoFFmpeg', 'inputs': {'force_rate': ['221', 0]}},
 '497': {'class_type': 'INTConstant', 'inputs': {'widget_0': 650}},
 '522': {'class_type': 'LTXVChunkFeedForward', 'inputs': {'widget_0': 2, 'widget_1': 4096, 'model': ['521', 0]}},
 '523': {'class_type': 'LTX2AttentionTunerPatch',
         'inputs': {'widget_0': '',
                    'widget_1': 1,
                    'widget_2': 1,
                    'widget_3': 1,
                    'widget_4': 1,
                    'widget_5': True,
                    'model': ['522', 0]}},
 '854': {'class_type': 'SimpleCalculatorKJ',
         'inputs': {'widget_0': '(a/b)+c',
                    'variables.a': ['872', 0],
                    'variables.b': ['873', 0],
                    'variables.c': ['874', 0]}},
 '872': {'class_type': 'GetNode', 'inputs': {'widget_0': 'frames_loaded'}},
 '873': {'class_type': 'GetNode', 'inputs': {'widget_0': 'fps'}},
 '874': {'class_type': 'GetNode', 'inputs': {'widget_0': 'ext_seconds'}},
 '852': {'class_type': 'SetNode', 'inputs': {'widget_0': 'audio_original', 'AUDIO': ['859', 0]}},
 '855': {'class_type': 'LoadAudio', 'inputs': {'widget_0': 'e9318ca1-5e2b-47aa-8397-f4538b0151b0.wav'}},
 '487': {'class_type': 'PrimitiveStringMultiline',
         'inputs': {'widget_0': 'Cinematic video woman wearing colorful make-up, with colorful  light creating a '
                                'creative scene. \n'
                                '\n'
                                'She talks with perfect lip-sync movements to the attached audio. Her mouth and lips '
                                'moves as she talks. \n'
                                ' \n'
                                'The camera slowly moves away from the woman, showing her full body. She is standing '
                                'at a  colorful theatre scene doing a victorian era play. '}},
 '211': {'class_type': 'INTConstant', 'inputs': {'widget_0': 3}},
 '879': {'class_type': 'GetNode', 'inputs': {'widget_0': 'latent_audio_selected'}},
 '368': {'class_type': 'LTX2SamplingPreviewOverride',
         'inputs': {'widget_0': 19, 'model': ['369', 0], 'vae': ['408', 0]}},
 '436': {'class_type': 'ResizeImageMaskNode',
         'inputs': {'widget_0': 'scale by multiplier', 'widget_1': 256, 'widget_2': 'area', 'input': ['638', 0]}},
 '565': {'class_type': 'VAEEncode', 'inputs': {'pixels': ['436', 0], 'vae': ['217', 0]}},
 '217': {'class_type': 'GetNode', 'inputs': {'widget_0': 'vae'}},
 '216': {'class_type': 'GetNode', 'inputs': {'widget_0': 'vae_audio'}},
 '862': {'class_type': 'GetNode', 'inputs': {'widget_0': 'width_generated'}},
 '856': {'class_type': 'GetNode', 'inputs': {'widget_0': 'height_generated'}},
 '865': {'class_type': 'SolidMask',
         'inputs': {'widget_0': 0, 'widget_1': 512, 'widget_2': 512, 'width': ['862', 0], 'height': ['856', 0]}},
 '859': {'class_type': 'TrimAudioDuration',
         'inputs': {'widget_0': 0, 'widget_1': 40, 'audio': ['855', 0], 'duration': ['854', 0]}},
 '869': {'class_type': 'MarkdownNote',
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
 '863': {'class_type': 'SetNode', 'inputs': {'widget_0': 'latent_custom_audio', 'LATENT': ['864', 0]}},
 '864': {'class_type': 'SetLatentNoiseMask', 'inputs': {'samples': ['866', 0], 'mask': ['865', 0]}},
 '876': {'class_type': 'SetNode', 'inputs': {'widget_0': 'latent_audio', 'LATENT': ['178', 1]}},
 '887': {'class_type': 'GetNode', 'inputs': {'widget_0': 'latent_audio_selected'}},
 '109': {'class_type': 'LTXVConcatAVLatent', 'inputs': {'video_latent': ['730', 0], 'audio_latent': ['887', 0]}},
 '638': {'class_type': 'GetNode', 'inputs': {'widget_0': 'ref_video'}},
 '884': {'class_type': 'SetNode', 'inputs': {'widget_0': 'height_generated', 'INT': ['698', 2]}},
 '698': {'class_type': 'GetImageSizeAndCount', 'inputs': {'image': ['638', 0]}},
 '883': {'class_type': 'SetNode', 'inputs': {'widget_0': 'width_generated', 'INT': ['698', 1]}},
 '642': {'class_type': 'LTXVEmptyLatentAudio',
         'inputs': {'frames_number': ['698', 3],
                    'frame_rate': ['699', 1],
                    'widget_0': 5,
                    'widget_1': 8,
                    'widget_2': 1,
                    'audio_vae': ['216', 0]}},
 '178': {'class_type': 'LTXVAudioVideoMask',
         'inputs': {'widget_0': 24,
                    'widget_1': 0,
                    'widget_2': 15,
                    'widget_3': 0,
                    'widget_4': 10000,
                    'widget_5': 'pad',
                    'widget_6': 'add',
                    'video_latent': ['794', 0],
                    'audio_latent': ['642', 0],
                    'video_fps': ['643', 0],
                    'video_start_time': ['700', 0],
                    'video_end_time': ['701', 0],
                    'audio_end_time': ['701', 0]}},
 '846': {'class_type': 'GetNode', 'inputs': {'widget_0': 'latent_audio'}},
 '845': {'class_type': 'GetNode', 'inputs': {'widget_0': 'latent_custom_audio'}},
 '849': {'class_type': 'SetNode', 'inputs': {'widget_0': 'latent_audio_selected', 'LATENT': ['847', 0]}},
 '847': {'class_type': 'ComfySwitchNode', 'inputs': {'widget_0': True, 'on_false': ['846', 0], 'on_true': ['845', 0]}},
 '512': {'class_type': 'ImageResizeKJv2',
         'inputs': {'widget_0': 512,
                    'widget_1': 512,
                    'widget_2': 'nearest-exact',
                    'widget_3': 'crop',
                    'widget_4': '0, 0, 0',
                    'widget_5': 'center',
                    'widget_6': 64,
                    'widget_7': 'cpu',
                    'image': ['506', 0],
                    'width': ['506', 1],
                    'height': ['506', 2]}}}

READY_METADATA = {'model_assets': [],
 'unbound_inputs': {'seed': 4569},
 'ready_template': 'video/ltx2_3_runexx_lipsync_custom_audio',
 'workflow_template': 'ltx2_3_runexx_lipsync_custom_audio',
 'capability': 'voice_to_lipsync_video',
 'source_role': 'materialized_ready_python_template',
 'source_workflow': 'workflow_corpus/custom_nodes/ltxvideo/runexx/LTX-2.3_V2V_Just_Talk_custom_audio_lipsync.json',
 'coverage_tier': 'supplemental',
 'approach': 'custom-audio lip-sync / voice-to-video',
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
        workflow_id=READY_METADATA.get("ready_template", "video/ltx2_3_runexx_lipsync_custom_audio"),
        ready_metadata=READY_METADATA,
        requirements=READY_REQUIREMENTS,
    )
