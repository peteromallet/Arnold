# Completion-delivery duplicate-run reconciliation — 2026-07-11

Two resident-managed repair runs were launched accidentally for the same operational problem:

- Authoritative: `subagent-20260711-105219-63bd54fe`
- Superseded: `subagent-20260711-105211-f3fb3bb7`

The authoritative run was selected because it had already established a concrete causal chain and passed 65 focused tests. The redundant run was still inspecting the same shared files and had not produced a result. Before its managed supervisor was interrupted, its completion outbox was fenced as `superseded` with `attempt_count=0`; the manifest then durably transitioned to `interrupted` through the supervisor's handled SIGTERM lifecycle. No process-group, resident-service, Megaplan-chain, or cloud-chain stop was used.

Useful findings retained from the redundant run:

- The live Discord resident had restarted at 10:42 UTC in `dev` mode.
- Operational completion delivery is guarded by a two-factor production boundary (production mode plus production bot role), so terminal delivery sweeps were skipped and recent completed outboxes remained pending with zero attempts.
- The three older records initially appeared to be a separate failed class, but deeper inspection found durable `delivered_at` timestamps and persisted provider message IDs for each. A later provenance migration had incorrectly downgraded them to `failed`. They were restored to truthful `delivered` state without resend; the original migration diagnostics remain preserved.
- Delivery truth must remain based on persisted provider message-ID evidence; mutable conversation cursors are not safe evidence for provenance recovery or redrive.

The redundant outbox's durable state history records `operator_reconciled_accidental_duplicate_before_provider_claim` and points to the authoritative run. This prevents an interruption notice or duplicate repair result from being sent for the superseded request.

Final verification:

- The authoritative run completed and its own outbox delivered once (`attempt_count=1`) with persisted provider message-ID evidence.
- The three recent zero-attempt terminal outboxes each delivered once after the guarded production/file-store restart.
- The three historically misclassified records were repaired from existing provider evidence with no provider call.
- Terminal delivery attention is zero: no terminal `pending`, `retry_pending`, `failed`, or `unknown` records remain. Pending outboxes belong only to live agents.
- The focused regression set passed 79 tests, covering startup discovery, exact reply targeting, stable retry/idempotency behavior, test-bot isolation, restart/store selection, migration safety, and truthful status accounting.

## Final lifecycle reconciliation

The apparent loop was a sequence of three separately requested resident launches, not an automatic worker relaunch or provider retry loop. The first duplicate repair was superseded before provider claim. The authoritative repair then completed and delivered once. The reconciliation operator also reached `completed` and its provider claim won a narrow race before a later reconciler could fence it, so its truthful one-attempt delivery remains recorded rather than being rewritten. No related managed repair worker remains active, and terminal delivery attention is zero. The only subsequently pending related outbox is the currently executing user-requested reconciliation turn, which will use the normal single final-delivery path.
