# Megaplan Native Parity Corrective North Star

The byte-preserved completion proposal and its supersession crosswalk are
normative inputs for every milestone assigned completion work. The bootstrap's
accepted `completion-crosswalk-readiness.json` resolves every requirement and
changed historical constraint to canonical milestone and proof-rule IDs. No
Native milestone may close with an assigned row missing, stale, unconsumed, or
mapped only by prose.

Canonical Megaplan must have one source-authoritative native workflow and one
composed, fenced runtime history.

Launch additionally requires the completed
`megaplan-chain-milestone-gates` bootstrap. Every milestone is checked before
merge eligibility and rebound to merge HEAD. Every authority/effect cutover is
a declared chain transition that consumes the exact accepted readiness receipt,
emits an immutable transition receipt, and is followed by a separate
post-transition verifier before milestone completion. S5A proves the complete
future-live delivery behavior matrix and all external-effect protocol classes
in shadow; S5B alone performs the live switch.
The bootstrap's own single PR is deliberately non-self-hosted: external CI
and a mechanically independent content-addressed attestation must precede
automatic merge readiness and its post-merge backstop.

The final semantic authority is:

- `arnold_pipelines/megaplan/workflows/workflow.pype`;
- named native subworkflows imported by that source;
- declared policies attached to named source constructs;
- retained pure phase bodies behind typed interfaces.

## Canonical source suffix

`.pype` is the only target suffix for newly authored or admitted Arnold
workflow source. S1 inventories and stages the complete rename while keeping
the old path usable. S2F implements and proves the exact-one compiler/linker,
then its typed post-validation transition renames `workflow.pypeline` and every
live named subworkflow to `.pype`, updates compiler/loader, package data, source
maps, manifests and locks, CLI/help, validators, generators, tests, examples,
editor/Linguist configuration, and selects the new suffix as one fail-closed
migration.

The old `.pypeline` suffix may survive only in immutable historical evidence or
an explicit expiry-bound reader for a pre-cutover pinned executable. It cannot
author or admit a new workflow, select a runtime route, satisfy final
conformance, or silently resume an existing occurrence as `.pype`. Existing
nonterminal work must resolve its exact pinned artifact or consume an accepted
typed migration/new-attempt/quarantine decision.

## One `.pype`, one workflow

`docs/arnold/pype-authoring-contract.md` is the normative format authority.
Every admitted root or child workflow lives in its own `.pype`, and every
`.pype` contains exactly one top-level `@workflow`. The exactly-one rule makes
that workflow canonical; there is no `main`, `__all__`, multi-export module,
library-only `.pype`, declaration-order selection, or file-local root selector.

A `.pype` may also contain private file-local steps and deterministic helpers.
They cannot be imported or independently addressed, and their transitive
behavior digest folds into the containing workflow. Reusable or independently
durable steps, effects, schemas, policies, prompts, types, and helpers live in
`.py`. An admitted `.py` workflow is forbidden; ordinary-Python workflows are
available only in explicit non-durable preview with fresh ephemeral identity
and fake/ephemeral-only effects with no durable effect history.

“Subworkflow” is a hosting role of `workflow`, not a separate authored kind.
Only the one canonical workflow crosses a `.pype` boundary. A step is a leaf:
it may call pure helpers and declared effect adapters but cannot invoke a
workflow or another decorated step. Workflows and helpers cannot call effect
adapters directly. Helper data may feed a visible authored branch; a helper
cannot return an invocation target, route table, or hidden policy owner.

Shared `.py` steps may use ordinary Python and third-party imports. The resolved
graph lock or explicit bindings pin selected implementations, optional features,
Python/runtime environment and plugins; import-time effects or mutable Arnold
registration, ambient dependency selection, imported topology and undeclared
effect bypass reject. Policies are immutable typed canonical values in
ordinary `.py`, conventionally `policies.py`, with stable kind/schema, explicit
attachment, provenance, precedence and digest; they cannot contain callables,
open route tables, mutable/ambient defaults or hidden product branches.

Static imports link canonical `.pype` workflows and typed `.py` components
without executing author source. Dynamic/conditional/star imports, import
registration, re-export laundering, import cycles, and recursive workflow
calls fail before durable lowering or authority. Explicit bounded workflow
loops are finite IR rather than recursion.

Logical workflow identity is `(distribution_name, logical_workflow_name)`;
the logical name is the explicit workflow ID when present and otherwise the
decorated function name, and is unique within the distribution. Physical and
wheel paths are provenance. Executable identity adds the complete behavior
digest. Moves with unchanged logical/digest identity are provenance changes;
rename, signature/outcome/hostability change, extraction, inline, private-step
promotion, or behavior drift requires an explicit accepted migration or a new
attempt/quarantine.

The canonical Arnold package descriptor owns the optional default pipeline,
the cross-package allowlist of canonical workflows (package visibility, not
file exports), source/descriptor correspondence, locks, and
append-only identity migration log. S1 must extend the existing canonical pack
metadata rather than create a parallel descriptor unless the inventory proves
none exists. Once a run resolves a pipeline, its logical and executable
identities are frozen across manifest, lock, admission, checkpoint, replay,
source map, and proof.

Unsupported code may run only in explicit `authoring_preview`, with no durable,
resume, comparison, admission, promotion, or certification claim. Durable
modes reject hidden topology/effects before authority or effect intent.
Diagnostics always name the definition and call spans, violated
responsibility, failed claim, and a supported rewrite.

S2F must close a content-addressed `GO-FORMAT` gate for this complete contract
before C1. It covers file shape, import/privacy/leaf laws, identity and
migration, preview/legacy isolation, source/package correspondence, and
checkout/editable/wheel/cloud equivalence. It also freezes the Step-IO-
referencing step-authoring contract: mandatory response directories and nested
child files, the five-class field-ownership algebra including monotone safety-
lattice proposal merges, derivation purity, normalized parse diagnostics, and
schema compatibility. C1 and C2 build the non-authoritative
completion kernel from that exact identity handoff. S2R independently
revalidates GO-FORMAT and both kernel receipts, implements durable runtime
primitives and concrete aggregation instances, and closes GO-0 through the sole
authoritative kernel-enablement transition before S3A.

S3A runs that compiler in a volume-gated shadow over real or content-addressed
replayed prep/plan/critique occurrences, dispositions every divergence, and
requires zero unexplained divergences before GO-1A. If detailed planning exceeds
the milestone budget, it may split only at the shadow/cutover seam. Compilation
admits a candidate; only the existing WBC/Custody transaction publishes it.
Final chat and editable response files never become authority.

## Completion kernel and semantic proof

The completion critical path is:

```text
S2F identity and durable-boundary call-site templates
  -> C1 contract/identity/shadow generation/divergence ledger
  -> C2 immutable binding/evaluation/compatibility/shadow acceptance
  -> S2R concrete primitive instances and sole GO-0 enablement
  -> S3A ... S7 consuming exact receipts and current ledger hash
```

S2F does not pretend that runtime human, dynamic fanout-child, invocation, or
rework occurrences already exist. Admission and S2R instantiate them beneath
source-stable call-site templates; S5 admits product-created reopened and
genuinely new work.

C1 is the inserted execution of Completion M1 and C2 is the inserted execution
of Completion M2. Native hosts them in this frontier; the preserved Completion
proposal, source briefs, and supersession crosswalk remain their normative
semantic source. C1 owns the experimental `arnold/workflow/completion/` boundary, internally
versioned schemas/serialization from introduction, executable obligation
identity `(spec_hash, obligation_id)`, a mechanically decidable durable-subject
predicate and static omission lint, one canonical completion
candidate-outcome registry, `superseded_by_named_exit`, shadow generation, the
false-done/`REVIEW` golden exemplar, and one content-addressed append-only
divergence ledger. Any Megaplan or platform completion registry is a strict
generated and tested projection of that canonical registry. C2 owns immutable
binding/evaluation schemas, the normative evidence-window tuple and proof
modes, candidate-first evaluation with typed blocked/waived proof, aggregation
signatures, verifier independence by producer identity and trust class,
waiver taint, internal persisted-wire compatibility and decoder behavior,
shadow atomic acceptance integration, introduction-time restore including
store-incarnation invalidation, and projection deletion/forgery invariance.
Neither milestone is authoritative.

S2R freezes child sets and supplies one concrete total aggregation instance for
every supported durable primitive. Its accepted GO-0 transition receipt is the
only live kernel enablement. Internal persisted-wire compatibility begins at
that point; stable public authoring/API publication remains Platform S6-only.

Completion authoring must remain elegant: authors declare durable intent and
domain obligations once on the canonical authoring surface; deterministic
tooling derives mechanical obligations, generates and pins bindings, and emits
human-readable worksheets/Markdown as non-authoritative disposable
projections. Static lint and admission reject omissions. Pure helpers require
no completion contract and inherit no independent durable identity.

Platform enforcement dispositions and completion candidate outcomes remain two
different versioned typed registries. Their interaction is one total generated
boundary mapping that rejects unknown pairs; neither vocabulary may be
collapsed into the other or extended through an unversioned local table.

“Python-native” means this source is the sole product control-flow authority,
not merely that orchestration is implemented in Python. Topology/control code
uses a versioned deterministic subset. Ambient time, randomness, environment
or process state, unordered traversal, mutable globals, unmanaged concurrency,
and direct filesystem/network/subprocess I/O are rejected or must cross a
declared typed durable boundary. An opaque phase/effect boundary may compute or
interact externally; it may not choose a product route.

The normative composition oracle is
`validation/GOLDEN_TRACE_CONTRACT.md`. It is the human-reviewed scenario/invariant
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

The accepted/consolidated Custody manifest must also bind the exact
`bounded-incident-projection-handoff.json`, including crash-safe
cursor-incremental or bounded snapshot-plus-tail behavior, invalidation,
full-rebuild parity, and the 57,000-event latency/peak-memory benchmark. Custody
owns the projector and receipt. Native launch and S5B consume that exact
handoff and prove no full-history fallback; Completion and Platformization do
not implement a competing projection.

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
- Exact inventory equality holds across durable subjects, CompletionBindings,
  required evidence, CompletionVerdicts, accepted Run Authority decisions,
  effects, and terminal candidate outcomes; no competing completion writer
  remains.
- Every S3A–S7 gate consumes the exact accepted C1/C2 manifests, S2R
  kernel-enablement receipt, and current divergence-ledger hash with no stale
  unresolved blocking occurrence.
- The complete finalize/admit → execute → landed-write/validation evidence →
  verdict/acceptance → review → reopen or admit new work → execute → aggregate
  slice rejects false `done`, never dispatches `REVIEW`, preserves unrelated
  accepted evidence, and meets the 57k bounded-query gate.
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
  behaviorally inert. It supports bidirectional navigation from every
  workflow/step occurrence and generation/attempt to agent sessions,
  model/tool/effect calls, cost and immutable structured-log/transcript
  artifacts, and from those records back to the owning semantic occurrence and
  source span plus consuming decision/terminal when one exists. Complete
  durable-boundary history is required; arbitrary Python
  instruction/local-variable tracing is not required.
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
