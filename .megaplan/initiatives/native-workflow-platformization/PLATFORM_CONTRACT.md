# Native Workflow Platformization Contract

## Status and authority

- **Status:** prepared, not launched.
- **Epic:** `native-workflow-platformization`.
- **Upstream:** `megaplan-native-parity-corrective` must complete and publish the
  exact handoff defined in §1 before this epic may start.
- **Scope:** the reusable component, composition, package, evolution, developer
  experience, and conformance layer built from proven Native Parity boundaries.
- **Normative role:** this file is the immutable cross-milestone contract for
  S1, S2A, S2B, S3, S4, S5, and S6.
  Milestone briefs may add implementation detail, but may not silently weaken,
  reinterpret, or omit it. Any deliberate change requires a versioned contract
  amendment, affected acceptance-family updates, and an explicit disposition for
  active artifacts and runs.
- **Publication state:** S1 pins a candidate/experimental contract for
  reproducibility; S5 may challenge and revise it; only S6 may confer `stable`
  registry status.

The end state is a workflow-component platform, not merely a collection of
importable Python helpers. An unrelated package can install, resolve, validate,
bind, compose, run, explain, upgrade, and—where separately proven—substitute a
step or subworkflow without importing Megaplan, copying its implementation, or
changing the component's declared semantics because of host, parent, shape,
policy binding, package version, suspension, retry, or cancellation.

This contract preserves the central authority split:

```text
.pype Python                             product control-flow authority
generated manifest + component lock     admitted coordinates and resolution
Run Authority                           permission and accepted decisions
Custody                                 current exact-target ownership
WBC                                     durable boundary/effect history
checkpoints                             semantic reentry and durable local state
logs/projections/conformance artifacts  explanation and evidence only
```

No lower layer may become a second product route table.

## 1. Launch admission and Native Parity handoff

### 1.1 Hard launch precondition

The chain must not launch merely because the predecessor chain reports a
completed status. Launch requires content-addressed, validator-consumed evidence
from the accepted `megaplan-native-parity-corrective` revision:

1. the accepted milestone-gate bootstrap completion manifest and its exact
   `downstream-spec-readiness.json`, `completion-crosswalk-readiness.json`, and
   `editable-runtime-readiness.json` proof-artifact rows;
2. Native Parity's completion manifest and `final-proof-map.json`;
3. its accepted final-conformance receipt, bound to the proof-map hash;
4. its content-addressed Native-to-Platformization handoff manifest;
5. the exact accepted commit/tree, installed artifact and dependency lock; and
6. the accepted M11/Native proof-registry incarnation, restore generation, and
   raw-history high-water coordinates on which the receipts depend.

Missing, stale, mismatched, self-declared, unconsumed, or red evidence blocks
launch. Platformization may not compensate by creating a local authority store,
facade, alternate validator, or friendlier proof baseline.

### 1.2 Required handoff payload

The handoff manifest must bind, rather than merely point at:

- the reusable-candidate inventory and dependency/coupling map;
- one executed classification for every candidate: `core_runtime_primitive`,
  `stable_pattern_candidate`, `experimental_two_consumer_unproven`, or
  `megaplan_specific`;
- exact snapshots of typed input, output, business-outcome, lifecycle/control,
  state, policy, effect, hostability, and suspension contracts;
- source-to-runtime golden adapters, the raw event schema, and the versioned
  trace-field classification;
- the exact adopted `.pype` contract, compiler/diagnostic/converter/minimal-
  preview versions, `GO-FORMAT` receipt, source/package correspondence,
  identity/migration matrix, and exact-pinned legacy-retention receipts;
- the full Native Parity diagnostic/DX corpus, named benchmark environment,
  numeric baselines, and measured results;
- certified production store/service conditional-write adapters and their
  service, key-schema, consistency, topology, and executable provenance;
- governed WBC producer/query registry rules, manifest schema/hash compatibility
  inputs, and proof-registry incarnation/high-water semantics;
- proof that generic primitives have zero Megaplan imports;
- every temporary outgoing seam's expiry/inertness proof; and
- exclusions and the executed rationale for what must not be extracted.
- exact `completion-kernel-c1-manifest.json`,
  `completion-kernel-c2-manifest.json`, S2R
  `completion-kernel-enablement-receipt.json`, and final
  `completion-divergence-ledger.json` path/hash;
- completion spec/binding/verdict/acceptance-reference schema, serialization,
  internal reader-writer and authoritative decoder matrix; candidate-outcome
  registry; proof-mode/evidence-scope/aggregation-signature contracts; adapter
  and legacy-writer inventory; restore/projection-invariance and false-done/
  `REVIEW` corpus; and
- the durable-subject predicate/static lint; `(spec_hash, obligation_id)` and
  semantic-ID stability rules; candidate-first disposition evaluation with
  blocked/waived proof and quarantine terminal-policy rules; normative
  evidence-window tuple; presence/complete-capture-absence verifiers;
  producer/trust-class independence; S2R concrete total child-disposition,
  multiplicity/no-double-counting and waiver-taint instances; human/rework
  templates; reopen-as-new-admission proof; neutral-package import lint; stable
  finding/occurrence divergence proof; store-incarnation invalidation; and the
  exact projection deletion/rebuild/forgery fixture; and
- Custody's exact `bounded-incident-projection-handoff.json`, including
  full-rebuild parity and the 57,000-event latency/peak-memory receipt.

The handoff manifest is a mandatory proof artifact in Native Parity's
`final-proof-map.json` and therefore is itself path-and-content-hashed by the
validated Native Parity `completion-manifest.json`. Platformization launch
requires `chain_completed + require_manifest` plus explicit artifact
preconditions. S1's intake gate must then find each exact path once in the
validated completion manifest and match the current artifact hash to the
manifest hash. The artifact preconditions alone, including file-exists or
`contains_text`, cannot satisfy this semantic handoff requirement.

Native Parity's classification is evidence, not stable publication. S1 must
consume and verify it; S4 may extract only selected candidates; S5 must try to
break the abstraction with a genuinely unrelated consumer.

### 1.3 Relationship to existing platform work

This epic does not rebuild work owned by M11 or the completed
`native-platform-followup` initiative. It consumes compatible accepted outputs
for RA, Custody, WBC, recovery, projections, controlled writers/producers,
linearizable persistence, DB-backed durability, credential brokerage, worker
supervision, pack/lock infrastructure, and installed/cloud execution. Those
outputs satisfy this epic only when the applicable acceptance row joins them to
the exact component, composition, lock, run, and raw history under test.

This epic owns the missing reusable workflow-component standard, product-neutral
workflow-topology and resource composition algebra, extracted pattern packages,
unrelated-consumer challenge, behavioral compatibility claims, authoring modes,
and cumulative conformance. It does not own a new completion aggregation
algebra: C2's signatures and S2R's concrete primitive instances remain
canonical.
It must not fork the underlying stores, validators, leases, event truth, fleet,
security broker, or projection model.

It also owns neutral extraction and productization of the exact Native
completion implementation. It does not define a replacement spec/binding/
verdict model, create another acceptance transaction, re-enable the kernel, or
implement a second incident projector. Native S2R GO-0 remains the sole
authoritative kernel enablement. Custody remains the bounded-projection
implementation and benchmark owner.

S2A must promote the exact accepted Native/Native-Parity runtime and adapters in
place: remove product coupling, generalize only through the frozen interfaces,
and retain their accepted identities, histories, compatibility readers, and
proof lineage. It may not fork, wrap-and-shadow, or rebuild a parallel runtime
and then call that implementation product-neutral. If promotion in place is
blocked, S2A stops and repairs the canonical owner.

## 2. Source, lowering, and generated-artifact authority

### PWC-SRC-01 — Sole semantic source

Canonical `.pype` Python is the sole product control-flow authority. Loops,
branches, retries, joins, human gates, reconfiguration, suspension, effects, and
terminal proposals must be visible as supported source constructs or declared
call-site policies. Helpers, handlers, metadata, schedulers, manifests,
registries, CLI/auto surfaces, exception strings, payload flags, and projections
cannot add, erase, or reinterpret routes.

### PWC-SRC-02 — Deterministic durable subset

The durable authoring profile is a versioned deterministic subset. It requires
canonical schema-qualified decision inputs, stable dynamic keys, canonical
iteration, frozen digest-bound fanout bindings, keyed-multiset reducers, and
closed typed phase errors. Ambient time, entropy, environment, filesystem or
network I/O, process/global mutation, reflection/dynamic import/eval, unmanaged
concurrency, host-dependent paths, arbitrary float behavior, completion-order
reducers, mutable sibling context, and open exception routing are rejected or
admitted only through declared providers/boundaries.

Every route-bearing decision uses a named, statically finite enum or closed
tagged union declared separately from its payload. The compiler binds each
variant to visible source edges. Whole payloads, open strings/maps, exception
text, helper-returned invocation targets, and callable/route-table values are
not discriminants. A helper may compute a declared discriminant from payload
data; the workflow must branch visibly on that value.

### PWC-SRC-03 — Generated artifacts preserve, never author

The compiler and source map preserve authored topology. A generated
`WorkflowManifest` owns immutable admitted runtime coordinates; it cannot invent
product semantics. Manifest schema, decoder, canonical serialization, hash,
producer entry, and mixed-worker compatibility are versioned and pinned.
Backwards decoding or coordinate migration requires a declared conservation
mapping; unsupported combinations quarantine or reject before body/effect
intent. Re-serializing old coordinates under a new meaning is forbidden.

### PWC-SRC-04 — Locks and product contracts

The component/dependency lock selects exact package, component contract,
implementation, transitive dependency, artifact, and conformance versions and
is part of admission and checkpoint identity. Consumer Plan Contracts and
equivalents remain typed product interfaces whose semantic digest may affect
evidence obligations; they never grant permission, Custody, WBC completion,
effect truth, or terminal acceptance.

### PWC-FMT-01 — One file, one canonical workflow

`docs/arnold/pype-authoring-contract.md` is incorporated by reference. Every
durable root or child workflow lives in one `.pype`, and every `.pype` contains
exactly one top-level `@workflow`. A second workflow or no workflow rejects.
The exactly-one rule is canonical; there is no `main`, `__all__`, multi-export
module, library-only `.pype`, declaration-order entrypoint, or file-local root
selector.

A `.pype` may contain private file-local steps and deterministic helpers. They
cannot be imported or independently addressed, and their transitive behavior
digests fold into the containing workflow. Shared steps, effects, schemas,
policies, prompts, types, and helpers live in `.py`.

### PWC-FMT-02 — Workflow, step, effect, and helper boundaries

`workflow` is the only authored topology kind. A workflow becomes a
subworkflow when hosted by a parent; legacy/generated `subflow` references are
decoding/lowering artifacts only.

A step is a leaf. It may invoke deterministic helpers and declared effect
adapters but cannot invoke a workflow or decorated step. Workflows and helpers
cannot invoke effect adapters directly. Helpers return data for visible
workflow decisions; they cannot return dynamic invocation targets, hide
topology/policy, suspend state, create durable children, or perform undeclared
effects.

Shared `.py` step implementations may use ordinary Python and third-party
imports; the `.pype` restricted grammar does not apply inside the leaf
implementation. The resolved graph lock or an explicit binding pins every
selected distribution/version/artifact, optional feature, Python/runtime
environment and plugin selection that can affect a durable result. Import-time
effects or mutable Arnold registration, ambient dependency choice, and
imported workflow/decorated-step invocation reject; third-party internal import
mechanisms are acceptable only under those pins and cannot bypass declared
effects.

An `@workflow` in ordinary `.py` is preview-only. It may run with fresh
ephemeral identity and fake/ephemeral-only effects with no durable effect
history, but cannot produce a durable checkpoint, replay/resume, comparison,
admission, publication, or certification claim. Every durable mode rejects it
before authority or effect intent.

### PWC-LINK-01 — Static canonical-workflow linking

Relative, absolute, and installed-package workflow imports resolve only the one
canonical workflow of each `.pype`; typed `.py` imports resolve declared
steps/effects/schemas/policies/helpers. Discovery parses syntax/descriptors and
never executes author source. Aliases preserve original provenance.

Dynamic/conditional/star imports, registration/re-export laundering, import
cycles, recursive workflow calls, duplicate logical identities, and
incompatible versions reject before lowering, authority, or effect intent.
Explicit bounded loops lower to finite loop IR and are not call recursion.

The canonical Arnold package descriptor owns the optional default pipeline,
the governed distribution namespace and fork/delegation lineage, the
cross-package allowlist of canonical workflows, exact locks, source/descriptor
correspondence, and append-only identity migration log.
“Allowlist” here is package visibility, not a source-file export table. The
implementation must extend existing canonical pack/lock metadata rather than
create a parallel descriptor without an inventory-backed decision.

`default_pipeline` selects a workflow only; it never selects or implies a root
adapter. The invoking admission binding owns root-adapter selection by default.
A producer may publish named adapters and nominate one named producer default,
but an invocation must explicitly accept and pin that adapter or select another
eligible total adapter.

### PWC-ID-01 — Logical identity, drift, and retention

Workflow identity is `(distribution_name, logical_workflow_name)`, where the
logical name is explicit workflow ID or decorated function name and is unique
within the distribution. Distribution names are registry-governed publisher
namespaces with append-only delegation/fork lineage. A fork takes a new
distribution name unless an accepted delegation authorizes continued use.
Conflicting namespace authorities for the same logical key are a hard
collision and report both provenance chains. Multiple executable digests under
the same authorized logical key are ordinary version evolution, not a
collision; admission and resume still pin one exact version and compatibility
disposition.

Physical and wheel paths are provenance. Executable identity uses the pinned,
versioned, conservative executable-closure canonicalization in
`docs/arnold/pype-authoring-contract.md`; no implementation-defined
“behavior-relevant” classifier is permitted. The closed exclusion list,
canonical IR/serialization, hash algorithm, and algorithm version are part of
the contract. Algorithm changes are explicit identity-version events and
cannot reinterpret old pins.

Component executable digests cover the component's own canonical closure and
direct dependency contract requirements; they do not recursively absorb the
selected concrete executable digests of all descendants. The separately
canonicalized transitive graph lock pins every selected logical/version/
executable identity and edge and has its own digest. Admission, actions,
effects, checkpoints, replay/resume, source maps, and proof bind both digests.
A compatible dependency substitution changes the graph-lock digest even when
the caller component digest remains stable.

Physical relocation with unchanged logical/digest identity is provenance-only.
Rename, signature/outcome/hostability change, extract/inline, private/shared
step promotion, or canonical executable-closure change requires an explicit
scoped migration record, new attempt, or quarantine. A blanket alias is
forbidden.

Pinned `.pypeline`, authored `subflow`, and durable `.py` workflow artifacts
remain exact-read-only resolvable while a nonterminal occurrence depends on
them. They cannot author/admit new work and are retired when no live pin remains.

## 3. Component descriptor and lifecycle

### PWC-DESC-01 — Descriptor v1 minimum

Every shared `.py` step and every canonical `.pype` workflow—including a
workflow hosted as a child—has one qualified, versioned descriptor declaring.
Private file-local steps have no independent descriptor; their contract and
digest are folded into the containing workflow:

- kind, governed distribution/package/component identity and lineage, contract
  version, executable-closure digest plus algorithm ID/version, hostability and
  extension points;
- canonical typed input/output/state schemas and checkpoint payload class/limits;
- conditioned closed business outcomes and applicable closed lifecycle/control
  terminals;
- finite named route discriminants, kept distinct from payload schemas, and
  their source-bound edge mapping;
- dependencies, capabilities, canonical `PolicyEnvelope` values/requirements,
  effects, compensations, storage, suspension/reentry and human-timeout graph;
- semantic instance and namespace rules;
- declared nondeterminism, LLM/model/tool slots, budgets, cache and replay rules;
- resource, deadline, cancellation and compensation context;
- authoring-profile and trace-field-contract versions; and
- required compatibility and mechanically derived conformance profiles.

An importable callable without this contract is not a stable component.

### PWC-LIFE-01 — One lifecycle for every kind

All component kinds execute through one versioned lifecycle:

```text
static validation and resolution
  -> admission and RA/Custody/WBC validation
  -> execution-attempt start
  -> body / checkpoint / declared effect
  -> retry OR suspend/resume OR cancel/compensate
  -> typed local result proposal
  -> canonical landed completion candidate-outcome evaluation
  -> one accepted local terminal through the existing acceptance transaction
  -> parent consumption or root-host proposal
```

This is the exact Native-landed kernel/evaluator and acceptance transaction,
not a Platformization-local outcome-condition evaluator.

Execution attempts, retry generations, aggregate component terminals, parent
consumption, and root product terminals are distinct identities and
cardinalities. Every attempt has one immutable attempt terminal; the retry
policy yields one immutable aggregate component terminal; the parent consumes
that terminal once by certified conditional mutation.

### PWC-LIFE-02 — Business versus lifecycle/control results

Business outcomes and lifecycle/control terminals are disjoint tagged unions.
Product loop/candidate caps may emit a declared business outcome when that
meaning is part of the component contract. Token, cost, deadline, lease,
infrastructure-retry, compensation, cancellation, and contract failure remain
lifecycle/control results. An accepted control terminal is not business success
unless a total typed parent policy explicitly classifies it as such.

Internal suspension is a lifecycle transition, not automatically a
`needs_human` business outcome. A component may deliberately export such a
business outcome only by declaring its distinct condition, evidence, and
emission semantics.

### PWC-LIFE-03 — Outcome-condition atomicity

Each business outcome declares canonical payload and maps its semantic
postcondition, durable evidence, effect/compensation completeness, emission
mode, and condition version into the subject's canonical `CompletionSpec`.
A proposal freezes those fields plus its executable and policy pins and becomes
a candidate outcome. The exact Native completion evaluator evaluates that
candidate before selecting its applicable obligations and records the verdict
through the one existing acceptance transaction. The lifecycle layer does not
implement a second condition/evidence evaluator.

- True accepts the proposed business outcome.
- False accepts only
  `contract_violation(reason=outcome_condition_failed,
  attempted_outcome=...)`.
- Missing, stale, ambiguous, or unavailable required evidence quarantines or
  reconciles until determinable, or follows an explicitly declared lifecycle
  policy. Quarantine is nonterminal unless that admitted policy explicitly
  permits it as a terminal candidate and supplies its typed obligations.

Replay consumes the recorded evaluation. Parents and root hosts never recompute
it or substitute a different business result.

## 3A. Completion semantics and registry boundary

### PWC-COMPLETE-01 — Exact Native kernel, no fork

Platformization consumes the exact Native
`CompletionSpec -> CompletionBinding -> CompletionVerdict -> existing
acceptance transaction` implementation and proof lineage.

- S1 inventories the schemas, registries, adapters, proof corpus, bridges,
  current divergence-ledger hash, legacy-writer retirement and product
  coupling without redesigning or stabilizing them.
- S2A extracts admission, immutable binding, evaluation, evidence scope,
  proof modes, waiver taint, lifecycle composition and inspection in place. It
  retains one acceptance transaction and cannot perform another live
  enablement.
- S2B derives mechanical completion templates from canonical `.pype`
  authored/component/graph identity, durable-boundary call-site templates and
  package locks. Authors declare only domain obligations.
- S3 owns generic lint, diagnostics, inspection, test-kit ergonomics,
  generated canonical-machine views and disposable Markdown/human views.
  Deletion, rebuild or forgery cannot affect authority.
- S4 proves Megaplan consumes the extracted implementation through one
  receipt-bound migration with no reverse dependency, semantic drift or
  duplicate completion writer.
- S5 proves different domain obligations, nontrivial composition, a human or
  effect boundary, and rework or analogous newly admitted work in an
  independently originated unrelated consumer.
- S6 publishes only the surface proved by both consumers.

The Native internal persisted-wire and authoritative decoder compatibility
promise begins at S2R GO-0 and is inherited unchanged. The schemas and persisted
binding envelope are nevertheless internally versioned from C1/M1, before live
authority, so old and future records are never unversioned ambiguity. Platform
S6 governs stable public authoring/API publication; it does not retroactively
create or reinterpret storage compatibility.

### PWC-COMPLETE-02 — Two typed registries, one total mapping

Completion candidate outcomes and platform enforcement dispositions are
different semantic axes:

- the completion registry names candidates such as accepted, blocked,
  suspended, failed, waived, cancelled-pending-reconciliation and quarantined;
- the enforcement registry names mode/claim dispositions such as
  `always_hard`, `production_admission_gate` and `non_durable_only`.

Each axis has one canonical versioned typed registry. Their interaction is one
generated total mapping bound to both versions; unknown pairs reject before
admission. They may not be collapsed into one enum, aliased through shared
numeric values, or extended by a consumer-local table. Every product, platform,
CLI, editor and documentation registry is a strict generated projection whose
set equality, version binding and unknown-entry rejection are tested.

### PWC-COMPLETE-04 — Inherited executable kernel contract

Platformization treats the Native kernel proof map as an executable dependency,
not background prose. S1 through S6 cumulatively consume and revalidate:

- the mechanically checkable durable-subject predicate and static lint; pure
  helpers carry no contract and cannot hide any durable behavior;
- stable semantic obligation IDs and executable
  `(spec_hash, obligation_id)` identity;
- candidate-first evaluation, typed proof for blocked and waived outcomes, and
  nonterminal quarantine absent an admitted terminal policy;
- immutable admission binding and the normative evidence window covering
  subject, attempt, generation, source/runtime/dependency digests, store
  incarnation, cursor bounds, Custody epoch/fence/WBC version, and frozen child
  set;
- separate presence and complete-capture absence verification, set equality,
  producer/trust-class verifier independence, waiver scope/expiry/taint, and
  S2R's total child-disposition, multiplicity and no-double-counting instances;
- source-stable human and rework identity templates, or their explicitly gated
  deferred-template mechanism, and reopen as a new admission referencing the
  prior subject without mutation or rebinding;
- restore invalidation on store-incarnation change, stable finding/occurrence
  divergence identity, the reproduced false-pass golden exemplar, and complete
  deletion/rebuild/forgery invariance for all status and Markdown projections;
  and
- neutral completion types with no Megaplan or Arnold product-policy import,
  enforced by cumulative import lint with adapters in product packages.

Platform milestones may test extraction, usability and substitutability. They
cannot change these rules, instantiate a new primitive mapping, or activate a
new writer. A discovered defect blocks the consumer or is repaired in the
canonical owner with versioned migration and re-executed proof.

### PWC-COMPLETE-03 — Custody projection consumption

Completion inspection and status queries consume Custody's exact bounded/
cursor-incremental incident projection and its 57k benchmark receipt.
Platformization may add generic completion inspection/query DX over that API.
It cannot own a checkpoint/snapshot implementation, full-journal fallback, or
parallel projection authority.

## 4. Root hosting and terminal truth

### PWC-ROOT-01 — Exclusive root-host adapter

Only a declared root-host adapter may map an eligible accepted local result to a
root product-terminal proposal. Component bodies and nested hosts cannot accept
root truth. The adapter has separate statically total maps for all declared
business outcomes and every applicable lifecycle/control terminal. Missing,
default/catch-all, and undeclared entries fail composition before authority.

Many local results may map to one root terminal, but the accepted record retains
the exact originating result identity, class, evidence, terminal-arbitration
role, and accepting actor/Run Authority identity. The proposal still passes
current RA/Custody/WBC validation and the inherited certified terminal CAS.

Platformization may relocate the Stage 1 proposal source into this adapter; it
may not create a second terminal namespace, erase accepting provenance, change
arbitration accidentally, or make an already accepted Stage 1 terminal eligible
again.

The invoking admission binding owns this adapter by default and pins its
qualified identity/version with the selected workflow. A producer package may
publish reusable named adapters and nominate one named producer default, but
the invoker must explicitly accept it; package `default_pipeline` has no
adapter-selection semantics.

## 5. Composition, identity, retry, loops, joins, and resources

### PWC-COMP-01 — Typed composition algebra

Composition statically defines port and result binding, context narrowing,
legal nesting, retry scope, dynamic fanout/fanin, checkpoint cursor joining,
cancellation/deadline/capability/budget propagation, compensation scope,
resource settlement, and namespaces. Products provide domain meaning, types,
policies, prompts/models/tools, effects, storage, and budgets through typed
bindings. Shared packages contain no Megaplan imports, defaults, or ambient
mutable authority.

### PWC-INSTANCE-01 — Stable isolated instance identity

Component, state, checkpoint, artifact, effect, Custody, cache, and evidence
namespaces derive from run identity, parent semantic path, qualified component
identity, and explicit stable instance/item key, including loop/retry/reentry
coordinates. List position, Python object identity, mutable payload, or
completion order is insufficient. Separate invocations are disjoint unless a
typed shared-resource port explicitly says otherwise.

### PWC-RETRY-01 — Retry is not a new logical action

A retry creates a new execution attempt under the same semantic child
occurrence and reuses durable terminal/effect outcomes. The parent consumes one
aggregate child result. A repeated non-idempotent logical action requires:

1. reconciled prior ambiguity;
2. an explicit new child generation/semantic occurrence and stable key;
3. fresh admission, Run Authority and exact-target Custody;
4. a new effect/idempotency domain; and
5. a declared repeat policy.

### PWC-LOOP-01 — Durable parent-loop ledger

Before admitting each child generation, a parent records the generation,
stable child key, frozen bindings, narrowed scopes and accumulator version. It
consumes one child aggregate terminal by certified conditional mutation,
persists the accumulator and typed next/exit decision, then admits the next
generation. Crash/replay resumes from the first incomplete ledger transition.

Named enclosing-loop exits close the target loop and every intervening durable
scope deterministically; they do not behave as ambient `break`/`continue`.
Every skipped scope records one typed supersession terminal, and reentry creates
an explicit new loop instance with only declared digest-bound carry state.

### PWC-JOIN-01 — Total JoinPolicy

Every `all`, `any`, `quorum(k)`, or reducer-threshold fanout uses a closed,
versioned `JoinPolicy` over the exact child business plus lifecycle/control
result union. It declares:

- the total qualifying/tolerated/fatal classifier and canonical predicates;
- required successes and tolerated failures;
- exact satisfied and impossible parent results, retaining result class;
- tie and simultaneous-event precedence;
- loser cancellation, late-result disposition and terminalization; and
- competition with parent cancel, deadline, budget, child failure, and resource
  settlement.

No result falls through a default. Scheduler timing and completion order cannot
choose the join result.

`JoinPolicy` governs platform business/lifecycle result composition. When those
results feed semantic completion, the frozen child set and every concrete
completion-disposition aggregation instance are the exact Native S2R
implementation conforming to C2's signatures. Platformization cannot infer a
second child disposition, deduplicate evidence, or count one child/receipt more
than once.

### PWC-RES-01 — Narrowing and eventwise accounting

Child capability, deadline, cancellation and resource scopes narrow, never
widen. Each resource class has durable reservation, committed charge,
unresolved liability, release/refund, and settlement-proof states. At every
observable event:

```text
committed charges + unresolved liabilities + live worst-case reservations
  <= admitted parent budget
```

Cancellation dispatch never releases capacity. Custody expiry does not by
itself settle token, money, tool, or effect liability. Release requires
resource-specific durable proof that no further charge can accrue; otherwise
the exposure stays reserved or unresolved until reconciliation.

### PWC-CANCEL-01 — Parent cancellation and unresolved children

Parent cancellation fences new child actions, records and propagates cancel,
and reaches its accepted terminal only after the declared child aggregate,
Custody and resource dispositions. Release/transfer is exact-target,
epoch-checked and idempotent; a parent terminal never implies a release that did
not occur.

If policy permits parent acceptance after lease expiry without a child
aggregate terminal, it records exactly one typed `unresolved_child` fact with
child/target, last epoch, attempt/effect state, expiry evidence, and a mandatory
reconciliation obligation. Explanation and conformance retain it. Later
reconciliation extends history but cannot rewrite the accepted parent terminal.

## 6. Required durable primitives and boundaries

The shared platform must support, validate, lower, and prove:

1. dynamic keyed fanout with frozen bindings and canonical keyed-multiset
   reducers;
2. bounded loops with declared policy, durable ledger, and named enclosing-loop
   typed exits;
3. typed checkpointed reconfiguration that accepts a schema-versioned delta,
   derives new pins, and resumes the same cursor under an explicit reentry
   generation;
4. durable human gates with typed inputs/answers, capability, suspension,
   reentry and total bounded timeout/escalation graphs;
5. call-site retry, deadline, fallback, model-routing and resource policy;
6. closed typed phase error outcomes and a fixed infrastructure-failure
   channel;
7. effect intent/outcome/ambiguity/compensation/reconciliation;
8. canonical checkpoint/artifact references and source-mapped diagnostics;
9. the LLM Invocation Contract in §8; and
10. a durable agentic-phase boundary where a real consumer requires it.

An agentic phase has typed input, closed outer results, declared route-bearing
discriminants, named WBC protocol and bounded call/resource policy. A model may
choose a runtime number of inner calls, but undeclared metadata, mutable state,
logs, exception strings, or call order cannot control the outer route. Every
effectful inner call has its own semantic occurrence, exact Custody target and
epoch, effect slot, intent/outcome identity, attempt causality, and resource
charge. No call starts after exhaustion; any finalization reserve is admitted
up front.

Open-ended event streams and opaque polling loops are not supported by this
epic. Diagnostics point to future typed event-queue ports rather than permitting
handler relapse.

## 7. Execution modes and enforcement dispositions

The sole normative mapping is the versioned machine registry
`docs/arnold/workflow-execution-mode-dispositions.yaml`. It owns mode claims, dispositions,
rule-to-disposition assignments, store/capability access, and logical
isolation. S1 validates and content-addresses the candidate registry; S6 may
stabilize an accepted version. CLI/runtime tables and the summaries below are
generated or informative views and may not be edited as independent policy.
An unknown mode, disposition, rule, store class, or consumer-local override
fails closed.

### 7.1 Five modes — informative registry view

| ID | Mode | Permitted claim |
| --- | --- | --- |
| `MODE-1` | `authoring_preview` | Rapid working-tree trials, fixtures, fakes and debugger use. Unsupported Python is conspicuously non-durable and earns no checkpoint, replay, resume, admission, comparison, compatibility or certification claim. |
| `MODE-2` | `durable_sandbox` | Fresh experiment/fork using production lifecycle semantics with isolated non-production identity, checkpoint/WBC history and fake or explicit sandbox effects. |
| `MODE-3` | `comparison` | Quarantined candidate/shadow evaluation over copied or recorded inputs; it cannot route, resume, acquire admitted authority, emit admitted effects/terminals, or be promoted. |
| `MODE-4` | `admitted_production` | Exact pins, current RA/Custody/WBC, certified CAS and effect protocol. Changed code requires a compatible resume, admitted migration, explicit fork, or new run. |
| `MODE-5` | `certification` | Admitted semantics plus clean-install, conformance, compatibility, DX/documentation and unrelated-consumer proof for stable claims. |

Mode is part of execution identity and evidence. No runner infers mode from a
flag, path, environment, or desired outcome.

### 7.2 Six dispositions — informative registry view

| ID | Disposition | Meaning |
| --- | --- | --- |
| `DISP-1` | `always_hard` | Effect leakage, evidence-as-authority, namespace collision, executable impersonation, admitted-history mutation and unsafe identity reuse are blocked in every mode. |
| `DISP-2` | `automatic` | Fresh executable/experiment/attempt identities, namespaces, fork lineage, digests and cache invalidation are mechanically derived. |
| `DISP-3` | `production_admission_gate` | Durable subset, exact pins, current authority/Custody/WBC, effect protocol, migration compatibility and production CAS block only the production claim. |
| `DISP-4` | `stable_publication_gate` | Clean wheels, conformance/compatibility profiles, second-consumer proof, stable docs/examples and published SLOs block only the stable claim. |
| `DISP-5` | `authoring_advisory` | Granularity, complexity, naming, candidate reuse class, pre-SLO performance and incomplete documentation warn but do not block experimentation. |
| `DISP-6` | `non_durable_only` | Unsupported or nondeterministic exploration may run, but cannot checkpoint, replay, resume, compare authoritatively, certify, publish or enter admitted evidence. |

Every restriction has exactly one versioned disposition per applicable mode.
There is no implicit warning-to-error promotion and no consumer-local severity
override. Mode changes never downgrade `always_hard`.

### 7.3 Logical store and capability isolation

The registry's store matrix is authoritative. Its classes distinguish
ephemeral fixture/debug state, sandbox checkpoint/WBC/effect history,
content-addressed artifacts, evidence/proof, and production authority/Custody/
WBC/checkpoint/effect/idempotency/cache stores. Classification follows logical
authority and namespace even when several classes share a physical backend.

Every access grant binds mode, store class, capability, namespace,
run/experiment lineage, allowed verbs, retention, and effect/idempotency
domain. Preview, sandbox, comparison, and certification receive no production
mutation capability by default. Comparison reads production-derived material
only through a declared redacted/copy boundary. Certification writes dedicated
fixtures and proof namespaces, never live product keys. Content addressing
does not by itself make a production store safe for experimentation.

### 7.4 Edit, repeat, replay, and fork

Editing a function, prompt, binding, dependency, or policy may run immediately
as a fresh preview/sandbox/comparison experiment. The platform automatically
derives a new content digest, lineage, attempt and disjoint state/checkpoint/
artifact/effect/cache namespace. A migration declaration is not required merely
to experiment.

The operations remain distinct:

- **resume:** same durable occurrence and compatible pinned meaning;
- **replay:** reconstruct from accepted recorded results without repeating
  nondeterministic work;
- **retry:** new attempt under the same semantic occurrence and declared policy;
- **rework/new generation:** new declared product occurrence;
- **fork:** new authorized history with provenance from a prior recorded
  boundary and isolated authority/effect identity.

“Continue from here with changed code” is an explicit fork/new run or admitted
migration, never disguised resume. Experimental output and history cannot be
relabelled as admitted production or stable conformance evidence, even when its
content digest later equals an admitted digest.

## 8. Authority, durability, humans, effects, and LLMs

### PWC-AUTH-01 — Conjunctive action admission

Every authority-increasing action requires exact admitted source/manifest,
component contract/implementation, dependency lock, policy, product contract,
state/payload, prompt/model/tool and schema bindings as applicable, plus:

```text
current accepted Run Authority decision/grant and fence
AND current exact-target Custody owner/lease/epoch
AND applicable exact-version WBC boundary/effect history
```

No receipt, checkpoint, cache, journal projection, CLI state, comparison result,
or conformance artifact supplies a missing conjunct. Schedulers may choose an
eligible worker, queue and wakeup time for an already accepted immutable action;
they may not select route, retry, escalation, reconfiguration, cost/stall,
resume, cancellation, or terminal behavior.

### PWC-CAS-01 — Certified production conditional mutation

Every decision consumption, arbitration, aggregate terminal, loop-ledger and
root-terminal site joins to one linearizable conditional mutation enforced by
the admitted production store/service. Application read/check/write,
process-local locks, serialized schedules, and in-memory fake CAS are not
authority proof.

Receipts bind store/service and adapter implementations, key schema,
consistency mode, deployment topology, proof-registry incarnation/restore
generation, raw high-water cursor, run, commit and lock. Two independent clients
must contend at the real pre-commit barrier and prove one accepted winner and a
loser that observes the durable winner. Exact set equality holds among lowered
arbitration sites, the policy index, forced-race fixtures and runtime-observed
sites.

### PWC-HUMAN-01 — Human gates

Human gates are durable components, not blocking calls or inbox flags. Their
timeout/escalation graph is total and bounded or terminates under a declared
overall deadline. Each generation advances to one named suspension/escalation
generation or one exact business/lifecycle result; there is no implicit
`needs_human`, `blocked`, or `deadline_exhausted` default.

Answer/answer, answer/timeout and accepted-but-unconsumed-answer/cancel races use
declared production CAS. One distinct answer wins; idempotent replay returns it;
every non-winning or late fact is durable and non-routing. Resume validates
schema and executable pins and reacquires current RA/Custody.

### PWC-CKPT-01 — Checkpoints and code evolution

Checkpoints bind semantic cursor; parent/child lineage; semantic, RA, WBC and
Custody coordinates; minimal schema-qualified durable state; content-addressed
artifact references; exact executable, lock, product-contract and model/tool
pins. Inline and aggregate payload bounds are enforced. Large/sensitive values
use typed content-addressed references with schema, digest, retention and
liveness; transient handles, mutable paths, clients, secrets, projections and
unbounded histories are rejected.

Suspended runs resume pinned artifacts, use a separately admitted compatible
resume, consume one provenance-bearing migration decision, start a new run/fork,
or quarantine. A matching path/name or “latest code” is never compatibility.

### PWC-EFFECT-01 — Effects and reconciliation

External actions execute only through declared slots:

```text
validate envelope
  -> persist intent + exact target + logical idempotency identity
  -> dispatch
  -> persist accepted outcome or explicit ambiguity
  -> continue, compensate, or reconcile under fresh current admission
```

Crash after durable outcome rebuilds the product receipt and never repeats the
effect. Intent without knowable outcome enters reconciliation. Effect identity
binds run, semantic occurrence/component instance, slot and logical action while
attempt identity remains distinct. Cancellation does not turn ambiguity into
success or settlement.

### PWC-LLM-01 — LLM Invocation Contract

Every LLM/model/tool invocation binds prompt template/version/digest, protected
rendered input or digest, resolved provider/model capability, tool set/schema,
decoding/routing policy, context digest, token/cost/call/deadline budgets, cache
policy/key, semantic occurrence and attempt causality. Accepted output and usage
are durable. Replay consumes them without another call; retry/fallback creates a
new attempt without overwriting history. Cache hits are provenance-bearing
outcomes whose keys include every declared semantic input. Effectful tools also
follow `PWC-EFFECT-01` with exact Custody.

## 9. Resolution, bindings, capabilities, compatibility, and observation

### PWC-BIND-01 — Explicit binding environment

Typed bindings provide consumer domain types, business semantics, policies,
capabilities, effects, compensation, storage, prompts/models/tools and resource
values with deterministic precedence. They may vary declared values; they cannot
mutate shared internals, widen inherited scopes, introduce hidden defaults, or
change the component's protocol.

Every policy binding uses the common immutable policy envelope: stable policy
kind and schema version, recursively immutable canonical serializable values,
explicit scope and attachment point, source provenance, deterministic
precedence, and digest.
Policies may parameterize declared lifecycle and resource mechanics, but cannot
contain callable invocation targets, open route tables, mutable/ambient
defaults, or hidden product branches. Inheritance and overrides are explicit;
an authored inline/call-site policy or policy-contract requirement changes the
caller component digest. An imported policy has its own executable identity;
selecting a different compatible concrete policy/value changes that identity
and the transitive graph-lock digest. Incompatible schema/value/attachment
changes require migration/new-attempt/quarantine and invalidate the applicable
admission, checkpoint, compatibility, and proof claims.

### PWC-PROFILE-01 — Effective capability closure

Required conformance profiles are mechanically derived from the descriptor,
lowered topology, resolved transitive lock, and actual policy/effect/model/tool/
storage bindings. Descriptor-declared profiles are claims, not truth.
Under-declaration fails initial admission, rebind, migration, substitution and
stable publication. Irrelevant profiles may be omitted only when this derived
closure excludes them.

The production deriver is never its own sole oracle. An independently
implemented profile-closure verifier re-derives the set from the same frozen
inputs without importing production selection or omission logic. Mutation
fixtures inject, remove, or rebind each capability-bearing topology edge,
policy, effect, model/tool, storage, human, checkpoint, resource, and root
binding; each mutation must add or remove exactly the applicable profile
families. Rebind, migration, substitution, or lock change invalidates prior
profile receipts and reruns both derivations before authority or publication.

### PWC-COMPAT-01 — Two compatibility claims

`new_instance_compatible` permits a substitute only for newly admitted
instances after black-box conformance. `resume_compatible` separately proves
identical durable state/checkpoint/effect semantics or one accepted migration.
Neither receipt implies the other. Active runs remain pinned, migrate with exact
provenance, fork/new-run, or quarantine.

Compatibility/change classes are explicit for Python API, descriptor, source
body/topology, manifest schema/hash and producer entry, prompt/model/tool/policy,
state/checkpoint, dependency implementation, effects and observable traces.

### PWC-OBS-01 — Portable causal evidence

The portable `arnold.workflow.event_envelope.v2` joins component instance and
parent, lifecycle,
decision, RA, Custody, WBC, checkpoint, effect, resource and terminal causality.
Generic tooling explains both consumers without importing product code. Logs,
including agent/LLM/tool calls and cost, remain queryable by exact semantic
occurrence, generation, attempt and experiment iteration, but cannot authorize
or route.

The envelope carries stable bidirectional correlation across run, workflow and
step occurrence, loop/rework/retry/reentry generation, execution attempt,
platform-issued agent session, model call, tool call, effect, trace/span and
immutable log/transcript artifact. A query can navigate from any workflow/step
attempt to its agent transcript, calls, effects, cost and structured logs, and
from any of those records back to the owning semantic occurrence and source
span, plus the accepted consuming decision or terminal when one exists.
Provider session/request IDs are optional provenance, never the platform
identity. Prompt/model/tool/policy versions, usage/cost, and artifact
digest/schema/retention/redaction provenance remain attached.

This is complete durable-boundary auditing, not instruction-by-instruction
Python tracing. Step inputs/outputs, attempts, terminals, declared effects and
structured telemetry are durable; large or sensitive values use immutable
artifact references. Internal work requiring independent retry, provenance or
durable inspection becomes a visible step/effect boundary. Diagnostic logs and
transcripts remain observational and cannot manufacture a decision, terminal,
route, authority grant or proof verdict. Durable events carry the correlation
keys; reverse indexes and search views are rebuildable projections.

Trace compatibility is normalized partial-order equivalence, not sorted-log
equality. It preserves exact event multiplicity, per-instance/attempt total
order, declared parent/child/effect happens-before edges, accepted and rejected
arbitration facts, relational identity changes, and only declared unordered
sibling sets. A versioned content-addressed field table classifies every field
as exact, canonical, relational, or ignorable volatile. Unknown fields fail.
Raw IDs, source-store cursor/schema/digest and multiplicity are verified before
normalization; normalization cannot deduplicate, fold, invent, erase relations,
or sort away races.

An allowlist/table amendment requires a content-addressed governance entry that
binds old/new versions, changed fields, rationale, affected proof-map rows and
raw histories, plus approval and verification independent of the trace
producer team. Comparators pin the version frozen by their admission or
certification receipt and reject newer versions without that accepted entry.
An amendment never retroactively reinterprets a prior result: it invalidates
all affected comparison/conformance receipts, then an independent verifier
replays the original raw histories under both versions and issues new receipts
or preserves the failure. Reclassifying an arbitration, identity, route,
multiplicity, or causality field as volatile is forbidden.

### PWC-PROOF-01 — Independent proof

The semantic source oracle does not call the production lowerer. The raw audit
verifier does not import production event selection, filtering, folding,
deduplication, cardinality, causality or verdict logic. Producers never solely
verify themselves. Each proof row binds invariant, owner/gate, exact executable
evidence, authoritative producer, independent verifier, negative mutation, run,
commit, lock, schemas and execution-derived status.

Independence applies specifically to executable-closure digest classification,
profile-closure derivation, trace-field/volatile-allowlist governance, and
final-validator verdict logic. Their mutation corpora are derived from the
normative inclusion/closure rules rather than from the production
implementation's own classifier.

### PWC-PROOF-02 — Intermediate gates and receipt-bound adoption

S1 through S5 each declare a typed `conformance_gate` over the rows owned
through that milestone. It runs before merge eligibility and again against
merge HEAD. S6 declares the cumulative `final_conformance_gate`. Stage and
final validators reject missing, extra, unknown, stale, red, unexecuted,
unbound, unconsumed, self-certified, cross-incarnation, and stitched rows.

Milestone validation is evidence, not permission to change product authority.
Any operation that selects a new canonical runtime for admissions, changes a
product dependency/binding lock, disables an old authority path, or promotes a
registry state must run as the milestone's declared typed post-validation
transition. The chain, not prose or milestone status, supplies the exact
accepted merge-HEAD readiness receipt; the registered non-shell handler
atomically consumes it and emits one idempotent transition receipt; a separate
post-transition validator must accept the resulting state before the milestone
can complete. S2A's runtime selection, S4's Megaplan binding migration, and
S6's stable publication are mandatory transitions. Candidate code remains
non-authoritative through merge; existing occurrences remain pinned unless a
separately accepted occurrence migration applies.

## 10. Seven-milestone ownership and freeze rules

| Sprint | Immutable responsibility | Gate meaning |
| --- | --- | --- |
| **S1 — candidate standard and executable corpus** | Consume the hashed handoff; freeze extraction direction; pin candidate Descriptor v1, executable-closure digest, distribution authority, finite route discriminants, root-adapter ownership, the sole machine mode/disposition/store registry, lifecycle, composition, humans, joins/resources, serialization, LLM, bindings, locks, trace-allowlist governance and compatibility contracts; extend Native's DX baselines; build executable reference models and invalid/mutation corpora. | Reproducible candidate, explicitly experimental. Prose-only rules, reset baselines, fake production CAS, missing negative dispositions, implicit modes, or self-authored classifiers fail. |
| **S2A — product-neutral runtime enforcement** | Promote the accepted runtime/adapters in place; implement shared validation/lowering interfaces, lifecycle/root hosting, local test kit, repeat/fork, mode/store isolation, identity/namespaces, loops/joins/resources/cancellation, RA/Custody/WBC generation, locks/receipts, manifest evolution, effects, traces, independent profile re-derivation and real-store contention. | The canonical runtime and authority substrate is executable and fault-tested without a fork or shadow implementation. S2B need not invent lifecycle, admission, authority or durable-state semantics. |
| **S2B — `.pype` authoring core** | Productize the one-workflow-per-file parser/linker, conservative digest canonicalizer, source correspondence, distribution/package selection, converter, identity-aware transactional refactors, minimum scriptable commands, source maps and checkout/editable/wheel/sdist/cloud equivalence over S2A. | The S4-blocking format/package/identity/refactor core is one product-neutral experimental SDK. S3 can add DX without changing semantics; S4 need not invent authoring, identity, packaging or migration rules. |
| **S3 — developer experience and tooling** | Complete the CLI/editor/navigation/format/lint/topology/preview/test experience, actionable diagnostics and tracebacks, unfamiliar-author tasks and pinned p50/p95 benchmarks using only S2B/S2A semantics. | The rigorous format is usable without alternate parser/runtime meaning or manual generated-file maintenance; S4 receives a complete local authoring loop. |
| **S4 — first extraction under isolation** | Extract evaluator panel, bounded refinement, human gate and effect-safe action first; remove Megaplan defaults; prove concurrent isolation and multiple shapes; make Megaplan consume shared implementations with unchanged golden traces; exercise reconfigure and a bounded agentic fixture where justified. | One correct product consumes real shared patterns, with low-latency faithful local tests and installed equivalence. |
| **S5 — unrelated adversarial consumer** | Build a real non-Megaplan workflow with different types, outcomes, root maps, joins, timeout/resource policies, effects, storage and composition shapes; produce and verify the executable independence manifest/scan; challenge and narrow S1; swap an independently originated implementation; independently re-derive profiles; prove separate new-instance/resume compatibility, migration, pin and quarantine; exercise the evolution matrix and modes. | A mechanically independent second consumer must expose product leakage. Unresolved or unproved independence blocks S6 rather than being normalized into the standard. |
| **S6 — stable certification and adoption** | Incorporate S5 findings, then freeze stable public surfaces; finalize docs/DX/SLOs, compatibility/evolution, registry states, retention/GC, conformance profiles/manifests, allowlist replay/invalidation, CAS/registry/manifest provenance, LLM/effect/checkpoint/resource receipts, reusable-pattern registry, validator self-mutations and completion manifest. | Only this gate may promote candidate artifacts from `experimental` to `stable`. |

The milestone count is seven. S2A owns platform runtime meaning while consuming
the Native completion kernel unchanged; S2B owns the
S4-blocking authoring/package/identity/refactor core; S3 owns the developer
experience over that exact core. Handoff processing remains part of S1 and
completion-manifest work remains part of S6.

### S5 independence contract

S5 emits a content-addressed `unrelated-consumer-independence-manifest` and an
independently executed source/dependency/lineage scan. They bind:

- an isolated build/test lock in which the Megaplan distribution is absent;
- zero imports or copied definitions from Megaplan domain schemas/types,
  outcome vocabulary, root adapters, policies, effects, storage bindings, or
  product helpers;
- at least two composition shapes absent from Megaplan's actual usage;
- a materially non-isomorphic outcome algebra with at least one domain
  outcome/condition absent from Megaplan, plus materially different root,
  timeout/join/resource, effect, and storage bindings; overlap in generic
  lifecycle/business terms such as success, cancelled, timeout, or failed is
  permitted and is not independence evidence;
- at least one independently originated compatible component implementation,
  with no fork/copy lineage from the implementation it substitutes; and
- exact source tree, dependency graph, schema/vocabulary comparison,
  composition-shape diff, repository lineage, commit, and lock.

This rule does **not** forbid imports from the generic Arnold workflow platform
or the reusable component packages under test; those are the subject of the
proof. It forbids product coupling and costume reuse. Missing, self-declared,
or producer-only-verified independence blocks S5.

## 11. Standardization closure clauses

All eleven clauses are simultaneously required. These identifiers are stable
proof-map keys.

| ID | Clause | Closure condition |
| --- | --- | --- |
| `PWC-CL-01` | Descriptor | Every canonical workflow and shared component satisfies `PWC-DESC-01`, while private local steps fold into their workflow; effective profiles derive from actual topology/lock/bindings. |
| `PWC-CL-02` | Lifecycle | One enforced protocol covers every kind, disjoint business/control results, atomic conditions, humans, replay and root-host exclusivity. |
| `PWC-CL-03` | Composition | Exactly-one canonical workflows, static canonical imports, package-owned optional workflow default distinct from invoking-admission root-adapter selection, ports, outcomes, finite named route discriminants, named exits, reconfigure, retry/generation, parent loops, joins, cancellation, scopes, resources and namespaces are explicit and statically checkable. |
| `PWC-CL-04` | Isolation | Every instance has disjoint durable and authority/effect namespaces unless an explicit shared-resource port exists. |
| `PWC-CL-05` | Authority and evidence | Generated RA/Custody/WBC integration, exact pins and certified production CAS govern every authority-increasing boundary; evidence never grants. |
| `PWC-CL-06` | Resolution | Governed distribution ownership/fork lineage and a content-addressed transitive component lock deterministically select exact logical and executable versions before product work, distinguishing authority collision from legitimate version evolution. |
| `PWC-CL-07` | Evolution | Change classes and pin/migrate/new-run/quarantine behavior are explicit; new-instance and resume compatibility remain separate. |
| `PWC-CL-08` | Observation | Product-neutral causal events and raw-before-normalized partial-order equivalence preserve multiplicity, causality, arbitration and provenance; allowlist amendments require independent governance, invalidate affected receipts, and replay pinned raw histories. |
| `PWC-CL-09` | Conformance | Stable components pass every applicable static, lifecycle, isolation, recomposition, fault, install, upgrade, substitution, DX, effect and LLM profile selected by both production and independent profile derivation. |
| `PWC-CL-10` | Variability | Consumer meaning and values enter only through bindings; schedulers and shared internals cannot invent policy or routes. |
| `PWC-CL-11` | Execution modes | The sole machine registry governs all five modes, six dispositions, and logical store/capability access over one compiler/lifecycle/event model with explicit claim boundaries; derived views cannot drift, and easy fresh experiments cannot impersonate admitted history. |

## 12. Standardization acceptance-family index

These 38 identifiers are exhaustive and stable. A sprint may refine fixtures,
but it may not close a family with a hand-authored label, hash-only receipt,
projection, stitched cross-run history, producer self-certification, or a test
path that bypasses production semantics. The S6 completion manifest must consume
every applicable row and explicitly mark any mechanically inapplicable profile
with the derived-closure evidence that excludes it.

| ID | Acceptance family | Required proof shape | Primary owner(s) |
| --- | --- | --- | --- |
| `PWC-AF-01` | Descriptor/static invalidity | Zero or multiple workflows per `.pype`, private-member import, `.py` durable topology, missing ports/results, ambiguous package defaults, implicit/missing root adapter, undeclared state/effects/routes, illegal imports/nesting/cycles/recursion, hidden globals/helpers and noncanonical state fail before authority. | S1, S2A, S2B, S6 |
| `PWC-AF-02` | Decompose/reinsert | Extracting and reinserting a child workflow preserves normalized behavior modulo declared namespace boundaries and records deliberate identity migration. | S2B, S4, S5 |
| `PWC-AF-03` | Shape recomposition | Root, child, sequential, loop, fanout/fanin, suspension, cancellation and retry preserve the local contract. | S2A, S4, S5 |
| `PWC-AF-04` | Concurrent isolation | Duplicate/concurrent differently bound instances cannot cross-read or act on state, checkpoints, effects, Custody or outcomes. | S2A, S4 |
| `PWC-AF-05` | Lifecycle crash matrix | Crash around admission, body, checkpoint, effect, suspend/resume, compensation, condition, local terminal and root terminal yields only declared history. | S2A, S4 |
| `PWC-AF-06` | Authority negatives | Stale/missing RA, Custody, WBC, pins, locks, schemas, workers or artifacts reject before body/effect intent; evidence cannot authorize. | S1, S2A |
| `PWC-AF-07` | Deterministic resolution and manifest evolution | Checkout/editable/wheel/sdist/cloud select the same logical workflow, canonical import graph, ordinary shared-step Python dependencies and transitive lock; source/package/dependency and manifest schema/hash/producer evolution plus mixed workers follow pin/migrate/reject rules. | S2A, S2B, S5, S6 |
| `PWC-AF-08` | Suspended-run evolution | Pinned-old resume, compatible resume, exact migration, explicit new run and breaking-change quarantine cover source/prompt/model/tool/policy/schema/dependency changes. | S5, S6 |
| `PWC-AF-09` | Substitution and consumer independence | The independently originated implementation and compatible version pass the same black-box component contract; the unrelated-consumer manifest and independent scan prove absent Megaplan product coupling while permitting generic platform/component imports. | S5, S6 |
| `PWC-AF-10` | Cross-consumer explanation | Generic tooling reconstructs Megaplan and unrelated-consumer causal histories without product imports and navigates bidirectionally between source occurrence/attempt and agent/model/tool/effect/cost/log artifacts. | S5, S6 |
| `PWC-AF-11` | Binding variability | Product policy/effect/type/storage variation changes only declared values, outcomes and digests, never shared protocol. | S2A, S4, S5 |
| `PWC-AF-12` | Registry and namespace governance | Experimental/stable/deprecated/withdrawn transitions, distribution ownership/delegation/fork lineage, legitimate same-key version evolution versus conflicting-authority collision, and content-addressed conformance manifests are enforced; only S6 may promote stable versions after S5 challenge evidence. | S1, S2B, S5, S6 |
| `PWC-AF-13` | Deterministic authoring and executable closure | The pinned canonicalizer includes every normative closure input, excludes only the closed list, records algorithm version, and is mutation-tested independently; allowed pure helpers retain transitive call/dependency source maps; ordinary shared-step Python/third-party imports resolve under exact environment/feature/plugin pins; forbidden nondeterminism, import-time I/O/registration and hidden route/effect/policy escapes reject; compile-twice/replay-twice are equivalent. | S1, S2B |
| `PWC-AF-14` | Diagnostics/source maps | Stable codes, authored spans, semantic paths, supported rewrites and user-code tracebacks cover every rejection/fault without a second editor/CLI rule table. | S1, S2A, S2B, S3, S6 |
| `PWC-AF-15` | Faithful local harness | Production compiler/lifecycle/validators/events with fakes and virtual time match installed traces; fake CAS cannot certify production; the mode registry's store/capability matrix prevents production namespace access. | S2A, S3, S4, S6 |
| `PWC-AF-16` | Non-repeatable replay | Accepted external-effect, LLM/tool and human results replay without repeating the action. | S2A, S4 |
| `PWC-AF-17` | LLM identity/budget/cache | Prompt/model/tool/policy pins, budget, cache provenance, retry and fallback mutations preserve attempt/effect truth. | S1, S2A, S6 |
| `PWC-AF-18` | Checkpoint payload discipline | Inline limits, artifact refs, digest/schema/retention/redaction/recovery and invalid-ref negatives are enforced. | S1, S2A, S6 |
| `PWC-AF-19` | Ordinary v1/v2 matrix | A v1 suspension under v2 deploy deterministically chooses pin, compatible resume, migration/new run or quarantine. | S5, S6 |
| `PWC-AF-20` | Source-to-admission provenance and adoption | Selected logical workflow plus definition/import/call sites → versioned manifest → transitive lock → governed producer entry → explicit invoking-admission root adapter → admission receipt retain topology, source correspondence, registry high-water and adapter provenance; `default_pipeline` never implies an adapter. Runtime/product binding promotions remain non-authoritative through merge, change only in the declared typed receipt-consuming transition, and pass separate post-transition verification before milestone completion. | S2A, S2B, S4, S6 |
| `PWC-AF-21` | Root and outcome atomicity | Root exclusivity/total maps/provenance, result-class separation, atomic conditions, false contract violation and indeterminate quarantine pass mutations. | S1, S2A |
| `PWC-AF-22` | Retry versus generation | Same-child retry, aggregate consumption, new generation and durable/ambiguous non-idempotent effects obey `PWC-RETRY-01`. | S2A, S4 |
| `PWC-AF-23` | Parent-loop recovery | Crash at generation, admission, terminal, consumption CAS, accumulator and next/exit boundaries produces no skip/duplicate. | S2A, S4 |
| `PWC-AF-24` | Compatibility split | Separate content-addressed new-instance and resume receipts; no-migration old checkpoint rejects; one admitted migration succeeds. | S1, S2A, S2B, S5 |
| `PWC-AF-25` | Partial-order traces and allowlist governance | Raw multiplicity precedes versioned field classification; unknown fields and duplicate/drop/invert/sort-away mutations fail; field-table amendments require independent approval, invalidate affected receipts, and replay raw histories under pinned old/new versions. | S1, S2A, S5, S6 |
| `PWC-AF-26` | Parent cancel/Custody expiry | Fence/release/transfer/expiry across epochs/reassignment retains `unresolved_child` and never fabricates terminal or settlement. | S1, S2A, S4 |
| `PWC-AF-27` | Total joins and races | All/any/quorum/reducer joins classify all results, produce exact satisfaction/impossibility, cancel losers and retain late/race facts. | S1, S2A, S5 |
| `PWC-AF-28` | Eventwise resource accounting | Narrowed budgets and reservation/charge/liability/settlement/refund invariants hold across retry, cache, cancel, expiry and late completion. | S1, S2A, S6 |
| `PWC-AF-29` | Named exit/reconfigure/agentic | Typed loop exits, checkpointed reconfigure and agentic inner-call/effect/Custody semantics reject sentinel, ambient and route-leak variants. | S1, S2A, S5 |
| `PWC-AF-30` | Canonical routing boundary | Canonical values, keyed reducers, frozen fanout, closed errors, scheduler separation, finite named discriminants distinct from payload, and whole-payload/open-string/callable smuggling negatives preserve one route authority. | S1, S2A, S2B, S6 |
| `PWC-AF-31` | Cumulative DX safety | Inherited Native corpus, all registry-derived diagnostic dispositions, zero hidden routes, timed author tasks, bidirectional occurrence/agent-log navigation, p50/p95 and local/installed trace equality remain cumulative. | S1, S3–S6 |
| `PWC-AF-32` | Human timeout/races | Total bounded graph plus answer/timeout, answer/answer and accepted-answer/cancel CAS orders retain one winner and every loser fact. | S1, S2A, S4, S5 |
| `PWC-AF-33` | Effective profile closure | Required profiles derive from actual topology/lock/bindings; an independent deriver and per-capability inclusion/removal/rebind mutations catch under-derivation; changes invalidate and recompute receipts before admission, rebind/migration, substitution, and publication. | S1, S2A, S5, S6 |
| `PWC-AF-34` | Cap/result-class separation | Product control-cap exhaustion remains business outcome; platform resource exhaustion remains lifecycle/control under varied values/policies. | S1, S2A, S5 |
| `PWC-AF-35` | Mode/severity/store registry | The sole machine registry gives five modes and six dispositions complete versioned transitions, logical store/capability isolation, and identical behavior across both consumers; duplicate tables, implicit mode/promotion, unknown classes, and production-store access from experimental defaults fail. | S1, S2A, S3, S5, S6 |
| `PWC-AF-36` | Edited-code repeat/fork | Recorded input/checkpoint trials get fresh digest/lineage/attempt/namespaces and preserve bidirectionally queryable source/agent-session/LLM/tool/effect/cost/log/transcript records without appending to admitted history. | S2A, S3–S6 |
| `PWC-AF-37` | Mode-boundary negatives | Silent changed-code resume, production authority/effect/key/cache/checkpoint reuse, evidence promotion and durable claims from unsupported preview all fail. | S1, S2A, S3, S5, S6 |
| `PWC-AF-38` | Native completion-kernel preservation | The exact `PWC-COMPLETE-04` dependency passes at intake, in-place extraction, authoring generation/lint, projection deletion/rebuild/forgery, Megaplan migration, adversarial-consumer candidate/algebra/absence/waiver/reopen mutations, and final two-consumer certification. Any changed semantic ID, evidence window, child mapping, registry projection, writer/decoder/evaluator, import direction, restore behavior, stable occurrence, or false-pass result fails before adoption/publication. | S1, S2A, S2B, S3, S4, S5, S6 |

## 13. Proof trust, receipts, and final manifest

Every closure clause and acceptance family has one proof-map row with:

```text
stable invariant/family ID
  -> owning sprint and gate
  -> exact executable evidence artifact
  -> authoritative primary-store producer
  -> independent verifier implementation
  -> negative/mutation/race/crash fixture IDs
  -> exact run, commit, lock, schemas and raw history cursor
  -> status derived from execution
```

The stage validator consumes the exact rows owned through the current
milestone; the final validator consumes the complete map. Both reject missing,
extra, unknown, stale, red, unexecuted, unbound, unconsumed, self-certified,
cross-incarnation or stitched rows. The validation receipt binds the proof-map
hash before its own receipt is appended. An artifact's existence, a whole-file
hash, a projection, a human-authored `PASS`, or a copied upstream receipt is
never enough.

An independently authored validator-self-mutation corpus must prove those
failures rather than assume them. Starting from one known-green synthetic map,
separate fixtures inject at least: one red row, stale commit/lock/schema/raw
cursor, unbound evidence, produced-but-unconsumed evidence, an extra/unknown
row, a missing row, producer self-certification, cross-incarnation evidence,
and stitched runs. Each mutation must make both the final validator and the
completion-manifest consumer fail for the named reason. The validator and its
mutation generator may share schemas, but not verdict or row-selection logic.

The production arbitration index maps every semantic site to policy/version,
closed participants, conditional-write key/precondition, precedence, winner/
loser/late disposition, gate, and forced-race fixtures. Pairwise release orders
at the real pre-commit barrier must converge on the same policy result unless a
policy explicitly declares and tests non-associative multi-party behavior.

## 14. Deliberately variable

The platform standardizes where variability is declared and bound, not its
consumer-owned values. The following remain variable behind typed contracts:

- product domain types, business meaning, artifacts, outcome vocabularies and
  product cap policies;
- prompt content, provider/model/tool selection, policy and budget values;
- effect, compensation, storage and external-system implementations;
- scheduler, transport and physical persistence implementation;
- legal sibling wall-clock ordering;
- UI and performance/cost before a component publishes an SLO;
- authoring-advisory presentation, while its severity/promotion semantics stay
  versioned platform data; and
- internal compiler APIs until explicitly promoted.

Variation may not change source authority, result-class separation, lifecycle,
identity/isolation, current action admission, effect safety, settlement,
arbitration, raw trace conservation, or a certified compatibility claim.

## 15. Non-goals and prohibited duplication

- Generalizing every Megaplan function or imposing Megaplan-shaped domain
  outcomes on unrelated products.
- Rebuilding or shadowing Run Authority, Custody, WBC, recovery, projections,
  controlled-writer/producer registries, durable stores, credential brokerage,
  worker-fleet supervision, or their accepted restore/fencing contracts.
- Replacing the completed `native-platform-followup` durability/security/fleet
  work; this epic integrates it through exact adapters and proofs.
- A workflow marketplace.
- Freezing internal compiler APIs before they become deliberate public
  composition surfaces.
- Declaring stable abstractions from one consumer.
- Arbitrary Python as durable workflow code. Unsupported exploration remains
  available only through the explicit `non_durable_only` disposition.
- Standardizing product prompt/model/policy/budget values rather than their
  declaration, identity, replay, evolution and enforcement.
- Open-ended item streams, opaque polling loops or a hidden runtime callback
  escape hatch. Future event-queue ports require a separate contract.
- Treating Platformization as a repair venue for missing M11 capabilities or
  extracting patterns inside the Native Parity S7 handoff.

## 16. Completion and launch posture

The epic is complete only when all 11 closure clauses and every mechanically
applicable one of the 38 acceptance families are accepted from cumulative,
independently verified evidence; Megaplan and the unrelated consumer use the
same clean-wheel implementations without copies or reverse imports; the second
consumer's independence manifest and external scan prove the exact §10
criteria while allowing generic platform/component imports; it changes domain
semantics and composition shape, swaps one independently originated
implementation, exercises suspended-run evolution, and still passes the shared
contract; and S6 publishes the reusable-pattern registry plus a
content-addressed Platformization completion manifest.

Unproven product abstractions and compiler internals remain experimental. A
green Megaplan path alone is not platform completion. A stable package cannot
be published before the S5 challenge and S6 certification.

Preparation of this contract, the North Star, briefs, chain, and proof-map
skeleton does **not** authorize launch. Launch remains blocked on §1 and must be
an explicit future action.

## 17. Controlling references

- `docs/arnold/pype-authoring-contract.md`
- `docs/arnold/workflow-execution-mode-dispositions.yaml`
- `.megaplan/tickets/01KY2DWSJG0B9YKAJRYA0107XE-build-a-reusable-native-workflow-pattern-platform-after-megaplan-parity.md`
- `.megaplan/initiatives/megaplan-native-parity-corrective/`
- `.megaplan/initiatives/megaplan-native-parity-corrective/GOLDEN_TRACE_CONTRACT.md`
- `.megaplan/initiatives/megaplan-native-parity-corrective/briefs/s7-final-conformance-rollout.md`
- `docs/arnold/megaplan-native-parity-corrective-plan.md`
- `docs/arnold/megaplan-native-representation-report.md`
- `.megaplan/initiatives/native-platform-followup/`
