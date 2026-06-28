# Python-Shaped To Native Gap Roadmap

This document compares the expected repository state after the
`python-shaped-workflow-authoring` epic completes with the fuller native
Megaplan target in `docs/arnold/megaplan-native-representation-report.md`.

The short version: M1-M8 deliver an import-first, statically compiled,
manifest-first Python authoring surface. That is a large step toward readable
Megaplan workflows, but it is not the full native-program model from the report.
The remaining work is mostly dynamic topology, richer loop outcomes, event and
human control-plane modeling, call-site policies, and extraction of hidden
handler orchestration.

## 1. Summary Of What The Python-Shaped Epic Delivers

M1, `m1-component-contract-grammar`, freezes the V1 authoring contract. It
makes workflow `.py` imports the user-facing source of truth, defines typed
component exports for steps, prompts, policies, schemas, and subflows, and
settles import validation, source provenance, diagnostics, grammar versioning,
and package layout expectations. Its most important limit is explicit: this is
a frontend over `arnold.workflow.dsl.Pipeline` and `WorkflowManifest`, not a new
runtime, and it must not depend on `arnold.pipeline.native`, `_pipeline`,
`stages`, native projection, or compatibility shims.

M2, `m2-compiler-core-linear-lowering`, implements the first production
compiler slice. It parses restricted Python-shaped source without executing the
workflow, validates component imports, lowers assignment and tuple-assignment
component calls, supports the useful linear subset, carries source spans into
DSL/manifest output, and proves deterministic compiles through golden fixtures.
It delivers linear workflow authoring, not general Python control flow.

M3, `m3-control-flow-policy-lowering`, adds the bounded control-flow forms
needed for the current Megaplan planning topology. It covers `if` / `elif` /
`else` over declared decision outputs, route labels, stable condition refs,
`while True` backedges for critique/revise and review/rework loops, bounded
loop policy, policy references for existing manifest concepts, suspension,
halt, and manifest-lowerable subworkflow references. It still rejects general
Python control flow, unsupported mutation, ambiguous loops, and non-literal
routing decisions.

M4, `m4-megaplan-component-migration`, makes
`arnold_pipelines.megaplan.workflows.planning.py` the canonical product-facing
Megaplan workflow. It exports Megaplan steps, prompts, policies, schemas, and
subflows as typed components, moves `build_pipeline()` behind a loader/compiler
facade, and uses golden tests to preserve previous explicit-DSL manifest
identity and behavior. This is the milestone where the real Megaplan workflow
becomes readable as source, but the runtime is still the manifest runtime.

M5, `m5-validator-cli-ux`, ships the authoring surface as an operator and agent
interface. It adds `arnold workflow check`, `compile`, `inspect`, and `explain`
flows for source files, machine-readable diagnostics, human-readable diagnostics
with source locations and fix guidance, and CLI coverage for source checkouts
and installed packages. It makes the source usable and hard to misuse, but does
not broaden runtime semantics.

M6, `m6-explain-render-shipped-pipelines`, makes topology visible. It adds
source-first explanation, graph/render views derived from authored source and
lowered DSL, docs that lead with workflow `.py` files, and migrations or
scaffolds for shipped/example pipelines where the V1 grammar is sufficient. It
does not expand the grammar just to migrate examples.

M7, `m7-runtime-conformance-installed-artifacts`, proves behavioral equivalence
from authored source through DSL, manifest, runtime execution, event journals,
artifact refs, resume cursors, suspension, loop/retry behavior, review/rework
semantics, wheel/sdist installs, and negative import gates. This is the proof
that Python-shaped authoring did not break the current runtime path.

M8, `m8-generated-assets-merge-result-conformance`, regenerates and verifies
docs, examples, generated skills/assets, registries/catalogs, CLI snapshots,
package ledgers, manifest identity ledgers, source/wheel/sdist gates, dynamic
import tracing, deleted-prefix audits, and source authoring smoke tests. It
certifies the integrated Python-shaped merge result, not the full native target
from `docs/arnold/megaplan-native-representation-report.md`.

## 2. Capability-By-Capability Gap Analysis

### Status Key

- **Delivered**: M1-M8 should provide this in the Python-shaped authoring line.
- **Partial**: M1-M8 provide a compatible piece, but not the native report's
  full capability.
- **Not delivered**: needs a follow-up milestone or epic.
- **Exists elsewhere**: current code has ingredients outside the Python-shaped
  source line, usually under `arnold.pipeline.native`, `arnold.patterns`, or
  `arnold.manifest`.

### Native Product Semantics In Python Control Flow

**Native requirement:** product semantics should be visible in Python control
flow: loops as loops, gates as branches, tiebreakers as subworkflows,
review/rework as explicit cycles, human intervention as suspension points, and
task fanout not hidden behind an opaque handler.

**After M1-M8:** partial.

M3 and M4 should make the current Megaplan graph readable and source-authored.
The gap is that the V1 contract in
`docs/arnold/python-shaped-authoring-contract.md` remains a static frontend over
`arnold.workflow.dsl.Pipeline` and `WorkflowManifest`. It is not the "normal
Python program with durable phase calls" shown in the native report.

**Missing:** arbitrary-looking but durable source-level `await phase(...)`,
runtime-list fanout, typed loop exits, call-site policies, source-visible
effects, and event transitions.

**Follow-up:** a native authoring architecture milestone deciding whether the
next line is `arnold.workflow.authoring.v2`, convergence with
`arnold.pipeline.native`, or a bridge/projection model.

### Import-First Component Contract

**Native requirement:** stable references for phases, prompts, policies,
schemas, and subflows.

**After M1-M8:** delivered for V1 components.

`arnold/workflow/authoring.py` defines `ComponentKind`, `ComponentContract`,
`StepComponent`, `PromptComponent`, `PolicyComponent`, `SchemaComponent`, and
`SubflowComponent`. M1 freezes the contract and M4 migrates Megaplan components.

**Missing:** first-class component forms for dynamic fanout, foreach, model
routing, human gates, edge effects, and typed outcomes.

**Follow-up:** extend component/policy schemas once the runtime supports those
constructs.

### Sequential Durable Phases

**Native requirement:** durable phase calls for prep, plan, critique, gate,
revise, tiebreaker, finalize, execute, review, override, and halt.

**After M1-M8:** delivered for coarse phases.

M2 lowers component calls to DSL steps. M4 exports Megaplan step components and
makes the authored workflow canonical.

**Missing:** phase bodies may still hide orchestration. The native report wants
critique fanout, gate reprompt, execute batches, and review checks lifted into
topology.

**Follow-up:** split handlers into pure phase bodies plus explicit subworkflow
topology, starting with gate and review.

### Top-Level Workflow Function

**Native requirement:** a native source file that reads like a Python program,
for example `planning_native(ctx)`.

**After M1-M8:** partial.

M3 allows restricted function-shaped control flow; M4 makes a workflow source
file canonical. However, the V1 line is still statically parsed and lowered to
the explicit DSL. Existing `arnold/pipeline/native/decorators.py` has
`@pipeline` and `@phase`, and `arnold/pipeline/native/compiler.py` compiles a
separate `yield <phase>` milestone grammar, but M1 explicitly excludes that
surface as an authoring dependency.

**Missing:** one unified source story for future native authoring.

**Follow-up:** architecture decision before adding syntax.

### Branches And Decision Variables

**Native requirement:** explicit prep, gate, tiebreaker, review, override, and
finalize fallback branches.

**After M1-M8:** delivered for manifest-lowerable branches; partial for event
and control-plane branches.

M3 covers decision branches, route labels, and condition refs. M4 requires
tiebreaker, override, review/rework, and loop paths to be represented when they
affect topology.

**Missing:** external override/resume/cancel/recover events, runtime-payload
branching, and named control actions such as `force-proceed`, `replan`, and
`recover-blocked`.

**Follow-up:** human/control-plane topology milestone.

### Prep Clarification Gate

**Native requirement:** prep can suspend for blocking open questions and resume
after human clarification.

**After M1-M8:** mostly delivered.

M3 includes suspension and halt; M4 includes Megaplan suspension behavior; M7
proves event journals, resume cursors, and suspension.

**Missing:** the report's ordinary-source shape, such as
`if prep_payload.has_blocking_questions: human_gate(...)`, will probably be
represented by declared decision outputs and `suspend(...)` rather than direct
payload property checks.

**Follow-up:** typed decision-output ergonomics if M4's source reads too
indirectly.

### Adaptive Critique Evaluator And Retry

**Native requirement:** critique skips on bare robustness, runs an adaptive
evaluator, retries evaluator once, selects active lenses, and merges findings.

**After M1-M8:** partial.

M3 includes retry policy references where existing manifest concepts support
them. M4 should expose critique as a Megaplan step or subflow.

**Missing:** runtime-selected critique lenses, dynamic fanout, per-lens
artifacts, sequential fallback after parallel failure, and source-visible
evaluator retry semantics.

**Follow-up:** dynamic critique subworkflow milestone after dynamic fanout.

### Parallel Critique Lenses With Fan-In

**Native requirement:** selected critique checks run concurrently and merge.

**After M1-M8:** partial.

`FanoutPolicy(mode="static")` and `ReducerRef` exist in
`arnold/manifest/manifests.py`; `arnold/patterns/control.py` has `fanout` and
`panel`; `arnold/pipeline/native/decorators.py` has fixed `parallel(...)`.

**Missing:** dynamic `parallel_map(selection.active_checks, ...)`; item
schemas; deterministic runtime item IDs; per-item retry/timeout/fallback; and
dynamic reducer semantics.

**Follow-up:** dynamic fanout/foreach epic.

### Gate Worker, Reprompt, Downgrade, And Debt

**Native requirement:** gate builds signals, invokes the worker, normalizes
output, validates unresolved flags, reprompts once, downgrades invalid proceed
decisions, records debt, and routes to proceed, iterate, tiebreaker, blocked,
abort, or override.

**After M1-M8:** partial.

M3 and M4 should expose the coarse gate decision and loop topology.

**Missing:** source-visible reprompt/repair edge, high-complexity downgrade,
debt recording as an idempotent effect, no-progress termination, and
severity-aware exhausted behavior.

**Follow-up:** gate-native extraction milestone.

### Critique/Gate/Revise Loop

**Native requirement:** bounded loop with severity-aware termination,
tiebreaker branch, retry, no-progress logic, and explicit exits.

**After M1-M8:** delivered for coarse loop topology; partial for semantic exits.

M3 includes bounded `while True` backedges. The current source compiler rejects
unsupported loop controls, and `arnold/pipeline/native/compiler.py` also rejects
`break` and `continue`.

**Missing:** typed outcomes such as proceed, iterate, blocked, force-proceed,
tiebreaker, replan, and await-human.

**Follow-up:** typed loop outcome milestone.

### Tiebreaker Subworkflow

**Native requirement:** researcher/challenger branches, then a human/system
decision choosing pick, escalate, or replan.

**After M1-M8:** partial.

M3 supports typed subworkflow references where manifest-lowerable. M4 includes
tiebreaker components. `SubpipelineRef` and `SubflowComponent` already exist.

**Missing:** explicit researcher/challenger fanout, human decision payload
schema, pick/replan/escalate typed outcomes, and re-entry into revise/critique
or planning restart.

**Follow-up:** tiebreaker-native subworkflow milestone.

### Finalize Fallback Routes

**Native requirement:** finalize baseline/test-selection failures can route
back to revise and retry finalize.

**After M1-M8:** partial.

M3 supports branches and policy references; M4 exposes finalize as source; M7
proves current runtime behavior.

**Missing:** exception/failure edges, typed failure classes, and structured
payload from finalize failure back into revise.

**Follow-up:** failure-edge milestone, or include in gate-native extraction if
small.

### Dependency-Aware Execute Over Runtime Task Batches

**Native requirement:** execute iterates over finalized task batches, respects
dependencies, dispatches by complexity/model route, handles blocked tasks, and
merges results.

**After M1-M8:** not delivered as native topology.

M4 can expose `execute` as a step and M7 can prove behavior, but the actual
batch loop remains hidden in execution runtime/handlers. V1 has no
`foreach.dag_batches(...)` or dynamic DAG scheduler construct.

**Missing:** runtime task graph schema, dependency-aware batch formation,
dynamic per-task/per-batch execution, blocked/retry/recover transitions,
model routing by task complexity, and resume from mid-execution.

**Follow-up:** execution DAG native runtime epic.

### Execute Approval And Destructive Gates

**Native requirement:** execute can suspend for user/destructive approval.

**After M1-M8:** partial.

M3 includes suspension and approval policy references; M4 includes approval
boundaries as policy/schema components; M7 verifies suspension/resume.

**Missing:** source-visible approval branches, destructive classification
outside handlers, and composition with dynamic execution batches.

**Follow-up:** include in execution DAG or human-control-plane epic.

### Review Worker, Parallel Review, And Rework

**Native requirement:** review approves, requests rework, blocks, routes to
human verification, retries infrastructure failure, runs parallel checks for
extreme robustness, caps rework, and decides blocked versus force-proceed.

**After M1-M8:** partial.

M3 includes review/rework backedges and policy lowering. M4 exposes review
paths. M7 proves current review/rework runtime behavior.

**Missing:** dynamic review-check fanout, typed infrastructure retry, explicit
review outcome decision, structured rework scope, and cap outcome visibility.

**Follow-up:** review-native extraction milestone, likely paired with critique
native extraction.

### Human Suspension Points

**Native requirement:** prep clarification, tiebreaker decide, review human
verification, execute approval, blocked recovery, and override are first-class
suspension/control points.

**After M1-M8:** delivered for basic suspension; partial for full control-plane
semantics.

`SuspensionRoute` exists in `arnold/manifest/manifests.py`; M3 includes
suspension; M7 proves current resume behavior.

**Missing:** route-specific choice schemas, authority/evidence contracts,
override action topology, pause/cancel/recover events, and first-class source
human-gate syntax.

**Follow-up:** human-control-plane epic.

### Override And Force-Proceed Routes

**Native requirement:** override and force-proceed are explicit control-flow
edges, not opaque action strings.

**After M1-M8:** partial.

M3 can represent control flow and policies; M4 includes override components.

**Missing:** named transitions for abort, force-proceed, replan,
resume-clarify, recover-blocked, set-robustness, set-profile, set-model, and
set-vendor; evidence and waiver/debt recording for force-proceed; recovery
re-entry through typed outcomes.

**Follow-up:** override topology milestone inside human-control-plane work.

### Retry, Timeout, And Escalation Policies

**Native requirement:** critique evaluator retry, gate reprompt, review retry,
timeouts, stale/dead worker handling, escalation, and fallback should be
source-visible.

**After M1-M8:** partial.

`RetryPolicy`, `TimingPolicy`, and `EscalationPolicy` exist in
`arnold/manifest/manifests.py`; `PolicyComponent` can carry metadata; M3 lowers
policy references where already representable.

**Missing:** ergonomic call-site syntax, typed retry conditions, exhausted
outcomes, per-item policies for dynamic fanout, and explicit stale/dead-worker
event transitions.

**Follow-up:** policy-callsite milestone.

### Model Routing

**Native requirement:** route models by phase, task complexity, robustness,
profile, vendor override, and fallback.

**After M1-M8:** partial as policy metadata, not full native routing.

M3 names model routing among policy references, and M4 exports Megaplan policy
components. But `WorkflowPolicy` has no explicit `model_route` field today.

**Missing:** manifest/source representation for model routing, task-level
routing, vendor/profile override state, fallback policy, and explain output.

**Follow-up:** model-routing policy/schema milestone, likely grouped with
policy-callsite.

### Dynamic Parallel Map And Foreach

**Native requirement:** `parallel_map` or `foreach` over runtime lists for
critique checks, review checks, tiebreaker roles, and execution batches.

**After M1-M8:** not delivered.

Static fanout exists, but V1 does not support runtime-cardinality topology.
`arnold/pipeline/native/decorators.py` requires literal branch callables for
`parallel(...)`, and M1 excludes that surface anyway.

**Missing:** collection refs, item schemas, deterministic runtime item IDs,
mapper/reducer policy, max workers, per-item retry/timeout/fallback, partial
completion, cancellation, and resume.

**Follow-up:** dynamic fanout/foreach epic.

### Dynamic DAG Scheduling

**Native requirement:** execution schedules runtime tasks by dependency graph.

**After M1-M8:** not delivered.

The Python-shaped epic can preserve existing execute behavior, but no source or
manifest construct represents dependency-aware runtime task batches.

**Missing:** task graph schema, ready/blocked/done states, batch formation
policy, task frontier resume, and review rework scoping back into the task
graph.

**Follow-up:** execution DAG milestone.

### Fan-In And Reducers

**Native requirement:** critique, tiebreaker, review, and execution results
merge through explicit reducers.

**After M1-M8:** partial.

`FanoutPolicy.reducer_ref` and `ReducerRef` exist. Static fanout/panel patterns
can attach reducer refs.

**Missing:** dynamic reducer input/output schemas, deterministic ordering,
reducer retry/failure behavior, and reducer artifact refs.

**Follow-up:** include reducer semantics in the dynamic fanout epic.

### Subworkflow Invocation

**Native requirement:** critique, gate, tiebreaker, execute, and review can be
nested workflows with typed outcomes.

**After M1-M8:** partial.

`SubflowComponent` and `SubpipelineRef` support manifest-level nested workflow
references where lowerable.

**Missing:** subworkflow-local dynamic topology, parent/child journal
composition, typed subworkflow returns, and source-visible nested outcomes.

**Follow-up:** subworkflow outcome milestone after loop outcomes and dynamic
fanout.

### Edge Effects And Compensation

**Native requirement:** gate debt recording, checkpoints, failure events, state
recovery, and side effects are explicit and replay-safe.

**After M1-M8:** partial.

`EffectRef`, `IdempotencyPolicy`, `CompensationPolicy`, and
`CompensationTarget` exist in `arnold/manifest/manifests.py`.

**Missing:** source-visible effect statements or edge annotations, runtime
idempotency enforcement, compensation for partial dynamic work, and explain
output for effects.

**Follow-up:** effect/compensation milestone after policy-callsite.

### Event-Driven Transitions And Auto-Drive

**Native requirement:** override, resume, cancel, pause, recovery, timeout,
stale worker, and auto-drive liveness transitions are top-level control data.

**After M1-M8:** partial.

`ControlTransitionSlot` and `TopologyOverlaySlot` exist. M3 can lower policy
references. M7 proves current journals/resume behavior.

**Missing:** source-level event transition syntax, event vocabulary, ownership
boundary between workflow topology and operator loop policy, and render/explain
views for events.

**Follow-up:** auto-drive control topology milestone.

### Resume Cursors And Replay

**Native requirement:** human gates and long loops resume durably.

**After M1-M8:** delivered for current behavior; partial for future native
dynamic topology.

M7 covers event journals, artifact refs, resume cursors, suspension, and
loop/retry behavior.

**Missing:** resume through dynamic fanout, dynamic DAG execution, nested
subworkflows, partial reducers, and control-plane overrides that change
profile/model/vendor.

**Follow-up:** every dynamic topology epic must extend resume conformance.

### Explain, Render, And Installed Artifact Conformance

**Native requirement:** native topology is visible in source, explain output,
rendered graph, package artifacts, and generated docs/skills/examples.

**After M1-M8:** delivered for V1 source; partial for future native constructs.

M5/M6 deliver source-first inspect/explain/render; M7/M8 deliver package and
merge-result conformance.

**Missing:** dynamic fanout visualization, typed loop outcome visualization,
event/control-plane visualization, model route visualization, and conformance
for later native manifest/schema changes.

**Follow-up:** each native construct must include inspect/explain/render and
M7/M8-style conformance acceptance criteria.

## 3. Proposed Follow-Up Epics And Milestones

### Epic A: Native Authoring Architecture Decision

Sprint estimate: 1 sprint.

Scope:

- Decide between `arnold.workflow.authoring.v2`, convergence with
  `arnold.pipeline.native`, or a bridge/projection model.
- Inventory overlap between `arnold/workflow/source_compiler.py` and
  `arnold/pipeline/native/compiler.py`.
- Define whether future source stays import-first/static or moves toward
  decorator/native function syntax.
- Define manifest schema/hash compatibility.

Acceptance criteria:

- Checked-in architecture decision under `docs/arnold/`.
- One chosen future source-of-truth story.
- Explicit containment or deprecation plan for the unchosen surface.
- Target Megaplan source sketch showing loops, gates, dynamic fanout, human
  gates, policies, and override transitions.
- Manifest identity and packaging risks documented.

### Epic B: Dynamic Fanout And Foreach

Sprint estimate: 3 sprints.

Scope:

- Add runtime collection refs, item schemas, deterministic item IDs,
  mapper/reducer refs, max workers, per-item retry/timeout/fallback, and resume
  semantics.
- Extend manifest/source/compiler/runtime as needed.
- Add explain/render support.

Acceptance criteria:

- Selected critique checks compile into dynamic fanout.
- Selected review checks compile into dynamic fanout.
- Reducer ordering is deterministic.
- Event journals can resume partial fanout completion.
- Installed package tests pass.

### Epic C: Typed Loop Outcomes

Sprint estimate: 2 sprints.

Scope:

- Add explicit product loop outcomes such as proceed, iterate, tiebreaker,
  replan, blocked, force-proceed, approved, needs-rework, human-verify, and
  abort.
- Lower outcomes to manifest edges and loop policies.

Acceptance criteria:

- Critique/gate/revise exits are source-visible.
- Review/rework exits are source-visible.
- Loop counters and no-progress state are journaled.
- Explain output separates product iteration from transient retry.

### Epic D: Policy Call-Site And Model Routing

Sprint estimate: 2 sprints.

Scope:

- Make retry, timeout, escalation, authority, and model routing source-visible
  on steps, subflows, and fanout items.
- Add or formalize model-route manifest representation.

Acceptance criteria:

- Critique evaluator retry, gate reprompt, and review retry are declared as
  policies.
- Execute task dispatch can route by complexity.
- Profile/model/vendor override state is journaled.
- Explain output shows routing and retry policy.

### Epic E: Human Control Plane And Override Topology

Sprint estimate: 2 sprints.

Scope:

- Replace opaque override action dispatch with named routing/effect actions.
- Model abort, force-proceed, replan, resume-clarify, recover-blocked,
  set-robustness, set-profile, set-model, and set-vendor.
- Add authority/evidence schemas.

Acceptance criteria:

- Explain output shows override routes and re-entry points.
- Force-proceed records authority and waiver/debt evidence.
- Recover-blocked re-enters execute/review through typed outcomes.
- Existing operator commands remain compatible.

### Epic F: Gate-Native Extraction

Sprint estimate: 2 sprints.

Scope:

- Lift gate signal build, worker call, normalization, unresolved-flag
  validation, reprompt, high-complexity downgrade, debt recording, and route
  decision into topology.

Acceptance criteria:

- `arnold workflow explain` shows gate worker, validation, reprompt, downgrade,
  debt effect, and route outcomes.
- Gate cap/no-progress behavior uses typed loop outcomes.
- Golden tests cover proceed, iterate, tiebreaker, blocked, force-proceed, and
  downgrade paths.
- Debt effect is idempotent under replay.

### Epic G: Critique And Review Native Extraction

Sprint estimate: 2 sprints.

Scope:

- Lift adaptive critique evaluator, selected-lens fanout, merge, retry, and
  fallback into topology.
- Lift review selection, parallel review, retry, merge, outcome decision, human
  verification, and rework scoping into topology.

Acceptance criteria:

- Bare robustness critique skip is explicit.
- Critique/review checks are dynamic fanout items.
- Sequential fallback is represented and tested.
- Review/rework cap behavior is source-visible.
- Existing artifacts remain compatible.

### Epic H: Tiebreaker Native Subworkflow

Sprint estimate: 2 sprints.

Scope:

- Represent researcher/challenger branches and pick/escalate/replan decision
  routing as an explicit subworkflow.

Acceptance criteria:

- Explain output shows researcher and challenger branches.
- Pick re-enters revise/critique.
- Replan restarts planning with durable state.
- Escalate suspends with a typed resume schema.

### Epic I: Execution DAG Native Runtime

Sprint estimate: 3 sprints.

Scope:

- Represent finalized tasks as a runtime task graph.
- Add dependency-aware batch formation, dynamic batch execution, task/batch
  routing, blocked handling, recovery, and rework scoping.

Acceptance criteria:

- Execute source shows DAG batch iteration.
- Runtime resumes from a partial task frontier.
- Blocked recovery is a named control-plane route.
- Task complexity model routing appears in explain output.
- No-review robustness terminal routes remain compatible.

### Epic J: Native Conformance And Merge Result

Sprint estimate: 1 sprint.

Scope:

- Repeat M7/M8-style conformance for native constructs.
- Regenerate docs, examples, skills, CLI snapshots, package ledgers, and
  manifest identity ledgers.
- Document migration for manifest/schema changes.

Acceptance criteria:

- Source/wheel/sdist gates pass.
- Dynamic import and deleted-surface audits pass.
- Native explain/render assets match the new source of truth.
- In-flight session compatibility is tested or explicitly documented.

## 4. Sprint Rollup

Assuming 2-week sprints and one full-time senior engineer, the proposed
follow-up set totals **20 sprints**, or roughly **40 engineer-weeks**.

Per-epic sizing:

| Epic | Estimate | Sizing rationale |
| --- | ---: | --- |
| A. Native Authoring Architecture Decision | 1 sprint | Documentation and architecture decision, no runtime or compiler changes. |
| B. Dynamic Fanout And Foreach | 3 sprints | New manifest/source/runtime dynamic topology with partial fanout resume and explain/render support. |
| C. Typed Loop Outcomes | 2 sprints | Moderate manifest/compiler extension that reuses existing loop and branch lowering. |
| D. Policy Call-Site And Model Routing | 2 sprints | New model-route policy shape plus retry/timeout/escalation call-site lowering. |
| E. Human Control Plane And Override Topology | 2 sprints | Mostly override extraction, with authority/evidence schemas and compatibility tests. |
| F. Gate-Native Extraction | 2 sprints | High-risk handler extraction, but largely reuses existing gate phase bodies and new C/D primitives. |
| G. Critique And Review Native Extraction | 2 sprints | Broad extraction over two quality handlers, assuming B/C/D have supplied fanout, outcomes, and retry policy. |
| H. Tiebreaker Native Subworkflow | 2 sprints | Isolated subworkflow extraction with fixed researcher/challenger branches and human decision routing. |
| I. Execution DAG Native Runtime | 3 sprints | New DAG task schema, runtime scheduler, frontier resume, and execute extraction over the stateful batch path. |
| J. Native Conformance And Merge Result | 1 sprint | M7/M8-style certification pass, assuming each feature epic already carried targeted tests. |

Serial calendar:

- One senior engineer running the work serially should plan for about
  **20 sprints**, or **40 weeks**. With ordinary review, stabilization, and
  release overhead, this is roughly **9-10 calendar months**.

Parallel tracks after Epic A:

- **Architecture gate:** Epic A must complete first.
- **Foundation track:** Epics C and D can run in parallel after A; Epic B can
  start after A but should align its per-item retry/timeout vocabulary with D.
- **Control-plane and extraction track:** Epic E follows C; Epic F follows C
  and D; Epic G follows B and C and benefits from D.
- **Subworkflow track:** Epic H can begin after A/C using fixed fanout, but
  final pick/escalate/replan semantics should align with E.
- **Execution track:** Epic I should wait for B, C, D, and E.
- **Certification track:** Epic J runs last after the native extraction work
  has landed.

With enough parallel staffing, the dependency-shaped critical path is roughly
**9-11 sprints**, or **18-22 calendar weeks**: A, then the foundation wave,
then human/control and quality extractions, then execution DAG, then final
native conformance. Extra staff helps with B/C/D/E/F/G/H overlap, but it does
not remove the critical path through A, the foundational constructs, I, and J.

Assumptions and estimate risks:

- Estimates assume M1-M8 land cleanly and provide the Python-shaped compiler,
  CLI, explain/render, runtime conformance, installed-wheel, and generated-asset
  baselines described above.
- Estimates assume each feature epic includes targeted unit, golden,
  characterization, explain/render, and installed-artifact tests; Epic J is an
  integration certification pass, not deferred testing for all prior work.
- B and I grow if partial resume, reducer ordering, or task-frontier replay
  require deeper runner changes than the current manifest cursor and journal
  substrate can support.
- F, G, and I grow if existing Megaplan auto-drive behavior depends on hidden
  handler side effects that cannot be preserved behind phase-body extraction.
- Any manifest schema/hash compatibility break that requires dual-version
  migration or in-flight session upgrade support can add at least one sprint to
  the affected epic or to Epic J.

## 5. Recommended Sequencing

Do first:

1. Finish M1-M8 without expanding them into the native report.
2. Run Epic A immediately after M8.
3. Choose source-line and manifest-version strategy before adding dynamic
   constructs.

Can proceed in parallel after Epic A:

1. Epic B, Dynamic Fanout And Foreach.
2. Epic C, Typed Loop Outcomes.
3. Epic D, Policy Call-Site And Model Routing.

Should wait for foundations:

1. Epic E should wait for typed outcomes, but authority/evidence schemas can be
   designed earlier.
2. Epic F should wait for typed outcomes and policy call-sites.
3. Epic G should wait for dynamic fanout and typed outcomes.
4. Epic H can start with fixed two-branch fanout, but should finalize after
   human decision and loop re-entry semantics settle.

Should wait longest:

1. Epic I should wait for dynamic fanout, typed outcomes, model routing, and
   human recovery routes.
2. Epic J should run after any major native extraction before declaring native
   Megaplan complete.

Recommended order:

1. Native Authoring Architecture Decision.
2. Typed Loop Outcomes.
3. Policy Call-Site And Model Routing.
4. Dynamic Fanout And Foreach.
5. Human Control Plane And Override Topology.
6. Gate-Native Extraction.
7. Critique And Review Native Extraction.
8. Tiebreaker Native Subworkflow.
9. Execution DAG Native Runtime.
10. Native Conformance And Merge Result.

Rationale:

- The architecture decision prevents a second source-of-truth split.
- Loop outcomes and policy call-sites clarify the language before high-risk
  runtime changes.
- Dynamic fanout unlocks critique, review, and execute, but needs deterministic
  policy and outcome vocabulary.
- Gate extraction should precede execute extraction because gate decides whether
  execution is legitimate.
- Execute has the broadest state, recovery, artifact, and model-routing blast
  radius, so it should come late.

## 6. If We Only Do One Thing Next

After M8, do the **Native Authoring Architecture Decision**.

The Python-shaped epic intentionally delivers a manifest-first source frontend.
The native report asks for a richer native-program representation. The next
implementation should not add dynamic fanout, loop outcomes, model routing, or
event transitions until the repo has one chosen future authoring line and one
manifest compatibility strategy.

The concrete output should be a checked-in decision doc plus a target Megaplan
source sketch showing critique/gate/revise, tiebreaker, execute/review/rework,
human suspension, dynamic fanout, policy call-sites, and override transitions in
the chosen future syntax.
