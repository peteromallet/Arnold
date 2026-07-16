---
type: brief
slug: l3-megaplan-phase-migration
title: Megaplan Phase Migration and Retirement Readiness
epic: session-knowledge-compiler
created_at: '2026-07-16T00:00:00+00:00'
---

# L3 — Megaplan Phase Migration and Retirement Readiness

## Outcome

Make the neutral lifecycle the reversible managed-launch substrate for every
in-scope Megaplan worker while preserving all Megaplan-owned phase, profile,
fallback, gate, retry/rework, mode, plan/chain, approval, acceptance, worktree,
and result behavior. Produce a complete launch-seam registry and one-compilation-
unit proof that C1 can treat as its capture-completeness prerequisite.

## Source and prerequisite

Require reviewed L1 and L2 handoffs with matching schema/implementation hashes,
accepted required gates, and no blocking parity anomaly. Re-inventory the
selected target's direct and shared worker launch paths; the research inventory
is a floor, not proof of complete current coverage.

## In scope

- Enumerate prep, plan, critique, gate, revise, finalize, execute, review/rework,
  planning loop, tiebreaker, batch, bakeoff, fanout, diagnostic, and approved
  standalone worker seams across in-process/isolated and persistent/orchestrated
  modes. Generated set equality must expose unclassified starts.
- Wrap the shared worker seam with v3 reservation/start/event/result mechanics
  while preserving `WorkerResult`, rendered prompts, artifacts, provider
  sessions, configured/attempted/actual route, costs/tokens, fallback reasons,
  receipts, and error classification.
- Keep phase topology/state, profile and fallback resolution, gate verdict,
  retry/rework iteration, execution authorization/approval, worktree/commit
  effects, review acceptance, chain binding/progression, and watchdog policy in
  their current Megaplan components. Lifecycle records immutable correlations.
- Dual-record phase/iteration/attempt/plan/milestone/chain refs and reconcile
  phase results, receipts, Store events, routing ledger, legacy projections, and
  raw provider evidence through `projection_of` and canonical evidence owners.
- Migrate in risk order: read/planning phases; gate; revise; finalize/execute;
  review/rework; batch/bakeoff/tiebreaker/diagnostics; remaining approved seams.
  Every seam retains old+shadow and old-only rollback until its evidence gate.
- Test persistent session/follow-up and orchestrated fresh-session semantics,
  fallback attempts, retry/rework, chain stop/escalate, watchdog recovery,
  cancellation, partial result, late terminal, and approval boundaries.
- Produce the compiler ownership matrix for root/parent/contributor, retry/
  fallback/rework, synthesis owner, phase/worker projection, observer/auditor,
  chain supervisor, and terminal-delivery cases.
- Record retirement readiness per seam; do not delete an old start path or
  broadly enable v3 without G8 and its operational evidence.

## Out of scope

- Changing phase algorithms, profile contents, route/fallback policy, chain
  specification semantics, approval defaults, acceptance criteria, or review
  behavior.
- Replacing Store events/receipts/WBC evidence or making the lifecycle own plan
  or chain state.
- Actual production deployment, restart, two release observation windows,
  broad enablement, or old-path deletion.
- Compiler product implementation beyond the C1 handoff contract.

## Locked decisions

- Lifecycle is the provider/process execution mechanic; Megaplan is the caller
  and remains orchestration/authorization owner.
- A route fallback is a new attempt only after caller policy permits it; the
  lifecycle neither classifies policy nor selects the next model.
- Phase result/receipt/Store/routing views of one underlying evidence range
  compile once through the canonical evidence owner.
- Mutating/finalizing/execute/review seams migrate last and require parity plus
  negative authority tests.
- Any missing/unclassified start seam blocks the complete-coverage claim.
- G8 is per seam and operational; implementation readiness never implies
  cutover, deployment, or retirement approval.

## Open questions for the planner

- Which target-revision launches bypass `run_step_with_worker`, and which are
  supported producers versus diagnostic/manual exceptions? Every exception
  needs owner, rationale, explicit lifecycle policy, and retirement status.
- Where does provider session persistence live for each mode, and which
  lifecycle fields are projections of caller state rather than owned facts?
- Which receipt/event writer is authoritative per fact under WBC adoption, and
  where are gaps only corroborating evidence?
- What deterministic local/offline representative chain can exercise every
  phase/terminal/retry/rework path without deployment or external delivery?

## Constraints

- Preserve phase artifacts/verdicts and configured/attempted/actual route
  decisions byte-for-byte where stable, semantically where nondeterministic.
- No duplicate model start in shadow comparison; lifecycle flags are separate
  from model-routing/profile flags.
- Before any start on a cutover seam, reservation must fail closed; after start,
  reconciliation adopts and never retries merely because journaling failed.
- Existing execution/approval/worktree/custody guards remain mandatory and are
  tested negatively against lifecycle records/projections alone.

## Touchpoints

`workers/_impl.py` and provider workers; shared handlers, every phase handler,
`auto.py`, planning/prep/tiebreaker/batch/bakeoff/fanout loops; phase result and
classification; receipts and observability projections/routing ledger; chain
spec/execution binding/supervisor; worktree and approval/acceptance gates; and
worker/session/fallback/phase/chain/authority/watchdog/conformance tests.

## Measurable done criteria

- Generated launch-seam registry has no unexplained or unclassified supported
  start; each row names owner, v3 seam/flag, source evidence, fixture, test,
  compiler policy, rollback, and retirement status.
- Representative full local/offline chains cover all phases, persistent and
  orchestrated modes, fallback/retry/rework, approval denied/allowed, failed/
  cancelled/superseded/completed terminals, and watchdog recovery.
- Shadow parity shows identical required artifacts/verdicts/routes/sessions/
  receipts and no unexplained result/terminal/chain mismatch or duplicate start.
- Negative tests prove lifecycle/journal/projection cannot pass a gate, approve
  execution, retry/rework, accept review, advance a milestone/chain, mutate a
  worktree, transfer custody, or deliver.
- Per-seam rollback rehearsal preserves mixed v2/v3 history and prior results.
- Compiler matrix proves one logical `compilation_unit_id` and one canonical
  source range across retry/fallback, phase projections, nested contributors,
  observers, controllers, and delivery verification.
- `docs/managed-agents/handoffs/l3-megaplan-cutover.json` satisfies the epic
  handoff schema and is reviewed for C1; unresolved coverage blocks C1.

## Anti-scope

Do not redesign Megaplan, flatten phases, move policy into the launcher, change
profiles/fallback/approval, use lifecycle state as acceptance, enable production,
or delete a launch path without G8.

## Estimate and run shape

Approximately two skilled-human weeks. Overall plan difficulty 5/5; profile
`partnered-5`; robustness `full`; depth `high`; directed prep. A shared-launch
refactor can preserve happy-path outputs while violating subtle Megaplan policy,
authority, or chain boundaries.
