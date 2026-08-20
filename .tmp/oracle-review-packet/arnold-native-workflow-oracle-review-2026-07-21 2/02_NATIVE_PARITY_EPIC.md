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

Intermediate M8/M9 receipts, dirty or divergent branches, shadow/default-off
guards, support manifests, status labels, and auto-publish commits do not
satisfy admission. Native Parity consumes only the accepted M11 surface.

If the prerequisite manifest is stale, incomplete, or mismatched, this chain
does not start. Native Parity does not repair or locally emulate missing M11
scope.

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
It is generated from or checked against the authored Python topology. It
freezes observable ordering, multiplicity, causality, identities, effects,
reentry, and terminals for named scenarios without becoming a second workflow
model. Neither fixtures nor normalized traces may route, authorize, resume, or
repair runtime.

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
  no sentinel or exception route smuggling;
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
  authority over the next outer product route.

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

## Seven busy two-week sprints

Every sprint has two independent closure gates:

- a **semantic gate** proving authored/lowered topology determines behavior;
- a **custody-adoption gate** proving actual authoritative actions use the
  admitted exact identities, fences, leases, WBC boundaries, and enforcement.

Passing one gate never implies the other.

Each sprint also emits a mandatory validation receipt into the deliberate
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
- no-duplication dependency map;
- source-to-lowered-to-authority/WBC/custody/projection row schema;
- current-pattern and installed-package negative fixtures;
- source/lowering semantic set-equality and mutation tests;
- evidence schema that cannot begin from predeclared implemented rows;
- mandatory per-sprint receipt registry/proof-map schema, including decision
  ID/outcome/CAS fields;
- retained old self-declared/hash-only ledger as a negative fixture that fails
  even after path/hash refresh;
- planned harness contract for the chain runner to pass `--proof-map`, the
  validator to consume every receipt, and the validation receipt to bind the
  proof-map hash before its own receipt is appended.
- executable ordered/partial-order and multiset golden-trace schema, normalizer,
  same-run predicates, forbidden observations, mutation interface, and skeletons
  for `NP-GT-001` through `NP-GT-006` including A/B/C;
- frozen authoring readability/edit-locality contract and six future-extension
  mutation specifications;
- versioned deterministic-Python allow/deny contract and source-map/diagnostic
  contract with ambient-nondeterminism and opaque-routing negative fixtures;
- Plan Contract/generated-manifest non-authority rows and explicit action
  envelope schema;
- retained/resolvable pinned-artifact inventory and garbage-collection rule;
- checkpoint inline-versus-artifact classification, bounds, reference schema,
  and required artifact retention classes.
- named enclosing-loop exit and canonical decision-value contracts;
- canonical normalized product/Plan Contract digest and semantic-versus-
  presentation field classification;
- quarantined comparison namespace/provenance contract and per-cutover union-
  of-writers shared-validator proof schema;
- accepted M11 receipt for restore-resistant fences/epochs and canonical
  repair-request revalidation;
- diagnostic disposition registry and measurable author-task/trace-latency gate
  definitions.

Semantic exit: current implementation fails because semantics are erased, not
because files or hashes are missing.

Adoption exit: M11 enforcement is active and the four identity domains are
separate; no local substitute substrate exists.

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
traces without becoming a route engine or release proof. Bind LLM/tool prompt
content/assets, model/provider parameters, tool schemas/effect class, durable
budgets, cache policy, output schema, and recorded result; replay must not
silently call again. Enforce bounded inline checkpoints, content-addressed
artifact references, and run-plus-semantic-occurrence durable namespaces.
Implement named enclosing-loop typed exits, canonical decision serialization,
canonically keyed completion-order-independent reducers, frozen digest-bound
fanout bindings, declared typed phase errors, checkpointed typed reconfigure,
and the durable agentic-phase inner-call protocol. Reject open-ended streams
with a stable diagnostic and event-queue-port disposition.

Semantic exit: a neutral reference pipeline preserves every source construct,
dynamic child, reducer, policy, and reentry through runtime; generic code has no
Megaplan coupling. Forbidden nondeterminism produces stable source-local
diagnostics, replay from identical recorded boundary results is trace-identical,
and local-harness traces normalize equivalently to installed execution without
weakening admission.

Adoption exit: enforce-mode crash/retry/idempotency/stale-fence/stale-epoch,
effect ambiguity, cancellation, transfer/reclaim, and resume tests pass using
M11 services. Decision/transition equality and program/policy/WBC-version drift
tests pass. Receipts/projections cannot grant actions.

### S3 - Front-half native vertical slice and carrier deletion

S3 begins with an internal stop/go gate: migrate only ordered prep -> plan,
including clarification suspend/reentry, through source lowering,
`build_pipeline()`, runtime, current M11 action validation, relocated WBC
producer identity, checkout execution, and clean installed-package execution.
Source mutation must change the trace and old-carrier mutation must not. Emit a
green builder/adoption receipt. No broader migration or carrier
deletion/quarantine begins before that receipt passes.

Move prep clarification, plan boundaries, critique selection/retry/dynamic
fanout/sequential fallback/merge, gate normalize/reprompt/backstops/debt, and
the bounded critique/gate/revise loop into canonical source. Attach policy at
call sites and leave only pure computation bodies.

Make `NP-GT-001` and `NP-GT-002` green incrementally, including loop
generation, retry/fallback causality, parallel-sibling partial order, child
multiplicity, and one-run decision/custody/WBC joins.

Relocate WBC producers from phase handlers to canonical lowered nodes/children.
Delete or hard-fence corresponding component routes, handler route strings,
manifest defaults, `_core` routes, CLI translation, and auto derivation.

Run GO-1 comparison work only in the quarantined comparison namespace and
prove it cannot acquire authority/custody, write admitted history, resume, or
emit an effect. Prove one real front-half agentic phase records its variable
inner model/tool calls under the declared WBC protocol and never returns an
outer route hint.

Semantic exit: split-outcome checkout/installed scenarios and legacy-carrier
mutation prove the authored source is load-bearing.

Adoption exit: every node/child has explicit four-domain joins and current
validator enforcement; handler-only instrumentation is insufficient. The
ordered prep/plan builder/adoption receipt proves the real seam before deletion.

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
`review_blocked -> replan`, not a sentinel or exception. Fanout children consume
one frozen admission binding; review reducers consume canonical keyed results
and remain invariant under completion-order permutations. GO-2 comparison
remains in the quarantined namespace and is never an admitted effect writer.

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

Author a closed cancel/publish/deliver/terminal arbitration with explicit CAS
preconditions, mutual exclusion, preserved completed-effect history, precedence,
and rejection outcomes. Make `NP-GT-006A` cancel-before-publish,
`NP-GT-006B` publish-outcome-before-cancel/pre-delivery, and `NP-GT-006C`
delivery/done-before-late-cancel green. Wall-clock or projection order cannot
pick a winner.

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
per-sprint receipt registry and rejects missing, extra, unknown, unconsumed,
stale, non-executed, non-commit-bound, or red records; and the receipt records
the proof-map hash before appending itself. A refreshed old ledger/evidence
bundle remains a mandatory failing fixture.

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

Require every golden family including NP-GT-006A/B/C—not a selected subset—to
match local and installed normalized lifecycle/admission traces under the same
recorded boundaries within declared virtual-time and wall-latency budgets.
Require every route divergence to be attributable to a declared outcome or
decision value; mutate undeclared payload fields to prove they cannot route.
Require zero diagnostic codes without either a supported primitive/example or
explicit deliberate-non-support boundary recipe, and pass a timed ten-task
author simulation as a blocking readability receipt.

Semantic exit: the smallest readable `.pypeline` fully determines actual
behavior and zero hidden route authority remains.

Adoption exit: every authoritative action is enforce-mode covered by current
grant/fence and exact lease/epoch plus applicable exact-version WBC evidence;
the pinned M11 receipt remains necessary but cannot substitute for Native
topology proof.

## Migration graph and binary stop/go receipts

```text
accepted M11
  -> S1 proof schema + golden skeletons + admission lock
  -> S2 generic primitives + neutral composed trace
  -> GO-0 generic ordered/multiset/decision/digest receipt
  -> S3 prep->plan producer + dual-read comparison
  -> GO-1 source-load-bearing/installed/adoption receipt
  -> S3 front-half consumer migration + old-carrier hard fence
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
- GO-1 failure keeps the old front-half producer authoritative and unfenced.
- GO-2 failure blocks live effect cutover and old-writer disable/fence/delete;
  external effects are never dual-written.
- GO-3 failure blocks old control-consumer demotion and heterogeneous rollout.
- GO-4 failure blocks epic completion.

At each cutover: land/test the authored producer and generated bindings; permit
only behaviorally inert dual-read comparison; relocate the WBC/action producer;
cut authority once at the receipt; move consumers; prove the old producer inert;
then hard-fence/delete after installed and cross-host proof.

Comparison execution uses a digest-bound `authority_class=comparison`
namespace that is non-authoritative, non-resumable and non-effect-capable.
Admitted RA/WBC/Custody/checkpoint/effect/terminal queries, projections, resume
selectors and decision consumers exclude it by construction. Comparison history
may be read only by the explicit comparison view and is never relabeled or
promoted into admitted history.

For every cutover, the union of old and candidate action/effect-capable paths
across `arnold.execution`, native runtime and legacy runtime-envelope planes is
registered in M11's controlled-writer inventory and crosses the same validator
in enforce mode. Exactly one producer may consume an accepted decision or write
admitted history. Unregistered old, candidate, or comparison paths fail before
body/effect intent.

## Normative semantic matrix

The aspirational Python in
`docs/arnold/megaplan-native-representation-report.md` is illustrative syntax,
not a demand for maximum granularity. This plan's machine-readable traceability
matrix is normative. For each product semantic it declares:

- required authored construct and typed vocabulary;
- routes and terminal outcomes;
- loop entry, exits, cap/no-progress/severity behavior;
- named enclosing-loop exit target and exhaustive parent handling;
- fanout collection, item schema, worker cap, per-item retry/fallback, reducer,
  deterministic naming and child coordinates;
- canonical decision-input schema/digest, frozen fanout binding digest, and
  canonical reducer-key contract;
- suspension capability, WBC lineage, exact reentry and lease lifecycle;
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
- accepted Run Authority decision ID/outcome/CAS sequence and consumed runtime
  transition/action for each typed decision occurrence or terminal acceptance;
- required positive, split-outcome, restart and negative-mutation scenarios;
- legacy carriers that must be deleted or hard-fenced;
- applicable M11 generic fixture and any Native-only proof extension;
- golden scenario/occurrence coordinates, required same-run order/partial-order,
  multiplicity, forbidden observations, and mutations;
- readability/edit-locality implications and generated-binding ownership.

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
- per-sprint validation receipt and proof-map membership/consumption status;
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
    variants and rejects conflicting terminal truth.
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
    all per-sprint receipts, and every blocking subcheck pass at the landed
    commit. The refreshed old ledger remains failing.
14. A reviewer can understand the entire product flow from canonical source
    without hidden carrier archaeology.
15. The durable golden trace contract is a consumed proof-map input, never a
    route authority, and all six scenario families/mutations pass from one
    composed history in checkout/wheel/cloud.
16. GO-0 through GO-4 are green; live external effects were never dual-written
    and no deletion/cutover crossed a failed binary boundary.
17. Cancel/publish/deliver/terminal arbitration has one closed authored CAS
    contract and one accepted terminal truth.
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
