# C3: Cloud Execution Custody And Consumers

## Outcome

Cloud execution boundary findings distinguish managed execution, unmanaged
liveness, dead/stale execution, provisional recovery, verified recovery,
blocked relaunch, human custody, and escalation by composing prerequisite-owned
views and verification records.

Watchdog, cloud status, repair, and the six-hour gather layer consume the same
typed facts without WBC introducing a competing custody or status model.
All supported Megaplan phase, reducer, suspension/resume/cancellation, and cloud
execution seams write the C2 ledger; shadow mode is a rollout stage, not a final
exemption.

## Entry Gate

C2 durable findings and mutation-disabled controls are green. Canonical
`RunnerView`, `MegaplanRecoveryView`, observation envelopes, repair-attempt and
verification contracts, status projection, and six-hour input contracts are
present at the versions pinned by C1/C2.

## Mutation Class

Global cloud consumers are shared, high-blast-radius surfaces. New findings and
rendering begin in shadow/observe-only mode across fixture sessions. Each
declared rollout scope advances automatically only after parity,
false-positive, and gate-matrix evidence passes. A failed gate remains disabled
and aborts the milestone with diagnostics; it does not request approval.

## Scope

IN:

- Migrate prep, plan/revise, critique/gate, tiebreaker/reducer, finalize,
  execute, feedback, review, and human suspension/resume/cancellation producers
  to ledger start and terminal/event writes. Retries create linked attempts;
  resumed work preserves checkpoint and predecessor lineage.
- Migrate parent/child/reducer fan-out and fan-in so each child attempt is
  independently ordered and parent aggregation references the exact accepted
  child results/verdicts. Child activity alone cannot complete the parent.
- Store or durably reference declared inputs, outputs/results, verdicts, state
  deltas, promoted artifacts, checkpoints, and model/provider effects according
  to C2 payload/reference and retention/security policy.
- Declare execution-custody boundary profiles over Run Authority runner and
  recovery views plus Maintenance observation/verification events.
- Represent expected session/supervisor/tmux identity, process PID/PGID/cmdline
  fingerprint, active-step invocation/worker identity, heartbeat freshness,
  install identity, retrigger receipt, and blocker fingerprint as evidence
  refs—not independent authority.
- Derive semantic findings for stale active-step worker, identity mismatch,
  orphan/unmanaged live process, dead managed session, hidden relaunch failure,
  repair success without restored custody, contradictory/incoherent evidence,
  and watchdog/status disagreement.
- Feed structured reasons into watchdog, repair context, cloud status, and the
  six-hour deterministic gather layer through their canonical APIs.
- Preserve separate operator fields for lifecycle/execution authority, runner
  liveness, publication, human gates, recovery custody, semantic health, and
  repairability. Status remains a projection.
- Use Maintenance's independent immediate/5m/1h/6h verification and reopen
  behavior; WBC contributes the boundary condition and clearance evaluator.
- Count findings by session, boundary, invocation, kind, repair domain, and
  occurrence without inventing a second occurrence budget.
- Route repeated unchanged findings to the prerequisite-owned escalation/meta
  path only after its policy threshold is met.

OUT:

- A new `custody_state` source of truth or universal lifecycle enum.
- Treating process/tmux/session existence as recovery or execution authority.
- Replacing status snapshot, repair contract, Run Authority views, or six-hour
  report schemas.
- Chain/PR publication boundary enforcement beyond consuming `PublicationView`.

## Locked Ownership

- `RunnerView` owns normalized runner observations; `MegaplanRecoveryView` owns
  recovery/custody policy.
- Maintenance owns attempt-to-verification custody, close/reopen, status truth
  semantics, auditor windows, and escalation budget.
- WBC owns the expected custody boundary profile and semantic mismatch finding.
- Status/watchdog/auditor consume facts; none independently decides authority.

## Compatibility Fixtures

- managed live session with matching invocation and fresh worker;
- live process without expected session custody;
- session present with dead or reused worker PID;
- stale active step with otherwise fresh artifacts;
- repair attempt that restores liveness but not expected custody;
- failed relaunch with structured reason;
- verified closure followed by regression/reopen;
- true human blocker with owner/deadline;
- watchdog/status disagreement and incoherent observation envelope.

## Required Acceptance Evidence

1. Every fixture yields the same custody/semantic reason across watchdog,
   status, repair context, and six-hour gather, allowing presentation-only
   differences.
2. Managed-running, unmanaged warning, provisional recovery, verified recovery,
   blocked relaunch, human custody, and escalation remain distinguishable.
3. Liveness-only and unknown/incoherent cases never close recovery or appear
   green.
4. Status clearly separates execution authority, liveness, publication, gates,
   recovery, semantic health, and repair state.
5. Mutation-gate matrices prove observe-only operation across every global
   consumer and zero dispatch when the master gate is off.
6. Delayed verification and reopen tests retain the original boundary/finding
   causal refs.
7. Shadow parity has explicit denominators and no unexplained state bucket
   before rollout mode advances.
8. The generated support-manifest diff shows 100% of C3-assigned Megaplan
   producers using the ledger with no best-effort writes or hash-only results;
   compatibility readers are read-only and time-bounded to C4/C5 removal.
9. Kill/retry/suspend/resume/cancel tests reconstruct exact attempt lineage and
   prove terminal persistence failure is visible consistently to runner view,
   status, watchdog, repair, and audit gather.

## Automatic Failure Conditions

Fail validation and abort through `stop_chain` if a consumer bypasses prerequisite views to classify raw process/JSON
evidence, if status becomes authority, if repair actors self-verify, if global
dispatch can bypass the master gate, or if equivalent facts produce conflicting
custody decisions across consumers. Also fail if any C3-assigned supported producer
can complete without a durable ledger terminal state or durable result ref.

These conditions are machine verdicts, not human rollout decisions.

## Likely Touchpoints

- Run Authority runner/recovery/publication views
- Maintenance observation, repair, verification, status, and audit contracts
- existing cloud watchdog/status/repair/auditor adapters
- custody and status compatibility fixtures/tests
