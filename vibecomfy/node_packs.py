from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from vibecomfy.node_packs_lockfile import LockEntry, read_lockfile


@dataclass(frozen=True, slots=True)
class CustomNodePack:
    name: str
    repo: str
    classes: frozenset[str]
    pip_packages: tuple[str, ...] = ()
    class_schema_sha256: str | None = None


_STATIC_NODE_PACKS: tuple[CustomNodePack, ...] = (
    CustomNodePack(
        name="ComfyUI-WanVideoWrapper",
        repo="https://github.com/kijai/ComfyUI-WanVideoWrapper.git",
        classes=frozenset(
            {
                "LoadWanVideoT5TextEncoder",
                "CreateCFGScheduleFloatList",
                "WanVideoBlockSwap",
                "WanVideoEncode",
                "WanVideoVAELoader",
                "WanVideoTorchCompileSettings",
                "WanVideoModelLoader",
                "WanVideoEmptyEmbeds",
                "WanVideoImageToVideoEncode",
                "WanVideoDecode",
                "WanVideoExperimentalArgs",
                "WanVideoEasyCache",
                "WanVideoSampler",
                "WanVideoTextEncode",
                "WanVideoTextEncodeCached",
                "WanVideoTextEmbedBridge",
                "WanVideoLoraSelect",
                "WanVideoLoraSelectMulti",
                "WanVideoSetBlockSwap",
                "WanVideoSetLoRAs",
                "WanVideoSLG",
                "WanVideoControlEmbeds",
                "WanVideoVACEEncode",
                "WanVideoVACEModelSelect",
                "WanVideoVACEStartToEndFrame",
            }
        ),
        pip_packages=("onnx", "opencv-python-headless"),
    ),
    CustomNodePack(
        name="ComfyUI-LTXVideo",
        repo="https://github.com/Lightricks/ComfyUI-LTXVideo.git",
        classes=frozenset(
            {
                "LTXAVTextEncoderLoader",
                "LTX2AttentionTunerPatch",
                "LTX2_NAG",
                "LTXVConditioning",
                "LTXVImgToVideo",
                "LTXVImgToVideoInplaceKJ",
                "EmptyLTXVLatentVideo",
                "LTXVAudioVAELoader",
                "LTXVAudioVAEDecode",
                "LTXVChunkFeedForward",
                "LTXVConcatAVLatent",
                "LTXVCropGuides",
                "LTXVEmptyLatentAudio",
                "LTXVPreprocess",
                "LTXVScheduler",
                "LTXVSeparateAVLatent",
                "LatentUpscaleModelLoader",
            }
        ),
    ),
    CustomNodePack(
        name="ComfyUI-KJNodes",
        repo="https://github.com/kijai/ComfyUI-KJNodes.git",
        classes=frozenset(
            {
                "BlockifyMask",
                "DrawMaskOnImage",
                "ImageResizeKJv2",
                "PreviewAnimation",
                "GetImageRangeFromBatch",
                "GetImageSize",
                "GetImageSizeAndCount",
                "INTConstant",
                "LTXVAddGuide",
                "PathchSageAttentionKJ",
                "PointsEditor",
                "ResizeImagesByLongerEdge",
                "SimpleCalculatorKJ",
                "VAELoaderKJ",
            }
        ),
        pip_packages=("matplotlib",),
    ),
    CustomNodePack(
        name="ComfyUI-VideoHelperSuite",
        repo="https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite.git",
        classes=frozenset({"VHS_LoadVideo", "VHS_VideoCombine"}),
    ),
    CustomNodePack(
        name="ComfyUI-segment-anything-2",
        repo="https://github.com/kijai/ComfyUI-segment-anything-2.git",
        classes=frozenset(
            {
                "DownloadAndLoadSAM2Model",
                "Sam2Segmentation",
                "Sam2AutoSegmentation",
                "Sam2VideoSegmentation",
                "Sam2VideoSegmentationAddPoints",
                "Florence2toCoordinates",
            }
        ),
        pip_packages=("opencv-python-headless",),
    ),
    CustomNodePack(
        name="ComfyUI-WanAnimatePreprocess",
        repo="https://github.com/kijai/ComfyUI-WanAnimatePreprocess.git",
        classes=frozenset(
            {
                "OnnxDetectionModelLoader",
                "PoseAndFaceDetection",
                "DrawViTPose",
                "PoseRetargetPromptHelper",
                "PoseDetectionOneToAllAnimation",
            }
        ),
        pip_packages=("onnx", "onnxruntime-gpu", "opencv-python-headless"),
    ),
    CustomNodePack(
        name="comfyui_controlnet_aux",
        repo="https://github.com/Fannovel16/comfyui_controlnet_aux.git",
        classes=frozenset({"DWPreprocessor", "CannyEdgePreprocessor"}),
        pip_packages=("onnxruntime", "opencv-python-headless"),
    ),
    CustomNodePack(
        name="ComfyUI-DepthAnythingV2",
        repo="https://github.com/kijai/ComfyUI-DepthAnythingV2.git",
        classes=frozenset(
            {
                "DownloadAndLoadDepthAnythingV2Model",
                "DepthAnything_V2",
                "LoadVideoDepthAnythingModel",
                "VideoDepthAnythingProcess",
                "VideoDepthAnythingOutput",
            }
        ),
        pip_packages=("transformers", "opencv-python-headless"),
    ),
    CustomNodePack(
        name="ComfyUI-GGUF",
        repo="https://github.com/city96/ComfyUI-GGUF.git",
        classes=frozenset({"DualCLIPLoaderGGUF", "UnetLoaderGGUF"}),
        pip_packages=("gguf",),
    ),
    CustomNodePack(
        name="rgthree-comfy",
        repo="https://github.com/rgthree/rgthree-comfy.git",
        classes=frozenset(
            {
                "Any Switch (rgthree)",
                "Fast Groups Bypasser (rgthree)",
                "Fast Groups Muter (rgthree)",
                "GetNode",
                "Label (rgthree)",
                "Power Lora Loader (rgthree)",
                "Seed (rgthree)",
                "SetNode",
            }
        ),
    ),
    CustomNodePack(
        name="ComfyUI-Qwen3-TTS",
        repo="https://github.com/DarioFT/ComfyUI-Qwen3-TTS.git",
        classes=frozenset(
            {
                "Qwen3Loader",
                "Qwen3CustomVoice",
                "Qwen3VoiceDesign",
                "Qwen3VoiceClone",
                "Qwen3PromptMaker",
                "Qwen3SavePrompt",
                "Qwen3LoadPrompt",
                "Qwen3DatasetFromFolder",
                "Qwen3DataPrep",
                "Qwen3FineTune",
                "Qwen3AudioCompare",
            }
        ),
        pip_packages=("qwen-tts", "modelscope", "soundfile", "librosa", "accelerate"),
    ),
    CustomNodePack(
        name="ComfyUI-QwenTTS",
        repo="https://github.com/1038lab/ComfyUI-QwenTTS.git",
        classes=frozenset(
            {
                "AILab_Qwen3TTSCustomVoice",
                "AILab_Qwen3TTSCustomVoice_Advanced",
                "AILab_Qwen3TTSVoiceDesign",
                "AILab_Qwen3TTSVoiceDesign_Advanced",
                "AILab_Qwen3TTSVoiceClone",
                "AILab_Qwen3TTSVoiceClone_Advanced",
                "AILab_Qwen3TTSVoicesLibrary",
                "AILab_Qwen3TTSLoadVoice",
                "AILab_Qwen3TTSWhisperSTT",
                "AILab_Qwen3TTSVoiceInstruct",
                "AILab_Qwen3TTSVoiceInstructZH",
            }
        ),
        pip_packages=("qwen-tts", "openai-whisper", "soundfile", "librosa", "tiktoken", "accelerate"),
    ),
)


def _pack_from_lock_entry(entry: LockEntry) -> CustomNodePack | None:
    if not entry.class_set:
        return None
    repo = entry.url or entry.path
    if not repo:
        return None
    return CustomNodePack(
        name=entry.name,
        repo=repo,
        classes=frozenset(entry.class_set),
        pip_packages=tuple(entry.pip_packages),
        class_schema_sha256=entry.class_schema_sha256 or entry.schema_hash,
    )


def _rich_lock_packs(lockfile_path: Path = Path("custom_nodes.lock")) -> tuple[CustomNodePack, ...]:
    try:
        entries = read_lockfile(lockfile_path)
    except (OSError, ValueError):
        return ()
    return tuple(pack for entry in entries if (pack := _pack_from_lock_entry(entry)) is not None)


def _known_node_packs(lockfile_path: Path = Path("custom_nodes.lock")) -> tuple[CustomNodePack, ...]:
    by_name = {pack.name: pack for pack in _STATIC_NODE_PACKS}
    for pack in _rich_lock_packs(lockfile_path):
        by_name[pack.name] = pack
    return tuple(sorted(by_name.values(), key=lambda pack: pack.name.lower()))


KNOWN_NODE_PACKS: tuple[CustomNodePack, ...] = _known_node_packs()


def resolve_node_packs(class_types: set[str]) -> list[CustomNodePack]:
    packs = [pack for pack in _known_node_packs() if class_types & pack.classes]
    return sorted(packs, key=lambda pack: pack.name.lower())


def unresolved_class_types(class_types: set[str]) -> list[str]:
    packs = _known_node_packs()
    covered = set().union(*(pack.classes for pack in packs)) if packs else set()
    return sorted(class_types - covered)
