# vibecomfy: generated - converted by tools/convert_ready_templates.py
# Edits will be overwritten on regeneration. Put the manual opt-out
# marker on the first line if hand-editing is required.
"""Auto-generated ready_template - see tools/convert_ready_templates.py."""
from __future__ import annotations

from vibecomfy.templates import InputSpec, ModelAsset, ReadyMetadata, finalize, new_workflow, node as raw_call, ref
from vibecomfy.nodes.core import ImageBlur
from vibecomfy.nodes.kjnodes import ImageConcatMulti
from vibecomfy.nodes.videohelpersuite import VHS_LoadVideo, VHS_VideoCombine
from vibecomfy.nodes.wanvideowrapper import LoadWanVideoT5TextEncoder, WanVideoControlEmbeds, WanVideoDecode, WanVideoEncode, WanVideoLoraSelect, WanVideoModelLoader, WanVideoSampler, WanVideoTeaCache, WanVideoTextEncode, WanVideoTorchCompileSettings, WanVideoVAELoader


DEFAULT_NEGATIVE = '色调艳丽，过曝，静态，细节模糊不清，字幕，风格，作品，画作，画面，静止，整体发灰，最差质量，低质量，JPEG压缩残留，丑陋的，残缺的，多余的手指，画得不好的手部，画得不好的脸部，畸形的，毁容的，形态畸形的肢体，手指融合，静止不动的画面，杂乱的背景，三条腿，背景人很多，倒着走'
DEFAULT_SEED = 0
MODEL_NAME = 'umt5-xxl-enc-bf16.safetensors'
MODEL_NAME_2 = 'wanvideo\\Wan2_1_VAE_bf16.safetensors'
MODEL_NAME_3 = 'WanVid\\wan2.1-1.3b-control-lora-tile-v1.1_comfy.safetensors'
MODEL_NAME_4 = 'WanVideo\\wan2.1_t2v_1.3B_fp16.safetensors'


MODELS = {}

PUBLIC_INPUTS = {
    'model': InputSpec(node=ref('loadwanvideot5textencoder'), field='model_name', default=MODEL_NAME),
    'seed': InputSpec(node=ref('wanvideosampler'), field='seed', default=DEFAULT_SEED),
}

READY_METADATA = ReadyMetadata.build(
    capability='control_lora_video',
    inputs=PUBLIC_INPUTS,
    models=MODELS,
    requirements={'models': ['umt5-xxl-enc-bf16.safetensors', 'wanvideo\\Wan2_1_VAE_bf16.safetensors'], 'custom_nodes': ['ComfyUI-VideoHelperSuite', 'ComfyUI-WanVideoWrapper']},
    custom_node_packs={'ComfyUI-VideoHelperSuite': {'commit': '4ee72c065db22c9d96c2427954dc69e7b908444b', 'url': 'https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite.git', 'class_schema_sha256': '8391e679554eecd5d324a3e34a713ff240e619e3a07476587845ba18c9fae310', 'classes_used': ['VHS_LoadVideo', 'VHS_VideoCombine'], 'pip_packages': [], 'status': 'pinned'}, 'ComfyUI-WanVideoWrapper': {'commit': 'df8f3e49daaad117cf3090cc916c83f3d001494c', 'url': 'https://github.com/kijai/ComfyUI-WanVideoWrapper.git', 'class_schema_sha256': '80187858cc6ec371c9860fd9ca5fcf5174324d75782046657e252492512d115f', 'classes_used': ['LoadWanVideoT5TextEncoder', 'WanVideoControlEmbeds', 'WanVideoDecode', 'WanVideoEncode', 'WanVideoLoraSelect', 'WanVideoModelLoader', 'WanVideoSampler', 'WanVideoTextEncode', 'WanVideoTorchCompileSettings', 'WanVideoVAELoader'], 'pip_packages': ['onnx', 'opencv-python-headless'], 'status': 'pinned'}},
    smoke_resolution='256x256x5_frames',
    approach='WanVideoWrapper 1.3B control LoRA',
    provenance={'source_workflow': 'workflow_corpus/custom_nodes/wanvideo_wrapper/kijai/wan13b_control_lora.json'},
)

def build() -> VibeWorkflow:
    """Build the workflow (auto-generated)."""
    with new_workflow(READY_METADATA, source_path=__file__) as wf:

        loadwanvideot5textencoder = LoadWanVideoT5TextEncoder(
            _id='11',
            model_name=MODEL_NAME,
        )
        wf.metadata.setdefault('id_map', {})['loadwanvideot5textencoder'] = loadwanvideot5textencoder.node.id

        wanvideotorchcompilesettings = WanVideoTorchCompileSettings(_id='35')
        wf.metadata.setdefault('id_map', {})['wanvideotorchcompilesettings'] = wanvideotorchcompilesettings.node.id
        wanvideovaeloader = WanVideoVAELoader(_id='38', model_name=MODEL_NAME_2)
        wf.metadata.setdefault('id_map', {})['wanvideovaeloader'] = wanvideovaeloader.node.id
        wanvideoteacache = WanVideoTeaCache(
            _id='52',
            widget_0=0.1,
            widget_1=1,
            widget_2=-1,
            widget_3='offload_device',
            widget_4='true',
        )
        wf.metadata.setdefault('id_map', {})['wanvideoteacache'] = wanvideoteacache.node.id

        wanvideotorchcompilesettings_2 = WanVideoTorchCompileSettings(_id='64')
        wf.metadata.setdefault('id_map', {})['wanvideotorchcompilesettings_2'] = wanvideotorchcompilesettings_2.node.id
        vhs_loadvideo = VHS_LoadVideo(
            _id='97',
            video='wolf_interpolated.mp4',
            _outputs=('IMAGE', 'FRAME_COUNT', 'AUDIO', 'VIDEO_INFO'),
        )
        wf.metadata.setdefault('id_map', {})['vhs_loadvideo'] = vhs_loadvideo.node.id

        wanvideoloraselect = WanVideoLoraSelect(_id='98', lora=MODEL_NAME_3)
        wf.metadata.setdefault('id_map', {})['wanvideoloraselect'] = wanvideoloraselect.node.id
        wanvideotextencode = WanVideoTextEncode(
            _id='16',
            positive_prompt='video of a wolf',
            negative_prompt=DEFAULT_NEGATIVE,
            t5=loadwanvideot5textencoder,
        )
        wf.metadata.setdefault('id_map', {})['wanvideotextencode'] = wanvideotextencode.node.id

        wanvideomodelloader = WanVideoModelLoader(
            _id='22',
            model=MODEL_NAME_4,
            base_precision='fp16',
            lora=wanvideoloraselect,
        )
        wf.metadata.setdefault('id_map', {})['wanvideomodelloader'] = wanvideomodelloader.node.id

        imageblur = ImageBlur(
            _id='104',
            widget_0=4,
            widget_1=1,
            image=vhs_loadvideo.out('IMAGE'),
        )
        wf.metadata.setdefault('id_map', {})['imageblur'] = imageblur.node.id

        wanvideoencode = WanVideoEncode(
            _id='95',
            widget_0=False,
            widget_1=272,
            widget_2=272,
            widget_3=144,
            widget_4=128,
            widget_5=0,
            widget_6=1.0000000000000002,
            image=imageblur,
            vae=wanvideovaeloader,
        )
        wf.metadata.setdefault('id_map', {})['wanvideoencode'] = wanvideoencode.node.id

        wanvideocontrolembeds = WanVideoControlEmbeds(
            _id='96',
            widget_0=0,
            widget_1=0.7,
            latents=wanvideoencode,
        )
        wf.metadata.setdefault('id_map', {})['wanvideocontrolembeds'] = wanvideocontrolembeds.node.id

        wanvideosampler = WanVideoSampler(
            _id='27',
            steps=1,
            seed=DEFAULT_SEED,
            batched_cfg='',
            cache_args=wanvideoteacache,
            image_embeds=wanvideocontrolembeds,
            model=wanvideomodelloader,
            text_embeds=wanvideotextencode,
            _outputs=('SAMPLES', 'DENOISED_SAMPLES'),
        )
        wf.metadata.setdefault('id_map', {})['wanvideosampler'] = wanvideosampler.node.id

        wanvideodecode = WanVideoDecode(
            _id='28',
            samples=wanvideosampler.out('SAMPLES'),
            vae=wanvideovaeloader,
        )
        wf.metadata.setdefault('id_map', {})['wanvideodecode'] = wanvideodecode.node.id

        imageconcatmulti = ImageConcatMulti(
            _id='103',
            unused_3=None,
            image_1=imageblur,
            image_2=wanvideodecode,
        )
        wf.metadata.setdefault('id_map', {})['imageconcatmulti'] = imageconcatmulti.node.id

        # Outputs
        vhs_videocombine = VHS_VideoCombine(_id='30', images=imageconcatmulti)
        wf.metadata.setdefault('id_map', {})['vhs_videocombine'] = vhs_videocombine.node.id

        return wf.finalize(PUBLIC_INPUTS, output_type='VHS_VideoCombine', name='video', artifact_kind='video', mime_type='video/mp4', expected_cardinality='one')

