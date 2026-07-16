# Plan Tightening Record — 2026-07-16

## Evidence reviewed

The revision used the authoritative resident conversation
`rconv_85a1c2bfd5f1`, including the original product-definition sequence
recorded in `research/conversation-audit-20260713.md`, the 2026-07-16 discovery,
resize, objection, and tightening follow-ups, `NORTHSTAR.md`, both prior chain
specifications, all 16 prior briefs, and every current research/note/archive
document. There is no initiative `decisions/` content. The current governing
request requires the whole original outcome with a materially smaller plan.

## Required scope ledger

The product requirements are: all managed sessions; exact append-only evidence
ranges; ~100,000-new-token and terminal triggers; atomic idempotent checkpoints;
harmless asynchronous failure; four separate evidence-linked record types;
explicit claim kinds; bounded exact direct-Pro extraction; rolling/final
synthesis; append-only correction; scoped evidence-aware search; five named
agent controls; explicit repository/revision-aware reviewed promotion;
contradiction/supersession/invalidation behavior; source-preserving paper-cut
consolidation and ticketing; backward-compatible storage; inherited access and
redaction; bounded/reversible operation; representative backend conformance;
and auditable end-to-end evidence. README `Scope coverage` is the canonical
row-by-row mapping to sprint and acceptance proof.

## Architecture and scheduling challenge

The 11-sprint resize was a mechanical decomposition of abstractions, not the
smallest delivery architecture. Identity types, cursor lifecycle, record
schemas, and extraction are one transaction and become useful only together;
they are now M1. Synthesis, correction, search, explicit controls, promotion,
and contradiction all operate on the same append-only lifecycle and scoped
query path; they are now M2. Consolidation, migration, controls, diagnostics,
backend proof, and documentation collectively establish operational readiness;
they are now M3.

The estimate is roughly six skilled-human engineering weeks across three
approximately two-week sprints, including implementation, tests, review, and
integration. It is deliberately an estimate, not a deadline or guarantee.
M2 is the uncertainty concentration; repository evidence may justify an
internal split during implementation, but not omission or false completion.

## Speculative machinery removed or deferred

- No new sidecar store, queue/lease service, event bus, promotion service,
  review authority, vector database, general RAG platform, or global ontology.
  Existing repository seams must be reused unless implementation evidence
  proves a narrow addition is necessary.
- Idle compilation remains disabled policy, as the original decision made it
  optional. Threshold and terminal compilation remain fully required.
- Search requires bounded scoped retrieval with evidence and lifecycle state,
  not a new semantic/vector platform.
- Conflict candidates may be deterministic and explainable; model-driven
  automatic adjudication and autonomous code action are not required.
- Broad enablement, deployment, restart, long soak, organization-wide ranking,
  and automatic backlog implementation occur only under future authority.

These deferrals remove machinery, not requested outcomes; the README coverage
matrix shows the retained acceptance path.

## Historical custody

The initialized five-milestone plan remains verbatim, incomplete, and
superseded under `archive/20260713-initialized-five-milestone/`. The later
11-sprint planning-only resize is preserved under
`archive/20260716-eleven-sprint-resize/`. Neither is marked complete or may be
resumed as current state. Root `chain.yaml` selects the fresh three-sprint
versioned specification.

## Boundary

Planning artifacts only. No chain/plan launch or resume, product implementation,
push, PR, deployment, service restart, or external mutation was performed.
