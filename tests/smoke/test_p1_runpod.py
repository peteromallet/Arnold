from __future__ import annotations

import asyncio
import os

import pytest

from ._runpod_helpers import (
    ensure_node_packs,
    install_current_branch,
    launch_with_budget,
    load_runpod_lifecycle,
    pod_name,
    require_runpod_api_key,
)

pytestmark = pytest.mark.runpod


def test_p1_runpod_typed_handle_smoke() -> None:
    require_runpod_api_key()
    runpod_lifecycle = load_runpod_lifecycle()
    asyncio.run(_run_smoke(runpod_lifecycle))


async def _run_smoke(runpod_lifecycle) -> None:
    config = runpod_lifecycle.RunPodConfig.from_env(
        gpu_type=os.environ.get("RUNPOD_GPU_TYPE", "NVIDIA GeForce RTX 4090"),
        ram_tiers=(32, 16),
        storage_volumes=(),
    )
    async with launch_with_budget(
        runpod_lifecycle,
        config,
        name=pod_name("p1", "z_image"),
        max_runtime_seconds=2400,
    ) as pod:
        await pod.wait_ready(timeout=600)
        await install_current_branch(pod)
        await ensure_node_packs(pod, ("image/z_image",))
        code, stdout, stderr = await pod.exec_ssh(_REMOTE_SMOKE_COMMAND, timeout=1800)
        assert code == 0, f"remote smoke failed with {code}\nSTDOUT:\n{stdout}\nSTDERR:\n{stderr}"
        assert "VIBECOMFY_P1_OUTPUTS=" in stdout


_REMOTE_SMOKE_COMMAND = r"""python - <<'PY'
from __future__ import annotations

import asyncio
import json

from vibecomfy import VibeWorkflow, WorkflowSource
from vibecomfy.runtime import EmbeddedSession

PROMPT = (
    "A fashion photography work full of surreal romanticism, using a low-angle upward shooting "
    "composition, with a clear light blue sky as the background, and the visual focus concentrated "
    "on the fantasy blue vegetation and the model walking through it.\n"
    "\n"
    "The vegetation in the picture is processed into varying shades of blue, from light ice blue to "
    "deep cobalt blue. The textures of the leaves and branches are delicate and realistic. The warm "
    "brown tree trunks form a sharp contrast with the cool blue leaves, resembling a dreamy forest "
    "from another world. An African-American model wearing a yellow and white vertical striped long "
    "dress walks slowly on the sand. The warm tones of the dress echo with the surrounding cool blue "
    "vegetation. The noon sun casts clear shadows on the sand, enhancing the sense of space and "
    "reality in the picture.\n"
    "\n"
    "The entire scene, with its clean and transparent colors and fantasy settings, not only exudes "
    "the vastness of the natural wilderness but also presents a quiet and poetic high-fashion sense "
    "due to the surreal vegetation."
)

Z_IMAGE_SUBGRAPH = "9b9009e4-2d3d-445f-9be5-6063f465757e"


def build_z_image_typed() -> VibeWorkflow:
    workflow = VibeWorkflow("image/z_image", WorkflowSource("runpod-smoke"))
    save = workflow.node("SaveImage", widget_0="z-image")
    image = workflow.node(
        Z_IMAGE_SUBGRAPH,
        widget_0=PROMPT,
        widget_1=1024,
        widget_2=1024,
        widget_3=25,
        widget_4=4,
        widget_5=None,
        widget_6=None,
        widget_7="z_image_bf16.safetensors",
        widget_8="qwen_3_4b.safetensors",
        widget_9="ae.safetensors",
    ).out(0)
    workflow.connect(image, f"{save.id}.images")
    return workflow


async def main() -> None:
    workflow = build_z_image_typed()
    session = EmbeddedSession()
    try:
        await session.reload_for_nodepack_change(reason="smoke")
        result = await session.run(workflow)
    finally:
        await session.stop()
    if not result.outputs:
        raise SystemExit("expected at least one output path")
    print("VIBECOMFY_P1_OUTPUTS=" + json.dumps(result.outputs))


asyncio.run(main())
PY"""
