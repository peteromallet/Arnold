# Discord resident working reaction lifecycle

Implement and verify a durable Discord reaction lifecycle for inbound resident messages.

Desired behavior:

- Once an accepted inbound Discord message actually begins resident processing, add a clear working/in-progress reaction to that exact source message.
- Do not mark messages merely received but not yet processing as working.
- When the terminal user-visible reply is successfully delivered, remove the working reaction and add/preserve the existing completion checkmark reaction.
- On retryable failure, interrupted processing, or pending delivery, do not falsely show completion. Reconcile stale working reactions safely after restart/replay.
- Preserve immutable Discord provenance, idempotency, burst/coalescing semantics, reply targeting, and the resident-managed detached subagent lifecycle.
- Avoid duplicate reactions under replay, duplicate delivery, concurrent sweeps, or retries.
- Treat reaction updates as transport effects with durable intent/outcome or equivalent existing outbox/effect fencing; failures must be visible and retryable without blocking the actual reply.
- Keep Discord-specific behavior behind the transport adapter; do not contaminate the transport-neutral resident core unnecessarily.
- Inspect existing reaction/checkmark behavior and extend it rather than creating a parallel mechanism.
- Add focused tests for normal success, long-running work, restart/replay, duplicate events, reaction API failure, terminal delivery retry, burst messages, and non-Discord transports.
- Implement the change in the current repository, run proportionate tests, and report files/behavior/test evidence. Do not deploy or restart the live Discord resident unless explicitly authorized.

This request originated from a Discord inbound message. Preserve the automatically injected immutable delegation provenance; do not reconstruct or replace it.
