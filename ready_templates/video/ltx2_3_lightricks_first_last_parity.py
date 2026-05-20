# vibecomfy: generated - converted by tools/convert_ready_templates.py
# Edits will be overwritten on regeneration. Put the manual opt-out
# marker on the first line if hand-editing is required.
"""Auto-generated ready_template - see tools/convert_ready_templates.py."""
from __future__ import annotations

from vibecomfy.templates import InputSpec, ModelAsset, ReadyMetadata, finalize, new_workflow, node as raw_call, ref
from vibecomfy.nodes.core import CFGGuider, CLIPTextEncode, CheckpointLoaderSimple, CreateVideo, EmptyLTXVLatentVideo, GetImageSize, LTXAVTextEncoderLoader, LTXVAddGuide, LTXVAudioVAEDecode, LTXVAudioVAELoader, LTXVConcatAVLatent, LTXVConditioning, LTXVCropGuides, LTXVEmptyLatentAudio, LTXVPreprocess, LTXVSeparateAVLatent, LoadImage, ManualSigmas, RandomNoise, ResizeImageMaskNode, SamplerCustomAdvanced, SamplerEulerAncestral, SaveVideo, VAEDecodeTiled


DEFAULT_PROMPT = 'A cinematic first-last frame transition.'
DEFAULT_SEED = 42
GUIDE_STRENGTH = 1
MODEL_NAME = 'gemma_3_12B_it_fp4_mixed.safetensors'
MODEL_NAME_2 = 'ltx-2.3-22b-distilled-fp8.safetensors'
RESIZE_TYPE = 'scale dimensions'
RESIZE_TYPE_CROP = 'center'
SCALE_METHOD = 'nearest-exact'


MODELS = {
    'ltx_2_3_22b_distilled_fp8': ModelAsset(url='https://huggingface.co/Lightricks/LTX-2.3-fp8/resolve/main/ltx-2.3-22b-distilled-fp8.safetensors', sha256='d9646b6f2d5c42d337b23671634c43bfeece6989644f51b4a3aa088465ccd3b2', hf_revision='1d756cd27fa11c0896c4dfee093cd1bf36c7f7a1', size_bytes=29531884062, subdir='checkpoints'),
    'gemma_3_12b_it_fp4_mixed': ModelAsset(url='https://huggingface.co/Comfy-Org/ltx-2/resolve/main/split_files/text_encoders/gemma_3_12B_it_fp4_mixed.safetensors', sha256='aaca463d11e6d8d2a4bdb0d6299214c15ef78a3f73e0ef8113d5a9d0219b3f6d', hf_revision='bd5f9c87fcb0360ae7112f9784562670894d9492', size_bytes=9447702218, subdir='text_encoders'),
}

PUBLIC_INPUTS = {
    'seed': InputSpec(node=ref('randomnoise'), field='noise_seed', default=DEFAULT_SEED),
    'model': InputSpec(node=ref('checkpointloadersimple'), field='ckpt_name', default=MODEL_NAME_2),
    'prompt': InputSpec(node=ref('cliptextencode_2'), field='text', default=DEFAULT_PROMPT),
    'negative_prompt': InputSpec(node=ref('cliptextencode'), field='text', default='blurry, distorted, low quality'),
    'seed_first': InputSpec(node=ref('randomnoise'), field='noise_seed', default=DEFAULT_SEED),
    'seed_last': InputSpec(node=ref('randomnoise'), field='noise_seed', default=DEFAULT_SEED),
    'width': InputSpec(node=ref('primitiveint_3'), field='value', default=832),
    'height': InputSpec(node=ref('primitiveint'), field='value', default=480),
    'output_fps': InputSpec(node=ref('primitivefloat'), field='value', default=16),
    'fps': InputSpec(node=ref('primitivefloat'), field='value', default=16),
    'fps_int': InputSpec(node=ref('primitiveint_4'), field='value', default=16),
    'first_strength': InputSpec(node=ref('ltxvaddguide_2'), field='strength', default=1.0),
    'last_strength': InputSpec(node=ref('ltxvaddguide'), field='strength', default=1.0),
    'first_image': InputSpec(node=ref('loadimage'), field='image', default='example_start.png'),
    'last_image': InputSpec(node=ref('loadimage_2'), field='image', default='example_end.png'),
    'start_image': InputSpec(node=ref('loadimage'), field='image', default='example_start.png'),
    'end_image': InputSpec(node=ref('loadimage_2'), field='image', default='example_end.png'),
    'length': InputSpec(node=ref('primitiveint_2'), field='value', default=81),
    'frames': InputSpec(node=ref('primitiveint_2'), field='value', default=81),
    'image': InputSpec(node=ref('loadimage'), field='image', default='example_start.png'),
    'input_image': InputSpec(node=ref('loadimage'), field='image', default='example_start.png'),
}

READY_METADATA = ReadyMetadata.build(
    capability='first_last_frame_video',
    inputs=PUBLIC_INPUTS,
    models=MODELS,
    requirements={'custom_nodes': ['ComfyUI-KJNodes', 'ComfyUI-LTXVideo']},
    custom_node_packs={'ComfyUI-KJNodes': {'commit': 'b7646ad70a7daa7aeb919ca542274758d26ba2df', 'url': 'https://github.com/kijai/ComfyUI-KJNodes.git', 'class_schema_sha256': '1beaf129c8fa26175d89a28f9ca10d08b5ac27c8fc9bff920263fcbba17cb691', 'classes_used': ['GetImageSize', 'LTXVAddGuide'], 'pip_packages': ['matplotlib'], 'status': 'pinned'}, 'ComfyUI-LTXVideo': {'commit': '229437c6b65796d6a7a63ae34be2bd5ba31fa543', 'url': 'https://github.com/Lightricks/ComfyUI-LTXVideo.git', 'class_schema_sha256': '82e0b1f31509a969cf441c45e2517d0cd93f31b5390cc16f4a0ffa244421f39e', 'classes_used': ['EmptyLTXVLatentVideo', 'LTXAVTextEncoderLoader', 'LTXVAudioVAEDecode', 'LTXVAudioVAELoader', 'LTXVConcatAVLatent', 'LTXVConditioning', 'LTXVCropGuides', 'LTXVEmptyLatentAudio', 'LTXVPreprocess', 'LTXVSeparateAVLatent'], 'pip_packages': [], 'status': 'pinned'}},
    approach='Official Lightricks distilled fp8 first/last frame route',
    smoke_resolution='256x256x5_frames',
    runtime_note='Patches named inputs for prompt, negative, seed, dimensions, frames, fps, first/last guide strengths, and first/last images.',
    discord_signal='Banodoco LTX notes point to the dedicated distilled fp8/quantized route for 4090 viability; dev+LoRA two-stage routes can OOM at 24GB.',
    ltx_best_practices=['Use the dedicated distilled fp8 checkpoint for first/last workflows on 24GB GPUs.', "Keep guide strengths in Wan2GP's 0..1 range.", 'Use tiled VAE decode for full-size app outputs.', 'Do not force the LTX2 memory-efficient Sage/Triton patch in the portable 4090 profile; LTX 2.3 guide masks must remain on the stable SDPA-compatible path unless a separate optimized profile proves the patch end-to-end.'],
    comfy_configuration={'memory_profile': 3, 'fp8_e4m3fn_text_enc': True},
)

def build() -> VibeWorkflow:
    """Build the workflow (auto-generated)."""
    with new_workflow(READY_METADATA, source_path=__file__) as wf:

        # Inputs
        loadimage = LoadImage(
            _id='31',
            image='example_start.png',
            _outputs=('image', 'mask'),
        )
        wf.metadata.setdefault('id_map', {})['loadimage'] = loadimage.node.id

        loadimage_2 = LoadImage(
            _id='39',
            image='example_end.png',
            _outputs=('image', 'mask'),
        )
        wf.metadata.setdefault('id_map', {})['loadimage_2'] = loadimage_2.node.id

        primitiveint = raw_call(wf, 'PrimitiveInt', '98', value=480)
        wf.metadata.setdefault('id_map', {})['primitiveint'] = primitiveint.node.id
        randomnoise = RandomNoise(_id='100', noise_seed=DEFAULT_SEED)
        wf.metadata.setdefault('id_map', {})['randomnoise'] = randomnoise.node.id
        primitiveint_2 = raw_call(wf, 'PrimitiveInt', '102', value=81)
        wf.metadata.setdefault('id_map', {})['primitiveint_2'] = primitiveint_2.node.id
        ltxavtextencoderloader = LTXAVTextEncoderLoader(
            _id='103',
            text_encoder=MODEL_NAME,
            ckpt_name=MODEL_NAME_2,
            device='default',
        )
        wf.metadata.setdefault('id_map', {})['ltxavtextencoderloader'] = ltxavtextencoderloader.node.id

        primitiveint_3 = raw_call(wf, 'PrimitiveInt', '113', value=832)
        wf.metadata.setdefault('id_map', {})['primitiveint_3'] = primitiveint_3.node.id
        primitiveint_4 = raw_call(wf, 'PrimitiveInt', '114', value=16)
        wf.metadata.setdefault('id_map', {})['primitiveint_4'] = primitiveint_4.node.id
        samplereulerancestral = SamplerEulerAncestral(_id='117', eta=0)
        wf.metadata.setdefault('id_map', {})['samplereulerancestral'] = samplereulerancestral.node.id
        manualsigmas = ManualSigmas(
            _id='118',
            sigmas='1., 0.99375, 0.9875, 0.98125, 0.975, 0.909375, 0.725, 0.421875, 0.0',
        )
        wf.metadata.setdefault('id_map', {})['manualsigmas'] = manualsigmas.node.id

        primitivefloat = raw_call(wf, 'PrimitiveFloat', '123', value=16)
        wf.metadata.setdefault('id_map', {})['primitivefloat'] = primitivefloat.node.id
        ltxvaudiovaeloader = LTXVAudioVAELoader(_id='126', ckpt_name=MODEL_NAME_2)
        wf.metadata.setdefault('id_map', {})['ltxvaudiovaeloader'] = ltxvaudiovaeloader.node.id
        # Loaders
        checkpointloadersimple = CheckpointLoaderSimple(
            _id='127',
            ckpt_name=MODEL_NAME_2,
            _outputs=('model', 'clip', 'vae'),
        )
        wf.metadata.setdefault('id_map', {})['checkpointloadersimple'] = checkpointloadersimple.node.id

        ltxvemptylatentaudio = LTXVEmptyLatentAudio(
            _id='101',
            frames_number=primitiveint_2,
            frame_rate=primitiveint_4,
            audio_vae=ltxvaudiovaeloader,
        )
        wf.metadata.setdefault('id_map', {})['ltxvemptylatentaudio'] = ltxvemptylatentaudio.node.id

        # Conditioning
        cliptextencode = CLIPTextEncode(
            _id='112',
            text='blurry, distorted, low quality',
            clip=ltxavtextencoderloader,
        )
        wf.metadata.setdefault('id_map', {})['cliptextencode'] = cliptextencode.node.id

        resizeimagemasknode = ResizeImageMaskNode(
            _id='124',
            resize_type=RESIZE_TYPE,
            scale_method=SCALE_METHOD,
            input=loadimage.out('image'),
            **{'resize_type.crop': RESIZE_TYPE_CROP, 'resize_type.height': primitiveint, 'resize_type.width': primitiveint_3},
        )
        wf.metadata.setdefault('id_map', {})['resizeimagemasknode'] = resizeimagemasknode.node.id

        resizeimagemasknode_2 = ResizeImageMaskNode(
            _id='125',
            resize_type=RESIZE_TYPE,
            scale_method=SCALE_METHOD,
            input=loadimage_2.out('image'),
            **{'resize_type.crop': RESIZE_TYPE_CROP, 'resize_type.height': primitiveint, 'resize_type.width': primitiveint_3},
        )
        wf.metadata.setdefault('id_map', {})['resizeimagemasknode_2'] = resizeimagemasknode_2.node.id

        cliptextencode_2 = CLIPTextEncode(
            _id='128',
            text=DEFAULT_PROMPT,
            clip=ltxavtextencoderloader,
        )
        wf.metadata.setdefault('id_map', {})['cliptextencode_2'] = cliptextencode_2.node.id

        ltxvpreprocess = LTXVPreprocess(
            _id='99',
            img_compression=25,
            image=resizeimagemasknode_2,
        )
        wf.metadata.setdefault('id_map', {})['ltxvpreprocess'] = ltxvpreprocess.node.id

        ltxvpreprocess_2 = LTXVPreprocess(
            _id='104',
            img_compression=25,
            image=resizeimagemasknode,
        )
        wf.metadata.setdefault('id_map', {})['ltxvpreprocess_2'] = ltxvpreprocess_2.node.id

        ltxvconditioning = LTXVConditioning(
            _id='109',
            frame_rate=primitivefloat,
            negative=cliptextencode,
            positive=cliptextencode_2,
            _outputs=('positive', 'negative'),
        )
        wf.metadata.setdefault('id_map', {})['ltxvconditioning'] = ltxvconditioning.node.id

        getimagesize = GetImageSize(
            _id='110',
            image=resizeimagemasknode,
            _outputs=('width', 'height', 'batch_size'),
        )
        wf.metadata.setdefault('id_map', {})['getimagesize'] = getimagesize.node.id

        # Sampling
        emptyltxvlatentvideo = EmptyLTXVLatentVideo(
            _id='108',
            width=getimagesize.out('width'),
            height=getimagesize.out('height'),
            length=primitiveint_2,
        )
        wf.metadata.setdefault('id_map', {})['emptyltxvlatentvideo'] = emptyltxvlatentvideo.node.id

        ltxvaddguide_2 = LTXVAddGuide(
            _id='115',
            strength=1.0,
            image=ltxvpreprocess_2,
            latent=emptyltxvlatentvideo,
            negative=ltxvconditioning.out('negative'),
            positive=ltxvconditioning.out('positive'),
            vae=checkpointloadersimple.out('vae'),
            _outputs=('positive', 'negative', 'latent'),
        )
        wf.metadata.setdefault('id_map', {})['ltxvaddguide_2'] = ltxvaddguide_2.node.id

        ltxvaddguide = LTXVAddGuide(
            _id='111',
            frame_idx=-1,
            strength=1.0,
            image=ltxvpreprocess,
            latent=ltxvaddguide_2.out('latent'),
            negative=ltxvaddguide_2.out('negative'),
            positive=ltxvaddguide_2.out('positive'),
            vae=checkpointloadersimple.out('vae'),
            _outputs=('positive', 'negative', 'latent'),
        )
        wf.metadata.setdefault('id_map', {})['ltxvaddguide'] = ltxvaddguide.node.id

        # Conditioning
        cfgguider = CFGGuider(
            _id='116',
            cfg=GUIDE_STRENGTH,
            model=checkpointloadersimple.out('model'),
            negative=ltxvaddguide.out('negative'),
            positive=ltxvaddguide.out('positive'),
        )
        wf.metadata.setdefault('id_map', {})['cfgguider'] = cfgguider.node.id

        ltxvconcatavlatent = LTXVConcatAVLatent(
            _id='119',
            audio_latent=ltxvemptylatentaudio,
            video_latent=ltxvaddguide.out('latent'),
        )
        wf.metadata.setdefault('id_map', {})['ltxvconcatavlatent'] = ltxvconcatavlatent.node.id

        # Sampling
        samplercustomadvanced = SamplerCustomAdvanced(
            _id='120',
            guider=cfgguider,
            latent_image=ltxvconcatavlatent,
            noise=randomnoise,
            sampler=samplereulerancestral,
            sigmas=manualsigmas,
            _outputs=('output', 'denoised_output'),
        )
        wf.metadata.setdefault('id_map', {})['samplercustomadvanced'] = samplercustomadvanced.node.id

        ltxvseparateavlatent = LTXVSeparateAVLatent(
            _id='121',
            av_latent=samplercustomadvanced.out('denoised_output'),
            _outputs=('video_latent', 'audio_latent'),
        )
        wf.metadata.setdefault('id_map', {})['ltxvseparateavlatent'] = ltxvseparateavlatent.node.id

        ltxvcropguides = LTXVCropGuides(
            _id='106',
            latent=ltxvseparateavlatent.out('video_latent'),
            negative=ltxvaddguide.out('negative'),
            positive=ltxvaddguide.out('positive'),
            _outputs=('positive', 'negative', 'latent'),
        )
        wf.metadata.setdefault('id_map', {})['ltxvcropguides'] = ltxvcropguides.node.id

        ltxvaudiovaedecode = LTXVAudioVAEDecode(
            _id='107',
            audio_vae=ltxvaudiovaeloader,
            samples=ltxvseparateavlatent.out('audio_latent'),
        )
        wf.metadata.setdefault('id_map', {})['ltxvaudiovaedecode'] = ltxvaudiovaedecode.node.id

        # Decode
        vaedecodetiled = VAEDecodeTiled(
            _id='105',
            tile_size=768,
            temporal_size=4096,
            temporal_overlap=64,
            samples=ltxvcropguides.out('latent'),
            vae=checkpointloadersimple.out('vae'),
        )
        wf.metadata.setdefault('id_map', {})['vaedecodetiled'] = vaedecodetiled.node.id

        createvideo = CreateVideo(
            _id='122',
            fps=primitivefloat,
            audio=ltxvaudiovaedecode,
            images=vaedecodetiled,
        )
        wf.metadata.setdefault('id_map', {})['createvideo'] = createvideo.node.id

        # Outputs
        savevideo = SaveVideo(_id='68', filename_prefix='output', video=createvideo)
        wf.metadata.setdefault('id_map', {})['savevideo'] = savevideo.node.id

        return wf.finalize(PUBLIC_INPUTS, output_type='SaveVideo', name='video', artifact_kind='video', mime_type='video/mp4', expected_cardinality='one', filename_prefix='output')

