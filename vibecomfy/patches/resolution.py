from __future__ import annotations

from vibecomfy.patches.types import Patch
from vibecomfy.workflow import VibeWorkflow


WIDTH_KEYS = {"width", "w"}
HEIGHT_KEYS = {"height", "h"}
LENGTH_KEYS = {"length", "frames", "num_frames"}


def resolution(width: int, height: int, length: int | None = None) -> Patch:
    def applies_to(workflow: VibeWorkflow) -> bool:
        return any(_has_resolution_surface(node.inputs, node.widgets, node.class_type) for node in workflow.nodes.values())

    def apply(workflow: VibeWorkflow) -> VibeWorkflow:
        for node in workflow.nodes.values():
            _set_resolution(node.inputs, node.widgets, node.class_type, width, height, length)
        workflow.finalize_metadata()
        return workflow

    def rationale(workflow: VibeWorkflow) -> str:
        suffix = f"x{length}" if length is not None else ""
        return f"Sets workflow resolution to {width}x{height}{suffix}."

    return Patch(f"resolution:{width}x{height}" + (f"x{length}" if length is not None else ""), applies_to, apply, rationale)


def _has_resolution_surface(inputs: dict, widgets: dict, class_type: str) -> bool:
    keys = {key.lower() for key in inputs} | {key.lower() for key in widgets}
    return bool((WIDTH_KEYS & keys and HEIGHT_KEYS & keys) or class_type in {"EmptyHunyuanLatentVideo", "EmptyLTXVLatentVideo"})


def _set_resolution(inputs: dict, widgets: dict, class_type: str, width: int, height: int, length: int | None) -> None:
    for key in list(inputs):
        lowered = key.lower()
        if lowered in WIDTH_KEYS:
            inputs[key] = width
        elif lowered in HEIGHT_KEYS:
            inputs[key] = height
        elif length is not None and lowered in LENGTH_KEYS and not isinstance(inputs[key], list):
            inputs[key] = length
    if class_type in {"EmptyHunyuanLatentVideo", "EmptyLTXVLatentVideo"}:
        widgets.update({"widget_0": width, "widget_1": height})
        if length is not None:
            widgets["widget_2"] = length


__all__ = ["resolution"]
