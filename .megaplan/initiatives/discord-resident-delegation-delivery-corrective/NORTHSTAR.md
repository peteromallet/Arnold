# North Star: Durable Discord Resident Delegation and Reply Delivery

## End state

A Discord message accepted by the resident enters a durable, replayable lifecycle whose identity and reply target never depend on mutable conversation cursors, process memory, burst ordering, or the latest message seen. Delegation and external effects are request-idempotent. Acknowledgements and terminal replies are durable outbox records. One delivery ledger and state machine explain custody, retries, recovery, and terminal disposition across the resident, delegated agent, and Discord adapter.

## Non-negotiable invariants

1. **Immutable per-message provenance.** Each accepted transport message receives a stable provenance envelope containing transport, guild/channel/thread or DM conversation identity, author identity, inbound message id, reply target, received timestamp, and correlation/request id. Burst coalescing may group work but may never replace, infer, or mutate the provenance of any member.
2. **Deterministic burst attribution.** A coalesced turn retains the ordered set of member envelopes and an explicit primary/request envelope selected by a documented deterministic rule. Every acknowledgement, delegated run, and terminal reply identifies the exact originating request/message; later burst members and conversation cursors cannot retarget it.
3. **Transactional inbound custody.** Acceptance, durable turn creation, provenance persistence, and the replay cursor/checkpoint cross a single transaction boundary or use an equivalent crash-safe protocol. After any restart, every accepted turn is either replayable or demonstrably terminal—never silently lost and never ambiguously owned.
4. **Request-id idempotency.** Reprocessing the same request id converges on one logical turn, one delegated execution, and one set of externally visible effects. Duplicate launches do not run the agent twice merely because the launcher was called twice.
5. **Side-effect fencing.** Launch, acknowledgement send, terminal send, and any other external mutation require durable intent plus a fencing/idempotency key. Stale workers and duplicate replays cannot repeat a committed effect; ambiguous provider outcomes remain recoverable without claiming success.
6. **Durable outbound custody.** Acknowledgements and terminal replies are outbox entries committed with their causal state transition, retried with bounded backoff, and retained with attempt and provider evidence until terminal delivery or an explicit operator-visible dead letter.
7. **Unified delivery truth.** One append-safe ledger/state machine is authoritative for inbound, launch, execution, acknowledgement, terminal reply, retry, and recovery state. Manifests and legacy fields may project from it during migration but cannot become competing authorities.
8. **Monotone, validated transitions.** State changes follow a declared transition table with causal references, timestamps, actor/fence identity, and compare-and-set/version checks. Terminal states cannot regress; recovery is an explicit transition, not silent field repair.
9. **Startup and continuous recovery.** Startup reconciliation runs before new work is accepted. Continuous sweeps reclaim expired leases, replay incomplete turns, reconcile ambiguous sends and executions, and expose stuck/dead-lettered work without duplicating effects.
10. **Backward-compatible migration.** Existing inbound records, `arnold-resident-agent-run-v1` manifests, request ids, Discord reply behavior, and readable legacy delivery fields continue to work through an explicit versioned dual-read/backfill/cutover/rollback sequence. No destructive migration is required to recover service.
11. **Evidence over timing.** Correctness is proven with deterministic fault injection and persisted ledger/outbox assertions, not sleeps or process-liveness guesses.
12. **Secret safety.** Provenance and observability carry non-secret identifiers only. Tokens, credentials, message content beyond existing retention policy, and arbitrary remote-shell access are excluded.

## Required acceptance evidence

- State-machine/schema documentation and executable transition validation.
- Transaction and replay tests that kill the process at every inbound custody boundary.
- Burst tests showing multiple messages, interleaved acknowledgements, and later arrivals cannot change any earlier message's reply target.
- Concurrent duplicate request/launch tests proving one logical execution and fenced external effects.
- Outbox tests covering success, retryable failure, permanent failure, timeout/unknown provider result, restart, and dead-letter/operator recovery.
- Startup and continuous reconciliation tests against seeded partial/legacy states.
- Migration fixtures and compatibility tests for old manifests/records plus rollback evidence.
- End-to-end Discord adapter tests proving the acknowledgement and terminal result reply to the intended originating message exactly once.
- Rollout evidence: feature flags, staged enablement/canary, rollback procedure, dashboards/metrics/log fields, and alerts for age, retries, duplicates prevented, ambiguous outcomes, dead letters, and recovery lag.

## Scope boundary

This epic corrects the resident lifecycle and its durable storage/adapter contracts. It does not redesign Discord UX, replace the resident with a parallel bot loop, broaden authorization, change unrelated Megaplan chain semantics, expose secrets, or use arbitrary remote shell commands.
