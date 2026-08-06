# Megaplan Native Parity Corrective North Star

Canonical Megaplan must have one source-authoritative native workflow and one
composed, fenced runtime history.

The final semantic authority is:

- `arnold_pipelines/megaplan/workflows/workflow.pypeline`;
- named native subworkflows imported by that source;
- declared policies attached to named source constructs;
- retained pure phase bodies behind typed interfaces.

“Python-native” means this source is the sole product control-flow authority,
not merely that orchestration is implemented in Python. Topology/control code
uses a versioned deterministic subset. Ambient time, randomness, environment
or process state, unordered traversal, mutable globals, unmanaged concurrency,
and direct filesystem/network/subprocess I/O are rejected or must cross a
declared typed durable boundary. An opaque phase/effect boundary may compute or
interact externally; it may not choose a product route.

The normative composition oracle is
`GOLDEN_TRACE_CONTRACT.md`. It is the human-reviewed scenario/invariant
contract. An independent static source oracle derives source occurrences
without calling the production lowerer, and a separately implemented verifier
checks raw primary-store event multiplicity before contract-approved
normalization. It proves one same-run ordered/partial-order history and is
neither a second topology nor route, dispatch, repair, or resume authority.

The final composed runtime contract is:

> One authored semantic topology; one exact authority-decision history; one
> current exclusive custody owner; one durable boundary/effect history; any
> number of disposable projections.

## Ownership boundaries

- Native topology owns what happens next: branches, loops, fanout/fanin,
  reentry, retry/cap semantics, model/call-site policy, and terminal outcomes.
- Run Authority owns permission: capability grants, subject attempts, accepted
  decisions, coordinator fences, CAS/idempotency, and quarantine.
- Custody owns current exclusive responsibility for an exact action target:
  renewable leases, process-birth identity, transfer/reclaim, and monotonic
  custody epochs.
- WBC owns exact-version durable evidence of what crossed a boundary and what
  was attempted or effected.
- The Megaplan Plan Contract declares product/milestone `provides`, `assumes`,
  and `pre_existing` interfaces. It neither routes nor authorizes execution.
- The generated manifest and executable/component lock are immutable
  lowering/install/replay coordinates derived from source. They participate in
  executable admission but are not independent route, grant, or lease owners.
- Projections own no decisions. They are disposable views rebuilt at declared
  source cursors.

WBC evidence is **not authority**. Lease ownership is also **not permission**.
Every authoritative dispatch, retry, resume, effect, completion, cancellation,
publication, or delivery must satisfy:

```text
current Run Authority grant + current coordinator fence
AND current Custody lease + current custody epoch
AND required exact-version WBC evidence at declared boundaries
```

The first two terms authorize and fence the action. WBC establishes durable
history and may make a boundary incomplete or indeterminate; it cannot grant a
route or action.

## Identity contract

Every executable semantic node and dynamic child preserves four related but
non-interchangeable identities:

1. authored semantic node/invocation and deterministic child path;
2. Run Authority subject attempt plus coordinator fence;
3. WBC execution attempt and exact boundary-contract version;
4. Custody action target plus lease owner and custody epoch.

No generic `attempt_id` may collapse these identities. Mappings and causal
joins must be explicit, generated, and checked for set equality.

Every authored typed decision occurrence and terminal acceptance emits or links
exactly one accepted Run Authority Decision under the current subject attempt
and fence. Its decision ID, outcome, and CAS sequence are consumed by exactly
one matching runtime transition/action. Orphan, duplicate, unaccepted,
stale-fence, inferred, and outcome-mismatched decisions are forbidden.
That CAS is a linearizable conditional operation enforced by the canonical
production store/service. Application read/check/write, process-local locks,
serialized fixtures and in-memory test-store atomicity do not prove exclusive
acceptance. Every owning cutover joins the lowered site to the certified
operation and records production adapter/store/schema provenance.

Every checkpoint/reentry envelope additionally binds the authored
program/topology digest, call-site-policy digest, and exact WBC contract
version, installed artifact, dependency lock, and applicable prompt/tool
identities, plus the normalized product/Plan Contract digest wherever its
`provides`, `assumes`, or `pre_existing` fields affect evidence obligations.
Resume after any drift uses the pinned original or an explicit
typed migration/new-attempt/quarantine decision; silently recompiling the same
path under changed program, policy, contract, or behavior-relevant asset is
forbidden.

Every nonterminal run keeps its exact executable, dependency lock, prompt/tool
assets, and required schemas resolvable. A pinned version cannot be collected
until all referencing runs are terminal or have an accepted migration or
quarantine disposition.

Checkpoint state is bounded and typed. Small control values may be inline;
large or unbounded plans, prompts, transcripts, model/tool results, task
outputs, reviews, and binaries use immutable content-addressed artifact
references with schema, provenance, digest, and retention metadata.

## Semantic compression without erasure

The goal is the smallest readable workflow that completely determines actual
behavior, not the largest possible number of visible steps. Pure computation
may remain inside phase bodies: parsing, normalization, signal construction,
validation, lens selection, result merging, ready-batch calculation, prompt
formatting, and serialization. A phase body may not choose product routes,
own suspension/retry/cap/model policy, mutate workflow state, or define resume
and checkpoint identity.

Repeated control structure should be generalized into typed, product-neutral
constructs—bounded loops, dynamic map/reducer, human suspension/reentry,
checkpointing, call-site policy, and reusable delivery cycles—provided lowering
preserves every semantic distinction and runtime behavior.

Typed loop exits may address a named enclosing loop; sentinels and exceptions
cannot smuggle multi-level routes. Acceptance closes the target loop ledger,
terminalizes every intervening durable scope exactly once, and reenters only as
an explicit new loop instance with declared carry state. Execution-attempt
terminals, retry generations and the one parent-consumed aggregate child
terminal are distinct. Decisions consume canonical schema-qualified
values. Fanout freezes its digest-bound item set, context, policies, and call
bindings at admission; reducers consume a canonically keyed multiset rather than
completion order. Topology handles only declared typed phase outcomes/errors;
unexpected exceptions use the fixed infrastructure-failure policy channel.

Configuration changes use a checkpointed typed reconfigure transition and
explicit reentry, never ambient mutable flags. A declared durable agentic phase
may perform a model-determined number of inner tool calls under one named WBC
protocol, durable budgets, and ordered effect history, but it has closed outer
outcomes and cannot own the next product route. No inner call starts after
budget exhaustion; a finalization call consumes a named admitted reserve.
Open-ended streams/polling are
deliberately unsupported; authors must use a future event-queue port.
Generic first-wins/k-of-n race/quorum is also not a Stage 1 primitive absent a
demonstrated current Megaplan parity route; it is handed to Platformization for
a real-consumer design with loser-cancellation semantics.

The present critique evaluator is a bounded selector/model call, not a durable
agentic inner loop. Native Parity freezes the generic safety contract and
rejects opaque inner loops at GO-0, but implements that runtime only if the
inventory proves a concrete current consumer. Otherwise implementation remains
experimental Platformization scope. When used, every effectful inner call has
an exact Custody target and its own WBC effect intent/outcome.

## Execution modes and developer freedom

Safety attaches to claims, not to the act of experimentation. The supported
surface has five explicit, non-interchangeable modes:

- `authoring_preview`: working-tree code and even unsupported durable Python may
  run with fresh ephemeral identity and fake effects, but produces no durable
  checkpoint, replay, resume, comparison, admission or certification claim;
- `durable_sandbox`: an edited step/subworkflow may repeat or fork from typed
  fixtures or immutable recorded boundaries with a working-tree content digest,
  fresh experiment/run/attempt lineage, isolated namespaces, recorded inputs
  and fake or sandbox-only effects;
- `comparison`: candidate execution stays in quarantined, non-authoritative,
  non-resumable, non-effect-capable and non-promotable history;
- `admitted_production`: only the exactly admitted executable/policy/schema may
  continue canonical history under production RA, Custody, WBC and effects; and
- `certification`: packaged candidates earn compatibility/stability claims
  through blocking proof without mutating a product run.

Editing a step and rerunning it is automatically a fresh experiment or explicit
fork, never a silent production resume. The platform generates content digests,
fresh identities, isolated effect/idempotency keys and provenance to the source
boundary without asking the author. The hard wall is truthful lineage: no mode
may overwrite admitted history, reuse production effect identity, or be
promoted/relabelled as another mode.

Every restriction is classified as `always_hard`, automatically satisfied, a
`production_admission_gate`, a separate `stable_publication_gate`, an authoring
advisory, or `non_durable_only`.
Complexity, provisional reuse and documentation guidance should not prevent a
local iteration. Changed executable identity, namespace separation, effect
safety, authority/evidence separation and truthful mode/provenance remain hard.
Diagnostics name both the violated claim and the supported next path; they may
offer preview or a typed rewrite but never silently downgrade execution.

## Pinned prerequisite and non-duplication

This epic starts only after `custody-control-plane` M11 has landed as one clean,
accepted revision with a valid completion manifest/proof map and enforced
installed-runtime conformance. Native Parity consumes its settled contracts,
stores, exact-version queries, action validator, lease/recovery services,
outbox/reconciliation, projections, controlled-writer inventory, and generic
conformance fixtures.

The accepted M11 proof must include restore-resistant Run Authority fence and
Custody epoch monotonicity and canonical acceptance-time revalidation of repair
requests. A restored store cannot resurrect pre-restore authority. Native
Parity consumes these proofs and creates no local restore marker or repair
trust mechanism.

Native Parity must not create parallel Run Authority, Custody, or WBC stores,
queries, recovery loops, projections, promotion logic, or generic cross-contract
conformance. It owns topology-specific binding, identity, producer relocation,
legacy-carrier deletion, and native semantic proof.

S1 executes capability probes against the admitted M11 revision. Missing
three-plane writer registration, opaque digest binding, restore-durable decision
consumption, exact-target scale, WBC reconciliation, repair classification or
pin resolution stops for a new M11 point release; it never licenses a Native
side authority store. Every migration application consumes its own accepted RA
decision. Repair validation distinguishes actor-local redispatch of a still-
valid unconsumed decision from semantic invalidation requiring a new decision.
The same probes cover governed versioned producer/query registry evolution and
generated-manifest schema/hash mixed-worker compatibility. Registry changes are
admitted data, not a way to silently change the pinned platform contract or
promote comparison history.

## Done means

- Source lowering is load-bearing and preserves every semantic node, decision,
  loop, dynamic fanout policy, reducer, call-site policy, and child path.
- Components, handlers, runtime maps, `_core` tables, compatibility native
  programs, CLI dispatch, and auto-drive cannot independently choose product
  behavior.
- WBC producers are attached to canonical lowered nodes/children, not merely
  to handlers that the migration is deleting.
- Human suspension resumes at the exact semantic point only after current
  authority and custody validation; marker-only resume is impossible.
- Installed checkout, wheel/sdist, and pinned cloud runtime yield the same
  topology, decisions, WBC history, and identity joins.
- A generated, fail-closed conformance model proves source/lowering/runtime set
  equality, decision-occurrence/accepted-decision/consumed-transition equality,
  and zero hidden route authority. Its validator consumes the complete proof
  map, not merely its path. Hashes, receipts, status labels, shadow enforcement,
  and projections cannot produce an `implemented` claim by themselves.
- All six `NP-GT-001` through `NP-GT-006` scenario families and their mutations
  pass as same-run composed traces in checkout, wheel/sdist, and cloud. The
  `NP-GT-006A/B/C` race variants prove closed terminal arbitration.
- Native authority-increasing dispatch, decision, and effect envelopes validate
  program/topology, call-site-policy, exact WBC contract, and installed-artifact
  digests plus dependency lock, applicable prompt/tool identities, and the
  normalized product/Plan Contract digest before product code/effect intent; a
  heterogeneous stale worker is rejected or explicitly migrated before action.
- The Python authoring surface retains one topology representation, one reusable
  delivery-cycle call, a small primitive set, generated mechanical identity and
  control-plane bindings, local policy, closed exhaustive vocabularies, and
  bounded edit locality. Handler/auto/metadata-only extensions fail closed.
- Compiler and runtime diagnostics resolve generated nodes back to precise
  authored file/span and semantic path, with stable error codes and supported
  rewrites for rejected Python constructs.
- A lightweight in-process authoring harness uses the production lowerer and
  transition semantics with typed fakes/recorded boundaries; it cannot become a
  second route engine or substitute for installed/cross-host custody proof.
- Working-tree edit/repeat and durable fork are first-class, low-friction
  developer paths with fresh isolated identities and source-boundary
  provenance. Changed-code resume, preview/comparison promotion and production
  effect/idempotency reuse fail before action; enforcement severity follows the
  frozen execution-mode/disposition matrix. `NP-DX-001` through `NP-DX-004`
  make these developer-mode claims executable.
- LLM/tool calls bind prompt content, model/provider parameters, tool schemas,
  budgets, cache policy, and durable result identity. Replay consumes recorded
  results rather than silently calling again; retry budget cannot reset.
- Durable state, checkpoint, artifact, effect-idempotency, and cache namespaces
  derive from run plus semantic occurrence/instance coordinates and remain
  isolated across repeated subworkflow invocations, fanout siblings, and runs.
- A rebuildable Native composed-history explanation and repair preflight joins
  admitted M11 facts for operators but remains observational/request-only and
  behaviorally inert.
- Comparison/shadow execution is non-authoritative, non-resumable, and
  non-effect-capable in a quarantined namespace excluded from admitted queries;
  its history can never be promoted or relabeled as canonical.
- At every cutover the union of old and candidate action-capable paths is in the
  admitted controlled-writer registry, every live path crosses the same shared
  validator, and exactly one producer can consume a decision or write admitted
  history.
- GO-1 is two explicit cuts: GO-1A for prep/plan/critique and GO-1B for
  gate/revise. Each partial cut owns a closed serialize-only outgoing seam that
  the next milestone removes; S7 proves no route-capable seam remains.
- Raw event identity/multiplicity survives an independent audit verifier;
  lowered-IR arbitration sites equal indexed policies/forced races; every
  Native durable record has restore ownership; and S7 emits the
  content-addressed Native-to-Platformization handoff manifest.
- Every durable record passes rollback/restore proof when introduced or first
  made authoritative, and each proof-registry receipt binds canonical store
  incarnation/restore generation and raw-history high-water cursor.
- Gate's eight-value vocabulary, precedence and canonical no-progress predicate
  are one exhaustive source/lowering/runtime contract; human answer/cancel races
  admit exactly one compatible transition through production-store CAS.
- Terminal arbitration preserves one explicit role, semantic key and accepting
  Run Authority identity so later root-host extraction cannot create a second
  acceptance domain.
- Every route divergence is attributable to a declared outcome/decision rather
  than payload fields; every diagnostic code has a supported example or
  deliberate-non-support recipe; the timed author tasks pass; and every golden
  family has local/installed normalized-trace equivalence within its declared
  latency budget.
