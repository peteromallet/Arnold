---
type: brief
slug: c2-evidence-compiler-records
title: Evidence Compiler and Four-Output Contract
epic: session-knowledge-compiler
created_at: '2026-07-13T20:36:41.553886+00:00'
---

# C2 — Evidence Compiler and Four-Output Contract

## Outcome

Build the bounded extraction compiler on C1's durable source-range contract.
For each eligible range it uses the cheap direct DeepSeek Pro route and emits
four separate, schema-validated, evidence-linked records: activity, reusable
knowledge, paper-cut observations, and improvement candidates.

## Source and prerequisite

The four-output and claim-kind decisions come from resident messages
`msg_63610d4bb911`, `msg_e7b43d46d642`, and `msg_5d47dbb7a366`, as audited in
`research/conversation-audit-20260713.md`. Require reviewed
`docs/session-knowledge-compiler/handoffs/c1-accepted-checkpoints.json` with
v3 evidence refs, compilation-unit ownership, source position, job,
idempotency, privacy, and atomic checkpoint contracts; do not invent a second
cursor, scheduler, lifecycle journal, or evidence owner.

## In scope

- Define versioned schemas and storage for:
  1. activity records (what actually happened),
  2. reusable knowledge,
  3. paper-cut source observations, and
  4. improvement candidates linked to one or more observations.
- Require each substantive claim to carry a claim kind: `observed`,
  `performed`, `inferred`, `proposed`, or `unverified`.
- Define durable evidence references into the C1 source range and relevant
  transcript/tool/log/manifest/file/commit/command/test evidence. Validation
  must reject missing, out-of-range, or structurally invalid references.
- Keep activity and knowledge distinct: activity records report this session's
  goals/actions/results; reusable knowledge records facts, techniques,
  constraints, or decisions that could apply later, with explicit applicability.
- Keep paper-cut observations immutable and descriptive. Improvement candidates
  are proposals and may link to observations, but cannot overwrite them.
- Invoke only the new persisted source segment plus the previous accepted
  synthesis/checkpoint context, within explicit size/cost/output bounds.
- Use the exact canonical Pro agent spec
  `hermes:deepseek:deepseek-v4-pro` through provider `direct`. Reuse the existing
  Hermes/worker structured-output seam and never silently fall back to another
  model/provider for semantic/schema/auth/context errors.
- Add prompt-injection-resistant evidence delimiters and structured output
  validation. Treat transcript content as evidence, not instructions.
- Atomically persist all required validated output records and mark the C1
  checkpoint successful. Malformed/partial extraction remains retryable and
  does not consume the range.
- Record model/profile/provider/schema/prompt generation and source-range
  provenance for reproducibility without storing credentials.

## Out of scope

- Mutable rolling/final synthesis and search UX (C3).
- Promotion into project-authoritative knowledge (C4).
- Cross-session dedup/prioritization (C5).
- Reclassifying raw source events or deleting evidence after extraction.

## Locked decisions

- DeepSeek Pro means `hermes:deepseek:deepseek-v4-pro`, provider `direct`, with
  the same canonical direct semantics used by partnered-5 Pro slots.
- All four outputs are separate durable records, even when a single source event
  supports more than one.
- `performed` requires action evidence; `proposed` is never rendered as done;
  `inferred` and `unverified` cannot be promoted as observed facts by wording.
- Source evidence remains primary; derived records may be corrected or
  superseded later but may not rewrite evidence.
- Extraction failure is harmless to the managed session and cannot advance C1's
  last-successful source position.

## Open questions for the planner

- What is the smallest schema that is expressive enough for evidence spans
  across transcripts, tool calls, manifests, files, commits, and tests?
- How should source content be chunked when one 100k range still exceeds the
  model's safe context after serialization?
- Which paper-cut categories should be stable enum values versus extensible
  tags? At minimum preserve discoverability, ambiguous contract, missing
  capability, reliability, performance/cost, and workaround evidence.
- Which validation failures are retryable with the same generation, and which
  require a new compiler/schema generation?
- How should authorized redacted views retain immutable source identity without
  leaking content across the G4 audience/retention policy?

## Constraints

- Do not guess provider/model identifiers. Tests and persisted checkpoint
  metadata must demonstrate the exact resolved direct spec.
- Never include secrets or unrestricted environment data in model input or
  stored provenance.
- Bound input, output, attempts, and cost per checkpoint; surface truncation and
  unverified gaps explicitly.
- Reuse existing worker result/error classification and fallback safety rules.
- Preserve C1 idempotency and atomicity under restart and duplicate invocation.

## Touchpoints

C1 handoff/schema and v3 evidence APIs;
`arnold_pipelines/megaplan/workers/hermes.py`, worker result and phase
classification modules, `profiles/partnered-5.toml`,
`profiles/policy.py`, managed-agent/session stores, schema/serialization modules,
and focused resident/store/worker tests.

## Measurable done criteria

- Versioned schemas enforce four record types, claim kinds, evidence references,
  source range, and compiler provenance.
- A representative direct Pro extraction persists all four outputs and records
  `hermes:deepseek:deepseek-v4-pro` plus provider `direct` in durable evidence.
- Tests reject a proposal phrased as performed, an inference lacking its kind,
  evidence outside the source range, malformed partial output, and transcript
  prompt injection.
- Retrying the same range produces one accepted checkpoint and no duplicate
  records; a failed validation leaves the cursor unchanged.
- Activity and reusable-knowledge fixtures demonstrate their different schemas
  and query semantics.
- `docs/session-knowledge-compiler/handoffs/c2-four-record-contract.json`
  records checkpoint enumeration, bounded prior-context input, four immutable
  output schemas, exact route/validation, and supersession refs and is reviewed
  for C3.

## Anti-scope

Do not build search UI, promotion approval, backlog ranking, or a general-purpose
document extraction framework. Do not replace raw evidence with a generated
summary.

## Estimate and run shape

Approximately two skilled-human weeks. Overall plan difficulty 5/5; profile
`partnered-5`; robustness `full`; depth `high`; directed prep. A plausible
extractor can silently turn an inference or proposal into durable fact or accept
the wrong evidence range while local schema tests pass.
