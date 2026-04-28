from __future__ import annotations

from typing import Any

from vibecomfy.artifacts import Image
from vibecomfy.cli_loader import load_workflow_any
from vibecomfy.ops._namespace import dispatch, namespace_getattr
from vibecomfy.ops.registry import register_op
from vibecomfy.patches.types import Patch
from vibecomfy.router import pick
from vibecomfy.workflow import VibeInput, VibeOutput, VibeWorkflow


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


__all__ = ["t2i"]
