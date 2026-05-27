# vibecomfy: generated
# For hand-editing, run: python -m vibecomfy.cli copy-to-recipe <id>
"""Auto-generated ready_template — use python -m vibecomfy.cli copy-to-recipe <id> for hand-editing."""
from __future__ import annotations

from vibecomfy.templates import InputSpec, ReadyMetadata, new_workflow, node as raw_call
from vibecomfy.nodes.core import CFGGuider, CLIPTextEncode, ComfySwitchNode, DualCLIPLoader, EmptyLTXVLatentVideo, GetImageSize, KSamplerSelect, LTXVAudioVAEDecode, LTXVAudioVAEEncode, LTXVAudioVAELoader, LTXVConcatAVLatent, LTXVConditioning, LTXVEmptyLatentAudio, LTXVImgToVideoInplace, LTXVLatentUpsampler, LTXVPreprocess, LTXVScheduler, LTXVSeparateAVLatent, LatentUpscaleModelLoader, LoadAudio, LoadImage, LoraLoaderModelOnly, ManualSigmas, RandomNoise, ResizeImageMaskNode, ResizeImagesByLongerEdge, SamplerCustomAdvanced, SetLatentNoiseMask, SolidMask, StringConcatenate, TextGenerateLTX2Prompt, TrimAudioDuration, UNETLoader, VAEDecodeTiled, VAELoader
from vibecomfy.nodes.gguf import DualCLIPLoaderGGUF, UnetLoaderGGUF
from vibecomfy.nodes.kjnodes import INTConstant, ImageResizeKJv2, LTX2_NAG, LTXVChunkFeedForward, SimpleCalculatorKJ
from vibecomfy.nodes.rgthree import Power_Lora_Loader_rgthree
from vibecomfy.nodes.videohelpersuite import VHS_VideoCombine


AUDIO_VAE_NAME = 'LTX23_audio_vae_bf16_KJ.safetensors'
CLIP_NAME = 'gemma_3_12B_it_fp8_scaled.safetensors'
CLIP_NAME_GGUF = 'gemma-3-12b-it-Q2_K.gguf'
CLIP_PROJECTION_NAME = 'ltx-2.3_text_projection_bf16.safetensors'
DEFAULT_PROMPT = 'blurry, oversaturated, pixelated, low resolution, grainy, distorted, noise, compression artifacts, jpeg artifacts, glitches, watermark, text, logo, signature, copyright, subtitles, distorted sound, saturated sound, loud'
DEFAULT_PROMPT_2 = 'Make this image come alive with fluid motion. \n\nA man with an intimidating expression speaks with expressive body language and gesticulations. \n\nHe looks at the vewer and talks, he says  : "If you say a bad word about LTX 2 point 3, i will find you.... and i will kill you" '
DEFAULT_SEED = 420
DEFAULT_SEED_2 = 43
FIXED = 'fixed'
GUIDE_STRENGTH = 1
GUIDE_STRENGTH_2 = 0.6
LORA_NAME = 'LTX\\LTX-2\\ltx-2.3-22b-distilled-lora-384.safetensors'
MODEL_NAME = 'ltx-2.3-spatial-upscaler-x2-1.0.safetensors'
MODEL_NAME_2 = 'MelBandRoformer\\MelBandRoformer_fp16.safetensors'
UNET_NAME = 'LTXVideo\\v2\\ltx-2.3-22b-distilled_transformer_only_fp8_scaled.safetensors'
UNET_NAME_GGUF = 'LTXvideo\\LTX-2\\quantstack\\LTX-2.3-distilled-Q4_K_S.gguf'
VAE_TAESD_NAME = 'vae_approx\\taeltx2_3.safetensors'
VIDEO_VAE_NAME = 'LTX23_video_vae_bf16_KJ.safetensors'


PUBLIC_INPUT_METADATA = {
    'seed': InputSpec(node='114', field='noise_seed', default=DEFAULT_SEED, type='INT'),
    'image': InputSpec(node='167', field='image', default='liam-neeson-in-retribution-ra.jpg', type='IMAGE', required=True, aliases=('input_image',), media_semantics='image'),
    'prompt': InputSpec(node='110', field='text', default=DEFAULT_PROMPT, type='STRING', required=True, media_semantics='text'),
}

READY_METADATA = ReadyMetadata.build(
    capability='unknown',
    inputs=PUBLIC_INPUT_METADATA,
    requirements={'models': ['LTX23_video_vae_bf16_KJ.safetensors', 'LTXVideo\\v2\\ltx-2.3-22b-distilled_transformer_only_fp8_scaled.safetensors', 'LTX\\LTX-2\\ltx-2.3-22b-distilled-lora-384.safetensors', 'LTXvideo\\LTX-2\\quantstack\\LTX-2.3-distilled-Q4_K_S.gguf', 'euler_ancestral_cfg_pp', 'euler_cfg_pp', 'ltx-2.3-spatial-upscaler-x2-1.0.safetensors', 'vae_approx\\taeltx2_3.safetensors']},
    custom_node_packs={'ComfyUI-GGUF': {'commit': '6ea2651e7df66d7585f6ffee804b20e92fb38b8a', 'url': 'https://github.com/city96/ComfyUI-GGUF.git', 'class_schema_sha256': '1336fad984841444a9559b602c34ef11d1dd4b68a9a902437aaee6771ab5d2d3', 'classes_used': ['DualCLIPLoaderGGUF', 'UnetLoaderGGUF'], 'pip_packages': ['gguf'], 'status': 'discovered'}, 'ComfyUI-KJNodes': {'commit': 'b7646ad70a7daa7aeb919ca542274758d26ba2df', 'url': 'https://github.com/kijai/ComfyUI-KJNodes.git', 'class_schema_sha256': '1beaf129c8fa26175d89a28f9ca10d08b5ac27c8fc9bff920263fcbba17cb691', 'classes_used': ['GetImageSize', 'INTConstant', 'ImageResizeKJv2', 'ResizeImagesByLongerEdge', 'SimpleCalculatorKJ'], 'pip_packages': ['matplotlib'], 'status': 'discovered'}, 'ComfyUI-LTXVideo': {'commit': '229437c6b65796d6a7a63ae34be2bd5ba31fa543', 'url': 'https://github.com/Lightricks/ComfyUI-LTXVideo.git', 'class_schema_sha256': '82e0b1f31509a969cf441c45e2517d0cd93f31b5390cc16f4a0ffa244421f39e', 'classes_used': ['EmptyLTXVLatentVideo', 'LTX2_NAG', 'LTXVAudioVAEDecode', 'LTXVAudioVAELoader', 'LTXVChunkFeedForward', 'LTXVConcatAVLatent', 'LTXVConditioning', 'LTXVEmptyLatentAudio', 'LTXVPreprocess', 'LTXVScheduler', 'LTXVSeparateAVLatent', 'LatentUpscaleModelLoader'], 'pip_packages': [], 'status': 'discovered'}, 'ComfyUI-VideoHelperSuite': {'commit': '4ee72c065db22c9d96c2427954dc69e7b908444b', 'url': 'https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite.git', 'class_schema_sha256': '8391e679554eecd5d324a3e34a713ff240e619e3a07476587845ba18c9fae310', 'classes_used': ['VHS_VideoCombine'], 'pip_packages': [], 'status': 'discovered'}, 'rgthree-comfy': {'commit': '738105af5fb14e96fbecaf406dc356e284797e8c', 'url': 'https://github.com/rgthree/rgthree-comfy.git', 'class_schema_sha256': '2b52072e02c59cb05ce83e5c45e1c7fd5b1273fee9b62eaaa0e66a81a4c07872', 'classes_used': ['Fast Groups Bypasser (rgthree)', 'Power Lora Loader (rgthree)'], 'pip_packages': [], 'status': 'discovered'}},
    provenance={'source_path': '/Users/peteromalley/Documents/reigh-workspace/vibecomfy/workflow_corpus/custom_nodes/ltxvideo/runexx/LTX-2.3_Custom_Audio.json', 'source_id': 'LTX-2.3_Custom_Audio', 'source_type': 'api', 'source_workflow_path': '/Users/peteromalley/Documents/reigh-workspace/vibecomfy/workflow_corpus/custom_nodes/ltxvideo/runexx/LTX-2.3_Custom_Audio.json', 'output_mode': 'ready_template', 'ready_id': 'video/ltx2_3_runexx_custom_audio'},
)

def build() -> VibeWorkflow:
    """Build the workflow (auto-generated)."""
    wf = new_workflow(READY_METADATA, source_path=__file__)

    manualsigmas = ManualSigmas(sigmas='0.909375, 0.725, 0.421875, 0.0')
    randomnoise = RandomNoise(noise_seed=DEFAULT_SEED, control_after_generate=FIXED)
    randomnoise_2 = RandomNoise(noise_seed=DEFAULT_SEED_2, control_after_generate=FIXED)

    # Sampling
    ksamplerselect = KSamplerSelect(sampler_name='euler_ancestral_cfg_pp')
    ksamplerselect_2 = KSamplerSelect(sampler_name='euler_cfg_pp')

    # Inputs
    image_load, mask_load = LoadImage(image='liam-neeson-in-retribution-ra.jpg')

    # Loaders
    vaeloader = VAELoader(vae_name=VIDEO_VAE_NAME)
    latentupscalemodelloader = LatentUpscaleModelLoader(model_name=MODEL_NAME)

    dualcliploader = DualCLIPLoader(
        clip_name1=CLIP_NAME,
        clip_name2=CLIP_PROJECTION_NAME,
        type_='ltxv',
        device='default',
    )

    ltxvaudiovaeloader = LTXVAudioVAELoader(ckpt_name=AUDIO_VAE_NAME)
    intconstant = INTConstant(value=10)
    intconstant_2 = INTConstant(value=1280)
    intconstant_3 = INTConstant(value=736)

    calc_float_simple, calc_int_simple, calc_bool_simple = SimpleCalculatorKJ(
        expression='a',
        **{'variables.a': 24.0},
    )

    unetloader = UNETLoader(unet_name=UNET_NAME)
    vaeloader_2 = VAELoader(vae_name=VAE_TAESD_NAME)
    unetloadergguf = UnetLoaderGGUF(unet_name=UNET_NAME_GGUF)

    dualcliploadergguf = DualCLIPLoaderGGUF(
        clip_name1=CLIP_NAME_GGUF,
        clip_name2=CLIP_PROJECTION_NAME,
        type_='sdxl',
    )

    stringconcatenate = StringConcatenate(
        string_a='You are a Creative Assistant writing concise, action-focused image-to-video prompts. Given an image (first frame) and user Raw Input Prompt, generate a prompt to guide video generation from that image.\n\n#### Guidelines:\n- Analyze the Image: Identify Subject, Setting, Elements, Style and Mood.\n- Follow user Raw Input Prompt: Include all requested motion, actions, camera movements, audio, and details. If in conflict with the image, prioritize user request while maintaining visual consistency (describe transition from image to user\'s scene).\n- Describe only changes from the image: Don\'t reiterate established visual details. Inaccurate descriptions may cause scene cuts.\n- Active language: Use present-progressive verbs ("is walking," "speaking"). If no action specified, describe natural movements.\n- Chronological flow: Use temporal connectors ("as," "then," "while").\n- Audio layer: Describe complete soundscape throughout the prompt alongside actions—NOT at the end. Align audio intensity with action tempo. Include natural background audio, ambient sounds, effects, speech or music (when requested). Be specific (e.g., "soft footsteps on tile") not vague (e.g., "ambient sound").\n- Speech (only when requested): Provide exact words in quotes with character\'s visual/voice characteristics (e.g., "The tall man speaks in a low, gravelly voice"), language if not English and accent if relevant. If general conversation mentioned without text, generate contextual quoted dialogue. (i.e., "The man is talking" input -> the output should include exact spoken words, like: "The man is talking in an excited voice saying: \'You won\'t believe what I just saw!\' His hands gesture expressively as he speaks, eyebrows raised with enthusiasm. The ambient sound of a quiet room underscores his animated speech.")\n- Style: Include visual style at beginning: "Style: <style>, <rest of prompt>." If unclear, omit to avoid conflicts.\n- Visual and audio only: Describe only what is seen and heard. NO smell, taste, or tactile sensations.\n- Restrained language: Avoid dramatic terms. Use mild, natural, understated phrasing.\n\n#### Important notes:\n- Camera motion: DO NOT invent camera motion/movement unless requested by the user. Make sure to include camera motion only if specified in the input.\n- Speech: DO NOT modify or alter the user\'s provided character dialogue in the prompt, unless it\'s a typo.\n- No timestamps or cuts: DO NOT use timestamps or describe scene cuts unless explicitly requested.\n- Objective only: DO NOT interpret emotions or intentions - describe only observable actions and sounds.\n- Format: DO NOT use phrases like "The scene opens with..." / "The video starts...". Start directly with Style (optional) and chronological scene description.\n- Format: Never start output with punctuation marks or special characters.\n- DO NOT invent dialogue unless the user mentions speech/talking/singing/conversation.\n- Your performance is CRITICAL. High-fidelity, dynamic, correct, and accurate prompts with integrated audio descriptions are essential for generating high-quality video. Your goal is flawless execution of these rules.\n\n#### Output Format (Strict):\n- Single concise paragraph in natural English. NO titles, headings, prefaces, sections, code fences, or Markdown.\n- If unsafe/invalid, return original user prompt. Never ask questions or clarifications.\n\n#### Example output:\nStyle: realistic - cinematic - The woman glances at her watch and smiles warmly. She speaks in a cheerful, friendly voice, "I think we\'re right on time!" In the background, a café barista prepares drinks at the counter. The barista calls out in a clear, upbeat tone, "Two cappuccinos ready!" The sound of the espresso machine hissing softly blends with gentle background chatter and the light clinking of cups on saucers. \n\nUSER PROMPT BELOW: \n___________________________________________________',
        string_b='',
    )

    fast_groups_bypasser__rgthree_ = raw_call('Fast Groups Bypasser (rgthree)', '354')
    melbandroformermodelloader = raw_call('MelBandRoFormerModelLoader', '370', model=MODEL_NAME_2)
    loadaudio = LoadAudio(audio='ComfyUI_00128_.mp3')
    manualsigmas_2 = ManualSigmas(sigmas='0.85, 0.7250, 0.4219, 0.0')

    manualsigmas_3 = ManualSigmas(
        sigmas='1.0, 0.99375, 0.9875, 0.98125, 0.975, 0.909375, 0.725, 0.421875, 0.0',
    )

    # Conditioning
    cliptextencode = CLIPTextEncode(text=DEFAULT_PROMPT, clip=dualcliploader)

    loraloadermodelonly = LoraLoaderModelOnly(
        lora_name=LORA_NAME,
        strength_model=GUIDE_STRENGTH_2,
        model=unetloader,
    )

    image, width_image, height_image, mask = ImageResizeKJv2(
        upscale_method='nearest-exact',
        keep_proportion='crop',
        divisible_by=32,
        device='cpu',
        width=intconstant_2,
        height=intconstant_3,
        image=image_load,
    )

    calc_float, calc_int, calc_bool = SimpleCalculatorKJ(
        expression='1+ 8*(round(a*b)/8)',
        b=24.0,
        a=intconstant,
    )

    solidmask = SolidMask(value=0, width=intconstant_2, height=intconstant_3)

    resizeimagemasknode = ResizeImageMaskNode(
        resize_type='scale by multiplier',
        input=image,
    )

    ltxvemptylatentaudio = LTXVEmptyLatentAudio(
        frames_number=calc_int,
        frame_rate=calc_int_simple,
        audio_vae=ltxvaudiovaeloader,
    )

    resizeimagesbylongeredge = ResizeImagesByLongerEdge(longer_edge=1536, images=image)
    ltxvchunkfeedforward = LTXVChunkFeedForward(model=loraloadermodelonly)

    textgenerateltx2prompt = TextGenerateLTX2Prompt(
        prompt=DEFAULT_PROMPT_2,
        sampling_mode='off',
        clip=dualcliploader,
        image=image,
    )

    calc_float_simple_2, calc_int_simple_2, calc_bool_simple_2 = SimpleCalculatorKJ(
        expression='a/b',
        b=24.0,
        a=calc_int,
    )

    cliptextencode_2 = CLIPTextEncode(text=textgenerateltx2prompt, clip=dualcliploader)
    ltxvpreprocess = LTXVPreprocess(img_compression=33, image=resizeimagesbylongeredge)
    width, height, batch_size = GetImageSize(image=resizeimagemasknode)
    model, clip = Power_Lora_Loader_rgthree(model=ltxvchunkfeedforward)
    easy_showanything = raw_call('easy showAnything', '351', anything=textgenerateltx2prompt)
    trimaudioduration = TrimAudioDuration(duration=calc_float_simple_2, audio=loadaudio)

    positive, negative = LTXVConditioning(
        frame_rate=24.0,
        negative=cliptextencode,
        positive=cliptextencode_2,
    )

    emptyltxvlatentvideo = EmptyLTXVLatentVideo(
        width=width,
        height=height,
        length=calc_int,
    )

    ltx2samplingpreviewoverride = raw_call('LTX2SamplingPreviewOverride', '337', model=model, vae=vaeloader_2)

    melbandroformersampler = raw_call('MelBandRoFormerSampler', '371',
        audio=trimaudioduration,
        model=melbandroformermodelloader.out(0),
    )

    ltxvimgtovideoinplace_2 = LTXVImgToVideoInplace(
        image=ltxvpreprocess,
        latent=emptyltxvlatentvideo,
        vae=vaeloader,
    )

    ltx2_nag = LTX2_NAG(
        model=ltx2samplingpreviewoverride,
        nag_cond_audio=negative,
        nag_cond_video=negative,
    )

    comfyswitchnode_2 = ComfySwitchNode(
        switch=False,
        on_false=trimaudioduration,
        on_true=melbandroformersampler.out(0),
    )

    cfgguider = CFGGuider(
        cfg=GUIDE_STRENGTH,
        model=ltx2_nag,
        negative=negative,
        positive=positive,
    )

    cfgguider_2 = CFGGuider(
        cfg=GUIDE_STRENGTH,
        model=ltx2_nag,
        negative=negative,
        positive=positive,
    )

    ltxvaudiovaeencode = LTXVAudioVAEEncode(
        audio=comfyswitchnode_2,
        audio_vae=ltxvaudiovaeloader,
    )

    setlatentnoisemask = SetLatentNoiseMask(mask=solidmask, samples=ltxvaudiovaeencode)

    comfyswitchnode = ComfySwitchNode(
        switch=True,
        on_false=ltxvemptylatentaudio,
        on_true=setlatentnoisemask,
    )

    ltxvconcatavlatent = LTXVConcatAVLatent(
        audio_latent=comfyswitchnode,
        video_latent=ltxvimgtovideoinplace_2,
    )

    output, denoised_output = SamplerCustomAdvanced(
        guider=cfgguider_2,
        latent_image=ltxvconcatavlatent,
        noise=randomnoise_2,
        sampler=ksamplerselect,
        sigmas=manualsigmas_3,
    )

    ltxvscheduler = LTXVScheduler(steps=8, latent=ltxvconcatavlatent)
    video_latent, audio_latent = LTXVSeparateAVLatent(av_latent=output)

    ltxvlatentupsampler = LTXVLatentUpsampler(
        samples=video_latent,
        upscale_model=latentupscalemodelloader,
        vae=vaeloader,
    )

    ltxvimgtovideoinplace = LTXVImgToVideoInplace(
        image=resizeimagesbylongeredge,
        latent=ltxvlatentupsampler,
        vae=vaeloader,
    )

    ltxvconcatavlatent_2 = LTXVConcatAVLatent(
        audio_latent=audio_latent,
        video_latent=ltxvimgtovideoinplace,
    )

    output_sampler, denoised_output_sampler = SamplerCustomAdvanced(
        guider=cfgguider,
        latent_image=ltxvconcatavlatent_2,
        noise=randomnoise,
        sampler=ksamplerselect_2,
        sigmas=manualsigmas_2,
    )

    video_latent_ltxv, audio_latent_ltxv = LTXVSeparateAVLatent(
        av_latent=output_sampler,
    )

    # Decode
    vaedecodetiled = VAEDecodeTiled(
        temporal_size=4096,
        samples=video_latent_ltxv,
        vae=vaeloader,
    )

    ltxvaudiovaedecode = LTXVAudioVAEDecode(
        audio_vae=ltxvaudiovaeloader,
        samples=audio_latent_ltxv,
    )

    # Outputs
    vhs_videocombine = VHS_VideoCombine(
        frame_rate=24.0,
        filename_prefix='LTX-2',
        format='video/h264-mp4',
        crf=19,
        pix_fmt='yuv420p',
        save_metadata=True,
        trim_to_audio=False,
        videopreview={'hidden': False, 'paused': False, 'params': {'filename': 'LTX-2_00796-audio.mp4', 'subfolder': '', 'type': 'output', 'format': 'video/h264-mp4', 'frame_rate': 24, 'workflow': 'LTX-2_00796.png', 'fullpath': 'E:\\AI\\ComfyUI\\output\\LTX-2_00796-audio.mp4'}},
        audio=trimaudioduration,
        images=vaedecodetiled,
    )

    return wf.finalize(PUBLIC_INPUT_METADATA, output_node=vhs_videocombine, output_type='VHS_VideoCombine', name='video', artifact_kind='video', mime_type='video/mp4', expected_cardinality='one', filename_prefix='LTX-2')

