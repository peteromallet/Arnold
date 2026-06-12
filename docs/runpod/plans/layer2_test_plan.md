# RunPod Layer 2 Test Plan

Goal: verify that the verb-native API (`image.t2i`, `video.t2v`, `video.i2v` and friends) shipped by `finish-higher-abstraction` actually runs end-to-end on a real GPU, not just compiles cleanly. The acceptance criteria for that megaplan deliberately excluded RunPod execution (`tests/smoke/test_p1_runpod.py` was scaffolded but never run); this plan closes that gap.

## Why this matters

The 6 verb-native routes that ship in v1 are:

| Verb | Template | Patches |
|---|---|---|
| `image.t2i` (default / `z_image`) | `image/z_image` | – |
| `image.t2i('flux2_klein_4b')` | `image/flux2_klein_4b_t2i` | – |
| `video.t2v` (default / `wan`) | `video/wan_t2v` | – |
| `video.t2v('ltx')` | `video/ltx2_3_t2v` | `ltx_lowvram`, `resolution:384x256x9` |
| `video.i2v` (default / `wan`) | `video/wan_i2v` | – |
| `video.i2v('ltx')` | `video/ltx2_3_i2v` | `ltx_lowvram`, `resolution:384x256x9` |

Plus 3 templates that **shipped but are not exposed via the verb-native API** (the scope-reduction from gate v5 ESCALATE — see `megaplan debt list`):

| Template | Why dropped from verb-native |
|---|---|
| `image/flux2_klein_9b_gguf_t2i` | UUID-opaque subgraph with no prompt-bearing input |
| `edit/flux2_klein_4b_image_edit_distilled` | Multi-branch; no clear primary instruction input |
| `edit/qwen_image_edit` (instruction path) | UUID-opaque; image-only path works, instruction= path needs MP-6 schema validation |

The dropped templates remain reachable via `load_workflow_any('edit/qwen_image_edit')` + raw `VibeWorkflow` editing; we should verify they still execute on a real pod so the scope-reduction is conservative (templates work, only the verb-native dispatch is missing) rather than a regression.

## What we're already standing on

- `tests/smoke/test_p1_runpod.py` — provisions one pod via `runpod_lifecycle`, installs vibecomfy from current git ref, runs `EmbeddedSession.reload_for_nodepack_change()` + `EmbeddedSession.run()` against the typed-handle z_image build, asserts `result.outputs` non-empty, tears down.
- `runpod_lifecycle` package (in `~/Documents/reigh-workspace/runpod-lifecycle`) — `RunPodConfig.from_env`, `launch`, `pod.wait_ready`, `pod.exec_ssh`, `pod.terminate`. All async, all tested.
- `../smoke.md` — documents the opt-in pattern (`pytest --runpod -m runpod`), env var contract (`RUNPOD_API_KEY`, `RUNPOD_GPU_TYPE`, `VIBECOMFY_RUNPOD_REPO_URL`, `VIBECOMFY_RUNPOD_GIT_REF`), and cost/time budget (~$0.05-$0.20, 5-10 min).

The new tests should reuse this scaffolding, not reinvent it.

## Phases

Phases are ordered by cost and value. Run Phase 1 routinely (cheap, catches most regressions); run Phase 2 before releases; run Phase 3 once after this plan executes, then quarterly to detect node-pack drift.

### Phase 1 — Verb-native ops smoke (one pod, ~$1, ~30 min)

**Goal:** prove that all 6 verb-native routes can compile-and-run on a real GPU at minimum-viable resolution. Catches regressions in router → ops → workflow → execute wiring.

**File:** `tests/smoke/test_layer2_runpod_ops.py`, marked `@pytest.mark.runpod`.

**Pod:** one RTX 4090, 32GB RAM tier (matches the existing P1 smoke). Reuse `_install_current_branch` from `test_p1_runpod.py` — extract it to `tests/smoke/_runpod_helpers.py` so both tests can share without circular deps.

**Test body (executed remotely on the pod via one `exec_ssh`):**

```python
from vibecomfy import image, video
from vibecomfy.runtime import run_embedded_sync

# t2i — z_image (default + explicit)
art1 = image.t2i("a fox", width=512, height=512, steps=4)
assert art1.preview_workflow().validate().ok
res1 = art1.run()  # exercises lazy → execute path
assert res1.outputs

# t2i — flux2_klein_4b
art2 = image.t2i("a fox", model="flux2_klein_4b", width=512, height=512, steps=4)
res2 = art2.run()
assert res2.outputs

# t2v — wan (default)
art3 = video.t2v("a fox running", length=9, fps=8)
res3 = art3.run()
assert res3.outputs

# t2v — ltx
art4 = video.t2v("a fox running", model="ltx", length=9)  # patches set 384x256x9
res4 = art4.run()
assert res4.outputs

# i2v — wan
art5 = video.i2v(res2.outputs[0], "make it move", length=9, fps=8)
res5 = art5.run()
assert res5.outputs

# i2v — ltx
art6 = video.i2v(res2.outputs[0], "make it move", model="ltx", length=9)
res6 = art6.run()
assert res6.outputs
```

**Assertions:**
- Each `art.run()` returns a `RunResult` with non-empty `outputs`
- Each output path exists on the pod and has a non-zero size
- Total wall-clock under 25 min (model staging dominates)

**Out of scope:** quality (we don't grade outputs), per-route timing budgets (variance is high), re-using model loads across routes (let the runtime decide; warm-runtime is shipped).

**Cost estimate:** ~$0.50-$1.50 (RTX 4090 at ~$0.50/hr × ~30 min).

### Phase 2 — Production-resolution matrix (per-family pods, ~$5-10, ~90 min)

**Goal:** prove the verb-native routes work at the resolutions users will actually run. Run before tagging a release.

**File:** `tests/smoke/test_layer2_runpod_matrix.py`, marked `@pytest.mark.runpod_full`.

**Pod strategy:** one pod per model family — z_image, flux_klein_4b, wan, ltx — provisioned in parallel via `asyncio.gather`. Each pod runs only its family's routes.

| Pod | GPU | Routes | Resolution |
|---|---|---|---|
| z_image | RTX 4090 | `image.t2i('z_image')` | 1024×1024, 25 steps |
| flux_klein_4b | RTX 4090 | `image.t2i('flux2_klein_4b')` | 1024×1024, default steps |
| wan | RTX 4090 (or A40 if OOM) | `video.t2v('wan')`, `video.i2v('wan')` | 832×480, 81 frames |
| ltx | RTX 4090 | `video.t2v('ltx')`, `video.i2v('ltx')` | patches set 384×256, 9 frames |

**Assertions:**
- Each route produces a file ≥ 100KB (PNG/MP4 plausibility check)
- For video routes, ffprobe reports the expected frame count
- For i2v routes, the output dimensions match the input image (modulo patch overrides)

**Failure handling:** one pod failing must not block the others. Collect per-route results; assert all-pass at the end. Each pod has an independent `try/finally` for teardown.

**Cost estimate:** 4 pods × ~30 min each, parallel = ~$5-10 wall.

### Phase 3 — Scope-reduction conservatism check (one pod, ~$1, ~20 min)

**Goal:** prove the 3 dropped templates still execute end-to-end. Confirms `megaplan debt` items 1-12 are accurately scoped: the work is "expose via verb-native API," not "fix the templates."

**File:** `tests/smoke/test_layer2_runpod_dropped.py`, marked `@pytest.mark.runpod`.

**Pod:** one RTX 4090, same as Phase 1.

**Test body:**

```python
from vibecomfy import load_workflow_any
from vibecomfy.runtime import run_embedded_sync

for tid in (
    "image/flux2_klein_9b_gguf_t2i",
    "edit/flux2_klein_4b_image_edit_distilled",
    "edit/qwen_image_edit",
):
    wf = load_workflow_any(tid)
    assert wf.validate().ok, f"{tid} failed validation"
    result = run_embedded_sync(wf)
    assert result.outputs, f"{tid} produced no outputs"
```

**Why this matters:** if any of the 3 fails here, the scope reduction was wrong — those templates have a deeper problem than just "no prompt input." We'd file a real bug, not a "wait for MP-6" debt entry.

**Cost estimate:** ~$0.50-$1.

### Phase 4 — Documentation + CI integration

- Extend `../smoke.md` (or rename to `docs/runpod/tests.md`) to cover all three phases.
- Document the new pytest markers: `runpod` (Phase 1, 3 — cheap, opt-in), `runpod_full` (Phase 2 — release-gate).
- Add a `Makefile` or shell-script entrypoint: `make runpod-smoke` (Phase 1+3), `make runpod-full` (Phase 2).
- No CI changes by default — these are opt-in. The `RUNPOD_API_KEY` env var stays out of CI.

## Pod-cost guardrails

Every test in every phase MUST:
1. Wrap the entire body in `try/finally` and call `pod.terminate()` in finally.
2. Set a per-pod wall-clock cap (`asyncio.wait_for` around the test body, default 60 min). On timeout: terminate, fail loudly.
3. Assert `pod_id` is logged at provision time and at teardown so any orphan can be tracked manually via the RunPod console.
4. Use `runpod_lifecycle.RunPodConfig.from_env(...)` so `RUNPOD_GPU_TYPE` overrides flow through cleanly without code changes.

If a test panics before teardown: `runpod_lifecycle.cleanup_orphans` (or the equivalent — verify the API surface in `~/Documents/reigh-workspace/runpod-lifecycle/src/runpod_lifecycle/lifecycle.py`) should be invokable via `python -m runpod_lifecycle cleanup` to garbage-collect anything tagged `vibecomfy-layer2-*`. The provisioning name pattern: `vibecomfy-layer2-{phase}-{family}-{epoch}` so orphans are easy to grep.

## Acceptance

- `pytest --runpod -m runpod tests/smoke/test_layer2_runpod_ops.py tests/smoke/test_layer2_runpod_dropped.py` passes against a known-good vibecomfy commit. Total cost ~$2.
- `pytest --runpod -m runpod_full tests/smoke/test_layer2_runpod_matrix.py` passes. Total cost ~$5-10.
- `docs/runpod/tests.md` (or extended `../smoke.md`) documents both invocations + the cost/time budget.
- No orphan pods after a successful run (verified via the RunPod console).
- The shared `tests/smoke/_runpod_helpers.py` doesn't introduce circular imports with `test_p1_runpod.py`.

## What this plan does NOT do

- **Does not test schema validation** — that's MP-6, blocked.
- **Does not re-enable the 3 dropped templates in the verb-native API** — that's the *consequence* of MP-6 shipping, not this plan.
- **Does not test plugin discovery end-to-end on a pod** — discovery is filesystem-only and unit-testable without GPU; pod time is wasted on it.
- **Does not test the ~40 unrefactored ready_templates** — they're on the legacy `API_WORKFLOW` path; `tests/test_runpod_matrix.py` already covers a corpus sweep.
- **Does not grade output quality** — that's a separate eval pipeline (use `ultrareview` or a creative-mode megaplan if needed).

## Sequencing recommendation

1. **Implement Phase 1** first as a single Codex session (probably 1-2 hours of work). It's small enough not to need a megaplan.
2. **Run Phase 1** once. If green, the framework is verified end-to-end on real hardware — biggest unknown removed.
3. **Run Phase 3** next. If any of the 3 dropped templates fails, file a real bug and don't proceed to Phase 2 until resolved.
4. **Implement Phase 2** as a separate session (parallel pods + per-family logic is the bulk of the new code).
5. **Run Phase 2** once before the next release.

## Estimate summary

| Phase | Pod count | Wall clock | Cost | Cadence |
|---|---|---|---|---|
| 1 — ops smoke | 1 | ~30 min | ~$1 | Every change to `vibecomfy/ops/`, `vibecomfy/router/`, or templates |
| 2 — production matrix | 4 (parallel) | ~90 min | ~$5-10 | Pre-release |
| 3 — dropped-templates check | 1 | ~20 min | ~$1 | Once now, then quarterly |
