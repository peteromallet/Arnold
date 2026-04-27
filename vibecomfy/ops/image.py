from __future__ import annotations

from typing import Any

from vibecomfy.artifacts import Image
from vibecomfy.cli_loader import load_workflow_any
from vibecomfy.ops._namespace import dispatch, namespace_getattr
from vibecomfy.ops.registry import register_op
from vibecomfy.patches.types import Patch
from vibecomfy.router import pick
from vibecomfy.workflow import VibeInput, VibeOutput, VibeWorkflow


_EDIT_UNAVAILABLE = (
    "image.edit is not yet exposed via the verb-native API for the qwen/flux edit templates whose UUID subgraphs "
    "lack a verified text input; use load_workflow_any('edit/qwen_image_edit') or "
    "load_workflow_any('edit/flux2_klein_4b_image_edit_distilled') and edit the VibeWorkflow directly until MP-6 "
    "ships schema-backed UUID-subgraph input validation"
)


def t2i(
    prompt: str,
    *,
    model: str | None = None,
    width: int = 1024,
    height: int = 1024,
    steps: int | None = None,
    seed: int | None = None,
    **overrides: Any,
) -> Image:
    return dispatch(
        "image",
        "t2i",
        prompt,
        model=model,
        width=width,
        height=height,
        steps=steps,
        seed=seed,
        **overrides,
    )


def _t2i(
    prompt: str,
    *,
    model: str | None = None,
    width: int = 1024,
    height: int = 1024,
    steps: int | None = None,
    seed: int | None = None,
    **overrides: Any,
) -> Image:
    result = pick("image", "t2i", model=model, width=width, height=height, steps=steps, seed=seed, **overrides)
    workflow = load_workflow_any(result.template_id)
    _set_prompt_preserving_registration(workflow, prompt, result.explicit_patches)
    if seed is not None:
        workflow.set_seed(seed)
    if steps is not None:
        workflow.set_steps(steps)
    output = _first_output(workflow, "SaveImage")
    return Image(
        workflow=workflow,
        node_id=output.node_id,
        output_slot=0,
        metadata={"template_id": result.template_id, "model": model},
    )


def edit(image: Any, instruction: str, *, model: str | None = None, **overrides: Any) -> Image:
    return dispatch("image", "edit", image, instruction, model=model, **overrides)


def _edit(image: Any, instruction: str, *, model: str | None = None, **overrides: Any) -> Image:
    raise NotImplementedError(_EDIT_UNAVAILABLE)


def _set_prompt_preserving_registration(workflow: VibeWorkflow, prompt: str, patches: list[Patch]) -> None:
    prompt_target = workflow.inputs.get("prompt")
    workflow.set_prompt(prompt)
    for patch in patches:
        patch.apply(workflow)
    if prompt_target is not None:
        _restore_input(workflow, "prompt", prompt_target)
    workflow.set_prompt(prompt)


def _restore_input(workflow: VibeWorkflow, name: str, target: VibeInput) -> None:
    if name in workflow.inputs or target.node_id not in workflow.nodes:
        return
    node = workflow.nodes[target.node_id]
    value = node.inputs.get(target.field, node.widgets.get(target.field, target.value))
    workflow.register_input(name, target.node_id, target.field, value)


def _first_output(workflow: VibeWorkflow, output_type: str) -> VibeOutput:
    if not workflow.outputs:
        workflow.finalize_metadata()
    for output in workflow.outputs:
        if output.output_type == output_type:
            return output
    raise ValueError(f"Workflow has no {output_type} output")


def __getattr__(name: str) -> Any:
    return namespace_getattr("image", name)


register_op("image", "t2i", _t2i)
register_op("image", "edit", _edit)


__all__ = ["edit", "t2i"]
