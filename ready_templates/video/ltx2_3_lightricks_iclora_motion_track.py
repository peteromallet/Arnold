# vibecomfy: manual
# Promoted because the upstream Lightricks source JSON is not present in this checkout.
"""Auto-generated ready_template — see tools/convert_ready_templates.py."""
from __future__ import annotations

from vibecomfy.workflow import VibeWorkflow, WorkflowSource
from vibecomfy.registry.ready_template import apply_ready_template_policy, bind_output


READY_METADATA = {'model_assets': [],
 'unbound_inputs': {'seed': 4825},
 'ready_template': 'video/ltx2_3_lightricks_iclora_motion_track',
 'workflow_template': 'ltx2_3_lightricks_iclora_motion_track',
 'capability': 'motion_track_control',
 'source_role': 'materialized_ready_python_template',
 'source_workflow': 'workflow_corpus/custom_nodes/ltxvideo/lightricks_2_3/LTX-2.3_ICLoRA_Motion_Track_Distilled.json',
 'coverage_tier': 'required',
 'approach': 'official IC-LoRA motion-track image anchor/control workflow',
 'runtime_note': None,
 'manual_promotion_rationale': 'Promoted during sprint 7 because the declared upstream source workflow is absent; preserve the materialized graph and curate public contracts manually.',
 'discord_signal': 'Motion transfer, body/camera movement, and image anchors were recurring LTX channel '
                   'themes.',
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
    primitiveint = _node(wf, 'PrimitiveInt', '5044',
        value=5,
        widget_1='fixed',
    )
    primitivefloat = _node(wf, 'PrimitiveFloat', '5045',
        value=8,
    )
    cliptextencode = _node(wf, 'CLIPTextEncode', '2483',
        text='Man on a small bycicle being chased by a police car. The sirens are blaring and the crowd of bystanders is cheering loudly. As he is pedaling away on the bike, he looks back at the police car and shouts in a taunting tone: "you can\'t catch me!" and waving his fist in the air. He then pedals away on his bike.',
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
    resizeimagemasknode = _node(wf, 'ResizeImageMaskNode', '5049',
        widget_0='scale shorter dimension',
        widget_1=256,
        widget_2='lanczos',
        input=loadimage.out(0),
    )
    ltxfloattoint = _node(wf, 'LTXFloatToInt', '5059',
        widget_0=0,
        a=primitivefloat.out(0),
    )
    ltxvconditioning = _node(wf, 'LTXVConditioning', '1241',
        widget_0=8,
        frame_rate=primitivefloat.out(0),
        negative=cliptextencode_2.out(0),
        positive=cliptextencode.out(0),
    )
    ltxvemptylatentaudio = _node(wf, 'LTXVEmptyLatentAudio', '3980',
        widget_0=5,
        widget_1=8,
        widget_2=1,
        audio_vae=lowvramaudiovaeloader.out(0),
        frame_rate=ltxfloattoint.out(0),
        frames_number=primitiveint.out(0),
    )
    ltxicloraloadermodelonly = _node(wf, 'LTXICLoRALoaderModelOnly', '5011',
        lora_name='ltx-2.3-22b-ic-lora-motion-track-control-ref0.5.safetensors',
        widget_0='ltx-2.3-22b-ic-lora-motion-track-control-ref0.5.safetensors',
        widget_1=1,
        model=loraloadermodelonly.out(0),
    )
    simplemath_ = _node(wf, 'SimpleMath+', '5056',
        widget_0='a*32',
        a=ltxicloraloadermodelonly.out(1),
    )
    resizeimagemasknode_2 = _node(wf, 'ResizeImageMaskNode', '5053',
        widget_0='scale to multiple',
        widget_1=256,
        widget_2='lanczos',
        input=resizeimagemasknode.out(0),
        _extras={'resize_type.multiple': simplemath_.out(0)},
    )
    ltxvsparsetrackeditor = _node(wf, 'LTXVSparseTrackEditor', '5040',
        widget_0='[[{"x":385.0759251206301,"y":238.92165891412267},{"x":226.6706827038015,"y":321.895716789677},{"x":118.7556948262006,"y":334.34620347590675},{"x":8.857468951125458,"y":294.56719637193584}],[{"x":550.4183052326947,"y":246.43019177413228},{"x":530.2019095759371,"y":493.9392986305124}]]',
        widget_1='[[{"x":385,"y":239},{"x":383,"y":240},{"x":381,"y":241},{"x":378,"y":243},{"x":375,"y":244},{"x":373,"y":246},{"x":369,"y":248},{"x":366,"y":249},{"x":363,"y":251},{"x":359,"y":253},{"x":355,"y":255},{"x":352,"y":258},{"x":348,"y":260},{"x":344,"y":262},{"x":339,"y":265},{"x":335,"y":267},{"x":331,"y":270},{"x":326,"y":272},{"x":322,"y":275},{"x":317,"y":277},{"x":313,"y":280},{"x":308,"y":282},{"x":303,"y":285},{"x":299,"y":287},{"x":294,"y":290},{"x":289,"y":292},{"x":285,"y":295},{"x":280,"y":297},{"x":275,"y":300},{"x":271,"y":302},{"x":266,"y":304},{"x":262,"y":306},{"x":258,"y":308},{"x":253,"y":311},{"x":249,"y":312},{"x":245,"y":314},{"x":241,"y":316},{"x":237,"y":318},{"x":234,"y":319},{"x":230,"y":321},{"x":227,"y":322},{"x":223,"y":323},{"x":220,"y":324},{"x":217,"y":325},{"x":214,"y":326},{"x":211,"y":327},{"x":208,"y":328},{"x":205,"y":329},{"x":202,"y":330},{"x":199,"y":330},{"x":196,"y":331},{"x":193,"y":332},{"x":191,"y":332},{"x":188,"y":333},{"x":185,"y":334},{"x":183,"y":334},{"x":180,"y":334},{"x":177,"y":335},{"x":175,"y":335},{"x":172,"y":336},{"x":170,"y":336},{"x":167,"y":336},{"x":165,"y":336},{"x":162,"y":336},{"x":160,"y":337},{"x":157,"y":337},{"x":155,"y":337},{"x":152,"y":337},{"x":150,"y":337},{"x":147,"y":337},{"x":145,"y":337},{"x":142,"y":336},{"x":140,"y":336},{"x":137,"y":336},{"x":135,"y":336},{"x":132,"y":336},{"x":129,"y":336},{"x":127,"y":335},{"x":124,"y":335},{"x":121,"y":335},{"x":119,"y":334},{"x":116,"y":334},{"x":113,"y":333},{"x":110,"y":333},{"x":107,"y":332},{"x":104,"y":332},{"x":101,"y":331},{"x":98,"y":330},{"x":95,"y":329},{"x":92,"y":328},{"x":89,"y":327},{"x":86,"y":326},{"x":82,"y":325},{"x":79,"y":324},{"x":76,"y":323},{"x":73,"y":322},{"x":70,"y":320},{"x":66,"y":319},{"x":63,"y":318},{"x":60,"y":317},{"x":57,"y":315},{"x":54,"y":314},{"x":51,"y":313},{"x":48,"y":311},{"x":45,"y":310},{"x":42,"y":309},{"x":39,"y":308},{"x":37,"y":306},{"x":34,"y":305},{"x":31,"y":304},{"x":29,"y":303},{"x":26,"y":302},{"x":24,"y":301},{"x":22,"y":300},{"x":19,"y":299},{"x":17,"y":298},{"x":15,"y":297},{"x":14,"y":296},{"x":12,"y":296},{"x":10,"y":295},{"x":9,"y":295}],[{"x":550,"y":246},{"x":550,"y":248},{"x":550,"y":251},{"x":550,"y":253},{"x":550,"y":255},{"x":550,"y":257},{"x":549,"y":259},{"x":549,"y":261},{"x":549,"y":263},{"x":549,"y":265},{"x":549,"y":267},{"x":549,"y":269},{"x":548,"y":271},{"x":548,"y":273},{"x":548,"y":275},{"x":548,"y":277},{"x":548,"y":279},{"x":548,"y":281},{"x":547,"y":284},{"x":547,"y":286},{"x":547,"y":288},{"x":547,"y":290},{"x":547,"y":292},{"x":547,"y":294},{"x":546,"y":296},{"x":546,"y":298},{"x":546,"y":300},{"x":546,"y":302},{"x":546,"y":304},{"x":546,"y":306},{"x":545,"y":308},{"x":545,"y":310},{"x":545,"y":312},{"x":545,"y":314},{"x":545,"y":317},{"x":545,"y":319},{"x":544,"y":321},{"x":544,"y":323},{"x":544,"y":325},{"x":544,"y":327},{"x":544,"y":329},{"x":544,"y":331},{"x":543,"y":333},{"x":543,"y":335},{"x":543,"y":337},{"x":543,"y":339},{"x":543,"y":341},{"x":543,"y":343},{"x":542,"y":345},{"x":542,"y":347},{"x":542,"y":350},{"x":542,"y":352},{"x":542,"y":354},{"x":541,"y":356},{"x":541,"y":358},{"x":541,"y":360},{"x":541,"y":362},{"x":541,"y":364},{"x":541,"y":366},{"x":540,"y":368},{"x":540,"y":370},{"x":540,"y":372},{"x":540,"y":374},{"x":540,"y":376},{"x":540,"y":378},{"x":539,"y":380},{"x":539,"y":383},{"x":539,"y":385},{"x":539,"y":387},{"x":539,"y":389},{"x":539,"y":391},{"x":538,"y":393},{"x":538,"y":395},{"x":538,"y":397},{"x":538,"y":399},{"x":538,"y":401},{"x":538,"y":403},{"x":537,"y":405},{"x":537,"y":407},{"x":537,"y":409},{"x":537,"y":411},{"x":537,"y":413},{"x":537,"y":416},{"x":536,"y":418},{"x":536,"y":420},{"x":536,"y":422},{"x":536,"y":424},{"x":536,"y":426},{"x":536,"y":428},{"x":535,"y":430},{"x":535,"y":432},{"x":535,"y":434},{"x":535,"y":436},{"x":535,"y":438},{"x":535,"y":440},{"x":534,"y":442},{"x":534,"y":444},{"x":534,"y":447},{"x":534,"y":449},{"x":534,"y":451},{"x":534,"y":453},{"x":533,"y":455},{"x":533,"y":457},{"x":533,"y":459},{"x":533,"y":461},{"x":533,"y":463},{"x":533,"y":465},{"x":532,"y":467},{"x":532,"y":469},{"x":532,"y":471},{"x":532,"y":473},{"x":532,"y":475},{"x":532,"y":477},{"x":531,"y":480},{"x":531,"y":482},{"x":531,"y":484},{"x":531,"y":486},{"x":531,"y":488},{"x":531,"y":490},{"x":530,"y":492},{"x":530,"y":494}]]',
        widget_2=121,
        widget_3='',
        image=resizeimagemasknode_2.out(0),
        points_to_sample=primitiveint.out(0),
    )
    getimagesize = _node(wf, 'GetImageSize', '5050',
        image=resizeimagemasknode_2.out(0),
    )
    emptyltxvlatentvideo = _node(wf, 'EmptyLTXVLatentVideo', '3059',
        batch_size=1,
        widget_0=256,
        widget_1=256,
        widget_2=5,
        width=getimagesize.out(0),
        height=getimagesize.out(1),
        length=primitiveint.out(0),
    )
    ltxvdrawtracks = _node(wf, 'LTXVDrawTracks', '5034',
        widget_0='',
        widget_1=512,
        widget_2=512,
        height=getimagesize.out(1),
        tracks=ltxvsparsetrackeditor.out(0),
        width=getimagesize.out(0),
    )
    ltxvimgtovideoconditiononly = _node(wf, 'LTXVImgToVideoConditionOnly', '3159',
        widget_0=1,
        widget_1=False,
        image=resizeimagemasknode_2.out(0),
        latent=emptyltxvlatentvideo.out(0),
        vae=lowvramcheckpointloader.out(2),
    )
    createvideo_2 = _node(wf, 'CreateVideo', '5051',
        widget_0=8,
        fps=primitivefloat.out(0),
        images=ltxvdrawtracks.out(0),
    )
    ltxaddvideoicloraguide = _node(wf, 'LTXAddVideoICLoRAGuide', '5012',
        widget_0=0,
        widget_1=1,
        widget_2=1,
        widget_3='disabled',
        widget_4=False,
        widget_5=128,
        widget_6=32,
        image=ltxvdrawtracks.out(0),
        latent=ltxvimgtovideoconditiononly.out(0),
        latent_downscale_factor=ltxicloraloadermodelonly.out(1),
        negative=ltxvconditioning.out(1),
        positive=ltxvconditioning.out(0),
        vae=lowvramcheckpointloader.out(2),
    )
    savevideo_2 = _node(wf, 'SaveVideo', '5052',
        filename_prefix='output',
        format='auto',
        codec='auto',
        video=createvideo_2.out(0),
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
    ltxvtiledvaedecode = _node(wf, 'LTXVTiledVAEDecode', '5058',
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
        '5052',
        output_type='SaveVideo',
        name='preview_video',
        artifact_kind='video',
        mime_type='video/mp4',
        filename_prefix='output',
        expected_cardinality='one',
    )
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
