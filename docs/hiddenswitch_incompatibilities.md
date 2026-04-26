# HiddenSwitch Incompatibilities

Running log of incompatibilities observed while validating VibeComfy workflows against the HiddenSwitch ComfyUI pip fork.

Current runtime under test:

```text
comfyui==0.18.2
hiddenswitch/ComfyUI commit c5ed940244b1373daf855c0adbf2f7fd6dec327a
RunPod RTX 4090 validation
```

## Runtime-Green Evidence So Far

These are the workflows that have generated real media through both baseline `comfyui run-workflow` and VibeComfy converted scratchpad execution on RunPod.

| Family | Workflow | Media | Artifact | Baseline | VibeComfy | Notes |
| --- | --- | --- | --- | ---: | ---: | --- |
| Z-Image | `z_image` | image | `out/runpod_artifacts/1777175257` | 121s | 81s | Official Comfy template path. |
| Flux Klein 4B | `flux2_klein_4b_t2i` | image | `out/runpod_artifacts/1777175257` | 100s | 80s | Official Comfy template path. |
| Flux Klein 4B | `flux2_klein_4b_image_edit_distilled` | image | `out/runpod_artifacts/1777175257` | 90s | 80s | Official edit template path. |
| Flux Klein 9B GGUF | `flux2_klein_9b_gguf_t2i` | image | `out/runpod_artifacts/1777175257` | 90s | 90s | Public GGUF path through ComfyUI-GGUF. |
| WanVideoWrapper | `wanvideo_wrapper_21_14b_t2v` | video | `out/runpod_artifacts/1777186120` | 140s | 140s | Kijai wrapper, source-authored prompt/sampler. |
| WanVideoWrapper | `wanvideo_wrapper_21_14b_i2v` | video | `out/runpod_artifacts/1777186120` | 171s | 160s | Kijai wrapper, image-to-video. |
| WanVideoWrapper | `wanvideo_wrapper_21_14b_flf2v` | video | `out/runpod_artifacts/1777186120` | 190s | 180s | First/last-frame video. |
| WanVideoWrapper | `wanvideo_wrapper_22_5b_i2v_controlnet` | video | `out/runpod_artifacts/1777186120` | 131s | 130s | 5B I2V ControlNet. |
| WanVideoWrapper | `wanvideo_wrapper_13b_control_lora` | video | `out/runpod_artifacts/1777186120` | 90s | 80s | Control LoRA. |
| WanVideoWrapper | `wanvideo_wrapper_21_14b_v2v_infinitetalk` | video | `out/runpod_artifacts/1777191469` | 220s | 210s | Focused InfiniteTalk rerun after initial failure. |
| LTX 2.3 | `ltx2_3_t2v` | video | earlier focused run | 265s | n/a | Green T2V smoke from earlier focused run; keep rerunning for complete artifact parity. |
| LTX 2.3 | `ltx2_3_i2v` | video | `out/runpod_artifacts/1777195666` | 295s | 355s | Official/Lightricks path. |
| LTX 2.3 | `ltx2_3_lightricks_iclora_motion_track` | video | `out/runpod_artifacts/1777195666` | 95s | 95s | Official IC-LoRA motion-track. |
| LTX 2.3 | `ltx2_3_lightricks_iclora_union_control` | video | `out/runpod_artifacts/1777195666` | 350s | 362s | Official IC-LoRA union control. |
| ACE Step 1.5 | `ace_step_1_5_t2a_song` | audio | `out/runpod_artifacts/1777204423` | 110s | 110s | Official subgraph materialized to API-shaped audio graph. |

Known green count so far:

- Images/edits: 4.
- Wan video: 6.
- LTX video: 4.
- Audio: 1.

## Status Legend

- `Open`: still blocks at least one runtime-green workflow.
- `Mitigated`: VibeComfy has a workaround, but the underlying fork mismatch remains.
- `Fixed (local)`: a previously-mitigated VibeComfy-side bug has been fixed in this repository; entry retained for historical context.
- `Fixed upstream required`: should ideally be fixed in HiddenSwitch or the relevant custom-node package.
- `Watch`: passed current smoke tests, but fragile enough to keep in the compatibility ledger.

## Root Cause Taxonomy

Every entry must declare at least one root cause label. Multiple labels are allowed when a failure has more than one cause; list them comma-separated.

- `local_bug`: bug in VibeComfy's materializer, harness, converter, or override logic. The fork is innocent.
- `fixture_gap`: synthetic test fixture (silent video, missing audio track, placeholder image) does not match what the workflow actually expects. Real input would not fail.
- `runtime_observability`: the failure is opaque because we lack diagnostics (no per-node progress, no VRAM sampling, no watchdog), not because the runtime itself is wrong.
- `model_layout`: model file exists but is not at the path or under the name the node pack expects. Includes alias, directory convention, and registry-discovery mismatches.
- `fork_behavior`: HiddenSwitch's pip fork diverges from upstream ComfyUI (lagging node defs, renamed inputs, different CLI semantics, embedded-execution context gaps) in a way that affects this workflow.
- `custom_node_contract`: a custom node pack (KJNodes, WanVideoWrapper, Lightricks, ComfyUI-GGUF, etc.) has an internal contract — declared schema, expected object attributes, server-context assumptions — that breaks under our usage.

## Runtime Green With Mitigations

### ACE Step audio prompt/runtime path

Status: `Mitigated`

Root cause: `local_bug, fork_behavior`

Affected workflows:

- `ace_step_1_5_t2a_song`

Observed failures:

- Generic `comfyui run-workflow --prompt ...` failed because HiddenSwitch prompt replacement could not find a positive image text encoder in an audio workflow.
- Materialized ACE subgraph initially omitted required `TextEncodeAceStepAudio1.5` API inputs: `top_p`, `min_p`, `top_k`, `temperature`, and `bpm`.
- UI widget-position mapping was fragile; after primitive-link replacement it sent `bpm=2`, which violated the node minimum of `10`.

Current VibeComfy mitigation:

- Audio workflows skip generic `--prompt` override and keep source-authored prompt wiring.
- ACE smoke materialization now writes explicit API fields for `bpm`, sampling controls, seed, duration, and cfg rather than trusting widget positions.

Validation evidence:

- RunPod artifact: `out/runpod_artifacts/1777204423`.
- Baseline `comfyui run-workflow`: `ok`, `110s`, MP3 output.
- VibeComfy converted scratchpad: `ok`, `110s`, MP3 output.
- Output files:
  - `out/corpus_matrix/comfyui/ace_step_1_5_t2a_song/audio/vibecomfy_ace_step_smoke_00001_.mp3`
  - `output/audio/vibecomfy_ace_step_smoke_00001_.mp3`

Remaining structural follow-up:

- Add doctor rules so future audio/custom-text workflows do not rely on image-oriented generic prompt override logic.

## Open / Active

### LTX Runexx 22B runtime path

Status: `Open`

Root cause: `custom_node_contract, fork_behavior`

Affected workflows:

- `ltx2_3_runexx_first_last_frame`
- `ltx2_3_runexx_video_to_video_extend`
- other Runexx community 22B workflows when promoted from supplemental to runtime-gated

Observed failures:

- Several community graphs depend on node packs that are not present by default in the HiddenSwitch pip environment.
- After installing the node packs and normalizing model names, the workflows still hit runtime incompatibilities or stalls under the smoke budget.
- `LTXVLatentUpsampler` path hit a KJNodes/HiddenSwitch object mismatch: `LatentUpscaleModelManageable` missing `model_mmap_residency`.

Current VibeComfy mitigation:

- Use official/Lightricks LTX workflows as runtime-green coverage.
- Convert Runexx workflows into ready templates but do not claim runtime-green until the fork mismatch is resolved.
- Bypass `LTXVLatentUpsampler` in smoke runs and remove unreferenced latent-upscale loader nodes.

Candidate root fixes:

- Patch or pin a KJNodes version whose latent upscaler object contract matches HiddenSwitch.
- Add a doctor check that flags this exact class/attribute mismatch before execution.
- Keep community 22B workflows behind a larger timeout and stronger model-cache policy once the object mismatch is gone.

### LTX Runexx audio extraction and audio-shape assumptions

Status: `Mitigated`

Root cause: `fixture_gap`

Affected workflows:

- `ltx2_3_runexx_video_to_video_extend`
- other Runexx custom-audio / lip-sync / talking-avatar graphs when promoted to runtime-gated

Observed failures:

- Some workflows extract audio from smoke guide videos. Our generated guide videos used to be silent, so audio-processing nodes received empty or unexpected waveform structures.
- WanVideoWrapper `NormalizeAudio` has been observed failing on audio tensor shape assumptions in one LTX community path.

Current VibeComfy mitigation:

- The smoke guide videos `ltx_smoke_guide.mp4`, `wolf_interpolated.mp4`, `bubble.mp4`, and `10.mp4` are now committed under `workflow_corpus/input/` with a real (non-silent) AAC audio stream muxed in (16kHz mono, sourced from `speech_smoke.wav`). Audio-extraction nodes therefore receive a non-empty waveform with realistic speech content rather than empty/DC tensors.
- A real-speech `workflow_corpus/input/speech_smoke.wav` (~94KB, mono 16kHz, ~2.94s) is committed and used both as the muxed audio in the guide videos and as the target of `LoadAudio("speech_smoke.wav")` injections.
- Bootstrap and fallback are unified in `vibecomfy/fixtures.py`. The matrix script calls `python -m vibecomfy.fixtures copy --target input`, which prefers committed assets and falls back to a synthetic generator (sine-wave WAV + audio-bearing H.264 videos) only when the committed assets are missing or when `VIBECOMFY_FIXTURES_REGENERATE=1` is set.
- For some LTX paths, replace audio extracted from video with synthetic `LoadAudio("speech_smoke.wav")` (materializer + matrix-remote workaround retained as a defensive belt-and-braces).
- See `workflow_corpus/input/FIXTURES.md` for source / license / format of each smoke fixture.

Remaining gap:

- Workflows that require specific speech *content* (talking-head / lip-sync graphs that need phoneme-level or VAD-aligned input, music or instrumental audio for ACE-style paths, multi-speaker mixes, etc.) are still unverified with these smoke fixtures. They will produce non-empty tensors but the output quality is undefined. A per-workflow input-contract system is the next step.

Candidate root fixes:

- Add doctor detection for workflows that use video-audio extraction but whose test input lacks an audio stream (now low-priority since the standard fixtures all carry audio, but useful as a guard against regression).
- Define per-workflow input contracts so talking-head and music-conditioned workflows can declare a more specific fixture instead of falling back to the generic `speech_smoke.wav`.

### Long-running LTX community graphs do not fail cleanly

Status: `Open`

Root cause: `runtime_observability`

Affected workflows:

- `ltx2_3_runexx_first_last_frame`
- `ltx2_3_runexx_video_to_video_extend`

Observed failures:

- Several attempts progressed past validation and then failed or stalled after roughly 280-351 seconds.
- The failure snippets were inside sampler/execution processing rather than a clear missing-node or missing-model error.

Current VibeComfy mitigation:

- Keep smoke budget bounded.
- Preserve downloaded logs in `out/runpod_artifacts/<run>/`.
- Prefer smaller official/Lightricks coverage while the community graph runtime path is unstable.

Candidate root fixes:

- Split cold install/model staging time from actual execution time so bottlenecks are visible.
- Add GPU/VRAM sampling during each run.
- Add an execution watchdog that records current node id, class type, VRAM, and last progress event before timeout.

## Mitigated

### Generic prompt and step overrides assume mainline image nodes

Status: `Fixed (local)`

Root cause: `local_bug`

Affected families:

- WanVideoWrapper
- ACE Step audio
- Some LTX custom-node graphs

Observed failure:

- HiddenSwitch CLI overrides such as `--prompt` and `--steps` are convenient for mainline image workflows, but they are not general graph transforms. They can fail or mutate the wrong node family when the workflow uses custom prompt/sampler nodes.

VibeComfy fix (`vibecomfy run`):

- `vibecomfy.metadata._register_common_inputs` now gates `workflow.inputs["prompt"]` and `workflow.inputs["steps"]` registration on class-type allowlists (`PROMPT_NODE_CLASSES`, `STEPS_NODE_CLASSES`) instead of pure field-name matching. Custom-node text/sampler classes (WanVideoTextEncode, TextEncodeAceStepAudio1.5, WanVideoSampler, ...) are intentionally excluded.
- `vibecomfy.commands.run._cmd_run` now exits with a clear error when `--prompt`/`--steps` is supplied against a workflow whose nodes do not match the allowlist, naming the workflow, the offending flag, and pointing the user at either editing the source workflow directly or extending the allowlist.
- Set `VIBECOMFY_LEGACY_OVERRIDES=1` to restore the field-name-only registration as an emergency reversibility lever.
- `--seed` remains universal — `seed`/`noise_seed` are well-defined across families.
- The matrix workaround that stripped `--prompt`/`--steps` from the vibecomfy invocation in `scripts/runpod_corpus_matrix.py` has been removed; the HiddenSwitch baseline (`comfyui run-workflow`) keeps its strip because that path has no equivalent enforcement layer.

### UI JSON to API JSON link representation

Status: `Mitigated`

Root cause: `local_bug`

Observed failure:

- HiddenSwitch's UI-to-API workflow conversion expected Comfy UI link arrays. A materialized ACE subgraph with dict-shaped links failed in `_compress_graph_nodes` with `KeyError: 0`.

Current VibeComfy mitigation:

- Materialized official subgraphs must emit standard Comfy UI link arrays:

```text
[link_id, origin_id, origin_slot, target_id, target_slot, type]
```

Policy:

- Do not hand-roll partial UI JSON shapes. Either normalize to API JSON or emit complete Comfy UI link arrays.

### Preview nodes can assume a server context

Status: `Mitigated`

Root cause: `custom_node_contract, fork_behavior`

Affected families:

- WanVideoWrapper preview nodes
- KJNodes/LTX preview paths

Observed failure:

- Some preview nodes accessed `serv.last_node_id` during embedded or CLI execution, where the server context can be missing or incomplete.

Current VibeComfy mitigation:

- Patch preview nodes to tolerate missing server node id:

```python
node_id = serv.last_node_id or "0"
```

Policy:

- Smoke runs should disable preview output where possible.
- Doctor should warn when workflows contain server-context preview nodes in embedded/CLI execution mode.

### Custom-node discovery is not enough

Status: `Mitigated`

Root cause: `fork_behavior`

Observed failure:

- HiddenSwitch can report missing node classes only at validation/execution time. That is too late for a smooth corpus run.

Current VibeComfy mitigation:

- Matrix setup installs known custom-node packages for WanVideoWrapper, LTXVideo, KJNodes, VHS/video helpers, Easy-Use, rgthree, GGUF, and related dependencies.
- `vibecomfy sources sync` indexes official workflows, external workflows, and custom nodes before materialization.

Policy:

- Required workflows must declare their custom-node source in the corpus manifest or the matrix setup.
- Ready templates should carry custom-node metadata even when runtime validation is deferred.

### Model name and directory conventions differ across node packs

Status: `Mitigated`

Root cause: `model_layout`

Affected families:

- LTX/KJNodes/Lightricks
- WanVideoWrapper/Kijai
- Flux GGUF
- ACE Step

Observed failure:

- The same model can be expected under different names or subdirectories depending on the node pack. A model can be downloaded correctly but still be invisible to the workflow.

Current VibeComfy mitigation:

- The RunPod matrix materializes model aliases into the directories expected by each node pack.
- LTX model names from community workflows are normalized to staged Kijai/Lightricks filenames.
- Wan model names are normalized across Kijai and Comfy-Org repackaged paths.
- Flux Klein 9B GGUF is added to HiddenSwitch's known GGUF registry during the matrix run.

Policy:

- Required workflows should declare all accepted aliases centrally.
- Doctor should report both "missing file" and "file exists but not at the path this node expects".

## Watch Items

### HiddenSwitch pip fork and official Comfy template drift

Status: `Watch`

Root cause: `fork_behavior`

Issue:

- Official Comfy templates may assume current Comfy core node definitions, while HiddenSwitch pip may lag, rename inputs, or expose a different API contract.

Examples:

- ACE Step official subgraph required explicit materialization.
- ACE text node required fields not visible in the first shallow conversion pass.

Policy:

- Validate against `/object_info` or embedded node definitions, not just raw template shape.
- Add doctor output that names missing required node inputs and suggests the patch/materialization location.

### Model downloader known-model registry

Status: `Mitigated / Watch`

Root cause: `model_layout, fork_behavior`

Issue:

- HiddenSwitch model downloader does not know every model used by our corpus.

Current mitigation:

- The RunPod matrix stages required model files directly through Hugging Face downloads and aliases them into all paths expected by the relevant custom nodes.
- The matrix patches the known GGUF model registry for Flux Klein 9B.

Policy:

- Model staging should be explicit and reproducible. Do not rely on ad hoc downloader discovery for required ready templates.

## Compatibility Checklist

Before calling a workflow `runtime_green` on HiddenSwitch:

- Baseline `comfyui run-workflow` generated the expected media.
- VibeComfy generated the expected media from the converted scratchpad.
- Any generic CLI overrides are known to be compatible with that node family.
- Required custom nodes are installed or intentionally absent.
- Required model files are staged and size-checked.
- Preview/server-only nodes are disabled, removed, or patched.
- UI JSON subgraphs have been materialized into a full API-compatible graph.
- Failure logs are archived under `out/runpod_artifacts/<run>/`.

## Contributing Entries

To prevent this doc from degrading into an unindexed pile of tribal exceptions, every new entry — and every PR that adds one — must satisfy two requirements:

1. **Declare a root cause label** from the Root Cause Taxonomy above. Place a `Root cause:` line directly under the `Status:` line. Multiple labels are allowed when a failure has more than one cause; list them comma-separated. The label is what lets future readers (and tooling) tell `local_bug` from `fork_behavior` from `fixture_gap` without reading the full prose.

2. **Cross-reference prior entries.** In the PR description, link any existing entry whose mitigation, observed failure, or affected family overlaps with the new one — or explicitly state "no prior entry applies." This forces the author to read the doc before adding to it, which is the only mechanism keeping mitigations from being silently reinvented.

If a previously `Mitigated` entry's underlying cause is later resolved upstream (HiddenSwitch fix, custom-node fix, etc.), update the status and root cause rather than deleting the entry — the historical record of what failed and why is part of the doc's value.
