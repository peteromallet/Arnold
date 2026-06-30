# Genuine-Hard: Architecture / Serialization Issues

**2 scenario(s)** in this category from the clean-100 eval (40/100).

## The issue
Code-level serialization or architecture issues that prevent valid edits from being applied. These are **pipeline bugs** (not agent-reasoning failures) that affect specific node types:

- **`ShowText|pysssss`**: LiteGraph serialization carries an inconsistent widget count — the node has 2 widgets in the UI but the serialization reports a different count, causing the widget-shape fence to flag it as malformed overflow.
- **`UNKNOWN` socket types**: two code paths in the pipeline handle `UNKNOWN` target socket types inconsistently — one treats them as compatible (any-type), the other rejects them as incompatible. This causes valid edits that wire to an `UNKNOWN` socket to be blocked.

**Fix needed:** normalize the widget-count reporting for custom nodes like `ShowText|pysssss` (trust the UI count); make `UNKNOWN` socket handling consistent across all code paths (treat as compatible by default).

## Affected scenarios

| Scenario ID | Root cause excerpt |
|---|---|
| `multi-image-to-video-with-llm` | `ShowText\|pysssss` LiteGraph serialization carries inconsistent widget count → widget-shape fence blocks |
| `multi-svd-image-to-video-with-webp-and-png-output-bd3af` | `UNKNOWN` socket type inconsistency between two code paths |

## Where to find the evidence

Each scenario's full artifacts are under:
```
out/agentic/clean-100/<scenario_id>/
```

For comparison, the iter5 run:
```
out/agentic/iter5-100/<scenario_id>/
```

Look at the widget-shape / socket diagnostics:
```bash
jq '.response.diagnostics[] | select(.severity == "error")' out/agentic/clean-100/<sid>/response.json
# See the specific widget-count or socket-type error

jq '.response | {ok, graph_unchanged, no_candidate_reason}' out/agentic/clean-100/<sid>/response.json
```

## How to re-run a scenario

```bash
.venv/bin/python -m tests.live_agentic_harness.runner \
  --single tests/live_agentic_harness/scenarios/<scenario_id>.json \
  --tag recheck --output-base out/agentic \
  --single-out /tmp/recheck.json
```

Then inspect:
```bash
jq '.response | {ok, graph_unchanged, no_candidate_reason, outcome, gates, diagnostics}' out/agentic/recheck/<scenario_id>/response.json
jq '{query, assessment}' tests/live_agentic_harness/scenarios/<scenario_id>.json
```
