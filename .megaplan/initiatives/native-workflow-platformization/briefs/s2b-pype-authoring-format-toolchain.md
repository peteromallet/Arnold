# S2B — `.pype` authoring core

## Objective

Productize the adopted `.pype` authoring contract as one product-neutral
compiler/linker, package/identity, conversion, and transactional-refactoring
core over the S2A runtime substrate. Deliver every semantic and install-form
capability S4 extraction depends on; leave editor integration, formatting,
linting, interactive topology, CLI ergonomics, unfamiliar-author studies, and
DX performance budgets to S3.

Native Parity owns the repository-wide `.pypeline` → `.pype` cutover, the first
grammar and conversion primitive, minimal preview, Megaplan's migration, and
preservation of its accepted semantics. S2B does not redo that migration or
reopen the format decision. It turns the proven product-local surface into the
reusable experimental authoring core required by S3 and S4. S3 productizes the
human-facing experience without adding another parser, rule registry, identity
model, or runtime meaning.

## Normative contract and inputs

`docs/arnold/pype-authoring-contract.md` is the sole normative format authority.
`../decisions/PLATFORM_CONTRACT.md` remains normative for lifecycle, composition,
identity, admission, execution modes, and proof.

Consume:

- the accepted Native Parity completion and Platformization handoff manifests;
- Native Parity's grammar/schema, compiler, diagnostics, converter, minimal
  preview, source/package correspondence proof, authoring-package format and
  shadow/cutover receipts, and legacy/identity receipts;
- S1's content-addressed candidate standard, format corpus, DX baselines,
  conformance skeleton, and proof-map rows; and
- S2A's product-neutral lifecycle, composition, admission, identity, lock,
  checkpoint, effect, trace, completion kernel, and local-kit implementation.

Missing predecessor behavior is fixed by its owner or blocks S2B. S2B must not
create a second compiler, lifecycle engine, package descriptor, lock format,
identity registry, or migration log.

## Locked decisions

- Every `.pype` contains exactly one top-level `@workflow`. Zero or multiple
  workflows are a structural error in every mode; preview flexibility belongs
  to ordinary `.py`.
- Every durable root or child workflow lives in its own `.pype`. “Subworkflow”
  is a call-site hosting role, not another decorator, source kind, or format.
- A `.pype` may contain private file-local steps and digest-bound pure helpers.
  They cannot be imported, re-exported, independently addressed, or separately
  pinned.
- Reusable steps, effects, schemas, policies, and helpers live in `.py`.
  Workflow topology in `.py` is legal only in explicit ephemeral preview.
- Composition imports only another `.pype` file's canonical workflow. There are
  no multi-workflow or library-only `.pype` files, file export tables,
  workflow re-exports, authored `subflow` definitions, dynamic/star/conditional
  imports, or source execution during discovery.
- Steps are leaves. Step-to-workflow, decorated-step-to-decorated-step, and
  helper-to-workflow/step/effect calls are structurally invalid in every mode.
- Stable logical identity is `(distribution_name, logical_workflow_name)`,
  where the logical name is an explicit `@workflow(id=...)` or the decorated
  function name. Distribution names are governed publisher namespaces; forks
  require a new name or accepted delegation/lineage. Same-authority version
  digest evolution is not a collision. Paths, filenames, wheel resources, and
  aliases are provenance.
- Executable identity uses the pinned conservative executable-closure
  algorithm/schema IDs, RFC 8785 serialization, SHA-256, and closed exclusion
  list from the authoring contract. A component digest covers its own closure
  and direct dependency contract requirements; a separate graph-lock digest
  pins selected transitive executables, and durable carriers bind both. S2B
  does not implement a subjective “behavior-relevant” classifier or recursively
  cascade every child implementation digest into every ancestor.
- Physical source/resource moves preserve logical and executable identity only
  when the logical key and behavior digest are unchanged; provenance is still
  updated atomically. Logical rename, extraction/inline, signature, outcomes,
  hostability, policy, private/shared promotion, or behavior drift requires an
  explicit compatibility or migration disposition.
- The existing canonical Arnold descriptor owns optional `default_pipeline`,
  distribution authority/lineage, cross-package canonical-workflow
  allowlisting, source correspondence, dependencies, locks, and the append-only
  migration log. `default_pipeline` selects no root adapter; the invoking
  admission binding owns adapter selection, optionally accepting a named
  producer default. No parallel package format is permitted.
- `.pypeline`, authored `subflow`, and durable `.py` workflow readers are
  read-only exact-pin resolvers. They cannot create, admit, publish, or certify
  new work.
- All S2B surfaces remain `experimental`. Only S6 may promote them to `stable`.
- Completion templates are derived mechanically from canonical authored,
  component, graph-lock, and durable-boundary call-site identities. Admission
  instantiates runtime human, dynamic-child, rework, retry and reentry
  occurrences. Authors declare domain obligations only: they do not author
  obligation IDs, binding records, evidence authority, registry mappings, or
  terminal acceptance logic.
- Pure helpers declare no completion contract. The mechanically checkable
  durable-subject predicate and static lint reject any helper that hides a
  registered effect, suspension/reentry, checkpoint/attempt-ledger
  participation, Custody/authority requirement, durable child, or artifact
  crossing a durable boundary. Every durable subject gets exactly one generated
  template; omission or duplication rejects before admission.
- The authoring surface pins stable semantic obligation IDs and executable
  `(spec_hash, obligation_id)` identities. Deterministic tooling generates and
  pins immutable admission bindings and human-readable completion worksheets/
  reports; worksheets and reports are disposable, non-authoritative
  projections and are never hand-edited inputs.
- Step authoring packages are distinct from completion worksheets. The frozen
  Native response directory is an agent-edited, hash-bound candidate-input
  view; completion worksheets remain read-only disposable projections. Neither
  is authority, and acceptance consumes only harness-produced compiled/verdict
  records through the existing WBC/Custody transaction.
- `StepAuthoringSpec` is a new contract vocabulary colocated with Step-IO field
  declarations, but it contains only ownership annotations, render/view
  configuration and derivation bindings. Shape, type and validation reference
  Step-IO. Static conformance rejects duplicated schema semantics. The neutral
  materializer/compiler imports no Megaplan product package.
- The ownership algebra is exactly `model_required`, `model_hint`, `derived`,
  `protected`, and `model_proposal(merge=...)`. Proposal merges are named
  deterministic meet/join operations on declared safety lattices, proven
  monotone in the safety direction. Arbitrary merge callbacks reject.
- Ownership is orthogonal to Step-IO presence, nullability, defaults,
  cardinality and candidate-outcome applicability. The generated prompt,
  package and compiler share that one projection. Optional omission never opens
  repair; required applicable model content never receives an invented default.
- Response directories and child files are the only supported authoring package
  form, including simple records. Native's layout, nested-child convention,
  diagnostic codes and schema compatibility rules are frozen inputs; S2B may
  generalize their implementation but may not reopen their meaning.
- Derivations read only admitted typed input, parsed model fields and declared
  receipts. They cannot query the ledger or ambient sibling results. Body
  validation is structural only; semantic quality remains a completion or
  critique concern.

## Required work

1. Validate the Native Parity, S1, and S2A handoffs against every `PYPE-*`
   rule. Fail intake on any multi-export, re-export, library-only, `.py`
   durable-workflow, identity, graph-lock, or completion-template mismatch.
   Validate that each completion template is reproducible from the exact
   source/component/graph/call-site identities and that occurrence-specific
   identities appear only at admission/runtime instantiation.
   Run the inherited durable-subject lint and prove pure helpers require no
   template while every durable subject has exactly one. Mutate each durable
   behavior category into a helper and require a source-located rejection.
2. Productize one static parser/index/linker over the Native compiler. It
   identifies the canonical workflow, classifies private local steps/helpers,
   resolves canonical workflow imports and shared `.py` bindings, detects
   collisions/cycles/recursion, and never executes author source.
   Preserve ordinary Python/third-party import freedom inside shared step
   implementations while pinning selected environment/features/plugins in the
   graph lock or explicit bindings; reject import-time effects/mutable Arnold
   registration, ambient dependency choice, imported topology and undeclared
   effect bypass.
3. Complete source maps and transitive dependency slicing. Definition/call
   spans, logical identity, ownership, aliases, descriptor entries, and
   executable-closure helper slices must agree through lowering.
4. Implement logical and executable identity calculation exactly once. Pin the
   canonical semantic IR/serialization/hash algorithm version, include every
   closure category, exclude only the closed list, and fail unknown
   syntax/metadata rather than silently exclude it. Prove provenance-only moves,
   and route logical/executable changes through explicit compatibility,
   migration, new-run, or quarantine handling.
5. Productize package discovery and root selection: descriptor-owned optional
   `default_pipeline`, explicit eligible CLI/API selection, cross-package
   allowlisting, distribution ownership/delegation/fork checks, explicit
   invoking-admission root-adapter binding, one frozen logical key/digest, and
   agreement across source, descriptor, lock, manifest, admission, checkpoint,
   and source map.
   Productize the one typed immutable policy envelope and its exact manifest
   lowering: kind/schema, recursively immutable values, scope/attachment,
   provenance, precedence/override and digest. Apply the frozen component-versus-
   graph-lock digest rule and reject raw config-map authority, callables, open
   routes, ambient/mutable defaults and hidden overrides.
6. Productize the inherited mechanical converter. It splits every workflow
   into one `.pype`, classifies private/shared steps, replaces authored
   `subflow` with canonical imports/calls, updates descriptor and migration log
   atomically, and refuses ambiguous control, state, identity, or effects.
7. Implement transactional semantic refactors: extract child workflow, inline
   child workflow, and promote private step to shared `.py`. Each updates
   source, imports, descriptor, locks, provenance, and migration records
   atomically or leaves the workspace unchanged.
8. Expose the minimum scriptable core commands required by S3 and S4: check,
   compile, package-verify, convert, extract, inline, and promote. They use the
   production parser/lowerer and stable diagnostic catalog; polished CLI/editor
   presentation is S3.
   The scriptable core also generates/pins completion templates and admission
   bindings from declared intent plus domain obligations and renders worksheets
   without making any generated Markdown authoritative.
   Productize the Native response-directory materializer/compiler through those
   same Step-IO declarations. Snapshot submitted bytes before parsing; preserve
   provenance for every model proposal; compare protected values with the
   admitted binding; write compiled/verdict records outside the agent grant;
   echo normalized parsed values in `validation.json`; and expose stable repair
   diagnostics. The compiler admits a candidate only and never publishes it.
   Acceptance may not read the response directory.
   Bind resume to `(occurrence, attempt, evidence_window_hash, schema_version,
   custody_epoch, writable_snapshot_hash)` and fail closed on any mismatch.
   Emit one typed post-compile disposition consumed by S2A's promoted runtime:
   safe deterministic fill, candidate ready, same-live-session repair,
   replacement repair session, changed-evidence generation, or repeated-
   fingerprint fixer escalation. S2B chooses the disposition from declared
   schema/diagnostics but does not own provider sessions or create workflow
   status aliases.
9. Verify checkout, editable install, wheel, sdist, and pinned cloud
    resolution. Descriptor, resource, logical graph, digest, source map, and
    selected pipeline must agree; disagreement fails before authority.
10. Run the full contract corpus: small private-step workflow, reusable child,
    package of separate workflow files, Megaplan-scale topology, monolith and
    file-explosion counterexamples, hidden-handler topology, transitive hidden
    effects, private imports, physical moves, logical renames, and legacy pins.
11. Run contract-authored digest mutations across every included/excluded
    category, unknown syntax/metadata, transitive dependency, and algorithm
    version. Run distribution fork/delegation, legitimate same-key version
    evolution, conflicting-authority collision, default-pipeline/no-adapter,
    named producer adapter, and explicit invoking-adapter fixtures.
    Include ordinary shared-step dependency/environment/feature/plugin
    selection and every policy-envelope/digest-placement mutation.
12. Update conformance, traceability, and proof-map rows with executable S2B
    receipts. Extraction, second-consumer, and stable-publication rows remain
    explicitly open, and all S3 DX/tooling rows remain honestly red.

## Gates

### Semantic gate

- Exactly one canonical workflow is admitted from every `.pype`; all durable
  child topology crosses canonical `.pype` imports.
- Private local steps/helpers stay private and fold into the workflow digest;
  shared `.py` steps resolve without creating hidden topology.
- Source, lowered graph, descriptor, lock, manifest, admission, checkpoint, and
  source map agree on one logical graph and executable identity.
- Physical moves preserve identity only under the normative provenance-only
  conditions. Logical or canonical executable-closure changes never
  impersonate a pinned executable.
- Conflicting distribution authority rejects as collision, while legitimate
  version evolution under one authorized lineage resolves by exact version.
- Package default selection never supplies a root adapter; admission pins the
  invoker-selected adapter and its complete result map.
- Generated artifacts, descriptors, handlers, registries, tools, and migration
  records cannot add, erase, or reinterpret product routes.
- Generated completion templates and bindings agree exactly with the durable
  subject inventory and semantic obligation IDs. A missing contract, duplicate
  template, unstable/reused obligation ID, or hand-authored binding fails lint
  and admission, while a pure helper remains contract-free.
- Every durable model step has exactly one Step-IO-referencing authoring spec;
  deterministic/model-free durable steps and pure helpers have none. Duplicate
  shape validation, reverse Megaplan imports, non-monotone proposal merges,
  ambient derivations and response-directory acceptance reads reject.
- Required/optional/conditional behavior is reproducible from Step-IO, and the
  typed compiler disposition composes with S2A's one continuation lifecycle.
  No prompt/parser/editor-local requiredness table or session controller exists.
- Preview-only `.py` workflows and legacy artifacts cannot cross a durable or
  publication boundary.

### Proof gate

- All minimum blocking families in
  `docs/arnold/pype-authoring-contract.md` pass through checkout, editable
  install, wheel/sdist, and cloud where applicable.
- Negative fixtures cover zero/two workflows, private imports, `.py` durable
  topology, step-to-workflow/step-to-step, helper-to-effect, dynamic/star/
  conditional imports, recursion, cycles, descriptor disagreement, hidden I/O,
  and route laundering.
- Move/rename/extract/inline/private-promotion fixtures distinguish provenance
  from drift and prove pinned resume, explicit migration, and rejection.
- Digest mutations are derived from the normative closed inclusion/exclusion
  rules and detect omitted closure inputs or invented exclusions.
- Refactors are transactionally safe and preserve or deliberately migrate
  topology, state, outcomes, effects, idempotency, and identity.
- Static topology, core diagnostics, and source maps derive without source
  execution and retain exact `.pype` spans for S3 consumers.
- Evidence is content-addressed, commit/lock/schema-bound, and independently
  consumed. Narrative or hash-only receipts cannot pass.
- Omitted hints compile through neutral defaults plus the derived safety floor;
  fabricated derived facts and protected identity mutations reject through two
  independent controls. A valid-but-wrong nested parse is exposed in normalized
  validation output and fails its semantic fixture rather than silently passing.

### Adoption gate

- A product-neutral package can compile, link, convert, refactor, package, and
  resolve workflows using only documented experimental core surfaces and no
  Megaplan knowledge.
- Megaplan continues through the generic S2B surface with unchanged accepted
  topology and normalized behavior; S2B does not redo its migration.
- S3 can build the complete authoring experience without changing parser,
  discovery, identity, migration, package, refactor, or runtime rules.
- Nothing is labeled stable or third-party supported before S6.

## Artifacts and S3 handoff

Produce the parser/index/linker and SDK; package discovery/correspondence;
transactional refactors; minimum scriptable core commands; positive, negative,
digest, namespace, migration, and packaging corpora; identity/provenance and
legacy-retention receipts; install-form equivalence evidence; updated proof
rows; and a content-addressed S2B handoff naming the exact experimental
surfaces S3 must present and S4 must consume, including the StepAuthoringSpec
conformance API, response-directory compiler, ownership/merge catalog,
normalized-parse diagnostics and exact resume tuple, plus every open DX,
extraction, consumer, and certification row.

## Do not close this milestone if

- any normative artifact permits multi-workflow or library-only `.pype`, file
  workflow export/re-export tables, or admitted `.py` workflow topology;
- a private local definition can cross a file or receive independent identity;
- discovery executes source or relies on registration, declaration order,
  filename magic, or generated route data;
- paths become portable identity, or a pure move is treated as behavior drift;
- logical/canonical-closure drift can resume a pin without accepted migration;
- source, descriptor, lock, installed resource, manifest, checkpoint, or source
  map can disagree without failing before authority;
- the executable-closure digest relies on an open or subjective exclusion
  classifier, or namespace forks/version evolution are conflated;
- `default_pipeline` supplies an implicit root adapter;
- legacy syntax can create new work or historical evidence is rewritten;
- refactor/core tooling maintains alternate semantics;
- S2B duplicates Native migration, S2A runtime meaning, or S4 extraction;
- S3 would need to invent or reinterpret an authoring-format rule; or
- a completion worksheet is confused with an editable response package, a
  response package becomes authority, or Native's frozen authoring format is
  reopened; or
- the candidate is described as stable.
