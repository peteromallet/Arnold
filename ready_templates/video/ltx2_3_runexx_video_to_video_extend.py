# vibecomfy: generated — converted by tools/convert_ready_templates.py
# Edits will be overwritten on regeneration. Add a `# vibecomfy: manual`
# marker on the first line if hand-editing is required.
"""Auto-generated ready_template — see tools/convert_ready_templates.py."""
from __future__ import annotations

from vibecomfy.workflow import VibeWorkflow, WorkflowSource
from vibecomfy.registry.ready_template import apply_ready_template_policy


READY_METADATA = {'model_assets': [],
 'unbound_inputs': {'seed': 4642},
 'ready_template': 'video/ltx2_3_runexx_video_to_video_extend',
 'workflow_template': 'ltx2_3_runexx_video_to_video_extend',
 'capability': 'video_to_video_extend',
 'source_role': 'materialized_ready_python_template',
 'source_workflow': 'workflow_corpus/custom_nodes/ltxvideo/runexx/LTX-2.3_V2V_Extend_Any_Video.json',
 'coverage_tier': 'supplemental',
 'approach': 'video-to-video extension',
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

    randomnoise = _node(wf, 'RandomNoise', '115',
        noise_seed=42,
        control_after_generate='fixed',
    )
    vaedecodetiled = _node(wf, 'VAEDecodeTiled', '127',
        tile_size=512,
        overlap=64,
        temporal_size=4096,
        temporal_overlap=8,
    )
    ksamplerselect = _node(wf, 'KSamplerSelect', '137',
        sampler_name='euler_ancestral',
    )
    intconstant = _node(wf, 'INTConstant', '211',
        widget_0=10,
    )
    primitivefloat = _node(wf, 'PrimitiveFloat', '214',
        value=8,
    )
    getnode = _node(wf, 'GetNode', '215',
        widget_0='clip',
    )
    getnode_2 = _node(wf, 'GetNode', '216',
        widget_0='vae_audio',
    )
    getnode_3 = _node(wf, 'GetNode', '217',
        widget_0='vae',
    )
    getnode_4 = _node(wf, 'GetNode', '219',
        widget_0='vae_audio',
    )
    getnode_5 = _node(wf, 'GetNode', '220',
        widget_0='vae',
    )
    getnode_6 = _node(wf, 'GetNode', '221',
        widget_0='fps',
    )
    getnode_7 = _node(wf, 'GetNode', '222',
        widget_0='fps',
    )
    getnode_8 = _node(wf, 'GetNode', '223',
        widget_0='fps',
    )
    getnode_9 = _node(wf, 'GetNode', '242',
        widget_0='upscale_model',
    )
    randomnoise_2 = _node(wf, 'RandomNoise', '243',
        noise_seed=432,
        control_after_generate='fixed',
    )
    getnode_10 = _node(wf, 'GetNode', '244',
        widget_0='vae',
    )
    ksamplerselect_2 = _node(wf, 'KSamplerSelect', '254',
        sampler_name='euler',
    )
    intconstant_2 = _node(wf, 'INTConstant', '305',
        widget_0=3,
    )
    getnode_11 = _node(wf, 'GetNode', '326',
        widget_0='ref_frames',
    )
    getnode_12 = _node(wf, 'GetNode', '356',
        widget_0='ext_seconds',
    )
    getnode_13 = _node(wf, 'GetNode', '363',
        widget_0='ref_video',
    )
    getnode_14 = _node(wf, 'GetNode', '369',
        widget_0='model',
    )
    getnode_15 = _node(wf, 'GetNode', '380',
        widget_0='ref_frames',
    )
    getnode_16 = _node(wf, 'GetNode', '392',
        widget_0='ref_audio',
    )
    getnode_17 = _node(wf, 'GetNode', '398',
        widget_0='overlap_seconds',
    )
    getnode_18 = _node(wf, 'GetNode', '408',
        widget_0='vae_tiny',
    )
    getnode_19 = _node(wf, 'GetNode', '439',
        widget_0='ref_image_overlap',
    )
    getnode_20 = _node(wf, 'GetNode', '442',
        widget_0='vae',
    )
    vaeloader = _node(wf, 'VAELoader', '463',
        vae_name='LTX23_video_vae_bf16.safetensors',
    )
    latentupscalemodelloader = _node(wf, 'LatentUpscaleModelLoader', '465',
        widget_0='ltx-2.3-spatial-upscaler-x2-1.1.safetensors',
    )
    dualcliploader = _node(wf, 'DualCLIPLoader', '466',
        clip_name1='gemma_3_12B_it_fp4_mixed.safetensors',
        clip_name2='ltx-2.3_text_projection_bf16.safetensors',
        type='ltxv',
        device='default',
    )
    vaeloaderkj = _node(wf, 'VAELoaderKJ', '471',
        widget_0='LTX23_audio_vae_bf16.safetensors',
        widget_1='main_device',
        widget_2='bf16',
    )
    vaeloader_2 = _node(wf, 'VAELoader', '473',
        vae_name='taeltx2_3.safetensors',
    )
    unetloader = _node(wf, 'UNETLoader', '474',
        unet_name='ltx-2.3-22b-distilled_transformer_only_fp8_scaled.safetensors',
        weight_dtype='default',
    )
    unetloadergguf = _node(wf, 'UnetLoaderGGUF', '475',
        widget_0='LTXvideo\\LTX-2\\quantstack\\LTX-2.3-distilled-Q4_K_S.gguf',
    )
    dualcliploadergguf = _node(wf, 'DualCLIPLoaderGGUF', '477',
        widget_0='gemma-3-12b-it-Q2_K.gguf',
        widget_1='ltx-2.3_text_projection_bf16.safetensors',
        widget_2='sdxl',
    )
    manualsigmas = _node(wf, 'ManualSigmas', '479',
        widget_0='0.85, 0.7250, 0.4219, 0.0',
    )
    manualsigmas_2 = _node(wf, 'ManualSigmas', '480',
        widget_0='1.0, 0.99375, 0.9875, 0.98125, 0.975, 0.909375, 0.725, 0.421875, 0.0',
    )
    primitivestringmultiline = _node(wf, 'PrimitiveStringMultiline', '487',
        value='The Joker looks at the camera and talks, he says "You know what clownheads. This scene is not from the movie. Its from LTX 2 point 3". \n\nThen the Joker stands up with an LTX soda can in his hand. \n\nHe drinks from the soda can, and then he says "Ahhh...  with a bit of LTX and Snickers, my mood changed. Lets all be friends." \n\nThen he laughs.\n',
    )
    reroute = _node(wf, 'Reroute', '496')
    intconstant_3 = _node(wf, 'INTConstant', '497',
        widget_0=832,
    )
    getnode_21 = _node(wf, 'GetNode', '502',
        widget_0='max_size',
    )
    getnode_22 = _node(wf, 'GetNode', '507',
        widget_0='max_size',
    )
    getnode_23 = _node(wf, 'GetNode', '508',
        widget_0='ref_image',
    )
    getnode_24 = _node(wf, 'GetNode', '514',
        widget_0='overlap_seconds',
    )
    reroute_2 = _node(wf, 'Reroute', '528')
    getnode_25 = _node(wf, 'GetNode', '541',
        widget_0='ref_video',
    )
    getnode_26 = _node(wf, 'GetNode', '542',
        widget_0='ref_frames',
    )
    getnode_27 = _node(wf, 'GetNode', '555',
        widget_0='vae',
    )
    getnode_28 = _node(wf, 'GetNode', '572',
        widget_0='positive',
    )
    getnode_29 = _node(wf, 'GetNode', '573',
        widget_0='negative',
    )
    getnode_30 = _node(wf, 'GetNode', '576',
        widget_0='positive',
    )
    getnode_31 = _node(wf, 'GetNode', '577',
        widget_0='negative',
    )
    getnode_32 = _node(wf, 'GetNode', '579',
        widget_0='final_audio',
    )
    getnode_33 = _node(wf, 'GetNode', '580',
        widget_0='fps',
    )
    getnode_34 = _node(wf, 'GetNode', '581',
        widget_0='final_video_blend',
    )
    primitiveboolean = _node(wf, 'PrimitiveBoolean', '594',
        value=True,
    )
    getnode_35 = _node(wf, 'GetNode', '600',
        widget_0='clip',
    )
    getnode_36 = _node(wf, 'GetNode', '602',
        widget_0='enable_promptenhance',
    )
    getnode_37 = _node(wf, 'GetNode', '606',
        widget_0='fps',
    )
    getnode_38 = _node(wf, 'GetNode', '628',
        widget_0='final_video_cut',
    )
    getnode_39 = _node(wf, 'GetNode', '638',
        widget_0='ref_video',
    )
    getnode_40 = _node(wf, 'GetNode', '640',
        widget_0='final_audio',
    )
    getnode_41 = _node(wf, 'GetNode', '641',
        widget_0='fps',
    )
    loadaudio = _node(wf, 'LoadAudio', '642',
        audio='speech_smoke.wav',
        widget_0='speech_smoke.wav',
    )
    cliptextencode = _node(wf, 'CLIPTextEncode', '110',
        text='text, subtitles, logo, low quality, distorted, bad anatomy, oversaturated, pixelated, low resolution, grainy, compression artifacts, jpeg artifacts, glitches, watermark, signature, copyright,  distortedsound, saturated sound, loud sound , deformed facial features, asymmetrical face, missing facial features, extra limbs, disfigured hands, blurry teeth, disfigured teeth',
        clip=getnode.out(0),
    )
    setnode_3 = _node(wf, 'SetNode', '209',
        widget_0='ext_seconds',
        INT=intconstant.out(0),
    )
    setnode_4 = _node(wf, 'SetNode', '210',
        widget_0='fps',
        FLOAT=primitivefloat.out(0),
    )
    getimagerangefrombatch = _node(wf, 'GetImageRangeFromBatch', '306',
        widget_0=0,
        widget_1=4096,
        images=reroute_2.out(0),
        start_index=getnode_11.out(0),
    )
    vhs_loadvideo = _node(wf, 'VHS_LoadVideo', '319',
        file='ltx_smoke_guide.mp4',
        video='ltx_smoke_guide.mp4',
        widget_0='ltx_smoke_guide.mp4',
        force_rate=getnode_6.out(0),
    )
    simplecalculatorkj = _node(wf, 'SimpleCalculatorKJ', '352',
        widget_0='((round((a * b -1) / 8)) * 8) + 1 ',
        _extras={'variables.a': intconstant.out(0), 'variables.b': primitivefloat.out(0)},
    )
    simplecalculatorkj_2 = _node(wf, 'SimpleCalculatorKJ', '357',
        widget_0='a + b',
        _extras={'variables.a': getnode_12.out(0), 'variables.b': getnode_24.out(0)},
    )
    ltx2samplingpreviewoverride = _node(wf, 'LTX2SamplingPreviewOverride', '368',
        widget_0=8,
        model=getnode_14.out(0),
        vae=getnode_18.out(0),
    )
    getimagerangefrombatch_2 = _node(wf, 'GetImageRangeFromBatch', '379',
        widget_0=-1,
        widget_1=1,
        images=getnode_39.out(0),
        num_frames=getnode_15.out(0),
    )
    normalizeaudioloudness = _node(wf, 'NormalizeAudioLoudness', '443',
        widget_0=-16,
        audio=loadaudio.out(0),
    )
    setnode_16 = _node(wf, 'SetNode', '459',
        widget_0='upscale_model',
        LATENT_UPSCALE_MODEL=latentupscalemodelloader.out(0),
    )
    setnode_17 = _node(wf, 'SetNode', '460',
        widget_0='vae_audio',
        VAE=vaeloaderkj.out(0),
    )
    setnode_18 = _node(wf, 'SetNode', '461',
        widget_0='vae',
        VAE=vaeloader.out(0),
    )
    setnode_19 = _node(wf, 'SetNode', '462',
        widget_0='clip',
        CLIP=dualcliploader.out(0),
    )
    loraloadermodelonly = _node(wf, 'LoraLoaderModelOnly', '464',
        lora_name='LTX\\LTX-2\\ltx-2.3-22b-distilled-lora-384.safetensors',
        strength_model=0.6,
        model=unetloader.out(0),
    )
    setnode_20 = _node(wf, 'SetNode', '472',
        widget_0='vae_tiny',
        VAE=vaeloader_2.out(0),
    )
    setnode_22 = _node(wf, 'SetNode', '498',
        widget_0='max_size',
        INT=intconstant_3.out(0),
    )
    resizeimagesbylongeredge_2 = _node(wf, 'ResizeImagesByLongerEdge', '505',
        widget_0=1536,
        images=reroute.out(0),
        longer_edge=getnode_22.out(0),
    )
    imagebatchextendwithoverlap = _node(wf, 'ImageBatchExtendWithOverlap', '536',
        widget_0=1,
        widget_1='source',
        widget_2='perceptual_crossfade',
        new_images=reroute_2.out(0),
        overlap=getnode_26.out(0),
        source_images=getnode_25.out(0),
    )
    vhs_videocombine = _node(wf, 'VHS_VideoCombine', '578',
        audio=getnode_32.out(0),
        frame_rate=getnode_33.out(0),
        images=getnode_34.out(0),
    )
    n_6002fb3c_ab34_4ad8_894e_fccaa60fd8c9 = _node(wf, '6002fb3c-ab34-4ad8-894e-fccaa60fd8c9', '599',
        clip=getnode_35.out(0),
        image=getnode_23.out(0),
        string_b=primitivestringmultiline.out(0),
    )
    setnode_25 = _node(wf, 'SetNode', '601',
        widget_0='enable_promptenhance',
        BOOLEAN=primitiveboolean.out(0),
    )
    simplecalculatorkj_6 = _node(wf, 'SimpleCalculatorKJ', '605',
        widget_0='((round((a * b -1) / 8)) * 8) + 1 ',
        _extras={'variables.a': intconstant_2.out(0), 'variables.b': getnode_37.out(0)},
    )
    cliptextencode_3 = _node(wf, 'CLIPTextEncode', '626',
        text=' distorted sound, saturated sound, loud sound',
        clip=getnode.out(0),
    )
    vhs_videocombine_2 = _node(wf, 'VHS_VideoCombine', '627',
        audio=getnode_40.out(0),
        frame_rate=getnode_41.out(0),
        images=getnode_38.out(0),
    )
    setnode_9 = _node(wf, 'SetNode', '310',
        widget_0='ref_frames',
        INT=simplecalculatorkj_6.out(1),
    )
    setnode_11 = _node(wf, 'SetNode', '329',
        widget_0='ref_audio',
        AUDIO=normalizeaudioloudness.out(0),
    )
    setnode_12 = _node(wf, 'SetNode', '349',
        widget_0='extended_frames',
        INT=simplecalculatorkj.out(1),
    )
    vhs_videoinfo = _node(wf, 'VHS_VideoInfo', '382',
        video_info=vhs_loadvideo.out(3),
    )
    imagebatchmulti = _node(wf, 'ImageBatchMulti', '403',
        widget_0=2,
        image_1=getnode_13.out(0),
        image_2=getimagerangefrombatch.out(0),
    )
    resizeimagemasknode = _node(wf, 'ResizeImageMaskNode', '436',
        widget_0='scale by multiplier',
        widget_1=256,
        widget_2='area',
        input=getimagerangefrombatch_2.out(0),
    )
    vhs_videoinfo_2 = _node(wf, 'VHS_VideoInfo', '492',
        video_info=vhs_loadvideo.out(3),
    )
    pathchsageattentionkj = _node(wf, 'PathchSageAttentionKJ', '520',
        widget_0='disabled',
        widget_1=False,
        model=loraloadermodelonly.out(0),
    )
    modelsamplingsd3 = _node(wf, 'ModelSamplingSD3', '526',
        shift=13,
        model=ltx2samplingpreviewoverride.out(0),
    )
    ltx2_nag = _node(wf, 'LTX2_NAG', '563',
        widget_0=11,
        widget_1=0.25,
        widget_2=2.5,
        widget_3=True,
        model=ltx2samplingpreviewoverride.out(0),
        nag_cond_audio=cliptextencode_3.out(0),
        nag_cond_video=cliptextencode.out(0),
    )
    getimagerangefrombatch_5 = _node(wf, 'GetImageRangeFromBatch', '566',
        widget_0=0,
        widget_1=1,
        images=getimagerangefrombatch_2.out(0),
    )
    setnode_24 = _node(wf, 'SetNode', '574',
        widget_0='final_video_blend',
        IMAGE=imagebatchextendwithoverlap.out(2),
    )
    cliptextencode_2 = _node(wf, 'CLIPTextEncode', '592',
        widget_0='= from prompt enhancer = ',
        text=n_6002fb3c_ab34_4ad8_894e_fccaa60fd8c9.out(0),
        clip=getnode.out(0),
    )
    basicscheduler = _node(wf, 'BasicScheduler', '164',
        scheduler=1,
        steps=1,
        denoise=1,
        widget_1=8,
        model=modelsamplingsd3.out(0),
    )
    simplecalculatorkj_3 = _node(wf, 'SimpleCalculatorKJ', '384',
        widget_0='a / b',
        _extras={'variables.a': getnode_15.out(0), 'variables.b': vhs_videoinfo.out(5)},
    )
    setnode_14 = _node(wf, 'SetNode', '451',
        widget_0='final_video_cut',
        IMAGE=imagebatchmulti.out(0),
    )
    simplecalculatorkj_5 = _node(wf, 'SimpleCalculatorKJ', '500',
        widget_0='(a > c) or (b > c) ',
        _extras={'variables.a': vhs_videoinfo_2.out(8), 'variables.b': vhs_videoinfo_2.out(9), 'variables.c': getnode_21.out(0)},
    )
    getimagerangefrombatch_4 = _node(wf, 'GetImageRangeFromBatch', '556',
        widget_0=-1,
        widget_1=1,
        images=resizeimagemasknode.out(0),
    )
    vaeencode_2 = _node(wf, 'VAEEncode', '565',
        pixels=resizeimagemasknode.out(0),
        vae=getnode_3.out(0),
    )
    setnode_23 = _node(wf, 'SetNode', '567',
        widget_0='ref_image_overlap',
        IMAGE=getimagerangefrombatch_5.out(0),
    )
    simplecalculatorkj_4 = _node(wf, 'SimpleCalculatorKJ', '386',
        widget_0='a - b',
        _extras={'variables.a': vhs_videoinfo.out(7), 'variables.b': simplecalculatorkj_3.out(0)},
    )
    setnode_13 = _node(wf, 'SetNode', '397',
        widget_0='overlap_seconds',
        FLOAT=simplecalculatorkj_3.out(0),
    )
    lazyswitchkj = _node(wf, 'LazySwitchKJ', '504',
        widget_0=False,
        on_false=reroute.out(0),
        on_true=resizeimagesbylongeredge_2.out(0),
        switch=simplecalculatorkj_5.out(2),
    )
    ltxvchunkfeedforward = _node(wf, 'LTXVChunkFeedForward', '522',
        widget_0=2,
        widget_1=4096,
        model=pathchsageattentionkj.out(0),
    )
    vaeencode = _node(wf, 'VAEEncode', '546',
        pixels=getimagerangefrombatch_4.out(0),
        vae=getnode_27.out(0),
    )
    trimaudioduration = _node(wf, 'TrimAudioDuration', '377',
        widget_0=0,
        widget_1=60,
        audio=normalizeaudioloudness.out(0),
        duration=simplecalculatorkj_3.out(0),
        start_index=simplecalculatorkj_4.out(0),
    )
    getimagesizeandcount = _node(wf, 'GetImageSizeAndCount', '506',
        image=lazyswitchkj.out(0),
    )
    ltx2attentiontunerpatch = _node(wf, 'LTX2AttentionTunerPatch', '523',
        widget_0='',
        widget_1=1,
        widget_2=1,
        widget_3=1,
        widget_4=1,
        widget_5=True,
        model=ltxvchunkfeedforward.out(0),
    )
    ltxvaudiovaeencode = _node(wf, 'LTXVAudioVAEEncode', '179',
        audio=trimaudioduration.out(0),
        audio_vae=getnode_2.out(0),
    )
    setnode_21 = _node(wf, 'SetNode', '481',
        widget_0='model',
        MODEL=ltx2attentiontunerpatch.out(0),
    )
    imageresizekjv2 = _node(wf, 'ImageResizeKJv2', '512',
        widget_0=512,
        widget_1=512,
        widget_2='lanczos',
        widget_3='crop',
        widget_4='0, 0, 0',
        widget_5='center',
        widget_6=64,
        widget_7='cpu',
        height=getimagesizeandcount.out(2),
        image=getimagesizeandcount.out(0),
        width=getimagesizeandcount.out(1),
    )
    ltxvaudiovideomask = _node(wf, 'LTXVAudioVideoMask', '178',
        widget_0=24,
        widget_1=0,
        widget_2=15,
        widget_3=0,
        widget_4=15,
        widget_5='pad',
        widget_6='add',
        audio_end_time=simplecalculatorkj_2.out(0),
        audio_latent=ltxvaudiovaeencode.out(0),
        audio_start_time=getnode_24.out(0),
        video_end_time=simplecalculatorkj_2.out(0),
        video_fps=getnode_8.out(0),
        video_latent=vaeencode_2.out(0),
        video_start_time=getnode_24.out(0),
    )
    setnode = _node(wf, 'SetNode', '207',
        widget_0='width',
        INT=imageresizekjv2.out(1),
    )
    setnode_2 = _node(wf, 'SetNode', '208',
        widget_0='height',
        INT=imageresizekjv2.out(2),
    )
    setnode_10 = _node(wf, 'SetNode', '328',
        widget_0='ref_video',
        IMAGE=imageresizekjv2.out(0),
    )
    getimagerangefrombatch_3 = _node(wf, 'GetImageRangeFromBatch', '440',
        widget_0=0,
        widget_1=1,
        images=imageresizekjv2.out(0),
    )
    resizeimagesbylongeredge = _node(wf, 'ResizeImagesByLongerEdge', '495',
        widget_0=1536,
        images=getimagerangefrombatch_3.out(0),
    )
    ltxvaddlatentguide = _node(wf, 'LTXVAddLatentGuide', '545',
        widget_0=-1,
        widget_1=1,
        guiding_latent=vaeencode.out(0),
        latent=ltxvaudiovideomask.out(0),
        negative=cliptextencode.out(0),
        positive=cliptextencode_2.out(0),
        vae=getnode_27.out(0),
    )
    ltxvconditioning = _node(wf, 'LTXVConditioning', '107',
        widget_0=8,
        frame_rate=getnode_7.out(0),
        negative=ltxvaddlatentguide.out(1),
        positive=ltxvaddlatentguide.out(0),
    )
    ltxvconcatavlatent = _node(wf, 'LTXVConcatAVLatent', '109',
        audio_latent=ltxvaudiovideomask.out(1),
        video_latent=ltxvaddlatentguide.out(2),
    )
    setnode_8 = _node(wf, 'SetNode', '294',
        widget_0='ref_image',
        IMAGE=resizeimagesbylongeredge.out(0),
    )
    ltxvpreprocess = _node(wf, 'LTXVPreprocess', '299',
        widget_0=18,
        image=resizeimagesbylongeredge.out(0),
    )
    cfgguider = _node(wf, 'CFGGuider', '129',
        cfg=2.5,
        model=ltx2_nag.out(0),
        negative=ltxvconditioning.out(1),
        positive=ltxvconditioning.out(0),
    )
    setnode_5 = _node(wf, 'SetNode', '224',
        widget_0='positive',
        CONDITIONING=ltxvconditioning.out(0),
    )
    setnode_6 = _node(wf, 'SetNode', '225',
        widget_0='negative',
        CONDITIONING=ltxvconditioning.out(1),
    )
    setnode_7 = _node(wf, 'SetNode', '285',
        widget_0='compress_image',
        IMAGE=ltxvpreprocess.out(0),
    )
    samplercustomadvanced = _node(wf, 'SamplerCustomAdvanced', '113',
        guider=cfgguider.out(0),
        latent_image=ltxvconcatavlatent.out(0),
        noise=randomnoise.out(0),
        sampler=ksamplerselect.out(0),
        sigmas=basicscheduler.out(0),
    )
    ltxvseparateavlatent_2 = _node(wf, 'LTXVSeparateAVLatent', '250',
        av_latent=samplercustomadvanced.out(0),
    )
    ltxvcropguides = _node(wf, 'LTXVCropGuides', '549',
        latent=ltxvseparateavlatent_2.out(0),
        negative=getnode_29.out(0),
        positive=getnode_28.out(0),
    )
    cfgguider_2 = _node(wf, 'CFGGuider', '256',
        cfg=2.5,
        model=ltx2_nag.out(0),
        negative=ltxvcropguides.out(1),
        positive=ltxvcropguides.out(0),
    )
    ltxvimgtovideoinplace = _node(wf, 'LTXVImgToVideoInplace', '438',
        widget_0=1,
        widget_1=False,
        image=getnode_19.out(0),
        latent=ltxvcropguides.out(2),
        vae=getnode_20.out(0),
    )
    ltxvconcatavlatent_2 = _node(wf, 'LTXVConcatAVLatent', '251',
        audio_latent=ltxvseparateavlatent_2.out(1),
        video_latent=ltxvimgtovideoinplace.out(0),
    )
    samplercustomadvanced_2 = _node(wf, 'SamplerCustomAdvanced', '258',
        guider=cfgguider_2.out(0),
        latent_image=ltxvconcatavlatent_2.out(0),
        noise=randomnoise_2.out(0),
        sampler=ksamplerselect_2.out(0),
        sigmas=manualsigmas.out(0),
    )
    ltxvseparateavlatent = _node(wf, 'LTXVSeparateAVLatent', '125',
        av_latent=samplercustomadvanced_2.out(0),
    )
    ltxvaudiovaedecode = _node(wf, 'LTXVAudioVAEDecode', '425',
        audio_vae=getnode_4.out(0),
        samples=ltxvseparateavlatent.out(1),
    )
    ltxvcropguides_2 = _node(wf, 'LTXVCropGuides', '569',
        latent=ltxvseparateavlatent.out(0),
        negative=getnode_31.out(0),
        positive=getnode_30.out(0),
    )
    trimaudioduration_2 = _node(wf, 'TrimAudioDuration', '394',
        widget_0=0,
        widget_1=2048,
        audio=ltxvaudiovaedecode.out(0),
        start_index=getnode_17.out(0),
    )
    vaedecode = _node(wf, 'VAEDecode', '527',
        samples=ltxvcropguides_2.out(2),
        vae=getnode_5.out(0),
    )
    audioconcat = _node(wf, 'AudioConcat', '393',
        widget_0='after',
        audio1=getnode_16.out(0),
        audio2=trimaudioduration_2.out(0),
    )
    setnode_15 = _node(wf, 'SetNode', '453',
        widget_0='final_audio',
        AUDIO=audioconcat.out(0),
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
