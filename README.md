# VibeComfy

**VibeComfy is a Python authoring layer for ComfyUI workflows.** Load a workflow
from a ready template, indexed JSON file, or scratchpad into `VibeWorkflow`, edit
it in Python, validate it, and run it through the same API JSON path ComfyUI
accepts.

![VibeComfy explainer](docs/assets/explainer.png)

## Quickstart

```bash
git clone https://github.com/peteromallet/VibeComfy
cd VibeComfy
uv sync
python -m vibecomfy.cli sources sync
python -m vibecomfy.cli workflows list --ready
python -m vibecomfy.cli inspect image/z_image
```

Give your coding agent [AGENTS.md](AGENTS.md) first. It is a short bootstrap that
points to [CLAUDE.md](CLAUDE.md), the canonical long-form agent guide for the
current v2.7 authoring surface. The old bundled-skill path is not present in
this checkout; use these repository docs instead.

## Current v2.7 Flow

The public import surface is recorded in
[artifacts/m6-public-api.md](artifacts/m6-public-api.md). The core path is:

```
load -> edit -> patch/block -> validate -> run
```

```python
from vibecomfy import load_workflow_any, run_embedded_sync
from vibecomfy.patches.resolution import resolution
from vibecomfy.patches.seed import seed

wf = load_workflow_any("image/z_image")

# Edit the workflow IR directly.
wf.set_prompt("a glass teapot on basalt")
wf.set_steps(20)

# Apply patches for policy-like changes.
resolution(832, 480).apply(wf)
seed(42).apply(wf)

wf.finalize_metadata()
report = wf.validate()
if not report.ok:
    raise RuntimeError("; ".join(issue.message for issue in report.issues))

result = run_embedded_sync(wf)
print(result.outputs)
```

Use blocks when composition adds graph structure and returns handles for later
wiring. For example, attach another image save node to an existing image handle:

```python
from vibecomfy import Handle
from vibecomfy.blocks.save import image as save_image

first_output = wf.outputs[0]
image_handle = Handle(first_output.node_id, 0, name="image")
save_handles = save_image(
    wf,
    images=image_handle,
    filename_prefix="quickstart/extra-save",
)
```

For verb-native generation, use the public `image` and `video` namespaces:

```python
from vibecomfy import image, video

still = image.t2i("a glass teapot").run(runtime="embedded")
clip = video.i2v(still.outputs[0], "the teapot rotates").run(runtime="embedded")
```

To inspect the exact JSON ComfyUI receives, compile the workflow:

```python
api_dict = wf.compile("api")
```

There is no separate public export method to use for this.

## Validate And Run From The CLI

```bash
python -m vibecomfy.cli validate out/scratchpads/my_workflow.py
python -m vibecomfy.cli doctor out/scratchpads/my_workflow.py
python -m vibecomfy.cli run image/z_image --ready --prompt "a glass teapot" --seed 42 --steps 20
```

Useful discovery commands:

```bash
python -m vibecomfy.cli workflows list --ready
python -m vibecomfy.cli workflows list
python -m vibecomfy.cli search wan --task i2v
python -m vibecomfy.cli nodes list
python -m vibecomfy.cli analyze info image/z_image
```

## Public Names

Top-level names currently exported from `vibecomfy` include:

- Loaders: `load_workflow_any`, `load_workflow_json`, `workflow_from_file`,
  `workflow_from_id`, `workflow_from_ready`, `ready_template_ids`
- Compatibility aliases: `workflow_from_template`, `load_template`
- Runtime helpers: `run`, `run_sync`, `run_embedded`, `run_embedded_sync`
- Namespaces: `image`, `video`, `blocks`, `patches`, `router`
- Core types: `VibeWorkflow`, `VibeNode`, `VibeEdge`, `VibeInput`,
  `VibeOutput`, `WorkflowRequirements`, `WorkflowSource`, `ValidationIssue`,
  `ValidationReport`, `Handle`
- Artifact types: `Artifact`, `Image`, `Video`, `Audio`, `Latent`, `Mask`
- Plugin hook: `ensure_plugins_loaded`

## Porting ComfyUI workflows

If you just want to **run a raw Comfy workflow as-is**, point the embedded runtime at the JSON — no porting required:

```bash
python -m vibecomfy.cli port check path/to/workflow.json --json   # cheap preflight
python -m vibecomfy.cli run path/to/workflow.json --runtime embedded
```

`load_workflow_any("path/to/workflow.json")` does the same from Python. Reach for the porting workbench below when you want editable Python, a checked-in ready template, or RunPod time.

Before manually editing a raw Comfy workflow, converting it into a template, or spending RunPod time, run the porting preflight:

```bash
python -m vibecomfy.cli port check <workflow> --json
python -m vibecomfy.cli port check <workflow> --strict-ready-template --json
python -m vibecomfy.cli port convert <workflow> --out out/scratchpads/<name>.py --json
python -m vibecomfy.cli port convert <workflow> --ready-id <kind>/<name> --out ready_templates/<kind>/<name>.py --json
python -m vibecomfy.cli port inventory --ready --json
```

`port check` reports helper/UI nodes, unresolved custom-node packs, missing required inputs, positional widget aliases, output-contract gaps, and model asset issues while staying offline by default. Use `--strict-ready-template` before promoting or RunPod-testing production/app-parity templates; it turns schema-backed unresolved widgets, missing or broken public inputs, missing or unnamed outputs, hidden model filenames, and opaque UUID subgraphs into hard errors. Use `--head-check-models` only when you want URL HEAD checks without downloading model bodies.

`port convert` uses atomic writes (temp file → validate/parity-check → `Path.replace()`), refuses to overwrite `# vibecomfy: manual` templates, and supports `--dry-run` (emit evidence without writing) and `--diff` (unified diff + JSON metadata). Parity evidence includes widget snapshots, output counts, class type counts, and topology snapshots.

`port inventory` scans only checked-in `ready_templates/**/*.py` and reports readability issues (positional `.out(<int>)`, `widget_N` fields, UUID class types, local `_node` copies, missing output contracts), marker classification, and source-provenance flags. The JSON output is deterministic and versioned.

See [docs/template_porting_workbench.md](docs/template_porting_workbench.md) for the command map and live validation loop.

Ready-template discovery is repo-indexed by default. `python -m vibecomfy.cli workflows list --ready --json` reads the checked-in `template_index.json` when it exists and does not import plugin, cwd-extra, or user-global template code. Use `--include-dynamic` only when you explicitly want plugin/user rows; those rows are marked `source_scope: "dynamic"` and `indexed: false` and are excluded from strict-ready CI gates.

When replacing or hand-authoring a node, inspect the node's real accepted inputs first:

```bash
python -m vibecomfy.cli nodes spec ImageResizeKJv2
```

`nodes spec` reads the local index when available and falls back to installed custom-node source with `INPUT_TYPES`, so it is useful before swapping a node class or translating a JSON widget payload into explicit Python keyword arguments.

Some custom nodes download annotator or preprocessor weights into their own package folders instead of Comfy's `models/` tree. Declare those as `model_assets` with `target_path` so `vibecomfy run` stages them before execution:

```python
{"name": "yolox_l.onnx", "url": "...", "subdir": "controlnet_aux", "target_path": "custom_nodes/comfyui_controlnet_aux/ckpts/yzd-v/DWPose/yolox_l.onnx"}
```

Loader-specific model folders matter. For example, LTX audio VAE files used by `LTXVAudioVAELoader` must be staged under `checkpoints`, not `vae`; `validate` rejects the known-bad `VAELoaderKJ` plus LTX audio VAE pairing before runtime.

For reusable workflows, the checked-in surface is Python, not raw JSON. Keep upstream/source workflows in `workflow_corpus/`, convert or author the reusable version in `ready_templates/<kind>/<id>.py`, record it in `workflow_corpus/manifests/coverage.json`, and refresh the static discovery index:

```bash
python -m vibecomfy.cli port convert workflow_corpus/.../<id>.json --out ready_templates/<kind>/<id>.py --ready-id <kind>/<id> --json
python -m tools.refresh_template_index
python -m tools.refresh_template_index --check
python -m vibecomfy.cli validate ready_templates/<kind>/<id>.py
python -m vibecomfy.cli port check ready_templates/<kind>/<id>.py --strict-ready-template --json
python -m vibecomfy.cli doctor ready_templates/<kind>/<id>.py --json
python -m tools.check_strict_ready_templates --json
```

The manifest/index tests catch missing ready-template rows, stale `template_index.json`, and manifest entries that point at Python templates that do not exist. `tools/check_strict_ready_templates.py` is the repo-wide gate: it walks every protected (`app_active: true` or `coverage_tier: required`) template, runs the strict checks, and reconciles surviving violations against the exception registry.

Required or app-active ready templates must stay on the clean path: public inputs are named and target real built nodes/fields, public outputs are semantically named, hidden model filenames are exposed through public inputs or model metadata, schema-backed `widget_N` aliases are resolved, and opaque UUID subgraphs are either replaced with transparent graph code or covered by an explicit strict-ready exception. Document any remaining non-compliant template as `reference`, `supplemental`, `blocked`, or `scratchpad-only` with an owner and follow-up ticket. Exceptions live in [`docs/strict_ready_exceptions.md`](docs/strict_ready_exceptions.md) and [`docs/strict_ready_exceptions.json`](docs/strict_ready_exceptions.json) — each entry pins a `ready_id` + `violation_code` + `target` and must carry an owner, ticket, expiry, and removal condition.

`doctor` is the local readiness pass for a built workflow. It reports missing
model assets, node-pack drift, suggested patches, and runtime warnings that
schema validation cannot infer. For video workflows, it also flags generated
frame-count bindings that are paired with uncapped video loaders; either bind
`frame_load_cap` to the same effective frame count or have the caller
materialize a capped source clip before runtime.

### Semantic Graph Lens and Contract Validation

For app-active workflows, validate intent before GPU time:

```bash
# Graph diagnostics: nodes, edges, inputs, outputs, upstream/downstream
python -m vibecomfy.cli workflows lens <template-or-path> [--json]

# Semantic contract validation for LTX first/last two-stage
python -m vibecomfy.cli workflows contract-validate <template-or-path> --type ltx-first-last-two-stage [--json]
```

From Python:

```python
from vibecomfy.lens import WorkflowLens
from vibecomfy.contracts import LTXFirstLastTwoStageContract

lens = WorkflowLens(workflow)
print(lens.diagnostics())
report = LTXFirstLastTwoStageContract().validate(workflow)
print(report.summary())
```

> **Compiled Comfy API JSON is runtime materialization only, not the workflow source of truth.** App intent should be validated through `VibeWorkflow`, the lens, and contracts. Tests may inspect compiled API for runtime smoke, but semantic assertions use the lens and contract layers.

## Thanks

VibeComfy is a thin Python authoring layer. The real work belongs to:

- **[`pip-and-uv-installable-ComfyUI`](https://github.com/hiddenswitch/pip-and-uv-installable-ComfyUI)** by [Dr. Pangloss / hiddenswitch](https://github.com/hiddenswitch) — the fork that makes ComfyUI installable as a normal Python package, which is what lets VibeComfy embed Comfy at all.
- **[ComfyUI](https://github.com/comfyanonymous/ComfyUI)** by **Comfy Anonymous** and the Comfy team / community, plus the custom-node pack authors VibeComfy indexes (KJNodes, VideoHelperSuite, WanVideoWrapper, LTXVideo, rgthree, was-node-suite, and many more).
- **The workflow builders** whose graphs the ready templates are based on — [Kijai](https://github.com/kijai), the [Comfy team's official examples](https://github.com/comfyanonymous/ComfyUI_examples), and many others across the community whose published workflows we adapted into the `ready_templates/` set.
- **The open-source model authors** whose weights every workflow actually runs — Black Forest Labs (Flux), Tencent (Hunyuan), Alibaba (Wan, Qwen), Lightricks (LTX-Video), Stability AI (SD/SDXL), and the long tail of fine-tuners and LoRA authors releasing openly on Hugging Face and Civitai.

## Code quality

![Code quality scorecard](docs/assets/scorecard.png)

## v2.6 Ready Templates

Ready templates use the v2.6 context-bound shape. Node wrappers read the active
workflow from `with new_workflow(...) as wf:`, so each node call carries only
semantic kwargs:

```python
from vibecomfy.nodes.core import CLIPTextEncode, SaveImage
from vibecomfy.templates import InputSpec, ModelAsset, ReadyMetadata, new_workflow

MODELS = {"main": ModelAsset(url="https://example.com/model.safetensors", subdir="checkpoints")}
PUBLIC_INPUTS = {"prompt": InputSpec(node="6", field="text", default="", type="STRING", required=True)}
READY_METADATA = ReadyMetadata.build(
    capability="text_to_image",
    inputs=PUBLIC_INPUTS,
    models=MODELS,
)

def build():
    with new_workflow(READY_METADATA, source_path=__file__) as wf:
        encoded = CLIPTextEncode(_id="6", text=PUBLIC_INPUTS["prompt"], clip=...)
        SaveImage(_id="9", images=encoded, filename_prefix="image/example")
        return wf.finalize(PUBLIC_INPUTS, output_node="9", output_type="SaveImage")
```

The explicit workflow form remains supported for external callers:
`CLIPTextEncode(wf, text="...", clip=...)`. Regenerated ready templates should
use the context-bound zero-positional form inside the `with` block.

`bind_input`, `bind_output`, direct `wf.register_input` calls in templates, and `apply_ready_template_policy` are compatibility APIs only. New templates declare public inputs in `PUBLIC_INPUTS`, model files in `MODELS`, and pack pins through `READY_METADATA.requirements` or derived `custom_node_packs`. The pack registry is `custom_nodes.lock`; rich TOML entries carry `slug`, `source`, `url`, `commit`, `version`, `schema_hash`, `class_set`, and `last_seen_at` so templates can be checked offline.

See [docs/authoring.md](docs/authoring.md) and [docs/adding_templates_models.md](docs/adding_templates_models.md) for the full authoring and promotion flow.

## License

MIT — see [LICENSE](LICENSE).

## Testing

- [Internal testing contract](docs/testing.md)
- [Testing your VibeComfy recipes](docs/testing-user-code.md) — assertions, dry-run runtime, snapshot CLI, pytest plugin
