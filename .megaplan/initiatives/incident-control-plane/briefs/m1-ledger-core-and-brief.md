---
superseded_by: custody-control-plane
---

# M1: Ledger Core And Incident Brief

## Outcome

Megaplan has a minimal incident-ledger core and a read-only `megaplan incident brief` projection that agents can trust before any repairer integration depends on it.

## Design Inputs

- `.megaplan/audits/incident-control-plane-plan-20260703.md`
- `.megaplan/audits/incident-control-plane-deepseek-review-20260703.md`
- `.megaplan/audits/incident-control-plane-codex-review-20260703.md`

## Scope

In:

- Add a schema-versioned event model for the minimum useful incident ledger.
- Add an append helper that writes JSONL atomically and preserves immutability.
- Add event validation for required identity, actor/type, scope, outcome, evidence refs, `next_expected_event`, deadline, and causal fields.
- Add claim, attempt, action, decision, and evidence-ref shapes at least as validation/projection-ready data.
- Add derived incident and problem projections that can be rebuilt from `events.jsonl`.
- Add `megaplan incident list --active` and `megaplan incident brief <id-or-session>`.
- Make `brief` show current state, next expected event, deadline, active/expired claims, missing evidence, attempts, shipped-fix status, install freshness placeholders, recurrence placeholders, and raw evidence refs.
- Add integrity detection for schema failures, missing refs, and index divergence. The first implementation can recommend `system.integrity_repair` without implementing full repair.
- Add redaction and size gates on event summaries and committed projection output.
- Add focused tests for append-only behavior, projection rebuild, brief output, missing evidence, stale/expired claims, redaction rejection, and malformed event handling.

Out:

- Do not wire watchdog/repairer/auditor wrappers yet except where needed for tests.
- Do not implement GitHub publication yet.
- Do not require complete cloud runtime sync in this milestone.
- Do not persist huge raw logs in git.

## Locked Decisions

- Canonical CLI namespace is `megaplan incident ...`.
- Source of truth is the append-only event log in the active workspace.
- Derived indexes and summaries are projections, not truth.
- Human-facing transitions use `<actor>.<type>`.
- GitHub is not canonical.

## Open Questions For Planner

- Best internal module placement for the incident ledger helper and CLI commands.
- Exact minimum schema that can be enforced now without blocking later fields.
- Whether projection files live under `.megaplan/incident-ledger/` only or also expose summaries elsewhere.
- How to represent evidence refs in tests without depending on cloud-only paths.

## Done Criteria

- `megaplan incident list --active` works against fixture and local test ledgers.
- `megaplan incident brief <id-or-session>` produces a coherent, bounded, redacted summary.
- Projections rebuild deterministically from `events.jsonl`.
- Missing refs, schema failures, stale claims, and index divergence are visible in brief output.
- Tests cover concurrent/atomic append behavior to the degree feasible locally.
- Existing megaplan tests still pass for impacted CLI/state modules.
