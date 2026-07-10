# Widget Name Resolution Design

Date: 2026-06-29

Scope: read-only investigation of the widget-name -> `widgets_values` index
misalignment affecting agent-edit named-parameter edits.

## Executive Recommendation

Implement a shared **per-node compact widget resolver** and route every
agent-facing render, field read, and apply-time write through it.

The resolver's contract must be explicit:

1. The edit/apply contract is **compact `widgets_values` order**: index `N` means
   `node["widgets_values"][N]` or IR `node.widgets["widget_N"]`.
2. Per-node/live UI widget names are the highest-confidence naming source when
   present, but the checked-in scenario graphs do **not** serialize widget-name
   lists for the two evidence nodes.
3. `object_info_widget_value_order()` is the class-level fallback for compact
   widget positions.
4. `object_info_widget_order()` is raw input/schema order and must stay reserved
   for emission/shape reasoning where `None` UI-only slots matter.
5. If a node has compact widget values but no trustworthy compact name for a
   slot, expose `widget_N`, not a guessed name.

The smallest sufficient patch is to fix the SVD/ACN class aliases. I do **not**
recommend that as the primary solution: the same drift recurs for any custom node
whose frontend adds widgets not represented in Python `INPUT_TYPES`, and for any
path that expands compact widget values against raw object-info input order.

## Root-Cause Confirmation

### What the Current Code Does

Class-level compact name lookup lives in
`vibecomfy/porting/widgets/schema.py:35`. `ui_widget_value_names_for_class()`
first returns curated `WIDGET_SCHEMA`, then, when fallback is allowed, returns
`object_info_widget_value_order()` (`schema.py:49`, `schema.py:53`).

The apply path uses that class-only lookup:

- `_widget_index_for_field(class_type, field_name)` enumerates
  `ui_widget_value_names_for_class()` and returns the first matching index
  (`vibecomfy/porting/edit/apply_slots.py:27`).
- `apply_resolve_base.py` calls `_widget_index_for_field()` before trying
  explicit `widget_N` syntax (`vibecomfy/porting/edit/apply_resolve_base.py:207`).
- The mutation then writes that index into the list, extending if needed
  (`vibecomfy/porting/edit/apply_mutate.py:421`).

The agent-facing projection has the same problem:

- `_field_rows()` enumerates `widgets_values`, labels each value with
  `ui_widget_value_names_for_class()`, and falls back to `widget_N` only if the
  class name list is shorter than the value list
  (`vibecomfy/porting/edit/projection.py:246`).
- `edit_ingest.py` sends that projection to the model
  (`vibecomfy/comfy_nodes/agent/edit_ingest.py:230`).

So the model sees and edits through the same class-level name map. If that map is
wrong, the model and apply path are consistently wrong.

### Case A: `ACN_AdvancedControlNetApply`

Source graph: `external_workflows/.shadow/source/88c38378edeb6ce3-sd3_tile_cn_test_01.json`.

Observed source node:

```text
node id: 60
type: ACN_AdvancedControlNetApply
inputs: positive, negative, control_net, image, mask_optional, timestep_kf,
        latent_kf_override, weights_override, model_optional, vae_optional
widgets_values: [0.6, 0, 0.75]
```

The source file shows the node at
`external_workflows/.shadow/source/88c38378edeb6ce3-sd3_tile_cn_test_01.json:528`,
the optional input/socket rows at lines `566` through `589`, and the three
serialized widget values at lines `627` through `631`.

Real function output:

```text
ui_widget_value_names_for_class("ACN_AdvancedControlNetApply")
  -> ["mask_optional", "timestep_kf", "latent_kf_override"]

object_info_widget_order("ACN_AdvancedControlNetApply")
  -> ["positive", "negative", "control_net", "image",
      "mask_optional", "timestep_kf", "latent_kf_override", "weights_override"]

object_info_widget_value_order("ACN_AdvancedControlNetApply")
  -> ["mask_optional", "timestep_kf", "latent_kf_override"]

_widget_index_for_field("ACN_AdvancedControlNetApply", "strength")
  -> None

_widget_index_from_input_stubs(node["inputs"], "strength")
  -> None

_widget_index_from_input_stubs(node["inputs"], "latent_kf_override")
  -> None in the corpus IR node, because the IR node has `inputs: {}`.
```

Why `strength` is missing: the cache entry is a stub derived from workflow JSON,
not authoritative Python/frontend schema. `scripts/generate_hotshot_stub_schema.py`
walks `node["inputs"]`, consumes `widgets_values` only to infer value types, then
uses input row names as `object_info_widget_order` (`scripts/generate_hotshot_stub_schema.py:52`,
`:55`, `:59`, `:71`, `:91`, `:95`). For ACN, that means the stub names the three
actual widget values with the first three unlinked socket/input rows:
`mask_optional`, `timestep_kf`, `latent_kf_override`
(`vibecomfy/porting/cache/object_info/ComfyUI-Hotshot@stub.json:8`,
`:22`, `:32`, `:71`).

The graph itself does not contain a serialized widget-name list. `metadata._ui`
preserves `inputs`, `outputs`, geometry, properties, and `widgets_values`
(`external_workflows/corpus/19d221f074b42462.json:1469`, `:1470`, `:1570`), but
there is no `_ui.widgets` array with names.

The observed agent run confirms the model was shown the bad names and edited a
bad name:

```text
diff:
  latent_kf_override=0.75 -> 0.5
  mask_optional=0.6
  timestep_kf=0
```

See
`out/agentic/verify-all/image-sd3-image-generation-with-controlnet-19d221/response.json:1660`
through `:1667`, and the resolved node carrying `widgets_values: [0.6, 0, 0.75]`
at `:1706`.

Conclusion: ACN is not merely an index shift. It is an **untrusted schema-name
fabrication**: a workflow-derived object-info stub labels anonymous widget values
with socket names. `strength` and likely `end_percent` are frontend/custom-node
widget semantics not present in the serialized graph or in the stub.

`_widget_index_from_input_stubs()` is not a viable recovery path for this stored
scenario. It only inspects `inputs[].widget.name`
(`vibecomfy/porting/edit/apply_slots.py:35`, `:40`). The corpus IR node has no
list-shaped `inputs`, and the original raw LiteGraph node has plain socket rows
with no `widget` subobject.

### Case B: `SVD_img2vid_Conditioning`

Source graph: `external_workflows/.shadow/source/2856625e4990a7f6-image_to_video.json`.

Observed source node:

```text
node id: 12
type: SVD_img2vid_Conditioning
inputs: clip_vision, init_image, vae
widgets_values: [1024, 576, 14, 127, 6, 0]
```

The source file shows the node at
`external_workflows/.shadow/source/2856625e4990a7f6-image_to_video.json:160`,
linked inputs at `:174` through `:189`, and the compact widget vector at `:220`
through `:227`.

Real function output:

```text
ui_widget_value_names_for_class("SVD_img2vid_Conditioning")
  -> ["width", "height", "video_frames",
      "motion_bucket_id", "fps", "augmentation_level"]

object_info_widget_order("SVD_img2vid_Conditioning")
  -> ["clip_vision", None, None, "width", "height", "video_frames",
      "motion_bucket_id", "fps", "augmentation_level"]

object_info_widget_value_order("SVD_img2vid_Conditioning")
  -> ["width", "height", "video_frames",
      "motion_bucket_id", "fps", "augmentation_level"]

_widget_index_for_field("SVD_img2vid_Conditioning", "motion_bucket_id")
  -> 3

_widget_index_from_input_stubs(node["inputs"], "motion_bucket_id")
  -> None
```

Important correction to the shared brief: in the original checked-in source
graph, `motion_bucket_id` is **not** at compact widget index 6. It is at compact
index 3, value `127`. The brief's "index 6" is the raw object-info/all-input
position after `clip_vision`, `init_image`, and `vae`, not the serialized compact
`widgets_values` position.

The real SVD failure appears after the UI/emission path expands the node to nine
values:

```text
resolved node widgets_values:
  [1024, 576, 14, 1024, 576, 14, 127, 6, 0.0]

agent diff:
  motion_bucket_id=576
  video_frames=1024 -> 1000
  widget_7=6
```

See
`out/agentic/verify-all/video-svd-image-to-video-generation-fc240f/response.json:1061`
for the rendered diff, `:1104` for the resolved emitted node with the nine-slot
`widgets_values`, and `:1133` through `:1143` for the misleading success summary.

Why this happens: the UI emitter currently chooses raw object-info widget order
for emission:

- `_widget_names_for_emission()` returns `object_info_widget_order()` when no
  committed schema exists (`vibecomfy/porting/emit/ui.py:675`, `:683`, `:691`).
- `_build_widget_values()` then indexes the compact `node.widgets` pool against
  that raw order; when a raw slot name is not in the pool it falls back to
  captured raw widget value at the same numeric index (`vibecomfy/porting/emit/ui.py:844`,
  `:876`, `:890`, `:893`, `:896`, `:900`).

For SVD, raw order length is 9 and compact captured raw values length is 6, so
positions 0-2 get old compact values as fallbacks for `clip_vision`/`None`/`None`,
then positions 3-8 are populated from the compact widget names. That duplicates
the first three values and shifts `motion_bucket_id` to raw index 6.

Conclusion: SVD is an **order-domain mismatch** introduced by emission: compact
source values are expanded against raw object-info/all-input order, then the
agent projection labels the expanded vector with compact names.

`_widget_index_from_input_stubs()` also cannot recover SVD in the source graph:
the raw node's list-shaped `inputs` contains only linked socket rows, and the
corpus IR node again has `inputs: {}`
(`external_workflows/corpus/fc240f1c4331a5e5.json:633`).

## Ground-Truth Source Analysis

### What Is Canonical for Values?

For edit/apply, the canonical value source is the node's own serialized compact
widget vector:

- In raw LiteGraph UI JSON, `widgets_values` is the actual value array.
- In VibeComfy IR, this is preserved as `raw_widgets.values` and
  `metadata._ui.widgets_values`; the SVD corpus stores `widget_0` through
  `widget_5` in both compiled API and IR (`external_workflows/corpus/fc240f1c4331a5e5.json:18`,
  `:21`, `:695`, `:724`).
- ACN stores `widget_0` through `widget_2` as `[0.6, 0, 0.75]`
  (`external_workflows/corpus/19d221f074b42462.json:1570`, `:1593`).

The edit resolver must never change the meaning of index `N`: it is the `N`th
entry in that compact vector.

### What Is Canonical for Names?

There are three possible name sources, with different trust levels:

1. **Live browser/LiteGraph runtime widget objects**: `node.widgets[].name` is
   the highest-confidence source when the actual browser graph is available.
   Frontend overlay code already uses live widget names in places (sidecar audit:
   `vibecomfy/comfy_nodes/web/panel_overlay.js:229`, `:631`).
2. **Per-node serialized aliases**: if VibeComfy has `metadata.input_aliases`,
   or future `_ui.widgets`/`_ui.widget_names` evidence, those names can be aligned
   to this node's compact vector.
3. **Class-level schema fallback**: `WIDGET_SCHEMA`, semantic patches, provider
   schema, then `object_info_widget_value_order()`.

The two checked-in evidence source graphs do **not** contain `_ui.widgets` names.
They only contain `inputs` and `widgets_values`. Therefore the hypothesis
"the node's `_ui` widget list is the canonical source" is directionally right
for a live browser node, but it is not validated by these serialized graph files.
The serialized `_ui.inputs` rows are socket/input rows, not widget rows:

- ACN `_ui.inputs` includes `mask_optional`, `timestep_kf`,
  `latent_kf_override`, and other sockets, but no `strength`/`end_percent`
  (`external_workflows/corpus/19d221f074b42462.json:1473` through `:1528`).
- SVD `_ui.inputs` has only linked sockets `clip_vision`, `init_image`, `vae`
  (`external_workflows/corpus/fc240f1c4331a5e5.json:638` through `:653`).

### Required Distinction

Keep two explicit domains:

- **Compact widget names**: aligned one-to-one with `widgets_values`.
  Used by agent projection, field lookup, apply, graph inspection, and Python
  readable rendering.
- **Raw emission order**: full object-info/input order plus `None` UI-only slots
  where needed. Used only when reconstructing a UI JSON shape known to require
  those slots, and only with evidence that the values are already in that raw
  domain.

The current code already has two functions for this split:
`object_info_widget_order()` (`vibecomfy/porting/object_info/consume.py:461`)
and `object_info_widget_value_order()` (`:511`). The design issue is that
callers cross those domains.

## Proposed Solution

### Add a Shared Resolver Module

Create a single resolver for compact widget value names, used by projection,
apply, old-value lookup, and graph inspection.

Code sketch:

```python
@dataclass(frozen=True)
class WidgetNameResolution:
    names: tuple[str | None, ...]
    source: str
    complete: bool
    aligned_to: Literal["compact_widgets_values"]
    warnings: tuple[str, ...] = ()

def compact_widget_names_for_node(
    node: Mapping[str, Any] | Any,
    class_type: str | None = None,
    *,
    value_count: int | None = None,
    schema_provider: Any | None = None,
    allow_object_info_fallback: bool = True,
) -> WidgetNameResolution:
    """Return names aligned to compact widgets_values / widget_N positions."""

def widget_index_for_field(
    node: Mapping[str, Any],
    field_name: str,
    *,
    schema_provider: Any | None = None,
) -> int | None:
    resolution = compact_widget_names_for_node(
        node,
        schema_provider=schema_provider,
        allow_object_info_fallback=True,
    )
    return next((i for i, name in enumerate(resolution.names) if name == field_name), None)

def widget_value_for_field(
    node: Mapping[str, Any],
    field_name: str,
    *,
    schema_provider: Any | None = None,
) -> Any:
    idx = widget_index_for_field(node, field_name, schema_provider=schema_provider)
    values = node.get("widgets_values")
    if idx is not None and isinstance(values, list) and idx < len(values):
        return values[idx]
    return _MISSING_WIDGET_VALUE
```

Resolution precedence:

1. `metadata["input_aliases"]` if present and length-compatible with the compact
   value count.
2. Serialized/live per-node widget evidence:
   - browser/live `widgets[].name` when the caller has a live node;
   - future `_ui.widgets[*].name`, `_ui.widget_names`, or equivalent, only if
     length-compatible with `widgets_values`;
   - existing `_ui_widget_aliases(node)` output only when it returns enough
     aliases for all observed `widget_N` keys.
3. Curated `WIDGET_SCHEMA` only if length-compatible or explicitly designed with
   `None` placeholders for compact UI-only slots.
4. Semantic patch table (`WIDGET_SEMANTIC_NAMES`) for targeted missing names.
5. Provider schema compact aliases, filtering link-only types.
6. `object_info_widget_value_order(class_type)`, not `object_info_widget_order()`.
7. `widget_N` fallback for unnamed slots.

Safety rules:

- Never use `_ui.inputs` socket position as a widget index.
- Never use raw `object_info_widget_order()` to label compact `widgets_values`.
- If a name source has fewer names than values, fill missing slots as `widget_N`;
  do not shift later names left.
- If a name source has more names than values, truncate only for display/apply of
  existing values; keep diagnostics for possible shape drift.
- If duplicate names appear, do not auto-resolve by name; require explicit
  `widget_N` for the duplicate slots.

### Fix SVD Emission Domain Drift

The SVD failure will not be fixed by changing `_widget_index_for_field()` alone,
because the node has already been expanded to nine values in the emitted graph.

Change `_widget_names_for_emission()` / `_build_widget_values()` so it does not
expand compact `node.widgets` against raw object-info order unless the value pool
is already raw-domain.

Code sketch:

```python
def _widget_names_for_ui_values(node: VibeNode, schema: Any) -> WidgetNameResolution:
    return compact_widget_names_for_node(
        node,
        node.class_type,
        value_count=_observed_compact_value_count(node),
        schema_provider=schema,
    )

def _build_widget_values(node, widget_names, *, raw_order=None, default_values=None):
    if _node_has_compact_widget_values(node):
        # Preserve compact widgets_values length/order. Populate by compact names
        # or widget_N carriers; never preprend linked socket placeholders.
        return _build_compact_widget_values(node, compact_names=widget_names)

    if _node_has_raw_domain_values(node):
        # Legacy/known raw-domain path: raw_order may include None slots.
        return _build_raw_order_widget_values(node, raw_order)
```

A more conservative implementation can be:

- Use compact order by default when `raw_widgets.length == len(node.widgets)` or
  when all `node.widgets` keys are exactly `widget_0..widget_N`.
- Use raw object-info order only for classes with committed `WIDGET_SCHEMA`
  containing explicit `None` UI-only slots, or for nodes whose captured raw UI
  vector length already equals the raw order length.
- If raw order length is greater than compact value count and the extra leading
  slots are link-only placeholders, do not synthesize values into those positions.

### Fix ACN Naming Without Guessing

For ACN, there is no serialized name evidence for `strength` and `end_percent`.
A robust resolver should therefore render:

```python
acn_advancedcontrolnetapply = ACN_AdvancedControlNetApply(
    ...
    widget_0=0.6,
    widget_1=0,
    widget_2=0.75,
)
```

until authoritative aliases are available.

Then add an authoritative compact alias source for `ACN_AdvancedControlNetApply`
only after verifying the custom node frontend/Python source:

```python
WIDGET_SCHEMA["ACN_AdvancedControlNetApply"] = [
    "strength",
    "start_percent",
    "end_percent",
]
```

This is not a one-off workaround if handled through the same resolver and
provenance ladder. It is a class-specific schema correction backed by source
evidence. The important part is to stop using the Hotshot stub's socket names as
widget names.

### Minimal Patch Alternative

Minimal patch:

1. Add/override ACN compact aliases to `[strength, start_percent, end_percent]`
   after source verification.
2. Change `_widget_names_for_emission()` to use `object_info_widget_value_order()`
   for SVD-like nodes when emitting from compact IR `node.widgets`.
3. Change projection/apply to use a node-aware helper but keep most fallbacks.

This is smaller, but it leaves duplicate resolver logic scattered across
projection, apply, describe, graph inspection, and emission. The robust resolver
is the better architectural move.

## Pipeline-Impact Map

### Agent Projection

Files:

- `vibecomfy/porting/edit/projection.py:246`
- `vibecomfy/comfy_nodes/agent/edit_ingest.py:230`
- `vibecomfy/comfy_nodes/agent/provider.py:639`

Impact: helps directly. The agent currently sees shifted or fabricated names.
Switch `_field_rows()` to `compact_widget_names_for_node(node, class_type)`.
Unknown names should render as `widget_N`, making uncertainty visible instead of
showing false semantic names.

Regression risk: the agent may see less friendly names on schema-poor custom
nodes. That is an accuracy improvement, not a regression. Add schema hints and
research guidance for `widget_N` values when names are unavailable.

### Apply Path

Files:

- `vibecomfy/porting/edit/apply_slots.py:27`
- `vibecomfy/porting/edit/apply_resolve_base.py:207`
- `vibecomfy/porting/edit/apply_mutate.py:421`

Impact: helps directly. Replace class-only `_widget_index_for_field(class_type,
field_name)` with node-aware `widget_index_for_field(node, field_name)`. Keep
explicit `widget_N` addressing as an escape hatch.

Regression risk: if the old schema name and new per-node name disagree, existing
edits using the old false name may stop resolving. That is desirable. Surface a
diagnostic with suggestions rather than silently writing the wrong slot.

### Old/New Value Summaries

Files:

- `vibecomfy/porting/edit/_ir_utils.py:117`
- `vibecomfy/porting/edit/_describe.py:395`

Impact: helps. `_widget_value_for_field()` and `_resolve_widget_value()` should
use the same resolver as apply; otherwise summaries will report false old values
such as SVD `motion_bucket_id=576`.

Regression risk: none if unresolved names return a sentinel/diagnostic instead
of guessing.

### Agent-Edit Python Rendering

Files:

- `vibecomfy/porting/emit/emit_prepare.py:351`
- `vibecomfy/porting/emit/emit_constants.py:1062`
- `vibecomfy/porting/emit/node_kwargs.py:32`

Impact: helps broadly. The Python form shown to the batch-REPL agent uses
`resolve_widget_key_with_provenance()` for `widget_N` kwargs and can pass
per-node aliases. Ensure that those aliases are compact-domain and node-aware.

Compensating change: if `_ui_widget_aliases()` returns aliases from
`_ui.inputs[].widget`, validate that they cover the compact widget indices. Do
not infer aliases from plain `_ui.inputs[].name`.

### UI Emission

Files:

- `vibecomfy/porting/emit/ui.py:675`
- `vibecomfy/porting/emit/ui.py:844`
- `vibecomfy/porting/emit/ui.py:1046`
- `vibecomfy/porting/emit/ui.py:1097`

Impact: helps SVD and prevents future compact/raw expansion drift.

Risk: this is the highest-risk surface. Existing comments say ComfyUI
`convert_ui_to_api` consumes raw object-info widget order including `None` slots
(`vibecomfy/porting/emit/ui.py:34`). That may be true for some nodes, especially
seed `control_after_generate`. The fix must not globally replace raw emission
order with compact order. It must choose based on value-domain evidence.

Compensating change: add diagnostics that record `value_domain="compact"` or
`"raw_object_info"` in widget-shape recovery entries.

### Widget-Shape Fence

Files:

- `vibecomfy/porting/widget_shape_fence.py:58`
- `vibecomfy/porting/emit/ui.py:1693`
- `vibecomfy/porting/emit/ui.py:1778`

Impact: potentially stricter and more accurate. The fence currently compares
raw/candidate/schema counts and can allow observed-shape regeneration when
counts match (`widget_shape_fence.py:159`, `:303`). If SVD no longer expands
from 6 to 9, it should stop relying on overflow recovery for a false candidate
shape.

Regression risk: accurate compact names may reveal graphs that were previously
mis-passed because both source and emitted sides were canonicalized through the
same wrong alias. That is not gaming; it is a true failure surfacing.

Compensating change: make the fence reason about compact count and raw-emission
count separately. Do not loosen `REFUSE` decisions. If anything, refuse when a
call site attempts to label compact values with raw names.

### Strict Ready

Files:

- `vibecomfy/porting/strict_ready.py:319`
- `vibecomfy/porting/strict_ready.py:369`
- `vibecomfy/porting/strict_ready.py:413`

Impact: helps or neutral. Strict-ready widget diagnostics are about unresolved
schema-backed positional aliases. A more accurate resolver may reduce false
unresolved aliases and increase true unresolved aliases for fabricated names.

Regression risk: templates depending on bogus object-info names may fail strict
ready. That is appropriate. Keep the assertion tight by requiring either
authoritative alias evidence or explicit `widget_N`.

### Parity

Files:

- `vibecomfy/porting/parity.py:63`
- `vibecomfy/porting/parity.py:200`
- `vibecomfy/porting/convert.py:379`

Impact: helps if parity is given node/class compact aliases from source evidence.
Parity already tries to avoid masking bad static aliases by accepting
`class_widget_aliases` (`parity.py:79`, `convert.py:379`). Preserve that design.

Regression risk: if both source and emitted are normalized through the same new
wrong alias, parity can still mask a bug. Use source/per-node compact aliases
only when length-compatible and provenance-tagged.

### Graph Inspection and Research

Files:

- `vibecomfy/executor/graph_inspection.py:147`
- `vibecomfy/executor/graph_inspection.py:166`
- `vibecomfy/executor/graph_inspection.py:864`
- `vibecomfy/executor/research.py:1668`

Impact: helps readability. Graph inspection currently shows raw `w[index]` for
plain UI graphs and `widget_N` names for Vibe nodes. It should use the shared
compact resolver where schema/provider context is available, but fall back to
`widget_N` when not.

Regression risk: low. Avoid overconfident names in research summaries.

### Frontend Diff/Overlay

Impact: mostly neutral. Browser-side code has access to live LiteGraph widgets
and should continue using live widget rows as ground truth. Backend object-info
fallback should not override live browser names.

## Larger Implications

### Widget-Shape Fence d9188411

Accurate compact names make the widget-shape fence more meaningful. Today a graph
can pass if the generated candidate and the comparator share the same wrong
alias/order. After this fix:

- SVD-like compact/raw expansion should be caught as a candidate shape drift, not
  summarized as a successful `motion_bucket_id` change.
- ACN-like missing names should surface as unresolved `widget_N` instead of
  silently validating a change to `latent_kf_override`.
- The fence can become stricter by refusing domain crossings: compact values
  labelled with raw object-info positions, or raw-domain vectors edited with
  compact aliases.

This is not a weakening of d9188411. It gives the fence better evidence.

### Cross-Domain Precedent Rejection

The change is orthogonal to cross-domain precedent rejection. Better widget names
may alter the agent's research behavior: if ACN shows `widget_0=0.6` instead of
`mask_optional=0.6`, the agent is less likely to accept a misleading named
parameter and more likely to research the custom node source. That supports
cross-domain rejection because the agent has less false in-graph evidence.

### Agent Behavior Blast Radius

The blast radius is significant but positive:

- Agents will see fewer fabricated names and more explicit `widget_N` placeholders
  on schema-poor nodes.
- Many named-parameter scenarios should improve because render and apply will use
  one resolver.
- Some previously "landed" edits will become unresolved. These were unsafe
  successes, not true passes.
- Custom nodes with dynamic/frontend widgets need either live widget-name capture
  or curated schema entries. The pipeline should make that absence visible.

## Anti-Gaming Check

This fix makes checks **more accurate**, not looser.

It must not:

- ignore widget-shape mismatches;
- accept unknown names as approximate matches;
- map `strength` to `widget_0` without authoritative ACN evidence;
- let class-level object-info names override per-node value shape;
- count `motion_bucket_id` as changed when the actual compact slot for `127`
  remains unchanged.

It may loosen one behavior only in appearance: false class names such as
ACN `mask_optional` for `0.6` will stop resolving. That is stricter. The
replacement is either explicit `widget_0` or a source-backed alias.

Keep assertions tight by adding:

- a resolver diagnostic whenever names are incomplete, duplicated, or longer than
  observed values;
- a fence refusal when a raw object-info order is used to label compact values;
- tests that assert the actual value index changed, not just the named field in
  the diff summary.

## Regression Test Plan

### Unit Tests: Resolver

Add tests around the real scenario graphs:

1. Load `external_workflows/corpus/19d221f074b42462.json`, node `60`.
   Assert compact values are `[0.6, 0, 0.75]`.
   Without an authoritative ACN schema, assert names are `widget_0..widget_2`
   or unresolved, not `mask_optional/timestep_kf/latent_kf_override`.
   With a verified ACN alias fixture, assert `strength` resolves to index `0`.

2. Load `external_workflows/corpus/fc240f1c4331a5e5.json`, node `12`.
   Assert compact values are `[1024, 576, 14, 127, 6, 0]`.
   Assert `motion_bucket_id` resolves to compact index `3`.

3. Create a synthetic node with `_ui.widgets = [{"name": "a"}, {"name": "b"}]`
   and `widgets_values=[1,2]`. Assert per-node names beat object-info names.

4. Create a node with duplicate widget names. Assert name lookup refuses or
   returns ambiguous diagnostics; explicit `widget_N` still works.

### Integration Tests: Agent Render + Apply

1. Render the ACN scenario to agent-edit Python/projection. Assert it does not
   show `mask_optional=0.6` or `latent_kf_override=0.75` unless those aliases are
   explicitly source-backed. With verified ACN aliases, assert it shows
   `strength=0.6` and `end_percent=0.75`.

2. Apply `acn_advancedcontrolnetapply.strength = 0.5` with verified aliases.
   Assert node 60 `widgets_values[0] == 0.5` and `widgets_values[2] == 0.75`.

3. Render/apply SVD. Assert the emitted graph for node 12 has six values, not
   nine. Apply `motion_bucket_id = <new value>` and assert compact index `3`
   changes from `127`.

4. Run existing widget-shape-fence and strict-ready tests:
   - `tests/test_widget_shape_fence.py`
   - `tests/test_strict_ready.py`
   - `tests/test_porting_emitter_widgets.py`
   - `tests/test_ui_emitter_parity.py`

No existing gate should be weakened to pass these tests.

## Verification Plan

After implementation, rerun live agentic scenarios where the success criterion is
a named parameter edit:

1. `image-sd3-image-generation-with-controlnet-19d221`
   - Expected: intent judge passes.
   - Required evidence: `correct_node_targeted: True`,
     `correct_parameter_changed: True`, node 60 compact `widgets_values[0]`
     changes to `0.5`, compact `widgets_values[2]` remains the end-percent value.

2. `video-svd-image-to-video-generation-fc240f`
   - Expected: intent judge passes.
   - Required evidence: `correct_node_targeted: True`,
     `correct_parameter_changed: True`, node 12 compact `widgets_values[3]`
     changes from `127`; width/height/frame slots remain unchanged unless the
     user explicitly asked for them.

3. `image-sd3-image-generation-with-controlnet-19d221` on both DeepSeek and GLM
   profiles, because the shared failure reproduced across models.

4. Two to three additional named-parameter scenarios selected from the live
   catalog with obvious compact widgets:
   - a KSampler/seed or CFG edit;
   - a LoadImage or loader filename edit;
   - a video node FPS/frame-count edit.

Exact acceptance assertion for each: final intent judge passes with
`correct_parameter_changed: True`, and the low-level graph diff confirms the
intended compact widget slot changed.

## Final Recommendation

Choose the robust fix:

- one node-aware compact widget resolver;
- no raw object-info names in edit/apply labeling;
- UI emission that preserves compact vectors unless raw-domain evidence is
  explicit;
- source-backed aliases for custom nodes like ACN.

The minimal ACN/SVD patch would raise pass count on these two cases, but it
would leave the architecture vulnerable to the next custom node with frontend
widgets or the next raw/compact order crossing. The robust fix is stricter,
better instrumented, and aligns the agent's view, apply semantics, parity, and
shape fence around the same invariant: **a name must resolve to the actual
serialized compact widget slot it claims to edit**.
