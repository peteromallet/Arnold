# Cross-Domain Over-Rejection (d9188411 / PR #117)

**8 scenario(s)** in this category from the clean-100 eval (40/100).

## The issue
Commit `d9188411` added a media-domain gate to precedent selection that rejects slices whose domain differs from the target graph. The intent was correct (reject an image-domain slice binding to a video graph). But the gate is **too aggressive** — it also rejects valid cross-media adapter slices (e.g., an image-to-video adapter that bridges domains correctly) + same-domain slices that happen to have different media subtypes. These scenarios previously got correct edits from (possibly cross-domain) precedent slices that d9188411 now rejects → the agent falls back to "no precedent" → refuses to edit.

## Affected scenarios

| Scenario ID | Root cause excerpt |
|---|---|
| `3d-3d-model-generation-and-rigging-workflow-90a1d5` | **Failure:** The executor classified this as `route: "clarify"` (non-applyable), producing `no_candidate_reason: "route_ |
| `hotshot-16-frames-agent-edit` | **Failure:** `queue_validate_ok: false` — the queue-validation gate failed. The assessor (`assessor.py:276-285`) treats  |
| `image-auraflow-image-generation-with-qwen-clip-9a3109` | **Failure:** The assessor reported **`gates` failure: `queue_validate_ok` is `false`**. The harness sees `expect_graph_c |
| `image-background-removal-and-grid-composition-54a681` | **Failure:** `gates.queue_validate_ok = false` — the assessor's `gates` check fires because `queue_validate_ok` is `Fals |
| `multi-deforum-stable-diffusion-animation-with-ip-ada-78afac` | **Failure:** `no_candidate_reason: "implementation_failed"` \| `failure_stage: "implement"` \| `failure_kind: "ModelMist |
| `multi-wanvideo-vace-inpainting-and-compositing-workf-b11a56` | **Failure:** `graph_unchanged: true`, `no_candidate_reason: "no_changes"`. The agent returned: *"I could not find a work |
| `video-generates-a-video-from-a` | **Failure:** The assessor flags `queue_validate_ok: false` in the response gates as a hard error. The agent produced a v |
| `video-ltx-video-upscaling-and-enhancement` | **Failure:** `RefusedEmit` at the `widget_shape` gate during `implement` stage. Node `5186` (`PrimitiveInt`) was refused |

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
cp tests/live_agentic_harness/scenarios/3d-3d-model-generation-and-rigging-workflow-90a1d5.json "$TMP/"
cp tests/live_agentic_harness/scenarios/hotshot-16-frames-agent-edit.json "$TMP/"
cp tests/live_agentic_harness/scenarios/image-auraflow-image-generation-with-qwen-clip-9a3109.json "$TMP/"
cp tests/live_agentic_harness/scenarios/image-background-removal-and-grid-composition-54a681.json "$TMP/"
cp tests/live_agentic_harness/scenarios/multi-deforum-stable-diffusion-animation-with-ip-ada-78afac.json "$TMP/"
cp tests/live_agentic_harness/scenarios/multi-wanvideo-vace-inpainting-and-compositing-workf-b11a56.json "$TMP/"
cp tests/live_agentic_harness/scenarios/video-generates-a-video-from-a.json "$TMP/"
cp tests/live_agentic_harness/scenarios/video-ltx-video-upscaling-and-enhancement.json "$TMP/"
.venv/bin/python -m tests.live_agentic_harness.runner \
  --tag recheck-cross_domain_over_rejection --scenarios-dir "$TMP" \
  --output-base out/agentic --max-workers 8 --json
```
