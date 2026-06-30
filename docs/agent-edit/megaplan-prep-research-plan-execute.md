# Megaplan Prep Memo: Research -> Plan -> Execute Overhaul

## 1. Verdict On Prior Prep

The prior prep is strong and mostly runnable: it identifies the real failure as a missing execution contract, correctly refuses to reuse `PrecedentAdaptationPlan`, and anchors the sprint around `ExecutionPlan`, `PlanEvaluation`, `plan_validate_ok`, artifacts, and HotShotXL negative tests.

Corrections:

- It is a little too broad if “research normalization” is treated as full workflow-pattern extraction. Make that minimal and HotShotXL/video-pattern focused for this sprint.
- `partnered-5` is spendy. `partnered-4/full/high` would probably be enough, but `partnered-5` is defensible because this creates a new semantic gate whose failures can pass ordinary tests while producing applyable broken graph edits.
- Do not add CLI extras. Use exactly the requested init shape.
- Keep the sprint to deterministic planning/evaluation. No model-backed planner, no frontend, no general research-system rewrite.

## 2. Recommended Run Config

`partnered-5 / full / high`

Overall plan difficulty: `5/5`; selected profile: `partnered-5`; because the dangerous planning failure is a bad cross-cutting contract/gate design that can still pass syntax, lowering, and queue checks while preserving the HotShotXL partial-edit failure.

`full` is enough. `thorough` would be excessive: this is not a security boundary, production-data migration, or public API migration. `high` depth is warranted because the planner must reason about contract placement, graph identity, gate propagation, stale-plan behavior, and branch/refactor compatibility.

## 3. Overall Plan Difficulty

Hard architectural implementation sprint, not just feature work.

The difficulty is not raw size. It is residual design risk across contracts, state, executor prompts, done guard, candidate/apply eligibility, artifacts, classifier routing, and tests. The key risk is implementing a plan object that looks authoritative but is not actually evaluable against graph structure.

## 4. Robustness / Depth / Prep Recommendation

Use `--robustness full` and `--depth high`.

Prep is complete enough to start. The source docs already specify the desired stage split, contract shapes, failure mode, gate behavior, artifact needs, and phased rollout. The megaplan planner should still inspect the current code before tasking, but it should not reopen the product decision.

## 5. Sprint Scope

MVP:

- Add first-class typed contracts: `ExecutionPlan`, `PlanStep`, `PlanCondition`, `RoleBinding`, `SocketRef`, `PlanEvaluation`.
- Add `state.execution_plan`, `state.plan_evaluation`, and artifact path fields.
- Build deterministic `ExecutionPlan` for precedent-backed `adapt` routes from selected precedent, current graph facts, schema/provisional schema, and known role bindings.
- Implement evaluator checks for required class presence, required value, direct/reachable edge, terminal consumption, active video output, and 8-frame batch/sequence evidence.
- Add hard `plan_validate_ok` gate.
- Block `done()` and candidate/apply when critical plan conditions fail.
- Persist `execution_plan.json` and `plan_evaluation.json`.
- Feed compact plan status into every execute turn.
- Fix classifier behavior so absent named external technology is preserved and routes to precedent planning.

Stretch only after MVP passes: broader workflow-pattern extraction from `WorkflowSlice`.

## 6. Locked Decisions

- `ExecutionPlan` is new. Do not reuse or rename `PrecedentAdaptationPlan` into authority.
- `PrecedentAdaptationPlan`, `SelectedPrecedent`, `PrecedentPacket`, and `WorkflowSlice` are evidence, not the execution contract.
- First implementation is deterministic. No model-backed planner.
- `plan_validate_ok == false` blocks semantic success for precedent-backed adapt routes.
- Queue blockers remain warnings only after the plan is structurally complete.
- Graph references use stable node/socket refs where available, not class names or REPL variables alone.
- Unknown newer plan/evaluation contract versions fail closed.

## 7. Open Questions for the Planner

- Exact module path: `vibecomfy/comfy_nodes/agent/edit_plan.py` or `vibecomfy/comfy_nodes/agent/agent_edit/plan.py`.
- How to bind roles when multiple samplers, decoders, or terminals exist.
- Minimal accepted 8-frame evidence set: `RepeatLatentBatch.amount`, `EmptyLatentImage.batch_size`, AnimateDiff context length, or equivalent active path.
- Where candidate/apply blocking is cleanest: `edit_entrypoint.py`, `edit_orchestration.py`, or apply eligibility derivation.
- Whether `needs_precedent_plan` becomes a versioned field or a derived helper from `route == "adapt"` plus trigger metadata.

## 8. Constraints and Anti-Scope

Constraints:

- Only precedent-backed `adapt` routes get plan enforcement.
- Small and medium local edits keep existing direct execute flow.
- Use existing serialization style and artifact plumbing.
- Keep integration shims small for compatibility with the god-file-splits branch.

Anti-scope:

- Model-backed planner.
- General custom-node installation/provider search changes.
- Frontend changes.
- Queue-validation policy rewrite.
- Broad live agentic harness expansion beyond one HotShotXL regression path.

## 9. Done Criteria

- HotShotXL sidecar-only edit is rejected: AnimateDiff nodes added but motion model not reaching sampler, no 8-frame active path, no connected `VHS_VideoCombine`.
- Complete HotShotXL edit is accepted: motion model reaches sampler, active path has 8-frame evidence, decoded images reach video terminal.
- `plan_validate_ok` appears in gate updates, turn context/debug surfaces, and task satisfaction.
- Incomplete plan produces no applyable candidate.
- Queue-blocked but structurally complete plan can remain applyable with warning.
- Non-adapt routes are behaviorally unchanged.
- `execution_plan.json` and `plan_evaluation.json` are persisted and exposed in artifacts.
- Existing executor contract/research tests pass, plus new plan evaluator tests.

## 10. Touchpoints

Likely files/modules:

- `vibecomfy/comfy_nodes/agent/edit_plan.py` or `agent_edit/plan.py`
- `vibecomfy/comfy_nodes/agent/edit_state.py`
- `vibecomfy/comfy_nodes/agent/edit_batch_loop_finish.py`
- `vibecomfy/comfy_nodes/agent/edit_batch_loop_intro.py`
- `vibecomfy/comfy_nodes/agent/edit_batch_memory.py`
- `vibecomfy/comfy_nodes/agent/edit_orchestration.py`
- `vibecomfy/executor/contracts.py`
- `vibecomfy/executor/core.py`
- `vibecomfy/executor/research.py`
- `tests/test_executor_contracts.py`
- `tests/test_executor_research.py`
- targeted new tests for plan building/evaluation and HotShotXL partial-edit rejection

## 11. Megaplan Brief Draft

```markdown
# Research Plan Execute Overhaul

Implement a typed, evaluable execution contract for precedent-backed agent-edit adapt routes so the system cannot accept partial graph edits as success. The concrete regression is HotShotXL: research can find an AnimateDiff/HotShotXL video workflow, execution can add relevant nodes, but `done()` can still pass without motion model reaching the sampler, without an 8-frame active path, and without a connected video terminal.

## Outcome

Deliver deterministic `research -> plan -> execute` enforcement for structural precedent-backed edits. Research remains evidence. A new `ExecutionPlan` becomes the authority. `PlanEvaluation` determines whether execution is complete before `done()`, candidate construction, or apply eligibility.

## In Scope

Add typed contracts: `ExecutionPlan`, `PlanStep`, `PlanCondition`, `RoleBinding`, `SocketRef`, and `PlanEvaluation`, with existing-style `to_dict()` serialization and contract versions.

Add state fields for `execution_plan`, `plan_evaluation`, `execution_plan_path`, and `plan_evaluation_path`.

Build deterministic plans for adapt routes using selected precedent evidence, current graph roles, schema/provisional schema, and graph facts. Do not build a model-backed planner.

Evaluate plans with graph-structural checks: required node/class exists, required value set, source reaches target input, motion model reaches sampler, decoded images reach video terminal, active output domain is video, and requested frame/batch count is represented.

Add `plan_validate_ok` as a hard semantic gate. If false for a precedent-backed adapt route, reject `done()` and block candidate/apply. Queue-blocked warnings are allowed only after plan validation passes.

Persist `execution_plan.json` and `plan_evaluation.json` with plan id, source graph hash, candidate graph hash, selected precedent id, schema provenance, step status, failed conditions, and deterministic feedback.

Show compact plan status in every execute turn. Once an execution plan exists, do not keep sending bulky research packets as the main authority.

Fix classifier/routing so named external technology absent from the current graph is preserved for research and routes to precedent planning.

## Out Of Scope

Do not reuse `PrecedentAdaptationPlan` as the authoritative plan. Do not change small/medium local edit routing. Do not implement a model-backed planner. Do not rewrite queue validation, frontend behavior, provider installation search, or general live-agentic infrastructure.

## Required Regression

For a HotShotXL image-to-video request, a candidate that only adds `ADE_AnimateDiffUniformContextOptions` and `ADE_AnimateDiffLoaderWithContext` must be rejected if:
- `motion_model.MODEL` does not reach the sampler model input;
- no active 8-frame latent/image path exists;
- no `VHS_VideoCombine` consumes decoded images.

A complete candidate satisfying those conditions must pass plan validation.

## Implementation Notes

Keep plan logic in a standalone module, not buried in batch-loop code, to ease compatibility with the god-file-splits branch. Use stable graph node/socket references where possible and include confidence for ambiguous role bindings. Unknown newer contract versions fail closed to no-candidate for plan-backed adapt routes.

## Done

The HotShotXL partial-edit regression is blocked with deterministic feedback. Complete HotShotXL video graph edits pass. Non-adapt routes are unchanged. Plan artifacts are persisted. `plan_validate_ok` propagates through gates/debug/task satisfaction. Existing executor tests plus new plan tests pass.
```

## 12. Exact Init Command

```bash
PYENV_VERSION=3.11.11 python -m arnold.pipelines.megaplan init --project-dir /Users/peteromalley/Documents/reigh-workspace/vibecomfy --profile partnered-5 --robustness full --depth high .megaplan/briefs/research-plan-execute-overhaul.md
```
