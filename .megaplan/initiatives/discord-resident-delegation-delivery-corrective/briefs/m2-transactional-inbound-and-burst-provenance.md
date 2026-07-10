# M2 — Transactional Inbound Custody and Provenance-Safe Burst Coalescing

## Outcome

Route Discord ingress and burst construction through immutable message envelopes and crash-safe turn custody so every accepted message is replayable and every grouped request retains the correct origin/reply target.

## Scope

In scope: atomically persist acceptance, message provenance, turn membership, and replay/checkpoint state; define deterministic primary/request attribution for a burst; make coalescer input/output carry the ordered member envelope set; lease/claim inbound turns; replay incomplete work after interruption; preserve authorization/escalation behavior; add fault-injection and burst tests. Keep the sprint within roughly two human-weeks.

Out of scope: delegated execution fencing, terminal delivery outbox implementation, full legacy backfill, and production-wide rollout.

## Locked decisions

- M1 ledger and transition APIs are the authority.
- Burst grouping cannot mutate member provenance or derive reply targets from latest message/history/cursors.
- Acceptance and replayability cross one transaction boundary or an explicitly proven crash-safe equivalent.
- Repeated delivery of the same transport message converges on the same request/message record.

## Open questions for the plan

- What deterministic primary attribution rule best preserves current user expectations for multi-message bursts while keeping every member addressable?
- Where should the acceptance acknowledgement intent be created so it is causally atomic but M4 can own actual dispatch?
- How should expired claims be distinguished from actively executing turns without relying on PID liveness?

## Constraints

Maintain current Discord message/content retention policy. Do not persist credentials. Recovery must not require arbitrary shell commands. Preserve voice/transcription and escalation paths by carrying the same provenance envelope.

## Done criteria and acceptance evidence

- Kill-point tests cover before/after inbound persistence, burst membership commit, turn claim, profile invocation handoff, and checkpoint commit; restart yields zero lost accepted turns and no duplicate logical turns.
- Tests with two or more rapidly coalesced messages assert immutable provenance per member and exact deterministic primary attribution.
- Interleaved acknowledgement, later inbound message, DM/thread/channel variants, duplicate transport delivery, and reordered scheduling cannot retarget an earlier request.
- Replay is bounded, lease-aware, and observable; stale claim commits are rejected by fence/version.
- Existing focused resident runtime, Discord adapter, voice/transcription, and escalation tests remain green or receive explicit compatibility updates.

## Touchpoints

Expected areas: `resident/runtime.py`, `resident/coalescing.py`, `resident/discord.py`, inbound models/store, and resident adapter/runtime tests.

## Anti-scope

Do not implement outbound provider retries here beyond durable intent creation; do not rewrite unrelated scheduler or cloud supervision code.
