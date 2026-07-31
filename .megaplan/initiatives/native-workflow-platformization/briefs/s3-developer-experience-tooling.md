# S3 — Developer experience and tooling

## Objective

Make the rigorous `.pype` contract pleasant and legible without changing its
semantics. Complete the generic CLI, editor, navigation, formatting, linting,
topology, preview/test, diagnostics, and unfamiliar-author experience over the
exact S2B authoring core and S2A runtime. Deliver the low-friction authoring
loop S4 extraction and eventual third-party use require.

This is a real product/tooling milestone, not a polish appendix. It must not
create an editor-only parser, a second mode/severity matrix, handwritten
generated metadata, or a local runtime that diverges from installed execution.

## Normative contract and inputs

`docs/arnold/pype-authoring-contract.md` is the sole format authority.
[`../decisions/PLATFORM_CONTRACT.md`](../decisions/PLATFORM_CONTRACT.md) is normative for runtime,
proof, execution modes, store/capability isolation, and milestone ownership.
`docs/arnold/workflow-execution-mode-dispositions.yaml` is the only machine mode/disposition/
store registry; all diagnostics and UI severity are derived from it.

Consume:

- the hashed Native Parity and S1 handoffs and cumulative diagnostic/DX corpus;
- S2A's promoted-in-place runtime, faithful local kit, mode/store enforcement,
  lifecycle events, source-map preservation, and proof interfaces; and
- S2B's parser/linker, conservative executable-closure digest, package/
  distribution identity, source correspondence, converter, transactional
  refactors, completion-template derivation, stable diagnostic codes, and
  install-equivalence receipts; and
- the exact Native completion schemas/decoder, current divergence-ledger hash,
  and Custody bounded-query API plus 57k benchmark receipt, all retained
  through the S2A handoff.

Missing semantic behavior blocks S3 and is fixed by S2A/S2B. S3 never patches
around it in an editor adapter or CLI translation layer.

## Locked decisions

- Every command and editor feature invokes the production S2B parser/linker,
  descriptor/lock owner, refactor transactions, diagnostic catalog, and S2A
  runtime/local kit.
- The machine registry is the sole source of mode, disposition, store access,
  and logical isolation. Prose tables, help text, editor severities, and CLI
  exit codes are generated views.
- Diagnostics name stable rule code, authored definition/import/call span,
  logical/executable identity, failed claim, mode/disposition, and a supported
  rewrite. They never silently downgrade a requested durable claim.
- Preview/test commands default to isolated capabilities and namespaces.
  Content-addressed artifact access follows the registry matrix; no “safe
  because immutable” shortcut grants production-store access.
- Formatter and editor adapters preserve the original `.pype` path/span and
  cannot change the canonical semantic envelope or contract digest.
- Authors never hand-edit generated manifests, locks, migration records,
  identity registries, source maps, or route tables.
- All surfaces remain experimental. S6 alone may stabilize them.
- Completion lint, diagnostics, inspection and query tools are views over the
  authoritative kernel and Custody projection. Generated canonical-machine
  exports are reproducible projections of canonical kernel records; they are
  not a second class of canonical record. Markdown, worksheets and all other
  human views are disposable.
  Deleting, rebuilding, editing or forging any view cannot change admission,
  evaluation, acceptance, evidence, ledger truth or query authority.

## Required work

1. Complete generic CLI commands for check, compile, inspect, explain,
   graph/topology, preview, test, package verify, convert, extract, inline,
   promote-private-step, identity/lineage inspection, causal-history inspection,
   agent-session/model/tool/effect/cost/log navigation, and migration planning.
   Commands compose the S2B core and S2A event/index contract rather than
   duplicate either.
   Completion inspection must show exact spec/binding/verdict/obligation
   identities, evidence scope, proof mode, waiver taint, decoder version,
   acceptance receipt and current divergence-ledger hash.
   Generated machine and Markdown completion views must also expose UTC
   start/end timestamps and duration, attempt/generation history, every failure
   and rework transition, verifier identity, waiver or justified-non-action
   rationale plus its independent quality disposition, and final resolution.
   Missing timing, failure, justification-quality, or resolution fields fail
   the projection acceptance fixture; all views remain disposable and
   non-authoritative.
   Run the exact inherited deletion fixture: accept canonically, delete every
   completion/status/Markdown projection, restart, rebuild and prove identical
   accepted decision, binding, verdict and effect identity with no new action.
   Forged and corrupt projections must also remain authority-inert.
2. Ship formatting and linting for the restricted Python profile. Format-twice
   is stable; formatting, comments, and source-location changes preserve the
   pinned executable digest; every other canonical-envelope change is visible.
3. Ship syntax highlighting, canonical-workflow/private-member distinction,
   import navigation, go-to-definition, find-importers, identity/digest hover,
   source-mapped traceback, and editor setup for `.pype`.
4. Generate a static topology view without executing author source. It shows
   canonical workflows, child calls, steps, finite named route discriminants,
   call-site policy, effects, suspension, source spans, package/distribution
   identity, and root-adapter binding. Payload is never displayed as an
   invocation target.
5. Productize one-command preview with fake/ephemeral-only effects and no
   durable history, plus separately explicit faithful durable-sandbox tests
   with isolated effects, virtual time, recorded inputs/outcomes, eligible-
   checkpoint fork, side-by-side comparison, and exact per-occurrence logs.
   Each command prints the mode, claim boundary, fresh lineage/namespaces,
   store capabilities, and why its output cannot promote.
   History inspection supports both occurrence/attempt → agent/log artifacts
   and agent/model/tool/effect/log record → owning occurrence/source plus
   decision/terminal when present, without importing product code or treating
   a rebuildable index as authority.
6. Present transactional extract/inline/promote operations as previewable plans
   and atomic apply operations. On failure, source, imports, descriptor, lock,
   provenance, and migration log remain unchanged.
7. Generate CLI/editor severity, help, and rewrite text from the single machine
   registry. Add a drift check that fails if any consumer ships a duplicate or
   contradictory rule/mode/store table.
   Generate completion-outcome views separately from the enforcement registry
   and its total version-bound mapping; never present or serialize them as one
   enum.
8. Exercise the Custody bounded/cursor query surface at the inherited 57k scale
   for completion inspection. A full-journal scan, Platform-owned checkpoint/
   snapshot, or alternate projection is a gate failure.
9. Run the complete inherited diagnostic corpus, including exact-one,
   private-member import, dynamic/cyclic/recursive topology, leaf-law,
   transitive hidden effect, route smuggling, finite-discriminant, digest
   inclusion/exclusion, distribution fork/collision/version evolution,
   root-adapter, legacy, and mode/store negatives.
10. Run pinned unfamiliar-author tasks for: create a small workflow with private
   steps; import a child workflow; promote a step; extract and inline a child;
   move a file; rename/migrate a workflow; select a non-default pipeline and
   bind a root adapter; diagnose hidden I/O; preview/fork edited code; and
   package/inspect from a clean wheel; and find the transcript, tool calls,
   effects and cost for one selected step attempt, then navigate one agent log
    back to its workflow source and causal consumer.
    Include one task where the author declares only durable intent and domain
    obligations, tooling generates/pins the binding and worksheet, an omitted
    durable obligation fails lint/admission, and an ordinary pure helper needs
    no completion declaration.
11. Measure no-network p50/p95 for format, check, compile, navigation, topology,
    preview startup, and each transactional refactor in the frozen benchmark
    environment. Compare to the inherited baseline; any baseline change is
    explicit and never reset to hide regression.
12. Prove checkout, editable, wheel/sdist, and pinned cloud tools resolve the
    same graph, digest, source spans, diagnostics, selected pipeline, adapter,
    and normalized local/installed traces.
13. Update conformance, traceability, and proof rows with executable S3
    evidence. Extraction, second-consumer, and stability rows remain red.

## Gates

### Semantic gate

- CLI, editor, formatter, topology, preview, and tests all consume the one S2B
  semantic core and S2A lifecycle. Mutating a presentation adapter cannot alter
  topology, identity, routing, authority, or effect meaning.
- Mode/disposition/store behavior is identical to the machine registry, and
  no production namespace or mutation capability is reachable from default
  preview, sandbox, comparison, or certification tooling.
- Named finite discriminants remain visibly distinct from payload, and every
  route divergence is attributable to one source-bound variant.
- Formatting and source moves have only the exact closed provenance effect;
  semantic changes produce the pinned digest/migration disposition.

### Proof gate

- Every inherited and new diagnostic fixture reports stable codes, precise
  `.pype` spans, claim/disposition, and a supported rewrite through CLI and
  editor adapters.
- Timed unfamiliar authors complete every named task without editing generated
  data or consulting Megaplan internals; p50/p95 budgets pass in the pinned
  environment.
- Checkout/editable/wheel/sdist/cloud and local/installed equivalence remains
  green. The editor/CLI cannot manufacture a green result when the core rejects.
- Registry drift, production-store reachability, implicit adapter selection,
  full-payload discriminants, and non-atomic refactor failure mutations reject.
- Projection deletion/rebuild/forgery cannot change a canonical completion
  record, accepted decision, evidence identity, effect identity or next action.

### Adoption gate

- S4 can extract, bind, inspect, locally exercise, package, and diagnose
  reusable patterns using documented product-neutral surfaces only.
- The rigorous one-workflow-per-file structure is demonstrably low-friction at
  small and Megaplan-scale examples, including monolith and file-explosion
  counterexamples.
- Nothing is labeled stable or third-party certified before S6.

## Artifacts and S4 handoff

Produce the generic CLI/editor/formatter/linter/topology/preview/test surfaces;
generated registry views; complete diagnostic and author-task corpus; benchmark
environment and p50/p95 report; install-form/source-map/local-trace receipts;
tooling docs/examples; updated proof rows; and a content-addressed S3 handoff
pinning the exact S2B/S2A versions S4 must use.

## Do not close this milestone if

- any tool maintains a second parser, identity rule, mode/disposition/store
  table, runtime lifecycle, or route interpretation;
- preview/sandbox/comparison defaults can reach production stores, keys,
  namespaces, effects, authority, or admitted evidence;
- a formatter/editor/refactor silently changes the canonical executable closure
  or loses original `.pype` spans;
- authors must edit generated manifests, locks, migration records, source maps,
  route tables, or identity registries;
- a timed task or pinned p50/p95 threshold is red, reset, or omitted;
- S4 must invent authoring or local-tool behavior; or
- experimental tooling is described as stable.

## Non-goals

- Changing the `.pype` format, lifecycle, identity/digest, package, migration,
  execution-mode, or store-access contract.
- Extracting Megaplan patterns, building the unrelated consumer, or publishing
  stable components.
- Supporting arbitrary durable Python, open streams, opaque polling loops, or a
  hidden callback escape hatch.
