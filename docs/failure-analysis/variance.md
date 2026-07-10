# DeepSeek Variance

**3 scenario(s)** in this category from the clean-100 eval (40/100).

## The issue
Pure DeepSeek model reasoning variance — the agent made a different (wrong) choice on this run vs a previous run, with no code change contributing. These scenarios pass on some runs and fail on others (±4 variance).

## Affected scenarios

| Scenario ID | Root cause excerpt |
|---|---|
| `3d-3d-inpainting-with-controlnet-and-detail-daemo-c24aa2` | **Failure:** `graph_unchanged: true`, `no_candidate_reason: "no_changes"` — the agent issued `clarify()` and exited with |
| `multi-video-based-character-replacement-using` | **Failure:** The agent never landed an edit. All 8 gates are `false` (only `state_match_ok: true`). The only edit attemp |
| `multi-wan-vace-video-retargeting-driven` | ### Failure gate |

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
cp tests/live_agentic_harness/scenarios/3d-3d-inpainting-with-controlnet-and-detail-daemo-c24aa2.json "$TMP/"
cp tests/live_agentic_harness/scenarios/multi-video-based-character-replacement-using.json "$TMP/"
cp tests/live_agentic_harness/scenarios/multi-wan-vace-video-retargeting-driven.json "$TMP/"
.venv/bin/python -m tests.live_agentic_harness.runner \
  --tag recheck-variance --scenarios-dir "$TMP" \
  --output-base out/agentic --max-workers 8 --json
```
