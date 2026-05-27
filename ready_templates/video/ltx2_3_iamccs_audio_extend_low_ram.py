# vibecomfy: generated
# For hand-editing, run: python -m vibecomfy.cli copy-to-recipe <id>
"""Auto-generated ready_template — use python -m vibecomfy.cli copy-to-recipe <id> for hand-editing."""
from __future__ import annotations

from vibecomfy.templates import InputSpec, ReadyMetadata, new_workflow, node as raw_call
from vibecomfy.nodes.core import CFGGuider, CLIPTextEncode, DualCLIPLoader, EmptyLTXVLatentVideo, KSamplerSelect, LTXVAudioVAEEncode, LTXVConcatAVLatent, LTXVConditioning, LTXVImgToVideoInplace, LTXVPreprocess, LTXVSeparateAVLatent, LoadImage, LoraLoaderModelOnly, ManualSigmas, RandomNoise, ResizeImageMaskNode, ResizeImagesByLongerEdge, SamplerCustomAdvanced, SetLatentNoiseMask, SolidMask, UNETLoader
from vibecomfy.nodes.gguf import UnetLoaderGGUF
from vibecomfy.nodes.kjnodes import VAELoaderKJ
from vibecomfy.nodes.videohelpersuite import VHS_LoadAudioUpload


ALL = 'all'
AUDIO_VAE_NAME = 'ltx-2.3-22b-dev_audio_vae.safetensors'
AUTO = 'auto'
BF16 = 'bf16'
CLIP_NAME = 'gemma_3_12B_it_fp8_e4m3fn.safetensors'
CLIP_PROJECTION_NAME = 'ltx-2.3_text_projection_bf16.safetensors'
CUT = 'cut'
DEFAULT_FRAMES = 249
DEFAULT_FRAMES_2 = 241
DEFAULT_PROMPT = 'flicker, jitter, low quality, bad anatomy, static image, frozen frame, deformed motion'
DEFAULT_PROMPT_2 = 'cinematic image to video shot of a singer actor acting and singing a song during a musical, intense expression, coherent motion, smooth camera movement, high detail, stable composition, audio-reactive motion'
DEFAULT_SEED = 264060544821466
DEFAULT_SEED_2 = 851629932274714
DEFAULT_SEED_3 = 606399719654025
GUIDE_STRENGTH = 0.7
GUIDE_STRENGTH_2 = 1
IAMCCS_SEAM_DEBUG = 'iamccs_seam_debug'
IAMCCS_VAE_FRAMES_30S_FREE_LOW_RAM_SEG0 = 'iamccs_vae_frames/30s_free_low_ram/seg0'
JPG = 'jpg'
LEFT_CONTEXT_ONLY = 'left_context_only'
LORA_NAME = 'ltx-2.3-22b-distilled-lora-dynamic_fro09_avg_rank_105_bf16.safetensors'
MAIN_DEVICE = 'main_device'
MEL_BAND_ROFORMER_NAME = 'MelBandRoformer_fp32.safetensors'
NATIVE_WORKFLOW_SAFE = 'native_workflow_safe'
NONE = 'none'
RANDOMIZE = 'randomize'
SNAP_TO_VIDEO_DURATION = 'snap_to_video_duration'
SOFT_CLAMP = 'soft_clamp'
SOURCE = 'source'
UNET_NAME_GGUF = 'ltx-2.3-22b-dev-Q4_K_S.gguf'
USE_TIMELINE_CURSOR = 'use_timeline_cursor'
VIDEOCLIP_AUDIO_24FPS = 'videoclip_audio_24fps'
VIDEO_VAE_NAME = 'ltx-2.3-22b-dev_video_vae.safetensors'


PUBLIC_INPUT_METADATA = {
    'image': InputSpec(node='1', field='image', default='ChatGPT Image Mar 27, 2026, 08_27_32 AM.png', type='IMAGE', required=True, aliases=('input_image',), media_semantics='image'),
    'width': InputSpec(node='16', field='width', default=1024, type='INT'),
    'height': InputSpec(node='16', field='height', default=1024, type='INT'),
    'frames': InputSpec(node='17', field='length', default=DEFAULT_FRAMES_2, type='INT'),
    'seed': InputSpec(node='25', field='noise_seed', default=DEFAULT_SEED_2, type='INT'),
    'prompt': InputSpec(node='8', field='text', default=DEFAULT_PROMPT_2, type='STRING', required=True, media_semantics='text'),
    'negative_prompt': InputSpec(node='9', field='text', default=DEFAULT_PROMPT, type='STRING', aliases=('negative',), media_semantics='text'),
}

READY_METADATA = ReadyMetadata.build(
    capability='unknown',
    inputs=PUBLIC_INPUT_METADATA,
    requirements={'models': ['MelBandRoformer_fp32.safetensors', 'ltx-2.3-22b-dev-Q4_K_S.gguf', 'ltx-2.3-22b-dev_audio_vae.safetensors', 'ltx-2.3-22b-dev_video_vae.safetensors', 'ltx-2.3-22b-distilled-lora-dynamic_fro09_avg_rank_105_bf16.safetensors']},
    custom_node_packs={'ComfyUI-GGUF': {'commit': '6ea2651e7df66d7585f6ffee804b20e92fb38b8a', 'url': 'https://github.com/city96/ComfyUI-GGUF.git', 'class_schema_sha256': '1336fad984841444a9559b602c34ef11d1dd4b68a9a902437aaee6771ab5d2d3', 'classes_used': ['UnetLoaderGGUF'], 'pip_packages': ['gguf'], 'status': 'discovered'}, 'ComfyUI-KJNodes': {'commit': 'b7646ad70a7daa7aeb919ca542274758d26ba2df', 'url': 'https://github.com/kijai/ComfyUI-KJNodes.git', 'class_schema_sha256': '1beaf129c8fa26175d89a28f9ca10d08b5ac27c8fc9bff920263fcbba17cb691', 'classes_used': ['ResizeImagesByLongerEdge', 'VAELoaderKJ'], 'pip_packages': ['matplotlib'], 'status': 'discovered'}, 'ComfyUI-LTXVideo': {'commit': '229437c6b65796d6a7a63ae34be2bd5ba31fa543', 'url': 'https://github.com/Lightricks/ComfyUI-LTXVideo.git', 'class_schema_sha256': '82e0b1f31509a969cf441c45e2517d0cd93f31b5390cc16f4a0ffa244421f39e', 'classes_used': ['EmptyLTXVLatentVideo', 'LTXVConcatAVLatent', 'LTXVConditioning', 'LTXVPreprocess', 'LTXVSeparateAVLatent'], 'pip_packages': [], 'status': 'discovered'}},
    provenance={'source_path': 'workflow_corpus/custom_nodes/ltxvideo/iamccs/IAMCCS_LTX23_BEST_3SEG_AUDIOEXT_30S_FREE_LOW_RAM.json', 'source_id': 'IAMCCS_LTX23_BEST_3SEG_AUDIOEXT_30S_FREE_LOW_RAM', 'source_type': 'api', 'source_workflow_path': 'workflow_corpus/custom_nodes/ltxvideo/iamccs/IAMCCS_LTX23_BEST_3SEG_AUDIOEXT_30S_FREE_LOW_RAM.json', 'output_mode': 'ready_template', 'ready_id': 'video/ltx2_3_iamccs_audio_extend_low_ram'},
)

def build() -> VibeWorkflow:
    """Build the workflow (auto-generated)."""
    wf = new_workflow(READY_METADATA, source_path=__file__)

    # Inputs
    image, _ = LoadImage(image='ChatGPT Image Mar 27, 2026, 08_27_32 AM.png')

    audio, _ = VHS_LoadAudioUpload(
        audio='It’s only Rock and roll.mp3',
        audiopreview={'params': {'start_time': 38, 'duration': 28, 'filename': 'It’s only Rock and roll.mp3', 'type': 'input'}},
        duration=28,
        start_time=38,
    )

    unetloadergguf = UnetLoaderGGUF(unet_name=UNET_NAME_GGUF)

    # Loaders
    dualcliploader = DualCLIPLoader(
        clip_name1=CLIP_NAME,
        clip_name2=CLIP_PROJECTION_NAME,
        type_='ltxv',
        device='default',
    )

    # Sampling
    ksamplerselect = KSamplerSelect(sampler_name='euler')

    manualsigmas = ManualSigmas(
        sigmas='1., 0.99375, 0.9875, 0.98125, 0.975, 0.909375, 0.725, 0.421875, 0.0',
    )

    vaeloaderkj = VAELoaderKJ(
        vae_name=VIDEO_VAE_NAME,
        device=MAIN_DEVICE,
        weight_dtype=BF16,
    )

    vaeloaderkj_2 = VAELoaderKJ(
        vae_name=AUDIO_VAE_NAME,
        device=MAIN_DEVICE,
        weight_dtype=BF16,
    )

    solidmask = SolidMask(value=0, width=1024, height=1024)

    emptyltxvlatentvideo = EmptyLTXVLatentVideo(
        width=1920,
        height=1088,
        length=DEFAULT_FRAMES_2,
    )

    randomnoise = RandomNoise(
        noise_seed=DEFAULT_SEED_2,
        control_after_generate=RANDOMIZE,
    )

    ltxvpreprocess_2 = LTXVPreprocess(img_compression=33)

    emptyltxvlatentvideo_2 = EmptyLTXVLatentVideo(
        width=1920,
        height=1088,
        length=DEFAULT_FRAMES,
    )

    randomnoise_2 = RandomNoise(
        noise_seed=DEFAULT_SEED,
        control_after_generate=RANDOMIZE,
    )

    ltxvpreprocess_3 = LTXVPreprocess(img_compression=33)

    emptyltxvlatentvideo_3 = EmptyLTXVLatentVideo(
        width=1920,
        height=1088,
        length=DEFAULT_FRAMES,
    )

    randomnoise_3 = RandomNoise(
        noise_seed=DEFAULT_SEED_3,
        control_after_generate=RANDOMIZE,
    )

    unetloader = UNETLoader(unet_name=MEL_BAND_ROFORMER_NAME)

    resizeimagemasknode = ResizeImageMaskNode(
        resize_type='scale dimensions',
        scale_method=1080,
        widget_3='center',
        widget_4='lanczos',
        input=image,
    )

    loraloadermodelonly = LoraLoaderModelOnly(
        lora_name=LORA_NAME,
        strength_model=GUIDE_STRENGTH,
        model=unetloadergguf,
    )

    # Conditioning
    cliptextencode = CLIPTextEncode(text=DEFAULT_PROMPT_2, clip=dualcliploader)
    cliptextencode_2 = CLIPTextEncode(text=DEFAULT_PROMPT, clip=dualcliploader)

    iamccs_audioextensionmath = raw_call('IAMCCS_AudioExtensionMath', '20',
        widget_0=24,
        widget_1=0,
        widget_2=240,
        widget_3=240,
        widget_4=True,
        widget_5=240,
        widget_6=0,
        audio=audio,
    )

    resizeimagesbylongeredge = ResizeImagesByLongerEdge(
        longer_edge=1536,
        images=resizeimagemasknode,
    )

    positive, negative = LTXVConditioning(
        frame_rate=24,
        negative=cliptextencode_2,
        positive=cliptextencode,
    )

    iamccs_audioextender = raw_call('IAMCCS_AudioExtender', '21',
        widget_0=24,
        widget_1=LEFT_CONTEXT_ONLY,
        widget_10=240,
        widget_11=240,
        widget_12=0,
        widget_13=0,
        widget_14=240,
        widget_15=240,
        widget_2=0.5,
        widget_3=0,
        widget_4=USE_TIMELINE_CURSOR,
        widget_5=SNAP_TO_VIDEO_DURATION,
        widget_6=SOFT_CLAMP,
        widget_7=0,
        widget_8=10,
        widget_9=240,
        audio=audio,
        effective_unique_frames=iamccs_audioextensionmath.out(3),
        segment_start_frames=iamccs_audioextensionmath.out(1),
    )

    iamccs_audiotimelinegate = raw_call('IAMCCS_AudioTimelineGate', '30',
        widget_0=1,
        widget_1=True,
        widget_2=1,
        widget_3=True,
        widget_4=0,
        widget_5=0,
        cursor_frames_out=iamccs_audioextensionmath.out(0),
        effective_unique_frames=iamccs_audioextensionmath.out(3),
        is_last_segment=iamccs_audioextensionmath.out(8),
        remaining_frames_after=iamccs_audioextensionmath.out(7),
    )

    cfgguider = CFGGuider(
        cfg=GUIDE_STRENGTH_2,
        model=loraloadermodelonly,
        negative=negative,
        positive=positive,
    )

    ltxvpreprocess = LTXVPreprocess(img_compression=33, image=resizeimagesbylongeredge)

    ltxvaudiovaeencode = LTXVAudioVAEEncode(
        audio=iamccs_audioextender.out(0),
        audio_vae=vaeloaderkj_2,
    )

    iamccs_audioextensionmath_2 = raw_call('IAMCCS_AudioExtensionMath', '34',
        widget_0=24,
        widget_1=1,
        widget_2=249,
        widget_3=240,
        widget_4=True,
        widget_5=240,
        widget_6=0,
        audio=audio,
        cursor_frames_in=iamccs_audiotimelinegate.out(3),
    )

    ltxvimgtovideoinplace = LTXVImgToVideoInplace(
        image=ltxvpreprocess,
        latent=emptyltxvlatentvideo,
        vae=vaeloaderkj,
    )

    setlatentnoisemask = SetLatentNoiseMask(mask=solidmask, samples=ltxvaudiovaeencode)

    iamccs_audioextender_2 = raw_call('IAMCCS_AudioExtender', '35',
        widget_0=24,
        widget_1=LEFT_CONTEXT_ONLY,
        widget_10=249,
        widget_11=240,
        widget_12=0,
        widget_13=240,
        widget_14=240,
        widget_15=240,
        widget_2=0.5,
        widget_3=0,
        widget_4=USE_TIMELINE_CURSOR,
        widget_5=SNAP_TO_VIDEO_DURATION,
        widget_6=SOFT_CLAMP,
        widget_7=1,
        widget_8=10,
        widget_9=240,
        audio=audio,
        effective_unique_frames=iamccs_audioextensionmath_2.out(3),
        segment_start_frames=iamccs_audioextensionmath_2.out(1),
    )

    iamccs_audiotimelinegate_2 = raw_call('IAMCCS_AudioTimelineGate', '44',
        widget_0=1,
        widget_1=True,
        widget_2=1,
        widget_3=True,
        widget_4=0,
        widget_5=0,
        cursor_frames_out=iamccs_audioextensionmath_2.out(0),
        effective_unique_frames=iamccs_audioextensionmath_2.out(3),
        is_last_segment=iamccs_audioextensionmath_2.out(8),
        remaining_frames_after=iamccs_audioextensionmath_2.out(7),
    )

    ltxvconcatavlatent = LTXVConcatAVLatent(
        audio_latent=setlatentnoisemask,
        video_latent=ltxvimgtovideoinplace,
    )

    ltxvaudiovaeencode_2 = LTXVAudioVAEEncode(
        audio=iamccs_audioextender_2.out(0),
        audio_vae=vaeloaderkj_2,
    )

    iamccs_audioextensionmath_3 = raw_call('IAMCCS_AudioExtensionMath', '48',
        widget_0=24,
        widget_1=2,
        widget_2=249,
        widget_3=240,
        widget_4=True,
        widget_5=240,
        widget_6=0,
        audio=audio,
        cursor_frames_in=iamccs_audiotimelinegate_2.out(3),
    )

    output, _ = SamplerCustomAdvanced(
        guider=cfgguider,
        latent_image=ltxvconcatavlatent,
        noise=randomnoise,
        sampler=ksamplerselect,
        sigmas=manualsigmas,
    )

    setlatentnoisemask_2 = SetLatentNoiseMask(
        mask=solidmask,
        samples=ltxvaudiovaeencode_2,
    )

    iamccs_audioextender_3 = raw_call('IAMCCS_AudioExtender', '49',
        widget_0=24,
        widget_1=LEFT_CONTEXT_ONLY,
        widget_10=249,
        widget_11=240,
        widget_12=0,
        widget_13=480,
        widget_14=240,
        widget_15=240,
        widget_2=0.5,
        widget_3=0,
        widget_4=USE_TIMELINE_CURSOR,
        widget_5=SNAP_TO_VIDEO_DURATION,
        widget_6=SOFT_CLAMP,
        widget_7=2,
        widget_8=10,
        widget_9=240,
        audio=audio,
        effective_unique_frames=iamccs_audioextensionmath_3.out(3),
        segment_start_frames=iamccs_audioextensionmath_3.out(1),
    )

    iamccs_audiotimelinegate_3 = raw_call('IAMCCS_AudioTimelineGate', '58',
        widget_0=1,
        widget_1=True,
        widget_2=1,
        widget_3=True,
        widget_4=0,
        widget_5=0,
        cursor_frames_out=iamccs_audioextensionmath_3.out(0),
        effective_unique_frames=iamccs_audioextensionmath_3.out(3),
        is_last_segment=iamccs_audioextensionmath_3.out(8),
        remaining_frames_after=iamccs_audioextensionmath_3.out(7),
    )

    video_latent, _ = LTXVSeparateAVLatent(av_latent=output)

    ltxvaudiovaeencode_3 = LTXVAudioVAEEncode(
        audio=iamccs_audioextender_3.out(0),
        audio_vae=vaeloaderkj_2,
    )

    setlatentnoisemask_3 = SetLatentNoiseMask(
        mask=solidmask,
        samples=ltxvaudiovaeencode_3,
    )

    iamccs_vaedecodetodisk = raw_call('IAMCCS_VAEDecodeToDisk', '60',
        widget_0=IAMCCS_VAE_FRAMES_30S_FREE_LOW_RAM_SEG0,
        widget_1='seg0',
        widget_10=True,
        widget_2=JPG,
        widget_3=95,
        widget_4=True,
        widget_5=AUTO,
        widget_6=512,
        widget_7=64,
        widget_8=True,
        widget_9=IAMCCS_SEAM_DEBUG,
        samples=video_latent,
        vae=vaeloaderkj,
    )

    iamccs_ltx2_extensionmodule_disk = raw_call('IAMCCS_LTX2_ExtensionModule_Disk', '29',
        widget_0=IAMCCS_VAE_FRAMES_30S_FREE_LOW_RAM_SEG0,
        widget_1='iamccs_extension_disk/30s_free_low_ram/seg0_extended',
        widget_10=VIDEOCLIP_AUDIO_24FPS,
        widget_11='',
        widget_12=1,
        widget_2='iamccs_extension_disk/30s_free_low_ram/seg0_start',
        widget_3=9,
        widget_4=SOURCE,
        widget_5=CUT,
        widget_6=True,
        widget_7=NONE,
        widget_8=NATIVE_WORKFLOW_SAFE,
        widget_9='none',
        source_dir=iamccs_vaedecodetodisk.out(0),
    )

    iamccs_startdirtovideolatent = raw_call('IAMCCS_StartDirToVideoLatent', '33',
        widget_0='iamccs_extension_disk/30s_free_low_ram/seg0_start',
        widget_1=ALL,
        widget_2=9,
        widget_3=0,
        widget_4=1,
        widget_5=True,
        widget_6=33,
        latent=emptyltxvlatentvideo_2,
        start_dir=iamccs_ltx2_extensionmodule_disk.out(1),
        vae=vaeloaderkj,
    )

    ltxvconcatavlatent_2 = LTXVConcatAVLatent(
        audio_latent=setlatentnoisemask_2,
        video_latent=iamccs_startdirtovideolatent.out(0),
    )

    output_sampler, _ = SamplerCustomAdvanced(
        guider=cfgguider,
        latent_image=ltxvconcatavlatent_2,
        noise=randomnoise_2,
        sampler=ksamplerselect,
        sigmas=manualsigmas,
    )

    video_latent_ltxv, _ = LTXVSeparateAVLatent(av_latent=output_sampler)

    iamccs_vaedecodetodisk_2 = raw_call('IAMCCS_VAEDecodeToDisk', '61',
        widget_0='iamccs_vae_frames/30s_free_low_ram/seg1',
        widget_1='seg1',
        widget_10=True,
        widget_2=JPG,
        widget_3=95,
        widget_4=True,
        widget_5=AUTO,
        widget_6=512,
        widget_7=64,
        widget_8=True,
        widget_9=IAMCCS_SEAM_DEBUG,
        samples=video_latent_ltxv,
        vae=vaeloaderkj,
    )

    iamccs_ltx2_extensionmodule_disk_2 = raw_call('IAMCCS_LTX2_ExtensionModule_Disk', '43',
        widget_0=IAMCCS_VAE_FRAMES_30S_FREE_LOW_RAM_SEG0,
        widget_1='iamccs_extension_disk/30s_free_low_ram/seg1_extended',
        widget_10=VIDEOCLIP_AUDIO_24FPS,
        widget_11='',
        widget_12=0,
        widget_2='iamccs_extension_disk/30s_free_low_ram/seg1_start',
        widget_3=9,
        widget_4=SOURCE,
        widget_5=CUT,
        widget_6=True,
        widget_7=NONE,
        widget_8=NATIVE_WORKFLOW_SAFE,
        widget_9='none',
        new_dir=iamccs_vaedecodetodisk_2.out(0),
        source_dir=iamccs_ltx2_extensionmodule_disk.out(0),
    )

    iamccs_startdirtovideolatent_2 = raw_call('IAMCCS_StartDirToVideoLatent', '47',
        widget_0='iamccs_extension_disk/30s_free_low_ram/seg1_start',
        widget_1=ALL,
        widget_2=9,
        widget_3=0,
        widget_4=1,
        widget_5=True,
        widget_6=33,
        latent=emptyltxvlatentvideo_3,
        start_dir=iamccs_ltx2_extensionmodule_disk_2.out(1),
        vae=vaeloaderkj,
    )

    ltxvconcatavlatent_3 = LTXVConcatAVLatent(
        audio_latent=setlatentnoisemask_3,
        video_latent=iamccs_startdirtovideolatent_2.out(0),
    )

    output_sampler_2, _ = SamplerCustomAdvanced(
        guider=cfgguider,
        latent_image=ltxvconcatavlatent_3,
        noise=randomnoise_3,
        sampler=ksamplerselect,
        sigmas=manualsigmas,
    )

    video_latent_ltxv_2, _ = LTXVSeparateAVLatent(av_latent=output_sampler_2)

    iamccs_vaedecodetodisk_3 = raw_call('IAMCCS_VAEDecodeToDisk', '62',
        widget_0='iamccs_vae_frames/30s_free_low_ram/seg2',
        widget_1='seg2',
        widget_10=True,
        widget_2=JPG,
        widget_3=95,
        widget_4=True,
        widget_5=AUTO,
        widget_6=512,
        widget_7=64,
        widget_8=True,
        widget_9=IAMCCS_SEAM_DEBUG,
        samples=video_latent_ltxv_2,
        vae=vaeloaderkj,
    )

    iamccs_ltx2_extensionmodule_disk_3 = raw_call('IAMCCS_LTX2_ExtensionModule_Disk', '57',
        widget_0=IAMCCS_VAE_FRAMES_30S_FREE_LOW_RAM_SEG0,
        widget_1='iamccs_extension_disk/30s_free_low_ram/final_extended',
        widget_10=VIDEOCLIP_AUDIO_24FPS,
        widget_11='',
        widget_12=1,
        widget_2='iamccs_extension_disk/30s_free_low_ram/final_start',
        widget_3=9,
        widget_4=SOURCE,
        widget_5=CUT,
        widget_6=True,
        widget_7=NONE,
        widget_8=NATIVE_WORKFLOW_SAFE,
        widget_9='none',
        new_dir=iamccs_vaedecodetodisk_3.out(0),
        source_dir=iamccs_ltx2_extensionmodule_disk_2.out(0),
    )

    iamccs_videocombinefromdir = raw_call('IAMCCS_VideoCombineFromDir', '59',
        widget_0='iamccs_extension_disk/30s_free_low_ram/final_extended',
        widget_1=24,
        widget_2='IAMCCS/LTX23_BEST_3SEG_AUDIOEXT_30S_FREE_LOW_RAM',
        widget_3=19,
        widget_4='yuv420p',
        widget_5=True,
        audio=audio,
        frames_dir=iamccs_ltx2_extensionmodule_disk_3.out(0),
    )

    return wf.finalize(PUBLIC_INPUT_METADATA)

