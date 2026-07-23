---
type: anchor
anchor_type: north_star
slug: custody-control-plane
title: 'North Star: Custody / Cluster Control Plane with Run Authority and WBC'
created_at: '2026-07-07T19:24:43.691296+00:00'
---

# North Star: Custody / Cluster Control Plane with Run Authority and WBC

## End State

The "derived-state-drift" failure class is mechanically impossible: custody
layers (watchdog, L1 repair, L2 meta-repair, L3 auditor, and status) never turn
cached or derived state into positive authority. One custody control plane
collects a coherent evidence snapshot, validates the current Run Authority
grant/coordinator fence and current Custody lease/custody epoch at the action
boundary, checks exact-version WBC evidence where declared, and emits only
rebuildable projections. Liveness is not success, a receipt is not a grant, and
a projection is not a lease. This initiative supersedes
canonical-run-state-control-plane, incident-control-plane,
superfixer-repair-custody, and tiered-repair-hardening.

The prevention extension closes the authority-and-efficiency incident class seen
in the Transaction Spine and Strategy Roadmap runs without pretending that all
latency is waste. Every accepted attempt and repair is exact-identity-bound,
immutable, fenced, quarantinable, and reducible from durable evidence; every
projection is rebuildable; event-driven recovery accepts or escalates 95% of
eligible blocked occurrences in under five minutes while the six-hour pass
remains a reconciliation backstop. Separately owned planner/compiler and
executor controls reject infeasible serial DAGs, oversized tasks, unbounded
startup/provider/compaction/rework loops, and model-backed mechanical
validation. A productive-versus-replayed work/token/cost ledger makes
legitimate implementation distinguishable from avoidable orchestration.

## Non-Negotiables

- The resolver is the single coherent evidence classifier used by status,
  watchdog, chain guards, L2, and L3. It can deny or diagnose; it cannot mint a
  grant, lease, completion, cancellation, publication, or delivery decision.
- Current source authority beats stale or derived state; evidence beats labels;
  liveness is not success. Terminal success requires a current Run Authority
  decision, current Custody lease/epoch, required WBC evidence, and independent
  verification where recovery is involved.
- The resolver gathers a READ-COHERENT snapshot (atomic/version-token), not 6 independent reads.
- Drift is EMITTED (`DRIFT_DETECTED`), never silently suppressed.
- The resolver + L2 are themselves audited by L3 (audit-the-auditor: L3 recursion guard + `auditor_escalate_to_human`).
- `manual_review` is never a dispatch policy; unknown fails safe.
- Run Authority is the only owner of grants, subject/coordinator attempts,
  accepted claims/decisions, coordinator fences, CAS/idempotency, and
  quarantine. Its reducer is pure; a serialized reducer view alone is not a
  bearer authorization. Run Authority is not the Custody lease service,
  TransitionWriter, repair queue, WBC ledger, planner, executor, or auditor.
- Custody is the only owner of exact action-target and repair-occurrence identity, renewable
  exclusive leases, custody epochs, transfer/reclaim/release/expiry, recovery,
  and reconciliation. Lease ownership grants exclusivity, not capability.
- WBC is the only owner of versioned boundary declarations, execution-attempt
  and external-effect evidence, provenance, receipts/findings,
  payload/reference policy, and WBC conformance. Its records never grant or
  lease authority.
- Every authoritative action requires both the current Run Authority grant and
  coordinator fence and the current Custody lease and custody epoch. Either
  stale half rejects; required WBC evidence is an additional boundary condition.
- Repair dispatch identity is an exact tuple over environment/session, chain,
  plan and revision, phase/task, attempt, normalized failure kind, blocker or
  phase-result digest, and current fence. A stale T7 occurrence cannot bind to
  T12 or to a same-basename run.
- Attempts and their evidence are append-only. A repair receipt may be adopted
  only through verify-only acceptance against the current grant, revision,
  task contract, commit/tree, tests, and fence; mismatch quarantines it and
  resumes normal execution without rewriting history.
- Recovery is event-driven and idempotent, with a measured p95 below five
  minutes from durable block/process-exit event to accepted repair or typed
  escalation. The periodic scan and six-hour auditor reconcile missed events;
  they are not the primary scheduler.
- Planning/execution efficiency policy stays domain-owned: semantic dependency
  reasons, critical-path and parallelism feasibility, complexity/task sizing,
  deterministic validation jobs, retry/rework/timeout/compaction ceilings, and
  executor circuit breakers do not move into the generic authority kernel.
- Completion requires content-addressed evidence, installed/runtime provenance,
  deterministic captured-run replay, canary and genuine blocked-run proof,
  generated call-site plus runtime-trace equality for every WBC boundary, zero
  legacy authority bypasses, and retirement/deletion evidence. Local tests,
  schema-only suites, nominal support manifests, manual assertions, or status
  labels cannot complete this epic.
- Source, seed, plan, runtime, and process identity are one launch invariant.
  The target checkout must descend from the exact final source revision; the
  chain, North Star, milestone briefs, decisions, incident amendment, and
  materialized plan snapshot are content-addressed inputs; interpreter, venv,
  imports, `direct_url`, every active `.pth`, wrappers, supervisor, resident,
  marker, and chain runtime binding must agree. Missing or ambiguous identity
  blocks before dispatch.
- Model-output contracts are producer/consumer contracts, not suggestions.
  Prompt, materialized schema, scratch, parser, handler, receipt, and replay use
  one strict schema hash. Required fields are never fabricated and unknown
  fields are never stripped into validity.
- Acceptance and liveness are target-bound reducer results. Receipt shape,
  activity, heartbeat, process presence, Git/PR/CI movement, stale review, or
  plan bookkeeping cannot project accepted progress, canonical advancement, or
  completion.

## Explicit Non-Goals

- Profile/model routing beyond closing the profile-pin-vs-tier residual (#2) — mostly fixed via `2f15007a`.
- Workspace restoration for deleted sessions (DETECT via `BROKEN_STATE_MACHINE`, don't recreate).
- Fixing main CI (DETECT red-main as base-health, don't fix).
- Real code/planner bugs (AWF242, test-selection) — the resolver reports, doesn't fix.
- Merging workflow-boundary-contracts (stays separate; consumed as resolver evidence).
- Treating all elapsed time or model cost as avoidable. Large code changes,
  required review, proof work, and intentional high-depth reasoning remain
  legitimate workload and are reported separately.
- Moving DAG semantics, model routing, task sizing, executor budgets, provider
  timeout policy, or deterministic validation into Run Authority.
- Claiming exact production projection-I/O cost, compaction time, or
  productive-versus-replayed baselines before M6/M8A/M9 instrumentation exists.

## Allowed Temporary Bridges

- `ARNOLD_RESOLVER_OBSERVE=1` / `ENFORCEMENT=0` feature flags during rollout (observe before enforce).
- Legacy derived-state fields kept during migration, with `stale_sources` surfacing disagreement.
- Bridge retirement completed on 2026-07-08: the 3 duplicate initiatives are superseded, merge-disabled, and retirement-logged.

## Drift Signals

- The resolver is bypassed at a call site (dispatch consumes raw labels).
- A known July-2026 incident shape isn't caught by a fixture.
- Drift is suppressed (not emitted) — operators lose visibility.
- L3 can't audit the resolver/L2 (no backstop for the backstop).
- The 3 duplicate initiatives get re-launched as separate chains.
- A repair request/claim/attempt omits the exact live failure signature or
  remains open after terminal acceptance, supersession, cancellation, or
  escalation.
- A mutable alias overwrites an earlier execute/review attempt, or repaired work
  is replayed despite a current verifiable receipt.
- A fully serial or high-complexity plan is admitted without explicit
  feasibility evidence, or validation-only work consumes a model call.
- Plan, chain, cloud, repair, and introspection disagree for the same reducer
  cursor, or an observer refreshes liveness.
- A WBC receipt/finding, Run Authority view, custody/status projection,
  process/heartbeat, or mutable sidecar is accepted as positive action authority.
- A WBC boundary is called supported without a durable pre-dispatch start,
  exactly one terminal/indeterminate outcome, generated call-site mapping, and
  captured runtime trace, or a required append failure is swallowed.
- A cross-host handoff permits overlapping custody epochs, or a reclaimed owner
  acts after transfer or expiry.
- Reports combine productive work with retry/replay/queue/compaction waste or
  emit an auditor reason without exact evidence IDs.

## Top-level Run Authority anchor

There is one Run Authority contract, one WBC contract family, and one Custody
contract across every supported pipeline surface. Run Authority owns grants,
subject attempts, accepted claims/decisions, coordinator fences, and quarantine.
WBC owns exact-version boundary declarations and durable transactional
execution-attempt/effect evidence. Custody owns action-target/repair-occurrence identity, renewable exclusive
leases/custody epochs, transfer, recovery, and reconciliation. They compose at
action boundaries; they are not competing ledgers, writers, resolvers, or
status systems.

Every authority-increasing writer is explicitly registered and double-fenced:
it validates current Run Authority capability/fence and current Custody
lease/epoch, then checks required WBC evidence. Every
reader validates the exact referenced workflow, contract, code/config, run,
attempt, and evidence version; there is no implicit-latest reinterpretation.
Mutable state, chain JSON, markers, process/tmux facts, logs, provider facts,
receipts, and status snapshots are evidence or rebuildable projections only.

The supported runtime and WBC adopters use the same contract identities and
failure semantics. Projection loss is recoverable by deterministic replay.
Retry, recovery, restart, publication, delivery, and other external effects are
idempotent or reconciled under current fences, reread authoritative state after
mutation, and cannot claim closure without independent verification.

Conformance evidence is machine-readable and content-addressed. Legacy bypasses
are shadowed, made fail-closed, and removed only after exact-version parity,
mixed-version/replay proof, zero authoritative readers/writers, rollback proof,
and the prerequisite ownership manifests all pass.

## Definitive migration extension

The resolver and custody work are necessary substrate, not the final authority
model. The deepest practical end state is one joinable causal history across
the owner-specific append-only Run Authority, WBC, lifecycle, and Custody
records—not one new omnibus ledger. Every record is bound to an exact
workflow/contract version, run and attempt identity, coordinator fence, custody
epoch where an owner is required, idempotency key, coherent evidence snapshot,
and causal parents. Mutable JSON, markers, process probes, logs, receipts,
status files, and provider facts are evidence or rebuildable projections only.

All supported writers must append through the fenced history API before an
effect or transition is considered accepted. All authority-increasing readers
must consume a version-matched reducer view, return `UNKNOWN` for incomplete or
incoherent evidence, and reread after mutation. Recovery closes only after an
independent verifier proves both blocker clearance and resumed authoritative
progress. Legacy bypasses fail closed, then are deleted behind machine-readable
conformance and zero-reader gates.

## Initiative lineage and residual epic

M1-M4 are completed historical foundation: resolver/read coherence, status and
dispatch integration, watchdog/repair verification, and auditor coverage. Their
briefs remain under `briefs/` as lineage and acceptance context; they are not
pending executable milestones.

Workflow Boundary Contracts owns the shared boundary declarations, durable
transactional attempt/effect evidence, payload/reference policy, findings, and
supported-runtime conformance. Read-only audit found the completed candidate's
ledger is schema-only and its declared support exceeds production producer
coverage, so this initiative must operationalize and adopt that owned contract
rather than treating its manifest as universal proof. Candidate
`cbe69337d6f469fd7ae12f1fd0a51007d93b5d70` is landed by audited merge
`24afce006b9ad20391ac7af10ef67ea0b1774f9f`; chain entry verifies that evidence
without pretending the invalid old four-milestone session completed the current
six-milestone corrective chain. M6 binds the exact landed/runtime vector rather
than guessing from topic branches or the working tree. M5 first reconciles the three currently rejected Run
Authority completion receipts and establishes zero-divergence completion plus
canonical retirement evidence. It may begin without already-accepted receipts
because producing them is its purpose. M6 inventories the exact landed revision;
M6A makes the WBC-owned store/API transactional; M7-M11 plus M8A then close the
pipeline-wide adoption gaps without changing prerequisite ownership,
decisions, lifecycle, or owned conformance work.

The July 14 latency synthesis extends, rather than replaces, this continuation.
M6-M11 retain their authority/custody sequence, with M6A inserted before Custody
writer implementation. M8A is genuinely separate:
semantic DAG feasibility, task complexity, deterministic validation, launcher
bounds, and executor circuit breakers are Megaplan domain policy and would make
M8 or M10 oversized if folded into them. The authoritative finding-to-control
map is `research/unified-authority-efficiency-prevention-20260714.md`.

No post-M5 milestone may be admitted until M5's exact current evidence contains
three accepted receipts, canonical verification with zero divergences, a
lifecycle-generated content-addressed manifest, and durable canonical Run
Authority retirement evidence. M6 additionally validates the exact
audited WBC merge ancestry and current support/runtime proof;
M6A and later implementation remain blocked until M6's ownership handoff and
the human approval record are accepted. Uncertainty, staleness, or hash mismatch
stops the serial chain.

Rollout is serial and evidence-gated: shadow evidence/telemetry; captured-plan
deterministic replays; an idle projection canary; planner/executor and repair/
worker canaries; controlled installed-runtime deployment; then one deliberately
eligible, genuine blocked-run recovery acceptance. Failed gates disable
promotion and effects while preserving append/reconciliation evidence. They
never restore a legacy writer, silently retry, or convert an unknown into green.

The earlier one-milestone post-WBC proposal remains lineage. M5-M11 plus M8A supersede it
as executable scope because the migration must independently prove controlled
writers, exact-version adoption, rebuildable projections, recovery/effect
safety, cross-system conformance, and evidence-gated legacy retirement.

The controlling closure amendment for the remaining milestones is
`decisions/m10-m11-structural-conformance-closure-20260723.md`. Its C01–C20
requirements are load-bearing seed material, not advisory incident notes.
