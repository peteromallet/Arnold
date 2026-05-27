# vibecomfy: generated
# For hand-editing, run: python -m vibecomfy.cli copy-to-recipe <id>
"""Auto-generated ready_template — use python -m vibecomfy.cli copy-to-recipe <id> for hand-editing."""
from __future__ import annotations

from vibecomfy.templates import InputSpec, ReadyMetadata, new_workflow, node as raw_call
from vibecomfy.nodes.core import CFGGuider, CLIPTextEncode, CheckpointLoaderSimple, CreateVideo, EmptyLTXVLatentVideo, GetImageSize, GetVideoComponents, KSamplerSelect, LTXAVTextEncoderLoader, LTXVAudioVAEDecode, LTXVAudioVAELoader, LTXVConcatAVLatent, LTXVConditioning, LTXVCropGuides, LTXVEmptyLatentAudio, LTXVSeparateAVLatent, LoadImage, LoadVideo, LoraLoaderModelOnly, ManualSigmas, RandomNoise, ResizeImageMaskNode, SamplerCustomAdvanced, SaveVideo, SimpleMath
from vibecomfy.nodes.ltxvideo import GemmaAPITextEncode, LTXAddVideoICLoRAGuide, LTXFloatToInt, LTXICLoRALoaderModelOnly, LTXVImgToVideoConditionOnly, LTXVTiledVAEDecode


BBOX_DETECTOR_NAME = 'yolox_l.onnx'
CKPT_NAME = 'ltx-2.3-22b-dev.safetensors'
DEFAULT_PROMPT = 'pc game, console game, video game, cartoon, childish, ugly'
DEFAULT_PROMPT_2 = 'Apocalyptic landscape with abandoned buildings, overgrown with foliage and trees. The sky is clear and the sun is setting, with the horizon turning bright red. The buildings are delapidated, falling apart and crumbling due to being abandoned for so long.\nThe air is full of silence and the only thing to be heard is a young girl breathing and saying: "Where is everyone?"'
DEFAULT_SEED = 42
ENHANCE_PROMPT_NAME = 'ltx-2.3-22b-dev.safetensors'
GUIDE_STRENGTH = 1
GUIDE_STRENGTH_2 = 0.5
LANCZOS = 'lanczos'
LORA_NAME = 'ltxv/ltx2/ltx-2.3-22b-ic-lora-union-control-ref0.5.safetensors'
LORA_NAME_2 = 'ltxv/ltx2/ltx-2.3-22b-distilled-lora-384-1.1.safetensors'
POSE_ESTIMATOR_NAME = 'dw-ll_ucoco_384_bs5.torchscript.pt'
TEXT_ENCODER_NAME = 'comfy_gemma_3_12B_it.safetensors'
VALUE = ''
WIDGET__NAME = 'video_depth_anything_vits.pth'


PUBLIC_INPUT_METADATA = {
    'image': InputSpec(node='2004', field='image', default='example.png', type='IMAGE', required=True, aliases=('input_image',), media_semantics='image'),
    'seed': InputSpec(node='4832', field='noise_seed', default=DEFAULT_SEED, type='INT'),
    'prompt': InputSpec(node='2483', field='text', default=DEFAULT_PROMPT_2, type='STRING', required=True, media_semantics='text'),
    'negative_prompt': InputSpec(node='2612', field='text', default=DEFAULT_PROMPT, type='STRING', aliases=('negative',), media_semantics='text'),
}

READY_METADATA = ReadyMetadata.build(
    capability='unknown',
    inputs=PUBLIC_INPUT_METADATA,
    requirements={'models': ['euler_ancestral_cfg_pp', 'ltx-2.3-22b-dev.safetensors', 'ltxv/ltx2/ltx-2.3-22b-distilled-lora-384-1.1.safetensors', 'ltxv/ltx2/ltx-2.3-22b-ic-lora-union-control-ref0.5.safetensors']},
    custom_node_packs={'ComfyUI-DepthAnythingV2': {'commit': '553187872eeb1d52e50dc53209fa57e569609a72', 'url': 'https://github.com/kijai/ComfyUI-DepthAnythingV2.git', 'class_schema_sha256': 'f4e181ab42ca179eda161acba5121e999cb54b1dbee0dc087a22bd42af7241ae', 'classes_used': ['LoadVideoDepthAnythingModel', 'VideoDepthAnythingOutput', 'VideoDepthAnythingProcess'], 'pip_packages': ['opencv-python-headless', 'transformers'], 'status': 'discovered'}, 'ComfyUI-KJNodes': {'commit': 'b7646ad70a7daa7aeb919ca542274758d26ba2df', 'url': 'https://github.com/kijai/ComfyUI-KJNodes.git', 'class_schema_sha256': '1beaf129c8fa26175d89a28f9ca10d08b5ac27c8fc9bff920263fcbba17cb691', 'classes_used': ['GetImageSize'], 'pip_packages': ['matplotlib'], 'status': 'discovered'}, 'ComfyUI-LTXVideo': {'commit': '229437c6b65796d6a7a63ae34be2bd5ba31fa543', 'url': 'https://github.com/Lightricks/ComfyUI-LTXVideo.git', 'class_schema_sha256': '82e0b1f31509a969cf441c45e2517d0cd93f31b5390cc16f4a0ffa244421f39e', 'classes_used': ['EmptyLTXVLatentVideo', 'LTXAVTextEncoderLoader', 'LTXVAudioVAEDecode', 'LTXVAudioVAELoader', 'LTXVConcatAVLatent', 'LTXVConditioning', 'LTXVCropGuides', 'LTXVEmptyLatentAudio', 'LTXVSeparateAVLatent'], 'pip_packages': [], 'status': 'discovered'}, 'comfyui_controlnet_aux': {'commit': 'e8b689a513c3e6b63edc44066560ca5919c0576e', 'url': 'https://github.com/Fannovel16/comfyui_controlnet_aux.git', 'class_schema_sha256': 'e485b148824d72ef7af7e90f711eefb511ffe73b25cd1c6053e1e5c7bd3bbd62', 'classes_used': ['CannyEdgePreprocessor', 'DWPreprocessor'], 'pip_packages': ['onnxruntime', 'opencv-python-headless'], 'status': 'discovered'}},
    provenance={'source_path': '/Users/peteromalley/Documents/reigh-workspace/vibecomfy/workflow_corpus/custom_nodes/ltxvideo/lightricks_2_3/LTX-2.3_ICLoRA_Union_Control_Distilled.json', 'source_id': 'LTX-2.3_ICLoRA_Union_Control_Distilled', 'source_type': 'api', 'source_workflow_path': '/Users/peteromalley/Documents/reigh-workspace/vibecomfy/workflow_corpus/custom_nodes/ltxvideo/lightricks_2_3/LTX-2.3_ICLoRA_Union_Control_Distilled.json', 'output_mode': 'ready_template', 'ready_id': 'video/ltx2_3_lightricks_iclora_union_control'},
)

def build() -> VibeWorkflow:
    """Build the workflow (auto-generated)."""
    wf = new_workflow(READY_METADATA, source_path=__file__)

    # Inputs
    image, mask = LoadImage(image='example.png')

    # Loaders
    model, clip, vae = CheckpointLoaderSimple(ckpt_name=CKPT_NAME)
    ltxvaudiovaeloader = LTXVAudioVAELoader(ckpt_name=CKPT_NAME)

    # Sampling
    ksamplerselect = KSamplerSelect(sampler_name='euler_ancestral_cfg_pp')
    randomnoise = RandomNoise(noise_seed=DEFAULT_SEED, control_after_generate='fixed')
    loadvideo = LoadVideo(file='buildings.mp4')

    gemmaapitextencode = GemmaAPITextEncode(
        ckpt_name=CKPT_NAME,
        enhance_prompt=False,
        prompt=DEFAULT_PROMPT,
        widget_0='',
    )

    gemmaapitextencode_2 = GemmaAPITextEncode(
        ckpt_name=CKPT_NAME,
        enhance_prompt=ENHANCE_PROMPT_NAME,
        widget_0='',
    )

    ltxavtextencoderloader = LTXAVTextEncoderLoader(
        text_encoder=TEXT_ENCODER_NAME,
        ckpt_name=CKPT_NAME,
        device='default',
    )

    manualsigmas = ManualSigmas(
        sigmas='1.0, 0.99375, 0.9875, 0.98125, 0.975, 0.909375, 0.725, 0.421875, 0.0',
    )

    loadvideodepthanythingmodel = raw_call('LoadVideoDepthAnythingModel', '5060', widget_0=WIDGET__NAME)

    # Conditioning
    cliptextencode = CLIPTextEncode(text=DEFAULT_PROMPT_2, clip=ltxavtextencoderloader)
    cliptextencode_2 = CLIPTextEncode(text=DEFAULT_PROMPT, clip=ltxavtextencoderloader)

    loraloadermodelonly = LoraLoaderModelOnly(
        lora_name=LORA_NAME_2,
        strength_model=GUIDE_STRENGTH_2,
        model=model,
    )

    images, audio, fps = GetVideoComponents(video=loadvideo)

    resizeimagemasknode_3 = ResizeImageMaskNode(
        resize_type='scale longer dimension',
        scale_method=LANCZOS,
        input=image,
    )

    positive, negative = LTXVConditioning(
        frame_rate=fps,
        negative=cliptextencode_2,
        positive=cliptextencode,
    )

    model_ltxic, latent_downscale_factor = LTXICLoRALoaderModelOnly(
        lora_name=LORA_NAME,
        model=loraloadermodelonly,
    )

    resizeimagemasknode = ResizeImageMaskNode(
        resize_type='scale shorter dimension',
        scale_method=LANCZOS,
        input=images,
    )

    ltxfloattoint = LTXFloatToInt(rounding=0, a=fps)

    dwpreprocessor = raw_call('DWPreprocessor', '4986',
        detect_hand='enable',
        detect_body='enable',
        detect_face='enable',
        bbox_detector=BBOX_DETECTOR_NAME,
        pose_estimator=POSE_ESTIMATOR_NAME,
        scale_stick_for_xinsr_cn='disable',
        image=resizeimagemasknode,
    )

    cannyedgepreprocessor = raw_call('CannyEdgePreprocessor', '4991', low_threshold=92, image=resizeimagemasknode)
    int, float = SimpleMath(value='a*32', a=latent_downscale_factor)

    videodepthanythingprocess = raw_call('VideoDepthAnythingProcess', '5061',
        widget_0=518,
        widget_1=960,
        widget_2='fp32',
        images=resizeimagemasknode,
        vda_model=loadvideodepthanythingmodel.out(0),
    )

    resizeimagemasknode_2 = ResizeImageMaskNode(
        resize_type='scale to multiple',
        scale_method=LANCZOS,
        input=cannyedgepreprocessor,
        **{'resize_type.multiple': int},
    )

    videodepthanythingoutput = raw_call('VideoDepthAnythingOutput', '5062',
        widget_0='gray',
        depths=videodepthanythingprocess.out(0),
    )

    width, height, batch_size = GetImageSize(image=resizeimagemasknode_2)

    emptyltxvlatentvideo = EmptyLTXVLatentVideo(
        width=width,
        height=height,
        length=batch_size,
    )

    ltxvemptylatentaudio = LTXVEmptyLatentAudio(
        frames_number=batch_size,
        frame_rate=ltxfloattoint,
        audio_vae=ltxvaudiovaeloader,
    )

    ltxvimgtovideoconditiononly = LTXVImgToVideoConditionOnly(
        bypass=True,
        image=resizeimagemasknode_3,
        latent=emptyltxvlatentvideo,
        vae=vae,
    )

    positive_ltx, negative_ltx, latent = LTXAddVideoICLoRAGuide(
        crop=1,
        use_tiled_encode='disabled',
        image=resizeimagemasknode_2,
        latent=ltxvimgtovideoconditiononly,
        latent_downscale_factor=latent_downscale_factor,
        negative=negative,
        positive=positive,
        vae=vae,
    )

    ltxvconcatavlatent = LTXVConcatAVLatent(
        audio_latent=ltxvemptylatentaudio,
        video_latent=latent,
    )

    cfgguider = CFGGuider(
        cfg=GUIDE_STRENGTH,
        model=model_ltxic,
        negative=negative_ltx,
        positive=positive_ltx,
    )

    output, denoised_output = SamplerCustomAdvanced(
        guider=cfgguider,
        latent_image=ltxvconcatavlatent,
        noise=randomnoise,
        sampler=ksamplerselect,
        sigmas=manualsigmas,
    )

    video_latent, audio_latent = LTXVSeparateAVLatent(av_latent=output)

    ltxvaudiovaedecode = LTXVAudioVAEDecode(
        audio_vae=ltxvaudiovaeloader,
        samples=audio_latent,
    )

    positive_ltxv, negative_ltxv, latent_ltxv = LTXVCropGuides(
        latent=video_latent,
        negative=negative_ltx,
        positive=positive_ltx,
    )

    ltxvtiledvaedecode = LTXVTiledVAEDecode(
        horizontal_tiles=2,
        vertical_tiles=2,
        overlap=6,
        latents=latent_ltxv,
        vae=vae,
    )

    createvideo = CreateVideo(
        fps=fps,
        audio=ltxvaudiovaedecode,
        images=ltxvtiledvaedecode,
    )

    # Outputs
    savevideo = SaveVideo(filename_prefix='output', video=createvideo)

    return wf.finalize(PUBLIC_INPUT_METADATA, output_node=savevideo, output_type='SaveVideo', name='video', artifact_kind='video', mime_type='video/mp4', expected_cardinality='one', filename_prefix='output')

