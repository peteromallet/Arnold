# Other / Unclear Failures

**4 scenario(s)** in this category from the clean-100 eval (40/100).

## The issue
Failures that didn't clearly fit into any category, or where the attribution was ambiguous.

## Affected scenarios

| Scenario ID | Root cause excerpt |
|---|---|
| `audio-transcribes-audio-appends-text-regenerates` | **Failure:** `RefusedEmit` — widget_shape guard blocked two `ShowText\|pysssss` nodes (72, 88) with verdict `refuse`, re |
| `image-image-to-image-with-stable-zero123-and-backgro-def5b5` | ### The Failure |
| `video-video-combine-with-image-loading-5b31ce` | **Failure:** `ir_validate_ok: false` — **incompatible socket types**. The agent correctly proposed adding an `ImageBatch |
| `video-wan2-2-text-to-video-with-dual-unet-and-model-03fced` |  |

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
cp tests/live_agentic_harness/scenarios/audio-transcribes-audio-appends-text-regenerates.json "$TMP/"
cp tests/live_agentic_harness/scenarios/image-image-to-image-with-stable-zero123-and-backgro-def5b5.json "$TMP/"
cp tests/live_agentic_harness/scenarios/video-video-combine-with-image-loading-5b31ce.json "$TMP/"
cp tests/live_agentic_harness/scenarios/video-wan2-2-text-to-video-with-dual-unet-and-model-03fced.json "$TMP/"
.venv/bin/python -m tests.live_agentic_harness.runner \
  --tag recheck-other --scenarios-dir "$TMP" \
  --output-base out/agentic --max-workers 8 --json
```
