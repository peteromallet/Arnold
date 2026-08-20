# Workflow Platformization ticket audit against implementation-facing feedback

## Verdict

The Workflow Platformization ticket already closes the original component-
standardization gap well: it defines contracted components, a common lifecycle,
composition algebra, closed outcomes, declared effects, instance isolation,
content-addressed resolution, in-flight evolution, adversarial recomposition,
and black-box substitutability. It also correctly defers extraction until
Native Parity supplies one correct product implementation and requires a
genuinely unrelated second consumer.

The latest feedback does **not** justify another sprint or a broader product-
specific expansion. It exposes six material Stage 2 omissions and two smaller
clarifications:

1. dependency determinism is covered, but deterministic **authoring and replay**
   are not;
2. adoption-facing compiler diagnostics, source maps, debugging, and fast local
   tests are not specified;
3. component/checkpoint evolution is covered abstractly, but the ordinary
   “edited a Python function while runs are suspended” case is not concrete;
4. LLM invocations have no standard identity, replay, budget, or cache contract;
5. checkpoint serialization is covered, but payload size/reference discipline
   is not;
6. effect declarations are covered, but the exact retry/idempotency key and
   recorded-outcome replay rule should be normative;
7. the relationship among source, generated `WorkflowManifest`, component
   descriptor, component lock, and action-admission envelope is implicit; and
8. first-class human gates are strong semantically but lack a portable local
   test/fast-forward contract.

All fit as bounded amendments to S1–S5 and their gates. Native Parity remains
the owner of Megaplan-specific topology and migration. Platformization should
standardize only the product-neutral contracts and developer surfaces.

## Coverage map

| Feedback area | Current ticket coverage | Assessment |
| --- | --- | --- |
| Python source is sole control-flow authority | The North Star requires native `.pypeline` composition; S2 forbids ambient mutable authority/product defaults; the completion proof says handlers, metadata, adapters, projections, and CLI/auto surfaces cannot own routes. | **Substantially covered.** Add the generated-artifact ownership rule so the compiler/manifest cannot become a second authored topology. |
| Deterministic restricted-Python subset | S2 rejects nondeterministic identity and locks dependencies, but nowhere defines which Python operations are replay-safe or how time/random/environment/I/O are mediated. | **Blocking gap.** Dependency resolution determinism is not execution/replay determinism. |
| Boundary contracts, closed outcomes, declared effects | Component Descriptor v1, canonical serialization, closed-outcome exhaustiveness, lifecycle/composition rules, negative admission corpus, and effect-safe-action extraction all cover this. | **Strongly covered.** Sharpen effect idempotency and recorded-outcome replay, not the overall structure. |
| Identity and isolation | S1 declares namespaces; S2 derives them from composition path plus semantic instance key; S3 proves duplicate/concurrent isolation; closure and acceptance gates repeat it. | **Fully covered.** No structural amendment needed. |
| Humans as first-class components | Human gate is a candidate pattern; descriptor/lifecycle include suspension/reentry; recomposition and fault suites include human suspension and resume. | **Semantically covered.** Missing only a standard fake/fast-forward test interface and reentry-payload test fixtures. |
| Reuse ladder | The five claims are explicit and separately proved. | **Fully covered.** |
| Compiler diagnostics and debugging | S5 mentions documentation, readability, and edit locality; registry failures promise deterministic diagnostics. No source locations, actionable errors, source maps, or debugger/traceback behavior. | **Material DX gap.** |
| Fast local testing | Conformance suites are extensive, but there is no product-team unit/component harness that avoids a full deployed durability stack. | **Material DX gap.** |
| Code evolution with suspended runs | S4 proves pinned-old/compatible/migration/quarantine; S5 defines change classes and migration windows. | **Covered in principle, underspecified in the everyday source-edit case.** |
| LLM-specific execution | Model choices and cost are left consumer-variable; no prompt/model/tool identity, recorded-output replay, budget, or cache semantics are standardized. | **Blocking for an LLM workflow platform.** Values may remain consumer-owned, but binding and replay invariants cannot. |
| Checkpoint payload discipline | Canonical state serialization and checkpoint compatibility exist; artifact namespaces exist. No inline-size, canonicalization, artifact-reference, retention, or sensitive-data rule. | **Material operational gap.** |
| Contract stack and generated artifacts | Descriptor, dependency lock, program/checkpoint digests, RA/Custody/WBC bindings, and causal envelope exist separately. `WorkflowManifest` and the source-to-generated-artifact ownership split are absent. | **Material clarity/admission gap.** |
| Avoiding premature abstraction | Separate follow-on sequencing, candidate classification, two-consumer rule, and explicit non-goals all reinforce it. | **Fully covered.** Do not add more generic patterns to address this feedback. |

## Smallest amendments to the existing five sprints

### S1 — add the authoring, replay, and durable-data contracts

Add four bounded deliverables:

1. **Deterministic authoring profile v1.** Define the supported `.pypeline`
   Python subset and its semantic reason, including:
   - permitted control-flow/data constructs and deterministic collection
     iteration;
   - stable semantic instance keys for runtime-created children;
   - forbidden ambient time, randomness, environment reads, filesystem/network
     I/O, process/global mutation, and undeclared concurrency in orchestration
     code;
   - declared runtime providers for clock, entropy, environment/config, I/O,
     effects, human input, and LLM calls;
   - replay rules: deterministic decisions re-execute; non-repeatable work
     consumes a recorded accepted outcome and may not silently run again.

   This must be described as a deliberate durable-Python profile, not as
   “ordinary Python with surprising exceptions.” The source remains the sole
   owner of product control flow even though only the durable subset is legal.

2. **Contract-stack ownership map.** Normatively state:

   ```text
   .pypeline source
     owns authored semantic topology and local policy declarations
       -> compiler/source map
   generated WorkflowManifest + component descriptors
     own immutable admitted runtime coordinates, never new product routes
       -> content-addressed component/dependency lock
   action-admission envelope
     joins exact executable bindings with RA + Custody + WBC
   journal/checkpoints/effect outcomes
     own durable history; projections only explain it
   ```

   Treat a product Plan Contract as a consumer-owned input/interface contract,
   not a platform authority primitive. Platformization need not redesign or
   standardize Megaplan's Plan Contract.

3. **LLM invocation contract v1.** Require declared identities for prompt
   template/version/digest, model capability and resolved provider/model,
   tool-set/schema versions, decoding and routing policy, input/context digest,
   and token/cost/deadline budget policy. Define which changes invalidate a
   checkpoint or cache key; record accepted outputs and usage so replay consumes
   history instead of calling the model again; make retry/fallback a new
   declared attempt with stable parent causality rather than an invisible
   rerun. Provider/model choices and budget values remain consumer-owned
   bindings.

4. **Checkpoint payload contract v1.** Define canonical serialization, inline
   size limits, aggregate checkpoint limits, artifact-reference thresholds,
   content digest/schema/version requirements, retention/liveness guarantees,
   and rejection of nonportable handles or undeclared sensitive material.
   A checkpoint must not become an unbounded object store.

Amend the S1 gate so its invalid corpus includes forbidden nondeterminism,
unstable collection/child identity, undeclared I/O/LLM calls, oversized or
noncanonical checkpoint payloads, stale artifact references, prompt/tool/model
identity drift, and generated manifests that add or erase source topology.

### S2 — enforce determinism and make failures point back to authored code

Add four implementation requirements:

1. Enforce the deterministic authoring profile before lowering. Every rejection
   must have a stable diagnostic code, exact source span, plain-language reason,
   legal rewrite/example, and relevant contract link. Batch independent errors
   where possible so authors do not discover restrictions one compile at a
   time.
2. Preserve source maps through `.pypeline` -> IR -> generated
   `WorkflowManifest` -> component instance. Runtime failures and causal traces
   must name the user's file, function, call site, semantic path, and component
   instance; compiler/driver frames are supplementary, not the only traceback.
3. Generate one admission receipt joining source/program digest, generated
   manifest digest, component contract/implementation digest, dependency lock,
   policy and LLM binding digests, state/payload schema versions, and the
   RA/Custody/WBC coordinates required at the action. Generated artifacts may
   validate and lower source semantics but may not introduce product routes.
4. Enforce effect invocation through declared effect slots. Derive the
   idempotency/reconciliation key from run + semantic occurrence/component
   instance + effect slot + logical action occurrence (with attempt identity
   kept distinct). Persist intent before dispatch and accepted outcome before
   continuation. Replay consumes the outcome; absence/ambiguity enters the
   declared reconciliation path rather than re-firing implicitly.

Amend the S2 gate with deterministic compile-twice and replay-twice proofs,
source-location snapshots for representative illegal constructs and runtime
faults, manifest/source topology equality, and crash injection around each
effect edge.

### S3 — provide the fast local authoring and component-test loop

Make the first extracted patterns consume a product-neutral local test kit:

- in-process deterministic runner with an in-memory journal/artifact store and
  virtual clock;
- typed fakes/spies for phases, policies, effects, capabilities, storage,
  clock/entropy, LLM invocations, and human decisions;
- fixtures to suspend at and fast-forward a human gate with a validated reentry
  payload, including stale/duplicate/wrong-capability negatives;
- fault injection at admission, phase result, checkpoint, effect
  intent/outcome, suspension, resume, and terminal acceptance;
- snapshot/inspection of emitted lifecycle events, outcomes, checkpoints,
  budgets, cache decisions, and namespace derivation;
- deterministic replay from recorded phase/LLM/effect/human outcomes without
  contacting real services.

The harness is not a second runtime semantics implementation: it executes the
same lifecycle/validator code behind in-memory adapters. A normal component
unit test should not require RA/Custody/WBC services, a cloud worker, or a real
model, while conformance/integration tests still exercise those real joins.

Gate S3 on concise tests for each first-wave pattern covering ordinary success,
human suspension/fast-forward, replay without repeated effects/LLM calls, and
two concurrent instances. Set an explicit local-test latency budget so the
developer loop cannot silently become an integration deployment.

### S4 — make evolution and the second consumer deliberately ordinary

Keep the existing upgrade proof, but spell it as changes developers actually
make while runs are suspended:

- function-body-only change with unchanged public contract;
- topology/control-flow change;
- prompt-only change;
- model/tool/policy binding change;
- port/outcome/state/checkpoint schema change;
- dependency implementation change.

For each, prove the deterministic disposition for suspended old runs: resume on
retained pinned artifacts, resume under a declared compatible range, execute an
explicit migration producing a new admitted binding, start a new run, or
quarantine. “Latest code” is never an implicit resume rule. Include a human
gate suspended on v1 while v2 is deployed, and require the old locked wheel and
prompt/tool assets to remain resolvable for the promised support window.

Also require the unrelated consumer to exercise one LLM-backed component with
different prompt/model/budget bindings and one payload large enough to cross
the artifact-reference threshold. This validates the generic contracts without
turning either consumer's domain behavior into platform policy.

### S5 — certify the developer surface and operational lifecycle

Extend publication/certification with:

- authoring-profile/version compatibility and diagnostic stability;
- source-map and user-code traceback conformance;
- local test-kit API, examples, fakes, human-gate fixtures, and latency budget;
- ordinary source/prompt/model/tool evolution matrix and pinned-artifact
  retention policy;
- LLM recorded-output replay, cache-key/provenance, token/cost budget, retry,
  and fallback conformance;
- checkpoint payload/reference, retention, redaction, and garbage-collection
  rules;
- effect idempotency/reconciliation conformance.

Stable registry status should require these proofs when the corresponding
feature is declared by a component. A deterministic pure component need not
pass LLM- or external-effect-specific cases; the conformance manifest must say
which capability profiles apply.

## Amendments to the closure contract and acceptance suite

Do not replace the ten clauses. Expand them narrowly:

- **Descriptor:** add authoring-profile version, declared nondeterminism
  providers, LLM invocation slots, checkpoint payload class/limits, and effect
  replay/idempotency semantics.
- **Lifecycle:** specify recorded-outcome replay for phase/effect/LLM/human
  boundaries.
- **Composition:** include deterministic collection iteration and stable dynamic
  child keys.
- **Authority and evidence:** bind generated manifest, authoring profile,
  prompt/model/tool/policy, state/payload schema, and dependency-lock digests in
  the appropriate executable/admission envelope; none independently grants
  authority.
- **Evolution:** enumerate ordinary source, topology, prompt, model/tool/policy,
  schema, and dependency changes, with deterministic pinned/migrate/new-run/
  quarantine outcomes.
- **Conformance:** add authoring diagnostics/source maps, fast local harness,
  deterministic replay, LLM, payload-bound, and effect-idempotency profiles.

Add acceptance families (or fold them into the current twelve):

1. deterministic authoring negatives and compile/replay equivalence;
2. actionable compiler/runtime source diagnostics;
3. in-process component tests with phase/effect/LLM/human fakes;
4. no repeated LLM/effect/human action on replay of accepted outcomes;
5. prompt/model/tool/policy identity and budget/cache behavior;
6. inline payload bounds and durable artifact-reference recovery;
7. suspended-v1/deployed-v2 evolution across the ordinary change matrix; and
8. source -> generated manifest -> component lock -> admission receipt
   provenance and topology equality.

## What should not change

- Do not move these amendments into Native Parity; that epic should prove one
  source-authoritative product and hand off real candidates/traces.
- Do not generalize additional Megaplan phases merely because the platform gains
  a richer contract.
- Do not standardize product prompts, model selections, budgets, business
  outcomes, or effect implementations. Standardize their typed declaration,
  identity, admission, replay, and evolution behavior.
- Do not create a second simulator semantics for local tests; use the production
  lifecycle and validation core with in-memory adapters.
- Do not promise arbitrary Python. Promise a clearly versioned durable-Python
  profile with excellent diagnostics and explicit providers for nondeterminism.
- Do not let generated manifests, component registries, WBC evidence,
  projections, or test fixtures become alternative route authorities.

## Final recommendation

Amend the existing five-sprint ticket; do not add a sixth sprint. The ticket's
architecture, sequencing, and component algebra are sound. Its main remaining
risk is that it could produce a semantically rigorous platform that is opaque
or slow for authors—or one whose resumes are undermined by ordinary Python,
LLM, source-evolution, or checkpoint behavior that was never standardized.

The sharper Stage 2 endpoint is:

> A `.pypeline` source is the sole product control-flow authority within a
> versioned deterministic Python profile. Its generated manifest and locked
> component graph preserve, but never invent, that topology. Every non-repeatable
> boundary is declared, identified, recorded, budgeted where applicable, and
> replayed from durable history. Authors can compile, debug, and unit-test the
> same lifecycle locally with actionable source-level feedback; suspended runs
> resume only against pinned or explicitly migrated code and data.

