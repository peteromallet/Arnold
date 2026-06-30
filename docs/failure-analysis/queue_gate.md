# Queue-Gate Blocks

**2 scenario(s)** in this category from the clean-100 eval (40/100).

## The issue
The queue-validation gate (`queue_validate_ok`) blocks edits because of pre-existing schema-less nodes or output-arity disagreements. These are scenarios where the edit itself is valid but the queue gate flags an unrelated pre-existing issue in the graph.

## Affected scenarios

| Scenario ID | Root cause excerpt |
|---|---|
| `image-two-stage-qwen-image-generation` | **Failure:** The assessor fails the scenario because `gates.queue_validate_ok` is **`false`** despite zero queue blocker |
| `multi-image-to-video-generation-with` | **Failure:** `queue_validate_ok: false` — the only gate that failed. Every other gate (`ir_validate_ok`, `lower_ok`, `py |

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
cp tests/live_agentic_harness/scenarios/image-two-stage-qwen-image-generation.json "$TMP/"
cp tests/live_agentic_harness/scenarios/multi-image-to-video-generation-with.json "$TMP/"
.venv/bin/python -m tests.live_agentic_harness.runner \
  --tag recheck-queue_gate --scenarios-dir "$TMP" \
  --output-base out/agentic --max-workers 8 --json
```
