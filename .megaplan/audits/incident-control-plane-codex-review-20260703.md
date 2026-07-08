---
superseded_by: custody-control-plane
---

# Incident Control Plane Codex Review Synthesis

Date: 2026-07-03

Input plan: `.megaplan/audits/incident-control-plane-plan-20260703.md`

Inputs also included: `.megaplan/audits/incident-control-plane-deepseek-review-20260703.md`

Batch:

- Reviewers: 3 Codex subagents
- Reasoning: high
- Sandbox: read-only
- Result: 3 succeeded, 0 failed
- Raw local outputs: `/tmp/incident-plan-codex-review/*.out`

## Reviewer Lenses

1. Agent UX: whether all touch points between actors are covered and easy for agents to follow.
2. System abstraction: whether the whole design has a coherent center of gravity.
3. Data/log completeness: whether the data model can reconstruct why agents chose and did things.

## Overall Verdict

All three Codex reviewers agreed the core architecture is right: an append-only incident ledger, a load-bearing `brief` command, expected transitions, deadlines, and original-condition verification.

The main concern was not conceptual wrongness. The main concern was implicitness. The plan needed sharper contracts for:

- actor quickstarts
- claim lifecycle
- dispatch commands
- transition naming
- subagent authority
- install/runtime identity
- closure semantics
- decision provenance
- causal event links
- write-path redaction

## Plan Updates Applied

The plan now adds:

- Event-sourced invariant: incidents are state machines; actors append events; projections derive state.
- `dispatch` command examples.
- Claim lifecycle events: created, heartbeat, released, expired, overridden.
- Actor prompt envelope.
- Explicit subagent default: frozen brief, no mutation unless delegated.
- Actor Quickstart table.
- `schema_version`, causal event fields, `attempt_id`, and structured `links`.
- Canonical human-facing transition format: `<actor>.<type>`.
- `decision` object for repair/diagnosis events.
- `actions` object for commands/patches.
- Evidence provenance fields including source, capturer, timestamp, hash, size, redaction status, and availability.
- Identity domain separation for provider sessions, agent runs, terminal sessions, chain runs, workspaces, commits, GitHub artifacts, install targets, and raw logs.
- `system.integrity_repair` path for malformed ledgers/indexes/broken evidence.
- New event types for subagent completion and integrity repair.
- Six-hour auditor reframed as reconciler first, direct fixer second.
- Problem mutable fields derived from events.
- Redaction moved from sync-only to append/brief/commit/GitHub write paths.
- Brief query requirements for causal timelines, claims, attempts, shipped status, install freshness, unresolved expectations, recurrence, GitHub status, and raw-log refs.

## Remaining Implementation Judgment

The plan is now strong enough to guide implementation. The main risk during implementation is overbuilding the full schema before a minimal event helper and `brief` projection exist. The first slice should enforce the invariant and a small schema immediately, then broaden event types and projections as wrappers adopt it.
