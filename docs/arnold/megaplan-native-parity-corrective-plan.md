# Megaplan Native Parity Corrective Plan

## Purpose

This plan makes canonical Megaplan's native Python source the complete,
load-bearing owner of product semantics, while adopting the completed
`custody-control-plane` M11 substrate for permission, exclusive ownership,
durable boundary/effect history, recovery, observation, and generic proof.

The prior native-composition/platform work delivered useful authoring,
lowering, topology, checkpoint, packaging, and conformance substrate. It did
not finish semantic migration. The measured current path can lower roughly 85
authored nodes and then rebuild a 14-step component graph, discard dynamic
fanout policy, and route through handler strings, runtime maps, `_core` state,
compatibility/CLI, and auto-drive. Existing proof can turn predeclared
`implemented` rows into whole-file hashes while non-blocking auxiliary checks
remain red. This is semantic erasure disguised as compression.

The custody work is complementary. It provides the generic control plane but
does not choose Megaplan product topology. Native Parity must bind canonical
lowered nodes to that substrate, migrate producer identity away from legacy
handlers, and delete competing route authorities. It must not recreate the
substrate.

This plan supersedes the closeout status claims in:

- `docs/arnold/megaplan-composition-conformance-report.md`;
- `docs/arnold/megaplan-native-representation-conformance-report.md`.

Those remain historical receipts, never final parity evidence.

## Sequencing assumption and launch contract

Native Parity starts only after `custody-control-plane` reaches its complete
M11 end state as one clean, landed, verified revision. The chain enforces this
with:

```yaml
kind: chain_completed
chain: .megaplan/initiatives/custody-control-plane/chain.yaml
require_manifest: true
```

The accepted prerequisite manifest/proof map must bind the final chain spec,
North Star, all M11 milestone records and publication evidence, exact source and
installed-runtime revision, proof artifacts, and their hashes. M11's proof must
cover at least:

- exact Run Authority, Custody, and WBC contract/schema versions;
- enabled enforcement cohort and zero-bypass controlled-writer inventory;
- exact-version WBC producer/query registries;
- transactional attempt/effect history, outbox, and reconciliation;
- custody lease/epoch lifecycle and the shared action validator;
- recovery, retry, cross-host transfer/reclaim, and effect ambiguity;
- backup/store-rollback recovery proving restore-resistant Run Authority fences
  and Custody epochs, plus canonical acceptance-time repair-request
  revalidation;
- rebuildable projections at declared source cursors;
- captured replay, independent verification, wheel/sdist and cloud runtime.

S1 must additionally execute capability probes against that exact admitted
revision. The probes prove that M11 can register external writers from all
three execution planes behind one enforce-mode validator; bind opaque Native
program/policy/lock/prompt/tool/Plan-Contract digests; durably CAS one accepted
decision to one consumed transition across backup/restore; address exact
task/effect Custody targets at production-shaped fanout scale; expose the
exact-version WBC ambiguity/reconciliation/checkpoint/query surface; classify
repair validation failures; and retain pinned installed artifacts across
cross-host handoff. Native owns Plan Contract canonicalization; M11 compares
the resulting opaque versioned digest rather than interpreting product fields.

Intermediate M8/M9 receipts, dirty or divergent branches, shadow/default-off
guards, support manifests, status labels, and auto-publish commits do not
satisfy admission. Native Parity consumes only the accepted M11 surface.

If the prerequisite manifest is stale, incomplete, or mismatched, this chain
does not start. Native Parity does not repair or locally emulate missing M11
scope. A missing required capability yields a typed
`blocked_on_m11_point_release` disposition and stops the chain for a new
content-addressed M11 prerequisite; it must not enter the ordinary milestone
retry loop or create a Native side store/facade.

## End state

> **One authored semantic topology; one exact authority-decision history; one
> current exclusive custody owner; one durable boundary/effect history; any
> number of disposable projections.**

The canonical semantic source is:

`arnold_pipelines/megaplan/workflows/workflow.pypeline`

together with named native subworkflows, declared policies attached to named
source constructs, and audited pure phase bodies behind typed interfaces.

A reviewer can read those files and understand prep, critique, gate, revise,
tiebreaker, finalize, execute, review, rework, override, human gates, retries,
caps, model routing, suspension, resume, checkpoint identity, and terminal
outcomes without reading component tables, handler-local state mutation,
runtime route maps, `_core` transition tables, compatibility projections, CLI
dispatch, or auto-drive.

The system need not maximize visible steps. It must use the minimum readable
workflow that completely determines behavior.

The normative composition oracle is
`.megaplan/initiatives/megaplan-native-parity-corrective/GOLDEN_TRACE_CONTRACT.md`.
It is the human-reviewed scenario/invariant contract, not a generated route
graph. An independent static source oracle derives source occurrences and
structured-control relations without calling the production lowerer; raw
primary-store exports are checked by a separately implemented audit normalizer
and verifier. Production lowering supplies actual traces, never expected ones.
The contract freezes observable ordering, raw multiplicity, causality,
identities, effects, reentry, and terminals for named scenarios without
becoming a second workflow model. Neither fixtures nor normalized traces may
route, authorize, resume, or repair runtime.

## Contract ownership

| Contract | Owns | Must never be treated as |
| --- | --- | --- |
| Native topology | Product routes, loops, fanout/fanin, semantic child/reentry/checkpoint paths, call-site policy and terminal outcomes | A decorative projection over component/handler routes |
| Megaplan Plan Contract | Milestone/product `provides`, `assumes`, and `pre_existing` interfaces | Route, grant, lease, boundary evidence, or execution authority |
| Generated manifest and executable/component lock | Immutable lowering, install, and replay coordinates derived from source | An independent topology, route, grant, or lease owner |
| Run Authority | Grants, subject attempts, accepted claims/decisions, coordinator fences, CAS/idempotency and quarantine | Renewable custody, WBC history, status, scheduling or repair ownership |
| Custody | Exact action/repair target, exclusive renewable lease, owner process-birth identity, transfer/reclaim/expiry and monotonic epoch | Permission to perform the action |
| WBC | Exact-version boundary declarations and durable execution-attempt/effect/provenance history | Grant, lease, transition, route or lifecycle decision |
| Projections | Rebuildable observation at declared source cursors | Bearer token for any positive action |

Every authoritative dispatch, transition, retry, resume, effect, terminal
acceptance, cancellation, adoption, publication, or delivery requires:

```text
current Run Authority grant + current coordinator fence
AND current Custody lease + current custody epoch
AND required exact-version WBC evidence at declared boundaries
```

The current grant/fence and lease/epoch authorize and fence the action. WBC
establishes durable facts and may make a boundary incomplete or indeterminate;
it never supplies permission. A WBC success receipt or projection cannot cause
the next route, skip work, resume, retry, complete, cancel, publish, or deliver.

## Four-domain identity model

Every executable node and dynamic child carries four related but distinct
identity domains:

1. **Semantic identity:** authored node/invocation and deterministic child path,
   including task ID, batch identity, and fanout item path where applicable.
2. **Run Authority identity:** subject attempt and its current independent
   coordinator fence.
3. **WBC identity:** execution attempt, exact boundary-contract version, ordered
   event/effect history, and causal parent/child joins.
4. **Custody identity:** exact action target, lease owner/process birth, and
   current custody epoch.

No shared `attempt_id` may collapse them. Generated mappings must state
cardinality and causality. Set-equality proof must show that every authored and
lowered executable node/child has the required WBC lifecycle and authoritative
action bindings, and that no un-authored producer or action exists.

Every authored typed product-decision occurrence and terminal acceptance must
create or link exactly one accepted Run Authority Decision under the current
subject attempt/fence. The corresponding runtime transition/action consumes
that exact decision ID, outcome, and CAS sequence. No handler, status field,
WBC receipt, or projection may independently persist or infer the accepted
route. Final set equality rejects orphan, duplicate, unaccepted, stale-fence,
outcome-mismatched, or multiply consumed decisions.

Every checkpoint/reentry envelope also binds the authored program/topology
digest, call-site-policy digest, and exact WBC boundary-contract version.
Resume after any drift uses the pinned original or an explicit accepted typed
migration/new-attempt/quarantine decision, with new subject/WBC attempt and
current custody epoch as applicable. A matching semantic path string does not
authorize silent recompilation under changed source, policy, or contract.
It also binds the installed artifact and dependency lock plus applicable prompt
content/tool-schema identities. Any behavior-relevant asset drift follows the
same pinned-original or explicit typed disposition rule.
Where Plan Contract fields can change execution or evidence obligations, the
envelope also binds a named digest of the canonical normalized product contract.
Changes to `provides`, `assumes`, or `pre_existing` use the same pin/migrate/
new-attempt/quarantine rule; presentation-only fields are explicitly excluded
and mutation-tested.

A standing compatibility declaration makes a migration eligible; it never
authorizes an application. Every migrated run/semantic occurrence consumes one
accepted Run Authority migration decision binding the exact from/to digests,
migration implementation/version and state input/output digests. The transform
is applied once by CAS with provenance and the required fresh subject/WBC
attempt plus current Custody. No class-level rule silently resumes a run.

The same executable binding is validated on every Native authority-increasing
dispatch, typed decision, transition, terminal acceptance, and effect envelope
before product body or effect intent: admitted program/topology digest,
call-site-policy digest, exact WBC contract version, and installed-artifact
digest. Homogeneous checkout/wheel/cloud parity is insufficient; one stale
worker in an otherwise current run must quarantine/reject before action unless
an explicit accepted migration/new-attempt decision continues it.

The action envelope therefore names the semantic occurrence; exact accepted
Run Authority decision/grant/fence; exact Custody target/owner/epoch; WBC
attempt, contract, and required evidence; and admitted program/topology,
call-policy, installed-artifact, dependency-lock, prompt, and tool bindings as
applicable. Plan Contract or generated-manifest metadata cannot add a route or
authorize an action.

Attempt, child and generation terminals remain distinct. Each WBC/worker
execution attempt has one immutable terminal, including `retryable_failure`.
An accepted retry decision starts a new logical retry generation under the
same semantic child, with a new RA/WBC attempt and current Custody. Retry policy
eventually accepts one immutable aggregate child/component terminal, which its
parent consumes exactly once by CAS. Repeating completed logical work requires
an explicitly authored new child generation and semantic key; it is never
another spelling of retry. Durable effect outcomes are reused and intent-only
ambiguity reconciles before either path advances.

Every executable, dependency lock, prompt/tool asset, and schema pinned by a
nonterminal run remains retained and resolvable. Garbage collection is blocked
until referencing runs are terminal or have an accepted migration or
quarantine disposition.

## Semantic compression versus semantic erasure

### Deterministic Python boundary

Native means that deterministic Python topology is the sole control-flow
authority, not merely that orchestration happens to be written in Python.
Topology/control code uses a versioned fenced subset. Ambient wall time,
randomness/UUIDs, environment or process state, unordered traversal, mutable
globals, reflection/dynamic import/eval, unmanaged threads/tasks, and direct
filesystem/network/subprocess I/O are rejected or must cross a declared typed
durable phase/effect boundary. Logical time, seeds, configuration, and ordered
collections are explicit inputs. Exception behavior cannot become an
undeclared product route.

Static diagnostics and runtime guards enforce the boundary. Each rejection has
a stable code, authored file/span and semantic path, the violated rule, and a
supported rewrite. Lowered/generated nodes retain source maps. Opaque phase or
effect implementations may compute or interact externally behind typed ports,
closed outcomes, declared policy/effects, and WBC history; transitive callees
may not use opacity to reclaim product routing.

Control-decision inputs are canonical, schema-qualified serializable values.
Host paths, datetimes/wall time, unordered containers, arbitrary floating-point
edge cases, and mutable/custom object identity are normalized under a declared
schema or rejected before they enter a decision digest.

Good compression keeps repeated control semantics in explicit typed,
inspectable abstractions. The plan should generalize:

- closed decisions and terminal outcomes;
- bounded loops with typed exits;
- typed exits that address a named enclosing loop, with exhaustive handling and
  no sentinel or exception route smuggling. Acceptance terminates and closes
  the named loop instance; every intervening durable scope records exactly one
  `superseded_by_named_exit` control terminal in innermost-to-outermost order.
  Reentry is an explicit new loop instance at generation zero, with any carried
  state declared and digest-bound in the exit payload;
- dynamic map/reducer with worker cap and sequential fallback;
- fanout-admission snapshots of the canonical item set, context, policy and
  call bindings, plus reducers over canonically keyed multisets rather than
  completion order;
- human suspension and exact durable reentry;
- semantic checkpoint coordinates;
- retry, timeout, model, cap, fallback, and effect policy at call sites;
- one reusable finalize/approval/execute/review/rework delivery cycle.
- checkpointed typed reconfiguration with a schema-versioned delta, changed
  bindings and exact reentry rather than ambient live flags;
- a durable agentic phase with closed outer outcomes and a named inner
  model/tool-call WBC protocol, durable budgets and ordered effects, but no
  authority over the next outer product route. Every inner call reserves and
  charges durable budget before invocation; no call starts after exhaustion.
  A finalization call is legal only from a named, admitted and charged reserve;
  otherwise exhaustion emits the closed `budget_exhausted` control result.

Topology handles only declared typed phase outcomes, including declared error
outcomes. Undeclared exceptions enter one fixed infrastructure-failure channel
and its authored retry/recovery policy; topology may not branch over an open set
of exception classes. Open-ended streams or polling inside topology are
deliberately unsupported in this epic; finite admitted collections are required
until a separately designed event-queue port exists.

Pure computation may remain inside phase bodies:

- parsing and serialization;
- prompt construction and model invocation;
- signal construction and normalization;
- payload validation and deterministic recovery;
- lens selection and result merging;
- ready-batch calculation and task shaping;
- command execution and narrowly scoped artifact writes.

A body ceases to be pure if it chooses a product route, owns retry/cap/model or
suspension policy, mutates workflow state, determines fanout topology, dispatches
an override, or defines resume/checkpoint identity. Moving or renaming such code
does not make it pure; transitive callees are scanned.

### Authoring readability and edit locality

The authoritative surface must remain the natural place for future changes:

1. one topology representation; all runtime graphs, indexes, routes, and
   projection metadata are generated or downstream;
2. one authored reusable delivery cycle, called from every entry route rather
   than copied;
3. one small durable primitive set: phase/subworkflow call, closed decision,
   bounded loop, dynamic map/reducer, human gate/reentry, checkpoint, explicit
   effect/compensation, terminal, and named policy;
4. generated mechanical identity and control-plane bindings—authors declare
   semantic keys, typed ports/outcomes, targets, and policy/effect references,
   not Run Authority/WBC/Custody IDs or parallel registries;
5. retry/timeout/model/cap/fallback/suspension/effect policy local to the call
   site or one plainly named object;
6. closed vocabulary and compile-time exhaustiveness; handler/runtime-only
   outcomes fail closed;
7. advisory structural complexity targets of at most three nested control
   levels, roughly 120 nonblank semantic top-level lines and 80 per subworkflow,
   with reviewed AST/IR-backed exceptions and no embedded route/interface/policy
   dictionaries; structural uniqueness, not a raw line count, is binding;
8. each future extension changes at most two manual authoritative declarations;
   generated artifacts do not count;
9. examples/lints reject route-bearing handler returns, status/auto route reads,
   suffix ID heuristics, undeclared effects, hidden retry/caps, manual alias
   maps, and non-generated projection topology.
10. a lightweight in-process authoring harness uses the production compiler,
    lowerer, and transition semantics with typed phase fakes, recorded
    boundaries, logical time/fault injection, fast-forwarded human input, and
    normalized trace inspection; it is not an alternative route engine or
    release proof.

### Execution modes and enforcement disposition

The platform is permissive about experiments and exact about durable claims.
S1 freezes one machine-readable execution-mode matrix; every CLI/API entry,
trace, checkpoint, artifact and diagnostic names one of these modes, and no
mode may be inferred from a directory, flag omission or credential accident.

| Mode | What authors may do | Identity, effects and authority | Claim it may make |
|---|---|---|---|
| `authoring_preview` | Run working-tree code repeatedly, including Python outside the durable subset | Fresh ephemeral experiment identity; effects are fake-only; no RA/Custody, production idempotency key, durable checkpoint or admitted history | Functional preview only; explicitly not resumable, replayable, comparable as parity evidence, admissible or certifiable |
| `durable_sandbox` | Run or fork an edited step/subworkflow from a typed fixture or recorded boundary | Working-tree content digest, fresh run/attempt lineage and isolated namespace; recorded inputs/results; fake or explicitly sandbox-scoped effects and idempotency keys; sandbox RA/Custody/WBC only | Durable experimental history, replay and debugging inside the sandbox; never production continuation or release proof |
| `comparison` | Evaluate candidate code against recorded/duplicated inputs | Quarantined comparison identity/namespace; no admitted RA/Custody, effects or resume selector; non-promotable provenance | Non-authoritative differential evidence only |
| `admitted_production` | Start or resume the exactly admitted executable | Exact program/policy/schema/artifact pins plus production RA, Custody, WBC and effect protocol | Canonical durable history and authorized action |
| `certification` | Exercise packaged candidates across checkout, wheel/cloud and conformance profiles | Fresh certification identities and controlled effects; consumes admitted proof contracts but cannot mutate a product run | Compatibility/stability/release claim only after all blocking receipts pass |

Editing code and selecting an old recorded boundary is therefore easy, but it
is a **fork**, not a resume. The harness automatically content-addresses the
working tree, starts fresh experiment lineage, derives new effect/cache/
idempotency namespaces, retains immutable provenance to the source run and
boundary, and groups repeated attempts for comparison. It never overwrites or
appends to the source history. Silent continuation of an admitted occurrence
under a changed behavior-relevant digest remains a hard failure.

Every restriction has exactly one enforcement disposition:

1. `always_hard`: truth/authority separation, namespace isolation, no
   production effect or idempotency reuse, no history overwrite, closed route
   authority, and truthful mode/provenance labels;
2. `automatic`: content digests, fresh experiment/run/attempt identities,
   isolated keys and lineage are generated without asking the author;
3. `production_admission_gate`: deterministic-subset, exact-version,
   migration, authority, Custody, WBC and effect requirements block production
   admission or resume without blocking a fresh experiment;
4. `stable_publication_gate`: installed-package, compatibility, conformance,
   second-consumer, documentation and release requirements block stable claims,
   not authoring or sandbox execution;
5. `authoring_advisory`: complexity, granularity, naming, provisional reuse and
   documentation guidance warn locally and block only a later declared quality
   or stable-publication gate; or
6. `non_durable_only`: an unsupported durable construct may execute in an
   explicitly labelled preview, but its result can never be resumed, replayed,
   admitted, promoted or used as certification evidence.

A diagnostic is a hard error only in the modes whose claim would make the
violated rule unsound. The same diagnostic may offer `authoring_preview` or a
typed durable rewrite as its next action, but never silently downgrade or
promote an execution.

### Durable LLM/tool and payload discipline

Every LLM/tool call policy binds prompt/template content and referenced-asset
digests, system/developer instructions, model/provider/profile and decoding or
tool-choice parameters, tool input/output schema versions and effect class,
token/cost/time/retry budgets with durable counters, cache/memoization policy,
output schema, and durable result identity. Replay consumes the recorded result;
a logical retry is a new declared attempt and cannot reset budget. Cache hits
are content-addressed by all behavior-relevant inputs, schema-validated,
provenance-journaled, and never authority. Cross-run caching must be explicit.

Checkpoint payloads inline only schema-versioned, size-bounded control values.
Large or unbounded plans, prompts, transcripts/results, task outputs, reviews,
and binaries use immutable artifact references with content digest, type/schema,
provenance, and retention/retrievability class. Missing, expired, mismatched, or
incompatible required artifacts take an explicit repair/migration/quarantine
path rather than silent recomputation. These rules reuse M11 facilities.

All state, checkpoint, artifact, effect-idempotency, and cache keys derive from
run identity plus semantic path and invocation/loop/item/retry/reentry
coordinates as applicable—not Python object identity, display labels, list
positions, or broad phase names.

## Reuse and non-duplication boundary

Native Parity reuses M11's accepted:

- Run Authority contracts, reducers, stores and decisions;
- WBC attempt/effect schema, transactional store/API, outbox/reconciliation,
  exact-version queries, producer registry, payload/version policy and receipts;
- Custody target/repair identity, lease history, action validator,
  controlled-writer registry, transfer/reclaim/recovery service;
- pure rebuildable projections and observation APIs;
- generic persistence, stale-fence/epoch, cross-host, installed-runtime,
  captured-replay, zero-bypass and conformance fixtures.

Native Parity may reuse an adapter only when it is downstream of a canonical
lowered node and cannot preserve a legacy route owner. This epic creates no
parallel grant/lease/attempt store, query facade, outbox, recovery loop,
projection, enforcement-promotion mechanism, or generic cross-contract proof
harness. Its additions are topology-specific authoring/lowering/runtime
binding, identity coordinates, producer relocation, carrier deletion, behavior
scenarios, and Native-specific conformance.

## Canonical machinery boundary

Canonical Megaplan executes by lowering `.pypeline` into the existing
DSL/manifest runtime. `build_pipeline()` must consume that lowered topology or
be replaced and quarantined. It may not filter detailed source nodes into
component IDs, overlay component metadata, rebuild routes, or drop dynamic
fanout/reducer policy.

The generic source compiler/lowerer/runtime must be product-neutral. It cannot
import Megaplan components or policies, literal-read Megaplan route dictionaries,
special-case the canonical path, or derive loop/route semantics from handlers.

These are downstream consumers only:

- components and retained pure handlers;
- compiled manifests and topology renderings;
- compatibility `Pipeline.native_program` shells;
- manifest backend and route-dispatch adapters;
- `_core` state/status views;
- CLI commands and auto-drive;
- WBC/status/watchdog/auditor projections.

During migration, compatibility is allowed only as an explicit, tested,
expiry-bound adapter. It cannot satisfy semantic evidence and cannot choose
behavior for a corrected slice.

## Eight busy two-week milestones

Every sprint has two independent closure gates:

- a **semantic gate** proving authored/lowered topology determines behavior;
- a **custody-adoption gate** proving actual authoritative actions use the
  admitted exact identities, fences, leases, WBC boundaries, and enforcement.

Passing one gate never implies the other.

Each milestone also emits a mandatory validation receipt into the deliberate
`final-proof-map.json` registry. A receipt binds command/tool version, exit
status, audited commit/tree, installed artifact where applicable, exact M11
admission-lock digest, semantic/identity/decision sets, runtime trace, and all
blocking subchecks. S7 must consume the complete registry; a prose claim that a
gate passed is not evidence.

The durable golden trace contract is also a mandatory proof-map input. Its
fixtures compare total order within occurrences and authority/custody/effect
causality, explicit partial order among parallel siblings, and multiset
occurrence/child equality from one run history. Sets and cross-run stitched
evidence cannot prove composition.

### S1 - Custody admission and semantic-preservation gate

Admit and pin M11. Build the normative identity/traceability model and a
fail-closed checker. Characterize the current 85-to-14 collapse, lost dynamic
fanout, handler/component/runtime route ownership, and false-pass proof.

Deliverables:

- validated prerequisite receipt and immutable version inventory;
- executable M11 capability-probe receipt covering three-plane writer
  registration, opaque executable/product digest binding, restore-durable
  decision consumption, exact-target fanout scale, WBC ambiguity/reconciliation,
  repair-failure classification and cross-host pin resolution;
- executable proof that decision consumption and terminal/arbitration CAS use a
  linearizable conditional operation enforced by the canonical production
  store/service. Application-level read/check/write, process-local locks and
  in-memory-store contention are negative fixtures, never release evidence;
- governed-registry capability probes covering versioned producer/query
  registration, comparison exclusion and registry evolution without silently
  changing the pinned M11 platform-contract identity;
- no-duplication dependency map;
- source-to-lowered-to-authority/WBC/custody/projection row schema;
- current-pattern and installed-package negative fixtures;
- source/lowering semantic set-equality and mutation tests;
- evidence schema that cannot begin from predeclared implemented rows;
- mandatory per-milestone receipt registry/proof-map schema, including decision
  ID/outcome/CAS fields, canonical store/service and adapter provenance, store
  incarnation/restore generation, and raw-history high-water cursor;
- retained old self-declared/hash-only ledger as a negative fixture that fails
  even after path/hash refresh;
- planned harness contract for the chain runner to pass `--proof-map`, the
  validator to consume every receipt, and the validation receipt to bind the
  proof-map hash before its own receipt is appended.
- executable ordered/partial-order and multiset golden-trace schema,
  independent static source-oracle contract, raw-event exporter contract,
  audit normalizer/comparator, same-run predicates, forbidden observations,
  mutation interface, and skeletons for `NP-GT-001` through `NP-GT-006`
  including A/B/C. S1 proves these against synthetic/raw mutations; production
  runtime integration is the first S2/GO-0 receipt;
- frozen authoring readability/edit-locality contract and six future-extension
  mutation specifications;
- machine-readable five-mode execution matrix and enforcement-disposition
  registry. Freeze mode identity/provenance, permitted authority/effect/
  checkpoint surfaces, diagnostic severity, and the prohibition on implicit
  downgrade or promotion. Add `NP-DX-001` through `NP-DX-004` skeletons for
  edited-step repeat, changed-code resume rejection, durable fork provenance,
  and unsupported-Python preview isolation;
- versioned deterministic-Python allow/deny contract and source-map/diagnostic
  contract with ambient-nondeterminism and opaque-routing negative fixtures;
- Plan Contract/generated-manifest non-authority rows and explicit action
  envelope schema;
- generated-manifest schema/version/hash evolution and mixed-worker
  compatibility contract. A worker that cannot prove support for the admitted
  manifest schema/hash fails before body/effect intent; serialization changes
  require an explicit compatibility or migration disposition;
- retained/resolvable pinned-artifact inventory and garbage-collection rule;
- checkpoint inline-versus-artifact classification, bounds, reference schema,
  and required artifact retention classes.
- named enclosing-loop exit and canonical decision-value contracts;
- immutable attempt-terminal/retry-generation/aggregate-child-terminal
  contract; cancellation-with-ambiguous-effect disposition; per-run migration
  application decision; repair rejection/redispatch classes; agentic final-call
  reserve; and duplicate-human-answer arbitration;
- canonical normalized product/Plan Contract digest and semantic-versus-
  presentation field classification;
- quarantined comparison namespace/provenance contract and per-cutover union-
  of-writers shared-validator proof schema;
- accepted M11 receipt for restore-resistant fences/epochs and canonical
  repair-request revalidation;
- diagnostic disposition registry and measurable author-task/trace-latency gate
  definitions.
- durable-record ownership/restore matrix. Decision consumption, loop ledgers,
  comparison provenance and proof registries must either be in the admitted
  restore boundary or carry their own restore-then-replay proof; Native may not
  create a side authority-consumption store.
- extraction-disposition field for every normative row, populated through S7
  as core primitive, stable reusable candidate, experimental candidate or
  Megaplan-specific behavior.

Semantic exit: current implementation fails because semantics are erased, not
because files or hashes are missing.

Adoption exit: M11 enforcement is active, all executable capability probes pass
and the four identity domains are separate; no local substitute substrate
exists. A missing capability exits only as `blocked_on_m11_point_release`.

### S2 - Generic authored control primitives bound to admitted APIs

Finish product-neutral typed decisions/outcomes, bounded loops, dynamic
map/reducer, per-item retry/fallback, deterministic child identity, human
suspend/resume, checkpoints, and call-site retry/timeout/model/effect policy.
Bind their runtime boundaries to M11's existing WBC and custody interfaces.
Every typed decision/terminal acceptance must map one-to-one to an accepted Run
Authority Decision consumed by the matching transition. Every
checkpoint/reentry binds program/topology, call-site-policy, and exact WBC
contract digests, with explicit migration/new-attempt/quarantine under drift.
Every Native authority-increasing dispatch, decision, transition, terminal, and
effect envelope validates those bindings plus installed artifact, dependency
lock, applicable prompt/tool identities, and normalized product-contract digest
before body/effect intent. The neutral reference includes one heterogeneous stale
worker rejected before action and emits ordered/multiset same-run trace proof.

Enforce the deterministic Python contract with source-local compiler diagnostics
and runtime guards. Ship an in-process authoring harness over the same production
lowerer and transition semantics, supporting typed fakes, recorded boundaries,
logical time/fault injection, fast-forwarded human input, and crash/reentry
traces without becoming a route engine or release proof. Make edit/repeat/fork
a first-class path: content-address working-tree code automatically, allow a
typed step/subworkflow fixture or recorded admitted boundary as immutable
input, start fresh experiment/run/attempt lineage in an isolated namespace,
and default every effect to fake or an explicit sandbox target with new
idempotency identity. Preserve source-run/boundary provenance without appending
to that run. An explicit `authoring_preview` may run unsupported Python through
a non-durable runner only when every result is marked non-resumable,
non-replayable, non-admissible and non-certifiable; it must not emit a durable
checkpoint or production-shaped success receipt. Bind LLM/tool prompt
content/assets, model/provider parameters, tool schemas/effect class, durable
budgets, cache policy, output schema, and recorded result; replay must not
silently call again. Enforce bounded inline checkpoints, content-addressed
artifact references, and run-plus-semantic-occurrence durable namespaces.
Implement named enclosing-loop typed exits, canonical decision serialization,
canonically keyed completion-order-independent reducers, frozen digest-bound
fanout bindings, declared typed phase errors, checkpointed typed reconfigure,
and—only if S1 proves a current consumer—the durable agentic-phase inner-call
protocol. Otherwise freeze that boundary and reject opaque inner loops with the
supported experimental-Platformization disposition. Reject open-ended streams
with a stable diagnostic and event-queue-port disposition.

Integrate S1's source oracle and raw-event audit comparator with the neutral
production runtime. Raw event IDs and multiplicity are checked before any
contract-approved volatile-field normalization; the production lowerer/runtime
adapter and audit verifier cannot share event-elision, deduplication or ordering
logic. Implement product-neutral entry adapters/guards for `arnold.execution`,
`NativeProgram`, and the retained runtime-envelope/legacy plane. Every live
writer is registered in M11's controlled-writer inventory and invokes the same
complete validator; adapters can serialize/validate an already selected action
but cannot select a route. GO-0 injects an unregistered writer and plane-local
validator bypass for each plane and rejects all before body/effect intent.

Before changing serialized topology, implement the S1 manifest evolution
contract and exercise old/new workers against old/new manifests. At GO-0, use
two independent clients through the production Run Authority adapter to
contend on every reference decision-consumption and terminal/arbitration key.
Force both release orders and crashes immediately before and after the
conditional write; exactly one acceptance may commit. The receipt binds the
concrete adapter, canonical store/service implementation and schema. An
application mutex, read/check/write sequence, or in-memory test double cannot
satisfy this proof. Any Native durable ledger/registry introduced here must
enter its admitted rollback boundary or pass its own restore-then-replay proof
in this milestone, not wait for S7.

The generic lifecycle distinguishes immutable execution-attempt terminals,
retry generations under one semantic child, and the one aggregate child
terminal consumed by its parent. It implements named-exit unwind terminals,
per-application migration decisions, declared cancellation-pending-
reconciliation obligations, typed repair validation classes, agentic budget
reserves and duplicate-human rejected-late evidence.

Semantic exit: a neutral reference pipeline preserves every source construct,
dynamic child, reducer, policy, and reentry through runtime; generic code has no
Megaplan coupling. Forbidden nondeterminism produces stable source-local
diagnostics, replay from identical recorded boundary results is trace-identical,
and local-harness traces normalize equivalently to installed execution without
weakening admission. `NP-DX-001` proves an edited step can be run repeatedly as
fresh experiments; `NP-DX-002` proves the same edit cannot silently resume an
admitted occurrence; `NP-DX-003` proves a durable fork retains immutable input
provenance but receives new authority/history/effect identity; `NP-DX-004`
proves unsupported preview code can run without acquiring any durable claim.

Adoption exit: enforce-mode crash/retry/idempotency/stale-fence/stale-epoch,
effect ambiguity, cancellation, transfer/reclaim, and resume tests pass using
M11 services. Decision/transition equality and program/policy/WBC-version drift
tests pass. The three-plane writer/bypass matrix and raw independent trace
comparison pass. Receipts/projections cannot grant actions.

### S3A - Prep, plan, and critique native cutover

Land the canonical execution-plane binding before the first source-authority
cut. Each migrated semantic scope binds one admitted execution plane in its
run/migration record and checkpoint. A pure shared selector reads that binding
and the pinned executable; it cannot choose the semantic cursor or fabricate a
migration. Every CLI/auto/native/legacy resume entry uses the same gate.

Migrate prep clarification, plan artifact boundaries, critique selection,
evaluator retry, dynamic lens fanout, per-item fallback and merge through source
lowering, `build_pipeline()`, runtime, current M11 validation, relocated WBC
producer identity, checkout, and clean installed execution. The current critique
evaluator is a bounded selector/model call, not evidence of a model-determined
durable inner tool loop. Do not claim a real Megaplan agentic consumer unless
the implementation inventory identifies one. S2 freezes the generic safety
contract and rejection fixtures at GO-0; runtime implementation and product
adoption are nonblocking and experimental until a concrete consumer exists.
Any such consumer must give
each effectful inner call its own exact Custody target and durable WBC effect
intent/outcome record.

Comparison runs use either M11's storage-enforced comparison class or a
physically/logically separate immutable artifact namespace with no RA grant,
Custody/effect client, admitted WBC/checkpoint/terminal writer, resume query or
promotion path. Separate credentials and bypass mutations prove isolation.

The outgoing bridge to the retained legacy gate is generated from a closed
typed boundary. The already accepted upstream decision names the downstream
entry; the bridge only serializes the immutable payload/action envelope and
records a compatibility handoff. It is a registered controlled writer when it
writes durable state, cannot compute `next_step`, and expires in S3B.

GO-1A proves source mutation changes the prefix trace, old-carrier mutation
does not, all concrete old/candidate writers cross the shared validator, exactly
one producer writes admitted history, comparison remains excluded, and legacy
cannot resume a native-bound scope (or vice versa). Failure leaves the old
prep/plan/critique producer authoritative, validator-registered and not yet
hard-fenced.

Semantic exit: prep/plan/critique are readable and load-bearing through the
critique join; child identities, attempt-terminal/retry-generation distinction,
fanout binding and keyed reducer are exact.

Adoption exit: GO-1A is green in checkout and clean installed execution before
the old prefix carriers are fenced.

### S3B - Gate, revise, and front-half cutover

Move gate signal construction, worker call, normalization, flag validation,
reprompt/downgrade, preflight/high-complexity/no-progress backstops, debt
effect, closed decision, revise and the bounded critique/gate/revise planning
cycle into canonical source. Establish the named outer `planning_cycle` and its
declared outcomes so later delivery `replan` exits have a real ancestor target.

Freeze one gate vocabulary shared by the decision annotation, return type,
lowering and exhaustive parent handling:
`proceed | iterate | tiebreaker | escalate | abort | blocked |
blocked_preflight | force_proceed`. After normalization and the one declared
reprompt, apply precedence in this order: agent-availability preflight;
cap/no-progress exhaustion; severity/high-complexity backstop; declared model
recommendation. At exhaustion, correctness/security blocking flags yield
`blocked` and cosmetic-only debt yields `force_proceed`; before exhaustion,
high-complexity unverifiable checks may yield `iterate`. No-progress means no
strict decrease in the canonical set of unresolved blocking flag identities
between admitted generations; display text, ordering and count alone cannot
reset it.

Relocate the remaining front-half WBC/action producers and delete or hard-fence
the corresponding component routes, handler route strings, manifest defaults,
`_core` routes, CLI translation and auto derivation. Remove the S3A gate bridge.
The outgoing typed bridge to retained legacy tiebreaker/finalize follows the
same serialize-only, registered-writer, mutation and expiry rules and is removed
by S4.

Make `NP-GT-001` and `NP-GT-002` green, including loop generation,
retry/fallback causality, parallel-sibling partial order, raw child/event
multiplicity, exact decision/custody/WBC joins and one aggregate child terminal
per semantic child. Derive the lowered-IR arbitration-site/participant set and
require equality with the versioned arbitration index and forced-race fixtures
for every front-half site.

GO-1B proves the entire front half source-authoritative with all old/candidate
writers registered behind the shared validator and one admitted decision
consumer/history writer. It closes GO-1. Failure blocks S4 but does not roll
back an already accepted GO-1A prefix cut; the still-legacy gate/revise slice
remains old-authoritative, validator-registered and not yet hard-fenced.

Semantic exit: source/installed split outcomes and old-carrier/bridge mutations
prove gate/revise behavior and outer-loop policy are load-bearing.

Adoption exit: GO-1B is green and all front-half nodes/children have exact
four-domain joins; handler-only instrumentation and comparison history are
insufficient.

### S4 - Tiebreaker, finalize, human decisions, and durable reentry

Author parallel researcher/challenger, synthesis, full tiebreaker decision
vocabulary, replan reset/rejoin, finalize fallback-to-revise, and scoped
re-finalization. Make every human gate a named suspension with exact reentry.
Make `NP-GT-003` green for clarification suspension, Host A/Host B custody, all
digest checks, and cross-host same-run resume.

Semantic exit: all tiebreaker/finalize routes are visible and legacy metadata
cannot alter behavior.

Adoption exit: kill/restart resumes at the exact semantic point only after an
accepted Run Authority decision and current fence plus reacquired/validated
exact Custody lease/epoch. Stale markers, approvals, fences, epochs, and WBC
success receipts cannot advance. Program/topology, call-site-policy, or WBC
contract drift uses the pinned original or an accepted typed
migration/new-attempt/quarantine path.

Exercise mixed suspended versions: create multiple v1 human suspensions, deploy
v2, and prove each run resolves its exact retained v1 executable/assets or takes
an accepted migration/new-attempt/quarantine path. Premature garbage collection
and silent continuation under v2 fail before product code.

Consume S3A's execution-plane binding/resume gate. Every compatible migration
application has its own accepted and once-consumed RA migration decision; a
standing compatibility rule is eligibility only. Human answer arbitration
accepts one distinct submission by CAS, treats an idempotent replay of the same
submission as the same fact, and durably records every different losing answer
as privacy-safe `human_answer.rejected_late` evidence with no route authority.
Force accepted-human-answer versus accepted-cancel contention, and two distinct
valid-answer contention, at the canonical CAS boundary through two independent
production-adapter clients in both release orders. Exactly one compatible
transition is accepted; the losing answer/cancel remains a durable typed loser
fact and cannot resume or rewrite terminal truth.

Remove the S3B tiebreaker/finalize bridge. The outgoing finalize-to-retained-
delivery bridge is generated from a closed typed handoff, registered when it
writes durable state, route-inert under mutation, and expires in S5.

### S5 - One reusable delivery cycle

Implement one authored:

```text
finalize -> approval -> dependency-ready dynamic batches
         -> review fanout/reducer -> bounded scoped rework -> finalize ...
```

Use task ID + batch identity + item path for children. Make parent/child WBC
attempt joins explicit. Acquire custody per exact task/effect target. Cover
approval, no-review, deferred-human, block/recovery, partial resume,
cancellation/fallback, review retry/caps, and scoped rework.

Prove namespace isolation across two sequential delivery generations,
same-kind fanout siblings, and concurrent runs with identical product task IDs.
State, checkpoints, artifacts, effect-idempotency keys, and caches may not
cross-read, overwrite, or deduplicate across those coordinates.

The review/rework cycle uses a named enclosing-loop typed exit for
`review_blocked -> replan`, not a sentinel or exception. Acceptance closes the
target `planning_cycle` ledger, records one `superseded_by_named_exit` control
terminal for every intervening durable scope in deterministic unwind order,
and lets the parent explicitly create a new planning-cycle instance at
generation zero with only declared digest-bound carry fields. Fanout children
consume one frozen admission binding; review reducers consume canonical keyed
results and remain invariant under completion-order permutations. GO-2 comparison
remains in the quarantined namespace and is never an admitted effect writer.

Cancellation defaults to waiting for effect ambiguity reconciliation. A site
may instead declare `cancelled_pending_reconciliation(obligation_id)`: this is
a child lifecycle terminal, never an effect terminal, and binds a mandatory
separately fenced reconciliation target. Late resolution updates effect history
and explanation but cannot rewrite the parent terminal; later compensation
requires a fresh typed decision. Remove the S4 finalize/delivery bridge and own
a route-inert delivery-to-legacy-control seam that expires in S6.

Before live effect authority cutover, require GO-2: execute one
production-shaped non-destructive/idempotent effect through checkout and clean
installed artifact, crash after durable outcome but before product receipt,
reconcile cross-host exactly once, and prove the old writer inert. Only dual-read
comparison is allowed; dual-write is forbidden. No old writer may be
disabled/fenced/deleted and no live cutover may occur until GO-2 is green. This
receipt makes `NP-GT-004` green; S5 also makes `NP-GT-005` scoped rework green.

Semantic exit: authored/runtime child sets and coordinates match; partial
failure reruns only incomplete children; one loop replaces duplicated passes.

Adoption exit: current independent fence and epoch guard every action/effect;
cross-host transfer/reclaim and crash around effect intent/outcome never
duplicate accepted effects; verify-only adoption matches revision, task
contract, tree/tests, semantic target, fence, and epoch.

### S6 - Override, recovery, auto-drive, and projection adoption

Author abort, force-proceed, replan, all resume/recover forms, adoption,
cancellation, halt, publication, delivery, configuration-effect reentry, and
typed effect-only `add-note`/supported annotation actions with exact target,
durable WBC effect history, and explicit `no_route_change` outcome.
Reduce auto-drive to event consumption/scheduling requests and adopt M11's
exact-version queries and rebuildable projections as observation only.

The scheduler allowlist is mechanical: after topology and an accepted decision
select an immutable typed action, auto-drive may choose only eligible host,
queue, and dispatch/wakeup time. It cannot create or reinterpret an outcome,
retry generation, escalation, cap/cost/stall transition, model/config change,
resume, or terminal.

Repair-request fields and projection-derived failed preconditions are untrusted
hints. Acceptance re-resolves canonical journals and current RA/Custody/WBC and
reruns every precondition through M11; the action validator runs again
immediately before work. Configuration changes use the typed reconfigure
transition and cannot mutate ambient context or live flags.

Pre-work validation classifies rejection. Actor-local stale worker/lease/epoch
or placement failure leaves a still-valid, unconsumed immutable decision
eligible for M11-controlled reassignment/redispatch. Canonical semantic
precondition, capability, executable/product/WBC drift or decision-validity
failure atomically records `decision.invalidated` and requires a new request and
decision. Once consumed or after body/effect intent, the decision is never
redispatched; continuation uses the authored retry/recovery/reconciliation
protocol. Scheduler code cannot choose the class.

Author a closed cancel/publish/deliver/terminal arbitration with explicit CAS
preconditions, mutual exclusion, preserved completed-effect history, precedence,
and rejection outcomes. Make `NP-GT-006A` cancel-before-publish,
`NP-GT-006B` publish-outcome-before-cancel/pre-delivery, and `NP-GT-006C`
delivery/done-before-late-cancel green. Wall-clock or projection order cannot
pick a winner.

The arbitration role, semantic key and accepting Run Authority identity are
stable contract fields so future root-host extraction cannot silently replace
the terminal arbiter or create a second acceptance domain. A Stage-2 root host
may adapt a closed result only by consuming this same accepted identity.

Mechanically derive every control-cutover CAS/arbitration site and participant
transition family from lowered IR. Require exact equality with the versioned
arbitration-policy index, then force each participant pair to the pre-CAS
boundary and release both legal orders. The accepted truth must match while all
loser/rejected-late facts remain in raw history.

Build a Native composed-history explanation and repair preflight solely from
admitted M11 queries. It joins semantic occurrence/retry/reentry, exact
accepted/consumed decisions, historical/current fences and epochs, WBC
attempt/effect ambiguity, pinned/current executable digests, terminal
arbitration, and request-only legal repairs/failed preconditions. It is
rebuildable, observational, request-only, and behaviorally inert.

Semantic exit: source owns every action/reentry and auto/CLI/component/runtime
mutations cannot alter product routes.
Specifically, `_core/workflow_data.py:WORKFLOW` and
`_ROBUSTNESS_OVERRIDES` are inert/hard-fenced or deleted; mutations across every
supported robustness level cannot change a normalized trace, and no runtime,
auto, or CLI entry point reads them as route or live-policy authority.

Adoption exit: all positive actions use M11's existing action/recovery boundary;
forged/stale but internally consistent projections and receipts cannot cause
dispatch, resume, retry, completion, cancellation, publication, or delivery.
The S5 delivery/control seam is removed and no control bridge remains.

### S7 - Native-topology conformance on the M11 proof framework

Extend M11's generated proof model with Native-specific set equality across
source, lowering, producer registry, runtime attempts/actions, semantic
checkpoint/reentry coordinates, and projection consumers, plus exact equality
between authored decision occurrences, accepted Run Authority decisions, and
consumed runtime transitions/actions. Reuse all generic M11 fixtures and add
only topology mutations and end-to-end compositions.

Run checkout, clean wheel/sdist, and pinned cloud runtime. Generate the final
proof map deliberately from accepted artifacts. The chain's schema-supported
`final_conformance_gate` is blocking and its receipt becomes completion proof.
S7 lands the S1-planned harness plumbing: the runner passes the declared
`final-proof-map.json` to the validator; the validator consumes the complete
per-milestone receipt registry and rejects missing, extra, unknown, unconsumed,
stale, non-executed, non-commit-bound, or red records; and the receipt records
the proof-map hash before appending itself. A refreshed old ledger/evidence
bundle remains a mandatory failing fixture.

Export raw primary-store events and prove raw event-ID/multiplicity equality
before normalization. Run an audit normalizer/verifier with disjoint code
provenance from production lowering/runtime trace adaptation; the golden
contract's versioned volatile-field allowlist is the only permitted elision and
unknown fields reject. Derive the lowered-IR arbitration-site/participant set
and require exact equality with every owning-cutover policy/forced-race receipt.
Every owning cutover receipt also joins each consumption/arbitration site to the
certified linearizable canonical store/service operation and records the exact
production adapter/store provenance. Serialized or in-memory race fixtures are
insufficient.

Consume the durable-record ownership/restore matrix for every Native-added
ledger, decision-consumption join, comparison registry and proof registry.
Each record is either inside M11's admitted rollback-resistant transaction
boundary or passes its own restore-then-replay mutation. No Native side
authority-consumption store can satisfy completion.
The corresponding restore proof must already have passed when the record was
introduced or first made authoritative; S7 verifies and consumes that receipt
rather than deferring safety until final conformance. Each registered receipt
binds the canonical store incarnation/restore generation and raw-history
high-water cursor, preventing a restored or truncated registry from satisfying
the final proof with an old acceptance.

Run all six golden families and mandatory mutations against checkout,
wheel/sdist, and cloud using one composed history per run. Run the six
future-extension mutations—gate outcome, dynamic review lens, retry policy,
human decision, override, external effect—and fail handler/auto/metadata-only
bypasses. Enforce the structural authoring/readability/edit-locality contract
with reviewed complexity exceptions. Run and rebuild the Native composed
explanation/preflight for every family and prove it inert.

Also run deterministic-subset and source-diagnostic mutations; local-versus-
installed normalized-trace equivalence; prompt/tool/schema/budget/cache/replay
mutations; checkpoint payload/reference mutations; pinned-version retention/GC
tests; namespace-isolation tests; and Plan Contract/generated-manifest
non-authority mutations.

Run the complete S1 execution-mode matrix through every public runner. Repeat a
working-tree-edited step from the same recorded input and require effortless
success under fresh experiment identities; attempt to relabel or resume either
result as the old admitted occurrence and fail before body/effect intent. Fork
an admitted boundary into `durable_sandbox` and prove immutable source
provenance plus new RA/WBC/Custody/history and sandbox-only effect/idempotency
keys. Run unsupported Python in `authoring_preview`, then prove that checkpoint,
replay, comparison promotion, admission and certification consumers all reject
it. Prove comparison remains quarantined and non-authoritative even when its
candidate digest equals a later admitted digest. Diagnostic severities must
match the frozen enforcement disposition: advisory locally where appropriate,
blocking at the applicable production-admission or stable-publication gate,
and always hard for
authority, effect, namespace, history and provenance safety.

Require every golden family including NP-GT-006A/B/C—not a selected subset—to
match local and installed normalized lifecycle/admission traces under the same
recorded boundaries within declared virtual-time and wall-latency budgets.
Require every route divergence to be attributable to a declared outcome or
decision value; mutate undeclared payload fields to prove they cannot route.
Require zero diagnostic codes without either a supported primitive/example or
explicit deliberate-non-support boundary recipe, and pass a timed ten-task
author simulation as a blocking readability receipt.

Emit a content-addressed Native-to-Platformization handoff manifest containing
the reusable-candidate/dependency inventory, exact typed port/outcome/policy/
effect snapshots, source-to-runtime golden adapters, zero-Megaplan-import proof
for generic primitives, coupling evidence, exclusions and the executed
classification rationale. Platformization consumes this manifest; S7 does not
extract or stabilize product patterns.

Semantic exit: the smallest readable `.pypeline` fully determines actual
behavior and zero hidden route authority remains.

All temporary typed seam bridges are removed or structurally incapable of
routing; mutating any retained serializer/projection cannot change a trace.

Adoption exit: every authoritative action is enforce-mode covered by current
grant/fence and exact lease/epoch plus applicable exact-version WBC evidence;
the pinned M11 receipt remains necessary but cannot substitute for Native
topology proof.

## Migration graph and binary stop/go receipts

```text
accepted M11
  -> S1 capability probes + proof/source-oracle schema + admission lock
  -> S2 generic primitives + three-plane adapters + neutral composed trace
  -> GO-0 raw/normalized/decision/digest/writer-bypass receipt
  -> S3A prep/plan/critique + execution-plane binding + typed seam
  -> GO-1A prefix source-load-bearing/installed/adoption receipt
  -> S3B gate/revise/planning-cycle + front-half carrier hard fence
  -> GO-1B complete front-half receipt (closes GO-1)
  -> S4 tiebreaker/finalize/human reentry + NP-GT-003
  -> S5 delivery cycle shadow/dry-run + exact effect binding
  -> GO-2 production-shaped effect/crash/cross-host exactly-once receipt
  -> S5 live delivery cutover + legacy-writer fence
  -> S6 control arbitration + NP-GT-006A/B/C
  -> GO-3 stale-worker/race/projection-forgery receipt
  -> S6 auto/CLI/status/projections demoted to request/observation
  -> S7 remaining deletion + checkout/wheel/cloud composed proof
  -> GO-4 complete proof-map/golden/readability/explainer receipt
```

Binary rules:

- GO-0 failure blocks product migration.
- GO-1A failure keeps the old prep/plan/critique producer authoritative,
  validator-registered and not yet hard-fenced. After GO-1A passes its cut is
  not rolled back by GO-1B failure.
- GO-1B failure keeps the still-legacy gate/revise producer authoritative,
  blocks S4 and prevents a complete front-half claim. GO-1 means both receipts.
- GO-2 failure blocks live effect cutover and old-writer disable/fence/delete;
  external effects are never dual-written.
- GO-3 failure blocks old control-consumer demotion and heterogeneous rollout.
- GO-4 failure blocks epic completion.

At each cutover: land/test the authored producer and generated bindings; permit
only behaviorally inert dual-read comparison; relocate the WBC/action producer;
cut authority once at the receipt; move consumers; prove the old producer inert;
then hard-fence/delete after installed and cross-host proof.

Every partial cut owns one closed typed outgoing seam. The accepted upstream
decision already names the downstream entry; the seam serializes only and is a
registered writer when durable. S3A's seam expires in S3B, S3B's in S4, S4's in
S5 and S5's in S6. S7 proves zero route-capable seam remains.

Comparison execution uses either M11's storage-enforced digest-bound
`authority_class=comparison` or an immutable isolated comparison-artifact
namespace with no RA grant, Custody/effect client or admitted writer. It is
non-authoritative, non-resumable and non-effect-capable. Admitted RA/WBC/
Custody/checkpoint/effect/terminal queries, projections, resume selectors and
decision consumers exclude it by construction. Comparison history may be read
only by the explicit comparison view and is never relabeled or promoted.

For every cutover, the union of old and candidate action/effect-capable paths
across `arnold.execution`, native runtime and legacy runtime-envelope planes is
registered in M11's controlled-writer inventory and crosses the same validator
in enforce mode. Exactly one producer may consume an accepted decision or write
admitted history. Unregistered old, candidate, or comparison paths fail before
body/effect intent.
Every decision-consumption/arbitration site additionally binds to a certified
linearizable conditional operation at the canonical production store/service.
Application read/check/write and process-local exclusion do not establish the
one-winner invariant.

## Normative semantic matrix

The aspirational Python in
`docs/arnold/megaplan-native-representation-report.md` is illustrative syntax,
not a demand for maximum granularity. This plan's machine-readable traceability
matrix is normative. For each product semantic it declares:

- required authored construct and typed vocabulary;
- routes and terminal outcomes;
- loop entry, exits, cap/no-progress/severity behavior;
- named enclosing-loop exit target and exhaustive parent handling;
- loop-instance ledger closure, intermediate-scope unwind terminals, explicit
  new-instance reentry and declared carry payload;
- fanout collection, item schema, worker cap, per-item retry/fallback, reducer,
  deterministic naming and child coordinates;
- canonical decision-input schema/digest, frozen fanout binding digest, and
  canonical reducer-key contract;
- suspension capability, WBC lineage, exact reentry and lease lifecycle;
- execution-plane binding, outgoing typed seam owner/expiry and bridge
  mutation-inertness;
- program/topology digest, call-site-policy digest, exact WBC contract version,
  normalized product/Plan Contract digest, and explicit drift disposition;
- retry/timeout/model/fallback/effect policy attachment;
- deterministic-subset classification and authored source-map/diagnostic codes;
- prompt/model/tool/schema/budget/cache and durable-result bindings;
- declared phase error outcomes, agentic inner-call protocol, and typed
  reconfiguration delta/reentry;
- checkpoint inline/reference classification, bound, artifact digest/schema,
  provenance, and retention class;
- run/semantic-occurrence namespace derivation for state, artifacts, effects,
  and caches;
- semantic node/child identity and the three external identity joins;
- execution-attempt terminal, retry generation and aggregate child-terminal
  identity/consumption;
- accepted Run Authority decision ID/outcome/CAS sequence and consumed runtime
  transition/action for each typed decision occurrence or terminal acceptance;
- required positive, split-outcome, restart and negative-mutation scenarios;
- legacy carriers that must be deleted or hard-fenced;
- applicable M11 generic fixture and any Native-only proof extension;
- lowered-IR arbitration-site/participant identity and policy/forced-race
  coverage;
- golden scenario/occurrence coordinates, required same-run order/partial-order,
  multiplicity, forbidden observations, and mutations;
- readability/edit-locality implications and generated-binding ownership.
- extraction disposition and Platformization handoff dependency.

At minimum the matrix covers prep, plan, critique, gate, revise, tiebreaker,
finalize, execute, review, rework, override/configuration, human gates,
robustness variants, installed runtime, and observation/projections.

## Row evidence contract

Every implemented row has generated evidence containing:

- row ID and required semantic distinction;
- carrier type and source file/span or attached policy;
- authored and lowered semantic identities;
- Run Authority subject attempt/fence mapping;
- accepted Run Authority decision ID, outcome, CAS sequence, and exactly one
  consumed matching transition/action where applicable;
- WBC execution attempt and exact contract version mapping;
- Custody target/owner/lease epoch mapping;
- executable proof test and split-outcome runtime trace;
- negative mutation/dead-delete proof;
- checkout commit/tree and installed artifact provenance;
- content hashes bound to those semantic records;
- per-milestone validation receipt and proof-map membership/consumption status;
- golden trace contract version, scenario ID, one-run history identity,
  normalized ordered/partial-order and multiset comparison receipt;
- executable digest-binding and heterogeneous-worker outcome;
- deterministic replay/diagnostic, local-harness equivalence, LLM/tool result,
  checkpoint-payload, pinned-resolution, and namespace-isolation receipts;
- applicable GO-0 through GO-4 receipt and composed explanation/preflight
  receipt.

Unacceptable evidence includes component constants, handler refs, route
bindings, metadata topology, trace-only fixtures, path existence, whole-file
hashes, report prose, prior status, support labels, shadow guards, compatibility
projections, WBC receipts, or status projections used alone.

The generator must derive row status from executed proof. It must not iterate
rows already labeled implemented and manufacture support records. Every
compatibility, purity, deletion, coupling, installed-runtime, zero-bypass, and
identity failure participates in the blocking result; auxiliary red checks
cannot coexist with a passing report.

The final validator consumes the declared proof map as an input, not merely as
a file checked by the runner. Its receipt binds the proof-map hash before that
receipt is appended. The retained legacy ledger/evidence bundle must remain
negative even when its old paths and hashes are refreshed.

## Minimum blocking regressions

1. Source-to-lowered graph preserves every semantic node, decision, bounded
   loop, dynamic fanout/reducer, call-site policy, and reentry edge.
2. Authored/lowered node identity, WBC producer registry, and actual runtime
   node/child attempts have generated set equality.
3. Every authored typed decision occurrence/terminal acceptance maps to exactly
   one accepted Run Authority decision and exactly one consumed matching runtime
   transition/action; orphan, duplicate, stale-fence, unaccepted, inferred, and
   outcome-mismatched cases fail.
4. Every authority-increasing Native action demonstrably passes through M11's
   admitted validator; missing/stale grant, fence, lease, epoch, target, or
   required boundary evidence fails closed.
5. WBC evidence/receipt/projection cannot become dispatch, resume, retry,
   completion, cancellation, publication, or delivery authority.
6. Every node/child maps to the admitted WBC lifecycle with idempotency,
   monotonic order, terminal uniqueness, ambiguity and reconciliation.
7. Fanout child identity includes semantic item/task, batch, and path
   coordinates rather than list position alone.
8. Suspension survives process death and resumes at the same semantic point
   only with current authority/custody and matching program/topology,
   call-site-policy, and exact WBC contract version, or an explicit accepted
   drift decision.
9. Fanout/resume identity survives M11's cross-host transfer/reclaim path.
10. Handler/component/runtime/`_core`/CLI/auto route mutation cannot alter
   canonical behavior.
11. Projection deletion/rebuild is deterministic and forged/stale projections
    cannot increase authority.
12. Checkout, wheel/sdist, and pinned cloud runtime produce the same topology,
    WBC history, identity joins, and decisions.
13. Native completion consumes the exact M11 manifest/conformance receipt and
    adds source/lowering/runtime topology proof; neither can be replaced by
    auto-publish, status, support manifest, or hashes.
14. The final validator consumes the complete declared proof map, binds its
    pre-receipt hash, and rejects a refreshed version of the old false-pass
    ledger/evidence bundle.
15. `NP-GT-001` through `NP-GT-006` including A/B/C preserve same-run total and
    partial order, multiset occurrence/child equality, all identity joins,
    effects, checkpoints, and exactly one terminal across checkout/wheel/cloud.
16. Every Native authority-increasing dispatch/decision/transition/terminal/
    effect envelope validates program/topology, call-site-policy, exact WBC,
    installed-artifact, dependency-lock, applicable prompt/tool, and normalized
    product-contract digests; a heterogeneous stale worker is rejected before
    body/effect intent.
17. GO-2 proves one production-shaped non-destructive/idempotent effect,
    outcome-before-receipt crash, cross-host exactly-once reconciliation, old
    writer inertness, and no dual-write interval before live cutover.
18. Closed cancel/publish/deliver/terminal CAS arbitration passes all three race
    variants and rejects conflicting terminal truth. The CAS is a linearizable
    conditional operation enforced by the canonical production store/service
    and passes two-independent-client contention/crash testing through the
    production adapter; application read/check/write or local locks fail.
19. Six future-extension mutations succeed from the Python topology/local
    policy/effect vocabulary with mechanical regeneration and fail from
    handler/auto/metadata-only additions; structural readability/edit locality
    and reviewed complexity exceptions pass.
20. The Native composed-history explanation and repair preflight answer causal
    and legal-request questions for every golden run solely from admitted M11
    queries; deletion/rebuild is deterministic and behaviorally inert.
21. Forbidden ambient nondeterminism and opaque product routing fail with stable
    authored source diagnostics; replay with the same recorded boundary results
    produces the same semantic, decision, and checkpoint trace.
22. LLM/tool prompt content, parameters, schemas, durable budgets, cache policy,
    and result identity are bound; replay never duplicates a completed call or
    resets retry budget, and forged cache entries fail.
23. Checkpoints reject oversized inline payloads and mutable, missing, expired,
    digest-mismatched, or schema-incompatible artifact references.
24. Nonterminal suspended runs retain exact resolvable executable/assets; a v1
    run cannot silently resume on v2 or lose its pinned artifacts to GC.
25. Repeated delivery generations, same-kind siblings, and concurrent runs with
    identical product IDs have isolated state/checkpoint/artifact/effect/cache
    namespaces.
26. Plan Contract and generated manifest/lock metadata cannot add a route or
    satisfy action authority.
27. Named enclosing-loop exits, canonical decision values, frozen fanout
    bindings, keyed reducers, and declared typed phase errors pass their
    sentinel/exception/order/context mutations.
28. Typed reconfiguration checkpoints a canonical delta and reenters the same
    cursor; ambient config/live flags cannot change control flow.
29. A declared agentic phase journals all variable inner model/tool calls and
    effects under its WBC protocol but cannot return an outer route hint.
30. Product/Plan Contract semantic edits cause pinned drift; presentation-only
    edits do not, and `pre_existing` cannot waive evidence mid-run.
31. Comparison history is quarantined/non-promotable, and every old/candidate
    live plane is registered behind one shared validator with one admitted
    writer per cutover.
32. Restore-resistant M11 fence/epoch and repair-revalidation receipts are
    consumed; no Megaplan-local substitute can pass.
33. Payload-route attribution, zero undispositioned diagnostics, timed author
    tasks, and every-family local/installed trace/latency equivalence pass.
34. Named exits close the target ledger, record every intermediate unwind
    terminal exactly once and reenter only as an explicit new loop instance.
35. Attempt terminals, retry generations and aggregate child terminals preserve
    their separate cardinalities; effect outcomes are reused and ambiguity is
    reconciled or bound to a declared cancellation obligation.
36. Each migration application consumes its own accepted decision; distinct
    late human answers are retained but cannot route; agentic calls cannot
    exceed admitted budget/reserve.
37. Repair validation distinguishes redispatchable actor-local rejection from
    decision-invalidating semantic drift and never reuses a consumed decision.
38. Raw-event multiplicity survives an independently implemented verifier, and
    lowered-IR arbitration-site/participant equality covers every cutover race.
39. Every Native durable record has restore ownership/proof, every partial-cut
    seam is expired, and the content-addressed Platformization handoff manifest
    is complete.
40. Governed producer/query registry evolution, manifest schema/hash evolution,
    mixed-worker rejection, receipt store-incarnation/high-water binding, and
    accepted-answer/cancel contention pass without introducing a second
    authority or proof domain.
41. Execution-mode fixtures prove working-tree edit/repeat and durable fork are
    easy fresh experiments, while changed-code resume, production effect/
    idempotency reuse, history append, preview promotion, comparison promotion,
    and diagnostic-mode downgrade all fail. Every restriction has one frozen
    `always_hard`, `automatic`, `production_admission_gate`,
    `stable_publication_gate`, `authoring_advisory`, or `non_durable_only`
    disposition.

## Required final gates

The epic is incomplete unless all are true:

1. M11 prerequisite manifest/proof map and exact installed revision validate.
2. `workflow.pypeline` and named subworkflows are the only product-topology
   authority.
3. Lowering preserves the complete semantic set and is runtime-load-bearing.
4. Generic compiler/runtime code has no Megaplan semantic coupling.
5. Components and retained handlers are pure interfaces/bodies; transitive
   route ownership is absent.
6. Compatibility, manifests, `_core`, CLI, auto, WBC queries, and projections
   are downstream consumers only.
7. Four identity domains remain distinct and completely mapped.
8. Decision-occurrence/accepted-decision/consumed-transition set equality holds.
9. Every authority-increasing action envelope, including checkpoint/reentry,
   binds program/topology, policy, exact WBC contract, installed artifact,
   dependency lock, and applicable prompt/tool identities and handles
   heterogeneous drift explicitly.
10. Every authoritative action uses current independent fence and epoch;
   evidence is never authority.
11. Every row has generated executable semantic, mutation, behavior, identity,
   and provenance proof.
12. Full split-outcome, restart/resume, partial failure, cross-host, effect
    ambiguity, installed-package, and cloud scenarios pass.
13. The final validator consumes the complete proof map; its pre-receipt hash,
    all per-milestone receipts, and every blocking subcheck pass at the landed
    commit. The refreshed old ledger remains failing.
14. A reviewer can understand the entire product flow from canonical source
    without hidden carrier archaeology.
15. The durable golden trace contract is a consumed proof-map input, never a
    route authority, and all six scenario families/mutations pass from one
    composed history in checkout/wheel/cloud.
16. GO-0, GO-1A, GO-1B, GO-2, GO-3 and GO-4 are green; live external effects
    were never dual-written and no deletion/cutover crossed a failed binary
    boundary.
17. Cancel/publish/deliver/terminal arbitration has one closed authored CAS
    contract and one accepted terminal truth, backed by the certified
    linearizable production persistence operation rather than an application
    critical section.
18. The one-topology, one-delivery-cycle, small-primitive, generated-binding,
    local-policy, closed-vocabulary, readability/edit-locality contract passes
    six future-extension tests with reviewed exceptions.
19. The rebuildable Native composed explanation/preflight is causally complete,
    observational/request-only, and behaviorally inert.
20. The deterministic Python fence, source-local diagnostics, and production-
    lowerer local harness pass without introducing a second route engine.
21. LLM/tool replay identity and durable budgets, bounded checkpoint payloads,
    pinned-version retention, and durable namespace isolation pass their
    blocking mutations across installed and cloud execution.
22. Addressed exits, canonical decisions, keyed reducers, frozen fanout,
    declared errors, typed reconfiguration, and agentic-phase protocol pass.
23. Product-contract pinning, comparison provenance, all-plane one-writer proof,
    scheduler allowlist, repair revalidation, concrete legacy-table inertness,
    and measurable ergonomics receipts all pass.
24. Independent source-oracle/raw-event proof, arbitration-site equality,
    restore ownership, typed seam expiry and the Native-to-Platformization
    handoff manifest all pass without becoming runtime authority.
25. Registry and manifest evolution, mixed-worker compatibility, proof-receipt
    incarnation/high-water binding, and root-arbitration identity stability are
    explicit, versioned and mutation-tested.

Any deliberate narrowing needs both a checker rule that blocks the original
false-pass pattern and behavior/identity proof that the chosen abstraction
preserves the omitted syntax's semantics.

## Closure anti-patterns

Reject these even when imports or reports are green:

1. **Semantic erasure:** detailed source lowers, then a builder reconstructs a
   coarser component graph.
2. **Indirect wrapper:** benign callable aliases resolve to component carriers
   or handler route ownership.
3. **Policy route table:** topology, targets, fanout contracts, or override
   dispatch hide in attached metadata.
4. **Handler-return routing:** runtime converts `next_step`, `current_state`,
   `route_signal`, verdict, or recommendation strings into routes.
5. **Wrong-boundary WBC:** instrumentation proves `handle_review()` ran but not
   the authored review children/reducer/loop.
6. **Identity collapse:** one attempt ID stands in for semantic invocation,
   subject attempt, WBC attempt, and custody lease.
7. **Evidence as authority:** receipt/projection/history triggers or skips an
   action.
8. **Shadow as enforcement:** default-off guard passes are counted as adoption.
9. **Projected-native proof:** compatibility native programs/CLI dispatch count
   as source-authoritative execution.
10. **Receipt substitution:** generated report, topology snapshot, or whole-file
    hash replaces runtime semantic proof.
11. **Installed drift:** checkout passes while wheel/sdist/cloud executes a
    different graph or control-plane version.
12. **Happy-path parity:** uncommon split outcomes, restart, ambiguity,
    cancellation, transfer, and stale-identity cases are absent.
13. **Cross-run trace stitching:** row-local traces from different executions
    are combined instead of proving one ordered/multiset composed history.
14. **Fixture authority:** a golden fixture, explainer, or repair projection is
    read to choose a route or authorize an action.
15. **Heterogeneous blind spot:** homogeneous checkout/wheel/cloud parity passes
    while a stale installed worker can execute under current fences.
16. **Live migration experiment:** old and new external-effect writers overlap,
    or cutover/deletion precedes GO-2.
17. **Terminal race ambiguity:** individually valid cancel/publish/deliver/done
    paths lack one authored CAS/precedence contract.
18. **Authoring ceremony regression:** a normal extension needs manually
    synchronized handler/auto/metadata routes or identity/control registries.

## Chain-schema enforcement and limitation

The current chain schema can enforce:

- launch-time completed-chain manifest validation;
- serial dependency assertions;
- a blocking final-milestone `final_conformance_gate` with content-addressed
  receipt inclusion in proof evidence.

`prerequisite_policy: required` and `validation_policy: required` are metadata
used for plan/status classification; they do not create or strengthen gates.
The explicit `launch_preconditions` entries and final milestone `validate`
entry carry enforcement. S1/S7 must add a loader invariant or chain-schema test
that a `required` metadata policy has at least one corresponding explicit
precondition/validation, so the metadata cannot falsely imply coverage.

It cannot declare arbitrary executable validation commands after every
milestone; `validate` currently supports only `final_conformance_gate` and only
on the final milestone. Therefore each sprint's semantic and custody-adoption
gates are mandatory brief acceptance criteria backed by tests/proof artifacts,
while S7 replays them all through the single schema-supported blocking final
gate. Adding generic per-milestone validators is useful harness follow-up but is
not required for this epic. This epic does require bounded existing-path
harness work: pass `--proof-map <validation.proof_map>` from the chain runner,
add the validator argument and full-map consumption, and bind/check the
pre-receipt proof-map hash. Those are planned S1/S7 deliverables, not runtime
changes made by this plan revision.

## Non-goals

- Reimplementing or repairing pre-M11 Run Authority, Custody, WBC, recovery,
  projection, query, or generic conformance infrastructure.
- Treating custody evidence around legacy handlers as native parity.
- Maximizing source step count or copying the aspirational report literally.
- Deleting every handler or string used only at serialization boundaries.
- True concurrent DAG optimization when deterministic dynamic batching,
  cancellation/fallback, and exact identity are correctly represented.
- Arbitrary-Python semantic checking; unsupported source may fail closed.
- Graph visualization UI, multi-region execution, or unrelated fleet growth.

## Definition of done

The end-state report, normative matrix, canonical source, lowering/runtime,
Run Authority decisions, Custody lease history, WBC attempt/effect history,
durable golden same-run traces, generated traceability/conformance evidence,
installed artifacts, cloud execution, and rebuildable Native causal explanation
independently prove the same composed fact:

**Megaplan's canonical native source completely determines product behavior;
Run Authority determines permission; Custody determines exclusive current
ownership; WBC durably proves the exact attempt and effects; projections only
explain.**

If any implemented claim lacks executable semantic and identity proof, or any
receipt/projection is required as authority, the row is not implemented.
