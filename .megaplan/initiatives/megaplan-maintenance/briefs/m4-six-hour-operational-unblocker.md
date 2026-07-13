# M4 — Six-hour operational unblocker

## Outcome

Deliver a deterministic six-hour operational loop that detects concrete loss of forward progress, joins or requests bounded repair through canonical custody, and independently verifies resumed progress. It never directly writes plan/chain truth.

## Scope (about one sprint; no more than two weeks)

In scope: a roughly six-hour schedule with jitter and persistent catch-up; half-open event-time windows; stored watermarks and late correction events; coherent observation intake; run/stage/profile/model/environment cohort context; cold-start static thresholds; false-positive suppressors; operational classifiers; occurrence dedupe; fenced request handoff; already-approved allowlisted retry/relaunch policies; exact-window report; immutable input/event lists and content hash; action/receipt reconciliation; audit-the-auditor controls; independent immediate/5m/1h/6h verification; shadow/report-only and canary runbooks.

Out of scope: changing profiles/budgets; force-proceed/waiver; destructive Git/provider actions; protected publication; new repair classes; daily root-cause clustering; editing active chain specs; enabling production autonomy in this milestone.

## Locked detection policy

- A stall is blocker-specific, not a status label. Require an expired stage policy, no valid in-flight model call/lease, no accepted-output/artifact/frontier delta, and confirmation in a second coherent observation.
- Gate/finalize/review intervention requires the declared SLO to expire and cohort evidence to agree; daily analysis may flag p95 outliers sooner but cannot act.
- Stage repetition is actionable after three equivalent failures, or two retry/revision cycles with the same input/error fingerprint and no material decision/artifact delta.
- No-progress calls require increasing time/cost without accepted decision, artifact digest, plan version, task frontier, or evidence-coverage improvement.
- Known backoff/fallback, fresh heartbeat with unmatched call start, declared long phase timeout, thorough/extreme robustness, active lease, external PR/human/quota gate, and improving quality suppress intervention while retaining censored metrics.
- Cold start uses conservative per-stage static SLOs and requires at least 30 completed comparable samples from at least 5 distinct plans before median/MAD/p95 can affect action. Below that threshold, adaptive output is report-only.

## Scheduling, leases, and replay

- Window: `[window_start, window_end)` in UTC event time. Persist the input watermark and allowed lateness; late evidence appends a correction referencing the prior report.
- Schedule lease key: `(six_hour, environment, scope, window_end)` with monotonic fence. Action idempotency key: `(schema, occurrence, action_type, policy_version, target)`.
- Replay rebuilds deterministic projections and appends only absent outputs. If the daily loop overlaps, it may reference custody but cannot claim it; the unblocker joins an existing request instead of duplicating repair.

## WBC gate/finalize example

For the observed WBC gate, repeated `north_star_actions` schema failures from roughly 15:30–15:36 UTC share one fingerprint. The loop may open one occurrence only while no accepted gate artifact exists, no authorized call/lease is live, and a second coherent observation confirms no progress. Once a passing gate is accepted around 15:43 and state/events advance around 15:45, it requests no new repair and schedules blocker-specific verification. A transient snapshot saying `repair_dispatched`, a live gate process, or no process is never sufficient alone.

Historical WBC finalize publication gaps of about 79, 84, and 176 minutes are censored operational observations. The unblocker acts only if the relevant finalize policy expires and no valid work/gate exists; otherwise it records them for M5 analysis.

## Open questions / human gates

Approve numeric stage SLOs, schedule timezone/offset, allowed lateness, minimum follow-up coverage, safe-action allowlist, canary session, false-intervention ceiling, promotion thresholds, and rollback/kill-switch owner before canary action. Shadow reporting may proceed without action authorization.

## Done criteria and handoff

- Golden/property timelines cover exact boundaries, skew, late/out-of-order/duplicate events, censoring, unmatched calls, long legitimate phases, human gates, overlap, crash/replay, and stale fences.
- Same immutable inputs reproduce the same hash and included event IDs; every metric exposes numerator, denominator, unknown count, and coverage.
- Zero unauthorized plan/chain mutations, duplicate repairs, or self-verifications; 100% action/receipt reconciliation in test/canary evidence.
- Shadow mode measures false-positive and missed-blocker rates. Canary requires demonstrated kill switch/rollback and explicit human approval; this milestone does not grant it.
- Handoff to M5: closed watermarks, operational occurrence history, censored durations, cost/outcome facts, and immutable report references suitable for read-only daily analysis.

## Players and authority

Observers, validators, per-run classifiers, and read-only investigators may run in parallel. A deterministic synthesizer emits one finding set. Canonical repair custody serializes request/claim/effects; TransitionWriter owns mutations; an independent verifier owns closure; human escalation authority owns all listed gates.
