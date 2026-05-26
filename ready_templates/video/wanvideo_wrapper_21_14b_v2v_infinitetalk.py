# vibecomfy: generated
# For hand-editing, run: python -m vibecomfy.cli copy-to-recipe <id>
"""Auto-generated ready_template — use python -m vibecomfy.cli copy-to-recipe <id> for hand-editing."""
from __future__ import annotations

from vibecomfy.templates import InputSpec, ReadyMetadata, new_workflow, node as raw_call
from vibecomfy.nodes.core import CLIPVisionLoader, GetImageRangeFromBatch, LoadAudio, PreviewAny
from vibecomfy.nodes.kjnodes import GetImageSizeAndCount, INTConstant, ImageConcatMulti, ImageResizeKJv2
from vibecomfy.nodes.videohelpersuite import VHS_LoadVideo, VHS_VideoCombine
from vibecomfy.nodes.wanvideowrapper import DownloadAndLoadWav2VecModel, MultiTalkModelLoader, MultiTalkWav2VecEmbeds, WanVideoBlockSwap, WanVideoClipVisionEncode, WanVideoDecode, WanVideoEncode, WanVideoImageToVideoMultiTalk, WanVideoLoraSelect, WanVideoModelLoader, WanVideoSampler, WanVideoTextEncodeCached, WanVideoTorchCompileSettings, WanVideoVAELoader, Wav2VecModelLoader


BASE_PRECISION = 'fp16'
DEFAULT_FRAMES = 1
DEFAULT_NEGATIVE = 'bright tones, overexposed, static, blurred details, subtitles, style, works, paintings, images, static, overall gray, worst quality, low quality, JPEG compression residue, ugly, incomplete, extra fingers, poorly drawn hands, poorly drawn faces, deformed, disfigured, misshapen limbs, fused fingers, still picture, messy background, three legs, many people in the background, walking backwards'
DEFAULT_SEED = 2
GUIDE_STRENGTH = 1.0000000000000002
LOAD_DEVICE = 'main_device'
MODEL_NAME = 'WanVideo\\InfiniteTalk\\InfiniteTalk\\Wan2_1-InfiniteTalk_Single_Q8.gguf'
MODEL_NAME_2 = 'wanvideo\\Wan2_1_VAE_bf16.safetensors'
MODEL_NAME_3 = 'clip_vision_h.safetensors'
MODEL_NAME_4 = 'WanVideo\\Lightx2v\\lightx2v_I2V_14B_480p_cfg_step_distill_rank64_bf16.safetensors'
MODEL_NAME_5 = 'umt5-xxl-enc-bf16.safetensors'
MODEL_NAME_6 = 'WanVideo\\wan2.1-i2v-14b-480p-Q8_0.gguf'
MODEL_NAME_7 = 'MelBandRoFormer\\MelBandRoformer_fp16.safetensors'
MODEL_NAME_8 = 'wav2vec2-chinese-base_fp16.safetensors'
MODEL_NAME_9 = 'TencentGameMate/chinese-wav2vec2-base'
PRECISION = 'bf16'
QUANTIZATION = 'disabled'


PUBLIC_INPUT_METADATA = {
    'seed': InputSpec(node='128', field='seed', default=DEFAULT_SEED, type='INT'),
}


def PUBLIC_INPUTS(**nodes):
    samples = nodes['samples']
    return {
    'seed': InputSpec(node=samples, field='seed', default=DEFAULT_SEED, type='INT'),
    }

READY_METADATA = ReadyMetadata.build(
    capability='unknown',
    inputs=PUBLIC_INPUT_METADATA,
    requirements={'models': ['clip_vision_h.safetensors', 'umt5-xxl-enc-bf16.safetensors', 'wanvideo\\Wan2_1_VAE_bf16.safetensors']},
    custom_node_packs={'ComfyUI-KJNodes': {'commit': 'b7646ad70a7daa7aeb919ca542274758d26ba2df', 'url': 'https://github.com/kijai/ComfyUI-KJNodes.git', 'class_schema_sha256': '1beaf129c8fa26175d89a28f9ca10d08b5ac27c8fc9bff920263fcbba17cb691', 'classes_used': ['GetImageRangeFromBatch', 'GetImageSizeAndCount', 'INTConstant', 'ImageResizeKJv2'], 'pip_packages': ['matplotlib'], 'status': 'discovered'}, 'ComfyUI-VideoHelperSuite': {'commit': '4ee72c065db22c9d96c2427954dc69e7b908444b', 'url': 'https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite.git', 'class_schema_sha256': '8391e679554eecd5d324a3e34a713ff240e619e3a07476587845ba18c9fae310', 'classes_used': ['VHS_LoadVideo', 'VHS_VideoCombine'], 'pip_packages': [], 'status': 'discovered'}, 'ComfyUI-WanVideoWrapper': {'commit': 'df8f3e49daaad117cf3090cc916c83f3d001494c', 'url': 'https://github.com/kijai/ComfyUI-WanVideoWrapper.git', 'class_schema_sha256': '80187858cc6ec371c9860fd9ca5fcf5174324d75782046657e252492512d115f', 'classes_used': ['WanVideoBlockSwap', 'WanVideoDecode', 'WanVideoEncode', 'WanVideoLoraSelect', 'WanVideoModelLoader', 'WanVideoSampler', 'WanVideoTextEncodeCached', 'WanVideoTorchCompileSettings', 'WanVideoVAELoader'], 'pip_packages': ['onnx', 'opencv-python-headless'], 'status': 'discovered'}},
    provenance={'source_path': 'workflow_corpus/custom_nodes/wanvideo_wrapper/kijai/wan21_14b_v2v_infinitetalk.json', 'source_id': 'wan21_14b_v2v_infinitetalk', 'source_type': 'api', 'source_workflow_path': 'workflow_corpus/custom_nodes/wanvideo_wrapper/kijai/wan21_14b_v2v_infinitetalk.json', 'source_hash': 'sha256:a0951c61b13ec6755772adfc5c13afe133284363e02053574a9fcbfd4c43817e', 'output_mode': 'ready_template', 'ready_id': 'video/wanvideo_wrapper_21_14b_v2v_infinitetalk'},
)

def build() -> VibeWorkflow:
    """Build the workflow (auto-generated)."""
    with new_workflow(READY_METADATA, source_path=__file__) as wf:

        multitalkmodelloader = MultiTalkModelLoader(model=MODEL_NAME)

        loadaudio = LoadAudio(
            audio='one-does-not-simply-walk-into-mordor-its-black-gates-are-guarded-by-more-than-just-orcs.mp3',
            widget_1=None,
            widget_2=None,
        )

        wanvideovaeloader = WanVideoVAELoader(model_name=MODEL_NAME_2)
        wanvideoblockswap = WanVideoBlockSwap(use_non_blocking=True, prefetch_blocks=1)
        downloadandloadwav2vecmodel = DownloadAndLoadWav2VecModel(model=MODEL_NAME_9)
        wanvideoloraselect = WanVideoLoraSelect(lora=MODEL_NAME_4, merge_loras=False)
        wanvideotorchcompilesettings = WanVideoTorchCompileSettings()

        # Loaders
        clipvisionloader = CLIPVisionLoader(clip_name=MODEL_NAME_3)

        text_embeds, negative_text_embeds, positive_prompt = WanVideoTextEncodeCached(
            model_name=MODEL_NAME_5,
            positive_prompt='a woman is singing a lullaby',
            negative_prompt=DEFAULT_NEGATIVE,
            use_disk_cache=False,
        )

        intconstant = INTConstant(value=640)
        intconstant_2 = INTConstant(value=640)
        intconstant_3 = INTConstant(value=1000)
        melbandroformermodelloader = raw_call('MelBandRoFormerModelLoader', '303', widget_0=MODEL_NAME_7)
        wav2vecmodelloader = Wav2VecModelLoader(model=MODEL_NAME_8)

        wanvideomodelloader = WanVideoModelLoader(
            model=MODEL_NAME_6,
            base_precision='fp16_fast',
            attention_mode='sageattn',
            block_swap_args=wanvideoblockswap,
            lora=wanvideoloraselect,
            multitalk_model=multitalkmodelloader,
        )

        image, frame_count, audio_load, video_info = VHS_LoadVideo(
            format='Wan',
            video='10.mp4',
            videopreview={'hidden': False, 'paused': False, 'params': {'filename': '10.mp4', 'type': 'input', 'format': 'video/mp4', 'force_rate': 0, 'custom_width': None, 'custom_height': 480, 'frame_load_cap': 0, 'skip_first_frames': 0, 'select_every_nth': 1}},
            custom_height=intconstant_2,
            custom_width=intconstant,
            **{'choose video to upload': 'image'},
        )

        melbandroformersampler = raw_call('MelBandRoFormerSampler', '304',
            audio=loadaudio,
            model=melbandroformermodelloader.out(0),
        )

        multitalk_embeds, audio, num_frames = MultiTalkWav2VecEmbeds(
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

        image_image, width, height, mask = ImageResizeKJv2(
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
            unused_widget_0=False,
            unused_widget_1=272,
            image=image_image,
            vae=wanvideovaeloader,
        )

        image_get, mask_get = GetImageRangeFromBatch(images=image_image)
        previewany = PreviewAny(source=num_frames)

        image_get_2, width_get, height_get, count = GetImageSizeAndCount(
            image=image_get,
        )

        wanvideoclipvisionencode = WanVideoClipVisionEncode(
            clip_vision=clipvisionloader,
            image_1=image_get_2,
        )

        image_embeds, output_path = WanVideoImageToVideoMultiTalk(
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

        samples, denoised_samples = WanVideoSampler(
            steps=4,
            cfg=GUIDE_STRENGTH,
            shift=11.000000000000002,
            seed=DEFAULT_SEED,
            scheduler='dpm++_sde',
            start_step=2,
            add_noise_to_samples=True,
            unused_widget_4='fixed',
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

        image_get_3, width_get_2, height_get_2, count_get = GetImageSizeAndCount(
            image=wanvideodecode,
        )

        image_get_4, mask_get_2 = GetImageRangeFromBatch(
            num_frames=count_get,
            images=image_get_3,
        )

        imageconcatmulti = ImageConcatMulti(
            direction=False,
            match_image_size=None,
            unused_widget_1='left',
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

        return wf.finalize(PUBLIC_INPUTS(**locals()), output_node=vhs_videocombine, output_type='VHS_VideoCombine', name='video', artifact_kind='video', mime_type='video/mp4', expected_cardinality='one', filename_prefix='WanVideo2_1_InfiniteTalk')

