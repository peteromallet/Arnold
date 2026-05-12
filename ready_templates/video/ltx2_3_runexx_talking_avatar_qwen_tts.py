# vibecomfy: generated — converted by tools/convert_ready_templates.py
# Edits will be overwritten on regeneration. Add a `# vibecomfy: manual`
# marker on the first line if hand-editing is required.
"""Auto-generated ready_template — see tools/convert_ready_templates.py."""
from __future__ import annotations

from vibecomfy.workflow import VibeWorkflow, WorkflowSource
from vibecomfy.registry.ready_template import apply_ready_template_policy


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
                        'Keep community audio, lip-sync, and long-form workflows as ready templates until '
                        'their custom node packs and service credentials are declared.'],
 'comfy_configuration': {'reserve_vram': 12, 'cache_none': True, 'fp8_e4m3fn_text_enc': True}}

READY_REQUIREMENTS = {'models': [],
 'custom_nodes': ['ComfyUI-GGUF',
                  'ComfyUI-KJNodes',
                  'ComfyUI-LTXVideo',
                  'ComfyUI-QwenTTS',
                  'ComfyUI-VideoHelperSuite',
                  'rgthree-comfy']}


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

    getnode = _node(wf, 'GetNode', '413',
        widget_0='vae',
    )
    loadimage = _node(wf, 'LoadImage', '444',
        image='17745317855d08.png',
        widget_1='image',
    )
    vaeloader = _node(wf, 'VAELoader', '1559',
        vae_name='LTX23_video_vae_bf16.safetensors',
    )
    latentupscalemodelloader = _node(wf, 'LatentUpscaleModelLoader', '1561',
        widget_0='ltx-2.3-spatial-upscaler-x2-1.1.safetensors',
    )
    dualcliploader = _node(wf, 'DualCLIPLoader', '1562',
        clip_name1='gemma_3_12B_it_fp4_mixed.safetensors',
        clip_name2='ltx-2.3_text_projection_bf16.safetensors',
        type='ltxv',
        device='default',
    )
    vaeloaderkj = _node(wf, 'LTXVAudioVAELoader', '1567',
        ckpt_name='LTX23_audio_vae_bf16.safetensors',
    )
    vaeloader_2 = _node(wf, 'VAELoader', '1569',
        vae_name='taeltx2_3.safetensors',
    )
    unetloader = _node(wf, 'UNETLoader', '1570',
        unet_name='ltx-2.3-22b-distilled_transformer_only_fp8_scaled.safetensors',
        weight_dtype='default',
    )
    unetloadergguf = _node(wf, 'UnetLoaderGGUF', '1571',
        widget_0='LTXvideo\\LTX-2\\quantstack\\LTX-2.3-distilled-Q4_K_S.gguf',
    )
    dualcliploadergguf = _node(wf, 'DualCLIPLoaderGGUF', '1573',
        widget_0='gemma-3-12b-it-Q2_K.gguf',
        widget_1='ltx-2.3_text_projection_bf16.safetensors',
        widget_2='sdxl',
    )
    intconstant = _node(wf, 'INTConstant', '1583',
        widget_0=10,
    )
    primitivefloat = _node(wf, 'PrimitiveFloat', '1586',
        value=8,
    )
    intconstant_2 = _node(wf, 'INTConstant', '1591',
        widget_0=960,
    )
    intconstant_3 = _node(wf, 'INTConstant', '1606',
        widget_0=544,
    )
    getnode_2 = _node(wf, 'GetNode', '1619',
        widget_0='clip',
    )
    getnode_3 = _node(wf, 'GetNode', '1622',
        widget_0='clip',
    )
    primitivestringmultiline = _node(wf, 'PrimitiveStringMultiline', '1624',
        value="A video from a TV broadcast with a male and a female news achor. They both stay in frame all the time.\n\nThe dialog from the male and female is as follows:\n\nSpaker_1 is the woman, and Speaker_2 is the man.\n\n[speaker_1][confused]: This is awkward! I guess the prompter ran out of ideas, and put us in this odd situation.\n[speaker_2][embarrassed] : But hey,  just because we are here, in a new video, doesn't mean our voices change. \n[speaker_1][excited]: Aber ich möchte mit dir schlafen.\n[speaker_2][happy]: I still have no idea what she said! Might be for the best [laughing]\n\nThe dialog with perfect lip-sync to the audio\n\n\nThey both smile at the end.\n\n\n",
    )
    getnode_4 = _node(wf, 'GetNode', '1628',
        widget_0='width',
    )
    getnode_5 = _node(wf, 'GetNode', '1629',
        widget_0='height',
    )
    getnode_6 = _node(wf, 'GetNode', '1635',
        widget_0='frames',
    )
    getnode_7 = _node(wf, 'GetNode', '1636',
        widget_0='fps',
    )
    getnode_8 = _node(wf, 'GetNode', '1784',
        widget_0='audio_tts',
    )
    getnode_9 = _node(wf, 'GetNode', '1807',
        widget_0='height_downscaled',
    )
    getnode_10 = _node(wf, 'GetNode', '1808',
        widget_0='width_downscaled',
    )
    getnode_11 = _node(wf, 'GetNode', '1809',
        widget_0='ref_image',
    )
    getnode_12 = _node(wf, 'GetNode', '1814',
        widget_0='vae',
    )
    getnode_13 = _node(wf, 'GetNode', '1815',
        widget_0='vae_audio',
    )
    getnode_14 = _node(wf, 'GetNode', '1816',
        widget_0='vae',
    )
    getnode_15 = _node(wf, 'GetNode', '1817',
        widget_0='upscale_model',
    )
    getnode_16 = _node(wf, 'GetNode', '1820',
        widget_0='negative',
    )
    getnode_17 = _node(wf, 'GetNode', '1821',
        widget_0='positive',
    )
    getnode_18 = _node(wf, 'GetNode', '1822',
        widget_0='fps',
    )
    getnode_19 = _node(wf, 'GetNode', '1823',
        widget_0='t2v_mode',
    )
    getnode_20 = _node(wf, 'GetNode', '1824',
        widget_0='ref_image',
    )
    getnode_21 = _node(wf, 'GetNode', '1828',
        widget_0='model',
    )
    getnode_22 = _node(wf, 'GetNode', '1829',
        widget_0='negative',
    )
    getnode_23 = _node(wf, 'GetNode', '1830',
        widget_0='positive',
    )
    getnode_24 = _node(wf, 'GetNode', '1831',
        widget_0='model_with_lora',
    )
    randomnoise = _node(wf, 'RandomNoise', '1832',
        noise_seed=420,
        control_after_generate='fixed',
    )
    getnode_25 = _node(wf, 'GetNode', '1833',
        widget_0='vae_tiny',
    )
    getnode_26 = _node(wf, 'GetNode', '1834',
        widget_0='model_with_lora',
    )
    getnode_27 = _node(wf, 'GetNode', '1835',
        widget_0='model',
    )
    getnode_28 = _node(wf, 'GetNode', '1841',
        widget_0='model',
    )
    randomnoise_2 = _node(wf, 'RandomNoise', '1842',
        noise_seed=42,
        control_after_generate='fixed',
    )
    getnode_29 = _node(wf, 'GetNode', '1843',
        widget_0='negative',
    )
    manualsigmas = _node(wf, 'ManualSigmas', '1851',
        widget_0='0.85, 0.7250, 0.4219, 0.0',
    )
    ksamplerselect = _node(wf, 'KSamplerSelect', '1852',
        sampler_name='euler_cfg_pp',
    )
    ksamplerselect_2 = _node(wf, 'KSamplerSelect', '1853',
        sampler_name='euler_ancestral_cfg_pp',
    )
    getnode_30 = _node(wf, 'GetNode', '1855',
        widget_0='latent',
    )
    manualsigmas_2 = _node(wf, 'ManualSigmas', '1857',
        widget_0='1.0, 0.99375, 0.9875, 0.98125, 0.975, 0.909375, 0.725, 0.421875, 0.0',
    )
    primitiveboolean = _node(wf, 'PrimitiveBoolean', '1862',
        value=False,
    )
    reroute = _node(wf, 'Reroute', '1865')
    getnode_31 = _node(wf, 'GetNode', '1878',
        widget_0='model',
    )
    getnode_32 = _node(wf, 'GetNode', '1887',
        widget_0='height',
    )
    getnode_33 = _node(wf, 'GetNode', '1888',
        widget_0='width',
    )
    getnode_34 = _node(wf, 'GetNode', '1889',
        widget_0='vae_audio',
    )
    getnode_35 = _node(wf, 'GetNode', '1894',
        widget_0='latent_custom_audio',
    )
    getnode_36 = _node(wf, 'GetNode', '1898',
        widget_0='fps',
    )
    primitiveboolean_2 = _node(wf, 'PrimitiveBoolean', '1929',
        value=True,
    )
    getnode_37 = _node(wf, 'GetNode', '1931',
        widget_0='enhance_prompt',
    )
    getnode_38 = _node(wf, 'GetNode', '1935',
        widget_0='t2v_mode',
    )
    melbandroformermodelloader = _node(wf, 'MelBandRoFormerModelLoader', '1937',
        widget_0='MelBandRoformer\\MelBandRoformer_fp16.safetensors',
    )
    primitivestringmultiline_2 = _node(wf, 'PrimitiveStringMultiline', '1938',
        value='',
    )
    loadaudio = _node(wf, 'LoadAudio', '1941',
        audio='d1b26d5a32db420183fa17af9c699278.mp3',
    )
    primitivestringmultiline_3 = _node(wf, 'PrimitiveStringMultiline', '1942',
        value='So what if you just want to prompt. Text to video works fine as well. Go generate some while I enjoy my coffee. ',
    )
    emptyltxvlatentvideo = _node(wf, 'EmptyLTXVLatentVideo', '344',
        batch_size=1,
        widget_0=256,
        widget_1=256,
        widget_2=5,
        width=getnode_10.out(0),
        height=getnode_9.out(0),
        length=getnode_6.out(0),
    )
    imageresizekjv2 = _node(wf, 'ImageResizeKJv2', '445',
        widget_0=960,
        widget_1=544,
        widget_2='lanczos',
        widget_3='crop',
        widget_4='0, 0, 0',
        widget_5='center',
        widget_6=2,
        widget_7='cpu',
        height=getnode_5.out(0),
        image=loadimage.out(0),
        width=getnode_4.out(0),
    )
    ltxvpreprocess = _node(wf, 'LTXVPreprocess', '446',
        widget_0=18,
        image=getnode_11.out(0),
    )
    setnode_4 = _node(wf, 'SetNode', '1555',
        widget_0='upscale_model',
        LATENT_UPSCALE_MODEL=latentupscalemodelloader.out(0),
    )
    setnode_5 = _node(wf, 'SetNode', '1556',
        widget_0='vae_audio',
        VAE=vaeloaderkj.out(0),
    )
    setnode_6 = _node(wf, 'SetNode', '1557',
        widget_0='vae',
        VAE=vaeloader.out(0),
    )
    setnode_7 = _node(wf, 'SetNode', '1558',
        widget_0='clip',
        CLIP=dualcliploader.out(0),
    )
    loraloadermodelonly = _node(wf, 'LoraLoaderModelOnly', '1560',
        lora_name='LTX\\LTX-2\\ltx-2.3-22b-distilled-lora-384.safetensors',
        strength_model=0.6,
        model=unetloader.out(0),
    )
    setnode_8 = _node(wf, 'SetNode', '1568',
        widget_0='vae_tiny',
        VAE=vaeloader_2.out(0),
    )
    setnode_9 = _node(wf, 'SetNode', '1575',
        widget_0='height',
        INT=intconstant_2.out(0),
    )
    setnode_10 = _node(wf, 'SetNode', '1576',
        widget_0='width',
        INT=intconstant_3.out(0),
    )
    setnode_11 = _node(wf, 'SetNode', '1577',
        widget_0='fps',
        FLOAT=primitivefloat.out(0),
    )
    cliptextencode_2 = _node(wf, 'CLIPTextEncode', '1626',
        text='text, subtitles, logo, still image, still video, no motion, static, frozen, blurry, low quality, distorted, bad anatomy, oversaturated, pixelated, low resolution, grainy, compression artifacts, jpeg artifacts, glitches, watermark, signature, copyright,  distortedsound, saturated sound, loud sound , deformed facial features, asymmetrical face, missing facial features, extra limbs, disfigured hands, blurry teeth, disfigured teeth',
        clip=getnode_3.out(0),
    )
    cfgguider = _node(wf, 'CFGGuider', '1836',
        cfg=2.5,
        model=getnode_27.out(0),
        negative=getnode_16.out(0),
        positive=getnode_17.out(0),
    )
    cfgguider_2 = _node(wf, 'CFGGuider', '1856',
        cfg=2.5,
        model=getnode_28.out(0),
        negative=getnode_22.out(0),
        positive=getnode_23.out(0),
    )
    setnode_19 = _node(wf, 'SetNode', '1861',
        widget_0='t2v_mode',
        BOOLEAN=primitiveboolean.out(0),
    )
    modelsamplingsd3 = _node(wf, 'ModelSamplingSD3', '1876',
        shift=13,
        model=getnode_31.out(0),
    )
    solidmask = _node(wf, 'SolidMask', '1890',
        widget_0=0,
        widget_1=512,
        widget_2=512,
        height=getnode_32.out(0),
        width=getnode_33.out(0),
    )
    ltxvaudiovaeencode = _node(wf, 'LTXVAudioVAEEncode', '1893',
        audio=reroute.out(0),
        audio_vae=getnode_34.out(0),
    )
    simplecalculatorkj = _node(wf, 'SimpleCalculatorKJ', '1897',
        widget_0='((round((a * b -1) / 8)) * 8) + 1 ',
        _extras={'variables.a': intconstant.out(0), 'variables.b': getnode_36.out(0)},
    )
    modelsamplingsd3_2 = _node(wf, 'ModelSamplingSD3', '1912',
        shift=13,
        model=getnode_27.out(0),
    )
    n_63e8c999_0a69_4f62_af3f_8b77f0095971 = _node(wf, '63e8c999-0a69-4f62-af3f-8b77f0095971', '1920',
        audio=reroute.out(0),
    )
    setnode_22 = _node(wf, 'SetNode', '1930',
        widget_0='enhance_prompt',
        BOOLEAN=primitiveboolean_2.out(0),
    )
    trimaudioduration = _node(wf, 'TrimAudioDuration', '1939',
        widget_0=0,
        widget_1=15,
        audio=loadaudio.out(0),
    )
    pathchsageattentionkj = _node(wf, 'PathchSageAttentionKJ', '268',
        widget_0='disabled',
        widget_1=False,
        model=loraloadermodelonly.out(0),
    )
    setnode_3 = _node(wf, 'SetNode', '650',
        widget_0='ref_image',
        IMAGE=imageresizekjv2.out(0),
    )
    setnode_12 = _node(wf, 'SetNode', '1578',
        widget_0='frames',
        _extras={'*': n_63e8c999_0a69_4f62_af3f_8b77f0095971.out(0)},
    )
    resizeimagemasknode = _node(wf, 'ResizeImageMaskNode', '1630',
        widget_0='scale by multiplier',
        widget_1=256,
        widget_2='area',
        input=imageresizekjv2.out(0),
    )
    ltx2_nag = _node(wf, 'LTX2_NAG', '1844',
        widget_0=11,
        widget_1=0.25,
        widget_2=2.5,
        widget_3=True,
        model=getnode_26.out(0),
        nag_cond_audio=getnode_29.out(0),
        nag_cond_video=getnode_29.out(0),
    )
    samplercustomadvanced_2 = _node(wf, 'SamplerCustomAdvanced', '1845',
        guider=cfgguider_2.out(0),
        latent_image=getnode_30.out(0),
        noise=randomnoise_2.out(0),
        sampler=ksamplerselect_2.out(0),
        sigmas=manualsigmas_2.out(0),
    )
    basicscheduler = _node(wf, 'BasicScheduler', '1877',
        scheduler=1,
        steps=1,
        denoise=1,
        widget_1=8,
        model=modelsamplingsd3.out(0),
    )
    setlatentnoisemask = _node(wf, 'SetLatentNoiseMask', '1892',
        mask=solidmask.out(0),
        samples=ltxvaudiovaeencode.out(0),
    )
    basicscheduler_2 = _node(wf, 'BasicScheduler', '1911',
        scheduler=1,
        steps=1,
        denoise=1,
        widget_1=4,
        model=modelsamplingsd3_2.out(0),
    )
    setnode_21 = _node(wf, 'SetNode', '1918',
        widget_0='frames_seconds',
        INT=simplecalculatorkj.out(1),
    )
    ltxvimgtovideoinplace_2 = _node(wf, 'LTXVImgToVideoInplace', '1934',
        widget_0=0.7,
        widget_1=False,
        bypass=getnode_38.out(0),
        image=ltxvpreprocess.out(0),
        latent=emptyltxvlatentvideo.out(0),
        vae=getnode.out(0),
    )
    melbandroformersampler = _node(wf, 'MelBandRoFormerSampler', '1936',
        audio=trimaudioduration.out(0),
        model=melbandroformermodelloader.out(0),
    )
    ltxvconcatavlatent = _node(wf, 'LTXVConcatAVLatent', '350',
        audio_latent=getnode_35.out(0),
        video_latent=ltxvimgtovideoinplace_2.out(0),
    )
    ltxvchunkfeedforward = _node(wf, 'LTXVChunkFeedForward', '504',
        widget_0=2,
        widget_1=4096,
        model=pathchsageattentionkj.out(0),
    )
    getimagesize = _node(wf, 'GetImageSize', '1631',
        image=resizeimagemasknode.out(0),
    )
    ltxvseparateavlatent = _node(wf, 'LTXVSeparateAVLatent', '1827',
        av_latent=samplercustomadvanced_2.out(0),
    )
    setnode_17 = _node(wf, 'SetNode', '1840',
        widget_0='model',
        MODEL=ltx2_nag.out(0),
    )
    setnode_20 = _node(wf, 'SetNode', '1891',
        widget_0='latent_custom_audio',
        LATENT=setlatentnoisemask.out(0),
    )
    a8d7fd9f_52aa_447a_9766_53cb91c0ef18 = _node(wf, 'a8d7fd9f-52aa-447a-9766-53cb91c0ef18', '1926',
        _1=primitivestringmultiline.out(0),
        clip=getnode_2.out(0),
        image=resizeimagemasknode.out(0),
    )
    ailab_qwen3ttsvoiceclone = _node(wf, 'AILab_Qwen3TTSVoiceClone', '1944',
        widget_0='Hello, this is a cloned voice.',
        widget_1='1.7B',
        widget_2='Auto',
        widget_3='',
        widget_4=True,
        widget_5=986337553816914,
        widget_6=116899311982882,
        widget_7='randomize',
        reference_audio=melbandroformersampler.out(0),
        reference_text=primitivestringmultiline_2.out(0),
        target_text=primitivestringmultiline_3.out(0),
    )
    ltx2attentiontunerpatch = _node(wf, 'LTX2AttentionTunerPatch', '1523',
        widget_0='',
        widget_1=1,
        widget_2=1,
        widget_3=1,
        widget_4=1,
        widget_5=False,
        model=ltxvchunkfeedforward.out(0),
    )
    cliptextencode = _node(wf, 'CLIPTextEncode', '1621',
        widget_0='= Enhanced Prompt = \n',
        text=a8d7fd9f_52aa_447a_9766_53cb91c0ef18.out(0),
        clip=getnode_3.out(0),
    )
    setnode_14 = _node(wf, 'SetNode', '1633',
        widget_0='width_downscaled',
        INT=getimagesize.out(0),
    )
    setnode_15 = _node(wf, 'SetNode', '1634',
        widget_0='height_downscaled',
        INT=getimagesize.out(1),
    )
    ltxvimgtovideoinplace = _node(wf, 'LTXVImgToVideoInplace', '1825',
        widget_0=1,
        widget_1=False,
        bypass=getnode_19.out(0),
        image=getnode_20.out(0),
        latent=ltxvseparateavlatent.out(0),
        vae=getnode_14.out(0),
    )
    setnode_18 = _node(wf, 'SetNode', '1860',
        widget_0='latent',
        LATENT=ltxvconcatavlatent.out(0),
    )
    audionormalizelufs = _node(wf, 'AudioNormalizeLUFS', '1916',
        widget_0=-20,
        widget_1=0,
        widget_2=0,
        widget_3='full_track',
        audio=ailab_qwen3ttsvoiceclone.out(0),
    )
    ltxvconditioning = _node(wf, 'LTXVConditioning', '164',
        widget_0=8,
        frame_rate=getnode_7.out(0),
        negative=cliptextencode_2.out(0),
        positive=cliptextencode.out(0),
    )
    power_lora_loader__rgthree_ = _node(wf, 'Power Lora Loader (rgthree)', '1627',
        widget_4='',
        model=ltx2attentiontunerpatch.out(0),
    )
    ltxvconcatavlatent_2 = _node(wf, 'LTXVConcatAVLatent', '1819',
        audio_latent=ltxvseparateavlatent.out(1),
        video_latent=ltxvimgtovideoinplace.out(0),
    )
    audioenhancementnode = _node(wf, 'AudioEnhancementNode', '1904',
        widget_0='manual',
        widget_1=0.7,
        widget_10=5,
        widget_11=0,
        widget_12=0,
        widget_13='full_track',
        widget_2=0.6,
        widget_3=1.3,
        widget_4=1.2,
        widget_5=1,
        widget_6=1,
        widget_7=0.5,
        widget_8='keep_original',
        widget_9=False,
        audio=audionormalizelufs.out(0),
    )
    setnode = _node(wf, 'SetNode', '645',
        widget_0='positive',
        CONDITIONING=ltxvconditioning.out(0),
    )
    setnode_2 = _node(wf, 'SetNode', '646',
        widget_0='negative',
        CONDITIONING=ltxvconditioning.out(1),
    )
    setnode_13 = _node(wf, 'SetNode', '1617',
        widget_0='model_with_lora',
        MODEL=power_lora_loader__rgthree_.out(0),
    )
    setnode_16 = _node(wf, 'SetNode', '1758',
        widget_0='audio_tts',
        AUDIO=audioenhancementnode.out(0),
    )
    samplercustomadvanced = _node(wf, 'SamplerCustomAdvanced', '1838',
        guider=cfgguider.out(0),
        latent_image=ltxvconcatavlatent_2.out(0),
        noise=randomnoise.out(0),
        sampler=ksamplerselect.out(0),
        sigmas=manualsigmas.out(0),
    )
    previewaudio = _node(wf, 'PreviewAudio', '1943',
        audio=audioenhancementnode.out(0),
    )
    ltxvseparateavlatent_2 = _node(wf, 'LTXVSeparateAVLatent', '1839',
        av_latent=samplercustomadvanced.out(0),
    )
    vaedecodetiled = _node(wf, 'VAEDecodeTiled', '1818',
        tile_size=512,
        overlap=64,
        temporal_size=4096,
        temporal_overlap=8,
        samples=ltxvseparateavlatent_2.out(0),
        vae=getnode_12.out(0),
    )
    ltxvaudiovaedecode = _node(wf, 'LTXVAudioVAEDecode', '1847',
        audio_vae=getnode_13.out(0),
        samples=ltxvseparateavlatent_2.out(1),
    )
    vram_debug = _node(wf, 'VRAM_Debug', '1915',
        widget_0=True,
        widget_1=True,
        widget_2=True,
        image_pass=vaedecodetiled.out(0),
    )
    vhs_videocombine = _node(wf, 'VHS_VideoCombine', '1837',
        audio=ltxvaudiovaedecode.out(0),
        frame_rate=getnode_18.out(0),
        images=vram_debug.out(1),
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
