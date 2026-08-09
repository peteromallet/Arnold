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
last_edited_at: '2026-07-21T21:21:51+00:00'
epics:
- epic_id: native-workflow-platformization
  resolves_on_complete: true
  linked_at: '2026-07-21T21:21:51+00:00'
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
storage, and effects, compose them in native `.pype` Python, and execute
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

Completion must prove six different claims rather than treating them as one:

1. **Source reuse:** consumers call the same implementation without copying or
   reverse product imports.
2. **Clean-wheel reuse:** independently installed packages can import and run it.
3. **Deterministic dependency reuse:** every host resolves the same qualified,
   content-addressed component graph.
4. **Shape-independent reuse:** supported nesting, looping, fanout, retry,
   suspension, and cancellation do not silently change the component contract.
5. **New-instance substitutability:** an independently implemented compatible
   component or version can serve newly admitted instances under the same
   black-box contract.
6. **Resume compatibility:** a suspended pinned occurrence resumes only against
   a separately proven compatible executable/state contract, an admitted
   migration/new run, or retained old artifacts; new-instance compatibility
   never implies resume compatibility.

The platform is strict about the claims an execution may make, not hostile to
iteration. Editing a step and running it repeatedly must be a first-class,
low-friction authoring path. Changed code receives a fresh digest, experiment
identity, and isolated namespace automatically; it may consume copied or
recorded inputs in a local or durable sandbox without claiming to be the pinned
executable of an admitted run. Production safety rules become hard precisely at
the boundary where an execution seeks durable replay/resume, external effects,
admitted authority, or stable publication.

## Dependency and handoff

Do not launch until `megaplan-native-parity-corrective` completes with its
content-addressed completion manifest and golden trace proof. Native Parity
should hand off:

- a reusable-candidate inventory and dependency map;
- stable typed ports/outcomes/policy/effect contracts;
- source-to-runtime golden trace adapters;
- the Native Parity diagnostic/DX corpus, benchmark environment, and measured
  baselines to extend rather than independently redefine;
- certified production-store/service atomic-CAS adapters, controlled-producer
  registry rules, and proof-registry incarnation/high-water semantics;
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

## Superseded five-milestone sketch (provenance only)

The detailed S1–S5 sketch below is retained as the proposal that created the
ticket. It is not launch authority. The prepared epic now has six milestones:
S1, S2A, S2B, S4, S5, and S6. Its `decisions/PLATFORM_CONTRACT.md`, current briefs, and
`chain.yaml` supersede the old numbering and ownership below.

In particular, `docs/arnold/pype-authoring-contract.md` freezes one canonical
workflow per `.pype`; private local steps/helpers are allowed; shared leaves
live in `.py`; `.py @workflow` is preview-only; and S2B owns the generic
compiler/linker, package correspondence, refactors, CLI/editor, and DX surface.
Nothing in the historical sketch may be read as permitting multi-workflow or
library-only `.pype`, file export tables/re-exports, or a second authored
subworkflow kind.

### S1 — Component standard and extraction inventory

- Consume the Native Parity completion manifest.
- Classify all steps/subworkflows and freeze dependency direction.
- Publish **candidate/experimental** Component Descriptor v1 for steps,
  subworkflows, and workflows:
  qualified identity; typed input/output/outcome/state schemas; required and
  optional dependencies; capabilities; policies; effects/compensations;
  suspension/reentry; identity; boundary version; state/artifact/effect
  namespaces; resource/cancellation context; authoring-profile version;
  declared nondeterminism and LLM slots; checkpoint payload class/limits; effect
  replay/idempotency semantics; and extension points. Pin its contract version
  for S2 implementation and reproducible receipts, but do not confer stable
  registry status before the unrelated S4 consumer challenges it and S5
  certifies it.
- Publish and pin a candidate versioned deterministic durable-Python authoring
  profile. Specify permitted control and data constructs, canonical collection iteration, and
  stable keys for dynamic children. Forbid ambient time, randomness,
  environment reads, filesystem/network I/O, process/global mutation, and
  undeclared concurrency in orchestration code; expose clock, entropy,
  configuration, I/O, effects, human input, and LLM calls only through declared
  runtime providers. Deterministic decisions may re-execute on replay;
  non-repeatable boundaries must consume a recorded accepted outcome.
- Publish and pin a candidate **execution-mode and enforcement-severity
  standard**. Define five modes with explicit claims and allowed transitions:
  `authoring_preview` for rapid working-tree execution; `durable_sandbox` for a
  fresh experiment or fork using production lifecycle semantics under isolated
  authority/effect bindings; `comparison` for shadow/replay
  evaluation that can record quarantined evidence but cannot route or act;
  `admitted_production` for exactly pinned, authority-bearing execution; and
  `certification` for the evidence-backed publication profile. Classify
  every compiler, lifecycle, binding, effect, compatibility, and publication
  restriction as exactly one of: `always_hard`; `automatic`;
  `production_admission_gate`; `stable_publication_gate`;
  `authoring_advisory`; or `non_durable_only`. The same named rule may have
  different enforcement by mode only where this table declares it; there are no
  implicit warning-to-error promotions.
- Make the mode boundary part of execution identity and evidence. A changed
  function body, prompt, binding, dependency, or policy may run immediately as
  a fresh preview/sandbox/comparison experiment, but cannot silently resume an
  in-flight occurrence pinned to the prior executable. A user-requested
  "continue from here with changed code" is an explicit fork/new-run lineage or
  admitted migration, never a disguised resume. Experimental histories,
  authority keys, external-effect/idempotency domains, caches, checkpoints, and
  projections are namespace-disjoint from admitted production history.
- Require route-bearing decisions to consume only schema-qualified canonical
  values: no host-dependent paths, arbitrary float behavior, unordered
  containers, completion-order reducers, mutable sibling context, or open
  exception sets. Fanout freezes digest-bound bindings at admission, reducers
  consume canonically keyed multisets, and phase failures enter topology only as
  declared typed error outcomes.
- Define the source/generated-artifact ownership stack:
  `.pype` source is the sole product control-flow authority; the compiler
  and source map preserve it; generated `WorkflowManifest` and component
  descriptors own immutable admitted runtime coordinates but may not add,
  erase, or reinterpret routes; the content-addressed component/dependency lock
  fixes executable selection; and the action-admission envelope joins those
  bindings with Run Authority, Custody, and WBC. Product Plan Contracts remain
  consumer-owned input/interface contracts, not platform authority.
- Define manifest evolution before changing serialized topology: schema and
  format versions, canonical hashing, reader/writer compatibility, mixed-worker
  rejection or support rules, and upgrade/quarantine behavior for pinned runs.
  Versioned generated-manifest and WBC producer registrations are governed,
  admitted data; registering a compatible producer must not silently mutate the
  pinned platform-contract identity, while an incompatible registry/schema
  change requires an explicit contract-version disposition.
- Inherit, rather than reinterpret, Native Parity's production arbitration
  contract. Every terminal/decision/input-consumption site resolves through a
  certified **linearizable conditional write** in the real store/service.
  Application read/check/write sequences, process-local locks, and in-memory
  fake CAS are not authority proofs. Bind store/service implementation,
  production adapter provenance, arbitration key/schema, and proof-registry
  incarnation/high-water coordinates into conformance receipts.
- Define one versioned component lifecycle protocol. Specify admission,
  authority/custody/WBC validation, body execution, checkpoint, retry,
  suspension/resume, cancellation, compensation, typed return, and terminal
  acceptance. Separate declared business outcomes from closed lifecycle/control
  terminals such as cancellation, deadline/budget exhaustion, infrastructure
  failure, compensation disposition, and
  `contract_violation(reason=outcome_condition_failed)`; internal suspension is
  a lifecycle transition, not automatically a returned business outcome.
  Business outcomes and lifecycle/control terminals are disjoint tagged unions:
  parents handle or explicitly propagate both, accepted control terminals do not
  implicitly qualify as successful business outcomes, and root mapping never
  erases the original result class or provenance.
- Define a root-host adapter as the sole layer that can map an eligible
  component result to a proposed root product terminal. Nested hosts bind local
  business/control results to parent ports; the root adapter additionally
  performs terminal arbitration CAS and current RA/Custody/WBC validation
  before one accepted root terminal. Component bodies cannot accept a root
  terminal directly. Its separate business-outcome and applicable
  lifecycle/control-terminal maps are statically total: missing, default/catch-
  all, and undeclared entries fail composition before authority acquisition.
  Multiple results may deliberately map to one root product terminal, but the
  accepted record retains the originating result identity, class, evidence,
  terminal-arbitration role, and accepting actor/authority identity. Extraction
  into a root-host adapter may relocate that role but may not erase or fabricate
  its accepted actor provenance.
- Add outcome-condition contracts to every closed business outcome: payload
  schema, semantic postcondition/invariant, required durable evidence,
  effect/compensation completeness, and emission mode (`return`,
  `suspend_then_continue`, or lifecycle/control terminal eligibility). Products
  provide domain predicates through typed bindings; the platform standardizes
  their declaration, evaluation, and fail-closed behavior. Evaluate a pinned
  proposal exactly once at the emitting component's local terminal-acceptance
  boundary and atomically record the evaluation with terminal acceptance.
  Replay consumes the recorded evaluation; parents/root hosts do not recompute
  it. True admits the proposed business outcome; false admits the reserved
  `contract_violation(reason=outcome_condition_failed)` lifecycle terminal and
  may not substitute another business outcome. Missing, stale, ambiguous, or
  unavailable required evidence quarantines/reconciles until determinable or a
  declared lifecycle policy terminates it.
- Define human suspension timeout as a total typed transition graph. Every
  timeout generation advances to one named escalation/suspension generation or
  emits one exact declared business outcome or lifecycle/control terminal. The
  graph is bounded or ends under a declared overall deadline; it has no implicit
  `needs_human`, `blocked`, or `deadline_exhausted` default. Human answer versus
  timeout/escalation or parent cancellation, and two simultaneously valid human
  answers, use declared CAS arbitration and retain every rejected-late fact.
- Define the composition algebra: port and outcome binding, context inheritance
  and narrowing, retry scope, fanout/fanin behavior, checkpoint cursor joining,
  cancellation/deadline/capability/budget propagation, compensation scope, and
  legal nesting. Children receive narrowed—not widened—scopes, with declared
  reservation, charge, release/refund, retry, cache-hit, cancellation, and late-
  completion accounting. Each resource class defines durable reservation,
  committed-charge, unresolved-liability, release/refund, and settlement-proof
  states. Cancellation dispatch never releases capacity. Release requires
  durable resource-specific proof that no further charge can accrue; Custody
  lease expiry alone does not settle token, money, tool, or external-effect
  liability, which remains reserved or unresolved until reconciliation.
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
  a total typed classifier over the child's closed business-outcome plus
  lifecycle/control-terminal union; versioned qualifying predicates; required
  successes; tolerated/fatal non-qualifying results; exact parent results for
  satisfaction and impossibility; tie precedence; loser cancellation; late-
  result disposition; terminalization; and deterministic arbitration of
  simultaneous success, failure, cancel, deadline, and budget events. No result
  may fall through a default, and an accepted control terminal is not a success
  unless the policy explicitly and validly classifies it.
- Define child Custody disposition on parent cancellation. Parent cancel fences
  new child actions, records and propagates cancellation, and reaches its
  accepted terminal only after each required child terminal plus epoch-checked
  idempotent release/transfer, or declared lease expiry. A parent terminal may
  not imply a release that did not occur. If policy permits expiry-based parent
  acceptance without a child terminal, record exactly one typed
  `unresolved_child` fact with child/target/last-epoch/attempt/effect state,
  expiry evidence, and reconciliation obligation; explanation and conformance
  retain it, and later reconciliation cannot rewrite the accepted parent terminal.
- Add three bounded durable composition primitives: a typed exit targeting a
  declared named enclosing loop; a typed reconfigure transition that checkpoints
  the current cursor, accepts a typed configuration delta, rebinds admitted
  policy/executable identity, and resumes the same cursor under a new generation;
  and a durable agentic-phase boundary with a closed outer outcome/WBC protocol
  whose runtime-count tool calls still use effect intent/outcome and budgets and
  cannot own outer product routing. The descriptor declares the only legal
  outer route-influence channel: a closed result discriminant and explicitly
  route-bearing typed payload fields. Undeclared payload metadata, exceptions,
  mutable state, and tool-call ordering are route-inert. Every effectful inner
  call has its own semantic occurrence, exact Custody target/epoch, effect slot,
  intent/outcome identity, attempt causality, and resource charge.
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
- Define the **effective capability-profile closure** mechanically from the
  component descriptor, lowered topology, transitive component graph, and
  resolved policy/effect/model/tool/storage bindings. A descriptor's declared
  profiles are claims, not the source of truth: under-declaration fails initial
  admission, any rebind or migration that changes the closure, and stable
  publication.
- Standardize the minimum portable event envelope for component instance,
  parent, lifecycle, decision, authority, custody, WBC, checkpoint, effect, and
  terminal causality.
- Define normalized partial-order trace equivalence: exact event multiplicity;
  per-instance/attempt total order; declared parent/child/effect happens-before
  edges; accepted and rejected-late arbitration facts; allowed unordered sibling
  sets; and a versioned, content-addressed trace-field table classifying every
  observable field as exact, canonically transformed, relationally compared, or
  ignorable volatile. The table is contract data bound into conformance receipts,
  not comparator-local configuration. Unknown fields fail comparison; raw event
  identity and multiplicity are checked before normalization; normalization may
  not deduplicate events, erase load-bearing relations, invert causality, or sort
  away a race.
- Define two compatibility claims. `new_instance_compatible` permits a
  conforming substitute for newly admitted instances. `resume_compatible`
  additionally requires identical durable checkpoint/state/effect semantics or
  an admitted migration; otherwise suspended instances stay pinned or take an
  explicit quarantine/new-run path.
- Separate protocol invariants from consumer-owned policy values and domain
  meaning. Product iteration/rework/no-progress caps resolve to declared
  business outcomes; platform token, cost, deadline, lease, and infrastructure
  exhaustion resolve through lifecycle/control terminals. Products may bind
  the values and exact declared dispositions, but cannot blur the two result
  classes.
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
partial/default root maps, implicit or unbounded human-timeout routes,
parent-side condition re-evaluation, false-condition business substitution,
incomplete join classifiers or missing impossibility results, cancellation-
dispatch or lease-expiry cost release, silent expiry-based child loss,
quorum/cancel/deadline/budget races, stale Custody releases, unclassified trace
fields, and trace normalizers that hide raw multiplicity, relational facts, or
causality; manifest/producer-registry evolution without a declared compatibility
disposition; application-level fake CAS presented as production authority;
proof-registry rollback/reincarnation; and capability-profile under-declaration.

The corpus also covers the complete mode/severity matrix: every restriction has
one declared class and enforcement disposition in every applicable mode;
changed-code experiment/fork is allowed with fresh identity; silent changed-code
resume is rejected; preview/comparison cannot acquire admitted authority or
production effect/idempotency identity; and no advisory can be promoted into an
admission blocker outside the versioned table.

S1 consumes and extends Native Parity's versioned DX corpus, named benchmark
machine/environment, and measured baselines, then pins the candidate corpus and
numeric thresholds needed for reproducible S2 work. It must not independently
refreeze weaker or incomparable baselines: every negative diagnostic has the
expected
stable code, authored span, semantic path, and supported rewrite or explicitly
unsupported-boundary recipe; every injected runtime fault identifies authored
call site and instance; compile and no-network local-test p50/p95 targets cover
named small/reference compositions; repeated runs meet declared normalized
trace equality; every route divergence is attributable to a declared outcome or
decision discriminant; zero hidden-route mutations pass; and a timed ten-task
author simulation meets its completion/error-recovery target.

### S2 — Enforced composition, resolution, and package surface

- Establish the reusable-pattern package and candidate exports/discovery.
  Contract versions are frozen for implementation and receipts, but registry
  status remains experimental until S5 stable certification.
- Add product-neutral `validate_component` and `validate_composition` passes,
  required before lowering or authority acquisition.
- Compute the effective capability-profile closure from the descriptor, lowered
  topology, transitive locked graph, and resolved bindings. Reject omitted
  required profiles before admission and recompute the closure on rebind,
  migration, substitution, or dependency-lock change.
- Enforce the durable-Python profile before lowering. Every rejection has a
  stable diagnostic code, exact user-source span, plain-language reason, legal
  rewrite/example, and contract link; report independent violations together.
- Implement the S1 mode/severity standard in one product-neutral local test kit
  that uses the production compiler, lifecycle, validators, identity rules, and
  event schemas behind in-memory journal/artifact adapters and a virtual clock.
  It supports running an edited step repeatedly from a typed fixture, a recorded
  component input, or an explicitly selected checkpoint; creates a fresh
  content digest, experiment/fork lineage, attempt identity, and disjoint state/
  checkpoint/artifact/effect namespace for every changed-code execution; and
  groups source-mapped lifecycle, agent/LLM, tool, effect, cost, and terminal
  logs by component occurrence and experiment iteration for side-by-side diff.
  Repeating the same unchanged experiment may be grouped as one authoring
  series, but its attempts and raw events remain individually addressable.
- Default preview and durable-sandbox effects to typed fakes or declared sandbox
  targets. Production effect targets, authority records, idempotency keys,
  caches, and admitted namespaces are inaccessible unless the execution passes
  the explicit production admission path; copying a production step input or
  checkpoint never copies its authority or effect identity. Provide an explicit
  `non_durable_preview` disposition for otherwise unsupported Python so authors
  can inspect local behavior, but mark it incapable of checkpoint, durable
  resume/replay, comparison authority, production admission, compatibility
  proof, or conformance credit. Preview execution may not silently lower an
  unsupported construct to a hidden handler or runtime callback.
- Lower every component kind through the common lifecycle and composition
  protocol.
- Implement the root-host adapter separately from component bodies and nested
  hosting while reusing the common lifecycle engine. Reject direct root-terminal
  emission, missing/default/undeclared business or control result mapping,
  outcomes without satisfied condition/evidence/emission-mode contracts, and
  implicit promotion of an internal suspension to a parent result. Preserve the
  originating result class/provenance through terminal arbitration even when
  multiple local results map to one product terminal, including the relocated
  arbitration role and exact accepting actor/authority identity.
- Implement human timeout/escalation through the S1-pinned total typed graph and
  answer/timeout, accepted-answer/cancel, and answer/answer CAS, never handler
  timing. Implement outcome-condition evaluation and local terminal acceptance
  atomically by proposal identity:
  consume recorded evaluations on replay, accept the reserved contract-violation
  terminal on false, and quarantine/reconcile indeterminate evidence before any
  terminal substitution.
- Lower named enclosing-loop exits and typed reconfiguration into explicit
  checkpointed transitions, never sentinels, exception control flow, or mutable
  ambient context. Lower a durable agentic phase as one declared outer
  occurrence with closed results and a WBC protocol while retaining distinct
  effect records, exact Custody/effect identities, and budget charges for
  internal tool calls. Only declared result discriminants and explicitly
  route-bearing payload fields may influence an outer decision.
- Preserve source maps through `.pype` source, IR, generated
  `WorkflowManifest`, and runtime component instances. Compiler errors, runtime
  failures, and causal traces identify the user's file, function, call site,
  semantic path, and instance; internal frames are supplementary rather than
  the only traceback.
- Support typed, inspectable policies/effects/capabilities and native
  `.pype` composition with no ambient mutable authority or product defaults.
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
  scopes cannot widen in a child. Validate total result classification and exact
  satisfied/impossible parent results. Persist resource-specific reservation,
  charge, unresolved-liability, settlement, release, and refund events so at
  every event committed charges plus unresolved liabilities plus live worst-case
  reservations remain within the admitted parent budget; cancel dispatch and
  Custody expiry alone never release unsettled external liability.
- Integrate parent cancellation with exact child Custody targets and epochs:
  fence admission/action, record/propagate cancellation, accept idempotent
  release/transfer or declared expiry, reject stale children after reassignment,
  and retain accepted plus rejected-late race facts. Expiry-based parent
  acceptance records the typed `unresolved_child` disposition and linked
  reconciliation obligation instead of fabricating release, child terminal, or
  resource settlement.
- Generate mechanical Run Authority/Custody/WBC bindings from semantic
  declarations; authors must not handwrite platform IDs.
- Define qualified component identity as package, component, contract version,
  and implementation digest. Resolve a content-addressed dependency lock and
  bind it into program/checkpoint digests.
- Generate one admission receipt joining source/program and generated-manifest
  digests; component contract/implementation and dependency-lock digests;
  policy, prompt/model/tool, state, payload, and checkpoint schema bindings; and
  the RA/Custody/WBC coordinates required at the action.
- Version, hash, and validate every generated manifest against its reader/writer
  compatibility matrix. Register admitted producer versions through the
  governed WBC producer registry and bind registry incarnation/high-water plus
  producer and production-adapter provenance into the admission/conformance
  receipt; a projection or mutable local registry cannot supply these facts.
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
  sibling equivalence classes. Check raw identity/multiplicity first; load the
  versioned content-addressed field classification from the trace contract;
  reject unknown fields; and preserve relational comparisons. Use it for trace
  and substitution conformance.
- Prove checkout, clean-wheel, and cloud runs select the same locked graph.
- Exercise each authority-bearing arbitration/consumption adapter against the
  real production persistence service with independent clients contending on
  one key. The in-process fake remains useful for author tests but is never a
  substitute for proof of linearizable production CAS.

Gate S2 on root/nested/fanout lifecycle equivalence, the negative admission
corpus, reproducible clean-wheel resolution, compile-twice and replay-twice
equivalence, source-location snapshots for representative compile/runtime
faults, source/manifest topology equality, and crash injection around every
effect boundary. Add exhaustive root-host terminal, outcome-condition,
parent-loop, same-child/new-generation, non-idempotent ambiguity, Custody
cancel/release/reassignment, human answer/timeout/escalation, and all/any/quorum
race injections, including accepted-but-unconsumed answer versus cancel and two
simultaneously valid answers. Require crash tests around condition-evaluation/terminal
atomicity; every root-map entry and missing/default-map negative; qualifying,
non-qualifying, and impossible join cases; eventwise resource-ledger invariants;
settled/unsettled expiry cases; and raw-before-normalized trace checks. Mutations
must duplicate/drop/invert/falsely sort events, introduce unknown fields, erase
relational facts, or smuggle routes through payload fields. Require local/
installed normalized lifecycle and admission trace equality for the same recorded
boundary outcomes plus the S1-pinned diagnostic, source-map, author-simulation,
and compile thresholds.

Add paired mode fixtures proving that edited code may run repeatedly as fresh
preview/sandbox experiments from recorded step input or checkpoint, while the
same edit is denied as a silent resume of the pinned in-flight occurrence.
Negative fixtures attempt production-effect dispatch, authority/idempotency-key
reuse, cache/checkpoint namespace reuse, evidence promotion, and conformance
credit from preview/comparison modes and must fail before action or publication.
Positive fixtures retain and compare per-iteration source, agent/LLM, tool,
effect, cost, outcome, and trace records without overwriting earlier attempts.

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
  qualifying/non-qualifying/impossible results, loser cancellation, and late-
  result evidence; the bounded refinement loop to prove its parent-loop ledger
  plus named enclosing-loop exits; the human gate to prove every typed timeout/
  escalation generation, answer races, suspension, parent cancellation, and child
  Custody release/expiry including `unresolved_child`; and the effect-safe action
  to prove parent retry over durable and ambiguous non-idempotent effects plus
  resource settlement before release.
- Exercise typed checkpointed reconfiguration without ambient mutation and a
  small durable agentic-phase fixture whose variable tool-call count preserves
  closed outer results, declared route influence, individual effect/Custody
  identities, and budget accounting.
- Exercise and extend the S2 product-neutral local test kit across every
  first-wave extracted pattern and Megaplan's shared implementations. Use typed
  fakes/spies for phases, policies, effects, capabilities, storage,
  clock/entropy, LLM invocations, and human decisions; human-gate suspend/fast-
  forward fixtures; boundary fault injection; lifecycle/event and namespace
  inspection; repeat/fork from recorded component inputs and checkpoints; and
  replay from recorded outcomes without real services. It must not implement a
  second set of runtime semantics, and its fake CAS remains labeled non-
  production evidence rather than satisfying the production-store contention
  profile.
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
at each lifecycle edge, human answer/timeout permutations, settled and unresolved
expiry, eventwise resource-ledger invariants, partial-order trace assertions with
raw multiplicity and the versioned field table, route-inert payload mutations,
and the inherited/S1-pinned no-network p50/p95 and repeatability targets. Given identical
recorded boundary outcomes, local and installed runs must have equivalent
normalized lifecycle/admission traces.

For each first-wave pattern, also edit one implementation or binding and prove
the author can repeat and compare isolated experimental iterations without a
migration declaration, while production-effect leakage, namespace reuse, and
silent resume of the original occurrence remain impossible. Agent/LLM and tool
logs must resolve to the exact pattern instance and experiment iteration in
both Megaplan and the extracted package.

### S4 — Adversarial second consumer and substitutability

- Build a deliberately non-Megaplan workflow using multiple shared patterns.
- Treat S1's descriptor/profile/package surface as a candidate standard to be
  challenged, not a stable truth to be accommodated. Record every abstraction
  changed, removed, or retained because of the unrelated consumer; unresolved
  consumer-specific leakage blocks S5 stable certification.
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
  that Megaplan does not, plus a different statically total root map, human-
  timeout disposition, qualifying predicate/impossibility result, resource-
  settlement policy, and parent cancellation during a live child/effect. Both
  consumers must pass the same partial-order comparator and versioned trace-field
  contract while only their declared predicates and policy values differ.
- Prove product-neutral tooling reconstructs component and parent/child causal
  history for both consumers without importing either product package.
- Prove it imports no Megaplan code and copies no pattern implementation.
- Mutate descriptor-declared profiles and resolved transitive bindings to prove
  that effective capability closure—not self-declaration—selects mandatory
  conformance profiles and rejects under-declaration.
- Make the unrelated consumer use the same five execution modes and enforcement
  taxonomy rather than consumer-local runner conventions. Repeat an edited step
  from a recorded input, fork a suspended occurrence under changed code, compare
  candidate output non-authoritatively, and promote only a separately admitted
  pinned execution. Prove its experimental namespaces and production effects
  cannot collide with Megaplan or with its own admitted runs, and that its
  per-iteration agent/LLM/tool logs remain queryable without product imports.

Gate S4 separately on content-addressed `new_instance_compatible` and
`resume_compatible` receipts; neither receipt may imply the other. The independent
implementation and upgrade must preserve originating business/control result
class, atomic outcome-condition disposition, total root hosting, timeout/join
arbitration, resource settlement invariants, unresolved-child evidence, and raw/
normalized partial-order truth.

The gate also requires identical mode-transition and severity-table behavior
across both consumers, including changed-code experiment allowed, silent resume
denied, preview/comparison promotion denied, and explicit fork or admitted
migration required where lineage crosses executable versions.

### S5 — Certification, evolution, and adoption

- Incorporate the S4 adversarial-consumer changes, then perform the stable
  standard freeze and certification. The earlier contract-version pin made S2–S4
  reproducible; only this gate may promote the resulting descriptor/profile/
  package versions from experimental to stable registry status.
- Finalize public exports, versioning, documentation, examples, compatibility,
  deprecation, authoring-readability, and edit-locality rules.
- Finalize authoring-profile compatibility; stable compiler diagnostics and
  source-map/user-traceback behavior; the local test-kit API, examples, fakes,
  human-gate fixtures, and latency budget; and the ordinary source/prompt/model/
  tool evolution matrix with pinned-artifact retention policy.
- Finalize and certify the five execution modes, their evidence/authority/
  effect/namespace boundaries, the six-class enforcement-severity table, and
  every allowed promotion or demotion transition. Stable certification requires
  the S3 and S4 cross-consumer receipts; neither a preview result, durable-
  sandbox result, nor non-authoritative comparison result can be relabeled as
  admitted production or stable conformance evidence. Promotion always creates
  or consumes the required pinned admission/certification record rather than
  mutating an experimental history in place.
- Publish the cumulative Native Parity → S1–S4 DX corpus and benchmark history,
  with comparable environment metadata and explicit baseline changes; do not
  replace the inherited corpus with a newly selected passing subset.
- Define compatibility/change classes separately for Python API, component
  descriptor, serialized state, checkpoints, effects, and observable traces.
- Certify applicable conformance profiles for root-hostability versus nested-
  only use and total maps; business/lifecycle-control result separation;
  atomic outcome-condition evaluation and contract-violation disposition; typed
  human timeout/escalation; retry-safe non-idempotent effects; durable parent
  loops; total join/race/quorum classifiers; cancellation/Custody release and
  unresolved expiry; resource-specific settlement/accounting; named enclosing-
  loop exits and typed reconfiguration; durable agentic phases and canonical
  decision data; versioned raw/normalized partial-order traces; and separate
  new-instance/resume compatibility.
- Define checkpoint migration rules, deprecation/migration windows, evidence
  required to publish, and registry states: experimental, stable, deprecated,
  and withdrawn.
- Require a content-addressed conformance manifest and the complete
  standardization acceptance suite before a component can be marked stable.
  The manifest records the mechanically derived effective capability-profile
  closure so pure components are not forced through irrelevant LLM/effect cases
  while components that declare those boundaries cannot omit their replay,
  budget, cache, idempotency, or
  reconciliation proofs. It also binds the exact trace-field classification;
  applicable missing profiles, partial maps/policies, eventwise resource-ledger
  violations, or comparator-local/unversioned field exclusions block stable
  registry status.
- Bind certified production-store/service CAS implementation and adapter
  provenance, WBC producer-registry incarnation/high-water, generated-manifest
  schema/hash version, and root arbitration-role/accepting-actor preservation
  into every applicable stable conformance manifest. Missing or fake-only
  authority proof blocks publication.
- Define LLM accepted-output replay, cache-key/provenance, token/cost budget,
  retry, and fallback conformance; checkpoint inline/reference, retention,
  redaction, and garbage-collection rules; and effect idempotency/
  reconciliation conformance.
- Publish the cumulative pinned DX corpus and benchmark environment with actual
  compile and local-test p50/p95 measurements, diagnostic/source-map pass rates,
  timed author-simulation results, local/installed trace-equivalence results, and
  hidden-route/payload-smuggling mutation results. Applicable missing profiles
  or missed numeric thresholds block stable registry status.
- Produce the reusable-pattern registry and platform completion manifest;
  unproven product abstractions and compiler internals remain experimental.

## Standardization closure contract

The epic is incomplete unless all eleven clauses hold:

1. **Descriptor:** every exported component has a qualified, versioned
   descriptor declaring its typed ports/outcomes/state, dependencies,
   capabilities, policies, effects, suspension, identity, authoring profile,
   declared nondeterminism/LLM slots, checkpoint payload bounds, effect replay
   semantics, business outcome conditions/evidence/emission modes, applicable
   lifecycle/control terminals, hostability, and extension points. Admission
   derives the effective capability-profile closure from this claim plus the
   lowered topology, transitive lock, and resolved bindings.
2. **Lifecycle:** every component kind follows one enforced protocol with
   explicit legal nesting, retry, suspension/resume, cancellation,
   compensation, business results, lifecycle/control terminals, child return,
   typed timeout/escalation, atomic outcome-condition/local-terminal acceptance,
   and statically total root-host terminal transitions that retain result class
   and provenance, arbitration role, and accepting actor identity. Replay
   consumes recorded accepted phase/effect/LLM/human/condition outcomes rather
   than repeating non-repeatable work, and only the root-host adapter may
   propose a root product terminal.
3. **Composition:** bindings and control propagation are explicit; port,
   outcome, named-loop exit, reconfiguration, retry/new generation, parent-loop
   durability, join/race/quorum, capability/deadline/cancellation/budget scope,
   resource settlement/accounting, Custody release/unresolved expiry, and
   namespace rules are statically checkable, including total join result
   classification with exact impossibility products, canonical decision values,
   keyed reducers, frozen sibling bindings, closed typed errors, canonical
   iteration, and stable child keys. Product control caps yield declared
   business outcomes; platform resource exhaustion remains a lifecycle/control
   disposition.
4. **Isolation:** instances own disjoint state, checkpoint, artifact, identity,
   custody, and effect namespaces unless an explicit shared-resource port says
   otherwise.
5. **Authority and evidence:** every authority-increasing boundary uses
   generated RA/Custody/WBC integration and exact source, manifest, authoring-
   profile, component, implementation, dependency-lock, policy, prompt/model/
   tool, state, and payload-schema bindings as applicable; evidence remains
   non-authoritative. Authority CAS is a certified linearizable production-
   store/service operation whose adapter and proof-registry incarnation/high-
   water provenance is receipt-bound; fake or application-level read/check/write
   implementations cannot satisfy this clause.
6. **Resolution:** execution uses a content-addressed component/dependency lock;
   incompatible or unavailable contracts fail before product work.
7. **Evolution:** compatible and breaking changes are defined across API,
   descriptor, source topology/body, generated-manifest schema/hash and producer
   registration, prompt/model/tool/policy, durable state, checkpoint, dependency,
   effect, and trace contracts; active runs use pinned artifacts, an explicitly
   compatible resume, an admitted migration/new run, or quarantine. New-instance
   compatibility and suspended-instance resume
   compatibility are independently certified.
8. **Observation:** a product-neutral event envelope explains component-local
   and parent/child causality across consumers, and normalized trace equivalence
   checks raw identity/multiplicity before applying a versioned content-addressed
   field classification, rejects unknown fields, and preserves per-attempt order,
   declared happens-before edges, relational facts, arbitration facts, and only
   explicitly unordered siblings.
9. **Conformance:** every stable component passes static, lifecycle, isolation,
   recomposition, fault, clean-wheel, upgrade, and substitution tests plus its
   mechanically derived deterministic-authoring, diagnostics, local-test, LLM,
   payload, and effect capability-profile closure.
10. **Variability:** consumer-owned domain meaning, policy values,
    implementations, and storage enter only through declared bindings and may
    not mutate shared internals or hidden global defaults. Schedulers dispatch
    accepted work but cannot choose route, retry, escalation, reconfiguration,
    cost/stall, or terminal decisions.
11. **Execution modes:** authoring preview, durable sandbox experiment/fork,
    non-authoritative comparison, admitted production, and stable certification
    share one compiler/lifecycle/event model but have explicit, receipt-bound
    authority, effect, durability, and claim boundaries. Every restriction has
    one versioned enforcement-severity classification. Working-tree edits and
    repeated step tests are easy fresh experiments; unsupported Python may run
    only as an explicitly non-durable preview; changed code cannot impersonate
    a pinned in-flight executable; and experimental evidence cannot leak into or
    be relabeled as production authority or stable conformance.

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
  topology and cannot introduce or erase product routes; their schema/hash and
  producer-registration evolution is explicit and mixed-worker safe.
- Adding a new consumer is possible using only documented public surfaces.
- A component run at root, nested, and inside fanout has an equivalent local
  lifecycle modulo declared parent/namespace differences.
- Component bodies and nested hosts cannot accept root product terminals; the
  root-host adapter has statically total business/control maps, maps only eligible
  condition-satisfying results, retains original result class/provenance, and
  preserves the arbitration role and accepting actor identity while passing
  terminal arbitration plus current RA/Custody/WBC validation.
- Business outcomes and lifecycle/control terminals cannot be conflated, and
  each emitted business outcome atomically satisfies its declared condition,
  evidence, and emission-mode contract at local terminal acceptance. False
  conditions yield the reserved contract-violation lifecycle terminal; ambiguous
  evidence quarantines/reconciles rather than fabricating a business outcome.
- Extracting a section into a subworkflow and inlining it again preserves
  normalized observable behavior modulo the explicit namespace boundary.
- The same component works sequentially, nested, under a bounded loop, in
  fanout/fanin, across human suspension, and under parent cancellation/retry
  according to the declared composition rules.
- Human timeout/escalation follows a total bounded typed transition graph;
  answer/answer, answer/timeout, and accepted-but-unconsumed-answer/cancel races
  consume one winner and retain every rejected-late fact.
- Parent-loop generations, child-terminal consumption, accumulator updates, and
  next/exit decisions survive crash/replay without skips or duplicates; typed
  named-loop exits and checkpointed reconfiguration remain explicit.
- All/any/quorum joins, loser cancellation, late results, and simultaneous
  cancel/deadline/budget events use a total classifier over child business/control
  results, emit exact declared satisfied/impossible parent results, resolve by the
  declared arbitration order, and retain rejected-late evidence.
- Parent cancellation fences child work and reaches its accepted disposition
  only after declared child terminal and epoch-checked Custody release/transfer
  or declared lease-expiry disposition. Expiry-based completion retains typed
  `unresolved_child` evidence and does not imply resource settlement; narrowed
  capability/deadline/budget scopes reconcile under resource-specific durable
  settlement, never cancel dispatch or lease expiry alone.
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
- Authors can edit and repeat any component from a fixture, recorded component
  input, or eligible checkpoint as isolated preview/sandbox experiments, retain
  and compare every iteration's component/agent/LLM/tool/effect logs, and fork
  from a recorded occurrence without modifying the source run. Fresh digests,
  lineages, attempts, namespaces, and non-production effect bindings are
  automatic; no compatibility declaration is required merely to experiment.
- The same changed code cannot silently resume an admitted in-flight occurrence,
  acquire its authority, reuse its production effect/idempotency identity, write
  its history, or count preview/comparison results as conformance. Continuing
  under changed code is an explicit fork/new run, compatible resume, or admitted
  migration according to the pinned mode-transition rules.
- Prompt/model/tool/policy changes and oversized checkpoint payloads follow
  their declared digest, migration, cache, budget, and artifact-reference rules.
- Descriptor-compatible implementations and compatible versions are
  observationally substitutable for new instances under one black-box suite;
  suspended instances require a separate resume-compatible receipt or admitted
  migration.
- Partial-order trace comparison preserves event multiplicity, causal order,
  arbitration, relational facts, and legal sibling nondeterminism across
  implementations; raw identity/multiplicity precede normalization, the field
  classification is versioned/content-addressed, and unknown fields fail.
- Canonical decision inputs, keyed reducers, frozen fanout bindings, closed typed
  errors, durable agentic outer boundaries, declared result/payload route
  influence, exact inner tool Custody/effect identities, and route-inert non-
  discriminant payload fields prevent hidden control-flow authority.
- Measured diagnostics, source maps, timed author tasks, compile/local-test
  p50/p95, and local/installed normalized trace equality meet the inherited and
  S1-pinned
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
7. Deterministic checkout/wheel/cloud resolution; generated-manifest
   schema/hash and producer-registry evolution; and mixed-version rejection.
8. Compatible resume, pinned-old resume, explicit checkpoint migration, and
   breaking-change quarantine.
9. Compatible implementation and version substitution.
10. Cross-consumer product-neutral causal explanation.
11. Policy/effect/type variability confined to declared bindings and digests.
12. Experimental-to-stable registry publication, deprecation, withdrawal, and
    conformance-manifest enforcement after the adversarial consumer.
13. Deterministic authoring negatives plus compile-twice and replay-twice
    equivalence.
14. Actionable compiler diagnostics, preserved source maps, and user-code
    runtime tracebacks.
15. In-process production-lifecycle tests with phase, effect, LLM, and human
    fakes, including human-gate fast-forward, explicitly separated from
    independent-client contention tests against certified production CAS.
16. No repeated external effect, LLM call, or human action when an accepted
    recorded outcome is replayed.
17. Prompt/model/tool/policy identity, token/cost budget, cache provenance,
    retry, and fallback behavior.
18. Checkpoint inline-size bounds, artifact-reference durability, retention,
    redaction, and recovery.
19. Suspended-v1/deployed-v2 behavior across the ordinary source, topology,
    prompt, binding, schema, and dependency change matrix.
20. Source -> versioned/hashed generated manifest -> component lock -> admitted
    producer registration -> admission receipt provenance and topology equality,
    including registry incarnation/high-water and production-adapter provenance.
21. Root-host adapter exclusivity and statically total maps with original-result,
    arbitration-role, and accepting-actor provenance; business-outcome versus
    lifecycle/control-terminal separation;
    atomic condition/evidence/emission-mode acceptance; false-condition contract
    violation; and indeterminate-evidence quarantine/reconciliation negatives.
22. Same-child resume versus explicit new generation, including durable and
    ambiguous non-idempotent effects under parent retry.
23. Parent-loop crash recovery at generation, child admission/terminal,
    terminal-consumption CAS, accumulator, and next/exit decision boundaries.
24. Separate new-instance-compatible and resume-compatible substitution,
    including no-migration rejection and one admitted migration.
25. Partial-order trace equivalence checking raw identity/multiplicity before a
    versioned content-addressed field classification, rejecting unknown fields,
    and preserving per-attempt order, causal/relational joins, arbitration facts,
    and allowed unordered siblings.
26. Parent-cancel fencing plus child Custody release/transfer/expiry across stale
    epochs and reassignment, including typed `unresolved_child` evidence and no
    fictional release, child terminal, or resource settlement on expiry.
27. All/any/quorum/reducer-threshold joins with loser cancellation, late-result
    disposition, total classification of every child business/control result,
    exact satisfied/impossible parent results, and every meaningful success/
    failure/cancel/deadline/budget race order.
28. Narrowed capability, deadline, cancellation, token/cost/resource budgets and
    eventwise reservation/charge/unresolved-liability/settlement/release accounting
    across retries, cache hits, cancellation, lease expiry, and late completion;
    cancel dispatch or expiry alone cannot release unsettled external liability.
29. Named enclosing-loop typed exits, checkpointed typed reconfiguration, and
    durable agentic phases with declared result/payload route influence and
    exact per-call Custody/effect identities.
30. Canonical decision values, keyed-multiset reducers, frozen fanout bindings,
    closed typed errors, scheduler/route separation, and payload-smuggling
    negatives.
31. Native-Parity-inherited and S1-pinned measurable DX corpus: complete
    diagnostic dispositions, source-map fidelity, zero hidden routes, timed
    ten-task author simulation, compile/
    local-test p50/p95, and local/installed normalized lifecycle/admission trace
    equality for identical recorded boundary outcomes.
32. Human suspension timeout/escalation graphs are total and bounded; every
    timeout generation, final disposition, answer/timeout, answer/answer, and
    accepted-but-unconsumed-answer/cancel CAS order retains the accepted winner
    and rejected-late facts.
33. Effective capability-profile closure is derived from descriptor, lowered
    topology, transitive lock, and resolved policy/effect/model/tool/storage
    bindings; under-declaration fails admission, rebind/migration, and stable
    publication.
34. Product control-cap exhaustion remains a declared business result while
    platform token/cost/deadline/lease/infrastructure exhaustion remains a
    lifecycle/control result, under varying consumer-owned values and policies.
35. The five execution modes and six enforcement-severity classes have complete
    versioned dispositions, legal-transition fixtures, and identical behavior
    across Megaplan and the unrelated consumer. No undeclared warning/error
    promotion or consumer-local runner semantics are accepted.
36. Changed-code edit/repeat/fork fixtures use recorded step inputs and eligible
    checkpoints with fresh digest, lineage, attempt, and namespaces; they retain
    separately queryable source, agent/LLM, tool, effect, cost, outcome, and raw/
    normalized trace records for every iteration and support side-by-side diff.
37. Negative mode-boundary fixtures reject silent changed-code resume,
    production effect/authority/idempotency/cache/checkpoint namespace reuse,
    preview/comparison evidence promotion, and conformance credit from explicit
    non-durable preview. Unsupported preview code cannot checkpoint, replay,
    resume, or acquire authority through an opaque fallback.

## Deliberately variable

Standardize where variability is declared and how it is bound, not the values
themselves. Product domain meaning and outcome vocabularies, policy values,
effect/storage implementations, scheduler and transport implementation,
parallel sibling wall-clock ordering, physical persistence layout, UI, and
performance/cost values remain consumer-owned behind declared contracts, while
their binding, identity, admission, recording, and budget enforcement are
platform invariants. Internal compiler APIs remain unstable until deliberately
promoted. Authoring advisories may remain consumer-tailored presentation, but
their severity class and promotion to admission/certification enforcement are
versioned platform contract data rather than runner-local discretion.

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

## Epic promotion

This ticket is promoted into the prepared, six-milestone epic at
`.megaplan/initiatives/native-workflow-platformization/`. Its `NORTHSTAR.md`,
`decisions/PLATFORM_CONTRACT.md`, `chain.yaml`, and six milestone briefs are the launch
source. The platform contract preserves all eleven standardization closure
clauses and all 37 acceptance families from this ticket as stable proof-map
identifiers.

The epic is deliberately **not launched**. This ticket remains open until the
epic completes from accepted, content-addressed evidence. File preparation,
S1's experimental candidate, or Megaplan-only success cannot resolve it. Launch
is separately blocked on the completed Native Parity chain and its exact
Native-to-Platformization handoff manifest.

## References

- `.megaplan/initiatives/megaplan-native-parity-corrective/`
- `.megaplan/initiatives/megaplan-native-parity-corrective/validation/GOLDEN_TRACE_CONTRACT.md`
- `docs/arnold/megaplan-native-parity-corrective-plan.md`
- `docs/arnold/megaplan-native-representation-report.md`
- `.tmp/workflow-standardization-gap/final-report.md`
- `.tmp/workflow-standardization-gap/oracle-answers-summary.md`
- `.tmp/workflow-standardization-gap/oracle-stage2-delta.md`

## Post-M11 release findings to inherit, not reimplement

Shard 016 of the post-M11 exact release inventory found two product-neutral
rules that this platform epic must preserve through its existing S1 admission
and conformance ownership:

- a retired/tombstoned workflow or initiative is rejected before generic
  worktree, compile, authority, custody, or mutation preflight, with one
  canonical typed disposition; and
- every conformance generator has an explicit attempt-local output root,
  writes all primary and side artifacts beneath it, uses one canonical module
  identity, and proves that checkout, wheel, and installed-package validation
  do not mutate their source or consume ambient build tooling.

These are feed-forward acceptance cases, not a reason to launch
Platformization early and not a second implementation of the M11 release
canary. The concrete pipless wheel fixture and honest semantic deployed M11
workflow proof remain immediate obligations of ticket
`01KYSBGRHM1S8R6RQ1DGZ7843Y`. The rejected nonlanded experiment `c88ebe00ac`
is a negative fixture: hashing caller-supplied booleans, kind labels, and
arbitrary JSON does not establish semantic behavior. Platformization should
reuse that failure when defining generic evidence-verifier independence and
test-kit contracts, but it does not own the immediate release correction.
