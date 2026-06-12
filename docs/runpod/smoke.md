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
| `tests/smoke/test_layer2_runpod_ops.py` | `runpod` | 1 | RTX 4090 | ~$1 | ~30 min | Per change to `vibecomfy/ops/`, `vibecomfy/router/`, or templates |
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
  `vibecomfy/ops/`, `vibecomfy/router/`, or templates touched by the
  verb-native API.
- **Phase 3** (`test_layer2_runpod_dropped.py`) — run once now, then quarterly,
  or whenever the legacy embedded path changes.
- **Phase 2** (`test_layer2_runpod_matrix.py`) — run before a release.

## What this harness does NOT do

- Does not test schema validation.
- Does not test the ~40 unrefactored ready_templates — those are covered by the
  legacy `tests/test_runpod_matrix.py` corpus sweep.
- Does not grade output quality. Tests assert that workflows run to completion
  and produce outputs of the expected shape; they do not score the pixels.

## Known issues and pre-existing failure modes

Discovered/triaged across 8 Tier 2 matrix attempts during the
ready_templates → real-Python conversion work (2026-04-27, branch
`codex/composition-ready-templates`). Some are fixed in tree; others are
genuine pre-existing failures with separate scope.

### Fixed in this branch

| ID | Symptom | Root cause | Fix commit |
|---|---|---|---|
| `RP-1` | `BrokenProcessPool: All workers expired` followed by `FileNotFoundError: '/root/<stdin>'` whenever LTX (or any high-VRAM workflow) tried to respawn a worker | Test bodies were piped via `python - <<'PY'` heredoc. ComfyUI runs workflows under `pebble.ProcessPool`; when a worker dies and respawns, `multiprocessing.spawn` re-imports the entry script — but the entry was `<stdin>`. | `4552b81` — write the body to `/tmp/vibecomfy_matrix_runner.py` and exec it as a real path |
| `RP-2` | `LaunchFailure: Something went wrong. Please try again later or contact support.` on ~50 % of pod create attempts | Transient RunPod 4090 capacity. No retry layer in the lifecycle library. | `89cab91` — `launch_with_retry(..., retries=4)` with 30/60/90s backoff in `_runpod_helpers.py` |
| `RP-3` | `git clone: tmp_pack_*: No such file or directory` / `unable to read sha1 file` / `unable to write new index file` | The `/workspace` network volume is shared across all matrix pods; prior failed installs leave partial state, full transfer races on filesystem. | `89cab91` — clone with `--depth=1 --shallow-submodules` plus 3× retries on `install_current_branch`. Mostly mitigated; for the residual cases see `RP-5`. |
| `RP-4` | `wan` KSampler rejected with `denoise: 'simple' could not convert to FLOAT`, `steps: 'randomize' could not convert to INT`, `sampler_name: 6 not in list`, `scheduler: 'uni_pc' not in list` — every kwarg shifted by one position | UI `widgets_values` puts `control_after_generate` at index 1 of KSampler / index 2 of KSamplerAdvanced. It is **UI-only**, not in `INPUT_TYPES`, and ComfyUI's API rejects it. The previous schema in `tools/_widget_schema.py` skipped it entirely, so widget_1='randomize' got emitted as `steps='randomize'`, etc. Local roundtrip-equality didn't catch it because both sides shifted the same way. | `bb38594` — `None` sentinel in `WIDGET_SCHEMA` for UI-only positions; emitter and `_compile_equivalence` both drop None-resolved widgets. All 8 AUTHORED templates re-emitted from source JSON; 9 snapshot triples regenerated. |
| `RP-5` | `rm: cannot remove '/workspace/vibecomfy/vendor/ComfyUI/...': Directory not empty` / `fatal: cannot copy /usr/share/git-core/templates/hooks/...` even with retries | The `/workspace` mount is the shared `Peter` network volume; corruption from prior pods persists across launches and defeats `rm -rf` (sym/dangling `.git/hooks`, partial submodule trees). | `58988a6` — install to `/root/vibecomfy` (container-local, fresh per pod boot) instead of `/workspace/vibecomfy` |
| `RP-6` | `RuntimeError: An attempt has been made to start a new process before the current process has finished its bootstrapping phase. … `if __name__ == '__main__':` … freeze_support()` | After `RP-1` we wrote the body to `/tmp/runner.py` but kept `sys.exit(_main())` at module top-level. When pebble respawned a worker, it re-imported the script and recursively re-ran `_main()`. | `0b7db16` — wrap entry in `if __name__ == '__main__':` |
| `RP-7` | `wan` matrix run reported `route 0 (video.t2v) output missing: ComfyUI_00001_.mp4` even when the workflow produced output | `outputs[0]` from `run_embedded_sync` is a relative path. Matrix runner used bare `os.path.exists`; no resolution against ComfyUI's output dir. (Same shape as `test_z_image_only.py:_resolve_path`.) | `0b7db16` — resolve against `output/`, cwd, and `/root/vibecomfy/output/` before declaring missing |
| `RP-9` | `test_layer2_runpod_matrix.py::ltx`, `test_layer2_runpod_ops.py::ltx` routes — `ValueError: missing_node_type: Node 'LowVRAMCheckpointLoader' not found. The custom node may not be installed.` | Patches like `ltx_lowvram` declare custom-node deps via `ensure_custom_nodes(workflow, ...)` into `workflow.requirements.custom_nodes`, but the pod bootstrap (`install_current_branch`) never consumed those declarations. ComfyUI then loaded without `ComfyUI-LTXVideo` / `ComfyUI-KJNodes`. | `505f5eb` — new `ensure_node_packs(pod, templates)` helper in `tests/smoke/_runpod_helpers.py`; called by all four smoke tests after `install_current_branch`. Loads each declared template, runs `find_applicable` + `patch.apply` to materialise deps, then `install_pack(name=...)` (clone path; cm-cli bypassed because pip-installed ComfyUI has no `COMFYUI_PATH` checkout) into `/root/vibecomfy/custom_nodes/`. Validated on a 4090: KJNodes + LTXVideo cloned cleanly. |

### Still open (pre-existing, not converter-related)

| ID | Test path it blocks | Symptom | Root cause | Scope |
|---|---|---|---|---|
| `RP-8` | `test_layer2_runpod_matrix.py::wan` family | Workflow validates clean (kwargs all valid post-`RP-4`), model loads, then `WATCHDOG diagnosis=crashed last_node=- elapsed_in_node=- vram_free=-` ~35 s after model load. No Python traceback, no comfy log line for the failure. Reproduces deterministically on attempts 7 and 8. | Pod-side runtime crash. Production-res wan_t2v is 832×480×81 frames on a 1.3 B-param model — likely VRAM exhaustion, low-step-count sampler instability, or a comfy worker segfault. The brief flags this category as "GPU-only KSampler convergence behavior at low step counts" — pod-only, not catchable locally. | Out of scope for the converter; needs a separate investigation pass with `VIBECOMFY_WATCHDOG=1` log capture or a smaller resolution to triangulate. |
| `RP-10` | `test_layer2_runpod_ops.py::z_image` route | `image.t2i("a fox", width=512, height=512, steps=4) → art.run(backend="graphbuilder")` crashes silently on the pod ~10 s after model load (`watchdog: diagnosis=crashed, last_node=-`). The same workflow via `load_workflow_any("image/z_image") + run_embedded_sync(wf, backend="graphbuilder")` runs cleanly to completion in ~268 s (proven in `test_z_image_only.py`). | The verb-native dispatch path mutates the workflow via `_set_prompt_preserving_registration` + `set_steps(4)`. Locally the compiled API dict is correct (verified). Pod-side, something about the mutated workflow at very low step counts segfaults the comfy worker. Matrix uses `steps=25` and works, so this only affects the cheap `_ops` smoke test. | Pre-existing verb-native path bug. Out of scope here; revisit when MP-6 schema validation lands. |
| `RP-11` | `test_layer2_runpod_dropped.py::flux2_klein_9b_gguf_t2i` | `value_not_in_list: unet_name 'flux-2-klein-base-9b-fp8.safetensors' not in (list of length 194)`, preceded by `httpx → anyio: ValueError: second argument (exceptions) must be a non-empty sequence` from anyio's `ExceptionGroup` constructor | The model isn't pre-cached on the pod and HF auto-download fails: anyio's TCP-connect chain raises `ExceptionGroup` with an empty list under Python 3.11. ComfyUI then validates the dropdown and rejects the missing model. | Pre-existing infra. Workarounds: pre-stage the model on the network volume, or pin a different anyio. |
| `RP-12` | All matrix families (intermittent) | Pod creation hits `LaunchFailure: Something went wrong. Please try again later or contact support.` for `gpu_type=NVIDIA GeForce RTX 4090, ram=32GB, storage=Peter` | RunPod 4090 capacity windows are thin and bursty. | External; `RP-2` retries handle most cases. |

### Tier 2 release-gate status (matrix attempt 8, post-fixes)

| Family | Result | Notes |
|---|---|---|
| `z_image` | ✅ pass | 1024² @ steps=25 (matrix default), template kept manual (`# vibecomfy: manual` marker) |
| `flux_klein_4b` | ✅ pass | 1024², converted template — first end-to-end converter validation on production resolution |
| `wan` | ❌ blocked by `RP-8` | Workflow shape correct post-`RP-4` fix; pod runtime crash |
| `ltx` | ❌ was blocked by `RP-9` | Custom-node-pack auto-install now wired in (`ensure_node_packs`); next matrix run validates end-to-end |

The release gate is partially green: the converter is validated end-to-end for both image families. Video families remain blocked by pre-existing pod-runtime / custom-pack issues that have separate work streams.
