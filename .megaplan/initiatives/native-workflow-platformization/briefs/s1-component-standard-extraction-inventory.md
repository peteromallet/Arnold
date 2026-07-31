# S1 — Component standard and extraction inventory

Before extraction, ingest and validate the exact completion supersession
crosswalk plus `completion-crosswalk-readiness.json`. Produce a row-by-row
Platform owner/proof inventory; reject unknown milestone labels, missing proof
rules, stale hashes, or free-text-only destinations.

Also inventory every milestone and proof artifact from the historical
`native-platform-followup` manifest. Record expected path/hash, current
path/hash, and one explicit disposition: `import_verified`,
`recover_required`, `reprove_in_native`, `reprove_in_platform`, or
`unavailable_nonblocking_with_rationale`. Missing or drifted evidence may not
be described as preserved. Any uniquely required proof blocks the consuming
milestone until recovered or re-proved.

## Objective

Consume the completed Native Parity handoff and turn its proved product-native
semantics into a pinned, executable **candidate** component standard. Produce
the classification, reference models, negative corpora, DX baseline, and
conformance/traceability skeletons that S2A, S2B, and S3 can implement without
inventing protocol semantics. This sprint pins an experimental contract for
reproducible work; it does not certify a stable platform.

## Normative contract and inputs

[`../decisions/PLATFORM_CONTRACT.md`](../decisions/PLATFORM_CONTRACT.md) is the normative
cross-milestone contract. This brief assigns S1 ownership; it does not abridge or
override that contract. If wording here appears to differ, the contract wins
and the inconsistency is a blocking defect.

Required launch inputs are:

- the accepted milestone-gate bootstrap completion manifest and its exact
  proof-artifact rows for `downstream-spec-readiness.json`,
  `completion-crosswalk-readiness.json`, and
  `editable-runtime-readiness.json`;
- the content-addressed completion manifest for
  `megaplan-native-parity-corrective` and its accepted final proof map, where
  the handoff path and content hash are mandatory proof entries;
- the exact Native-to-Platformization handoff manifest at
  `.megaplan/initiatives/megaplan-native-parity-corrective/platformization-handoff-manifest.json`;
- the exact Native C1 contract/identity manifest, C2 binding/evaluation
  manifest, authoritative S2R GO-0 kernel-enablement receipt, and the current
  content-addressed divergence-ledger head named by that handoff;
- the exact Native proof rows for the durable-subject predicate/static lint,
  stable `(spec_hash, obligation_id)` identity, candidate-first disposition
  evaluation, blocked/waived/quarantine policy, normative evidence window,
  presence/complete-capture absence, producer/trust-class verifier
  independence, S2R primitive aggregation instances, waiver taint and
  multiplicity, human/rework templates, reopen-as-new-admission, neutral import
  lint, store-incarnation restore invalidation, stable finding/occurrence
  divergences, false-pass golden exemplar, and projection deletion/rebuild/
  forgery invariance;
- the accepted Custody bounded/cursor-incremental incident-projection handoff
  and its 57k benchmark receipt, consumed through the exact Native handoff
  rather than reconstructed here;
- the handoff's candidate/dependency map, typed contract snapshots, source-to-
  runtime golden adapters, trace-field contract, diagnostic/DX corpus,
  benchmark environment and measured baselines;
- the exact adopted `.pype` contract/compiler/converter/minimal-preview
  versions, accepted `GO-FORMAT` receipt, package/source correspondence,
  identity/migration matrix, and exact-pinned legacy-retention receipts;
- certified production-store/service CAS and adapter provenance, controlled
  WBC producer/manifest-evolution rules, proof-registry incarnation/high-water
  semantics, generic-zero-Megaplan-import proof, and typed outgoing-seam
  expiry/inertness evidence; and
- the Native Parity golden and product conformance receipts. S1 extends them;
  it must not substitute a friendlier corpus, reset the benchmark, or introduce
  test-only lifecycle or admission semantics.

An incomplete or non-content-addressed handoff blocks S1. File existence or a
schema marker alone is not proof. Fix the predecessor; do not reconstruct
M11/Native proof or create Platformization-local authority.

## Locked decisions

- Arnold is a component platform, not a Megaplan helper package; `.pype`
  source remains the sole product control-flow authority.
- `docs/arnold/pype-authoring-contract.md` is the sole format authority. Every
  `.pype` has exactly one canonical `@workflow`; every durable root or child
  workflow has its own `.pype`. Private local steps and pure helpers may remain
  in that file and fold into its digest; reusable steps/effects/schemas/
  policies/helpers live in `.py`. A `.py @workflow` is preview-only. Static
  imports can address only another file's canonical workflow, never private
  members. There are no library-only/multi-workflow files, file export tables,
  re-exports, declaration-order entrypoints, or authored `subflow` kind.
- Classify every handed-off construct as exactly one of: core runtime primitive,
  stable reusable-pattern candidate, experimental/two-consumer-unproven
  pattern, or Megaplan-specific behavior. Classification evidence does not
  confer stable status.
- Pin candidate Component Descriptor v1, deterministic durable-Python profile,
  component lifecycle, composition/resource algebra, identity and namespace
  rules, resolution/evolution contracts, trace contract, and conformance
  capability model exactly as the platform contract requires.
- Pin the one `docs/arnold/workflow-execution-mode-dispositions.yaml` registry
  containing all five
  modes, all six dispositions, and the logical store/capability access matrix.
  Every prose/CLI/editor table is derived from it. Working-tree
  edit/repeat/fork is an easy isolated experiment; silent changed-code
  production resume, production-store leakage, and experimental-evidence
  promotion remain impossible.
- Pin the versioned conservative executable-closure digest algorithm, canonical
  serialization/hash version, and closed exclusion list; there is no
  implementation-defined behavior classifier.
- Pin governed distribution namespace ownership/delegation/fork lineage,
  distinguish conflicting-authority collision from legitimate same-key version
  evolution, and require exact version selection.
- Route-bearing discriminants are named finite enums/unions distinct from
  payload. Whole-payload/open-string/callable routing rejects.
- Business outcomes and lifecycle/control terminals are disjoint. Outcome-
  condition evaluation and local terminal acceptance are atomic. Only a
  statically total root-host adapter can propose root product truth. The
  invoking admission binding owns adapter selection by default; a producer may
  offer a named default, but `default_pipeline` never implies it.
- Human timeout/escalation is a total typed graph. Parent loops, named exits,
  typed reconfiguration, joins, cancellation, Custody and resources use the
  durable protocols in the platform contract.
- Production arbitration means certified real-store/service linearizable
  conditional mutation with production adapter and proof-registry provenance;
  fake CAS and application read/check/write cannot certify it.
- Capability profiles are mechanically derived from descriptor, lowered
  topology, transitive lock, and resolved bindings—not trusted self-report—and
  independently re-derived under inclusion/removal/rebind mutations.
- Trace-field/volatile-allowlist changes require independent governance,
  invalidate affected receipts, and independently replay pinned raw histories;
  they cannot retroactively launder a failed comparison.
- `new_instance_compatible` and `resume_compatible` are different claims.
- Product types, outcomes, policies, prompts/models/tools, effects, storage and
  budgets remain consumer-owned typed bindings. Shared defaults may not encode
  Megaplan meaning.
- Candidate artifacts remain `experimental` through S5. Only S6 can promote a
  challenged and certified version to `stable`.
- Completion candidate outcomes and platform enforcement dispositions remain
  two canonical, versioned typed registries. S1 inventories their generated
  total boundary mapping and rejects any combined enum or consumer-local
  translation table.
- Completion schemas, including the persisted binding envelope, are internally
  versioned from Native C1/M1. Native S2R GO-0 begins the persisted-wire
  compatibility and authoritative-decoder promise, which is inherited
  unchanged. S1 records both dates; no Platform milestone before S6 publishes a
  stable public authoring or API surface.
- The mechanical durable-subject predicate is authoritative: pure helpers need
  no completion contract and may not hide durable behavior; every admitted
  durable subject gets exactly one generated template. Static lint and
  admission reject omissions before authority.

## Required work

1. Validate and ingest every field of the Native Parity handoff; produce a
   content-addressed intake receipt mapping each input to its producer,
   verifier, exact commit/lock/schema and intended S1 consumer.
2. Freeze the package-direction and extraction inventory. Record dependency
   direction, coupling, generic/product classification, exclusion rationale,
   and proposed capability profiles for every step, workflow (including one
   hosted as a subworkflow), and candidate.
   Inventory the exact CompletionSpec, CompletionBinding, CompletionVerdict,
   candidate-outcome registry, enforcement-disposition registry, generated
   total boundary mapping, acceptance adapter, schema/decoder, proof corpus,
   current divergence-ledger hash, legacy completion writers/projections, and
   all remaining Megaplan coupling. Also inventory every
   `PWC-COMPLETE-04` invariant and exact proof row from the required inputs.
   Do not redesign, copy, or locally reinterpret any of them.
3. Publish candidate schemas and executable reference transition models for:
   one-workflow files/private members/static canonical imports/package default
   selection; ordinary locked third-party imports inside shared step bodies;
   the immutable typed policy envelope; descriptor/lifecycle;
   source-manifest-lock-registry authority; root hosting;
   outcome conditions; human suspension; retry/new generation; parent-loop
   ledger; JoinPolicy; cancellation/Custody/resource settlement; named exits;
   reconfiguration; durable agentic outer/inner boundary; effects/LLM;
   checkpoint payloads; the enforcement mode/disposition/store registry; the
   distinct completion candidate-outcome registry and total boundary mapping;
   evolution;
   substitution; governed raw-to-normalized partial-order trace truth; and
   `arnold.workflow.event_envelope.v2` bidirectional occurrence/attempt ↔
   agent/model/tool/effect/cost/log-artifact correlation.
4. Revalidate and republish the adopted machine schemas and corpus for
   `arnold.pype.executable_closure.v1`,
   `arnold.workflow.semantic_ir.v1`,
   `arnold.workflow.executable_envelope.v1`, and
   `arnold.workflow.graph_lock.v1`, using RFC 8785 canonical JSON and SHA-256.
   Preserve the closed exclusions and reject undefined tagged encodings.
   Component digests cover own closure/direct dependency contracts; the
   separately hashed graph lock pins selected transitive executables. Publish
   canonical decision data, stable child
   identity, frozen fanout binding, keyed-multiset reduction, closed error and
   finite named route-discriminant rules. Define manifest schema/hash and
   governed producer/trace-field-registry evolution before S2A changes
   serialized topology. Freeze exact environment/optional-feature/plugin pins
   for ordinary step dependencies and the policy component-versus-graph-lock
   digest placement.
5. Define the typed binding environment and precedence for domain ports,
   policies, capabilities, effects, storage, models/tools and budgets. Define
   logical component identity, distribution namespace/fork authority, static
   import/alias provenance, descriptor-owned optional default selection,
   invoking-admission root-adapter ownership, and the content-addressed
   transitive lock.
   Define platform-issued agent-session identity, optional provider provenance,
   protected transcript/log artifact refs, optional consuming decision/
   terminal joins, and rebuildable reverse indexes that never become authority.
6. Turn the contract into invalid descriptor, composition, topology, mode,
   lifecycle, authority/effect, payload, trace and evolution corpora. Every
   rejection has a stable code, exact source span, supported rewrite or a
   deliberately unsupported-boundary recipe.
7. Extend the inherited diagnostics/DX suite: route-smuggling mutations,
   compile/replay repeatability, ten-task timed author simulation, source-map
   and traceback checks, no-network compile/local p50/p95 thresholds, and
   changed-code edit/repeat/fork versus silent-resume paired scenarios.
8. Create the executable conformance and traceability skeletons consumed by
   S2A/S2B/S3 and named by the final S6 gate:
   `scripts/validate_native_workflow_platform_stage_gate.py`,
   `scripts/validate_native_workflow_platform_conformance.py`,
   `docs/arnold/native-workflow-platform-conformance.yaml`, and
   `docs/arnold/native-workflow-platform-traceability.yaml`. Skeletons must
   fail honestly for unimplemented S2A–S6 rows; no hand-authored green status.
   The stage validator consumes only the rows owned through the current
   milestone and rejects missing, extra, stale, red, unbound, unconsumed, or
   self-certified rows. The final validator consumes the complete applicable
   set.
   Create the fixed non-shell transition-handler entry points and the
   independent post-transition verifier referenced by `chain.yaml`. Later
   milestones implement their state changes; S1 supplies the shared
   wrong-tree, stale-receipt, partial-state, replay and handler-self-
   verification rejection contract.
9. Establish the initial proof-map schema. Each obligation records owning
   sprint/gate, authoritative producer, independent verifier, negative/mutation
   evidence, exact run/commit/lock/artifact/schema, and derived status.
10. Build contract-authored classifier mutations: every digest inclusion/
    exclusion category, every route-discriminant form, every logical store
    class/capability, trace-field amendment/invalidation/replay, and every
    capability-profile inclusion/removal/rebind. Production implementations
    cannot generate their own sole oracle.

## Gates

### Semantic gate

- The executable reference models cover every cross-milestone contract family,
  including five-mode/six-disposition behavior, and disagreeing source,
  generated artifact, descriptor, registry or runtime routes fail.
- Descriptor/composition validity, lifecycle result separation, total root and
  join mappings, outcome-condition atomicity, human race policy, resource
  accounting, trace field classification, compatibility claims and capability
  closure are unambiguous and mechanically checkable.
- Exact-one canonical workflow, package with multiple separate workflow files,
  private-member isolation, canonical import aliases, cycle/recursion/
  collision, preview-only `.py` workflows, allowed-helper provenance, hidden
  effects, finite discriminants, digest inclusion/exclusion, distribution
  fork/collision/version evolution, root-adapter selection, physical moves,
  logical renames, and descriptor mismatch are executable reference fixtures.
- Every candidate/exclusion has one recorded classification and dependency
  direction; generic candidates have zero Megaplan reverse imports/defaults.

### Proof gate

- Current gaps make at least one relevant positive or negative reference test
  fail for the expected reason; a prose-only or vacuously green corpus fails S1.
- Every compiler rejection code has a supported construct/example or an
  explicit non-durable/declared-boundary disposition.
- The inherited and extended DX corpus is pinned to a comparable environment
  with numeric baselines. Production-CAS claims cite the inherited real adapter
  receipts and are never satisfied by the local fake.
- Conformance/traceability skeletons enumerate all 38 acceptance-suite families
  and all eleven closure clauses from the platform contract, with owners and
  evidence schemas, even where execution remains red pending later sprints.
- The S1 stage gate consumes `s1-proof-map.json` before merge eligibility and
  rebinds it to merge HEAD; all later milestones declare the same typed gate
  over their own proof map.

### Adoption gate

- Candidate descriptor/profile/package/registry status is explicitly
  `experimental`; no public surface claims stable compatibility or adoption.
- The intake receipt proves the exact C1/C2/S2R artifacts, current
  divergence-ledger hash, and Custody bounded-projection receipt were consumed;
  a locally reconstructed kernel, decoder, registry, ledger, or projector
  fails the gate.
- The reproduced false-done/`REVIEW` golden exemplar and every inherited
  `PWC-COMPLETE-04` row are green before S1 hands work to S2A. A missing human
  or rework identity may proceed only through the exact admitted
  deferred-template gate; narrative deferral fails.
- S2A can promote runtime meaning in place, S2B can implement the authoring
  core, and S3 can implement DX/tooling without unresolved product semantics or
  hidden decisions. Any unresolved generic-vs-product or policy-vs-protocol
  question blocks handoff.

## Artifacts and S2A/S2B/S3 handoff

Produce a content-addressed S1 handoff containing the candidate standard,
descriptor/profile/trace schemas, extraction inventory and dependency map,
reference transition models, invalid corpora, inherited-plus-extended DX
corpus and baselines, diagnostic catalog, conformance/traceability skeletons,
and proof-map schema. The handoff records exact experimental versions and the
open failing rows, split explicitly between S2A runtime ownership, S2B
authoring-core ownership, and S3 DX/tooling ownership.

## Do not close this sprint if

- any cross-milestone rule exists only as prose or a local test convention;
- any mode/disposition, lifecycle/control result, root/condition/human/join/
  resource branch, trace field, compatibility claim or capability profile can
  fall through an implicit default;
- production authority is inferred from a fake/in-process CAS, projection,
  generated manifest, receipt hash without semantic consumption, or producer
  self-verification;
- inherited Native Parity evidence or benchmark cases were dropped or reset;
- S1 labels the candidate standard stable; or
- the S2A/S2B/S3 handoff lacks content-addressed provenance, executable
  failures, or an unambiguous ownership split.

## Non-goals

- Implementing the platform runtime or extracting product patterns.
- Rebuilding RA, Custody, WBC, recovery, projections or their stores.
- Generalizing every Megaplan phase, freezing compiler internals, building a
  marketplace, supporting arbitrary durable Python, or adding open-ended event
  streams/opaque polling loops.
- Selecting product prompt/model/policy/budget values.
