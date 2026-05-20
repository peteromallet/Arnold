# vibecomfy: generated - converted by tools/convert_ready_templates.py
# Edits will be overwritten on regeneration. Put the manual opt-out
# marker on the first line if hand-editing is required.
"""Auto-generated ready_template - see tools/convert_ready_templates.py."""
from __future__ import annotations

from vibecomfy.templates import InputSpec, ModelAsset, ReadyMetadata, finalize, new_workflow, node as raw_call, ref
from vibecomfy.nodes.core import CFGGuider, CLIPTextEncode, CreateVideo, EmptyLTXVLatentVideo, GetImageSize, KSamplerSelect, LTXAVTextEncoderLoader, LTXVAudioVAEDecode, LTXVConcatAVLatent, LTXVConditioning, LTXVCropGuides, LTXVEmptyLatentAudio, LTXVSeparateAVLatent, LoadImage, LoraLoaderModelOnly, ManualSigmas, RandomNoise, ResizeImageMaskNode, SamplerCustomAdvanced, SaveVideo
from vibecomfy.nodes.ltxvideo import GemmaAPITextEncode, LTXAddVideoICLoRAGuide, LTXFloatToInt, LTXICLoRALoaderModelOnly, LTXVImgToVideoConditionOnly, LTXVTiledVAEDecode, LowVRAMAudioVAELoader, LowVRAMCheckpointLoader


DEFAULT_FPS = 8
DEFAULT_FRAMES = 5
DEFAULT_PROMPT = 'Man on a small bycicle being chased by a police car. The sirens are blaring and the crowd of bystanders is cheering loudly. As he is pedaling away on the bike, he looks back at the police car and shouts in a taunting tone: "you can\'t catch me!" and waving his fist in the air. He then pedals away on his bike.'
DEFAULT_PROMPT_2 = 'pc game, console game, video game, cartoon, childish, ugly'
DEFAULT_SEED = 42
GUIDE_STRENGTH = 0.5
GUIDE_STRENGTH_2 = 2.5
IMAGE = 'example.png'
MODEL_NAME = 'ltx-2.3-22b-dev-fp8.safetensors'
MODEL_NAME_2 = 'gemma_3_12B_it_fp4_mixed.safetensors'
MODEL_NAME_3 = 'ltxv/ltx2/ltx-2.3-22b-distilled-lora-384-1.1.safetensors'
MODEL_NAME_4 = 'ltx-2.3-22b-ic-lora-motion-track-control-ref0.5.safetensors'
SCALE_METHOD = 'lanczos'
WIDGET_0 = ''


MODELS = {}

PUBLIC_INPUTS = {
    'model': InputSpec(node=ref('lowvramcheckpointloader'), field='ckpt_name', default=MODEL_NAME),
    'seed': InputSpec(node=ref('randomnoise'), field='noise_seed', default=DEFAULT_SEED),
    'prompt': InputSpec(node=ref('cliptextencode'), field='text', default=DEFAULT_PROMPT),
    'image': InputSpec(node=ref('loadimage'), field='image', default=IMAGE),
    'input_image': InputSpec(node=ref('loadimage'), field='image', default=IMAGE),
}

READY_METADATA = ReadyMetadata.build(
    capability='motion_track_control',
    inputs=PUBLIC_INPUTS,
    models=MODELS,
    requirements={'models': ['euler_ancestral_cfg_pp', 'ltx-2.3-22b-dev-fp8.safetensors', 'ltx-2.3-22b-ic-lora-motion-track-control-ref0.5.safetensors', 'ltxv/ltx2/ltx-2.3-22b-distilled-lora-384-1.1.safetensors'], 'custom_nodes': ['ComfyUI-KJNodes', 'ComfyUI-LTXVideo']},
    custom_node_packs={'ComfyUI-KJNodes': {'commit': 'b7646ad70a7daa7aeb919ca542274758d26ba2df', 'url': 'https://github.com/kijai/ComfyUI-KJNodes.git', 'class_schema_sha256': '1beaf129c8fa26175d89a28f9ca10d08b5ac27c8fc9bff920263fcbba17cb691', 'classes_used': ['GetImageSize'], 'pip_packages': ['matplotlib'], 'status': 'pinned'}, 'ComfyUI-LTXVideo': {'commit': '229437c6b65796d6a7a63ae34be2bd5ba31fa543', 'url': 'https://github.com/Lightricks/ComfyUI-LTXVideo.git', 'class_schema_sha256': '82e0b1f31509a969cf441c45e2517d0cd93f31b5390cc16f4a0ffa244421f39e', 'classes_used': ['EmptyLTXVLatentVideo', 'LTXAVTextEncoderLoader', 'LTXVAudioVAEDecode', 'LTXVConcatAVLatent', 'LTXVConditioning', 'LTXVCropGuides', 'LTXVEmptyLatentAudio', 'LTXVSeparateAVLatent'], 'pip_packages': [], 'status': 'pinned'}},
    approach='official IC-LoRA motion-track image anchor/control workflow',
    manual_promotion_rationale='Promoted during sprint 7 because the declared upstream source workflow is absent; preserve the materialized graph and curate public contracts manually.',
    discord_signal='Motion transfer, body/camera movement, and image anchors were recurring LTX channel themes.',
    smoke_resolution='256x256x5_frames',
    ltx_best_practices=['Use the official Lightricks workflows as runtime gates where possible.', 'Patch smoke runs to fp8/fp4 model assets, tiny frame counts, and low-VRAM loaders.', 'Bypass latent spatial upscalers in smoke runs until HiddenSwitch Comfy exposes model_mmap_residency for LatentUpscaleModelManageable.', 'Keep community audio, lip-sync, and long-form workflows as ready templates until their custom node packs and service credentials are declared.'],
    comfy_configuration={'reserve_vram': 12, 'cache_none': True, 'fp8_e4m3fn_text_enc': True},
    provenance={'source_workflow': 'workflow_corpus/custom_nodes/ltxvideo/lightricks_2_3/LTX-2.3_ICLoRA_Motion_Track_Distilled.json'},
)

def build() -> VibeWorkflow:
    """Build the workflow (auto-generated)."""
    with new_workflow(READY_METADATA, source_path=__file__) as wf:

        # Inputs
        loadimage = LoadImage(
            _id='2004',
            image=IMAGE,
            widget_0='example.png',
            _outputs=('IMAGE', 'MASK'),
        )
        wf.metadata.setdefault('id_map', {})['loadimage'] = loadimage.node.id

        lowvramcheckpointloader = LowVRAMCheckpointLoader(
            _id='3940',
            ckpt_name=MODEL_NAME,
            _outputs=('MODEL', 'CLIP', 'VAE'),
        )
        wf.metadata.setdefault('id_map', {})['lowvramcheckpointloader'] = lowvramcheckpointloader.node.id

        lowvramaudiovaeloader = LowVRAMAudioVAELoader(_id='4010', ckpt_name=MODEL_NAME)
        wf.metadata.setdefault('id_map', {})['lowvramaudiovaeloader'] = lowvramaudiovaeloader.node.id
        # Sampling
        ksamplerselect = KSamplerSelect(
            _id='4831',
            sampler_name='euler_ancestral_cfg_pp',
        )
        wf.metadata.setdefault('id_map', {})['ksamplerselect'] = ksamplerselect.node.id

        randomnoise = RandomNoise(
            _id='4832',
            noise_seed=DEFAULT_SEED,
            control_after_generate='fixed',
        )
        wf.metadata.setdefault('id_map', {})['randomnoise'] = randomnoise.node.id

        # Inputs
        primitivestring = raw_call(wf, 'PrimitiveString', '5022', value='')
        wf.metadata.setdefault('id_map', {})['primitivestring'] = primitivestring.node.id
        ltxavtextencoderloader = LTXAVTextEncoderLoader(
            _id='5023',
            text_encoder=MODEL_NAME_2,
            ckpt_name=MODEL_NAME,
            device='default',
            widget_0='gemma_3_12B_it_fp4_mixed.safetensors',
            widget_1='ltx-2.3-22b-dev-fp8.safetensors',
        )
        wf.metadata.setdefault('id_map', {})['ltxavtextencoderloader'] = ltxavtextencoderloader.node.id

        manualsigmas = ManualSigmas(
            _id='5025',
            sigmas='1.0, 0.99375, 0.9875, 0.98125, 0.975, 0.909375, 0.725, 0.421875, 0.0',
        )
        wf.metadata.setdefault('id_map', {})['manualsigmas'] = manualsigmas.node.id

        primitiveint = raw_call(wf, 'PrimitiveInt', '5044', value=5, widget_1='fixed')
        wf.metadata.setdefault('id_map', {})['primitiveint'] = primitiveint.node.id
        primitivefloat = raw_call(wf, 'PrimitiveFloat', '5045', value=8)
        wf.metadata.setdefault('id_map', {})['primitivefloat'] = primitivefloat.node.id
        # Conditioning
        cliptextencode = CLIPTextEncode(
            _id='2483',
            text=DEFAULT_PROMPT,
            clip=ltxavtextencoderloader,
        )
        wf.metadata.setdefault('id_map', {})['cliptextencode'] = cliptextencode.node.id

        cliptextencode_2 = CLIPTextEncode(
            _id='2612',
            text=DEFAULT_PROMPT_2,
            clip=ltxavtextencoderloader,
        )
        wf.metadata.setdefault('id_map', {})['cliptextencode_2'] = cliptextencode_2.node.id

        loraloadermodelonly = LoraLoaderModelOnly(
            _id='4922',
            lora_name=MODEL_NAME_3,
            strength_model=GUIDE_STRENGTH,
            model=lowvramcheckpointloader.out('MODEL'),
        )
        wf.metadata.setdefault('id_map', {})['loraloadermodelonly'] = loraloadermodelonly.node.id

        gemmaapitextencode = GemmaAPITextEncode(
            _id='5020',
            widget_0=WIDGET_0,
            widget_1='pc game, console game, video game, cartoon, childish, ugly',
            widget_2=False,
            widget_3=MODEL_NAME,
            api_key=primitivestring,
        )
        wf.metadata.setdefault('id_map', {})['gemmaapitextencode'] = gemmaapitextencode.node.id

        gemmaapitextencode_2 = GemmaAPITextEncode(
            _id='5021',
            widget_0=WIDGET_0,
            widget_1='',
            widget_2=MODEL_NAME,
            widget_3=MODEL_NAME,
            api_key=primitivestring,
        )
        wf.metadata.setdefault('id_map', {})['gemmaapitextencode_2'] = gemmaapitextencode_2.node.id

        resizeimagemasknode = ResizeImageMaskNode(
            _id='5049',
            resize_type='scale shorter dimension',
            scale_method=SCALE_METHOD,
            input=loadimage.out('IMAGE'),
        )
        wf.metadata.setdefault('id_map', {})['resizeimagemasknode'] = resizeimagemasknode.node.id

        ltxfloattoint = LTXFloatToInt(_id='5059', rounding=0, a=primitivefloat)
        wf.metadata.setdefault('id_map', {})['ltxfloattoint'] = ltxfloattoint.node.id
        ltxvconditioning = LTXVConditioning(
            _id='1241',
            widget_0=8,
            frame_rate=primitivefloat,
            negative=cliptextencode_2,
            positive=cliptextencode,
            _outputs=('POSITIVE', 'NEGATIVE'),
        )
        wf.metadata.setdefault('id_map', {})['ltxvconditioning'] = ltxvconditioning.node.id

        ltxvemptylatentaudio = LTXVEmptyLatentAudio(
            _id='3980',
            widget_0=5,
            widget_1=8,
            frames_number=primitiveint,
            frame_rate=ltxfloattoint,
            audio_vae=lowvramaudiovaeloader,
        )
        wf.metadata.setdefault('id_map', {})['ltxvemptylatentaudio'] = ltxvemptylatentaudio.node.id

        ltxicloraloadermodelonly = LTXICLoRALoaderModelOnly(
            _id='5011',
            lora_name=MODEL_NAME_4,
            widget_0='ltx-2.3-22b-ic-lora-motion-track-control-ref0.5.safetensors',
            model=loraloadermodelonly,
            _outputs=('MODEL', 'LATENT_DOWNSCALE_FACTOR'),
        )
        wf.metadata.setdefault('id_map', {})['ltxicloraloadermodelonly'] = ltxicloraloadermodelonly.node.id

        simplemath_ = raw_call(wf, 'SimpleMath+', '5056',
            _outputs=('INT', 'FLOAT'),
            widget_0='a*32',
            a=ltxicloraloadermodelonly.out('LATENT_DOWNSCALE_FACTOR'),
        )
        wf.metadata.setdefault('id_map', {})['simplemath_'] = simplemath_.node.id

        resizeimagemasknode_2 = ResizeImageMaskNode(
            _id='5053',
            resize_type='scale to multiple',
            scale_method=SCALE_METHOD,
            input=resizeimagemasknode,
            **{'resize_type.multiple': simplemath_.out('INT')},
        )
        wf.metadata.setdefault('id_map', {})['resizeimagemasknode_2'] = resizeimagemasknode_2.node.id

        ltxvsparsetrackeditor = raw_call(wf, 'LTXVSparseTrackEditor', '5040',
            widget_0='[[{"x":385.0759251206301,"y":238.92165891412267},{"x":226.6706827038015,"y":321.895716789677},{"x":118.7556948262006,"y":334.34620347590675},{"x":8.857468951125458,"y":294.56719637193584}],[{"x":550.4183052326947,"y":246.43019177413228},{"x":530.2019095759371,"y":493.9392986305124}]]',
            widget_1='[[{"x":385,"y":239},{"x":383,"y":240},{"x":381,"y":241},{"x":378,"y":243},{"x":375,"y":244},{"x":373,"y":246},{"x":369,"y":248},{"x":366,"y":249},{"x":363,"y":251},{"x":359,"y":253},{"x":355,"y":255},{"x":352,"y":258},{"x":348,"y":260},{"x":344,"y":262},{"x":339,"y":265},{"x":335,"y":267},{"x":331,"y":270},{"x":326,"y":272},{"x":322,"y":275},{"x":317,"y":277},{"x":313,"y":280},{"x":308,"y":282},{"x":303,"y":285},{"x":299,"y":287},{"x":294,"y":290},{"x":289,"y":292},{"x":285,"y":295},{"x":280,"y":297},{"x":275,"y":300},{"x":271,"y":302},{"x":266,"y":304},{"x":262,"y":306},{"x":258,"y":308},{"x":253,"y":311},{"x":249,"y":312},{"x":245,"y":314},{"x":241,"y":316},{"x":237,"y":318},{"x":234,"y":319},{"x":230,"y":321},{"x":227,"y":322},{"x":223,"y":323},{"x":220,"y":324},{"x":217,"y":325},{"x":214,"y":326},{"x":211,"y":327},{"x":208,"y":328},{"x":205,"y":329},{"x":202,"y":330},{"x":199,"y":330},{"x":196,"y":331},{"x":193,"y":332},{"x":191,"y":332},{"x":188,"y":333},{"x":185,"y":334},{"x":183,"y":334},{"x":180,"y":334},{"x":177,"y":335},{"x":175,"y":335},{"x":172,"y":336},{"x":170,"y":336},{"x":167,"y":336},{"x":165,"y":336},{"x":162,"y":336},{"x":160,"y":337},{"x":157,"y":337},{"x":155,"y":337},{"x":152,"y":337},{"x":150,"y":337},{"x":147,"y":337},{"x":145,"y":337},{"x":142,"y":336},{"x":140,"y":336},{"x":137,"y":336},{"x":135,"y":336},{"x":132,"y":336},{"x":129,"y":336},{"x":127,"y":335},{"x":124,"y":335},{"x":121,"y":335},{"x":119,"y":334},{"x":116,"y":334},{"x":113,"y":333},{"x":110,"y":333},{"x":107,"y":332},{"x":104,"y":332},{"x":101,"y":331},{"x":98,"y":330},{"x":95,"y":329},{"x":92,"y":328},{"x":89,"y":327},{"x":86,"y":326},{"x":82,"y":325},{"x":79,"y":324},{"x":76,"y":323},{"x":73,"y":322},{"x":70,"y":320},{"x":66,"y":319},{"x":63,"y":318},{"x":60,"y":317},{"x":57,"y":315},{"x":54,"y":314},{"x":51,"y":313},{"x":48,"y":311},{"x":45,"y":310},{"x":42,"y":309},{"x":39,"y":308},{"x":37,"y":306},{"x":34,"y":305},{"x":31,"y":304},{"x":29,"y":303},{"x":26,"y":302},{"x":24,"y":301},{"x":22,"y":300},{"x":19,"y":299},{"x":17,"y":298},{"x":15,"y":297},{"x":14,"y":296},{"x":12,"y":296},{"x":10,"y":295},{"x":9,"y":295}],[{"x":550,"y":246},{"x":550,"y":248},{"x":550,"y":251},{"x":550,"y":253},{"x":550,"y":255},{"x":550,"y":257},{"x":549,"y":259},{"x":549,"y":261},{"x":549,"y":263},{"x":549,"y":265},{"x":549,"y":267},{"x":549,"y":269},{"x":548,"y":271},{"x":548,"y":273},{"x":548,"y":275},{"x":548,"y":277},{"x":548,"y":279},{"x":548,"y":281},{"x":547,"y":284},{"x":547,"y":286},{"x":547,"y":288},{"x":547,"y":290},{"x":547,"y":292},{"x":547,"y":294},{"x":546,"y":296},{"x":546,"y":298},{"x":546,"y":300},{"x":546,"y":302},{"x":546,"y":304},{"x":546,"y":306},{"x":545,"y":308},{"x":545,"y":310},{"x":545,"y":312},{"x":545,"y":314},{"x":545,"y":317},{"x":545,"y":319},{"x":544,"y":321},{"x":544,"y":323},{"x":544,"y":325},{"x":544,"y":327},{"x":544,"y":329},{"x":544,"y":331},{"x":543,"y":333},{"x":543,"y":335},{"x":543,"y":337},{"x":543,"y":339},{"x":543,"y":341},{"x":543,"y":343},{"x":542,"y":345},{"x":542,"y":347},{"x":542,"y":350},{"x":542,"y":352},{"x":542,"y":354},{"x":541,"y":356},{"x":541,"y":358},{"x":541,"y":360},{"x":541,"y":362},{"x":541,"y":364},{"x":541,"y":366},{"x":540,"y":368},{"x":540,"y":370},{"x":540,"y":372},{"x":540,"y":374},{"x":540,"y":376},{"x":540,"y":378},{"x":539,"y":380},{"x":539,"y":383},{"x":539,"y":385},{"x":539,"y":387},{"x":539,"y":389},{"x":539,"y":391},{"x":538,"y":393},{"x":538,"y":395},{"x":538,"y":397},{"x":538,"y":399},{"x":538,"y":401},{"x":538,"y":403},{"x":537,"y":405},{"x":537,"y":407},{"x":537,"y":409},{"x":537,"y":411},{"x":537,"y":413},{"x":537,"y":416},{"x":536,"y":418},{"x":536,"y":420},{"x":536,"y":422},{"x":536,"y":424},{"x":536,"y":426},{"x":536,"y":428},{"x":535,"y":430},{"x":535,"y":432},{"x":535,"y":434},{"x":535,"y":436},{"x":535,"y":438},{"x":535,"y":440},{"x":534,"y":442},{"x":534,"y":444},{"x":534,"y":447},{"x":534,"y":449},{"x":534,"y":451},{"x":534,"y":453},{"x":533,"y":455},{"x":533,"y":457},{"x":533,"y":459},{"x":533,"y":461},{"x":533,"y":463},{"x":533,"y":465},{"x":532,"y":467},{"x":532,"y":469},{"x":532,"y":471},{"x":532,"y":473},{"x":532,"y":475},{"x":532,"y":477},{"x":531,"y":480},{"x":531,"y":482},{"x":531,"y":484},{"x":531,"y":486},{"x":531,"y":488},{"x":531,"y":490},{"x":530,"y":492},{"x":530,"y":494}]]',
            widget_2=121,
            widget_3='',
            image=resizeimagemasknode_2,
            points_to_sample=primitiveint,
        )
        wf.metadata.setdefault('id_map', {})['ltxvsparsetrackeditor'] = ltxvsparsetrackeditor.node.id

        getimagesize = GetImageSize(
            _id='5050',
            image=resizeimagemasknode_2,
            _outputs=('WIDTH', 'HEIGHT', 'BATCH_SIZE'),
        )
        wf.metadata.setdefault('id_map', {})['getimagesize'] = getimagesize.node.id

        # Sampling
        emptyltxvlatentvideo = EmptyLTXVLatentVideo(
            _id='3059',
            widget_0=256,
            widget_1=256,
            widget_2=5,
            width=getimagesize.out('WIDTH'),
            height=getimagesize.out('HEIGHT'),
            length=primitiveint,
        )
        wf.metadata.setdefault('id_map', {})['emptyltxvlatentvideo'] = emptyltxvlatentvideo.node.id

        ltxvdrawtracks = raw_call(wf, 'LTXVDrawTracks', '5034',
            widget_0=WIDGET_0,
            widget_1=512,
            widget_2=512,
            height=getimagesize.out('HEIGHT'),
            tracks=ltxvsparsetrackeditor,
            width=getimagesize.out('WIDTH'),
        )
        wf.metadata.setdefault('id_map', {})['ltxvdrawtracks'] = ltxvdrawtracks.node.id

        ltxvimgtovideoconditiononly = LTXVImgToVideoConditionOnly(
            _id='3159',
            image=resizeimagemasknode_2,
            latent=emptyltxvlatentvideo,
            vae=lowvramcheckpointloader.out('VAE'),
        )
        wf.metadata.setdefault('id_map', {})['ltxvimgtovideoconditiononly'] = ltxvimgtovideoconditiononly.node.id

        createvideo_2 = CreateVideo(
            _id='5051',
            widget_0=8,
            fps=primitivefloat,
            images=ltxvdrawtracks,
        )
        wf.metadata.setdefault('id_map', {})['createvideo_2'] = createvideo_2.node.id

        ltxaddvideoicloraguide = LTXAddVideoICLoRAGuide(
            _id='5012',
            crop=1,
            use_tiled_encode='disabled',
            tile_size=128,
            tile_overlap=32,
            image=ltxvdrawtracks,
            latent=ltxvimgtovideoconditiononly,
            latent_downscale_factor=ltxicloraloadermodelonly.out('LATENT_DOWNSCALE_FACTOR'),
            negative=ltxvconditioning.out('NEGATIVE'),
            positive=ltxvconditioning.out('POSITIVE'),
            vae=lowvramcheckpointloader.out('VAE'),
            _outputs=('POSITIVE', 'NEGATIVE', 'LATENT'),
        )
        wf.metadata.setdefault('id_map', {})['ltxaddvideoicloraguide'] = ltxaddvideoicloraguide.node.id

        # Outputs
        savevideo_2 = SaveVideo(
            _id='5052',
            filename_prefix='output',
            video=createvideo_2,
        )
        wf.metadata.setdefault('id_map', {})['savevideo_2'] = savevideo_2.node.id

        ltxvconcatavlatent = LTXVConcatAVLatent(
            _id='4528',
            audio_latent=ltxvemptylatentaudio,
            video_latent=ltxaddvideoicloraguide.out('LATENT'),
        )
        wf.metadata.setdefault('id_map', {})['ltxvconcatavlatent'] = ltxvconcatavlatent.node.id

        # Conditioning
        cfgguider = CFGGuider(
            _id='4828',
            cfg=GUIDE_STRENGTH_2,
            model=ltxicloraloadermodelonly.out('MODEL'),
            negative=ltxaddvideoicloraguide.out('NEGATIVE'),
            positive=ltxaddvideoicloraguide.out('POSITIVE'),
        )
        wf.metadata.setdefault('id_map', {})['cfgguider'] = cfgguider.node.id

        # Sampling
        samplercustomadvanced = SamplerCustomAdvanced(
            _id='4829',
            guider=cfgguider,
            latent_image=ltxvconcatavlatent,
            noise=randomnoise,
            sampler=ksamplerselect,
            sigmas=manualsigmas,
            _outputs=('OUTPUT', 'DENOISED_OUTPUT'),
        )
        wf.metadata.setdefault('id_map', {})['samplercustomadvanced'] = samplercustomadvanced.node.id

        ltxvseparateavlatent = LTXVSeparateAVLatent(
            _id='4845',
            av_latent=samplercustomadvanced.out('OUTPUT'),
            _outputs=('VIDEO_LATENT', 'AUDIO_LATENT'),
        )
        wf.metadata.setdefault('id_map', {})['ltxvseparateavlatent'] = ltxvseparateavlatent.node.id

        ltxvaudiovaedecode = LTXVAudioVAEDecode(
            _id='4848',
            audio_vae=lowvramaudiovaeloader,
            samples=ltxvseparateavlatent.out('AUDIO_LATENT'),
        )
        wf.metadata.setdefault('id_map', {})['ltxvaudiovaedecode'] = ltxvaudiovaedecode.node.id

        ltxvcropguides = LTXVCropGuides(
            _id='5013',
            latent=ltxvseparateavlatent.out('VIDEO_LATENT'),
            negative=ltxaddvideoicloraguide.out('NEGATIVE'),
            positive=ltxaddvideoicloraguide.out('POSITIVE'),
            _outputs=('POSITIVE', 'NEGATIVE', 'LATENT'),
        )
        wf.metadata.setdefault('id_map', {})['ltxvcropguides'] = ltxvcropguides.node.id

        ltxvtiledvaedecode = LTXVTiledVAEDecode(
            _id='5058',
            horizontal_tiles=2,
            vertical_tiles=2,
            overlap=6,
            latents=ltxvcropguides.out('LATENT'),
            vae=lowvramcheckpointloader.out('VAE'),
        )
        wf.metadata.setdefault('id_map', {})['ltxvtiledvaedecode'] = ltxvtiledvaedecode.node.id

        createvideo = CreateVideo(
            _id='4849',
            widget_0=8,
            fps=primitivefloat,
            audio=ltxvaudiovaedecode,
            images=ltxvtiledvaedecode,
        )
        wf.metadata.setdefault('id_map', {})['createvideo'] = createvideo.node.id

        # Outputs
        savevideo = SaveVideo(_id='4852', filename_prefix='output', video=createvideo)
        wf.metadata.setdefault('id_map', {})['savevideo'] = savevideo.node.id

        return wf.finalize(PUBLIC_INPUTS, output_node=savevideo, output_type='SaveVideo', name='video', artifact_kind='video', mime_type='video/mp4', expected_cardinality='one', filename_prefix='output')

