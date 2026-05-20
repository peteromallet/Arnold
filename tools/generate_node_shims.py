from __future__ import annotations

import json
import keyword
import re
from pathlib import Path
from typing import Any

from vibecomfy.porting.object_info import CACHE_DIR, get_class


ROOT = Path(__file__).resolve().parents[1]
INVENTORY_PATH = ROOT / "vibecomfy" / "porting" / "cache" / "class_inventory.json"
GENERATED_DIR = ROOT / "vibecomfy" / "nodes" / "_generated"
NODES_DIR = ROOT / "vibecomfy" / "nodes"

HELPER_CLASSES = {
    "GetNode",
    "MarkdownNote",
    "Note",
    "PrimitiveNode",
    "Reroute",
    "SetNode",
}
RESERVED_INPUT_NAMES = {"class", "from", "type"}
CURATED_DEFAULTS: dict[str, dict[str, Any]] = {
    "UNETLoader": {"weight_dtype": "default"},
    "CLIPLoader": {"device": "default"},
    "KSampler": {"scheduler": "simple", "denoise": 1},
    "KSamplerAdvanced": {"scheduler": "simple"},
    "EmptyLatentImage": {"batch_size": 1},
    "EmptySD3LatentImage": {"batch_size": 1},
    "EmptyFlux2LatentImage": {"batch_size": 1},
    "ImageScale": {"crop": "none"},
    "ImageResizeKJv2": {"crop": "none"},
    "VHS_VideoCombine": {"format": "auto", "codec": "auto"},
    "SaveVideo": {"format": "auto", "codec": "auto"},
    "WanVideoSampler": {"shift": 8},
}

PACK_MODULES = {
    "AILab_QwenTTS": "qwentts",
    "AILab_QwenTTS_Tools": "qwentts",
    "ComfyUI-DepthAnythingV2": "depthanythingv2",
    "ComfyUI-GGUF": "gguf",
    "ComfyUI-KJNodes": "kjnodes",
    "ComfyUI-LTXVideo": "ltxvideo",
    "ComfyUI-Qwen3-TTS": "qwen3tts",
    "ComfyUI-VideoHelperSuite": "videohelpersuite",
    "ComfyUI-WanAnimatePreprocess": "wananimatepreprocess",
    "ComfyUI-WanVideoWrapper": "wanvideowrapper",
    "ComfyUI-segment-anything-2": "sam2",
    "comfy": "core",
    "comfy_core": "core",
    "comfy_extras": "core",
    "rgthree-comfy": "rgthree",
}

PACK_FILE_MODULES = {
    "AILab_QwenTTS@runpod-snapshot.json": "qwentts",
    "AILab_QwenTTS_Tools@runpod-snapshot.json": "qwentts",
    "ComfyUI-DepthAnythingV2@local-5531878.json": "depthanythingv2",
    "ComfyUI-GGUF@local-6ea2651.json": "gguf",
    "ComfyUI-KJNodes@runpod-snapshot.json": "kjnodes",
    "ComfyUI-LTXVideo@runpod-snapshot.json": "ltxvideo",
    "ComfyUI-Qwen3-TTS@local-17c22ad.json": "qwen3tts",
    "ComfyUI-VideoHelperSuite@runpod-snapshot.json": "videohelpersuite",
    "ComfyUI-WanAnimatePreprocess@local-1a35b81.json": "wananimatepreprocess",
    "ComfyUI-WanVideoWrapper@runpod-snapshot.json": "wanvideowrapper",
    "ComfyUI-segment-anything-2@local-0c35fff.json": "sam2",
    "comfy@runpod-snapshot.json": "core",
    "comfy_core@runpod-snapshot.json": "core",
    "comfy_extras@runpod-snapshot.json": "core",
    "rgthree-comfy@runpod-snapshot.json": "rgthree",
}

FORCED_WHOLE_PACK_MODULES = {
    "depthanythingv2",
    "gguf",
    "qwentts",
    "qwen3tts",
    "rgthree",
    "sam2",
    "videohelpersuite",
    "wananimatepreprocess",
}
TARGET_MODULES = (
    "core",
    "kjnodes",
    "ltxvideo",
    "videohelpersuite",
    "controlnet_aux",
    "depthanythingv2",
    "wanvideowrapper",
    "qwentts",
    "qwen3tts",
    "gguf",
    "rgthree",
    "sam2",
    "wananimatepreprocess",
)


def main() -> None:
    GENERATED_DIR.mkdir(parents=True, exist_ok=True)
    classes_by_module = _select_classes()
    all_exports: dict[str, list[str]] = {}
    for module in TARGET_MODULES:
        exports = _write_module(module, sorted(classes_by_module.get(module, set())))
        all_exports[module] = exports
        _write_reexport_module(module)
    _write_generated_init()
    _write_nodes_init(all_exports)
    print(f"generated {sum(len(v) for v in all_exports.values())} wrappers across {len(TARGET_MODULES)} modules")


def _select_classes() -> dict[str, set[str]]:
    selected: dict[str, set[str]] = {module: set() for module in TARGET_MODULES}
    if INVENTORY_PATH.is_file():
        inventory = json.loads(INVENTORY_PATH.read_text(encoding="utf-8"))
        fallback = set(inventory.get("fallback_helpers", {})) | HELPER_CLASSES
        for class_type, info in inventory.get("typed_wrappers", {}).items():
            if class_type in fallback or _skip_class_type(class_type):
                continue
            entry = get_class(class_type)
            if entry is None:
                continue
            module = PACK_MODULES.get(str(entry.get("pack") or ""))
            if module is None:
                module = "core" if bool(info.get("is_core")) else None
            if module in selected:
                selected[module].add(class_type)

    for filename, module in PACK_FILE_MODULES.items():
        if module not in FORCED_WHOLE_PACK_MODULES:
            continue
        path = CACHE_DIR / filename
        if not path.is_file():
            continue
        pack = json.loads(path.read_text(encoding="utf-8"))
        for class_type, entry in pack.items():
            if _is_wrappable(class_type, entry):
                selected[module].add(class_type)
    return selected


def _write_module(module: str, class_types: list[str]) -> list[str]:
    export_names: list[str] = []
    used_names: set[str] = set()
    lines = [
        '"""Auto-generated thin wrappers for ComfyUI node classes.',
        "",
        "Regenerate via: python -m tools.generate_node_shims",
        '"""',
        "from __future__ import annotations",
        "",
        "from typing import Any",
        "",
        "from vibecomfy.templates import node",
        "from vibecomfy.workflow import VibeWorkflow",
        "",
        "_UNSET = object()",
        "",
    ]
    for class_type in class_types:
        entry = get_class(class_type)
        if entry is None or not _is_wrappable(class_type, entry):
            continue
        function_name = _unique_name(_identifier(class_type), used_names)
        used_names.add(function_name)
        export_names.append(function_name)
        lines.extend(_render_wrapper(function_name, class_type, entry))
        lines.append("")
    lines.append(f"__all__ = {export_names!r}")
    lines.append("")
    (GENERATED_DIR / f"{module}.py").write_text("\n".join(lines), encoding="utf-8")
    return export_names


def _render_wrapper(function_name: str, class_type: str, entry: dict[str, Any]) -> list[str]:
    inputs = _input_specs(class_type, entry)
    params = _ordered_params(inputs)
    pack = str(entry.get("pack") or "core")
    returns = ", ".join(_output_names(entry)) or "None"
    description = str(entry.get("description") or entry.get("display_name") or "").strip()

    lines = [f"def {function_name}(", "    wf: VibeWorkflow,", "    *,"]
    for param in params:
        default = param["default"]
        default_text = "" if default is _NO_DEFAULT else f" = {_default_repr(default)}"
        lines.append(f"    {param['name']}: Any{default_text},")
    lines.append("    pass_raw: bool = False,")
    lines.append("    **_extras: Any,")
    lines.append("):")
    doc = ['    """']
    if description:
        doc.extend(f"    {line}" if line else "    " for line in description.splitlines())
        doc.append("    ")
    doc.append(f"    Pack: {pack}")
    doc.append(f"    Returns: {returns}")
    doc.append('    """')
    lines.extend(doc)
    lines.append("    _kwargs: dict[str, Any] = {}")
    for param in params:
        original = param["original"]
        name = param["name"]
        default = param["default"]
        if default is _UNSET_DEFAULT:
            lines.append(f"    if {name} is not _UNSET:")
            lines.append(f"        _kwargs[{original!r}] = {name}")
        else:
            lines.append(f"    _kwargs[{original!r}] = {name}")
    lines.append("    _kwargs.update(_extras)")
    lines.append(f"    return node(wf, {class_type!r}, pass_raw=pass_raw, **_kwargs)")
    return lines


_NO_DEFAULT = object()
_UNSET_DEFAULT = object()


def _ordered_params(inputs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    required = [item for item in inputs if item["default"] is _NO_DEFAULT]
    defaulted = [item for item in inputs if item["default"] is not _NO_DEFAULT]
    return required + defaulted


def _input_specs(class_type: str, entry: dict[str, Any]) -> list[dict[str, Any]]:
    inputs = entry.get("inputs")
    if not isinstance(inputs, dict):
        return []
    order = entry.get("input_order_all")
    ordered_names = [str(name) for name in order] if isinstance(order, list) else []
    specs: dict[str, list[Any]] = {}
    optional_names: set[str] = set()
    for section in ("required", "optional"):
        section_inputs = inputs.get(section)
        if not isinstance(section_inputs, dict):
            continue
        for name, spec in section_inputs.items():
            if isinstance(spec, list):
                specs[str(name)] = spec
            elif isinstance(spec, str):
                specs[str(name)] = [spec]
            if section == "optional":
                optional_names.add(str(name))
    names = ordered_names or sorted(specs)
    used_param_names: set[str] = set()
    params: list[dict[str, Any]] = []
    for original in names:
        spec = specs.get(original)
        if spec is None:
            continue
        param_name = _unique_name(_identifier(original), used_param_names)
        used_param_names.add(param_name)
        metadata = spec[1] if len(spec) > 1 and isinstance(spec[1], dict) else {}
        if "default" in metadata:
            default: Any = metadata["default"]
        elif original in CURATED_DEFAULTS.get(class_type, {}):
            default = CURATED_DEFAULTS[class_type][original]
        elif original in optional_names:
            default = _UNSET_DEFAULT
        else:
            default = _NO_DEFAULT
        params.append({"original": original, "name": param_name, "default": default})
    return params


def _default_repr(value: Any) -> str:
    if value is _UNSET_DEFAULT:
        return "_UNSET"
    return repr(value)


def _output_names(entry: dict[str, Any]) -> list[str]:
    outputs = entry.get("outputs")
    if not isinstance(outputs, list):
        return []
    return [str(item.get("name") or item.get("type") or "") for item in outputs if isinstance(item, dict)]


def _is_wrappable(class_type: str, entry: dict[str, Any]) -> bool:
    if _skip_class_type(class_type):
        return False
    inputs = entry.get("inputs")
    return isinstance(inputs, dict) and any(key in inputs for key in ("required", "optional"))


def _skip_class_type(class_type: str) -> bool:
    return class_type in HELPER_CLASSES or not _identifier(class_type)


def _identifier(value: str) -> str:
    cleaned = re.sub(r"\W+", "_", value).strip("_")
    if not cleaned:
        return ""
    if cleaned[0].isdigit():
        cleaned = f"_{cleaned}"
    if keyword.iskeyword(cleaned) or cleaned in RESERVED_INPUT_NAMES:
        cleaned = f"{cleaned}_"
    return cleaned


def _unique_name(value: str, used: set[str]) -> str:
    candidate = value
    index = 2
    while candidate in used:
        candidate = f"{value}_{index}"
        index += 1
    return candidate


def _write_reexport_module(module: str) -> None:
    (NODES_DIR / f"{module}.py").write_text(
        "\n".join([
            f"from vibecomfy.nodes._generated import {module} as _generated",
            f"from vibecomfy.nodes._generated.{module} import *",
            "",
            "__all__ = list(_generated.__all__)",
            "",
        ]),
        encoding="utf-8",
    )


def _write_generated_init() -> None:
    (GENERATED_DIR / "__init__.py").write_text('__all__: list[str] = []\n', encoding="utf-8")


def _write_nodes_init(all_exports: dict[str, list[str]]) -> None:
    lines = ["from __future__ import annotations", ""]
    for module in TARGET_MODULES:
        lines.append(f"from vibecomfy.nodes.{module} import *")
    exported = sorted({name for names in all_exports.values() for name in names})
    lines.append("")
    lines.append(f"__all__ = {exported!r}")
    lines.append("")
    (NODES_DIR / "__init__.py").write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    main()
