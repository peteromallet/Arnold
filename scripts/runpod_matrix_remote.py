from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from vibecomfy.ingest.loader import load_template
from vibecomfy.ingest.normalize import normalize_to_api


LTX_CHECKPOINT = "ltx-2.3-22b-dev-fp8.safetensors"
LTX_TEXT_ENCODER = "gemma_3_12B_it_fp4_mixed.safetensors"
LTX_TEXT_PROJECTION = "ltx-2.3_text_projection_bf16.safetensors"
LTX_VIDEO_VAE = "LTX23_video_vae_bf16.safetensors"
LTX_AUDIO_VAE = "LTX23_audio_vae_bf16.safetensors"
LTX_PREVIEW_VAE = "taeltx2_3.safetensors"
GGUF_MODEL = "flux-2-klein-9b-Q4_K_M.gguf"
FLUX_VAE = "flux2-vae.safetensors"


def prepare_workflow(workflow_id: str, source: Path, output: Path) -> Path:
    api = normalize_to_api(load_template(source))
    if not patch_workflow_api(workflow_id, api):
        return source
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(api, indent=2), encoding="utf-8")
    return output


def patch_workflow_api(workflow_id: str, api: dict[str, Any]) -> bool:
    if workflow_id == "ltx2_3_t2v":
        _patch_ltx(api, image_to_video=False)
        return True
    if workflow_id == "ltx2_3_i2v":
        _patch_ltx(api, image_to_video=True)
        return True
    if workflow_id.startswith("ltx2_3_lightricks"):
        _patch_ltx_official(api)
        return True
    if workflow_id.startswith("ltx2_3"):
        _patch_ltx_official(api)
        return True
    if workflow_id == "flux2_klein_9b_gguf_t2i":
        _patch_gguf(api)
        return True
    if workflow_id.startswith("wanvideo_wrapper"):
        _patch_wanvideo_wrapper(api)
        return True
    if workflow_id.startswith("ace_step"):
        _patch_ace_step(api)
        return True
    return False


def _patch_ace_step(api: dict[str, Any]) -> None:
    _replace_ace_primitive_links(api, "126", 561594583201063)
    _replace_ace_primitive_links(api, "110", 2)
    for node in list(api.values()):
        if not isinstance(node, dict):
            continue
        inputs = node.get("inputs", {})
        class_type = node.get("class_type")
        if class_type == "DualCLIPLoader":
            node["inputs"] = {
                "clip_name1": inputs.get("clip_name1", inputs.get("widget_0", "qwen_0.6b_ace15.safetensors")),
                "clip_name2": inputs.get("clip_name2", inputs.get("widget_1", "qwen_4b_ace15.safetensors")),
                "type": inputs.get("type", inputs.get("widget_2", "ace")),
                "device": inputs.get("device", inputs.get("widget_3", "default")),
            }
        elif class_type == "VAELoader":
            node["inputs"] = {"vae_name": inputs.get("vae_name", inputs.get("widget_0", "ace_1.5_vae.safetensors"))}
        elif class_type == "UNETLoader":
            node["inputs"] = {
                "unet_name": inputs.get("unet_name", inputs.get("widget_0", "acestep_v1.5_turbo.safetensors")),
                "weight_dtype": inputs.get("weight_dtype", inputs.get("widget_1", "default")),
            }
        elif class_type == "KSampler":
            node["inputs"] = {
                "model": inputs["model"],
                "positive": inputs["positive"],
                "negative": inputs["negative"],
                "latent_image": inputs["latent_image"],
                "seed": inputs.get("seed", inputs.get("widget_0", 561594583201063)),
                "steps": 1,
                "cfg": 1,
                "sampler_name": "euler",
                "scheduler": "simple",
                "denoise": 1,
            }
        elif class_type == "ModelSamplingAuraFlow":
            node["inputs"] = {"model": inputs["model"], "shift": inputs.get("shift", inputs.get("widget_0", 3))}
        elif class_type == "EmptyAceStep1.5LatentAudio":
            node["inputs"] = {"seconds": 2, "batch_size": inputs.get("batch_size", inputs.get("widget_1", 1))}
        elif class_type == "TextEncodeAceStepAudio1.5":
            node["inputs"] = {
                "clip": inputs["clip"],
                "tags": inputs.get("tags", inputs.get("widget_0", "synthwave, short instrumental")),
                "lyrics": inputs.get("lyrics", inputs.get("widget_1", "Verse\nTiny signal in the night.")),
                "seed": inputs.get("seed", inputs.get("widget_2", 561594583201063)),
                "duration": 2,
                "bpm": 120,
                "timesignature": inputs.get("timesignature", inputs.get("widget_6", "4")),
                "language": inputs.get("language", inputs.get("widget_7", "en")),
                "keyscale": inputs.get("keyscale", inputs.get("widget_8", "E minor")),
                "generate_audio_codes": inputs.get("generate_audio_codes", inputs.get("widget_9", True)),
                "cfg_scale": 1.5,
                "top_p": 0.85,
                "min_p": 0.9,
                "top_k": 0,
                "temperature": 0,
            }
        elif class_type == "SaveAudioMP3":
            node["inputs"] = {
                "audio": inputs["audio"],
                "filename_prefix": inputs.get("filename_prefix", inputs.get("widget_0", "audio/vibecomfy_ace_step_smoke")),
                "quality": inputs.get("quality", inputs.get("widget_1", "V0")),
            }


def _replace_ace_primitive_links(api: dict[str, Any], source_id: str, value: Any) -> None:
    api.pop(source_id, None)
    for node in api.values():
        if not isinstance(node, dict):
            continue
        for key, current in list(node.get("inputs", {}).items()):
            if isinstance(current, list) and len(current) == 2 and str(current[0]) == source_id:
                node["inputs"][key] = value


def _patch_ltx(api: dict[str, Any], *, image_to_video: bool) -> None:
    _patch_ltx_common(api)
    if not all(node_id in api for node_id in ("4977", "2004", "4981")):
        return
    for node in api.values():
        if not isinstance(node, dict):
            continue
        inputs = node.get("inputs", {})
        for key, value in list(inputs.items()):
            if isinstance(value, dict) or value is None:
                inputs.pop(key)
        for key, value in list(inputs.items()):
            if value == "ltx-2.3-22b-dev.safetensors":
                inputs[key] = LTX_CHECKPOINT
            elif value == "comfy_gemma_3_12B_it.safetensors":
                inputs[key] = LTX_TEXT_ENCODER
    api["3059"]["inputs"].update({"widget_0": 256, "widget_1": 256, "widget_2": 5})
    api["4979"]["inputs"]["widget_0"] = 5
    api["4978"]["inputs"]["widget_0"] = 4
    api["1241"]["inputs"]["widget_0"] = 4
    api["3980"]["inputs"].update({"widget_0": 5, "widget_1": 4})
    api["4977"]["inputs"]["widget_0"] = not image_to_video
    api["2004"]["inputs"]["widget_0"] = "egyptian_queen.png" if image_to_video else "example.png"
    api["4981"]["inputs"]["widget_1"] = 256
    if "4819" in api:
        api["4819"]["inputs"].pop("audio", None)
    if "4849" in api:
        api["4849"]["inputs"].pop("audio", None)
    if "4010" in api:
        api["4010"]["class_type"] = "LowVRAMAudioVAELoader"
        api["4010"]["inputs"] = {"ckpt_name": LTX_CHECKPOINT}
    if "3940" in api:
        api["3940"]["class_type"] = "LowVRAMCheckpointLoader"
        api["3940"]["inputs"] = {"ckpt_name": LTX_CHECKPOINT}
        if "4960" in api:
            api["3940"]["inputs"]["dependencies"] = ["4960", 0]


def _patch_ltx_official(api: dict[str, Any]) -> None:
    _patch_ltx_common(api)


def _patch_ltx_common(api: dict[str, Any]) -> None:
    audio_node_ids: set[str] = set()
    for node_id, node in api.items():
        if not isinstance(node, dict):
            continue
        inputs = node.get("inputs", {})
        for key, value in list(inputs.items()):
            if isinstance(value, dict):
                inputs.pop(key)
        for key, value in list(inputs.items()):
            if value == "ltx-2.3-22b-dev.safetensors":
                inputs[key] = LTX_CHECKPOINT
            elif value == "comfy_gemma_3_12B_it.safetensors":
                inputs[key] = LTX_TEXT_ENCODER
            elif isinstance(value, str) and value in {"gemma_3_12B_it_fp8_scaled.safetensors", "gemma_3_12B_it_fp4_mixed.safetensors"}:
                inputs[key] = LTX_TEXT_ENCODER
            elif value == "ltx-2.3_text_projection_bf16.safetensors":
                inputs[key] = LTX_TEXT_PROJECTION
            elif isinstance(value, str) and value in {"LTX23_video_vae_bf16_KJ.safetensors", "LTX23_video_vae_bf16.safetensors"}:
                inputs[key] = LTX_VIDEO_VAE
            elif isinstance(value, str) and value in {"LTX23_audio_vae_bf16_KJ.safetensors", "LTX23_audio_vae_bf16.safetensors"}:
                inputs[key] = LTX_AUDIO_VAE
            elif isinstance(value, str) and value.replace("\\", "/").endswith("taeltx2_3.safetensors"):
                inputs[key] = LTX_PREVIEW_VAE
            elif isinstance(value, str) and "ltx-2.3-22b-distilled" in value and "transformer_only" in value:
                inputs[key] = value.replace("\\", "/").rsplit("/", 1)[-1]
        class_type = node.get("class_type")
        if class_type == "EmptyLTXVLatentVideo":
            inputs.update({"width": 256, "height": 256, "length": 5, "widget_0": 256, "widget_1": 256, "widget_2": 5})
        elif class_type == "PrimitiveInt":
            inputs["widget_0"] = 5
        elif class_type == "PrimitiveFloat":
            inputs["widget_0"] = 8
        elif class_type == "LTXVConditioning":
            inputs["widget_0"] = 8
            inputs.setdefault("frame_rate", 8)
        elif class_type in {"BasicScheduler", "LTXVScheduler"}:
            inputs["steps"] = 1
            inputs["widget_0"] = 1
        elif class_type == "CFGGuider":
            inputs["widget_0"] = 2.5
        elif class_type == "LTXVEmptyLatentAudio":
            inputs.update({"frames_number": 5, "frame_rate": 8, "widget_0": 5, "widget_1": 8})
        elif class_type == "CreateVideo":
            inputs.pop("audio", None)
            inputs["fps"] = 8
            inputs["widget_0"] = 8
        elif class_type == "SaveVideo":
            inputs["widget_0"] = "output"
        elif class_type == "LoadImage":
            inputs["widget_0"] = "example.png"
            inputs["image"] = "example.png"
        elif class_type in {"LoadVideo", "VHS_LoadVideo"}:
            inputs["widget_0"] = "ltx_smoke_guide.mp4"
            inputs["file"] = "ltx_smoke_guide.mp4"
            inputs["video"] = "ltx_smoke_guide.mp4"
            if class_type == "VHS_LoadVideo":
                audio_node_ids.add(str(node_id))
        elif class_type == "LTXICLoRALoaderModelOnly":
            lora_name = str(inputs.get("lora_name", ""))
            if lora_name.startswith("ltxv/ltx2/"):
                inputs["lora_name"] = lora_name.rsplit("/", 1)[-1]
        elif class_type == "ResizeImageMaskNode":
            inputs["widget_1"] = 256
            for key in ("resize_type.shorter_size", "resize_type.longer_size", "shorter_size", "longer_size"):
                if key in inputs:
                    inputs[key] = 256
        elif class_type in {"DWPreprocessor", "CannyEdgePreprocessor"}:
            for key in ("resolution", "detect_resolution", "image_resolution", "widget_3"):
                if key in inputs:
                    inputs[key] = 256
            if class_type == "CannyEdgePreprocessor":
                inputs["widget_2"] = 256
        elif class_type == "LTXAddVideoICLoRAGuide":
            inputs["widget_5"] = 128
            inputs["widget_6"] = 32
        elif class_type == "LTXAVTextEncoderLoader":
            inputs.update({"text_encoder": LTX_TEXT_ENCODER, "ckpt_name": LTX_CHECKPOINT, "widget_0": LTX_TEXT_ENCODER, "widget_1": LTX_CHECKPOINT})
        elif class_type == "LTXVAudioVAELoader":
            node["class_type"] = "LowVRAMAudioVAELoader"
            node["inputs"] = {"ckpt_name": LTX_CHECKPOINT}
        elif class_type == "LoadVideoDepthAnythingModel":
            node["class_type"] = "DownloadAndLoadDepthAnythingV2Model"
            node["inputs"] = {"model": "depth_anything_v2_vits_fp32.safetensors", "precision": "fp32"}
        elif class_type == "VideoDepthAnythingProcess":
            node["class_type"] = "DepthAnything_V2"
            for key in ("widget_0", "widget_1", "widget_2"):
                inputs.pop(key, None)
        elif class_type == "CheckpointLoaderSimple" and any(value == LTX_CHECKPOINT for value in inputs.values()):
            node["class_type"] = "LowVRAMCheckpointLoader"
            node["inputs"] = {"ckpt_name": LTX_CHECKPOINT}
            if "4960" in api:
                node["inputs"]["dependencies"] = ["4960", 0]
    _drop_unused_ltx_depth_output(api)
    _drop_unreferenced_ltx_ui_nodes(api)
    _bypass_ltx_latent_upscalers(api)
    _patch_ltx_video_audio_inputs(api, audio_node_ids)
    for node in api.values():
        if not isinstance(node, dict):
            continue
        inputs = node.get("inputs", {})
        if "vda_model" in inputs:
            inputs["da_model"] = inputs.pop("vda_model")


def _patch_ltx_video_audio_inputs(api: dict[str, Any], video_node_ids: set[str]) -> None:
    if not video_node_ids:
        return
    for node_id, node in list(api.items()):
        if not isinstance(node, dict):
            continue
        inputs = node.get("inputs", {})
        audio = inputs.get("audio")
        if not (isinstance(audio, list) and len(audio) == 2 and str(audio[0]) in video_node_ids):
            continue
        load_audio_id = f"{node_id}_vibe_audio"
        api[load_audio_id] = {"class_type": "LoadAudio", "inputs": {"audio": "speech_smoke.wav", "widget_0": "speech_smoke.wav"}}
        inputs["audio"] = [load_audio_id, 0]


def _bypass_ltx_latent_upscalers(api: dict[str, Any]) -> None:
    removed: set[str] = set()
    for node_id, node in list(api.items()):
        if not isinstance(node, dict) or node.get("class_type") != "LTXVLatentUpsampler":
            continue
        source = node.get("inputs", {}).get("samples")
        if not (isinstance(source, list) and len(source) == 2):
            continue
        for other in api.values():
            if not isinstance(other, dict):
                continue
            for key, value in list(other.get("inputs", {}).items()):
                if isinstance(value, list) and len(value) == 2 and str(value[0]) == str(node_id):
                    other["inputs"][key] = source
        removed.add(str(node_id))
        api.pop(node_id, None)
    if not removed:
        return
    referenced = {
        str(value[0])
        for node in api.values()
        if isinstance(node, dict)
        for value in node.get("inputs", {}).values()
        if isinstance(value, list) and len(value) == 2
    }
    for node_id, node in list(api.items()):
        if isinstance(node, dict) and node.get("class_type") == "LatentUpscaleModelLoader" and str(node_id) not in referenced:
            api.pop(node_id, None)


def _drop_unused_ltx_depth_output(api: dict[str, Any]) -> None:
    referenced = {
        str(value[0])
        for node in api.values()
        if isinstance(node, dict)
        for value in node.get("inputs", {}).values()
        if isinstance(value, list) and len(value) == 2
    }
    for node_id, node in list(api.items()):
        if isinstance(node, dict) and node.get("class_type") == "VideoDepthAnythingOutput" and str(node_id) not in referenced:
            api.pop(node_id)


def _drop_unreferenced_ltx_ui_nodes(api: dict[str, Any]) -> None:
    ui_types = {"Fast Groups Bypasser (rgthree)", "easy showAnything", "Label (rgthree)", "PreviewAny"}
    changed = True
    while changed:
        changed = False
        referenced = {
            str(value[0])
            for node in api.values()
            if isinstance(node, dict)
            for value in node.get("inputs", {}).values()
            if isinstance(value, list) and len(value) == 2
        }
        for node_id, node in list(api.items()):
            if isinstance(node, dict) and node.get("class_type") in ui_types and str(node_id) not in referenced:
                api.pop(node_id)
                changed = True


def _patch_gguf(api: dict[str, Any]) -> None:
    for node in api.values():
        if not isinstance(node, dict):
            continue
        inputs = node.get("inputs", {})
        if node.get("class_type") == "UNETLoader" and "unet_name" in inputs:
            node["class_type"] = "UnetLoaderGGUF"
            inputs["unet_name"] = GGUF_MODEL
        if node.get("class_type") == "VAELoader" and inputs.get("vae_name") == "full_encoder_small_decoder.safetensors":
            inputs["vae_name"] = FLUX_VAE


def _patch_wanvideo_wrapper(api: dict[str, Any]) -> None:
    _strip_ui_only_nodes(api)
    for node in api.values():
        if not isinstance(node, dict):
            continue
        inputs = node.get("inputs", {})
        class_type = node.get("class_type")
        for key, value in list(inputs.items()):
            if not isinstance(value, str):
                continue
            if value == "WanVideo\\Lightx2v\\lightx2v_T2V_14B_cfg_step_distill_v2_lora_rank64_bf16_.safetensors":
                inputs[key] = "WanVideo\\Lightx2v\\lightx2v_T2V_14B_cfg_step_distill_v2_lora_rank64_bf16.safetensors"
            elif value == "WanVid\\wan2.1-1.3b-control-lora-tile-v0.1_comfy.safetensors":
                inputs[key] = "WanVid\\wan2.1-1.3b-control-lora-tile-v1.1_comfy.safetensors"
            elif value in {
                "WanVideo\\InfiniteTalk\\InfiniteTalk\\Wan2_1-InfiniteTalk_Single_Q8.gguf",
                "WanVideo/InfiniteTalk/InfiniteTalk/Wan2_1-InfiniteTalk_Single_Q8.gguf",
            }:
                inputs[key] = "WanVideo/InfiniteTalk/InfiniteTalk/Wan2_1-InfiniteTalk_Single_Q4_K_M.gguf"
            elif value in {
                "WanVideo\\wan2.1-i2v-14b-480p-Q8_0.gguf",
                "WanVideo/wan2.1-i2v-14b-480p-Q8_0.gguf",
            }:
                inputs[key] = "WanVideo/wan2.1-i2v-14b-480p-Q4_K_M.gguf"
        if class_type in {"WanVideoEmptyEmbeds", "WanVideoImageToVideoEncode"}:
            inputs.update({"width": 256, "height": 256, "num_frames": 5, "widget_0": 256, "widget_1": 256, "widget_2": 5})
        elif class_type == "WanVideoModelLoader":
            if inputs.get("base_precision") == "fp16_fast":
                inputs["base_precision"] = "fp16"
            if inputs.get("widget_1") == "fp16_fast":
                inputs["widget_1"] = "fp16"
            if inputs.get("attention_mode") == "sageattn":
                inputs["attention_mode"] = "sdpa"
            if inputs.get("widget_4") == "sageattn":
                inputs["widget_4"] = "sdpa"
        elif class_type == "ImageResizeKJv2":
            inputs.update({"width": 256, "height": 256, "widget_0": 256, "widget_1": 256})
        elif class_type == "WanVideoSampler":
            inputs.update({"steps": 1, "widget_0": 1})
            if isinstance(inputs.get("start_step"), int) and inputs["start_step"] >= inputs["steps"]:
                inputs["start_step"] = 0
            if isinstance(inputs.get("widget_8"), int) and inputs["widget_8"] >= inputs["steps"]:
                inputs["widget_8"] = 0
        elif class_type == "VHS_VideoCombine":
            inputs["save_output"] = True
            if inputs.get("widget_8") is False:
                inputs["widget_8"] = True
        elif class_type == "VHS_LoadVideo":
            inputs.setdefault("video", "wolf_interpolated.mp4")
            inputs.setdefault("file", inputs.get("video", "wolf_interpolated.mp4"))
            if inputs.get("video") in {"bubble.mp4", "10.mp4"}:
                inputs["file"] = inputs["video"]
            if "frame_load_cap" in inputs and not isinstance(inputs["frame_load_cap"], list):
                inputs["frame_load_cap"] = 5
        elif class_type == "LoadImage":
            image_name = inputs.get("image") or inputs.get("widget_0") or "example.png"
            inputs["image"] = image_name
            inputs["widget_0"] = image_name
        elif class_type == "LoadAudio":
            audio_name = "speech_smoke.wav"
            inputs["audio"] = audio_name
            inputs["widget_0"] = audio_name


def _strip_ui_only_nodes(api: dict[str, Any]) -> None:
    removed = {node_id for node_id, node in api.items() if isinstance(node, dict) and node.get("class_type") in {"Note", "MarkdownNote"}}
    if not removed:
        return
    for node_id in removed:
        api.pop(node_id, None)
    for node in api.values():
        if not isinstance(node, dict):
            continue
        inputs = node.get("inputs", {})
        for key, value in list(inputs.items()):
            if isinstance(value, list) and value and str(value[0]) in removed:
                inputs.pop(key)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="cmd", required=True)
    prepare = subparsers.add_parser("prepare-workflow")
    prepare.add_argument("workflow_id")
    prepare.add_argument("source", type=Path)
    prepare.add_argument("output", type=Path)
    args = parser.parse_args(argv)

    if args.cmd == "prepare-workflow":
        print(prepare_workflow(args.workflow_id, args.source, args.output).as_posix())
        return 0
    raise AssertionError(args.cmd)


if __name__ == "__main__":
    raise SystemExit(main())
