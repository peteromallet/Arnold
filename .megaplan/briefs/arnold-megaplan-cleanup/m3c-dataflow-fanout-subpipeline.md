# M3c: Dataflow, Dynamic Fanout, And Subpipeline Promotion

## Outcome

Land the composability contracts that let Arnold pipelines prove data availability, run dynamic fanout, and compose subpipelines without importing Megaplan policy.

## Scope

In:
- Add or complete unified control-flow and dataflow validation: `validate_control_flow()` plus `validate_dataflow_paths()`.
- Ensure required reads/ports are satisfiable on every incoming path unless marked optional, external, or late-bound.
- Specify dynamic fanout generated spec schema, specialization, concurrency mode, governor limits, typed output port, and join contract.
- Specify first-class subpipeline execution with explicit input/output maps, artifact scope, and `promote(child_result, parent_ctx) -> StateDelta`.
- Add a research-fanout or toy plugin fixture that proves fanout, reducer synthesis, and non-Megaplan composition.

Out:
- Do not split batch runtime or recovery classifier here; that is M3d.
- Do not build remote subpipeline execution.
- Do not require independent child resume unless M-1 selected a current workflow that depends on it.

## Locked Decisions

- `reads=[...]` and `writes=[...]` are Level-1 sugar over artifact/port binding.
- Simple strings use wildcard content type until a plugin opts into typed ports.
- Prompt resolution is bundle/resource scoped, not global mutable registry for new code.
- Child run envelopes, nested profile mapping, parent/child observability linkage, and independent child resume are target capabilities unless required by parity.

## Boundary

Dataflow validation, dynamic fanout, and subpipeline promotion are Arnold runtime mechanics. They must not import Megaplan policy, contain Megaplan phase/state/decision literals, or silently default to Megaplan schema assumptions.

## Runtime Settings For Subpipelines

Child subpipelines inherit parent run settings by default, then apply child pipeline defaults, child profile/settings, child stage overrides, and explicit invocation overrides. Arnold owns carrier mechanics, precedence, validation, and dry-run source reporting; plugins own defaults and meanings attached to their stages.

## Required Outputs

- Exact public syntax for dynamic fanout in tests versus M8 docs.
- `PipelineRef` is a target capability. Inline `Pipeline` objects are sufficient for this milestone unless a real discoverable-child-pipeline parity case requires registry references now.

## Constraints

- Preserve `doc` dynamic fanout and terminal halt behavior.
- Preserve `creative` dataflow parity.
- Preserve `select-tournament` typed-port binding and reducer outputs.
- Preserve `writing-panel-strict` human pause/resume loop behavior.
- Validators preserve both `result.next == "halt"` short-circuit and edge-target `HALT`/`"halt"` dispatch.
- Do not expose advanced contracts in the first 10-minute authoring guide.

## Done Criteria

- Validators catch route bypasses, missing prompt/resource dependencies, unknown routes, and unguarded cycles.
- Dynamic fanout has a stable internal contract and parity tests.
- Subpipeline promotion and artifact isolation have parity tests.
- `creative` dataflow parity still passes.
- Research-fanout/toy fixture runs without importing Megaplan policy.

## Touchpoints

- `arnold/pipeline/`
- `megaplan/_pipeline/subloop.py`
- `megaplan/_pipeline/executor.py`
- `megaplan/_pipeline/steps/`
- non-Megaplan pipeline tests

## Anti-Scope

- Do not move Megaplan stages/prompts/state.
- Do not build batch/recovery seams here.
