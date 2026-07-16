---
type: brief
slug: m1-capture-contracts
title: Canonical Capture, Identity, and Source-Position Contracts
epic: session-knowledge-compiler
created_at: '2026-07-16T00:00:00+00:00'
---

# M1 — Canonical Capture, Identity, and Source-Position Contracts

## Outcome

Deliver the provider-neutral data contract that identifies every managed
session and its append-only evidence, normalizes backend-specific positions,
and permits an exact immutable source range to be named without changing any
primary-session completion or delivery behavior.

## In scope

- Inventory transcript, tool-event, manifest, log, lifecycle, and usage sources
  for resident-managed and automatic-repair managed agents.
- Define versioned canonical session identity, evidence-source identity,
  source-position, half-open range, terminal-state, and token-observation types.
- Preserve native backend offsets; never equate byte, event, sequence, and token
  positions. Define stable ordering and ambiguity/error behavior.
- Persist exact token usage where available and tagged fallback observations
  where not, including counter reset, cache, retry, and multi-provider cases.
- Add compatible file/DB persistence and fixtures for existing records without
  compiler fields.
- Produce `docs/session-knowledge-compiler/handoffs/m1-capture-contract.md` with
  schema versions, invariants, backend mappings, and unresolved limitations.

## Out of scope

Durable cursors, queues, leases, threshold scheduling, extraction, derived
record schemas, synthesis, search, promotion, backlog work, and rollout.

## Locked decisions

- Raw transcripts, tool events, logs, manifests, files, commits, and tests
  remain primary evidence.
- Eligibility is ultimately based on roughly 100,000 newly persisted tokens and
  terminal states, but this sprint only supplies truthful observations.
- Ambiguous positions fail closed; primary session completion remains fail-open.
- Existing stores are extended rather than replaced by a sidecar authority.

## Open questions

- Which persisted source is authoritative for each managed backend?
- What fallback token observation is least misleading when exact usage is absent?
- Which retention, redaction, and authorization fields must be inherited?
- Can one ordering contract span every backend, or must capability flags remain?

## Constraints

- No hidden network dependency in contract tests and no credentials in fixtures.
- Preserve existing manifest/store compatibility and unrelated Run Authority.
- Contracts must be append-only, schema-versioned, and portable across file/DB.
- Do not compact or delete primary evidence.

## Done criteria

- Versioned identity/position/range/token schemas and migrations load old data.
- Tests cover duplicate IDs, out-of-order events, counter resets, missing usage,
  retry/cache tokens, terminal observations, and position ambiguity.
- Representative resident and repair sessions map to exact evidence ranges.
- The M1 handoff document is reviewed and names the exact API M2 must consume.

## Touchpoints

Investigate `managed_agent.py`, resident session/subagent/runtime stores, worker
usage capture, Store file/DB implementations and migrations, plus managed-agent,
resident, and store tests. Exact files are selected after directed prep.

## Anti-scope

Do not add a scheduler, LLM call, search system, generalized event bus, RAG
platform, transcript cleanup, or unrelated resident/storage refactor.

## Predecessor handoff

No implementation predecessor. Consume `NORTHSTAR.md`, the conversation audit,
the historical M1 brief as provenance only, and a fresh repository/backend
inventory. The historical initialized plan is not seed work and is not complete.

## Plan sizing and rubric

Estimated duration: approximately two skilled-human weeks. Overall plan
difficulty: 5/5; profile `partnered-5`; robustness `thorough`; depth `high`;
directed prep enabled. A flawed identity/range abstraction can pass local tests
while silently losing evidence in every downstream sprint, warranting maximum
planning quality and expanded critique.
