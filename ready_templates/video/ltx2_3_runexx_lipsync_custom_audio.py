# vibecomfy: generated — converted by tools/convert_ready_templates.py
# Edits will be overwritten on regeneration. Add a `# vibecomfy: manual`
# marker on the first line if hand-editing is required.
"""Auto-generated ready_template — see tools/convert_ready_templates.py."""
from __future__ import annotations

from vibecomfy.workflow import VibeWorkflow, WorkflowSource
from vibecomfy.registry.ready_template import apply_ready_template_policy


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
                        'Keep community audio, lip-sync, and long-form workflows as ready templates until '
                        'their custom node packs and service credentials are declared.'],
 'comfy_configuration': {'reserve_vram': 12, 'cache_none': True, 'fp8_e4m3fn_text_enc': True}}

READY_REQUIREMENTS = {'models': [],
 'custom_nodes': ['ComfyUI-GGUF', 'ComfyUI-KJNodes', 'ComfyUI-LTXVideo', 'ComfyUI-VideoHelperSuite', 'rgthree-comfy']}


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
        noise_seed=790774741312584,
        control_after_generate='randomize',
    )
    vaedecodetiled = _node(wf, 'VAEDecodeTiled', '127',
        tile_size=512,
        overlap=64,
        temporal_size=4096,
        temporal_overlap=8,
    )
    ksamplerselect = _node(wf, 'KSamplerSelect', '137',
        sampler_name='euler_ancestral_cfg_pp',
    )
    intconstant = _node(wf, 'INTConstant', '211',
        widget_0=3,
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
    getnode_8 = _node(wf, 'GetNode', '242',
        widget_0='upscale_model',
    )
    randomnoise_2 = _node(wf, 'RandomNoise', '243',
        noise_seed=43,
        control_after_generate='fixed',
    )
    getnode_9 = _node(wf, 'GetNode', '244',
        widget_0='vae',
    )
    ksamplerselect_2 = _node(wf, 'KSamplerSelect', '254',
        sampler_name='euler_cfg_pp',
    )
    getnode_10 = _node(wf, 'GetNode', '356',
        widget_0='ext_seconds',
    )
    getnode_11 = _node(wf, 'GetNode', '369',
        widget_0='model',
    )
    getnode_12 = _node(wf, 'GetNode', '408',
        widget_0='vae_tiny',
    )
    getnode_13 = _node(wf, 'GetNode', '439',
        widget_0='ref_image',
    )
    getnode_14 = _node(wf, 'GetNode', '442',
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
    vaeloaderkj = _node(wf, 'LTXVAudioVAELoader', '471',
        ckpt_name='LTX23_audio_vae_bf16.safetensors',
    )
    vaeloader_2 = _node(wf, 'VAELoader', '473',
        vae_name='taeltx2_3.safetensors',
    )
    unetloader = _node(wf, 'UNETLoader', '474',
        unet_name='ltx-2.3-22b-distilled-1.1_transformer_only_fp8_scaled.safetensors',
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
        value='Cinematic video woman wearing colorful make-up, with colorful  light creating a creative scene. \n\nShe talks with perfect lip-sync movements to the attached audio. Her mouth and lips moves as she talks. \n \nThe camera slowly moves away from the woman, showing her full body. She is standing at a  colorful theatre scene doing a victorian era play. ',
    )
    reroute = _node(wf, 'Reroute', '496')
    intconstant_2 = _node(wf, 'INTConstant', '497',
        widget_0=650,
    )
    getnode_15 = _node(wf, 'GetNode', '502',
        widget_0='max_size',
    )
    getnode_16 = _node(wf, 'GetNode', '507',
        widget_0='max_size',
    )
    getnode_17 = _node(wf, 'GetNode', '508',
        widget_0='ref_image',
    )
    getnode_18 = _node(wf, 'GetNode', '572',
        widget_0='positive',
    )
    getnode_19 = _node(wf, 'GetNode', '573',
        widget_0='negative',
    )
    getnode_20 = _node(wf, 'GetNode', '580',
        widget_0='fps',
    )
    getnode_21 = _node(wf, 'GetNode', '581',
        widget_0='final_video',
    )
    primitiveboolean = _node(wf, 'PrimitiveBoolean', '594',
        value=False,
    )
    getnode_22 = _node(wf, 'GetNode', '600',
        widget_0='clip',
    )
    getnode_23 = _node(wf, 'GetNode', '602',
        widget_0='enable_promptenhance',
    )
    getnode_24 = _node(wf, 'GetNode', '638',
        widget_0='ref_video',
    )
    getnode_25 = _node(wf, 'GetNode', '643',
        widget_0='fps',
    )
    getnode_26 = _node(wf, 'GetNode', '649',
        widget_0='final_audio',
    )
    getnode_27 = _node(wf, 'GetNode', '652',
        widget_0='model_n_nag',
    )
    getnode_28 = _node(wf, 'GetNode', '654',
        widget_0='model_n_nag',
    )
    getnode_29 = _node(wf, 'GetNode', '719',
        widget_0='vae',
    )
    getnode_30 = _node(wf, 'GetNode', '724',
        widget_0='ref_video',
    )
    getnode_31 = _node(wf, 'GetNode', '731',
        widget_0='vae',
    )
    getnode_32 = _node(wf, 'GetNode', '732',
        widget_0='ref_image',
    )
    getnode_33 = _node(wf, 'GetNode', '739',
        widget_0='positive',
    )
    getnode_34 = _node(wf, 'GetNode', '740',
        widget_0='negative',
    )
    ltxavtextencoderloader = _node(wf, 'LTXAVTextEncoderLoader', '742',
        ckpt_name='ltx-2.3-22b-dev-fp8.safetensors',
        text_encoder='gemma_3_12B_it_fp4_mixed.safetensors',
        widget_0='gemma_3_12B_it_fp4_mixed.safetensors',
        widget_1='VIDEO\\LTX\\LTX-2\\ltx-2.3_text_projection_bf16.safetensors',
        widget_2='default',
    )
    getnode_35 = _node(wf, 'GetNode', '804',
        widget_0='vae',
    )
    primitivefloat_2 = _node(wf, 'PrimitiveFloat', '814',
        value=8,
    )
    getnode_36 = _node(wf, 'GetNode', '816',
        widget_0='last_latent_strength',
    )
    getnode_37 = _node(wf, 'GetNode', '822',
        widget_0='positive_to_crop',
    )
    getnode_38 = _node(wf, 'GetNode', '823',
        widget_0='negative_to_crop',
    )
    getnode_39 = _node(wf, 'GetNode', '825',
        widget_0='negative_to_crop',
    )
    getnode_40 = _node(wf, 'GetNode', '826',
        widget_0='positive_to_crop',
    )
    getnode_41 = _node(wf, 'GetNode', '845',
        widget_0='latent_custom_audio',
    )
    getnode_42 = _node(wf, 'GetNode', '846',
        widget_0='latent_audio',
    )
    loadaudio = _node(wf, 'LoadAudio', '855',
        audio='e9318ca1-5e2b-47aa-8397-f4538b0151b0.wav',
    )
    getnode_43 = _node(wf, 'GetNode', '856',
        widget_0='height_generated',
    )
    getnode_44 = _node(wf, 'GetNode', '858',
        widget_0='vae_audio',
    )
    melbandroformermodelloader = _node(wf, 'MelBandRoFormerModelLoader', '861',
        widget_0='MelBandRoformer\\MelBandRoformer_fp16.safetensors',
    )
    getnode_45 = _node(wf, 'GetNode', '862',
        widget_0='width_generated',
    )
    getnode_46 = _node(wf, 'GetNode', '872',
        widget_0='frames_loaded',
    )
    getnode_47 = _node(wf, 'GetNode', '873',
        widget_0='fps',
    )
    getnode_48 = _node(wf, 'GetNode', '874',
        widget_0='ext_seconds',
    )
    getnode_49 = _node(wf, 'GetNode', '879',
        widget_0='latent_audio_selected',
    )
    getnode_50 = _node(wf, 'GetNode', '887',
        widget_0='latent_audio_selected',
    )
    ltxvconditioning = _node(wf, 'LTXVConditioning', '107',
        widget_0=8,
        frame_rate=getnode_7.out(0),
        negative=getnode_34.out(0),
        positive=getnode_33.out(0),
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
    cfgguider_2 = _node(wf, 'CFGGuider', '256',
        cfg=2.5,
        model=getnode_27.out(0),
        negative=getnode_19.out(0),
        positive=getnode_18.out(0),
    )
    resizeimagemasknode = _node(wf, 'ResizeImageMaskNode', '436',
        widget_0='scale by multiplier',
        widget_1=256,
        widget_2='area',
        input=getnode_24.out(0),
    )
    setnode_9 = _node(wf, 'SetNode', '459',
        widget_0='upscale_model',
        LATENT_UPSCALE_MODEL=latentupscalemodelloader.out(0),
    )
    setnode_10 = _node(wf, 'SetNode', '460',
        widget_0='vae_audio',
        VAE=vaeloaderkj.out(0),
    )
    setnode_11 = _node(wf, 'SetNode', '461',
        widget_0='vae',
        VAE=vaeloader.out(0),
    )
    setnode_12 = _node(wf, 'SetNode', '462',
        widget_0='clip',
        CLIP=ltxavtextencoderloader.out(0),
    )
    loraloadermodelonly = _node(wf, 'LoraLoaderModelOnly', '464',
        lora_name='LTX\\LTX-2\\ltx-2.3-22b-distilled-lora-384.safetensors',
        strength_model=0.6,
        model=unetloader.out(0),
    )
    setnode_13 = _node(wf, 'SetNode', '472',
        widget_0='vae_tiny',
        VAE=vaeloader_2.out(0),
    )
    setnode_15 = _node(wf, 'SetNode', '498',
        widget_0='max_size',
        INT=intconstant_2.out(0),
    )
    resizeimagesbylongeredge_2 = _node(wf, 'ResizeImagesByLongerEdge', '505',
        widget_0=1536,
        images=reroute.out(0),
        longer_edge=getnode_16.out(0),
    )
    vhs_videocombine = _node(wf, 'VHS_VideoCombine', '578',
        audio=getnode_26.out(0),
        frame_rate=getnode_20.out(0),
        images=getnode_21.out(0),
    )
    setnode_16 = _node(wf, 'SetNode', '601',
        widget_0='enable_promptenhance',
        BOOLEAN=primitiveboolean.out(0),
    )
    cliptextencode_3 = _node(wf, 'CLIPTextEncode', '626',
        text=' distorted sound, saturated sound, loud sound',
        clip=getnode.out(0),
    )
    getimagesizeandcount_2 = _node(wf, 'GetImageSizeAndCount', '698',
        image=getnode_24.out(0),
    )
    comfymathexpression = _node(wf, 'ComfyMathExpression', '699',
        widget_0='a',
        _extras={'values.a': getnode_25.out(0)},
    )
    resizeimagemasknode_3 = _node(wf, 'ResizeImageMaskNode', '726',
        widget_0='scale by multiplier',
        widget_1=256,
        widget_2='nearest-exact',
        input=getnode_30.out(0),
    )
    vhs_loadvideoffmpeg = _node(wf, 'VHS_LoadVideoFFmpeg', '774',
        force_rate=getnode_6.out(0),
    )
    e428c881_c48b_4849_9158_8311b4df27c7 = _node(wf, 'e428c881-c48b-4849-9158-8311b4df27c7', '784',
        clip=getnode_22.out(0),
        image=getnode_17.out(0),
        switch=getnode_23.out(0),
    )
    setnode_21 = _node(wf, 'SetNode', '815',
        widget_0='last_latent_strength',
        FLOAT=primitivefloat_2.out(0),
    )
    comfyswitchnode = _node(wf, 'ComfySwitchNode', '847',
        widget_0=True,
        on_false=getnode_42.out(0),
        on_true=getnode_41.out(0),
    )
    simplecalculatorkj_2 = _node(wf, 'SimpleCalculatorKJ', '854',
        widget_0='(a/b)+c',
        _extras={'variables.a': getnode_46.out(0), 'variables.b': getnode_47.out(0), 'variables.c': getnode_48.out(0)},
    )
    solidmask = _node(wf, 'SolidMask', '865',
        widget_0=0,
        widget_1=512,
        widget_2=512,
        height=getnode_43.out(0),
        width=getnode_45.out(0),
    )
    vhs_videoinfo = _node(wf, 'VHS_VideoInfo', '492',
        video_info=vhs_loadvideoffmpeg.out(3),
    )
    pathchsageattentionkj = _node(wf, 'PathchSageAttentionKJ', '520',
        widget_0='disabled',
        widget_1=False,
        model=loraloadermodelonly.out(0),
    )
    modelsamplingsd3 = _node(wf, 'ModelSamplingSD3', '526',
        shift=13,
        model=getnode_11.out(0),
    )
    ltx2_nag = _node(wf, 'LTX2_NAG', '563',
        widget_0=11,
        widget_1=0.25,
        widget_2=2.5,
        widget_3=True,
        model=getnode_11.out(0),
        nag_cond_audio=cliptextencode_3.out(0),
        nag_cond_video=cliptextencode.out(0),
    )
    vaeencode = _node(wf, 'VAEEncode', '565',
        pixels=resizeimagemasknode.out(0),
        vae=getnode_3.out(0),
    )
    cliptextencode_2 = _node(wf, 'CLIPTextEncode', '592',
        widget_0='= from prompt enhancer = ',
        text=e428c881_c48b_4849_9158_8311b4df27c7.out(0),
        clip=getnode.out(0),
    )
    ltxvemptylatentaudio = _node(wf, 'LTXVEmptyLatentAudio', '642',
        widget_0=5,
        widget_1=8,
        widget_2=1,
        audio_vae=getnode_2.out(0),
        frame_rate=comfymathexpression.out(1),
        frames_number=getimagesizeandcount_2.out(3),
    )
    setnode_20 = _node(wf, 'SetNode', '656',
        widget_0='negative',
        CONDITIONING=cliptextencode.out(0),
    )
    comfymathexpression_2 = _node(wf, 'ComfyMathExpression', '700',
        widget_0='a/b',
        _extras={'values.a': getimagesizeandcount_2.out(3), 'values.b': getnode_25.out(0)},
    )
    getimagerangefrombatch_2 = _node(wf, 'GetImageRangeFromBatch', '714',
        widget_0=0,
        widget_1=1,
        images=resizeimagemasknode_3.out(0),
    )
    facesegment = _node(wf, 'FaceSegment', '761',
        widget_0=True,
        widget_1=True,
        widget_10=True,
        widget_11=True,
        widget_12=False,
        widget_13=False,
        widget_14=False,
        widget_15=512,
        widget_16=0,
        widget_17=10,
        widget_18=False,
        widget_19='Alpha',
        widget_2=False,
        widget_20='#222222',
        widget_3=True,
        widget_4=True,
        widget_5=True,
        widget_6=True,
        widget_7=True,
        widget_8=True,
        widget_9=True,
        images=resizeimagemasknode_3.out(0),
    )
    getimagerangefrombatch_4 = _node(wf, 'GetImageRangeFromBatch', '806',
        widget_0=-1,
        widget_1=1,
        images=resizeimagemasknode.out(0),
    )
    setnode_24 = _node(wf, 'SetNode', '849',
        widget_0='latent_audio_selected',
        LATENT=comfyswitchnode.out(0),
    )
    trimaudioduration = _node(wf, 'TrimAudioDuration', '859',
        widget_0=0,
        widget_1=40,
        audio=loadaudio.out(0),
        duration=simplecalculatorkj_2.out(0),
    )
    setnode_31 = _node(wf, 'SetNode', '883',
        widget_0='width_generated',
        INT=getimagesizeandcount_2.out(1),
    )
    setnode_32 = _node(wf, 'SetNode', '884',
        widget_0='height_generated',
        INT=getimagesizeandcount_2.out(2),
    )
    basicscheduler = _node(wf, 'BasicScheduler', '164',
        scheduler=1,
        steps=1,
        denoise=1,
        widget_1=15,
        model=modelsamplingsd3.out(0),
    )
    simplecalculatorkj = _node(wf, 'SimpleCalculatorKJ', '500',
        widget_0='(a > c) or (b > c) ',
        _extras={'variables.a': vhs_videoinfo.out(8), 'variables.b': vhs_videoinfo.out(9), 'variables.c': getnode_15.out(0)},
    )
    setnode_18 = _node(wf, 'SetNode', '651',
        widget_0='model_n_nag',
        MODEL=ltx2_nag.out(0),
    )
    setnode_19 = _node(wf, 'SetNode', '655',
        widget_0='positive',
        CONDITIONING=cliptextencode_2.out(0),
    )
    comfymathexpression_3 = _node(wf, 'ComfyMathExpression', '701',
        widget_0='a+b',
        _extras={'values.a': comfymathexpression_2.out(0), 'values.b': getnode_10.out(0)},
    )
    blockifymask = _node(wf, 'BlockifyMask', '790',
        widget_0=12,
        widget_1='cpu',
        masks=facesegment.out(1),
    )
    vaeencode_2 = _node(wf, 'VAEEncode', '809',
        pixels=getimagerangefrombatch_4.out(0),
        vae=getnode_35.out(0),
    )
    setnode_25 = _node(wf, 'SetNode', '852',
        widget_0='audio_original',
        AUDIO=trimaudioduration.out(0),
    )
    melbandroformersampler = _node(wf, 'MelBandRoFormerSampler', '860',
        audio=trimaudioduration.out(0),
        model=melbandroformermodelloader.out(0),
    )
    setnode_29 = _node(wf, 'SetNode', '871',
        widget_0='frames_loaded',
        INT=vhs_videoinfo.out(6),
    )
    lazyswitchkj = _node(wf, 'LazySwitchKJ', '504',
        widget_0=False,
        on_false=reroute.out(0),
        on_true=resizeimagesbylongeredge_2.out(0),
        switch=simplecalculatorkj.out(2),
    )
    ltxvchunkfeedforward = _node(wf, 'LTXVChunkFeedForward', '522',
        widget_0=2,
        widget_1=4096,
        model=pathchsageattentionkj.out(0),
    )
    resizeimagemasknode_2 = _node(wf, 'ResizeImageMaskNode', '717',
        widget_0='match size',
        widget_1=256,
        widget_2='nearest-exact',
        input=blockifymask.out(0),
        _extras={'resize_type.match': getimagerangefrombatch_2.out(0)},
    )
    masktoimage = _node(wf, 'MaskToImage', '791',
        mask=blockifymask.out(0),
    )
    setnode_26 = _node(wf, 'SetNode', '853',
        widget_0='audio_vocals',
        AUDIO=melbandroformersampler.out(0),
    )
    comfyswitchnode_2 = _node(wf, 'ComfySwitchNode', '868',
        widget_0=True,
        on_false=trimaudioduration.out(0),
        on_true=melbandroformersampler.out(0),
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
    ltxvpreprocessmasks = _node(wf, 'LTXVPreprocessMasks', '720',
        widget_0=False,
        widget_1=False,
        widget_2='max',
        widget_3=0,
        widget_4=True,
        widget_5=0.5,
        widget_6=1,
        masks=resizeimagemasknode_2.out(0),
        vae=getnode_29.out(0),
    )
    getimagerangefrombatch_3 = _node(wf, 'GetImageRangeFromBatch', '775',
        widget_0=0,
        widget_1=1,
        images=masktoimage.out(0),
    )
    ltxvaudiovaeencode = _node(wf, 'LTXVAudioVAEEncode', '866',
        audio=comfyswitchnode_2.out(0),
        audio_vae=getnode_44.out(0),
    )
    setnode_28 = _node(wf, 'SetNode', '867',
        widget_0='audio',
        AUDIO=comfyswitchnode_2.out(0),
    )
    imageresizekjv2 = _node(wf, 'ImageResizeKJv2', '512',
        widget_0=512,
        widget_1=512,
        widget_2='nearest-exact',
        widget_3='crop',
        widget_4='0, 0, 0',
        widget_5='center',
        widget_6=64,
        widget_7='cpu',
        height=getimagesizeandcount.out(2),
        image=getimagesizeandcount.out(0),
        width=getimagesizeandcount.out(1),
    )
    power_lora_loader__rgthree_ = _node(wf, 'Power Lora Loader (rgthree)', '660',
        widget_3='',
        model=ltx2attentiontunerpatch.out(0),
    )
    previewimage = _node(wf, 'PreviewImage', '763',
        images=getimagerangefrombatch_3.out(0),
    )
    ltxvsetvideolatentnoisemasks = _node(wf, 'LTXVSetVideoLatentNoiseMasks', '794',
        masks=ltxvpreprocessmasks.out(0),
        samples=vaeencode.out(0),
    )
    setlatentnoisemask = _node(wf, 'SetLatentNoiseMask', '864',
        mask=solidmask.out(0),
        samples=ltxvaudiovaeencode.out(0),
    )
    ltxvaudiovideomask = _node(wf, 'LTXVAudioVideoMask', '178',
        widget_0=24,
        widget_1=0,
        widget_2=15,
        widget_3=0,
        widget_4=10000,
        widget_5='pad',
        widget_6='add',
        audio_end_time=comfymathexpression_3.out(0),
        audio_latent=ltxvemptylatentaudio.out(0),
        video_end_time=comfymathexpression_3.out(0),
        video_fps=getnode_25.out(0),
        video_latent=ltxvsetvideolatentnoisemasks.out(0),
        video_start_time=comfymathexpression_2.out(0),
    )
    setnode = _node(wf, 'SetNode', '207',
        widget_0='width',
        INT=imageresizekjv2.out(1),
    )
    setnode_2 = _node(wf, 'SetNode', '208',
        widget_0='height',
        INT=imageresizekjv2.out(2),
    )
    setnode_7 = _node(wf, 'SetNode', '328',
        widget_0='ref_video',
        IMAGE=imageresizekjv2.out(0),
    )
    getimagerangefrombatch = _node(wf, 'GetImageRangeFromBatch', '440',
        widget_0=0,
        widget_1=1,
        images=imageresizekjv2.out(0),
    )
    setnode_14 = _node(wf, 'SetNode', '481',
        widget_0='model',
        MODEL=power_lora_loader__rgthree_.out(0),
    )
    setnode_27 = _node(wf, 'SetNode', '863',
        widget_0='latent_custom_audio',
        LATENT=setlatentnoisemask.out(0),
    )
    resizeimagesbylongeredge = _node(wf, 'ResizeImagesByLongerEdge', '495',
        widget_0=1536,
        images=getimagerangefrombatch.out(0),
    )
    ltxvaddlatentguide = _node(wf, 'LTXVAddLatentGuide', '799',
        widget_0=-1,
        widget_1=0.7,
        guiding_latent=vaeencode_2.out(0),
        latent=ltxvaudiovideomask.out(0),
        latent_idx=getimagesizeandcount_2.out(3),
        negative=ltxvconditioning.out(1),
        positive=ltxvconditioning.out(0),
        strength=getnode_36.out(0),
        vae=getnode_35.out(0),
    )
    setnode_30 = _node(wf, 'SetNode', '876',
        widget_0='latent_audio',
        LATENT=ltxvaudiovideomask.out(1),
    )
    cfgguider = _node(wf, 'CFGGuider', '129',
        cfg=2.5,
        model=getnode_28.out(0),
        negative=ltxvaddlatentguide.out(1),
        positive=ltxvaddlatentguide.out(0),
    )
    setnode_6 = _node(wf, 'SetNode', '294',
        widget_0='ref_image',
        IMAGE=resizeimagesbylongeredge.out(0),
    )
    ltxvpreprocess = _node(wf, 'LTXVPreprocess', '299',
        widget_0=18,
        image=resizeimagesbylongeredge.out(0),
    )
    ltxvimgtovideoinplace_2 = _node(wf, 'LTXVImgToVideoInplace', '730',
        widget_0=0.7,
        widget_1=False,
        image=getnode_32.out(0),
        latent=ltxvaddlatentguide.out(2),
        vae=getnode_31.out(0),
    )
    setnode_22 = _node(wf, 'SetNode', '820',
        widget_0='positive_to_crop',
        CONDITIONING=ltxvaddlatentguide.out(0),
    )
    setnode_23 = _node(wf, 'SetNode', '821',
        widget_0='negative_to_crop',
        CONDITIONING=ltxvaddlatentguide.out(1),
    )
    ltxvconcatavlatent = _node(wf, 'LTXVConcatAVLatent', '109',
        audio_latent=getnode_50.out(0),
        video_latent=ltxvimgtovideoinplace_2.out(0),
    )
    setnode_5 = _node(wf, 'SetNode', '285',
        widget_0='compress_image',
        IMAGE=ltxvpreprocess.out(0),
    )
    samplercustomadvanced = _node(wf, 'SamplerCustomAdvanced', '113',
        guider=cfgguider.out(0),
        latent_image=ltxvconcatavlatent.out(0),
        noise=randomnoise.out(0),
        sampler=ksamplerselect.out(0),
        sigmas=manualsigmas_2.out(0),
    )
    ltxvseparateavlatent_2 = _node(wf, 'LTXVSeparateAVLatent', '250',
        av_latent=samplercustomadvanced.out(0),
    )
    ltxvcropguides = _node(wf, 'LTXVCropGuides', '810',
        latent=ltxvseparateavlatent_2.out(0),
        negative=getnode_38.out(0),
        positive=getnode_37.out(0),
    )
    ltxvimgtovideoinplace = _node(wf, 'LTXVImgToVideoInplace', '438',
        widget_0=1,
        widget_1=False,
        image=getnode_13.out(0),
        latent=ltxvcropguides.out(2),
        vae=getnode_14.out(0),
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
    ltxvcropguides_2 = _node(wf, 'LTXVCropGuides', '824',
        latent=ltxvseparateavlatent.out(0),
        negative=getnode_39.out(0),
        positive=getnode_40.out(0),
    )
    vaedecode = _node(wf, 'VAEDecode', '527',
        samples=ltxvcropguides_2.out(2),
        vae=getnode_5.out(0),
    )
    setnode_17 = _node(wf, 'SetNode', '648',
        widget_0='final_audio',
        AUDIO=ltxvaudiovaedecode.out(0),
    )
    setnode_8 = _node(wf, 'SetNode', '451',
        widget_0='final_video',
        IMAGE=vaedecode.out(0),
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
