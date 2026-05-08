# Adding Templates And Models

This is the operating path for adding a new model family, workflow template, or custom-node workflow to VibeComfy. The goal is that a contributed template becomes a reusable Python ready template, declares its node/model requirements, and can be validated on RunPod without an agent hand-editing the machine.

## Target Shape

Every runnable template should move through this pipeline:

```text
raw Comfy workflow JSON
  -> workflow_corpus/... source file
  -> port check report
  -> port-converted Python scratchpad
  -> workflow_corpus/manifests/coverage.json entry
  -> scripts/materialize_ready_templates.py policy, if needed
  -> ready_templates/<media>/<id>.py
  -> local validate
  -> focused RunPod matrix scope
  -> checked-in artifact notes/docs if it exposes a new compatibility issue
```

Raw JSON remains import material. `ready_templates/` is the reusable VibeComfy surface. A ready template is only "ready" after it validates locally and has a plausible runtime path for its node packs and models.

Run the porting workbench before manual edits and before RunPod validation:

```bash
python -m vibecomfy.cli port check workflow_corpus/.../<id>.json --json
python -m vibecomfy.cli port convert workflow_corpus/.../<id>.json --out out/scratchpads/<id>.py --json
```

Use `--head-check-models` only when you intentionally want model URL HEAD checks. Normal `port check`, `doctor`, `validate`, `fetch`, and `run` paths stay offline by default.

## Checklist

1. Pick a stable template id.
2. Add the raw source workflow under `workflow_corpus/`.
3. Run `port check` and inspect the report before editing.
4. Add or update custom-node catalog entries.
5. Add model registry entries or workflow metadata for model staging.
6. Convert to a Python scratchpad, then decide whether a ready-template candidate is warranted.
7. Add a manifest row.
8. Add a materializer policy when the raw workflow is not directly smoke-runnable.
9. Regenerate ready templates.
10. Run local validation and tests.
11. Add or update a focused RunPod scope.
12. Run the focused RunPod matrix.
13. Document any new incompatibility or structural issue.

## 1. Template Id

Use lower snake case and encode the model family plus capability:

```text
qwen3_tts_voice_clone
flux2_klein_4b_image_edit_base
wanvideo_wrapper_21_14b_t2v
ltx2_3_lightricks_iclora_motion_track
```

The id should be stable because it becomes the manifest id, ready template filename, RunPod matrix row, artifact path, and CLI handle.

## 2. Source Workflow

Put imported source JSON where its ownership is clear:

```text
workflow_corpus/official/<media>/<id>.json
workflow_corpus/custom_nodes/<node_pack>/<source>/<id>.json
workflow_corpus/community/<source>/<id>.json
```

Prefer official Comfy templates when they exist. Use custom-node examples when the capability only exists there. Keep the raw JSON as close to upstream as possible; runtime-smoke edits belong in the materializer policy, not in the source file, unless the source is a small hand-authored API smoke fixture.

## 3. Custom Nodes

If the workflow uses custom classes, add them to `vibecomfy/node_packs.py`:

```python
CustomNodePack(
    name="ComfyUI-QwenTTS",
    repo="https://github.com/1038lab/ComfyUI-QwenTTS.git",
    classes=frozenset({"AILab_Qwen3TTSVoiceClone"}),
    pip_packages=("soundfile", "librosa", "accelerate"),
)
```

Then update `custom_nodes.lock` when the pack should be pinned. Pinning by commit is the default for runtime matrix work. Use floating latest only for exploration, not for a ready template.

Run:

```bash
uv run python -m vibecomfy.cli port check workflow_corpus/custom_nodes/.../<id>.json --json
uv run python -m vibecomfy.cli nodes install-plan workflow_corpus/custom_nodes/.../<id>.json
uv run python -m vibecomfy.cli doctor workflow_corpus/custom_nodes/.../<id>.json
```

## 4. Models

There are two model paths:

1. Workflow-embedded model URLs: keep them in workflow metadata. `scripts/materialize_ready_templates.py` extracts them into `READY_REQUIREMENTS["models"]`.
2. Node-pack-specific model layouts: add them to `vibecomfy/registry/models.yaml` so staging can hardlink or symlink the same downloaded asset into every path expected by each node pack.

Use the registry when a model has aliases, multiple target directories, custom-node naming conventions, or a minimum-size sanity check. The matrix should not hide model staging inside one-off shell snippets long term.

## 5. Manifest Row

Add a row to `workflow_corpus/manifests/coverage.json`:

```json
{
  "id": "qwen3_tts_voice_clone",
  "path": "workflow_corpus/custom_nodes/qwen_tts/1038lab/qwen3_tts_voice_clone.json",
  "source": "1038lab/ComfyUI-QwenTTS distilled API smoke template",
  "model_family": "qwen3-tts",
  "media": "audio",
  "task": "text_to_speech_voice_clone",
  "coverage_tier": "supplemental",
  "ready_template": true,
  "approach": "reference-audio voice cloning with a bundled smoke fixture",
  "runtime_note": "Uses workflow_corpus/input/speech_smoke.wav as the reference clip."
}
```

`coverage_tier: required` means it runs in the default matrix. `supplemental` needs an explicit scope unless it belongs to an existing scoped family. Use `ready_template: true` when it should materialize into checked-in Python.

## 6. Materializer Policy

Add a policy in `scripts/materialize_ready_templates.py` when a source workflow needs smoke-time normalization:

- reduce resolution, duration, frame count, steps, or batch size;
- replace gated/huge models with public smoke variants;
- normalize stale class names or widget fields;
- inject committed fixtures such as `speech_smoke.wav`;
- set deterministic seeds and output prefixes;
- add `runtime_variant`, `input_fixtures`, or `runtime_note` metadata.

Do not use the policy to paper over missing custom-node or model declarations. Those belong in `node_packs.py`, `custom_nodes.lock`, or `models.yaml`.

Regenerate:

```bash
uv run python scripts/materialize_ready_templates.py
```

## 7. Local Validation

First confirm the port report is clean enough to edit and convert:

```bash
uv run python -m vibecomfy.cli port check workflow_corpus/.../<id>.json --json
uv run python -m vibecomfy.cli port convert workflow_corpus/.../<id>.json --out out/scratchpads/<id>.py --json
```

Run validation on the generated ready template:

```bash
uv run python -m vibecomfy.cli validate ready_templates/<media>/<id>.py
```

Then run targeted tests:

```bash
uv run pytest -q tests/test_ready_templates.py tests/test_runpod_matrix.py tests/test_nodes_install.py tests/test_cli.py
```

For a new scope, add a unit test in `tests/test_runpod_matrix.py` so the selected rows cannot silently disappear.

## 8. RunPod Validation

Use focused scopes. Do not run the full matrix while iterating on one family:

```bash
uv run python -m vibecomfy.cli port check video/wanvideo_wrapper_22_wan_animate_preprocess_kijai --json
VIBECOMFY_MATRIX_SCOPE=qwen_tts uv run python scripts/runpod_corpus_matrix.py
VIBECOMFY_MATRIX_SCOPE=flux2_4b uv run python scripts/runpod_corpus_matrix.py
VIBECOMFY_MATRIX_SCOPE=wan_creation_types uv run python scripts/runpod_corpus_matrix.py
```

The matrix launches a fresh pod, uploads the checkout, installs VibeComfy and HiddenSwitch ComfyUI, syncs sources, installs selected custom nodes, stages models, executes baseline `comfyui run-workflow`, converts the workflow, runs the generated VibeComfy scratchpad, downloads artifacts, and terminates the launched pod in `finally`. It also writes an offline `port check --json` report and port-convert preview artifacts beside the existing logs so GPU failures can be compared with the cheap local preflight.

That means the machine should not require hand setup for a checked-in matrix scope. If an agent has to SSH in and run ad hoc commands, convert that into code in one of these places:

- custom-node install: `vibecomfy/node_packs.py`, `custom_nodes.lock`, or `scripts/runpod_corpus_matrix.py`;
- model staging: `vibecomfy/registry/models.yaml` and `vibecomfy.registry.models_loader`;
- workflow patching: `scripts/runpod_matrix_remote.py`;
- ready-template policy: `scripts/materialize_ready_templates.py`;
- fixtures: `workflow_corpus/input/` and `vibecomfy.fixtures`;
- override behavior: matrix scope policy or the family-aware override layer.

## 9. What Is Automatic Today

Already automatic:

- source indexing via `vibecomfy sources sync`;
- port reports for helper nodes, custom-node packs, model assets, schema issues, and widget aliases;
- UI JSON to API JSON normalization;
- API JSON to `VibeWorkflow`;
- ready template generation for required rows and `ready_template: true` rows;
- custom-node requirement discovery from known class names;
- local ready-template validation;
- RunPod launch, upload, polling, artifact download, and termination;
- smoke fixture copy into pod `input/`;
- focused matrix row selection by scope;
- baseline plus VibeComfy execution for matrix rows.

Partially automatic:

- custom-node installation is catalog-backed, but each RunPod scope still declares which packs it installs;
- model staging has a registry path, but some family-specific staging is still inline in `scripts/runpod_corpus_matrix.py`;
- workflow compatibility patches are centralized in `scripts/runpod_matrix_remote.py`, but new custom-node drift still needs a patch once discovered;
- family-specific override stripping exists in the matrix, but should become declarative per workflow family.

Still too manual:

- choosing high-quality source workflows;
- deciding the smoke variant for expensive models;
- adding new RunPod scopes for new model families;
- promoting discovered one-off shell fixes into reusable code;
- updating docs when a new HiddenSwitch incompatibility or structural issue appears.

## 10. Documentation Rule

Every runtime failure should land in one of three buckets:

- `docs/hiddenswitch_incompatibilities.md` when HiddenSwitch differs from mainline Comfy or a custom node assumes mainline behavior;
- `docs/structural_issues.md` when the problem is in VibeComfy architecture, tooling, staging, fixtures, or validation;
- a family coverage doc when the issue is specific to Wan, LTX, Flux, Z-Image, Qwen TTS, ACE-Step, or another model family.

Do not leave successful fixes only in chat history or RunPod logs. If the next agent would need to rediscover it, it belongs in code or docs.
