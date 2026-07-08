# Megaplan Native Representation Alignment Plan

## Purpose

`docs/arnold/megaplan-native-representation-report.md` is the target shape for
canonical Megaplan. The goal is not merely "Python-authored workflow files"; the
goal is a Megaplan workflow where product semantics are visible in native Python
structure:

- loops are loops;
- gates are branches;
- tiebreaker is a subworkflow;
- review rework is an explicit cycle;
- human intervention is a suspension point;
- task execution fanout is not hidden behind one opaque handler;
- timeout, retry, model routing, escalation, override, and resume behavior are
  declared as workflow structure or policy rather than implicit handler effects.

For this plan, "native Python" means ordinary Python authoring, not a
Python-shaped graph DSL. Decorators, policy objects, and invocable metadata may
annotate functions, but the source language for product orchestration is Python
branches, loops, function calls, subworkflow calls, and typed return values.
Manual node construction, route tables, generic stage dispatch, component
constants, handler refs, and manifest-authoring APIs are not acceptable
author-facing control-flow constructs for canonical Megaplan.

The author-facing workflow extension is `.pypeline`. A `.pypeline` file uses
Python syntax under Arnold's structured workflow contract; it is validated and
compiled into manifest/runtime artifacts, but it is not an unconstrained `.py`
module and not a hand-authored graph file. The target canonical Megaplan source
is `arnold_pipelines/megaplan/workflows/workflow.pypeline`. A retained
`workflow.py` is compatibility glue only and cannot be the semantic carrier for
implemented report rows.

This document defines how the three follow-up epics should be checked against
that target. It is both a traceability matrix template and a review plan.

## Doctrine Precedence

Use this precedence order when documents appear to conflict:

1. Canonical Megaplan product semantics are owned by visible compositional
   native Python source, declared workflow policy, or an audited pure phase
   body. If a reviewer cannot see the real Megaplan control flow in those
   carriers, the report target is not met.
   The canonical source must read as ordinary Python orchestration. A decorated
   function that still routes through `SOURCE_*`-style component calls, generic
   stage dispatch, route-label tables, handler refs, or manifest/node builders
   is a wrapper around the old model, not report conformance.
   For migrated Megaplan, the semantic source carrier should be
   `workflow.pypeline`; `.py` carriers are acceptable for audited pure phase
   bodies, imported helpers, runtime code, tests, and compatibility shims, not
   for the authored workflow skeleton.
2. `WorkflowManifest` is the stable normalized runtime, replay, inspection, and
   interchange contract. It proves compiled behavior and durable execution, but
   it is not the final Megaplan authoring doctrine and must not become a second
   source of product semantic truth separate from canonical source.
3. `Pipeline.native_program` and projected compatibility shells are migration
   substrate and dispatch compatibility. They are useful proof that execution
   can move away from graph-era bundles, but they never prove report
   conformance by themselves.

A Python-shaped graph wrapper around graph-era components is not native
authoring conformance, even if the wrapper compiles, traces, resumes, and
renders a plausible topology.

The older workflow-manifest-runtime work remains valuable as runtime/kernel
quarry and compatibility evidence. Where it says Megaplan should be authored as
explicit-node manifest data, read that as an intermediate migration substrate
unless a later composition milestone deliberately re-charters it. The final
target remains the native representation report: Megaplan semantics visible in
canonical compositional source and declared policy, with manifests compiled
from that source.

## Governing Sources

- `docs/arnold/megaplan-native-representation-report.md`
- `docs/arnold/megaplan-native-representation-launch-readiness.md`
- `docs/arnold/megaplan-native-representation-traceability.yaml`
- `docs/arnold/megaplan-native-representation-scenarios.yaml`
- `docs/arnold/python-shaped-authoring-contract.md`
- `.megaplan/initiatives/native-python-pipelines-completion/NORTHSTAR.md`
- `.megaplan/initiatives/native-composition-followup/NORTHSTAR.md`
- `.megaplan/initiatives/native-platform-followup/NORTHSTAR.md`
- `.megaplan/initiatives/workflow-manifest-runtime/NORTHSTAR.md` (reconciled
  runtime/kernel source; not an authoring end-state override)
- `.megaplan/initiatives/native-python-pipelines-completion/briefs/*.md`
- `.megaplan/initiatives/native-composition-followup/briefs/*.md`
- `.megaplan/initiatives/native-platform-followup/briefs/*.md`

## Epic Responsibilities

| Epic | Responsibility against the report | Must not claim |
| --- | --- | --- |
| Native Python Pipelines Completion | Establish or preserve migration substrate: native-backed dispatch, resume, trace, package, and test truth so later visible compositional Megaplan work is possible. | Full report conformance; `Pipeline.native_program` as final authoring truth; or any closure based only on non-null native programs, projected shells, route labels, or native traces. |
| Native Composition Follow-Up | Primary delivery epic for the report shape: native compositional source, declared interfaces, subworkflows, loops, routing, tree traces, path resume, and canonical Megaplan as proof target. | That a flat graph, explicit-node manifest, projected shell, or handler-ref wrapper is enough. |
| Native Platform Follow-Up | Production hardening around the report shape: durable backend, side-effect fences, brokered credentials, approval gates, worker leases, cancellation, audit, and reconcile. | Any platform/runtime/manifest design that moves semantic ownership out of canonical source/declared policy and back into opaque handlers or runtime side effects. |

## Traceability Matrix

Every row must end with one of:

- `implemented`: visible in source and proven by tests/rendered topology;
- `enabled`: substrate exists, but a later named epic owns visible Megaplan use;
- `deferred`: explicitly not in scope, with owner and proof gate;
- `missing`: no credible owner or proof.

`missing` is a blocking result for launching or trusting the full sequence. A
row is not `implemented` if the required branch, loop, retry, fanout,
suspension, route, or policy exists only inside a handler body or implicit state
mutation. For composition-owned Megaplan semantics, `enabled` is only an interim
status before the composition epic launches; by the end of that epic the row
must be `implemented` or explicitly `deferred` with a downstream owner and
blocking proof.

For this pre-launch planning pass, `enabled` means the row has an explicit
milestone owner, final shape, proof artifact, and false-pass guard in the
three-epic sequence. It does not mean the report requirement is already
implemented. Closing an owning milestone must update the row to `implemented`
or to a narrower explicit `deferred` status with a downstream owner.

| Report requirement | Current hidden/current surface | Responsible epic | Owning milestone | Status | Required final shape | Required proof | False-pass scenario | Required negative test/source invariant |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Prep clarification gate | `_apply_prep_clarify_gate()` and state mutation in prep/plan handlers. | Composition, with platform durability for waits. | Composition M1/M5, Platform M4 | enabled | `prep` result branches to a declared human suspension/resume path when blocking questions exist. | Source excerpt, rendered route, suspend/resume test, legacy state/cursor compatibility test. | Handler sets a waiting state while topology still shows a single prep node. | Structural conformance fails if the branch is not visible outside handler code. |
| Plan artifact/version metadata | Planner handler writes artifacts and metadata. | Completion/Composition. | Completion M3.5/M5, Composition M1/M6 | enabled | Plan remains a phase, but inputs/outputs/artifacts are declared at the workflow boundary. | Artifact manifest and schema test. | Artifacts are emitted but source does not declare their contract. | Schema/source invariant requires declared boundary names for plan artifacts. |
| Critique skip on bare robustness | Robustness condition hidden in handler/state policy. | Composition. | Composition M1/M6 | enabled | Robustness variant is explicit workflow policy or branch. | Rendered topology for bare/light/full variants and behavior golden. | Bare mode skips in handler only. | Mutation moving skip into handler makes conformance fail. |
| Adaptive critique evaluator retry | Retry loop inside `handle_critique()`. | Composition. | Composition M1/M6 | enabled | Retry is visible at critique call site or declared as step policy. | Retry exhaustion and retry-success tests with event trace. | Retry works but is invisible to topology/policy inspection. | Source invariant rejects retry loops in retained critique handler. |
| Parallel critique lenses with fan-in | `run_parallel_critique(...)` hidden in critique handler. | Composition. | Composition M0/M1/M3/M6 | enabled (M3: `parallel_map` general construct + reducer + canonical critique-fanout node; M6: final lens-selection conformance — handler-purity-gated, unimplemented until structural tests land) | `parallel_map`/fanout over selected checks plus reducer/fan-in is visible. | Dynamic-list fanout fixture, reducer trace, and fallback-behavior test are covered by `test_runtime.py::test_parallel_map_reducer_receives_ordered_results_and_item_paths`, `test_graph_projection.py::test_parallel_map_becomes_dynamic_fanout_stage`, and `valid_m3_canonical_megaplan_topology.py` (critique-fanout parallel_map node with reducer). M6 owns selected-lens wiring and full conformance. | Native trace lists child calls but source still invokes one handler. | Static topology snapshot includes untaken selected-lens branches. |
| Bounded critique/gate/revise loop | Loop partly present as graph policy, termination hidden in handlers/state. | Composition. | Composition M0/M1/M2/M6 | enabled | A visible bounded loop with typed outcomes for proceed, iterate, blocked, escalate, and cap/no-progress termination. | Loop iteration trace, cap test, severity-aware termination test. | A state field jumps back to critique without visible typed outcomes. | Source invariant requires loop bounds and outcome enum at workflow level. |
| Gate preflight and payload normalization | Gate handler normalizes/recover payloads and checks agent availability. | Composition. | Composition M1/M2/M6 | enabled | Preflight, malformed payload recovery, and agent-availability decisions are named gate sub-decisions or declared policies. | Malformed payload golden, unavailable-agent route, topology excerpt. | Bad payload fallback remains buried inside `handle_gate()`. | Handler-purity scan rejects route decisions in gate payload recovery code. |
| Gate signal building and reprompt | Gate handler builds signals, validates flags, reprompts. | Composition. | Composition M1/M2/M6 | enabled | Gate remains a named subworkflow or step cluster with explicit retry/reprompt policy and declared outputs. | Gate retry/reprompt test, route decision golden, artifact schema check. | Gate looks native but reprompt/downgrade lives in handler. | Source invariant requires reprompt policy and downgrade route outside handler. |
| Gate flag/debt/fallback handling | Handler records debt, validates flags, and mutates state. | Composition/Platform. | Composition M1/M2/M6, Platform M4/M6 | enabled | Flag resolution, debt recording, high-complexity downgrade, and fallback routes are explicit effects/events/routes. | Effect/event trace, accepted-with-debt golden, downgrade golden. | Debt flag is written but no explicit product route exists. | Semantic diff fails if debt/downgrade route disappears from topology. |
| Tiebreaker researcher/challenger path | `tiebreaker_run` / `tiebreaker_decide` handlers hide internal split. | Composition. | Composition M1/M3/M4/M6 | enabled (M3: nested workflow invocation with literal `id=` + canonical tiebreaker call-site with `call_site_path` metadata; M4: researcher/challenger split internals; M6: final conformance — handler-purity-gated, unimplemented until structural tests land) | Tiebreaker is a declared subworkflow with researcher, challenger, decision, and parent promotion. | Subworkflow graph, path-addressed trace, and proceed/iterate/escalate tests are covered by `test_source_compiler_api.py::test_source_compiler_m3_native_nested_workflow_requires_literal_call_site_id`, `test_source_compiler_api.py::test_source_compiler_m3_native_nested_workflow_validates_child_input_schema`, `test_canonical_megaplan_conformance.py::test_tournament_has_two_full_tiebreaker_rounds`, and `valid_m3_canonical_megaplan_topology.py` (tiebreaker subworkflow node with `call_site_path: "tiebreaker"`). M4 owns internal split semantics; M6 owns final conformance. | One native node calls old tiebreaker handler. | Structural conformance fails for single handler-backed tiebreaker stage. |
| Human decision/suspension | Human wait states spread across handlers/control. | Composition/Platform. | Composition M1/M5, Platform M2/M4/M6 | enabled | Human gates are explicit suspension points with durable resume coordinates. | Process-death resume test, rendered suspension points, and boundary receipt test. | Status or CLI says waiting, but the durable resume coordinate or suspension authority still lives only in runtime state. | Implemented proof must start from canonical source plus boundary receipts; status/CLI hints and compatibility shells do not satisfy the row. |
| Finalize fallback routes | Finalize handler carries fallback/test-selection behavior. | Composition. | Composition M1/M6 | enabled | Finalize failures, baseline/test selection, and fallback outcomes are declared outputs/routes where they affect control flow. | Finalize failure golden and route test. | Finalize errors are swallowed into artifact flags. | Topology includes failure/fallback routes and tests assert they are taken. |
| Dependency-aware execute batches | Execute DAG and batching live in `execute/batch.py`. | Composition, with platform worker hardening. | Composition M1/M3/M4/M6, Platform M1/M5/M6 | enabled (M3: `parallel_map` for execute batching + canonical execute-batches node with stable call-site identity; M4: DAG dependency internals; M6: full execute conformance — handler-purity-gated, unimplemented until structural tests land) | Execution is not one opaque handler; dependency-aware runtime task batches are visible as a subworkflow or dynamic DAG primitive. | DAG fixture, partial-failure resume test, and task-dependency trace are covered by `valid_m3_canonical_megaplan_topology.py` (execute-batches parallel_map node, tiebreaker-execute-batches node) and `test_canonical_megaplan_conformance.py::test_canonical_shape`. M4 owns DAG internals; M6 owns final execute conformance. | Execute remains one node with richer internal logging. | Structural conformance fails if execute is only one handler-backed stage. |
| Execute approval/no-review/deferred-human gates | Confirmation, no-review, and deferred-human behavior hidden in execute/control code. | Composition/Platform. | Composition M1/M5/M6, Platform M2/M4/M6 | enabled | Approval and deferred-human/no-review choices are declared suspension/effect gates before protected execution or review. | Approval deny/approve/resume tests, no-review golden, deferred-human golden, and boundary receipt test. | Approval works through side effect, but topology cannot show it and a CLI or manifest bridge still supplies the route. | Implemented proof must cite declared execute gates and boundary receipts; CLI handlers and manifest backend routing cannot satisfy the row. |
| Execute/review/rework loop | Review rework path partly route-level, much behavior hidden in review/execute handlers. | Composition. | Composition M1/M4/M5/M6 | enabled | Review can approve, request rework, block, force-proceed, or escalate through an explicit loop. | Review pass/rework/block/force-proceed goldens and loop trace. | Review handler mutates `next_step` to execute. | Mutation hiding rework route in handler must fail conformance. |
| Review parallel checks/fan-in | Review panels and checks hidden in review code. | Composition. | Composition M1/M3/M4/M6 | enabled (M3: `parallel_map` reducer for review fan-in + canonical review-fan-in node; M4/M6: final review panel conformance — handler-purity-gated, unimplemented until structural tests land) | Review fanout and reducer are represented as workflow structure or declared policy. | Parallel-review trace and deterministic-ordering test are covered by `test_runtime.py::test_parallel_map_reducer_receives_ordered_results_and_item_paths`, `test_graph_projection.py::test_parallel_map_becomes_dynamic_fanout_stage`, and `valid_m3_canonical_megaplan_topology.py` (review-fan-in parallel_map node with reducer). M4/M6 own final review panel conformance. | Parallel checks run but topology has one review node. | Static snapshot includes child review checks and reducer. |
| Review infrastructure retry and cap outcomes | Infra failure retry, deferred-human-must route, and repeated failure caps are hidden in review code. | Composition/Platform. | Composition M1/M2/M6, Platform M4/M5/M6 | enabled | Review distinguishes infra retry, blocking failure, advisory failure, deferred human, force-proceed, and cap outcomes. | Infra retry golden, repeated-failure cap golden, force-proceed/block route tests, and authority boundary test. | Cap exhaustion force-proceeds or blocks through handler/control state while source and authority receipts stay silent. | Implemented proof must cite review route policy and cap authority receipts; handler refs, auto next-step hints, and compatibility bridges cannot satisfy the row. |
| Override full action surface | Product control meanings are spread across override handler and control binding. | Composition/Platform. | Composition M1/M2/M6, Platform M2/M6 | enabled | Override routes are explicit product-owned decision paths; neutral runtime only dispatches declared keys. | Override matrix for abort, replan, force-proceed, add-note, resume-clarify, recover-blocked, set-robustness/profile/model/vendor, action-by-action route tests, and authority boundary test. | Only abort/replan are visible; other actions mutate config/state or still depend on components or route bindings. | Implemented proof must cite the override matrix, canonical source, and authority receipts; components, handler refs, route bindings, manifest routing, CLI handlers, and compatibility bridges cannot satisfy the row. |
| Timeout/deadline policy | Phase/runtime timeout logic spread across runtime helpers. | Composition/Platform. | Composition M1/M6, Platform M4/M5/M6 | enabled | Timeout/deadline policy is declared at step/subworkflow call sites or workflow policy. | Timeout event trace, retry/escalation test. | Runtime helper times out but source does not declare retryability. | Source invariant requires timeout/retry policy at call site or named policy object. |
| Model routing by phase/task complexity | Profiles and routing live outside workflow source. | Composition/Platform. | Composition M1/M6, Platform M2/M6 | enabled | Model routing is visible as declared policy keyed by phase/task complexity, without neutral Megaplan literals. | Profile validation, task-complexity route test, rendered policy view. | Correct model is picked by hidden profile code only. | Rendered policy view and negative test for missing route metadata. |
| Runtime-list iteration | Current source compilers reject broad dynamic iteration. | Composition. | Composition M0/M1/M3/M6 | enabled (M3: parallel_map compiler/runtime acceptance with dynamic items=briefs fanout; M6: final conformance) | Supported runtime-list iteration or typed dynamic map for critique/review/execute. | Compiler fixture and runtime trace are covered by `test_runtime.py::test_parallel_map_uses_parameter_precedence_and_preserves_item_order`, `test_compiler.py::test_parallel_map_accepts_workflow_mapper`, `test_compiler.py::test_parallel_map_rejects_dynamic_step_expression`, `test_decorators.py::test_parallel_map_importable`, and `valid_m3_parallel_map_loop_policy` (dynamic `items=briefs` with runtime fanout). | Megaplan uses bespoke helper instead of general native construct. | Compiler acceptance/rejection fixtures prevent Megaplan-only escape hatch. |
| Dynamic parallel map | Fixed fanout exists; Megaplan needs runtime-selected lists. | Composition. | Composition M0/M1/M3/M6 | enabled (M3: parallel_map as first-class native construct with ParallelMapInstruction IR; M6: final conformance) | `parallel_map` or equivalent is a first-class native construct. | Selected-lens fanout fixture and execute-batch fanout fixture are covered by `test_decorators.py::test_parallel_map_instruction_importable` (ParallelMapInstruction IR distinct from ParallelInstruction), `test_graph_projection.py::test_parallel_map_becomes_dynamic_fanout_stage`, `test_runtime.py::test_parallel_map_empty_collection_invokes_reducer_with_empty_results`, and `valid_m3_canonical_megaplan_topology.py` (critique-fanout, execute-batches, review-fan-in nodes all using `parallel_map`). | Fanout only works for hardcoded examples. | Dynamic-list fixture must vary list at runtime and preserve child paths. |
| Typed loop outcomes or break/continue | Existing compiler subsets reject `break`/`continue`. | Composition. | Composition M0/M1/M2/M6 | enabled | Either typed loop outcomes or a safe break/continue subset expresses native loop exits. | Compiler acceptance/rejection tests and route parity. | Handler returns magic strings consumed by generic router. | Source invariant requires typed outcome declarations or accepted Python loop syntax. |
| Auto-drive/event/liveness transitions | Auto-drive and control transitions mutate state through helpers. | Platform, with composition-visible hooks. | Completion M3.5, Composition M1/M6, Platform M4/M5/M6 | enabled | Stall caps, external-provider retry, phase-timeout retryability, cost/context retry, escalation, and status projection are visible as declared overlays/events. | Event replay test, liveness policy test, status projection parity, and cursor projection test. | Auto-drive keeps working, but next-step authority still comes from state, status, or CLI projection instead of canonical workflow events. | Implemented proof must cite source-derived workflow events and cursors; auto next-step derivation, CLI handlers, and projected native shells cannot satisfy the row. |
| Path-addressed checkpoints | Current plan has traces, but nested composition needs stable paths. | Composition/Platform. | Composition M0/M4/M5/M6, Platform M4/M6 | enabled | Every step/subworkflow/loop iteration has stable path identity. | Tree trace snapshot, resume-from-path test. | Flattened trace loses subworkflow identity. | Snapshot asserts nested path identity and resume target. |
| Trace-only native shadow topology | Report recommends a shadow topology before full migration. | Composition. | Composition M0/M1 | enabled | A reviewable native shadow topology exists before behavior switches, showing intended Megaplan product structure. | Shadow topology diff, review signoff, parity notes. | Migration starts directly from handler-backed runtime and drifts. | Epic cannot launch migration milestone without accepted shadow topology. |
| Handler topology extraction/purity audit | Current handlers own routing, loop exits, fanout, and state mutation. | Composition. | Composition M1/M2/M6, Platform M6 | enabled | Retained handlers are pure phase bodies only; product topology moves to workflow source or declared policy. | Handler inventory, purity scan, source excerpts, reviewer signoff. | Handler names are wrapped in native nodes but retain control flow. | Scan for `current_state`, `next_step`, `workflow_transition`, `run_parallel_*`, auto-loop dispatch, and override action dispatch. |
| Golden trace regeneration guard | Existing traces can be regenerated after behavior drift. | All three. | Completion M5, Composition M6, Platform M6 | enabled | Scenario definitions are fixed; regenerated traces require semantic diff review. | Golden scenario manifest, semantic diff checklist, reviewer approval. | Tests pass because goldens were overwritten. | CI fails on unreviewed trace regeneration or missing semantic diff note. |
| Canonical source path reconciliation | Briefs reference future `arnold/pipelines/...` while current code uses `arnold_pipelines/...`; some expected paths may not exist in the current checkout. | Completion/Composition. | Completion M2/M7, Composition M0/M1/M6, Platform M6 | enabled | Each milestone identifies the actual canonical source path and import surface it is changing; migrated Megaplan's authored source is `arnold_pipelines/megaplan/workflows/workflow.pypeline`, with any `workflow.py` retained only as compatibility glue. | Path reconciliation table, `.pypeline` source evidence, import smoke test, and native shell negative test. | Review inspects stale or future path while projected native shells hide that live execution no longer follows canonical source. | Milestone cannot close unless installed package, canonical `.pypeline`, and the native shell negative test agree; `Pipeline.native_program` and `workflow.py` shims are receipts, not proof. |
| Behavior parity with existing Megaplan | Current behavior is broad and handler-heavy. | All three. | Completion M3.5/M5, Composition M1/M6, Platform M6 | enabled | New structure preserves fresh, iterate, tiebreaker, execute/review, human, override, resume, and failure paths. | Golden suite, live smoke, installed-wheel conformance. | Report shape looks good but regressions hide in less common flows. | Scenario goldens cover prep blocking, bare skip, critique retry/fallback, gate reprompt/downgrade, severity cap, tiebreaker pick/escalate/replan, finalize failure, execute approval, DAG partial resume, review infra retry, review cap, and every override action. |
| Source readability | Current source may still be graph-like or handler-ref-heavy. | Composition. | Composition M1/M6 | enabled | A reviewer can understand the real Megaplan product flow by reading the canonical `.pypeline` workflow source. | Human review checklist plus rendered topology diff. | Source has readable names but the important decisions are still elsewhere. | Structural conformance, native-Python anti-wrapper check, and handler-purity inventory are required, not just human readability. |

## High-Abstraction Review Waves

These reviews judge whether the whole sequence is structurally likely to reach
the report target. Each should return findings, missing proof gates, and edits
to North Stars or milestone briefs.

| Wave | Question | Inputs | Output |
| --- | --- | --- | --- |
| H0 Matrix Closure Gate | Before launching each epic, does every row have status, owning milestone, proof artifact, and false-pass test? | Traceability matrix, milestone briefs, current source. | Launch/no-launch verdict and required brief edits. |
| H1 End-State Fit | If all three epics pass as written, does Megaplan look like the report, or merely like a better manifest graph? | Native report, three North Stars, all milestone briefs. | Verdict, blocking gaps, required milestone edits. |
| H2 Sequencing | Are prerequisites ordered correctly, especially substrate before composition and composition before platform hardening? | Chain specs, milestone dependencies, report matrix. | Reordered milestones or explicit dependency gates. |
| H3 Product/Neutral Boundary | Does Arnold stay generic while Megaplan owns product semantics? | Workflow migration docs, cleanup docs, composition/platform briefs. | Boundary risks and scans/tests to prevent leakage. |
| H4 Deferral Honesty | Are any load-bearing report requirements mislabeled as optional or deferred too late? | Traceability matrix and all brief done criteria. | Deferral table with owners and blockers. |
| H5 Proof Sufficiency | Would the proposed tests catch a false pass where handlers still hide semantics? | Test plans, conformance docs, current fixtures. | Required proof gates and golden scenarios. |
| H6 Semantics Carrier Review | For every hidden-logic item in the report, is the semantic carrier canonical source, declared policy, or a deliberately pure phase body? | Report, handler inventory, source excerpts. | Carrier table and required extraction edits. |
| H7 Native Language Sufficiency | Can the native language/runtime express dynamic maps, typed loop exits, policy calls, nested paths, and subworkflow invocation without Megaplan-only escape hatches? | Compiler/runtime source, composition briefs, Megaplan target source. | Missing language primitives, acceptance/rejection fixtures, and sequencing changes. |
| H8 Completion-vs-Conformance Review | Are completion-epic native truth tests being mistaken for report conformance? | Completion briefs, Megaplan migration briefs, matrix statuses. | Rows that are only substrate proof, plus required composition conformance gates. |
| H9 Platform Preservation Review | Does platform durability, brokerage, worker supervision, or reconcile move workflow semantics back into runtime side effects? | Platform briefs, conformance scenario, composition output. | Platform regression checks and post-hardening structural conformance proof. |

## Detail Audit Waves

These reviews inspect one product slice at a time. They should be run after the
matrix is filled once and again before each epic is launched.

| Wave | Slice | Required checks |
| --- | --- | --- |
| D1 Prep/Plan | Prep clarification, plan artifacts, criteria import, open questions, human wait. |
| D2 Critique | Robustness skip, evaluator retry, selected checks, parallel fanout, reducer, fallback. |
| D3 Gate Preflight | Payload normalization/recovery, agent availability, high-complexity downgrade, malformed input backstop. |
| D4 Gate/Revise | Gate signal building, flag resolution, reprompt, debt, fallback, severity termination, revise loop. |
| D5 Tiebreaker | Researcher/challenger split, decision, promotion, escalation, replan, path identity. |
| D6 Finalize | Task generation, baseline/test selection, user actions, fallback/failure routes. |
| D7 Execute DAG | Dependency DAG, batching, model routing, side effects, partial failure, resume/reconcile. |
| D8 Execute Gates | Approval, no-review, deferred-human, protected actions, deny/cancel/resume. |
| D9 Review Fanout | Parallel checks, reducer ordering, infra retry, outcome classifier. |
| D10 Review Caps | Pass/rework/block/escalate outcomes, rework loop, repeated failure caps, force-proceed distinction. |
| D11 Human/Control | Suspension, override action routes, add-note, resume-clarify, recover-blocked, abort, replan, profile/model/vendor changes. |
| D12 Runtime/Trace | Tree traces, checkpoint paths, replay, resume from path, event/control overlays, trace regeneration guard. |
| D13 Policy/Platform | Timeout, retry, model routing, credentials, worker leases, cancellation, audit, conformance. |
| D14 Compiler/Authoring | Dynamic iteration, parallel map, typed loop outcomes, policy call syntax, nested subworkflow invocation, rejection of Megaplan-only escape hatches. |
| D15 Handler Extraction | Handler inventory, purity classification, source invariants, mutation tests that move semantics back into handlers. |

## Milestone Brief Requirements

Every milestone brief in the three-epic sequence must include a `Native
Representation Alignment` section before launch. That section must list:

- matrix rows owned or affected by the milestone;
- row status changes expected by the milestone;
- proof artifacts the milestone will produce;
- false-pass scenarios the milestone explicitly guards against;
- deferrals created or retired, with downstream owner and blocking proof;
- the canonical source paths/import surfaces the milestone will inspect or edit.

A milestone cannot close by saying `native_program` is non-null, route labels
exist, or traces render. It must show that the relevant Megaplan semantics are
visible in canonical workflow source, declared policy, or an audited pure phase
body. Completion-epic milestones may produce substrate proof; composition-owned
report rows still require later structural conformance.

## Required Proof Gates

The final plan should require these proof gates before the sequence is treated
as report-conformant:

- structural conformance test that fails if `critique`, `gate`, `tiebreaker`,
  `execute`, `review`, or `override` are represented only as single
  handler-backed stages;
- native-Python anti-wrapper test that fails if canonical `workflow.pypeline` or its
  imported native subworkflows express product control flow through
  `SOURCE_*`-style component calls, generic stage dispatch, route-label tables,
  handler refs, or direct manifest/node builders rather than Python branches,
  loops, calls, subworkflow calls, typed outcomes, and declared policies;
- handler-purity inventory and scan for `current_state`, `next_step`,
  `workflow_transition`, `run_parallel_*`, auto-loop dispatch, override action
  dispatch, and equivalent routing/state mutation APIs;
- mutation tests that move one visible branch, retry, fanout, or suspension
  route back into a handler and prove conformance fails;
- static topology snapshots that include untaken branches, not only runtime
  traces from a happy path;
- fixed scenario manifest and semantic diff process for regenerated goldens;
- installed-package/source-path reconciliation proving reviews inspect the
  actual canonical source that users run;
- platform post-hardening check proving DB durability, brokered credentials,
  workers, cancellation, and reconcile did not collapse product routes into
  runtime side effects.

## Required Review Prompt Shape

Every review agent should receive:

1. the native representation report;
2. the three North Stars;
3. the relevant milestone briefs;
4. this alignment plan;
5. the current canonical Megaplan source and generated topology if available.

Each review must answer:

- Which report requirements does the plan fully satisfy?
- Which requirements are only enabled, not delivered?
- Which requirements are missing or under-specified?
- What exact milestone brief edits or proof gates would make the plan robust?
- What false-pass scenario could make the team believe the report was satisfied
  when it was not?

## Current Pre-Launch Audit

This planning pass established the pre-launch alignment baseline:

- 31 matrix rows have explicit milestone owners, proof artifacts, final shape,
  false-pass scenarios, and source invariants.
- All rows are `enabled` in the pre-launch sense defined above: they have named
  owners and proof gates, but they are not yet implemented.
- Every milestone brief in the three-epic sequence contains a `Native
  Representation Alignment` section.
- Every brief is referenced by its initiative `chain.yaml`; the completion
  chain runs M1, M2, M3, M3.5, M4, M5, M6, and M7.
- Cross-chain prerequisite references point at initiative-root chain files, not
  stale `briefs/chain.yaml` paths.
- A GPT-5.5 Codex high-reasoning doctrine arbitration on 2026-06-30 found that
  the previous launch audit was only a pre-doctrine baseline. It is not launch
  approval until the manifest/runtime versus compositional-source doctrine is
  reconciled into the plan and the required review waves are rerun.
- Earlier H0-H9 and D1-D15 review waves are recorded in
  `docs/arnold/megaplan-native-representation-review-execution.md`. After the
  doctrine update, H0-H9 and D1-D15 were rerun with GPT-5.5 high reasoning; no
  review returned `BLOCK`, and all `PASS WITH EDIT` findings from those
  doctrine-aware passes have been folded into this plan and the milestone
  briefs.

## Mandatory Doctrine Revalidation

Before implementation chains launch:

- preserve the doctrine-aware H0-H9 and D1-D15 review log as required launch
  evidence;
- treat any future `BLOCK` or unaddressed `PASS WITH EDIT` from H1 End-State
  Fit, H7 Native Language Sufficiency, H8 Completion-vs-Conformance Review,
  D14 Compiler/Authoring, D15 Handler Extraction, D1-D11 scenario slices, D12
  Runtime/Trace, D13 Policy/Platform, or H9 Platform Preservation Review as a
  no-launch condition;
- require every review to state whether it is evaluating source authoring,
  manifest/runtime behavior, or `native_program` compatibility so those proof
  classes are not conflated.

## Chain Launch Preconditions

The executable chain specs for the three follow-up epics use
`driver.require_clean_base: true`. That is intentional: each milestone should
start from a clean base so review findings are about the milestone diff, not
carried local WIP. The chain harness also supports top-level
`launch_preconditions` with `exists`, `contains_text`, `review_log_clean`,
`git_tracked`, and `chain_completed` checks; these are validated by `megaplan
chain verify` and before `megaplan chain start` reaches agent backend preflight.

The launch path must therefore satisfy these invariants:

- the chain spec, `NORTHSTAR.md`, and every milestone brief are committed in
  `HEAD` and clean in the checkout that runs the chain;
- `base_branch` names an existing branch or remote ref; for the current local
  launch pass the three follow-up specs target `main`;
- no generated runtime state lives under `.megaplan/initiatives/**/.megaplan/`;
- launchers must not rely on untracked durable source files when
  `require_clean_base` is enabled, because the chain runner auto-stashes carried
  WIP before `megaplan init` and untracked idea files then disappear from the
  run checkout.
- composition follow-up launch requires the native-python-pipelines-completion
  chain state to prove every current M1-M7 milestone is `done` against the
  current chain spec hash, with plan evidence and merged PR evidence when the
  prerequisite chain uses `merge_policy: review`;
- platform follow-up launch requires both the completion chain and composition
  chain state to prove every current milestone is `done` against the current
  chain spec hash, with plan evidence and merged PR evidence when the
  prerequisite chain uses `merge_policy: review`;
- composition follow-up launch requires the permanent native representation
  report and alignment plan anchors to exist and contain their expected markers;
- all three chains require the machine-readable traceability and fixed scenario
  artifacts to exist with their expected schema markers;
- all three chains require their initiative source directory and every
  load-bearing native-representation document to be committed in `HEAD` and
  clean before launch, so `require_clean_base` cannot stash away staged,
  modified, deleted, or untracked source files;
- platform follow-up launch requires the composition conformance report
  `docs/arnold/megaplan-composition-conformance-report.md`, which composition
  M6 must produce before platform starts.
- final report conformance requires the platform M6 closeout artifact
  `docs/arnold/megaplan-native-representation-conformance-report.md`, the
  machine-readable row ledger
  `docs/arnold/megaplan-native-representation-conformance.yaml`, plus the final
  platform `proof-map.json` and generated
  `.megaplan/initiatives/native-platform-followup/completion-manifest.json`;
  this is the terminal evidence ledger for the three-chain sequence and must
  map every traceability row to implemented or explicitly deferred with proof.

A preflight failure on 2026-06-30 proved this invariant: the first completion
milestone could not initialize because untracked initiative files were hidden by
the `require_clean_base` auto-stash. Treat any recurrence as a launcher
precondition failure, not as a missing-brief authoring failure.

If composition `chain verify` fails before completion M7 lands, or platform
`chain verify` fails before completion M7 and composition M6 land, that is the
expected enforcement behavior. Do not bypass it with manual launch unless the
missing prerequisite is deliberately re-chartered in this alignment plan and
the affected initiative North Star.

Residual risk is execution discipline. The final M6 conformance gates must be
real blockers, not documentation-only checklists. In particular, composition
M6 and platform M6 must refuse closure unless structural conformance,
native-Python anti-wrapper checks, handler-purity inventory, mutation tests,
static topology snapshots, semantic golden review, source-path reconciliation,
and post-platform preservation checks all pass.

Codex GPT-5.5 high-reasoning release-gate review on 2026-07-01 found that
plain label/hash completion was not release-hard enough. The gate now rejects
unsupported failure-policy keys and requires prerequisite chains to have
advanced past all milestones with `done` records, plan names, and merged PR
evidence for review-merge chains. A follow-up GPT-5.5 high-reasoning
adjudication on 2026-07-01 ruled that downstream chain launch also requires an
authoritative completion manifest for each prerequisite chain. That manifest is
content-addressed evidence, not prose: it must bind the prerequisite
`chain.yaml`, `NORTHSTAR.md`, ordered milestone labels, milestone brief paths
and SHA-256 hashes, final milestone status, and declared proof artifact paths
and SHA-256 hashes. It must also record completed plan names and merged PR
metadata, including merge SHA for review-merge chains, so downstream launch can
compare those records against canonical chain state. The dependent `chain_completed`
precondition must use `require_manifest: true` before
`native-composition-followup` or `native-platform-followup` can launch.

The row-by-row traceability matrix is now mirrored in
`docs/arnold/megaplan-native-representation-traceability.yaml`, and the fixed
D1-D15 scenario manifest is now recorded in
`docs/arnold/megaplan-native-representation-scenarios.yaml`. The focused
validator in
`tests/arnold_pipelines/megaplan/test_native_representation_alignment_artifacts.py`
checks the schema, 31 traceability rows, 15 fixed scenarios, row references,
required proof fields, and scenario coverage of every row.

GPT-5.5 Codex high-reasoning launch-readiness review on 2026-07-01 judged
these artifacts sufficient for the current planning/alignment phase and
sufficient to launch only the first prerequisite chain
(`native-python-pipelines-completion`) once the launch checkout has the
load-bearing initiative/docs files committed in `HEAD` and clean. The harness
now exposes `megaplan chain manifest --spec ... --proof-map ...` to write the
content-addressed prerequisite manifest. Completion M7 must run that command
with an explicit proof map, and `native-composition-followup` launch must fail
if the manifest is absent, stale, has no proof artifacts, or no longer matches
the current chain spec, North Star, milestone briefs, proof file hashes, state
records, or review-merge PR metadata.

## Completion Standard

The alignment work is done only when:

- completion-owned substrate rows may remain `enabled` only as named inputs to
  later epics; composition-owned final report rows are `implemented` or
  explicitly `deferred` with downstream owner and blocking proof; no
  report-owned Megaplan semantic may be deferred merely because it still lives
  in a handler, metadata constant, route label, native trace, manifest
  projection, or `native_program` shell;
- no row is `missing`;
- every milestone brief has a `Native Representation Alignment` section and has
  updated the matrix rows it owns;
- prerequisite chain completion for `native-composition-followup` and
  `native-platform-followup` is proven by the canonical chain state plus a
  content-addressed `completion-manifest.json` for each prerequisite chain,
  including current chain/North Star/brief/proof artifact hashes, matching plan
  records, and merged PR metadata for review-merge prerequisite chains;
- high-abstraction reviewers agree the three-epic sequence converges on the
  report, not merely on a cleaner graph/manifest wrapper;
- detail reviewers agree the major hidden-handler behaviors have either been
  lifted into visible workflow structure or intentionally retained as pure phase
  implementation details;
- final conformance includes source excerpts, rendered topology, static topology
  snapshots with untaken branches, trace fixtures, behavior goldens, resume
  tests, native-Python anti-wrapper checks, handler-purity inventory, mutation
  tests, installed artifact checks, and post-platform preservation checks;
- platform M6 has written
  `docs/arnold/megaplan-native-representation-conformance-report.md`,
  `docs/arnold/megaplan-native-representation-conformance.yaml`, final
  `proof-map.json`, and the final platform `completion-manifest.json`, and the
  conformance report plus YAML row ledger prove every row in
  `docs/arnold/megaplan-native-representation-traceability.yaml` is
  implemented or explicitly deferred with downstream owner and blocking proof;
- every implemented row in the final YAML ledger uses `semantic_carrier:
  canonical_source`, `semantic_carrier: declared_policy`, or
  `semantic_carrier: audited_pure_phase_body`; deferred rows use
  `semantic_carrier: explicit_deferral`;
- every implemented row includes `carrier_evidence` paths pointing at the
  source, declared policy, or audited pure phase body that carries the
  semantic, and the validator confirms those paths exist; `canonical_source`
  workflow evidence must be `.pypeline` files, `audited_pure_phase_body`
  evidence may be `.py` files, and `declared_policy` evidence may be
  `.pypeline`, `.py`, `.yaml`, `.yml`, `.json`, or `.md`;
- `python scripts/validate_native_representation_conformance.py --conformance
  docs/arnold/megaplan-native-representation-conformance.yaml` passes against
  the final YAML ledger.

The practical final test is simple: open the canonical Megaplan workflow source.
If the real product flow is not visible there, the sequence has not reached the
native representation target.
