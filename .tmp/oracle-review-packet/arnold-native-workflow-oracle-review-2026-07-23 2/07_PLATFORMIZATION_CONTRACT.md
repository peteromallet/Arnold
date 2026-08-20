# Native Workflow Platformization Contract

## Status and authority

- **Status:** prepared, not launched.
- **Epic:** `native-workflow-platformization`.
- **Upstream:** `megaplan-native-parity-corrective` must complete and publish the
  exact handoff defined in §1 before this epic may start.
- **Scope:** the reusable component, composition, package, evolution, developer
  experience, and conformance layer built from proven Native Parity boundaries.
- **Normative role:** this file is the immutable cross-milestone contract for
  S1, S2A, S2B, S4, S5, and S6.
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

1. its completion manifest and `final-proof-map.json`;
2. its accepted final-conformance receipt, bound to the proof-map hash;
3. its content-addressed Native-to-Platformization handoff manifest;
4. the exact accepted commit/tree, installed artifact and dependency lock; and
5. the accepted M11/Native proof-registry incarnation, restore generation, and
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
composition algebra, extracted pattern packages, unrelated-consumer challenge,
behavioral compatibility claims, authoring modes, and cumulative conformance.
It must not fork the underlying stores, validators, leases, event truth, fleet,
security broker, or projection model.

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

An `@workflow` in ordinary `.py` is preview-only. It may run with fresh
ephemeral identity and fake/sandbox effects but cannot produce a durable
checkpoint, replay/resume, comparison, admission, publication, or certification
claim. Every durable mode rejects it before authority or effect intent.

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
the cross-package allowlist of canonical workflows, exact locks,
source/descriptor correspondence, and append-only identity migration log.
“Allowlist” here is package visibility, not a source-file export table. The
implementation must extend existing canonical pack/lock metadata rather than
create a parallel descriptor without an inventory-backed decision.

### PWC-ID-01 — Logical identity, drift, and retention

Workflow identity is `(distribution_name, logical_workflow_name)`, where the
logical name is explicit workflow ID or decorated function name and is unique
within the distribution. Physical and wheel paths are provenance. Executable
identity adds typed ports/outcomes, hostability, topology/policy/child
references, shared component versions, private code/helper slices, and
behavior-relevant prompt/model/tool bindings.

Physical relocation with unchanged logical/digest identity is provenance-only.
Rename, signature/outcome/hostability change, extract/inline, private/shared
step promotion, or behavior drift requires an explicit scoped migration record,
new attempt, or quarantine. A blanket alias is forbidden.

Pinned `.pypeline`, authored `subflow`, and durable `.py` workflow artifacts
remain exact-read-only resolvable while a nonterminal occurrence depends on
them. They cannot author/admit new work and are retired when no live pin remains.

## 3. Component descriptor and lifecycle

### PWC-DESC-01 — Descriptor v1 minimum

Every shared `.py` step and every canonical `.pype` workflow—including a
workflow hosted as a child—has one qualified, versioned descriptor declaring.
Private file-local steps have no independent descriptor; their contract and
digest are folded into the containing workflow:

- kind, package/component identity, contract version, implementation digest,
  hostability and extension points;
- canonical typed input/output/state schemas and checkpoint payload class/limits;
- conditioned closed business outcomes and applicable closed lifecycle/control
  terminals;
- dependencies, capabilities, policies, effects, compensations, storage,
  suspension/reentry and human-timeout graph;
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
  -> outcome-condition evaluation and one accepted local terminal
  -> parent consumption or root-host proposal
```

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

Each business outcome declares canonical payload, semantic postcondition,
required durable evidence, effect/compensation completeness, emission mode, and
condition version. A proposal freezes those fields plus its executable and
policy pins. The emitting component evaluates the condition exactly once at its
local terminal-acceptance boundary and atomically records the evaluation with
terminal acceptance.

- True accepts the proposed business outcome.
- False accepts only
  `contract_violation(reason=outcome_condition_failed,
  attempted_outcome=...)`.
- Missing, stale, ambiguous, or unavailable required evidence quarantines or
  reconciles until determinable, or follows an explicitly declared lifecycle
  policy.

Replay consumes the recorded evaluation. Parents and root hosts never recompute
it or substitute a different business result.

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

## 5. Composition, identity, retry, loops, joins, and resources

### PWC-COMP-01 — Typed composition algebra

Composition statically defines port and result binding, context narrowing,
legal nesting, retry scope, dynamic fanout/fanin, checkpoint cursor joining,
cancellation/deadline/capability/budget propagation, compensation scope,
resource settlement, and namespaces. Products provide domain meaning, types,
policies, prompts/models/tools, effects, storage, and budgets through typed
bindings. Shared packages contain no Megaplan imports, defaults, or ambient
mutable authority.

### PWC-ID-01 — Stable isolated identity

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

### 7.1 Five modes

| ID | Mode | Permitted claim |
| --- | --- | --- |
| `MODE-1` | `authoring_preview` | Rapid working-tree trials, fixtures, fakes and debugger use. Unsupported Python is conspicuously non-durable and earns no checkpoint, replay, resume, admission, comparison, compatibility or certification claim. |
| `MODE-2` | `durable_sandbox` | Fresh experiment/fork using production lifecycle semantics with isolated non-production identity, checkpoint/WBC history and fake or explicit sandbox effects. |
| `MODE-3` | `comparison` | Quarantined candidate/shadow evaluation over copied or recorded inputs; it cannot route, resume, acquire admitted authority, emit admitted effects/terminals, or be promoted. |
| `MODE-4` | `admitted_production` | Exact pins, current RA/Custody/WBC, certified CAS and effect protocol. Changed code requires a compatible resume, admitted migration, explicit fork, or new run. |
| `MODE-5` | `certification` | Admitted semantics plus clean-install, conformance, compatibility, DX/documentation and unrelated-consumer proof for stable claims. |

Mode is part of execution identity and evidence. No runner infers mode from a
flag, path, environment, or desired outcome.

### 7.2 Six dispositions

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

### 7.3 Edit, repeat, replay, and fork

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

### PWC-PROFILE-01 — Effective capability closure

Required conformance profiles are mechanically derived from the descriptor,
lowered topology, resolved transitive lock, and actual policy/effect/model/tool/
storage bindings. Descriptor-declared profiles are claims, not truth.
Under-declaration fails initial admission, rebind, migration, substitution and
stable publication. Irrelevant profiles may be omitted only when this derived
closure excludes them.

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

The portable event envelope joins component instance and parent, lifecycle,
decision, RA, Custody, WBC, checkpoint, effect, resource and terminal causality.
Generic tooling explains both consumers without importing product code. Logs,
including agent/LLM/tool calls and cost, remain queryable by exact semantic
occurrence, generation, attempt and experiment iteration, but cannot authorize
or route.

Trace compatibility is normalized partial-order equivalence, not sorted-log
equality. It preserves exact event multiplicity, per-instance/attempt total
order, declared parent/child/effect happens-before edges, accepted and rejected
arbitration facts, relational identity changes, and only declared unordered
sibling sets. A versioned content-addressed field table classifies every field
as exact, canonical, relational, or ignorable volatile. Unknown fields fail.
Raw IDs, source-store cursor/schema/digest and multiplicity are verified before
normalization; normalization cannot deduplicate, fold, invent, erase relations,
or sort away races.

### PWC-PROOF-01 — Independent proof

The semantic source oracle does not call the production lowerer. The raw audit
verifier does not import production event selection, filtering, folding,
deduplication, cardinality, causality or verdict logic. Producers never solely
verify themselves. Each proof row binds invariant, owner/gate, exact executable
evidence, authoritative producer, independent verifier, negative mutation, run,
commit, lock, schemas and execution-derived status.

## 10. Six-milestone ownership and freeze rules

| Sprint | Immutable responsibility | Gate meaning |
| --- | --- | --- |
| **S1 — candidate standard and executable corpus** | Consume the handoff; freeze extraction direction; pin candidate Descriptor v1, authoring profile, modes/dispositions, lifecycle, composition, root, conditions, humans, joins/resources, durable primitives, serialization, LLM, bindings, locks, evolution, trace and compatibility contracts; extend Native's DX baselines; build executable reference models and invalid/mutation corpora. | Reproducible candidate, explicitly experimental. Prose-only rules, reset baselines, fake production CAS, missing negative dispositions or implicit modes fail. |
| **S2A — product-neutral runtime enforcement** | Implement shared validation/lowering interfaces, lifecycle/root hosting, local test kit, repeat/fork, safe preview/sandbox effects, identity/namespaces, loops/joins/resources/cancellation, RA/Custody/WBC generation, locks/receipts, manifest evolution, effects, traces and real-store contention. | The runtime and authority substrate is executable and fault-tested. S2B need not invent lifecycle, admission, authority or durable-state semantics. |
| **S2B — `.pype` authoring format and toolchain** | Productize the one-workflow-per-file parser/linker, source correspondence, package selection, converter, identity-aware refactors, CLI/editor surfaces, diagnostics, source maps and checkout/editable/wheel/sdist/cloud equivalence over S2A. | The adopted format is complete and usable as one product-neutral experimental SDK. S4 need not invent authoring, identity, packaging, migration or tooling rules. |
| **S4 — first extraction under isolation** | Extract evaluator panel, bounded refinement, human gate and effect-safe action first; remove Megaplan defaults; prove concurrent isolation and multiple shapes; make Megaplan consume shared implementations with unchanged golden traces; exercise reconfigure and a bounded agentic fixture where justified. | One correct product consumes real shared patterns, with low-latency faithful local tests and installed equivalence. |
| **S5 — unrelated adversarial consumer** | Build a real non-Megaplan workflow with different types, outcomes, root maps, joins, timeout/resource policies, effects, storage and composition shapes; challenge and narrow S1; swap an independent implementation; prove separate new-instance/resume compatibility, migration, pin and quarantine; exercise the evolution matrix and modes. | A second consumer must expose product leakage. Unresolved leakage blocks S6 rather than being normalized into the standard. |
| **S6 — stable certification and adoption** | Incorporate S5 findings, then freeze stable public surfaces; finalize docs/DX/SLOs, compatibility/evolution, registry states, retention/GC, conformance profiles/manifests, CAS/registry/manifest provenance, LLM/effect/checkpoint/resource receipts, reusable-pattern registry and completion manifest. | Only this gate may promote candidate artifacts from `experimental` to `stable`. |

The milestone count is six. S2A and S2B are deliberately separate: S2A owns
runtime meaning, while S2B owns the public authoring/tooling surface over that
meaning. Handoff processing remains part of S1 and completion-manifest work
remains part of S6.

## 11. Standardization closure clauses

All eleven clauses are simultaneously required. These identifiers are stable
proof-map keys.

| ID | Clause | Closure condition |
| --- | --- | --- |
| `PWC-CL-01` | Descriptor | Every canonical workflow and shared component satisfies `PWC-DESC-01`, while private local steps fold into their workflow; effective profiles derive from actual topology/lock/bindings. |
| `PWC-CL-02` | Lifecycle | One enforced protocol covers every kind, disjoint business/control results, atomic conditions, humans, replay and root-host exclusivity. |
| `PWC-CL-03` | Composition | Exactly-one canonical workflows, static canonical imports, package-owned optional default selection, ports, outcomes, named exits, reconfigure, retry/generation, parent loops, joins, cancellation, scopes, resources and namespaces are explicit and statically checkable. |
| `PWC-CL-04` | Isolation | Every instance has disjoint durable and authority/effect namespaces unless an explicit shared-resource port exists. |
| `PWC-CL-05` | Authority and evidence | Generated RA/Custody/WBC integration, exact pins and certified production CAS govern every authority-increasing boundary; evidence never grants. |
| `PWC-CL-06` | Resolution | A content-addressed transitive component lock deterministically selects executable contracts before product work. |
| `PWC-CL-07` | Evolution | Change classes and pin/migrate/new-run/quarantine behavior are explicit; new-instance and resume compatibility remain separate. |
| `PWC-CL-08` | Observation | Product-neutral causal events and raw-before-normalized partial-order equivalence preserve multiplicity, causality, arbitration and provenance. |
| `PWC-CL-09` | Conformance | Stable components pass every applicable static, lifecycle, isolation, recomposition, fault, install, upgrade, substitution, DX, effect and LLM profile. |
| `PWC-CL-10` | Variability | Consumer meaning and values enter only through bindings; schedulers and shared internals cannot invent policy or routes. |
| `PWC-CL-11` | Execution modes | All five modes and six dispositions share one compiler/lifecycle/event model with explicit claim boundaries; edits are easy fresh experiments but cannot impersonate admitted history. |

## 12. Standardization acceptance-family index

These 37 identifiers are exhaustive and stable. A sprint may refine fixtures,
but it may not close a family with a hand-authored label, hash-only receipt,
projection, stitched cross-run history, producer self-certification, or a test
path that bypasses production semantics. The S6 completion manifest must consume
every applicable row and explicitly mark any mechanically inapplicable profile
with the derived-closure evidence that excludes it.

| ID | Acceptance family | Required proof shape | Primary owner(s) |
| --- | --- | --- | --- |
| `PWC-AF-01` | Descriptor/static invalidity | Zero or multiple workflows per `.pype`, private-member import, `.py` durable topology, missing ports/results, ambiguous package defaults, undeclared state/effects/routes, illegal imports/nesting/cycles/recursion, hidden globals/helpers and noncanonical state fail before authority. | S1, S2A, S2B, S6 |
| `PWC-AF-02` | Decompose/reinsert | Extracting and reinserting a child workflow preserves normalized behavior modulo declared namespace boundaries and records deliberate identity migration. | S2B, S4, S5 |
| `PWC-AF-03` | Shape recomposition | Root, child, sequential, loop, fanout/fanin, suspension, cancellation and retry preserve the local contract. | S2A, S4, S5 |
| `PWC-AF-04` | Concurrent isolation | Duplicate/concurrent differently bound instances cannot cross-read or act on state, checkpoints, effects, Custody or outcomes. | S2A, S4 |
| `PWC-AF-05` | Lifecycle crash matrix | Crash around admission, body, checkpoint, effect, suspend/resume, compensation, condition, local terminal and root terminal yields only declared history. | S2A, S4 |
| `PWC-AF-06` | Authority negatives | Stale/missing RA, Custody, WBC, pins, locks, schemas, workers or artifacts reject before body/effect intent; evidence cannot authorize. | S1, S2A |
| `PWC-AF-07` | Deterministic resolution and manifest evolution | Checkout/editable/wheel/sdist/cloud select the same logical workflow, canonical import graph and transitive lock; source/package and manifest schema/hash/producer evolution plus mixed workers follow pin/migrate/reject rules. | S2A, S2B, S5, S6 |
| `PWC-AF-08` | Suspended-run evolution | Pinned-old resume, compatible resume, exact migration, explicit new run and breaking-change quarantine cover source/prompt/model/tool/policy/schema/dependency changes. | S5, S6 |
| `PWC-AF-09` | Substitution | Independent implementation and compatible version pass the same black-box component contract. | S5, S6 |
| `PWC-AF-10` | Cross-consumer explanation | Generic tooling reconstructs Megaplan and unrelated-consumer causal histories without product imports. | S5, S6 |
| `PWC-AF-11` | Binding variability | Product policy/effect/type/storage variation changes only declared values, outcomes and digests, never shared protocol. | S2A, S4, S5 |
| `PWC-AF-12` | Registry governance | Experimental/stable/deprecated/withdrawn transitions and content-addressed conformance manifests are enforced; only S6 may promote stable versions after S5 challenge evidence. | S1, S6 |
| `PWC-AF-13` | Deterministic authoring | Allowed pure helpers retain transitive call/dependency source maps and digest drift; forbidden nondeterminism, I/O and hidden route/effect/policy escapes reject through reachable helpers; compile-twice/replay-twice are equivalent. | S1, S2B |
| `PWC-AF-14` | Diagnostics/source maps | Stable codes, authored spans, semantic paths, supported rewrites and user-code tracebacks cover every rejection/fault. | S1, S2A, S2B, S6 |
| `PWC-AF-15` | Faithful local harness | Production compiler/lifecycle/validators/events with fakes and virtual time match installed traces; fake CAS cannot certify production. | S2A, S2B, S4, S6 |
| `PWC-AF-16` | Non-repeatable replay | Accepted external-effect, LLM/tool and human results replay without repeating the action. | S2A, S4 |
| `PWC-AF-17` | LLM identity/budget/cache | Prompt/model/tool/policy pins, budget, cache provenance, retry and fallback mutations preserve attempt/effect truth. | S1, S2A, S6 |
| `PWC-AF-18` | Checkpoint payload discipline | Inline limits, artifact refs, digest/schema/retention/redaction/recovery and invalid-ref negatives are enforced. | S1, S2A, S6 |
| `PWC-AF-19` | Ordinary v1/v2 matrix | A v1 suspension under v2 deploy deterministically chooses pin, compatible resume, migration/new run or quarantine. | S5, S6 |
| `PWC-AF-20` | Source-to-admission provenance | Selected logical workflow plus definition/import/call sites → versioned manifest → transitive lock → governed producer entry → admission receipt retain topology, source correspondence, registry high-water and adapter provenance. | S2A, S2B, S6 |
| `PWC-AF-21` | Root and outcome atomicity | Root exclusivity/total maps/provenance, result-class separation, atomic conditions, false contract violation and indeterminate quarantine pass mutations. | S1, S2A |
| `PWC-AF-22` | Retry versus generation | Same-child retry, aggregate consumption, new generation and durable/ambiguous non-idempotent effects obey `PWC-RETRY-01`. | S2A, S4 |
| `PWC-AF-23` | Parent-loop recovery | Crash at generation, admission, terminal, consumption CAS, accumulator and next/exit boundaries produces no skip/duplicate. | S2A, S4 |
| `PWC-AF-24` | Compatibility split | Separate content-addressed new-instance and resume receipts; no-migration old checkpoint rejects; one admitted migration succeeds. | S1, S2A, S2B, S5 |
| `PWC-AF-25` | Partial-order traces | Raw multiplicity precedes versioned field classification; unknown fields and duplicate/drop/invert/sort-away mutations fail. | S1, S2A, S6 |
| `PWC-AF-26` | Parent cancel/Custody expiry | Fence/release/transfer/expiry across epochs/reassignment retains `unresolved_child` and never fabricates terminal or settlement. | S1, S2A, S4 |
| `PWC-AF-27` | Total joins and races | All/any/quorum/reducer joins classify all results, produce exact satisfaction/impossibility, cancel losers and retain late/race facts. | S1, S2A, S5 |
| `PWC-AF-28` | Eventwise resource accounting | Narrowed budgets and reservation/charge/liability/settlement/refund invariants hold across retry, cache, cancel, expiry and late completion. | S1, S2A, S6 |
| `PWC-AF-29` | Named exit/reconfigure/agentic | Typed loop exits, checkpointed reconfigure and agentic inner-call/effect/Custody semantics reject sentinel, ambient and route-leak variants. | S1, S2A, S5 |
| `PWC-AF-30` | Canonical routing boundary | Canonical values, keyed reducers, frozen fanout, closed errors, scheduler separation and payload-smuggling negatives preserve one route authority. | S1, S2A, S6 |
| `PWC-AF-31` | Cumulative DX safety | Inherited Native corpus, all diagnostic dispositions, zero hidden routes, timed author tasks, p50/p95 and local/installed trace equality remain cumulative. | S1, S2B, S4–S6 |
| `PWC-AF-32` | Human timeout/races | Total bounded graph plus answer/timeout, answer/answer and accepted-answer/cancel CAS orders retain one winner and every loser fact. | S1, S2A, S4, S5 |
| `PWC-AF-33` | Effective profile closure | Required profiles derive from actual topology/lock/bindings; under-declaration fails admission, rebind/migration and publication. | S1, S2A, S5, S6 |
| `PWC-AF-34` | Cap/result-class separation | Product control-cap exhaustion remains business outcome; platform resource exhaustion remains lifecycle/control under varied values/policies. | S1, S2A, S5 |
| `PWC-AF-35` | Mode/severity matrix | Five modes and six dispositions have complete versioned transitions and identical behavior across both consumers; implicit mode/promotion fails. | S1, S2A, S2B, S5, S6 |
| `PWC-AF-36` | Edited-code repeat/fork | Recorded input/checkpoint trials get fresh digest/lineage/attempt/namespaces and preserve separately queryable source/agent/LLM/tool/effect/cost/trace records. | S2A, S2B, S4–S6 |
| `PWC-AF-37` | Mode-boundary negatives | Silent changed-code resume, production authority/effect/key/cache/checkpoint reuse, evidence promotion and durable claims from unsupported preview all fail. | S1, S2A, S2B, S5, S6 |

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

The final validator consumes the complete map and rejects missing, extra,
unknown, stale, red, unexecuted, unbound, self-certified, cross-incarnation or
stitched rows. The validation receipt binds the proof-map hash before its own
receipt is appended. An artifact's existence, a whole-file hash, a projection,
a human-authored `PASS`, or a copied upstream receipt is never enough.

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
applicable one of the 37 acceptance families are accepted from cumulative,
independently verified evidence; Megaplan and the unrelated consumer use the
same clean-wheel implementations without copies or reverse imports; the second
consumer changes domain semantics and composition shape, swaps one
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

- `.megaplan/tickets/01KY2DWSJG0B9YKAJRYA0107XE-build-a-reusable-native-workflow-pattern-platform-after-megaplan-parity.md`
- `.megaplan/initiatives/megaplan-native-parity-corrective/`
- `.megaplan/initiatives/megaplan-native-parity-corrective/GOLDEN_TRACE_CONTRACT.md`
- `.megaplan/initiatives/megaplan-native-parity-corrective/briefs/s7-final-conformance-rollout.md`
- `docs/arnold/megaplan-native-parity-corrective-plan.md`
- `docs/arnold/megaplan-native-representation-report.md`
- `.megaplan/initiatives/native-platform-followup/`
