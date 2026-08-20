---
id: 01KYMTMKX3VA0VBKXJ1GY5FRN8
title: Finalizer must not emit graphs rejected by execution feasibility
status: open
source: human
tags:
- bug
- finalize
- execute
- graph
- feasibility
- routing
- regression
- post-m11
- blocked-by-m11
- execution-transaction-integrity
- progress
- pre-native-blocker
- planner
codebase_id: null
created_at: '2026-07-28T16:58:58.851378+00:00'
last_edited_at: '2026-07-30T20:56:30.000000+00:00'
epics:
- epic_id: megaplan-native-parity-corrective
  resolves_on_complete: false
  kind: associated
  provenance: null
  linked_at: 2026-07-30 20:16:48.610459+00:00
---

## Classification

MUST LAND IN THE POST-M11 STABILIZATION/RELEASE FOLLOW-UP BEFORE NATIVE PARITY OR PLATFORMIZATION EXECUTES. This is an admission/finalization correctness defect, not ordinary implementation rework.

## Repeated production occurrences

M11 has reproduced the same defect twice:

- An earlier finalize emitted a 46-task execution graph containing routing-only dependency reasons and many unordered overlapping write sets. The post-finalize feasibility gate rejected it.
- On iteration 10, already-completed implementation reached finalization and the canonical force receipt moved blocked to gated. Finalize then generated a 40-task, 67-edge graph that failed with 60 deterministic diagnostics: 59 write_overlap_unordered failures and one routing_dependency_forbidden failure (T15 depending on T6). State was persisted as critiqued/needs_rework and the status projection fell from 100% to 92%, although authenticated accepted implementation evidence had not been lost.

This is a recurring contract mismatch, not a one-off bad plan: finalize/revise can publish graphs that their own execute-feasibility contract rejects, causing expensive loops and making planner failure look like lost implementation progress.

## Root cause

Plan/rework generation, finalization, and execute entry do not share one atomic fail-closed graph-admission boundary. A candidate graph can be generated after expensive execution/review work, fail deterministic feasibility only at late finalize/execute admission, and replace the current workflow/progress cursor with needs_rework. Structured diagnostics are degraded into generic prose feedback, allowing revise to regenerate the same conflict family. Status also mixes task-graph bookkeeping with accepted implementation authority.

## Durable repair

- Use the exact same feasibility compiler for initial, revised, review-originated, finalized, and execute-entry graphs.
- Build every candidate graph off to the side; publish it and advance the workflow cursor only after the exact graph contract passes atomically.
- On rejection, preserve the last admitted graph, accepted attempt authority, completion evidence, and acceptance progress. Record planner_repair_required rather than implementation needs_rework.
- Feed structured diagnostics into deterministic graph repair: shared write paths require explicit semantic order or a declared single-writer/routing group; routing, authoring order, and batch shape may never create correctness dependencies.
- Enforce task size, declared-path, selector, test-run, and timeout limits at generation time. Split mechanically where safe; otherwise fail closed before dispatch.
- Fingerprint feasibility failures. The same graph/error signature gets only a small deterministic planner-repair budget; repetition trips a circuit breaker and cannot launch implementation or erase progress.
- Rework reconciliation consumes current authority before graph generation, so already-satisfied tasks cannot be regenerated merely to repair graph shape.
- Status reports accepted implementation/authority progress separately from plan-bookkeeping progress and never implies accepted work was undone solely because a candidate graph was rejected.

### Post-execution planner-repair lane

The 2026-07-30 recovery also proved that graph repair after accepted execution
must not route through the ordinary broad critique/revise/gate loop. M11 had
already completed implementation when a late graph-feasibility rejection sent
the run back through full-plan critique. That re-opened unrelated intent and
scope judgments, allowed a reviser to collapse the executable plan from 97
steps to 9, and consumed another wide model cycle even though the required
mutation was only deterministic graph normalization.

Add a distinct `planner_repair` transition for a rejected candidate graph:

- freeze the admitted intent, task authority, accepted attempts, scope, and
  completion evidence by content hash;
- repair only the candidate graph against the deterministic feasibility
  diagnostics (write ordering, routing-edge removal, bounded task splitting,
  selector budgets, and dependency evidence);
- compare the repaired graph's intent/scope/task semantic hashes with the frozen
  inputs and reject any semantic drift;
- run only the deterministic feasibility compiler plus a narrow independent
  graph-repair verifier;
- atomically admit the repaired graph or emit a typed planner blocker while
  retaining the prior admitted graph and accepted-work projection.

Broad model critique/revise/gate is permitted only when an explicit semantic
diff proves that user intent, scope, acceptance obligations, or task meaning
changed. Graph shape alone is not such a change. Recovery supervision must
route this receipt to `planner_repair`, not to implementation rework or the
ordinary planning loop.

## Acceptance

1. Replay both exact M11 regressions: the earlier 46-task graph and iteration-10's 40 tasks, 67 edges, 59 unordered overlaps, and T15-to-T6 forbidden routing dependency.
2. Infeasible candidates are rejected before publication or dispatch and never become the authoritative current graph.
3. The prior admitted cursor and all authenticated accepted task attempts remain unchanged and visible.
4. Structured repair produces a feasible graph or a typed planner blocker; it never redispatches completed implementation.
5. Every successfully finalized graph passes byte-for-byte the feasibility validator used at execute entry.
6. Two identical failure fingerprints trip the bounded planner-repair circuit breaker; no unbounded revise/finalize loop occurs.
7. Crash before candidate validation, between validation and publication, and after publication resumes idempotently with exactly one admitted graph generation.
8. Concurrent revise/finalize candidates race through CAS; exactly one feasible generation becomes current.
9. Cover valid parallel batches, genuine conflicts, overlapping write sets, routing-only pseudo-dependencies, task sizing, and narrow test selectors.
10. Status shows unchanged accepted-work progress plus a separate planner-feasibility blocker, with UTC occurrence and resolution receipts.
11. Replay the late M11 rejection after accepted execution and prove it enters
    `planner_repair`, not broad critique/revise/gate, and does not dispatch any
    implementation task.
12. A graph-only repair preserves the frozen intent/scope/task semantic hashes
    byte-for-byte; any mismatch fails closed and requires an explicit semantic
    replanning decision.
13. A fixture with a real acceptance-scope change proves the opposite route:
    broad re-critique is required and cannot be mislabeled as graph-only repair.

## Ownership and handoff

Execute this in the post-M11 stabilization release, not inside the live M11 epic. Native Parity must consume and replay the fixtures when it introduces source-visible completion/rework semantics. Platformization may extract the neutral candidate-graph admission/CAS/circuit-breaker primitive, but must not introduce a second planner, scheduler, authority reducer, or progress registry.
