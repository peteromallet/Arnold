# vibecomfy: generated — converted by tools/convert_ready_templates.py
# Edits will be overwritten on regeneration. Add a `# vibecomfy: manual`
# marker on the first line if hand-editing is required.
"""Auto-generated ready_template — see tools/convert_ready_templates.py."""
from __future__ import annotations

from vibecomfy.workflow import VibeWorkflow, WorkflowSource
from vibecomfy.registry.ready_template import apply_ready_template_policy


READY_METADATA = {'model_assets': [],
 'unbound_inputs': {'seed': 4588},
 'ready_template': 'video/wanvideo_wrapper_22_5b_ovi_audio_i2v',
 'workflow_template': 'wanvideo_wrapper_22_5b_ovi_audio_i2v',
 'capability': 'audio_image_to_video',
 'source_role': 'materialized_ready_python_template',
 'source_workflow': 'workflow_corpus/custom_nodes/wanvideo_wrapper/kijai/wan22_5b_ovi_audio_i2v.json',
 'coverage_tier': 'supplemental',
 'approach': 'Ovi image-to-video with audio',
 'runtime_note': None,
 'discord_signal': None,
 'smoke_resolution': '256x256x5_frames'}

READY_REQUIREMENTS = {'models': [], 'custom_nodes': ['ComfyUI-KJNodes', 'ComfyUI-VideoHelperSuite', 'ComfyUI-WanVideoWrapper']}


def build() -> VibeWorkflow:
    """Build the workflow (auto-generated)."""
    wf = VibeWorkflow(
        READY_METADATA["ready_template"],
        WorkflowSource(
            id=READY_METADATA["ready_template"],
            path=__file__,
            source_type="ready_template",
        ),
    )

    wanvideoextramodelselect = _node(wf, 'WanVideoExtraModelSelect', '78',
        widget_0='WanVideo/Ovi/Wan_2_1_Ovi_audio_model_bf16.safetensors',
    )
    wanvideoblockswap = _node(wf, 'WanVideoBlockSwap', '83',
        widget_0=15,
        widget_1=False,
        widget_2=False,
        widget_3=True,
        widget_4=0,
        widget_5=1,
        widget_6=False,
    )
    wanvideotextencodecached = _node(wf, 'WanVideoTextEncodeCached', '85',
        widget_0='umt5-xxl-enc-bf16.safetensors',
        widget_1='bf16',
        widget_2='A tired old man is very sarcastically saying: <S>Oh great, they are making me talk now too.<E>. <AUDCAP>Clear older male voices speaking dialogue, subtle outdoor ambience.<ENDAUDCAP>',
        widget_3='色调艳丽，过曝，静态，细节模糊不清，字幕，风格，作品，画作，画面，静止，整体发灰，最差质量，低质量，JPEG压缩残留，丑陋的，残缺的，多余的手指，画得不好的手部，画得不好的脸部，畸形的，毁容的，形态畸形的肢体，手指融合，静止不动的画面，杂乱的背景，三条腿，背景人很多，倒着走',
        widget_4='disabled',
        widget_5=False,
        widget_6='gpu',
    )
    wanvideovaeloader = _node(wf, 'WanVideoVAELoader', '87',
        widget_0='Wan2_2_VAE_bf16.safetensors',
        widget_1='bf16',
    )
    ovimmaudiovaeloader = _node(wf, 'OviMMAudioVAELoader', '89',
        widget_0='mmaudio_vae_16k_fp32.safetensors',
        widget_1='mmaudio_vocoder_bigvgan_best_netG_fp32.safetensors',
        widget_2='fp32',
    )
    wanvideotorchcompilesettings = _node(wf, 'WanVideoTorchCompileSettings', '91',
        widget_0='inductor',
        widget_1=False,
        widget_2='default',
        widget_3=False,
        widget_4=64,
        widget_5=True,
        widget_6=128,
    )
    wanvideoslg = _node(wf, 'WanVideoSLG', '93',
        widget_0='11',
        widget_1=0,
        widget_2=1,
    )
    wanvideotextencodecached_2 = _node(wf, 'WanVideoTextEncodeCached', '96',
        widget_0='umt5-xxl-enc-bf16.safetensors',
        widget_1='bf16',
        widget_2='',
        widget_3='robotic, muffled, echo, distorted',
        widget_4='disabled',
        widget_5=True,
        widget_6='gpu',
    )
    loadimage = _node(wf, 'LoadImage', '109',
        image='oldman_upscaled.png',
        widget_1='image',
    )
    wanvideoeasycache = _node(wf, 'WanVideoEasyCache', '118',
        widget_0=0.015,
        widget_1=10,
        widget_2=-1,
        widget_3='offload_device',
    )
    wanvideoemptymmaudiolatents = _node(wf, 'WanVideoEmptyMMAudioLatents', '125',
        widget_0=157,
    )
    wanvideomodelloader = _node(wf, 'WanVideoModelLoader', '12',
        widget_0='WanVideo/Ovi/Wan_2_1_Ovi_video_model_bf16.safetensors',
        widget_1='bf16',
        widget_2='disabled',
        widget_3='offload_device',
        widget_4='sdpa',
        widget_5='default',
        compile_args=wanvideotorchcompilesettings.out(0),
        extra_model=wanvideoextramodelselect.out(0),
    )
    wanvideoovicfg = _node(wf, 'WanVideoOviCFG', '94',
        widget_0=3,
        original_text_embeds=wanvideotextencodecached.out(0),
        ovi_negative_text_embeds=wanvideotextencodecached_2.out(1),
    )
    imageresizekjv2 = _node(wf, 'ImageResizeKJv2', '110',
        height=256,
        widget_0=256,
        widget_1=256,
        widget_2='lanczos',
        widget_3='crop',
        widget_4='0, 0, 0',
        widget_5='center',
        widget_6=32,
        widget_7='cpu',
        width=256,
        image=loadimage.out(0),
    )
    wanvideosetblockswap = _node(wf, 'WanVideoSetBlockSwap', '84',
        block_swap_args=wanvideoblockswap.out(0),
        model=wanvideomodelloader.out(0),
    )
    wanvideoencode = _node(wf, 'WanVideoEncode', '111',
        widget_0=False,
        widget_1=272,
        widget_2=272,
        widget_3=144,
        widget_4=128,
        widget_5=0,
        widget_6=1,
        image=imageresizekjv2.out(0),
        vae=wanvideovaeloader.out(0),
    )
    wanvideoemptyembeds = _node(wf, 'WanVideoEmptyEmbeds', '81',
        num_frames=5,
        widget_0=256,
        widget_1=256,
        widget_2=5,
        extra_latents=wanvideoencode.out(0),
        height=imageresizekjv2.out(2),
        width=imageresizekjv2.out(1),
    )
    wanvideosampler = _node(wf, 'WanVideoSampler', '80',
        steps=1,
        widget_0=1,
        widget_1=4,
        widget_10='default',
        widget_11=0,
        widget_12=-1,
        widget_13=False,
        widget_2=5,
        widget_3=42,
        widget_4='fixed',
        widget_5=True,
        widget_6='unipc',
        widget_7=0,
        widget_8=1,
        widget_9=False,
        cache_args=wanvideoeasycache.out(0),
        image_embeds=wanvideoemptyembeds.out(0),
        model=wanvideosetblockswap.out(0),
        samples=wanvideoemptymmaudiolatents.out(0),
        slg_args=wanvideoslg.out(0),
        text_embeds=wanvideoovicfg.out(0),
    )
    wanvideodecode = _node(wf, 'WanVideoDecode', '86',
        widget_0=False,
        widget_1=272,
        widget_2=272,
        widget_3=144,
        widget_4=128,
        widget_5='default',
        samples=wanvideosampler.out(0),
        vae=wanvideovaeloader.out(0),
    )
    wanvideodecodeoviaudio = _node(wf, 'WanVideoDecodeOviAudio', '90',
        mmaudio_vae=ovimmaudiovaeloader.out(0),
        samples=wanvideosampler.out(0),
    )
    vhs_videocombine = _node(wf, 'VHS_VideoCombine', '88',
        save_output=True,
        audio=wanvideodecodeoviaudio.out(0),
        images=wanvideodecode.out(0),
    )
    previewaudio = _node(wf, 'PreviewAudio', '108',
        audio=wanvideodecodeoviaudio.out(0),
    )

    wf.finalize_metadata()
    apply_ready_template_policy(wf, READY_METADATA, source_path=__file__, requirements=READY_REQUIREMENTS)
    return wf


def _node(wf: VibeWorkflow, class_type: str, _id: str, _extras: dict | None = None, **kwargs):
    """Create a node, preserving the original node id from the source workflow.

    `_extras` carries kwargs whose names are not valid Python identifiers
    (e.g. "resize_type.multiple") which Python disallows as kwarg syntax.
    They are applied to the new node post-construction.
    """
    from vibecomfy.handles import Handle
    builder = wf.node(class_type, **kwargs)
    if _extras:
        for key, value in _extras.items():
            if isinstance(value, Handle):
                wf.connect(value, f"{builder.node.id}.{key}")
            else:
                builder.node.inputs[key] = value
    if builder.node.id != _id:
        old_id = builder.node.id
        node = wf.nodes.pop(old_id)
        node.id = _id
        wf.nodes[_id] = node
        for edge in wf.edges:
            if edge.to_node == old_id:
                edge.to_node = _id
            if edge.from_node == old_id:
                edge.from_node = _id
    return builder

