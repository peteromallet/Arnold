# Research -> Plan -> Execute Megaplan Epic

Generated from a GPT-5.5 Codex epic-architecture pass over the current overhaul doc, three GPT-5.5 critique docs, and the prior single-sprint prep memo.

## Verdict

This should be an epic, not one megaplan. The work has multiple architectural decision points whose outputs need to become handoff artifacts before the next sprint can safely proceed:

1. Typed authority contracts and deterministic graph evaluators.
2. Deterministic plan construction and routing from precedent-backed research.
3. Execute-stage enforcement, candidate gating, and artifacts.
4. Regression, live/agentic validation, and rollout guardrails.

Flattening these into one sprint risks preserving the core failure mode: a model can add plausible nodes, call done, and produce an applyable candidate even though the required graph topology is incomplete.

## Epic Goal

Deliver a durable `research -> plan -> execute` path for precedent-backed structural agent edits so research evidence becomes a typed, evaluable graph contract, execution implements that contract, and no candidate/apply path can accept semantically incomplete graph edits.

The concrete acceptance anchor is HotShotXL image-to-video: adding AnimateDiff nodes as disconnected sidecars must be rejected; a complete graph where motion model reaches sampler, an active 8-frame path exists, and decoded images reach a video terminal must pass.

## Milestones

| Milestone | Outcome | Profile |
|---|---|---|
| M1 Contracts And Evaluator | Typed `ExecutionPlan`/`PlanEvaluation` contracts plus deterministic graph validators | `partnered-5 / full / high` |
| M2 Plan Builder And Routing | Deterministic plan builder, minimal research normalization, classifier trigger rules | `partnered-5 / full / high` |
| M3 Execute Enforcement And Artifacts | Execute prompt status, `done()` guard, candidate/apply gating, persisted artifacts | `partnered-5 / full / high` |
| M4 Regression, Rollout, And Guardrails | HotShotXL tests, ordinary-edit regression coverage, rollout docs/audit checks | `partnered-5 / full / medium` |

## Chain Files

```text
.megaplan/briefs/research-plan-execute-epic/chain.yaml
.megaplan/briefs/research-plan-execute-epic/m1-contracts-evaluator.md
.megaplan/briefs/research-plan-execute-epic/m2-plan-builder-routing.md
.megaplan/briefs/research-plan-execute-epic/m3-execute-enforcement-artifacts.md
.megaplan/briefs/research-plan-execute-epic/m4-regression-rollout.md
```

## Start Command

```bash
PYENV_VERSION=3.11.11 python -m arnold.pipelines.megaplan chain start --spec .megaplan/briefs/research-plan-execute-epic/chain.yaml
```

## Anti-Scope

- No model-backed planner in this epic.
- No broad provider/custom-node installation search.
- No frontend redesign.
- No queue-validation rewrite.
- No general workflow-family expansion beyond HotShotXL/video fixtures needed to prove the pattern.
- No reuse of `PrecedentAdaptationPlan` as the authoritative execution plan.
