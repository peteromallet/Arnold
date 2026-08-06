# S2 - Generic Authored Control Primitives Bound to Custody APIs

## Objective

Implement the product-neutral native constructs needed to express Megaplan
without semantic erasure, then bind their execution boundaries to the admitted
M11 Run Authority, Custody, and WBC APIs. Do not migrate Megaplan product phases
until a neutral reference pipeline proves the machinery.

Use `../GOLDEN_TRACE_CONTRACT.md` as the neutral pipeline's normalized ordered,
multiset, same-run trace oracle; never as an execution input.

## Required work

- Implement or finish typed decisions, typed terminal outcomes, bounded loops,
  dynamic runtime map/reducer, sequential fallback, per-item retry/fallback,
  deterministic child naming, human suspend/resume, checkpoint coordinates,
  and retry/timeout/model/fallback policy attached at call sites.
- Lower source constructs to a product-neutral runtime graph without importing
  Megaplan components, policies, handlers, route vocabulary, or canonical-path
  special cases.
- Implement S1's generated-manifest schema/version/hash evolution contract
  before changing serialized topology. Exercise old/new workers against old/new
  manifests; an unsupported schema/hash rejects before body/effect intent and
  continuation requires the declared compatibility/migration/quarantine path.
- Preserve runtime collection schema, max workers, reducer, child paths,
  cancellation/orphan behavior, and dynamic cardinality when width is unknown
  at compile time.
- Give every invocation and fanout child a deterministic semantic identity.
  Map it—without collapsing it—to a Run Authority subject attempt/fence, WBC
  execution attempt/version, and exact Custody target/lease epoch.
- Use M11's existing WBC reservation/start/terminal/retry/suspend/resume/cancel,
  effect-intent/outcome, checkpoint, outbox, and reconciliation APIs.
- Invoke the admitted action validator and lease/recovery interfaces at every
  authority-increasing dispatch, transition, retry, resume, effect, or terminal
  acceptance. Do not recreate grant, lease, or reconciliation logic.
- Every closed typed decision and terminal acceptance creates or links exactly
  one accepted Run Authority Decision under the current subject attempt/fence.
  The runtime transition consumes that exact decision ID/outcome/CAS sequence;
  no handler, status field, WBC receipt, or projection may independently persist
  or infer the accepted route.
- Define Native-specific semantic reentry and checkpoint coordinates and pass
  them through the settled custody lifecycle.
- Bind every checkpoint/reentry envelope to the authored program/topology
  digest, call-site-policy digest, exact WBC boundary-contract version,
  installed-artifact and dependency-lock digests, and applicable prompt/tool
  binding identities.
  Resume under drift must use the pinned original or take an explicit typed
  migration, new-attempt, or quarantine path—with new subject/WBC attempt and
  current custody epoch as applicable. Silent recompilation under changed
  program, policy, or contract is forbidden.
- Bind and validate the admitted program/topology digest, call-site-policy
  digest, exact WBC contract version, installed-artifact/dependency-lock
  digests, and applicable prompt/tool identities on **every**
  Native authority-increasing dispatch, typed decision, transition, terminal
  acceptance, and effect envelope before product body or effect intent—not only
  at checkpoint/reentry.
- Build a neutral reference pipeline that exercises crash, retry, dynamic
  fanout, cancellation, suspension, effect ambiguity, transfer/reclaim, and
  resume in enforce mode.
- Add a heterogeneous-host fixture: one stale installed worker in an otherwise
  current run is rejected/quarantined before body/effect intent; continuation
  requires an explicit accepted migration/new-attempt decision.
- Enforce S1's deterministic-Python contract with compile-time analysis and
  runtime guards where static proof is impossible. Canonicalize or reject
  unstable ordering. Preserve authored file/span and semantic path through
  lowering so compile and runtime failures report stable source-local
  diagnostics and supported rewrites.
- Ship an in-process authoring harness over the production compiler, lowerer,
  and transition semantics. It supports typed phase fakes, recorded LLM/tool/
  effect results, logical time and fault injection, fast-forwarded human
  decisions, crash/retry/resume simulation, and normalized trace inspection.
  Test stores implement the admitted RA/Custody/WBC contracts; the harness may
  not add routes, weaken closed outcomes/effects, or count as release proof.
- Implement S1's execution modes as explicit runner inputs and record fields.
  Make working-tree edit/repeat/fork the short path: automatically compute the
  behavior-relevant content digest; accept typed fixtures or immutable recorded
  boundary inputs; start fresh experiment/run/attempt lineage and isolated
  state/checkpoint/artifact/cache/effect-idempotency namespaces; retain source-
  run/boundary provenance; and default effects to fakes or explicitly sandbox-
  scoped targets. No experiment appends to the source run or reuses its
  production authority/effect identity.
- Provide an explicit non-durable `authoring_preview` runner for unsupported
  Python. It may return functional output, but cannot emit a durable checkpoint,
  RA/Custody/WBC/effect success, replay/resume token, comparison evidence or
  admission/certification receipt. Durable compiler errors link to this preview
  and the supported typed rewrite without silently selecting either.
- Define an LLM/tool call envelope binding prompt/template content and all
  referenced prompt assets, system/developer instructions, model/provider/
  profile and decoding/tool-choice parameters, tool input/output schema/version
  and effect class, token/cost/time/retry budgets with durable counters, cache/
  memoization policy and key, output schema, and durable result identity.
  Replay consumes a recorded result; logical retry creates a new declared
  attempt without resetting budget. Cache entries are fully content-addressed,
  schema-validated, provenance-journaled, non-authoritative, and run-scoped
  unless cross-run reuse is explicitly declared.
- Enforce checkpoint payload discipline using M11 facilities: inline only
  bounded schema-versioned control values; represent large/unbounded plans,
  prompts, transcripts/results, task outputs, reviews, and binaries as immutable
  artifact references. Missing/expired/digest-mismatched/schema-incompatible
  required artifacts enter typed repair/migration/quarantine, never silent
  recomputation.
- Derive durable state, checkpoint, artifact, effect-idempotency, and cache keys
  from run identity plus semantic path and invocation/loop/item/retry/reentry
  coordinates. Python object identity, display labels, list positions, and broad
  phase names are forbidden.
- Implement typed exits that address a named enclosing loop. Lowering validates
  ancestor targets and exhaustive parent handling; sentinels and exceptions
  cannot encode multi-level product routes.
- Canonicalize every decision input as a schema-qualified serializable value and
  journal its digest with the accepted RA decision. Reject or explicitly
  normalize host paths, datetimes, float edge cases, unordered containers, and
  mutable/custom objects.
- Freeze one fanout-admission digest over canonical item keys, context, policy,
  prompt/tool bindings, and artifact references. Every sibling consumes it.
  Reducers receive a canonical keyed multiset of typed results, never completion
  order; duplicate or missing keys fail.
- Permit topology to match only declared typed phase outcomes/errors. Unexpected
  exceptions enter one fixed infrastructure-failure channel and declared retry/
  recovery policy; open exception-class product branching is forbidden.
- Implement a typed `reconfigure(delta, target_cursor)` transition that accepts
  a schema-versioned delta, checkpoints it, derives new policy/executable and
  product-contract bindings, advances reentry/attempt identity as required, and
  resumes the named cursor. Ambient context or live flags cannot mutate routes.
- Freeze the declared durable-agentic boundary with typed ports, closed outer
  outcomes, named policy/budgets, one explicit WBC inner-call protocol, and an
  ordered durable model/tool/effect ledger. Implement it in this milestone only
  if S1 proves a current model-determined inner-call consumer; otherwise reject
  opaque inner loops with a stable diagnostic and experimental-Platformization
  recipe. For any admitted implementation, outer route hints are forbidden and
  every effectful inner call owns an exact Custody target plus its own durable
  WBC effect intent/outcome record; an enclosing phase receipt cannot stand in
  for them.
- Reject open-ended streams or opaque polling with a stable diagnostic and a
  deliberate-non-support recipe pointing to a future event-queue port. Do not
  add race/quorum without a demonstrated current Megaplan parity requirement.
- Bind the normalized product/Plan Contract digest to compile, checkpoint,
  reentry, decision, transition, terminal, and effect envelopes wherever it
  changes evidence obligations.
- Integrate S1's independent source oracle and raw-event audit comparator with
  the neutral production runtime. Check raw event IDs/multiplicity before the
  golden contract's approved normalization; production lowerer/runtime
  adapters and the verifier cannot share deduplication, event-elision or
  ordering logic.
- Implement product-neutral entry adapters/guards for `arnold.execution`,
  `NativeProgram`, and the retained runtime-envelope/legacy plane. Register all
  live writers in M11 and cross one complete enforce-mode validator. GO-0
  injects an unregistered writer and a plane-local bypass for every plane;
  adapters may serialize an already selected action but cannot route.
- Through two independent clients using the production Run Authority adapter,
  contend on every neutral decision-consumption and terminal/arbitration key in
  both release orders. Inject crashes immediately before and after the
  conditional write and require exactly one committed acceptance. Bind the
  receipt to the concrete adapter, canonical store/service and schema;
  application read/check/write, local mutexes and in-memory test stores do not
  count as GO-0 evidence.
- Put every Native durable ledger/registry introduced here inside the admitted
  rollback boundary or run its restore-then-replay proof now. S7 may consume
  this introduction receipt but cannot be the first time rollback safety is
  tested.
- Distinguish immutable execution-attempt terminals, retry generations under
  one semantic child, and the one aggregate child terminal consumed by the
  parent. Implement named-exit unwind terminals and explicit new-instance
  reentry; per-application migration decisions; default reconcile-before-cancel
  plus declared `cancelled_pending_reconciliation`; typed repair invalidation/
  redispatch classes; conditional agentic final-call reserves; and duplicate-
  human rejected-late evidence.

## Semantic gate

- Source-to-lowered-to-runtime set equality passes for every reference node,
  decision, loop, dynamic child, reducer, policy, and reentry edge.
- Dynamic fanout works for runtime-sized collections and collision tests prove
  identity is semantic, not list-position-only.
- The generic compiler/runtime has zero Megaplan carrier imports or
  report-specific route reconstruction.
- Decision occurrences, accepted Run Authority decisions, and consumed runtime
  transitions are one-to-one with matching outcomes.
- The neutral reference trace passes ordered/partial-order and multiset
  occurrence equality from one composed history.
- Raw event multiplicity and the independently normalized audit trace agree;
  duplicate events cannot be laundered by a shared normalizer.
- Production-adapter contention yields one accepted truth at every reference
  CAS site under both release orders and every injected crash edge.
- Replaying with identical recorded boundary results produces the same semantic,
  decision, and checkpoint trace. Representative illegal constructs report the
  authored location rather than only generated IR frames.
- Selected local-harness traces normalize equivalently to installed execution
  with the same recorded boundaries.
- Completion-order permutations yield identical keyed-reducer output and
  decision-input digest; sibling mutation after fanout admission cannot change
  another child's frozen binding.
- `NP-DX-001` repeats edited working-tree code from one recorded input under
  fresh isolated identities; `NP-DX-002` rejects silent changed-code resume;
  `NP-DX-003` preserves source provenance while assigning a sandbox fork new
  authority/history/effect identity; and `NP-DX-004` runs unsupported preview
  code while every durable/promotion consumer rejects it.

## Custody-adoption gate

- Missing/stale grant, coordinator fence, lease, or custody epoch blocks every
  authority-increasing reference action in enforce mode.
- WBC ambiguity or missing required boundary evidence may block or mark the
  boundary indeterminate, but no WBC receipt can grant dispatch or resume.
- Crash/retry/idempotency, terminal uniqueness, persistence failure,
  cross-host transfer/reclaim, and stale-epoch tests reuse the admitted M11
  facilities and pass without a parallel store or recovery service.
- Program/topology, call-site-policy, and WBC-version drift tests prove pinned
  resume or explicit migration/new-attempt/quarantine behavior.
- Installed-artifact and all other executable-digest mismatches reject a stale
  dispatched worker before product execution or effect intent.
- A crash after a durable LLM/tool result but before checkpoint does not repeat
  the call or reset budget; forged cache entries and changed prompt/tool schema
  fail admission.
- Oversized inline checkpoint values and invalid artifact references fail
  closed through the admitted payload/version facilities.
- Product-contract drift, non-canonical decision values, undeclared phase
  errors, ambient reconfiguration, and unjournaled agentic inner calls fail
  before they can select or execute a route.
- An effectful agentic inner call without an exact target, current custody and
  its own effect intent/outcome record fails before external action.
- Every unregistered or plane-local bypass fails before body/effect intent, and
  repair rejection cannot be reclassified by scheduler code.

## Do not close if

- Product-specific metadata is used to compensate for missing generic
  lowering/runtime semantics.
- A common `attempt_id` collapses the four identity domains.
- A projection, receipt, or historical success record can trigger a positive
  action.
- A typed outcome routes without exactly one accepted, matching Run Authority
  Decision consumed by the transition.
- A checkpoint resumes after program, policy, or WBC-version drift without an
  explicit accepted drift decision.
- A current grant/fence and lease/epoch allow a stale worker to dispatch,
  decide, transition, accept terminal, or emit effect intent.
- The local harness contains an alternate route table, replay performs a fresh
  completed LLM/tool call, or durable keys omit run/occurrence coordinates.
- A multi-level exit uses a sentinel/exception, a reducer observes completion
  order, siblings observe mutable shared bindings, or payload fields smuggle an
  undeclared route.
- A serialized/local-lock CAS fixture is presented as release proof, or a new
  durable record lacks an introduction-time restore owner and passing receipt.
- Edit/repeat requires a migration declaration merely to execute, an
  experiment overwrites admitted history, preview emits a durable claim, a
  fork reuses production effect/idempotency identity, or mode/severity changes
  implicitly between CLI/API/runtime layers.
