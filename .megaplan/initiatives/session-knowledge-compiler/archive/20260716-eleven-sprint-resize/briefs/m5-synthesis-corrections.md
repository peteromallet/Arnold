---
type: brief
slug: m5-synthesis-corrections
title: Rolling and Final Synthesis with Append-Only Correction
epic: session-knowledge-compiler
created_at: '2026-07-16T00:00:00+00:00'
---

# M5 — Rolling and Final Synthesis with Append-Only Correction

## Outcome

Turn accepted M4 checkpoints into versioned rolling and terminal syntheses and
append-only claim/synthesis corrections while preserving the exact evidence,
checkpoint versions, claim kinds, and supersession history used.

## In scope

- Materialize a new rolling synthesis from a bounded sequence of accepted
  checkpoints and a final synthesis only after terminal-range acceptance.
- Link every synthesis version to exact checkpoint/record versions and expose
  omitted/unverified gaps.
- Define correction, supersession, rationale, actor, target, and evidence records
  for individual claims and whole syntheses.
- Preserve all prior synthesis/correction versions and deterministic active-view
  resolution without rewriting M1–M4 evidence or records.
- Prevent prior synthesis errors from becoming self-validating evidence for later
  extraction; context remains derived and visibly typed.
- Enforce session/repository authorization and bounded generation/rebuild work.
- Add rebuild/idempotency behavior for duplicate terminal and correction events.
- Produce `docs/session-knowledge-compiler/handoffs/m5-synthesis-correction.md`.

## Out of scope

Search indexes/UX, agent tool registration, promotion acceptance, contradiction
governance, paper-cut consolidation, rollout, and source-evidence editing.

## Locked decisions

- Checkpoints stay immutable; rolling/final syntheses are versioned derivatives.
- Corrections supersede derived claims/syntheses only and never alter evidence.
- Terminal final synthesis waits for successful terminal-range compilation.
- Claim kind and verification state survive synthesis and correction.
- Historical versions remain retrievable and independently auditable.

## Open questions

- What bounded context window/reduction tree produces stable rolling synthesis?
- How should claim-level versus whole-synthesis corrections compose?
- What deterministic rule selects the active version under concurrent corrections?
- Which correction operations require stronger authorization or review?

## Constraints

- Append-only file/DB parity and idempotent rebuilds.
- No source mutation/destructive correction API.
- Bounded inputs/outputs/cost and permission scope no broader than source records.
- Preserve compatibility with sessions that have checkpoints but no synthesis.

## Done criteria

- Multiple checkpoints yield versioned rolling syntheses with exact lineage.
- Terminal acceptance yields one idempotent final synthesis below or above the
  threshold as appropriate.
- Tests cover claim and synthesis correction, concurrent/duplicate correction,
  active-view resolution, authorization denial, and complete history retrieval.
- Original evidence and superseded versions remain resolvable after correction.
- M5 handoff defines bounded enumeration/query primitives M6 must expose.

## Touchpoints

M3/M4 record and checkpoint APIs, Store event/version patterns, authorization,
bounded generation, serialization, and synthesis/correction/store tests.

## Anti-scope

Do not implement global memory, search UI, promotion, ticket creation, source
deletion, or inject the full knowledge corpus into every agent prompt.

## Predecessor handoff

Require reviewed `docs/session-knowledge-compiler/handoffs/m4-accepted-checkpoints.md`,
accepted-checkpoint enumeration, exact route provenance, and passing retry/
atomicity tests. Only accepted M4 outputs may enter synthesis.

## Plan sizing and rubric

Estimated duration: approximately two skilled-human weeks. Overall plan
difficulty: 5/5; profile `partnered-5`; robustness `thorough`; depth `high`;
directed prep enabled. A correction/synthesis design can look useful while
silently replacing history or laundering inference into fact.
