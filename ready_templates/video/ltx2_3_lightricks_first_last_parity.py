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
    'first_strength': InputSpec(node=ref('ltxvaddguide'), field='strength', default=1.0),
    'last_strength': InputSpec(node=ref('ltxvaddguide_2'), field='strength', default=1.0),
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
        loadimage = LoadImage(image='example_start.png', _outputs=('image', 'mask'))
        loadimage_2 = LoadImage(image='example_end.png', _outputs=('image', 'mask'))
        primitiveint = raw_call(wf, 'PrimitiveInt', '98', value=480)
        randomnoise = RandomNoise(noise_seed=DEFAULT_SEED)
        primitiveint_2 = raw_call(wf, 'PrimitiveInt', '102', value=81)
        ltxavtextencoderloader = LTXAVTextEncoderLoader(
            text_encoder=MODEL_NAME,
            ckpt_name=MODEL_NAME_2,
            device='default',
        )

        primitiveint_3 = raw_call(wf, 'PrimitiveInt', '113', value=832)
        primitiveint_4 = raw_call(wf, 'PrimitiveInt', '114', value=16)
        samplereulerancestral = SamplerEulerAncestral(eta=0)
        manualsigmas = ManualSigmas(
            sigmas='1., 0.99375, 0.9875, 0.98125, 0.975, 0.909375, 0.725, 0.421875, 0.0',
        )

        primitivefloat = raw_call(wf, 'PrimitiveFloat', '123', value=16)
        ltxvaudiovaeloader = LTXVAudioVAELoader(ckpt_name=MODEL_NAME_2)

        # Loaders
        checkpointloadersimple = CheckpointLoaderSimple(
            ckpt_name=MODEL_NAME_2,
            _outputs=('model', 'clip', 'vae'),
        )

        ltxvemptylatentaudio = LTXVEmptyLatentAudio(
            frames_number=primitiveint_2,
            frame_rate=primitiveint_4,
            audio_vae=ltxvaudiovaeloader,
        )

        # Conditioning
        cliptextencode = CLIPTextEncode(
            text='blurry, distorted, low quality',
            clip=ltxavtextencoderloader,
        )

        resizeimagemasknode = ResizeImageMaskNode(
            resize_type=RESIZE_TYPE,
            scale_method=SCALE_METHOD,
            input=loadimage.out('image'),
            **{'resize_type.crop': RESIZE_TYPE_CROP, 'resize_type.height': primitiveint, 'resize_type.width': primitiveint_3},
        )

        resizeimagemasknode_2 = ResizeImageMaskNode(
            resize_type=RESIZE_TYPE,
            scale_method=SCALE_METHOD,
            input=loadimage_2.out('image'),
            **{'resize_type.crop': RESIZE_TYPE_CROP, 'resize_type.height': primitiveint, 'resize_type.width': primitiveint_3},
        )

        cliptextencode_2 = CLIPTextEncode(
            text=DEFAULT_PROMPT,
            clip=ltxavtextencoderloader,
        )

        ltxvpreprocess = LTXVPreprocess(img_compression=25, image=resizeimagemasknode_2)
        ltxvpreprocess_2 = LTXVPreprocess(img_compression=25, image=resizeimagemasknode)
        ltxvconditioning = LTXVConditioning(
            frame_rate=primitivefloat,
            negative=cliptextencode,
            positive=cliptextencode_2,
            _outputs=('positive', 'negative'),
        )

        getimagesize = GetImageSize(
            image=resizeimagemasknode,
            _outputs=('width', 'height', 'batch_size'),
        )

        # Sampling
        emptyltxvlatentvideo = EmptyLTXVLatentVideo(
            width=getimagesize.out('width'),
            height=getimagesize.out('height'),
            length=primitiveint_2,
        )

        ltxvaddguide = LTXVAddGuide(
            strength=1.0,
            image=ltxvpreprocess_2,
            latent=emptyltxvlatentvideo,
            negative=ltxvconditioning.out('negative'),
            positive=ltxvconditioning.out('positive'),
            vae=checkpointloadersimple.out('vae'),
            _outputs=('positive', 'negative', 'latent'),
        )

        ltxvaddguide_2 = LTXVAddGuide(
            frame_idx=-1,
            strength=1.0,
            image=ltxvpreprocess,
            latent=ltxvaddguide.out('latent'),
            negative=ltxvaddguide.out('negative'),
            positive=ltxvaddguide.out('positive'),
            vae=checkpointloadersimple.out('vae'),
            _outputs=('positive', 'negative', 'latent'),
        )

        # Conditioning
        cfgguider = CFGGuider(
            cfg=GUIDE_STRENGTH,
            model=checkpointloadersimple.out('model'),
            negative=ltxvaddguide_2.out('negative'),
            positive=ltxvaddguide_2.out('positive'),
        )

        ltxvconcatavlatent = LTXVConcatAVLatent(
            audio_latent=ltxvemptylatentaudio,
            video_latent=ltxvaddguide_2.out('latent'),
        )

        # Sampling
        samplercustomadvanced = SamplerCustomAdvanced(
            guider=cfgguider,
            latent_image=ltxvconcatavlatent,
            noise=randomnoise,
            sampler=samplereulerancestral,
            sigmas=manualsigmas,
            _outputs=('output', 'denoised_output'),
        )

        ltxvseparateavlatent = LTXVSeparateAVLatent(
            av_latent=samplercustomadvanced.out('denoised_output'),
            _outputs=('video_latent', 'audio_latent'),
        )

        ltxvcropguides = LTXVCropGuides(
            latent=ltxvseparateavlatent.out('video_latent'),
            negative=ltxvaddguide_2.out('negative'),
            positive=ltxvaddguide_2.out('positive'),
            _outputs=('positive', 'negative', 'latent'),
        )

        ltxvaudiovaedecode = LTXVAudioVAEDecode(
            audio_vae=ltxvaudiovaeloader,
            samples=ltxvseparateavlatent.out('audio_latent'),
        )

        # Decode
        vaedecodetiled = VAEDecodeTiled(
            tile_size=768,
            temporal_size=4096,
            temporal_overlap=64,
            samples=ltxvcropguides.out('latent'),
            vae=checkpointloadersimple.out('vae'),
        )

        createvideo = CreateVideo(
            fps=primitivefloat,
            audio=ltxvaudiovaedecode,
            images=vaedecodetiled,
        )

        # Outputs
        savevideo = SaveVideo(filename_prefix='output', video=createvideo)

        wf._set_id_map({name: node.node.id for name, node in (('loadimage', loadimage), ('loadimage_2', loadimage_2), ('primitiveint', primitiveint), ('randomnoise', randomnoise), ('primitiveint_2', primitiveint_2), ('ltxavtextencoderloader', ltxavtextencoderloader), ('primitiveint_3', primitiveint_3), ('primitiveint_4', primitiveint_4), ('samplereulerancestral', samplereulerancestral), ('manualsigmas', manualsigmas), ('primitivefloat', primitivefloat), ('ltxvaudiovaeloader', ltxvaudiovaeloader), ('checkpointloadersimple', checkpointloadersimple), ('ltxvemptylatentaudio', ltxvemptylatentaudio), ('cliptextencode', cliptextencode), ('resizeimagemasknode', resizeimagemasknode), ('resizeimagemasknode_2', resizeimagemasknode_2), ('cliptextencode_2', cliptextencode_2), ('ltxvpreprocess', ltxvpreprocess), ('ltxvpreprocess_2', ltxvpreprocess_2), ('ltxvconditioning', ltxvconditioning), ('getimagesize', getimagesize), ('emptyltxvlatentvideo', emptyltxvlatentvideo), ('ltxvaddguide', ltxvaddguide), ('ltxvaddguide_2', ltxvaddguide_2), ('cfgguider', cfgguider), ('ltxvconcatavlatent', ltxvconcatavlatent), ('samplercustomadvanced', samplercustomadvanced), ('ltxvseparateavlatent', ltxvseparateavlatent), ('ltxvcropguides', ltxvcropguides), ('ltxvaudiovaedecode', ltxvaudiovaedecode), ('vaedecodetiled', vaedecodetiled), ('createvideo', createvideo), ('savevideo', savevideo))})

        return wf.finalize(PUBLIC_INPUTS, output_type='SaveVideo', name='video', artifact_kind='video', mime_type='video/mp4', expected_cardinality='one', filename_prefix='output')

