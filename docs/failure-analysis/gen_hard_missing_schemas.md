# Genuine-Hard: Missing Custom-Node Schemas

**6 scenario(s)** in this category from the clean-100 eval (40/100).

## The issue
The agent genuinely cannot edit because the target node's schema is not available — the custom node pack is not installed, not in the Comfy Registry, and not in any web-accessible workflow. The agent correctly searches + researches but finds nothing. Examples: `Rodin3D_Regular` (3D model generation), `UltraShapeRefine` (3D shape), `AudioLDM2` (audio), `MTCNN`/`RetinaFace` (face detection), `FloatSlider` (UI widgets), `LambdaLambert` (character replacement). **These need a provisional-schema source** (extract schemas from GitHub node-class `__init__` signatures or the Comfy Registry).

## Affected scenarios

| Scenario ID | Root cause excerpt |
|---|---|
| `3d-3d-model-generation-and-preview-workflow-cc0df7` | **Failure:** `no_candidate_reason: "no_changes"`, `graph_unchanged: true`. The agent returned a no-op with the message:  |
| `3d-3d-shape-generation-and-export-workflow-8800a9` | Now I have the full picture. Let me trace through the exact failure mechanism. |
| `3d-converts-image-to-3d-model` | **Failure:** The assessor's `gates` check — `queue_validate_ok: false` is the sole failing gate. All other gates pass (` |
| `audio-ltx-video-and-audio-generation-with-lora-and-m-c80bbf` | **Failure:** `graph_changed` check fails — the harness expects `graph_changed: true` but the agent returned `graph_uncha |
| `image-face-detection-and-cropping-workflow-949658` | **Failure:** `no_candidate_reason: "no_changes"`, `graph_unchanged: true`. All gates failed (`ir_validate_ok: false`, `u |
| `image-image-comparison-and-enhancement-with-florence-007018` | **Failure:** `failure_kind: SchemaGap` — the agent exhausted its budget (3 consecutive errors in 6 turns) because requir |

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
cp tests/live_agentic_harness/scenarios/3d-3d-model-generation-and-preview-workflow-cc0df7.json "$TMP/"
cp tests/live_agentic_harness/scenarios/3d-3d-shape-generation-and-export-workflow-8800a9.json "$TMP/"
cp tests/live_agentic_harness/scenarios/3d-converts-image-to-3d-model.json "$TMP/"
cp tests/live_agentic_harness/scenarios/audio-ltx-video-and-audio-generation-with-lora-and-m-c80bbf.json "$TMP/"
cp tests/live_agentic_harness/scenarios/image-face-detection-and-cropping-workflow-949658.json "$TMP/"
cp tests/live_agentic_harness/scenarios/image-image-comparison-and-enhancement-with-florence-007018.json "$TMP/"
.venv/bin/python -m tests.live_agentic_harness.runner \
  --tag recheck-gen_hard_missing_schemas --scenarios-dir "$TMP" \
  --output-base out/agentic --max-workers 8 --json
```
