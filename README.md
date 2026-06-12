# VibeComfy

VibeComfy makes ComfyUI workflows usable by agents.

Its core job is translation: import a ComfyUI workflow, represent it as editable
Python, validate the result, and compile it back to the API JSON that ComfyUI queues.
JSON is the import/export format. Python is the authoring surface.

The generated Python is intentionally ordinary code. A ready template is a
`build()` function that creates a `VibeWorkflow`, calls typed ComfyUI node
wrappers or generated subgraph functions, and finalizes the workflow contract.
This is abridged from `ready_templates/image/z_image.py`:

```python
# Abridged from ready_templates/image/z_image.py.
from vibecomfy.templates import ReadyMetadata, new_workflow
from vibecomfy.nodes.core import SaveImage

READY_METADATA = ReadyMetadata.build(capability="image")

def text_to_image_z_image_base(*, width, height, unet_name, clip_name, vae_name, prompt, steps, cfg):
    # Generated from a ComfyUI subgraph. Internally this calls CLIPLoader,
    # VAELoader, UNETLoader, EmptySD3LatentImage, CLIPTextEncode,
    # ModelSamplingAuraFlow, KSampler, and VAEDecode.
    ...

def build():
    wf = new_workflow(READY_METADATA, source_path=__file__)

    edited = text_to_image_z_image_base(
        width=1024,
        height=1024,
        unet_name="z_image_bf16.safetensors",
        clip_name="qwen_3_4b.safetensors",
        vae_name="ae.safetensors",
        prompt="a glass teapot on black basalt",
        steps=25,
        cfg=4,
    )

    save = SaveImage(_id="9", images=edited, filename_prefix="z-image")
    return wf.finalize(
        {},
        output_node=save,
        output_type="SaveImage",
        name="image",
        artifact_kind="image",
        mime_type="image/png",
        expected_cardinality="one",
        filename_prefix="z-image",
    )
```

Generated files in `ready_templates/` are annotated `# vibecomfy: generated`.
Treat them as read-only; copy one to `recipes/` with `copy-to-recipe` before
editing.

Unlike ComfyScript-style exports that flatten a graph into Python calls,
VibeComfy preserves a workflow contract for agents. See
[VibeComfy And ComfyScript](docs/comparisons/comfyscript.md).

## Getting Started

Each path below is meant to be copied directly into an agent.

### Use VibeComfy Directly

Use this when you want an agent to install VibeComfy, discover templates, copy
one into a recipe, import unfamiliar ComfyUI workflows when needed, validate the
result, and show the runtime JSON that ComfyUI will receive.

```text
Clone https://github.com/peteromallet/VibeComfy and install it with `python -m pip install -e .`.
Run `python scripts/sync_agent_skill.py --apply`; if this checkout should become a reusable local agent skill, run `python scripts/sync_agent_skill.py --install-user`.
That installer uses SkillSinker: it symlinks the VibeComfy skill into detected Claude, Codex, and Hermes skill directories without overwriting existing entries, and it updates Codex's `AGENTS.md` with an idempotent fenced VibeComfy block.
If I already have ComfyUI workflows or custom nodes, index them with `python -m vibecomfy.cli sources sync --official <official_workflow_dir> --external <my_workflow_dir> --custom-nodes <ComfyUI/custom_nodes> --json`, then use `workflows list`, `search`, `nodes list`, and `nodes spec` against that local context.
List ready templates with `python -m vibecomfy.cli workflows list --ready`.
Inspect `image/z_image` with `python -m vibecomfy.cli inspect image/z_image`.
Copy it to `recipes/my_z_image.py` with `python -m vibecomfy.cli copy-to-recipe image/z_image --out recipes/my_z_image.py`.
If I give you an unfamiliar ComfyUI JSON workflow instead of a ready template, first run `python -m vibecomfy.cli port check <workflow.json> --json` and `python -m vibecomfy.cli nodes install-plan <workflow.json>`, then convert it with `python -m vibecomfy.cli port convert <workflow.json> --out out/scratchpads/<name>.py --json`.
Edit the copied or converted Python itself: change prompts, seeds, steps, model choices, wiring, and output prefixes in the generated/template call sites, not by editing compiled API JSON.
Validate the recipe with `python -m vibecomfy.cli validate recipes/my_z_image.py`.
For converted scratchpads, validate `out/scratchpads/<name>.py` instead.
Export the runtime API JSON with `python -m vibecomfy.cli port export recipes/my_z_image.py --to json --json`.
If node packs are missing, use `python -m vibecomfy.cli nodes ensure <workflow>`. If model assets are missing, prefer normal `run` because it reconciles declared assets before queueing; use `fetch` only when explicitly staging authored model assets.
Summarize what changed and show me the exact API JSON fields ComfyUI will receive before any GPU run.
```

### Use VibeComfy Inside ComfyUI

Use this when you want VibeComfy's ComfyUI extension nodes. The in-editor agent
panel is still a development surface.

```text
Install VibeComfy into my ComfyUI checkout. Use the same Python that runs ComfyUI, install VibeComfy editable, symlink `vibecomfy/comfy_nodes` into `ComfyUI/custom_nodes/vibecomfy`, restart ComfyUI, and verify that the VibeComfy node categories appear.
```

After restart, look for nodes under `vibecomfy/exec`, `vibecomfy/intent`, and
`conditioning/vibecomfy`.

The experimental agent panel lets an agent edit a workflow from inside ComfyUI.
It needs an agent runtime module in the ComfyUI process; the current development
setup is documented in
[docs/local_agent_text_to_graph_e2e.md](docs/local_agent_text_to_graph_e2e.md).

### Use VibeComfy Through Astrid

Astrid is the higher-level agentic art harness one level above this repo. Use
VibeComfy for workflow translation and execution; use Astrid for agent/human
creative runs around image, video, and audio assets.

```text
Clone https://github.com/banodoco/Astrid, install it editable with `cd Astrid && python -m pip install -e .`, run `python3 -m astrid skills install --all`, then run `python3 -m astrid skills doctor`.
Use `python3 -m astrid --help`, `python3 -m astrid status`, and `python3 -m astrid next` to attach or create the working project; treat `astrid next` as the canonical next-action oracle.
Explain how Astrid can use VibeComfy-backed image, video, or audio workflows inside an agent/human creative run. Start with one small demo plan, use VibeComfy for workflow translation/execution, and validate before any GPU run.
```

## Architecture In One Pass

Everything flows through `VibeWorkflow`.

```mermaid
flowchart LR
    A[ComfyUI JSON<br/>import/export format] -->|port convert| B[Python ready template<br/>or scratchpad]
    B --> C[VibeWorkflow<br/>editable IR]
    Agent[Agent edits here] --> B
    C --> D[validate / patch / compose]
    D -->|compile("api")| E[API JSON dict]
    E --> F[ComfyUI queue_prompt]
```

`compile("api")` returns the dict that ComfyUI's `queue_prompt` accepts. It is
useful for inspection and runtime, but it is not the format VibeComfy asks
agents to edit.

The main artifact types are:

| Term | Meaning |
|---|---|
| Workflow | Any graph, whether it came from ComfyUI JSON, a ready template, or a scratchpad. |
| Ready template | A curated Python starting point in `ready_templates/`, addressed by ids like `image/z_image`. |
| Recipe | User code in `recipes/` that loads templates, applies patches, adds blocks, and runs or exports the result. |
| API JSON | The runtime dict produced by `wf.compile("api")`; ComfyUI queues this, but agents should not hand-edit it. |

Agents should edit the Python workflow surface. Use patches when a change
decorates an existing graph, such as resolution, save prefix, model policy, or
low-VRAM behavior. Use blocks when a change adds graph structure and creates new
handles to wire.

## Templates And Porting

Ready templates live in [ready_templates/](ready_templates/). Give this to an
agent when you want it to choose a starting point:

```text
If I have an existing ComfyUI checkout or workflow folder, first run `python -m vibecomfy.cli sources sync --external <workflow_dir> --custom-nodes <ComfyUI/custom_nodes> --json` so discovery and node specs reflect my local workflows and installed custom nodes.
List ready templates with `python -m vibecomfy.cli workflows list --ready`.
Search for a relevant workflow with `python -m vibecomfy.cli search <query> --task <task>`.
Inspect likely candidates with `python -m vibecomfy.cli inspect <template_id>` and `python -m vibecomfy.cli analyze info <template_id>`.
Pick the smallest ready template that already has the needed media type, model family, and output contract.
```

Porting converts a raw ComfyUI JSON workflow into a Python scratchpad or ready
template. Give this to an agent when starting from raw JSON:

```text
Run `python -m vibecomfy.cli port check <workflow.json> --json` before editing or GPU time.
Run `python -m vibecomfy.cli nodes install-plan <workflow.json>` against the same custom-node context, then use `nodes ensure`, `nodes lock`, or `nodes restore` when the workflow needs packs that are missing or unpinned.
Convert to a scratchpad with `python -m vibecomfy.cli port convert <workflow.json> --out out/scratchpads/<name>.py --json`.
Validate the emitted Python with `python -m vibecomfy.cli validate out/scratchpads/<name>.py`.
If the workflow should become reusable, promote it to a ready template with `port convert --ready-id <kind>/<name> --out ready_templates/<kind>/<name>.py`.
```

Promote durable workflows to Python ready templates. Keep raw JSON as source
evidence; do not make compiled API JSON the reusable source of truth.

## Deeper Docs

- [Authoring](docs/authoring.md)
- [Porting workbench](docs/templates/porting_workbench.md)
- [Adding templates and models](docs/templates/adding_templates_models.md)
- [Testing user code](docs/testing/user_code.md)
- [ComfyScript comparison](docs/comparisons/comfyscript.md)

## Repository Layout

| Path | Purpose |
|---|---|
| `vibecomfy/` | Package, CLI, workflow IR, porting code, runtime helpers, and ComfyUI nodes. |
| `ready_templates/` | Curated Python templates intended as starting points. |
| `recipes/` | User code that composes templates, patches, blocks, and runtime calls. |
| `workflow_corpus/` | Source ComfyUI workflows used for indexing, conversion, and coverage. |
| `docs/` | Authoring, porting, runtime, testing, architecture, and migration docs. |
| `out/` | Generated scratchpads, run outputs, reports, and temporary artifacts. |

## Thanks

VibeComfy is a relatively thin Python authoring layer for agents. The real work belongs to:

- **[`pip-and-uv-installable-ComfyUI`](https://github.com/hiddenswitch/pip-and-uv-installable-ComfyUI)** by [Dr. Pangloss / hiddenswitch](https://github.com/hiddenswitch) - the fork that makes ComfyUI installable as a normal Python package, which is what lets VibeComfy embed Comfy at all.
- **[ComfyUI](https://github.com/comfyanonymous/ComfyUI)** by **Comfy Anonymous** and the Comfy team / community, plus the custom-node pack authors VibeComfy indexes (KJNodes, VideoHelperSuite, WanVideoWrapper, LTXVideo, rgthree, was-node-suite, and many more).
- **The workflow builders** whose graphs the ready templates are based on - [Kijai](https://github.com/kijai), the [Comfy team's official examples](https://github.com/comfyanonymous/ComfyUI_examples), and many others across the community whose published workflows we adapted into the `ready_templates/` set.
- **The open-source model authors** whose weights every workflow actually runs - Black Forest Labs (Flux), Tencent (Hunyuan), Alibaba (Wan, Qwen), Lightricks (LTX-Video), Stability AI (SD/SDXL), and the long tail of fine-tuners and LoRA authors releasing openly on Hugging Face and Civitai.

## License

MIT - see [LICENSE](LICENSE).
