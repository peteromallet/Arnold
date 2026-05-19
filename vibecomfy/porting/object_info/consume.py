"""Lazy consumer for the structured object_info cache.

Reads per-pack JSON files and ``index.json`` on first access.
All public functions are deterministic and do not require ComfyUI or network.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

CACHE_DIR: Path = Path(__file__).resolve().parent.parent / "cache" / "object_info"
INDEX_PATH: Path = CACHE_DIR / "index.json"

# ComfyUI types that are link-only sockets — NOT widget controls.
# These are excluded from object_info_widget_order.
_WIDGET_LIKE_TYPES: frozenset[str] = frozenset({
    "MODEL", "CLIP", "VAE", "IMAGE", "LATENT", "CONDITIONING", "MASK",
    "AUDIO", "VIDEO", "hidden",
})

_CURATED_WIDGET_ORDERS: dict[str, list[str | None]] = {
    # The checked-in object_info cache does not include LTX2_NAG in all
    # environments. Curate only the missing fallback slot; WIDGET_SCHEMA owns
    # the first three widget names and asks object_info for index 3.
    "LTX2_NAG": ["nag_scale", "nag_alpha", "nag_tau", "inplace"],
}

_CURATED_OUTPUTS: dict[str, list[dict[str, str]]] = {
    # Core classes used by checked-in tests and v2.3 generated templates. These
    # labels are stable ComfyUI socket names and keep named handles available
    # when the large generated object_info cache is not committed.
    "CLIPTextEncode": [{"name": "CONDITIONING", "type": "CONDITIONING"}],
    "CLIPLoader": [{"name": "CLIP", "type": "CLIP"}],
    "CLIPVisionEncode": [{"name": "CLIP_VISION_OUTPUT", "type": "CLIP_VISION_OUTPUT"}],
    "CLIPVisionLoader": [{"name": "CLIP_VISION", "type": "CLIP_VISION"}],
    "CFGGuider": [{"name": "GUIDER", "type": "GUIDER"}],
    "CFGNorm": [{"name": "patched_model", "type": "MODEL"}],
    "ComfySwitchNode": [{"name": "output", "type": "*"}],
    "ConditioningZeroOut": [{"name": "CONDITIONING", "type": "CONDITIONING"}],
    "CreateVideo": [{"name": "VIDEO", "type": "VIDEO"}],
    "DepthAnything_V2": [{"name": "image", "type": "IMAGE"}],
    "DownloadAndLoadDepthAnythingV2Model": [{"name": "da_v2_model", "type": "MODEL"}],
    "DualCLIPLoader": [{"name": "CLIP", "type": "CLIP"}],
    "EmptyAceStep1.5LatentAudio": [{"name": "LATENT", "type": "LATENT"}],
    "EmptyLTXVLatentVideo": [{"name": "LATENT", "type": "LATENT"}],
    "EmptySD3LatentImage": [{"name": "LATENT", "type": "LATENT"}],
    "GetVideoComponents": [{"name": "images", "type": "IMAGE"}],
    "ImageResizeKJv2": [{"name": "IMAGE", "type": "IMAGE"}],
    "ImageScaleToTotalPixels": [{"name": "IMAGE", "type": "IMAGE"}],
    "INTConstant": [{"name": "value", "type": "INT"}],
    "KSampler": [{"name": "LATENT", "type": "LATENT"}],
    "KSamplerSelect": [{"name": "SAMPLER", "type": "SAMPLER"}],
    "LoadImage": [{"name": "IMAGE", "type": "IMAGE"}],
    "LoadVideo": [{"name": "VIDEO", "type": "VIDEO"}],
    "LoraLoaderModelOnly": [{"name": "MODEL", "type": "MODEL"}],
    "ManualSigmas": [{"name": "SIGMAS", "type": "SIGMAS"}],
    "ModelSamplingAuraFlow": [{"name": "MODEL", "type": "MODEL"}],
    "ModelSamplingSD3": [{"name": "MODEL", "type": "MODEL"}],
    "PathchSageAttentionKJ": [{"name": "MODEL", "type": "MODEL"}],
    "PrimitiveBoolean": [{"name": "BOOLEAN", "type": "BOOLEAN"}],
    "PrimitiveFloat": [{"name": "FLOAT", "type": "FLOAT"}],
    "PrimitiveInt": [{"name": "INT", "type": "INT"}],
    "RandomNoise": [{"name": "NOISE", "type": "NOISE"}],
    "SamplerCustomAdvanced": [{"name": "output", "type": "LATENT"}],
    "TextEncodeAceStepAudio1.5": [{"name": "CONDITIONING", "type": "CONDITIONING"}],
    "TextEncodeQwenImageEdit": [{"name": "CONDITIONING", "type": "CONDITIONING"}],
    "UNETLoader": [{"name": "MODEL", "type": "MODEL"}],
    "VAEDecode": [{"name": "IMAGE", "type": "IMAGE"}],
    "VAEDecodeAudio": [{"name": "AUDIO", "type": "AUDIO"}],
    "VAEDecodeTiled": [{"name": "IMAGE", "type": "IMAGE"}],
    "VAEEncode": [{"name": "LATENT", "type": "LATENT"}],
    "VAELoader": [{"name": "VAE", "type": "VAE"}],
    "WanImageToVideo": [
        {"name": "positive", "type": "CONDITIONING"},
        {"name": "negative", "type": "CONDITIONING"},
        {"name": "latent", "type": "LATENT"},
    ],
    "LTX2AttentionTunerPatch": [{"name": "model", "type": "MODEL"}],
    "LTX2_NAG": [{"name": "model", "type": "MODEL"}],
    "LTXAddVideoICLoRAGuide": [
        {"name": "positive", "type": "CONDITIONING"},
        {"name": "negative", "type": "CONDITIONING"},
        {"name": "latent", "type": "LATENT"},
    ],
    "LTXFloatToInt": [{"name": "INT", "type": "INT"}],
    "LTXICLoRALoaderModelOnly": [
        {"name": "model", "type": "MODEL"},
        {"name": "latent_downscale_factor", "type": "FLOAT"},
    ],
    "LTXVAudioVAELoader": [{"name": "Audio VAE", "type": "VAE"}],
    "LTXVChunkFeedForward": [{"name": "model", "type": "MODEL"}],
    "LTXVConcatAVLatent": [{"name": "latent", "type": "LATENT"}],
    "LTXVConditioning": [
        {"name": "positive", "type": "CONDITIONING"},
        {"name": "negative", "type": "CONDITIONING"},
    ],
    "LTXVCropGuides": [{"name": "latent", "type": "LATENT"}],
    "LTXVEmptyLatentAudio": [{"name": "Latent", "type": "LATENT"}],
    "LTXVImgToVideoInplaceKJ": [{"name": "latent", "type": "LATENT"}],
    "LTXVPreprocess": [{"name": "output_image", "type": "IMAGE"}],
    "LTXVSeparateAVLatent": [
        {"name": "video_latent", "type": "LATENT"},
        {"name": "audio_latent", "type": "LATENT"},
    ],
    # controlnet_aux classes used by the v2.3 pilot. These packs were absent
    # from the local object_info cache during the audit, but their single image
    # output is stable and needed by both codemod readability and Handle.out().
    "CannyEdgePreprocessor": [{"name": "IMAGE", "type": "IMAGE"}],
    "DWPreprocessor": [{"name": "IMAGE", "type": "IMAGE"}],
}

# ---------------------------------------------------------------------------
# Internal lazy state
# ---------------------------------------------------------------------------

_index: dict[str, str] | None = None
_pack_cache: dict[str, dict[str, dict[str, Any]]] = {}


def _normalize_output_name(name: str) -> str:
    cleaned = name.strip().replace(" ", "_")
    return cleaned.upper()


def _load_index() -> dict[str, str]:
    global _index
    if _index is None:
        if INDEX_PATH.is_file():
            with open(INDEX_PATH, "r", encoding="utf-8") as fh:
                _index = json.load(fh)
        else:
            _index = {}
    return _index


def _load_pack(filename: str) -> dict[str, dict[str, Any]]:
    if filename not in _pack_cache:
        filepath = CACHE_DIR / filename
        if filepath.is_file():
            with open(filepath, "r", encoding="utf-8") as fh:
                _pack_cache[filename] = json.load(fh)
        else:
            _pack_cache[filename] = {}
    return _pack_cache[filename]


def _resolve_class_type(class_type: str) -> dict[str, Any] | None:
    idx = _load_index()
    filename = idx.get(class_type)
    if filename is None:
        return None
    pack = _load_pack(filename)
    return pack.get(class_type)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_class(class_type: str) -> dict[str, Any] | None:
    """Return the normalized cache entry for *class_type*, or ``None``.

    The returned dict has keys:
    ``pack``, ``pack_version``, ``python_module``, ``category``, ``name``,
    ``display_name``, ``description``, ``inputs``, ``input_order``,
    ``input_order_all``, ``object_info_widget_order``, ``outputs``, ``function``.
    """
    entry = _resolve_class_type(class_type)
    if entry is not None:
        return entry
    curated_outputs = _CURATED_OUTPUTS.get(class_type)
    if curated_outputs is None:
        return None
    return {"outputs": curated_outputs}


def object_info_widget_order(class_type: str) -> list[str | None]:
    """Return the ordered widget names (excluding link-only sockets) for *class_type*.

    Returns an empty list when the class is not found in the cache.
    This is a raw object_info fallback — callers should prefer the curated
    ``WIDGET_SCHEMA`` table and only use this when no curated entry exists.
    """
    entry = _resolve_class_type(class_type)
    if entry is None:
        return list(_CURATED_WIDGET_ORDERS.get(class_type, []))
    return list(entry.get("object_info_widget_order", []))


def effective_widget_names_for_class(class_type: str, *, allow_object_info_fallback: bool = False) -> list[str | None]:
    """Return curated widget names, optionally falling back to cached object_info."""
    from vibecomfy.porting.widget_schema import WIDGET_SCHEMA

    curated = WIDGET_SCHEMA.get(class_type)
    if curated is not None:
        return list(curated)
    if allow_object_info_fallback:
        return object_info_widget_order(class_type)
    return []


def output_names(class_type: str) -> list[str]:
    """Return ordered output names for *class_type* (e.g. ``["MODEL"]``).

    Returns an empty list when the class is not found in the cache.
    """
    entry = _resolve_class_type(class_type)
    if entry is None:
        return [o["name"] for o in _CURATED_OUTPUTS.get(class_type, [])]
    names = [o.get("name", "") for o in entry.get("outputs", [])]
    return names or [o["name"] for o in _CURATED_OUTPUTS.get(class_type, [])]


def output_types(class_type: str) -> list[str]:
    """Return ordered output types for *class_type* (e.g. ``["MODEL"]``).

    Returns an empty list when the class is not found in the cache.
    """
    entry = _resolve_class_type(class_type)
    if entry is None:
        return [o["type"] for o in _CURATED_OUTPUTS.get(class_type, [])]
    types = [o.get("type", "") for o in entry.get("outputs", [])]
    return types or [o["type"] for o in _CURATED_OUTPUTS.get(class_type, [])]


def list_classes() -> list[str]:
    """Return all class types in the cache, sorted deterministically."""
    idx = _load_index()
    if idx:
        return sorted(idx.keys())
    return sorted(_CURATED_OUTPUTS)


def cache_stats() -> dict[str, Any]:
    """Return summary stats about the loaded cache (for debugging)."""
    idx = _load_index()
    return {
        "total_classes": len(idx),
        "packs_cached": len(_pack_cache),
        "cache_dir": str(CACHE_DIR),
    }
