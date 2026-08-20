# Platformization Epic Decision and Obligation Inventory

Source set reviewed in full/relevant scope:

- `.megaplan/tickets/01KY2DWSJG0B9YKAJRYA0107XE-build-a-reusable-native-workflow-pattern-platform-after-megaplan-parity.md`
- `docs/arnold/megaplan-native-representation-report.md` sections 6, 7, 9.2, 10, and 14
- `.megaplan/initiatives/megaplan-native-parity-corrective/briefs/s7-final-conformance-rollout.md`

This is a promotion checklist, not a replacement contract. The epic must retain
the ticket as an input/reference and make the decisions below explicit in its
North Star, milestone briefs, chain gates, and final proof-map obligations.

## 1. Launch prerequisites and Native Parity handoff

- Do not launch before `megaplan-native-parity-corrective` is accepted with its
  content-addressed completion manifest, `final-proof-map.json`, final
  conformance receipt, and content-addressed Native-to-Platformization handoff
  manifest.
- Consume, do not recreate or weaken, the accepted M11/Native contracts and
  receipts for Run Authority, Custody, WBC, recovery, projections, controlled
  writers/producers, linearizable production CAS, restore incarnation/high-water
  semantics, and installed/cloud execution.
- Require the handoff manifest to bind:
  - reusable candidates and their dependency/coupling map;
  - exact typed input/output/outcome/state/policy/effect contract snapshots;
  - source-to-runtime golden adapters and trace-field contract;
  - the inherited diagnostic/DX corpus, benchmark machine/environment, numeric
    baselines, and measured results;
  - certified production store/service CAS and adapter provenance;
  - governed WBC producer-registry rules and manifest compatibility inputs;
  - generic-primitives-zero-Megaplan-import proof;
  - typed outgoing-seam expiry/inertness proof;
  - exclusions and executed classification rationale for each construct.
- Admit each candidate as exactly one of: core runtime primitive; stable reusable
  pattern candidate; experimental/two-consumer-unproven pattern; or
  Megaplan-specific behavior. Native Parity's classification is evidence for
  Platformization, not automatic stable publication.
- Extend the Native Parity proof/DX corpus. Do not select a friendlier subset,
  independently reset baselines, or introduce test-only lifecycle/admission
  semantics.
- Failed or incomplete handoff evidence blocks launch. Platformization must not
  compensate by rebuilding M11 or inventing Native-local authority stores.

**Promotion-loss risk:** a generic dependency such as "Native Parity complete"
is insufficient. The epic needs a named, content-addressed launch receipt whose
required fields are enumerated above.

## 2. Immutable architectural decisions

### 2.1 Source and generated-artifact authority

- `.pypeline` Python is the sole product control-flow authority.
- Source maps and lowering preserve authored topology. Generated manifests and
  descriptors own immutable admitted runtime coordinates but may not add,
  erase, or reinterpret routes.
- Content-addressed locks select package/component implementations and
  transitive dependencies. Generated artifact or registry evolution is
  versioned, hash-canonical, mixed-worker safe, and explicit for pinned runs.
- Plan Contracts remain consumer-owned input/interface contracts, not runtime
  authority. Logs, receipts, projections, caches, repair requests, comparison
  records, and golden artifacts remain evidence/request surfaces only.

### 2.2 Component contract and lifecycle

- A reusable component is more than an importable callable. Its qualified,
  versioned descriptor declares kind; typed ports and state; closed conditioned
  business outcomes; distinct closed lifecycle/control terminals; hostability;
  dependencies; policies; capabilities; effects/compensation; suspension;
  identity/namespaces; nondeterminism and LLM slots; checkpoint payload limits;
  extension points; and the authoring profile.
- All component kinds use one versioned lifecycle: admission, RA/Custody/WBC
  validation, execution attempt, body, checkpoint, retry, suspension/resume,
  cancellation, compensation, typed return, and one accepted local terminal.
- Business outcomes and lifecycle/control terminals are disjoint tagged unions.
  Product control-cap exhaustion is a declared business result; platform
  token/cost/deadline/lease/infrastructure exhaustion is lifecycle/control.
- Outcome conditions bind canonical payload, condition version, required
  evidence, emission mode, pins, and proposal identity. Condition evaluation and
  local terminal acceptance are atomic and replay consumes the recorded
  evaluation. False yields reserved
  `contract_violation(reason=outcome_condition_failed)`; indeterminate evidence
  quarantines/reconciles or follows a declared lifecycle policy.
- Internal human suspension is a lifecycle transition, not automatically a
  `needs_human` product outcome. Human timeout/escalation is a total bounded
  typed transition graph with declared answer/answer, answer/timeout, and
  accepted-answer/cancel CAS arbitration and durable rejected-late facts.

### 2.3 Root hosting and terminal truth

- Only a root-host adapter may map an eligible local result to a root product
  terminal proposal. Component bodies and nested hosts cannot accept root truth.
- Separate business and lifecycle/control maps are statically total: missing,
  default/catch-all, and undeclared entries fail before authority acquisition.
- Many-to-one mapping may not erase the source result identity/class/evidence,
  terminal-arbitration role, or accepting actor/authority provenance.
- Root proposals still pass current RA/Custody/WBC validation and the inherited
  terminal arbitration CAS. Extraction must not create a second root-terminal
  namespace or make an already accepted Stage 1 terminal eligible again.

### 2.4 Composition, identity, retry, and resources

- Typed bindings explicitly supply product domain types, outcome meaning,
  policies, capabilities, effects, storage, prompts/models/tools, and budgets.
  Shared packages have no Megaplan defaults/imports or ambient mutable authority.
- Component instance, state, checkpoint, artifact, effect, identity, and
  Custody namespaces derive from run identity, parent semantic path, qualified
  component identity, and explicit stable instance/item key. Sharing requires a
  declared shared-resource port.
- Composition statically defines port/outcome binding, context narrowing,
  nesting, retry scope, fanout/fanin, cursor joining, cancellation/deadline/
  budget/capability propagation, compensation, and namespace rules.
- Parent retry consumes the same child's durable result/effect outcome by
  default. Repeating a non-idempotent logical action requires reconciled
  ambiguity, fresh admission, a new semantic occurrence/generation, and a
  declared repeat policy.
- Parent loops durably persist generation/stable child key before admission;
  consume one child terminal by CAS; persist accumulator and next/exit decision;
  and resume at the first incomplete transition.
- `JoinPolicy` is total over the exact child business plus lifecycle/control
  result union and declares qualifying predicates, required success, tolerated/
  fatal results, exact satisfied/impossible parent products, precedence, loser
  cancellation, late-result disposition, and terminalization.
- Child scopes narrow, never widen. Resource ledgers retain reservation,
  committed charge, unresolved liability, release/refund, and settlement proof.
  At every event, committed charges + unresolved liabilities + live worst-case
  reservations stay within the admitted parent budget. Cancel dispatch and
  Custody expiry do not by themselves settle external liability.
- Parent cancellation fences new child action, records/propagates cancellation,
  and accepts only after the policy-required child/Custody/resource disposition.
  Expiry-based acceptance without a child terminal records one typed
  `unresolved_child` fact and reconciliation obligation; later reconciliation
  cannot rewrite the parent terminal.

### 2.5 Required reusable durable primitives

- Named enclosing-loop typed exit.
- Typed checkpointed reconfiguration with new admitted generation/pins.
- Durable agentic-phase boundary with a closed outer result protocol; only the
  declared discriminant and explicitly route-bearing typed payload fields may
  affect the outer route. Every inner effectful call has exact occurrence,
  Custody target/epoch, effect slot/intent/outcome, attempt causality, and charge.
- Dynamic keyed fanout and deterministic keyed-multiset reducers; frozen
  sibling bindings; canonical route data; closed typed phase errors.
- Durable human gates, retry/deadline policy at call sites, effect intent/outcome
  and reconciliation, checkpoint/artifact discipline, LLM Invocation Contract,
  source-mapped diagnostics, and a fast faithful local harness.

### 2.6 Resolution, substitution, and observation

- Qualified identity includes package, component, contract version, and
  implementation digest; the complete content-addressed dependency lock is an
  admission/checkpoint input.
- `new_instance_compatible` and `resume_compatible` are independent claims with
  separate receipts. Suspended instances remain pinned, migrate explicitly, or
  quarantine; "latest code" is never an implicit resume rule.
- The portable event envelope joins component/parent lifecycle, decisions, RA,
  Custody, WBC, checkpoints, effects, resources, and terminals.
- Compatibility uses normalized partial-order equivalence: exact multiplicity;
  per-instance/attempt order; declared happens-before edges; accepted/rejected
  arbitration facts; and only declared unordered siblings.
- The versioned, content-addressed trace-field table classifies every field as
  exact, canonical, relational, or ignorable volatile. Unknown fields fail. Raw
  IDs/multiplicity and source provenance are verified before normalization;
  normalization cannot deduplicate, fold, erase relations, or sort away races.
- Capability/conformance profiles are mechanically derived from the descriptor,
  lowered topology, transitive lock, and resolved policy/effect/model/tool/
  storage bindings. Self-declaration cannot omit required profiles.

### 2.7 Authority and proof trust

- Every authority-increasing action requires exact admitted source/manifest,
  contract, implementation, dependency, policy, prompt/model/tool, state/payload
  and product bindings plus current RA, Custody, and WBC.
- Every arbitration/consumption point joins to a certified linearizable
  conditional mutation in the admitted production store/service. Application
  read/check/write, process-local locks, and fake/in-memory CAS cannot certify it.
- Receipts bind service/store, production adapter, key schema, consistency mode,
  deployment topology, proof-registry incarnation/high-water cursor, exact run,
  commit, lock, and raw export.
- Exact set equality must hold between lowered arbitration sites, the normative
  policy index, forced-race fixtures, and observed runtime sites.
- Producers do not verify themselves. The independent source oracle does not
  call the production lowerer; the independent raw verifier does not import
  production selection/filtering/folding/cardinality/causality/verdict logic.

**Promotion-loss risk:** the root-host rules, outcome-condition atomicity,
resource settlement, raw-before-normalized verification, production CAS
provenance, and compatibility split are easy to collapse into vague words such
as "lifecycle" or "conformance." They must remain explicit gate clauses.

## 3. Five execution modes and six enforcement dispositions

### Modes

1. `authoring_preview`: rapid working-tree trials, fixtures/fakes/debugger.
   Unsupported Python is conspicuously non-durable and earns no resume, replay,
   evidence, admission, compatibility, certification, or publication claim.
2. `durable_sandbox`: fresh experiment/fork with production lifecycle semantics,
   isolated non-production identity, checkpoints/WBC, and fake or explicitly
   sandboxed effects.
3. `comparison`: quarantined shadow/replay evaluation only; no admitted route,
   resume, authority, effect, or terminal.
4. `admitted_production`: exact pins plus current RA/Custody/WBC, certified CAS,
   effect protocol, compatible migration or explicit new run/fork.
5. `certification`: admitted semantics plus clean-install, conformance,
   compatibility, documentation/DX, and unrelated-consumer evidence for stable
   claims.

### Dispositions

1. `always_hard`: production-effect leakage, evidence-as-authority, namespace
   collision, executable impersonation, admitted-history mutation.
2. `automatic`: fresh executable/experiment/attempt identities, namespaces,
   fork lineage, digests, and cache invalidation.
3. `production_admission_gate`: deterministic supported subset, pins, current
   authority/Custody/WBC, effects, migration compatibility, production CAS.
4. `stable_publication_gate`: clean wheels, conformance/compatibility profiles,
   second consumer where required, stable docs/examples/SLOs.
5. `authoring_advisory`: suggested granularity, complexity, naming, candidate
   reuse class, pre-SLO performance, documentation completeness.
6. `non_durable_only`: unsupported/nondeterministic exploration that cannot
   checkpoint, replay, resume, certify, publish, or enter admitted evidence.

### Mode contract

- Mode is part of execution identity/evidence. Every rule has exactly one
  versioned disposition per applicable mode; no runner-local warning/error
  promotion or implicit mode inference is allowed.
- Edited code is immediately runnable with a fresh digest, lineage, attempt,
  namespace, cache disposition, and safe effect bindings. No migration
  declaration is needed merely to experiment.
- "Continue from here with changed code" means explicit fork/new run or admitted
  migration, never disguised resume.
- Experimental authority, checkpoints, artifacts, caches, projections,
  idempotency keys, effects, and histories are namespace-disjoint from
  production. Experimental output cannot be relabeled as admitted or stable.
- Moving modes never downgrades `always_hard`; promotion creates/consumes an
  admitted record instead of mutating experimental history.

**Promotion-loss risk:** this recently added contract is spread across North
Star, S1/S2/S3/S4/S5, closure clause 11, acceptance cases 35-37, and Native
Parity NP-DX fixtures. Preserve all five modes, all six dispositions, and their
cross-mode negative fixtures—not just the local repeat-step feature.

## 4. Five-sprint ownership

### S1 — Candidate standard and executable contract corpus

Owns and pins, as **candidate/experimental** rather than stable:

- extraction/dependency classification and package-direction freeze;
- Component Descriptor v1, durable-Python authoring profile, five-mode/six-
  disposition standard, lifecycle, source/generated ownership, manifest/
  producer evolution, root hosting, outcome conditions, human timeout graph,
  composition algebra, retry/generation, loop ledger, joins, cancellation/
  Custody/resources, durable primitives, serialization/payload/LLM/bindings,
  identity/resolution/evolution/trace/substitution contracts;
- reference executable transition models and invalid descriptor/composition/
  mode corpora;
- inherited DX corpus, benchmark environment, comparable baselines, stable
  diagnostic codes/source spans/recipes, route-smuggling mutations, repeatability,
  timed author simulation, and compile/local p50/p95 thresholds.

S1 is blocked by prose-only contracts, weaker reset baselines, fake production
CAS, implicit mode promotion, or any missing negative disposition.

### S2 — Product-neutral implementation and enforcement

Owns:

- experimental package/export/discovery surface;
- static component/composition/profile validation before authority;
- durable-Python compiler enforcement and source maps;
- one product-neutral local test kit using production compiler/lifecycle/
  validators/events with in-memory adapters/virtual time—not alternate semantics;
- repeat/fork/log comparison, non-durable preview, and safe default effects;
- common component lifecycle, root adapter, outcome atomicity, human graph/races,
  named exits, reconfiguration, agentic boundary, parent ledger, joins/resources,
  cancellation/Custody, generated RA/Custody/WBC identities;
- content-addressed resolution/admission receipts, manifest/registry evolution,
  effects, trace comparator, clean-wheel parity, and real production CAS
  contention with independent clients.

S2 gate includes exhaustive lifecycle/recomposition/race/fault/mode tests,
raw-before-normalized mutations, resource invariants, paired changed-code
experiment vs silent-resume fixtures, and local/installed trace equivalence.

### S3 — First extraction under isolation and recomposition

Owns:

- first-wave evaluator panel, bounded refinement loop, human gate, and effect-
  safe action; product-neutral bindings and no Megaplan defaults/globals;
- two concurrent differently bound instances and at least two supported shapes
  per pattern;
- all/any/quorum, loop ledger/named exit, timeout/human races, cancellation/
  unresolved child, same-child/non-idempotent effect/resource settlement,
  reconfiguration, and small durable-agentic fixture proofs;
- Megaplan consumption of shared implementations with unchanged normalized
  golden traces plus generic conformance;
- low-latency local tests, installed equivalence, and edit/repeat/fork/log
  association for each first-wave pattern.

### S4 — Unrelated adversarial consumer and substitution

Owns:

- a real non-Megaplan workflow importing multiple patterns with different domain
  types, outcomes, policies, effects, storage, root maps, joins, timeout/resource
  policies, and composition shapes;
- recorded revisions/narrowing of the candidate abstraction—S1 is challenged,
  not accommodated or presumed stable;
- independent implementation swap with separate new-instance and resume-
  compatibility receipts; migration, quarantine, pinned-old support, and the
  complete ordinary code/prompt/model/tool/policy/schema/dependency evolution
  matrix;
- product-neutral explanation, no Megaplan imports/copies, effective-profile
  derivation mutations, and the same mode/severity behavior with isolated logs.

### S5 — Stable certification, evolution, and adoption

Owns:

- incorporating S4 findings, then—and only then—freezing/promoting stable
  descriptor/profile/package versions;
- public APIs, registry states, docs/examples, compatibility/change classes,
  deprecation/migration/retention/GC, authoring/readability/edit-locality, local
  kit and SLOs;
- final five-mode/six-disposition publication contract and legal transitions;
- conformance profiles/manifest with mechanically derived capability closure;
  exact trace table, production CAS/adapter provenance, registry incarnation/
  high-water, manifest schema/hash, root accepting provenance, LLM/effect/
  checkpoint/resource/DX receipts;
- reusable-pattern registry and content-addressed platform completion manifest.

**Promotion-loss risk:** preserve this exact order. In particular, S1's pinned
version is reproducibility scope, not a stable compatibility promise; S4 may
revise it, and only S5 can confer `stable` status. Do not add a sixth sprint for
handoff work and do not launch S1 before Native Parity acceptance.

## 5. Cross-cutting proof and acceptance obligations

The epic's final proof map must cover, with positive, negative, mutation,
crash, race, install, and cross-consumer variants as applicable:

1. Descriptor/static invalidity before authority; hidden imports/globals and
   undeclared state/effects/routes rejected.
2. Decompose/reinsert and shape recomposition across root, nested, sequential,
   loop, fanout/fanin, suspension, cancellation, retry.
3. Duplicate/concurrent instance isolation and namespace collision negatives.
4. Lifecycle crashes at admission/body/checkpoint/effect/suspend/resume/
   compensation/condition/local/root terminal boundaries.
5. Stale/missing RA/Custody/WBC, pins, locks, schemas, workers, and artifact
   rejection before body/effect intent; evidence/projections never authorize.
6. Checkout/clean-wheel/cloud identical locked graph, topology, lifecycle and
   admitted behavior; source-to-versioned-manifest-to-lock-to-registry-to-
   admission-receipt provenance.
7. State/checkpoint/prompt/model/tool/policy/dependency/effect/manifest/registry
   evolution: pinned-old, compatible resume, explicit migration/new run, or
   quarantine; retention prevents premature GC.
8. New-instance versus resume substitution with distinct receipts and one
   provenance-bearing migration.
9. Root-host exclusivity/totality; retained result class, arbitration role, and
   accepting actor; outcome-condition atomicity/false/indeterminate paths.
10. Parent retry/generation and crash-safe loop ledger at every edge, including
    non-idempotent effect ambiguity/reconciliation.
11. Human timeout graph and all answer/timeout/cancel race orders with one winner
    and rejected-late facts.
12. Total all/any/quorum/reducer policies, satisfaction/impossibility, loser
    cancellation, late results, and cancel/deadline/budget race orders.
13. Parent cancellation/Custody release-transfer-expiry, stale epochs,
    `unresolved_child`, late reconciliation, and no fictional settlement.
14. Eventwise budget/resource ledger across retry, cache hit, cancellation,
    expiry, late completion, refund, and unresolved liability.
15. Effects and LLM/model/tool calls: exact intent/outcome/attempt/pins/budget/
    cache/replay/fallback/reconciliation; no repeat of accepted results.
16. Checkpoint payload inline/reference bounds, digests/schema/retention/
    redaction/recovery and invalid-reference negatives.
17. Named loop exits, typed reconfiguration, agentic boundaries, canonical
    decision values, keyed reducers, frozen fanout, closed errors, scheduler/
    route separation, route-inert payload mutation.
18. Raw event conservation, independent verifier, partial-order comparator,
    unknown-field failure, multiplicity/causality/arbitration mutation resistance.
19. Exact arbitration-site/policy/forced-race/runtime equality and real-store
    independent-client linearizability/provenance; no fake CAS certification.
20. Effective capability-profile closure from actual transitive topology and
    bindings; under-declaration rejected on admission/rebind/migration/publish.
21. Cross-consumer product-neutral causal explanation and binding variability;
    no copied implementation or Megaplan import.
22. Registry governance through experimental/stable/deprecated/withdrawn states
    and content-addressed conformance manifests.
23. Diagnostics/source maps/user tracebacks, complete rejection dispositions,
    zero hidden routes/payload smuggling, author task timings, compile/local
    p50/p95, repeatability, and local/installed trace equality.
24. All five modes and six severities across both consumers: repeat/fork allowed
    with fresh identity; silent changed-code resume, namespace/effect/key reuse,
    experimental evidence promotion, implicit mode, and advisory-to-admission
    escalation rejected.

Proof trust requirements apply to every row: owning sprint/gate; exact receipt;
authoritative producer; independent verifier; negative mutation; exact run,
commit, lock, artifact, schema, and status derived from execution. Hand-authored
green labels, hashes without semantic consumption, stitched traces, projections,
or producer self-certification do not close a row.

## 6. Deliberately variable and non-goals

### Deliberately variable behind declared bindings/contracts

- Product types, domain meaning, business outcome vocabularies and policies.
- Prompt content, model choice, tools, policy/budget values, effect and storage
  implementations.
- Scheduler/transport/physical persistence and legal sibling wall-clock order.
- UI and performance/cost absent a published SLO.
- Authoring-advisory presentation; its severity/promotion semantics remain a
  versioned platform contract.
- Internal compiler APIs until deliberately promoted.

### Non-goals

- Generalizing every Megaplan function or forcing unrelated products into
  Megaplan-shaped outcomes.
- Rebuilding RA, Custody, WBC, recovery, projections, or their stores/facades.
- A workflow marketplace.
- Prematurely freezing compiler internals.
- Inventing stable abstractions without a genuinely different second consumer.
- Arbitrary Python; the platform provides a clear versioned durable subset and
  an explicitly non-durable exploration path.
- Standardizing product prompt/model/policy/budget values rather than their
  declaration, identity, replay, evolution, and enforcement.
- Open-ended item streams or opaque polling loops; diagnostics point to future
  typed event-queue ports.
- Extracting reusable patterns during the Native Parity S7 handoff.

**Promotion-loss risk:** “platform” must not be interpreted as marketplace,
generic domain model, a rebuild of M11, or immediate stable generalization of
all candidates.

## 7. Stable completion criteria

The epic is complete only when all of the following are simultaneously true:

- The descriptor, lifecycle, composition, isolation, authority/evidence,
  resolution, evolution, observation, conformance, variability, and execution-
  mode closure clauses are implemented and proof-mapped—not merely specified.
- Shared packages have zero Megaplan imports; Megaplan and the unrelated
  consumer use the same implementations from clean wheels without copying.
- A consumer can compose documented public components using its own types,
  policies, effects, storage, prompts/models/tools, and outcomes; a new domain
  result changes the shared package only when the generic protocol changes.
- The same component preserves its contract root/nested/sequential/loop/fanout,
  through suspension/retry/cancel/resume, with statically total hosting/join
  behavior and isolated durable identity.
- Source topology remains sole product authority; manifests/registries/handlers/
  adapters/projections/CLI/auto cannot add or erase routes.
- Current RA/Custody/WBC and certified production CAS govern every authority-
  increasing boundary; evidence never grants or routes.
- Durable replay/resume does not repeat accepted external, LLM, or human work;
  changed code experiments remain easy, isolated, and explicitly non-production.
- Checkout, wheel, and cloud resolve the same content-addressed graph and
  observable partial-order history; source maps and diagnostics identify user
  code.
- New-instance substitution and suspended-run resume compatibility are
  separately proven, with pin/migrate/new-run/quarantine behavior explicit.
- The unrelated consumer adversarially changes composition shape and bindings,
  swaps one implementation, performs one compatible upgrade, and passes the
  same black-box conformance suite without knowing Megaplan.
- All mechanically applicable capability profiles pass, including production
  CAS, effects, LLMs, checkpoints, joins/resources, trace conservation, and DX;
  irrelevant profiles may be omitted only because the derived closure excludes
  them.
- The cumulative Native Parity + Platformization acceptance corpus and numeric
  benchmark history are published with comparable environment metadata; no red,
  missing, fake-only, self-certified, or unconsumed proof row is hidden.
- Only after S4 challenge and S5 certification are descriptor/profile/package
  artifacts promoted from experimental to stable; registry states,
  deprecation/withdrawal, retained-artifact promises, and conformance manifests
  are operational.
- The reusable-pattern registry and content-addressed Platformization completion
  manifest are accepted. Unproven product abstractions and compiler internals
  remain explicitly experimental.

The decisive end-state proof is the unrelated non-Megaplan workflow: it imports
shared patterns, supplies different domain semantics, uses unfamiliar supported
shapes, swaps one compatible implementation, exercises upgrade and suspended-
run evolution, and passes the same externally verified conformance contract.

## 8. Epic-promotion checklist: decisions most likely to be lost

The epic conversion must explicitly retain these items; a reference back to the
ticket is useful but not sufficient:

1. Launch consumes the exact content-addressed S7 handoff—not merely a completed
   predecessor status.
2. Five sprints only, with S1 experimental pin -> S4 adversarial revision -> S5
   stable promotion. A pin is not a stability claim.
3. Five execution modes, six dispositions, no implicit mode or severity change,
   and the changed-code repeat/fork versus silent-resume boundary.
4. Business outcomes versus lifecycle/control terminals; atomic outcome-
   condition acceptance; reserved contract-violation behavior.
5. Root-host exclusivity, total maps, inherited Stage 1 terminal identity and
   accepting actor/arbitration provenance.
6. Same-child retry versus new generation and non-idempotent effect reuse.
7. Total JoinPolicy plus exact impossibility result and declared race policy.
8. Resource-specific settlement; cancellation and Custody expiry never
   automatically free external liability; `unresolved_child` is retained.
9. Named loop exits, typed reconfigure, and durable-agentic outer/inner boundary.
10. `new_instance_compatible` is not `resume_compatible`.
11. Raw-event conservation and independently implemented verification before
    normalized partial-order comparison.
12. Production-store/service linearizable CAS with real adapter/provenance and
    two-client contention—not fake/in-process CAS.
13. Mechanically derived capability-profile closure, not descriptor self-report.
14. Manifest and WBC producer-registry evolution/mixed-worker rules.
15. Inherited Native Parity DX corpus and numeric baselines; measurable authoring
    ergonomics are safety gates, while advisories do not become hidden blockers.
16. Product variability remains through typed bindings; no Megaplan defaults or
    premature generalization.
17. All proof-map rows bind exact execution and independent evidence; no
    hand-authored status, hash-only proof, stitched trace, or self-verification.
18. Open streams, marketplace, M11 rebuilds, arbitrary Python, and universal
    Megaplan generalization remain out of scope.
