# M4 — Exact six-hour feedback and controlled rollout

## Outcome

Rebuild the six-hour audit as a deterministic, read-only feedback product over typed evidence, then prepare a gated canary rollout without enabling it during this plan.

## In scope

- Exact event-time windows with clock-skew policy, out-of-order/late/duplicate handling, censored durations, and explicit unknowns.
- Required-source coverage, freshness, coherence, action/receipt reconciliation, and immutable input/content hashes.
- Read-only L3 findings routed to normal repair/ticket authority with causal IDs.
- Audit-the-auditor negative controls and external CI/engine evidence receipts.
- Thin wrappers over shared typed Python adapters where needed to eliminate duplicated policy/report assembly.
- Canary runbook for resolver enforcement, L1 mutation, promotion stages, rollback, kill switch, and weekly effectiveness review.
- Update active operator documentation and mark superseded contracts precisely.

## Out of scope

- Enabling production enforcement/autonomy or mutating audited state from L3.

## Done criteria

- Golden timelines prove exact boundary, late, duplicate, missing, censored, and out-of-order behavior.
- Recomputing from the same inputs yields the same report hash.
- Every green finding cites fresh evidence; every unknown names the missing source.
- L3 cannot modify audited state/input artifacts; routed findings retain causal identity.
- Canary plan requires zero unexplained mutation, zero liveness-only closure, 100% receipt reconciliation, zero projection lag/namespace contamination, and demonstrated kill switch/rollback.

## Gate requiring operator input

Set numeric SLO thresholds and minimum follow-up coverage for false completion, recurrence, latency, and promotion stages before any canary is launched.
