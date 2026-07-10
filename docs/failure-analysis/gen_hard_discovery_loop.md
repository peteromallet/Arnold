# Genuine-Hard: Agent Stuck in Discovery Loop

**2 scenario(s)** in this category from the clean-100 eval (40/100).

## The issue
The agent gets stuck in a research/search loop — repeatedly calling `search(focus_types=[...])` or `research(...)` without converging to an edit. Typically 5-7 turns of discovery with `0 landed ops` before the scenario times out or the agent gives up. The agent finds the node class signature but can't figure out how to wire it, or keeps searching for a "better" precedent instead of applying what it found.

**Fix needed:** a research-turn cap — after 3-5 consecutive non-landing search/research turns, the agent must either apply the best schema-backed edit OR return no-candidate (stop researching). Do NOT raise the per-scenario timeout — cap the churn.

## Affected scenarios

| Scenario ID | Root cause excerpt |
|---|---|
| `video-anime-video-to-video-with-controlnet-and-openp-cb` | 6 turns of `search()` calls, never converging to an edit |
| `video-ltx-video-upscaling-and-enhancement` | `PrimitiveInt` node with `"widget_1": "fixed"` — widget serialization issue causing the agent to loop |

## Where to find the evidence

Each scenario's full artifacts (response.json, implementation_result.json, flow_metadata.json, research.json) are under:
```
out/agentic/clean-100/<scenario_id>/
```

For comparison, the iter5 run (57/100, before the regression):
```
out/agentic/iter5-100/<scenario_id>/
```

Look at the batch-turn trace to see the loop:
```bash
jq '.response.report.executor.implementation | .batch_turns | length' out/agentic/clean-100/<sid>/response.json
# Count the turns — >5 with 0 landed = discovery loop

jq '.response.report.executor.implementation.batch_turns[] | {landed: .landed_op_count, batch: .batch[:80]}' out/agentic/clean-100/<sid>/response.json
# See each turn's batch call + whether it landed
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
jq '.response | {ok, graph_unchanged, no_candidate_reason, outcome, gates, diagnostics}' out/agentic/recheck/<scenario_id>/response.json
jq '{ok, message}' out/agentic/recheck/<scenario_id>/implementation_result.json
jq '{query, assessment}' tests/live_agentic_harness/scenarios/<scenario_id>.json
```
