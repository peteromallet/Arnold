# Locked Lifecycle Architecture Constraints

1. Preserve the existing `ResidentDiscordService` → `ResidentRuntime` → resident profile/delegated-agent path; introduce no parallel bot loop.
2. Use a versioned canonical lifecycle ledger with explicit transition validation, causal ids, record version, lease/fence token, and timestamps. Storage implementation may reuse the existing resident store, but it must offer the transaction/compare-and-set semantics required by the North Star.
3. Treat transport message id plus transport/conversation scope as immutable ingress identity. Assign a stable resident request id once and persist both before coalescing.
4. Represent coalescing as a grouping relationship over immutable message envelopes. Do not synthesize provenance from `last_*`, delivery cursors, history order, or the newest burst member.
5. Create durable outbox intents for acknowledgements and terminal replies. Transport sends occur only by claiming an intent with a fence; provider receipts/unknowns are recorded as attempts.
6. Make delegated execution uniqueness durable at request-id scope. A run manifest is a compatibility projection/evidence artifact, not the sole authority for whether execution may begin.
7. Use leases plus monotonically increasing fencing/version checks for workers. Expiry enables recovery but never authorizes a stale worker to commit.
8. Reconcile before accepting new work at startup, then continuously on a bounded cadence. Recovery must be safe to run concurrently and repeatedly.
9. Migrate via additive schema, dual-read/compatibility projections, backfill, monitored cutover, and reversible flagging. Do not delete legacy data in this epic.
10. Preserve current authorization and secret-redaction boundaries. Store only the non-secret provenance necessary to route and audit delivery.
