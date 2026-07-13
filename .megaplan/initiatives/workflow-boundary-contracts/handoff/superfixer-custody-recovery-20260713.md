# Superfixer custody recovery — 2026-07-13

## Scope and outcome

This investigation repaired the existing cloud session
`workflow-boundary-contracts-corrective-20260710`; it did not create a
replacement session or hand-advance plan or chain state. The original C1 plan
`c1-contract-reality-20260711-1433` is now `done`, the same chain has one
completed milestone, and it has advanced to the live S2 plan
`s2-contract-foundation-and-20260713-1544`.

## Chain of custody

- **Original target failure:** a valid PROCEED gate repeatedly emitted
  `north_star_actions`, but the strict gate schema rejected that top-level field
  as an additional property. The C1 chain log records the same deterministic
  schema error 34 times. The first L1 repair fixed that schema defect, but later
  repair runs did not revalidate the current phase/target before declaring
  partial liveness.
- **L0 watchdog/status:** the watchdog's manual-review machine-repairable branch
  dispatched L1 before loading request and blocker identity. It also returned
  before evaluating the L2 trigger. Status could report running from fresh
  sidecar activity even when the recorded active-step PID was dead.
- **L1 repair lifecycle:** request
  `7473fa422fea89a936d0be64f25468524f0d7d0e1c8632478f5dcfc6ec37860e`
  was accepted with a legacy empty failure kind/blocker identity. The launch
  therefore occurred outside formal claim/attempt custody, leaving the request
  truthfully at zero claims and zero attempts. A later review worker (PID
  `1412472`) died with the plan `executed`, the chain `blocked`, and an orphaned
  active step; L1 classified the stale state but did not clear that shape.
- **L2 meta-repair:** the early L0 return prevented `repair_exhausted` and
  repeated no-advance evidence from reaching `compute_meta_repair_trigger`, so
  no original meta-repair existed. The bounded retrigger with
  `l1_custody_failure` created meta-repair
  `928ad038-19fa-4c98-bc35-82b9683c08a1`, diagnosed the dead-step
  reconciliation defect, cleared the stale state, and exposed the next review
  defect without claiming terminal success.
- **L3 auditor:** incident audits were written to a workspace-local queue that
  no consumer owned. The auditor trampoline also placed the invoking checkout
  ahead of the deployed source and used an obsolete current-target call, so it
  could neither project custody nor deterministically escalate the broken L1/L2
  cycle.

The first broken custody layer was L1 dispatch/claim ownership. The first
higher layer that should have caught it was L2 trigger evaluation in the
watchdog; L3 independently failed to authorize a canonical escalation because
of queue and runtime-resolution drift.

## Permanent prevention

- L1 now requires request and blocker identity plus a real fenced claim. Missing
  identity records a bounded unclaimed failure and routes to L2; it is never
  relabeled human-required. All dispatch environment is loaded before L1 and
  pending L2 work is evaluated before another L1 launch.
- L1 reconciles an executed plan with a dead active-step PID and blocked chain,
  clearing the orphan and synchronizing chain state.
- L2 has a deterministic `l1_custody_failure` trigger and can repair L1 launch,
  implementation, and custody defects.
- L3 uses the canonical global queue and deployed source, resolves the live
  target with the current API, and projects accepted-unclaimed requests, retry
  and alert budgets, runner/active-step liveness, and L2 evidence. Typed human
  gates remain excluded; unknown or malformed evidence fails closed but stays
  visible.
- Status is process-authoritative when an active PID is recorded; sidecar
  freshness cannot turn a dead worker into `running`.
- A repair request whose explicit target plan has already advanced is
  terminalized as `stale`, without inventing a claim or attempt. Explicit target
  identity takes precedence over the legacy compatibility signature so genuine
  human-gate step names are preserved.

Relevant prevention commits include `598f6ce059`, `52c764ce45`, `c89c3d6516`,
`25b8181395`, `2165aa2f62`, and `5a522e4e7a`. The installed watchdog, repair,
meta-repair, auditor, and repair-trigger wrappers were synchronized to the
deployed source; source and installed hashes matched after deployment.

## Verification and live evidence

- Focused control-plane regressions: 346 passed across custody projection,
  watchdog, L1/L2 triggers, auditor, status, and stale-chain reconciliation.
- Review-handler regressions: 104 passed.
- Full progress-auditor file: 112 passed.
- Repair-trigger target advancement plus genuine-human-gate preservation:
  17 passed.
- C1's approved review reported 897 scoped review tests and 122 Run Authority /
  launch-safety tests passing. Its full-suite shadow backstop retained the same
  13 baseline collection failures with `newly_failing=[]`; no gate was weakened.
- The canonical retrigger reused the original marker/session and PID lineage.
  C1 reached `done`; chain `chain-06e4c6966e36.json` advanced to milestone index
  1 and created S2. The original chain PID `1854068` remained live with fresh S2
  gate activity through the post-fix audit. A later canonical watchdog refresh
  adopted the same session as PID `2009128` with runtime provenance at
  `cd3128fcd4`; S2 continued with a fresh live gate heartbeat rather than an
  orphaned sidecar.
- The legacy request was not backfilled. Decision
  `20260713T155826Z-183a2c54fe9a6b8af2591ad97dd7e7da521ce7d042fac5e566493b4468a2c2fe.json`
  marks it `stale` because the target advanced from C1 to S2.
- Post-fix L3 report `/workspace/audit-reports/20260713T155345Z-audit.json`
  resolves the live current target without projection error, reports
  `RUNNING`, `human_required=false`, no dead active step, no accepted-unclaimed
  current request, and `preserve_live_no_duplicate`. It also retains the
  historical incident and escalates the unreconciled external publication
  handoff instead of erasing the repair churn. The canonical publication step
  then appended incident event 457 (`github_sync.issue_published`) and opened
  GitHub issue 214 for `problem-3bc7a5eaa27e`.

## Remaining operational caveat

The fixes are pushed on `origin/editible-install` and the external publication
step completed, but problem `problem-3bc7a5eaa27e` intentionally remains open:
its projection has not yet linked the fix commits or appended terminal repair
verification. This does not block the live recovered chain, and no typed human
gate is active. The open issue and incident must be closed only after canonical
verification reconciles those commits; they must not be manually marked fixed.
