# vibecomfy: generated — converted by tools/convert_ready_templates.py
# Edits will be overwritten on regeneration. Add a `# vibecomfy: manual`
# marker on the first line if hand-editing is required.
"""Audio Image To Video with Gemma CLIP.

Output: unknown.

Source:  workflow_corpus/custom_nodes/ltxvideo/iamccs/IAMCCS_LTX2_AU_IMG2V.json

Packs:   ComfyUI-GGUF, ComfyUI-KJNodes, ComfyUI-LTXVideo, ComfyUI-VideoHelperSuite, rgthree-comfy
"""
from __future__ import annotations

from vibecomfy.workflow import VibeWorkflow
from vibecomfy.templates import InputSpec, ModelAsset, ReadyMetadata, finalize, new_workflow, node
MODELS = {
    'gemma_clip': ModelAsset(
        filename='gemma_3_12B_it_fp8_e4m3fn.safetensors',
        url='',
        subdir='text_encoders',
    ),
    'ltx_2_19b_embeddings_connector_dev_bf16_cl': ModelAsset(
        filename='ltx-2-19b-embeddings_connector_dev_bf16.safetensors',
        url='',
        subdir='text_encoders',
    ),
    'ltx_2_19b_distilled_checkpoint': ModelAsset(
        filename='ltx-2-19b-distilled.safetensors',
        url='',
        subdir='checkpoints',
    ),
}

PUBLIC_INPUTS = {}

READY_METADATA = ReadyMetadata.build(
    template_id='ltx2_3_iamccs_audio_image_to_video',
    capability='audio_image_to_video',
    inputs=PUBLIC_INPUTS,
    models=MODELS,
    output_prefix='',
    requirements={'custom_nodes': ['ComfyUI-GGUF', 'ComfyUI-KJNodes', 'ComfyUI-LTXVideo', 'ComfyUI-VideoHelperSuite', 'rgthree-comfy'], 'custom_node_refs': [{'slug': 'ComfyUI-GGUF', 'source': 'git',
                       'commit': '6ea2651e7df66d7585f6ffee804b20e92fb38b8a', 'url': 'https://github.com/city96/ComfyUI-GGUF.git'}, {'slug': 'ComfyUI-KJNodes', 'source': 'git', 'commit': 'b7646ad70a7daa7aeb919ca542274758d26ba2df', 'url': 'https://github.com/kijai/ComfyUI-KJNodes.git'}, {'slug': 'ComfyUI-LTXVideo', 'source': 'git',
                       'commit': '229437c6b65796d6a7a63ae34be2bd5ba31fa543', 'url': 'https://github.com/Lightricks/ComfyUI-LTXVideo.git'}, {'slug': 'ComfyUI-VideoHelperSuite', 'source': 'git',
                       'commit': '4ee72c065db22c9d96c2427954dc69e7b908444b', 'url': 'https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite.git'}, {'slug': 'rgthree-comfy', 'source': 'git',
                       'commit': '738105af5fb14e96fbecaf406dc356e284797e8c', 'url': 'https://github.com/rgthree/rgthree-comfy.git'}]},
    provenance={'source_role': 'materialized_ready_python_template', 'smoke_resolution': '256x256x5_frames', 'source_workflow': 'workflow_corpus/custom_nodes/ltxvideo/iamccs/IAMCCS_LTX2_AU_IMG2V.json', 'approach': 'audio plus image-to-video'},
    coverage_tier='supplemental',
    ltx_best_practices=['Use the official Lightricks workflows as runtime gates where possible.', 'Patch smoke runs to fp8/fp4 model assets, tiny frame counts, and low-VRAM loaders.', 'Bypass latent spatial upscalers in smoke runs until HiddenSwitch Comfy exposes model_mmap_residency for LatentUpscaleModelManageable.', 'Keep community audio, lip-sync, and long-form workflows as ready templates until their custom node packs and service credentials are declared.'],
    comfy_configuration={'reserve_vram': 12, 'cache_none': True, 'fp8_e4m3fn_text_enc': True},
    vibecomfy_version='0.1.0',
    comfy_core={'version': '0.18.2', 'tested_at': '2026-05-20T09:19:32.302139+00:00', 'commit': 'f7b38d2eb97207cd834bcc3eb2e8b1d447b96c68', 'status': 'discovered'},
)

def build() -> VibeWorkflow:
    """Build the workflow (auto-generated)."""
    wf = new_workflow(READY_METADATA, source_path=__file__)

    # ════ SAMPLING ════
    sampler_kind = node(wf, 'KSamplerSelect', '154',
        sampler_name='lcm',
    )
    input_image = node(wf, 'LoadImage', '240',
        image='ComfyUI_00126_.png',
)
    # ════ LOADERS ════
    load_audio_243 = node(wf, 'LoadAudio', '243',
        audio='man voice 1.mp3',
    )
    seed__rgthree_ = node(wf, 'Seed (rgthree)', '290',
        widget_0=923615063061116,
        widget_1='',
        widget_2='',
        widget_3='',
    )
    text_multiline = node(wf, 'Text Multiline', '293',
        widget_0='video of a goblin talking to the camera',
    )
    unet_loader_gguf = node(wf, 'UnetLoaderGGUF', '301',
        unet_name='LTX-2-dev-Q4_K_S.gguf',
    )
    text_encoder = node(wf, 'DualCLIPLoader', '303',
        clip_name1=MODELS['gemma_clip'].filename,
        clip_name2=MODELS['ltx_2_19b_embeddings_connector_dev_bf16_cl'].filename,
        type='ltxv',
        device='default',
    )
    vaeloader_k_j = node(wf, 'VAELoaderKJ', '305',
        vae_name='LTX2_video_vae_2_bf16.safetensors',
        device='main_device',
        weight_dtype='bf16',
    )
    audio_vae = node(wf, 'LTXVAudioVAELoader', '311',
        ckpt_name='LTX23_audio_vae_bf16.safetensors',
    )
    iamccs__ltx2__lo_rastack = node(wf, 'IAMCCS_LTX2_LoRAStack', '321',
        widget_0='ltx-2-19b-distilled-lora-384.safetensors',
        widget_1=0.7,
        widget_2='ltx-2-19b-lora-camera-control-static.safetensors',
        widget_3=1,
        widget_4='no',
        widget_5=0,
    )
    load_audio_2 = node(wf, 'LoadAudio', '347',
        audio='man voice 2 LONG.mp3',
    )
    load_audio_3 = node(wf, 'LoadAudio', '376',
        audio='EdgarLetfall.mp3',
    )
    mel_band_ro_former_model_loader_377 = node(wf, 'MelBandRoFormerModelLoader', '377',
        widget_0='MelBandRoformer_fp32.safetensors',
    )
    param_float = node(wf, 'PrimitiveFloat', '382', value=8)
    load_whisper__mtb_ = node(wf, 'Load Whisper (mtb)', '405',
        widget_0='tiny',
        widget_1=True,
    )
    low_vramaudio_vaeloader = node(wf, 'LowVRAMAudioVAELoader', '411',
        ckpt_name='ltx-2.3-22b-dev-fp8.safetensors',
    )
    ltxvgemma_clipmodel_loader = node(wf, 'LTXVGemmaCLIPModelLoader', '412',
        widget_0=MODELS['gemma_clip'].filename,
        widget_1=MODELS['ltx_2_19b_distilled_checkpoint'].filename,
        widget_2=1024,
    )
    checkpoint_loader_simple_413 = node(wf, 'CheckpointLoaderSimple', '413',
        ckpt_name=MODELS['ltx_2_19b_distilled_checkpoint'].filename,
    )
    load_whisper__mtb__2 = node(wf, 'Load Whisper (mtb)', '433',
        widget_0='tiny',
        widget_1=True,
    )
    iamccsbus_group_1 = node(wf, 'IAMCCS_bus_group', '448',
        widget_0='both',
        widget_1=False,
        widget_2=True,
        widget_3='',
        widget_4='',
        widget_5=False,
        widget_7='',
        widget_8='none',
        widget_9=False,
    )
    iamccs_bus_group_2 = node(wf, 'IAMCCS_bus_group', '450',
        widget_0='groups',
        widget_1=True,
        widget_10=False,
        widget_11=False,
        widget_12=False,
        widget_2=False,
        widget_3='models',
        widget_4='',
        widget_5=False,
        widget_7='',
        widget_8='none',
    )
    iamccs__auto_link_arguments = node(wf, 'IAMCCS_AutoLinkArguments', '457',
        widget_0=False,
        widget_1=False,
        widget_10='Orange',
        widget_11='Green',
        widget_12='Gray',
        widget_13='White',
        widget_14='',
        widget_15='',
        widget_16='both',
        widget_18='',
        widget_2=False,
        widget_3=True,
        widget_4=False,
        widget_5='None',
        widget_6='',
        widget_7='TopToDown',
        widget_8='AvoidAll',
        widget_9=True,
    )
    sampled_latent = node(wf, 'SamplerCustomAdvanced', '467')
    noise = node(wf, 'RandomNoise', '178',
        control_after_generate='fixed',
        widget_0=24838260293478,
        noise_seed=seed__rgthree_.out(0),
    )
    # ════ IMAGE PREP ════
    resized_image = node(wf, 'ImageResizeKJv2', '241',
        width=720,
        height=1280,
        upscale_method='lanczos',
        keep_proportion='crop',
        pad_color='0, 0, 0',
        crop_position='top',
        divisible_by=32,
        device='cpu',
        image=input_image.out('IMAGE'),
    )
    iamccs__model_with_lo_r_a__ltx2 = node(wf, 'IAMCCS_ModelWithLoRA_LTX2', '322',
        lora=iamccs__ltx2__lo_rastack.out(0),
        model=unet_loader_gguf.out(0),
    )
    f_l__chatterbox_turbo_tts = node(wf, 'FL_ChatterboxTurboTTS', '348',
        widget_0='Hello! I am a goblin <laugh>  a real goblin. <sarcastic>  Are You a real human?',
        widget_1=0.8,
        widget_2=1000,
        widget_3=0.95,
        widget_4=1.2,
        widget_5=42,
        widget_6='fixed',
        widget_7=False,
        widget_8=True,
        audio_prompt=load_audio_2.out(0),
    )
    trim_audio_duration_366 = node(wf, 'TrimAudioDuration', '366',
        widget_0=0,
        widget_1=20,
        audio=load_audio_3.out(0),
    )
    cr_float_to_integer = node(wf, 'CR Float To Integer', '384',
        _float=param_float.out('FLOAT'),
    )
    audio_to_text__mtb_ = node(wf, 'Audio To Text (mtb)', '406',
        widget_0='auto',
        widget_1=False,
        audio=load_audio_3.out(0),
        pipeline=load_whisper__mtb_.out(0),
    )
    iamccs__ltx2__lo_rastack_model_i_o = node(wf, 'IAMCCS_LTX2_LoRAStackModelIO', '416',
        widget_0='ltx-2-19b-distilled-lora-384.safetensors',
        widget_1=1,
        widget_2='no',
        widget_3=0,
        widget_4='no',
        widget_5=0,
        model=checkpoint_loader_simple_413.out(0),
    )
    iamccs_multiswitch_3 = node(wf, 'IAMCCS_MultiSwitch', '452',
        widget_0='VAE AUDIO LOW',
        widget_1=True,
        input_01=low_vramaudio_vaeloader.out(0),
        input_02=audio_vae.out('AUDIO_VAE'),
    )
    iamccs_multiswitch_4 = node(wf, 'IAMCCS_MultiSwitch', '453',
        widget_0='VAE h',
        widget_1=True,
        input_01=checkpoint_loader_simple_413.out(2),
        input_02=vaeloader_k_j.out(0),
    )
    iamccs_multiswitch_5 = node(wf, 'IAMCCS_MultiSwitch', '454',
        widget_0='CLIP L',
        widget_1=True,
        input_01=ltxvgemma_clipmodel_loader.out(0),
        input_02=text_encoder.out('CLIP'),
    )
    iamccs__auto_link_converter = node(wf, 'IAMCCS_AutoLinkConverter', '456',
        arg=iamccs__auto_link_arguments.out(0),
    )
    preprocessed_image = node(wf, 'LTXVPreprocess', '269',
        img_compression=33,
        image=resized_image.out('IMAGE'),
    )
    # ════ OUTPUT ════
    preview_image_275 = node(wf, 'PreviewImage', '275',
        images=resized_image.out('IMAGE'),
    )
    save_audio = node(wf, 'SaveAudioMP3', '350',
        filename_prefix='audio/ComfyUI',
        quality='V0',
        audio=f_l__chatterbox_turbo_tts.out(0),
    )
    solid_mask_388 = node(wf, 'SolidMask', '388',
        widget_0=0,
        widget_1=512,
        widget_2=512,
        height=resized_image.out(2),
        width=resized_image.out(1),
    )
    easy_cleangpuused = node(wf, 'easy cleanGpuUsed', '407',
        anything=audio_to_text__mtb_.out(0),
    )
    iamccs_multiswitch_2 = node(wf, 'IAMCCS_MultiSwitch', '451',
        widget_0='input_03',
        widget_1=True,
        input_01=iamccs__ltx2__lo_rastack_model_i_o.out(0),
        input_02=iamccs__model_with_lo_r_a__ltx2.out(0),
    )
    showtext_pysssss_2 = node(wf, 'ShowText|pysssss', '373',
        widget_0=' How are you? I am from metallurgia, Elfica, a fantasy tale from our dear. Welcome to our show. And sit down and listen carefully.',
        text=easy_cleangpuused.out(0),
    )
    iamccs__ggufaccelerator = node(wf, 'IAMCCS_GGUF_accelerator', '475',
        widget_0='auto_oom_safe',
        widget_1=True,
        widget_2=True,
        widget_3=1500,
        widget_4=True,
        widget_5='all_or_nothing',
        widget_6=1024,
        model=iamccs_multiswitch_2.out(0),
    )
    f_b__qwen3_ttsvoice_clone_prompt = node(wf, 'FB_Qwen3TTSVoiceClonePrompt', '379',
        widget_0='',
        widget_1='1.7B',
        widget_2='auto',
        widget_3='fp32',
        widget_4='sage_attn',
        widget_5=True,
        widget_6=True,
        ref_audio=trim_audio_duration_366.out(0),
        ref_text=showtext_pysssss_2.out(0),
    )
    iamccs__hw_supporter = node(wf, 'IAMCCS_HwSupporter', '893',
        widget_0='auto',
        widget_1=True,
        widget_10='auto',
        widget_11=False,
        widget_12=True,
        widget_13=False,
        widget_14='overwrite',
        widget_15='(not probed)',
        widget_16='run',
        widget_17='copy',
        widget_18=True,
        widget_2='manual',
        widget_3=0,
        widget_4=1,
        widget_5=0,
        widget_6='auto',
        widget_7=False,
        widget_8='off',
        widget_9='auto',
        clip=iamccs_multiswitch_5.out(0),
        model=iamccs__ggufaccelerator.out(0),
        vae=iamccs_multiswitch_4.out(0),
    )
    # ════ TEXT CONDITIONING ════
    negative_prompt = node(wf, 'CLIPTextEncode', '165',
        text='blurry, out of focus, overexposed, underexposed, low contrast, washed out colors, excessive noise, grainy texture, poor lighting, flickering, motion blur, distorted proportions, unnatural skin tones, deformed facial features, asymmetrical face, missing facial features, extra limbs, disfigured hands, wrong hand count, artifacts around text, unreadable text on shirt or hat, incorrect lettering on cap (“PNTR”), incorrect t-shirt slogan (“JUST DO IT”), missing microphone, misplaced microphone, inconsistent perspective, camera shake, incorrect depth of field, background too sharp, background clutter, distracting reflections, harsh shadows, inconsistent lighting direction, color banding, cartoonish rendering, 3D CGI look, unrealistic materials, uncanny valley effect, incorrect ethnicity, wrong gender, exaggerated expressions, smiling, laughing, exaggerated sadness, wrong gaze direction, eyes looking at camera, mismatched lip sync, silent or muted audio, distorted voice, robotic voice, echo, background noise, off-sync audio, missing sniff sounds, incorrect dialogue, added dialogue, repetitive speech, jittery movement, awkward pauses, incorrect timing, unnatural transitions, inconsistent framing, tilted camera, missing door or shelves, missing shallow depth of field, flat lighting, inconsistent tone, cinematic oversaturation, stylized filters, or AI artifacts.',
        clip=iamccs__hw_supporter.out(1),
    )
    positive_prompt = node(wf, 'CLIPTextEncode', '169',
        text=text_multiline.out(0),
        clip=iamccs__hw_supporter.out(1),
    )
    basic_scheduler_238 = node(wf, 'BasicScheduler', '238',
        scheduler=1,
        steps=1,
        denoise=1,
        widget_1=8,
        model=iamccs__hw_supporter.out(0),
    )
    iamccs__hw_supporter_any = node(wf, 'IAMCCS_HwSupporterAny', '375',
        widget_0='low_vram',
        widget_1=True,
        widget_10=False,
        widget_11='overwrite',
        widget_12='run',
        widget_13='copy',
        widget_14='copy',
        widget_15=True,
        widget_2='auto_used_plus',
        widget_3=1.25,
        widget_4=1,
        widget_5=0,
        widget_6='auto',
        widget_7='auto',
        widget_8=True,
        widget_9=True,
        input=f_b__qwen3_ttsvoice_clone_prompt.out(0),
    )
    showtext_pysssss_3 = node(wf, 'ShowText|pysssss', '974',
        text=iamccs__hw_supporter.out(3),
    )
    conditioning = node(wf, 'LTXVConditioning', '164',
        frame_rate=param_float.out('FLOAT'),
        negative=negative_prompt.out('CONDITIONING'),
        positive=positive_prompt.out('CONDITIONING'),
    )
    f_b__qwen3_ttsvoice_clone = node(wf, 'FB_Qwen3TTSVoiceClone', '374',
        widget_0='this is only a test! check it out!',
        widget_1='1.7B',
        widget_10=20,
        widget_11=1,
        widget_12=1.05,
        widget_13=True,
        widget_14='auto',
        widget_15=True,
        widget_2='auto',
        widget_3='bf16',
        widget_4='Auto',
        widget_5='',
        widget_6=663647919912928,
        widget_7='fixed',
        widget_8=2048,
        widget_9=0.8,
        ref_audio=trim_audio_duration_366.out(0),
        ref_text=showtext_pysssss_2.out(0),
        voice_clone_prompt=iamccs__hw_supporter_any.out(0),
    )
    cfg_guider = node(wf, 'CFGGuider', '153',
        cfg=2.5,
        model=iamccs__hw_supporter.out(0),
        negative=conditioning.out('NEGATIVE'),
        positive=conditioning.out('POSITIVE'),
    )
    iamccs__multi_switch_5 = node(wf, 'IAMCCS_MultiSwitch', '441',
        widget_0='input_6',
        widget_1=True,
        input_01=load_audio_243.out(0),
        input_03=f_l__chatterbox_turbo_tts.out(0),
        input_05=f_b__qwen3_ttsvoice_clone.out(0),
    )
    audio_duration__mtb_ = node(wf, 'Audio Duration (mtb)', '363',
        audio=iamccs__multi_switch_5.out(0),
    )
    mel_band_ro_former_sampler_365 = node(wf, 'MelBandRoFormerSampler', '365',
        audio=iamccs__multi_switch_5.out(0),
        model=mel_band_ro_former_model_loader_377.out(0),
    )
    set_node_362 = node(wf, 'SetNode', '362',
        widget_0='audio_vocals',
        AUDIO=mel_band_ro_former_sampler_365.out(0),
    )
    mathexpression_pysssss = node(wf, 'MathExpression|pysssss', '364',
        widget_0='((a*0.001)*b)',
        a=audio_duration__mtb_.out(0),
        b=cr_float_to_integer.out(0),
    )
    audio_to_text__mtb__2 = node(wf, 'Audio To Text (mtb)', '409',
        widget_0='auto',
        widget_1=False,
        audio=mel_band_ro_former_sampler_365.out(0),
        pipeline=load_whisper__mtb__2.out(0),
    )
    # ════ LATENT ════
    empty_video_latent = node(wf, 'EmptyLTXVLatentVideo', '162',
        batch_size=1,
        
        
        width=resized_image.out(1),
        height=resized_image.out(2),
        length=mathexpression_pysssss.out(0),
    )
    preview_audio_380 = node(wf, 'PreviewAudio', '380',
        audio=set_node_362.out(0),
    )
    ltxvaudio_vaeencode = node(wf, 'LTXVAudioVAEEncode', '387',
        audio=set_node_362.out(0),
        audio_vae=iamccs_multiswitch_3.out(0),
    )
    easy_cleangpuused_2 = node(wf, 'easy cleanGpuUsed', '410',
        anything=audio_to_text__mtb__2.out(0),
    )
    ltxvimg_to_video_inplace = node(wf, 'LTXVImgToVideoInplace', '239',
        widget_0=0.8,
        widget_1=False,
        image=preprocessed_image.out('OUTPUT_IMAGE'),
        latent=empty_video_latent.out('LATENT'),
        vae=iamccs__hw_supporter.out(2),
    )
    showtext_pysssss = node(wf, 'ShowText|pysssss', '370',
        widget_0=" Hey, how are you? Well, I suppose you already know me, but wait a moment. Are human? I mean, I am not. So I've been thinking about it all day. Believe me.",
        text=easy_cleangpuused_2.out(0),
    )
    set_latent_noise_mask_389 = node(wf, 'SetLatentNoiseMask', '389',
        mask=solid_mask_388.out(0),
        samples=ltxvaudio_vaeencode.out(0),
    )
    av_latent = node(wf, 'LTXVConcatAVLatent', '166',
        audio_latent=set_latent_noise_mask_389.out(0),
        video_latent=ltxvimg_to_video_inplace.out(0),
    )
    iamccs__sampler_advanced_version1 = node(wf, 'IAMCCS_SamplerAdvancedVersion1', '474',
        widget_0=True,
        widget_1=True,
        guider=cfg_guider.out('GUIDER'),
        latent_image=av_latent.out('LATENT'),
        noise=noise.out('NOISE'),
        sampler=sampler_kind.out('SAMPLER'),
        sigmas=basic_scheduler_238.out(0),
    )
    av_latent_separated = node(wf, 'LTXVSeparateAVLatent', '245',
        av_latent=iamccs__sampler_advanced_version1.out(0),
    )
    # ════ DECODE ════
    iamccs__vaedecode_tiled_safe = node(wf, 'IAMCCS_VAEDecodeTiledSafe', '234',
        widget_0=True,
        widget_1='manual',
        widget_10='copy',
        widget_2=512,
        widget_3=32,
        widget_4=64,
        widget_5=32,
        widget_6=True,
        widget_7='overwrite',
        widget_8='run',
        widget_9='copy',
        samples=av_latent_separated.out('VIDEO_LATENT'),
        vae=iamccs__hw_supporter.out(2),
    )
    video_output = node(wf, 'VHS_VideoCombine', '190',
        audio=iamccs__multi_switch_5.out(0),
        images=iamccs__vaedecode_tiled_safe.out(0),
    )

    return finalize(
        wf,
        PUBLIC_INPUTS,
        READY_METADATA,
        output_node='',
        source_path=__file__,
    )

