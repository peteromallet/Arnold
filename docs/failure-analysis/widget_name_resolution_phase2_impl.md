# Widget Name Resolution Phase 2 Implementation

Date: 2026-06-29

## Scope

Phase 2 added one source-backed curated compact widget alias for
`ACN_AdvancedControlNetApply`. No other node aliases were added.

## Verified Widget Order

The local workspace did not contain an installed
`ComfyUI-Advanced-ControlNet` custom-node source under the visible
`ComfyUI/custom_nodes` tree, so the order was verified against the upstream
source:

- `https://github.com/Kosinkadink/ComfyUI-Advanced-ControlNet/blob/main/adv_control/nodes.py`
  maps the corpus class name `ACN_AdvancedControlNetApply` to
  `AdvancedControlNetApplyDEPR`.
- `https://github.com/Kosinkadink/ComfyUI-Advanced-ControlNet/blob/main/adv_control/nodes_deprecated.py`
  defines `AdvancedControlNetApplyDEPR.INPUT_TYPES`.
- `https://github.com/Kosinkadink/ComfyUI-Advanced-ControlNet/blob/main/adv_control/nodes_main.py`
  defines the current `AdvancedControlNetApply.INPUT_TYPES` with the same scalar
  widget order.
- `https://github.com/Kosinkadink/ComfyUI-Advanced-ControlNet/blob/main/web/js/autosize.js`
  registers the hidden autosize widget with `serialize: false`, so it does not
  add a serialized `widgets_values` slot or reorder the Python scalar widgets.

Relevant `INPUT_TYPES` excerpt from `nodes_deprecated.py`:

```python
"required": {
    "positive": ("CONDITIONING", ),
    "negative": ("CONDITIONING", ),
    "control_net": ("CONTROL_NET", ),
    "image": ("IMAGE", ),
    "strength": ("FLOAT", {"default": 1.0, "min": 0.0, "max": 10.0, "step": 0.01}),
    "start_percent": ("FLOAT", {"default": 0.0, "min": 0.0, "max": 1.0, "step": 0.001}),
    "end_percent": ("FLOAT", {"default": 1.0, "min": 0.0, "max": 1.0, "step": 0.001})
},
"optional": {
    "mask_optional": ("MASK", ),
    "timestep_kf": ("TIMESTEP_KEYFRAME", ),
    "latent_kf_override": ("LATENT_KEYFRAME", ),
    "weights_override": ("CONTROL_NET_WEIGHTS", ),
    "model_optional": ("MODEL",),
    "vae_optional": ("VAE",),
},
```

The verified compact serialized order for the corpus values `[0.6, 0, 0.75]` is:

```python
["strength", "start_percent", "end_percent"]
```

## Schema Entry Added

Added to `WIDGET_SCHEMA` in `vibecomfy/_compile/_widgets.py`:

```python
"ACN_AdvancedControlNetApply": ["strength", "start_percent", "end_percent"],
```

The existing compact resolver precedence then resolves ACN through
`committed_widget_schema`, while the workflow-derived object-info stub remains
non-authoritative.

## Reproduction

Command:

```bash
.venv/bin/python - <<'PY'
import json
from pathlib import Path
from vibecomfy.porting.widgets.compact_resolver import compact_widget_names_for_node, widget_index_for_field
from vibecomfy.workflow import RawWidgetPayload, VibeNode

data = json.loads(Path("external_workflows/corpus/19d221f074b42462.json").read_text())
raw_node = data["nodes"]["60"]
raw_widgets = raw_node["raw_widgets"]
node = VibeNode(
    id=str(raw_node["id"]),
    class_type=str(raw_node["class_type"]),
    inputs=dict(raw_node.get("inputs") or {}),
    widgets=dict(raw_node.get("widgets") or {}),
    metadata=dict(raw_node.get("metadata") or {}),
    uid=str(raw_node.get("uid") or ""),
    raw_widgets=RawWidgetPayload(
        values=list(raw_widgets["values"]),
        shape=str(raw_widgets["shape"]),
        source=str(raw_widgets["source"]),
        has_dict_rows=bool(raw_widgets["has_dict_rows"]),
        length=int(raw_widgets["length"]),
    ),
)
resolution = compact_widget_names_for_node(node, "ACN_AdvancedControlNetApply")
print("names =", list(resolution.names))
print("source =", resolution.source)
print("strength =", widget_index_for_field(node, "strength"))
print("end_percent =", widget_index_for_field(node, "end_percent"))
print("latent_kf_override =", widget_index_for_field(node, "latent_kf_override"))
PY
```

Output:

```text
names = ['strength', 'start_percent', 'end_percent']
source = committed_widget_schema
strength = 0
end_percent = 2
latent_kf_override = None
```

## Verification

`py_compile` passed:

```bash
.venv/bin/python -m py_compile vibecomfy/_compile/_widgets.py tests/test_compact_widget_resolver.py
```

Focused resolver tests passed:

```text
tests/test_compact_widget_resolver.py -q
4 passed
```

Required gate command:

```bash
.venv/bin/python -m pytest tests/test_compact_widget_resolver.py tests/test_widget_shape_fence.py tests/test_strict_ready.py tests/test_porting_edit_apply.py tests/test_ui_emitter_widget_shape_verdict.py tests/test_widget_shape_evidence.py -q
```

Result:

```text
92 passed, 1 skipped, 1 failed
TOLERATED FAIL: tests/test_widget_shape_evidence.py::test_raw_scalar_widget_overflow_is_not_hidden_by_compacted_candidate_count
All 1 failure(s) are quarantined baseline failures. No regressions.
```
