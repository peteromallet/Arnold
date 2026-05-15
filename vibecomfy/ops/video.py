from __future__ import annotations

from pathlib import Path
from typing import Any, Union

from vibecomfy.artifacts import Image, Video
from vibecomfy.cli_loader import load_workflow_any
from vibecomfy.ops._common import first_output, set_prompt_preserving_registration
from vibecomfy.ops._namespace import dispatch, namespace_getattr
from vibecomfy.ops.registry import register_op
from vibecomfy.router import pick

I2VImage = Union[Image, str, Path, bytes]


def t2v(
    prompt: str,
    *,
    model: str | None = None,
    width: int | None = None,
    height: int | None = None,
    length: int | None = None,
    fps: int = 16,
    seed: int | None = None,
    **overrides: Any,
) -> Video:
    return dispatch(
        "video",
        "t2v",
        prompt,
        model=model,
        width=width,
        height=height,
        length=length,
        fps=fps,
        seed=seed,
        **overrides,
    )


def _t2v(
    prompt: str,
    *,
    model: str | None = None,
    width: int | None = None,
    height: int | None = None,
    length: int | None = None,
    fps: int = 16,
    seed: int | None = None,
    **overrides: Any,
) -> Video:
    result = pick("video", "t2v", model=model, width=width, height=height, length=length, fps=fps, seed=seed, **overrides)
    workflow = load_workflow_any(result.template_id)
    set_prompt_preserving_registration(workflow, prompt, result.explicit_patches)
    if seed is not None:
        workflow.set_seed(seed)
    output = first_output(workflow, "SaveVideo")
    return Video(
        workflow=workflow,
        node_id=output.node_id,
        output_slot=0,
        metadata={"template_id": result.template_id, "model": model},
    )


def i2v(
    image: Any,
    prompt: str,
    *,
    model: str | None = None,
    length: int | None = None,
    fps: int = 16,
    seed: int | None = None,
    **overrides: Any,
) -> Video:
    return dispatch(
        "video",
        "i2v",
        image,
        prompt,
        model=model,
        length=length,
        fps=fps,
        seed=seed,
        **overrides,
    )


def _i2v(
    image: Any,
    prompt: str,
    *,
    model: str | None = None,
    length: int | None = None,
    fps: int = 16,
    seed: int | None = None,
    **overrides: Any,
) -> Video:
    result = pick("video", "i2v", model=model, image=image, length=length, fps=fps, seed=seed, **overrides)
    workflow = load_workflow_any(result.template_id)
    set_prompt_preserving_registration(workflow, prompt, result.explicit_patches)
    if seed is not None:
        workflow.set_seed(seed)
    output = first_output(workflow, "SaveVideo")
    return Video(
        workflow=workflow,
        node_id=output.node_id,
        output_slot=0,
        metadata={"template_id": result.template_id, "model": model},
    )


def __getattr__(name: str) -> Any:
    return namespace_getattr("video", name)


register_op("video", "t2v", _t2v)
register_op("video", "i2v", _i2v)


__all__ = ["i2v", "t2v"]
