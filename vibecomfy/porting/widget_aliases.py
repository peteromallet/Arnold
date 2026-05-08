from __future__ import annotations

from typing import Any

from vibecomfy.porting.widget_schema import WIDGET_SCHEMA


COMPILE_WIDGET_ALIAS_CLASS_TYPES: frozenset[str] = frozenset(
    {
        "LoadWanVideoT5TextEncoder",
        "WanVideoTextEncode",
        "WanVideoTextEncodeCached",
        "WanVideoModelLoader",
        "WanVideoBlockSwap",
        "WanVideoTorchCompileSettings",
        "WanVideoLoraSelect",
        "WanVideoLoraSelectMulti",
        "WanVideoImageToVideoEncode",
        "WanVideoVAELoader",
        "WanVideoDecode",
        "WanVideoSampler",
        "CreateCFGScheduleFloatList",
        "WanVideoAnimateEmbeds",
        "ImageResizeKJv2",
        "INTConstant",
        "FloatConstant",
        "ImageConcatMulti",
        "BlockifyMask",
        "DrawMaskOnImage",
        "GrowMaskWithBlur",
    }
)


LINK_ONLY_TYPES: frozenset[str] = frozenset(
    {
        "AUDIO",
        "CLIP",
        "CONDITIONING",
        "CONTROL_NET",
        "IMAGE",
        "LATENT",
        "MASK",
        "MODEL",
        "SIGMAS",
        "VAE",
    }
)


def resolve_widget_name(class_type: str, idx: int) -> str | None:
    names = WIDGET_SCHEMA.get(class_type)
    if names is not None and 0 <= idx < len(names):
        return names[idx]
    return f"widget_{idx}"


def widget_names_for_class(class_type: str) -> list[str | None] | None:
    names = WIDGET_SCHEMA.get(class_type)
    return list(names) if names is not None else None


def apply_positional_widget_aliases(inputs: dict[str, Any], class_type: str) -> None:
    if class_type not in COMPILE_WIDGET_ALIAS_CLASS_TYPES:
        return
    names = widget_names_for_class(class_type)
    if not names:
        return
    for index, name in enumerate(names):
        if name is None:
            continue
        widget_key = f"widget_{index}"
        if name not in inputs and widget_key in inputs:
            inputs[name] = inputs[widget_key]


def resolve_widget_key(class_type: str, key: str) -> str | None:
    if not key.startswith("widget_"):
        return key
    try:
        idx = int(key.split("_", 1)[1])
    except ValueError:
        return key
    return resolve_widget_name(class_type, idx)


def widget_names_from_schema(class_type: str, schema: Any | None) -> list[str | None]:
    committed = widget_names_for_class(class_type)
    if committed is not None:
        return committed
    inputs = getattr(schema, "inputs", None)
    if not isinstance(inputs, dict):
        return []
    names: list[str | None] = []
    for name, spec in inputs.items():
        input_type = str(getattr(spec, "type", "") or "").upper()
        if input_type in LINK_ONLY_TYPES:
            continue
        names.append(str(name))
    return names


def unresolved_widget_aliases(api_prompt: dict[str, Any] | None) -> list[dict[str, Any]]:
    unresolved: list[dict[str, Any]] = []
    if api_prompt is None:
        return unresolved
    for node_id, node in sorted(api_prompt.items(), key=lambda item: _sort_key(item[0])):
        if not isinstance(node, dict):
            continue
        inputs = node.get("inputs", {})
        if not isinstance(inputs, dict):
            continue
        class_type = str(node.get("class_type", ""))
        for input_name in sorted(inputs):
            if not input_name.startswith("widget_"):
                continue
            resolved = resolve_widget_key(class_type, input_name)
            if resolved is None or resolved != input_name:
                continue
            unresolved.append({"node_id": str(node_id), "class_type": class_type, "input": input_name})
    return unresolved


def _sort_key(value: Any) -> tuple[int, str]:
    try:
        return (int(value), str(value))
    except (TypeError, ValueError):
        return (10**12, str(value))


__all__ = [
    "COMPILE_WIDGET_ALIAS_CLASS_TYPES",
    "LINK_ONLY_TYPES",
    "apply_positional_widget_aliases",
    "resolve_widget_key",
    "resolve_widget_name",
    "unresolved_widget_aliases",
    "widget_names_for_class",
    "widget_names_from_schema",
]
