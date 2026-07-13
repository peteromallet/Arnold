# Implement the resident restart transaction corrective

Implement and verify the systemic fix described by the inbound Discord request. Work in `/workspace/arnold` and preserve unrelated dirty work.

Required outcomes:

1. Move restart completion supervision outside the dying Discord resident process. The replacement process/supervisor must verify process identity changed, finalize the durable restart record, and deliver the terminal confirmation.
2. On startup, reconcile stranded `prepared` restart records safely and idempotently.
3. Emit a durable immediate “restart accepted” acknowledgment before shutdown.
4. Remove synchronous cloud/repair projection rebuilding from the Discord event loop. Prefer the precomputed snapshot, bounded timeout/fallback behavior, and background refresh.
5. Requeue restart-interrupted inbound turns promptly and idempotently instead of waiting 30 minutes and abandoning them. Preserve exact Discord reply provenance and prevent duplicate execution/delivery.
6. Fence overlapping restart requests so at most one restart transaction is active.
7. Persist restart initiator/provenance and expose enough evidence to diagnose the lifecycle.

Investigate the existing implementation and tests first; integrate with the canonical `agentbox services restart agentbox-discord-resident` safety boundary. Never use pkill, killall, cgroup-wide stop, or tmux cleanup. Do not run arbitrary remote shell commands.

Add focused regression tests for prepared-record reconciliation, external finalization, acknowledgment ordering, duplicate restart fencing, interrupted-turn replay, exact-message delivery idempotency, event-loop-safe hot-context loading, and restart provenance. Run proportionate focused and broader resident tests. Implement the fix, not merely a report. Commit only if that is already normal and safe for this delegated workflow; do not push or restart the live resident unless the task's existing authorization and safety contract explicitly permits it. Report remaining deployment steps honestly.
