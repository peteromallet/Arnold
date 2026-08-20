---
id: 01KY2DWSJG0B9YKAJRYA0107XE
title: Build a reusable native workflow-pattern platform after Megaplan parity
status: open
source: human
tags:
- platform
- architecture
- workflow
- reuse
- follow-up
codebase_id: null
created_at: '2026-07-21T13:29:55.536587+00:00'
last_edited_at: '2026-07-21T19:10:44+00:00'
epics: []
---

## Problem

The Native Parity corrective epic is designed to make Megaplan one readable,
source-authoritative Python workflow. It deliberately does not prove the next
platform-level outcome: that useful steps and subworkflows are packaged,
documented, versioned, and reusable by unrelated workflows without importing or
copying Megaplan.

This should be a separate follow-on epic, not concurrent implementation inside
Native Parity. Native Parity must design for extraction now, but reusable product
patterns should be stabilized only after one correct implementation and a second
real consumer exist.

## North Star

Arnold is a workflow-component platform, not only a runtime with reusable
helpers. An unrelated workflow package can import qualified, contracted steps
and subworkflows, bind its own typed domain objects, policies, capabilities,
storage, and effects, compose them in native `.pypeline` Python, and execute
them from a clean installed package—without importing Megaplan, copying its
implementation, or acquiring different semantics because the parent,
composition shape, host, package version, policy, or compatible implementation
changed.

Every exported component has a stable identity, typed ports, declared runtime
dependencies, explicit lifecycle semantics, isolated durable state, and known
authority/effect boundaries. The same component contract applies whether it
runs at the root, inside a subworkflow, in a bounded loop, in fanout/fanin, or
across suspension, retry, cancellation, and resume.

Given only a component descriptor and locked package graph, Arnold can determine
whether the component may be inserted into a composition, reject invalid
compositions before product work, execute valid ones with consistent semantics,
explain their causal history, and resume them on another compatible worker
without knowing anything about Megaplan.

The intended layering is:

```text
Arnold workflow platform
  authoring, lowering, execution, identity, suspension, effects

Reusable workflow patterns
  evaluator panels, bounded refinement, human gates,
  dependency-ready execution, review/rework, effect-safe actions,
  terminal/control arbitration

Product workflows
  Megaplan, a non-Megaplan reference consumer, future workflows
```

The shared layer owns orchestration mechanics. Product packages own domain
meaning, domain outcomes, artifacts, policies, and effect implementations.

Completion must prove five different claims rather than treating them as one:

1. **Source reuse:** consumers call the same implementation without copying or
   reverse product imports.
2. **Clean-wheel reuse:** independently installed packages can import and run it.
3. **Deterministic dependency reuse:** every host resolves the same qualified,
   content-addressed component graph.
4. **Shape-independent reuse:** supported nesting, looping, fanout, retry,
   suspension, and cancellation do not silently change the component contract.
5. **Behavioral substitutability:** a compatible implementation or version can
   replace another under the same black-box contract.

## Dependency and handoff

Do not launch until `megaplan-native-parity-corrective` completes with its
content-addressed completion manifest and golden trace proof. Native Parity
should hand off:

- a reusable-candidate inventory and dependency map;
- stable typed ports/outcomes/policy/effect contracts;
- source-to-runtime golden trace adapters;
- proof that generic primitives do not import Megaplan;
- explicit classification of core primitive, stable reusable pattern,
  experimental pattern, or Megaplan-specific behavior.

## Candidate reusable patterns

- Dynamic evaluator panel with runtime children, retry, sequential fallback,
  reducer, and stable item identity.
- Bounded evaluate/decide/revise loop with caps, no-progress detection,
  escalation, and typed exits.
- Typed human decision gate with capability, suspension, durable reentry, and
  drift handling.
- Dependency-ready executor with worker cap, exact child identity, partial
  restart, and aggregation.
- Review/rework/refinalization cycle.
- Effect-safe action with intent/outcome, idempotency, ambiguity, and
  reconciliation.
- Closed terminal arbitration for cancel, publish, deliver, and completion.

Not every Megaplan phase should be generalized. Product-specific planning,
critique, gate, finalization, and task semantics remain in Megaplan unless a
second consumer proves the shared abstraction.

## Proposed epic

### S1 — Component standard and extraction inventory

- Consume the Native Parity completion manifest.
- Classify all steps/subworkflows and freeze dependency direction.
- Freeze Component Descriptor v1 for steps, subworkflows, and workflows:
  qualified identity; typed input/output/outcome/state schemas; required and
  optional dependencies; capabilities; policies; effects/compensations;
  suspension/reentry; identity; boundary version; state/artifact/effect
  namespaces; resource/cancellation context; authoring-profile version;
  declared nondeterminism and LLM slots; checkpoint payload class/limits; effect
  replay/idempotency semantics; and extension points.
- Freeze a versioned deterministic durable-Python authoring profile. Specify
  permitted control and data constructs, canonical collection iteration, and
  stable keys for dynamic children. Forbid ambient time, randomness,
  environment reads, filesystem/network I/O, process/global mutation, and
  undeclared concurrency in orchestration code; expose clock, entropy,
  configuration, I/O, effects, human input, and LLM calls only through declared
  runtime providers. Deterministic decisions may re-execute on replay;
  non-repeatable boundaries must consume a recorded accepted outcome.
- Require route-bearing decisions to consume only schema-qualified canonical
  values: no host-dependent paths, arbitrary float behavior, unordered
  containers, completion-order reducers, mutable sibling context, or open
  exception sets. Fanout freezes digest-bound bindings at admission, reducers
  consume canonically keyed multisets, and phase failures enter topology only as
  declared typed error outcomes.
- Define the source/generated-artifact ownership stack:
  `.pypeline` source is the sole product control-flow authority; the compiler
  and source map preserve it; generated `WorkflowManifest` and component
  descriptors own immutable admitted runtime coordinates but may not add,
  erase, or reinterpret routes; the content-addressed component/dependency lock
  fixes executable selection; and the action-admission envelope joins those
  bindings with Run Authority, Custody, and WBC. Product Plan Contracts remain
  consumer-owned input/interface contracts, not platform authority.
- Define one versioned component lifecycle protocol. Specify admission,
  authority/custody/WBC validation, body execution, checkpoint, retry,
  suspension/resume, cancellation, compensation, typed return, and terminal
  acceptance. Separate declared business outcomes from closed lifecycle/control
  terminals such as cancellation, deadline/budget exhaustion, infrastructure
  failure, and compensation disposition; internal suspension is a lifecycle
  transition, not automatically a returned business outcome.
- Define a root-host adapter as the sole layer that can map an eligible
  component result to a proposed root product terminal. Nested hosts bind local
  business/control results to parent ports; the root adapter additionally
  performs terminal arbitration CAS and current RA/Custody/WBC validation
  before one accepted root terminal. Component bodies cannot accept a root
  terminal directly.
- Add outcome-condition contracts to every closed business outcome: payload
  schema, semantic postcondition/invariant, required durable evidence,
  effect/compensation completeness, and emission mode (`return`,
  `suspend_then_continue`, or lifecycle/control terminal eligibility). Products
  provide domain predicates through typed bindings; the platform standardizes
  their declaration, evaluation, and fail-closed behavior.
- Define the composition algebra: port and outcome binding, context inheritance
  and narrowing, retry scope, fanout/fanin behavior, checkpoint cursor joining,
  cancellation/deadline/capability/budget propagation, compensation scope, and
  legal nesting. Children receive narrowed—not widened—scopes, with declared
  reservation, charge, release/refund, retry, cache-hit, cancellation, and late-
  completion accounting.
- Define same-child resume versus explicit new-child generation. A parent retry
  reuses the original child's durable terminal/effect outcome by default; a
  non-idempotent effect can repeat only as a new logical action with a distinct
  semantic occurrence, fresh admission, and declared repeat policy, after any
  ambiguity is reconciled.
- Define a durable parent-loop ledger: persist generation and stable child key
  before admission; consume one child terminal by CAS; persist accumulator and
  next/exit decision before starting the next generation; resume from the first
  incomplete transition after a crash.
- Define a closed `JoinPolicy` for all/any/quorum/reducer-threshold fanout:
  required successes, tolerated failures, tie precedence, loser cancellation,
  late-result disposition, terminalization, and deterministic arbitration of
  simultaneous success, failure, cancel, deadline, and budget events.
- Define child Custody disposition on parent cancellation. Parent cancel fences
  new child actions, records and propagates cancellation, and reaches its
  accepted terminal only after each required child terminal plus epoch-checked
  idempotent release/transfer, or declared lease expiry. A parent terminal may
  not imply a release that did not occur.
- Add three bounded durable composition primitives: a typed exit targeting a
  declared named enclosing loop; a typed reconfigure transition that checkpoints
  the current cursor, accepts a typed configuration delta, rebinds admitted
  policy/executable identity, and resumes the same cursor under a new generation;
  and a durable agentic-phase boundary with a closed outer outcome/WBC protocol
  whose runtime-count tool calls still use effect intent/outcome and budgets and
  cannot own outer product routing.
- Define canonical port/outcome/state serialization and validation, qualified
  type identity, closed-outcome exhaustiveness, and backward/forward/breaking
  compatibility classes.
- Define checkpoint payload discipline: canonical serialization; inline and
  aggregate size bounds; mandatory artifact references above the threshold;
  content digest, schema, version, retention, and liveness requirements; and
  rejection of nonportable handles or undeclared sensitive material.
- Define LLM Invocation Contract v1: prompt template/version/digest, model
  capability and resolved provider/model, tool-set/schema versions, decoding
  and routing policy, input/context digest, and token/cost/deadline budget
  policy. Specify checkpoint/cache invalidation, accepted-output and usage
  recording, deterministic replay without another model call, and explicit
  retry/fallback attempt causality. Products own prompt content, model choices,
  tools, and budget values through typed bindings.
- Define an explicit typed binding environment and deterministic precedence for
  policies, capabilities, effects, storage, and other runtime dependencies.
- Standardize the minimum portable event envelope for component instance,
  parent, lifecycle, decision, authority, custody, WBC, checkpoint, effect, and
  terminal causality.
- Define normalized partial-order trace equivalence: exact event multiplicity;
  per-instance/attempt total order; declared parent/child/effect happens-before
  edges; accepted and rejected-late arbitration facts; allowed unordered sibling
  sets; and an allowlist of volatile fields normalization may erase. It may not
  deduplicate events, invert causality, or sort away a race.
- Define two compatibility claims. `new_instance_compatible` permits a
  conforming substitute for newly admitted instances. `resume_compatible`
  additionally requires identical durable checkpoint/state/effect semantics or
  an admitted migration; otherwise suspended instances stay pinned or take an
  explicit quarantine/new-run path.
- Separate protocol invariants from consumer-owned policy values and domain
  meaning.
- Add reverse-import and hidden-global-state checks.

Gate S1 on executable/reference transition models plus invalid descriptor and
composition corpora, not prose alone. They must cover forbidden nondeterminism,
noncanonical decision values, unstable iteration/child identity, mutable fanout
bindings, completion-order reducers, open exception routing, undeclared I/O or
LLM calls, oversized/noncanonical checkpoint payloads, stale artifact refs,
prompt/tool/model identity drift, generated manifests that alter source
topology, local/root terminal confusion, illegal outcome conditions/emission
modes, retry/new-generation confusion, every loop-ledger crash edge, invalid
named-loop exits, ambient reconfiguration, agentic outer-route leakage,
quorum/cancel/deadline/budget races, stale Custody releases, and trace
normalizers that hide multiplicity or causality.

S1 also freezes a versioned DX corpus, named benchmark machine/environment, and
numeric thresholds before S2 begins: every negative diagnostic has the expected
stable code, authored span, semantic path, and supported rewrite or explicitly
unsupported-boundary recipe; every injected runtime fault identifies authored
call site and instance; compile and no-network local-test p50/p95 targets cover
named small/reference compositions; repeated runs meet declared normalized
trace equality; every route divergence is attributable to a declared outcome or
decision discriminant; zero hidden-route mutations pass; and a timed ten-task
author simulation meets its completion/error-recovery target.

### S2 — Enforced composition, resolution, and package surface

- Establish the reusable-pattern package and stable exports/discovery.
- Add product-neutral `validate_component` and `validate_composition` passes,
  required before lowering or authority acquisition.
- Enforce the durable-Python profile before lowering. Every rejection has a
  stable diagnostic code, exact user-source span, plain-language reason, legal
  rewrite/example, and contract link; report independent violations together.
- Lower every component kind through the common lifecycle and composition
  protocol.
- Implement the root-host adapter separately from component bodies and nested
  hosting while reusing the common lifecycle engine. Reject direct root-terminal
  emission, missing business/control result mapping, outcomes without satisfied
  condition/evidence/emission-mode contracts, and implicit promotion of an
  internal suspension to a parent result.
- Lower named enclosing-loop exits and typed reconfiguration into explicit
  checkpointed transitions, never sentinels, exception control flow, or mutable
  ambient context. Lower a durable agentic phase as one declared outer
  occurrence with closed results and a WBC protocol while retaining distinct
  effect records and budget charges for internal tool calls.
- Preserve source maps through `.pypeline` source, IR, generated
  `WorkflowManifest`, and runtime component instances. Compiler errors, runtime
  failures, and causal traces identify the user's file, function, call site,
  semantic path, and instance; internal frames are supplementary rather than
  the only traceback.
- Support typed, inspectable policies/effects/capabilities and native
  `.pypeline` composition with no ambient mutable authority or product defaults.
- Derive disjoint component state, checkpoint, artifact, identity, custody, and
  effect namespaces from composition path plus semantic instance key; shared
  resources require explicit ports.
- Implement the durable parent-loop ledger and same-child/new-generation rules
  in the production lifecycle path. A parent retry after a durable child outcome
  consumes that result; ambiguity reconciles before progress; only an explicit
  new logical action can repeat a non-idempotent effect.
- Enforce `JoinPolicy` and resource-scope propagation through the shared
  arbitration/lifecycle primitives rather than scheduler timing. Scheduling may
  dispatch already accepted work but may not choose retry, escalation,
  reconfiguration, cost/stall, or terminal routes. Budget/capability/deadline
  scopes cannot widen in a child, and reservations/charges/releases reconcile.
- Integrate parent cancellation with exact child Custody targets and epochs:
  fence admission/action, record/propagate cancellation, accept idempotent
  release/transfer or declared expiry, reject stale children after reassignment,
  and retain accepted plus rejected-late race facts.
- Generate mechanical Run Authority/Custody/WBC bindings from semantic
  declarations; authors must not handwrite platform IDs.
- Define qualified component identity as package, component, contract version,
  and implementation digest. Resolve a content-addressed dependency lock and
  bind it into program/checkpoint digests.
- Generate one admission receipt joining source/program and generated-manifest
  digests; component contract/implementation and dependency-lock digests;
  policy, prompt/model/tool, state, payload, and checkpoint schema bindings; and
  the RA/Custody/WBC coordinates required at the action.
- Execute external effects only through declared slots. Derive the effect replay/idempotency key
  and reconciliation key from run, semantic occurrence/component instance,
  effect slot, and logical action occurrence while keeping retry-attempt
  identity distinct. Persist intent before dispatch and accepted outcome before
  continuation. Replay consumes that outcome; absence or ambiguity follows the
  declared reconciliation path and never silently re-fires the effect.
- Fail closed on unavailable or conflicting constraints, mixed worker versions,
  incompatible contracts, undeclared effects/state, illegal cycles/nesting,
  unhandled outcomes, namespace collisions, nondeterministic identity,
  noncanonical route inputs, incomplete join/resource policies, and outcome
  payload fields that attempt to introduce undeclared route divergence.
- Implement the normalized partial-order comparator over exact multiplicity,
  per-attempt order, declared causal edges, arbitration facts, and unordered
  sibling equivalence classes. Use it for trace and substitution conformance.
- Prove checkout, clean-wheel, and cloud runs select the same locked graph.

Gate S2 on root/nested/fanout lifecycle equivalence, the negative admission
corpus, reproducible clean-wheel resolution, compile-twice and replay-twice
equivalence, source-location snapshots for representative compile/runtime
faults, source/manifest topology equality, and crash injection around every
effect boundary. Add exhaustive root-host terminal, outcome-condition,
parent-loop, same-child/new-generation, non-idempotent ambiguity, Custody
cancel/release/reassignment, and all/any/quorum race injections; mutations that
duplicate/drop/invert/falsely sort trace events or smuggle routes through payload
fields; local/installed normalized lifecycle and admission trace equality for
the same recorded boundary outcomes; and the S1-frozen diagnostic, source-map,
author-simulation, and compile thresholds.

### S3 — Extract under isolation and recomposition proof

- Extract the evaluator panel, bounded refinement loop, human gate, and
  effect-safe action first.
- Parameterize domain types and policies without Megaplan defaults.
- Remove ambient product state, dependency lookup, and default precedence from
  extracted patterns.
- Instantiate the same pattern twice and concurrently with distinct bindings;
  prove instances cannot read, resume, cancel, or reconcile one another's state
  or effects.
- Recompose every first-wave pattern in at least two supported shapes, including
  nesting, loop or fanout, and suspension/cancellation where applicable.
- Use the evaluator panel to prove all/any/quorum races, loser cancellation,
  and late-result evidence; the bounded refinement loop to prove its parent-loop
  ledger plus named enclosing-loop exits; the human gate to prove suspension,
  parent cancellation, and child Custody release/expiry; and the effect-safe
  action to prove parent retry over durable and ambiguous non-idempotent effects.
- Exercise typed checkpointed reconfiguration without ambient mutation and a
  small durable agentic-phase fixture whose variable tool-call count preserves
  closed outer results, individual effect histories, and budget accounting.
- Ship a product-neutral local test kit that runs the production lifecycle and
  validators behind in-memory journal/artifact adapters and a virtual clock. It
  provides typed fakes/spies for phases, policies, effects, capabilities,
  storage, clock/entropy, LLM invocations, and human decisions; human-gate
  suspend/fast-forward fixtures; boundary fault injection; lifecycle/event and
  namespace inspection; and replay from recorded outcomes without real services.
  It must not implement a second set of runtime semantics.
- Make Megaplan consume the shared implementations with unchanged normalized
  golden traces while also passing the generic component conformance suite.

Gate S3 on concise local tests for each first-wave pattern covering success,
human suspend/fast-forward (including stale, duplicate, and wrong-capability
reentry), replay without repeated effects or LLM calls, and two concurrent
instances. Set a local-test latency budget that does not require deployed
RA/Custody/WBC services, cloud workers, or live models; integration conformance
still exercises the real joins. The gate also covers same-child resume versus
new generation, checkpoint/replay at every parent-loop ledger edge,
all/any/quorum joins and late children, cancellation/deadline/budget exhaustion
at each lifecycle edge, partial-order trace assertions with multiplicity,
route-inert payload mutations, and the S1-frozen no-network p50/p95 and
repeatability targets. Given identical recorded boundary outcomes, local and
installed runs must have equivalent normalized lifecycle/admission traces.

### S4 — Adversarial second consumer and substitutability

- Build a deliberately non-Megaplan workflow using multiple shared patterns.
- Use different domain types, outcome vocabulary, artifacts, policies, effects,
  and storage layout.
- Use at least two shared patterns in composition shapes Megaplan does not use,
  exercising different nesting, suspension, cancellation, retry scope, and
  effect/storage bindings.
- Swap one pattern for an independent descriptor-compatible implementation and
  prove `new_instance_compatible` observational substitutability at declared
  ports, outcome conditions/emission modes, business and lifecycle/control
  results, lifecycle events, decisions, effects, partial-order traces, and
  terminals.
- Prove `resume_compatible` separately: an old suspended instance rejects the
  substitute unless durable schemas and semantics are identical and declared
  compatible or an admitted checkpoint/state migration exists. Prove one
  provenance-bearing migration and successful resume, then remove the old
  artifact without a migration and prove quarantine rather than fallback to
  latest code.
- Perform one compatible package/state upgrade and prove pinned-old resume,
  compatible resume, explicit migration, and breaking-change quarantine paths.
- Exercise the ordinary suspended-run evolution matrix: function-body-only,
  topology/control-flow, prompt-only, model/tool/policy binding, port/outcome/
  state/checkpoint schema, and dependency-implementation changes. Each must
  deterministically select retained pinned artifacts, a declared compatible
  resume, an explicit admitted migration, a new run, or quarantine; “latest
  code” is never an implicit resume rule. Include a human gate suspended on v1
  while v2 is deployed and retain old locked wheels plus prompt/tool assets for
  the promised support window.
- Exercise one LLM-backed shared component with different prompt/model/budget
  bindings and one checkpoint payload large enough to require an artifact
  reference, without promoting either consumer's product values into platform
  defaults.
- Make the unrelated consumer use an outcome condition and `JoinPolicy` shape
  that Megaplan does not, plus parent cancellation during a live child/effect.
  Both consumers must pass the same partial-order comparator while only their
  declared predicates and policy values differ.
- Prove product-neutral tooling reconstructs component and parent/child causal
  history for both consumers without importing either product package.
- Prove it imports no Megaplan code and copies no pattern implementation.

Gate S4 separately on content-addressed `new_instance_compatible` and
`resume_compatible` receipts; neither receipt may imply the other.

### S5 — Certification, evolution, and adoption

- Finalize public exports, versioning, documentation, examples, compatibility,
  deprecation, authoring-readability, and edit-locality rules.
- Finalize authoring-profile compatibility; stable compiler diagnostics and
  source-map/user-traceback behavior; the local test-kit API, examples, fakes,
  human-gate fixtures, and latency budget; and the ordinary source/prompt/model/
  tool evolution matrix with pinned-artifact retention policy.
- Define compatibility/change classes separately for Python API, component
  descriptor, serialized state, checkpoints, effects, and observable traces.
- Certify applicable conformance profiles for root-hostability versus nested-
  only use; business/lifecycle-control result separation; outcome-condition
  evaluation; retry-safe non-idempotent effects; durable parent loops; join/
  race/quorum; cancellation/Custody release; resource propagation/accounting;
  named enclosing-loop exits and typed reconfiguration; durable agentic phases
  and canonical decision data; partial-order traces; and separate new-instance/
  resume compatibility.
- Define checkpoint migration rules, deprecation/migration windows, evidence
  required to publish, and registry states: experimental, stable, deprecated,
  and withdrawn.
- Require a content-addressed conformance manifest and the complete
  standardization acceptance suite before a component can be marked stable.
  The manifest declares applicable capability profiles so pure components are
  not forced through irrelevant LLM/effect cases while components that declare
  those boundaries cannot omit their replay, budget, cache, idempotency, or
  reconciliation proofs.
- Define LLM accepted-output replay, cache-key/provenance, token/cost budget,
  retry, and fallback conformance; checkpoint inline/reference, retention,
  redaction, and garbage-collection rules; and effect idempotency/
  reconciliation conformance.
- Publish the frozen DX corpus and benchmark environment with actual compile and
  local-test p50/p95 measurements, diagnostic/source-map pass rates, timed
  author-simulation results, local/installed trace-equivalence results, and
  hidden-route/payload-smuggling mutation results. Applicable missing profiles
  or missed numeric thresholds block stable registry status.
- Produce the reusable-pattern registry and platform completion manifest;
  unproven product abstractions and compiler internals remain experimental.

## Standardization closure contract

The epic is incomplete unless all ten clauses hold:

1. **Descriptor:** every exported component has a qualified, versioned
   descriptor declaring its typed ports/outcomes/state, dependencies,
   capabilities, policies, effects, suspension, identity, authoring profile,
   declared nondeterminism/LLM slots, checkpoint payload bounds, effect replay
   semantics, business outcome conditions/evidence/emission modes, applicable
   lifecycle/control terminals, hostability, and extension points.
2. **Lifecycle:** every component kind follows one enforced protocol with
   explicit legal nesting, retry, suspension/resume, cancellation,
   compensation, business results, lifecycle/control terminals, child return,
   and root-host terminal transitions. Replay consumes recorded accepted phase/
   effect/LLM/human outcomes rather than repeating non-repeatable work, and only
   the root-host adapter may propose a root product terminal.
3. **Composition:** bindings and control propagation are explicit; port,
   outcome, named-loop exit, reconfiguration, retry/new generation, parent-loop
   durability, join/race/quorum, capability/deadline/cancellation/budget scope,
   accounting, Custody release, and namespace rules are statically checkable,
   including canonical decision values, keyed reducers, frozen sibling
   bindings, closed typed errors, canonical iteration, and stable child keys.
4. **Isolation:** instances own disjoint state, checkpoint, artifact, identity,
   custody, and effect namespaces unless an explicit shared-resource port says
   otherwise.
5. **Authority and evidence:** every authority-increasing boundary uses
   generated RA/Custody/WBC integration and exact source, manifest, authoring-
   profile, component, implementation, dependency-lock, policy, prompt/model/
   tool, state, and payload-schema bindings as applicable; evidence remains
   non-authoritative.
6. **Resolution:** execution uses a content-addressed component/dependency lock;
   incompatible or unavailable contracts fail before product work.
7. **Evolution:** compatible and breaking changes are defined across API,
   descriptor, source topology/body, prompt/model/tool/policy, durable state,
   checkpoint, dependency, effect, and trace contracts; active runs use pinned
   artifacts, an explicitly compatible resume, an admitted migration/new run,
   or quarantine. New-instance compatibility and suspended-instance resume
   compatibility are independently certified.
8. **Observation:** a product-neutral event envelope explains component-local
   and parent/child causality across consumers, and normalized trace equivalence
   preserves multiplicity, per-attempt order, declared happens-before edges,
   arbitration facts, and only explicitly unordered siblings.
9. **Conformance:** every stable component passes static, lifecycle, isolation,
   recomposition, fault, clean-wheel, upgrade, and substitution tests plus its
   declared deterministic-authoring, diagnostics, local-test, LLM, payload, and
   effect capability profiles.
10. **Variability:** consumer-owned domain meaning, policy values,
    implementations, and storage enter only through declared bindings and may
    not mutate shared internals or hidden global defaults. Schedulers dispatch
    accepted work but cannot choose route, retry, escalation, reconfiguration,
    cost/stall, or terminal decisions.

## Blocking completion proof

- Shared packages have zero imports from Megaplan.
- Megaplan and the reference workflow consume the same pattern implementations.
- No copied implementation exists in either consumer.
- Both consumers execute from clean wheels.
- Consumer policies/types/effects can vary without modifying shared internals.
- A consumer-specific outcome does not require shared-package changes unless it
  changes the generic protocol.
- Identity, Run Authority, Custody, WBC, checkpoints, and golden traces remain
  correct under different consumer namespaces.
- Metadata, handlers, adapters, projections, and CLI/auto surfaces cannot own
  shared route semantics.
- Generated manifests and component registries preserve source-authored
  topology and cannot introduce or erase product routes.
- Adding a new consumer is possible using only documented public surfaces.
- A component run at root, nested, and inside fanout has an equivalent local
  lifecycle modulo declared parent/namespace differences.
- Component bodies and nested hosts cannot accept root product terminals; the
  root-host adapter maps only eligible condition-satisfying results and passes
  terminal arbitration plus current RA/Custody/WBC validation.
- Business outcomes and lifecycle/control terminals cannot be conflated, and
  each emitted business outcome satisfies its declared condition, evidence, and
  emission-mode contract.
- Extracting a section into a subworkflow and inlining it again preserves
  normalized observable behavior modulo the explicit namespace boundary.
- The same component works sequentially, nested, under a bounded loop, in
  fanout/fanin, across human suspension, and under parent cancellation/retry
  according to the declared composition rules.
- Parent-loop generations, child-terminal consumption, accumulator updates, and
  next/exit decisions survive crash/replay without skips or duplicates; typed
  named-loop exits and checkpointed reconfiguration remain explicit.
- All/any/quorum joins, loser cancellation, late results, and simultaneous
  cancel/deadline/budget events resolve by the declared arbitration order while
  retaining rejected-late evidence.
- Parent cancellation fences child work and reaches its accepted disposition
  only after declared child terminal and epoch-checked Custody release/transfer
  or lease expiry; narrowed capability/deadline/budget scopes and accounting
  reconcile.
- Duplicate and concurrent instances cannot cross-read state, checkpoints,
  effects, custody, or outcomes.
- Missing ports, unhandled outcomes, undeclared effects/state, illegal nesting,
  namespace collisions, incompatible schemas/versions, and hidden product
  dependencies fail before authority acquisition.
- Checkout, clean-wheel, and cloud execution resolve the identical locked
  component/dependency graph; active checkpoints resume pinned code or take an
  explicit migration/new-run path.
- Compile/replay equivalence holds under the durable-Python profile; accepted
  human, LLM, and effect outcomes are not repeated on replay.
- Parent retry reuses same-child durable outcomes, including non-idempotent
  effects; only an explicit new generation/logical action may repeat them after
  ambiguity reconciliation and fresh admission.
- Compiler and runtime failures identify the authored file/function/call site
  with actionable diagnostics, and the production-semantics local test kit runs
  representative components without deployed services or live models.
- Prompt/model/tool/policy changes and oversized checkpoint payloads follow
  their declared digest, migration, cache, budget, and artifact-reference rules.
- Descriptor-compatible implementations and compatible versions are
  observationally substitutable for new instances under one black-box suite;
  suspended instances require a separate resume-compatible receipt or admitted
  migration.
- Partial-order trace comparison preserves event multiplicity, causal order,
  arbitration, and legal sibling nondeterminism across implementations.
- Canonical decision inputs, keyed reducers, frozen fanout bindings, closed typed
  errors, durable agentic outer boundaries, and route-inert non-discriminant
  payload fields prevent hidden control-flow authority.
- Measured diagnostics, source maps, timed author tasks, compile/local-test
  p50/p95, and local/installed normalized trace equality meet the S1-frozen
  thresholds.
- Generic tooling explains both consumers' component histories without product
  imports.

The decisive acceptance test is an adversarial second non-Megaplan workflow
that imports shared patterns, supplies different domain semantics, recomposes
them into shapes Megaplan does not use, swaps one compatible implementation,
performs one compatible upgrade, and passes the same black-box conformance suite
without knowing Megaplan internals.

## Standardization acceptance suite

The final gate consumes one common, versioned suite covering:

1. Descriptor and static negative mutations.
2. Decompose/reinsert equivalence.
3. Root/nested/loop/fanout/suspension/cancellation recomposition.
4. Duplicate and concurrent instance isolation.
5. Lifecycle crashes around admission, body, checkpoint, effect,
   suspension/resume, compensation, and terminal acceptance.
6. Stale or missing RA, Custody, WBC, executable digest, and dependency-lock
   rejection before action.
7. Deterministic checkout/wheel/cloud resolution and mixed-version rejection.
8. Compatible resume, pinned-old resume, explicit checkpoint migration, and
   breaking-change quarantine.
9. Compatible implementation and version substitution.
10. Cross-consumer product-neutral causal explanation.
11. Policy/effect/type variability confined to declared bindings and digests.
12. Registry publication, deprecation, withdrawal, and conformance-manifest
    enforcement.
13. Deterministic authoring negatives plus compile-twice and replay-twice
    equivalence.
14. Actionable compiler diagnostics, preserved source maps, and user-code
    runtime tracebacks.
15. In-process production-lifecycle tests with phase, effect, LLM, and human
    fakes, including human-gate fast-forward.
16. No repeated external effect, LLM call, or human action when an accepted
    recorded outcome is replayed.
17. Prompt/model/tool/policy identity, token/cost budget, cache provenance,
    retry, and fallback behavior.
18. Checkpoint inline-size bounds, artifact-reference durability, retention,
    redaction, and recovery.
19. Suspended-v1/deployed-v2 behavior across the ordinary source, topology,
    prompt, binding, schema, and dependency change matrix.
20. Source -> generated manifest -> component lock -> admission receipt
    provenance and topology equality.
21. Root-host adapter exclusivity, business-outcome versus lifecycle/control-
    terminal separation, and outcome condition/evidence/emission-mode negatives.
22. Same-child resume versus explicit new generation, including durable and
    ambiguous non-idempotent effects under parent retry.
23. Parent-loop crash recovery at generation, child admission/terminal,
    terminal-consumption CAS, accumulator, and next/exit decision boundaries.
24. Separate new-instance-compatible and resume-compatible substitution,
    including no-migration rejection and one admitted migration.
25. Partial-order trace equivalence preserving event multiplicity, per-attempt
    order, causal joins, arbitration facts, and allowed unordered siblings.
26. Parent-cancel fencing plus child Custody release/transfer/expiry across stale
    epochs and reassignment.
27. All/any/quorum/reducer-threshold joins with loser cancellation, late-result
    disposition, and every meaningful success/failure/cancel/deadline/budget
    race order.
28. Narrowed capability, deadline, cancellation, token/cost/resource budgets and
    reconciled reservation/charge/release accounting across retries, cache hits,
    cancellation, and late completion.
29. Named enclosing-loop typed exits, checkpointed typed reconfiguration, and
    durable agentic phases with closed outer routing and effect-safe tool calls.
30. Canonical decision values, keyed-multiset reducers, frozen fanout bindings,
    closed typed errors, scheduler/route separation, and payload-smuggling
    negatives.
31. S1-frozen measurable DX corpus: complete diagnostic dispositions, source-
    map fidelity, zero hidden routes, timed ten-task author simulation, compile/
    local-test p50/p95, and local/installed normalized lifecycle/admission trace
    equality for identical recorded boundary outcomes.

## Deliberately variable

Standardize where variability is declared and how it is bound, not the values
themselves. Product domain meaning and outcome vocabularies, policy values,
effect/storage implementations, scheduler and transport implementation,
parallel sibling wall-clock ordering, physical persistence layout, UI, and
performance/cost values remain consumer-owned behind declared contracts, while
their binding, identity, admission, recording, and budget enforcement are
platform invariants. Internal compiler APIs remain unstable until deliberately
promoted.

## Non-goals

- Generalizing every Megaplan function.
- Rebuilding Run Authority, Custody, WBC, recovery, or projections.
- Building a workflow marketplace.
- Freezing internal compiler APIs prematurely.
- Inventing abstractions without two concrete consumers.
- Forcing unrelated domains into Megaplan-shaped outcomes.
- Promising arbitrary Python instead of a clear, versioned durable subset.
- Standardizing product prompt content, model selections, policy values, or
  budgets rather than how they are declared, identified, replayed, and evolved.
- Supporting open-ended item streams or opaque polling loops in this epic;
  diagnostics point to deliberately unsupported future event-queue ports.

## References

- `.megaplan/initiatives/megaplan-native-parity-corrective/`
- `.megaplan/initiatives/megaplan-native-parity-corrective/GOLDEN_TRACE_CONTRACT.md`
- `docs/arnold/megaplan-native-parity-corrective-plan.md`
- `docs/arnold/megaplan-native-representation-report.md`
- `.tmp/workflow-standardization-gap/final-report.md`
- `.tmp/workflow-standardization-gap/oracle-answers-summary.md`
- `.tmp/workflow-standardization-gap/oracle-stage2-delta.md`
