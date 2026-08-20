# Oracle control-plane delta

**Date:** 2026-07-21  
**Scope:** the oracle's Q2/Q3 control-plane findings, checked against the current
Megaplan Native Representation Report, Native Parity canonical plan, S1/S5/S6/S7
briefs, Golden Trace Contract, and the previously audited/assumed-complete Custody
Control Plane M11 prerequisite.  
**Change policy:** read-only review; no authoritative plan or report was edited.

## Executive verdict

The oracle found two genuine Native Parity specification gaps, two shared-boundary
clarifications worth making blocking, one valid but prerequisite-owned disaster-
recovery question, and two issues that the current plan already covers strongly.
It did **not** uncover a contradiction in the Run Authority + Custody + WBC model.
The main weakness is that several migration and acceptance invariants are implicit
rather than mechanically stated.

The most important amendments are:

1. digest-bind the normalized Megaplan Plan Contract whenever `pre_existing` or
   another field can change evidence obligations;
2. prevent comparison/shadow executions from writing into admitted runtime history;
3. make repair requests hints whose preconditions are recomputed from canonical
   journals at acceptance time;
4. define the auto-drive scheduler boundary as placement/wakeup of an already
   selected, immutable typed action—not retry/route/policy selection;
5. consume a prerequisite proof that Run Authority fences and Custody epochs cannot
   be resurrected by backup restore or store rollback;
6. preserve a mechanically enforced, zero-bypass shared-validator choke point during
   every old/new producer handoff.

Native Parity should specify and test items 1–4 and 6. The Custody/Run Authority
prerequisite should implement item 5 and the generic portions of items 3 and 6.
Native Parity must consume those facilities, not build parallel control-plane
infrastructure.

## Ownership classification

| Oracle finding | Classification | Current coverage | Recommended disposition |
| --- | --- | --- | --- |
| Plan Contract `pre_existing` can waive evidence after an edit | **Genuine Native Parity gap** | The report correctly says `pre_existing` changes required evidence and that the Plan Contract cannot authorize. S1/S7 mutation-test non-routing/non-authority. But the action envelope and Golden Trace checkpoint digest list omit a Plan Contract/product-contract digest. | Add a normalized product Plan Contract digest (or prove it is transitively and unambiguously included in the program/policy digest) to admission, checkpoints, resume, decisions/transitions/effects, and golden mutations. Drift must pin, migrate, or quarantine; it cannot silently change evidence obligations. |
| Shadow/native comparison history can pollute authoritative WBC/checkpoint queries | **Genuine Native Parity migration gap** | The plan requires behaviorally inert dual-read, one binary authority cut, no dual-write effects, and old-writer inertness. It does not say where shadow WBC/checkpoint/decision records go or prohibit admitted-history writes by the comparison path. | Define a quarantined comparison identity/store namespace excluded from admitted WBC queries, projections, checkpoints, resume selection, RA decision consumption, and final proof except as explicitly labeled comparison evidence. Prefer no authority/custody/effect writes at all from shadow execution. Promotion must never relabel old shadow history as authoritative. |
| Auto-drive “scheduling” may still decide retries/escalations | **Already conceptually covered; wording should be made normative** | S6 explicitly restricts auto-drive to canonical events, liveness, and requests for topology-declared actions; it forbids deriving routes, retry/cap policy, model choice, resume, completion, cancellation, publication, or delivery from state/status. Final gates require zero route authority in auto/CLI. | Define a mechanical scheduler ABI/allowlist: auto-drive may choose host/queue/wakeup time for an immutable admitted action request whose semantic transition and policy decision already exist; it may not create or reinterpret an outcome, retry generation, escalation, terminal, or config change. Add mutation tests for legacy retry/escalation/cost/stall tables. |
| Backup restore can resurrect old RA fences or Custody epochs | **Valid concern; generic implementation is Custody/Run Authority prerequisite-owned and currently unverified** | The assumed M11 contract promises monotonic fences/epochs, persistence/recovery, cross-host handoff, and zero bypass. The available audit does not show a store-rollback/disaster-recovery incarnation rule or restore test. Process-birth identity and lease expiry do not by themselves prove coordinator-fence monotonicity after a restored store. | Add an S1 prerequisite acceptance item requiring M11 evidence for rollback-resistant authority: e.g. external monotonic store/cluster incarnation, restore generation that invalidates all pre-restore grants/leases, or fail-closed recovery requiring reissue under a higher epoch. Reuse its fixture in S7. If absent from completed M11, harden the prerequisite before Native Parity; do not implement a Megaplan-local workaround. |
| Repair requests may carry projection-derived preconditions that become authority | **Shared boundary gap; report has the principle but not the acceptance rule** | Report §1.4 and §5.5 say projections may emit typed requests but cannot feed positive authority or dispatch. S6 makes explanation/preflight request-only and inert. It does not explicitly require the authority/recovery acceptor to recompute every claimed precondition from canonical journals/current stores. | State that request fields are untrusted hints. At acceptance, the M11 authority/recovery API must resolve current journal/RA/Custody/WBC facts and rerun all preconditions; the normal action validator then runs again immediately before action. Native S6 adds forged/stale precondition negatives. Generic revalidation belongs to M11; request construction and Native tests belong to Native Parity. |
| Three overlapping execution planes can bypass the shared validator during convergence | **Substantially covered; sharpen the interim invariant** | Native Parity starts only after M11 zero-bypass/enforce-mode acceptance. S1 inventories all controlled writers/APIs; every Native authority-increasing action must use M11's validator. Cutover is binary, old writer stays authoritative, effects are never dual-written, and S7 requires zero bypass/set equality. | Make the invariant explicit per cutover: the union of old and candidate effect/action-capable paths is registered; every live path crosses the same enforce-mode validator; exactly one producer may consume an accepted decision/write admitted history; the shadow path cannot acquire action authority or emit admitted effects/checkpoints/terminals. Add a writer-registry mutation proving an unregistered legacy or candidate path is blocked. |
| `workflow_data.py` robustness overrides remain data-table route authority | **Already covered** | The report explicitly diagnoses `bare` and `light` overrides. S6 deletes/fences `_core` product transitions; S7 requires zero hidden authority and mutation-inert legacy carriers. The parity matrix includes robustness variants. | No new architectural work. Ensure the existing robustness matrix mutates every supported level and proves `_core/workflow_data.py` edits cannot change the normalized trace after the relevant slice cut. |

## Detailed analysis

### 1. Plan Contract digest pinning is a real omission

The current report is already unusually precise about the Plan Contract: it owns
milestone interface truth, and `pre_existing` changes which execution evidence is
required, but it does not authorize. That creates a direct consistency obligation.
If admitted action `A` was validated under Plan Contract `P1`, then a later edit to
`P2` cannot change the evidence predicate used for `A`, its resume, or its terminal.

The current executable-binding coordinates include program/topology, call-site
policy, component/implementation, installed artifact, dependency lock, schemas,
and model/tool bindings. The Golden Trace Contract checkpoint assertion lists the
same categories. Neither explicitly includes normalized Plan Contract identity.
The S1/S7 negative “cannot add a route or satisfy authority” is necessary but does
not detect an edited `pre_existing` entry reducing evidence requirements.

Normative fix:

```text
product_contract_digest = digest(canonical_normalized_plan_contract)

admitted action/checkpoint/reentry/terminal/effect binds product_contract_digest

current != admitted
  -> resume pinned P1
  -> or accepted P1->P2 migration/new-attempt disposition
  -> or quarantine
  -> never silently recompute evidence obligations under P2
```

It is acceptable to make this a transitive field of `program_digest` only if the
compiler emits and validates an explicit dependency edge and the proof can show
that every semantically relevant Plan Contract edit changes that digest. A named
field is clearer and easier to mutation-test.

### 2. Comparison history needs non-admitted provenance

“Behaviorally inert dual-read” and “never dual-write effects” do not completely
answer whether the candidate slice can append WBC attempts, checkpoints, decisions,
or terminals to the same histories queried by the authoritative run. If it can,
exact-version queries may see extra attempts; a resume selector may see a shadow
cursor; a projection may fold both histories; and a later proof may confuse
comparison evidence with authoritative occurrence multiplicity.

The candidate may produce comparison traces, but those records need a separate
provenance class that cannot satisfy admission. Strong options, in preference order:

1. pure/dry evaluation that emits only a signed comparison artifact outside the
   runtime stores;
2. a separate store or run namespace with `authority_class=comparison` that the
   admitted query registry categorically excludes;
3. if a common append store is unavoidable, a mandatory non-promotable provenance
   field enforced by every query, resume selector, projection, decision consumer,
   and proof adapter.

Copying or relabeling shadow attempts into the admitted namespace should be
forbidden. After the cut, the new producer starts fresh admitted occurrence/attempt
history or consumes an explicitly authored migration, rather than “promoting” the
shadow cursor.

### 3. Auto-drive is not an open conceptual hole

The oracle is right that “scheduling” can hide policy, but the current S6 brief
already prohibits precisely the listed behavior. The remaining issue is semantic
precision and enforceability, not missing ownership.

A safe definition is:

```text
topology/accepted decision selects transition + retry generation + declared policy
  -> immutable typed action request is admitted
  -> scheduler may choose eligible worker, queue, and dispatch/wakeup time
  -> worker revalidates exact current envelope immediately before action
```

Scheduling cannot interpret product status, manufacture a retry, advance a cap,
escalate, change a model, choose a terminal, or translate a legacy `next_step`.
“Wake up to ask the topology/authority process what is legal now” is scheduling;
“decide that a retry is due and create it” is routing/policy authority unless the
topology has already emitted the exact typed retry action.

### 4. Disaster recovery belongs below Native Parity

Monotonicity inside one live SQLite/history store is not automatically monotonicity
across restoration of an older copy. A restored authority store can make a lower
fence appear current; a restored lease store can forget a later reclaim/epoch. The
correct solution must be universal across workflows, so it belongs to the admitted
Run Authority/Custody substrate.

Native Parity's role is to reject a prerequisite that lacks the property and to
exercise the generic fixture under one Native action. It must not add another
Megaplan fence, “latest epoch” cache, restore marker, or projection-based guard.

The proof should include a store rollback/restore while an old actor and a newer
actor both exist. All pre-restore grants, accepted-but-unconsumed decisions, leases,
and checkpoints must either be invalid under a new control-plane incarnation or
revalidated/reissued under strictly newer tokens before any product body/effect
intent. A restore procedure that merely reloads rows and restarts workers is not
adequate.

### 5. Repair acceptance must distrust the request

The report's evidence/authority wall is correct. The missing sentence is:

> A repair request is an untrusted proposal; its cited observations and failed
> preconditions are never accepted as facts. The authority/recovery acceptor resolves
> and re-evaluates them from canonical exact-version histories/current stores at the
> acceptance cursor, then the action path revalidates current RA, Custody, WBC, and
> executable bindings immediately before work.

This closes both projection forgery and ordinary TOCTOU drift. A stale but honestly
generated request should be rejected or recomputed, not grandfathered.

### 6. Shared-validator convergence is already the plan's backbone

The oracle's “top risk” would be decisive if Native Parity began against today's
shadow/default-off M7 state. It does not: the explicit prerequisite is accepted M11
enforcement plus zero-bypass inventory. The plan then requires every Native action
to use that validator, a controlled-writer inventory, binary producer handoff,
old-writer inertness, no dual-written effects, and final source/lowering/runtime/
producer/action equality. Thus the claim that the interim invariant is absent is
overstated.

The narrow remaining ambiguity is the candidate comparison path. Closing the
shadow-history rule and spelling out a per-cutover union-of-writers assertion makes
the choke point mechanically complete.

### 7. `workflow_data.py` is known debt, not a newly missed surface

The representation report names the exact `bare` and `light` transitions. S6's
required deletion/fencing of `_core` product transitions and S7's zero-hidden-route
gate already target this. Retain it as a concrete mutation fixture because data
tables are an especially plausible hiding place for future relapse, but do not add a
new sprint or control-plane abstraction for it.

## Exact recommended plan actions

### Native Representation Report

1. Add `product_contract_digest` to the action-envelope table and explain that
   normalized Plan Contract fields affecting execution/evidence are immutable inputs
   for an admitted run; changes require pin/migrate/quarantine.
2. Add a migration rule that shadow/comparison executions cannot append to admitted
   RA/WBC/Custody/checkpoint/effect/terminal history and cannot be promoted by
   relabeling.
3. Define the scheduler boundary using the immutable typed-action formulation above.
4. State explicit request distrust and acceptance-time canonical revalidation.
5. Add restore/rollback lineage to the M11 prerequisite semantics, clearly labeled
   as assumed prerequisite behavior rather than a local implemented API.

### Native Parity S1 / GO-0

1. Extend the envelope/proof schema and Golden Trace global assertion 7 with the
   normalized Plan Contract/product-contract digest.
2. Add mutations: add/remove `pre_existing`, change interface path/signature, and
   mutate a non-semantic display field. Semantic changes must cause drift; explicitly
   excluded presentation-only fields should not.
3. Freeze `authority_class`/provenance rules for authoritative versus comparison
   histories and fail queries that mix them.
4. Add an M11 prerequisite receipt for restore-resistant RA/Custody monotonicity and
   acceptance-time repair-request revalidation.
5. Add an all-planes/all-writers inventory assertion: any authority-increasing path
   not registered behind the shared validator fails admission.

### Native Parity slice cutovers / GO-1 and GO-2

1. For each old/new producer pair, prove exactly one admitted writer and zero
   authority/custody/effect acquisition by the comparison path.
2. Query/projection/resume fixtures must ignore comparison records categorically.
3. Inject an unregistered legacy writer and an unregistered candidate writer; both
   must fail before body/effect intent.
4. Keep existing no-dual-write and outcome-before-receipt reconciliation gates.

### Native Parity S6 / GO-3

1. Add a scheduler conformance allowlist and mutations for retry, escalation, cap,
   cost, stall, model, resume, and terminal selection from auto/status state.
2. Add forged, stale, and internally inconsistent repair requests. Acceptance must
   recompute facts from canonical histories; deleting/rebuilding projections must not
   change the result.
3. Preserve the existing `_core/workflow_data.py` robustness mutations and assert
   they are inert after cutover.

### Native Parity S7 / GO-4

1. Reuse—not implement—the prerequisite backup-restore/cluster-incarnation and
   repair-revalidation fixtures.
2. Require authoritative/comparison provenance separation and the all-writers shared-
   validator inventory in the final proof map.
3. Add the product-contract digest to same-run checkout/wheel/cloud and stale-worker
   equivalence.

No new sprint is required. These fit S1, the existing binary cutovers, S6, and S7.

## Q2 limitation: missing numbered transitions

The supplied oracle answer says “items 3, 5, and 7 are genuine wrong-action paths”
and “item 2 can lose an accepted human result,” but the numbered list of
underspecified transitions is absent from the provided text. Those four references
cannot be assessed or mapped responsibly from the surviving summary alone.

The visible adversarial-history conclusions are already covered in broad form:

- stale epoch before body/effect intent: M11 validator + NP-GT-003/004;
- effect outcome before product receipt: NP-GT-004 and GO-2;
- recorded LLM terminal replay: Golden Trace assertions 13 and S7 mutations;
- executable drift on suspended resume: Golden Trace assertion 7 and NP-GT-003.

But no claim should be made that the omitted items 2/3/5/7 are closed. Obtain the
missing numbered text and map each transition to a scenario family before amending
the Golden Trace Contract. If any is a wrong-action path, add it before GO-2 as the
oracle recommends; if it is a generic RA/Custody/WBC transition, add it to the M11
prerequisite suite and consume it from Native Parity.

## Bottom line

The control-plane architecture remains sound:

> Python topology declares product behavior; Run Authority permits; Custody owns the
> exact current action; WBC records exact boundary/effect history; executable and
> product-contract digests pin what was admitted; projections and repair requests
> explain or propose but never supply facts or authority.

The oracle's best contribution is not a new layer. It is forcing four implicit
edges—product-contract pinning, comparison provenance, request revalidation, and
restore lineage—to become explicit blocking proofs.
