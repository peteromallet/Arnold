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

## Thanks

VibeComfy is a thin Python authoring layer. The real work belongs to:

- **[`pip-and-uv-installable-ComfyUI`](https://github.com/hiddenswitch/pip-and-uv-installable-ComfyUI)** by [Dr. Pangloss / hiddenswitch](https://github.com/hiddenswitch) — the fork that makes ComfyUI installable as a normal Python package, which is what lets VibeComfy embed Comfy at all.
- **[ComfyUI](https://github.com/comfyanonymous/ComfyUI)** by **Comfy Anonymous** and the Comfy team / community, plus the custom-node pack authors VibeComfy indexes (KJNodes, VideoHelperSuite, WanVideoWrapper, LTXVideo, rgthree, was-node-suite, and many more).
- **The workflow builders** whose graphs the ready templates are based on — [Kijai](https://github.com/kijai), the [Comfy team's official examples](https://github.com/comfyanonymous/ComfyUI_examples), and many others across the community whose published workflows we adapted into the `ready_templates/` set.
- **The open-source model authors** whose weights every workflow actually runs — Black Forest Labs (Flux), Tencent (Hunyuan), Alibaba (Wan, Qwen), Lightricks (LTX-Video), Stability AI (SD/SDXL), and the long tail of fine-tuners and LoRA authors releasing openly on Hugging Face and Civitai.

## Code quality

![Code quality scorecard](docs/assets/scorecard.png)

## License

MIT — see [LICENSE](LICENSE).
