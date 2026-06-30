# Batch-REPL Queue-Validation Gap

**3 scenario(s)** in this category from the clean-100 eval (40/100).

## The issue
A pre-existing architecture gap: the batch-REPL product path (`_run_batch_repl_product_path`) has no post-agent-batch summarize/queue-validate stage. When the agent successfully makes a batch edit, `queue_validate_ok` stays **false-by-default** (the queue validation never runs for batch-repl candidates). The assessor treats any false gate as a hard error when `expect_graph_changed: true` → the scenario fails even though the agent made the correct edit.

## Affected scenarios

| Scenario ID | Root cause excerpt |
|---|---|
| `image-sdxl-txt2img-cat-in-spacesuit` | **Failure:** `queue_validate_ok: false` in the response gates. The assessor's false-gate check (`assessor.py:273-280`) f |
| `image-wan2-2-video-generation-with-chroma-lut-and-fi-a7ecc5` | **Failure:** The assessor flagged `expect_graph_changed=True` but found a false gate: **`queue_validate_ok: false`**. Th |
| `multi-image-to-3d-object-generation-with-background-1a7f84` | **Failure:** The assessor flags `queue_validate_ok: false` as a failing gate. The scenario expects `graph_changed: true` |

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
cp tests/live_agentic_harness/scenarios/image-sdxl-txt2img-cat-in-spacesuit.json "$TMP/"
cp tests/live_agentic_harness/scenarios/image-wan2-2-video-generation-with-chroma-lut-and-fi-a7ecc5.json "$TMP/"
cp tests/live_agentic_harness/scenarios/multi-image-to-3d-object-generation-with-background-1a7f84.json "$TMP/"
.venv/bin/python -m tests.live_agentic_harness.runner \
  --tag recheck-batch_repl_gap --scenarios-dir "$TMP" \
  --output-base out/agentic --max-workers 8 --json
```
