"""Single-route smoke for the hand-authored z_image template.

Runs only the z_image t2i route on one pod via the verb-native API. Used to
validate the conversion before spending parallel pods on the other templates.
"""
from __future__ import annotations

import asyncio
import os

import pytest

from ._runpod_helpers import (
    install_current_branch,
    launch_with_budget,
    load_runpod_lifecycle,
    pod_name,
    require_runpod_api_key,
)

pytestmark = pytest.mark.runpod


def test_z_image_only_smoke() -> None:
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
        name=pod_name("zimage", "proof"),
        max_runtime_seconds=2400,
    ) as pod:
        print(f"[z-image-only] pod_id={pod.id}")
        try:
            await pod.wait_ready(timeout=600)
            await install_current_branch(pod)
            await asyncio.wait_for(_remote(pod), timeout=2400)
        finally:
            print(f"[z-image-only] terminating pod_id={pod.id}")


async def _remote(pod) -> None:
    code, stdout, stderr = await pod.exec_ssh(_REMOTE_BODY, timeout=2100)
    assert code == 0, f"remote z_image smoke failed with {code}\nSTDOUT:\n{stdout}\nSTDERR:\n{stderr}"
    assert "VIBECOMFY_Z_IMAGE_OK=" in stdout, (
        f"missing OK marker\nSTDOUT:\n{stdout}\nSTDERR:\n{stderr}"
    )


_REMOTE_BODY = r"""python - <<'PY'
from __future__ import annotations

import asyncio
import json
import os
import traceback

from vibecomfy import load_workflow_any
from vibecomfy.runtime import EmbeddedSession, run_embedded_sync


async def warmup() -> None:
    session = EmbeddedSession()
    try:
        await session.reload_for_nodepack_change(reason="z-image-only-smoke")
    finally:
        await session.stop()


def _resolve_path(path: str) -> str:
    # ComfyUI may return paths relative to its output dir.
    if os.path.isabs(path) and os.path.exists(path):
        return path
    candidates = [path, os.path.join("output", path), os.path.join(os.getcwd(), path)]
    for c in candidates:
        if os.path.exists(c):
            return c
    return path


def main() -> None:
    asyncio.run(warmup())

    wf = load_workflow_any("image/z_image")
    print("VIBECOMFY_Z_IMAGE_VALIDATE=" + json.dumps({"ok": wf.validate().ok}))
    print("VIBECOMFY_Z_IMAGE_NODES=" + str(len(wf.nodes)))

    try:
        res = run_embedded_sync(wf, backend="graphbuilder")
    except Exception as exc:
        print("VIBECOMFY_Z_IMAGE_EXCEPTION=" + repr(exc))
        traceback.print_exc()
        raise SystemExit(1)

    print("VIBECOMFY_Z_IMAGE_RUN_ID=" + res.run_id)
    print("VIBECOMFY_Z_IMAGE_OUTPUTS_RAW=" + json.dumps(res.outputs))
    print("VIBECOMFY_Z_IMAGE_LOG_PATH=" + res.log_path)

    # Show comfy log tail to help diagnose silent crashes
    if os.path.exists(res.log_path):
        with open(res.log_path) as f:
            tail = f.read()[-2000:]
        print("=== COMFY LOG TAIL ===")
        print(tail)
        print("=== END LOG ===")

    if not res.outputs:
        print("VIBECOMFY_Z_IMAGE_FAIL=empty_outputs")
        raise SystemExit(2)

    resolved = []
    for path in res.outputs:
        rp = _resolve_path(path)
        exists = os.path.exists(rp)
        size = os.path.getsize(rp) if exists else 0
        resolved.append({"raw": path, "resolved": rp, "exists": exists, "size": size})
    print("VIBECOMFY_Z_IMAGE_RESOLVED=" + json.dumps(resolved))

    if not all(r["exists"] and r["size"] > 0 for r in resolved):
        raise SystemExit(3)

    print("VIBECOMFY_Z_IMAGE_OK=" + json.dumps([r["resolved"] for r in resolved]))


main()
PY"""
