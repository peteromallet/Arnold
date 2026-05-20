# vibecomfy: generated - converted by tools/convert_ready_templates.py
# Edits will be overwritten on regeneration. Put the manual opt-out
# marker on the first line if hand-editing is required.
"""Auto-generated ready_template - see tools/convert_ready_templates.py."""
from __future__ import annotations

from vibecomfy.templates import InputSpec, ModelAsset, ReadyMetadata, finalize, new_workflow, node as raw_call, ref
from vibecomfy.nodes.core import CFGGuider, CLIPTextEncode, CreateVideo, EmptyLTXVLatentVideo, GetImageSize, GetVideoComponents, KSamplerSelect, LTXAVTextEncoderLoader, LTXVConditioning, LTXVCropGuides, LoadVideo, ManualSigmas, RandomNoise, ResizeImageMaskNode, SamplerCustomAdvanced, SaveVideo, VAEDecodeTiled
from vibecomfy.nodes.ltxvideo import GemmaAPITextEncode, LTXAddVideoICLoRAGuide, LTXICLoRALoaderModelOnly, LTXVHDRDecodePostprocess, LowVRAMCheckpointLoader


DEFAULT_FPS = 8
DEFAULT_PROMPT = 'pc game, console game, video game, ugly, still, static, slow'
DEFAULT_SEED = 42
GUIDE_STRENGTH = 0.5
GUIDE_STRENGTH_2 = 2.5
MODEL_NAME = 'ltx-2.3-22b-dev-fp8.safetensors'
MODEL_NAME_2 = 'gemma_3_12B_it_fp4_mixed.safetensors'
MODEL_NAME_3 = 'ltx-2.3-22b-distilled-lora-384-1.1.safetensors'
MODEL_NAME_4 = 'ltx-2.3-22b-ic-lora-hdr-0.9.safetensors'
WIDGET_0 = ''


MODELS = {}

PUBLIC_INPUTS = {
    'model': InputSpec(node=ref('lowvramcheckpointloader'), field='ckpt_name', default=MODEL_NAME),
    'seed': InputSpec(node=ref('randomnoise'), field='noise_seed', default=DEFAULT_SEED),
    'prompt': InputSpec(node=ref('cliptextencode'), field='text', default='HDR footage'),
    'fps': InputSpec(node=ref('createvideo'), field='fps', default=DEFAULT_FPS),
}

READY_METADATA = ReadyMetadata.build(
    capability='video_guided_hdr',
    inputs=PUBLIC_INPUTS,
    models=MODELS,
    requirements={'models': ['euler_ancestral', 'ltx-2.3-22b-dev-fp8.safetensors', 'ltx-2.3-22b-distilled-lora-384-1.1.safetensors', 'ltx-2.3-22b-ic-lora-hdr-0.9.safetensors'], 'custom_nodes': ['ComfyUI-KJNodes', 'ComfyUI-LTXVideo']},
    custom_node_packs={'ComfyUI-KJNodes': {'commit': 'b7646ad70a7daa7aeb919ca542274758d26ba2df', 'url': 'https://github.com/kijai/ComfyUI-KJNodes.git', 'class_schema_sha256': '1beaf129c8fa26175d89a28f9ca10d08b5ac27c8fc9bff920263fcbba17cb691', 'classes_used': ['GetImageSize'], 'pip_packages': ['matplotlib'], 'status': 'pinned'}, 'ComfyUI-LTXVideo': {'commit': '229437c6b65796d6a7a63ae34be2bd5ba31fa543', 'url': 'https://github.com/Lightricks/ComfyUI-LTXVideo.git', 'class_schema_sha256': '82e0b1f31509a969cf441c45e2517d0cd93f31b5390cc16f4a0ffa244421f39e', 'classes_used': ['EmptyLTXVLatentVideo', 'LTXAVTextEncoderLoader', 'LTXVConditioning', 'LTXVCropGuides'], 'pip_packages': [], 'status': 'pinned'}},
    approach='official IC-LoRA HDR video guide',
    smoke_resolution='256x256x5_frames',
    manual_promotion_rationale='Promoted during sprint 7 because the declared upstream source workflow is absent; preserve the materialized graph and curate public contracts manually.',
    discord_signal='IC-LoRA, relight/HDR, and guide-video workflows were recurring LTX channel themes.',
    ltx_best_practices=['Use the official Lightricks workflows as runtime gates where possible.', 'Patch smoke runs to fp8/fp4 model assets, tiny frame counts, and low-VRAM loaders.', 'Bypass latent spatial upscalers in smoke runs until HiddenSwitch Comfy exposes model_mmap_residency for LatentUpscaleModelManageable.', 'Keep community audio, lip-sync, and long-form workflows as ready templates until their custom node packs and service credentials are declared.'],
    comfy_configuration={'reserve_vram': 12, 'cache_none': True, 'fp8_e4m3fn_text_enc': True},
    provenance={'source_workflow': 'workflow_corpus/custom_nodes/ltxvideo/lightricks_2_3/LTX-2.3_ICLoRA_HDR_Distilled.json'},
)

def build() -> VibeWorkflow:
    """Build the workflow (auto-generated)."""
    with new_workflow(READY_METADATA, source_path=__file__) as wf:

        lowvramcheckpointloader = LowVRAMCheckpointLoader(
            _id='3940',
            ckpt_name=MODEL_NAME,
            _outputs=('MODEL', 'CLIP', 'VAE'),
        )
        wf.metadata.setdefault('id_map', {})['lowvramcheckpointloader'] = lowvramcheckpointloader.node.id

        # Sampling
        ksamplerselect = KSamplerSelect(_id='4831', sampler_name='euler_ancestral')
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
        )
        wf.metadata.setdefault('id_map', {})['ltxavtextencoderloader'] = ltxavtextencoderloader.node.id

        manualsigmas = ManualSigmas(
            _id='5025',
            sigmas='1.0, 0.99375, 0.9875, 0.98125, 0.975, 0.909375, 0.725, 0.421875, 0.0',
        )
        wf.metadata.setdefault('id_map', {})['manualsigmas'] = manualsigmas.node.id

        loadvideo = LoadVideo(
            _id='5106',
            file='ltx_smoke_guide.mp4',
            video='ltx_smoke_guide.mp4',
        )
        wf.metadata.setdefault('id_map', {})['loadvideo'] = loadvideo.node.id

        # Conditioning
        cliptextencode = CLIPTextEncode(
            _id='2483',
            text='HDR footage',
            clip=ltxavtextencoderloader,
        )
        wf.metadata.setdefault('id_map', {})['cliptextencode'] = cliptextencode.node.id

        cliptextencode_2 = CLIPTextEncode(
            _id='2612',
            text=DEFAULT_PROMPT,
            clip=ltxavtextencoderloader,
        )
        wf.metadata.setdefault('id_map', {})['cliptextencode_2'] = cliptextencode_2.node.id

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

        getvideocomponents = GetVideoComponents(
            _id='5105',
            video=loadvideo,
            _outputs=('IMAGES', 'AUDIO', 'FPS'),
        )
        wf.metadata.setdefault('id_map', {})['getvideocomponents'] = getvideocomponents.node.id

        ltxicloraloadermodelonly_2 = LTXICLoRALoaderModelOnly(
            _id='5125',
            lora_name=MODEL_NAME_3,
            strength_model=GUIDE_STRENGTH,
            model=lowvramcheckpointloader.out('MODEL'),
            _outputs=('MODEL', 'LATENT_DOWNSCALE_FACTOR'),
        )
        wf.metadata.setdefault('id_map', {})['ltxicloraloadermodelonly_2'] = ltxicloraloadermodelonly_2.node.id

        ltxvconditioning = LTXVConditioning(
            _id='1241',
            frame_rate=getvideocomponents.out('FPS'),
            negative=cliptextencode_2,
            positive=cliptextencode,
            _outputs=('POSITIVE', 'NEGATIVE'),
        )
        wf.metadata.setdefault('id_map', {})['ltxvconditioning'] = ltxvconditioning.node.id

        ltxicloraloadermodelonly = LTXICLoRALoaderModelOnly(
            _id='5011',
            lora_name=MODEL_NAME_4,
            model=ltxicloraloadermodelonly_2.out('MODEL'),
            _outputs=('MODEL', 'LATENT_DOWNSCALE_FACTOR'),
        )
        wf.metadata.setdefault('id_map', {})['ltxicloraloadermodelonly'] = ltxicloraloadermodelonly.node.id

        simplemath_ = raw_call(wf, 'SimpleMath+', '5111',
            _outputs=('INT', 'FLOAT'),
            widget_0='a*32',
            a=ltxicloraloadermodelonly.out('LATENT_DOWNSCALE_FACTOR'),
        )
        wf.metadata.setdefault('id_map', {})['simplemath_'] = simplemath_.node.id

        resizeimagemasknode = ResizeImageMaskNode(
            _id='5112',
            resize_type='scale to multiple',
            scale_method='lanczos',
            input=getvideocomponents.out('IMAGES'),
            **{'resize_type.multiple': simplemath_.out('INT')},
        )
        wf.metadata.setdefault('id_map', {})['resizeimagemasknode'] = resizeimagemasknode.node.id

        getimagesize = GetImageSize(
            _id='5029',
            image=resizeimagemasknode,
            _outputs=('WIDTH', 'HEIGHT', 'BATCH_SIZE'),
        )
        wf.metadata.setdefault('id_map', {})['getimagesize'] = getimagesize.node.id

        # Sampling
        emptyltxvlatentvideo = EmptyLTXVLatentVideo(
            _id='3059',
            width=getimagesize.out('WIDTH'),
            height=getimagesize.out('HEIGHT'),
            length=getimagesize.out('BATCH_SIZE'),
        )
        wf.metadata.setdefault('id_map', {})['emptyltxvlatentvideo'] = emptyltxvlatentvideo.node.id

        ltxaddvideoicloraguide = LTXAddVideoICLoRAGuide(
            _id='5012',
            crop=1,
            use_tiled_encode='disabled',
            tile_size=128,
            tile_overlap=32,
            image=resizeimagemasknode,
            latent=emptyltxvlatentvideo,
            negative=ltxvconditioning.out('NEGATIVE'),
            positive=ltxvconditioning.out('POSITIVE'),
            vae=lowvramcheckpointloader.out('VAE'),
            _outputs=('POSITIVE', 'NEGATIVE', 'LATENT'),
        )
        wf.metadata.setdefault('id_map', {})['ltxaddvideoicloraguide'] = ltxaddvideoicloraguide.node.id

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
            latent_image=ltxaddvideoicloraguide.out('LATENT'),
            noise=randomnoise,
            sampler=ksamplerselect,
            sigmas=manualsigmas,
            _outputs=('OUTPUT', 'DENOISED_OUTPUT'),
        )
        wf.metadata.setdefault('id_map', {})['samplercustomadvanced'] = samplercustomadvanced.node.id

        ltxvcropguides = LTXVCropGuides(
            _id='5013',
            latent=samplercustomadvanced.out('OUTPUT'),
            negative=ltxaddvideoicloraguide.out('NEGATIVE'),
            positive=ltxaddvideoicloraguide.out('POSITIVE'),
            _outputs=('POSITIVE', 'NEGATIVE', 'LATENT'),
        )
        wf.metadata.setdefault('id_map', {})['ltxvcropguides'] = ltxvcropguides.node.id

        # Decode
        vaedecodetiled = VAEDecodeTiled(
            _id='4851',
            tile_size=768,
            overlap=256,
            temporal_size=8,
            temporal_overlap=4,
            samples=ltxvcropguides.out('LATENT'),
            vae=lowvramcheckpointloader.out('VAE'),
        )
        wf.metadata.setdefault('id_map', {})['vaedecodetiled'] = vaedecodetiled.node.id

        ltxvhdrdecodepostprocess = LTXVHDRDecodePostprocess(
            _id='5114',
            widget_0=7.1,
            widget_1=True,
            widget_2='output/hdr_exr3',
            widget_3='frame',
            widget_4=True,
            image=vaedecodetiled,
            _outputs=('TONEMAPPED', 'HDR_LINEAR'),
        )
        wf.metadata.setdefault('id_map', {})['ltxvhdrdecodepostprocess'] = ltxvhdrdecodepostprocess.node.id

        createvideo = CreateVideo(
            _id='5108',
            fps=DEFAULT_FPS,
            widget_0=8,
            audio=getvideocomponents.out('AUDIO'),
            images=ltxvhdrdecodepostprocess.out('HDR_LINEAR'),
        )
        wf.metadata.setdefault('id_map', {})['createvideo'] = createvideo.node.id

        # Outputs
        savevideo = SaveVideo(_id='5109', filename_prefix='output', video=createvideo)
        wf.metadata.setdefault('id_map', {})['savevideo'] = savevideo.node.id

        return wf.finalize(PUBLIC_INPUTS, output_type='SaveVideo', name='video', artifact_kind='video', mime_type='video/mp4', expected_cardinality='one', filename_prefix='output')

