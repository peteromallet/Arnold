# Swarm Adjacent Surfaces

This note records the July 4, 2026 swarm findings and the judgment calls made
from them. It is input to the epic, not a requirement dump.

## Accepted Changes

- Split the core vocabulary into `BoundaryContract`, `BoundaryReceipt` /
  `BoundaryEvidence`, and `SemanticFinding`. A single contract class must not
  become a god abstraction.
- Run producer-side immediate verification before hardening the generic
  contract foundation. The repair path should be proved with the prep incident
  class first.
- Define cloud custody contracts before requiring repair/status/auditor to
  consume custody findings.
- Treat `state.json` as a projection. Boundary health should compare state,
  receipts, event journals, warrants, step IO, and current durable reality.
- Store finding evidence outside volatile prompt fields and make it compatible
  with existing store/warrant/capsule patterns where possible.
- Add a finding lifecycle: observed, queued, claimed, repairing, cleared,
  unchanged-after-repair, stale, suppressed, waived, human-required, escalated,
  terminal.
- Include human approval, waiver, manual override, blocked/unblocked, and resume
  as authority-bearing boundary families.

## Core Surfaces To Shape The Architecture

- Step IO envelopes and contract results: strongest substrate for typed inputs,
  outputs, provenance, freshness, authority, and evidence refs.
- Event journals/folds: strongest append-only evidence stream for boundary facts
  and contradictions.
- Transition evidence contracts: closest existing vocabulary for authority,
  evidence refs, decisions, and trust status.
- Store/warrant/capsule projections: closest existing durable evidence custody
  layer.
- Template registry and structured output modes: closest bridge from
  BoundaryTurn/template promotion to generic boundary contracts.
- Shared phase handlers and `_finish_step()`: main producer boundary for
  receipts, history, state deltas, canonical outputs, and `phase_result`.
- Cloud `repair_contract.py`: existing custody/outcome vocabulary that should be
  reconciled with semantic findings rather than replaced.

## High-Value Later Consumers

- Cloud status CLI: should render typed lifecycle, activity, semantic-health,
  repair, and custody fields without becoming source of truth.
- 6h progress auditor: should use deterministic gather reasons from findings and
  custody contracts.
- Chain completion and PR merge guards: should pin PR, SHA, CI, merge, and chain
  evidence before authority transitions.
- Execute/tiebreaker/reducer phases: richest side-effect and child/parent
  boundary surface, but too broad for the first cut.
- Native platform durable operations and AgentBox resources: valuable reference
  and later adoption target for cloud custody.
- Resident/scheduler/guardian loops: boundary-rich but not where this epic
  should pioneer the model.

## Rejected Or Deferred

- Do not build a huge generic semantic engine before shipping the prep guard.
- Do not create a second repair-custody model beside the existing cloud repair
  contract.
- Do not require every workflow to implement every boundary field immediately.
- Do not make status, auditor, or repair-loop decide ground truth independently.
- Do not expand early milestones to resident/scheduler, AgentBox, or every
  execute-side effect. Those are later consumers once the vocabulary is stable.
