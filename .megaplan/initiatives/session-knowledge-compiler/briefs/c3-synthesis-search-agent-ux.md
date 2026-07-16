---
type: brief
slug: c3-synthesis-search-agent-ux
title: Synthesis, Corrections, Search, and Agent UX
epic: session-knowledge-compiler
created_at: '2026-07-13T20:36:41.554150+00:00'
---

# C3 — Synthesis, Corrections, Search, and Agent UX

## Outcome

Turn immutable C2 checkpoints into useful rolling and terminal run, session,
plan, milestone, chain, and workflow syntheses, searchable knowledge, and
lightweight agent controls while keeping automatic operation nearly invisible
and preserving complete lineage.

## Source and prerequisite

Resident message `msg_5d47dbb7a366` locks the near-invisible UX and the
activity-versus-knowledge distinction; `msg_63610d4bb911` locks immutable
checkpoints plus rolling/final synthesis and correction-friendly behavior.
Require reviewed C1 and
`docs/session-knowledge-compiler/handoffs/c2-four-record-contract.json` storage,
lineage, authorization, and evidence contracts.

## In scope

- Materialize a versioned rolling synthesis from accepted immutable checkpoints
  and create a terminal final synthesis after terminal eligibility has been
  successfully compiled. Both must link to the exact checkpoint versions used.
- Preserve older synthesis versions and express correction/supersession as
  append-only records. Never mutate evidence or pretend a corrected summary was
  the original extraction.
- Implement bounded search across session activity, reusable knowledge,
  observations, candidates, and synthesis versions. Results must include source
  session/range, claim kind, confidence/verification, applicability, and evidence
  links rather than returning decontextualized prose.
- Make compilation automatic at C1 boundaries with no prompt burden on agents.
- Add lightweight agent/tool surfaces with stable structured contracts:
  - `record-learning` adds agent-supplied reusable knowledge as a claimed record
    linked to current evidence and marked with its source/verification state.
  - `record-friction` adds a paper-cut observation without requiring a fix.
  - `correct-summary` appends a correction/supersession with rationale/evidence.
  - `search-session-knowledge` searches scoped derived records and returns
    evidence-aware results.
  - `propose-promotion` creates an explicit promotion candidate for C4 review;
    it never promotes directly.
- Integrate the surfaces into the appropriate resident/managed-agent tool
  registry and prompt/context guidance without flooding every prompt with the
  full knowledge corpus.
- Expose compiler/synthesis status and correction history through bounded,
  permission-consistent read surfaces.
- Build disposable hierarchical projections from agent run through attempt,
  phase/step, plan, milestone, epic/chain, and workflow. Preserve rejected,
  failed, retried, reworked, late, nested, concurrent, superseded, and gap
  inputs; active views select without deleting or conflating lifecycle,
  authority acceptance, and knowledge acceptance.

## Out of scope

- Accepting project-authoritative promotions (C4).
- Cross-session paper-cut dedup/ranking or automatic tickets (C5).
- A conversational memory system that injects all history into every turn.

## Locked decisions

- Immutable checkpoints coexist with rolling and final syntheses; a rolling
  view is derived and versioned, not a mutable replacement for history.
- Corrections supersede derived claims and syntheses only. Primary transcript
  and tool evidence is never rewritten.
- Automatic operation is default. Explicit controls add human/agent intent and
  correction, not mandatory bookkeeping.
- Search results preserve claim type and provenance; unverified and proposed
  records cannot be presented as confirmed knowledge.
- `propose-promotion` stops at a candidate boundary.

## Open questions for the planner

- Should the first surface be resident tools, a Megaplan/Arnold CLI namespace,
  managed-agent prompt affordances, or one shared service with adapters?
- Which indexing backend fits existing Store contracts and scale without a new
  operational dependency?
- How should corrections target individual claims versus an entire synthesis?
- What default search scope avoids cross-repository leakage while remaining
  useful for the current session/project?
- How much prior synthesis context should be passed to the next C2 extraction
  without allowing a prior error to become self-reinforcing?
- Which hierarchical active-view rules are deterministic, and which require
  explicit acceptance/correction evidence? Missing child/attempt evidence must
  remain a gap rather than disappearing.

## Constraints

- Enforce the same authorization, redaction, and repository/session scope as the
  source evidence.
- Search and tool use must be bounded and pagination-aware.
- No destructive edit API for checkpoints or source evidence.
- Explicit agent records must identify the submitting actor and remain
  unverified until evidence/review justifies stronger status.
- Preserve backward compatibility for managed agents that do not use the new
  explicit controls.

## Touchpoints

C1/C2 compiler and v3 lineage APIs; `resident/profile.py`,
`resident/tool_registry.py`, `resident/tool_schemas.py`, `resident/context_tree.py`, managed-agent prompt
construction in `resident/subagent.py`, relevant CLI registration, Store/index
modules, and resident context/tool/schema tests.

## Measurable done criteria

- Multiple checkpoints produce versioned rolling syntheses; terminal completion
  produces one final synthesis linked to all included checkpoint versions.
- Correction tests demonstrate append-only supersession of a claim and a
  synthesis while original evidence and versions remain retrievable.
- Search tests return evidence-aware, claim-kind-preserving results and enforce
  session/project scope and pagination.
- All five named surfaces have structured schema validation, authorization, and
  positive/negative tests.
- A managed session that uses none of the explicit controls still compiles and
  synthesizes automatically.
- Hierarchical replay tests rebuild equivalent run-to-workflow projections under
  retry/rework, nested/concurrent child, correction, late, superseded, rejected,
  and acceptance-change cases without silent omission.
- `docs/session-knowledge-compiler/handoffs/c3-synthesis-search-controls.json`
  records projection/correction/query/control and promotion-candidate APIs and is
  reviewed for C4.

## Anti-scope

Do not auto-promote, auto-create backlog items, inject the full corpus into every
agent prompt, or build a general chat-memory UI.

## Estimate and run shape

Approximately two skilled-human weeks. Overall plan difficulty 5/5; profile
`partnered-5`; robustness `full`; depth `high`; directed prep. Correction,
hierarchical synthesis, and scoped retrieval can create a mutable or leaking
parallel truth source even when point queries look correct.
