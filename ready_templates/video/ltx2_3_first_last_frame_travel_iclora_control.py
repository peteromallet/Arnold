# vibecomfy: generated - converted by tools/convert_ready_templates.py
# Edits will be overwritten on regeneration. Put the manual opt-out
# marker on the first line if hand-editing is required.
"""Auto-generated ready_template - see tools/convert_ready_templates.py."""
from __future__ import annotations

from vibecomfy.templates import InputSpec, ModelAsset, ReadyMetadata, finalize, new_workflow, node as raw_call, ref
from vibecomfy.nodes.core import CFGGuider, CLIPTextEncode, DualCLIPLoader, EmptyLTXVLatentVideo, GetVideoComponents, KSamplerSelect, LTXVAudioVAEDecode, LTXVAudioVAELoader, LTXVConcatAVLatent, LTXVConditioning, LTXVCropGuides, LTXVEmptyLatentAudio, LTXVPreprocess, LTXVSeparateAVLatent, LoadImage, LoadVideo, LoraLoaderModelOnly, ManualSigmas, RandomNoise, SamplerCustomAdvanced, UNETLoader, VAEDecodeTiled, VAELoader
from vibecomfy.nodes.depthanythingv2 import DepthAnything_V2, DownloadAndLoadDepthAnythingV2Model
from vibecomfy.nodes.kjnodes import INTConstant, ImageResizeKJv2, LTX2AttentionTunerPatch, LTX2_NAG, LTXVChunkFeedForward, LTXVImgToVideoInplaceKJ, PathchSageAttentionKJ
from vibecomfy.nodes.ltxvideo import LTXAddVideoICLoRAGuide, LTXFloatToInt, LTXICLoRALoaderModelOnly
from vibecomfy.nodes.videohelpersuite import VHS_VideoCombine


CONTROL_AFTER_GENERATE = 'fixed'
DEFAULT_PROMPT = 'blurry, oversaturated, pixelated, low resolution, grainy, distorted, noise, compression artifacts, jpeg artifacts, glitches, watermark, text, logo, signature, copyright, subtitles'
DEFAULT_PROMPT_2 = 'A cinematic first-to-last-frame travel shot with smooth continuous camera motion, coherent subject motion, realistic lighting, and natural temporal consistency.'
DEFAULT_SEED = 43
DEFAULT_SEED_2 = 42
DEVICE = 'cpu'
GUIDE_STRENGTH = 0.6
GUIDE_STRENGTH_2 = 2.5
GUIDE_STRENGTH_3 = 1
KEEP_PROPORTION = 'crop'
KEEP_PROPORTION_2 = 'stretch'
MODEL_NAME = 'LTX23_audio_vae_bf16.safetensors'
MODEL_NAME_10 = 'dw-ll_ucoco_384_bs5.torchscript.pt'
MODEL_NAME_11 = 'ltxv/ltx2/ltx-2.3-22b-ic-lora-union-control-ref0.5.safetensors'
MODEL_NAME_2 = 'taeltx2_3.safetensors'
MODEL_NAME_3 = 'LTX23_video_vae_bf16.safetensors'
MODEL_NAME_4 = 'ltx-2.3-22b-distilled-1.1_transformer_only_fp8_scaled.safetensors'
MODEL_NAME_5 = 'gemma_3_12B_it_fp4_mixed.safetensors'
MODEL_NAME_6 = 'ltx-2.3_text_projection_bf16.safetensors'
MODEL_NAME_7 = 'depth_anything_v2_vits_fp32.safetensors'
MODEL_NAME_8 = 'LTX\\v2\\ltx-2.3-22b-distilled-1.1_lora-dynamic_fro09_avg_rank_111_bf16.safetensors'
MODEL_NAME_9 = 'yolox_l.onnx'
UPSCALE_METHOD = 'nearest-exact'
UPSCALE_METHOD_2 = 'lanczos'


MODELS = {
    'ltx_2_3_text_projection_bf16': ModelAsset(url='https://huggingface.co/Kijai/LTX2.3_comfy/resolve/main/text_encoders/ltx-2.3_text_projection_bf16.safetensors', sha256='911d59bb4cb7708179c9a0045ea0fe41212ecfb77aed3a02702b7c0a8274911f', hf_revision='72af6430be2ff9b6792e9bdb8b7bd8ddcc11bc8b', size_bytes=2312149072, subdir='text_encoders'),
    'ltx23_video_vae_bf16': ModelAsset(url='https://huggingface.co/Kijai/LTX2.3_comfy/resolve/main/vae/LTX23_video_vae_bf16.safetensors', sha256='01ea62d09bc139f95c5dee7b5c062ad6a3e6cd8be910a1983ac02e7eb5b8ee3b', hf_revision='72af6430be2ff9b6792e9bdb8b7bd8ddcc11bc8b', size_bytes=1452258578, subdir='vae'),
    'ltx23_audio_vae_bf16': ModelAsset(url='https://huggingface.co/Kijai/LTX2.3_comfy/resolve/main/vae/LTX23_audio_vae_bf16.safetensors', sha256='5bc10fa4adecf99dda132d916e23048cbd56797702c5fa50eb5d2079048a38c3', hf_revision='72af6430be2ff9b6792e9bdb8b7bd8ddcc11bc8b', size_bytes=364855188, subdir='checkpoints'),
    'taeltx2_3': ModelAsset(url='https://huggingface.co/Kijai/LTX2.3_comfy/resolve/main/vae/taeltx2_3.safetensors', sha256='f0773b4e3e57318e6aa4dd4a35e1d16213a5f160fbc0376163f06888bbcbe246', hf_revision='72af6430be2ff9b6792e9bdb8b7bd8ddcc11bc8b', size_bytes=23531296, subdir='vae'),
    'ltx_2_3_22b_distilled_1_1_transformer_only_fp8_scaled': ModelAsset(url='https://huggingface.co/Kijai/LTX2.3_comfy/resolve/main/diffusion_models/ltx-2.3-22b-distilled-1.1_transformer_only_fp8_scaled.safetensors', sha256='0a1d7aac2b338e8ec7e832149f1dcf11c9323272482b1cca0673d229702370f0', hf_revision='72af6430be2ff9b6792e9bdb8b7bd8ddcc11bc8b', size_bytes=25226571988, subdir='diffusion_models'),
    'ltx_v2_ltx_2_3_22b_distilled_1_1_lora_dynamic_fro09_avg_rank_111_bf16': ModelAsset(filename='LTX\\v2\\ltx-2.3-22b-distilled-1.1_lora-dynamic_fro09_avg_rank_111_bf16.safetensors', url='https://huggingface.co/Kijai/LTX2.3_comfy/resolve/main/loras/ltx-2.3-22b-distilled-1.1_lora-dynamic_fro09_avg_rank_111_bf16.safetensors', sha256='31e0c0195fb841bf31af78e8b60858f489e87ddcea4a5239abc80943da65e3ac', hf_revision='72af6430be2ff9b6792e9bdb8b7bd8ddcc11bc8b', size_bytes=2741024390, subdir='loras'),
    'depth_anything_v2_vits_fp32': ModelAsset(url='https://huggingface.co/Kijai/DepthAnythingV2-safetensors/resolve/main/depth_anything_v2_vits_fp32.safetensors', sha256='cb2d537ed6e45921f27f61f0b605dcfafb6b97c7d1a15e551280bdd867605c86', hf_revision='5aa7ab578df757d94c743998b157a0204ff29215', size_bytes=99165460, subdir='depthanything'),
    'yolox_l': ModelAsset(url='https://huggingface.co/yzd-v/DWPose/resolve/main/yolox_l.onnx', target_path='custom_nodes/comfyui_controlnet_aux/ckpts/yzd-v/DWPose/yolox_l.onnx', sha256='7860ae79de6c89a3c1eb72ae9a2756c0ccfbe04b7791bb5880afabd97855a411', hf_revision='1a7144101628d69ee7a3768d1ee3a094070dc388', size_bytes=216746733, subdir='controlnet_aux'),
    'dw_ll_ucoco_384_bs5_torchscript': ModelAsset(url='https://huggingface.co/hr16/DWPose-TorchScript-BatchSize5/resolve/main/dw-ll_ucoco_384_bs5.torchscript.pt', target_path='custom_nodes/comfyui_controlnet_aux/ckpts/hr16/DWPose-TorchScript-BatchSize5/dw-ll_ucoco_384_bs5.torchscript.pt', sha256='d86a0b2b59fddc0901a7076e9f59c9f8602602133ed72511c693fd11eea23d91', hf_revision='359d662a9b33b73f6d0f21732baf8845f17bb4be', size_bytes=135059124, subdir='controlnet_aux'),
}

PUBLIC_INPUTS = {
    'seed': InputSpec(node=ref('randomnoise'), field='noise_seed', default=DEFAULT_SEED),
    'model': InputSpec(node=ref('ltxvaudiovaeloader'), field='ckpt_name', default=MODEL_NAME),
    'prompt': InputSpec(node=ref('cliptextencode_2'), field='text', default=DEFAULT_PROMPT_2),
    'start_image': InputSpec(node=ref('loadimage'), field='image', default='example.png'),
    'end_image': InputSpec(node=ref('loadimage_2'), field='image', default='egyptian_queen.png'),
    'control_video': InputSpec(node=ref('loadvideo'), field='video', default='ltx_smoke_guide.mp4'),
    'control_mode': InputSpec(node=ref('primitivestring'), field='value', default='canny'),
    'negative_prompt': InputSpec(node=ref('cliptextencode'), field='text', default=DEFAULT_PROMPT),
    'negative': InputSpec(node=ref('cliptextencode'), field='text', default=DEFAULT_PROMPT),
    'width': InputSpec(node=ref('intconstant_3'), field='value', default=256),
    'height': InputSpec(node=ref('intconstant_2'), field='value', default=256),
    'output_fps': InputSpec(node=ref('primitivefloat'), field='value', default=8),
    'fps': InputSpec(node=ref('primitivefloat'), field='value', default=8),
    'ic_lora_filename': InputSpec(node=ref('ltxicloraloadermodelonly'), field='lora_name', default=MODEL_NAME_11),
    'ic_lora_strength': InputSpec(node=ref('ltxicloraloadermodelonly'), field='strength_model', default=GUIDE_STRENGTH_3),
    'seed_refine': InputSpec(node=ref('randomnoise_2'), field='noise_seed', default=DEFAULT_SEED_2),
    'length': InputSpec(node=ref('intconstant'), field='value', default=9),
    'frames': InputSpec(node=ref('intconstant'), field='value', default=9),
    'guide_strength': InputSpec(node=ref('ltxaddvideoicloraguide'), field='strength', default=1),
    'strength': InputSpec(node=ref('ltxaddvideoicloraguide'), field='strength', default=1),
    'image': InputSpec(node=ref('loadimage'), field='image', default='example.png'),
    'input_image': InputSpec(node=ref('loadimage'), field='image', default='example.png'),
}

READY_METADATA = ReadyMetadata.build(
    capability='first_last_frame_control_video',
    inputs=PUBLIC_INPUTS,
    models=MODELS,
    requirements={'custom_nodes': ['ComfyUI-DepthAnythingV2', 'ComfyUI-KJNodes', 'ComfyUI-LTXVideo', 'ComfyUI-VideoHelperSuite', 'comfyui_controlnet_aux']},
    custom_node_packs={'ComfyUI-DepthAnythingV2': {'commit': '553187872eeb1d52e50dc53209fa57e569609a72', 'url': 'https://github.com/kijai/ComfyUI-DepthAnythingV2.git', 'class_schema_sha256': 'f4e181ab42ca179eda161acba5121e999cb54b1dbee0dc087a22bd42af7241ae', 'classes_used': ['DepthAnything_V2', 'DownloadAndLoadDepthAnythingV2Model'], 'pip_packages': ['opencv-python-headless', 'transformers'], 'status': 'pinned'}, 'ComfyUI-KJNodes': {'commit': 'b7646ad70a7daa7aeb919ca542274758d26ba2df', 'url': 'https://github.com/kijai/ComfyUI-KJNodes.git', 'class_schema_sha256': '1beaf129c8fa26175d89a28f9ca10d08b5ac27c8fc9bff920263fcbba17cb691', 'classes_used': ['INTConstant', 'ImageResizeKJv2', 'PathchSageAttentionKJ'], 'pip_packages': ['matplotlib'], 'status': 'pinned'}, 'ComfyUI-LTXVideo': {'commit': '229437c6b65796d6a7a63ae34be2bd5ba31fa543', 'url': 'https://github.com/Lightricks/ComfyUI-LTXVideo.git', 'class_schema_sha256': '82e0b1f31509a969cf441c45e2517d0cd93f31b5390cc16f4a0ffa244421f39e', 'classes_used': ['EmptyLTXVLatentVideo', 'LTX2AttentionTunerPatch', 'LTX2_NAG', 'LTXVAudioVAEDecode', 'LTXVAudioVAELoader', 'LTXVChunkFeedForward', 'LTXVConcatAVLatent', 'LTXVConditioning', 'LTXVCropGuides', 'LTXVEmptyLatentAudio', 'LTXVImgToVideoInplaceKJ', 'LTXVPreprocess', 'LTXVSeparateAVLatent'], 'pip_packages': [], 'status': 'pinned'}, 'ComfyUI-VideoHelperSuite': {'commit': '4ee72c065db22c9d96c2427954dc69e7b908444b', 'url': 'https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite.git', 'class_schema_sha256': '8391e679554eecd5d324a3e34a713ff240e619e3a07476587845ba18c9fae310', 'classes_used': ['VHS_VideoCombine'], 'pip_packages': [], 'status': 'pinned'}, 'comfyui_controlnet_aux': {'commit': 'e8b689a513c3e6b63edc44066560ca5919c0576e', 'url': 'https://github.com/Fannovel16/comfyui_controlnet_aux.git', 'class_schema_sha256': 'e485b148824d72ef7af7e90f711eefb511ffe73b25cd1c6053e1e5c7bd3bbd62', 'classes_used': ['CannyEdgePreprocessor', 'DWPreprocessor'], 'pip_packages': ['onnxruntime', 'opencv-python-headless'], 'status': 'pinned'}},
    smoke_resolution='256x256x9_frames',
    approach='first/last-frame image anchors plus full-length raw/pose/depth/canny IC-LoRA guide branches',
    runtime_note='Default guide branch is Canny. Patch node 5012 input image to select raw, pose, or depth branches.',
    discord_signal='Combines recurring LTX first/last travel and full-length control-guide workflows.',
    ltx_best_practices=['Use first/last anchors for travel endpoints.', 'Use a full-length guide video with IC-LoRA union-control conditioning.', 'Patch smoke runs to fp8/fp4 model assets, tiny frame counts, and low-VRAM loader settings.'],
    comfy_configuration={'reserve_vram': 12, 'cache_none': True, 'fp8_e4m3fn_text_enc': True},
    provenance={'source_workflow': 'manual'},
)

def build() -> VibeWorkflow:
    """Build the workflow (auto-generated)."""
    with new_workflow(READY_METADATA, source_path=__file__) as wf:

        # Sampling
        ksamplerselect = KSamplerSelect(_id='1', sampler_name='euler_ancestral_cfg_pp')
        wf.metadata.setdefault('id_map', {})['ksamplerselect'] = ksamplerselect.node.id
        ksamplerselect_2 = KSamplerSelect(_id='4', sampler_name='euler_cfg_pp')
        wf.metadata.setdefault('id_map', {})['ksamplerselect_2'] = ksamplerselect_2.node.id
        randomnoise = RandomNoise(
            _id='14',
            noise_seed=DEFAULT_SEED,
            control_after_generate=CONTROL_AFTER_GENERATE,
        )
        wf.metadata.setdefault('id_map', {})['randomnoise'] = randomnoise.node.id

        randomnoise_2 = RandomNoise(
            _id='15',
            noise_seed=DEFAULT_SEED_2,
            control_after_generate=CONTROL_AFTER_GENERATE,
        )
        wf.metadata.setdefault('id_map', {})['randomnoise_2'] = randomnoise_2.node.id

        # Inputs
        loadimage = LoadImage(_id='45', image='example.png', _outputs=('IMAGE', 'MASK'))
        wf.metadata.setdefault('id_map', {})['loadimage'] = loadimage.node.id
        loadimage_2 = LoadImage(
            _id='47',
            image='egyptian_queen.png',
            _outputs=('IMAGE', 'MASK'),
        )
        wf.metadata.setdefault('id_map', {})['loadimage_2'] = loadimage_2.node.id

        ltxvaudiovaeloader = LTXVAudioVAELoader(_id='175', ckpt_name=MODEL_NAME)
        wf.metadata.setdefault('id_map', {})['ltxvaudiovaeloader'] = ltxvaudiovaeloader.node.id
        # Loaders
        vaeloader = VAELoader(_id='180', vae_name=MODEL_NAME_2)
        wf.metadata.setdefault('id_map', {})['vaeloader'] = vaeloader.node.id
        vaeloader_2 = VAELoader(_id='181', vae_name=MODEL_NAME_3)
        wf.metadata.setdefault('id_map', {})['vaeloader_2'] = vaeloader_2.node.id
        unetloader = UNETLoader(_id='187', unet_name=MODEL_NAME_4)
        wf.metadata.setdefault('id_map', {})['unetloader'] = unetloader.node.id
        dualcliploader = DualCLIPLoader(
            _id='190',
            clip_name1=MODEL_NAME_5,
            clip_name2=MODEL_NAME_6,
            type_='ltxv',
            device='default',
        )
        wf.metadata.setdefault('id_map', {})['dualcliploader'] = dualcliploader.node.id

        manualsigmas = ManualSigmas(
            _id='215',
            sigmas='1.0, 0.99375, 0.9875, 0.98125, 0.975, 0.909375, 0.725, 0.421875, 0.0',
        )
        wf.metadata.setdefault('id_map', {})['manualsigmas'] = manualsigmas.node.id

        manualsigmas_2 = ManualSigmas(_id='216', sigmas='0.85, 0.7250, 0.4219, 0.0')
        wf.metadata.setdefault('id_map', {})['manualsigmas_2'] = manualsigmas_2.node.id
        # Inputs
        primitivefloat = raw_call(wf, 'PrimitiveFloat', '2076', value=8)
        wf.metadata.setdefault('id_map', {})['primitivefloat'] = primitivefloat.node.id
        intconstant = INTConstant(_id='2078', value=9)
        wf.metadata.setdefault('id_map', {})['intconstant'] = intconstant.node.id
        intconstant_2 = INTConstant(_id='2079', value=256)
        wf.metadata.setdefault('id_map', {})['intconstant_2'] = intconstant_2.node.id
        intconstant_3 = INTConstant(_id='2080', value=256)
        wf.metadata.setdefault('id_map', {})['intconstant_3'] = intconstant_3.node.id
        primitivefloat_2 = raw_call(wf, 'PrimitiveFloat', '2108', value=0.8)
        wf.metadata.setdefault('id_map', {})['primitivefloat_2'] = primitivefloat_2.node.id
        primitivefloat_3 = raw_call(wf, 'PrimitiveFloat', '2110', value=0.8)
        wf.metadata.setdefault('id_map', {})['primitivefloat_3'] = primitivefloat_3.node.id
        loadvideo = LoadVideo(
            _id='5001',
            file='ltx_smoke_guide.mp4',
            video='ltx_smoke_guide.mp4',
        )
        wf.metadata.setdefault('id_map', {})['loadvideo'] = loadvideo.node.id

        downloadandloaddepthanythingv2model = DownloadAndLoadDepthAnythingV2Model(
            _id='5060',
            model=MODEL_NAME_7,
            precision='fp32',
        )
        wf.metadata.setdefault('id_map', {})['downloadandloaddepthanythingv2model'] = downloadandloaddepthanythingv2model.node.id

        primitivestring = raw_call(wf, 'PrimitiveString', '6000', value='canny')
        wf.metadata.setdefault('id_map', {})['primitivestring'] = primitivestring.node.id
        # Conditioning
        cliptextencode = CLIPTextEncode(
            _id='11',
            text=DEFAULT_PROMPT,
            clip=dualcliploader,
        )
        wf.metadata.setdefault('id_map', {})['cliptextencode'] = cliptextencode.node.id

        cliptextencode_2 = CLIPTextEncode(
            _id='16',
            text=DEFAULT_PROMPT_2,
            clip=dualcliploader,
        )
        wf.metadata.setdefault('id_map', {})['cliptextencode_2'] = cliptextencode_2.node.id

        # Sampling
        emptyltxvlatentvideo = EmptyLTXVLatentVideo(
            _id='32',
            width=intconstant_3,
            height=intconstant_2,
            length=intconstant,
        )
        wf.metadata.setdefault('id_map', {})['emptyltxvlatentvideo'] = emptyltxvlatentvideo.node.id

        imageresizekjv2 = ImageResizeKJv2(
            _id='44',
            upscale_method=UPSCALE_METHOD,
            keep_proportion=KEEP_PROPORTION,
            divisible_by=32,
            device=DEVICE,
            width=intconstant_3,
            height=intconstant_2,
            image=loadimage.out('IMAGE'),
            _outputs=('IMAGE', 'WIDTH', 'HEIGHT', 'MASK'),
        )
        wf.metadata.setdefault('id_map', {})['imageresizekjv2'] = imageresizekjv2.node.id

        imageresizekjv2_2 = ImageResizeKJv2(
            _id='48',
            upscale_method=UPSCALE_METHOD,
            keep_proportion=KEEP_PROPORTION,
            divisible_by=32,
            device=DEVICE,
            width=intconstant_3,
            height=intconstant_2,
            image=loadimage_2.out('IMAGE'),
            _outputs=('IMAGE', 'WIDTH', 'HEIGHT', 'MASK'),
        )
        wf.metadata.setdefault('id_map', {})['imageresizekjv2_2'] = imageresizekjv2_2.node.id

        loraloadermodelonly = LoraLoaderModelOnly(
            _id='186',
            lora_name=MODEL_NAME_8,
            strength_model=GUIDE_STRENGTH,
            model=unetloader,
        )
        wf.metadata.setdefault('id_map', {})['loraloadermodelonly'] = loraloadermodelonly.node.id

        ltx2_nag = LTX2_NAG(_id='197', model=unetloader)
        wf.metadata.setdefault('id_map', {})['ltx2_nag'] = ltx2_nag.node.id
        getvideocomponents = GetVideoComponents(
            _id='5000',
            video=loadvideo,
            _outputs=('IMAGES', 'AUDIO', 'FPS'),
        )
        wf.metadata.setdefault('id_map', {})['getvideocomponents'] = getvideocomponents.node.id

        ltxfloattoint = LTXFloatToInt(_id='5066', rounding=0, a=primitivefloat)
        wf.metadata.setdefault('id_map', {})['ltxfloattoint'] = ltxfloattoint.node.id
        ltxvemptylatentaudio = LTXVEmptyLatentAudio(
            _id='9',
            frames_number=intconstant,
            frame_rate=ltxfloattoint,
            audio_vae=ltxvaudiovaeloader,
        )
        wf.metadata.setdefault('id_map', {})['ltxvemptylatentaudio'] = ltxvemptylatentaudio.node.id

        ltxvconditioning = LTXVConditioning(
            _id='10',
            frame_rate=primitivefloat,
            negative=cliptextencode,
            positive=cliptextencode_2,
            _outputs=('POSITIVE', 'NEGATIVE'),
        )
        wf.metadata.setdefault('id_map', {})['ltxvconditioning'] = ltxvconditioning.node.id

        ltxvpreprocess = LTXVPreprocess(
            _id='50',
            img_compression=18,
            image=imageresizekjv2_2.out('IMAGE'),
        )
        wf.metadata.setdefault('id_map', {})['ltxvpreprocess'] = ltxvpreprocess.node.id

        pathchsageattentionkj = PathchSageAttentionKJ(
            _id='226',
            sage_attention='disabled',
            model=loraloadermodelonly,
        )
        wf.metadata.setdefault('id_map', {})['pathchsageattentionkj'] = pathchsageattentionkj.node.id

        ltxvpreprocess_2 = LTXVPreprocess(
            _id='2084',
            img_compression=18,
            image=imageresizekjv2.out('IMAGE'),
        )
        wf.metadata.setdefault('id_map', {})['ltxvpreprocess_2'] = ltxvpreprocess_2.node.id

        imageresizekjv2_3 = ImageResizeKJv2(
            _id='5026',
            upscale_method=UPSCALE_METHOD_2,
            keep_proportion=KEEP_PROPORTION_2,
            divisible_by=32,
            device=DEVICE,
            width=intconstant_3,
            height=intconstant_2,
            image=getvideocomponents.out('IMAGES'),
            _outputs=('IMAGE', 'WIDTH', 'HEIGHT', 'MASK'),
        )
        wf.metadata.setdefault('id_map', {})['imageresizekjv2_3'] = imageresizekjv2_3.node.id

        # Conditioning
        cfgguider_2 = CFGGuider(
            _id='36',
            cfg=GUIDE_STRENGTH_2,
            model=ltx2_nag,
            negative=ltxvconditioning.out('NEGATIVE'),
            positive=ltxvconditioning.out('POSITIVE'),
        )
        wf.metadata.setdefault('id_map', {})['cfgguider_2'] = cfgguider_2.node.id

        ltxvimgtovideoinplacekj = LTXVImgToVideoInplaceKJ(
            _id='210',
            num_images='2',
            latent=emptyltxvlatentvideo,
            vae=vaeloader_2,
            **{'num_images.index_1': 0, 'num_images.index_2': -1, 'num_images.image_1': ltxvpreprocess_2, 'num_images.image_2': ltxvpreprocess, 'num_images.strength_1': primitivefloat_3, 'num_images.strength_2': primitivefloat_2},
        )
        wf.metadata.setdefault('id_map', {})['ltxvimgtovideoinplacekj'] = ltxvimgtovideoinplacekj.node.id

        ltxvchunkfeedforward = LTXVChunkFeedForward(
            _id='228',
            model=pathchsageattentionkj,
        )
        wf.metadata.setdefault('id_map', {})['ltxvchunkfeedforward'] = ltxvchunkfeedforward.node.id

        dwpreprocessor = raw_call(wf, 'DWPreprocessor', '4986',
            detect_hand='enable',
            detect_body='enable',
            detect_face='enable',
            resolution=256,
            bbox_detector=MODEL_NAME_9,
            pose_estimator=MODEL_NAME_10,
            scale_stick_for_xinsr_cn='disable',
            image=imageresizekjv2_3.out('IMAGE'),
        )
        wf.metadata.setdefault('id_map', {})['dwpreprocessor'] = dwpreprocessor.node.id

        cannyedgepreprocessor = raw_call(wf, 'CannyEdgePreprocessor', '4991',
            low_threshold=92,
            high_threshold=200,
            resolution=256,
            image=imageresizekjv2_3.out('IMAGE'),
        )
        wf.metadata.setdefault('id_map', {})['cannyedgepreprocessor'] = cannyedgepreprocessor.node.id

        depthanything_v2 = DepthAnything_V2(
            _id='5061',
            da_model=downloadandloaddepthanythingv2model,
            images=imageresizekjv2_3.out('IMAGE'),
        )
        wf.metadata.setdefault('id_map', {})['depthanything_v2'] = depthanything_v2.node.id

        imageresizekjv2_5 = ImageResizeKJv2(
            _id='6101',
            upscale_method=UPSCALE_METHOD_2,
            keep_proportion=KEEP_PROPORTION_2,
            divisible_by=32,
            device=DEVICE,
            width=intconstant_3,
            height=intconstant_2,
            image=imageresizekjv2_3.out('IMAGE'),
            _outputs=('IMAGE', 'WIDTH', 'HEIGHT', 'MASK'),
        )
        wf.metadata.setdefault('id_map', {})['imageresizekjv2_5'] = imageresizekjv2_5.node.id

        ltx2attentiontunerpatch = LTX2AttentionTunerPatch(
            _id='229',
            triton_kernels=False,
            model=ltxvchunkfeedforward,
        )
        wf.metadata.setdefault('id_map', {})['ltx2attentiontunerpatch'] = ltx2attentiontunerpatch.node.id

        imageresizekjv2_4 = ImageResizeKJv2(
            _id='5028',
            upscale_method=UPSCALE_METHOD_2,
            keep_proportion=KEEP_PROPORTION_2,
            divisible_by=32,
            device=DEVICE,
            width=intconstant_3,
            height=intconstant_2,
            image=cannyedgepreprocessor,
            _outputs=('IMAGE', 'WIDTH', 'HEIGHT', 'MASK'),
        )
        wf.metadata.setdefault('id_map', {})['imageresizekjv2_4'] = imageresizekjv2_4.node.id

        imageresizekjv2_6 = ImageResizeKJv2(
            _id='6102',
            upscale_method=UPSCALE_METHOD_2,
            keep_proportion=KEEP_PROPORTION_2,
            divisible_by=32,
            device=DEVICE,
            width=intconstant_3,
            height=intconstant_2,
            image=dwpreprocessor,
            _outputs=('IMAGE', 'WIDTH', 'HEIGHT', 'MASK'),
        )
        wf.metadata.setdefault('id_map', {})['imageresizekjv2_6'] = imageresizekjv2_6.node.id

        imageresizekjv2_7 = ImageResizeKJv2(
            _id='6103',
            upscale_method=UPSCALE_METHOD_2,
            keep_proportion=KEEP_PROPORTION_2,
            divisible_by=32,
            device=DEVICE,
            width=intconstant_3,
            height=intconstant_2,
            image=depthanything_v2,
            _outputs=('IMAGE', 'WIDTH', 'HEIGHT', 'MASK'),
        )
        wf.metadata.setdefault('id_map', {})['imageresizekjv2_7'] = imageresizekjv2_7.node.id

        ltxicloraloadermodelonly = LTXICLoRALoaderModelOnly(
            _id='5011',
            lora_name=MODEL_NAME_11,
            strength_model=GUIDE_STRENGTH_3,
            model=ltx2attentiontunerpatch,
            _outputs=('MODEL', 'LATENT_DOWNSCALE_FACTOR'),
        )
        wf.metadata.setdefault('id_map', {})['ltxicloraloadermodelonly'] = ltxicloraloadermodelonly.node.id

        ltxaddvideoicloraguide = LTXAddVideoICLoRAGuide(
            _id='5012',
            strength=1,
            crop='center',
            use_tiled_encode='disabled',
            tile_size=128,
            tile_overlap=32,
            image=imageresizekjv2_4.out('IMAGE'),
            latent=ltxvimgtovideoinplacekj,
            latent_downscale_factor=ltxicloraloadermodelonly.out('LATENT_DOWNSCALE_FACTOR'),
            negative=ltxvconditioning.out('NEGATIVE'),
            positive=ltxvconditioning.out('POSITIVE'),
            vae=vaeloader_2,
            _outputs=('POSITIVE', 'NEGATIVE', 'LATENT'),
        )
        wf.metadata.setdefault('id_map', {})['ltxaddvideoicloraguide'] = ltxaddvideoicloraguide.node.id

        cfgguider = CFGGuider(
            _id='8',
            cfg=GUIDE_STRENGTH_2,
            model=ltxicloraloadermodelonly.out('MODEL'),
            negative=ltxaddvideoicloraguide.out('NEGATIVE'),
            positive=ltxaddvideoicloraguide.out('POSITIVE'),
        )
        wf.metadata.setdefault('id_map', {})['cfgguider'] = cfgguider.node.id

        ltxvconcatavlatent = LTXVConcatAVLatent(
            _id='24',
            audio_latent=ltxvemptylatentaudio,
            video_latent=ltxaddvideoicloraguide.out('LATENT'),
        )
        wf.metadata.setdefault('id_map', {})['ltxvconcatavlatent'] = ltxvconcatavlatent.node.id

        # Sampling
        samplercustomadvanced = SamplerCustomAdvanced(
            _id='13',
            guider=cfgguider_2,
            latent_image=ltxvconcatavlatent,
            noise=randomnoise_2,
            sampler=ksamplerselect,
            sigmas=manualsigmas,
            _outputs=('OUTPUT', 'DENOISED_OUTPUT'),
        )
        wf.metadata.setdefault('id_map', {})['samplercustomadvanced'] = samplercustomadvanced.node.id

        ltxvseparateavlatent = LTXVSeparateAVLatent(
            _id='18',
            av_latent=samplercustomadvanced.out('OUTPUT'),
            _outputs=('VIDEO_LATENT', 'AUDIO_LATENT'),
        )
        wf.metadata.setdefault('id_map', {})['ltxvseparateavlatent'] = ltxvseparateavlatent.node.id

        ltxvconcatavlatent_2 = LTXVConcatAVLatent(
            _id='34',
            audio_latent=ltxvseparateavlatent.out('AUDIO_LATENT'),
            video_latent=ltxvseparateavlatent.out('VIDEO_LATENT'),
        )
        wf.metadata.setdefault('id_map', {})['ltxvconcatavlatent_2'] = ltxvconcatavlatent_2.node.id

        samplercustomadvanced_2 = SamplerCustomAdvanced(
            _id='21',
            guider=cfgguider,
            latent_image=ltxvconcatavlatent_2,
            noise=randomnoise,
            sampler=ksamplerselect_2,
            sigmas=manualsigmas_2,
            _outputs=('OUTPUT', 'DENOISED_OUTPUT'),
        )
        wf.metadata.setdefault('id_map', {})['samplercustomadvanced_2'] = samplercustomadvanced_2.node.id

        ltxvseparateavlatent_2 = LTXVSeparateAVLatent(
            _id='146',
            av_latent=samplercustomadvanced_2.out('OUTPUT'),
            _outputs=('VIDEO_LATENT', 'AUDIO_LATENT'),
        )
        wf.metadata.setdefault('id_map', {})['ltxvseparateavlatent_2'] = ltxvseparateavlatent_2.node.id

        ltxvaudiovaedecode = LTXVAudioVAEDecode(
            _id='150',
            audio_vae=ltxvaudiovaeloader,
            samples=ltxvseparateavlatent_2.out('AUDIO_LATENT'),
        )
        wf.metadata.setdefault('id_map', {})['ltxvaudiovaedecode'] = ltxvaudiovaedecode.node.id

        ltxvcropguides = LTXVCropGuides(
            _id='2156',
            latent=ltxvseparateavlatent_2.out('VIDEO_LATENT'),
            negative=ltxaddvideoicloraguide.out('NEGATIVE'),
            positive=ltxaddvideoicloraguide.out('POSITIVE'),
            _outputs=('POSITIVE', 'NEGATIVE', 'LATENT'),
        )
        wf.metadata.setdefault('id_map', {})['ltxvcropguides'] = ltxvcropguides.node.id

        # Decode
        vaedecodetiled = VAEDecodeTiled(
            _id='149',
            temporal_size=4096,
            samples=ltxvcropguides.out('LATENT'),
            vae=vaeloader_2,
        )
        wf.metadata.setdefault('id_map', {})['vaedecodetiled'] = vaedecodetiled.node.id

        # Outputs
        vhs_videocombine = VHS_VideoCombine(
            _id='43',
            filename_prefix='reigh_vibecomfy_ltx_control_first_last',
            format='video/h264-mp4',
            frame_rate=primitivefloat,
            images=vaedecodetiled,
        )
        wf.metadata.setdefault('id_map', {})['vhs_videocombine'] = vhs_videocombine.node.id

        return wf.finalize(PUBLIC_INPUTS, output_type='VHS_VideoCombine', name='video', artifact_kind='video', mime_type='video/mp4', expected_cardinality='one', filename_prefix='reigh_vibecomfy_ltx_control_first_last')

