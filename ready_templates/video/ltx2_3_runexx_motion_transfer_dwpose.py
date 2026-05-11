# vibecomfy: generated — converted by tools/convert_ready_templates.py
# Edits will be overwritten on regeneration. Add a `# vibecomfy: manual`
# marker on the first line if hand-editing is required.
"""Auto-generated ready_template — see tools/convert_ready_templates.py."""
from __future__ import annotations

from vibecomfy.workflow import VibeWorkflow, WorkflowSource
from vibecomfy.registry.ready_template import apply_ready_template_policy


READY_METADATA = {'model_assets': [],
 'unbound_inputs': {'seed': 4791},
 'ready_template': 'video/ltx2_3_runexx_motion_transfer_dwpose',
 'workflow_template': 'ltx2_3_runexx_motion_transfer_dwpose',
 'capability': 'dwpose_motion_transfer',
 'source_role': 'materialized_ready_python_template',
 'source_workflow': 'workflow_corpus/custom_nodes/ltxvideo/runexx/LTX-2.3_Motion_Transfer_DWPose.json',
 'coverage_tier': 'supplemental',
 'approach': 'DWPose body motion transfer',
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
                  'ComfyUI-VideoHelperSuite',
                  'comfyui_controlnet_aux',
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

    loadimage = _node(wf, 'LoadImage', '2004',
        image='fjf1oxsjnnrgphxxrnzx6dh4k9-nano-banana-gemini-3-pro-image-ultra-realistic-black-and-white-cinematic-fullbody-portrait-of-muhammad-ali-standing-side-lighting-strong-contrast-intense-mysterious-expression-sharp.jpg',
        widget_1='image',
    )
    ksamplerselect = _node(wf, 'KSamplerSelect', '4831',
        sampler_name='euler_ancestral_cfg_pp',
    )
    randomnoise = _node(wf, 'RandomNoise', '4832',
        noise_seed=42,
        control_after_generate='fixed',
    )
    manualsigmas = _node(wf, 'ManualSigmas', '5025',
        widget_0='1.0, 0.99375, 0.9875, 0.98125, 0.975, 0.909375, 0.725, 0.421875, 0.0',
    )
    randomnoise_2 = _node(wf, 'RandomNoise', '5068',
        noise_seed=43,
        control_after_generate='fixed',
    )
    ksamplerselect_2 = _node(wf, 'KSamplerSelect', '5070',
        sampler_name='euler_cfg_pp',
    )
    manualsigmas_2 = _node(wf, 'ManualSigmas', '5071',
        widget_0='0.85, 0.7250, 0.4219, 0.0',
    )
    vaeloader = _node(wf, 'VAELoader', '5125',
        vae_name='LTX23_video_vae_bf16.safetensors',
    )
    dualcliploader = _node(wf, 'DualCLIPLoader', '5126',
        clip_name1='gemma_3_12B_it_fp4_mixed.safetensors',
        clip_name2='ltx-2.3_text_projection_bf16.safetensors',
        type='ltxv',
        device='default',
    )
    vaeloaderkj = _node(wf, 'VAELoaderKJ', '5127',
        widget_0='LTX23_audio_vae_bf16.safetensors',
        widget_1='main_device',
        widget_2='bf16',
    )
    vaeloader_2 = _node(wf, 'VAELoader', '5129',
        vae_name='taeltx2_3.safetensors',
    )
    unetloader = _node(wf, 'UNETLoader', '5130',
        unet_name='ltx-2.3-22b-distilled-1.1_transformer_only_fp8_scaled.safetensors',
        weight_dtype='default',
    )
    latentupscalemodelloader = _node(wf, 'LatentUpscaleModelLoader', '5132',
        widget_0='ltx-2.3-spatial-upscaler-x2-1.1.safetensors',
    )
    getnode = _node(wf, 'GetNode', '5137',
        widget_0='clip',
    )
    getnode_2 = _node(wf, 'GetNode', '5139',
        widget_0='vae',
    )
    getnode_3 = _node(wf, 'GetNode', '5140',
        widget_0='vae',
    )
    getnode_4 = _node(wf, 'GetNode', '5141',
        widget_0='vae',
    )
    getnode_5 = _node(wf, 'GetNode', '5143',
        widget_0='vae',
    )
    getnode_6 = _node(wf, 'GetNode', '5145',
        widget_0='vae_audio',
    )
    getnode_7 = _node(wf, 'GetNode', '5146',
        widget_0='vae',
    )
    getnode_8 = _node(wf, 'GetNode', '5147',
        widget_0='vae_audio',
    )
    getnode_9 = _node(wf, 'GetNode', '5149',
        widget_0='model',
    )
    getnode_10 = _node(wf, 'GetNode', '5150',
        widget_0='model',
    )
    getnode_11 = _node(wf, 'GetNode', '5152',
        widget_0='ref_video',
    )
    getnode_12 = _node(wf, 'GetNode', '5156',
        widget_0='ref_height',
    )
    getnode_13 = _node(wf, 'GetNode', '5157',
        widget_0='ref_width',
    )
    getnode_14 = _node(wf, 'GetNode', '5158',
        widget_0='ref_frames',
    )
    getnode_15 = _node(wf, 'GetNode', '5159',
        widget_0='ref_height',
    )
    getnode_16 = _node(wf, 'GetNode', '5160',
        widget_0='ref_width',
    )
    getnode_17 = _node(wf, 'GetNode', '5163',
        widget_0='positive',
    )
    getnode_18 = _node(wf, 'GetNode', '5164',
        widget_0='negative',
    )
    getnode_19 = _node(wf, 'GetNode', '5169',
        widget_0='positive_guider',
    )
    getnode_20 = _node(wf, 'GetNode', '5170',
        widget_0='negative_guider',
    )
    getnode_21 = _node(wf, 'GetNode', '5171',
        widget_0='positive',
    )
    getnode_22 = _node(wf, 'GetNode', '5172',
        widget_0='negative',
    )
    getnode_23 = _node(wf, 'GetNode', '5173',
        widget_0='negative',
    )
    getnode_24 = _node(wf, 'GetNode', '5174',
        widget_0='positive',
    )
    getnode_25 = _node(wf, 'GetNode', '5176',
        widget_0='ref_image',
    )
    getnode_26 = _node(wf, 'GetNode', '5177',
        widget_0='ref_image',
    )
    getnode_27 = _node(wf, 'GetNode', '5180',
        widget_0='t2v_mode',
    )
    getnode_28 = _node(wf, 'GetNode', '5181',
        widget_0='t2v_mode',
    )
    getnode_29 = _node(wf, 'GetNode', '5184',
        widget_0='latent_down_factor',
    )
    getnode_30 = _node(wf, 'GetNode', '5185',
        widget_0='latent_down_factor',
    )
    getnode_31 = _node(wf, 'GetNode', '5188',
        widget_0='model_with_lora',
    )
    getnode_32 = _node(wf, 'GetNode', '5190',
        widget_0='vae_tiny',
    )
    getnode_33 = _node(wf, 'GetNode', '5191',
        widget_0='upscale_model',
    )
    primitiveboolean = _node(wf, 'PrimitiveBoolean', '5198',
        value=False,
    )
    primitivefloat = _node(wf, 'PrimitiveFloat', '5199',
        value=8,
    )
    primitiveboolean_2 = _node(wf, 'PrimitiveBoolean', '5201',
        value=False,
    )
    getnode_34 = _node(wf, 'GetNode', '5203',
        widget_0='fps',
    )
    intconstant = _node(wf, 'INTConstant', '5205',
        widget_0=10,
    )
    intconstant_2 = _node(wf, 'INTConstant', '5206',
        widget_0=736,
    )
    intconstant_3 = _node(wf, 'INTConstant', '5207',
        widget_0=1280,
    )
    getnode_35 = _node(wf, 'GetNode', '5209',
        widget_0='fps',
    )
    getnode_36 = _node(wf, 'GetNode', '5210',
        widget_0='audio_selected',
    )
    getnode_37 = _node(wf, 'GetNode', '5212',
        widget_0='width',
    )
    getnode_38 = _node(wf, 'GetNode', '5213',
        widget_0='height',
    )
    getnode_39 = _node(wf, 'GetNode', '5216',
        widget_0='fps',
    )
    getnode_40 = _node(wf, 'GetNode', '5217',
        widget_0='frames',
    )
    getnode_41 = _node(wf, 'GetNode', '5218',
        widget_0='fps',
    )
    dualcliploadergguf = _node(wf, 'DualCLIPLoaderGGUF', '5228',
        widget_0='gemma-3-12b-it-Q2_K.gguf',
        widget_1='ltx-2.3_text_projection_bf16.safetensors',
        widget_2='sdxl',
    )
    unetloadergguf = _node(wf, 'UnetLoaderGGUF', '5229',
        widget_0='LTXvideo\\LTX-2\\quantstack\\LTX-2.3-distilled-Q4_K_S.gguf',
    )
    getnode_42 = _node(wf, 'GetNode', '5235',
        widget_0='clip',
    )
    getnode_43 = _node(wf, 'GetNode', '5236',
        widget_0='enhance_prompt',
    )
    primitivestringmultiline = _node(wf, 'PrimitiveStringMultiline', '5242',
        value='highly detailed, monochrime colors. Make this image come alive with fluid motion. \n\nA make boxer. \n\nHe is dancing in sync to the music ',
    )
    getnode_44 = _node(wf, 'GetNode', '5245',
        widget_0='fps',
    )
    getnode_45 = _node(wf, 'GetNode', '5248',
        widget_0='ref_frames',
    )
    getnode_46 = _node(wf, 'GetNode', '5250',
        widget_0='negative',
    )
    getnode_47 = _node(wf, 'GetNode', '5253',
        widget_0='negative',
    )
    getnode_48 = _node(wf, 'GetNode', '5255',
        widget_0='vae_audio',
    )
    getnode_49 = _node(wf, 'GetNode', '5257',
        widget_0='latent_audio_selected',
    )
    getnode_50 = _node(wf, 'GetNode', '5261',
        widget_0='latent_audio_custom',
    )
    loadaudio = _node(wf, 'LoadAudio', '5263',
        audio='(Verse).mp3',
    )
    getnode_51 = _node(wf, 'GetNode', '5267',
        widget_0='audio_output',
    )
    vaedecodetiled_2 = _node(wf, 'VAEDecodeTiled', '5268',
        tile_size=544,
        overlap=64,
        temporal_size=4096,
        temporal_overlap=4,
    )
    getnode_52 = _node(wf, 'GetNode', '5269',
        widget_0='video_output',
    )
    getnode_53 = _node(wf, 'GetNode', '5278',
        widget_0='ref_blended',
    )
    getnode_54 = _node(wf, 'GetNode', '5279',
        widget_0='ref_pose',
    )
    getnode_55 = _node(wf, 'GetNode', '5281',
        widget_0='ref_selected',
    )
    getnode_56 = _node(wf, 'GetNode', '5285',
        widget_0='ref_frames',
    )
    getnode_57 = _node(wf, 'GetNode', '5286',
        widget_0='fps',
    )
    getnode_58 = _node(wf, 'GetNode', '5287',
        widget_0='audio_custom',
    )
    getnode_59 = _node(wf, 'GetNode', '5288',
        widget_0='audio_original',
    )
    getnode_60 = _node(wf, 'GetNode', '5291',
        widget_0='ref_frames',
    )
    getnode_61 = _node(wf, 'GetNode', '5292',
        widget_0='fps',
    )
    getnode_62 = _node(wf, 'GetNode', '5295',
        widget_0='latent_audio',
    )
    getnode_63 = _node(wf, 'GetNode', '5296',
        widget_0='audio_selected',
    )
    primitivefloat_2 = _node(wf, 'PrimitiveFloat', '5298',
        value=8,
    )
    primitivefloat_3 = _node(wf, 'PrimitiveFloat', '5299',
        value=8,
    )
    getnode_64 = _node(wf, 'GetNode', '5301',
        widget_0='ref_strength',
    )
    primitiveboolean_3 = _node(wf, 'PrimitiveBoolean', '5303',
        value=True,
    )
    getnode_65 = _node(wf, 'GetNode', '5305',
        widget_0='audio_custom_mode',
    )
    getnode_66 = _node(wf, 'GetNode', '5306',
        widget_0='audio_custom_mode',
    )
    cliptextencode_2 = _node(wf, 'CLIPTextEncode', '2612',
        text='low contrast, washed out, text, subtitles, logo, still image, still video, blurry, low quality, distorted, bad anatomy, oversaturated, pixelated, low resolution, grainy, compression artifacts, jpeg artifacts, glitches, watermark, signature, copyright,  distortedsound, saturated sound, loud sound , deformed facial features, asymmetrical face, missing facial features, extra limbs, disfigured hands, blurry teeth, disfigured teeth',
        clip=getnode.out(0),
    )
    emptyltxvlatentvideo = _node(wf, 'EmptyLTXVLatentVideo', '3059',
        batch_size=1,
        widget_0=256,
        widget_1=256,
        widget_2=5,
        width=getnode_13.out(0),
        height=getnode_12.out(0),
        length=getnode_14.out(0),
    )
    ltxvpreprocess = _node(wf, 'LTXVPreprocess', '3336',
        widget_0=18,
        image=getnode_26.out(0),
    )
    simplemath_ = _node(wf, 'SimpleMath+', '5034',
        widget_0='a*32',
        a=getnode_30.out(0),
    )
    resizeimagemasknode_2 = _node(wf, 'ResizeImageMaskNode', '5035',
        widget_0='scale longer dimension',
        widget_1=256,
        widget_2='lanczos',
        input=loadimage.out(0),
    )
    cfgguider_2 = _node(wf, 'CFGGuider', '5069',
        cfg=2.5,
        model=getnode_10.out(0),
        negative=getnode_22.out(0),
        positive=getnode_21.out(0),
    )
    ltxvaudiovaeencode = _node(wf, 'LTXVAudioVAEEncode', '5079',
        audio=getnode_63.out(0),
        audio_vae=getnode_8.out(0),
    )
    solidmask = _node(wf, 'SolidMask', '5080',
        widget_0=0,
        widget_1=512,
        widget_2=512,
        height=getnode_15.out(0),
        width=getnode_16.out(0),
    )
    setnode = _node(wf, 'SetNode', '5121',
        widget_0='upscale_model',
        LATENT_UPSCALE_MODEL=latentupscalemodelloader.out(0),
    )
    setnode_2 = _node(wf, 'SetNode', '5122',
        widget_0='vae_audio',
        VAE=vaeloaderkj.out(0),
    )
    setnode_3 = _node(wf, 'SetNode', '5123',
        widget_0='vae',
        VAE=vaeloader.out(0),
    )
    setnode_4 = _node(wf, 'SetNode', '5124',
        widget_0='clip',
        CLIP=dualcliploader.out(0),
    )
    setnode_5 = _node(wf, 'SetNode', '5128',
        widget_0='vae_tiny',
        VAE=vaeloader_2.out(0),
    )
    loraloadermodelonly = _node(wf, 'LoraLoaderModelOnly', '5131',
        lora_name='LTX\\LTX-2\\ltx-2.3-22b-distilled-lora-384.safetensors',
        strength_model=0.6,
        model=unetloader.out(0),
    )
    vhs_loadvideoffmpeg = _node(wf, 'VHS_LoadVideoFFmpeg', '5192',
        force_rate=getnode_41.out(0),
        frame_load_cap=getnode_40.out(0),
    )
    setnode_19 = _node(wf, 'SetNode', '5194',
        widget_0='height',
        INT=intconstant_3.out(0),
    )
    setnode_20 = _node(wf, 'SetNode', '5195',
        widget_0='width',
        INT=intconstant_2.out(0),
    )
    setnode_21 = _node(wf, 'SetNode', '5196',
        widget_0='fps',
        FLOAT=primitivefloat.out(0),
    )
    setnode_22 = _node(wf, 'SetNode', '5197',
        widget_0='t2v_mode',
        BOOLEAN=primitiveboolean.out(0),
    )
    setnode_23 = _node(wf, 'SetNode', '5200',
        widget_0='enhance_prompt',
        BOOLEAN=primitiveboolean_2.out(0),
    )
    simplecalculatorkj = _node(wf, 'SimpleCalculatorKJ', '5202',
        widget_0='((round((a * b -1) / 8)) * 8) + 1 ',
        _extras={'variables.a': intconstant.out(0), 'variables.b': getnode_34.out(0)},
    )
    vhs_videocombine_2 = _node(wf, 'VHS_VideoCombine', '5208',
        audio=getnode_51.out(0),
        frame_rate=getnode_35.out(0),
        images=getnode_52.out(0),
    )
    simplecalculatorkj_2 = _node(wf, 'SimpleCalculatorKJ', '5247',
        widget_0='a',
        _extras={'variables.a': getnode_44.out(0)},
    )
    comfyswitchnode = _node(wf, 'ComfySwitchNode', '5256',
        widget_0=True,
        on_false=getnode_62.out(0),
        on_true=getnode_50.out(0),
        switch=getnode_66.out(0),
    )
    comfyswitchnode_3 = _node(wf, 'ComfySwitchNode', '5272',
        widget_0=False,
        on_false=getnode_54.out(0),
        on_true=getnode_53.out(0),
    )
    simplecalculatorkj_3 = _node(wf, 'SimpleCalculatorKJ', '5284',
        widget_0='a / b ',
        _extras={'variables.a': getnode_56.out(0), 'variables.b': getnode_57.out(0)},
    )
    simplecalculatorkj_4 = _node(wf, 'SimpleCalculatorKJ', '5290',
        widget_0='a / b',
        _extras={'variables.a': getnode_60.out(0), 'variables.b': getnode_61.out(0)},
    )
    setnode_36 = _node(wf, 'SetNode', '5300',
        widget_0='ref_strength',
        FLOAT=primitivefloat_3.out(0),
    )
    setnode_37 = _node(wf, 'SetNode', '5304',
        widget_0='audio_custom_mode',
        BOOLEAN=primitiveboolean_3.out(0),
    )
    ltxvimgtovideoconditiononly = _node(wf, 'LTXVImgToVideoConditionOnly', '3159',
        widget_0=1,
        widget_1=False,
        bypass=getnode_28.out(0),
        image=ltxvpreprocess.out(0),
        latent=emptyltxvlatentvideo.out(0),
        vae=getnode_2.out(0),
    )
    ltxicloraloadermodelonly = _node(wf, 'LTXICLoRALoaderModelOnly', '5011',
        widget_0='LTX\\LTX-2\\IC-Lora\\ltx-2.3-22b-v1.1-ic-lora-union-control-ref0.5.safetensors',
        widget_1=0.71,
        model=loraloadermodelonly.out(0),
    )
    setlatentnoisemask = _node(wf, 'SetLatentNoiseMask', '5081',
        mask=solidmask.out(0),
        samples=ltxvaudiovaeencode.out(0),
    )
    setnode_15 = _node(wf, 'SetNode', '5175',
        widget_0='ref_image',
        IMAGE=resizeimagemasknode_2.out(0),
    )
    setnode_18 = _node(wf, 'SetNode', '5193',
        widget_0='audio_original',
        AUDIO=vhs_loadvideoffmpeg.out(2),
    )
    setnode_24 = _node(wf, 'SetNode', '5204',
        widget_0='frames',
        INT=simplecalculatorkj.out(1),
    )
    imageresizekjv2 = _node(wf, 'ImageResizeKJv2', '5211',
        widget_0=512,
        widget_1=512,
        widget_2='nearest-exact',
        widget_3='crop',
        widget_4='0, 0, 0',
        widget_5='center',
        widget_6=2,
        widget_7='cpu',
        height=getnode_38.out(0),
        image=vhs_loadvideoffmpeg.out(0),
        width=getnode_37.out(0),
    )
    resizeimagemasknode_4 = _node(wf, 'ResizeImageMaskNode', '5241',
        widget_0='scale by multiplier',
        widget_1=256,
        widget_2='area',
        input=resizeimagemasknode_2.out(0),
    )
    ltxvemptylatentaudio = _node(wf, 'LTXVEmptyLatentAudio', '5243',
        widget_0=5,
        widget_1=8,
        widget_2=1,
        audio_vae=getnode_48.out(0),
        frame_rate=simplecalculatorkj_2.out(1),
        frames_number=getnode_45.out(0),
    )
    ltx2_nag = _node(wf, 'LTX2_NAG', '5251',
        widget_0=11,
        widget_1=0.25,
        widget_2=2.5,
        widget_3=True,
        model=getnode_31.out(0),
        nag_cond_audio=getnode_47.out(0),
        nag_cond_video=getnode_47.out(0),
    )
    setnode_26 = _node(wf, 'SetNode', '5258',
        widget_0='latent_audio_selected',
        LATENT=comfyswitchnode.out(0),
    )
    setnode_32 = _node(wf, 'SetNode', '5280',
        widget_0='ref_selected',
        IMAGE=comfyswitchnode_3.out(0),
    )
    trimaudioduration = _node(wf, 'TrimAudioDuration', '5283',
        widget_0=0,
        widget_1=60,
        audio=loadaudio.out(0),
        duration=simplecalculatorkj_3.out(0),
    )
    emptyaudio = _node(wf, 'EmptyAudio', '5289',
        widget_0=60,
        widget_1=44100,
        widget_2=2,
        duration=simplecalculatorkj_4.out(0),
    )
    ltxaddvideoicloraguide = _node(wf, 'LTXAddVideoICLoRAGuide', '5012',
        widget_0=0,
        widget_1=0.7,
        widget_2=1,
        widget_3='disabled',
        widget_4=False,
        widget_5=128,
        widget_6=32,
        image=getnode_11.out(0),
        latent=ltxvimgtovideoconditiononly.out(0),
        latent_downscale_factor=getnode_29.out(0),
        negative=getnode_18.out(0),
        positive=getnode_17.out(0),
        strength=getnode_64.out(0),
        vae=getnode_7.out(0),
    )
    setnode_6 = _node(wf, 'SetNode', '5148',
        widget_0='model_iclora',
        MODEL=ltxicloraloadermodelonly.out(0),
    )
    setnode_16 = _node(wf, 'SetNode', '5183',
        widget_0='latent_down_factor',
        FLOAT=ltxicloraloadermodelonly.out(1),
    )
    setnode_17 = _node(wf, 'SetNode', '5189',
        widget_0='model',
        MODEL=ltx2_nag.out(0),
    )
    resizeimagemasknode_3 = _node(wf, 'ResizeImageMaskNode', '5214',
        widget_0='scale by multiplier',
        widget_1=256,
        widget_2='area',
        input=imageresizekjv2.out(0),
    )
    pathchsageattentionkj = _node(wf, 'PathchSageAttentionKJ', '5231',
        widget_0='disabled',
        widget_1=False,
        model=ltxicloraloadermodelonly.out(0),
    )
    n_94e8f3a0_557f_4580_93a0_f762c7b0d076 = _node(wf, '94e8f3a0-557f-4580-93a0-f762c7b0d076', '5237',
        _1=primitivestringmultiline.out(0),
        clip=getnode_42.out(0),
        image=resizeimagemasknode_4.out(0),
    )
    setnode_27 = _node(wf, 'SetNode', '5260',
        widget_0='latent_audio_custom',
        LATENT=setlatentnoisemask.out(0),
    )
    comfyswitchnode_4 = _node(wf, 'ComfySwitchNode', '5273',
        widget_0=True,
        on_false=emptyaudio.out(0),
        on_true=getnode_59.out(0),
    )
    setnode_33 = _node(wf, 'SetNode', '5282',
        widget_0='audio_custom',
        AUDIO=trimaudioduration.out(0),
    )
    setnode_35 = _node(wf, 'SetNode', '5294',
        widget_0='latent_audio',
        LATENT=ltxvemptylatentaudio.out(0),
    )
    cliptextencode = _node(wf, 'CLIPTextEncode', '2483',
        widget_0='= enhanced prompt = ',
        text=n_94e8f3a0_557f_4580_93a0_f762c7b0d076.out(0),
        clip=getnode.out(0),
    )
    ltxvconcatavlatent = _node(wf, 'LTXVConcatAVLatent', '4528',
        audio_latent=getnode_49.out(0),
        video_latent=ltxaddvideoicloraguide.out(2),
    )
    cfgguider = _node(wf, 'CFGGuider', '4828',
        cfg=2.5,
        model=getnode_9.out(0),
        negative=ltxaddvideoicloraguide.out(1),
        positive=ltxaddvideoicloraguide.out(0),
    )
    resizeimagemasknode = _node(wf, 'ResizeImageMaskNode', '5026',
        widget_0='scale shorter dimension',
        widget_1=256,
        widget_2='lanczos',
        input=resizeimagemasknode_3.out(0),
    )
    setnode_13 = _node(wf, 'SetNode', '5165',
        widget_0='positive_guider',
        CONDITIONING=ltxaddvideoicloraguide.out(0),
    )
    setnode_14 = _node(wf, 'SetNode', '5166',
        widget_0='negative_guider',
        CONDITIONING=ltxaddvideoicloraguide.out(1),
    )
    getimagesize_2 = _node(wf, 'GetImageSize', '5219',
        image=resizeimagemasknode_3.out(0),
    )
    ltxvchunkfeedforward = _node(wf, 'LTXVChunkFeedForward', '5232',
        widget_0=2,
        widget_1=4096,
        model=pathchsageattentionkj.out(0),
    )
    comfyswitchnode_5 = _node(wf, 'ComfySwitchNode', '5274',
        widget_0=False,
        on_false=comfyswitchnode_4.out(0),
        on_true=getnode_58.out(0),
    )
    ltxvconditioning = _node(wf, 'LTXVConditioning', '1241',
        widget_0=8,
        frame_rate=getnode_39.out(0),
        negative=cliptextencode_2.out(0),
        positive=cliptextencode.out(0),
    )
    samplercustomadvanced = _node(wf, 'SamplerCustomAdvanced', '4829',
        guider=cfgguider.out(0),
        latent_image=ltxvconcatavlatent.out(0),
        noise=randomnoise.out(0),
        sampler=ksamplerselect.out(0),
        sigmas=manualsigmas.out(0),
    )
    dwpreprocessor = _node(wf, 'DWPreprocessor', '4986',
        widget_0='enable',
        widget_1='enable',
        widget_2='enable',
        widget_3=256,
        widget_4='yolox_l.onnx',
        widget_5='dw-ll_ucoco_384_bs5.torchscript.pt',
        widget_6='disable',
        image=resizeimagemasknode.out(0),
    )
    depthanythingpreprocessor = _node(wf, 'DepthAnythingPreprocessor', '5114',
        widget_0='depth_anything_vitl14.pth',
        widget_1=512,
        image=resizeimagemasknode.out(0),
    )
    imageresizekjv2_2 = _node(wf, 'ImageResizeKJv2', '5221',
        widget_0=512,
        widget_1=512,
        widget_2='nearest-exact',
        widget_3='crop',
        widget_4='0, 0, 0',
        widget_5='center',
        widget_6=2,
        widget_7='cpu',
        divisible_by=simplemath_.out(0),
        height=getimagesize_2.out(1),
        image=getnode_55.out(0),
        width=getimagesize_2.out(0),
    )
    ltx2attentiontunerpatch = _node(wf, 'LTX2AttentionTunerPatch', '5233',
        widget_0='',
        widget_1=1,
        widget_2=1,
        widget_3=1,
        widget_4=1,
        widget_5=True,
        model=ltxvchunkfeedforward.out(0),
    )
    setnode_34 = _node(wf, 'SetNode', '5293',
        widget_0='audio_selected',
        AUDIO=comfyswitchnode_5.out(0),
    )
    ltxvseparateavlatent = _node(wf, 'LTXVSeparateAVLatent', '4845',
        av_latent=samplercustomadvanced.out(0),
    )
    getimagesize = _node(wf, 'GetImageSize', '5029',
        image=imageresizekjv2_2.out(0),
    )
    imageblend = _node(wf, 'ImageBlend', '5115',
        widget_0=0.5,
        widget_1='multiply',
        image1=dwpreprocessor.out(0),
        image2=depthanythingpreprocessor.out(0),
    )
    vhs_videocombine = _node(wf, 'VHS_VideoCombine', '5120',
        images=imageresizekjv2_2.out(0),
    )
    setnode_7 = _node(wf, 'SetNode', '5151',
        widget_0='ref_video',
        IMAGE=imageresizekjv2_2.out(0),
    )
    setnode_11 = _node(wf, 'SetNode', '5161',
        widget_0='positive',
        CONDITIONING=ltxvconditioning.out(0),
    )
    setnode_12 = _node(wf, 'SetNode', '5162',
        widget_0='negative',
        CONDITIONING=ltxvconditioning.out(1),
    )
    power_lora_loader__rgthree_ = _node(wf, 'Power Lora Loader (rgthree)', '5275',
        widget_3='',
        model=ltx2attentiontunerpatch.out(0),
    )
    setnode_31 = _node(wf, 'SetNode', '5277',
        widget_0='ref_pose',
        IMAGE=dwpreprocessor.out(0),
    )
    ltxvcropguides = _node(wf, 'LTXVCropGuides', '5013',
        latent=ltxvseparateavlatent.out(0),
        negative=getnode_20.out(0),
        positive=getnode_19.out(0),
    )
    setnode_8 = _node(wf, 'SetNode', '5153',
        widget_0='ref_height',
        INT=getimagesize.out(1),
    )
    setnode_9 = _node(wf, 'SetNode', '5154',
        widget_0='ref_width',
        INT=getimagesize.out(0),
    )
    setnode_10 = _node(wf, 'SetNode', '5155',
        widget_0='ref_frames',
        INT=getimagesize.out(2),
    )
    setnode_25 = _node(wf, 'SetNode', '5234',
        widget_0='model_with_lora',
        MODEL=power_lora_loader__rgthree_.out(0),
    )
    setnode_30 = _node(wf, 'SetNode', '5276',
        widget_0='ref_blended',
        IMAGE=imageblend.out(0),
    )
    ltxvimgtovideoinplace = _node(wf, 'LTXVImgToVideoInplace', '5067',
        widget_0=0.7,
        widget_1=False,
        bypass=getnode_27.out(0),
        image=getnode_25.out(0),
        latent=ltxvcropguides.out(2),
        vae=getnode_4.out(0),
    )
    ltxvconcatavlatent_2 = _node(wf, 'LTXVConcatAVLatent', '5072',
        audio_latent=ltxvseparateavlatent.out(1),
        video_latent=ltxvimgtovideoinplace.out(0),
    )
    samplercustomadvanced_2 = _node(wf, 'SamplerCustomAdvanced', '5073',
        guider=cfgguider_2.out(0),
        latent_image=ltxvconcatavlatent_2.out(0),
        noise=randomnoise_2.out(0),
        sampler=ksamplerselect_2.out(0),
        sigmas=manualsigmas_2.out(0),
    )
    ltxvseparateavlatent_2 = _node(wf, 'LTXVSeparateAVLatent', '5074',
        av_latent=samplercustomadvanced_2.out(0),
    )
    ltxvaudiovaedecode = _node(wf, 'LTXVAudioVAEDecode', '5076',
        audio_vae=getnode_6.out(0),
        samples=ltxvseparateavlatent_2.out(1),
    )
    ltxvcropguides_2 = _node(wf, 'LTXVCropGuides', '5082',
        latent=ltxvseparateavlatent_2.out(0),
        negative=getnode_23.out(0),
        positive=getnode_24.out(0),
    )
    vaedecodetiled = _node(wf, 'VAEDecodeTiled', '5075',
        tile_size=544,
        overlap=64,
        temporal_size=4096,
        temporal_overlap=4,
        samples=ltxvcropguides_2.out(2),
        vae=getnode_5.out(0),
    )
    comfyswitchnode_2 = _node(wf, 'ComfySwitchNode', '5264',
        widget_0=True,
        on_false=ltxvaudiovaedecode.out(0),
        on_true=getnode_36.out(0),
        switch=getnode_65.out(0),
    )
    setnode_28 = _node(wf, 'SetNode', '5265',
        widget_0='audio_output',
        AUDIO=comfyswitchnode_2.out(0),
    )
    setnode_29 = _node(wf, 'SetNode', '5266',
        widget_0='video_output',
        IMAGE=vaedecodetiled.out(0),
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
