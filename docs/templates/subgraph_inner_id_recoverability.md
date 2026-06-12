# Subgraph inner-id recoverability (M1 Step 6.3 / Criterion 8)

**Question (must-deliver, outcome-agnostic):** Do the inner `raw_call` nodes inside
subgraph definitions (`definitions.subgraphs[].nodes[]`) expose *real, stable ids* that
M2 group boxes can anchor to?

The pass criterion for this task is that the finding is **documented**, regardless of the
outcome. This document records it.

## What was investigated

Reference workflow: `ready_templates/sources/official/image/flux2_klein_4b_t2i.json` (chosen in
T1; it carries two real subgraph definitions). Two layers were inspected:

1. The raw litegraph source JSON — `definitions.subgraphs[].nodes[]`.
2. The post-ingest IR produced by `vibecomfy.ingest.normalize.convert_to_vibe_format`,
   and what `emit_ui_json`'s `_emit_definitions` path does with subgraph data.

## Finding

### 1. Inner ids ARE real and stable in the source litegraph JSON

Each subgraph definition carries a full inner node list, and every inner node has an
explicit integer `id` that is stable within the source file:

```
subgraph 7b34ab90-…-71d418f0df18  "Text to Image (Flux.2 Klein 4B)"  — 14 inner nodes
  node id=61 type=KSamplerSelect
  node id=62 type=Flux2Scheduler
  node id=63 type=CFGGuider
  node id=64 type=SamplerCustomAdvanced
  node id=65 type=VAEDecode
  node id=66 type=EmptyFlux2LatentImage
  …
```

These are concrete, addressable ids — not ephemeral. In principle an M2 group box could
anchor to them the same way the top-level emitter anchors to `properties["ir_node_id"]`.

### 2. Those ids are NOT recoverable through the current M1 IR roundtrip

The current ingest path discards subgraph definitions entirely. After
`convert_to_vibe_format(raw)` on the reference workflow:

- `wf.metadata` is **empty** (`[]`) — no `definitions` key is retained.
- The top-level IR node references the subgraph only by its **UUID `class_type`**
  (e.g. `"7b34ab90-36f9-45ba-a665-71d418f0df18"`); it is an opaque `raw_call`-style
  reference.
- The inner nodes (`61`, `62`, …) are **absent from the IR** — they are neither carried
  in metadata nor flattened into the top-level `wf.nodes`.

Consequently `emit_ui_json` cannot reproduce the inner nodes for an ingested corpus
workflow: its `_emit_definitions` helper only fires when `wf.metadata["definitions"]` is
present, which never happens on the present ingest path (consistent with the T7 prior-batch
deviation noting the definitions-emission path is currently dormant).

### 3. The emission mechanism *would* preserve inner ids if the IR carried them

`_emit_definitions` copies each subgraph's `nodes[]` through **verbatim** (`dict(raw_sg)`),
so any inner node ids present in `wf.metadata["definitions"]` survive emission unchanged.
The mechanism is id-preserving; the gap is purely that **nothing populates that metadata
during ingest today**.

## Conclusion for M2

- Inner `raw_call` node ids are **real and anchorable in principle** (explicit, stable
  integers in the source).
- They are **not recoverable via the M1 IR** as it stands, because `convert_to_vibe_format`
  flattens to API form and drops `definitions`. The UUID `class_type` on the top-level node
  is the only surviving handle to the subgraph as a whole — there is no per-inner-node anchor
  in the IR.

For M2 to anchor group boxes to subgraph internals, one of the following is required (a
design choice for M2, not resolved here):

1. **Extend ingest** to retain `definitions` (including inner node ids) in
   `wf.metadata["definitions"]`; the existing `_emit_definitions` path will then round-trip
   the inner ids unchanged, and M2 can anchor to them.
2. **Read the source litegraph JSON directly** for subgraph layout, using the breadcrumb
   `extra.vibecomfy.prior_path` (stamped in T9) to locate it, rather than relying on the IR.

Either path is viable because the underlying ids are stable; the M1 IR simply does not carry
them yet.
