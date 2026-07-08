---
superseded_by: custody-control-plane
---

# North Star

Megaplan autonomous recovery has one coherent incident control plane.

Any watchdog, repairer, meta-repairer, six-hour auditor, chain runner, subagent, install sync step, GitHub sync step, or human operator can start from one incident brief and understand:

- what happened
- why it happened
- who noticed it
- which repair was attempted
- whether the repairer itself failed
- whether a repair-system fix was committed, installed, and retriggered
- whether the original work recovered
- whether the problem recurred after a claimed fix
- where the sessions, logs, commits, PRs, processes, and raw evidence live

## Durable Invariant

An incident is an event-sourced state machine.

Actors do not mutate hidden state. They append events. Current state, active claims, problem indexes, summaries, and GitHub updates are projections from the event stream.

## What Clean Means

- `events.jsonl` is append-only, atomically written, schema-versioned, and safe under concurrent watchdog/repairer/auditor activity.
- `incidents.json`, `problems.json`, summaries, and GitHub updates can be regenerated from events.
- `megaplan incident brief` is the canonical agent UX and validates evidence, claims, expectations, install freshness, recurrence, and missing provenance.
- Repair-system fixes are not considered shipped until the ledger proves commit, install sync, retrigger/relaunch, and original-condition recovery.
- Immediate repair, meta repair, and the six-hour auditor have distinct contracts and do not silently loop on the same attempt without new evidence.
- The six-hour auditor is a reconciler first: it audits broken expectations and hands off clearly instead of becoming an unbounded second control plane.
- Raw logs and transcripts are referenced by path/hash/session/artifact metadata. Committed summaries are small and redacted.
- GitHub is a publication and review sink, not the source of truth.

## Why This Matters

The current cloud recovery system can appear active while missing the reason a repairer did not repair, whether a meta-repairer ran, whether a source fix reached the active runtime, or whether stale state is being replayed as truth.

This initiative removes that class of failure by making every recovery step explicit, queryable, and tied back to evidence.
