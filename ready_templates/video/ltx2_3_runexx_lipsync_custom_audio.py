# vibecomfy: generated
# For hand-editing, run: python -m vibecomfy.cli copy-to-recipe <id>
"""Auto-generated ready_template — use python -m vibecomfy.cli copy-to-recipe <id> for hand-editing."""
from __future__ import annotations

from vibecomfy.templates import InputSpec, ReadyMetadata, new_workflow, node as raw_call
from vibecomfy.nodes.core import BasicScheduler, CFGGuider, CLIPTextEncode, ComfyMathExpression, ComfySwitchNode, DualCLIPLoader, GetImageRangeFromBatch, KSamplerSelect, LTXAVTextEncoderLoader, LTXVAudioVAEDecode, LTXVAudioVAEEncode, LTXVConcatAVLatent, LTXVConditioning, LTXVCropGuides, LTXVEmptyLatentAudio, LTXVImgToVideoInplace, LTXVLatentUpsampler, LTXVPreprocess, LTXVSeparateAVLatent, LatentUpscaleModelLoader, LoadAudio, LoraLoaderModelOnly, ManualSigmas, MaskToImage, ModelSamplingSD3, PreviewImage, RandomNoise, ResizeImageMaskNode, ResizeImagesByLongerEdge, SamplerCustomAdvanced, SetLatentNoiseMask, SolidMask, StringConcatenate, TextGenerateLTX2Prompt, TrimAudioDuration, UNETLoader, VAEDecode, VAEDecodeTiled, VAEEncode, VAELoader
from vibecomfy.nodes.gguf import DualCLIPLoaderGGUF, UnetLoaderGGUF
from vibecomfy.nodes.kjnodes import BlockifyMask, GetImageSizeAndCount, INTConstant, ImageResizeKJv2, LTX2AttentionTunerPatch, LTX2MemoryEfficientSageAttentionPatch, LTX2_NAG, LTXVAudioVideoMask, LTXVChunkFeedForward, LazySwitchKJ, PathchSageAttentionKJ, SimpleCalculatorKJ, VAELoaderKJ
from vibecomfy.nodes.ltxvideo import LTXVAddLatentGuide, LTXVPreprocessMasks, LTXVSetVideoLatentNoiseMasks
from vibecomfy.nodes.rgthree import Power_Lora_Loader_rgthree
from vibecomfy.nodes.videohelpersuite import VHS_LoadVideoFFmpeg, VHS_VideoCombine, VHS_VideoInfo


AUDIO_VAE_NAME = 'LTX23_audio_vae_bf16_KJ.safetensors'
CLIP_NAME = 'gemma_3_12B_it_fp8_scaled.safetensors'
CLIP_NAME_GGUF = 'gemma-3-12b-it-Q2_K.gguf'
CLIP_PROJECTION_NAME = 'VIDEO\\LTX\\LTX-2\\ltx-2.3_text_projection_bf16.safetensors'
CPU = 'cpu'
DEFAULT = 'default'
DEFAULT_FRAMES = 1
DEFAULT_PROMPT = ' distorted sound, saturated sound, loud sound'
DEFAULT_PROMPT_2 = 'text, subtitles, logo, low quality, distorted, bad anatomy, oversaturated, pixelated, low resolution, grainy, compression artifacts, jpeg artifacts, glitches, watermark, signature, copyright,  distortedsound, saturated sound, loud sound , deformed facial features, asymmetrical face, missing facial features, extra limbs, disfigured hands, blurry teeth, disfigured teeth'
DEFAULT_SEED = 43
DEFAULT_SEED_2 = 790774741312584
GUIDE_STRENGTH = 0.6
GUIDE_STRENGTH_2 = 1
GUIDE_STRENGTH_3 = 0.7
LORA_NAME = 'LTX\\LTX-2\\ltx-2.3-22b-distilled-lora-384.safetensors'
MEL_BAND_ROFORMER_NAME = 'MelBandRoformer\\MelBandRoformer_fp16.safetensors'
NEAREST_EXACT = 'nearest-exact'
SCALE_BY_MULTIPLIER = 'scale by multiplier'
SPATIAL_UPSCALER_NAME = 'ltx-2.3-spatial-upscaler-x2-1.1.safetensors'
UNET_NAME = 'LTXVideo\\v2\\ltx-2.3-22b-distilled-1.1_transformer_only_fp8_scaled.safetensors'
UNET_NAME_GGUF = 'LTXvideo\\LTX-2\\quantstack\\LTX-2.3-distilled-Q4_K_S.gguf'
VAE_TAESD_NAME = 'vae_approx\\taeltx2_3.safetensors'
VIDEO_VAE_NAME = 'LTX23_video_vae_bf16_KJ.safetensors'


PUBLIC_INPUT_METADATA = {
    'enable_promptenhance': InputSpec(node='e428c881-c48b-4849-9158-8311b4df27c7:878', field='switch', default=False),
    'last_latent_strength': InputSpec(node='799', field='strength', default=1.0),
    'seed': InputSpec(node='115', field='noise_seed', default=DEFAULT_SEED_2, type='INT'),
    'prompt': InputSpec(node='110', field='text', default=DEFAULT_PROMPT_2, type='STRING', required=True, media_semantics='text'),
    'negative_prompt': InputSpec(node='626', field='text', default=DEFAULT_PROMPT, type='STRING', aliases=('negative',), media_semantics='text'),
}

READY_METADATA = ReadyMetadata.build(
    capability='unknown',
    inputs=PUBLIC_INPUT_METADATA,
    requirements={'models': ['LTX23_audio_vae_bf16_KJ.safetensors', 'LTX23_video_vae_bf16_KJ.safetensors', 'LTXVideo\\v2\\ltx-2.3-22b-distilled-1.1_transformer_only_fp8_scaled.safetensors', 'LTX\\LTX-2\\ltx-2.3-22b-distilled-lora-384.safetensors', 'LTXvideo\\LTX-2\\quantstack\\LTX-2.3-distilled-Q4_K_S.gguf', 'VIDEO\\LTX\\LTX-2\\ltx-2.3_text_projection_bf16.safetensors', 'euler_ancestral_cfg_pp', 'euler_cfg_pp', 'ltx-2.3-spatial-upscaler-x2-1.1.safetensors', 'vae_approx\\taeltx2_3.safetensors']},
    custom_node_packs={'ComfyUI-GGUF': {'commit': '6ea2651e7df66d7585f6ffee804b20e92fb38b8a', 'url': 'https://github.com/city96/ComfyUI-GGUF.git', 'class_schema_sha256': '1336fad984841444a9559b602c34ef11d1dd4b68a9a902437aaee6771ab5d2d3', 'classes_used': ['DualCLIPLoaderGGUF', 'UnetLoaderGGUF'], 'pip_packages': ['gguf'], 'status': 'discovered'}, 'ComfyUI-KJNodes': {'commit': 'b7646ad70a7daa7aeb919ca542274758d26ba2df', 'url': 'https://github.com/kijai/ComfyUI-KJNodes.git', 'class_schema_sha256': '1beaf129c8fa26175d89a28f9ca10d08b5ac27c8fc9bff920263fcbba17cb691', 'classes_used': ['BlockifyMask', 'GetImageRangeFromBatch', 'GetImageSizeAndCount', 'INTConstant', 'ImageResizeKJv2', 'PathchSageAttentionKJ', 'ResizeImagesByLongerEdge', 'SimpleCalculatorKJ', 'VAELoaderKJ'], 'pip_packages': ['matplotlib'], 'status': 'discovered'}, 'ComfyUI-LTXVideo': {'commit': '229437c6b65796d6a7a63ae34be2bd5ba31fa543', 'url': 'https://github.com/Lightricks/ComfyUI-LTXVideo.git', 'class_schema_sha256': '82e0b1f31509a969cf441c45e2517d0cd93f31b5390cc16f4a0ffa244421f39e', 'classes_used': ['LTX2AttentionTunerPatch', 'LTX2_NAG', 'LTXAVTextEncoderLoader', 'LTXVAudioVAEDecode', 'LTXVChunkFeedForward', 'LTXVConcatAVLatent', 'LTXVConditioning', 'LTXVCropGuides', 'LTXVEmptyLatentAudio', 'LTXVPreprocess', 'LTXVSeparateAVLatent', 'LatentUpscaleModelLoader'], 'pip_packages': [], 'status': 'discovered'}, 'ComfyUI-VideoHelperSuite': {'commit': '4ee72c065db22c9d96c2427954dc69e7b908444b', 'url': 'https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite.git', 'class_schema_sha256': '8391e679554eecd5d324a3e34a713ff240e619e3a07476587845ba18c9fae310', 'classes_used': ['VHS_VideoCombine'], 'pip_packages': [], 'status': 'discovered'}, 'rgthree-comfy': {'commit': '738105af5fb14e96fbecaf406dc356e284797e8c', 'url': 'https://github.com/rgthree/rgthree-comfy.git', 'class_schema_sha256': '2b52072e02c59cb05ce83e5c45e1c7fd5b1273fee9b62eaaa0e66a81a4c07872', 'classes_used': ['Fast Groups Bypasser (rgthree)', 'Power Lora Loader (rgthree)'], 'pip_packages': [], 'status': 'discovered'}},
    provenance={'source_path': '/Users/peteromalley/Documents/reigh-workspace/vibecomfy/workflow_corpus/custom_nodes/ltxvideo/runexx/LTX-2.3_V2V_Just_Talk_custom_audio_lipsync.json', 'source_id': 'LTX-2.3_V2V_Just_Talk_custom_audio_lipsync', 'source_type': 'api', 'source_workflow_path': '/Users/peteromalley/Documents/reigh-workspace/vibecomfy/workflow_corpus/custom_nodes/ltxvideo/runexx/LTX-2.3_V2V_Just_Talk_custom_audio_lipsync.json', 'output_mode': 'ready_template', 'ready_id': 'video/ltx2_3_runexx_lipsync_custom_audio'},
)

# === Subgraph functions ===

def prompt_enhancer(
    *,
    clip,
    image,
    prompt,
    switch: bool,
):
    """Prompt Enhancer - single-image variant.

    Materialized from subgraph e428c881-c48b-4849-9158-8311b4df27c7 in /Users/peteromalley/Documents/reigh-workspace/vibecomfy/workflow_corpus/custom_nodes/ltxvideo/runexx/LTX-2.3_V2V_Just_Talk_custom_audio_lipsync.json.
    # vibecomfy source hash: sha256:8649b8b5f790ee6c1785ff11ae08e22cb71074e69a0f2062bc30ce791ee3d900
    Inner nodes: TextGenerateLTX2Prompt, ComfySwitchNode, StringConcatenate.
    """

    stringconcatenate = StringConcatenate(
        _id='e428c881-c48b-4849-9158-8311b4df27c7:779',
        string_a='',
        string_b=prompt,
    )

    textgenerateltx2prompt = TextGenerateLTX2Prompt(
        _id='e428c881-c48b-4849-9158-8311b4df27c7:782',
        sampling_mode='off',
        thinking=True,
        prompt=stringconcatenate,
        clip=clip,
        image=image,
    )

    comfyswitchnode = ComfySwitchNode(
        _id='e428c881-c48b-4849-9158-8311b4df27c7:878',
        switch=switch,
        on_false=prompt,
        on_true=textgenerateltx2prompt,
    )

    return comfyswitchnode

def build() -> VibeWorkflow:
    """Build the workflow (auto-generated)."""
    wf = new_workflow(READY_METADATA, source_path=__file__)

    randomnoise = RandomNoise(
        noise_seed=DEFAULT_SEED_2,
        control_after_generate='randomize',
    )

    # Decode
    vaedecodetiled = VAEDecodeTiled(temporal_size=4096)

    # Sampling
    ksamplerselect = KSamplerSelect(sampler_name='euler_ancestral_cfg_pp')
    intconstant = INTConstant(value=3)
    randomnoise_2 = RandomNoise(noise_seed=DEFAULT_SEED, control_after_generate='fixed')
    ksamplerselect_2 = KSamplerSelect(sampler_name='euler_cfg_pp')

    # Loaders
    vaeloader = VAELoader(vae_name=VIDEO_VAE_NAME)

    latentupscalemodelloader = LatentUpscaleModelLoader(
        model_name=SPATIAL_UPSCALER_NAME,
    )

    dualcliploader = DualCLIPLoader(
        clip_name1=CLIP_NAME,
        clip_name2=CLIP_PROJECTION_NAME,
        type_='ltxv',
        device=DEFAULT,
    )

    vaeloaderkj = VAELoaderKJ(
        vae_name=AUDIO_VAE_NAME,
        device='main_device',
        weight_dtype='bf16',
    )

    vaeloader_2 = VAELoader(vae_name=VAE_TAESD_NAME)
    unetloader = UNETLoader(unet_name=UNET_NAME)
    unetloadergguf = UnetLoaderGGUF(unet_name=UNET_NAME_GGUF)

    dualcliploadergguf = DualCLIPLoaderGGUF(
        clip_name1=CLIP_NAME_GGUF,
        clip_name2=CLIP_PROJECTION_NAME,
        type_='sdxl',
    )

    manualsigmas = ManualSigmas(sigmas='0.85, 0.7250, 0.4219, 0.0')

    manualsigmas_2 = ManualSigmas(
        sigmas='1.0, 0.99375, 0.9875, 0.98125, 0.975, 0.909375, 0.725, 0.421875, 0.0',
    )

    intconstant_2 = INTConstant(value=650)
    fast_groups_bypasser__rgthree_ = raw_call('Fast Groups Bypasser (rgthree)', '515')
    _, comfy_int = ComfyMathExpression(expression='a', **{'values.a': 24.0})

    ltxavtextencoderloader = LTXAVTextEncoderLoader(
        text_encoder=CLIP_NAME,
        ckpt_name=CLIP_PROJECTION_NAME,
        device=DEFAULT,
    )

    image_load, _, _, video_info = VHS_LoadVideoFFmpeg(
        force_rate=24.0,
        format='LTXV',
        video='450x_auto__ (2).mp4',
        videopreview={'hidden': False, 'paused': False, 'params': {'filename': '450x_auto__ (2).mp4', 'type': 'input', 'format': 'video/mp4', 'force_rate': 0, 'custom_width': 0, 'custom_height': 0, 'frame_load_cap': 0, 'start_time': 0}},
    )

    fast_groups_bypasser__rgthree__2 = raw_call('Fast Groups Bypasser (rgthree)', '788')
    fast_groups_bypasser__rgthree__3 = raw_call('Fast Groups Bypasser (rgthree)', '819')
    loadaudio = LoadAudio(audio='e9318ca1-5e2b-47aa-8397-f4538b0151b0.wav')
    melbandroformermodelloader = raw_call('MelBandRoFormerModelLoader', '861', model=MEL_BAND_ROFORMER_NAME)

    # Conditioning
    negative = CLIPTextEncode(text=DEFAULT_PROMPT_2, clip=ltxavtextencoderloader)

    loraloadermodelonly = LoraLoaderModelOnly(
        lora_name=LORA_NAME,
        strength_model=GUIDE_STRENGTH,
        model=unetloader,
    )

    _, _, _, _, _, _, loaded_frame_count_, _, loaded_width_, loaded_height_ = VHS_VideoInfo(
        video_info=video_info,
    )

    resizeimagesbylongeredge_2 = ResizeImagesByLongerEdge(
        longer_edge=intconstant_2,
        images=image_load,
    )

    cliptextencode = CLIPTextEncode(text=DEFAULT_PROMPT, clip=ltxavtextencoderloader)

    _, _, calc_bool = SimpleCalculatorKJ(
        expression='(a > c) or (b > c) ',
        **{'variables.a': loaded_width_, 'variables.b': loaded_height_, 'variables.c': intconstant_2},
    )

    pathchsageattentionkj = PathchSageAttentionKJ(
        sage_attention='auto',
        model=loraloadermodelonly,
    )

    calc_float_simple, _, _ = SimpleCalculatorKJ(
        expression='(a/b)+c',
        **{'variables.b': 24.0, 'variables.a': loaded_frame_count_, 'variables.c': intconstant},
    )

    lazyswitchkj = LazySwitchKJ(
        switch=calc_bool,
        on_false=image_load,
        on_true=resizeimagesbylongeredge_2,
    )

    ltx2memoryefficientsageattentionpatch = LTX2MemoryEfficientSageAttentionPatch(
        model=pathchsageattentionkj,
    )

    trimaudioduration = TrimAudioDuration(duration=calc_float_simple, audio=loadaudio)
    image_get, width, height, _ = GetImageSizeAndCount(image=lazyswitchkj)

    ltxvchunkfeedforward = LTXVChunkFeedForward(
        model=ltx2memoryefficientsageattentionpatch,
    )

    melbandroformersampler = raw_call('MelBandRoFormerSampler', '860',
        audio=trimaudioduration,
        model=melbandroformermodelloader.out(0),
    )

    image_image, _, _, _ = ImageResizeKJv2(
        upscale_method='nearest-exact',
        keep_proportion='crop',
        divisible_by=64,
        device=CPU,
        width=width,
        height=height,
        image=image_get,
    )

    ltx2attentiontunerpatch = LTX2AttentionTunerPatch(model=ltxvchunkfeedforward)

    comfyswitchnode_2 = ComfySwitchNode(
        switch=True,
        on_false=trimaudioduration,
        on_true=melbandroformersampler.out(0),
    )

    resizeimagemasknode = ResizeImageMaskNode(
        resize_type=SCALE_BY_MULTIPLIER,
        input=image_image,
    )

    image, _ = GetImageRangeFromBatch(images=image_image)
    model, _ = Power_Lora_Loader_rgthree(model=ltx2attentiontunerpatch)
    _, width_get, height_get, count_get = GetImageSizeAndCount(image=image_image)

    resizeimagemasknode_3 = ResizeImageMaskNode(
        resize_type=SCALE_BY_MULTIPLIER,
        scale_method=NEAREST_EXACT,
        input=image_image,
    )

    ltxvaudiovaeencode = LTXVAudioVAEEncode(
        audio=comfyswitchnode_2,
        audio_vae=vaeloaderkj,
    )

    ltx2samplingpreviewoverride = raw_call('LTX2SamplingPreviewOverride', '368',
        preview_rate=19,
        model=model,
        vae=vaeloader_2,
    )

    resizeimagesbylongeredge = ResizeImagesByLongerEdge(longer_edge=1536, images=image)
    vaeencode = VAEEncode(pixels=resizeimagemasknode, vae=vaeloader)

    ltxvemptylatentaudio = LTXVEmptyLatentAudio(
        frames_number=count_get,
        frame_rate=comfy_int,
        audio_vae=vaeloaderkj,
    )

    comfy_float_comfy, _ = ComfyMathExpression(
        expression='a/b',
        **{'values.b': 24.0, 'values.a': count_get},
    )

    image_get_3, _ = GetImageRangeFromBatch(images=resizeimagemasknode_3)

    facesegment = raw_call('FaceSegment', '761',
        skin=True,
        nose=True,
        eyeglasses=False,
        left_eye=True,
        right_eye=True,
        left_eyebrow=True,
        right_eyebrow=True,
        left_ear=True,
        right_ear=True,
        mouth=True,
        upper_lip=True,
        lower_lip=True,
        hair=False,
        earring=False,
        neck=False,
        process_res=512,
        mask_blur=0,
        mask_offset=10,
        invert_output=False,
        background='Alpha',
        background_color='#222222',
        images=resizeimagemasknode_3,
    )

    image_get_5, _ = GetImageRangeFromBatch(start_index=-1, images=resizeimagemasknode)
    solidmask = SolidMask(value=0, width=width_get, height=height_get)
    ltxvpreprocess = LTXVPreprocess(img_compression=18, image=resizeimagesbylongeredge)
    modelsamplingsd3 = ModelSamplingSD3(shift=13, model=ltx2samplingpreviewoverride)

    ltx2_nag = LTX2_NAG(
        model=ltx2samplingpreviewoverride,
        nag_cond_audio=cliptextencode,
        nag_cond_video=negative,
    )

    comfy_float_comfy_2, _ = ComfyMathExpression(
        expression='a+b',
        **{'values.a': comfy_float_comfy, 'values.b': intconstant},
    )

    prompt_enhancer_result = prompt_enhancer(
        clip=ltxavtextencoderloader,
        image=resizeimagesbylongeredge,
        prompt='Cinematic video woman wearing colorful make-up, with colorful  light creating a creative scene. \n\nShe talks with perfect lip-sync movements to the attached audio. Her mouth and lips moves as she talks. \n \nThe camera slowly moves away from the woman, showing her full body. She is standing at a  colorful theatre scene doing a victorian era play. ',
        switch=False,
    )
    blockifymask = BlockifyMask(block_size=12, masks=facesegment.out(1))
    vaeencode_2 = VAEEncode(pixels=image_get_5, vae=vaeloader)
    setlatentnoisemask = SetLatentNoiseMask(mask=solidmask, samples=ltxvaudiovaeencode)

    basicscheduler = BasicScheduler(
        scheduler='linear_quadratic',
        steps=15,
        model=modelsamplingsd3,
    )

    positive = CLIPTextEncode(text=prompt_enhancer_result, clip=ltxavtextencoderloader)

    resizeimagemasknode_2 = ResizeImageMaskNode(
        resize_type='match size',
        scale_method=NEAREST_EXACT,
        input=blockifymask,
        **{'resize_type.match': image_get_3},
    )

    masktoimage = MaskToImage(mask=blockifymask)

    positive_ltxv, negative_ltxv = LTXVConditioning(
        frame_rate=24.0,
        negative=negative,
        positive=positive,
    )

    cfgguider_2 = CFGGuider(
        cfg=GUIDE_STRENGTH_3,
        model=ltx2_nag,
        negative=negative,
        positive=positive,
    )

    ltxvpreprocessmasks = LTXVPreprocessMasks(
        ignore_first_mask=False,
        masks=resizeimagemasknode_2,
        vae=vaeloader,
    )

    image_get_4, _ = GetImageRangeFromBatch(images=masktoimage)

    # Outputs
    previewimage = PreviewImage(images=image_get_4)

    ltxvsetvideolatentnoisemasks = LTXVSetVideoLatentNoiseMasks(
        masks=ltxvpreprocessmasks,
        samples=vaeencode,
    )

    video_latent_ltxv, audio_latent_ltxv = LTXVAudioVideoMask(
        video_fps=24.0,
        max_length='pad',
        video_start_time=comfy_float_comfy,
        video_end_time=comfy_float_comfy_2,
        audio_end_time=comfy_float_comfy_2,
        audio_latent=ltxvemptylatentaudio,
        video_latent=ltxvsetvideolatentnoisemasks,
    )

    positive_ltxv_2, negative_ltxv_2, latent = LTXVAddLatentGuide(
        strength=1.0,
        latent_idx=count_get,
        guiding_latent=vaeencode_2,
        latent=video_latent_ltxv,
        negative=negative_ltxv,
        positive=positive_ltxv,
        vae=vaeloader,
    )

    comfyswitchnode = ComfySwitchNode(
        switch=True,
        on_false=audio_latent_ltxv,
        on_true=setlatentnoisemask,
    )

    cfgguider = CFGGuider(
        cfg=GUIDE_STRENGTH_2,
        model=ltx2_nag,
        negative=negative_ltxv_2,
        positive=positive_ltxv_2,
    )

    ltxvimgtovideoinplace_2 = LTXVImgToVideoInplace(
        strength=0.7,
        image=resizeimagesbylongeredge,
        latent=latent,
        vae=vaeloader,
    )

    ltxvconcatavlatent = LTXVConcatAVLatent(
        audio_latent=comfyswitchnode,
        video_latent=ltxvimgtovideoinplace_2,
    )

    output, _ = SamplerCustomAdvanced(
        guider=cfgguider,
        latent_image=ltxvconcatavlatent,
        noise=randomnoise,
        sampler=ksamplerselect,
        sigmas=manualsigmas_2,
    )

    video_latent_ltxv_2, audio_latent_ltxv_2 = LTXVSeparateAVLatent(av_latent=output)

    _, _, latent_ltxv = LTXVCropGuides(
        latent=video_latent_ltxv_2,
        negative=negative_ltxv_2,
        positive=positive_ltxv_2,
    )

    ltxvlatentupsampler = LTXVLatentUpsampler(
        samples=latent_ltxv,
        upscale_model=latentupscalemodelloader,
        vae=vaeloader,
    )

    ltxvimgtovideoinplace = LTXVImgToVideoInplace(
        image=resizeimagesbylongeredge,
        latent=ltxvlatentupsampler,
        vae=vaeloader,
    )

    ltxvconcatavlatent_2 = LTXVConcatAVLatent(
        audio_latent=audio_latent_ltxv_2,
        video_latent=ltxvimgtovideoinplace,
    )

    output_sampler, _ = SamplerCustomAdvanced(
        guider=cfgguider_2,
        latent_image=ltxvconcatavlatent_2,
        noise=randomnoise_2,
        sampler=ksamplerselect_2,
        sigmas=manualsigmas,
    )

    video_latent, audio_latent = LTXVSeparateAVLatent(av_latent=output_sampler)
    ltxvaudiovaedecode = LTXVAudioVAEDecode(audio_vae=vaeloaderkj, samples=audio_latent)

    _, _, latent_ltxv_2 = LTXVCropGuides(
        latent=video_latent,
        negative=negative_ltxv_2,
        positive=positive_ltxv_2,
    )

    vaedecode = VAEDecode(samples=latent_ltxv_2, vae=vaeloader)

    vhs_videocombine = VHS_VideoCombine(
        frame_rate=24.0,
        filename_prefix='LTX-2',
        format='video/h264-mp4',
        save_output=False,
        crf=19,
        pix_fmt='yuv420p',
        save_metadata=True,
        trim_to_audio=False,
        videopreview={'hidden': False, 'paused': False, 'params': {'filename': 'LTX-2_00005-audio.mp4', 'subfolder': '', 'type': 'temp', 'format': 'video/h264-mp4', 'frame_rate': 24, 'workflow': 'LTX-2_00005.png', 'fullpath': 'C:\\Users\\runeg\\AppData\\Local\\Temp\\latentsync_72fd2bab\\LTX-2_00005-audio.mp4'}},
        audio=ltxvaudiovaedecode,
        images=vaedecode,
    )

    return wf.finalize(PUBLIC_INPUT_METADATA, output_node=vhs_videocombine, output_type='VHS_VideoCombine', name='video', artifact_kind='video', mime_type='video/mp4', expected_cardinality='one', filename_prefix='LTX-2')

