# M3b: Generic Decision Routing And Megaplan Literal Removal

## Outcome

Split generic decision/loop routing from Megaplan's four-way gate vocabulary so Arnold routes on plugin-owned decision keys without embedding `proceed`, `iterate`, `tiebreaker`, `escalate`, or Megaplan override policy.

## Scope

In:
- Replace Megaplan-shaped generic gate APIs with a policy-neutral `decision()` or equivalent.
- Move the four-way Megaplan gate helper into the Megaplan plugin.
- Move `PipelineBuilder.tiebreaker()` into the Megaplan plugin or remove it from generic Arnold. Do not keep a Megaplan-shaped generic tiebreaker helper.
- Split `critique_revise_gate_loop()` into a generic loop helper parameterized by decisions/overrides/fallback edges/caps plus a Megaplan wrapper.
- Classify `phase_zero_gate`, `alternating_turns`, and conditional escape-edge patterns as generic only when they are policy-free.
- Remove `GateRecommendation` and `OverrideAction` from generic runtime.
- Make override-edge dispatch behavior explicit and tested.
- Preserve halt dispatch via `result.next == "halt"` and edge target `"halt"`.

Out:
- Do not move stages/prompts/state/control.
- Do not build the authoring API; this is runtime routing, not M8.

## Locked Decisions

- Megaplan owns its decision labels and override action meanings.
- Generic edge dispatch validates plugin-owned routing strings against each decision stage's declared vocabulary.
- Generic `decision()` supports override/fallback edges parameterized by plugin-owned override action strings, separate from model-decision routing.
- Control flow and dataflow remain distinct.

## Required Outputs

- The generic override-dispatch contract, made explicit and covered by tests. Either the executor dispatches `kind="override"` edges or the generic contract documents and preserves label-based `override <action>` routing.
- Which topology helpers have non-Megaplan users.

## Constraints

- Preserve planning graph parity, tiebreaker path behavior, override/fallback edges, and settled-decision behavior.
- Do not hide Megaplan literals in renamed generic helpers.

## Done Criteria

- Generic runtime has no `GateRecommendation`, `OverrideAction`, or Megaplan gate labels as typed policy.
- Megaplan plugin provides its own gate/tiebreaker helper or wrapper.
- Override dispatch contract is explicit and covered by tests.
- Halt dispatch via `result.next == "halt"` and edge target `"halt"` is preserved.
- Planning parity tests still pass.

## Touchpoints

- `megaplan/_pipeline/types.py`
- `megaplan/_pipeline/builder.py`
- `megaplan/_pipeline/pattern_topology.py`
- `megaplan/pipelines/planning/`
- planning parity tests

## Anti-Scope

- Do not generalize robustness/depth/prep semantics.
- Do not flatten Megaplan topology into Arnold defaults.
