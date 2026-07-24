# Megaplan Native Parity Current Codebase Map

## Purpose

This document maps the current codebase surface relevant to Megaplan native
parity. It is the companion to:

- `docs/arnold/megaplan-native-representation-report.md` — the end-state target;
- `docs/arnold/megaplan-native-parity-corrective-plan.md` — the corrective
  plan to reach that target.

Together, those three documents should answer:

1. What should Megaplan look like when native parity is complete?
2. What does the current codebase actually do?
3. What work is required to close the gap without another false pass?

## Executive Summary

The current codebase has real native-workflow machinery, but canonical Megaplan
is still not source-authoritative in the way the end-state report requires.

The important split is:

- Arnold has native ingredients: `.pypeline` parsing, source spans, static
  lowering, policies, native runtime execution, dynamic `parallel_map`, traces,
  resume cursors, and installed-package checks.
- Megaplan still routes much of its product behavior through `components.py`,
  compatibility shells, handler refs, route bindings, manifest backend routing,
  CLI handlers, and handler-local state transitions.

The current `workflow.pypeline` is therefore a readable top-level skeleton, not
the complete semantic owner of the Megaplan product workflow.

## Evidence-backed status update (2026-07-08)

The current generated evidence bundle narrows that earlier diagnosis. The
machine-readable conformance ledger now regenerates from current evidence and
records 31 implemented rows in traceability order. That evidence keeps
`workflow.pypeline` as the canonical authored source, treats `workflow.py` as
compatibility glue only, and quarantines `components.py`, route bindings,
manifest backend routing, CLI dispatch, auto next-step derivation, and
compatibility shells from satisfying row authority.

The same bundle also records the remaining narrowing findings explicitly:
handler-purity audit receipts still capture retained-handler routing/state
mutations, and the compatibility-quarantine and dead-delete mutation records
preserve the known baseline conformance failures as audit evidence rather than
as closure proof. The rest of this map should therefore be read as the
inventory of historical and quarantined semantic carriers that informed the
corrective work.

## Canonical Source Surface

### `arnold_pipelines/megaplan/workflows/workflow.pypeline`

This is the current canonical authored workflow file. It imports:

- `AUTHORING_PREP`
- `AUTHORING_PLAN`
- `AUTHORING_CRITIQUE`
- `AUTHORING_GATE`
- `AUTHORING_REVISE`
- `AUTHORING_FINALIZE`
- `AUTHORING_EXECUTE`
- `AUTHORING_REVIEW`
- `AUTHORING_OVERRIDE`
- `AUTHORING_HALT`
- `CRITIQUE_PANEL_WORKFLOW`
- `TIEBREAKER_WORKFLOW`
- `EXECUTE_BATCH_WORKFLOW`
- `REVIEW_PANEL_WORKFLOW`
- policy constants such as `DEFAULT_POLICY` and `REVISE_LOOP_POLICY`

What it currently owns:

- high-level stage order;
- a visible critique/gate/revise loop shape;
- gate branches such as proceed, iterate, retry, reprompt downgrade,
  tiebreaker, escalate, abort, suspend, blocked preflight, force proceed;
- review branches such as pass, rework, blocked, deferred human;
- override branches such as abort, force proceed, replan;
- visible uses of `parallel_map` for critique, execute, and review;
- a visible call to a tiebreaker workflow.

What it does not fully own:

- prep clarification decision internals;
- plan artifact/version semantics;
- critique evaluator retry and lens selection semantics;
- gate preflight, normalization, reprompt, debt, no-progress cap, and downgrade
  semantics;
- tiebreaker researcher/challenger/decision internals;
- execute dependency scheduling, blocked-task handling, approval gates, and
  partial-resume semantics;
- review mode selection, review fanout/fanin internals, rework cap, force
  proceed, blocked outcomes, and human verification;
- override action dispatch internals;
- model-routing, timeout/deadline, resume, and auto-drive/liveness semantics.

Important current mismatch:

- The `review_route_signal == "rework"` branch calls `AUTHORING_REVISE` and
  returns. The end state needs a visible execute/review/rework cycle.
- The tiebreaker proceed branch executes batches and returns, rather than
  visibly rejoining the normal finalize/execute/review path.

## Component and Metadata Surface

### `arnold_pipelines/megaplan/workflows/components.py`

This is currently the densest semantic carrier.

It defines:

- `StepComponent` objects;
- `ComponentContract` objects;
- `handler_ref` metadata;
- `route_bindings`;
- route vocabularies;
- policy components;
- prompt refs;
- schema refs;
- topology contracts;
- override matrices;
- source and authoring variants of steps/workflows.

Current important objects include:

- public step components such as `PREP`, `PLAN`, `CRITIQUE`, `GATE`, `REVISE`,
  `FINALIZE`, `EXECUTE`, `REVIEW`, `OVERRIDE`;
- source variants such as `SOURCE_*`;
- authoring variants such as `AUTHORING_*`;
- workflow constants such as `CRITIQUE_PANEL_WORKFLOW`,
  `TIEBREAKER_WORKFLOW`, `EXECUTE_BATCH_WORKFLOW`, and
  `REVIEW_PANEL_WORKFLOW`;
- `LEGACY_ALIASES`, including mappings into handler-private override
  functions.

Why this matters:

`components.py` currently makes the `.pypeline` source look more native than it
really is. The source calls clean-looking constants, but those constants point
back to metadata, handler refs, route bindings, and topology contracts.

Final parity requires this file to become one of:

- pure interface/schema/prompt metadata;
- compatibility-only metadata that cannot affect corrected product flow;
- historical/baseline migration evidence.

It must not remain the source of report-owned topology.

## Pipeline Assembly Surface

### `arnold_pipelines/megaplan/workflows/planning.py`

This module builds the current Megaplan pipeline.

Important behavior:

- reads `AUTHORING_SOURCE_PATH = workflow.pypeline`;
- calls `lower_workflow_file(AUTHORING_SOURCE_PATH)`;
- uses the lowered source mostly for identity/version;
- constructs canonical steps from `ALL_STEP_COMPONENTS`;
- constructs routes from component `route_bindings`;
- constructs policy by merging component policy configs;
- produces a DSL-style `Pipeline`.

Risk:

`workflow.pypeline` can improve while `build_pipeline()` still rebuilds the
runtime behavior from `components.py`. That would reproduce the prior false
pass: source looks better, runtime semantics remain component-owned.

Final parity needs one of these outcomes:

- `build_pipeline()` derives canonical behavior from lowered `.pypeline`
  structure;
- a new canonical builder replaces it;
- the old builder is quarantined as legacy compatibility and cannot satisfy
  native-parity evidence.

### `arnold_pipelines/megaplan/workflows/workflow.py`

This is currently compatibility glue around the authored source and builder.

Final parity requirement:

- `workflow.py` must remain non-semantic.
- Removing or changing `workflow.py` must not be able to change product routing,
  loop exits, fanout/fanin, suspension, override dispatch, or review/execute
  decisions.

## Compatibility and Projection Surface

### `arnold_pipelines/megaplan/_compatibility.py`

This module projects graph/DSL Megaplan pipelines into compatibility shells and
native-looking programs.

Risk:

A projected `Pipeline.native_program` can look native while preserving
component/handler ownership underneath. It is useful for migration and runtime
compatibility, but it is not proof of source-level semantic parity.

Final parity requirement:

- compatibility shells may consume canonical source behavior;
- they may not be treated as semantic authority;
- they must be explicitly marked/quarantined if they still run old handlers.

## Runtime Dispatch Surface

### `arnold_pipelines/megaplan/runtime/manifest_backend.py`

This module maps manifest nodes to Megaplan handlers and translates handler
responses into node outcomes.

Important current behavior:

- resolves node IDs to handler functions;
- converts handler responses into branch edge IDs;
- interprets `next_step`, `recommendation`, `decision`, `review_verdict`,
  `override_action`, and `route_signal`;
- contains hardcoded branch mapping behavior in addition to component route
  bindings.

Risk:

Even if `.pypeline` looks fully native, this backend can still own product
routing by interpreting handler-returned strings into workflow edges.

Final parity requirement:

- manifest backend routing must either derive from canonical source or be
  legacy-only;
- handler output may not be the sole carrier of report-owned routes.

### `arnold_pipelines/megaplan/route_dispatch.py`

This is a small route resolver over component `route_bindings`.

Risk:

It is a live path where component metadata can still decide product routing.

Final parity requirement:

- no report-owned semantic can depend on resolving component route bindings at
  runtime.

## Auto and CLI Surface

### `arnold_pipelines/megaplan/auto.py`

Auto-drive currently advances Megaplan using status, next-step state, retries,
escalation, recovery, and compatibility/native phase execution paths.

Risk:

Auto-drive can continue to own liveness and route behavior outside canonical
source. It can also invoke compatibility native phases that call old CLI
handlers.

Final parity requirement:

- auto-drive consumes canonical workflow state/events;
- liveness policy is declared and replayable;
- auto cannot silently run a different semantic path from canonical source.

### CLI dispatch and `COMMAND_HANDLERS`

CLI phase dispatch still routes to old phase handlers.

Risk:

Native-looking execution can re-enter old handler semantics through CLI commands
or compatibility native phases.

Final parity requirement:

- CLI can remain as an operator surface;
- CLI dispatch cannot be final proof of native source semantics;
- any legacy CLI path must be quarantined or proven to delegate to canonical
  native workflow semantics.

## Handler and Orchestration Surface

The current handlers are not all equal. Some are thin wrappers; others contain
large chunks of product policy.

### `handlers/plan.py`

Important current semantics:

- prep clarification detection and state transition;
- plan artifact/version state updates;
- blast-radius/test-surface derivation;
- verifiability flag construction.

Final direction:

- prompt execution and artifact writes may remain;
- clarification gate and artifact contracts must become source/policy visible.

### `handlers/critique.py` and critique runtime modules

The visible handler may delegate, but delegated runtime code still owns
semantics.

Important current semantics:

- critique evaluator behavior;
- retry/recovery;
- revise transitions;
- state updates in orchestration runtime modules.

Final direction:

- critique selection, retry, fanout, merge, and revise loop behavior must be
  native-source visible;
- delegation targets must be scanned, not assumed pure.

### `handlers/gate.py`

This is one of the largest current semantic owners.

Important current semantics:

- gate signal building;
- gate payload normalization and fallback;
- reprompt/downgrade behavior;
- no-progress and cap termination;
- severity-based blocked vs proceed decisions;
- debt recording;
- gate carry artifacts;
- state transitions.

Final direction:

- gate worker/model invocation may remain as a phase body;
- gate decision topology, reprompt, downgrade, debt effect, and loop exit
  semantics must become native-source/policy visible.

### `handlers/_tiebreaker_impl.py` and tiebreaker runtime modules

Current risk:

- tiebreaker internals may be delegated out of the handler file, but still own
  decision routes, state updates, and next-step values.

Final direction:

- tiebreaker must be a real native subworkflow with researcher, challenger,
  synthesis, and decision phases.

### `handlers/finalize.py`

Important current semantics:

- finalize payload validation;
- task and sense-check generation;
- verification-task shaping;
- baseline capture and fallback;
- user-action gate task injection;
- model-output scrubbing.

Final direction:

- artifact writing and validation helpers may remain;
- fallback routes, injected gate semantics, and coverage policy must be source
  or declared policy.

### `handlers/execute.py` and `execute/batch.py`

Important current semantics:

- destructive/user approval gates;
- no-review terminal path;
- blocked-task retry and re-execution;
- task complexity/tier capping;
- batch execution and dependency-aware auto loop.

Final direction:

- low-level command execution may remain;
- dependency batching, approval gates, blocked retry, no-review routing, and
  partial resume must become native-source visible or declared policy.

### `handlers/review.py`

Important current semantics:

- review mode selection;
- review infrastructure retry;
- parallel review behavior;
- review outcome classification;
- rework cap;
- force proceed vs blocked;
- human verification;
- state rollback/transition behavior.

Final direction:

- review worker execution may remain;
- review fanout/fanin, outcome routing, retry caps, and execute/review/rework
  loop must become native-source visible.

### `handlers/override.py`

Important current semantics:

- abort;
- force proceed;
- replan;
- add note;
- recover blocked;
- adopt execution;
- resume clarify;
- set robustness/profile/model/vendor;
- state mutation and action dispatch.

Final direction:

- low-level action effects may remain;
- action routing and terminal/continuation behavior must be visible in native
  source.

## Native Authoring Machinery

### `arnold/workflow/source_compiler.py`

Relevant capabilities:

- parses `.py` and `.pypeline` authoring source;
- preserves source spans;
- handles static imports;
- lowers steps, branches, loops, nested workflows, and `parallel_map`;
- supports policy metadata and diagnostics.

Current risk:

- it accepts component calls as source constructs;
- conformance is syntactic/structural, not row-semantic;
- it is not currently the same thing as proving product semantics live in
  canonical source.

### `arnold/workflow/authoring.py`

Relevant capabilities:

- component contracts;
- workflow/step/policy/schema contract metadata;
- reserved authoring calls and intrinsic names.

Current risk:

- the component-contract model is useful but can preserve graph-era component
  semantics if not constrained.

### `arnold/workflow/diagnostics.py`

Relevant capabilities:

- existing diagnostic registry for unsupported syntax, import issues, invalid
  policies, invalid parallel maps, and component errors.

Final direction:

- reuse diagnostic patterns for native-parity semantic checker failures.

## Native Runtime Machinery

### `arnold/pipeline/native/decorators.py`

Relevant capabilities:

- `@workflow`, `@step`, `@phase`, `@decision`;
- dynamic `parallel_map` declarations;
- metadata on decisions and phases.

Potential value:

- native decisions and typed phase functions may be a better fit for the final
  end-state than component constants.

### `arnold/pipeline/native/compiler.py`

Relevant capabilities:

- compiles generator-style native workflows into `NativeProgram`;
- supports phase, decision, loops, subpipeline, parallel, and `parallel_map`
  instructions.

Open design question:

- should canonical Megaplan execute through this native runtime, through
  `.pypeline` lowering to DSL/manifest, or through a checked equivalence bridge?

### `arnold/pipeline/native/runtime.py`

Relevant capabilities:

- executes `NativeProgram`;
- supports sequential execution;
- supports `parallel_map` with child paths;
- supports suspension/resume cursors;
- supports human-gate-like behavior;
- supports retry attempts and trace hooks.

Limits relevant to parity:

- dependency-aware execute DAG semantics are not the same as generic
  `parallel_map`;
- timeout/deadline/model-route policies need source-visible attachment and
  enforcement;
- runtime must not become the hidden owner of Megaplan product decisions.

### `arnold/pipeline/native/graph_projection.py`

Relevant capabilities:

- projects native programs into graph/topology views.

Risk:

- projection is a view/receipt, not semantic authority.

## Current Test and Conformance Surface

### `scripts/validate_native_representation_conformance.py`

Current behavior:

- validates YAML schema;
- validates row IDs and statuses;
- validates proof category labels;
- validates file existence;
- validates carrier evidence suffix shape.

What it does not prove:

- whether the source actually contains the semantic construct;
- whether proof artifacts contain meaningful tests;
- whether a row is implemented rather than merely present in a file;
- whether runtime behavior follows canonical source;
- whether installed package source matches checked source semantically.

Final direction:

- it should become a final receipt validator that consumes semantic-checker
  evidence, not the primary proof itself.

### Existing workflow/source tests

Useful current tests include:

- `.pypeline` source loading and syntax checks;
- AST checks around visible control flow;
- installed-package smoke checks;
- topology fixture comparisons;
- source-path reconciliation tests.

Risk:

- current anti-wrapper checks ban obvious tokens but can be bypassed by
  aliases, wrappers, re-exports, metadata indirection, or runtime dispatch.

Final direction:

- keep useful tests, but add row-level semantic evidence and negative fixtures.

## Relevant Documentation and State Artifacts

Important docs:

- `docs/arnold/megaplan-native-representation-report.md`;
- `docs/arnold/megaplan-native-representation-alignment-plan.md`;
- `docs/arnold/megaplan-composition-conformance-report.md`;
- `docs/arnold/megaplan-native-representation-conformance-report.md`;
- `docs/arnold/megaplan-native-representation-conformance.yaml`;
- `docs/arnold/megaplan-native-representation-traceability.yaml`;
- `docs/arnold/megaplan-native-parity-corrective-plan.md`.

Important state artifacts:

- `.megaplan/initiatives/native-composition-followup/NORTHSTAR.md`;
- `.megaplan/initiatives/native-platform-followup/NORTHSTAR.md`;
- `.megaplan/initiatives/native-platform-followup/validation-m6-platform-docs-conformance-and-rollout-final_conformance_gate.json`.

Interpretation:

- prior conformance reports are historical receipts and failure evidence;
- they must not be treated as final parity proof after this corrective work.

## Main Ownership Map

| Semantic Area | Current Dominant Owner | Desired Final Owner |
| --- | --- | --- |
| Top-level phase order | `workflow.pypeline` | `workflow.pypeline` |
| Prep clarification | `handlers/plan.py` | Native source gate + suspension policy |
| Plan artifact contract | handler + metadata | Source/policy-declared artifact contract |
| Critique selection/retry | critique runtime + metadata | Native source + retry policy |
| Critique fanout | `.pypeline` shape + component workflow | Native `parallel_map` source/subworkflow |
| Gate decision | `handlers/gate.py` | Native decision/source branches |
| Gate reprompt/downgrade | `handlers/gate.py` + policy metadata | Source-visible retry/repair branch |
| Gate debt | `handlers/gate.py` | Declared edge effect on proceed path |
| Revise loop cap | policy metadata/runtime | Source-visible loop policy + typed outcomes |
| Tiebreaker | component workflow + runtime | Native subworkflow internals |
| Finalize fallback | handler | Native branches/policy |
| Execute DAG | `execute/batch.py` | Native execute subworkflow/batch topology |
| Execute approval | `handlers/execute.py` | Native gate/suspension policy |
| Review fanout/fanin | component workflow + handler | Native `parallel_map` + reducer |
| Review outcome/cap | `handlers/review.py` | Native decision + loop policy |
| Override dispatch | `handlers/override.py` | Native override decision/subworkflow |
| Timeout/deadline | runtime/policy fragments | Declared policy attached to source |
| Model routing | profile/handler fragments | Declared model-route policy |
| Auto-drive liveness | `auto.py` | Declared/replayable event policy |
| Final conformance | YAML validator + reports | Semantic checker + generated ledger |

## Ten Oracle Questions

If we had access to a genius-level oracle, these are the ten questions most
likely to improve the decision quality.

Answers and engineering synthesis live in
`docs/arnold/megaplan-native-oracle-synthesis.md`. This section keeps the
questions as the review checklist; the synthesis document records the current
recommended answers and the risks those answers introduce.

1. What should be the single canonical execution substrate for Megaplan after
   parity: `.pypeline` lowering to DSL/manifest, generator-style native runtime,
   or a checked equivalence bridge? What hidden cost does each option impose?

2. What is the smallest semantic checker that would have rejected the current
   false pass while not turning into an unmaintainable static-analysis project?

3. Which current Megaplan handler semantics are genuinely product topology and
   which are better left as phase-local normalization, validation, or effect
   code?

4. Where is the line between declared policy and hidden routing table? How
   should the checker distinguish a legitimate timeout/model-route/retry policy
   from topology smuggled into metadata?

5. Does the desired end state require true dependency-aware execute DAG support
   in native runtime, or is source-visible deterministic batching plus stable
   child paths enough?

6. What compatibility paths can safely remain forever, and which ones will keep
   reintroducing semantic drift unless deleted?

7. What are the few behavior parity scenarios that dominate risk? If only ten
   scenarios could be required in CI, which ten would expose most hidden
   handler/component ownership?

8. How should typed outcomes be represented so they are strong enough to block
   stringly runtime dispatch but not so heavy that workflow authoring becomes
   painful?

9. What is the right migration order if we want every milestone to leave the
   system shippable and avoid running half-native Megaplan through incompatible
   execution paths?

10. What part of the end-state report is likely over-idealized or not worth the
    engineering cost, and what evidence would justify deliberately narrowing
    the target without repeating the previous false pass?
