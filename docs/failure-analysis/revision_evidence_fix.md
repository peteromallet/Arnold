# Revision-Evidence Fix Causing New Failures (my GPT-5.4 change)

**2 scenario(s)** in this category from the clean-100 eval (40/100).

## The issue
An uncommitted change to `vibecomfy/executor/revision_evidence.py` (from the GPT-5.4 regression fix) that allows revise to proceed on graphs with pre-existing missing models/packs. The intent was correct (relax the revision-evidence gate), but the implementation is **too permissive** in some cases — it lets the agent proceed when it shouldn't, or changes the evidence assessment in a way that breaks downstream gates.

## Affected scenarios

| Scenario ID | Root cause excerpt |
|---|---|
| `3d-generates-a-3d-mesh-from` | **Failure:** `queue_validate_ok: false` — the only failing gate in the response envelope. The assessor (`tests/live_agen |
| `video-wan-alpha-video-generation-with-lora-and-gguf-6a9e20` | **Failure:** The assessor flags `gates.queue_validate_ok: false` as a blocking error. Despite the agent **successfully** |

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
cp tests/live_agentic_harness/scenarios/3d-generates-a-3d-mesh-from.json "$TMP/"
cp tests/live_agentic_harness/scenarios/video-wan-alpha-video-generation-with-lora-and-gguf-6a9e20.json "$TMP/"
.venv/bin/python -m tests.live_agentic_harness.runner \
  --tag recheck-revision_evidence_fix --scenarios-dir "$TMP" \
  --output-base out/agentic --max-workers 8 --json
```
