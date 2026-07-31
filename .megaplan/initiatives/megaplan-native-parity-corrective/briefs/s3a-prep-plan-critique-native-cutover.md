# S3A - Prep, Plan, and Critique Native Cutover

## Objective

Make prep, plan, and critique through the critique join load-bearing authored
topology, establish exclusive resume-plane selection before the first human
resume cut, and hand one closed typed result to the retained legacy gate.

Use `../validation/GOLDEN_TRACE_CONTRACT.md` as proof only. S3A owns GO-1A; it does not
claim that the complete front half is native.

## Mandatory GO-1A stop/go

GO-FORMAT and GO-0 must already be green. Before any S3A work, independently
rerun their validators against the accepted merged trees, locks, descriptors,
proof maps, compilers/runtime and installed artifacts. Reconsume the exact
C1/C2 manifests, S2R `completion-kernel-enablement-receipt.json`, current
divergence-ledger hash, accepted M11 coordinates, and scoped
topology/obligation hashes. Missing, red, stale, unresolved-blocking, unbound,
cross-incarnation or mismatched evidence blocks S3A; prose completion is not
sufficient. Once green, execute
prep -> clarification suspend/
resume -> plan -> dynamic critique from canonical source through lowering,
`build_pipeline()`, current M11 validation, relocated lowered-node WBC
producers, checkout and clean installed execution. Source mutation must change
the raw and normalized trace; old-carrier mutation must not.

The S3A `conformance_gate` runs before merge eligibility and rebinds GO-1A to
merge HEAD. Any registry-side authority switch or old-prefix fence/delete must
consume that exact post-merge receipt; a milestone state, copied verdict or
later S7 replay cannot authorize the cut. Failure leaves the old
prep/plan/critique producer authoritative,
validator-registered and not yet hard-fenced. A passing GO-1A cut is not rolled
back if later GO-1B fails.
The switch runs only as the chain's declared S3A transition. It emits one
immutable cutover receipt, and the separate post-transition GO-1A verifier must
accept the selected producer/fence state before S3A completes.

## Product scope

- prep research and typed clarification suspension/reentry;
- plan artifact boundaries and version metadata;
- bare critique skip, adaptive evaluator selection, bounded evaluator retry,
  dynamic lens fanout, per-item policy, sequential fallback and merge.

The current critique evaluator is a bounded selector/model call, not proof of a
model-determined durable inner tool loop. GO-0 freezes the generic agentic
safety contract and rejects opaque inner loops; this milestone must not invent
or claim a product consumer. Runtime implementation/adoption is explicitly
experimental and nonblocking unless the inventory discovers a real consumer,
and every effectful inner call then needs an exact Custody target and its own
WBC effect intent/outcome.

Pure computation may remain in phase bodies, but no body may own routes,
retry/cap/model policy, suspension, workflow mutation or child topology.

## Required work

- Make `workflows/workflow.pype` own the root topology and
  `workflows/plan_quality/critique.pype` own critique as its one canonical
  workflow invoked as a child. Shared steps/policies/types live in
  `workflows/plan_quality/*.py`; truly private critique steps may remain only in
  `critique.pype`. No second workflow or importable private member is allowed.
- Bind the admitted run to logical identity
  `(arnold-pipelines, workflow)` and its content-addressed canonical import/lock
  graph. Imported workflows use the same typed contract whether child-hosted or
  root-hosted; the package descriptor may supply an optional default, but no
  filename, declaration order, handler, generated manifest, or downstream CLI
  may reinterpret the frozen selection.
- Make `build_pipeline()` consume lowered structure without component
  selection, metadata overlay or route reconstruction.
- Land a canonical digest-bound `execution_plane_binding` in each admitted
  run/migration record and checkpoint. A pure selector reads it and the pinned
  executable; it cannot choose a semantic cursor or manufacture migration.
- Route every CLI/auto/native/legacy resume entry through the same selector and
  current action validator. Mutations prove neither plane can resume a scope
  bound to the other.
- Move WBC producers from handler names to canonical lowered occurrences and
  preserve exact admitted contract versions.
- Bind every action/effect/resume to the current RA fence and exact Custody
  target/epoch through M11.
- Use either storage-enforced `authority_class=comparison` or an immutable
  isolated comparison-artifact namespace with separate credentials and no RA
  grant, Custody/effect client, admitted writer, resume or promotion path.
- Generate the outgoing gate seam from a closed typed boundary. The accepted
  upstream decision already names the legacy gate entry; the seam only
  serializes the immutable payload/action envelope. Register it as a controlled
  writer when durable and mark it to expire in S3B.
- Exercise evaluator attempt-terminal -> accepted retry -> same semantic child
  -> one aggregate terminal. Reducers consume the aggregate exactly once.
- Bind the exact old/candidate writer cohort across all three execution planes
  to S2R's shared validator and one admitted decision/history writer.
- Bind every scoped consumption/arbitration site to S2R's certified production
  CAS operation and record the concrete adapter/store provenance. Any durable
  execution-plane, comparison or proof registry introduced by the cut has a
  passing restore-then-replay receipt before GO-1A can accept it.
- Mutate missing, forged and relabelled comparison admission tokens/provenance;
  none may enter admitted queries, resume, producer history or proof.
- Emit GO-1A raw-event/source-oracle/normalized receipts and the partial
  `NP-GT-002` critique-through-join evidence.
- Generate and consume completion bindings for every scoped durable occurrence
  using the S2R kernel. Legacy status, projections, handler results, and WBC
  receipts cannot satisfy an obligation or terminalize the prefix. Append any
  parity difference to C1's same stable-occurrence divergence ledger and bind
  the exact resulting hash in GO-1A.

## Semantic gate

- Prep, plan, critique selection/retry/fanout/fallback/merge are readable from
  canonical source and installed execution follows it.
- The selected workflow and every imported definition/import/call site survive
  the source map and lock. A pure physical move with unchanged logical/digest
  identity updates provenance only; rename, reselect, extraction, inline, or
  behavior drift requires an accepted migration/new-attempt/quarantine path.
- Dynamic child identity is stable under input reordering; fanout bindings are
  frozen and reducers are completion-order independent.
- Attempt terminals, retry generations and the aggregate child terminal retain
  distinct identities and cardinalities.
- Source changes alter the trace; old prefix and seam mutations cannot choose a
  product route.
- Comparison records are absent from admitted queries and proof.
- Scoped CAS and registry receipts bind the production adapter/store,
  incarnation/restore generation and raw-history high-water cursor.
- Scoped durable subjects, bindings, required evidence, verdicts, accepted
  decisions and terminal candidate outcomes have exact inventory equality.

## Custody-adoption gate

- Every scoped occurrence maps to distinct semantic, RA, WBC and Custody
  identities with generated joins.
- Unregistered plane, stale worker/fence/epoch, missing lease, duplicate effect
  and forged projection fail before body/effect intent.
- Cross-host clarification resumes only through the admitted execution-plane
  binding with current authority and custody.
- GO-1A passes in checkout and clean installed execution before old prefix
  carriers are fenced.

## Do not close if

- The old prefix remains a second producer after GO-1A.
- The execution-plane selector is an editable route/status table.
- The gate seam computes `next_step`, reads status to choose an entry or lacks
  an expiry owner.
- Comparison can acquire authority, write canonical history, resume or promote.
- A retry consumes a second aggregate child result, comparison provenance can
  be forged/relabelled, or a cutover record defers restore proof until S7.
