# vibecomfy: manual
# Edits will be overwritten on regeneration. Add a `# vibecomfy: manual`
# marker on the first line if hand-editing is required.
"""Auto-generated ready_template — see tools/convert_ready_templates.py."""
from __future__ import annotations

from vibecomfy.workflow import VibeWorkflow, WorkflowSource
from vibecomfy.registry.ready_template import apply_ready_template_policy


LTX_RUNEXX_MODEL_ASSETS = [
    {
        "name": "ltx-2.3_text_projection_bf16.safetensors",
        "url": "https://huggingface.co/Kijai/LTX2.3_comfy/resolve/main/text_encoders/ltx-2.3_text_projection_bf16.safetensors",
        "subdir": "text_encoders",
    },
    {
        "name": "LTX23_video_vae_bf16.safetensors",
        "url": "https://huggingface.co/Kijai/LTX2.3_comfy/resolve/main/vae/LTX23_video_vae_bf16.safetensors",
        "subdir": "vae",
    },
    {
        "name": "LTX23_audio_vae_bf16.safetensors",
        "url": "https://huggingface.co/Kijai/LTX2.3_comfy/resolve/main/vae/LTX23_audio_vae_bf16.safetensors",
        "subdir": "vae",
    },
    {
        "name": "taeltx2_3.safetensors",
        "url": "https://huggingface.co/Kijai/LTX2.3_comfy/resolve/main/vae/taeltx2_3.safetensors",
        "subdir": "vae",
    },
    {
        "name": "ltx-2.3-22b-distilled-1.1_transformer_only_fp8_scaled.safetensors",
        "url": "https://huggingface.co/Kijai/LTX2.3_comfy/resolve/main/diffusion_models/ltx-2.3-22b-distilled-1.1_transformer_only_fp8_scaled.safetensors",
        "subdir": "diffusion_models",
    },
    {
        "name": "LTX/v2/ltx-2.3-22b-distilled-1.1_lora-dynamic_fro09_avg_rank_111_bf16.safetensors",
        "url": "https://huggingface.co/Kijai/LTX2.3_comfy/resolve/main/loras/ltx-2.3-22b-distilled-1.1_lora-dynamic_fro09_avg_rank_111_bf16.safetensors",
        "subdir": "loras",
    },
]


READY_METADATA = {'model_assets': LTX_RUNEXX_MODEL_ASSETS,
 'unbound_inputs': {'seed': 4831},
 'ready_template': 'video/ltx2_3_runexx_first_middle_last_frame',
 'workflow_template': 'ltx2_3_runexx_first_middle_last_frame',
 'capability': 'first_middle_last_frame_video',
 'source_role': 'materialized_ready_python_template',
 'source_workflow': 'workflow_corpus/custom_nodes/ltxvideo/runexx/LTX-2.3_FML2V_First_Middle_Last_Frame_guider.json',
 'coverage_tier': 'supplemental',
 'approach': 'multi-anchor image-guided video',
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

    ksamplerselect = _node(wf, 'KSamplerSelect', '1',
        sampler_name='euler_ancestral_cfg_pp',
    )
    ksamplerselect_2 = _node(wf, 'KSamplerSelect', '4',
        sampler_name='euler_cfg_pp',
    )
    manualsigmas = _node(wf, 'ManualSigmas', '5',
        widget_0='0.909375, 0.725, 0.421875, 0.0',
    )
    randomnoise = _node(wf, 'RandomNoise', '14',
        noise_seed=43,
        control_after_generate='fixed',
    )
    randomnoise_2 = _node(wf, 'RandomNoise', '15',
        noise_seed=42,
        control_after_generate='fixed',
    )
    loadimage = _node(wf, 'LoadImage', '45',
        image='sodacan_01.png',
        widget_1='image',
    )
    loadimage_2 = _node(wf, 'LoadImage', '47',
        image='image (11).png',
        widget_1='image',
    )
    getnode = _node(wf, 'GetNode', '70',
        widget_0='width',
    )
    getnode_2 = _node(wf, 'GetNode', '71',
        widget_0='height',
    )
    getnode_3 = _node(wf, 'GetNode', '91',
        widget_0='fps',
    )
    getnode_4 = _node(wf, 'GetNode', '93',
        widget_0='fps',
    )
    getnode_5 = _node(wf, 'GetNode', '117',
        widget_0='vae_audio',
    )
    getnode_6 = _node(wf, 'GetNode', '120',
        widget_0='vae',
    )
    getnode_7 = _node(wf, 'GetNode', '122',
        widget_0='model',
    )
    getnode_8 = _node(wf, 'GetNode', '124',
        widget_0='clip',
    )
    getnode_9 = _node(wf, 'GetNode', '127',
        widget_0='frames',
    )
    getnode_10 = _node(wf, 'GetNode', '128',
        widget_0='width',
    )
    getnode_11 = _node(wf, 'GetNode', '129',
        widget_0='height',
    )
    getnode_12 = _node(wf, 'GetNode', '133',
        widget_0='upscale_model',
    )
    getnode_13 = _node(wf, 'GetNode', '137',
        widget_0='fps',
    )
    getnode_14 = _node(wf, 'GetNode', '147',
        widget_0='vae',
    )
    getnode_15 = _node(wf, 'GetNode', '148',
        widget_0='vae_audio',
    )
    vaeloaderkj = _node(wf, 'VAELoaderKJ', '175',
        widget_0='LTX23_audio_vae_bf16.safetensors',
        widget_1='main_device',
        widget_2='bf16',
    )
    vaeloader = _node(wf, 'VAELoader', '180',
        vae_name='taeltx2_3.safetensors',
    )
    vaeloader_2 = _node(wf, 'VAELoader', '181',
        vae_name='LTX23_video_vae_bf16.safetensors',
    )
    latentupscalemodelloader = _node(wf, 'LatentUpscaleModelLoader', '182',
        widget_0='ltx-2.3-spatial-upscaler-x2-1.1.safetensors',
    )
    unetloader = _node(wf, 'UNETLoader', '187',
        unet_name='ltx-2.3-22b-distilled-1.1_transformer_only_fp8_scaled.safetensors',
        weight_dtype='default',
    )
    dualcliploadergguf = _node(wf, 'DualCLIPLoaderGGUF', '189',
        widget_0='gemma-3-12b-it-Q2_K.gguf',
        widget_1='ltx-2.3_text_projection_bf16.safetensors',
        widget_2='ltxv',
    )
    dualcliploader = _node(wf, 'DualCLIPLoader', '190',
        clip_name1='gemma_3_12B_it_fp4_mixed.safetensors',
        clip_name2='ltx-2.3_text_projection_bf16.safetensors',
        type='ltxv',
        device='default',
    )
    unetloadergguf = _node(wf, 'UnetLoaderGGUF', '191',
        widget_0='LTXvideo\\LTX-2\\quantstack\\LTX-2.3-distilled-Q4_K_S.gguf',
    )
    getnode_16 = _node(wf, 'GetNode', '193',
        widget_0='vae_tiny',
    )
    getnode_17 = _node(wf, 'GetNode', '196',
        widget_0='negative',
    )
    getnode_18 = _node(wf, 'GetNode', '200',
        widget_0='model_nag',
    )
    getnode_19 = _node(wf, 'GetNode', '201',
        widget_0='model_nag',
    )
    getnode_20 = _node(wf, 'GetNode', '203',
        widget_0='final_video',
    )
    getnode_21 = _node(wf, 'GetNode', '204',
        widget_0='final_audio',
    )
    manualsigmas_2 = _node(wf, 'ManualSigmas', '215',
        widget_0='1.0, 0.99375, 0.9875, 0.98125, 0.975, 0.909375, 0.725, 0.421875, 0.0',
    )
    manualsigmas_3 = _node(wf, 'ManualSigmas', '216',
        widget_0='0.85, 0.7250, 0.4219, 0.0',
    )
    getnode_22 = _node(wf, 'GetNode', '219',
        widget_0='height',
    )
    getnode_23 = _node(wf, 'GetNode', '220',
        widget_0='width',
    )
    getnode_24 = _node(wf, 'GetNode', '224',
        widget_0='lastframe',
    )
    getnode_25 = _node(wf, 'GetNode', '225',
        widget_0='firstframe',
    )
    getnode_26 = _node(wf, 'GetNode', '2067',
        widget_0='clip',
    )
    getnode_27 = _node(wf, 'GetNode', '2068',
        widget_0='enhance_prompt',
    )
    primitivefloat = _node(wf, 'PrimitiveFloat', '2076',
        value=8,
    )
    intconstant = _node(wf, 'INTConstant', '2078',
        widget_0=15,
    )
    intconstant_2 = _node(wf, 'INTConstant', '2079',
        widget_0=720,
    )
    intconstant_3 = _node(wf, 'INTConstant', '2080',
        widget_0=1280,
    )
    primitiveboolean = _node(wf, 'PrimitiveBoolean', '2082',
        value=True,
    )
    n_19e3f7e8_881c_4a61_a360_1c463734043a = _node(wf, '19e3f7e8-881c-4a61-a360-1c463734043a', '2102')
    primitivestringmultiline = _node(wf, 'PrimitiveStringMultiline', '2103',
        value='Make this come alive with cinematic motion, smooth animation. \n\nThe scene starts with a close up of an LTX soda can with ic cubes around it. \n\nAll of a suddent an arm comes into frame and grabs the soda can, and lifts the soda can up. \n\nCamera pans up smoothly to show a woman holding the soda can. She talks with a soft British voice, and she says :" An LTX a day, keeps the doctor away". Then she laghts, and finally she drinks from the soda can. ',
    )
    getnode_28 = _node(wf, 'GetNode', '2106',
        widget_0='lastframe',
    )
    primitivefloat_2 = _node(wf, 'PrimitiveFloat', '2108',
        value=8,
    )
    primitivefloat_3 = _node(wf, 'PrimitiveFloat', '2110',
        value=8,
    )
    getnode_29 = _node(wf, 'GetNode', '2154',
        widget_0='negative_guider',
    )
    getnode_30 = _node(wf, 'GetNode', '2155',
        widget_0='vae',
    )
    getnode_31 = _node(wf, 'GetNode', '2163',
        widget_0='positive_guider',
    )
    getnode_32 = _node(wf, 'GetNode', '2166',
        widget_0='negative_guider2',
    )
    getnode_33 = _node(wf, 'GetNode', '2167',
        widget_0='positive_guider2',
    )
    loadimage_3 = _node(wf, 'LoadImage', '2172',
        image='image (12).png',
        widget_1='image',
    )
    getnode_34 = _node(wf, 'GetNode', '2173',
        widget_0='middleframe',
    )
    getnode_35 = _node(wf, 'GetNode', '2175',
        widget_0='frames',
    )
    getnode_36 = _node(wf, 'GetNode', '2187',
        widget_0='firstframe_strength',
    )
    getnode_37 = _node(wf, 'GetNode', '2188',
        widget_0='lastframe_strength',
    )
    getnode_38 = _node(wf, 'GetNode', '2189',
        widget_0='middleframe_strength',
    )
    getnode_39 = _node(wf, 'GetNode', '2214',
        widget_0='latent_audio',
    )
    getnode_40 = _node(wf, 'GetNode', '2220',
        widget_0='firstframe',
    )
    getnode_41 = _node(wf, 'GetNode', '2226',
        widget_0='lastframe_strength',
    )
    getnode_42 = _node(wf, 'GetNode', '2255',
        widget_0='vae',
    )
    getnode_43 = _node(wf, 'GetNode', '2259',
        widget_0='negative_guider',
    )
    getnode_44 = _node(wf, 'GetNode', '2260',
        widget_0='positive_guider',
    )
    getnode_45 = _node(wf, 'GetNode', '2276',
        widget_0='firstframe_strength',
    )
    primitivefloat_4 = _node(wf, 'PrimitiveFloat', '2278',
        value=8,
    )
    getnode_46 = _node(wf, 'GetNode', '2279',
        widget_0='firstframe_strength',
    )
    getnode_47 = _node(wf, 'GetNode', '2280',
        widget_0='lastframe_strength',
    )
    getnode_48 = _node(wf, 'GetNode', '2281',
        widget_0='middleframe_strength',
    )
    cliptextencode = _node(wf, 'CLIPTextEncode', '11',
        text='blurry, oversaturated, pixelated, low resolution, grainy, distorted, noise, compression artifacts, jpeg artifacts, glitches, watermark, text, logo, signature, copyright, subtitles, distorted sound, saturated sound, loud',
        clip=getnode_8.out(0),
    )
    vhs_videocombine = _node(wf, 'VHS_VideoCombine', '43',
        audio=getnode_21.out(0),
        filename_prefix='reigh_vibecomfy_ltx_first_middle_last',
        format='video/h264-mp4',
        frame_rate=getnode_13.out(0),
        images=getnode_20.out(0),
        loop_count=0,
        pingpong=False,
        save_output=True,
    )
    imageresizekjv2 = _node(wf, 'ImageResizeKJv2', '44',
        widget_0=960,
        widget_1=544,
        widget_2='lanczos',
        widget_3='crop',
        widget_4='0, 0, 0',
        widget_5='center',
        widget_6=32,
        widget_7='cpu',
        height=getnode_2.out(0),
        image=loadimage.out(0),
        width=getnode.out(0),
    )
    ltxvpreprocess = _node(wf, 'LTXVPreprocess', '50',
        widget_0=18,
        image=getnode_24.out(0),
    )
    simplecalculatorkj = _node(wf, 'SimpleCalculatorKJ', '92',
        widget_0='a',
        a=getnode_3.out(0),
    )
    setnode_5 = _node(wf, 'SetNode', '171',
        widget_0='upscale_model',
        LATENT_UPSCALE_MODEL=latentupscalemodelloader.out(0),
    )
    setnode_6 = _node(wf, 'SetNode', '172',
        widget_0='vae_audio',
        VAE=vaeloaderkj.out(0),
    )
    setnode_7 = _node(wf, 'SetNode', '173',
        widget_0='vae',
        VAE=vaeloader_2.out(0),
    )
    setnode_8 = _node(wf, 'SetNode', '177',
        widget_0='vae_tiny',
        VAE=vaeloader.out(0),
    )
    loraloadermodelonly = _node(wf, 'LoraLoaderModelOnly', '186',
        lora_name='LTX\\v2\\ltx-2.3-22b-distilled-1.1_lora-dynamic_fro09_avg_rank_111_bf16.safetensors',
        strength_model=0.6,
        model=unetloader.out(0),
    )
    setnode_9 = _node(wf, 'SetNode', '188',
        widget_0='clip',
        CLIP=dualcliploader.out(0),
    )
    ltx2samplingpreviewoverride = _node(wf, 'LTX2SamplingPreviewOverride', '198',
        widget_0=8,
        model=getnode_7.out(0),
        vae=getnode_16.out(0),
    )
    n_8fa4f93a_67ee_463f_ba43_249580c0bfb1 = _node(wf, '8fa4f93a-67ee-463f-ba43-249580c0bfb1', '2070',
        _1=primitivestringmultiline.out(0),
        clip=getnode_26.out(0),
        image=n_19e3f7e8_881c_4a61_a360_1c463734043a.out(0),
    )
    setnode_13 = _node(wf, 'SetNode', '2072',
        widget_0='height',
        INT=intconstant_2.out(0),
    )
    setnode_14 = _node(wf, 'SetNode', '2073',
        widget_0='width',
        INT=intconstant_3.out(0),
    )
    setnode_15 = _node(wf, 'SetNode', '2074',
        widget_0='fps',
        FLOAT=primitivefloat.out(0),
    )
    simplecalculatorkj_2 = _node(wf, 'SimpleCalculatorKJ', '2077',
        widget_0='((round((a * b -1) / 8)) * 8) + 1 ',
        a=intconstant.out(0),
        b=primitivefloat.out(0),
    )
    setnode_17 = _node(wf, 'SetNode', '2081',
        widget_0='enhance_prompt',
        BOOLEAN=primitiveboolean.out(0),
    )
    ltxvpreprocess_2 = _node(wf, 'LTXVPreprocess', '2084',
        widget_0=18,
        image=getnode_25.out(0),
    )
    setnode_18 = _node(wf, 'SetNode', '2112',
        widget_0='firstframe_strength',
        FLOAT=primitivefloat_3.out(0),
    )
    setnode_19 = _node(wf, 'SetNode', '2113',
        widget_0='lastframe_strength',
        FLOAT=primitivefloat_2.out(0),
    )
    ltxvpreprocess_3 = _node(wf, 'LTXVPreprocess', '2174',
        widget_0=18,
        image=getnode_34.out(0),
    )
    comfymathexpression = _node(wf, 'ComfyMathExpression', '2191',
        widget_0='a/2',
        _extras={'values.a': getnode_23.out(0)},
    )
    comfymathexpression_2 = _node(wf, 'ComfyMathExpression', '2192',
        widget_0='a/2',
        _extras={'values.a': getnode_22.out(0)},
    )
    simplecalculatorkj_3 = _node(wf, 'SimpleCalculatorKJ', '2216',
        widget_0='a/2',
        _extras={'variables.a': getnode_35.out(0)},
    )
    setnode_31 = _node(wf, 'SetNode', '2277',
        widget_0='middleframe_strength',
        FLOAT=primitivefloat_4.out(0),
    )
    ltxvemptylatentaudio = _node(wf, 'LTXVEmptyLatentAudio', '9',
        widget_0=5,
        widget_1=8,
        widget_2=1,
        audio_vae=getnode_5.out(0),
        frame_rate=simplecalculatorkj.out(1),
        frames_number=getnode_9.out(0),
    )
    cliptextencode_2 = _node(wf, 'CLIPTextEncode', '16',
        widget_0='= enhanced prompt = ',
        text=n_8fa4f93a_67ee_463f_ba43_249580c0bfb1.out(0),
        clip=getnode_8.out(0),
    )
    wf.replace_edge('16.text', primitivestringmultiline.out(0))
    wf.remove_node('2070')
    wf.remove_node('2102')
    emptyltxvlatentvideo = _node(wf, 'EmptyLTXVLatentVideo', '32',
        batch_size=1,
        widget_0=256,
        widget_1=256,
        widget_2=5,
        width=comfymathexpression.out(1),
        height=comfymathexpression_2.out(1),
        length=getnode_9.out(0),
    )
    imageresizekjv2_2 = _node(wf, 'ImageResizeKJv2', '48',
        widget_0=512,
        widget_1=512,
        widget_2='lanczos',
        widget_3='crop',
        widget_4='0, 0, 0',
        widget_5='center',
        widget_6=32,
        widget_7='cpu',
        height=imageresizekjv2.out(2),
        image=loadimage_2.out(0),
        width=imageresizekjv2.out(1),
    )
    ltx2_nag = _node(wf, 'LTX2_NAG', '197',
        widget_0=11,
        widget_1=0.25,
        widget_2=2.5,
        widget_3=True,
        model=ltx2samplingpreviewoverride.out(0),
        nag_cond_audio=getnode_17.out(0),
        nag_cond_video=getnode_17.out(0),
    )
    pathchsageattentionkj = _node(wf, 'PathchSageAttentionKJ', '226',
        widget_0='auto',
        widget_1=False,
        model=loraloadermodelonly.out(0),
    )
    setnode_16 = _node(wf, 'SetNode', '2075',
        widget_0='frames',
        INT=simplecalculatorkj_2.out(1),
    )
    resizeimagesbylongeredge_2 = _node(wf, 'ResizeImagesByLongerEdge', '2083',
        widget_0=1536,
        images=imageresizekjv2.out(0),
    )
    setnode_23 = _node(wf, 'SetNode', '2185',
        widget_0='middleframe_count',
        INT=simplecalculatorkj_3.out(1),
    )
    setnode_25 = _node(wf, 'SetNode', '2217',
        widget_0='firstframe_resized',
        IMAGE=imageresizekjv2.out(0),
    )
    setnode_30 = _node(wf, 'SetNode', '2233',
        widget_0='negative',
        CONDITIONING=cliptextencode.out(0),
    )
    ltxvconditioning = _node(wf, 'LTXVConditioning', '10',
        widget_0=8,
        frame_rate=getnode_4.out(0),
        negative=cliptextencode.out(0),
        positive=cliptextencode_2.out(0),
    )
    resizeimagesbylongeredge = _node(wf, 'ResizeImagesByLongerEdge', '49',
        widget_0=1536,
        images=imageresizekjv2_2.out(0),
    )
    setnode = _node(wf, 'SetNode', '75',
        widget_0='firstframe',
        IMAGE=resizeimagesbylongeredge_2.out(0),
    )
    setnode_11 = _node(wf, 'SetNode', '199',
        widget_0='model_nag',
        MODEL=ltx2_nag.out(0),
    )
    ltx2memoryefficientsageattentionpatch = _node(wf, 'LTX2MemoryEfficientSageAttentionPatch', '227',
        widget_0=True,
        model=pathchsageattentionkj.out(0),
    )
    imageresizekjv2_3 = _node(wf, 'ImageResizeKJv2', '2171',
        widget_0=512,
        widget_1=512,
        widget_2='lanczos',
        widget_3='crop',
        widget_4='0, 0, 0',
        widget_5='center',
        widget_6=32,
        widget_7='cpu',
        height=imageresizekjv2_2.out(2),
        image=loadimage_3.out(0),
        width=imageresizekjv2_2.out(1),
    )
    setnode_24 = _node(wf, 'SetNode', '2215',
        widget_0='latent_audio',
        LATENT=ltxvemptylatentaudio.out(0),
    )
    setnode_26 = _node(wf, 'SetNode', '2218',
        widget_0='middleframe_resized',
        IMAGE=imageresizekjv2_2.out(0),
    )
    setnode_2 = _node(wf, 'SetNode', '78',
        widget_0='middleframe',
        IMAGE=resizeimagesbylongeredge.out(0),
    )
    ltxvchunkfeedforward = _node(wf, 'LTXVChunkFeedForward', '228',
        widget_0=2,
        widget_1=4096,
        model=ltx2memoryefficientsageattentionpatch.out(0),
    )
    resizeimagesbylongeredge_3 = _node(wf, 'ResizeImagesByLongerEdge', '2168',
        widget_0=1536,
        images=imageresizekjv2_3.out(0),
    )
    setnode_27 = _node(wf, 'SetNode', '2219',
        widget_0='lastframe_resized',
        IMAGE=imageresizekjv2_3.out(0),
    )
    ltxvaddguidemulti_2 = _node(wf, 'LTXVAddGuideMulti', '2221',
        widget_0='3',
        widget_1=0,
        widget_2=0.7,
        widget_3=0,
        widget_4=0.25,
        widget_5=-1,
        widget_6=1,
        latent=emptyltxvlatentvideo.out(0),
        negative=ltxvconditioning.out(1),
        positive=ltxvconditioning.out(0),
        vae=getnode_42.out(0),
        _extras={'num_guides.frame_idx_2': simplecalculatorkj_3.out(1), 'num_guides.image_1': ltxvpreprocess_2.out(0), 'num_guides.image_2': ltxvpreprocess_3.out(0), 'num_guides.image_3': ltxvpreprocess.out(0), 'num_guides.strength_1': getnode_46.out(0), 'num_guides.strength_2': getnode_48.out(0), 'num_guides.strength_3': getnode_47.out(0)},
    )
    ltxvconcatavlatent = _node(wf, 'LTXVConcatAVLatent', '24',
        audio_latent=getnode_39.out(0),
        video_latent=ltxvaddguidemulti_2.out(2),
    )
    cfgguider_2 = _node(wf, 'CFGGuider', '36',
        cfg=2.5,
        model=getnode_18.out(0),
        negative=ltxvaddguidemulti_2.out(1),
        positive=ltxvaddguidemulti_2.out(0),
    )
    ltx2attentiontunerpatch = _node(wf, 'LTX2AttentionTunerPatch', '229',
        widget_0='',
        widget_1=1,
        widget_2=1,
        widget_3=1,
        widget_4=1,
        widget_5=True,
        model=ltxvchunkfeedforward.out(0),
    )
    setnode_22 = _node(wf, 'SetNode', '2169',
        widget_0='lastframe',
        IMAGE=resizeimagesbylongeredge_3.out(0),
    )
    setnode_28 = _node(wf, 'SetNode', '2223',
        widget_0='positive_guider',
        CONDITIONING=ltxvaddguidemulti_2.out(0),
    )
    setnode_29 = _node(wf, 'SetNode', '2224',
        widget_0='negative_guider',
        CONDITIONING=ltxvaddguidemulti_2.out(1),
    )
    ltxvscheduler = _node(wf, 'LTXVScheduler', '2',
        steps=1,
        widget_0=1,
        widget_1=2.05,
        widget_2=0.95,
        widget_3=True,
        widget_4=0.1,
        latent=ltxvconcatavlatent.out(0),
    )
    samplercustomadvanced = _node(wf, 'SamplerCustomAdvanced', '13',
        guider=cfgguider_2.out(0),
        latent_image=ltxvconcatavlatent.out(0),
        noise=randomnoise_2.out(0),
        sampler=ksamplerselect.out(0),
        sigmas=manualsigmas_2.out(0),
    )
    power_lora_loader__rgthree_ = _node(wf, 'Power Lora Loader (rgthree)', '2107',
        widget_3='',
        model=ltx2attentiontunerpatch.out(0),
    )
    ltxvseparateavlatent = _node(wf, 'LTXVSeparateAVLatent', '18',
        av_latent=samplercustomadvanced.out(0),
    )
    setnode_10 = _node(wf, 'SetNode', '192',
        widget_0='model',
        MODEL=power_lora_loader__rgthree_.out(0),
    )
    setnode_12 = _node(wf, 'SetNode', '230',
        widget_0='model_with_lora',
        MODEL=power_lora_loader__rgthree_.out(0),
    )
    ltxvcropguides_2 = _node(wf, 'LTXVCropGuides', '2222',
        latent=ltxvseparateavlatent.out(0),
        negative=getnode_43.out(0),
        positive=getnode_44.out(0),
    )
    ltxvaddguidemulti = _node(wf, 'LTXVAddGuideMulti', '2182',
        widget_0='2',
        widget_1=0,
        widget_2=1,
        widget_3=-1,
        widget_4=1,
        latent=ltxvcropguides_2.out(2),
        negative=ltxvcropguides_2.out(1),
        positive=ltxvcropguides_2.out(0),
        vae=getnode_30.out(0),
        _extras={'num_guides.image_1': getnode_40.out(0), 'num_guides.image_2': getnode_28.out(0), 'num_guides.strength_1': getnode_45.out(0), 'num_guides.strength_2': getnode_41.out(0)},
    )
    cfgguider = _node(wf, 'CFGGuider', '8',
        cfg=2.5,
        model=getnode_19.out(0),
        negative=ltxvaddguidemulti.out(1),
        positive=ltxvaddguidemulti.out(0),
    )
    ltxvconcatavlatent_2 = _node(wf, 'LTXVConcatAVLatent', '34',
        audio_latent=ltxvseparateavlatent.out(1),
        video_latent=ltxvaddguidemulti.out(2),
    )
    setnode_20 = _node(wf, 'SetNode', '2164',
        widget_0='positive_guider2',
        CONDITIONING=ltxvaddguidemulti.out(0),
    )
    setnode_21 = _node(wf, 'SetNode', '2165',
        widget_0='negative_guider2',
        CONDITIONING=ltxvaddguidemulti.out(1),
    )
    samplercustomadvanced_2 = _node(wf, 'SamplerCustomAdvanced', '21',
        guider=cfgguider.out(0),
        latent_image=ltxvconcatavlatent_2.out(0),
        noise=randomnoise.out(0),
        sampler=ksamplerselect_2.out(0),
        sigmas=manualsigmas_3.out(0),
    )
    ltxvseparateavlatent_2 = _node(wf, 'LTXVSeparateAVLatent', '146',
        av_latent=samplercustomadvanced_2.out(0),
    )
    ltxvaudiovaedecode = _node(wf, 'LTXVAudioVAEDecode', '150',
        audio_vae=getnode_15.out(0),
        samples=ltxvseparateavlatent_2.out(1),
    )
    ltxvcropguides = _node(wf, 'LTXVCropGuides', '2156',
        latent=ltxvseparateavlatent_2.out(0),
        negative=getnode_32.out(0),
        positive=getnode_33.out(0),
    )
    vaedecodetiled = _node(wf, 'VAEDecodeTiled', '149',
        tile_size=512,
        overlap=64,
        temporal_size=4096,
        temporal_overlap=8,
        samples=ltxvcropguides.out(2),
        vae=getnode_14.out(0),
    )
    setnode_4 = _node(wf, 'SetNode', '154',
        widget_0='final_audio',
        AUDIO=ltxvaudiovaedecode.out(0),
    )
    setnode_3 = _node(wf, 'SetNode', '153',
        widget_0='final_video',
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
