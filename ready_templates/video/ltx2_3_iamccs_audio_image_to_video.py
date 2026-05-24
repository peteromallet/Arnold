# vibecomfy: generated — converted by tools/convert_ready_templates.py
# Edits will be overwritten on regeneration. Add a `# vibecomfy: manual`
# marker on the first line if hand-editing is required.
"""Auto-generated ready_template — see tools/convert_ready_templates.py."""
from __future__ import annotations

from vibecomfy.workflow import VibeWorkflow, WorkflowSource
from vibecomfy.registry.ready_template import apply_ready_template_policy


READY_METADATA = {'model_assets': [],
 'unbound_inputs': {'seed': 4446},
 'ready_template': 'video/ltx2_3_iamccs_audio_image_to_video',
 'workflow_template': 'ltx2_3_iamccs_audio_image_to_video',
 'capability': 'audio_image_to_video',
 'source_role': 'materialized_ready_python_template',
 'source_workflow': 'workflow_corpus/custom_nodes/ltxvideo/iamccs/IAMCCS_LTX2_AU_IMG2V.json',
 'coverage_tier': 'supplemental',
 'approach': 'audio plus image-to-video',
 'runtime_note': None,
 'discord_signal': None,
 'smoke_resolution': '256x256x5_frames',
 'ltx_best_practices': ['Use the official Lightricks workflows as runtime gates where possible.',
                        'Patch smoke runs to fp8/fp4 model assets, tiny frame counts, and low-VRAM loaders.',
                        'Bypass latent spatial upscalers in smoke runs until HiddenSwitch Comfy exposes '
                        'model_mmap_residency for LatentUpscaleModelManageable.',
                        'Keep community audio, lip-sync, and long-form workflows as ready templates until '
                        'their custom node packs and service credentials are declared.'],
 'comfy_configuration': {'reserve_vram': 12, 'cache_none': True, 'fp8_e4m3fn_text_enc': True}}

READY_REQUIREMENTS = {'models': [],
 'custom_nodes': ['ComfyUI-GGUF', 'ComfyUI-KJNodes', 'ComfyUI-LTXVideo', 'ComfyUI-VideoHelperSuite']}


def build() -> VibeWorkflow:
    """Build the workflow (auto-generated)."""
    wf = VibeWorkflow(
        READY_METADATA["ready_template"],
        WorkflowSource(
            id=READY_METADATA["ready_template"],
            path=__file__,
            source_type="ready_template",
        ),
    )

    ksamplerselect = _node(wf, 'KSamplerSelect', '154',
        sampler_name='lcm',
    )
    loadimage = _node(wf, 'LoadImage', '240',
        image='ComfyUI_00126_.png',
        widget_1='image',
    )
    loadaudio = _node(wf, 'LoadAudio', '243',
        audio='man voice 1.mp3',
    )
    seed__rgthree_ = _node(wf, 'Seed (rgthree)', '290',
        widget_0=923615063061116,
        widget_1='',
        widget_2='',
        widget_3='',
    )
    text_multiline = _node(wf, 'Text Multiline', '293',
        widget_0='video of a goblin talking to the camera',
    )
    unetloadergguf = _node(wf, 'UnetLoaderGGUF', '301',
        widget_0='LTX-2-dev-Q4_K_S.gguf',
    )
    dualcliploader = _node(wf, 'DualCLIPLoader', '303',
        clip_name1='gemma_3_12B_it_fp8_e4m3fn.safetensors',
        clip_name2='ltx-2-19b-embeddings_connector_dev_bf16.safetensors',
        type='ltxv',
        device='default',
    )
    vaeloaderkj = _node(wf, 'VAELoaderKJ', '305',
        widget_0='LTX2_video_vae_2_bf16.safetensors',
        widget_1='main_device',
        widget_2='bf16',
    )
    vaeloaderkj_2 = _node(wf, 'LTXVAudioVAELoader', '311',
        ckpt_name='LTX23_audio_vae_bf16.safetensors',
    )
    iamccs_ltx2_lorastack = _node(wf, 'IAMCCS_LTX2_LoRAStack', '321',
        widget_0='ltx-2-19b-distilled-lora-384.safetensors',
        widget_1=0.7,
        widget_2='ltx-2-19b-lora-camera-control-static.safetensors',
        widget_3=1,
        widget_4='no',
        widget_5=0,
    )
    loadaudio_2 = _node(wf, 'LoadAudio', '347',
        audio='man voice 2 LONG.mp3',
    )
    loadaudio_3 = _node(wf, 'LoadAudio', '376',
        audio='EdgarLetfall.mp3',
    )
    melbandroformermodelloader = _node(wf, 'MelBandRoFormerModelLoader', '377',
        widget_0='MelBandRoformer_fp32.safetensors',
    )
    primitivefloat = _node(wf, 'PrimitiveFloat', '382',
        value=8,
    )
    load_whisper__mtb_ = _node(wf, 'Load Whisper (mtb)', '405',
        widget_0='tiny',
        widget_1=True,
    )
    lowvramaudiovaeloader = _node(wf, 'LowVRAMAudioVAELoader', '411',
        ckpt_name='ltx-2.3-22b-dev-fp8.safetensors',
    )
    ltxvgemmaclipmodelloader = _node(wf, 'LTXVGemmaCLIPModelLoader', '412',
        widget_0='gemma_3_12B_it_fp8_e4m3fn.safetensors',
        widget_1='ltx-2-19b-distilled.safetensors',
        widget_2=1024,
    )
    checkpointloadersimple = _node(wf, 'CheckpointLoaderSimple', '413',
        ckpt_name='ltx-2-19b-distilled.safetensors',
    )
    load_whisper__mtb__2 = _node(wf, 'Load Whisper (mtb)', '433',
        widget_0='tiny',
        widget_1=True,
    )
    iamccs_bus_group = _node(wf, 'IAMCCS_bus_group', '448',
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
    iamccs_bus_group_2 = _node(wf, 'IAMCCS_bus_group', '450',
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
    iamccs_autolinkarguments = _node(wf, 'IAMCCS_AutoLinkArguments', '457',
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
    samplercustomadvanced = _node(wf, 'SamplerCustomAdvanced', '467')
    randomnoise = _node(wf, 'RandomNoise', '178',
        control_after_generate='fixed',
        widget_0=24838260293478,
        noise_seed=seed__rgthree_.out(0),
    )
    imageresizekjv2 = _node(wf, 'ImageResizeKJv2', '241',
        widget_0=720,
        widget_1=1280,
        widget_2='lanczos',
        widget_3='crop',
        widget_4='0, 0, 0',
        widget_5='top',
        widget_6=32,
        widget_7='cpu',
        image=loadimage.out(0),
    )
    iamccs_modelwithlora_ltx2 = _node(wf, 'IAMCCS_ModelWithLoRA_LTX2', '322',
        lora=iamccs_ltx2_lorastack.out(0),
        model=unetloadergguf.out(0),
    )
    fl_chatterboxturbotts = _node(wf, 'FL_ChatterboxTurboTTS', '348',
        widget_0='Hello! I am a goblin <laugh>  a real goblin. <sarcastic>  Are You a real human?',
        widget_1=0.8,
        widget_2=1000,
        widget_3=0.95,
        widget_4=1.2,
        widget_5=42,
        widget_6='fixed',
        widget_7=False,
        widget_8=True,
        audio_prompt=loadaudio_2.out(0),
    )
    trimaudioduration = _node(wf, 'TrimAudioDuration', '366',
        widget_0=0,
        widget_1=20,
        audio=loadaudio_3.out(0),
    )
    cr_float_to_integer = _node(wf, 'CR Float To Integer', '384',
        _float=primitivefloat.out(0),
    )
    audio_to_text__mtb_ = _node(wf, 'Audio To Text (mtb)', '406',
        widget_0='auto',
        widget_1=False,
        audio=loadaudio_3.out(0),
        pipeline=load_whisper__mtb_.out(0),
    )
    iamccs_ltx2_lorastackmodelio = _node(wf, 'IAMCCS_LTX2_LoRAStackModelIO', '416',
        widget_0='ltx-2-19b-distilled-lora-384.safetensors',
        widget_1=1,
        widget_2='no',
        widget_3=0,
        widget_4='no',
        widget_5=0,
        model=checkpointloadersimple.out(0),
    )
    iamccs_multiswitch_3 = _node(wf, 'IAMCCS_MultiSwitch', '452',
        widget_0='VAE AUDIO LOW',
        widget_1=True,
        input_01=lowvramaudiovaeloader.out(0),
        input_02=vaeloaderkj_2.out(0),
    )
    iamccs_multiswitch_4 = _node(wf, 'IAMCCS_MultiSwitch', '453',
        widget_0='VAE h',
        widget_1=True,
        input_01=checkpointloadersimple.out(2),
        input_02=vaeloaderkj.out(0),
    )
    iamccs_multiswitch_5 = _node(wf, 'IAMCCS_MultiSwitch', '454',
        widget_0='CLIP L',
        widget_1=True,
        input_01=ltxvgemmaclipmodelloader.out(0),
        input_02=dualcliploader.out(0),
    )
    iamccs_autolinkconverter = _node(wf, 'IAMCCS_AutoLinkConverter', '456',
        arg=iamccs_autolinkarguments.out(0),
    )
    ltxvpreprocess = _node(wf, 'LTXVPreprocess', '269',
        widget_0=33,
        image=imageresizekjv2.out(0),
    )
    previewimage = _node(wf, 'PreviewImage', '275',
        images=imageresizekjv2.out(0),
    )
    saveaudiomp3 = _node(wf, 'SaveAudioMP3', '350',
        filename_prefix='audio/ComfyUI',
        quality='V0',
        audio=fl_chatterboxturbotts.out(0),
    )
    solidmask = _node(wf, 'SolidMask', '388',
        widget_0=0,
        widget_1=512,
        widget_2=512,
        height=imageresizekjv2.out(2),
        width=imageresizekjv2.out(1),
    )
    easy_cleangpuused = _node(wf, 'easy cleanGpuUsed', '407',
        anything=audio_to_text__mtb_.out(0),
    )
    iamccs_multiswitch_2 = _node(wf, 'IAMCCS_MultiSwitch', '451',
        widget_0='input_03',
        widget_1=True,
        input_01=iamccs_ltx2_lorastackmodelio.out(0),
        input_02=iamccs_modelwithlora_ltx2.out(0),
    )
    showtext_pysssss_2 = _node(wf, 'ShowText|pysssss', '373',
        widget_0=' How are you? I am from metallurgia, Elfica, a fantasy tale from our dear. Welcome to our show. And sit down and listen carefully.',
        text=easy_cleangpuused.out(0),
    )
    iamccs_gguf_accelerator = _node(wf, 'IAMCCS_GGUF_accelerator', '475',
        widget_0='auto_oom_safe',
        widget_1=True,
        widget_2=True,
        widget_3=1500,
        widget_4=True,
        widget_5='all_or_nothing',
        widget_6=1024,
        model=iamccs_multiswitch_2.out(0),
    )
    fb_qwen3ttsvoicecloneprompt = _node(wf, 'FB_Qwen3TTSVoiceClonePrompt', '379',
        widget_0='',
        widget_1='1.7B',
        widget_2='auto',
        widget_3='fp32',
        widget_4='sage_attn',
        widget_5=True,
        widget_6=True,
        ref_audio=trimaudioduration.out(0),
        ref_text=showtext_pysssss_2.out(0),
    )
    iamccs_hwsupporter = _node(wf, 'IAMCCS_HwSupporter', '893',
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
        model=iamccs_gguf_accelerator.out(0),
        vae=iamccs_multiswitch_4.out(0),
    )
    cliptextencode = _node(wf, 'CLIPTextEncode', '165',
        text='blurry, out of focus, overexposed, underexposed, low contrast, washed out colors, excessive noise, grainy texture, poor lighting, flickering, motion blur, distorted proportions, unnatural skin tones, deformed facial features, asymmetrical face, missing facial features, extra limbs, disfigured hands, wrong hand count, artifacts around text, unreadable text on shirt or hat, incorrect lettering on cap (“PNTR”), incorrect t-shirt slogan (“JUST DO IT”), missing microphone, misplaced microphone, inconsistent perspective, camera shake, incorrect depth of field, background too sharp, background clutter, distracting reflections, harsh shadows, inconsistent lighting direction, color banding, cartoonish rendering, 3D CGI look, unrealistic materials, uncanny valley effect, incorrect ethnicity, wrong gender, exaggerated expressions, smiling, laughing, exaggerated sadness, wrong gaze direction, eyes looking at camera, mismatched lip sync, silent or muted audio, distorted voice, robotic voice, echo, background noise, off-sync audio, missing sniff sounds, incorrect dialogue, added dialogue, repetitive speech, jittery movement, awkward pauses, incorrect timing, unnatural transitions, inconsistent framing, tilted camera, missing door or shelves, missing shallow depth of field, flat lighting, inconsistent tone, cinematic oversaturation, stylized filters, or AI artifacts.',
        clip=iamccs_hwsupporter.out(1),
    )
    negative = _node(wf, 'CLIPTextEncode', '169',
        widget_0='',
        text=text_multiline.out(0),
        clip=iamccs_hwsupporter.out(1),
    )
    basicscheduler = _node(wf, 'BasicScheduler', '238',
        scheduler=1,
        steps=1,
        denoise=1,
        widget_1=8,
        model=iamccs_hwsupporter.out(0),
    )
    iamccs_hwsupporterany = _node(wf, 'IAMCCS_HwSupporterAny', '375',
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
        input=fb_qwen3ttsvoicecloneprompt.out(0),
    )
    showtext_pysssss_3 = _node(wf, 'ShowText|pysssss', '974',
        text=iamccs_hwsupporter.out(3),
    )
    ltxvconditioning = _node(wf, 'LTXVConditioning', '164',
        widget_0=8,
        frame_rate=primitivefloat.out(0),
        negative=cliptextencode.out(0),
        positive=negative.out(0),
    )
    fb_qwen3ttsvoiceclone = _node(wf, 'FB_Qwen3TTSVoiceClone', '374',
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
        ref_audio=trimaudioduration.out(0),
        ref_text=showtext_pysssss_2.out(0),
        voice_clone_prompt=iamccs_hwsupporterany.out(0),
    )
    cfgguider = _node(wf, 'CFGGuider', '153',
        cfg=2.5,
        model=iamccs_hwsupporter.out(0),
        negative=ltxvconditioning.out(1),
        positive=ltxvconditioning.out(0),
    )
    iamccs_multiswitch = _node(wf, 'IAMCCS_MultiSwitch', '441',
        widget_0='input_6',
        widget_1=True,
        input_01=loadaudio.out(0),
        input_03=fl_chatterboxturbotts.out(0),
        input_05=fb_qwen3ttsvoiceclone.out(0),
    )
    audio_duration__mtb_ = _node(wf, 'Audio Duration (mtb)', '363',
        audio=iamccs_multiswitch.out(0),
    )
    melbandroformersampler = _node(wf, 'MelBandRoFormerSampler', '365',
        audio=iamccs_multiswitch.out(0),
        model=melbandroformermodelloader.out(0),
    )
    setnode = _node(wf, 'SetNode', '362',
        widget_0='audio_vocals',
        AUDIO=melbandroformersampler.out(0),
    )
    mathexpression_pysssss = _node(wf, 'MathExpression|pysssss', '364',
        widget_0='((a*0.001)*b)',
        a=audio_duration__mtb_.out(0),
        b=cr_float_to_integer.out(0),
    )
    audio_to_text__mtb__2 = _node(wf, 'Audio To Text (mtb)', '409',
        widget_0='auto',
        widget_1=False,
        audio=melbandroformersampler.out(0),
        pipeline=load_whisper__mtb__2.out(0),
    )
    emptyltxvlatentvideo = _node(wf, 'EmptyLTXVLatentVideo', '162',
        batch_size=1,
        widget_0=256,
        widget_1=256,
        widget_2=5,
        width=imageresizekjv2.out(1),
        height=imageresizekjv2.out(2),
        length=mathexpression_pysssss.out(0),
    )
    previewaudio = _node(wf, 'PreviewAudio', '380',
        audio=setnode.out(0),
    )
    ltxvaudiovaeencode = _node(wf, 'LTXVAudioVAEEncode', '387',
        audio=setnode.out(0),
        audio_vae=iamccs_multiswitch_3.out(0),
    )
    easy_cleangpuused_2 = _node(wf, 'easy cleanGpuUsed', '410',
        anything=audio_to_text__mtb__2.out(0),
    )
    ltxvimgtovideoinplace = _node(wf, 'LTXVImgToVideoInplace', '239',
        widget_0=0.8,
        widget_1=False,
        image=ltxvpreprocess.out(0),
        latent=emptyltxvlatentvideo.out(0),
        vae=iamccs_hwsupporter.out(2),
    )
    showtext_pysssss = _node(wf, 'ShowText|pysssss', '370',
        widget_0=" Hey, how are you? Well, I suppose you already know me, but wait a moment. Are human? I mean, I am not. So I've been thinking about it all day. Believe me.",
        text=easy_cleangpuused_2.out(0),
    )
    setlatentnoisemask = _node(wf, 'SetLatentNoiseMask', '389',
        mask=solidmask.out(0),
        samples=ltxvaudiovaeencode.out(0),
    )
    ltxvconcatavlatent = _node(wf, 'LTXVConcatAVLatent', '166',
        audio_latent=setlatentnoisemask.out(0),
        video_latent=ltxvimgtovideoinplace.out(0),
    )
    iamccs_sampleradvancedversion1 = _node(wf, 'IAMCCS_SamplerAdvancedVersion1', '474',
        widget_0=True,
        widget_1=True,
        guider=cfgguider.out(0),
        latent_image=ltxvconcatavlatent.out(0),
        noise=randomnoise.out(0),
        sampler=ksamplerselect.out(0),
        sigmas=basicscheduler.out(0),
    )
    ltxvseparateavlatent = _node(wf, 'LTXVSeparateAVLatent', '245',
        av_latent=iamccs_sampleradvancedversion1.out(0),
    )
    iamccs_vaedecodetiledsafe = _node(wf, 'IAMCCS_VAEDecodeTiledSafe', '234',
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
        samples=ltxvseparateavlatent.out(0),
        vae=iamccs_hwsupporter.out(2),
    )
    vhs_videocombine = _node(wf, 'VHS_VideoCombine', '190',
        audio=iamccs_multiswitch.out(0),
        images=iamccs_vaedecodetiledsafe.out(0),
    )

    wf.finalize_metadata()
    apply_ready_template_policy(wf, READY_METADATA, source_path=__file__, requirements=READY_REQUIREMENTS)
    return wf


def _node(wf: VibeWorkflow, class_type: str, _id: str, _extras: dict | None = None, **kwargs):
    """Create a node, preserving the original node id from the source workflow.

    `_extras` carries kwargs whose names are not valid Python identifiers
    (e.g. "resize_type.multiple") which Python disallows as kwarg syntax.
    They are applied to the new node post-construction.
    """
    from vibecomfy.handles import Handle
    builder = wf.node(class_type, **kwargs)
    if _extras:
        for key, value in _extras.items():
            if isinstance(value, Handle):
                wf.connect(value, f"{builder.node.id}.{key}")
            else:
                builder.node.inputs[key] = value
    if builder.node.id != _id:
        old_id = builder.node.id
        node = wf.nodes.pop(old_id)
        node.id = _id
        wf.nodes[_id] = node
        for edge in wf.edges:
            if edge.to_node == old_id:
                edge.to_node = _id
            if edge.from_node == old_id:
                edge.from_node = _id
    return builder
