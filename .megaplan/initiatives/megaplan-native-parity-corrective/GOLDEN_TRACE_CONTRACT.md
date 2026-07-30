# Native Megaplan golden source-to-runtime trace contract

Status: normative Native Parity composition oracle and twelve-milestone fixture contract
Scope: Megaplan Native Parity only; the accepted M11 Run Authority, Custody, WBC, recovery, query, projection, and conformance substrate is assumed
Normative source: `docs/arnold/megaplan-native-representation-report.md`, especially the aspirational Python workflow and its semantic explanation

## 1. Purpose

The existing corrective plan is strong at proving individual semantic rows. This contract adds the missing composition oracle: for a named scenario, the authored source, lowered program, accepted authority decisions, custody changes, WBC boundary/effect records, checkpoints, reentries, and terminal acceptance must describe the **same ordered run**.

This is not a second workflow model and must never become dispatch authority.
It is the human-reviewed scenario/invariant contract. An independent static
source oracle derives semantic occurrences and structured-control relations
from authored Python without calling the production lowerer. Runtime adapters
export raw primary-store facts; a separately implemented audit normalizer and
verifier checks raw event identity/multiplicity before applying only the
versioned volatile-field allowlist in this contract. Production lowering emits
actual traces, never expected traces. The fixture freezes observable semantic
facts while leaving internal class names, decorator spelling, storage schema,
and event transport replaceable.

The acceptance relation is:

```text
one authored semantic topology
  == one ordered semantic-occurrence trace
  == one exact accepted-decision/consumption trace
  == one current-custody trace
  == one durable WBC attempt/effect/checkpoint trace
```

Projections may reproduce that relation, but they may not supply any fact used to execute it.

The field-classification table has an immutable nonvolatile floor for semantic
identity, participants/outcomes, accepted and losing decisions, CAS sequence,
precedence, store incarnation and raw-history cursor. Every run and receipt
pins the exact table/allowlist version. Any amendment requires a
content-addressed amendment receipt, approval or verification independent of
the trace producer, and invalidation/replay of every dependent receipt affected
by the changed classification. A comparator rejects a newer table against old
evidence without that amendment chain.

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
dependency_lock_digest: "fixture-token:lock-v1"
prompt_tool_bindings_digest: "fixture-token:calls-v1"
product_contract_digest: "fixture-token:plan-contract-v1"
generated_manifest_schema: arnold.native-program.v1
generated_manifest_digest: "fixture-token:manifest-v1"
execution_mode: admitted_production
enforcement_disposition_version: arnold.native-execution-dispositions.v1
authority_class: admitted
authority_adapter_digest: "fixture-token:ra-adapter-v1"
authority_store_service_digest: "fixture-token:ra-store-v1"
authority_store_incarnation: "fixture-token:ra-incarnation-1"
raw_history_high_water_cursor: "fixture-token:event-420"
source_oracle_implementation_digest: "fixture-token:source-oracle-v1"
audit_normalizer_implementation_digest: "fixture-token:audit-normalizer-v1"
raw_export_digest: "fixture-token:raw-events-v1"
completion_spec_hash: "fixture-token:completion-spec-v1"
completion_binding_hash: "fixture-token:completion-binding-v1"
completion_candidate_outcome: accepted
completion_verdict_hash: "fixture-token:completion-verdict-v1"
completion_kernel_enablement_receipt: "fixture-token:s2r-go-0-v1"
completion_divergence_ledger_hash: "fixture-token:divergence-ledger-v1"
volatile_field_allowlist_version: arnold.megaplan.native-volatile.v1
volatile_field_nonvolatile_floor_digest: "fixture-token:nonvolatile-floor-v1"
volatile_field_amendment_receipt: null

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

Unknown raw fields are rejected rather than dropped. The production
lowerer/runtime trace adapter and the independent audit verifier may share the
versioned event schema, but not deduplication, event-elision or ordering logic.

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
  dependency_lock_digest: fixture-token:lock-v1
  prompt_tool_bindings_digest: fixture-token:calls-v1
  product_contract_digest: fixture-token:plan-contract-v1
  fanout_binding_digest: fixture-token:fanout-binding-v1
namespace:
  run: NP-GT-001
  occurrence: critique-0-correctness-0
observability:
  step_occurrence: step-critique-correctness-0
  execution_attempt: attempt-0
  agent_session_id: agent-session-0
  trace_span: trace-NP-GT-001/span-critique-correctness-0
  transcript_artifact: fixture-token:transcript-artifact-0
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
| `fanout.bind` | canonical keyed item set, immutable context/policy/call/artifact binding digest |
| `loop.exit.accept` | exit ID, typed outcome, named target loop instance, accepted/consumed decision and target-ledger close |
| `scope.superseded_by_exit` | exit ID, intervening durable scope, innermost-to-outermost unwind sequence and one control terminal |
| `decision.accept` | semantic occurrence, typed vocabulary/outcome, Run Authority decision ID, subject attempt, fence, CAS sequence, certified conditional-operation and adapter/store provenance |
| `decision.consume` | exact accepted decision ID, outcome, CAS sequence, consuming transition/action, store incarnation and raw-history high-water cursor |
| `custody.acquire` / `custody.release` / `custody.transfer` | target, owner, epoch, reason |
| `wbc.attempt.start` / `wbc.attempt.terminal` | semantic occurrence, WBC attempt, contract version, authority, custody |
| `step.attempt.start` / `step.attempt.terminal` | workflow/step occurrence, loop/rework/retry/reentry generation, execution attempt, exact input/output or artifact refs, executable/graph-lock/policy digests and source span |
| `child.terminal.accept` / `child.terminal.consume` | semantic child, immutable aggregate terminal and one parent CAS consumption; distinct from attempt terminals |
| `wbc.effect.intent` / `wbc.effect.outcome` | effect identity, idempotency identity, exact target, attempt lineage, external receipt or ambiguity |
| `agent.session.start` / `agent.session.terminal` | exact workflow/step attempt, platform agent-session identity/configuration, transcript/log artifact refs, terminal and consuming decision when one exists |
| `model.call.start` / `model.call.terminal` | agent session, prompt/model/tool/policy versions, provider request identity where available, result artifact, token/time/cost usage and effect identity |
| `tool.call.start` / `tool.call.terminal` | agent session/model call, tool/schema/input/output identities, effect intent/outcome and cost/resource charge |
| `log.artifact.attach` / `usage.charge` | exact occurrence/attempt/session/span, immutable artifact digest/schema/retention/redaction provenance, usage class and amount |
| `agentic.call.start` / `agentic.call.terminal` | enclosing WBC protocol, ordered inner call, prompt/tool/result identity, budget and effect joins |
| `agentic.budget.reserve` / `agentic.budget.exhaust` | durable charged allowance, optional named finalization reserve and closed exhaustion result |
| `reconfigure.accept` | typed delta, old/new policy and product-contract bindings, checkpoint and exact reentry cursor |
| `migration.accept` / `migration.consume` | per-run decision, exact from/to and state transform digests, new attempts and current custody |
| `checkpoint.write` | semantic cursor plus all four identity domains and all applicable executable/call/lock digests |
| `suspend` / `resume` | reason/input schema, checkpoint, reentry coordinate, old/new host and custody epoch |
| `human_answer.rejected_late` | distinct losing submission, privacy-safe evidence reference and no decision/route consumption |
| `repair.validation.reject` | actor-local redispatchable versus semantic-invalidating class and decision consumption state |
| `compat.seam.handoff` | serialize-only typed boundary, preselected downstream entry, controlled-writer identity and expiry milestone |

The correlation joins are bidirectional: an occurrence/attempt resolves every
platform-issued agent session, model/tool/effect call, usage charge and
log/transcript artifact, and each such record resolves the exact source span
and owning occurrence/generation/attempt, plus the consuming decision or
terminal when one exists. Provider session/request IDs are optional provenance,
not platform identity. Large or sensitive content is an immutable artifact
reference rather than an inline event. Durable events carry the correlation
keys; reverse indexes are rebuildable projections. This is complete
durable-boundary history, not instruction/local-variable tracing; logs and transcripts
are observational and cannot route, authorize, terminalize or certify.
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
7. Every checkpoint contains the semantic cursor, four identity domains,
source-program, policy, WBC-contract, installed-artifact, dependency-lock,
applicable prompt/tool binding, and normalized product/Plan Contract digests.
Every Native authority-increasing
dispatch, decision, transition, terminal acceptance, and effect envelope
validates those executable bindings before product body or effect intent.
Resume or dispatch under drift verifies pinned versions or consumes an explicit
admitted migration/new-attempt decision; a heterogeneous stale worker is
rejected/quarantined before action.
8. Only the authored topology and accepted authority decisions can choose a route. Handler return hints, auto/status logic, compatibility metadata, receipts, projections, and CLI presentation are observational or request-only.
9. Exactly one product terminal is accepted. Later conflicting cancellation, publication, or delivery actions are either rejected or handled by the closed arbitration rule specified in scenario 6.
10. Checkout, built wheel, and cloud execute the same fixture. A deliberately mixed-version host is rejected before action; homogeneous parity alone is not enough.
11. Topology/control code obeys the versioned deterministic-Python contract.
    Ambient time/randomness, process/environment state, unstable iteration,
    mutable globals, reflection/dynamic import/eval, unmanaged concurrency,
    direct I/O, and exception-driven product routes are rejected or cross a
    declared typed durable boundary. Replaying with identical recorded boundary
    results preserves semantic, decision, checkpoint, and terminal traces.
12. Every compiler/runtime rejection preserves a stable diagnostic code,
    authored file/span and semantic path, violated rule, and supported rewrite;
    generated frames do not obscure the source call site.
13. Every LLM/tool attempt binds prompt content/assets, model/provider
    parameters, tool schema/effect class, durable budgets, cache policy, output
    schema, and result identity. A durable result is replayed rather than called
    again; a retry is a distinct attempt and cannot reset budget. Cache evidence
    is content-addressed, provenance-recorded, schema-valid, and non-authority.
14. Checkpoints inline only bounded typed control data. Large/unbounded values
    use immutable artifact references with digest, schema/type, provenance, and
    retention. Invalid or unavailable required references cannot silently
    recompute or resume.
15. Executables, locks, prompt/tool assets, and schemas pinned by nonterminal
    runs remain resolvable until terminal or accepted migration/quarantine.
16. Durable state, checkpoints, artifacts, effect-idempotency keys, and caches
    are isolated by run plus semantic occurrence/instance coordinates.
17. Megaplan Plan Contracts and generated manifest/lock metadata neither add a
    route nor satisfy Run Authority, Custody, or WBC action admission.
18. Every control decision consumes a canonical schema-qualified serializable
    value and records its input digest. Host representation, container insertion
    order, completion order, or mutable object identity cannot change it.
19. Fanout freezes one binding digest at admission; every sibling consumes it.
    Fanin reducers receive a canonical keyed multiset and reject missing or
    duplicate keys rather than observing completion order.
20. Multi-level control uses a typed exit addressed to a named enclosing loop.
    Only declared typed phase outcomes/errors may be product-routed; sentinels,
    payload fields, and open exception classes cannot route.
21. Reconfiguration is an accepted typed delta plus checkpoint and exact
    reentry under new bindings. Ambient context/live flags cannot change flow.
22. If the admitted program declares an agentic phase, it journals every
    variable inner model/tool call under its named WBC protocol and durable
    budgets/effects. Every effectful inner
    call has an exact Custody target and its own WBC effect intent/outcome. The
    phase returns one closed outer outcome and no outer route hint.
23. Evidence-affecting normalized product/Plan Contract fields are digest-pinned
    at admission/checkpoint/action. Drift pins, migrates, starts a new attempt,
    or quarantines; it never silently waives evidence.
24. `authority_class=comparison` history is non-authoritative, non-resumable,
    non-effect-capable, excluded from admitted queries, and non-promotable.
    Every live old/candidate execution plane is registered behind one shared
    validator and exactly one producer writes admitted history per cutover.
25. Repair requests are untrusted hints whose preconditions are re-resolved from
    canonical stores at acceptance and revalidated immediately before action.
    Auto scheduling is limited to host/worker, queue, and wakeup/dispatch time
    for an immutable already-admitted typed action.
26. Every route divergence is attributable to a separately source-mapped
    finite route key or statically named finite predicate set declared by a
    closed outcome/decision. Whole-payload, open-string and undeclared
    payload-field discriminants reject. All diagnostic codes have a
    disposition; every family has local/installed normalized
    lifecycle/admission equivalence within the declared budget.
27. A named exit closes its target loop ledger, records exactly one
    `superseded_by_named_exit` terminal for every intervening durable scope in
    unwind order, and reenters only through an explicit new loop instance with
    declared carry data.
28. Every execution attempt has one immutable attempt terminal. Accepted retry
    creates a new retry generation under the same semantic child; the parent
    consumes exactly one immutable aggregate child terminal. Explicit new
    generation is a new semantic occurrence.
29. Effect ambiguity reconciles before cancellation by default. A declared
    `cancelled_pending_reconciliation` child lifecycle terminal binds a separate
    fenced obligation without fabricating an effect terminal or reopening the
    parent terminal.
30. Every migration application consumes its own accepted RA decision. A
    standing compatibility rule provides eligibility only.
31. Actor-local validation rejection may redispatch only a still-valid,
    unconsumed immutable decision through M11; semantic/precondition/executable
    invalidation voids it, and consumed decisions are never redispatched.
32. Agentic calls cannot start after durable budget exhaustion; optional
    finalization uses a named admitted charged reserve. One human answer wins
    CAS; same-submission replay is idempotent and distinct losers remain
    `rejected_late` evidence without route authority.
33. Raw event IDs/multiplicity are checked before normalization by a verifier
    independent of the production lowerer/runtime adapter. Lowered-IR
    arbitration-site/participant sets equal the indexed policies and forced
    race fixtures.
34. Every partial-cut seam is closed, serialize-only, preselected by an accepted
    upstream decision, registered when durable and expired by its owner. Every
    Native durable record has admitted restore ownership/proof.
35. Authoritative decision consumption and terminal/arbitration CAS are
    linearizable conditional operations enforced by the canonical production
    store/service. Two independent production-adapter clients, both release
    orders and pre/post-write crash edges admit exactly one winner; application
    read/check/write, local locks and in-memory stores are not release proof.
36. Governed producer/query registry and generated-manifest schema/hash
    evolution are explicit. Unsupported mixed workers reject before body/effect
    intent; comparison provenance cannot be forged, omitted, relabelled or
    promoted through a registry edit.
37. A durable-record restore receipt exists at introduction/first authority,
    and each proof-registry receipt binds adapter/store provenance, canonical
    store incarnation/restore generation and raw-history high-water cursor.
    Rollback, truncation and cross-incarnation stitching fail.
38. The gate annotation, return type, lowering and parent handling share the
    exact eight-value vocabulary. Preflight, cap/no-progress exhaustion,
    severity/high-complexity and recommendation precedence is fixed; progress
    requires strict decrease in canonical unresolved-blocking flag identities.
    A schema change supplies a total flag/streak mapping or emits
    `progress_incomparable`, leaves the ordinary progress streak unadvanced,
    increments a separate bounded incomparable counter and takes the declared
    cap disposition when exhausted.
39. Terminal arbitration exposes one stable role, semantic key and accepting
    Run Authority identity. A root-host adapter may consume that identity but
    cannot substitute another arbiter or acceptance domain.
40. The S1 machine-readable mode/disposition registries are the sole normative
    data source; this assertion list is an informative required rendering.
    Every runner and record names exactly one execution mode from
    `authoring_preview`, `durable_sandbox`, `comparison`,
    `admitted_production`, or `certification`. Mode is immutable for a history;
    promotion or relabeling is forbidden. A new mode starts a new identity/
    history with explicit lineage where applicable.
41. Working-tree edit/repeat automatically binds the edited content digest and
    fresh experiment/run/attempt and effect/cache/idempotency namespaces. It
    never appends to or overwrites the recorded source history.
42. A durable sandbox fork may consume an immutable admitted boundary as input
    provenance, but receives new authority/WBC/Custody/history identity and may
    use only sandbox-scoped authority records plus fake or explicitly sandbox-
    scoped effects. It is not production authority or resume.
43. `authoring_preview` may execute code outside the durable subset only when
    it emits no durable checkpoint or production-shaped authority/effect proof
    and is explicitly non-resumable, non-replayable, non-admissible and
    non-certifiable.
44. Every restriction has one versioned enforcement disposition:
    `always_hard`, `automatic`, `production_admission_gate`,
    `stable_publication_gate`, `authoring_advisory`, or `non_durable_only`.
    Diagnostics enforce the claim
    for the selected mode and cannot silently downgrade or promote it.
45. Every admitted durable subject has exactly one immutable
    `CompletionBinding`; pure helpers and disposable projections have none.
    The binding, candidate outcome, verdict, accepted decision/effect and
    terminal occurrence are joined without treating the verdict as permission.
46. Completion candidate outcomes and platform enforcement dispositions are
    separate versioned registries. Their generated boundary mapping is total
    and rejects every unknown pair; neither registry aliases the other.
47. C1 and C2 shadow records cannot affect admission or acceptance. The exact
    S2R GO-0 enablement receipt is required before any live kernel record, and
    every later authority-changing gate binds it plus the current
    content-addressed divergence-ledger hash.
48. The false-done/`REVIEW` fixture rejects legacy `done` without an accepted
    bound verdict, never admits `REVIEW` as executable identity, preserves
    unrelated accepted evidence, and routes reopened or genuinely new review
    work through normal admission with a fresh binding.
49. Projection deletion, rebuild, forgery and corruption cannot change the
    accepted completion decision, verdict or effect identity. At 57,000-event
    scale, live review/rework consumes Custody's exact bounded/incremental
    incident projection with no full-history fallback.

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

Determinism mutations replace an injected logical value with wall time/random or
unordered traversal and must fail at the authored span. Replaying the accepted
case twice with the same recorded phase/LLM/tool results yields the same trace.

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

The retryable failure is the immutable terminal of execution attempt 0, not the
aggregate terminal of the semantic `security` child. An accepted retry decision
opens attempt/retry generation 1. Success accepts the child's one aggregate
terminal, which the reducer/parent consumes exactly once.

**Fanout binding/reducer:** admission freezes the canonical lens set, context,
policy, prompt/tool and artifact binding digest consumed by all three children.
The reducer receives results keyed by lens and produces the same output under
every legal completion order.

**WBC/effects:** failed attempt terminal precedes retry start. Sequential fallback has no duplicate intent from an abandoned parallel child.

**Checkpoint/reentry:** retry checkpoint records cap consumption and all digests; no host reentry.

**Terminal:** `done`.

**Forbidden:** index-derived child paths; four reducer inputs; retry without accepted authority; fallback after any abandoned parallel child has produced an external effect unless the declared reconciliation policy admits it; hidden global retry/fallback policy.

**Mutations:** permuting lens order preserves child identities; removing the retry cap, changing the call-site model/retry policy, or forcing fallback from compatibility code changes or rejects the trace; mutating an index must not change identity.

Prompt-content-with-same-filename, model-parameter, tool-schema, exhausted-
budget, and forged-cache mutations reject before reuse/action. Crash after a
durable model/tool result but before checkpoint reuses that result and retains
budget consumption; it does not issue a second call.
Mutating shared context after fanout admission, supplying mixed binding digests,
or permuting completion order cannot change sibling inputs or reducer output.

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

Replaying the same answer submission ID returns the original acceptance without
another semantic fact. A different later submission records one privacy-safe
`human_answer.rejected_late` fact and cannot consume a decision or resume.
Two distinct schema-valid answers, and a schema-valid answer versus cancel,
are forced to the canonical CAS boundary through two independent production-
adapter clients in both release orders. Exactly one compatible transition
commits. Each loser remains a durable typed fact and cannot resume or rewrite
terminal truth.

**Custody:** Host A acquires target epoch 1, suspension releases or durably parks it according to M11; Host B obtains epoch 2. Any Host A action at epoch 1 is fenced.

**Checkpoint/reentry:** checkpoint contains the prep semantic cursor, human input schema, authority subject/fence, WBC attempt lineage, custody target/epoch, and the program/policy/WBC/installed digests. Host B verifies exact equality before product code. A mismatch yields admitted quarantine/migration handling, not implicit continuation.

**Terminal:** `done` under Host B lineage.

**Forbidden:** marker-only resume; reuse of Host A epoch; resume selected from status/projection; plan body before exact digest/authority/custody checks; silent migration; duplicate human decision consumption.

**Mutations:** stale fence, stale custody epoch, changed program digest, changed call-site policy digest, changed WBC version, changed installed artifact, forged resume projection, and wrong human input schema must each fail before `megaplan/plan` enters.
Replacing production-store CAS with application read/check/write, a process
mutex or an in-memory store fails even if a serialized fixture chooses one
answer.

Suspend multiple v1 runs, admit v2, and require exact retained v1 executable,
lock, prompt/tool assets, and schemas or an accepted migration/new-attempt/
quarantine decision. Premature GC, oversized inline human payload, missing or
digest/schema-invalid artifact reference, and silent v2 resume each fail before
plan enters.

Any migrated run consumes its own accepted RA migration decision binding exact
from/to and transform digests; a standing compatibility declaration cannot
silently migrate the cohort.

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

Cancellation during intent-without-outcome blocks by default until
reconciliation. A site that declares
`cancelled_pending_reconciliation(obligation_id)` may accept that child
lifecycle terminal only with a separate fenced reconciliation target; the
effect remains ambiguous, late resolution cannot rewrite the parent terminal,
and compensation requires a fresh decision.

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

If review returns declared `review_blocked -> replan`, the delivery/rework loop
emits a typed exit addressed to the named enclosing planning/critique loop. The
child outcome is not a root terminal and carries no sentinel or exception route.

The exit closes the target `planning_cycle` ledger after exactly one
`superseded_by_named_exit` control terminal for every intervening durable scope
in innermost-to-outermost order. Parent handling starts a new planning-cycle
instance at generation zero; only declared digest-bound carry fields survive.

**Fanout/identity:** T1 generation 0 is not regenerated or rerun. T2 generation 1 has lineage to T2 generation 0 and the rework decision. The delivery behavior is one authored reusable cycle entered twice, not copied branch blocks.

**WBC/effects:** T1 effect and artifact lineage remain terminal; only T2 receives a new attempt/effect where required. Revision 2 final artifact records scope and predecessor.

**Terminal:** `done` after the second review only.

**Forbidden:** full-batch rerun; T1 external effect repetition; unbounded recursion; a manually duplicated second delivery topology; terminal before re-review; scope inferred from handler-local state.

**Mutations:** widen scope to `{T1,T2}`, change cap to zero/two, remove re-review, or make the compatibility review reader authoritative; each must change or reject the trace. Editing the one source cycle changes both generations.

Run two delivery generations, same-kind siblings, and a concurrent second run
with identical task IDs. State/checkpoint/artifact/effect/cache namespaces must
remain distinct and any cross-read, overwrite, or accidental dedupe fails.
Replace the named replan exit with a payload field, sentinel, or exception; the
compiler or golden trace must reject it.

### NP-GT-006 — config override, note effect, publication/cancellation race

This fixture is a family with a shared prefix and three race variants.

**Shared prefix:** an admitted `set-model` request is translated to a typed authority decision and typed reconfigure transition carrying a schema-versioned delta. It durably checkpoints, binds the changed policy/executable/product-contract identity, advances reentry identity as required, and resumes the exact semantic cursor. Ambient context/live flags remain inert. An `add-note` request produces a WBC effect targeted at the exact semantic occurrence and an explicit `no_route_change` outcome. Neither CLI request directly dispatches product work.

**Variant A — `NP-GT-006A cancel-before-publish`:** cancel is accepted/consumed before publication intent. Terminal is `cancelled`; no publication or delivery effect is permitted.

**Variant B — `NP-GT-006B publish-outcome-before-cancel`:** publication intent and terminal outcome are durable, then cancel wins the still-open terminal arbitration before delivery. Publication remains in history; terminal is `cancelled`; delivery is forbidden. No rollback fiction is manufactured.

**Variant C — `NP-GT-006C delivery-terminal-before-late-cancel`:** publication and delivery terminal outcomes precede terminal `done`. A later cancel request is durably rejected as `terminal_conflict`; it cannot rewrite the terminal.

Pre-work repair/action rejection is classified from canonical facts. An
actor-local stale worker/lease/epoch may leave the same still-valid unconsumed
decision eligible for M11 reassignment; semantic/precondition/executable drift
records `decision.invalidated` and requires a new request. A consumed decision
is never redispatched.

**Required closed arbitration rule:** before S6 closes, the product topology/policy must define the legal order and CAS/precondition for cancel, publish, deliver, and terminal acceptance. The fixture must not infer the winner from wall-clock order or a projection. A minimal admissible rule is:

```text
cancel accepted before publish intent       -> cancelled, no publish/deliver
publish outcome then cancel before delivery -> cancelled, preserve publish, no deliver
delivery outcome and done accepted          -> late cancel rejected
```

Equivalent semantics are acceptable if explicitly authored and covered by the three variants.

The terminal-arbitration role, semantic key and accepting Run Authority
identity are stable contract fields. A future root-host adapter translates the
closed result only by consuming that same accepted identity; changing host
shape cannot install a second arbiter or acceptance domain. The arbitration
CAS is exercised by two independent production-adapter clients against the
certified canonical store/service operation, not inferred from a local mutex or
serialized event order.

**Identities/effects:** config, note, publication, delivery, cancellation request, and terminal decision have distinct semantic/authority/WBC/custody identities and causal joins. `add-note` cannot consume a route decision or change the semantic cursor.

**Forbidden:** config mutation without reentry; note changes route; cancel and done both accepted; delivery after the winning cancel; projection/status chooses the winner; CLI directly publishes; loss of a completed publication from history.

**Mutations:** reorder each race at the authority CAS boundary; mutate the authored arbitration branch; repeat note; replay stale cancel; forge published status; run a mixed-version delivery worker. Outcomes must follow the closed rule or reject before effect.
Mutate ambient config/live flags, scheduler retry/escalation/cost/stall tables,
repair-request preconditions, and `_core/workflow_data.py` robustness tables;
none may choose a route. Canonical repair facts are recomputed at acceptance.

### NP-DX-001 through NP-DX-004 — authoring execution modes

These developer fixtures exercise the same identity, provenance and trace
contracts but are not additional product scenarios.

- **`NP-DX-001 edited-step-repeat`:** select one typed recorded boundary, edit
  the step, and execute it repeatedly from working-tree content. Every attempt
  succeeds as a fresh experiment with the edited content digest, isolated
  identity and fake/sandbox effects; the source run remains byte-for-byte
  unchanged.
- **`NP-DX-002 changed-code-resume-rejected`:** present that edited digest as a
  continuation of the admitted source occurrence. Admission rejects before
  body/effect intent unless an explicit migration/new-attempt path is accepted;
  the harness must not silently reinterpret it as resume.
- **`NP-DX-003 durable-sandbox-fork`:** fork the recorded boundary with immutable
  provenance to source run, semantic occurrence and input/artifact digests. The
  fork receives new sandbox run/RA/WBC/Custody/history and effect-idempotency
  identity, remains sandbox-scoped, and cannot append to or authorize the source
  run.
- **`NP-DX-004 unsupported-preview`:** run one construct rejected by the durable
  compiler in explicit `authoring_preview`. Functional output is allowed, but
  no durable checkpoint/replay/resume/admission/certification receipt exists;
  every attempted relabel, promotion or downstream durable consumption fails.

The comparison control runs the same candidate digest in `comparison` and
proves that equal code identity does not promote quarantined history. Mode and
authority class are independent, explicit proof fields.

## 7. Mandatory mutation suite

Each fixture carries scenario-specific mutations plus this common suite:

| Mutation | Required observation |
|---|---|
| Change a Python-authored branch/outcome/cap/policy | Lowered program and relevant runtime trace change, or compilation fails |
| Change legacy handler route hint, route table, status/auto derivation, component routing metadata, or compatibility adapter | Runtime semantic trace is unchanged after that surface is fenced |
| Delete, duplicate, or reorder a same-path occurrence | Multiplicity/order assertion fails; legitimate sibling schedule variation remains accepted |
| Substitute decision ID, typed outcome, or CAS sequence | Consumption rejected before action |
| Substitute stale authority fence or custody epoch | Rejected before body/effect intent |
| Substitute program, policy, WBC, installed-artifact, dependency-lock, prompt, or tool digest | Quarantine or explicit migration decision; no implicit resume/action |
| Collapse semantic, authority, WBC, and custody IDs | Identity-domain assertion fails |
| Reorder dynamic input list | Same semantic child identities and aggregate result |
| Forge or stale a projection/receipt/status field | No dispatch, route, completion, resume, cancel, publish, or delivery change |
| Switch checkout/wheel/cloud implementation | Same normalized trace |
| Change Plan Contract `pre_existing`/`assumes`/interface semantics | Pinned drift disposition; no evidence waiver |
| Change an excluded Plan Contract presentation field | No false executable drift |
| Append comparison WBC/checkpoint/effect/terminal history | Excluded/rejected; never resumable, authoritative, or promotable |
| Register neither an old nor candidate action plane | Shared validator blocks it before body/effect intent |
| Change non-vocabulary outcome payload fields | No route change; every divergence remains attributable to a declared outcome/decision |
| Change fanout sibling completion order | Same keyed reducer output and decision-input digest |
| Introduce one stale worker into an otherwise current run | That worker is rejected before product execution |
| Omit/duplicate/reorder an intermediate named-exit unwind terminal or preserve the old loop instance | Raw trace fails; target ledger closure and explicit fresh-instance reentry are mandatory |
| Treat a retryable attempt terminal as the aggregate child terminal, or contribute twice to the reducer | Child-terminal cardinality/consumption fails |
| Cancel while effect state is ambiguous without the declared obligation policy | Parent cancellation remains unaccepted |
| Apply standing migration compatibility without a per-run accepted decision | Resume/action rejects |
| Redispatch a semantically invalidated or consumed decision | Rejected; actor-local still-valid unconsumed redispatch remains the only allowed case |
| Start an agentic call after budget exhaustion or use an undeclared finalization reserve | Rejected before call intent |
| Submit a distinct second human answer | Retained as rejected-late evidence; no route/resume change |
| Hide duplicate raw events in normalization | Independent raw-level multiplicity comparison fails |
| Add a lowered arbitration site without an indexed policy/forced-race fixture | Arbitration-site equality fails |
| Restore a Native durable record outside its declared rollback boundary | Restore-then-replay proof fails |
| Keep a typed outgoing seam past its expiry or let it select an entry | Cutover/conformance fails |
| Replace canonical CAS with application read/check/write, local locking, serialized clients or in-memory atomicity | Two-client production-adapter contention/crash proof fails |
| Forge, omit or relabel a comparison token/provenance field, or register it as admitted | Shared validator/query/proof exclusion fails; history is never promoted |
| Mark semantic key, participants/outcomes, accepted/loser identity, CAS sequence, precedence, store incarnation or high-water cursor volatile | Contract rejects the classification; normalization cannot elide arbitration truth |
| Change the field table/allowlist without an accepted amendment receipt and replaying every affected dependent receipt | Old evidence is invalid for the new table version; comparison/certification fails |
| Roll back/truncate a proof registry or replay a receipt under another store incarnation/high-water cursor | Receipt validation and restore-then-replay proof fail |
| Change generated-manifest schema/version/hash or mix an unsupported worker | Reject before body/effect intent or consume the explicit compatibility/migration disposition |
| Change one gate vocabulary site, precedence order or no-progress flag identity set without a total migration mapping | Compile/exhaustiveness fails or emits bounded `progress_incomparable`; the ordinary streak is never silently reset/carried |
| Use the whole payload, an open string or an undeclared field as a route discriminant | Static route-key validation fails |
| Substitute a new root arbiter/accepting identity through an adapter | Terminal-arbitration identity equality fails |
| Run edited working-tree code repeatedly from one recorded boundary | Fresh experiment identities and isolated keys; source history unchanged |
| Present an edited experiment as resume of the admitted occurrence | Reject before body/effect intent unless the explicit migration/new-attempt contract applies |
| Reuse a source-run authority, effect idempotency key, cache namespace or checkpoint namespace in a fork | Always-hard isolation assertion fails |
| Promote/relabel preview, sandbox or comparison history as admitted/certification evidence | Reject; create a new correctly admitted/certified history instead |
| Emit a durable checkpoint or replay/certification receipt from unsupported preview | Preview-disposition assertion fails |
| Downgrade an always-hard rule to warning, or make an authoring advisory block preview | Enforcement-disposition/severity matrix fails |

## 8. Twelve-milestone adoption

- **S1:** check in the schema, independent source-oracle/raw-export/verifier contract, six scenario and four `NP-DX` skeletons, forbidden-source vocabulary, multiplicity/order predicates, and mutation interface. Freeze the five-mode execution and enforcement-disposition matrix, certified-CAS provenance, registry/manifest evolution and receipt incarnation/high-water contracts. Prove the comparator on synthetic/raw mutations; current product behavior may remain red.
- **S2F:** implement the static `.pype` compiler/linker, canonical executable-closure identity, descriptor/lock integration, converter, diagnostics and minimal preview; close GO-FORMAT.
- **C1:** consume GO-FORMAT; land the experimental neutral completion package,
  versioned spec/identity/serialization, durable/helper lint, candidate-outcome
  registry, named-exit terminal, shadow generation, false-done/`REVIEW`
  fixture, and content-addressed divergence ledger without authority.
- **C2:** consume C1 and the current ledger hash; land immutable
  binding/evaluation schemas, evidence scope/proof modes, aggregation
  signatures, verifier independence, waiver taint, the internal persisted-wire
  compatibility matrix and decoder behavior, shadow atomic acceptance, restore, and
  projection-invariance proof without authority.
- **S2R:** consume GO-FORMAT and C1/C2; integrate the independent proof path with the neutral production runtime; fill generic loop, fanout/fanin, decision, policy, identity, checkpoint and retry/fallback events; instantiate concrete child-set/aggregation semantics for every primitive; implement edit/repeat/fork with isolated identities; register all three planes, pass production-adapter two-client CAS/crash and introduction-time restore proofs, and close GO-0 through the sole kernel-enablement transition.
- **S3A:** make prep/plan/critique through the join green, land execution-plane resume binding and the typed gate seam, and close GO-1A.
- **S3B:** freeze the eight-value gate vocabulary, precedence and canonical no-progress predicate; make gate/revise and `NP-GT-001/002` green, remove the S3A seam, own the typed tiebreaker/finalize seam and close GO-1B/GO-1.
- **S4:** make tiebreaker and `NP-GT-003` green, including answer-versus-answer and answer-versus-cancel production-CAS races.
- **S5A:** make the full finalize/admit/execute/evidence/accept/review/reopen-or-new-work/aggregate topology green in comparison/shadow execution, reject false done and executable `REVIEW`, inventory every effect-protocol class, and close per-class GO-2 without live effect authority.
- **S5B:** require the accepted GO-2 and exact Custody bounded-projection receipts at the live authority switch, then make `NP-GT-004` and `NP-GT-005` green against the admitted live-effect and bounded review/rework paths, including the 57k no-full-history-fallback gate.
- **S6:** make all `NP-GT-006` variants green, including the mixed-version rejection, projection-forgery and stable root-arbitration identity mutations.
- **S7:** run every fixture and mutation against checkout, built wheel, and cloud; compare ordered/multiset normalized traces from one run history, not separately manufactured row evidence.
  Also prove raw independent verification, restore ownership, arbitration-site
  equality, production CAS/store provenance, registry/manifest evolution,
  receipt incarnation/high-water binding, comparison-token/volatile-field
  mutations, all `NP-DX` mode-crossing and diagnostic-severity mutations, seam
  expiry and the content-addressed Platformization handoff.

## 9. What this contract deliberately does not specify

It does not choose UUID formats, database tables, Python decorator spelling,
subprocess/container boundaries, or projection UI. The `.pype` executable
closure does choose and version its canonicalization algorithm because those
digests enter durable identity; transport and unrelated internal hashes remain
implementation details when their artifact records pin the algorithm version.
This contract also does not redesign M11; it exercises the accepted substrate
through Native Megaplan’s authored semantics.

Open-ended streams/polling are deliberately unsupported; this contract covers
finite admitted fanout collections. Race/quorum is not added for Stage 1 absent
a demonstrated current Megaplan parity route and remains a Stage 2 candidate.

The supplied oracle Q2 answer referenced numbered transitions 2, 3, 5, and 7
that were absent from the pasted text. This editorial evidence gap creates no
speculative scenario and weakens no gate above; the missing transitions must be
obtained and mapped before any additional golden mutation is claimed.
