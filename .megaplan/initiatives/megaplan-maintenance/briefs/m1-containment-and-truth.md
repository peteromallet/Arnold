# M1 — Containment and truthful control

## Outcome

Deliver a default-off containment release in which every automatic action has a factual durable receipt, one master mutation gate dominates every L1/L2/L3 path, missing evidence cannot become green, and model-backed maintenance dispatch proves the resolved `gpt-5.6-sol` identity.

## Scope (about one sprint; no more than two weeks)

In scope: audit backlog ranks 1–7; durable dispatch receipts; report mode derived from actual actions; the master-plus-path gate matrix; the production-signature current-target adapter; one explicit central repair queue root and stranded-request migration; enqueue-before-exit ordering; `provisional_liveness`; a closed repair-outcome enum; mandatory environment namespace; removal of production cwd fallback; resolved-model receipts; focused negative-control and end-to-end tests.

Out of scope: enabling production autonomy; coherent observation/ledger v2; replacing every direct state write; delayed verification; six-hour/daily analytics; arbitrary remote commands or deployment outside supported tooling.

## Locked decisions

- Mutation requires `master_enabled AND path_enabled`; master off is fail-closed while observation/reporting continue.
- Liveness never emits verified recovery.
- The central queue root is explicit and rejects plan directories.
- Missing/stale/cross-environment evidence is typed unknown.
- Runtime model truth comes from the dispatch receipt, not a profile name or intent.
- M1 preserves existing Run Authority and TransitionWriter custody; it introduces no new state writer.

## Open questions / human gates

None required to implement containment. Production enablement remains a later explicit gate.

## Done criteria and handoff

- Exhaustive tests prove master-off causes zero plan/state/source/commit/push mutation across L1/L2/L3 while reports still run.
- One lifecycle failure produces one central request and one valid claim; repeated identical detection does not duplicate it.
- Reports cannot claim report-only after any action starts; every started action reconciles to a receipt.
- Real-module adapter resolution succeeds and signature drift fails loudly.
- Live-but-blocked remains open; empty/stale evidence yields no green finding.
- Test/staging records cannot enter production aggregates.
- Automatic maintenance receipts prove the resolved model is exactly `gpt-5.6-sol`; conflicting pins fail visibly.
- Handoff to M2: a documented mutation/receipt/queue boundary plus passing contract tests that M2 can wrap with coherent observations without changing custody.

## Touchpoints and anti-scope

Expected touchpoints include repair request/contract/feature-flag modules, lifecycle/supervisor wrappers, current-target adapters, incident bridge/storage, and focused cloud/auditor tests. Preserve unrelated dirty work; do not redesign Run Authority, WBC, or active chain state.
