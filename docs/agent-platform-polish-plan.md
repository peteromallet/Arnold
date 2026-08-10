# Agent-Facing Platform Polish Plan

## Goal

Make megaplan/Arnold safe and predictable for autonomous agent consumers without
prematurely turning it into a broad generic SDK. The target is an explicit
machine-facing contract for the surfaces agents already use: CLI JSON responses,
plan state, chain state, status/progress output, event logs, recovery commands,
and completion evidence.

## Ticket

Tracked by ticket `01KT4NND8KG77GJY9K5QWBWPXT`: "Make megaplan a first-class
agent-facing platform contract".

## Current Strengths

- Characterization gates already pin core behavior with CLI snapshots and
  pipeline golden fixtures.
- Store contracts and typed store errors provide a real backend contract.
- `events.ndjson`, `trace`, `doctor`, and status/progress views already create
  an observability substrate.
- `CliError` already carries `code`, `valid_next`, `extra`, and `exit_code`.
- Canonical vocabulary and resolution-contract docs show the right discipline:
  one source of truth, explicit semantics, and grep-verifiable naming cleanup.

## Main Gap

The existing guarantees are scattered across tests, docs, handlers, state files,
and operator practice. An autonomous agent can drive megaplan, but it still has
to infer too much from human prose, implicit artifacts, stale cached claims, and
partially structured errors.

## Workstreams

1. Define the agent-facing command contract.
   - Document canonical JSON response shapes for `init`, `auto`, `chain`,
     `status`, `progress`, `trace`, `doctor`, failure, retry, and completion.
   - Specify required fields, optional fields, state transitions, exit codes,
     and artifact promises.
   - Treat human prose as presentation, not as the agent's source of truth.

2. Harden structured recoverability.
   - Extend consumer-visible errors with `phase`, `plan`, `recoverable`,
     `blocking_reason`, `valid_next`, and `suggested_commands` where applicable.
   - Map `DriverOutcomeStatus` values to a stable recovery taxonomy:
     recoverable, terminal, human-required, retryable, blocked, and stale-base.
   - Keep internal best-effort fallbacks lightweight; do not envelope every
     non-boundary exception.

3. Add orchestration goldens.
   - Add fixtures for chain failure/retry, blocked recovery, stale-base
     prevention, review-audit freshness, and status output for a stalled run.
   - Keep fixture updates gated by explicit rationale, matching the existing
     characterization policy.

4. Make live verification trustworthy.
   - Ensure review/audit gates read live state rather than stale cached claims.
   - Add or document checks for event-sequence gaps, base-branch freshness, and
     chain milestone provenance.
   - Prefer status/event evidence over reviewer narrative when determining
     whether a milestone is done.

5. Consolidate docs and naming around the contract.
   - Fold this into `m13-docs-naming-cleanup` where possible.
   - Update canonical vocabulary for agent-visible names and deliberate
     non-renames.
   - Add a short "what an agent can trust" guide covering state, events,
     command JSON, recovery, and known limitations.

## Non-Goals

- Do not build a large generic Python SDK before there is a clear second
  consumer.
- Do not make every internal fallback a formal public contract.
- Do not rename persisted state strings or command names unless a golden-backed
  migration proves compatibility.

## Suggested Execution Order

1. Write `docs/agent-facing-contract.md` from the current CLI/status/event
   behavior.
2. Add focused tests around existing JSON/error/status outputs.
3. Extend `CliError` rendering and status payloads with missing recovery fields.
4. Add chain/recovery/stale-freshness golden fixtures.
5. Finish docs/naming cleanup and update canonical vocabulary.

## Acceptance Criteria

- A new agent can determine valid next actions from structured output without
  parsing prose.
- A failed chain milestone records why it failed and how to recover in a
  machine-readable form.
- Golden tests catch regressions in command JSON, state transitions, and the
  core unattended-chain recovery paths.
- Documentation clearly distinguishes public agent-facing contracts from
  internal implementation details.
