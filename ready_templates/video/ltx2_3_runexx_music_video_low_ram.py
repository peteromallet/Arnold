# vibecomfy: generated — converted by tools/convert_ready_templates.py
# Edits will be overwritten on regeneration. Add a `# vibecomfy: manual`
# marker on the first line if hand-editing is required.
"""Auto-generated ready_template — see tools/convert_ready_templates.py."""
from __future__ import annotations

from vibecomfy.workflow import VibeWorkflow, WorkflowSource
from vibecomfy.registry.ready_template import apply_ready_template_policy


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

    getnode = _node(wf, 'GetNode', '236',
        widget_0='vae',
    )
    getnode_2 = _node(wf, 'GetNode', '413',
        widget_0='vae',
    )
    loadimage = _node(wf, 'LoadImage', '444',
        image='download (8).png',
        widget_1='image',
    )
    getnode_3 = _node(wf, 'GetNode', '582',
        widget_0='audio_original',
    )
    intconstant = _node(wf, 'INTConstant', '1527',
        widget_0=1000,
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
    vaeloaderkj = _node(wf, 'VAELoaderKJ', '1567',
        widget_0='LTX23_audio_vae_bf16.safetensors',
        widget_1='main_device',
        widget_2='bf16',
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
    primitivefloat = _node(wf, 'PrimitiveFloat', '1586',
        value=8,
    )
    intconstant_2 = _node(wf, 'INTConstant', '1591',
        widget_0=480,
    )
    loadaudio = _node(wf, 'LoadAudio', '1594',
        audio='ComfyUI_00152_.mp3',
    )
    getnode_4 = _node(wf, 'GetNode', '1595',
        widget_0='height',
    )
    getnode_5 = _node(wf, 'GetNode', '1597',
        widget_0='vae_audio',
    )
    melbandroformermodelloader = _node(wf, 'MelBandRoFormerModelLoader', '1600',
        widget_0='MelBandRoformer\\MelBandRoformer_fp16.safetensors',
    )
    getnode_6 = _node(wf, 'GetNode', '1601',
        widget_0='width',
    )
    intconstant_3 = _node(wf, 'INTConstant', '1606',
        widget_0=832,
    )
    getnode_7 = _node(wf, 'GetNode', '1622',
        widget_0='clip',
    )
    primitivestringmultiline = _node(wf, 'PrimitiveStringMultiline', '1624',
        value='Make this image come alive with fluid motion. Cinematic music video shot of a red haired woman. \n\nShe sings with expressive motion and gesticulation. \nThe song she is singing is a sweet slow melancolic melody. Her lips moves in perfect lip-sync to the attached audio.  \n\nShe is walking through a mystical dreamy forrest, tracking camera as she walks towards the viewer. \nThe camera pulls away slowly keeping same distance to the woman. \n\nCinematic, volumetric lights, shadow play. \n\nIMPORTANT: The woman is singing, and her lips are moving with lip-sync to the lyrics of the song.',
    )
    getnode_8 = _node(wf, 'GetNode', '1628',
        widget_0='width',
    )
    getnode_9 = _node(wf, 'GetNode', '1629',
        widget_0='height',
    )
    getnode_10 = _node(wf, 'GetNode', '1635',
        widget_0='frames',
    )
    getnode_11 = _node(wf, 'GetNode', '1636',
        widget_0='fps',
    )
    getnode_12 = _node(wf, 'GetNode', '1654',
        widget_0='window_sec_01',
    )
    primitivefloat_2 = _node(wf, 'PrimitiveFloat', '1722',
        value=8,
    )
    primitivestringmultiline_2 = _node(wf, 'PrimitiveStringMultiline', '1805',
        value='Make this image come alive with fluid motion. Cinematic music video shot of a red haired woman. \n\nShe sings with expressive motion and gesticulation. \nThe song she is singing is a sweet slow melancolic melody. Her lips moves in perfect lip-sync to the attached audio.  \n\nShe is walking through a romantic greenhouse with flowers and warm light, tracking camera as she walks towards the viewer.\n\nShe sings the lyrics: "I type a whisper, watch it bloom. In pixel fog and quiet rooms. A hundred frames begin to breathe. While melodies I couldn’t weave" \n\nCinematic, volumetric lights, shadow play.\n\nIMPORTANT: The woman is singing, and her lips are moving with lip-sync to the lyrics of the song.',
    )
    primitivefloat_3 = _node(wf, 'PrimitiveFloat', '1997',
        value=8,
    )
    primitivefloat_4 = _node(wf, 'PrimitiveFloat', '2012',
        value=8,
    )
    getnode_13 = _node(wf, 'GetNode', '2110',
        widget_0='clip',
    )
    getnode_14 = _node(wf, 'GetNode', '2111',
        widget_0='enhance_prompt',
    )
    getnode_15 = _node(wf, 'GetNode', '2113',
        widget_0='ref_image',
    )
    primitiveboolean = _node(wf, 'PrimitiveBoolean', '2116',
        value=False,
    )
    getnode_16 = _node(wf, 'GetNode', '2151',
        widget_0='vae',
    )
    getnode_17 = _node(wf, 'GetNode', '2152',
        widget_0='upscale_model',
    )
    getnode_18 = _node(wf, 'GetNode', '2154',
        widget_0='negative_base',
    )
    getnode_19 = _node(wf, 'GetNode', '2155',
        widget_0='positive_base',
    )
    getnode_20 = _node(wf, 'GetNode', '2157',
        widget_0='ref_image',
    )
    getnode_21 = _node(wf, 'GetNode', '2161',
        widget_0='positive_base',
    )
    getnode_22 = _node(wf, 'GetNode', '2162',
        widget_0='positive_base',
    )
    getnode_23 = _node(wf, 'GetNode', '2164',
        widget_0='vae_tiny',
    )
    getnode_24 = _node(wf, 'GetNode', '2165',
        widget_0='model_with_lora',
    )
    getnode_25 = _node(wf, 'GetNode', '2166',
        widget_0='model',
    )
    getnode_26 = _node(wf, 'GetNode', '2167',
        widget_0='negative_base',
    )
    randomnoise = _node(wf, 'RandomNoise', '2169',
        noise_seed=420,
        control_after_generate='fixed',
    )
    getnode_27 = _node(wf, 'GetNode', '2171',
        widget_0='model',
    )
    getnode_28 = _node(wf, 'GetNode', '2172',
        widget_0='model',
    )
    ksamplerselect = _node(wf, 'KSamplerSelect', '2174',
        sampler_name='euler_cfg_pp',
    )
    manualsigmas = _node(wf, 'ManualSigmas', '2176',
        widget_0='0.85, 0.7250, 0.4219, 0.0',
    )
    randomnoise_2 = _node(wf, 'RandomNoise', '2179',
        noise_seed=42,
        control_after_generate='fixed',
    )
    ksamplerselect_2 = _node(wf, 'KSamplerSelect', '2180',
        sampler_name='euler_ancestral_cfg_pp',
    )
    manualsigmas_2 = _node(wf, 'ManualSigmas', '2187',
        widget_0='1.0, 0.99375, 0.9875, 0.98125, 0.975, 0.909375, 0.725, 0.421875, 0.0',
    )
    getnode_29 = _node(wf, 'GetNode', '2190',
        widget_0='ref_image',
    )
    getnode_30 = _node(wf, 'GetNode', '2191',
        widget_0='width_downscaled',
    )
    getnode_31 = _node(wf, 'GetNode', '2192',
        widget_0='height_downscaled',
    )
    getnode_32 = _node(wf, 'GetNode', '2198',
        widget_0='image_strength',
    )
    primitiveint = _node(wf, 'PrimitiveInt', '2284',
        value=5,
        widget_1='fixed',
    )
    n_5e410bb1_405a_4d3d_808b_8f5f29426943 = _node(wf, '5e410bb1-405a-4d3d-808b-8f5f29426943', '3877')
    primitivestring = _node(wf, 'PrimitiveString', '4119',
        value='mynewvideo',
    )
    getnode_33 = _node(wf, 'GetNode', '4204',
        widget_0='initial_frames_count',
    )
    getnode_34 = _node(wf, 'GetNode', '4710',
        widget_0='fps',
    )
    getnode_35 = _node(wf, 'GetNode', '4711',
        widget_0='foldername',
    )
    getnode_36 = _node(wf, 'GetNode', '4724',
        widget_0='temp_name',
    )
    getnode_37 = _node(wf, 'GetNode', '4727',
        widget_0='fps',
    )
    getnode_38 = _node(wf, 'GetNode', '4728',
        widget_0='foldername',
    )
    getnode_39 = _node(wf, 'GetNode', '4729',
        widget_0='fps',
    )
    primitiveboolean_2 = _node(wf, 'PrimitiveBoolean', '4736',
        value=True,
    )
    primitiveboolean_3 = _node(wf, 'PrimitiveBoolean', '4740',
        value=True,
    )
    loadimage_2 = _node(wf, 'LoadImage', '4750',
        image='download (1).png',
        widget_1='image',
    )
    getnode_40 = _node(wf, 'GetNode', '5065',
        widget_0='foldername',
    )
    getnode_41 = _node(wf, 'GetNode', '5066',
        widget_0='fps',
    )
    primitiveboolean_4 = _node(wf, 'PrimitiveBoolean', '5067',
        value=True,
    )
    primitivestringmultiline_3 = _node(wf, 'PrimitiveStringMultiline', '5068',
        value='Make this image come alive with fluid motion. Cinematic music video shot of a red haired woman. \n\nShe sings with expressive motion and gesticulation. \nThe song she is singing is a sweet slow melancolic melody. Her lips moves in perfect lip-sync to the attached audio.  \n\nShe is sitting down at the stage at an abandoned teather.  The camera slowly orbits around the woman, the woman is always looking at the viewer.\n\nShe sings the lyrics: "Now rise from weights, unchained and free.\nLike open doors for you and me.\nAnd every node connects the light. To hands that build without a figh.  No locked gates, just open skies.Where anyone can close their eyes…".\n\n\nCinematic, volumetric lights, shadow play.\n\nIMPORTANT: The woman is singing, and her lips are moving with lip-sync to the lyrics of the song.',
    )
    getnode_42 = _node(wf, 'GetNode', '5070',
        widget_0='initial_frames_count',
    )
    primitivefloat_5 = _node(wf, 'PrimitiveFloat', '5071',
        value=8,
    )
    primitiveint_2 = _node(wf, 'PrimitiveInt', '5072',
        value=5,
        widget_1='fixed',
    )
    loadimage_3 = _node(wf, 'LoadImage', '5074',
        image='download (6).png',
        widget_1='image',
    )
    getnode_43 = _node(wf, 'GetNode', '5140',
        widget_0='foldername',
    )
    getnode_44 = _node(wf, 'GetNode', '5141',
        widget_0='fps',
    )
    primitiveboolean_5 = _node(wf, 'PrimitiveBoolean', '5142',
        value=True,
    )
    primitivestringmultiline_4 = _node(wf, 'PrimitiveStringMultiline', '5143',
        value='Make this image come alive with fluid motion. Cinematic music video shot of a red haired woman. \n\nShe sings with expressive motion and gesticulation. \nThe song she is singing is a sweet slow melancolic melody. Her lips moves in perfect lip-sync to the attached audio.  \n\nShe is sitting down at a piece of drift-wood at the beach, at dusk. Soft light from a cloudy sky. \n\n\nShe sings the lyrics: " … and dream. Oh, AceStep XL, you paint my dreams. ComfyUI, you stitch the seams. Of every film, each trembling tone. Where lonely sparks now feel at home".\n\nShe sings for a bit before she stands up and walks towards the viewer. \n\nThe camera slowly pulls in closer to the woman singing. \n\n\nCinematic, volumetric lights, shadow play.\n\nIMPORTANT: The woman is singing, and her lips are moving with lip-sync to the lyrics of the song.',
    )
    getnode_45 = _node(wf, 'GetNode', '5145',
        widget_0='initial_frames_count',
    )
    primitivefloat_6 = _node(wf, 'PrimitiveFloat', '5146',
        value=8,
    )
    primitiveint_3 = _node(wf, 'PrimitiveInt', '5147',
        value=5,
        widget_1='fixed',
    )
    loadimage_4 = _node(wf, 'LoadImage', '5149',
        image='download (2).png',
        widget_1='image',
    )
    getnode_46 = _node(wf, 'GetNode', '5215',
        widget_0='foldername',
    )
    getnode_47 = _node(wf, 'GetNode', '5216',
        widget_0='fps',
    )
    primitiveboolean_6 = _node(wf, 'PrimitiveBoolean', '5217',
        value=True,
    )
    primitivestringmultiline_5 = _node(wf, 'PrimitiveStringMultiline', '5218',
        value='Make this image come alive with fluid motion. Cinematic music video shot of a red haired woman. \n\nShe sings with expressive motion and gesticulation. \nThe song she is singing is a sweet slow melancolic melody. Her lips moves in perfect lip-sync to the attached audio.  \n\nShe is standing on a rooftop balcony with the city behind her, at night. Camera slowly orbits around her, with her always looking towards the viewer as she sings. \n\nShe sings the lyrics: "Thank you, Kijai, for the quiet grace. That smoothed the path through digital space. We dream in code, we dream in blue. And every open door leads through.......". \n\nThe camera slowly pulls in closer to the woman singing. \n\n\nCinematic, volumetric lights, shadow play.\n\nIMPORTANT: The woman is singing, and her lips are moving with lip-sync to the lyrics of the song.',
    )
    getnode_48 = _node(wf, 'GetNode', '5220',
        widget_0='initial_frames_count',
    )
    primitivefloat_7 = _node(wf, 'PrimitiveFloat', '5221',
        value=8,
    )
    primitiveint_4 = _node(wf, 'PrimitiveInt', '5222',
        value=5,
        widget_1='fixed',
    )
    loadimage_5 = _node(wf, 'LoadImage', '5224',
        image='download (12).png',
        widget_1='image',
    )
    getnode_49 = _node(wf, 'GetNode', '5226',
        widget_0='final_frames',
    )
    getnode_50 = _node(wf, 'GetNode', '5227',
        widget_0='audio_original',
    )
    emptyltxvlatentvideo = _node(wf, 'EmptyLTXVLatentVideo', '344',
        batch_size=1,
        widget_0=256,
        widget_1=256,
        widget_2=5,
        width=getnode_30.out(0),
        height=getnode_31.out(0),
        length=getnode_10.out(0),
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
        height=getnode_9.out(0),
        image=loadimage.out(0),
        width=getnode_8.out(0),
    )
    ltxvpreprocess = _node(wf, 'LTXVPreprocess', '446',
        widget_0=18,
        image=getnode_29.out(0),
    )
    setnode_4 = _node(wf, 'SetNode', '1528',
        widget_0='start_seed',
        INT=intconstant.out(0),
    )
    setnode_5 = _node(wf, 'SetNode', '1555',
        widget_0='upscale_model',
        LATENT_UPSCALE_MODEL=latentupscalemodelloader.out(0),
    )
    setnode_6 = _node(wf, 'SetNode', '1556',
        widget_0='vae_audio',
        VAE=vaeloaderkj.out(0),
    )
    setnode_7 = _node(wf, 'SetNode', '1557',
        widget_0='vae',
        VAE=vaeloader.out(0),
    )
    setnode_8 = _node(wf, 'SetNode', '1558',
        widget_0='clip',
        CLIP=dualcliploader.out(0),
    )
    loraloadermodelonly = _node(wf, 'LoraLoaderModelOnly', '1560',
        lora_name='LTX\\LTX-2\\ltx-2.3-22b-distilled-lora-384.safetensors',
        strength_model=0.6,
        model=unetloader.out(0),
    )
    setnode_9 = _node(wf, 'SetNode', '1568',
        widget_0='vae_tiny',
        VAE=vaeloader_2.out(0),
    )
    setnode_10 = _node(wf, 'SetNode', '1575',
        widget_0='height',
        INT=intconstant_2.out(0),
    )
    setnode_11 = _node(wf, 'SetNode', '1576',
        widget_0='width',
        INT=intconstant_3.out(0),
    )
    setnode_12 = _node(wf, 'SetNode', '1577',
        widget_0='fps',
        FLOAT=primitivefloat.out(0),
    )
    trimaudioduration = _node(wf, 'TrimAudioDuration', '1598',
        widget_0=11,
        widget_1=40,
        audio=loadaudio.out(0),
        duration=n_5e410bb1_405a_4d3d_808b_8f5f29426943.out(0),
    )
    solidmask = _node(wf, 'SolidMask', '1604',
        widget_0=0,
        widget_1=512,
        widget_2=512,
        height=getnode_4.out(0),
        width=getnode_6.out(0),
    )
    cliptextencode_2 = _node(wf, 'CLIPTextEncode', '1626',
        text='text, subtitles, logo, still image, still video, no motion, static, frozen, blurry, low quality, distorted, bad anatomy, oversaturated, pixelated, low resolution, grainy, compression artifacts, jpeg artifacts, glitches, watermark, signature, copyright,  distortedsound, saturated sound, loud sound , deformed facial features, asymmetrical face, missing facial features, extra limbs, disfigured hands, blurry teeth, disfigured teeth',
        clip=getnode_7.out(0),
    )
    simplecalculatorkj = _node(wf, 'SimpleCalculatorKJ', '1651',
        widget_0='((round((a * b -1) / 8)) * 8) + 1 ',
        _extras={'variables.a': primitivefloat_4.out(0), 'variables.b': primitivefloat.out(0)},
    )
    setnode_22 = _node(wf, 'SetNode', '1738',
        widget_0='image_strength',
        FLOAT=primitivefloat_2.out(0),
    )
    n_3bd4eeb9_31fa_461a_8c04_2b24dd0aabaf = _node(wf, '3bd4eeb9-31fa-461a-8c04-2b24dd0aabaf', '2109',
        _1=primitivestringmultiline.out(0),
        clip=getnode_13.out(0),
        image=getnode_15.out(0),
    )
    setnode_25 = _node(wf, 'SetNode', '2115',
        widget_0='enhance_prompt',
        BOOLEAN=primitiveboolean.out(0),
    )
    cfgguider = _node(wf, 'CFGGuider', '2170',
        cfg=2.5,
        model=getnode_25.out(0),
        negative=getnode_21.out(0),
        positive=getnode_22.out(0),
    )
    modelsamplingsd3 = _node(wf, 'ModelSamplingSD3', '2175',
        shift=13,
        model=getnode_27.out(0),
    )
    cfgguider_2 = _node(wf, 'CFGGuider', '2177',
        cfg=2.5,
        model=getnode_27.out(0),
        negative=getnode_18.out(0),
        positive=getnode_19.out(0),
    )
    modelsamplingsd3_2 = _node(wf, 'ModelSamplingSD3', '2185',
        shift=13,
        model=getnode_28.out(0),
    )
    ltx2samplingpreviewoverride = _node(wf, 'LTX2SamplingPreviewOverride', '2188',
        widget_0=8,
        model=getnode_24.out(0),
        vae=getnode_23.out(0),
    )
    setnode_28 = _node(wf, 'SetNode', '2196',
        widget_0='sampler',
        SAMPLER=ksamplerselect_2.out(0),
    )
    setnode_30 = _node(wf, 'SetNode', '2314',
        widget_0='sigmas_2',
        SIGMAS=manualsigmas.out(0),
    )
    setnode_31 = _node(wf, 'SetNode', '2315',
        widget_0='sampler_2',
        SAMPLER=ksamplerselect.out(0),
    )
    setnode_32 = _node(wf, 'SetNode', '2325',
        widget_0='window_sec_02',
        FLOAT=primitivefloat_3.out(0),
    )
    c4106aee_ad7a_4925_972b_6f5b3d34db6e = _node(wf, 'c4106aee-ad7a-4925-972b-6f5b3d34db6e', '2329',
        _1=primitivestringmultiline_2.out(0),
        _2=primitivefloat_3.out(0),
        _4=getnode_33.out(0),
        images=loadimage_2.out(0),
        noise_seed=primitiveint.out(0),
    )
    setnode_33 = _node(wf, 'SetNode', '3722',
        widget_0='window_sec_01',
        FLOAT=primitivefloat_4.out(0),
    )
    stringconcatenate = _node(wf, 'StringConcatenate', '4164',
        widget_0='MusicVideo',
        widget_1='',
        widget_2='\\',
        string_b=primitivestring.out(0),
    )
    stringconcatenate_3 = _node(wf, 'StringConcatenate', '4743',
        widget_0='output\\MusicVideo',
        widget_1='',
        widget_2='\\',
        string_b=getnode_36.out(0),
    )
    setnode_37 = _node(wf, 'SetNode', '4995',
        widget_0='sigmas',
        SIGMAS=manualsigmas_2.out(0),
    )
    setnode_38 = _node(wf, 'SetNode', '5064',
        widget_0='window_sec_03',
        FLOAT=primitivefloat_5.out(0),
    )
    setnode_39 = _node(wf, 'SetNode', '5139',
        widget_0='window_sec_04',
        FLOAT=primitivefloat_6.out(0),
    )
    setnode_40 = _node(wf, 'SetNode', '5214',
        widget_0='window_sec_05',
        FLOAT=primitivefloat_7.out(0),
    )
    setnode_41 = _node(wf, 'SetNode', '5225',
        widget_0='temp_name',
        STRING=primitivestring.out(0),
    )
    simplecalculatorkj_2 = _node(wf, 'SimpleCalculatorKJ', '5228',
        widget_0='a + 100',
        _extras={'variables.a': getnode_49.out(0)},
    )
    pathchsageattentionkj = _node(wf, 'PathchSageAttentionKJ', '268',
        widget_0='auto',
        widget_1=False,
        model=loraloadermodelonly.out(0),
    )
    setnode_13 = _node(wf, 'SetNode', '1578',
        widget_0='frames',
        INT=simplecalculatorkj.out(1),
    )
    setnode_14 = _node(wf, 'SetNode', '1589',
        widget_0='audio_original',
        AUDIO=trimaudioduration.out(0),
    )
    melbandroformersampler = _node(wf, 'MelBandRoFormerSampler', '1599',
        audio=trimaudioduration.out(0),
        model=melbandroformermodelloader.out(0),
    )
    cliptextencode = _node(wf, 'CLIPTextEncode', '1621',
        widget_0='= Enhanced Prompt = \n',
        text=n_3bd4eeb9_31fa_461a_8c04_2b24dd0aabaf.out(0),
        clip=getnode_7.out(0),
    )
    resizeimagemasknode = _node(wf, 'ResizeImageMaskNode', '1630',
        widget_0='scale by multiplier',
        widget_1=256,
        widget_2='area',
        input=imageresizekjv2.out(0),
    )
    basicscheduler = _node(wf, 'BasicScheduler', '2173',
        scheduler=1,
        steps=1,
        denoise=1,
        widget_1=4,
        model=modelsamplingsd3.out(0),
    )
    ltx2_nag = _node(wf, 'LTX2_NAG', '2178',
        widget_0=11,
        widget_1=0.25,
        widget_2=2.5,
        widget_3=True,
        model=ltx2samplingpreviewoverride.out(0),
        nag_cond_audio=getnode_26.out(0),
        nag_cond_video=getnode_26.out(0),
    )
    basicscheduler_2 = _node(wf, 'BasicScheduler', '2186',
        scheduler=1,
        steps=1,
        denoise=1,
        widget_1=10,
        model=modelsamplingsd3_2.out(0),
    )
    resizeimagesbylongeredge = _node(wf, 'ResizeImagesByLongerEdge', '2189',
        widget_0=1536,
        images=imageresizekjv2.out(0),
    )
    setnode_27 = _node(wf, 'SetNode', '2195',
        widget_0='guider',
        GUIDER=cfgguider.out(0),
    )
    setnode_29 = _node(wf, 'SetNode', '2313',
        widget_0='guider_2',
        GUIDER=cfgguider_2.out(0),
    )
    ltxvimgtovideoinplace_2 = _node(wf, 'LTXVImgToVideoInplace', '4109',
        widget_0=1,
        widget_1=False,
        image=ltxvpreprocess.out(0),
        latent=emptyltxvlatentvideo.out(0),
        vae=getnode_2.out(0),
    )
    loadvideosfromfolder = _node(wf, 'LoadVideosFromFolder', '4708',
        widget_0='output\\MusicVideo',
        widget_1=0,
        widget_2=0,
        widget_3=0,
        widget_4=0,
        widget_5=0,
        widget_6=1,
        widget_7='batch',
        widget_8=4,
        widget_9=False,
        frame_load_cap=simplecalculatorkj_2.out(1),
        video=stringconcatenate_3.out(0),
    )
    vhs_videocombine = _node(wf, 'VHS_VideoCombine', '4709',
        audio=c4106aee_ad7a_4925_972b_6f5b3d34db6e.out(2),
        filename_prefix=getnode_35.out(0),
        frame_rate=getnode_34.out(0),
        images=c4106aee_ad7a_4925_972b_6f5b3d34db6e.out(1),
        save_output=primitiveboolean_2.out(0),
    )
    stringconcatenate_2 = _node(wf, 'StringConcatenate', '4735',
        widget_0='MusicVideo',
        widget_1='MusicVideo',
        widget_2='\\',
        string_a=stringconcatenate.out(0),
    )
    n_17238add_9973_482f_8fa3_248d4ed29886 = _node(wf, '17238add-9973-482f-8fa3-248d4ed29886', '5073',
        _1=primitivestringmultiline_3.out(0),
        _2=primitivefloat_5.out(0),
        _4=c4106aee_ad7a_4925_972b_6f5b3d34db6e.out(0),
        images=loadimage_3.out(0),
        noise_seed=primitiveint_2.out(0),
    )
    ltxvconditioning = _node(wf, 'LTXVConditioning', '164',
        widget_0=8,
        frame_rate=getnode_11.out(0),
        negative=cliptextencode_2.out(0),
        positive=cliptextencode.out(0),
    )
    ltxvchunkfeedforward = _node(wf, 'LTXVChunkFeedForward', '504',
        widget_0=2,
        widget_1=4096,
        model=pathchsageattentionkj.out(0),
    )
    setnode_3 = _node(wf, 'SetNode', '650',
        widget_0='ref_image',
        IMAGE=resizeimagesbylongeredge.out(0),
    )
    setnode_15 = _node(wf, 'SetNode', '1590',
        widget_0='audio_vocals',
        AUDIO=melbandroformersampler.out(0),
    )
    comfyswitchnode = _node(wf, 'ComfySwitchNode', '1616',
        widget_0=True,
        on_false=trimaudioduration.out(0),
        on_true=melbandroformersampler.out(0),
    )
    getimagesize = _node(wf, 'GetImageSize', '1631',
        image=resizeimagemasknode.out(0),
    )
    setnode_26 = _node(wf, 'SetNode', '2184',
        widget_0='model',
        MODEL=ltx2_nag.out(0),
    )
    setnode_34 = _node(wf, 'SetNode', '4121',
        widget_0='foldername',
        STRING=stringconcatenate_2.out(0),
    )
    vhs_videocombine_2 = _node(wf, 'VHS_VideoCombine', '4725',
        audio=getnode_50.out(0),
        frame_rate=getnode_37.out(0),
        images=loadvideosfromfolder.out(0),
    )
    vhs_videocombine_4 = _node(wf, 'VHS_VideoCombine', '5069',
        audio=n_17238add_9973_482f_8fa3_248d4ed29886.out(2),
        filename_prefix=getnode_40.out(0),
        frame_rate=getnode_41.out(0),
        images=n_17238add_9973_482f_8fa3_248d4ed29886.out(1),
        save_output=primitiveboolean_4.out(0),
    )
    a3fb563d_4711_4225_9210_fbe61b1bd79d = _node(wf, 'a3fb563d-4711-4225-9210-fbe61b1bd79d', '5148',
        _1=primitivestringmultiline_4.out(0),
        _2=primitivefloat_6.out(0),
        _4=n_17238add_9973_482f_8fa3_248d4ed29886.out(0),
        images=loadimage_4.out(0),
        noise_seed=primitiveint_3.out(0),
    )
    setnode = _node(wf, 'SetNode', '645',
        widget_0='positive_base',
        CONDITIONING=ltxvconditioning.out(0),
    )
    setnode_2 = _node(wf, 'SetNode', '646',
        widget_0='negative_base',
        CONDITIONING=ltxvconditioning.out(1),
    )
    ltx2attentiontunerpatch = _node(wf, 'LTX2AttentionTunerPatch', '1523',
        widget_0='',
        widget_1=1,
        widget_2=1,
        widget_3=1,
        widget_4=1,
        widget_5=True,
        model=ltxvchunkfeedforward.out(0),
    )
    setnode_17 = _node(wf, 'SetNode', '1615',
        widget_0='audio',
        AUDIO=comfyswitchnode.out(0),
    )
    setnode_19 = _node(wf, 'SetNode', '1633',
        widget_0='width_downscaled',
        INT=getimagesize.out(0),
    )
    setnode_20 = _node(wf, 'SetNode', '1634',
        widget_0='height_downscaled',
        INT=getimagesize.out(1),
    )
    trimaudioduration_2 = _node(wf, 'TrimAudioDuration', '1653',
        widget_0=0,
        widget_1=40,
        audio=comfyswitchnode.out(0),
        duration=getnode_12.out(0),
    )
    vhs_videocombine_5 = _node(wf, 'VHS_VideoCombine', '5144',
        audio=a3fb563d_4711_4225_9210_fbe61b1bd79d.out(2),
        filename_prefix=getnode_43.out(0),
        frame_rate=getnode_44.out(0),
        images=a3fb563d_4711_4225_9210_fbe61b1bd79d.out(1),
        save_output=primitiveboolean_5.out(0),
    )
    n_4acc9924_c0bd_470a_b000_46c75e61d004 = _node(wf, '4acc9924-c0bd-470a-b000-46c75e61d004', '5223',
        _1=primitivestringmultiline_5.out(0),
        _2=primitivefloat_7.out(0),
        _4=a3fb563d_4711_4225_9210_fbe61b1bd79d.out(0),
        images=loadimage_5.out(0),
        noise_seed=primitiveint_4.out(0),
    )
    ltxvaudiovaeencode = _node(wf, 'LTXVAudioVAEEncode', '1605',
        audio=trimaudioduration_2.out(0),
        audio_vae=getnode_5.out(0),
    )
    power_lora_loader__rgthree_ = _node(wf, 'Power Lora Loader (rgthree)', '2150',
        widget_7='',
        model=ltx2attentiontunerpatch.out(0),
    )
    setnode_36 = _node(wf, 'SetNode', '4733',
        widget_0='final_frames',
        INT=n_4acc9924_c0bd_470a_b000_46c75e61d004.out(0),
    )
    vhs_videocombine_6 = _node(wf, 'VHS_VideoCombine', '5219',
        audio=n_4acc9924_c0bd_470a_b000_46c75e61d004.out(2),
        filename_prefix=getnode_46.out(0),
        frame_rate=getnode_47.out(0),
        images=n_4acc9924_c0bd_470a_b000_46c75e61d004.out(1),
        save_output=primitiveboolean_6.out(0),
    )
    setlatentnoisemask = _node(wf, 'SetLatentNoiseMask', '1603',
        mask=solidmask.out(0),
        samples=ltxvaudiovaeencode.out(0),
    )
    setnode_18 = _node(wf, 'SetNode', '1617',
        widget_0='model_with_lora',
        MODEL=power_lora_loader__rgthree_.out(0),
    )
    ltxvconcatavlatent = _node(wf, 'LTXVConcatAVLatent', '350',
        audio_latent=setlatentnoisemask.out(0),
        video_latent=ltxvimgtovideoinplace_2.out(0),
    )
    setnode_16 = _node(wf, 'SetNode', '1602',
        widget_0='latent_custom_audio',
        LATENT=setlatentnoisemask.out(0),
    )
    samplercustomadvanced = _node(wf, 'SamplerCustomAdvanced', '2181',
        guider=cfgguider.out(0),
        latent_image=ltxvconcatavlatent.out(0),
        noise=randomnoise_2.out(0),
        sampler=ksamplerselect_2.out(0),
        sigmas=manualsigmas_2.out(0),
    )
    ltxvseparateavlatent_2 = _node(wf, 'LTXVSeparateAVLatent', '2159',
        av_latent=samplercustomadvanced.out(0),
    )
    ltxvimgtovideoinplace = _node(wf, 'LTXVImgToVideoInplace', '2183',
        widget_0=1,
        widget_1=False,
        image=getnode_20.out(0),
        latent=ltxvseparateavlatent_2.out(0),
        strength=getnode_32.out(0),
        vae=getnode_16.out(0),
    )
    ltxvconcatavlatent_2 = _node(wf, 'LTXVConcatAVLatent', '2153',
        audio_latent=ltxvseparateavlatent_2.out(1),
        video_latent=ltxvimgtovideoinplace.out(0),
    )
    samplercustomadvanced_2 = _node(wf, 'SamplerCustomAdvanced', '2182',
        guider=cfgguider_2.out(0),
        latent_image=ltxvconcatavlatent_2.out(0),
        noise=randomnoise.out(0),
        sampler=ksamplerselect.out(0),
        sigmas=manualsigmas.out(0),
    )
    ltxvseparateavlatent = _node(wf, 'LTXVSeparateAVLatent', '245',
        av_latent=samplercustomadvanced_2.out(0),
    )
    vaedecode = _node(wf, 'VAEDecode', '1318',
        samples=ltxvseparateavlatent.out(0),
        vae=getnode.out(0),
    )
    getimagesizeandcount = _node(wf, 'GetImageSizeAndCount', '2023',
        image=vaedecode.out(0),
    )
    vram_debug = _node(wf, 'VRAM_Debug', '4184',
        widget_0=True,
        widget_1=True,
        widget_2=False,
        image_pass=vaedecode.out(0),
    )
    vhs_videocombine_3 = _node(wf, 'VHS_VideoCombine', '4730',
        audio=getnode_3.out(0),
        filename_prefix=getnode_38.out(0),
        frame_rate=getnode_39.out(0),
        images=vaedecode.out(0),
        save_output=primitiveboolean_3.out(0),
    )
    setnode_23 = _node(wf, 'SetNode', '1938',
        widget_0='height_generated',
        INT=getimagesizeandcount.out(2),
    )
    setnode_24 = _node(wf, 'SetNode', '1939',
        widget_0='width_generated',
        INT=getimagesizeandcount.out(1),
    )
    getimagesizeandcount_2 = _node(wf, 'GetImageSizeAndCount', '4199',
        image=vram_debug.out(1),
    )
    setnode_21 = _node(wf, 'SetNode', '1716',
        widget_0='initial_frames',
        IMAGE=getimagesizeandcount_2.out(0),
    )
    setnode_35 = _node(wf, 'SetNode', '4203',
        widget_0='initial_frames_count',
        INT=getimagesizeandcount_2.out(3),
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

