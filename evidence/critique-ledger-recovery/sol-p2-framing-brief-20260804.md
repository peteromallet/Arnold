# Sol framing brief: P2 control-plane reliability plan

You are GPT-5.6 Sol at high reasoning. This is a read-only architecture and
planning review. Do not edit the repository, launch cloud commands, or change
the current critique session.

Do not use collaboration/delegation tools and do not perform a broad repository
search. Read only the four evidence documents listed below, reason from them,
and return the requested judgement directly.

## Goal

Design a P2 follow-up plan that solves the *category* of failures exposed by
the critique-ledger run across all Megaplan/cloud pipelines, not merely the
current VJ9 test. The plan must be implementable, testable, and sequenced so
the current critique session can be recovered separately without smuggling the
whole platform hardening effort into that recovery.

## Existing evidence to read

- `evidence/critique-ledger-recovery/sol-final-plan-20260804.md` — current
  recovery plan and shared control-plane workstreams.
- `evidence/critique-ledger-recovery/luna-synthesis-20260804.md` — six prior
  Luna audits of runtime, lease, evidence, lineage, provider, and observer
  paths.
- `evidence/critique-ledger-recovery/luna-vj9-review-20260804.md` — current
  adapter/test contract failure and source-lineage caveat.
- `evidence/critique-ledger-recovery/current-provider-preflight-20260804.md`
  — concrete cloud credential/bootstrap evidence.

## Required judgement

Take a firm position on:

1. The deepest unifying failure mechanism beneath the individual incidents.
2. What belongs in the immediate recovery plan versus a P2 follow-up.
3. The smallest coherent architecture that prevents recurrence across every
   pipeline entry point.
4. Which investigative lanes Luna explorers should audit next, and the exact
   question each lane must answer.
5. Which decisions are high-risk/human-gated and which can be automated.

## Return format (under 1600 words)

- One-paragraph diagnosis.
- P2 north star and explicit non-goals.
- Five-to-eight explorer lanes, each with: surfaces, failure hypothesis,
  evidence to collect, and a concrete acceptance test.
- Proposed P2 milestones, dependencies, parallelism, and hard gates.
- “Do now / P2 / later” boundary for the current critique run.
- What evidence the final Sol synthesis must require before declaring the P2
  plan complete.

Do not hand-wave “add logging” or “use retries”: identify the authoritative
record, custody boundary, state transition, and proof for each recommendation.
