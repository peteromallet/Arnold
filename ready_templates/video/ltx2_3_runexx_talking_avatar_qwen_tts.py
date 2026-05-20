# vibecomfy: generated - converted by tools/convert_ready_templates.py
# Edits will be overwritten on regeneration. Put the manual opt-out
# marker on the first line if hand-editing is required.
"""Auto-generated ready_template - see tools/convert_ready_templates.py."""
from __future__ import annotations

from vibecomfy.templates import InputSpec, ModelAsset, ReadyMetadata, finalize, new_workflow, node as raw_call, ref
from vibecomfy.nodes.core import BasicScheduler, CFGGuider, CLIPTextEncode, DualCLIPLoader, EmptyLTXVLatentVideo, GetImageSize, KSamplerSelect, LTXVAudioVAEDecode, LTXVAudioVAEEncode, LTXVAudioVAELoader, LTXVConcatAVLatent, LTXVConditioning, LTXVImgToVideoInplace, LTXVPreprocess, LTXVSeparateAVLatent, LatentUpscaleModelLoader, LoadAudio, LoadImage, LoraLoaderModelOnly, ManualSigmas, ModelSamplingSD3, PreviewAudio, PrimitiveStringMultiline, RandomNoise, ResizeImageMaskNode, SamplerCustomAdvanced, SetLatentNoiseMask, SolidMask, TrimAudioDuration, UNETLoader, VAEDecodeTiled, VAELoader
from vibecomfy.nodes.gguf import DualCLIPLoaderGGUF, UnetLoaderGGUF
from vibecomfy.nodes.kjnodes import INTConstant, ImageResizeKJv2, LTX2AttentionTunerPatch, LTX2_NAG, LTXVChunkFeedForward, PathchSageAttentionKJ, SimpleCalculatorKJ, VRAM_Debug
from vibecomfy.nodes.qwentts import AILab_Qwen3TTSVoiceClone
from vibecomfy.nodes.videohelpersuite import VHS_VideoCombine


CONTROL_AFTER_GENERATE = 'fixed'
DEFAULT_PROMPT = 'text, subtitles, logo, still image, still video, no motion, static, frozen, blurry, low quality, distorted, bad anatomy, oversaturated, pixelated, low resolution, grainy, compression artifacts, jpeg artifacts, glitches, watermark, signature, copyright,  distortedsound, saturated sound, loud sound , deformed facial features, asymmetrical face, missing facial features, extra limbs, disfigured hands, blurry teeth, disfigured teeth'
DEFAULT_SEED = 420
DEFAULT_SEED_2 = 42
GUIDE_STRENGTH = 0.6
GUIDE_STRENGTH_2 = 2.5
MODEL_NAME = 'LTX23_video_vae_bf16.safetensors'
MODEL_NAME_10 = 'MelBandRoformer\\MelBandRoformer_fp16.safetensors'
MODEL_NAME_11 = 'LTX\\LTX-2\\ltx-2.3-22b-distilled-lora-384.safetensors'
MODEL_NAME_2 = 'ltx-2.3-spatial-upscaler-x2-1.1.safetensors'
MODEL_NAME_3 = 'gemma_3_12B_it_fp4_mixed.safetensors'
MODEL_NAME_4 = 'ltx-2.3_text_projection_bf16.safetensors'
MODEL_NAME_5 = 'LTX23_audio_vae_bf16.safetensors'
MODEL_NAME_6 = 'taeltx2_3.safetensors'
MODEL_NAME_7 = 'ltx-2.3-22b-distilled_transformer_only_fp8_scaled.safetensors'
MODEL_NAME_8 = 'LTXvideo\\LTX-2\\quantstack\\LTX-2.3-distilled-Q4_K_S.gguf'
MODEL_NAME_9 = 'gemma-3-12b-it-Q2_K.gguf'
WIDGET_0 = 'vae'
WIDGET_0_10 = 'ref_image'
WIDGET_0_11 = 'vae_audio'
WIDGET_0_12 = 'upscale_model'
WIDGET_0_13 = 'negative'
WIDGET_0_14 = 'positive'
WIDGET_0_15 = 't2v_mode'
WIDGET_0_16 = 'model'
WIDGET_0_17 = 'model_with_lora'
WIDGET_0_18 = 'vae_tiny'
WIDGET_0_19 = 'latent'
WIDGET_0_2 = 'clip'
WIDGET_0_20 = 'latent_custom_audio'
WIDGET_0_21 = 'enhance_prompt'
WIDGET_0_3 = 'width'
WIDGET_0_4 = 'height'
WIDGET_0_5 = 'frames'
WIDGET_0_6 = 'fps'
WIDGET_0_7 = 'audio_tts'
WIDGET_0_8 = 'height_downscaled'
WIDGET_0_9 = 'width_downscaled'


MODELS = {}

PUBLIC_INPUTS = {
    'model': InputSpec(node=ref('latentupscalemodelloader'), field='model_name', default=MODEL_NAME_2),
    'seed': InputSpec(node=ref('randomnoise'), field='noise_seed', default=DEFAULT_SEED),
    'prompt': InputSpec(node=ref('cliptextencode_2'), field='text', default=DEFAULT_PROMPT),
    'steps': InputSpec(node=ref('basicscheduler'), field='steps', default=8),
    'use_lora': InputSpec(node=ref('primitiveboolean'), field='value', default=False),
    'image': InputSpec(node=ref('loadimage'), field='image', default='17745317855d08.png'),
    'input_image': InputSpec(node=ref('loadimage'), field='image', default='17745317855d08.png'),
}

READY_METADATA = ReadyMetadata.build(
    capability='tts_talking_avatar',
    inputs=PUBLIC_INPUTS,
    models=MODELS,
    requirements={'models': ['LTX23_audio_vae_bf16.safetensors', 'LTX23_video_vae_bf16.safetensors', 'LTX\\LTX-2\\ltx-2.3-22b-distilled-lora-384.safetensors', 'LTXvideo\\LTX-2\\quantstack\\LTX-2.3-distilled-Q4_K_S.gguf', 'euler_ancestral_cfg_pp', 'euler_cfg_pp', 'ltx-2.3-22b-distilled_transformer_only_fp8_scaled.safetensors', 'ltx-2.3-spatial-upscaler-x2-1.1.safetensors', 'taeltx2_3.safetensors'], 'custom_nodes': ['ComfyUI-GGUF', 'ComfyUI-KJNodes', 'ComfyUI-LTXVideo', 'ComfyUI-QwenTTS', 'ComfyUI-VideoHelperSuite', 'rgthree-comfy']},
    custom_node_packs={'ComfyUI-GGUF': {'commit': '6ea2651e7df66d7585f6ffee804b20e92fb38b8a', 'url': 'https://github.com/city96/ComfyUI-GGUF.git', 'class_schema_sha256': '1336fad984841444a9559b602c34ef11d1dd4b68a9a902437aaee6771ab5d2d3', 'classes_used': ['DualCLIPLoaderGGUF', 'UnetLoaderGGUF'], 'pip_packages': ['gguf'], 'status': 'pinned'}, 'ComfyUI-KJNodes': {'commit': 'b7646ad70a7daa7aeb919ca542274758d26ba2df', 'url': 'https://github.com/kijai/ComfyUI-KJNodes.git', 'class_schema_sha256': '1beaf129c8fa26175d89a28f9ca10d08b5ac27c8fc9bff920263fcbba17cb691', 'classes_used': ['GetImageSize', 'INTConstant', 'ImageResizeKJv2', 'PathchSageAttentionKJ', 'SimpleCalculatorKJ'], 'pip_packages': ['matplotlib'], 'status': 'pinned'}, 'ComfyUI-LTXVideo': {'commit': '229437c6b65796d6a7a63ae34be2bd5ba31fa543', 'url': 'https://github.com/Lightricks/ComfyUI-LTXVideo.git', 'class_schema_sha256': '82e0b1f31509a969cf441c45e2517d0cd93f31b5390cc16f4a0ffa244421f39e', 'classes_used': ['EmptyLTXVLatentVideo', 'LTX2AttentionTunerPatch', 'LTX2_NAG', 'LTXVAudioVAEDecode', 'LTXVAudioVAELoader', 'LTXVChunkFeedForward', 'LTXVConcatAVLatent', 'LTXVConditioning', 'LTXVPreprocess', 'LTXVSeparateAVLatent', 'LatentUpscaleModelLoader'], 'pip_packages': [], 'status': 'pinned'}, 'ComfyUI-QwenTTS': {'commit': 'd8122a8ba835b65fd65c113d2b273b1ad1579293', 'url': 'https://github.com/1038lab/ComfyUI-QwenTTS.git', 'class_schema_sha256': '4137bb4f37ea178be0e794377829905d9ede1bc65496a23a51d766a3f03b2c84', 'classes_used': ['AILab_Qwen3TTSVoiceClone'], 'pip_packages': ['accelerate', 'librosa', 'openai-whisper', 'qwen-tts', 'soundfile', 'tiktoken'], 'status': 'pinned'}, 'ComfyUI-VideoHelperSuite': {'commit': '4ee72c065db22c9d96c2427954dc69e7b908444b', 'url': 'https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite.git', 'class_schema_sha256': '8391e679554eecd5d324a3e34a713ff240e619e3a07476587845ba18c9fae310', 'classes_used': ['VHS_VideoCombine'], 'pip_packages': [], 'status': 'pinned'}, 'rgthree-comfy': {'commit': '738105af5fb14e96fbecaf406dc356e284797e8c', 'url': 'https://github.com/rgthree/rgthree-comfy.git', 'class_schema_sha256': '2b52072e02c59cb05ce83e5c45e1c7fd5b1273fee9b62eaaa0e66a81a4c07872', 'classes_used': ['GetNode', 'Power Lora Loader (rgthree)', 'SetNode'], 'pip_packages': [], 'status': 'pinned'}},
    smoke_resolution='256x256x5_frames',
    approach='Qwen TTS talking avatar',
    ltx_best_practices=['Use the official Lightricks workflows as runtime gates where possible.', 'Patch smoke runs to fp8/fp4 model assets, tiny frame counts, and low-VRAM loaders.', 'Bypass latent spatial upscalers in smoke runs until HiddenSwitch Comfy exposes model_mmap_residency for LatentUpscaleModelManageable.', 'Keep community audio, lip-sync, and long-form workflows as ready templates until their custom node packs and service credentials are declared.'],
    comfy_configuration={'reserve_vram': 12, 'cache_none': True, 'fp8_e4m3fn_text_enc': True},
    provenance={'source_workflow': 'workflow_corpus/custom_nodes/ltxvideo/runexx/LTX-2.3_Talking_Avatar_Qwen_TTS.json'},
)

def build() -> VibeWorkflow:
    """Build the workflow (auto-generated)."""
    with new_workflow(READY_METADATA, source_path=__file__) as wf:

        getnode = raw_call(wf, 'GetNode', '413', widget_0=WIDGET_0)
        wf.metadata.setdefault('id_map', {})['getnode'] = getnode.node.id
        # Inputs
        loadimage = LoadImage(
            _id='444',
            image='17745317855d08.png',
            _outputs=('IMAGE', 'MASK'),
        )
        wf.metadata.setdefault('id_map', {})['loadimage'] = loadimage.node.id

        # Loaders
        vaeloader = VAELoader(_id='1559', vae_name=MODEL_NAME)
        wf.metadata.setdefault('id_map', {})['vaeloader'] = vaeloader.node.id
        latentupscalemodelloader = LatentUpscaleModelLoader(
            _id='1561',
            model_name=MODEL_NAME_2,
        )
        wf.metadata.setdefault('id_map', {})['latentupscalemodelloader'] = latentupscalemodelloader.node.id

        dualcliploader = DualCLIPLoader(
            _id='1562',
            clip_name1=MODEL_NAME_3,
            clip_name2=MODEL_NAME_4,
            type_='ltxv',
            device='default',
        )
        wf.metadata.setdefault('id_map', {})['dualcliploader'] = dualcliploader.node.id

        ltxvaudiovaeloader = LTXVAudioVAELoader(_id='1567', ckpt_name=MODEL_NAME_5)
        wf.metadata.setdefault('id_map', {})['ltxvaudiovaeloader'] = ltxvaudiovaeloader.node.id
        vaeloader_2 = VAELoader(_id='1569', vae_name=MODEL_NAME_6)
        wf.metadata.setdefault('id_map', {})['vaeloader_2'] = vaeloader_2.node.id
        unetloader = UNETLoader(_id='1570', unet_name=MODEL_NAME_7)
        wf.metadata.setdefault('id_map', {})['unetloader'] = unetloader.node.id
        unetloadergguf = UnetLoaderGGUF(_id='1571', unet_name=MODEL_NAME_8)
        wf.metadata.setdefault('id_map', {})['unetloadergguf'] = unetloadergguf.node.id
        dualcliploadergguf = DualCLIPLoaderGGUF(
            _id='1573',
            clip_name1=MODEL_NAME_9,
            clip_name2=MODEL_NAME_4,
            type_='sdxl',
        )
        wf.metadata.setdefault('id_map', {})['dualcliploadergguf'] = dualcliploadergguf.node.id

        intconstant = INTConstant(_id='1583', value=10)
        wf.metadata.setdefault('id_map', {})['intconstant'] = intconstant.node.id
        # Inputs
        primitivefloat = raw_call(wf, 'PrimitiveFloat', '1586', value=8)
        wf.metadata.setdefault('id_map', {})['primitivefloat'] = primitivefloat.node.id
        intconstant_2 = INTConstant(_id='1591', value=960)
        wf.metadata.setdefault('id_map', {})['intconstant_2'] = intconstant_2.node.id
        intconstant_3 = INTConstant(_id='1606', value=544)
        wf.metadata.setdefault('id_map', {})['intconstant_3'] = intconstant_3.node.id
        getnode_2 = raw_call(wf, 'GetNode', '1619', widget_0=WIDGET_0_2)
        wf.metadata.setdefault('id_map', {})['getnode_2'] = getnode_2.node.id
        getnode_3 = raw_call(wf, 'GetNode', '1622', widget_0=WIDGET_0_2)
        wf.metadata.setdefault('id_map', {})['getnode_3'] = getnode_3.node.id
        primitivestringmultiline = PrimitiveStringMultiline(
            _id='1624',
            value="A video from a TV broadcast with a male and a female news achor. They both stay in frame all the time.\n\nThe dialog from the male and female is as follows:\n\nSpaker_1 is the woman, and Speaker_2 is the man.\n\n[speaker_1][confused]: This is awkward! I guess the prompter ran out of ideas, and put us in this odd situation.\n[speaker_2][embarrassed] : But hey,  just because we are here, in a new video, doesn't mean our voices change. \n[speaker_1][excited]: Aber ich möchte mit dir schlafen.\n[speaker_2][happy]: I still have no idea what she said! Might be for the best [laughing]\n\nThe dialog with perfect lip-sync to the audio\n\n\nThey both smile at the end.\n\n\n",
        )
        wf.metadata.setdefault('id_map', {})['primitivestringmultiline'] = primitivestringmultiline.node.id

        getnode_4 = raw_call(wf, 'GetNode', '1628', widget_0=WIDGET_0_3)
        wf.metadata.setdefault('id_map', {})['getnode_4'] = getnode_4.node.id
        getnode_5 = raw_call(wf, 'GetNode', '1629', widget_0=WIDGET_0_4)
        wf.metadata.setdefault('id_map', {})['getnode_5'] = getnode_5.node.id
        getnode_6 = raw_call(wf, 'GetNode', '1635', widget_0=WIDGET_0_5)
        wf.metadata.setdefault('id_map', {})['getnode_6'] = getnode_6.node.id
        getnode_7 = raw_call(wf, 'GetNode', '1636', widget_0=WIDGET_0_6)
        wf.metadata.setdefault('id_map', {})['getnode_7'] = getnode_7.node.id
        getnode_8 = raw_call(wf, 'GetNode', '1784', widget_0=WIDGET_0_7)
        wf.metadata.setdefault('id_map', {})['getnode_8'] = getnode_8.node.id
        getnode_9 = raw_call(wf, 'GetNode', '1807', widget_0=WIDGET_0_8)
        wf.metadata.setdefault('id_map', {})['getnode_9'] = getnode_9.node.id
        getnode_10 = raw_call(wf, 'GetNode', '1808', widget_0=WIDGET_0_9)
        wf.metadata.setdefault('id_map', {})['getnode_10'] = getnode_10.node.id
        getnode_11 = raw_call(wf, 'GetNode', '1809', widget_0=WIDGET_0_10)
        wf.metadata.setdefault('id_map', {})['getnode_11'] = getnode_11.node.id
        getnode_12 = raw_call(wf, 'GetNode', '1814', widget_0=WIDGET_0)
        wf.metadata.setdefault('id_map', {})['getnode_12'] = getnode_12.node.id
        getnode_13 = raw_call(wf, 'GetNode', '1815', widget_0=WIDGET_0_11)
        wf.metadata.setdefault('id_map', {})['getnode_13'] = getnode_13.node.id
        getnode_14 = raw_call(wf, 'GetNode', '1816', widget_0=WIDGET_0)
        wf.metadata.setdefault('id_map', {})['getnode_14'] = getnode_14.node.id
        getnode_15 = raw_call(wf, 'GetNode', '1817', widget_0=WIDGET_0_12)
        wf.metadata.setdefault('id_map', {})['getnode_15'] = getnode_15.node.id
        getnode_16 = raw_call(wf, 'GetNode', '1820', widget_0=WIDGET_0_13)
        wf.metadata.setdefault('id_map', {})['getnode_16'] = getnode_16.node.id
        getnode_17 = raw_call(wf, 'GetNode', '1821', widget_0=WIDGET_0_14)
        wf.metadata.setdefault('id_map', {})['getnode_17'] = getnode_17.node.id
        getnode_18 = raw_call(wf, 'GetNode', '1822', widget_0=WIDGET_0_6)
        wf.metadata.setdefault('id_map', {})['getnode_18'] = getnode_18.node.id
        getnode_19 = raw_call(wf, 'GetNode', '1823', widget_0=WIDGET_0_15)
        wf.metadata.setdefault('id_map', {})['getnode_19'] = getnode_19.node.id
        getnode_20 = raw_call(wf, 'GetNode', '1824', widget_0=WIDGET_0_10)
        wf.metadata.setdefault('id_map', {})['getnode_20'] = getnode_20.node.id
        getnode_21 = raw_call(wf, 'GetNode', '1828', widget_0=WIDGET_0_16)
        wf.metadata.setdefault('id_map', {})['getnode_21'] = getnode_21.node.id
        getnode_22 = raw_call(wf, 'GetNode', '1829', widget_0=WIDGET_0_13)
        wf.metadata.setdefault('id_map', {})['getnode_22'] = getnode_22.node.id
        getnode_23 = raw_call(wf, 'GetNode', '1830', widget_0=WIDGET_0_14)
        wf.metadata.setdefault('id_map', {})['getnode_23'] = getnode_23.node.id
        getnode_24 = raw_call(wf, 'GetNode', '1831', widget_0=WIDGET_0_17)
        wf.metadata.setdefault('id_map', {})['getnode_24'] = getnode_24.node.id
        randomnoise = RandomNoise(
            _id='1832',
            noise_seed=DEFAULT_SEED,
            control_after_generate=CONTROL_AFTER_GENERATE,
        )
        wf.metadata.setdefault('id_map', {})['randomnoise'] = randomnoise.node.id

        getnode_25 = raw_call(wf, 'GetNode', '1833', widget_0=WIDGET_0_18)
        wf.metadata.setdefault('id_map', {})['getnode_25'] = getnode_25.node.id
        getnode_26 = raw_call(wf, 'GetNode', '1834', widget_0=WIDGET_0_17)
        wf.metadata.setdefault('id_map', {})['getnode_26'] = getnode_26.node.id
        getnode_27 = raw_call(wf, 'GetNode', '1835', widget_0=WIDGET_0_16)
        wf.metadata.setdefault('id_map', {})['getnode_27'] = getnode_27.node.id
        getnode_28 = raw_call(wf, 'GetNode', '1841', widget_0=WIDGET_0_16)
        wf.metadata.setdefault('id_map', {})['getnode_28'] = getnode_28.node.id
        randomnoise_2 = RandomNoise(
            _id='1842',
            noise_seed=DEFAULT_SEED_2,
            control_after_generate=CONTROL_AFTER_GENERATE,
        )
        wf.metadata.setdefault('id_map', {})['randomnoise_2'] = randomnoise_2.node.id

        getnode_29 = raw_call(wf, 'GetNode', '1843', widget_0=WIDGET_0_13)
        wf.metadata.setdefault('id_map', {})['getnode_29'] = getnode_29.node.id
        manualsigmas = ManualSigmas(_id='1851', sigmas='0.85, 0.7250, 0.4219, 0.0')
        wf.metadata.setdefault('id_map', {})['manualsigmas'] = manualsigmas.node.id
        # Sampling
        ksamplerselect = KSamplerSelect(_id='1852', sampler_name='euler_cfg_pp')
        wf.metadata.setdefault('id_map', {})['ksamplerselect'] = ksamplerselect.node.id
        ksamplerselect_2 = KSamplerSelect(
            _id='1853',
            sampler_name='euler_ancestral_cfg_pp',
        )
        wf.metadata.setdefault('id_map', {})['ksamplerselect_2'] = ksamplerselect_2.node.id

        getnode_30 = raw_call(wf, 'GetNode', '1855', widget_0=WIDGET_0_19)
        wf.metadata.setdefault('id_map', {})['getnode_30'] = getnode_30.node.id
        manualsigmas_2 = ManualSigmas(
            _id='1857',
            sigmas='1.0, 0.99375, 0.9875, 0.98125, 0.975, 0.909375, 0.725, 0.421875, 0.0',
        )
        wf.metadata.setdefault('id_map', {})['manualsigmas_2'] = manualsigmas_2.node.id

        primitiveboolean = raw_call(wf, 'PrimitiveBoolean', '1862', value=False)
        wf.metadata.setdefault('id_map', {})['primitiveboolean'] = primitiveboolean.node.id
        reroute = raw_call(wf, 'Reroute', '1865')
        wf.metadata.setdefault('id_map', {})['reroute'] = reroute.node.id
        getnode_31 = raw_call(wf, 'GetNode', '1878', widget_0=WIDGET_0_16)
        wf.metadata.setdefault('id_map', {})['getnode_31'] = getnode_31.node.id
        getnode_32 = raw_call(wf, 'GetNode', '1887', widget_0=WIDGET_0_4)
        wf.metadata.setdefault('id_map', {})['getnode_32'] = getnode_32.node.id
        getnode_33 = raw_call(wf, 'GetNode', '1888', widget_0=WIDGET_0_3)
        wf.metadata.setdefault('id_map', {})['getnode_33'] = getnode_33.node.id
        getnode_34 = raw_call(wf, 'GetNode', '1889', widget_0=WIDGET_0_11)
        wf.metadata.setdefault('id_map', {})['getnode_34'] = getnode_34.node.id
        getnode_35 = raw_call(wf, 'GetNode', '1894', widget_0=WIDGET_0_20)
        wf.metadata.setdefault('id_map', {})['getnode_35'] = getnode_35.node.id
        getnode_36 = raw_call(wf, 'GetNode', '1898', widget_0=WIDGET_0_6)
        wf.metadata.setdefault('id_map', {})['getnode_36'] = getnode_36.node.id
        primitiveboolean_2 = raw_call(wf, 'PrimitiveBoolean', '1929', value=True)
        wf.metadata.setdefault('id_map', {})['primitiveboolean_2'] = primitiveboolean_2.node.id
        getnode_37 = raw_call(wf, 'GetNode', '1931', widget_0=WIDGET_0_21)
        wf.metadata.setdefault('id_map', {})['getnode_37'] = getnode_37.node.id
        getnode_38 = raw_call(wf, 'GetNode', '1935', widget_0=WIDGET_0_15)
        wf.metadata.setdefault('id_map', {})['getnode_38'] = getnode_38.node.id
        melbandroformermodelloader = raw_call(wf, 'MelBandRoFormerModelLoader', '1937',
            widget_0=MODEL_NAME_10,
        )
        wf.metadata.setdefault('id_map', {})['melbandroformermodelloader'] = melbandroformermodelloader.node.id

        primitivestringmultiline_2 = PrimitiveStringMultiline(_id='1938', value='')
        wf.metadata.setdefault('id_map', {})['primitivestringmultiline_2'] = primitivestringmultiline_2.node.id
        loadaudio = LoadAudio(_id='1941', audio='d1b26d5a32db420183fa17af9c699278.mp3')
        wf.metadata.setdefault('id_map', {})['loadaudio'] = loadaudio.node.id
        primitivestringmultiline_3 = PrimitiveStringMultiline(
            _id='1942',
            value='So what if you just want to prompt. Text to video works fine as well. Go generate some while I enjoy my coffee. ',
        )
        wf.metadata.setdefault('id_map', {})['primitivestringmultiline_3'] = primitivestringmultiline_3.node.id

        emptyltxvlatentvideo = EmptyLTXVLatentVideo(
            _id='344',
            width=getnode_10.out(0),
            height=getnode_9.out(0),
            length=getnode_6.out(0),
        )
        wf.metadata.setdefault('id_map', {})['emptyltxvlatentvideo'] = emptyltxvlatentvideo.node.id

        imageresizekjv2 = ImageResizeKJv2(
            _id='445',
            upscale_method='lanczos',
            keep_proportion='crop',
            device='cpu',
            width=getnode_4.out(0),
            height=getnode_5.out(0),
            image=loadimage.out('IMAGE'),
            _outputs=('IMAGE', 'WIDTH', 'HEIGHT', 'MASK'),
        )
        wf.metadata.setdefault('id_map', {})['imageresizekjv2'] = imageresizekjv2.node.id

        ltxvpreprocess = LTXVPreprocess(
            _id='446',
            img_compression=18,
            image=getnode_11.out(0),
        )
        wf.metadata.setdefault('id_map', {})['ltxvpreprocess'] = ltxvpreprocess.node.id

        setnode_4 = raw_call(wf, 'SetNode', '1555',
            widget_0=WIDGET_0_12,
            LATENT_UPSCALE_MODEL=latentupscalemodelloader,
        )
        wf.metadata.setdefault('id_map', {})['setnode_4'] = setnode_4.node.id

        setnode_5 = raw_call(wf, 'SetNode', '1556',
            widget_0=WIDGET_0_11,
            VAE=ltxvaudiovaeloader,
        )
        wf.metadata.setdefault('id_map', {})['setnode_5'] = setnode_5.node.id

        setnode_6 = raw_call(wf, 'SetNode', '1557', widget_0=WIDGET_0, VAE=vaeloader)
        wf.metadata.setdefault('id_map', {})['setnode_6'] = setnode_6.node.id
        setnode_7 = raw_call(wf, 'SetNode', '1558',
            widget_0=WIDGET_0_2,
            CLIP=dualcliploader,
        )
        wf.metadata.setdefault('id_map', {})['setnode_7'] = setnode_7.node.id

        loraloadermodelonly = LoraLoaderModelOnly(
            _id='1560',
            lora_name=MODEL_NAME_11,
            strength_model=GUIDE_STRENGTH,
            model=unetloader,
        )
        wf.metadata.setdefault('id_map', {})['loraloadermodelonly'] = loraloadermodelonly.node.id

        setnode_8 = raw_call(wf, 'SetNode', '1568',
            widget_0=WIDGET_0_18,
            VAE=vaeloader_2,
        )
        wf.metadata.setdefault('id_map', {})['setnode_8'] = setnode_8.node.id

        setnode_9 = raw_call(wf, 'SetNode', '1575',
            widget_0=WIDGET_0_4,
            INT=intconstant_2,
        )
        wf.metadata.setdefault('id_map', {})['setnode_9'] = setnode_9.node.id

        setnode_10 = raw_call(wf, 'SetNode', '1576',
            widget_0=WIDGET_0_3,
            INT=intconstant_3,
        )
        wf.metadata.setdefault('id_map', {})['setnode_10'] = setnode_10.node.id

        setnode_11 = raw_call(wf, 'SetNode', '1577',
            widget_0=WIDGET_0_6,
            FLOAT=primitivefloat,
        )
        wf.metadata.setdefault('id_map', {})['setnode_11'] = setnode_11.node.id

        # Conditioning
        cliptextencode_2 = CLIPTextEncode(
            _id='1626',
            text=DEFAULT_PROMPT,
            clip=getnode_3.out(0),
        )
        wf.metadata.setdefault('id_map', {})['cliptextencode_2'] = cliptextencode_2.node.id

        cfgguider = CFGGuider(
            _id='1836',
            cfg=GUIDE_STRENGTH_2,
            model=getnode_27.out(0),
            negative=getnode_16.out(0),
            positive=getnode_17.out(0),
        )
        wf.metadata.setdefault('id_map', {})['cfgguider'] = cfgguider.node.id

        ltx2_nag = LTX2_NAG(
            _id='1844',
            model=getnode_26.out(0),
            nag_cond_audio=getnode_29.out(0),
            nag_cond_video=getnode_29.out(0),
        )
        wf.metadata.setdefault('id_map', {})['ltx2_nag'] = ltx2_nag.node.id

        cfgguider_2 = CFGGuider(
            _id='1856',
            cfg=GUIDE_STRENGTH_2,
            model=getnode_28.out(0),
            negative=getnode_22.out(0),
            positive=getnode_23.out(0),
        )
        wf.metadata.setdefault('id_map', {})['cfgguider_2'] = cfgguider_2.node.id

        setnode_19 = raw_call(wf, 'SetNode', '1861',
            widget_0=WIDGET_0_15,
            BOOLEAN=primitiveboolean,
        )
        wf.metadata.setdefault('id_map', {})['setnode_19'] = setnode_19.node.id

        modelsamplingsd3 = ModelSamplingSD3(
            _id='1876',
            shift=13,
            model=getnode_31.out(0),
        )
        wf.metadata.setdefault('id_map', {})['modelsamplingsd3'] = modelsamplingsd3.node.id

        solidmask = SolidMask(
            _id='1890',
            widget_0=0,
            widget_1=512,
            widget_2=512,
            height=getnode_32.out(0),
            width=getnode_33.out(0),
        )
        wf.metadata.setdefault('id_map', {})['solidmask'] = solidmask.node.id

        ltxvaudiovaeencode = LTXVAudioVAEEncode(
            _id='1893',
            audio=reroute.out(0),
            audio_vae=getnode_34.out(0),
        )
        wf.metadata.setdefault('id_map', {})['ltxvaudiovaeencode'] = ltxvaudiovaeencode.node.id

        simplecalculatorkj = SimpleCalculatorKJ(
            _id='1897',
            expression='((round((a * b -1) / 8)) * 8) + 1 ',
            _outputs=('FLOAT', 'INT', 'BOOLEAN'),
            **{'variables.a': intconstant, 'variables.b': getnode_36.out(0)},
        )
        wf.metadata.setdefault('id_map', {})['simplecalculatorkj'] = simplecalculatorkj.node.id

        modelsamplingsd3_2 = ModelSamplingSD3(
            _id='1912',
            shift=13,
            model=getnode_27.out(0),
        )
        wf.metadata.setdefault('id_map', {})['modelsamplingsd3_2'] = modelsamplingsd3_2.node.id

        n_63e8c999_0a69_4f62_af3f_8b77f0095971 = raw_call(wf, '63e8c999-0a69-4f62-af3f-8b77f0095971', '1920',
            audio=reroute.out(0),
        )
        wf.metadata.setdefault('id_map', {})['n_63e8c999_0a69_4f62_af3f_8b77f0095971'] = n_63e8c999_0a69_4f62_af3f_8b77f0095971.node.id

        setnode_22 = raw_call(wf, 'SetNode', '1930',
            widget_0=WIDGET_0_21,
            BOOLEAN=primitiveboolean_2,
        )
        wf.metadata.setdefault('id_map', {})['setnode_22'] = setnode_22.node.id

        trimaudioduration = TrimAudioDuration(
            _id='1939',
            widget_0=0,
            widget_1=15,
            audio=loadaudio,
        )
        wf.metadata.setdefault('id_map', {})['trimaudioduration'] = trimaudioduration.node.id

        pathchsageattentionkj = PathchSageAttentionKJ(
            _id='268',
            sage_attention='disabled',
            model=loraloadermodelonly,
        )
        wf.metadata.setdefault('id_map', {})['pathchsageattentionkj'] = pathchsageattentionkj.node.id

        setnode_3 = raw_call(wf, 'SetNode', '650',
            widget_0=WIDGET_0_10,
            IMAGE=imageresizekjv2.out('IMAGE'),
        )
        wf.metadata.setdefault('id_map', {})['setnode_3'] = setnode_3.node.id

        setnode_12 = raw_call(wf, 'SetNode', '1578',
            widget_0=WIDGET_0_5,
            _extras={'*': n_63e8c999_0a69_4f62_af3f_8b77f0095971.out(0)},
        )
        wf.metadata.setdefault('id_map', {})['setnode_12'] = setnode_12.node.id

        resizeimagemasknode = ResizeImageMaskNode(
            _id='1630',
            resize_type='scale by multiplier',
            input=imageresizekjv2.out('IMAGE'),
        )
        wf.metadata.setdefault('id_map', {})['resizeimagemasknode'] = resizeimagemasknode.node.id

        setnode_17 = raw_call(wf, 'SetNode', '1840',
            widget_0=WIDGET_0_16,
            MODEL=ltx2_nag,
        )
        wf.metadata.setdefault('id_map', {})['setnode_17'] = setnode_17.node.id

        # Sampling
        samplercustomadvanced_2 = SamplerCustomAdvanced(
            _id='1845',
            guider=cfgguider_2,
            latent_image=getnode_30.out(0),
            noise=randomnoise_2,
            sampler=ksamplerselect_2,
            sigmas=manualsigmas_2,
            _outputs=('OUTPUT', 'DENOISED_OUTPUT'),
        )
        wf.metadata.setdefault('id_map', {})['samplercustomadvanced_2'] = samplercustomadvanced_2.node.id

        basicscheduler = BasicScheduler(
            _id='1877',
            scheduler=1,
            steps=1,
            widget_1=8,
            model=modelsamplingsd3,
        )
        wf.metadata.setdefault('id_map', {})['basicscheduler'] = basicscheduler.node.id

        setlatentnoisemask = SetLatentNoiseMask(
            _id='1892',
            mask=solidmask,
            samples=ltxvaudiovaeencode,
        )
        wf.metadata.setdefault('id_map', {})['setlatentnoisemask'] = setlatentnoisemask.node.id

        basicscheduler_2 = BasicScheduler(
            _id='1911',
            scheduler=1,
            steps=1,
            widget_1=4,
            model=modelsamplingsd3_2,
        )
        wf.metadata.setdefault('id_map', {})['basicscheduler_2'] = basicscheduler_2.node.id

        setnode_21 = raw_call(wf, 'SetNode', '1918',
            widget_0='frames_seconds',
            INT=simplecalculatorkj.out('INT'),
        )
        wf.metadata.setdefault('id_map', {})['setnode_21'] = setnode_21.node.id

        ltxvimgtovideoinplace_2 = LTXVImgToVideoInplace(
            _id='1934',
            widget_0=0.7,
            widget_1=False,
            bypass=getnode_38.out(0),
            image=ltxvpreprocess,
            latent=emptyltxvlatentvideo,
            vae=getnode.out(0),
        )
        wf.metadata.setdefault('id_map', {})['ltxvimgtovideoinplace_2'] = ltxvimgtovideoinplace_2.node.id

        melbandroformersampler = raw_call(wf, 'MelBandRoFormerSampler', '1936',
            audio=trimaudioduration,
            model=melbandroformermodelloader.out(0),
        )
        wf.metadata.setdefault('id_map', {})['melbandroformersampler'] = melbandroformersampler.node.id

        ltxvconcatavlatent = LTXVConcatAVLatent(
            _id='350',
            audio_latent=getnode_35.out(0),
            video_latent=ltxvimgtovideoinplace_2,
        )
        wf.metadata.setdefault('id_map', {})['ltxvconcatavlatent'] = ltxvconcatavlatent.node.id

        ltxvchunkfeedforward = LTXVChunkFeedForward(
            _id='504',
            model=pathchsageattentionkj,
        )
        wf.metadata.setdefault('id_map', {})['ltxvchunkfeedforward'] = ltxvchunkfeedforward.node.id

        getimagesize = GetImageSize(
            _id='1631',
            image=resizeimagemasknode,
            _outputs=('WIDTH', 'HEIGHT', 'BATCH_SIZE'),
        )
        wf.metadata.setdefault('id_map', {})['getimagesize'] = getimagesize.node.id

        ltxvseparateavlatent = LTXVSeparateAVLatent(
            _id='1827',
            av_latent=samplercustomadvanced_2.out('OUTPUT'),
            _outputs=('VIDEO_LATENT', 'AUDIO_LATENT'),
        )
        wf.metadata.setdefault('id_map', {})['ltxvseparateavlatent'] = ltxvseparateavlatent.node.id

        setnode_20 = raw_call(wf, 'SetNode', '1891',
            widget_0=WIDGET_0_20,
            LATENT=setlatentnoisemask,
        )
        wf.metadata.setdefault('id_map', {})['setnode_20'] = setnode_20.node.id

        a8d7fd9f_52aa_447a_9766_53cb91c0ef18 = raw_call(wf, 'a8d7fd9f-52aa-447a-9766-53cb91c0ef18', '1926',
            _1=primitivestringmultiline,
            clip=getnode_2.out(0),
            image=resizeimagemasknode,
        )
        wf.metadata.setdefault('id_map', {})['a8d7fd9f_52aa_447a_9766_53cb91c0ef18'] = a8d7fd9f_52aa_447a_9766_53cb91c0ef18.node.id

        ailab_qwen3ttsvoiceclone = AILab_Qwen3TTSVoiceClone(
            _id='1944',
            widget_0='Hello, this is a cloned voice.',
            widget_1='1.7B',
            widget_2='Auto',
            widget_3='',
            widget_4=True,
            widget_5=986337553816914,
            widget_6=116899311982882,
            widget_7='randomize',
            reference_audio=melbandroformersampler.out(0),
            reference_text=primitivestringmultiline_2,
            target_text=primitivestringmultiline_3,
        )
        wf.metadata.setdefault('id_map', {})['ailab_qwen3ttsvoiceclone'] = ailab_qwen3ttsvoiceclone.node.id

        ltx2attentiontunerpatch = LTX2AttentionTunerPatch(
            _id='1523',
            triton_kernels=False,
            model=ltxvchunkfeedforward,
        )
        wf.metadata.setdefault('id_map', {})['ltx2attentiontunerpatch'] = ltx2attentiontunerpatch.node.id

        # Conditioning
        cliptextencode = CLIPTextEncode(
            _id='1621',
            text=a8d7fd9f_52aa_447a_9766_53cb91c0ef18.out(0),
            clip=getnode_3.out(0),
        )
        wf.metadata.setdefault('id_map', {})['cliptextencode'] = cliptextencode.node.id

        setnode_14 = raw_call(wf, 'SetNode', '1633',
            widget_0=WIDGET_0_9,
            INT=getimagesize.out('WIDTH'),
        )
        wf.metadata.setdefault('id_map', {})['setnode_14'] = setnode_14.node.id

        setnode_15 = raw_call(wf, 'SetNode', '1634',
            widget_0=WIDGET_0_8,
            INT=getimagesize.out('HEIGHT'),
        )
        wf.metadata.setdefault('id_map', {})['setnode_15'] = setnode_15.node.id

        ltxvimgtovideoinplace = LTXVImgToVideoInplace(
            _id='1825',
            widget_0=1,
            widget_1=False,
            bypass=getnode_19.out(0),
            image=getnode_20.out(0),
            latent=ltxvseparateavlatent.out('VIDEO_LATENT'),
            vae=getnode_14.out(0),
        )
        wf.metadata.setdefault('id_map', {})['ltxvimgtovideoinplace'] = ltxvimgtovideoinplace.node.id

        setnode_18 = raw_call(wf, 'SetNode', '1860',
            widget_0=WIDGET_0_19,
            LATENT=ltxvconcatavlatent,
        )
        wf.metadata.setdefault('id_map', {})['setnode_18'] = setnode_18.node.id

        audionormalizelufs = raw_call(wf, 'AudioNormalizeLUFS', '1916',
            widget_0=-20,
            widget_1=0,
            widget_2=0,
            widget_3='full_track',
            audio=ailab_qwen3ttsvoiceclone,
        )
        wf.metadata.setdefault('id_map', {})['audionormalizelufs'] = audionormalizelufs.node.id

        ltxvconditioning = LTXVConditioning(
            _id='164',
            frame_rate=getnode_7.out(0),
            negative=cliptextencode_2,
            positive=cliptextencode,
            _outputs=('POSITIVE', 'NEGATIVE'),
        )
        wf.metadata.setdefault('id_map', {})['ltxvconditioning'] = ltxvconditioning.node.id

        power_lora_loader__rgthree_ = raw_call(wf, 'Power Lora Loader (rgthree)', '1627',
            _outputs=('MODEL', 'CLIP'),
            widget_4='',
            model=ltx2attentiontunerpatch,
        )
        wf.metadata.setdefault('id_map', {})['power_lora_loader__rgthree_'] = power_lora_loader__rgthree_.node.id

        ltxvconcatavlatent_2 = LTXVConcatAVLatent(
            _id='1819',
            audio_latent=ltxvseparateavlatent.out('AUDIO_LATENT'),
            video_latent=ltxvimgtovideoinplace,
        )
        wf.metadata.setdefault('id_map', {})['ltxvconcatavlatent_2'] = ltxvconcatavlatent_2.node.id

        audioenhancementnode = raw_call(wf, 'AudioEnhancementNode', '1904',
            widget_0='manual',
            widget_1=0.7,
            widget_10=5,
            widget_11=0,
            widget_12=0,
            widget_13='full_track',
            widget_2=0.6,
            widget_3=1.3,
            widget_4=1.2,
            widget_5=1,
            widget_6=1,
            widget_7=0.5,
            widget_8='keep_original',
            widget_9=False,
            audio=audionormalizelufs.out(0),
        )
        wf.metadata.setdefault('id_map', {})['audioenhancementnode'] = audioenhancementnode.node.id

        setnode = raw_call(wf, 'SetNode', '645',
            widget_0=WIDGET_0_14,
            CONDITIONING=ltxvconditioning.out('POSITIVE'),
        )
        wf.metadata.setdefault('id_map', {})['setnode'] = setnode.node.id

        setnode_2 = raw_call(wf, 'SetNode', '646',
            widget_0=WIDGET_0_13,
            CONDITIONING=ltxvconditioning.out('NEGATIVE'),
        )
        wf.metadata.setdefault('id_map', {})['setnode_2'] = setnode_2.node.id

        setnode_13 = raw_call(wf, 'SetNode', '1617',
            widget_0=WIDGET_0_17,
            MODEL=power_lora_loader__rgthree_.out('MODEL'),
        )
        wf.metadata.setdefault('id_map', {})['setnode_13'] = setnode_13.node.id

        setnode_16 = raw_call(wf, 'SetNode', '1758',
            widget_0=WIDGET_0_7,
            AUDIO=audioenhancementnode.out(0),
        )
        wf.metadata.setdefault('id_map', {})['setnode_16'] = setnode_16.node.id

        # Sampling
        samplercustomadvanced = SamplerCustomAdvanced(
            _id='1838',
            guider=cfgguider,
            latent_image=ltxvconcatavlatent_2,
            noise=randomnoise,
            sampler=ksamplerselect,
            sigmas=manualsigmas,
            _outputs=('OUTPUT', 'DENOISED_OUTPUT'),
        )
        wf.metadata.setdefault('id_map', {})['samplercustomadvanced'] = samplercustomadvanced.node.id

        previewaudio = PreviewAudio(_id='1943', audio=audioenhancementnode.out(0))
        wf.metadata.setdefault('id_map', {})['previewaudio'] = previewaudio.node.id
        ltxvseparateavlatent_2 = LTXVSeparateAVLatent(
            _id='1839',
            av_latent=samplercustomadvanced.out('OUTPUT'),
            _outputs=('VIDEO_LATENT', 'AUDIO_LATENT'),
        )
        wf.metadata.setdefault('id_map', {})['ltxvseparateavlatent_2'] = ltxvseparateavlatent_2.node.id

        # Decode
        vaedecodetiled = VAEDecodeTiled(
            _id='1818',
            temporal_size=4096,
            samples=ltxvseparateavlatent_2.out('VIDEO_LATENT'),
            vae=getnode_12.out(0),
        )
        wf.metadata.setdefault('id_map', {})['vaedecodetiled'] = vaedecodetiled.node.id

        ltxvaudiovaedecode = LTXVAudioVAEDecode(
            _id='1847',
            audio_vae=getnode_13.out(0),
            samples=ltxvseparateavlatent_2.out('AUDIO_LATENT'),
        )
        wf.metadata.setdefault('id_map', {})['ltxvaudiovaedecode'] = ltxvaudiovaedecode.node.id

        vram_debug = VRAM_Debug(
            _id='1915',
            widget_0=True,
            widget_1=True,
            widget_2=True,
            image_pass=vaedecodetiled,
            _outputs=('ANY_OUTPUT', 'IMAGE_PASS', 'MODEL_PASS', 'FREEMEM_BEFORE', 'FREEMEM_AFTER'),
        )
        wf.metadata.setdefault('id_map', {})['vram_debug'] = vram_debug.node.id

        # Outputs
        vhs_videocombine = VHS_VideoCombine(
            _id='1837',
            frame_rate=getnode_18.out(0),
            audio=ltxvaudiovaedecode,
            images=vram_debug.out('IMAGE_PASS'),
        )
        wf.metadata.setdefault('id_map', {})['vhs_videocombine'] = vhs_videocombine.node.id

        return wf.finalize(PUBLIC_INPUTS, output_node=vhs_videocombine, output_type='VHS_VideoCombine', name='video', artifact_kind='video', mime_type='video/mp4', expected_cardinality='one')

