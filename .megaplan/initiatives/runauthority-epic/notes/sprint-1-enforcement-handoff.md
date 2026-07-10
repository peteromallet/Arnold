# Sprint 1 enforcement handoff

**Status:** handoff to Sprint 2; this is not an enforcement-completion claim.
**Scope:** the Sprint 1 freeze and shadow foundation completed on 2026-07-10.

## What Sprint 1 established

Sprint 1 closed the demonstrated scope-widening routes in batch replay,
failure-boundary reconciliation, and creative/doc merging when a persisted S4
batch scope can be proven. It also introduced a read-only authority inventory,
a generic contracts/reducer substrate, Megaplan execution binding and shadow
views, plus separate runner and publication diagnostics.

The persisted `batch_scope` record is deliberately a **compatibility bridge**.
It proves the bounded subject set for selected existing batch artifacts, so an
unproven artifact is quarantined rather than being merged under all-task scope.
It is not a `DispatchGrant`; it is not a coordinator lease or fence; it does
not create a task attempt or an accepted decision; and it must not become the
source from which final execution authority is reconstructed. Sprint 1 remains
shadow/read-only outside the explicitly repaired legacy mutation boundaries.

In particular, the following are *not* enforced by Sprint 1:

- issuance and validation of dispatch grants;
- coordinator-fence ownership and stale-fence exclusion;
- a single merge/reconcile validator on every mutation path;
- accepted-attempt and dependency-closure authority for the scheduler frontier;
- recovery custody decisions; or
- consumer rewiring away from raw artifact interpretation.

## Sprint 2 enforcement spine

Sprint 2 should bind the already-defined generic mechanics into a Megaplan
authority path without putting task-DAG, recovery, runner, or publication policy
into the generic kernel.

1. **Dispatch grants.** Introduce immutable `DispatchGrant` values as the
   Megaplan wrapper over `CapabilityGrant`. A result must carry its dispatch
   ID, run/plan revision, coordinator fence, explicit task and sense-check
   scope, prerequisite digest, worker identity, and task-attempt identity.
   Grant issuance and result validation must be idempotent and CAS-bound.

2. **Coordinator fences.** Establish a coordinator ownership epoch for each
   dispatch/recovery attempt. A result from a stale, superseded, or otherwise
   mismatched fence is rejected or quarantined, never made current by replay.
   The existing `ExecutionLease` is only temporary exclusion machinery; it is
   insufficient as dispatch authority because it lacks the complete scope,
   revision, attempt, and fence binding.

3. **Unified merge validation.** Route normal merge, failure-boundary
   reconciliation, no-pending replay, review rework, and creative/doc merge
   through one grant-and-evidence validator. It must validate scope, revision,
   dispatch, fence, prerequisite digest, subject attempt, evidence, CAS, and
   idempotency before deciding to accept, reject, quarantine, or supersede a
   claim. Keep legacy JSON as compatibility projections rather than a second
   mutation authority.

4. **Accepted-attempt frontier authority.** Make task completion an
   evidence-backed accepted `TaskAttempt`, not a terminal label in
   `finalize.json` or a batch payload. Derive dependency closure and
   `PlanExecutionView.next_ready_wave` exclusively from accepted attempts and
   their decisions. The scheduler must stop deriving its frontier from raw
   finalize status.

5. **Recovery custody.** Create `MegaplanRecoveryView`/service decisions that
   custody quarantined artifacts, invalid revision/lease/prerequisite cases,
   stale-runner evidence, branch ancestry faults, and repair actions. Recovery
   actions must bind a precondition view hash and actor, scope watchdog/repair
   markers to `(run_id, plan_revision, attempt_id)`, and never silently adopt
   or reinterpret stale legacy inputs.

6. **Consumer migration.** Move consumers through shadow, warn, then enforce
   using the smallest relevant authority or sibling view: execute scheduling;
   merge/reconcile; chain advancement; cloud status; watchdog; repair;
   PR/publication waiting; and human overrides. Preserve the separation of
   execution, runner, publication, human-gate, and recovery state throughout.

## Raw-reader retirement map

Sprint 1 intentionally leaves compatibility readers in place. Sprint 2 must
catalogue each consumer, place it behind the validated view/decision path, and
only remove or quarantine it after shadow-to-enforce equivalence coverage. No
raw source below is completion, scheduler, or recovery authority by itself.

| Remaining source family | Current role | Enforcement disposition |
| --- | --- | --- |
| `state.json`, `finalize.json`, `execution.json`, audits/checkpoints/traces | mutable projections | retain for diagnostics/compatibility; never infer accepted completion |
| S4 batch files and legacy `execution_batch_N.json` | claims; legacy input may lack scope | require grant/attempt/fence/evidence validation; legacy gaps quarantine |
| chain specs and canonical/alias/legacy chain state | configuration/projections | bind chain advancement to accepted dependency authority; do not choose a raw “best” state |
| cloud session markers, current-target evidence, and status sidecars | claims/projections | normalize as observations; bind identity before runner/recovery actions |
| watchdog snapshots/reports/registry and process/tmux/heartbeat data | observations/projections | use only correlated identity and freshness evidence in their sibling view |
| repair needs-human markers, snapshots, queues, decisions, and JSONL sidecars | claims/decisions/projections | custody through recovery decisions; disallow repair mutations that bypass authority |
| Git worktree, chain Git fields, and GitHub PR data | observations/projections | keep publication separate from execution completion |
| `run_state`, Store/compat adapters, `events.ndjson`, WAL folds, journals, and event-sourced configuration | legacy projections, claims, or storage decisions | consume as typed evidence/decisions with sequence and identity checks; do not silently fall back |

## Contradictions that must survive into enforcement

The inventory's contradictions are input diagnostics, not tie-break rules.
Sprint 2 must retain source paths, hashes/identities, and reasons in quarantine
or recovery records rather than selecting whichever raw artifact appears newest.
At minimum, the validator and recovery custody must cover:

- state/marker run or session mismatch; terminal state paired with a live
  process, or active state paired with dead/mismatched process/session evidence;
- `state.json` versus WAL-fold divergence, and `finalize.json` labels versus
  proven scoped claims or typed verdicts;
- S4 filename/path/index/digest/embedded-scope/subject disagreement, duplicate
  batch siblings, and every legacy batch without complete authority identity;
- canonical, alias, or legacy chain state disagreement; chain marker/state
  plan mismatch; and stale terminal/nonterminal combinations;
- invalid, superseded, out-of-workspace, or wrong-kind cloud markers and
  current-target observations;
- repair, needs-human, request, decision, or attempt session/plan/fingerprint
  mismatch; orphan or conflicting repair decisions; and post-terminal repair
  activity;
- watchdog/registry reports that conflict with marker, tmux, process, or
  freshness evidence;
- Git HEAD, chain heads, pushed/PR heads, execution evidence, dirty state, PR
  repository, or merged timestamp disagreement;
- ambiguous/reused PIDs or mismatched process/tmux/run identity;
- duplicate, gapped, out-of-order, or sidecar-disagreeing event sequences;
- journal prepare/commit/hash disagreement; and
- configured-but-unimplemented event-sourced storage or any input missing
  revision, attempt, grant, fence, and evidence identity.

## Sprint 2 acceptance boundary

Sprint 2 is ready to claim enforcement only when every accepted Megaplan task
transition has a traceable run revision, subject attempt, dispatch grant,
coordinator fence, prerequisite/evidence digest, validation decision, and
idempotency/CAS outcome; every merge-like path has used the same validator; and
the ready frontier derives from accepted dependency closure. Quarantined and
rejected inputs must remain explainable through durable, source-addressable
diagnostics and recovery custody.

Until those conditions hold, durable batch scope remains a safe compatibility
boundary for the repaired Sprint 1 paths, not final run authority.
