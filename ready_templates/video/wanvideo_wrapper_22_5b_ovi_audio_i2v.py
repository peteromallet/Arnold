# vibecomfy: generated - converted by tools/convert_ready_templates.py
# Edits will be overwritten on regeneration. Put the manual opt-out
# marker on the first line if hand-editing is required.
"""Auto-generated ready_template - see tools/convert_ready_templates.py."""
from __future__ import annotations

from vibecomfy.templates import InputSpec, ModelAsset, ReadyMetadata, finalize, new_workflow, node as raw_call, ref
from vibecomfy.nodes.core import LoadImage, PreviewAudio
from vibecomfy.nodes.kjnodes import ImageResizeKJv2
from vibecomfy.nodes.videohelpersuite import VHS_VideoCombine
from vibecomfy.nodes.wanvideowrapper import OviMMAudioVAELoader, WanVideoBlockSwap, WanVideoDecode, WanVideoDecodeOviAudio, WanVideoEasyCache, WanVideoEmptyEmbeds, WanVideoEmptyMMAudioLatents, WanVideoEncode, WanVideoExtraModelSelect, WanVideoModelLoader, WanVideoOviCFG, WanVideoSLG, WanVideoSampler, WanVideoSetBlockSwap, WanVideoTextEncodeCached, WanVideoTorchCompileSettings, WanVideoVAELoader


DEFAULT_FRAMES = 5
DEFAULT_NEGATIVE = '色调艳丽，过曝，静态，细节模糊不清，字幕，风格，作品，画作，画面，静止，整体发灰，最差质量，低质量，JPEG压缩残留，丑陋的，残缺的，多余的手指，画得不好的手部，画得不好的脸部，畸形的，毁容的，形态畸形的肢体，手指融合，静止不动的画面，杂乱的背景，三条腿，背景人很多，倒着走'
DEFAULT_NEGATIVE_2 = 'robotic, muffled, echo, distorted'
DEFAULT_PROMPT = 'A tired old man is very sarcastically saying: <S>Oh great, they are making me talk now too.<E>. <AUDCAP>Clear older male voices speaking dialogue, subtle outdoor ambience.<ENDAUDCAP>'
DEFAULT_SEED = 42
GUIDE_STRENGTH = 4
MODEL_NAME = 'WanVideo/Ovi/Wan_2_1_Ovi_audio_model_bf16.safetensors'
MODEL_NAME_2 = 'umt5-xxl-enc-bf16.safetensors'
MODEL_NAME_3 = 'Wan2_2_VAE_bf16.safetensors'
MODEL_NAME_4 = 'mmaudio_vae_16k_fp32.safetensors'
MODEL_NAME_5 = 'mmaudio_vocoder_bigvgan_best_netG_fp32.safetensors'
MODEL_NAME_6 = 'WanVideo/Ovi/Wan_2_1_Ovi_video_model_bf16.safetensors'


MODELS = {}

PUBLIC_INPUTS = {
    'model': InputSpec(node=ref('wanvideotextencodecached'), field='model_name', default=MODEL_NAME_2),
    'seed': InputSpec(node=ref('wanvideosampler'), field='seed', default=DEFAULT_SEED),
    'image': InputSpec(node=ref('loadimage'), field='image', default='oldman_upscaled.png'),
    'input_image': InputSpec(node=ref('loadimage'), field='image', default='oldman_upscaled.png'),
    'width': InputSpec(node=ref('imageresizekjv2'), field='width', default=256),
    'height': InputSpec(node=ref('imageresizekjv2'), field='height', default=256),
}

READY_METADATA = ReadyMetadata.build(
    capability='audio_image_to_video',
    inputs=PUBLIC_INPUTS,
    models=MODELS,
    requirements={'models': ['Wan2_2_VAE_bf16.safetensors', 'umt5-xxl-enc-bf16.safetensors'], 'custom_nodes': ['ComfyUI-KJNodes', 'ComfyUI-VideoHelperSuite', 'ComfyUI-WanVideoWrapper']},
    custom_node_packs={'ComfyUI-KJNodes': {'commit': 'b7646ad70a7daa7aeb919ca542274758d26ba2df', 'url': 'https://github.com/kijai/ComfyUI-KJNodes.git', 'class_schema_sha256': '1beaf129c8fa26175d89a28f9ca10d08b5ac27c8fc9bff920263fcbba17cb691', 'classes_used': ['ImageResizeKJv2'], 'pip_packages': ['matplotlib'], 'status': 'pinned'}, 'ComfyUI-VideoHelperSuite': {'commit': '4ee72c065db22c9d96c2427954dc69e7b908444b', 'url': 'https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite.git', 'class_schema_sha256': '8391e679554eecd5d324a3e34a713ff240e619e3a07476587845ba18c9fae310', 'classes_used': ['VHS_VideoCombine'], 'pip_packages': [], 'status': 'pinned'}, 'ComfyUI-WanVideoWrapper': {'commit': 'df8f3e49daaad117cf3090cc916c83f3d001494c', 'url': 'https://github.com/kijai/ComfyUI-WanVideoWrapper.git', 'class_schema_sha256': '80187858cc6ec371c9860fd9ca5fcf5174324d75782046657e252492512d115f', 'classes_used': ['WanVideoBlockSwap', 'WanVideoDecode', 'WanVideoEasyCache', 'WanVideoEmptyEmbeds', 'WanVideoEncode', 'WanVideoModelLoader', 'WanVideoSLG', 'WanVideoSampler', 'WanVideoSetBlockSwap', 'WanVideoTextEncodeCached', 'WanVideoTorchCompileSettings', 'WanVideoVAELoader'], 'pip_packages': ['onnx', 'opencv-python-headless'], 'status': 'pinned'}},
    smoke_resolution='256x256x5_frames',
    approach='Ovi image-to-video with audio',
    provenance={'source_workflow': 'workflow_corpus/custom_nodes/wanvideo_wrapper/kijai/wan22_5b_ovi_audio_i2v.json'},
)

def build() -> VibeWorkflow:
    """Build the workflow (auto-generated)."""
    with new_workflow(READY_METADATA, source_path=__file__) as wf:

        wanvideoextramodelselect = WanVideoExtraModelSelect(
            _id='78',
            widget_0=MODEL_NAME,
        )
        wf.metadata.setdefault('id_map', {})['wanvideoextramodelselect'] = wanvideoextramodelselect.node.id

        wanvideoblockswap = WanVideoBlockSwap(
            _id='83',
            blocks_to_swap=15,
            use_non_blocking=True,
            prefetch_blocks=1,
        )
        wf.metadata.setdefault('id_map', {})['wanvideoblockswap'] = wanvideoblockswap.node.id

        wanvideotextencodecached = WanVideoTextEncodeCached(
            _id='85',
            model_name=MODEL_NAME_2,
            positive_prompt=DEFAULT_PROMPT,
            negative_prompt=DEFAULT_NEGATIVE,
            use_disk_cache=False,
            _outputs=('TEXT_EMBEDS', 'NEGATIVE_TEXT_EMBEDS', 'POSITIVE_PROMPT'),
        )
        wf.metadata.setdefault('id_map', {})['wanvideotextencodecached'] = wanvideotextencodecached.node.id

        wanvideovaeloader = WanVideoVAELoader(_id='87', model_name=MODEL_NAME_3)
        wf.metadata.setdefault('id_map', {})['wanvideovaeloader'] = wanvideovaeloader.node.id
        ovimmaudiovaeloader = OviMMAudioVAELoader(
            _id='89',
            widget_0=MODEL_NAME_4,
            widget_1=MODEL_NAME_5,
            widget_2='fp32',
        )
        wf.metadata.setdefault('id_map', {})['ovimmaudiovaeloader'] = ovimmaudiovaeloader.node.id

        wanvideotorchcompilesettings = WanVideoTorchCompileSettings(_id='91')
        wf.metadata.setdefault('id_map', {})['wanvideotorchcompilesettings'] = wanvideotorchcompilesettings.node.id
        wanvideoslg = WanVideoSLG(
            _id='93',
            widget_0='11',
            widget_1=0,
            widget_2=1,
        )
        wf.metadata.setdefault('id_map', {})['wanvideoslg'] = wanvideoslg.node.id

        wanvideotextencodecached_2 = WanVideoTextEncodeCached(
            _id='96',
            model_name=MODEL_NAME_2,
            negative_prompt=DEFAULT_NEGATIVE_2,
            _outputs=('TEXT_EMBEDS', 'NEGATIVE_TEXT_EMBEDS', 'POSITIVE_PROMPT'),
        )
        wf.metadata.setdefault('id_map', {})['wanvideotextencodecached_2'] = wanvideotextencodecached_2.node.id

        # Inputs
        loadimage = LoadImage(
            _id='109',
            image='oldman_upscaled.png',
            _outputs=('IMAGE', 'MASK'),
        )
        wf.metadata.setdefault('id_map', {})['loadimage'] = loadimage.node.id

        wanvideoeasycache = WanVideoEasyCache(
            _id='118',
            widget_0=0.015,
            widget_1=10,
            widget_2=-1,
            widget_3='offload_device',
        )
        wf.metadata.setdefault('id_map', {})['wanvideoeasycache'] = wanvideoeasycache.node.id

        wanvideoemptymmaudiolatents = WanVideoEmptyMMAudioLatents(
            _id='125',
            widget_0=157,
        )
        wf.metadata.setdefault('id_map', {})['wanvideoemptymmaudiolatents'] = wanvideoemptymmaudiolatents.node.id

        wanvideomodelloader = WanVideoModelLoader(
            _id='12',
            model=MODEL_NAME_6,
            compile_args=wanvideotorchcompilesettings,
            extra_model=wanvideoextramodelselect,
        )
        wf.metadata.setdefault('id_map', {})['wanvideomodelloader'] = wanvideomodelloader.node.id

        wanvideoovicfg = WanVideoOviCFG(
            _id='94',
            widget_0=3,
            original_text_embeds=wanvideotextencodecached.out('TEXT_EMBEDS'),
            ovi_negative_text_embeds=wanvideotextencodecached_2.out('NEGATIVE_TEXT_EMBEDS'),
        )
        wf.metadata.setdefault('id_map', {})['wanvideoovicfg'] = wanvideoovicfg.node.id

        imageresizekjv2 = ImageResizeKJv2(
            _id='110',
            width=256,
            height=256,
            upscale_method='lanczos',
            keep_proportion='crop',
            divisible_by=32,
            device='cpu',
            image=loadimage.out('IMAGE'),
            _outputs=('IMAGE', 'WIDTH', 'HEIGHT', 'MASK'),
        )
        wf.metadata.setdefault('id_map', {})['imageresizekjv2'] = imageresizekjv2.node.id

        wanvideosetblockswap = WanVideoSetBlockSwap(
            _id='84',
            block_swap_args=wanvideoblockswap,
            model=wanvideomodelloader,
        )
        wf.metadata.setdefault('id_map', {})['wanvideosetblockswap'] = wanvideosetblockswap.node.id

        wanvideoencode = WanVideoEncode(
            _id='111',
            widget_0=False,
            widget_1=272,
            widget_2=272,
            widget_3=144,
            widget_4=128,
            widget_5=0,
            widget_6=1,
            image=imageresizekjv2.out('IMAGE'),
            vae=wanvideovaeloader,
        )
        wf.metadata.setdefault('id_map', {})['wanvideoencode'] = wanvideoencode.node.id

        wanvideoemptyembeds = WanVideoEmptyEmbeds(
            _id='81',
            num_frames=DEFAULT_FRAMES,
            widget_0=256,
            widget_1=256,
            widget_2=5,
            extra_latents=wanvideoencode,
            height=imageresizekjv2.out('HEIGHT'),
            width=imageresizekjv2.out('WIDTH'),
        )
        wf.metadata.setdefault('id_map', {})['wanvideoemptyembeds'] = wanvideoemptyembeds.node.id

        wanvideosampler = WanVideoSampler(
            _id='80',
            steps=1,
            cfg=GUIDE_STRENGTH,
            seed=DEFAULT_SEED,
            rope_function='default',
            cache_args=wanvideoeasycache,
            image_embeds=wanvideoemptyembeds,
            model=wanvideosetblockswap,
            samples=wanvideoemptymmaudiolatents,
            slg_args=wanvideoslg,
            text_embeds=wanvideoovicfg,
            _outputs=('SAMPLES', 'DENOISED_SAMPLES'),
        )
        wf.metadata.setdefault('id_map', {})['wanvideosampler'] = wanvideosampler.node.id

        wanvideodecode = WanVideoDecode(
            _id='86',
            normalization='default',
            samples=wanvideosampler.out('SAMPLES'),
            vae=wanvideovaeloader,
        )
        wf.metadata.setdefault('id_map', {})['wanvideodecode'] = wanvideodecode.node.id

        wanvideodecodeoviaudio = WanVideoDecodeOviAudio(
            _id='90',
            mmaudio_vae=ovimmaudiovaeloader,
            samples=wanvideosampler.out('SAMPLES'),
        )
        wf.metadata.setdefault('id_map', {})['wanvideodecodeoviaudio'] = wanvideodecodeoviaudio.node.id

        # Outputs
        vhs_videocombine = VHS_VideoCombine(
            _id='88',
            audio=wanvideodecodeoviaudio,
            images=wanvideodecode,
        )
        wf.metadata.setdefault('id_map', {})['vhs_videocombine'] = vhs_videocombine.node.id

        previewaudio = PreviewAudio(_id='108', audio=wanvideodecodeoviaudio)
        wf.metadata.setdefault('id_map', {})['previewaudio'] = previewaudio.node.id

        return wf.finalize(PUBLIC_INPUTS, output_node=vhs_videocombine, output_type='VHS_VideoCombine', name='video', artifact_kind='video', mime_type='video/mp4', expected_cardinality='one')

