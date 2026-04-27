# RunPod Smoke Tests

vibecomfy ships an opt-in pytest harness that provisions real RunPod GPU pods to
exercise GPU code paths end-to-end. Two markers gate these tests: `runpod`
(routine, ~$1) and `runpod_full` (pre-release, ~$5-10). They are deselected by
default and require explicit CLI flags (`--runpod`, `--runpod-full`) because
they cost real money and take real time.

## Quick reference

| File | Marker | Pods | GPU | Cost | Wall clock | Cadence |
|---|---|---|---|---|---|---|
| `tests/smoke/test_p1_runpod.py` | `runpod` | 1 | RTX 4090 | $0.05-$0.20 | 5-10 min | On P1 typed-handle changes |
| `tests/smoke/test_layer2_runpod_ops.py` | `runpod` | 1 | RTX 4090 | ~$1 | ~30 min | Per change to `vibecomfy/ops/`, `router.py`, or templates |
| `tests/smoke/test_layer2_runpod_dropped.py` | `runpod` | 1 | RTX 4090 | ~$1 | ~20 min | Once now, then quarterly |
| `tests/smoke/test_layer2_runpod_matrix.py` | `runpod_full` | 4 (parallel) | per-family | ~$5-10 | ~90 min | Pre-release |

## test_p1_runpod.py

Predates the verb-native API. Mirrors the tracked `image/z_image` ready
template using the P1 typed-handle authoring path, calls
`EmbeddedSession.reload_for_nodepack_change()`, then runs the workflow through
`EmbeddedSession.run()`. Kept because it exercises a different code path than
the layer-2 tests.

```bash
pytest --runpod -m runpod tests/smoke/test_p1_runpod.py
```

## test_layer2_runpod_ops.py (Phase 1)

Exercises all six verb-native routes (`image.t2i` x2, `video.t2v` x2,
`video.i2v` x2) on a single RTX 4090 pod at minimum-viable resolution. This is
the routine smoke test for the verb-native API.

```bash
pytest --runpod -m runpod tests/smoke/test_layer2_runpod_ops.py
```

## test_layer2_runpod_dropped.py (Phase 3)

Verifies the three templates that did not make it into the verb-native API
still execute via `load_workflow_any` + `run_embedded_sync`. Catches
regressions in the legacy embedded path.

```bash
pytest --runpod -m runpod tests/smoke/test_layer2_runpod_dropped.py
```

## test_layer2_runpod_matrix.py (Phase 2)

Production-resolution matrix across four parallel pods, one per family
(`z_image`, `flux_klein_4b`, `wan`, `ltx`). Run before a release.

```bash
pytest --runpod-full -m runpod_full tests/smoke/test_layer2_runpod_matrix.py
```

## Required environment

- `RUNPOD_API_KEY` — RunPod API key with permission to create and terminate pods.
- `VIBECOMFY_RUNPOD_LIFECYCLE_ROOT` (optional) — local source root for
  `runpod_lifecycle` when the package is not installed in the test environment.

## Optional environment

- `RUNPOD_GPU_TYPE` — overrides the default GPU class. Defaults to RTX 4090.
- `RUNPOD_GPU_TYPE_<FAMILY>` (Phase 2 only) — per-family override, e.g.
  `RUNPOD_GPU_TYPE_WAN=NVIDIA A40` to put `wan` on an A40 if it OOMs on a 4090.
  Falls back to `RUNPOD_GPU_TYPE` when unset.
- `VIBECOMFY_RUNPOD_REPO_URL` — git URL installed on the pod. Defaults to the
  local `origin` URL.
- `VIBECOMFY_RUNPOD_GIT_REF` — branch, tag, or commit installed on the pod.
  Defaults to the current branch when available, then the current commit.

## Pod-cost guardrails

Every test:

- Tears down the pod in a `try`/`finally` block on success and failure.
- Wraps the pod-bound work in `asyncio.wait_for` with a 60-minute cap.
- Names pods `vibecomfy-layer2-{phase}-{family}-{epoch}` so orphans are
  greppable in the RunPod console.
- Logs `pod.id` at launch and at teardown.

If a test crashes hard enough to skip the `finally` (e.g. SIGKILL, laptop lid
shut), hunt orphans using the `runpod_lifecycle` CLI in the
[runpod-lifecycle](https://github.com/) repo:

```bash
python -m runpod_lifecycle list
python -m runpod_lifecycle terminate <pod-id>
```

## Sequencing

- **Phase 1** (`test_layer2_runpod_ops.py`) — run on every change to
  `vibecomfy/ops/`, `router.py`, or templates touched by the verb-native API.
- **Phase 3** (`test_layer2_runpod_dropped.py`) — run once now, then quarterly,
  or whenever the legacy embedded path changes.
- **Phase 2** (`test_layer2_runpod_matrix.py`) — run before a release.

## What this harness does NOT do

- Does not test schema validation.
- Does not test the ~40 unrefactored ready_templates — those are covered by the
  legacy `tests/test_runpod_matrix.py` corpus sweep.
- Does not grade output quality. Tests assert that workflows run to completion
  and produce outputs of the expected shape; they do not score the pixels.
