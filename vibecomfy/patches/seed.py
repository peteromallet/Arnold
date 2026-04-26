from __future__ import annotations

from vibecomfy.metadata import SEED_KEYS
from vibecomfy.patches.types import Patch
from vibecomfy.workflow import VibeWorkflow


SEED_WIDGET_CLASSES = {"KSampler", "RandomNoise"}


def seed(value: int) -> Patch:
    seed_value = int(value)

    def applies_to(workflow: VibeWorkflow) -> bool:
        return any(_has_seed(node.inputs, node.widgets, node.class_type) for node in workflow.nodes.values())

    def apply(workflow: VibeWorkflow) -> VibeWorkflow:
        changed = False
        for node in workflow.nodes.values():
            changed = _set_seed(node.inputs, node.widgets, node.class_type, seed_value) or changed
        if not changed:
            workflow.metadata.setdefault("unbound_inputs", {})["seed"] = seed_value
        workflow.finalize_metadata()
        return workflow

    def rationale(workflow: VibeWorkflow) -> str:
        return f"Pins stochastic seed fields to {seed_value}."

    return Patch(f"seed:{seed_value}", applies_to, apply, rationale)


def _has_seed(inputs: dict, widgets: dict, class_type: str) -> bool:
    keys = {key.lower() for key in inputs} | {key.lower() for key in widgets}
    return bool(SEED_KEYS & keys or class_type in SEED_WIDGET_CLASSES)


def _set_seed(inputs: dict, widgets: dict, class_type: str, value: int) -> bool:
    changed = False
    for container in (inputs, widgets):
        for key in list(container):
            if key.lower() in SEED_KEYS:
                container[key] = value
                changed = True
    if class_type in SEED_WIDGET_CLASSES and "widget_0" in widgets:
        widgets["widget_0"] = value
        changed = True
    return changed


__all__ = ["seed"]
