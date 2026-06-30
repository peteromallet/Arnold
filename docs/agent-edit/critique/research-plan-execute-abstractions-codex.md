# Codex Critique: Technical Abstractions

## Summary

The overhaul is directionally right: the failure mode is not bad research, it is missing authority between evidence and edits. But the proposal still treats "plan" too much like a JSON prompt blob. The core abstraction should be a typed, evaluable execution contract with graph-role bindings and deterministic satisfaction checks. Without that, this becomes another larger prompt injection layer around the batch REPL.

## Strong Ideas

Separating `research -> plan -> execute` is the right boundary for precedent-backed edits. Current `adapt` already carries `ResearchResult`, `SelectedPrecedent`, `PrecedentPacket`, and `PrecedentAdaptationPlan`, but execution still receives mostly contextual evidence.

The proposed `done_conditions` are the most important part. Current done rejection catches no-op, failed edits, and some revise-candidate issues, but not semantic incompleteness such as "motion model sidecar exists but does not reach sampler."

The apply-eligibility distinction is also right: queue blockers should remain warnings only when the graph is structurally complete. Semantic plan failures should block candidate/apply before queue policy matters.

## Missing Abstractions

`ExecutionPlan` must be a first-class dataclass, not a dict. It should live beside existing executor contracts or agent contracts and serialize through the same `to_dict()` pattern. Otherwise validation, artifacts, and response debug data will drift.

The proposal lacks a `PlanEvaluation` abstraction. This should report per-step status, failed conditions, blocking severity, and deterministic feedback text. It should be usable in three places: prompt status, `done()` guard, and final response/task satisfaction.

Graph roles need their own model. `current_graph_roles: {"sampler": "ksampler"}` is too vague because class type is not identity. Use stable node refs plus role names, socket refs, and confidence. Multiple samplers/decoders/output nodes are common.

Pattern edges need path semantics. "source reaches target" is different from "direct wire equals target input." The validator needs `direct_edge`, `reachable_path`, `terminal_consumes`, and `active_output_path` checks.

Batch/frame cardinality is underspecified. `ensure_batch_or_sequence` needs a validator that can recognize known batch mechanisms, widget fields, and active latent/image paths.

There is no explicit schema capability abstraction. The implementation should separate `planned_class_known_from_installed_schema`, `planned_class_known_from_workflow_provisional_schema`, `missing_schema_but_research_supported`, and `runtime_queue_blocker`.

## Simplifications

Do not start with a model-backed planner. Build the first planner deterministically from existing `SelectedPrecedent.minimal_spine`, `terminal_output_path`, `promotion_gates`, workflow schema, current graph facts, and graph inspection.

Do not reuse `PrecedentAdaptationPlan` as the authoritative plan. Its current contract is explicitly neutral/presentation-oriented, can leave validation `not_evaluated`, and often has empty `required_new_nodes`, `required_rewires`, and `edit_ops`. Keep it as research evidence.

Do not repeat full research every batch turn. Send compact plan status regenerated from the candidate graph.

Add one gate rather than many ad hoc branches: `plan_validate_ok`. It can feed `StageResult.gate_updates`, `TurnContext`, `ApplyEligibility`, and response debug snapshots like existing validation gates.

## Risks

The plan can become over-authoritative and block valid alternative implementations. Mitigate this by allowing explicit equivalent mechanisms, but require the evaluator to name the evidence.

Research may select the wrong precedent. A plan validator cannot fix bad precedent selection; it will only enforce the wrong shape more reliably. Keep selection confidence and mismatch warnings visible.

Graph-role binding is the hard part. If binding uses class type only, multi-branch workflows will be misplanned. If binding requires perfect certainty, adapt will clarify too often.

## Recommended Changes

1. Add typed `ExecutionPlan`, `PlanStep`, `PlanCondition`, `RoleBinding`, and `PlanEvaluation` contracts.
2. Treat `SelectedPrecedent` and `PrecedentPacket` as research inputs; produce a separate authoritative execution plan.
3. Implement deterministic plan evaluation before accepting `done()` and before building an applyable candidate.
4. Represent graph references as stable node/socket refs, not class names or REPL variable names.
5. Add reusable validators for `edge_reaches`, `terminal_consumes`, `active_domain_output`, and `batch_or_sequence_count`.
6. Reuse existing schema hydration and provisional schema providers instead of inventing a new class lookup path.
7. Integrate plan results into existing `StageResult`, `TurnContext`, `ApplyEligibility`, and `task_satisfaction` surfaces.
8. Keep small and medium edit routing on existing `revise`/local schema paths; reserve this machinery for `adapt` precedent workflows.
