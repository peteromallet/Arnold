# Genuine-Hard: Missing Precedent Data

**8 scenario(s)** in this category from the clean-100 eval (40/100).

## The issue
The research knowledge base lacks workflow precedents for the requested edit pattern. The agent searches Hivemind workflows + Discord messages but finds zero parseable precedents for the specific combination (e.g., Flux + ControlNet inpainting, SVD animation, llama-cpp instruct). The agent can't generate a structurally valid adaptation plan without a precedent to follow. **These need richer precedent data** (more diverse workflows in the KB).

## Affected scenarios

| Scenario ID | Root cause excerpt |
|---|---|
| `3d-3d-model-generation-and-retargeting-workflow-f65774` | **Failure:** `graph_unchanged: true`, `no_candidate_reason: "no_changes"`, outcome `kind: "clarify"`. The agent asked th |
| `image-flux-image-inpainting-and-compositing-with-con-00444a` | **Failure:** `UnsupportedNonDAG` at `failure_stage: implement`. The exact message: *"This request requires custom code o |
| `image-kolors-image-generation-with-segs-detailer-and-d813fe` | **Failure:** `graph_unchanged: true`, `no_candidate_reason: "no_changes"`, ALL gates failed (`ir_validate_ok`, `lower_ok |
| `image-llama-cpp-instruct-image-preview-and-save-5b54bf` | **Failure:** `no_candidate_reason: "no_changes"` — the agent produced zero edit operations. The adaptation plan shows `s |
| `multi-image-to-video-with-llm` | **Failure:** `RefusedEmit` at the `implement` stage. The widget-shape guard blocked node **180** (`ShowText\|pysssss`) w |
| `multi-svd-image-to-video-with-webp-and-png-output-bd3afb` | **Failure:** `incompatible_socket_types` — every edit batch rolled back because `SaveImage.images` is typed `UNKNOWN` in |
| `multi-wan2-2-animate-video-with-pose-and-segmentatio-1cc457` | **Failure:** `RefusedEmit` — the widget-shape guard blocked the candidate graph at emit time. 5 existing `PrimitiveInt`  |
| `video-anime-video-to-video-with-controlnet-and-openp-cb5cd2` | **Failure:** `no_candidate_reason: "no_changes"` / `graph_unchanged: true`. The agent exited via `pure_clarify` after 6  |

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
cp tests/live_agentic_harness/scenarios/3d-3d-model-generation-and-retargeting-workflow-f65774.json "$TMP/"
cp tests/live_agentic_harness/scenarios/image-flux-image-inpainting-and-compositing-with-con-00444a.json "$TMP/"
cp tests/live_agentic_harness/scenarios/image-kolors-image-generation-with-segs-detailer-and-d813fe.json "$TMP/"
cp tests/live_agentic_harness/scenarios/image-llama-cpp-instruct-image-preview-and-save-5b54bf.json "$TMP/"
cp tests/live_agentic_harness/scenarios/multi-image-to-video-with-llm.json "$TMP/"
cp tests/live_agentic_harness/scenarios/multi-svd-image-to-video-with-webp-and-png-output-bd3afb.json "$TMP/"
cp tests/live_agentic_harness/scenarios/multi-wan2-2-animate-video-with-pose-and-segmentatio-1cc457.json "$TMP/"
cp tests/live_agentic_harness/scenarios/video-anime-video-to-video-with-controlnet-and-openp-cb5cd2.json "$TMP/"
.venv/bin/python -m tests.live_agentic_harness.runner \
  --tag recheck-gen_hard_missing_precedents --scenarios-dir "$TMP" \
  --output-base out/agentic --max-workers 8 --json
```
