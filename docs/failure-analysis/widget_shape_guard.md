# Widget-Shape Guard Blocking Valid Edits (my iteration changes)

**4 scenario(s)** in this category from the clean-100 eval (40/100).

## The issue
Uncommitted working-tree changes to `vibecomfy/porting/emit/ui.py` + `vibecomfy/porting/widget_shape_fence.py` from the watchdog iteration loop. The widget-shape pre-pass checks whether a candidate node's widget shape can be reconstructed; if not (missing raw_widget_payload, missing_layout_entry, overflow), it refuses emission with "destroy editor state." My extensions widened the schema-default path for multi-slot nodes, but the guard is still **too conservative** for collateral nodes (nodes the agent didn't edit but that are in the graph) — it blocks the entire edit because an unrelated node has a widget-shape issue.

## Affected scenarios

| Scenario ID | Root cause excerpt |
|---|---|
| `audio-acestep-audio-latent-workflow-with-vocal-separ-0eb676` | **Failure:** `RefusedEmit` — widget-shape guard on node 251 (`PrimitiveInt`), axis `widget_shape`, reason `overflow`. Th |
| `multi-crops-face-previews-it-sets` | **Failure:** `gates.queue_validate_ok = false`. The assessor (assessor.py:278-286) flags any false gate as an error when |
| `multi-image-to-video-with-upscaling-and-color-matchi-359848` | **Failure:** `RefusedEmit` — **widget_shape gate** at emit time. The agent assembled a candidate graph containing two ne |
| `video-svd-image-to-video-generation-fc240f` | **Failure:** `gates.queue_validate_ok: false` → assessor error: *"Expected edit but gates failed: queue_validate_ok"* |

## Where to find the evidence

Each scenario's full artifacts (response.json, implementation_result.json, flow_metadata.json, research.json) are under:
```
out/agentic/clean-100/<scenario_id>/
```

For comparison, the iter5 run (57/100, before the regression):
```
out/agentic/iter5-100/<scenario_id>/
```

## How to re-run a scenario

Run a single scenario to see the failure live:
```bash
.venv/bin/python -m tests.live_agentic_harness.runner \
  --single tests/live_agentic_harness/scenarios/<scenario_id>.json \
  --tag recheck --output-base out/agentic \
  --single-out /tmp/recheck.json
```

Then inspect:
```bash
# The agent's response (gates, diagnostics, outcome)
jq '.response | {ok, graph_unchanged, no_candidate_reason, outcome, gates, diagnostics}' out/agentic/recheck/<scenario_id>/response.json

# The implementation result
jq '{ok, message}' out/agentic/recheck/<scenario_id>/implementation_result.json

# The scenario query + expected assessment
jq '{query, assessment}' tests/live_agentic_harness/scenarios/<scenario_id>.json
```

## How to re-run ALL scenarios in this category
```bash
# Create a temp dir with just these scenarios
TMP=$(mktemp -d)
cp tests/live_agentic_harness/scenarios/audio-acestep-audio-latent-workflow-with-vocal-separ-0eb676.json "$TMP/"
cp tests/live_agentic_harness/scenarios/multi-crops-face-previews-it-sets.json "$TMP/"
cp tests/live_agentic_harness/scenarios/multi-image-to-video-with-upscaling-and-color-matchi-359848.json "$TMP/"
cp tests/live_agentic_harness/scenarios/video-svd-image-to-video-generation-fc240f.json "$TMP/"
.venv/bin/python -m tests.live_agentic_harness.runner \
  --tag recheck-widget_shape_guard --scenarios-dir "$TMP" \
  --output-base out/agentic --max-workers 8 --json
```
