# M2 — Coherent evidence and transition authority

## Outcome

Introduce versioned operational contracts, a read-coherent `ObservationEnvelope`, occurrence-scoped identity, journal failure visibility, and a single TransitionWriter path for lifecycle mutation, initially in shadow/warn mode where enforcement risk remains.

## In scope

- Audit backlog ranks 9, 10, 12, and 14 plus the proposed v1/v2 schemas.
- Environment namespaces, causal IDs, content hashes, read versions, coherence retry/fail-closed behavior, dead-letter replay, and projection seq/digest freshness.
- Shadow comparison across watchdog, status, dispatch, chain guards, and L3.
- Preserve the `gpt-5.6-sol` runtime pin and receipt proof introduced in M1.

## Locked decisions

- Authority-boundary schemas use closed enums and reject unknown fields except explicit extension maps.
- An incoherent envelope cannot produce terminal or dispatchable state without a recorded fail-closed override.
- Repair actors propose transitions; TransitionWriter owns mutation and immutable transition events.
- Signature groups recurrences; occurrence ID controls dedupe and budget.

## Out of scope

- Production enforcement or autonomy promotion.
- Rebuilding the exact six-hour metrics product.

## Done criteria

- Fault-injected read tearing returns a coherent retry result or typed `INCOHERENT`, never mixed truth.
- Direct repair-state writes are detected and blocked/warned according to the declared rollout mode.
- Projection lag/digest mismatch is explicit and cannot support green status.
- Journal failure produces a replayable dead letter and alerting signal.
- Runtime model receipts remain exactly `gpt-5.6-sol` for automatic repair and six-hour checks.

