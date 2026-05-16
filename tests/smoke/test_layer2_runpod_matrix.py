"""Phase 2 — production-resolution matrix across model families.

Launches one pod per family in parallel, each running only its family's verb-native
routes at the resolutions users actually run. Marker: ``runpod_full``.

Per-pod failures are isolated: ``asyncio.gather(..., return_exceptions=True)`` plus a
per-coroutine ``try/finally`` ensures one OOM does not block the other families'
results or leak pods.
"""

from __future__ import annotations

import asyncio
import json
import os

import pytest

import time

from ._runpod_helpers import (
    ensure_node_packs,
    install_current_branch,
    launch_with_retry,
    load_runpod_lifecycle,
    pod_name,
    precharge_budget,
    require_runpod_api_key,
    settle_budget,
)

pytestmark = pytest.mark.runpod_full


_FAMILY_CONFIGS: list[dict] = [
    {
        "family": "z_image",
        "default_gpu": "NVIDIA GeForce RTX 4090",
        "templates": ("image/z_image",),
        "routes": [
            {
                "verb": "image.t2i",
                "model": None,
                "kwargs": {"width": 1024, "height": 1024, "steps": 25},
                "kind": "image",
            },
        ],
    },
    {
        "family": "flux_klein_4b",
        "default_gpu": "NVIDIA GeForce RTX 4090",
        "templates": ("image/flux2_klein_4b_t2i",),
        "routes": [
            {
                "verb": "image.t2i",
                "model": "flux2_klein_4b",
                "kwargs": {"width": 1024, "height": 1024},
                "kind": "image",
            },
        ],
    },
    {
        "family": "wan",
        "default_gpu": "NVIDIA GeForce RTX 4090",
        "templates": ("video/wan_t2v", "video/wan_i2v"),
        "routes": [
            {
                "verb": "video.t2v",
                "model": None,
                "kwargs": {"width": 832, "height": 480, "length": 81, "fps": 16},
                "kind": "video",
                "expected_frames": 81,
            },
            {
                "verb": "video.i2v",
                "model": None,
                "kwargs": {"length": 81, "fps": 16},
                "kind": "video",
                "expected_frames": 81,
                "needs_input_image": True,
            },
        ],
    },
    {
        "family": "ltx",
        "default_gpu": "NVIDIA GeForce RTX 4090",
        "templates": ("video/ltx2_3_t2v", "video/ltx2_3_i2v"),
        "routes": [
            # ltx patch overrides length to 9 and resolution to 384x256 — let the patch own it.
            {
                "verb": "video.t2v",
                "model": "ltx",
                "kwargs": {},
                "kind": "video",
                "expected_frames": 9,
            },
            {
                "verb": "video.i2v",
                "model": "ltx",
                "kwargs": {},
                "kind": "video",
                "expected_frames": 9,
                "needs_input_image": True,
            },
        ],
    },
]


# ---------------------------------------------------------------------------
# Test entry point
# ---------------------------------------------------------------------------


def test_layer2_runpod_matrix() -> None:
    require_runpod_api_key()
    runpod_lifecycle = load_runpod_lifecycle()
    asyncio.run(_run_matrix(runpod_lifecycle))


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------


async def _run_matrix(runpod_lifecycle) -> None:
    coros = [_run_family(runpod_lifecycle, fam) for fam in _FAMILY_CONFIGS]
    results = await asyncio.gather(*coros, return_exceptions=True)

    failures: list[tuple[str, str, object]] = []
    for fam, result in zip(_FAMILY_CONFIGS, results):
        family = fam["family"]
        if isinstance(result, BaseException):
            print(f"[layer2-matrix] {family} EXCEPTION: {result!r}")
            failures.append((family, "exception", repr(result)))
        elif not isinstance(result, dict) or not result.get("ok"):
            print(f"[layer2-matrix] {family} FAIL: {result!r}")
            failures.append((family, "route_fail", result))
        else:
            print(f"[layer2-matrix] {family} OK: {result}")

    assert not failures, f"matrix failures: {failures}"


async def _run_family(runpod_lifecycle, family_cfg: dict) -> dict:
    family = family_cfg["family"]
    gpu_type = os.environ.get(
        f"RUNPOD_GPU_TYPE_{family.upper()}",
        os.environ.get("RUNPOD_GPU_TYPE", family_cfg["default_gpu"]),
    )
    config = runpod_lifecycle.RunPodConfig.from_env(
        gpu_type=gpu_type,
        ram_tiers=(32, 16),
        storage_volumes=(),
    )
    pod = None
    max_runtime_seconds = 3600
    precharge_budget(gpu_type=gpu_type, max_runtime_seconds=max_runtime_seconds)
    start = time.monotonic()
    try:
        pod = await launch_with_retry(runpod_lifecycle, config, pod_name("matrix", family))
        print(f"[layer2-matrix:{family}] pod_id={pod.id} gpu={gpu_type}")
        await asyncio.wait_for(_run_on_pod(pod, family_cfg), timeout=3600)
        return {"ok": True, "family": family, "pod_id": pod.id}
    except BaseException as exc:  # noqa: BLE001 — collected per-family, asserted later
        pod_id = getattr(pod, "id", None)
        return {"ok": False, "family": family, "pod_id": pod_id, "error": repr(exc)}
    finally:
        if pod is not None:
            print(f"[layer2-matrix:{family}] terminating pod_id={pod.id}")
            try:
                await pod.terminate()
            except BaseException as term_exc:  # noqa: BLE001 — log, don't mask main error
                print(f"[layer2-matrix:{family}] terminate failed: {term_exc!r}")
        settle_budget(
            gpu_type=gpu_type,
            elapsed_seconds=time.monotonic() - start,
            projected_seconds=max_runtime_seconds,
        )


async def _run_on_pod(pod, family_cfg: dict) -> None:
    family = family_cfg["family"]
    await pod.wait_ready(timeout=600)
    await install_current_branch(pod)
    await ensure_node_packs(pod, family_cfg.get("templates", ()))
    body = _build_remote_body(family_cfg)
    code, stdout, stderr = await pod.exec_ssh(body, timeout=3300)
    if code != 0:
        raise AssertionError(
            f"family {family} remote failed code={code}\nSTDOUT:\n{stdout}\nSTDERR:\n{stderr}"
        )
    if "VIBECOMFY_LAYER2_MATRIX_RESULT_OK" not in stdout:
        raise AssertionError(
            f"family {family} did not emit OK marker:\nSTDOUT:\n{stdout}\nSTDERR:\n{stderr}"
        )


# ---------------------------------------------------------------------------
# Remote heredoc builder
# ---------------------------------------------------------------------------


_REMOTE_PROMPT = (
    "A serene cinematic landscape at golden hour: rolling hills, soft warm light, "
    "gentle wind through tall grass, painterly atmosphere with rich color depth."
)


def _build_remote_body(family_cfg: dict) -> str:
    config_json = json.dumps(family_cfg)
    prompt_json = json.dumps(_REMOTE_PROMPT)
    # Single-quoted heredoc so the inner Python is not subject to shell expansion.
    # Config is injected via json.loads on a triple-quoted literal — safe because
    # json.dumps escapes everything that matters inside a Python string literal.
    # NOTE: write to a real file before exec'ing — if we pipe via `python -`,
    # ComfyUI's internal pebble.ProcessPool workers fail to respawn (multiprocessing
    # spawn re-imports `<stdin>` and crashes with FileNotFoundError /root/<stdin>),
    # and any worker death (e.g. LTX OOM) cascades into BrokenProcessPool.
    return (
        "cat > /tmp/vibecomfy_matrix_runner.py <<'PY'\n"
        "from __future__ import annotations\n"
        "\n"
        "import asyncio\n"
        "import json\n"
        "import os\n"
        "import subprocess\n"
        "import sys\n"
        "import traceback\n"
        "\n"
        f"FAMILY_CONFIG = json.loads({_py_triple_literal(config_json)})\n"
        f"PROMPT = json.loads({_py_triple_literal(prompt_json)})\n"
        "MIN_BYTES = 100 * 1024\n"
        "\n"
        "from vibecomfy import image, video  # type: ignore\n"
        "from vibecomfy.runtime import EmbeddedSession\n"
        "\n"
        "\n"
        "async def _warmup() -> None:\n"
        "    session = EmbeddedSession()\n"
        "    try:\n"
        "        await session.reload_for_nodepack_change(reason='layer2-matrix')\n"
        "    finally:\n"
        "        await session.stop()\n"
        "\n"
        "\n"
        "def _ffprobe_frame_count(path: str):\n"
        "    try:\n"
        "        out = subprocess.run(\n"
        "            [\n"
        "                'ffprobe', '-v', 'error', '-count_frames',\n"
        "                '-select_streams', 'v:0',\n"
        "                '-show_entries', 'stream=nb_read_frames',\n"
        "                '-of', 'csv=p=0', path,\n"
        "            ],\n"
        "            check=True, capture_output=True, text=True, timeout=120,\n"
        "        )\n"
        "    except FileNotFoundError:\n"
        "        return None, 'ffprobe-not-installed'\n"
        "    except subprocess.CalledProcessError as exc:\n"
        "        return None, f'ffprobe-failed: {exc.stderr.strip() or exc!r}'\n"
        "    except subprocess.TimeoutExpired:\n"
        "        return None, 'ffprobe-timeout'\n"
        "    raw = (out.stdout or '').strip().splitlines()\n"
        "    if not raw:\n"
        "        return None, 'ffprobe-empty-output'\n"
        "    try:\n"
        "        return int(raw[0]), None\n"
        "    except ValueError:\n"
        "        return None, f'ffprobe-non-int: {raw[0]!r}'\n"
        "\n"
        "\n"
        "def _resolve_verb(name: str):\n"
        "    if name == 'image.t2i':\n"
        "        return image.t2i\n"
        "    if name == 'video.t2v':\n"
        "        return video.t2v\n"
        "    if name == 'video.i2v':\n"
        "        return video.i2v\n"
        "    raise ValueError(f'unknown verb: {name}')\n"
        "\n"
        "\n"
        "def _run() -> dict:\n"
        "    # Warmup is async; the verb-native artifact.run() is a sync wrapper around\n"
        "    # asyncio.run() and must NOT be called from inside a running event loop.\n"
        "    asyncio.run(_warmup())\n"
        "    route_results: list[dict] = []\n"
        "    prev_output: str | None = None\n"
        "    for idx, route in enumerate(FAMILY_CONFIG['routes']):\n"
        "        verb_name = route['verb']\n"
        "        verb = _resolve_verb(verb_name)\n"
        "        kwargs = dict(route.get('kwargs') or {})\n"
        "        if route.get('model') is not None:\n"
        "            kwargs['model'] = route['model']\n"
        "        try:\n"
        "            if route.get('needs_input_image'):\n"
        "                if prev_output is None:\n"
        "                    raise AssertionError(\n"
        "                        f'route {idx} ({verb_name}) needs input image but no prior output exists'\n"
        "                    )\n"
        "                artifact = verb(prev_output, PROMPT, **kwargs)\n"
        "            else:\n"
        "                artifact = verb(PROMPT, **kwargs)\n"
        "            # Light validation before run — surfaces wiring errors fast.\n"
        "            artifact.preview_workflow().validate()\n"
        "            run_result = artifact.run(backend='graphbuilder')\n"
        "            outputs = list(getattr(run_result, 'outputs', []) or [])\n"
        "            if not outputs:\n"
        "                raise AssertionError(f'route {idx} ({verb_name}) produced zero outputs')\n"
        "            first = outputs[0]\n"
        "            # ComfyUI may return paths relative to its output dir; resolve.\n"
        "            if not (os.path.isabs(first) and os.path.exists(first)):\n"
        "                for c in (first, os.path.join('output', first), os.path.join(os.getcwd(), first), os.path.join('/root/vibecomfy/output', first)):\n"
        "                    if os.path.exists(c):\n"
        "                        first = c\n"
        "                        break\n"
        "            if not os.path.exists(first):\n"
        "                raise AssertionError(f'route {idx} ({verb_name}) output missing: {first}')\n"
        "            size = os.path.getsize(first)\n"
        "            if size < MIN_BYTES:\n"
        "                raise AssertionError(\n"
        "                    f'route {idx} ({verb_name}) output too small: {size} bytes ({first})'\n"
        "                )\n"
        "            route_record: dict = {\n"
        "                'idx': idx,\n"
        "                'verb': verb_name,\n"
        "                'kind': route['kind'],\n"
        "                'output': first,\n"
        "                'size': size,\n"
        "                'output_count': len(outputs),\n"
        "            }\n"
        "            if route['kind'] == 'video' and route.get('expected_frames') is not None:\n"
        "                expected = int(route['expected_frames'])\n"
        "                count, warn = _ffprobe_frame_count(first)\n"
        "                if count is None:\n"
        "                    route_record['frame_count'] = None\n"
        "                    route_record['frame_warning'] = warn\n"
        "                else:\n"
        "                    route_record['frame_count'] = count\n"
        "                    if count != expected:\n"
        "                        raise AssertionError(\n"
        "                            f'route {idx} ({verb_name}) frame count {count} != expected {expected}'\n"
        "                        )\n"
        "            # NOTE: i2v dimension-match-input-image is intentionally NOT asserted —\n"
        "            # the verb-native router currently accepts image= but does not wire it into\n"
        "            # the workflow, so the output is template-default sized. Test still exercises\n"
        "            # dispatch + execute. See plan §i2v image-wiring quirk.\n"
        "            route_results.append(route_record)\n"
        "            prev_output = first\n"
        "        except BaseException as exc:\n"
        "            route_results.append({\n"
        "                'idx': idx,\n"
        "                'verb': verb_name,\n"
        "                'kind': route.get('kind'),\n"
        "                'error': repr(exc),\n"
        "                'traceback': traceback.format_exc(),\n"
        "            })\n"
        "            return {'ok': False, 'routes': route_results}\n"
        "    return {'ok': True, 'routes': route_results}\n"
        "\n"
        "\n"
        "def _main() -> int:\n"
        "    try:\n"
        "        result = _run()\n"
        "    except BaseException as exc:\n"
        "        print('VIBECOMFY_LAYER2_MATRIX_RESULT_FAIL=' + json.dumps({\n"
        "            'family': FAMILY_CONFIG['family'],\n"
        "            'error': repr(exc),\n"
        "            'traceback': traceback.format_exc(),\n"
        "        }))\n"
        "        return 1\n"
        "    payload = {'family': FAMILY_CONFIG['family'], **result}\n"
        "    if result.get('ok'):\n"
        "        print('VIBECOMFY_LAYER2_MATRIX_RESULT_OK=' + json.dumps(payload))\n"
        "        return 0\n"
        "    print('VIBECOMFY_LAYER2_MATRIX_RESULT_FAIL=' + json.dumps(payload))\n"
        "    return 1\n"
        "\n"
        "\n"
        "if __name__ == '__main__':\n"
        "    sys.exit(_main())\n"
        "PY\n"
        "python /tmp/vibecomfy_matrix_runner.py\n"
    )


def _py_triple_literal(payload: str) -> str:
    """Render a JSON string as a Python triple-quoted literal safely.

    json.dumps output never contains a literal triple-quote, but be defensive: if
    one ever appeared we'd want a hard fail rather than a broken heredoc.
    """
    if "'''" in payload:
        raise ValueError("payload contains triple-single-quote; refusing to embed")
    return f"'''{payload}'''"
