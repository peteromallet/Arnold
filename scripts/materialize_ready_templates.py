from __future__ import annotations

import json
import sys
from pathlib import Path
from pprint import pformat

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from vibecomfy.ingest.loader import load_template
from vibecomfy.ingest.normalize import convert_to_vibe_format, normalize_to_api
from vibecomfy.model_assets import extract_from_raw_workflow
from vibecomfy.node_packs import resolve_node_packs
from vibecomfy.workflow import VibeWorkflow


MANIFEST = ROOT / "workflow_corpus/manifests/coverage.json"
READY_ROOT = ROOT / "ready_templates"


def main() -> int:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    for item in manifest["workflows"]:
        if item.get("coverage_tier") != "required" and not item.get("ready_template"):
            continue
        workflow = _workflow_for_item(item)
        _write_ready_template(item, workflow)
    return 0


def _workflow_for_item(item: dict) -> VibeWorkflow:
    raw = load_template(ROOT / item["path"])
    api = normalize_to_api(raw)
    workflow = convert_to_vibe_format(api, source_path=item["path"], workflow_id=item["id"])
    workflow.metadata["model_assets"] = extract_from_raw_workflow(raw)
    _apply_ready_policy(workflow, item)
    return workflow


def _apply_ready_policy(workflow: VibeWorkflow, item: dict) -> None:
    template_id = _ready_template_id(item)
    workflow_template = item["id"]
    workflow.set_seed(_ready_seed(workflow_template))
    workflow.metadata.update(
        {
            "ready_template": template_id,
            "workflow_template": workflow_template,
            "capability": item["task"],
            "source_role": "materialized_ready_python_template",
            "source_workflow": item["path"],
            "coverage_tier": item.get("coverage_tier"),
            "approach": item.get("approach"),
            "runtime_note": item.get("runtime_note"),
            "discord_signal": item.get("discord_signal"),
        }
    )
    if workflow_template == "flux2_klein_9b_gguf_t2i":
        _apply_flux2_gguf_policy(workflow)
    elif workflow_template == "qwen_image_2512":
        _apply_qwen_image_2512_policy(workflow)
    elif workflow_template.startswith("ace_step"):
        _apply_ace_step_policy(workflow)
    elif workflow_template.startswith("ltx2_3"):
        _apply_ltx_policy(workflow, image_to_video=workflow_template == "ltx2_3_i2v")
    elif workflow_template.startswith("wanvideo_wrapper"):
        _apply_wanvideo_wrapper_policy(workflow)


def _ready_seed(template_id: str) -> int:
    return 1000 + sum(ord(char) for char in template_id) % 100000


def _apply_flux2_gguf_policy(workflow: VibeWorkflow) -> None:
    workflow.metadata["model_assets_replaced_by_policy"] = [
        "flux-2-klein-base-9b-fp8.safetensors",
        "full_encoder_small_decoder.safetensors",
    ]
    for node in workflow.nodes.values():
        if node.class_type == "UNETLoader" and "unet_name" in node.inputs:
            node.class_type = "UnetLoaderGGUF"
            # No canonical Comfy-Org URL is available for this GGUF asset yet; a follow-up should supply it via model_assets_extra.
            node.inputs["unet_name"] = "flux-2-klein-9b-Q4_K_M.gguf"
        if node.class_type == "VAELoader" and node.inputs.get("vae_name") == "full_encoder_small_decoder.safetensors":
            node.inputs["vae_name"] = "flux2-vae.safetensors"
    workflow.requirements.custom_nodes.append("ComfyUI-GGUF")


def _apply_qwen_image_2512_policy(workflow: VibeWorkflow) -> None:
    for node in workflow.nodes.values():
        if node.class_type == "PrimitiveBoolean":
            node.inputs["value"] = True
            node.widgets = {}
        elif node.class_type == "PrimitiveInt":
            node.inputs["value"] = min(int(node.inputs.get("value", 4)), 4)
            node.widgets = {}
        elif node.class_type == "PrimitiveFloat":
            node.inputs["value"] = min(float(node.inputs.get("value", 1)), 1)
            node.widgets = {}
        elif node.class_type == "EmptySD3LatentImage":
            node.inputs.update({"width": 768, "height": 768, "batch_size": 1})
            node.widgets = {}
        elif node.class_type == "KSampler":
            node.inputs.update({"seed": 1232512, "sampler_name": "euler", "scheduler": "simple", "denoise": 1})
            node.widgets = {}
        elif node.class_type == "SaveImage":
            node.inputs["filename_prefix"] = "Qwen-Image-2512"
            node.widgets = {}
    workflow.metadata["runtime_variant"] = "qwen-image-2512-lightning-4step-768px"
    workflow.metadata["smoke_resolution"] = "768x768"
    workflow.metadata["model_assets_extra"] = [
        {
            "name": "qwen_image_2512_fp8_e4m3fn.safetensors",
            "url": "https://huggingface.co/Comfy-Org/Qwen-Image_ComfyUI/resolve/main/split_files/diffusion_models/qwen_image_2512_fp8_e4m3fn.safetensors",
            "subdir": "diffusion_models",
        },
        {
            "name": "qwen_2.5_vl_7b_fp8_scaled.safetensors",
            "url": "https://huggingface.co/Comfy-Org/Qwen-Image_ComfyUI/resolve/main/split_files/text_encoders/qwen_2.5_vl_7b_fp8_scaled.safetensors",
            "subdir": "text_encoders",
        },
        {
            "name": "qwen_image_vae.safetensors",
            "url": "https://huggingface.co/Comfy-Org/Qwen-Image_ComfyUI/resolve/main/split_files/vae/qwen_image_vae.safetensors",
            "subdir": "vae",
        },
        {
            "name": "Qwen-Image-2512-Lightning-4steps-V1.0-fp32.safetensors",
            "url": "https://huggingface.co/lightx2v/Qwen-Image-2512-Lightning/resolve/main/Qwen-Image-2512-Lightning-4steps-V1.0-fp32.safetensors",
            "subdir": "loras",
        },
    ]


def _apply_ace_step_policy(workflow: VibeWorkflow) -> None:
    _replace_ace_primitive_edges(workflow, "126", 561594583201063)
    _replace_ace_primitive_edges(workflow, "110", 2)
    for node in workflow.nodes.values():
        if node.class_type == "DualCLIPLoader":
            node.inputs = {
                "clip_name1": node.inputs.get("clip_name1", node.inputs.get("widget_0", "qwen_0.6b_ace15.safetensors")),
                "clip_name2": node.inputs.get("clip_name2", node.inputs.get("widget_1", "qwen_4b_ace15.safetensors")),
                "type": node.inputs.get("type", node.inputs.get("widget_2", "ace")),
                "device": node.inputs.get("device", node.inputs.get("widget_3", "default")),
            }
            node.widgets = {}
        elif node.class_type == "VAELoader":
            node.inputs = {"vae_name": node.inputs.get("vae_name", node.inputs.get("widget_0", "ace_1.5_vae.safetensors"))}
            node.widgets = {}
        elif node.class_type == "UNETLoader":
            node.inputs = {
                "unet_name": node.inputs.get("unet_name", node.inputs.get("widget_0", "acestep_v1.5_turbo.safetensors")),
                "weight_dtype": node.inputs.get("weight_dtype", node.inputs.get("widget_1", "default")),
            }
            node.widgets = {}
        elif node.class_type == "KSampler":
            node.inputs.update({"seed": 561594583201063, "steps": 1, "cfg": 1, "sampler_name": "euler", "scheduler": "simple", "denoise": 1})
            for key in tuple(node.inputs):
                if key.startswith("widget_"):
                    node.inputs.pop(key)
            node.widgets = {}
        elif node.class_type == "ModelSamplingAuraFlow":
            node.inputs["shift"] = node.inputs.pop("widget_0", node.inputs.get("shift", 3))
            node.widgets = {}
        elif node.class_type == "EmptyAceStep1.5LatentAudio":
            node.inputs = {"seconds": 2, "batch_size": node.inputs.get("batch_size", node.inputs.get("widget_1", 1))}
            node.widgets = {}
        elif node.class_type == "TextEncodeAceStepAudio1.5":
            node.inputs.update(
                {
                    "tags": node.inputs.get("tags", node.inputs.get("widget_0", "synthwave, short instrumental")),
                    "lyrics": node.inputs.get("lyrics", node.inputs.get("widget_1", "Verse\nTiny signal in the night.")),
                    "seed": 561594583201063,
                    "duration": 2,
                    "bpm": 120,
                    "timesignature": node.inputs.get("timesignature", node.inputs.get("widget_6", "4")),
                    "language": node.inputs.get("language", node.inputs.get("widget_7", "en")),
                    "keyscale": node.inputs.get("keyscale", node.inputs.get("widget_8", "E minor")),
                    "generate_audio_codes": node.inputs.get("generate_audio_codes", node.inputs.get("widget_9", True)),
                    "cfg_scale": 1.5,
                    "top_p": 0.85,
                    "min_p": 0.9,
                    "top_k": 0,
                    "temperature": 0,
                }
            )
            for key in tuple(node.inputs):
                if key.startswith("widget_"):
                    node.inputs.pop(key)
            node.widgets = {}
        elif node.class_type == "SaveAudioMP3":
            node.inputs["filename_prefix"] = node.inputs.pop("widget_0", node.inputs.get("filename_prefix", "audio/vibecomfy_ace_step_smoke"))
            node.inputs["quality"] = node.inputs.pop("widget_1", node.inputs.get("quality", "V0"))
            node.widgets = {}
    workflow.metadata["smoke_duration_seconds"] = 2
    workflow.metadata["subgraph_materialized"] = True


def _replace_ace_primitive_edges(workflow: VibeWorkflow, source_id: str, value: object) -> None:
    workflow.nodes.pop(source_id, None)
    for edge in list(workflow.edges):
        if edge.from_node != source_id:
            continue
        target = workflow.nodes.get(edge.to_node)
        if target is not None:
            target.inputs[edge.to_input] = value
        workflow.edges.remove(edge)


def _apply_ltx_policy(workflow: VibeWorkflow, *, image_to_video: bool) -> None:
    for node in workflow.nodes.values():
        for key, value in list(node.inputs.items()):
            if isinstance(value, dict) or value is None:
                node.inputs.pop(key)
        for key, value in list(node.widgets.items()):
            if isinstance(value, dict) or value is None:
                node.widgets.pop(key)
        for key, value in list(node.inputs.items()):
            if value == "ltx-2.3-22b-dev.safetensors":
                node.inputs[key] = "ltx-2.3-22b-dev-fp8.safetensors"
            elif value == "comfy_gemma_3_12B_it.safetensors":
                node.inputs[key] = "gemma_3_12B_it_fp4_mixed.safetensors"
            elif isinstance(value, str) and value in {"gemma_3_12B_it_fp8_scaled.safetensors", "gemma_3_12B_it_fp4_mixed.safetensors"}:
                node.inputs[key] = "gemma_3_12B_it_fp4_mixed.safetensors"
            elif value == "ltx-2.3_text_projection_bf16.safetensors":
                node.inputs[key] = "ltx-2.3_text_projection_bf16.safetensors"
            elif isinstance(value, str) and value in {"LTX23_video_vae_bf16_KJ.safetensors", "LTX23_video_vae_bf16.safetensors"}:
                node.inputs[key] = "LTX23_video_vae_bf16.safetensors"
            elif isinstance(value, str) and value in {"LTX23_audio_vae_bf16_KJ.safetensors", "LTX23_audio_vae_bf16.safetensors"}:
                node.inputs[key] = "LTX23_audio_vae_bf16.safetensors"
            elif isinstance(value, str) and value.replace("\\", "/").endswith("taeltx2_3.safetensors"):
                node.inputs[key] = "taeltx2_3.safetensors"
            elif isinstance(value, str) and "ltx-2.3-22b-distilled" in value and "transformer_only" in value:
                node.inputs[key] = value.replace("\\", "/").rsplit("/", 1)[-1]
        for key, value in list(node.widgets.items()):
            if value == "ltx-2.3-22b-dev.safetensors":
                node.widgets[key] = "ltx-2.3-22b-dev-fp8.safetensors"
            elif value == "comfy_gemma_3_12B_it.safetensors":
                node.widgets[key] = "gemma_3_12B_it_fp4_mixed.safetensors"
            elif isinstance(value, str) and value in {"gemma_3_12B_it_fp8_scaled.safetensors", "gemma_3_12B_it_fp4_mixed.safetensors"}:
                node.widgets[key] = "gemma_3_12B_it_fp4_mixed.safetensors"
            elif value == "ltx-2.3_text_projection_bf16.safetensors":
                node.widgets[key] = "ltx-2.3_text_projection_bf16.safetensors"
            elif isinstance(value, str) and value in {"LTX23_video_vae_bf16_KJ.safetensors", "LTX23_video_vae_bf16.safetensors"}:
                node.widgets[key] = "LTX23_video_vae_bf16.safetensors"
            elif isinstance(value, str) and value in {"LTX23_audio_vae_bf16_KJ.safetensors", "LTX23_audio_vae_bf16.safetensors"}:
                node.widgets[key] = "LTX23_audio_vae_bf16.safetensors"
            elif isinstance(value, str) and value.replace("\\", "/").endswith("taeltx2_3.safetensors"):
                node.widgets[key] = "taeltx2_3.safetensors"
            elif isinstance(value, str) and "ltx-2.3-22b-distilled" in value and "transformer_only" in value:
                node.widgets[key] = value.replace("\\", "/").rsplit("/", 1)[-1]
        if node.class_type == "CreateVideo":
            node.inputs.pop("audio", None)
            node.inputs.setdefault("fps", 8)
            node.widgets["widget_0"] = 8
        elif node.class_type == "SaveVideo" and "widget_0" in node.widgets:
            node.widgets["widget_0"] = "output"
        elif node.class_type == "LoadImage" and node.widgets.get("widget_0") in {"example.png", "motion_track_input.jpg"}:
            node.widgets["widget_0"] = "egyptian_queen.png" if image_to_video else "example.png"
            node.inputs["image"] = node.widgets["widget_0"]
        elif node.class_type in {"LoadVideo", "VHS_LoadVideo"}:
            node.widgets["widget_0"] = "ltx_smoke_guide.mp4"
            node.inputs["file"] = "ltx_smoke_guide.mp4"
            node.inputs["video"] = "ltx_smoke_guide.mp4"
        elif node.class_type == "LTXICLoRALoaderModelOnly":
            lora_name = str(node.inputs.get("lora_name", node.widgets.get("widget_0", "")))
            if lora_name.startswith("ltxv/ltx2/"):
                normalized = lora_name.rsplit("/", 1)[-1]
                node.inputs["lora_name"] = normalized
                if node.widgets.get("widget_0") == lora_name:
                    node.widgets["widget_0"] = normalized
        elif node.class_type == "ResizeImageMaskNode":
            node.widgets["widget_1"] = 256
            for key in ("resize_type.shorter_size", "resize_type.longer_size", "shorter_size", "longer_size"):
                if key in node.inputs:
                    node.inputs[key] = 256
        elif node.class_type in {"DWPreprocessor", "CannyEdgePreprocessor"}:
            for key in ("resolution", "detect_resolution", "image_resolution", "widget_3"):
                if key in node.inputs:
                    node.inputs[key] = 256
                if key in node.widgets:
                    node.widgets[key] = 256
            if node.class_type == "CannyEdgePreprocessor":
                node.widgets["widget_2"] = 256
        elif node.class_type == "LTXAddVideoICLoRAGuide":
            node.widgets["widget_5"] = 128
            node.widgets["widget_6"] = 32
        elif node.class_type == "PrimitiveInt":
            node.widgets["widget_0"] = 5
        elif node.class_type == "PrimitiveFloat":
            node.widgets["widget_0"] = 8
        elif node.class_type == "LTXVConditioning":
            node.widgets["widget_0"] = 8
        elif node.class_type in {"BasicScheduler", "LTXVScheduler"}:
            node.inputs["steps"] = 1
            node.widgets["widget_0"] = 1
        elif node.class_type == "CFGGuider":
            node.widgets["widget_0"] = 2.5
        elif node.class_type == "LTXVEmptyLatentAudio":
            node.inputs["frames_number"] = 5
            node.inputs["frame_rate"] = 8
            node.widgets.update({"widget_0": 5, "widget_1": 8})
        elif node.class_type == "EmptyLTXVLatentVideo":
            node.inputs.update({"width": 256, "height": 256, "length": 5})
            node.widgets.update({"widget_0": 256, "widget_1": 256, "widget_2": 5})
        elif node.class_type == "LTXAVTextEncoderLoader":
            node.inputs.update(
                {
                    "text_encoder": "gemma_3_12B_it_fp4_mixed.safetensors",
                    "ckpt_name": "ltx-2.3-22b-dev-fp8.safetensors",
                }
            )
        elif node.class_type == "LTXVAudioVAELoader":
            node.class_type = "LowVRAMAudioVAELoader"
            node.inputs = {"ckpt_name": "ltx-2.3-22b-dev-fp8.safetensors"}
            node.widgets = {}
        elif node.class_type == "LoadVideoDepthAnythingModel":
            node.class_type = "DownloadAndLoadDepthAnythingV2Model"
            node.inputs = {"model": "depth_anything_v2_vits_fp32.safetensors", "precision": "fp32"}
            node.widgets = {}
        elif node.class_type == "VideoDepthAnythingProcess":
            node.class_type = "DepthAnything_V2"
            node.inputs = {}
            node.widgets = {}
        elif node.class_type == "CheckpointLoaderSimple" and any(
            "ltx-2.3-22b-dev-fp8.safetensors" == value for value in list(node.inputs.values()) + list(node.widgets.values())
        ):
            node.class_type = "LowVRAMCheckpointLoader"
            node.inputs = {"ckpt_name": "ltx-2.3-22b-dev-fp8.safetensors"}
            if "4960" in workflow.nodes:
                node.inputs["dependencies"] = ["4960", 0]
            node.widgets = {}
    if "4977" in workflow.nodes:
        workflow.nodes["4977"].widgets["widget_0"] = not image_to_video
    if "4981" in workflow.nodes:
        workflow.nodes["4981"].widgets["widget_1"] = 384
    _drop_unused_ltx_depth_output(workflow)
    _drop_unreferenced_ltx_ui_nodes(workflow)
    _bypass_ltx_latent_upscalers(workflow)
    _patch_ltx_video_audio_edges(workflow)
    for edge in workflow.edges:
        if edge.to_input == "vda_model":
            edge.to_input = "da_model"
    workflow.metadata["smoke_resolution"] = "256x256x5_frames"
    workflow.metadata["ltx_best_practices"] = [
        "Use the official Lightricks workflows as runtime gates where possible.",
        "Patch smoke runs to fp8/fp4 model assets, tiny frame counts, and low-VRAM loaders.",
        "Bypass latent spatial upscalers in smoke runs until HiddenSwitch Comfy exposes model_mmap_residency for LatentUpscaleModelManageable.",
        "Keep community audio, lip-sync, and long-form workflows as ready templates until their custom node packs and service credentials are declared.",
    ]
    workflow.metadata["comfy_configuration"] = {
        "reserve_vram": 12,
        "cache_none": True,
        "fp8_e4m3fn_text_enc": True,
    }
    workflow.requirements.custom_nodes.extend(["ComfyUI-LTXVideo", "ComfyUI-KJNodes"])


def _patch_ltx_video_audio_edges(workflow: VibeWorkflow) -> None:
    video_node_ids = {node_id for node_id, node in workflow.nodes.items() if node.class_type == "VHS_LoadVideo"}
    if not video_node_ids:
        return
    for edge in list(workflow.edges):
        if edge.to_input != "audio" or edge.from_node not in video_node_ids:
            continue
        audio_node = workflow.add_node("LoadAudio", audio="speech_smoke.wav", widget_0="speech_smoke.wav")
        workflow.replace_edge(f"{edge.to_node}.audio", f"{audio_node.id}.0")


def _bypass_ltx_latent_upscalers(workflow: VibeWorkflow) -> None:
    removed: set[str] = set()
    for node_id, node in list(workflow.nodes.items()):
        if node.class_type != "LTXVLatentUpsampler":
            continue
        source = next((edge for edge in workflow.edges if edge.to_node == node_id and edge.to_input == "samples"), None)
        if source is None:
            continue
        for edge in workflow.edges:
            if edge.from_node == node_id:
                edge.from_node = source.from_node
                edge.from_output = source.from_output
        removed.add(node_id)
        workflow.nodes.pop(node_id, None)
    if not removed:
        return
    workflow.edges = [edge for edge in workflow.edges if edge.to_node not in removed]
    referenced = {edge.from_node for edge in workflow.edges}
    unused_upscale_loaders = {
        node_id
        for node_id, node in workflow.nodes.items()
        if node.class_type == "LatentUpscaleModelLoader" and node_id not in referenced
    }
    for node_id in unused_upscale_loaders:
        workflow.nodes.pop(node_id, None)
    if unused_upscale_loaders:
        workflow.edges = [edge for edge in workflow.edges if edge.to_node not in unused_upscale_loaders]


def _drop_unused_ltx_depth_output(workflow: VibeWorkflow) -> None:
    unused_depth_outputs = {
        node_id
        for node_id, node in workflow.nodes.items()
        if node.class_type == "VideoDepthAnythingOutput"
        and not any(edge.from_node == node_id for edge in workflow.edges)
    }
    for node_id in unused_depth_outputs:
        workflow.nodes.pop(node_id, None)
    if unused_depth_outputs:
        workflow.edges = [
            edge for edge in workflow.edges if edge.from_node not in unused_depth_outputs and edge.to_node not in unused_depth_outputs
        ]


def _drop_unreferenced_ltx_ui_nodes(workflow: VibeWorkflow) -> None:
    ui_types = {"Fast Groups Bypasser (rgthree)", "easy showAnything", "Label (rgthree)", "PreviewAny"}
    changed = True
    while changed:
        removed = {
            node_id
            for node_id, node in workflow.nodes.items()
            if node.class_type in ui_types and not any(edge.from_node == node_id for edge in workflow.edges)
        }
        changed = bool(removed)
        for node_id in removed:
            workflow.nodes.pop(node_id, None)
        if removed:
            workflow.edges = [edge for edge in workflow.edges if edge.from_node not in removed and edge.to_node not in removed]


def _apply_wanvideo_wrapper_policy(workflow: VibeWorkflow) -> None:
    removed = {node_id for node_id, node in workflow.nodes.items() if node.class_type in {"Note", "MarkdownNote"}}
    for node_id in removed:
        workflow.nodes.pop(node_id, None)
    workflow.edges = [edge for edge in workflow.edges if edge.from_node not in removed and edge.to_node not in removed]
    for node in workflow.nodes.values():
        for key, value in list(node.inputs.items()):
            if value == "WanVideo\\Lightx2v\\lightx2v_T2V_14B_cfg_step_distill_v2_lora_rank64_bf16_.safetensors":
                node.inputs[key] = "WanVideo\\Lightx2v\\lightx2v_T2V_14B_cfg_step_distill_v2_lora_rank64_bf16.safetensors"
            elif value == "WanVid\\wan2.1-1.3b-control-lora-tile-v0.1_comfy.safetensors":
                node.inputs[key] = "WanVid\\wan2.1-1.3b-control-lora-tile-v1.1_comfy.safetensors"
        for key, value in list(node.widgets.items()):
            if value == "WanVideo\\Lightx2v\\lightx2v_T2V_14B_cfg_step_distill_v2_lora_rank64_bf16_.safetensors":
                node.widgets[key] = "WanVideo\\Lightx2v\\lightx2v_T2V_14B_cfg_step_distill_v2_lora_rank64_bf16.safetensors"
            elif value == "WanVid\\wan2.1-1.3b-control-lora-tile-v0.1_comfy.safetensors":
                node.widgets[key] = "WanVid\\wan2.1-1.3b-control-lora-tile-v1.1_comfy.safetensors"
        if node.class_type in {"WanVideoEmptyEmbeds", "WanVideoImageToVideoEncode"}:
            node.inputs.update({"width": 256, "height": 256, "num_frames": 5})
            node.widgets.update({"widget_0": 256, "widget_1": 256, "widget_2": 5})
        elif node.class_type == "WanVideoModelLoader":
            if node.inputs.get("base_precision") == "fp16_fast":
                node.inputs["base_precision"] = "fp16"
            if node.inputs.get("widget_1") == "fp16_fast":
                node.inputs["widget_1"] = "fp16"
            if node.widgets.get("widget_1") == "fp16_fast":
                node.widgets["widget_1"] = "fp16"
            if node.inputs.get("attention_mode") == "sageattn":
                node.inputs["attention_mode"] = "sdpa"
            if node.inputs.get("widget_4") == "sageattn":
                node.inputs["widget_4"] = "sdpa"
            if node.widgets.get("widget_4") == "sageattn":
                node.widgets["widget_4"] = "sdpa"
        elif node.class_type == "ImageResizeKJv2":
            node.inputs.update({"width": 256, "height": 256})
            node.widgets.update({"widget_0": 256, "widget_1": 256})
        elif node.class_type == "WanVideoSampler":
            node.inputs["steps"] = 1
            node.widgets["widget_0"] = 1
        elif node.class_type == "VHS_VideoCombine":
            node.inputs["save_output"] = True
            if node.inputs.get("widget_8") is False:
                node.inputs["widget_8"] = True
            if node.widgets.get("widget_8") is False:
                node.widgets["widget_8"] = True
        elif node.class_type == "VHS_LoadVideo":
            node.inputs.setdefault("video", "wolf_interpolated.mp4")
    workflow.metadata["smoke_resolution"] = "256x256x5_frames"
    workflow.requirements.custom_nodes.extend(["ComfyUI-WanVideoWrapper", "ComfyUI-KJNodes", "ComfyUI-VideoHelperSuite"])


def _write_ready_template(item: dict, workflow: VibeWorkflow) -> None:
    _sync_custom_node_requirements(workflow)
    _finalise_model_assets(workflow)
    category = _ready_category(item)
    template_id = _ready_template_id(item)
    path = READY_ROOT / category / f"{item['id']}.py"
    path.parent.mkdir(parents=True, exist_ok=True)
    api = workflow.compile("api")
    metadata = dict(workflow.metadata)
    requirements = {
        "models": workflow.metadata.get("model_assets", []),
        "custom_nodes": sorted(workflow.requirements.custom_nodes),
    }
    text = f'''from __future__ import annotations

from vibecomfy.registry.ready_template import build_api_ready_workflow


API_WORKFLOW = {pformat(api, width=120, sort_dicts=False)}

READY_METADATA = {pformat(metadata, width=120, sort_dicts=False)}

READY_REQUIREMENTS = {pformat(requirements, width=120, sort_dicts=False)}


def build():
    return build_api_ready_workflow(
        API_WORKFLOW,
        source_path=__file__,
        workflow_id=READY_METADATA.get("ready_template", "{template_id}"),
        ready_metadata=READY_METADATA,
        requirements=READY_REQUIREMENTS,
    )
'''
    path.write_text(text, encoding="utf-8")
    print(path.relative_to(ROOT))


def _ready_category(item: dict) -> str:
    return "edit" if item["task"] == "image_edit" else item["media"]


def _ready_template_id(item: dict) -> str:
    return f"{_ready_category(item)}/{item['id']}"


def _sync_custom_node_requirements(workflow: VibeWorkflow) -> None:
    class_types = {node.class_type for node in workflow.nodes.values()}
    for pack in resolve_node_packs(class_types):
        if pack.name not in workflow.requirements.custom_nodes:
            workflow.requirements.custom_nodes.append(pack.name)


_MODEL_EXTENSIONS = (".safetensors", ".ckpt", ".gguf", ".pt", ".bin", ".pth")


def _referenced_model_filenames(workflow: VibeWorkflow) -> set[str]:
    filenames: set[str] = set()
    for node in workflow.nodes.values():
        for value in list(node.inputs.values()) + list(node.widgets.values()):
            if isinstance(value, str) and value.endswith(_MODEL_EXTENSIONS):
                filenames.add(value)
                filenames.add(Path(value.replace("\\", "/")).name)
    return filenames


def _finalise_model_assets(workflow: VibeWorkflow) -> None:
    referenced = _referenced_model_filenames(workflow)
    raw_assets = workflow.metadata.get("model_assets", [])
    extra_assets = workflow.metadata.pop("model_assets_extra", [])
    replaced_by_policy = set(workflow.metadata.pop("model_assets_replaced_by_policy", []))
    filtered = [
        asset
        for asset in raw_assets
        if isinstance(asset, dict)
        and isinstance(asset.get("name"), str)
        and asset["name"] not in replaced_by_policy
        and (asset["name"] in referenced or _asset_name_appears_in_workflow_text(workflow, asset["name"]))
    ]
    combined = filtered + [asset for asset in extra_assets if isinstance(asset, dict)]
    final_assets: list[dict] = []
    seen: set[tuple[object, object]] = set()
    for asset in combined:
        key = (asset.get("name"), asset.get("subdir"))
        if key in seen:
            continue
        seen.add(key)
        final_assets.append(asset)
    workflow.metadata["model_assets"] = final_assets


def _asset_name_appears_in_workflow_text(workflow: VibeWorkflow, name: str) -> bool:
    for node in workflow.nodes.values():
        for value in list(node.inputs.values()) + list(node.widgets.values()):
            if isinstance(value, str) and name in value:
                return True
    return False


if __name__ == "__main__":
    raise SystemExit(main())
