# vibecomfy: generated
# For hand-editing, run: python -m vibecomfy.cli copy-to-recipe <id>
"""Auto-generated ready_template — use python -m vibecomfy.cli copy-to-recipe <id> for hand-editing."""
from __future__ import annotations

from vibecomfy.templates import InputSpec, ReadyMetadata, new_workflow, node as raw_call
from vibecomfy.nodes.core import CLIPVisionLoader, GetImageRangeFromBatch, LoadAudio
from vibecomfy.nodes.kjnodes import GetImageSizeAndCount, INTConstant, ImageConcatMulti, ImageResizeKJv2
from vibecomfy.nodes.videohelpersuite import VHS_LoadVideo, VHS_VideoCombine
from vibecomfy.nodes.wanvideowrapper import DownloadAndLoadWav2VecModel, MultiTalkModelLoader, MultiTalkWav2VecEmbeds, WanVideoBlockSwap, WanVideoClipVisionEncode, WanVideoDecode, WanVideoEncode, WanVideoImageToVideoMultiTalk, WanVideoLoraSelect, WanVideoModelLoader, WanVideoSampler, WanVideoTextEncodeCached, WanVideoTorchCompileSettings, WanVideoVAELoader, Wav2VecModelLoader


BF16 = 'bf16'
CLIP_NAME = 'clip_vision_h.safetensors'
CLIP_NAME_2 = 'umt5-xxl-enc-bf16.safetensors'
DEFAULT_FRAMES = 1
DEFAULT_NEGATIVE = 'bright tones, overexposed, static, blurred details, subtitles, style, works, paintings, images, static, overall gray, worst quality, low quality, JPEG compression residue, ugly, incomplete, extra fingers, poorly drawn hands, poorly drawn faces, deformed, disfigured, misshapen limbs, fused fingers, still picture, messy background, three legs, many people in the background, walking backwards'
DEFAULT_SEED = 2
DISABLED = 'disabled'
FP16 = 'fp16'
GUIDE_STRENGTH = 1.0000000000000002
LORA_NAME = 'WanVideo\\Lightx2v\\lightx2v_I2V_14B_480p_cfg_step_distill_rank64_bf16.safetensors'
MAIN_DEVICE = 'main_device'
MEL_BAND_ROFORMER_NAME = 'MelBandRoFormer\\MelBandRoformer_fp16.safetensors'
MODEL_NAME = 'WanVideo\\InfiniteTalk\\InfiniteTalk\\Wan2_1-InfiniteTalk_Single_Q8.gguf'
MODEL_NAME_2 = 'WanVideo\\wan2.1-i2v-14b-480p-Q8_0.gguf'
MODEL_NAME_3 = 'wav2vec2-chinese-base_fp16.safetensors'
MODEL_NAME_4 = 'TencentGameMate/chinese-wav2vec2-base'
VAE_NAME = 'wanvideo\\Wan2_1_VAE_bf16.safetensors'


PUBLIC_INPUT_METADATA = {
    'seed': InputSpec(node='128', field='seed', default=DEFAULT_SEED, type='INT'),
}

READY_METADATA = ReadyMetadata.build(
    capability='unknown',
    inputs=PUBLIC_INPUT_METADATA,
    requirements={'models': ['clip_vision_h.safetensors', 'umt5-xxl-enc-bf16.safetensors', 'wanvideo\\Wan2_1_VAE_bf16.safetensors']},
    custom_node_packs={'ComfyUI-KJNodes': {'commit': 'b7646ad70a7daa7aeb919ca542274758d26ba2df', 'url': 'https://github.com/kijai/ComfyUI-KJNodes.git', 'class_schema_sha256': '1beaf129c8fa26175d89a28f9ca10d08b5ac27c8fc9bff920263fcbba17cb691', 'classes_used': ['GetImageRangeFromBatch', 'GetImageSizeAndCount', 'INTConstant', 'ImageResizeKJv2'], 'pip_packages': ['matplotlib'], 'status': 'discovered'}, 'ComfyUI-VideoHelperSuite': {'commit': '4ee72c065db22c9d96c2427954dc69e7b908444b', 'url': 'https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite.git', 'class_schema_sha256': '8391e679554eecd5d324a3e34a713ff240e619e3a07476587845ba18c9fae310', 'classes_used': ['VHS_LoadVideo', 'VHS_VideoCombine'], 'pip_packages': [], 'status': 'discovered'}, 'ComfyUI-WanVideoWrapper': {'commit': 'df8f3e49daaad117cf3090cc916c83f3d001494c', 'url': 'https://github.com/kijai/ComfyUI-WanVideoWrapper.git', 'class_schema_sha256': '80187858cc6ec371c9860fd9ca5fcf5174324d75782046657e252492512d115f', 'classes_used': ['WanVideoBlockSwap', 'WanVideoDecode', 'WanVideoEncode', 'WanVideoLoraSelect', 'WanVideoModelLoader', 'WanVideoSampler', 'WanVideoTextEncodeCached', 'WanVideoTorchCompileSettings', 'WanVideoVAELoader'], 'pip_packages': ['onnx', 'opencv-python-headless'], 'status': 'discovered'}},
    provenance={'source_path': '/Users/peteromalley/Documents/reigh-workspace/vibecomfy/workflow_corpus/custom_nodes/wanvideo_wrapper/kijai/wan21_14b_v2v_infinitetalk.json', 'source_id': 'wan21_14b_v2v_infinitetalk', 'source_type': 'api', 'source_workflow_path': '/Users/peteromalley/Documents/reigh-workspace/vibecomfy/workflow_corpus/custom_nodes/wanvideo_wrapper/kijai/wan21_14b_v2v_infinitetalk.json', 'output_mode': 'ready_template', 'ready_id': 'video/wanvideo_wrapper_21_14b_v2v_infinitetalk'},
)

def build() -> VibeWorkflow:
    """Build the workflow (auto-generated)."""
    wf = new_workflow(READY_METADATA, source_path=__file__)

    multitalkmodelloader = MultiTalkModelLoader(model=MODEL_NAME)

    loadaudio = LoadAudio(
        audio='one-does-not-simply-walk-into-mordor-its-black-gates-are-guarded-by-more-than-just-orcs.mp3',
    )

    wanvideovaeloader = WanVideoVAELoader(model_name=VAE_NAME)
    wanvideoblockswap = WanVideoBlockSwap(use_non_blocking=True, prefetch_blocks=1)
    downloadandloadwav2vecmodel = DownloadAndLoadWav2VecModel(model=MODEL_NAME_4)
    wanvideoloraselect = WanVideoLoraSelect(lora=LORA_NAME, merge_loras=False)
    wanvideotorchcompilesettings = WanVideoTorchCompileSettings()

    # Loaders
    clipvisionloader = CLIPVisionLoader(clip_name=CLIP_NAME)

    text_embeds, _, _ = WanVideoTextEncodeCached(
        model_name=CLIP_NAME_2,
        positive_prompt='a woman is singing a lullaby',
        negative_prompt=DEFAULT_NEGATIVE,
        use_disk_cache=False,
    )

    intconstant = INTConstant(value=640)
    intconstant_2 = INTConstant(value=640)
    intconstant_3 = INTConstant(value=1000)
    melbandroformermodelloader = raw_call('MelBandRoFormerModelLoader', '303', model=MEL_BAND_ROFORMER_NAME)
    wav2vecmodelloader = Wav2VecModelLoader(model=MODEL_NAME_3)

    wanvideomodelloader = WanVideoModelLoader(
        model=MODEL_NAME_2,
        base_precision='fp16_fast',
        attention_mode='sageattn',
        block_swap_args=wanvideoblockswap,
        lora=wanvideoloraselect,
        multitalk_model=multitalkmodelloader,
    )

    image, _, _, _ = VHS_LoadVideo(
        video='10.mp4',
        format='Wan',
        videopreview={'hidden': False, 'paused': False, 'params': {'filename': '10.mp4', 'type': 'input', 'format': 'video/mp4', 'force_rate': 0, 'custom_width': None, 'custom_height': 480, 'frame_load_cap': 0, 'skip_first_frames': 0, 'select_every_nth': 1}},
        custom_width=intconstant,
        custom_height=intconstant_2,
        **{'choose video to upload': 'image'},
    )

    melbandroformersampler = raw_call('MelBandRoFormerSampler', '304',
        audio=loadaudio,
        model=melbandroformermodelloader.out(0),
    )

    multitalk_embeds, _, _ = MultiTalkWav2VecEmbeds(
        widget_0=True,
        widget_1=400,
        widget_2=25,
        widget_3=1.5,
        widget_4=1,
        widget_5='para',
        audio_1=melbandroformersampler.out(0),
        num_frames=intconstant_3,
        wav2vec_model=downloadandloadwav2vecmodel,
    )

    image_image, _, _, _ = ImageResizeKJv2(
        upscale_method='lanczos',
        keep_proportion='crop',
        divisible_by=16,
        device='cpu',
        width=intconstant,
        height=intconstant_2,
        image=image,
    )

    wanvideoencode = WanVideoEncode(
        enable_vae_tiling=272,
        tile_x=144,
        tile_y=128,
        tile_stride_x=0,
        tile_stride_y=1,
        image=image_image,
        vae=wanvideovaeloader,
    )

    image_get, _ = GetImageRangeFromBatch(images=image_image)
    image_get_2, width_get, height_get, _ = GetImageSizeAndCount(image=image_get)

    wanvideoclipvisionencode = WanVideoClipVisionEncode(
        clip_vision=clipvisionloader,
        image_1=image_get_2,
    )

    image_embeds, _ = WanVideoImageToVideoMultiTalk(
        colormatch=False,
        force_offload='disabled',
        frame_window_size=9,
        motion_frame=False,
        widget_0=832,
        widget_1=480,
        widget_2=81,
        widget_7='infinitetalk',
        clip_embeds=wanvideoclipvisionencode,
        height=height_get,
        start_image=image_get_2,
        vae=wanvideovaeloader,
        width=width_get,
    )

    samples, _ = WanVideoSampler(
        steps=4,
        cfg=GUIDE_STRENGTH,
        shift=11.000000000000002,
        seed=DEFAULT_SEED,
        scheduler='dpm++_sde',
        start_step=2,
        add_noise_to_samples=True,
        image_embeds=image_embeds,
        model=wanvideomodelloader,
        multitalk_embeds=multitalk_embeds,
        samples=wanvideoencode,
        text_embeds=text_embeds,
    )

    wanvideodecode = WanVideoDecode(
        normalization='default',
        samples=samples,
        vae=wanvideovaeloader,
    )

    image_get_3, _, _, count_get = GetImageSizeAndCount(image=wanvideodecode)
    image_get_4, _ = GetImageRangeFromBatch(num_frames=count_get, images=image_get_3)

    imageconcatmulti = ImageConcatMulti(
        direction='left',
        unused_3=None,
        image_1=image_get_4,
        image_2=image_image,
    )

    # Outputs
    vhs_videocombine = VHS_VideoCombine(
        frame_rate=25,
        filename_prefix='WanVideo2_1_InfiniteTalk',
        format='video/h264-mp4',
        save_output=False,
        crf=19,
        pix_fmt='yuv420p',
        save_metadata=True,
        trim_to_audio=False,
        videopreview={'hidden': False, 'paused': False, 'params': {'filename': 'WanVideo2_1_InfiniteTalk_00007-audio.mp4', 'subfolder': '', 'type': 'temp', 'format': 'video/h264-mp4', 'frame_rate': 25, 'workflow': 'WanVideo2_1_InfiniteTalk_00007.png', 'fullpath': 'N:\\AI\\ComfyUI\\temp\\WanVideo2_1_InfiniteTalk_00007-audio.mp4'}},
        audio=loadaudio,
        images=imageconcatmulti,
    )

    return wf.finalize(PUBLIC_INPUT_METADATA, output_node=vhs_videocombine, output_type='VHS_VideoCombine', name='video', artifact_kind='video', mime_type='video/mp4', expected_cardinality='one', filename_prefix='WanVideo2_1_InfiniteTalk')

