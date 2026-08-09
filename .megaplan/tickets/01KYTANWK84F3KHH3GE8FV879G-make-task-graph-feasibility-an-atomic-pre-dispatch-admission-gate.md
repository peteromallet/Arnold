---
id: 01KYTANWK84F3KHH3GE8FV879G
title: Make task-graph feasibility an atomic pre-dispatch admission gate
status: dismissed
source: human
tags:
- bug
- planner
- finalize
- rework
- admission
- progress
- pre-native-blocker
codebase_id: null
created_at: '2026-07-30T20:15:29.896799+00:00'
last_edited_at: '2026-07-30T20:17:12.801303+00:00'
resolution_note: Duplicate discovered during verification; superseded by canonical
  ticket 01KYMTMKX3VA0VBKXJ1GY5FRN8, which now contains both M11 occurrences and the
  full durable repair contract.
epics: []
---

## Classification

MUST LAND IN THE POST-M11 STABILIZATION/RELEASE FOLLOW-UP BEFORE NATIVE PARITY OR PLATFORMIZATION EXECUTES. This is an admission/finalization correctness defect, not ordinary implementation rework.

## Exact production occurrence

On M11 iteration 10, already-completed implementation reached the finalization path and the canonical operator force receipt moved blocked to gated. The subsequent finalizer generated a 40-task, 67-edge task graph that failed its own feasibility compiler with 60 diagnostics: 59 write_overlap_unordered failures and one routing_dependency_forbidden failure (T15 depending on T6). The plan was then persisted as critiqued/needs_rework and the status projection fell from 100% to 92%, even though accepted implementation evidence had not been lost.

This created another expensive revise/finalize loop and made a planner-contract defect appear to operators as lost implementation progress.

## Root cause

Plan/rework generation and finalization do not share one atomic fail-closed admission boundary. A candidate graph can be generated after expensive execution/review work, fail deterministic feasibility only at late finalize, and then replace the current workflow/progress cursor with needs_rework. Repeated revise may regenerate the same overlap family because the diagnostics are treated as generic prose feedback instead of executable graph constraints. Status then mixes task-graph bookkeeping with accepted implementation authority.

## Durable repair

- Compile and validate every initial, revised, and review-originated task graph before it becomes the current admitted graph or can dispatch implementation.
- Build a candidate graph off to the side; persist it and advance the workflow cursor only after the exact feasibility contract passes atomically.
- On rejection, preserve the last admitted graph, accepted attempt authority, completion evidence, and acceptance progress. Record planner_repair_required rather than implementation needs_rework.
- Feed structured diagnostics back into deterministic graph repair: shared write paths require an explicit semantic order or declared single-writer/routing group; routing/authoring/batch shape may never create correctness dependencies.
- Enforce task size, declared-path, selector, test-run, and timeout limits at generation time. Split mechanically where safe; otherwise fail closed before dispatch.
- Fingerprint feasibility failures. The same graph/error signature may be retried only through a small deterministic planner-repair budget; repeated signatures trip a circuit breaker and must not launch implementation or erase progress.
- Status must report accepted implementation/authority progress separately from plan-bookkeeping progress and must never imply accepted work was undone solely because a candidate graph was rejected.
- Rework reconciliation must consume current authority first, so already-satisfied tasks cannot be regenerated merely to repair graph shape.

## Acceptance

1. Replay the exact M11 v10 fixture: 40 tasks, 67 edges, 59 unordered write overlaps, and the T15-to-T6 forbidden routing dependency.
2. The infeasible candidate is rejected before dispatch and never becomes the authoritative current graph.
3. The prior admitted cursor and all authenticated accepted task attempts remain unchanged and visible.
4. Structured repair produces a feasible graph or a typed planner blocker; it never redispatches completed implementation.
5. Two identical failure fingerprints trip the bounded planner-repair circuit breaker; no unbounded revise/finalize loop occurs.
6. Crash before candidate validation, between validation and publication, and after publication resumes idempotently with exactly one admitted graph generation.
7. Concurrent revise/finalize candidates race through CAS; exactly one feasible generation can become current.
8. Status shows unchanged accepted-work progress plus a separate planner-feasibility blocker, with UTC occurrence and resolution receipts.
9. Narrow affected tests validate the repair; a bounded full-suite backstop runs only at the declared release gate.

## Ownership and handoff

The post-M11 stabilization release owns the immediate compatibility fix and this exact regression. Native Parity must consume and replay the fixture when it introduces source-visible completion/rework semantics. Platformization may extract the neutral candidate-graph admission/CAS/circuit-breaker primitive, but must not introduce a second planner, scheduler, authority reducer, or progress registry.
