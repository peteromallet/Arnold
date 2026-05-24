# vibecomfy: generated — converted by tools/convert_ready_templates.py
# Edits will be overwritten on regeneration. Add a `# vibecomfy: manual`
# marker on the first line if hand-editing is required.
"""Auto-generated ready_template — see tools/convert_ready_templates.py."""
from __future__ import annotations

from vibecomfy.workflow import VibeWorkflow, WorkflowSource
from vibecomfy.registry.ready_template import apply_ready_template_policy


READY_METADATA = {'model_assets': [],
 'unbound_inputs': {'seed': 3154},
 'ready_template': 'video/ltx2_3_iamccs_long_i2v',
 'workflow_template': 'ltx2_3_iamccs_long_i2v',
 'capability': 'long_image_to_video',
 'source_role': 'materialized_ready_python_template',
 'source_workflow': 'workflow_corpus/custom_nodes/ltxvideo/iamccs/IAMCCS_LTX2_I2V_LONG_LENGTH.json',
 'coverage_tier': 'supplemental',
 'approach': 'long low-VRAM image-to-video',
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

READY_REQUIREMENTS = {'models': [], 'custom_nodes': ['ComfyUI-GGUF', 'ComfyUI-KJNodes', 'ComfyUI-LTXVideo']}


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

    primitivestringmultiline = _node(wf, 'PrimitiveStringMultiline', '5175',
        value='Cinematic action packed shot. the man says silently: "We need to run." the camera zooms in on his mouth then immediately screams: "NOW!". the camera zooms back out, he turns around, and starts running away, the camera tracks his run in hand held style.',
    )
    checkpointloadersimple = _node(wf, 'CheckpointLoaderSimple', '5176',
        ckpt_name='ltx-2-19b-distilled.safetensors',
    )
    ltxvgemmaclipmodelloader = _node(wf, 'LTXVGemmaCLIPModelLoader', '5178',
        widget_0='gemma_3_12B_it_fp8_e4m3fn.safetensors',
        widget_1='ltx-2-19b-distilled.safetensors',
        widget_2=1024,
    )
    loadimage = _node(wf, 'LoadImage', '5180',
        image='z-image_00255_.png',
        widget_1='image',
    )
    lowvramaudiovaeloader = _node(wf, 'LowVRAMAudioVAELoader', '5188',
        ckpt_name='ltx-2.3-22b-dev-fp8.safetensors',
    )
    latentupscalemodelloader = _node(wf, 'LatentUpscaleModelLoader', '5210',
        widget_0='ltx-2-spatial-upscaler-x2-1.0.safetensors',
    )
    unetloadergguf = _node(wf, 'UnetLoaderGGUF', '5215',
        widget_0='LTX-2-dev-Q5_K_S.gguf',
    )
    iamccs_ltx2_lorastackstaged = _node(wf, 'IAMCCS_LTX2_LoRAStackStaged', '5218',
        widget_0='ltx-2-19b-distilled-lora-384.safetensors',
        widget_1=1,
        widget_2=1,
        widget_3='ltx-2-19b-lora-camera-control-dolly-right.safetensors',
        widget_4=0,
        widget_5=0,
        widget_6='no',
        widget_7=0,
        widget_8=0,
    )
    vaeloaderkj = _node(wf, 'VAELoaderKJ', '5220',
        widget_0='LTX2_video_vae_2_bf16.safetensors',
        widget_1='main_device',
        widget_2='bf16',
    )
    vaeloaderkj_2 = _node(wf, 'LTXVAudioVAELoader', '5221',
        ckpt_name='LTX23_audio_vae_bf16.safetensors',
    )
    dualcliploader = _node(wf, 'DualCLIPLoader', '5222',
        clip_name1='gemma_3_12B_it_fp8_e4m3fn.safetensors',
        clip_name2='ltx-2-19b-embeddings_connector_dev_bf16.safetensors',
        type='ltxv',
        device='default',
    )
    iamccs_ltx2_frameratesync = _node(wf, 'IAMCCS_LTX2_FrameRateSync', '5225',
        widget_0=24,
        widget_1='fixed',
    )
    primitivestringmultiline_2 = _node(wf, 'PrimitiveStringMultiline', '5232',
        value='man runs away from camera. the camera cranes up and show him run into the distance down the street at a busy New York night.',
    )
    fast_groups_muter__rgthree_ = _node(wf, 'Fast Groups Muter (rgthree)', '5265')
    primitivestringmultiline_3 = _node(wf, 'PrimitiveStringMultiline', '9001',
        value='the camera cranes up and show the whole streets of new york.',
    )
    iamccs_autolinkarguments = _node(wf, 'IAMCCS_AutoLinkArguments', '9026',
        widget_0=False,
        widget_1=False,
        widget_10='Red',
        widget_11='Orange',
        widget_12='Black',
        widget_13='',
        widget_14='',
        widget_15='both',
        widget_17='',
        widget_19='',
        widget_2=False,
        widget_3=True,
        widget_4='None',
        widget_5='',
        widget_6='TopToDown',
        widget_7='AvoidAll',
        widget_8='',
        widget_9=True,
    )
    emptyimage = _node(wf, 'EmptyImage', '10955',
        widget_0=1332,
        widget_1=720,
        widget_2=1,
        widget_3=0,
    )
    iamccs_ltx2_timeframecount = _node(wf, 'IAMCCS_LTX2_TimeFrameCount', '10956',
        widget_0=10,
        widget_1=241,
        widget_2='fixed',
    )
    iamccs_modelwithlora_ltx2_staged = _node(wf, 'IAMCCS_ModelWithLoRA_LTX2_Staged', '5219',
        lora_stage1=iamccs_ltx2_lorastackstaged.out(0),
        lora_stage2=iamccs_ltx2_lorastackstaged.out(1),
        model=unetloadergguf.out(0),
        model_stage2=unetloadergguf.out(0),
    )
    iamccs_ltx2_lorastackmodelio = _node(wf, 'IAMCCS_LTX2_LoRAStackModelIO', '5259',
        widget_0='ltx-2-19b-distilled-lora-384.safetensors',
        widget_1=1,
        widget_2='no',
        widget_3=0,
        widget_4='no',
        widget_5=0,
        model=checkpointloadersimple.out(0),
    )
    any_switch__rgthree__2 = _node(wf, 'Any Switch (rgthree)', '5261',
        any_01=lowvramaudiovaeloader.out(0),
        any_02=vaeloaderkj_2.out(0),
    )
    any_switch__rgthree__3 = _node(wf, 'Any Switch (rgthree)', '5262',
        any_01=ltxvgemmaclipmodelloader.out(0),
        any_02=dualcliploader.out(0),
    )
    any_switch__rgthree__4 = _node(wf, 'Any Switch (rgthree)', '5263',
        any_01=checkpointloadersimple.out(2),
        any_02=vaeloaderkj.out(0),
    )
    iamccs_autolinkconverter = _node(wf, 'IAMCCS_AutoLinkConverter', '9025',
        arg=iamccs_autolinkarguments.out(0),
    )
    negative = _node(wf, 'CLIPTextEncode', '5174',
        widget_0='',
        text=primitivestringmultiline.out(0),
        clip=any_switch__rgthree__3.out(0),
    )
    negative_2 = _node(wf, 'CLIPTextEncode', '5233',
        widget_0='',
        text=primitivestringmultiline_2.out(0),
        clip=any_switch__rgthree__3.out(0),
    )
    negative_3 = _node(wf, 'CLIPTextEncode', '9002',
        widget_0='',
        text=primitivestringmultiline_3.out(0),
        clip=any_switch__rgthree__3.out(0),
    )
    iamccs_gguf_accelerator = _node(wf, 'IAMCCS_GGUF_accelerator', '9684',
        widget_0=True,
        widget_1=True,
        widget_2=True,
        widget_3=1500,
        widget_4=True,
        widget_5='all_or_nothing',
        widget_6=1024,
        model=iamccs_modelwithlora_ltx2_staged.out(1),
    )
    iamccs_gguf_accelerator_2 = _node(wf, 'IAMCCS_GGUF_accelerator', '9685',
        widget_0=True,
        widget_1=True,
        widget_2=True,
        widget_3=1500,
        widget_4=True,
        widget_5='all_or_nothing',
        widget_6=1024,
        model=iamccs_modelwithlora_ltx2_staged.out(1),
    )
    ltxvconditioning = _node(wf, 'LTXVConditioning', '5173',
        widget_0=8,
        frame_rate=iamccs_ltx2_frameratesync.out(1),
        negative=negative.out(0),
        positive=negative.out(0),
    )
    ltxvconditioning_2 = _node(wf, 'LTXVConditioning', '5234',
        widget_0=8,
        frame_rate=iamccs_ltx2_frameratesync.out(1),
        negative=negative_2.out(0),
        positive=negative_2.out(0),
    )
    any_switch__rgthree_ = _node(wf, 'Any Switch (rgthree)', '5258',
        any_01=iamccs_ltx2_lorastackmodelio.out(0),
        any_02=iamccs_gguf_accelerator.out(0),
    )
    any_switch__rgthree__5 = _node(wf, 'Any Switch (rgthree)', '5264',
        any_01=iamccs_ltx2_lorastackmodelio.out(0),
        any_02=iamccs_gguf_accelerator_2.out(0),
    )
    ltxvconditioning_3 = _node(wf, 'LTXVConditioning', '9003',
        widget_0=8,
        frame_rate=iamccs_ltx2_frameratesync.out(1),
        negative=negative_3.out(0),
        positive=negative_3.out(0),
    )
    n_3eaa20c4_5842_4fe4_87df_c0a7e83a6a78 = _node(wf, '3eaa20c4-5842-4fe4-87df-c0a7e83a6a78', '5189',
        widget_0=121,
        widget_1=25,
        widget_2=0.6,
        widget_3=43,
        audio_vae=any_switch__rgthree__2.out(0),
        frame_rate=iamccs_ltx2_frameratesync.out(0),
        image_1=emptyimage.out(0),
        images=loadimage.out(0),
        length=iamccs_ltx2_timeframecount.out(0),
        model=any_switch__rgthree__5.out(0),
        model_1=any_switch__rgthree_.out(0),
        negative=ltxvconditioning.out(1),
        positive=ltxvconditioning.out(0),
        upscale_model_1=latentupscalemodelloader.out(0),
        vae=any_switch__rgthree__4.out(0),
    )
    createvideo = _node(wf, 'CreateVideo', '5190',
        widget_0=8,
        fps=iamccs_ltx2_frameratesync.out(1),
        audio=n_3eaa20c4_5842_4fe4_87df_c0a7e83a6a78.out(1),
        images=n_3eaa20c4_5842_4fe4_87df_c0a7e83a6a78.out(0),
    )
    iamccs_ltx2_getimagefrombatch = _node(wf, 'IAMCCS_LTX2_GetImageFromBatch', '9014',
        widget_0='from_end',
        widget_1=10,
        widget_2='none',
        widget_3='none',
        widget_4='none',
        widget_5='native_workflow_safe',
        widget_6=10,
        widget_7=0,
        widget_8=10,
        images=n_3eaa20c4_5842_4fe4_87df_c0a7e83a6a78.out(0),
    )
    savevideo = _node(wf, 'SaveVideo', '4958',
        filename_prefix='output',
        format='mp4',
        codec='h264',
        video=createvideo.out(0),
    )
    n_8b36a85a_087e_4ee5_85ca_cccc69c5c5d0 = _node(wf, '8b36a85a-087e-4ee5-85ca-cccc69c5c5d0', '5235',
        widget_0=121,
        widget_1=24,
        widget_2=0.6,
        widget_3=43,
        audio_vae=any_switch__rgthree__2.out(0),
        frame_rate=iamccs_ltx2_frameratesync.out(0),
        image_1=emptyimage.out(0),
        images=iamccs_ltx2_getimagefrombatch.out(0),
        length=iamccs_ltx2_timeframecount.out(0),
        model=any_switch__rgthree__5.out(0),
        model_1=any_switch__rgthree_.out(0),
        negative=ltxvconditioning_2.out(1),
        positive=ltxvconditioning_2.out(0),
        upscale_model_1=latentupscalemodelloader.out(0),
        vae=any_switch__rgthree__4.out(0),
    )
    createvideo_2 = _node(wf, 'CreateVideo', '5236',
        widget_0=8,
        fps=iamccs_ltx2_frameratesync.out(1),
        audio=n_8b36a85a_087e_4ee5_85ca_cccc69c5c5d0.out(1),
        images=n_8b36a85a_087e_4ee5_85ca_cccc69c5c5d0.out(0),
    )
    audioconcat = _node(wf, 'AudioConcat', '5252',
        widget_0='after',
        audio1=n_3eaa20c4_5842_4fe4_87df_c0a7e83a6a78.out(1),
        audio2=n_8b36a85a_087e_4ee5_85ca_cccc69c5c5d0.out(1),
    )
    iamccs_ltx2_extensionmodule = _node(wf, 'IAMCCS_LTX2_ExtensionModule', '9015',
        widget_0=10,
        widget_1='source',
        widget_10='none',
        widget_11=0,
        widget_12=1,
        widget_13=0.5,
        widget_14='target_extension_ltx2',
        widget_15=1,
        widget_2='linear_blend',
        widget_3=True,
        widget_4='a-1',
        widget_5='none',
        widget_6='none',
        widget_7='none',
        widget_8=0,
        widget_9=8,
        new_images=n_8b36a85a_087e_4ee5_85ca_cccc69c5c5d0.out(0),
        source_images=n_3eaa20c4_5842_4fe4_87df_c0a7e83a6a78.out(0),
    )
    savevideo_2 = _node(wf, 'SaveVideo', '5237',
        filename_prefix='output',
        format='mp4',
        codec='h264',
        video=createvideo_2.out(0),
    )
    n_8b36a85a_087e_4ee5_85ca_cccc69c5c5d0_2 = _node(wf, '8b36a85a-087e-4ee5-85ca-cccc69c5c5d0', '9004',
        widget_0=121,
        widget_1=24,
        widget_2=0.6,
        widget_3=43,
        audio_vae=any_switch__rgthree__2.out(0),
        frame_rate=iamccs_ltx2_frameratesync.out(0),
        image_1=emptyimage.out(0),
        images=iamccs_ltx2_extensionmodule.out(1),
        length=iamccs_ltx2_timeframecount.out(0),
        model=any_switch__rgthree__5.out(0),
        model_1=any_switch__rgthree_.out(0),
        negative=ltxvconditioning_3.out(1),
        positive=ltxvconditioning_3.out(0),
        upscale_model_1=latentupscalemodelloader.out(0),
        vae=any_switch__rgthree__4.out(0),
    )
    createvideo_4 = _node(wf, 'CreateVideo', '9005',
        widget_0=8,
        fps=iamccs_ltx2_frameratesync.out(1),
        audio=n_8b36a85a_087e_4ee5_85ca_cccc69c5c5d0_2.out(1),
        images=n_8b36a85a_087e_4ee5_85ca_cccc69c5c5d0_2.out(0),
    )
    audioconcat_2 = _node(wf, 'AudioConcat', '9008',
        widget_0='after',
        audio1=audioconcat.out(0),
        audio2=n_8b36a85a_087e_4ee5_85ca_cccc69c5c5d0_2.out(1),
    )
    iamccs_ltx2_extensionmodule_2 = _node(wf, 'IAMCCS_LTX2_ExtensionModule', '9016',
        widget_0=10,
        widget_1='source',
        widget_10='none',
        widget_11=0,
        widget_12=1,
        widget_13=0.5,
        widget_14='target_extension_ltx2',
        widget_15=1,
        widget_2='linear_blend',
        widget_3=True,
        widget_4='a-1',
        widget_5='none',
        widget_6='none',
        widget_7='none',
        widget_8=0,
        widget_9=8,
        new_images=n_8b36a85a_087e_4ee5_85ca_cccc69c5c5d0_2.out(0),
        source_images=iamccs_ltx2_extensionmodule.out(2),
    )
    createvideo_3 = _node(wf, 'CreateVideo', '5254',
        widget_0=8,
        fps=iamccs_ltx2_frameratesync.out(1),
        audio=audioconcat_2.out(0),
        images=iamccs_ltx2_extensionmodule_2.out(2),
    )
    savevideo_4 = _node(wf, 'SaveVideo', '9006',
        filename_prefix='output',
        format='mp4',
        codec='h264',
        video=createvideo_4.out(0),
    )
    savevideo_3 = _node(wf, 'SaveVideo', '5255',
        filename_prefix='output',
        format='mp4',
        codec='h264',
        video=createvideo_3.out(0),
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
