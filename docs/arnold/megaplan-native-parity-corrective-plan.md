# Megaplan Native Parity Corrective Plan

## Purpose

This document defines the corrective work required to bring canonical Megaplan
to parity with the end state described in
`docs/arnold/megaplan-native-representation-report.md`.

The prior native-composition and native-platform epics delivered useful
substrate: `.pypeline` loading, compositional authoring primitives, static
topology, trace/checkpoint structure, installed-package reconciliation, and a
platform conformance ledger. They did not finish the core product migration
that the North Stars required: the whole Megaplan workflow, including its
decision topology, loops, fanout/fanin, human gates, override behavior, and
execute/review cycles, must be visible in canonical native source.

The corrective goal is semantic parity, not another representational pass.

This plan supersedes the closeout status claims in
`docs/arnold/megaplan-composition-conformance-report.md` and
`docs/arnold/megaplan-native-representation-conformance-report.md`. Those
reports remain useful historical receipts for substrate work and for diagnosing
the false pass. They are not final parity evidence. After this corrective work,
row status authority must come from machine-checked semantic evidence generated
from the canonical source and supporting artifacts, not from manually asserted
tables.

## Status after final conformance rollout (2026-07-08)

The corrective work described here is now closed by the generated evidence
bundle in `docs/arnold/megaplan-native-representation-evidence.yaml`, the
regenerated ledger in
`docs/arnold/megaplan-native-representation-conformance.yaml`, and the
generated closeout report in
`docs/arnold/megaplan-native-representation-conformance-report.md`. Those
artifacts keep current implemented-row authority in `workflow.pypeline`, named
native support carriers, boundary receipts, scenario hashes, installed-package
fingerprints, and explicit quarantine/audit records rather than in prior report
prose.

The rollout evidence also preserves explicit narrowing records instead of
erasing them: retained-handler purity findings, compatibility-quarantine
findings, and dead-delete mutation findings remain in the bundle as audit
surfaces. The rest of this document remains the rationale and execution plan
for the corrective work, while the generated evidence artifacts are the current
closure proof.

## End State

The canonical source is:

`arnold_pipelines/megaplan/workflows/workflow.pypeline`

It should read as the authoritative Megaplan product workflow. A reviewer
should be able to understand the whole pipeline by reading that file and its
named native subworkflows, without consulting component tables, handler refs,
route bindings, prompt metadata, manifest builders, or handler-local
`current_state` / `next_step` mutation.

The final workflow should make these units explicit:

- prep and prep clarification gate;
- plan artifact creation and version metadata;
- critique selection, critique fanout, critique merge, and critique skip policy;
- gate preflight normalization, gate decision, reprompt/downgrade behavior, and
  debt/fallback handling;
- bounded critique/gate/revise loop;
- tiebreaker researcher/challenger/decision subworkflow;
- finalize and fallback routing;
- execute dependency batching and dynamic batch scheduling;
- execute approval/no-review/deferred-human gates;
- review parallel fanout/fanin;
- review retry caps, blocked outcomes, force-proceed, and human verification;
- explicit execute/review/rework cycle;
- full override action surface: abort, force-proceed, replan, resume, recover,
  profile/model changes, and terminal halt behavior;
- timeout, retry, deadline, model-routing, suspension, resume, and
  path-addressed checkpoint policy as declared workflow policy, not hidden
  handler control flow.

Handlers may remain only as pure phase bodies or narrowly scoped side-effect
adapters. A retained handler may do phase-local work such as prompt execution,
artifact writing, model invocation, command execution, or low-level side
effects. It may not own product routing, loop exits, retry decisions,
fanout/fanin topology, override dispatch, suspension semantics, model-routing
policy, timeout/deadline policy, or implicit workflow state transitions.

A retained handler is not pure if it assigns or derives `current_state`,
`next_step`, route labels, branch targets, retry/cap outcomes, override
actions, or resume cursors for report-owned semantics. Thin delegation is also
not purity: if `handle_review()` delegates to a runtime module that owns review
routing, the runtime module is the semantic owner and must be extracted or
audited under the same rule.

## Historical pre-closeout state

The current `workflow.pypeline` is native-shaped but not semantically complete.
It imports and calls component constants such as:

- `AUTHORING_PREP`
- `AUTHORING_PLAN`
- `AUTHORING_GATE`
- `AUTHORING_EXECUTE`
- `AUTHORING_REVIEW`
- `AUTHORING_REVISE`
- `AUTHORING_OVERRIDE`
- `TIEBREAKER_WORKFLOW`
- `CRITIQUE_PANEL_WORKFLOW`
- `EXECUTE_BATCH_WORKFLOW`
- `REVIEW_PANEL_WORKFLOW`

The file exposes a high-level route through Megaplan, but many semantics remain
behind `arnold_pipelines/megaplan/workflows/components.py` and the handler
modules. That indirection is precisely what the North Stars said must not count
as final conformance.

The delivered source answers:

> What high-level stage happens next?

The target source must answer:

> What is the whole Megaplan pipeline, including decisions, loops, retries,
> fanout/fanin, suspension, override, execute/review behavior, and model
> routing?

## What Specifically Went Wrong

### 1. The closeout accepted the wrong bar

The North Star required semantic parity with the end-state report. The final
closeout accepted representational parity: a canonical `.pypeline` existed, the
file had visible branches and loops, the YAML ledger listed every row as
implemented, and installed-package smoke checks passed.

Those checks proved that a native representation existed. They did not prove
that Megaplan's product semantics had been lifted into native source.

### 2. The wrapper was made indirect

The tests rejected obvious wrapper tokens in `workflow.pypeline`, such as
`SOURCE_`, `handler_ref`, and `route_bindings`. But the source still calls
imported component constants whose backing metadata and handlers own important
semantics.

The banned concepts moved out of the visible file rather than being eliminated
as semantic carriers.

### 3. Handler-owned gaps were treated as progress

The composition conformance report identified a handler-purity inventory with
nine report-semantic owners and two pure phase bodies. It also documented
expected failures that would turn green as handlers were progressively
extracted.

That was useful as an intermediate status. It was not a valid final state. The
platform closeout later converted that weaker status into final `implemented`
closure.

### 4. The final validator checked the ledger, not the source semantics

The final Platform M6 gate ran:

`scripts/validate_native_representation_conformance.py --conformance docs/arnold/megaplan-native-representation-conformance.yaml --traceability docs/arnold/megaplan-native-representation-traceability.yaml`

The receipt is:

`.megaplan/initiatives/native-platform-followup/validation-m6-platform-docs-conformance-and-rollout-final_conformance_gate.json`

That validator checks schema, row IDs, statuses, proof categories, path
existence, and carrier-evidence suffix shape. For `canonical_source`, it checks
that evidence points at `.pypeline` files. It does not AST-inspect whether the
canonical source actually carries the required semantics.

### 5. The final report overclaimed

`docs/arnold/megaplan-native-representation-conformance-report.md` states that
all 31 rows are implemented and that no Megaplan semantic is deferred into
handlers, route labels, manifests, native traces, or runtime side effects.

That claim does not match the actual source shape. The current implementation
still requires `components.py` and handlers to explain major behavior.

## Corrective Principles

1. Canonical native source is the semantic authority.
2. `components.py` may describe invocable interfaces, but it may not be the
   product workflow skeleton.
3. Handlers may implement phase bodies, not orchestration.
4. Declared policy is valid only when it is inspectable and attached to named
   native workflow constructs.
5. A conformance ledger is a receipt, not the proof.
6. Every traceability row must have source-level evidence, policy-level
   evidence, or audited pure-body evidence that is stronger than path existence.
7. The current component-call pattern must become a failing fixture.
8. The burden of proof is on the closer. A row without structured checker
   evidence is `unproven`, regardless of ledger status or prior report prose.
9. Compatibility projections, `Pipeline.native_program` shells, `workflow.py`
   shims, compiled manifests, rendered topology, and native traces are
   consumers or receipts. They are not semantic authority unless they are
   proven to derive from canonical `.pypeline` source.

## Machinery Readiness

The underlying Arnold machinery is good enough to start the corrective epic,
but not good enough to assume the end state is already expressible and verified
without additional hardening.

Ready now:

- `.pypeline` parsing, source spans, static lowering, route/topology fixtures,
  native traces, installed-package reconciliation, and behavior goldens exist.
- Native runtime support exists for sequential execution, path-style traces,
  suspension/resume cursors, human-gate-like pauses, retry hooks, effect
  idempotency, and graph projection.
- Megaplan already has stable interface metadata that can help name phases and
  payload boundaries.

Not ready enough:

- The current source/conformance stack accepts component-call skeletons as
  canonical source. That is the exact false pass.
- Some target constructs need first-class authoring or checker treatment before
  they can be trusted: inline suspension/halt/transition, typed decisions,
  timeout/deadline policy, model-routing policy, explicit review/rework loops,
  and execute DAG/batch semantics.
- Native runtime parallelism and DAG execution are not the same thing as
  source-visible execute dependency semantics. If true concurrent execution is
  out of scope, the final source must still expose dependency batching and
  deterministic child paths rather than hiding scheduling in handlers.
- Compatibility shells and projected native programs are especially dangerous:
  they can look native while preserving graph/component ownership underneath.

Therefore the first corrective milestone must harden semantic checking and
baseline failure before any large workflow rewrite.

## Machinery Boundary

The corrected system must name exactly which layer owns semantics and which
layers consume them.

Semantic authority:

- `workflow.pypeline`;
- named native subworkflows imported by `workflow.pypeline`;
- declared policy objects attached to those source constructs;
- audited pure phase bodies behind typed native interfaces.

Compatibility and execution consumers:

- `arnold_pipelines/megaplan/workflows/planning.py::build_pipeline()`;
- projected `Pipeline.native_program` compatibility shells;
- compiled manifests and rendered topology;
- `arnold_pipelines/megaplan/runtime/manifest_backend.py`;
- `arnold_pipelines/megaplan/route_dispatch.py`;
- `arnold_pipelines/megaplan/auto.py`;
- CLI phase dispatch and `COMMAND_HANDLERS`.

Those consumer paths may continue to exist during migration, but they must not
be the proof source for report-owned semantics. Before closure, each consumer
path must either be proven to derive behavior from canonical source or be
quarantined as a legacy path that cannot satisfy traceability rows.

One decision is required before extraction work can close: whether canonical
Megaplan executes through `.pypeline` lowering into the existing DSL/manifest
runtime, through the generator-style native runtime, or through a checked
equivalence projection between the two. The plan may support a bridge period,
but it may not leave two independent "native" truths.

Decision: canonical Megaplan should execute through `.pypeline` lowering into
the existing DSL/manifest runtime for this corrective epic. The generator-style
native runtime remains useful for patterns, tests, and possible future runtime
migration, but it is not the canonical Megaplan runtime target here.

This makes `build_pipeline()` the immediate load-bearing seam. It must stop
discarding lowered `.pypeline` topology for canonical Megaplan, or it must be
replaced/quarantined before extraction milestones can close.

Compatibility bridges are temporary. If a bridge remains during migration, it
needs an explicit expiry milestone and cannot satisfy semantic evidence rows.

## Work Plan

### Phase 0: Freeze, Baseline, and Semantic Checker

Goal: preserve the current state as a known non-parity baseline and build the
checker that prevents another false pass before extraction begins.

Tasks:

- Add a failing characterization fixture that represents the current pattern:
  a `.pypeline` importing `AUTHORING_*` component constants whose semantics are
  backed by `components.py` metadata and handlers.
- Add the same fixture in installed-package mode, so a wheel containing that
  source fails outside the checkout too.
- Mark that fixture as invalid for final native parity.
- Snapshot the current `workflow.pypeline`, `components.py` semantic carriers,
  handler purity inventory, conformance YAML, and final M6 receipt.
- Write a short baseline report listing every row where current evidence is
  only component-backed, handler-backed, or policy-backed without source-level
  semantic structure.
- Record every compatibility path that can still execute old semantics:
  `workflow.py`, `build_pipeline()`, compatibility shells, route dispatch,
  manifest backend handler resolution, CLI phase dispatch, and direct handler
  calls.
- Add the first production semantic checker for canonical `.pypeline` files.
  It does not need every final row rule yet, but it must already reject the
  current component-call skeleton, handler refs, route tables, projected-native
  proof, and path-only ledger evidence.
- Implement the minimum checker rules:
  - callee provenance for report-owned source calls;
  - row-anchor shape matching for branches, loops, maps, gates, subworkflows,
    and policies;
  - dead-delete mutation checks for legacy carriers such as `route_bindings`,
    `_branch_edge_id`, and `route_dispatch`.
- Add a row-evidence schema before any row can be reclassified as
  `implemented`.
- Add a machinery-boundary decision record covering `.pypeline` lowering,
  generator-style native runtime, compatibility native programs, and the
  required equivalence/quarantine gates.
- Prove `build_pipeline()` either consumes lowered `.pypeline` topology for a
  real vertical slice or is quarantined behind a new canonical builder.

Exit gate:

- The current implementation can be loaded for backward compatibility, but it
  must fail the new semantic parity checker.
- The baseline report distinguishes three categories for every row:
  source-owned, policy-owned, and still owned by components/handlers/runtime.
- No extraction milestone may close until the checker and row-evidence schema
  exist and are running against both checkout source and installed-package
  source.
- A compatibility bridge, if present, has an expiry milestone and is forbidden
  as row evidence.

### Phase 1: Define the Native Megaplan Domain Model

Goal: replace stringly route signals and component placeholders with typed
domain outcomes and define the allowed retained-handler boundary.

Tasks:

- Define typed results for prep, plan, critique, gate, tiebreaker, finalize,
  execute, review, revise, override, suspension, and halt.
- Define closed route/result objects or enums for:
  - gate: proceed, iterate, retry_gate, reprompt_downgrade, tiebreaker,
    escalate, abort, suspend, blocked_preflight, force_proceed;
  - tiebreaker: proceed, iterate, escalate, abort, suspend;
  - review: pass, rework, blocked, deferred_human, retry_review,
    force_proceed;
  - override: abort, force_proceed, replan, resume, recover, halt,
    profile_change, model_change.
- Keep raw string labels only inside compatibility adapters and serialization
  boundaries. They may not be the primary workflow control-flow contract.
- Define explicit payload types for fanout/fanin and checkpoint paths.
- Define native interface/protocol boundaries for retained phase bodies so a
  handler can be called without carrying routing metadata with it.
- Add type-level tests proving unsupported route values fail authoring or
  validation.
- Add a source-authoring decision on any missing primitives needed before the
  rewrite: suspension/halt/transition syntax, timeout/deadline attachment,
  model-route attachment, and explicit retry/cap policy.
- Add a transitive handler-purity contract: every retained handler declares its
  allowed side effects, and the checker scans the retained body plus Megaplan
  callees for report-level routing, caps, fanout/fanin, resume, state
  transition, and override dispatch.

Exit gate:

- `workflow.pypeline` and native subworkflows can use typed outcomes instead of
  opaque component route strings as the primary control-flow contract.
- Any required authoring/compiler primitive that does not exist yet has either
  landed with tests or is called out as a blocking gap. It is not papered over
  with handler metadata.
- Typed outcome objects are enforced at workflow boundaries; raw string
  dispatch is confined to compatibility adapters.

### Phase 2: Extract Prep, Plan, Critique, Gate, and Revise

Goal: make the front half of Megaplan inspectable as native workflow structure.

Tasks:

- Replace `AUTHORING_PREP` and `AUTHORING_PLAN` as skeleton calls with named
  native phases.
- Add an explicit prep clarification gate with suspension/resume semantics.
- Replace `CRITIQUE_PANEL_WORKFLOW` and `AUTHORING_CRITIQUE` as opaque fanout
  carriers with:
  - critique evaluator phase;
  - active lens selection;
  - native dynamic parallel map over critique lenses;
  - native reducer/merge phase;
  - bare-robustness skip branch.
- Replace `AUTHORING_GATE` with a native gate decision phase and explicit
  branches for proceed, iterate, retry, reprompt downgrade, tiebreaker,
  escalate, abort, suspend, blocked preflight, and force proceed.
- Replace `AUTHORING_REVISE` as the visible loop carrier with an explicit
  bounded revise loop and loop outcome policy.

Exit gate:

- A reviewer can follow prep clarification, critique fanout, gate, and revise
  behavior through native branches, loops, typed results, and named phase calls.
- `components.py` no longer owns front-half routing semantics.
- The phase-local behavior scenarios for these rows pass before the phase can
  close; they are not deferred to final rollout.

### Phase 3: Extract Tiebreaker as a Real Subworkflow

Goal: make tiebreaker internals visible instead of treating it as one imported
component.

Tasks:

- Define `tiebreaker_workflow` as a native subworkflow.
- Expose researcher, challenger, synthesis, and decision phases.
- Make proceed/iterate/escalate/abort/suspend outcomes typed and branch-visible.
- Preserve path-addressed checkpoint and resume points for each tiebreaker
  child phase.
- Audit `_tiebreaker_impl.py` so retained functions are pure phase bodies, not
  route owners.

Exit gate:

- The traceability row `tiebreaker-subworkflow` is proven by inspecting native
  subworkflow structure, not by seeing a `TIEBREAKER_WORKFLOW(...)` call.
- Tiebreaker proceed/iterate/escalate behavior parity scenarios pass before
  this phase closes.

### Phase 4: Extract Execute DAG and Approval Gates

Goal: make execution topology explicit and dependency-aware in native source.

Tasks:

- Replace `EXECUTE_BATCH_WORKFLOW` and `AUTHORING_EXECUTE` as the visible
  execute skeleton with native batching constructs.
- Represent task dependency scheduling as a native DAG/batch iteration
  subworkflow.
- Expose batch execution, blocked-task handling, partial failure, retry, and
  resume behavior.
- Expose destructive/user approval gates, no-review terminal routing, and
  deferred-human routing as declared workflow policy attached to native source.
- Keep low-level command execution and artifact writes in handlers only when
  those handlers satisfy the retained-handler purity rule from the End State.
  A handler may execute a batch; it may not decide which batch topology exists,
  when dependency iteration stops, which approval route is taken, or where the
  workflow routes after execution.

Exit gate:

- `execute-dependency-batches`, `execute-approval-gates`,
  `runtime-list-iteration`, and `dynamic-parallel-map` are proven by native
  source and static topology, not by component metadata.
- Execute DAG, approval/no-review/deferred-human, blocked-task, and partial
  resume scenarios pass before this phase closes.

### Phase 5: Extract Review, Rework, and Review Caps

Goal: make the execute/review/rework cycle explicit.

Tasks:

- Replace `REVIEW_PANEL_WORKFLOW` and `AUTHORING_REVIEW` as opaque fanin
  carriers with native review fanout/fanin.
- Expose review mode selection, parallel review checks, merge/reducer behavior,
  retry caps, blocked outcomes, force-proceed behavior, and human verification.
- Replace the current `review_route_signal == "rework"` branch that calls
  revise and returns with an explicit cycle back into execute/review as required
  by policy.
- Add cap tests for repeated rework, infrastructure retry exhaustion, blocked
  review, force-proceed, and human verification.

Exit gate:

- `execute-review-rework-loop`, `review-parallel-fanin`, and
  `review-retry-cap-outcomes` are inspectable in native source and tested with
  deterministic scenarios.
- Review rework visibly cycles back through execute/review. A revise-and-return
  path does not satisfy this gate.

### Phase 6: Extract Override and Human Control Surface

Goal: make override behavior source-visible rather than metadata/handler-owned.

Tasks:

- Replace `AUTHORING_OVERRIDE` as the visible override skeleton with a native
  override subworkflow or decision function.
- Expose action dispatch for abort, force-proceed, replan, resume, recover,
  profile/model changes, halt, and unknown action fallback.
- Attach human suspension/resume/deny/cancel policy to explicit native gates.
- Ensure platform machinery consumes these decisions without owning them.

Exit gate:

- Override behavior is understandable from source branches and typed outcomes.
- Handler retained code is pure effect/application logic, not product
  orchestration.
- Override abort, force-proceed, replan, resume, recover, profile/model change,
  and halt scenarios pass before this phase closes.

### Phase 7: Collapse Component Constants to Interfaces or Remove Them

Goal: prevent the old graph-era component model from remaining the semantic
carrier.

Tasks:

- Inventory every `AUTHORING_*`, `*_WORKFLOW`, `handler_ref`,
  `route_bindings`, topology contract, and prompt ref in
  `workflows/components.py`.
- For each item, choose one fate:
  - remove because native source now owns the semantics;
  - convert to a typed invocable interface with no routing semantics, no
    handler-ref dispatch, no route table, and no topology metadata;
  - keep as compatibility metadata only, with tests proving it cannot influence
    product control flow.
- Delete or quarantine obsolete route tables and handler refs.
- Update compatibility shims so old imports continue only where required, but
  cannot be used as final conformance evidence.
- Make compatibility use explicit and fenced. A compatibility path must be
  named, tested, and forbidden as evidence for any report-owned semantic.
- Add a no-new-component-semantic-dependency gate before this phase starts:
  extraction phases may not introduce new report-owned semantics into
  `components.py`, route dispatch, manifest backend routing, auto, or CLI
  command handlers.

Exit gate:

- `workflow.pypeline` no longer uses component constants as its control-flow
  skeleton.
- `components.py` is no longer needed to understand Megaplan's product
  topology.
- Deleting or quarantining semantic metadata from `components.py` does not
  change deterministic product-routing traces for the corrected workflow.

### Phase 8: Finalize Semantic Proof and Conformance

Goal: complete the semantic checker, bind it to the ledger/report generator,
and make the old false pass impossible at final closeout.

Tasks:

- Extend the Phase 0 semantic checker into the full final checker for
  canonical `.pypeline` files and imported native subworkflows.
- Reject source that uses component constants, handler refs, route tables,
  manifest builders, generic stage dispatch, or imported component calls as the
  primary skeleton for report-owned semantics.
- Resolve imports transitively. The checker must not be a string scan. It must
  follow aliases, re-exports, decorators, helper wrappers, dynamic module
  access where statically detectable, and imported native subworkflows far
  enough to decide whether a report-owned semantic ultimately lands in
  `components.py`, a handler ref, a route table, a manifest builder, or runtime
  dispatch.
- Treat policy as inspectable structure, not a dumping ground. A declared
  policy can satisfy a row only when it is attached to a named source construct
  and its content is specific to that row. A policy object that contains route
  tables, target refs, fanout contracts, hidden topology, or override dispatch
  is not a substitute for source-visible semantics.
- Require each traceability row to map to one of:
  - source construct: branch, loop, typed call, subworkflow, dynamic map,
    human gate, retry, timeout, model route;
  - declared policy attached to a named source construct;
  - audited pure phase body with no route ownership.
- Add negative fixtures:
  - current `AUTHORING_*` component-call skeleton;
  - aliased or re-exported component constants;
  - wrapper functions/classes/decorators that return component carriers;
  - hidden `handler_ref` route carrier;
  - route table disguised as declared policy;
  - topology or fanout contracts hidden in metadata;
  - manifest-builder source that bypasses native Python control flow;
  - handler-local or transitive `current_state` / `next_step` mutation;
  - handler return-value routing through `route_signal`;
  - runtime route dispatch from `components.py` bindings;
  - manifest backend `_branch_edge_id` or equivalent handler-output routing;
  - auto/CLI execution through `__megaplan_auto_phase__` or `COMMAND_HANDLERS`
    as proof of native semantics;
  - compatibility shell or projected-native evidence used as semantic proof;
  - installed-package divergence from the checked canonical source.
- Update the YAML validator so it can only pass after the semantic checker
  produces row-level evidence.
- Add content/provenance checks so a row cannot pass because a file exists with
  the right suffix. Implemented rows need source-locatable checker evidence and
  evidence hashes tied to the checked commit or installed artifact.
- Make the final conformance report generated from checked evidence, not
  manually asserted status.

Exit gate:

- The current implementation and all Phase 0 false-pass fixtures still fail the
  final checker.
- The corrected implementation passes by source-level evidence.
- Every `implemented` row has a machine-readable evidence record containing the
  row id, carrier type, source file, source span or policy object, proof test,
  and content hash.
- The validator rejects an otherwise well-formed ledger if the semantic checker
  evidence is absent, stale, hand-authored, or points only at path existence.

### Phase 9: Behavior Parity and Rollout

Goal: preserve existing Megaplan behavior while changing the semantic carrier.

Tasks:

- Run existing golden scenarios and installed-package checks.
- Add fixed deterministic scenarios for:
  - prep clarification suspend/resume;
  - critique/gate/revise loop and cap;
  - tiebreaker proceed/iterate/escalate;
  - execute DAG partial failure and resume;
  - approval/no-review/deferred-human gates;
  - review pass/rework/blocked/force-proceed;
  - override abort/force-proceed/replan/resume/recover;
  - timeout/retry/model-routing policy.
- Ensure the scenario set proves split outcomes, not only happy paths:
  - critical vs cosmetic cap exhaustion;
  - destructive execution denied vs approved;
  - blocking review cap vs advisory-only force proceed;
  - recover-blocked resume with stable batch paths;
  - bare/light robustness critique skip and no-review terminal routing.
- Compare old and new behavior where old behavior is intended to remain.
- Explicitly document intentional behavior changes.
- Update final docs only after semantic and behavior gates pass.

Exit gate:

- Canonical source parity, behavior parity, installed-package parity, and final
  documentation all agree.
- The suite includes enough split-outcome scenarios to prove routing semantics,
  not only artifact production.

## Row Evidence Contract

Every traceability row must be checked against a concrete evidence contract.
The contract lives in machine-readable form next to the traceability ledger and
is summarized in the final report. At minimum, every row defines:

- required carrier: canonical source, declared policy, audited pure phase body,
  or explicit deferral;
- required source shape: branch, loop, typed outcome, subworkflow, dynamic map,
  suspension gate, retry policy, timeout policy, model route, or pure phase
  call;
- unacceptable evidence: component constant, handler ref, route binding,
  topology metadata, manifest projection, trace-only proof, or prose-only
  claim;
- positive test proving the final source shape;
- negative fixture proving the old false pass fails;
- behavior scenario proving the row still behaves correctly.
- runtime path checked or compatibility path quarantined, so installed-package,
  auto-drive, manifest backend, route dispatch, and CLI paths cannot silently
  execute old semantics while source conformance passes.

The front-half rows require explicit source evidence for prep clarification,
plan artifact boundaries, critique skip/retry/fanout, gate preflight/reprompt,
gate debt/fallback, and the bounded critique/gate/revise loop. The tiebreaker
row requires source-visible researcher, challenger, synthesis, and decision
phases. Execute and review rows require source-visible batching, approval,
review fanout/fanin, retry caps, and the execute/review/rework cycle. Policy
rows such as timeout, model routing, autodrive liveness, golden regeneration,
and source-path reconciliation require declared, generated, or replayable
evidence rather than handler or report prose.

No row inherits its previous `enabled` or `implemented` status. Every row is
re-proved under this contract.

## Required Final Gates

The corrective epic is not done until all gates pass:

1. `workflow.pypeline` has no component constants as product-control skeleton.
2. No report-owned semantic is solely carriered by `components.py`.
3. No report-owned semantic is solely carriered by handler refs, route labels,
   manifests, native traces, or runtime side effects.
4. Every traceability row has machine-checked source/policy/pure-body evidence.
5. The current pre-correction implementation fails as a negative fixture.
6. The generated conformance report cannot claim `implemented` for a row unless
   the semantic checker emitted proof for that row.
7. Installed-package source-path reconciliation proves the shipped artifact uses
   the same canonical `.pypeline`.
8. Behavior parity tests pass or intentional differences are named with the old
   behavior, new behavior, reason, affected scenarios, and reviewer signoff.
9. Human-readable topology/rendered views derive from canonical source.
10. A reviewer can inspect canonical source and understand the complete
    Megaplan product flow without reading handler-local state transitions.
11. `workflow.py`, compatibility shells, `Pipeline.native_program` projections,
    manifest backends, route dispatch, and CLI phase dispatch are either
    proven non-semantic for the corrected workflow or explicitly quarantined
    as legacy execution paths.
12. Prior conformance reports cannot be used as proof artifacts except as
    historical baseline/failure evidence.
13. `build_pipeline()` no longer discards the lowered `.pypeline` topology for
    canonical Megaplan, or it is quarantined as a legacy builder with a new
    canonical builder in place.
14. Any deliberate narrowing of the end-state target includes both a checker
    rule that still blocks the original false-pass pattern and a behavior
    scenario proving the narrowed carrier cannot smuggle routing.

## Suggested Epic Breakdown

The active cloud initiative compresses the work into seven busy two-week
sprints. This is a schedule compression, not a scope reduction: the original
phase plan above remains authoritative for detailed content, and the active
briefs under
`.megaplan/initiatives/megaplan-native-parity-corrective/briefs/s*.md` name
which earlier milestone scope they absorb.

### Sprint 1: Checker, Outcomes, Builder Slice

Build the checker, negative fixtures, typed outcome/interface boundary, and one
runtime-load-bearing `.pypeline` vertical slice. This combines the old semantic
checker, typed domain model, and canonical builder slice work because the
checker cannot be trusted until it proves a real source-derived runtime edge.

Deliverables:

- semantic checker skeleton and current-pattern negative fixture;
- row-to-evidence schema and baseline gap report;
- typed outcomes and retained-handler interfaces;
- `build_pipeline()` or replacement builder consuming lowered `.pypeline`
  topology for at least one real edge;
- dead-delete mutation and installed-package proof for that edge.

### Sprint 2: Front-Half Native Loop

Extract prep, plan, critique, gate, revise, and the coupled front-half loop.

Deliverables:

- native front-half source;
- prep clarify, gate downgrade, cap exhaustion, and force-proceed scenarios;
- component/handler carrier deletion or quarantine for implemented front-half
  rows;
- row-level checker evidence for the front half.

### Sprint 3: Tiebreaker And Replan Native Flow

Extract tiebreaker into a real native subworkflow and make replan rejoin normal
planning/finalize behavior.

Deliverables:

- researcher/challenger/synthesis/decision source structure;
- tiebreaker proceed/iterate/escalate/replan scenarios;
- path checkpoint tests;
- dead-delete proof for old tiebreaker carriers.

### Sprint 4: Execute DAG, Approval, Resume

Extract dependency-aware execution, deterministic batching, approval gates,
blocked recovery, no-review terminal routing, and partial resume.

Deliverables:

- execute native subworkflow or visible source/policy batching;
- DAG/batch fixtures and stable checkpoint tests;
- destructive approval and recover-blocked scenarios;
- source-visible blocked/partial-failure/resume branches.

### Sprint 5: Review, Rework, Finalize

Extract review fanout/fanin, retry caps, blocked/force-proceed outcomes, human
verification, explicit execute/review/rework loop, and finalize fallback
routing.

Deliverables:

- review native subworkflow and explicit rework cycle;
- blocking vs advisory cap scenarios;
- human verification and finalize fallback scenarios;
- review/finalize component carrier quarantine or deletion.

### Sprint 6: Override, Auto, Compatibility Collapse

Extract routing overrides, remove auto-drive as a second route brain, and
collapse or fence remaining semantic compatibility paths.

Deliverables:

- override native decision/subworkflow for abort, force-proceed, replan,
  resume, recover, and halt;
- authority-declared human/control gates;
- `components.py`, route dispatch, manifest backend, auto, CLI, and projection
  quarantine/deletion proofs;
- handler purity tests with no report-semantic owners.

### Sprint 7: Final Conformance Rollout

Generate final reports from checked evidence and rerun full behavior,
installed-package, compatibility, mutation, resume, and rollout validation.

Deliverables:

- generated conformance YAML/report from checker evidence;
- proof map and final source topology snapshot;
- full split-outcome behavior scenario suite;
- installed-package verification;
- updated docs and explicit narrowing records where applicable.

## Closure Anti-Patterns

The corrective epic must reject these patterns even when tests, imports, or
reports look green:

1. **Indirect component wrapper:** canonical source imports a benignly named
   callable that resolves to `AUTHORING_*`, `SOURCE_*`, `*_WORKFLOW`, or any
   other component carrier.
2. **Handler return-value routing:** a handler returns `route_signal`,
   `next_step`, `current_state`, or equivalent data that the runtime turns into
   a product route.
3. **Policy as route table:** declared policy contains target refs, route
   groups, decision routes, fanout contracts, reducer routes, or override
   dispatch that should be visible workflow structure.
4. **Metadata topology:** `components.py` or another metadata module contains
   the tiebreaker split, execute batching, review fanin, retry/cap behavior, or
   override matrix while canonical source shows only one call.
5. **Projected-native proof:** a graph/component pipeline is projected into a
   native program and then treated as native source authority.
6. **Receipt substitution:** a validator receipt, topology snapshot, or final
   report is used instead of rerunning source-level semantic checks at the
   final commit.
7. **Installed artifact drift:** checkout source passes, but the installed
   package ships stale or generated source with different semantics.
8. **Handler reclassification:** a handler is renamed or moved from
   `handlers/` to `orchestration/` and then treated as pure without scanning
   the transitive implementation.
9. **Happy-path parity:** behavior parity proves only the default path while
   uncommon routes such as reprompt downgrade, blocked preflight, force
   proceed, review cap, partial execute resume, and override actions remain
   untested.

## Non-Goals

This corrective plan does not require finishing unrelated platform items:

- graph visualization UI;
- hot migration of already-running workflows across incompatible versions;
- automatic shared-pack upgrade propagation;
- multi-region execution;
- broader worker-fleet expansion beyond the existing platform guarantees.
- deleting every handler or string constant in the Megaplan package;
- implementing true concurrent execution if deterministic dependency batching
  and path-stable fanout/fanin can be represented and tested;
- parsing arbitrary Python in the semantic checker. The checker may reject
  source outside the Arnold workflow authoring subset.

Those can remain platform follow-ups. They must not be used to defer Megaplan's
native semantic parity.

## Definition of Done

The corrective work is complete when the end-state report, canonical source,
traceability ledger, generated conformance report, tests, and installed package
independently prove the same fact:

Megaplan's canonical `.pypeline` source is the readable, native, inspectable
owner of the whole product workflow. Components, handlers, manifests, traces,
and runtime policies support that source; they do not replace it.

If any artifact says a row is implemented while the checker has no source,
policy, or pure-body evidence for that row, the row is not implemented.
