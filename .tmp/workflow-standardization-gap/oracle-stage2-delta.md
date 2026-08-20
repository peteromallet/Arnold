# Oracle Stage 2 delta audit

## Verdict

The amended Platformization ticket and representation report have the right
architecture and do not need another sprint. The oracle feedback finds no
missing platform layer, but it does reveal several places where a broad rule is
present without a closed executable contract.

Three items are already adequately covered: cancellation/deadline propagation
at principle level, non-repeatable effect replay at principle level, and the
developer-experience surfaces. They need sharper test matrices or numeric gates,
not redesign. The materially underspecified set is: the root-host adapter; the
separation of business outcomes from lifecycle/control terminals; outcome-
condition contracts; parent-loop durable state transitions; substitution
limited to new instances absent migration; normalized partial-order trace
equivalence; child-custody release; and race/quorum behavior. The oracle also
finds three bounded authoring/composition holes—typed exits to named enclosing
loops, typed reconfiguration at the same semantic cursor, and a durable agentic
phase boundary—and several deterministic-data constraints that must be made
normative to prevent handler relapse.

All amendments fit inside S1 contract closure, S2 enforcement, S3 reusable-
pattern/local-harness proof, S4 adversarial consumer/substitution proof, and S5
certification. The two-consumer sequencing and product-neutral boundary should
remain unchanged.

## Delta classification

| Oracle concern | Current coverage | Classification | Smallest amendment |
| --- | --- | --- | --- |
| Root-hosting adapter | The ticket distinguishes child typed return from root terminal acceptance. The report repeatedly says a child terminal cannot terminate the root. Neither defines the adapter that hosts a component as a root and converts its local return into an RA-governed workflow terminal. | **Material gap.** The distinction exists; the executable join does not. | Define a root-host adapter as the sole layer allowed to map a component-local terminal into a proposed root terminal, subject to root outcome mapping, terminal arbitration CAS, current RA/Custody/WBC validation, and one accepted root terminal. |
| Two-layer lifecycle terminal model | S1 defines one lifecycle and distinguishes child return from root terminal, but does not separate business typed outcomes from lifecycle/control terminals. | **Material gap.** | Define orthogonal result layers: declared business outcomes versus closed lifecycle/control terminals such as cancelled, deadline/budget exhausted, infrastructure failure, and compensation failure/completed. Hosting then maps a component's permitted result to its parent or, through the root adapter, to a product terminal. |
| Outcome-condition contracts | Typed output/outcome schemas and exhaustive parent handling are strong. They say what values may be returned, not the semantic conditions/evidence under which each outcome is legal, or whether an apparent outcome is an internal suspension versus a returned business result. | **Material gap.** Closed labels alone cannot establish behavioral substitution. | Add per-outcome postconditions/invariants, required evidence, and emission mode (`return`, `suspend_then_continue`, or declared lifecycle/control terminal). Static validation checks exhaustive bindings; runtime terminal admission checks the selected condition; conformance mutates results/evidence to prove illegal outcomes fail closed. |
| Non-idempotent child effect under parent retry | The ticket records effect intent/outcome and forbids silent re-fire; the report says parent retry cannot repeat a durable child effect. It does not close the case where parent retry creates another logical child action or encounters intent-without-outcome. | **Partially covered; needs a normative retry matrix.** | Define resume-same-child versus new-child-generation semantics. A parent retry resumes/reuses the original child's durable terminal/effect outcome by default. A non-idempotent effect may execute again only as an explicitly new logical action with a new semantic occurrence, fresh authority/custody, and a declared repeat policy; ambiguity must reconcile first. |
| Parent loop durability | Composition mentions checkpoint cursor joining, stable generations, and retry scope. No transition specifies when parent loop generation/accumulator/decision state is persisted relative to child start and terminal consumption. | **Material gap.** | Define a durable loop ledger/state machine: persist generation and child key before child admission; record one child-terminal consumption CAS; persist accumulator and next/exit decision before launching the next generation; replay resumes at the first incomplete transition. |
| Substitution without checkpoint migration | S4 asks for implementation substitution and separately for upgrade/migration paths; closure says active runs pin or migrate. It does not state that black-box substitutability alone authorizes only new instances when durable state/checkpoint representation differs. | **Material ambiguity.** | Split certification into `new_instance_compatible` and `resume_compatible`. A substitute may serve new instances after behavioral conformance. It may resume an existing instance only with identical durable schemas/semantics or an admitted checkpoint/state migration. Otherwise the old implementation remains pinned or the run quarantines/restarts explicitly. |
| Normalized partial-order trace conformance | The ticket requires normalized golden traces and observable substitutability; sibling wall-clock order is deliberately variable. “Normalized” is undefined and could sort away multiplicity, illegal causality, or races. | **Material gap.** | Define trace equivalence as event multiplicity plus per-instance total orders plus declared cross-instance happens-before edges and allowed unordered sibling sets. Normalization may erase approved volatile fields only; it may not deduplicate, reorder causal edges, or hide rejected/late events. |
| Child Custody release on parent cancellation | Cancellation propagation and exact child Custody targets are covered, but release/expiry behavior during cancellation is not explicit. | **Material edge-case gap.** | Parent cancel first fences new child admissions, records cancel intent, propagates child cancel, and waits for terminal/release or lease expiry before parent cancel acceptance. Release must be epoch-checked and idempotent; a stale child cannot act after release/reassignment. Parent terminal must not imply a fictional child release. |
| Race/quorum semantics | Fanout/fanin behavior, terminal arbitration, sibling failure, cancellation, and reducers are named. No required race/quorum policy describes winners, late results, partial success, or simultaneous threshold/cancel/timeout events. | **Material gap for reusable panels/fanout.** | Add a closed `JoinPolicy`: all/any/quorum/reducer threshold, failure tolerance, tie precedence, loser cancellation, late-result disposition, and terminalization condition. Every competing transition uses one CAS/arbitration order and records accepted plus rejected-late facts. |
| Cancellation/deadline/budget propagation | S1 already covers cancellation/deadline context and propagation; report adds token/cost budget. Budget composition and charging/refund rules are not explicit. | **Mostly covered; sharpen.** | State that children receive narrowed—not widened—deadline/cancellation/capability/budget scopes. Define reservation/charge/release for fanout, retries, cache hits, cancellations, and late completions; parent completion waits for the policy-required child dispositions. |
| Measurable DX gates | Stable diagnostic codes/spans/rewrites, source maps, tracebacks, local production-semantics harness, and a latency budget are now present. The ticket does not define the corpus, benchmark shape, percentile, or numeric threshold. | **Surface covered, gate not measurable yet.** | Freeze a versioned DX benchmark and numerical SLOs in S1; enforce them in S2/S3 and publish results in S5. At minimum measure diagnostic correctness, source-map fidelity, no-network local test determinism, compile/test latency, and escape-hatch regressions. |
| Typed exit to an enclosing loop | Typed outcomes and loop policies exist, but no structured result can leave a rework loop and address a named enclosing planning/critique loop without a sentinel or exception. | **Material expressiveness gap.** | Add a typed, statically resolved enclosing-loop transition whose target loop and outcome vocabulary are declared at the call site and represented in checkpoints/traces. |
| Typed reconfiguration | Policy bindings and evolution digests exist, but live set-model/set-robustness-style changes could still become ambient mutation or opaque continuation. | **Material expressiveness gap.** | Add a typed reconfigure transition: checkpoint current cursor, validate/accept a typed config delta, recompute admitted policy/executable identity, and resume that same semantic cursor under a new explicit generation. |
| Durable agentic inner loop | LLM/tool invocation identity and tool effects are covered, but runtime model-determined tool-call counts cannot be statically expanded into topology. | **Bounded declared-boundary gap.** | Permit a durable agentic phase boundary with a closed outer outcome contract and explicit WBC protocol; every internal tool effect still uses intent/outcome and budgets, and the phase cannot own outer product routing. |
| Deterministic decision data | The durable-Python profile broadly forbids ambient nondeterminism. It does not explicitly close host-dependent `Path`, arbitrary float, unordered-container, completion-order reducer, mutable fanout binding, or open exception-set paths. | **Material hardening.** | Require schema-qualified canonical decision values, keyed-multiset reducers, frozen digest-bound fanout bindings, and closed typed error outcomes; live config affects routing only through typed reconfiguration. |
| Scheduler versus route authority | Hidden route authority is prohibited, but the scheduling boundary is not positively defined. | **Small but important clarification.** | Scheduler/auto surfaces may dispatch already accepted work; retry, escalation, cost/stall, reconfigure, and terminal choices must be accepted source-authored decisions. |
| Outcome payload smuggling | Unhandled outcomes fail closed, but a product could encode a new route in a non-vocabulary field of an existing outcome. | **Material negative-test gap.** | Route selection must depend only on declared outcome/decision discriminants. Mutate other payload fields and prove no route divergence unless an explicitly declared decision consumes them. |

## Exact sprint and gate ownership

### S1 — close the normative contracts

Add these clauses to Component Lifecycle and Composition Algebra v1:

1. **Business/control result contract plus host terminal contract.** Every
   component instance has one lifecycle:

   ```text
   admitted -> running -> retrying/suspended/cancelling/compensating
            -> one local typed terminal
   ```

   The terminal result is a tagged union of declared **business outcomes** and
   closed **lifecycle/control terminals** (`cancelled`, deadline/budget
   exhausted, infrastructure failure, compensation disposition). Internal
   suspension is a lifecycle transition, not automatically a returned business
   outcome. A host consumes the terminal: a nested host binds it to a parent
   port, while the root-host adapter alone maps an eligible result to a proposed
   root product terminal and performs terminal arbitration plus accepted-
   decision/authority/custody/WBC validation. A component implementation cannot
   directly emit an accepted root terminal.

2. **Outcome-condition contract.** Each closed outcome declares:
   - payload schema;
   - semantic postcondition/invariant;
   - required durable evidence classes;
   - effect/compensation completeness requirements;
   - whether the outcome is returned, produced only after internal suspension,
     retryable/resumable, terminal-local, or eligible for root mapping.

   Product-specific predicates remain in product bindings, but their schema and
   evaluation protocol are standardized.

3. **Parent retry and loop durability contract.** Define same-child resume,
   explicit new-child generation, terminal consumption CAS, loop generation,
   accumulator/checkpoint state, next/exit decision, and crash recovery at each
   edge. New generation is not an alias for retry and receives a distinct
   semantic occurrence.

4. **Race/quorum and cancel contract.** Define `JoinPolicy` and deterministic
   arbitration precedence for threshold reached, child failure, parent cancel,
   deadline, budget exhaustion, and late success. Define child Custody release/
   expiry acknowledgements and parent terminal preconditions.

5. **Resource-scope algebra.** Capabilities, deadline, cancellation, and token/
   cost/resource budgets may be inherited or narrowed, never silently widened.
   Specify reservations, committed charges, release/refund, retry charging,
   cache-hit accounting, and late-completion treatment.

6. **Two compatibility classes.** `new_instance_compatible` is established by
   boundary/lifecycle conformance. `resume_compatible` additionally requires
   durable checkpoint/state/effect compatibility or an admitted migration.

7. **Partial-order trace contract.** Standardize event identity, multiplicity,
   per-component sequence, parent/child/effect happens-before relations,
   allowed unordered sets, and the exact volatile fields normalization may
   erase.

8. **Missing deterministic composition primitives.** Add a typed transition to
   a declared named enclosing loop, a typed checkpointed reconfiguration that
   resumes the same semantic cursor under new admitted bindings, and a declared
   durable agentic phase boundary with closed outer outcomes and effect-safe
   internal tool calls. Deliberately reject open-ended item streams in this
   epic, with a diagnostic that points to a future event-queue port rather than
   an opaque polling loop.

9. **Canonical decision-data contract.** Route-bearing decisions accept only
   schema-qualified canonical serialized values; exclude host-dependent paths,
   arbitrary float behavior, unordered containers, and open exception classes.
   Fanout freezes digest-bound bindings at admission, and reducers consume a
   canonically keyed multiset rather than completion order.

Gate S1 on executable reference models and invalid corpora for all nine. Add
model-check scenarios for local-terminal/root-terminal confusion, illegal
outcome conditions, retry versus new generation, crash at every loop-ledger
edge, simultaneous quorum/cancel/deadline/budget events, stale release epochs,
trace normalizers that hide duplicates or causal inversions, invalid enclosing-
loop targets, ambient reconfiguration, agentic phases that choose outer routes,
completion-order reducers, mutable sibling bindings, and open exception routing.

S1 also owns the DX measurement specification. Freeze a representative workflow
corpus and machine class plus numeric thresholds before S2 begins. The minimum
metrics are:

- 100% of negative-corpus diagnostics carry the expected stable code, authored
  source span, semantic path, and supported rewrite;
- 100% of injected runtime faults identify the authored call site and component
  instance;
- compile and no-network local-test p50/p95 targets on named small and reference
  compositions;
- byte-for-byte or contractually normalized repeatability across repeated local
  runs;
- zero accepted hidden-route escape-hatch mutations;
- every route divergence in golden runs attributable to a declared outcome or
  decision discriminant, including payload-field mutation tests;
- zero diagnostic codes without a supported primitive/example or an explicit
  deliberately-unsupported boundary recipe; and
- a timed ten-task author simulation over representative legal and illegal
  edits.

The actual latency numbers should be selected from a checked-in baseline and
then frozen in the S1 receipt, rather than guessed in prose.

### S2 — enforce host, retry, loop, resource, and trace semantics

Implement the root-host adapter separately from component bodies and the nested
host. The common lifecycle engine should still be shared; only the host terminal
mapping differs. Admission and static validation must reject a component that
can bypass its host, an outcome without a condition/evidence binding, and a
composition without a complete race/quorum or resource-propagation policy where
one is required.

Implement the durable parent-loop ledger and same-child/new-generation rules in
the production lifecycle path. Integrate child cancel with exact Custody target
and epoch release/expiry handling. Implement `JoinPolicy` through the same
terminal arbitration primitive used by root terminal races rather than through
ad hoc scheduler timing.

Lower named enclosing-loop exits and typed reconfiguration into explicit
checkpointed transitions, not sentinel payloads, exceptions, or mutable
context. Lower an agentic phase as one declared outer component occurrence with
its own closed result and WBC protocol while retaining distinct effect records
for internal tool actions. Reject open streams, noncanonical decision inputs,
completion-order route reducers, and open exception routing. Define the
scheduler boundary positively: scheduling may dispatch an already accepted
transition, but cannot choose retry, escalation, reconfiguration, cost/stall, or
terminal outcomes.

The normalized trace comparator must compare:

```text
event multiset with exact multiplicity
+ total order inside each component/effect attempt
+ declared cross-attempt happens-before edges
+ accepted/rejected arbitration facts
+ allowed unordered sibling equivalence classes
```

Gate S2 on exhaustive crash/race injection, including:

- local terminal recorded before/after root-host proposal and acceptance;
- parent crash before child start, after child terminal, before/after terminal
  consumption, and before/after next loop generation;
- parent retry after durable non-idempotent outcome and after ambiguous intent;
- parent cancellation before child admission, during effect, after child
  terminal, during release, and after Custody reassignment;
- quorum and deadline/budget/cancel arriving in every meaningful order;
- trace mutations that duplicate, drop, causally invert, or falsely sort events;
- payload mutations that attempt to smuggle a new route through an existing
  outcome;
- local versus installed normalized lifecycle/admission trace identity for the
  same recorded boundary results; and
- the S1 diagnostic/source-map and timed author benchmark meeting their frozen
  thresholds.

### S3 — prove the reusable patterns and local harness

Use the evaluator panel to prove quorum/race semantics, the bounded refinement
loop to prove the parent-loop ledger, the human gate to prove cancellation and
Custody release around suspension, and the effect-safe action to prove parent
retry over both terminal and ambiguous non-idempotent effects.

Exercise named enclosing-loop exits in the bounded refinement pattern, typed
reconfiguration without ambient context mutation, and a small agentic phase
fixture whose variable tool-call count cannot alter its closed outer routing.

The production-semantics local harness should expose deterministic controls for
each race edge, not merely a “run concurrently” helper. Gate S3 on the same
pattern run under:

- same-child resume and explicit new generation;
- all/any/quorum joins with late child results;
- parent cancel/deadline/budget exhaustion at each lifecycle edge;
- checkpoint/replay at every parent-loop transition;
- partial-order trace assertions with multiplicity;
- the frozen no-network local-test p50/p95 latency and repeatability targets;
- route-inert payload mutation; and
- local/installed normalized lifecycle and admission trace identity given the
  same recorded boundary results.

No product-specific Megaplan outcome predicates should move into the shared
package; Megaplan supplies them through the standardized outcome-condition
binding.

### S4 — make substitution and the second consumer adversarial

Split the existing implementation-swap proof:

1. Run the replacement for **new instances** under the same descriptor and
   outcome-condition/trace conformance contract.
2. Attempt to resume an old suspended instance with no migration and prove it
   is rejected unless durable schemas and semantics are identical and declared
   resume-compatible.
3. Add an admitted migration and prove one provenance-bearing transformation,
   new attempt identity where required, then successful resume.
4. Remove the old artifact without a supported migration and prove quarantine,
   not fallback to latest code.

Have the unrelated consumer exercise a join policy and outcome condition that
Megaplan does not use, plus a parent cancellation during a live child/effect.
Require both products to pass the same partial-order comparator while allowing
only their declared outcome predicates and policy values to differ.

Gate S4 separately on `new_instance_compatible` and `resume_compatible`
receipts; one must never imply the other.

### S5 — certify and govern the sharper profiles

Extend the conformance manifest with optional/required profiles for:

- root-hostability versus nested-only components;
- outcome-condition evaluation;
- retry-safe non-idempotent effects;
- durable parent loops;
- join/race/quorum;
- cancellation/Custody release;
- resource-budget propagation;
- new-instance and resume compatibility;
- partial-order trace equivalence.
- named enclosing-loop exits and typed reconfiguration;
- durable agentic phases and canonical decision data.

Publish the frozen DX corpus, machine/environment description, actual p50/p95
measurements, diagnostic/source-map pass rates, repeatability result, and escape-
hatch mutation result. Registry stability must fail when an applicable semantic
profile or measurable DX threshold is missing.

## Acceptance additions

Fold these into the existing acceptance suite rather than adding a new suite:

1. Component-local terminal cannot bypass the root-host adapter; nested
   terminal never becomes root terminal without explicit mapping and accepted
   arbitration.
2. Every closed outcome satisfies its declared condition/evidence contract;
   counterexample payload/evidence pairs fail closed.
3. Parent retry after child effect terminal consumes the original outcome;
   ambiguous non-idempotent effects reconcile before progress; explicit repeats
   have new logical action identity.
4. Parent-loop state survives crashes at every generation/child-terminal/
   accumulator/decision boundary without skipped or duplicated generations.
5. New-instance substitution succeeds independently of resume compatibility;
   old checkpoints require identical durable semantics or admitted migration.
6. Partial-order trace comparison preserves multiplicity, per-instance order,
   causality, arbitration, and allowed sibling nondeterminism.
7. Parent cancel fences child admission/action and reaches accepted parent
   terminal only after the declared child terminal/release/expiry disposition.
8. All/any/quorum policies resolve simultaneous success/failure/cancel/deadline/
   budget events deterministically and retain rejected-late evidence.
9. Child scopes never widen parent cancellation, deadline, capability, or
   budget; reservation/charge/release totals reconcile.
10. DX conformance meets the S1-frozen diagnostic, source-map, repeatability,
    escape-hatch, and latency thresholds.
11. Named enclosing-loop exits and typed reconfiguration survive checkpoint/
    replay without sentinels, exceptions, or ambient mutation.
12. Agentic phases may vary internal tool-call count but cannot emit undeclared
    outer routes; every tool effect and budget charge remains durable.
13. Route divergence is attributable only to declared outcome/decision
    discriminants; unrelated payload mutation is route-inert.

## Oracle findings that should not expand Stage 2

- The omitted numbered transition list in oracle Q2 is not available, so its
  references to items 2, 3, 5, and 7 cannot support precise amendments. Do not
  invent them.
- Shadow comparison namespaces, fencing `workflow_data.py`, and proving all
  transitional execution planes use the single validator belong to Native
  Parity migration, not Platformization.
- Disaster-recovery fence/epoch monotonicity belongs to the assumed completed
  M11 RA/Custody substrate. Stage 2 should consume its conformance receipt, not
  reimplement it.
- Repair-request fields remain non-authoritative under the existing evidence
  rule; no new Stage 2 mechanism is needed.
- If a consumer contract such as Megaplan's Plan Contract can change evidence
  requirements, its content fingerprint must enter the admitted consumer-
  contract/policy digest and checkpoint pins. The platform standardizes that
  generic pinning slot; it does not standardize Megaplan's Plan Contract shape.

## Final recommendation

Amend the current five sprints, not the architecture. The most important
conceptual sharpening is:

> A reusable component terminates locally; a host interprets that terminal.
> Only the root host can propose a workflow terminal, and it still must pass
> authority and arbitration. Recomposition is safe only when outcome
> conditions, durable parent state, effects, resource scopes, Custody release,
> and trace causality survive the new shape. Behavioral substitution applies to
> new instances by default; resuming old instances is a stronger, separately
> certified claim.
