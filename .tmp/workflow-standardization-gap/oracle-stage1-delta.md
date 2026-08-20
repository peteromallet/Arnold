# Oracle answers versus amended Native Parity: Stage 1 delta

Status: read-only delta audit  
Date: 2026-07-21  
Inputs: `oracle-answers-summary.md` and the amended Native Parity North Star,
canonical plan, golden trace contract, README, chain, and seven active briefs

## Verdict

The amendments close most of the oracle's safety concerns: sole Python route
authority, fenced determinism, source-local diagnostics, durable LLM/tool
results and budgets, bounded checkpoint/artifact references, exact pinned
versions, namespace isolation, human suspension, closed outcomes/effects,
auto-drive demotion, and no-dual-write migration are now real gates.

The oracle still exposes **eleven bounded Stage 1 deltas**. They fit the current
S1/S2/S3/S5/S6/S7 ownership and do not require an eighth sprint:

1. named multi-level typed loop exits;
2. canonical schema-qualified decision inputs;
3. canonically keyed reducer inputs independent of completion order;
4. frozen digest-bound fanout bindings/context;
5. declared typed error outcomes versus open exception routing;
6. an explicit typed reconfigure/checkpoint/reentry primitive;
7. a declared durable agentic phase protocol;
8. Plan Contract content digest pinning;
9. quarantined non-resumable shadow namespaces;
10. named all-plane shared-validator and `workflow_data.py` bypass proof;
11. the three measurable anti-relapse ergonomics gates.

Race/quorum and open-ended streams should not be implemented speculatively in
Native Parity. Streams should be deliberate non-support. Race/quorum should be
deliberate Stage 1 non-support unless a concrete current Megaplan parity path is
identified, and otherwise remain a Stage 2 candidate requiring a real consumer.

Q2 cannot be fully audited: its referenced numbered transitions are absent.
The broad safety mechanisms are present, but “items 2, 3, 5, and 7” must not be
converted into inferred plan requirements without the missing text.

## Closed by the amendments or prior plan

| Oracle finding | Current disposition | Evidence in amended epic |
| --- | --- | --- |
| Python must be sole route authority | **Closed** | North Star deterministic/native definition; canonical machinery boundary; S3/S6 carrier deletion; S7 hidden-route mutations |
| Ambient nondeterminism and direct I/O | **Closed at the general boundary** | Versioned allow/deny contract, static/runtime guards, replay-twice proof, declared durable phase/effect boundary |
| LLM prompt/model/tool identity, budgets, caching, durable replay | **Closed** | S2 envelope; S4 long suspension; S7 prompt/schema/budget/cache/crash mutations; golden assertions 13 |
| Human suspension is first class | **Closed** | S2 primitive, S4/NP-GT-003 exact checkpoint/reentry and cross-host resume |
| Exact pinned v1 versus silent v2 | **Closed** | S1 retention rule, S4 mixed-version suspensions, S7 premature-GC tests |
| Bounded checkpoint payloads/artifact references | **Closed** | S1 classification, S2 enforcement, S7 invalid-reference mutations, golden assertion 14 |
| Identity/isolation | **Closed for Native** | Run plus semantic occurrence namespaces; S5 sequential/sibling/concurrent collision tests |
| Closed outcomes and declared effects/idempotency | **Substantially closed** | Closed decisions/terminals, WBC intent/outcome, GO-2 and NP-GT-004; only typed error-outcome wording remains |
| Auto-drive scheduling versus routing | **Closed** | S6 explicitly limits auto-drive to event consumption, liveness, and requests; forbids product route, retry/cap, model, resume, completion, cancellation, publication, delivery derivation |
| Repair requests/projection preconditions are hints | **Closed compositionally** | S6 explanation/preflight is request-only and inert; every positive action re-enters the admitted action/recovery boundary; forged projections cannot act |
| Configuration cannot change route invisibly | **Substantially closed** | S6 requires durable configuration effect and explicit reentry; NP-GT-006 pins changed policy digest; typed primitive shape still needs tightening |
| No dual-write migration/cutover | **Closed** | GO-0–GO-4, inert dual-read only, GO-2 effect proof, single authority cut |

## Genuine remaining Stage 1 gaps

### S1. Named multi-level typed exits

The plan has bounded loops with typed exits but does not specify how a child
loop returns `review_blocked -> replan` to a named enclosing planning/critique
loop without sentinel state or exception routing.

**Smallest amendment:** S1 freezes an addressed-exit contract
`Exit[target_loop, outcome, payload_schema]`; S2 lowers and validates named
ancestor targets and exhaustive parent handling; S5 proves the delivery/rework
loop's replan path returns to the named outer planning loop; S7 rejects
sentinel/exception/unknown-target/missing-handler mutations. Identity must show
the child terminal is a typed return, not a root terminal.

### S2. Canonical decision inputs

The deterministic boundary rejects ambient sources but does not require every
control-decision input to be a schema-qualified canonical serializable value.
Host-dependent `Path`, non-canonical float behavior, unordered containers, and
mutable object identity can therefore leak into a nominally pure decision.

**Smallest amendment:** S1 defines canonical decision-value types and encoding;
S2 rejects or normalizes host paths, floats, maps/sets, datetimes and custom
objects before a decision; the decision input digest is journaled and bound to
the accepted RA decision. S7 mutates host, insertion order, float edge cases,
and schema versions and requires identical or explicit rejection.

### S3. Canonically keyed reducer inputs

The golden contract correctly treats siblings as an unordered multiset and
uses stable item keys, but it never says the reducer receives a canonical keyed
collection rather than completion order. A reducer could still produce a
different decision from legal sibling timing.

**Smallest amendment:** S2's dynamic reducer contract receives a key-sorted or
otherwise canonically keyed multiset of `(declared_item_key, typed_result)`;
duplicate/missing keys fail. NP-GT-001/002 permute completion order, not only
input order, and require the same reducer output and decision-input digest.

### S4. Frozen fanout bindings

Fanout child identities are stable, but sibling call policy/context is not
explicitly snapshotted at fanout admission. An in-place config mutation could
make siblings observe different policy while retaining the same declared set.

**Smallest amendment:** S2 records one fanout-admission binding digest covering
declared item set, canonical context, policy, prompt/tool bindings, and relevant
artifact references. Every child envelope consumes that frozen digest. Later
configuration applies only through typed reconfiguration/new generation. Add
NP-GT-002 sibling-context-mutation and mixed-binding negative tests.

### S5. Declared error outcomes only

The amended plan forbids exception-driven product routing and requires closed
outcomes, but does not explicitly distinguish a declared typed business/error
outcome from an open set of implementation exception classes.

**Smallest amendment:** S2 permits topology to catch/match only declared typed
outcomes in the phase port contract. Undeclared exceptions become a fixed
runtime/infrastructure-failure channel handled by declared retry/recovery policy,
never dynamically matched product branches. S7 rejects `except Exception` or
exception-class product routing and tests declared error exhaustiveness.

### S6. Typed reconfiguration primitive

S6 already requires config effect plus exact reentry and the golden contract
changes the policy digest. What remains implicit is the atomic primitive and
the ban on ambient context mutation.

**Smallest amendment:** S2 defines a product-neutral
`reconfigure(delta, target_cursor)` transition: accept a schema-versioned typed
delta through RA, durably checkpoint, derive new policy/executable binding,
increment reentry generation/new attempt as required, and resume the same named
semantic cursor under current Custody/WBC. S6 uses it for model/vendor/profile/
robustness changes and rejects in-place context/global/live-flag mutation.

### S7. Declared durable agentic phase protocol

The deterministic boundary allows opaque typed phase/effect boundaries and the
LLM/tool envelope is strong, but a model-determined number of inner tool calls
is not explicitly representable. Requiring topology to enumerate them will
push real agent phases back into unobserved handlers.

**Smallest amendment:** S2 permits a declared `agentic_phase` boundary with
typed input, closed outer outcomes, named policy/budgets, one explicit WBC
attempt/protocol, and a durable ordered inner model/tool-call ledger. Every
effectful tool call uses admitted intent/outcome, authority/custody as required,
and replay/result rules. The boundary cannot choose the next outer product
route. S3 or S5 proves one real Megaplan agent phase, including crash after an
inner tool outcome and cap exhaustion; S7 rejects unjournaled inner tools and
outer route hints.

This is not a general Stage 2 component ABI; it is the faithful Stage 1
boundary needed by the product already being migrated.

### S8. Plan Contract content digest pinning

The amendments correctly say Plan Contract metadata is non-authority, but the
checkpoint/action bindings still do not include its applicable content digest.
Because `pre_existing` can change which evidence is required, a mid-run edit
could otherwise weaken admission without adding a route.

**Smallest amendment:** S1 defines canonical Plan Contract content/fingerprint
and maps the applicable contract version to semantic occurrences. S2 includes
that digest in compile, checkpoint, reentry and action envelopes wherever it
affects required evidence. Drift uses pinned original or accepted typed
migration/new attempt/quarantine. S7 mutates only `pre_existing`/`assumes` and
proves it cannot waive evidence mid-run.

### S9. Quarantined shadow namespace

The migration graph allows inert dual-read/shadow comparison but does not say
where its checkpoints, WBC attempts, or effect-shaped evidence are written.
Canonical queries could accidentally observe comparison records or a repair
path could resume them.

**Smallest amendment:** S1 defines a distinct digest-bound shadow namespace
with `non_authoritative`, `non_resumable`, and `non_effect_capable` invariants.
S3/GO-1 and S5/GO-2 require canonical WBC/checkpoint/effect queries to exclude
it by construction. Shadow records cannot satisfy row evidence, RA decisions,
action admission, recovery, reconciliation, or projections except an explicit
comparison view. S7 mutates namespace labels/queries and attempts resume/effect.

### S10. Explicit all-plane validator and `workflow_data.py` proof

M11 is expected to own the shared action validator and controlled-writer
inventory. Native Parity already requires all Native positive actions to use it
and broadly deletes `_core` routes. Two delta details remain:

- S1 should consume M11 proof that `arnold.execution`, the native runtime, and
  legacy runtime-envelope effect-capable paths are all registered controlled
  writers using the same validator. Native owns the convergence-era proof that
  no newly introduced or retained Native/legacy path bypasses it.
- S3/S6/S7 should name `_core/workflow_data.py:WORKFLOW` and
  `_ROBUSTNESS_OVERRIDES` explicitly. Mutating them must be inert after their
  slice cutover; no auto/runtime/CLI entry point may read them as route or live
  policy authority; they are then hard-fenced/deleted.

This is a bounded specificity amendment, not a new control plane.

### S11. Three measurable ergonomics gates

The amendments contain the right mechanisms, but the oracle is correct that
the current gates remain weaker than the proposed measurable claims.

1. **No payload route smuggling.** Add a mutation family showing undeclared or
   non-vocabulary payload fields cannot change a route. For every golden run,
   every route divergence must map to a declared typed outcome/decision value.
2. **No undispositioned rejection.** The diagnostic contract already requires a
   supported rewrite. Make the registry measurable: every diagnostic code maps
   to a supported primitive/example or an explicit deliberate-non-support
   boundary recipe; zero codes lack disposition. Run a timed ten-task author
   simulation and record completion/errors as a blocking readability receipt.
3. **Faithful fast local loop.** S7 currently compares only “selected” local
   traces. Require every NP-GT family, including A/B/C, to produce the same
   normalized lifecycle/admission trace locally and installed when supplied the
   same recorded boundaries, within a declared virtual-time/wall-latency budget.
   Local success still cannot replace installed/cross-host/cloud release proof.

These belong in S1's evidence/diagnostic schema, S2's harness contract, and
S7's final conformance gate. No new sprint is needed.

## Custody/M11 prerequisite ownership

The following should be required from and verified against the accepted M11
manifest/proof map, not reimplemented in Native Parity:

- **Disaster-recovery monotonicity:** restore generation plus monotonic RA fence
  and Custody epoch recovery; restoring a database snapshot cannot resurrect an
  old owner as current.
- **Shared action validator and controlled-writer registry:** generic enforcement
  across execution planes, stale fence/epoch, WBC version/evidence, and effect
  admission. Native adds only topology-specific bindings and no-bypass proof for
  its migration paths.
- **Repair acceptance revalidation:** requests and projection-derived failed
  preconditions are hints; canonical journals and current RA/Custody/WBC are
  re-read at action acceptance.
- **Generic effect identity, ambiguity, reconciliation, and cancellation lease
  lifecycle.** Native supplies exact semantic target and scenarios; it does not
  invent another protocol.

If any of these are absent from the final M11 completion manifest, the Native
chain launch precondition must fail rather than silently absorb the work.

## Stage 2 Platformization ownership

Q4 is chiefly a reusable component-model audit. Preserve it for the dependent
Platformization ticket/epic:

- root hosting adapters mapping component returns to root product terminals;
- normative business-outcome versus lifecycle/control-terminal layers;
- outcome-condition/temporal behavior contracts;
- cross-implementation behavioral substitutability and normalized trace
  compatibility;
- generic parent loop-state durability as a composition obligation;
- new-instance substitution versus suspended-instance migration policy;
- generic non-idempotent child-effect identity under parent retry;
- generic parent-cancels-suspended-child Custody release/transfer semantics,
  building on M11's lease lifecycle;
- race/quorum composition if a second real consumer establishes the need.

Native Parity should implement only the concrete Megaplan semantics and emit
evidence that later extraction can inspect. It should not define a public ABI,
registry governance, or universal composition algebra.

## Deliberate non-support

The deterministic authoring contract should explicitly reject these with a
diagnostic and supported architectural recipe:

- **Open-ended item streams/polling inside topology.** Stage 1 and initial Stage
  2 support finite admitted collections only. Future streaming requires a
  separately designed event-queue/stream port with cursor, backpressure,
  cancellation, and replay semantics.
- **Undeclared open exception vocabularies as product routes.** Convert expected
  domain failures to declared typed outcomes; unexpected exceptions use the
  fixed infrastructure-failure/retry boundary.
- **Arbitrary ambient/live configuration mutation.** Use typed reconfiguration.
- **Race/quorum in Stage 1 absent a current Megaplan parity case.** Do not add a
  primitive from metrics/alerts examples alone. Reject it clearly for Native
  authoring; reconsider during Stage 2 with a real second consumer. If a current
  Megaplan route truly is first-wins/k-of-n, reclassify it immediately as a
  Stage 1 gap and specify loser cancellation/terminal evidence through M11.

## Q2 limitation

The available Q2 summary confirms that the conjunctive action envelope,
version pins, and effect protocol address duplicate external effects, repeated
model calls, stale worker epochs, and silent v2 resume. But the oracle's
specific claims about numbered items 2, 3, 5, and 7 are not reproducible because
the numbered transition list was omitted from the pasted answer.

Do not infer those transitions. Obtain the missing list and run a focused delta
against NP-GT-003/004/006 before changing the plan. Until then, Q2 is
**indeterminate only for those four referenced transitions**, not a general
failure of the amended suspension/effect design.

## Recommended next amendment pass

One concise pass can close the Stage 1 delta without changing the chain:

- **S1:** freeze addressed exits, canonical decision values, Plan Contract
  digest, shadow namespace, diagnostic dispositions, and M11 all-plane
  admission requirements.
- **S2:** implement addressed exits, keyed reducers, frozen fanout bindings,
  typed errors, typed reconfigure, and declared agentic phase protocol; extend
  the production-lowerer harness.
- **S3/S5:** prove one real agentic phase, outer-loop replan, shadow quarantine,
  and frozen/collision-safe fanout behavior.
- **S6:** explicitly inert/delete `workflow_data.py` route/policy tables and use
  typed reconfigure; retain auto-drive as scheduling only.
- **S7:** make payload-route attribution, diagnostic disposition/author trial,
  and every-family local/installed equivalence blocking; run the new negative
  mutations.

No eighth sprint is warranted. Do not reopen M11 or fold Stage 2 component
standardization into Native Parity.
