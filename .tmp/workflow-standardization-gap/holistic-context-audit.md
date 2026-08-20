# Holistic context audit of the native representation report

## Verdict

The revised representation report is a strong **target-shape document**, but it
is not yet a self-sufficient **system-context document**. A reader can now see
the two-stage destination and the desired component standard, yet still has to
already know Arnold's contract history to understand what is authored, what is
compiled, what is admitted, what authorizes an action, what merely proves an
observation, and what survives as compatibility during cutover.

The biggest omission is the contract stack itself. The report jumps from
Python source to an illustrative future `ComponentDescriptor` and then to
Run Authority/Custody/WBC validation. It does not place the existing
Python-shaped authoring contract, generated `WorkflowManifest`, Megaplan Plan
Contract, WBC declaration/evidence contract, runtime envelope/driver contract,
Run Authority decisions, Custody leases, journals, checkpoints, effects, and
projections in one ownership and dataflow model.

Three consequences follow:

1. “Source-authoritative” appears to conflict with the repository's statement
   that `WorkflowManifest` is the canonical serialized runtime contract. The
   intended distinction is reconcilable—source owns product semantics; the
   generated manifest is the immutable admitted runtime coordinate—but the
   report does not say it.
2. “Plan Contract,” “boundary contract,” “component contract,” “workflow
   contract,” and “runtime contract” can be read as variants of one abstraction.
   They are not.
3. The report uses the assumed completed-M11 RA/Custody/WBC semantics without
   explaining that the local checkout contains earlier/partial contracts and a
   different local `custody-control-plane` epic. The strongest M11 contract is
   currently present only through the Native Parity prerequisite text and the
   remote custody audit, not as the current local implementation.

This is a context gap, not a reason to redesign the architecture. A compact
contract-stack section, one action-envelope table, one lifecycle/dataflow
diagram, one end-to-end example, and one migration diagram would close most of
it.

## 1. Authority map for surrounding sources

The repository has several documents called “contract” at different layers.
The report should name their authority and status explicitly.

| Concern | Best current source | Authority/status | Important qualification |
| --- | --- | --- | --- |
| Python-shaped workflow source | `docs/arnold/python-shaped-authoring-contract.md`; implementation in `arnold.workflow.authoring` and `arnold/workflow/source_compiler.py` | Declares itself authoritative for grammar `arnold.workflow.authoring.v2` | Source is statically parsed and validated; it is not executed to discover topology. Its actual syntax differs from the report's illustrative API. |
| Serialized workflow/runtime coordinate | `docs/arnold/workflow-manifest.md`; `arnold/manifest/manifests.py`; `arnold/manifest/refs.py` | `arnold.workflow.manifest.v1` is the canonical serialized workflow contract | `manifest_hash` and stable refs own runtime/replay identity. The manifest must remain generated from source rather than becoming a second hand-authored product topology. |
| Manifest execution path | `docs/arnold/workflow-runtime.md`; `arnold/execution/runner.py`; `arnold/execution/backend.py` | Current journaled WorkflowManifest runner contract | This is distinct from direct `NativeProgram` execution and from the generic `StepwiseDriver` plane. |
| Native execution path | `arnold/pipeline/native/compiler.py`; `arnold/pipeline/native/runtime.py`; `arnold/pipeline/native/trace.py` | Current native compiler/runtime implementation | It can execute with optional pack metadata/lock and has a separate trace model. Native Parity must converge these paths rather than let both remain semantic authorities. |
| Generic runtime envelope and driver | `arnold/runtime/CONTRACT.md` | Normative for its M2a/M3d plugin runtime surface | This is an older/current `RuntimeEnvelope`/`StepwiseDriver` contract, not the proposed future component lifecycle. It also contains legacy lease/fencing fields that must not be conflated with M11 Run Authority/Custody. |
| Megaplan Plan Contract | `arnold_pipelines/megaplan/orchestration/plan_contracts.py`; finalize/execution consumers | The concrete current product contract implementation | It is a narrow `provides`/`assumes`/`pre_existing` schema. There is no equally clear canonical narrative document. |
| Workflow Boundary Contracts | `.megaplan/initiatives/workflow-boundary-contracts/NORTHSTAR.md`; `arnold/workflow/boundary_evidence.py`; `arnold_pipelines/megaplan/workflows/boundary_contracts.py` | Current local doctrine and v1 declarative/evidence vocabulary | Local code is partial and phase-specific. `BoundaryContract`, `BoundaryReceipt`, `AuthorityRecord`, and `SemanticFinding` are separate data roles. |
| Run Authority | `docs/arnold/runauthority-main-plan.md`; `docs/arnold/runauthority-architecture-decision.md` | Main plan explicitly says it is controlling direction | This checkout does not expose the completed M11 kernel implementation cited by the remote custody audit. These docs define authority doctrine, not proof that every writer is migrated. |
| Assumed M11 RA/Custody/WBC composition | `docs/arnold/megaplan-native-parity-corrective-plan.md`; `.megaplan/initiatives/megaplan-native-parity-corrective/NORTHSTAR.md`; `GOLDEN_TRACE_CONTRACT.md` | Authoritative prerequisite/consumer contract for Native Parity | These intentionally assume the remote custody chain finishes. They are the strongest local statement of the future conjunctive action rule. |
| Remote M11 design and current progress | `.tmp/native-parity-sensecheck/custody-overlap-audit.md`, citing remote `decisions/single-authoritative-runtime-history.md` and future code paths | Audit evidence, not a durable local canonical contract | The cited accepted target implementation is not present in this checkout. Do not treat similarly named local lease/resolver code as equivalent. |
| Current local custody epic | `.megaplan/initiatives/custody-control-plane/NORTHSTAR.md` and `chain.yaml` | Canonical for the older four-milestone local chain | It centers `resolve_run_state()` and repair/status custody; it does not define the M11 exact-action lease/epoch contract assumed by Native Parity. The shared name is materially overloaded. |
| State/resume migration | `docs/arnold/state-authority-migration.md`; `arnold/kernel/events.py`; `arnold/manifest/refs.py`; `arnold/execution/resume.py` | Current manifest/journal migration doctrine | Runtime identity there is alias + manifest hash. Native Parity and Platformization add more digest and component coordinates; the relationship needs an explicit additive map. |
| Current native checkpoints | `arnold/pipeline/native/checkpoint.py` | Current implementation contract for native/composite cursors | It has program counter, version, paths, parent/child cursor data, and fail-closed engine classification, but not yet the full future program/policy/WBC/install/component/dependency binding described by the plan. |
| Effects | `arnold/kernel/effect.py`; `arnold/kernel/effect_ledger.py`; `GOLDEN_TRACE_CONTRACT.md` NP-GT-004 | Current kernel precedent plus future acceptance semantics | Current vocabulary is intent/fulfillment/receipt/compensation; future WBC vocabulary uses intent/outcome/ambiguity/reconciliation. The report should map rather than silently merge them. |
| Current native packs | `arnold/pipeline/native/pack_metadata.py`; `pack_registry.py`; `pack_validation.py` | Existing packaging/resolution substrate | Current interface hash covers stable ID plus input/output schemas, not the full future lifecycle/outcome/state/effect/policy contract; lock enforcement is not universal. It is precedent, not completion of the Stage 2 component lock. |
| Projections/observation | `docs/reference/arnold-projections.md`; RA/WBC North Stars; Native Parity plan | Generated current reference plus future doctrine | A projection is rebuildable observation at a source cursor. It cannot become a bearer token for action. |
| Legacy cutover | `docs/arnold/state-authority-migration.md`; Native Parity plan's GO-0–GO-4 migration graph | Current journal migration precedent plus controlling future cutover | Detailed gates belong in the plan, but the representation report needs the overall producer/authority handoff model. |

### Source conflict that must be resolved in prose

The report's “source-authoritative Python” claim and the manifest contract's
“canonical serialized workflow contract” claim are compatible only under this
explicit ownership split:

```text
Python source owns product semantic authorship
  -> static validation/lowering
generated WorkflowManifest owns admitted runtime/replay coordinates
  -> runtime may not add, erase, or reinterpret product topology
```

The manifest is canonical *as serialized runtime input and identity*. It is not
a second editable source of product routes. The source is canonical *as product
semantic authorship*. The current report never states this distinction, so a
reader could reasonably infer a doctrine conflict.

## 2. Ambiguous and overloaded terms

| Term | Distinct meanings present in Arnold | Required disambiguation |
| --- | --- | --- |
| Contract | Python authoring grammar; component export contract; generated workflow manifest; Megaplan Plan Contract; WBC declaration; generic runtime driver contract | Always qualify the owner and purpose. Do not use “the workflow contract” without naming source, manifest, boundary, or runtime layer. |
| Plan Contract | Megaplan `provides`/`assumes`/`pre_existing` artifact | It describes inter-milestone/product interface expectations and selected pre-existing task treatment. It is not the workflow manifest, a WBC, an RA grant, a lease, or completion evidence. |
| Attempt | Semantic occurrence/retry; RA subject attempt; WBC execution attempt; custody repair/action occurrence | Preserve four identities and explicit joins; never use a generic `attempt_id` across them. |
| Authority | RA capability/accepted decision; older `AuthorityRecord` embedded in a boundary receipt; product transition policy | Only current RA grant/fence and accepted decision confer permission. A receipt's `AuthorityRecord` is evidence about a decision, not the grant itself. |
| Custody | Current local resolver/repair-custody doctrine; capacity/project leases; assumed M11 exact-action renewable lease/epoch | The report must mean the M11 exact-target lease/epoch when composing an action boundary and link the prerequisite that supplies it. |
| Fence | RA coordinator fence; old capacity-lease fencing token; current runtime envelope fencing field | Name the domain. Native Parity requires an RA coordinator fence independently from the Custody epoch. |
| Evidence | RA immutable evidence reference; WBC receipt/history; source semantic proof; observation set; validation proof-map item | Evidence can support admission or make a boundary incomplete. It never independently authorizes a positive action. |
| Checkpoint | Runtime snapshot; semantic checkpoint occurrence; WBC checkpoint event; native/composite cursor; operator `state.json` view | State owner, semantic coordinate, authority/custody identities, and all pinned versions must be explicit. |
| State | Component durable state; journal-derived authority state; compatibility `state.json`; projection; process liveness | Only the specified journal/decision sources are authoritative. Compatibility state is rebuildable/read-only during migration. |
| Identity/digest | Manifest alias/hash; source program/topology digest; call-site-policy digest; component contract/version; implementation/install digest; dependency lock; WBC version; payload/state schema; evidence-set digest | Preserve named fields and compatibility rules. One “workflow hash” cannot stand in for the entire executable binding. |
| Terminal | Component-local typed return; WBC attempt terminal; RA accepted terminal decision; root product terminal; external effect outcome | The component protocol must define the joins and forbid implicit promotion. |
| Reconcile | External-effect ambiguity resolution; WBC outbox persistence repair; worktree/checkpoint recovery; projection rebuild | Each has a separate authority and side-effect boundary. |
| Component | Current static `arnold.workflow.authoring.ComponentContract`; current native pack export; future Stage 2 lifecycle-bearing `ComponentDescriptor` | The report's descriptor is explicitly illustrative and must not be mistaken for the current static resolver metadata. |

## 3. Already adequately covered in the representation report

Ranked from strongest coverage downward:

1. **Two-stage architecture and layering.** The report clearly distinguishes
   source-authoritative Megaplan from independently packaged reusable patterns
   and shows the three layers: runtime/component protocol, pattern packages,
   product workflows.
2. **Reuse standardization target.** Qualified descriptors, typed bindings,
   clean wheels, deterministic component locks, shape-independent reuse,
   isolation, upgrade, and behavioral substitution are well articulated.
3. **Evidence is not authority at principle level.** The executive summary,
   generated binding discussion, closure contract, and Stage 1 recommendation
   correctly state that projections/receipts cannot choose routes or authorize
   actions.
4. **Generic versus product-owned policy.** The report consistently keeps
   domain types, outcome meaning, policy values, effects, artifacts, and
   storage behind product bindings.
5. **Component-local versus root terminal.** Section 6.1 says a subworkflow
   typed return is not root terminal permission. That is an important nesting
   invariant.
6. **Isolation intention.** Section 6.2 identifies run, parent semantic path,
   component identity, instance key, state/checkpoint/artifact/effect/Custody
   namespaces, and explicit shared-resource ports.
7. **Version/substitution intention.** Component, implementation, dependency,
   lock, checkpoint evolution, and conformance are covered at the target level.
8. **Migration direction.** Section 9 correctly makes Native Parity
   load-bearing, rejects a shadow as a finish line, mentions inert comparison,
   stale-worker rejection, no-dual-write effects, and downstream compatibility
   consumers.

These sections should be retained. The problem is that they state correct
outcomes without showing how they join the pre-existing contract stack.

## 4. Missing or underspecified context

### P0 — blocking comprehension gaps

#### P0.1 Contract stack and ownership boundaries

The report needs one table that distinguishes:

- Python authoring contract;
- component descriptor/export contract;
- generated WorkflowManifest/runtime identity;
- Megaplan Plan Contract;
- WBC declaration/evidence/finding;
- RA permission and accepted decisions;
- Custody exclusive exact-target ownership;
- checkpoint/state schemas;
- effects ledger;
- package/component lock;
- journal and projections.

For each, it should say “owns,” “does not own,” and “authoritative source.” The
current report provides only the upper architecture layers, not the contract
stack inside them.

#### P0.2 The Plan Contract is absent

The phrase “Plan Contract” does not appear. The actual current schema in
`plan_contracts.py` contains:

- `provides`: named descriptions plus interfaces (`symbol`, `signature`,
  normalized `path`);
- `assumes`: named upstream milestone plus expected interfaces;
- `pre_existing`: task IDs treated as already-existing by selected execution/
  evidence checks;
- deterministic `MISSING_UPSTREAM`/`MISMATCH` diff rows and a fingerprint.

It is a product-level inter-milestone/interface declaration. It can affect
planning/finalization and how Megaplan classifies pre-existing work, but it does
not grant a capability, accept a route decision, acquire custody, prove a WBC
complete, or prove that an effect occurred. The report must say that directly.

#### P0.3 No complete action-boundary envelope

The report lists several checks in prose, but not the complete composed record
needed immediately before an action:

```text
semantic occurrence + stable component instance/path
+ current RA grant, subject attempt, accepted decision (if applicable), fence
+ exact Custody target, owner/process-birth identity, lease, current epoch
+ WBC boundary ID, exact contract version, execution attempt, required history
+ program/topology + call-site policy + component contract/implementation
  + installed artifact + dependency-lock + payload/state-schema digests
= admitted action envelope
```

The actual positive gate is conjunctive:

```text
current RA grant/fence
AND current exact-target Custody lease/epoch
AND required exact-version WBC evidence
AND matching admitted executable bindings
```

The report should show who validates this, when it happens, and which mismatch
quarantines before body/effect intent.

#### P0.4 No authoring-to-observation dataflow

There is no single flow connecting:

```text
author source/imports
 -> static grammar/component/port validation
 -> lowering to DSL/WorkflowManifest
 -> manifest/component/dependency lock and admission
 -> RA grant/decision + Custody acquisition + WBC attempt start
 -> component body / checkpoint / effect lifecycle
 -> journal and accepted terminal
 -> WBC queries / causal explanation / projections
```

Without it, a reader cannot tell whether the illustrative component descriptor
is source, compiled manifest metadata, runtime registry data, or all three.

#### P0.5 Current-local versus assumed-M11 provenance

The local `.megaplan/initiatives/custody-control-plane` is a four-milestone
resolver/repair-custody epic. Native Parity assumes a different remote M11
end-state with exact-action leases, epochs, a shared conjunctive validator,
transactional WBC attempts/effects, recovery, and conformance. The report links
the Native Parity plan but does not disclose this provenance gap.

The report must not teach readers that `arnold/supervisor/leases.py`,
`capacity_lease.py`, the local resolver, or `RuntimeEnvelope.fencing_token` are
already the M11 contracts. It should state: “The following composed semantics
are the admitted prerequisite target; exact API paths and versions come from
the accepted M11 completion manifest.”

#### P0.6 Multiple current authoring, runtime, observation, and package planes

The report presents one clean target but does not orient the reader to today's
fragmentation:

- Python-shaped source lowers through the explicit DSL to `WorkflowManifest`
  and can run through `arnold.execution` with a journaled backend.
- The native compiler produces `NativeProgram`, executed by a separate native
  runtime with separate hooks/trace and optional pack metadata.
- `arnold/runtime/CONTRACT.md` defines another envelope/driver/settings plane
  and contains namespace drift from code now under `arnold.execution`.
- observation is split between manifest execution observability, native trace,
  and Megaplan product observability;
- package documentation reflects transitional disagreement over whether
  explicit-manifest or native-decorator surfaces are canonical;
- native pack resolution exists, but its interface hash/lock is materially
  narrower and less universal than the Stage 2 target.

This is not detail to hide: convergence of these planes is why the future
component lifecycle and admission receipt are needed. The report should name
the current planes, then state which one owns each end-state role. It should
not imply the illustrative `ComponentDescriptor` and `ComponentLock` already
wrap all current execution paths.

### P1 — material design-context gaps

#### P1.1 Component nesting to WBC boundaries and Custody targets

The report describes namespaces but does not specify:

- which step/subworkflow/workflow lifecycle transitions declare WBC boundaries;
- how parent and child WBC execution attempts join causally;
- whether child computation-only phases need custody versus only
  authority-increasing actions;
- how an exact Custody target derives from component instance path plus action/
  effect target;
- why a parent grant or lease cannot blanket-authorize children;
- how capability narrowing and independent child action validation work;
- how child WBC terminal becomes a typed parent input without becoming root
  completion authority.

This is the central bridge between the reusable component protocol and M11.

#### P1.2 Checkpoint/resume and drift need one envelope/table

Checkpoint ideas are spread across the illustrative code and closure contract.
A reader needs one record showing:

- semantic path and reentry coordinate;
- parent/child cursor lineage and retry/reentry generation;
- four identity domains;
- durable component state and schema version;
- program/topology, policy, exact WBC, component contract/implementation,
  installed artifact, and dependency lock digests;
- disposition on mismatch: pinned original, accepted migration/new attempt, or
  quarantine;
- reacquired/current RA and Custody on cross-host resume.

It should also state that matching a path string or a valid old marker is not
resume authority.

#### P1.3 Effect lifecycle vocabulary and authority joins

The report has effect-safe examples but lacks one authoritative sequence:

```text
validate action envelope
 -> durable WBC effect intent/idempotency identity
 -> external action
 -> durable outcome (or ambiguity)
 -> product receipt/projection
 -> crash-safe reconciliation under new current RA/Custody
```

It should reconcile the current kernel terms
intent/fulfillment/receipt/compensation with the future WBC terms
intent/outcome/ambiguity/reconciliation. A missing product receipt after a
durable outcome is rebuilt; it is not evidence that the effect did not happen.

#### P1.4 Evidence, projections, and causal explanation

The principle is present, but the report should distinguish:

- evidence collected before an RA decision;
- an accepted RA decision that cites evidence;
- WBC runtime history produced by an attempt;
- a semantic finding comparing contract, evidence, authority, and reality;
- a journal-derived/rebuildable projection;
- an operator explanation or repair preflight that may propose/request but not
  perform an action.

The current report does not show the source cursors or causal joins that make
an explanation trustworthy while keeping it behaviorally inert.

#### P1.5 Migration/cutover mechanics

Section 9 summarizes the destination but omits the key migration invariant:

```text
land generated bindings and new producer
 -> inert dual-read comparison
 -> pass binary receipt
 -> relocate WBC/action producer and cut authority exactly once
 -> migrate consumers
 -> prove old producer inert
 -> hard-fence/delete after installed and cross-host proof
```

For external effects, dual-read may be allowed; dual-write never is. The
report should summarize GO-0 through GO-4 by purpose and link the plan for
details. It should name compatibility surfaces—builder/component routes,
handlers, `_core`, CLI, auto-drive, status/WBC projections—and say which are
producer/authority before and downstream-only after each cut.

#### P1.6 No concrete full-stack run

The Python examples demonstrate authoring and reuse but stop before a complete
runtime narrative. One worked example should follow a dynamic review child or
effect-safe task through:

1. source call site and stable instance key;
2. static validation and generated manifest/component-lock coordinates;
3. Plan Contract input, if relevant;
4. WBC declaration and attempt start;
5. RA decision/grant and Custody target/epoch;
6. action validation;
7. checkpoint or effect intent/outcome;
8. child terminal and parent reducer;
9. journal/projection/explanation;
10. crash/resume or version-drift disposition.

That single example would give both developers and operators the missing
mental model.

#### P1.7 Developer and operator views are not separated

The developer needs to know what they author (source, typed component export,
ports, policies, effects, semantic keys) and what is generated (manifest,
mechanical IDs, WBC/RA/Custody bindings, dependency lock, trace adapters).

The operator needs to know what they inspect (accepted decisions, current
lease/epoch, WBC history/ambiguity, pinned versions, journal cursor,
projections), what a proposed repair means, and which surfaces are never safe
to edit to advance a run.

The report currently mixes these viewpoints.

### P2 — useful hardening

#### P2.1 Glossary and qualified naming

The ambiguity table in this audit should become a shorter glossary. In
particular, every use of `attempt`, `authority`, `custody`, `checkpoint`,
`terminal`, `contract`, and `digest` should be qualified where confusion is
possible.

#### P2.2 Admission terminology

“Admission” is used for prerequisite validation, executable validation, and
component registry acceptance. The report should distinguish:

- epic prerequisite admission (accept M11 completion manifest);
- compile/package admission (validated manifest and lock);
- action admission (current RA/Custody/WBC/executable envelope);
- registry publication admission (component conformance status).

## 5. Material detail better kept in companion documents

The representation report should orient and link, not reproduce all of this:

1. **Full Native Parity migration gates and scenario traces.** Keep GO-0–GO-4,
   NP-GT-001–006, proof-map schemas, and all negative mutations in the Native
   Parity plan and golden trace contract. The report needs only the purpose and
   invariant of each family.
2. **RA journal/reducer/CAS schema.** Keep claim envelopes, reducer fields,
   idempotency conflict rules, quarantine, and domain binding implementation in
   the RunAuthority plan/accepted M11 contracts. The report should summarize
   permission ownership and the action-boundary fields.
3. **Custody store and recovery protocol.** Lease event schemas, renewal TTLs,
   transfer/reclaim algorithms, process-birth encoding, and controlled-writer
   registries belong in the accepted M11 docs. The report needs exact-target,
   current epoch, independence from permission, and nesting rules.
4. **WBC storage/query/outbox schemas.** Transaction tables, monotonic sequence,
   dedupe constraints, payload migration, query APIs, and projection rebuild
   mechanics belong in WBC/M11 docs. The report needs declaration → attempt →
   evidence/finding → query flow and “not authority.”
5. **Python grammar and diagnostic catalog.** Keep AWF diagnostic codes,
   accepted/rejected AST forms, provenance fields, and compiler grammar in
   `python-shaped-authoring-contract.md`. The report should link it and explain
   source-to-manifest ownership.
6. **WorkflowManifest field specification and hashing algorithms.** Keep exact
   serialization/hash inputs in `workflow-manifest.md`. The report should name
   manifest identity and how component/dependency pins extend admission.
7. **Current runtime-plane implementation details.** Keep `ExecutionBackend`,
   native runtime hook/trace APIs, and `StepwiseDriver` method-level detail in
   `workflow-runtime.md`, native runtime code, and `arnold/runtime/CONTRACT.md`.
   The report should provide only a convergence/disposition map.
8. **Megaplan Plan Contract normalization/diff details.** Exact path cleanup,
   rendering, fingerprint serialization, and downstream checker behavior can
   remain in `plan_contracts.py` and focused docs/tests. The report needs a
   concise semantic boundary.
9. **Registry governance procedures.** Exact deprecation windows, signing,
   publishing commands, and artifact distribution procedures belong in the
   Platformization epic once written. The report should retain closure
   criteria.

## 6. Smallest coherent additions to the representation report

No rewrite is needed. Add five compact sections and extend one example.

### Addition 1 — “Contract stack and source-of-truth map” after section 1.2

Add a table with columns:

```text
Layer / contract | Authored or generated | Owns | Does not authorize/own |
Runtime identity/version | Canonical companion source
```

Rows: Python source grammar, component descriptor, WorkflowManifest, Plan
Contract, WBC, RA, Custody, journal/checkpoint, effect record, package lock,
projection. Include the source-authority versus manifest-runtime-coordinate
distinction and the local-versus-M11 custody provenance note.

### Addition 2 — “Authoring to observation” flow immediately after that table

Use one small diagram:

```text
Python + typed imports + Plan Contract inputs
  -> static validation
  -> lower to WorkflowManifest + component/dependency lock
  -> admit exact program/policy/WBC/install/lock versions
  -> create semantic occurrence and WBC attempt
  -> accept RA decision/grant and acquire exact Custody target/epoch
  -> conjunctive action validation
  -> body/checkpoint/effect/terminal journal
  -> exact-version WBC queries
  -> rebuildable projections/explanation/repair requests
```

Annotate which arrows may fail closed and that the final line cannot feed
positive authority back into execution.

### Addition 3 — “Action envelope and nesting” before Stage 2 examples

Add:

- the conjunctive action equation;
- a table for semantic, RA, Custody, WBC, and executable-binding fields;
- parent/child rules: separate attempts, explicit causal join, scoped grant,
  exact child action target, stable instance namespace, local terminal return,
  no blanket inherited authority;
- one checkpoint/resume envelope table and drift dispositions.

This is the minimum bridge between Native Parity and reusable components.

### Addition 4 — Extend the unrelated-consumer example with one full runtime
walkthrough

Follow `qualification/linux/review-rework` through compile, lock, WBC attempt,
RA grant/decision, Custody target/epoch, effect intent/outcome, checkpoint,
child terminal, reducer, projection, crash/reconcile, and compatible-version
resume. Put the operator-visible causal explanation beside the developer-side
source coordinate.

### Addition 5 — “Migration and compatibility ownership” in section 9

Add a short producer-cutover diagram and a table:

| Surface | Before cut | During comparison | End state |
| --- | --- | --- | --- |
| `.pypeline`/lowered manifest | candidate | load-bearing slice | only product-topology authority |
| handlers/components | route producer | old authority until binary gate, then inert | pure bodies/adapters or deleted |
| WBC producers | handler/component adjacent | relocate at exact cut | canonical semantic nodes/children |
| CLI/auto/`_core` | may route/mutate | consumer migration | request/observation only |
| legacy state/receipts | mixed authority | read-only projection | rebuilt/archived/deleted |
| external-effect writer | old only | new dry-run/dual-read, never dual-write | new only after GO-2 |

Summarize GO-0–GO-4 in one sentence each and link the Native Parity plan.

### Addition 6 — Short “Developer and operator mental model” near the conclusion

Developer rule:

> Author semantic topology, typed ports/outcomes, stable instance keys,
> policies, capabilities, effects, and product bindings; never hand-author
> runtime IDs, grants, leases, WBC attempt IDs, dependency locks, or projection
> routes.

Operator rule:

> Inspect accepted RA decisions, current exact-target Custody, WBC history,
> pinned executable versions, and causal projections; request a typed repair or
> migration, but never advance a run by editing status, receipt, checkpoint, or
> compatibility files.

### Addition 7 — Qualified glossary and companion links

Add the shortened ambiguity table and direct links to the authoritative
authoring, manifest, RA, WBC, Native Parity, golden trace, state migration, and
Platformization sources. Mark future M11 API paths as supplied by its accepted
completion manifest rather than current local code.

## Final assessment

The representation report now answers **what the target should look like** and
**what reuse should mean**. It does not yet answer **how all Arnold contracts
compose into one admitted action and one explainable run**.

The smallest philosophical addition is this sentence, expanded into the two
tables and diagrams above:

> Product semantics are authored in Python; runtime identity is the generated
> and locked manifest/component graph; Plan Contracts describe product
> inter-milestone assumptions; Run Authority permits; Custody exclusively owns
> the exact current action; WBC records the exact boundary/attempt/effect
> history; checkpoints pin reentry and executable versions; journals are folded
> into disposable projections that explain but never authorize.

Once that contract stack and one end-to-end run are present, the report will be
holistic enough for a reader who did not participate in the prior epics.
