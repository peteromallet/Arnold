---
name: epic-blitz
description: Three-round adversarial critique of epic drafts (high / mid / low abstraction) with revision after each round. Produces a chain-ready revised epic.
---

# Epic Blitz

A three-round pipeline for rigorous epic critique and revision. Fifteen
independent critics across three abstraction levels (high, mid, low) review
the epic in panels of five. After each panel, a senior reviser adjudicates
the findings — accepting, rejecting, deferring, clarifying, or escalating —
and produces a revised epic. The final readiness stage assesses whether the
epic is ready for `megaplan chain` decomposition into milestone briefs.

## Runtime

`epic-blitz` is a native-default converted pipeline. Fresh runs through
`megaplan run epic-blitz ...` or `arnold pipelines run epic-blitz ...` persist
runtime ownership in `state.json.runtime_envelope.runtime` and
`state.json.meta.executor`. During the M7 deprecation window, the derived graph
remains available as a compatibility fallback: pass `--runtime graph` (or the
deprecated `--executor graph`) for a fresh run that must use the graph
executor. Existing graph-born plan directories keep resuming on graph.
Native-born runs resume on native, and corrupt native cursors fail closed
rather than silently falling back to graph.

## When to invoke Epic Blitz

Use Epic Blitz when:

- You have a draft epic document and want adversarial review before committing to chain planning.
- You want to surface strategic risks, missing abstractions, decomposition flaws, convention mismatches, and implementation feasibility gaps.
- You want a structured, artifact-oriented critique process rather than ad-hoc human review.
- You need a readiness assessment before running `megaplan chain`.

Do NOT use Epic Blitz for:

- Prose or document review (use `writing-panel-strict` for that).
- Sprint-level critique (Epic Blitz is for epic-level documents).

## Required input

- `draft` (file, required): Path to the epic markdown draft to review.

## Usage

```bash
# Run with default profile
megaplan run epic-blitz path/to/epic.md

# Run with explicit inputs flag
megaplan run epic-blitz --inputs draft=path/to/epic.md

# Run with a specific profile
megaplan run epic-blitz path/to/epic.md --profile @epic-blitz:standard
```

## Pipeline flow

Epic Blitz runs three critique-and-revision rounds, each at a different
abstraction level:

### Round 1: High abstraction

1. **High Panel** (parallel) — five critics review the draft:
   - `existing_system_reuse` — does the repo already solve this?
   - `conceptual_fit` — does this belong in megaplan's model?
   - `missing_abstraction` — is there a shared abstraction opportunity?
   - `epic_decomposition` — are milestones sliced correctly?
   - `strategic_risk` — is this solving the right problem?
2. **High Revise** — senior reviser adjudicates findings and produces a revised epic.

### Round 2: Mid abstraction

3. **Mid Panel** (parallel) — five critics review the revised epic:
   - `codebase_convention_fit` — does the approach match existing patterns?
   - `data_artifact_model` — are files and schemas shaped correctly?
   - `orchestration_semantics` — do phase transitions and failures make sense?
   - `agent_model_assignment` — are the right models on the right jobs?
   - `blast_radius` — what could regress?
4. **Mid Revise** — senior reviser adjudicates findings and produces a further revised epic.

### Round 3: Low abstraction

5. **Low Panel** (parallel) — five critics review the revised epic:
   - `implementation_feasibility` — can an agent execute without guessing?
   - `testability` — are concrete tests specified?
   - `edge_cases` — what about empty findings, malformed output, interrupted runs?
   - `cli_ux_details` — are names, flags, and errors clear?
   - `migration_backcompat` — does this preserve existing behavior?
6. **Readiness** — terminal reviser produces the final epic and chain-readiness assessment.

## Expected artifacts

After a successful run, the plan directory contains:

```
<plan_dir>/
├── high_panel/
│   ├── existing_system_reuse/v1.md
│   ├── conceptual_fit/v1.md
│   ├── missing_abstraction/v1.md
│   ├── epic_decomposition/v1.md
│   └── strategic_risk/v1.md
├── high_revise/v1.md
├── mid_panel/
│   ├── codebase_convention_fit/v1.md
│   ├── data_artifact_model/v1.md
│   ├── orchestration_semantics/v1.md
│   ├── agent_model_assignment/v1.md
│   └── blast_radius/v1.md
├── mid_revise/v1.md
├── low_panel/
│   ├── implementation_feasibility/v1.md
│   ├── testability/v1.md
│   ├── edge_cases/v1.md
│   ├── cli_ux_details/v1.md
│   └── migration_backcompat/v1.md
├── readiness/v1.md
└── state.json
```

The terminal artifact is `readiness/v1.md` — the final revised epic with a
chain-readiness assessment.

## Profiles

| Profile | Description |
|---------|-------------|
| `@epic-blitz:standard` | Default — Claude low-effort for all 15 critics and 3 revisers |

## Notes

- Epic Blitz v1 is fully non-interactive. All 15 critics and 3 revisers run without human gates.
- Each panel's critics receive the latest revised epic (not the original draft), ensuring later rounds build on prior revisions.
- Critics produce artifact-oriented findings with IDs, severity, rationale, evidence, and proposed actions.
- Revisers produce decision tables tracking every finding's disposition.
