# S2F — `.pype` Compiler, Identity, and Converter

## Objective

Implement the adopted `.pype` authoring contract as one static product-neutral
frontend, emit source-stable durable-boundary call-site identity templates, and
close GO-FORMAT before the completion kernel, any durable runtime primitive, or
any Megaplan product phase depends on it.

This sprint owns grammar, discovery, linking, authored/component/graph identity,
source-stable call-site templates, package correspondence, migration
conversion, diagnostics, and minimal non-durable preview. C1/C2 own the
non-authoritative completion contracts. S2R owns runtime occurrence identity
and durable control/runtime semantics. Platformization later productizes the
developer toolchain; it must not replace this frontend.

Normative format authority:
`docs/arnold/pype-authoring-contract.md`.

## Receipt-bound authoring cutover

Consume S1's staged rename/inventory while keeping `.pypeline` selected for new
work through merge. The pre-merge and post-merge readiness gate proves the
candidate compiler/linker, converter, exact-one rules, package correspondence,
legacy resolution, and rollback safety. The chain's typed transition then
validates and consumes that exact current receipt and atomically:

- selects `.pype` for new authoring, compilation, package admission, and
  certification;
- applies the staged canonical-source/descriptor/package/source-map switch;
- rejects `.pypeline` for new work while retaining exact-pin resolution for
  already admitted occurrences; and
- records old/new suffix, source, descriptor, component/graph-lock, reader,
  registry, and migration snapshots.

The post-transition GO-FORMAT verifier reruns against the selected state before
S2F can complete. Wrong-tree, pre-merge, stale, red, cross-incarnation,
partial-switch, wrong legacy-reader, and replayed-receipt mutations leave the
old path usable and cannot strand admitted work.

## Required work

1. Parse `.pype` as restricted Python syntax without executing author source.
   Enforce exactly one canonical top-level workflow, private local steps and
   helpers, shared `.py` leaves, canonical-only workflow imports, leaf laws,
   and cycle/recursion/dynamic-topology rejection.
   Permit ordinary Python/third-party imports inside shared `.py` step
   implementations; pin their selected distribution/version/artifact,
   optional-feature, Python/runtime-environment and plugin requirements in the
   graph lock or explicit bindings, and reject import-time effects/mutable
   Arnold registration, ambient dependency selection, imported topology and
   undeclared effect bypass.
2. Implement one source index/linker over checkout, editable install, wheel,
   sdist, and cloud resources. Preserve definition/import/call spans and alias
   provenance; reject source/descriptor/resource disagreement.
3. Implement logical identity and the versioned canonical executable-closure
   digest exactly as frozen in the authoring contract. The canonical form is
   conservative and syntactic: it may cause safe extra drift, but it may never
   omit a reachable declared dependency, prompt, policy, model/tool binding,
   constant, or private/shared behavior slice.
   Implement the common immutable policy envelope with stable kind/schema,
   canonical values, explicit scope/attachment, provenance, precedence and
   digest; reject mutable/ambient defaults, callables, open route tables and
   hidden overrides.
   Keep component and graph identity separate: a component digest includes its
   own canonical closure and direct dependency contract requirements; the
   transitive lock separately pins every selected concrete executable digest
   and receives its own graph-lock digest. Admission/checkpoint/proof surfaces
   bind both; do not recursively cascade every child implementation digest into
   every ancestor.
4. Extend the existing canonical Arnold descriptor/lock/manifest owner. Do not
   create `package.toml`, a second registry, a route catalog, or path-derived
   identity. Implement distribution-coordinate ownership, authorized fork
   lineage, optional `default_pipeline`, canonical workflow visibility, source
   correspondence, locks, and migration log.
5. Resolve root-result adapters independently of `default_pipeline`. The
   invoking admission binding supplies exactly one total adapter unless the
   producer descriptor exposes an explicitly named default adapter.
6. Implement the mechanical `.pypeline`/authored-subflow converter and staged
   cutover transaction. They create one workflow per `.pype`, classify private/
   shared steps, update the canonical descriptor and migration log atomically,
   and refuse ambiguity.
7. Emit stable diagnostics and supported rewrites for every structural
   rejection. Provide check, compile, inspect, static topology, and minimal
   `authoring_preview` commands through the same parser/lowerer.
8. Enforce the execution-mode store/capability matrix. Preview uses ephemeral
   or logically isolated namespaces and credentials and cannot reach admitted
   authority, product-history, proof/evidence, effect, checkpoint, idempotency,
   or production cache capabilities. A shared physical blob service is legal
   only through disjoint non-production authority, keys, indexes, retention,
   and discovery.
9. Create GO-FORMAT readiness and post-transition conformance/traceability proof
   maps, validator receipts, transition receipt, and verifier receipt using the
   generic chain gate/transition interface. The validator independently
   recomputes all bindings and rejects missing, extra, red, stale, unbound,
   unconsumed, cross-incarnation, self-certified, or pre-proof-map-hash
   evidence.
10. Emit a source-stable durable-boundary call-site identity template for every
    authored workflow/step, human suspension declaration, effect boundary,
    dynamic-child creation site, and rework/reopen declaration. Bind each
    template to authored/component/graph identity, source span, executable
    closure, graph lock, allowed occurrence kind, and declaration provenance.
    S2F must not allocate runtime invocation, human, fanout-child, or rework
    occurrences. Admission and S2R instantiate those beneath the template;
    S5 admits product-created reopened and genuinely new work.
    A human-gate or rework subject that cannot be fully instantiated at S2F
    must still have an explicit source template plus a versioned deferred-
    instantiation schema naming the allocator, required runtime coordinates,
    admission lint, and S2R/S5 closure owner. The GO-FORMAT gate rejects an
    implicit or unowned deferral.
11. Publish exact inventory equality across authored durable declarations,
    call-site templates, source maps, manifests, and graph locks. Pure helpers
    have no template or independent durable identity; their behavior remains in
    the containing executable digest.
12. Freeze the Native step-authoring-package contract that S3A must consume.
    Extend the Step-IO declaration vocabulary with `StepAuthoringSpec` ownership
    annotations only; field shape, type and validation remain references to
    Step-IO and a conformance lint rejects any duplicate schema declaration.
    Freeze five ownership classes: `model_required`, `model_hint`, `derived`,
    `protected`, and `model_proposal(merge=...)`. Joint proposal merges are
    named deterministic meet/join operations over declared safety lattices and
    must be monotone in the safety direction; arbitrary callbacks reject.
    Keep ownership orthogonal to Step-IO presence, nullability, default,
    cardinality and candidate-outcome applicability. Missing required model
    semantics produces repair; optional model content records absence/default;
    omitted hints/proposals use declared neutral values; derived/protected
    fields are never requested. Defaults cannot invent required semantics.
    Freeze a response-directory format from day one (`fields.yaml`, optional
    `body.md`, and child files for nested/stable records), the nested-child
    convention, stable diagnostic codes, normalized parsed rendering, schema
    compatibility rules, and derivation purity. Derivations may read only the
    admitted typed input, parsed model fields and declared receipts—never the
    ledger or ambient sibling results. Body validation is structural only;
    semantic prose quality remains a critique/completion obligation.
    Freeze the attempted-finish disposition protocol: safe deterministic fill,
    accept, same-live-session continuation, replacement repair session, changed-
    evidence generation, or repeated-fingerprint fixer escalation. Same-session
    continuation is the default for locally repairable required omissions, has
    a declared budget, and is recorded as a new repair attempt; session identity
    is provenance rather than authority.

## GO-FORMAT gate

The readiness `conformance_gate` runs before merge eligibility and again
against merge HEAD. It covers at least:

- exact-one file rules and canonical-only linking;
- private/shared ownership and leaf laws;
- ordinary locked imports inside shared `.py` steps, plus import-time,
  dynamic-dependency, imported-topology and undeclared-effect negatives;
- typed policy envelope round-trip, attachment/precedence/digest and
  callable/open-route/ambient/mutable-default negatives;
- no source execution, re-export laundering, cycles, recursion, hidden I/O, or
  dynamic topology;
- deterministic source maps and conservative executable-closure digests;
- physical move versus logical/behavioral drift;
- namespace/fork collision and legitimate version-evolution cases;
- descriptor/default/root-adapter/source/lock/resource correspondence;
- preview-only `.py` workflows and store/effect isolation;
- exact-pin legacy retention and converter refusal cases; and
- exact inventory equality for human-gate and rework/reopen templates,
  including fail-closed deferred-instantiation schemas and their named closure
  owners; and
- authoring-spec conformance to Step-IO; deterministic monotone proposal merges;
  response-directory/nested-child parse and compile equivalence; derivation
  purity; protected-field comparison; and a valid-but-wrong parse fixture whose
  normalized rendering exposes the semantic inversion; and
- orthogonal required/optional/applicability behavior; attempted-finish
  interception; same-session repair; dead-session replacement; changed-evidence
  generation; and bounded identical-failure fixer escalation; and
- checkout/editable/wheel/sdist/cloud equivalence.

The transition consumes that readiness receipt; the post-transition verifier
then proves the selected state. S2F cannot close and C1 cannot start unless
both receipts are green and content-addressed. C1/C2 consume the exact identity
handoff; S2R later independently revalidates GO-FORMAT and both kernel receipts
before consuming compiler output.

## Deliverables

- one compiler/index/linker and versioned IR;
- canonical executable-closure digest implementation;
- descriptor/lock/manifest and namespace/fork integration;
- source maps and diagnostic catalog;
- converter and minimal preview/check/inspect/topology surface;
- format corpus, mutation corpus, validator, traceability, proof map, and
  accepted readiness/transition/post-transition GO-FORMAT receipts; and
- a content-addressed S2F handoff naming authored/component/graph identity,
  durable-boundary call-site templates, human/effect/rework declarations,
  any explicitly gated deferred-instantiation schema, and every frozen
  interface C1/C2 and S2R consume; and
- a content-addressed authoring-package handoff naming the Step-IO vocabulary,
  response-directory and child-file format, ownership algebra and safety
  lattices, derivation inputs, compiler/schema versions, diagnostic catalog and
  normalized-render contract that S3A consumes and Platformization cannot
  reopen.

## Do not close if

- discovery executes source or another compiler/registry appears;
- “behavior relevant” remains an implementation judgment rather than a
  versioned canonicalization rule;
- a whole payload or open string can become a route key;
- a path/resource name becomes logical identity;
- legitimate package version evolution is mistaken for a namespace collision,
  or an unauthorized fork can retain the coordinate;
- `default_pipeline` silently supplies a root-result adapter;
- preview can touch an admitted capability or relabel its output as durable;
- legacy syntax can author new work after the transition, the old path is
  disabled before it, or the transition can be skipped/partially applied; or
- a runtime human, fanout-child, invocation, or rework occurrence is
  preallocated at S2F, a durable declaration lacks a call-site template, or a
  pure helper receives one; or
- an authoring spec redeclares Step-IO shape/type/validation, a joint field uses
  arbitrary merge code, a derivation reaches into the ledger, nested records
  depend on frontmatter, or a valid-but-wrong parse is not visibly normalized;
  or
- attempted finish releases a locally repairable session, an optional omission
  causes a model call, required semantic content is silently defaulted, session
  continuity becomes authoritative, or identical repair prompts loop without a
  deterministic budget/escalation; or
- GO-FORMAT is narrative, self-declared, stale, or first enforced after merge.
