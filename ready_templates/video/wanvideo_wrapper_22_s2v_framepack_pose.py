# vibecomfy: generated
# For hand-editing, run: python -m vibecomfy.cli copy-to-recipe <id>
"""Auto-generated ready_template — use python -m vibecomfy.cli copy-to-recipe <id> for hand-editing."""
from __future__ import annotations

from vibecomfy.templates import InputSpec, ReadyMetadata, new_workflow, node as raw_call
from vibecomfy.nodes.core import AudioEncoderEncode, AudioEncoderLoader, GetImageRangeFromBatch, LoadAudio, LoadImage, PreviewAny
from vibecomfy.nodes.kjnodes import ColorMatch, GetImageSizeAndCount, INTConstant, ImageConcatMulti, ImageResizeKJv2, LazySwitchKJ
from vibecomfy.nodes.videohelpersuite import VHS_LoadAudio, VHS_LoadVideo, VHS_VideoCombine
from vibecomfy.nodes.wanvideowrapper import NormalizeAudioLoudness, WanVideoAddS2VEmbeds, WanVideoBlockSwap, WanVideoDecode, WanVideoEmptyEmbeds, WanVideoEncode, WanVideoLoraSelectMulti, WanVideoModelLoader, WanVideoSampler, WanVideoSetBlockSwap, WanVideoSetLoRAs, WanVideoTextEncodeCached, WanVideoTorchCompileSettings, WanVideoVAELoader


CHOOSE_VIDEO_TO_UPLOAD = 'image'
CROP_POSITION = 'center'
DEFAULT_FRAMES = 501
DEFAULT_NEGATIVE = '色调艳丽，过曝，静态，细节模糊不清，字幕，风格，作品，画作，画面，静止，整体发灰，最差质量，低质量，JPEG压缩残留，丑陋的，残缺的，多余的手指，画得不好的手部，画得不好的脸部，畸形的，毁容的，形态畸形的肢体，手指融合，静止不动的画面，杂乱的背景，三条腿，背景人很多，倒着走'
DEFAULT_PROMPT = '3D animated scene of a young woman singing melancholically'
DEFAULT_SEED = 45
DEVICE = 'cpu'
DEVICE_2 = 'gpu'
FORMAT = 'Wan'
GUIDE_STRENGTH = 1
KEEP_PROPORTION = 'crop'
MODEL_NAME = 'WanVideo\\S2V\\Wan2_2-S2V-14B_fp8_e4m3fn_scaled_KJ.safetensors'
MODEL_NAME_2 = 'WanVideo\\Lightx2v\\lightx2v_T2V_14B_cfg_step_distill_v2_lora_rank64_bf16_.safetensors'
MODEL_NAME_3 = 'wanvideo\\Wan2_1_VAE_bf16.safetensors'
MODEL_NAME_4 = 'wav2vec_xlsr_53_english_fp32.safetensors'
MODEL_NAME_5 = 'MelBandRoFormer\\MelBandRoformer_fp16.safetensors'
MODEL_NAME_6 = 'yolox_l.torchscript.pt'
MODEL_NAME_7 = 'dw-ll_ucoco_384_bs5.torchscript.pt'
MODEL_NAME_8 = 'umt5-xxl-enc-bf16.safetensors'
PAD_COLOR = '0, 0, 0'
PRECISION = 'bf16'
UPSCALE_METHOD = 'bilinear'


PUBLIC_INPUT_METADATA = {
    'seed': InputSpec(node='27', field='seed', default=DEFAULT_SEED, type='INT'),
    'image': InputSpec(node='73', field='image', default='2b.jpg', type='IMAGE', required=True, aliases=('input_image',), media_semantics='image'),
    'width': InputSpec(node='111', field='width', default=640, type='INT'),
    'height': InputSpec(node='111', field='height', default=640, type='INT'),
}


def PUBLIC_INPUTS(**nodes):
    samples = nodes['samples']
    image_load = nodes['image_load']
    image_image_3 = nodes['image_image_3']
    image_image_3 = nodes['image_image_3']
    return {
    'seed': InputSpec(node=samples, field='seed', default=DEFAULT_SEED, type='INT'),
    'image': InputSpec(node=image_load, field='image', default='2b.jpg', type='IMAGE', required=True, aliases=('input_image',), media_semantics='image'),
    'width': InputSpec(node=image_image_3, field='width', default=640, type='INT'),
    'height': InputSpec(node=image_image_3, field='height', default=640, type='INT'),
    }

READY_METADATA = ReadyMetadata.build(
    capability='unknown',
    inputs=PUBLIC_INPUT_METADATA,
    requirements={'models': ['umt5-xxl-enc-bf16.safetensors', 'wanvideo\\Wan2_1_VAE_bf16.safetensors']},
    custom_node_packs={'ComfyUI-KJNodes': {'commit': 'b7646ad70a7daa7aeb919ca542274758d26ba2df', 'url': 'https://github.com/kijai/ComfyUI-KJNodes.git', 'class_schema_sha256': '1beaf129c8fa26175d89a28f9ca10d08b5ac27c8fc9bff920263fcbba17cb691', 'classes_used': ['GetImageRangeFromBatch', 'GetImageSizeAndCount', 'INTConstant', 'ImageResizeKJv2'], 'pip_packages': ['matplotlib'], 'status': 'discovered'}, 'ComfyUI-VideoHelperSuite': {'commit': '4ee72c065db22c9d96c2427954dc69e7b908444b', 'url': 'https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite.git', 'class_schema_sha256': '8391e679554eecd5d324a3e34a713ff240e619e3a07476587845ba18c9fae310', 'classes_used': ['VHS_LoadVideo', 'VHS_VideoCombine'], 'pip_packages': [], 'status': 'discovered'}, 'ComfyUI-WanVideoWrapper': {'commit': 'df8f3e49daaad117cf3090cc916c83f3d001494c', 'url': 'https://github.com/kijai/ComfyUI-WanVideoWrapper.git', 'class_schema_sha256': '80187858cc6ec371c9860fd9ca5fcf5174324d75782046657e252492512d115f', 'classes_used': ['WanVideoBlockSwap', 'WanVideoDecode', 'WanVideoEmptyEmbeds', 'WanVideoEncode', 'WanVideoLoraSelectMulti', 'WanVideoModelLoader', 'WanVideoSampler', 'WanVideoSetBlockSwap', 'WanVideoSetLoRAs', 'WanVideoTextEncodeCached', 'WanVideoTorchCompileSettings', 'WanVideoVAELoader'], 'pip_packages': ['onnx', 'opencv-python-headless'], 'status': 'discovered'}, 'comfyui_controlnet_aux': {'commit': 'e8b689a513c3e6b63edc44066560ca5919c0576e', 'url': 'https://github.com/Fannovel16/comfyui_controlnet_aux.git', 'class_schema_sha256': 'e485b148824d72ef7af7e90f711eefb511ffe73b25cd1c6053e1e5c7bd3bbd62', 'classes_used': ['DWPreprocessor'], 'pip_packages': ['onnxruntime', 'opencv-python-headless'], 'status': 'discovered'}},
    provenance={'source_path': 'workflow_corpus/custom_nodes/wanvideo_wrapper/kijai/wan22_s2v_framepack_pose.json', 'source_id': 'wan22_s2v_framepack_pose', 'source_type': 'api', 'source_workflow_path': 'workflow_corpus/custom_nodes/wanvideo_wrapper/kijai/wan22_s2v_framepack_pose.json', 'source_hash': 'sha256:887315d87ce17ddfe92490e70ea450ddfe27d000fd56b9c4dca0dadaf300b401', 'output_mode': 'ready_template', 'ready_id': 'video/wanvideo_wrapper_22_s2v_framepack_pose'},
)

def build() -> VibeWorkflow:
    """Build the workflow (auto-generated)."""
    with new_workflow(READY_METADATA, source_path=__file__) as wf:

        wanvideotorchcompilesettings = WanVideoTorchCompileSettings()
        wanvideovaeloader = WanVideoVAELoader(model_name=MODEL_NAME_3)

        wanvideoblockswap = WanVideoBlockSwap(
            blocks_to_swap=32,
            use_non_blocking=True,
            prefetch_blocks=1,
        )

        wanvideoloraselectmulti = WanVideoLoraSelectMulti(
            lora_0=MODEL_NAME_2,
            strength_0=1.2,
            merge_loras=False,
        )

        audioencoderloader = AudioEncoderLoader(audio_encoder_name=MODEL_NAME_4)

        loadaudio = LoadAudio(
            audio='0321. Alphaville - Big In Japan.mp3',
            widget_1=None,
            widget_2=None,
        )

        text_embeds, negative_text_embeds, positive_prompt = WanVideoTextEncodeCached(
            model_name=MODEL_NAME_8,
            positive_prompt=DEFAULT_PROMPT,
            negative_prompt=DEFAULT_NEGATIVE,
        )

        # Inputs
        image_load, mask = LoadImage(image='2b.jpg', unused_widget_1='image')
        melbandroformermodelloader = raw_call('MelBandRoFormerModelLoader', '81', widget_0=MODEL_NAME_5)
        audio, duration = VHS_LoadAudio(audio_file='input/weightoftheworld2.mp4')
        intconstant = INTConstant(value=640)
        intconstant_2 = INTConstant(value=640)

        wanvideomodelloader = WanVideoModelLoader(
            model=MODEL_NAME,
            base_precision='fp16_fast',
            quantization='fp8_e4m3fn_scaled',
            attention_mode='sageattn',
            compile_args=wanvideotorchcompilesettings,
        )

        image_image, width_image, height_image, mask_image = ImageResizeKJv2(
            upscale_method='lanczos',
            keep_proportion=KEEP_PROPORTION,
            divisible_by=16,
            device=DEVICE,
            unused_widget_8='<tr><td>Output: </td><td><b>1</b> x <b>960</b> x <b>640 | 7.03MB</b></td></tr>',
            width=intconstant,
            height=intconstant_2,
            image=image_load,
        )

        image_load_2, frame_count, audio_load, video_info = VHS_LoadVideo(
            force_rate=16,
            format=FORMAT,
            frame_load_cap=501,
            video='weightoftheworld2.mp4',
            videopreview={'hidden': False, 'paused': False, 'params': {'filename': 'weightoftheworld2.mp4', 'type': 'input', 'format': 'video/mp4', 'force_rate': 16, 'custom_width': 0, 'custom_height': 0, 'frame_load_cap': 501, 'skip_first_frames': 0, 'select_every_nth': 1}},
            custom_height=intconstant_2,
            custom_width=intconstant,
            **{'choose video to upload': CHOOSE_VIDEO_TO_UPLOAD},
        )

        image_load_3, frame_count_load, audio_load_2, video_info_load = VHS_LoadVideo(
            force_rate=16,
            format=FORMAT,
            frame_load_cap=501,
            video='weight-world-bones_00003-audio.mp4',
            videopreview={'hidden': False, 'paused': False, 'params': {'filename': 'weight-world-bones_00003-audio.mp4', 'type': 'input', 'format': 'video/mp4', 'force_rate': 16, 'custom_width': 0, 'custom_height': 0, 'frame_load_cap': 501, 'skip_first_frames': 0, 'select_every_nth': 1}},
            custom_height=intconstant_2,
            custom_width=intconstant,
            **{'choose video to upload': CHOOSE_VIDEO_TO_UPLOAD},
        )

        wanvideoemptyembeds = WanVideoEmptyEmbeds(
            num_frames=DEFAULT_FRAMES,
            width=width_image,
            height=height_image,
        )

        wanvideosetloras = WanVideoSetLoRAs(
            lora=wanvideoloraselectmulti,
            model=wanvideomodelloader,
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

        melbandroformersampler = raw_call('MelBandRoFormerSampler', '82',
            audio=audio_load,
            model=melbandroformermodelloader.out(0),
        )

        image_image_2, width_image_2, height_image_2, mask_image_2 = ImageResizeKJv2(
            upscale_method=UPSCALE_METHOD,
            keep_proportion=KEEP_PROPORTION,
            divisible_by=16,
            device=DEVICE,
            width=intconstant,
            height=intconstant_2,
            image=image_load_3,
        )

        wanvideosetblockswap = WanVideoSetBlockSwap(
            block_swap_args=wanvideoblockswap,
            model=wanvideosetloras,
        )

        normalizeaudioloudness = NormalizeAudioLoudness(
            widget_0=-23,
            audio=melbandroformersampler.out(0),
        )

        dwpreprocessor = raw_call('DWPreprocessor', '107',
            detect_hand='disable',
            detect_body='disable',
            detect_face='enable',
            resolution=640,
            bbox_detector=MODEL_NAME_6,
            pose_estimator=MODEL_NAME_7,
            image=image_image_2,
        )

        audioencoderencode = AudioEncoderEncode(
            audio=normalizeaudioloudness,
            audio_encoder=audioencoderloader,
        )

        image_image_3, width_image_3, height_image_3, mask_image_3 = ImageResizeKJv2(
            width=640,
            height=640,
            upscale_method=UPSCALE_METHOD,
            keep_proportion='stretch',
            divisible_by=16,
            device=DEVICE_2,
            image=dwpreprocessor,
        )

        wanvideoencode_2 = WanVideoEncode(
            enable_vae_tiling=272,
            tile_x=144,
            tile_y=128,
            tile_stride_x=0,
            tile_stride_y=0.5,
            unused_widget_0=False,
            unused_widget_1=272,
            image=image_image_3,
            vae=wanvideovaeloader,
        )

        image_embeds, audio_frame_count = WanVideoAddS2VEmbeds(
            audio_scale=0,
            frame_window_size=1,
            pose_start_percent=1,
            widget_0=80,
            audio_encoder_output=audioencoderencode,
            embeds=wanvideoemptyembeds,
            pose_latent=wanvideoencode_2,
            ref_latent=wanvideoencode,
            vae=wanvideovaeloader,
        )

        samples, denoised_samples = WanVideoSampler(
            steps=4,
            cfg=GUIDE_STRENGTH,
            shift=4,
            seed=DEFAULT_SEED,
            scheduler='lcm',
            unused_widget_4='fixed',
            image_embeds=image_embeds,
            model=wanvideosetblockswap,
            text_embeds=text_embeds,
        )

        previewany = PreviewAny(source=audio_frame_count)

        wanvideodecode = WanVideoDecode(
            normalization='default',
            samples=samples,
            vae=wanvideovaeloader,
        )

        image, width, height, count = GetImageSizeAndCount(image=wanvideodecode)

        image_get, mask_get = GetImageRangeFromBatch(
            num_frames=DEFAULT_FRAMES,
            images=image,
        )

        colormatch = ColorMatch(
            widget_0='mkl',
            widget_1=1,
            widget_2=True,
            image_ref=image_image,
            image_target=image_get,
        )

        imageconcatmulti = ImageConcatMulti(
            direction=False,
            match_image_size=None,
            unused_widget_1='right',
            image_1=image_image_3,
            image_2=colormatch,
        )

        lazyswitchkj = LazySwitchKJ(
            switch=True,
            on_false=colormatch,
            on_true=imageconcatmulti,
        )

        # Outputs
        vhs_videocombine = VHS_VideoCombine(
            frame_rate=16,
            filename_prefix='WanVideo2_2_S2V',
            format='video/h264-mp4',
            save_output=False,
            crf=19,
            pix_fmt='yuv420p',
            save_metadata=True,
            trim_to_audio=False,
            videopreview={'hidden': False, 'paused': False, 'params': {'filename': 'WanVideo2_2_S2V_00014-audio.mp4', 'subfolder': '', 'type': 'temp', 'format': 'video/h264-mp4', 'frame_rate': 16, 'workflow': 'WanVideo2_2_S2V_00014.png', 'fullpath': 'N:\\AI\\ComfyUI\\temp\\WanVideo2_2_S2V_00014-audio.mp4'}},
            audio=audio_load,
            images=lazyswitchkj,
        )

        return wf.finalize(PUBLIC_INPUTS(**locals()), output_node=vhs_videocombine, output_type='VHS_VideoCombine', name='video', artifact_kind='video', mime_type='video/mp4', expected_cardinality='one', filename_prefix='WanVideo2_2_S2V')

