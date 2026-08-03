# a03-s09-retry-effect-budgets-notification-escalation: retry-effect-budgets × notification-escalation

## Verdict

Nonconformant, with reachable P0 authority-mutation paths.

`IncidentNotificationStore` plus `EffectProtocol` is the intended canonical foundation, but no single durable occurrence-wide budget currently covers diagnostic retries, delegated verification, provider attempts, repair, and user notification. Multiple callers maintain independent counters or bypass the canonical outbox entirely.

The most severe issue is that provider failures can fall through to direct delivery, including after an ambiguous provider outcome. This permits duplicate external notifications outside the durable budget and idempotency protocol.

## Intended canonical contract

The repository’s contract requires every external effect to have one durable write-before-call record, stable idempotency identity, provider reconciliation, and no blind redispatch after ambiguity: `arnold/workflow/effect_protocol.py:140-153`, `arnold/workflow/effect_protocol.py:430-468`.

The transactional outbox is intended to commit the event and outbox row atomically, deduplicate by idempotency key, and avoid duplicate outbox entries: `arnold/workflow/ledger_outbox.py:339-360`, `arnold/workflow/ledger_outbox.py:376-435`, `arnold/workflow/ledger_outbox.py:468-555`.

The canonical incident path is `IncidentNotificationStore`, whose SQLite records cover occurrences, provider attempts, and authority transitions: `arnold_pipelines/megaplan/cloud/incident_notification.py:44-79`. Its module contract says the watchdog admits only stable occurrence/outbox intent and that the incident card is a projection, not authority: `arnold_pipelines/megaplan/cloud/incident_notification.py:1-13`.

There is no canonical retry/effect budget implementation. `BudgetAuthority` tracks cost spend by lease and fencing token, not retry, delegation, notification, or occurrence budgets: `arnold_pipelines/megaplan/runtime/budget_authority.py:1-35`, `arnold_pipelines/megaplan/runtime/budget_authority.py:95-163`.

## Evidence and complete path inventory

I searched repository-wide with `rg --files` and `rg -n` over `arnold`, `arnold_pipelines`, `agentbox`, `tests`, `docs`, and `.megaplan`, targeting `IncidentNotificationStore`, `EffectProtocol`, `LedgerOutbox`, `outbound.send`, `send_discord_dm`, `DeliveryEffects`, `create_message`, `occurrence`, `escalation`, `authority_transition`, provider receipt, retry, and budget symbols. I then inspected callers and tests line-by-line.

The relevant inventory is:

- Canonical incident writers: `IncidentNotificationStore.admit`, diagnostic-terminal recording, provider-attempt recording, provider receipts, authority transitions, and card projection: `arnold_pipelines/megaplan/cloud/incident_notification.py:170-307`, `:309-365`, `:367-463`, `:465-565`.
- Canonical callers: watchdog human-review notification calls the diagnostic launcher, which calls `custody.admit`: `arnold_pipelines/megaplan/cloud/wrappers/arnold-watchdog:981-1027`, `:1135-1152`; `arnold_pipelines/megaplan/cloud/human_review_diagnostic.py:391-453`.
- Delegated diagnostic retry writer: local launch state and a stable-gate-only cap of three attempts: `arnold_pipelines/megaplan/cloud/human_review_diagnostic.py:455-531`; `_MAX_STABLE_GATE_LAUNCH_ATTEMPTS=3`: `arnold_pipelines/megaplan/cloud/human_review_diagnostic.py:49`.
- Generic effect writer/adapter: `EffectProtocol` and `DeliveryEffects`: `arnold/workflow/effect_protocol.py:140-153`; `arnold_pipelines/megaplan/resident/delivery_effects.py:178-282`.
- Provider consumers/callers: `DiscordOutboundSink` routes through WBC or direct Discord: `arnold_pipelines/megaplan/resident/discord.py:408-425`, `:426-577`, `:580-641`; structured DM has the same WBC-then-direct fallback: `arnold_pipelines/megaplan/discord_dm.py:114-217`.
- Resident completion consumer: sweep calls WBC with a fake success callback and then always calls `outbound.send`: `arnold_pipelines/megaplan/resident/subagent.py:7162-7213`.
- Parallel notification writers: Guardian notifier: `agentbox/guardian/notifications.py:83-156`; reset notification outbox: `agentbox/reset_notifications.py:459-493`, `:733-855`; scheduler notifications: `arnold_pipelines/megaplan/resident/scheduler.py:574-616`, `:647-695`.
- Parallel escalation reader/authority: legacy JSONL escalation state and answer authorization: `arnold_pipelines/megaplan/resident/escalations.py:114-160`, `:163-214`, `:233-249`.
- No concrete repository worker draining the incident notification outbox was found; the module explicitly leaves provider delivery outside itself: `arnold_pipelines/megaplan/cloud/incident_notification.py:1-13`.

## Adherence gaps

1. **P0 — authority mutation: direct provider bypass and fallback.**  
   `discord_dm.py` sends through a real Discord transport inside `apply_fn`, but any WBC failure or exception falls through to a second direct-send path: `arnold_pipelines/megaplan/discord_dm.py:114-181`. `DeliveryEffects.deliver` converts provider exceptions into `OUTCOME_FAILED`, not `INDETERMINATE`: `arnold_pipelines/megaplan/resident/delivery_effects.py:178-282`. Therefore an applied-then-timeout can be retried outside the same effect attempt. This is an observed duplicate-side-effect mechanism; duplicate delivery under an ambiguous provider result is an inference about runtime timing.

   `DiscordOutboundSink` is worse: its WBC callback is a fake `{"delivered": True}` result, so WBC can report completion without sending Discord; on block/error it falls through to direct delivery: `arnold_pipelines/megaplan/resident/discord.py:580-641`. The resident completion sweep invokes the same fake-success route and then unconditionally sends directly: `arnold_pipelines/megaplan/resident/subagent.py:7165-7213`.

2. **P0 — authority mutation: budgets are fragmented and bypassable.**  
   Provider attempts accept arbitrary positive attempt numbers and have no occurrence-wide maximum: `arnold_pipelines/megaplan/cloud/incident_notification.py:367-396`. `dispatch_eligible` permits another attempt after `FAILED` without a durable total budget: `:455-463`.

   Diagnostic launches cap only stable-human-gate retries; other launches remain retryable: `arnold_pipelines/megaplan/cloud/human_review_diagnostic.py:455-498`. Resident completion delivery has its own eight-attempt counter, while delegated completion verification has a separate eight-attempt counter: `arnold_pipelines/megaplan/resident/subagent.py:6239-6265`, `:6341-6365`, `:6441-6504`. Reset delivery has another independent eight-attempt file budget: `agentbox/reset_notifications.py:28-42`, `:814-855`. These counters can multiply across one occurrence rather than consume one shared durable allowance.

3. **P1 — authority mutation: admission is not fully atomic.**  
   `admit` commits the event/outbox through `_outbox.append_event_with_outbox`, then separately inserts `incident_occurrences`: `arnold_pipelines/megaplan/cloud/incident_notification.py:253-293`. A crash between those operations can leave a durable effect intent without the occurrence authority row. This is directly observable from transaction ordering; whether production has encountered it is unknown.

4. **P1 — status misreporting: provider receipts are not an idempotent state machine.**  
   Duplicate provider attempts do not compare request digests, and receipt updates can overwrite prior status except for sticky `INDETERMINATE`: `arnold_pipelines/megaplan/cloud/incident_notification.py:367-453`. A later `SUCCEEDED` or `FAILED` receipt can therefore change authoritative status and eligibility incorrectly.

   `record_fallback_delivery` writes local `delivered` state before recording provider attempt/receipt and swallows recording failures: `arnold_pipelines/megaplan/cloud/human_review_diagnostic.py:651-700`. This can suppress retries while the canonical ledger still lacks delivery evidence.

5. **P1 — authority mutation/status misreporting: duplicate local notification authorities.**  
   Guardian dedupe checks and marks state in separate operations around direct provider delivery: `agentbox/guardian/notifications.py:83-156`; state methods are separate: `agentbox/guardian/state.py:62-82`. FileStore message deduplication is scan-then-write rather than one shared atomic authority operation: `arnold_pipelines/megaplan/store/_file/conversations.py:19-63`.

   Reset and scheduler notifications use independent JSON/file or conversation idempotency records and direct `outbound.send`, not the incident occurrence ledger: `agentbox/reset_notifications.py:459-493`; `arnold_pipelines/megaplan/resident/scheduler.py:574-616`. This is an observed parallel implementation and an inferred duplicate risk when these surfaces represent the same incident lifecycle.

6. **P1 — authority/status split: legacy escalation state remains authoritative at the reader boundary.**  
   Escalation authorization reads and folds legacy JSONL records, including malformed-line skipping, rather than the canonical incident occurrence and authority-transition tables: `arnold_pipelines/megaplan/resident/escalations.py:114-160`, `:163-214`, `:233-249`. The inspected code does not prove the final mutation caller, so reachability to an incorrect mutation is unknown; the bypassed reader is directly evidenced.

7. **P1 — authority mutation: authority transitions lack idempotent/CAS semantics.**  
   Transitions use random IDs, require only nonempty caller strings, and enforce uniqueness by `(occurrence_id, action)` such that repeated actions error rather than deduplicate; resolve/acknowledge ordering can leave inconsistent state: `arnold_pipelines/megaplan/cloud/incident_notification.py:465-529`.

## Incident reachability and severity

The direct path is reachable from watchdog notification escalation into `human_review_diagnostic`, then `IncidentNotificationStore.admit`: `arnold_pipelines/megaplan/cloud/wrappers/arnold-watchdog:1135-1152`; `arnold_pipelines/megaplan/cloud/human_review_diagnostic.py:391-453`.

P0 is justified by observed code paths that can issue provider effects outside WBC and by independent retry counters that permit more than the intended occurrence-wide allowance. P1 covers crash windows, split authority, and status corruption. Existing tests prove some same-occurrence deduplication and provider ambiguity blocking, but not the bypasses: `tests/cloud/test_incident_notification_ux.py:54-84`, `:222-271`; `tests/cloud/test_human_review_diagnostic.py:318-379`.

## Minimal generalized remediation

Consolidate on `IncidentNotificationStore` for incident occurrence/admission/authority and `EffectProtocol`/`LedgerOutbox` for effects. Add a narrow shared occurrence-budget table/API, keyed by occurrence and stable effect lineage, with atomic reservation across diagnostic launch, delegated verification, provider attempt, fallback, and notification delivery.

First, make occurrence insertion and event/outbox insertion one SQLite transaction. Then require every provider attempt to reserve the shared budget and use a stable attempt key; reject divergent payloads. Implement `PENDING → SUCCEEDED|FAILED|INDETERMINATE`, with sticky unknown and provider reconciliation before any retry.

Replace direct/fallback sends with one canonical provider adapter. Preserve local manifests, cards, Guardian state, reset records, and scheduler messages only as projections or migrated compatibility records. Migrate legacy escalation rows into canonical occurrences/transitions, then make the legacy reader read-only and remove its authority role.

This is narrower than a broad rewrite: one shared reservation/state API and call-site consolidation fixes the invariant while retaining existing projections and provider adapters.

## Required tests and retirement proof

- Concurrent 200-call, multi-process, and two-container tests: one occurrence, one event, one outbox, one provider attempt, and one shared budget consumption.
- Crash injection after outbox commit, after provider acceptance before receipt, and after local projection before canonical receipt; restart must reconcile orphan/unknown state without blind resend.
- Provider matrix covering success, explicit failure, timeout after application, lost ACK, and query-unavailable; unknown must remain sticky.
- Budget contention tests proving diagnostic retry, delegation, repair, fallback, and notification consume one occurrence-wide maximum rather than separate maxima.
- Authority tests for duplicate/concurrent acknowledge/resolve, invalid authority identity, ordering, and CAS behavior.
- Two-container/PID-namespace tests must use a demonstrably shared SQLite/filesystem volume; otherwise the implementation must fail closed rather than rely on process-local `flock`.
- Static/import tests must prove scoped incident/escalation writers no longer call direct `outbound.send`, `send_discord_dm`, or legacy JSONL mutation paths. Migration is complete only when repository-wide call-site search shows canonical adapter usage, legacy rows are backfilled/read-only, and old implementations are deleted or unreachable—not merely wrapped.

## Unknowns

No live service, cloud database, provider, or deployment state was inspected. Production enablement of `DeliveryEffects`, shared-volume topology, and actual outbox-worker deployment are therefore unknown. The final escalation mutation caller was not identified beyond the legacy reader. Provider-side Discord nonce behavior and whether all notification routes represent the same occurrence also require deployment-level verification.