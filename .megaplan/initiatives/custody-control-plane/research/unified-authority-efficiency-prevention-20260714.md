---
type: research
date: 2026-07-14
status: canonical-planning-input
source_snapshot: '2026-07-14T10:35:52+00:00'
current_run_snapshot: '2026-07-17T13:42:46.341461+00:00'
current_run: custody-control-plane-20260714
current_plan: m6-exact-contract-and-20260716-1303
---

# Unified Run Authority and Megaplan efficiency prevention synthesis

## Decision summary

The two investigated epics exposed one shared orchestration failure family with
two ownership lanes. Split identity, mutable attempts, stale repair attachment,
independent status projections, and scan-driven recovery are correctness and
custody failures. They belong to the existing Run Authority, WBC, TransitionWriter,
repair-custody, and projection contracts. Serial DAG admission, oversized tasks,
model-backed deterministic checks, invalid-ref retry storms, provider/compaction
budgets, and executor rework loops are adjacent Megaplan efficiency policy. They
must be fixed in this same prevention epic, but must not be generalized into Run
Authority.

The Strategy Roadmap's M4 first execute is the controlling counterexample to
calling all duration waste: 2h03m17s was 99.6% enclosed by 15 worker calls and
produced 8,327 additions. Its review found real defects. Transaction Spine's
stopped attempts also produced useful implementation and repairs. The prevention
target is avoidable queue, replay, retry, compaction, validation, detection, and
projection overhead, reported separately from productive implementation and
necessary proof/review.

## Evidence reconciled

- Combined synthesis:
  `.megaplan/plans/resident-subagents/subagent-20260714-101421-463e5e9c/result.md`.
- Transaction Spine investigation:
  `.megaplan/plans/resident-subagents/subagent-20260714-101356-39ea719f/result.md`.
- Strategy Roadmap contributor ID:
  `subagent-20260714-101356-fc5f6cae`. Its requested checkout-local `result.md`
  is absent at synthesis time. The completed contributor was consumed into the
  immutable combined report and the consolidated report at
  `.megaplan/tx-spine-systemic-fix/.megaplan/initiatives/megaplan-maintenance/handoff/active-epics-latency-synthesis-20260714.md`;
  this plan uses that content and does not fabricate or backfill the missing file.
- Run Authority North Star, architecture decision, controlling main plan, M1-M3
  briefs, proof map, completion manifest, dependency proof, and all three current
  `completion_verdict.json` files. The manifest says `done`, but each current
  verdict has `accepted: false`; this is why M5 remains a hard prerequisite.
- Current Custody North Star, single-authority decision, lineage/gap audit,
  migration matrix, M5-M11 plus M6A briefs, sequencing handoff, and prep note.
- WBC North Star, execution-attempt-ledger decision, corrective ownership
  decision, TransitionWriter/phase/repair/cloud boundary briefs, and launch
  ownership matrix.
- Read-only WBC revision audit: completed candidate `cbe69337…`, landed by
  audited consolidation merge `24afce00…`. The candidate
  ledger is schema-only, and its 35-row producer inventory is 5 auto-matched, 8
  manual-emission, 13 declared-only, and 9 unknown. These are planning inputs,
  not universal-adoption proof; M6 still binds exact landed and runtime vectors.
- Maintenance North Star, authority-ledger/loop decision, coherent authority,
  independent verification, six-hour product, daily efficiency auditor, and
  managed repair/L3 handoffs.

The isolated projection commits `3221870c965f086691610321b41b126f4aff3266`
and `0a31d539caae5edb1623266d0150ab8a7d272c28` are candidate implementation
evidence only. They are not merged, installed, deployed, or accepted by this
planning update.

## Current-run implementation answer and evidence boundary

At the bounded read-only observation generated
`2026-07-17T13:42:46.341461Z`, the current Custody run had completed the first
two entries of its ten-entry execution binding and was positioned at M6:

- raw chain state
  `/workspace/custody-control-plane-20260714/Arnold/.megaplan/plans/.chains/chain-1e998199f544.json`
  (observed mtime `2026-07-17T13:42:26.080658899Z`) records
  `current_milestone_index: 2`, current plan
  `m6-exact-contract-and-20260716-1303`, two `completed` entries (M5 and M5A),
  `last_state: blocked`, `sync_state: clean`, and branch/PR head
  `5ece35918c2f0fcbdebb744c5060b4236657f43a`;
- raw plan state
  `/workspace/custody-control-plane-20260714/Arnold/.megaplan/plans/m6-exact-contract-and-20260716-1303/state.json`
  records `current_state: gated`, `iteration: 5`, a passing `PROCEED` gate, and
  `resume_cursor.phase: finalize`; the read-only `introspect` payload at the
  snapshot time reported `display_state: gated`, `execution_state: inactive`,
  no in-flight LLM call, `active_phase.liveness: stalled` because the last event
  was 592 seconds old, and `block_details.is_blocked: true`;
- the same plan's `events.ndjson` last observed event was sequence 2582 at
  `2026-07-17T13:32:54.255746Z`, a `drift_detected` event where the canonical
  repair dispatch intent was `broken_superfixer` with canonical state
  `UNKNOWN`, while the legacy/actual result was `queue_only`/`no_action`;
- the chain's immutable execution binding names intended initiative revision
  `0f28081c0fed61faaa8f1a2b1ac5861de11dfddf`, the exact ten-milestone
  sequence, and content hashes for M6 through M11. The M6 plan's canonical
  source binding independently pins its brief to Git revision
  `5ece35918c2f0fcbdebb744c5060b4236657f43a`, blob
  `9717a811eb1d4cb9cae877a00d1912220671b419`, and file SHA-256
  `3fea24d7120fb6dd97a0a876caff200bd9d2847d6fcae37dcb69a63b1b8ec66e`.

The chain-level `blocked` label, plan-level `gated` label, and later repair
drift event are separate evidence dimensions; none is normalized into a claim
that M6 executed or that any later control is runtime-active. This report is a
documentation update only. It does not finalize, resume, replan, restart,
deploy, or otherwise mutate that run.

## Durable North Star

For every supported run, one exact-version Run Authority reducer decides which
attempts and claims are accepted. WBC preserves the immutable attempt/boundary/
effect facts; TransitionWriter and fenced repair custody serialize lifecycle
mutation and recovery; all plan, chain, cloud, repair, resident, and operator
views are rebuildable projections. Eligible blocked occurrences reach accepted
repair or typed escalation with p95 below five minutes, with a six-hour missed-
event backstop. Megaplan admits only feasible DAGs/tasks and bounds retries,
provider waits, compaction, rework, and validation cost. A joined ledger proves
productive versus replayed work, tokens, cost, and time. No legacy authority
bypass survives completion.

## Explicit ownership matrix

| Owner | Owns | Must not own |
|---|---|---|
| Run Authority | capability/dispatch grants; coordinator and subject attempts; accepted/rejected/quarantined/superseded decisions; fences; dependency acceptance; the pure authoritative reducer and authority-increasing views | lifecycle writes, repair queue policy, WBC event storage, DAG design, model routing, executor budgets, status rendering, auditing |
| TransitionWriter and repair custody | plan/chain lifecycle CAS; occurrence request/claim/lease/fence; repair dispatch; terminalization; recurrence/reopen; independent verification scheduling | accepting task claims, inventing attempt identity, self-verifying, direct sidecar authority, analytics policy |
| WBC | exact-version boundary contracts; transactional immutable execution-attempt and external-effect store/API; receipts/evidence and payload/reference governance; semantic findings; supported-runtime conformance | grants/acceptance, lifecycle mutation, repair custody, aggregate status, planner/executor policy |
| Megaplan Maintenance | coherent observation envelopes; incident/maintenance analytical events; six-hour reconciliation/backstop; daily read-only efficiency analysis; deterministic findings and ticket proposals | a second authority ledger, direct run mutation, active-chain redesign, model/budget changes, self-verified repair |
| Planner/compiler/finalizer | semantic dependency reasons; routing groups; critical-path/parallelism and turn-budget feasibility; complexity splitting; validation-job compilation; task/rework ceilings in the finalized contract | authority acceptance, repair custody, provider effects, projection truth |
| Executor/launcher/runtime packaging | bounded invalid-ref/startup validation; worker/import/model isolation; timeout/failover/compaction/rework circuits; deterministic harness jobs; verify-only repair-receipt adoption | silently widening scope/budget, rewriting attempts, blind retry, accepting stale repair work |
| Observability/projection/auditor | append-efficient projection builders; latency/work ledger; pure status/introspection; exact-evidence deterministic reasons; SLO and drift reporting | refreshing liveness on read, resolving authority independently, performing repair, combining productive and replayed work |

Run Authority is therefore the correctness kernel, not the universal owner. The
joined contract has one authority reducer, one WBC attempt/effect history, and
one lifecycle/repair writer. “One” does not mean a god object or a new combined
ledger created by Custody.

## Finding-to-prevention traceability

Every item below names the root cause, canonical owner, control, milestone,
acceptance proof, rollout gate, rollback/fail-closed behavior, and legacy
deletion gate.

### F01 — stale repair identity attached T7 evidence to T12

- Root cause: repair identity was request/session oriented and was not
  revalidated against the live attempt and normalized failure signature.
- Owner/control: Run Authority defines attempt/fence identity; repair custody
  dispatches only an exact tuple `(environment, session, chain, plan_revision,
  phase, task, attempt, normalized_failure_kind, blocker_or_phase_result_hash,
  fence)` and supersedes mismatches.
- Milestone/proof: M7 freezes identity and quarantine semantics; M10 enforces
  dispatch and terminal closure. Captured T7/T12 replay proves cross-binding is
  impossible and every request/claim/attempt/decision/index ends terminal.
- Rollout gate: shadow mismatch telemetry must have exact evidence IDs before a
  repair/worker canary. p95 event-to-accepted-repair is measured in the canary.
- Fail closed/retirement: mismatch becomes superseded/quarantined and launches
  nothing. Delete basename, implicit-latest, and request-only selectors only
  after zero runtime callers and mixed-version replay proof in M11.

### F02 — scan-driven recovery added 1h38m44s

- Root cause: blocked/process-exit state depended on hourly discovery.
- Owner/control: WBC emits durable block/exit events; repair custody consumes a
  deduplicated trigger; Run Authority validates current identity/fence. Hourly
  scan and six-hour Maintenance pass reconcile missed events only.
- Milestone/proof: M6A/M8 make block/exit writes durable; M10 runs deterministic
  lost/duplicate/out-of-order trigger
  fixtures and a real eligible blocked-run prove p95 under five minutes plus
  missed-event recovery by the six-hour backstop.
- Rollout gate: action-off shadow SLO, then one allowlisted repair/worker canary.
- Fail closed/retirement: delivery ambiguity stays pending and scan-recoverable;
  no duplicate launch. Retire scan-as-primary only after the missed-event corpus
  and canary both pass.

### F03 — repair results were not adoptable and work replayed

- Root cause: repair receipts lacked current grant/task/revision/tree/test/fence
  proof and could not become accepted checkpoints.
- Owner/control: WBC stores immutable receipt evidence; Run Authority validates
  and accepts/quarantines; executor offers a verify-only adoption path.
- Milestone/proof: M6A/M8 make WBC receipt/attempt evidence durable; M7 joins
  custody identity; M8A implements
  verify-only adoption. Valid T7/T12 fixtures skip full replay; any altered
  contract, tree, test set, or fence rejects adoption and executes normally.
- Rollout gate: shadow comparison, captured replay, executor canary.
- Fail closed/retirement: no receipt means no adoption, never implicit trust.
  Remove repair-specific replay shortcuts after zero callers and replay parity.

### F04 — mutable aliases overwrote attempt history

- Root cause: `execution`, batch, and review aliases acted as both current view
  and historical record.
- Owner/control: WBC owns append-only attempt-scoped artifacts/events; Run
  Authority reducer selects accepted attempt; aliases become projections.
- Milestone/proof: M6A supplies the store, M8 adopts review/rework producers,
  and M10 proves replay. Two review/rework cycles preserve byte-identical attempt
  1, monotonic ordinals, causal parents, and deterministic current projection.
- Rollout gate: dual-write shadow and deterministic replay before enforcement.
- Fail closed/retirement: append failure is `persistence_failed`/`indeterminate`;
  no success. Delete mutable historical writes after old-reader compatibility
  expiry and zero-writer scan in M11.

### F05 — plan, chain, cloud, repair, and introspection disagreed

- Root cause: independent precedence rules reduced mutable snapshots and
  sidecars, allowing `repairing`, `executing`, and `finalized` simultaneously.
- Owner/control: one pure attempt-aware Run Authority reducer; custody supplies
  coherent evidence; every other view projects reducer cursor/hash and keeps
  execution, liveness, custody, publication, delivery, and integrity separate.
- Milestone/proof: M9. Captured review-rework input renders `executing attempt 2`
  everywhere with 100% cursor/hash agreement; torn evidence becomes unknown.
- Rollout gate: deterministic replay, action-off shadow, then idle projection
  canary before any control consumer promotion.
- Fail closed/retirement: disagreement emits drift and blocks action. Delete
  local status classifiers and raw fallback control reads only after M11 zero-
  reader and forced-rollback proof.

### F06 — heartbeat projection rewrote a growing journal non-atomically

- Root cause: every heartbeat performed a quadratic full-file compatibility
  rewrite and exposed partial destinations to readers.
- Owner/control: observability owns cursor-checked O(event-size) append and
  atomic rebuild; authority remains upstream and projections disposable.
- Milestone/proof: M7 lands/proves the writer boundary; M9 proves complete
  rebuild. At least 10,000 heartbeats yield sequences 0..9999, one rebuild,
  monotonic valid concurrent reads, zero false stalls, and recorded bytes/time.
- Rollout gate: review candidate commits, deterministic stress, idle runtime
  canary, then controlled deployment with installed SHA provenance.
- Fail closed/retirement: cursor mismatch rebuilds atomically while the prior
  complete file remains readable. Remove full-journal rewrite only after
  rollback and historical-reader compatibility proof.

### F07 — fully serial DAGs were admitted without feasibility proof

- Root cause: `depends_on` mixed semantic prerequisites with routing/order and
  finalization did not report critical path or usable parallelism.
- Owner/control: planner/compiler requires a reason per dependency, separates
  `routing_group`, calculates critical path/width/seriality/turn demand, and
  rejects unexplained 100% serialization for eight or more tasks.
- Milestone/proof: M8A. Replaying both finalized plans flags the observed serial
  chains and produces safe independent waves without changing semantics.
- Rollout gate: report-only compiler diagnostics, captured replay, then new-plan
  canary; existing plans are never silently rewritten.
- Fail closed/retirement: infeasible plan returns a typed planning blocker
  requiring split/replan or explicit authorized exception. Delete implicit
  dependency/order coupling after corpus parity and zero emitters.

### F08 — high-complexity tasks exhausted fixed worker budgets

- Root cause: complexity 7–9 tasks bundled implementation and proof under one
  uniform 90-iteration ceiling.
- Owner/control: planner/compiler splits implementation from proof at complexity
  >=7 or records an explicit evidence-backed larger budget; executor enforces
  the compiled ceiling and checkpoint boundaries.
- Milestone/proof: M8A. T7/T12 and later complexity-8/9 fixtures either split or
  fail admission; no partial implementation is discarded when proof budget ends.
- Rollout gate: shadow feasibility, replay, then executor canary.
- Fail closed/retirement: budget exhaustion opens a typed blocker/checkpoint,
  never blind retry. Remove uniform-budget fallback after zero callers.

### F09 — deterministic validation consumed model calls

- Root cause: no-file checks were compiled as ordinary model tasks.
- Owner/control: planner/compiler emits harness validation jobs; executor runs
  them outside model calls with captured command, environment, output, and hash.
- Milestone/proof: M8A. Strategy T10/T12/T15 equivalents make zero model calls
  and reproduce the same pass/fail semantics.
- Rollout gate: shadow task classification, captured replay, executor canary.
- Fail closed/retirement: ambiguous or mutating checks remain explicit model or
  human tasks; they are not guessed mechanical. Delete validation-only model
  routing after zero classified callers and parity.

### F10 — invalid source refs retried for 2h09m

- Root cause: launcher did not validate/suggest once and lacked a startup retry
  circuit tied to source/runtime provenance.
- Owner/control: launcher/runtime packaging validates the ref once, suggests a
  valid audited ref, caps attempts, and proves detached source/install/runtime
  SHA equality before start.
- Milestone/proof: M8A. Invalid-ref and dirty/divergent-checkout fixtures stop
  within the configured bounded attempts and never create repeated chain starts.
- Rollout gate: fixture and dry-run preflight before any controlled deployment.
- Fail closed/retirement: unresolved or divergent ref is a launch blocker. Remove
  permissive repeated-start paths after installed-runtime provenance canary.

### F11 — provider timeout, invalid summary model, import leakage, and compaction churn

- Root cause: worker configuration/import boundaries were mutable, repeated
  invalid model requests were not terminal, and provider/compaction budgets were
  not joined to one attempt circuit.
- Owner/control: executor/launcher resolves model before dispatch, isolates
  target/runtime imports, permits at most one repeated 300-second timeout before
  failover/escalation, and caps compaction at one per turn unless authorized.
- Milestone/proof: M8A. Empty/invalid model, divergent checkout, import leakage,
  repeated timeout, and compaction fixtures terminate within bounds with exact
  reasons and no duplicate effect.
- Rollout gate: shadow counters and worker canary before promotion.
- Fail closed/retirement: invalid route/import or exhausted budget is visible
  terminal/escalated state. Remove ambient unbounded fallbacks after zero use.

### F12 — oversized rework exceeded the five-task ceiling

- Root cause: review rework bypassed finalized dispatch-wave limits.
- Owner/control: planner/compiler compiles rework waves; executor enforces the
  same maximum scope/grant as normal dispatch.
- Milestone/proof: M8A. Six-task fixture splits into bounded waves with exact
  grants and identical accepted output.
- Rollout gate: replay then executor canary.
- Fail closed/retirement: oversized grant is rejected before worker launch.
  Delete review-only fanout bypass after zero-call scan.

### F13 — repeated normalized budget failures did not stop retries

- Root cause: circuit identity included task-specific text and every retry was
  treated as novel.
- Owner/control: executor normalizes failure class while retaining exact task/
  attempt identity; two equivalent `worker_budget_exhausted` occurrences open a
  plan circuit requiring split/budget authority.
- Milestone/proof: M8A. T7 plus T12 opens the circuit before a third blind retry;
  unrelated failures do not collide.
- Rollout gate: shadow-only circuits on captured corpus, then executor canary.
- Fail closed/retirement: open circuit blocks dispatch and preserves checkpoints.
  Delete unconditional retry branch after false-positive review.

### F14 — productive and replayed time/tokens/cost were not authoritative

- Root cause: telemetry lacked joined task/batch/attempt/repair identities and
  stage decomposition.
- Owner/control: observability emits queue, session-start, inference, tool,
  validation, retry-wait, compaction, Git, transition, repair, verify, and replay
  time plus calls/tokens/dollars and accepted-output deltas; Maintenance analyzes
  but does not mutate.
- Milestone/proof: M6 freezes unknown baselines/schema; M8A emits executor fields;
  M9 joins projections. Replays reconcile totals and never label legitimate M4
  implementation/review as waste; missing cost has an explicit reason.
- Rollout gate: shadow telemetry across captured and canary runs before an SLO
  becomes enforcing.
- Fail closed/retirement: missing denominators yield unknown, not zero. Remove
  raw-total efficiency reports after joined-ledger coverage reaches the M11 gate.

### F15 — custody records and overlaps were left open or contradictory

- Root cause: request, claim, attempt, decision, index, worker, and repair
  terminalization were separate best-effort paths.
- Owner/control: repair custody owns one fenced terminalization transaction or
  reconciled outbox; Run Authority prevents simultaneous current worker and
  repair grants for the same subject attempt.
- Milestone/proof: M7 writer/identity contract and M10 fault matrix. Every
  success, failure, cancellation, supersession, timeout, and escalation closes
  exactly one custody chain; overlap fixture accepts only one actor.
- Rollout gate: shadow closure audit, repair/worker canary, genuine block test.
- Fail closed/retirement: ambiguity remains open/pending and blocks another
  effect. Delete repair sidecar authority after zero reader/writer proof.

### F16 — auditor reasons were heuristic and could join unrelated sessions

- Root cause: findings used labels/basenames and omitted deterministic exact IDs.
- Owner/control: observability gathers exact evidence; Maintenance owns read-only
  deterministic reasons for normalized consecutive blocks, signature drift,
  unclosed custody, index mismatch, detection SLO, worker/repair overlap,
  cross-session joins, projection amplification, full seriality, oversized
  rework, invalid model, and missing ledger coverage.
- Milestone/proof: M9 reason fixtures fire once with exact evidence IDs and never
  match a same-basename unrelated session; M10/M11 verify recovery reporting.
- Rollout gate: report-only shadow and precision review before ticket proposals.
- Fail closed/retirement: unknown evidence produces an explicit unknown reason
  and no repair. Remove old heuristic gather branches after reason parity.

### F17 — mixed source/install/runtime versions could invalidate every proof

- Root cause: source, editable install, wrapper, worker, and running process
  provenance were not one enforced version vector.
- Owner/control: WBC records code/config/adapter identity; launcher proves it;
  Run Authority rejects wrong-version claims; observability reports provenance.
- Milestone/proof: M6 freezes the vector, M8 adopts it, M11 proves old-reader/
  new-writer and new-reader/old-run behavior plus source/install/cloud/resident
  SHA equality in canary/live evidence.
- Rollout gate: no deployment without pinned source and installed/runtime/wrapper
  receipts.
- Fail closed/retirement: mismatch stops launch/promotion and preserves read-only
  historical adapters. Delete compatibility writers only after mixed-version
  replay and forced rollback pass.

## Current-run implementation crosswalk

### Classification result

All F01-F17 controls and all three ranked recommendations are **already in
current-run scope** at their named M6-M11 integration points. The
`adoptable in a later unexecuted milestone without invalidating accepted work`
class is empty because those later briefs already contain the work; the
`post-run/follow-on only` class is also empty. No chain amendment is required if
each control stays in its assigned milestone. Pulling implementation or
enforcement forward into the current observe-only M6 plan would instead
**require amendment/replan/revision-boundary** and is not authorized by this
report.

The preceding 15-item user-visible summary is fully covered without separate
scope: item 1 maps to F05/F16; 2 to F01/F04/F15; 3 to F02; 4 to F03; 5 to F04;
6 to F06; 7 to F07; 8 to F08/F12; 9 to F09; 10 to F10/F11; 11 to F13; 12 to
F14; 13 to F15; 14 to F16; and 15 to F17/F10. The reusable components audited
for those items are named below so component existence is never confused with
current-executor wiring.

### F01-F17

**F01 — exact repair occurrence identity — already in current-run scope
(M6, M7, M10).** Integration: M6 freezes the exact tuple and inventories every
enqueue/claim/execute/receipt/decision/terminal join; M7 makes it the custody
writer key; M10 enforces dispatch and closure. Existing
`cloud/repair_requests.py`, `repair_contract.py`, recurrence logic, grants and
fences are partial components, not one key wired across the current executor.
Prerequisites are M6's accepted version/owner bundle and M6A's durable WBC store.
The first safe action is M6's observe-only occurrence-field/conformance matrix.
Acceptance is captured T7/T12 cross-binding rejection plus terminal evidence for
every request/claim/attempt/decision/index. The integrity risk is attaching a
valid receipt to the wrong revision or replay attempt.

**F02 — durable event-driven recovery — already in current-run scope (M6A, M8,
M10).** Integration: M6A persists block/exit facts, M8 wires every producer, and
M10 consumes deduplicated triggers while scans remain reconciliation backstops.
Enqueue hooks, request storage, watchdog and repair-trigger code exist and have
run, but the audit did not prove accepted recovery or the five-minute SLO.
Prerequisites are F01 identity, terminal storage and eligibility semantics. The
first safe action is to add the exact event/request/claim/terminal timestamp
fields to M6's inventory and baseline, without dispatch. Acceptance requires a
denominated genuine-blocker p50/p95/p99, p95 below five minutes, miss/duplicate
counts, and six-hour missed-event recovery. The risk is duplicate launch or
false liveness after ambiguous delivery.

**F03 — verify-only repair adoption — already in current-run scope (M6A, M7,
M8A).** Integration: M6A stores immutable receipts, M7 binds grant/tree/test/
fence identity, and M8A adds the executor's verify-only branch. Existing
same-lineage validators, adopt-execution authority receipts and completed-task
projections are reusable precursors; none is a repair-receipt consumer wired to
the current executor. Prerequisites are F01/F04/F15 and an accepted WBC API. The
first safe action is a non-dispatching receipt schema/negative-fixture contract;
the adapter waits for M8A. Acceptance proves same-revision adoption skips replay
while any code, contract, tree, test-set or fence drift selects normal execution.
The risk is silently trusting stale or incomplete work.

**F04 — append-only attempt/effect history — already in current-run scope (M6,
M6A, M8, M10).** Integration: M6 inventories aliases and producers; M6A turns
WBC's `ExecutionAttemptLedger` schema into transactional storage/query; M8
migrates producers; M10 proves replay. The schema exists, but its own audited
contract is schema-only and is not current-runtime storage. Prerequisites are
the exact WBC revision/vector and migration/data-policy decisions. The first
safe action is to retain every schema-only row as residual in M6 rather than
credit it as implementation. Acceptance requires durable start-before-dispatch,
exactly one terminal or explicit indeterminate result, byte-stable attempt
history and deterministic alias projections. The risk is overwriting custody or
replay evidence while presenting a mutable alias as history.

**F05 — one attempt-aware reducer and cursor vector — already in current-run
scope (M6, M9, M11).** Integration: M6 inventories authority-increasing readers;
M9 moves all status/liveness/repair/operator consumers to the Run Authority
reducer and coherent owner-source cursor vector; M11 retires fallbacks.
`arnold_pipelines/run_authority/reducer.py`, `authority/views.py` and shadow
comparators exist, but current chain/plan/repair labels still disagree and the
legacy readers remain wired. Prerequisites are F04 history and M8 producer
coverage. The first safe action is M6's reader registry and report-only
same-input comparison. Acceptance is 100% cursor/hash agreement with torn input
reported `UNKNOWN`/`INCOHERENT` and proven rollback. The risk is two authorities
selecting different attempts or allowing replay from a stale view.

**F06 — append-safe heartbeat projection — already in current-run scope (M6,
M7, M9, M11).** Integration: M6 records the implementation/runtime provenance
gap; M7 adopts the cursor-checked writer boundary; M9 proves rebuild and readers;
M11 retires full-file writers. `observability/events_projection.py` and commits
`3221870c…`/`0a31d539…` exist, and advancing cursor artifacts were observed, but
their exact producer SHA and current-executor adoption were not proven.
Prerequisites are a pinned version vector and F04 source history. The first safe
action is a read-only writer/reader/provenance inventory, not another projection
implementation. Acceptance is the 10,000-heartbeat/concurrent-reader stress,
sequences 0..9999, atomic rebuild digest parity, byte/time telemetry and zero
false stalls. The risk is journal loss, torn reads or liveness fabricated by
projection I/O.

**F07 — DAG feasibility — already in current-run scope (M6, M8A).** Integration:
M6 captures the Transaction/Strategy corpus; M8A uses and extends
`orchestration/task_feasibility.py` at finalization for width, critical path,
seriality, routing groups and turn demand. The v2 compiler exists and has focused
tests, but no captured-corpus report or current new-plan canary proves it is the
governing runtime gate. Prerequisites are immutable corpus hashes and F17
provenance. The first safe action is captured replay in report-only mode.
Acceptance rejects unexplained full seriality for eight or more tasks while
preserving real semantic dependencies. The risk is either rewriting an accepted
plan or rejecting legitimate serial work; enforcement therefore applies only to
newly finalized canary plans.

**F08 — split complex implementation/proof work — already in current-run scope
(M6, M8A).** Integration: M6 captures oversized-task evidence; M8A extends the
existing feasibility result with split-or-signed-budget authority and residual
checkpoints. Prompt/compiler checks exist only partially and are not universally
enforced by the executor. Prerequisites are F07 feasibility, exact attempt
identity and a versioned budget grant. The first safe action is replaying known
complexity-7/8/9 fixtures without changing live plans. Acceptance proves each
fixture splits or fails admission and preserves productive checkpoints when
proof budget ends. The risk is discarding partial work or silently widening the
budget/revision contract.

**F09 — deterministic harness validation — already in current-run scope (M6,
M8A).** Integration: M6 records the unconsumed declaration; M8A wires the
existing `finalize_contract.validation_jobs` schema to the existing suite
runner/backstop/acceptance transaction. The declaration and adjacent harness
exist, but no current runtime consumer was found. Prerequisites are F07
classification and a reviewed allowlist for non-mutating checks. The first safe
action is an M6 producer/consumer row showing the missing edge; the wiring waits
for M8A. Acceptance gives T10/T12/T15-equivalent jobs reproducible environment,
output and hashes with exactly zero model calls. The risk is either continuing
to spend model calls or letting a misclassified validation job perform effects.

**F10 — exact source/ref admission and bounded startup — already in current-run
scope (M6, M8A, M11).** Integration: M6 freezes every source/install/runtime
boundary; M8A applies existing execution binding/source admission to every
launcher and relauncher; M11 proves mixed-version behavior. Those guards exist
and protect some boundaries, but the audit found divergent relaunch paths and no
universal current-runtime gate. Prerequisites are the F17 vector and full Git
history for ancestry proof. The first safe action is M6's zero-exemption launcher
registry and one-read validation contract. Acceptance proves invalid refs stop
within the configured attempts before provider/model dispatch and emit a typed
reason. The risk is executing or accepting evidence from the wrong tree.

**F11 — typed provider/model/import/compaction circuits — already in current-run
scope (M6, M8A).** Integration: M6 inventories each failure class separately;
M8A adds distinct counters and terminal outcomes to the existing circuit
framework. The context compressor and completed-receipt replay bounds exist and
are tested; provider timeout, model resolution and import-isolation coverage are
not jointly wired or canary-proven. Prerequisites are F01 attempt identity and
F17 provenance. The first safe action is a report-only per-class circuit matrix,
not one combined counter. Acceptance fixtures cover empty/invalid model,
divergent imports, repeated 300-second timeout, repeat compaction and replay with
one typed terminal outcome and no duplicate effect. The risk is hiding repeated
work or colliding unrelated failures.

**F12 — bounded review-rework waves — already in current-run scope (M6, M8A).**
Integration: M6 identifies the review bypass; M8A routes review rework through
existing `_core.io.split_oversized_batches` and enforces the grant ceiling. The
splitter is wired for ordinary batches, not the audited review-rework path.
Prerequisites are finalized task identity and unchanged max-wave policy. The
first safe action is the six-task regression fixture; production wiring waits
for M8A. Acceptance observes a 5+1 dispatch and rejects an oversized grant before
worker launch with identical accepted output. The risk is unbounded fanout or a
wave split that changes dependency/revision semantics.

**F13 — normalized budget-failure circuit — already in current-run scope (M6,
M8A).** Integration: M6 freezes the normalized reason and collision corpus;
M8A adds `worker_budget_exhausted` to the existing hinge/phase/recurrence
framework. Adjacent circuits exist, but the named two-strike plan breaker is not
wired. Prerequisites are F01 exact occurrence identity and F08 split/budget
transitions. The first safe action is report-only normalization and collision
fixtures. Acceptance proves two equivalent failures block a third launch while
unrelated tasks/providers do not collide. The risk is either another blind retry
or a false circuit that blocks valid work and loses replay custody.

**F14 — joined productive/replayed telemetry — already in current-run scope
(M6, M8A, M9, M11).** Integration: M6 freezes vocabulary, explicit unknowns and
denominators; M8A emits executor work-class fields; M9 joins the WBC/event stream;
M11 makes coverage a promotion gate. Event kinds, cost projection and timing
fragments exist, but no authoritative task/attempt/repair/accepted-output join is
wired. Prerequisites are F01/F04 keys and accepted work-class rules. The first
safe action is the current M6 unknown-preserving schema/baseline. Acceptance
reconciles queue, inference, tool, validation, retry, compaction, Git, repair,
tokens, dollars and accepted-output totals without converting missing to zero.
The risk is false efficiency claims that misclassify productive review or drive
authority-changing policy from incomplete telemetry.

**F15 — atomic custody terminalization — already in current-run scope (M6, M7,
M10).** Integration: M6 inventories all writer/terminal joins; M7 implements one
fenced occurrence lease/epoch transaction or reconciled outbox; M10 runs the
fault/overlap matrix. Repair claims, attempts, custody events and Run Authority
grants are actively used precursors, but coherent terminal closure is not
current-runtime proven. Prerequisites are F01 identity and M6A transactional
storage. The first safe action is M6's writer/outbox/terminal conformance map.
Acceptance closes exactly one chain for success/failure/cancel/supersede/timeout/
escalate and accepts only one actor under stale-fence/cross-host overlap. The
risk is simultaneous authoritative actors, double effects or ambiguous open
custody that later replay treats as available.

**F16 — deterministic exact-evidence auditing — already in current-run scope
(M6, M9, M10, M11).** Integration: M6 inventories exact evidence consumers; M9
makes gather reasons pure over occurrence/cursor/version; M10/M11 prove recovery
reporting and retire heuristic joins. Typed reasons, exact references and the
progress-auditor controller exist and run, but the current plan's sequence-2582
drift event still records canonical `UNKNOWN` versus legacy `no_action`.
Prerequisites are F05 cursor truth and F01/F17 identity. The first safe action is
replaying known false same-basename/cross-session joins in report-only mode.
Acceptance emits each reason once with exact IDs, never matches the unrelated
session, and takes no action on ambiguity. The risk is an observer becoming a
second authority or repairing the wrong run.

**F17 — one time-scoped version vector — already in current-run scope (M6, M8,
M11).** Integration: M6 freezes source, install, wrapper, config, worker and
process identities; M8 carries them through every producer; M11 gates promotion
and compatibility retirement. Execution binding, source admission and restart
receipts exist, but they are selective: the live M6 canonical source binding is
to `5ece3591…`, the observed project head was `47fc7a62…` and dirty, while this
read-only introspection used pinned resident runtime `6788980d…`; that is
evidence of separate code locations, not proof of one loaded runtime vector.
Prerequisites are exact ownership and immutable runtime directories. The first
safe action is M6's attested vector and mismatch inventory. Acceptance requires
source/install/wrapper/config/process/import equality at launch, relaunch and
promotion plus mixed-version and forced-rollback canaries. The risk is that
every other test, receipt and replay proves behavior of different code.

### Ranked recommendations

**R1 — enforce the existing authority/custody/WBC/version foundation everywhere
— already in current-run scope (M6-M8, M10-M11).** Integration combines F01,
F04, F05, F10, F15, F16 and F17 without creating another reducer, queue, ledger
or provenance manifest. The components exist only in partial/selective wiring.
Prerequisites are the M5/M5A completed-prefix evidence, accepted M6 owner/vector
bundle and M6A/M7 storage/custody contracts. The first safe action is the current
M6 zero-exemption producer/consumer/boundary matrix in report-only mode.
Acceptance is exact vector equality, complete owned rows, zero accepted-but-
unclaimed repair, one terminal actor and no same-cursor projection disagreement.
The risk is invalidating accepted history through competing authority or
cross-revision adoption.

**R2 — wire existing Megaplan efficiency controls into the compiler/executor —
already in current-run scope (M8A).** Integration composes F03 and F07-F13 at the
existing feasibility, validation, batch-splitting and circuit seams. Those
primitives range from tested-but-unproved to entirely unwired in the current
executor. Prerequisites are R1's exact identity/storage/vector and the immutable
Transaction/Strategy/rework corpus. The first safe action now is only M6 corpus
capture; M8A begins with report-only replay. Acceptance requires feasible DAGs,
zero-model deterministic validation, 5+1 rework, no third equivalent budget
launch and drift-sensitive verify-only adoption. The risk is applying new policy
to an accepted live plan or widening budgets/effects outside its revision.

**R3 — make joined telemetry and canaries the completion authority — already in
current-run scope (M6, M9-M11).** Integration combines F02, F06 and F14 with the
M9 projection/ledger, M10 genuine recovery and M11 promotion/retirement gates.
Telemetry and projection components exist, but joined denominators and exact-
runtime canaries do not. Prerequisites are R1-R2, accepted WBC storage/identity
and explicit missing-data semantics. The first safe action is M6's schema and
unknown baseline; mutation-capable canaries wait for their named milestones.
Acceptance requires sub-five-minute denominated recovery, 10,000-heartbeat
concurrency proof, 100% cursor/hash agreement, productive/replayed totals, one
genuine recovery, no duplicate effect and mixed-version rollback evidence. The
risk is treating commits, tests, PIDs or labels as runtime completion and then
retiring custody/replay compatibility too early.

## Recommended sequencing for this run

1. **Can be incorporated at M6 without changing its accepted intent:** finish
   only the already-planned observe-only exact vector/owner validation,
   zero-exemption writer/reader/producer/consumer inventories, F01-F17 mapping,
   captured-corpus hashes, reusable-component-versus-runtime-wiring status, and
   explicit unknown baselines. The current gated plan already contains these;
   this report does not authorize its finalize or execution transition.
2. **Must wait for the existing unexecuted milestones:** M6A owns the operational
   WBC store; M7 owns occurrence/lease/epoch and append-safe writer adoption; M8
   owns universal runtime/boundary producers; M8A owns compiler/executor controls;
   M9 owns reducer consumers, projections and joined telemetry; M10 owns safe
   retry/event recovery/effects; M11 owns conformance, controlled runtime proof
   and evidence-gated retirement.
3. **Cannot be pulled forward without a revision boundary:** any M6 runtime
   writer change, enforcement, repair dispatch, active-plan rewrite, deployment,
   restart, bypass deletion or canary with real effects. If a later milestone's
   accepted brief proves insufficient, amend/replan that milestone before its
   execution; do not smuggle the change into M6 or reinterpret existing code as
   current-run adoption.

## Dependency-ordered milestone sequence

M5 remains prerequisite evidence reconciliation, not prevention implementation.

1. **M6 — contract, inventory, captured corpus, and baselines.** Observe only.
   Freeze owners, exact signatures, current WBC/Run Authority evidence, legacy
   paths, generated boundary/call-site/consumer inventory, deterministic
   Transaction/Strategy replay fixtures, SLO definitions, and unknown
   projection/compaction/productive-replay baselines. Stop if any owner or
   prerequisite proof is missing.
2. **M6A — WBC transactional ledger and migration foundation.** Implement the
   WBC-owned durable store/query API, start-before-dispatch and exactly-one-
   terminal/indeterminate semantics, transaction/outbox reconciliation,
   process-safe adapters, stored-byte privacy/retention/encryption, and
   crash-resumable mixed-version migrations.
3. **M7 — controlled writers, immutable attempts, receipts, and append-safe
   projection boundary.** Establish attempt-scoped evidence, fences/quarantine,
   repair receipt form, terminal custody joins, and the cursor/atomic projection
   writer. Roll back by disabling promotion while append/reconciliation stays on;
   never restore raw writers.
4. **M8 — universal WBC producer and runtime adoption.** Move every declared
   and discovered stage, chain, resident, cloud, worker, repair, finalize,
   cancellation/resume, publication/delivery and wrapper producer through the
   WBC API with generated static/runtime evidence. Historical adapters remain read-only.
5. **M8A — planner/compiler and executor efficiency.** Add DAG feasibility,
   complexity split, deterministic validation, bounded invalid-ref/provider/
   compaction/rework behavior, repair adoption, and plan circuits. This is a new
   milestone because those controls are a separate domain and do not fit safely
   inside the already broad M8/M10 custody work.
6. **M9 — canonical WBC consumers, one reducer, rebuildable projections, pure observers, and joined
   latency ledger.** Cut all views to one reducer cursor/hash, complete projection
   rebuild, separate work classes, and emit deterministic auditor reasons.
7. **M10 — failure injection, event-driven recovery and effect-safe retry.** Enforce exact repair
   signatures, bounded trigger/retry custody, p95 under five minutes, six-hour
   reconciliation, terminalization, independent verification, and repair/worker
   canary proof.
8. **M11 — controlled rollout, conformance, genuine block, and retirement.**
   Verify runtime provenance, mixed versions, deterministic replay, idle and
   worker/repair canaries, forced rollback, controlled deployment, and one real
   eligible blocked-run recovery before deleting any bypass and generating the
   content-addressed completion manifest.

Each post-M5 milestone is approximately one sprint. M6A prevents the WBC
transactional substrate from being hidden inside Custody M7 or universal M8;
M8A prevents M8 and M10 from
becoming multi-domain, superficially testable mega-sprints.

## Rollout and promotion gates

1. Shadow append-only evidence and latency/work telemetry; mutation, enforcement,
   external effects, and deletion remain off.
2. Replay the captured Transaction Spine and Strategy Roadmap inputs. Results
   must be deterministic by content hash, exercise each F01-F17 reason/control,
   and preserve the productive-versus-avoidable distinction.
3. Idle projection canary: pinned installed runtime, no active mutation,
   10,000-heartbeat/stress proof, valid monotonic concurrent reads, rebuild
   digest parity, zero false-stall or authority drift.
4. Planner/executor canary: new plans only, feasibility warnings before reject,
   deterministic validation and bounded circuits, no rewriting existing plans.
5. Repair/worker canary: one allowlisted synthetic or naturally occurring
   eligible blocker, exact signature/fence, one managed worker, verify-only
   adoption, terminal custody, independent 5m/1h/6h checkpoints.
6. Controlled deployment: record source, installed package, wrapper, config,
   contract, and running process SHAs; promote cohorts only on zero authoritative
   divergence and within SLO/error budgets.
7. Genuine blocked-run acceptance: deliberately use a real supported run and a
   genuine eligible blocker—not a mocked status label—to prove durable event to
   accepted repair/escalation p95, resumed authoritative progress, independent
   verification, projection agreement, and no duplicate/replayed effect.
8. Retirement: only after mixed-version and forced rollback proof, zero legacy
   authority readers/writers at static and runtime levels, approved deletion
   list, compatibility expiry, and content-addressed evidence.

At every stage the kill switch disables promotion/effects, not evidence append,
reconciliation, observation, or reporting. Rollback retains the new history and
projections and cannot restore a legacy authority writer.

## Completion contract

Completion requires all of the following together:

- current accepted Run Authority and WBC prerequisite manifests and ownership
  proofs;
- content-addressed milestone evidence and a chain-generated manifest/proof map;
- exact source/install/wrapper/config/contract/running-runtime provenance;
- deterministic replay of both captured incidents and all adversarial fixtures;
- idle projection, planner/executor, and repair/worker canary evidence;
- one genuine eligible blocked-run recovery with independent delayed proof;
- productive/replayed ledger coverage with explicit unknowns and no false waste
  classification;
- 100% reducer-cursor agreement across supported views;
- static and runtime proof of zero legacy authority bypasses;
- exact equality of generated WBC contracts, semantic call sites and captured
  runtime traces, with no schema/support/manual-only completion row;
- approved removal list, actual deletion/retirement receipts, compatibility
  expiry register, and forced rollback proof.

Local tests, green component suites, nominal `done`, manifest presence without
valid hashes, a repair commit, a fresh PID, or a passing canary simulation cannot
individually claim completion.

## Explicit unknowns and non-goals

- Exact production latency caused by projection I/O is unknown until M9 timing
  and byte telemetry exists. The 137 GiB estimate demonstrates amplification,
  not a measured wall-time attribution.
- Exact compaction time and the productive fraction of the 50m20s Strategy GLM
  turn are unknown until M8A instrumentation exists.
- Productive-versus-replayed token/cost baselines are unknown until joined
  per-task/attempt/repair receipts exist; current figures are conservative
  lower bounds, not SLO baselines.
- Initial p95 and circuit thresholds are safety policies, not claims about
  mature cohort distributions. Maintenance's cold-start sample rules govern
  analytical recommendations.
- The epic does not remove necessary review, proof, high-depth reasoning, or
  legitimate serial dependencies; it makes their cost explicit and justified.
- The epic does not deploy, restart, repair, merge, push, or mutate a live chain.
  Planning artifacts confer no runtime authority.
