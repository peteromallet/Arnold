# M5 — 24-hour efficiency auditor and recommendation routing

## Outcome

Deliver a read-only daily auditor that quantifies systemic waste across completed and censored histories, clusters recurring symptoms into root-cause candidates, and routes deduplicated ticket proposals or initiative recommendations without repairing, rerouting, or reshaping active chains.

## Scope (about one sprint; no more than two weeks)

In scope: a fixed daily UTC offset after a closed six-hour watermark; catch-up and replay; cohort baselines using rolling median/MAD/p95/p99; censored duration analysis; gate/finalize/review dwell; equivalent stage failures and retry/revision loops; duplicate/no-progress calls; idle handoffs; expected-versus-resolved model/profile mismatch; recurring repair patterns; cost/token/time per accepted task/milestone and quality outcome; root-cause clustering; confidence/alternatives; avoidable-impact estimates; deduplicated ticket proposals; active-custody references; report hashes, coverage, corrections, and precision metrics.

Out of scope: claiming active repair; invoking retries/relaunch; editing profiles, budgets, plans, briefs, or chains; force-proceed; automatic ticket creation without policy; initiative prioritization without human authority; raw-total comparisons without an accepted-outcome denominator.

## Locked analytical policy

- Compare like cohorts by stage/profile/model/robustness/environment and classifier version. Use conservative static reporting until at least 30 completed samples from 5 distinct plans exist; require 100 samples from 10 plans before p99 or regression claims can drive ticket-priority recommendations.
- Flag dwell when above cohort p95 and either 2× median or the declared SLO. Preserve right-censored observations and known gates/backoff rather than treating them as completions or zeros.
- Cluster normalized problem signatures separately from operational occurrences. Suggested recurrence signal: 2 occurrences in 7 days or 3 in 30 days; ticket proposal still requires evidence coverage and confidence thresholds.
- Profile/model mismatch compares expected route, resolved route, and provider-reported actual model from dispatch/routing receipts.
- Regression compares time/tokens/cost per accepted outcome and quality delta, not raw totals. Thorough/extreme robustness and deliberate exploration are explicit covariates.
- Ticket dedupe key includes root-cause fingerprint, affected contract, classifier version, and open-ticket identity. A proposal is inert until ticket authority accepts it.

## Scheduling, custody, and overlap

- Consume only watermarks closed by the preceding six-hour pass; append corrections for late evidence.
- Schedule lease key: `(daily_efficiency, environment, scope, window_end)` with monotonic fence. Replay appends only absent analysis/proposal events.
- Parallel analysts may process independent problem families. One fenced synthesizer serializes cluster merge and proposal emission; ticket materialization and initiative prioritization remain canonical/human authority.
- If an occurrence has active repair custody, report its costs and recurrence context but do not claim it, change its policy, or open a competing repair. Never edit an active chain.

## WBC gate/finalize example

The daily auditor clusters the repeated `north_star_actions` gate-schema failures, counts equivalent calls/revisions and avoidable elapsed/cost, and correlates them with the later accepted gate. It separately measures the roughly 79/84/176-minute finalize-output-to-`finalize.json` publication gaps as censored handoff/dwell observations. It may propose a root fix for schema compatibility or publication custody only after evidence supports that root cause; it never restarts WBC, changes its profile, waives its gate, or edits its active chain.

## Open questions / human gates

Approve cohort dimensions and SLOs, authoritative cost source, retention, schedule offset/timezone, cluster-confidence and ticket-precision thresholds, ticket auto-materialization policy, ticket/initiative owner, and handling of sensitive prompt/provider evidence. Default is report-only proposals requiring human acceptance.

## Done criteria

- Golden/property tests cover censoring, late corrections, cohort cold start, legitimate high-depth work, configured backoff, duplicated calls, no-progress deltas, recurrence, model mismatch, overlap with active custody, replay, and ticket dedupe.
- Reports reproduce from immutable inputs, expose coverage/unknowns/denominators, and never mutate audited inputs or plan/chain truth.
- Adversarial tests prove the daily loop cannot obtain repair custody, invoke action, change routing/profile/budget, or edit active chain assets.
- Shadow evaluation reports precision/recall samples, analyst overhead, false-positive rate, recurrence yield, accepted-ticket rate, and estimated versus realized savings.
- Promotion from report-only proposals requires the explicit human ticket-policy gate; no launch or promotion is part of editorial preparation.

## Handoff

Produce a daily report schema, baseline snapshots, cluster/proposal events, deterministic replay fixtures, operator runbook, and a decision packet for ticket-policy approval. Long-term operations remain split: the six-hour loop owns occurrence recovery through canonical custody; the daily loop owns analysis and recommendations only.
