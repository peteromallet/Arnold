# M4 — Durable Acknowledgement and Terminal Reply Outbox

## Outcome

Deliver acknowledgements and terminal replies from a durable, retryable, fenced outbox tied to immutable request provenance, with explicit handling of provider success, retryable/permanent failure, and unknown outcomes.

## Scope

In scope: acknowledgement and terminal-reply intent creation; outbox claim/lease/fence; transport idempotency key and provider attempt/receipt records; retry/backoff/dead-letter policy; Discord reply-target routing from the immutable envelope; terminal result rendering; operator-visible recovery; compatibility projections to existing delivery fields/status. Keep the sprint within roughly two human-weeks.

Out of scope: changing Discord product copy beyond what durable templates require, adding new transports, or production cutover for all legacy records.

## Locked decisions

- Intent is committed with its causal lifecycle transition before any send.
- A send occurs only from a claimed outbox item with a current fence and stable idempotency key.
- Unknown provider outcomes remain `unknown/reconcile`, never falsely `sent` and never immediately resent without reconciliation policy.
- Reply target comes only from the immutable originating provenance envelope.

## Open questions for the plan

- What Discord API/provider evidence is available to reconcile timeout/unknown outcomes without duplicate visible messages?
- What retry budgets and dead-letter thresholds fit existing resident operating expectations?
- How should acknowledgement and terminal intents interact if execution finishes before acknowledgement delivery?

## Constraints

Retain non-secret delivery evidence and redact credentials/content according to existing policy. Recovery and retries must be deterministic under fake clock/provider tests. Preserve user-facing terminal summaries and exact reply semantics.

## Done criteria and acceptance evidence

- Restart tests prove unsent acknowledgement and terminal intents are retried without losing provenance.
- Provider matrix tests cover success, retryable failure, permanent failure, timeout/unknown, duplicate callback, process death before/after send, lease expiry, and stale sender completion.
- Burst/interleaving end-to-end tests prove both acknowledgement and terminal reply target the exact originating Discord message and cannot be retargeted by later messages/cursors.
- One logical request produces at most one visible acknowledgement and one visible terminal reply under all deterministic duplicate/restart scenarios supported by the provider contract; unavoidable unknowns are held for reconciliation and alerted.
- Delivery state, attempts, next retry, dead-letter reason, and causal request/execution are visible through the unified ledger/status projection.

## Touchpoints

Expected areas: Discord outbound adapter/service, resident completion sweep, lifecycle store/outbox worker, manifest/status projections, and outbound/launch tests.

## Anti-scope

Do not add arbitrary transport abstraction, silently swallow permanent failures, or use mutable conversation delivery cursors as authority.
