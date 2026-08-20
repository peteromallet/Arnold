# Native Megaplan golden source-to-runtime trace contract

Status: proposed bounded amendment and S1/S7 fixture design  
Scope: Megaplan Native Parity only; the accepted M11 Run Authority, Custody, WBC, recovery, query, projection, and conformance substrate is assumed  
Normative source: `docs/arnold/megaplan-native-representation-report.md`, especially the aspirational Python workflow and its semantic explanation

## 1. Purpose

The existing corrective plan is strong at proving individual semantic rows. This contract adds the missing composition oracle: for a named scenario, the authored source, lowered program, accepted authority decisions, custody changes, WBC boundary/effect records, checkpoints, reentries, and terminal acceptance must describe the **same ordered run**.

This is not a second workflow model and must never become dispatch authority. It is a fixture format generated from or checked against the authored Python topology. The fixture freezes observable semantic facts while leaving internal class names, decorator spelling, storage schema, and event transport replaceable.

The acceptance relation is:

```text
one authored semantic topology
  == one ordered semantic-occurrence trace
  == one exact accepted-decision/consumption trace
  == one current-custody trace
  == one durable WBC attempt/effect/checkpoint trace
```

Projections may reproduce that relation, but they may not supply any fact used to execute it.

## 2. Fixture envelope

S1 should freeze a machine-readable equivalent of this schema. The names below are contractual; serialization is not.

```yaml
schema: arnold.megaplan.native-golden-trace.v1
scenario_id: NP-GT-001
title: ordinary revise success
source_program_digest: "fixture-token:program-v1"
policy_digest: "fixture-token:policy-v1"
wbc_contract_version: "fixture-token:wbc-m11"
installed_artifact_digest: "fixture-token:wheel-v1"

inputs: {}
faults: []
expected:
  authored_occurrences: []
  ordered_events: []
  decisions: []
  fanout_children: []
  checkpoints: []
  effects: []
  terminal: {}
forbidden_observations: []
mutations: []
```

Every expected occurrence has:

```yaml
semantic:
  path: megaplan/critique-cycle/0/critique/lens/correctness
  occurrence:
    loop_generation: 0
    item_key: correctness
    logical_retry_generation: 0
    reentry_generation: 0
authority:
  subject_attempt: ra-subject-critique-0-correctness-0
  fence: 17
  accepted_decision: null
wbc:
  attempt: wbc-attempt-critique-0-correctness-0
  contract_version: fixture-token:wbc-m11
custody:
  target: run/NP-GT-001/critique/0/correctness
  epoch: 3
bindings:
  program_digest: fixture-token:program-v1
  policy_digest: fixture-token:policy-v1
  installed_artifact_digest: fixture-token:wheel-v1
```

Concrete IDs may be deterministic fixture aliases rather than production UUIDs. Equality, inequality, ordering, lineage, and reuse rules are normative.

## 3. Four identity domains

The fixture must reject collapsing any two of these domains:

| Domain | Meaning | Stability rule |
|---|---|---|
| Authored semantic identity | The source-visible node or child occurrence | Stable across host, install form, list reordering, retry, and resume when it is the same logical occurrence |
| Run Authority identity | The current subject attempt/fence and an accepted decision where one is required | A fresh authority attempt/fence is used after reassignment; an accepted decision is consumed exactly once by the matching action |
| WBC identity | The durable boundary attempt/effect/checkpoint lineage | A retry or reconciliation attempt is distinct even when it belongs to the same semantic occurrence |
| Custody identity | The exact protected target and current epoch | An epoch changes on reassignment; stale owners cannot act |

The occurrence coordinate used by the oracle is:

```text
(semantic_path,
 loop_generation,
 dynamic_item_key,
 logical_retry_generation,
 reentry_generation)
```

For a dynamic child, identity comes from the declared item identity (for delivery, the plan's task/batch/item identity), never a list index. A retry keeps the logical semantic child identity and increments its retry coordinate while receiving the distinct authority/WBC attempt identities required by M11. A cross-host resume keeps the suspended semantic occurrence, increments reentry generation, and receives current authority/custody identities.

## 4. Ordered event vocabulary

The exact storage event names may differ. The fixture adapter must normalize them to:

| Event | Required joins |
|---|---|
| `semantic.enter` / `semantic.exit` | semantic occurrence; parent occurrence |
| `fanout.declare` / `fanout.child` / `fanin.complete` | declared item set, semantic child paths, reducer/join path |
| `decision.accept` | semantic occurrence, typed vocabulary/outcome, Run Authority decision ID, subject attempt, fence, CAS sequence |
| `decision.consume` | exact accepted decision ID, outcome, CAS sequence, consuming transition/action |
| `custody.acquire` / `custody.release` / `custody.transfer` | target, owner, epoch, reason |
| `wbc.attempt.start` / `wbc.attempt.terminal` | semantic occurrence, WBC attempt, contract version, authority, custody |
| `wbc.effect.intent` / `wbc.effect.outcome` | effect identity, idempotency identity, exact target, attempt lineage, external receipt or ambiguity |
| `checkpoint.write` | semantic cursor plus all four identity domains and all three executable digests |
| `suspend` / `resume` | reason/input schema, checkpoint, reentry coordinate, old/new host and custody epoch |
| `terminal.accept` | typed product outcome and exact accepted/consumed terminal decision |
| `projection.observe` | source event cursor and projection provenance only |

Events are compared as an ordered partial order: total order is required within an occurrence, for authority/custody/effect causality, and at joins; siblings explicitly declared parallel need not have a fixed wall-clock interleaving. Child **multiplicity** is always compared as a multiset, never a set.

## 5. Global assertions

Every scenario fixture must establish all of the following:

1. Every runtime WBC-producing occurrence has exactly one authored semantic occurrence, and no un-authored product branch, loop, child, retry, reentry, effect, or terminal appears.
2. Occurrence multiplicity and loop generation agree across source, lowering, runtime, and WBC; set equality alone is insufficient.
3. Every typed product decision and terminal acceptance creates or links exactly one accepted Run Authority decision. The consuming transition/action uses that exact decision ID, outcome, and CAS sequence exactly once.
4. Every authority-increasing action starts only under current Run Authority and current exact-target Custody. A stale fence or epoch fails before the product body or effect intent.
5. Every WBC attempt has the admitted exact contract version and a causal join to semantic occurrence, authority, and custody.
6. Every external effect has durable intent and one terminal outcome or an explicit ambiguity requiring reconciliation. Reentry never repeats a terminal effect.
7. Every checkpoint contains the semantic cursor, four identity domains, source-program digest, policy digest, WBC contract version, and installed-artifact digest. Resume verifies them before product execution, or consumes an explicit admitted migration decision.
8. Only the authored topology and accepted authority decisions can choose a route. Handler return hints, auto/status logic, compatibility metadata, receipts, projections, and CLI presentation are observational or request-only.
9. Exactly one product terminal is accepted. Later conflicting cancellation, publication, or delivery actions are either rejected or handled by the closed arbitration rule specified in scenario 6.
10. Checkout, built wheel, and cloud execute the same fixture. A deliberately mixed-version host is rejected before action; homogeneous parity alone is not enough.

## 6. Scenario fixtures

### NP-GT-001 — ordinary critique/revise/finalize success

**Inputs:** ordinary brief; critique lens set `{correctness, scope}`; gate outcomes `iterate`, then `proceed`; final review `approved`.

**Authored path:**

```text
megaplan/prep
megaplan/plan
megaplan/critique-cycle/0/critique/{correctness,scope}
megaplan/critique-cycle/0/critique-join
megaplan/critique-cycle/0/gate[iterate]
megaplan/critique-cycle/0/revise
megaplan/critique-cycle/1/critique/{correctness,scope}
megaplan/critique-cycle/1/critique-join
megaplan/critique-cycle/1/gate[proceed]
megaplan/delivery-cycle/0/finalize
megaplan/delivery-cycle/0/execute/batch/B1/task/T1
megaplan/delivery-cycle/0/execute-join
megaplan/delivery-cycle/0/review/item/T1
megaplan/delivery-cycle/0/review-join[approved]
megaplan/terminal/done
```

**Typed decisions:** gate generation 0 accepts/consumes `iterate`; gate generation 1 accepts/consumes `proceed`; review accepts/consumes `approved`; terminal accepts/consumes `done`. Each has a different Run Authority decision ID and the exact matching CAS sequence.

**Fanout:** two stable critique children in each loop generation; one delivery child. Child order may vary, membership and multiplicity may not.

**WBC/effects:** durable attempts for all boundary occurrences; plan/final artifact writes are declared effects if they cross the admitted boundary; no duplicate final artifact or task effect.

**Checkpoint/reentry:** checkpoint after revise and before the second critique generation; no reentry.

**Terminal:** `done`, with review payload and final artifact lineage.

**Forbidden:** direct gate-to-finalize after `iterate`; a second revise; handler/status-selected next step; a delivery cycle copied under a second entry route; shared semantic/RA/WBC/custody ID.

**Mutations:** changing the authored first gate branch to `proceed` changes the trace and fixture fails; changing a legacy route map or handler `next_step` does not; deleting one same-named critique child is detected as a multiplicity failure.

### NP-GT-002 — dynamic critique retry and sequential fallback

**Inputs:** dynamic lenses `{correctness, security, api}`; `security` fails transiently once; the declared parallel launcher becomes unavailable before any child effect; policy permits sequential fallback; gate proceeds.

**Authored path:**

```text
.../critique-cycle/0/critique/lens/correctness/retry/0
.../critique-cycle/0/critique/lens/security/retry/0 [retryable failure]
.../critique-cycle/0/critique/lens/security/retry/1 [success]
.../critique-cycle/0/critique/lens/api/retry/0
.../critique-cycle/0/critique-join
.../gate[proceed]
.../delivery-cycle/0/...
.../terminal/done
```

**Decisions/policy:** one accepted/consumed fallback decision bound to the call-site policy and observed launcher failure; one accepted/consumed logical retry decision for `security`; retry cap and fallback eligibility come from the authored call site or its named policy, not a handler default.

**Fanout identities:** children use lens keys, not positions. Reorder input to `{api, correctness, security}` and the same three logical child identities result. The retried `security` occurrence has one semantic child with retry generations 0 and 1, distinct authority/WBC attempts, and no duplicate reducer contribution.

**WBC/effects:** failed attempt terminal precedes retry start. Sequential fallback has no duplicate intent from an abandoned parallel child.

**Checkpoint/reentry:** retry checkpoint records cap consumption and all digests; no host reentry.

**Terminal:** `done`.

**Forbidden:** index-derived child paths; four reducer inputs; retry without accepted authority; fallback after any abandoned parallel child has produced an external effect unless the declared reconciliation policy admits it; hidden global retry/fallback policy.

**Mutations:** permuting lens order preserves child identities; removing the retry cap, changing the call-site model/retry policy, or forcing fallback from compatibility code changes or rejects the trace; mutating an index must not change identity.

### NP-GT-003 — human clarification suspension and cross-host resume

**Inputs:** prep requests clarification; Host A initially owns custody; human supplies typed clarification; Host A is unavailable; Host B reclaims custody.

**Authored path:**

```text
megaplan/prep/human-clarification[suspend]
megaplan/prep/human-clarification[resume generation 1]
megaplan/plan
... ordinary successful path ...
megaplan/terminal/done
```

**Decisions:** accepted/consumed `needs_clarification`; accepted human decision with schema-valid input; resume consumes that exact decision. No plan decision/action exists before resume acceptance.

**Custody:** Host A acquires target epoch 1, suspension releases or durably parks it according to M11; Host B obtains epoch 2. Any Host A action at epoch 1 is fenced.

**Checkpoint/reentry:** checkpoint contains the prep semantic cursor, human input schema, authority subject/fence, WBC attempt lineage, custody target/epoch, and the program/policy/WBC/installed digests. Host B verifies exact equality before product code. A mismatch yields admitted quarantine/migration handling, not implicit continuation.

**Terminal:** `done` under Host B lineage.

**Forbidden:** marker-only resume; reuse of Host A epoch; resume selected from status/projection; plan body before exact digest/authority/custody checks; silent migration; duplicate human decision consumption.

**Mutations:** stale fence, stale custody epoch, changed program digest, changed call-site policy digest, changed WBC version, changed installed artifact, forged resume projection, and wrong human input schema must each fail before `megaplan/plan` enters.

### NP-GT-004 — external effect outcome before receipt, then crash

**Inputs:** delivery tasks `T1`, `T2`, `T3` in batch `B1`; external effect `E-T2`; crash occurs after the external system returns success and durable `wbc.effect.outcome`, before the product receipt/projection is written.

**Authored path:**

```text
.../delivery-cycle/0/finalize
.../execute/batch/B1/task/T1 [complete]
.../execute/batch/B1/task/T2 [effect intent, effect outcome, crash]
.../execute/batch/B1/task/T2 [reconcile, no repeat]
.../execute/batch/B1/task/T3 [complete]
.../execute-join
.../review/...
.../terminal/done
```

**Identities:** delivery children include stable task, batch, and item identity. T2 reconciliation preserves the semantic child and effect idempotency identity while using the current post-reassignment authority/custody and the WBC reconciliation attempt identity.

**WBC/effects:** exactly one `E-T2` intent that reaches the external system and exactly one terminal success outcome. Missing product receipt is rebuilt as a projection from the durable outcome. If only intent were durable, the run would enter WBC ambiguity/reconciliation rather than guessing.

**Checkpoint/reentry:** checkpoint after T1 and at T2 effect outcome; new host/worker verifies digests and current authority/custody before reconciliation.

**Terminal:** `done`; tasks T1–T3 each contribute exactly once.

**Forbidden:** repeating `E-T2`; treating absence of a product receipt as evidence the effect did not happen; an index path; two writers during compatibility cutover; completing from a forged receipt.

**Mutations:** crash injection before intent, after intent, after outcome, and after receipt must yield the admitted four distinct histories; deleting the outcome causes ambiguity rather than replay-as-success; changing an old execute handler is inert after cutover.

### NP-GT-005 — review failure, bounded scoped rework, refinalization

**Inputs:** initial tasks `T1`, `T2`; review approves T1 and returns `rework(T2)`; rework cap is one; T2 revision succeeds; second review approves.

**Authored path:**

```text
.../delivery-cycle/0/finalize/revision/1
.../delivery-cycle/0/execute/task/T1
.../delivery-cycle/0/execute/task/T2
.../delivery-cycle/0/review/item/T1[approved]
.../delivery-cycle/0/review/item/T2[rework]
.../delivery-cycle/0/rework[scope={T2}]
.../delivery-cycle/1/finalize/revision/2[scope={T2}]
.../delivery-cycle/1/execute/task/T2
.../delivery-cycle/1/review/item/T2[approved]
.../terminal/done
```

**Decisions:** exact review aggregate decision `rework`; scoped rework/refinalization decision names `{T2}`; second review `approved`; terminal `done`. Cap state is source/policy visible and durable.

**Fanout/identity:** T1 generation 0 is not regenerated or rerun. T2 generation 1 has lineage to T2 generation 0 and the rework decision. The delivery behavior is one authored reusable cycle entered twice, not copied branch blocks.

**WBC/effects:** T1 effect and artifact lineage remain terminal; only T2 receives a new attempt/effect where required. Revision 2 final artifact records scope and predecessor.

**Terminal:** `done` after the second review only.

**Forbidden:** full-batch rerun; T1 external effect repetition; unbounded recursion; a manually duplicated second delivery topology; terminal before re-review; scope inferred from handler-local state.

**Mutations:** widen scope to `{T1,T2}`, change cap to zero/two, remove re-review, or make the compatibility review reader authoritative; each must change or reject the trace. Editing the one source cycle changes both generations.

### NP-GT-006 — config override, note effect, publication/cancellation race

This fixture is a family with a shared prefix and three race variants.

**Shared prefix:** an admitted `set-model` request is translated to a typed authority decision and durable config effect; policy digest changes; continuation occurs only through explicit checkpoint/reentry. An `add-note` request produces a WBC effect targeted at the exact semantic occurrence and an explicit `no_route_change` outcome. Neither CLI request directly dispatches product work.

**Variant A — `NP-GT-006A cancel-before-publish`:** cancel is accepted/consumed before publication intent. Terminal is `cancelled`; no publication or delivery effect is permitted.

**Variant B — `NP-GT-006B publish-outcome-before-cancel`:** publication intent and terminal outcome are durable, then cancel wins the still-open terminal arbitration before delivery. Publication remains in history; terminal is `cancelled`; delivery is forbidden. No rollback fiction is manufactured.

**Variant C — `NP-GT-006C delivery-terminal-before-late-cancel`:** publication and delivery terminal outcomes precede terminal `done`. A later cancel request is durably rejected as `terminal_conflict`; it cannot rewrite the terminal.

**Required closed arbitration rule:** before S6 closes, the product topology/policy must define the legal order and CAS/precondition for cancel, publish, deliver, and terminal acceptance. The fixture must not infer the winner from wall-clock order or a projection. A minimal admissible rule is:

```text
cancel accepted before publish intent       -> cancelled, no publish/deliver
publish outcome then cancel before delivery -> cancelled, preserve publish, no deliver
delivery outcome and done accepted          -> late cancel rejected
```

Equivalent semantics are acceptable if explicitly authored and covered by the three variants.

**Identities/effects:** config, note, publication, delivery, cancellation request, and terminal decision have distinct semantic/authority/WBC/custody identities and causal joins. `add-note` cannot consume a route decision or change the semantic cursor.

**Forbidden:** config mutation without reentry; note changes route; cancel and done both accepted; delivery after the winning cancel; projection/status chooses the winner; CLI directly publishes; loss of a completed publication from history.

**Mutations:** reorder each race at the authority CAS boundary; mutate the authored arbitration branch; repeat note; replay stale cancel; forge published status; run a mixed-version delivery worker. Outcomes must follow the closed rule or reject before effect.

## 7. Mandatory mutation suite

Each fixture carries scenario-specific mutations plus this common suite:

| Mutation | Required observation |
|---|---|
| Change a Python-authored branch/outcome/cap/policy | Lowered program and relevant runtime trace change, or compilation fails |
| Change legacy handler route hint, route table, status/auto derivation, component routing metadata, or compatibility adapter | Runtime semantic trace is unchanged after that surface is fenced |
| Delete, duplicate, or reorder a same-path occurrence | Multiplicity/order assertion fails; legitimate sibling schedule variation remains accepted |
| Substitute decision ID, typed outcome, or CAS sequence | Consumption rejected before action |
| Substitute stale authority fence or custody epoch | Rejected before body/effect intent |
| Substitute program, policy, WBC, or installed-artifact digest | Quarantine or explicit migration decision; no implicit resume/action |
| Collapse semantic, authority, WBC, and custody IDs | Identity-domain assertion fails |
| Reorder dynamic input list | Same semantic child identities and aggregate result |
| Forge or stale a projection/receipt/status field | No dispatch, route, completion, resume, cancel, publish, or delivery change |
| Switch checkout/wheel/cloud implementation | Same normalized trace |
| Introduce one stale worker into an otherwise current run | That worker is rejected before product execution |

## 8. S1–S7 adoption

- **S1:** check in the schema, normalizer, six scenario skeletons, forbidden-source vocabulary, multiplicity/order predicates, and mutation interface. Existing behavior may be red; the oracle itself must be executable and incapable of passing on set-only evidence.
- **S2:** fill generic loop, fanout/fanin, decision, policy, identity, checkpoint, and retry/fallback events using the neutral reference pipeline.
- **S3:** make the prep→plan prefix and ordinary critique/revise path green; the existing S3 internal gate consumes the relevant prefix receipts.
- **S4:** make tiebreaker and `NP-GT-003` green.
- **S5:** make `NP-GT-004` and `NP-GT-005` green, first against a non-destructive effect adapter and then against the admitted live-effect path.
- **S6:** make all `NP-GT-006` variants green, including the mixed-version rejection and projection-forgery mutations.
- **S7:** run every fixture and mutation against checkout, built wheel, and cloud; compare ordered/multiset normalized traces from one run history, not separately manufactured row evidence.

## 9. What this contract deliberately does not specify

It does not choose UUID formats, database tables, hash canonicalization algorithms, Python decorator spelling, subprocess/container boundaries, or projection UI. Those are implementation details as long as equality and drift detection are deterministic and the observable contract above holds. It also does not redesign M11; it exercises the accepted substrate through Native Megaplan’s authored semantics.
