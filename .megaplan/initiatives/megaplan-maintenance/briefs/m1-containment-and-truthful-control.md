# M1 — Containment and truthful control

## Outcome

Ship the containment release described in the July 10 audit: every dispatched action has a factual durable receipt, one default-off master mutation gate covers L1/L2/L3 mutation, the L3 current-target adapter uses its production contract, all immediate repair requests join one central queue, liveness cannot close recovery, missing evidence is unknown, and test data cannot enter production journals.

## In scope

- Audit backlog ranks 1–7 and their focused integration tests.
- The lifecycle, supervisor, repair-trigger, meta-repair, progress-auditor, feature-flag, current-target, and incident-store seams implicated by those findings.
- Pin every model-backed automatic-repair dispatch and six-hour-auditor dispatch to `gpt-5.6-sol`; remove or reject stale/default model pins that could resolve another model.
- Record the actually resolved model in dispatch receipts and reports, and test that it is `gpt-5.6-sol`.

## Locked decisions

- One master autonomy gate AND a path-specific gate is required for mutation; master off is fail-closed and leaves observation/reporting available.
- Liveness is provisional only. It never emits verified recovery.
- The central queue root is explicit; plan directories are rejected as queue roots.
- Missing/stale evidence yields typed unknown, never green.
- Runtime model proof comes from the dispatch receipt, not comments, profile names, or environment intent.

## Out of scope

- Enabling autonomy in production.
- The coherent observation service, TransitionWriter enforcement, delayed verification, or full metric rebuild; those follow in later milestones.
- Arbitrary remote commands or deployment outside supported tooling.

## Done criteria

- The Phase 0 acceptance gate and test additions 1–4 and 10 from the audit pass.
- Exhaustive gate-matrix tests prove master-off prevents state/source/commit/push mutation across L1/L2/L3.
- Auto-repair and six-hour-auditor model-dispatch tests prove the resolved model is exactly `gpt-5.6-sol` and a conflicting stale pin fails visibly.
- Reports cannot claim report-only after any subprocess starts.

## Prep direction

Trace production adapters and wrapper subprocess boundaries using real modules. Identify concurrent changes before editing and preserve unrelated work.

