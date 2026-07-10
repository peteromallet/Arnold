# Codex Critique: Data Contracts

## Summary

The overhaul is directionally right, but the current contracts are not ready for it. The biggest issue is name collision: the code already has `PrecedentAdaptationPlan`, but it is explicitly neutral/contextual and non-authoritative, while the proposal needs an authoritative execution contract. Reusing that concept will preserve the current failure mode.

## Current Data Flow

`ClassifyDecision` currently routes `adapt` as research plus implementation. Research returns `sources`, `precedent_slices`, `precedent_packet`, `selected_precedent`, and `adaptation_plan`.

For `adapt`, `core.py` passes `selected_precedent` inside `execution_protocol_notes` and `precedent_packet` as `research_context_packet`. It does not pass top-level `adaptation_plan` to `handle_agent_edit`. `edit_entrypoint.py` only hydrates `state.executor_adaptation_plan` from top-level `adaptation_plan`, so adapt-route semantic checks often have no plan object to consume.

Execution then returns any changed graph if the route can produce candidates. The done guard rejects no-op/error cases and revise-scoped eligibility failures, but not semantic incompleteness.

## Contract Gaps

There are three competing precedent contracts: `PrecedentAdaptationPlan`, `PrecedentPacket`, and `SelectedPrecedent`. Their semantics conflict: neutral packet, directive selected precedent, and neutral "adaptation plan." Add a new `ExecutionPlan`, not another meaning for `adaptation_plan`.

Research lacks normalized graph-pattern data. `WorkflowSlice` has node ids/types and entry/exit anchors, but not roles, typed edges, input/output sockets, terminal semantics, widget mappings, model filenames, or required vs optional parts. That is insufficient to build deterministic done conditions.

The classifier proposal adds `needs_precedent_plan`, but the current system already has route/task vocabulary. Either derive it from `route == adapt` plus trigger metadata, or version the classifier output. Do not add a parallel boolean without conflict rules.

Missing fields include `contract_version`, `plan_id`, `source_graph_hash`, `research_result_hash`, `selected_precedent_id`, `step_id`, `step_status`, `evidence_refs`, `schema_source`, `runtime_availability`, `criticality`, and `idempotency_key` propagation for generated plans.

## Persistence/Artifacts

Current artifacts persist request, original UI, before/after Python, model request/response, candidate UI, messages, and `revision_evidence.json`. There is no `execution_plan.json` or `plan_evaluation.json`.

`revision_evidence.json` stores topology/readiness/scoped diff, but not precedent obligations. Later accept/reject/audit flows can prove "changed graph" but not "satisfied HotShotXL plan."

Plan persistence should include the original graph hash and candidate graph hash. Otherwise a stale plan could be evaluated against a different graph after rebaseline or idempotent replay.

## Validation Data Needs

Validation needs graph-reachability evidence, not prose. Required checks should be typed: edge reaches, terminal consumes, required class exists, required value set, active path contains batch/frame count, and no required node output remains unconsumed.

Schema validation needs to distinguish installed/runtime schema from workflow-provisional schema. `NodeSchema` already has provenance and `ignored_evidence=("not_installed", "not_runtime_validated")`; plan steps should record which provenance allowed authoring and whether runtime validation may still block queue.

Apply eligibility should consume plan evaluation. Queue-blocked but plan-complete can remain applyable with warnings. Plan-incomplete must be no candidate or non-applyable.

## Recommended Changes

1. Add a separate `ExecutionPlan` contract with `contract_version`, `plan_id`, `required_steps`, `done_conditions`, `blocked_if`, and evidence refs.
2. Rename or de-emphasize current `PrecedentAdaptationPlan`; it is research context, not an execution plan.
3. Normalize research output into roles and edges before planning: role id, class type, node id, input/output socket names, widget/value evidence, terminal role, optionality.
4. Persist `execution_plan.json` and `plan_evaluation.json` alongside `revision_evidence.json`, and expose refs in `artifacts`.
5. Add `state.execution_plan` and `state.plan_evaluation`; do not overload `executor_adaptation_plan`.
6. Run plan evaluation before accepting `done()` and before building applyable candidate payloads.
7. Make idempotency include plan identity: same idempotency key plus same baseline hash should replay the same plan/result, not rebuild against changed research.
8. Add schema version migration rules for classifier/research/plan; unknown newer versions should fail closed to no-candidate, not direct execute.
