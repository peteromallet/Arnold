# Oracle answers: durable summary for delta review

Date: 2026-07-21

This is a concise durable summary of the user's pasted oracle answers. It is an
audit input, not an authoritative plan or contract.

## Q1 — durable-Python safety and expressiveness

Verdict: safe-by-construction, but realistic expressiveness holes still create
handler-relapse pressure.

### Expressiveness findings

1. **Two-level typed exit:** `review-blocked -> replan` must leave a rework loop
   and re-enter a named enclosing critique/planning loop. Sentinel variables or
   exceptions are opaque. Add typed loop outcomes able to address an enclosing
   named loop.
2. **Race/quorum with loser cancellation:** first-wins or k-of-n over metrics,
   alerts, or human abort cannot be represented by exact-multiset fanout alone.
   Add a structured race/quorum reducer with declared cancellation semantics.
3. **Typed reconfiguration:** set-model/set-robustness then re-enter the current
   phase is a computed continuation and must not mutate ambient context. Add a
   typed reconfigure transition: checkpoint, accept a typed config delta, bind
   the changed policy/executable identity, and resume the same semantic cursor.
4. **Agentic inner loop:** runtime model-determined tool-call count cannot be
   statically lifted to topology. Permit a declared durable agentic phase
   boundary whose internal tool calls still use effect intent/outcome under one
   explicit WBC attempt/protocol. It may not own outer product routing.
5. **Open-ended item streams:** deliberately unsupported for Stage 1/2; reject
   opaque polling and point authors toward a future event-queue port.

### Remaining nondeterminism findings

- Decision inputs must be canonical schema-qualified serializable values;
  host-dependent `Path`, wall time, arbitrary floats, and unordered containers
  cannot enter control decisions.
- Parallel reducers receive a canonically keyed multiset, not completion order.
- Fanout freezes digest-bound bindings/context at admission; siblings cannot see
  in-place context changes.
- Topology catches only declared typed error outcomes, never an open set of
  exception classes from phase bodies.
- Live configuration flags cannot change control flow; admitted policy values
  change only through typed reconfiguration.

The oracle says ordinary authors stay inside only if every rejection maps to a
supported primitive or explicit declared-boundary/deliberate-non-support recipe.

## Q2 — adversarial suspension/crash/redeployment

The pasted answer says the conjunctive action envelope, version pins, and effect
protocol compose correctly for duplicate effects, repeated model calls, stale
worker epochs, and silent v2 resume.

However, it then refers to an omitted numbered list of underspecified
transitions and says “items 3, 5, and 7” are wrong-action paths and “item 2” can
lose an accepted human result. That numbered list was not present in the pasted
answer. These findings cannot be actioned precisely until the missing text is
provided.

## Q3 — authority/evidence crossing points

1. **Plan Contract pinning:** `pre_existing` changes evidence requirements; the
   applicable Plan Contract content/fingerprint must be admitted and checkpoint
   pinned so a mid-run edit cannot waive evidence.
2. **Shadow namespace:** inert comparison runs must write checkpoints/WBC/effect
   evidence into a quarantined, non-resumable namespace that canonical queries
   exclude.
3. **Scheduling versus routing:** auto-drive may schedule accepted work but may
   not choose retry/escalation/cost/stall transitions. Those are source-owned
   policy decisions. Define and test the boundary.
4. **Disaster-recovery monotonicity:** restoring RA/Custody storage must not
   resurrect old fences/epochs as current. Determine whether completed M11 owns
   restore-generation/monotonic recovery proof.
5. **Repair request trust:** request fields and projection-derived failed
   preconditions are hints only; acceptance revalidates journals/authority.
6. **Overlapping execution planes:** during convergence, no effect-capable path
   may bypass the single shared action validator. Prove this across
   `arnold.execution`, native runtime, and legacy runtime-envelope paths.
7. **`workflow_data.py` overrides:** robustness tables remain a current route
   authority until explicitly fenced/inert/deleted.

## Q4 — decomposition/recomposition

Identity and namespace machinery is judged strong. Remaining component-model
gaps:

1. Define a root hosting adapter mapping a component's closed return outcomes
   to accepted root product terminals; a `subworkflow` cannot implicitly run as
   root.
2. Define a normative two-layer terminal model: business typed outcomes versus
   lifecycle/control terminals such as cancellation, deadline exhaustion,
   infrastructure failure, and compensation.
3. Add outcome-condition contracts describing when outcomes may/must be
   emitted. A component that suspends internally on `needs_human` is not
   behaviorally substitutable for one that returns `needs_human`, even with the
   same vocabulary.
4. Specify non-idempotent effect behavior under parent retry and whether effect
   identity excludes logical retry generation for outcome reuse.
5. Make parent loop-state durability an explicit parent-side composition
   obligation.
6. Compatible implementation substitution applies to new instances by default;
   suspended instances remain pinned unless checkpoint migration is declared.
7. Define normalized partial-order trace compatibility so implementation speed
   or legal internal reordering neither breaks all substitutions nor makes trace
   conformance vacuous.
8. Define custody release/transfer ownership when a parent cancels a suspended
   child.

## Q5 — author experience and measurable gates

Three likely relapse mechanisms and proposed gates:

1. **Outcome evolution -> payload smuggling:** authors avoid adding a breaking
   outcome by hiding a route in an existing outcome's payload. Add mutations
   proving non-vocabulary payload fields cannot cause route divergence. Metric:
   every route divergence in golden runs is attributable to a declared outcome
   or decision value.
2. **Unsupported syntax without a supported alternative -> helper relapse:**
   every diagnostic code maps to a supported construct/example or explicit
   deliberately-unsupported declared-boundary recipe. Metric: zero rejection
   codes without a disposition; run a timed ten-task author simulation.
3. **Slow/unfaithful local harness -> admission bypass:** for each golden family,
   local and installed normalized lifecycle/admission traces must be identical
   given the same recorded boundary results, within a fixed virtual-time/latency
   budget.

The oracle recommends making these blocking safety gates, not post-parity polish.
