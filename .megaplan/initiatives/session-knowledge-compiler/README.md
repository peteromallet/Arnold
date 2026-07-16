# Durable Session Knowledge Compiler

Build an automatic, evidence-linked knowledge compiler for every managed agent
session. It records activity, reusable knowledge, paper-cut observations, and
improvement candidates without changing the outcome or latency contract of the
managed work itself. `NORTHSTAR.md` is the unchanged end-state authority.

## Current truth

This initiative is now an eleven-sprint Megaplan epic. Each sprint represents
approximately two weeks of skilled human engineering, including design,
implementation, tests, review, and its predecessor/successor handoff. The
canonical executable front door is `chain.yaml`, a symlink to the versioned
successor spec `chain-v2-20260716.yaml`; current briefs live only under
`briefs/`.

| Sprint | Theme | Human estimate | Required predecessor handoff |
|---|---|---:|---|
| M1 | Canonical capture, identity, and source-position contracts | ~2 weeks | Initiative evidence and current backend inventory |
| M2 | Durable cursors, jobs, leases, and trigger lifecycle | ~2 weeks | M1 capture-contract handoff |
| M3 | Four-record schemas, evidence references, and persistence | ~2 weeks | M2 checkpoint-commit handoff |
| M4 | Bounded direct-Pro extraction and atomic acceptance | ~2 weeks | M3 record-schema handoff |
| M5 | Rolling/final synthesis and append-only correction | ~2 weeks | M4 accepted-checkpoint handoff |
| M6 | Scoped search and five agent-facing controls | ~2 weeks | M5 synthesis/correction handoff |
| M7 | Promotion candidates, applicability, and review authority | ~2 weeks | M6 promotion-candidate handoff |
| M8 | Contradiction, supersession, invalidation, and revision-aware search | ~2 weeks | M7 promotion-governance handoff |
| M9 | Paper-cut consolidation, ranking, and ticket adapter | ~2 weeks | M8 governed-search handoff |
| M10 | Rollout controls, budgets, diagnostics, and rollback | ~2 weeks | M9 backlog-lineage handoff |
| M11 | Cross-backend conformance, failure hardening, and operator docs | ~2 weeks | M10 rollout-readiness handoff |

The original milestones were too broad for the two-week sizing contract. The
recorded estimates are M1 ~4 weeks, M2 ~4 weeks, M3 ~4 weeks, M4 ~4 weeks, and
M5 ~6 weeks, for approximately 22 weeks total. The resize preserves that total
outcome while separating durable dependency boundaries instead of creating
micro-milestones.

## Initialized M1 disposition

Historical chain `chain-c256f171485f` initialized plan
`m1-durable-capture-cursors-20260713-2045` on 2026-07-13. It was not
implemented and is not complete. Its brief was snapshotted at initialization,
so neither that plan nor its five-milestone chain is mutated or resumed by this
resize. The original spec and briefs are retained verbatim under
`archive/20260713-initialized-five-milestone/` and are superseded for future
execution only.

Any future run must start from root `chain.yaml`. Because that symlink resolves
to the new versioned spec path, the file-backed chain-state identity is fresh;
operators must not copy old chain state, resume `chain-c256f171485f`, or treat
its initialized M1 as predecessor completion. No chain was launched as part of
this planning update.

## Canonical asset index

- `NORTHSTAR.md` — durable outcome and load-bearing invariants; unchanged by
  the resize because the intended product boundary is unchanged.
- `chain.yaml` — canonical front door symlink for the successor chain.
- `chain-v2-20260716.yaml` — current eleven-milestone executable spec.
- `briefs/` — the eleven current self-contained milestone briefs.
- `notes/resize-20260716.md` — duration estimates, decomposition logic, rubric
  choices, and initialized-plan custody decision.
- `research/conversation-audit-20260713.md` — authoritative product discussion
  and provenance.
- `notes/megaplan-prep-20260713.md` — historical five-milestone prep record;
  superseded for sizing/profile choices but retained as provenance.
- `archive/20260713-initialized-five-milestone/README.md` — non-destructive
  index of the original snapshotted planning inputs.

## Product boundaries retained

- Roughly 100,000 newly persisted tokens and terminal states drive eligibility.
- Evidence remains primary; checkpoints are immutable, idempotent, and
  correction-friendly.
- Compiler failure is visible and retryable but harmless to primary-session
  completion and delivery.
- Activity, reusable knowledge, paper cuts, and improvement candidates remain
  distinct and carry observed/performed/inferred/proposed/unverified claim kind.
- Promotion is explicit, evidence-linked, repository/revision-aware, and
  contradiction-sensitive.
- Consolidation never deletes source observations, and bounded extraction uses
  canonical `hermes:deepseek:deepseek-v4-pro` through provider `direct`.

## Launch boundary

These are planning assets only. Product implementation, chain launch/resume,
deployment, push, remote PR merge, and restart remain unauthorized by this
update. `driver.auto_approve` remains `false` and failure/escalation stop the
successor chain.
