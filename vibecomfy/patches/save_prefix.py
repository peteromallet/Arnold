from __future__ import annotations

from vibecomfy.patches.types import Patch
from vibecomfy.workflow import VibeWorkflow


SAVE_CLASSES = {"SaveImage", "SaveVideo", "VHS_VideoCombine", "SaveAnimatedWEBP", "SaveWEBM"}


def save_prefix(value: str) -> Patch:
    def applies_to(workflow: VibeWorkflow) -> bool:
        return any(node.class_type in SAVE_CLASSES for node in workflow.nodes.values())

    def apply(workflow: VibeWorkflow) -> VibeWorkflow:
        for node in workflow.nodes.values():
            if node.class_type not in SAVE_CLASSES:
                continue
            if "filename_prefix" in node.inputs:
                node.inputs["filename_prefix"] = value
            else:
                node.widgets["widget_0"] = value
        workflow.finalize_metadata()
        return workflow

    def rationale(workflow: VibeWorkflow) -> str:
        return f"Sets output filename prefix to {value!r}."

    return Patch(f"save_prefix:{value}", applies_to, apply, rationale)


__all__ = ["save_prefix"]
