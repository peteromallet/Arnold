# vibecomfy: generated - converted by tools/convert_ready_templates.py
# Edits will be overwritten on regeneration. Put the manual opt-out
# marker on the first line if hand-editing is required.
"""Auto-generated ready_template - see tools/convert_ready_templates.py."""
from __future__ import annotations

from vibecomfy.templates import InputSpec, ModelAsset, ReadyMetadata, finalize, new_workflow, node as raw_call, ref
from vibecomfy.nodes.core import CFGGuider, CLIPTextEncode, CreateVideo, EmptyLTXVLatentVideo, KSamplerSelect, LTXAVTextEncoderLoader, LTXVAudioVAEDecode, LTXVConcatAVLatent, LTXVConditioning, LTXVEmptyLatentAudio, LTXVPreprocess, LTXVSeparateAVLatent, LoadImage, LoraLoaderModelOnly, ManualSigmas, RandomNoise, ResizeImageMaskNode, SamplerCustomAdvanced, SaveVideo
from vibecomfy.nodes.ltxvideo import GemmaAPITextEncode, LTXFloatToInt, LTXVImgToVideoConditionOnly, LTXVTiledVAEDecode, LowVRAMAudioVAELoader, LowVRAMCheckpointLoader


CONTROL_AFTER_GENERATE = 'fixed'
DEFAULT_FPS = 8
DEFAULT_FRAMES = 5
DEFAULT_PROMPT = 'A traditional Japanese tea ceremony takes place in a tatami room as a host carefully prepares matcha. Soft traditional koto music plays in the background, adding to the serene atmosphere. The bamboo whisk taps rhythmically against the ceramic bowl while water simmers in an iron kettle. Guests kneel in formal seiza position, watching in respectful silence. The host bows and presents the tea bowl, turning it precisely before offering it to the first guest with soft-spoken words.'
DEFAULT_PROMPT_2 = 'pc game, console game, video game, cartoon, childish, ugly'
DEFAULT_SEED = 43
DEFAULT_SEED_2 = 42
GUIDE_STRENGTH = 0.5
GUIDE_STRENGTH_2 = 2.5
IMAGE = 'example.png'
MODEL_NAME = 'ltx-2.3-22b-dev-fp8.safetensors'
MODEL_NAME_2 = 'gemma_3_12B_it_fp4_mixed.safetensors'
MODEL_NAME_3 = 'ltxv/ltx2/ltx-2.3-22b-distilled-lora-384-1.1.safetensors'
WIDGET_0 = ''


MODELS = {}

PUBLIC_INPUTS = {
    'model': InputSpec(node=ref('lowvramcheckpointloader'), field='ckpt_name', default=MODEL_NAME),
    'seed': InputSpec(node=ref('randomnoise'), field='noise_seed', default=DEFAULT_SEED),
    'prompt': InputSpec(node=ref('cliptextencode'), field='text', default=DEFAULT_PROMPT),
    'image': InputSpec(node=ref('loadimage'), field='image', default=IMAGE),
    'input_image': InputSpec(node=ref('loadimage'), field='image', default=IMAGE),
    'width': InputSpec(node=ref('emptyltxvlatentvideo'), field='width', default=256),
    'height': InputSpec(node=ref('emptyltxvlatentvideo'), field='height', default=256),
}

READY_METADATA = ReadyMetadata.build(
    capability='text_or_image_to_video_upscale',
    inputs=PUBLIC_INPUTS,
    models=MODELS,
    requirements={'models': ['euler_ancestral_cfg_pp', 'euler_cfg_pp', 'ltx-2.3-22b-dev-fp8.safetensors', 'ltxv/ltx2/ltx-2.3-22b-distilled-lora-384-1.1.safetensors'], 'custom_nodes': ['ComfyUI-KJNodes', 'ComfyUI-LTXVideo']},
    custom_node_packs={'ComfyUI-LTXVideo': {'commit': '229437c6b65796d6a7a63ae34be2bd5ba31fa543', 'url': 'https://github.com/Lightricks/ComfyUI-LTXVideo.git', 'class_schema_sha256': '82e0b1f31509a969cf441c45e2517d0cd93f31b5390cc16f4a0ffa244421f39e', 'classes_used': ['EmptyLTXVLatentVideo', 'LTXAVTextEncoderLoader', 'LTXVAudioVAEDecode', 'LTXVConcatAVLatent', 'LTXVConditioning', 'LTXVEmptyLatentAudio', 'LTXVPreprocess', 'LTXVSeparateAVLatent'], 'pip_packages': [], 'status': 'pinned'}},
    approach='official two-stage low-VRAM T2V/I2V with latent spatial upscaler',
    manual_promotion_rationale='Promoted during sprint 7 because the declared upstream source workflow is absent; preserve the materialized graph and curate public contracts manually.',
    discord_signal='Longer clips and upscale passes were recurring LTX channel themes.',
    smoke_resolution='256x256x5_frames',
    ltx_best_practices=['Use the official Lightricks workflows as runtime gates where possible.', 'Patch smoke runs to fp8/fp4 model assets, tiny frame counts, and low-VRAM loaders.', 'Bypass latent spatial upscalers in smoke runs until HiddenSwitch Comfy exposes model_mmap_residency for LatentUpscaleModelManageable.', 'Keep community audio, lip-sync, and long-form workflows as ready templates until their custom node packs and service credentials are declared.'],
    comfy_configuration={'reserve_vram': 12, 'cache_none': True, 'fp8_e4m3fn_text_enc': True},
    provenance={'source_workflow': 'workflow_corpus/custom_nodes/ltxvideo/lightricks_2_3/LTX-2.3_T2V_I2V_Two_Stage_Distilled.json'},
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
            control_after_generate=CONTROL_AFTER_GENERATE,
        )
        wf.metadata.setdefault('id_map', {})['randomnoise'] = randomnoise.node.id

        randomnoise_2 = RandomNoise(
            _id='4967',
            noise_seed=DEFAULT_SEED_2,
            control_after_generate=CONTROL_AFTER_GENERATE,
        )
        wf.metadata.setdefault('id_map', {})['randomnoise_2'] = randomnoise_2.node.id

        ksamplerselect_2 = KSamplerSelect(_id='4976', sampler_name='euler_cfg_pp')
        wf.metadata.setdefault('id_map', {})['ksamplerselect_2'] = ksamplerselect_2.node.id
        # Inputs
        primitivestring = raw_call(wf, 'PrimitiveString', '4979', value='')
        wf.metadata.setdefault('id_map', {})['primitivestring'] = primitivestring.node.id
        ltxavtextencoderloader = LTXAVTextEncoderLoader(
            _id='4982',
            text_encoder=MODEL_NAME_2,
            ckpt_name=MODEL_NAME,
            device='default',
            widget_0='gemma_3_12B_it_fp4_mixed.safetensors',
            widget_1='ltx-2.3-22b-dev-fp8.safetensors',
        )
        wf.metadata.setdefault('id_map', {})['ltxavtextencoderloader'] = ltxavtextencoderloader.node.id

        manualsigmas = ManualSigmas(
            _id='4984',
            sigmas='1.0, 0.99375, 0.9875, 0.98125, 0.975, 0.909375, 0.725, 0.421875, 0.0',
        )
        wf.metadata.setdefault('id_map', {})['manualsigmas'] = manualsigmas.node.id

        manualsigmas_2 = ManualSigmas(_id='4985', sigmas='0.85, 0.7250, 0.4219, 0.0')
        wf.metadata.setdefault('id_map', {})['manualsigmas_2'] = manualsigmas_2.node.id
        primitiveboolean = raw_call(wf, 'PrimitiveBoolean', '4987', value=True)
        wf.metadata.setdefault('id_map', {})['primitiveboolean'] = primitiveboolean.node.id
        primitiveint = raw_call(wf, 'PrimitiveInt', '4988', value=5, widget_1='fixed')
        wf.metadata.setdefault('id_map', {})['primitiveint'] = primitiveint.node.id
        primitivefloat = raw_call(wf, 'PrimitiveFloat', '4989', value=8)
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

        # Sampling
        emptyltxvlatentvideo = EmptyLTXVLatentVideo(
            _id='3059',
            width=256,
            height=256,
            widget_0=256,
            widget_1=256,
            widget_2=5,
            length=primitiveint,
        )
        wf.metadata.setdefault('id_map', {})['emptyltxvlatentvideo'] = emptyltxvlatentvideo.node.id

        loraloadermodelonly = LoraLoaderModelOnly(
            _id='4922',
            lora_name=MODEL_NAME_3,
            strength_model=GUIDE_STRENGTH,
            model=lowvramcheckpointloader.out('MODEL'),
        )
        wf.metadata.setdefault('id_map', {})['loraloadermodelonly'] = loraloadermodelonly.node.id

        gemmaapitextencode = GemmaAPITextEncode(
            _id='4980',
            widget_0=WIDGET_0,
            widget_1='',
            widget_2=MODEL_NAME,
            widget_3=MODEL_NAME,
            api_key=primitivestring,
        )
        wf.metadata.setdefault('id_map', {})['gemmaapitextencode'] = gemmaapitextencode.node.id

        gemmaapitextencode_2 = GemmaAPITextEncode(
            _id='4981',
            widget_0=WIDGET_0,
            widget_1=384,
            widget_2=False,
            widget_3=MODEL_NAME,
            api_key=primitivestring,
        )
        wf.metadata.setdefault('id_map', {})['gemmaapitextencode_2'] = gemmaapitextencode_2.node.id

        resizeimagemasknode = ResizeImageMaskNode(
            _id='4990',
            resize_type='scale longer dimension',
            scale_method='lanczos',
            input=loadimage.out('IMAGE'),
        )
        wf.metadata.setdefault('id_map', {})['resizeimagemasknode'] = resizeimagemasknode.node.id

        ltxfloattoint = LTXFloatToInt(_id='5000', rounding=0, a=primitivefloat)
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

        ltxvpreprocess = LTXVPreprocess(
            _id='3336',
            img_compression=18,
            image=resizeimagemasknode,
        )
        wf.metadata.setdefault('id_map', {})['ltxvpreprocess'] = ltxvpreprocess.node.id

        ltxvemptylatentaudio = LTXVEmptyLatentAudio(
            _id='3980',
            widget_0=5,
            widget_1=8,
            frames_number=primitiveint,
            frame_rate=ltxfloattoint,
            audio_vae=lowvramaudiovaeloader,
        )
        wf.metadata.setdefault('id_map', {})['ltxvemptylatentaudio'] = ltxvemptylatentaudio.node.id

        ltxvimgtovideoconditiononly = LTXVImgToVideoConditionOnly(
            _id='3159',
            strength=0.7,
            widget_1=False,
            bypass=primitiveboolean,
            image=ltxvpreprocess,
            latent=emptyltxvlatentvideo,
            vae=lowvramcheckpointloader.out('VAE'),
        )
        wf.metadata.setdefault('id_map', {})['ltxvimgtovideoconditiononly'] = ltxvimgtovideoconditiononly.node.id

        # Conditioning
        cfgguider = CFGGuider(
            _id='4828',
            cfg=GUIDE_STRENGTH_2,
            model=loraloadermodelonly,
            negative=ltxvconditioning.out('NEGATIVE'),
            positive=ltxvconditioning.out('POSITIVE'),
        )
        wf.metadata.setdefault('id_map', {})['cfgguider'] = cfgguider.node.id

        cfgguider_2 = CFGGuider(
            _id='4964',
            cfg=GUIDE_STRENGTH_2,
            model=loraloadermodelonly,
            negative=ltxvconditioning.out('NEGATIVE'),
            positive=ltxvconditioning.out('POSITIVE'),
        )
        wf.metadata.setdefault('id_map', {})['cfgguider_2'] = cfgguider_2.node.id

        ltxvconcatavlatent = LTXVConcatAVLatent(
            _id='4528',
            audio_latent=ltxvemptylatentaudio,
            video_latent=ltxvimgtovideoconditiononly,
        )
        wf.metadata.setdefault('id_map', {})['ltxvconcatavlatent'] = ltxvconcatavlatent.node.id

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

        ltxvimgtovideoconditiononly_2 = LTXVImgToVideoConditionOnly(
            _id='4970',
            widget_1=False,
            bypass=primitiveboolean,
            image=resizeimagemasknode,
            latent=ltxvseparateavlatent.out('VIDEO_LATENT'),
            vae=lowvramcheckpointloader.out('VAE'),
        )
        wf.metadata.setdefault('id_map', {})['ltxvimgtovideoconditiononly_2'] = ltxvimgtovideoconditiononly_2.node.id

        ltxvconcatavlatent_2 = LTXVConcatAVLatent(
            _id='4969',
            audio_latent=ltxvseparateavlatent.out('AUDIO_LATENT'),
            video_latent=ltxvimgtovideoconditiononly_2,
        )
        wf.metadata.setdefault('id_map', {})['ltxvconcatavlatent_2'] = ltxvconcatavlatent_2.node.id

        samplercustomadvanced_2 = SamplerCustomAdvanced(
            _id='4971',
            guider=cfgguider_2,
            latent_image=ltxvconcatavlatent_2,
            noise=randomnoise_2,
            sampler=ksamplerselect_2,
            sigmas=manualsigmas_2,
            _outputs=('OUTPUT', 'DENOISED_OUTPUT'),
        )
        wf.metadata.setdefault('id_map', {})['samplercustomadvanced_2'] = samplercustomadvanced_2.node.id

        ltxvseparateavlatent_2 = LTXVSeparateAVLatent(
            _id='4973',
            av_latent=samplercustomadvanced_2.out('OUTPUT'),
            _outputs=('VIDEO_LATENT', 'AUDIO_LATENT'),
        )
        wf.metadata.setdefault('id_map', {})['ltxvseparateavlatent_2'] = ltxvseparateavlatent_2.node.id

        ltxvaudiovaedecode = LTXVAudioVAEDecode(
            _id='4848',
            audio_vae=lowvramaudiovaeloader,
            samples=ltxvseparateavlatent_2.out('AUDIO_LATENT'),
        )
        wf.metadata.setdefault('id_map', {})['ltxvaudiovaedecode'] = ltxvaudiovaedecode.node.id

        ltxvtiledvaedecode = LTXVTiledVAEDecode(
            _id='4995',
            horizontal_tiles=2,
            vertical_tiles=2,
            overlap=6,
            latents=ltxvseparateavlatent_2.out('VIDEO_LATENT'),
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

        return wf.finalize(PUBLIC_INPUTS, output_type='SaveVideo', name='video', artifact_kind='video', mime_type='video/mp4', expected_cardinality='one', filename_prefix='output')

