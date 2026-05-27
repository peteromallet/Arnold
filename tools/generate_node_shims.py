from __future__ import annotations

import json
import keyword
import re
from pathlib import Path
from typing import Any

from vibecomfy.porting.object_info import CACHE_DIR, get_class


# TODO(repo-root): migrate to vibecomfy.utils.find_repo_root() once this tool's
# script-mode import path is package-import-safe.
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

CURATED_WRAPPER_SCHEMAS: dict[str, dict[str, Any]] = {
    "DownloadAndLoadSAM2Model": {
        "pack": "ComfyUI-segment-anything-2",
        "display_name": "DownloadAndLoadSAM2Model",
        "inputs": {"optional": {name: ["ANY"] for name in ("model", "segmentor", "device", "precision")}},
        "input_order_all": ["model", "segmentor", "device", "precision"],
        "outputs": [{"name": "sam2_model", "type": "SAM2_MODEL"}],
    },
    "Florence2toCoordinates": {
        "pack": "ComfyUI-segment-anything-2",
        "display_name": "Florence2toCoordinates",
        "inputs": {"optional": {name: ["ANY"] for name in ("data", "index", "batch")}},
        "input_order_all": ["data", "index", "batch"],
        "outputs": [{"name": "center_coordinates", "type": "COORDINATES"}, {"name": "bboxes", "type": "BBOXES"}],
    },
    "Sam2AutoSegmentation": {
        "pack": "ComfyUI-segment-anything-2",
        "display_name": "Sam2AutoSegmentation",
        "inputs": {
            "optional": {
                name: ["ANY"]
                for name in (
                    "sam2_model",
                    "image",
                    "points_per_side",
                    "points_per_batch",
                    "pred_iou_thresh",
                    "stability_score_thresh",
                    "stability_score_offset",
                    "mask_threshold",
                    "crop_n_layers",
                    "box_nms_thresh",
                    "crop_nms_thresh",
                    "crop_overlap_ratio",
                    "crop_n_points_downscale_factor",
                    "min_mask_region_area",
                    "use_m2m",
                    "keep_model_loaded",
                )
            }
        },
        "input_order_all": [
            "sam2_model",
            "image",
            "points_per_side",
            "points_per_batch",
            "pred_iou_thresh",
            "stability_score_thresh",
            "stability_score_offset",
            "mask_threshold",
            "crop_n_layers",
            "box_nms_thresh",
            "crop_nms_thresh",
            "crop_overlap_ratio",
            "crop_n_points_downscale_factor",
            "min_mask_region_area",
            "use_m2m",
            "keep_model_loaded",
        ],
        "outputs": [
            {"name": "mask", "type": "MASK"},
            {"name": "segmented_image", "type": "IMAGE"},
            {"name": "bbox", "type": "BBOX"},
        ],
    },
    "Sam2Segmentation": {
        "pack": "ComfyUI-segment-anything-2",
        "display_name": "Sam2Segmentation",
        "inputs": {
            "optional": {
                name: ["ANY"]
                for name in (
                    "sam2_model",
                    "image",
                    "keep_model_loaded",
                    "coordinates_positive",
                    "coordinates_negative",
                    "bboxes",
                    "individual_objects",
                    "mask",
                )
            }
        },
        "input_order_all": [
            "sam2_model",
            "image",
            "keep_model_loaded",
            "coordinates_positive",
            "coordinates_negative",
            "bboxes",
            "individual_objects",
            "mask",
        ],
        "outputs": [{"name": "mask", "type": "MASK"}],
    },
    "Sam2VideoSegmentation": {
        "pack": "ComfyUI-segment-anything-2",
        "display_name": "Sam2VideoSegmentation",
        "inputs": {"optional": {name: ["ANY"] for name in ("sam2_model", "inference_state", "keep_model_loaded")}},
        "input_order_all": ["sam2_model", "inference_state", "keep_model_loaded"],
        "outputs": [{"name": "mask", "type": "MASK"}],
    },
    "Sam2VideoSegmentationAddPoints": {
        "pack": "ComfyUI-segment-anything-2",
        "display_name": "Sam2VideoSegmentationAddPoints",
        "inputs": {
            "optional": {
                name: ["ANY"]
                for name in (
                    "sam2_model",
                    "coordinates_positive",
                    "frame_index",
                    "object_index",
                    "image",
                    "coordinates_negative",
                    "prev_inference_state",
                )
            }
        },
        "input_order_all": [
            "sam2_model",
            "coordinates_positive",
            "frame_index",
            "object_index",
            "image",
            "coordinates_negative",
            "prev_inference_state",
        ],
        "outputs": [{"name": "sam2_model", "type": "SAM2_MODEL"}, {"name": "inference_state", "type": "INFERENCE_STATE"}],
    },
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

_LOCAL_SCHEMA_ENTRIES: dict[str, dict[str, Any]] = {}


def main() -> None:
    GENERATED_DIR.mkdir(parents=True, exist_ok=True)
    classes_by_module = _select_classes()
    all_exports: dict[str, list[str]] = {}
    for module in TARGET_MODULES:
        exports = _write_module(module, sorted(classes_by_module.get(module, set())))
        _write_stub_module(module, sorted(classes_by_module.get(module, set())))
        all_exports[module] = exports
        _write_reexport_module(module)
        _write_reexport_stub_module(module)
    _write_generated_init()
    _write_generated_init_stub()
    _write_nodes_init(all_exports)
    _write_nodes_init_stub(all_exports)
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
                _LOCAL_SCHEMA_ENTRIES[class_type] = entry
                selected[module].add(class_type)
    for class_type, entry in CURATED_WRAPPER_SCHEMAS.items():
        module = PACK_MODULES.get(str(entry.get("pack") or ""))
        if module in selected:
            _LOCAL_SCHEMA_ENTRIES[class_type] = entry
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
        "from typing import Any, Literal",
        "",
        "from vibecomfy.templates import _current_workflow_or_raise, node",
        "from vibecomfy.workflow import VibeWorkflow",
        "",
        "class _Omitted:",
        "    pass",
        "",
        "_UNSET = _Omitted()",
        "",
    ]
    for class_type in class_types:
        entry = _schema_entry(class_type)
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


def _schema_entry(class_type: str) -> dict[str, Any] | None:
    return _LOCAL_SCHEMA_ENTRIES.get(class_type) or get_class(class_type)


def _render_wrapper(function_name: str, class_type: str, entry: dict[str, Any]) -> list[str]:
    inputs = _input_specs(class_type, entry)
    params = _ordered_params(inputs)
    pack = str(entry.get("pack") or "core")
    returns = ", ".join(_output_names(entry)) or "None"
    description = str(entry.get("description") or entry.get("display_name") or "").strip()

    lines = [f"def {function_name}(", "    *args: VibeWorkflow,"]
    lines.append("    _id: str | None = None,")
    for param in params:
        default = param["default"]
        default_text = "" if default is _NO_DEFAULT else f" = {_default_repr(default)}"
        annotation = _annotation_for_param(param)
        lines.append(f"    {param['name']}: {annotation}{default_text},")
    lines.append("    pass_raw: bool = False,")
    lines.append("    **_extras: Any,")
    lines.append("):")
    doc = ['    """']
    if description:
        doc.extend(f"    {line}" if line else "    " for line in description.splitlines())
        doc.append("    ")
    doc.append(f"    Pack: {pack}")
    doc.append(f"    Returns: {returns}")
    doc.append("    ")
    doc.append("    Use inside a `with new_workflow(...) as wf:` block, or pass wf explicitly.")
    doc.append('    """')
    lines.extend(doc)
    lines.append("    if len(args) > 1:")
    lines.append(f"        raise TypeError(f\"{function_name}() takes at most 1 positional argument, got {{len(args)}}\")")
    lines.append("    wf = args[0] if args else _current_workflow_or_raise()")
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
    lines.append(f"    return node(wf, {class_type!r}, _id, pass_raw=pass_raw, **_kwargs)")
    return lines


def _write_stub_module(module: str, class_types: list[str]) -> list[str]:
    export_names: list[str] = []
    used_names: set[str] = set()
    lines = [
        '"""Type stubs for generated ComfyUI node wrappers."""',
        "from __future__ import annotations",
        "",
        "from typing import Any, Literal",
        "",
        "from vibecomfy.workflow import VibeWorkflow",
        "",
        "class _Omitted: ...",
        "_UNSET: _Omitted",
        "",
    ]
    for class_type in class_types:
        entry = _schema_entry(class_type)
        if entry is None or not _is_wrappable(class_type, entry):
            continue
        function_name = _unique_name(_identifier(class_type), used_names)
        used_names.add(function_name)
        export_names.append(function_name)
        lines.extend(_render_stub_wrapper(function_name, entry))
        lines.append("")
    lines.append(f"__all__: list[str]")
    lines.append("")
    (GENERATED_DIR / f"{module}.pyi").write_text("\n".join(lines), encoding="utf-8")
    return export_names


def _render_stub_wrapper(function_name: str, entry: dict[str, Any]) -> list[str]:
    params = _ordered_params(_input_specs(function_name, entry))
    lines = [f"def {function_name}(", "    *args: VibeWorkflow,"]
    lines.append("    _id: str | None = ...,")
    for param in params:
        annotation = _annotation_for_param(param)
        lines.append(f"    {param['name']}: {annotation} = ...,")
    lines.append("    pass_raw: bool = ...,")
    lines.append("    **_extras: Any,")
    lines.append(") -> Any: ...")
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
        # Keep wrappers thin: schema defaults are useful documentation, but
        # generated templates omit them for canonical parity. Omitted wrapper
        # kwargs must therefore stay omitted instead of being reintroduced by
        # the convenience layer.
        default = _UNSET_DEFAULT
        params.append({"original": original, "name": param_name, "default": default, "spec": spec})
    return params


def _default_repr(value: Any) -> str:
    if value is _UNSET_DEFAULT:
        return "_UNSET"
    return repr(value)


def _annotation_for_param(param: dict[str, Any]) -> str:
    spec = param.get("spec") or []
    schema_type = spec[0] if isinstance(spec, list) and spec else None
    base = _annotation_for_schema_type(schema_type)
    return f"{base} | _Omitted"


def _annotation_for_schema_type(schema_type: Any) -> str:
    if isinstance(schema_type, list) and 0 < len(schema_type) <= 64 and all(_literal_allowed(value) for value in schema_type):
        values = ", ".join(repr(value) for value in schema_type)
        return f"Literal[{values}]"
    if isinstance(schema_type, str):
        normalized = schema_type.upper()
        if normalized == "INT":
            return "int"
        if normalized == "FLOAT":
            return "float"
        if normalized in {"STRING", "TEXT"}:
            return "str"
        if normalized in {"BOOLEAN", "BOOL"}:
            return "bool"
    return "Any"


def _literal_allowed(value: Any) -> bool:
    return isinstance(value, (str, int, bool)) or value is None


def _output_names(entry: dict[str, Any]) -> list[str]:
    outputs = entry.get("outputs")
    if not isinstance(outputs, list):
        return []
    return [str(item.get("name") or item.get("type") or "") for item in outputs if isinstance(item, dict)]


def _is_wrappable(class_type: str, entry: dict[str, Any]) -> bool:
    if _skip_class_type(class_type):
        return False
    inputs = entry.get("inputs")
    return isinstance(inputs, dict) or bool(entry.get("outputs"))


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


def _write_reexport_stub_module(module: str) -> None:
    (NODES_DIR / f"{module}.pyi").write_text(
        "\n".join([
            f"from vibecomfy.nodes._generated.{module} import *",
            "",
            "__all__: list[str]",
            "",
        ]),
        encoding="utf-8",
    )


def _write_generated_init() -> None:
    (GENERATED_DIR / "__init__.py").write_text('__all__: list[str] = []\n', encoding="utf-8")


def _write_generated_init_stub() -> None:
    (GENERATED_DIR / "__init__.pyi").write_text("__all__: list[str]\n", encoding="utf-8")


def _write_nodes_init(all_exports: dict[str, list[str]]) -> None:
    lines = ["from __future__ import annotations", ""]
    for module in TARGET_MODULES:
        lines.append(f"from vibecomfy.nodes.{module} import *")
    exported = sorted({name for names in all_exports.values() for name in names})
    lines.append("")
    lines.append(f"__all__ = {exported!r}")
    lines.append("")
    (NODES_DIR / "__init__.py").write_text("\n".join(lines), encoding="utf-8")


def _write_nodes_init_stub(all_exports: dict[str, list[str]]) -> None:
    lines = ["from __future__ import annotations", ""]
    for module in TARGET_MODULES:
        lines.append(f"from vibecomfy.nodes.{module} import *")
    lines.append("")
    lines.append(f"__all__: list[str]")
    lines.append("")
    (NODES_DIR / "__init__.pyi").write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    main()
