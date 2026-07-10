# Pre-existing Bug: _iter_graph_nodes dict-form (a5ddbbce)

**8 scenario(s)** in this category from the clean-100 eval (40/100).

## The issue
A pre-existing bug in `vibecomfy/executor/core.py` (commit `a5ddbbce` "Consolidate watchdog and agentic pipeline fixes"). The `_iter_graph_nodes()` function extracts nodes from the graph for inspection, but when the graph uses VibeComfy's dict-form `nodes: {}` (instead of ComfyUI's list-form `nodes: []`), the dict branch falls through to `graph.items()` instead of `nodes.items()` — so graph inspection returns empty `{}`. This means the agent can't see what nodes exist in its own graph → can't do parameter tweaks on existing nodes → refuses with "could not find precedent/schema" even though the node is right there.

## Affected scenarios

| Scenario ID | Root cause excerpt |
|---|---|
| `3d-3d-model-generation-and-rigging-from-image-352066` | **Failure:** Route = `clarify`, `no_candidate_reason = "route_not_applyable"`, `graph_unchanged = true`. The classificat |
| `image-image-to-image-with-controlnet-and-dwpreproces-49d057` | **Failure:** `queue_validate_ok: false` — the assessor flags this gate as failed (severity=error), which blocks the scen |
| `image-sd3-image-generation-with-controlnet-19d221` | **Failure:** The `queue_validate_ok` gate is **false**, even though the agent DID successfully edit the graph (changed ` |
| `image-style-transfer-using-ip-adapter` | **Failure:** The assessor flags `queue_validate_ok: false` as a gate failure. Since the scenario expects `graph_changed: |
| `multi-animatediff-video-face-swapping-with-deflicker-506ebd` | **Failure:** `gates.queue_validate_ok: false` — the assessor flags this as an error because `expect_graph_changed: true` |
| `multi-image-to-video-generation-with-2` | **Failure:** `gates.queue_validate_ok = false` — the assessor flags this as an error because `expect_graph_changed = tru |
| `video-video-frame-by-frame-style` | **Failure:** Assessor `gates` check — `queue_validate_ok: false`. The assessor flags *any* `false` gate when `expect_gra |
| `video-video-generation-from-resized-image` | **Failure:** The assessor flags `gates.queue_validate_ok: false` as a hard error when `expect_graph_changed: true`. The  |

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
cp tests/live_agentic_harness/scenarios/3d-3d-model-generation-and-rigging-from-image-352066.json "$TMP/"
cp tests/live_agentic_harness/scenarios/image-image-to-image-with-controlnet-and-dwpreproces-49d057.json "$TMP/"
cp tests/live_agentic_harness/scenarios/image-sd3-image-generation-with-controlnet-19d221.json "$TMP/"
cp tests/live_agentic_harness/scenarios/image-style-transfer-using-ip-adapter.json "$TMP/"
cp tests/live_agentic_harness/scenarios/multi-animatediff-video-face-swapping-with-deflicker-506ebd.json "$TMP/"
cp tests/live_agentic_harness/scenarios/multi-image-to-video-generation-with-2.json "$TMP/"
cp tests/live_agentic_harness/scenarios/video-video-frame-by-frame-style.json "$TMP/"
cp tests/live_agentic_harness/scenarios/video-video-generation-from-resized-image.json "$TMP/"
.venv/bin/python -m tests.live_agentic_harness.runner \
  --tag recheck-pre_existing_bug --scenarios-dir "$TMP" \
  --output-base out/agentic --max-workers 8 --json
```
