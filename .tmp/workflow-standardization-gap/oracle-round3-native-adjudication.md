# Oracle round 3: Native Parity and sequencing adjudication

Date: 2026-07-21

Scope: the current representation report, Native Parity corrective plan,
`chain.yaml`, North Star, golden trace contract, seven active briefs, current
codebase map, and Workflow Platformization ticket. This is an adjudication of
the supplied Oracle answers, not an adoption of them verbatim.

## Decisive verdict

The Oracle found real specification and sequencing gaps. Most should be
absorbed as normative rules and proof obligations. Two proposed rules are too
blunt and must **not** be copied as written:

1. A retry cannot be limited to a child that has no terminal record. The
   existing `NP-GT-002` contract correctly requires an immutable terminal for
   each execution attempt, followed by a new retry generation under the same
   semantic child. What must be unique is the child's aggregate component
   terminal consumed by its parent, not every WBC attempt terminal.
2. Any action-validator rejection must not automatically void an accepted
   decision. Actor-local placement/custody rejection before decision
   consumption may redispatch the same still-valid immutable decision through
   M11 recovery. Semantic/precondition/executable invalidation must void it.
   Conflating those cases either creates duplicate action or needless route
   re-decision.

The chain should become **eight two-week milestones**, expressed as
`S1, S2, S3A, S3B, S4, S5, S6, S7`. Seven cannot be preserved safely by moving
S3's gate/revise work into S4: that would combine the densest current semantic
owner with tiebreaker, finalize, mixed-version human reentry, and its own
carrier cutover. S1 can remain one milestone only by freezing and testing the
proof contracts there while moving their production-runtime integration to
S2/GO-0. S3 must split.

No new Platformization sprint follows from these findings. Native Parity must
emit a content-addressed handoff manifest in S7; the existing five-stage
Platformization ticket consumes it.

## Normative resolutions

### 1. Named enclosing-loop exits and unwound scopes

Adopt the Oracle's direction, but define the target precisely:

- A named exit identifies an active ancestor **loop instance** and one of that
  loop's declared typed outcomes.
- Accepting the exit unwinds through and terminates the named loop instance. It
  is never an implicit `continue` at the target and never preserves counters by
  accident.
- Every intervening active durable control scope with a WBC attempt or durable
  ledger records exactly one
  `superseded_by_named_exit(exit_id, target_loop_instance, outcome)` control
  terminal, in deterministic innermost-to-outermost order. These are lifecycle
  terminals, not product business outcomes.
- The target loop closes its ledger and emits its declared outcome exactly
  once to its parent.
- If the parent re-enters planning, it explicitly creates a new planning-loop
  instance with generation zero. Any carried accumulator or evidence is named
  in the exit outcome payload schema and digest-bound; no loop state is carried
  implicitly.

For Megaplan, `review_blocked -> replan` must target a named outer
`planning_cycle`, close the current delivery/rework and planning-cycle
instances, and let the parent start a fresh planning-cycle instance. The
critique cap therefore resets only because the parent explicitly starts a new
instance, not because `exit` secretly means `continue`.

Required trace additions:

- `loop.exit.accept` with exit ID, source and target loop instances, outcome,
  and accepted/consumed RA decision;
- one `scope.superseded_by_exit` per unwound durable intermediate scope;
- target ledger close before parent re-entry;
- mutations for omitted, duplicated, or incorrectly ordered unwind terminals.

### 2. Retry versus new generation

Reject the Oracle's proposed “retry only nonterminal children” rule. Freeze a
three-layer model instead:

1. **Execution attempt:** every WBC/worker attempt has one immutable attempt
   terminal, including `retryable_failure`.
2. **Semantic child occurrence:** retry creates a new logical retry generation
   under the same semantic child occurrence, with a new RA/WBC attempt and
   current Custody, after an accepted retry decision. Earlier attempt terminals
   remain immutable.
3. **Aggregate child/component terminal:** the retry policy eventually accepts
   exactly one final child result (success, exhausted failure, cancellation,
   etc.). The parent consumes that aggregate terminal exactly once by CAS.

An explicit new child generation is a new semantic occurrence and key. It is
used only when the product topology deliberately repeats completed logical
work under a declared repeat policy. It is not an alias for an execution retry.

A durable effect outcome is reused during retry and cannot be repeated. An
intent without outcome reconciles before retry or new generation advances.
The current report/ticket phrase “same child and its durable terminal/effect
outcome” must be rewritten to distinguish immutable **attempt** terminals,
reused effect outcomes, and the single aggregate child terminal.

### 3. Cancellation while an effect is ambiguous

Effect ambiguity remains an unresolved effect state; it must never be relabeled
as effect success, failure, or compensation.

The default is to block parent cancellation acceptance until reconciliation
produces a durable effect outcome. A component may opt into a second explicit
policy:

- the child accepts the lifecycle/control terminal
  `cancelled_pending_reconciliation(obligation_id)`;
- that terminal does not terminalize the effect; it binds a mandatory durable
  reconciliation obligation and the ambiguous effect identity;
- ordinary child work Custody is released/transferred or expires, while the
  separate reconciliation target remains eligible for fenced Custody;
- late reconciliation can update effect/WBC history and the causal explanation
  but cannot reopen or rewrite the accepted parent terminal;
- any later compensation requires a fresh typed decision and current action
  envelope.

The chosen policy is declared at the effect/component boundary and mutation
tested. An undeclared choice fails closed. This avoids both indefinite hidden
stall and the fiction that an unknown external action has finished.

### 4. Migration decisions

Adopt and strengthen the Oracle rule:

- A standing compatibility declaration establishes **eligibility**, never
  permission.
- Every application to a run/semantic occurrence creates one accepted RA
  migration decision binding from/to program, policy, component, state schema,
  dependency lock, prompt/tool, Plan Contract, and WBC versions as applicable.
- The state transform is applied once by CAS, records input/output digests and
  migration implementation/version, starts the required new subject/WBC
  attempt, and validates current Custody.
- The exact migration decision is consumed once. Blanket rules cannot produce
  silent resume, even when acceptance is automated by declared policy.

### 5. Repair/action validation failure

Do not adopt the Oracle's unconditional void-on-rejection rule. Classify the
failure before any body/effect intent:

| Failure class | Decision disposition |
|---|---|
| Actor-local placement, stale worker, stale/missing lease or epoch, or host unavailability; decision validity predicate still holds; decision unconsumed | Record the rejected dispatch attempt. M11 recovery may reacquire/reassign and redispatch the same immutable decision before its expiry. The scheduler cannot change its route or policy. |
| Canonical semantic precondition changed, repair is no longer legal, capability/grant expired, executable/product/WBC binding drifted, or the decision's validity predicate fails | Atomically record `decision.invalidated`; it can never be redispatched. A new typed request and accepted decision are required. |
| Decision already consumed or body/effect intent started | Never redispatch the decision. Any continuation uses the authored retry/recovery/effect-reconciliation protocol with a distinct attempt. |

Every validation rejection records its class, canonical facts, and consumption
state. The classification belongs to the admitted M11 action/recovery contract,
not Native scheduler heuristics.

### 6. Agentic budget exhaustion

Adopt the Oracle rule:

- Inner LLM/tool calls reserve and charge durable token/cost/time/call budgets
  atomically before invocation, including retries.
- No inner call may start after exhaustion.
- A final summarization/finalization call is legal only if a named reserve was
  declared and admitted at phase entry; it is charged like every other call.
- On exhaustion the phase emits its declared closed lifecycle/control result
  (normally `budget_exhausted`) without a hidden call or outer route hint.
- Any unused declared reserve is released only under the published accounting
  rule at terminal acceptance.

### 7. Duplicate human answers

Adopt with an idempotency distinction:

- One distinct answer submission wins the accepted-decision CAS and is
  consumed once by resume.
- A replay with the same submission/idempotency ID returns the original result
  and does not manufacture a second semantic answer.
- A different submission after a winner is durably recorded as
  `human_answer.rejected_late`, with schema/version, submission identity,
  arbitration reason, and privacy-safe digest/artifact reference. It is
  evidence, not an accepted route decision.
- Rejected-late facts survive projection rebuild and are included in
  arbitration conformance; they can never resume or alter the winner.

### 8. Golden-contract provenance

Resolve “generated from or checked against” now; it is not adequate normative
language.

- `GOLDEN_TRACE_CONTRACT.md` is the human-reviewed normative scenario and
  invariant contract. It declares scenario inputs, business outcomes,
  ordering/causal constraints, forbidden facts, and mutations; it is not a
  complete executable route table.
- An **independent static source oracle** derives semantic occurrences, source
  spans, named policies, and structured-control relations from canonical
  `.pypeline` source and scenario inputs. It must not call the production
  lowerer or use production runtime traces as expected output.
- Runtime adapters export raw primary-store facts. A separately implemented
  normalizer/comparator checks raw multiplicity first, then contract-approved
  normalization, then source/runtime/golden relations.
- Production lowering may produce the actual execution trace but never the
  expected trace. The production trace adapter and independent verifier may
  share versioned schemas, but not deduplication, event-elision, or ordering
  logic.
- The volatile-field allowlist is versioned in the golden contract. Unknown
  fields are rejected rather than silently dropped.

S1 owns the schema, source-oracle contract, comparator, and synthetic/raw-level
mutation tests. S2 integrates them with the neutral production runtime and
must make GO-0 green. This keeps S1 executable without making it depend on S2's
new primitives.

## M11 admission and migration-boundary decisions

### 9. Executable M11 capability checklist

The existing content-addressed completion manifest is necessary but not
sufficient. S1 must run an executable capability audit against the exact
accepted M11 revision. At minimum it proves:

1. external writer registration for all three execution planes and one shared
   enforce-mode validator;
2. accepted RA decision identity and single-consumption/CAS semantics durable
   across restore;
3. action-envelope support for opaque, equality-checked product/program/policy/
   lock/prompt/tool/Plan-Contract digests;
4. exact per-action/per-effect Custody targets, transfer/reclaim, and a
   production-shaped scale/capacity fixture adequate for delivery fanout;
5. exact-version WBC attempts, checkpoints, effect ambiguity, reconciliation,
   causal queries, and terminal uniqueness;
6. backup-restore-resistant fence/epoch and all Native-introduced durable
   consumption/ledger records either inside that rollback boundary or covered
   by an equivalent restore proof;
7. canonical acceptance-time repair precondition revalidation and the failure
   classification above;
8. installed-artifact/pinned-version resolution and cross-host handoff needed
   by Native action admission.

Native owns canonical Plan Contract normalization and computes its digest. M11
need only bind and compare that opaque versioned field; it must not interpret
`provides`, `assumes`, or `pre_existing`.

Comparison history does **not** require an M11 comparison namespace if it never
enters M11's canonical stores. Therefore the Oracle's comparison-class item is
not unconditionally an upstream feature requirement.

If any required capability is absent, S1 emits a typed
`blocked_on_m11_point_release` result and the chain stops. It must not retry
indefinitely under the current global retry policy, add a Native side store, or
implement a local compatibility facade. The accepted M11 point release then
becomes the new content-addressed prerequisite.

### 10. Comparison isolation

Use the stronger of two mechanically proven forms:

1. M11 natively supports an `authority_class=comparison` that canonical
   admitted queries and writers exclude at storage/API level; or
2. preferred when M11 has no such class: the candidate has no RA grant,
   Custody client, admitted WBC/checkpoint/effect/terminal writer, or production
   effect capability, and writes only an immutable signed comparison artifact
   to a physically/logically separate artifact namespace unavailable to
   canonical resume, decision, WBC, projection, and proof queries.

In both forms separate credentials and fail-closed validator mutations prove
that a comparison process cannot call an admitted writer. Comparison records
cannot be relabeled or promoted; post-cut admitted execution starts a fresh
attempt or consumes an explicit migration decision. A separate comparison
artifact store is not a parallel RA/Custody/WBC store.

### 11. Plane-writer registration adapters

The Oracle is right that ownership is missing. Assign it as follows:

- S1 inventories every action/effect-capable entry point in `arnold.execution`,
  `NativeProgram`, and the retained runtime-envelope/legacy plane and proves
  the M11 external-registration capability.
- S2 implements product-neutral entry adapters/guards that construct the
  complete admitted envelope, register each plane writer, and invoke the one
  shared validator. The adapter can serialize and validate; it cannot select a
  product route.
- GO-0 injects an unregistered writer and a plane-specific validator bypass for
  every plane; all fail before body/effect intent.
- S3A onward bind each concrete slice's exact old/candidate writer cohort and
  decision consumer in the cutover receipt.

No authority cut may discover writer registration as follow-up work.

### 12. Resume-plane selection

The Oracle correctly moves this before S4, but an editable “resume selector
registry” would itself become hidden route authority. S3A must instead land:

- one canonical, digest-bound `execution_plane_binding` in the admitted run or
  migration record for each migrated semantic scope;
- a pure selector that reads that binding and the checkpoint's pinned
  executable, then returns the only eligible execution plane;
- a shared resume gate used by every CLI/auto/native/legacy resume entry point;
- mutations proving legacy cannot resume a native-bound scope, native cannot
  resume a legacy-bound scope, and no selector can change the semantic cursor
  or fabricate a migration.

Changing the binding is an accepted migration/cutover decision, not a status
edit. S3A needs this for prep clarification; S4 consumes it for tiebreaker and
mixed-version human resumes.

### 13. Front/back seam bridges

There is not one bridge; every partial cut creates an outgoing seam. The
milestone that cuts a slice owns its bridge and the next milestone removes or
replaces it:

- S3A: native prep/plan/critique to the retained legacy gate;
- S3B: native gate/revise/planning-cycle to retained legacy
  tiebreaker/finalize;
- S4: native finalize to retained legacy delivery;
- S5: native delivery to retained legacy control/auto surfaces until S6.

Each bridge is generated from a closed typed boundary. The upstream accepted
decision already names the downstream entry target; the bridge only serializes
the immutable payload/action envelope and records a compatibility handoff. It
cannot compute `next_step`, inspect status to choose an entry, or emit an
alternate outcome. It is registered as a controlled writer when it writes
durable state, has an explicit expiry/removal milestone, and has source/bridge
mutation tests. S7 requires zero surviving route-capable seam bridges.

### 14. Platformization handoff

Add a classification field to the S1 normative row schema. S2 through S6 fill
it from actual implementation evidence as one of:

- core runtime primitive;
- stable reusable-pattern candidate;
- experimental/two-consumer-unproven candidate;
- Megaplan-specific behavior.

S7 emits a content-addressed Native-to-Platformization handoff manifest
containing the candidate/dependency inventory, exact typed port/outcome/policy/
effect contract snapshots, source-to-runtime golden adapters, zero-Megaplan-
import proof for generic primitives, coupling evidence, known exclusions, and
the classification rationale. The Platformization epic must require this
manifest in addition to Native Parity's completion manifest. This is a
projection of already-required row evidence, not a new Native extraction
project.

## Milestone sizing and exact eight-milestone map

### Why seven is no longer credible

S1 currently combines prerequisite verification, substrate inventory, a new
semantic/identity/proof model, false-pass checkers, a machine golden oracle,
proof-map plumbing design, deterministic-Python and diagnostics contracts,
action-envelope and Plan Contract binding, payload/pin retention, comparison
isolation, M11 restore/repair proofs, writer inventory, and measured DX gates.
It fits one milestone only if production integration is explicitly deferred to
S2/GO-0; otherwise it needs its own split.

Current S3 is not one vertical slice. It contains:

- prep clarification and cross-host reentry;
- plan artifact boundaries;
- adaptive critique selection, evaluator retry, dynamic fanout, per-item
  fallback, and reducer;
- the densest current semantic owner: gate signal building, normalization,
  reprompt/downgrade, preflight/backstops, cap/no-progress/severity decisions,
  debt effect, and state transitions;
- revise and the bounded outer loop;
- WBC producer relocation and deletion/fencing across component, handler,
  manifest, `_core`, CLI, and auto surfaces;
- comparison isolation, all-plane writer proof, installed execution, two
  golden families, and an agentic-phase proof.

The current codebase map independently identifies `handlers/gate.py` as one of
the largest product-policy owners. Folding gate/revise into S4 would combine it
with researcher/challenger fanout, tiebreaker decisions, finalize fallback,
multiple human gates, cross-host resume, and v1/v2 asset retention. That is not
a safe two-week milestone. The only honest decomposition is eight milestones.

### Exact map

| Ordinal | Chain label | Scope and blocking handoff |
|---|---|---|
| 1 | `s1-custody-capability-admission-semantic-contract` | M11 manifest plus executable capability audit; normative identities/rows; independent golden/source-oracle contract; synthetic raw-level comparator mutations; current false-pass baseline; comparison and DX contracts. Production trace integration is not an S1 exit. |
| 2 | `s2-control-primitives-writer-registration` | Generic durable constructs, deterministic compiler/runtime, local harness, LLM/payload discipline, agentic protocol, all-plane registration adapters, neutral production trace integration; **GO-0**. |
| 3 | `s3a-prep-plan-critique-native-cutover` | Execution-plane binding/resume gate; prep clarification, plan, critique selection/retry/dynamic fanout/fallback/merge; producer relocation; comparison isolation; outgoing typed seam to legacy gate; **GO-1A** installed cutover receipt. Agentic critique proof belongs here. |
| 4 | `s3b-gate-revise-front-half-cutover` | Gate signals/worker/normalization/reprompt/backstops/debt, bounded critique/gate/revise planning cycle, named planning-loop outcome, remaining front-carrier deletion/fencing, outgoing typed seam to legacy tiebreaker/finalize; `NP-GT-001/002`; **GO-1B**, which closes GO-1. |
| 5 | `s4-tiebreaker-finalize-durable-reentry` | Existing S4 scope; consume the S3A resume gate; exact migration decisions; duplicate-human arbitration; remove S3B seam and own finalize-to-legacy-delivery seam; `NP-GT-003`. |
| 6 | `s5-reusable-delivery-cycle` | Existing S5 scope plus precise named-exit unwind and cancellation/effect-ambiguity disposition; remove S4 seam and own delivery-to-control seam; `NP-GT-004/005`; **GO-2**. |
| 7 | `s6-override-auto-control-adoption` | Existing S6 scope plus repair rejection classification and full arbitration index; remove S5 seam; **GO-3**. |
| 8 | `s7-native-topology-conformance` | Raw-level independent proof hardening, restore drill for every Native durable store, all golden/mutation/install forms, zero seam bridges, Platformization handoff manifest; **GO-4**. |

GO-1 becomes a composite binary gate:

- GO-1A failure leaves the old prep/plan/critique producer authoritative.
- After GO-1A passes, that cut is not rolled back by a later GO-1B failure;
  only the still-legacy gate/revise slice remains old-authoritative.
- GO-1B failure blocks the completed front-half declaration and S4.

This is more precise than the current all-or-nothing sentence “GO-1 failure
keeps the old front-half producer authoritative,” which is false once slices
are cut independently.

### Migration of the current S3 label and brief

The chain has not legitimately launched before the M11 prerequisite, so the
combined S3 can be replaced before execution rather than migrated in-flight.
Make these editorial changes:

1. Remove chain label `s3-front-half-native-slice` and its dependency edge.
2. Add the `s3a-...` and `s3b-...` labels above with `S3B -> S3A -> S2`.
3. Make existing S4 depend on S3B; S5-S7 retain their current dependency order.
4. Replace active brief
   `briefs/s3-tiebreaker-replan-native.md` with:
   - `briefs/s3a-prep-plan-critique-native-cutover.md`;
   - `briefs/s3b-gate-revise-front-half-cutover.md`.
5. Move the combined old brief to a clearly historical appendix such as
   `briefs/archive/s3-front-half-combined-pre-round3.md`, or delete it after all
   unique clauses are assigned. It must not remain described as an active
   launch contract.
6. Update README, canonical plan, golden adoption table, North Star receipt
   language, proof-map milestone registry, final validator expected labels, and
   chain notes from seven to eight milestones.

If a chain state unexpectedly exists, do not edit the spec expecting sticky
completed state to replay. Stop it, preserve any accepted receipts explicitly,
and start the new spec/state after adjudicating whether they are reusable. The
current unmet launch prerequisite should make this a pre-launch edit.

## Required artifact amendments

The authoritative amendment pass should update:

- representation report §§5.2, 5.3, 5.6, 9.1, and 14.3-14.6;
- canonical plan ownership, S1/S2, split S3A/S3B, migration graph, blocking
  regressions, and final gates;
- North Star retry/attempt terminology and eight-milestone receipt language;
- golden contract event vocabulary, global assertions, `NP-GT-002`,
  `NP-GT-003`, `NP-GT-005`, mutation suite, provenance, and adoption table;
- `chain.yaml`, README, active briefs, proof-map schema, and final validator
  milestone-label expectations;
- Platformization ticket dependency/handoff and its same-child retry language.

No new generic race/quorum primitive is required in Native Parity. Open-ended
streams remain out of scope. Restore-resistant M11 semantics remain upstream;
Native Parity audits and consumes them rather than implementing a local copy.

## Bottom line

The Oracle materially improved the specification, but copying it verbatim
would introduce two new errors: treating retryable attempt terminals as final
child terminals, and invalidating valid unconsumed decisions for actor-local
dispatch failures. With those corrected, the new rules close real ambiguity in
loop unwinding, effect cancellation, migration, human arbitration, proof
provenance, and partial-cutover ownership.

The work no longer fits the current seven-milestone chain honestly. Eight
milestones, with S3 split at the critique/gate boundary and S1 runtime
integration moved to S2/GO-0, is the smallest safe schedule.
