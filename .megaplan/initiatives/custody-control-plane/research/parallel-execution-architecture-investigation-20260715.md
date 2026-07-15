# Megaplan bounded parallel execution: evidence and architecture

Status: architecture investigation; no implementation
Initiative: custody-control-plane
Related milestone: m8a-planner-compiler-and-executor-efficiency
Companion evidence and policy: [Task sizing, dependency graph, and test budget investigation](task-sizing-dependency-test-budget-investigation-20260715.md)

## 1. Scope and evidence labels

This document establishes what Megaplan actually does after finalization and
designs bounded dependency-aware parallelism. It uses four explicit labels:

- **Evidence**: behavior visible in code, schema, artifacts, or tests.
- **Inference**: a conclusion drawn from multiple evidence points.
- **Design choice**: proposed behavior, not current behavior.
- **Unknown**: a decision that must be resolved before implementation.

This investigation was read-only except for this document. It does not
implement parallel execution.

### Baselines inspected

| Baseline | Revision/state | Purpose |
| --- | --- | --- |
| /workspace/arnold | b764651308a6426983315047d231e2ba0d71211c plus a materially dirty concurrent worktree | Current project behavior and in-flight changes |
| /workspace/arnold-consolidation-20260714 | 89e74997dd807f20c659519bf4831beed3c2ab7d, clean | Pinned resident runtime named by the delegated context |

Core topological batching and the neutral batch runtime are the same in both
baselines. Relevant divergence is identified below.

### Initiative selection

The existing custody-control-plane initiative is the real match and is reused.
Its M8A milestone already owns semantic dependency reasons,
critical-path/parallelism feasibility, task sizing, and executor efficiency:

- .megaplan/initiatives/custody-control-plane/NORTHSTAR.md:76-78
- .megaplan/initiatives/custody-control-plane/chain.yaml:154-171
- .megaplan/initiatives/custody-control-plane/briefs/m8a-planner-compiler-and-executor-efficiency.md:58-59,94

No new initiative is warranted.

## 2. Executive conclusion

**Evidence:** Megaplan has a deterministic topological-wave calculator,
dependency-closed authority projections, batch result envelopes, scope and
revision checks, atomic state writes, a monotonic event journal, whole-plan
worktree support, and generic threaded/process scatter-gather utilities.

**Evidence:** Production execute does not dispatch finalized tasks to parallel
workers. One topological batch becomes one prompt to one worker session. The
auto loop invokes batches serially. Ready waves wider than five are split into
serial chunks. Manual batch execution also requires all earlier chunks to be
complete, including independent sibling chunks.

**Evidence:** Dependencies are model-authored. Finalize validation checks basic
task shape, status, complexity, and hygiene, but does not require depends_on,
unique task IDs, known dependency IDs, semantic dependency reasons, or an
acyclic graph. Graph errors surface later when execute calculates batches.

**Inference:** Current batching is a cognitive/context grouping contract, not a
safe concurrency contract. Wrapping the loop in a thread pool would race a
shared checkout, one mutable finalize.json, one active_step record, and
phase-wide plan locks.

**Design choice:** Introduce a compile-and-run boundary:

~~~text
model-authored finalize.json
        |
        v
deterministic execution compiler
  - validate graph and semantic edges
  - bind immutable plan base
  - derive one unit per task
  - validate write/test/resource declarations
        |
        v
content-addressed execution_manifest.v2.json
        |
        v
bounded ready-queue scheduler
        |
        +--> isolated task worktree --> proposed commit/result
        +--> isolated task worktree --> proposed commit/result
        |
        v
single deterministic acceptance coordinator
  - fence lease/result
  - validate writes and narrow tests
  - apply to private integration ref
  - persist acceptance receipt
  - release dependents
~~~

Worker success must not equal task acceptance. Only a persisted acceptance
receipt for a result integrated into the plan's private integration lineage may
satisfy a dependency.

## 3. Current implementation: evidence

### 3.1 Finalization and graph generation

**Evidence:** The finalize prompt asks the model for JSON tasks, tells it that
tasks sharing dependencies form a batch capped at five, and describes one batch
as one model conversation. It asks for ID, description, depends_on, pending
status, kind, complexity, evidence, and review fields
(arnold_pipelines/megaplan/prompts/finalize.py:95-175). This is a prompt
contract, not enforcement.

**Evidence:** In the project checkout, _FINALIZE_INPUT_SCHEMA requires task ID,
description, status, complexity, and complexity justification. It does not
require dependencies, kind, executor evidence, or reviewer verdict
(arnold_pipelines/megaplan/handlers/finalize.py:390-430).

**Evidence:** _validate_finalize_payload applies that schema and semantic checks
for nonempty tasks/strings, pending status, complexity 1-10, justification,
human-action phases, harness paths, and model-authored re-run-until-pass tasks.
It does not validate graph identity or topology
(arnold_pipelines/megaplan/handlers/finalize.py:432-560).

**Evidence:** The pinned resident runtime centralizes essentially the same weak
model schema in arnold_pipelines/megaplan/finalize_contract.py:12-58 and uses it
at arnold_pipelines/megaplan/handlers/finalize.py:392-433. It also requires top-level user_actions and
meta_commentary, but still does not require or validate dependencies.

**Evidence:** The broader persisted runtime schema describes depends_on,
executor evidence, files, commands, and review fields
(arnold_pipelines/megaplan/schemas/runtime.py:653-768). The model-input handler
remains the admission gate; write_plan_artifact_json applies step-I/O envelope
checks, not full graph validation
(arnold_pipelines/megaplan/store/plan_repository.py:238-287).

**Evidence:** _apply_programmatic_coverage maps detected plan-step summaries,
paths, and terms to model-authored task IDs. It records uncovered plan steps
but does not generate nodes or edges
(arnold_pipelines/megaplan/handlers/finalize.py:294-389).

**Evidence:** _write_finalize_artifacts normalizes contracts, selects baseline
tests, rewrites verification tasks, injects gates, calculates coverage and
complexity/calibration data, and writes artifacts
(arnold_pipelines/megaplan/handlers/finalize.py:1775-1848).

**Evidence:** A before_execute user action becomes a synthetic leading task and
every other task depends on it. An after_execute action remains a human handoff
(arnold_pipelines/megaplan/handlers/finalize.py:669-756).

**Evidence:** _ensure_execution_baseline records current Git/baseline
information. It does not create an immutable task base or checkout
(arnold_pipelines/megaplan/handlers/finalize.py:1851-1884).

**Evidence:** handle_finalize holds the plan lock, runs one finalizer worker,
promotes and validates scratch output, performs North Star gating, writes
artifacts, and transitions to finalized
(arnold_pipelines/megaplan/handlers/finalize.py:1896-1989).

**Conclusion from evidence:** The graph is authored by the finalizer model and
lightly normalized. It is not compiled from a stricter intermediate
representation.

### 3.2 Dependency-ready batching

**Evidence:** compute_task_batches treats evidence-backed completed IDs as
satisfied, rejects unknown dependencies, calculates topological waves,
preserves original task order among ready siblings, and rejects cycles
(arnold_pipelines/megaplan/_core/io.py:67-121).

**Evidence:** split_oversized_batches cuts a ready wave into contiguous chunks,
defaulting to five tasks (arnold_pipelines/megaplan/_core/io.py:124-142).

**Evidence:** The scheduler facade is serial: process_driver.process(batch) is
inside a normal for loop
(arnold_pipelines/megaplan/_core/scheduler/run.py:42-79). Code search found no
production execute callsite for run_scheduler in either baseline.

**Evidence:** The authority read model derives dependency-closed accepted IDs
and a next ready wave, preferring evidence-backed accepted attempts over raw
task status (arnold_pipelines/megaplan/authority/views.py:681-790). Tests show
T3/T4 becoming ready after accepted ancestors and accepted-attempt projection
winning over raw status
(tests/arnold_pipelines/megaplan/test_authority_views.py:232-286,336-380).

**Inference:** The wave calculator and authority projection are reusable pure
logic, but neither is a dispatcher.

### 3.3 Actual execute behavior

**Evidence:** handle_execute holds load_plan_locked for the whole execute
phase, applies approval/preflight policy, creates one active step, and chooses
manual batch or auto loop
(arnold_pipelines/megaplan/handlers/execute.py:429-602).

**Evidence:** In the dirty project checkout only, execution admission calls
assert_canonical_source_current
(arnold_pipelines/megaplan/handlers/execute.py:431-444;
arnold_pipelines/megaplan/planning/source_binding.py:52-230). The pinned
resident revision lacks this call. It binds plan source freshness, not worker
attempts to immutable Git trees.

**Evidence:** _run_and_merge_batch snapshots one shared worktree and invokes
run_step_with_worker exactly once for the entire batch task list. It merges that
single payload into shared finalize state and writes batch/evidence artifacts
(arnold_pipelines/megaplan/execute/batch.py:1783-2055, especially 1839-1847).

**Evidence:** handle_execute_one_batch recomputes and splits waves, refuses
batch N until every earlier split batch is authority-complete, then runs one
_run_and_merge_batch
(arnold_pipelines/megaplan/execute/batch.py:2069-2200).

**Evidence:** handle_execute_auto_loop recomputes pending batches and iterates
them serially. Each iteration calls one _run_and_merge_batch; timeout or a
blocking result breaks the loop
(arnold_pipelines/megaplan/execute/batch.py:3433-4310, especially
3918-3924,4029,4160,4205,4302).

**Conclusion from evidence:** Ready siblings may share one prompt, but they do
not receive separate workers. No production execute task has its own process,
lease, branch, worktree, or acceptance transaction.

### 3.4 Worktrees, immutable bases, and merge behavior

**Evidence:** init --in-worktree creates one branch/worktree for a whole plan
(arnold_pipelines/megaplan/cli/__init__.py:2564-2678).

**Evidence:** Chain --in-worktree creates one shared worktree for the chain
(arnold_pipelines/megaplan/cli/__init__.py:2776-2914). Milestone depends_on is a validation assertion;
the chain explicitly runs serially in listed order
(arnold_pipelines/megaplan/chain/spec.py:565-592).

**Evidence:** Chain Git code creates/reconciles one milestone branch and
publishes it through PR squash merge. Auto-merge refuses a dirty checkout and
retries without local branch deletion when a linked worktree prevents it
(arnold_pipelines/megaplan/chain/git_ops.py:838-1035,1985-2073).

**Evidence:** resolve_execution_environment records paths and current Git
provenance. Its module says the engine checkout is live process context, not a
plan-pinned identity. Mutating preflight persists evidence but creates no
isolated checkout
(arnold_pipelines/megaplan/runtime/execution_environment.py:1-6,109-186,205-243).

**Inference:** Plan/chain worktrees and PR merge code provide useful safety
primitives but are not task isolation. Execute workers mutate one shared
checkout and do not commit/merge tasks separately.

### 3.5 State and authority

**Evidence:** load_plan_locked takes a nonblocking plan-level file lock and
phase handlers retain it for long worker calls
(arnold_pipelines/megaplan/_core/state.py:684-725).

**Evidence:** write_plan_state takes a state lock, read-modify-validates, uses
atomic replacement, and emits a full state snapshot to a shadow-WAL event
(arnold_pipelines/megaplan/_core/state.py:1075-1271).

**Evidence:** save_state_merge_meta unions append-only metadata while caller
non-metadata normally wins
(arnold_pipelines/megaplan/_core/state.py:1463-1487).

**Evidence:** active_step is one record, not a set of active attempts, and its
heartbeat is conditional on one run ID
(arnold_pipelines/megaplan/_core/state.py:1522-1605). History and costs also
accumulate through one plan state
(arnold_pipelines/megaplan/_core/state.py:1624-1655).

**Evidence:** The event journal serializes per-plan sequence allocation and
emits monotonic events; state writes can emit complete snapshots
(arnold_pipelines/megaplan/observability/events.py:293-396,518-559).

**Evidence:** Existing result envelopes carry dispatch identity, scope,
revision, and idempotency data. Tests reject off-batch updates and stale
revisions, accept enveloped updates, and recognize duplicate idempotent results
(tests/execute/test_merge_scope.py:56-79,272-301,619-713).

**Inference:** Atomic files, monotonic events, and result envelopes are useful
foundations. The mutable projection and phase-wide lock are not a concurrent
state machine. Workers must never edit shared state directly.

### 3.6 Retry, review, failure, and cancellation

**Evidence:** --retry-blocked-tasks resets only blocked tasks to pending and
preserves completed/skipped evidence. Rework and blocked retries force a fresh
session (arnold_pipelines/megaplan/execute/batch.py:3468-3569;
arnold_pipelines/megaplan/handlers/execute.py:518-540).

**Evidence:** Characterization tests prove partial resume reruns only blocked
work and preserves earlier success
(tests/arnold_pipelines/megaplan/test_execute_s4_behavior_parity.py:82-128,159-191).

**Evidence:** A blocked batch stops the auto loop, so unrelated later batches
do not continue (arnold_pipelines/megaplan/execute/batch.py:4264-4302).

**Evidence:** Review is aggregate after execute. At the rework cap, blockers
remain recoverably blocked while cosmetic-only findings may proceed
(arnold_pipelines/megaplan/handlers/review.py:1256-1330,1698-1820). Rework task
IDs return to execute as a batch
(arnold_pipelines/megaplan/execute/batch.py:3645-3698).

**Evidence:** FutureParallelMarker reserves CANCEL, AWAIT, and ORPHAN as future
policy anchors; it is not task cancellation
(arnold_pipelines/megaplan/execute/policy.py:232-253,788-789).

**Evidence:** The neutral process batch runtime has bounded workers, per-child
timeout, and termination, but no execute-task lease/fencing protocol
(arnold_pipelines/megaplan/runtime/batch.py:92-169,369-640).

**Inference:** Existing retry preserves serial results but cannot quarantine
one failing task while independent siblings continue, revoke leases, reject
late cancelled results, or invalidate descendants after ancestor rework.

### 3.7 Generic parallel primitives

**Evidence:** arnold_pipelines/megaplan/runtime/batch.py defines immutable batch units/results/settings
and threaded/process scatter-gather with bounded concurrency and submission
order results
(arnold_pipelines/megaplan/runtime/batch.py:92-169,238-342,369-640).

**Evidence:** These utilities serve worker/research/review fanout, not execute
task dispatch. No execute-task concurrency tests use them.

**Inference:** The process runner can sit below a future scheduler, but it is
not the scheduler, workspace manager, authority writer, or merge coordinator.

## 4. Test evidence and gap matrix

The following focused suites ran in both baselines:

~~~text
tests/arnold_pipelines/megaplan/test_execute_s4_behavior_parity.py
tests/arnold_pipelines/megaplan/test_authority_views.py
tests/execute/test_merge_scope.py
tests/arnold_pipelines/megaplan/test_state_reconciliation.py
~~~

Result: **63 passed in each baseline**. They cover deterministic waves, partial
resume, authority projection, scoped/revisioned/idempotent merge, and state
reconciliation. They do not execute independent mutating tasks concurrently.

An extended run added chain worktree and milestone-validation suites:

- project checkout: **106 passed, 4 failed**;
- pinned resident runtime: **109 passed, 3 failed**.

Those failures reproduce without this document and concern existing chain
checkout/rebase, resume/PR anchor, deferred PR creation, and a project-only
auto-merge expectation. They are baseline drift, not parallelism regressions.

| Capability | Exists today | Absent |
| --- | --- | --- |
| Graph | Model-authored dependencies; deterministic wave calculation | Finalizer/compiler graph admission and semantic reasons |
| Frontier | Pure wave calculator and read-only authority projection | Durable queue, leases, dynamic release |
| Concurrency | Generic fanout runtime | Execute dispatcher with one worker per task |
| Isolation | Optional worktree per plan/chain | Immutable-base worktree per attempt |
| Base | Current provenance; dirty-project source binding | Content-addressed plan and attempt bases |
| Conflicts | Payload scope checks; Git at chain publication | Write prediction/reservations and task integration |
| Tests | Plan baseline and aggregate evidence | Narrow worker and candidate-integration tests |
| Acceptance | Batch envelopes/artifacts | Commit/tree acceptance receipt releasing dependents |
| Persistence | Atomic state, monotonic journal, one active step | Multi-attempt ledger/projection |
| Failure | Serial stop and blocked reset | Quarantine and unrelated continuation |
| Cancellation | Timeouts and future vocabulary | Cancellation fence, cascade, late-result rejection |
| Determinism | Stable wave order | Timing-independent dispatch and acceptance order |
| Limits | Five tasks per prompt; generic max workers | Global/plan/provider/resource/conflict permits |
| Review | Aggregate review and bounded rework | Per-task admission and descendant invalidation |

## 5. Proposed architecture

Everything in this section is a **design choice**.

### 5.1 Compiler and executable-unit contract

Finalization remains model-assisted. A deterministic compiler turns its output
into an immutable manifest. Workers never execute raw finalize.json.

The manifest binds plan ID, finalize digest, compiler/schema version, immutable
plan base commit/tree, graph digest, canonical task order, and one executable
unit per finalized task.

Each unit contains:

~~~yaml
- id: T3
  order: 30
  description: Add the executor receipt validator
  kind: code
  depends_on: [T1]
  dependency_reasons:
    T1: Consumes the receipt schema introduced by T1
  declared_reads:
    - arnold_pipelines/megaplan/schemas/**
  declared_writes:
    - arnold_pipelines/megaplan/execute/receipts.py
    - tests/execute/test_acceptance_receipts.py
  narrow_tests:
    - argv: [python, -m, pytest, -q, tests/execute/test_acceptance_receipts.py]
      timeout_seconds: 120
  resource_class: model_worker
  concurrency_group: default
  isolation: git_worktree
  max_attempts: 2
  timeout_seconds: 900
~~~

One task is the smallest object receiving a lease, fresh worker session,
worktree, tests, output commit, acceptance decision, and retry. The current
five-task prompt batch is not a parallel unit.

### 5.2 Graph validation

Reject compilation unless:

1. IDs are nonempty, unique, stable, and match a restricted grammar.
2. Every dependency exists; self-dependencies are forbidden.
3. Every edge has a semantic reason. Routing/model preference is not a reason.
4. The graph is acyclic, with a deterministic reported cycle path.
5. Canonical rank uses explicit order then ID as stable tie-break.
6. Disconnected roots are allowed and represent parallel opportunity.
7. Complexity, paths, tests, retries, and timeouts fit policy.
8. Paths are normalized repository-relative paths, cannot escape, and cannot
   target Megaplan control artifacts.
9. Unknown/dynamic write scope forces an exclusive lane.
10. Direct write conflicts between independent tasks are diagnosed and either
    serialized or rejected.
11. Shared-write ordering is a conflict group, not a false semantic dependency.
12. External effects require idempotency/effect keys and exclusive leases.

Emit a compiler report with critical path, maximum theoretical width, conflict
groups, exclusive tasks, predicted utilization, and all diagnostics.

### 5.3 Immutable bases and isolation

Two identities are immutable:

- plan_base_sha is fixed at manifest compilation.
- attempt_base_sha is fixed when an attempt is leased.

The plan owns a private integration ref initially at plan_base_sha. A ready
task's attempt base is the current integration head containing all accepted
dependencies. Each attempt receives a dedicated worktree/ref:

~~~text
.megaplan-worktrees/<plan>/<task>/attempt-<n>/
refs/megaplan/<plan>/attempts/<task>/<n>
HEAD = exact attempt_base_sha
~~~

The worker writes only there and cannot edit state.json, finalize.json, the
event journal, or another worktree. It returns a commit/tree, actual paths,
commands, test receipts, and structured output.

Initially reject dirty source checkouts for parallel mode and fall back to
legacy serial execute. A later explicit operation may snapshot dirty state into
a private synthetic base.

### 5.4 Ready queue and limits

A task is ready only when every dependency has an acceptance receipt for the
same manifest lineage. Raw done status, worker completion, or a proposed commit
is insufficient.

~~~python
while plan_is_runnable():
    view = authority.read_projection()
    ready = tasks_waiting_with_all_dependencies_accepted(view)
    ready.sort(key=lambda t: (t.topological_rank, t.order, t.id))

    for task in ready:
        if permits.available(task) and not reservations.conflicts(task):
            lease = authority.try_lease(
                task=task,
                attempt_base_sha=view.integration_head,
                dispatch_ticket=next_monotonic_ticket(),
            )
            if lease:
                reservations.acquire(task, lease)
                workers.launch(lease)

    for result in workers.poll():
        authority.record_proposed_result(result)
        acceptance.enqueue(result)

    acceptance.advance_in_dispatch_ticket_order()
    recover_expired_leases()
~~~

Effective concurrency is the minimum of global, per-plan, model/provider,
resource-class, concurrency-group, and nonconflicting write permits. Default to
one until serial equivalence passes; canary at two. Keep the existing five-task
setting as a legacy prompt-size control, not a worker limit.

### 5.5 Write-set/conflict prediction

Use three layers:

1. Declared exact paths and conservative directory globs.
2. Repository rules for generated files, lockfiles, migrations, schemas, code
   generation, and contract-sensitive reads.
3. Actual Git diff paths from the worker.

Overlapping declared writes cannot run together. A write/read contract hazard
becomes a real dependency or serialization constraint. Unknown scope is
exclusive.

At result time, fail closed or explicitly adjudicate actual writes outside the
declaration; compare actual changes with accepted changes since the attempt
base; use Git three-way apply as the syntactic authority; use candidate tests
as semantic conflict authority.

Begin prediction in report-only mode and measure false positives/negatives
before strict enforcement.

### 5.6 Narrow tests

The finalizer proposes tests; the compiler validates argv form, scope, timeout,
and repository policy. Avoid shell strings.

The initial enforcement ceiling follows the companion task-sizing policy: at
most three narrow selectors, 120 seconds total narrow-test wall time, and two
attempts (one normal run plus one diagnostic rerun). Integration and full-suite
validation remain harness-owned jobs.

Run:

1. task-local checks in the worker worktree;
2. the same checks plus conflict-sensitive selection on a temporary candidate
   integration tree.

The plan-level acceptance suite remains after all tasks are accepted. Each test
receipt records argv, cwd identity, base/candidate tree, exit, duration, bounded
output digest/location, and toolchain identity.

### 5.7 Deterministic merge and acceptance receipts

Workers may finish in any order. Acceptance advances by monotonic dispatch
ticket. A lower ticket must become accepted, quarantined, failed, cancelled, or
expired before a higher ticket is integrated. Validation can still overlap.

Acceptance transaction:

~~~text
1. Verify manifest/task/attempt/lease/cancellation fence/result digest.
2. Verify proposed commit descends from immutable attempt base.
3. Verify actual writes and idempotency envelope.
4. Apply to temporary candidate at current integration head.
5. Run candidate narrow/conflict-sensitive tests.
6. Atomically advance private integration ref.
7. Append immutable merge/acceptance receipt.
8. Update rebuildable projections.
9. Release newly dependency-complete tasks.
~~~

The receipt includes manifest/graph digest; task, attempt, lease, and ticket;
plan/attempt/prior/accepted Git identities; write-set digests; result/test
digests; merge outcome; authority decision; and retry lineage.

Only the receipt creates dependency-satisfying authority. Crash recovery
reconciles ref and receipt idempotently.

### 5.8 Task lifecycle

~~~mermaid
stateDiagram-v2
    [*] --> Waiting
    Waiting --> Ready: dependency receipts accepted
    Ready --> Leased: permits + reservation + immutable base
    Leased --> Running
    Running --> ResultProposed
    ResultProposed --> Validating
    Validating --> MergePending: checks pass
    MergePending --> Accepted: integration + receipt
    Accepted --> [*]

    Leased --> Ready: lease expires before start
    Running --> Quarantined: worker failure / timeout / scope
    Validating --> Quarantined: test or merge conflict
    MergePending --> Quarantined: cancellation fence
    Quarantined --> Ready: retry allowed
    Quarantined --> Failed: cap or circuit
    Waiting --> Cancelled
    Ready --> Cancelled
    Running --> Cancelling
    Cancelling --> Cancelled
~~~

Do not collapse worker outcome, result validity, integration, and acceptance
into pending/done/blocked.

### 5.9 Quarantine, retries, cancellation, and review

A failed worker contaminates only its worktree. Preserve its branch, logs,
result, and evidence under quarantine policy; do not change integration.
Unrelated tasks continue and descendants wait.

Retries receive new attempt/lease IDs, a fresh session, and a new immutable base
from current accepted integration. Prior evidence is never overwritten. Fence
late results. Open a failure circuit when a normalized signature repeats or the
attempt cap is exhausted.

Plan cancellation persists a new generation, stops leases, signals workers,
waits a grace period, kills survivors, rejects old-generation results, keeps
accepted receipts, and cancels waiting/ready work. Task cancellation cascades
only to transitive descendants. Mutating tasks cannot be orphaned.

Add per-task admission review for scope, evidence, tests, and obvious
incompleteness. Keep aggregate review. Rework of an accepted ancestor creates a
new attempt and, by safe default, invalidates all transitive descendants built
against its earlier result. Execution retries and review-rework counts remain
distinct.

### 5.10 State persistence and observability

Workers never write shared plan artifacts. One scheduler/acceptance authority
writer uses short transactions and append-only events:

~~~text
manifest_compiled, task_ready, lease_acquired, attempt_started,
attempt_heartbeat, result_proposed, validation_started,
validation_completed, conflict_predicted, conflict_detected,
attempt_quarantined, task_retry_scheduled, integration_advanced,
task_accepted, dependency_released, cancellation_requested,
cancellation_acknowledged, failure_circuit_opened,
plan_execution_completed
~~~

state.json, finalize task status, dashboards, and active_attempts become
rebuildable projections. Extend the existing monotonic journal and result
envelopes; do not create a second history outside the custody control plane.

The new engine replaces phase-wide locking with a scheduler-leader lease, short
compare-and-swap authority transactions, per-task leases, serialized
integration, and projection refreshes. Legacy serial execute retains its lock
during migration.

Expose task state, blockers, lease/heartbeat, bases/commits, durations,
write sets, permit/conflict reason, receipts, and retry/cancellation lineage.
Expose plan critical path, queue/running counts, effective concurrency,
integration head/next ticket, conflict accuracy, utilization, retry waste, and
speedup. Alert on stale leases, starvation, blocked acceptance tickets,
repeated failures, fenced late results, and ref/receipt divergence.

Stored/control-plane timestamps remain UTC; durations remain relative.

### 5.11 Determinism rules

- canonical manifest JSON and graph digest;
- ready order by topological rank, explicit order, then task ID;
- monotonic dispatch tickets;
- immutable attempt bases;
- acceptance in ticket order, independent of completion timing;
- canonical paths/write sets;
- idempotent result and receipt IDs;
- explicit retry lineage and cancellation generation;
- one serialized integration ref.

Replay of the same receipts and retry/cancellation decisions must derive the
same projection and integration sequence.

## 6. Migration and rollout

### Phase 0: contract and characterization

- Add compiler tests for IDs, dependencies, cycles, reasons, paths, and order.
- Preserve the focused 63-test suite as the serial oracle.
- Resolve or quarantine existing chain test drift before making it a gate.

### Phase 1: shadow compiler

- Produce execution_manifest.v2.json beside legacy artifacts.
- Dispatch nothing from it.
- Compare waves with compute_task_batches.
- Report invalid graphs, conflicts, width, and forced serialization.

Legacy plans continue through serial execute.

### Phase 2: new engine at concurrency one

- Run one task per worktree with immutable bases, leases, receipts, and private
  integration.
- Require state/result and final-tree equivalence with the serial oracle.

This validates protocol correctness without concurrency timing.

### Phase 3: canary at two

- Enable only clean Git plans with explicit nonoverlapping writes and no
  external effects.
- Keep prediction advisory but enforce actual scope and merge checks.
- Inject worker crash, restart, timeout, cancellation, stale result, and
  integration conflict faults.

### Phase 4: dynamic release

- Release dependents immediately after accepted receipts.
- Add global/provider/resource limits and cross-plan fairness.
- Enable safe retries and transitive cancellation/review invalidation.
- Measure speedup, contention, conflict accuracy, and waste.

### Phase 5: enforcement and retirement

- Make compilation mandatory for new plans.
- Enforce write declarations only after prediction quality is proven.
- Raise defaults only with operational evidence.
- Retain a kill switch setting effective concurrency to one.
- Keep a read-only adapter for active old plans; never silently reinterpret a
  legacy graph as safe parallel work.

Rollback stops leases and resumes the new engine at concurrency one. It never
discards receipts or rewrites accepted integration history.

## 7. Required implementation tests

1. Compiler invalid IDs/dependencies/cycles/reasons/paths and stable digest.
2. Ready closure from receipts, stable order, fairness, and permit clamping.
3. Exact attempt base, sibling isolation, control-write denial, cleanup.
4. Write/glob/read hazards, unknown exclusivity, actual-scope escape.
5. Real overlapping worker execution and all concurrency caps.
6. Narrow worker/candidate tests, timeout, and bounded evidence.
7. Reverse completion with stable acceptance order, clean/conflicting apply,
   semantic test failure, and crash replay at every transaction boundary.
8. Sibling continuation, descendant waiting, fresh retry base, stale fence,
   repeated-failure circuit.
9. Cancellation before launch/during worker/during validation, cascade, kill,
   and late result.
10. Per-task review, aggregate rework, descendant invalidation, separate caps.
11. Scheduler restart, leader loss, projection rebuild, ref/receipt reconcile.
12. Random DAG/property tests and real Git fixtures compared with
    concurrency-one final trees.

## 8. Remaining decisions and unknowns

1. **Authority integration:** exact API and receipt ownership in custody/WBC.
2. **Artifact store:** location/names for manifest, attempts, and receipts.
3. **Git result:** commit/cherry-pick versus tree/patch application.
4. **Dirty plans:** fallback only versus private synthetic snapshot.
5. **Write language:** paths/globs plus generated and read-contract policy.
6. **Scope expansion:** fail, exclusive retry, or human adjudication.
7. **Limits/fairness:** initial global, plan, provider, and resource caps.
8. **Test selection:** repository mapping and per-task cost ceiling.
9. **Review invalidation:** formal proof needed to narrow descendant replay.
10. **External effects:** eligible effects and idempotent effect leases.
11. **Retention:** failed worktree, log, commit, and output lifetime/size.
12. **Cross-plan conflicts:** limit plans or reserve shared repository writes.
13. **Non-Git/prose mode:** equivalent immutable input/output acceptance.

## 9. Recommended decision

Build the deterministic compiler and a concurrency-one isolated executor before
enabling parallel workers. Treat one task as one executable unit, bind every
attempt to an immutable base, let only accepted integration receipts satisfy
dependencies, and keep state/integration authority single-writer.

The safety invariant is:

> No worker completion, task status field, or unmerged commit releases a
> dependent. A dependent becomes ready only after authority records an accepted
> ancestor result on the plan's integration lineage.

That invariant permits bounded concurrency without turning today's shared
checkout and shared JSON projections into race-prone authority.
