# Authoring

> See [docs/python_composition_dsl_plan.md](python_composition_dsl_plan.md) for the broader composition-layer architecture this doc fits into.

`VibeWorkflow` is the only editable IR. Blocks and patches mutate that object; API JSON is an escape hatch produced by `wf.compile("api")`, not an authoring surface.

## Blocks

A block is a small function that mutates a workflow and returns `Handles`. Most blocks use `workflow.add_node()` plus `workflow.connect()`, but blocks may use any `VibeWorkflow` method — including `disconnect()` and `replace_edge()` for blocks that splice into existing topology. The contract is "mutate and return handles," not "add_node/connect only."

```python
from vibecomfy.blocks import Handle, Handles

def my_block(wf, *, prompt: str) -> Handles:
    node = wf.add_node("CLIPTextEncode")
    node.widgets["widget_0"] = prompt
    node.metadata["block"] = "my_package.my_block"
    return Handles({"text": Handle(node_id=node.id, output_slot=0, name="text")})
```

Built-in blocks also record `metadata.block`, `metadata.block_id`, and `metadata.widget_kwargs` on produced nodes. This keeps generated graphs inspectable without making node ids part of the public contract.

Use blocks when the call changes the handles available to the caller: a loader creates `model`, `clip`, and `vae`; a sampler creates `samples`; a decode block creates `images`.

## Typed Handles in P1

P1 ships typed handle metadata, not mypy-grade static validation. New authoring code should prefer `wf.node(...).out(<int_slot>)`, which returns a `Handle` carrying the source node id, output slot, optional output type, and optional name. Blocks should return `Handles({"image": Handle(node_id=node.id, output_slot=0, name="image")})` instead of raw string references.

Named output strings such as `.out("IMAGE")` are intentionally gated until MP-6 schema integration can map Comfy output names to slots. In P1, pass an integer slot or digit string; non-numeric output names raise `NotImplementedError`.

## Patches

A patch is a `Patch(name, applies_to, apply, rationale)`.

```python
from vibecomfy.patches import Patch

def applies_to(wf):
    return any(node.class_type == "SaveImage" for node in wf.nodes.values())

def apply(wf):
    for node in wf.nodes.values():
        if node.class_type == "SaveImage":
            node.widgets["widget_0"] = "demo"
    return wf.finalize_metadata()

patch = Patch("demo_prefix", applies_to, apply, lambda wf: "sets a demo prefix")
```

Use patches when the call decorates or adjusts existing handles: seed, resolution, save prefix, loader policy, or runtime policy. A patch should return the same workflow object.

Patches may use any `VibeWorkflow` method, including `disconnect()` and `replace_edge()`. This is the difference between *mutational* decoration (set a widget, swap a class — what `seed`, `resolution`, `gguf_unet` do) and *topological* decoration (splice a node into an existing edge — what ControlNet, IP-Adapter, and similar conditioning patches require). Both are patches.

Rule of thumb: changes-handles -> new template; decorates-handles -> patch.

The LTX low-VRAM policy is the main counter-example. It decorates a template, but it changes enough loader classes and smoke dimensions that it would be a separate template if users needed both forms equally. Today it is a patch because the low-VRAM form is the supported local default.

## Edge Primitives

`VibeWorkflow.disconnect(to_ref)` removes the edge feeding `to_ref` (e.g. `"5.positive"`). `VibeWorkflow.replace_edge(to_ref, new_from_ref)` does the same and then connects a new source.

Topological patches use these to splice a node into an existing path. `vibecomfy.patches.controlnet` is the canonical example: it finds the edge feeding `KSampler.positive`, redirects the original source through a `ControlNetApplyAdvanced` node, and reconnects the apply node's output to the sampler.

```python
def apply(wf, *, control_net_name="depth.safetensors", strength=1.0):
    sampler_id = next(nid for nid, n in wf.nodes.items() if n.class_type == "KSampler")
    pos_edge = next(e for e in wf.edges if e.to_node == sampler_id and e.to_input == "positive")
    loader = wf.add_node("ControlNetLoader", widget_0=control_net_name)
    apply_node = wf.add_node("ControlNetApplyAdvanced", widget_0=strength)
    wf.connect(f"{pos_edge.from_node}.{pos_edge.from_output}", f"{apply_node.id}.positive")
    wf.connect(f"{loader.id}.0", f"{apply_node.id}.control_net")
    wf.replace_edge(f"{sampler_id}.positive", f"{apply_node.id}.0")
    return wf
```

Topology mutation is allowed by the patch contract; the `add_node/connect only` rule from earlier drafts has been retired.

## Metadata

Call `wf.finalize_metadata()` after assembling a workflow outside an individual block. It rebuilds discoverable inputs, outputs, and requirements from the current nodes.

Do this after applying patches that change prompts, seeds, model names, save nodes, or class types. The method returns `wf`, so builders can end with:

```python
return wf.finalize_metadata()
```

## Opaque Subgraphs

Some ComfyUI templates contain UUID class-type subgraph nodes. `vibecomfy.blocks.subgraph.opaque()` preserves those nodes without unpacking them.

```python
from vibecomfy.blocks import subgraph

handles = subgraph.opaque(
    wf,
    class_type="9b9009e4-2d3d-445f-9be5-6063f465757e",
    widgets=["prompt", 1024, 1024],
    outputs=("image",),
)
```

The block sets `metadata.subgraph_class_type` to the UUID class type. Wire its returned handles like any other block output.

## Ready Templates

Ready templates should be hand-curated Python builders. Retiring `scripts/materialize_ready_templates.py` is intentional: the materializer was useful for bootstrapping, but it hid authoring decisions inside copied API dictionaries.

`MarkdownNote` nodes are dropped during refactor because they are ComfyUI UI annotations with no execution effect. Snapshot tests filter them at capture time so runnable graph parity is compared without those notes.

## Escape Hatches

Every layer stays public and inspectable. Ops (when they ship) return concrete paths eagerly; for inspection, use the lower layers directly:

```python
from vibecomfy.registry.ready import workflow_from_ready
from vibecomfy.runtime import run_embedded_sync

wf = workflow_from_ready("image/z_image")        # the editable IR
api = wf.compile("api")                          # the dict ComfyUI accepts
result = run_embedded_sync(wf)                   # actually run it
path = result.outputs[0]                         # the saved file
```

Pipelines are ordinary Python. Use blocks for new graph structure, patches for policy, and `compile("api")` only when handing the graph to ComfyUI.
