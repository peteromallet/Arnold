# Completion Specifications: Ownership, Sequencing, and Oracle Review Brief

## Current operational strategy

This document now governs three prepared, ordered initiatives:

1. **Milestone-gate bootstrap** —
   `.megaplan/initiatives/megaplan-chain-milestone-gates/chain.yaml`.
   One sprint adds generic per-milestone pre/post-merge conformance gates,
   exact predecessor-proof assertions, and typed receipt-consuming
   transitions. It also migrates and preflights the two downstream chain specs
   under that newly installed schema, then emits a content-addressed
   `downstream-spec-readiness.json`. It does not launch them.
2. **Megaplan Native Parity Corrective** —
   `.megaplan/initiatives/megaplan-native-parity-corrective/chain.yaml`.
   Twelve milestones run in this exact order:
   `S1 -> S2F -> C1 -> C2 -> S2R -> S3A -> S3B -> S4 -> S5A -> S5B -> S6 -> S7`.
   C1/C2 are the completion kernel; the standalone completion initiative is
   normative source and traceability, not a competing launch target.
3. **Native Workflow Platformization** —
   `.megaplan/initiatives/native-workflow-platformization/chain.yaml`.
   Seven milestones run only after Native Parity:
   `S1 -> S2A -> S2B -> S3 -> S4 -> S5 -> S6`.

The production order is therefore:

```text
Custody M11 accepted and manifested
  -> milestone-gate bootstrap accepted and manifested
  -> Native Parity with Completion C1/C2
  -> Native Workflow Platformization
```

The bootstrap comes first for a concrete reason: the current chain driver can
enforce only its final conformance gate. The downstream plans require
intermediate gates and atomic receipt-consuming authority transitions. Writing
those fields into a chain before the parser/driver supports them produces a
design-shaped but invalid artifact; omitting them lets authority-changing
milestones rely on narrative completion. The bootstrap closes that
orchestration gap once, generically, before either downstream program runs.

The bootstrap is deliberately the one human-reviewed exception to unattended
auto-merge. It cannot safely use the new gate to certify the implementation of
that same gate. Its exact proposed tree therefore requires external CI,
independent review, manual merge, and a content-addressed attestation; the
existing final gate then certifies the landed tree. This is a bootstrap trust
boundary, not a general preference for PR ceremony. Native Parity and
Platformization remain unattended/auto-merge once that capability is installed.

All three cloud configurations intentionally target the existing Custody
checkout **sequentially**, after M11. `chain_completed` state and completion
manifests are checkout-local; using unrelated workspaces would make a genuinely
completed predecessor invisible to its successor. Distinct chain sessions
remain named separately, but they must not run concurrently against the shared
checkout.

The durable source is the `editible-install` branch. Before each launch, refresh
from that branch and verify the exact initiative/spec hashes. Never replace
these sources with older same-named files already present on the machine, never
use generated `.megaplan/plans/` state as initiative source, and never reset or
sync-clean the active M11 checkout while M11 is running.

## Decision in one paragraph

Do **not** launch the prepared five-milestone
`standardized-completion-specifications` chain as an independent epic in its
current form. Completion semantics belong between two layers, but they must be
introduced *inside* the Native Parity migration rather than before or after the
whole thing:

1. Custody M11 finishes and publishes its exact completion manifest.
2. The milestone-gate bootstrap installs and certifies the generic chain
   enforcement needed by the downstream authority transitions, migrates both
   downstream specs, and emits their readiness manifest.
3. Native Parity establishes canonical `.pype` source identity, lowering, and
   durable-subject identity through S2F.
4. The completion **kernel**—the current Completion M1 and M2—is inserted after
   S2F and before S2R. S2R then gives every durable control primitive explicit
   composition semantics under that kernel.
5. Native Parity's S2R–S7 migrations consume that kernel. The current
   Completion M3 and the Megaplan-specific parts of M4 are folded into those
   milestones rather than run later as a retrofit.
6. Platformization consumes the completed Megaplan proof. It owns durable
   product-neutral extraction, authoring/tooling, isolated recomposition, and
   the unrelated second-consumer proof. The current Completion M5 is distributed
   across Platformization S1–S6, with certification only in S6.

In shorthand:

```text
Custody M11
  -> milestone-gate bootstrap
  -> Native Parity S1 -> S2F
  -> completion kernel (spec + binding + evaluator)
  -> Native Parity S2R ... S7 using that kernel
  -> Native Workflow Platformization S1 ... S6
  -> stable public completion API only after second-consumer proof
```

The prepared completion initiative remains valuable as a byte-preserved design
and brief source. Its work has been redistributed through an explicit
crosswalk covering 81 requirements plus two intentionally changed historical
constraints; its `chain.yaml` is non-launchable by design.

## Why this is not simply “before” or “after”

The completion model needs two things that are delivered by different stages:

- It needs **stable semantic subjects**—durable workflow, step, task, effect,
  and human-boundary identities—from Native Parity's compiler and durable
  control work.
- Native Parity's live phase migrations need **correct completion semantics**
  before they cut over, or they will migrate legacy `done` projections and
  review pseudo-tasks into the new topology.

Therefore:

- Completion **before all Native Parity** is too early. It would bind contracts
  to `.pypeline`, legacy handler/task identities, and source/runtime shapes that
  S2F and S2R intentionally replace.
- Completion **after all Native Parity** is too late. S3A–S7 would first migrate
  old completion behavior and then be rewritten immediately.
- Completion **after Platformization** is much too late. The platform's durable
  database schema, approval gates, worker supervision, and compatibility
  promises would already have chosen what “finished” means.
- Running all three independently is worst of all: it creates multiple schema
  owners, duplicated migration work, and ambiguous authority at exactly the
  boundary the completion proposal is meant to simplify.

The correct seam is after Native Parity has made subjects stable but before it
makes product paths live.

## The systems involved

### 1. Custody M11: authority and acceptance substrate

Custody M11 owns the lower-level invariants that completion must consume:

- Run Authority grants, attempts, decisions, and fences;
- Custody targets, leases, and epochs;
- exact-version Workflow Boundary Contract evidence and effects;
- transactional admission and acceptance;
- replay, stale-fence, restore, and zero-bypass behavior;
- the operational failure corpus that exposed false completion and unroutable
  review work.

M11 does **not** need to invent the final neutral completion abstraction. Its
job is to leave a trustworthy substrate and proof manifest.

The captured M10/M11 failures are mandatory downstream fixtures:

- legacy tasks can say `done` while no accepted attempt exists;
- review-originated work can become the pseudo-task `REVIEW` without admitted
  executable identity;
- immutable task packets can reject already-landed work because generated
  outputs, directory scopes, and per-command budgets were modeled incorrectly;
- a shadow accepted-attempt projection can accidentally become hard recovery
  authority;
- a blocked plan can be projected as a complete chain, blinding the fixer;
- recomputing authority over a large event history can delay dispatch while a
  runner merely appears alive.

Completion work should prevent the semantic false passes. Platform and
supervision work should prevent the liveness, persistence, and projection
failures. Neither should recreate M11's authority systems.

### 2. Native Parity: canonical subject and product-semantic owner

`megaplan-native-parity-corrective` is the current corrective program. Its
active chain establishes:

- one canonical `.pype` workflow per durable root or child workflow;
- exact semantic identity and source/runtime digests;
- compiler-fenced lowering and typed durable control primitives;
- visible Megaplan product control flow;
- staged cutovers for planning, execution, review/rework, override, recovery,
  and final conformance.

This is where CompletionSpecs become useful. Native source owns *what durable
subjects exist and how they compose*. Completion owns *what each admitted
subject must prove*. Run Authority/Custody/WBC own *whether the evidence and
transition are authorized*.

Those must stay separate:

```text
Native source/compiler
  defines subject identity and topology

CompletionSpec -> CompletionBinding -> CompletionVerdict
  defines and evaluates semantic proof obligations

Run Authority + Custody + WBC + acceptance transaction
  authorize the transition and effects

Status/Markdown/timelines
  explain the result but never authorize it
```

### 3. Platformization: production substrate and public proof

The historical `native-platform-followup` owns already-completed production
substrate around the earlier composition model:

- idempotent side effects and reconcile-on-resume;
- credential brokerage and approval gates;
- shared packs, pins, and compatibility;
- a durable backend for checkpoints, events, waits, and audit references;
- worker leases, cancellation, quarantine, and fleet supervision;
- installed/cloud conformance and public documentation.

The future `native-workflow-platformization` initiative has a narrower current
mission: extract the Native-proven component standard, productize `.pype`
authoring and tooling, prove isolated recomposition, and challenge it with an
unrelated consumer. It must reuse the historical production substrate and the
Native completion handoff rather than recreate either. Completion work must not
build a second database, lease system, effect ledger, worker supervisor,
credential broker, scheduler, or public component standard.

## Which existing initiative is authoritative?

There are three overlapping generations of native work in the repository:

1. `native-python-pipelines-completion`
2. `native-composition-followup`
3. `megaplan-native-parity-corrective`

The first two describe a `.pypeline`-based substrate followed by composition.
The corrective initiative explicitly selects `.pype`, defines the current
compiler/identity contract, binds M11, and includes the staged Megaplan
cutovers. These are not three independent chains that should all run.

The recommended interpretation is:

- the older Native Python, Composition, and Platform Follow-up manifests report
  their milestones complete, so they are historical substrate and evidence—not
  future work to relaunch;
- `megaplan-native-parity-corrective` supersedes their authoring and
  product-semantic assumptions where the new `.pype` contract conflicts;
- unique accepted proof or genuinely completed substrate from the older chains
  must be imported by content address, not reimplemented;
- the older chains should remain immutable historical evidence, with their
  retained responsibilities named explicitly in the new handoff;
- Platformization should depend on the authoritative Native Parity corrective
  completion manifest, as its prepared chain already does.

This conclusion still needs an oracle and repository-state audit before
mutation, because a completed historical milestone may contain proof that the
corrective program expects to consume. “Superseded” must never mean “delete its
evidence.”

That earlier preparation defect is now resolved in source: Native Parity has
explicit C1/C2 milestones for `CompletionSpec`, `CompletionBinding`, and
`CompletionVerdict`; the standalone completion briefs and governing proposal
remain byte-preserved; and
`standardized-completion-specifications/SUPERSESSION_CROSSWALK.yaml` maps all
81 retained requirements plus two changed constraints to active owners and
proof destinations. The
remaining launch dependency is executable rather than architectural: the
bootstrap must first install the chain schema that makes each intermediate
gate and transition enforceable.

## Exact allocation of completion work

### Completion M1 — Contract, identity, and shadow generation

**Put it in:** Native Parity, immediately after S2F and before S2R.

**Why there:** S2F fixes `.pype` authored workflow/component identity,
executable closure, graph lock, source correspondence, and the namespace in
which later occurrences live. It does **not** currently define runtime human,
fanout-child, or review-created rework identities. Amend S2F to emit stable
call-site identity templates for durable boundaries; finalization/admission and
S2R allocate runtime occurrence identities beneath those templates. This is
enough to define a kernel without pinning obsolete handler or path identities,
while avoiding the false claim that every subject occurrence already exists.
S2R then defines how decision, loop, fanout, suspension, checkpoint, retry, and
effect primitives instantiate and compose those contracts. Putting the whole
kernel after S2R would let S2R invent an interim completion algebra that
immediately needs replacement.

**Deliverables:**

- `CompletionSpec`, stable `obligation_id`, canonical `spec_hash`;
- the mechanical durable-subject versus pure-helper predicate;
- source/compiler-derived spec-template factories for subject kinds already
  knowable at S2F, with occurrence bindings deliberately deferred;
- an explicit S2F inventory of human-boundary and rework/reopen declarations;
  S2R instantiates invocation, fanout-child, human-suspension, and rework-
  generation identities, while S5 admits product-created new/reopened work;
- neutral interfaces under experimental `arnold/workflow/completion/`, which
  imports neither Megaplan nor product orchestration, plus deterministic
  adapters under `arnold_pipelines/megaplan/`;
- an import-linter that makes that dependency direction mechanical from the
  first kernel milestone and is rerun at Native S7 and Platform S4/S5;
- shadow evaluation over the M10/M11 negative corpus;
- individually classified parity divergences recorded through the normal
  stable-occurrence mechanism, exposed as a content-addressed append-only
  ledger whose current hash every later authority-changing transition consumes;
- separate versioned wire schemas and canonical serialization/hash versions for
  spec, binding, verdict, and acceptance reference, with an explicit old/new
  reader-writer compatibility matrix;
- `superseded_by_named_exit` as a typed lifecycle/control terminal—not success,
  waiver, cancellation, or arbitrary not-applicable—bound to an accepted named
  exit, target loop, source declaration, and ordered unwind set;
- no authoritative cutover yet.

**Must not own:** acceptance authority, storage backend, product review policy,
or public API stability.

### Completion M2 — Binding, evidence evaluation, and acceptance integration

**Put it in:** Native Parity, directly after the kernel schema and still before
S2R.

**Deliverables:**

- immutable `CompletionBinding` at admission;
- exact evidence scope: subject, attempt, generation, source/runtime digests,
  store incarnation, cursor range, custody epoch, fence, WBC version, and child
  set;
- presence, complete-capture absence, set-equality, and aggregate proof modes;
- generic aggregation **signatures**: total child-disposition mapping shape,
  multiplicity and double-counting constraints, and transitive waiver-taint
  laws; S2R owns the concrete aggregation instance for each durable primitive;
- explicit candidate dispositions and obligations for non-accepted outcomes;
- verifier independence by producer and trust class;
- waiver scope/expiry/taint propagation;
- a versioned internal persisted-wire compatibility contract;
- shadow-capable integration with the existing M11 acceptance transaction,
  including atomic contender tests, but no broad authoritative enablement;
- an introduction-time restore/replay drill for every new durable kernel record;
- authoritative decoders that map legacy ambiguity to `legacy/unknown` and
  reject or quarantine unknown-future versions before body/effect intent;
- a projection-deletion/rebuild fixture: accept canonically, delete all
  completion/status/Markdown projections, restart, rebuild, and prove identical
  accepted decision/verdict/effect identity with no new action; forged or
  corrupt projections must likewise have no authority;
- named-exit mutations covering duplicate, missing, reordered, wrong-target,
  and ambient-exception supersession terminals;
- resume rejection or explicit migration/quarantine when bindings change.

**Why before S2R:** every durable primitive and every subsequent phase cutover
should emit and consume the same binding/verdict model. S2R owns the total
aggregation rules for its primitives, but it consumes the kernel rather than
creating a competing semantic status model. S2R's exit receipt is the first
point at which the kernel may become authoritative: enabling it earlier would
enforce bindings before the supported primitives have total completion
semantics.

### Completion M3 — Megaplan vertical slice and rework

**Put it in:** split across Native Parity S5A/S5B and their entry gates.

The vertical slice is:

```text
finalize/admit
  -> execute
  -> landed-write and validation evidence
  -> verdict/acceptance
  -> review
  -> reopen an existing task or admit new rework
  -> execute
  -> aggregate workflow completion
```

S5A should prove this in shadow for every relevant effect class. S5B should be
the only live cutover. The M10/M11 `done`/`REVIEW` fixture must be an explicit
GO gate, not a later regression test. Reopen is a new admission referencing the
stable prior semantic subject; it never mutates or reuses the prior binding.

S5B must also run the real large-history liveness gate: at least the captured
57,000-event scale, with bounded/cursor-incremental authority projection and a
pinned latency and peak-memory budget. This exposes a known upstream gap:
`arnold_pipelines/megaplan/incident/projection.py` currently rereads and hashes
the complete journal even though `arnold/runtime/event_journal.py` already has
cursor/range/limit reads. Custody owns the incident ledger and must deliver a
crash-safe incremental checkpoint or bounded snapshot-plus-tail projection,
with full-rebuild parity and invalidation on truncation/store-incarnation
change, before Native launch. S5B proves the complete live
execute/review/rework path consumes that bounded API without falling back to
full-history recomputation.

Megaplan-specific finding routing, rework policy, task difficulty, and
non-convergence stay in Megaplan. Stable admission, binding, accepted-attempt
evidence, and execution-frontier mechanics stay product-neutral.

### Completion M4 — Composition, migration, and authoring experience

**Split it:**

- **Native Parity S3A–S7 owns:** adoption by all Megaplan phases, workflow
  aggregation over the topology it supports, removal of competing Megaplan
  completion writers, causal operator projections, and installed-runtime
  conformance.
- **Completion kernel owns:** neutral composition rules and generated
  authoring/lint support.
- **Custody owns:** scalable canonical incident/status projection and the
  bounded query/cursor substrate.
- **Platformization owns:** completion-specific inspection/query DX over that
  substrate, human/effect operating surfaces, and reusable component tooling.

Authoring should remain small:

- pure helpers declare nothing;
- standard durable subjects get generated mechanical obligations;
- authors add only domain obligations;
- `accepted(...)` proposes a disposition but cannot mark work complete;
- canonical machine records are generated;
- Markdown completion reports are disposable projections.

### Completion M5 — Public extraction and second consumer

**Put it in:** distribute it across Native Workflow Platformization S1–S6.

Do not freeze a public completion API immediately after Megaplan migration.
Megaplan is the first and hardest consumer, but still only one product.
Platformization should inventory the candidate in S1; extract enforcement and
authoring hooks in S2A/S2B; provide lint, inspection, generated views, and docs
in S3; prove isolated extraction in S4; provide the unrelated consumer in S5;
and certify only the surviving surface in S6.

The second consumer must:

- use the neutral implementation without importing or copying Megaplan policy;
- have different domain obligations and nontrivial composition;
- exercise a human or effect boundary and review/rework or analogous new work;
- prove changed-runtime rejection, old-run resume, migration/quarantine,
  absence evidence, and waiver taint;
- run from a clean installed distribution, not just an editable checkout.

Only behavior proven by both consumers becomes stable. The rest remains
experimental. This does not postpone durable compatibility: once S2R enables
authoritative persisted bindings, their internal wire schemas and decoder
behavior are versioned promises. Platform S6 decides what becomes a supported
public authoring/API promise; it does not retroactively create storage
compatibility.

## How Native Workflow Platformization should consume completion

### Platform S1 — Candidate inventory

Consume the exact Native handoff and inventory the completion schemas,
registries, adapters, proof corpus, legacy bridges, and product coupling.
Keep two concepts explicitly separate:

- completion candidate outcomes such as `accepted`, `blocked`, or `waived`; and
- platform enforcement dispositions such as `always_hard`,
  `production_admission_gate`, or `non_durable_only`.

The latter already live in
`docs/arnold/workflow-execution-mode-dispositions.yaml`; they are not competing
terminal statuses. Define a total, generated boundary mapping wherever an
enforcement result affects whether a completion candidate may be admitted, and
reject unknown pairs. Do not collapse the two vocabularies or allow either to
grow through an unversioned local table. This stage may challenge the candidate
but must not silently redesign it or stabilize a public API.

### Platform S2A — Neutral enforcement surface

Extract shared admission, binding, evaluation, evidence scoping, lifecycle
composition, and runtime inspection without forking the Native implementation.
There must remain one acceptance transaction and one canonical mapping between
the two intentionally distinct disposition domains.

### Platform S2B — `.pype` authoring core

Productize compiler hooks that derive completion templates from canonical
`.pype` identity and package locks. Generated obligations remain mechanical;
authors declare only domain obligations.

### Platform S3 — Developer experience

Own generic format/lint diagnostics, inspection, generated machine and Markdown
views, editor integration, test-kit ergonomics, and documentation. These are
projections and authoring aids, never authority.

### Platform S4 — Isolated extraction and recomposition

Extract the first reusable patterns and prove that Megaplan consumes the shared
candidate through receipt-bound migration, with no Arnold-to-Megaplan reverse
dependency and no duplicate completion writer.

### Platform S5 — Adversarial second consumer

Use a genuinely unrelated consumer with different obligations, topology,
effects or human boundaries, and rework semantics. It must run with Megaplan
absent and force revision or deletion of any falsely generic surface.

### Platform S6 — Certification and public API

Run both consumer suites, clean-install/package/cloud tests, schema and resume
compatibility, and independent post-publication verification. Freeze only the
neutral surface proven by S5; leave unsupported capabilities experimental.

## Required dependency and manifest changes

### Milestone-gate bootstrap

Run this after M11 acceptance and before Native Parity. Its completion manifest
must bind:

- the parser/driver implementation supporting intermediate
  `conformance_gate` and `receipt_consuming_transition`;
- exact-tree negative and compatibility tests;
- external CI, independent review, manual merge attestation, and the existing
  final conformance receipt;
- the migrated Native Parity and Platformization chain specs;
- every referenced downstream brief and North Star; and
- `downstream-spec-readiness.json`, containing those hashes and the installed
  implementation commit.
- `editable-runtime-readiness.json`, binding the exact approved
  `editible-install` commit, import root, installed distribution/module hashes,
  and cloud worker runtime provenance consumed by downstream preflight.

The bootstrap is not a fourth product architecture or a completion bridge. It
adds missing orchestration enforcement, then hands control to Native Parity.
It must not define completion semantics, product dispositions, or Megaplan
cutover policy.

### Native Parity

The Native Parity chain now places the completion kernel after S2F and before
S2R as inserted C1/C2 milestones. The bootstrap must encode the prepared
per-milestone gates and transitions into the newly supported chain schema and
prove the resulting spec preflights. Do not use a separately completed
completion bridge chain: it would add a manifest authority and pause/resume
seam across two parts that need one semantic owner.

S2R and every S3A–S7 gate should bind:

- the exact completion-kernel manifest;
- the exact current completion-divergence ledger hash, with no unresolved or
  stale blocking entry;
- the exact `.pype` compiler/identity receipt;
- M11's accepted authority/custody/WBC versions;
- the relevant product topology and obligation hashes.

### Prepared completion initiative

It has been converted from an independently executable five-sprint chain into
normative source briefs and traceability assets imported into Native Parity and
Platformization. C1/C2 are in the Native chain, and the source initiative is
explicitly non-launchable. A bridge chain would add a manifest authority and
crash/resume seam between two parts that must share one semantic owner.

Its current local M11 precondition must not be trusted until the authoritative
cloud M11 initiative revision is merged and the manifest matches that exact
chain. The active M11 run lives in the cloud custody checkout; a same-named
local chain is not proof of identity.

### Platformization

Its predecessor checks now name the final authoritative Native Parity
corrective manifest and hashed handoff. The bootstrap must migrate its
intermediate gates/transitions to the supported schema and bind the result in
the downstream readiness manifest. If the older Native Python and Composition
chains retain unique responsibilities, enumerate their exact proof artifacts
rather than requiring vague nominal completion.

The current `native-workflow-platformization` chain already depends on the
Native Parity manifest and hashed handoff. Extend that handoff and its S1 gate
to require the completion schemas, registries, negative traces, exact inventory,
and legacy-writer retirement proof. Require the Megaplan completion-conformance
proof before S4 extraction and S6 public freeze.

### Old Native Python and Composition initiatives

Perform a disposition audit:

- completed and uniquely useful proof -> import and preserve;
- any artifact consumed by an M11 manifest or Native S1 gate -> retain
  regardless of semantic supersession;
- scope fully superseded by corrective -> mark superseded and non-launchable;
- genuinely independent unfinished substrate -> narrow, rename, and declare an
  exact downstream consumer;
- contradictory `.pypeline` semantics -> historical evidence only after
  `.pype` cutover.

Do not run them merely because chain files exist.

### Historical platform-evidence caveat

The historical `native-platform-followup/completion-manifest.json` is
spec-hash-valid, but that does not prove its referenced evidence is still
available or current. The preservation audit found twelve referenced plan
artifacts absent locally and on the active cloud checkout, plus eleven
referenced working artifacts whose hashes have drifted. Until reconciled, the
strategy must not claim complete historical-proof preservation.

Platform S1 therefore owns a milestone-by-milestone disposition ledger with
expected path/hash, observed path/hash, and one explicit state:
`import_verified`, `recover_required`, `reprove_in_native`,
`reprove_in_platform`, or `unavailable_nonblocking_with_rationale`. Any unique
proof required by a later gate blocks that consumer until recovered or
re-proved. Native S7 hands the final retained/reproved set forward; Platform S6
must prove the ledger is closed before public certification.

## Handoff artifacts

Each boundary should be mechanical:

| Producer | Required handoff |
|---|---|
| Custody M11/consolidation | Completion manifest covering RA/Custody/WBC versions, acceptance transaction, replay, runtime provenance, negative fixtures, and a 57k-scale bounded projection receipt with full-rebuild parity |
| Milestone-gate bootstrap | Installed intermediate-gate/transition schema and driver proof; exact-tree negative tests; migrated Native/Platform specs; `downstream-spec-readiness.json`; completion manifest |
| Native Parity S2F | `.pype` identity/compiler receipt, authored host identity and durable-boundary call-site templates, source/runtime correspondence, graph lock, GO-FORMAT proof |
| Completion kernel C1/C2 | Experimental package/import contract; schema, serialization, hash, reader/writer versions; durable predicate; adapter map; evidence-scope and candidate-outcome model; current divergence-ledger hash; restore and projection-invariance receipts; shadow acceptance integration |
| Native Parity S2R | Total completion semantics for every durable primitive, crash/reentry proof, child-set and waiver aggregation instances, named-exit supersession proof, and the sole authoritative kernel-enablement receipt |
| Native Parity S7 | Megaplan-wide inventory equality, executed golden trace, no competing completion writer, installed/cloud conformance, public-candidate extraction inventory |
| Platform S4 | Isolated extraction/recomposition and Megaplan consumption without semantic drift |
| Platform S6 | Two-consumer conformance, compatibility matrix, public/experimental surface classification, final proof map |

Downstream launch should use `chain_completed` with
`require_manifest: true` where a chain boundary remains. Milestone labels or
status strings are not sufficient.

## Rejected plans

### Run the five-sprint completion epic immediately after M11

Rejected because S2F has not yet fixed the canonical subjects to bind.
This invites schema churn and reverse dependencies on Megaplan internals.

### Finish Native Parity, then run all five completion milestones

Rejected because Native Parity's live migration would first encode legacy
completion and rework behavior. Completion M3/M4 would repeat the migration.

### Finish Platformization, then add completion

Rejected because storage, approval, worker, and compatibility surfaces would
already expose a de facto completion model that would be expensive to unwind.

### Let Completion own persistence, leases, workers, and effects

Rejected because M11 and Platformization already own those mechanisms.
Completion should evaluate semantic obligations using their evidence, not
become a second control plane.

### Declare the API public after the Megaplan slice

Rejected because a single product cannot distinguish neutral semantics from
well-disguised product policy. The second consumer is a prerequisite to
stability.

## Recommended execution plan

1. Let M11 finish; do not weaken its acceptance criteria.
2. Produce and independently validate the M11 completion manifest, then close
   the known incident-projection scalability gap with a 57k-scale Custody
   follow-up receipt before Native launch.
3. Run the one-sprint milestone-gate bootstrap in the same Custody checkout.
   Require its final manifest and `downstream-spec-readiness.json`; it must
   migrate and preflight both downstream specs but must not launch them.
4. Audit the actual completion state of the older Native Python and Composition
   chains and record an explicit retain/import/supersede disposition for every
   milestone.
5. Run the prepared Native Parity chain:
   - S2F establishes durable-boundary call-site identity templates;
   - Completion Kernel C1 lands the neutral package, versioned spec/identity,
     shadow evaluation, divergence ledger, and named-exit terminal;
   - Completion Kernel C2 lands immutable binding/evaluator schemas, wire
     compatibility, restore/projection proof, and shadow acceptance integration;
   - S2R instantiates aggregate semantics and is the sole authoritative
     enablement point;
   - every later cutover consumes those exact proof receipts and ledger hash;
   - S5A/S5B executes the M10/M11 false-done, discontinuous-manifest,
     accepted-attempt-closure, bounded-history, and causal-rework fixtures.
6. Run Platformization only after Native Parity's exact final manifest proves
   no live competing completion authority. It owns neutral extraction,
   authoring/tooling, second-consumer proof, and public certification.
7. Keep the standalone completion chain non-launchable and preserve its five
   briefs, governing proposal, and 83-entry crosswalk as normative
   traceability.
8. After each chain, refresh the shared checkout from the exact
   `editible-install` commit, verify predecessor state/manifests in that same
   checkout, and refuse older same-named cloud artifacts.

## Disposition of the second oracle review

The review's central verdict is accepted. Repository inspection confirms its
three required amendments and sharpens them:

1. **Aggregation split — accepted.** C2 defines the algebraic signatures and
   remains shadow-only. S2R owns child-set freezing and concrete instances for
   map/reducer, retry, loop, human, checkpoint, and effect primitives. GO-0 is
   the sole live-enablement receipt.
2. **Identity caveat — accepted and made concrete.** S2F currently owns
   authored/component/graph identity, not runtime human or rework occurrences.
   It must add source-stable durable-boundary call-site templates; S2R and
   admission instantiate occurrences.
3. **Q49 ownership — accepted with an upstream correction.** The known O(N)
   implementation is Custody's incident projector, not a future completion
   query. Custody must fix and benchmark it before Native; S5B consumes and
   rechecks the bounded path.
4. **Package/import boundary — accepted.** The generic kernel is fixed under
   experimental `arnold/workflow/completion/`; Megaplan adapters remain
   product-side, with a cumulative import lint.
5. **Projection, divergence, restore, and persisted compatibility gaps —
   accepted.** They are now explicit C1/C2 receipts rather than late oracle
   questions.
6. **Single disposition registry — amended.** The review correctly detected a
   collision risk but the repository contains two different semantic axes:
   platform enforcement dispositions and completion candidate outcomes. They
   must not be one enum. Each has one canonical registry, and their interaction
   is a total generated mapping.

One proposed optimization is rejected after repository inspection:
Platformization S2B and S3 should not trail S4/S5. The current Platform Contract
explicitly treats S2B's format/package/identity/refactor core as S4-blocking,
and S3 supplies the complete local authoring and diagnostic loop that the
extraction and independent consumer must use. Moving them later would let S4 or
S5 invent temporary authoring/package semantics and would weaken the
independence test.

## Oracle review dossier

The oracle should review code, initiative sources, fixtures, and manifests—not
only this prose. At minimum inspect:

- `docs/arnold/standardized-completion-spec-proposal.md`
- `.megaplan/initiatives/standardized-completion-specifications/`
- `.megaplan/initiatives/megaplan-native-parity-corrective/`
- `.megaplan/initiatives/native-python-pipelines-completion/`
- `.megaplan/initiatives/native-composition-followup/`
- `.megaplan/initiatives/native-platform-followup/` (historical substrate)
- `.megaplan/initiatives/native-workflow-platformization/` (future extraction)
- the authoritative cloud M11 plan state, accepted-attempt records, recovery
  traces, and eventual completion manifest
- current implementations of completion contracts, admission, Run Authority,
  Custody, WBC, review/rework, frontier compilation, status, and acceptance.

The oracle should distinguish:

- **subject identity** from obligation identity;
- **semantic completion** from transition authority;
- **evidence** from authorization;
- **liveness** from completion;
- **canonical records** from projections;
- **experimental extraction** from stable public API.

### A. Sequencing and supersession

1. Does S2F truly provide every stable identity coordinate Completion M1/M2
   requires, or is another identity stage needed before the kernel?
2. Would inserting the completion kernel before S3A create any circular
   dependency on Megaplan phase migrations?
3. Which exact work in `native-python-pipelines-completion` and
   `native-composition-followup` is already completed, uniquely valuable, or
   not covered by the corrective initiative?
4. Is it correct to treat `.pypeline` plans as superseded by `.pype`, or are
   there live consumers whose migration must be a separate gated step?
5. Should the kernel be two milestones inside Native Parity or a separate
   bridge chain? What failure/recovery behavior materially favors one?
6. Are Platformization's existing preconditions stale or misleading if they
   require the older chains rather than the corrective manifest?

### B. Ownership and abstraction boundaries

7. Is the proposed ownership split mechanically enforceable in package imports
   and APIs, or can Completion accidentally depend on Megaplan policy?
8. Which package should own neutral `CompletionSpec`, `CompletionBinding`, and
   `CompletionVerdict` types without creating Arnold-to-Megaplan reverse
   dependencies?
9. Does the completion evaluator merely evaluate obligations, or does any path
   let it mint Run Authority, custody, WBC, or acceptance authority?
10. Can Platformization persist and index completion records without creating a
    second semantic status column that later becomes authoritative?
11. Are effect completeness, absence proof, and reconcile evidence cleanly
    split between Completion semantics and Platform mechanisms?
12. Are review finding classification and non-convergence correctly retained
    as Megaplan policy while task admission and execution remain neutral?

### C. Durable-subject generation

13. Is the durable-subject predicate statically checkable from the post-S2F
    compiler model, with S2R then providing its composition semantics?
14. Does it cover registered effects, suspension/reentry, checkpoint/attempt
    ledger participation, custody/authority requirements, and artifacts crossing
    durable boundaries?
15. Can a pure helper hide any of those behaviors, and will the compiler reject
    it deterministically?
16. Will workflows, steps, dynamic tasks, human gates, effects, and rework
    subjects each receive exactly one generated template without contract noise
    on ordinary helpers?
17. Which obligations are mechanical, and what is the minimum domain-specific
    author declaration?

### D. Binding and evidence semantics

18. Is the binding frozen at the only correct point—admission—and consumed
    unchanged on resume?
19. Is `(spec_hash, obligation_id)` the executable obligation identity, with
    semantic IDs stable and never reused?
20. Does the evidence scope include all restore, store, attempt, generation,
    source/runtime, dependency, custody, fence, and WBC coordinates that can
    invalidate reuse?
21. Can evidence from different attempts or restore generations be stitched
    accidentally?
22. Are complete-capture absence and set-equality proofs backed by genuinely
    complete windows rather than missing receipts?
23. Is verifier independence structural—different implementation provenance,
    producer identity, trust domain, and primary evidence access—or just a
    caller-supplied label?
24. Do waiver scope, expiry, authority, and transitive taint survive workflow
    composition without becoming clean parent acceptance?

### E. Candidate dispositions and composition

25. Is evaluation explicitly per proposed candidate outcome, avoiding
    `applies_when` circularity?
26. Do blocked, suspended, failed, waived, denied, cancelled,
    pending-reconciliation, and quarantined candidates each have nontrivial
    evidence obligations?
27. Is quarantine correctly nonterminal unless a separate terminal policy is
    explicitly admitted?
28. Does parent aggregation define a total mapping for every child disposition?
29. Are unselected branches proven not applicable, admitted loop/fanout child
    sets proven complete, and aggregate multiplicity protected from evidence
    double-counting?
30. Can any projection, Markdown report, status label, heartbeat, or model
    narrative satisfy an obligation or authorize a transition?

### F. Native Parity integration

31. Can S3A–S7 consume one kernel without phase-specific copies or adapters
    becoming permanent semantic owners?
32. Is S5A the right shadow boundary and S5B the right live boundary for the
    complete execute/review/rework slice?
33. Does the M10/M11 fixture prove both false-done rejection and normal
    admission of genuinely new review work?
34. Are existing accepted tasks preserved during rework without rebinding,
    while reopened tasks receive a new attempt/generation?
35. Does S7 prove exact inventory equality among durable subjects, bindings,
    required evidence, accepted decisions, effects, and terminal outcomes?
36. Which legacy completion writers/readers remain, who owns their expiry, and
    what test proves each writer is inert?

### G. Platformization integration

37. Does Platform S1 inventory and challenge the complete Native candidate
    without inventing a second lifecycle or disposition registry?
38. Can Platform S2A extract neutral admission, evaluation, and inspection
    without forking the Native implementation or acceptance transaction?
39. Does Platform S2B derive templates from `.pype` and package locks only when
    they can affect executable meaning or obligations?
40. Are Platform S3 views, diagnostics, and author documents generated
    projections that cannot influence authority?
41. Does Platform S4 migrate Megaplan to the extracted surface through one
    receipt-bound transition with no reverse product dependency?
42. Is Platform S5's consumer independently originated and materially different
    enough to expose falsely generic completion semantics?
43. Does Platform S6 freeze only behavior proven by both consumers and preserve
    an explicit experimental surface for the rest?

### H. Migration, compatibility, and operational proof

44. What is the exact shadow-to-enforced cutover rule, and how is every
    divergence individually disposed?
45. Can old suspended runs resume with pinned old bindings while new runs use
    the new spec version?
46. What changes require new attempt, explicit migration, quarantine, or hard
    rejection?
47. Are editable, clean checkout, wheel/sdist, and cloud worker identities
    proven identical?
48. Can status or fixer code still call a chain complete while the newest
    admitted plan has an unresolved binding?
49. Review the proposed Custody fix for the known full-journal incident
    projection: does checkpoint/snapshot-plus-tail invalidation remain correct
    across malformed lines, truncation, store-incarnation change, restore, and
    concurrent append, while meeting the 57,000-event latency/memory budget?
50. Does every failure create one stable occurrence whose narrowing evidence
    updates the same finding rather than changing blocker identity repeatedly?

### I. Second-consumer and public API proof

51. Is the proposed second consumer genuinely unrelated in obligations,
    topology, and operating environment?
52. Can static scans prove it does not import or copy Megaplan adapters,
    defaults, fixtures, terminology, or review policy?
53. Which candidate APIs fail substitutability and should remain experimental
    or be removed?
54. Does the compatibility matrix distinguish schema, verifier, binding,
    evidence, runtime, and product-policy evolution?
55. Is there any public promise being frozen before two independent consumers
    and installed-package tests prove it?

### J. Empirical go/no-go questions

56. Show one captured legacy false pass that the new kernel rejects without
    manually curated evidence.
57. Show one valid old behavior that shadow comparison preserves exactly.
58. Show a crash at admission, execution, review, rework, and acceptance
    resuming without duplicate work or cross-window evidence reuse.
59. Show a waiver at depth propagating visible taint to the root.
60. Show an absence claim remaining unknown when capture completeness is
    unavailable.
61. Show changed source, runtime, dependency, store incarnation, custody epoch,
    fence, and WBC version each independently invalidating reuse.
62. Show an unrelated consumer forcing at least one API revision or deletion;
    if it changes nothing, explain why it was genuinely adversarial.
63. Show that no second evidence registry, verdict type, acceptance authority,
    scheduler, lease system, effect ledger, or durable store was introduced.
64. Show that C2 remains non-authoritative until S2R's accepted GO-0 receipt,
    and that no crash between C2 and S2R can partially enable the kernel.
65. Show that every supported S2R primitive supplies one total aggregation
    instance conforming to C2's signatures, while an incomplete candidate
    mapping fails at compile/admission rather than runtime.
66. Show that `superseded_by_named_exit` preserves each intervening binding and
    cannot be laundered into success, waiver, cancellation, or
    not-applicable.
67. Show that the neutral kernel package has no product import and that both
    Megaplan and the unrelated consumer depend inward through declared
    interfaces rather than copied adapters.

## Oracle verdict format requested

Ask the oracle to return:

1. **Verdict:** adopt, adopt with amendments, or reject.
2. **Sequencing corrections:** exact milestone moves or prerequisite changes.
3. **Ownership corrections:** any responsibility assigned to the wrong layer.
4. **Circular dependencies:** with concrete code or artifact paths.
5. **Duplicate systems risk:** existing machinery that the proposal may
   accidentally recreate.
6. **Missing empirical proof:** fixtures/traces required before cutover.
7. **Supersession table:** retain/import/supersede for every older native
   milestone.
8. **Public API decision:** what can be stable, experimental, or private.
9. **Smallest sound plan:** the minimum milestone set that preserves the North
   Star without duplicating work.

The oracle should cite code, schemas, fixtures, executed traces, and current
chain manifests. A prose-only agreement is not sufficient.
