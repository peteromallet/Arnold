# Native Workflow Platformization North Star

Platformization consumes the exact completion supersession crosswalk and the
bootstrap's accepted mechanical-traceability receipt. Every row assigned to a
Platform milestone must resolve to a real conformance/proof rule and be
revalidated at S6; free-text ownership or nominal milestone completion is not
evidence.

## Destination

Arnold becomes a workflow-component platform, not a Megaplan helper library and
not merely a runtime containing importable Python functions. A product team can
install qualified, versioned steps and subworkflows from reusable packages,
bind its own domain types, policies, capabilities, models, storage and effects,
compose them in native `.pype` Python, and obtain the same declared
semantics in a clean checkout, wheel/sdist installation and compatible cloud
worker.

Megaplan is the first load-bearing proof of that shape. It is not privileged in
the platform contract. An unrelated workflow must be able to use the same
patterns without importing or copying Megaplan, inheriting Megaplan defaults,
or moving its own product meaning into a shared runtime layer.

The platform has three deliberate layers:

```text
Arnold workflow platform
  authoring, lowering, lifecycle, identity, suspension, effects and proof

Reusable workflow components and patterns
  contracted steps and subworkflows with product-neutral orchestration mechanics

Product workflows
  Megaplan, an unrelated adversarial consumer and future products
```

The shared layers own reusable orchestration mechanics. Product packages retain
their domain inputs, outcomes, artifacts, policies, prompts, budgets and effect
implementations.

## One readable semantic authority

The authored `.pype` Python is the sole product control-flow authority.
Branches, loops, dynamic fanout/fanin, retries, reentry, human gates,
reconfiguration and terminal proposals are visible there through the supported
deterministic Python profile and typed durable primitives. Helpers, handlers,
status fields, route tables, generated manifests, registries, schedulers,
projections and logs may not secretly choose what happens next.

Lowering and source maps preserve that authored meaning. Generated manifests,
component descriptors and content-addressed locks own admitted runtime
coordinates and executable selection; they cannot add, erase or reinterpret a
route. Plan Contracts remain product interface declarations, not runtime
authority. The platform must reject an unsupported durable construct with a
source-located explanation and a supported path, never silently relocate its
control flow into an opaque handler.

## One `.pype`, one workflow

`docs/arnold/pype-authoring-contract.md` is the shared normative format
authority. Every durable root or child workflow has one `.pype`; every `.pype`
has exactly one canonical top-level `@workflow`. A `.pype` may contain private
file-local steps and digest-bound pure helpers, but only its workflow crosses
the file boundary. There are no multi-export or library-only `.pype` modules,
file-local export tables, or declaration-order entrypoints.

Shared steps/effects/schemas/policies/helpers live in `.py`. A `.py` workflow
may run only as explicit non-durable preview and can never admit, checkpoint,
resume, replay, publish, or certify. A step is a leaf and cannot invoke a
workflow or decorated step. “Subworkflow” remains the role of a workflow at a
parent call site; generated child references may exist, but no second authored
`subflow` kind does.

Linking parses static `.pype` and `.py` dependencies without executing source.
Only canonical workflows are importable from `.pype`. Dynamic/conditional/star
imports, import registration/re-export laundering, import cycles, recursive
workflow calls, and identity/version collisions fail before durable lowering.
Explicit finite loop constructs are not recursion.

Logical workflow identity is distribution plus stable logical workflow name;
physical paths are provenance. Distribution names are governed publisher
namespaces: forks use a new name or accepted delegation, while legitimate
version digests under one authorized lineage are evolution rather than
collision. Contract digests use a pinned, versioned conservative
executable-closure algorithm with a closed exclusion list; they do not depend
on a subjective behavior classifier. Package metadata owns the optional default
pipeline, distribution lineage, the cross-package allowlist of canonical
workflows, exact locks, source/descriptor correspondence, and append-only
identity migrations. A resolved run identity is immutable through admission
and replay.

Every route-bearing value is a named finite discriminant distinct from payload.
Whole-payload, open-string, callable, exception-text, or hidden route tables do
not satisfy source visibility.

`default_pipeline` selects only a workflow. The invoking admission binding owns
the statically total root-result adapter by default; a producer may offer named
adapters and nominate one named default, but invocation still accepts and pins
it explicitly.

This discipline must remain pleasant: file-local private steps keep small
workflows compact; diagnostics provide actionable rewrites; unsupported Python
may be explored in non-durable preview; and S2B ships extract/inline/promote
refactors and the authoring/package/identity core, while S3 ships navigation,
lint/format, topology view, package verification, preview/test experience, and
developer benchmarks before reusable extraction or stable publication.

Shared `.py` step bodies retain ordinary Python and third-party import freedom;
exact selected distributions, environment, optional features and plugins are
pinned, while imported code cannot add topology or bypass declared effects.
Policies remain immutable typed Python values lowered through one canonical
envelope with explicit kind/schema, attachment, provenance, precedence and
digest—not a second policy language or an untyped config-map escape hatch.

## Contracted components, not reusable-by-convention helpers

Steps and workflows—including workflows hosted as subworkflows—share one
qualified, versioned component model. A component contract declares typed ports
and state, closed conditioned
business outcomes, distinct lifecycle/control terminals, dependencies,
policies, capabilities, effects and compensation, suspension/reentry,
identity/namespaces, checkpoint discipline, declared nondeterminism and the
applicable conformance surface.

The platform must prove, separately:

1. source reuse without copying or reverse product imports;
2. clean-install reuse from independently installed packages;
3. deterministic dependency reuse through a complete content-addressed lock;
4. shape-independent reuse at root and when nested, sequenced, looped, fanned
   out, retried, suspended or cancelled; and
5. behavioral substitutability under explicit compatibility claims.

The same invocation remains isolated wherever it is placed. Durable identity
derives from run lineage, parent semantic path, qualified component identity
and a stable instance/item key rather than from Python object identity or list
position. A root-host adapter is the only layer that maps an eligible component
result into a root product terminal proposal. `new_instance_compatible` and
`resume_compatible` remain different claims: suspended work stays pinned,
migrates explicitly or quarantines.

## Durability without a second semantic system

The authored meaning must survive checkpoint, crash, replay, retry, human wait,
redeployment, cancellation, compensation and cross-host resume. Replay consumes
recorded nondeterministic boundary results rather than silently repeating model
calls or effects. A changed executable can begin a fresh experiment, fork or
admitted migration, but cannot impersonate the executable pinned by an existing
production occurrence.

Every authority-increasing action is admitted only when exact executable,
contract, dependency, policy, model/tool and state bindings join with:

```text
current Run Authority grant and coordinator fence
AND current exact-target Custody lease and epoch
AND required exact-version WBC boundary/effect history
```

Run Authority permits and arbitrates. Custody owns current exclusive
responsibility. WBC records exact durable boundary and effect history. Effects
use declared intent/outcome, idempotency, ambiguity and reconciliation
protocols. Checkpoints preserve reentry state. Projections, logs, caches,
receipts, repair requests, comparison records and golden artifacts explain or
request; none authorizes or routes. Every arbitration or consumption point
ultimately uses the certified linearizable conditional operation in the
canonical production store/service, with independent proof of the real adapter
and raw event history.

Portable events carry stable occurrence, generation, attempt, platform agent-
session, model/tool/effect, trace/span, cost and protected log/transcript
correlation keys. Generic tools navigate in both directions between workflow
source and agent records. Reverse indexes are rebuildable; durable-boundary
events and immutable artifact refs remain the auditable truth. This does not
require instruction-by-instruction Python tracing.

This epic consumes the accepted control-plane, durability, effect, recovery,
worker and proof substrate handed off by Native Parity and its predecessors. It
does not create parallel Run Authority, Custody or WBC stores, a second
production CAS, a second lifecycle engine, an alternate local route engine, or
a competing projection/recovery stack. Missing prerequisite behavior is fixed
upstream or blocks the epic; it is never locally emulated to make a milestone
green.

The Native-to-Platformization handoff is itself a mandatory proof-map artifact
whose path and content hash are verified by the predecessor completion
manifest. File existence or a schema marker is not launch evidence.

The handoff also carries the exact Native completion implementation: C1/C2
manifests, S2R's sole authoritative kernel-enablement receipt, final current
divergence-ledger hash, schema/serialization/decoder and internal persisted-wire
matrix, candidate-outcome registry, adapter/proof corpus, false-done/`REVIEW`
fixture, legacy-writer retirement, and Custody's bounded-projection/57k
benchmark receipt. Platformization extracts and productizes that exact
implementation; it must not fork a second evaluator, re-enable the kernel,
create another acceptance transaction, or rebuild the Custody projector.

The handoff is accepted only when the Native completion manifest binds the
complete executable kernel contract and its current proofs:

- the mechanically checkable durable-subject predicate and cumulative static
  lint, including the rule that a pure helper has no completion contract and
  cannot hide durable behavior;
- candidate-first evaluation, typed proof requirements for blocked and waived
  candidates, and quarantine as nonterminal unless an admitted terminal policy
  explicitly says otherwise;
- `(spec_hash, obligation_id)` as executable obligation identity, stable
  semantic obligation IDs, and an immutable admission binding;
- the normative evidence-window tuple, presence and complete-capture absence
  proof modes, and verifier independence by producer identity and trust class;
- S2R's concrete total child-disposition mappings, frozen child sets,
  multiplicity/no-double-counting rules, and transitive waiver-taint
  propagation for every supported durable primitive;
- S2F durable-boundary call-site templates, including human-gate and rework
  identities or the accepted deferred-template gate, plus the rule that reopen
  is a new admission referencing the prior subject rather than mutation or
  rebinding;
- store-incarnation restore invalidation, projection deletion/rebuild/forgery
  invariance, the reproduced false-pass golden exemplar, and divergences
  recorded through the stable finding/occurrence system; and
- the neutral-package import-lint receipt proving that completion types import
  neither Megaplan nor Arnold product policy and that product adapters remain
  product-side.

Platformization may challenge whether the public surface is usable or generic.
It may not silently alter those semantics. Any incompatibility is repaired in
the owning Native/kernel layer or remains an explicit experimental limitation;
it is never resolved by a Platform-local registry, evaluator, adapter copy, or
evidence rule.

Completion candidate outcomes and platform enforcement dispositions are two
different semantic axes and remain two versioned typed registries. Their
interaction is one total generated mapping that rejects unknown pairs.
Collapsing them into one enum or adding an unversioned consumer-local table is
a hard failure.

Each axis has exactly one canonical registry. Product, CLI, editor and platform
tables are strict generated projections whose equality and unknown-entry
rejection are tested; none is an independently editable registry.

## Freedom to experiment, precision about claims

Safety attaches to the claim an execution makes, not to the act of trying code.
The platform supports five explicit execution modes:

- `authoring_preview` for fast working-tree trials with no durable claim;
- `durable_sandbox` for isolated experiments and forks using production
  lifecycle semantics with safe bindings;
- `comparison` for quarantined, non-authoritative shadow/replay evaluation;
- `admitted_production` for exactly pinned authority-bearing execution; and
- `certification` for evidence-backed compatibility and stable publication.

Every restriction has one declared disposition in each applicable mode:
`always_hard`, `automatic`, `production_admission_gate`,
`stable_publication_gate`, `authoring_advisory`, or `non_durable_only`. The one
machine `docs/arnold/workflow-execution-mode-dispositions.yaml` registry also
owns logical
store/capability access. All prose/CLI/editor tables are derived from it; there
is no runner-local or implicit warning-to-error promotion. Preview, sandbox,
comparison, and certification defaults cannot mutate production logical
stores, keys, namespaces, or effect/idempotency domains even when they share a
physical backend.

Editing a step and running it repeatedly is deliberately easy. The platform
automatically assigns a fresh digest, experiment lineage, attempt, namespace,
cache disposition and safe effect identity. An author may repeat a step against
typed fixtures or fork an immutable recorded boundary without first declaring a
production migration. The hard wall is truthful lineage: experimental history
cannot overwrite admitted history, reuse production effect/idempotency identity
or be relabelled as production or certified evidence.

## Prove before stabilizing

Platformization follows one ordered, seven-milestone argument:

1. S1 publishes and pins an **experimental candidate** component standard and
   executable contract corpus, including the exact Native completion schemas,
   registries, adapters, proof and coupling inventory; its pin makes receipts
   reproducible, not stable.
2. S2A implements and enforces the product-neutral runtime, lifecycle,
   completion admission/binding/evaluation/evidence-scope/inspection,
   authority, state, and observation contract by promoting the accepted
   implementation in place, never by forking it or performing another kernel
   enablement.
3. S2B productizes the S4-blocking `.pype` compiler/linker, conservative
   digest, package/distribution identity, converter, transactional refactors,
   source correspondence, completion-template derivation, and install
   equivalence.
4. S3 completes CLI/editor/navigation/format/lint/topology/preview/test
   experience, completion inspection and generated machine/Markdown views,
   unfamiliar-author tasks, and benchmarks over that exact core. Every view is
   a disposable projection.
5. S4 extracts the first proven patterns and makes Megaplan consume them under
   isolation, recomposition, exact completion-conformance and no-duplicate-
   writer proof.
6. S5 challenges the design with a machine-scanned unrelated consumer,
   unfamiliar bindings and shapes, an independently originated implementation,
   different completion obligations, a human/effect boundary, admitted rework
   or analogous new work, independent profile re-derivation, and real evolution
   scenarios; it may require revision or removal.
7. Only S6 may freeze and publish stable descriptors, profiles, packages,
   registries and public compatibility promises.

Completion schema records, including the persisted binding envelope, are
internally versioned from Native C1/M1 so every later record carries an
unambiguous version. The authoritative persisted-wire compatibility promise and
decoder enforcement begin at Native S2R GO-0. Platform S6 freezes only the
public authoring/API surface proven by both consumers; it does not originate or
retroactively redefine storage compatibility.

The authoring result must be elegant rather than contract-heavy. An author uses
one canonical `.pype` surface to declare durable intent and only the domain
obligations that cannot be generated mechanically. Deterministic tooling
derives and pins templates and admission bindings, rejects an omitted durable
subject or obligation, and generates completion worksheets and Markdown reports
as disposable, non-authoritative projections. Pure helpers require no
completion declaration. No author hand-edits obligation IDs, bindings, evidence
windows, registries, source maps, locks, or reports.

No Megaplan phase is generalized merely because its source can be imported.
Product-specific planning, critique, gate, finalization and task meaning stay in
Megaplan until an unrelated consumer demonstrates the shared abstraction. An
unproven pattern remains explicitly experimental rather than weakening the
standard or manufacturing a ceremonial second consumer.

## Completion truth

This epic is complete only when exact, content-addressed and independently
checked proof shows that:

- an unrelated non-Megaplan workflow clean-installs multiple shared patterns,
  supplies different domain contracts and bindings, recomposes them in
  unfamiliar supported shapes, and receives product-neutral causal explanation;
- Megaplan consumes the extracted implementations without changing its accepted
  normalized behavior or recreating hidden orchestration;
- concurrent instances remain isolated and suspension, replay, cancellation,
  effects, resource settlement and cross-host resume preserve the component
  contract;
- an independent implementation swap, compatible upgrade, pinned old run,
  explicit migration and quarantine exercise the separate new-instance and
  resume-compatibility promises;
- effective conformance profiles are derived mechanically from source,
  topology, transitive locks and resolved bindings, independently re-derived
  under inclusion/removal/rebind mutations, and every applicable production,
  packaging, trace, CAS, effect, LLM, checkpoint, resource and DX profile
  passes;
- trace allowlist changes have independent approval, receipt invalidation, and
  pinned raw-history replay; the unrelated consumer's independence manifest/
  scan permits generic Arnold imports while proving no Megaplan product
  coupling; and
- S6 accepts the final proof map, reusable-pattern registry and
  content-addressed completion manifest after validator self-mutations and the
  S5 challenge, while every unproven abstraction remains experimental.

Hand-authored status, self-verification, hash-only receipts, fake-store
atomicity, stitched traces, comparison evidence or a successful import are not
completion. The decisive proof is that another product can safely decompose,
recompose, evolve and substitute these components while the authored Python
remains the one semantic authority and the existing durable control plane
remains the one runtime authority substrate.

No supersession or publication record may orphan M11, Native, historical
platform, false-pass, restore, bounded-replay, or live-cutover evidence still
referenced by an active binding, accepted decision, proof row, compatibility
promise, or retained run. Generated Markdown may be deleted; canonical records
and content-addressed evidence may not.
