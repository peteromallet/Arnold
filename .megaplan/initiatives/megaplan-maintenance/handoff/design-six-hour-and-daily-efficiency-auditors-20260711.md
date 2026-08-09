# Task: Design complementary six-hour unblocker and daily efficiency auditors

Analyze and propose what it would take to implement two complementary durable Megaplan operator/auditor loops that write to the same canonical ledger:

1. A roughly six-hour operational unblocker focused on concrete forward progress: stalled tasks, blockers, broken harness behavior, missing evidence, safe repair actions, and verifying that work resumes.
2. A roughly 24-hour efficiency auditor focused on systemic waste: excessive time in gates/finalize/review, repeated model or stage failures, retry/revision loops, duplicate work, long idle handoffs, model/profile mismatch, escalating token/time/cost without improved outcomes, recurring repair patterns, and avoidable operator latency.

Think this through as an agent architecture and operating contract, grounded in the current Arnold/Megaplan repository and existing initiatives, especially `megaplan-maintenance`, its chain/briefs/notes, watchdog/progress-auditor machinery, plan state/events, chain state, resident/cloud snapshots, repair custody, Run Authority, Workflow Boundary Contracts, and any existing ledger/ticket mechanisms.

Deliver a concise but rigorous design covering:

- Clear division of responsibility between six-hour and 24-hour loops; prevent duplicate repair ownership or conflicting mutations.
- Canonical evidence inputs and authority order. Do not trust status labels alone.
- A shared append-only ledger/event schema: observation, fingerprint, time window, severity, confidence, affected run/plan/stage/model/attempt, evidence references, suspected cause, action, owner, lifecycle, recurrence links, cost/time impact, and resolution proof.
- Detection rules and baselines for gate dwell, stage repetition, failure/retry loops, no-progress model calls, repair recurrence, idle gaps, profile/model mismatch, and throughput/cost regressions. Explain how to avoid false positives for legitimate long-running work.
- Agent/player roles: observer, classifier, investigator, safe repairer, efficiency analyst, synthesizer/prioritizer, and human escalation authority. Say which can run in parallel and which require serialized authority.
- How the daily auditor should turn repeated symptoms into root-cause clusters, tickets or initiative recommendations without autonomously reshaping active chains.
- Safe actions each loop may take automatically versus actions requiring human approval.
- Scheduling, idempotency, leases/fencing, replay/restart behavior, deduplication, and overlap handling.
- Suggested changes to the existing `megaplan-maintenance` initiative: whether to extend current briefs/chain, add a future milestone, or create a separate initiative. Search/reuse existing initiative material; do not create a new initiative or edit planning assets in this read-only task.
- A staged implementation plan, acceptance tests, rollout metrics, and concrete examples using the current Workflow Boundary Contracts gate/finalize delay.
- Identify unknowns and explicit human decisions.

This is read-only architecture/research. Do not modify repository files, planning assets, tickets, todos, chain state, cloud state, git state, or launch any chain. Do not use arbitrary remote shell commands. Return findings only.
