from __future__ import annotations

from dataclasses import dataclass

from vibecomfy.patches.requirements import ensure_custom_nodes
from vibecomfy.patches.types import Patch
from vibecomfy.workflow import VibeWorkflow


CUSTOM_NODE_PACK = "ComfyUI-ControlNet"


@dataclass(frozen=True)
class ControlNetSettings:
    control_net_name: str = "depth.safetensors"
    image_node_id: str | None = None
    strength: float = 1.0


def _find_ksampler_id(workflow: VibeWorkflow) -> str | None:
    for node_id, node in workflow.nodes.items():
        if node.class_type == "KSampler":
            return node_id
    return None


def _has_edge_into(workflow: VibeWorkflow, node_id: str, input_name: str) -> bool:
    return any(edge.to_node == node_id and edge.to_input == input_name for edge in workflow.edges)


def _find_edge_into(workflow: VibeWorkflow, node_id: str, input_name: str):
    for edge in workflow.edges:
        if edge.to_node == node_id and edge.to_input == input_name:
            return edge
    return None


def applies_to(workflow: VibeWorkflow) -> bool:
    sampler_id = _find_ksampler_id(workflow)
    if sampler_id is None:
        return False
    return _has_edge_into(workflow, sampler_id, "positive")


def apply(workflow: VibeWorkflow) -> VibeWorkflow:
    return _apply_with_settings(workflow, ControlNetSettings())


def _apply_with_settings(workflow: VibeWorkflow, settings: ControlNetSettings) -> VibeWorkflow:
    sampler_id = _find_ksampler_id(workflow)
    if sampler_id is None:
        return workflow

    pos_edge = _find_edge_into(workflow, sampler_id, "positive")
    neg_edge = _find_edge_into(workflow, sampler_id, "negative")
    if pos_edge is None:
        return workflow

    # Add the new ControlNet support nodes.
    loader = workflow.add_node("ControlNetLoader")
    loader.widgets["control_net_name"] = settings.control_net_name

    apply_pos = workflow.add_node("ControlNetApplyAdvanced")
    apply_pos.widgets["strength"] = settings.strength
    apply_pos.widgets["start_percent"] = 0.0
    apply_pos.widgets["end_percent"] = 1.0

    # Wire ControlNetLoader -> ControlNetApplyAdvanced.control_net.
    workflow.connect(f"{loader.id}.0", f"{apply_pos.id}.control_net")

    # Splice on the positive chain:
    #   original_pos_source -> apply_pos.positive
    #   apply_pos.0         -> sampler.positive
    original_pos_from = f"{pos_edge.from_node}.{pos_edge.from_output}"
    workflow.connect(original_pos_from, f"{apply_pos.id}.positive")
    workflow.replace_edge(f"{sampler_id}.positive", f"{apply_pos.id}.0")

    # Mirror the splice on the negative chain when present.
    if neg_edge is not None:
        apply_neg = workflow.add_node("ControlNetApplyAdvanced")
        apply_neg.widgets["strength"] = settings.strength
        apply_neg.widgets["start_percent"] = 0.0
        apply_neg.widgets["end_percent"] = 1.0
        workflow.connect(f"{loader.id}.0", f"{apply_neg.id}.control_net")
        original_neg_from = f"{neg_edge.from_node}.{neg_edge.from_output}"
        workflow.connect(original_neg_from, f"{apply_neg.id}.negative")
        workflow.replace_edge(f"{sampler_id}.negative", f"{apply_neg.id}.0")
        if settings.image_node_id is not None:
            workflow.connect(f"{settings.image_node_id}.0", f"{apply_neg.id}.image")

    if settings.image_node_id is not None:
        workflow.connect(f"{settings.image_node_id}.0", f"{apply_pos.id}.image")

    ensure_custom_nodes(workflow, (CUSTOM_NODE_PACK,))

    return workflow


def rationale(workflow: VibeWorkflow) -> str:
    return "KSampler with conditioning detected; ControlNet can splice extra conditioning into the positive/negative chain."


def controlnet_patch(
    *,
    control_net_name: str = "depth.safetensors",
    image_node_id: str | None = None,
    strength: float = 1.0,
) -> Patch:
    settings = ControlNetSettings(
        control_net_name=control_net_name,
        image_node_id=image_node_id,
        strength=strength,
    )

    def configured_apply(workflow: VibeWorkflow) -> VibeWorkflow:
        return _apply_with_settings(workflow, settings)

    suffix = control_net_name
    if image_node_id is not None:
        suffix = f"{suffix}:{image_node_id}"
    if strength != 1.0:
        suffix = f"{suffix}:{strength:g}"
    return Patch(f"controlnet:{suffix}", applies_to, configured_apply, rationale)


patch = Patch("controlnet", applies_to, apply, rationale)


__all__ = ["CUSTOM_NODE_PACK", "ControlNetSettings", "applies_to", "apply", "controlnet_patch", "patch", "rationale"]
