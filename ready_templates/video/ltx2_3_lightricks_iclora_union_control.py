# vibecomfy: generated — converted by tools/convert_ready_templates.py
# Edits will be overwritten on regeneration. Add a `# vibecomfy: manual`
# marker on the first line if hand-editing is required.
"""Auto-generated ready_template — see tools/convert_ready_templates.py."""
from __future__ import annotations

from vibecomfy.workflow import VibeWorkflow, WorkflowSource
from vibecomfy.registry.ready_template import apply_ready_template_policy


READY_METADATA = {'model_assets': [],
 'unbound_inputs': {'seed': 4952},
 'ready_template': 'video/ltx2_3_lightricks_iclora_union_control',
 'workflow_template': 'ltx2_3_lightricks_iclora_union_control',
 'capability': 'union_control_video_guided_i2v',
 'source_role': 'materialized_ready_python_template',
 'source_workflow': 'workflow_corpus/custom_nodes/ltxvideo/lightricks_2_3/LTX-2.3_ICLoRA_Union_Control_Distilled.json',
 'coverage_tier': 'supplemental',
 'approach': 'official IC-LoRA union control workflow with depth/pose-style guide preprocessing',
 'runtime_note': 'Requires additional VideoDepthAnything/DWPose model setup beyond the core LTX smoke stack.',
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
 'custom_nodes': ['ComfyUI-DepthAnythingV2', 'ComfyUI-KJNodes', 'ComfyUI-LTXVideo', 'comfyui_controlnet_aux']}


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
        image='example.png',
        widget_0='example.png',
        widget_1='image',
    )
    lowvramcheckpointloader = _node(wf, 'LowVRAMCheckpointLoader', '3940',
        ckpt_name='ltx-2.3-22b-dev-fp8.safetensors',
    )
    lowvramaudiovaeloader = _node(wf, 'LowVRAMAudioVAELoader', '4010',
        ckpt_name='ltx-2.3-22b-dev-fp8.safetensors',
    )
    ksamplerselect = _node(wf, 'KSamplerSelect', '4831',
        sampler_name='euler_ancestral_cfg_pp',
    )
    randomnoise = _node(wf, 'RandomNoise', '4832',
        noise_seed=42,
        control_after_generate='fixed',
    )
    loadvideo = _node(wf, 'LoadVideo', '5001',
        file='ltx_smoke_guide.mp4',
        video='ltx_smoke_guide.mp4',
        widget_0='ltx_smoke_guide.mp4',
        widget_1='image',
    )
    primitiveboolean = _node(wf, 'PrimitiveBoolean', '5019',
        value=True,
    )
    primitivestring = _node(wf, 'PrimitiveString', '5022',
        value='',
    )
    ltxavtextencoderloader = _node(wf, 'LTXAVTextEncoderLoader', '5023',
        ckpt_name='ltx-2.3-22b-dev-fp8.safetensors',
        text_encoder='gemma_3_12B_it_fp4_mixed.safetensors',
        widget_0='gemma_3_12B_it_fp4_mixed.safetensors',
        widget_1='ltx-2.3-22b-dev-fp8.safetensors',
        widget_2='default',
    )
    manualsigmas = _node(wf, 'ManualSigmas', '5025',
        widget_0='1.0, 0.99375, 0.9875, 0.98125, 0.975, 0.909375, 0.725, 0.421875, 0.0',
    )
    downloadandloaddepthanythingv2model = _node(wf, 'DownloadAndLoadDepthAnythingV2Model', '5060',
        model='depth_anything_v2_vits_fp32.safetensors',
        precision='fp32',
    )
    cliptextencode = _node(wf, 'CLIPTextEncode', '2483',
        text='Apocalyptic landscape with abandoned buildings, overgrown with foliage and trees. The sky is clear and the sun is setting, with the horizon turning bright red. The buildings are delapidated, falling apart and crumbling due to being abandoned for so long.\nThe air is full of silence and the only thing to be heard is a young girl breathing and saying: "Where is everyone?"',
        clip=ltxavtextencoderloader.out(0),
    )
    cliptextencode_2 = _node(wf, 'CLIPTextEncode', '2612',
        text='pc game, console game, video game, cartoon, childish, ugly',
        clip=ltxavtextencoderloader.out(0),
    )
    loraloadermodelonly = _node(wf, 'LoraLoaderModelOnly', '4922',
        lora_name='ltxv/ltx2/ltx-2.3-22b-distilled-lora-384-1.1.safetensors',
        strength_model=0.5,
        model=lowvramcheckpointloader.out(0),
    )
    getvideocomponents = _node(wf, 'GetVideoComponents', '5000',
        video=loadvideo.out(0),
    )
    gemmaapitextencode = _node(wf, 'GemmaAPITextEncode', '5020',
        widget_0='',
        widget_1='pc game, console game, video game, cartoon, childish, ugly',
        widget_2=False,
        widget_3='ltx-2.3-22b-dev-fp8.safetensors',
        api_key=primitivestring.out(0),
    )
    gemmaapitextencode_2 = _node(wf, 'GemmaAPITextEncode', '5021',
        widget_0='',
        widget_1='',
        widget_2='ltx-2.3-22b-dev-fp8.safetensors',
        widget_3='ltx-2.3-22b-dev-fp8.safetensors',
        api_key=primitivestring.out(0),
    )
    resizeimagemasknode_3 = _node(wf, 'ResizeImageMaskNode', '5035',
        widget_0='scale longer dimension',
        widget_1=256,
        widget_2='lanczos',
        input=loadimage.out(0),
    )
    ltxvconditioning = _node(wf, 'LTXVConditioning', '1241',
        widget_0=8,
        frame_rate=getvideocomponents.out(2),
        negative=cliptextencode_2.out(0),
        positive=cliptextencode.out(0),
    )
    ltxicloraloadermodelonly = _node(wf, 'LTXICLoRALoaderModelOnly', '5011',
        lora_name='ltx-2.3-22b-ic-lora-union-control-ref0.5.safetensors',
        widget_0='ltx-2.3-22b-ic-lora-union-control-ref0.5.safetensors',
        widget_1=1,
        model=loraloadermodelonly.out(0),
    )
    resizeimagemasknode = _node(wf, 'ResizeImageMaskNode', '5026',
        widget_0='scale shorter dimension',
        widget_1=256,
        widget_2='lanczos',
        input=getvideocomponents.out(0),
    )
    ltxfloattoint = _node(wf, 'LTXFloatToInt', '5066',
        widget_0=0,
        a=getvideocomponents.out(2),
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
    cannyedgepreprocessor = _node(wf, 'CannyEdgePreprocessor', '4991',
        widget_0=92,
        widget_1=200,
        widget_2=256,
        image=resizeimagemasknode.out(0),
    )
    simplemath_ = _node(wf, 'SimpleMath+', '5034',
        widget_0='a*32',
        a=ltxicloraloadermodelonly.out(1),
    )
    depthanything_v2 = _node(wf, 'DepthAnything_V2', '5061',
        da_model=downloadandloaddepthanythingv2model.out(0),
        images=resizeimagemasknode.out(0),
    )
    resizeimagemasknode_2 = _node(wf, 'ResizeImageMaskNode', '5028',
        widget_0='scale to multiple',
        widget_1=256,
        widget_2='lanczos',
        input=cannyedgepreprocessor.out(0),
        _extras={'resize_type.multiple': simplemath_.out(0)},
    )
    getimagesize = _node(wf, 'GetImageSize', '5029',
        image=resizeimagemasknode_2.out(0),
    )
    emptyltxvlatentvideo = _node(wf, 'EmptyLTXVLatentVideo', '3059',
        batch_size=1,
        widget_0=256,
        widget_1=256,
        widget_2=5,
        width=getimagesize.out(0),
        height=getimagesize.out(1),
        length=getimagesize.out(2),
    )
    ltxvemptylatentaudio = _node(wf, 'LTXVEmptyLatentAudio', '3980',
        widget_0=5,
        widget_1=8,
        widget_2=1,
        audio_vae=lowvramaudiovaeloader.out(0),
        frame_rate=ltxfloattoint.out(0),
        frames_number=getimagesize.out(2),
    )
    ltxvimgtovideoconditiononly = _node(wf, 'LTXVImgToVideoConditionOnly', '3159',
        widget_0=1,
        widget_1=False,
        bypass=primitiveboolean.out(0),
        image=resizeimagemasknode_3.out(0),
        latent=emptyltxvlatentvideo.out(0),
        vae=lowvramcheckpointloader.out(2),
    )
    ltxaddvideoicloraguide = _node(wf, 'LTXAddVideoICLoRAGuide', '5012',
        widget_0=0,
        widget_1=1,
        widget_2=1,
        widget_3='disabled',
        widget_4=False,
        widget_5=128,
        widget_6=32,
        image=resizeimagemasknode_2.out(0),
        latent=ltxvimgtovideoconditiononly.out(0),
        latent_downscale_factor=ltxicloraloadermodelonly.out(1),
        negative=ltxvconditioning.out(1),
        positive=ltxvconditioning.out(0),
        vae=lowvramcheckpointloader.out(2),
    )
    ltxvconcatavlatent = _node(wf, 'LTXVConcatAVLatent', '4528',
        audio_latent=ltxvemptylatentaudio.out(0),
        video_latent=ltxaddvideoicloraguide.out(2),
    )
    cfgguider = _node(wf, 'CFGGuider', '4828',
        cfg=2.5,
        model=ltxicloraloadermodelonly.out(0),
        negative=ltxaddvideoicloraguide.out(1),
        positive=ltxaddvideoicloraguide.out(0),
    )
    samplercustomadvanced = _node(wf, 'SamplerCustomAdvanced', '4829',
        guider=cfgguider.out(0),
        latent_image=ltxvconcatavlatent.out(0),
        noise=randomnoise.out(0),
        sampler=ksamplerselect.out(0),
        sigmas=manualsigmas.out(0),
    )
    ltxvseparateavlatent = _node(wf, 'LTXVSeparateAVLatent', '4845',
        av_latent=samplercustomadvanced.out(0),
    )
    ltxvaudiovaedecode = _node(wf, 'LTXVAudioVAEDecode', '4848',
        audio_vae=lowvramaudiovaeloader.out(0),
        samples=ltxvseparateavlatent.out(1),
    )
    ltxvcropguides = _node(wf, 'LTXVCropGuides', '5013',
        latent=ltxvseparateavlatent.out(0),
        negative=ltxaddvideoicloraguide.out(1),
        positive=ltxaddvideoicloraguide.out(0),
    )
    ltxvtiledvaedecode = _node(wf, 'LTXVTiledVAEDecode', '5065',
        widget_0=2,
        widget_1=2,
        widget_2=6,
        widget_3=False,
        widget_4='auto',
        widget_5='auto',
        latents=ltxvcropguides.out(2),
        vae=lowvramcheckpointloader.out(2),
    )
    createvideo = _node(wf, 'CreateVideo', '4849',
        widget_0=8,
        fps=getvideocomponents.out(2),
        audio=ltxvaudiovaedecode.out(0),
        images=ltxvtiledvaedecode.out(0),
    )
    savevideo = _node(wf, 'SaveVideo', '4852',
        filename_prefix='output',
        format='auto',
        codec='auto',
        video=createvideo.out(0),
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

