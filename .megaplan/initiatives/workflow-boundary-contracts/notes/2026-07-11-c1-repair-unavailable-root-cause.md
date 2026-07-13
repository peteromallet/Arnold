# C1 `repair_unavailable` Root Cause and Corrective Plan

Date: 2026-07-11
Canonical session: `workflow-boundary-contracts-corrective-20260710`
Plan: `c1-contract-reality-20260711-1433`

## Evidence-backed causal chain

1. C1 reached `critiqued`, but gate output repeatedly included the unsupported
   top-level property `north_star_actions`. The schema audit rejected the same
   otherwise-`PROCEED` result through attempt 34.
2. At 15:36:35Z the watchdog correctly classified this as a progress stall
   (`active_step.attempt=34>=10`) and at 15:36:36Z dispatched the bounded repair
   loop. The repair capability therefore existed; this was not a missing-binary
   or feature-disabled incident.
3. The repair loop retained a target snapshot and log tail from the gate loop.
   During repair, the canonical plan advanced: gate completed at 15:43:35Z,
   state transitioned to `gated` at 15:43:36Z, and finalize started at
   15:43:37Z. The finalize worker heartbeat stopped at 15:45:46Z and its PID
   later proved dead.
4. At 15:46:10Z the repair model nevertheless reported the older gate failure
   as current, said the session was still blocked at gate, and prescribed a
   gate-normalizer deployment. The persisted repair target still said
   `critiqued`, had no active heartbeat, and had an event cursor ending before
   the successful gate. Repair custody closed as `partial_liveness` even though
   the live target had changed to stale `gated/finalize`.
5. On the next watchdog classification, `kimi_dispatch_failed_previously`
   treated `partial_liveness` as non-retryable, cleared the dispatch marker, and
   returned “direct relaunch needed.” The stale-active-step caller discarded
   that return (`repair_unintended_stop ... || true; return 0`), emitted the
   umbrella status `repair_unavailable`, and never executed the advertised
   direct-relaunch fallback.

This is not a human gate, authority/fence denial, profile mismatch, or missing
repair capability. It combines a gate schema producer/consumer mismatch, stale
repair target verification, a swallowed fallback transition, and lossy reason
projection. The final visible stall is a dead finalize worker with durable state
still at `gated` and `recoverable_via` including `finalize` and `step`.

## One-time recovery result

Policy already authorized `finalize`, so it was invoked once against the pinned
editable runtime without starting a chain runner. The worker ran normally and
cleared the stale active step, then finalize correctly rejected the plan contract
with `missing_scoped_baseline_test_contract`: its scoped baseline referenced 11
deleted `tests/archive/...` paths and had no valid task-level pytest command or
mappable planned files. It emitted `finalize_revise_feedback.json` and routed to
`revise`; durable plan state is now `critiqued`, with no active phase and no human
gate. No second transition was attempted.

## Required corrective slices

1. **Gate loop circuit breaker and schema compatibility**
   - Normalize or version `north_star_actions` consistently at the gate producer
     and schema boundary.
   - Stop identical schema-audit retries after a small bounded count and publish
     the stable error fingerprint instead of spending 34 attempts.
   - Test an otherwise-valid `PROCEED` gate result containing the legacy field.

2. **Repair target revalidation**
   - Immediately before terminal classification, re-run `resolve_current_target`
     and compare plan state, active-step run id/PID, event cursor, and artifact
     fingerprint to the dispatch snapshot.
   - If any authority-bearing target field advanced, supersede the old diagnosis
     and classify the new target; never let old log tails overrule newer state and
     journal evidence.
   - Treat `partial_liveness`/`live_with_fresh_activity` as verification-required,
     not as recovered and not as an opaque non-retryable failure.

3. **Recovery fallback correctness**
   - Replace the boolean `repair_unhealthy_session` contract with a typed result:
     `running`, `dispatched`, `busy`, `direct_relaunch_required`,
     `capability_missing`, `claim_denied`, or `human_gate`.
   - In stale-active-step, progress-stall, phase-failure, and chain-health callers,
     route `direct_relaunch_required` into the canonical relaunch/resume path
     before returning. Add an end-to-end regression where a prior repair exits,
     the active worker PID is dead, and the next tick performs exactly one
     canonical recovery.

4. **Truthful reason and liveness projection**
   - Preserve the typed dispatch/fallback reason in watchdog report, status
     snapshot, repair data, and incident ledger. Reserve `repair_unavailable` for
     an actually absent/disabled capability.
   - Do not label a session `running` or `preserve_live` solely because a stale
     `active_step` exists or a chain-health observation timestamp is recent.
     Runner PID/tmux truth and plan progress time must remain separate.
   - Exclude observation commands and unrelated processes sharing the workspace
     from plan subprocess discovery. Match LLM start/end by transaction identity
     so a completed gate call cannot remain “in flight.” Add introspect/doctor
     self-observer and matched-LLM regression tests.

## Acceptance evidence

- Reproducer reaches `finalized` after one dead-finalize recovery without a
  duplicate chain or human action.
- Watchdog reports the actual typed repair/fallback reason and current target
  revision at every transition.
- A repair model cannot close custody using a snapshot older than the live plan
  state/event cursor.
- `introspect`, `doctor`, cloud status, watchdog, and repair custody agree on
  runner liveness and the state-machine next action.

Implementation should land from a clean checkout because the active Arnold
checkout already contains overlapping uncommitted watchdog, repair, liveness,
status, and test work.
