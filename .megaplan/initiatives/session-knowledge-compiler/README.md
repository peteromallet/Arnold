# Durable Session Knowledge Compiler

Build an automatic, evidence-linked knowledge compiler for every managed agent
session. It incrementally records what happened, reusable knowledge, paper-cut
observations, and improvement candidates without changing the outcome or
latency contract of the managed work itself.

## Concise user request and product intent

The user wants every managed agent/session to compile durable knowledge
automatically at roughly 100,000 newly persisted tokens and at terminal states.
The compiler must keep immutable evidence-linked checkpoints plus rolling/final
syntheses; separate activity, reusable knowledge, paper-cut observations, and
improvement candidates; label observed/performed/inferred/proposed/unverified
claims; promote project knowledge cautiously; preserve source observations
through backlog deduplication; and expose lightweight record, correction,
search, and promotion controls. Bounded extraction should use the same cheap
direct DeepSeek Pro semantics as partnered-5.

## Concise factual conversation/session record

The authoritative resident conversation shows the product emerging across the
user and assistant turns from `msg_af16e8600ccc` through `msg_534f83393205` on
2026-07-13. The delegated operator then searched that conversation, created
this five-milestone initiative, wrote its North Star, audit, prep record,
briefs, and chain, verified the exact
`partnered-5` direct-provider routing, and initialized chain
`chain-c256f171485f` with M1 plan
`m1-durable-capture-cursors-20260713-2045`. Resident completion message
`msg_3e70b98cfb87` independently records the prepared assets and initialization.
No product implementation was completed in that session: at
2026-07-13T21:07:18Z the plan remained `initialized`, with its original `prep`
worker dead/stale and no active lock. This factual record is deliberately
separate from the intended product behavior above.

## Initiative assets

- `NORTHSTAR.md` defines the durable product destination and invariants.
- `research/conversation-audit-20260713.md` records the authoritative product
  discussion and provenance used to prepare the epic.
- `notes/megaplan-prep-20260713.md` records sizing and run-dial choices.
- `briefs/m1.md` through `briefs/m5.md` are self-contained sprint briefs.
- `chain.yaml` is the executable five-milestone Megaplan chain.

## Prep record

This is an epic because persistence and scheduling, evidence compilation,
synthesis and UX, project promotion governance, and backlog consolidation are
separate architectural deliverables with sequential contracts. Each milestone
is scoped to no more than roughly two weeks of skilled engineering work.

Every milestone is overall plan difficulty 5/5 and uses `partnered-5/full`
with default depth. A locally plausible design could pass focused tests while
silently losing evidence, advancing an idempotency cursor incorrectly,
promoting stale claims, or erasing source observations during deduplication.
DeepSeek routing is explicitly `direct`; canonical Pro slots resolve to
`hermes:deepseek:deepseek-v4-pro`.

The pinned runtime has no configured `execution.auto_approve`. The chain is
therefore review-gated with `driver.auto_approve: false`; launch is authorized,
but destructive code execution still requires the harness approval checkpoint.
