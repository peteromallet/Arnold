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
        "CLIPVisionLoader",
        "CLIPTextEncode",
        "WanVideoClipVisionEncode",
        "ImageResizeKJv2",
        "INTConstant",
        "FloatConstant",
        "EmptyLTXVLatentVideo",
        "ImageConcatMulti",
        "BlockifyMask",
        "DrawMaskOnImage",
        "GrowMaskWithBlur",
        "DownloadAndLoadSAM2Model",
        "Sam2Segmentation",
        "GrowMask",
        "DWPreprocessor",
        "PointsEditor",
        "CLIPVisionEncode",
        "LoadVideo",
        "ImageScaleBy",
        "DualCLIPLoaderGGUF",
        "LTX2AttentionTunerPatch",
        "LTX2MemoryEfficientSageAttentionPatch",
        "LTX2_NAG",
        "LTX2SamplingPreviewOverride",
        "LTXAddVideoICLoRAGuide",
        "LTXICLoRALoaderModelOnly",
        "LTXVAddGuide",
        "LTXVChunkFeedForward",
        "LTXVConditioning",
        "LTXVEmptyLatentAudio",
        "LTXVImgToVideoConditionOnly",
        "LTXAVTextEncoderLoader",
        "LTXVPreprocess",
        "LTXVScheduler",
        "LTXVTiledVAEDecode",
        "LoadImage",
        "LatentUpscaleModelLoader",
        "ManualSigmas",
        "PathchSageAttentionKJ",
        "Power Lora Loader (rgthree)",
        "PixelPerfectResolution",
        "ResizeImageMaskNode",
        "ResizeImagesByLongerEdge",
        "SimpleCalculatorKJ",
        "OnnxDetectionModelLoader",
        "PoseAndFaceDetection",
        "DrawViTPose",
        "VAELoaderKJ",
        "UnetLoaderGGUF",
        "VHS_VideoCombine",
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
        widget_key = f"widget_{index}"
        if name is None:
            inputs.pop(widget_key, None)
            continue
        if name not in inputs and widget_key in inputs:
            inputs[name] = inputs[widget_key]
        if name != widget_key:
            inputs.pop(widget_key, None)


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


def widget_alias_analysis(
    api_prompt: dict[str, Any] | None,
    *,
    raw_workflow: dict[str, Any] | None = None,
    schema_provider: Any | None = None,
) -> dict[str, Any]:
    unresolved = unresolved_widget_aliases(api_prompt)
    return {
        "unresolved_widget_aliases": unresolved,
        "suggestions": _widget_alias_suggestions(
            api_prompt,
            unresolved,
            raw_workflow=raw_workflow,
            schema_provider=schema_provider,
        ),
    }


def _widget_alias_suggestions(
    api_prompt: dict[str, Any] | None,
    unresolved: list[dict[str, Any]],
    *,
    raw_workflow: dict[str, Any] | None,
    schema_provider: Any | None,
) -> list[dict[str, Any]]:
    if not unresolved:
        return []

    raw_ui_nodes = _raw_ui_nodes_by_id(raw_workflow)
    groups: dict[str, dict[str, Any]] = {}
    for alias in unresolved:
        class_type = str(alias["class_type"])
        node_id = str(alias["node_id"])
        node = api_prompt.get(node_id, {}) if isinstance(api_prompt, dict) else {}
        widget_values = _widget_values_for_node(node_id, node, raw_ui_nodes)
        observed_count = max(_widget_index(alias["input"]) + 1, len(widget_values))
        group = groups.setdefault(
            class_type,
            {
                "class_type": class_type,
                "nodes": {},
                "observed_widget_count": 0,
                "schema_source": "unavailable",
                "suggested_schema_entry": None,
            },
        )
        group["observed_widget_count"] = max(group["observed_widget_count"], observed_count)
        node_entry = group["nodes"].setdefault(
            node_id,
            {
                "node_id": node_id,
                "unresolved_inputs": [],
                "widgets_values": widget_values,
            },
        )
        node_entry["unresolved_inputs"].append(alias["input"])

    for class_type, group in groups.items():
        source, names = _schema_entry_for_class(class_type, schema_provider)
        group["schema_source"] = source
        if names is not None:
            suggested = list(names)
            if group["observed_widget_count"] > len(suggested):
                suggested.extend([None] * (group["observed_widget_count"] - len(suggested)))
            group["suggested_schema_entry"] = suggested
            group["python"] = _format_widget_schema_entry(class_type, suggested)
        group["nodes"] = [group["nodes"][node_id] for node_id in sorted(group["nodes"], key=_sort_key)]

    return [groups[class_type] for class_type in sorted(groups)]


def _schema_entry_for_class(class_type: str, schema_provider: Any | None) -> tuple[str, list[str | None] | None]:
    committed = widget_names_for_class(class_type)
    if committed is not None:
        return "committed_widget_schema", committed
    from vibecomfy.schema import schema_for

    schema = schema_for(schema_provider, class_type)
    if schema is None:
        return "unavailable", None
    return "schema_provider", widget_names_from_schema(class_type, schema)


def _raw_ui_nodes_by_id(raw_workflow: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    if not isinstance(raw_workflow, dict):
        return {}
    raw = raw_workflow.get("prompt") if isinstance(raw_workflow.get("prompt"), dict) else raw_workflow
    nodes = raw.get("nodes") if isinstance(raw, dict) else None
    if not isinstance(nodes, list):
        return {}
    return {str(node["id"]): node for node in nodes if isinstance(node, dict) and "id" in node}


def _widget_values_for_node(node_id: str, api_node: Any, raw_ui_nodes: dict[str, dict[str, Any]]) -> list[Any]:
    raw_ui = raw_ui_nodes.get(node_id)
    if raw_ui is None and isinstance(api_node, dict) and isinstance(api_node.get("_ui"), dict):
        raw_ui = api_node["_ui"]
    if isinstance(raw_ui, dict) and isinstance(raw_ui.get("widgets_values"), list):
        return list(raw_ui["widgets_values"])
    if not isinstance(api_node, dict) or not isinstance(api_node.get("inputs"), dict):
        return []
    values: list[Any] = []
    for key, value in api_node["inputs"].items():
        if not key.startswith("widget_"):
            continue
        idx = _widget_index(key)
        if idx < 0:
            continue
        while len(values) <= idx:
            values.append(None)
        values[idx] = value
    return values


def _widget_index(input_name: str) -> int:
    if not input_name.startswith("widget_"):
        return -1
    try:
        return int(input_name.split("_", 1)[1])
    except ValueError:
        return -1


def _format_widget_schema_entry(class_type: str, names: list[str | None]) -> str:
    rendered = ", ".join("None" if name is None else repr(name) for name in names)
    return f"{class_type!r}: [{rendered}]"


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
    "widget_alias_analysis",
    "unresolved_widget_aliases",
    "widget_names_for_class",
    "widget_names_from_schema",
]
