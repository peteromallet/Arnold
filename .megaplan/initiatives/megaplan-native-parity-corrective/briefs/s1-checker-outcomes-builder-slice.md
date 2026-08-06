# S1 - Custody Admission and Semantic-Preservation Gate

## Objective

Admit the completed `custody-control-plane` M11 substrate as an immutable,
content-addressed prerequisite and establish the fail-closed topology/identity
contract. The current 85-lowered-node to 14-component-step collapse must fail
before product migration begins.

Normative composition oracle:
`../GOLDEN_TRACE_CONTRACT.md`. It is the human-reviewed scenario/invariant
contract. An independent static source oracle checks Python topology without
calling the production lowerer, and an independently implemented audit
normalizer/verifier checks raw primary-store exports. It is proof only and can
never route or authorize runtime.

## Required work

- Verify the prerequisite completion manifest against the final custody chain,
  North Star, briefs, chain state, landed publication evidence, and proof hashes.
- Pin the exact source and installed-runtime revision, Run Authority/Custody/WBC
  contract and schema versions, enforcement cohort, controlled-writer registry,
  exact-version query registry, projection rebuild digest, captured replay,
  cross-host handoff, and zero-bypass baseline admitted from M11.
- Fail admission if any required guard is shadow-only/default-off or if evidence
  comes only from an intermediate M8/M9 receipt, status label, support manifest,
  or auto-publish commit.
- Run executable capability probes against the exact admitted M11 revision:
  three-plane external-writer registration/shared validation; opaque Native
  executable/product digest binding; restore-durable decision-consumption CAS;
  exact-target delivery-fanout scale; WBC ambiguity/reconciliation/checkpoint/
  query; repair rejection classification; and pinned cross-host resolution.
  Missing capability emits `blocked_on_m11_point_release` and stops for a new
  M11 prerequisite—never a local substitute or ordinary retry.
- Prove that every authoritative decision-consumption and terminal/arbitration
  CAS is a linearizable conditional operation enforced by the canonical
  production store/service. Capture the adapter/store/schema provenance needed
  for S2's two-client contention tests. Application read/check/write,
  process-local locks and in-memory CAS are explicit failing fixtures.
- Probe governed evolution of the admitted producer and exact-version query
  registries: versioned Native producer registration, comparison exclusion,
  atomic visibility and rollback behavior must work without silently changing
  the pinned M11 platform-contract identity.
- Inventory the admitted stores, APIs, queries, recovery services, projections,
  action validator, outbox/reconciliation, and generic conformance fixtures.
  Record them as reuse-only dependencies; create no fallback implementation.
- Define a normative row contract mapping:
  `source declaration -> lowered semantic node/child -> Run Authority subject
  attempt/fence -> WBC execution attempt/version -> Custody target/lease epoch
  -> downstream projection consumer`.
- Where a row produces or consumes a typed product decision or terminal
  acceptance, include the accepted Run Authority decision ID, outcome, and CAS
  sequence. Subject attempt/fence alone is insufficient.
- Keep those four identities distinct. Specify deterministic semantic paths,
  causal joins, cardinality, and which operations are authority-increasing.
- Build semantic checker/evidence scaffolding that rejects component-call
  skeletons, `handler_ref`, route bindings, policy route tables, handler route
  strings, manifest/runtime defaults, projected-native proof, and auto/CLI
  route ownership.
- Add blocking source-to-lowered set-equality tests, including retention of
  decisions, bounded loops, dynamic fanout/reducer policy, call-site policy,
  suspension/reentry, and child identity.
- Prove checkout and installed package fail on the current false-pass fixture.
- Define the final proof-map schema now: evidence must be semantic, executable,
  content-addressed, commit-bound, and generated; whole-file hashes alone never
  establish an `implemented` row.
- Define a mandatory per-sprint validation-receipt registry in
  `final-proof-map.json`. Every active milestone receipt binds the command and tool version,
  exit status, audited commit/tree, installed artifact, exact M11 admission-lock
  digest, semantic/identity/decision sets, runtime trace, and every blocking
  subcheck. It also binds canonical adapter/store provenance, store
  incarnation/restore generation and raw-history high-water cursor. Unknown or
  ad-hoc files are not proof, and restored/truncated proof history cannot reuse
  a receipt from another incarnation.
- Plan and specify the harness plumbing that passes `--proof-map` from the
  chain runner to the final validator, makes that validator consume every
  registered receipt, and binds the proof-map hash before the validator's own
  receipt is appended. This sprint defines and tests the contract; S7 lands and
  exercises the complete implementation.
- Add a chain-loader/schema invariant test: `prerequisite_policy: required`
  requires at least one explicit launch precondition, and
  `validation_policy: required` requires at least one explicit milestone
  validation. These policy fields are metadata, not enforcement by themselves.
- Retain the old self-declared/hash-only current-tree ledger/evidence bundle as
  a mandatory negative fixture. It must fail even after all stale path and hash
  records are refreshed.
- Freeze an executable machine-readable implementation of the full golden trace
  contract: occurrence coordinates, raw event identity/multiplicity, a
  contract-versioned volatile-field allowlist, normalized event vocabulary, explicit
  ordered/partial-order predicates, multiset occurrence/child equality, four
  identity joins, digest bindings, forbidden observations, and same-run proof.
  Set-only or separately manufactured row traces cannot satisfy it.
- Freeze the independent source-oracle, raw-export, audit-normalizer and
  verifier provenance contract. Production lowerer/runtime adapters may not
  generate expected traces or share deduplication, event-elision or ordering
  logic with the verifier. Prove the comparator against synthetic/raw mutation
  fixtures; S2 integrates it with production runtime at GO-0.
- Check in executable skeletons for all six families: `NP-GT-001`,
  `NP-GT-002`, `NP-GT-003`, `NP-GT-004`, `NP-GT-005`, and `NP-GT-006`
  (including its A/B/C variants), with mutation interfaces and expected red
  placeholders for later sprints.
- Freeze the authoring readability/edit-locality contract: one topology
  representation, one authored reusable delivery-cycle call, the small durable
  primitive set, generated mechanical identity/control-plane bindings, local
  call-site policy, closed exhaustive vocabularies, advisory structural
  complexity budget with reviewed exceptions, and at most two manual
  authoritative declarations per future extension.
- Freeze one machine-readable execution-mode matrix for `authoring_preview`,
  `durable_sandbox`, `comparison`, `admitted_production`, and `certification`.
  For every public entry and durable record it defines mode identity,
  provenance, permitted RA/Custody/WBC/checkpoint/effect surfaces, namespace
  rules, allowed claims and forbidden mode crossings. No mode is inferred and
  no existing history is promoted or relabelled.
- Freeze one enforcement-disposition registry. Every restriction is exactly
  `always_hard`, `automatic`, `production_admission_gate`,
  `stable_publication_gate`, `authoring_advisory`, or `non_durable_only`;
  diagnostics name the selected
  mode, violated claim, severity and supported preview/typed-rewrite path.
  Warning-to-error differences are declared, never accidental downgrades.
- Add executable skeletons `NP-DX-001` edited-step repeat, `NP-DX-002`
  changed-code resume rejection, `NP-DX-003` durable sandbox fork with source
  provenance/new history, and `NP-DX-004` unsupported-Python preview. Freeze
  mutations for production identity/effect/idempotency reuse, source-history
  append, preview/comparison promotion and diagnostic-severity drift.
- Freeze a versioned deterministic-Python allow/deny contract for topology and
  control code. At minimum classify wall time, random/UUID, environment/process
  state, unordered traversal, mutable globals, reflection/dynamic import/eval,
  unmanaged concurrency, filesystem/network/subprocess I/O, and exception-
  driven routing. Nondeterministic work must cross a typed durable phase/effect
  boundary that cannot own product routes.
- Freeze a diagnostic/source-map contract: stable error code, authored
  file/span and semantic path, violated rule, supported rewrite, and generated-
  node-to-source mapping.
- Add Plan Contract and generated manifest/executable-lock rows to the contract
  model. They describe product interfaces or derived runtime coordinates; they
  cannot route or satisfy authority. Define the complete action-envelope fields
  and corresponding negative fixtures.
- Freeze generated-manifest schema/version/hash evolution before S2 changes
  serialized topology. Define old/new worker versus old/new manifest behavior,
  supported-version advertisement, admission failure before body/effect intent,
  and explicit compatible-migration/quarantine dispositions.
- Classify checkpoint fields as size-bounded schema-versioned inline control
  values or immutable content-addressed artifact references with digest,
  type/schema, provenance, and retention/retrievability class.
- Inventory every executable, dependency lock, prompt/tool asset, and schema
  pinned by a nonterminal run. Define retention/resolution and garbage-
  collection eligibility: referenced versions remain available until terminal
  or accepted migration/quarantine disposition.
- Freeze named enclosing-loop typed exits and canonical schema-qualified
  decision values. Define normalization/rejection for host paths, datetimes,
  floats, unordered containers, and mutable/custom objects before decision
  digesting.
- Freeze that a named exit terminates/closes its target loop ledger, records
  one `superseded_by_named_exit` control terminal per intervening durable scope
  in innermost-to-outermost order, and reenters only as an explicit new loop
  instance with declared digest-bound carry fields.
- Freeze separate immutable attempt terminals, retry generations under one
  semantic child, and one aggregate child terminal consumed by the parent.
  Define default reconcile-before-cancel plus the optional declared
  `cancelled_pending_reconciliation` obligation terminal.
- Freeze per-run accepted migration applications, repair rejection categories,
  agentic named final-call reserves, and duplicate-human idempotent replay versus
  durable privacy-safe rejected-late evidence.
- Define canonical normalized product/Plan Contract digesting, explicitly
  classifying semantic `provides`/`assumes`/`pre_existing` fields versus excluded
  presentation fields. Bind semantic changes to drift disposition.
- Freeze fanout-admission bindings and canonical keyed-reducer contracts, closed
  typed phase error outcomes, typed reconfigure delta/reentry, and the durable
  agentic-phase inner-call protocol. Declare open-ended streams/polling
  unsupported with a future event-queue-port recipe. Race/quorum remains out of
  Stage 1 absent a proved current Megaplan parity requirement.
- Define a digest-bound comparison namespace with `non_authoritative`,
  `non_resumable`, `non_effect_capable`, and non-promotable provenance.
  Admitted queries, resume, decisions, projections, and proof exclude it.
- Require accepted M11 proof for backup/store-rollback-resistant RA fences and
  Custody epochs, canonical repair-request revalidation, and the all-plane
  controlled-writer/shared-validator inventory. Missing proof blocks launch;
  no Native substitute is allowed.
- Define the per-cutover union-of-old-and-candidate-writers receipt: all live
  action/effect paths registered behind one enforce-mode validator, exactly one
  admitted decision consumer/history writer, and no comparison writer.
- Define a durable-record ownership/restore matrix. Native decision-consumption
  joins, loop ledgers, comparison registries and proof registries are either in
  M11's restore boundary or require their own restore-then-replay proof; a
  Native side authority-consumption store is forbidden.
- Add extraction disposition to each normative row for S7's content-addressed
  Platformization handoff: core primitive, stable candidate, experimental
  candidate or Megaplan-specific.
- Make ergonomics measurable: route attribution forbidding payload smuggling;
  a diagnostic disposition registry with zero unmapped codes and a timed ten-
  task author simulation; and every-family local/installed normalized-trace
  equivalence with declared virtual-time/wall-latency budgets.

## Semantic gate

- The present implementation fails closed for the measured 85-to-14 collapse
  and dropped dynamic fanout.
- Editing canonical source changes the lowered semantic set; a builder overlay
  cannot silently reconstruct a second graph.
- No row can become implemented from path existence, declared status, hashes,
  receipts, projections, or prose without source-shape and behavior evidence.
- The proof-map schema rejects missing, extra, unknown, unconsumed, stale,
  non-executed, non-commit-bound, or red validation receipts.
- The golden oracle itself executes and rejects set-only evidence, wrong
  multiplicity/order/causality, and traces stitched from different runs.
- The deterministic and diagnostic contracts reject representative ambient
  nondeterminism and opaque route ownership at the authored source span.
- Plan Contract/generated-manifest mutations cannot add a semantic row or
  satisfy an action envelope.
- Product/Plan Contract evidence-affecting edits change the admitted digest;
  explicitly excluded presentation edits do not.
- Comparison history cannot enter admitted queries, and unregistered old or
  candidate execution planes fail the shared-validator inventory.
- Governed producer/query registry edits cannot bypass admission or comparison
  exclusion, and unsupported manifest/schema combinations fail before work.
- The execution-mode schema rejects missing/unknown/implicit modes and any
  promotion/relabel operation. Changed-code repeat is classified as a fresh
  experiment/fork; presenting it as the old admitted resume fails.
- Always-hard safety violations remain errors in every mode, while structural
  complexity and provisional-reuse guidance remain advisory during authoring
  and block only the declared later quality/certification claim.

## Custody-adoption gate

- The exact M11 completion manifest and accepted installed revision validate.
- The dependency inventory proves no duplicate grant/lease/WBC store, query
  facade, recovery loop, projection, promotion mechanism, or generic
  conformance harness was introduced.
- The identity matrix distinguishes semantic node/child, Run Authority subject
  attempt/fence, WBC execution attempt/version, and Custody target/lease epoch.
- WBC evidence is explicitly non-authoritative in code contracts and negative
  fixtures.

## Do not close if

- M11 is only nominally complete, enforcement remains shadow-only, or a stale
  prerequisite manifest passes.
- A WBC producer registered against a soon-to-be-deleted handler is treated as
  proof of native topology.
- The semantic checker validates labels or hashes without executing/mutating
  the claimed behavior.
- The old ledger passes after its hashes are refreshed, or the declared proof
  map is merely checked for existence rather than consumed.
- The golden trace fixture becomes a manually maintained route graph, or an
  author must handwrite authority/WBC/custody IDs and parallel binding tables.
- A pinned executable or required asset may be collected while referenced by a
  resumable nonterminal run, or checkpoint payload classification is absent.
- M11 lacks restore-resistant fence/epoch or repair-revalidation proof, a
  comparison record can be promoted/resumed, or a declared blocking ergonomics
  acceptance metric is demoted to advisory.
- Any executable M11 capability probe is missing/red, a Native side authority-
  consumption store is proposed, or production lowering manufactures its own
  expected golden trace.
- A CAS proof uses a local critical section, serialized harness or in-memory
  store, or a proof receipt omits production adapter/store provenance,
  incarnation or high-water cursor.
- The mode/disposition matrix is prose-only, a runner silently downgrades or
  promotes mode, local iteration requires production migration/certification,
  or preview/sandbox/comparison can reuse production authority, effect identity
  or admitted history.
