---
type: brief
slug: m5-post-wbc-custody-convergence
title: Post-WBC Megaplan cloud custody convergence
epic: custody-control-plane
status: superseded-lineage-only
superseded_by: m5-run-authority-receipt-reconciliation-and-retirement
created_at: '2026-07-11T00:00:00+00:00'
---

# M5: Post-WBC Megaplan cloud custody convergence

> Historical lineage only; this brief is not referenced by `chain.yaml`. Its
> useful cloud-custody cases are absorbed by M8-M11. The settled split is in
> `../decisions/single-authoritative-runtime-history.md`: Run Authority owns
> grants/decisions/coordinator fences, WBC owns boundary and attempt/effect
> evidence, Custody owns action-target leases/epochs/transfer/recovery, and no
> projection authorizes action.

**Sizing and dials:** one roughly two-week sprint; overall plan difficulty 5/5;
`partnered-5/full/high @codex +prep`.

## Outcome

Make the existing custody control plane consume the completed Workflow Boundary
Contracts (WBC) and Run Authority contracts for one bounded surface: custody
decisions for Megaplan cloud-chain execution. The resolver, status/current-target,
watchdog/repair classification, and independent recovery verification must agree
from the same version-pinned evidence and fail closed on missing, stale, torn, or
contradictory facts.

This is an integration and cutover sprint over the completed M1-M4 foundation,
not a new event ledger, workflow runtime, or portfolio-wide migration.

## In scope

- Verify the prerequisite WBC completion manifest against the current WBC chain,
  North Star, briefs, milestone state, merged publication evidence, and deliberate
  proof artifacts; record the accepted manifest and contract hashes in the
  milestone handoff.
- Map the landed WBC boundary/attempt/effect evidence and Run Authority
  grant/attempt/decision/custody views into the existing read-coherent
  `resolve_run_state()` evidence envelope without introducing a parallel schema.
- Cut the supported Megaplan cloud-chain custody path over to that envelope:
  cloud status and current-target selection, watchdog classification, repair
  dispatch eligibility, and post-repair independent verification.
- Preserve status as a multidimensional projection: execution authority,
  liveness, custody, recovery, publication, and integrity remain distinct.
- Add legacy/current and fault fixtures for missing/stale contract versions,
  torn evidence, unrelated/dead processes, stale fences, duplicate dispatch,
  false recovery, projection drift, and WBC/Run Authority disagreement.
- Run shadow comparison first. Implement enforce-mode gates and rollback wiring,
  but leave production enforcement and mutating repair disabled until the human
  promotion gate is approved outside this run.

## Out of scope

- Creating or replacing WBC's execution-attempt/effect ledger, boundary schema,
  semantic findings, payload store, conformance manifest, or writer APIs.
- Reworking Run Authority grants, attempts, decisions, fences, quarantine, or
  accepted operational views.
- Generic/native workflow migration; resident, AgentBox, Discord delivery,
  notification, PR/publication, provider-effect, or broad auditor rewrites.
- Portfolio-wide writer consolidation, historical backfill, general replay,
  legacy deletion, production rollout, or a second status/repair lifecycle.

## Locked decisions

- WBC owns boundary declarations plus attempt/effect evidence; Run Authority owns
  grants and accepted decisions; custody owns coherent observation and the policy
  that turns those facts into a safe action/no-action result.
- M1-M4 are completed historical foundation. Their resolver and incident fixtures
  are extended in place and are not re-planned as milestones.
- Exact recorded contract and manifest versions are validated; never interpret an
  old record through a newer default schema.
- Live process evidence is corroboration only. Liveness is not success, custody,
  publication, or recovery.
- `UNKNOWN`/`INCOHERENT` and source disagreement authorize no dispatch, retry,
  terminal success, or finding clearance. Drift remains visible.
- A repair actor cannot verify itself. Recovery closes only after independent
  blocker-clearance evidence and resumed authoritative progress.
- Legacy raw fields may remain as expiring diagnostic projections, never as an
  action-authority fallback.

## Open questions and human gates

- Before chain launch, a human must approve the pinned WBC completion manifest
  and interface hashes, the exact cloud-chain surface inventory, freshness/lag
  thresholds, repair allowlist, canary cohort, rollback owner, and kill switch.
- If the WBC manifest is missing, stale, proof-empty, or lacks merged completion
  evidence, launch remains blocked; nominal chain status or a live process is not
  a substitute.
- Production enforcement, mutating repair, provider/Git effects, and legacy
  deletion are separate post-run approvals and are not granted by milestone
  acceptance or PR merge.
- Any discovered ownership conflict is a blocking finding to resolve in WBC or
  Run Authority ownership records; it must not be solved by adding custody-local
  authority.

## Constraints

- Start only from a clean checkout containing the genuinely completed WBC result.
- Preserve the North Star, existing public compatibility fields, and M1-M4
  incident behavior while making authority precedence explicit and testable.
- Evidence collection and status reads are pure: observer activity cannot refresh
  runner liveness, custody, or progress.
- Use existing feature flags or one narrowly scoped custody gate. Default and
  rollback state is observe-only/action-off.
- No chain/cloud start, approval, merge, push, or manifest fabrication is part of
  this planning brief.

## Done criteria

1. A checked-in surface map shows every in-scope cloud-chain reader and decision
   point consuming one version-pinned custody envelope, with no unexplained path.
2. The WBC prerequisite manifest and referenced contracts validate against the
   landed source; their hashes and Run Authority view versions are recorded.
3. Identical fixtures yield the same custody reason and next-action eligibility
   across resolver, status/current-target, watchdog, repair dispatch, and verifier.
4. Missing/stale versions, torn or contradictory evidence, unrelated/dead process
   evidence, stale fences, and projection drift return explicit unknown/degraded
   results and cause zero authority-increasing action.
5. Duplicate repair dispatch is fenced/idempotent, and no repair can record
   terminal recovery without later independent negative-control plus resumed-
   progress evidence.
6. Observer-purity, shadow-parity, false-positive, fault-injection, rollback, and
   compatibility tests pass for every in-scope surface.
7. Production enforcement and mutating repair remain disabled in configuration;
   the handoff names the unapproved promotion gates and rollback owner.
8. No new ledger, lifecycle enum, status authority, repair queue, writer API, or
   WBC/Run Authority contract is introduced.

## Touchpoints

- `.megaplan/initiatives/workflow-boundary-contracts/` completion manifest and
  landed contract/support-manifest outputs (read-only inputs)
- Run Authority runner and recovery views (read-only contracts)
- `arnold_pipelines/megaplan/run_state/`
- `arnold_pipelines/megaplan/cloud/current_target.py`
- `arnold_pipelines/megaplan/cloud/status_snapshot.py` and status formatting
- watchdog/progress classification and repair dispatch/lock contracts
- independent retrigger/recovery verification and focused custody fixtures

## Anti-scope

Do not revive the superseded ten-milestone migration, treat the historical M1-M4
briefs as pending, or use the research migration matrix as an executable promise.
Do not broaden the supported surface when an inventory gap appears; fail closed,
record the owner, and leave it for a separately approved follow-up. Do not enable
automatic execution or production action to make a test pass.
