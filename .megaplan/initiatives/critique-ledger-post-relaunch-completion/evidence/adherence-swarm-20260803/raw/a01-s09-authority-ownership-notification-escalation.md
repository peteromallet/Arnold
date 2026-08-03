# a01-s09-authority-ownership-notification-escalation: authority-ownership × notification-escalation

## Verdict

FAIL. There are two independent P0 authority violations and several P1 consistency/status gaps.

Observed authority mutations occur in:

- `IncidentNotificationStore.authority_transition`, which mutates a local authority table without a canonical ledger transition.
- The legacy repair-loop provider path, which calls `DISCORD_DM_BIN` directly and records delivery in a sidecar later consumed as authorization state.

The intended canonical WBC/outbox implementation exists, but callers bypass it and the notification intent currently has no in-tree consumer.

## Intended canonical contract

`arnold/workflow/ledger_outbox.py:1-15,345-360` defines the transactional contract: parent ledger event and outbox record commit atomically; outbox rows are delivery intent/projection state and do not grant dispatch authority.

The stronger canonical provider contract is `EffectProtocol`: reserve a global effect, persist intent before dispatch, verify current Run Authority and Custody, then accept one terminal or indeterminate outcome (`arnold/workflow/effect_protocol.py:1-29,140-153,277-303,307-322`). `DeliveryEffects` is the existing adapter over that single protocol and explicitly introduces no second ledger (`arnold_pipelines/megaplan/resident/delivery_effects.py:1-12,178-244`).

M1 incident lifecycle authority is separate and append-only: `IncidentLedger.append_event` validates and appends to `.megaplan/incident-ledger/events.jsonl` (`arnold_pipelines/megaplan/incident/ledger.py:24-46`). Incident/problem JSON files are projections rebuilt from that event stream (`arnold_pipelines/megaplan/incident/projection.py:38-110`).

## Evidence and complete path inventory

I searched with `rg --files` for incident, notification, escalation, outbox, provider, resident, wrapper, schema, and test files; then used `rg -n` across `arnold_pipelines`, `arnold`, `scripts`, `tests`, and `docs` for `IncidentNotificationStore`, `notification:discord`, `authority_transition`, provider receipt methods, `EscalationLedgerWriter`, `needs-human`, and escalation IDs. I traced every production caller returned by those searches and inspected the relevant tests and schemas.

- M1 writers are the bridge helpers in `incident_bridge.py:226-231,254-379,435-762,907-1191`; readers are projection/CLI paths in `incident/projection.py:38-110,972-1034` and `incident/cli.py:81-97`.
- Notification admission is written by `IncidentNotificationStore.admit` (`cloud/incident_notification.py:170-307`), called by `human_review_diagnostic.py:424,437-444`. The same caller directly invokes provider-attempt/receipt methods at `human_review_diagnostic.py:680-694`.
- The notification store emits `notification:discord` at `incident_notification.py:252-267`, but the repository contains no matching worker/provider-consumer implementation. The watchdog merely reports that a separate worker owns delivery (`cloud/wrappers/arnold-watchdog:1217-1221`).
- A separate resident completion path creates Discord outbox identities at `resident/subagent.py:4101-4136`; `resident/discord.py:1493-1504` runs its sweep.
- Legacy escalation writers are enabled in `cloud/wrappers/arnold-progress-auditor:6661-6708`, `cloud/wrappers/arnold-repair-loop:8461-8474`, and `resident/runtime.py:1448-1479`. Readers include the watchdog (`cloud/wrappers/arnold-watchdog:5586-5620`), resident Discord resolution (`resident/discord.py:1254-1277`), and resident authorization (`resident/escalations.py:61-111,114-160`).
- Existing tests cover two processes, thread races, restart after projection loss, and indeterminate receipts (`tests/cloud/test_incident_notification_ux.py:54-84,134-160,197-271`), but also directly bless `authority_transition` (`:274-312`).

## Adherence gaps

1. **P0 — duplicate authority mutation.**  
   `authority_transition` accepts arbitrary `authority_id` and `actor_id`, updates `incident_occurrences.authority_state_json`, inserts `incident_authority_transitions`, and calls the card a projection only after declaring the local table authoritative (`cloud/incident_notification.py:465-530`). No canonical `LedgerEvent`, WBC reservation, owner check, or custody fence is emitted. The test invokes it directly with `"run-authority:operator-1"` (`tests/cloud/test_incident_notification_ux.py:293-312`). This is an authority mutation, not status misreporting.

2. **P0 — sidecar/provider bypass becomes manual-review authority.**  
   The legacy repair loop calls `DISCORD_DM_BIN` directly (`cloud/wrappers/arnold-repair-loop:8488-8508,8548-8549`) and writes `delivered` to the escalation sidecar (`:8573-8585`). `resident/escalations.py` then authorizes replies/resolution based on sidecar-derived delivery, supersession, and message IDs (`:81-111,114-160`). Thus a projection/sidecar controls whether a user may mutate repair state. This is both an authority-ownership violation and a provider mutation bypass.

3. **P0 — two reachable notification authorities/effect identities.**  
   Human-review admission creates a WBC outbox intent `notification:discord` (`cloud/incident_notification.py:252-267`), while resident completion creates `resident-subagent-completion:<run_id>` (`resident/subagent.py:4103-4116`) and is actually swept by resident Discord (`resident/discord.py:1493-1504`). The watchdog claims the first is pending and separately says the resident diagnostic owns terminal delivery (`cloud/wrappers/arnold-watchdog:1184-1193,1217-1221`). Inference: adding the missing worker without retiring the resident path can duplicate user notifications; leaving it absent can strand admitted intents.

4. **P1 — caller-controlled authority identity and insufficient owner validation.**  
   `admit` only checks that `owner` is a nonempty string (`cloud/incident_notification.py:170-184`), then records it as provenance while minting the fixed grant `"run-authority:incident-notification-admission"` (`:223-249`). The production caller supplies `"watchdog"` (`cloud/human_review_diagnostic.py:437-443`). There is no current Run Authority/Custody reread. Additionally, `_escalation_id` accepts a caller-provided ID after regex validation (`human_review_diagnostic.py:225-261`). These are canonical mutation/dedupe inputs, not merely display fields.

5. **P1 — event/outbox and occurrence metadata are not one transaction.**  
   `admit` commits the canonical event/outbox at line 267, then starts a separate `BEGIN IMMEDIATE` for `incident_occurrences` at lines 269-293. A crash or storage failure between them leaves an outbox intent without the local dedupe/occurrence row. Existing restart coverage only simulates death before JSON projection (`tests/cloud/test_incident_notification_ux.py:197-220`).

6. **P1 — provider receipts are an unbound local authority.**  
   `record_provider_attempt`, `record_provider_receipt`, and `dispatch_eligible` accept arbitrary intent IDs, request digests, statuses, and receipts and consult only `notification_provider_attempts` (`cloud/incident_notification.py:367-463`). They do not verify canonical outbox membership, provider identity, owner, reservation, or custody. `record_fallback_delivery` writes `state.json` as delivered before receipt persistence and suppresses receipt errors (`human_review_diagnostic.py:651-698`). This is status misreporting plus a provider mutation bypass.

7. **P2 — legacy sidecar lifecycle API remains reachable.**  
   `EscalationLedgerWriter.enable` permits arbitrary sidecar destinations and writes opened/delivered/answered/resolved lifecycle records (`cloud/human_blockers.py:638-711,713-905`). Tests intentionally validate these writes (`tests/cloud/test_human_blockers.py:1159-1185`). Even where intended as observe-only, production readers use the records as authorization inputs.

## Incident reachability and severity

The P0 paths are statically reachable in the current checkout: the legacy wrapper invokes the provider when its executable exists, and resident authorization reads the resulting sidecar. The notification outbox path is also reachable through `launch_human_review_diagnostic`.

Actual external delivery may be action-off for `DeliveryEffects` (`resident/delivery_effects.py:111-119,197-202`), but that does not neutralize the legacy direct provider path. The missing notification worker is an observed repository gap; duplicate delivery after a future worker is an inference from the two independent effect identities.

## Minimal generalized remediation

Consolidate notification delivery on `EffectProtocol`/`DeliveryEffects`, retaining M1 `IncidentLedger` only for incident lifecycle. Make `IncidentNotificationStore` a thin adapter or remove it; do not retain its parallel authority/provider tables.

- Replace `authority_transition` with canonical acknowledged/resolved ledger events requiring validated owner, current grant, and custody.
- Atomically persist occurrence identity with the canonical event/outbox, or derive occurrence metadata exclusively from that event.
- Derive escalation/occurrence identity from the canonical current-target tuple; reject caller-supplied mismatches.
- Delete the direct `DISCORD_DM_BIN` path and all new sidecar lifecycle writes. Migrate historical sidecars as read-only evidence; `resident/escalations.py` must authorize from canonical delivery receipts, not sidecar state.
- Choose one notification effect identity and retire the other. Given the existing consumer, the resident/WBC path is the smallest consolidation target.

## Required tests and retirement proof

Add deterministic tests for:

- concurrent threads, processes, and two containers with separate PID namespaces sharing one durable root: one occurrence, one effect reservation, one provider outcome;
- crash between every persistence boundary and restart, including before occurrence metadata commit;
- provider success, failure, timeout/indeterminate, restart, idempotency-key replay, and stale-owner/custody rejection;
- forged owner/grant, caller escalation ID, receipt, sidecar “delivered,” and direct SQL/method authority mutations;
- card/projection corruption proving no authority change;
- static and runtime proof that no production path references `authority_transition`, `record_provider_*`, `EscalationLedgerWriter.enable`, `DISCORD_DM_BIN`, or the retired notification destination. Historical sidecars may remain only under a read-only migration reader.

## Unknowns

No current in-tree notification worker or provider implementation matched the searches; deployment-side consumers were not inspected. It is also unclear whether M1 incident IDs and notification occurrence IDs are intentionally separate resources or an accidental second occurrence authority. No cloud state or external provider configuration was consulted.