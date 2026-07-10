# M4 — Exact six-hour feedback product

## Outcome

Rebuild the six-hour audit as a deterministic, exact-window, read-only feedback product over typed evidence, with reproducible hashes, honest source coverage, negative controls, and actionable findings routed through normal repair/ticket authority.

## In scope

- Audit backlog ranks 8, 13, 15, and the relevant portion of 16.
- `AuditReport.v2`, atomic watchdog reports, exact time-window aggregation, censored durations, explicit denominators/unknowns, dispatch-receipt reconciliation, and audit-the-auditor controls.
- Thin wrappers around shared typed Python policy/report logic where feasible within the sprint.
- Pin the six-hour model-backed analysis/check-in agent to `gpt-5.6-sol`; record and validate the resolved model in the report receipt.

## Locked decisions

- L3 is read-only. It files findings or tickets; L1/L2/operator authority performs changes.
- Reports derive mode from receipts and cannot modify audited state or input artifacts.
- Same immutable inputs reproduce the same content hash.
- Every green finding cites fresh evidence; every unknown names the missing source.

## Out of scope

- Enabling L3 mutation.
- Advancing production autonomy percentages; that requires a separate human-approved rollout after evidence review.

## Done criteria

- Golden/property timelines cover boundaries, skew, duplicates, late/out-of-order events, missing evidence, and censored phases.
- Six-hour totals equal only included event IDs and expose numerator, denominator, unknown count, and coverage.
- L3 cannot mutate audited state or its inputs; routed findings preserve causal IDs.
- The six-hour agent receipt proves the resolved model is exactly `gpt-5.6-sol`; alternate or missing model resolution fails closed.
- Recomputed reports are content-hash identical.

