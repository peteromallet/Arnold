# Systemic recovery decision contract fix — 2026-07-11

## Audit inputs

- `subagent-20260711-221130-7db46841`: WBC C1 was a deterministic repairable quality failure whose blocked writer omitted `latest_failure`; the accepted request therefore carried an empty `failure_kind` and was misclassified human-required before claim.
- `subagent-20260711-221301-c3639dcf`: 38/39 distinct historical repair escalations were `AMBIGUOUS_BLOCKER`, none were proven true blockers; generic manual-review, ambiguity, exhaustion, and stale markers were being collapsed into needs-human across independent consumers.

## Root fixes

- Review-cap exhaustion now persists `quality_gate_blocked` only when structured failing deterministic checks exist. It includes stable blocker IDs, exact check evidence, task IDs, artifact/history cursor, repairability, timestamp, and resume cursor. Unstructured blocks persist `review_quality_blocked_unknown` and do not auto-mutate.
- A shared decision vocabulary allowlists only structured approval, credential/account, destructive-action, product-decision, policy/legal, mandated verification, and explicit user-action gates. Quota, prose, ambiguity, generic blocked state, and retry exhaustion do not invent a human decision.
- Legacy and recovery-view dispatch route deterministic quality failures to one bounded L1 attempt; unknown/ambiguous evidence routes to `broken_superfixer`.
- Accepted request custody now projects request/claim/attempt counts, active and accepted-unclaimed IDs, evidence cursor, automatic-attempt budget, claim-retry budget, and alert state. Failed claim handoffs append at most three durable retries and one durable alert.
- Cloud status uses the same custody and dispatch classifier as watchdog and exposes the same counts/budget/cursor; the shared CLI/Discord resident formatter renders that projection directly. Newer typed recovery evidence supersedes older compatibility markers.
- Watchdog dispatch handles typed quality/execution blocks before any human path. L1 exhaustion/breaker outcomes are `repair_exhausted`/broken-superfixer and do not write needs-human or notify Discord. The six-hour auditor remains observational and no longer mints needs-human authority markers.

## Verification

- 245 focused existing/new tests passed across human blockers, repair contract, cloud status, review blocking, and the new systemic regression suite.
- 51 repair-trigger and canonical resolver tests passed.
- Focused watchdog deterministic manual-review dispatch passed.
- Auditor read-only escalation, repair exhaustion no-notification, shell syntax, Python compilation, and whitespace checks passed.
- A broader legacy sweep had 338 passes and 33 failures; 25+ are pre-existing branch fixture/wrapper drift (obsolete `enqueue_repair_request(marker_dir=...)`, missing historical wrapper strings/functions). Behavior-change expectations for unknown dispatch and quota were updated and pass.

## Residual risk

- Automatic repair is proven only for typed deterministic quality failures with complete current-target evidence and an accepted request. Unknown evidence fails closed and remains visible as broken-superfixer; it is not automatically repaired.
- A genuine typed human gate still requires current plan identity or authoritative proof. Old untyped markers remain compatibility artifacts but cannot assert human-required.
- Claim retry records bound and alert failed handoffs; they do not seize a live/stale foreign claim without the existing fenced reclaim checks.
- The branch contains unrelated pre-existing wrapper/test drift that should be reconciled separately before treating the entire historical watchdog suite as green.

Future failures equivalent to WBC C1 now persist the needed type/evidence, dispatch exactly one bounded L1 repair, remain visible if unclaimed, and do not notify a human. This does not promise recovery for ambiguous, destructive, credential/account, or product-decision cases.
