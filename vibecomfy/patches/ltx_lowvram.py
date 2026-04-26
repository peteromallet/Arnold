from __future__ import annotations

from vibecomfy.patches.requirements import ensure_custom_nodes
from vibecomfy.patches.types import Patch
from vibecomfy.workflow import VibeWorkflow


COMFY_CONFIGURATION = {
    "reserve_vram": 12,
    "cache_none": True,
    "fp8_e4m3fn_text_enc": True,
}


def applies_to(workflow: VibeWorkflow) -> bool:
    has_ltx = any(node.class_type.startswith("LTX") or "LTX" in node.class_type for node in workflow.nodes.values())
    already_lowvram = any(node.class_type in {"LowVRAMAudioVAELoader", "LowVRAMCheckpointLoader"} for node in workflow.nodes.values())
    return has_ltx and (workflow.metadata.get("comfy_configuration") != COMFY_CONFIGURATION or not already_lowvram)


def apply(workflow: VibeWorkflow) -> VibeWorkflow:
    image_to_video = workflow.metadata.get("capability") == "image_to_video"
    if "3159" in workflow.nodes:
        image_to_video = True

    _update_node(workflow, "3059", inputs={"width": 384, "height": 256}, widgets={"widget_0": 384, "widget_1": 256, "widget_2": 9})
    _update_node(workflow, "4979", widgets={"widget_0": 9})
    _update_node(workflow, "4978", widgets={"widget_0": 8})
    _update_node(workflow, "1241", widgets={"widget_0": 8})
    _update_node(workflow, "3980", widgets={"widget_0": 9, "widget_1": 8})
    _update_node(workflow, "4977", widgets={"widget_0": not image_to_video})
    _update_node(workflow, "2004", widgets={"widget_0": "egyptian_queen.png" if image_to_video else "example.png"})
    _update_node(workflow, "4981", widgets={"widget_1": 384})

    if "4010" in workflow.nodes:
        node = workflow.nodes["4010"]
        node.class_type = "LowVRAMAudioVAELoader"
        node.inputs = {"ckpt_name": "ltx-2.3-22b-dev-fp8.safetensors"}
        node.widgets = {}
    if "3940" in workflow.nodes:
        node = workflow.nodes["3940"]
        node.class_type = "LowVRAMCheckpointLoader"
        node.inputs = {"ckpt_name": "ltx-2.3-22b-dev-fp8.safetensors", "dependencies": ["4960", 0]}
        node.widgets = {}

    workflow.metadata["smoke_resolution"] = "384x256x9_frames"
    workflow.metadata["comfy_configuration"] = dict(COMFY_CONFIGURATION)
    if ready_template := workflow.metadata.get("ready_template"):
        workflow.metadata["external_python_marker"] = f"external_python:{ready_template}"

    workflow.finalize_metadata()
    ensure_custom_nodes(workflow, ("ComfyUI-LTXVideo", "ComfyUI-KJNodes"))
    return workflow


def rationale(workflow: VibeWorkflow) -> str:
    return "LTXVideo nodes detected; reduces VRAM by using low-VRAM loaders and 384x256x9 smoke settings."


def _update_node(
    workflow: VibeWorkflow,
    node_id: str,
    *,
    inputs: dict | None = None,
    widgets: dict | None = None,
) -> None:
    node = workflow.nodes.get(node_id)
    if node is None:
        return
    if inputs:
        for key, value in inputs.items():
            if isinstance(value, list):
                continue
            node.inputs[key] = value
    if widgets:
        node.widgets.update(widgets)


patch = Patch("ltx_lowvram", applies_to, apply, rationale)


__all__ = ["COMFY_CONFIGURATION", "applies_to", "apply", "patch", "rationale"]
