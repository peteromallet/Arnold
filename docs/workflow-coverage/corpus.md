# Workflow Corpus

`ready_templates/sources/` is the repo-local template set VibeComfy must be able to convert and run. It is intentionally task/model-family focused rather than a random dump of Comfy JSON files.

The required manifest is:

```text
ready_templates/sources/manifests/coverage.json
```

Each entry defines:

- `id`: stable VibeComfy coverage id.
- `path`: repo-local workflow JSON.
- `source`: upstream source repository.
- `model_family`: model family under test.
- `task`: text-to-image, image-edit, text-to-video, image-to-video, etc.
- `media`: expected output media.
- `coverage_tier`: `required` means RunPod validation must attempt baseline Comfy and VibeComfy execution.
- `ready_template`: `true` means the workflow has a checked-in Python ready template even when it is supplemental runtime coverage. A string value points at the category-qualified Python template id when it differs from the manifest id.
- `source_only`: `true` means the row is retained as upstream source material and is intentionally not a runnable template row. Use `ready_template_consumers` to list the Python ready templates that consume that source.

Status language:

- `raw_json`: imported source material only.
- `converted`: raw JSON normalizes into API JSON and VibeWorkflow.
- `ready_template`: checked-in Python template that can be loaded and structurally validated.
- `runtime_ready`: all node packs, model files, and input media are declared and staged for a RunPod attempt.
- `runtime_green`: baseline Comfy and VibeComfy both generated the expected media on RunPod.

Do not use `ready_template` to imply `runtime_green`. A template can be useful and reusable before every model/input dependency has been staged.

The RunPod matrix must be runtime-profile aware. Mainline Comfy workflows can use generic CLI overrides such as `--prompt` and `--steps`. Custom-node families such as LTX and WanVideoWrapper need family-specific handling:

- LTX smoke workflows are patched down to tiny real generations, use the pinned Lightricks/KJNodes runtime, and run with low-VRAM Comfy flags.
- WanVideoWrapper workflows keep their source-authored prompt and sampler wiring because their custom nodes are not compatible with Hiddenswitch's generic `--prompt`/`--steps` replacement logic.
- Custom-node dependency installs should be declared in the matrix script, not discovered manually per pod run.

Current required families:

- Qwen image edit.
- Z-Image.
- Wan text-to-video and image-to-video.
- LTX 2.3 text-to-video, image-to-video, two-stage upscaling, HDR IC-LoRA, and motion-track IC-LoRA.
- FLUX.2 Klein 4B text-to-image and image edit.
- FLUX.2 Klein 9B text-to-image and image edit.

Note: the public official Comfy templates expose FLUX.2 Klein 4B and 9B variants. The 9B coverage is the closest official match for the requested larger/8B-class Klein template.

Validation command:

```bash
../runpod-lifecycle/.venv/bin/python scripts/runpod_corpus_matrix.py
```

The matrix launches a fresh RunPod GPU machine, installs the HiddenSwitch pip ComfyUI fork, converts each corpus workflow into a VibeComfy scratchpad, runs baseline `comfyui run-workflow`, runs the VibeComfy scratchpad, records timing/output/failure metadata, and terminates the pod.

For LTX-specific source coverage and the Discord-derived approach matrix, see `ltx.md`.

For cross-cutting template/converter/runtime issues, see `../structural_issues.md`.
