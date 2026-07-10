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


_OPS_TEMPLATES = (
    "image/z_image",
    "image/flux2_klein_4b_t2i",
    "video/wan_t2v",
    "video/wan_i2v",
    "video/ltx2_3_t2v",
    "video/ltx2_3_i2v",
)

pytestmark = pytest.mark.runpod


def test_layer2_runpod_ops_smoke() -> None:
    require_runpod_api_key()
    runpod_lifecycle = load_runpod_lifecycle()
    asyncio.run(_run(runpod_lifecycle))


async def _run(runpod_lifecycle) -> None:
    config = runpod_lifecycle.RunPodConfig.from_env(
        gpu_type=os.environ.get("RUNPOD_GPU_TYPE", "NVIDIA GeForce RTX 4090"),
        ram_tiers=(32, 16),
        storage_volumes=(),
    )
    async with launch_with_budget(
        runpod_lifecycle,
        config,
        name=pod_name("ops"),
        max_runtime_seconds=3600,
    ) as pod:
        print(f"[layer2-ops] pod_id={pod.id}")
        try:
            await pod.wait_ready(timeout=600)
            await install_current_branch(pod)
            await ensure_node_packs(pod, _OPS_TEMPLATES)
            await asyncio.wait_for(_remote(pod), timeout=3600)
        finally:
            print(f"[layer2-ops] terminating pod_id={pod.id}")


async def _remote(pod) -> None:
    code, stdout, stderr = await pod.exec_ssh(_REMOTE_BODY, timeout=3300)
    assert code == 0, f"remote layer2 ops smoke failed with {code}\nSTDOUT:\n{stdout}\nSTDERR:\n{stderr}"
    assert "VIBECOMFY_LAYER2_OPS_OUTPUTS=" in stdout


_REMOTE_BODY = r"""python - <<'PY'
from __future__ import annotations

import asyncio
import json
import os

from vibecomfy import image, video
from vibecomfy.runtime import EmbeddedSession


async def warmup() -> None:
    session = EmbeddedSession()
    try:
        await session.reload_for_nodepack_change(reason="layer2-ops-smoke")
    finally:
        await session.stop()


def check_outputs(label: str, outputs) -> None:
    if not outputs:
        raise SystemExit(f"{label}: empty outputs")
    for path in outputs:
        if not os.path.exists(path):
            raise SystemExit(f"{label}: missing path {path}")
        if os.path.getsize(path) <= 0:
            raise SystemExit(f"{label}: zero-size path {path}")


def main() -> None:
    # Warmup runs in its own event loop. The verb-native art.run() calls below are
    # sync wrappers that internally call asyncio.run(), so they MUST execute at
    # sync top-level — not from inside another running loop. backend="graphbuilder"
    # inlines subgraph definitions; "api" leaves them as UUID-typed nodes that
    # HiddenSwitch ComfyUI rejects with missing_node_type.
    asyncio.run(warmup())

    art1 = image.t2i("a fox", width=512, height=512, steps=4)
    if not art1.preview_workflow().validate().ok:
        raise SystemExit("t2i z_image: validation failed")
    res1 = art1.run(backend="graphbuilder")
    check_outputs("t2i z_image", res1.outputs)

    art2 = image.t2i("a fox", model="flux2_klein_4b", width=512, height=512, steps=4)
    res2 = art2.run(backend="graphbuilder")
    check_outputs("t2i flux2_klein_4b", res2.outputs)

    art3 = video.t2v("a fox running", length=9, fps=8)
    res3 = art3.run(backend="graphbuilder")
    check_outputs("t2v wan", res3.outputs)

    art4 = video.t2v("a fox running", model="ltx", length=9)
    res4 = art4.run(backend="graphbuilder")
    check_outputs("t2v ltx", res4.outputs)

    art5 = video.i2v(res2.outputs[0], "make it move", length=9, fps=8)
    res5 = art5.run(backend="graphbuilder")
    check_outputs("i2v wan", res5.outputs)

    art6 = video.i2v(res2.outputs[0], "make it move", model="ltx", length=9)
    res6 = art6.run(backend="graphbuilder")
    check_outputs("i2v ltx", res6.outputs)

    print("VIBECOMFY_LAYER2_OPS_OUTPUTS=" + json.dumps([
        res1.outputs,
        res2.outputs,
        res3.outputs,
        res4.outputs,
        res5.outputs,
        res6.outputs,
    ]))


main()
PY"""
