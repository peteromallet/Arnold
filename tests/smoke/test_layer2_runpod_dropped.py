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


_DROPPED_TEMPLATES = (
    "image/flux2_klein_9b_gguf_t2i",
    "edit/flux2_klein_4b_image_edit_distilled",
    "edit/qwen_image_edit",
)

pytestmark = pytest.mark.runpod


def test_layer2_runpod_dropped_templates() -> None:
    require_runpod_api_key()
    runpod_lifecycle = load_runpod_lifecycle()
    asyncio.run(_run_dropped(runpod_lifecycle))


async def _run_dropped(runpod_lifecycle) -> None:
    config = runpod_lifecycle.RunPodConfig.from_env(
        gpu_type=os.environ.get("RUNPOD_GPU_TYPE", "NVIDIA GeForce RTX 4090"),
        ram_tiers=(32, 16),
        storage_volumes=(),
    )
    async with launch_with_budget(
        runpod_lifecycle,
        config,
        name=pod_name("dropped"),
        max_runtime_seconds=3600,
    ) as pod:
        print(f"VIBECOMFY_LAYER2_DROPPED_POD_PROVISIONED id={pod.id}")
        try:
            await asyncio.wait_for(_run_body(pod), timeout=3600)
        finally:
            print(f"VIBECOMFY_LAYER2_DROPPED_POD_TEARDOWN id={pod.id}")


async def _run_body(pod) -> None:
    await pod.wait_ready(timeout=600)
    await install_current_branch(pod)
    await ensure_node_packs(pod, _DROPPED_TEMPLATES)
    code, stdout, stderr = await pod.exec_ssh(_REMOTE_DROPPED_COMMAND, timeout=3000)
    assert "VIBECOMFY_LAYER2_DROPPED_FAILURES=" in stdout, (
        f"missing failure marker in stdout\nSTDOUT:\n{stdout}\nSTDERR:\n{stderr}"
    )
    marker_line = next(
        line for line in stdout.splitlines() if line.startswith("VIBECOMFY_LAYER2_DROPPED_FAILURES=")
    )
    payload = marker_line.split("=", 1)[1]
    assert payload == "[]", (
        f"dropped templates reported failures (exit={code}): {payload}\n"
        f"STDOUT:\n{stdout}\nSTDERR:\n{stderr}"
    )
    assert code == 0, (
        f"remote dropped-templates run exited {code} despite empty failures list\n"
        f"STDOUT:\n{stdout}\nSTDERR:\n{stderr}"
    )


_REMOTE_DROPPED_COMMAND = r"""python - <<'PY'
from __future__ import annotations

import asyncio
import json
import sys


TIDS = (
    "image/flux2_klein_9b_gguf_t2i",
    "edit/flux2_klein_4b_image_edit_distilled",
    "edit/qwen_image_edit",
)


async def warmup_nodepack() -> None:
    from vibecomfy.runtime import EmbeddedSession

    warmup = EmbeddedSession()
    try:
        await warmup.reload_for_nodepack_change(reason="layer2-dropped-smoke")
    finally:
        await warmup.stop()


def main() -> int:
    asyncio.run(warmup_nodepack())

    from vibecomfy import load_workflow_any
    from vibecomfy.runtime import run_embedded_sync

    failures: list = []
    for tid in TIDS:
        try:
            wf = load_workflow_any(tid)
            report = wf.validate()
            if not report.ok:
                failures.append(
                    (
                        tid,
                        "validate",
                        [
                            {"code": getattr(issue, "code", ""), "message": getattr(issue, "message", "")}
                            for issue in report.issues[:5]
                        ],
                    )
                )
                continue
            result = run_embedded_sync(wf, backend="graphbuilder")
            if not result.outputs:
                failures.append((tid, "run", "no outputs"))
        except Exception as exc:
            failures.append((tid, "exception", repr(exc)))

    print("VIBECOMFY_LAYER2_DROPPED_FAILURES=" + json.dumps(failures))
    return 1 if failures else 0


sys.exit(main())
PY"""
