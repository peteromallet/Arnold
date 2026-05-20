# vibecomfy: generated — converted by tools/convert_ready_templates.py
# Edits will be overwritten on regeneration. Add a `# vibecomfy: manual`
# marker on the first line if hand-editing is required.
"""Auto-generated ready_template — see tools/convert_ready_templates.py."""
from __future__ import annotations

from vibecomfy.workflow import VibeWorkflow, WorkflowSource
from vibecomfy.registry.ready_template import apply_ready_template_policy


READY_METADATA = {'model_assets': [],
 'unbound_inputs': {'seed': 4925},
 'ready_template': 'video/wanvideo_wrapper_22_s2v_context_window',
 'workflow_template': 'wanvideo_wrapper_22_s2v_context_window',
 'capability': 'speech_to_video_context_window',
 'source_role': 'materialized_ready_python_template',
 'source_workflow': 'workflow_corpus/custom_nodes/wanvideo_wrapper/kijai/wan22_s2v_context_window.json',
 'coverage_tier': 'supplemental',
 'approach': 'S2V context-window workflow',
 'runtime_note': None,
 'discord_signal': None,
 'smoke_resolution': '256x256x5_frames'}

READY_REQUIREMENTS = {'models': [],
 'custom_nodes': ['ComfyUI-KJNodes', 'ComfyUI-VideoHelperSuite', 'ComfyUI-WanVideoWrapper'],
 'custom_node_refs': [{'slug': 'ComfyUI-KJNodes',
                       'source': 'git',
                       'commit': 'b7646ad70a7daa7aeb919ca542274758d26ba2df',
                       'url': 'https://github.com/kijai/ComfyUI-KJNodes.git'},
                      {'slug': 'ComfyUI-VideoHelperSuite',
                       'source': 'git',
                       'url': 'https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite.git'},
                      {'slug': 'ComfyUI-WanVideoWrapper',
                       'source': 'git',
                       'commit': 'df8f3e49daaad117cf3090cc916c83f3d001494c',
                       'url': 'https://github.com/kijai/ComfyUI-WanVideoWrapper.git'}]}


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

    wanvideotorchcompilesettings = _node(wf, 'WanVideoTorchCompileSettings', '35',
        widget_0='inductor',
        widget_1=False,
        widget_2='default',
        widget_3=False,
        widget_4=64,
        widget_5=True,
        widget_6=128,
    )
    wanvideovaeloader = _node(wf, 'WanVideoVAELoader', '38',
        widget_0='wanvideo\\Wan2_1_VAE_bf16.safetensors',
        widget_1='bf16',
    )
    wanvideoblockswap = _node(wf, 'WanVideoBlockSwap', '39',
        widget_0=25,
        widget_1=False,
        widget_2=False,
        widget_3=True,
        widget_4=0,
        widget_5=1,
        widget_6=False,
    )
    wanvideoloraselectmulti = _node(wf, 'WanVideoLoraSelectMulti', '60',
        widget_0='WanVideo\\Lightx2v\\lightx2v_T2V_14B_cfg_step_distill_v2_lora_rank64_bf16.safetensors',
        widget_1=1.5,
        widget_10=False,
        widget_11=False,
        widget_2='none',
        widget_3=1,
        widget_4='none',
        widget_5=1,
        widget_6='none',
        widget_7=1,
        widget_8='none',
        widget_9=1,
    )
    audioencoderloader = _node(wf, 'AudioEncoderLoader', '65',
        widget_0='wav2vec_xlsr_53_english_fp32.safetensors',
    )
    loadaudio = _node(wf, 'LoadAudio', '66',
        audio='NieR_ Automata - _Weight of the World_ ENG VER. by Lizz Robinett [CyOSTbel3AM].mp3',
        widget_1=None,
        widget_2=None,
    )
    wanvideotextencodecached = _node(wf, 'WanVideoTextEncodeCached', '67',
        widget_0='umt5-xxl-enc-bf16.safetensors',
        widget_1='bf16',
        widget_2='a woman is singing passionately',
        widget_3='色调艳丽，过曝，静态，细节模糊不清，字幕，风格，作品，画作，画面，静止，整体发灰，最差质量，低质量，JPEG压缩残留，丑陋的，残缺的，多余的手指，画得不好的手部，画得不好的脸部，畸形的，毁容的，形态畸形的肢体，手指融合，静止不动的画面，杂乱的背景，三条腿，背景人很多，倒着走',
        widget_4='disabled',
        widget_5=True,
        widget_6='gpu',
    )
    primitivenode = _node(wf, 'PrimitiveNode', '71',
        widget_0=201,
        widget_1='fixed',
    )
    loadimage = _node(wf, 'LoadImage', '73',
        image='2b.jpg',
        widget_1='image',
    )
    melbandroformermodelloader = _node(wf, 'MelBandRoFormerModelLoader', '81',
        widget_0='MelBandRoFormer\\MelBandRoformer_fp16.safetensors',
    )
    wanvideocontextoptions = _node(wf, 'WanVideoContextOptions', '83',
        widget_0='uniform_standard',
        widget_1=81,
        widget_2=4,
        widget_3=16,
        widget_4=True,
        widget_5=False,
        widget_6='linear',
    )
    vhs_loadaudio = _node(wf, 'VHS_LoadAudio', '94')
    downloadandloadgimmvfimodel = _node(wf, 'DownloadAndLoadGIMMVFIModel', '95',
        widget_0='gimmvfi_r_arb_lpips_fp32.safetensors',
        widget_1='fp16',
        widget_2=False,
    )
    wanvideomodelloader = _node(wf, 'WanVideoModelLoader', '22',
        widget_0='WanVideo\\S2V\\Wan2_2-S2V-14B_fp8_e4m3fn_scaled_KJ.safetensors',
        widget_1='fp16',
        widget_2='fp8_e4m3fn_scaled',
        widget_3='offload_device',
        widget_4='sdpa',
        compile_args=wanvideotorchcompilesettings.out(0),
    )
    imageresizekjv2 = _node(wf, 'ImageResizeKJv2', '74',
        height=256,
        widget_0=256,
        widget_1=256,
        widget_2='lanczos',
        widget_3='crop',
        widget_4='0, 0, 0',
        widget_5='center',
        widget_6=2,
        widget_7='cpu',
        widget_8='<tr><td>Output: </td><td><b>1</b> x <b>960</b> x <b>640 | 7.03MB</b></td></tr>',
        width=256,
        image=loadimage.out(0),
    )
    melbandroformersampler = _node(wf, 'MelBandRoFormerSampler', '82',
        audio=vhs_loadaudio.out(0),
        model=melbandroformermodelloader.out(0),
    )
    wanvideoemptyembeds = _node(wf, 'WanVideoEmptyEmbeds', '37',
        widget_0=256,
        widget_1=256,
        widget_2=5,
        height=imageresizekjv2.out(2),
        num_frames=primitivenode.out(0),
        width=imageresizekjv2.out(1),
    )
    wanvideosetloras = _node(wf, 'WanVideoSetLoRAs', '58',
        lora=wanvideoloraselectmulti.out(0),
        model=wanvideomodelloader.out(0),
    )
    previewany = _node(wf, 'PreviewAny', '62',
        source=wanvideomodelloader.out(0),
    )
    wanvideoencode = _node(wf, 'WanVideoEncode', '72',
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
    normalizeaudioloudness = _node(wf, 'NormalizeAudioLoudness', '98',
        widget_0=-23,
        audio=melbandroformersampler.out(0),
    )
    wanvideosetblockswap = _node(wf, 'WanVideoSetBlockSwap', '56',
        block_swap_args=wanvideoblockswap.out(0),
        model=wanvideosetloras.out(0),
    )
    audioencoderencode = _node(wf, 'AudioEncoderEncode', '64',
        audio=normalizeaudioloudness.out(0),
        audio_encoder=audioencoderloader.out(0),
    )
    wanvideoadds2vembeds = _node(wf, 'WanVideoAddS2VEmbeds', '101',
        widget_0=201,
        widget_1=1,
        widget_2=0,
        widget_3=1,
        widget_4=False,
        audio_encoder_output=audioencoderencode.out(0),
        embeds=wanvideoemptyembeds.out(0),
        frame_window_size=primitivenode.out(0),
        ref_latent=wanvideoencode.out(0),
    )
    wanvideosampler = _node(wf, 'WanVideoSampler', '27',
        steps=1,
        widget_0=1,
        widget_1=1,
        widget_10='comfy',
        widget_11=0,
        widget_12=-1,
        widget_13=False,
        widget_2=4,
        widget_3=45,
        widget_4='fixed',
        widget_5=True,
        widget_6='dpm++_sde',
        widget_7=0,
        widget_8=1,
        widget_9=False,
        context_options=wanvideocontextoptions.out(0),
        image_embeds=wanvideoadds2vembeds.out(0),
        model=wanvideosetblockswap.out(0),
        text_embeds=wanvideotextencodecached.out(0),
    )
    previewany_2 = _node(wf, 'PreviewAny', '69',
        source=wanvideoadds2vembeds.out(1),
    )
    wanvideodecode = _node(wf, 'WanVideoDecode', '28',
        widget_0=False,
        widget_1=272,
        widget_2=272,
        widget_3=144,
        widget_4=128,
        widget_5='default',
        samples=wanvideosampler.out(0),
        vae=wanvideovaeloader.out(0),
    )
    insertlatenttoindexed = _node(wf, 'InsertLatentToIndexed', '77',
        widget_0=0,
        destination=wanvideosampler.out(0),
        source=wanvideoencode.out(0),
    )
    getimagesizeandcount = _node(wf, 'GetImageSizeAndCount', '70',
        image=wanvideodecode.out(0),
    )
    vhs_splitimages = _node(wf, 'VHS_SplitImages', '80',
        images=getimagesizeandcount.out(0),
    )
    gimmvfi_interpolate = _node(wf, 'GIMMVFI_interpolate', '96',
        widget_0=1,
        widget_1=3,
        widget_2=0,
        widget_3='fixed',
        widget_4=False,
        gimmvfi_model=downloadandloadgimmvfimodel.out(0),
        images=vhs_splitimages.out(2),
    )
    vhs_videocombine_2 = _node(wf, 'VHS_VideoCombine', '97',
        save_output=True,
        audio=vhs_loadaudio.out(0),
        images=vhs_splitimages.out(2),
    )
    vhs_selecteverynthimage = _node(wf, 'VHS_SelectEveryNthImage', '102',
        images=gimmvfi_interpolate.out(0),
    )
    vhs_videocombine = _node(wf, 'VHS_VideoCombine', '30',
        save_output=True,
        audio=vhs_loadaudio.out(0),
        images=vhs_selecteverynthimage.out(0),
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

