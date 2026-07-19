---
type: brief
slug: m6-search-agent-ux
title: Scoped Search and Five Agent-Facing Controls
epic: session-knowledge-compiler
created_at: '2026-07-16T00:00:00+00:00'
---

# M6 — Scoped Search and Five Agent-Facing Controls

## Outcome

Expose bounded, authorization-aware session-knowledge search and stable
structured controls for recording learning/friction, correcting summaries,
searching, and proposing promotion while keeping automatic compilation the
default and preserving M1–M5 lineage.

## In scope

- Implement paginated search across activity, reusable knowledge, observations,
  candidates, synthesis versions, corrections, and active/superseded views.
- Return session/range, claim kind, verification/confidence, applicability,
  evidence, correction lineage, and scope with every result.
- Enforce repository/session/actor authorization, safe default scope, and
  cross-repository leakage tests.
- Add stable structured surfaces: `record-learning`, `record-friction`,
  `correct-summary`, `search-session-knowledge`, and `propose-promotion`.
- Mark agent-supplied records with actor/source/verification; never upgrade their
  authority merely because an agent submitted them.
- Make `propose-promotion` emit a candidate only and stop before acceptance.
- Register appropriate resident/managed-agent adapters and concise prompt/tool
  guidance without injecting the full corpus.
- Produce `docs/session-knowledge-compiler/handoffs/m6-search-tools.md`.

## Out of scope

Promotion review/acceptance, contradiction adjudication, backlog consolidation,
automatic ticket creation, broad rollout, and conversational memory UI.

## Locked decisions

- Automatic operation requires no manual bookkeeping; tools add intent.
- Search never strips claim kind, evidence, verification, applicability, or
  correction state from results.
- Unverified/proposed content is not presented as confirmed knowledge.
- `propose-promotion` cannot self-promote.
- Source authorization bounds derived-record visibility.

## Open questions

- Which shared service and adapters best fit resident, CLI, and managed agents?
- Which existing index/query substrate suffices without new operations burden?
- What default scope is useful without leaking across repositories/worktrees?
- How should stale/superseded results be ranked and visibly labeled?

## Constraints

- Structured schema validation, pagination, cost/result limits, and explicit
  authorization on every surface.
- Backward compatibility for agents that never call the tools.
- No destructive update to checkpoints, source evidence, or prior synthesis.
- File/DB parity and no new unbounded/global index.

## Done criteria

- Search returns evidence-aware, claim-preserving results and enforces scope,
  authorization, pagination, active/superseded filters, and bounded results.
- All five surfaces have positive, negative, schema, actor, and authorization tests.
- A session using no explicit control still compiles/synthesizes automatically.
- Prompt/context tests prove the corpus is not bulk-injected.
- M6 handoff specifies the complete promotion-candidate API M7 consumes.

## Touchpoints

M5 query APIs, resident tool registry/schemas/profile/context/prompt paths,
managed-agent adapters, CLI registration where appropriate, Store queries/index,
authorization, and resident/tool/search tests.

## Anti-scope

Do not accept promotions, auto-create tickets, build a chat-memory product,
inject all history, broaden authorization, or add unrelated resident tools.

## Predecessor handoff

Require reviewed `docs/session-knowledge-compiler/handoffs/m5-synthesis-correction.md`,
landed active/history query primitives, and passing correction/idempotency tests.
M6 exposes those semantics; it does not create a parallel store.

## Plan sizing and rubric

Estimated duration: approximately two skilled-human weeks. Overall plan
difficulty: 4/5; profile `partnered-4`; robustness `full`; depth `high`;
directed prep enabled. The data contract is settled, but authorization,
pagination, tool registration, and prompt integration cross several subsystems.
