# vibecomfy: generated — converted by tools/convert_ready_templates.py
# Edits will be overwritten on regeneration. Add a `# vibecomfy: manual`
# marker on the first line if hand-editing is required.
"""Auto-generated ready_template — see tools/convert_ready_templates.py."""
from __future__ import annotations

from vibecomfy.workflow import VibeWorkflow, WorkflowSource
from vibecomfy.registry.ready_template import apply_ready_template_policy


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

    manualsigmas = _node(wf, 'ManualSigmas', '100',
        widget_0='0.909375, 0.725, 0.421875, 0.0',
    )
    randomnoise = _node(wf, 'RandomNoise', '114',
        noise_seed=420,
        control_after_generate='fixed',
    )
    randomnoise_2 = _node(wf, 'RandomNoise', '115',
        noise_seed=43,
        control_after_generate='fixed',
    )
    ksamplerselect = _node(wf, 'KSamplerSelect', '137',
        sampler_name='euler_ancestral_cfg_pp',
    )
    ksamplerselect_2 = _node(wf, 'KSamplerSelect', '138',
        sampler_name='euler_cfg_pp',
    )
    loadimage = _node(wf, 'LoadImage', '167',
        image='liam-neeson-in-retribution-ra.jpg',
        widget_1='image',
    )
    vaeloader = _node(wf, 'VAELoader', '184',
        vae_name='LTX23_video_vae_bf16.safetensors',
    )
    latentupscalemodelloader = _node(wf, 'LatentUpscaleModelLoader', '189',
        widget_0='ltx-2.3-spatial-upscaler-x2-1.0.safetensors',
    )
    dualcliploader = _node(wf, 'DualCLIPLoader', '190',
        clip_name1='gemma_3_12B_it_fp4_mixed.safetensors',
        clip_name2='ltx-2.3_text_projection_bf16.safetensors',
        type='ltxv',
        device='default',
    )
    vaeloaderkj = _node(wf, 'VAELoaderKJ', '196',
        widget_0='LTX23_audio_vae_bf16.safetensors',
        widget_1='main_device',
        widget_2='bf16',
    )
    getnode = _node(wf, 'GetNode', '205',
        widget_0='frames',
    )
    getnode_2 = _node(wf, 'GetNode', '210',
        widget_0='ref_image',
    )
    getnode_3 = _node(wf, 'GetNode', '212',
        widget_0='ref_image',
    )
    getnode_4 = _node(wf, 'GetNode', '214',
        widget_0='clip',
    )
    getnode_5 = _node(wf, 'GetNode', '217',
        widget_0='vae_audio',
    )
    getnode_6 = _node(wf, 'GetNode', '218',
        widget_0='vae',
    )
    getnode_7 = _node(wf, 'GetNode', '219',
        widget_0='vae',
    )
    getnode_8 = _node(wf, 'GetNode', '220',
        widget_0='vae',
    )
    getnode_9 = _node(wf, 'GetNode', '221',
        widget_0='vae_audio',
    )
    getnode_10 = _node(wf, 'GetNode', '225',
        widget_0='model',
    )
    getnode_11 = _node(wf, 'GetNode', '228',
        widget_0='positive',
    )
    getnode_12 = _node(wf, 'GetNode', '229',
        widget_0='negative',
    )
    getnode_13 = _node(wf, 'GetNode', '230',
        widget_0='positive',
    )
    getnode_14 = _node(wf, 'GetNode', '231',
        widget_0='negative',
    )
    getnode_15 = _node(wf, 'GetNode', '236',
        widget_0='width_downsized',
    )
    getnode_16 = _node(wf, 'GetNode', '237',
        widget_0='height_downsized',
    )
    getnode_17 = _node(wf, 'GetNode', '239',
        widget_0='latent',
    )
    getnode_18 = _node(wf, 'GetNode', '242',
        widget_0='upscale_model',
    )
    getnode_19 = _node(wf, 'GetNode', '243',
        widget_0='width',
    )
    getnode_20 = _node(wf, 'GetNode', '244',
        widget_0='height',
    )
    primitivefloat = _node(wf, 'PrimitiveFloat', '285',
        value=8,
    )
    primitiveboolean = _node(wf, 'PrimitiveBoolean', '290',
        value=False,
    )
    intconstant = _node(wf, 'INTConstant', '291',
        widget_0=10,
    )
    intconstant_2 = _node(wf, 'INTConstant', '292',
        widget_0=1280,
    )
    intconstant_3 = _node(wf, 'INTConstant', '293',
        widget_0=736,
    )
    getnode_21 = _node(wf, 'GetNode', '306',
        widget_0='model_with_lora',
    )
    getnode_22 = _node(wf, 'GetNode', '307',
        widget_0='fps',
    )
    getnode_23 = _node(wf, 'GetNode', '308',
        widget_0='t2v_mode',
    )
    getnode_24 = _node(wf, 'GetNode', '309',
        widget_0='t2v_mode',
    )
    getnode_25 = _node(wf, 'GetNode', '310',
        widget_0='fps',
    )
    getnode_26 = _node(wf, 'GetNode', '322',
        widget_0='fps',
    )
    unetloader = _node(wf, 'UNETLoader', '329',
        unet_name='ltx-2.3-22b-distilled_transformer_only_fp8_scaled.safetensors',
        weight_dtype='default',
    )
    vaeloader_2 = _node(wf, 'VAELoader', '330',
        vae_name='taeltx2_3.safetensors',
    )
    getnode_27 = _node(wf, 'GetNode', '338',
        widget_0='vae_tiny',
    )
    getnode_28 = _node(wf, 'GetNode', '339',
        widget_0='model_with_lora',
    )
    getnode_29 = _node(wf, 'GetNode', '341',
        widget_0='model',
    )
    getnode_30 = _node(wf, 'GetNode', '343',
        widget_0='negative',
    )
    getnode_31 = _node(wf, 'GetNode', '344',
        widget_0='model',
    )
    unetloadergguf = _node(wf, 'UnetLoaderGGUF', '345',
        widget_0='LTXvideo\\LTX-2\\quantstack\\LTX-2.3-distilled-Q4_K_S.gguf',
    )
    dualcliploadergguf = _node(wf, 'DualCLIPLoaderGGUF', '346',
        widget_0='gemma-3-12b-it-Q2_K.gguf',
        widget_1='ltx-2.3_text_projection_bf16.safetensors',
        widget_2='sdxl',
    )
    primitivestringmultiline = _node(wf, 'PrimitiveStringMultiline', '350',
        value='You are a Creative Assistant writing concise, action-focused image-to-video prompts. Given an image (first frame) and user Raw Input Prompt, generate a prompt to guide video generation from that image.\n\n#### Guidelines:\n- Analyze the Image: Identify Subject, Setting, Elements, Style and Mood.\n- Follow user Raw Input Prompt: Include all requested motion, actions, camera movements, audio, and details. If in conflict with the image, prioritize user request while maintaining visual consistency (describe transition from image to user\'s scene).\n- Describe only changes from the image: Don\'t reiterate established visual details. Inaccurate descriptions may cause scene cuts.\n- Active language: Use present-progressive verbs ("is walking," "speaking"). If no action specified, describe natural movements.\n- Chronological flow: Use temporal connectors ("as," "then," "while").\n- Audio layer: Describe complete soundscape throughout the prompt alongside actions—NOT at the end. Align audio intensity with action tempo. Include natural background audio, ambient sounds, effects, speech or music (when requested). Be specific (e.g., "soft footsteps on tile") not vague (e.g., "ambient sound").\n- Speech (only when requested): Provide exact words in quotes with character\'s visual/voice characteristics (e.g., "The tall man speaks in a low, gravelly voice"), language if not English and accent if relevant. If general conversation mentioned without text, generate contextual quoted dialogue. (i.e., "The man is talking" input -> the output should include exact spoken words, like: "The man is talking in an excited voice saying: \'You won\'t believe what I just saw!\' His hands gesture expressively as he speaks, eyebrows raised with enthusiasm. The ambient sound of a quiet room underscores his animated speech.")\n- Style: Include visual style at beginning: "Style: <style>, <rest of prompt>." If unclear, omit to avoid conflicts.\n- Visual and audio only: Describe only what is seen and heard. NO smell, taste, or tactile sensations.\n- Restrained language: Avoid dramatic terms. Use mild, natural, understated phrasing.\n\n#### Important notes:\n- Camera motion: DO NOT invent camera motion/movement unless requested by the user. Make sure to include camera motion only if specified in the input.\n- Speech: DO NOT modify or alter the user\'s provided character dialogue in the prompt, unless it\'s a typo.\n- No timestamps or cuts: DO NOT use timestamps or describe scene cuts unless explicitly requested.\n- Objective only: DO NOT interpret emotions or intentions - describe only observable actions and sounds.\n- Format: DO NOT use phrases like "The scene opens with..." / "The video starts...". Start directly with Style (optional) and chronological scene description.\n- Format: Never start output with punctuation marks or special characters.\n- DO NOT invent dialogue unless the user mentions speech/talking/singing/conversation.\n- Your performance is CRITICAL. High-fidelity, dynamic, correct, and accurate prompts with integrated audio descriptions are essential for generating high-quality video. Your goal is flawless execution of these rules.\n\n#### Output Format (Strict):\n- Single concise paragraph in natural English. NO titles, headings, prefaces, sections, code fences, or Markdown.\n- If unsafe/invalid, return original user prompt. Never ask questions or clarifications.\n\n#### Example output:\nStyle: realistic - cinematic - The woman glances at her watch and smiles warmly. She speaks in a cheerful, friendly voice, "I think we\'re right on time!" In the background, a café barista prepares drinks at the counter. The barista calls out in a clear, upbeat tone, "Two cappuccinos ready!" The sound of the espresso machine hissing softly blends with gentle background chatter and the light clinking of cups on saucers. \n\nUSER PROMPT BELOW: \n___________________________________________________',
    )
    primitivestringmultiline_2 = _node(wf, 'PrimitiveStringMultiline', '352',
        value='Make this image come alive with fluid motion. \n\nA man with an intimidating expression speaks with expressive body language and gesticulations. \n\nHe looks at the vewer and talks, he says  : "If you say a bad word about LTX 2 point 3, i will find you.... and i will kill you" ',
    )
    getnode_32 = _node(wf, 'GetNode', '359',
        widget_0='height',
    )
    getnode_33 = _node(wf, 'GetNode', '360',
        widget_0='width',
    )
    getnode_34 = _node(wf, 'GetNode', '361',
        widget_0='vae_audio',
    )
    getnode_35 = _node(wf, 'GetNode', '368',
        widget_0='frames',
    )
    getnode_36 = _node(wf, 'GetNode', '369',
        widget_0='fps',
    )
    melbandroformermodelloader = _node(wf, 'MelBandRoFormerModelLoader', '370',
        widget_0='MelBandRoformer\\MelBandRoformer_fp16.safetensors',
    )
    loadaudio = _node(wf, 'LoadAudio', '372',
        audio='ComfyUI_00128_.mp3',
    )
    getnode_37 = _node(wf, 'GetNode', '374',
        widget_0='latent_audio',
    )
    getnode_38 = _node(wf, 'GetNode', '375',
        widget_0='latent_custom_audio',
    )
    getnode_39 = _node(wf, 'GetNode', '378',
        widget_0='org_audio',
    )
    reroute = _node(wf, 'Reroute', '379')
    manualsigmas_2 = _node(wf, 'ManualSigmas', '380',
        widget_0='0.85, 0.7250, 0.4219, 0.0',
    )
    manualsigmas_3 = _node(wf, 'ManualSigmas', '381',
        widget_0='1.0, 0.99375, 0.9875, 0.98125, 0.975, 0.909375, 0.725, 0.421875, 0.0',
    )
    cfgguider = _node(wf, 'CFGGuider', '103',
        cfg=2.5,
        model=getnode_29.out(0),
        negative=getnode_12.out(0),
        positive=getnode_11.out(0),
    )
    emptyltxvlatentvideo = _node(wf, 'EmptyLTXVLatentVideo', '108',
        batch_size=1,
        widget_0=256,
        widget_1=256,
        widget_2=5,
        width=getnode_15.out(0),
        height=getnode_16.out(0),
        length=getnode.out(0),
    )
    cliptextencode = _node(wf, 'CLIPTextEncode', '110',
        text='blurry, oversaturated, pixelated, low resolution, grainy, distorted, noise, compression artifacts, jpeg artifacts, glitches, watermark, text, logo, signature, copyright, subtitles, distorted sound, saturated sound, loud',
        clip=getnode_4.out(0),
    )
    cfgguider_2 = _node(wf, 'CFGGuider', '129',
        cfg=2.5,
        model=getnode_31.out(0),
        negative=getnode_14.out(0),
        positive=getnode_13.out(0),
    )
    loraloadermodelonly = _node(wf, 'LoraLoaderModelOnly', '134',
        lora_name='LTX\\LTX-2\\ltx-2.3-22b-distilled-lora-384.safetensors',
        strength_model=0.6,
        model=unetloader.out(0),
    )
    ltxvpreprocess = _node(wf, 'LTXVPreprocess', '162',
        widget_0=33,
        image=getnode_2.out(0),
    )
    imageresizekjv2 = _node(wf, 'ImageResizeKJv2', '165',
        widget_0=736,
        widget_1=1280,
        widget_2='nearest-exact',
        widget_3='crop',
        widget_4='0, 0, 0',
        widget_5='center',
        widget_6=32,
        widget_7='cpu',
        height=getnode_20.out(0),
        image=loadimage.out(0),
        width=getnode_19.out(0),
    )
    setnode = _node(wf, 'SetNode', '188',
        widget_0='upscale_model',
        LATENT_UPSCALE_MODEL=latentupscalemodelloader.out(0),
    )
    ltxvscheduler = _node(wf, 'LTXVScheduler', '206',
        steps=1,
        widget_0=1,
        widget_1=2.05,
        widget_2=0.95,
        widget_3=True,
        widget_4=0.1,
        latent=getnode_17.out(0),
    )
    setnode_4 = _node(wf, 'SetNode', '213',
        widget_0='clip',
        CLIP=dualcliploader.out(0),
    )
    setnode_5 = _node(wf, 'SetNode', '215',
        widget_0='vae',
        VAE=vaeloader.out(0),
    )
    setnode_6 = _node(wf, 'SetNode', '216',
        widget_0='vae_audio',
        VAE=vaeloaderkj.out(0),
    )
    setnode_14 = _node(wf, 'SetNode', '282',
        widget_0='height',
        INT=intconstant_3.out(0),
    )
    setnode_15 = _node(wf, 'SetNode', '283',
        widget_0='width',
        INT=intconstant_2.out(0),
    )
    setnode_16 = _node(wf, 'SetNode', '284',
        widget_0='fps',
        FLOAT=primitivefloat.out(0),
    )
    simplecalculatorkj = _node(wf, 'SimpleCalculatorKJ', '287',
        widget_0='1+ 8*(round(a*b)/8)',
        a=intconstant.out(0),
        b=primitivefloat.out(0),
    )
    setnode_18 = _node(wf, 'SetNode', '288',
        widget_0='t2v_mode',
        BOOLEAN=primitiveboolean.out(0),
    )
    simplecalculatorkj_2 = _node(wf, 'SimpleCalculatorKJ', '311',
        widget_0='a',
        _extras={'variables.a': getnode_25.out(0)},
    )
    setnode_20 = _node(wf, 'SetNode', '331',
        widget_0='vae_tiny',
        VAE=vaeloader_2.out(0),
    )
    stringconcatenate = _node(wf, 'StringConcatenate', '347',
        widget_0='',
        widget_1='',
        widget_2='',
        string_a=primitivestringmultiline.out(0),
    )
    solidmask = _node(wf, 'SolidMask', '362',
        widget_0=0,
        widget_1=512,
        widget_2=512,
        height=getnode_32.out(0),
        width=getnode_33.out(0),
    )
    simplecalculatorkj_3 = _node(wf, 'SimpleCalculatorKJ', '367',
        widget_0='a/b',
        a=getnode_35.out(0),
        b=getnode_36.out(0),
    )
    comfyswitchnode = _node(wf, 'ComfySwitchNode', '376',
        widget_0=True,
        on_false=getnode_37.out(0),
        on_true=getnode_38.out(0),
    )
    samplercustomadvanced = _node(wf, 'SamplerCustomAdvanced', '113',
        guider=cfgguider_2.out(0),
        latent_image=getnode_17.out(0),
        noise=randomnoise_2.out(0),
        sampler=ksamplerselect.out(0),
        sigmas=manualsigmas_3.out(0),
    )
    ltxvimgtovideoinplace_2 = _node(wf, 'LTXVImgToVideoInplace', '161',
        widget_0=1,
        widget_1=False,
        bypass=getnode_23.out(0),
        image=ltxvpreprocess.out(0),
        latent=emptyltxvlatentvideo.out(0),
        vae=getnode_6.out(0),
    )
    resizeimagemasknode = _node(wf, 'ResizeImageMaskNode', '164',
        widget_0='scale by multiplier',
        widget_1=256,
        widget_2='area',
        input=imageresizekjv2.out(0),
    )
    ltxvemptylatentaudio = _node(wf, 'LTXVEmptyLatentAudio', '199',
        widget_0=5,
        widget_1=8,
        widget_2=1,
        audio_vae=getnode_5.out(0),
        frame_rate=simplecalculatorkj_2.out(1),
        frames_number=getnode.out(0),
    )
    setnode_3 = _node(wf, 'SetNode', '211',
        widget_0='compress_image',
        IMAGE=ltxvpreprocess.out(0),
    )
    resizeimagesbylongeredge = _node(wf, 'ResizeImagesByLongerEdge', '246',
        widget_0=1536,
        images=imageresizekjv2.out(0),
    )
    setnode_17 = _node(wf, 'SetNode', '286',
        widget_0='frames',
        INT=simplecalculatorkj.out(1),
    )
    ltxvchunkfeedforward = _node(wf, 'LTXVChunkFeedForward', '332',
        widget_0=2,
        widget_1=4096,
        model=loraloadermodelonly.out(0),
    )
    ltx2_nag = _node(wf, 'LTX2_NAG', '342',
        widget_0=11,
        widget_1=0.25,
        widget_2=2.5,
        widget_3=True,
        model=getnode_28.out(0),
        nag_cond_audio=getnode_30.out(0),
        nag_cond_video=getnode_30.out(0),
    )
    textgenerateltx2prompt = _node(wf, 'TextGenerateLTX2Prompt', '349',
        widget_0='',
        widget_1=256,
        widget_2='off',
        clip=getnode_4.out(0),
        image=imageresizekjv2.out(0),
        prompt=primitivestringmultiline_2.out(0),
    )
    trimaudioduration = _node(wf, 'TrimAudioDuration', '373',
        widget_0=0,
        widget_1=8,
        audio=loadaudio.out(0),
        duration=simplecalculatorkj_3.out(0),
    )
    ltxvconcatavlatent = _node(wf, 'LTXVConcatAVLatent', '109',
        audio_latent=comfyswitchnode.out(0),
        video_latent=ltxvimgtovideoinplace_2.out(0),
    )
    ltxvseparateavlatent = _node(wf, 'LTXVSeparateAVLatent', '116',
        av_latent=samplercustomadvanced.out(0),
    )
    cliptextencode_2 = _node(wf, 'CLIPTextEncode', '121',
        widget_0='= Enhanced Prompt = \n',
        text=textgenerateltx2prompt.out(0),
        clip=getnode_4.out(0),
    )
    getimagesize = _node(wf, 'GetImageSize', '163',
        image=resizeimagemasknode.out(0),
    )
    setnode_2 = _node(wf, 'SetNode', '209',
        widget_0='ref_image',
        IMAGE=resizeimagesbylongeredge.out(0),
    )
    setnode_12 = _node(wf, 'SetNode', '240',
        widget_0='latent_audio',
        LATENT=ltxvemptylatentaudio.out(0),
    )
    setnode_13 = _node(wf, 'SetNode', '248',
        widget_0='resize_image',
        IMAGE=resizeimagemasknode.out(0),
    )
    power_lora_loader__rgthree_ = _node(wf, 'Power Lora Loader (rgthree)', '301',
        widget_3='',
        model=ltxvchunkfeedforward.out(0),
    )
    setnode_21 = _node(wf, 'SetNode', '340',
        widget_0='model',
        MODEL=ltx2_nag.out(0),
    )
    setnode_22 = _node(wf, 'SetNode', '365',
        widget_0='org_audio',
        AUDIO=trimaudioduration.out(0),
    )
    melbandroformersampler = _node(wf, 'MelBandRoFormerSampler', '371',
        audio=trimaudioduration.out(0),
        model=melbandroformermodelloader.out(0),
    )
    ltxvconditioning = _node(wf, 'LTXVConditioning', '107',
        widget_0=8,
        frame_rate=getnode_26.out(0),
        negative=cliptextencode.out(0),
        positive=cliptextencode_2.out(0),
    )
    ltxvimgtovideoinplace = _node(wf, 'LTXVImgToVideoInplace', '160',
        widget_0=1,
        widget_1=False,
        bypass=getnode_24.out(0),
        image=getnode_3.out(0),
        latent=ltxvseparateavlatent.out(0),
        vae=getnode_7.out(0),
    )
    setnode_9 = _node(wf, 'SetNode', '233',
        widget_0='width_downsized',
        INT=getimagesize.out(0),
    )
    setnode_10 = _node(wf, 'SetNode', '234',
        widget_0='height_downsized',
        INT=getimagesize.out(1),
    )
    setnode_11 = _node(wf, 'SetNode', '238',
        widget_0='latent',
        LATENT=ltxvconcatavlatent.out(0),
    )
    setnode_19 = _node(wf, 'SetNode', '303',
        widget_0='model_with_lora',
        MODEL=power_lora_loader__rgthree_.out(0),
    )
    comfyswitchnode_2 = _node(wf, 'ComfySwitchNode', '382',
        widget_0=False,
        on_false=trimaudioduration.out(0),
        on_true=melbandroformersampler.out(0),
    )
    ltxvconcatavlatent_2 = _node(wf, 'LTXVConcatAVLatent', '117',
        audio_latent=ltxvseparateavlatent.out(1),
        video_latent=ltxvimgtovideoinplace.out(0),
    )
    setnode_7 = _node(wf, 'SetNode', '226',
        widget_0='positive',
        CONDITIONING=ltxvconditioning.out(0),
    )
    setnode_8 = _node(wf, 'SetNode', '227',
        widget_0='negative',
        CONDITIONING=ltxvconditioning.out(1),
    )
    ltxvaudiovaeencode = _node(wf, 'LTXVAudioVAEEncode', '364',
        audio=comfyswitchnode_2.out(0),
        audio_vae=getnode_34.out(0),
    )
    samplercustomadvanced_2 = _node(wf, 'SamplerCustomAdvanced', '119',
        guider=cfgguider.out(0),
        latent_image=ltxvconcatavlatent_2.out(0),
        noise=randomnoise.out(0),
        sampler=ksamplerselect_2.out(0),
        sigmas=manualsigmas_2.out(0),
    )
    setlatentnoisemask = _node(wf, 'SetLatentNoiseMask', '363',
        mask=solidmask.out(0),
        samples=ltxvaudiovaeencode.out(0),
    )
    ltxvseparateavlatent_2 = _node(wf, 'LTXVSeparateAVLatent', '125',
        av_latent=samplercustomadvanced_2.out(0),
    )
    setnode_23 = _node(wf, 'SetNode', '366',
        widget_0='latent_custom_audio',
        LATENT=setlatentnoisemask.out(0),
    )
    vaedecodetiled = _node(wf, 'VAEDecodeTiled', '127',
        tile_size=512,
        overlap=64,
        temporal_size=4096,
        temporal_overlap=8,
        samples=ltxvseparateavlatent_2.out(0),
        vae=getnode_8.out(0),
    )
    ltxvaudiovaedecode = _node(wf, 'LTXVAudioVAEDecode', '201',
        audio_vae=getnode_9.out(0),
        samples=ltxvseparateavlatent_2.out(1),
    )
    vhs_videocombine = _node(wf, 'VHS_VideoCombine', '140',
        audio=getnode_39.out(0),
        frame_rate=getnode_22.out(0),
        images=vaedecodetiled.out(0),
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
