# Workflow Precedent Scenario Coverage

This note summarizes a 10-scenario DeepSeek fanout and a Codex synthesis over
those reports. The goal was to test whether the graph-native,
Python-rendered-evidence, `PrecedentAdaptationPlan` design covers real user task
classes.

## Position

The design is strong as a specialized pattern-adaptation lane. It should not be
the universal executor.

Graph-native inspection and Python-rendered evidence should be a shared
substrate across VibeComfy, but `PrecedentAdaptationPlan` should be used only
for true workflow-pattern changes where a known-good precedent helps.

## Scenario Matrix

| # | User task class | Route | Use precedent research? | Fit |
| --- | --- | --- | --- | --- |
| 1 | Simple parameter edit | `direct_edit` | No | Poor fit; precedent machinery is unnecessary. |
| 2 | Explain current graph | `inspect_only` | No | Partial; slices/Python evidence can help explanation, but no edit. |
| 3 | Small obvious node add | `direct_edit` | No | Poor fit; use current graph sockets and edit ops directly. |
| 4 | Multi-node local precedent | `precedent_research` | Yes | Strong fit. |
| 5 | External workflow precedent | `precedent_research` | Yes, gated | Partial; needs hardened external intake. |
| 6 | Ambiguous audio request | `clarify` then maybe `precedent_research` | Only after clarification | Partial; must stop before guessing. |
| 7 | Model/asset config swap | `asset_lookup` then `direct_edit` | Usually no | Poor fit; use registry/asset validation. |
| 8 | Broken/dangling graph repair | `diagnose_repair` | Maybe as confirmation | Partial; diagnose current graph first. |
| 9 | Composite multi-pattern edit | `decompose` then iterative `precedent_research` | Per subgoal | Partial; avoid merging unrelated precedents. |
| 10 | Preview/eval intermediate node | `subgraph_preview` | No | Poor fit; use runtime eval/preview route. |

## Findings

### The Route Taxonomy Is Load-Bearing

The strongest finding is that the precedent lane must be gated by task class.
The system needs sibling routes:

- `direct_edit`
- `inspect_only`
- `precedent_research`
- `clarify`
- `asset_lookup`
- `diagnose_repair`
- `decompose`
- `subgraph_preview`
- `respond_only`

Without these routes, agents will drag simple edits, repairs, previews, and
asset swaps into expensive precedent research.

### PrecedentAdaptationPlan Is The Right Handoff For Pattern Edits

The useful bridge is:

```text
selected_slice + anchor_bindings + required_new_nodes + required_rewires
-> edit_ops[]
-> candidate_graph
-> structural validation
-> semantic validation
-> emitted Python / Comfy API
```

This is narrower and more practical than a total graph-to-graph mapping. It
records only the anchors and changes needed for the selected slice.

### External Precedents Need Stronger Intake

External public workflows should not enter the precedent store until they pass:

- preview-before-fetch;
- fetch caps and retry caps;
- content-type and byte-size gates;
- JSON-as-data parsing;
- class-type/dependency allowlist checks;
- conversion validation;
- `trust_tier`;
- `loss_summary`;
- dedupe by URL and content hash;
- dry-run Hivemind envelope before upload.

### Validation Must Be Task-Typed

Different routes need different validators:

- widget update: field changed and graph still compiles;
- obvious node add: target node exists and is connected;
- pattern adaptation: semantic checks from `PrecedentAdaptationPlan`;
- repair: original failure is absent and no new dangling nodes appear;
- preview/eval: subgraph can be compiled/evaluated without mutating the
  durable workflow;
- asset swap: required models/assets resolve.

### Composite Edits Need Decomposition

For tasks like "add pose guidance and a LoRA stack", fetch one precedent slice
per subgoal, apply and validate each subgoal, then continue. Do not merge two
unrelated precedents into an invented hybrid pattern.

## Documentation Changes Implied

- Add a "Scope and Non-Goals" section to the main plan.
- Add a routing matrix and full route set.
- Add `task_class`, `pattern_category`, `model_families`, and explicit
  clarification fields to classification.
- Add the full `PrecedentAdaptationPlan` schema.
- Add a worked example from selected slice through edit ops and validation.
- Add explicit external-ingestion policy with trust tiers and loss summaries.
- Add composite-edit decomposition guidance.
- Add a "Do Not Use This Route For..." section to keep the precedent lane
  narrow.

## Bottom Line

Keep the graph-native core. Keep Python as readable evidence and final emitted
representation. Keep `PrecedentAdaptationPlan`, but narrow it to the
pattern-adaptation lane. The design fails only if the system treats precedent
research as the road for every non-trivial user request.
