# vibecomfy: generated — converted by tools/convert_ready_templates.py
# Edits will be overwritten on regeneration. Add a `# vibecomfy: manual`
# marker on the first line if hand-editing is required.
"""Auto-generated ready_template — see tools/convert_ready_templates.py."""
from __future__ import annotations

from vibecomfy.workflow import VibeWorkflow, WorkflowSource
from vibecomfy.registry.ready_template import apply_ready_template_policy
from vibecomfy.patches.ltx_lowvram import apply as apply_ltx_lowvram
from vibecomfy.patches.requirements import ensure_custom_nodes
from vibecomfy.patches.resolution import resolution


READY_METADATA = {'model_assets': [],
 'unbound_inputs': {'seed': 1919},
 'ready_template': 'video/ltx2_3_t2v',
 'workflow_template': 'ltx2_3_t2v',
 'capability': 'text_to_video',
 'source_role': 'materialized_ready_python_template',
 'source_workflow': 'workflow_corpus/custom_nodes/ltxvideo/ltx2_3_single_stage_distilled_full.json',
 'coverage_tier': 'required',
 'approach': None,
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

READY_REQUIREMENTS = {'models': [], 'custom_nodes': ['ComfyUI-KJNodes', 'ComfyUI-LTXVideo']}


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
        widget_0='egyptian_queen.png',
    )
    lowvramaudiovaeloader = _node(wf, 'LowVRAMAudioVAELoader', '4010',
        ckpt_name='ltx-2.3-22b-dev-fp8.safetensors',
    )
    randomnoise = _node(wf, 'RandomNoise', '4814',
        noise_seed=42,
    )
    ksamplerselect = _node(wf, 'KSamplerSelect', '4831',
        sampler_name='euler_ancestral_cfg_pp',
    )
    randomnoise_2 = _node(wf, 'RandomNoise', '4832',
        noise_seed=43,
    )
    ltxavtextencoderloader = _node(wf, 'LTXAVTextEncoderLoader', '4960',
        ckpt_name='ltx-2.3-22b-dev.safetensors',
        device='default',
        text_encoder='comfy_gemma_3_12B_it.safetensors',
    )
    guiderparameters = _node(wf, 'GuiderParameters', '4963',
        UNKNOWN=True,
    )
    clownsampler_beta = _node(wf, 'ClownSampler_Beta', '4967',
        UNKNOWN=True,
    )
    manualsigmas = _node(wf, 'ManualSigmas', '4971',
        sigmas='1.0, 0.99375, 0.9875, 0.98125, 0.975, 0.909375, 0.725, 0.421875, 0.0',
    )
    primitiveboolean = _node(wf, 'PrimitiveBoolean', '4977',
        value=True,
        widget_0=False,
    )
    primitivefloat = _node(wf, 'PrimitiveFloat', '4978',
        value=24,
        widget_0=8,
    )
    primitiveint = _node(wf, 'PrimitiveInt', '4979',
        value=121,
        widget_0=9,
    )
    cliptextencode = _node(wf, 'CLIPTextEncode', '2483',
        text='A traditional Japanese tea ceremony takes place in a tatami room as a host carefully prepares matcha. Soft traditional koto music plays in the background, adding to the serene atmosphere. The bamboo whisk taps rhythmically against the ceramic bowl while water simmers in an iron kettle. Guests kneel in formal seiza position, watching in respectful silence. The host bows and presents the tea bowl, turning it precisely before offering it to the first guest with soft-spoken words.',
        clip=ltxavtextencoderloader.out(0),
    )
    cliptextencode_2 = _node(wf, 'CLIPTextEncode', '2612',
        text='pc game, console game, video game, cartoon, childish, ugly',
        clip=ltxavtextencoderloader.out(0),
    )
    emptyltxvlatentvideo = _node(wf, 'EmptyLTXVLatentVideo', '3059',
        width=384,
        height=256,
        batch_size=1,
        widget_0=384,
        widget_1=256,
        widget_2=9,
        length=primitiveint.out(0),
    )
    lowvramcheckpointloader = _node(wf, 'LowVRAMCheckpointLoader', '3940',
        ckpt_name='ltx-2.3-22b-dev-fp8.safetensors',
        dependencies=ltxavtextencoderloader.out(0),
    )
    guiderparameters_2 = _node(wf, 'GuiderParameters', '4964',
        UNKNOWN=True,
        parameters=guiderparameters.out(0),
    )
    resizeimagemasknode = _node(wf, 'ResizeImageMaskNode', '4981',
        resize_type='scale longer dimension',
        scale_method='lanczos',
        widget_1=384,
        input=loadimage.out(0),
        _extras={'resize_type.longer_size': 1536},
    )
    ltxfloattoint = _node(wf, 'LTXFloatToInt', '4985',
        UNKNOWN=0,
        a=primitivefloat.out(0),
    )
    ltxvconditioning = _node(wf, 'LTXVConditioning', '1241',
        widget_0=8,
        frame_rate=primitivefloat.out(0),
        negative=cliptextencode_2.out(0),
        positive=cliptextencode.out(0),
    )
    ltxvpreprocess = _node(wf, 'LTXVPreprocess', '3336',
        img_compression=18,
        image=resizeimagemasknode.out(0),
    )
    ltxvemptylatentaudio = _node(wf, 'LTXVEmptyLatentAudio', '3980',
        batch_size=1,
        widget_0=9,
        widget_1=8,
        audio_vae=lowvramaudiovaeloader.out(0),
        frame_rate=ltxfloattoint.out(0),
        frames_number=primitiveint.out(0),
    )
    loraloadermodelonly = _node(wf, 'LoraLoaderModelOnly', '4922',
        lora_name='ltxv/ltx2/ltx-2.3-22b-distilled-lora-384-1.1.safetensors',
        strength_model=0.5,
        model=lowvramcheckpointloader.out(0),
    )
    loraloadermodelonly_2 = _node(wf, 'LoraLoaderModelOnly', '4968',
        lora_name='ltxv/ltx2/ltx-2.3-22b-distilled-lora-384-1.1.safetensors',
        strength_model=0.2,
        model=lowvramcheckpointloader.out(0),
    )
    ltxvimgtovideoconditiononly = _node(wf, 'LTXVImgToVideoConditionOnly', '3159',
        UNKNOWN=False,
        bypass=primitiveboolean.out(0),
        image=ltxvpreprocess.out(0),
        latent=emptyltxvlatentvideo.out(0),
        vae=lowvramcheckpointloader.out(2),
    )
    multimodalguider = _node(wf, 'MultimodalGuider', '4808',
        UNKNOWN='28',
        model=loraloadermodelonly_2.out(0),
        negative=ltxvconditioning.out(1),
        parameters=guiderparameters_2.out(0),
        positive=ltxvconditioning.out(0),
    )
    cfgguider = _node(wf, 'CFGGuider', '4828',
        cfg=1,
        model=loraloadermodelonly.out(0),
        negative=ltxvconditioning.out(1),
        positive=ltxvconditioning.out(0),
    )
    ltxvconcatavlatent = _node(wf, 'LTXVConcatAVLatent', '4528',
        audio_latent=ltxvemptylatentaudio.out(0),
        video_latent=ltxvimgtovideoconditiononly.out(0),
    )
    samplercustomadvanced_2 = _node(wf, 'SamplerCustomAdvanced', '4829',
        guider=cfgguider.out(0),
        latent_image=ltxvconcatavlatent.out(0),
        noise=randomnoise_2.out(0),
        sampler=ksamplerselect.out(0),
        sigmas=manualsigmas.out(0),
    )
    ltxvscheduler = _node(wf, 'LTXVScheduler', '4966',
        base_shift=0.95,
        max_shift=2.05,
        steps=15,
        stretch=True,
        terminal=0.1,
        latent=ltxvconcatavlatent.out(0),
    )
    samplercustomadvanced = _node(wf, 'SamplerCustomAdvanced', '4802',
        guider=multimodalguider.out(0),
        latent_image=ltxvconcatavlatent.out(0),
        noise=randomnoise.out(0),
        sampler=clownsampler_beta.out(0),
        sigmas=ltxvscheduler.out(0),
    )
    ltxvseparateavlatent_2 = _node(wf, 'LTXVSeparateAVLatent', '4845',
        av_latent=samplercustomadvanced_2.out(0),
    )
    ltxvseparateavlatent = _node(wf, 'LTXVSeparateAVLatent', '4824',
        av_latent=samplercustomadvanced.out(0),
    )
    ltxvaudiovaedecode_2 = _node(wf, 'LTXVAudioVAEDecode', '4848',
        audio_vae=lowvramaudiovaeloader.out(0),
        samples=ltxvseparateavlatent_2.out(1),
    )
    ltxvtiledvaedecode = _node(wf, 'LTXVTiledVAEDecode', '4982',
        UNKNOWN='auto',
        latents=ltxvseparateavlatent_2.out(0),
        vae=lowvramcheckpointloader.out(2),
    )
    ltxvaudiovaedecode = _node(wf, 'LTXVAudioVAEDecode', '4818',
        audio_vae=lowvramaudiovaeloader.out(0),
        samples=ltxvseparateavlatent.out(1),
    )
    createvideo_2 = _node(wf, 'CreateVideo', '4849',
        fps=primitivefloat.out(0),
        audio=ltxvaudiovaedecode_2.out(0),
        images=ltxvtiledvaedecode.out(0),
    )
    ltxvtiledvaedecode_2 = _node(wf, 'LTXVTiledVAEDecode', '4983',
        UNKNOWN='auto',
        latents=ltxvseparateavlatent.out(0),
        vae=lowvramcheckpointloader.out(2),
    )
    createvideo = _node(wf, 'CreateVideo', '4819',
        fps=primitivefloat.out(0),
        audio=ltxvaudiovaedecode.out(0),
        images=ltxvtiledvaedecode_2.out(0),
    )
    savevideo_2 = _node(wf, 'SaveVideo', '4852',
        filename_prefix='output_D',
        format='auto',
        codec='auto',
        video=createvideo_2.out(0),
    )
    savevideo = _node(wf, 'SaveVideo', '4823',
        filename_prefix='output_F',
        format='auto',
        codec='auto',
        video=createvideo.out(0),
    )

    apply_ltx_lowvram(wf)
    resolution(384, 256, 9).apply(wf)
    ensure_custom_nodes(wf, READY_REQUIREMENTS["custom_nodes"])
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
