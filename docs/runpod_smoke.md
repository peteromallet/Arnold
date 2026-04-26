# RunPod P1 Smoke Test

The P1 RunPod smoke test is opt-in because it provisions a real GPU pod.
It mirrors the tracked `image/z_image` ready template using the P1 typed-handle
authoring path, calls `EmbeddedSession.reload_for_nodepack_change()`, then runs
the workflow through `EmbeddedSession.run()`.

Run it explicitly:

```bash
pytest --runpod -m runpod tests/smoke/test_p1_runpod.py
```

Required environment:

- `RUNPOD_API_KEY`: RunPod API key with permission to create and terminate pods.
- `VIBECOMFY_RUNPOD_LIFECYCLE_ROOT` (optional): local source root for `runpod_lifecycle` when that package is not installed in the test environment.

Optional environment:

- `RUNPOD_GPU_TYPE`: overrides the default cheap GPU class. The scaffold defaults to an RTX 4090-class pod.
- `VIBECOMFY_RUNPOD_REPO_URL`: git URL installed on the pod. Defaults to the local `origin` URL.
- `VIBECOMFY_RUNPOD_GIT_REF`: branch, tag, or commit installed on the pod. Defaults to the current branch when available, then current commit.

Expected cost and time:

- Wall clock: about 5-10 minutes.
- Cost: about $0.05-$0.20 per run, depending on pod availability, image pull time, and selected GPU.

Safety contract:

- The test tears down the pod in a `finally` block on success and failure.
- It is marked `runpod` and is deselected from normal `pytest` and CI unless `--runpod` is supplied.
- Do not run it from broad local validation commands unless you intend to spend RunPod budget.
