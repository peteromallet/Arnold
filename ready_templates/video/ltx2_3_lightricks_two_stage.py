# vibecomfy: manual
# Promoted because the upstream Lightricks source JSON is not present in this checkout.
"""Auto-generated ready_template — see tools/convert_ready_templates.py."""
from __future__ import annotations

from vibecomfy.workflow import VibeWorkflow, WorkflowSource
from vibecomfy.registry.ready_template import apply_ready_template_policy, bind_output


READY_METADATA = {'model_assets': [],
 'unbound_inputs': {'seed': 3779},
 'ready_template': 'video/ltx2_3_lightricks_two_stage',
 'workflow_template': 'ltx2_3_lightricks_two_stage',
 'capability': 'text_or_image_to_video_upscale',
 'source_role': 'materialized_ready_python_template',
 'source_workflow': 'workflow_corpus/custom_nodes/ltxvideo/lightricks_2_3/LTX-2.3_T2V_I2V_Two_Stage_Distilled.json',
 'coverage_tier': 'required',
 'approach': 'official two-stage low-VRAM T2V/I2V with latent spatial upscaler',
 'runtime_note': None,
 'manual_promotion_rationale': 'Promoted during sprint 7 because the declared upstream source workflow is absent; preserve the materialized graph and curate public contracts manually.',
 'discord_signal': 'Longer clips and upscale passes were recurring LTX channel themes.',
 'smoke_resolution': '256x256x5_frames',
 'ltx_best_practices': ['Use the official Lightricks workflows as runtime gates where possible.',
                        'Patch smoke runs to fp8/fp4 model assets, tiny frame counts, and low-VRAM loaders.',
                        'Bypass latent spatial upscalers in smoke runs until HiddenSwitch Comfy exposes '
                        'model_mmap_residency for LatentUpscaleModelManageable.',
                        'Keep community audio, lip-sync, and long-form workflows as ready templates until '
                        'their custom node packs and service credentials are declared.'],
 'comfy_configuration': {'reserve_vram': 12, 'cache_none': True, 'fp8_e4m3fn_text_enc': True}}

READY_REQUIREMENTS = {'models': [],
 'custom_nodes': ['ComfyUI-KJNodes', 'ComfyUI-LTXVideo'],
 'custom_node_refs': [{'slug': 'ComfyUI-KJNodes',
                       'source': 'git',
                       'commit': 'b7646ad70a7daa7aeb919ca542274758d26ba2df',
                       'url': 'https://github.com/kijai/ComfyUI-KJNodes.git'},
                      {'slug': 'ComfyUI-LTXVideo',
                       'source': 'git',
                       'url': 'https://github.com/Lightricks/ComfyUI-LTXVideo.git'}]}


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
        noise_seed=43,
        control_after_generate='fixed',
    )
    randomnoise_2 = _node(wf, 'RandomNoise', '4967',
        noise_seed=42,
        control_after_generate='fixed',
    )
    ksamplerselect_2 = _node(wf, 'KSamplerSelect', '4976',
        sampler_name='euler_cfg_pp',
    )
    primitivestring = _node(wf, 'PrimitiveString', '4979',
        value='',
    )
    ltxavtextencoderloader = _node(wf, 'LTXAVTextEncoderLoader', '4982',
        ckpt_name='ltx-2.3-22b-dev-fp8.safetensors',
        text_encoder='gemma_3_12B_it_fp4_mixed.safetensors',
        widget_0='gemma_3_12B_it_fp4_mixed.safetensors',
        widget_1='ltx-2.3-22b-dev-fp8.safetensors',
        widget_2='default',
    )
    manualsigmas = _node(wf, 'ManualSigmas', '4984',
        widget_0='1.0, 0.99375, 0.9875, 0.98125, 0.975, 0.909375, 0.725, 0.421875, 0.0',
    )
    manualsigmas_2 = _node(wf, 'ManualSigmas', '4985',
        widget_0='0.85, 0.7250, 0.4219, 0.0',
    )
    primitiveboolean = _node(wf, 'PrimitiveBoolean', '4987',
        value=True,
    )
    primitiveint = _node(wf, 'PrimitiveInt', '4988',
        value=5,
        widget_1='fixed',
    )
    primitivefloat = _node(wf, 'PrimitiveFloat', '4989',
        value=8,
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
        width=256,
        height=256,
        batch_size=1,
        widget_0=256,
        widget_1=256,
        widget_2=5,
        length=primitiveint.out(0),
    )
    loraloadermodelonly = _node(wf, 'LoraLoaderModelOnly', '4922',
        lora_name='ltxv/ltx2/ltx-2.3-22b-distilled-lora-384-1.1.safetensors',
        strength_model=0.5,
        model=lowvramcheckpointloader.out(0),
    )
    gemmaapitextencode = _node(wf, 'GemmaAPITextEncode', '4980',
        widget_0='',
        widget_1='',
        widget_2='ltx-2.3-22b-dev-fp8.safetensors',
        widget_3='ltx-2.3-22b-dev-fp8.safetensors',
        api_key=primitivestring.out(0),
    )
    gemmaapitextencode_2 = _node(wf, 'GemmaAPITextEncode', '4981',
        widget_0='',
        widget_1=384,
        widget_2=False,
        widget_3='ltx-2.3-22b-dev-fp8.safetensors',
        api_key=primitivestring.out(0),
    )
    resizeimagemasknode = _node(wf, 'ResizeImageMaskNode', '4990',
        widget_0='scale longer dimension',
        widget_1=256,
        widget_2='lanczos',
        input=loadimage.out(0),
    )
    ltxfloattoint = _node(wf, 'LTXFloatToInt', '5000',
        widget_0=0,
        a=primitivefloat.out(0),
    )
    ltxvconditioning = _node(wf, 'LTXVConditioning', '1241',
        widget_0=8,
        frame_rate=primitivefloat.out(0),
        negative=cliptextencode_2.out(0),
        positive=cliptextencode.out(0),
    )
    ltxvpreprocess = _node(wf, 'LTXVPreprocess', '3336',
        widget_0=18,
        image=resizeimagemasknode.out(0),
    )
    ltxvemptylatentaudio = _node(wf, 'LTXVEmptyLatentAudio', '3980',
        widget_0=5,
        widget_1=8,
        widget_2=1,
        audio_vae=lowvramaudiovaeloader.out(0),
        frame_rate=ltxfloattoint.out(0),
        frames_number=primitiveint.out(0),
    )
    ltxvimgtovideoconditiononly = _node(wf, 'LTXVImgToVideoConditionOnly', '3159',
        widget_0=0.7,
        widget_1=False,
        bypass=primitiveboolean.out(0),
        image=ltxvpreprocess.out(0),
        latent=emptyltxvlatentvideo.out(0),
        vae=lowvramcheckpointloader.out(2),
    )
    cfgguider = _node(wf, 'CFGGuider', '4828',
        cfg=2.5,
        model=loraloadermodelonly.out(0),
        negative=ltxvconditioning.out(1),
        positive=ltxvconditioning.out(0),
    )
    cfgguider_2 = _node(wf, 'CFGGuider', '4964',
        cfg=2.5,
        model=loraloadermodelonly.out(0),
        negative=ltxvconditioning.out(1),
        positive=ltxvconditioning.out(0),
    )
    ltxvconcatavlatent = _node(wf, 'LTXVConcatAVLatent', '4528',
        audio_latent=ltxvemptylatentaudio.out(0),
        video_latent=ltxvimgtovideoconditiononly.out(0),
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
    ltxvimgtovideoconditiononly_2 = _node(wf, 'LTXVImgToVideoConditionOnly', '4970',
        widget_0=1,
        widget_1=False,
        bypass=primitiveboolean.out(0),
        image=resizeimagemasknode.out(0),
        latent=ltxvseparateavlatent.out(0),
        vae=lowvramcheckpointloader.out(2),
    )
    ltxvconcatavlatent_2 = _node(wf, 'LTXVConcatAVLatent', '4969',
        audio_latent=ltxvseparateavlatent.out(1),
        video_latent=ltxvimgtovideoconditiononly_2.out(0),
    )
    samplercustomadvanced_2 = _node(wf, 'SamplerCustomAdvanced', '4971',
        guider=cfgguider_2.out(0),
        latent_image=ltxvconcatavlatent_2.out(0),
        noise=randomnoise_2.out(0),
        sampler=ksamplerselect_2.out(0),
        sigmas=manualsigmas_2.out(0),
    )
    ltxvseparateavlatent_2 = _node(wf, 'LTXVSeparateAVLatent', '4973',
        av_latent=samplercustomadvanced_2.out(0),
    )
    ltxvaudiovaedecode = _node(wf, 'LTXVAudioVAEDecode', '4848',
        audio_vae=lowvramaudiovaeloader.out(0),
        samples=ltxvseparateavlatent_2.out(1),
    )
    ltxvtiledvaedecode = _node(wf, 'LTXVTiledVAEDecode', '4995',
        widget_0=2,
        widget_1=2,
        widget_2=6,
        widget_3=False,
        widget_4='auto',
        widget_5='auto',
        latents=ltxvseparateavlatent_2.out(0),
        vae=lowvramcheckpointloader.out(2),
    )
    createvideo = _node(wf, 'CreateVideo', '4849',
        widget_0=8,
        fps=primitivefloat.out(0),
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
    bind_output(
        wf,
        '4852',
        output_type='SaveVideo',
        name='video',
        artifact_kind='video',
        mime_type='video/mp4',
        filename_prefix='output',
        expected_cardinality='one',
    )
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
